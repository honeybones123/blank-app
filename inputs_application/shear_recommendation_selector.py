"""Application-owned final selector for shear recommendations."""

from __future__ import annotations

import math
from typing import Any, Callable

from application.candidate_geometry_metrics import (
    resolve_auto_design_shear_candidate_practicality_metrics,
)
from application.target_band_evaluation import resolve_candidate_in_target_band
from inputs_application.geometry_search_policy import design_optimisation_goal
from inputs_application.recommendation_primitives import shear_util_from_candidate
from inputs_application.recommendation_target_band import (
    annotate_candidate_target_band_metrics,
)
from inputs_application.state_utils import updates_match_state
from inputs_application.policy_constants import (
    EFFICIENCY_TARGET_UTIL_MAX,
    EFFICIENCY_TARGET_UTIL_MIN,
)


def _candidate_bending_demand_util(candidate: dict) -> float | None:
    pack = (((candidate or {}).get("overview") or {}).get("packs") or {}).get(
        "bending"
    ) or {}
    capacity = float(pack.get("summary_phiMu_kNm", 0.0) or 0.0)
    demand = float(pack.get("summary_Mu_star_kNm", 0.0) or 0.0)
    return demand / capacity if capacity > 1e-9 else None


def _candidate_objective_util(candidate: dict) -> float:
    state = candidate.get("state") if isinstance(candidate, dict) else {}
    goal = design_optimisation_goal(state if isinstance(state, dict) else {})
    utils = (
        candidate.get("overview", {}).get("utils", {})
        if isinstance(candidate, dict)
        else {}
    )
    target_domain = str(
        (
            candidate.get("target_domain_for_band")
            if isinstance(candidate, dict)
            else ""
        )
        or ""
    ).strip().lower()
    bending_util = (
        _candidate_bending_demand_util(candidate)
        if isinstance(candidate, dict)
        else None
    )
    values = (
        [utils.get("shear")]
        if target_domain == "shear" or goal == "less_shear_reinforcement"
        else [bending_util, utils.get("shear")]
    )
    resolved = []
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except Exception:
            continue
        if not math.isnan(number):
            resolved.append(number)
    return (
        max(resolved)
        if resolved
        else float(candidate.get("worst_util", 0.0) or 0.0)
    )


def _candidate_util_distance(candidate: dict, mode_config: dict) -> float:
    util = _candidate_objective_util(candidate)
    target_min = float(mode_config["target_util_min"])
    target_max = float(mode_config["target_util_max"])
    target_mid = (target_min + target_max) / 2.0
    if util < target_min:
        return target_min - util
    if util > target_max:
        return util - target_max
    return abs(util - target_mid)


def shear_candidate_selector_key(
    candidate: dict,
    seed_candidate: dict,
    mode_config: dict,
) -> tuple:
    current_state = dict(seed_candidate.get("state") or {})
    annotate_candidate_target_band_metrics(candidate, mode_config)
    metrics = resolve_auto_design_shear_candidate_practicality_metrics(
        candidate,
        current_state,
    )
    candidate.update(metrics)
    post_util = candidate.get("candidate_post_util", candidate.get("worst_util"))
    try:
        post_util_value = (
            float(post_util) if post_util is not None else float("inf")
        )
    except (TypeError, ValueError):
        post_util_value = float("inf")
    in_target_band = resolve_candidate_in_target_band(
        candidate,
        mode_config,
        default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
        default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
        optimisation_goal_resolver=lambda state: design_optimisation_goal(state),
    )
    return (
        0 if bool(candidate.get("is_compliant")) else 1,
        0 if in_target_band else 1,
        float(
            candidate.get("candidate_distance_to_target_band")
            or _candidate_util_distance(candidate, mode_config)
            or 0.0
        ),
        float(metrics.get("shear_candidate_engineering_change", 0.0) or 0.0),
        int(metrics.get("shear_candidate_leg_delta", 0) or 0),
        float(metrics.get("shear_candidate_spacing_delta", 0.0) or 0.0),
        int(metrics.get("shear_candidate_dia_delta", 0) or 0),
        int(metrics.get("shear_candidate_geometry_escalation_flag", 0) or 0),
        float(metrics.get("shear_candidate_geometry_delta", 0.0) or 0.0),
        float(metrics.get("shear_candidate_steel_delta", 0.0) or 0.0),
        float(
            metrics.get("shear_candidate_total_practicality_penalty", 0.0)
            or 0.0
        ),
        float(candidate.get("score", 0.0) or 0.0),
        post_util_value,
        float(candidate.get("depth", 0.0) or 0.0),
        float(candidate.get("width", 0.0) or 0.0),
    )


def pick_best_shear_recommendation(
    candidates: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
    conservative: bool,
    baseline_su: float | None,
    log_candidate_rank: Callable[..., Any],
) -> dict | None:
    pool = [candidate for candidate in candidates if candidate]
    while pool:
        ranked_pool = sorted(
            pool,
            key=lambda item: shear_candidate_selector_key(
                item,
                seed_candidate,
                mode_config,
            ),
        )
        pick = ranked_pool[0] if ranked_pool else None
        if pick is None:
            return None
        if updates_match_state(state, pick.get("updates") or {}):
            log_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=pick,
                reason="noop_updates_match_state",
                util_after=shear_util_from_candidate(pick),
            )
            pool = [item for item in pool if item is not pick]
            continue
        shear_util = shear_util_from_candidate(pick)
        if shear_util is None:
            log_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=pick,
                reason="missing_shear_util",
            )
            pool = [item for item in pool if item is not pick]
            continue
        if (
            not conservative
            and baseline_su is not None
            and float(shear_util) >= float(baseline_su) - 1e-9
        ):
            log_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=pick,
                reason="shear_util_not_improved_vs_baseline",
                util_before=float(baseline_su),
                util_after=float(shear_util),
            )
            pool = [item for item in pool if item is not pick]
            continue
        log_candidate_rank(
            domain="shear",
            event="accepted",
            candidate=pick,
            reason="selector_top_valid",
            util_before=None if conservative else baseline_su,
            util_after=float(shear_util),
        )
        return pick
    return None


__all__ = [
    "pick_best_shear_recommendation",
    "shear_candidate_selector_key",
]
