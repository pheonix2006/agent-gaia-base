"""Decorators and context manager for recording trace spans.

Provides ``trace_run`` / ``trace_span`` decorators and the ``TraceSpanCtx``
context manager so that instrumented code can be traced with minimal
boilerplate.
"""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable

from .config import TraceConfig
from .context import active_recorder
from .recorder import TraceRecorder


# ---------------------------------------------------------------------------
# trace_run decorator
# ---------------------------------------------------------------------------


def trace_run(
    name: str | None = None,
    *,
    config: TraceConfig | None = None,
    tags: list[str] | None = None,
) -> Callable:
    """Create a ``TraceRecorder``, wrap function execution, and flush to JSON.

    Works on both sync and async functions.  The decorated function becomes
    the top-level span of a new trace run.

    Args:
        name: Human-readable name for the run.  Defaults to the function name.
        config: Optional ``TraceConfig``.  Defaults to ``TraceConfig()``.
        tags: Optional list of tags attached to the run.

    Returns:
        A decorator that wraps the target function.
    """

    def decorator(func: Callable) -> Callable:
        run_name = name if name is not None else func.__name__

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                recorder = TraceRecorder(run_name, config=config, tags=tags)
                span_id = recorder.start_span(func.__name__)
                try:
                    result = await func(*args, **kwargs)
                    recorder.finish_span(output=result)
                    return result
                except BaseException:
                    recorder.finish_span(error=_format_exc())
                    raise
                finally:
                    recorder.finish_run()

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                recorder = TraceRecorder(run_name, config=config, tags=tags)
                span_id = recorder.start_span(func.__name__)  # noqa: F841
                try:
                    result = func(*args, **kwargs)
                    recorder.finish_span(output=result)
                    return result
                except BaseException:
                    recorder.finish_span(error=_format_exc())
                    raise
                finally:
                    recorder.finish_run()

            return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# trace_span decorator
# ---------------------------------------------------------------------------


def trace_span(
    name: str | None = None,
    *,
    config: TraceConfig | None = None,
) -> Callable:
    """Record a child span within the active trace run.

    If no active recorder is found this is a silent no-op -- the original
    function is called unchanged.  This makes it safe to decorate library
    functions unconditionally.

    Args:
        name: Span name.  Defaults to the decorated function name.
        config: Unused (reserved for future per-span config).

    Returns:
        A decorator that records the function call as a span.
    """

    def decorator(func: Callable) -> Callable:
        span_name = name if name is not None else func.__name__

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                recorder = active_recorder()
                if recorder is None:
                    return await func(*args, **kwargs)

                recorder.start_span(span_name)
                try:
                    result = await func(*args, **kwargs)
                    recorder.finish_span(output=result)
                    return result
                except BaseException:
                    recorder.finish_span(error=_format_exc())
                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                recorder = active_recorder()
                if recorder is None:
                    return func(*args, **kwargs)

                recorder.start_span(span_name)
                try:
                    result = func(*args, **kwargs)
                    recorder.finish_span(output=result)
                    return result
                except BaseException:
                    recorder.finish_span(error=_format_exc())
                    raise

            return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# TraceSpanCtx context manager
# ---------------------------------------------------------------------------


class TraceSpanCtx:
    """Context manager for manual span tracking.

    Supports both sync (``with``) and async (``async with``) usage::

        with TraceSpanCtx("my_operation"):
            do_work()

        async with TraceSpanCtx("my_async_op"):
            await do_async_work()
    """

    def __init__(
        self,
        name: str,
        *,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._input = input
        self._output: Any = None
        self._metadata: dict[str, Any] = metadata if metadata is not None else {}
        self._recorder: TraceRecorder | None = None
        self._error: str | None = None

    def set_tag(self, key: str, value: Any) -> None:
        """Store a metadata key-value pair on this span.

        Args:
            key: Metadata key.
            value: Metadata value.
        """
        self._metadata[key] = value

    def set_output(self, value: Any) -> None:
        """Set the output value for this span.

        The output will be recorded when the context manager exits.
        If not called, the span output will be ``None``.

        Args:
            value: The output value to record.
        """
        self._output = value

    # -- sync context manager ------------------------------------------------

    def __enter__(self) -> TraceSpanCtx:
        self._recorder = active_recorder()
        if self._recorder is not None:
            self._recorder.start_span(self._name)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._recorder is not None:
            if exc_val is not None:
                self._error = _format_exc()
            span_input: dict[str, Any] = {}
            if self._input is not None:
                span_input.update(self._input if isinstance(self._input, dict) else {"value": self._input})
            if self._metadata:
                span_input["metadata"] = self._metadata
            self._recorder.finish_span(
                input=span_input if span_input else None,
                output=self._output,
                error=self._error,
            )

    # -- async context manager -----------------------------------------------

    async def __aenter__(self) -> TraceSpanCtx:
        self._recorder = active_recorder()
        if self._recorder is not None:
            self._recorder.start_span(self._name)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        if self._recorder is not None:
            if exc_val is not None:
                self._error = _format_exc()
            span_input: dict[str, Any] = {}
            if self._input is not None:
                span_input.update(self._input if isinstance(self._input, dict) else {"value": self._input})
            if self._metadata:
                span_input["metadata"] = self._metadata
            self._recorder.finish_span(
                input=span_input if span_input else None,
                output=self._output,
                error=self._error,
            )
        return False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _format_exc() -> str:
    """Return a short string representation of the currently handled exception."""
    import traceback

    return traceback.format_exc()
