"""TraceRecorder - core span tree builder and JSON file output.

Provides ``TraceRecorder`` which manages the lifecycle of a single trace run:
creating spans, tracking parent-child nesting via ``contextvars``, and
flushing the completed run to a timestamped JSON file.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .assertions import SpanAssertion

from .config import TraceConfig
from .context import (
    active_run,
    clear_run,
    current_parent_id,
    pop_span,
    push_span,
    set_active_recorder,
    set_active_run,
)
from .types import SpanData, TraceRun, generate_run_id


class TraceRecorder:
    """Records execution traces by building a span tree and writing JSON output.

    A ``TraceRecorder`` owns a single ``TraceRun``.  Spans are started with
    ``start_span`` and finished with ``finish_span``.  When the run is
    complete, call ``finish_run`` to serialize everything to disk.

    Args:
        name: Human-readable name for this trace run.
        config: Optional trace configuration.  Defaults to ``TraceConfig()``.
        tags: Optional list of string tags for categorization.
    """

    def __init__(
        self,
        name: str,
        *,
        config: TraceConfig | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self._config: TraceConfig = config if config is not None else TraceConfig()
        self._pending_spans: list[SpanData] = []

        now = datetime.now(timezone.utc)
        run_id = generate_run_id()
        self._run: TraceRun = TraceRun(
            run_id=run_id,
            name=name,
            started_at=now,
            finished_at=None,
            tags=tags if tags is not None else [],
        )

        # Activate in the current context
        set_active_run(self._run)
        set_active_recorder(self)

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the human-readable name of this trace run."""
        return self._run.name

    # ------------------------------------------------------------------
    # Assertion helpers (for use in tests)
    # ------------------------------------------------------------------

    def success(self) -> bool:
        """Return True if all spans succeeded.

        Returns:
            True when every recorded span has status ``"success"``
            (trivially True when there are no spans).
        """
        return self._run.is_success()

    def has_span(self, name: str) -> "SpanAssertion":
        """Return a ``SpanAssertion`` for the given span name.

        Args:
            name: The span name to assert against.

        Returns:
            A ``SpanAssertion`` instance that supports chainable assertions.
        """
        from .assertions import SpanAssertion

        return SpanAssertion(self._run, name)

    def span_count(self) -> int:
        """Return total number of completed spans.

        Returns:
            The count of spans recorded in this run.
        """
        return self._run.span_count()

    def duration_ms(self) -> float:
        """Return total run duration in milliseconds.

        Returns:
            The total duration in ms, or ``0.0`` if the run has not
            finished yet.
        """
        dur = self._run.total_duration_ms
        return dur if dur is not None else 0.0

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------

    def set_tag(self, tag: str) -> None:
        """Append a tag to the run's tag list.

        Args:
            tag: A string tag to add.
        """
        if tag not in self._run.tags:
            self._run.tags.append(tag)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata key-value pair on the run.

        Args:
            key: Metadata key.
            value: Metadata value (any JSON-serializable type).
        """
        if self._run.metadata is None:
            self._run.metadata = {}
        self._run.metadata[key] = value

    # ------------------------------------------------------------------
    # Span lifecycle
    # ------------------------------------------------------------------

    def start_span(self, name: str) -> str:
        """Begin a new trace span and return its span ID.

        The span is stored as pending until ``finish_span`` is called.
        The span's ``parent_id`` is resolved from the current context stack.

        Args:
            name: Human-readable span name (e.g. ``"llm.call"``).

        Returns:
            An 8-character hex span ID.
        """
        span_id = self._generate_span_id()
        parent_id = current_parent_id()

        span = SpanData(
            name=name,
            span_id=span_id,
            parent_id=parent_id,
            started_at=datetime.now(timezone.utc),
            finished_at=None,
            status="running",
        )
        self._pending_spans.append(span)

        # Push onto context stack and ensure this run is active
        push_span(span_id)
        set_active_run(self._run)

        return span_id

    def finish_span(
        self,
        *,
        input: Any = None,
        output: Any = None,
        error: str | None = None,
    ) -> None:
        """Complete the current pending span and record it.

        The span's status is set to ``"success"`` unless *error* is provided.

        Args:
            input: Optional input payload for the span.
            output: Optional output payload for the span.
            error: Error message; if set, status becomes ``"error"``.
        """
        if not self._pending_spans:
            return

        span = self._pending_spans.pop()
        span.finished_at = datetime.now(timezone.utc)
        span.status = "error" if error is not None else "success"

        # Normalize input/output to dicts if they are plain values
        span.input = input if isinstance(input, dict) or input is None else {"value": input}
        span.output = output if isinstance(output, dict) or output is None else {"value": output}
        span.error = error

        self._run.spans.append(span)

        pop_span()

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    def finish_run(self) -> str | None:
        """Finalize the run and flush it to a JSON file.

        Sets ``finished_at``, clears the active run context, and writes
        the trace data to disk if tracing is enabled.

        Returns:
            The file path of the written JSON, or ``None`` if tracing
            is disabled.
        """
        self._run.finished_at = datetime.now(timezone.utc)
        set_active_recorder(None)
        clear_run()

        if not self._config.enabled:
            return None

        return self._flush_to_file()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_span_id() -> str:
        """Generate a random 8-character hex span ID."""
        return secrets.token_hex(4)  # 4 bytes = 8 hex chars

    def _flush_to_file(self) -> str:
        """Write the completed run to a JSON file and return the path.

        The file path is derived from the run_id::

            {trace_dir}/{date_str}/{time_id}_{name}.json

        Intermediate directories are created automatically.
        Non-JSON-serializable values are converted to ``str()`` to avoid
        write failures when decorated functions return complex objects
        (e.g. Pydantic models, ``StreamingResponse``).
        """
        run_id = self._run.run_id
        parts = run_id.split("_")
        date_str = parts[0]
        time_id = f"{parts[1]}_{parts[2]}"

        full_path = self._config.trace_file_path(date_str, time_id, self._run.name)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(
                self._run.to_dict(),
                f,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        return full_path
