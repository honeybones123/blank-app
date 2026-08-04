"""Rescue seed policy and entry decision for one-click auto-design."""

from __future__ import annotations

import math
from collections.abc import Callable


TIER_ORDER = ("medium", "high", "very_high", "extreme")


def _updates(values: tuple[float, float, int, int, int, int, int, int, float]) -> dict:
    b, depth, top_count, top_dia, bottom_count, bottom_dia, lig_d, lig_legs, spacing = values
    return {
        "b": float(b),
        "D": float(depth),
        "top1_layout_mode": "Count",
        "top1_count": int(top_count),
        "db_top_1": int(top_dia),
        "top2_layout_mode": "Count",
        "top2_count": 0,
        "db_top_2": 0,
        "bot1_layout_mode": "Count",
        "bot1_count": int(bottom_count),
        "db_bot_1": int(bottom_dia),
        "bot2_layout_mode": "Count",
        "bot2_count": 0,
        "db_bot_2": 0,
        "lig_d": int(lig_d),
        "lig_legs": int(lig_legs),
        "s_lig": float(spacing),
    }


_SEED_ROWS = {
    "bending": (
        ((350, 600, 2, 16, 4, 24, 12, 2, 150), (250, 400), (0, 400), (1.5, 3.0)),
        ((400, 700, 2, 20, 5, 28, 12, 2, 125), (400, 650), (0, 650), (3.0, 6.0)),
        ((450, 800, 2, 20, 6, 28, 12, 4, 125), (650, 850), (0, 850), (6.0, 10.0)),
        ((500, 900, 2, 24, 6, 32, 16, 4, 100), (850, 1000), (0, 1000), (10.0, None)),
    ),
    "shear": (
        ((350, 600, 2, 16, 4, 24, 12, 4, 125), (0, 400), (250, 400), (1.5, 3.0)),
        ((400, 700, 2, 20, 5, 28, 16, 4, 100), (0, 650), (400, 650), (3.0, 6.0)),
        ((450, 800, 2, 20, 5, 32, 16, 6, 100), (0, 850), (650, 850), (6.0, 10.0)),
        ((500, 900, 2, 24, 6, 32, 20, 6, 75), (0, 1000), (850, 1000), (10.0, None)),
    ),
    "combined": (
        ((400, 650, 2, 20, 5, 24, 12, 4, 125), (300, 450), (250, 400), (1.5, 3.0)),
        ((450, 750, 2, 20, 5, 28, 16, 4, 100), (450, 650), (400, 650), (3.0, 6.0)),
        ((500, 850, 2, 24, 6, 28, 16, 6, 100), (650, 850), (650, 850), (6.0, 10.0)),
        ((550, 950, 2, 24, 6, 32, 20, 6, 75), (850, 1000), (850, 1000), (10.0, None)),
    ),
}


RESCUE_SEED_LIBRARY = {
    family: {
        tier: {
            "key": f"{family}_{tier}",
            "updates": _updates(row[0]),
            "intended_action_range": {
                "Mu": list(row[1]),
                "Vu": list(row[2]),
            },
            "intended_util_range": list(row[3]),
        }
        for tier, row in zip(TIER_ORDER, rows)
    }
    for family, rows in _SEED_ROWS.items()
}


def rescue_mode_should_enter(
    *,
    state: dict,
    init_eval: dict | None,
    final_eval: dict | None,
    final_pass: bool,
    final_updates: dict,
    stop_reason: str,
    mode_config: dict,
    candidate_objective_util: Callable[[dict], float],
    domain_score: Callable[..., dict],
    build_design_actions_context: Callable[[dict], dict],
) -> tuple[bool, str | None, str | None, str | None, dict]:
    section_kind = str(
        state.get("section_shape")
        or state.get("section_type")
        or "RECT"
    ).strip().upper()
    initial_all_pass = bool(
        ((init_eval or {}).get("overview") or {}).get("all_key_pass")
    )
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

    bending = domain_score(init_eval, "bending", mode_config)
    shear = domain_score(init_eval, "shear", mode_config)
    bending_fail = not bool(bending.get("pass"))
    shear_fail = not bool(shear.get("pass"))
    try:
        bending_util = float(bending.get("util"))
        shear_util = float(shear.get("util"))
    except (TypeError, ValueError):
        bending_util = shear_util = None
    both_fail = bool(
        bending_fail
        and shear_fail
        and bending_util is not None
        and shear_util is not None
        and math.isfinite(bending_util)
        and math.isfinite(shear_util)
        and bending_util >= 1.10
        and shear_util >= 1.10
    )
    family = (
        "combined"
        if both_fail
        else "bending"
        if bending_fail and not shear_fail
        else "shear"
        if shear_fail and not bending_fail
        else None
    )
    debug["family"] = family
    if not family:
        return False, "family_not_rescue_eligible", None, None, debug

    try:
        actions = dict(
            build_design_actions_context(state).get("actions") or {}
        )
        action_value = abs(float(actions.get("Mu", 0.0) or 0.0))
        if family == "shear":
            action_value = abs(float(actions.get("Vu", 0.0) or 0.0))
        elif family == "combined":
            action_value = max(
                abs(float(actions.get("Mu", 0.0) or 0.0)),
                abs(float(actions.get("Vu", 0.0) or 0.0)),
            )
    except Exception:
        action_value = 0.0
    action_tier = (
        "extreme" if action_value >= 850
        else "very_high" if action_value >= 650
        else "high" if action_value >= 400
        else "medium" if action_value >= 250
        else None
    )
    initial_util = candidate_objective_util(init_eval or {})
    try:
        initial_u = float(initial_util)
    except (TypeError, ValueError):
        initial_u = None
    util_tier = (
        "extreme" if initial_u is not None and math.isfinite(initial_u) and initial_u > 10
        else "very_high" if initial_u is not None and math.isfinite(initial_u) and initial_u >= 6
        else "high" if initial_u is not None and math.isfinite(initial_u) and initial_u >= 3
        else "medium" if initial_u is not None and math.isfinite(initial_u) and initial_u >= 1.5
        else None
    )
    tiers = [tier for tier in (action_tier, util_tier) if tier in TIER_ORDER]
    requested_tier = (
        TIER_ORDER[max(TIER_ORDER.index(tier) for tier in tiers)]
        if tiers else None
    )
    debug["requested_tier"] = requested_tier
    if requested_tier is None:
        return False, "tier_not_rescue_eligible", family, None, debug
    seed = RESCUE_SEED_LIBRARY[family][requested_tier]["updates"]
    plausible = bool(
        float(state.get("b", 0.0) or 0.0) >= 0.85 * float(seed["b"])
        and float(state.get("D", 0.0) or 0.0) >= 0.85 * float(seed["D"])
    )
    debug["current_beam_plausible"] = plausible
    if plausible:
        return False, "current_beam_already_plausible", family, requested_tier, debug
    if str(stop_reason or "") in {"already_in_band", "reached_target_band"}:
        return False, "normal_one_click_retained_control", family, requested_tier, debug
    debug["initial_objective_util"] = initial_u
    severe_fail = bool(
        initial_u is not None and math.isfinite(initial_u) and initial_u >= 3.0
    )
    try:
        final_u = float(candidate_objective_util(final_eval or {}))
    except (TypeError, ValueError):
        final_u = None
    debug["final_objective_util"] = final_u
    debug["severe_fail"] = severe_fail
    debug["both_fail_meaningfully"] = both_fail
    if not severe_fail and not both_fail:
        return False, "severity_below_rescue_threshold", family, requested_tier, debug
    reason = str(stop_reason or "")
    if final_updates and not final_pass and final_u is not None and math.isfinite(final_u) and final_u > 1.10 and reason == "best_available_out_of_band_candidate":
        return True, "normal_one_click_best_available_still_far_from_band", family, requested_tier, debug
    if not final_updates and reason in {
        "no_actionable_candidates",
        "no_actionable_candidates_after_full_tightening_search",
        "no_improving_candidate",
        "no_full_coverage_candidate",
        "no_multi_domain_target_candidate",
        "non_material_remaining_candidates",
    }:
        return True, "normal_one_click_no_direct_path_from_implausible_seed", family, requested_tier, debug
    if reason in {"no_full_coverage_candidate", "no_multi_domain_target_candidate"}:
        return True, "normal_one_click_stopped_outside_practical_neighborhood", family, requested_tier, debug
    return False, "normal_one_click_keep_control", family, requested_tier, debug


__all__ = ["RESCUE_SEED_LIBRARY", "rescue_mode_should_enter"]
