# tests/unit/agents/test_react_agent_memory.py

import pytest
from unittest.mock import MagicMock


def test_react_agent_accepts_memory():
    """测试 ReActAgent 接受 memory 参数"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()
    mock_memory = MagicMock(spec=CompressedMemory)

    agent = ReActAgent(mock_llm, memory=mock_memory)

    assert agent._memory is mock_memory


def test_react_agent_creates_default_memory():
    """测试 ReActAgent 默认创建 memory"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()

    agent = ReActAgent(mock_llm, create_memory=True)

    assert agent._memory is not None
    assert isinstance(agent._memory, CompressedMemory)


def test_react_agent_no_memory_by_default():
    """测试默认不创建 memory（保持向后兼容）"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm)

    assert agent._memory is None
