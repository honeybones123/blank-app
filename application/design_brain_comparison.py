"""Pure comparison gate for the incremental Load Analysis migration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping

from application.contracts.design_actions import DesignActionsSnapshot


@dataclass(frozen=True)
class DesignBrainActionComparison:
    matches: bool
    expected: dict[str, float]
    actual: dict[str, float]
    differences: dict[str, float]
    tolerance: float
    expected_revision: int | None = None
    actual_revision: int | None = None
    revision_matches: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare_design_brain_actions(
    actions: DesignActionsSnapshot,
    actions_used: Mapping[str, Any] | None,
    *,
    tolerance: float = 1e-9,
    actual_revision: int | None = None,
) -> DesignBrainActionComparison:
    """Compare the adapter handover with actions consumed by the brain."""

    expected = {
        "Mu": float(actions.mu),
        "Vu": float(actions.vu),
        "Nu": float(actions.nu),
        "SLS_M": float(actions.sls_m),
        "SLS_V": float(actions.sls_v),
    }
    source = dict(actions_used or {})
    actual: dict[str, float] = {}
    differences: dict[str, float] = {}
    for key, expected_value in expected.items():
        try:
            actual_value = float(source.get(key, float("nan")))
        except (TypeError, ValueError):
            actual_value = float("nan")
        actual[key] = actual_value
        difference = abs(actual_value - expected_value)
        if not math.isfinite(difference) or difference > tolerance:
            differences[key] = difference
    expected_revision = actions.input_revision
    revision_matches = (
        expected_revision is None
        or (
            actual_revision is not None
            and int(expected_revision) == int(actual_revision)
        )
    )
    return DesignBrainActionComparison(
        matches=not differences and revision_matches,
        expected=expected,
        actual=actual,
        differences=differences,
        tolerance=float(tolerance),
        expected_revision=expected_revision,
        actual_revision=actual_revision,
        revision_matches=revision_matches,
    )


__all__ = ["DesignBrainActionComparison", "compare_design_brain_actions"]
