"""Design Guide mode recommendation coordination."""

from __future__ import annotations

from typing import Any


_MODE_GUIDANCE_RECOMMENDATION_DEPENDENCIES: tuple[str, ...] = (
    "_agent_debug_log",
    "_candidate_debug_summary",
    "_candidate_objective_util",
    "_design_optimisation_goal",
    "_evaluate_auto_design_candidate",
    "_governing_focus_from_overview",
    "_guidance_state_snapshot",
    "_materialize_full_evaluated_candidate",
    "_mode_guidance_focus_from_updates",
    "_recommendation_search_allowed",
    "_updates_match_state",
    "math",
    "run_full_auto_design",
    "st",
)


def bind_mode_guidance_recommendation_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _MODE_GUIDANCE_RECOMMENDATION_DEPENDENCIES
            if name in namespace
        }
    )


def _compute_mode_guidance_recommendation_uncached(state: dict) -> dict | None:
    state = _guidance_state_snapshot(state)
    if not _recommendation_search_allowed(state):
        return None
    seed_candidate = _evaluate_auto_design_candidate(state, source="guidance_seed")
    if not seed_candidate or not bool(seed_candidate.get("is_compliant")):
        return None
    mode = _design_optimisation_goal(state)
    optimiser_result = run_full_auto_design(seed_candidate, mode, force=False)
    best_candidate = _materialize_full_evaluated_candidate(
        (optimiser_result or {}).get("candidate"),
        source="mode_guidance_selected_full",
    )
    if not best_candidate:
        return None
    updates = dict(best_candidate.get("updates") or {})
    if not updates or _updates_match_state(state, updates):
        return None
    current_summary = _candidate_debug_summary(seed_candidate) or {}
    candidate_summary = _candidate_debug_summary(best_candidate) or {}
    current_ast = float(current_summary.get("Ast_bot", 0.0) or 0.0)
    recommended_ast = float(candidate_summary.get("Ast_bot", 0.0) or 0.0)
    governing_focus = _governing_focus_from_overview(seed_candidate.get("overview") or {})
    focus = _mode_guidance_focus_from_updates(updates)
    heavier_for_tightening = recommended_ast > current_ast + 1e-6
    if bool(st.session_state.get("_dev_mode")) and heavier_for_tightening:
        non_bending_reason = focus != "bending" or governing_focus != "bending"
        _agent_debug_log(
            "Heavier candidate produced for tightening recommendation",
            {
                "warning": not non_bending_reason,
                "current_candidate": current_summary,
                "recommended_candidate": candidate_summary,
                "governing_focus": governing_focus,
                "recommendation_focus": focus,
                "non_bending_reason_identified": non_bending_reason,
            },
            location="inputs_page.py:_compute_mode_guidance_recommendation_uncached",
            hypothesis_id="H307",
        )
    phi_m = float(candidate_summary.get("summary_phiMu_kNm", 0.0) or 0.0)
    mu_m = float(candidate_summary.get("summary_Mu_star_kNm", 0.0) or 0.0)
    expected_bend_util = (mu_m / phi_m) if phi_m > 1e-9 else None
    expected_util = expected_bend_util
    mode_goal = _design_optimisation_goal(best_candidate.get("state") or seed_candidate.get("state") or {})
    if mode_goal == "less_shear_reinforcement":
        su = ((best_candidate.get("overview") or {}).get("utils") or {}).get("shear")
        try:
            if su is not None and not math.isnan(float(su)):
                expected_util = float(su)
        except Exception:
            pass
    recommendation = {
        "updates": updates,
        "label": str(best_candidate.get("label") or ""),
        "focus": focus,
        "score": float(best_candidate.get("score", 0.0) or 0.0),
        "optimisation_score": float(_candidate_objective_util(best_candidate)),
        "expected_util": expected_util,
        "real_util": candidate_summary.get("real_util"),
        "material_change": bool((optimiser_result or {}).get("material_change")),
        "candidate_summary": candidate_summary,
        "candidate_type": "mode",
    }
    if bool(st.session_state.get("_dev_mode")):
        fast_candidate = (optimiser_result or {}).get("candidate")
        _agent_debug_log(
            "Computed mode guidance recommendation",
            {
                "solver_seed": current_summary,
                "selected_candidate": candidate_summary,
                "selected_candidate_fast_eval": _candidate_debug_summary(fast_candidate),
                "recommendation": recommendation,
                "fast_vs_full_compare": {
                    "fast": _candidate_debug_summary(fast_candidate),
                    "full": candidate_summary,
                },
                "selection_metrics": (optimiser_result or {}).get("metrics"),
            },
            location="inputs_page.py:_compute_mode_guidance_recommendation_uncached",
            hypothesis_id="H305",
        )
    return recommendation


__all__ = [
    "bind_mode_guidance_recommendation_dependencies",
    "_compute_mode_guidance_recommendation_uncached",
]
