"""ReAct Agent 集成测试（原生 tool_calling 模式）

验证重构后的 Agent 端到端流程：
- Mock LLM 返回 tool_calls → Agent 正确执行工具 → 返回最终结果
- 多步工具调用场景
- max_steps 限制
- stream 产生正确的事件序列
- 未知工具错误处理
"""

import json

import pytest
from unittest.mock import MagicMock, AsyncMock

from langchain_core.messages import AIMessage, ToolMessage


def _make_tool_call_response(tool_name: str, tool_id: str, args: dict) -> AIMessage:
    """构造包含 tool_calls 的 AI 响应"""
    return AIMessage(
        content="",
        tool_calls=[{"name": tool_name, "id": tool_id, "args": args}],
    )


def _make_text_response(text: str) -> AIMessage:
    """构造纯文本 AI 响应"""
    return AIMessage(content=text)


class FakeTool:
    """模拟 BaseAgentTool，用于集成测试"""

    def __init__(self, name: str, result: str = "mock result"):
        self._name = name
        self._result = result
        self.call_count = 0
        self.last_params = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Fake tool: {self._name}"

    class _FakeSchema:
        def __init__(self, **kwargs):
            self._data = kwargs

    @property
    def params_schema(self):
        return self._FakeSchema

    async def run(self, params):
        self.call_count += 1
        self.last_params = params
        return MagicMock(data=self._result)

    def to_langchain_tool(self):
        """返回 LangChain 兼容的工具"""
        fake_lc = MagicMock()
        fake_lc.name = self._name
        fake_lc.description = self.description
        return fake_lc


class TestReActIntegrationSingleStep:
    """单步工具调用集成测试"""

    @pytest.mark.asyncio
    async def test_single_tool_call_then_done(self):
        """LLM 返回一个 tool_call → 执行 → LLM 返回最终文本"""
        from ai_agent.agents.react import ReActAgent

        echo_tool = FakeTool("echo", result="Echo: hello")

        responses = [
            _make_tool_call_response("echo", "call_1", {"text": "hello"}),
            _make_text_response("The echo tool returned: Echo: hello"),
        ]

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        response_index = 0

        async def mock_ainvoke(messages):
            nonlocal response_index
            if response_index < len(responses):
                resp = responses[response_index]
                response_index += 1
                return resp
            return _make_text_response("Done")

        mock_llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)

        agent = ReActAgent(llm=mock_llm, tools=[echo_tool], max_steps=10)

        result = await agent.run("Test the echo tool")
        assert result == "The echo tool returned: Echo: hello"


class TestReActIntegrationMultiStep:
    """多步工具调用集成测试"""

    @pytest.mark.asyncio
    async def test_multi_step_tool_calls(self):
        """多轮工具调用：search → read → 完成"""
        from ai_agent.agents.react import ReActAgent

        search_tool = FakeTool("web_search", result="Found: Python docs")
        read_tool = FakeTool("read", result="Python is a programming language")

        responses = [
            _make_tool_call_response("web_search", "call_1", {"query": "Python"}),
            _make_tool_call_response("read", "call_2", {"path": "/docs/python"}),
            _make_text_response("Based on my research, Python is a programming language."),
        ]

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        response_index = 0

        async def mock_ainvoke(messages):
            nonlocal response_index
            if response_index < len(responses):
                resp = responses[response_index]
                response_index += 1
                return resp
            return _make_text_response("Done")

        mock_llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)

        agent = ReActAgent(
            llm=mock_llm,
            tools=[search_tool, read_tool],
            max_steps=10,
        )

        result = await agent.run("Tell me about Python")
        assert "Python" in result
        assert search_tool.call_count == 1
        assert read_tool.call_count == 1


class TestReActIntegrationMaxSteps:
    """max_steps 限制测试"""

    @pytest.mark.asyncio
    async def test_max_steps_limits_iterations(self):
        """达到 max_steps 时强制结束"""
        from ai_agent.agents.react import ReActAgent

        echo_tool = FakeTool("echo", result="ok")

        call_counter = [0]

        def always_tool_call():
            call_counter[0] += 1
            return _make_tool_call_response("echo", f"call_{call_counter[0]}", {"text": "loop"})

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(side_effect=lambda msgs: always_tool_call())

        agent = ReActAgent(llm=mock_llm, tools=[echo_tool], max_steps=3)

        result = await agent.run("Infinite loop test")

        assert result is not None
        # 工具最多被调用 max_steps 次
        assert echo_tool.call_count <= 3


class TestReActIntegrationStream:
    """stream() 事件序列测试"""

    @pytest.mark.asyncio
    async def test_stream_produces_done_event(self):
        """stream 最终产生 DONE 事件"""
        from ai_agent.agents.react import ReActAgent
        from ai_agent.types.agents import AgentEventType

        echo_tool = FakeTool("echo", result="echo result")

        responses = [
            _make_tool_call_response("echo", "call_1", {"text": "test"}),
            _make_text_response("Final answer"),
        ]

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        response_index = 0

        async def mock_ainvoke(messages):
            nonlocal response_index
            if response_index < len(responses):
                resp = responses[response_index]
                response_index += 1
                return resp
            return _make_text_response("Done")

        mock_llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)

        agent = ReActAgent(llm=mock_llm, tools=[echo_tool], max_steps=10)

        events = []
        async for event in agent.stream("Test streaming"):
            events.append(event)

        # stream 最后一个事件必须是 DONE
        assert events[-1].type == AgentEventType.DONE
        assert events[-1].data.get("answer") is not None

    @pytest.mark.asyncio
    async def test_stream_event_types_are_valid(self):
        """stream 产生的事件类型都在新枚举中"""
        from ai_agent.agents.react import ReActAgent
        from ai_agent.types.agents import AgentEventType

        echo_tool = FakeTool("echo", result="ok")

        responses = [
            _make_tool_call_response("echo", "call_1", {"text": "test"}),
            _make_text_response("Done"),
        ]

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        response_index = 0

        async def mock_ainvoke(messages):
            nonlocal response_index
            if response_index < len(responses):
                resp = responses[response_index]
                response_index += 1
                return resp
            return _make_text_response("Done")

        mock_llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)

        agent = ReActAgent(llm=mock_llm, tools=[echo_tool], max_steps=10)

        valid_types = {
            AgentEventType.TEXT,
            AgentEventType.TOOL_CALL,
            AgentEventType.TOOL_RESULT,
            AgentEventType.THINKING,
            AgentEventType.ERROR,
            AgentEventType.DONE,
        }

        async for event in agent.stream("Test"):
            assert event.type in valid_types, f"Invalid event type: {event.type}"


class TestReActIntegrationError:
    """错误处理集成测试"""

    @pytest.mark.asyncio
    async def test_unknown_tool_error(self):
        """LLM 调用不存在的工具时，返回错误信息给 LLM"""
        from ai_agent.agents.react import ReActAgent

        responses = [
            _make_tool_call_response("nonexistent_tool", "call_1", {}),
            _make_text_response("I couldn't find that tool, but here's my answer."),
        ]

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        response_index = 0

        async def mock_ainvoke(messages):
            nonlocal response_index
            if response_index < len(responses):
                resp = responses[response_index]
                response_index += 1
                return resp
            return _make_text_response("Done")

        mock_llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)

        agent = ReActAgent(
            llm=mock_llm,
            tools=[],
            max_steps=10,
        )

        result = await agent.run("Use nonexistent tool")
        assert result is not None
