# tests/unit/memory/test_base.py
import pytest


def test_memory_record_model():
    """测试 MemoryRecord 模型"""
    from ai_agent.memory.base import MemoryRecord

    record = MemoryRecord(
        observation={"result": "success"},
        action={"name": "search", "params": {"query": "test"}},
        thinking="Need to search for test",
        reward=1.0,
    )

    assert record.observation == {"result": "success"}
    assert record.action == {"name": "search", "params": {"query": "test"}}
    assert record.thinking == "Need to search for test"
    assert record.reward == 1.0


def test_memory_record_optional_fields():
    """测试 MemoryRecord 可选字段"""
    from ai_agent.memory.base import MemoryRecord

    record = MemoryRecord(
        observation={"data": "test"},
        action={"name": "echo"},
    )

    assert record.thinking is None
    assert record.reward is None
    assert record.raw_response is None


def test_memory_record_validation():
    """测试 MemoryRecord 必填字段验证"""
    from ai_agent.memory.base import MemoryRecord
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MemoryRecord()  # 缺少必填字段


@pytest.fixture
def mock_llm():
    """创建模拟 LLM"""
    from unittest.mock import MagicMock, AsyncMock
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="Summary of records"))
    return llm


def test_compressed_memory_initialization(mock_llm):
    """测试 CompressedMemory 初始化"""
    from ai_agent.memory.base import CompressedMemory

    memory = CompressedMemory(mock_llm, max_memory=10, keep_recent=3)

    assert memory.max_memory == 10
    assert memory.keep_recent == 3
    assert memory.record_count == 0
    assert not memory.has_summary


@pytest.mark.asyncio
async def test_compressed_memory_add(mock_llm):
    """测试 CompressedMemory 添加记录"""
    from ai_agent.memory.base import CompressedMemory, MemoryRecord

    memory = CompressedMemory(mock_llm, max_memory=10, keep_recent=3)
    record = MemoryRecord(
        observation={"result": "ok"},
        action={"name": "test"},
    )

    await memory.add(record)

    assert memory.record_count == 1


@pytest.mark.asyncio
async def test_compressed_memory_add_raw(mock_llm):
    """测试 add_raw 便捷方法"""
    from ai_agent.memory.base import CompressedMemory

    memory = CompressedMemory(mock_llm)

    await memory.add_raw(
        observation={"data": "test"},
        action={"name": "echo"},
        thinking="Testing add_raw",
        reward=0.5,
    )

    assert memory.record_count == 1


def test_compressed_memory_as_text_empty(mock_llm):
    """测试空记忆的 as_text"""
    from ai_agent.memory.base import CompressedMemory

    memory = CompressedMemory(mock_llm)
    assert memory.as_text() == "None"


@pytest.mark.asyncio
async def test_compressed_memory_as_text_with_records(mock_llm):
    """测试有记录时的 as_text"""
    from ai_agent.memory.base import CompressedMemory

    memory = CompressedMemory(mock_llm)

    await memory.add_raw(
        observation={"result": "data1"},
        action={"name": "action1"},
        thinking="First thought",
    )
    await memory.add_raw(
        observation={"result": "data2"},
        action={"name": "action2"},
        thinking="Second thought",
    )

    text = memory.as_text()

    assert "[Recent steps (latest first)]" in text
    assert "action2" in text  # 最新记录在前
    assert "action1" in text


@pytest.mark.asyncio
async def test_compressed_memory_as_text_with_summary(mock_llm):
    """测试有摘要时的 as_text"""
    from ai_agent.memory.base import CompressedMemory

    memory = CompressedMemory(mock_llm)
    memory._summary = "Previous summary content"

    await memory.add_raw(
        observation={"current": "obs"},
        action={"name": "current_action"},
    )

    text = memory.as_text()

    assert "[Summary of earlier steps]" in text
    assert "Previous summary content" in text
    assert "current_action" in text


@pytest.mark.asyncio
async def test_compressed_memory_triggers_compress(mock_llm):
    """测试达到 max_memory 时触发压缩"""
    from ai_agent.memory.base import CompressedMemory

    memory = CompressedMemory(mock_llm, max_memory=5, keep_recent=2)

    # 添加 5 条记录
    for i in range(5):
        await memory.add_raw(
            observation={"step": i},
            action={"name": f"action_{i}"},
        )

    # 应该触发压缩，只保留最近 2 条
    assert memory.record_count == 2
    assert memory.has_summary


@pytest.mark.asyncio
async def test_compressed_memory_clear(mock_llm):
    """测试清空记忆"""
    from ai_agent.memory.base import CompressedMemory

    memory = CompressedMemory(mock_llm)
    await memory.add_raw({"data": "test"}, {"name": "test"})
    memory._summary = "old summary"

    memory.clear()

    assert memory.record_count == 0
    assert not memory.has_summary


def test_compressed_memory_invalid_max_memory(mock_llm):
    """测试 max_memory 参数验证"""
    from ai_agent.memory.base import CompressedMemory

    with pytest.raises(ValueError, match="max_memory must be at least 1"):
        CompressedMemory(mock_llm, max_memory=0)

    with pytest.raises(ValueError, match="max_memory must be at least 1"):
        CompressedMemory(mock_llm, max_memory=-1)


def test_compressed_memory_invalid_keep_recent(mock_llm):
    """测试 keep_recent 参数验证"""
    from ai_agent.memory.base import CompressedMemory

    with pytest.raises(ValueError, match="keep_recent must be non-negative"):
        CompressedMemory(mock_llm, keep_recent=-1)

    with pytest.raises(ValueError, match="keep_recent cannot exceed max_memory"):
        CompressedMemory(mock_llm, max_memory=5, keep_recent=10)
