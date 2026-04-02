# tests/unit/agents/test_base.py
"""Agent 基类测试（tool_calling 版本）"""

import pytest
from collections.abc import AsyncIterator
from unittest.mock import MagicMock

from langchain_core.language_models import BaseChatModel


class TestBaseAgentAbstract:
    """测试 BaseAgent 抽象类约束"""

    def test_base_agent_cannot_be_instantiated(self):
        """测试 BaseAgent 不能直接实例化"""
        from ai_agent.agents.base import BaseAgent

        mock_llm = MagicMock(spec=BaseChatModel)
        with pytest.raises(TypeError, match="abstract method|instantiate"):
            BaseAgent(mock_llm, tools=[])

    def test_concrete_class_must_implement_run(self):
        """测试子类必须实现 run 方法"""
        from ai_agent.agents.base import BaseAgent

        class IncompleteAgent(BaseAgent):
            async def stream(self, message: str, *, context=None):
                yield  # type: ignore

            def get_graph(self):
                return None

        mock_llm = MagicMock(spec=BaseChatModel)
        with pytest.raises(TypeError):
            IncompleteAgent(mock_llm, tools=[])

    def test_concrete_class_must_implement_stream(self):
        """测试子类必须实现 stream 方法"""
        from ai_agent.agents.base import BaseAgent

        class IncompleteAgent(BaseAgent):
            async def run(self, message: str, *, context=None) -> str:
                return ""

            def get_graph(self):
                return None

        mock_llm = MagicMock(spec=BaseChatModel)
        with pytest.raises(TypeError):
            IncompleteAgent(mock_llm, tools=[])

    def test_concrete_class_must_implement_get_graph(self):
        """测试子类必须实现 get_graph 方法"""
        from ai_agent.agents.base import BaseAgent

        class IncompleteAgent(BaseAgent):
            async def run(self, message: str, *, context=None) -> str:
                return ""

            async def stream(self, message: str, *, context=None):
                yield  # type: ignore

        mock_llm = MagicMock(spec=BaseChatModel)
        with pytest.raises(TypeError):
            IncompleteAgent(mock_llm, tools=[])

    def test_complete_concrete_class_instantiates(self):
        """测试完整实现的子类可以实例化"""
        from ai_agent.agents.base import BaseAgent

        class CompleteAgent(BaseAgent):
            async def run(self, message: str, *, context=None) -> str:
                return f"Response to: {message}"

            async def stream(self, message: str, *, context=None):
                yield  # type: ignore

            def get_graph(self):
                return None

        mock_llm = MagicMock(spec=BaseChatModel)
        agent = CompleteAgent(mock_llm, tools=[])
        assert agent.llm == mock_llm


class TestBaseAgentToolMap:
    """测试 BaseAgent._tool_map 构建"""

    def test_tool_map_built_from_tools_list(self):
        """测试 _tool_map 从 tools 列表正确构建"""
        from ai_agent.agents.base import BaseAgent

        class ConcreteAgent(BaseAgent):
            async def run(self, message: str, *, context=None) -> str:
                return ""

            async def stream(self, message: str, *, context=None):
                yield  # type: ignore

            def get_graph(self):
                return None

        tool_a = MagicMock()
        tool_a.name = "search"
        tool_b = MagicMock()
        tool_b.name = "calculator"

        mock_llm = MagicMock(spec=BaseChatModel)
        agent = ConcreteAgent(mock_llm, tools=[tool_a, tool_b])

        assert "search" in agent._tool_map
        assert "calculator" in agent._tool_map
        assert agent._tool_map["search"] is tool_a
        assert agent._tool_map["calculator"] is tool_b

    def test_tool_map_empty_when_no_tools(self):
        """测试无工具时 _tool_map 为空"""
        from ai_agent.agents.base import BaseAgent

        class ConcreteAgent(BaseAgent):
            async def run(self, message: str, *, context=None) -> str:
                return ""

            async def stream(self, message: str, *, context=None):
                yield  # type: ignore

            def get_graph(self):
                return None

        mock_llm = MagicMock(spec=BaseChatModel)
        agent = ConcreteAgent(mock_llm, tools=[])

        assert agent._tool_map == {}
        assert len(agent._tool_map) == 0

    def test_tools_stored_as_list(self):
        """测试 tools 以列表形式存储"""
        from ai_agent.agents.base import BaseAgent

        class ConcreteAgent(BaseAgent):
            async def run(self, message: str, *, context=None) -> str:
                return ""

            async def stream(self, message: str, *, context=None):
                yield  # type: ignore

            def get_graph(self):
                return None

        tool = MagicMock()
        tool.name = "test_tool"

        mock_llm = MagicMock(spec=BaseChatModel)
        agent = ConcreteAgent(mock_llm, tools=[tool])

        assert len(agent.tools) == 1
        assert agent.tools[0] is tool


class TestBaseAgentContext:
    """测试 BaseAgent 接受 AgentContext"""

    def test_run_accepts_context_parameter(self):
        """测试 run 方法接受 context 关键字参数"""
        from ai_agent.agents.base import BaseAgent
        from ai_agent.types.agents import AgentContext

        class ConcreteAgent(BaseAgent):
            async def run(self, message: str, *, context=None) -> str:
                if context and context.system_prompt_override:
                    return f"Custom: {context.system_prompt_override}"
                return f"Default: {message}"

            async def stream(self, message: str, *, context=None):
                yield  # type: ignore

            def get_graph(self):
                return None

        mock_llm = MagicMock(spec=BaseChatModel)
        agent = ConcreteAgent(mock_llm, tools=[])
        ctx = AgentContext(system_prompt_override="Be concise")

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            agent.run("hello", context=ctx)
        )
        assert result == "Custom: Be concise"

    def test_run_context_defaults_to_none(self):
        """测试 run 方法的 context 默认为 None"""
        from ai_agent.agents.base import BaseAgent

        class ConcreteAgent(BaseAgent):
            async def run(self, message: str, *, context=None) -> str:
                return "ok"

            async def stream(self, message: str, *, context=None):
                yield  # type: ignore

            def get_graph(self):
                return None

        mock_llm = MagicMock(spec=BaseChatModel)
        agent = ConcreteAgent(mock_llm, tools=[])

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            agent.run("hello")
        )
        assert result == "ok"
