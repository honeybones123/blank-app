"""Dedicated boundary for an externally supplied replacement Design Brain.

The active application never imports a replacement implementation directly.
The replacement may return the neutral execution contract itself, or a caller
may provide an explicit mapper for the replacement's native result shape.
"""

from __future__ import annotations

from typing import Any, Callable

from application.design_brain_port import (
    DesignBrainExecution,
    DesignBrainPort,
    DesignBrainRequest,
)


ReplacementResultMapper = Callable[
    [DesignBrainRequest, Any], DesignBrainExecution
]


class ReplacementDesignBrainAdapter:
    """Adapt one external implementation without leaking its result types."""

    def __init__(
        self,
        implementation: DesignBrainPort | Callable[[DesignBrainRequest], Any],
        *,
        result_mapper: ReplacementResultMapper | None = None,
    ) -> None:
        if not callable(getattr(implementation, "run", None)) and not callable(
            implementation
        ):
            raise TypeError("replacement implementation must provide run(request)")
        if result_mapper is not None and not callable(result_mapper):
            raise TypeError("result_mapper must be callable")
        self._implementation = implementation
        self._result_mapper = result_mapper

    def run(self, request: DesignBrainRequest) -> DesignBrainExecution:
        runner = getattr(self._implementation, "run", None)
        raw_result = runner(request) if callable(runner) else self._implementation(request)
        if isinstance(raw_result, DesignBrainExecution):
            return raw_result
        if self._result_mapper is None:
            raise TypeError(
                "replacement implementation must return DesignBrainExecution "
                "or be paired with result_mapper"
            )
        mapped_result = self._result_mapper(request, raw_result)
        if not isinstance(mapped_result, DesignBrainExecution):
            raise TypeError("result_mapper must return DesignBrainExecution")
        return mapped_result


__all__ = ["ReplacementDesignBrainAdapter", "ReplacementResultMapper"]
