# tests/unit/agents/test_simple_agent.py
"""SimpleChatAgent tests"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import AIMessage


class TestSimpleChatAgent:

    def test_simple_chat_agent_initialization(self):
        """Test SimpleChatAgent initializes correctly"""
        from ai_agent.agents.simple.graph import SimpleChatAgent

        mock_llm = MagicMock()
        agent = SimpleChatAgent(mock_llm)

        assert agent.llm is mock_llm

    def test_simple_chat_agent_has_graph(self):
        """Test SimpleChatAgent has a compiled graph"""
        from ai_agent.agents.simple.graph import SimpleChatAgent

        mock_llm = MagicMock()
        agent = SimpleChatAgent(mock_llm)

        graph = agent.get_graph()
        assert graph is not None

    @pytest.mark.asyncio
    async def test_simple_chat_agent_run(self):
        """Test SimpleChatAgent run returns response"""
        from ai_agent.agents.simple.graph import SimpleChatAgent

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="Test response")
        )

        agent = SimpleChatAgent(mock_llm)
        result = await agent.run("Test message")

        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_simple_chat_agent_invokes_llm(self):
        """Test SimpleChatAgent calls LLM"""
        from ai_agent.agents.simple.graph import SimpleChatAgent

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="Test response")
        )

        agent = SimpleChatAgent(mock_llm)
        await agent.run("Test message")

        mock_llm.ainvoke.assert_called_once()
