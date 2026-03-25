"""Configuration for the local trace system.

Provides ``TraceConfig`` for controlling trace output behavior and
``default_trace_dir()`` for the standard log directory path.
"""

from __future__ import annotations

import os


def default_trace_dir() -> str:
    """Return the default directory for trace log files.

    Returns:
        ``os.path.join("logs", "traces")``
    """
    return os.path.join("logs", "traces")


class TraceConfig:
    """Configuration for local trace file output.

    Attributes:
        enabled: Whether tracing is active.
        trace_dir: Root directory under which trace JSON files are stored.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        trace_dir: str | None = None,
    ) -> None:
        """Initialize trace configuration.

        Args:
            enabled: Whether tracing is active. Defaults to ``True``.
            trace_dir: Root directory for trace files. Defaults to
                ``default_trace_dir()`` if not provided.
        """
        self.enabled: bool = enabled
        self.trace_dir: str = trace_dir if trace_dir is not None else default_trace_dir()

    def trace_file_path(
        self,
        date_str: str,
        time_id: str,
        name: str,
    ) -> str:
        """Build the full file path for a trace JSON file.

        The resulting path has the format::

            {trace_dir}/{date_str}/{time_id}_{name}.json

        Args:
            date_str: Date string for the subdirectory (e.g. ``"2026-03-24"``).
            time_id: Time-based identifier prefix (e.g. ``"103000_a1b2"``).
            name: Human-readable run name suffix.

        Returns:
            The full path as a string.
        """
        filename = f"{time_id}_{name}.json"
        return os.path.join(self.trace_dir, date_str, filename)
