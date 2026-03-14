# ReAct Agent Memory 集成实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将现有的 CompressedMemory 模块集成到 ReActAgent，实现单次长任务的上下文管理。

**Architecture:** 在 ReActAgent 中注入 CompressedMemory 实例，_observe_node 记录每步操作，_think_node 读取 memory.as_text() 注入 prompt。

**Tech Stack:** Python 3.11+, Pydantic, LangChain, pytest, pytest-asyncio

---

## 现状分析

### 已实现 ✅
- `src/ai_agent/memory/base.py` - MemoryRecord, BaseMemory, CompressedMemory
- `tests/unit/memory/test_base.py` - Memory 单元测试（完整）

### 待实现 ❌
- ReActAgent 集成 Memory
- 集成测试验证 memory 注入
- stream() 方法的 memory 支持

---

## Task 1: 添加 Memory 到 ReActAgent 构造函数

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py:57-69`

**Step 1: Write the failing test**

```python
# tests/unit/agents/test_react_agent_memory.py

import pytest
from unittest.mock import MagicMock

def test_react_agent_accepts_memory():
    """测试 ReActAgent 接受 memory 参数"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()
    mock_memory = MagicMock(spec=CompressedMemory)

    agent = ReActAgent(mock_llm, memory=mock_memory)

    assert agent._memory is mock_memory


def test_react_agent_creates_default_memory():
    """测试 ReActAgent 默认创建 memory"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()

    agent = ReActAgent(mock_llm, create_memory=True)

    assert agent._memory is not None
    assert isinstance(agent._memory, CompressedMemory)


def test_react_agent_no_memory_by_default():
    """测试默认不创建 memory（保持向后兼容）"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm)

    assert agent._memory is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/test_react_agent_memory.py -v`
Expected: FAIL - `AttributeError: 'ReActAgent' has no attribute '_memory'`

**Step 3: Write minimal implementation**

```python
# src/ai_agent/agents/react/graph.py
# 在 __init__ 方法中添加 memory 参数

def __init__(
    self,
    llm,
    tools: List[BaseTool] | None = None,
    prompt: ReActPrompt | None = None,
    max_steps: int = MAX_STEPS,
    max_retries: int = MAX_RETRIES,
    memory: Optional["CompressedMemory"] = None,
    create_memory: bool = False,
):
    super().__init__(llm, tools)
    self.prompt = prompt or ReActPrompt()
    self.max_steps = max_steps
    self.max_retries = max_retries

    # Memory 集成
    if memory is not None:
        self._memory = memory
    elif create_memory:
        from ...memory import CompressedMemory
        self._memory = CompressedMemory(llm=llm, max_memory=10, keep_recent=3)
    else:
        self._memory = None

    self._graph = self._build_graph()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/test_react_agent_memory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/agents/react/graph.py tests/unit/agents/test_react_agent_memory.py
git commit -m "feat(react): add memory parameter to ReActAgent constructor"
```

---

## Task 2: 在 _think_node 中注入 Memory 文本

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py:102-133`
- Modify: `tests/unit/agents/test_react_agent_memory.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/test_react_agent_memory.py

@pytest.mark.asyncio
async def test_think_node_injects_memory_text():
    """测试 _think_node 注入 memory 文本到 prompt"""
    from ai_agent.agents.react import ReActAgent, AgentState
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}')
    )

    # 创建带内容的 memory
    memory = CompressedMemory(mock_llm)
    memory._summary = "Previous summary"

    agent = ReActAgent(mock_llm, memory=memory)

    state = AgentState(question="test question")
    result = await agent._think_node(state)

    # 验证 LLM 被调用
    assert mock_llm.ainvoke.called

    # 验证 prompt 包含 memory 内容
    call_args = mock_llm.ainvoke.call_args
    prompt = call_args[0][0].content  # HumanMessage.content

    assert "Previous summary" in prompt


@pytest.mark.asyncio
async def test_think_node_memory_none_when_no_memory():
    """测试无 memory 时 prompt 中为 None"""
    from ai_agent.agents.react import ReActAgent, AgentState

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}')
    )

    agent = ReActAgent(mock_llm)  # 无 memory

    state = AgentState(question="test")
    await agent._think_node(state)

    call_args = mock_llm.ainvoke.call_args
    prompt = call_args[0][0].content

    # 验证 prompt 中 memory 部分是 "None"
    assert "==== Memory ====\nNone" in prompt
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/test_react_agent_memory.py::test_think_node_injects_memory_text -v`
Expected: FAIL - `AssertionError: 'Previous summary' not found in prompt`

**Step 3: Write minimal implementation**

```python
# src/ai_agent/agents/react/graph.py
# 修改 _think_node 方法

async def _think_node(self, state: AgentState) -> Dict[str, Any]:
    """Think 节点：调用 LLM 决定下一步行动"""
    # 构建工具描述
    action_space = self._build_action_space()

    # 获取 memory 文本
    memory_text = self._memory.as_text() if self._memory else "None"

    # 格式化 Prompt
    formatted_prompt = self.prompt.format(
        original_question=state.question,
        action_space=action_space,
        memory=memory_text,  # 注入 memory
        obs=state.current_obs or "No observation yet.",
    )

    # ... 其余代码不变
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/test_react_agent_memory.py::test_think_node_injects_memory_text -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/agents/react/graph.py tests/unit/agents/test_react_agent_memory.py
git commit -m "feat(react): inject memory text into _think_node prompt"
```

---

## Task 3: 在 _observe_node 中记录到 Memory

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py:162-164`
- Modify: `tests/unit/agents/test_react_agent_memory.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/test_react_agent_memory.py

@pytest.mark.asyncio
async def test_observe_node_records_to_memory():
    """测试 _observe_node 记录操作到 memory"""
    from ai_agent.agents.react import ReActAgent, AgentState, ReActAction
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()

    # 创建 mock memory 追踪调用
    memory = MagicMock(spec=CompressedMemory)
    memory.add = AsyncMock()

    agent = ReActAgent(mock_llm, memory=memory)

    state = AgentState(
        question="test",
        current_obs="Observation result",
        steps_taken=1,
        actions_history=[
            ReActAction(action="search", params={"q": "test"}, memory="Searching for test")
        ],
    )

    await agent._observe_node(state)

    # 验证 memory.add 被调用
    assert memory.add.called

    # 验证传递的记录内容
    call_args = memory.add.call_args
    record = call_args[0][0]  # MemoryRecord

    assert record.observation == "Observation result"
    assert record.action == "search"


@pytest.mark.asyncio
async def test_observe_node_no_memory_no_error():
    """测试无 memory 时不报错"""
    from ai_agent.agents.react import ReActAgent, AgentState, ReActAction

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm)  # 无 memory

    state = AgentState(
        question="test",
        current_obs="obs",
        actions_history=[ReActAction(action="test", params={}, memory="think")],
    )

    # 应该不报错
    result = await agent._observe_node(state)
    assert result == {}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/test_react_agent_memory.py::test_observe_node_records_to_memory -v`
Expected: FAIL - `AssertionError: memory.add.called is False`

**Step 3: Write minimal implementation**

```python
# src/ai_agent/agents/react/graph.py
# 修改 _observe_node 方法

async def _observe_node(self, state: AgentState) -> Dict[str, Any]:
    """Observe 节点：处理观察结果，准备下一轮"""
    # 记录到 Memory（如果有）
    if self._memory and state.actions_history:
        from ...memory import MemoryRecord

        last_action = state.actions_history[-1]

        await self._memory.add(MemoryRecord(
            observation={"result": state.current_obs},
            action={
                "name": last_action.action,
                "params": last_action.params,
            },
            thinking=last_action.memory,
        ))

    return {}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/test_react_agent_memory.py::test_observe_node_records_to_memory -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/agents/react/graph.py tests/unit/agents/test_react_agent_memory.py
git commit -m "feat(react): record observations to memory in _observe_node"
```

---

## Task 4: 在 stream() 方法中支持 Memory

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py:260-444`
- Modify: `tests/unit/agents/test_react_agent_memory.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/test_react_agent_memory.py

@pytest.mark.asyncio
async def test_stream_uses_memory():
    """测试 stream 方法使用 memory"""
    from ai_agent.agents.react import ReActAgent, AgentEventType
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()

    # 第一次返回工具调用，第二次返回 finish
    responses = [
        MagicMock(content='{"action": "echo", "params": {}, "memory": "calling echo"}'),
        MagicMock(content='{"action": "finish", "params": {"answer": "done"}, "memory": "completed"}'),
    ]
    mock_llm.ainvoke = AsyncMock(side_effect=responses)

    mock_tool = MagicMock()
    mock_tool.name = "echo"
    mock_tool.ainvoke = AsyncMock(return_value="Echo result")

    memory = CompressedMemory(mock_llm, max_memory=10, keep_recent=3)
    agent = ReActAgent(mock_llm, tools=[mock_tool], memory=memory)

    events = []
    async for event in agent.stream("test message"):
        events.append(event)

    # 验证 memory 被使用
    assert memory.record_count > 0 or memory.has_summary


@pytest.mark.asyncio
async def test_stream_injects_memory_to_prompt():
    """测试 stream 方法将 memory 注入 prompt"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()

    # 创建带预置内容的 memory
    memory = MagicMock()
    memory.as_text = MagicMock(return_value="[Pre-existing memory content]")
    memory.add = AsyncMock()

    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}')
    )

    agent = ReActAgent(mock_llm, memory=memory)

    events = []
    async for event in agent.stream("test"):
        events.append(event)

    # 验证 prompt 包含 memory 内容
    call_args = mock_llm.ainvoke.call_args
    prompt = call_args[0][0].content

    assert "[Pre-existing memory content]" in prompt
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/test_react_agent_memory.py::test_stream_injects_memory_to_prompt -v`
Expected: FAIL - `AssertionError: '[Pre-existing memory content]' not found`

**Step 3: Write minimal implementation**

```python
# src/ai_agent/agents/react/graph.py
# 修改 stream() 方法中的 prompt 格式化部分

# 在 stream() 方法中找到格式化 prompt 的地方（约第301-306行）
# 将 memory="None" 改为动态获取

# ========== THINK 阶段 ==========
# ... 省略 ...

# 构建工具描述
action_space = self._build_action_space()

# 获取 memory 文本（修改这里）
memory_text = self._memory.as_text() if self._memory else "None"

# 格式化 Prompt
formatted_prompt = self.prompt.format(
    original_question=state.question,
    action_space=action_space,
    memory=memory_text,  # 修改这里
    obs=state.current_obs or "No observation yet.",
)

# ... 省略 ...

# 在 OBSERVE 阶段后添加 memory 记录
# 在 yield OBSERVE 事件后，continue 之前添加：

# 记录到 Memory
if self._memory:
    from ...memory import MemoryRecord
    await self._memory.add(MemoryRecord(
        observation={"result": state.current_obs},
        action={"name": action.action, "params": action.params},
        thinking=action.memory,
    ))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/test_react_agent_memory.py::test_stream_injects_memory_to_prompt -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ai_agent/agents/react/graph.py tests/unit/agents/test_react_agent_memory.py
git commit -m "feat(react): add memory support to stream method"
```

---

## Task 5: 在 run() 方法中支持 Memory

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py:227-253`
- Modify: `tests/unit/agents/test_react_agent_memory.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/test_react_agent_memory.py

@pytest.mark.asyncio
async def test_run_creates_memory_when_enabled():
    """测试 run 方法在启用时创建 memory"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "42"}, "memory": "done"}')
    )

    agent = ReActAgent(mock_llm, create_memory=True)

    result = await agent.run("What is the answer?")

    # 验证 memory 被创建并使用
    assert agent._memory is not None


@pytest.mark.asyncio
async def test_run_with_external_memory():
    """测试 run 方法使用外部传入的 memory"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}')
    )

    external_memory = CompressedMemory(mock_llm)
    external_memory._summary = "Previous context"

    agent = ReActAgent(mock_llm, memory=external_memory)

    await agent.run("test question")

    # 验证使用了外部 memory
    assert agent._memory is external_memory
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/test_react_agent_memory.py::test_run_creates_memory_when_enabled -v`
Expected: 可能 PASS（因为 Task 1 已实现）

**Step 3: Write minimal implementation**

```python
# src/ai_agent/agents/react/graph.py
# run() 方法不需要额外修改，因为 memory 已在 __init__ 中初始化
# 确保使用 LangGraph 的 ainvoke 时 memory 被正确使用
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/test_react_agent_memory.py::test_run_creates_memory_when_enabled -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/agents/test_react_agent_memory.py
git commit -m "test(react): add tests for run method memory support"
```

---

## Task 6: 集成测试 - 验证 Memory 完整流程

**Files:**
- Create: `tests/integration/test_memory_integration.py`

**Step 1: Write the integration test**

```python
# tests/integration/test_memory_integration.py
"""Memory 集成测试 - 验证真实流程中的 memory 注入"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List, Dict, Any
from datetime import datetime


class LLMCallCapture:
    """捕获 LLM 调用的 prompt 内容"""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def capture(self, messages: List) -> None:
        """记录每次 LLM 调用"""
        self.calls.append({
            "messages": [m.content for m in messages],
            "timestamp": datetime.now(),
        })


@pytest.fixture
def llm_capture():
    return LLMCallCapture()


@pytest.fixture
def mock_tool():
    """创建模拟工具"""
    tool = MagicMock()
    tool.name = "search"
    tool.description = "Search for information"
    tool.ainvoke = AsyncMock(return_value="Search results: ...")
    return tool


def extract_memory_section(prompt: str) -> str:
    """从 prompt 中提取 memory 部分"""
    import re
    match = re.search(r'==== Memory ====\n(.*?)\n==== Current Observation ====', prompt, re.DOTALL)
    if match:
        return match.group(1).strip()
    return "NOT FOUND"


@pytest.mark.asyncio
async def test_memory_integration_first_step_is_none(llm_capture, mock_tool):
    """集成测试：第一步 memory 应该是 None"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.llm.client import create_llm_client

    # 创建带捕获的 mock LLM
    mock_llm = MagicMock()

    async def capture_and_respond(messages):
        llm_capture.capture(messages)
        return MagicMock(content='{"action": "finish", "params": {"answer": "done"}, "memory": "completed"}')

    mock_llm.ainvoke = capture_and_respond

    agent = ReActAgent(mock_llm, tools=[mock_tool], create_memory=True)

    await agent.run("Test question")

    # 分析第一次 LLM 调用
    assert len(llm_capture.calls) >= 1

    first_prompt = llm_capture.calls[0]["messages"][0]
    memory_section = extract_memory_section(first_prompt)

    assert memory_section == "None", f"First step memory should be 'None', got: {memory_section}"


@pytest.mark.asyncio
async def test_memory_integration_records_observations(llm_capture, mock_tool):
    """集成测试：memory 记录观察结果"""
    from ai_agent.agents.react import ReActAgent

    call_count = [0]

    async def capture_and_respond(messages):
        llm_capture.capture(messages)
        call_count[0] += 1

        if call_count[0] == 1:
            # 第一次调用工具
            return MagicMock(content='{"action": "search", "params": {"q": "test"}, "memory": "searching"}')
        else:
            # 第二次完成
            return MagicMock(content='{"action": "finish", "params": {"answer": "found"}, "memory": "done"}')

    mock_llm = MagicMock()
    mock_llm.ainvoke = capture_and_respond

    agent = ReActAgent(mock_llm, tools=[mock_tool], create_memory=True)

    await agent.run("Test question")

    # 验证 memory 有记录
    assert agent._memory.record_count > 0, "Memory should have records after multi-step execution"


@pytest.mark.asyncio
async def test_memory_integration_second_step_has_content(llm_capture, mock_tool):
    """集成测试：第二步 memory 应该包含之前的内容"""
    from ai_agent.agents.react import ReActAgent

    call_count = [0]

    async def capture_and_respond(messages):
        llm_capture.capture(messages)
        call_count[0] += 1

        if call_count[0] == 1:
            return MagicMock(content='{"action": "search", "params": {"q": "test"}, "memory": "searching"}')
        else:
            return MagicMock(content='{"action": "finish", "params": {"answer": "found"}, "memory": "done"}')

    mock_llm = MagicMock()
    mock_llm.ainvoke = capture_and_respond

    agent = ReActAgent(mock_llm, tools=[mock_tool], create_memory=True)

    await agent.run("Test question")

    # 分析第二次 LLM 调用
    assert len(llm_capture.calls) >= 2

    second_prompt = llm_capture.calls[1]["messages"][0]
    memory_section = extract_memory_section(second_prompt)

    # 第二步 memory 不应该是 None
    assert memory_section != "None", f"Second step memory should not be 'None', got: {memory_section}"
    # 应该包含 "Recent steps" 或类似标记
    assert "Recent" in memory_section or "action" in memory_section.lower(), \
        f"Memory should contain recent steps info: {memory_section}"


@pytest.mark.asyncio
async def test_memory_integration_compression_trigger():
    """集成测试：达到阈值时触发压缩"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()

    call_count = [0]

    async def respond_with_tool_call(messages):
        call_count[0] += 1
        if call_count[0] < 12:
            return MagicMock(content='{"action": "search", "params": {}, "memory": "step ' + str(call_count[0]) + '"}')
        else:
            return MagicMock(content='{"action": "finish", "params": {"answer": "done"}, "memory": "completed"}')

    mock_llm.ainvoke = respond_with_tool_call

    # 使用低阈值便于测试
    memory = CompressedMemory(mock_llm, max_memory=5, keep_recent=2)

    mock_tool = MagicMock()
    mock_tool.name = "search"
    mock_tool.ainvoke = AsyncMock(return_value="result")

    agent = ReActAgent(mock_llm, tools=[mock_tool], memory=memory, max_steps=15)

    await agent.run("Long task")

    # 验证压缩被触发
    assert memory.has_summary, "Memory should have summary after compression"
    assert memory.record_count <= 2, f"Records should be <= 2 after compression, got: {memory.record_count}"


@pytest.mark.asyncio
async def test_memory_detailed_prompt_analysis():
    """详细分析每次 LLM 调用的 prompt 内容"""
    from ai_agent.agents.react import ReActAgent

    calls_log = []

    mock_llm = MagicMock()

    async def log_and_respond(messages):
        prompt = messages[0].content
        memory = extract_memory_section(prompt)

        calls_log.append({
            "call_number": len(calls_log) + 1,
            "memory_content": memory,
            "memory_length": len(memory),
        })

        if len(calls_log) < 3:
            return MagicMock(content='{"action": "search", "params": {}, "memory": "thinking..."}')
        else:
            return MagicMock(content='{"action": "finish", "params": {"answer": "done"}, "memory": "done"}')

    mock_llm.ainvoke = log_and_respond

    mock_tool = MagicMock()
    mock_tool.name = "search"
    mock_tool.ainvoke = AsyncMock(return_value="search result")

    agent = ReActAgent(mock_llm, tools=[mock_tool], create_memory=True)

    await agent.run("Multi-step task")

    # 输出详细分析
    print("\n" + "=" * 60)
    print("MEMORY INTEGRATION ANALYSIS")
    print("=" * 60)

    for call in calls_log:
        print(f"\n--- LLM Call #{call['call_number']} ---")
        print(f"Memory length: {call['memory_length']} chars")
        print(f"Memory content:\n{call['memory_content'][:500]}...")
        print("-" * 40)

    # 验证：第一次是 None，后续有内容
    assert calls_log[0]["memory_content"] == "None"
    for call in calls_log[1:]:
        assert call["memory_content"] != "None"
```

**Step 2: Run integration tests**

Run: `pytest tests/integration/test_memory_integration.py -v -s`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_memory_integration.py
git commit -m "test(integration): add comprehensive memory integration tests"
```

---

## Task 7: 真实 API 集成测试（可选）

**Files:**
- Create: `tests/integration/test_memory_real_api.py`

**Step 1: Write real API test**

```python
# tests/integration/test_memory_real_api.py
"""真实 API 测试 - 需要 API Key"""

import pytest
import os


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") == "test-api-key",
    reason="Requires real OPENAI_API_KEY"
)
@pytest.mark.asyncio
async def test_memory_with_real_llm():
    """使用真实 LLM 测试 memory 功能"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.llm.client import create_llm_client
    from ai_agent.memory import CompressedMemory
    from ai_agent.tools.web import GoogleSearchTool

    llm = create_llm_client()
    memory = CompressedMemory(llm, max_memory=5, keep_recent=2)

    # 创建简单的 mock 工具
    from unittest.mock import MagicMock, AsyncMock

    mock_tool = MagicMock()
    mock_tool.name = "echo"
    mock_tool.description = "Echo back the input"
    mock_tool.ainvoke = AsyncMock(return_value="Echo: test")

    agent = ReActAgent(llm, tools=[mock_tool], memory=memory, max_steps=5)

    result = await agent.run("Please echo 'hello' and then finish")

    print(f"\nResult: {result}")
    print(f"Memory records: {memory.record_count}")
    print(f"Memory has summary: {memory.has_summary}")
    print(f"\nMemory text:\n{memory.as_text()}")

    assert result is not None
```

**Step 2: Run real API test**

Run: `pytest tests/integration/test_memory_real_api.py -v -m integration`
Expected: PASS（需要真实 API Key）

**Step 3: Commit**

```bash
git add tests/integration/test_memory_real_api.py
git commit -m "test(integration): add real API memory test"
```

---

## Task 8: 更新导出和文档

**Files:**
- Modify: `src/ai_agent/agents/react/__init__.py`
- Modify: `src/ai_agent/__init__.py`

**Step 1: Update exports**

```python
# src/ai_agent/agents/react/__init__.py
"""ReAct Agent 模块"""

from .graph import ReActAgent, ReActAction, AgentState
from .events import AgentEvent, AgentEventType

__all__ = [
    "ReActAgent",
    "ReActAction",
    "AgentState",
    "AgentEvent",
    "AgentEventType",
]
```

**Step 2: Verify all tests pass**

Run: `pytest tests/unit/agents/test_react_agent_memory.py tests/integration/test_memory_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/ai_agent/agents/react/__init__.py
git commit -m "chore: update react module exports"
```

---

## 验证清单

| 检查项 | 测试命令 |
|-------|---------|
| 单元测试 | `pytest tests/unit/agents/test_react_agent_memory.py -v` |
| 集成测试 | `pytest tests/integration/test_memory_integration.py -v` |
| Memory 单元测试 | `pytest tests/unit/memory/ -v` |
| 全量测试 | `pytest tests/ -v --ignore=tests/integration/test_memory_real_api.py` |
| 覆盖率 | `pytest tests/unit/agents/test_react_agent_memory.py --cov=ai_agent.agents.react --cov-report=term-missing` |

---

## 质量检验标准

1. **单元测试覆盖率 > 90%** - 新增代码路径
2. **所有测试通过** - 无跳过、无失败
3. **集成测试验证真实流程** - prompt 中 memory 注入正确
4. **向后兼容** - 不影响现有 ReActAgent 用法
5. **代码风格一致** - 遵循现有代码规范
