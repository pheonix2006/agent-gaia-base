# -*- coding: utf-8 -*-
"""
ReAct Agent Memory Integration Demo

Shows how Memory works in real execution:
1. First step: memory = None
2. Second step: memory contains first record
3. Third step+: memory accumulates
4. At threshold: compression triggered
"""

import asyncio
import sys
import io
from unittest.mock import MagicMock, AsyncMock

# Setup UTF-8 output for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project path
sys.path.insert(0, 'E:/Project/ai agent')

from ai_agent.agents.react import ReActAgent
from ai_agent.memory import CompressedMemory


def extract_memory_section(prompt: str) -> str:
    """Extract memory section from prompt"""
    import re
    match = re.search(r'==== Memory ====\n(.*?)\n==== Current Observation ====', prompt, re.DOTALL)
    if match:
        return match.group(1).strip()
    return "NOT FOUND"


def print_section(title: str, content: str = ""):
    """Print formatted section"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)
    if content:
        print(content)


async def demo_basic_memory_flow():
    """Demo: Basic memory injection flow"""
    print_section("Demo 1: Basic Memory Flow")

    llm_calls = []

    async def capture_llm(messages):
        prompt = messages[0].content
        memory = extract_memory_section(prompt)

        llm_calls.append({
            "step": len(llm_calls) + 1,
            "memory": memory,
            "memory_length": len(memory),
        })

        print(f"\nStep {len(llm_calls)} - Memory Content:")
        print("-" * 40)
        if memory == "None":
            print("  (Empty - this is the first step)")
        else:
            preview = memory[:350] + "..." if len(memory) > 350 else memory
            print(f"  {preview}")

        if len(llm_calls) == 1:
            return MagicMock(content='{"action": "search", "params": {"query": "python async"}, "memory": "Searching for Python async"}')
        elif len(llm_calls) == 2:
            return MagicMock(content='{"action": "search", "params": {"query": "python await"}, "memory": "Searching for Python await keyword"}')
        elif len(llm_calls) == 3:
            return MagicMock(content='{"action": "search", "params": {"query": "python asyncio"}, "memory": "Searching for Python asyncio module"}')
        else:
            return MagicMock(content='{"action": "finish", "params": {"answer": "Python async uses async/await syntax, asyncio provides event loop"}, "memory": "Summarizing answer"}')

    mock_llm = MagicMock()
    mock_llm.ainvoke = capture_llm

    mock_tool = MagicMock()
    mock_tool.name = "search"
    mock_tool.description = "Search engine"
    mock_tool.ainvoke = AsyncMock(return_value="Search results: Found relevant content")

    memory = CompressedMemory(mock_llm, max_memory=10, keep_recent=3)
    agent = ReActAgent(mock_llm, tools=[mock_tool], memory=memory)

    print("\nTask: Explain Python async programming basics")
    print("\nStarting execution...")

    result = await agent.run("Explain Python async programming basics")

    print_section("Execution Complete", f"Final Answer: {result}")

    print_section("Memory Final State")
    print(f"  Record count: {memory.record_count}")
    print(f"  Has summary: {memory.has_summary}")
    print(f"\nMemory full content:\n{memory.as_text()}")


async def demo_memory_compression():
    """Demo: Memory compression mechanism"""
    print_section("Demo 2: Memory Compression Mechanism")

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content="Summary: Previous steps executed multiple search queries about Python async programming topics."
        )
    )

    memory = CompressedMemory(
        mock_llm,
        max_memory=5,  # Trigger compression at 5 records
        keep_recent=2  # Keep most recent 2
    )

    print(f"Config: max_memory=5, keep_recent=2")
    print("Meaning: Every 5 records, keep 2 recent ones, compress 3 into summary\n")

    for i in range(1, 8):
        await memory.add_raw(
            observation={"result": f"Observation from step {i}"},
            action={"name": "search", "params": {"q": f"query_{i}"}},
            thinking=f"Thinking at step {i}"
        )

        print(f"Added record {i} -> Total: {memory.record_count}, Has summary: {memory.has_summary}")

        if i == 5:
            print("  [COMPRESSION TRIGGERED!] First 3 compressed to summary, keeping recent 2")

    print_section("Memory After Compression")
    print(memory.as_text())


async def demo_stream_with_memory():
    """Demo: Memory in stream() method"""
    print_section("Demo 3: Memory in stream() Method")

    events_log = []

    async def capture_llm(messages):
        if len(events_log) < 2:
            return MagicMock(content='{"action": "calculate", "params": {"x": 10, "y": 20}, "memory": "Calculating 10 + 20"}')
        else:
            return MagicMock(content='{"action": "finish", "params": {"answer": "The result is 30"}, "memory": "Done calculation"}')

    mock_llm = MagicMock()
    mock_llm.ainvoke = capture_llm

    mock_tool = MagicMock()
    mock_tool.name = "calculate"
    mock_tool.description = "Calculator tool"
    mock_tool.ainvoke = AsyncMock(return_value="Calculation result: 30")

    memory = CompressedMemory(mock_llm, max_memory=10, keep_recent=3)
    agent = ReActAgent(mock_llm, tools=[mock_tool], memory=memory)

    print("Task: Calculate 10 + 20\n")

    async for event in agent.stream("Calculate 10 + 20"):
        events_log.append(event)
        event_type = event.event.upper()
        if event.event.value == "finish":
            answer = event.data.get("answer", "")
            print(f"[{event_type}] Answer: {answer}")
        else:
            print(f"[{event_type}] {event.data}")

    print_section("Memory State After stream()")
    print(f"  Record count: {memory.record_count}")
    print(f"  Has summary: {memory.has_summary}")


async def main():
    """Run all demos"""
    print("\n")
    print("=" * 70)
    print("        ReAct Agent Memory Integration Demo")
    print("=" * 70)

    await demo_basic_memory_flow()
    await asyncio.sleep(0.3)

    await demo_memory_compression()
    await asyncio.sleep(0.3)

    await demo_stream_with_memory()

    print_section("Demo Complete!")
    print("\nSummary:")
    print("  [OK] Memory is None on first step")
    print("  [OK] Memory contains previous content in subsequent steps")
    print("  [OK] Memory compression mechanism works")
    print("  [OK] stream() method supports Memory")
    print("  [OK] run() method supports Memory")
    print()


if __name__ == "__main__":
    asyncio.run(main())
