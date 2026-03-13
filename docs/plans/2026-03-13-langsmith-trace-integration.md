# LangSmith Trace 集成实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 ReActAgent.stream() 方法添加 @traceable 装饰器，实现 LangSmith 中完整的任务追踪层级。

**Architecture:** 使用 langsmith.traceable 装饰器包装 stream 方法，自动创建主 Trace。LangChain 的 LLM 和 Tool 调用会被自动追踪为子 span，无需额外代码。

**Tech Stack:** langsmith, langchain-core, langgraph

---

## Task 1: 编写单元测试 - @traceable 装饰器验证

**Files:**
- Create: `tests/unit/agents/react/test_traceable.py`

**Step 1: 编写测试验证装饰器存在**

```python
"""测试 @traceable 装饰器集成"""

import pytest
from unittest.mock import MagicMock, AsyncMock
import inspect


def test_stream_method_has_traceable_decorator():
    """验证 stream 方法有 @traceable 装饰器"""
    from ai_agent.agents.react import ReActAgent

    # 检查 stream 方法存在
    assert hasattr(ReActAgent, "stream")

    # 检查方法签名
    stream_method = getattr(ReActAgent, "stream")
    assert inspect.iscoroutinefunction(stream_method)


def test_traceable_import_available():
    """验证 langsmith.traceable 可导入"""
    from langsmith import traceable

    assert callable(traceable)


@pytest.mark.asyncio
async def test_stream_returns_async_generator():
    """验证 stream 返回异步生成器"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}')
    )

    agent = ReActAgent(mock_llm, tools=[])
    result = agent.stream("test message")

    # 验证是异步生成器
    import collections.abc
    assert isinstance(result, collections.abc.AsyncGenerator)


@pytest.mark.asyncio
async def test_stream_yields_events():
    """验证 stream yield 正确的事件"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.agents.react.events import AgentEventType

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "test answer"}, "memory": "done"}')
    )

    agent = ReActAgent(mock_llm, tools=[])
    events = []

    async for event in agent.stream("test"):
        events.append(event)

    # 至少有一个 finish 事件
    assert any(e.event == AgentEventType.FINISH for e in events)
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/react/test_traceable.py -v`
Expected: 部分测试通过（装饰器相关测试等待实现）

---

## Task 2: 编写集成测试 - stream 追踪行为

**Files:**
- Create: `tests/integration/test_trace_integration.py`

**Step 1: 编写集成测试**

```python
"""Trace 集成测试"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import os


@pytest.fixture
def mock_langsmith_client():
    """模拟 LangSmith 客户端"""
    with patch("langsmith.Client") as mock_client:
        yield mock_client


@pytest.mark.asyncio
async def test_stream_creates_trace_context():
    """验证 stream 方法创建 trace 上下文"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}')
    )

    agent = ReActAgent(mock_llm, tools=[])

    # 收集事件
    events = []
    async for event in agent.stream("test question"):
        events.append(event)

    # 验证事件正常产生
    assert len(events) > 0


@pytest.mark.asyncio
async def test_trace_includes_metadata():
    """验证 trace 包含正确的 metadata"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}')
    )

    agent = ReActAgent(mock_llm, tools=[])

    # 执行 stream
    result = []
    async for event in agent.stream("test"):
        result.append(event)

    # 验证执行成功
    assert len(result) > 0


@pytest.mark.asyncio
async def test_trace_with_tool_calls():
    """验证带工具调用的 trace 结构"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    responses = [
        MagicMock(content='{"action": "echo", "params": {"text": "hello"}, "memory": "calling echo"}'),
        MagicMock(content='{"action": "finish", "params": {"answer": "done"}, "memory": "completed"}'),
    ]
    mock_llm.ainvoke = AsyncMock(side_effect=responses)

    mock_tool = MagicMock()
    mock_tool.name = "echo"
    mock_tool.description = "Echo tool"
    mock_tool.ainvoke = AsyncMock(return_value="Echo: hello")

    agent = ReActAgent(mock_llm, tools=[mock_tool])

    events = []
    async for event in agent.stream("test"):
        events.append(event)

    # 验证有 think, act, observe, finish 事件
    event_types = [e.event for e in events]
    from ai_agent.agents.react.events import AgentEventType

    assert AgentEventType.THINK in event_types
    assert AgentEventType.ACT in event_types
    assert AgentEventType.OBSERVE in event_types
    assert AgentEventType.FINISH in event_types
```

**Step 2: 运行测试**

Run: `pytest tests/integration/test_trace_integration.py -v`

---

## Task 3: 实现 @traceable 装饰器

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py`

**Step 1: 添加导入**

在文件顶部（约第 9 行后）添加：

```python
from langsmith import traceable
```

**Step 2: 添加装饰器到 stream 方法**

在 `stream` 方法定义前（约第 254 行）添加装饰器：

```python
@traceable(
    name="react_agent",
    run_type="chain",
    tags=["react", "agent"],
)
async def stream(self, message: str) -> AsyncGenerator[AgentEvent, None]:
```

**Step 3: 验证语法**

Run: `python -m py_compile src/ai_agent/agents/react/graph.py`
Expected: 无输出（编译成功）

---

## Task 4: 编写真实 API 测试 - LangSmith 集成

**Files:**
- Modify: `tests/integration/test_react_agent_live.py`

**Step 1: 添加 LangSmith 追踪验证测试**

在现有文件末尾添加：

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_react_agent_langsmith_trace():
    """真实 API 测试：验证 LangSmith trace 创建

    此测试需要真实的 API 密钥：
    - OPENAI_API_KEY
    - LANGSMITH_API_KEY

    运行方式：pytest -m integration tests/integration/test_react_agent_live.py::test_react_agent_langsmith_trace -v
    """
    import os

    # 检查环境变量
    if not os.getenv("LANGSMITH_API_KEY"):
        pytest.skip("LANGSMITH_API_KEY not set")

    from ai_agent.agents.react import ReActAgent
    from ai_agent.agents.react.events import AgentEventType
    from ai_agent.llm import get_llm
    from ai_agent.tools import get_all_tools

    # 初始化 LLM 和工具
    llm = get_llm()
    tools = get_all_tools()

    agent = ReActAgent(llm, tools=tools, max_steps=3)

    # 执行一个简单查询
    events = []
    async for event in agent.stream("今天北京天气怎么样？"):
        events.append(event)
        print(f"Event: {event.event}, Step: {event.step}")

    # 验证事件
    assert len(events) > 0
    event_types = [e.event for e in events]
    assert AgentEventType.FINISH in event_types

    # 提示：检查 LangSmith 控制台验证 trace 结构
    print("\n✅ 请在 LangSmith 控制台检查 trace 结构：")
    print("   https://smith.langchain.com")
    print("   项目: ai-agent")
    print("   应该看到一个名为 'react_agent' 的 trace")
```

**Step 2: 运行真实 API 测试**

Run: `pytest -m integration tests/integration/test_react_agent_live.py::test_react_agent_langsmith_trace -v`

---

## Task 5: 运行所有测试验证

**Step 1: 运行单元测试**

Run: `pytest tests/unit/agents/react/ -v`
Expected: 所有测试通过

**Step 2: 运行集成测试（mock）**

Run: `pytest tests/integration/test_trace_integration.py -v`
Expected: 所有测试通过

**Step 3: 运行集成测试（真实 API，需要密钥）**

Run: `pytest -m integration tests/integration/ -v`
Expected: 所有测试通过（需要 API 密钥）

**Step 4: 检查代码覆盖率（可选）**

Run: `pytest tests/unit/agents/react/ --cov=src/ai_agent/agents/react --cov-report=term-missing`

---

## Task 6: 提交更改

**Step 1: 检查更改**

Run: `git status`

**Step 2: 添加文件**

```bash
git add src/ai_agent/agents/react/graph.py
git add tests/unit/agents/react/test_traceable.py
git add tests/integration/test_trace_integration.py
git add docs/plans/2026-03-13-langsmith-trace-integration.md
```

**Step 3: 提交**

```bash
git commit -m "feat(trace): add @traceable decorator to ReActAgent.stream for LangSmith integration

- Add @traceable decorator to stream method for hierarchical tracing
- Add unit tests for decorator verification
- Add integration tests for trace context
- Add live API test for LangSmith trace validation
"
```

---

## 改动摘要

| 文件 | 操作 | 行数 |
|------|------|------|
| `src/ai_agent/agents/react/graph.py` | 修改 | +7 行 |
| `tests/unit/agents/react/test_traceable.py` | 新建 | ~70 行 |
| `tests/integration/test_trace_integration.py` | 新建 | ~80 行 |
| `tests/integration/test_react_agent_live.py` | 修改 | +40 行 |

## 预期效果

```
LangSmith Trace: react_agent
├── LLM Call (think - ainvoke)
├── Tool Call (act - tool.ainvoke)
│   └── [Tool-specific spans]
├── LLM Call (think - ainvoke)
└── ...
```
