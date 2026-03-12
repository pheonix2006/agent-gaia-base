# tests/unit/agents/test_base.py
"""Agent 基类测试"""
import pytest
from unittest.mock import MagicMock


def test_base_agent_is_abstract():
    """测试 Agent 基类是抽象类"""
    from ai_agent.agents.base import BaseAgent

    mock_llm = MagicMock()
    with pytest.raises(TypeError):
        BaseAgent(mock_llm)


def test_base_agent_interface():
    """测试 Agent 接口定义"""
    from ai_agent.agents.base import BaseAgent

    class ConcreteAgent(BaseAgent):
        async def run(self, message: str) -> str:
            return f"Response to: {message}"

        def get_graph(self):
            return "mock_graph"

    mock_llm = MagicMock()
    agent = ConcreteAgent(mock_llm)

    assert agent.llm == mock_llm
    assert agent.tools == []


def test_base_agent_with_tools():
    """测试带工具的 Agent"""
    from ai_agent.agents.base import BaseAgent

    class ToolAgent(BaseAgent):
        async def run(self, message: str) -> str:
            return "ok"

        def get_graph(self):
            return None

    mock_llm = MagicMock()
    mock_tools = [MagicMock(), MagicMock()]

    agent = ToolAgent(mock_llm, tools=mock_tools)
    assert len(agent.tools) == 2
