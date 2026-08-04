"""Typed geometry recommendation transaction over explicit candidate ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from inputs_application.geometry_search_policy import (
    build_auto_design_context,
    design_mode_config,
    design_optimisation_goal,
    generate_balanced_geometry_options,
    generate_same_or_larger_geometry_options,
    generate_shallower_or_equal_depths,
    generate_slightly_deeper_depths,
    geometry_lock_enabled,
    geometry_tightening_trial_updates,
    recommendation_search_allowed,
)
from inputs_application.recommendation_evaluation import evaluate_shear_with_state
from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.state_utils import (
    float_from_state,
    guidance_state_snapshot,
    updates_match_state,
)
from inputs_application.candidate_identity import (
    make_auto_design_candidate_key as _make_auto_design_candidate_key,
)


CandidateEvaluator = Callable[..., dict[str, Any] | None]
CandidateRanker = Callable[..., list[dict[str, Any]]]


@dataclass(frozen=True)
class GeometryCandidateRuntime:
    evaluate_full: CandidateEvaluator
    evaluate_fast: CandidateEvaluator
    rank: CandidateRanker
    max_stage_candidates: int = 20


def compute_geometry_recommendation(
    state: Mapping[str, Any],
    *,
    runtime: GeometryCandidateRuntime,
) -> dict[str, Any] | None:
    """Run one geometry recommendation search without any provider globals."""

    resolved_state = guidance_state_snapshot(state)
    if geometry_lock_enabled(resolved_state):
        return None
    mode = design_mode_config(design_optimisation_goal(resolved_state))
    seed = runtime.evaluate_full(
        resolved_state,
        source="geometry_recommendation_seed",
    )
    if not seed or not recommendation_search_allowed(
        resolved_state,
        seed.get("overview"),
    ):
        return None
    context = build_auto_design_context(
        seed["state"],
        mode,
        reference_overview=seed.get("overview"),
    )
    cache: dict = {}
    metrics = {
        "_reference_overview": seed.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    states: list[dict[str, Any]] = []
    if bool(seed.get("is_compliant")):
        for updates in geometry_tightening_trial_updates(resolved_state):
            states.append({**resolved_state, **updates})
    else:
        goal = design_optimisation_goal(resolved_state)
        if goal == "shallower_beam":
            states.extend(generate_shallower_or_equal_depths(seed))
            states.extend(generate_slightly_deeper_depths(seed))
        elif goal == "less_longitudinal_reinforcement":
            states.extend(generate_same_or_larger_geometry_options(seed))
        else:
            states.extend(generate_balanced_geometry_options(seed))

    deduped = {
        _make_auto_design_candidate_key(candidate_state): candidate_state
        for candidate_state in states
    }
    candidates: list[dict[str, Any]] = []
    for candidate_state in list(deduped.values())[: runtime.max_stage_candidates]:
        candidate = runtime.evaluate_fast(
            candidate_state,
            seed_state=seed["state"],
            context=context,
            eval_cache=cache,
            metrics=metrics,
            source="geometry_recommendation",
            label=(
                f"{int(resolve_geometry_width_context(candidate_state)[2])} x "
                f"{int(float_from_state(candidate_state, 'D', 0.0))} mm"
            ),
            action_type="apply_geometry_recommendation",
        )
        if candidate is None or updates_match_state(
            resolved_state,
            candidate.get("updates", {}),
        ):
            continue
        candidates.append(candidate)
    ranked = runtime.rank(candidates, mode, limit=1)
    best = ranked[0] if ranked else None
    if not best or updates_match_state(resolved_state, best.get("updates", {})):
        return None
    width_key, width_label, _ = resolve_geometry_width_context(resolved_state)
    return {
        "updates": dict(best.get("updates") or {}),
        "width_key": width_key,
        "width_label": width_label,
        "width": float(best.get("width", 0.0) or 0.0),
        "depth": float(best.get("depth", 0.0) or 0.0),
        "bending_util": float(
            best.get("overview", {}).get("utils", {}).get("bending", 0.0) or 0.0
        ),
        "shear_util": float(
            best.get("overview", {}).get("utils", {}).get("shear", 0.0) or 0.0
        ),
        "web_util": float(
            (evaluate_shear_with_state(best.get("state") or resolved_state) or {}).get(
                "web_util",
                0.0,
            )
            or 0.0
        ),
        "required_ast": float(best.get("required_ast", 0.0) or 0.0),
        "score": float(best.get("score", 0.0) or 0.0),
    }


__all__ = ["GeometryCandidateRuntime", "compute_geometry_recommendation"]
