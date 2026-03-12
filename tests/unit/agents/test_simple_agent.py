# tests/unit/agents/test_simple_agent.py
"""SimpleChatAgent 测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import AIMessage


@pytest.fixture
def mock_llm():
    """创建模拟 LLM"""
    llm = MagicMock()
    # 返回真正的 AIMessage 对象
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mock response"))
    return llm


def test_simple_chat_agent_initialization(mock_llm):
    """测试 SimpleChatAgent 初始化"""
    from ai_agent.agents.simple.graph import SimpleChatAgent

    agent = SimpleChatAgent(mock_llm)
    assert agent.llm == mock_llm
    assert agent.tools == []


def test_simple_chat_agent_has_graph(mock_llm):
    """测试 SimpleChatAgent 有图"""
    from ai_agent.agents.simple.graph import SimpleChatAgent

    agent = SimpleChatAgent(mock_llm)
    graph = agent.get_graph()

    assert graph is not None


@pytest.mark.asyncio
async def test_simple_chat_agent_run(mock_llm):
    """测试 SimpleChatAgent 运行"""
    from ai_agent.agents.simple.graph import SimpleChatAgent

    agent = SimpleChatAgent(mock_llm)
    response = await agent.run("Hello")

    assert response == "Mock response"


@pytest.mark.asyncio
async def test_simple_chat_agent_invokes_llm(mock_llm):
    """测试 SimpleChatAgent 调用 LLM"""
    from ai_agent.agents.simple.graph import SimpleChatAgent

    agent = SimpleChatAgent(mock_llm)
    await agent.run("Test message")

    mock_llm.ainvoke.assert_called_once()
