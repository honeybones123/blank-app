"""Typed, presentation-neutral Design Brain search budgets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SearchMode(StrEnum):
    FAST = "Fast"
    DETAILED = "Detailed"


class SearchKind(StrEnum):
    """Family-owned search intent used only to select a calculation budget."""

    REPAIR = "repair"
    OPTIMISATION = "optimisation"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class SearchProfile:
    mode: SearchMode = SearchMode.FAST
    max_full_evaluations: int = 2500
    max_failure_evaluations: int = 12000
    nearby_dimension_steps: int = 4
    max_consecutive_infeasible: int = 80
    max_combined_continuation_rounds: int = 5

    @classmethod
    def for_mode(cls, mode: str | SearchMode) -> "SearchProfile":
        selected = SearchMode(mode)
        if selected is SearchMode.DETAILED:
            # Detailed mode already owns the full twelve-step geometry
            # neighbourhood, so it does not need Fast mode's bounded
            # continuation frontiers.
            return cls(selected, 12000, 24000, 12, 200, 1)
        return cls()

    def evaluation_budget(self, kind: SearchKind) -> int:
        """Return the configured budget without inferring intent from names."""

        if kind is SearchKind.REPAIR:
            return self.max_failure_evaluations
        if kind is SearchKind.OPTIMISATION:
            return self.max_full_evaluations
        return 0


__all__ = ["SearchKind", "SearchMode", "SearchProfile"]
