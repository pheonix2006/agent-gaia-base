# tests/unit/agents/test_react_execution.py
"""ReActAgent 执行方法单元测试（run / stream / helpers）"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ai_agent.agents.react.graph import ReActAgent
from ai_agent.types.agents import AgentContext


@pytest.fixture
def mock_llm():
    """创建 mock LLM"""
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock()
    return llm


@pytest.fixture
def mock_tool():
    """创建 mock BaseAgentTool"""
    from pydantic import BaseModel

    class CalcParams(BaseModel):
        expression: str

    tool = MagicMock()
    tool.name = "calculator"
    tool.description = "Performs calculations"
    tool.params_schema = CalcParams
    tool.to_langchain_tool.return_value = MagicMock(
        name="calculator",
        description="Performs calculations",
    )
    return tool


class TestBuildMessages:
    """测试 _build_messages 消息构建"""

    def test_basic_messages_without_context(self, mock_llm, mock_tool):
        """无 context 时应构建 [SystemMessage, HumanMessage]"""
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        messages = agent._build_messages("Hello", context=None)

        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        assert messages[1].content == "Hello"

    def test_system_message_uses_default_prompt(self, mock_llm, mock_tool):
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        messages = agent._build_messages("test", context=None)
        assert messages[0].content == agent.system_prompt

    def test_system_message_uses_custom_prompt(self, mock_llm, mock_tool):
        agent = ReActAgent(
            mock_llm, tools=[mock_tool], system_prompt="Custom system prompt"
        )
        messages = agent._build_messages("test", context=None)
        assert messages[0].content == "Custom system prompt"

    def test_context_with_memory_text(self, mock_llm, mock_tool):
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        context = AgentContext(memory_text="Previous conversation summary")
        messages = agent._build_messages("test", context=context)
        assert "Previous conversation summary" in messages[0].content
        assert "历史记忆" in messages[0].content or "记忆" in messages[0].content

    def test_context_without_memory_text(self, mock_llm, mock_tool):
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        context = AgentContext()
        messages = agent._build_messages("test", context=context)
        assert messages[0].content == agent.system_prompt

    def test_context_with_system_prompt_override(self, mock_llm, mock_tool):
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        context = AgentContext(system_prompt_override="Override prompt")
        messages = agent._build_messages("test", context=context)
        assert "Override prompt" in messages[0].content


class TestRun:
    """测试 run() 方法"""

    async def test_run_simple_response(self, mock_llm, mock_tool):
        """run() 无工具调用时应返回 LLM 直接回复"""
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="The answer is 42.")
        )
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        result = await agent.run("What is the meaning?")
        assert result == "The answer is 42."

    async def test_run_single_tool_call(self, mock_llm, mock_tool):
        """run() 单次工具调用流程"""
        from ai_agent.types import ToolResult

        tool_call_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "calculator", "args": {"expression": "6*7"}, "id": "tc_1"}
            ],
        )
        final_msg = AIMessage(content="The result is 42.")

        mock_tool.run = AsyncMock(return_value=ToolResult(success=True, data="42"))
        mock_llm.ainvoke = AsyncMock(side_effect=[tool_call_msg, final_msg])
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        result = await agent.run("What is 6*7?")
        assert "42" in result

    async def test_run_multi_step_tool_calls(self, mock_llm, mock_tool):
        """run() 多步工具调用流程"""
        from ai_agent.types import ToolResult

        step1_tc = AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {"expression": "2+2"}, "id": "tc_1"}],
        )
        step2_tc = AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {"expression": "4*3"}, "id": "tc_2"}],
        )
        final = AIMessage(content="The final answer is 12.")

        mock_tool.run = AsyncMock(
            side_effect=[
                ToolResult(success=True, data="4"),
                ToolResult(success=True, data="12"),
            ]
        )
        mock_llm.ainvoke = AsyncMock(side_effect=[step1_tc, step2_tc, final])
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        result = await agent.run("Calculate (2+2)*3")
        assert "12" in result

    async def test_run_respects_max_steps(self, mock_llm, mock_tool):
        """run() 达到 max_steps 时应停止"""
        from ai_agent.types import ToolResult

        def make_tool_call_msg(i: int) -> AIMessage:
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "calculator", "args": {"expression": str(i)}, "id": f"tc_{i}"}
                ],
            )

        responses = [make_tool_call_msg(i) for i in range(50)]
        responses.append(AIMessage(content="done after max steps"))

        mock_tool.run = AsyncMock(return_value=ToolResult(success=True, data="computed"))
        mock_llm.ainvoke = AsyncMock(side_effect=responses)
        agent = ReActAgent(mock_llm, tools=[mock_tool], max_steps=2)
        result = await agent.run("Keep calculating")
        assert isinstance(result, str)

    async def test_run_with_context(self, mock_llm, mock_tool):
        """run() 应传递 context 到 _build_messages"""
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Noted."))
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        context = AgentContext(memory_text="User prefers Chinese")
        result = await agent.run("Hello", context=context)
        assert result == "Noted."
        first_call_args = mock_llm.ainvoke.call_args_list[0]
        messages = first_call_args[0][0]
        assert any("User prefers Chinese" in m.content for m in messages)


class TestTranslateEvent:
    """测试 _translate_event 事件映射"""

    def test_translate_on_chat_model_stream_with_content(self, mock_llm, mock_tool):
        from ai_agent.types.agents import AgentEventType
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        raw_event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": AIMessage(content="Hello world")},
        }
        result = agent._translate_event(raw_event, 0)
        assert result is not None
        assert result.type == AgentEventType.TEXT
        assert result.data["content"] == "Hello world"
        assert result.step == 0

    def test_translate_on_chat_model_stream_with_tool_call_chunks(self, mock_llm, mock_tool):
        from ai_agent.types.agents import AgentEventType
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        raw_event = {
            "event": "on_chat_model_stream",
            "data": {
                "chunk": AIMessage(
                    content="",
                    tool_call_chunks=[{"name": "calculator", "args": '{"expression": "1+1"}'}],
                ),
            },
        }
        result = agent._translate_event(raw_event, 1)
        assert result is not None
        assert result.type == AgentEventType.TOOL_CALL
        assert result.data["name"] == "calculator"
        assert result.step == 1

    def test_translate_on_tool_start(self, mock_llm, mock_tool):
        from ai_agent.types.agents import AgentEventType
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        raw_event = {
            "event": "on_tool_start",
            "data": {"name": "calculator", "input": {"expression": "2+2"}},
        }
        result = agent._translate_event(raw_event, 2)
        assert result is not None
        assert result.type == AgentEventType.TOOL_CALL
        assert result.data["name"] == "calculator"
        assert result.step == 2

    def test_translate_on_tool_end(self, mock_llm, mock_tool):
        from ai_agent.types.agents import AgentEventType
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        raw_event = {
            "event": "on_tool_end",
            "data": {"output": "42"},
        }
        result = agent._translate_event(raw_event, 2)
        assert result is not None
        assert result.type == AgentEventType.TOOL_RESULT
        assert result.data["content"] == "42"

    def test_translate_unrecognized_event_returns_none(self, mock_llm, mock_tool):
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        raw_event = {"event": "on_chain_start", "data": {}}
        result = agent._translate_event(raw_event, 0)
        assert result is None

    def test_translate_on_chat_model_stream_empty_content_returns_none(self, mock_llm, mock_tool):
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        raw_event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": AIMessage(content="")},
        }
        result = agent._translate_event(raw_event, 0)
        assert result is None


class TestStream:
    """测试 stream() 方法"""

    async def test_stream_yields_events(self, mock_llm, mock_tool):
        from ai_agent.types.agents import AgentEventType
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        events_sequence = [
            {"event": "on_chat_model_stream", "data": {"chunk": AIMessage(content="Let me think")}},
            {"event": "on_chat_model_stream", "data": {"chunk": AIMessage(content="")}},
            {"event": "on_tool_start", "data": {"name": "calculator", "input": {"expression": "1+1"}}},
            {"event": "on_tool_end", "data": {"output": "2"}},
            {"event": "on_chat_model_stream", "data": {"chunk": AIMessage(content="The answer is 2.")}},
        ]

        async def mock_astream_events(*args, **kwargs):
            for event in events_sequence:
                yield event

        mock_graph = MagicMock()
        mock_graph.astream_events = mock_astream_events
        agent._graph = mock_graph

        collected_events = []
        async for event in agent.stream("What is 1+1?"):
            collected_events.append(event)

        assert len(collected_events) >= 3
        event_types = [e.type for e in collected_events]
        assert AgentEventType.TEXT in event_types
        assert AgentEventType.TOOL_CALL in event_types
        assert AgentEventType.TOOL_RESULT in event_types

    async def test_stream_filters_none_events(self, mock_llm, mock_tool):
        from ai_agent.types.agents import AgentEventType
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        events_sequence = [
            {"event": "on_chain_start", "data": {}},
            {"event": "on_chat_model_stream", "data": {"chunk": AIMessage(content="Hello")}},
            {"event": "on_chain_end", "data": {}},
        ]

        async def mock_astream_events(*args, **kwargs):
            for event in events_sequence:
                yield event

        mock_graph = MagicMock()
        mock_graph.astream_events = mock_astream_events
        agent._graph = mock_graph

        collected = []
        async for event in agent.stream("test"):
            collected.append(event)

        assert len(collected) == 2  # 1 TEXT + 1 DONE
        assert collected[0].type == AgentEventType.TEXT

    async def test_stream_with_context(self, mock_llm, mock_tool):
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        events_sequence = [
            {"event": "on_chat_model_stream", "data": {"chunk": AIMessage(content="Response")}},
        ]

        async def mock_astream_events(*args, **kwargs):
            for event in events_sequence:
                yield event

        mock_graph = MagicMock()
        mock_graph.astream_events = mock_astream_events
        agent._graph = mock_graph

        context = AgentContext(memory_text="User context here")
        collected = []
        async for event in agent.stream("test", context=context):
            collected.append(event)
        assert len(collected) >= 1


class TestGetGraph:
    """测试 get_graph()"""

    def test_get_graph_returns_compiled_graph(self, mock_llm, mock_tool):
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        graph = agent.get_graph()
        assert graph is not None
        assert graph is agent._graph
