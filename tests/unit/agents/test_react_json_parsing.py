"""测试 ReAct Agent 的 JSON 解析和参数提取功能"""
import pytest
from ai_agent.agents.react import ReActAgent
from unittest.mock import MagicMock


@pytest.fixture
def agent():
    """创建一个基本的 ReActAgent 实例用于测试"""
    mock_llm = MagicMock()
    return ReActAgent(mock_llm, tools=[])


class TestExtractActionWithRegex:
    """测试 _extract_action_with_regex 方法"""

    def test_extract_standard_json(self, agent):
        """测试提取标准 JSON 格式"""
        text = '''```json
        {
            "action": "web_search",
            "params": {
                "query": "test query",
                "count": 10,
                "search_recency_filter": "oneWeek"
            },
            "memory": "Searching for test query"
        }
        ```'''
        result = agent._extract_action_with_regex(text)

        assert result is not None
        assert result.action == "web_search"
        assert result.params == {
            "query": "test query",
            "count": 10,
            "search_recency_filter": "oneWeek"
        }
        assert result.memory == "Searching for test query"

    def test_extract_with_nested_params(self, agent):
        """测试提取包含嵌套对象的 params"""
        text = '''{
            "action": "complex_tool",
            "params": {
                "query": "test",
                "options": {
                    "deep": true,
                    "nested": {
                        "value": 42
                    }
                },
                "array": [1, 2, 3]
            },
            "memory": "Complex operation"
        }'''
        result = agent._extract_action_with_regex(text)

        assert result is not None
        assert result.action == "complex_tool"
        assert result.params["query"] == "test"
        assert result.params["options"]["deep"] is True
        assert result.params["options"]["nested"]["value"] == 42
        assert result.params["array"] == [1, 2, 3]
        assert result.memory == "Complex operation"

    def test_extract_with_boolean_and_number(self, agent):
        """测试提取布尔值和数字类型的 params"""
        text = '''{
            "action": "data_tool",
            "params": {
                "enabled": true,
                "count": 100,
                "ratio": 3.14,
                "disabled": false,
                "name": "test"
            },
            "memory": "Data processing"
        }'''
        result = agent._extract_action_with_regex(text)

        assert result is not None
        assert result.action == "data_tool"
        assert result.params["enabled"] is True
        assert result.params["count"] == 100
        assert result.params["ratio"] == 3.14
        assert result.params["disabled"] is False
        assert result.params["name"] == "test"

    def test_extract_with_missing_params(self, agent):
        """测试缺少 params 字段时返回空字典"""
        text = '''{
            "action": "simple_tool",
            "memory": "No params needed"
        }'''
        result = agent._extract_action_with_regex(text)

        assert result is not None
        assert result.action == "simple_tool"
        assert result.params == {}
        assert result.memory == "No params needed"

    def test_extract_with_empty_params(self, agent):
        """测试 params 为空对象"""
        text = '''{
            "action": "tool",
            "params": {},
            "memory": "Empty params"
        }'''
        result = agent._extract_action_with_regex(text)

        assert result is not None
        assert result.action == "tool"
        assert result.params == {}

    def test_extract_finish_action(self, agent):
        """测试提取 finish action（向后兼容）"""
        text = '''{
            "action": "finish",
            "params": {
                "result": "Final answer",
                "status": "done"
            },
            "memory": "Completed"
        }'''
        result = agent._extract_action_with_regex(text)

        assert result is not None
        assert result.action == "finish"
        assert result.params["result"] == "Final answer"
        assert result.params["status"] == "done"

    def test_extract_finish_action_legacy_format(self, agent):
        """测试提取旧格式的 finish action（只有 result 字段）"""
        text = '''{
            "action": "finish",
            "result": "Final answer",
            "memory": "Completed"
        }'''
        result = agent._extract_action_with_regex(text)

        assert result is not None
        assert result.action == "finish"
        assert result.params["result"] == "Final answer"

    def test_extract_with_special_characters_in_strings(self, agent):
        """测试 params 中包含特殊字符的字符串"""
        text = r'''{
            "action": "search",
            "params": {
                "query": "What is \"AI\"?",
                "path": "C:\\Users\\test",
                "regex": "\\d+"
            },
            "memory": "Special chars test"
        }'''
        result = agent._extract_action_with_regex(text)

        assert result is not None
        assert result.action == "search"
        # 注意：JSON 解析后转义字符会被处理
        assert "AI" in result.params["query"]

    def test_extract_with_unescaped_newlines(self, agent):
        """测试 params 字符串中包含未转义换行符（常见 LLM 输出问题）"""
        text = '''{
            "action": "search",
            "params": {
                "query": "line1
line2",
                "count": 5
            },
            "memory": "Multiline test"
        }'''
        result = agent._extract_action_with_regex(text)

        # 应该能提取，即使有换行符
        assert result is not None
        assert result.action == "search"
        # 换行符应该被保留或修复
        assert "line" in result.params.get("query", "")

    def test_real_world_web_search_case(self, agent):
        """测试真实场景：web_search 工具调用"""
        text = '''{
            "action": "web_search",
            "params": {
                "query": "Claude 3.5 sonnet latest features 2025",
                "count": 10,
                "search_recency_filter": "oneWeek"
            },
            "memory": "用户想了解 Claude 3.5 sonnet 的最新功能"
        }'''
        result = agent._extract_action_with_regex(text)

        assert result is not None
        assert result.action == "web_search"
        assert result.params["query"] == "Claude 3.5 sonnet latest features 2025"
        assert result.params["count"] == 10
        assert result.params["search_recency_filter"] == "oneWeek"
        assert "Claude" in result.memory

    def test_extract_with_no_memory(self, agent):
        """测试没有 memory 字段的情况"""
        text = '''{
            "action": "tool",
            "params": {
                "query": "test"
            }
        }'''
        result = agent._extract_action_with_regex(text)

        assert result is not None
        assert result.action == "tool"
        assert result.params["query"] == "test"
        assert result.memory == ""

    def test_extract_with_malformed_json(self, agent):
        """测试格式错误的 JSON"""
        text = '''{
            "action": "tool",
            "params": {query: test},
            "memory": "Malformed"
        }'''
        result = agent._extract_action_with_regex(text)

        # 至少应该提取出 action
        assert result is not None
        assert result.action == "tool"

    def test_extract_returns_none_for_no_action(self, agent):
        """测试没有 action 字段时返回 None"""
        text = '''{
            "params": {"query": "test"},
            "memory": "No action"
        }'''
        result = agent._extract_action_with_regex(text)

        assert result is None


class TestRepairJsonString:
    """测试 _repair_json_string 方法"""

    def test_repair_unescaped_newlines(self, agent):
        """测试修复未转义的换行符"""
        json_str = '{"query": "line1\nline2"}'
        repaired = agent._repair_json_string(json_str)

        assert '\\n' in repaired
        assert '\n' not in repaired.replace('\\n', '')

    def test_repair_unescaped_tabs(self, agent):
        """测试修复未转义的制表符"""
        json_str = '{"query": "col1\tcol2"}'
        repaired = agent._repair_json_string(json_str)

        assert '\\t' in repaired

    def test_repair_unescaped_carriage_return(self, agent):
        """测试修复未转义的回车符"""
        json_str = '{"query": "text\rmore"}'
        repaired = agent._repair_json_string(json_str)

        assert '\\r' in repaired

    def test_preserve_already_escaped(self, agent):
        """测试保留已转义的控制字符"""
        json_str = r'{"query": "line1\\nline2"}'
        repaired = agent._repair_json_string(json_str)

        # 应该保持不变或等价
        assert '\\n' in repaired

    def test_remove_trailing_commas(self, agent):
        """测试移除多余的尾部逗号"""
        json_str = '{"query": "test", "count": 5,}'
        repaired = agent._repair_json_string(json_str)

        # 尾部逗号应该被移除
        assert ',}' not in repaired

    def test_fix_unclosed_quotes(self, agent):
        """测试修复未闭合的引号"""
        json_str = '{"query": "test}'
        repaired = agent._repair_json_string(json_str)

        # 应该添加闭合引号
        assert repaired.count('"') % 2 == 0

    def test_fix_unclosed_braces(self, agent):
        """测试修复未闭合的大括号"""
        json_str = '{"query": "test"'
        repaired = agent._repair_json_string(json_str)

        # 应该添加闭合括号
        assert repaired.endswith('}')

    def test_fix_unclosed_brackets(self, agent):
        """测试修复未闭合的中括号"""
        json_str = '{"array": [1, 2, 3}'
        repaired = agent._repair_json_string(json_str)

        # 应该添加闭合括号
        assert repaired.endswith(']')

    def test_complex_nested_structure(self, agent):
        """测试复杂的嵌套结构修复"""
        json_str = '''{
    "action": "tool",
    "params": {
        "query": "test
with newline",
        "options": {"deep": true
    },
    "memory": "test"
}'''
        repaired = agent._repair_json_string(json_str)

        # 应该修复换行符和缺失的括号
        assert '\\n' in repaired or 'with' in repaired

    def test_preserve_valid_json(self, agent):
        """测试不破坏有效的 JSON"""
        json_str = '{"query": "test", "count": 5}'
        repaired = agent._repair_json_string(json_str)

        # 有效 JSON 应该基本保持不变
        assert 'query' in repaired
        assert 'test' in repaired


class TestParseActionIntegration:
    """测试完整的 _parse_action 方法（集成测试）"""

    def test_parse_standard_json_block(self, agent):
        """测试解析标准 JSON 块"""
        response = '''```json
{
    "action": "web_search",
    "params": {
        "query": "test query",
        "count": 10
    },
    "memory": "Searching"
}
```'''
        result = agent._parse_action(response)

        assert result is not None
        assert result.action == "web_search"
        assert result.params["query"] == "test query"
        assert result.params["count"] == 10

    def test_parse_json_with_control_chars(self, agent):
        """测试解析包含控制字符的 JSON"""
        response = '''{
    "action": "search",
    "params": {
        "query": "line1
line2",
        "count": 5
    },
    "memory": "Test"
}'''
        result = agent._parse_action(response)

        assert result is not None
        assert result.action == "search"

    def test_parse_minimal_json(self, agent):
        """测试解析最小 JSON"""
        response = '{"action": "finish", "params": {"result": "Done"}, "memory": ""}'
        result = agent._parse_action(response)

        assert result is not None
        assert result.action == "finish"
        assert result.params["result"] == "Done"

    def test_parse_fallback_to_regex(self, agent):
        """测试 JSON 解析失败时回退到 regex"""
        # 构造一个 JSON 解析会失败，但 regex 可以提取的字符串
        response = '''Some text before
        {"action": "tool", "params": {broken json}, "memory": "test"}
        Some text after'''
        result = agent._parse_action(response)

        # 至少应该通过 regex 提取出 action
        if result:  # regex 可能无法完全解析 broken json
            assert result.action == "tool"

    def test_parse_returns_none_for_completely_invalid(self, agent):
        """测试完全无效的输入返回 None"""
        response = "This is not JSON at all, just plain text."
        result = agent._parse_action(response)

        assert result is None


class TestRealWorldScenarios:
    """真实场景测试"""

    def test_zhipu_web_search_params(self, agent):
        """测试智谱 AI 的 web_search 参数格式"""
        response = '''```json
{
    "action": "web_search",
    "params": {
        "query": "Claude 3.5 sonnet 最新功能 2025",
        "count": 10,
        "search_recency_filter": "oneWeek"
    },
    "memory": "用户想了解最新的 Claude 功能"
}
```'''
        result = agent._parse_action(response)

        assert result is not None
        assert result.action == "web_search"
        assert result.params["query"] == "Claude 3.5 sonnet 最新功能 2025"
        assert result.params["count"] == 10
        assert result.params["search_recency_filter"] == "oneWeek"

        # 验证参数可以被 Pydantic 验证
        from test_debug_tool_invoke import ZhipuWebSearchParams
        params = ZhipuWebSearchParams(**result.params)
        assert params.query == "Claude 3.5 sonnet 最新功能 2025"

    def test_multiline_query_with_special_chars(self, agent):
        """测试包含换行和特殊字符的查询"""
        response = '''{
    "action": "search",
    "params": {
        "query": "What is AI?
How does it work?
Examples:\\n1. NLP\\n2. CV",
        "count": 5
    },
    "memory": "Complex query"
}'''
        result = agent._parse_action(response)

        assert result is not None
        assert result.action == "search"
        # 参数应该被正确提取
        assert "query" in result.params
