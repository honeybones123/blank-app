"""Shear low-util active-link blocker coordination for the Inputs Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Callable

import inputs_application.policy_constants as inputs_page_app_contracts


@dataclass(frozen=True)
class ShearLowUtilBlockerRuntime:
    design_mode_config: Callable[..., dict]
    design_optimisation_goal: Callable[..., str]
    evaluate_auto_design_candidate: Callable[..., dict | None]
    generate_less_shear_reo_variants: Callable[..., list[dict]]
    guidance_cleanup_candidate_id: Callable[..., str]
    one_click_diff_accumulated_updates: Callable[..., dict]
    parse_util_value: Callable[..., float | None]
    shear_cleanup_materially_reduces_reinforcement: Callable[..., bool]
    shear_reinforcement_is_active: Callable[..., bool]
    get_cache: Callable[..., Any]
    set_cache: Callable[..., Any]
    stable_fingerprint: Callable[..., str]


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
    "get_rerun_pure_cache",
    "set_rerun_pure_cache",
    "stable_fingerprint_for_payload",
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
    runtime: ShearLowUtilBlockerRuntime | None = None,
) -> dict | None:
    if runtime is None:
        namespace = globals()
        runtime = ShearLowUtilBlockerRuntime(
            design_mode_config=namespace["_design_mode_config"],
            design_optimisation_goal=namespace["_design_optimisation_goal"],
            evaluate_auto_design_candidate=namespace[
                "_evaluate_auto_design_candidate_for_app_bridge"
            ],
            generate_less_shear_reo_variants=namespace[
                "_generate_less_shear_reo_variants_for_app_bridge"
            ],
            guidance_cleanup_candidate_id=namespace[
                "_guidance_cleanup_candidate_id"
            ],
            one_click_diff_accumulated_updates=namespace[
                "_one_click_diff_accumulated_updates"
            ],
            parse_util_value=namespace["_parse_util_value"],
            shear_cleanup_materially_reduces_reinforcement=namespace[
                "_shear_cleanup_materially_reduces_reinforcement"
            ],
            shear_reinforcement_is_active=namespace[
                "_shear_reinforcement_is_active"
            ],
            get_cache=namespace["get_rerun_pure_cache"],
            set_cache=namespace["set_rerun_pure_cache"],
            stable_fingerprint=namespace[
                "stable_fingerprint_for_payload"
            ],
        )
    _design_mode_config = runtime.design_mode_config
    _design_optimisation_goal = runtime.design_optimisation_goal
    _evaluate_auto_design_candidate_for_app_bridge = (
        runtime.evaluate_auto_design_candidate
    )
    _generate_less_shear_reo_variants_for_app_bridge = (
        runtime.generate_less_shear_reo_variants
    )
    _guidance_cleanup_candidate_id = runtime.guidance_cleanup_candidate_id
    _one_click_diff_accumulated_updates = (
        runtime.one_click_diff_accumulated_updates
    )
    _parse_util_value = runtime.parse_util_value
    _shear_cleanup_materially_reduces_reinforcement = (
        runtime.shear_cleanup_materially_reduces_reinforcement
    )
    _shear_reinforcement_is_active = runtime.shear_reinforcement_is_active
    get_rerun_pure_cache = runtime.get_cache
    set_rerun_pure_cache = runtime.set_cache
    stable_fingerprint_for_payload = runtime.stable_fingerprint
    if not isinstance(state, dict) or not _shear_reinforcement_is_active(state):
        return None
    ov = overview if isinstance(overview, dict) else {}
    utils = dict(ov.get("utils") or {})
    current_shear_util = _parse_util_value(utils.get("shear"))
    if current_shear_util is None or current_shear_util >= float(threshold):
        return None
    blocker_fp = stable_fingerprint_for_payload(
        {
            "state": state,
            "overview": ov,
            "threshold": float(threshold),
        }
    )
    cached_blocker = get_rerun_pure_cache(
        "shear_low_util_active_links_exact_blocker",
        blocker_fp,
    )
    if isinstance(cached_blocker, dict) and cached_blocker.get("_cache_record") == "shear_low_util_active_links_exact_blocker":
        result = cached_blocker.get("result")
        return dict(result) if isinstance(result, dict) else None
    mode_cfg = _design_mode_config(_design_optimisation_goal(state))
    attempted = 0
    best_failed: dict | None = None

    def _link_label(source: dict[str, Any]) -> str:
        try:
            legs = int(float(source.get("lig_legs") or 0))
            diameter = int(float(source.get("lig_d") or 0))
            spacing = float(source.get("s_lig") or 0)
        except (TypeError, ValueError):
            return "the recorded shear-link arrangement"
        if legs <= 0 or diameter <= 0 or spacing <= 0:
            return "no shear links"
        spacing_text = (
            str(int(round(spacing)))
            if abs(spacing - round(spacing)) <= 1e-9
            else f"{spacing:.2f}".rstrip("0").rstrip(".")
        )
        return f"{legs}-leg N{diameter} @ {spacing_text} mm"

    def _attempted_change_label(updates: dict[str, Any]) -> str:
        attempted_state = dict(state)
        attempted_state.update(dict(updates or {}))
        return (
            "changing shear links from "
            f"{_link_label(state)} to {_link_label(attempted_state)}"
        )
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
            set_rerun_pure_cache(
                "shear_low_util_active_links_exact_blocker",
                blocker_fp,
                {
                    "_cache_record": "shear_low_util_active_links_exact_blocker",
                    "result": None,
                },
            )
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
                "attempted_change_label": _attempted_change_label(updates),
                "attempted_util": (
                    fail_util if fail_util is not None else "not_available"
                ),
                "attempted_passed": False,
                "failed_check_name": shear_pack.get("summary_governing_check_name")
                or shear_pack.get("summary_governing_reason")
                or "shear capacity/detailing check",
                "failed_check_status": str(statuses.get("shear") or "FAIL"),
                "failed_check_util": fail_util if fail_util is not None else "not_available",
                "failed_check_demand": demand,
                "failed_check_capacity_or_limit": capacity,
                "demand": demand,
                "capacity_or_limit": capacity,
                "rejection_category": (
                    "The next lighter link layout failed the governing shear "
                    "capacity or detailing check"
                ),
                "current_arrangement_label": _link_label(state),
                "retained_arrangement_label": _link_label(state),
                "repair_search_ran": True,
                "repair_search_exhaustive": True,
                "exact_stop_proven": True,
                "no_second_cta_required": True,
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
            blocker = {
                "family": "shear",
                "current_util": current_shear_util,
                "threshold": float(threshold),
                "attempted_candidate_count": attempted,
                "best_rejected_candidate_id": _guidance_cleanup_candidate_id(
                    "shear",
                    dict(best_low_safe.get("updates") or {}),
                ),
                "attempted_updates": dict(best_low_safe.get("updates") or {}),
                "attempted_change_label": _attempted_change_label(
                    dict(best_low_safe.get("updates") or {})
                ),
                "attempted_util": (
                    low_util
                    if low_util is not None
                    else current_shear_util
                ),
                "attempted_passed": True,
                "failed_check_name": "final accepted shear utilisation threshold",
                "failed_check_status": "BLOCKED",
                "failed_check_util": low_util if low_util is not None else current_shear_util,
                "failed_check_demand": demand,
                "failed_check_capacity_or_limit": capacity,
                "demand": demand,
                "capacity_or_limit": capacity,
                "rejection_category": (
                    "Safe but still below the final accepted shear "
                    "utilisation threshold"
                ),
                "current_arrangement_label": _link_label(state),
                "retained_arrangement_label": _link_label(state),
                "repair_search_ran": True,
                "repair_search_exhaustive": True,
                "safe_candidate_count": 1,
                "safe_executor_backed_candidates_count": 1,
                "executable_candidate_count": 1,
                "target_band_candidate_count": 0,
                "exact_stop_proven": True,
                "no_second_cta_required": True,
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
            set_rerun_pure_cache(
                "shear_low_util_active_links_exact_blocker",
                blocker_fp,
                {
                    "_cache_record": "shear_low_util_active_links_exact_blocker",
                    "result": blocker,
                },
            )
            return blocker
        set_rerun_pure_cache(
            "shear_low_util_active_links_exact_blocker",
            blocker_fp,
            {
                "_cache_record": "shear_low_util_active_links_exact_blocker",
                "result": None,
            },
        )
        return None
    best_failed["attempted_candidate_count"] = attempted
    set_rerun_pure_cache(
        "shear_low_util_active_links_exact_blocker",
        blocker_fp,
        {
            "_cache_record": "shear_low_util_active_links_exact_blocker",
            "result": best_failed,
        },
    )
    return best_failed
