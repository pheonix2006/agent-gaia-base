"""ReAct Agent 真实 API 测试 - 需要真实 API Key"""

import os
import pytest

# 跳过条件：没有真实 API Key
requires_real_api = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-api-key",
    reason="需要真实的 OPENAI_API_KEY"
)


@pytest.fixture
def real_tools():
    """创建真实可用的测试工具"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class CalculatorTool(BaseAgentTool):
        @property
        def name(self) -> str:
            return "calculator"

        @property
        def description(self) -> str:
            return "Perform basic arithmetic. Input should be a math expression like '2+2'."

        def run(self, expression: str) -> ToolResult:
            try:
                # 安全的数学计算（仅允许基本运算）
                allowed = set("0123456789+-*/(). ")
                if not all(c in allowed for c in expression):
                    return ToolResult(success=False, data="", error="Invalid characters")
                result = eval(expression)
                return ToolResult(success=True, data=str(result))
            except Exception as e:
                return ToolResult(success=False, data="", error=str(e))

    class EchoTool(BaseAgentTool):
        @property
        def name(self) -> str:
            return "echo"

        @property
        def description(self) -> str:
            return "Echo back the input text."

        def run(self, text: str) -> ToolResult:
            return ToolResult(success=True, data=f"Echo: {text}")

    return [CalculatorTool().to_langchain_tool(), EchoTool().to_langchain_tool()]


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_real_react_agent_simple_math(real_tools):
    """测试真实 ReAct Agent - 简单数学"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.agents.react import ReActAgent

    llm = create_llm_client()
    agent = ReActAgent(llm, tools=real_tools, max_steps=10)

    result = await agent.run("What is 15 + 27? Use the calculator tool.")

    assert result is not None
    assert "42" in result


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_real_react_agent_echo(real_tools):
    """测试真实 ReAct Agent - Echo 工具"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.agents.react import ReActAgent

    llm = create_llm_client()
    agent = ReActAgent(llm, tools=real_tools, max_steps=5)

    result = await agent.run("Use the echo tool to say 'Hello World'")

    assert result is not None
    assert "Hello World" in result or "Echo" in result


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_real_react_agent_no_tools():
    """测试真实 ReAct Agent - 无工具直接回答"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.agents.react import ReActAgent

    llm = create_llm_client()
    agent = ReActAgent(llm, tools=[], max_steps=3)

    result = await agent.run("What is the capital of France?")

    assert result is not None
    assert "Paris" in result


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_real_react_agent_custom_prompt(real_tools):
    """测试真实 ReAct Agent - 自定义 Prompt"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.agents.react import ReActAgent
    from ai_agent.prompts import ReActPrompt

    llm = create_llm_client()
    prompt = ReActPrompt().with_task(
        "You are a helpful math assistant. Always use the calculator for calculations."
    )

    agent = ReActAgent(llm, tools=real_tools, prompt=prompt, max_steps=10)

    result = await agent.run("Calculate 100 / 4")

    assert result is not None
    assert "25" in result


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_real_react_agent_memory_integration(real_tools):
    """测试真实 ReAct Agent - Memory 集成"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.agents.react import ReActAgent
    from ai_agent.memory import CompressedMemory

    llm = create_llm_client()
    memory = CompressedMemory(llm, max_memory=5, keep_recent=2)

    # 当前单轮不使用 memory，但验证可以创建
    agent = ReActAgent(llm, tools=real_tools, max_steps=5)

    result = await agent.run("What is 2 * 3?")

    assert result is not None
    assert "6" in result
