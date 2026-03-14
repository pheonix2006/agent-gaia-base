# tests/integration/test_memory_integration.py
"""Memory 集成测试 - 验证真实流程中的 memory 注入"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import List, Dict, Any
from datetime import datetime


class LLMCallCapture:
    """捕获 LLM 调用的 prompt 内容"""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def capture(self, messages: List) -> None:
        """记录每次 LLM 调用"""
        self.calls.append({
            "messages": [m.content for m in messages],
            "timestamp": datetime.now(),
        })


@pytest.fixture
def llm_capture():
    return LLMCallCapture()


@pytest.fixture
def mock_tool():
    """创建模拟工具"""
    tool = MagicMock()
    tool.name = "search"
    tool.description = "Search for information"
    tool.ainvoke = AsyncMock(return_value="Search results: ...")
    return tool


def extract_memory_section(prompt: str) -> str:
    """从 prompt 中提取 memory 部分"""
    import re
    match = re.search(r'==== Memory ====\n(.*?)\n==== Current Observation ====', prompt, re.DOTALL)
    if match:
        return match.group(1).strip()
    return "NOT FOUND"


@pytest.mark.asyncio
async def test_memory_integration_first_step_is_none(llm_capture, mock_tool):
    """集成测试：第一步 memory 应该是 None"""
    from ai_agent.agents.react import ReActAgent

    # 创建带捕获的 mock LLM
    mock_llm = MagicMock()

    async def capture_and_respond(messages):
        llm_capture.capture(messages)
        return MagicMock(content='{"action": "finish", "params": {"answer": "done"}, "memory": "completed"}')

    mock_llm.ainvoke = capture_and_respond

    agent = ReActAgent(mock_llm, tools=[mock_tool], create_memory=True)

    await agent.run("Test question")

    # 分析第一次 LLM 调用
    assert len(llm_capture.calls) >= 1

    first_prompt = llm_capture.calls[0]["messages"][0]
    memory_section = extract_memory_section(first_prompt)

    assert memory_section == "None", f"First step memory should be 'None', got: {memory_section}"


@pytest.mark.asyncio
async def test_memory_integration_records_observations(llm_capture, mock_tool):
    """集成测试：memory 记录观察结果"""
    from ai_agent.agents.react import ReActAgent

    call_count = [0]

    async def capture_and_respond(messages):
        llm_capture.capture(messages)
        call_count[0] += 1

        if call_count[0] == 1:
            # 第一次调用工具
            return MagicMock(content='{"action": "search", "params": {"q": "test"}, "memory": "searching"}')
        else:
            # 第二次完成
            return MagicMock(content='{"action": "finish", "params": {"answer": "found"}, "memory": "done"}')

    mock_llm = MagicMock()
    mock_llm.ainvoke = capture_and_respond

    agent = ReActAgent(mock_llm, tools=[mock_tool], create_memory=True)

    await agent.run("Test question")

    # 验证 memory 有记录
    assert agent._memory.record_count > 0, "Memory should have records after multi-step execution"


@pytest.mark.asyncio
async def test_memory_integration_second_step_has_content(llm_capture, mock_tool):
    """集成测试：第二步 memory 应该包含之前的内容"""
    from ai_agent.agents.react import ReActAgent

    call_count = [0]

    async def capture_and_respond(messages):
        llm_capture.capture(messages)
        call_count[0] += 1

        if call_count[0] == 1:
            return MagicMock(content='{"action": "search", "params": {"q": "test"}, "memory": "searching"}')
        else:
            return MagicMock(content='{"action": "finish", "params": {"answer": "found"}, "memory": "done"}')

    mock_llm = MagicMock()
    mock_llm.ainvoke = capture_and_respond

    agent = ReActAgent(mock_llm, tools=[mock_tool], create_memory=True)

    await agent.run("Test question")

    # 分析第二次 LLM 调用
    assert len(llm_capture.calls) >= 2

    second_prompt = llm_capture.calls[1]["messages"][0]
    memory_section = extract_memory_section(second_prompt)

    # 第二步 memory 不应该是 None
    assert memory_section != "None", f"Second step memory should not be 'None', got: {memory_section}"
    # 应该包含 "Recent" 或类似标记
    assert "Recent" in memory_section or "action" in memory_section.lower(), \
        f"Memory should contain recent steps info: {memory_section}"


@pytest.mark.asyncio
async def test_memory_integration_compression_trigger():
    """集成测试：达到阈值时触发压缩"""
    from ai_agent.agents.react import ReActAgent
    from ai_agent.memory import CompressedMemory

    mock_llm = MagicMock()

    call_count = [0]

    async def respond_with_tool_call(messages):
        call_count[0] += 1
        if call_count[0] < 12:
            return MagicMock(content='{"action": "search", "params": {}, "memory": "step ' + str(call_count[0]) + '"}')
        else:
            return MagicMock(content='{"action": "finish", "params": {"answer": "done"}, "memory": "completed"}')

    mock_llm.ainvoke = respond_with_tool_call

    # 使用低阈值便于测试
    # max_memory=5: 当记录数达到 5 时触发压缩
    # keep_recent=2: 压缩后保留最近 2 条，其余转为摘要
    memory = CompressedMemory(mock_llm, max_memory=5, keep_recent=2)

    mock_tool = MagicMock()
    mock_tool.name = "search"
    mock_tool.ainvoke = AsyncMock(return_value="result")

    agent = ReActAgent(mock_llm, tools=[mock_tool], memory=memory, max_steps=15)

    await agent.run("Long task")

    # 验证压缩被触发：应该有摘要
    assert memory.has_summary, "Memory should have summary after compression"
    # 压缩后记录数应不超过 max_memory（因为每次压缩后会继续添加）
    # 实际行为：每次达到 max_memory 就压缩，保留 keep_recent 条
    # 最终记录数 = (总步数 % (max_memory - keep_recent)) + keep_recent 左右
    # 对于 11 步，max_memory=5, keep_recent=2：
    # - 第 5 条触发压缩，保留 2 条
    # - 继续添加第 6,7,8,9,10 条，第 10 条触发压缩，保留 2 条
    # - 添加第 11 条（finish），最终有 3 条
    assert memory.record_count <= memory.max_memory, \
        f"Records should be <= max_memory ({memory.max_memory}), got: {memory.record_count}"


@pytest.mark.asyncio
async def test_memory_detailed_prompt_analysis():
    """详细分析每次 LLM 调用的 prompt 内容"""
    from ai_agent.agents.react import ReActAgent

    calls_log = []

    mock_llm = MagicMock()

    async def log_and_respond(messages):
        prompt = messages[0].content
        memory = extract_memory_section(prompt)

        calls_log.append({
            "call_number": len(calls_log) + 1,
            "memory_content": memory,
            "memory_length": len(memory),
        })

        if len(calls_log) < 3:
            return MagicMock(content='{"action": "search", "params": {}, "memory": "thinking..."}')
        else:
            return MagicMock(content='{"action": "finish", "params": {"answer": "done"}, "memory": "done"}')

    mock_llm.ainvoke = log_and_respond

    mock_tool = MagicMock()
    mock_tool.name = "search"
    mock_tool.ainvoke = AsyncMock(return_value="search result")

    agent = ReActAgent(mock_llm, tools=[mock_tool], create_memory=True)

    await agent.run("Multi-step task")

    # 输出详细分析
    print("\n" + "=" * 60)
    print("MEMORY INTEGRATION ANALYSIS")
    print("=" * 60)

    for call in calls_log:
        print(f"\n--- LLM Call #{call['call_number']} ---")
        print(f"Memory length: {call['memory_length']} chars")
        print(f"Memory content:\n{call['memory_content'][:500]}...")
        print("-" * 40)

    # 验证：第一次是 None，后续有内容
    assert calls_log[0]["memory_content"] == "None"
    for call in calls_log[1:]:
        assert call["memory_content"] != "None"
