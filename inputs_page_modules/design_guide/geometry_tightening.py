"""Geometry tightening recommendation coordination for the Inputs Design Guide."""

from __future__ import annotations

from typing import Any


_GEOMETRY_TIGHTENING_DEPENDENCIES: tuple[str, ...] = (
    "_build_auto_design_context",
    "_candidate_debug_summary",
    "_candidate_in_target_band",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_evaluate_candidate_fast",
    "_geometry_lock_enabled",
    "_geometry_tightening_trial_updates",
    "_guidance_state_snapshot",
    "_resolve_geometry_width_context",
    "_score_auto_design_candidate",
    "evaluate_candidate_full",
)


def bind_geometry_tightening_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _GEOMETRY_TIGHTENING_DEPENDENCIES
            if name in namespace
        }
    )


def _compute_geometry_tightening_recommendation(state: dict) -> dict | None:
    state = _guidance_state_snapshot(state)
    if _geometry_lock_enabled(state):
        return None
    seed_candidate = evaluate_candidate_full(state, source="guidance_geometry_seed")
    if not seed_candidate or not bool(seed_candidate.get("is_compliant")):
        return None

    mode_config = _design_mode_config(_design_optimisation_goal(state))
    current_score = _score_auto_design_candidate(seed_candidate, mode_config, seed_candidate)
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    candidates: list[dict] = []
    for updates in _geometry_tightening_trial_updates(state):
        width_key, _, _ = _resolve_geometry_width_context(state)
        trial_width = float(updates.get(width_key, updates.get("b", 0.0)) or 0.0)
        trial_depth = float(updates.get("D", 0.0) or 0.0)
        candidate_state = dict(state)
        candidate_state.update(updates)
        candidate = _evaluate_candidate_fast(
            candidate_state,
            seed_state=seed_candidate["state"],
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            source="geometry_tighten",
            label=f"{int(trial_width)} x {int(trial_depth)} mm",
            action_type="tighten_geometry",
        )
        if candidate is None or not bool(candidate.get("is_compliant")):
            continue
        candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
        candidates.append(candidate)

    if not candidates:
        return None

    best = min(
        candidates,
        key=lambda item: (
            float(item.get("score", float("inf"))),
            0 if _candidate_in_target_band(item, mode_config) else 1,
            float(item.get("depth", 0.0) or 0.0),
            float(item.get("width", 0.0) or 0.0),
        ),
    )
    if float(best.get("score", float("inf"))) >= current_score - 1e-6:
        return None

    width_key, width_label, _ = _resolve_geometry_width_context(state)
    return {
        "updates": dict(best.get("updates") or {}),
        "width_key": width_key,
        "width_label": width_label,
        "width": float(best.get("width", 0.0) or 0.0),
        "depth": float(best.get("depth", 0.0) or 0.0),
        "util": float(best.get("worst_util", 0.0) or 0.0),
        "score": float(best.get("score", 0.0) or 0.0),
        "label": str(best.get("label") or ""),
        "candidate_summary": _candidate_debug_summary(best),
        "candidate_type": "geometry",
    }


__all__ = [
    "bind_geometry_tightening_dependencies",
    "_compute_geometry_tightening_recommendation",
]
