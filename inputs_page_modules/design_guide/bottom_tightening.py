"""Bottom reinforcement tightening recommendation coordination."""

from __future__ import annotations

from typing import Any


_BOTTOM_TIGHTENING_DEPENDENCIES: tuple[str, ...] = (
    "_bottom_arrangement_to_shared_updates",
    "_build_auto_design_context",
    "_candidate_debug_summary",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_effective_bottom_design_state",
    "_evaluate_candidate_fast",
    "_generate_local_bottom_arrangements",
    "_guidance_state_snapshot",
    "_practical_bottom_reo_label",
    "_resolved_efficiency_target_band",
    "evaluate_candidate_full",
)


def bind_bottom_tightening_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _BOTTOM_TIGHTENING_DEPENDENCIES
            if name in namespace
        }
    )


def _compute_bottom_reo_tightening_recommendation(state: dict) -> dict | None:
    state = _guidance_state_snapshot(state)
    current_bottom = _effective_bottom_design_state(state)
    current_ast = float(current_bottom.get("Ast_bot", 0.0) or 0.0)
    if current_ast <= 0.0:
        return None

    mode_config = _design_mode_config(_design_optimisation_goal(state))
    target_lo, target_hi, _ = _resolved_efficiency_target_band(mode_config, goal=_design_optimisation_goal(state))
    target_mid = (target_lo + target_hi) / 2.0
    seed_candidate = evaluate_candidate_full(state, source="guidance_bottom_seed")
    if not seed_candidate:
        return None
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
    for band in range(2):
        for arrangement in _generate_local_bottom_arrangements(state, mode_config, band=band, context=context):
            candidate_state = dict(state)
            candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="guidance_bottom_tighten",
                label=_practical_bottom_reo_label(
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                ),
                action_type="reduce_bottom_reinforcement",
            )
            if candidate is None:
                continue
            actual_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
            if not bool(candidate.get("is_compliant")) or actual_ast >= current_ast - 1e-6:
                continue
            candidate["actual_ast"] = actual_ast
            candidate["arrangement"] = arrangement
            candidates.append(candidate)

    if not candidates:
        return None

    best = min(
        candidates,
        key=lambda item: (
            0 if target_lo <= float(item.get("overview", {}).get("utils", {}).get("bending", 0.0) or 0.0) <= target_hi else 1,
            abs(float(item.get("overview", {}).get("utils", {}).get("bending", 0.0) or 0.0) - target_mid),
            int(item.get("row_count", 1) or 1),
            int(item.get("bar_count", 0) or 0),
            float(item.get("Ast_bot", 0.0) or 0.0),
        ),
    )
    return {
        "arrangement": dict(best.get("arrangement") or {}),
        "updates": _bottom_arrangement_to_shared_updates(dict(best.get("arrangement") or {})),
        "actual_ast": float(best.get("actual_ast", 0.0) or 0.0),
        "util": float(best.get("overview", {}).get("utils", {}).get("bending", 0.0) or 0.0),
        "label": str(best.get("label") or ""),
        "score": float(best.get("score", 0.0) or 0.0),
        "candidate_summary": _candidate_debug_summary(best),
        "candidate_type": "bottom",
    }


__all__ = [
    "bind_bottom_tightening_dependencies",
    "_compute_bottom_reo_tightening_recommendation",
]
