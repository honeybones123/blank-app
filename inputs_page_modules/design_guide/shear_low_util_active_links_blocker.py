"""Shear low-util active-link blocker coordination for the Inputs Design Guide."""

from __future__ import annotations

from typing import Any

import inputs_page_app_contracts


_SHEAR_LOW_UTIL_ACTIVE_LINKS_BLOCKER_DEPENDENCIES: tuple[str, ...] = (
    "_design_mode_config",
    "_design_optimisation_goal",
    "_evaluate_auto_design_candidate_for_app_bridge",
    "_generate_less_shear_reo_variants_for_app_bridge",
    "_guidance_cleanup_candidate_id",
    "_one_click_diff_accumulated_updates",
    "_parse_util_value",
    "_shear_cleanup_materially_reduces_reinforcement",
    "_shear_reinforcement_is_active",
)


def bind_shear_low_util_active_links_blocker_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SHEAR_LOW_UTIL_ACTIVE_LINKS_BLOCKER_DEPENDENCIES
            if name in namespace
        }
    )


def _shear_low_util_active_links_exact_blocker(
    state: dict | None,
    overview: dict | None,
    *,
    threshold: float = inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
) -> dict | None:
    if not isinstance(state, dict) or not _shear_reinforcement_is_active(state):
        return None
    ov = overview if isinstance(overview, dict) else {}
    utils = dict(ov.get("utils") or {})
    current_shear_util = _parse_util_value(utils.get("shear"))
    if current_shear_util is None or current_shear_util >= float(threshold):
        return None
    mode_cfg = _design_mode_config(_design_optimisation_goal(state))
    attempted = 0
    best_failed: dict | None = None
    try:
        variants = list(
            _generate_less_shear_reo_variants_for_app_bridge({"state": dict(state)}, mode_cfg) or []
        )
    except Exception:
        variants = []
    best_low_safe: dict | None = None
    for variant_state in variants[:24]:
        updates = _one_click_diff_accumulated_updates(state, variant_state)
        if not updates:
            continue
        trial_state = dict(state)
        trial_state.update(updates)
        if not _shear_cleanup_materially_reduces_reinforcement(state, trial_state):
            continue
        attempted += 1
        try:
            candidate = _evaluate_auto_design_candidate_for_app_bridge(
                state,
                updates=updates,
                source="accepted_green_shear_low_util_blocker_probe",
                label="Shear low-util blocker probe",
                action_type="apply_shear_recommendation",
            )
        except Exception:
            candidate = None
        if not isinstance(candidate, dict):
            continue
        cand_ov = dict(candidate.get("overview") or {})
        cand_utils = dict(cand_ov.get("utils") or {})
        cand_shear_util = _parse_util_value(cand_utils.get("shear"))
        if (
            bool(cand_ov.get("all_key_pass"))
            and not bool(cand_ov.get("any_fail"))
            and cand_shear_util is not None
            and cand_shear_util >= float(threshold)
        ):
            return None
        if (
            bool(cand_ov.get("all_key_pass"))
            and not bool(cand_ov.get("any_fail"))
            and cand_shear_util is not None
            and cand_shear_util < float(threshold)
        ):
            low_safe = {
                "updates": dict(updates),
                "candidate": dict(candidate),
                "overview": dict(cand_ov),
                "shear_util": float(cand_shear_util),
                "attempted": attempted,
            }
            if best_low_safe is None:
                best_low_safe = low_safe
            else:
                prev_util = _parse_util_value(best_low_safe.get("shear_util"))
                if prev_util is None or float(cand_shear_util) > float(prev_util):
                    best_low_safe = low_safe
        statuses = dict(cand_ov.get("statuses") or {})
        shear_failed = str(statuses.get("shear") or "").strip().upper() == "FAIL"
        if shear_failed or bool(cand_ov.get("any_fail")):
            packs = dict(cand_ov.get("packs") or {})
            shear_pack = dict(packs.get("shear") or {})
            fail_util = cand_shear_util
            if fail_util is None:
                fail_util = _parse_util_value(shear_pack.get("summary_util"))
            demand = (
                shear_pack.get("summary_governing_demand_kN")
                or shear_pack.get("summary_Veq_kN")
                or shear_pack.get("summary_demand_kN")
                or ov.get("Vu_star")
                or "unknown"
            )
            capacity = (
                shear_pack.get("summary_governing_capacity_kN")
                or shear_pack.get("summary_phiVu_kN")
                or shear_pack.get("summary_display_capacity")
                or "unknown"
            )
            failed = {
                "family": "shear",
                "current_util": current_shear_util,
                "threshold": float(threshold),
                "attempted_candidate_count": attempted,
                "best_rejected_candidate_id": _guidance_cleanup_candidate_id("shear", updates),
                "attempted_updates": dict(updates),
                "failed_check_name": shear_pack.get("summary_governing_check_name")
                or shear_pack.get("summary_governing_reason")
                or "shear capacity/detailing check",
                "failed_check_status": str(statuses.get("shear") or "FAIL"),
                "failed_check_util": fail_util if fail_util is not None else "not_available",
                "failed_check_demand": demand,
                "failed_check_capacity_or_limit": capacity,
                "demand": demand,
                "capacity_or_limit": capacity,
                "why_reduction_would_hurt_other_design_elements": (
                    "The active shear links were reduced in a preview candidate, but the lighter layout "
                    "failed the governing shear capacity or detailing check; further shear cleanup would "
                    "reduce link area/spacing reserve and make the shear design unacceptable."
                ),
                "reason": (
                    "Further shear-link cleanup is blocked because the next lighter link layout fails "
                    "the governing shear capacity or detailing check."
                ),
            }
            if best_failed is None:
                best_failed = failed
            else:
                prev_util = _parse_util_value(best_failed.get("failed_check_util"))
                if fail_util is not None and (
                    prev_util is None
                    or abs(float(fail_util) - 1.0) < abs(float(prev_util) - 1.0)
                ):
                    best_failed = failed
    if best_failed is None:
        if best_low_safe is not None:
            low_ov = dict(best_low_safe.get("overview") or {})
            packs = dict(low_ov.get("packs") or {})
            shear_pack = dict(packs.get("shear") or {})
            low_util = _parse_util_value(best_low_safe.get("shear_util"))
            demand = (
                shear_pack.get("summary_governing_demand_kN")
                or shear_pack.get("summary_Veq_kN")
                or shear_pack.get("summary_demand_kN")
                or ov.get("Vu_star")
                or "unknown"
            )
            capacity = (
                shear_pack.get("summary_governing_capacity_kN")
                or shear_pack.get("summary_phiVu_kN")
                or shear_pack.get("summary_display_capacity")
                or "minimum constructible/no-link shear floor"
            )
            return {
                "family": "shear",
                "current_util": current_shear_util,
                "threshold": float(threshold),
                "attempted_candidate_count": attempted,
                "best_rejected_candidate_id": _guidance_cleanup_candidate_id(
                    "shear",
                    dict(best_low_safe.get("updates") or {}),
                ),
                "attempted_updates": dict(best_low_safe.get("updates") or {}),
                "failed_check_name": "final accepted shear utilisation threshold",
                "failed_check_status": "BLOCKED",
                "failed_check_util": low_util if low_util is not None else current_shear_util,
                "failed_check_demand": demand,
                "failed_check_capacity_or_limit": capacity,
                "demand": demand,
                "capacity_or_limit": capacity,
                "why_reduction_would_hurt_other_design_elements": (
                    "The lighter shear-link layouts were previewed and remained safe, but the shear demand is too low "
                    "for those layouts to raise shear utilisation to the final 0.85 threshold; further reserve reduction "
                    "would require changing section geometry or bending reinforcement and would affect bending, "
                    "serviceability, detailing, or concrete shear capacity."
                ),
                "reason": (
                    "Further shear-link cleanup cannot reach the final 0.85 utilisation threshold for this low shear demand "
                    "without changing other design families."
                ),
            }
        return None
    best_failed["attempted_candidate_count"] = attempted
    return best_failed
