import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock


def test_react_action_model():
    """测试 ReActAction 模型"""
    from ai_agent.agents.react import ReActAction

    action = ReActAction(
        action="search",
        params={"query": "test"},
        memory="Found results",
    )

    assert action.action == "search"
    assert action.params == {"query": "test"}
    assert action.memory == "Found results"


def test_react_action_defaults():
    """测试 ReActAction 默认值"""
    from ai_agent.agents.react import ReActAction

    action = ReActAction(action="finish")

    assert action.params == {}
    assert action.memory == ""


def test_agent_state_model():
    """测试 AgentState 模型"""
    from ai_agent.agents.react import AgentState

    state = AgentState(question="What is the weather?")

    assert state.question == "What is the weather?"
    assert state.current_obs == ""
    assert state.steps_taken == 0
    assert state.actions_history == []
    assert state.final_answer is None
    assert state.error is None


def test_agent_state_with_history():
    """测试 AgentState 带历史记录"""
    from ai_agent.agents.react import AgentState, ReActAction

    state = AgentState(
        question="test",
        steps_taken=3,
        actions_history=[
            ReActAction(action="search", params={}, memory="step1"),
            ReActAction(action="read", params={}, memory="step2"),
        ],
    )

    assert len(state.actions_history) == 2
    assert state.steps_taken == 3


def test_build_action_space():
    """测试构建工具描述 - 新格式"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "calculator"
    mock_tool.description = "Performs calculations"
    mock_tool.parameters = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression"}
        },
        "required": ["expression"]
    }
    mock_tool.get_input_jsonschema.return_value = mock_tool.parameters

    agent = ReActAgent(mock_llm, tools=[mock_tool])
    action_space = agent._build_action_space()

    # 验证新格式
    assert "Available actions:" in action_space
    assert "### calculator" in action_space
    assert "Description: Performs calculations" in action_space
    assert "Parameters:" in action_space
    assert '"expression"' in action_space

    # 验证 finish 部分
    assert "### finish" in action_space
    assert '"result"' in action_space
    assert '"status"' in action_space
    assert '"done"' in action_space
    assert '"partial"' in action_space
    assert '"blocked"' in action_space


def test_build_action_space_empty():
    """测试无工具时的描述 - 新格式"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm, tools=[])

    action_space = agent._build_action_space()

    # 即使无工具，也应该包含 finish
    assert "Available actions:" in action_space
    assert "### finish" in action_space
    assert '"result"' in action_space


def test_parse_action_valid_json():
    """测试解析有效 JSON"""
    from ai_agent.agents.react import ReActAgent, ReActAction

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm)

    response = '{"action": "search", "params": {"q": "test"}, "memory": "found"}'
    result = agent._parse_action(response)

    assert result is not None
    assert result.action == "search"
    assert result.params == {"q": "test"}


def test_parse_action_json_block():
    """测试解析 JSON 代码块"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm)

    response = '''Here is my response:
```json
{"action": "finish", "params": {"answer": "42"}, "memory": "done"}
```
'''
    result = agent._parse_action(response)

    assert result is not None
    assert result.action == "finish"
    assert result.params == {"answer": "42"}


def test_parse_action_invalid():
    """测试解析无效响应"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm)

    result = agent._parse_action("This is not JSON at all")

    assert result is None


def test_find_tool():
    """测试查找工具"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_tool1 = MagicMock()
    mock_tool1.name = "search"
    mock_tool2 = MagicMock()
    mock_tool2.name = "calculator"

    agent = ReActAgent(mock_llm, tools=[mock_tool1, mock_tool2])

    found = agent._find_tool("calculator")
    assert found == mock_tool2

    not_found = agent._find_tool("unknown")
    assert not_found is None


@pytest.mark.asyncio
async def test_execute_with_retry_success():
    """测试成功执行"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_tool = MagicMock()
    mock_tool.ainvoke = AsyncMock(return_value="success result")

    agent = ReActAgent(mock_llm)
    result = await agent._execute_with_retry(mock_tool, {"input": "test"})

    assert result == "success result"


@pytest.mark.asyncio
async def test_execute_with_retry_failure():
    """测试失败后重试"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_tool = MagicMock()
    call_count = [0]

    async def failing_invoke(x):
        call_count[0] += 1
        raise Exception(f"Error on call {call_count[0]}")

    mock_tool.ainvoke = failing_invoke

    agent = ReActAgent(mock_llm, max_retries=2)
    result = await agent._execute_with_retry(mock_tool, {})

    assert "Error after 2 retries" in result
    assert call_count[0] == 2


@pytest.mark.asyncio
async def test_execute_with_retry_eventual_success():
    """测试重试后成功"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_tool = MagicMock()
    call_count = [0]

    async def eventual_success(x):
        call_count[0] += 1
        if call_count[0] < 3:
            raise Exception("Temporary error")
        return "eventual success"

    mock_tool.ainvoke = eventual_success

    agent = ReActAgent(mock_llm, max_retries=5)
    result = await agent._execute_with_retry(mock_tool, {})

    assert result == "eventual success"
    assert call_count[0] == 3


def test_react_agent_has_graph():
    """测试 Agent 有图"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm)

    graph = agent.get_graph()

    assert graph is not None


def test_react_agent_initialization_with_prompt():
    """测试带 Prompt 初始化"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.prompts import ReActPrompt

    mock_llm = MagicMock()
    prompt = ReActPrompt().with_task("Custom task")

    agent = ReActAgent(mock_llm, prompt=prompt)

    assert agent.prompt is not None
    assert "Custom task" in agent.prompt.format(
        original_question="test", action_space="test"
    )


@pytest.mark.asyncio
async def test_react_agent_run_finish_immediately():
    """测试 Agent 立即完成"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "42"}, "memory": "done"}')
    )

    agent = ReActAgent(mock_llm, tools=[], max_steps=5)
    result = await agent.run("What is the answer?")

    assert "42" in result


@pytest.mark.asyncio
async def test_react_agent_max_steps_limit():
    """测试最大步数限制"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    # 每次都返回调用工具（无限循环）
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "echo", "params": {}, "memory": "loop"}')
    )

    mock_tool = MagicMock()
    mock_tool.name = "echo"
    mock_tool.description = "Echo"
    mock_tool.ainvoke = AsyncMock(return_value="ok")

    agent = ReActAgent(mock_llm, tools=[mock_tool], max_steps=3)

    result = await agent.run("Infinite loop test")

    # 应该因为达到最大步数而停止
    assert result is not None


@pytest.mark.asyncio
async def test_react_agent_tool_execution():
    """测试工具执行"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    # 第一次调用工具，第二次完成
    responses = [
        MagicMock(content='{"action": "echo", "params": {"text": "hello"}, "memory": "called echo"}'),
        MagicMock(content='{"action": "finish", "params": {"answer": "done"}, "memory": "completed"}'),
    ]
    mock_llm.ainvoke = AsyncMock(side_effect=responses)

    mock_tool = MagicMock()
    mock_tool.name = "echo"
    mock_tool.description = "Echo back input"
    mock_tool.ainvoke = AsyncMock(return_value="Echo: hello")

    agent = ReActAgent(mock_llm, tools=[mock_tool], max_steps=5)
    result = await agent.run("Test echo")

    assert "done" in result
