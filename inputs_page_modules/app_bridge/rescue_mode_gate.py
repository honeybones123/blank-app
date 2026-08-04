"""Auto-design rescue-mode entry gate."""

from __future__ import annotations

import math
from typing import Any


_RESCUE_MODE_GATE_DEPENDENCIES: tuple[str, ...] = (
    "_candidate_objective_util",
    "_rescue_mode_both_domains_fail_meanfully",
    "_rescue_mode_choose_family",
    "_rescue_mode_choose_tier",
    "_rescue_mode_current_beam_plausible",
)


def bind_rescue_mode_gate_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _RESCUE_MODE_GATE_DEPENDENCIES
            if name in namespace
        }
    )


def _rescue_mode_should_enter(
    *,
    state: dict,
    init_eval: dict | None,
    final_eval: dict | None,
    final_pass: bool,
    final_updates: dict,
    stop_reason: str,
    mode_config: dict,
) -> tuple[bool, str | None, str | None, str | None, dict]:
    section_kind = str(state.get("section_shape") or state.get("section_type") or "RECT").strip().upper()
    initial_all_pass = bool((init_eval.get("overview") or {}).get("all_key_pass"))
    debug = {
        "section_kind": section_kind,
        "initial_all_pass": initial_all_pass,
        "final_pass": bool(final_pass),
        "final_updates_present": bool(final_updates),
        "stop_reason": str(stop_reason or ""),
        "initial_objective_util": None,
        "final_objective_util": None,
        "severe_fail": False,
        "both_fail_meaningfully": False,
        "family": None,
        "requested_tier": None,
        "current_beam_plausible": None,
    }
    if section_kind not in {"RECT", "RECTANGULAR", ""}:
        return False, "non_rectangular_section", None, None, debug
    if initial_all_pass:
        return False, "initial_state_already_passing", None, None, debug
    if final_pass:
        return False, "normal_one_click_found_all_pass_path", None, None, debug
    family = _rescue_mode_choose_family(init_eval, mode_config)
    debug["family"] = family
    if not family:
        return False, "family_not_rescue_eligible", None, None, debug
    requested_tier = _rescue_mode_choose_tier(state, init_eval, family)
    debug["requested_tier"] = requested_tier
    if requested_tier is None:
        return False, "tier_not_rescue_eligible", family, None, debug
    current_beam_plausible = _rescue_mode_current_beam_plausible(state, family=family, tier=requested_tier)
    debug["current_beam_plausible"] = bool(current_beam_plausible)
    if current_beam_plausible:
        return False, "current_beam_already_plausible", family, requested_tier, debug
    if str(stop_reason or "") in {"already_in_band", "reached_target_band"}:
        return False, "normal_one_click_retained_control", family, requested_tier, debug
    init_util = _candidate_objective_util(init_eval or {})
    try:
        init_u = float(init_util)
    except (TypeError, ValueError):
        init_u = None
    debug["initial_objective_util"] = init_u
    severe_fail = bool(
        init_u is not None
        and math.isfinite(init_u)
        and init_u >= 3.0
    )
    final_util = _candidate_objective_util(final_eval or {})
    try:
        final_u = float(final_util)
    except (TypeError, ValueError):
        final_u = None
    debug["final_objective_util"] = final_u
    both_fail = _rescue_mode_both_domains_fail_meanfully(init_eval, mode_config)
    debug["severe_fail"] = bool(severe_fail)
    debug["both_fail_meaningfully"] = bool(both_fail)
    if not severe_fail and not both_fail:
        return False, "severity_below_rescue_threshold", family, requested_tier, debug
    if (
        final_updates
        and not final_pass
        and final_u is not None
        and math.isfinite(final_u)
        and final_u > 1.10
        and str(stop_reason or "") == "best_available_out_of_band_candidate"
    ):
        return True, "normal_one_click_best_available_still_far_from_band", family, requested_tier, debug
    if not final_updates and str(stop_reason or "") in {
        "no_actionable_candidates",
        "no_actionable_candidates_after_full_tightening_search",
        "no_improving_candidate",
        "no_full_coverage_candidate",
        "no_multi_domain_target_candidate",
        "non_material_remaining_candidates",
    }:
        return True, "normal_one_click_no_direct_path_from_implausible_seed", family, requested_tier, debug
    if str(stop_reason or "") in {"no_full_coverage_candidate", "no_multi_domain_target_candidate"}:
        return True, "normal_one_click_stopped_outside_practical_neighborhood", family, requested_tier, debug
    return False, "normal_one_click_keep_control", family, requested_tier, debug
