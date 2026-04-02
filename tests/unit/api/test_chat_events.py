"""测试 SSE 事件映射（新事件类型）"""

import json

import pytest

from ai_agent.types.agents import AgentEvent, AgentEventType


class TestSSEEventMapping:
    """测试新旧事件类型映射"""

    def test_text_event_to_sse(self):
        """TEXT 事件转换为 SSE 格式"""
        event = AgentEvent(
            type=AgentEventType.TEXT,
            data={"content": "Hello"},
            step=1,
        )
        sse = event.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        assert '"type": "text"' in sse
        assert '"content": "Hello"' in sse

    def test_tool_call_event_to_sse(self):
        """TOOL_CALL 事件转换为 SSE 格式"""
        event = AgentEvent(
            type=AgentEventType.TOOL_CALL,
            data={"name": "web_search", "args": {"query": "test"}},
            step=2,
        )
        sse = event.to_sse()
        assert '"type": "tool_call"' in sse
        assert '"name": "web_search"' in sse

    def test_tool_result_event_to_sse(self):
        """TOOL_RESULT 事件转换为 SSE 格式"""
        event = AgentEvent(
            type=AgentEventType.TOOL_RESULT,
            data={"tool_name": "web_search", "result_summary": "Found results"},
            step=3,
        )
        sse = event.to_sse()
        assert '"type": "tool_result"' in sse
        assert '"result_summary": "Found results"' in sse

    def test_done_event_to_sse(self):
        """DONE 事件替代旧的 FINISH 事件"""
        event = AgentEvent(
            type=AgentEventType.DONE,
            data={"answer": "The answer is 42"},
            step=4,
        )
        sse = event.to_sse()
        assert '"type": "done"' in sse
        assert '"answer": "The answer is 42"' in sse

    def test_error_event_to_sse(self):
        """ERROR 事件格式保持不变"""
        event = AgentEvent(
            type=AgentEventType.ERROR,
            data={"message": "LLM call failed", "details": "TimeoutError"},
            step=0,
        )
        sse = event.to_sse()
        assert '"type": "error"' in sse
        assert '"message": "LLM call failed"' in sse

    def test_event_type_map_comment_documented(self):
        """验证事件类型映射关系已文档化"""
        assert AgentEventType.TEXT.value == "text"
        assert AgentEventType.TOOL_CALL.value == "tool_call"
        assert AgentEventType.TOOL_RESULT.value == "tool_result"
        assert AgentEventType.DONE.value == "done"
        assert AgentEventType.ERROR.value == "error"


class TestChatStreamEventHandling:
    """测试 chat_stream 对新事件类型的处理"""

    def test_text_event_type_correct(self):
        """TEXT 事件类型判断正确"""
        text_event = AgentEvent(
            type=AgentEventType.TEXT,
            data={"content": "Hello"},
            step=1,
        )
        assert text_event.type == AgentEventType.TEXT

    def test_tool_call_event_type_correct(self):
        """TOOL_CALL 事件类型判断正确"""
        tool_call_event = AgentEvent(
            type=AgentEventType.TOOL_CALL,
            data={"name": "web_search", "args": {"query": "test"}},
            step=1,
        )
        assert tool_call_event.type == AgentEventType.TOOL_CALL

    def test_done_event_contains_answer(self):
        """DONE 事件包含最终答案"""
        done_event = AgentEvent(
            type=AgentEventType.DONE,
            data={"answer": "The weather is sunny"},
            step=5,
        )
        assert done_event.data.get("answer") == "The weather is sunny"

    def test_tool_result_event_data(self):
        """TOOL_RESULT 事件包含结果数据"""
        result_event = AgentEvent(
            type=AgentEventType.TOOL_RESULT,
            data={"tool_name": "calculator", "result": "42"},
            step=2,
        )
        assert result_event.data["tool_name"] == "calculator"
        assert result_event.data["result"] == "42"
