# tests/unit/tools/web/test_google_search.py

"""GoogleSearchTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch
from ai_agent.tools.web.google_search import GoogleSearchTool


class TestGoogleSearchTool:
    """GoogleSearchTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = GoogleSearchTool()
        assert tool.name == "google_search"
        assert "搜索" in tool.description or "Google" in tool.description
        assert "query" in tool.parameters.get("properties", {})

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

            result = await tool.run(query="Python 是什么")

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

            result = await tool.run(query="Python", k=2)

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

            result = await tool.run(query="不存在的查询xyz123")

            assert result.success is True
            assert "No good" in result.data[0]["content"]

    @pytest.mark.asyncio
    async def test_run_api_error(self):
        """测试 API 错误"""
        tool = GoogleSearchTool()

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("API Error")

            result = await tool.run(query="test")

            assert result.success is False
            assert "API Error" in result.error

    @pytest.mark.asyncio
    async def test_run_with_custom_params(self):
        """测试自定义参数"""
        tool = GoogleSearchTool()

        mock_response = {"organic": [{"snippet": "test", "link": "url"}]}

        with patch.object(tool, '_search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response

            await tool.run(query="test", k=10, gl="cn", hl="zh")

            # 验证调用参数
            call_args = mock_search.call_args
            assert call_args[1]["k"] == 10
            assert call_args[1]["gl"] == "cn"
            assert call_args[1]["hl"] == "zh"
