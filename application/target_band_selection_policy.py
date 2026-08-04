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


def resolve_target_band_candidate_sort_key(
    *,
    tier: int,
    mixed_sort_prefix: tuple[Any, ...] = (),
    tightening_mode_active: bool,
    governing_domain: str,
    has_target_domains: bool,
    new_max: Any = None,
    new_total: Any = None,
    required_fail_count: int = 0,
    required_unsatisfied_count: int = 0,
    prefer_total_before_max: bool = False,
    shear_sort_util: Any = float("inf"),
    web_sort_util: Any = float("inf"),
    practical_spacing_penalty: int = 0,
    congestion_penalty: int = 0,
    goal_bias: int = 0,
    new_distance: Any = float("inf"),
    wrong_dir_penalty: Any = 0.0,
    directional_tie_key: Any = 0.0,
    reduction_bias: int = 0,
    update_count: int = 0,
) -> tuple[Any, ...]:
    """Build the target-band candidate ranking tuple from plain scoring inputs."""

    prefix = tuple(mixed_sort_prefix or ())
    if bool(tightening_mode_active):
        if str(governing_domain or "").strip().lower() == "shear":
            if bool(has_target_domains) and new_total is not None:
                return (tier, *prefix, int(required_fail_count), int(required_unsatisfied_count), float(new_max), float(new_total), float(shear_sort_util), float(web_sort_util), int(practical_spacing_penalty), int(congestion_penalty), int(goal_bias), float(wrong_dir_penalty), int(reduction_bias), int(update_count))
            return (tier, *prefix, float(shear_sort_util), float(web_sort_util), int(practical_spacing_penalty), int(congestion_penalty), int(goal_bias), float(new_distance), float(wrong_dir_penalty), int(reduction_bias), int(update_count))
        if bool(has_target_domains) and new_total is not None:
            if bool(prefer_total_before_max):
                return (tier, *prefix, int(required_fail_count), int(required_unsatisfied_count), float(new_total), float(new_max), float(wrong_dir_penalty), int(reduction_bias), int(update_count))
            return (tier, *prefix, int(required_fail_count), int(required_unsatisfied_count), float(new_max), float(new_total), float(wrong_dir_penalty), int(reduction_bias), int(update_count))
        return (tier, *prefix, float(new_distance), float(wrong_dir_penalty), int(reduction_bias), int(update_count))
    if bool(has_target_domains) and new_max is not None and new_total is not None:
        if bool(prefer_total_before_max):
            return (tier, *prefix, int(required_fail_count), int(required_unsatisfied_count), float(new_total), float(new_max), float(directional_tie_key), int(update_count))
        return (tier, *prefix, int(required_fail_count), int(required_unsatisfied_count), float(new_max), float(new_total), float(directional_tie_key), int(update_count))
    return (tier, *prefix, float(new_distance), float(directional_tie_key), int(update_count))


def select_target_band_ranked_candidate(
    scored_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    """Select the lexicographic best target-band candidate from scored rows."""

    rows = [dict(row) for row in list(scored_candidates or []) if isinstance(row, dict)]
    if not rows:
        return None
    return min(rows, key=lambda row: row.get("sort_key"))


__all__ = [
    "build_target_band_fallback_scored_candidate",
    "resolve_target_band_candidate_sort_key",
    "resolve_target_band_selected_candidate_acceptance",
    "select_target_band_ranked_candidate",
]
