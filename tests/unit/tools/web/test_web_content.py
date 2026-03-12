# tests/unit/tools/web/test_web_content.py

"""WebContentTool 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ai_agent.tools.web.web_content import WebContentTool


class TestWebContentTool:
    """WebContentTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = WebContentTool()
        assert tool.name == "web_content"
        assert "网页" in tool.description or "URL" in tool.description
        assert "url" in tool.parameters.get("properties", {})
        assert "query" in tool.parameters.get("properties", {})

    @pytest.mark.asyncio
    async def test_run_success(self):
        """测试成功提取网页内容"""
        tool = WebContentTool()

        with patch.object(tool, '_fetch_jina', new_callable=AsyncMock) as mock_fetch, \
             patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_fetch.return_value = "这是一段网页内容"
            mock_llm.return_value = "这是摘要答案"

            result = await tool.run(url="https://example.com", query="总结这篇文章")

            assert result.success is True
            assert result.data["answer"] == "这是摘要答案"
            assert result.data["url"] == "https://example.com"
            mock_fetch.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_run_fetch_failure(self):
        """测试网页获取失败"""
        tool = WebContentTool()

        with patch.object(tool, '_fetch_jina', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None

            result = await tool.run(url="https://invalid-url.com", query="测试")

            assert result.success is False
            assert "获取网页内容失败" in result.error

    @pytest.mark.asyncio
    async def test_run_empty_content(self):
        """测试空网页内容"""
        tool = WebContentTool()

        with patch.object(tool, '_fetch_jina', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = ""

            result = await tool.run(url="https://example.com", query="测试")

            assert result.success is False

    @pytest.mark.asyncio
    async def test_run_long_content_chunking(self):
        """测试长内容分块处理"""
        tool = WebContentTool()

        # 模拟超长内容（触发分块）
        long_content = "测试内容 " * 50000  # 约 10万 token

        with patch.object(tool, '_fetch_jina', new_callable=AsyncMock) as mock_fetch, \
             patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_llm, \
             patch('ai_agent.tools.web.web_content.tiktoken') as mock_tiktoken:
            mock_fetch.return_value = long_content
            mock_llm.return_value = "分块答案"
            # 模拟 tiktoken 返回超长 token 数
            mock_encoding = MagicMock()
            mock_encoding.encode.return_value = [1] * 100000  # 10万 token
            mock_encoding.decode.return_value = "解码内容"
            mock_tiktoken.get_encoding.return_value = mock_encoding

            result = await tool.run(url="https://example.com", query="总结")

            assert result.success is True
            # 应该调用多次 LLM（分块）
            assert mock_llm.call_count > 1
