"""Typed mixed-family width cleanup promotion at the guidance entry boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MixedWidthCleanupPromotionRuntime:
    target_util_min: float
    target_util_max: float
    identify_materially_overprovided_families: Callable[..., Any]
    design_mode_config: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    evaluate_auto_design_candidate: Callable[..., Any]
    overview_required_checks_acceptable: Callable[..., Any]
    parse_util_value: Callable[..., Any]


def promote_shear_fail_bending_overdesign_width_cleanup(
    payload: dict,
    *,
    state: dict,
    runtime: MixedWidthCleanupPromotionRuntime,
) -> dict:
    if not isinstance(payload, dict):
        return payload
    items = list(payload.get("guidance_items") or [])
    if not items or not isinstance(items[0], dict):
        return payload
    primary = dict(items[0])
    button = dict(primary.get("button_contract") or {})
    if str(button.get("family") or "").strip().upper() != "SHEAR_FAIL_GOVERNS":
        return payload
    shear_updates = dict(button.get("updates") or {})
    if not (set(shear_updates) & {"lig_d", "lig_legs", "s_lig"}):
        return payload
    if set(shear_updates) - {"lig_d", "lig_legs", "s_lig"}:
        return payload
    debug = dict(payload.get("debug_trace") or {})

    def skip(reason: str, **extra: Any) -> dict:
        next_payload = dict(payload)
        next_debug = dict(debug)
        next_debug["mixed_width_cleanup_bridge_attempted"] = True
        next_debug["mixed_width_cleanup_bridge_skipped_reason"] = reason
        for key, value in extra.items():
            next_debug[f"mixed_width_cleanup_bridge_{key}"] = value
        next_payload["debug_trace"] = next_debug
        return next_payload

    overview = dict(debug.get("overview") or {})
    statuses = {
        str(key or "").strip().lower(): str(value or "").strip().upper()
        for key, value in dict(overview.get("statuses") or {}).items()
    }
    if statuses.get("shear") != "FAIL" or statuses.get("bending") == "FAIL":
        return skip("not_shear_only_active_failure", statuses=dict(statuses))
    try:
        family_utils, material_families, governing_family = (
            runtime.identify_materially_overprovided_families(overview)
        )
    except Exception:
        family_utils, material_families, governing_family = {}, [], None
    if "bending" not in {
        str(family or "").strip().lower()
        for family in material_families
    }:
        return skip(
            "bending_not_materially_overprovided",
            family_utils=dict(family_utils),
            material_families=list(material_families),
            governing_family=governing_family,
        )
    state_d = dict(state or {})
    try:
        current_width = float(
            state_d.get("b") or state_d.get("bw") or 0.0
        )
    except Exception:
        current_width = 0.0
    if current_width <= 260:
        return skip("current_width_too_low", current_width=current_width)
    mode_config = runtime.design_mode_config(
        runtime.design_optimisation_goal(state_d)
    )
    try:
        target_low = float(
            mode_config.get(
                "target_util_min",
                runtime.target_util_min,
            )
            or runtime.target_util_min
        )
        target_high = float(
            mode_config.get(
                "target_util_max",
                runtime.target_util_max,
            )
            or runtime.target_util_max
        )
    except Exception:
        target_low = float(runtime.target_util_min)
        target_high = float(runtime.target_util_max)
    width_key = "b" if "b" in state_d or "bw" not in state_d else "bw"
    selected_candidate = None
    selected_width = None
    selected_util = None
    for width in range(int(current_width) - 10, 249, -10):
        trial_updates = dict(shear_updates)
        trial_updates[width_key] = float(width)
        try:
            candidate = runtime.evaluate_auto_design_candidate(
                state_d,
                updates=trial_updates,
                source=(
                    "shear_fail_bending_overdesign_width_cleanup_bridge"
                ),
                label=str(
                    primary.get("title_main")
                    or primary.get("title")
                    or "Shear capacity is low"
                ),
                action_type="apply_resolved_candidate",
            )
        except Exception:
            candidate = None
        if not isinstance(candidate, dict):
            continue
        candidate_overview = dict(candidate.get("overview") or {})
        if (
            not runtime.overview_required_checks_acceptable(
                candidate_overview
            )
            or bool(candidate_overview.get("any_fail"))
        ):
            continue
        util = runtime.parse_util_value(
            candidate.get("candidate_post_util")
            or candidate.get("worst_util")
            or candidate_overview.get("worst_util")
            or candidate_overview.get("governing_util")
        )
        if util is None or not (
            target_low <= float(util) <= target_high
        ):
            continue
        selected_candidate = dict(candidate)
        selected_width = float(width)
        selected_util = float(util)
    if (
        not isinstance(selected_candidate, dict)
        or selected_width is None
        or selected_util is None
    ):
        return skip(
            "no_width_cleanup_candidate_passed_preview",
            current_width=current_width,
            target_low=float(target_low),
            target_high=float(target_high),
        )

    family_id = "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
    candidate_id = (
        f"{button.get('candidate_id') or button.get('source_candidate_id') or 'shear_repair'}"
        f"+width_{int(selected_width)}"
    )
    merged_updates = dict(shear_updates)
    merged_updates[width_key] = float(selected_width)
    evidence = dict(
        primary.get("candidate_search_evidence")
        or dict(primary.get("action_payload") or {}).get(
            "candidate_search_evidence"
        )
        or debug.get("candidate_search_evidence")
        or {}
    )
    evidence.update(
        {
            "source": (
                "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS."
                "width_cleanup_bridge"
            ),
            "selected_family_id": family_id,
            "published_family_id": family_id,
            "cta_family_id": family_id,
            "card_family_id": family_id,
            "candidate_family_id": family_id,
            "apply_payload_family_id": family_id,
            "active_failures": ["shear"],
            "family_utils": dict(family_utils),
            "governing_family": governing_family,
            "mandatory_source_family_id": "SHEAR_FAIL_GOVERNS",
            "opportunistic_source_family_id": (
                "BENDING_OVERDESIGN_GOVERNS"
            ),
            "mandatory_source_updates": dict(shear_updates),
            "opportunistic_source_updates": {
                width_key: float(selected_width)
            },
            "selected_candidate_id": candidate_id,
            "selected_candidate_updates": dict(merged_updates),
            "selected_candidate_preview_pass": True,
            "selected_candidate_post_util": float(selected_util),
            "candidate_reaches_target_band": True,
            "safe_executor_backed_candidates_count": 1,
            "executable_repair_candidate_count": 1,
            "safe_repair_candidate_count": 1,
            "mixed_merge_proof": {
                "mandatory_shear_repair_included": True,
                "opportunistic_bending_cleanup_included": True,
                "merged_preview_required_checks_pass": True,
                "merged_preview_util": float(selected_util),
                "target_low": float(target_low),
                "target_high": float(target_high),
            },
        }
    )
    button.update(
        {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": family_id,
            "family_id": family_id,
            "selected_family_id": family_id,
            "published_family_id": family_id,
            "cta_family_id": family_id,
            "apply_payload_family_id": family_id,
            "updates": dict(merged_updates),
            "preview_pass": True,
            "expected_util": float(selected_util),
            "blocking_reason": None,
            "disabled_reason": None,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
        }
    )
    for key in (
        "family",
        "family_id",
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "apply_payload_family_id",
        "candidate_family_id",
        "card_family_id",
    ):
        primary[key] = family_id
    primary["button_contract"] = dict(button)
    primary["candidate_search_evidence"] = dict(evidence)
    primary["candidate_id"] = candidate_id
    primary["source_candidate_id"] = candidate_id
    primary["primary_card_actionable"] = True
    action_payload = dict(primary.get("action_payload") or {})
    action_payload.update(
        {
            "button_contract": dict(button),
            "candidate_search_evidence": dict(evidence),
            "resolved_candidate_updates": dict(merged_updates),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "source_candidate_id": candidate_id,
            "family": family_id,
            "family_id": family_id,
            "selected_family_id": family_id,
            "published_family_id": family_id,
            "cta_family_id": family_id,
            "apply_payload_family_id": family_id,
        }
    )
    primary["action_payload"] = action_payload
    debug.update(
        {
            "primary_item": dict(primary),
            "primary_button_contract": dict(button),
            "button_contract": dict(button),
            "displayed_primary_button_contract": dict(button),
            "candidate_search_evidence": dict(evidence),
            "selected_family_id": family_id,
            "published_family_id": family_id,
            "cta_family_id": family_id,
            "mixed_width_cleanup_bridge_promoted": True,
            "mixed_width_cleanup_bridge_updates": dict(merged_updates),
            "mixed_width_cleanup_bridge_expected_util": float(
                selected_util
            ),
        }
    )
    next_payload = dict(payload)
    next_payload["guidance_items"] = [
        primary,
        *[item for item in items[1:] if isinstance(item, dict)],
    ]
    next_payload["debug_trace"] = debug
    return next_payload


__all__ = [
    "MixedWidthCleanupPromotionRuntime",
    "promote_shear_fail_bending_overdesign_width_cleanup",
]
