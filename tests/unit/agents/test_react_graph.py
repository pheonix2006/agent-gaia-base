# tests/unit/agents/test_react_graph.py
"""ReActAgent 图结构与节点单元测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import AIMessage, ToolMessage

from ai_agent.agents.react.graph import ReActAgent
from langgraph.graph import END


@pytest.fixture
def mock_llm():
    """创建 mock LLM"""
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


@pytest.fixture
def mock_tool():
    """创建 mock BaseAgentTool"""
    from pydantic import BaseModel

    class CalcParams(BaseModel):
        expression: str

    tool = MagicMock()
    tool.name = "calculator"
    tool.description = "Performs calculations"
    tool.params_schema = CalcParams
    tool.to_langchain_tool.return_value = MagicMock(
        name="calculator",
        description="Performs calculations",
    )
    return tool


class TestBuildGraph:
    """测试 _build_graph 生成的图结构"""

    def test_graph_has_agent_node(self, mock_llm, mock_tool):
        """图应包含 'agent' 节点"""
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        graph = agent.get_graph()
        node_names = list(graph.nodes.keys())
        assert "agent" in node_names

    def test_graph_has_tools_node(self, mock_llm, mock_tool):
        """图应包含 'tools' 节点"""
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        graph = agent.get_graph()
        node_names = list(graph.nodes.keys())
        assert "tools" in node_names

    def test_graph_has_only_two_core_nodes(self, mock_llm, mock_tool):
        """图应恰好有 2 个核心节点（agent + tools），不含旧的 think/act/observe"""
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        graph = agent.get_graph()
        node_names = list(graph.nodes.keys())
        core_nodes = [n for n in node_names if not n.startswith("__")]
        assert set(core_nodes) == {"agent", "tools"}

    def test_graph_compiles_successfully(self, mock_llm, mock_tool):
        """图应能成功编译"""
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        graph = agent.get_graph()
        assert graph is not None

    def test_init_binds_tools_to_llm(self, mock_llm, mock_tool):
        """初始化时应调用 llm.bind_tools()"""
        ReActAgent(mock_llm, tools=[mock_tool])
        mock_llm.bind_tools.assert_called_once()

    def test_init_creates_tool_map(self, mock_llm, mock_tool):
        """初始化时应创建 _tool_map"""
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        assert "calculator" in agent._tool_map
        assert agent._tool_map["calculator"] == mock_tool

    def test_default_max_steps(self, mock_llm, mock_tool):
        """默认 max_steps 应为 20"""
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        assert agent.max_steps == 20

    def test_custom_max_steps(self, mock_llm, mock_tool):
        """应支持自定义 max_steps"""
        agent = ReActAgent(mock_llm, tools=[mock_tool], max_steps=5)
        assert agent.max_steps == 5

    def test_default_system_prompt(self, mock_llm, mock_tool):
        """不传 system_prompt 时应使用默认值"""
        agent = ReActAgent(mock_llm, tools=[mock_tool])
        assert agent.system_prompt
        assert "AI" in agent.system_prompt or "助手" in agent.system_prompt

    def test_custom_system_prompt(self, mock_llm, mock_tool):
        """应支持自定义 system_prompt"""
        agent = ReActAgent(
            mock_llm, tools=[mock_tool], system_prompt="Custom prompt"
        )
        assert agent.system_prompt == "Custom prompt"


class TestAgentNode:
    """测试 _agent_node"""

    async def test_agent_node_returns_llm_response(self, mock_llm, mock_tool):
        """_agent_node 应调用 LLM 并返回消息"""
        ai_response = AIMessage(content="Hello!")
        mock_llm.ainvoke = AsyncMock(return_value=ai_response)
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        agent = ReActAgent(mock_llm, tools=[mock_tool])
        state = {"messages": [], "step_count": 0}
        result = await agent._agent_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "Hello!"

    async def test_agent_node_passes_state_messages_to_llm(
        self, mock_llm, mock_tool
    ):
        """_agent_node 应将 state['messages'] 传给 LLM"""
        from langchain_core.messages import HumanMessage

        ai_response = AIMessage(content="response")
        mock_llm.ainvoke = AsyncMock(return_value=ai_response)
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        agent = ReActAgent(mock_llm, tools=[mock_tool])
        messages = [HumanMessage(content="test")]
        state = {"messages": messages, "step_count": 0}
        await agent._agent_node(state)

        mock_llm.ainvoke.assert_called_once_with(messages)


class TestToolNode:
    """测试 _tool_node"""

    async def test_tool_node_executes_tool(self, mock_llm, mock_tool):
        """_tool_node 应执行工具并返回 ToolMessage"""
        from ai_agent.types import ToolResult

        mock_tool.run = AsyncMock(return_value=ToolResult(success=True, data="42"))
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "calculator", "args": {"expression": "6*7"}, "id": "tc_1"}
            ],
        )
        state = {"messages": [ai_msg], "step_count": 0}
        result = await agent._tool_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], ToolMessage)
        assert result["messages"][0].content == "42"
        assert result["messages"][0].tool_call_id == "tc_1"
        assert result["step_count"] == 1

    async def test_tool_node_handles_unknown_tool(self, mock_llm, mock_tool):
        """_tool_node 对未知工具应返回错误 ToolMessage"""
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "nonexistent", "args": {}, "id": "tc_2"}],
        )
        state = {"messages": [ai_msg], "step_count": 0}
        result = await agent._tool_node(state)

        assert len(result["messages"]) == 1
        assert "unknown tool" in result["messages"][0].content
        assert result["messages"][0].status == "error"

    async def test_tool_node_handles_tool_error(self, mock_llm, mock_tool):
        """_tool_node 对工具执行异常应返回错误 ToolMessage"""
        mock_tool.run = AsyncMock(side_effect=ValueError("bad params"))
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "calculator", "args": {"expression": "bad"}, "id": "tc_3"}
            ],
        )
        state = {"messages": [ai_msg], "step_count": 5}
        result = await agent._tool_node(state)

        assert len(result["messages"]) == 1
        assert "Error executing tool" in result["messages"][0].content
        assert result["messages"][0].status == "error"
        assert result["step_count"] == 6

    async def test_tool_node_handles_multiple_tool_calls(self, mock_llm, mock_tool):
        """_tool_node 应处理单条消息中的多个 tool_calls"""
        from ai_agent.types import ToolResult

        mock_tool.run = AsyncMock(return_value=ToolResult(success=True, data="ok"))
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "calculator", "args": {"expression": "1+1"}, "id": "tc_a"},
                {"name": "calculator", "args": {"expression": "2+2"}, "id": "tc_b"},
            ],
        )
        state = {"messages": [ai_msg], "step_count": 0}
        result = await agent._tool_node(state)

        assert len(result["messages"]) == 2
        assert result["messages"][0].tool_call_id == "tc_a"
        assert result["messages"][1].tool_call_id == "tc_b"

    async def test_tool_node_serializes_dict_result(self, mock_llm, mock_tool):
        """_tool_node 对 dict 类型的工具结果应序列化为 JSON"""
        from ai_agent.types import ToolResult

        mock_tool.run = AsyncMock(
            return_value=ToolResult(success=True, data={"answer": 42})
        )
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "calculator", "args": {"expression": "meaning"}, "id": "tc_4"}
            ],
        )
        state = {"messages": [ai_msg], "step_count": 0}
        result = await agent._tool_node(state)

        import json

        parsed = json.loads(result["messages"][0].content)
        assert parsed == {"answer": 42}


class TestShouldContinue:
    """测试 _should_continue 条件边逻辑"""

    def test_returns_tools_when_tool_calls_present(self, mock_llm, mock_tool):
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {}, "id": "tc_1"}],
        )
        state = {"messages": [ai_msg], "step_count": 0}
        assert agent._should_continue(state) == "tools"

    def test_returns_end_when_no_tool_calls(self, mock_llm, mock_tool):
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        ai_msg = AIMessage(content="The answer is 42.")
        state = {"messages": [ai_msg], "step_count": 0}
        assert agent._should_continue(state) == END

    def test_returns_end_when_max_steps_reached(self, mock_llm, mock_tool):
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool], max_steps=3)

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {}, "id": "tc_1"}],
        )
        state = {"messages": [ai_msg], "step_count": 3}
        assert agent._should_continue(state) == END

    def test_returns_end_when_step_count_exceeds_max(self, mock_llm, mock_tool):
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool], max_steps=5)

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {}, "id": "tc_1"}],
        )
        state = {"messages": [ai_msg], "step_count": 10}
        assert agent._should_continue(state) == END

    def test_continues_when_below_max_steps(self, mock_llm, mock_tool):
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool], max_steps=3)

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {}, "id": "tc_1"}],
        )
        state = {"messages": [ai_msg], "step_count": 2}
        assert agent._should_continue(state) == "tools"

    def test_handles_missing_step_count(self, mock_llm, mock_tool):
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {}, "id": "tc_1"}],
        )
        state = {"messages": [ai_msg]}
        assert agent._should_continue(state) == "tools"


class TestUpdateTools:
    """测试 update_tools 运行时工具更新"""

    def test_update_tools_rebuilds_tool_map(self, mock_llm, mock_tool):
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        new_tool = MagicMock()
        new_tool.name = "search"
        new_tool.description = "Search the web"
        new_tool.to_langchain_tool.return_value = MagicMock(name="search")

        agent.update_tools([new_tool])
        assert "search" in agent._tool_map
        assert "calculator" not in agent._tool_map

    def test_update_tools_rebinds_llm(self, mock_llm, mock_tool):
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        initial_call_count = mock_llm.bind_tools.call_count

        new_tool = MagicMock()
        new_tool.name = "search"
        new_tool.description = "Search"
        new_tool.to_langchain_tool.return_value = MagicMock(name="search")

        agent.update_tools([new_tool])
        assert mock_llm.bind_tools.call_count == initial_call_count + 1

    def test_update_tools_updates_tools_list(self, mock_llm, mock_tool):
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        agent = ReActAgent(mock_llm, tools=[mock_tool])

        new_tool = MagicMock()
        new_tool.name = "search"
        new_tool.description = "Search"
        new_tool.to_langchain_tool.return_value = MagicMock(name="search")

        agent.update_tools([new_tool])
        assert agent.tools == [new_tool]
