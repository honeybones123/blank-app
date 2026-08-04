"""Application-owned target-band candidate acceptance decisions."""

from __future__ import annotations

from typing import Any


def build_target_band_fallback_scored_candidate(
    *,
    next_hop_payload: dict[str, Any] | None,
    updates: dict[str, Any] | None,
    signature: Any = None,
    label: str = "Fallback multi-domain cleanup",
    action_type: str = "fallback_next_hop_cleanup",
) -> dict[str, Any] | None:
    """Build the scored-row shape for an approved target-band fallback candidate."""

    if not isinstance(next_hop_payload, dict):
        return None
    update_payload = dict(updates or {})
    if not update_payload:
        return None
    candidate_eval = dict(next_hop_payload.get("eval") or {})
    if not candidate_eval:
        return None
    overview = dict(candidate_eval.get("overview") or {})
    return {
        "sort_key": (-1,),
        "eval": candidate_eval,
        "updates": update_payload,
        "label": str(label or "Fallback multi-domain cleanup"),
        "action_type": str(action_type or "fallback_next_hop_cleanup"),
        "signature": signature,
        "change_summary": None,
        "worst_util": float(overview.get("worst_util", 0.0) or 0.0),
    }


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


__all__ = [
    "build_target_band_fallback_scored_candidate",
    "resolve_target_band_selected_candidate_acceptance",
]
