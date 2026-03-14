# src/ai_agent/tools/web/google_search.py

"""Google 搜索工具（Serper API）"""

import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types import ToolResult, AnyDict
from ai_agent.llm.config import LLMSettings


logger = logging.getLogger(__name__)


class GoogleSearchParams(BaseModel):
    """Google 搜索参数"""

    query: str = Field(description="搜索关键词或问题")
    k: int = Field(default=5, ge=1, le=20, description="返回结果数量")
    gl: str = Field(default="us", min_length=2, max_length=2, description="国家/地区代码 (e.g., us, cn, uk)")
    hl: str = Field(default="en", min_length=2, max_length=5, description="语言代码 (e.g., en, zh, zh-CN, ja)")


class GoogleSearchTool(BaseAgentTool[GoogleSearchParams, list[dict[str, Any]]]):
    """Search via Serper (google.serper.dev) and return snippets. Requires SERPER_API_KEY."""

    @property
    def name(self) -> str:
        return "google_search"

    @property
    def description(self) -> str:
        return "Search via Serper (google.serper.dev) and return snippets. Requires SERPER_API_KEY."

    @property
    def params_schema(self) -> type[GoogleSearchParams]:
        return GoogleSearchParams

    def __init__(self) -> None:
        self._settings: LLMSettings | None = None

    @property
    def settings(self) -> LLMSettings:
        """懒加载配置"""
        if self._settings is None:
            self._settings = LLMSettings()
        return self._settings

    async def _get_http_client(self) -> httpx.AsyncClient:
        """创建新的 HTTP 客户端（每次调用都创建新的，避免线程安全问题）"""
        return httpx.AsyncClient(timeout=30.0)

    async def _search(self, query: str, k: int = 5, gl: str = "us", hl: str = "en") -> dict[str, Any]:
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
        data: dict[str, Any] = response.json()
        return data

    def _parse_results(self, results: dict[str, Any], k: int) -> list[dict[str, Any]]:
        """解析搜索结果

        answerBox 和 organic 结果都会返回，answerBox 作为第一条（如果有）
        """
        snippets: list[dict[str, Any]] = []

        # 1. answerBox 作为第一条（如果有），不再直接 return
        answer_box = results.get("answerBox") or {}
        if isinstance(answer_box, dict):
            if answer_box.get("answer"):
                snippets.append({"content": str(answer_box.get("answer")), "source": "answer_box"})
            elif answer_box.get("snippet"):
                snippets.append({"content": str(answer_box.get("snippet")).replace("\n", " "), "source": "answer_box"})
            elif answer_box.get("snippetHighlighted"):
                snippets.append({"content": str(answer_box.get("snippetHighlighted")), "source": "answer_box"})

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

    async def run(self, params: GoogleSearchParams) -> ToolResult[list[dict[str, Any]]]:
        """执行 Google 搜索"""
        start_time = time.time()

        try:
            results = await self._search(params.query, k=params.k, gl=params.gl, hl=params.hl)
            parsed = self._parse_results(results, params.k)

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
                data=[],
                error=str(e),
                metrics={"elapsed_time": time.time() - start_time},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=[],
                error=f"搜索失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
