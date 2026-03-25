"""Tests for trace assertion API (SpanAssertion and TraceRecorder helpers)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai_agent.trace.assertions import SpanAssertion
from ai_agent.trace.context import (
    _active_recorder,
    _span_stack,
    active_run,
    clear_run,
)
from ai_agent.trace.recorder import TraceRecorder
from ai_agent.trace.types import SpanData, TraceRun


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(spans: list[SpanData]) -> TraceRun:
    """Build a TraceRun with the given spans for testing."""
    return TraceRun(
        run_id="20260324_000000_0000",
        name="test",
        started_at=datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 3, 24, 0, 0, 1, tzinfo=timezone.utc),
        spans=spans,
    )


def _make_span(
    name: str,
    *,
    status: str = "success",
    input: dict | None = None,
    output: dict | None = None,
    error: str | None = None,
) -> SpanData:
    """Build a SpanData with the given fields."""
    return SpanData(
        name=name,
        span_id="ab" * 4,
        parent_id=None,
        started_at=datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 3, 24, 0, 0, 0, 100000, tzinfo=timezone.utc),
        status=status,
        input=input,
        output=output,
        error=error,
    )


# ---------------------------------------------------------------------------
# SpanAssertion tests
# ---------------------------------------------------------------------------


class TestSpanAssertion:
    """Tests for SpanAssertion chainable assertions."""

    def test_with_input_match(self) -> None:
        """with_input passes when a span has all expected key-value pairs."""
        span = _make_span("llm.call", input={"model": "gpt-4", "temperature": 0.7})
        run = _make_run([span])

        assertion = SpanAssertion(run, "llm.call")
        # Should not raise
        assertion.with_input(model="gpt-4")

    def test_with_input_partial_match(self) -> None:
        """with_input passes when checking a subset of input keys."""
        span = _make_span(
            "llm.call", input={"model": "gpt-4", "temperature": 0.7}
        )
        run = _make_run([span])

        assertion = SpanAssertion(run, "llm.call")
        assertion.with_input(model="gpt-4")

    def test_with_input_mismatch_raises(self) -> None:
        """with_input raises AssertionError when no span has matching input."""
        span = _make_span("llm.call", input={"model": "gpt-4"})
        run = _make_run([span])

        assertion = SpanAssertion(run, "llm.call")
        with pytest.raises(AssertionError, match="No span 'llm.call' has input"):
            assertion.with_input(model="claude-3")

    def test_with_input_none_input_raises(self) -> None:
        """with_input raises when the matching span has None input."""
        span = _make_span("llm.call", input=None)
        run = _make_run([span])

        assertion = SpanAssertion(run, "llm.call")
        with pytest.raises(AssertionError, match="No span 'llm.call' has input"):
            assertion.with_input(model="gpt-4")

    def test_with_output_match(self) -> None:
        """with_output passes when a span has all expected key-value pairs."""
        span = _make_span("tool.run", output={"result": "ok", "count": 3})
        run = _make_run([span])

        assertion = SpanAssertion(run, "tool.run")
        assertion.with_output(result="ok")

    def test_with_output_mismatch_raises(self) -> None:
        """with_output raises AssertionError when no span has matching output."""
        span = _make_span("tool.run", output={"result": "ok"})
        run = _make_run([span])

        assertion = SpanAssertion(run, "tool.run")
        with pytest.raises(AssertionError, match="No span 'tool.run' has output"):
            assertion.with_output(result="fail")

    def test_with_output_none_output_raises(self) -> None:
        """with_output raises when the matching span has None output."""
        span = _make_span("tool.run", output=None)
        run = _make_run([span])

        assertion = SpanAssertion(run, "tool.run")
        with pytest.raises(AssertionError, match="No span 'tool.run' has output"):
            assertion.with_output(result="ok")

    def test_nested_field_match(self) -> None:
        """with_input/with_output should match nested dict values exactly."""
        nested = {"inner": {"key": "value"}}
        span = _make_span("agent.think", input=nested)
        run = _make_run([span])

        assertion = SpanAssertion(run, "agent.think")
        assertion.with_input(inner={"key": "value"})

    def test_no_matching_span_raises(self) -> None:
        """exists() raises when the span name is not found in the run."""
        span = _make_span("other.span")
        run = _make_run([span])

        assertion = SpanAssertion(run, "missing.span")
        with pytest.raises(
            AssertionError, match="No span named 'missing.span' found"
        ):
            assertion.exists()

    def test_exists_passes_when_span_found(self) -> None:
        """exists() does not raise when the span exists."""
        span = _make_span("llm.call")
        run = _make_run([span])

        assertion = SpanAssertion(run, "llm.call")
        result = assertion.exists()
        assert result is assertion  # returns self for chaining

    def test_has_error_match(self) -> None:
        """has_error passes when a span has error status."""
        span = _make_span("tool.run", status="error", error="timeout")
        run = _make_run([span])

        assertion = SpanAssertion(run, "tool.run")
        assertion.has_error()

    def test_has_error_with_substring_match(self) -> None:
        """has_error passes when error message contains expected substring."""
        span = _make_span(
            "tool.run", status="error", error="connection timeout after 30s"
        )
        run = _make_run([span])

        assertion = SpanAssertion(run, "tool.run")
        assertion.has_error("timeout")

    def test_has_error_substring_mismatch_raises(self) -> None:
        """has_error raises when error message does not contain substring."""
        span = _make_span("tool.run", status="error", error="timeout")
        run = _make_run([span])

        assertion = SpanAssertion(run, "tool.run")
        with pytest.raises(AssertionError, match="does not contain 'auth'"):
            assertion.has_error("auth")

    def test_has_error_no_error_span_raises(self) -> None:
        """has_error raises when all matching spans have non-error status."""
        span = _make_span("tool.run", status="success")
        run = _make_run([span])

        assertion = SpanAssertion(run, "tool.run")
        with pytest.raises(AssertionError, match="No span 'tool.run' has error"):
            assertion.has_error()

    def test_multiple_spans_match_at_least_one(self) -> None:
        """When multiple spans share a name, assertions pass if at least one matches."""
        span1 = _make_span("llm.call", input={"model": "gpt-3"})
        span2 = _make_span(
            "llm.call",
            input={"model": "gpt-4", "temperature": 0.7},
        )
        span2.span_id = "cd" * 4  # unique ID
        run = _make_run([span1, span2])

        assertion = SpanAssertion(run, "llm.call")
        # Should match span2
        assertion.with_input(model="gpt-4", temperature=0.7)

    def test_multiple_spans_error_matches_any(self) -> None:
        """When multiple spans share a name, has_error matches if any has error."""
        span1 = _make_span("tool.run", status="success")
        span2 = _make_span(
            "tool.run", status="error", error="rate limited"
        )
        span2.span_id = "cd" * 4
        run = _make_run([span1, span2])

        assertion = SpanAssertion(run, "tool.run")
        assertion.has_error("rate limited")

    def test_chaining(self) -> None:
        """Assertion methods should be chainable."""
        span = _make_span(
            "llm.call",
            input={"model": "gpt-4"},
            output={"tokens": 100},
        )
        run = _make_run([span])

        result = (
            SpanAssertion(run, "llm.call")
            .exists()
            .with_input(model="gpt-4")
            .with_output(tokens=100)
        )
        assert isinstance(result, SpanAssertion)

    def test_dict_contains_non_dict_actual(self) -> None:
        """_dict_contains returns False when actual is not a dict."""
        assert SpanAssertion._dict_contains("not a dict", {"key": "val"}) is False

    def test_dict_contains_missing_key(self) -> None:
        """_dict_contains returns False when a key is missing."""
        assert SpanAssertion._dict_contains({"a": 1}, {"b": 2}) is False

    def test_dict_contains_value_mismatch(self) -> None:
        """_dict_contains returns False when a value differs."""
        assert SpanAssertion._dict_contains({"a": 1}, {"a": 2}) is False

    def test_dict_contains_exact_match(self) -> None:
        """_dict_contains returns True when all expected pairs are present."""
        assert SpanAssertion._dict_contains({"a": 1, "b": 2}, {"a": 1}) is True


# ---------------------------------------------------------------------------
# TraceRecorder assertion helpers tests
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


class TestTraceRecorderAssertions:
    """Tests for TraceRecorder assertion helper methods."""

    def test_success_returns_true_when_all_spans_ok(self) -> None:
        """success() returns True when all spans have status 'success'."""
        rec = TraceRecorder("test")
        try:
            rec.start_span("op1")
            rec.finish_span()
            rec.start_span("op2")
            rec.finish_span()
            assert rec.success() is True
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)

    def test_success_returns_false_when_error_span(self) -> None:
        """success() returns False when any span has status 'error'."""
        rec = TraceRecorder("test")
        try:
            rec.start_span("op_ok")
            rec.finish_span()
            rec.start_span("op_err")
            rec.finish_span(error="boom")
            assert rec.success() is False
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)

    def test_success_returns_true_with_no_spans(self) -> None:
        """success() returns True trivially when there are no spans."""
        rec = TraceRecorder("test")
        try:
            assert rec.success() is True
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)

    def test_has_span_returns_assertion(self) -> None:
        """has_span() returns a SpanAssertion instance."""
        rec = TraceRecorder("test")
        try:
            rec.start_span("op")
            rec.finish_span()
            assertion = rec.has_span("op")
            assert isinstance(assertion, SpanAssertion)
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)

    def test_has_span_not_found_raises_on_exists(self) -> None:
        """has_span() for a missing name only raises when exists() is called."""
        rec = TraceRecorder("test")
        try:
            rec.start_span("existing")
            rec.finish_span()
            # Getting the assertion itself should not raise
            assertion = rec.has_span("missing")
            # But calling exists() should raise
            with pytest.raises(AssertionError, match="No span named 'missing'"):
                assertion.exists()
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)

    def test_span_count(self) -> None:
        """span_count() returns the number of completed spans."""
        rec = TraceRecorder("test")
        try:
            assert rec.span_count() == 0
            rec.start_span("a")
            rec.finish_span()
            assert rec.span_count() == 1
            rec.start_span("b")
            rec.finish_span()
            assert rec.span_count() == 2
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)

    def test_duration_ms_before_finish(self) -> None:
        """duration_ms() returns 0.0 before finish_run."""
        rec = TraceRecorder("test")
        try:
            rec.start_span("op")
            rec.finish_span()
            assert rec.duration_ms() == 0.0
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)

    def test_duration_ms_after_finish(self) -> None:
        """duration_ms() returns a non-negative float after finish_run."""
        rec = TraceRecorder("test")
        try:
            import time

            time.sleep(0.01)  # ensure measurable duration
            rec.start_span("op")
            rec.finish_span()
            rec.finish_run()
            # Duration should be >= 0.0 and include the sleep
            assert rec.duration_ms() >= 0.0
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)
