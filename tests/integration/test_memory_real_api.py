# tests/integration/test_memory_real_api.py
"""真实 API 测试 - 需要 API Key"""

import pytest
import os


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") == "test-api-key",
    reason="Requires real OPENAI_API_KEY"
)
@pytest.mark.asyncio
async def test_memory_with_real_llm():
    """使用真实 LLM 测试 memory 功能"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.llm.client import create_llm_client
    from ai_agent.memory import CompressedMemory
    from unittest.mock import MagicMock, AsyncMock

    llm = create_llm_client()
    memory = CompressedMemory(llm, max_memory=5, keep_recent=2)

    # 创建简单的 mock 工具
    mock_tool = MagicMock()
    mock_tool.name = "echo"
    mock_tool.description = "Echo back the input"
    mock_tool.ainvoke = AsyncMock(return_value="Echo: test")

    agent = ReActAgent(llm, tools=[mock_tool], memory=memory, max_steps=5)

    result = await agent.run("Please echo 'hello' and then finish")

    print(f"\nResult: {result}")
    print(f"Memory records: {memory.record_count}")
    print(f"Memory has summary: {memory.has_summary}")
    print(f"\nMemory text:\n{memory.as_text()}")

    assert result is not None
