"""Tests for ContextVar-based trace context propagation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from ai_agent.trace.context import (
    active_run,
    clear_run,
    current_parent_id,
    pop_span,
    push_span,
    set_active_run,
)
from ai_agent.trace.types import TraceRun


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trace_run(run_id: str = "run_1", name: str = "test") -> TraceRun:
    """Create a minimal TraceRun for testing."""
    return TraceRun(
        run_id=run_id,
        name=name,
        started_at=datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc),
        finished_at=None,
        spans=[],
        tags=[],
        metadata=None,
    )


# ---------------------------------------------------------------------------
# TestContextVarPropagation
# ---------------------------------------------------------------------------


class TestContextVarPropagation:
    """Tests for basic ContextVar get/set/clear behavior."""

    def test_default_no_active_run(self) -> None:
        """active_run() returns None when no run has been set."""
        assert active_run() is None

    def test_set_and_get_active_run(self) -> None:
        """set_active_run() stores a TraceRun retrievable via active_run()."""
        run = _make_trace_run(run_id="run_a")
        set_active_run(run)
        try:
            assert active_run() is run
            assert active_run() is not None
            assert active_run().run_id == "run_a"  # type: ignore[union-attr]
        finally:
            clear_run()

    def test_set_active_run_replaces_previous(self) -> None:
        """Setting a new active run replaces the previous one."""
        run_a = _make_trace_run(run_id="run_a")
        run_b = _make_trace_run(run_id="run_b")
        set_active_run(run_a)
        set_active_run(run_b)
        try:
            assert active_run() is run_b
        finally:
            clear_run()

    def test_clear_run(self) -> None:
        """clear_run() resets active_run() to None."""
        run = _make_trace_run()
        set_active_run(run)
        clear_run()
        assert active_run() is None

    def test_clear_run_idempotent(self) -> None:
        """clear_run() can be called multiple times without error."""
        clear_run()
        clear_run()
        assert active_run() is None

    def test_push_span_and_current_parent_id(self) -> None:
        """push_span() pushes onto the stack; current_parent_id() returns top."""
        push_span("span_1")
        try:
            assert current_parent_id() == "span_1"
        finally:
            pop_span()

    def test_push_span_nesting(self) -> None:
        """Multiple push_span calls build a stack; top is always the latest."""
        push_span("root")
        push_span("child_a")
        push_span("child_b")
        try:
            assert current_parent_id() == "child_b"
            pop_span()
            assert current_parent_id() == "child_a"
            pop_span()
            assert current_parent_id() == "root"
        finally:
            # Clean up remaining
            pop_span()

    def test_pop_span_removes_top(self) -> None:
        """pop_span() removes the top of the stack."""
        push_span("a")
        push_span("b")
        pop_span()
        try:
            assert current_parent_id() == "a"
        finally:
            pop_span()

    def test_pop_span_empty_stack_noop(self) -> None:
        """pop_span() on an empty stack is a no-op (does not raise)."""
        pop_span()  # should not raise
        assert current_parent_id() is None

    def test_current_parent_id_empty_stack(self) -> None:
        """current_parent_id() returns None when no spans have been pushed."""
        assert current_parent_id() is None

    def test_span_stack_isolation_from_run(self) -> None:
        """The span stack operates independently of the active run."""
        push_span("span_x")
        try:
            assert active_run() is None
            assert current_parent_id() == "span_x"
        finally:
            pop_span()


# ---------------------------------------------------------------------------
# TestAsyncIsolation
# ---------------------------------------------------------------------------


class TestAsyncIsolation:
    """Tests verifying that ContextVars are isolated across async tasks."""

    @pytest.mark.asyncio
    async def test_concurrent_tasks_isolated_active_run(self) -> None:
        """Two concurrent asyncio tasks see their own active_run, not each other's."""
        run_a = _make_trace_run(run_id="task_a")
        run_b = _make_trace_run(run_id="task_b")

        async def task_a() -> str:
            set_active_run(run_a)
            await asyncio.sleep(0.01)  # yield to let task_b also set
            result = active_run()
            clear_run()
            return result.run_id if result else "none"

        async def task_b() -> str:
            await asyncio.sleep(0.005)  # start slightly after task_a
            set_active_run(run_b)
            result = active_run()
            clear_run()
            return result.run_id if result else "none"

        results = await asyncio.gather(task_a(), task_b())
        assert results == ["task_a", "task_b"]

    @pytest.mark.asyncio
    async def test_concurrent_tasks_isolated_span_stack(self) -> None:
        """Two concurrent asyncio tasks have independent span stacks."""
        async def task_1() -> str | None:
            push_span("t1_root")
            push_span("t1_child")
            await asyncio.sleep(0.01)  # yield
            parent = current_parent_id()
            pop_span()
            pop_span()
            return parent

        async def task_2() -> str | None:
            await asyncio.sleep(0.005)
            push_span("t2_root")
            parent = current_parent_id()
            pop_span()
            return parent

        results = await asyncio.gather(task_1(), task_2())
        assert results == ["t1_child", "t2_root"]

    @pytest.mark.asyncio
    async def test_task_inherits_parent_context_on_create(self) -> None:
        """A task created after setting context inherits that context."""
        run_parent = _make_trace_run(run_id="parent_run")
        set_active_run(run_parent)

        async def child_task() -> str | None:
            run = active_run()
            return run.run_id if run else None

        try:
            result = await child_task()
            assert result == "parent_run"
        finally:
            clear_run()
