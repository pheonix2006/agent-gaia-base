# src/ai_agent/tools/web/google_search.py

"""Google 搜索工具（Serper API）"""

import json
import logging
from typing import Any, Optional, List
import httpx

from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.llm.config import LLMSettings


logger = logging.getLogger(__name__)


class GoogleSearchTool(BaseAgentTool):
    """使用 Serper API 进行 Google 搜索"""

    name = "google_search"
    description = "通过 Google 搜索获取信息。返回搜索结果摘要列表。适用于查找最新信息或特定内容。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或问题",
            },
            "k": {
                "type": "integer",
                "default": 5,
                "description": "返回结果数量",
            },
            "gl": {
                "type": "string",
                "default": "us",
                "description": "国家/地区代码",
            },
            "hl": {
                "type": "string",
                "default": "en",
                "description": "语言代码",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self):
        self._settings: Optional[LLMSettings] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def settings(self) -> LLMSettings:
        """懒加载配置"""
        if self._settings is None:
            self._settings = LLMSettings()
        return self._settings

    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def _search(self, query: str, k: int = 5, gl: str = "us", hl: str = "en") -> dict:
        """调用 Serper API 执行搜索"""
        api_key = self.settings.serper_api_key
        base_url = self.settings.serper_base_url

        if not api_key:
            raise ValueError("SERPER_API_KEY 未配置")

        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }
        payload = {"q": query, "num": k, "gl": gl, "hl": hl}

        client = await self._get_http_client()
        response = await client.post(base_url, json=payload, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"Serper API 错误 ({response.status_code}): {response.text[:500]}")
        return response.json()

    def _parse_results(self, results: dict, k: int) -> List[dict]:
        """解析搜索结果"""
        snippets: List[dict] = []

        # 1. 优先返回 answerBox（直接答案）
        answer_box = results.get("answerBox") or {}
        if isinstance(answer_box, dict):
            if answer_box.get("answer"):
                return [{"content": str(answer_box.get("answer")), "source": "None"}]
            if answer_box.get("snippet"):
                return [{"content": str(answer_box.get("snippet")).replace("\n", " "), "source": "None"}]
            if answer_box.get("snippetHighlighted"):
                return [{"content": str(answer_box.get("snippetHighlighted")), "source": "None"}]

        # 2. 知识图谱
        kg = results.get("knowledgeGraph") or {}
        if isinstance(kg, dict):
            title = kg.get("title")
            etype = kg.get("type")
            if etype:
                snippets.append({"content": f"{title}: {etype}", "source": "None"})
            desc = kg.get("description")
            if desc:
                snippets.append({"content": str(desc), "source": "None"})
            for attr, val in (kg.get("attributes") or {}).items():
                snippets.append({"content": f"{attr}: {val}", "source": "None"})

        # 3. 自然搜索结果
        for item in (results.get("organic") or [])[: max(1, k)]:
            if "snippet" in item:
                snippets.append({
                    "content": str(item.get("snippet")),
                    "source": str(item.get("link", "None")),
                })
            for attr, val in (item.get("attributes") or {}).items():
                snippets.append({
                    "content": f"{attr}: {val}",
                    "source": str(item.get("link", "None")),
                })

        # 4. 无结果时返回默认
        if not snippets:
            return [{"content": "No good Google Search Result was found", "source": "None"}]

        return snippets

    async def run(self, query: str, k: int = 5, gl: str = "us", hl: str = "en") -> ToolResult:
        """执行 Google 搜索"""
        import time
        start_time = time.time()

        try:
            results = await self._search(query, k=k, gl=gl, hl=hl)
            parsed = self._parse_results(results, k)

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
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                metrics={"elapsed_time": time.time() - start_time},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"搜索失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
