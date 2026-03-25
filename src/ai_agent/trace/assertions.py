"""Pytest-style assertion API for verifying traces in tests.

Provides ``SpanAssertion`` for chainable assertions against individual span
names within a ``TraceRun``, and is consumed by ``TraceRecorder`` helper
methods such as ``has_span()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import TraceRun


class SpanAssertion:
    """Chainable assertion interface for a single span name.

    Returns ``self`` from every assertion method so that calls can be
    chained::

        recorder.has_span("llm.call").exists().with_output(model="gpt-4")

    Args:
        run: The ``TraceRun`` to search within.
        name: The span name to assert against.
    """

    def __init__(self, run: TraceRun, name: str) -> None:
        self._run = run
        self._name = name
        self._spans = run.find_spans(name)

    def exists(self) -> SpanAssertion:
        """Assert at least one span with the given name exists.

        Returns:
            ``self`` for chaining.

        Raises:
            AssertionError: If no matching span is found.
        """
        if not self._spans:
            available = [s.name for s in self._run.spans]
            raise AssertionError(
                f"No span named '{self._name}' found.\n"
                f"Available spans: {available}"
            )
        return self

    def with_input(self, **expected: Any) -> SpanAssertion:
        """Assert at least one matching span has input containing all expected pairs.

        Args:
            **expected: Key-value pairs that must all be present in the span input.

        Returns:
            ``self`` for chaining.

        Raises:
            AssertionError: If no matching span has the expected input.
        """
        self.exists()
        for span in self._spans:
            if span.input is not None and self._dict_contains(span.input, expected):
                return self
        raise AssertionError(
            f"No span '{self._name}' has input containing {expected!r}.\n"
            f"Actual inputs: "
            f"{[span.input for span in self._spans]}"
        )

    def with_output(self, **expected: Any) -> SpanAssertion:
        """Assert at least one matching span has output containing all expected pairs.

        Args:
            **expected: Key-value pairs that must all be present in the span output.

        Returns:
            ``self`` for chaining.

        Raises:
            AssertionError: If no matching span has the expected output.
        """
        self.exists()
        for span in self._spans:
            if span.output is not None and self._dict_contains(span.output, expected):
                return self
        raise AssertionError(
            f"No span '{self._name}' has output containing {expected!r}.\n"
            f"Actual outputs: "
            f"{[span.output for span in self._spans]}"
        )

    def has_error(self, expected_substring: str | None = None) -> SpanAssertion:
        """Assert at least one matching span has error status.

        Args:
            expected_substring: If provided, the span error message must
                contain this substring.

        Returns:
            ``self`` for chaining.

        Raises:
            AssertionError: If no matching span is in error state, or if
                the substring is not found in the error message.
        """
        self.exists()
        for span in self._spans:
            if span.status == "error":
                if expected_substring is None or (
                    span.error is not None and expected_substring in span.error
                ):
                    return self
                raise AssertionError(
                    f"Span '{self._name}' has error but message does not contain "
                    f"'{expected_substring}'.\n"
                    f"Actual error: {span.error!r}"
                )
        raise AssertionError(
            f"No span '{self._name}' has error status.\n"
            f"Statuses: {[span.status for span in self._spans]}"
        )

    @staticmethod
    def _dict_contains(actual: Any, expected: dict[str, Any]) -> bool:
        """Check if *actual* dict contains all key-value pairs from *expected*.

        Args:
            actual: The dict to check against.
            expected: The required key-value pairs.

        Returns:
            True if every key in *expected* exists in *actual* with the same
            value.
        """
        if not isinstance(actual, dict):
            return False
        return all(actual.get(key) == value for key, value in expected.items())
