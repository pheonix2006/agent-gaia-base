"""Tests for trace configuration module."""

from __future__ import annotations

import os

import pytest

from ai_agent.trace.config import TraceConfig, default_trace_dir


# ---------------------------------------------------------------------------
# TestTraceConfig
# ---------------------------------------------------------------------------


class TestTraceConfig:
    """Tests for TraceConfig initialization and attributes."""

    def test_default_enabled_true(self) -> None:
        """By default, trace is enabled."""
        config = TraceConfig()
        assert config.enabled is True

    def test_default_trace_dir(self) -> None:
        """Default trace_dir ends with 'logs/traces'."""
        config = TraceConfig()
        assert config.trace_dir.endswith(os.path.join("logs", "traces"))

    def test_default_trace_dir_matches_default_trace_dir_func(self) -> None:
        """Default trace_dir equals the return value of default_trace_dir()."""
        config = TraceConfig()
        assert config.trace_dir == default_trace_dir()

    def test_custom_trace_dir(self) -> None:
        """Custom trace_dir is stored as-is."""
        config = TraceConfig(trace_dir="/tmp/my_traces")
        assert config.trace_dir == "/tmp/my_traces"

    def test_disabled(self) -> None:
        """enabled=False is honored."""
        config = TraceConfig(enabled=False)
        assert config.enabled is False

    def test_disabled_with_custom_dir(self) -> None:
        """disabled config can still have a custom trace_dir."""
        config = TraceConfig(enabled=False, trace_dir="/custom/path")
        assert config.enabled is False
        assert config.trace_dir == "/custom/path"


# ---------------------------------------------------------------------------
# TestTraceFilePath
# ---------------------------------------------------------------------------


class TestTraceFilePath:
    """Tests for TraceConfig.trace_file_path() method."""

    def test_generates_expected_path(self) -> None:
        """trace_file_path returns {trace_dir}/{date_str}/{time_id}_{name}.json."""
        config = TraceConfig(trace_dir="/traces")
        path = config.trace_file_path(
            date_str="2026-03-24",
            time_id="103000_a1b2",
            name="agent_run",
        )
        expected = os.path.join("/traces", "2026-03-24", "103000_a1b2_agent_run.json")
        assert path == expected

    def test_default_trace_dir(self) -> None:
        """trace_file_path works with default trace_dir."""
        config = TraceConfig()
        path = config.trace_file_path(
            date_str="2026-03-24",
            time_id="103000_a1b2",
            name="test",
        )
        expected_suffix = os.path.join("2026-03-24", "103000_a1b2_test.json")
        assert path.endswith(expected_suffix)
        assert path.startswith(config.trace_dir)

    def test_name_with_special_characters(self) -> None:
        """trace_file_path handles name with dots and underscores."""
        config = TraceConfig(trace_dir="/t")
        path = config.trace_file_path(
            date_str="2026-03-24",
            time_id="103000_a1b2",
            name="my.run_name",
        )
        expected = os.path.join("/t", "2026-03-24", "103000_a1b2_my.run_name.json")
        assert path == expected

    def test_empty_name(self) -> None:
        """trace_file_path works with an empty name."""
        config = TraceConfig(trace_dir="/t")
        path = config.trace_file_path(
            date_str="2026-03-24",
            time_id="103000_a1b2",
            name="",
        )
        expected = os.path.join("/t", "2026-03-24", "103000_a1b2_.json")
        assert path == expected

    def test_path_uses_os_path_join(self) -> None:
        """trace_file_path uses os.path.join internally."""
        config = TraceConfig(trace_dir=os.path.join("logs", "traces"))
        path = config.trace_file_path(
            date_str="2026-03-24",
            time_id="103000_a1b2",
            name="run",
        )
        expected = os.path.join("logs", "traces", "2026-03-24", "103000_a1b2_run.json")
        assert path == expected


# ---------------------------------------------------------------------------
# TestDefaultTraceDir
# ---------------------------------------------------------------------------


class TestDefaultTraceDir:
    """Tests for default_trace_dir() free function."""

    def test_returns_logs_traces(self) -> None:
        """default_trace_dir() returns 'logs/traces' via os.path.join."""
        assert default_trace_dir() == os.path.join("logs", "traces")
