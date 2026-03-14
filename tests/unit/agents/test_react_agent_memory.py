# tests/unit/agents/test_react_agent_memory.py

import pytest
from unittest.mock import MagicMock, AsyncMock


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


def test_memory_takes_precedence_over_create_memory():
    """测试 memory 参数优先于 create_memory"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()
    external_memory = MagicMock(spec=CompressedMemory)

    # 同时传入两个参数
    agent = ReActAgent(mock_llm, memory=external_memory, create_memory=True)

    # memory 参数应优先
    assert agent._memory is external_memory


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
    prompt = call_args[0][0][0].content  # [HumanMessage][0].content

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
    prompt = call_args[0][0][0].content

    # 验证 prompt 中 memory 部分是 "None"
    assert "==== Memory ====\nNone" in prompt


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

    # 验证记录内容（根据实际 MemoryRecord 结构）
    assert "result" in record.observation or record.observation == "Observation result"
    assert record.action["name"] == "search" or record.action.get("name") == "search"


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
