"""ReAct Agent 集成测试"""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_llm_with_tools():
    """创建完整的模拟环境"""
    from ai_agent.prompts import ReActPrompt

    llm = MagicMock()

    # 模拟 LLM 响应序列
    responses = [
        # 第一次：调用工具
        MagicMock(content='{"action": "echo", "params": {"text": "hello"}, "memory": "Testing echo tool"}'),
        # 第二次：完成
        MagicMock(content='{"action": "finish", "params": {"answer": "Task completed"}, "memory": "Done"}'),
    ]
    llm.ainvoke = AsyncMock(side_effect=responses)

    # 模拟工具
    echo_tool = MagicMock()
    echo_tool.name = "echo"
    echo_tool.description = "Echo back the input"
    echo_tool.ainvoke = AsyncMock(return_value="Echo: hello")

    return llm, [echo_tool], ReActPrompt()


@pytest.mark.asyncio
async def test_react_agent_full_flow(mock_llm_with_tools):
    """测试完整的 ReAct 流程"""
    from ai_agent.agents.react import ReActAgent

    llm, tools, prompt = mock_llm_with_tools

    agent = ReActAgent(llm, tools=tools, prompt=prompt, max_steps=5)

    result = await agent.run("Test the echo tool")

    assert result == "Task completed"
    assert llm.ainvoke.call_count == 2  # think 被调用两次


@pytest.mark.asyncio
async def test_react_agent_max_steps():
    """测试最大步数限制"""
    from ai_agent.agents.react import ReActAgent

    llm = MagicMock()
    # 每次都返回调用工具（无限循环）
    llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "echo", "params": {}, "memory": "loop"}')
    )

    echo_tool = MagicMock()
    echo_tool.name = "echo"
    echo_tool.description = "Echo"
    echo_tool.ainvoke = AsyncMock(return_value="ok")

    agent = ReActAgent(llm, tools=[echo_tool], max_steps=3)

    result = await agent.run("Infinite loop test")

    # 应该因为达到最大步数而停止
    assert result is not None


@pytest.mark.asyncio
async def test_react_agent_tool_not_found():
    """测试工具不存在的情况"""
    from ai_agent.agents.react import ReActAgent

    llm = MagicMock()
    responses = [
        MagicMock(content='{"action": "unknown_tool", "params": {}, "memory": "Trying unknown"}'),
        MagicMock(content='{"action": "finish", "params": {"answer": "Handled error"}, "memory": "Done"}'),
    ]
    llm.ainvoke = AsyncMock(side_effect=responses)

    agent = ReActAgent(llm, tools=[], max_steps=5)

    result = await agent.run("Use non-existent tool")

    assert "Handled error" in result


@pytest.mark.asyncio
async def test_react_agent_with_custom_prompt():
    """测试自定义 Prompt"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.prompts import ReActPrompt

    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        return_value=MagicMock(content='{"action": "finish", "params": {"answer": "ok"}, "memory": "done"}')
    )

    prompt = ReActPrompt().with_task("You are a math solver").with_context("Solve math problems only")

    agent = ReActAgent(llm, tools=[], prompt=prompt)

    result = await agent.run("What is 1+1?")

    # 验证 prompt 被正确使用
    call_args = llm.ainvoke.call_args[0][0]
    prompt_text = call_args[0].content
    assert "math solver" in prompt_text
    assert "Solve math problems only" in prompt_text
