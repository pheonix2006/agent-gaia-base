# tests/unit/agents/react/test_events.py
"""AgentEvent 事件模型测试"""

import pytest
import json
from datetime import datetime

from ai_agent.agents.react.events import AgentEvent, AgentEventType


class TestAgentEventType:
    """测试 AgentEventType 枚举"""

    def test_event_types_exist(self):
        """测试所有事件类型存在"""
        assert AgentEventType.THINK == "think"
        assert AgentEventType.ACT == "act"
        assert AgentEventType.OBSERVE == "observe"
        assert AgentEventType.ERROR == "error"
        assert AgentEventType.FINISH == "finish"

    def test_event_type_values(self):
        """测试事件类型值是小写字符串"""
        assert all(isinstance(t.value, str) for t in AgentEventType)
        assert all(t.value.islower() for t in AgentEventType)


class TestAgentEventCreation:
    """测试 AgentEvent 创建"""

    def test_create_think_event(self):
        """测试创建 THINK 事件"""
        event = AgentEvent(
            event=AgentEventType.THINK,
            data={"reasoning": "分析问题中...", "raw_output": "思考内容"},
            step=1,
        )

        assert event.event == AgentEventType.THINK
        assert event.data["reasoning"] == "分析问题中..."
        assert event.data["raw_output"] == "思考内容"
        assert event.step == 1
        assert isinstance(event.timestamp, datetime)

    def test_create_act_event(self):
        """测试创建 ACT 事件"""
        event = AgentEvent(
            event=AgentEventType.ACT,
            data={"tool_name": "search", "params": {"query": "test"}},
            step=2,
        )

        assert event.event == AgentEventType.ACT
        assert event.data["tool_name"] == "search"
        assert event.data["params"]["query"] == "test"
        assert event.step == 2

    def test_create_observe_event(self):
        """测试创建 OBSERVE 事件"""
        event = AgentEvent(
            event=AgentEventType.OBSERVE,
            data={"tool_name": "search", "result_summary": "找到 3 条结果"},
            step=3,
        )

        assert event.event == AgentEventType.OBSERVE
        assert event.data["tool_name"] == "search"
        assert event.data["result_summary"] == "找到 3 条结果"

    def test_create_error_event(self):
        """测试创建 ERROR 事件"""
        event = AgentEvent(
            event=AgentEventType.ERROR,
            data={"message": "工具调用失败", "details": "Timeout after 30s"},
            step=4,
        )

        assert event.event == AgentEventType.ERROR
        assert event.data["message"] == "工具调用失败"
        assert event.data["details"] == "Timeout after 30s"

    def test_create_finish_event(self):
        """测试创建 FINISH 事件"""
        event = AgentEvent(
            event=AgentEventType.FINISH,
            data={"answer": "最终答案是 42"},
            step=5,
        )

        assert event.event == AgentEventType.FINISH
        assert event.data["answer"] == "最终答案是 42"

    def test_timestamp_auto_generated(self):
        """测试时间戳自动生成"""
        before = datetime.now()
        event = AgentEvent(
            event=AgentEventType.THINK,
            data={"reasoning": "test"},
            step=1,
        )
        after = datetime.now()

        assert before <= event.timestamp <= after

    def test_timestamp_can_be_set(self):
        """测试可以手动设置时间戳"""
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        event = AgentEvent(
            event=AgentEventType.THINK,
            data={"reasoning": "test"},
            step=1,
            timestamp=custom_time,
        )

        assert event.timestamp == custom_time


class TestAgentEventSerialization:
    """测试 AgentEvent 序列化"""

    def test_to_json(self):
        """测试 JSON 序列化"""
        custom_time = datetime(2024, 1, 15, 10, 30, 0)
        event = AgentEvent(
            event=AgentEventType.ACT,
            data={"tool_name": "search", "params": {"q": "test"}},
            step=1,
            timestamp=custom_time,
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["event"] == "act"
        assert data["data"]["tool_name"] == "search"
        assert data["step"] == 1
        assert data["timestamp"] == "2024-01-15T10:30:00"

    def test_to_json_chinese_content(self):
        """测试 JSON 序列化中文内容"""
        event = AgentEvent(
            event=AgentEventType.FINISH,
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
            event=AgentEventType.THINK,
            data={"reasoning": "思考中..."},
            step=1,
            timestamp=custom_time,
        )

        sse_str = event.to_sse()

        assert sse_str.startswith("data: ")
        assert sse_str.endswith("\n\n")

        # 提取并解析 SSE 数据
        json_part = sse_str[6:-2]  # 移除 "data: " 和 "\n\n"
        data = json.loads(json_part)
        assert data["event"] == "think"

    def test_to_sse_event_type_in_data(self):
        """测试 SSE 包含事件类型"""
        event = AgentEvent(
            event=AgentEventType.ACT,
            data={"tool_name": "calculator"},
            step=2,
        )

        sse_str = event.to_sse()
        json_part = sse_str[6:-2]
        data = json.loads(json_part)

        assert data["event"] == "act"
        assert data["step"] == 2

    def test_model_dump(self):
        """测试 Pydantic model_dump 方法"""
        event = AgentEvent(
            event=AgentEventType.ERROR,
            data={"message": "错误", "details": "详情"},
            step=3,
        )

        dump = event.model_dump()

        assert dump["event"] == AgentEventType.ERROR
        assert dump["data"]["message"] == "错误"
        assert dump["step"] == 3
        assert "timestamp" in dump


class TestAgentEventValidation:
    """测试 AgentEvent 验证"""

    def test_event_type_must_be_valid(self):
        """测试事件类型必须是有效值"""
        event = AgentEvent(
            event=AgentEventType.THINK,
            data={},
            step=1,
        )
        assert event.event == AgentEventType.THINK

    def test_step_must_be_integer(self):
        """测试步骤必须是整数"""
        event = AgentEvent(
            event=AgentEventType.THINK,
            data={},
            step=5,
        )
        assert event.step == 5

    def test_data_can_be_empty(self):
        """测试 data 可以是空字典"""
        event = AgentEvent(
            event=AgentEventType.THINK,
            data={},
            step=1,
        )
        assert event.data == {}

    def test_data_can_contain_nested_structures(self):
        """测试 data 可以包含嵌套结构"""
        event = AgentEvent(
            event=AgentEventType.OBSERVE,
            data={
                "tool_name": "search",
                "result_summary": "搜索结果",
                "metadata": {
                    "total": 10,
                    "items": ["a", "b", "c"],
                },
            },
            step=2,
        )

        assert event.data["metadata"]["total"] == 10
        assert len(event.data["metadata"]["items"]) == 3
