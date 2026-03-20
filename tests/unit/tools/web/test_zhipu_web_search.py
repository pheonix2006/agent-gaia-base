# tests/unit/tools/web/test_zhipu_web_search.py

"""ZhipuWebSearchTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ai_agent.tools.web.zhipu_web_search import (
    ZhipuWebSearchTool,
    ZhipuWebSearchParams,
)


class TestZhipuWebSearchParams:
    """参数模型测试"""

    def test_default_values(self) -> None:
        """测试默认参数值"""
        params = ZhipuWebSearchParams(query="test")
        assert params.query == "test"
        assert params.count == 10
        assert params.search_recency_filter == "noLimit"

    def test_custom_values(self) -> None:
        """测试自定义参数值"""
        params = ZhipuWebSearchParams(
            query="Python 教程",
            count=20,
            search_recency_filter="oneWeek",
        )
        assert params.count == 20
        assert params.search_recency_filter == "oneWeek"

    def test_query_max_length(self) -> None:
        """测试查询最大长度限制"""
        long_query = "a" * 71
        with pytest.raises(Exception):  # Pydantic ValidationError
            ZhipuWebSearchParams(query=long_query)

    def test_count_range(self) -> None:
        """测试结果数量范围"""
        with pytest.raises(Exception):
            ZhipuWebSearchParams(query="test", count=0)
        with pytest.raises(Exception):
            ZhipuWebSearchParams(query="test", count=51)


class TestZhipuWebSearchTool:
    """工具类测试"""

    def test_tool_name(self) -> None:
        """测试工具名称"""
        tool = ZhipuWebSearchTool()
        assert tool.name == "web_search"

    def test_tool_description(self) -> None:
        """测试工具描述"""
        tool = ZhipuWebSearchTool()
        assert "搜索" in tool.description

    def test_params_schema(self) -> None:
        """测试参数 schema"""
        tool = ZhipuWebSearchTool()
        assert tool.params_schema == ZhipuWebSearchParams

    def test_to_langchain_tool(self) -> None:
        """测试转换为 LangChain 工具"""
        tool = ZhipuWebSearchTool()
        lc_tool = tool.to_langchain_tool()
        assert lc_tool.name == "web_search"

    @pytest.mark.asyncio
    async def test_run_missing_api_key(self) -> None:
        """测试缺少 API Key 时的错误处理"""
        tool = ZhipuWebSearchTool()

        with patch.object(
            tool,
            "settings",
            MagicMock(zhipu_api_key="", zhipu_web_search_url="https://example.com")
        ):
            params = ZhipuWebSearchParams(query="test")
            result = await tool.run(params)

            assert result.success is False
            assert "ZHIPU_API_KEY 未配置" in result.error

    def test_parse_results_empty(self) -> None:
        """测试空结果解析"""
        tool = ZhipuWebSearchTool()
        parsed = tool._parse_results({})

        assert len(parsed) == 1
        assert "未找到" in parsed[0]["content"]

    def test_parse_results_with_data(self) -> None:
        """测试正常结果解析"""
        tool = ZhipuWebSearchTool()
        response = {
            "search_result": [
                {
                    "title": "Python 官方文档",
                    "content": "Python 是一种编程语言",
                    "link": "https://python.org",
                    "icon": "https://python.org/favicon.ico",
                    "media": "Python.org",
                },
                {
                    "title": "Python 教程",
                    "content": "学习 Python 的最佳教程",
                    "link": "https://example.com/python",
                },
            ]
        }
        parsed = tool._parse_results(response)

        assert len(parsed) == 2
        assert parsed[0]["title"] == "Python 官方文档"
        assert parsed[0]["content"] == "Python 是一种编程语言"
        assert parsed[0]["link"] == "https://python.org"
        # 确保精简字段，不包含 icon
        assert "icon" not in parsed[0]
        assert "media" not in parsed[0]
