"""Tests for trace data models: SpanData, TraceRun, generate_run_id."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import pytest

from ai_agent.trace.types import SpanData, TraceRun, generate_run_id


# ---------------------------------------------------------------------------
# SpanData
# ---------------------------------------------------------------------------


class TestSpanData:
    """Tests for the SpanData dataclass."""

    def _make_timestamps(self) -> tuple[datetime, datetime]:
        """Return two timestamps 0.5s apart for consistent test data."""
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 0, 500_000, tzinfo=timezone.utc)
        return started, finished

    def test_creation_basic(self) -> None:
        """SpanData can be created with required fields."""
        started, finished = self._make_timestamps()
        span = SpanData(
            name="llm.call",
            span_id="s1",
            parent_id=None,
            started_at=started,
            finished_at=finished,
            status="success",
            input=None,
            output=None,
            error=None,
            metadata=None,
        )
        assert span.name == "llm.call"
        assert span.span_id == "s1"
        assert span.parent_id is None
        assert span.status == "success"

    def test_creation_with_input_output(self) -> None:
        """SpanData stores input and output payloads."""
        started, finished = self._make_timestamps()
        span = SpanData(
            name="tool.run",
            span_id="s2",
            parent_id="s1",
            started_at=started,
            finished_at=finished,
            status="success",
            input={"query": "hello"},
            output={"result": "world"},
            error=None,
            metadata=None,
        )
        assert span.input == {"query": "hello"}
        assert span.output == {"result": "world"}
        assert span.parent_id == "s1"

    def test_creation_error_state(self) -> None:
        """SpanData correctly stores error information."""
        started, finished = self._make_timestamps()
        span = SpanData(
            name="tool.run",
            span_id="s3",
            parent_id=None,
            started_at=started,
            finished_at=finished,
            status="error",
            input=None,
            output=None,
            error="Timeout after 30s",
            metadata={"retry": 3},
        )
        assert span.status == "error"
        assert span.error == "Timeout after 30s"
        assert span.metadata == {"retry": 3}

    def test_duration_ms_property(self) -> None:
        """duration_ms returns the elapsed milliseconds between started_at and finished_at."""
        started, finished = self._make_timestamps()
        span = SpanData(
            name="span",
            span_id="s1",
            parent_id=None,
            started_at=started,
            finished_at=finished,
            status="success",
            input=None,
            output=None,
            error=None,
            metadata=None,
        )
        assert span.duration_ms == pytest.approx(500.0)

    def test_duration_ms_none_when_incomplete(self) -> None:
        """duration_ms returns None when finished_at is None (incomplete span)."""
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        span = SpanData(
            name="span",
            span_id="s1",
            parent_id=None,
            started_at=started,
            finished_at=None,
            status="running",
            input=None,
            output=None,
            error=None,
            metadata=None,
        )
        assert span.duration_ms is None

    def test_to_dict_includes_duration_ms(self) -> None:
        """to_dict() includes the computed duration_ms field."""
        started, finished = self._make_timestamps()
        span = SpanData(
            name="llm.call",
            span_id="s1",
            parent_id=None,
            started_at=started,
            finished_at=finished,
            status="success",
            input={"model": "gpt-4"},
            output={"content": "hi"},
            error=None,
            metadata={"tokens": 100},
        )
        d = span.to_dict()
        assert d["name"] == "llm.call"
        assert d["span_id"] == "s1"
        assert d["parent_id"] is None
        assert d["status"] == "success"
        assert d["input"] == {"model": "gpt-4"}
        assert d["output"] == {"content": "hi"}
        assert d["error"] is None
        assert d["metadata"] == {"tokens": 100}
        assert d["duration_ms"] == pytest.approx(500.0)

    def test_to_dict_incomplete_span_duration_ms_none(self) -> None:
        """to_dict() sets duration_ms to None for incomplete spans."""
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        span = SpanData(
            name="span",
            span_id="s1",
            parent_id=None,
            started_at=started,
            finished_at=None,
            status="running",
            input=None,
            output=None,
            error=None,
            metadata=None,
        )
        d = span.to_dict()
        assert d["duration_ms"] is None

    def test_special_characters_in_fields(self) -> None:
        """SpanData handles special characters in string fields gracefully."""
        started, finished = self._make_timestamps()
        span = SpanData(
            name='tool.run "search"',
            span_id="s1",
            parent_id=None,
            started_at=started,
            finished_at=finished,
            status="success",
            input={"query": 'Hello "World" & <friends>'},
            output={"result": "line1\nline2\ttab"},
            error=None,
            metadata=None,
        )
        d = span.to_dict()
        assert d["name"] == 'tool.run "search"'
        assert d["input"]["query"] == 'Hello "World" & <friends>'
        assert d["output"]["result"] == "line1\nline2\ttab"

    def test_none_values_in_optional_fields(self) -> None:
        """SpanData handles None values in all optional fields."""
        started, finished = self._make_timestamps()
        span = SpanData(
            name="span",
            span_id="s1",
            parent_id=None,
            started_at=started,
            finished_at=finished,
            status="success",
            input=None,
            output=None,
            error=None,
            metadata=None,
        )
        d = span.to_dict()
        assert d["input"] is None
        assert d["output"] is None
        assert d["error"] is None
        assert d["metadata"] is None


# ---------------------------------------------------------------------------
# TraceRun
# ---------------------------------------------------------------------------


class TestTraceRun:
    """Tests for the TraceRun dataclass."""

    def _make_base_spans(self) -> list[SpanData]:
        """Create a fixed list of test spans."""
        t0 = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 3, 24, 10, 0, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 3, 24, 10, 0, 2, 500_000, tzinfo=timezone.utc)
        return [
            SpanData(
                name="agent.run",
                span_id="r1",
                parent_id=None,
                started_at=t0,
                finished_at=t2,
                status="success",
                input={"query": "test"},
                output={"answer": "42"},
                error=None,
                metadata=None,
            ),
            SpanData(
                name="llm.call",
                span_id="s1",
                parent_id="r1",
                started_at=t0,
                finished_at=t1,
                status="success",
                input=None,
                output={"content": "hello"},
                error=None,
                metadata={"tokens": 50},
            ),
        ]

    def test_creation_basic(self) -> None:
        """TraceRun can be created with required fields."""
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="20260324_100000_abcd",
            name="test_run",
            started_at=started,
            finished_at=finished,
            spans=[],
            tags=["unit"],
            metadata=None,
        )
        assert run.run_id == "20260324_100000_abcd"
        assert run.name == "test_run"
        assert run.spans == []
        assert run.tags == ["unit"]

    def test_creation_with_spans(self) -> None:
        """TraceRun stores spans correctly."""
        spans = self._make_base_spans()
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=spans,
            tags=[],
            metadata=None,
        )
        assert len(run.spans) == 2
        assert run.spans[0].name == "agent.run"
        assert run.spans[1].name == "llm.call"

    def test_total_duration_ms(self) -> None:
        """total_duration_ms returns the elapsed ms of the overall run."""
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 3, 200_000, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=[],
            tags=[],
            metadata=None,
        )
        assert run.total_duration_ms == pytest.approx(3200.0)

    def test_total_duration_ms_none_when_incomplete(self) -> None:
        """total_duration_ms returns None when finished_at is None."""
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=None,
            spans=[],
            tags=[],
            metadata=None,
        )
        assert run.total_duration_ms is None

    def test_span_count(self) -> None:
        """span_count() returns the number of spans."""
        spans = self._make_base_spans()
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=spans,
            tags=[],
            metadata=None,
        )
        assert run.span_count() == 2

    def test_span_count_empty(self) -> None:
        """span_count() returns 0 for no spans."""
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=None,
            spans=[],
            tags=[],
            metadata=None,
        )
        assert run.span_count() == 0

    def test_is_success_all_success(self) -> None:
        """is_success() returns True when all spans have status 'success'."""
        spans = self._make_base_spans()
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=spans,
            tags=[],
            metadata=None,
        )
        assert run.is_success() is True

    def test_is_success_with_error_span(self) -> None:
        """is_success() returns False when any span has status 'error'."""
        t0 = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 3, 24, 10, 0, 1, tzinfo=timezone.utc)
        spans = [
            SpanData(
                name="agent.run",
                span_id="r1",
                parent_id=None,
                started_at=t0,
                finished_at=t1,
                status="success",
                input=None,
                output=None,
                error=None,
                metadata=None,
            ),
            SpanData(
                name="tool.run",
                span_id="s1",
                parent_id="r1",
                started_at=t0,
                finished_at=t1,
                status="error",
                input=None,
                output=None,
                error="boom",
                metadata=None,
            ),
        ]
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=spans,
            tags=[],
            metadata=None,
        )
        assert run.is_success() is False

    def test_is_success_empty_spans(self) -> None:
        """is_success() returns True when there are no spans (trivially successful)."""
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=[],
            tags=[],
            metadata=None,
        )
        assert run.is_success() is True

    def test_find_span_found(self) -> None:
        """find_span() returns the first span matching the given name."""
        spans = self._make_base_spans()
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=spans,
            tags=[],
            metadata=None,
        )
        result = run.find_span("llm.call")
        assert result is not None
        assert result.span_id == "s1"

    def test_find_span_not_found(self) -> None:
        """find_span() returns None when no span matches the given name."""
        spans = self._make_base_spans()
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=spans,
            tags=[],
            metadata=None,
        )
        assert run.find_span("nonexistent") is None

    def test_find_spans_multiple(self) -> None:
        """find_spans() returns all spans matching the given name."""
        t0 = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 3, 24, 10, 0, 1, tzinfo=timezone.utc)
        spans = [
            SpanData(
                name="llm.call",
                span_id="s1",
                parent_id="r1",
                started_at=t0,
                finished_at=t1,
                status="success",
                input=None,
                output=None,
                error=None,
                metadata=None,
            ),
            SpanData(
                name="tool.run",
                span_id="s2",
                parent_id="r1",
                started_at=t0,
                finished_at=t1,
                status="success",
                input=None,
                output=None,
                error=None,
                metadata=None,
            ),
            SpanData(
                name="llm.call",
                span_id="s3",
                parent_id="r1",
                started_at=t0,
                finished_at=t1,
                status="success",
                input=None,
                output=None,
                error=None,
                metadata=None,
            ),
        ]
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=spans,
            tags=[],
            metadata=None,
        )
        results = run.find_spans("llm.call")
        assert len(results) == 2
        assert results[0].span_id == "s1"
        assert results[1].span_id == "s3"

    def test_find_spans_empty(self) -> None:
        """find_spans() returns an empty list when no spans match."""
        spans = self._make_base_spans()
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=spans,
            tags=[],
            metadata=None,
        )
        assert run.find_spans("nonexistent") == []

    def test_to_dict_basic(self) -> None:
        """to_dict() produces a dict with all fields and computed status."""
        spans = self._make_base_spans()
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test_run",
            started_at=started,
            finished_at=finished,
            spans=spans,
            tags=["unit"],
            metadata={"version": "1.0"},
        )
        d = run.to_dict()
        assert d["run_id"] == "run1"
        assert d["name"] == "test_run"
        assert d["tags"] == ["unit"]
        assert d["metadata"] == {"version": "1.0"}
        # Computed fields
        assert d["status"] == "success"
        assert d["total_duration_ms"] == pytest.approx(5000.0)
        assert len(d["spans"]) == 2
        # Spans should have duration_ms included
        assert d["spans"][0]["duration_ms"] == pytest.approx(2500.0)
        assert d["spans"][1]["duration_ms"] == pytest.approx(1000.0)

    def test_to_dict_error_status(self) -> None:
        """to_dict() computes status as 'error' when any span has error."""
        t0 = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 3, 24, 10, 0, 1, tzinfo=timezone.utc)
        spans = [
            SpanData(
                name="agent.run",
                span_id="r1",
                parent_id=None,
                started_at=t0,
                finished_at=t1,
                status="error",
                input=None,
                output=None,
                error="fail",
                metadata=None,
            ),
        ]
        started = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 3, 24, 10, 0, 5, tzinfo=timezone.utc)
        run = TraceRun(
            run_id="run1",
            name="test",
            started_at=started,
            finished_at=finished,
            spans=spans,
            tags=[],
            metadata=None,
        )
        d = run.to_dict()
        assert d["status"] == "error"


# ---------------------------------------------------------------------------
# generate_run_id
# ---------------------------------------------------------------------------


class TestGenerateRunId:
    """Tests for the generate_run_id() function."""

    def test_format(self) -> None:
        """generate_run_id() returns a string matching YYYYMMDD_HHMMSS_xxxx."""
        run_id = generate_run_id()
        pattern = r"^\d{8}_\d{6}_[a-z0-9]{4}$"
        assert re.match(pattern, run_id), f"run_id '{run_id}' does not match pattern {pattern}"

    def test_uniqueness(self) -> None:
        """Calling generate_run_id() multiple times produces different IDs."""
        ids = {generate_run_id() for _ in range(100)}
        # With 4 random hex chars (16^4 = 65536 possibilities), 100 calls
        # should all be unique. Allow for the extremely unlikely collision.
        assert len(ids) > 95, f"Expected near-100 unique IDs, got {len(ids)}"

    def test_timestamp_is_current(self) -> None:
        """The timestamp portion of the ID is close to the current time."""
        before = datetime.now(timezone.utc).replace(microsecond=0)
        run_id = generate_run_id()
        after = datetime.now(timezone.utc).replace(microsecond=0)

        # Parse the timestamp part: "20260324_100000"
        ts_str = run_id.rsplit("_", 1)[0]
        ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)

        # The generated timestamp should be between before and after (second precision)
        assert before <= ts <= after, (
            f"Timestamp {ts} is not between {before} and {after}"
        )
