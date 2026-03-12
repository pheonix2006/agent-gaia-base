# AI Agent MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个基于 LangGraph 的多层架构 AI Agent 服务，支持 FastAPI 接口、工具注册和 LangSmith 追踪。

**Architecture:** 五层分离架构 - API 层、Agent 层、工具层、LLM 配置层、追踪层。每层独立解耦，通过依赖注入组装。支持未来扩展多种 Agent 类型（ReAct、Plan-and-Execute 等）。

**Tech Stack:**
- FastAPI + Uvicorn（API 服务）
- LangGraph（Agent 状态机）
- LangChain OpenAI（LLM 客户端，兼容 DeepSeek）
- Pydantic Settings（配置管理）
- LangSmith（链路追踪）
- Pytest（TDD 测试）

---

## 项目结构

```
ai-agent/
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── src/
    └── ai_agent/
        ├── __init__.py
        ├── api/
        │   ├── __init__.py
        │   ├── main.py
        │   └── routes/
        │       ├── __init__.py
        │       └── chat.py
        ├── agents/
        │   ├── __init__.py
        │   ├── base.py
        │   └── simple/
        │       ├── __init__.py
        │       └── graph.py
        ├── tools/
        │   ├── __init__.py
        │   ├── base.py
        │   └── registry.py
        ├── llm/
        │   ├── __init__.py
        │   ├── config.py
        │   └── client.py
        └── trace/
            ├── __init__.py
            └── langsmith.py
tests/
├── conftest.py
├── unit/
│   ├── llm/
│   │   ├── test_config.py
│   │   └── test_client.py
│   ├── tools/
│   │   ├── test_base.py
│   │   └── test_registry.py
│   └── agents/
│       └── test_simple_agent.py
└── integration/
    ├── test_api_chat.py
    └── test_real_api.py
```

---

## Task 1: 项目初始化

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/ai_agent/__init__.py`

**Step 1: 使用 uv 初始化项目**

Run: `cd "E:/Project/ai agent" && uv init --name ai-agent --python 3.11`
Expected: 创建 pyproject.toml

**Step 2: 添加依赖**

Run:
```bash
cd "E:/Project/ai agent" && uv add fastapi uvicorn langgraph langchain-openai langchain-core pydantic-settings python-dotenv pytest pytest-asyncio httpx
```
Expected: 依赖添加到 pyproject.toml

**Step 3: 创建 .gitignore**

```gitignore
.env
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
.pytest_cache/
.ruff_cache/
```

**Step 4: 创建 .env.example**

```env
# LLM 配置 (DeepSeek)
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
TEMPERATURE=0.7

# LangSmith 追踪配置
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key_here
LANGSMITH_PROJECT=ai-agent
```

**Step 5: 创建目录结构**

Run:
```bash
cd "E:/Project/ai agent" && mkdir -p src/ai_agent/api/routes src/ai_agent/agents/simple src/ai_agent/tools src/ai_agent/llm src/ai_agent/trace tests/unit/llm tests/unit/tools tests/unit/agents tests/integration
```

**Step 6: 创建 __init__.py 文件**

Run:
```bash
cd "E:/Project/ai agent" && touch src/ai_agent/__init__.py src/ai_agent/api/__init__.py src/ai_agent/api/routes/__init__.py src/ai_agent/agents/__init__.py src/ai_agent/agents/simple/__init__.py src/ai_agent/tools/__init__.py src/ai_agent/llm/__init__.py src/ai_agent/trace/__init__.py tests/__init__.py tests/unit/__init__.py tests/unit/llm/__init__.py tests/unit/tools/__init__.py tests/unit/agents/__init__.py tests/integration/__init__.py
```

**Step 7: Commit**

```bash
git init
git add .
git commit -m "chore: initialize project structure with uv"
```

---

## Task 2: LLM 配置层 - 配置定义 (TDD)

**Files:**
- Create: `tests/unit/llm/test_config.py`
- Create: `src/ai_agent/llm/config.py`

**Step 1: Write the failing test**

```python
# tests/unit/llm/test_config.py
import os
import pytest
from pydantic import ValidationError


def test_llm_settings_defaults():
    """测试 LLM 配置默认值"""
    # 设置必要的环境变量
    os.environ["OPENAI_API_KEY"] = "test-key"

    from ai_agent.llm.config import LLMSettings

    settings = LLMSettings()

    assert settings.openai_api_key == "test-key"
    assert settings.openai_base_url == "https://api.deepseek.com/v1"
    assert settings.openai_model == "deepseek-chat"
    assert settings.temperature == 0.7


def test_llm_settings_custom_values():
    """测试自定义配置值"""
    os.environ["OPENAI_API_KEY"] = "custom-key"
    os.environ["OPENAI_BASE_URL"] = "https://custom.api.com/v1"
    os.environ["OPENAI_MODEL"] = "custom-model"
    os.environ["TEMPERATURE"] = "0.5"

    from ai_agent.llm.config import LLMSettings

    # 清除模块缓存以获取新值
    import importlib
    import ai_agent.llm.config as config_module
    importlib.reload(config_module)

    settings = config_module.LLMSettings()

    assert settings.openai_api_key == "custom-key"
    assert settings.openai_base_url == "https://custom.api.com/v1"
    assert settings.openai_model == "custom-model"
    assert settings.temperature == 0.5


def test_llm_settings_missing_api_key():
    """测试缺少 API Key 时抛出错误"""
    # 清除环境变量
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]

    from ai_agent.llm.config import LLMSettings

    with pytest.raises(ValidationError):
        LLMSettings()
```

**Step 2: Run test to verify it fails**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/llm/test_config.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/llm/config.py
from pydantic_settings import BaseSettings


class LLMSettings(BaseSettings):
    """LLM 配置"""

    openai_api_key: str
    openai_base_url: str = "https://api.deepseek.com/v1"
    openai_model: str = "deepseek-chat"
    temperature: float = 0.7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

**Step 4: Run test to verify it passes**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/llm/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/llm/test_config.py src/ai_agent/llm/config.py
git commit -m "feat(llm): add LLM settings configuration"
```

---

## Task 3: LLM 配置层 - 客户端工厂 (TDD)

**Files:**
- Create: `tests/unit/llm/test_client.py`
- Create: `src/ai_agent/llm/client.py`

**Step 1: Write the failing test**

```python
# tests/unit/llm/test_client.py
import os
import pytest
from unittest.mock import patch, MagicMock


def test_create_llm_client_with_settings():
    """测试使用配置创建 LLM 客户端"""
    os.environ["OPENAI_API_KEY"] = "test-key"

    from ai_agent.llm.config import LLMSettings
    from ai_agent.llm.client import create_llm_client

    settings = LLMSettings()
    client = create_llm_client(settings)

    assert client is not None
    assert client.model_name == settings.openai_model


def test_create_llm_client_without_settings():
    """测试不传配置时自动加载"""
    os.environ["OPENAI_API_KEY"] = "auto-key"

    from ai_agent.llm.client import create_llm_client

    client = create_llm_client()

    assert client is not None


def test_llm_client_configuration():
    """测试客户端配置正确性"""
    os.environ["OPENAI_API_KEY"] = "config-test-key"
    os.environ["OPENAI_BASE_URL"] = "https://test.api.com/v1"
    os.environ["OPENAI_MODEL"] = "test-model"
    os.environ["TEMPERATURE"] = "0.3"

    from ai_agent.llm.config import LLMSettings
    from ai_agent.llm.client import create_llm_client

    settings = LLMSettings()
    client = create_llm_client(settings)

    assert client.model_name == "test-model"
    assert client.temperature == 0.3
```

**Step 2: Run test to verify it fails**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/llm/test_client.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/llm/client.py
from langchain_openai import ChatOpenAI
from .config import LLMSettings


def create_llm_client(settings: LLMSettings | None = None) -> ChatOpenAI:
    """创建 LLM 客户端

    Args:
        settings: LLM 配置，不传则自动加载

    Returns:
        ChatOpenAI 客户端实例
    """
    if settings is None:
        settings = LLMSettings()

    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=settings.temperature,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/llm/test_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/llm/test_client.py src/ai_agent/llm/client.py
git commit -m "feat(llm): add LLM client factory"
```

---

## Task 4: 追踪层 - LangSmith 配置 (TDD)

**Files:**
- Create: `tests/unit/trace/test_langsmith.py`
- Create: `tests/unit/trace/__init__.py`
- Create: `src/ai_agent/trace/langsmith.py`

**Step 1: Write the failing test**

```python
# tests/unit/trace/test_langsmith.py
import os
import pytest


def test_langsmith_settings_defaults():
    """测试 LangSmith 配置默认值"""
    os.environ["LANGSMITH_API_KEY"] = "test-langsmith-key"

    from ai_agent.trace.langsmith import LangSmithSettings

    settings = LangSmithSettings()

    assert settings.langsmith_tracing is True
    assert settings.langsmith_project == "ai-agent"
    assert settings.langsmith_api_key == "test-langsmith-key"


def test_langsmith_setup_sets_environment():
    """测试 setup 方法设置环境变量"""
    os.environ["LANGSMITH_API_KEY"] = "setup-test-key"

    from ai_agent.trace.langsmith import LangSmithSettings

    settings = LangSmithSettings()
    settings.setup()

    assert os.environ.get("LANGSMITH_TRACING") == "true"
    assert os.environ.get("LANGSMITH_PROJECT") == "ai-agent"
    assert os.environ.get("LANGSMITH_API_KEY") == "setup-test-key"


def test_langsmith_can_be_disabled():
    """测试可以禁用追踪"""
    os.environ["LANGSMITH_API_KEY"] = "disable-test-key"
    os.environ["LANGSMITH_TRACING"] = "false"

    from ai_agent.trace.langsmith import LangSmithSettings

    settings = LangSmithSettings()

    assert settings.langsmith_tracing is False
```

**Step 2: Run test to verify it fails**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/trace/test_langsmith.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/trace/langsmith.py
import os
from pydantic_settings import BaseSettings


class LangSmithSettings(BaseSettings):
    """LangSmith 追踪配置"""

    langsmith_tracing: bool = True
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str
    langsmith_project: str = "ai-agent"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def setup(self) -> None:
        """配置 LangSmith 环境变量"""
        os.environ["LANGSMITH_TRACING"] = str(self.langsmith_tracing).lower()
        os.environ["LANGSMITH_ENDPOINT"] = self.langsmith_endpoint
        os.environ["LANGSMITH_API_KEY"] = self.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = self.langsmith_project
```

**Step 4: Run test to verify it passes**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/trace/test_langsmith.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/trace/ src/ai_agent/trace/langsmith.py
git commit -m "feat(trace): add LangSmith tracing configuration"
```

---

## Task 5: 工具层 - 工具基类 (TDD)

**Files:**
- Create: `tests/unit/tools/test_base.py`
- Create: `src/ai_agent/tools/base.py`

**Step 1: Write the failing test**

```python
# tests/unit/tools/test_base.py
import pytest
from langchain_core.tools import Tool


def test_tool_result_model():
    """测试工具结果模型"""
    from ai_agent.tools.base import ToolResult

    result = ToolResult(success=True, data="test data")
    assert result.success is True
    assert result.data == "test data"
    assert result.error is None

    error_result = ToolResult(success=False, data="", error="test error")
    assert error_result.success is False
    assert error_result.error == "test error"


def test_base_agent_tool_is_abstract():
    """测试基类是抽象类"""
    from ai_agent.tools.base import BaseAgentTool

    with pytest.raises(TypeError):
        BaseAgentTool()


def test_concrete_tool_implementation():
    """测试具体工具实现"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class EchoTool(BaseAgentTool):
        @property
        def name(self) -> str:
            return "echo"

        @property
        def description(self) -> str:
            return "Echo back the input"

        def run(self, text: str) -> ToolResult:
            return ToolResult(success=True, data=text)

    tool = EchoTool()
    assert tool.name == "echo"
    assert tool.description == "Echo back the input"

    result = tool.run("hello")
    assert result.success is True
    assert result.data == "hello"


def test_tool_to_langchain_conversion():
    """测试转换为 LangChain 工具"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class TestTool(BaseAgentTool):
        @property
        def name(self) -> str:
            return "test_tool"

        @property
        def description(self) -> str:
            return "A test tool"

        def run(self, x: str) -> ToolResult:
            return ToolResult(success=True, data=f"processed: {x}")

    tool = TestTool()
    lc_tool = tool.to_langchain_tool()

    assert isinstance(lc_tool, Tool)
    assert lc_tool.name == "test_tool"
    assert lc_tool.description == "A test tool"
```

**Step 2: Run test to verify it fails**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/tools/test_base.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/tools/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel
from langchain_core.tools import Tool


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool
    data: str
    error: str | None = None


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

    @abstractmethod
    def run(self, *args, **kwargs) -> ToolResult:
        """执行工具逻辑"""
        pass

    def to_langchain_tool(self) -> Tool:
        """转换为 LangChain 工具格式"""
        return Tool(
            name=self.name,
            description=self.description,
            func=lambda *args, **kwargs: self.run(*args, **kwargs).data,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/tools/test_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/tools/test_base.py src/ai_agent/tools/base.py
git commit -m "feat(tools): add base tool class and result model"
```

---

## Task 6: 工具层 - 工具注册中心 (TDD)

**Files:**
- Create: `tests/unit/tools/test_registry.py`
- Create: `src/ai_agent/tools/registry.py`

**Step 1: Write the failing test**

```python
# tests/unit/tools/test_registry.py
import pytest
from ai_agent.tools.base import BaseAgentTool, ToolResult
from ai_agent.tools.registry import ToolRegistry


class MockTool(BaseAgentTool):
    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    def run(self, x: str) -> ToolResult:
        return ToolResult(success=True, data=x)


class AnotherTool(BaseAgentTool):
    @property
    def name(self) -> str:
        return "another_tool"

    @property
    def description(self) -> str:
        return "Another mock tool"

    def run(self, x: str) -> ToolResult:
        return ToolResult(success=True, data=x.upper())


@pytest.fixture(autouse=True)
def clear_registry():
    """每个测试前清空注册中心"""
    ToolRegistry._tools = {}
    yield
    ToolRegistry._tools = {}


def test_register_tool():
    """测试注册工具"""
    tool = MockTool()
    ToolRegistry.register(tool)

    assert "mock_tool" in ToolRegistry._tools
    assert ToolRegistry._tools["mock_tool"] == tool


def test_get_tool():
    """测试获取工具"""
    tool = MockTool()
    ToolRegistry.register(tool)

    retrieved = ToolRegistry.get("mock_tool")
    assert retrieved == tool


def test_get_nonexistent_tool():
    """测试获取不存在的工具"""
    retrieved = ToolRegistry.get("nonexistent")
    assert retrieved is None


def test_get_all_tools():
    """测试获取所有工具"""
    tool1 = MockTool()
    tool2 = AnotherTool()
    ToolRegistry.register(tool1)
    ToolRegistry.register(tool2)

    all_tools = ToolRegistry.get_all()
    assert len(all_tools) == 2
    assert tool1 in all_tools
    assert tool2 in all_tools


def test_get_langchain_tools():
    """测试获取 LangChain 格式的工具"""
    tool = MockTool()
    ToolRegistry.register(tool)

    lc_tools = ToolRegistry.get_langchain_tools()
    assert len(lc_tools) == 1
    assert lc_tools[0].name == "mock_tool"


def test_registry_is_singleton():
    """测试注册中心是单例"""
    r1 = ToolRegistry()
    r2 = ToolRegistry()
    assert r1 is r2
```

**Step 2: Run test to verify it fails**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/tools/test_registry.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/tools/registry.py
from typing import Type
from .base import BaseAgentTool


class ToolRegistry:
    """工具注册中心（单例模式）"""

    _instance = None
    _tools: dict[str, BaseAgentTool] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, tool: BaseAgentTool) -> None:
        """注册工具"""
        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str) -> BaseAgentTool | None:
        """获取工具"""
        return cls._tools.get(name)

    @classmethod
    def get_all(cls) -> list[BaseAgentTool]:
        """获取所有工具"""
        return list(cls._tools.values())

    @classmethod
    def get_langchain_tools(cls) -> list:
        """获取 LangChain 格式的所有工具"""
        return [t.to_langchain_tool() for t in cls._tools.values()]

    @classmethod
    def clear(cls) -> None:
        """清空注册中心（仅用于测试）"""
        cls._tools = {}
```

**Step 4: Run test to verify it passes**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/tools/test_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/tools/test_registry.py src/ai_agent/tools/registry.py
git commit -m "feat(tools): add tool registry with singleton pattern"
```

---

## Task 7: Agent 层 - Agent 基类 (TDD)

**Files:**
- Create: `tests/unit/agents/test_base.py`
- Create: `tests/unit/agents/__init__.py`
- Create: `src/ai_agent/agents/base.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/test_base.py
import pytest
from unittest.mock import MagicMock


def test_base_agent_is_abstract():
    """测试 Agent 基类是抽象类"""
    from ai_agent.agents.base import BaseAgent

    mock_llm = MagicMock()
    with pytest.raises(TypeError):
        BaseAgent(mock_llm)


def test_base_agent_interface():
    """测试 Agent 接口定义"""
    from ai_agent.agents.base import BaseAgent

    class ConcreteAgent(BaseAgent):
        async def run(self, message: str) -> str:
            return f"Response to: {message}"

        def get_graph(self):
            return "mock_graph"

    mock_llm = MagicMock()
    agent = ConcreteAgent(mock_llm)

    assert agent.llm == mock_llm
    assert agent.tools == []


def test_base_agent_with_tools():
    """测试带工具的 Agent"""
    from ai_agent.agents.base import BaseAgent

    class ToolAgent(BaseAgent):
        async def run(self, message: str) -> str:
            return "ok"

        def get_graph(self):
            return None

    mock_llm = MagicMock()
    mock_tools = [MagicMock(), MagicMock()]

    agent = ToolAgent(mock_llm, tools=mock_tools)
    assert len(agent.tools) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_base.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/agents/base.py
from abc import ABC, abstractmethod
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool


class BaseAgent(ABC):
    """Agent 基类，定义统一接口"""

    def __init__(self, llm: BaseChatModel, tools: list[BaseTool] | None = None):
        self.llm = llm
        self.tools = tools or []

    @abstractmethod
    async def run(self, message: str) -> str:
        """运行 Agent，返回响应"""
        pass

    @abstractmethod
    def get_graph(self):
        """获取 LangGraph 编译后的图（用于调试/可视化）"""
        pass
```

**Step 4: Run test to verify it passes**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/agents/test_base.py tests/unit/agents/__init__.py src/ai_agent/agents/base.py
git commit -m "feat(agents): add base agent interface"
```

---

## Task 8: Agent 层 - 简单对话 Agent (TDD)

**Files:**
- Create: `tests/unit/agents/test_simple_agent.py`
- Create: `src/ai_agent/agents/simple/graph.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/test_simple_agent.py
import os
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_llm():
    """创建模拟 LLM"""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="Mock response"))
    return llm


def test_simple_chat_agent_initialization(mock_llm):
    """测试 SimpleChatAgent 初始化"""
    from ai_agent.agents.simple.graph import SimpleChatAgent

    agent = SimpleChatAgent(mock_llm)
    assert agent.llm == mock_llm
    assert agent.tools == []


def test_simple_chat_agent_has_graph(mock_llm):
    """测试 SimpleChatAgent 有图"""
    from ai_agent.agents.simple.graph import SimpleChatAgent

    agent = SimpleChatAgent(mock_llm)
    graph = agent.get_graph()

    assert graph is not None


@pytest.mark.asyncio
async def test_simple_chat_agent_run(mock_llm):
    """测试 SimpleChatAgent 运行"""
    from ai_agent.agents.simple.graph import SimpleChatAgent

    agent = SimpleChatAgent(mock_llm)
    response = await agent.run("Hello")

    assert response == "Mock response"


@pytest.mark.asyncio
async def test_simple_chat_agent_invokes_llm(mock_llm):
    """测试 SimpleChatAgent 调用 LLM"""
    from ai_agent.agents.simple.graph import SimpleChatAgent

    agent = SimpleChatAgent(mock_llm)
    await agent.run("Test message")

    mock_llm.ainvoke.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_simple_agent.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/agents/simple/graph.py
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_core.messages import HumanMessage
from ..base import BaseAgent


class SimpleChatAgent(BaseAgent):
    """简单对话 Agent，无工具调用"""

    def __init__(self, llm):
        super().__init__(llm)
        self._graph = self._build_graph()

    def _build_graph(self):
        """构建 LangGraph 图"""

        async def chat_node(state: MessagesState):
            response = await self.llm.ainvoke(state["messages"])
            return {"messages": [response]}

        graph = StateGraph(MessagesState)
        graph.add_node("chat", chat_node)
        graph.add_edge(START, "chat")
        graph.add_edge("chat", END)
        return graph.compile()

    async def run(self, message: str) -> str:
        """运行 Agent"""
        result = await self._graph.ainvoke({"messages": [HumanMessage(message)]})
        return result["messages"][-1].content

    def get_graph(self):
        """获取编译后的图"""
        return self._graph
```

**Step 4: Run test to verify it passes**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_simple_agent.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/agents/test_simple_agent.py src/ai_agent/agents/simple/graph.py
git commit -m "feat(agents): add simple chat agent with LangGraph"
```

---

## Task 9: API 层 - FastAPI 应用入口 (TDD)

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/integration/test_api_chat.py`
- Create: `src/ai_agent/api/main.py`

**Step 1: Write the failing test**

```python
# tests/conftest.py
import os
import pytest


@pytest.fixture(autouse=True)
def setup_env():
    """设置测试环境变量"""
    os.environ["OPENAI_API_KEY"] = "test-api-key"
    os.environ["LANGSMITH_API_KEY"] = "test-langsmith-key"
    yield


@pytest.fixture
def mock_llm():
    """创建模拟 LLM"""
    from unittest.mock import MagicMock, AsyncMock

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test response"))
    return llm
```

```python
# tests/integration/test_api_chat.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
async def client():
    """创建测试客户端"""
    from ai_agent.api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_chat_endpoint_returns_response(client):
    """测试聊天端点返回响应"""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Hello! How can I help you?"))

    with patch("ai_agent.api.main.create_llm_client", return_value=mock_llm):
        # 重新初始化应用状态
        from ai_agent.api.main import app, SimpleChatAgent
        app.state.agent = SimpleChatAgent(mock_llm)

        response = await client.post(
            "/api/v1/chat",
            json={"message": "Hello"}
        )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data


@pytest.mark.asyncio
async def test_chat_endpoint_validates_input(client):
    """测试聊天端点验证输入"""
    response = await client.post(
        "/api/v1/chat",
        json={}
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_health_check(client):
    """测试健康检查端点"""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
```

**Step 2: Run test to verify it fails**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/integration/test_api_chat.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/ai_agent/api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ai_agent.llm.client import create_llm_client
from ai_agent.agents.simple.graph import SimpleChatAgent
from ai_agent.trace.langsmith import LangSmithSettings
from .routes.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    try:
        LangSmithSettings().setup()
    except Exception:
        pass  # LangSmith 配置可选

    llm = create_llm_client()
    app.state.agent = SimpleChatAgent(llm)
    yield
    # 关闭时清理


app = FastAPI(
    title="AI Agent API",
    description="基于 LangGraph 的 AI Agent 服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}
```

**Step 4: Run test to verify it passes**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/integration/test_api_chat.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/conftest.py tests/integration/test_api_chat.py src/ai_agent/api/main.py
git commit -m "feat(api): add FastAPI application with lifespan management"
```

---

## Task 10: API 层 - 聊天路由 (TDD)

**Files:**
- Create: `src/ai_agent/api/routes/chat.py`

**Step 1: Write the failing test (update existing)**

Add to `tests/integration/test_api_chat.py`:

```python
@pytest.mark.asyncio
async def test_chat_endpoint_structure(client):
    """测试响应结构"""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Structured response"))

    with patch("ai_agent.api.main.create_llm_client", return_value=mock_llm):
        from ai_agent.api.main import app, SimpleChatAgent
        app.state.agent = SimpleChatAgent(mock_llm)

        response = await client.post(
            "/api/v1/chat",
            json={"message": "Test"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Structured response"
```

**Step 2: Run test to verify setup**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/integration/test_api_chat.py -v`

**Step 3: Write minimal implementation**

```python
# src/ai_agent/api/routes/chat.py
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    """处理聊天请求"""
    agent = request.app.state.agent
    response = await agent.run(body.message)
    return ChatResponse(response=response)
```

**Step 4: Run test to verify it passes**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/integration/test_api_chat.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/api/routes/chat.py
git commit -m "feat(api): add chat route with request/response models"
```

---

## Task 11: 真实 API 集成测试 (TDD)

**Files:**
- Create: `tests/integration/test_real_api.py`

**注意:** 此任务需要真实的 API Key，标记为 `integration_real`

**Step 1: Write the test**

```python
# tests/integration/test_real_api.py
import os
import pytest

# 跳过条件：没有真实 API Key
requires_real_api = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-api-key",
    reason="需要真实的 OPENAI_API_KEY"
)


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_real_llm_response():
    """测试真实 LLM API 调用"""
    from ai_agent.llm.client import create_llm_client
    from langchain_core.messages import HumanMessage

    llm = create_llm_client()
    response = await llm.ainvoke([HumanMessage("Say 'Hello World' and nothing else")])

    assert response is not None
    assert response.content
    assert len(response.content) > 0


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_real_simple_chat_agent():
    """测试真实 SimpleChatAgent"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.agents.simple.graph import SimpleChatAgent

    llm = create_llm_client()
    agent = SimpleChatAgent(llm)

    response = await agent.run("What is 2+2? Answer with just the number.")

    assert response is not None
    assert "4" in response


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_real_api_end_to_end():
    """端到端测试：真实 API 通过 FastAPI"""
    from fastapi.testclient import TestClient
    from ai_agent.api.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Say 'pong' and nothing else"}
        )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert len(data["response"]) > 0
```

**Step 2: Run with real API key**

创建 `.env` 文件：
```env
OPENAI_API_KEY=sk-5d8c889707064007b05790121702a383
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
TEMPERATURE=0.7
```

Run: `cd "E:/Project/ai agent" && uv run pytest tests/integration/test_real_api.py -v -m integration_real`
Expected: PASS (使用真实 API)

**Step 3: Commit**

```bash
git add tests/integration/test_real_api.py
git commit -m "test: add real API integration tests"
```

---

## Task 12: 运行所有测试并验证

**Step 1: 运行单元测试**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit -v`
Expected: All PASS

**Step 2: 运行集成测试（模拟）**

Run: `cd "E:/Project/ai agent" && uv run pytest tests/integration -v -m "not integration_real"`
Expected: All PASS

**Step 3: 运行完整测试套件**

Run: `cd "E:/Project/ai agent" && uv run pytest -v --cov=src/ai_agent`
Expected: All PASS with coverage report

**Step 4: Final Commit**

```bash
git add .
git commit -m "test: complete test suite with unit and integration tests"
```

---

## Task 13: 启动服务并手动验证

**Step 1: 启动服务**

Run: `cd "E:/Project/ai agent" && uv run uvicorn ai_agent.api.main:app --reload`

**Step 2: 测试 API**

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, who are you?"}'
```

**Step 3: 访问文档**

打开浏览器: http://localhost:8000/docs

---

## 执行选项

**Plan complete and saved to `docs/plans/2026-03-11-ai-agent-mvp.md`.**

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
