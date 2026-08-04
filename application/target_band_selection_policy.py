"""Application-owned target-band candidate acceptance decisions."""

from __future__ import annotations

from typing import Any


def resolve_target_band_selected_candidate_acceptance(
    *,
    candidate_improves: bool,
    allow_in_band_shear_cleanup_candidate: bool = False,
) -> dict[str, Any]:
    """Resolve whether the ranked target-band candidate should be accepted."""

    accepted = bool(candidate_improves) or bool(allow_in_band_shear_cleanup_candidate)
    if accepted:
        return {
            "accepted": True,
            "stop_reason": None,
            "reason_code": "ranked_candidate_improves",
        }
    return {
        "accepted": False,
        "stop_reason": "no_improving_candidate",
        "reason_code": "ranked_candidate_no_improvement",
    }


__all__ = ["resolve_target_band_selected_candidate_acceptance"]
