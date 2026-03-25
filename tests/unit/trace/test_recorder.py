"""Tests for TraceRecorder - the core span tree builder and JSON file output."""

from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from ai_agent.trace.config import TraceConfig
from ai_agent.trace.context import (
    _active_recorder,
    _span_stack,
    active_run,
    clear_run,
    current_parent_id,
)
from ai_agent.trace.recorder import TraceRecorder
from ai_agent.trace.types import SpanData, TraceRun, generate_run_id


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


@pytest.fixture
def recorder(trace_config: TraceConfig) -> TraceRecorder:
    """Return a fresh TraceRecorder with temporary config."""
    # Ensure clean context state before each test
    clear_run()
    _span_stack.set(None)
    _active_recorder.set(None)
    rec = TraceRecorder("test_run", config=trace_config)
    yield rec
    # Clean up context after test to prevent leaks between tests
    clear_run()
    _span_stack.set(None)
    _active_recorder.set(None)


# ---------------------------------------------------------------------------
# Basic: create recorder
# ---------------------------------------------------------------------------


class TestRecorderCreation:
    """Tests for TraceRecorder initialization."""

    def test_creates_recorder_with_name(self, trace_config: TraceConfig) -> None:
        recorder = TraceRecorder("my_run", config=trace_config)
        assert recorder.name == "my_run"

    def test_creates_trace_run_on_init(self, recorder: TraceRecorder) -> None:
        assert active_run() is not None
        run = active_run()
        assert isinstance(run, TraceRun)
        assert run.name == "test_run"
        assert run.started_at is not None
        assert run.finished_at is None

    def test_init_with_default_config(self) -> None:
        """Recorder can be created with default config (no explicit config)."""
        try:
            rec = TraceRecorder("default_config_run")
            assert rec.name == "default_config_run"
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)

    def test_init_with_tags(self, trace_config: TraceConfig) -> None:
        clear_run()
        _span_stack.set(None)
        rec = TraceRecorder("tagged", config=trace_config, tags=["fast", "debug"])
        try:
            run = active_run()
            assert run is not None
            assert "fast" in run.tags
            assert "debug" in run.tags
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)

    def test_run_id_format(self, recorder: TraceRecorder) -> None:
        """Run ID should match YYYYMMDD_HHMMSS_xxxx pattern."""
        run = active_run()
        assert run is not None
        parts = run.run_id.split("_")
        assert len(parts) == 3
        # First part is date: YYYYMMDD (8 chars)
        assert len(parts[0]) == 8
        # Second part is time: HHMMSS (6 chars)
        assert len(parts[1]) == 6
        # Third part is 4-char hex
        assert len(parts[2]) == 4


# ---------------------------------------------------------------------------
# Basic: start_span / finish_span
# ---------------------------------------------------------------------------


class TestSpanLifecycle:
    """Tests for start_span and finish_span basic operations."""

    def test_start_span_returns_span_id(self, recorder: TraceRecorder) -> None:
        span_id = recorder.start_span("test.op")
        assert isinstance(span_id, str)
        assert len(span_id) == 8

    def test_start_span_pushes_to_context(self, recorder: TraceRecorder) -> None:
        span_id = recorder.start_span("test.op")
        assert current_parent_id() == span_id

    def test_start_span_sets_active_run(self, recorder: TraceRecorder) -> None:
        recorder.start_span("test.op")
        run = active_run()
        assert run is not None

    def test_finish_span_success(self, recorder: TraceRecorder) -> None:
        recorder.start_span("test.op")
        recorder.finish_span(output={"result": "ok"})

        run = active_run()
        assert run is not None
        assert run.span_count() == 1
        span = run.spans[0]
        assert span.name == "test.op"
        assert span.status == "success"
        assert span.output == {"result": "ok"}
        assert span.finished_at is not None

    def test_finish_span_error(self, recorder: TraceRecorder) -> None:
        recorder.start_span("test.op")
        recorder.finish_span(error="something went wrong")

        run = active_run()
        assert run is not None
        span = run.spans[0]
        assert span.status == "error"
        assert span.error == "something went wrong"

    def test_finish_span_with_input(self, recorder: TraceRecorder) -> None:
        recorder.start_span("test.op")
        recorder.finish_span(input={"query": "hello"})

        run = active_run()
        span = run.spans[0]
        assert span.input == {"query": "hello"}

    def test_finish_span_pops_context(self, recorder: TraceRecorder) -> None:
        recorder.start_span("outer")
        recorder.start_span("inner")
        assert current_parent_id() is not None
        recorder.finish_span()
        # After popping inner, parent should be outer
        assert current_parent_id() is not None
        recorder.finish_span()
        # After popping outer, no parent
        assert current_parent_id() is None

    def test_span_duration_computed(self, recorder: TraceRecorder) -> None:
        recorder.start_span("test.op")
        time.sleep(0.01)  # 10ms
        recorder.finish_span()

        run = active_run()
        span = run.spans[0]
        assert span.duration_ms is not None
        assert span.duration_ms >= 5.0  # at least ~10ms

    def test_finish_span_none_fields(self, recorder: TraceRecorder) -> None:
        """finish_span with no arguments should have None input/output/error."""
        recorder.start_span("test.op")
        recorder.finish_span()

        run = active_run()
        span = run.spans[0]
        assert span.input is None
        assert span.output is None
        assert span.error is None


# ---------------------------------------------------------------------------
# Nesting: parent_id resolution
# ---------------------------------------------------------------------------


class TestSpanNesting:
    """Tests for correctly nested span parent_id resolution."""

    def test_root_span_has_no_parent(self, recorder: TraceRecorder) -> None:
        recorder.start_span("root")
        recorder.finish_span()

        run = active_run()
        span = run.spans[0]
        assert span.parent_id is None

    def test_nested_span_has_parent_id(self, recorder: TraceRecorder) -> None:
        root_id = recorder.start_span("root")
        recorder.start_span("child")
        recorder.finish_span()
        recorder.finish_span()

        run = active_run()
        assert run.span_count() == 2
        # Spans are appended in finish order: child first, root second
        child_span = run.find_span("child")
        root_span = run.find_span("root")
        assert root_span is not None
        assert child_span is not None
        assert root_span.parent_id is None
        assert child_span.parent_id == root_id

    def test_deeply_nested_spans(self, recorder: TraceRecorder) -> None:
        id1 = recorder.start_span("level_1")
        id2 = recorder.start_span("level_2")
        id3 = recorder.start_span("level_3")
        id4 = recorder.start_span("level_4")

        recorder.finish_span()  # level_4 -> parent is level_3
        recorder.finish_span()  # level_3 -> parent is level_2
        recorder.finish_span()  # level_2 -> parent is level_1
        recorder.finish_span()  # level_1 -> root, no parent

        run = active_run()
        assert run.span_count() == 4

        # Spans are appended in finish order: level_4, level_3, level_2, level_1
        s4 = run.find_span("level_4")
        s3 = run.find_span("level_3")
        s2 = run.find_span("level_2")
        s1 = run.find_span("level_1")
        assert s1 is not None and s2 is not None and s3 is not None and s4 is not None

        assert s1.parent_id is None       # level_1 is root
        assert s2.parent_id == id1         # level_2 -> level_1
        assert s3.parent_id == id2         # level_3 -> level_2
        assert s4.parent_id == id3         # level_4 -> level_3

    def test_sibling_spans_share_parent(self, recorder: TraceRecorder) -> None:
        root_id = recorder.start_span("root")
        recorder.start_span("sibling_a")
        recorder.finish_span()
        recorder.start_span("sibling_b")
        recorder.finish_span()
        recorder.finish_span()

        run = active_run()
        assert run.span_count() == 3
        # Spans are appended in finish order: sibling_a, sibling_b, root
        root_span = run.find_span("root")
        sibling_a = run.find_span("sibling_a")
        sibling_b = run.find_span("sibling_b")
        assert root_span is not None and sibling_a is not None and sibling_b is not None
        assert sibling_a.parent_id == root_id
        assert sibling_b.parent_id == root_id


# ---------------------------------------------------------------------------
# Metadata: set_tag / set_metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    """Tests for set_tag and set_metadata."""

    def test_set_tag(self, recorder: TraceRecorder) -> None:
        recorder.set_tag("production")
        run = active_run()
        assert run is not None
        assert "production" in run.tags

    def test_set_multiple_tags(self, recorder: TraceRecorder) -> None:
        recorder.set_tag("tag1")
        recorder.set_tag("tag2")
        recorder.set_tag("tag3")
        run = active_run()
        assert "tag1" in run.tags
        assert "tag2" in run.tags
        assert "tag3" in run.tags

    def test_set_metadata(self, recorder: TraceRecorder) -> None:
        recorder.set_metadata("model", "gpt-4")
        run = active_run()
        assert run is not None
        assert run.metadata is not None
        assert run.metadata["model"] == "gpt-4"

    def test_set_metadata_overwrites(self, recorder: TraceRecorder) -> None:
        recorder.set_metadata("key", "value1")
        recorder.set_metadata("key", "value2")
        run = active_run()
        assert run.metadata is not None
        assert run.metadata["key"] == "value2"

    def test_set_metadata_multiple_keys(self, recorder: TraceRecorder) -> None:
        recorder.set_metadata("key1", 1)
        recorder.set_metadata("key2", "two")
        recorder.set_metadata("key3", {"nested": True})
        run = active_run()
        assert run.metadata is not None
        assert run.metadata["key1"] == 1
        assert run.metadata["key2"] == "two"
        assert run.metadata["key3"] == {"nested": True}

    def test_init_tags_combined_with_set_tag(self, trace_config: TraceConfig) -> None:
        clear_run()
        _span_stack.set(None)
        rec = TraceRecorder("combined", config=trace_config, tags=["init"])
        try:
            rec.set_tag("added")
            run = active_run()
            assert "init" in run.tags
            assert "added" in run.tags
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)


# ---------------------------------------------------------------------------
# File output: flush_to_file
# ---------------------------------------------------------------------------


class TestFileOutput:
    """Tests for JSON file output on finish_run."""

    def test_finish_run_creates_json_file(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        recorder.start_span("op1")
        recorder.finish_span(output={"result": "ok"})
        filepath = recorder.finish_run()

        assert filepath is not None
        assert os.path.isfile(filepath)
        # File is under tmp_trace_dir
        assert filepath.startswith(tmp_trace_dir)

    def test_flush_creates_date_subdirectory(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        recorder.start_span("op")
        recorder.finish_span()
        filepath = recorder.finish_run()

        assert filepath is not None
        # Parent directory should be a date string under tmp_trace_dir
        parent_dir = os.path.dirname(filepath)
        date_part = os.path.basename(parent_dir)
        # Date format should be parseable
        datetime.strptime(date_part, "%Y%m%d")

    def test_flush_auto_creates_nested_directories(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        """Verify that makedirs(exist_ok=True) creates intermediate dirs."""
        recorder.start_span("op")
        recorder.finish_span()
        filepath = recorder.finish_run()

        assert filepath is not None
        # The file exists, which proves directories were created
        assert os.path.isfile(filepath)

    def test_json_file_is_valid(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        recorder.start_span("op1")
        recorder.finish_span(output={"data": 42})
        filepath = recorder.finish_run()

        assert filepath is not None
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        # Top-level required fields
        assert "run_id" in data
        assert "name" in data
        assert "started_at" in data
        assert "finished_at" in data
        assert "status" in data
        assert "total_duration_ms" in data
        assert "spans" in data
        assert "tags" in data
        assert "metadata" in data

    def test_json_spans_have_required_fields(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        recorder.start_span("op1")
        recorder.finish_span()
        filepath = recorder.finish_run()

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["spans"]) == 1
        span = data["spans"][0]
        for field in (
            "name", "span_id", "parent_id", "started_at",
            "finished_at", "status", "duration_ms",
            "input", "output", "error", "metadata",
        ):
            assert field in span, f"Missing field '{field}' in span JSON"

    def test_json_ensure_ascii_false(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        """Non-ASCII characters should be preserved (not escaped)."""
        recorder.start_span("测试操作")
        recorder.finish_span(output={"消息": "你好世界"})
        filepath = recorder.finish_run()

        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Should contain the raw Unicode, not \uXXXX escapes
        assert "测试操作" in content
        assert "你好世界" in content

    def test_json_indent_2(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        """JSON should be pretty-printed with 2-space indent."""
        recorder.start_span("op")
        recorder.finish_span()
        filepath = recorder.finish_run()

        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Check that indentation uses 2 spaces
        lines = content.split("\n")
        # Find a line that should be indented (inside top-level object)
        indented_lines = [
            line for line in lines
            if line.startswith("  ") and not line.strip().startswith("//")
        ]
        assert len(indented_lines) > 0, "JSON should be indented"

    def test_filename_format(self, recorder: TraceRecorder, tmp_trace_dir: str) -> None:
        """Filename should be {time_id}_{name}.json."""
        recorder.start_span("op")
        recorder.finish_span()
        filepath = recorder.finish_run()

        assert filepath is not None
        filename = os.path.basename(filepath)
        assert filename.endswith("_test_run.json")
        # Should start with HHMMSS_xxxx
        prefix = filename.replace("_test_run.json", "")
        parts = prefix.split("_")
        assert len(parts) == 2
        assert len(parts[0]) == 6   # HHMMSS
        assert len(parts[1]) == 4   # hex suffix

    def test_flush_preserves_span_order(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        """Spans should appear in finish order, not start order."""
        recorder.start_span("first")
        recorder.start_span("second")
        recorder.start_span("third")
        recorder.finish_span()  # finishes "third"
        recorder.finish_span()  # finishes "second"
        recorder.finish_span()  # finishes "first"

        filepath = recorder.finish_run()

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        assert [s["name"] for s in data["spans"]] == ["third", "second", "first"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests."""

    def test_finish_run_without_spans(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        """finish_run should work even if no spans were recorded."""
        filepath = recorder.finish_run()
        assert filepath is not None
        assert os.path.isfile(filepath)

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        assert data["spans"] == []
        assert data["status"] == "success"  # no spans -> trivially success

    def test_multiple_recorders_isolated(
        self, trace_config: TraceConfig, tmp_trace_dir: str
    ) -> None:
        """Two recorders should not interfere with each other's runs."""
        rec1 = TraceRecorder("run_a", config=trace_config)
        rec1.start_span("op_a")
        rec1.finish_span()

        # rec2 takes over the context
        rec2 = TraceRecorder("run_b", config=trace_config)
        rec2.start_span("op_b")
        rec2.finish_span()
        filepath2 = rec2.finish_run()

        # rec1's run should still have its span
        assert rec1._run.span_count() == 1
        assert rec1._run.spans[0].name == "op_a"

        # rec2's file should only have op_b
        with open(filepath2, encoding="utf-8") as f:
            data2 = json.load(f)
        assert data2["name"] == "run_b"
        assert len(data2["spans"]) == 1
        assert data2["spans"][0]["name"] == "op_b"

    def test_disabled_config_skips_flush(self, tmp_trace_dir: str) -> None:
        """When config.enabled is False, finish_run should return None."""
        config = TraceConfig(enabled=False, trace_dir=tmp_trace_dir)
        rec = TraceRecorder("disabled", config=config)
        try:
            rec.start_span("op")
            rec.finish_span()
            filepath = rec.finish_run()
            assert filepath is None
        finally:
            clear_run()
            _span_stack.set(None)
            _active_recorder.set(None)
    def test_finish_run_sets_finished_at(self, recorder: TraceRecorder) -> None:
        recorder.start_span("op")
        recorder.finish_span()

        # Before finish_run
        run = active_run()
        assert run is not None
        assert run.finished_at is None

        recorder.finish_run()

        # After finish_run, the run object should have finished_at set
        assert recorder._run.finished_at is not None

    def test_finish_run_clears_context(self, recorder: TraceRecorder) -> None:
        recorder.start_span("op")
        recorder.finish_span()
        recorder.finish_run()

        # Context should be cleared
        assert active_run() is None

    def test_span_id_format(self, recorder: TraceRecorder) -> None:
        """Span IDs should be 8-character strings."""
        span_id = recorder.start_span("op")
        assert len(span_id) == 8
        # Should be hex characters
        assert all(c in "0123456789abcdef" for c in span_id)

    def test_span_ids_are_unique(self, recorder: TraceRecorder) -> None:
        """Multiple spans should have unique IDs."""
        ids = set()
        for i in range(20):
            sid = recorder.start_span(f"op_{i}")
            recorder.finish_span()
            ids.add(sid)
        assert len(ids) == 20


# ---------------------------------------------------------------------------
# JSON validation: comprehensive field checks
# ---------------------------------------------------------------------------


class TestJsonValidation:
    """Comprehensive validation of JSON output structure."""

    def test_full_run_json_structure(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        """End-to-end: record tags, metadata, spans, verify full JSON."""
        recorder.set_tag("integration")
        recorder.set_metadata("version", "1.0")
        recorder.set_metadata("env", "test")

        recorder.start_span("agent.think")
        recorder.finish_span(input={"query": "hello"}, output={"thought": "hi"})

        recorder.start_span("llm.call")
        recorder.finish_span(output={"tokens": 42})

        recorder.start_span("tool.execute")
        recorder.finish_span(error="timeout")

        filepath = recorder.finish_run()
        assert filepath is not None

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        # Run-level fields
        assert data["name"] == "test_run"
        assert data["status"] == "error"  # one span has error
        assert data["total_duration_ms"] is not None and data["total_duration_ms"] >= 0
        assert data["finished_at"] is not None
        assert "integration" in data["tags"]
        assert data["metadata"]["version"] == "1.0"
        assert data["metadata"]["env"] == "test"
        assert len(data["spans"]) == 3

        # First span (agent.think)
        span0 = data["spans"][0]
        assert span0["name"] == "agent.think"
        assert span0["status"] == "success"
        assert span0["input"] == {"query": "hello"}
        assert span0["output"] == {"thought": "hi"}
        assert span0["error"] is None
        assert span0["duration_ms"] is not None

        # Second span (llm.call)
        span1 = data["spans"][1]
        assert span1["name"] == "llm.call"
        assert span1["status"] == "success"
        assert span1["output"] == {"tokens": 42}

        # Third span (tool.execute)
        span2 = data["spans"][2]
        assert span2["name"] == "tool.execute"
        assert span2["status"] == "error"
        assert span2["error"] == "timeout"

    def test_run_id_in_json_matches(
        self, recorder: TraceRecorder, tmp_trace_dir: str
    ) -> None:
        """JSON run_id should match the TraceRun's run_id."""
        recorder.start_span("op")
        recorder.finish_span()
        filepath = recorder.finish_run()

        run_id = recorder._run.run_id

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        assert data["run_id"] == run_id
