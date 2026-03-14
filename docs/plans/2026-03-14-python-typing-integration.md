# Python Typing Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 全项目集成 Pydantic 类型系统，实现严格类型注解（必须有类型，允许 Any），添加 mypy 静态检查。

**Architecture:** 创建 `types/` 核心类型层，重构 `BaseAgentTool` 为泛型基类，逐模块迁移，保持向后兼容。

**Tech Stack:** Python 3.11, Pydantic v2, mypy, pytest

---

## Phase 1: 基础设施搭建

### Task 1: 创建核心类型目录结构

**Files:**
- Create: `src/ai_agent/types/__init__.py`
- Create: `src/ai_agent/types/common.py`

**Step 1: 创建 types 目录和 __init__.py**

```python
# src/ai_agent/types/__init__.py
"""核心类型定义模块"""

from .common import JSON, AnyDict, JSONDict

__all__ = ["JSON", "AnyDict", "JSONDict"]
```

**Step 2: 创建 common.py 定义通用类型别名**

```python
# src/ai_agent/types/common.py
"""通用类型别名定义

这些类型别名用于简化类型注解，提高代码可读性。
"""

from typing import Any, TypeAlias

# 基础 JSON 类型
JSON: TypeAlias = str | int | float | bool | None | dict[str, "JSON"] | list["JSON"]

# 通用字典类型
AnyDict: TypeAlias = dict[str, Any]

# JSON 兼容字典
JSONDict: TypeAlias = dict[str, JSON]
```

**Step 3: 验证导入正常**

Run: `python -c "from ai_agent.types import JSON, AnyDict, JSONDict; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/ai_agent/types/
git commit -m "feat(types): add core type aliases module"
```

---

### Task 2: 添加工具相关类型定义

**Files:**
- Create: `src/ai_agent/types/tools.py`
- Modify: `src/ai_agent/types/__init__.py`

**Step 1: 创建 tools.py 定义工具类型**

```python
# src/ai_agent/types/tools.py
"""工具相关类型定义"""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

from .common import AnyDict

# 泛型类型变量
P = TypeVar("P", bound=BaseModel)  # 参数类型
R = TypeVar("R")  # 返回类型


class ToolResult(BaseModel, Generic[R]):
    """泛型工具执行结果

    使用泛型支持不同工具指定返回类型。

    Example:
        class SearchParams(BaseModel):
            query: str

        class SearchTool(BaseAgentTool[SearchParams, list[str]]):
            async def run(self, params: SearchParams) -> ToolResult[list[str]]:
                ...
    """

    success: bool = Field(description="执行是否成功")
    data: R = Field(description="返回数据")
    error: str | None = Field(default=None, description="错误信息")
    metrics: AnyDict = Field(default_factory=dict, description="执行指标")


# 常用返回类型别名
ToolDataStr = ToolResult[str]
ToolDataDict = ToolResult[AnyDict]
ToolDataList = ToolResult[list[Any]]
```

**Step 2: 更新 __init__.py 导出**

```python
# src/ai_agent/types/__init__.py
"""核心类型定义模块"""

from .common import JSON, AnyDict, JSONDict
from .tools import ToolResult, P, R

__all__ = [
    "JSON",
    "AnyDict",
    "JSONDict",
    "ToolResult",
    "P",
    "R",
]
```

**Step 3: 验证导入**

Run: `python -c "from ai_agent.types import ToolResult, P, R; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/ai_agent/types/
git commit -m "feat(types): add ToolResult generic type"
```

---

### Task 3: 添加 Agent 相关类型定义

**Files:**
- Create: `src/ai_agent/types/agents.py`
- Modify: `src/ai_agent/types/__init__.py`

**Step 1: 创建 agents.py 定义 Agent 类型**

```python
# src/ai_agent/types/agents.py
"""Agent 相关类型定义"""

from enum import Enum
from typing import Any, AsyncGenerator
from pydantic import BaseModel, ConfigDict, Field

from .common import AnyDict


class AgentEventType(str, Enum):
    """Agent 事件类型"""

    THINK = "think"
    ACT = "act"
    OBSERVE = "observe"
    ERROR = "error"
    FINISH = "finish"


class AgentAction(BaseModel):
    """LLM 返回的结构化动作"""

    action: str = Field(description="工具名称或 'finish'")
    params: AnyDict = Field(default_factory=dict, description="工具参数")
    memory: str = Field(default="", description="本轮观察/思考")


class AgentEvent(BaseModel):
    """Agent 执行事件"""

    event: AgentEventType
    data: AnyDict
    step: int = Field(ge=0)
    timestamp: str | None = None

    model_config = ConfigDict(frozen=True)

    def to_sse(self) -> str:
        """转换为 SSE 格式字符串"""
        import json
        from datetime import datetime

        event_dict: AnyDict = {
            "event": self.event.value,
            "data": self.data,
            "step": self.step,
            "timestamp": self.timestamp or datetime.now().isoformat(),
        }
        return f"data: {json.dumps(event_dict, ensure_ascii=False)}\n\n"
```

**Step 2: 更新 __init__.py 导出**

```python
# src/ai_agent/types/__init__.py
"""核心类型定义模块"""

from .common import JSON, AnyDict, JSONDict
from .tools import ToolResult, P, R
from .agents import AgentEventType, AgentAction, AgentEvent

__all__ = [
    "JSON",
    "AnyDict",
    "JSONDict",
    "ToolResult",
    "P",
    "R",
    "AgentEventType",
    "AgentAction",
    "AgentEvent",
]
```

**Step 3: 验证导入**

Run: `python -c "from ai_agent.types import AgentEvent, AgentEventType; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/ai_agent/types/
git commit -m "feat(types): add AgentEvent and AgentAction types"
```

---

### Task 4: 配置 mypy

**Files:**
- Modify: `pyproject.toml`

**Step 1: 添加 mypy 配置到 pyproject.toml**

在 `pyproject.toml` 末尾添加：

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
disallow_untyped_calls = true
disallow_untyped_decorators = true
check_untyped_defs = true
strict_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
show_error_codes = true
pretty = true
exclude = ["tests/", "examples/", "scripts/"]

[[tool.mypy.overrides]]
module = [
    "langgraph.*",
    "langsmith.*",
    "langchain_core.*",
    "langchain_openai.*",
    "tiktoken.*",
    "pydantic_settings.*",
]
ignore_missing_imports = true
```

**Step 2: 安装 mypy（如未安装）**

Run: `pip install mypy`
Expected: mypy 安装成功

**Step 3: 验证 mypy 配置**

Run: `mypy src/ai_agent/types/ --no-error-summary 2>&1 | head -20`
Expected: 类型检查通过或显示新模块的类型错误

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add mypy configuration for strict type checking"
```

---

## Phase 2: Tools 模块重构

### Task 5: 重构 BaseAgentTool 为泛型基类

**Files:**
- Modify: `src/ai_agent/tools/base.py`
- Create: `tests/unit/tools/test_base_typed.py`

**Step 1: 写失败的测试**

```python
# tests/unit/tools/test_base_typed.py
"""测试泛型工具基类"""

import pytest
from pydantic import BaseModel, Field

from ai_agent.types import ToolResult


class TestParams(BaseModel):
    """测试参数"""
    query: str = Field(description="查询字符串")
    limit: int = Field(default=10, ge=1, le=100)


def test_tool_result_generic():
    """测试 ToolResult 泛型"""
    result: ToolResult[str] = ToolResult(
        success=True,
        data="test output",
    )
    assert result.success is True
    assert result.data == "test output"


def test_tool_result_with_dict():
    """测试 ToolResult 返回字典"""
    result: ToolResult[dict[str, str]] = ToolResult(
        success=True,
        data={"key": "value"},
    )
    assert result.data["key"] == "value"


def test_tool_result_with_error():
    """测试 ToolResult 包含错误"""
    result: ToolResult[str] = ToolResult(
        success=False,
        data="",
        error="Something went wrong",
    )
    assert result.success is False
    assert result.error == "Something went wrong"
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/unit/tools/test_base_typed.py -v`
Expected: 测试通过（ToolResult 已定义）

**Step 3: 重构 BaseAgentTool**

```python
# src/ai_agent/tools/base.py
"""工具基类模块"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from ai_agent.types import ToolResult, AnyDict

P = TypeVar("P", bound=BaseModel)
R = TypeVar("R")


class BaseAgentTool(ABC, Generic[P, R]):
    """工具基类，所有工具继承此类

    泛型参数:
        P: 参数 Pydantic 模型类型
        R: 返回数据类型

    Example:
        class SearchParams(BaseModel):
            query: str

        class SearchTool(BaseAgentTool[SearchParams, list[str]]):
            @property
            def name(self) -> str:
                return "search"

            @property
            def description(self) -> str:
                return "Search for items"

            @property
            def params_schema(self) -> type[SearchParams]:
                return SearchParams

            async def run(self, params: SearchParams) -> ToolResult[list[str]]:
                results = await self._search(params.query)
                return ToolResult(success=True, data=results)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述，供 LLM 理解用途"""
        ...

    @property
    @abstractmethod
    def params_schema(self) -> type[BaseModel]:
        """参数的 Pydantic 模型类"""
        ...

    @property
    def parameters(self) -> AnyDict:
        """自动生成 JSON Schema（向后兼容）

        从 params_schema 自动生成，无需手写。
        """
        schema: AnyDict = self.params_schema.model_json_schema()
        return schema

    @abstractmethod
    async def run(self, params: P) -> ToolResult[R]:
        """执行工具逻辑（异步）

        Args:
            params: 类型化的参数对象

        Returns:
            ToolResult 包含执行结果
        """
        ...

    def to_langchain_tool(self) -> StructuredTool:
        """转换为 LangChain StructuredTool 格式"""
        import asyncio

        args_schema: type[BaseModel] = self.params_schema

        async def async_wrapper(**kwargs: Any) -> str:
            """异步包装器"""
            # 将 kwargs 转换为 Pydantic 模型
            params: P = args_schema(**kwargs)  # type: ignore
            result: ToolResult[R] = await self.run(params)
            return result.data if result.success else f"Error: {result.error}"

        def sync_wrapper(**kwargs: Any) -> str:
            """同步包装器：处理异步调用"""
            coro = async_wrapper(**kwargs)
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    import threading

                    result_container: list[str] = []
                    exception_container: list[Exception] = []

                    def run_in_new_loop() -> None:
                        try:
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            result_container.append(new_loop.run_until_complete(coro))
                            new_loop.close()
                        except Exception as e:
                            exception_container.append(e)

                    thread = threading.Thread(target=run_in_new_loop)
                    thread.start()
                    thread.join(timeout=30)

                    if exception_container:
                        raise exception_container[0]
                    if result_container:
                        return result_container[0]
                    raise TimeoutError("Tool execution timeout")
                else:
                    return asyncio.run(coro)
            except RuntimeError:
                return asyncio.run(coro)

        return StructuredTool(
            name=self.name,
            description=self.description,
            func=sync_wrapper,
            coroutine=async_wrapper,
            args_schema=args_schema,
        )
```

**Step 4: 运行 mypy 检查**

Run: `mypy src/ai_agent/tools/base.py`
Expected: 无类型错误

**Step 5: 运行所有工具测试**

Run: `pytest tests/unit/tools/ -v`
Expected: 全部通过

**Step 6: Commit**

```bash
git add src/ai_agent/tools/base.py tests/unit/tools/test_base_typed.py
git commit -m "refactor(tools): convert BaseAgentTool to generic base class"
```

---

### Task 6: 迁移 GoogleSearchTool

**Files:**
- Modify: `src/ai_agent/tools/web/google_search.py`
- Create: `tests/unit/tools/web/test_google_search_typed.py`

**Step 1: 写失败的测试**

```python
# tests/unit/tools/web/test_google_search_typed.py
"""测试 GoogleSearchTool 类型化参数"""

import pytest
from pydantic import ValidationError

from ai_agent.tools.web.google_search import GoogleSearchParams


def test_params_schema_required_query():
    """测试 query 是必需字段"""
    with pytest.raises(ValidationError):
        GoogleSearchParams()  # 缺少 query


def test_params_schema_defaults():
    """测试默认值"""
    params = GoogleSearchParams(query="test")
    assert params.k == 5
    assert params.gl == "us"
    assert params.hl == "en"


def test_params_schema_validation():
    """测试参数验证"""
    params = GoogleSearchParams(query="test", k=10, gl="cn", hl="zh")
    assert params.k == 10
    assert params.gl == "cn"
    assert params.hl == "zh"
```

**Step 2: 重构 GoogleSearchTool**

```python
# src/ai_agent/tools/web/google_search.py
"""Google 搜索工具（通过 Serper API）"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types import ToolResult, AnyDict

logger = logging.getLogger(__name__)


class GoogleSearchParams(BaseModel):
    """Google 搜索参数"""

    query: str = Field(description="搜索关键词")
    k: int = Field(default=5, ge=1, le=20, description="返回结果数")
    gl: str = Field(default="us", min_length=2, max_length=2, description="地区代码")
    hl: str = Field(default="en", min_length=2, max_length=2, description="语言代码")


class SearchResult(BaseModel):
    """单条搜索结果"""

    title: str
    link: str
    snippet: str


class GoogleSearchTool(BaseAgentTool[GoogleSearchParams, list[SearchResult]]):
    """Google 搜索工具

    使用 Serper API 执行 Google 搜索并返回结构化结果。
    需要配置 SERPER_API_KEY 环境变量。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://google.serper.dev/search",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url

    @property
    def name(self) -> str:
        return "google_search"

    @property
    def description(self) -> str:
        return "Search Google and return relevant results. Use for finding current information."

    @property
    def params_schema(self) -> type[GoogleSearchParams]:
        return GoogleSearchParams

    async def run(self, params: GoogleSearchParams) -> ToolResult[list[SearchResult]]:
        """执行 Google 搜索

        Args:
            params: 搜索参数

        Returns:
            ToolResult 包含搜索结果列表
        """
        try:
            results: list[SearchResult] = await self._search(params)
            return ToolResult(success=True, data=results)
        except Exception as e:
            logger.error(f"Google search failed: {e}")
            return ToolResult(success=False, data=[], error=str(e))

    async def _search(self, params: GoogleSearchParams) -> list[SearchResult]:
        """执行搜索请求"""
        headers: AnyDict = {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
        }

        payload: AnyDict = {
            "q": params.query,
            "gl": params.gl,
            "hl": params.hl,
            "num": params.k,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._base_url,
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()

        data: AnyDict = response.json()
        return self._parse_results(data, params.k)

    def _parse_results(
        self, data: AnyDict, limit: int
    ) -> list[SearchResult]:
        """解析搜索结果"""
        results: list[SearchResult] = []
        organic: list[AnyDict] = data.get("organic", [])

        for item in organic[:limit]:
            results.append(SearchResult(
                title=item.get("title", ""),
                link=item.get("link", ""),
                snippet=item.get("snippet", ""),
            ))

        return results
```

**Step 3: 运行测试**

Run: `pytest tests/unit/tools/web/test_google_search_typed.py -v`
Expected: 全部通过

**Step 4: 运行 mypy 检查**

Run: `mypy src/ai_agent/tools/web/google_search.py`
Expected: 无类型错误

**Step 5: Commit**

```bash
git add src/ai_agent/tools/web/google_search.py tests/unit/tools/web/test_google_search_typed.py
git commit -m "refactor(tools): migrate GoogleSearchTool to typed parameters"
```

---

### Task 7: 迁移 WebContentTool

**Files:**
- Modify: `src/ai_agent/tools/web/web_content.py`

**Step 1: 重构 WebContentTool**

```python
# src/ai_agent/tools/web/web_content.py
"""网页内容提取工具"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ai_agent.tools.base import BaseAgentTool
from ai_agent.types import ToolResult, AnyDict

logger = logging.getLogger(__name__)


class WebContentParams(BaseModel):
    """网页内容提取参数"""

    url: str = Field(description="要提取内容的网页 URL")
    max_length: int = Field(default=5000, ge=100, le=50000, description="最大字符数")


class WebContentTool(BaseAgentTool[WebContentParams, str]):
    """网页内容提取工具

    使用 Jina AI Reader API 提取网页的纯文本内容。
    支持免费模式（无需 API Key）和付费模式。
    """

    def __init__(
        self,
        api_key: str = "",
        use_free_mode: bool = True,
    ) -> None:
        self._api_key = api_key
        self._use_free_mode = use_free_mode

    @property
    def name(self) -> str:
        return "web_content"

    @property
    def description(self) -> str:
        return "Extract text content from a web page URL."

    @property
    def params_schema(self) -> type[WebContentParams]:
        return WebContentParams

    async def run(self, params: WebContentParams) -> ToolResult[str]:
        """提取网页内容

        Args:
            params: 提取参数

        Returns:
            ToolResult 包含网页文本内容
        """
        try:
            content: str = await self._fetch_content(params)
            # 截断到最大长度
            if len(content) > params.max_length:
                content = content[:params.max_length] + "..."
            return ToolResult(success=True, data=content)
        except Exception as e:
            logger.error(f"Web content fetch failed: {e}")
            return ToolResult(success=False, data="", error=str(e))

    async def _fetch_content(self, params: WebContentParams) -> str:
        """获取网页内容"""
        if self._use_free_mode:
            # 免费模式：使用 Jina Reader
            reader_url = f"https://r.jina.ai/{params.url}"
            headers: AnyDict = {}
        else:
            # 付费模式
            reader_url = f"https://r.jina.ai/{params.url}"
            headers = {"Authorization": f"Bearer {self._api_key}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                reader_url,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

        return response.text
```

**Step 2: 运行 mypy 检查**

Run: `mypy src/ai_agent/tools/web/web_content.py`
Expected: 无类型错误

**Step 3: Commit**

```bash
git add src/ai_agent/tools/web/web_content.py
git commit -m "refactor(tools): migrate WebContentTool to typed parameters"
```

---

## Phase 3: Agents 模块重构

### Task 8: 更新 AgentState 类型

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py`

**Step 1: 更新导入和类型定义**

在文件顶部更新导入：

```python
# src/ai_agent/agents/react/graph.py
"""ReAct Agent 实现"""

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, START, END
from langsmith import traceable
from pydantic import BaseModel, ConfigDict, Field

from ..base import BaseAgent
from ...prompts import ReActPrompt
from ...types import AgentAction, AgentEvent, AgentEventType, AnyDict

logger = logging.getLogger(__name__)
```

**Step 2: 更新 AgentState 使用 AgentAction**

```python
# 在 ReActAction 定义处替换为：
# 使用 types 中的 AgentAction（或保留本地定义如果需要额外字段）

class ReActAction(BaseModel):
    """LLM 返回的结构化动作（本地扩展版本）"""

    action: str = Field(description="工具名称或 'finish'")
    params: AnyDict = Field(default_factory=dict, description="工具参数")
    memory: str = Field(default="", description="本轮观察/思考")


class AgentState(BaseModel):
    """ReAct Agent 状态"""

    question: str = Field(description="用户原始问题")
    current_obs: str = Field(default="", description="当前观察")
    steps_taken: int = Field(default=0, ge=0, description="已执行步数")
    actions_history: list[ReActAction] = Field(
        default_factory=list, description="动作历史"
    )
    final_answer: str | None = Field(default=None, description="最终答案")
    error: str | None = Field(default=None, description="错误信息")

    model_config = ConfigDict(arbitrary_types_allowed=True)
```

**Step 3: 添加返回类型注解到所有方法**

为 `_think_node`, `_act_node`, `_observe_node`, `_should_finish` 等方法添加完整的返回类型：

```python
def _should_finish(self, state: AgentState) -> str:
    """判断是否应该结束"""
    ...

async def _think_node(self, state: AgentState) -> AnyDict:
    """Think 节点：调用 LLM 决定下一步行动"""
    ...

async def _act_node(self, state: AgentState) -> AnyDict:
    """Act 节点：执行工具调用（带重试）"""
    ...

async def _observe_node(self, state: AgentState) -> AnyDict:
    """Observe 节点：处理观察结果，准备下一轮"""
    ...

def _build_action_space(self) -> str:
    """构建工具描述供 LLM 选择（包含参数 schema）"""
    ...

def _parse_action(self, response: str) -> ReActAction | None:
    """从 LLM 响应中解析 JSON 动作"""
    ...

def _find_tool(self, name: str) -> BaseTool | None:
    """根据名称查找工具"""
    ...

async def _execute_with_retry(
    self,
    tool: BaseTool,
    params: AnyDict,
) -> str:
    """执行工具调用，带重试机制"""
    ...

async def run(self, message: str) -> str:
    """运行 ReAct Agent"""
    ...

async def stream(self, message: str) -> AsyncGenerator[AgentEvent, None]:
    """流式执行 ReAct Agent，yield 每个事件"""
    ...

def get_graph(self) -> StateGraph:
    """获取编译后的图（用于调试/可视化）"""
    ...
```

**Step 4: 运行 mypy 检查**

Run: `mypy src/ai_agent/agents/react/graph.py`
Expected: 无类型错误

**Step 5: Commit**

```bash
git add src/ai_agent/agents/react/graph.py
git commit -m "refactor(agents): add complete type annotations to ReActAgent"
```

---

### Task 9: 重构 events.py 使用类型模块

**Files:**
- Modify: `src/ai_agent/agents/react/events.py`

**Step 1: 更新 events.py 使用类型模块**

```python
# src/ai_agent/agents/react/events.py
"""ReAct Agent 事件定义

注意：此模块保留以向后兼容。
新代码应使用 ai_agent.types 模块中的类型。
"""

# 从类型模块重新导出，保持兼容
from ai_agent.types import AgentEvent, AgentEventType  # noqa: F401

__all__ = ["AgentEvent", "AgentEventType"]
```

**Step 2: 验证兼容性**

Run: `python -c "from ai_agent.agents.react.events import AgentEvent, AgentEventType; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/ai_agent/agents/react/events.py
git commit -m "refactor(agents): re-export events from types module for compatibility"
```

---

## Phase 4: Memory & LLM 模块

### Task 10: 更新 Memory 模块类型

**Files:**
- Modify: `src/ai_agent/memory/base.py`

**Step 1: 更新导入和类型注解**

```python
# src/ai_agent/memory/base.py
"""Memory 模块 - 支持 ReAct 及其他 Agent 类型的记忆管理"""

import json
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from ai_agent.types import AnyDict


class MemoryRecord(BaseModel):
    """单条记忆记录

    用于存储 Agent 执行过程中的观察、动作和思考过程。
    """

    observation: AnyDict = Field(description="从环境获取的观察结果")
    action: AnyDict = Field(description="Agent 执行的动作及其参数")
    thinking: str | None = Field(default=None, description="推理过程")
    reward: float | None = Field(default=None, ge=0.0, le=1.0, description="奖励信号")
    raw_response: str | None = Field(default=None, description="LLM 原始响应")


class BaseMemory(ABC):
    """Memory 基类，定义统一接口"""

    @abstractmethod
    async def add(self, record: MemoryRecord) -> None:
        """添加记忆"""
        ...

    @abstractmethod
    def as_text(self) -> str:
        """转换为可注入 Prompt 的文本"""
        ...

    @abstractmethod
    def clear(self) -> None:
        """清空记忆"""
        ...


class CompressedMemory(BaseMemory):
    """
    带压缩功能的 Memory 实现
    - 保留最近 keep_recent 条完整记录
    - 早期记录通过 LLM 压缩为摘要
    """

    def __init__(
        self,
        llm: BaseChatModel,
        max_memory: int = 10,
        keep_recent: int = 3,
    ) -> None:
        if max_memory < 1:
            raise ValueError("max_memory must be at least 1")
        if keep_recent < 0:
            raise ValueError("keep_recent must be non-negative")
        if keep_recent > max_memory:
            raise ValueError("keep_recent cannot exceed max_memory")

        self._llm: BaseChatModel = llm
        self._max_memory: int = max_memory
        self._keep_recent: int = keep_recent
        self._records: list[MemoryRecord] = []
        self._summary: str | None = None

    async def add(self, record: MemoryRecord) -> None:
        """添加记忆并触发压缩检查"""
        self._records.append(record)
        await self._compress()

    def as_text(self) -> str:
        """生成可注入 Prompt 的文本"""
        if not self._summary and not self._records:
            return "None"

        parts: list[str] = []

        if self._records:
            parts.append("[Recent steps (latest first)]")
            for idx, r in enumerate(reversed(self._records), 1):
                parts.append(
                    f"{idx}. action={json.dumps(r.action, ensure_ascii=False)}, "
                    f"observation={json.dumps(r.observation, ensure_ascii=False)}, "
                    f"thinking={r.thinking}, reward={r.reward}"
                )

        if self._summary:
            parts.append("")
            parts.append("[Summary of earlier steps]")
            parts.append(self._summary)

        return "\n".join(parts)

    def clear(self) -> None:
        """清空所有记忆"""
        self._records.clear()
        self._summary = None

    async def _compress(self) -> None:
        """达到上限时压缩旧记录"""
        if len(self._records) < self._max_memory:
            return

        if self._keep_recent > 0:
            head: list[MemoryRecord] = self._records[:-self._keep_recent]
            tail: list[MemoryRecord] = self._records[-self._keep_recent:]
        else:
            head = self._records[:]
            tail = []

        if head:
            head_summary: str = await self._summarize_records(head)
            if self._summary:
                self._summary += "\n\n" + head_summary
            else:
                self._summary = head_summary

        self._records = tail

    async def _summarize_records(self, records: list[MemoryRecord]) -> str:
        """使用 LLM 压缩记录"""
        record_lines: list[str] = []
        for idx, r in enumerate(records, 1):
            record_lines.append(
                f"{idx}. action={json.dumps(r.action, ensure_ascii=False)}, "
                f"observation={json.dumps(r.observation, ensure_ascii=False)}, "
                f"thinking={json.dumps(r.thinking, ensure_ascii=False)}, "
                f"reward={r.reward}"
            )
        records_text: str = "\n".join(record_lines)

        summary_prompt: str = f"""You are the memory compression module of a language-model-based agent.

You are given several past interaction steps in chronological order (oldest first).
Each step includes:
- the agent's action,
- the environment observation,
- the reward signal,
- the agent's thinking.

Your task is to write a compact, **persistent memory** block that lets the agent
continue its work without seeing the full history.

Please:
- Focus on:
  1) stable facts and rules about the environment/world,
  2) useful strategies / plans / tools the agent tried,
  3) important mistakes or failure patterns to avoid later,
  4) partial progress and remaining goals / TODOs.
- Use at most 8–10 lines.
- Use a neutral, factual tone.
- Do NOT repeat low-level JSON details unless they are crucial.
- Do NOT include meta text like "here is the summary" or any explanation.
- Output ONLY the memory lines, one per line.

===== PAST STEPS =====
{records_text}
===== SUMMARY (start here) ====="""

        response = await self._llm.ainvoke([HumanMessage(summary_prompt)])
        content: str = response.content  # type: ignore[assignment]
        return content

    @property
    def record_count(self) -> int:
        """当前完整记录数"""
        return len(self._records)

    @property
    def has_summary(self) -> bool:
        """是否有压缩摘要"""
        return self._summary is not None
```

**Step 2: 运行 mypy 检查**

Run: `mypy src/ai_agent/memory/base.py`
Expected: 无类型错误

**Step 3: Commit**

```bash
git add src/ai_agent/memory/base.py
git commit -m "refactor(memory): add complete type annotations"
```

---

### Task 11: 更新 LLM 配置类型

**Files:**
- Modify: `src/ai_agent/llm/config.py`

**Step 1: 添加完整类型注解和验证器**

```python
# src/ai_agent/llm/config.py
"""LLM 配置模块"""

from pydantic import Field, field_validator
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
    openai_api_key: str = Field(..., repr=False, min_length=1)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-3.5-turbo"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Jina API 配置（网页内容提取）
    jina_api_key: str = Field(default="", repr=False)
    jina_use_free_mode: bool = False  # True: 免费模式（无需 Key），False: 付费模式（需要 Key）

    # Serper API 配置（Google 搜索）
    serper_api_key: str = Field(default="", repr=False)
    serper_base_url: str = "https://google.serper.dev/search"

    @field_validator("openai_base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """验证 URL 格式"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("openai_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """验证 API Key 非空"""
        if not v or not v.strip():
            raise ValueError("openai_api_key cannot be empty")
        return v
```

**Step 2: 运行 mypy 检查**

Run: `mypy src/ai_agent/llm/config.py`
Expected: 无类型错误

**Step 3: Commit**

```bash
git add src/ai_agent/llm/config.py
git commit -m "refactor(llm): add validators and complete type annotations"
```

---

## Phase 5: API 模块 & CI 集成

### Task 12: 更新 API 路由类型

**Files:**
- Modify: `src/ai_agent/api/routes/chat.py`
- Modify: `src/ai_agent/api/main.py`

**Step 1: 更新 chat.py 添加完整类型注解**

```python
# src/ai_agent/api/routes/chat.py
"""聊天路由模块"""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ai_agent.types import AgentEvent, AgentEventType

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求"""

    message: str = Field(min_length=1, max_length=10000, description="用户消息")


class ChatResponse(BaseModel):
    """聊天响应"""

    response: str = Field(description="Agent 响应")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """处理聊天请求"""
    # 从 app.state 获取 agent
    from ai_agent.agents.react import ReActAgent

    agent: ReActAgent = request.app.state.agent
    response: str = await agent.run(body.message)
    return ChatResponse(response=response)


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """流式聊天端点

    返回 SSE (Server-Sent Events) 格式的流式响应。
    每个事件包含 Agent 执行过程中的状态更新。
    """
    from ai_agent.agents.react import ReActAgent

    agent: ReActAgent = request.app.state.agent

    async def event_generator():
        """生成 SSE 事件流"""
        try:
            async for event in agent.stream(body.message):
                yield event.to_sse()
        except Exception as e:
            # 生成错误事件
            error_event = AgentEvent(
                event=AgentEventType.ERROR,
                data={"message": str(e), "details": type(e).__name__},
                step=-1,
            )
            yield error_event.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
```

**Step 2: 运行 mypy 检查**

Run: `mypy src/ai_agent/api/`
Expected: 无类型错误

**Step 3: Commit**

```bash
git add src/ai_agent/api/
git commit -m "refactor(api): add complete type annotations to routes"
```

---

### Task 13: CI 集成 mypy

**Files:**
- Create: `.github/workflows/type-check.yml`（如果使用 GitHub Actions）
- 或更新现有 CI 配置

**Step 1: 创建 GitHub Actions workflow**

```yaml
# .github/workflows/type-check.yml
name: Type Check

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  mypy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install mypy
          pip install -e .

      - name: Run mypy
        run: mypy src/ai_agent/
```

**Step 2: 本地验证 CI 流程**

Run: `mypy src/ai_agent/`
Expected: 无类型错误

**Step 3: Commit**

```bash
git add .github/workflows/type-check.yml
git commit -m "ci: add mypy type checking workflow"
```

---

### Task 14: 最终验证和清理

**Step 1: 运行完整 mypy 检查**

Run: `mypy src/ai_agent/`
Expected: `Success: no issues found`

**Step 2: 运行完整测试套件**

Run: `pytest tests/ -v`
Expected: 全部通过

**Step 3: 更新模块 __init__.py 导出**

确保所有模块正确导出新类型：

```python
# src/ai_agent/__init__.py
"""AI Agent 包"""

from ai_agent.types import (
    JSON,
    AnyDict,
    JSONDict,
    ToolResult,
    AgentEventType,
    AgentAction,
    AgentEvent,
)

__all__ = [
    "JSON",
    "AnyDict",
    "JSONDict",
    "ToolResult",
    "AgentEventType",
    "AgentAction",
    "AgentEvent",
]
```

**Step 4: 最终 Commit**

```bash
git add src/ai_agent/__init__.py
git commit -m "chore: update package exports for types module"
```

---

## Summary

**Files Created:**
- `src/ai_agent/types/__init__.py`
- `src/ai_agent/types/common.py`
- `src/ai_agent/types/tools.py`
- `src/ai_agent/types/agents.py`
- `tests/unit/tools/test_base_typed.py`
- `tests/unit/tools/web/test_google_search_typed.py`
- `.github/workflows/type-check.yml`

**Files Modified:**
- `pyproject.toml` - 添加 mypy 配置
- `src/ai_agent/tools/base.py` - 泛型基类
- `src/ai_agent/tools/web/google_search.py` - 类型化参数
- `src/ai_agent/tools/web/web_content.py` - 类型化参数
- `src/ai_agent/agents/react/graph.py` - 完整类型注解
- `src/ai_agent/agents/react/events.py` - 重导出
- `src/ai_agent/memory/base.py` - 完整类型注解
- `src/ai_agent/llm/config.py` - 验证器
- `src/ai_agent/api/routes/chat.py` - 完整类型注解
- `src/ai_agent/__init__.py` - 导出

**Migration Order:**
1. Phase 1: 基础设施（4 tasks）
2. Phase 2: Tools 模块（3 tasks）
3. Phase 3: Agents 模块（2 tasks）
4. Phase 4: Memory & LLM（2 tasks）
5. Phase 5: API & CI（3 tasks）
