# tests/integration/tools/test_web_tools.py

"""Web 工具集成测试（真实 API）"""

import pytest
from ai_agent.tools.web import WebContentTool, GoogleSearchTool


# 使用自定义标记，可通过 -m integration 运行
pytestmark = pytest.mark.integration


class TestWebContentToolIntegration:
    """WebContentTool 集成测试"""

    @pytest.fixture
    def tool(self):
        return WebContentTool()

    @pytest.mark.asyncio
    async def test_extract_python_org(self, tool):
        """测试提取 Python 官网内容"""
        result = await tool.run(
            url="https://www.python.org",
            query="What is Python? Answer in one sentence."
        )

        assert result.success is True
        assert result.data is not None
        assert "answer" in result.data
        assert result.data["url"] == "https://www.python.org"
        assert len(result.data["answer"]) > 10
        print(f"\n答案: {result.data['answer'][:200]}...")

    @pytest.mark.asyncio
    async def test_extract_github_readme(self, tool):
        """测试提取 GitHub README"""
        result = await tool.run(
            url="https://github.com/langchain-ai/langchain",
            query="What is LangChain? Brief summary."
        )

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
        result = await tool.run(query="Python programming language", k=3)

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
        result = await tool.run(query="人工智能", k=5, gl="cn", hl="zh")

        assert result.success is True
        assert len(result.data) > 0
        print(f"\n中文搜索结果数量: {len(result.data)}")

    @pytest.mark.asyncio
    async def test_search_specific_question(self, tool):
        """测试具体问题搜索"""
        result = await tool.run(query="What is the capital of France?", k=1)

        assert result.success is True
        print(f"\n答案: {result.data[0]['content']}")
