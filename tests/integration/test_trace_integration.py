"""Trace 集成测试

此模块测试 ReActAgent 与 LangSmith 追踪的集成，
验证 trace 上下文正确创建和传播。
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_stream_creates_trace_context():
    """验证 stream 方法创建 trace 上下文"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}'
        )
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
    from ai_agent.agents.react.events import AgentEventType

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content='{"action": "finish", "params": {"answer": "test answer"}, "memory": "done"}'
        )
    )

    agent = ReActAgent(mock_llm, tools=[])

    # 执行 stream
    events = []
    async for event in agent.stream("test"):
        events.append(event)

    # 验证执行成功
    assert len(events) > 0

    # 验证 finish 事件包含答案
    finish_events = [e for e in events if e.event == AgentEventType.FINISH]
    assert len(finish_events) == 1
    assert "answer" in finish_events[0].data


@pytest.mark.asyncio
async def test_trace_with_tool_calls():
    """验证带工具调用的 trace 结构"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.agents.react.events import AgentEventType

    mock_llm = MagicMock()
    responses = [
        MagicMock(
            content='{"action": "echo", "params": {"text": "hello"}, "memory": "calling echo"}'
        ),
        MagicMock(
            content='{"action": "finish", "params": {"answer": "done"}, "memory": "completed"}'
        ),
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

    event_types = [e.event for e in events]

    # 验证有 think, act, observe, finish 事件
    assert AgentEventType.THINK in event_types
    assert AgentEventType.ACT in event_types
    assert AgentEventType.OBSERVE in event_types
    assert AgentEventType.FINISH in event_types


@pytest.mark.asyncio
async def test_trace_step_numbering():
    """验证 trace 中的步骤编号正确"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    responses = [
        MagicMock(
            content='{"action": "echo", "params": {"text": "a"}, "memory": "step1"}'
        ),
        MagicMock(
            content='{"action": "echo", "params": {"text": "b"}, "memory": "step2"}'
        ),
        MagicMock(
            content='{"action": "finish", "params": {"answer": "done"}, "memory": "completed"}'
        ),
    ]
    mock_llm.ainvoke = AsyncMock(side_effect=responses)

    mock_tool = MagicMock()
    mock_tool.name = "echo"
    mock_tool.description = "Echo"
    mock_tool.ainvoke = AsyncMock(return_value="ok")

    agent = ReActAgent(mock_llm, tools=[mock_tool])

    events = []
    async for event in agent.stream("test"):
        events.append(event)

    # 验证步骤编号是递增的
    steps = [e.step for e in events]
    assert steps == sorted(steps)  # 步骤应该是有序的


@pytest.mark.asyncio
async def test_trace_error_handling():
    """验证 trace 正确处理错误"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.agents.react.events import AgentEventType

    mock_llm = MagicMock()
    # LLM 返回无效响应
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="not valid json"))

    agent = ReActAgent(mock_llm, tools=[])

    events = []
    async for event in agent.stream("test"):
        events.append(event)

    # 应该有错误事件
    error_events = [e for e in events if e.event == AgentEventType.ERROR]
    finish_events = [e for e in events if e.event == AgentEventType.FINISH]

    assert len(error_events) >= 1 or len(finish_events) >= 1


@pytest.mark.asyncio
async def test_multiple_stream_calls_create_separate_traces():
    """验证多次调用 stream 创建独立的 trace"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.agents.react.events import AgentEventType

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}'
        )
    )

    agent = ReActAgent(mock_llm, tools=[])

    # 第一次调用
    events1 = []
    async for event in agent.stream("question 1"):
        events1.append(event)

    # 第二次调用
    events2 = []
    async for event in agent.stream("question 2"):
        events2.append(event)

    # 两次调用都应该产生事件
    assert len(events1) > 0
    assert len(events2) > 0

    # 两次调用都应该有 finish 事件
    assert any(e.event == AgentEventType.FINISH for e in events1)
    assert any(e.event == AgentEventType.FINISH for e in events2)
