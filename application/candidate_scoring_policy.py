"""Pure candidate scoring policies owned by the application layer."""

from __future__ import annotations

from typing import Any


def resolve_auto_design_candidate_violation_score(
    candidate: dict[str, Any] | None,
) -> float:
    """Resolve the non-compliant auto-design candidate violation score."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    util = float(candidate_d.get("worst_util", 0.0) or 0.0)
    overflow = max(util - 1.0, 0.0)
    fail_count = int(candidate_d.get("fail_count", 0) or 0)
    return overflow * 100.0 + fail_count * 25.0


__all__ = ["resolve_auto_design_candidate_violation_score"]
