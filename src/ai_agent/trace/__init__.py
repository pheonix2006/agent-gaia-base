"""Local trace system

Decorator-driven structured tracing for recording execution traces to JSON files.

Usage:
    from ai_agent.trace import trace_run, trace_span, TraceSpanCtx

    @trace_run("my_agent")
    async def run_agent(query: str) -> str:
        ...
"""

from .assertions import SpanAssertion
from .config import TraceConfig
from .decorators import TraceSpanCtx, trace_run, trace_span
from .recorder import TraceRecorder

__all__ = [
    "trace_run",
    "trace_span",
    "TraceSpanCtx",
    "TraceRecorder",
    "TraceConfig",
    "SpanAssertion",
]
