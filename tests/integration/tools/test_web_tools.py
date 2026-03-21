# tests/integration/tools/test_web_tools.py

"""Web 工具集成测试（真实 API）"""

import os
import pytest
from ai_agent.tools.web import (
    WebContentTool,
    WebContentParams,
    GoogleSearchTool,
    GoogleSearchParams,
)


# 使用自定义标记，可通过 -m integration 运行
pytestmark = pytest.mark.integration

# 跳过条件：Jina API 不可用（免费模式可能有限制）
requires_jina = pytest.mark.skipif(
    os.getenv("JINA_API_KEY", "") == "" and os.getenv("SKIP_JINA_TESTS", "") != "",
    reason="Jina API 免费模式可能有限制，设置 JINA_API_KEY 或取消设置 SKIP_JINA_TESTS 来运行"
)


class TestWebContentToolIntegration:
    """WebContentTool 集成测试"""

    @pytest.fixture
    def tool(self):
        return WebContentTool()

    @pytest.mark.asyncio
    @requires_jina
    async def test_extract_python_org(self, tool):
        """测试提取 Python 官网内容"""
        params = WebContentParams(
            url="https://www.python.org",
            query="What is Python? Answer in one sentence."
        )
        result = await tool.run(params)

        assert result.success is True
        assert result.data is not None
        assert "answer" in result.data
        assert result.data["url"] == "https://www.python.org"
        assert len(result.data["answer"]) > 10
        print(f"\n答案: {result.data['answer'][:200]}...")

    @pytest.mark.asyncio
    @requires_jina
    async def test_extract_github_readme(self, tool):
        """测试提取 GitHub README"""
        params = WebContentParams(
            url="https://github.com/langchain-ai/langchain",
            query="What is LangChain? Brief summary."
        )
        result = await tool.run(params)

        assert result.success is True
        print(f"\n答案: {result.data['answer'][:200]}...")


class TestGoogleSearchToolIntegration:
    """GoogleSearchTool 集成测试"""

    @pytest.fixture
    def tool(self):
        return GoogleSearchTool()

    @pytest.mark.asyncio
    async def test_search_python(self, tool):
        """测试搜索 Python"""
        params = GoogleSearchParams(query="Python programming language", k=3)
        result = await tool.run(params)

        assert result.success is True
        assert result.data is not None
        assert len(result.data) > 0
        assert len(result.data) <= 3

        print(f"\n搜索结果:")
        for i, item in enumerate(result.data[:3], 1):
            print(f"  {i}. {item['content'][:100]}...")
            print(f"     来源: {item['source']}")

    @pytest.mark.asyncio
    async def test_search_with_chinese(self, tool):
        """测试中文搜索"""
        params = GoogleSearchParams(query="人工智能", k=5, gl="cn", hl="zh")
        result = await tool.run(params)

        assert result.success is True
        assert len(result.data) > 0
        print(f"\n中文搜索结果数量: {len(result.data)}")

    @pytest.mark.asyncio
    async def test_search_specific_question(self, tool):
        """测试具体问题搜索"""
        params = GoogleSearchParams(query="What is the capital of France?", k=1)
        result = await tool.run(params)

        assert result.success is True
        print(f"\n答案: {result.data[0]['content']}")
