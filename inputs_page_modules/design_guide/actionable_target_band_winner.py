"""Actionable target-band winner coordination for the Inputs Design Guide."""

from __future__ import annotations

from typing import Any


_ACTIONABLE_TARGET_BAND_WINNER_DEPENDENCIES: tuple[str, ...] = (
    "EFFICIENCY_TARGET_UTIL_MAX",
    "EFFICIENCY_TARGET_UTIL_MIN",
    "TARGET_BAND_EPS",
    "_candidate_is_materially_actionable",
    "_compute_bottom_reo_recommendation",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_design_optimisation_goal_label",
    "_guidance_change_lines_for_updates",
    "_guidance_item",
    "_guidance_state_snapshot",
    "_parse_util_value",
    "_recommendation_search_allowed",
    "_reinforcement_options_remain",
    "_should_override_target_band_done_state",
    "_updates_match_state",
    "evaluate_candidate_full",
)


def bind_actionable_target_band_winner_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _ACTIONABLE_TARGET_BAND_WINNER_DEPENDENCIES
            if name in namespace
        }
    )


def _get_actionable_target_band_winner(
    state: dict,
    overview: dict,
    *,
    debug_extra: dict | None = None,
) -> dict | None:
    if isinstance(debug_extra, dict):
        debug_extra["target_band_default_stop"] = True
        debug_extra["target_band_override_allowed"] = False
        debug_extra["target_band_override_reason"] = None
        debug_extra["in_band_materiality_passed"] = None
        debug_extra["mode_difference_material"] = None
        debug_extra["current_goal_alignment_score"] = None
        debug_extra["winner_goal_alignment_score"] = None
        debug_extra["goal_alignment_improvement"] = None
    if not isinstance(overview, dict) or not bool(overview.get("all_key_pass")):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "not_all_key_pass"
        return None
    goal = _design_optimisation_goal(state)
    if goal not in ("balanced", "shallower_beam"):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "goal_not_balanced_or_shallower"
        return None
    if not _recommendation_search_allowed(state):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "recommendation_search_blocked"
        return None
    if not _reinforcement_options_remain(state):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "no_reinforcement_options_remain"
        return None
    worst_util = _parse_util_value(overview.get("worst_util"))
    governing_util = _parse_util_value(overview.get("governing_util"))
    bending_util = _parse_util_value((overview.get("utils") or {}).get("bending"))
    band_focus_util = governing_util
    band_focus_source = str(overview.get("governing_util_source") or "overview.governing_util")
    if band_focus_util is None and bending_util is not None:
        band_focus_util = bending_util
        band_focus_source = "overview.utils.bending"
    if band_focus_util is None:
        band_focus_util = worst_util
        band_focus_source = "overview.worst_util"
    if band_focus_util is None:
        band_focus_util = 0.0
    in_band_with_eps = (
        EFFICIENCY_TARGET_UTIL_MIN
        <= float(band_focus_util)
        <= (EFFICIENCY_TARGET_UTIL_MAX + TARGET_BAND_EPS)
    )
    if isinstance(debug_extra, dict):
        debug_extra["target_band_eps"] = float(TARGET_BAND_EPS)
        debug_extra["target_band_with_eps_passed"] = bool(in_band_with_eps)
        debug_extra["target_band_focus_util"] = float(band_focus_util)
        debug_extra["target_band_focus_source"] = str(band_focus_source or "overview.worst_util")
        debug_extra["target_band_worst_util"] = (
            float(worst_util) if worst_util is not None else None
        )
        debug_extra["target_band_bending_util"] = (
            float(bending_util) if bending_util is not None else None
        )
    if not in_band_with_eps:
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "not_in_efficiency_target_band"
        return None
    if float(band_focus_util) > EFFICIENCY_TARGET_UTIL_MAX + 1e-9:
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "near_upper_band_border_stop_default"
        return None
    if isinstance(debug_extra, dict):
        debug_extra["reason"] = "already_in_efficiency_target_band"
    return None
    rec = _compute_bottom_reo_recommendation(state)
    if not isinstance(rec, dict):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "no_bottom_recommendation"
        return None
    updates = dict(rec.get("updates") or {})
    if not updates or _updates_match_state(state, updates):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "empty_or_noop_updates"
        return None
    raw_cl = rec.get("guidance_change_lines")
    clines = raw_cl if isinstance(raw_cl, list) else _guidance_change_lines_for_updates(state, updates)
    if not _candidate_is_materially_actionable(
        state,
        updates,
        delta_b_mm=rec.get("delta_b_mm"),
        delta_D_mm=rec.get("delta_D_mm"),
        delta_Ast_bot=rec.get("delta_Ast_bot"),
        guidance_change_lines=None,
    ):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "not_materially_actionable"
        return None
    trial = dict(_guidance_state_snapshot(state))
    trial.update(updates)
    cand = evaluate_candidate_full(
        _guidance_state_snapshot(trial),
        source="target_band_actionable_winner_check",
    )
    if not cand or not bool((cand.get("overview") or {}).get("all_key_pass")):
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = "trial_not_compliant_or_eval_failed"
        return None
    mode_cfg = _design_mode_config(goal)
    seed_c = evaluate_candidate_full(
        _guidance_state_snapshot(state),
        source="in_band_goal_align_seed",
    )
    ok_override, o_reason = _should_override_target_band_done_state(
        rec,
        state,
        overview,
        goal,
        mode_cfg,
        seed_c,
        cand,
        debug_extra=debug_extra,
    )
    if isinstance(debug_extra, dict):
        debug_extra["target_band_override_reason"] = o_reason
    if not ok_override:
        if isinstance(debug_extra, dict):
            debug_extra["reason"] = o_reason
        return None
    if isinstance(debug_extra, dict):
        debug_extra["target_band_default_stop"] = False
        debug_extra["target_band_override_allowed"] = True
    gcl = [str(x).strip() for x in (clines or []) if str(x).strip()]
    fam = str(rec.get("recommendation_family_tag") or "")
    subs = list(rec.get("subfamilies") or []) if isinstance(rec.get("subfamilies"), list) else []
    if isinstance(debug_extra, dict):
        debug_extra["family"] = fam
        debug_extra["subfamilies"] = subs
        debug_extra["change_lines"] = gcl
    title = (
        str(rec.get("guidance_recommendation_title") or rec.get("label") or "").strip()
        or "Refine section and bottom reinforcement"
    )
    primary = str(rec.get("label") or "").strip() or "Apply recommended adjustment"
    return _guidance_item(
        "bending",
        title,
        primary,
        "Alternative: keep the current design if the reserve is acceptable.",
        (
            f"Why: worst utilisation is {wu:.2f} (within the "
            f"{EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f} target band), "
            f"but a practical one-click refinement remains for "
            f"{_design_optimisation_goal_label(state).lower()}."
        ),
        "Key levers: beam width b, depth D, bottom reinforcement layout",
        "apply_bottom_recommendation",
        {},
        status="PASS",
        util=wu,
        guidance_change_lines=gcl or None,
    )
