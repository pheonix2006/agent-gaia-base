"""Tests for trace decorators and context manager."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from ai_agent.trace.config import TraceConfig
from ai_agent.trace.context import (
    _active_recorder,
    _span_stack,
    active_recorder,
    clear_run,
    set_active_recorder,
)
from ai_agent.trace.decorators import TraceSpanCtx, trace_run, trace_span
from ai_agent.trace.recorder import TraceRecorder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_trace_context() -> None:
    """Reset trace context vars before every test to prevent cross-test leakage."""
    clear_run()
    _span_stack.set(None)
    _active_recorder.set(None)
    yield
    clear_run()
    _span_stack.set(None)
    _active_recorder.set(None)


@pytest.fixture
def tmp_trace_dir(tmp_path: str) -> str:
    """Return a temporary directory path for trace output."""
    return str(tmp_path)


@pytest.fixture
def trace_config(tmp_trace_dir: str) -> TraceConfig:
    """Return a TraceConfig writing to a temporary directory."""
    return TraceConfig(enabled=True, trace_dir=tmp_trace_dir)


# ---------------------------------------------------------------------------
# trace_run decorator
# ---------------------------------------------------------------------------


class TestTraceRunDecorator:
    """Tests for the @trace_run decorator."""

    def test_sync_creates_run_and_json(self, trace_config: TraceConfig) -> None:
        """Sync decorated function should create a trace run and flush JSON."""

        @trace_run("my_sync_fn", config=trace_config)
        def add(a: int, b: int) -> int:
            return a + b

        result = add(2, 3)
        assert result == 5

        # A JSON file should have been written
        json_files = _collect_json_files(trace_config.trace_dir)
        assert len(json_files) == 1

        with open(json_files[0], encoding="utf-8") as f:
            data = json.load(f)

        assert data["name"] == "my_sync_fn"
        assert data["status"] == "success"
        assert len(data["spans"]) == 1
        assert data["spans"][0]["name"] == "add"
        assert data["spans"][0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_async_creates_run(self, trace_config: TraceConfig) -> None:
        """Async decorated function should create a trace run."""

        @trace_run("my_async_fn", config=trace_config)
        async def greet(name: str) -> str:
            return f"hello {name}"

        result = await greet("world")
        assert result == "hello world"

        json_files = _collect_json_files(trace_config.trace_dir)
        assert len(json_files) == 1

        with open(json_files[0], encoding="utf-8") as f:
            data = json.load(f)

        assert data["name"] == "my_async_fn"
        assert len(data["spans"]) == 1
        assert data["spans"][0]["name"] == "greet"

    def test_nested_trace_span_inside_trace_run(self, trace_config: TraceConfig) -> None:
        """trace_span inside trace_run should be recorded as a child span."""

        @trace_span("inner_op")
        def helper(x: int) -> int:
            return x * 2

        @trace_run("outer_fn", config=trace_config)
        def outer(x: int) -> int:
            return helper(x) + 1

        result = outer(5)
        assert result == 11

        json_files = _collect_json_files(trace_config.trace_dir)
        assert len(json_files) == 1

        with open(json_files[0], encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["spans"]) == 2
        # Spans are appended in finish order: inner_op finishes first, then outer
        inner_span = next(s for s in data["spans"] if s["name"] == "inner_op")
        outer_span = next(s for s in data["spans"] if s["name"] == "outer")
        assert inner_span["parent_id"] is not None
        assert outer_span["parent_id"] is None

    def test_exception_creates_error_run(self, trace_config: TraceConfig) -> None:
        """Exceptions should be recorded and re-raised."""

        @trace_run("failing_fn", config=trace_config)
        def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            fail()

        json_files = _collect_json_files(trace_config.trace_dir)
        assert len(json_files) == 1

        with open(json_files[0], encoding="utf-8") as f:
            data = json.load(f)

        assert data["status"] == "error"
        assert len(data["spans"]) == 1
        span = data["spans"][0]
        assert span["status"] == "error"
        assert span["error"] is not None
        assert "ValueError" in span["error"]

    def test_preserves_function_name(self, trace_config: TraceConfig) -> None:
        """functools.wraps should preserve the original function name."""

        @trace_run(config=trace_config)
        def my_special_function() -> int:
            return 42

        assert my_special_function.__name__ == "my_special_function"

    def test_default_run_name_is_function_name(self, trace_config: TraceConfig) -> None:
        """When no name is given, run name defaults to the function name."""

        @trace_run(config=trace_config)
        def compute() -> int:
            return 1

        compute()

        json_files = _collect_json_files(trace_config.trace_dir)
        with open(json_files[0], encoding="utf-8") as f:
            data = json.load(f)
        assert data["name"] == "compute"

    def test_tags_applied_to_run(self, trace_config: TraceConfig) -> None:
        """Tags should be attached to the run."""

        @trace_run("tagged_run", config=trace_config, tags=["unit", "fast"])
        def work() -> None:
            pass

        work()

        json_files = _collect_json_files(trace_config.trace_dir)
        with open(json_files[0], encoding="utf-8") as f:
            data = json.load(f)
        assert "unit" in data["tags"]
        assert "fast" in data["tags"]


# ---------------------------------------------------------------------------
# trace_span decorator
# ---------------------------------------------------------------------------


class TestTraceSpanDecorator:
    """Tests for the @trace_span decorator."""

    def test_sync_records_span_in_trace_run(self, trace_config: TraceConfig) -> None:
        """Sync decorated function should record a span when inside a trace_run."""

        @trace_span("my_span")
        def helper() -> str:
            return "ok"

        rec = TraceRecorder("parent_run", config=trace_config)
        try:
            result = helper()
            assert result == "ok"
        finally:
            rec.finish_run()

        run = rec._run
        assert run.span_count() == 1
        span = run.spans[0]
        assert span.name == "my_span"
        assert span.status == "success"

    @pytest.mark.asyncio
    async def test_async_records_span(self, trace_config: TraceConfig) -> None:
        """Async decorated function should record a span when inside a trace_run."""

        @trace_span("async_span")
        async def async_helper() -> int:
            return 99

        rec = TraceRecorder("async_parent", config=trace_config)
        try:
            result = await async_helper()
            assert result == 99
        finally:
            rec.finish_run()

        run = rec._run
        assert run.span_count() == 1
        span = run.spans[0]
        assert span.name == "async_span"
        assert span.status == "success"

    def test_exception_captured_and_reraised(self, trace_config: TraceConfig) -> None:
        """Exceptions should be captured in the span and re-raised."""

        @trace_span("failing_span")
        def fail() -> None:
            raise RuntimeError("span error")

        rec = TraceRecorder("error_parent", config=trace_config)
        try:
            with pytest.raises(RuntimeError, match="span error"):
                fail()
        finally:
            rec.finish_run()

        run = rec._run
        assert run.span_count() == 1
        span = run.spans[0]
        assert span.status == "error"
        assert span.error is not None
        assert "RuntimeError" in span.error

    def test_no_active_run_silent_skip(self) -> None:
        """Without an active recorder, trace_span should just call the function."""

        @trace_span("orphan_span")
        def work() -> str:
            return "done"

        result = work()
        assert result == "done"


# ---------------------------------------------------------------------------
# TraceSpanCtx context manager
# ---------------------------------------------------------------------------


class TestTraceSpanContextManager:
    """Tests for the TraceSpanCtx context manager."""

    def test_sync_records_span(self, trace_config: TraceConfig) -> None:
        """Sync context manager should record a span."""

        rec = TraceRecorder("ctx_run", config=trace_config)
        try:
            with TraceSpanCtx("my_block"):
                pass  # no-op work
            rec.finish_run()
        except Exception:
            rec.finish_run()
            raise

        run = rec._run
        assert run.span_count() == 1
        span = run.spans[0]
        assert span.name == "my_block"
        assert span.status == "success"

    def test_error_handling(self, trace_config: TraceConfig) -> None:
        """Errors inside the context manager should be recorded."""

        rec = TraceRecorder("error_ctx_run", config=trace_config)
        try:
            with pytest.raises(ValueError, match="ctx_error"):
                with TraceSpanCtx("failing_block"):
                    raise ValueError("ctx_error")
        finally:
            rec.finish_run()

        run = rec._run
        assert run.span_count() == 1
        span = run.spans[0]
        assert span.name == "failing_block"
        assert span.status == "error"
        assert span.error is not None

    @pytest.mark.asyncio
    async def test_async_context_manager(self, trace_config: TraceConfig) -> None:
        """Async context manager should record a span."""

        rec = TraceRecorder("async_ctx_run", config=trace_config)
        try:
            async with TraceSpanCtx("async_block"):
                await asyncio.sleep(0.001)
            rec.finish_run()
        except Exception:
            rec.finish_run()
            raise

        run = rec._run
        assert run.span_count() == 1
        span = run.spans[0]
        assert span.name == "async_block"
        assert span.status == "success"

    def test_set_tag_stores_metadata(self, trace_config: TraceConfig) -> None:
        """set_tag should store metadata on the span."""

        rec = TraceRecorder("tag_ctx_run", config=trace_config)
        try:
            with TraceSpanCtx("tagged_block") as ctx:
                ctx.set_tag("source", "test")
                ctx.set_tag("count", 42)
            rec.finish_run()
        except Exception:
            rec.finish_run()
            raise

        run = rec._run
        assert run.span_count() == 1
        span = run.spans[0]
        assert span.input is not None
        assert span.input["metadata"] == {"source": "test", "count": 42}

    def test_no_active_recorder_no_error(self) -> None:
        """Without an active recorder, the context manager should not raise."""

        with TraceSpanCtx("orphan_block"):
            pass  # should work fine

    def test_input_passed_to_span(self, trace_config: TraceConfig) -> None:
        """Input passed in constructor should appear on the span."""

        rec = TraceRecorder("input_run", config=trace_config)
        try:
            with TraceSpanCtx("input_block", input={"query": "hello"}):
                pass
            rec.finish_run()
        except Exception:
            rec.finish_run()
            raise

        run = rec._run
        span = run.spans[0]
        assert span.input == {"query": "hello"}

    def test_set_output_sync(self, trace_config: TraceConfig) -> None:
        """set_output should store output on the span (sync context manager)."""

        rec = TraceRecorder("output_run", config=trace_config)
        try:
            with TraceSpanCtx("output_block") as ctx:
                ctx.set_output({"result": 42, "label": "answer"})
            rec.finish_run()
        except Exception:
            rec.finish_run()
            raise

        run = rec._run
        span = run.spans[0]
        assert span.output == {"result": 42, "label": "answer"}

    @pytest.mark.asyncio
    async def test_set_output_async(self, trace_config: TraceConfig) -> None:
        """set_output should store output on the span (async context manager)."""

        rec = TraceRecorder("async_output_run", config=trace_config)
        try:
            async with TraceSpanCtx("async_output_block") as ctx:
                ctx.set_output({"data": "async result data"})
            rec.finish_run()
        except Exception:
            rec.finish_run()
            raise

        run = rec._run
        span = run.spans[0]
        assert span.output == {"data": "async result data"}

    def test_set_output_with_input_and_metadata(self, trace_config: TraceConfig) -> None:
        """set_output should work alongside input and metadata."""

        rec = TraceRecorder("combined_run", config=trace_config)
        try:
            with TraceSpanCtx(
                "combined_block",
                input={"query": "test"},
                metadata={"step": 1},
            ) as ctx:
                ctx.set_output({"action": "finish", "params": {"result": "ok"}})
            rec.finish_run()
        except Exception:
            rec.finish_run()
            raise

        run = rec._run
        span = run.spans[0]
        assert span.input == {"query": "test", "metadata": {"step": 1}}
        assert span.output == {"action": "finish", "params": {"result": "ok"}}

    def test_no_set_output_gives_none(self, trace_config: TraceConfig) -> None:
        """When set_output is not called, span output should be None."""

        rec = TraceRecorder("no_output_run", config=trace_config)
        try:
            with TraceSpanCtx("no_output_block"):
                pass
            rec.finish_run()
        except Exception:
            rec.finish_run()
            raise

        run = rec._run
        span = run.spans[0]
        assert span.output is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_json_files(root_dir: str) -> list[str]:
    """Recursively collect all .json files under *root_dir*."""
    result: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith(".json"):
                result.append(os.path.join(dirpath, fname))
    return sorted(result)
