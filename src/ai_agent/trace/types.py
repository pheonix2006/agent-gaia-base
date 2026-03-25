"""Trace data models for recording execution traces.

Provides SpanData (single trace node), TraceRun (complete run record),
and generate_run_id() utility for producing unique run identifiers.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SpanData:
    """A single trace span representing one unit of recorded work.

    Attributes:
        name: Human-readable span name (e.g. "llm.call", "tool.run").
        span_id: Unique identifier for this span.
        parent_id: ID of the parent span, or None for root spans.
        started_at: When the span started (UTC).
        finished_at: When the span finished (UTC), or None if still running.
        status: Status of the span ("success", "error", "running", etc.).
        input: Optional input payload for the span.
        output: Optional output payload for the span.
        error: Error message if status is "error", otherwise None.
        metadata: Optional arbitrary metadata dict.
    """

    name: str
    span_id: str
    parent_id: str | None
    started_at: datetime
    finished_at: datetime | None
    status: str
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None

    @property
    def duration_ms(self) -> float | None:
        """Elapsed time in milliseconds, or None if not yet finished."""
        if self.finished_at is None:
            return None
        delta = self.finished_at - self.started_at
        return delta.total_seconds() * 1000.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSON output.

        Includes the computed ``duration_ms`` field.

        Uses manual dict construction instead of ``asdict()`` to avoid
        deep-copying values that may contain non-pickleable objects
        (e.g. ``StreamingResponse`` with async generators).
        """
        d: dict[str, Any] = {
            "name": self.name,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at is not None else None,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "duration_ms": self.duration_ms,
        }
        return d


@dataclass
class TraceRun:
    """A complete trace run containing one or more spans.

    Attributes:
        run_id: Unique identifier for this run (from generate_run_id()).
        name: Human-readable name for the run.
        started_at: When the run started (UTC).
        finished_at: When the run finished (UTC), or None if still running.
        spans: Ordered list of recorded spans.
        tags: Optional list of string tags for categorization.
        metadata: Optional arbitrary metadata dict.
    """

    run_id: str
    name: str
    started_at: datetime
    finished_at: datetime | None
    spans: list[SpanData] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] | None = None

    @property
    def total_duration_ms(self) -> float | None:
        """Total elapsed time in milliseconds, or None if not yet finished."""
        if self.finished_at is None:
            return None
        delta = self.finished_at - self.started_at
        return delta.total_seconds() * 1000.0

    def span_count(self) -> int:
        """Return the number of recorded spans."""
        return len(self.spans)

    def is_success(self) -> bool:
        """Return True if all spans have status 'success'.

        Returns True trivially when there are no spans.
        """
        return all(span.status == "success" for span in self.spans)

    def find_span(self, name: str) -> SpanData | None:
        """Find the first span matching the given name.

        Args:
            name: The span name to search for.

        Returns:
            The first matching SpanData, or None if not found.
        """
        for span in self.spans:
            if span.name == name:
                return span
        return None

    def find_spans(self, name: str) -> list[SpanData]:
        """Find all spans matching the given name.

        Args:
            name: The span name to search for.

        Returns:
            A list of all matching SpanData instances (may be empty).
        """
        return [span for span in self.spans if span.name == name]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSON file output.

        Includes computed fields ``status`` and ``total_duration_ms``.
        Each span in ``spans`` also includes its computed ``duration_ms``.
        """
        return {
            "run_id": self.run_id,
            "name": self.name,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at is not None else None,
            "status": "success" if self.is_success() else "error",
            "total_duration_ms": self.total_duration_ms,
            "spans": [span.to_dict() for span in self.spans],
            "tags": self.tags,
            "metadata": self.metadata,
        }


def generate_run_id() -> str:
    """Generate a unique run identifier in the format ``YYYYMMDD_HHMMSS_xxxx``.

    The timestamp uses UTC. The suffix is a 4-character random hex string.

    Returns:
        A unique run ID string.
    """
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2)  # 2 bytes = 4 hex chars
    return f"{ts}_{suffix}"
