"""测试 @traceable 装饰器集成

此模块测试 ReActAgent.stream() 方法的 @traceable 装饰器，
确保 LangSmith 追踪功能正确集成。
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
import inspect
import collections.abc


def test_stream_method_has_traceable_decorator():
    """验证 stream 方法有 @traceable 装饰器"""
    from ai_agent.agents.react import ReActAgent

    # 检查 stream 方法存在
    assert hasattr(ReActAgent, "stream")

    # 检查方法是可调用的
    stream_method = getattr(ReActAgent, "stream")
    assert callable(stream_method)

    # @traceable 装饰器会添加 __wrapped__ 属性
    # 这是 functools.wraps 的标准行为
    assert hasattr(stream_method, "__wrapped__"), "stream 方法应该被装饰器包装"


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
        return_value=MagicMock(
            content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}'
        )
    )

    agent = ReActAgent(mock_llm, tools=[])
    result = agent.stream("test message")

    # 验证是异步生成器
    assert isinstance(result, collections.abc.AsyncGenerator)


@pytest.mark.asyncio
async def test_stream_yields_events():
    """验证 stream yield 正确的事件"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.agents.react.events import AgentEventType

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content='{"action": "finish", "params": {"answer": "test answer"}, "memory": "done"}'
        )
    )

    agent = ReActAgent(mock_llm, tools=[])
    events = []

    async for event in agent.stream("test"):
        events.append(event)

    # 至少有一个 finish 事件
    assert any(e.event == AgentEventType.FINISH for e in events)


@pytest.mark.asyncio
async def test_stream_with_think_act_observe():
    """验证 stream 产生完整的 think-act-observe 事件序列"""
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

    # 验证完整的事件序列
    assert AgentEventType.THINK in event_types
    assert AgentEventType.ACT in event_types
    assert AgentEventType.OBSERVE in event_types
    assert AgentEventType.FINISH in event_types


def test_traceable_decorator_preserves_function_metadata():
    """验证 @traceable 装饰器保留函数元数据"""
    from ai_agent.agents.react import ReActAgent

    stream_method = getattr(ReActAgent, "stream")

    # 验证方法名被保留
    assert stream_method.__name__ == "stream" or "stream" in str(stream_method)
