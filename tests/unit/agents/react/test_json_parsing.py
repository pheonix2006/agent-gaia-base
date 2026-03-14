"""测试 ReAct Agent 的 JSON 解析容错能力"""

import pytest
from unittest.mock import MagicMock

from ai_agent.agents.react.graph import ReActAgent


class TestJsonParsing:
    """测试 JSON 解析的各种边缘情况"""

    @pytest.fixture
    def agent(self):
        """创建测试用的 ReActAgent"""
        mock_llm = MagicMock()
        return ReActAgent(llm=mock_llm, tools=[])

    def test_parse_standard_json(self, agent):
        """测试标准 JSON 解析"""
        response = '''```json
{
    "action": "finish",
    "params": {"result": "任务完成"},
    "memory": "观察到一些信息"
}
```'''
        action = agent._parse_action(response)
        assert action is not None
        assert action.action == "finish"
        assert action.params["result"] == "任务完成"
        assert action.memory == "观察到一些信息"

    def test_parse_json_without_code_block(self, agent):
        """测试没有代码块的纯 JSON"""
        response = '{"action": "google_search", "params": {"query": "test"}, "memory": "搜索测试"}'
        action = agent._parse_action(response)
        assert action is not None
        assert action.action == "google_search"
        assert action.params["query"] == "test"

    def test_parse_json_with_unescaped_newlines(self, agent):
        """测试包含未转义换行符的 JSON（GLM 等模型的常见问题）"""
        # 模拟 GLM 模型输出的 JSON：字符串中包含实际的换行符
        response = '''{
    "action": "finish",
    "params": {
        "result": "这是第一行
这是第二行
这是第三行"
    },
    "memory": "观察结果"
}'''
        action = agent._parse_action(response)
        assert action is not None
        assert action.action == "finish"
        assert "第一行" in action.params["result"]
        assert "第二行" in action.params["result"]

    def test_parse_json_with_tabs(self, agent):
        """测试包含制表符的 JSON"""
        response = '''{
    "action": "finish",
    "params": {"result": "包含\t制表符\t的内容"},
    "memory": "观察"
}'''
        action = agent._parse_action(response)
        assert action is not None
        assert action.action == "finish"

    def test_parse_truncated_json_with_regex_fallback(self, agent):
        """测试截断 JSON 的正则兜底解析"""
        # JSON 不完整，但包含关键字段
        response = '''{
    "action": "finish",
    "params": {
        "result": "任务结果"
    }'''
        action = agent._parse_action(response)
        # 应该通过正则提取成功
        assert action is not None
        assert action.action == "finish"

    def test_parse_invalid_json_returns_none(self, agent):
        """测试完全无效的 JSON 返回 None"""
        response = "这不是 JSON 格式"
        action = agent._parse_action(response)
        assert action is None

    def test_repair_json_string_basic(self, agent):
        """测试 JSON 字符串修复方法"""
        # 字符串中包含未转义的换行符
        broken = '{"text": "line1\nline2"}'
        repaired = agent._repair_json_string(broken)
        assert repaired == '{"text": "line1\\nline2"}'

    def test_repair_json_string_preserves_escaped(self, agent):
        """测试已转义的字符保持不变"""
        # 已经正确转义的 JSON 不应被修改
        valid = '{"text": "line1\\nline2"}'
        repaired = agent._repair_json_string(valid)
        assert repaired == valid

    def test_repair_json_string_complex(self, agent):
        """测试复杂场景：混合转义和非转义"""
        # 混合场景
        broken = '{"result": "hello\\nworld\nnew line", "status": "done"}'
        repaired = agent._repair_json_string(broken)
        # 第一个 \n 已转义保持，第二个实际换行应被转义
        assert "\\n" in repaired
        assert repaired.count("\\n") >= 2
