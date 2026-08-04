"""Design Guide executor actionability contract coordination."""

from __future__ import annotations

from typing import Any


_EXECUTOR_ACTIONABILITY_CONTRACT_DEPENDENCIES: tuple[str, ...] = (
    "FINAL_ACCEPTED_MIN_FAMILY_UTIL",
    "GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN",
    "_COMPOUND_SHEAR_UPDATE_KEYS",
    "_build_design_actions_context",
    "_collect_design_overview",
    "_compound_subfamilies_from_updates",
    "_design_guide_candidate_family",
    "_design_guide_preview_contract_for_updates",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_evaluate_auto_design_candidate",
    "_float_from_state",
    "_governing_focus_from_overview",
    "_guidance_item_is_resolved_one_click",
    "_guidance_state_snapshot",
    "_int_from_state",
    "_one_click_domain_needs_cleanup",
    "_parse_util_value",
    "_resolve_design_actions_from_state",
    "_resolve_recommendation_updates",
    "_resolved_shear_cleanup_is_executor_safe",
    "_shear_demands_negligible",
)


def bind_executor_actionability_contract_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _EXECUTOR_ACTIONABILITY_CONTRACT_DEPENDENCIES
            if name in namespace
        }
    )


def _guidance_executor_actionability_contract(
    item: dict | None,
    *,
    state: dict | None,
) -> tuple[bool, str | None]:
    """
    Keep Design Guide primary actionability aligned with the executor's current
    acceptance rules.

    This is intentionally narrow: we only suppress cards that are effectively
    non-governing shear cleanup from the current state, because one-click later
    prunes those candidates as non-actionable.
    """
    if not isinstance(item, dict):
        return False, "invalid_guidance_item"
    current_state = _guidance_state_snapshot(state or {})
    action_type = str(item.get("action_type") or "").strip()
    if not action_type:
        return False, "missing_action_type"
    if str(item.get("bucket") or "").strip().lower() == "efficiency" and not _guidance_item_is_resolved_one_click(item):
        return False, "primary_efficiency_card_not_executor_backed"

    try:
        updates = _resolve_recommendation_updates(item, state=current_state)
    except Exception:
        updates = None
    updates = dict(updates or {})
    if not updates:
        return False, "missing_recommendation_updates"

    touches_shear = bool(set(updates) & _COMPOUND_SHEAR_UPDATE_KEYS)
    if touches_shear:
        design_actions = dict(_resolve_design_actions_from_state(current_state) or {})
        direct_vu = abs(_float_from_state(current_state, "uls_Vstar", _float_from_state(current_state, "Vu_star", 0.0)))
        if (
            _shear_demands_negligible(design_actions)
            or direct_vu <= float(GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN) + 1e-12
        ):
            return False, "blocked_zero_shear_demand_shear_update_not_meaningful"

    is_local_cleanup = bool(
        item.get("local_cleanup_candidate")
        or str(item.get("source") or "").strip() == "generate_in_target_local_cleanup_candidates"
        or bool((item.get("resolved_candidate") or {}).get("local_cleanup_candidate"))
    )
    if is_local_cleanup and _guidance_item_is_resolved_one_click(item):
        preview_pass, _preview_util, preview_reason = _design_guide_preview_contract_for_updates(
            current_state,
            updates,
        )
        if preview_pass:
            return True, None
        return False, preview_reason or "local_cleanup_preview_failed"

    if not touches_shear:
        return True, None

    next_state = dict(current_state)
    next_state.update(updates)
    current_spacing = _float_from_state(current_state, "s_lig", 0.0)
    next_spacing = _float_from_state(next_state, "s_lig", current_spacing)
    current_legs = _int_from_state(current_state, "lig_legs", 0)
    next_legs = _int_from_state(next_state, "lig_legs", current_legs)
    current_dia = _int_from_state(current_state, "lig_d", 0)
    next_dia = _int_from_state(next_state, "lig_d", current_dia)
    shear_cleanup_like = bool(
        (next_legs == 0 and current_legs > 0)
        or (next_spacing > current_spacing + 1e-9)
        or (current_legs > 0 and next_legs < current_legs)
        or (current_dia > 0 and next_dia < current_dia)
    )
    if not shear_cleanup_like:
        return True, None

    design_context = _build_design_actions_context(current_state)
    overview = _collect_design_overview(current_state, context=design_context)
    cur_eval = {
        "state": current_state,
        "overview": overview,
    }
    mode_config = _design_mode_config(_design_optimisation_goal(current_state))
    try:
        preview_candidate = _evaluate_auto_design_candidate(
            current_state,
            updates=updates,
            source="design_guide_executor_shear_family_threshold_probe",
            label=str(item.get("title_main") or "Design Guide candidate"),
            action_type=action_type,
        )
    except Exception:
        preview_candidate = None
    preview_overview = dict((preview_candidate or {}).get("overview") or {})
    preview_shear_util = _parse_util_value(dict(preview_overview.get("utils") or {}).get("shear"))
    if preview_shear_util is None or float(preview_shear_util) < float(FINAL_ACCEPTED_MIN_FAMILY_UTIL):
        return False, "blocked_shear_cleanup_does_not_reach_final_family_threshold"
    governing_domain = str(_governing_focus_from_overview(overview) or "").strip().lower()
    family = str(_design_guide_candidate_family(item) or "").strip().lower()
    subfamilies = set(_compound_subfamilies_from_updates(updates))
    behaves_like_shear_cleanup = bool(
        family in {"shear", "compound"}
        or "shear" in subfamilies
    )
    if not behaves_like_shear_cleanup:
        return True, None

    if _guidance_item_is_resolved_one_click(item) and _resolved_shear_cleanup_is_executor_safe(
        item,
        state=current_state,
        overview=overview,
    ):
        return True, None

    if family == "compound" and bool(overview.get("all_key_pass")):
        return False, "rejected_as_non_governing_cleanup"

    shear_cleanup_needed = _one_click_domain_needs_cleanup(cur_eval, "shear", mode_config)
    if governing_domain == "bending" and not shear_cleanup_needed:
        return False, "rejected_as_non_governing_cleanup"
    if governing_domain == "shear" and not shear_cleanup_needed:
        return False, "rejected_as_non_governing_cleanup"
    return True, None
