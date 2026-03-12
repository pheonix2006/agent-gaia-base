# Multi-Modal Tools Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 4 个多模态工具（网页提取、Google搜索、图像分析、音频解析），支持 ReAct Agent 调用。

**Architecture:**
- 扩展现有 `BaseAgentTool` 基类，支持异步调用和复杂返回值
- 工具按类型分组（web/media），每个工具独立文件
- 复用现有 `LLMSettings` 配置模式，新增 Jina/Serper API Key

**Tech Stack:**
- httpx / aiohttp - 异步 HTTP 请求
- openai - 多模态 API 调用
- tiktoken - 文本分词（长内容分块）
- pytest + pytest-asyncio - 异步测试

---

## Task 1: 扩展工具基类

**Files:**
- Modify: `src/ai_agent/tools/base.py`
- Modify: `src/ai_agent/llm/config.py`

### Step 1: 扩展 LLMSettings 添加新 API Key 配置

```python
# src/ai_agent/llm/config.py

"""LLM 配置模块"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM 配置

    从 .env 文件加载配置，支持所有兼容 OpenAI API 的服务。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI 兼容 API 配置
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-3.5-turbo"
    temperature: float = 0.7

    # Jina API 配置（网页内容提取）
    jina_api_key: str = ""

    # Serper API 配置（Google 搜索）
    serper_api_key: str = ""
    serper_base_url: str = "https://google.serper.dev/search"
```

### Step 2: 更新 .env.example

```env
# .env.example

# LLM 配置 (兼容 OpenAI API 格式)
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
TEMPERATURE=0.7

# Jina API 配置（网页内容提取）
JINA_API_KEY=your_jina_api_key_here

# Serper API 配置（Google 搜索）
SERPER_API_KEY=your_serper_api_key_here
SERPER_BASE_URL=https://google.serper.dev/search

# LangSmith 追踪配置
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key_here
LANGSMITH_PROJECT=ai-agent
```

### Step 3: 扩展 ToolResult 和 BaseAgentTool

```python
# src/ai_agent/tools/base.py

"""工具基类模块"""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel
from langchain_core.tools import Tool


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool
    data: Any  # 改为 Any 支持复杂结构
    error: str | None = None
    metrics: dict[str, Any] = {}  # 执行指标（耗时、token数等）


class BaseAgentTool(ABC):
    """工具基类，所有工具继承此类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述，供 LLM 理解用途"""
        pass

    @property
    def parameters(self) -> dict[str, Any]:
        """JSON Schema 格式的参数定义，供 LLM 理解参数结构"""
        return {}

    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        """执行工具逻辑（异步）"""
        pass

    def to_langchain_tool(self) -> Tool:
        """转换为 LangChain 工具格式"""
        import asyncio

        def sync_wrapper(*args, **kwargs):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            coro = self.run(**kwargs)
            if loop and loop.is_running():
                # 如果已在事件循环中，创建新线程运行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result().data
            else:
                return asyncio.run(coro).data

        return Tool(
            name=self.name,
            description=self.description,
            func=sync_wrapper,
        )
```

### Step 4: 更新 tools/__init__.py

```python
# src/ai_agent/tools/__init__.py

"""工具模块"""

from .base import BaseAgentTool, ToolResult
from .registry import ToolRegistry

__all__ = ["BaseAgentTool", "ToolResult", "ToolRegistry"]
```

### Step 5: 提交基类变更

```bash
git add src/ai_agent/tools/base.py src/ai_agent/tools/__init__.py src/ai_agent/llm/config.py .env.example
git commit -m "feat(tools): extend BaseAgentTool with async support and metrics"
```

---

## Task 2: 创建 Web 工具目录结构

**Files:**
- Create: `src/ai_agent/tools/web/__init__.py`

### Step 1: 创建 web 目录初始化文件

```python
# src/ai_agent/tools/web/__init__.py

"""Web 相关工具"""

from .web_content import WebContentTool
from .google_search import GoogleSearchTool

__all__ = ["WebContentTool", "GoogleSearchTool"]
```

### Step 2: 提交目录结构

```bash
git add src/ai_agent/tools/web/__init__.py
git commit -m "feat(tools): add web tools directory structure"
```

---

## Task 3: 实现 WebContentTool（Jina API）

**Files:**
- Create: `src/ai_agent/tools/web/web_content.py`
- Create: `tests/unit/tools/web/__init__.py`
- Create: `tests/unit/tools/web/test_web_content.py`

### Step 1: 创建单元测试目录

```python
# tests/unit/tools/web/__init__.py
```

### Step 2: 编写 WebContentTool 单元测试

```python
# tests/unit/tools/web/test_web_content.py

"""WebContentTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ai_agent.tools.web.web_content import WebContentTool


class TestWebContentTool:
    """WebContentTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = WebContentTool()
        assert tool.name == "web_content"
        assert "网页" in tool.description or "URL" in tool.description
        assert "url" in tool.parameters.get("properties", {})
        assert "query" in tool.parameters.get("properties", {})

    @pytest.mark.asyncio
    async def test_run_success(self):
        """测试成功提取网页内容"""
        tool = WebContentTool()

        with patch.object(tool, '_fetch_jina', new_callable=AsyncMock) as mock_fetch, \
             patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_fetch.return_value = "这是一段网页内容"
            mock_llm.return_value = "这是摘要答案"

            result = await tool.run(url="https://example.com", query="总结这篇文章")

            assert result.success is True
            assert result.data["answer"] == "这是摘要答案"
            assert result.data["url"] == "https://example.com"
            mock_fetch.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_run_fetch_failure(self):
        """测试网页获取失败"""
        tool = WebContentTool()

        with patch.object(tool, '_fetch_jina', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None

            result = await tool.run(url="https://invalid-url.com", query="测试")

            assert result.success is False
            assert "获取网页内容失败" in result.error

    @pytest.mark.asyncio
    async def test_run_empty_content(self):
        """测试空网页内容"""
        tool = WebContentTool()

        with patch.object(tool, '_fetch_jina', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = ""

            result = await tool.run(url="https://example.com", query="测试")

            assert result.success is False

    @pytest.mark.asyncio
    async def test_run_long_content_chunking(self):
        """测试长内容分块处理"""
        tool = WebContentTool()

        # 模拟超长内容（触发分块）
        long_content = "测试内容 " * 50000  # 约 10万 token

        with patch.object(tool, '_fetch_jina', new_callable=AsyncMock) as mock_fetch, \
             patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_llm, \
             patch('ai_agent.tools.web.web_content.tiktoken') as mock_tiktoken:
            mock_fetch.return_value = long_content
            mock_llm.return_value = "分块答案"
            # 模拟 tiktoken 返回超长 token 数
            mock_encoding = MagicMock()
            mock_encoding.encode.return_value = [1] * 100000  # 10万 token
            mock_encoding.decode.return_value = "解码内容"
            mock_tiktoken.get_encoding.return_value = mock_encoding

            result = await tool.run(url="https://example.com", query="总结")

            assert result.success is True
            # 应该调用多次 LLM（分块）
            assert mock_llm.call_count > 1
```

### Step 3: 运行测试确认失败

```bash
pytest tests/unit/tools/web/test_web_content.py -v
```

Expected: FAIL - ModuleNotFoundError

### Step 4: 实现 WebContentTool

```python
# src/ai_agent/tools/web/web_content.py

"""网页内容提取工具（Jina API）"""

import os
import asyncio
from typing import Any, Optional, List
import httpx
import tiktoken

from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.llm.config import LLMSettings


class WebContentTool(BaseAgentTool):
    """使用 Jina API 提取网页内容并进行智能问答"""

    name = "web_content"
    description = "提取网页内容并回答问题。支持 http/https URL。返回基于网页内容的答案。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要提取内容的网页 URL（仅支持 http/https）",
            },
            "query": {
                "type": "string",
                "description": "针对网页内容的问题或指令",
            },
        },
        "required": ["url", "query"],
        "additionalProperties": False,
    }

    # 内容分块的 token 限制
    CHUNK_TOKEN_LIMIT = 95000

    def __init__(self):
        self._settings: Optional[LLMSettings] = None

    @property
    def settings(self) -> LLMSettings:
        """懒加载配置"""
        if self._settings is None:
            self._settings = LLMSettings()
        return self._settings

    async def _fetch_jina(self, url: str, max_retry: int = 3) -> Optional[str]:
        """通过 Jina API 获取网页内容"""
        jina_api_key = self.settings.jina_api_key
        if not jina_api_key:
            raise ValueError("JINA_API_KEY 未配置")

        headers = {"Authorization": f"Bearer {jina_api_key}"}
        jina_url = f"https://r.jina.ai/{url}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(max_retry):
                try:
                    response = await client.get(jina_url, headers=headers)
                    if response.status_code == 200:
                        return response.text
                    else:
                        print(f"Jina API error (attempt {attempt + 1}): {response.text[:200]}")
                except httpx.RequestError as e:
                    print(f"Jina request error (attempt {attempt + 1}): {e}")

        return None

    async def _call_llm(self, query: str) -> str:
        """调用 LLM 处理查询"""
        from openai import AsyncOpenAI

        api_key = self.settings.openai_api_key
        base_url = self.settings.openai_base_url
        model = self.settings.openai_model

        if not api_key:
            raise ValueError("OPENAI_API_KEY 未配置")

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        messages = [{"role": "user", "content": query}]

        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.settings.temperature,
        )

        content = completion.choices[0].message.content if completion and completion.choices else None
        if not content:
            raise RuntimeError("LLM 返回空响应")

        return content.strip()

    async def run(self, url: str, query: str) -> ToolResult:
        """执行网页内容提取和问答"""
        import time
        start_time = time.time()

        try:
            # 1. 获取网页内容
            source_text = await self._fetch_jina(url)
            if not source_text or not source_text.strip():
                return ToolResult(
                    success=False,
                    data=None,
                    error="获取网页内容失败或内容为空",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            # 2. 构建查询 prompt
            def build_prompt(content: str, q: str) -> str:
                return (
                    f"请阅读以下网页内容并回答问题：\n"
                    f"--- 网页内容开始 ---\n{content}\n--- 网页内容结束 ---\n\n"
                    f"如果没有相关信息，请明确说明。现在请回答问题：{q}"
                )

            # 3. 检查是否需要分块
            encoding = tiktoken.get_encoding("cl100k_base")
            tokens = encoding.encode(source_text)
            token_count = len(tokens)

            if token_count > self.CHUNK_TOKEN_LIMIT:
                # 分块处理
                output_parts: List[str] = []
                num_chunks = max(2, token_count // self.CHUNK_TOKEN_LIMIT + 1)
                chunk_size = token_count // num_chunks

                tasks: List[asyncio.Task[str]] = []
                for i in range(num_chunks):
                    start_idx = i * chunk_size
                    end_idx = min(start_idx + chunk_size + 1024, token_count)
                    chunk_text = encoding.decode(tokens[start_idx:end_idx])
                    chunk_prompt = build_prompt(chunk_text, query)
                    tasks.append(asyncio.create_task(self._call_llm(chunk_prompt)))

                results = await asyncio.gather(*tasks, return_exceptions=True)

                output = f"内容较长，分 {num_chunks} 部分处理。请综合以下结果：\n\n"
                for idx, result in enumerate(results):
                    if isinstance(result, Exception):
                        return ToolResult(
                            success=False,
                            data=None,
                            error=f"第 {idx + 1} 部分处理失败: {result}",
                            metrics={"elapsed_time": time.time() - start_time},
                        )
                    output += f"--- 第 {idx + 1} 部分答案 ---\n{result}\n\n"
            else:
                # 直接处理
                prompt = build_prompt(source_text, query)
                output = await self._call_llm(prompt)

            # 4. 返回结果
            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "answer": output,
                    "source_preview": source_text[:2000] if source_text else "",
                },
                error=None,
                metrics={
                    "elapsed_time": time.time() - start_time,
                    "token_count": token_count,
                    "chunked": token_count > self.CHUNK_TOKEN_LIMIT,
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
                error=f"处理失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
```

### Step 5: 添加 tiktoken 依赖

```bash
uv add tiktoken
```

### Step 6: 运行测试确认通过

```bash
pytest tests/unit/tools/web/test_web_content.py -v
```

Expected: PASS

### Step 7: 提交 WebContentTool

```bash
git add src/ai_agent/tools/web/web_content.py src/ai_agent/tools/web/__init__.py tests/unit/tools/web/
git commit -m "feat(tools): add WebContentTool with Jina API support"
```

---

## Task 4: 实现 GoogleSearchTool（Serper API）

**Files:**
- Create: `src/ai_agent/tools/web/google_search.py`
- Create: `tests/unit/tools/web/test_google_search.py`

### Step 1: 编写 GoogleSearchTool 单元测试

```python
# tests/unit/tools/web/test_google_search.py

"""GoogleSearchTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch
from ai_agent.tools.web.google_search import GoogleSearchTool


class TestGoogleSearchTool:
    """GoogleSearchTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = GoogleSearchTool()
        assert tool.name == "google_search"
        assert "搜索" in tool.description or "Google" in tool.description
        assert "query" in tool.parameters.get("properties", {})

    @pytest.mark.asyncio
    async def test_run_success_with_answer_box(self):
        """测试搜索成功（有 answerBox）"""
        tool = GoogleSearchTool()

        mock_response = {
            "answerBox": {
                "answer": "Python 是一种编程语言"
            },
            "organic": []
        }

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response

            result = await tool.run(query="Python 是什么")

            assert result.success is True
            assert len(result.data) == 1
            assert "编程语言" in result.data[0]["content"]

    @pytest.mark.asyncio
    async def test_run_success_with_organic(self):
        """测试搜索成功（使用 organic 结果）"""
        tool = GoogleSearchTool()

        mock_response = {
            "organic": [
                {"snippet": "Python 官方网站", "link": "https://python.org"},
                {"snippet": "Python 教程", "link": "https://tutorial.python.org"},
            ]
        }

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response

            result = await tool.run(query="Python", k=2)

            assert result.success is True
            assert len(result.data) == 2
            assert result.data[0]["source"] == "https://python.org"

    @pytest.mark.asyncio
    async def test_run_no_results(self):
        """测试无搜索结果"""
        tool = GoogleSearchTool()

        mock_response = {}

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response

            result = await tool.run(query="不存在的查询xyz123")

            assert result.success is True
            assert "No good" in result.data[0]["content"]

    @pytest.mark.asyncio
    async def test_run_api_error(self):
        """测试 API 错误"""
        tool = GoogleSearchTool()

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("API Error")

            result = await tool.run(query="test")

            assert result.success is False
            assert "API Error" in result.error

    @pytest.mark.asyncio
    async def test_run_with_custom_params(self):
        """测试自定义参数"""
        tool = GoogleSearchTool()

        mock_response = {"organic": [{"snippet": "test", "link": "url"}]}

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response

            await tool.run(query="test", k=10, gl="cn", hl="zh")

            # 验证调用参数
            call_args = mock_search.call_args
            assert call_args[1]["k"] == 10
            assert call_args[1]["gl"] == "cn"
            assert call_args[1]["hl"] == "zh"
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/tools/web/test_google_search.py -v
```

Expected: FAIL - ModuleNotFoundError

### Step 3: 实现 GoogleSearchTool

```python
# src/ai_agent/tools/web/google_search.py

"""Google 搜索工具（Serper API）"""

import json
from typing import Any, Optional, List
import httpx

from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.llm.config import LLMSettings


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

    @property
    def settings(self) -> LLMSettings:
        """懒加载配置"""
        if self._settings is None:
            self._settings = LLMSettings()
        return self._settings

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

        async with httpx.AsyncClient(timeout=30.0) as client:
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
```

### Step 4: 更新 web/__init__.py

```python
# src/ai_agent/tools/web/__init__.py

"""Web 相关工具"""

from .web_content import WebContentTool
from .google_search import GoogleSearchTool

__all__ = ["WebContentTool", "GoogleSearchTool"]
```

### Step 5: 运行测试确认通过

```bash
pytest tests/unit/tools/web/test_google_search.py -v
```

Expected: PASS

### Step 6: 提交 GoogleSearchTool

```bash
git add src/ai_agent/tools/web/google_search.py src/ai_agent/tools/web/__init__.py tests/unit/tools/web/test_google_search.py
git commit -m "feat(tools): add GoogleSearchTool with Serper API support"
```

---

## Task 5: 创建 Media 工具目录结构

**Files:**
- Create: `src/ai_agent/tools/media/__init__.py`

### Step 1: 创建 media 目录初始化文件

```python
# src/ai_agent/tools/media/__init__.py

"""多媒体相关工具"""

from .image_analysis import ImageAnalysisTool
from .audio_parse import AudioParseTool

__all__ = ["ImageAnalysisTool", "AudioParseTool"]
```

### Step 2: 提交目录结构

```bash
git add src/ai_agent/tools/media/__init__.py
git commit -m "feat(tools): add media tools directory structure"
```

---

## Task 6: 实现 ImageAnalysisTool

**Files:**
- Create: `src/ai_agent/tools/media/image_analysis.py`
- Create: `tests/unit/tools/media/__init__.py`
- Create: `tests/unit/tools/media/test_image_analysis.py`

### Step 1: 创建单元测试目录

```python
# tests/unit/tools/media/__init__.py
```

### Step 2: 编写 ImageAnalysisTool 单元测试

```python
# tests/unit/tools/media/test_image_analysis.py

"""ImageAnalysisTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ai_agent.tools.media.image_analysis import ImageAnalysisTool


class TestImageAnalysisTool:
    """ImageAnalysisTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = ImageAnalysisTool()
        assert tool.name == "image_analysis"
        assert "图像" in tool.description or "图片" in tool.description or "image" in tool.description.lower()
        assert "image_path" in tool.parameters.get("properties", {})
        assert "query" in tool.parameters.get("properties", {})

    @pytest.mark.asyncio
    async def test_run_success_with_local_file(self, tmp_path):
        """测试本地图片分析成功"""
        tool = ImageAnalysisTool()

        # 创建临时图片文件
        image_file = tmp_path / "test.png"
        image_file.write_bytes(b"fake image data")

        with patch('ai_agent.tools.media.image_analysis.AsyncOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "这是一张测试图片"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await tool.run(image_path=str(image_file), query="描述这张图片")

            assert result.success is True
            assert result.data == "这是一张测试图片"

    @pytest.mark.asyncio
    async def test_run_success_with_url(self):
        """测试 URL 图片分析成功"""
        tool = ImageAnalysisTool()

        with patch('ai_agent.tools.media.image_analysis.AsyncOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "URL 图片描述"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await tool.run(
                image_path="https://example.com/image.jpg",
                query="描述这张图片"
            )

            assert result.success is True
            assert result.data == "URL 图片描述"

    @pytest.mark.asyncio
    async def test_run_missing_params(self):
        """测试缺少参数"""
        tool = ImageAnalysisTool()

        result = await tool.run(image_path="test.jpg", query="")
        assert result.success is False
        assert "query" in result.error.lower() or "required" in result.error.lower()

        result = await tool.run(image_path="", query="描述")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_run_file_not_found(self):
        """测试文件不存在"""
        tool = ImageAnalysisTool()

        result = await tool.run(image_path="/nonexistent/image.jpg", query="描述")

        assert result.success is False
        assert "not found" in result.error.lower() or "不存在" in result.error or "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_api_error(self):
        """测试 API 错误"""
        tool = ImageAnalysisTool()

        with patch('ai_agent.tools.media.image_analysis.AsyncOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            # 使用 URL 避免文件读取
            result = await tool.run(
                image_path="https://example.com/image.jpg",
                query="描述"
            )

            assert result.success is False
            assert "API Error" in result.error
```

### Step 3: 运行测试确认失败

```bash
pytest tests/unit/tools/media/test_image_analysis.py -v
```

Expected: FAIL - ModuleNotFoundError

### Step 4: 实现 ImageAnalysisTool

```python
# src/ai_agent/tools/media/image_analysis.py

"""图像分析工具"""

import base64
from pathlib import Path
from typing import Any, Optional

from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.llm.config import LLMSettings


class ImageAnalysisTool(BaseAgentTool):
    """使用多模态模型分析图像内容"""

    name = "image_analysis"
    description = "分析图像内容，回答关于图像的问题。支持本地图片路径和 URL。"
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "图像路径（本地文件或 URL）",
            },
            "query": {
                "type": "string",
                "description": "关于图像的问题或分析指令",
            },
        },
        "required": ["image_path", "query"],
        "additionalProperties": False,
    }

    def __init__(self):
        self._settings: Optional[LLMSettings] = None

    @property
    def settings(self) -> LLMSettings:
        """懒加载配置"""
        if self._settings is None:
            self._settings = LLMSettings()
        return self._settings

    def _encode_image(self, image_path: str) -> str:
        """将本地图片编码为 base64"""
        path = Path(image_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        data = path.read_bytes()
        return base64.b64encode(data).decode("utf-8")

    def _get_image_url(self, image_path: str) -> str:
        """获取图片 URL（本地文件转 base64 data URL）"""
        if image_path.startswith(("http://", "https://")):
            return image_path
        encoded = self._encode_image(image_path)
        # 根据文件扩展名确定 MIME 类型
        ext = Path(image_path).suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/png")
        return f"data:{mime_type};base64,{encoded}"

    async def run(self, image_path: str, query: str) -> ToolResult:
        """执行图像分析"""
        import time
        start_time = time.time()

        # 参数校验
        if not image_path or not query:
            return ToolResult(
                success=False,
                data=None,
                error="image_path 和 query 都是必需参数",
                metrics={"elapsed_time": time.time() - start_time},
            )

        try:
            from openai import AsyncOpenAI
        except ImportError:
            return ToolResult(
                success=False,
                data=None,
                error="openai 包未安装",
                metrics={"elapsed_time": time.time() - start_time},
            )

        api_key = self.settings.openai_api_key
        base_url = self.settings.openai_base_url
        model = self.settings.openai_model

        if not api_key:
            return ToolResult(
                success=False,
                data=None,
                error="OPENAI_API_KEY 未配置",
                metrics={"elapsed_time": time.time() - start_time},
            )

        try:
            image_url = self._get_image_url(image_path)
        except FileNotFoundError as e:
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
                error=f"图片处理失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )

        try:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": query},
                    ],
                }
            ]

            completion = await client.chat.completions.create(
                model=model,
                messages=messages,
            )

            content = None
            if completion and completion.choices:
                content = completion.choices[0].message.content

            if not content:
                return ToolResult(
                    success=False,
                    data=None,
                    error="模型返回空响应",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            return ToolResult(
                success=True,
                data=content.strip(),
                error=None,
                metrics={"elapsed_time": time.time() - start_time},
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"图像分析失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
```

### Step 5: 运行测试确认通过

```bash
pytest tests/unit/tools/media/test_image_analysis.py -v
```

Expected: PASS

### Step 6: 提交 ImageAnalysisTool

```bash
git add src/ai_agent/tools/media/image_analysis.py src/ai_agent/tools/media/__init__.py tests/unit/tools/media/
git commit -m "feat(tools): add ImageAnalysisTool with multi-modal support"
```

---

## Task 7: 实现 AudioParseTool

**Files:**
- Create: `src/ai_agent/tools/media/audio_parse.py`
- Create: `tests/unit/tools/media/test_audio_parse.py`

### Step 1: 编写 AudioParseTool 单元测试

```python
# tests/unit/tools/media/test_audio_parse.py

"""AudioParseTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ai_agent.tools.media.audio_parse import AudioParseTool


class TestAudioParseTool:
    """AudioParseTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = AudioParseTool()
        assert tool.name == "audio_parse"
        assert "音频" in tool.description or "audio" in tool.description.lower()
        assert "audio_path" in tool.parameters.get("properties", {})
        assert "query" in tool.parameters.get("properties", {})

    @pytest.mark.asyncio
    async def test_run_success(self, tmp_path):
        """测试音频解析成功"""
        tool = AudioParseTool()

        # 创建临时音频文件
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        with patch('ai_agent.tools.media.audio_parse.AsyncOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "这是转录的文本内容"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await tool.run(audio_path=str(audio_file), query="转录这段音频")

            assert result.success is True
            assert result.data == "这是转录的文本内容"

    @pytest.mark.asyncio
    async def test_run_missing_params(self):
        """测试缺少参数"""
        tool = AudioParseTool()

        result = await tool.run(audio_path="test.mp3", query="")
        assert result.success is False

        result = await tool.run(audio_path="", query="转录")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_run_file_not_found(self):
        """测试文件不存在"""
        tool = AudioParseTool()

        result = await tool.run(audio_path="/nonexistent/audio.mp3", query="转录")

        assert result.success is False
        assert "not found" in result.error.lower() or "不存在" in result.error or "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_run_api_error(self, tmp_path):
        """测试 API 错误"""
        tool = AudioParseTool()

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        with patch('ai_agent.tools.media.audio_parse.AsyncOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            result = await tool.run(audio_path=str(audio_file), query="转录")

            assert result.success is False
            assert "API Error" in result.error

    @pytest.mark.asyncio
    async def test_run_different_formats(self, tmp_path):
        """测试不同音频格式"""
        tool = AudioParseTool()

        for ext in ["mp3", "wav", "m4a"]:
            audio_file = tmp_path / f"test.{ext}"
            audio_file.write_bytes(b"fake audio data")

            with patch('ai_agent.tools.media.audio_parse.AsyncOpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = f"转录结果 {ext}"
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

                result = await tool.run(audio_path=str(audio_file), query="转录")

                assert result.success is True
                assert ext in result.data
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/tools/media/test_audio_parse.py -v
```

Expected: FAIL - ModuleNotFoundError

### Step 3: 实现 AudioParseTool

```python
# src/ai_agent/tools/media/audio_parse.py

"""音频解析工具"""

import base64
from pathlib import Path
from typing import Any, Optional

from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.llm.config import LLMSettings


class AudioParseTool(BaseAgentTool):
    """使用多模态模型解析音频内容"""

    name = "audio_parse"
    description = "转录音频内容或回答关于音频的问题。支持 mp3、wav、m4a 等格式。"
    parameters = {
        "type": "object",
        "properties": {
            "audio_path": {
                "type": "string",
                "description": "音频文件路径（仅支持本地文件）",
            },
            "query": {
                "type": "string",
                "description": "关于音频的问题或转录指令",
            },
        },
        "required": ["audio_path", "query"],
        "additionalProperties": False,
    }

    # 支持的音频格式
    SUPPORTED_FORMATS = {"mp3", "wav", "m4a", "ogg", "flac", "aac"}

    def __init__(self):
        self._settings: Optional[LLMSettings] = None

    @property
    def settings(self) -> LLMSettings:
        """懒加载配置"""
        if self._settings is None:
            self._settings = LLMSettings()
        return self._settings

    def _validate_audio_file(self, audio_path: str) -> Path:
        """验证音频文件"""
        path = Path(audio_path).expanduser()

        if not path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        ext = path.suffix.lower().lstrip(".")
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"不支持的音频格式: {ext}。支持: {', '.join(self.SUPPORTED_FORMATS)}")

        return path

    async def run(self, audio_path: str, query: str) -> ToolResult:
        """执行音频解析"""
        import time
        start_time = time.time()

        # 参数校验
        if not audio_path or not query:
            return ToolResult(
                success=False,
                data=None,
                error="audio_path 和 query 都是必需参数",
                metrics={"elapsed_time": time.time() - start_time},
            )

        try:
            from openai import AsyncOpenAI
        except ImportError:
            return ToolResult(
                success=False,
                data=None,
                error="openai 包未安装",
                metrics={"elapsed_time": time.time() - start_time},
            )

        api_key = self.settings.openai_api_key
        base_url = self.settings.openai_base_url
        model = self.settings.openai_model

        if not api_key:
            return ToolResult(
                success=False,
                data=None,
                error="OPENAI_API_KEY 未配置",
                metrics={"elapsed_time": time.time() - start_time},
            )

        # 验证并读取音频文件
        try:
            audio_file = self._validate_audio_file(audio_path)
            audio_data = audio_file.read_bytes()
            encoded_audio = base64.b64encode(audio_data).decode("utf-8")
            audio_format = audio_file.suffix.lower().lstrip(".")
        except FileNotFoundError as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                metrics={"elapsed_time": time.time() - start_time},
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
                error=f"音频文件读取失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )

        try:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)

            # 使用 input_audio 格式（OpenAI API 标准）
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": encoded_audio,
                                "format": audio_format,
                            },
                        },
                    ],
                }
            ]

            completion = await client.chat.completions.create(
                model=model,
                messages=messages,
            )

            content = None
            if completion and completion.choices:
                content = completion.choices[0].message.content

            if not content:
                return ToolResult(
                    success=False,
                    data=None,
                    error="模型返回空响应",
                    metrics={"elapsed_time": time.time() - start_time},
                )

            return ToolResult(
                success=True,
                data=content.strip(),
                error=None,
                metrics={
                    "elapsed_time": time.time() - start_time,
                    "audio_format": audio_format,
                    "audio_size": len(audio_data),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"音频解析失败: {str(e)}",
                metrics={"elapsed_time": time.time() - start_time},
            )
```

### Step 4: 更新 media/__init__.py

```python
# src/ai_agent/tools/media/__init__.py

"""多媒体相关工具"""

from .image_analysis import ImageAnalysisTool
from .audio_parse import AudioParseTool

__all__ = ["ImageAnalysisTool", "AudioParseTool"]
```

### Step 5: 运行测试确认通过

```bash
pytest tests/unit/tools/media/test_audio_parse.py -v
```

Expected: PASS

### Step 6: 提交 AudioParseTool

```bash
git add src/ai_agent/tools/media/audio_parse.py src/ai_agent/tools/media/__init__.py tests/unit/tools/media/test_audio_parse.py
git commit -m "feat(tools): add AudioParseTool with multi-modal support"
```

---

## Task 8: 更新工具注册和导出

**Files:**
- Modify: `src/ai_agent/tools/__init__.py`

### Step 1: 更新工具模块导出

```python
# src/ai_agent/tools/__init__.py

"""工具模块"""

from .base import BaseAgentTool, ToolResult
from .registry import ToolRegistry
from .web import WebContentTool, GoogleSearchTool
from .media import ImageAnalysisTool, AudioParseTool

__all__ = [
    "BaseAgentTool",
    "ToolResult",
    "ToolRegistry",
    "WebContentTool",
    "GoogleSearchTool",
    "ImageAnalysisTool",
    "AudioParseTool",
]
```

### Step 2: 提交模块导出更新

```bash
git add src/ai_agent/tools/__init__.py
git commit -m "feat(tools): export all tools from main module"
```

---

## Task 9: 编写集成测试（真实 API）

**Files:**
- Create: `tests/integration/tools/__init__.py`
- Create: `tests/integration/tools/test_web_tools.py`
- Create: `tests/integration/tools/test_media_tools.py`

### Step 1: 创建集成测试目录

```python
# tests/integration/tools/__init__.py
```

### Step 2: 编写 Web 工具集成测试

```python
# tests/integration/tools/test_web_tools.py

"""Web 工具集成测试（真实 API）"""

import pytest
from ai_agent.tools.web import WebContentTool, GoogleSearchTool


# 使用自定义标记，可通过 -m integration 运行
pytestmark = pytest.mark.integration


class TestWebContentToolIntegration:
    """WebContentTool 集成测试"""

    @pytest.fixture
    def tool(self):
        return WebContentTool()

    @pytest.mark.asyncio
    async def test_extract_python_org(self, tool):
        """测试提取 Python 官网内容"""
        result = await tool.run(
            url="https://www.python.org",
            query="What is Python? Answer in one sentence."
        )

        assert result.success is True
        assert result.data is not None
        assert "answer" in result.data
        assert result.data["url"] == "https://www.python.org"
        assert len(result.data["answer"]) > 10
        print(f"\n答案: {result.data['answer'][:200]}...")

    @pytest.mark.asyncio
    async def test_extract_github_readme(self, tool):
        """测试提取 GitHub README"""
        result = await tool.run(
            url="https://github.com/langchain-ai/langchain",
            query="What is LangChain? Brief summary."
        )

        assert result.success is True
        assert "LangChain" in result.data["answer"] or "framework" in result.data["answer"].lower()
        print(f"\n答案: {result.data['answer'][:200]}...")


class TestGoogleSearchToolIntegration:
    """GoogleSearchTool 集成测试"""

    @pytest.fixture
    def tool(self):
        return GoogleSearchTool()

    @pytest.mark.asyncio
    async def test_search_python(self, tool):
        """测试搜索 Python"""
        result = await tool.run(query="Python programming language", k=3)

        assert result.success is True
        assert result.data is not None
        assert len(result.data) > 0
        assert len(result.data) <= 3

        print(f"\n搜索结果:")
        for i, item in enumerate(result.data[:3], 1):
            print(f"  {i}. {item['content'][:100]}...")
            print(f"     来源: {item['source']}")

    @pytest.mark.asyncio
    async def test_search_with_chinese(self, tool):
        """测试中文搜索"""
        result = await tool.run(query="人工智能", k=5, gl="cn", hl="zh")

        assert result.success is True
        assert len(result.data) > 0
        print(f"\n中文搜索结果数量: {len(result.data)}")

    @pytest.mark.asyncio
    async def test_search_specific_question(self, tool):
        """测试具体问题搜索"""
        result = await tool.run(query="What is the capital of France?", k=1)

        assert result.success is True
        # 可能直接返回 answerBox
        print(f"\n答案: {result.data[0]['content']}")
```

### Step 3: 编写 Media 工具集成测试

```python
# tests/integration/tools/test_media_tools.py

"""Media 工具集成测试（真实 API）"""

import pytest
from ai_agent.tools.media import ImageAnalysisTool, AudioParseTool


pytestmark = pytest.mark.integration


class TestImageAnalysisToolIntegration:
    """ImageAnalysisTool 集成测试"""

    @pytest.fixture
    def tool(self):
        return ImageAnalysisTool()

    @pytest.mark.asyncio
    async def test_analyze_url_image(self, tool):
        """测试分析 URL 图片"""
        # 使用公开的测试图片
        result = await tool.run(
            image_path="https://www.python.org/static/img/python-logo.png",
            query="Describe this image. What do you see?"
        )

        assert result.success is True
        assert result.data is not None
        assert len(result.data) > 10
        print(f"\n图像描述: {result.data[:300]}...")

    @pytest.mark.asyncio
    async def test_analyze_photo(self, tool):
        """测试分析照片"""
        # 使用公开的测试照片
        result = await tool.run(
            image_path="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/800px-Python-logo-notext.svg.png",
            query="What colors are used in this logo?"
        )

        assert result.success is True
        print(f"\n颜色描述: {result.data}")


class TestAudioParseToolIntegration:
    """AudioParseTool 集成测试"""

    @pytest.fixture
    def tool(self):
        return AudioParseTool()

    @pytest.fixture
    def sample_audio(self, tmp_path):
        """创建测试音频文件（需要真实音频才能测试）"""
        # 注意：这里需要一个真实的音频文件
        # 实际测试时，可以下载一个小的测试音频
        audio_file = tmp_path / "test.mp3"
        # 这里只是占位，实际需要真实音频
        return str(audio_file)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要真实音频文件")
    async def test_transcribe_audio(self, tool, sample_audio):
        """测试音频转录"""
        result = await tool.run(
            audio_path=sample_audio,
            query="Transcribe this audio"
        )

        assert result.success is True
        print(f"\n转录结果: {result.data}")
```

### Step 4: 运行集成测试

```bash
# 运行集成测试（需要真实 API Key）
pytest tests/integration/tools/ -v -m integration
```

### Step 5: 提交集成测试

```bash
git add tests/integration/tools/
git commit -m "test(tools): add integration tests with real API calls"
```

---

## Task 10: 更新 conftest.py

**Files:**
- Modify: `tests/conftest.py`

### Step 1: 添加测试配置

```python
# tests/conftest.py

import pytest
import asyncio


def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require real API keys)"
    )


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

### Step 2: 提交配置更新

```bash
git add tests/conftest.py
git commit -m "test: add integration test marker configuration"
```

---

## Task 11: 最终验证

### Step 1: 运行所有单元测试

```bash
pytest tests/unit/tools/ -v
```

Expected: All PASS

### Step 2: 运行集成测试

```bash
pytest tests/integration/tools/ -v -m integration
```

Expected: All PASS (需要真实 API Key)

### Step 3: 验证工具导入

```bash
python -c "from ai_agent.tools import WebContentTool, GoogleSearchTool, ImageAnalysisTool, AudioParseTool; print('All tools imported successfully')"
```

### Step 4: 最终提交

```bash
git add -A
git status
git commit -m "feat(tools): complete multi-modal tools implementation with tests"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | 扩展工具基类 | `tools/base.py`, `llm/config.py` |
| 2 | 创建 web 目录 | `tools/web/__init__.py` |
| 3 | WebContentTool | `tools/web/web_content.py` + tests |
| 4 | GoogleSearchTool | `tools/web/google_search.py` + tests |
| 5 | 创建 media 目录 | `tools/media/__init__.py` |
| 6 | ImageAnalysisTool | `tools/media/image_analysis.py` + tests |
| 7 | AudioParseTool | `tools/media/audio_parse.py` + tests |
| 8 | 更新模块导出 | `tools/__init__.py` |
| 9 | 集成测试 | `tests/integration/tools/` |
| 10 | 测试配置 | `tests/conftest.py` |
| 11 | 最终验证 | - |
