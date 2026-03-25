# Local Trace System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现装饰器驱动的本地追踪系统，零侵入记录 Agent/Tool/LLM 执行的完整轨迹到 JSON 文件。

**Architecture:** 轻量自定义 Tracer，基于 ContextVar 传播，零外部依赖。扁平 spans + parent_id 构成树结构，装饰器自动捕获输入输出和异常。与 LangSmith 完全独立。

**Tech Stack:** Python 3.11, dataclasses, contextvars, json, pytest

**Design Doc:** `docs/plans/2026-03-24-local-trace-system-design.md`

---

## Task 1: 数据模型 types.py

**Files:**
- Create: `src/ai_agent/trace/types.py`
- Create: `tests/unit/trace/test_types.py`

**Step 1: Write the failing test**

```python
# tests/unit/trace/test_types.py
"""Trace 数据模型单元测试"""

import json
import time
from dataclasses import asdict

import pytest

from ai_agent.trace.types import SpanData, TraceRun, generate_run_id


class TestSpanData:
    """SpanData 数据模型测试"""

    def test_create_basic_span(self):
        """测试基本 span 创建"""
        span = SpanData(
            name="think",
            span_id="a1b2c3d4",
            parent_id=None,
            started_at=1000.0,
            finished_at=2000.0,
            status="success",
        )
        assert span.name == "think"
        assert span.span_id == "a1b2c3d4"
        assert span.parent_id is None
        assert span.status == "success"
        assert span.input is None
        assert span.output is None
        assert span.error is None
        assert span.metadata == {}

    def test_span_with_input_output(self):
        """测试带输入输出的 span"""
        span = SpanData(
            name="act:web_search",
            span_id="e5f6a7b8",
            parent_id="a1b2c3d4",
            started_at=1000.0,
            finished_at=2000.0,
            status="success",
            input={"query": "python tutorial"},
            output={"results": ["url1", "url2"]},
            metadata={"tool": "web_search"},
        )
        assert span.input == {"query": "python tutorial"}
        assert span.output == {"results": ["url1", "url2"]}
        assert span.metadata == {"tool": "web_search"}

    def test_span_error_state(self):
        """测试错误状态的 span"""
        span = SpanData(
            name="think",
            span_id="a1b2c3d4",
            parent_id=None,
            started_at=1000.0,
            finished_at=2000.0,
            status="error",
            error="LLM call failed: timeout",
        )
        assert span.status == "error"
        assert span.error == "LLM call failed: timeout"

    def test_span_incomplete(self):
        """测试未完成的 span（异常中断）"""
        span = SpanData(
            name="think",
            span_id="a1b2c3d4",
            parent_id=None,
            started_at=1000.0,
            finished_at=None,
            status="error",
        )
        assert span.finished_at is None

    def test_span_serialize_to_json(self):
        """测试 span 序列化为 JSON"""
        span = SpanData(
            name="act:web_search",
            span_id="e5f6a7b8",
            parent_id="a1b2c3d4",
            started_at=1000.0,
            finished_at=2000.5,
            status="success",
            input={"query": "test"},
            output={"result": "ok"},
        )
        data = asdict(span)
        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["name"] == "act:web_search"
        assert parsed["duration_ms"] == 1000.5
        assert parsed["input"] == {"query": "test"}

    def test_span_duration_ms_property(self):
        """测试 duration_ms 计算属性"""
        span = SpanData(
            name="think",
            span_id="a1b2c3d4",
            parent_id=None,
            started_at=1000.0,
            finished_at=2500.5,
            status="success",
        )
        assert span.duration_ms == 1500.5

    def test_span_duration_ms_none_when_incomplete(self):
        """测试未完成 span 的 duration_ms 为 None"""
        span = SpanData(
            name="think",
            span_id="a1b2c3d4",
            parent_id=None,
            started_at=1000.0,
            finished_at=None,
            status="error",
        )
        assert span.duration_ms is None

    def test_span_with_special_characters_in_output(self):
        """测试输出含特殊字符时 JSON 正确"""
        span = SpanData(
            name="act",
            span_id="a1b2c3d4",
            parent_id=None,
            started_at=1000.0,
            finished_at=2000.0,
            status="success",
            output='{"key": "value with \n newline and \t tab"}',
        )
        data = asdict(span)
        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert "\n" in parsed["output"]

    def test_span_with_none_values(self):
        """测试含 None 值的 span 序列化"""
        span = SpanData(
            name="think",
            span_id="a1b2c3d4",
            parent_id=None,
            started_at=1000.0,
            finished_at=2000.0,
            status="success",
            input=None,
            output=None,
        )
        data = asdict(span)
        assert data["input"] is None
        assert data["output"] is None


class TestTraceRun:
    """TraceRun 数据模型测试"""

    def test_create_basic_run(self):
        """测试基本 run 创建"""
        run = TraceRun(
            run_id="20260324_143022_a3f2",
            name="react_agent",
            started_at=1000.0,
            finished_at=5000.0,
            spans=[],
        )
        assert run.run_id == "20260324_143022_a3f2"
        assert run.name == "react_agent"
        assert run.spans == []
        assert run.tags == []
        assert run.metadata == {}

    def test_run_with_spans(self):
        """测试带 spans 的 run"""
        think_span = SpanData(
            name="think",
            span_id="a1b2c3d4",
            parent_id=None,
            started_at=1000.0,
            finished_at=3000.0,
            status="success",
        )
        act_span = SpanData(
            name="act:web_search",
            span_id="e5f6a7b8",
            parent_id="a1b2c3d4",
            started_at=3000.0,
            finished_at=4500.0,
            status="success",
        )
        run = TraceRun(
            run_id="20260324_143022_a3f2",
            name="react_agent",
            started_at=1000.0,
            finished_at=4500.0,
            spans=[think_span, act_span],
        )
        assert len(run.spans) == 2
        assert run.span_count() == 2

    def test_run_total_duration_ms(self):
        """测试 run 总耗时"""
        run = TraceRun(
            run_id="test",
            name="test",
            started_at=1000.0,
            finished_at=5333.5,
            spans=[],
        )
        assert run.total_duration_ms == 4333.5

    def test_run_total_duration_ms_incomplete(self):
        """测试未完成 run 的 total_duration_ms"""
        run = TraceRun(
            run_id="test",
            name="test",
            started_at=1000.0,
            finished_at=None,
            spans=[],
        )
        assert run.total_duration_ms is None

    def test_run_success_property_all_success(self):
        """测试所有 span 成功时 run 状态"""
        spans = [
            SpanData(
                name="think", span_id="a1", parent_id=None,
                started_at=1000.0, finished_at=2000.0, status="success",
            ),
            SpanData(
                name="act", span_id="b2", parent_id="a1",
                started_at=2000.0, finished_at=3000.0, status="success",
            ),
        ]
        run = TraceRun(
            run_id="test", name="test",
            started_at=1000.0, finished_at=3000.0,
            spans=spans,
        )
        assert run.is_success() is True

    def test_run_success_property_has_error(self):
        """测试有 span 失败时 run 状态"""
        spans = [
            SpanData(
                name="think", span_id="a1", parent_id=None,
                started_at=1000.0, finished_at=2000.0, status="success",
            ),
            SpanData(
                name="act", span_id="b2", parent_id="a1",
                started_at=2000.0, finished_at=3000.0, status="error",
                error="tool not found",
            ),
        ]
        run = TraceRun(
            run_id="test", name="test",
            started_at=1000.0, finished_at=3000.0,
            spans=spans,
        )
        assert run.is_success() is False

    def test_run_serialize_to_json(self):
        """测试 run 序列化为 JSON 文件格式"""
        think_span = SpanData(
            name="think",
            span_id="a1b2c3d4",
            parent_id=None,
            started_at=1742807422.123,
            finished_at=1742807424.423,
            status="success",
            input={"question": "test"},
        )
        run = TraceRun(
            run_id="20260324_143022_a3f2",
            name="react_agent",
            started_at=1742807422.123,
            finished_at=1742807425.456,
            spans=[think_span],
            tags=["react", "agent"],
        )
        data = run.to_dict()
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        parsed = json.loads(json_str)

        assert parsed["run_id"] == "20260324_143022_a3f2"
        assert parsed["name"] == "react_agent"
        assert parsed["status"] == "success"
        assert parsed["total_duration_ms"] == 3333.0
        assert parsed["tags"] == ["react", "agent"]
        assert len(parsed["spans"]) == 1
        assert parsed["spans"][0]["duration_ms"] == 2300.0

    def test_run_find_span_by_name(self):
        """测试按名称查找 span"""
        spans = [
            SpanData(
                name="think", span_id="a1", parent_id=None,
                started_at=1000.0, finished_at=2000.0, status="success",
            ),
            SpanData(
                name="act:web_search", span_id="b2", parent_id="a1",
                started_at=2000.0, finished_at=3000.0, status="success",
            ),
        ]
        run = TraceRun(
            run_id="test", name="test",
            started_at=1000.0, finished_at=3000.0,
            spans=spans,
        )
        found = run.find_span("act:web_search")
        assert found is not None
        assert found.span_id == "b2"

        not_found = run.find_span("nonexistent")
        assert not_found is None

    def test_run_find_all_spans_by_name(self):
        """测试按名称查找所有匹配 span"""
        spans = [
            SpanData(
                name="think", span_id="a1", parent_id=None,
                started_at=1000.0, finished_at=2000.0, status="success",
            ),
            SpanData(
                name="think", span_id="a2", parent_id=None,
                started_at=2000.0, finished_at=3000.0, status="success",
            ),
            SpanData(
                name="act", span_id="b2", parent_id="a2",
                started_at=3000.0, finished_at=4000.0, status="success",
            ),
        ]
        run = TraceRun(
            run_id="test", name="test",
            started_at=1000.0, finished_at=4000.0,
            spans=spans,
        )
        found = run.find_spans("think")
        assert len(found) == 2


class TestGenerateRunId:
    """run_id 生成测试"""

    def test_format(self):
        """测试 run_id 格式：YYYYMMDD_HHMMSS_xxxx"""
        run_id = generate_run_id()
        parts = run_id.split("_")
        assert len(parts) == 3
        # 日期部分 8 位
        assert len(parts[0]) == 8
        # 时间部分 6 位
        assert len(parts[1]) == 6
        # 随机后缀 4 位
        assert len(parts[2]) == 4

    def test_uniqueness(self):
        """测试多次生成不重复"""
        ids = {generate_run_id() for _ in range(100)}
        assert len(ids) == 100
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/trace/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_agent.trace.types'`

**Step 3: Write minimal implementation**

```python
# src/ai_agent/trace/types.py
"""Trace 数据模型定义

提供 SpanData 和 TraceRun 数据结构，用于记录执行轨迹。
"""

import random
import string
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SpanData:
    """单个追踪节点

    Attributes:
        name: 节点名称，如 "think", "act:web_search", "llm_call"
        span_id: 8位短ID
        parent_id: 父节点ID，顶层为 None
        started_at: 开始时间戳
        finished_at: 结束时间戳，None 表示未完成（异常中断）
        status: "success" | "error"
        input: 序列化后的输入
        output: 序列化后的输出
        error: 异常信息
        metadata: 扩展字段
    """

    name: str
    span_id: str
    parent_id: str | None
    started_at: float
    finished_at: float | None
    status: str
    input: Any = None
    output: Any = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        """计算耗时（毫秒）"""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at) * 1000

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的字典"""
        data = asdict(self)
        data["duration_ms"] = self.duration_ms
        return data


@dataclass
class TraceRun:
    """一次完整的运行记录

    Attributes:
        run_id: 唯一ID，格式 "YYYYMMDD_HHMMSS_xxxx"
        name: 运行名称
        started_at: 开始时间戳
        finished_at: 结束时间戳
        spans: 扁平 span 列表，通过 parent_id 构成树
        tags: 标签列表
        metadata: 扩展字段
    """

    run_id: str
    name: str
    started_at: float
    finished_at: float | None
    spans: list[SpanData] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def total_duration_ms(self) -> float | None:
        """计算总耗时（毫秒）"""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at) * 1000

    def span_count(self) -> int:
        """span 总数"""
        return len(self.spans)

    def is_success(self) -> bool:
        """所有 span 是否都成功"""
        return all(s.status == "success" for s in self.spans)

    def find_span(self, name: str) -> SpanData | None:
        """按名称查找第一个匹配的 span"""
        for span in self.spans:
            if span.name == name:
                return span
        return None

    def find_spans(self, name: str) -> list[SpanData]:
        """按名称查找所有匹配的 span"""
        return [s for s in self.spans if s.name == name]

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的字典（JSON 文件格式）"""
        return {
            "run_id": self.run_id,
            "name": self.name,
            "status": "success" if self.is_success() else "error",
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_duration_ms": self.total_duration_ms,
            "tags": self.tags,
            "metadata": self.metadata,
            "spans": [s.to_dict() for s in self.spans],
        }


def generate_run_id() -> str:
    """生成唯一 run_id

    格式: YYYYMMDD_HHMMSS_xxxx（时间戳 + 4位随机后缀）
    """
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{date_part}_{time_part}_{random_suffix}"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/trace/test_types.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/ai_agent/trace/types.py tests/unit/trace/test_types.py
git commit -m "feat(trace): add SpanData and TraceRun data models"
```

---

## Task 2: ContextVar 传播 context.py

**Files:**
- Create: `src/ai_agent/trace/context.py`
- Create: `tests/unit/trace/test_context.py`

**Step 1: Write the failing test**

```python
# tests/unit/trace/test_context.py
"""ContextVar 传播机制单元测试"""

import asyncio

import pytest

from ai_agent.trace.context import active_run, current_parent_id, push_span, pop_span, set_active_run, clear_run
from ai_agent.trace.types import TraceRun, generate_run_id


class TestContextVarPropagation:
    """ContextVar 传播测试"""

    def test_set_and_get_active_run(self):
        """测试设置和获取活跃 run"""
        run = TraceRun(
            run_id=generate_run_id(),
            name="test",
            started_at=1000.0,
            finished_at=None,
        )
        set_active_run(run)
        assert active_run() is run
        assert active_run().name == "test"
        clear_run()
        assert active_run() is None

    def test_clear_run(self):
        """测试清除活跃 run"""
        run = TraceRun(
            run_id=generate_run_id(),
            name="test",
            started_at=1000.0,
            finished_at=None,
        )
        set_active_run(run)
        clear_run()
        assert active_run() is None

    def test_default_no_active_run(self):
        """测试默认无活跃 run"""
        assert active_run() is None

    def test_push_and_pop_span(self):
        """测试 span 栈的 push/pop"""
        set_active_run(TraceRun(
            run_id=generate_run_id(), name="test",
            started_at=1000.0, finished_at=None,
        ))
        assert current_parent_id() is None

        push_span("a1")
        assert current_parent_id() == "a1"

        push_span("b2")
        assert current_parent_id() == "b2"

        pop_span()
        assert current_parent_id() == "a1"

        pop_span()
        assert current_parent_id() is None

        clear_run()

    def test_empty_pop(self):
        """测试空栈 pop 不报错"""
        set_active_run(TraceRun(
            run_id=generate_run_id(), name="test",
            started_at=1000.0, finished_at=None,
        ))
        # 空 pop 不应报错
        pop_span()
        assert current_parent_id() is None
        clear_run()


class TestAsyncIsolation:
    """异步并发隔离测试"""

    @pytest.mark.asyncio
    async def test_concurrent_tasks_isolated(self):
        """测试并发任务的 ContextVar 隔离"""
        results = {}

        async def task(name: str, run_id: str) -> None:
            run = TraceRun(
                run_id=run_id,
                name=name,
                started_at=1000.0,
                finished_at=None,
            )
            set_active_run(run)
            push_span(f"span_{name}")
            # 模拟异步等待
            await asyncio.sleep(0.01)
            # 验证隔离
            results[name] = {
                "run_name": active_run().name if active_run() else None,
                "parent": current_parent_id(),
            }
            pop_span()
            clear_run()

        await asyncio.gather(
            task("task_a", "run_a"),
            task("task_b", "run_b"),
        )

        assert results["task_a"]["run_name"] == "task_a"
        assert results["task_a"]["parent"] == "span_task_a"
        assert results["task_b"]["run_name"] == "task_b"
        assert results["task_b"]["parent"] == "span_task_b"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/trace/test_context.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/ai_agent/trace/context.py
"""ContextVar 传播机制

使用 Python ContextVar 实现异步安全的 run/span 上下文传播。
每个 asyncio Task 拥有独立的上下文，天然隔离并发场景。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from contextvars import ContextVar

if TYPE_CHECKING:
    from .types import TraceRun

# 当前活跃的 TraceRun
_active_run: ContextVar[TraceRun | None] = ContextVar("trace_active_run", default=None)

# 当前 span 嵌套栈
_span_stack: ContextVar[list[str]] = ContextVar("trace_span_stack", default_factory=list)


def active_run() -> TraceRun | None:
    """获取当前活跃的 TraceRun"""
    return _active_run.get()


def set_active_run(run: TraceRun) -> None:
    """设置当前活跃的 TraceRun"""
    _active_run.set(run)


def clear_run() -> None:
    """清除当前活跃的 TraceRun（不报错）"""
    _active_run.set(None)


def current_parent_id() -> str | None:
    """获取当前 span 栈顶的 span_id 作为 parent_id"""
    stack = _span_stack.get()
    return stack[-1] if stack else None


def push_span(span_id: str) -> None:
    """将 span_id 压入栈"""
    stack = _span_stack.get()
    _span_stack.set(stack + [span_id])


def pop_span() -> None:
    """将 span_id 弹出栈（空栈不报错）"""
    stack = _span_stack.get()
    if stack:
        _span_stack.set(stack[:-1])
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/trace/test_context.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/ai_agent/trace/context.py tests/unit/trace/test_context.py
git commit -m "feat(trace): add ContextVar propagation for async-safe span tracking"
```

---

## Task 3: 配置模块 config.py

**Files:**
- Create: `src/ai_agent/trace/config.py`
- Create: `tests/unit/trace/test_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/trace/test_config.py
"""Trace 配置模块单元测试"""

import os
import tempfile

import pytest

from ai_agent.trace.config import TraceConfig, default_trace_dir


class TestTraceConfig:
    """TraceConfig 测试"""

    def test_default_values(self):
        """测试默认配置"""
        config = TraceConfig()
        assert config.enabled is True
        assert config.trace_dir.endswith("logs" + os.sep + "traces")

    def test_custom_trace_dir(self, tmp_path):
        """测试自定义目录"""
        config = TraceConfig(trace_dir=str(tmp_path / "custom_traces"))
        assert config.trace_dir == str(tmp_path / "custom_traces")

    def test_disabled(self):
        """测试禁用追踪"""
        config = TraceConfig(enabled=False)
        assert config.enabled is False

    def test_default_trace_dir_exists(self):
        """测试默认 trace 目录路径可生成"""
        assert default_trace_dir() is not None
        assert "logs" in default_trace_dir()
        assert "traces" in default_trace_dir()


class TestTraceFilePath:
    """文件路径生成测试"""

    def test_generate_file_path(self, tmp_path):
        """测试文件路径生成"""
        config = TraceConfig(trace_dir=str(tmp_path))
        path = config.trace_file_path("20260324", "143022_a3f2", "react_agent")
        expected = str(tmp_path / "20260324" / "143022_a3f2_react_agent.json")
        assert path == expected
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/trace/test_config.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/ai_agent/trace/config.py
"""Trace 配置模块

管理本地追踪系统的配置项。
"""

from __future__ import annotations

import os
from pathlib import Path


def default_trace_dir() -> str:
    """获取默认 trace 存储目录

    Returns:
        项目根目录下的 logs/traces/ 路径
    """
    return os.path.join("logs", "traces")


class TraceConfig:
    """本地追踪系统配置

    Attributes:
        enabled: 是否启用追踪
        trace_dir: trace JSON 文件存储根目录
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        trace_dir: str | None = None,
    ) -> None:
        self.enabled = enabled
        self.trace_dir = trace_dir or default_trace_dir()

    def trace_file_path(
        self,
        date_str: str,
        time_id: str,
        name: str,
    ) -> str:
        """生成 trace 文件完整路径

        Args:
            date_str: 日期字符串，如 "20260324"
            time_id: 时间+ID部分，如 "143022_a3f2"
            name: 运行名称

        Returns:
            完整文件路径
        """
        filename = f"{time_id}_{name}.json"
        return os.path.join(self.trace_dir, date_str, filename)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/trace/test_config.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/ai_agent/trace/config.py tests/unit/trace/test_config.py
git commit -m "feat(trace): add trace configuration module"
```

---

## Task 4: TraceRecorder 核心记录器 recorder.py

**Files:**
- Create: `src/ai_agent/trace/recorder.py`
- Create: `tests/unit/trace/test_recorder.py`

**Step 1: Write the failing test**

```python
# tests/unit/trace/test_recorder.py
"""TraceRecorder 核心记录器单元测试"""

import json
import os

import pytest

from ai_agent.trace.config import TraceConfig
from ai_agent.trace.recorder import TraceRecorder
from ai_agent.trace.types import SpanData


class TestTraceRecorder:
    """TraceRecorder 测试"""

    def _make_recorder(self, tmp_path) -> TraceRecorder:
        return TraceRecorder(
            name="test_run",
            config=TraceConfig(trace_dir=str(tmp_path)),
        )

    def test_create_recorder(self, tmp_path):
        """测试创建 recorder"""
        recorder = self._make_recorder(tmp_path)
        assert recorder.name == "test_run"
        assert recorder.run is not None
        assert recorder.run.run_id is not None
        assert len(recorder.run.spans) == 0

    def test_start_span(self, tmp_path):
        """测试开始 span"""
        recorder = self._make_recorder(tmp_path)
        recorder.start_span("think")
        assert recorder.run.span_count() == 0  # span 未完成不计入

    def test_finish_span_success(self, tmp_path):
        """测试成功完成 span"""
        recorder = self._make_recorder(tmp_path)
        recorder.start_span("think")
        recorder.finish_span(output={"action": "search"})
        assert recorder.run.span_count() == 1
        span = recorder.run.spans[0]
        assert span.name == "think"
        assert span.status == "success"
        assert span.output == {"action": "search"}
        assert span.parent_id is None
        assert span.finished_at is not None

    def test_finish_span_error(self, tmp_path):
        """测试异常完成 span"""
        recorder = self._make_recorder(tmp_path)
        recorder.start_span("think")
        recorder.finish_span(error="LLM timeout")
        span = recorder.run.spans[0]
        assert span.status == "error"
        assert span.error == "LLM timeout"

    def test_nested_spans(self, tmp_path):
        """测试嵌套 span 的 parent_id 关联"""
        recorder = self._make_recorder(tmp_path)
        recorder.start_span("think")
        think_id = recorder._current_span_id

        recorder.start_span("act:web_search")
        recorder.finish_span(input={"query": "test"})

        recorder.finish_span(output={"action": "search"})

        assert recorder.run.span_count() == 2

        think_span = recorder.run.find_span("think")
        act_span = recorder.run.find_span("act:web_search")
        assert think_span.parent_id is None
        assert act_span.parent_id == think_id

    def test_deeply_nested_spans(self, tmp_path):
        """测试深层嵌套 span"""
        recorder = self._make_recorder(tmp_path)
        recorder.start_span("think")
        think_id = recorder._current_span_id

        recorder.start_span("llm_call")
        llm_id = recorder._current_span_id
        recorder.finish_span(output="response text")

        recorder.start_span("parse_action")
        recorder.finish_span(output={"action": "search"})

        recorder.finish_span(output={"action": "search"})

        spans = recorder.run.spans
        assert len(spans) == 3

        # llm_call 和 parse_action 的 parent 都是 think
        llm_span = recorder.run.find_span("llm_call")
        parse_span = recorder.run.find_span("parse_action")
        assert llm_span.parent_id == think_id
        assert parse_span.parent_id == think_id

    def test_flush_creates_json_file(self, tmp_path):
        """测试 flush 写入 JSON 文件"""
        recorder = self._make_recorder(tmp_path)
        recorder.start_span("think")
        recorder.finish_span(input={"question": "test"})

        recorder.finish_run()

        # 验证文件存在
        trace_files = list(tmp_path.rglob("*.json"))
        assert len(trace_files) == 1

        # 验证 JSON 内容
        with open(trace_files[0], encoding="utf-8") as f:
            data = json.load(f)

        assert data["name"] == "test_run"
        assert data["status"] == "success"
        assert len(data["spans"]) == 1
        assert data["spans"][0]["name"] == "think"

    def test_flush_creates_date_subdirectory(self, tmp_path):
        """测试 flush 自动创建日期子目录"""
        recorder = self._make_recorder(tmp_path)
        recorder.finish_run()

        # 检查有日期子目录
        subdirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(subdirs) == 1

    def test_auto_creates_directory_structure(self, tmp_path):
        """测试自动创建不存在的目录"""
        non_existent = str(tmp_path / "deep" / "nested" / "traces")
        recorder = TraceRecorder(
            name="test",
            config=TraceConfig(trace_dir=non_existent),
        )
        recorder.start_span("test")
        recorder.finish_span()
        recorder.finish_run()

        trace_files = list(Path(non_existent).rglob("*.json"))
        assert len(trace_files) == 1

    def test_set_tag(self, tmp_path):
        """测试设置 tag"""
        recorder = self._make_recorder(tmp_path)
        recorder.set_tag("react")
        recorder.set_tag("agent")
        assert recorder.run.tags == ["react", "agent"]

    def test_set_metadata(self, tmp_path):
        """测试设置 metadata"""
        recorder = self._make_recorder(tmp_path)
        recorder.set_metadata("model", "gpt-4")
        recorder.set_metadata("max_steps", 10)
        assert recorder.run.metadata == {"model": "gpt-4", "max_steps": 10}

    def test_finish_run_without_spans(self, tmp_path):
        """测试无 span 时 finish_run"""
        recorder = self._make_recorder(tmp_path)
        recorder.finish_run()

        trace_files = list(tmp_path.rglob("*.json"))
        assert len(trace_files) == 1
        with open(trace_files[0], encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["spans"]) == 0

    def test_multiple_runs_isolated(self, tmp_path):
        """测试多个 recorder 实例隔离"""
        recorder_a = TraceRecorder(
            name="run_a",
            config=TraceConfig(trace_dir=str(tmp_path)),
        )
        recorder_b = TraceRecorder(
            name="run_b",
            config=TraceConfig(trace_dir=str(tmp_path)),
        )

        recorder_a.start_span("think_a")
        recorder_a.finish_span()
        recorder_b.start_span("think_b")
        recorder_b.finish_span()

        assert recorder_a.run.span_count() == 1
        assert recorder_b.run.span_count() == 1
        assert recorder_a.run.spans[0].name == "think_a"
        assert recorder_b.run.spans[0].name == "think_b"

    def test_json_contains_all_fields(self, tmp_path):
        """测试 JSON 文件包含所有必要字段"""
        recorder = self._make_recorder(tmp_path)
        recorder.set_tag("test")
        recorder.start_span("act:web_search")
        recorder.finish_span(
            input={"query": "python"},
            output={"results": ["url1"]},
        )
        recorder.finish_run()

        trace_files = list(tmp_path.rglob("*.json"))
        with open(trace_files[0], encoding="utf-8") as f:
            data = json.load(f)

        # 验证顶层字段
        assert "run_id" in data
        assert "name" in data
        assert "status" in data
        assert "started_at" in data
        assert "finished_at" in data
        assert "total_duration_ms" in data
        assert "tags" in data
        assert "spans" in data

        # 验证 span 字段
        span = data["spans"][0]
        assert "name" in span
        assert "span_id" in span
        assert "parent_id" in span
        assert "started_at" in span
        assert "finished_at" in span
        assert "duration_ms" in span
        assert "status" in span
        assert "input" in span
        assert "output" in span


# 需要导入 Path
from pathlib import Path
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/trace/test_recorder.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/ai_agent/trace/recorder.py
"""TraceRecorder 核心记录器

负责 span 树构建、JSON 序列化和文件写入。
每个 TraceRecorder 实例对应一次完整的运行记录。
"""

from __future__ import annotations

import json
import os
import random
import string
import time
from datetime import datetime, timezone
from typing import Any

from .config import TraceConfig
from .context import clear_run, current_parent_id, pop_span, push_span, set_active_run
from .types import SpanData, TraceRun, generate_run_id


def _generate_span_id() -> str:
    """生成 8 位 span ID"""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


class TraceRecorder:
    """追踪记录器

    管理一次完整运行的 span 树，提供 start_span/finish_span 接口，
    运行结束时 flush 到 JSON 文件。

    Usage:
        recorder = TraceRecorder(name="react_agent")
        recorder.start_span("think")
        recorder.finish_span(output={"action": "search"})
        recorder.finish_run()  # 写入 JSON 文件
    """

    def __init__(
        self,
        name: str,
        *,
        config: TraceConfig | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self._config = config or TraceConfig()
        self.run = TraceRun(
            run_id=generate_run_id(),
            name=name,
            started_at=time.time(),
            finished_at=None,
            tags=tags or [],
        )
        self._current_span_id: str | None = None

    @property
    def name(self) -> str:
        """运行名称"""
        return self.run.name

    def set_tag(self, tag: str) -> None:
        """添加标签"""
        if tag not in self.run.tags:
            self.run.tags.append(tag)

    def set_metadata(self, key: str, value: Any) -> None:
        """设置元数据"""
        self.run.metadata[key] = value

    def start_span(self, name: str) -> str:
        """开始一个新的 span

        Args:
            name: span 名称

        Returns:
            span_id
        """
        span_id = _generate_span_id()
        parent_id = current_parent_id()

        span = SpanData(
            name=name,
            span_id=span_id,
            parent_id=parent_id,
            started_at=time.time(),
            finished_at=None,
            status="success",  # 默认成功，异常时更新
        )
        # 暂存当前 span（不加入列表，完成时才加入）
        self._pending_span = span
        self._current_span_id = span_id
        push_span(span_id)
        set_active_run(self.run)

        return span_id

    def finish_span(
        self,
        *,
        input: Any = None,
        output: Any = None,
        error: str | None = None,
    ) -> None:
        """完成当前 span

        Args:
            input: span 输入数据
            output: span 输出数据
            error: 错误信息（非 None 时标记为 error 状态）
        """
        span = getattr(self, "_pending_span", None)
        if span is None:
            return

        span.finished_at = time.time()
        span.input = input
        span.output = output

        if error is not None:
            span.status = "error"
            span.error = error

        self.run.spans.append(span)
        self._pending_span = None
        pop_span()

    def finish_run(self) -> str | None:
        """完成运行并 flush 到 JSON 文件

        Returns:
            写入的文件路径，如果禁用则返回 None
        """
        self.run.finished_at = time.time()
        clear_run()

        if not self._config.enabled:
            return None

        file_path = self._flush_to_file()
        return file_path

    def _flush_to_file(self) -> str:
        """将 run 数据写入 JSON 文件

        Returns:
            写入的文件路径
        """
        run_id = self.run.run_id
        # 解析 run_id: "20260324_143022_a3f2"
        parts = run_id.split("_")
        date_str = parts[0]  # "20260324"
        time_id = f"{parts[1]}_{parts[2]}"  # "143022_a3f2"

        full_path = self._config.trace_file_path(date_str, time_id, self.run.name)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(self.run.to_dict(), f, ensure_ascii=False, indent=2)

        return full_path
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/trace/test_recorder.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/ai_agent/trace/recorder.py tests/unit/trace/test_recorder.py
git commit -m "feat(trace): add TraceRecorder with span tree and JSON file output"
```

---

## Task 5: 装饰器 decorators.py

**Files:**
- Create: `src/ai_agent/trace/decorators.py`
- Create: `tests/unit/trace/test_decorators.py`

**Step 1: Write the failing test**

```python
# tests/unit/trace/test_decorators.py
"""装饰器单元测试"""

import asyncio
import json
from pathlib import Path

import pytest

from ai_agent.trace.config import TraceConfig
from ai_agent.trace.decorators import trace_run, trace_span, TraceSpanCtx


class TestTraceSpanDecorator:
    """@trace_span 装饰器测试"""

    def test_sync_function_records_span(self, tmp_path):
        """测试同步函数记录 span"""
        config = TraceConfig(trace_dir=str(tmp_path))

        @trace_span("my_func", config=config)
        def add(a: int, b: int) -> int:
            return a + b

        # 需要在 trace_run 上下文中使用
        from ai_agent.trace.recorder import TraceRecorder
        recorder = TraceRecorder("test", config=config)
        recorder.start_span("outer")
        result = add(1, 2)
        recorder.finish_span()
        recorder.finish_run()

        assert result == 3
        assert recorder.run.span_count() == 2

        my_func_span = recorder.run.find_span("my_func")
        assert my_func_span is not None
        assert my_func_span.input == {"args": (1, 2), "kwargs": {}}
        assert my_func_span.output == 3

    @pytest.mark.asyncio
    async def test_async_function_records_span(self, tmp_path):
        """测试异步函数记录 span"""
        config = TraceConfig(trace_dir=str(tmp_path))

        @trace_span("async_func", config=config)
        async def async_add(a: int, b: int) -> int:
            return a + b

        from ai_agent.trace.recorder import TraceRecorder
        recorder = TraceRecorder("test", config=config)
        recorder.start_span("outer")
        result = await async_add(1, 2)
        recorder.finish_span()
        recorder.finish_run()

        assert result == 3
        async_func_span = recorder.run.find_span("async_func")
        assert async_func_span is not None

    def test_exception_captured_and_reraised(self, tmp_path):
        """测试异常被捕获并重新抛出"""
        config = TraceConfig(trace_dir=str(tmp_path))

        @trace_span("failing_func", config=config)
        def fail():
            raise ValueError("test error")

        from ai_agent.trace.recorder import TraceRecorder
        recorder = TraceRecorder("test", config=config)
        recorder.start_span("outer")

        with pytest.raises(ValueError, match="test error"):
            fail()

        recorder.finish_span()
        recorder.finish_run()

        failing_span = recorder.run.find_span("failing_func")
        assert failing_span.status == "error"
        assert "test error" in failing_span.error

    def test_no_active_run_silent_skip(self, tmp_path):
        """测试无活跃 run 时静默跳过"""
        config = TraceConfig(trace_dir=str(tmp_path))

        @trace_span("orphan_func", config=config)
        def orphan():
            return "ok"

        result = orphan()
        assert result == "ok"
        # 无文件生成
        trace_files = list(tmp_path.rglob("*.json"))
        assert len(trace_files) == 0


class TestTraceRunDecorator:
    """@trace_run 装饰器测试"""

    def test_sync_function_creates_run(self, tmp_path):
        """测试同步函数创建 run 并写入文件"""
        config = TraceConfig(trace_dir=str(tmp_path))

        @trace_run("sync_run", config=config)
        def compute():
            return 42

        result = compute()

        assert result == 42
        trace_files = list(tmp_path.rglob("*.json"))
        assert len(trace_files) == 1

        with open(trace_files[0], encoding="utf-8") as f:
            data = json.load(f)
        assert data["name"] == "sync_run"
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_async_function_creates_run(self, tmp_path):
        """测试异步函数创建 run"""
        config = TraceConfig(trace_dir=str(tmp_path))

        @trace_run("async_run", config=config)
        async def async_compute():
            return 42

        result = await async_compute()

        assert result == 42
        trace_files = list(tmp_path.rglob("*.json"))
        assert len(trace_files) == 1

    def test_with_nested_spans(self, tmp_path):
        """测试 @trace_run 内嵌套 @trace_span"""
        config = TraceConfig(trace_dir=str(tmp_path))

        @trace_span("inner", config=config)
        def helper():
            return "inner_result"

        @trace_run("outer_run", config=config)
        def main():
            return helper()

        result = main()

        assert result == "inner_result"
        trace_files = list(tmp_path.rglob("*.json"))
        assert len(trace_files) == 1

        with open(trace_files[0], encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["spans"]) == 2  # outer_run + inner
        inner_span = next(s for s in data["spans"] if s["name"] == "inner")
        assert inner_span["output"] == "inner_result"

    def test_exception_creates_error_run(self, tmp_path):
        """测试异常时创建 error run"""
        config = TraceConfig(trace_dir=str(tmp_path))

        @trace_run("failing_run", config=config)
        def fail():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            fail()

        trace_files = list(tmp_path.rglob("*.json"))
        assert len(trace_files) == 1

        with open(trace_files[0], encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == "error"

    def test_decorator_preserves_function_name(self, tmp_path):
        """测试装饰器保留函数名和文档"""
        config = TraceConfig(trace_dir=str(tmp_path))

        @trace_run("test", config=config)
        def my_function():
            """My docstring"""
            return 1

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring"


class TestTraceSpanContextManager:
    """trace_span 上下文管理器测试"""

    def test_context_manager_records_span(self, tmp_path):
        """测试上下文管理器记录 span"""
        config = TraceConfig(trace_dir=str(tmp_path))

        from ai_agent.trace.recorder import TraceRecorder
        recorder = TraceRecorder("test", config=config)
        recorder.start_span("outer")

        with TraceSpanCtx("manual_span", config=config) as span:
            span.set_tag("key", "value")
            pass  # do work

        recorder.finish_span()
        recorder.finish_run()

        manual_span = recorder.run.find_span("manual_span")
        assert manual_span is not None
        assert manual_span.metadata == {"key": "value"}

    def test_context_manager_with_error(self, tmp_path):
        """测试上下文管理器异常时记录错误"""
        config = TraceConfig(trace_dir=str(tmp_path))

        from ai_agent.trace.recorder import TraceRecorder
        recorder = TraceRecorder("test", config=config)
        recorder.start_span("outer")

        with pytest.raises(ValueError):
            with TraceSpanCtx("error_span", config=config):
                raise ValueError("ctx error")

        recorder.finish_span()
        recorder.finish_run()

        error_span = recorder.run.find_span("error_span")
        assert error_span.status == "error"
        assert "ctx error" in error_span.error

    @pytest.mark.asyncio
    async def test_async_context_manager(self, tmp_path):
        """测试异步上下文管理器"""
        config = TraceConfig(trace_dir=str(tmp_path))

        from ai_agent.trace.recorder import TraceRecorder
        recorder = TraceRecorder("test", config=config)
        recorder.start_span("outer")

        async with TraceSpanCtx("async_manual", config=config):
            await asyncio.sleep(0.001)

        recorder.finish_span()
        recorder.finish_run()

        async_span = recorder.run.find_span("async_manual")
        assert async_span is not None
        assert async_span.status == "success"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/trace/test_decorators.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/ai_agent/trace/decorators.py
"""Trace 装饰器和上下文管理器

提供 @trace_run、@trace_span 装饰器和 TraceSpanCtx 上下文管理器。
"""

from __future__ import annotations

import functools
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, TypeVar

from .config import TraceConfig
from .context import active_run, clear_run, current_parent_id, pop_span, push_span, set_active_run
from .recorder import TraceRecorder

F = TypeVar("F")


def _default_config() -> TraceConfig:
    """获取默认配置（可被测试覆盖）"""
    return TraceConfig()


def trace_run(
    name: str | None = None,
    *,
    config: TraceConfig | None = None,
    tags: list[str] | None = None,
) -> Callable[[F], F]:
    """创建完整 run 的装饰器

    装饰的函数执行完成后，自动将 trace 写入 JSON 文件。

    Args:
        name: run 名称，默认使用函数名
        config: 追踪配置
        tags: 标签列表
    """

    def decorator(func: F) -> F:
        _name = name or func.__name__
        _config = config or _default_config()

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                recorder = TraceRecorder(
                    _name, config=_config, tags=tags,
                )
                recorder.start_span(_name)
                try:
                    result = await func(*args, **kwargs)
                    recorder.finish_span(output=result)
                    return result
                except Exception as e:
                    recorder.finish_span(error=str(e))
                    raise
                finally:
                    recorder.finish_run()

            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                recorder = TraceRecorder(
                    _name, config=_config, tags=tags,
                )
                recorder.start_span(_name)
                try:
                    result = func(*args, **kwargs)
                    recorder.finish_span(output=result)
                    return result
                except Exception as e:
                    recorder.finish_span(error=str(e))
                    raise
                finally:
                    recorder.finish_run()

            return sync_wrapper  # type: ignore[return-value]

    return decorator


def trace_span(
    name: str | None = None,
    *,
    config: TraceConfig | None = None,
) -> Callable[[F], F]:
    """子节点 span 装饰器

    挂载到当前活跃的 run。如果没有活跃 run，静默跳过。

    Args:
        name: span 名称，默认使用函数名
        config: 追踪配置
    """

    def decorator(func: F) -> F:
        _name = name or func.__name__
        _config = config or _default_config()

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if active_run() is None:
                    return await func(*args, **kwargs)

                # 查找活跃 run 的 recorder
                # 通过 context 找到 run，然后通过 run 管理 span
                recorder = _find_recorder_for_run(_config)
                if recorder is None:
                    return await func(*args, **kwargs)

                recorder.start_span(_name)
                try:
                    result = await func(*args, **kwargs)
                    recorder.finish_span(
                        input={"args": args, "kwargs": kwargs},
                        output=result,
                    )
                    return result
                except Exception as e:
                    recorder.finish_span(
                        input={"args": args, "kwargs": kwargs},
                        error=str(e),
                    )
                    raise

            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if active_run() is None:
                    return func(*args, **kwargs)

                recorder = _find_recorder_for_run(_config)
                if recorder is None:
                    return func(*args, **kwargs)

                recorder.start_span(_name)
                try:
                    result = func(*args, **kwargs)
                    recorder.finish_span(
                        input={"args": args, "kwargs": kwargs},
                        output=result,
                    )
                    return result
                except Exception as e:
                    recorder.finish_span(
                        input={"args": args, "kwargs": kwargs},
                        error=str(e),
                    )
                    raise

            return sync_wrapper  # type: ignore[return-value]

    return decorator


# 当前线程活跃的 recorder（用于 trace_span 找到对应的 recorder）
_active_recorders: dict[int, TraceRecorder] = {}


def _register_recorder(recorder: TraceRecorder) -> None:
    """注册活跃 recorder"""
    _active_recorders[id(recorder.run)] = recorder


def _unregister_recorder(run_id_str: str) -> None:
    """注销 recorder"""
    # 遍历查找匹配的 recorder（通过 run_id 字符串匹配）
    to_remove = [
        k for k, v in _active_recorders.items()
        if v.run.run_id == run_id_str
    ]
    for k in to_remove:
        del _active_recorders[k]


def _find_recorder_for_run(config: TraceConfig) -> TraceRecorder | None:
    """查找当前活跃 run 对应的 recorder"""
    run = active_run()
    if run is None:
        return None
    return _active_recorders.get(id(run))


class TraceSpanCtx:
    """trace_span 上下文管理器

    用于代码块级追踪，支持 sync 和 async。

    Usage:
        with TraceSpanCtx("llm_call") as span:
            span.set_tag("model", "gpt-4")
            result = llm.chat(messages)

        async with TraceSpanCtx("async_op") as span:
            result = await async_operation()
    """

    def __init__(
        self,
        name: str,
        *,
        config: TraceConfig | None = None,
    ) -> None:
        self._name = name
        self._config = config or _default_config()
        self._recorder: TraceRecorder | None = None
        self.metadata: dict[str, Any] = {}

    def set_tag(self, key: str, value: Any) -> None:
        """设置 span 标签（写入 metadata）"""
        self.metadata[key] = value

    def __enter__(self) -> TraceSpanCtx:
        if active_run() is None:
            return self
        self._recorder = _find_recorder_for_run(self._config)
        if self._recorder:
            self._recorder.start_span(self._name)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._recorder is None:
            return
        error = str(exc_val) if exc_val else None
        self._recorder.finish_span(metadata=self.metadata or None, error=error)

    async def __aenter__(self) -> TraceSpanCtx:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


# 需要导入 asyncio
import asyncio
```

> **注意：** 上面的 `_find_recorder_for_run` 机制是一个简化实现。Task 4 的 `TraceRecorder.start_span` 中已经调用了 `set_active_run`，所以 `trace_run` 装饰器创建的 recorder 会自动注册。`trace_span` 通过 `active_run()` 找到当前 run，然后通过 `_active_recorders[id(run)]` 找到 recorder 实例。需要在 `TraceRecorder.__init__` 和 `finish_run` 中补充注册/注销逻辑。

**需要在 recorder.py 中补充的修改：**

```python
# 在 recorder.py 的 __init__ 末尾添加：
from .decorators import _register_recorder, _unregister_recorder

# 在 __init__ 中添加：
_register_recorder(self)

# 在 finish_run 中 clear_run() 之前添加：
_unregister_recorder(self.run.run_id)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/trace/test_decorators.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/ai_agent/trace/decorators.py tests/unit/trace/test_decorators.py
git commit -m "feat(trace): add @trace_run, @trace_span decorators and TraceSpanCtx"
```

---

## Task 6: 断言 API assertions.py

**Files:**
- Create: `src/ai_agent/trace/assertions.py`
- Create: `tests/unit/trace/test_assertions.py`

**Step 1: Write the failing test**

```python
# tests/unit/trace/test_assertions.py
"""断言 API 单元测试"""

import pytest

from ai_agent.trace.assertions import SpanAssertion
from ai_agent.trace.recorder import TraceRecorder
from ai_agent.trace.types import SpanData, TraceRun


class TestSpanAssertion:
    """SpanAssertion 测试"""

    def _make_run_with_spans(self) -> TraceRun:
        return TraceRun(
            run_id="test_run",
            name="test",
            started_at=1000.0,
            finished_at=5000.0,
            spans=[
                SpanData(
                    name="think", span_id="a1", parent_id=None,
                    started_at=1000.0, finished_at=2000.0, status="success",
                    input={"question": "test query"},
                    output={"action": "search", "params": {"query": "test"}},
                ),
                SpanData(
                    name="act:web_search", span_id="b2", parent_id="a1",
                    started_at=2000.0, finished_at=3000.0, status="success",
                    input={"query": "test"},
                    output={"results": ["url1", "url2"]},
                ),
                SpanData(
                    name="think", span_id="a3", parent_id=None,
                    started_at=3000.0, finished_at=4000.0, status="success",
                    output={"action": "finish"},
                ),
            ],
        )

    def test_with_input_exact_match(self):
        """测试精确匹配输入"""
        run = self._make_run_with_spans()
        assertion = SpanAssertion(run, "think")
        # 不报错即通过
        assertion.with_input(question="test query")

    def test_with_input_mismatch_raises(self):
        """测试输入不匹配时抛出断言错误"""
        run = self._make_run_with_spans()
        assertion = SpanAssertion(run, "think")
        with pytest.raises(AssertionError, match="think"):
            assertion.with_input(question="wrong query")

    def test_with_output_exact_match(self):
        """测试精确匹配输出"""
        run = self._make_run_with_spans()
        assertion = SpanAssertion(run, "act:web_search")
        assertion.with_output(results=["url1", "url2"])

    def test_with_output_mismatch_raises(self):
        """测试输出不匹配时抛出断言错误"""
        run = self._make_run_with_spans()
        assertion = SpanAssertion(run, "act:web_search")
        with pytest.raises(AssertionError):
            assertion.with_output(results=["wrong"])

    def test_with_nested_field_match(self):
        """测试嵌套字段匹配"""
        run = self._make_run_with_spans()
        assertion = SpanAssertion(run, "think")
        assertion.with_output(action="search")

    def test_assertion_has_multiple_spans(self):
        """测试匹配多个同名 span"""
        run = self._make_run_with_spans()
        # 有两个 think span
        think_spans = run.find_spans("think")
        assert len(think_spans) == 2
        assertion = SpanAssertion(run, "think")
        # with_input 应该在至少一个 think span 上匹配
        assertion.with_input(question="test query")

    def test_assertion_no_matching_span(self):
        """测试无匹配 span 时抛出错误"""
        run = self._make_run_with_spans()
        assertion = SpanAssertion(run, "nonexistent")
        with pytest.raises(AssertionError, match="nonexistent"):
            assertion.with_input(foo="bar")

    def test_assertion_error_status(self):
        """测试断言 span 错误状态"""
        run = TraceRun(
            run_id="test", name="test",
            started_at=1000.0, finished_at=2000.0,
            spans=[
                SpanData(
                    name="act", span_id="a1", parent_id=None,
                    started_at=1000.0, finished_at=2000.0,
                    status="error", error="tool not found",
                ),
            ],
        )
        assertion = SpanAssertion(run, "act")
        assertion.has_error("tool not found")

    def test_assertion_error_status_mismatch(self):
        """测试错误信息不匹配时抛出"""
        run = TraceRun(
            run_id="test", name="test",
            started_at=1000.0, finished_at=2000.0,
            spans=[
                SpanData(
                    name="act", span_id="a1", parent_id=None,
                    started_at=1000.0, finished_at=2000.0,
                    status="error", error="timeout",
                ),
            ],
        )
        assertion = SpanAssertion(run, "act")
        with pytest.raises(AssertionError):
            assertion.has_error("wrong error")


class TestTraceRecorderAssertions:
    """TraceRecorder 断言扩展测试"""

    def _make_recorder(self, tmp_path) -> TraceRecorder:
        from ai_agent.trace.config import TraceConfig
        return TraceRecorder("test", config=TraceConfig(trace_dir=str(tmp_path)))

    def test_success_method(self, tmp_path):
        """测试 success() 断言"""
        recorder = self._make_recorder(tmp_path)
        recorder.start_span("ok")
        recorder.finish_span()
        assert recorder.success() is True

    def test_success_false_when_error(self, tmp_path):
        """测试有 error span 时 success() 返回 False"""
        recorder = self._make_recorder(tmp_path)
        recorder.start_span("ok")
        recorder.finish_span()
        recorder.start_span("fail")
        recorder.finish_span(error="error")
        assert recorder.success() is False

    def test_has_span_returns_assertion(self, tmp_path):
        """测试 has_span 返回 SpanAssertion"""
        recorder = self._make_recorder(tmp_path)
        recorder.start_span("think")
        recorder.finish_span()

        assertion = recorder.has_span("think")
        assert isinstance(assertion, SpanAssertion)

    def test_has_span_not_found_raises(self, tmp_path):
        """测试 has_span 找不到时抛出"""
        recorder = self._make_recorder(tmp_path)
        with pytest.raises(AssertionError, match="not found"):
            recorder.has_span("nonexistent").exists()

    def test_span_count(self, tmp_path):
        """测试 span_count"""
        recorder = self._make_recorder(tmp_path)
        recorder.start_span("a")
        recorder.finish_span()
        recorder.start_span("b")
        recorder.finish_span()
        assert recorder.span_count() == 2

    def test_duration_ms(self, tmp_path):
        """测试 duration_ms"""
        recorder = self._make_recorder(tmp_path)
        recorder.finish_run()
        assert recorder.duration_ms() is not None
        assert recorder.duration_ms() >= 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/trace/test_assertions.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/ai_agent/trace/assertions.py
"""pytest 断言 API

提供链式断言接口，用于在测试中验证 trace 记录。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import TraceRun


class SpanAssertion:
    """单个 span 的断言接口

    Usage:
        recorder.has_span("act:web_search").with_input(query="test")
        recorder.has_span("think").with_output(action="search")
    """

    def __init__(self, run: TraceRun, name: str) -> None:
        self._run = run
        self._name = name
        self._spans = run.find_spans(name)

    def exists(self) -> SpanAssertion:
        """断言 span 存在"""
        if not self._spans:
            all_names = [s.name for s in self._run.spans]
            raise AssertionError(
                f"Span '{self._name}' not found. "
                f"Available spans: {all_names}"
            )
        return self

    def with_input(self, **expected: Any) -> SpanAssertion:
        """断言 span 输入包含指定字段（至少一个 span 匹配即可）"""
        self.exists()
        for span in self._spans:
            if span.input is not None and self._dict_contains(span.input, expected):
                return self

        actual = [s.input for s in self._spans if s.input is not None]
        raise AssertionError(
            f"Span '{self._name}': no matching input found.\n"
            f"Expected fields: {expected}\n"
            f"Actual inputs: {actual}"
        )

    def with_output(self, **expected: Any) -> SpanAssertion:
        """断言 span 输出包含指定字段（至少一个 span 匹配即可）"""
        self.exists()
        for span in self._spans:
            if span.output is not None and self._dict_contains(span.output, expected):
                return self

        actual = [s.output for s in self._spans if s.output is not None]
        raise AssertionError(
            f"Span '{self._name}': no matching output found.\n"
            f"Expected fields: {expected}\n"
            f"Actual outputs: {actual}"
        )

    def has_error(self, expected_substring: str | None = None) -> SpanAssertion:
        """断言 span 处于 error 状态"""
        self.exists()
        error_spans = [s for s in self._spans if s.status == "error"]
        if not error_spans:
            raise AssertionError(
                f"Span '{self._name}': expected error status, but all spans have status 'success'"
            )
        if expected_substring is not None:
            error_msgs = [s.error for s in error_spans]
            if not any(expected_substring in (msg or "") for msg in error_msgs):
                raise AssertionError(
                    f"Span '{self._name}': expected error containing '{expected_substring}'.\n"
                    f"Actual errors: {error_msgs}"
                )
        return self

    @staticmethod
    def _dict_contains(actual: Any, expected: dict[str, Any]) -> bool:
        """检查 actual 字典是否包含 expected 中的所有键值对"""
        if not isinstance(actual, dict):
            return False
        return all(
            actual.get(k) == v
            for k, v in expected.items()
        )
```

**还需要在 TraceRecorder 中添加断言方法：**

```python
# 在 recorder.py 的 TraceRecorder 类中添加以下方法：

    def success(self) -> bool:
        """断言 run 整体成功"""
        return self.run.is_success()

    def has_span(self, name: str) -> SpanAssertion:
        """断言存在指定名称的 span，返回 SpanAssertion"""
        from .assertions import SpanAssertion
        return SpanAssertion(self.run, name)

    def span_count(self) -> int:
        """span 总数"""
        return self.run.span_count()

    def duration_ms(self) -> float | None:
        """run 总耗时"""
        return self.run.total_duration_ms
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/trace/test_assertions.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/ai_agent/trace/assertions.py tests/unit/trace/test_assertions.py
git commit -m "feat(trace): add pytest assertion API with chainable interface"
```

---

## Task 7: 公开 API __init__.py + pytest fixture

**Files:**
- Modify: `src/ai_agent/trace/__init__.py`
- Modify: `tests/conftest.py` (添加 trace_recorder fixture)

**Step 1: Write __init__.py**

```python
# src/ai_agent/trace/__init__.py
"""本地追踪系统

提供装饰器驱动的结构化追踪，零侵入记录执行轨迹到 JSON 文件。

Usage:
    from ai_agent.trace import trace_run, trace_span, TraceSpanCtx

    @trace_run("my_agent")
    async def run_agent(query: str) -> str:
        ...
"""

from .decorators import trace_run, trace_span, TraceSpanCtx
from .recorder import TraceRecorder
from .config import TraceConfig

__all__ = [
    "trace_run",
    "trace_span",
    "TraceSpanCtx",
    "TraceRecorder",
    "TraceConfig",
]
```

**Step 2: Add pytest fixture to conftest.py**

在 `tests/conftest.py` 中添加：

```python
@pytest.fixture
def trace_recorder(tmp_path):
    """为当前测试创建 TraceRecorder，测试结束自动 flush

    Usage:
        def test_something(trace_recorder):
            # ... run code that uses trace decorators ...
            assert trace_recorder.has_span("think").with_output(action="search")
    """
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.recorder import TraceRecorder

    config = TraceConfig(trace_dir=str(tmp_path))
    recorder = TraceRecorder(
        name="test",
        config=config,
    )
    recorder.start_span("test")
    yield recorder
    recorder.finish_span()
    recorder.finish_run()
```

**Step 3: Verify imports work**

Run: `uv run python -c "from ai_agent.trace import trace_run, trace_span, TraceSpanCtx, TraceRecorder; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add src/ai_agent/trace/__init__.py tests/conftest.py
git commit -m "feat(trace): add public API and pytest trace_recorder fixture"
```

---

## Task 8: 接入 ReActAgent

**Files:**
- Modify: `src/ai_agent/agents/react/graph.py`
- Create: `tests/unit/trace/test_react_integration.py`

**Step 1: Write the failing integration test**

```python
# tests/unit/trace/test_react_integration.py
"""ReActAgent + Trace 系统集成单元测试

使用 mock LLM 验证装饰器接入不影响现有逻辑。
"""

import pytest

from ai_agent.trace.config import TraceConfig
from ai_agent.trace.decorators import trace_run, trace_span


class MockLLMResponse:
    """模拟 LLM 响应"""
    def __init__(self, content: str):
        self.content = content


class MockLLM:
    """模拟 LLM 客户端"""
    def __init__(self, response: str = '{"action": "finish", "params": {"result": "42"}}'):
        self._response = response

    async def ainvoke(self, messages: list) -> MockLLMResponse:
        return MockLLMResponse(self._response)


@pytest.mark.asyncio
async def test_trace_run_decorator_on_sync_function(tmp_path):
    """测试 @trace_run 装饰同步函数不影响返回值"""
    config = TraceConfig(trace_dir=str(tmp_path))

    @trace_run("sync_test", config=config)
    def compute():
        return 42

    result = compute()
    assert result == 42


@pytest.mark.asyncio
async def test_trace_decorator_chain(tmp_path):
    """测试装饰器链：trace_run 包含 trace_span"""
    config = TraceConfig(trace_dir=str(tmp_path))

    @trace_span("helper", config=config)
    def helper():
        return "helper_result"

    @trace_run("main_run", config=config)
    def main():
        return helper()

    result = main()
    assert result == "helper_result"

    # 验证 trace 文件
    import json
    from pathlib import Path
    trace_files = list(Path(str(tmp_path)).rglob("*.json"))
    assert len(trace_files) == 1

    with open(trace_files[0], encoding="utf-8") as f:
        data = json.load(f)

    span_names = [s["name"] for s in data["spans"]]
    assert "main_run" in span_names
    assert "helper" in span_names


@pytest.mark.asyncio
async def test_trace_span_with_mock_llm(tmp_path):
    """测试 trace_span 在模拟 LLM 场景下正常工作"""
    config = TraceConfig(trace_dir=str(tmp_path))

    llm = MockLLM()

    @trace_span("llm_call", config=config)
    async def call_llm(prompt: str) -> str:
        response = await llm.ainvoke([prompt])
        return str(response.content)

    @trace_run("agent_step", config=config)
    async def agent_step():
        result = await call_llm("test prompt")
        return result

    result = await agent_step()
    assert "finish" in result

    # 验证 trace
    import json
    from pathlib import Path
    trace_files = list(Path(str(tmp_path)).rglob("*.json"))
    assert len(trace_files) == 1

    with open(trace_files[0], encoding="utf-8") as f:
        data = json.load(f)

    llm_span = next(s for s in data["spans"] if s["name"] == "llm_call")
    assert llm_span["status"] == "success"
    assert "test prompt" in str(llm_span["input"])
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/unit/trace/test_react_integration.py -v`
Expected: ALL PASS

> **注意：** 此测试仅验证装饰器与 mock LLM 的集成。ReActAgent 本身的装饰器接入在 Task 9 完成，此时不修改 graph.py，先确保 trace 系统本身稳定。

**Step 3: Commit**

```bash
git add tests/unit/trace/test_react_integration.py
git commit -m "test(trace): add integration tests for trace decorators with mock LLM"
```

---

## Task 9: 集成测试 — 单次 LLM 调用（真实 API）

**Files:**
- Create: `tests/integration/test_trace_llm_real.py`

**Step 1: Write the integration test**

```python
# tests/integration/test_trace_llm_real.py
"""单次 LLM 调用的 trace 集成测试（真实 API）

验证 @trace_span 在真实 LLM 调用场景下正确记录 prompt 和 response。
"""

import json
import os
from pathlib import Path

import pytest

requires_real_api = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-api-key",
    reason="需要真实的 OPENAI_API_KEY",
)


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_single_llm_call(tmp_path):
    """测试单次 LLM 调用完整记录 prompt 和 response"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run, trace_span

    config = TraceConfig(trace_dir=str(tmp_path))
    llm = create_llm_client()

    @trace_span("llm_call", config=config)
    async def call_llm(prompt: str) -> str:
        from langchain_core.messages import HumanMessage
        response = await llm.ainvoke([HumanMessage(prompt)])
        return str(response.content)

    @trace_run("single_llm_test", config=config)
    async def test():
        return await call_llm("What is 2+2? Answer with just the number.")

    result = await test()
    assert result is not None
    assert len(result) > 0

    # 验证 trace 文件
    trace_files = list(Path(str(tmp_path)).rglob("*.json"))
    assert len(trace_files) == 1

    with open(trace_files[0], encoding="utf-8") as f:
        data = json.load(f)

    # 验证顶层结构
    assert data["name"] == "single_llm_test"
    assert data["status"] == "success"
    assert data["total_duration_ms"] > 0

    # 验证 span 记录
    assert len(data["spans"]) >= 2  # single_llm_test + llm_call

    llm_span = next(s for s in data["spans"] if s["name"] == "llm_call")
    assert llm_span["status"] == "success"
    assert llm_span["duration_ms"] > 0
    # 验证 input 包含 prompt
    assert "2+2" in str(llm_span["input"])
    # 验证 output 包含 LLM 响应
    assert len(str(llm_span["output"])) > 0


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_llm_call_with_error_handling(tmp_path):
    """测试 LLM 调用异常时 trace 记录错误"""
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run, trace_span

    config = TraceConfig(trace_dir=str(tmp_path))

    @trace_span("failing_call", config=config)
    async def fail():
        raise ConnectionError("API connection failed")

    @trace_run("error_test", config=config)
    async def test():
        return await fail()

    with pytest.raises(ConnectionError, match="API connection failed"):
        await test()

    # 验证 trace 文件
    trace_files = list(Path(str(tmp_path)).rglob("*.json"))
    assert len(trace_files) == 1

    with open(trace_files[0], encoding="utf-8") as f:
        data = json.load(f)

    assert data["status"] == "error"

    failing_span = next(
        (s for s in data["spans"] if s["name"] == "failing_call"), None
    )
    assert failing_span is not None
    assert failing_span["status"] == "error"
    assert "API connection failed" in failing_span["error"]
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_trace_llm_real.py -v -m integration_real`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/integration/test_trace_llm_real.py
git commit -m "test(trace): add real API integration test for single LLM call tracing"
```

---

## Task 10: 集成测试 — 单个工具执行（真实 API）

**Files:**
- Create: `tests/integration/test_trace_tool_real.py`

**Step 1: Write the integration test**

```python
# tests/integration/test_trace_tool_real.py
"""单个工具执行的 trace 集成测试（真实 API）

验证 @trace_span 在真实工具调用场景下正确记录输入参数和执行结果。
"""

import json
import os
from pathlib import Path

import pytest

requires_real_api = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-api-key",
    reason="需要真实的 OPENAI_API_KEY",
)


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_single_tool_execution(tmp_path):
    """测试单个工具执行完整记录输入和输出"""
    from ai_agent.tools.web.zhipu_web_search import ZhipuWebSearchTool
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run, trace_span

    config = TraceConfig(trace_dir=str(tmp_path))
    tool = ZhipuWebSearchTool()

    @trace_span("act:web_search", config=config)
    async def search(query: str) -> str:
        result = await tool.run(query=query)
        return str(result.data) if result.success else f"Error: {result.error}"

    @trace_run("tool_test", config=config)
    async def test():
        return await search("Python programming language")

    result = await test()
    assert result is not None
    assert len(result) > 0

    # 验证 trace 文件
    trace_files = list(Path(str(tmp_path)).rglob("*.json"))
    assert len(trace_files) == 1

    with open(trace_files[0], encoding="utf-8") as f:
        data = json.load(f)

    assert data["status"] == "success"

    search_span = next(
        (s for s in data["spans"] if s["name"] == "act:web_search"), None
    )
    assert search_span is not None
    assert search_span["status"] == "success"
    assert search_span["duration_ms"] > 0
    # 验证输入
    assert "Python" in str(search_span["input"])
    # 验证输出非空
    assert len(str(search_span["output"])) > 0
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_trace_tool_real.py -v -m integration_real`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/integration/test_trace_tool_real.py
git commit -m "test(trace): add real API integration test for tool execution tracing"
```

---

## Task 11: 集成测试 — 完整 ReAct 流程（真实 API）

**Files:**
- Create: `tests/integration/test_trace_react_real.py`

**Step 1: Write the integration test**

```python
# tests/integration/test_trace_react_real.py
"""完整 ReAct 流程的 trace 集成测试（真实 API）

验证 @trace_run + @trace_span 在完整 ReAct Agent 多轮循环中正确记录全链路。
"""

import json
import os
from pathlib import Path

import pytest

requires_real_api = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-api-key",
    reason="需要真实的 OPENAI_API_KEY",
)


@pytest.fixture
def trace_tools():
    """创建测试用工具"""
    from ai_agent.tools.base import BaseAgentTool, ToolResult

    class CalculatorTool(BaseAgentTool):
        @property
        def name(self) -> str:
            return "calculator"

        @property
        def description(self) -> str:
            return "Perform basic arithmetic. Input should be a math expression like '2+2'."

        @property
        def parameters(self) -> dict:
            return {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression"}
                },
                "required": ["expression"],
            }

        async def run(self, **kwargs) -> ToolResult:
            expression = kwargs.get("expression", "")
            allowed = set("0123456789+-*/(). ")
            if not all(c in allowed for c in expression):
                return ToolResult(success=False, data="", error="Invalid characters")
            result = eval(expression)
            return ToolResult(success=True, data=str(result))

    class EchoTool(BaseAgentTool):
        @property
        def name(self) -> str:
            return "echo"

        @property
        def description(self) -> str:
            return "Echo back the input text."

        @property
        def parameters(self) -> dict:
            return {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to echo"}
                },
                "required": ["text"],
            }

        async def run(self, **kwargs) -> ToolResult:
            text = kwargs.get("text", "")
            return ToolResult(success=True, data=f"Echo: {text}")

    return [CalculatorTool().to_langchain_tool(), EchoTool().to_langchain_tool()]


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_full_react_run(tmp_path, trace_tools):
    """测试完整 ReAct 流程的全链路追踪"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.agents.react import ReActAgent
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run, trace_span

    config = TraceConfig(trace_dir=str(tmp_path))
    llm = create_llm_client()

    @trace_run("react_full_test", config=config)
    async def run_agent():
        agent = ReActAgent(llm, tools=trace_tools, max_steps=5)
        return await agent.run("What is 15 + 27? Use the calculator tool.")

    result = await run_agent()
    assert result is not None
    assert len(result) > 0

    # 验证 trace 文件
    trace_files = list(Path(str(tmp_path)).rglob("*.json"))
    assert len(trace_files) == 1

    with open(trace_files[0], encoding="utf-8") as f:
        data = json.load(f)

    # 验证顶层结构
    assert data["name"] == "react_full_test"
    assert data["status"] == "success"
    assert data["total_duration_ms"] > 0
    assert len(data["spans"]) >= 1  # 至少有顶层 span

    # 验证每个 span 都有完整字段
    for span in data["spans"]:
        assert "name" in span
        assert "span_id" in span
        assert "started_at" in span
        assert "finished_at" in span
        assert "duration_ms" in span
        assert "status" in span


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_react_stream(tmp_path, trace_tools):
    """测试 ReAct stream 模式的追踪"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.agents.react import ReActAgent
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run

    config = TraceConfig(trace_dir=str(tmp_path))
    llm = create_llm_client()

    @trace_run("react_stream_test", config=config)
    async def run_agent():
        agent = ReActAgent(llm, tools=trace_tools, max_steps=5)
        events = []
        async for event in agent.stream("What is 2 * 3? Use the calculator tool."):
            events.append(event)
        return events

    events = await run_agent()
    assert len(events) > 0

    # 验证 trace 文件
    trace_files = list(Path(str(tmp_path)).rglob("*.json"))
    assert len(trace_files) == 1

    with open(trace_files[0], encoding="utf-8") as f:
        data = json.load(f)

    assert data["name"] == "react_stream_test"
    assert data["status"] == "success"


@pytest.mark.integration_real
@requires_real_api
@pytest.mark.asyncio
async def test_trace_react_error_handling(tmp_path, trace_tools):
    """测试 ReAct 流程异常时的追踪记录"""
    from ai_agent.llm.client import create_llm_client
    from ai_agent.agents.react import ReActAgent
    from ai_agent.trace.config import TraceConfig
    from ai_agent.trace.decorators import trace_run

    config = TraceConfig(trace_dir=str(tmp_path))
    llm = create_llm_client()

    @trace_run("react_error_test", config=config)
    async def run_agent():
        # 不传工具，直接提问
        agent = ReActAgent(llm, tools=[], max_steps=3)
        return await agent.run("What is the capital of France?")

    result = await run_agent()
    assert result is not None
    assert "Paris" in result

    trace_files = list(Path(str(tmp_path)).rglob("*.json"))
    assert len(trace_files) == 1

    with open(trace_files[0], encoding="utf-8") as f:
        data = json.load(f)

    assert data["status"] == "success"
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_trace_react_real.py -v -m integration_real`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/integration/test_trace_react_real.py
git commit -m "test(trace): add real API integration tests for full ReAct flow tracing"
```

---

## Task 12: 类型检查 + 全量测试

**Step 1: Run mypy**

Run: `uv run mypy src/ai_agent/trace/`
Expected: 0 errors

**Step 2: Run all unit tests**

Run: `uv run pytest tests/unit/trace/ -v`
Expected: ALL PASS

**Step 3: Run all integration tests**

Run: `uv run pytest tests/integration/test_trace_llm_real.py tests/integration/test_trace_tool_real.py tests/integration/test_trace_react_real.py -v -m integration_real`
Expected: ALL PASS

**Step 4: Fix any issues**

如发现类型错误或测试失败，逐一修复。

**Step 5: Commit**

```bash
git commit -m "fix(trace): resolve type check and test issues"
```
