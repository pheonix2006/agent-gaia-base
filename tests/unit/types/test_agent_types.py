"""AgentState and AgentContext type tests"""

from __future__ import annotations

import pytest
from typing import get_type_hints
from langchain_core.messages import BaseMessage, HumanMessage


class TestAgentState:
    """Test AgentState TypedDict structure"""

    def test_agent_state_is_typed_dict(self):
        """AgentState should be a TypedDict"""
        from typing import TypedDict, get_type_hints

        from ai_agent.types.agents import AgentState

        # TypedDict classes have __annotations__ and are subclasses of dict
        assert issubclass(AgentState, dict)

    def test_agent_state_has_messages_field(self):
        """AgentState should have a messages field with Annotated type"""
        from ai_agent.types.agents import AgentState

        annotations = AgentState.__annotations__
        assert "messages" in annotations

    def test_agent_state_has_step_count_field(self):
        """AgentState should have a step_count field"""
        from ai_agent.types.agents import AgentState

        annotations = AgentState.__annotations__
        assert "step_count" in annotations

    def test_agent_state_can_be_created_with_dict(self):
        """AgentState should accept dict-style construction"""
        from ai_agent.types.agents import AgentState

        state: AgentState = {
            "messages": [HumanMessage(content="hello")],
            "step_count": 0,
        }
        assert state["messages"][0].content == "hello"
        assert state["step_count"] == 0

    def test_agent_state_messages_accepts_list_of_base_message(self):
        """AgentState messages should accept a list of BaseMessage instances"""
        from ai_agent.types.agents import AgentState

        messages = [
            HumanMessage(content="first"),
            HumanMessage(content="second"),
        ]
        state: AgentState = {
            "messages": messages,
            "step_count": 3,
        }
        assert len(state["messages"]) == 2
        assert state["step_count"] == 3

    def test_agent_state_messages_annotated_with_add_messages(self):
        """AgentState messages field should be annotated with add_messages reducer"""
        from typing import Annotated, get_type_hints

        from ai_agent.types.agents import AgentState
        from langgraph.graph.message import add_messages

        # The annotation should be Annotated[list[BaseMessage], add_messages]
        # We verify by checking that the type hint resolves
        hints = get_type_hints(AgentState, include_extras=True)
        assert "messages" in hints
        # The hint should be an Annotated type with add_messages as metadata
        msg_hint = hints["messages"]
        assert hasattr(msg_hint, "__metadata__"), "messages should be Annotated"
        assert add_messages in msg_hint.__metadata__, "messages should use add_messages reducer"


class TestAgentContext:
    """Test AgentContext dataclass"""

    def test_agent_context_import(self):
        """AgentContext should be importable"""
        from ai_agent.types.agents import AgentContext
        assert AgentContext is not None

    def test_agent_context_default_values(self):
        """AgentContext should have None defaults for optional fields"""
        from ai_agent.types.agents import AgentContext

        ctx = AgentContext()
        assert ctx.system_prompt_override is None
        assert ctx.memory_text is None
        assert ctx.max_steps_override is None

    def test_agent_context_with_system_prompt_override(self):
        """AgentContext should accept system_prompt_override"""
        from ai_agent.types.agents import AgentContext

        ctx = AgentContext(system_prompt_override="You are a helpful assistant.")
        assert ctx.system_prompt_override == "You are a helpful assistant."
        assert ctx.memory_text is None
        assert ctx.max_steps_override is None

    def test_agent_context_with_all_fields(self):
        """AgentContext should accept all fields at once"""
        from ai_agent.types.agents import AgentContext

        ctx = AgentContext(
            system_prompt_override="Custom prompt",
            memory_text="Previous conversation summary",
            max_steps_override=5,
        )
        assert ctx.system_prompt_override == "Custom prompt"
        assert ctx.memory_text == "Previous conversation summary"
        assert ctx.max_steps_override == 5

    def test_agent_context_is_frozen_safe(self):
        """AgentContext should be mutable (not frozen) - it's a plain dataclass"""
        from ai_agent.types.agents import AgentContext

        ctx = AgentContext()
        ctx.system_prompt_override = "new prompt"
        assert ctx.system_prompt_override == "new prompt"
