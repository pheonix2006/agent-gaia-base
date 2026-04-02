"""AgentEvent 事件模型测试（tool_calling 版本）"""

import json
from datetime import datetime

import pytest

from ai_agent.agents.react.events import AgentEvent, AgentEventType


class TestAgentEventType:
    """测试 AgentEventType 枚举"""

    def test_new_event_types_exist(self):
        """测试新的 tool_calling 事件类型存在"""
        assert AgentEventType.TEXT == "text"
        assert AgentEventType.TOOL_CALL == "tool_call"
        assert AgentEventType.TOOL_RESULT == "tool_result"
        assert AgentEventType.THINKING == "thinking"
        assert AgentEventType.ERROR == "error"
        assert AgentEventType.DONE == "done"

    def test_old_event_types_removed(self):
        """测试旧的 JSON 解析模式事件类型已移除"""
        assert not hasattr(AgentEventType, "THINK")
        assert not hasattr(AgentEventType, "ACT")
        assert not hasattr(AgentEventType, "OBSERVE")
        assert not hasattr(AgentEventType, "FINISH")

    def test_all_values_are_lowercase_strings(self):
        """测试所有枚举值是小写字符串"""
        for t in AgentEventType:
            assert isinstance(t.value, str)
            assert t.value.islower()


class TestAgentEventCreation:
    """测试 AgentEvent 创建"""

    def test_create_text_event(self):
        """测试创建 TEXT 事件"""
        event = AgentEvent(
            type=AgentEventType.TEXT,
            data={"content": "Hello, I am thinking about..."},
            step=1,
        )
        assert event.type == AgentEventType.TEXT
        assert event.data["content"] == "Hello, I am thinking about..."
        assert event.step == 1
        assert isinstance(event.timestamp, datetime)

    def test_create_tool_call_event(self):
        """测试创建 TOOL_CALL 事件"""
        event = AgentEvent(
            type=AgentEventType.TOOL_CALL,
            data={"tool_name": "search", "arguments": {"query": "test"}},
            step=2,
        )
        assert event.type == AgentEventType.TOOL_CALL
        assert event.data["tool_name"] == "search"
        assert event.data["arguments"]["query"] == "test"

    def test_create_tool_result_event(self):
        """测试创建 TOOL_RESULT 事件"""
        event = AgentEvent(
            type=AgentEventType.TOOL_RESULT,
            data={"tool_name": "search", "result": "Found 3 items"},
            step=3,
        )
        assert event.type == AgentEventType.TOOL_RESULT
        assert event.data["tool_name"] == "search"
        assert event.data["result"] == "Found 3 items"

    def test_create_thinking_event(self):
        """测试创建 THINKING 事件"""
        event = AgentEvent(
            type=AgentEventType.THINKING,
            data={"content": "Analyzing the problem..."},
            step=1,
        )
        assert event.type == AgentEventType.THINKING

    def test_create_error_event(self):
        """测试创建 ERROR 事件"""
        event = AgentEvent(
            type=AgentEventType.ERROR,
            data={"message": "Tool execution failed", "details": "Timeout after 30s"},
            step=4,
        )
        assert event.type == AgentEventType.ERROR
        assert event.data["message"] == "Tool execution failed"

    def test_create_done_event(self):
        """测试创建 DONE 事件"""
        event = AgentEvent(
            type=AgentEventType.DONE,
            data={"answer": "The result is 42"},
            step=5,
        )
        assert event.type == AgentEventType.DONE
        assert event.data["answer"] == "The result is 42"

    def test_timestamp_auto_generated(self):
        """测试时间戳自动生成"""
        before = datetime.now()
        event = AgentEvent(
            type=AgentEventType.TEXT,
            data={"content": "test"},
            step=1,
        )
        after = datetime.now()
        assert before <= event.timestamp <= after

    def test_timestamp_can_be_set(self):
        """测试可以手动设置时间戳"""
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        event = AgentEvent(
            type=AgentEventType.TEXT,
            data={"content": "test"},
            step=1,
            timestamp=custom_time,
        )
        assert event.timestamp == custom_time

    def test_event_field_renamed_to_type(self):
        """测试 event 字段已重命名为 type"""
        event = AgentEvent(
            type=AgentEventType.DONE,
            data={"answer": "done"},
            step=1,
        )
        # Should have 'type' attribute, not 'event'
        assert hasattr(event, "type")
        assert event.type == AgentEventType.DONE

    def test_data_can_be_empty(self):
        """测试 data 可以是空字典"""
        event = AgentEvent(
            type=AgentEventType.TEXT,
            data={},
            step=1,
        )
        assert event.data == {}


class TestAgentEventSerialization:
    """测试 AgentEvent 序列化"""

    def test_to_json_uses_type_field(self):
        """测试 JSON 序列化使用 type 字段名"""
        custom_time = datetime(2024, 1, 15, 10, 30, 0)
        event = AgentEvent(
            type=AgentEventType.TOOL_CALL,
            data={"tool_name": "search", "arguments": {"q": "test"}},
            step=1,
            timestamp=custom_time,
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["type"] == "tool_call"
        assert data["data"]["tool_name"] == "search"
        assert data["step"] == 1
        assert data["timestamp"] == "2024-01-15T10:30:00"
        # Should NOT have "event" key
        assert "event" not in data

    def test_to_json_chinese_content(self):
        """测试 JSON 序列化中文内容"""
        event = AgentEvent(
            type=AgentEventType.DONE,
            data={"answer": "答案是中文"},
            step=1,
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["data"]["answer"] == "答案是中文"

    def test_to_sse_format(self):
        """测试 SSE 格式输出"""
        custom_time = datetime(2024, 1, 15, 10, 30, 0)
        event = AgentEvent(
            type=AgentEventType.THINKING,
            data={"content": "Thinking..."},
            step=1,
            timestamp=custom_time,
        )

        sse_str = event.to_sse()

        assert sse_str.startswith("data: ")
        assert sse_str.endswith("\n\n")

        # 提取并解析 SSE 数据
        json_part = sse_str[6:-2]  # 移除 "data: " 和 "\n\n"
        data = json.loads(json_part)
        assert data["type"] == "thinking"

    def test_to_sse_contains_type_not_event(self):
        """测试 SSE 数据使用 type 字段名而非 event"""
        event = AgentEvent(
            type=AgentEventType.TOOL_RESULT,
            data={"tool_name": "calculator", "result": "42"},
            step=2,
        )

        sse_str = event.to_sse()
        json_part = sse_str[6:-2]
        data = json.loads(json_part)

        assert "type" in data
        assert data["type"] == "tool_result"
        assert "event" not in data

    def test_model_dump(self):
        """测试 Pydantic model_dump 方法"""
        event = AgentEvent(
            type=AgentEventType.ERROR,
            data={"message": "错误", "details": "详情"},
            step=3,
        )

        dump = event.model_dump()

        assert dump["type"] == AgentEventType.ERROR
        assert dump["data"]["message"] == "错误"
        assert dump["step"] == 3
        assert "timestamp" in dump
