"""Design Brain candidate ranking helpers.

This module owns pure score tuple construction and target-band proximity
scoring. It does not search, generate candidates, evaluate formulas, apply
updates, or render UI.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AutoDesignCandidateSelectionResult:
    """Typed proof record for shared auto-design winner selection.

    This record describes the already-run local selector. It must not drive
    product behaviour until the selector logic itself has been split safely.
    """

    status: str
    selected_reason: str | None
    no_winner_reason: str | None
    selected_candidate_id: str | None
    selected_candidate_identity: str | None
    selected_candidate_index: int | None
    selected_candidate_rank: int | None
    selected_score: float | None
    selected_candidate_post_util: Any
    selected_reaches_target_band: bool | None
    selected_because_band: bool
    winner_pool_mode: str | None
    candidate_count: int
    valid_candidate_count: int
    compliant_count: int
    band_reacher_count: int
    current_in_band: bool
    one_click_available: bool
    winner_goal_score: float | None
    runner_up_goal_score: float | None
    goal_tie_break_reason: str | None
    annotation_keys_added: tuple[str, ...]
    rank_trace_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def auto_design_winner_annotation_keys() -> tuple[str, ...]:
    return (
        "winning_candidate_post_util",
        "winning_candidate_reaches_target_band",
        "winning_candidate_distance_to_target_band",
        "winning_candidate_selected_because_reaches_band",
        "winning_candidate_selected_from_band_reachers",
        "winner_pool_mode",
        "band_reacher_labels_considered",
        "winning_candidate_goal_score",
        "runner_up_goal_score",
        "goal_tie_break_reason",
        "winning_candidate_goal_preference",
        "canonical_winner_label",
        "title_locked_from_final_winner",
    )


def auto_design_candidate_identity(candidate: dict | None, *, fallback_hash: str | None = None) -> str | None:
    if not isinstance(candidate, dict):
        return None
    candidate_id = candidate.get("candidate_id") or candidate.get("source_candidate_id") or None
    if candidate_id:
        return str(candidate_id)
    return f"trace:{fallback_hash}" if fallback_hash else None


def build_no_winner_auto_design_candidate_selection_result(
    *,
    reason: str,
    candidate_count: int,
    valid_candidate_count: int = 0,
    compliant_count: int = 0,
    band_reacher_count: int = 0,
    current_in_band: bool = False,
    one_click_available: bool = False,
) -> AutoDesignCandidateSelectionResult:
    return AutoDesignCandidateSelectionResult(
        status="no_winner",
        selected_reason=None,
        no_winner_reason=str(reason or "no_winner"),
        selected_candidate_id=None,
        selected_candidate_identity=None,
        selected_candidate_index=None,
        selected_candidate_rank=None,
        selected_score=None,
        selected_candidate_post_util=None,
        selected_reaches_target_band=None,
        selected_because_band=False,
        winner_pool_mode=None,
        candidate_count=int(candidate_count),
        valid_candidate_count=int(valid_candidate_count),
        compliant_count=int(compliant_count),
        band_reacher_count=int(band_reacher_count),
        current_in_band=bool(current_in_band),
        one_click_available=bool(one_click_available),
        winner_goal_score=None,
        runner_up_goal_score=None,
        goal_tie_break_reason=None,
        annotation_keys_added=(),
        rank_trace_summary={},
    )


def build_selected_auto_design_candidate_selection_result(
    *,
    winner: dict,
    selected_candidate_identity: str | None,
    selected_candidate_index: int | None,
    selected_reason: str,
    selected_because_band: bool,
    winner_pool_mode: str | None,
    candidate_count: int,
    valid_candidate_count: int,
    compliant_count: int,
    band_reacher_count: int,
    current_in_band: bool,
    one_click_available: bool,
    winner_goal_score: float | None,
    runner_up_goal_score: float | None,
    goal_tie_break_reason: str | None,
) -> AutoDesignCandidateSelectionResult:
    candidate_id = winner.get("candidate_id") or winner.get("source_candidate_id") or None
    return AutoDesignCandidateSelectionResult(
        status="selected",
        selected_reason=str(selected_reason or "selected"),
        no_winner_reason=None,
        selected_candidate_id=str(candidate_id) if candidate_id else None,
        selected_candidate_identity=selected_candidate_identity,
        selected_candidate_index=selected_candidate_index,
        selected_candidate_rank=0,
        selected_score=_as_float(winner.get("score")),
        selected_candidate_post_util=winner.get("candidate_post_util"),
        selected_reaches_target_band=bool(winner.get("candidate_reaches_target_band")),
        selected_because_band=bool(selected_because_band),
        winner_pool_mode=winner_pool_mode,
        candidate_count=int(candidate_count),
        valid_candidate_count=int(valid_candidate_count),
        compliant_count=int(compliant_count),
        band_reacher_count=int(band_reacher_count),
        current_in_band=bool(current_in_band),
        one_click_available=bool(one_click_available),
        winner_goal_score=winner_goal_score,
        runner_up_goal_score=runner_up_goal_score,
        goal_tie_break_reason=goal_tie_break_reason,
        annotation_keys_added=auto_design_winner_annotation_keys(),
        rank_trace_summary={
            "winner_pool_mode": winner_pool_mode,
            "selected_because_band": bool(selected_because_band),
            "final_winner_label": str(winner.get("label") or ""),
            "final_winner_reaches_target_band": bool(winner.get("candidate_reaches_target_band")),
            "final_winner_post_util": winner.get("candidate_post_util"),
            "final_winner_goal_score": winner_goal_score,
        },
    )


def build_auto_design_selected_candidate_selection_result_from_context(
    *,
    winner: dict,
    candidates: list[dict] | tuple[dict, ...],
    fallback_hash: str | None,
    selected_because_band: bool,
    compliant_available: bool,
    winner_pool_mode: str | None,
    candidate_count: int,
    valid_candidate_count: int,
    compliant_count: int,
    band_reacher_count: int,
    current_in_band: bool,
    one_click_available: bool,
    winner_goal_score: float | None,
    runner_up_goal_score: float | None,
    goal_tie_break_reason: str | None,
) -> AutoDesignCandidateSelectionResult:
    selected_candidate_identity = auto_design_candidate_identity(
        winner,
        fallback_hash=fallback_hash,
    )
    selected_candidate_index = next(
        (
            index
            for index, item in enumerate(list(candidates or []))
            if item is winner
        ),
        None,
    )
    selected_reason = (
        "band_reacher_goal_tie_break"
        if selected_because_band
        else ("compliant_candidate" if compliant_available else "least_violation_candidate")
    )
    return build_selected_auto_design_candidate_selection_result(
        winner=winner,
        selected_candidate_identity=selected_candidate_identity,
        selected_candidate_index=selected_candidate_index,
        selected_reason=selected_reason,
        selected_because_band=selected_because_band,
        winner_pool_mode=winner_pool_mode,
        candidate_count=candidate_count,
        valid_candidate_count=valid_candidate_count,
        compliant_count=compliant_count,
        band_reacher_count=band_reacher_count,
        current_in_band=current_in_band,
        one_click_available=one_click_available,
        winner_goal_score=winner_goal_score,
        runner_up_goal_score=runner_up_goal_score,
        goal_tie_break_reason=goal_tie_break_reason,
    )


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def distance_to_band(util: float | None, lo: float, hi: float) -> float | None:
    if util is None:
        return None
    if lo <= util <= hi:
        return 0.0
    if util < lo:
        return float(lo - util)
    return float(util - hi)


def selection_sort_key(candidate: dict, target_low: float, target_high: float) -> tuple:
    preview = _as_float(candidate.get("preview_util"))
    target_mid = (float(target_low) + float(target_high)) / 2.0
    return (
        float(candidate.get("distance_to_target_band") if candidate.get("distance_to_target_band") is not None else 1e9),
        abs(float(preview) - target_mid) if preview is not None else 1e9,
        len(dict(candidate.get("updates") or {})),
        str(candidate.get("title") or ""),
        str(candidate.get("candidate_id") or ""),
    )


def keep_top_candidates(
    candidates: list[dict] | tuple[dict, ...],
    *,
    limit: int,
    max_kept_results: int,
    candidate_key: Callable[[dict], tuple],
    sort_key: Callable[[dict], tuple],
    dominates: Callable[[dict, dict], bool],
) -> dict[str, Any]:
    """Pure generic candidate dedupe/rank/prune core.

    Callers own candidate preparation, debug logging, mode-specific sort-key
    construction, and any intentional candidate mutation.
    """
    bounded_limit = min(max(int(limit), 1), int(max_kept_results))
    deduped: dict[tuple, dict] = {}
    for candidate in list(candidates or []):
        if not candidate:
            continue
        key = candidate_key(candidate)
        existing = deduped.get(key)
        if existing is None or sort_key(candidate) < sort_key(existing):
            deduped[key] = candidate

    ordered = sorted(deduped.values(), key=sort_key)
    kept: list[dict] = []
    decisions: list[tuple[dict, str]] = []
    for candidate in ordered:
        decision = "kept"
        if any(dominates(existing, candidate) for existing in kept):
            decision = "discarded_dominated"
            decisions.append((candidate, decision))
            continue
        if len(kept) >= bounded_limit:
            decision = "discarded_limit"
            decisions.append((candidate, decision))
            continue
        kept.append(candidate)
        decisions.append((candidate, decision))

    return {
        "limit": bounded_limit,
        "ordered": ordered,
        "kept": kept,
        "decisions": decisions,
    }
