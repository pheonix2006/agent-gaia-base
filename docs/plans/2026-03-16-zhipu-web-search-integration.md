# 智谱 Web Search 工具集成实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 集成智谱 AI Web Search API 作为新的网络搜索工具，支持通过配置切换使用智谱搜索或 Google 搜索。

**Architecture:** 新建独立的 `ZhipuWebSearchTool` 工具类，遵循现有 `BaseAgentTool` 模式。在 `LLMSettings` 中添加配置项，通过 `WEB_SEARCH_PROVIDER` 环境变量切换搜索引擎。API Key 通过 `ZHIPU_API_KEY` 环境变量管理。

**Tech Stack:** Pydantic、httpx、智谱 Web Search API

---

## Task 1: 扩展 LLM 配置

**Files:**
- Modify: `src/ai_agent/llm/config.py:29-31`

**Step 1: 添加智谱搜索配置项**

在 `LLMSettings` 类中添加以下配置：

```python
    # Serper API 配置（Google 搜索）
    serper_api_key: str = Field(default="", repr=False)
    serper_base_url: str = "https://google.serper.dev/search"

    # 智谱 Web Search API 配置
    zhipu_api_key: str = Field(default="", repr=False)
    zhipu_web_search_url: str = "https://open.bigmodel.cn/api/paas/v4/web_search"

    # 搜索引擎选择：zhipu | google
    web_search_provider: str = Field(default="zhipu", description="搜索引擎提供者")
```

**Step 2: 验证配置加载**

```bash
uv run python -c "from ai_agent.llm.config import LLMSettings; s = LLMSettings(); print(f'Provider: {s.web_search_provider}')"
```

Expected: `Provider: zhipu`

**Step 3: Commit**

```bash
git add src/ai_agent/llm/config.py
git commit -m "feat(config): add Zhipu Web Search API configuration"
```

---

## Task 2: 创建 ZhipuWebSearchTool 工具

**Files:**
- Create: `src/ai_agent/tools/web/zhipu_web_search.py`

**Step 1: 创建工具文件**

```python
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
```

**Step 2: 验证语法正确**

```bash
uv run python -c "from ai_agent.tools.web.zhipu_web_search import ZhipuWebSearchTool; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add src/ai_agent/tools/web/zhipu_web_search.py
git commit -m "feat(tools): add ZhipuWebSearchTool for Zhipu AI web search"
```

---

## Task 3: 更新工具模块导出

**Files:**
- Modify: `src/ai_agent/tools/__init__.py`
- Modify: `src/ai_agent/tools/web/__init__.py`

**Step 1: 更新 web/__init__.py**

```python
# src/ai_agent/tools/web/__init__.py

"""Web 相关工具"""

from ai_agent.tools.web.google_search import GoogleSearchTool
from ai_agent.tools.web.web_content import WebContentTool
from ai_agent.tools.web.zhipu_web_search import ZhipuWebSearchTool

__all__ = [
    "GoogleSearchTool",
    "WebContentTool",
    "ZhipuWebSearchTool",
]
```

**Step 2: 更新 tools/__init__.py**

在现有导出基础上添加 `ZhipuWebSearchTool`：

```python
from ai_agent.tools.web.zhipu_web_search import ZhipuWebSearchTool
```

**Step 3: 验证导出**

```bash
uv run python -c "from ai_agent.tools import ZhipuWebSearchTool; print(ZhipuWebSearchTool().name)"
```

Expected: `web_search`

**Step 4: Commit**

```bash
git add src/ai_agent/tools/__init__.py src/ai_agent/tools/web/__init__.py
git commit -m "feat(tools): export ZhipuWebSearchTool"
```

---

## Task 4: 更新 API 入口，支持配置切换

**Files:**
- Modify: `src/ai_agent/api/main.py:62-70`

**Step 1: 修改 lifespan 中的工具初始化逻辑**

```python
    # 初始化所有工具并转换为 LangChain 格式
    from ai_agent.tools.base import BaseAgentTool
    from ai_agent.llm.config import LLMSettings

    settings = LLMSettings()

    # 根据配置选择搜索引擎
    if settings.web_search_provider == "zhipu":
        from ai_agent.tools import ZhipuWebSearchTool
        search_tool = ZhipuWebSearchTool()
        logger.info("使用智谱 Web Search")
    else:
        from ai_agent.tools import GoogleSearchTool
        search_tool = GoogleSearchTool()
        logger.info("使用 Google Search (Serper)")

    tools: list[BaseAgentTool] = [
        search_tool,
        WebContentTool(),
        ImageAnalysisTool(),
        AudioParseTool(),
    ]
    langchain_tools = [tool.to_langchain_tool() for tool in tools]
    logger.info(f"已加载 {len(langchain_tools)} 个工具: {[t.name for t in langchain_tools]}")
```

**Step 2: 验证导入**

```bash
uv run python -c "from ai_agent.api.main import app; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add src/ai_agent/api/main.py
git commit -m "feat(api): add web search provider configuration"
```

---

## Task 5: 更新 .env.example（如存在）

**Files:**
- Modify: `.env.example` (如存在) 或创建

**Step 1: 添加配置示例**

```env
# 搜索引擎配置
WEB_SEARCH_PROVIDER=zhipu    # zhipu | google

# 智谱 AI API
ZHIPU_API_KEY=your_zhipu_api_key_here

# Serper API (Google Search)
SERPER_API_KEY=your_serper_api_key_here
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add Zhipu search config to .env.example"
```

---

## Task 6: 编写单元测试

**Files:**
- Create: `tests/unit/tools/web/test_zhipu_web_search.py`

**Step 1: 创建测试文件**

```python
# tests/unit/tools/web/test_zhipu_web_search.py

"""ZhipuWebSearchTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ai_agent.tools.web.zhipu_web_search import (
    ZhipuWebSearchTool,
    ZhipuWebSearchParams,
)


class TestZhipuWebSearchParams:
    """参数模型测试"""

    def test_default_values(self) -> None:
        """测试默认参数值"""
        params = ZhipuWebSearchParams(query="test")
        assert params.query == "test"
        assert params.count == 10
        assert params.search_recency_filter == "noLimit"

    def test_custom_values(self) -> None:
        """测试自定义参数值"""
        params = ZhipuWebSearchParams(
            query="Python 教程",
            count=20,
            search_recency_filter="oneWeek",
        )
        assert params.count == 20
        assert params.search_recency_filter == "oneWeek"

    def test_query_max_length(self) -> None:
        """测试查询最大长度限制"""
        long_query = "a" * 71
        with pytest.raises(Exception):  # Pydantic ValidationError
            ZhipuWebSearchParams(query=long_query)

    def test_count_range(self) -> None:
        """测试结果数量范围"""
        with pytest.raises(Exception):
            ZhipuWebSearchParams(query="test", count=0)
        with pytest.raises(Exception):
            ZhipuWebSearchParams(query="test", count=51)


class TestZhipuWebSearchTool:
    """工具类测试"""

    def test_tool_name(self) -> None:
        """测试工具名称"""
        tool = ZhipuWebSearchTool()
        assert tool.name == "web_search"

    def test_tool_description(self) -> None:
        """测试工具描述"""
        tool = ZhipuWebSearchTool()
        assert "搜索" in tool.description

    def test_params_schema(self) -> None:
        """测试参数 schema"""
        tool = ZhipuWebSearchTool()
        assert tool.params_schema == ZhipuWebSearchParams

    def test_to_langchain_tool(self) -> None:
        """测试转换为 LangChain 工具"""
        tool = ZhipuWebSearchTool()
        lc_tool = tool.to_langchain_tool()
        assert lc_tool.name == "web_search"

    @pytest.mark.asyncio
    async def test_run_missing_api_key(self) -> None:
        """测试缺少 API Key 时的错误处理"""
        tool = ZhipuWebSearchTool()

        with patch.object(
            tool,
            "settings",
            MagicMock(zhipu_api_key="", zhipu_web_search_url="https://example.com")
        ):
            params = ZhipuWebSearchParams(query="test")
            result = await tool.run(params)

            assert result.success is False
            assert "ZHIPU_API_KEY 未配置" in result.error

    def test_parse_results_empty(self) -> None:
        """测试空结果解析"""
        tool = ZhipuWebSearchTool()
        parsed = tool._parse_results({})

        assert len(parsed) == 1
        assert "未找到" in parsed[0]["content"]

    def test_parse_results_with_data(self) -> None:
        """测试正常结果解析"""
        tool = ZhipuWebSearchTool()
        response = {
            "search_result": [
                {
                    "title": "Python 官方文档",
                    "content": "Python 是一种编程语言",
                    "link": "https://python.org",
                    "icon": "https://python.org/favicon.ico",
                    "media": "Python.org",
                },
                {
                    "title": "Python 教程",
                    "content": "学习 Python 的最佳教程",
                    "link": "https://example.com/python",
                },
            ]
        }
        parsed = tool._parse_results(response)

        assert len(parsed) == 2
        assert parsed[0]["title"] == "Python 官方文档"
        assert parsed[0]["content"] == "Python 是一种编程语言"
        assert parsed[0]["link"] == "https://python.org"
        # 确保精简字段，不包含 icon
        assert "icon" not in parsed[0]
        assert "media" not in parsed[0]
```

**Step 2: 运行测试**

```bash
uv run pytest tests/unit/tools/web/test_zhipu_web_search.py -v
```

Expected: 所有测试通过

**Step 3: Commit**

```bash
git add tests/unit/tools/web/test_zhipu_web_search.py
git commit -m "test(tools): add unit tests for ZhipuWebSearchTool"
```

---

## Task 7: 类型检查验证

**Step 1: 运行 mypy**

```bash
uv run mypy src/ai_agent/tools/web/zhipu_web_search.py
```

Expected: `Success: no issues found`

**Step 2: 如果有类型错误，修复后再提交**

---

## Task 8: 集成测试（手动）

**Step 1: 配置 .env 文件**

```env
ZHIPU_API_KEY=b1081315874f4fdf93dc9a2a93a61812.ndRi1cCSOaIs6yuS
WEB_SEARCH_PROVIDER=zhipu
```

**Step 2: 启动服务**

```bash
uv run python -m ai_agent.api.main
```

**Step 3: 测试搜索**

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "搜索一下今天的新闻"}'
```

Expected: 返回带有搜索结果的响应

---

## 验收清单

- [ ] `ZHIPU_API_KEY` 环境变量正常读取
- [ ] `WEB_SEARCH_PROVIDER=zhipu` 时使用智谱搜索
- [ ] `WEB_SEARCH_PROVIDER=google` 时使用 Google 搜索
- [ ] 搜索结果精简返回（title, content, link）
- [ ] 单元测试全部通过
- [ ] mypy 类型检查通过
- [ ] 集成测试通过
