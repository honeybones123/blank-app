"""Guidance-intent coordination for Inputs Design Guide items."""

from __future__ import annotations

from typing import Any


_GUIDANCE_INTENT_DEPENDENCIES: tuple[str, ...] = (
    "EFFICIENCY_TARGET_UTIL_MIN",
    "TARGET_BAND_EPS",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_guidance_item_is_shear_only_cleanup",
    "_guidance_item_material_updates",
    "_guidance_shear_is_non_governing_conservative",
    "_guidance_update_is_lighter_or_smaller",
    "_is_in_target_zone_with_eps",
    "_parse_util_value",
)


def bind_guidance_intent_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _GUIDANCE_INTENT_DEPENDENCIES
            if name in namespace
        }
    )


def _derive_design_guide_guidance_intent(
    item: dict,
    *,
    state: dict,
    overview: dict | None,
    efficiency_state: dict | None,
) -> str:
    ov = overview if isinstance(overview, dict) else {}
    mode_cfg = _design_mode_config(_design_optimisation_goal(state))
    updates = _guidance_item_material_updates(item, state)
    has_material_update = bool(updates)
    has_action = bool(str((item or {}).get("action_type") or "").strip())
    statuses = dict(ov.get("statuses") or {})
    fail_keys = {
        str(k).strip().lower()
        for k, v in statuses.items()
        if str(v or "").strip().upper() == "FAIL"
    }
    any_fail = bool(ov.get("any_fail")) or bool(fail_keys)
    all_key_pass = bool(ov.get("all_key_pass")) and not any_fail
    worst_util = _parse_util_value(ov.get("worst_util"))
    target_lo = float(mode_cfg.get("target_lo", EFFICIENCY_TARGET_UTIL_MIN))
    below_target = bool(all_key_pass and worst_util is not None and float(worst_util) < target_lo - float(TARGET_BAND_EPS))
    in_target_band = bool(all_key_pass and _is_in_target_zone_with_eps(ov, mode_cfg, eps=TARGET_BAND_EPS))
    terminal_state = str((item or {}).get("design_guide_terminal_state") or "").strip()
    classification = str((efficiency_state or {}).get("classification") or "").strip()

    if any_fail and has_action and has_material_update:
        return "required_fix"
    if (
        has_action
        and has_material_update
        and (
            bool((item or {}).get("allow_in_target_primary_action"))
            or str((item or {}).get("design_guide_refinement_priority") or "").strip()
            == "shear_congestion_reshape"
            or bool(((item or {}).get("resolved_candidate") or {}).get("allow_in_target_primary_action"))
            or str(((item or {}).get("resolved_candidate") or {}).get("design_guide_refinement_priority") or "").strip()
            == "shear_congestion_reshape"
        )
    ):
        return "efficiency_tightening"
    if (
        has_action
        and has_material_update
        and _guidance_item_is_shear_only_cleanup(state, updates, item)
        and _guidance_shear_is_non_governing_conservative(ov, mode_cfg)
    ):
        return "optional_cleanup"
    if (
        not has_material_update
        and str((item or {}).get("check_key") or "").strip().lower() == "shear"
        and _guidance_shear_is_non_governing_conservative(ov, mode_cfg)
    ):
        return "optional_cleanup"
    if has_action and below_target and has_material_update and _guidance_update_is_lighter_or_smaller(state, updates, item):
        return "efficiency_tightening"
    if in_target_band and not has_material_update:
        return "already_efficient"
    if terminal_state == "optimal" or (classification == "optimal" and not has_material_update):
        return "already_efficient"
    return "advisory_warning"
