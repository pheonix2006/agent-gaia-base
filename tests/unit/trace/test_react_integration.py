"""Integration tests for trace decorators with ReAct agent-like execution patterns.

Uses mock LLM to verify that @trace_run, @trace_span, and TraceSpanCtx
work correctly together, reproducing the call patterns a ReActAgent would
exhibit during a typical run.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import pytest

from ai_agent.trace import TraceConfig, TraceSpanCtx, trace_run, trace_span


# ---------------------------------------------------------------------------
# Mock LLM infrastructure
# ---------------------------------------------------------------------------


@dataclass
class MockLLMResponse:
    """Minimal mock of an LLM response object."""

    content: str


class MockLLM:
    """Mock LLM that returns a fixed JSON response."""

    def __init__(self, response_content: str) -> None:
        self._content = response_content

    async def ainvoke(self, messages: list[Any]) -> MockLLMResponse:
        return MockLLMResponse(self._content)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_trace_context() -> None:
    """Reset trace context vars to prevent cross-test leakage."""
    from ai_agent.trace.context import (
        _active_recorder,
        _span_stack,
        clear_run,
        set_active_recorder,
    )

    clear_run()
    _span_stack.set(None)
    _active_recorder.set(None)
    yield
    clear_run()
    _span_stack.set(None)
    _active_recorder.set(None)


@pytest.fixture
def trace_config(tmp_path) -> TraceConfig:
    """Return a TraceConfig writing to a temporary directory."""
    return TraceConfig(trace_dir=str(tmp_path))


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


def _load_trace_json(trace_config: TraceConfig) -> dict[str, Any]:
    """Load the single JSON file produced by a trace run."""
    json_files = _collect_json_files(trace_config.trace_dir)
    assert len(json_files) == 1, f"Expected 1 JSON file, got {len(json_files)}"
    with open(json_files[0], encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTraceRunOnSyncFunction:
    """Verify @trace_run on a simple sync function returns correct value."""

    def test_trace_run_on_sync_function(self, trace_config: TraceConfig) -> None:
        """trace_run wrapping a sync function should return the correct value
        and write a valid JSON trace file."""

        @trace_run("compute_answer", config=trace_config)
        def compute(x: int, y: int) -> int:
            return x * y + 1

        result = compute(3, 7)
        assert result == 22, "Decorator should not alter the return value"

        data = _load_trace_json(trace_config)
        assert data["name"] == "compute_answer"
        assert data["status"] == "success"
        assert len(data["spans"]) == 1

        span = data["spans"][0]
        assert span["name"] == "compute"
        assert span["status"] == "success"
        assert span["parent_id"] is None


class TestTraceDecoratorChain:
    """Verify @trace_run wrapping @trace_span creates nested spans in JSON."""

    def test_trace_decorator_chain(self, trace_config: TraceConfig) -> None:
        """trace_run + trace_span should produce parent-child nesting."""

        @trace_span("parse_input")
        def parse(x: str) -> dict[str, Any]:
            return {"value": int(x), "source": "user"}

        @trace_run("agent_run", config=trace_config)
        def run_agent(raw_input: str) -> str:
            parsed = parse(raw_input)
            return str(parsed["value"] * 2)

        result = run_agent("21")
        assert result == "42"

        data = _load_trace_json(trace_config)
        assert len(data["spans"]) == 2

        parse_span = next(s for s in data["spans"] if s["name"] == "parse_input")
        run_span = next(s for s in data["spans"] if s["name"] == "run_agent")

        # The run span is the root; parse_input is its child
        assert run_span["parent_id"] is None
        assert parse_span["parent_id"] is not None
        assert parse_span["parent_id"] == run_span["span_id"]


class TestTraceSpanWithMockLLM:
    """Verify @trace_span on async function calling mock LLM records I/O."""

    @pytest.mark.asyncio
    async def test_trace_span_with_mock_llm(self, trace_config: TraceConfig) -> None:
        """An async trace_span calling a mock LLM should record input/output."""

        mock_llm = MockLLM('{"action": "finish", "params": {"result": "42"}}')
        captured_input: dict[str, Any] | None = None
        captured_output: Any = None

        @trace_span("llm.call")
        async def call_llm(messages: list[dict[str, str]]) -> str:
            nonlocal captured_input, captured_output
            captured_input = {"messages": messages}
            response = await mock_llm.ainvoke(messages)
            captured_output = response.content
            return response.content

        @trace_run("react_step", config=trace_config)
        async def react_step(query: str) -> str:
            messages = [{"role": "user", "content": query}]
            result = await call_llm(messages)
            return result

        answer = await react_step("What is the answer?")
        assert answer == '{"action": "finish", "params": {"result": "42"}}'

        data = _load_trace_json(trace_config)
        assert data["status"] == "success"

        llm_span = next(s for s in data["spans"] if s["name"] == "llm.call")
        assert llm_span["status"] == "success"
        assert llm_span["output"]["value"] == captured_output
        assert llm_span["parent_id"] is not None


class TestTraceRunWithMultipleSpans:
    """Verify a trace_run containing multiple trace_spans records all of them."""

    def test_trace_run_with_multiple_spans(self, trace_config: TraceConfig) -> None:
        """Multiple trace_spans inside a trace_run should all be recorded."""

        @trace_span("tool.lookup")
        def lookup(key: str) -> str:
            return f"result_of_{key}"

        @trace_span("tool.compute")
        def compute(values: list[str]) -> int:
            return sum(len(v) for v in values)

        @trace_span("tool.format")
        def format_result(value: int) -> str:
            return f"The answer is {value}"

        @trace_run("multi_step_agent", config=trace_config)
        def run_agent(query: str) -> str:
            r1 = lookup(query)
            r2 = lookup("extra")
            total = compute([r1, r2])
            return format_result(total)

        result = run_agent("test_key")
        assert result == "The answer is 33"  # len("result_of_test_key") + len("result_of_extra") = 17 + 16

        data = _load_trace_json(trace_config)
        span_names = [s["name"] for s in data["spans"]]
        assert span_names.count("tool.lookup") == 2
        assert span_names.count("tool.compute") == 1
        assert span_names.count("tool.format") == 1
        assert span_names.count("run_agent") == 1
        assert len(data["spans"]) == 5

        # All child spans should have a parent_id pointing to the run span
        run_span = next(s for s in data["spans"] if s["name"] == "run_agent")
        for span in data["spans"]:
            if span["name"] != "run_agent":
                assert span["parent_id"] == run_span["span_id"]


class TestTraceSpanErrorPropagation:
    """Verify error in trace_span is recorded but still raised to caller."""

    def test_trace_span_error_propagation(self, trace_config: TraceConfig) -> None:
        """An error inside trace_span should be recorded and re-raised."""

        @trace_span("risky_operation")
        def risky_step() -> str:
            raise RuntimeError("database connection failed")

        @trace_run("agent_with_error", config=trace_config)
        def run_agent() -> str:
            return risky_step()

        with pytest.raises(RuntimeError, match="database connection failed"):
            run_agent()

        data = _load_trace_json(trace_config)
        assert data["status"] == "error"

        error_span = next(s for s in data["spans"] if s["name"] == "risky_operation")
        assert error_span["status"] == "error"
        assert error_span["error"] is not None
        assert "RuntimeError" in error_span["error"]
        assert "database connection failed" in error_span["error"]


class TestContextManagerInRun:
    """Verify TraceSpanCtx used inside trace_run records correctly."""

    @pytest.mark.asyncio
    async def test_context_manager_in_run(self, trace_config: TraceConfig) -> None:
        """TraceSpanCtx inside trace_run should be recorded as a child span."""

        @trace_run("agent_with_ctx", config=trace_config)
        async def run_agent(query: str) -> str:
            async with TraceSpanCtx("retrieval", input={"query": query}):
                # Simulate a retrieval step
                await asyncio_sleep_zero()

            async with TraceSpanCtx("reasoning") as ctx:
                ctx.set_tag("model", "mock-gpt4")
                await asyncio_sleep_zero()

            return f"done: {query}"

        result = await run_agent("test query")
        assert result == "done: test query"

        data = _load_trace_json(trace_config)
        assert data["status"] == "success"

        # Should have: run_agent (root), retrieval, reasoning (children)
        assert len(data["spans"]) == 3

        run_span = next(s for s in data["spans"] if s["name"] == "run_agent")
        retrieval_span = next(s for s in data["spans"] if s["name"] == "retrieval")
        reasoning_span = next(s for s in data["spans"] if s["name"] == "reasoning")

        assert run_span["parent_id"] is None
        assert retrieval_span["parent_id"] == run_span["span_id"]
        assert reasoning_span["parent_id"] == run_span["span_id"]

        # Verify retrieval input
        assert retrieval_span["input"]["query"] == "test query"

        # Verify reasoning metadata
        assert reasoning_span["input"]["metadata"]["model"] == "mock-gpt4"


class TestMixedDecoratorsAndContextManagers:
    """Verify trace_span decorators and TraceSpanCtx can be mixed in one run."""

    @pytest.mark.asyncio
    async def test_mixed_span_types_in_single_run(
        self, trace_config: TraceConfig
    ) -> None:
        """trace_span decorator + TraceSpanCtx in one trace_run should all record."""

        @trace_span("llm.call")
        async def call_llm(msg: str) -> str:
            return f"response_to_{msg}"

        @trace_run("hybrid_agent", config=trace_config)
        async def run_agent(query: str) -> str:
            # Use decorator-based span
            llm_result = await call_llm(query)

            # Use context manager-based span
            async with TraceSpanCtx("tool.execute", input={"command": "search"}):
                await asyncio_sleep_zero()

            return llm_result

        result = await run_agent("hello")
        assert result == "response_to_hello"

        data = _load_trace_json(trace_config)
        assert data["status"] == "success"

        span_names = [s["name"] for s in data["spans"]]
        assert "run_agent" in span_names
        assert "llm.call" in span_names
        assert "tool.execute" in span_names
        assert len(data["spans"]) == 3

        # All should be children of the run span
        run_span = next(s for s in data["spans"] if s["name"] == "run_agent")
        for span in data["spans"]:
            if span["name"] != "run_agent":
                assert span["parent_id"] == run_span["span_id"]


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


async def asyncio_sleep_zero() -> None:
    """Minimal async yield point for testing."""
    import asyncio

    await asyncio.sleep(0)
