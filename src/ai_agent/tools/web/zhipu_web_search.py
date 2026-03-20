# src/ai_agent/tools/web/zhipu_web_search.py

"""智谱 Web Search 工具"""

import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types import ToolResult, AnyDict
from ai_agent.llm.config import LLMSettings


logger = logging.getLogger(__name__)


class ZhipuWebSearchParams(BaseModel):
    """智谱 Web Search 参数"""

    query: str = Field(description="搜索关键词或问题", max_length=70)
    count: int = Field(default=10, ge=1, le=50, description="返回结果数量")
    search_recency_filter: str = Field(
        default="noLimit",
        description="时间范围过滤: oneDay, oneWeek, oneMonth, oneYear, noLimit",
    )


class ZhipuWebSearchTool(BaseAgentTool[ZhipuWebSearchParams, list[dict[str, Any]]]):
    """智谱 Web Search 工具 - 专为中文搜索优化

    使用智谱 AI 的 Web Search API 进行网络搜索，支持意图识别和多引擎。
    需要 ZHIPU_API_KEY 环境变量。
    """

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return """搜索互联网获取实时信息。

适用场景：
- 查询最新新闻、事件、动态
- 获取事实性信息、数据、统计
- 查找技术文档、教程、解决方案
- 中文内容搜索效果更佳

参数说明：
- query: 搜索关键词，不超过70字符
- count: 返回结果数量，1-50，默认10
- search_recency_filter: 时间过滤，可选 oneDay/oneWeek/oneMonth/oneYear/noLimit"""

    @property
    def params_schema(self) -> type[ZhipuWebSearchParams]:
        return ZhipuWebSearchParams

    def __init__(self) -> None:
        self._settings: LLMSettings | None = None

    @property
    def settings(self) -> LLMSettings:
        """懒加载配置"""
        if self._settings is None:
            self._settings = LLMSettings()
        return self._settings

    @settings.setter
    def settings(self, value: LLMSettings | None) -> None:
        """设置配置（用于测试注入）"""
        self._settings = value

    @settings.deleter
    def settings(self) -> None:
        """删除配置（用于测试清理）"""
        self._settings = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """创建 HTTP 客户端"""
        return httpx.AsyncClient(timeout=30.0)

    async def _search(
        self,
        query: str,
        count: int = 10,
        search_recency_filter: str = "noLimit",
    ) -> dict[str, Any]:
        """调用智谱 Web Search API"""
        api_key = self.settings.zhipu_api_key
        base_url = self.settings.zhipu_web_search_url

        if not api_key:
            raise ValueError("ZHIPU_API_KEY 未配置，请在 .env 文件中设置")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "search_query": query,
            "search_engine": "search_pro",
            "search_intent": False,
            "count": count,
            "search_recency_filter": search_recency_filter,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(base_url, json=payload, headers=headers)

            if response.status_code >= 400:
                error_text = response.text[:500]
                raise RuntimeError(f"智谱 API 错误 ({response.status_code}): {error_text}")

            data: dict[str, Any] = response.json()
            return data

    def _parse_results(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """解析搜索结果，返回精简格式

        仅保留核心字段：title, content, link
        """
        results: list[dict[str, Any]] = []
        search_result = response.get("search_result") or []

        for item in search_result:
            result: dict[str, Any] = {
                "title": str(item.get("title", "")),
                "content": str(item.get("content", "")),
                "link": str(item.get("link", "")),
            }
            results.append(result)

        if not results:
            return [{"title": "", "content": "未找到相关搜索结果", "link": ""}]

        return results

    async def run(self, params: ZhipuWebSearchParams) -> ToolResult[list[dict[str, Any]]]:
        """执行智谱 Web Search"""
        start_time = time.time()

        try:
            response = await self._search(
                query=params.query,
                count=params.count,
                search_recency_filter=params.search_recency_filter,
            )
            parsed = self._parse_results(response)

            return ToolResult(
                success=True,
                data=parsed,
                error=None,
                metrics={
                    "elapsed_time": time.time() - start_time,
                    "result_count": len(parsed),
                },
            )

        except ValueError as e:
            logger.error(f"配置错误: {e}")
            return ToolResult(
                success=False,
                data=[],
                error=str(e),
                metrics={"elapsed_time": time.time() - start_time},
            )
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return ToolResult(
                success=False,
                data=[],
                error=f"搜索失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
