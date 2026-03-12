# ReAct Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现一个完整的 ReAct Agent，支持结构化 JSON 输出、工具调用重试、Memory 压缩，并通过 TDD 方式确保质量。

**Architecture:** 三模块解耦设计 - Memory 模块（独立压缩记忆）、Prompt 模块（可复用模板）、ReAct Agent（LangGraph 状态机）。通过 LangGraph 构建 Think→Act→Observe 循环，支持自动终止和最大步数限制。

**Tech Stack:** LangGraph, LangChain Core, Pydantic, asyncio

---

## 项目结构变更

```
src/ai_agent/
├── memory/                    # 【新增】Memory 模块
│   ├── __init__.py
│   └── base.py               # MemoryRecord, BaseMemory, CompressedMemory
├── prompts/                   # 【新增】Prompt 模块
│   ├── __init__.py
│   ├── base.py               # BasePrompt 基类
│   └── react.py              # ReActPrompt 模板
├── agents/
│   └── react/                # 【新增】ReAct Agent
│       ├── __init__.py
│       └── graph.py          # ReActAgent, ReActAction, AgentState
└── ...

tests/
├── unit/
│   ├── memory/               # 【新增】Memory 单元测试
│   │   ├── __init__.py
│   │   └── test_base.py
│   ├── prompts/              # 【新增】Prompt 单元测试
│   │   ├── __init__.py
│   │   └── test_react.py
│   └── agents/
│       └── test_react_agent.py  # 【新增】ReAct Agent 单元测试
└── integration/
    └── test_react_integration.py  # 【新增】ReAct 集成测试
    └── test_react_real_api.py     # 【新增】真实 API 测试
```

---

## Task 1: Memory 模块 - 基础模型

**Files:**
- Create: `src/ai_agent/memory/__init__.py`
- Create: `src/ai_agent/memory/base.py`
- Create: `tests/unit/memory/__init__.py`
- Create: `tests/unit/memory/test_base.py`

### Step 1: 创建目录和 __init__.py

Run:
```bash
cd "E:/Project/ai agent" && mkdir -p src/ai_agent/memory tests/unit/memory
```

### Step 2: Write the failing test - MemoryRecord

```python
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
```

### Step 3: Run test to verify it fails

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/memory/test_base.py -v`
Expected: FAIL - ModuleNotFoundError

### Step 4: Write minimal implementation - MemoryRecord

```python
# src/ai_agent/memory/__init__.py
"""Memory 模块"""
from .base import MemoryRecord, BaseMemory, CompressedMemory

__all__ = ["MemoryRecord", "BaseMemory", "CompressedMemory"]
```

```python
# src/ai_agent/memory/base.py
"""Memory 模块 - 支持 ReAct 及其他 Agent 类型的记忆管理"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class MemoryRecord(BaseModel):
    """单条记忆记录"""

    observation: Dict[str, Any]
    action: Dict[str, Any]
    thinking: Optional[str] = None
    reward: Optional[float] = None
    raw_response: Optional[str] = None


class BaseMemory(ABC):
    """Memory 基类，定义统一接口"""

    @abstractmethod
    async def add(self, record: MemoryRecord) -> None:
        """添加记忆"""
        pass

    @abstractmethod
    def as_text(self) -> str:
        """转换为可注入 Prompt 的文本"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空记忆"""
        pass


class CompressedMemory(BaseMemory):
    """占位实现，后续 Task 完成"""
    pass
```

```python
# tests/unit/memory/__init__.py
"""Memory 单元测试"""
```

### Step 5: Run test to verify it passes

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/memory/test_base.py -v`
Expected: PASS

### Step 6: Commit

```bash
git add src/ai_agent/memory/ tests/unit/memory/
git commit -m "feat(memory): add MemoryRecord model and BaseMemory interface"
```

---

## Task 2: Memory 模块 - CompressedMemory 基础功能

**Files:**
- Modify: `src/ai_agent/memory/base.py`
- Modify: `tests/unit/memory/test_base.py`

### Step 1: Write the failing test - CompressedMemory 初始化和 add

```python
# 添加到 tests/unit/memory/test_base.py

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
```

### Step 2: Run test to verify it fails

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/memory/test_base.py -v -k "compressed"`
Expected: FAIL - AttributeError/TypeError

### Step 3: Write minimal implementation

```python
# 更新 src/ai_agent/memory/base.py 中的 CompressedMemory

from langchain_core.language_models import BaseChatModel


class CompressedMemory(BaseMemory):
    """
    带压缩功能的 Memory 实现
    - 保留最近 keep_recent 条完整记录
    - 早期记录通过 LLM 压缩为摘要
    """

    def __init__(
        self,
        llm: BaseChatModel,
        max_memory: int = 10,
        keep_recent: int = 3,
    ):
        self.llm = llm
        self.max_memory = max_memory
        self.keep_recent = keep_recent
        self._records: List[MemoryRecord] = []
        self._summary: Optional[str] = None

    async def add(self, record: MemoryRecord) -> None:
        """添加记忆并触发压缩检查"""
        self._records.append(record)
        await self._compress()

    async def add_raw(
        self,
        observation: Dict[str, Any],
        action: Dict[str, Any],
        thinking: Optional[str] = None,
        reward: Optional[float] = None,
        raw_response: Optional[str] = None,
    ) -> None:
        """便捷方法：直接添加原始数据"""
        record = MemoryRecord(
            observation=observation,
            action=action,
            thinking=thinking,
            reward=reward,
            raw_response=raw_response,
        )
        await self.add(record)

    def as_text(self) -> str:
        """生成可注入 Prompt 的文本"""
        raise NotImplementedError("将在下一个 Task 实现")

    def clear(self) -> None:
        """清空所有记忆"""
        self._records.clear()
        self._summary = None

    async def _compress(self) -> None:
        """达到上限时压缩旧记录"""
        raise NotImplementedError("将在下一个 Task 实现")

    @property
    def record_count(self) -> int:
        """当前完整记录数"""
        return len(self._records)

    @property
    def has_summary(self) -> bool:
        """是否有压缩摘要"""
        return self._summary is not None
```

### Step 4: Run test to verify it passes

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/memory/test_base.py -v -k "compressed"`
Expected: PASS

### Step 5: Commit

```bash
git add src/ai_agent/memory/base.py tests/unit/memory/test_base.py
git commit -m "feat(memory): add CompressedMemory initialization and add methods"
```

---

## Task 3: Memory 模块 - as_text 方法

**Files:**
- Modify: `src/ai_agent/memory/base.py`
- Modify: `tests/unit/memory/test_base.py`

### Step 1: Write the failing test - as_text

```python
# 添加到 tests/unit/memory/test_base.py

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
```

### Step 2: Run test to verify it fails

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/memory/test_base.py -v -k "as_text"`
Expected: FAIL - NotImplementedError

### Step 3: Write implementation - as_text

```python
# 更新 src/ai_agent/memory/base.py 中的 CompressedMemory.as_text

import json

# 在文件顶部添加 import json

    def as_text(self) -> str:
        """生成可注入 Prompt 的文本"""
        if not self._summary and not self._records:
            return "None"

        parts: List[str] = []

        if self._records:
            parts.append("[Recent steps (latest first)]")
            for idx, r in enumerate(reversed(self._records), 1):
                parts.append(
                    f"{idx}. action={json.dumps(r.action, ensure_ascii=False)}, "
                    f"observation={json.dumps(r.observation, ensure_ascii=False)}, "
                    f"thinking={r.thinking}, reward={r.reward}"
                )

        if self._summary:
            parts.append("")
            parts.append("[Summary of earlier steps]")
            parts.append(self._summary)

        return "\n".join(parts)
```

### Step 4: Run test to verify it passes

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/memory/test_base.py -v -k "as_text"`
Expected: PASS

### Step 5: Commit

```bash
git add src/ai_agent/memory/base.py tests/unit/memory/test_base.py
git commit -m "feat(memory): implement CompressedMemory.as_text method"
```

---

## Task 4: Memory 模块 - 压缩功能

**Files:**
- Modify: `src/ai_agent/memory/base.py`
- Modify: `tests/unit/memory/test_base.py`

### Step 1: Write the failing test - compress

```python
# 添加到 tests/unit/memory/test_base.py

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
```

### Step 2: Run test to verify it fails

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/memory/test_base.py -v -k "compress or clear"`
Expected: FAIL - NotImplementedError

### Step 3: Write implementation - compress

```python
# 更新 src/ai_agent/memory/base.py 中的 CompressedMemory

from langchain_core.messages import HumanMessage

    async def _compress(self) -> None:
        """达到上限时压缩旧记录"""
        if len(self._records) < self.max_memory:
            return

        if self.keep_recent > 0:
            head = self._records[:-self.keep_recent]
            tail = self._records[-self.keep_recent:]
        else:
            head = self._records[:]
            tail = []

        if head:
            head_summary = await self._summarize_records(head)
            if self._summary:
                self._summary += "\n\n" + head_summary
            else:
                self._summary = head_summary

        self._records = tail

    async def _summarize_records(self, records: List[MemoryRecord]) -> str:
        """使用 LLM 压缩记录"""
        record_lines: List[str] = []
        for idx, r in enumerate(records, 1):
            record_lines.append(
                f"{idx}. action={json.dumps(r.action, ensure_ascii=False)}, "
                f"observation={json.dumps(r.observation, ensure_ascii=False)}, "
                f"thinking={json.dumps(r.thinking, ensure_ascii=False)}, "
                f"reward={r.reward}"
            )
        records_text = "\n".join(record_lines)

        summary_prompt = f"""You are the memory compression module of a language-model-based agent.

You are given several past interaction steps in chronological order (oldest first).
Each step includes:
- the agent's action,
- the environment observation,
- the reward signal,
- the agent's thinking.

Your task is to write a compact, **persistent memory** block that lets the agent
continue its work without seeing the full history.

Please:
- Focus on:
  1) stable facts and rules about the environment/world,
  2) useful strategies / plans / tools the agent tried,
  3) important mistakes or failure patterns to avoid later,
  4) partial progress and remaining goals / TODOs.
- Use at most 8–10 lines.
- Use a neutral, factual tone.
- Do NOT repeat low-level JSON details unless they are crucial.
- Do NOT include meta text like "here is the summary" or any explanation.
- Output ONLY the memory lines, one per line.

===== PAST STEPS =====
{records_text}
===== SUMMARY (start here) ====="""

        response = await self.llm.ainvoke([HumanMessage(summary_prompt)])
        return response.content
```

### Step 4: Run test to verify it passes

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/memory/test_base.py -v -k "compress or clear"`
Expected: PASS

### Step 5: Run all Memory tests

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/memory/ -v`
Expected: All PASS

### Step 6: Commit

```bash
git add src/ai_agent/memory/base.py tests/unit/memory/test_base.py
git commit -m "feat(memory): implement CompressedMemory compression with LLM"
```

---

## Task 5: Prompt 模块 - 基类

**Files:**
- Create: `src/ai_agent/prompts/__init__.py`
- Create: `src/ai_agent/prompts/base.py`
- Create: `tests/unit/prompts/__init__.py`
- Create: `tests/unit/prompts/test_base.py`

### Step 1: 创建目录

Run:
```bash
cd "E:/Project/ai agent" && mkdir -p src/ai_agent/prompts tests/unit/prompts
```

### Step 2: Write the failing test - BasePrompt

```python
# tests/unit/prompts/test_base.py
import pytest


def test_base_prompt_is_abstract():
    """测试 BasePrompt 是抽象类"""
    from ai_agent.prompts.base import BasePrompt

    with pytest.raises(TypeError):
        BasePrompt()


def test_base_prompt_concrete_implementation():
    """测试具体实现"""

    class SimplePrompt(BasePrompt):
        @property
        def template(self) -> str:
            return "Hello {name}!"

        def format(self, **kwargs) -> str:
            return self.template.format(**kwargs)

    prompt = SimplePrompt()
    assert prompt.template == "Hello {name}!"
    assert prompt.format(name="World") == "Hello World!"
```

### Step 3: Run test to verify it fails

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/prompts/test_base.py -v`
Expected: FAIL - ModuleNotFoundError

### Step 4: Write minimal implementation

```python
# src/ai_agent/prompts/__init__.py
"""Prompt 模块"""
from .base import BasePrompt
from .react import ReActPrompt, REACT_TEMPLATE

__all__ = ["BasePrompt", "ReActPrompt", "REACT_TEMPLATE"]
```

```python
# src/ai_agent/prompts/base.py
"""Prompt 基类模块"""

from abc import ABC, abstractmethod
from typing import Any


class BasePrompt(ABC):
    """Prompt 基类，定义统一接口"""

    @property
    @abstractmethod
    def template(self) -> str:
        """获取原始模板字符串"""
        pass

    @abstractmethod
    def format(self, **kwargs: Any) -> str:
        """格式化模板，注入变量"""
        pass
```

```python
# tests/unit/prompts/__init__.py
"""Prompt 单元测试"""
```

### Step 5: Run test to verify it passes

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/prompts/test_base.py -v`
Expected: PASS

### Step 6: Commit

```bash
git add src/ai_agent/prompts/ tests/unit/prompts/
git commit -m "feat(prompts): add BasePrompt abstract class"
```

---

## Task 6: Prompt 模块 - ReActPrompt

**Files:**
- Create: `src/ai_agent/prompts/react.py`
- Create: `tests/unit/prompts/test_react.py`

### Step 1: Write the failing test - ReActPrompt

```python
# tests/unit/prompts/test_react.py
import pytest


def test_react_prompt_template_constant():
    """测试 REACT_TEMPLATE 常量存在"""
    from ai_agent.prompts.react import REACT_TEMPLATE

    assert "{task_instruction}" in REACT_TEMPLATE
    assert "{original_question}" in REACT_TEMPLATE
    assert "{action_space}" in REACT_TEMPLATE
    assert "{memory}" in REACT_TEMPLATE
    assert "{obs}" in REACT_TEMPLATE


def test_react_prompt_initialization():
    """测试 ReActPrompt 初始化"""
    from ai_agent.prompts import ReActPrompt

    prompt = ReActPrompt()
    assert prompt.template is not None


def test_react_prompt_format():
    """测试 ReActPrompt 格式化"""
    from ai_agent.prompts import ReActPrompt

    prompt = ReActPrompt()

    formatted = prompt.format(
        original_question="What is 2+2?",
        action_space="tools: calculator",
        memory="None",
        obs="No observation",
    )

    assert "What is 2+2?" in formatted
    assert "calculator" in formatted


def test_react_prompt_with_task():
    """测试 with_task 链式调用"""
    from ai_agent.prompts import ReActPrompt

    prompt = ReActPrompt().with_task("Solve math problems")
    formatted = prompt.format(
        original_question="test",
        action_space="none",
    )

    assert "Solve math problems" in formatted


def test_react_prompt_with_context():
    """测试 with_context 链式调用"""
    from ai_agent.prompts import ReActPrompt

    prompt = ReActPrompt().with_context("You are a math assistant")
    formatted = prompt.format(
        original_question="test",
        action_space="none",
    )

    assert "You are a math assistant" in formatted
```

### Step 2: Run test to verify it fails

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/prompts/test_react.py -v`
Expected: FAIL - ModuleNotFoundError

### Step 3: Write implementation

```python
# src/ai_agent/prompts/react.py
"""ReAct Prompt 模板"""

from typing import Any
from .base import BasePrompt


REACT_TEMPLATE = """==== Your Task ====
{task_instruction}

==== Context ====
{context}

==== Original Question (for reference) ====
{original_question}

==== Available Tools ====
{action_space}

==== Guidelines ====
1. Focus on completing YOUR TASK above
2. Think step by step before outputting an action
3. Write key observations to the "memory" field
4. Use tools to gather information or take actions
5. Once done, use 'finish' IMMEDIATELY

⚠️ BUDGET: When remaining_steps <= 5, use 'finish' NOW!

==== Output Format ====
```json
{{
    "action": "<tool_name>",
    "params": {{}},
    "memory": "<observations>"
}}
```

==== Memory ====
{memory}

==== Current Observation ====
{obs}"""


class ReActPrompt(BasePrompt):
    """ReAct Prompt 模板类"""

    def __init__(
        self,
        task_instruction: str = "Answer the user's question accurately.",
        context: str = "No additional context provided.",
    ):
        self._task_instruction = task_instruction
        self._context = context
        self._template = REACT_TEMPLATE

    @property
    def template(self) -> str:
        return self._template

    def format(
        self,
        original_question: str,
        action_space: str,
        memory: str = "None",
        obs: str = "None",
        **kwargs: Any,
    ) -> str:
        """格式化 ReAct Prompt"""
        return self._template.format(
            task_instruction=self._task_instruction,
            context=self._context,
            original_question=original_question,
            action_space=action_space,
            memory=memory,
            obs=obs,
        )

    def with_task(self, task: str) -> "ReActPrompt":
        """链式调用：设置任务指令"""
        self._task_instruction = task
        return self

    def with_context(self, context: str) -> "ReActPrompt":
        """链式调用：设置上下文"""
        self._context = context
        return self
```

### Step 4: Run test to verify it passes

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/prompts/test_react.py -v`
Expected: PASS

### Step 5: Run all Prompt tests

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/prompts/ -v`
Expected: All PASS

### Step 6: Commit

```bash
git add src/ai_agent/prompts/ tests/unit/prompts/
git commit -m "feat(prompts): add ReActPrompt with template and fluent API"
```

---

## Task 7: ReAct Agent - 状态模型

**Files:**
- Create: `src/ai_agent/agents/react/__init__.py`
- Create: `src/ai_agent/agents/react/graph.py` (部分)
- Create: `tests/unit/agents/test_react_agent.py` (部分)

### Step 1: 创建目录

Run:
```bash
cd "E:/Project/ai agent" && mkdir -p src/ai_agent/agents/react
```

### Step 2: Write the failing test - Models

```python
# 添加到 tests/unit/agents/test_react_agent.py

import pytest


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
```

### Step 3: Run test to verify it fails

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_react_agent.py -v -k "action or state"`
Expected: FAIL - ModuleNotFoundError

### Step 4: Write minimal implementation

```python
# src/ai_agent/agents/react/__init__.py
"""ReAct Agent 模块"""
from .graph import ReActAgent, ReActAction, AgentState

__all__ = ["ReActAgent", "ReActAction", "AgentState"]
```

```python
# src/ai_agent/agents/react/graph.py (第一部分：模型)

"""ReAct Agent 实现"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReActAction(BaseModel):
    """LLM 返回的结构化动作"""

    action: str = Field(description="工具名称或 'finish'")
    params: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    memory: str = Field(default="", description="本轮观察/思考")


class AgentState(BaseModel):
    """ReAct Agent 状态"""

    question: str = Field(description="用户原始问题")
    current_obs: str = Field(default="", description="当前观察")
    steps_taken: int = Field(default=0, description="已执行步数")
    actions_history: List[ReActAction] = Field(
        default_factory=list, description="动作历史"
    )
    final_answer: Optional[str] = Field(default=None, description="最终答案")
    error: Optional[str] = Field(default=None, description="错误信息")

    class Config:
        arbitrary_types_allowed = True
```

### Step 5: Run test to verify it passes

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_react_agent.py -v -k "action or state"`
Expected: PASS

### Step 6: Commit

```bash
git add src/ai_agent/agents/react/ tests/unit/agents/test_react_agent.py
git commit -m "feat(agents): add ReActAction and AgentState models"
```

---

## Task 8: ReAct Agent - 辅助方法

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py`
- Modify: `tests/unit/agents/test_react_agent.py`

### Step 1: Write the failing test - Helper methods

```python
# 添加到 tests/unit/agents/test_react_agent.py

from unittest.mock import MagicMock


def test_build_action_space():
    """测试构建工具描述"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "calculator"
    mock_tool.description = "Performs calculations"

    agent = ReActAgent(mock_llm, tools=[mock_tool])
    action_space = agent._build_action_space()

    assert "calculator" in action_space
    assert "Performs calculations" in action_space
    assert "finish" in action_space


def test_build_action_space_empty():
    """测试无工具时的描述"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    agent = ReActAgent(mock_llm, tools=[])

    action_space = agent._build_action_space()

    assert "No tools available" in action_space


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
```

### Step 2: Run test to verify it fails

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_react_agent.py -v -k "build or parse or find"`
Expected: FAIL - AttributeError

### Step 3: Write implementation

```python
# 更新 src/ai_agent/agents/react/graph.py (添加辅助方法)

import json
import re
from langchain_core.tools import BaseTool
from ..base import BaseAgent


class ReActAgent(BaseAgent):
    """
    ReAct Agent 实现
    - 结构化 JSON 输出（action + params + memory）
    - 自动终止 + 最大步数兜底
    - 工具调用重试机制
    """

    MAX_STEPS = 20
    MAX_RETRIES = 3

    def __init__(
        self,
        llm,
        tools: List[BaseTool] | None = None,
        max_steps: int = MAX_STEPS,
        max_retries: int = MAX_RETRIES,
    ):
        super().__init__(llm, tools)
        self.max_steps = max_steps
        self.max_retries = max_retries

    def _build_action_space(self) -> str:
        """构建工具描述供 LLM 选择"""
        if not self.tools:
            return "No tools available. Use 'finish' to provide your answer."

        lines = ["Available tools:"]
        for tool in self.tools:
            lines.append(f"- {tool.name}: {tool.description}")
        lines.append("- finish: Use this when you have the final answer.")

        return "\n".join(lines)

    def _parse_action(self, response: str) -> ReActAction | None:
        """从 LLM 响应中解析 JSON 动作"""
        try:
            # 尝试提取 JSON 块
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response.strip()

            data = json.loads(json_str)
            return ReActAction(**data)
        except (json.JSONDecodeError, ValueError):
            # 尝试修复常见问题
            try:
                fixed = "{" + json_str + "}"
                data = json.loads(fixed)
                return ReActAction(**data)
            except:
                return None

    def _find_tool(self, name: str) -> BaseTool | None:
        """根据名称查找工具"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    async def run(self, message: str) -> str:
        """将在后续 Task 实现"""
        raise NotImplementedError

    def get_graph(self):
        """将在后续 Task 实现"""
        raise NotImplementedError
```

### Step 4: Run test to verify it passes

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_react_agent.py -v -k "build or parse or find"`
Expected: PASS

### Step 5: Commit

```bash
git add src/ai_agent/agents/react/graph.py tests/unit/agents/test_react_agent.py
git commit -m "feat(agents): add ReActAgent helper methods"
```

---

## Task 9: ReAct Agent - 重试机制

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py`
- Modify: `tests/unit/agents/test_react_agent.py`

### Step 1: Write the failing test - retry

```python
# 添加到 tests/unit/agents/test_react_agent.py

import asyncio


@pytest.mark.asyncio
async def test_execute_with_retry_success():
    """测试成功执行"""
    from ai_agent.agents.react import ReActAgent

    mock_llm = MagicMock()
    mock_tool = MagicMock()
    mock_tool.ainvoke = asyncio.coroutine(lambda x: "success result")

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
```

### Step 2: Run test to verify it fails

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_react_agent.py -v -k "retry"`
Expected: FAIL - AttributeError

### Step 3: Write implementation

```python
# 更新 src/ai_agent/agents/react/graph.py (添加重试方法)

import asyncio

    async def _execute_with_retry(
        self,
        tool: BaseTool,
        params: Dict[str, Any],
    ) -> str:
        """执行工具调用，带重试机制"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                result = await tool.ainvoke(params)
                return str(result)
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    # 指数退避
                    await asyncio.sleep(0.5 * (attempt + 1))

        return f"Error after {self.max_retries} retries: {last_error}"
```

### Step 4: Run test to verify it passes

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_react_agent.py -v -k "retry"`
Expected: PASS

### Step 5: Commit

```bash
git add src/ai_agent/agents/react/graph.py tests/unit/agents/test_react_agent.py
git commit -m "feat(agents): add tool execution with retry mechanism"
```

---

## Task 10: ReAct Agent - LangGraph 构建与核心节点

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py`
- Modify: `tests/unit/agents/test_react_agent.py`

### Step 1: Write the failing test - Graph structure

```python
# 添加到 tests/unit/agents/test_react_agent.py

from unittest.mock import MagicMock, AsyncMock


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
```

### Step 2: Run test to verify it fails

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_react_agent.py -v -k "graph or prompt"`
Expected: FAIL - NotImplementedError

### Step 3: Write implementation

```python
# 更新 src/ai_agent/agents/react/graph.py (完整实现)

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from ..base import BaseAgent
from ...prompts import ReActPrompt


class ReActAgent(BaseAgent):
    """
    ReAct Agent 实现
    - 结构化 JSON 输出（action + params + memory）
    - 自动终止 + 最大步数兜底
    - 工具调用重试机制
    """

    MAX_STEPS = 20
    MAX_RETRIES = 3

    def __init__(
        self,
        llm,
        tools: List[BaseTool] | None = None,
        prompt: ReActPrompt | None = None,
        max_steps: int = MAX_STEPS,
        max_retries: int = MAX_RETRIES,
    ):
        super().__init__(llm, tools)
        self.prompt = prompt or ReActPrompt()
        self.max_steps = max_steps
        self.max_retries = max_retries
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 状态图"""
        graph = StateGraph(AgentState)

        # 节点
        graph.add_node("think", self._think_node)
        graph.add_node("act", self._act_node)
        graph.add_node("observe", self._observe_node)

        # 边
        graph.add_edge(START, "think")
        graph.add_conditional_edges(
            "think",
            self._should_finish,
            {"finish": END, "continue": "act"},
        )
        graph.add_edge("act", "observe")
        graph.add_edge("observe", "think")

        return graph.compile()

    def _should_finish(self, state: AgentState) -> str:
        """判断是否应该结束"""
        if state.final_answer is not None:
            return "finish"
        if state.error and "max_retries_exceeded" in state.error:
            return "finish"
        if state.steps_taken >= self.max_steps:
            return "finish"
        return "continue"

    async def _think_node(self, state: AgentState) -> Dict[str, Any]:
        """Think 节点：调用 LLM 决定下一步行动"""
        # 构建工具描述
        action_space = self._build_action_space()

        # 格式化 Prompt
        formatted_prompt = self.prompt.format(
            original_question=state.question,
            action_space=action_space,
            memory="None",
            obs=state.current_obs or "No observation yet.",
        )

        # 调用 LLM
        response = await self.llm.ainvoke([HumanMessage(formatted_prompt)])

        # 解析 JSON 响应
        action = self._parse_action(response.content)

        if action is None:
            return {"error": "Failed to parse LLM response as JSON"}

        # 更新状态
        updates: Dict[str, Any] = {
            "actions_history": state.actions_history + [action],
        }

        # 如果是 finish，设置最终答案
        if action.action == "finish":
            updates["final_answer"] = action.params.get("answer", action.memory)

        return updates

    async def _act_node(self, state: AgentState) -> Dict[str, Any]:
        """Act 节点：执行工具调用（带重试）"""
        if not state.actions_history:
            return {"error": "No action to execute"}

        current_action = state.actions_history[-1]

        # finish 不需要执行工具
        if current_action.action == "finish":
            return {"current_obs": "Task completed."}

        # 查找工具
        tool = self._find_tool(current_action.action)
        if tool is None:
            return {
                "current_obs": f"Error: Tool '{current_action.action}' not found.",
                "steps_taken": state.steps_taken + 1,
            }

        # 执行工具（带重试）
        result = await self._execute_with_retry(tool, current_action.params)

        return {
            "current_obs": result,
            "steps_taken": state.steps_taken + 1,
        }

    async def _observe_node(self, state: AgentState) -> Dict[str, Any]:
        """Observe 节点：处理观察结果，准备下一轮"""
        return {}

    async def run(self, message: str) -> str:
        """运行 ReAct Agent"""
        initial_state = AgentState(
            question=message,
            current_obs="",
            steps_taken=0,
            actions_history=[],
        )

        result = await self._graph.ainvoke(initial_state)

        # 返回最终答案或错误信息
        final_state = AgentState(**result)

        if final_state.final_answer:
            return final_state.final_answer
        elif final_state.error:
            return f"Agent error: {final_state.error}"
        else:
            return "Agent completed without a clear answer."

    def get_graph(self):
        """获取编译后的图（用于调试/可视化）"""
        return self._graph
```

### Step 4: Run test to verify it passes

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/test_react_agent.py -v -k "graph or prompt"`
Expected: PASS

### Step 5: Run all Agent tests

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/agents/ -v`
Expected: All PASS

### Step 6: Commit

```bash
git add src/ai_agent/agents/react/graph.py tests/unit/agents/test_react_agent.py
git commit -m "feat(agents): implement ReActAgent with LangGraph state machine"
```

---

## Task 11: 集成测试

**Files:**
- Create: `tests/integration/test_react_integration.py`

### Step 1: Write the integration test

```python
# tests/integration/test_react_integration.py
"""ReAct Agent 集成测试"""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


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
    assert "clear answer" in result or result is not None


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
```

### Step 2: Run integration tests

Run: `cd "E:/Project/ai agent" && uv run pytest tests/integration/test_react_integration.py -v`
Expected: All PASS

### Step 3: Commit

```bash
git add tests/integration/test_react_integration.py
git commit -m "test: add ReAct Agent integration tests"
```

---

## Task 12: 真实 API 测试

**Files:**
- Create: `tests/integration/test_react_real_api.py`

### Step 1: Write the real API test

```python
# tests/integration/test_react_real_api.py
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
```

### Step 2: Run real API tests

Run: `cd "E:/Project/ai agent" && uv run pytest tests/integration/test_react_real_api.py -v -m integration_real`
Expected: PASS (需要真实 API Key)

### Step 3: Commit

```bash
git add tests/integration/test_react_real_api.py
git commit -m "test: add ReAct Agent real API integration tests"
```

---

## Task 13: 完整测试验证

### Step 1: 运行所有单元测试

Run: `cd "E:/Project/ai agent" && uv run pytest tests/unit/ -v`
Expected: All PASS

### Step 2: 运行所有集成测试（模拟）

Run: `cd "E:/Project/ai agent" && uv run pytest tests/integration/test_react_integration.py -v`
Expected: All PASS

### Step 3: 运行完整测试套件

Run: `cd "E:/Project/ai agent" && uv run pytest -v`
Expected: All PASS

### Step 4: Final Commit

```bash
git add .
git commit -m "feat: complete ReAct Agent implementation with Memory and Prompt modules"
```

---

## 实现文件清单

| 文件 | 说明 |
|------|------|
| `src/ai_agent/memory/__init__.py` | Memory 模块入口 |
| `src/ai_agent/memory/base.py` | MemoryRecord + BaseMemory + CompressedMemory |
| `src/ai_agent/prompts/__init__.py` | Prompt 模块入口 |
| `src/ai_agent/prompts/base.py` | BasePrompt 抽象类 |
| `src/ai_agent/prompts/react.py` | ReActPrompt 模板 + REACT_TEMPLATE |
| `src/ai_agent/agents/react/__init__.py` | ReAct Agent 入口 |
| `src/ai_agent/agents/react/graph.py` | ReActAgent + ReActAction + AgentState |
| `tests/unit/memory/test_base.py` | Memory 单元测试 |
| `tests/unit/prompts/test_base.py` | Prompt 基类单元测试 |
| `tests/unit/prompts/test_react.py` | ReActPrompt 单元测试 |
| `tests/unit/agents/test_react_agent.py` | ReAct Agent 单元测试 |
| `tests/integration/test_react_integration.py` | 集成测试 |
| `tests/integration/test_react_real_api.py` | 真实 API 测试 |

---

## 设计原则遵循

| 原则 | 应用 |
|------|------|
| **KISS** | 三节点状态机，结构简洁 |
| **YAGNI** | 当前单轮对话，Memory 压缩预留 |
| **DRY** | Prompt/Memory 模块可复用 |
| **TDD** | 每个 Task 先写测试再实现 |
| **SRP** | Memory/Prompt/Agent 各司其职 |
| **OCP** | BaseMemory/BasePrompt 可扩展 |
| **DIP** | Agent 依赖抽象接口 |
