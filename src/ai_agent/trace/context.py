"""ContextVar-based propagation for trace runs and span nesting.

Uses Python's ``contextvars`` module so that trace state is automatically
isolated per-async-task, without any manual plumbing.  This is the
foundation that lets nested spans resolve their ``parent_id`` correctly
even when execution crosses ``await`` boundaries.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .recorder import TraceRecorder
    from .types import TraceRun

# ---------------------------------------------------------------------------
# Module-level ContextVars
# ---------------------------------------------------------------------------

_active_run: ContextVar[TraceRun | None] = ContextVar(
    "trace_active_run", default=None
)

_span_stack: ContextVar[list[str] | None] = ContextVar(
    "trace_span_stack", default=None
)

_active_recorder: ContextVar[TraceRecorder | None] = ContextVar(
    "trace_active_recorder", default=None
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def active_run() -> TraceRun | None:
    """Return the current active ``TraceRun``, or ``None`` if unset."""
    return _active_run.get()


def set_active_run(run: TraceRun) -> None:
    """Bind *run* as the active run in the current context.

    Args:
        run: The ``TraceRun`` to make active.
    """
    _active_run.set(run)


def clear_run() -> None:
    """Clear the active run in the current context (set to ``None``)."""
    _active_run.set(None)


def current_parent_id() -> str | None:
    """Return the span id at the top of the stack, or ``None`` if empty."""
    stack = _span_stack.get()
    if stack is None or not stack:
        return None
    return stack[-1]


def push_span(span_id: str) -> None:
    """Push *span_id* onto the current span stack.

    A **new** list is created (rather than mutating in place) to stay safe
    with ``ContextVar`` semantics -- each context update should produce a
    distinct object so that changes in a child task never leak back to the
    parent.

    Args:
        span_id: The identifier of the span being entered.
    """
    stack = _span_stack.get()
    _span_stack.set((stack or []) + [span_id])


def pop_span() -> None:
    """Remove the top span id from the stack.

    This is a **no-op** when the stack is already empty.
    """
    stack = _span_stack.get()
    if stack:
        _span_stack.set(stack[:-1])


def active_recorder() -> TraceRecorder | None:
    """Return the current active ``TraceRecorder``, or ``None`` if unset."""
    return _active_recorder.get()


def set_active_recorder(recorder: TraceRecorder | None) -> None:
    """Bind *recorder* as the active recorder in the current context.

    Args:
        recorder: The ``TraceRecorder`` to make active, or ``None`` to clear.
    """
    _active_recorder.set(recorder)
