"""Efficiency tightening state coordination for the Inputs page Design Guide."""

from __future__ import annotations

from typing import Any


_EFFICIENCY_TIGHTENING_STATE_DEPENDENCIES: tuple[str, ...] = (
    "GUIDANCE_INEFFICIENT_UTIL_THRESHOLD",
    "GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD",
    "GUIDANCE_STRONGLY_UNDERUTILISED_UTIL",
    "GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL",
    "TARGET_BAND_EPS",
    "VERY_LOW_DEMAND_UTIL_THRESHOLD",
    "_annotate_shear_link_state_debug_from_state",
    "_build_design_actions_context",
    "_candidate_is_growth_move",
    "_collect_design_overview",
    "_combined_underdesign_shear_strengthening_truth_gate_payload",
    "_compute_bottom_reo_tightening_recommendation",
    "_compute_geometry_tightening_recommendation",
    "_compute_mode_guidance_recommendation",
    "_compute_shear_tightening_recommendation",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_effective_bottom_design_state",
    "_efficiency_reduction_profile_from_overview",
    "_geometry_lock_enabled",
    "_guidance_state_snapshot",
    "_is_in_target_zone_with_eps",
    "_log_efficiency_growth_rejection",
    "_parse_util_value",
    "_resolve_design_actions_from_state",
    "_resolved_efficiency_target_band",
    "_resolve_geometry_width_context",
    "_shear_change_is_relevant",
    "_shear_change_is_reinforcement_growth",
    "_shear_cleanup_possible",
    "_shear_demands_negligible",
    "_shear_governing_truth_allows_overdesign_cleanup",
    "_shear_reinforcement_is_active",
    "_shear_overdesign_reserve_guidance_predicate",
    "_state_with_resolved_design_actions",
    "_updates_match_state",
    "_float_from_state",
    "evaluate_candidate_full",
)


def bind_efficiency_tightening_state_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _EFFICIENCY_TIGHTENING_STATE_DEPENDENCIES
            if name in namespace
        }
    )


def _build_efficiency_exhaustion_map(
    *,
    state: dict,
    overview: dict,
    conservative: bool,
    bottom_tighten: dict | None,
    shear_tighten: dict | None,
    geometry_tighten: dict | None,
    shear_cleanup_possible: bool,
    shear_overdesign_cleanup_eligible: bool,
    bending_inefficient: bool,
    shear_inefficient: bool,
) -> dict:
    ex: dict[str, dict] = {
        "shear_cleanup": {"tried": False, "accepted": False, "rejected_reason": None},
        "bottom_reo_reduction": {"tried": False, "accepted": False, "rejected_reason": None},
        "depth_reduction": {"tried": False, "accepted": False, "rejected_reason": None},
        "width_reduction": {"tried": False, "accepted": False, "rejected_reason": None},
    }
    if _shear_reinforcement_is_active(state):
        ex["shear_cleanup"]["tried"] = True
        if shear_tighten:
            ups = dict(shear_tighten.get("updates") or {})
            trial_st = dict(state)
            trial_st.update(ups)
            if shear_tighten.get("candidate_type") == "no_shear_design_cleanup":
                ex["shear_cleanup"]["accepted"] = True
            elif not _shear_change_is_reinforcement_growth(state, trial_st):
                ex["shear_cleanup"]["accepted"] = True
            else:
                ex["shear_cleanup"]["rejected_reason"] = "shear_tightening_was_growth_not_reduction"
        elif shear_cleanup_possible and not shear_overdesign_cleanup_eligible:
            ex["shear_cleanup"]["rejected_reason"] = "shear_overdesign_cleanup_blocked_governing_truth"
        elif shear_overdesign_cleanup_eligible or shear_inefficient:
            ex["shear_cleanup"]["rejected_reason"] = "no_safe_shear_reduction_candidate"
        else:
            ex["shear_cleanup"]["rejected_reason"] = "shear_not_marked_inefficient"
    else:
        ex["shear_cleanup"]["tried"] = True
        ex["shear_cleanup"]["accepted"] = True

    if conservative and bending_inefficient:
        ex["bottom_reo_reduction"]["tried"] = True
        if bottom_tighten:
            ex["bottom_reo_reduction"]["accepted"] = True
        else:
            ex["bottom_reo_reduction"]["rejected_reason"] = "no_safe_bottom_reduction_candidate"
    else:
        ex["bottom_reo_reduction"]["tried"] = True
        ex["bottom_reo_reduction"]["rejected_reason"] = (
            "bending_not_inefficient_vs_guidance_threshold" if not bending_inefficient else "efficiency_branch_inactive"
        )

    if conservative and geometry_tighten:
        ex["depth_reduction"]["tried"] = True
        ex["width_reduction"]["tried"] = True
        ups = dict(geometry_tighten.get("updates") or {})
        wkey, _, w0 = _resolve_geometry_width_context(state)
        d0 = _float_from_state(state, "D", 0.0)
        d1 = float(ups.get("D", d0) or d0)
        w1 = float(ups.get(wkey, w0) or w0)
        depth_down = d1 < d0 - 1e-9
        width_down = w1 < float(w0) - 1e-9
        if depth_down:
            ex["depth_reduction"]["accepted"] = True
        else:
            ex["depth_reduction"]["rejected_reason"] = "no_depth_reduction_in_selected_geometry_trial"
        if width_down:
            ex["width_reduction"]["accepted"] = True
        else:
            ex["width_reduction"]["rejected_reason"] = "no_width_reduction_in_selected_geometry_trial"
    elif conservative:
        ex["depth_reduction"]["tried"] = True
        ex["width_reduction"]["tried"] = True
        ex["depth_reduction"]["rejected_reason"] = "geometry_tightening_unavailable"
        ex["width_reduction"]["rejected_reason"] = "geometry_tightening_unavailable"
    else:
        ex["depth_reduction"]["tried"] = True
        ex["width_reduction"]["tried"] = True
        ex["depth_reduction"]["rejected_reason"] = "efficiency_branch_inactive"
        ex["width_reduction"]["rejected_reason"] = "efficiency_branch_inactive"

    return ex


def compute_efficiency_tightening_state(state: dict, context: dict | None = None) -> dict:
    design_context = context or _build_design_actions_context(state)
    working_state = dict(design_context.get("state") or _state_with_resolved_design_actions(state))
    actions = dict(design_context.get("actions") or _resolve_design_actions_from_state(working_state))
    overview = _collect_design_overview(working_state, context=design_context)
    goal = _design_optimisation_goal(working_state)
    mode_cfg_eff = _design_mode_config(goal)
    target_lo, target_hi, efficiency_default_band_used = _resolved_efficiency_target_band(mode_cfg_eff, goal=goal)
    utils = overview["utils"]
    shear_pack = (((overview or {}).get("packs") or {}).get("shear") or {})
    current_governing_util_source = "overview.worst_util"
    current_governing_util = _parse_util_value(overview.get("governing_util"))
    if current_governing_util is None:
        current_governing_util = _parse_util_value(overview.get("worst_util"))
    else:
        current_governing_util_source = str(overview.get("governing_util_source") or "overview.governing_util")
    current_shear_util_source = "overview.utils.shear"
    current_shear_util = _parse_util_value(shear_pack.get("summary_governing_util"))
    if current_shear_util is None:
        current_shear_util = _parse_util_value(utils.get("shear"))
    else:
        current_shear_util_source = "shear_pack.summary_governing_util"
    current_shear_status = str(shear_pack.get("summary_governing_status") or overview.get("statuses", {}).get("shear") or "").strip().upper()
    current_shear_reason = str(shear_pack.get("summary_governing_reason") or "").strip()
    raw_summary_shear_status = str(shear_pack.get("summary_governing_status") or "").strip().upper()
    if current_shear_util is not None:
        try:
            su_eff = float(current_shear_util)
        except (TypeError, ValueError):
            su_eff = None
        if su_eff is not None:
            if su_eff > 1.0 + 1e-9:
                current_shear_status = "FAIL"
            elif "NEAR" in raw_summary_shear_status or raw_summary_shear_status in ("WARN", "CHECK", "NEAR LIMIT"):
                current_shear_status = "NEAR LIMIT"
            elif su_eff >= float(GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD) - 1e-12:
                current_shear_status = "NEAR LIMIT"
            elif raw_summary_shear_status in {"FAIL", "FAILED"}:
                current_shear_status = "FAIL"
            elif raw_summary_shear_status not in {"INVALID"}:
                current_shear_status = "PASS"
    elif raw_summary_shear_status:
        if "NEAR" in raw_summary_shear_status or raw_summary_shear_status in ("WARN", "CHECK", "NEAR LIMIT"):
            current_shear_status = "NEAR LIMIT"
        elif raw_summary_shear_status in {"FAIL", "FAILED"}:
            current_shear_status = "FAIL"
        elif raw_summary_shear_status not in {"INVALID"}:
            current_shear_status = raw_summary_shear_status
    if current_shear_status:
        overview["statuses"]["shear"] = current_shear_status
    if current_shear_util is not None:
        overview["utils"]["shear"] = current_shear_util
    _tracked_statuses_eff = [
        status for status in (overview.get("statuses") or {}).values()
        if status not in ("—", "")
    ]
    overview["any_fail"] = any(str(status or "").upper() == "FAIL" for status in _tracked_statuses_eff)
    overview["any_warn"] = any(str(status or "").upper() == "NEAR LIMIT" for status in _tracked_statuses_eff)
    overview["all_key_pass"] = bool(_tracked_statuses_eff) and all(
        str(status or "").upper() == "PASS" for status in _tracked_statuses_eff
    )
    overview["optimisation_shear_truth_status_used"] = current_shear_status
    overview["optimisation_shear_truth_util_used"] = current_shear_util
    overview["optimisation_shear_truth_reason_used"] = current_shear_reason
    current_bending_util_source = "overview.utils.bending"
    current_bending_util = _parse_util_value(utils.get("bending"))
    bending_inefficient = current_bending_util is not None and current_bending_util <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD
    shear_relevant = _shear_change_is_relevant(overview, actions)
    shear_cleanup_possible = _shear_cleanup_possible(working_state)
    _truth_allow_overdesign_cleanup, _shear_truth_overdesign_detail = _shear_governing_truth_allows_overdesign_cleanup(
        shear_pack,
    )
    shear_overdesign_cleanup_eligible = bool(shear_cleanup_possible and _truth_allow_overdesign_cleanup)
    shear_inefficient = (
        current_shear_util is not None
        and current_shear_util <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD
        and shear_relevant
    )
    try:
        worst_u = float(overview.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        worst_u = 0.0
    if current_governing_util is None:
        current_governing_util = worst_u
    bending_in_target_band = bool(
        current_bending_util is not None
        and float(current_bending_util) >= float(target_lo) - float(TARGET_BAND_EPS)
        and float(current_bending_util) <= float(target_hi) + float(TARGET_BAND_EPS)
    )
    very_low_demand = (
        bool(overview["all_key_pass"])
        and not bool(overview["any_fail"])
        and not bool(overview["any_warn"])
        and float(current_governing_util or 0.0) < float(VERY_LOW_DEMAND_UTIL_THRESHOLD)
        and not bending_in_target_band
    )
    efficiency_moves_ok = (
        bool(overview["all_key_pass"])
        and not bool(overview["any_fail"])
        and (not bool(overview["any_warn"]) or worst_u < float(GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL))
    )
    bottom_change_possible = float((_effective_bottom_design_state(working_state) or {}).get("Ast_bot", 0.0) or 0.0) > 0.0
    reduction_family_available = bool(bottom_change_possible or shear_cleanup_possible or not _geometry_lock_enabled(working_state))
    low_action_reduction_mode = bool(
        bool(overview["all_key_pass"])
        and not bool(overview["any_fail"])
        and not bool(overview["any_warn"])
        and current_governing_util is not None
        and float(current_governing_util) <= float(target_hi)
        and float(current_governing_util) <= float(GUIDANCE_INEFFICIENT_UTIL_THRESHOLD)
        and reduction_family_available
    )
    cleanup_trigger_util = max(float(target_lo), 0.88)
    in_band_non_governing_shear_cleanup_mode = bool(
        not bool(overview["any_fail"])
        and current_governing_util is not None
        and float(current_governing_util) >= float(target_lo) - float(TARGET_BAND_EPS)
        and float(current_governing_util) <= float(target_hi) + float(TARGET_BAND_EPS)
        and bool(shear_overdesign_cleanup_eligible)
        and _shear_demands_negligible(actions)
    )
    safe_cleanup_mode = bool(
        (
            not bool(overview["any_fail"])
            and current_governing_util is not None
            and float(current_governing_util) <= float(cleanup_trigger_util) + float(TARGET_BAND_EPS)
            and reduction_family_available
        )
        or in_band_non_governing_shear_cleanup_mode
    )
    conservative = bool(
        (efficiency_moves_ok and (bending_inefficient or shear_inefficient or low_action_reduction_mode))
        or safe_cleanup_mode
    )
    if very_low_demand:
        conservative = False
        low_action_reduction_mode = False
        safe_cleanup_mode = False
    classification = "acceptable"
    if overview["any_fail"]:
        classification = "failing"
    elif overview["any_warn"] or float(current_governing_util or 0.0) >= GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD:
        classification = "near_limit"
    elif very_low_demand:
        classification = "very_low_demand"
    elif conservative:
        classification = "inefficient"
    elif overview["all_key_pass"] and target_lo <= float(current_governing_util or 0.0) <= target_hi:
        classification = "optimal"

    mode_tighten = _compute_mode_guidance_recommendation(working_state) if conservative and not safe_cleanup_mode else None
    if mode_tighten and isinstance(mode_tighten, dict):
        mtu = mode_tighten.get("updates") or {}
        if not mtu or _updates_match_state(working_state, mtu):
            mode_tighten = None
    reduction_profile_active = bool(
        _efficiency_reduction_profile_from_overview(overview)
        or low_action_reduction_mode
        or safe_cleanup_mode
    )
    if (
        mode_tighten
        and reduction_profile_active
    ):
        seed_chk = evaluate_candidate_full(_guidance_state_snapshot(working_state), source="efficiency_mode_growth_gate")
        if seed_chk:
            trial_st = dict(working_state)
            trial_st.update(dict(mode_tighten.get("updates") or {}))
            tri_chk = evaluate_candidate_full(_guidance_state_snapshot(trial_st), source="efficiency_mode_growth_gate_trial")
            if tri_chk and _candidate_is_growth_move(seed_chk, tri_chk):
                _log_efficiency_growth_rejection(
                    candidate_family="mode_guidance",
                    seed_candidate=seed_chk,
                    candidate=tri_chk,
                    extra={"label": str(mode_tighten.get("label") or "")},
                )
                mode_tighten = None
    bottom_tighten = _compute_bottom_reo_tightening_recommendation(working_state) if conservative and bending_inefficient and mode_tighten is None else None
    shear_overdesign_reserve_ok, shear_tighten_reserve_predicate = _shear_overdesign_reserve_guidance_predicate(
        working_state,
        overview,
        actions,
        current_shear_status=str(current_shear_status or ""),
        current_shear_util=current_shear_util,
        shear_cleanup_possible=shear_overdesign_cleanup_eligible,
    )
    _base_shear_tighten_conditions = bool(
        (efficiency_moves_ok or safe_cleanup_mode)
        and not very_low_demand
        and (
            shear_inefficient
            or shear_overdesign_cleanup_eligible
            or low_action_reduction_mode
            or safe_cleanup_mode
        )
    )
    _mode_blocks_shear_default = mode_tighten is not None
    _compute_shear_tightening_move = _base_shear_tighten_conditions and (
        not _mode_blocks_shear_default or shear_overdesign_reserve_ok
    )
    shear_link_optim_debug: dict = {}
    if _compute_shear_tightening_move:
        shear_tighten = _compute_shear_tightening_recommendation(working_state, out_debug=shear_link_optim_debug)
    else:
        shear_tighten = None
        _annotate_shear_link_state_debug_from_state(working_state, shear_link_optim_debug)
        shear_link_optim_debug["shear_tightening_terminal_reason"] = "efficiency_branch_suppressed"
    shear_tighten_suppressed_by_mode = bool(
        _mode_blocks_shear_default and _base_shear_tighten_conditions and not shear_overdesign_reserve_ok
    )
    shear_tighten_reserve_override_active = bool(
        _mode_blocks_shear_default and shear_overdesign_reserve_ok and _base_shear_tighten_conditions
    )
    geometry_tighten = _compute_geometry_tightening_recommendation(working_state) if conservative and mode_tighten is None else None
    is_efficiency_reduction_mode = bool(conservative or reduction_profile_active)
    filter_growth_candidates = bool(reduction_profile_active)
    cleanup_candidates_found_count = sum(
        1
        for candidate in (bottom_tighten, shear_tighten, geometry_tighten)
        if isinstance(candidate, dict)
    )
    exhaustion_map = _build_efficiency_exhaustion_map(
        state=working_state,
        overview=overview,
        conservative=conservative,
        bottom_tighten=bottom_tighten,
        shear_tighten=shear_tighten,
        geometry_tighten=geometry_tighten,
        shear_cleanup_possible=shear_cleanup_possible,
        shear_overdesign_cleanup_eligible=shear_overdesign_cleanup_eligible,
        bending_inefficient=bending_inefficient,
        shear_inefficient=shear_inefficient,
    )
    in_target_band_eff = _is_in_target_zone_with_eps(overview, mode_cfg_eff, eps=TARGET_BAND_EPS)
    no_tightening_moves = (
        mode_tighten is None
        and bottom_tighten is None
        and shear_tighten is None
        and geometry_tighten is None
    )
    if (
        bool(overview["all_key_pass"])
        and not bool(overview["any_fail"])
        and not bool(overview["any_warn"])
        and not very_low_demand
        and in_target_band_eff
    ):
        # Once the design is already inside the target band, stop in the done state
        # instead of surfacing a final tightening/cleanup pass.
        classification = "optimal"
        is_efficiency_reduction_mode = False


    return {
        "classification": classification,
        "very_low_demand": bool(very_low_demand),
        "overview": overview,
        "conservative": conservative,
        "efficiency_moves_ok": efficiency_moves_ok,
        "mode_tightening": mode_tighten,
        "bottom_tightening": bottom_tighten,
        "shear_tightening": shear_tighten,
        "geometry_tightening": geometry_tighten,
        "actions_used": actions,
        "shear_relevant": shear_relevant,
        "shear_cleanup_possible": shear_cleanup_possible,
        "shear_overdesign_cleanup_eligible": bool(shear_overdesign_cleanup_eligible),
        "shear_overdesign_truth_util": _shear_truth_overdesign_detail.get("shear_overdesign_truth_util"),
        "shear_overdesign_truth_status": _shear_truth_overdesign_detail.get("shear_overdesign_truth_status"),
        "shear_overdesign_truth_governing_check": _shear_truth_overdesign_detail.get(
            "shear_overdesign_truth_governing_check",
        ),
        "shear_cleanup_blocked_due_to_truth_near_limit": bool(
            _shear_truth_overdesign_detail.get("shear_cleanup_blocked_due_to_truth_near_limit"),
        ),
        "shear_inefficient": shear_inefficient,
        "bending_inefficient": bending_inefficient,
        "is_efficiency_reduction_mode": is_efficiency_reduction_mode,
        "filter_growth_candidates": filter_growth_candidates,
        "exhaustion_map": exhaustion_map,
        "worst_util": worst_u,
        "target_band_lo": target_lo,
        "target_band_hi": target_hi,
        "efficiency_default_band_used": bool(efficiency_default_band_used),
        "efficiency_target_band_lo": target_lo,
        "efficiency_target_band_hi": target_hi,
        "optimisation_target_band_lo": target_lo,
        "optimisation_target_band_hi": target_hi,
        "optimisation_current_governing_util": current_governing_util,
        "optimisation_current_governing_util_source": current_governing_util_source,
        "optimisation_current_shear_util_source": current_shear_util_source,
        "optimisation_current_bending_util_source": current_bending_util_source,
        "optimisation_reduction_mode_active": bool(is_efficiency_reduction_mode),
        "optimisation_safe_cleanup_mode_active": bool(safe_cleanup_mode),
        "optimisation_cleanup_trigger_util": cleanup_trigger_util,
        "optimisation_safe_cleanup_mode_reason": (
            "in_band_non_governing_shear_cleanup"
            if in_band_non_governing_shear_cleanup_mode
            else ("governing_util_within_safe_cleanup_trigger" if safe_cleanup_mode else None)
        ),
        "optimisation_cleanup_candidates_found_count": int(cleanup_candidates_found_count),
        "optimisation_reduction_mode_reason": (
            "very_low_demand_block"
            if very_low_demand
            else (
                "low_action_all_pass_cleanup"
                if low_action_reduction_mode
                else (
                    "safe_cleanup_within_trigger"
                    if safe_cleanup_mode
                    else (
                        "under_target_profile"
                        if reduction_profile_active
                        else (
                            "inefficient_governing_util"
                            if conservative
                            else "inactive"
                        )
                    )
                )
            )
        ),
        "strongly_underutilised": bool(worst_u < float(GUIDANCE_STRONGLY_UNDERUTILISED_UTIL)),
        "shear_tighten_suppressed_by_mode": bool(shear_tighten_suppressed_by_mode),
        "shear_tighten_reserve_override_active": bool(shear_tighten_reserve_override_active),
        "shear_tighten_reserve_predicate": dict(shear_tighten_reserve_predicate),
        "shear_overdesign_reserve_guidance_eligible": bool(shear_overdesign_reserve_ok),
        "mode_guidance_return_blocked_for_shear_reserve": False,
        "surfaced_shear_reserve_item": False,
        **shear_link_optim_debug,
        **_combined_underdesign_shear_strengthening_truth_gate_payload(
            working_state,
            overview=overview,
            efficiency_classification=classification,
        ),
    }


__all__ = [
    "bind_efficiency_tightening_state_dependencies",
    "compute_efficiency_tightening_state",
]
