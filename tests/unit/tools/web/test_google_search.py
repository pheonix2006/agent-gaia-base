# tests/unit/tools/web/test_google_search.py

"""GoogleSearchTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch
from ai_agent.tools.web.google_search import GoogleSearchTool, GoogleSearchParams


class TestGoogleSearchTool:
    """GoogleSearchTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = GoogleSearchTool()
        assert tool.name == "google_search"
        assert "Search via Serper" in tool.description or "Google" in tool.description
        assert "query" in tool.parameters.get("properties", {})

    def test_params_schema(self):
        """测试参数模型"""
        tool = GoogleSearchTool()
        assert tool.params_schema == GoogleSearchParams

        # 测试默认值
        params = GoogleSearchParams(query="test")
        assert params.k == 5
        assert params.gl == "us"
        assert params.hl == "en"

    def test_params_validation(self):
        """测试参数验证"""
        # k 的范围验证
        params = GoogleSearchParams(query="test", k=10)
        assert params.k == 10

        # gl 和 hl 的长度验证
        params = GoogleSearchParams(query="test", gl="cn", hl="zh")
        assert params.gl == "cn"
        assert params.hl == "zh"

    @pytest.mark.asyncio
    async def test_run_success_with_answer_box(self):
        """测试搜索成功（有 answerBox）"""
        tool = GoogleSearchTool()

        mock_response = {
            "answerBox": {
                "answer": "Python 是一种编程语言"
            },
            "organic": []
        }

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response

            params = GoogleSearchParams(query="Python 是什么")
            result = await tool.run(params)

            assert result.success is True
            assert len(result.data) == 1
            assert "编程语言" in result.data[0]["content"]

    @pytest.mark.asyncio
    async def test_run_success_with_organic(self):
        """测试搜索成功（使用 organic 结果）"""
        tool = GoogleSearchTool()

        mock_response = {
            "organic": [
                {"snippet": "Python 官方网站", "link": "https://python.org"},
                {"snippet": "Python 教程", "link": "https://tutorial.python.org"},
            ]
        }

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response

            params = GoogleSearchParams(query="Python", k=2)
            result = await tool.run(params)

            assert result.success is True
            assert len(result.data) == 2
            assert result.data[0]["source"] == "https://python.org"

    @pytest.mark.asyncio
    async def test_run_no_results(self):
        """测试无搜索结果"""
        tool = GoogleSearchTool()

        mock_response = {}

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response

            params = GoogleSearchParams(query="不存在的查询xyz123")
            result = await tool.run(params)

            assert result.success is True
            assert "No good" in result.data[0]["content"]

    @pytest.mark.asyncio
    async def test_run_api_error(self):
        """测试 API 错误"""
        tool = GoogleSearchTool()

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("API Error")

            params = GoogleSearchParams(query="test")
            result = await tool.run(params)

            assert result.success is False
            assert "API Error" in result.error

    @pytest.mark.asyncio
    async def test_run_with_custom_params(self):
        """测试自定义参数"""
        tool = GoogleSearchTool()

        mock_response = {"organic": [{"snippet": "test", "link": "url"}]}

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response

            params = GoogleSearchParams(query="test", k=10, gl="cn", hl="zh")
            await tool.run(params)

            # 验证调用参数
            call_args = mock_search.call_args
            assert call_args[1]["k"] == 10
            assert call_args[1]["gl"] == "cn"
            assert call_args[1]["hl"] == "zh"

    def test_to_langchain_tool(self):
        """测试转换为 LangChain 工具"""
        tool = GoogleSearchTool()
        lc_tool = tool.to_langchain_tool()

        assert lc_tool.name == "google_search"
        assert "Search via Serper" in lc_tool.description
