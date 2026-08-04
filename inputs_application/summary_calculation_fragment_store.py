"""Session-owned handoff between the Inputs Summary and Calculation fragments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping

from inputs_application.summary_contracts import InputsSummaryCalculationSource


SUMMARY_CALCULATION_SOURCE_KEY = "_inputs_summary_calculation_source_v1"


@dataclass(frozen=True)
class SummaryCalculationFragmentState:
    input_revision: int | None = None
    engineering_hash: str | None = None
    source: InputsSummaryCalculationSource | None = None


class SummaryCalculationFragmentStore:
    """Keep Calculation independent from the Summary fragment return value."""

    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    def current(self) -> SummaryCalculationFragmentState:
        value = self._state.get(SUMMARY_CALCULATION_SOURCE_KEY)
        if isinstance(value, SummaryCalculationFragmentState):
            return value
        return SummaryCalculationFragmentState()

    def publish(
        self,
        source: InputsSummaryCalculationSource,
        *,
        engineering_hash: str | None,
        input_revision: int | None = None,
    ) -> SummaryCalculationFragmentState:
        if not isinstance(source, InputsSummaryCalculationSource):
            raise TypeError("source must be an InputsSummaryCalculationSource")
        current = self.current()
        if (
            input_revision is not None
            and current.input_revision is not None
            and int(input_revision) < int(current.input_revision)
        ):
            raise ValueError("cannot publish a superseded summary revision")
        state = SummaryCalculationFragmentState(
            input_revision=(
                int(input_revision) if input_revision is not None else None
            ),
            engineering_hash=(
                str(engineering_hash) if engineering_hash is not None else None
            ),
            source=source,
        )
        self._state[SUMMARY_CALCULATION_SOURCE_KEY] = state
        return state


__all__ = [
    "SUMMARY_CALCULATION_SOURCE_KEY",
    "SummaryCalculationFragmentState",
    "SummaryCalculationFragmentStore",
]
