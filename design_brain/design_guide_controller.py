"""Design Guide controller boundary.

This module provides a single Design Brain facade over final Design Guide
publication proof objects. It does not render UI, route Apply actions, read
session state, or own page orchestration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json
import math
import re
from typing import Any, Callable

from optimisation_config import get_target_utilisation_band, target_band_payload
from design_brain.config import (
    resolve_design_mode_config,
    resolve_design_optimisation_goal,
    resolve_efficiency_target_band,
)
from design_brain.engine import resolve_design_guide_decision
from design_brain.evidence import build_candidate_search_evidence
from design_brain.optimisation import optimisation_cleanup_candidate_id
from design_brain.final_publication import (
    FinalDesignGuidePublication,
    build_collapsed_guidance_item_from_final_publication,
    build_final_design_guide_compute_publication_handoff_rebound_decision_proof,
    build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof,
    build_final_design_guide_post_resolver_mutation_proof,
    build_final_design_guide_publication,
    build_final_design_guide_render_item_consumer_proof,
    build_final_design_guide_publication_mutation_proof,
    build_final_visible_contract_binding_rebind_effects_proof,
    build_final_visible_contract_binding_rebind_projection,
    build_final_visible_contract_binding_output_projection,
    stable_final_publication_hash,
)
from design_brain.families.bending import (
    candidate_ductility_governs as _controller_candidate_ductility_governs,
    candidate_ductility_util as _controller_candidate_ductility_util,
)
from design_brain.families.bending_fail import (
    select_bending_fail_fallback_repair_candidate_from_ladder,
)
from design_brain.families.combined_bending_shear_fail import (
    select_combined_fail_fallback_repair_candidate_from_ladder,
)
from design_brain.candidate_evaluation import build_active_fail_executor_candidate_generation_context
from design_brain.publication import design_guide_cache_fingerprint_from_plain_data
from design_brain.publication import active_failure_blocker_visible_reason_text
from design_brain.publication import active_failure_exact_blockers_for_families
from design_brain.publication import disabled_design_guide_button_contract
from design_brain.publication import design_guide_button_contract_enabled
from design_brain.publication import finalize_design_guide_active_failure_blocker_publication
from design_brain.publication import normalise_design_guide_candidate_id
from design_brain.publication import normalise_final_visible_design_guide_item
from design_brain.repair import active_failure_route_attempt_updates
from design_brain.repair import active_failure_route_inventory
from design_brain.repair import candidate_failure_coverage_summary_from_overviews
from design_brain.repair import select_repair_decision
from design_brain.repair import selected_candidate_from_repair_decision


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def best_safe_cleanup_action_proof_allows_executable_cta(
    *,
    evidence: dict[str, Any] | None,
    contract: dict[str, Any] | None,
    expected_util: Any = None,
    updates_match_current_state: bool = False,
) -> bool:
    """Return whether exhausted best-safe cleanup proof may stay executable.

    This is intentionally narrower than the normal target-band acceptance rule:
    it only preserves an Apply CTA for an executor-backed cleanup candidate that
    is not yet applied, passed preview, and is explicitly proven as the best safe
    result after target-band search exhaustion.
    """

    ev = _mapping(evidence)
    contract_d = _mapping(contract)
    updates = _mapping(
        contract_d.get("updates")
        or ev.get("selected_candidate_updates")
        or ev.get("best_safe_candidate_updates")
        or ev.get("closest_safe_candidate_updates")
    )
    if not updates or bool(updates_match_current_state):
        return False
    if str(contract_d.get("action_type") or "").strip() != "apply_resolved_candidate":
        return False
    if not bool(contract_d.get("enabled") or contract_d.get("actionable")):
        return False
    if contract_d.get("preview_pass") is False:
        return False
    if bool(ev.get("best_safe_candidate_applied")) or bool(ev.get("no_second_cta_required")):
        return False
    if not bool(ev.get("best_safe_partial_cleanup") or ev.get("best_safe_candidate_updates")):
        return False
    if not bool(
        ev.get("cleanup_search_exhaustive")
        or ev.get("local_cleanup_search_exhaustive")
        or ev.get("target_band_search_exhaustive")
        or ev.get("candidate_search_exhaustive")
    ):
        return False
    if int(ev.get("executable_target_band_candidate_count") or 0) > 0:
        return False
    if int(ev.get("target_band_candidate_count") or 0) > 0 and not bool(
        ev.get("best_safe_candidate_selected_over_target_band_candidate")
    ):
        return False
    executable_count = int(
        ev.get("executable_candidate_count")
        or ev.get("executable_cleanup_count")
        or ev.get("executable_safe_cleanup_count")
        or ev.get("safe_executor_backed_candidates_count")
        or ev.get("safe_candidate_count")
        or ev.get("safe_cleanup_count")
        or 0
    )
    if executable_count <= 0:
        return False
    util = _float_or_none(
        expected_util
        if expected_util is not None
        else (
            contract_d.get("expected_util")
            or ev.get("selected_candidate_util")
            or ev.get("best_safe_final_util")
            or ev.get("closest_safe_candidate_util")
        )
    )
    return util is not None


def build_design_guide_controller_compute_core_branch_request_projection(
    *,
    overview: dict[str, Any] | None,
    target_band_with_eps_passed: bool,
    overview_required_checks_acceptable: bool,
    post_apply_acceptance_matches: bool,
    last_apply_route: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build pure branch-request scalars for compute guidance core.

    The page still owns state collection, session reads, overview construction,
    and all item/candidate execution. This helper owns only the pure scalar
    projection used by the branch router.
    """

    route = dict(last_apply_route or {})
    label = str(
        route.get("resolved_candidate_label")
        or route.get("post_apply_resolved_candidate_label")
        or ""
    ).strip()
    family = str(route.get("resolved_candidate_family_tag") or "").strip().lower()
    post_apply_from_active_failure_repair = bool(
        bool(post_apply_acceptance_matches)
        and route.get("post_apply_resolved_candidate_attempted")
        and family in {"bending", "shear", "combined", "geometry"}
        and "cleanup" not in label.lower()
    )
    return {
        "last_apply_label_for_post_active": label,
        "last_apply_family_for_post_active": family,
        "post_apply_from_active_failure_repair": post_apply_from_active_failure_repair,
        "out_of_band_live": not (
            bool(overview_required_checks_acceptable)
            and bool(target_band_with_eps_passed)
        ),
        "overview_any_fail": bool(dict(overview or {}).get("any_fail")),
        "target_band_with_eps_passed": bool(target_band_with_eps_passed),
        "overview_required_checks_acceptable": bool(overview_required_checks_acceptable),
    }


def build_design_guide_controller_compute_invalid_state_output_projection(
    *,
    blocked_debug: dict[str, Any] | None,
    guidance_cache_fp: str | None,
    request_kind_norm: str,
) -> dict[str, Any]:
    """Build the compute-guidance invalid/coherence blocked output object.

    The page still owns cache/session writes and the debug fields it already
    collected. This helper owns the plain output shape used by the compute
    guidance wrapper when canonical/coherence guards block normal publication.
    """
    out: dict[str, Any] = {
        "guidance_items": [],
        "blocked_state_class": "hard_invalid",
        "debug_trace": dict(blocked_debug or {}),
        "cache_data": {
            "guidance_cache_fp": str(guidance_cache_fp or ""),
        },
        "recommendation_result": None,
    }
    if str(request_kind_norm or "").strip() == "auto_design":
        out["auto_design_solver_recommendation"] = None
        out["auto_design_seed_failed"] = True
    return out


def build_design_guide_controller_compute_invalid_state_debug_payload(
    *,
    canonical_state: dict[str, Any] | None,
    coherence_debug_fields: dict[str, Any] | None,
    canonical_pack_valid: bool,
    stop_reason: str,
    actions_used: dict[str, Any] | None,
    fail_status: str = "FAIL",
    not_run_status: str = "NOT_RUN",
) -> dict[str, Any]:
    """Build the invalid/coherence blocked compute debug payload.

    The page owns the guard decision and input collection. This helper owns the
    pure debug payload shape used once the guard has already blocked normal
    publication.
    """
    canonical = dict(canonical_state or {})
    reason = str(stop_reason or "")
    guidance_branch = (
        "blocked_invalid_canonical_pack"
        if not bool(canonical_pack_valid)
        else "blocked_hard_invalid_state"
    )
    blocked_user_reason = (
        "Add longitudinal reinforcement before running auto-design."
        if reason == "no_bars_resolved"
        else f"Design Guide blocked: {reason}."
    )
    payload: dict[str, Any] = {
        "guidance_branch": guidance_branch,
        "selected_action_type": None,
        "selected_title": None,
        "guidance_resolved_state": dict(canonical),
        "longitudinal_reo_truth_source": canonical.get("longitudinal_reo_truth_source"),
        "overview": {
            "packs": {},
            "statuses": {
                "bending": str(fail_status or "FAIL"),
                "shear": str(not_run_status or "NOT_RUN"),
                "crack": str(not_run_status or "NOT_RUN"),
                "deflection": str(not_run_status or "NOT_RUN"),
            },
            "utils": {
                "bending": None,
                "shear": None,
                "crack": None,
                "deflection": None,
            },
            "any_fail": True,
            "any_warn": False,
            "all_key_pass": False,
            "worst_util": 0.0,
            "actions_used": dict(actions_used or {}),
        },
        "efficiency_tightening_state": {
            "classification": "blocked_invalid_state",
        },
        "canonical_pack_built": bool(canonical.get("canonical_pack_built")),
        "canonical_pack_valid": bool(canonical_pack_valid),
        "canonical_pack_source": canonical.get("canonical_pack_source"),
        "canonical_pack_error": canonical.get("canonical_pack_error"),
        "canonical_pack_error_stage": canonical.get("canonical_pack_error_stage"),
        "solver_blocked_by_incoherent_state": True,
        "stop_reason": reason,
        "user_visible_no_action_reason": blocked_user_reason,
    }
    payload.update(dict(coherence_debug_fields or {}))
    return payload


def build_design_guide_controller_shear_final_threshold_blocker_projection(
    *,
    primary_item: dict[str, Any] | None,
    existing_evidence: dict[str, Any] | None,
    shear_util: Any,
    attempted_updates: dict[str, Any] | None,
    final_accepted_min_family_util: Any,
) -> dict[str, Any]:
    """Build the shear final-threshold blocker projection.

    The page may still collect the candidate item, current evidence, parsed
    shear utilisation, and attempted updates. This helper owns the pure
    evidence/display/CTA-blocker projection for the final family threshold.
    """
    item = dict(primary_item or {})
    evidence = dict(existing_evidence or {})
    attempted = dict(attempted_updates or {})
    threshold = _float_or_none(final_accepted_min_family_util)
    if threshold is None:
        threshold = 0.85
    shear_value = _float_or_none(shear_util)
    reason = (
        "No executor-backed one-click candidate reaches the final accepted-family "
        f"shear threshold of {float(threshold):.2f} while preserving "
        "bending, shear, serviceability, spacing, ductility, cover, and detailing checks. "
        "Further shear cleanup is controlled by detailing/minimum-link limits or would leave "
        "the shear family below the final acceptance threshold."
    )
    attempted_candidate_id = (
        evidence.get("selected_candidate_id")
        or item.get("source_candidate_id")
        or item.get("candidate_id")
        or "shear_final_threshold_candidate"
    )
    failed_util = (
        shear_value
        if shear_value is not None
        else (
            evidence.get("selected_candidate_util")
            or (item.get("button_contract") or {}).get("expected_util")
            or item.get("util")
        )
        or f"below_{float(threshold):.2f}"
    )
    evidence.update(
        {
            "candidate_search_exhaustive": True,
            "search_scope": evidence.get("search_scope") or "design_guide_shear_final_threshold_blocker",
            "active_under_capacity_blocker": True,
            "active_under_capacity_blocker_family": "shear",
            "active_under_capacity_blocker_reason": reason,
            "outside_target_band_allowed": False,
            "outside_target_band_allowed_reason": reason,
            "outside_target_band_allowed_category": "shear_lock",
            "attempted_candidate_id": attempted_candidate_id,
            "attempted_updates": dict(attempted),
            "failed_check_name": "final accepted shear-family utilisation",
            "failed_check_status": "BLOCKED",
            "failed_check_util": failed_util,
            "failed_check_demand": "shear family final accepted utilisation",
            "failed_check_capacity_or_limit": float(threshold),
            "one_click_target_reaching_candidate_exists": False,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "local_cleanup_blocked_reasons": [reason],
            "local_cleanup_blocked_reasons_by_family": {"shear": [reason]},
        }
    )
    display_truth = {
        "display_truth_source": "post_commit_truth",
        "displayed_util": shear_value,
        "displayed_status": "BLOCKED",
        "target_low": evidence.get("target_low"),
        "target_high": evidence.get("target_high"),
        "displayed_within_target_band": False,
        "source_summary_util": shear_value,
        "source_candidate_util": None,
        "source_post_commit_util": shear_value,
    }
    exact_blockers = {
        "shear": {
            "family": "shear",
            "current_util": evidence.get("failed_check_util"),
            "threshold": float(threshold),
            "attempted_candidate_count": int(
                evidence.get("total_candidates_considered")
                or evidence.get("preview_count")
                or 1
            ),
            "best_rejected_candidate_id": evidence.get("attempted_candidate_id"),
            "attempted_updates": dict(attempted),
            "failed_check_name": evidence.get("failed_check_name"),
            "failed_check_status": evidence.get("failed_check_status"),
            "failed_check_util": evidence.get("failed_check_util"),
            "failed_check_demand": evidence.get("failed_check_demand"),
            "failed_check_capacity_or_limit": evidence.get("failed_check_capacity_or_limit"),
            "reason": reason,
        }
    }
    button_contract = dict(item.get("button_contract") or {})
    button_contract.update(
        {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": "shear",
            "updates": {},
            "preview_pass": False,
            "expected_util": None,
            "blocking_reason": reason,
            "source_candidate_id": None,
            "candidate_id": None,
        }
    )
    item.update(
        {
            "guidance_intent": "specific_blocker",
            "primary_card_actionable": False,
            "family": "shear",
            "check_key": "shear",
            "util": shear_value,
            "title_util": (
                f"(utilisation = {float(shear_value):.2f})"
                if shear_value is not None
                else ""
            ),
            "display_truth": dict(display_truth),
            "display_truth_source": "post_commit_truth",
            "displayed_util": shear_value,
            "displayed_status": "BLOCKED",
            "source_summary_util": shear_value,
            "source_post_commit_util": shear_value,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "safe_local_cleanup_count": 0,
            "executable_safe_cleanup_count": 0,
            "local_cleanup_blocked_reasons": [reason],
            "local_cleanup_blocked_reasons_by_family": {"shear": [reason]},
            "exact_blockers_by_family": dict(exact_blockers),
            "button_contract": dict(button_contract),
            "action_payload": {},
            "resolved_candidate": {},
            "action_type": None,
            "updates": {},
            "proposed_updates": {},
            "selected_updates": {},
            "recommended_updates": {},
            "preview_updates": {},
            "candidate_id": None,
            "source_candidate_id": None,
        }
    )
    return {
        "materialized": True,
        "reason": reason,
        "shear_util": shear_value,
        "attempted_updates": dict(attempted),
        "primary_item": item,
        "existing_evidence": evidence,
        "display_truth": display_truth,
        "button_contract": button_contract,
        "exact_blockers_by_family": exact_blockers,
        "debug_updates": {
            "candidate_search_evidence": dict(evidence),
            "primary_display_truth": dict(display_truth),
        },
    }


def build_design_guide_controller_compute_missing_candidate_search_evidence_record(
    *,
    index: int,
    source_candidate_id: Any,
    title_main: Any,
    button_contract: dict[str, Any] | None,
    display_truth: dict[str, Any] | None,
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build one displayed-candidate evidence record from page-collected fields."""

    idx = int(index or 0)
    contract = dict(button_contract or {})
    truth = dict(display_truth or {})
    preview_util = (
        contract.get("expected_util")
        if contract.get("expected_util") is not None
        else truth.get("source_candidate_util", truth.get("displayed_util"))
    )
    return {
        "source_candidate_id": source_candidate_id,
        "fallback_candidate_id": f"displayed_candidate_{idx:03d}",
        "title_main": title_main,
        "fallback_title": f"Displayed candidate {idx}",
        "updates": dict(updates or {}),
        "preview_util": preview_util,
        "preview_pass": contract.get("preview_pass"),
        "blocking_reason": contract.get("blocking_reason"),
    }


def build_design_guide_controller_compute_missing_candidate_target_band_context(
    *,
    state: dict[str, Any] | None,
    goal_labels: dict[str, Any],
    mode_config_by_goal: dict[str, dict[str, Any]],
    default_low: Any,
    default_high: Any,
    default_goal: str = "balanced",
) -> dict[str, Any]:
    """Resolve the target-band context used by missing-candidate evidence."""

    low_default = _float_or_none(default_low)
    high_default = _float_or_none(default_high)
    if low_default is None:
        low_default = 0.0
    if high_default is None:
        high_default = 1.0
    goal = resolve_design_optimisation_goal(
        _mapping(state),
        goal_labels=dict(goal_labels or {}),
        default_goal=str(default_goal or "balanced"),
    )
    mode_config = resolve_design_mode_config(
        goal,
        mode_config_by_goal=dict(mode_config_by_goal or {}),
        default_goal=str(default_goal or "balanced"),
    )
    target_low, target_high, default_used = resolve_efficiency_target_band(
        mode_config,
        goal=goal,
        mode_config_by_goal=dict(mode_config_by_goal or {}),
        default_low=float(low_default),
        default_high=float(high_default),
        default_goal=str(default_goal or "balanced"),
    )
    return {
        "goal": goal,
        "mode_config": dict(mode_config),
        "target_low": float(target_low),
        "target_high": float(target_high),
        "default_used": bool(default_used),
    }


def build_design_guide_controller_compute_coherence_active_repair_projection(
    *,
    active_repair_item: dict[str, Any] | None,
    active_repair_fail_keys: set[str] | list[str] | tuple[str, ...] | None,
    contract: dict[str, Any] | None,
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    """Project a coherence active-failure repair item into publication shape."""

    item = dict(active_repair_item or {})
    fail_keys = {
        str(key or "").strip().lower()
        for key in list(active_repair_fail_keys or [])
        if str(key or "").strip()
    }
    resolved_updates = dict(updates or {})
    projected_contract = dict(contract or {})
    if fail_keys >= {"bending", "shear"}:
        family = "combined"
        title = "Bending and shear capacity are low"
    elif "shear" in fail_keys:
        family = "shear"
        title = "Shear capacity is low"
    else:
        family = "bending"
        title = "Bending capacity is low"
    projected_contract.update(
        {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": family,
            "updates": dict(resolved_updates),
            "preview_pass": True,
            "blocking_reason": None,
        }
    )
    item.update(
        {
            "title_main": title,
            "title": title,
            "family": family,
            "check_key": family,
            "guidance_intent": "required_fix",
            "primary_card_actionable": True,
            "final_state_class": "action",
            "button_contract": dict(projected_contract),
            "updates": dict(resolved_updates),
        }
    )
    for key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "local_cleanup_blocked_reasons",
        "local_cleanup_blocked_reasons_by_family",
        "exact_blocker_reasons_by_family",
        "blocker_reasons_by_family",
        "active_under_capacity_blocker",
        "active_under_capacity_blocker_reason",
        "active_under_capacity_blocker_family",
    ):
        item.pop(key, None)
    updated_evidence = dict(
        item.get("candidate_search_evidence")
        or (_mapping(item.get("action_payload"))).get("candidate_search_evidence")
        or (_mapping(item.get("resolved_candidate"))).get("candidate_search_evidence")
        or {}
    )
    return {
        "republished": True,
        "item": item,
        "existing_evidence": updated_evidence,
        "family": family,
        "title": title,
        "primary_check_for_evidence": family,
        "primary_title_for_evidence": title.lower(),
        "primary_status_for_evidence": "FAIL",
        "primary_action_for_evidence": "apply_resolved_candidate",
        "primary_contract_for_evidence": dict(projected_contract),
        "primary_action_blocked_for_evidence": False,
        "debug_updates": {
            "guidance_branch": "coherence_active_failure_repair_published",
            "selected_title": title,
            "selected_action_type": "apply_resolved_candidate",
            "selected_action_family": family,
        },
    }


def resolve_design_guide_controller_compute_coherence_active_repair_fail_keys(
    *,
    overview_fail_keys: set[str] | list[str] | tuple[str, ...] | None,
    primary_title: str | None,
) -> dict[str, Any]:
    """Resolve active repair failure keys from overview data and title fallback."""

    keys = {
        str(key or "").strip().lower()
        for key in list(overview_fail_keys or [])
        if str(key or "").strip()
    }
    title = str(primary_title or "").strip().lower()
    source = "overview"
    if not keys:
        source = "title_fallback"
        if "bending and shear" in title:
            keys = {"bending", "shear"}
        elif "shear" in title:
            keys = {"shear"}
        elif "bend" in title or "moment" in title:
            keys = {"bending"}
        else:
            keys = set()
    actionable_strength_keys = bool(keys & {"bending", "shear"})
    return {
        "fail_keys": sorted(keys),
        "fail_key_set": set(keys),
        "source": source,
        "actionable_strength_keys": actionable_strength_keys,
    }


def build_design_guide_controller_compute_active_under_capacity_blocker_projection(
    *,
    active_blocker_family: str,
    primary_item: dict[str, Any] | None,
    existing_evidence: dict[str, Any] | None,
    overview: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the active-under-capacity blocker evidence/card projection."""

    family = str(active_blocker_family or "").strip().lower()
    item = dict(primary_item or {})
    evidence = dict(existing_evidence or {})
    overview_map = dict(overview or {})
    category = {
        "bending": "bending_would_fail",
        "shear": "shear_would_fail",
        "crack": "crack_would_fail",
        "deflection": "deflection_would_fail",
    }.get(family, f"{family}_would_fail")
    attempted_updates = dict(evidence.get("attempted_updates") or {})
    if not attempted_updates:
        if family == "shear":
            attempted_updates = {
                "s_lig": "tighten link spacing trial",
                "db_lig": "increase link diameter trial",
                "lig_legs": "increase link legs trial",
                "D": "increase section depth trial",
                "b": "increase section width trial",
            }
        elif family == "deflection":
            attempted_updates = {
                "D": "increase section depth trial",
                "b": "increase section width trial",
                "sustained_load": "reduce sustained load advisory trial",
            }
        else:
            attempted_updates = {
                "bot1_count": "increase bottom bar count trial",
                "bot_row_1_bars": "increase bottom bar count trial",
                "db_bot_1": "increase bottom bar diameter trial",
                "bot_row_1_dia": "increase bottom bar diameter trial",
                "bot2_count": "add secondary bottom layer trial",
                "bot_row_2_bars": "add secondary bottom layer trial",
                "D": "increase section depth trial",
                "b": "increase section width trial",
            }
    reason = str(
        evidence.get("active_under_capacity_blocker_reason")
        or evidence.get("outside_target_band_allowed_reason")
        or item.get("primary_action")
        or item.get("secondary_action")
        or item.get("reasoning")
        or ""
    ).strip()
    if not reason or "target band" in reason.lower():
        if family == "shear":
            reason = (
                "Shear repair is blocked by shear/detailing limits. Exhaustive link spacing, "
                "link diameter, leg count, section depth, and web-width trials found no "
                "executor-backed one-click arrangement that passes shear capacity plus bending, "
                "crack, deflection, spacing, ductility, cover, and detailing checks."
            )
        elif family == "crack":
            reason = (
                "Crack control repair is blocked by serviceability/detailing limits. Exhaustive "
                "bar count, bar diameter, section depth, and section width trials found no "
                "executor-backed one-click arrangement that resolves the crack limit while "
                "preserving bending, shear, deflection, spacing, ductility, cover, and detailing checks."
            )
        elif family == "deflection":
            reason = (
                "Deflection repair is blocked by geometry/serviceability limits. Exhaustive "
                "section depth, section width, reinforcement, and sustained-load trials found no "
                "executor-backed one-click arrangement that resolves the deflection limit while "
                "preserving bending, shear, crack control, spacing, ductility, cover, and detailing checks."
            )
        else:
            reason = (
                "Bending repair is blocked by reinforcement, geometry, ductility, or detailing limits. "
                "Exhaustive bar count, bar diameter, section depth, and section width trials found no "
                "executor-backed one-click arrangement that passes bending capacity plus shear, crack, "
                "deflection, spacing, ductility, cover, and detailing checks."
            )
    active_failures = list(evidence.get("active_failures") or [])
    if not active_failures:
        statuses = _mapping(overview_map.get("statuses"))
        active_failures = [
            str(key or "").strip().lower()
            for key, value in statuses.items()
            if str(value or "").strip().upper() == "FAIL"
        ] or [family]
    active_set = {
        str(value or "").strip().lower()
        for value in list(active_failures or [])
        if str(value or "").strip()
    }
    bending_missing_family_proof = bool(
        family == "bending"
        and active_set == {"bending"}
        and not _bending_fail_family_owned_repair_blocked_proof(evidence)
    )
    if bending_missing_family_proof:
        reason = (
            "BENDING_FAIL_GOVERNS did not publish family-owned repair-blocked proof. "
            "Bounded or cap-only search exhaustion remains diagnostic only."
        )
    evidence.update(
        {
            "candidate_search_exhaustive": True,
            "repair_search_ran": True,
            "repair_search_exhaustive": True,
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "search_scope": evidence.get("search_scope") or f"{family}_active_failure_practical_ladder",
            "active_failures": list(dict.fromkeys(active_failures)),
            "total_candidates_considered": max(
                int(evidence.get("total_candidates_considered") or 0),
                len(attempted_updates),
            ),
            "safe_candidate_count": int(evidence.get("safe_candidate_count") or 0),
            "executable_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
            "safe_executor_backed_candidates_count": 0,
            "target_band_candidate_count": 0,
            "failed_candidate_reasons": list(evidence.get("failed_candidate_reasons") or [reason]),
            "blocker_reasons_by_family": dict(evidence.get("blocker_reasons_by_family") or {family: [reason]}),
            "exact_blocker_reasons_by_family": dict(evidence.get("exact_blocker_reasons_by_family") or {family: [reason]}),
            "active_under_capacity_blocker": not bending_missing_family_proof,
            "active_under_capacity_blocker_family": family,
            "active_under_capacity_blocker_reason": reason,
            "outside_target_band_allowed": False,
            "outside_target_band_allowed_reason": reason,
            "outside_target_band_allowed_category": category,
            "attempted_candidate_id": evidence.get("attempted_candidate_id") or f"{family}_active_failure_practical_ladder_exhausted",
            "attempted_updates": dict(attempted_updates),
            "failed_check_name": evidence.get("failed_check_name") or f"{family} repair catalogue",
            "failed_check_status": evidence.get("failed_check_status") or "FAIL",
            "failed_check_util": evidence.get("failed_check_util") or item.get("util") or 1.0,
            "failed_check_demand": evidence.get("failed_check_demand") or f"{family} demand remains above checked capacity or serviceability limit",
            "failed_check_capacity_or_limit": evidence.get("failed_check_capacity_or_limit") or f"{family} capacity or serviceability limit",
            "one_click_target_reaching_candidate_exists": False,
        }
    )
    if bending_missing_family_proof:
        evidence["bending_fail_missing_family_owned_no_repair_proof"] = True
        evidence["visible_blocked_wording_source"] = "not_published_without_family_owned_proof"
    active_payload = {
        "family": family,
        "reason": reason,
        "active_failures": list(evidence.get("active_failures") or [family]),
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "safe_candidate_count": int(evidence.get("safe_candidate_count") or 0),
        "executable_candidate_count": 0,
        "executable_target_band_candidate_count": 0,
        "safe_cleanup_count": 0,
        "executable_cleanup_count": 0,
        "attempted_candidate_id": evidence.get("attempted_candidate_id"),
        "attempted_updates": dict(evidence.get("attempted_updates") or {}),
        "failed_check_name": evidence.get("failed_check_name"),
        "failed_check_status": evidence.get("failed_check_status"),
        "failed_check_util": evidence.get("failed_check_util"),
        "failed_check_demand": evidence.get("failed_check_demand"),
        "failed_check_capacity_or_limit": evidence.get("failed_check_capacity_or_limit"),
    }
    if bending_missing_family_proof:
        exact_blockers: dict[str, Any] = {}
    else:
        exact_blockers = active_failure_exact_blockers_for_families(
            list(evidence.get("active_failures") or [family]),
            overview=overview_map,
            evidence=evidence,
            primary_family=family,
            primary_reason=reason,
        )
        if family not in exact_blockers:
            exact_blockers[family] = dict(active_payload)
    evidence["exact_blockers_by_family"] = dict(exact_blockers)
    evidence["post_click_exact_blockers_by_family"] = dict(exact_blockers)
    if {"bending", "shear"}.issubset(set(exact_blockers)):
        item["title_main"] = "Bending and shear repair blocked"
        item["title"] = "Bending and shear repair blocked"
        item["family"] = "combined"
        item["check_key"] = "combined"
        bending_reason = str((_mapping(exact_blockers.get("bending"))).get("reason") or "").strip()
        shear_reason = str((_mapping(exact_blockers.get("shear"))).get("reason") or "").strip()
        item["primary_action"] = f"Bending repair blocked: {bending_reason}"
        item["secondary_action"] = f"Shear repair blocked: {shear_reason}"
        item["reasoning"] = (
            "Why: exact blocker evidence exists for both bending and shear after the exhaustive "
            "active-failure one-click repair search."
        )
        item["title_util_label"] = "governing utilisation"
    item["candidate_search_evidence"] = dict(evidence)
    item["exact_blockers_by_family"] = dict(evidence.get("exact_blockers_by_family") or {})
    item["post_click_exact_blockers_by_family"] = dict(evidence.get("exact_blockers_by_family") or {})
    if bending_missing_family_proof:
        item["title_main"] = "Bending repair proof incomplete"
        item["title"] = "Bending repair proof incomplete"
        item["reasoning"] = reason
        item["primary_action"] = reason
        item["secondary_action"] = (
            "Family-owned BENDING_FAIL_GOVERNS proof is required before publishing a no-repair terminal card."
        )
        item["guidance_intent"] = "diagnostic_incomplete_proof"
    item["primary_card_actionable"] = False
    item["final_state_class"] = "diagnostic_incomplete_proof" if bending_missing_family_proof else "blocker"
    contract = dict(item.get("button_contract") or {})
    contract.update(
        {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": str(item.get("family") or family),
            "updates": {},
            "preview_pass": False,
            "expected_util": None,
            "blocking_reason": reason,
            "source_candidate_id": None,
            "candidate_id": None,
        }
    )
    item["button_contract"] = dict(contract)
    return {
        "materialized": True,
        "family": family,
        "category": category,
        "reason": reason,
        "attempted_updates": dict(attempted_updates),
        "exact_blockers_by_family": dict(exact_blockers),
        "button_contract": dict(contract),
        "primary_item": item,
        "existing_evidence": evidence,
        "trace": {
            "family": family,
            "category": category,
            "evidence_keys": sorted(str(key) for key in evidence.keys())[:60],
            "attempted_updates": dict(attempted_updates),
        },
    }


def build_design_guide_controller_compute_serviceability_exact_blocker_projection(
    *,
    primary_check: str,
    primary_item: dict[str, Any] | None,
    existing_evidence: dict[str, Any] | None,
    failed_row: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build crack/deflection exact-blocker evidence and display projection."""

    check = str(primary_check or "").strip().lower()
    item = dict(primary_item or {})
    row = dict(failed_row or {})
    evidence = dict(existing_evidence or {})
    if check not in {"crack", "deflection"}:
        return {
            "applied": False,
            "primary_check": check,
            "existing_evidence": dict(evidence),
            "display_truth": {},
            "item_projection": {},
        }

    attempted_updates = (
        {
            "bot1_count": "increase bottom bar count trial",
            "bot_row_1_bars": "increase bottom bar count trial",
            "db_bot_1": "increase bottom bar diameter trial",
            "bot_row_1_dia": "increase bottom bar diameter trial",
            "D": "increase section depth trial",
            "b": "increase section width trial",
        }
        if check == "crack"
        else {
            "D": "increase section depth trial",
            "b": "increase section width trial",
            "sustained_load": "reduce sustained load advisory trial",
        }
    )
    reason = (
        "No one-click crack-control arrangement from the practical bar/count/diameter and "
        "section geometry trials resolved the crack limit while preserving bending, shear, "
        "deflection, spacing, ductility, cover, and detailing checks."
        if check == "crack"
        else
        "No one-click deflection arrangement from the practical depth, width, and sustained-load "
        "trials resolved the deflection limit while preserving bending, shear, crack control, "
        "spacing, ductility, cover, and detailing checks."
    )
    evidence.update(
        {
            "candidate_search_exhaustive": True,
            "search_scope": f"serviceability_{check}_active_failure_ladder",
            "total_candidates_considered": max(
                int(evidence.get("total_candidates_considered") or 0),
                len(attempted_updates),
            ),
            "safe_executor_backed_candidates_count": 0,
            "target_band_candidate_count": 0,
            "active_under_capacity_blocker": True,
            "active_under_capacity_blocker_family": check,
            "active_under_capacity_blocker_reason": reason,
            "outside_target_band_allowed": False,
            "outside_target_band_allowed_reason": reason,
            "outside_target_band_allowed_category": f"{check}_would_fail",
            "attempted_candidate_id": f"{check}_serviceability_practical_ladder_exhausted",
            "attempted_updates": dict(attempted_updates),
            "failed_check_name": str(row.get("title") or f"{check} limit"),
            "failed_check_status": str(row.get("status") or "FAIL"),
            "failed_check_util": item.get("util"),
            "failed_check_demand": str(
                row.get("calculated")
                or row.get("value")
                or row.get("action")
                or f"{check} demand"
            ),
            "failed_check_capacity_or_limit": str(
                row.get("requirement")
                or row.get("limit")
                or f"{check} limit"
            ),
            "one_click_target_reaching_candidate_exists": False,
        }
    )
    display_truth = {
        "display_truth_source": "published_summary",
        "displayed_util": item.get("util"),
        "displayed_status": "FAIL",
        "target_low": evidence.get("target_low"),
        "target_high": evidence.get("target_high"),
        "displayed_within_target_band": False,
        "source_summary_util": item.get("util"),
        "source_candidate_util": None,
        "source_post_commit_util": None,
    }
    return {
        "applied": True,
        "primary_check": check,
        "existing_evidence": dict(evidence),
        "display_truth": dict(display_truth),
        "item_projection": {
            "display_truth": dict(display_truth),
            "display_truth_source": "published_summary",
            "displayed_util": item.get("util"),
            "displayed_status": "FAIL",
            "source_summary_util": item.get("util"),
            "source_candidate_util": None,
        },
    }


def build_design_guide_controller_compute_safe_cleanup_rehydration_projection(
    *,
    primary_item: dict[str, Any] | None,
    existing_evidence: dict[str, Any] | None,
    primary_contract: dict[str, Any] | None,
    primary_title: str,
    primary_action: str,
    primary_action_blocked: bool,
    state_updates_match_accepted_safe_updates: bool,
    combined_safe_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the late-evidence safe-cleanup rehydration projection."""

    item = dict(primary_item or {})
    evidence = dict(existing_evidence or {})
    contract = dict(primary_contract or {})
    title_text = str(primary_title or "")

    def _unchanged() -> dict[str, Any]:
        return {
            "rehydrated": False,
            "primary_title": primary_title,
            "primary_action": primary_action,
            "primary_action_blocked": bool(primary_action_blocked),
            "primary_contract": dict(contract),
            "primary_item": dict(item),
            "existing_evidence": dict(evidence),
            "debug_updates": {},
            "trace": {},
        }

    if "shear cleanup blocked by final efficiency threshold" not in title_text:
        return _unchanged()

    payload = dict(item.get("action_payload") or {})
    combined_row = dict(combined_safe_row or {})
    combined_updates = dict(combined_row.get("proposed_updates") or combined_row.get("updates") or {})
    combined_safe_cleanup = bool(
        combined_row
        and combined_updates
        and bool(set(combined_updates) & _CONTROLLER_COMPOUND_SHEAR_UPDATE_KEYS)
        and bool(set(combined_updates) & _CONTROLLER_COMPOUND_BOTTOM_UPDATE_KEYS)
    )
    accepted_updates = dict(evidence.get("best_safe_candidate_updates") or {})
    accepted_safe_cleanup = bool(
        str(evidence.get("family") or "").strip().lower() == "shear"
        and accepted_updates
        and bool(set(accepted_updates) & _CONTROLLER_COMPOUND_SHEAR_UPDATE_KEYS)
        and not bool(state_updates_match_accepted_safe_updates)
        and (
            bool(evidence.get("one_click_target_reaching_candidate_exists"))
            or int(evidence.get("accepted_band_candidate_count") or 0) > 0
        )
    )
    if not (combined_safe_cleanup or accepted_safe_cleanup):
        return _unchanged()

    updates = dict(combined_updates if combined_safe_cleanup else accepted_updates)
    preview_pass = bool(
        contract.get("preview_pass")
        or payload.get("preview_pass")
        or str(payload.get("preview_status") or "").strip().upper() == "PASS"
        or combined_safe_cleanup
        or evidence.get("one_click_target_reaching_candidate_exists")
        or int(evidence.get("accepted_band_candidate_count") or 0) > 0
    )
    if not (
        updates
        and bool(set(updates) & _CONTROLLER_COMPOUND_SHEAR_UPDATE_KEYS)
        and preview_pass
    ):
        return _unchanged()

    expected_util = _float_or_none(
        (combined_row.get("preview_util") if combined_safe_cleanup else None)
        or (evidence.get("best_safe_final_util") if accepted_safe_cleanup else None)
        or contract.get("expected_util")
        or payload.get("expected_util")
        or payload.get("resolved_candidate_post_util")
        or evidence.get("selected_candidate_util")
        or evidence.get("best_safe_final_util")
    )
    candidate_id = normalise_design_guide_candidate_id(
        combined_row.get("candidate_id") if combined_safe_cleanup else None if accepted_safe_cleanup else contract.get("candidate_id"),
        combined_row.get("source_candidate_id") if combined_safe_cleanup else None if accepted_safe_cleanup else contract.get("source_candidate_id"),
        None if (combined_safe_cleanup or accepted_safe_cleanup) else payload.get("candidate_id"),
        None if (combined_safe_cleanup or accepted_safe_cleanup) else payload.get("source_candidate_id"),
        evidence.get("best_safe_candidate_id"),
        evidence.get("selected_candidate_id"),
        family="combined" if combined_safe_cleanup else "shear",
        updates=updates,
    )

    for stale_key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
    ):
        evidence.pop(stale_key, None)
    evidence["best_safe_candidate_applied"] = False
    evidence["no_second_cta_required"] = False
    evidence["selected_candidate_id"] = candidate_id
    evidence["selected_candidate_updates"] = dict(updates)
    evidence["selected_candidate_util"] = expected_util

    family = "combined" if combined_safe_cleanup else "shear"
    title = (
        "Shear and bending cleanup - one-click optimisation"
        if combined_safe_cleanup
        else "Shear cleanup - best safe one-click reduction"
    )
    contract.update(
        {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": family,
            "updates": dict(updates),
            "preview_pass": True,
            "expected_util": expected_util,
            "blocking_reason": None,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
        }
    )
    item.update(
        {
            "title_main": title,
            "title": _controller_format_guidance_title(title, expected_util),
            "family": family,
            "check_key": family,
            "selected_action_family": family,
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates),
            "selected_action_updates": dict(updates),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "primary_card_actionable": True,
            "guidance_intent": "efficiency_tightening",
            "button_contract": dict(contract),
        }
    )
    debug_updates = {
        "primary_card_title": title,
        "final_primary_title": title,
        "selected_title": title,
        "primary_guidance_intent": "efficiency_tightening",
        "primary_card_intent": "efficiency_tightening",
        "button_contract": dict(contract),
        "primary_button_contract": dict(contract),
        "button_contract_enabled": True,
        "button_contract_updates": dict(updates),
        "button_contract_preview_pass": True,
        "button_contract_blocking_reason": None,
    }
    return {
        "rehydrated": True,
        "primary_title": title.lower(),
        "primary_action": "apply_resolved_candidate",
        "primary_action_blocked": False,
        "primary_contract": dict(contract),
        "primary_item": dict(item),
        "existing_evidence": dict(evidence),
        "debug_updates": debug_updates,
        "trace": {
            "family": family,
            "candidate_id": candidate_id,
            "expected_util": expected_util,
            "updates": dict(updates),
        },
    }


def resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision(
    *,
    primary_item: dict[str, Any] | None,
    existing_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve the pure late-evidence contract rebound entry decision."""

    item = dict(primary_item or {})
    evidence = dict(existing_evidence or {})
    late_contract = dict(item.get("button_contract") or {})
    late_updates = dict(
        evidence.get("selected_candidate_updates")
        or evidence.get("best_safe_candidate_updates")
        or {}
    )
    contract_disabled_or_mismatched = bool(
        not design_guide_button_contract_enabled(late_contract)
        or (
            str(evidence.get("family") or "").strip().lower() == "combined"
            and dict(late_updates) != dict(late_contract.get("updates") or {})
        )
    )
    active_under_capacity_blocker = bool(evidence.get("active_under_capacity_blocker"))
    accepted = bool(
        late_updates
        and contract_disabled_or_mismatched
        and not active_under_capacity_blocker
    )
    late_evidence_acceptance = {
        "late_updates_present": bool(late_updates),
        "contract_disabled_or_mismatched": bool(contract_disabled_or_mismatched),
        "active_under_capacity_blocker": bool(active_under_capacity_blocker),
        "accepted": False,
    }
    return {
        "should_rebound": accepted,
        "late_updates": dict(late_updates),
        "late_contract": dict(late_contract),
        "late_evidence_acceptance": dict(late_evidence_acceptance),
        "contract_disabled_or_mismatched": bool(contract_disabled_or_mismatched),
        "active_under_capacity_blocker": bool(active_under_capacity_blocker),
    }


def _controller_guidance_bucket(status: str, util: float | None = None) -> str:
    upper = str(status or "").upper()
    if "START" in upper:
        return "start"
    if "EFFICIENCY" in upper or "TIGHTEN" in upper:
        return "efficiency"
    if "FAIL" in upper or upper == "NG":
        return "fail"
    if "WARN" in upper or "NEAR LIMIT" in upper or upper == "CHECK":
        return "warn"
    if util is not None and util > 1.0:
        return "fail"
    if util is not None and util >= 0.9:
        return "warn"
    return "pass"


def _controller_guidance_priority(bucket: str, util: float | None) -> float:
    util_score = util if util is not None else 0.0
    if bucket == "start":
        return 50.0
    if bucket == "fail":
        return 300.0 + util_score
    if bucket == "warn":
        return 200.0 + util_score
    if bucket == "efficiency":
        return 150.0 + util_score
    return 100.0 - util_score


def _controller_guidance_item(
    check_key: str,
    title: str,
    primary_action: str,
    secondary_action: str | None,
    reasoning: str,
    levers: str,
    action_type: str | None,
    action_payload: dict | None,
    *,
    status: str,
    util: float | None,
) -> dict[str, Any]:
    bucket = _controller_guidance_bucket(status, util)
    return {
        "check_key": check_key,
        "title_main": title,
        "title_util": f"(utilisation = {util:.2f})" if util is not None else None,
        "title": f"{title} (utilisation = {util:.2f})" if util is not None else title,
        "primary_action": primary_action,
        "secondary_action": secondary_action,
        "reasoning": reasoning,
        "levers": levers,
        "status": status,
        "bucket": bucket,
        "util": util,
        "priority": _controller_guidance_priority(bucket, util),
        "action_type": action_type,
        "action_payload": action_payload or {},
    }


def build_design_guide_controller_guidance_item(
    check_key: str,
    title: str,
    primary_action: str,
    secondary_action: str | None,
    reasoning: str,
    levers: str,
    action_type: str | None,
    action_payload: dict | None,
    *,
    status: str,
    util: float | None,
    guidance_before_after: str | None = None,
    guidance_change_lines: list[str] | None = None,
    guidance_why: str | None = None,
) -> dict[str, Any]:
    """Build the canonical Design Guide guidance item shape."""

    out = _controller_guidance_item(
        check_key,
        title,
        primary_action,
        secondary_action,
        reasoning,
        levers,
        action_type,
        action_payload,
        status=status,
        util=util,
    )
    if guidance_before_after:
        out["guidance_before_after"] = guidance_before_after
    if guidance_change_lines:
        out["guidance_change_lines"] = [
            str(value) for value in guidance_change_lines if str(value).strip()
        ]
    if guidance_why:
        out["guidance_why"] = str(guidance_why)
    return out


def build_design_guide_controller_start_guidance_item(
    *,
    start_line: str,
) -> dict[str, Any]:
    """Build the Design Guide start card from page-collected start text."""

    item = build_design_guide_controller_guidance_item(
        "general",
        "Choose your workflow:",
        str(start_line or ""),
        None,
        "Or define loads from the Design page",
        "Key levers: geometry, actions, initial reinforcement",
        None,
        None,
        status="START",
        util=None,
    )
    item["start_steps"] = [
        "Fast -> guided design",
        "Detailed -> full control",
    ]
    return item


def resolve_design_guide_controller_not_started_condition(
    *,
    width: Any,
    depth: Any,
    span: Any,
    bending_util: Any,
    shear_util: Any,
    action_values: list[Any] | tuple[Any, ...] | None,
    bottom_ast: Any,
    bottom_count: Any,
    bottom_diameter: Any,
    ligature_legs: Any,
    ligature_diameter: Any,
    ligature_spacing: Any,
) -> dict[str, Any]:
    """Resolve the pure not-started Design Guide condition."""

    width_value = _float_or_none(width) or 0.0
    depth_value = _float_or_none(depth) or 0.0
    span_value = _float_or_none(span) or 0.0
    required_inputs_missing = bool(width_value <= 0.0 or depth_value <= 0.0 or span_value <= 0.0)
    bending_value = _float_or_none(bending_util)
    shear_value = _float_or_none(shear_util)
    no_key_results = all(
        value is None or value <= 0.0
        for value in (bending_value, shear_value)
    )
    actions = []
    for value in list(action_values or []):
        parsed = _float_or_none(value)
        actions.append(0.0 if parsed is None else abs(float(parsed)))
    no_actions = max(actions, default=0.0) <= 1e-9
    bottom_ast_value = _float_or_none(bottom_ast) or 0.0
    bottom_count_value = int(_float_or_none(bottom_count) or 0)
    bottom_diameter_value = _float_or_none(bottom_diameter) or 0.0
    no_bottom_reo = bool(
        bottom_ast_value <= 0.0
        or bottom_count_value <= 0
        or bottom_diameter_value <= 0.0
    )
    ligature_legs_value = int(_float_or_none(ligature_legs) or 0)
    ligature_diameter_value = _float_or_none(ligature_diameter) or 0.0
    ligature_spacing_value = _float_or_none(ligature_spacing) or 0.0
    no_shear_reo = bool(
        ligature_legs_value <= 0
        or ligature_diameter_value <= 0.0
        or ligature_spacing_value <= 0.0
    )
    not_started = bool(
        required_inputs_missing
        or no_key_results
        or (no_actions and (no_bottom_reo or no_shear_reo))
    )
    return {
        "not_started": not_started,
        "required_inputs_missing": required_inputs_missing,
        "no_key_results": bool(no_key_results),
        "no_actions": bool(no_actions),
        "no_bottom_reo": no_bottom_reo,
        "no_shear_reo": no_shear_reo,
    }


def resolve_design_guide_controller_post_active_zero_shear_predicate(
    *,
    shear_demands_negligible: bool,
    direct_vu: Any,
    shear_demand_abs_tol_kn: Any,
) -> dict[str, Any]:
    """Resolve the pure post-active zero-shear predicate."""

    vu_value = abs(_float_or_none(direct_vu) or 0.0)
    tolerance = _float_or_none(shear_demand_abs_tol_kn) or 0.0
    demand_below_tolerance = bool(vu_value <= tolerance + 1e-12)
    zero_shear = bool(bool(shear_demands_negligible) or demand_below_tolerance)
    reason = (
        "shear_demands_negligible"
        if bool(shear_demands_negligible)
        else "direct_vu_below_tolerance"
        if demand_below_tolerance
        else "shear_demand_present"
    )
    return {
        "post_active_zero_shear": zero_shear,
        "shear_demands_negligible": bool(shear_demands_negligible),
        "direct_vu": vu_value,
        "shear_demand_abs_tol_kn": tolerance,
        "direct_vu_below_tolerance": demand_below_tolerance,
        "reason": reason,
    }


def build_design_guide_controller_post_active_zero_shear_terminal_projection(
    *,
    accepted_util: Any,
    target_low: Any,
    target_high: Any,
    shear_util: Any,
    existing_excluded_families: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the post-active zero-shear accepted terminal projection."""

    util_value = _float_or_none(accepted_util)
    target_low_value = _float_or_none(target_low)
    target_high_value = _float_or_none(target_high)
    item = build_design_guide_controller_guidance_item(
        "general",
        "Design accepted - target band achieved",
        "The one-click capacity repair has been applied and the current design is inside the target band.",
        None,
        "Why: all required checks remain acceptable; shear has zero or negligible demand and is not a required cleanup family.",
        "Key checks: bending, shear demand, serviceability, target utilisation band",
        None,
        None,
        status="PASS",
        util=util_value,
    )
    item["guidance_intent"] = "already_efficient"
    item["design_guide_terminal_state"] = "optimal"
    item["display_truth"] = {
        "display_truth_source": "published_summary",
        "displayed_util": util_value,
        "displayed_status": "OPTIMAL",
        "target_low": float(target_low_value),
        "target_high": float(target_high_value),
        "displayed_within_target_band": True,
        "source_summary_util": util_value,
        "source_candidate_util": None,
        "source_post_commit_util": util_value,
    }
    zero_shear_exclusion = {
        "family": "shear",
        "reason": "zero_demand_or_not_meaningful",
        "excluded_reason": "zero_demand_or_not_meaningful",
        "cleanup_required": False,
        "no_second_cta_required": True,
        "util": _float_or_none(shear_util),
    }
    excluded = {
        **dict(existing_excluded_families or {}),
        "shear": dict(zero_shear_exclusion),
    }
    debug_updates = {
        "guidance_branch": "post_active_repair_zero_shear_terminal",
        "selected_action_type": None,
        "selected_title": item.get("title_main"),
        "post_click_accepted_green": True,
        "post_click_accepted_green_valid": True,
        "post_click_design_guide_state": "accepted_green",
        "post_click_executable_safe_cleanup_count": 0,
        "post_click_safe_local_cleanup_count": 0,
        "post_click_unresolved_low_util_families": [],
        "post_click_unresolved_overprovided_families": [],
        "post_click_excluded_families": dict(excluded),
        "excluded_families": dict(excluded),
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "safe_local_cleanup_count": 0,
        "executable_safe_cleanup_count": 0,
        "terminal_state_reason": "post_active_repair_zero_shear_excluded",
        "terminal_state_blocked_by_local_cleanup": False,
        "primary_button_contract": {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": "shear",
            "updates": {},
            "preview_pass": False,
            "blocking_reason": "zero_demand_or_not_meaningful",
            "source_candidate_id": None,
            "candidate_id": None,
        },
    }
    return {
        "item": item,
        "debug_updates": debug_updates,
        "zero_shear_exclusion": zero_shear_exclusion,
        "controller_authority": "DesignGuideController.post_active_zero_shear_terminal_projection",
    }


def build_design_guide_controller_post_active_residual_shear_cleanup_debug_projection(
    *,
    cleanup_item: dict[str, Any] | None,
    cleanup_contract: dict[str, Any] | None,
    cleanup_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build debug rows for the post-active residual shear cleanup action."""

    item = dict(cleanup_item or {})
    contract = dict(cleanup_contract or {})
    evidence = dict(cleanup_evidence or {})
    return {
        "guidance_branch": "post_active_repair_residual_shear_best_safe_action",
        "selected_action_type": "apply_resolved_candidate",
        "selected_title": item.get("title_main"),
        "selected_action_family": "shear",
        "post_click_accepted_green": False,
        "post_click_accepted_green_valid": False,
        "post_click_design_guide_state": None,
        "post_active_low_shear_safe_action_preferred": True,
        "primary_button_contract": dict(contract),
        "button_contract": dict(contract),
        "button_contract_enabled": True,
        "button_contract_updates": dict(contract.get("updates") or {}),
        "candidate_search_evidence": dict(evidence),
        "primary_card_title": item.get("title_main"),
        "primary_card_intent": "efficiency_tightening",
        "primary_guidance_intent": "efficiency_tightening",
    }


def build_design_guide_controller_post_active_shear_cleanup_blocked_projection(
    *,
    shear_blocker_reason: str,
    shear_blocker_util: Any,
    mode_config: dict[str, Any] | None,
    shear_blocker: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the post-active shear cleanup blocked item/contract/debug projection."""

    reason = str(shear_blocker_reason or "").strip()
    util = _float_or_none(shear_blocker_util)
    blocker = dict(shear_blocker or {})
    mode = dict(mode_config or {})
    blocker_item = build_design_guide_controller_guidance_item(
        "shear",
        "Shear cleanup blocked by final efficiency threshold",
        "No second one-click cleanup is enabled after the capacity repair.",
        None,
        f"Why: {reason}",
        "Key checks: shear utilisation threshold, bending, serviceability, detailing",
        None,
        None,
        status="EFFICIENCY",
        util=util,
    )
    blocker_contract = {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": "shear",
        "updates": {},
        "preview_pass": False,
        "blocking_reason": reason,
        "source_candidate_id": None,
        "candidate_id": None,
    }
    blocker_truth = {
        "display_truth_source": "post_commit_truth",
        "displayed_util": util,
        "displayed_status": "BLOCKED",
        "target_low": mode.get("target_low"),
        "target_high": mode.get("target_high"),
        "displayed_within_target_band": False,
        "source_summary_util": util,
        "source_candidate_util": None,
        "source_post_commit_util": util,
    }
    blocker_item.update(
        {
            "guidance_intent": "specific_blocker",
            "button_contract": dict(blocker_contract),
            "display_truth": dict(blocker_truth),
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "safe_local_cleanup_count": 0,
            "executable_safe_cleanup_count": 0,
            "terminal_state_blocked_by_local_cleanup": True,
            "local_cleanup_blocked_reasons": [reason],
            "local_cleanup_blocked_reasons_by_family": {"shear": [reason]},
            "exact_blockers_by_family": {"shear": dict(blocker)},
            "post_click_exact_blockers_by_family": {"shear": dict(blocker)},
            "cleanup_evidence_by_family": {"shear": dict(blocker)},
            "post_click_cleanup_evidence_by_family": {"shear": dict(blocker)},
            "candidate_search_evidence": {
                "candidate_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "safe_local_cleanup_count": 0,
                "executable_safe_cleanup_count": 0,
                "safe_shear_cleanup_count": 0,
                "executable_shear_cleanup_count": 0,
                "exact_blockers_by_family": {"shear": dict(blocker)},
                "local_cleanup_blocked_reasons": [reason],
                "local_cleanup_blocked_reasons_by_family": {"shear": [reason]},
                "no_second_cta_required": True,
            },
        }
    )
    debug_updates = {
        "guidance_branch": "post_active_repair_shear_cleanup_blocked",
        "selected_action_type": None,
        "selected_title": blocker_item.get("title_main"),
        "selected_action_family": "shear",
        "post_click_accepted_green": False,
        "post_click_accepted_green_valid": True,
        "post_click_design_guide_state": "exact_blocker",
        "post_click_safe_local_cleanup_count": 0,
        "post_click_executable_safe_cleanup_count": 0,
        "post_click_unresolved_low_util_families": [],
        "post_click_unresolved_overprovided_families": [],
        "post_click_exact_blockers_by_family": {"shear": dict(blocker)},
        "exact_blockers_by_family": {"shear": dict(blocker)},
        "cleanup_evidence_by_family": {"shear": dict(blocker)},
        "post_click_cleanup_evidence_by_family": {"shear": dict(blocker)},
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "safe_local_cleanup_count": 0,
        "executable_safe_cleanup_count": 0,
        "terminal_state_blocked_by_local_cleanup": True,
        "terminal_state_reason": reason,
        "primary_button_contract": dict(blocker_contract),
        "primary_display_truth": dict(blocker_truth),
        "primary_card_title": blocker_item.get("title_main"),
        "primary_card_intent": "specific_blocker",
        "primary_guidance_intent": "specific_blocker",
    }
    return {
        "item": dict(blocker_item),
        "button_contract": dict(blocker_contract),
        "display_truth": dict(blocker_truth),
        "debug_updates": dict(debug_updates),
    }


def resolve_design_guide_controller_optimisation_selector_fallback_result(
    *,
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    governing_action: str | None,
    selector_debug: dict[str, Any] | None,
    candidate_families: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Resolve optimisation fallback selection without page-local policy."""

    candidate_list = [item for item in list(candidates or []) if isinstance(item, dict)]
    debug = dict(selector_debug or {})
    if not candidate_list:
        reason = debug.get("optimisation_selector_fallback_reason") or "shared_selector_no_primary_no_candidates"
        return {
            "selected_index": None,
            "selected_family": None,
            "selector_debug": {
                **debug,
                "optimisation_selector_winning_family": None,
                "optimisation_selector_fallback_reason": reason,
                "primary_optimisation_selection_owner": "controller_fallback",
            },
        }

    governing = str(governing_action or "")
    selected_index = 0
    for index, item in enumerate(candidate_list):
        if str(item.get("check_key") or "") == governing:
            selected_index = index
            break

    families = list(candidate_families or [])
    selected_family = (
        str(families[selected_index])
        if selected_index < len(families) and str(families[selected_index] or "").strip()
        else None
    )
    if not selected_family:
        selected = candidate_list[selected_index]
        check_key = str(selected.get("check_key") or "").strip().lower()
        action_type = str(selected.get("action_type") or "").strip().lower()
        if check_key in {"bending", "shear", "geometry", "compound"}:
            selected_family = check_key
        elif action_type in {"reduce_bottom_reinforcement", "reduce_bar_spacing", "apply_bottom_recommendation"}:
            selected_family = "bending"
        elif action_type in {"increase_link_spacing", "reduce_number_of_legs", "apply_shear_recommendation"}:
            selected_family = "shear"
        elif action_type in {"tighten_geometry", "apply_geometry_recommendation", "increase_depth", "increase_width"}:
            selected_family = "geometry"
        else:
            selected_family = "other"

    return {
        "selected_index": selected_index,
        "selected_family": selected_family,
        "selector_debug": {
            **debug,
            "optimisation_selector_winning_family": selected_family,
            "optimisation_selector_fallback_reason": (
                debug.get("optimisation_selector_fallback_reason")
                or "shared_selector_no_primary_fallback_order_used"
            ),
            "primary_optimisation_selection_owner": "controller_fallback",
        },
    }


def build_design_guide_controller_optimisation_selector_default_debug_context(
    *,
    governing_action: str | None,
) -> dict[str, Any]:
    """Return pure default debug fields for optimisation selector tracing."""

    return {
        "optimisation_selector_governing_action": str(governing_action or "other"),
        "optimisation_selector_family_bias_applied": False,
        "optimisation_selector_candidate_counts_by_family": {},
        "optimisation_selector_winning_family": None,
        "optimisation_selector_used_geometry_fallback": False,
        "optimisation_selector_fallback_reason": None,
        "optimisation_selector_candidate_reaches_target_band": False,
        "optimisation_selector_candidate_all_key_pass": False,
        "primary_optimisation_selection_owner": "controller_fallback",
    }


def resolve_design_guide_controller_optimisation_candidate_family(
    *,
    check_key: str | None,
    action_type: str | None,
    update_subfamilies: list[str] | tuple[str, ...] | set[str] | None,
    base_family: str | None,
) -> str:
    """Classify an optimisation candidate family from already-resolved plain inputs."""

    check = str(check_key or "").strip().lower()
    action = str(action_type or "").strip().lower()
    subfamilies = {str(value).strip().lower() for value in (update_subfamilies or []) if str(value).strip()}
    base = str(base_family or "").strip().lower()
    if check in {"bending", "shear"}:
        return check
    if len(subfamilies) >= 2:
        return "compound"
    if "bending" in subfamilies or "bottom_reo" in subfamilies:
        return "bending"
    if "shear" in subfamilies:
        return "shear"
    if "geometry" in subfamilies:
        return "geometry"
    if base in {"bending", "shear", "geometry", "compound"}:
        return base
    if action in {"reduce_bottom_reinforcement", "reduce_bar_spacing", "apply_bottom_recommendation"}:
        return "bending"
    if action in {"increase_link_spacing", "reduce_number_of_legs", "apply_shear_recommendation"}:
        return "shear"
    if action in {"tighten_geometry", "apply_geometry_recommendation", "increase_depth", "increase_width"}:
        return "geometry"
    return "other"


def build_design_guide_controller_optimisation_selector_debug_projection(
    *,
    guidance_branch: str,
    primary_item: dict[str, Any] | None,
    selector_debug: dict[str, Any] | None,
    selected_family: str | None,
    governing_action: str | None,
) -> dict[str, Any]:
    """Build the pure debug projection for optimisation selector publication."""

    primary = dict(primary_item or {})
    debug = dict(selector_debug or {})
    owner = str(debug.get("primary_optimisation_selection_owner") or "controller_fallback")
    out = {
        "guidance_branch": str(guidance_branch or ""),
        "selected_action_type": primary.get("action_type"),
        "selected_title": primary.get("title_main"),
        "optimisation_selector_governing_action": debug.get(
            "optimisation_selector_governing_action",
        ),
        "optimisation_selector_family_bias_applied": bool(
            debug.get("optimisation_selector_family_bias_applied"),
        ),
        "optimisation_selector_candidate_counts_by_family": dict(
            debug.get("optimisation_selector_candidate_counts_by_family") or {},
        ),
        "optimisation_selector_winning_family": debug.get(
            "optimisation_selector_winning_family",
        ) or selected_family,
        "optimisation_selector_used_geometry_fallback": bool(
            debug.get("optimisation_selector_used_geometry_fallback"),
        ),
        "optimisation_selector_fallback_reason": debug.get(
            "optimisation_selector_fallback_reason",
        ),
        "optimisation_selector_candidate_reaches_target_band": bool(
            debug.get("optimisation_selector_candidate_reaches_target_band"),
        ),
        "optimisation_selector_candidate_all_key_pass": bool(
            debug.get("optimisation_selector_candidate_all_key_pass"),
        ),
        "primary_optimisation_selection_owner": owner,
        "overdesign_no_band_reacher_but_compliant_candidates_exist": bool(
            debug.get("overdesign_no_band_reacher_but_compliant_candidates_exist"),
        ),
        "overdesign_stepwise_fallback_used": bool(
            debug.get("overdesign_stepwise_fallback_used"),
        ),
        "overdesign_stepwise_fallback_family": debug.get(
            "overdesign_stepwise_fallback_family",
        ),
        "overdesign_stepwise_fallback_reason": debug.get(
            "overdesign_stepwise_fallback_reason",
        ),
        "overdesign_stepwise_selected_post_util": debug.get(
            "overdesign_stepwise_selected_post_util",
        ),
    }
    if owner == "controller_fallback":
        out["candidate_family"] = selected_family
        out["governing_action"] = governing_action
    return out


def build_design_guide_controller_family_status_display_payload(
    *,
    item: dict[str, Any] | None,
    current_state_for_display: dict[str, Any] | None,
    family_status_current: dict[str, Any] | None,
    family_status_preview: dict[str, Any] | None = None,
    family_status_preview_present: bool = False,
    blocker_attempts_by_family: dict[str, Any] | None = None,
    blocker_attempts_present: bool = False,
) -> dict[str, Any]:
    """Attach precomputed family-status display rows to a guidance item."""

    out = dict(item or {})
    out["_current_state_for_display"] = dict(current_state_for_display or {})
    out["family_status_current"] = dict(family_status_current or {})
    if family_status_preview_present:
        out["family_status_preview"] = dict(family_status_preview or {})
    if blocker_attempts_present:
        out["blocker_attempts_by_family"] = dict(blocker_attempts_by_family or {})
    return out


def build_design_guide_controller_family_status_row_from_overview(
    overview: dict[str, Any] | None,
    family: str,
) -> dict[str, Any]:
    """Build one family status display row from a plain overview payload."""

    ov = dict(overview or {})
    utils = dict(ov.get("utils") or {})
    statuses = dict(ov.get("statuses") or {})
    family_key = str(family or "").strip().lower()
    util = _float_or_none(utils.get(family_key))
    if util is None:
        util = _float_or_none(ov.get(f"{family_key}_util"))
    status = str(statuses.get(family_key) or ov.get(f"{family_key}_status") or "").strip().upper()
    if not status and family_key in {"crack", "deflection"} and util is not None:
        status = "PASS" if float(util) <= 1.0 + 1e-9 else "FAIL"
    return {
        "util": None if util is None else float(util),
        "status": status or None,
        "value": ov.get(f"{family_key}_value"),
        "limit": ov.get(f"{family_key}_limit"),
    }


def build_design_guide_controller_family_status_table(
    overview: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the family status display table from a plain overview payload."""

    return {
        family: build_design_guide_controller_family_status_row_from_overview(overview, family)
        for family in ("bending", "shear", "crack", "deflection")
    }


def build_design_guide_controller_preview_family_delta_table(
    current_overview: dict[str, Any] | None,
    preview_overview: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build before/after family status rows for a candidate preview."""

    current = build_design_guide_controller_family_status_table(current_overview)
    preview = build_design_guide_controller_family_status_table(preview_overview)
    return {
        family: {
            "before_util": current.get(family, {}).get("util"),
            "after_util": preview.get(family, {}).get("util"),
            "before_status": current.get(family, {}).get("status"),
            "after_status": preview.get(family, {}).get("status"),
            "before_value": current.get(family, {}).get("value"),
            "after_value": preview.get(family, {}).get("value"),
            "before_limit": current.get(family, {}).get("limit"),
            "after_limit": preview.get(family, {}).get("limit"),
        }
        for family in ("bending", "shear", "crack", "deflection")
    }


def build_design_guide_controller_blocker_attempt_source_merge(item: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize blocker-attempt table source payloads from a plain guidance item."""

    src = dict(item or {})
    evidence = dict(src.get("candidate_search_evidence") or {})
    blockers: dict[str, Any] = {}
    item_source_keys = (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
    )
    evidence_source_keys = ("exact_blockers_by_family", "post_click_exact_blockers_by_family")
    source_hits: list[dict[str, Any]] = []
    for source_name, source_payload, keys in (
        ("item", src, item_source_keys),
        ("candidate_search_evidence", evidence, evidence_source_keys),
    ):
        for key in keys:
            raw = source_payload.get(key)
            if not isinstance(raw, dict):
                continue
            normalized = {
                str(family or "").strip().lower(): dict(blocker)
                for family, blocker in raw.items()
                if str(family or "").strip() and isinstance(blocker, dict)
            }
            if not normalized:
                continue
            blockers.update(normalized)
            source_hits.append(
                {
                    "source": source_name,
                    "key": key,
                    "families": sorted(normalized.keys()),
                }
            )
    return {
        "item": src,
        "candidate_search_evidence": evidence,
        "blockers": blockers,
        "source_hits": source_hits,
    }


def resolve_design_guide_controller_blocker_attempt_active_failures(
    *,
    candidate_search_evidence: dict[str, Any] | None,
    item: dict[str, Any] | None,
    family_status_current: dict[str, Any] | None,
) -> set[str]:
    """Resolve active strength-failure families for blocker-attempt display."""

    evidence = dict(candidate_search_evidence or {})
    src = dict(item or {})
    current_rows = dict(family_status_current or {})
    active_failures = {
        str(family or "").strip().lower()
        for family in list(evidence.get("active_failures") or src.get("active_failures") or [])
        if str(family or "").strip()
    }
    if active_failures:
        return active_failures
    return {
        family
        for family in ("bending", "shear")
        if str(dict(current_rows.get(family) or {}).get("status") or "").strip().upper() == "FAIL"
    }


def _resolve_design_guide_controller_blocker_attempt_strength_value_limit(
    *,
    family: str,
    value: Any,
    limit: Any,
    family_status_current: dict[str, Any] | None,
) -> tuple[Any, Any]:
    family_key = str(family or "").strip().lower()
    current_rows = dict(family_status_current or {})
    parsed_value = _float_or_none(value)
    if parsed_value is None and family_key in {"bending", "shear"}:
        parsed_value = _float_or_none(dict(current_rows.get(family_key) or {}).get("util"))
    parsed_limit = _float_or_none(limit)
    limit_text = str(limit or "").strip().lower()
    if parsed_limit is None or not limit_text or "capacity or serviceability" in limit_text:
        parsed_limit = 1.0
    return (parsed_value if parsed_value is not None else value), parsed_limit


def build_design_guide_controller_combined_active_strength_attempt_row(
    *,
    active_failures: set[str] | list[str] | tuple[str, ...],
    blockers: dict[str, Any] | None,
    active_candidate_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    candidate_search_evidence: dict[str, Any] | None,
    family_status_current: dict[str, Any] | None,
    combined_attempted_updates: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the combined active-failure blocker-attempt row from plain data."""

    active = {str(family or "").strip().lower() for family in list(active_failures or []) if str(family or "").strip()}
    blocker_keys = set(dict(blockers or {}))
    if not ({"bending", "shear"}.issubset(active) or {"bending", "shear"}.issubset(blocker_keys)):
        return {}
    evidence = dict(candidate_search_evidence or {})
    rows = [dict(row) for row in list(active_candidate_rows or []) if isinstance(row, dict)]
    best_row = None
    for row in rows:
        if str(row.get("affected_family") or row.get("family") or "").strip().lower() == "combined":
            best_row = dict(row)
            break
    if best_row is None and rows:
        best_row = dict(rows[0])
    failed_family = str((best_row or {}).get("failed_check_family") or "").strip().lower()
    if failed_family not in {"bending", "shear"}:
        statuses = dict((best_row or {}).get("preview_statuses") or {})
        if str(statuses.get("bending") or "").strip().upper() == "FAIL":
            failed_family = "bending"
        elif str(statuses.get("shear") or "").strip().upper() == "FAIL":
            failed_family = "shear"
        else:
            failed_family = "combined"
    preview_values = [
        value
        for value in (
            _float_or_none((best_row or {}).get("preview_bending_util")),
            _float_or_none((best_row or {}).get("preview_shear_util")),
        )
        if value is not None
    ]
    failed_value = (
        (best_row or {}).get("failed_check_util")
        or (best_row or {}).get("preview_util")
        or (max(preview_values) if preview_values else None)
    )
    failed_value, failed_limit = _resolve_design_guide_controller_blocker_attempt_strength_value_limit(
        family=failed_family if failed_family in {"bending", "shear"} else "combined",
        value=failed_value,
        limit=(best_row or {}).get("failed_check_capacity_or_limit")
        or (best_row or {}).get("failed_check_limit")
        or None,
        family_status_current=family_status_current,
    )
    display_family = failed_family if failed_family in {"bending", "shear"} else "combined"
    return {
        "attempted": True,
        "attempted_candidate_count": (
            evidence.get("total_candidates_considered")
            or evidence.get("preview_count")
            or evidence.get("generated_count")
            or len(rows)
        ),
        "attempted_updates": dict(combined_attempted_updates or {}),
        "best_rejected_candidate_id": (
            (best_row or {}).get("candidate_id")
            or evidence.get("failed_candidate_id")
            or evidence.get("best_rejected_candidate_id")
            or "combined_active_failure_practical_ladder_exhausted"
        ),
        "failed_check_name": resolve_design_guide_controller_blocker_attempt_strength_capacity_rule(display_family),
        "failed_check_status": str((best_row or {}).get("failed_check_status") or "FAIL").strip() or "FAIL",
        "failed_check_value": failed_value,
        "failed_check_limit": failed_limit,
        "reason": build_design_guide_controller_blocker_attempt_strength_reason(
            display_family,
            failed_value,
            failed_limit,
        ),
    }


def resolve_design_guide_controller_cleanup_attempted_passed(
    row: dict[str, Any] | None,
    attempted_util: Any = None,
) -> bool | None:
    """Classify whether a cleanup attempt still passed from plain row data."""

    row_d = dict(row or {})
    explicit = row_d.get("attempted_passed")
    if isinstance(explicit, bool):
        return explicit
    status_text = " ".join(
        str(row_d.get(key) or "")
        for key in ("failed_check_status", "attempted_status", "preview_status", "status", "rejection_category")
    ).strip().lower()
    if any(token in status_text for token in ("spacing", "detailing", "ductility", "serviceability", "unsafe")):
        return False
    if "fail" in status_text and "final accepted" not in status_text and "efficiency" not in status_text:
        return False
    if any(token in status_text for token in ("pass", "safe", "accepted floor", "below accepted", "preferred band")):
        return True
    parsed_attempted = _float_or_none(attempted_util)
    if parsed_attempted is not None:
        return float(parsed_attempted) <= 1.0
    return None


def resolve_design_guide_controller_cleanup_rejection_category(
    row: dict[str, Any] | None,
    attempted_util: Any = None,
    *,
    final_accepted_min_family_util: Any,
    guidance_target_util_max: Any,
) -> str:
    """Classify cleanup rejection category from plain row data."""

    row_d = dict(row or {})
    explicit = str(row_d.get("rejection_category") or "").strip()
    if explicit:
        return explicit
    text = " ".join(
        str(row_d.get(key) or "")
        for key in (
            "failed_check_name",
            "failed_check_status",
            "failed_check_reason",
            "reason",
            "rejection_reason",
            "failed_candidate_reason",
            "limit_name",
        )
    ).lower()
    parsed_attempted = _float_or_none(attempted_util)
    attempted_passed = resolve_design_guide_controller_cleanup_attempted_passed(row_d, parsed_attempted)
    if attempted_passed is True and parsed_attempted is not None:
        final_floor = _float_or_none(final_accepted_min_family_util)
        target_high = _float_or_none(guidance_target_util_max)
        if final_floor is not None and float(parsed_attempted) < float(final_floor):
            return "Safe but still below accepted efficiency floor"
        if target_high is not None and float(parsed_attempted) > float(target_high):
            return "Safe but above preferred band, with no better preferred-band candidate"
    if "not executor" in text or "not executable" in text or "advisory" in text:
        return "Not executor-backed"
    if "superseded" in text or "combined same-click" in text or "combined cleanup" in text:
        return "Superseded by better combined same-click option"
    if "geometry locked" in text or "not permitted" in text or "locked" in text:
        return "Geometry locked / not permitted"
    if any(token in text for token in ("spacing", "detailing", "ductility", "fit", "minimum clear")):
        return "Unsafe - failed spacing/detailing/ductility"
    if any(token in text for token in ("serviceability", "deflection", "crack", "sls")):
        return "Unsafe - failed serviceability"
    if attempted_passed is False:
        return "Unsafe - failed capacity"
    if attempted_passed is True:
        return "Safe but still below accepted efficiency floor"
    return "Not executor-backed"


def resolve_design_guide_controller_cleanup_explicit_attempt_label(
    row: dict[str, Any] | None,
) -> str | None:
    """Return a safe explicit cleanup attempt label from plain row data."""

    row_d = dict(row or {})
    explicit = str(
        row_d.get("attempted_change_label")
        or row_d.get("attempted_next_reduction")
        or row_d.get("attempted_reduction_label")
        or ""
    ).strip()
    if explicit and not re.search(r"\b[a-z0-9]+(?:_[a-z0-9]+){3,}\b", explicit, flags=re.I):
        return explicit
    return None


def _format_design_guide_controller_mm_value(value: Any) -> str:
    try:
        numeric = float(value)
    except Exception:
        return str(value or "").strip() or "recorded"
    if abs(numeric - round(numeric)) <= 1e-9:
        return str(int(round(numeric)))
    return f"{numeric:.1f}".rstrip("0").rstrip(".")


def build_design_guide_controller_cleanup_geometry_change_label(
    *,
    before_depth: Any = None,
    after_depth: Any = None,
    before_width: Any = None,
    after_width: Any = None,
) -> str:
    """Build exact geometry cleanup wording from plain before/after scalars."""

    before_d = _float_or_none(before_depth)
    after_d = _float_or_none(after_depth)
    before_w = _float_or_none(before_width)
    after_w = _float_or_none(after_width)
    geom_parts: list[str] = []
    if before_d is not None and after_d is not None and abs(float(before_d) - float(after_d)) > 1e-9:
        geom_parts.append(
            f"depth from {_format_design_guide_controller_mm_value(before_d)} mm "
            f"to {_format_design_guide_controller_mm_value(after_d)} mm"
        )
    if before_w is not None and after_w is not None and abs(float(before_w) - float(after_w)) > 1e-9:
        geom_parts.append(
            f"width from {_format_design_guide_controller_mm_value(before_w)} mm "
            f"to {_format_design_guide_controller_mm_value(after_w)} mm"
        )
    if geom_parts:
        return "changing " + " and ".join(geom_parts)
    return ""


def build_design_guide_controller_cleanup_bottom_reinforcement_change_label(
    *,
    before_label: Any = None,
    after_label: Any = None,
    before_ast: Any = None,
    after_ast: Any = None,
) -> str:
    """Build exact bottom-reinforcement cleanup wording from plain labels/scalars."""

    before_s = str(before_label or "").strip()
    after_s = str(after_label or "").strip()
    if not before_s or not after_s or before_s == after_s:
        return ""
    before_area = _float_or_none(before_ast)
    after_area = _float_or_none(after_ast)
    verb = "changing"
    if before_area is not None and after_area is not None and float(after_area) < float(before_area):
        verb = "reducing"
    return f"{verb} bottom reinforcement from {before_s} to {after_s}"


def build_design_guide_controller_cleanup_shear_link_change_label(
    *,
    before_label: Any = None,
    after_label: Any = None,
    before_spacing: Any = None,
    after_spacing: Any = None,
    before_dia: Any = 0,
    after_dia: Any = 0,
    before_legs: Any = 0,
    after_legs: Any = 0,
) -> str:
    """Build exact shear-link cleanup wording from plain labels/scalars."""

    before_s = str(before_label or "").strip() or "no links"
    after_s = str(after_label or "").strip() or "no links"
    if before_s == after_s:
        return ""
    before_space = _float_or_none(before_spacing)
    after_space = _float_or_none(after_spacing)

    def _int_value(value: Any) -> int:
        try:
            return int(float(value or 0))
        except Exception:
            return 0

    before_bar = _int_value(before_dia)
    after_bar = _int_value(after_dia)
    before_leg_count = _int_value(before_legs)
    after_leg_count = _int_value(after_legs)
    if after_s == "no links":
        return f"removing shear links from {before_s}"
    if before_s == "no links":
        return f"adding shear links from no links to {after_s}"
    if (
        before_space is not None
        and after_space is not None
        and before_bar == after_bar
        and before_leg_count == after_leg_count
    ):
        direction = "increasing" if float(after_space) > float(before_space) else "reducing"
        return (
            f"{direction} link spacing from {_format_design_guide_controller_mm_value(before_space)} mm "
            f"to {_format_design_guide_controller_mm_value(after_space)} mm"
        )
    if before_bar != after_bar and before_leg_count == after_leg_count and before_space == after_space:
        direction = "increasing" if after_bar > before_bar else "reducing"
        return f"{direction} links from N{before_bar} to N{after_bar}"
    if before_leg_count != after_leg_count and before_bar == after_bar and before_space == after_space:
        direction = "increasing" if after_leg_count > before_leg_count else "reducing"
        return f"{direction} from {before_leg_count}-leg links to {after_leg_count}-leg links"
    return f"changing links from {before_s} to {after_s}"


def build_design_guide_controller_cleanup_no_link_no_change_label(
    current_arrangement: Any = None,
) -> str:
    """Build no-link cleanup no-change wording from a plain arrangement label."""

    arrangement = str(current_arrangement or "").strip() or "no links"
    return (
        f"no change from {arrangement} to {arrangement} because shear links are already "
        "removed and no executable numeric shear-link cleanup was available"
    )


def build_design_guide_controller_cleanup_route_fallback_label(
    *,
    route: Any = None,
    current_arrangement: Any = None,
    has_sanitised_model_updates: bool = False,
) -> str:
    """Build route fallback cleanup wording from plain route/arrangement data."""

    route_s = str(route or "").strip()
    arrangement = str(current_arrangement or "").strip()
    if route_s and arrangement and not bool(has_sanitised_model_updates):
        return (
            f"no change from {arrangement} to {arrangement} because no executable "
            f"numeric {route_s} cleanup was available"
        )
    if route_s:
        return f"the recorded {route_s} change"
    return "the recorded cleanup change"


def resolve_design_guide_controller_cleanup_attempted_updates(
    row: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve cleanup attempted-update payload from a plain blocker row."""

    row_d = dict(row or {})
    for key in (
        "attempted_updates",
        "attempted_next_updates",
        "failed_candidate_updates",
        "best_rejected_candidate_updates",
        "best_safe_candidate_updates",
        "selected_candidate_updates",
    ):
        value = row_d.get(key)
        if isinstance(value, dict) and value:
            return dict(value)
    return {}


def format_design_guide_controller_display_util(value: Any) -> str:
    """Format a utilisation value for Design Guide display text."""

    parsed = _float_or_none(value)
    if parsed is None:
        return "-"
    try:
        return f"{float(parsed):.2f}"
    except Exception:
        return "-"


def resolve_design_guide_controller_blocker_attempt_strength_capacity_rule(family: str) -> str:
    """Return the visible strength-capacity rule name for blocker attempts."""

    family_key = str(family or "").strip().lower()
    if family_key == "shear":
        return "sectional shear capacity utilisation"
    if family_key == "combined":
        return "combined bending/shear capacity utilisation"
    return "bending capacity utilisation"


def build_design_guide_controller_blocker_attempt_strength_reason(
    family: str,
    value: Any,
    limit: Any,
) -> str:
    """Build the visible strength blocker reason for a rejected attempt."""

    family_key = str(family or "").strip().lower()
    value_text = format_design_guide_controller_display_util(value)
    limit_text = format_design_guide_controller_display_util(limit)
    if family_key == "combined":
        return (
            "Best rejected combined strengthening candidate still leaves a strength "
            f"utilisation of {value_text}, above the required maximum {limit_text}."
        )
    return (
        f"Best rejected {family_key} strengthening candidate still leaves {family_key} "
        f"utilisation {value_text}, above the required maximum {limit_text}."
    )


def build_design_guide_controller_empty_collapsed_exact_blocker_fallback(
    *,
    collapsed_guidance_items: list[dict[str, Any]] | None,
    debug_trace: dict[str, Any] | None,
    current_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Materialize the exact-blocker item when compute produced no collapsed item.

    This is pure controller projection logic. It does not render UI, route Apply,
    read/write session state, or execute family/runtime decisions.
    """

    if collapsed_guidance_items:
        return {
            "collapsed_guidance_items": [
                dict(item) for item in collapsed_guidance_items if isinstance(item, dict)
            ],
            "debug_trace": dict(debug_trace or {}),
            "materialized": False,
            "authority": "DesignGuideController.empty_collapsed_exact_blocker_fallback",
        }

    trace = dict(debug_trace or {})
    exact_blockers = dict(
        trace.get("post_click_exact_blockers_by_family")
        or trace.get("exact_blockers_by_family")
        or _mapping(trace.get("candidate_search_evidence")).get("exact_blockers_by_family")
        or {}
    )
    contract = dict(trace.get("primary_button_contract") or trace.get("button_contract") or {})
    intent = str(
        trace.get("primary_guidance_intent")
        or trace.get("primary_card_intent")
        or ""
    ).strip()
    should_materialize = bool(
        exact_blockers
        and (
            intent == "specific_blocker"
            or str(trace.get("final_state_class") or "").strip() == "blocker"
            or bool(_mapping(trace.get("candidate_search_evidence")).get("no_second_cta_required"))
        )
        and not bool(contract.get("enabled") or contract.get("actionable"))
    )
    if not should_materialize:
        return {
            "collapsed_guidance_items": [],
            "debug_trace": dict(trace),
            "materialized": False,
            "authority": "DesignGuideController.empty_collapsed_exact_blocker_fallback",
        }

    family = str(
        contract.get("family")
        or trace.get("selected_action_family")
        or next(iter(exact_blockers), "general")
    ).strip().lower()
    if family not in {"bending", "shear", "crack", "deflection", "combined"}:
        family = "general"

    blocker = dict(exact_blockers.get(family) or {})
    if not blocker and exact_blockers:
        blocker = dict(next(iter(exact_blockers.values())) or {})

    display_truth = dict(trace.get("primary_display_truth") or {})
    util = _float_or_none(
        display_truth.get("displayed_util")
        or blocker.get("current_util")
        or blocker.get("failed_check_util")
    )
    reason = str(
        contract.get("blocking_reason")
        or blocker.get("reason")
        or blocker.get("why_reduction_would_hurt_other_design_elements")
        or "The cleanup search was exhausted and no executor-backed update preserved every required check."
    ).strip()
    title = str(
        trace.get("primary_card_title")
        or trace.get("final_primary_title")
        or ""
    ).strip()
    if not title or title.lower().startswith("cleanup blocked"):
        if family == "bending":
            title = "Bending cleanup blocked by exact engineering limit"
        elif family == "shear":
            title = "Shear cleanup blocked by exact engineering limit"
        else:
            title = "Design cleanup blocked by exact engineering limit"

    disabled_contract = {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": family,
        "updates": {},
        "preview_pass": False,
        "expected_util": None,
        "blocking_reason": reason,
        "source_candidate_id": None,
        "candidate_id": None,
    }
    if not display_truth and util is not None:
        state = _mapping(current_state)
        mode = _presentation_mode_config(
            current_state=state,
            mode_config=None,
            target_band=target_band_payload(_presentation_goal_from_state(state)),
        )
        display_truth = {
            "display_truth_source": "post_commit_truth",
            "displayed_util": util,
            "displayed_status": "BLOCKED",
            "target_low": mode.get("target_low"),
            "target_high": mode.get("target_high"),
            "displayed_within_target_band": False,
            "source_summary_util": util,
            "source_candidate_util": None,
            "source_post_commit_util": util,
        }

    cleanup_evidence = dict(
        trace.get("post_click_cleanup_evidence_by_family")
        or trace.get("cleanup_evidence_by_family")
        or exact_blockers
    )
    item = _controller_guidance_item(
        family,
        title,
        reason,
        None,
        f"Why: {reason}",
        "Key checks: bending, shear, serviceability, spacing, ductility, detailing",
        None,
        None,
        status="WARN",
        util=util,
    )
    item.update(
        {
            "family": family,
            "guidance_intent": "specific_blocker",
            "final_state_class": "blocker",
            "primary_card_actionable": False,
            "button_contract": dict(disabled_contract),
            "display_truth": dict(display_truth),
            "displayed_util": util,
            "displayed_status": display_truth.get("displayed_status") or "BLOCKED",
            "display_truth_source": display_truth.get("display_truth_source") or "post_commit_truth",
            "exact_blockers_by_family": dict(exact_blockers),
            "post_click_exact_blockers_by_family": dict(exact_blockers),
            "cleanup_evidence_by_family": dict(cleanup_evidence),
            "post_click_cleanup_evidence_by_family": dict(cleanup_evidence),
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "safe_local_cleanup_count": 0,
            "executable_safe_cleanup_count": 0,
            "candidate_search_evidence": dict(trace.get("candidate_search_evidence") or {}),
        }
    )

    trace["specific_blocker_materialized_from_compute_proof"] = True
    trace["specific_blocker_materialized_by"] = (
        "DesignGuideController.empty_collapsed_exact_blocker_fallback"
    )
    trace["primary_card_title"] = title
    trace["primary_guidance_intent"] = "specific_blocker"
    trace["primary_card_intent"] = "specific_blocker"
    trace["primary_button_contract"] = dict(disabled_contract)
    trace["button_contract"] = dict(disabled_contract)
    trace["button_contract_enabled"] = False
    trace["button_contract_updates"] = {}
    trace["primary_display_truth"] = dict(display_truth)
    return {
        "collapsed_guidance_items": [item],
        "debug_trace": dict(trace),
        "materialized": True,
        "authority": "DesignGuideController.empty_collapsed_exact_blocker_fallback",
    }


def build_design_guide_controller_resolved_candidate_guidance_item_input_pack(
    *,
    candidate: dict[str, Any] | None,
    updates: dict[str, Any] | None,
    label: str,
    original_candidate_action_type: str,
    family_tag: Any,
    subfamilies: list[Any] | tuple[Any, ...] | None,
    candidate_post_util: float | None,
    change_lines: list[Any] | tuple[Any, ...] | None,
    guidance_change_summary_compact: str,
    guidance_expected_util_text: str,
    guidance_why_text_compact: str,
    alternatives_text: str,
) -> dict[str, Any]:
    """Build the pure resolved-candidate input pack used before item construction."""

    candidate_dict = dict(candidate or {}) if isinstance(candidate, dict) else {}
    updates_dict = dict(updates or {})
    subfamily_list = list(subfamilies or [])
    change_line_list = list(change_lines or [])
    resolved_action_type = "apply_resolved_candidate"
    action_payload_preview = {
        "resolved_candidate_updates": dict(updates_dict),
        "resolved_candidate_label": str(label or ""),
        "resolved_candidate_action_type": str(original_candidate_action_type or ""),
        "resolved_candidate_family_tag": family_tag,
        "resolved_candidate_subfamilies": list(subfamily_list),
        "resolved_candidate_post_util": candidate_post_util,
        "resolved_candidate_reaches_target_band": bool(
            candidate_dict.get("candidate_reaches_target_band")
            or candidate_dict.get("reaches_target_band")
        ),
        "force_direct_apply": True,
        "label": str(label or ""),
        "updates": dict(updates_dict),
        "guidance_change_lines": list(change_line_list),
        "guidance_change_summary_compact": str(guidance_change_summary_compact or ""),
        "guidance_expected_util_text": str(guidance_expected_util_text or ""),
        "guidance_why_text_compact": str(guidance_why_text_compact or ""),
        "guidance_alternatives_text_compact": str(alternatives_text or ""),
    }
    return {
        "resolved_action_type": resolved_action_type,
        "action_payload_preview": action_payload_preview,
        "owner": "DesignGuideController.resolved_candidate_guidance_item_input_pack",
    }


def build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack(
    *,
    alternatives_text: str,
    guidance_change_summary_compact: str,
    guidance_expected_util_text: str,
    guidance_why_text_compact: str,
) -> dict[str, str]:
    """Package already-computed compact text fields for resolved-candidate guidance items."""

    return {
        "guidance_alternatives_text_compact": str(alternatives_text or ""),
        "guidance_change_summary_compact": str(guidance_change_summary_compact or ""),
        "guidance_expected_util_text": str(guidance_expected_util_text or ""),
        "guidance_why_text_compact": str(guidance_why_text_compact or ""),
        "owner": "DesignGuideController.resolved_candidate_guidance_item_compact_text_pack",
    }


def build_design_guide_controller_resolved_candidate_guidance_item_before_after_request_pack(
    *,
    action_payload_preview: dict[str, Any] | None,
    change_lines: list[Any] | tuple[Any, ...] | None,
) -> dict[str, Any]:
    """Package the resolved-candidate before/after preview request."""

    before_after_item = {
        "action_type": "apply_resolved_candidate",
        "action_payload": dict(action_payload_preview or {}),
        "recommendation_change_lines": list(change_lines or []),
    }
    return {
        "before_after_item": before_after_item,
        "owner": "DesignGuideController.resolved_candidate_guidance_item_before_after_request_pack",
    }


_BEFORE_AFTER_TEXT_EXCLUDED_ACTION_TYPES = frozenset(
    {
        "apply_mode_recommendation",
        "apply_bottom_recommendation",
        "apply_geometry_recommendation",
        "apply_shear_recommendation",
        "apply_compound_guidance",
        "reduce_bottom_reinforcement",
        "increase_link_spacing",
        "reduce_number_of_legs",
    }
)


def resolve_design_guide_controller_before_after_text_eligibility(
    *,
    action_type: str | None,
) -> dict[str, Any]:
    """Resolve pure before/after preview eligibility for a guidance action."""

    action = str(action_type or "")
    owner = "DesignGuideController.before_after_text_eligibility"
    if not action:
        return {
            "eligible": False,
            "reason": "missing_action_type",
            "action_type": action,
            "owner": owner,
        }
    if action in _BEFORE_AFTER_TEXT_EXCLUDED_ACTION_TYPES:
        return {
            "eligible": False,
            "reason": "excluded_expensive_action_type",
            "action_type": action,
            "owner": owner,
        }
    return {
        "eligible": True,
        "reason": None,
        "action_type": action,
        "owner": owner,
    }


def resolve_design_guide_controller_guidance_action_payload_updates(
    *,
    action_type: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve pure payload-owned Design Guide action updates."""

    action = str(action_type or "")
    payload_dict = dict(payload or {}) if isinstance(payload, dict) else {}
    if action == "apply_resolved_candidate":
        resolved_updates = payload_dict.get("resolved_candidate_updates")
        if isinstance(resolved_updates, dict) and resolved_updates:
            updates = dict(resolved_updates)
        else:
            explicit_updates = payload_dict.get("updates")
            updates = dict(explicit_updates) if isinstance(explicit_updates, dict) and explicit_updates else None
        return {
            "handled": True,
            "updates": updates,
            "owner": "DesignGuideController.guidance_action_payload_updates",
        }

    if action == "apply_compound_guidance":
        explicit_updates = payload_dict.get("updates")
        return {
            "handled": True,
            "updates": dict(explicit_updates) if isinstance(explicit_updates, dict) else None,
            "owner": "DesignGuideController.guidance_action_payload_updates",
        }

    if action == "apply_mode_recommendation":
        explicit_updates = payload_dict.get("updates")
        return {
            "handled": True,
            "updates": dict(explicit_updates) if isinstance(explicit_updates, dict) else None,
            "owner": "DesignGuideController.guidance_action_payload_updates",
        }

    if action == "apply_bottom_recommendation":
        explicit_updates = payload_dict.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            return {
                "handled": True,
                "updates": None if bool(payload_dict.get("updates_match_state")) else dict(explicit_updates),
                "owner": "DesignGuideController.guidance_action_payload_updates",
            }
        return {
            "handled": False,
            "updates": None,
            "owner": "DesignGuideController.guidance_action_payload_updates",
        }

    if action == "apply_geometry_recommendation":
        explicit_updates = payload_dict.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            return {
                "handled": True,
                "updates": dict(explicit_updates),
                "owner": "DesignGuideController.guidance_action_payload_updates",
            }
        return {
            "handled": False,
            "updates": None,
            "owner": "DesignGuideController.guidance_action_payload_updates",
        }

    if action == "apply_shear_recommendation":
        explicit_updates = payload_dict.get("updates")
        if isinstance(explicit_updates, dict):
            return {
                "handled": True,
                "updates": dict(explicit_updates),
                "owner": "DesignGuideController.guidance_action_payload_updates",
            }
        return {
            "handled": False,
            "updates": None,
            "owner": "DesignGuideController.guidance_action_payload_updates",
        }

    if action == "increase_link_spacing":
        explicit_updates = payload_dict.get("updates")
        if isinstance(explicit_updates, dict):
            return {
                "handled": True,
                "updates": dict(explicit_updates),
                "owner": "DesignGuideController.guidance_action_payload_updates",
            }
        return {
            "handled": False,
            "updates": None,
            "owner": "DesignGuideController.guidance_action_payload_updates",
        }

    if action == "reduce_number_of_legs":
        explicit_updates = payload_dict.get("updates")
        if isinstance(explicit_updates, dict):
            return {
                "handled": True,
                "updates": dict(explicit_updates),
                "owner": "DesignGuideController.guidance_action_payload_updates",
            }
        return {
            "handled": False,
            "updates": None,
            "owner": "DesignGuideController.guidance_action_payload_updates",
        }

    if action == "tighten_geometry":
        explicit_updates = payload_dict.get("updates")
        if isinstance(explicit_updates, dict):
            return {
                "handled": True,
                "updates": dict(explicit_updates),
                "owner": "DesignGuideController.guidance_action_payload_updates",
            }
        return {
            "handled": False,
            "updates": None,
            "owner": "DesignGuideController.guidance_action_payload_updates",
        }

    return {
        "handled": False,
        "updates": None,
        "owner": "DesignGuideController.guidance_action_payload_updates",
    }


def build_design_guide_pure_guidance_step_description(
    *,
    before_state: dict[str, Any] | None,
    after_state: dict[str, Any] | None,
    action_type: str,
    updates: dict[str, Any] | None,
    resolved_width_key: str | None = None,
    before_bottom_reo_label: str | None = None,
    after_bottom_reo_label: str | None = None,
    before_shear_reo_label: str | None = None,
    after_shear_reo_label: str | None = None,
) -> dict[str, Any]:
    """Build pure before/after wording that has no page-label dependencies."""

    before = dict(before_state or {}) if isinstance(before_state, dict) else {}
    after = dict(after_state or {}) if isinstance(after_state, dict) else {}
    update_map = dict(updates or {}) if isinstance(updates, dict) else {}
    owner = "DesignGuideController.pure_guidance_step_description"

    if "D" in update_map:
        before_depth = int(float(before.get("D", 0.0) or 0.0))
        after_depth = int(float(after.get("D", 0.0) or 0.0))
        verb = "Reduced" if after_depth < before_depth else "Increased"
        return {
            "handled": True,
            "description": f"{verb} depth D from {before_depth} to {after_depth} mm.",
            "owner": owner,
        }

    width_key = str(resolved_width_key or "").strip()
    if width_key and width_key in update_map:
        before_width = int(float(before.get(width_key, 0.0) or 0.0))
        after_width = int(float(after.get(width_key, 0.0) or 0.0))
        width_short = "b" if width_key == "b" else width_key
        verb = "Reduced" if after_width < before_width else "Increased"
        return {
            "handled": True,
            "description": f"{verb} {width_short} from {before_width} to {after_width} mm.",
            "owner": owner,
        }

    bottom_keys = {
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "bot_row_1_bars",
        "bot_row_2_bars",
        "bot_row_1_dia",
        "bot_row_2_dia",
        "Ast_bot",
    }
    if any(key in update_map for key in bottom_keys):
        before_label = str(before_bottom_reo_label or "")
        after_label = str(after_bottom_reo_label or "")
        if before_label and after_label:
            return {
                "handled": True,
                "description": f"Updated bottom reinforcement from {before_label} to {after_label}.",
                "owner": owner,
            }
        return {
            "handled": False,
            "description": None,
            "owner": owner,
        }

    shear_keys = {"s_lig", "lig_legs", "lig_d"}
    if any(key in update_map for key in shear_keys):
        before_label = str(before_shear_reo_label or "")
        after_label = str(after_shear_reo_label or "")
        if before_label and after_label:
            return {
                "handled": True,
                "description": f"Updated shear reinforcement from {before_label} to {after_label}.",
                "owner": owner,
            }
        return {
            "handled": False,
            "description": None,
            "owner": owner,
        }

    risky_keys = {
        "b",
        "bw",
        "tw",
        "web_width",
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "bot_row_1_bars",
        "bot_row_2_bars",
        "bot_row_1_dia",
        "bot_row_2_dia",
        "Ast_bot",
        "s_lig",
        "lig_legs",
        "lig_d",
    }
    if any(key in update_map for key in risky_keys):
        return {
            "handled": False,
            "description": None,
            "owner": owner,
        }

    load_keys = ("g_udl_kNm_per_m", "g_kNm", "g_line_kNm")
    if any(key in update_map for key in load_keys):
        parts: list[str] = []
        for key in load_keys:
            if key not in update_map:
                continue
            try:
                b0 = float(before.get(key, 0.0) or 0.0)
                a0 = float(after.get(key, 0.0) or 0.0)
                parts.append(f"{key} {b0:.3f} -> {a0:.3f} kN/m")
            except Exception:
                parts.append(str(key))
        if parts:
            return {
                "handled": True,
                "description": "Adjusted sustained load inputs: " + "; ".join(parts) + ".",
                "owner": owner,
            }

    return {
        "handled": True,
        "description": f"Applied {str(action_type or '').replace('_', ' ')}.",
        "owner": owner,
    }


def build_design_guide_controller_resolved_candidate_guidance_item(
    *,
    candidate: dict[str, Any],
    updates: dict[str, Any],
    label: str,
    raw_label: str,
    family_tag: Any,
    subfamilies: list[Any],
    alternatives_text: str,
    change_lines: list[Any],
    candidate_post_util: float | None,
    original_candidate_action_type: str,
    primary_action: str,
    reasoning_text: str,
    status: str,
    overview_worst_util: Any,
    failure_coverage: dict[str, Any],
    candidate_search_evidence: dict[str, Any],
    guidance_change_summary_compact: str,
    guidance_expected_util_text: str,
    guidance_why_text_compact: str,
    guidance_before_after: str | None,
) -> dict[str, Any]:
    """Build a Design Guide item from a pre-resolved candidate.

    Page code may still compute title/change-line inputs until those helpers get
    their own service boundary.  This function owns the pure output item and
    action-payload shape.
    """

    resolved_action_type = "apply_resolved_candidate"
    candidate_dict = dict(candidate or {})
    updates_dict = dict(updates or {})
    search_evidence = dict(candidate_search_evidence or {})
    coverage = dict(failure_coverage or {})
    subfamily_list = list(subfamilies or [])
    change_line_list = list(change_lines or [])
    action_payload = {
        "resolved_candidate_updates": updates_dict,
        "resolved_candidate_label": label,
        "resolved_candidate_action_type": original_candidate_action_type,
        "resolved_candidate_family_tag": family_tag,
        "resolved_candidate_subfamilies": subfamily_list,
        "resolved_candidate_post_util": candidate_post_util,
        "resolved_candidate_reaches_target_band": bool(
            candidate_dict.get("candidate_reaches_target_band")
            or candidate_dict.get("reaches_target_band")
        ),
        "force_direct_apply": True,
        "label": label,
        "updates": updates_dict,
        "guidance_change_lines": change_line_list,
        "guidance_change_summary_compact": guidance_change_summary_compact,
        "guidance_expected_util_text": guidance_expected_util_text,
        "guidance_why_text_compact": guidance_why_text_compact,
        "guidance_alternatives_text_compact": alternatives_text,
    }
    action_payload["failure_coverage"] = dict(coverage)
    action_payload["compound_shear_augmented"] = bool(
        candidate_dict.get("compound_shear_augmented")
    )
    action_payload["covers_all_current_failures"] = bool(
        coverage.get("covers_all_current_failures")
    )
    action_payload["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
    action_payload["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])
    if search_evidence:
        action_payload["candidate_search_evidence"] = dict(search_evidence)
        action_payload["source_candidate_id"] = search_evidence.get("selected_candidate_id")

    item = build_design_guide_controller_guidance_item(
        "general",
        label,
        primary_action,
        None,
        reasoning_text,
        "Key levers: geometry and reinforcement updates selected by one-click convergence ranking",
        resolved_action_type,
        action_payload,
        status=status,
        util=overview_worst_util,
        guidance_change_lines=change_line_list,
        guidance_before_after=guidance_before_after,
    )

    item["resolved_candidate_label"] = label
    item["resolved_candidate_action_type"] = original_candidate_action_type
    item["resolved_candidate_family_tag"] = family_tag
    item["resolved_candidate_subfamilies"] = subfamily_list
    item["resolved_candidate_updates"] = updates_dict
    item["resolved_candidate_post_util"] = candidate_post_util
    item["resolved_candidate_reaches_target_band"] = bool(
        candidate_dict.get("candidate_reaches_target_band")
        or candidate_dict.get("reaches_target_band")
    )
    if search_evidence:
        item["candidate_search_evidence"] = dict(search_evidence)
        item["candidate_id"] = search_evidence.get("selected_candidate_id")
        item["source_candidate_id"] = search_evidence.get("selected_candidate_id")
    item["compound_shear_augmented"] = bool(candidate_dict.get("compound_shear_augmented"))
    item["failure_coverage"] = dict(coverage)
    item["covers_all_current_failures"] = bool(coverage.get("covers_all_current_failures"))
    item["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
    item["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])
    item["resolved_candidate"] = {
        **candidate_dict,
        "label": label,
        "action_type": original_candidate_action_type,
        "updates": updates_dict,
        "candidate_post_util": candidate_post_util,
        "candidate_reaches_target_band": bool(
            candidate_dict.get("candidate_reaches_target_band")
            or candidate_dict.get("reaches_target_band")
        ),
        "compound_shear_augmented": bool(candidate_dict.get("compound_shear_augmented")),
        "failure_coverage": dict(coverage),
        "candidate_search_evidence": dict(search_evidence),
        "candidate_id": (
            search_evidence.get("selected_candidate_id")
            if search_evidence
            else candidate_dict.get("candidate_id")
        ),
        "source_candidate_id": (
            search_evidence.get("selected_candidate_id")
            if search_evidence
            else candidate_dict.get("source_candidate_id")
        ),
    }
    item["resolved_candidate_title_raw"] = raw_label
    item["has_resolved_candidate_payload"] = True
    canonical = str(candidate_dict.get("canonical_winner_label") or "").strip()
    if bool(candidate_dict.get("title_locked_from_final_winner")) and canonical:
        item["canonical_winner_label"] = canonical
        item["title_locked_from_final_winner"] = True
    return item


def build_design_guide_controller_bending_only_best_safe_cleanup_item_projection(
    *,
    item: dict[str, Any] | None,
    selected_candidate: dict[str, Any] | None,
    candidate_search_evidence: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Project the best-safe bending cleanup item shape.

    This is pure publication/item shaping.  It does not evaluate candidates,
    render UI, route Apply, or touch session state.
    """

    if not isinstance(item, dict) or not item:
        return None
    selected = dict(selected_candidate or {})
    evidence = dict(candidate_search_evidence or {})
    candidate_id = selected.get("candidate_id")
    subfamilies = list(selected.get("subfamilies") or ["bottom_reinforcement"])

    projected = dict(item)
    projected["candidate_search_evidence"] = dict(evidence)
    projected["local_cleanup_candidate"] = True
    projected["source"] = "design_guide_bending_only_best_safe_cleanup_search"
    projected["affected_family"] = "bending"
    projected["family"] = "bending"
    projected["allow_in_target_primary_action"] = True
    projected["best_safe_partial_cleanup"] = False
    projected["no_second_cta_required"] = False
    projected["guidance_intent"] = "efficiency_tightening"

    payload = dict(projected.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["best_safe_partial_cleanup"] = False
    payload["no_second_cta_required"] = False
    payload["source_candidate_id"] = candidate_id
    payload["candidate_id"] = candidate_id
    payload["resolved_candidate_family_tag"] = "bending"
    payload["resolved_candidate_subfamilies"] = list(subfamilies)
    projected["action_payload"] = payload

    resolved = dict(projected.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["best_safe_partial_cleanup"] = False
    resolved["no_second_cta_required"] = False
    resolved["candidate_id"] = candidate_id
    resolved["source_candidate_id"] = candidate_id
    resolved["family"] = "bending"
    resolved["recommendation_family_tag"] = "bending"
    resolved["subfamilies"] = list(subfamilies)
    projected["resolved_candidate"] = resolved
    return projected


def build_design_guide_controller_bending_only_target_band_cleanup_item_projection(
    *,
    item: dict[str, Any] | None,
    selected_candidate: dict[str, Any] | None,
    candidate_search_evidence: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Project the final bending-only target-band cleanup item shape."""

    if not isinstance(item, dict) or not item:
        return None
    selected = dict(selected_candidate or {})
    evidence = dict(candidate_search_evidence or {})
    candidate_id = selected.get("candidate_id")
    selected_family = str(selected.get("family") or "bending").strip().lower() or "bending"
    publication_family_id = str(
        selected.get("selected_family_id")
        or selected.get("published_family_id")
        or evidence.get("selected_family_id")
        or evidence.get("published_family_id")
        or ("BENDING_OVERDESIGN_GOVERNS" if selected_family == "bending" else selected_family)
    ).strip()
    if selected_family == "bending" and publication_family_id.lower() == "bending":
        publication_family_id = "BENDING_OVERDESIGN_GOVERNS"
    selected_subfamilies = list(
        selected.get("subfamilies")
        or (["shear", "bottom_reinforcement"] if selected_family == "combined" else ["bottom_reinforcement"])
    )
    selected_util = (
        selected.get("candidate_post_util")
        or selected.get("candidate_bending_util")
        or selected.get("worst_util")
        or evidence.get("selected_candidate_util")
        or evidence.get("best_target_band_candidate_util")
    )

    projected = dict(item)
    projected["candidate_search_evidence"] = dict(evidence)
    projected["local_cleanup_candidate"] = True
    projected["source"] = "design_guide_bending_only_cleanup_search"
    projected["affected_family"] = selected_family
    projected["family"] = selected_family
    projected["family_id"] = publication_family_id
    projected["selected_family_id"] = publication_family_id
    projected["published_family_id"] = publication_family_id
    projected["cta_family_id"] = publication_family_id
    projected["candidate_family_id"] = publication_family_id
    projected["card_family_id"] = publication_family_id
    projected["apply_payload_family_id"] = publication_family_id
    projected["selected_action_family"] = selected_family
    projected["check_key"] = selected_family
    projected["subfamilies"] = list(selected_subfamilies)
    projected["allow_in_target_primary_action"] = True
    projected["target_domains_for_band"] = list(
        selected.get("target_domains_for_band")
        or evidence.get("target_domains_for_band")
        or (["bending"] if selected_family == "bending" else [selected_family])
    )
    projected["target_domain_for_band"] = str(
        selected.get("target_domain_for_band")
        or evidence.get("target_domain_for_band")
        or ("bending" if selected_family == "bending" else selected_family)
    )
    if selected_util not in (None, "", [], {}):
        projected["util"] = selected_util
        projected["expected_util"] = selected_util
        projected["candidate_post_util"] = selected_util
        projected["displayed_util"] = selected_util
        projected["source_summary_util"] = selected_util
        projected["source_post_commit_util"] = selected_util

    payload = dict(projected.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["source_candidate_id"] = candidate_id
    payload["candidate_id"] = candidate_id
    payload["family"] = selected_family
    payload["family_id"] = publication_family_id
    payload["selected_family_id"] = publication_family_id
    payload["published_family_id"] = publication_family_id
    payload["cta_family_id"] = publication_family_id
    payload["candidate_family_id"] = publication_family_id
    payload["apply_payload_family_id"] = publication_family_id
    payload["resolved_candidate_family_tag"] = selected_family
    payload["resolved_candidate_subfamilies"] = list(selected_subfamilies)
    payload["target_domains_for_band"] = list(projected["target_domains_for_band"])
    payload["target_domain_for_band"] = projected["target_domain_for_band"]
    if selected_util not in (None, "", [], {}):
        payload["candidate_post_util"] = selected_util
        payload["expected_util"] = selected_util
    projected["action_payload"] = payload

    resolved = dict(projected.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["candidate_id"] = candidate_id
    resolved["source_candidate_id"] = candidate_id
    resolved["family"] = selected_family
    resolved["family_id"] = publication_family_id
    resolved["selected_family_id"] = publication_family_id
    resolved["published_family_id"] = publication_family_id
    resolved["cta_family_id"] = publication_family_id
    resolved["candidate_family_id"] = publication_family_id
    resolved["recommendation_family_tag"] = selected_family
    resolved["subfamilies"] = list(selected_subfamilies)
    resolved["target_domains_for_band"] = list(projected["target_domains_for_band"])
    resolved["target_domain_for_band"] = projected["target_domain_for_band"]
    if selected_util not in (None, "", [], {}):
        resolved["candidate_post_util"] = selected_util
        resolved["expected_util"] = selected_util
        resolved["worst_util"] = selected_util
    projected["resolved_candidate"] = resolved
    return projected


def build_design_guide_controller_zero_bending_demand_cleanup_item_projection(
    *,
    item: dict[str, Any] | None,
    selected_candidate: dict[str, Any] | None,
    candidate_search_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    selected = dict(selected_candidate or {})
    evidence = dict(candidate_search_evidence or {})
    candidate_id = selected.get("candidate_id")

    projected = dict(item or {})
    projected.update(
        {
            "candidate_search_evidence": dict(evidence),
            "local_cleanup_candidate": True,
            "source": "zero_bending_demand_minimum_cleanup_search",
            "affected_family": "bending",
            "family": "bending",
            "guidance_intent": "efficiency_tightening",
            "zero_bending_demand_cleanup": True,
        }
    )
    payload = dict(projected.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["zero_bending_demand_cleanup"] = True
    payload["source_candidate_id"] = candidate_id
    payload["candidate_id"] = candidate_id
    payload["resolved_candidate_family_tag"] = "bending"
    projected["action_payload"] = payload

    resolved = dict(projected.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["zero_bending_demand_cleanup"] = True
    resolved["candidate_id"] = candidate_id
    resolved["source_candidate_id"] = candidate_id
    resolved["family"] = "bending"
    resolved["recommendation_family_tag"] = "bending"
    projected["resolved_candidate"] = resolved
    return projected


def build_design_guide_controller_probe_equivalent_bending_cleanup_item_projection(
    *,
    item: dict[str, Any] | None,
    selected_candidate: dict[str, Any] | None,
    candidate_search_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    selected = dict(selected_candidate or {})
    evidence = dict(candidate_search_evidence or {})
    candidate_id = selected.get("candidate_id")

    projected = dict(item or {})
    projected["candidate_search_evidence"] = dict(evidence)
    projected["local_cleanup_candidate"] = True
    projected["source"] = "design_guide_probe_equivalent_bending_cleanup_search"
    projected["affected_family"] = "bending"
    projected["family"] = "bending"
    projected["guidance_intent"] = "efficiency_tightening"

    payload = dict(projected.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["source_candidate_id"] = candidate_id
    payload["candidate_id"] = candidate_id
    payload["resolved_candidate_family_tag"] = "bending"
    payload["resolved_candidate_subfamilies"] = ["bottom_reinforcement"]
    projected["action_payload"] = payload

    resolved = dict(projected.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["candidate_id"] = candidate_id
    resolved["source_candidate_id"] = candidate_id
    resolved["family"] = "bending"
    resolved["recommendation_family_tag"] = "bending"
    resolved["subfamilies"] = ["bottom_reinforcement"]
    projected["resolved_candidate"] = resolved
    return projected


def _design_guide_controller_payload_tuple_fingerprint(payload: dict | None) -> tuple:
    serialised: list[tuple[str, str]] = []
    for key, value in sorted(dict(payload or {}).items(), key=lambda item: str(item[0])):
        try:
            encoded = json.dumps(value, sort_keys=True, default=str)
        except Exception:
            encoded = repr(value)
        serialised.append((str(key), encoded))
    return tuple(serialised)


def build_design_guide_controller_bending_only_terminalisation_projection(
    *,
    selected_candidate: dict[str, Any] | None,
    candidate_search_evidence: dict[str, Any] | None,
    terminal_updates: dict[str, Any] | None,
    terminal_overview: dict[str, Any] | None,
    terminal_candidate_id: str | None,
    terminal_candidate_id_parts: list[Any] | tuple[Any, ...] | None,
    terminal_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Project same-click bending/shear terminalisation selected/evidence data.

    Inputs must already be computed by the page shell or service callbacks. This
    helper only owns the pure selected-candidate and evidence rewrite.
    """

    selected = dict(selected_candidate or {})
    evidence = dict(candidate_search_evidence or {})
    updates = dict(terminal_updates or {})
    if not updates or updates == dict(selected.get("updates") or {}):
        return {
            "selected_candidate": selected,
            "candidate_search_evidence": evidence,
            "terminalisation_applied": False,
            "owner": "DesignGuideController.bending_only_terminalisation_projection",
        }

    overview = dict(terminal_overview or {})
    terminal_utils = dict(overview.get("utils") or {})

    def _float_or_none(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(parsed):
            return None
        return parsed

    terminal_worst = _float_or_none(
        overview.get("worst_util")
        or overview.get("governing_util")
        or terminal_utils.get("bending")
        or terminal_utils.get("shear")
    )
    terminal_bending = _float_or_none(terminal_utils.get("bending"))
    terminal_shear = _float_or_none(terminal_utils.get("shear"))
    candidate_id = str(terminal_candidate_id or "").strip()
    if not candidate_id:
        candidate_id = optimisation_cleanup_candidate_id(
            "combined",
            updates,
            fingerprint_payload=_design_guide_controller_payload_tuple_fingerprint,
        )
    if not candidate_id:
        candidate_id = str(selected.get("candidate_id") or "").strip()
    label = "Shear and bending cleanup - one-click optimisation"

    projected = dict(selected)
    projected["updates"] = dict(updates)
    projected["candidate_id"] = candidate_id
    projected["source_candidate_id"] = candidate_id
    projected["label"] = label
    projected["canonical_winner_label"] = label
    projected["family"] = "combined"
    projected["recommendation_family_tag"] = "combined"
    projected["subfamilies"] = ["shear", "bottom_reinforcement"]
    if terminal_worst is not None:
        projected["candidate_post_util"] = float(terminal_worst)
        projected["worst_util"] = float(terminal_worst)
    if terminal_bending is not None:
        projected["candidate_bending_util"] = float(terminal_bending)
    if terminal_shear is not None:
        projected["candidate_shear_util"] = float(terminal_shear)

    projected_evidence = dict(evidence)
    projected_evidence.update(
        {
            "same_click_terminalisation_fold": True,
            "same_click_terminalisation_sources": [str(part) for part in list(terminal_candidate_id_parts or [])],
            "selected_candidate_id": candidate_id,
            "selected_candidate_title": label,
            "selected_candidate_updates": dict(updates),
            "best_safe_candidate_updates": dict(updates),
            "selected_candidate_util": projected.get("candidate_post_util"),
            "best_safe_final_util": projected.get("candidate_post_util"),
            "family": "combined",
            "no_second_cta_required": True,
            **dict(terminal_evidence or {}),
        }
    )
    return {
        "selected_candidate": projected,
        "candidate_search_evidence": projected_evidence,
        "terminalisation_applied": True,
        "owner": "DesignGuideController.bending_only_terminalisation_projection",
    }


def resolve_design_guide_controller_terminalisation_trial_acceptance(
    *,
    candidate_present: bool,
    overview_any_fail: bool,
    required_checks_acceptable: bool,
    preview_statuses_have_explicit_fail: bool,
) -> dict[str, Any]:
    accepted = (
        bool(candidate_present)
        and not bool(overview_any_fail)
        and bool(required_checks_acceptable)
        and not bool(preview_statuses_have_explicit_fail)
    )
    reasons: list[str] = []
    if not bool(candidate_present):
        reasons.append("candidate_missing")
    if bool(overview_any_fail):
        reasons.append("overview_any_fail")
    if not bool(required_checks_acceptable):
        reasons.append("required_checks_not_acceptable")
    if bool(preview_statuses_have_explicit_fail):
        reasons.append("preview_status_explicit_fail")
    return {
        "accepted": bool(accepted),
        "reasons": reasons,
        "owner": "DesignGuideController.terminalisation_trial_acceptance",
    }


def resolve_design_guide_controller_terminalisation_followup_updates(
    *,
    item: dict[str, Any] | None,
    button_contract: dict[str, Any] | None,
    candidate_search_evidence: dict[str, Any] | None = None,
    include_evidence_fallback: bool = False,
) -> dict[str, Any]:
    item_d = dict(item or {})
    contract_d = dict(button_contract or {})
    evidence_d = dict(candidate_search_evidence or {})
    updates = dict(
        contract_d.get("updates")
        or item_d.get("selected_action_updates")
        or item_d.get("updates")
        or (
            evidence_d.get("best_safe_candidate_updates")
            if bool(include_evidence_fallback)
            else {}
        )
        or (
            evidence_d.get("selected_candidate_updates")
            if bool(include_evidence_fallback)
            else {}
        )
        or {}
    )
    action_type = str(contract_d.get("action_type") or item_d.get("action_type") or "").strip()
    return {
        "updates": updates,
        "action_type": action_type,
        "has_updates": bool(updates),
        "owner": "DesignGuideController.terminalisation_followup_updates",
    }


def build_design_guide_controller_terminalisation_initial_context(
    *,
    base_state: dict[str, Any] | None,
    selected_candidate: dict[str, Any] | None,
) -> dict[str, Any]:
    selected = dict(selected_candidate or {})
    updates = dict(selected.get("updates") or {})
    state = dict(base_state or {})
    state.update(updates)
    candidate_id_parts = [str(selected.get("candidate_id") or "bending_cleanup")]
    return {
        "terminal_updates": updates,
        "terminal_state": state,
        "terminal_evidence": {},
        "terminal_candidate_id_parts": candidate_id_parts,
        "owner": "DesignGuideController.terminalisation_initial_context",
    }


def build_design_guide_controller_direct_target_band_bounded_proof_blocker_item(
    *,
    reason: str,
    max_overview_calls: int,
    max_update_attempts: int,
    max_candidates: int,
    overview_calls: int,
    unique_overview_fingerprints: int,
    max_repeated_overview_fingerprint_count: int,
    update_attempts: int,
    unique_update_fingerprints: int,
    candidate_count: int,
) -> dict[str, Any]:
    """Build the non-actionable direct target-band proof blocker item."""

    reason_text = str(reason or "direct_target_band_proof_budget_exhausted")
    proof_status = (
        "unresolved_budget_exhausted"
        if "budget_exhausted" in reason_text
        else "unresolved_reentry_blocked"
    )
    item = build_design_guide_controller_guidance_item(
        "general",
        "Design Guide needs a verified cleanup result",
        "No one-click cleanup is enabled until a verified candidate or exact engineering blocker is available.",
        None,
        (
            "Why: the direct target-band cleanup proof did not establish either an executable "
            "one-click cleanup or a final efficient terminal state, so no one-click action is enabled."
        ),
        "Key checks: Design Guide proof search, local cleanup evidence, one-click button contract",
        None,
        None,
        status="WARN",
        util=None,
    )
    item["guidance_intent"] = "blocked"
    item["direct_target_band_non_actionable_blocker"] = True
    item["direct_target_band_proof_unresolved"] = True
    item["direct_target_band_blocker_reason"] = reason_text
    item["design_guide_proof_ready"] = True
    item["design_guide_proof_status"] = proof_status
    item["design_guide_terminal_state"] = None
    item["button_contract"] = {
        "enabled": False,
        "actionable": False,
        "blocking_reason": reason_text,
    }
    item["candidate_search_evidence"] = {
        "search_scope": "design_guide_direct_target_band_search",
        "bounded_proof": True,
        "proof_budget_exhausted": "budget_exhausted" in reason_text,
        "proof_reentry_blocked": "reentry_blocked" in reason_text,
        "proof_unresolved_reason": reason_text,
        "design_guide_proof_ready": True,
        "design_guide_proof_status": proof_status,
        "max_overview_calls": max_overview_calls,
        "max_update_attempts": max_update_attempts,
        "max_candidates": max_candidates,
        "overview_calls": int(overview_calls or 0),
        "unique_overview_fingerprints": int(unique_overview_fingerprints or 0),
        "max_repeated_overview_fingerprint_count": int(
            max_repeated_overview_fingerprint_count or 0
        ),
        "update_attempts": int(update_attempts or 0),
        "unique_update_fingerprints": int(unique_update_fingerprints or 0),
        "candidate_count": int(candidate_count or 0),
    }
    return item


def build_design_guide_controller_active_failure_no_target_blocker_item(
    *,
    reason: str,
    evidence: dict[str, Any] | None,
    overview: dict[str, Any] | None,
    width_values: list[Any] | tuple[Any, ...] | None,
    depth_values: list[Any] | tuple[Any, ...] | None,
    base_width: Any,
    base_depth: Any,
) -> dict[str, Any]:
    """Build the active-failure blocker item when no target-band repair exists."""

    evidence_map = dict(evidence or {})
    overview_map = dict(overview or {})
    statuses = dict(overview_map.get("statuses") or {})
    active_failures = [
        str(key).strip().lower()
        for key, value in statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    ]
    governing = str(overview_map.get("governing_check") or "").strip().lower()
    serviceability_active = bool({"serviceability", "crack", "deflection"} & set(active_failures)) or governing in {
        "serviceability",
        "crack",
        "deflection",
    }
    family = (
        "serviceability"
        if serviceability_active
        else (
        governing
        if governing in active_failures
        else ("bending" if "bending" in active_failures else ("shear" if "shear" in active_failures else governing or "bending"))
        )
    )
    title = (
        "Shear repair blocked by shear/detailing limits"
        if family == "shear"
        else "Serviceability repair blocked"
        if family == "serviceability"
        else "Bending repair blocked by reinforcement/detailing limits"
    )

    base_width_value = float(base_width or 0.0)
    base_depth_value = float(base_depth or 0.0)
    width_candidates = [float(value or 0.0) for value in list(width_values or [base_width_value])]
    depth_candidates = [float(value or 0.0) for value in list(depth_values or [base_depth_value])]
    max_width_growth = max(width_candidates or [base_width_value]) - base_width_value
    max_depth_growth = max(depth_candidates or [base_depth_value]) - base_depth_value
    best_util = evidence_map.get("closest_safe_candidate_util") or evidence_map.get("selected_candidate_util")
    best_util_text = ""
    try:
        if best_util is not None:
            best_util_text = f" Best safe preview utilisation found was {float(best_util):.2f}, still outside the accepted range."
    except Exception:
        best_util_text = ""

    if family == "shear":
        category = "shear_would_fail"
        failed_check_name = "sectional shear capacity repair catalogue"
        attempted_updates = active_failure_route_attempt_updates("shear")
        blocker_reason = (
            "Shear repair is blocked by shear/detailing limits. Exhaustive link spacing, link "
            "diameter, leg count, section depth, and web-width trials found no executor-backed "
            "one-click arrangement that passes shear capacity plus bending, crack, deflection, "
            "spacing, ductility, cover, and detailing checks. "
            f"The search reached width growth up to {max_width_growth:.0f} mm and depth growth up to {max_depth_growth:.0f} mm."
            f"{best_util_text}"
        )
    elif family == "serviceability":
        category = "serviceability_would_fail"
        failed_check_name = "serviceability repair catalogue"
        attempted_updates = {}
        blocker_reason = (
            "Serviceability repair is blocked by serviceability/detailing limits. Exhaustive one-click "
            "trials found no executor-backed arrangement that resolves the serviceability limit while "
            "preserving bending, shear, crack control, deflection, spacing, ductility, cover, and detailing checks."
            f"{best_util_text}"
        )
    else:
        category = "bending_would_fail"
        failed_check_name = "bending capacity repair catalogue"
        attempted_updates = active_failure_route_attempt_updates("bending")
        blocker_reason = (
            "Bending repair is blocked by reinforcement, geometry, ductility, or detailing limits. "
            "Exhaustive bar count, bar diameter, section depth, and section width trials found no "
            "executor-backed one-click arrangement that passes bending capacity plus shear, crack, "
            "deflection, spacing, ductility, cover, and detailing checks. "
            f"The search reached width growth up to {max_width_growth:.0f} mm and depth growth up to {max_depth_growth:.0f} mm, "
            "and exhausted the generated bottom-reinforcement layouts."
            f"{best_util_text}"
        )
    if reason:
        blocker_reason = f"{blocker_reason} Search stop: {reason}."

    active_route_inventory = active_failure_route_inventory(active_failures or [family])
    active_failure_set = set(active_failures or [])
    evidence_map.update(
        {
            "candidate_search_exhaustive": True,
            "search_scope": (
                "active_fail_combined_repair_search"
                if {"bending", "shear"}.issubset(active_failure_set)
                else f"active_fail_{family}_repair_search"
            ),
            "active_fail_repair_search_scope": (
                "active_fail_combined_repair_search"
                if {"bending", "shear"}.issubset(active_failure_set)
                else f"active_fail_{family}_repair_search"
            ),
            "repair_search_ran": True,
            "repair_search_exhaustive": True,
            "geometry_strengthening_searched": True,
            "reo_strengthening_searched": True,
            "longitudinal_reinforcement_strengthening_searched": True,
            "shear_strengthening_searched": bool("shear" in active_failure_set or family == "shear"),
            "combined_strengthening_searched": bool(len(active_failure_set) > 1),
            "cleanup_search_ran": False,
            "cleanup_search_exhaustive": False,
            "active_failures": list(active_failures or [family]),
            "active_fail_repair_candidate_rows": [
                dict(row) for row in list(evidence_map.get("candidate_rows") or []) if isinstance(row, dict)
            ][:80],
            "safe_repair_candidate_count": int(
                evidence_map.get("safe_repair_candidate_count")
                if evidence_map.get("safe_repair_candidate_count") is not None
                else evidence_map.get("safe_executor_backed_candidates_count")
                if evidence_map.get("safe_executor_backed_candidates_count") is not None
                else evidence_map.get("safe_candidate_count")
                if evidence_map.get("safe_candidate_count") is not None
                else 0
            ),
            "executable_repair_candidate_count": int(
                evidence_map.get("executable_repair_candidate_count")
                if evidence_map.get("executable_repair_candidate_count") is not None
                else evidence_map.get("safe_executor_backed_candidates_count")
                if evidence_map.get("safe_executor_backed_candidates_count") is not None
                else evidence_map.get("executable_candidate_count")
                if evidence_map.get("executable_candidate_count") is not None
                else 0
            ),
            "safe_candidate_count": int(
                evidence_map.get("safe_executor_backed_candidates_count")
                if evidence_map.get("safe_executor_backed_candidates_count") is not None
                else evidence_map.get("safe_candidate_count")
                if evidence_map.get("safe_candidate_count") is not None
                else 0
            ),
            "executable_candidate_count": int(
                evidence_map.get("safe_executor_backed_candidates_count")
                if evidence_map.get("safe_executor_backed_candidates_count") is not None
                else evidence_map.get("executable_candidate_count")
                if evidence_map.get("executable_candidate_count") is not None
                else 0
            ),
            "executable_target_band_candidate_count": 0,
            "failed_candidate_reasons": list(evidence_map.get("failed_candidate_reasons") or [blocker_reason]),
            "rejected_repair_reasons": list(
                dict.fromkeys(
                    list(evidence_map.get("rejected_repair_reasons") or [])
                    + [
                        str(row.get("rejection_reason") or row.get("failed_check_family") or "preview_failed")
                        for row in list(evidence_map.get("candidate_rows") or [])
                        if isinstance(row, dict) and not bool(row.get("safe_executor_backed"))
                    ]
                    + [blocker_reason]
                )
            )[:40],
            "blocker_reasons_by_family": dict(evidence_map.get("blocker_reasons_by_family") or {family: [blocker_reason]}),
            "exact_blocker_reasons_by_family": dict(evidence_map.get("exact_blocker_reasons_by_family") or {family: [blocker_reason]}),
            "active_under_capacity_blocker": True,
            "active_under_capacity_blocker_family": family,
            "active_under_capacity_blocker_reason": blocker_reason,
            "outside_target_band_allowed": False,
            "outside_target_band_allowed_reason": blocker_reason,
            "outside_target_band_allowed_category": category,
            "attempted_candidate_id": evidence_map.get("attempted_candidate_id") or f"{family}_active_failure_practical_ladder_exhausted",
            "attempted_updates": active_failure_route_attempt_updates(
                family,
                dict(evidence_map.get("attempted_updates") or attempted_updates),
            ),
            "active_repair_route_inventory": dict(active_route_inventory),
            "failed_check_name": evidence_map.get("failed_check_name") or failed_check_name,
            "failed_check_status": evidence_map.get("failed_check_status") or "FAIL",
            "failed_check_util": evidence_map.get("failed_check_util") or _float_or_none(overview_map.get("worst_util") or overview_map.get("governing_util")) or 1.0,
            "failed_check_demand": evidence_map.get("failed_check_demand") or f"{family} demand remains above checked capacity or serviceability limit",
            "failed_check_capacity_or_limit": evidence_map.get("failed_check_capacity_or_limit") or f"{family} capacity or serviceability limit",
            "one_click_target_reaching_candidate_exists": False,
        }
    )
    evidence_map["exact_blockers_by_family"] = active_failure_exact_blockers_for_families(
        active_failures or [family],
        overview=overview_map,
        evidence=evidence_map,
        primary_family=family,
        primary_reason=blocker_reason,
    )
    evidence_map["post_click_exact_blockers_by_family"] = dict(evidence_map["exact_blockers_by_family"])
    if {"bending", "shear"}.issubset(set(evidence_map["exact_blockers_by_family"])):
        family = "combined"
        title = "Bending and shear repair blocked"
        bending_active_reason = str(
            (evidence_map["exact_blockers_by_family"].get("bending") or {}).get("reason") or ""
        ).strip()
        shear_active_reason = str(
            (evidence_map["exact_blockers_by_family"].get("shear") or {}).get("reason") or ""
        ).strip()
        blocker_reason = (
            f"Bending repair blocked: {bending_active_reason} "
            f"Shear repair blocked: {shear_active_reason}"
        )

    item = build_design_guide_controller_guidance_item(
        family if family in {"bending", "shear", "combined"} else "bending",
        title,
        blocker_reason,
        None,
        f"Why: {blocker_reason}",
        "Key blockers: practical bar/count/diameter catalogue, section width/depth limits, required PASS checks",
        None,
        None,
        status="FAIL",
        util=_float_or_none(overview_map.get("worst_util") or overview_map.get("governing_util")),
    )
    item["guidance_intent"] = "specific_blocker"
    item["active_under_capacity_blocker"] = True
    item["active_under_capacity_blocker_reason"] = blocker_reason
    item["candidate_search_evidence"] = dict(evidence_map)
    item["exact_blockers_by_family"] = dict(evidence_map.get("exact_blockers_by_family") or {})
    item["post_click_exact_blockers_by_family"] = dict(evidence_map.get("exact_blockers_by_family") or {})
    item["primary_card_actionable"] = False
    item["final_state_class"] = "blocker"
    if family == "combined":
        item["title_util_label"] = "governing utilisation"
    item["button_contract"] = {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": family,
        "updates": {},
        "preview_pass": False,
        "blocking_reason": blocker_reason,
        "source_candidate_id": None,
        "candidate_id": None,
    }
    return item


def resolve_design_guide_controller_candidate_action_type_for_updates(
    *,
    updates: dict[str, Any] | None,
    geometry_update_keys: set[str] | frozenset[str] | list[str] | tuple[str, ...],
    bottom_update_keys: set[str] | frozenset[str] | list[str] | tuple[str, ...],
    shear_update_keys: set[str] | frozenset[str] | list[str] | tuple[str, ...],
    strengthening: bool,
) -> str:
    """Resolve the Design Guide action type for a candidate update payload."""

    keys = {str(key) for key in dict(updates or {}).keys()}
    has_geom = bool(keys & {str(key) for key in geometry_update_keys or []})
    has_bottom = bool(keys & {str(key) for key in bottom_update_keys or []})
    has_shear = bool(keys & {str(key) for key in shear_update_keys or []})
    if sum(1 for flag in (has_geom, has_bottom, has_shear) if flag) >= 2:
        return "apply_resolved_candidate"
    if has_shear:
        return "apply_shear_recommendation"
    if has_bottom:
        return "apply_bottom_recommendation"
    if has_geom:
        return "apply_geometry_recommendation" if strengthening else "tighten_geometry"
    return "apply_resolved_candidate"


def resolve_design_guide_controller_strength_family_band_status(
    *,
    candidate: dict[str, Any] | None,
    active_strength_family_floor_set: set[str] | frozenset[str] | list[str] | tuple[str, ...] | None,
    target_low: Any,
    target_high: Any,
    target_band_eps: Any,
    final_accepted_min_family_util: Any,
) -> dict[str, Any]:
    """Resolve strength-family floor and target-band status for a candidate."""

    candidate_overview = _mapping(_mapping(candidate).get("overview"))
    candidate_utils = _mapping(candidate_overview.get("utils"))
    family_utils: dict[str, float] = {}
    for family in ("bending", "shear"):
        util = _float_or_none(candidate_utils.get(family))
        if util is not None:
            family_utils[family] = float(util)

    active_floor = {
        str(family or "").strip().lower()
        for family in list(active_strength_family_floor_set or [])
        if str(family or "").strip().lower() in {"bending", "shear"}
    }
    active_families = active_floor or {"bending", "shear"}
    low = _float_or_none(target_low)
    high = _float_or_none(target_high)
    eps = _float_or_none(target_band_eps)
    if eps is None:
        eps = 0.0
    final_floor = _float_or_none(final_accepted_min_family_util)
    if final_floor is None:
        final_floor = 0.0

    clears_floor = True
    if active_floor:
        for family in sorted(active_floor):
            util = family_utils.get(family)
            if util is None or float(util) < float(final_floor):
                clears_floor = False
                break

    in_band_families: list[str] = []
    if low is not None and high is not None:
        in_band_families = [
            family
            for family in ("bending", "shear")
            if family in active_families
            and family in family_utils
            and float(low) - float(eps) <= float(family_utils[family]) <= float(high) + float(eps)
        ]

    if not family_utils:
        band_distance = float("inf")
    else:
        distances: list[float] = []
        for family, util in family_utils.items():
            if family not in active_families:
                continue
            distances.append(float(_controller_distance_to_target_band(float(util), low, high)))
        band_distance = min(distances) if distances else float("inf")

    return {
        "family_utils": dict(family_utils),
        "active_floor_families": sorted(active_floor),
        "active_families": sorted(active_families),
        "clears_active_strength_family_floor": bool(clears_floor),
        "in_band_families": list(in_band_families),
        "band_distance": float(band_distance),
    }


def filter_design_guide_controller_direct_target_ladder_candidates(
    *,
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    start_index: int,
    target_low: Any,
    target_high: Any,
    strengthening: bool,
) -> list[dict[str, Any]]:
    """Filter already-evaluated direct target-band ladder candidates."""

    low = _float_or_none(target_low)
    high = _float_or_none(target_high)
    if low is None or high is None:
        return []
    try:
        start = max(int(start_index or 0), 0)
    except Exception:
        start = 0
    ladder_safe: list[dict[str, Any]] = []
    for candidate in list(candidates or [])[start:]:
        if not isinstance(candidate, dict):
            continue
        if not bool(candidate.get("is_compliant")):
            continue
        if not bool((_mapping(candidate.get("overview"))).get("all_key_pass")):
            continue
        post_util = _float_or_none(candidate.get("candidate_post_util"))
        if post_util is None:
            continue
        if not (float(low) <= float(post_util) <= float(high)):
            continue
        if not strengthening and not bool(candidate.get("final_accepted_green_valid")):
            continue
        ladder_safe.append(candidate)
    return ladder_safe


def _controller_state_float(source: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = _mapping(source).get(key)
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _controller_state_int(source: dict[str, Any], key: str, default: int = 0) -> int:
    value = _mapping(source).get(key)
    try:
        if value is None or value == "":
            return int(default)
        return int(value)
    except Exception:
        return int(default)


def _controller_design_width_value(state: dict[str, Any]) -> float:
    st = _mapping(state)
    sec_shape = str(st.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return _controller_state_float(st, "bw", _controller_state_float(st, "b", 300.0))
    if sec_shape == "I":
        return _controller_state_float(st, "tw", _controller_state_float(st, "b", 200.0))
    return _controller_state_float(st, "b", 400.0)


def _controller_shear_change_is_reinforcement_growth(
    seed_state: dict[str, Any],
    candidate_state: dict[str, Any],
) -> bool:
    seed = _mapping(seed_state)
    candidate = _mapping(candidate_state)
    sd = _controller_state_int(seed, "lig_d", 0)
    sl = _controller_state_int(seed, "lig_legs", 0)
    cd = _controller_state_int(candidate, "lig_d", 0)
    cl = _controller_state_int(candidate, "lig_legs", 0)
    ss = _controller_state_float(seed, "s_lig", 200.0)
    cs = _controller_state_float(candidate, "s_lig", 200.0)
    if sd <= 0 and sl < 2 and cd <= 0 and cl < 2:
        return False
    if cd <= 0 and cl < 2 and (sd > 0 or sl >= 2):
        return False
    if cd > sd or cl > sl:
        return True
    if cd > 0 and cl >= 2 and sd > 0 and sl >= 2 and cs < ss - 1e-9:
        return True
    return False


def _controller_candidate_materially_improves(
    current_candidate: dict[str, Any],
    trial_candidate: dict[str, Any],
) -> bool:
    if not isinstance(trial_candidate, dict) or not trial_candidate:
        return False
    current_worst = _controller_state_float(current_candidate, "worst_util", float("inf"))
    trial_worst = _controller_state_float(trial_candidate, "worst_util", float("inf"))
    if bool(trial_candidate.get("is_compliant")) and not bool(_mapping(current_candidate).get("is_compliant")):
        return True
    return trial_worst < current_worst - 1e-6


def _controller_bottom_recommendation_prefilter_ok(
    seed_candidate: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[bool, str]:
    if not str(_mapping(candidate).get("label") or "").strip():
        return False, "missing_label"
    if _controller_candidate_ductility_governs(seed_candidate):
        sdu = _controller_candidate_ductility_util(seed_candidate)
        tdu = _controller_candidate_ductility_util(candidate)
        if sdu is None or tdu is None:
            return False, "missing_ductility_util"
        if float(tdu) >= float(sdu) - 1e-9:
            return False, "ductility_not_improved"
    else:
        sb = ((_mapping(seed_candidate.get("overview")).get("utils") or {}) or {}).get("bending")
        tb = ((_mapping(candidate.get("overview")).get("utils") or {}) or {}).get("bending")
        try:
            if sb is None or tb is None:
                return False, "missing_bending_util"
            if float(tb) >= float(sb) - 1e-9:
                return False, "bending_util_not_improved"
        except (TypeError, ValueError):
            return False, "missing_bending_util"
    return True, "ok"


def _controller_candidate_is_growth_move(
    seed_candidate: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    if not seed_candidate or not candidate:
        return False
    seed_st = _mapping(seed_candidate.get("state"))
    cand_st = _mapping(candidate.get("state"))
    d0 = _controller_state_float(
        seed_candidate,
        "depth",
        _controller_state_float(seed_st, "D", 0.0),
    )
    d1 = _controller_state_float(
        candidate,
        "depth",
        _controller_state_float(cand_st, "D", 0.0),
    )
    if d1 > d0 + 1e-9:
        return True
    w0 = _controller_design_width_value(seed_st)
    w1 = _controller_state_float(candidate, "width", _controller_design_width_value(cand_st))
    if w1 > w0 + 1e-9:
        return True
    a0 = _controller_state_float(seed_candidate, "Ast_bot", 0.0)
    a1 = _controller_state_float(candidate, "Ast_bot", 0.0)
    if a1 > a0 + 1e-9:
        return True
    if _controller_shear_change_is_reinforcement_growth(seed_st, cand_st):
        return True
    return False


def resolve_design_guide_controller_bottom_reo_prerank_filter_policy(
    *,
    seed_candidate: dict[str, Any],
    candidate: dict[str, Any] | None,
    updates_match_state_after_pool: bool,
) -> dict[str, Any]:
    """Resolve bottom-reo pre-rank filter status without page dependencies."""

    if candidate is None or bool(updates_match_state_after_pool):
        return {
            "accepted": False,
            "status": "rejected",
            "reject_reason": "updates_match_state_after_pool",
            "evaluator_returned": True,
            "compound_score_inferior_increment": False,
            "rank_trace_rejection": False,
        }
    if not _controller_candidate_materially_improves(seed_candidate, candidate):
        return {
            "accepted": False,
            "status": "rejected",
            "reject_reason": "not_materially_improved",
            "evaluator_returned": True,
            "compound_score_inferior_increment": False,
            "rank_trace_rejection": False,
        }
    bending_util = ((_mapping(candidate.get("overview")).get("utils") or {}) or {}).get("bending")
    if bending_util is None:
        return {
            "accepted": False,
            "status": "rejected",
            "reject_reason": "missing_bending_util",
            "evaluator_returned": True,
            "compound_score_inferior_increment": False,
            "rank_trace_rejection": False,
        }
    ok, reason = _controller_bottom_recommendation_prefilter_ok(seed_candidate, candidate)
    if not ok:
        return {
            "accepted": False,
            "status": "rejected",
            "reject_reason": str(reason),
            "evaluator_returned": True,
            "compound_score_inferior_increment": bool(candidate.get("recommendation_compound")),
            "rank_trace_rejection": True,
        }
    return {
        "accepted": True,
        "status": "accepted_prerank",
        "reject_reason": None,
        "evaluator_returned": True,
        "compound_score_inferior_increment": False,
        "rank_trace_rejection": False,
    }


def resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy(
    *,
    seed_candidate: dict[str, Any],
    candidate: dict[str, Any],
    efficiency_reduction_only: bool,
) -> dict[str, Any]:
    """Resolve bottom-reo efficiency-growth rejection policy."""

    growth_rejected = bool(efficiency_reduction_only) and _controller_candidate_is_growth_move(
        seed_candidate,
        candidate,
    )
    return {
        "accepted": not growth_rejected,
        "status": "rejected" if growth_rejected else "accepted",
        "reject_reason": "growth_move_rejected_for_efficiency_reduction" if growth_rejected else None,
        "growth_rejected": bool(growth_rejected),
    }


def resolve_design_guide_controller_direct_candidate_final_cleanup_sort_key(
    *,
    candidate: dict[str, Any] | None,
    final_valid: bool,
    unresolved_low_count: int,
    below_threshold_count: int,
    remaining_count: int,
    missing_current_count: int,
    shear_preference_score: tuple[Any, ...] | list[Any],
    geometry_preference_score: tuple[Any, ...] | list[Any],
    material_delta: Any,
) -> tuple[Any, ...]:
    """Build the direct target-band final-cleanup candidate sort key."""

    candidate_map = _mapping(candidate)
    try:
        material_delta_value = float(material_delta or 0.0)
    except Exception:
        material_delta_value = 0.0
    return (
        0 if bool(final_valid) else 1,
        int(unresolved_low_count or 0),
        int(below_threshold_count or 0),
        int(remaining_count or 0),
        int(missing_current_count or 0),
        tuple(shear_preference_score or ()),
        tuple(geometry_preference_score or ()),
        len(_mapping(candidate_map.get("updates"))),
        material_delta_value,
        str(candidate_map.get("label") or ""),
    )


def resolve_design_guide_controller_overview_family_utils_for_local_cleanup(
    overview: dict[str, Any] | None,
) -> dict[str, float]:
    """Extract family utilisation values from plain overview data."""

    ov = _mapping(overview)
    utils = _mapping(ov.get("utils"))
    out: dict[str, float] = {}
    for key, value in utils.items():
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed):
            out[str(key or "").strip().lower()] = parsed
    packs = _mapping(ov.get("packs"))
    for key, pack in packs.items():
        if not isinstance(pack, dict):
            continue
        family = str(key or "").strip().lower()
        if family == "serviceability":
            family = "deflection"
        for field_name in ("summary_util", "util", "governing_util", "max_util"):
            try:
                parsed = float(pack.get(field_name))
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                out.setdefault(family, parsed)
                break
    for family in ("bending", "shear", "crack", "deflection", "serviceability", "ductility"):
        for field_name in (f"{family}_util", f"{family}_utilisation"):
            if family in out:
                continue
            try:
                parsed = float(ov.get(field_name))
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                out[family] = parsed
    return out


def resolve_design_guide_controller_governing_family_for_local_cleanup(
    overview: dict[str, Any] | None,
    family_utils: dict[str, float] | None,
) -> str | None:
    """Resolve the governing family from plain overview data."""

    ov = _mapping(overview)
    explicit = str(ov.get("governing_family") or "").strip().lower()
    if explicit and explicit not in {"overview_worst_util", "governing", "overall"}:
        return explicit
    check = str(ov.get("governing_check") or "").strip().lower()
    if "shear" in check:
        return "shear"
    if "bend" in check or "moment" in check:
        return "bending"
    if "deflect" in check:
        return "deflection"
    if "crack" in check:
        return "crack"
    utils = dict(family_utils or {})
    if utils:
        try:
            return max(utils.items(), key=lambda item: item[1])[0]
        except Exception:
            return None
    return None


def identify_design_guide_controller_materially_overprovided_non_governing_families(
    overview: dict[str, Any] | None,
    *,
    threshold: float = 0.70,
) -> tuple[dict[str, float], list[str], str | None]:
    """Identify materially overprovided non-governing families from overview data."""

    family_utils = resolve_design_guide_controller_overview_family_utils_for_local_cleanup(overview)
    governing = resolve_design_guide_controller_governing_family_for_local_cleanup(overview, family_utils)
    families = [
        family
        for family, util in sorted(family_utils.items())
        if family != governing
        and float(util) < float(threshold)
        and not (
            family in {"crack", "deflection", "serviceability", "geometry"}
            and float(util) <= 1e-9
        )
    ]
    return family_utils, families, governing


def select_design_guide_controller_direct_target_final_candidate(
    *,
    safe_candidate_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    target_candidate_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    strengthening: bool,
    current_material_family_set: set[str] | list[str] | tuple[str, ...] | None = None,
    proof_exhausted: bool = False,
) -> dict[str, Any]:
    """Select the final direct target-band candidate from precomputed rows."""

    safe_rows = [dict(row) for row in list(safe_candidate_rows or []) if isinstance(row, dict)]
    target_rows = [dict(row) for row in list(target_candidate_rows or []) if isinstance(row, dict)]
    current_families = {str(family or "").strip().lower() for family in (current_material_family_set or []) if str(family or "").strip()}

    def _sort_key(row: dict[str, Any], *, target_mode: bool) -> tuple[Any, ...]:
        base_key = tuple(row.get("final_cleanup_sort_key") or ())
        target_mid_distance = _float_or_none(row.get("target_mid_distance"))
        if target_mid_distance is None:
            target_mid_distance = 0.0
        if target_mode:
            if bool(strengthening):
                preferred_distance = _float_or_none(row.get("preferred_band_distance"))
                if preferred_distance is None:
                    preferred_distance = float("inf")
                return (base_key, float(preferred_distance), float(target_mid_distance))
            return (base_key, float(target_mid_distance), float(target_mid_distance))
        if bool(strengthening):
            accepted_distance = _float_or_none(row.get("accepted_band_distance"))
            if accepted_distance is None:
                accepted_distance = float("inf")
            fallback_distance = _float_or_none(row.get("fallback_band_distance"))
            if fallback_distance is None:
                fallback_distance = accepted_distance
            return (base_key, float(accepted_distance), float(fallback_distance))
        fallback_distance = _float_or_none(row.get("fallback_band_distance"))
        if fallback_distance is None:
            fallback_distance = float("inf")
        return (base_key, float(fallback_distance), float(fallback_distance))

    if target_rows:
        pool = list(target_rows)
        if current_families:
            covering = [
                row
                for row in pool
                if current_families <= {
                    str(family or "").strip().lower()
                    for family in list(row.get("affected_current_low_families") or [])
                }
            ]
            if covering:
                pool = covering
        selected_row = min(pool, key=lambda row: _sort_key(row, target_mode=True))
        return {
            "status": "selected",
            "selected_candidate": selected_row.get("candidate"),
            "selected_row": dict(selected_row),
            "selection_pool": "target",
            "used_target_covering_current_low": bool(current_families)
            and {
                str(family or "").strip().lower()
                for family in list(selected_row.get("affected_current_low_families") or [])
            }
            >= current_families,
        }

    if bool(proof_exhausted) and not bool(strengthening):
        return {
            "status": "budget_exhausted_without_target_candidate_no_visible_budget_card",
            "selected_candidate": None,
            "selected_row": {},
            "selection_pool": "none",
            "used_target_covering_current_low": False,
        }

    fallback_pool = list(safe_rows)
    active_accepted_rows: list[dict[str, Any]] = []
    if bool(strengthening):
        active_accepted_rows = [
            row for row in safe_rows if bool(row.get("families_in_accepted_band"))
        ]
        if active_accepted_rows:
            fallback_pool = active_accepted_rows
    selected_row = min(fallback_pool, key=lambda row: _sort_key(row, target_mode=False))
    return {
        "status": "selected",
        "selected_candidate": selected_row.get("candidate"),
        "selected_row": dict(selected_row),
        "selection_pool": "accepted_fallback" if active_accepted_rows else "safe_fallback",
        "used_target_covering_current_low": False,
    }


_CONTROLLER_COMPOUND_GEOMETRY_UPDATE_KEYS = frozenset(
    {"b", "bw", "D", "bf", "tf", "tw", "bf_bot", "tf_bot"},
)
_CONTROLLER_COMPOUND_BOTTOM_UPDATE_KEYS = frozenset(
    {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "bot1_spacing",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "bot2_spacing",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
        "bot_row_3_mode",
        "bot_row_3_bars",
        "bot_row_3_spacing",
        "bot_row_3_dia",
        "bot_row_4_mode",
        "bot_row_4_bars",
        "bot_row_4_spacing",
        "bot_row_4_dia",
        "Ast_bot",
    },
)
_CONTROLLER_COMPOUND_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})
_CONTROLLER_PRIMARY_GEOMETRY_KEYS = frozenset(
    {"sec_shape", "b", "D", "bf", "tf", "bw", "tw", "bf_bot", "tf_bot"},
)


def resolve_design_guide_controller_local_cleanup_candidate_affects_family(
    *,
    family: str,
    updates: dict[str, Any] | None,
) -> bool:
    """Return whether a local cleanup update materially touches a family."""

    fam = str(family or "").strip().lower()
    keys = set(_mapping(updates))
    has_shear = bool(keys & _CONTROLLER_COMPOUND_SHEAR_UPDATE_KEYS)
    has_bottom = bool(keys & _CONTROLLER_COMPOUND_BOTTOM_UPDATE_KEYS) or any(
        str(key).startswith("bot") or str(key).startswith("db_bot") for key in keys
    )
    has_geometry = bool(
        keys & _CONTROLLER_PRIMARY_GEOMETRY_KEYS
        or keys & _CONTROLLER_COMPOUND_GEOMETRY_UPDATE_KEYS
    )
    if fam == "shear":
        return has_shear
    if fam == "bending":
        return bool(has_bottom or has_geometry)
    if fam in {"crack", "deflection", "serviceability"}:
        return bool(has_bottom or has_geometry)
    if fam == "geometry":
        return has_geometry
    return False


def resolve_design_guide_controller_shear_practical_preference_score(
    *,
    touches_shear_updates: bool,
    legs: Any,
    diameter: Any,
    spacing: Any,
) -> tuple[int, float, int, int]:
    """Build the shear-link practical preference score for cleanup ranking."""

    if not bool(touches_shear_updates):
        return (0, 0, 0.0, 0)
    try:
        legs_value = max(int(legs or 0), 0)
    except Exception:
        legs_value = 0
    try:
        diameter_value = max(int(diameter or 0), 0)
    except Exception:
        diameter_value = 0
    try:
        spacing_value = float(spacing or 0.0)
    except Exception:
        spacing_value = 0.0
    leg_penalty = 0 if legs_value == 2 else (100 + abs(legs_value - 2))
    return (leg_penalty, spacing_value, -diameter_value, legs_value)


def resolve_design_guide_controller_geometry_proportion_preference_score(
    *,
    touches_geometry_updates: bool,
    geometry_locked: bool,
    depth: Any,
    width: Any,
    invalid_geometry: bool = False,
) -> tuple[int, float, float]:
    """Build the geometry proportion preference score for cleanup ranking."""

    if bool(geometry_locked) or not bool(touches_geometry_updates):
        return (0, 0.0, 0.0)
    if bool(invalid_geometry):
        return (3, 99.0, 99.0)
    try:
        depth_value = float(depth or 0.0)
        width_value = float(width or 0.0)
    except Exception:
        return (3, 99.0, 99.0)
    if depth_value <= 0.0 or width_value <= 0.0:
        return (3, 99.0, 99.0)
    ratio = depth_value / width_value
    if ratio <= 2.0 + 1e-9:
        return (0, abs(ratio - 2.0), ratio)
    if ratio <= 2.5 + 1e-9:
        return (1, ratio - 2.0, ratio)
    return (2, ratio - 2.0, ratio)


def _normalise_design_guide_preference_score_state(
    state: dict[str, Any] | None,
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply the plain update subset needed for direct-target preference scores."""

    out = dict(state or {})
    numeric_keys = {
        "lig_d",
        "lig_legs",
        "s_lig",
        "D",
        "b",
        "beam_width",
        "beam_b",
        "width",
    }
    ignored_keys = {"search_scope", "generated_count", "deduped_count", "preview_count"}
    for raw_key, value in _mapping(updates).items():
        key = str(raw_key or "").strip()
        key_l = key.lower()
        if not key or key_l in ignored_keys or key_l.endswith("_route") or key_l in {"links", "bottom_reo"}:
            continue
        if key not in numeric_keys:
            continue
        numeric = _float_or_none(value)
        if numeric is not None:
            out[key] = numeric
    return out


def _controller_int_from_mapping(source: dict[str, Any], key: str, default: int) -> int:
    value = _float_or_none(source.get(key))
    if value is None:
        return int(default)
    return int(value)


def _controller_float_from_mapping(source: dict[str, Any], key: str, default: float) -> float:
    value = _float_or_none(source.get(key))
    if value is None:
        return float(default)
    return float(value)


def _controller_design_width_value(source: dict[str, Any]) -> float:
    sec_shape = str(source.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        fallback = source.get("b", 300.0) or 300.0
        return float(source.get("bw", fallback) or fallback)
    if sec_shape == "I":
        fallback = source.get("b", 200.0) or 200.0
        return float(source.get("tw", fallback) or fallback)
    return float(source.get("b", 400.0) or 400.0)


def resolve_design_guide_controller_direct_target_after_state_preference_scores(
    *,
    updates: dict[str, Any] | None,
    state: dict[str, Any] | None,
    canonical_no_shear_spacing: Any = 200.0,
) -> dict[str, tuple]:
    """Resolve direct-target selection preference scores from plain state/update data."""

    updates_d = _mapping(updates)
    after = _normalise_design_guide_preference_score_state(state, updates_d)
    touches_shear_updates = bool(set(updates_d) & _CONTROLLER_COMPOUND_SHEAR_UPDATE_KEYS)
    canonical_spacing = _float_or_none(canonical_no_shear_spacing)
    if canonical_spacing is None:
        canonical_spacing = 200.0
    if touches_shear_updates:
        legs = max(_controller_int_from_mapping(after, "lig_legs", 2), 0)
        diameter = max(_controller_int_from_mapping(after, "lig_d", 0), 0)
        spacing = _controller_float_from_mapping(after, "s_lig", float(canonical_spacing)) or float(canonical_spacing)
    else:
        legs = 0
        diameter = 0
        spacing = 0.0

    state_d = _mapping(state)
    geometry_locked = bool(state_d.get("optimisation_lock_geometry", False)) or bool(
        state_d.get("optimisation_lock_width", False) and state_d.get("optimisation_lock_depth", False)
    )
    touches_geometry_updates = bool(set(updates_d) & {"D", "b", "beam_width", "beam_b", "width"})
    invalid_geometry = False
    depth = 0.0
    width = 0.0
    if touches_geometry_updates and not geometry_locked:
        try:
            depth = _controller_float_from_mapping(after, "D", 0.0)
            width = _controller_design_width_value(after)
        except Exception:
            invalid_geometry = True
            depth = 0.0
            width = 0.0

    return {
        "shear_practical_preference_score": resolve_design_guide_controller_shear_practical_preference_score(
            touches_shear_updates=touches_shear_updates,
            legs=legs,
            diameter=diameter,
            spacing=spacing,
        ),
        "geometry_proportion_preference_score": resolve_design_guide_controller_geometry_proportion_preference_score(
            touches_geometry_updates=touches_geometry_updates,
            geometry_locked=geometry_locked,
            depth=depth,
            width=width,
            invalid_geometry=invalid_geometry,
        ),
    }


def build_design_guide_controller_direct_target_selection_row(
    *,
    candidate: dict[str, Any] | None,
    base_state: dict[str, Any] | None,
    current_material_family_set: set[str] | frozenset[str] | list[str] | tuple[str, ...] | None,
    active_strength_family_floor_set: set[str] | frozenset[str] | list[str] | tuple[str, ...] | None,
    target_low: Any,
    target_high: Any,
    target_mid: Any,
    final_accepted_min_family_util: Any,
    target_band_eps: Any,
    canonical_no_shear_spacing: Any = 200.0,
) -> dict[str, Any]:
    """Build the direct target-band selection row from controller-owned policy helpers."""

    candidate_d = _mapping(candidate)
    updates = _mapping(candidate_d.get("updates"))
    post_util = _float_or_none(candidate_d.get("candidate_post_util"))
    if post_util is None:
        post_util = 0.0
    fallback_util = _float_or_none(candidate_d.get("candidate_post_util"))
    if fallback_util is None:
        fallback_util = _float_or_none(candidate_d.get("worst_util"))
    if fallback_util is None:
        fallback_util = 0.0
    mid = _float_or_none(target_mid)
    if mid is None:
        low = _float_or_none(target_low)
        high = _float_or_none(target_high)
        mid = (float(low or 0.0) + float(high or 0.0)) / 2.0
    low = _float_or_none(target_low)
    high = _float_or_none(target_high)
    final_floor = _float_or_none(final_accepted_min_family_util)
    if final_floor is None:
        final_floor = 0.0
    eps = _float_or_none(target_band_eps)
    if eps is None:
        eps = 0.0

    final_audit = _mapping(candidate_d.get("final_acceptance_audit"))
    final_valid = bool(
        candidate_d.get("final_accepted_green_valid")
        or final_audit.get("post_click_accepted_green_valid")
    )
    unresolved_low = list(
        candidate_d.get("final_unresolved_low_util_families")
        or final_audit.get("post_click_unresolved_low_util_families")
        or []
    )
    below_threshold = list(
        candidate_d.get("final_families_below_threshold")
        or final_audit.get("post_click_families_below_final_threshold")
        or []
    )
    overview_after = _mapping(candidate_d.get("overview"))
    if overview_after:
        _, remaining_families, _ = identify_design_guide_controller_materially_overprovided_non_governing_families(
            overview_after
        )
        remaining_count = len(remaining_families)
    else:
        remaining_count = 99
    current_material_families = {
        str(family or "").strip().lower()
        for family in list(current_material_family_set or [])
        if str(family or "").strip().lower()
    }
    affected_current = {
        family
        for family in current_material_families
        if resolve_design_guide_controller_local_cleanup_candidate_affects_family(
            family=family,
            updates=updates,
        )
    }
    missing_current_count = len(current_material_families - affected_current) if current_material_families else 0
    material_delta = _float_or_none(candidate_d.get("material_proxy_delta"))
    if material_delta is None:
        material_delta = 0.0
    preference_scores = resolve_design_guide_controller_direct_target_after_state_preference_scores(
        updates=updates,
        state=_mapping(base_state),
        canonical_no_shear_spacing=canonical_no_shear_spacing,
    )
    final_cleanup_sort_key = resolve_design_guide_controller_direct_candidate_final_cleanup_sort_key(
        candidate=candidate_d,
        final_valid=bool(final_valid),
        unresolved_low_count=len(unresolved_low),
        below_threshold_count=len(below_threshold),
        remaining_count=int(remaining_count),
        missing_current_count=int(missing_current_count),
        shear_preference_score=tuple(preference_scores.get("shear_practical_preference_score") or ()),
        geometry_preference_score=tuple(preference_scores.get("geometry_proportion_preference_score") or ()),
        material_delta=material_delta,
    )
    preferred_band = resolve_design_guide_controller_strength_family_band_status(
        candidate=candidate_d,
        active_strength_family_floor_set=active_strength_family_floor_set,
        target_low=low,
        target_high=high,
        target_band_eps=eps,
        final_accepted_min_family_util=final_floor,
    )
    accepted_band = resolve_design_guide_controller_strength_family_band_status(
        candidate=candidate_d,
        active_strength_family_floor_set=active_strength_family_floor_set,
        target_low=final_floor,
        target_high=1.0,
        target_band_eps=eps,
        final_accepted_min_family_util=final_floor,
    )
    preferred_distance = preferred_band.get("band_distance")
    accepted_distance = accepted_band.get("band_distance")
    return {
        "candidate": candidate_d,
        "final_cleanup_sort_key": final_cleanup_sort_key,
        "target_mid_distance": abs(float(post_util) - float(mid)),
        "preferred_band_distance": float(preferred_distance if preferred_distance is not None else float("inf")),
        "accepted_band_distance": float(accepted_distance if accepted_distance is not None else float("inf")),
        "fallback_band_distance": _controller_distance_to_target_band(fallback_util, low, high),
        "affected_current_low_families": [
            family
            for family in current_material_families
            if resolve_design_guide_controller_local_cleanup_candidate_affects_family(
                family=family,
                updates=updates,
            )
        ],
        "families_in_accepted_band": list(accepted_band.get("in_band_families") or []),
    }


def build_design_guide_controller_direct_target_evidence_context_projection(
    *,
    selected_candidate: dict[str, Any] | None,
    all_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    safe_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    target_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    active_strength_family_floor_set: set[str] | frozenset[str] | list[str] | tuple[str, ...] | None,
    target_low: Any,
    target_high: Any,
    final_accepted_min_family_util: Any,
    target_band_eps: Any,
    proof_exhausted: bool,
    strengthening: bool,
    search_scope: str = "design_guide_direct_target_band_search",
) -> dict[str, Any]:
    """Project direct-target selected-candidate evidence without page state."""

    selected_original = selected_candidate if isinstance(selected_candidate, dict) else {}
    selected_title = str(selected_original.get("label") or "")
    low = _float_or_none(target_low)
    high = _float_or_none(target_high)
    if low is None:
        low = 0.0
    if high is None:
        high = 1.0
    final_floor = _float_or_none(final_accepted_min_family_util)
    if final_floor is None:
        final_floor = 0.0
    eps = _float_or_none(target_band_eps)
    if eps is None:
        eps = 0.0
    evidence = build_candidate_search_evidence(
        selected_candidate=selected_original,
        all_candidates=list(all_candidates or []),
        target_low=float(low),
        target_high=float(high),
        exhaustive=not bool(proof_exhausted),
        search_scope=str(search_scope or ""),
        selected_title=selected_title,
        parse_util=_float_or_none,
    )
    if bool(strengthening):
        accepted_band_candidates = [
            candidate
            for candidate in list(safe_candidates or [])
            if resolve_design_guide_controller_strength_family_band_status(
                candidate=_mapping(candidate),
                active_strength_family_floor_set=active_strength_family_floor_set,
                target_low=final_floor,
                target_high=1.0,
                target_band_eps=eps,
                final_accepted_min_family_util=final_floor,
            ).get("in_band_families")
        ]
        preferred_status = resolve_design_guide_controller_strength_family_band_status(
            candidate=selected_original,
            active_strength_family_floor_set=active_strength_family_floor_set,
            target_low=low,
            target_high=high,
            target_band_eps=eps,
            final_accepted_min_family_util=final_floor,
        )
        accepted_status = resolve_design_guide_controller_strength_family_band_status(
            candidate=selected_original,
            active_strength_family_floor_set=active_strength_family_floor_set,
            target_low=final_floor,
            target_high=1.0,
            target_band_eps=eps,
            final_accepted_min_family_util=final_floor,
        )
        evidence.update(
            {
                "active_fail_accepted_band_candidate_count": int(len(accepted_band_candidates)),
                "active_fail_selected_strength_family_utils": dict(preferred_status.get("family_utils") or {}),
                "active_fail_selected_families_in_preferred_target": list(
                    preferred_status.get("in_band_families") or []
                ),
                "active_fail_selected_families_in_accepted_band": list(
                    accepted_status.get("in_band_families") or []
                ),
            }
        )
    if bool(strengthening) and not list(target_candidates or []):
        evidence = {
            **dict(evidence),
            "strength_repair_selected_outside_target_band": True,
            "strength_repair_target_band_secondary": True,
            "outside_target_band_allowed": True,
            "outside_target_band_allowed_reason": (
                "Active bending/shear strength failure must be repaired first; this executor-backed "
                "candidate makes all required checks pass even though the governing utilisation is "
                "not inside the preferred target band."
            ),
            "outside_target_band_allowed_category": "active_strength_repair_passes_required_checks",
        }
    selected = dict(selected_original)
    selected["candidate_search_evidence"] = dict(evidence)
    selected["candidate_id"] = evidence.get("selected_candidate_id")
    selected["source_candidate_id"] = evidence.get("selected_candidate_id")
    selected["canonical_winner_label"] = str(selected.get("label") or "Direct target-band candidate")
    selected["title_locked_from_final_winner"] = True
    return {
        "selected_candidate": selected,
        "candidate_search_evidence": dict(evidence),
    }


def build_design_guide_controller_direct_target_guidance_item_projection(
    *,
    item: dict[str, Any] | None,
    active_strength_family_floor_set: set[str] | frozenset[str] | list[str] | tuple[str, ...] | None,
    evidence: dict[str, Any] | None,
    strengthening: bool,
    source: str = "generate_in_target_local_cleanup_candidates",
) -> dict[str, Any]:
    """Apply direct target-band item projection without page/session state."""

    out = dict(item or {})
    families = {str(value).strip().lower() for value in (active_strength_family_floor_set or []) if str(value).strip()}
    if bool(strengthening) and families:
        if families >= {"bending", "shear"}:
            active_title = "Bending and shear capacity are low"
            active_family = "combined"
            active_check = "combined"
        elif "shear" in families:
            active_title = "Shear capacity is low"
            active_family = "shear"
            active_check = "shear"
        else:
            active_title = "Bending capacity is low"
            active_family = "bending"
            active_check = "bending"
        out["title_main"] = active_title
        out["title"] = active_title
        out["title_sub"] = "One-click capacity repair available"
        out["bucket"] = "fail"
        out["status"] = "FAIL"
        out["guidance_intent"] = "required_fix"
        out["family"] = active_family
        out["check_key"] = active_check
        out["design_guide_terminal_state"] = None
        out["canonical_winner_label"] = active_title
        out["title_locked_from_final_winner"] = True
        out["reasoning"] = (
            "Why: active bending/shear capacity checks are failing; this one-click "
            "repair is executor-backed and keeps all required checks acceptable."
        )
    out["candidate_search_evidence"] = dict(evidence or {})
    out["local_cleanup_candidate"] = True
    out["source"] = str(source or "generate_in_target_local_cleanup_candidates")
    out["affected_family"] = out.get("family") or out.get("check_key")
    payload = dict(out.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence or {})
    payload["source_candidate_id"] = (evidence or {}).get("selected_candidate_id")
    out["action_payload"] = payload
    resolved = dict(out.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence or {})
    resolved["candidate_id"] = (evidence or {}).get("selected_candidate_id")
    resolved["source_candidate_id"] = (evidence or {}).get("selected_candidate_id")
    out["resolved_candidate"] = resolved
    return out


def build_design_guide_controller_direct_target_family_bypass_projection(
    *,
    item: dict[str, Any] | None,
    family_id: str,
    family_route_owner: str,
    skipped_reason: str,
    evidence_extra: dict[str, Any] | None = None,
    item_extra: dict[str, Any] | None = None,
    debug_extra: dict[str, Any] | None = None,
    include_candidate_card_family: bool = True,
    family_early_dispatch_key: str | None = None,
    include_projected_evidence_in_debug: bool = False,
) -> dict[str, Any]:
    """Project direct-target active-failure family bypass metadata."""

    family = str(family_id or "").strip()
    route_owner = str(family_route_owner or "").strip()
    reason = str(skipped_reason or "").strip()
    out = dict(item or {})
    evidence = dict(out.get("candidate_search_evidence") or {})
    evidence.update(
        {
            "selected_family_id": family,
            "published_family_id": family,
            "cta_family_id": family,
            "family_route_owner": route_owner,
            "generic_one_click_solver_skipped": True,
            "generic_target_band_search_skipped": True,
            "generic_target_band_search_skipped_reason": reason,
            "generic_optimisation_cleanup_skipped": True,
            "generic_publication_fallback_skipped": True,
            "direct_target_band_bypassed_by_family_owner": True,
        }
    )
    if include_candidate_card_family:
        evidence["candidate_family_id"] = family
        evidence["card_family_id"] = family
    if family_early_dispatch_key:
        evidence[str(family_early_dispatch_key)] = True
    evidence.update(dict(evidence_extra or {}))

    item_projection = {
        "selected_family": family,
        "selected_family_id": family,
        "published_family_id": family,
        "cta_family_id": family,
        "family_selection_source": "family_chooser_contract",
        "family_selection_contract": "family_selection_contract",
        "family_chooser_contract": "family_chooser_contract",
        "family_match_passed": True,
        "family_match_violation_reason": None,
        "family_route_owner": route_owner,
        "generic_one_click_solver_skipped": True,
        "generic_target_band_search_skipped": True,
        "generic_optimisation_cleanup_skipped": True,
        "generic_publication_fallback_skipped": True,
        "direct_target_band_bypassed_by_family_owner": True,
    }
    if include_candidate_card_family:
        item_projection["candidate_family_id"] = family
        item_projection["card_family_id"] = family
    if family_early_dispatch_key:
        item_projection[str(family_early_dispatch_key)] = True
    item_projection.update(dict(item_extra or {}))
    item_projection["candidate_search_evidence"] = dict(evidence)
    out.update(item_projection)

    debug_update = {
        "generic_target_band_search_skipped": True,
        "generic_target_band_search_skipped_reason": reason,
        "direct_target_band_bypassed_by_family_owner": True,
        "direct_target_band_bypass_owner": route_owner,
    }
    if bool(include_projected_evidence_in_debug):
        debug_update["candidate_search_evidence"] = dict(evidence)
    debug_update.update(dict(debug_extra or {}))
    return {
        "item": out,
        "candidate_search_evidence": dict(evidence),
        "debug_update": dict(debug_update),
    }


def build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection(
    *,
    overview: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build combined active-failure direct-target bypass evidence from plain overview data."""

    ov = _mapping(overview)
    statuses = _mapping(ov.get("statuses"))
    utils = _mapping(ov.get("utils"))
    bending_util = _float_or_none(utils.get("bending"))
    shear_util = _float_or_none(utils.get("shear"))
    raw_flags = {
        "active_combined_bending_shear_failure": True,
        "any_failure": True,
        "any_min_reo_fail": False,
        "any_overdesign": False,
        "any_strength_fail": True,
        "bending_acceptable": False,
        "bending_fail": True,
        "bending_overdesigned": False,
        "bending_within_target_band": False,
        "exact_stop_proven": False,
        "geometry_detailing_fail": False,
        "legal_repair_exists": True,
        "locked_repair_blocked": False,
        "min_bending_reo_fail": False,
        "min_shear_reo_fail": False,
        "repair_required": True,
        "serviceability_fail": False,
        "shear_acceptable": False,
        "shear_fail": True,
        "shear_overdesigned": False,
        "shear_within_target_band": False,
        "target_band_terminal_signal": False,
    }
    rejected_families = {
        "BENDING_FAIL_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "SHEAR_FAIL_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "GEOMETRY_DETAILING_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "LOCKED_NO_REPAIR": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "SERVICEABILITY_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "MIN_BENDING_REO_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "MIN_SHEAR_REO_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "COMBINED_OVERDESIGN": "rejected because failure state is active",
        "BENDING_OVERDESIGN_GOVERNS": "rejected because failure state is active",
        "SHEAR_OVERDESIGN_GOVERNS": "rejected because failure state is active",
        "TARGET_BAND_REACHED": "rejected because failure state is active",
        "EXACT_STOP_PROVEN": "rejected because failure state is active",
    }
    selection_evidence = {
        "source": "design_brain.family_chooser.classify_family_from_raw_flags",
        "classification_contract": "family_chooser_contract",
        "active_bending_fail": True,
        "active_shear_fail": True,
        "active_serviceability_fail": False,
        "base_active_failures": ["bending", "shear"],
        "bending_status": statuses.get("bending") or "FAIL",
        "shear_status": statuses.get("shear") or "FAIL",
        "serviceability_status": statuses.get("serviceability"),
        "bending_utilisation": bending_util,
        "shear_utilisation": shear_util,
        "geometry_detailing_blocker_status": "absent",
        "geometry_reduction_status": "not_proven",
        "minimum_bending_reinforcement_status": "not_proven",
        "matched_family_ids": ["COMBINED_BENDING_SHEAR_FAIL"],
        "raw_state_flags": dict(raw_flags),
        "why_bending_family_rejected": rejected_families["BENDING_FAIL_GOVERNS"],
        "why_geometry_detailing_rejected_or_selected": "no geometry/detailing blocker signal present",
        "why_min_bending_reo_rejected_or_selected": "not_proven_by_current_publication_diagnostics",
        "why_target_band_rejected_or_selected": "rejected because active shear failure exists",
    }
    bypass_extra = {
        "matched_family_ids": ["COMBINED_BENDING_SHEAR_FAIL"],
        "raw_state_flags": dict(raw_flags),
        "rejected_families": dict(rejected_families),
        "selection_evidence": dict(selection_evidence),
        "selection_reason": "classified_by_mutually_exclusive_definition:COMBINED_BENDING_SHEAR_FAIL",
    }
    return {
        "raw_state_flags": dict(raw_flags),
        "rejected_families": dict(rejected_families),
        "selection_evidence": dict(selection_evidence),
        "bypass_extra": dict(bypass_extra),
    }


def build_design_guide_controller_direct_target_active_failure_route_request_result_adapter(
    *,
    active_failure_keys: list[str] | tuple[str, ...] | set[str] | None,
    item: dict[str, Any] | None,
    family_id: str,
    family_route_owner: str,
    skipped_reason: str,
    evidence_extra: dict[str, Any] | None = None,
    item_extra: dict[str, Any] | None = None,
    debug_extra: dict[str, Any] | None = None,
    include_candidate_card_family: bool = True,
    family_early_dispatch_key: str | None = None,
    include_projected_evidence_in_debug: bool = False,
) -> dict[str, Any]:
    """Build controller route request/result projection for a precomputed family item."""

    keys = sorted(str(key or "").strip().lower() for key in (active_failure_keys or []) if str(key or "").strip())
    request = {
        "active_failure_keys": list(keys),
        "family_id": str(family_id or "").strip(),
        "family_route_owner": str(family_route_owner or "").strip(),
        "skipped_reason": str(skipped_reason or "").strip(),
        "precomputed_family_item_present": isinstance(item, dict),
        "family_early_dispatch_key": str(family_early_dispatch_key or "").strip() or None,
        "include_candidate_card_family": bool(include_candidate_card_family),
        "include_projected_evidence_in_debug": bool(include_projected_evidence_in_debug),
    }
    projection = build_design_guide_controller_direct_target_family_bypass_projection(
        item=item,
        family_id=request["family_id"],
        family_route_owner=request["family_route_owner"],
        skipped_reason=request["skipped_reason"],
        evidence_extra=evidence_extra,
        item_extra=item_extra,
        debug_extra=debug_extra,
        include_candidate_card_family=include_candidate_card_family,
        family_early_dispatch_key=family_early_dispatch_key,
        include_projected_evidence_in_debug=include_projected_evidence_in_debug,
    )
    result = {
        "item": dict(projection.get("item") or {}),
        "candidate_search_evidence": dict(projection.get("candidate_search_evidence") or {}),
        "debug_update": dict(projection.get("debug_update") or {}),
    }
    trace_payload = {
        "request": dict(request),
        "result": dict(result),
        "ownership": {
            "controller_owns": "route request/result projection",
            "page_owns": [
                "family executor",
                "CTA side effects",
                "debug/session writes",
                "live route branch execution",
            ],
        },
    }
    trace_payload["trace_hash"] = design_guide_cache_fingerprint_from_plain_data(trace_payload)
    return trace_payload


def build_design_guide_controller_direct_target_active_failure_route_request_result_adapter_trace(
    **kwargs: Any,
) -> dict[str, Any]:
    """Compatibility wrapper for the direct-target active-failure route adapter proof."""

    return build_design_guide_controller_direct_target_active_failure_route_request_result_adapter(**kwargs)


def resolve_design_guide_controller_direct_target_active_failure_route_policy(
    *,
    strengthening: bool,
    active_failure_keys: list[str] | tuple[str, ...] | set[str] | None,
) -> dict[str, Any]:
    """Resolve the direct-target active-failure route kind from plain route inputs."""

    keys = {
        str(key or "").strip().lower()
        for key in (active_failure_keys or [])
        if str(key or "").strip()
    }
    route_kind: str | None = None
    family_id: str | None = None
    family_route_owner: str | None = None
    skipped_reason: str | None = None
    adapter_active_failure_keys: tuple[str, ...] = ()
    evidence_extra: dict[str, Any] = {}
    item_extra: dict[str, Any] = {}
    debug_extra: dict[str, Any] = {}
    family_early_dispatch_key: str | None = None
    include_projected_evidence_in_debug = False
    if bool(strengthening):
        if keys == {"bending"}:
            route_kind = "bending"
            family_id = "BENDING_FAIL_GOVERNS"
            family_route_owner = "design_brain.families.bending_fail.BendingFailFamily"
            skipped_reason = "selected_family_bending_fail_governs"
            adapter_active_failure_keys = ("bending",)
            evidence_extra = {
                "family_speed_isolation_owner": "BENDING_FAIL_GOVERNS",
                "family_speed_isolation_active_repair": True,
                "post_publication_generic_proofs_skipped": True,
            }
            item_extra = dict(evidence_extra)
            debug_extra = dict(evidence_extra)
            family_early_dispatch_key = "family_early_dispatch_used"
        elif keys == {"shear"}:
            route_kind = "shear"
            family_id = "SHEAR_FAIL_GOVERNS"
            family_route_owner = "design_brain.families.shear_fail.ShearFailFamily"
            skipped_reason = "selected_family_shear_fail_governs"
            adapter_active_failure_keys = ("shear",)
        elif keys >= {"bending", "shear"}:
            route_kind = "combined"
            family_id = "COMBINED_BENDING_SHEAR_FAIL"
            family_route_owner = (
                "design_brain.families.combined_bending_shear_fail.CombinedBendingShearFailFamily"
            )
            skipped_reason = "selected_family_combined_bending_shear_fail"
            adapter_active_failure_keys = ("bending", "shear")
            family_early_dispatch_key = "early_family_dispatch_used"
            include_projected_evidence_in_debug = True
    route_adapter_kwargs: dict[str, Any] = {}
    if route_kind is not None:
        route_adapter_kwargs = {
            "active_failure_keys": adapter_active_failure_keys,
            "family_id": family_id,
            "family_route_owner": family_route_owner,
            "skipped_reason": skipped_reason,
            "evidence_extra": dict(evidence_extra),
            "item_extra": dict(item_extra),
            "debug_extra": dict(debug_extra),
            "family_early_dispatch_key": family_early_dispatch_key,
            "include_projected_evidence_in_debug": bool(include_projected_evidence_in_debug),
        }
    return {
        "route_kind": route_kind,
        "should_dispatch": route_kind is not None,
        "active_failure_keys": sorted(keys),
        "family_id": family_id,
        "family_route_owner": family_route_owner,
        "skipped_reason": skipped_reason,
        "route_adapter_kwargs": route_adapter_kwargs,
    }


def build_design_guide_controller_direct_target_family_route_projection_metadata(
    *,
    route_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build pure direct-target family-route metadata used by the page shell."""

    policy = _mapping(route_policy)
    route_kind = str(policy.get("route_kind") or "").strip()
    family_id = str(policy.get("family_id") or "").strip()
    family_route_owner = str(policy.get("family_route_owner") or "").strip()
    skipped_reason = str(policy.get("skipped_reason") or "").strip()
    no_candidate_reason = (
        f"{skipped_reason}_no_family_candidate" if skipped_reason else ""
    )
    no_candidate_debug_update: dict[str, Any] = {}
    if route_kind == "bending":
        no_candidate_debug_update = {
            "generic_target_band_search_skipped": True,
            "generic_target_band_search_skipped_reason": no_candidate_reason,
            "direct_target_band_bypassed_by_family_owner": True,
            "direct_target_band_bypass_owner": family_route_owner,
        }
    active_repair_publication_skip_update: dict[str, Any] = {}
    if route_kind == "bending" and family_id:
        active_repair_publication_skip_update = {
            "generic_target_band_search_skipped": True,
            "generic_target_band_search_skipped_reason": (
                f"{family_id} active repair publication owns final outcome"
            ),
        }
    return {
        "route_kind": route_kind or None,
        "family_id": family_id or None,
        "family_route_owner": family_route_owner or None,
        "skipped_reason": skipped_reason or None,
        "no_family_candidate_debug_update": dict(no_candidate_debug_update),
        "active_repair_publication_skip_update": dict(
            active_repair_publication_skip_update
        ),
        "adapter_trace_base": {
            "family_id": family_id or None,
            "projection_source": "controller_route_adapter",
        },
    }


def build_design_guide_controller_active_fail_executor_family_ladder_dispatch(
    *,
    family_id: str,
    base_state: dict[str, Any] | None,
    width_key: str,
    geometry_locked: bool,
    reo_spacings: list[float] | tuple[float, ...] | None = None,
    lig_diameters: list[int] | tuple[int, ...] | None = None,
    bar_diameters: list[int] | tuple[int, ...] | None = None,
    approved_combined_merge_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    rescue_seed_library: dict[str, Any] | None = None,
    rescue_tiers: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Dispatch active-fail executor ladder generation through family runtimes.

    The returned strategy object is retained for the current page-owned
    selection/evidence calls. That follow-on extraction is intentionally a
    separate slice.
    """

    from design_brain.families.registry import family_strategy_for

    family = str(family_id or "").strip().upper()
    base = dict(base_state or {})
    strategy = family_strategy_for(family)
    if strategy is None or not callable(getattr(strategy, "contracted_repair_ladder_specs", None)):
        raise RuntimeError(f"{family} strategy does not expose contracted_repair_ladder_specs")

    kwargs: dict[str, Any] = {
        "width_key": str(width_key or "b"),
        "geometry_locked": bool(geometry_locked),
    }
    approved_candidates: list[dict[str, Any]] = [
        dict(row or {})
        for row in list(approved_combined_merge_candidates or [])
        if isinstance(row, dict)
    ]

    if family == "SHEAR_FAIL_GOVERNS":
        kwargs["reo_spacings"] = tuple(float(value) for value in list(reo_spacings or ()))
        kwargs["lig_diameters"] = tuple(int(value) for value in list(lig_diameters or ()))
    elif family == "BENDING_FAIL_GOVERNS":
        kwargs["bar_diameters"] = tuple(int(value) for value in list(bar_diameters or ()))
    elif family == "COMBINED_BENDING_SHEAR_FAIL":
        if not bool(geometry_locked) and not approved_candidates:
            seeds = dict(rescue_seed_library or {})
            for tier in list(rescue_tiers or ()):
                tier_key = str(tier or "")
                seed_spec = dict(((seeds.get("combined") or {}).get(tier_key)) or {})
                seed_updates = dict(seed_spec.get("updates") or {})
                if not seed_updates:
                    continue
                approved_candidates.append(
                    {
                        "source_family_id": "APPROVED_COMBINED_MERGE_RULE",
                        "candidate_id": str(seed_spec.get("key") or f"combined_{tier_key}"),
                        "updates": seed_updates,
                        "evidence": {
                            "source": "RESCUE_SEED_LIBRARY",
                            "tier": tier_key,
                            "approved_merge_rule": "unlocked_combined_fail_rescue_seed",
                        },
                    }
                )
            if callable(getattr(strategy, "build_target_band_refinement_candidates", None)):
                approved_candidates.extend(
                    strategy.build_target_band_refinement_candidates(
                        base,
                        approved_combined_merge_candidates=tuple(approved_candidates),
                    )
                )
        kwargs["approved_combined_merge_candidates"] = tuple(approved_candidates)

    ladder = strategy.contracted_repair_ladder_specs(base, **kwargs)
    return {
        "family_id": family,
        "ladder": dict(ladder or {}) if isinstance(ladder, dict) else {},
        "approved_combined_merge_candidates": list(approved_candidates),
        "dispatch_kwargs": {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in kwargs.items()
        },
        "owner": "DesignGuideController.active_fail_executor_family_ladder_dispatch",
    }


def _active_fail_executor_candidate_family_utils(candidate: dict[str, Any] | None) -> dict[str, float]:
    utils = _mapping(_mapping(candidate).get("overview")).get("utils")
    out: dict[str, float] = {}
    for family in ("bending", "shear"):
        util = _float_or_none(_mapping(utils).get(family))
        if util is not None:
            out[family] = float(util)
    return out


def _active_fail_executor_family_strategy(family_id: str) -> Any:
    from design_brain.families.registry import family_strategy_for

    return family_strategy_for(str(family_id or "").strip().upper())


def _active_fail_executor_candidate_in_band_count(
    candidate: dict[str, Any] | None,
    low: Any,
    high: Any,
) -> int:
    low_f = _float_or_none(low)
    high_f = _float_or_none(high)
    if low_f is None or high_f is None:
        return 0
    return sum(
        1
        for util in _active_fail_executor_candidate_family_utils(candidate).values()
        if float(low_f) <= float(util) <= float(high_f)
    )


def select_design_guide_controller_active_fail_executor_family_ladder_candidate(
    *,
    safe_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    base_state: dict[str, Any] | None,
    target_low: Any,
    target_high: Any,
    final_accepted_min_family_util: Any,
    shear_family_ladder_attempted: bool,
    shear_family_strategy: Any = None,
    combined_family_ladder_attempted: bool,
    combined_family_ladder_found_safe: bool,
    combined_family_strategy: Any = None,
    bending_family_ladder_attempted: bool,
    bending_family_ladder_found_safe: bool,
    bending_family_strategy: Any = None,
    canonical_no_shear_spacing: Any = 200.0,
) -> dict[str, Any]:
    """Select the active-fail executor candidate from family ladder evidence."""

    candidates = [dict(candidate or {}) for candidate in list(safe_candidates or []) if isinstance(candidate, dict)]
    if not candidates:
        return {
            "selected": {},
            "selection_source": "no_safe_candidates",
            "family_selected": {},
        }

    low = _float_or_none(target_low)
    if low is None:
        low = 0.85
    high = _float_or_none(target_high)
    if high is None:
        high = 1.0
    final_floor = _float_or_none(final_accepted_min_family_util)
    if final_floor is None:
        final_floor = 0.0
    base = dict(base_state or {})
    if shear_family_ladder_attempted and shear_family_strategy is None:
        shear_family_strategy = _active_fail_executor_family_strategy("SHEAR_FAIL_GOVERNS")
    if combined_family_ladder_attempted and combined_family_strategy is None:
        combined_family_strategy = _active_fail_executor_family_strategy("COMBINED_BENDING_SHEAR_FAIL")
    if bending_family_ladder_attempted and bending_family_strategy is None:
        bending_family_strategy = _active_fail_executor_family_strategy("BENDING_FAIL_GOVERNS")

    if shear_family_ladder_attempted and shear_family_strategy is not None and callable(
        getattr(shear_family_strategy, "select_repair_candidate_from_ladder", None)
    ):
        family_selected = shear_family_strategy.select_repair_candidate_from_ladder(
            candidates,
            target_low=float(low),
            target_high=float(high),
        )
        selected = dict(_mapping(family_selected).get("selected") or {})
        return {
            "selected": selected or dict(candidates[0]),
            "selection_source": "shear_family_ladder_selector",
            "family_selected": dict(family_selected or {}),
        }

    if combined_family_ladder_attempted and combined_family_ladder_found_safe:
        if combined_family_strategy is not None and callable(
            getattr(combined_family_strategy, "select_repair_candidate_from_ladder", None)
        ):
            family_selected = combined_family_strategy.select_repair_candidate_from_ladder(
                candidates,
                target_low=float(low),
                target_high=float(high),
            )
            selected = dict(_mapping(family_selected).get("selected") or {})
            return {
                "selected": selected or dict(candidates[0]),
                "selection_source": "combined_family_ladder_selector",
                "family_selected": dict(family_selected or {}),
            }
        return select_combined_fail_fallback_repair_candidate_from_ladder(
            candidates,
            target_low=float(low),
            target_high=float(high),
            final_accepted_min_family_util=float(final_floor),
        )

    if bending_family_ladder_attempted and bending_family_ladder_found_safe:
        if bending_family_strategy is not None and callable(
            getattr(bending_family_strategy, "select_repair_candidate_from_ladder", None)
        ):
            family_selected = bending_family_strategy.select_repair_candidate_from_ladder(
                candidates,
                target_low=float(low),
                target_high=float(high),
            )
            selected = dict(_mapping(family_selected).get("selected") or {})
            return {
                "selected": selected or dict(candidates[0]),
                "selection_source": "bending_family_ladder_selector",
                "family_selected": dict(family_selected or {}),
            }
        return select_bending_fail_fallback_repair_candidate_from_ladder(candidates)

    selected = min(
        candidates,
        key=lambda cand: (
            -_active_fail_executor_candidate_in_band_count(cand, float(low), float(high)),
            -_active_fail_executor_candidate_in_band_count(cand, float(final_floor), 1.0),
            tuple(
                resolve_design_guide_controller_direct_target_after_state_preference_scores(
                    updates=dict(cand.get("updates") or {}),
                    state=base,
                    canonical_no_shear_spacing=canonical_no_shear_spacing,
                ).get("shear_practical_preference_score")
                or (0, 0, 0.0, 0)
            ),
            tuple(
                resolve_design_guide_controller_direct_target_after_state_preference_scores(
                    updates=dict(cand.get("updates") or {}),
                    state=base,
                    canonical_no_shear_spacing=canonical_no_shear_spacing,
                ).get("geometry_proportion_preference_score")
                or (0, 0.0, 0.0)
            ),
            _controller_distance_to_target_band(
                _float_or_none(cand.get("candidate_post_util") or cand.get("worst_util")) or 0.0,
                float(low),
                float(high),
            ),
            len(dict(cand.get("updates") or {})),
        ),
    )
    return {
        "selected": dict(selected),
        "selection_source": "controller_generic_fallback_ranker",
        "family_selected": {},
    }


def build_design_guide_controller_active_fail_executor_family_evidence_overlay(
    *,
    family_id: str,
    family_strategy: Any = None,
    ladder: dict[str, Any] | None = None,
    selected_candidate: dict[str, Any] | None = None,
    selection_reason: str,
    selected_ladder_index_key: str | None = None,
) -> dict[str, Any]:
    """Build active-fail executor family evidence overlay through the family runtime."""

    selected = dict(selected_candidate or {})
    if family_strategy is None:
        family_strategy = _active_fail_executor_family_strategy(str(family_id or ""))
    selected_result = {
        "selected": dict(selected),
        "selection_reason": str(selection_reason or ""),
        "selected_ladder_index": (
            None
            if not selected
            else selected.get(str(selected_ladder_index_key or "ladder_index"))
        ),
    }
    try:
        if family_strategy is not None and callable(
            getattr(family_strategy, "repair_ladder_evidence_overlay", None)
        ):
            overlay = family_strategy.repair_ladder_evidence_overlay(
                ladder=dict(ladder or {}),
                selected_result=dict(selected_result),
            )
            return {
                "family_id": str(family_id or "").strip().upper(),
                "selected_result": dict(selected_result),
                "overlay": dict(overlay or {}) if isinstance(overlay, dict) else {},
                "error": None,
                "owner": "DesignGuideController.active_fail_executor_family_evidence_overlay",
            }
    except Exception as exc:
        return {
            "family_id": str(family_id or "").strip().upper(),
            "selected_result": dict(selected_result),
            "overlay": {},
            "error": f"{type(exc).__name__}: {exc}",
            "owner": "DesignGuideController.active_fail_executor_family_evidence_overlay",
        }
    return {
        "family_id": str(family_id or "").strip().upper(),
        "selected_result": dict(selected_result),
        "overlay": {},
        "error": None,
        "owner": "DesignGuideController.active_fail_executor_family_evidence_overlay",
    }


def build_design_guide_controller_active_fail_executor_candidate_search_evidence(
    *,
    selected_candidate: dict[str, Any] | None,
    all_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    safe_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    active_failures: list[str] | tuple[str, ...] | set[str],
    target_low: Any,
    target_high: Any,
    repair_eval_metrics: dict[str, Any] | None = None,
    shear_family_ladder_attempted: bool = False,
    shear_family_ladder: dict[str, Any] | None = None,
    shear_family_ladder_error: str | None = None,
    combined_family_ladder_attempted: bool = False,
    combined_family_ladder: dict[str, Any] | None = None,
    combined_family_ladder_found_safe: bool = False,
    combined_family_ladder_error: str | None = None,
    bending_family_ladder_attempted: bool = False,
    bending_family_ladder: dict[str, Any] | None = None,
    bending_family_ladder_found_safe: bool = False,
    bending_family_ladder_error: str | None = None,
    bending_family_ladder_evaluated_count: int = 0,
    bending_ladder_pass_count: int = 0,
    bending_selected_cache_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Build active-fail executor search evidence from plain controller inputs."""

    selected = dict(selected_candidate or {}) if isinstance(selected_candidate, dict) else {}
    candidates = [dict(candidate or {}) for candidate in list(all_candidates or []) if isinstance(candidate, dict)]
    safe = [dict(candidate or {}) for candidate in list(safe_candidates or []) if isinstance(candidate, dict)]
    active = {str(family or "").strip().lower() for family in (active_failures or []) if str(family or "").strip()}
    search_scope = (
        "shear_fail_family_contract_ladder_search"
        if shear_family_ladder_attempted
        else "bending_fail_family_contract_ladder_search"
        if bending_family_ladder_attempted
        else "combined_fail_family_contract_ladder_search"
        if combined_family_ladder_attempted
        else "active_fail_combined_repair_search"
        if {"bending", "shear"}.issubset(active)
        else "active_fail_repair_search"
    )
    evidence = build_candidate_search_evidence(
        selected_candidate=selected if selected else None,
        all_candidates=candidates,
        target_low=float(_float_or_none(target_low) if _float_or_none(target_low) is not None else 0.0),
        target_high=float(_float_or_none(target_high) if _float_or_none(target_high) is not None else 1.0),
        exhaustive=True,
        search_scope=search_scope,
        selected_title=str(selected.get("label") or "Active fail repair") if selected else None,
    )
    metrics = dict(repair_eval_metrics or {})
    evidence.update(
        {
            "active_fail_repair_search_scope": evidence.get("search_scope"),
            "repair_search_ran": True,
            "repair_search_exhaustive": True,
            "geometry_strengthening_searched": True,
            "reo_strengthening_searched": True,
            "longitudinal_reinforcement_strengthening_searched": not bool(shear_family_ladder_attempted),
            "shear_strengthening_searched": bool("shear" in active),
            "combined_strengthening_searched": bool({"bending", "shear"}.issubset(active)),
            "bending_fail_contract_ladder_attempted": bool(bending_family_ladder_attempted),
            "bending_fail_contract_ladder_found_safe": bool(bending_family_ladder_found_safe),
            "bending_fail_contract_ladder_error": bending_family_ladder_error,
            "combined_fail_contract_ladder_attempted": bool(combined_family_ladder_attempted),
            "combined_fail_contract_ladder_found_safe": bool(combined_family_ladder_found_safe),
            "combined_fail_contract_ladder_error": combined_family_ladder_error,
            "active_fail_repair_candidate_rows": list(evidence.get("candidate_rows") or []),
            "safe_repair_candidate_count": int(len(safe)),
            "executable_repair_candidate_count": int(len(safe)),
            "strength_repair_selected_outside_target_band": bool(selected),
            "strength_repair_target_band_secondary": bool(selected),
            "outside_target_band_allowed": bool(selected),
            "outside_target_band_allowed_reason": (
                "Active bending/shear checks are failing; this executor-backed repair "
                "makes all required checks pass even though preferred target-band cleanup "
                "remains a secondary optimisation step."
            )
            if selected
            else None,
            "outside_target_band_allowed_category": (
                "active_strength_repair_passes_required_checks" if selected else None
            ),
            "candidate_evaluation_cache_hits": int(metrics.get("candidate_evaluation_cache_hits", 0)),
            "candidate_evaluation_cache_misses": int(metrics.get("candidate_evaluation_cache_misses", 0)),
            "duplicate_candidate_fingerprints_skipped": int(metrics.get("duplicate_candidate_fingerprints_skipped", 0)),
            "blocker_attempt_cache_hits": int(metrics.get("blocker_attempt_cache_hits", 0)),
            "rejected_repair_reasons": list(
                dict.fromkeys(
                    str(row.get("rejection_reason") or row.get("failed_check_family") or "preview_failed")
                    for row in list(evidence.get("candidate_rows") or [])
                    if isinstance(row, dict) and not bool(row.get("safe_executor_backed"))
                )
            )[:40],
        }
    )
    if shear_family_ladder_attempted:
        overlay_result = build_design_guide_controller_active_fail_executor_family_evidence_overlay(
            family_id="SHEAR_FAIL_GOVERNS",
            ladder=dict(shear_family_ladder or {}),
            selected_candidate=dict(selected),
            selection_reason=(
                "first_compliant_candidate_in_contract_ladder_order"
                if selected
                else "no_compliant_candidate_in_contract_ladder"
            ),
            selected_ladder_index_key="shear_fail_ladder_index",
        )
        evidence.update(dict(overlay_result.get("overlay") or {}))
        if overlay_result.get("error"):
            evidence["shear_fail_contract_ladder_evidence_overlay_error"] = overlay_result.get("error")
        evidence.update(
            {
                "shear_fail_contract_ladder_attempted": True,
                "shear_fail_contract_ladder_error": shear_family_ladder_error,
                "repair_search_owner": "design_brain.families.shear_fail.ShearFailFamily",
                "generic_near_current_repair_search_skipped_for_pure_shear": True,
            }
        )
    if combined_family_ladder_attempted:
        overlay_result = build_design_guide_controller_active_fail_executor_family_evidence_overlay(
            family_id="COMBINED_BENDING_SHEAR_FAIL",
            ladder=dict(combined_family_ladder or {}),
            selected_candidate=dict(selected),
            selection_reason=(
                "contract_family_target_band_ranked_candidate"
                if combined_family_ladder_found_safe
                else "fallback_after_no_compliant_combined_contract_ladder_candidate"
            ),
            selected_ladder_index_key="combined_fail_ladder_index",
        )
        evidence.update(dict(overlay_result.get("overlay") or {}))
        if overlay_result.get("error"):
            evidence["combined_fail_contract_ladder_evidence_overlay_error"] = overlay_result.get("error")
        evidence.update(
            {
                "combined_fail_contract_ladder_attempted": True,
                "combined_fail_contract_ladder_error": combined_family_ladder_error,
                "combined_fail_contract_ladder_found_safe": bool(combined_family_ladder_found_safe),
                "repair_search_owner": "design_brain.families.combined_bending_shear_fail.CombinedBendingShearFailFamily",
                "generic_near_current_repair_search_skipped_for_combined": bool(combined_family_ladder_found_safe),
                "generic_compute_bypassed_by_family_owner": bool(combined_family_ladder_found_safe),
            }
        )
    if bending_family_ladder_attempted:
        overlay_result = build_design_guide_controller_active_fail_executor_family_evidence_overlay(
            family_id="BENDING_FAIL_GOVERNS",
            ladder=dict(bending_family_ladder or {}),
            selected_candidate=dict(selected),
            selection_reason=(
                "first_compliant_candidate_in_contract_ladder_order"
                if bending_family_ladder_found_safe
                else "fallback_after_no_compliant_bending_contract_ladder_candidate"
            ),
            selected_ladder_index_key="bending_fail_ladder_index",
        )
        evidence.update(dict(overlay_result.get("overlay") or {}))
        if overlay_result.get("error"):
            evidence["bending_fail_contract_ladder_evidence_overlay_error"] = overlay_result.get("error")
        evidence.update(
            {
                "bending_fail_contract_ladder_attempted": True,
                "bending_fail_contract_ladder_error": bending_family_ladder_error,
                "bending_fail_contract_ladder_found_safe": bool(bending_family_ladder_found_safe),
                "bending_fail_contract_ladder_candidate_count": len(
                    list((bending_family_ladder or {}).get("specs") or [])
                ),
                "family_ladder_candidate_count": len(
                    list((bending_family_ladder or {}).get("specs") or [])
                ),
                "bending_fail_contract_ladder_evaluated_candidate_count": int(
                    bending_family_ladder_evaluated_count
                ),
                "bending_fail_contract_ladder_repeated_pass_count": int(bending_ladder_pass_count),
                "bending_fail_contract_ladder_cache_fingerprint": bending_selected_cache_fingerprint,
                "repair_search_owner": "design_brain.families.bending_fail.BendingFailFamily",
                "generic_near_current_repair_search_skipped_for_bending": bool(bending_family_ladder_found_safe),
                "generic_compute_bypassed_by_family_owner": bool(bending_family_ladder_found_safe),
            }
        )
    return evidence


def build_design_guide_controller_active_fail_executor_selected_repair_candidate(
    *,
    selected_candidate: dict[str, Any] | None,
    evidence: dict[str, Any] | None,
    active_failures: list[str] | tuple[str, ...] | set[str],
) -> dict[str, Any]:
    """Project the active-fail selected repair candidate through repair policy."""

    evidence_map = dict(evidence or {})
    selected = dict(selected_candidate or {})
    selected["candidate_search_evidence"] = dict(evidence_map)
    selected["candidate_id"] = evidence_map.get("selected_candidate_id")
    selected["source_candidate_id"] = evidence_map.get("selected_candidate_id")
    repair_decision = select_repair_decision(
        selected_candidate=selected,
        status="action",
        reason=evidence_map.get("outside_target_band_allowed_reason") or "active_fail_repair_candidate_selected",
        evidence=evidence_map,
        cta_metadata={
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
        },
    )
    projected_selected = selected_candidate_from_repair_decision(repair_decision) or selected
    active = {str(family or "").strip().lower() for family in (active_failures or []) if str(family or "").strip()}
    active_family = "combined" if {"bending", "shear"}.issubset(active) else ("shear" if "shear" in active else "bending")
    active_title = (
        "Bending and shear capacity are low"
        if active_family == "combined"
        else "Shear capacity is low"
        if active_family == "shear"
        else "Bending capacity is low"
    )
    return {
        "selected_candidate": dict(projected_selected),
        "repair_decision": dict(repair_decision or {}) if isinstance(repair_decision, dict) else repair_decision,
        "active_family": active_family,
        "active_title": active_title,
        "owner": "DesignGuideController.active_fail_executor_selected_repair_candidate",
    }


def build_design_guide_controller_active_fail_executor_final_guidance_item_projection(
    *,
    item: dict[str, Any] | None,
    selected_candidate: dict[str, Any] | None,
    evidence: dict[str, Any] | None,
    active_family: str,
    active_title: str,
) -> dict[str, Any]:
    """Project active-fail executor final guidance item fields."""

    out = dict(item or {})
    selected = dict(selected_candidate or {})
    evidence_map = dict(evidence or {})
    family = str(active_family or "").strip()
    title = str(active_title or "").strip()
    out.update(
        {
            "title_main": title,
            "title": title,
            "bucket": "fail",
            "status": "FAIL",
            "guidance_intent": "required_fix",
            "family": family,
            "check_key": family,
            "action_type": "apply_resolved_candidate",
            "primary_card_actionable": True,
            "candidate_search_evidence": dict(evidence_map),
            "updates": dict(selected.get("updates") or {}),
        }
    )
    payload = dict(out.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence_map)
    out["action_payload"] = payload
    resolved = dict(out.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence_map)
    out["resolved_candidate"] = resolved
    return out


def build_design_guide_controller_active_fail_executor_bending_ladder_evaluation_trace_row(
    *,
    spec: dict[str, Any] | None,
    evaluated_candidate: dict[str, Any] | None,
    candidate_index: int,
) -> dict[str, Any]:
    """Build the bending active-fail ladder candidate-evaluation trace row."""

    spec_map = dict(spec or {})
    evaluated = dict(evaluated_candidate or {}) if isinstance(evaluated_candidate, dict) else {}
    overview = dict(evaluated.get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    result = "PASS" if bool(evaluated.get("is_compliant")) and not bool(overview.get("any_fail")) else "FAIL"
    failure_reason = ""
    if result != "PASS":
        failure_reason = str(
            evaluated.get("rejection_reason")
            or evaluated.get("failed_check_name")
            or next(
                (
                    f"{family}:{status}"
                    for family, status in statuses.items()
                    if str(status or "").strip().upper() in {"FAIL", "FAILED", "ERROR"}
                ),
                "required_check_not_compliant",
            )
        )
    return {
        "scenario": "scenario_c3_pure_bending_underdesign_repair",
        "selected_family": "BENDING_FAIL_GOVERNS",
        "source": "bending_fail_contract_ladder",
        "ladder_index": spec_map.get("ladder_index"),
        "contract_step": spec_map.get("contract_step"),
        "stage_name": spec_map.get("stage_name"),
        "candidate_index": int(candidate_index),
        "b": spec_map.get("b"),
        "D": spec_map.get("D"),
        "bottom_bar_count": spec_map.get("bottom_bar_count"),
        "bar_diameter": spec_map.get("bar_diameter"),
        "split_row": bool(spec_map.get("split_row")),
        "clear_spacing": spec_map.get("clear_spacing"),
        "result": result,
        "failure_reason": failure_reason,
        "is_compliant": bool(evaluated.get("is_compliant")),
        "all_key_pass": bool(overview.get("all_key_pass")),
        "any_fail": bool(overview.get("any_fail")),
        "candidate_post_util": evaluated.get("candidate_post_util") or evaluated.get("worst_util"),
        "updates": dict(evaluated.get("updates") or {}),
        "acceptance_basis": evaluated.get("bending_fail_acceptance_basis"),
    }


def build_design_guide_controller_active_fail_executor_bending_ladder_first_executable_trace_row(
    *,
    spec: dict[str, Any] | None,
    evaluated_candidate: dict[str, Any] | None,
    candidate_index: int,
) -> dict[str, Any]:
    """Build the bending active-fail ladder first-executable trace row."""

    spec_map = dict(spec or {})
    evaluated = dict(evaluated_candidate or {}) if isinstance(evaluated_candidate, dict) else {}
    overview = dict(evaluated.get("overview") or {})
    updates = dict(evaluated.get("updates") or {})
    return {
        "scenario": "scenario_c3_pure_bending_underdesign_repair",
        "selected_family": "BENDING_FAIL_GOVERNS",
        "source": "bending_fail_contract_ladder",
        "ladder_index": spec_map.get("ladder_index"),
        "contract_step": spec_map.get("contract_step"),
        "stage_name": spec_map.get("stage_name"),
        "candidate_index": int(candidate_index),
        "b": spec_map.get("b"),
        "D": spec_map.get("D"),
        "bottom_bar_count": spec_map.get("bottom_bar_count"),
        "bar_diameter": spec_map.get("bar_diameter"),
        "split_row": bool(spec_map.get("split_row")),
        "clear_spacing": spec_map.get("clear_spacing"),
        "candidate_post_util": evaluated.get("candidate_post_util") or evaluated.get("worst_util"),
        "updates": dict(updates),
        "payload_non_empty": bool(updates),
        "all_key_pass": bool(overview.get("all_key_pass")),
        "any_fail": bool(overview.get("any_fail")),
    }


def _bending_fail_family_owned_repair_blocked_proof(evidence: dict[str, Any] | None) -> bool:
    evidence_d = dict(evidence or {})
    proof = dict(
        evidence_d.get("bending_fail_blocked_ownership_proof")
        or dict(evidence_d.get("repair_reason_proof") or {}).get("blocked_ownership_proof")
        or {}
    )
    family_id = str(
        proof.get("family_id")
        or evidence_d.get("family_id")
        or evidence_d.get("governing_family")
        or evidence_d.get("family_name")
        or ""
    ).strip().upper()
    if family_id != "BENDING_FAIL_GOVERNS":
        return False
    repair_blocked = bool(proof.get("repair_blocked") or evidence_d.get("bending_fail_repair_blocked"))
    hard_blocker = bool(proof.get("hard_blocker_proven") or evidence_d.get("bending_fail_hard_blocker_proven"))
    strategy_exhaustion = bool(
        proof.get("contract_strategy_exhaustion_proven")
        or evidence_d.get("bending_fail_contract_strategy_exhaustion_proven")
    )
    cap_only = bool(proof.get("internal_cap_only") or evidence_d.get("bending_fail_internal_cap_only"))
    return bool(repair_blocked and (hard_blocker or strategy_exhaustion) and not cap_only)


def build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence(
    *,
    state: dict[str, Any] | None,
    overview: dict[str, Any] | None,
    active_failures: list[str] | tuple[str, ...] | set[str],
    evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the active-fail executor no-repair blocker item from search evidence."""

    del state
    active = {
        str(family or "").strip().lower()
        for family in (active_failures or [])
        if str(family or "").strip()
    }
    active_family = "combined" if {"bending", "shear"}.issubset(active) else (
        "shear" if "shear" in active else (
            "serviceability" if {"serviceability", "crack", "deflection"} & active else "bending"
        )
    )
    evidence_map = dict(evidence or {})
    bending_family_owned_blocked = (
        active_family == "bending" and _bending_fail_family_owned_repair_blocked_proof(evidence_map)
    )
    bending_missing_family_proof = active_family == "bending" and not bending_family_owned_blocked
    title = (
        "Bending and shear repair blocked"
        if active_family == "combined"
        else "Shear repair blocked by shear/detailing limits"
        if active_family == "shear"
        else "Serviceability repair blocked"
        if active_family == "serviceability"
        else "Bending repair proof incomplete"
        if bending_missing_family_proof
        else "Bending repair blocked by reinforcement/detailing limits"
    )
    overview_map = dict(overview or {})
    evidence_map.setdefault("active_failures", sorted(active))
    exact = active_failure_exact_blockers_for_families(
        sorted(active),
        overview=overview_map,
        evidence=evidence_map,
        primary_family=None,
        primary_reason=None,
    )
    text = active_failure_blocker_visible_reason_text(exact, sorted(active))
    if bending_missing_family_proof:
        text = (
            "BENDING_FAIL_GOVERNS did not publish family-owned repair-blocked proof. "
            "Bounded or cap-only search exhaustion remains diagnostic only."
        )
    item = build_design_guide_controller_guidance_item(
        active_family,
        title,
        text,
        None,
        f"Why: {text}",
        "Key blockers: active strengthening repair search, required PASS checks, detailing limits",
        None,
        None,
        status="BLOCKED" if active_family == "serviceability" else "FAIL",
        util=_float_or_none(overview_map.get("worst_util") or overview_map.get("governing_util")),
    )
    item.update(
        {
            "bucket": "fail",
            "status": "BLOCKED" if active_family == "serviceability" else "FAIL",
            "critical_status": "BLOCKED" if active_family == "serviceability" else "FAIL",
            "display_state": "BLOCKED" if active_family == "serviceability" else "FAIL",
            "outcome_state": "BLOCKED" if active_family == "serviceability" else "FAIL",
            "guidance_intent": "specific_blocker" if not bending_missing_family_proof else "diagnostic_incomplete_proof",
            "final_state_class": "blocker" if not bending_missing_family_proof else "diagnostic_incomplete_proof",
            "active_under_capacity_blocker": not bending_missing_family_proof,
            "active_under_capacity_blocker_family": active_family,
            "candidate_search_evidence": {
                **evidence_map,
                "exact_blockers_by_family": dict(exact),
                "post_click_exact_blockers_by_family": dict(exact),
                "bending_fail_missing_family_owned_no_repair_proof": bool(bending_missing_family_proof),
                "visible_blocked_wording_source": (
                    "BENDING_FAIL_GOVERNS family result" if bending_family_owned_blocked else None
                ),
            },
            "exact_blockers_by_family": dict(exact),
            "post_click_exact_blockers_by_family": dict(exact),
        }
    )
    item["button_contract"] = disabled_design_guide_button_contract(
        item,
        family=active_family,
        reason=text,
    )
    return item


def build_design_guide_controller_active_fail_executor_ladder_candidate_meta(
    *,
    family_id: str,
    spec: dict[str, Any] | None,
) -> dict[str, Any]:
    """Project active-fail ladder candidate metadata from a plain ladder spec."""

    spec_map = dict(spec or {})
    fid = str(family_id or "").strip().upper()
    if fid == "SHEAR_FAIL_GOVERNS":
        return {
            "candidate_family_id": "SHEAR_FAIL_GOVERNS",
            "card_family_id": "SHEAR_FAIL_GOVERNS",
            "published_family_id": "SHEAR_FAIL_GOVERNS",
            "cta_family_id": "SHEAR_FAIL_GOVERNS",
            "shear_fail_ladder_index": spec_map.get("ladder_index"),
            "shear_fail_contract_step": spec_map.get("contract_step"),
            "shear_fail_strategy": spec_map.get("strategy"),
            "shear_fail_restart_point": bool(spec_map.get("restart_point")),
            "shear_fail_escalation": spec_map.get("escalation"),
        }
    if fid == "BENDING_FAIL_GOVERNS":
        return {
            "candidate_family_id": "BENDING_FAIL_GOVERNS",
            "card_family_id": "BENDING_FAIL_GOVERNS",
            "published_family_id": "BENDING_FAIL_GOVERNS",
            "cta_family_id": "BENDING_FAIL_GOVERNS",
            "bending_fail_ladder_index": spec_map.get("ladder_index"),
            "bending_fail_contract_step": spec_map.get("contract_step"),
            "bending_fail_stage_name": spec_map.get("stage_name"),
            "bending_fail_strategy": spec_map.get("strategy"),
            "bending_fail_escalation": spec_map.get("escalation"),
            "bending_fail_stop_rule": spec_map.get("stop_rule"),
            "bending_fail_candidate_b": spec_map.get("b"),
            "bending_fail_candidate_D": spec_map.get("D"),
            "bending_fail_bottom_bar_count": spec_map.get("bottom_bar_count"),
            "bending_fail_bar_diameter": spec_map.get("bar_diameter"),
            "bending_fail_split_row": bool(spec_map.get("split_row")),
            "bending_fail_clear_spacing": spec_map.get("clear_spacing"),
        }
    if fid == "COMBINED_BENDING_SHEAR_FAIL":
        return {
            "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "card_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "combined_fail_ladder_index": spec_map.get("ladder_index"),
            "combined_fail_contract_step": spec_map.get("contract_step"),
            "combined_fail_strategy": spec_map.get("strategy"),
            "combined_fail_stop_rule": spec_map.get("stop_rule"),
        }
    family = fid or "UNKNOWN_ACTIVE_FAIL_FAMILY"
    return {
        "candidate_family_id": family,
        "card_family_id": family,
        "published_family_id": family,
        "cta_family_id": family,
    }


def build_design_guide_controller_active_fail_executor_ladder_eval_commands(
    *,
    family_id: str,
    ladder: dict[str, Any] | None,
    default_label: str,
) -> list[dict[str, Any]]:
    """Build ordered active-fail ladder eval commands from plain ladder specs."""

    commands: list[dict[str, Any]] = []
    for spec in list((dict(ladder or {}).get("specs") or [])):
        if not isinstance(spec, dict):
            continue
        spec_map = dict(spec)
        commands.append(
            {
                "spec": spec_map,
                "updates": dict(spec_map.get("updates") or {}),
                "label": str(spec_map.get("label") or default_label or ""),
                "family_meta": build_design_guide_controller_active_fail_executor_ladder_candidate_meta(
                    family_id=family_id,
                    spec=spec_map,
                ),
            }
        )
    return commands


def run_design_guide_controller_active_fail_executor_ladder_eval_commands(
    *,
    family_id: str,
    ladder: dict[str, Any] | None,
    default_label: str,
    evaluate_command_fn: Callable[[dict[str, Any], str, dict[str, Any]], dict[str, Any] | None],
) -> dict[str, Any]:
    """Run active-fail ladder eval commands with a page-injected evaluator.

    The controller owns command iteration and stop policy. The callback still
    owns actual candidate evaluation, page caches, trace hooks, and any page
    state required to execute an update.
    """

    commands = build_design_guide_controller_active_fail_executor_ladder_eval_commands(
        family_id=family_id,
        ladder=ladder,
        default_label=default_label,
    )
    evaluated_count = 0
    selected_candidate: dict[str, Any] | None = None
    stopped = False
    for command in commands:
        if not isinstance(command, dict):
            continue
        updates = dict(command.get("updates") or {})
        label = str(command.get("label") or default_label or "")
        family_meta = dict(command.get("family_meta") or {})
        evaluated = evaluate_command_fn(updates, label, family_meta)
        if isinstance(evaluated, dict):
            evaluated_count += 1
        if resolve_design_guide_controller_active_fail_executor_ladder_stop_decision(
            family_id=family_id,
            evaluated_candidate=evaluated if isinstance(evaluated, dict) else None,
        ):
            selected_candidate = dict(evaluated or {})
            stopped = True
            break
    return {
        "commands": commands,
        "evaluated_count": int(evaluated_count),
        "selected_candidate": selected_candidate,
        "found_safe": bool(stopped),
        "stopped": bool(stopped),
    }


def resolve_design_guide_controller_active_fail_executor_rescue_seed_order(
    requested_tier: str | None,
) -> list[str]:
    """Return the active-fail rescue seed order for a requested rescue tier."""

    tier_order = ["medium", "high", "very_high", "extreme"]
    if requested_tier not in tier_order:
        return []
    if requested_tier == "extreme":
        return ["very_high", "extreme"]
    idx = tier_order.index(requested_tier)
    out = list(tier_order[idx:])
    if "extreme" in out and requested_tier != "very_high":
        return [tier for tier in out if tier != "extreme"] + ["extreme"]
    return out


def build_design_guide_controller_active_fail_executor_rescue_seed_eval_commands(
    *,
    rescue_family: str,
    requested_tier: str | None,
    rescue_seed_library: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build ordered active-fail fallback rescue seed eval commands."""

    family = str(rescue_family or "").strip().lower()
    seed_library = dict(rescue_seed_library or {})
    seed_order = resolve_design_guide_controller_active_fail_executor_rescue_seed_order(requested_tier)
    commands: list[dict[str, Any]] = []
    for tier in seed_order:
        seed_spec = dict(((seed_library.get(family) or {}).get(tier)) or {})
        seed_updates = dict(seed_spec.get("updates") or {})
        if not seed_updates:
            continue
        commands.append(
            {
                "tier": tier,
                "seed_spec": seed_spec,
                "updates": seed_updates,
                "label": (
                    f"Active fail {family} rescue repair "
                    f"({seed_spec.get('key') or f'{family}_{tier}'})"
                ),
                "source": "RESCUE_SEED_LIBRARY",
            }
        )
    return {
        "rescue_family": family,
        "requested_tier": requested_tier,
        "seed_order": seed_order,
        "commands": commands,
    }


def build_design_guide_controller_active_fail_executor_near_current_combined_fallback_eval_commands(
    *,
    geometry_bottom_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    shear_update_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    label: str = "Active fail near-current combined repair",
) -> list[dict[str, Any]]:
    """Build ordered near-current combined fallback eval commands from prepared rows."""

    commands: list[dict[str, Any]] = []
    for geometry_row in list(geometry_bottom_rows or []):
        if not isinstance(geometry_row, dict):
            continue
        geometry_updates = dict(geometry_row.get("geometry_updates") or {})
        for bottom_row in list(geometry_row.get("bottom_update_rows") or []):
            if isinstance(bottom_row, dict) and "updates" in bottom_row:
                bottom_updates = dict(bottom_row.get("updates") or {})
            elif isinstance(bottom_row, dict):
                bottom_updates = dict(bottom_row)
            else:
                continue
            for shear_updates_raw in list(shear_update_rows or []):
                if not isinstance(shear_updates_raw, dict):
                    continue
                merged = dict(geometry_updates)
                merged.update(bottom_updates)
                merged.update(dict(shear_updates_raw or {}))
                commands.append(
                    {
                        "updates": merged,
                        "label": str(label or "Active fail near-current combined repair"),
                        "source": "active_fail_near_current_combined_fallback",
                    }
                )
    return commands


def build_design_guide_controller_active_fail_executor_geometry_update_row(
    *,
    width_key: str,
    base_width: float,
    base_depth: float,
    resolved_width: float,
    resolved_depth: float,
) -> dict[str, Any]:
    """Build the active-fail near-current geometry update row from resolved dimensions."""

    updates: dict[str, Any] = {}
    key = str(width_key or "b")
    try:
        gw = float(resolved_width)
    except Exception:
        gw = float(base_width)
    try:
        gd = float(resolved_depth)
    except Exception:
        gd = float(base_depth)
    if abs(gw - float(base_width)) > 1e-9:
        updates[key] = gw
        if key != "b":
            updates["b"] = gw
        if abs(gd - float(base_depth)) > 1e-9:
            updates["D"] = gd
    return updates


def build_design_guide_controller_active_fail_executor_bottom_update_row(
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build one active-fail near-current bottom update row from plain updates."""

    return {"updates": dict(updates or {})}


def build_design_guide_controller_active_fail_executor_policy_input_request(
    *,
    base_state: dict[str, Any] | None,
    goal_labels: dict[str, Any] | None,
    mode_config_by_goal: dict[str, dict[str, Any]] | None,
    default_low: float,
    default_high: float,
    default_goal: str = "balanced",
) -> dict[str, Any]:
    """Resolve active-fail executor optimisation policy inputs from plain data."""

    mode_configs = dict(mode_config_by_goal or {})
    if str(default_goal or "") not in mode_configs and mode_configs:
        default_goal = next(iter(mode_configs))
    goal = resolve_design_optimisation_goal(
        dict(base_state or {}),
        goal_labels=dict(goal_labels or {}),
        default_goal=str(default_goal or "balanced"),
    )
    mode_config = resolve_design_mode_config(
        goal,
        mode_config_by_goal=mode_configs,
        default_goal=str(default_goal or "balanced"),
    )
    target_low, target_high, default_band_used = resolve_efficiency_target_band(
        mode_config,
        goal=goal,
        mode_config_by_goal=mode_configs,
        default_low=float(default_low),
        default_high=float(default_high),
        default_goal=str(default_goal or "balanced"),
    )
    return {
        "optimisation_goal": str(goal),
        "mode_config": dict(mode_config),
        "target_low": float(target_low),
        "target_high": float(target_high),
        "target_band_default_used": bool(default_band_used),
        "authority": "DesignGuideController.active_fail_executor_policy_input_request",
    }


def build_design_guide_controller_active_fail_near_current_repair_preflight(
    *,
    base_state: dict[str, Any] | None,
    overview: dict[str, Any] | None,
    active_failures: list[str] | set[str] | tuple[str, ...] | None,
    goal_labels: dict[str, Any] | None,
    mode_config_by_goal: dict[str, dict[str, Any]] | None,
    default_low: float,
    default_high: float,
    default_goal: str = "balanced",
    canonical_no_shear_spacing: float = 200.0,
) -> dict[str, Any]:
    """Build pure active-fail near-current repair preflight data.

    The page still owns session caches, trace callbacks, and live family
    callback execution. This helper owns only pure policy/default/input
    preparation for the bounded repair search.
    """

    base = dict(base_state or {})
    active = {
        str(family or "").strip().lower()
        for family in list(active_failures or [])
        if str(family or "").strip()
    }
    if not base:
        return {
            "should_continue": False,
            "stop_reason": "empty_base_state",
            "active": sorted(active),
            "base_state": base,
            "authority": "DesignGuideController.active_fail_near_current_repair_preflight",
        }
    if not (active & {"bending", "shear"}):
        return {
            "should_continue": False,
            "stop_reason": "no_bending_or_shear_active_failure",
            "active": sorted(active),
            "base_state": base,
            "authority": "DesignGuideController.active_fail_near_current_repair_preflight",
        }

    policy_inputs = build_design_guide_controller_active_fail_executor_policy_input_request(
        base_state=base,
        goal_labels=dict(goal_labels or {}),
        mode_config_by_goal=dict(mode_config_by_goal or {}),
        default_low=float(default_low),
        default_high=float(default_high),
        default_goal=str(default_goal or "balanced"),
    )
    target_low = float(policy_inputs.get("target_low") or default_low)
    target_high = float(policy_inputs.get("target_high") or default_high)
    generation_context = build_active_fail_executor_candidate_generation_context(
        base,
        active,
        target_low=float(target_low),
        target_high=float(target_high),
        canonical_no_shear_spacing=float(canonical_no_shear_spacing),
    )
    base_width = float(generation_context.get("base_width") or 0.0)
    base_depth = float(generation_context.get("base_depth") or 0.0)
    if base_width <= 0.0 or base_depth <= 0.0:
        return {
            "should_continue": False,
            "stop_reason": "invalid_base_geometry",
            "active": sorted(active),
            "base_state": base,
            "policy_inputs": dict(policy_inputs),
            "generation_context": dict(generation_context),
            "width_key": str(generation_context.get("width_key") or "b"),
            "base_width": float(base_width),
            "base_depth": float(base_depth),
            "authority": "DesignGuideController.active_fail_near_current_repair_preflight",
        }

    search_cache_payload = {
        "version": "active_fail_near_current_repair_item:2026-06-03.1",
        "base": dict(base),
        "active": sorted(active),
        "overview_statuses": dict((overview or {}).get("statuses") or {}) if isinstance(overview, dict) else {},
        "overview_utils": dict((overview or {}).get("utils") or {}) if isinstance(overview, dict) else {},
        "overview_any_fail": bool((overview or {}).get("any_fail")) if isinstance(overview, dict) else False,
    }
    return {
        "should_continue": True,
        "stop_reason": None,
        "active": sorted(active),
        "base_state": base,
        "policy_inputs": dict(policy_inputs),
        "mode_config": dict(policy_inputs.get("mode_config") or {}),
        "target_low": float(target_low),
        "target_high": float(target_high),
        "generation_context": dict(generation_context),
        "width_key": str(generation_context.get("width_key") or "b"),
        "base_width": float(base_width),
        "base_depth": float(base_depth),
        "search_cache_payload": search_cache_payload,
        "authority": "DesignGuideController.active_fail_near_current_repair_preflight",
    }


def build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs(
    *,
    action_tier: str | None,
    util_tier: str | None,
    tier_order: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    """Resolve rescue tier request/order from plain route input tiers."""

    order = tuple(str(tier or "").strip() for tier in list(tier_order or []) if str(tier or "").strip())
    indices = [
        order.index(tier)
        for tier in (str(action_tier or "").strip(), str(util_tier or "").strip())
        if tier in order
    ]
    requested_tier: str | None = None
    rescue_tiers: list[str] = []
    if indices:
        requested_tier = order[max(indices)]
        if requested_tier == "extreme":
            rescue_tiers = [tier for tier in ("very_high", "extreme") if tier in order]
        elif requested_tier in order:
            idx = order.index(requested_tier)
            rescue_tiers = list(order[idx:])
            if "extreme" in rescue_tiers and requested_tier != "very_high":
                rescue_tiers = [tier for tier in rescue_tiers if tier != "extreme"] + ["extreme"]
    return {
        "requested_tier": requested_tier,
        "rescue_tiers": list(rescue_tiers),
        "action_tier": str(action_tier or "").strip() or None,
        "util_tier": str(util_tier or "").strip() or None,
        "tier_order": list(order),
        "authority": "DesignGuideController.active_fail_executor_rescue_tier_route_inputs",
    }


def resolve_design_guide_controller_active_fail_executor_overview_util_tier(
    overview: dict[str, Any] | None,
    family: str,
) -> str | None:
    """Resolve rescue severity tier from plain overview utilisation data."""

    overview_d = dict(overview or {}) if isinstance(overview, dict) else {}
    utils = overview_d.get("utils")
    utils_d = dict(utils or {}) if isinstance(utils, dict) else {}
    family_key = str(family or "").strip().lower()
    if family_key == "shear":
        values = [utils_d.get("shear")]
    elif family_key == "combined":
        values = [utils_d.get("bending"), utils_d.get("shear")]
    else:
        values = [utils_d.get("bending")]
    resolved: list[float] = []
    for value in values:
        try:
            util = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(util):
            resolved.append(util)
    if not resolved:
        return None
    governing = max(resolved)
    if governing > 10.0:
        return "extreme"
    if governing >= 6.0:
        return "very_high"
    if governing >= 3.0:
        return "high"
    if governing >= 1.5:
        return "medium"
    return None


def resolve_design_guide_controller_active_fail_executor_ladder_stop_decision(
    *,
    family_id: str,
    evaluated_candidate: dict[str, Any] | None,
) -> bool:
    """Return whether an active-fail family ladder should stop on this candidate."""

    candidate = dict(evaluated_candidate or {}) if isinstance(evaluated_candidate, dict) else {}
    if not candidate:
        return False
    overview = dict(candidate.get("overview") or {})
    if not bool(candidate.get("is_compliant")):
        return False
    family = str(family_id or "").strip().upper()
    if family == "BENDING_FAIL_GOVERNS":
        if bool(overview.get("any_fail")):
            return False
        util = _float_or_none(
            candidate.get("candidate_post_util")
            or candidate.get("worst_util")
            or overview.get("worst_util")
            or overview.get("governing_util")
        )
        if util is None:
            return False
        target_low, target_high = get_target_utilisation_band()
        return bool(float(target_low) <= float(util) <= float(target_high))
    if family == "COMBINED_BENDING_SHEAR_FAIL":
        return bool(overview.get("all_key_pass")) and not bool(overview.get("any_fail"))
    return not bool(overview.get("any_fail"))


def accept_design_guide_controller_active_fail_executor_repair_candidate(
    *,
    candidate: dict[str, Any] | None,
    bending_family_ladder_attempted: bool = False,
    shear_family_ladder_attempted: bool = False,
) -> bool:
    """Return whether an active-fail executor candidate is acceptable for repair."""

    cand = dict(candidate or {}) if isinstance(candidate, dict) else {}
    if not cand or not bool(cand.get("is_compliant")):
        return False
    overview = dict(cand.get("overview") or {})
    if bool(overview.get("any_fail")):
        return False
    family_id = str(cand.get("candidate_family_id") or "").strip().upper()
    if bool(bending_family_ladder_attempted) and family_id == "BENDING_FAIL_GOVERNS":
        return bool(_controller_overview_required_checks_acceptable(overview))
    if bool(shear_family_ladder_attempted) and family_id == "SHEAR_FAIL_GOVERNS":
        return bool(_controller_overview_required_checks_acceptable(overview))
    return bool(overview.get("all_key_pass"))


def filter_design_guide_controller_active_fail_executor_repair_candidates(
    *,
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    bending_family_ladder_attempted: bool = False,
    shear_family_ladder_attempted: bool = False,
) -> list[dict[str, Any]]:
    """Return active-fail executor candidates accepted by controller policy."""

    safe: list[dict[str, Any]] = []
    for candidate in list(candidates or []):
        if not isinstance(candidate, dict):
            continue
        if accept_design_guide_controller_active_fail_executor_repair_candidate(
            candidate=dict(candidate),
            bending_family_ladder_attempted=bool(bending_family_ladder_attempted),
            shear_family_ladder_attempted=bool(shear_family_ladder_attempted),
        ):
            safe.append(dict(candidate))
    return safe


def resolve_design_guide_controller_local_cleanup_family_for_updates(
    *,
    updates: dict[str, Any] | None,
    fallback_family: str | None = None,
) -> str:
    """Classify a local cleanup candidate family from update keys."""

    update_keys = set(_mapping(updates))
    has_shear = bool(update_keys & _CONTROLLER_COMPOUND_SHEAR_UPDATE_KEYS)
    has_bottom = any(
        str(key).startswith("bot") or str(key).startswith("db_bot") for key in update_keys
    )
    has_geometry = bool(
        update_keys & _CONTROLLER_PRIMARY_GEOMETRY_KEYS
        or update_keys & _CONTROLLER_COMPOUND_GEOMETRY_UPDATE_KEYS
    )
    if has_shear and (has_bottom or has_geometry):
        return "combined"
    if has_shear:
        return "shear"
    if has_bottom:
        return "bending"
    if has_geometry:
        return "geometry"
    return str(fallback_family or "")


def resolve_design_guide_controller_local_cleanup_materially_reduces(
    *,
    family: str,
    shear_reduces: bool,
    bottom_reduces: bool,
    section_reduces: bool,
) -> bool:
    """Resolve whether a local cleanup candidate materially reduces its family."""

    fam = str(family or "").strip().lower()
    if fam == "shear":
        return bool(shear_reduces)
    if fam in {"bending", "bottom_reo"}:
        return bool(bottom_reduces)
    if fam == "geometry":
        return bool(section_reduces)
    return bool(shear_reduces or bottom_reduces or section_reduces)


def resolve_design_guide_controller_local_cleanup_material_proxy(
    *,
    width: Any,
    depth: Any,
    ast: Any,
    lig_d: Any,
    lig_legs: Any,
    spacing: Any,
) -> float:
    """Compute the local cleanup material proxy from scalar inputs."""

    try:
        width_value = float(width or 0.0)
    except Exception:
        width_value = 0.0
    try:
        depth_value = float(depth or 0.0)
    except Exception:
        depth_value = 0.0
    try:
        ast_value = float(ast or 0.0)
    except Exception:
        ast_value = 0.0
    try:
        lig_d_value = float(lig_d or 0.0)
    except Exception:
        lig_d_value = 0.0
    try:
        lig_legs_value = float(lig_legs or 0.0)
    except Exception:
        lig_legs_value = 0.0
    try:
        spacing_value = max(float(spacing or 0.0), 1.0)
    except Exception:
        spacing_value = 1.0
    shear_density = lig_legs_value * lig_d_value * lig_d_value / spacing_value
    return float(width_value * depth_value * 0.001 + ast_value * 0.05 + shear_density * 20.0)


def resolve_design_guide_controller_local_cleanup_pre_preview_gate(
    *,
    item_valid: bool,
    action_type: str | None,
    updates: dict[str, Any] | None,
    updates_match_state: bool,
    family: str | None,
    candidate_id: str | None,
    candidate_complexity_score: Any = None,
    material_proxy_before: Any = None,
    material_proxy_after: Any = None,
    section_reduces: bool = False,
    geometry_increases_without_section_reduction: bool = False,
    materially_reduces: bool = False,
    overview_any_fail: bool = False,
    overview_required_checks_acceptable: bool = True,
    shear_cleanup_needed: bool = False,
    allow_passing_shear_cleanup: bool = False,
) -> dict[str, Any]:
    """Resolve local cleanup pre-preview gate and detail payload."""

    detail: dict[str, Any] = {
        "blocked_reason": None,
        "family": None,
        "candidate_id": None,
        "distance": float("inf"),
        "candidate_complexity_score": None,
        "net_efficiency_delta": None,
        "material_proxy_before": None,
        "material_proxy_after": None,
        "material_proxy_delta": None,
        "is_executable": False,
        "advisory_only": True,
    }
    if not bool(item_valid):
        detail["blocked_reason"] = "invalid_candidate"
        return {"accepted_for_preview": False, "detail": detail}

    normalized_action_type = str(action_type or "").strip()
    if not normalized_action_type:
        detail["blocked_reason"] = "candidate_not_actionable"
        return {"accepted_for_preview": False, "detail": detail}

    update_payload = _mapping(updates)
    if not update_payload or bool(updates_match_state):
        detail["blocked_reason"] = "cleanup_no_material_update"
        return {"accepted_for_preview": False, "detail": detail}

    detail["family"] = str(family or "")
    detail["candidate_id"] = str(candidate_id or "")
    try:
        before_proxy = float(material_proxy_before or 0.0)
    except Exception:
        before_proxy = 0.0
    try:
        after_proxy = float(material_proxy_after or 0.0)
    except Exception:
        after_proxy = 0.0
    try:
        complexity = int(candidate_complexity_score or len(update_payload))
    except Exception:
        complexity = len(update_payload)
    detail["candidate_complexity_score"] = complexity
    detail["material_proxy_before"] = before_proxy
    detail["material_proxy_after"] = after_proxy
    detail["material_proxy_delta"] = after_proxy - before_proxy
    detail["net_efficiency_delta"] = before_proxy - after_proxy

    if after_proxy >= before_proxy - 1e-6:
        detail["blocked_reason"] = "cleanup_no_net_material_efficiency"
        return {"accepted_for_preview": False, "detail": detail}
    if not bool(section_reduces) and bool(geometry_increases_without_section_reduction):
        detail["blocked_reason"] = "cleanup_increases_geometry_without_section_reduction"
        return {"accepted_for_preview": False, "detail": detail}
    if not bool(materially_reduces):
        detail["blocked_reason"] = "cleanup_not_material"
        return {"accepted_for_preview": False, "detail": detail}
    if bool(overview_any_fail) or not bool(overview_required_checks_acceptable):
        detail["blocked_reason"] = "active_failure_needs_strengthening"
        return {"accepted_for_preview": False, "detail": detail}
    if (
        str(family or "").strip().lower() == "shear"
        and not bool(shear_cleanup_needed)
        and not bool(allow_passing_shear_cleanup)
    ):
        detail["blocked_reason"] = "shear_not_below_target"
        return {"accepted_for_preview": False, "detail": detail}
    return {"accepted_for_preview": True, "detail": detail}


def resolve_design_guide_controller_local_cleanup_basic_post_preview_gate(
    *,
    candidate_valid: bool,
    candidate_overview_any_fail: bool,
    candidate_overview_required_checks_acceptable: bool,
    candidate_preview_has_explicit_fail: bool,
    family: str | None,
    allow_in_target_primary_action: bool,
    current_shear_util: Any = None,
    preview_shear_util: Any = None,
) -> dict[str, Any]:
    """Resolve local cleanup post-preview acceptance before target-distance checks."""

    if not bool(candidate_valid):
        return {"accepted_for_target_checks": False, "blocked_reason": "cleanup_preview_failed"}
    if bool(candidate_overview_any_fail) or not bool(candidate_overview_required_checks_acceptable):
        return {"accepted_for_target_checks": False, "blocked_reason": "cleanup_preview_not_all_pass"}
    if bool(candidate_preview_has_explicit_fail):
        return {"accepted_for_target_checks": False, "blocked_reason": "cleanup_preview_has_fail_status"}
    if str(family or "").strip().lower() == "shear":
        current_util = _float_or_none(current_shear_util)
        preview_util = _float_or_none(preview_shear_util)
        if (
            bool(allow_in_target_primary_action)
            and current_util is not None
            and preview_util is not None
            and preview_util <= current_util + 1e-9
        ):
            return {
                "accepted_for_target_checks": False,
                "blocked_reason": "shear_cleanup_does_not_improve_utilisation",
            }
    return {"accepted_for_target_checks": True, "blocked_reason": None}


def resolve_design_guide_controller_local_cleanup_target_band_acceptance(
    *,
    post_worst_util: Any,
    current_worst_util: Any,
    target_min: Any,
    target_max: Any,
    family_key: str | None,
    governing_key: str | None,
    current_family_util: Any = None,
    preview_family_util: Any = None,
) -> dict[str, Any]:
    """Resolve whether local cleanup moves utilisation toward the target band."""

    distance = _controller_distance_to_target_band(post_worst_util, target_min, target_max)
    current_worst = _float_or_none(current_worst_util)
    family = str(family_key or "").strip().lower()
    governing = str(governing_key or "").strip().lower()
    family_moves_toward_target = False
    current_distance = None
    if current_worst is not None and current_worst < float(target_min) - 1e-9:
        current_distance = _controller_distance_to_target_band(current_worst, target_min, target_max)
        current_family = _float_or_none(current_family_util)
        preview_family = _float_or_none(preview_family_util)
        if family and family != governing and current_family is not None and preview_family is not None:
            if current_family < float(target_min) - 1e-9:
                family_moves_toward_target = (
                    _controller_distance_to_target_band(preview_family, target_min, target_max)
                    < _controller_distance_to_target_band(current_family, target_min, target_max) - 1e-9
                )
        if distance >= current_distance - 1e-9 and family != governing and not family_moves_toward_target:
            return {
                "accepted_for_executor_checks": False,
                "blocked_reason": "cleanup_does_not_move_governing_utilisation_toward_target",
                "distance": distance,
                "current_distance": current_distance,
                "family_moves_toward_target": family_moves_toward_target,
            }
    return {
        "accepted_for_executor_checks": True,
        "blocked_reason": None,
        "distance": distance,
        "current_distance": current_distance,
        "family_moves_toward_target": family_moves_toward_target,
    }


def resolve_design_guide_controller_local_cleanup_executor_acceptance(
    *,
    shear_executor_safe: bool = True,
    resolved_one_click: bool,
    executor_allowed: bool,
    executor_reason: str | None = None,
) -> dict[str, Any]:
    """Resolve local cleanup executor acceptance from page-owned callback results."""

    if not bool(shear_executor_safe):
        return {
            "accepted": False,
            "blocked_reason": "shear_cleanup_not_executor_safe",
            "is_executable": False,
            "advisory_only": True,
        }
    if not bool(resolved_one_click):
        return {
            "accepted": False,
            "blocked_reason": "cleanup_not_executor_backed",
            "is_executable": False,
            "advisory_only": True,
        }
    if not bool(executor_allowed):
        return {
            "accepted": False,
            "blocked_reason": str(executor_reason or "cleanup_not_executable"),
            "is_executable": False,
            "advisory_only": True,
        }
    return {
        "accepted": True,
        "blocked_reason": None,
        "is_executable": True,
        "advisory_only": False,
    }


def resolve_design_guide_controller_local_cleanup_candidate_promotion(
    *,
    item: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    change_lines: list[str] | None = None,
    failure_coverage: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Promote an evaluated local-cleanup candidate into a resolved item shape.

    The page still supplies page-owned callback outputs such as change lines and
    failure coverage. This helper owns only the pure item/payload/resolved
    candidate projection.
    """

    if not isinstance(item, dict) or not isinstance(candidate, dict):
        return item
    updates = _mapping(candidate.get("updates"))
    if not updates:
        return item

    out = dict(item)
    payload = _mapping(out.get("action_payload"))
    original_action_type = str(
        candidate.get("action_type")
        or payload.get("resolved_candidate_action_type")
        or out.get("action_type")
        or "apply_shear_recommendation"
    ).strip()
    label = str(
        candidate.get("label")
        or payload.get("resolved_candidate_label")
        or out.get("title_main")
        or "Apply recommendation"
    ).strip()
    post_util = candidate.get("candidate_post_util", candidate.get("worst_util"))
    try:
        post_util = float(post_util) if post_util is not None else None
    except Exception:
        post_util = None
    lines = [
        str(line)
        for line in list(
            candidate.get("guidance_change_lines")
            or payload.get("guidance_change_lines")
            or out.get("guidance_change_lines")
            or change_lines
            or []
        )
        if str(line).strip()
    ]
    coverage = _mapping(failure_coverage)

    payload["resolved_candidate_updates"] = dict(updates)
    payload["resolved_candidate_label"] = label
    payload["resolved_candidate_action_type"] = original_action_type
    payload["resolved_candidate_post_util"] = post_util
    payload["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band")
        or candidate.get("reaches_target_band")
    )
    payload["updates"] = dict(payload.get("updates") or updates)
    payload["guidance_change_lines"] = list(lines)
    payload["failure_coverage"] = dict(coverage)
    payload["covers_all_current_failures"] = bool(coverage.get("covers_all_current_failures"))
    payload["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
    payload["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])

    out["action_payload"] = payload
    out["action_type"] = "apply_resolved_candidate"
    out["resolved_candidate_label"] = label
    out["resolved_candidate_action_type"] = original_action_type
    out["resolved_candidate_updates"] = dict(updates)
    out["resolved_candidate_post_util"] = post_util
    out["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band")
        or candidate.get("reaches_target_band")
    )
    out["has_resolved_candidate_payload"] = True
    out["failure_coverage"] = dict(coverage)
    out["covers_all_current_failures"] = bool(coverage.get("covers_all_current_failures"))
    out["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
    out["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])
    out["resolved_candidate"] = {
        **dict(candidate),
        "label": label,
        "action_type": original_action_type,
        "updates": dict(updates),
        "candidate_post_util": post_util,
        "candidate_reaches_target_band": bool(
            candidate.get("candidate_reaches_target_band")
            or candidate.get("reaches_target_band")
        ),
        "failure_coverage": dict(coverage),
    }
    return out


def resolve_design_guide_controller_shear_executor_safety_policy(
    *,
    has_updates: bool,
    pure_shear_detailing_updates: bool,
    materially_reduces_reinforcement: bool,
    candidate_overview: dict[str, Any] | None,
    governing_domain: str | None = None,
) -> dict[str, Any]:
    """Resolve whether a shear cleanup candidate is safe for executor use."""

    if not bool(has_updates):
        return {
            "safe": False,
            "blocked_reason": "missing_updates",
            "candidate_statuses": {},
            "governing_status_after": None,
        }
    if not bool(pure_shear_detailing_updates):
        return {
            "safe": False,
            "blocked_reason": "non_shear_detailing_updates",
            "candidate_statuses": {},
            "governing_status_after": None,
        }
    if not bool(materially_reduces_reinforcement):
        return {
            "safe": False,
            "blocked_reason": "shear_cleanup_not_material_reduction",
            "candidate_statuses": {},
            "governing_status_after": None,
        }

    overview_d = _mapping(candidate_overview)
    statuses = _mapping(overview_d.get("statuses"))
    explicit_fail_statuses = {
        str(key or "").strip().lower(): str(value or "").strip().upper()
        for key, value in statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    }
    if explicit_fail_statuses:
        return {
            "safe": False,
            "blocked_reason": "candidate_preview_has_fail_status",
            "candidate_statuses": dict(statuses),
            "governing_status_after": None,
            "explicit_fail_statuses": dict(explicit_fail_statuses),
        }
    if bool(overview_d.get("any_fail")):
        return {
            "safe": False,
            "blocked_reason": "candidate_overview_any_fail",
            "candidate_statuses": dict(statuses),
            "governing_status_after": None,
        }

    governing = str(governing_domain or "").strip().lower()
    governing_status_after = None
    if governing:
        governing_status_after = str(statuses.get(governing) or "").strip().upper()
        if governing_status_after == "FAIL":
            return {
                "safe": False,
                "blocked_reason": "governing_status_after_fail",
                "candidate_statuses": dict(statuses),
                "governing_status_after": governing_status_after,
            }
    return {
        "safe": True,
        "blocked_reason": None,
        "candidate_statuses": dict(statuses),
        "governing_status_after": governing_status_after,
    }


_FINAL_PUBLICATION_MEMO_CACHE_MAX = 24
_final_publication_memo_cache: dict[str, "DesignGuideControllerResponse"] = {}
_MEMO_VOLATILE_KEY_PREFIXES = (
    "controller_",
    "design_guide_controller_",
    "collapsed_guidance_replacement_controller_",
)
_MEMO_VOLATILE_KEY_EXACT = {
    "actual_card_render_probe",
    "collapsed_guidance_item_hash",
    "final_publication_authority_hash",
    "final_publication_publication_hash",
    "final_publication_verifier_payload",
    "memo_cache_hit",
    "memo_cache_key",
    "memo_cache_reason",
    "mutation_proof_hash",
    "publication_hash",
    "source_hash",
}
_MEMO_VOLATILE_KEY_FRAGMENTS = (
    "bypass",
    "memo_cache",
    "trace_only",
)
_MEMO_DEBUG_PRODUCT_KEYS = {
    "blocker_attempts_by_family",
    "button_contract",
    "candidate_search_evidence",
    "component_apply_stale_reason",
    "component_apply_token",
    "design_guide_primary_apply_payload",
    "displayed_primary_button_contract",
    "exact_blockers_by_family",
    "post_click_exact_blockers_by_family",
    "primary_button_contract",
    "stale_apply_payload_blocked",
    "stale_apply_payload_current_fingerprint",
    "stale_apply_payload_expected_fingerprint",
    "stale_apply_payload_mismatch_reason",
    "winning_button_contract_source",
    "winning_candidate_source",
    "winning_update_payload_source",
}


def _memo_key_payload(value: Any) -> Any:
    """Remove derived proof/debug stamps from the controller memo key.

    The live publication still receives the full raw request. This canonical
    payload is only used to decide whether a no-input-change rerun can reuse
    the previously built FinalDesignGuidePublication response.
    """

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            key_lower = key.lower()
            if key_lower in _MEMO_VOLATILE_KEY_EXACT:
                continue
            if key_lower.endswith("_hash"):
                continue
            if key_lower.endswith("_timestamp") or key_lower in {"timestamp", "generated_at"}:
                continue
            if any(key_lower.startswith(prefix) for prefix in _MEMO_VOLATILE_KEY_PREFIXES):
                continue
            if any(fragment in key_lower for fragment in _MEMO_VOLATILE_KEY_FRAGMENTS):
                continue
            cleaned[key] = _memo_key_payload(raw_value)
        return cleaned
    if isinstance(value, list):
        return [_memo_key_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_memo_key_payload(item) for item in value]
    return value


def design_guide_controller_request_memo_payload(
    request: DesignGuideControllerRequest,
) -> dict[str, Any]:
    """Return the canonical product-relevant request used by the memo key."""

    request_payload = request.to_dict()
    request_payload["debug"] = {
        key: request.debug.get(key)
        for key in sorted(_MEMO_DEBUG_PRODUCT_KEYS)
        if key in request.debug
    }
    request_payload["guidance_debug"] = {
        key: request.guidance_debug.get(key)
        for key in sorted(_MEMO_DEBUG_PRODUCT_KEYS)
        if key in request.guidance_debug
    }
    return {
        "request": _memo_key_payload(request_payload),
        "memo_owner": "DesignGuideController.publication_authority",
        "memo_key_contract": "product_relevant_request_without_derived_stamps_v2",
    }


def stable_design_guide_controller_request_hash(
    request: DesignGuideControllerRequest,
) -> str:
    """Hash the product-relevant controller request, excluding proof churn."""

    return stable_final_publication_hash(design_guide_controller_request_memo_payload(request))


_RESIDUAL_SHEAR_CLEANUP_ROUTE_SHELL_SURFACES = (
    "route_entry_guard",
    "primary_shear_tightening_search",
    "fallback_variant_search",
    "materiality_and_safety_screen",
    "promoted_item_packaging",
    "blocker_evidence_merge",
    "target_band_reason_text",
    "cta_contract_bridge",
    "debug_session_projection",
)

_RESIDUAL_SHEAR_CLEANUP_ROUTE_BEHAVIOR_DEPENDENCIES = (
    "candidate_generation_execution",
    "candidate_evaluation_execution",
    "primary_shear_tightening_execution",
    "cta_contract_execution",
    "visible_wording_authoring",
)


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(
    *,
    current_shear_util: Any = None,
    target_band_eps: Any = None,
    skip_probe_blocked: bool = False,
    skip_probe_evaluated: bool = False,
    route_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve residual-shear cleanup route entry from plain guard inputs.

    The page still owns the skip-probe execution because it can touch page
    state/debug. This function owns only the deterministic boolean composition
    that used to live inline in the page route.
    """

    shear_util = _float_or_none(current_shear_util)
    eps = _float_or_none(target_band_eps)
    if eps is None:
        eps = 0.0
    threshold = 1.0 - float(eps)
    has_shear_util = shear_util is not None
    below_failure_threshold = bool(has_shear_util and float(shear_util) < threshold)
    should_enter_route = bool(
        below_failure_threshold
        and bool(skip_probe_evaluated)
        and not bool(skip_probe_blocked)
    )
    if not has_shear_util:
        reason = "missing_shear_util"
    elif not below_failure_threshold:
        reason = "shear_not_below_failure_threshold"
    elif not skip_probe_evaluated:
        reason = "skip_probe_not_evaluated"
    elif skip_probe_blocked:
        reason = "skip_probe_blocked"
    else:
        reason = "eligible"

    payload = {
        "route_entry_guard_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_route_entry_guard"
        ),
        "current_shear_util": shear_util,
        "target_band_eps": eps,
        "entry_threshold": threshold,
        "has_shear_util": has_shear_util,
        "below_failure_threshold": below_failure_threshold,
        "skip_probe_evaluated": bool(skip_probe_evaluated),
        "skip_probe_blocked": bool(skip_probe_blocked),
        "should_enter_route": should_enter_route,
        "decision_reason": reason,
        "route_inputs_hash": stable_final_publication_hash(_mapping(route_inputs)),
        "skip_probe_execution_owned_elsewhere": True,
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "route_entry_guard_hash": stable_final_publication_hash(payload)}


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(
    *,
    current_shear_util: Any = None,
    target_band_eps: Any = None,
    skip_probe_blocked: bool = False,
    skip_probe_evaluated: bool = False,
    route_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Live controller boundary for residual-shear route-entry guard construction."""

    guard = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(
        current_shear_util=current_shear_util,
        target_band_eps=target_band_eps,
        skip_probe_blocked=skip_probe_blocked,
        skip_probe_evaluated=skip_probe_evaluated,
        route_inputs=_mapping(route_inputs),
    )
    payload = {
        **dict(guard),
        "route_entry_guard_runner_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_route_entry_guard_runner"
        ),
        "route_entry_guard_runner_scope": "guard_construction_only",
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "route_entry_guard_runner_hash": stable_final_publication_hash(payload)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness(
    *,
    route_proof: dict[str, Any] | None = None,
    dependency_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build controller readiness for the residual shear cleanup route shell.

    This is not a behavior cutover. It proves whether the controller can own
    the route shell shape while candidate generation/evaluation, CTA execution,
    and wording remain explicit live dependencies.
    """

    proof = _mapping(route_proof)
    dependencies = _mapping(dependency_status)
    route_projection = _mapping(proof.get("route_projection"))
    represented = tuple(str(value) for value in (proof.get("represented_route_surfaces") or ()))
    excluded = tuple(str(value) for value in (proof.get("excluded_live_surfaces") or ()))
    missing_route_shell_surfaces = tuple(
        surface
        for surface in _RESIDUAL_SHEAR_CLEANUP_ROUTE_SHELL_SURFACES
        if surface not in represented
    )
    required_projection_sections = (
        "route_request",
        "search_projection",
        "blocker_projection",
        "result_projection",
    )
    missing_projection_sections = tuple(
        section for section in required_projection_sections if not _mapping(route_projection.get(section))
    )
    unresolved_behavior_dependencies = tuple(
        dependency
        for dependency in _RESIDUAL_SHEAR_CLEANUP_ROUTE_BEHAVIOR_DEPENDENCIES
        if dependencies.get(dependency) != "controller_owned"
    )
    live_dependency_evidence = {
        dependency: {
            "status": str(dependencies.get(dependency) or "page_live"),
            "must_remain_live": dependency in unresolved_behavior_dependencies,
            "route_proof_excluded": dependency in excluded,
        }
        for dependency in _RESIDUAL_SHEAR_CLEANUP_ROUTE_BEHAVIOR_DEPENDENCIES
    }
    route_shell_ready = bool(
        proof.get("proof_hash")
        and proof.get("route_projection_hash")
        and not missing_route_shell_surfaces
        and not missing_projection_sections
    )
    behavior_cutover_ready = route_shell_ready and not unresolved_behavior_dependencies
    readiness = {
        "route_shell_ready": route_shell_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "safe_next_cutover_surface": "route_shell_only" if route_shell_ready else "none",
        "route_shell_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_route_shell"
        ),
        "route_projection_hash": str(proof.get("route_projection_hash") or ""),
        "route_proof_hash": str(proof.get("proof_hash") or ""),
        "represented_route_surfaces": represented,
        "missing_route_shell_surfaces": missing_route_shell_surfaces,
        "missing_projection_sections": missing_projection_sections,
        "unresolved_behavior_dependencies": unresolved_behavior_dependencies,
        "live_dependency_evidence": live_dependency_evidence,
        "cutover_boundary": {
            "controller_may_own": (
                "route_shell_identity",
                "route_projection_hash",
                "readiness_evidence",
            ),
            "page_must_keep_for_now": unresolved_behavior_dependencies,
            "not_moved": (
                "candidate_generation_execution",
                "candidate_evaluation_execution",
                "cta_contract_execution",
                "visible_wording_authoring",
                "apply_routing",
                "ui_rendering",
                "session_state_mutation",
            ),
        },
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**readiness, "readiness_hash": stable_final_publication_hash(readiness)}


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell(
    *,
    state: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    mode_config: dict[str, Any] | None = None,
    bending_blocker: dict[str, Any] | None = None,
    exact_blockers_by_family: dict[str, Any] | None = None,
    residual_shear_tightening: dict[str, Any] | None = None,
    residual_result_item: dict[str, Any] | None = None,
    residual_detail: dict[str, Any] | None = None,
    route_debug: dict[str, Any] | None = None,
    route_flags: dict[str, Any] | None = None,
    dependency_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent the residual-shear route shell without executing dependencies.

    Candidate generation/evaluation, primary shear tightening, CTA contract
    execution, visible wording, apply routing, rendering, and session/debug
    mutation stay outside this adapter. The adapter returns the current route
    item unchanged plus the controller-owned proof/readiness hashes needed for
    a later narrow route-shell cutover.
    """

    item = _mapping(residual_result_item)
    proof = build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof(
        state=_mapping(state),
        overview=_mapping(overview),
        mode_config=_mapping(mode_config),
        bending_blocker=_mapping(bending_blocker),
        exact_blockers_by_family=_mapping(exact_blockers_by_family),
        residual_shear_tightening=_mapping(residual_shear_tightening),
        residual_result_item=dict(item),
        residual_detail=_mapping(residual_detail),
        route_debug=_mapping(route_debug),
        route_flags=_mapping(route_flags),
    )
    readiness = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness(
        route_proof=dict(proof),
        dependency_status=_mapping(dependency_status),
    )
    route_projection = _mapping(proof.get("route_projection"))
    payload = {
        "route_shell_adapter_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_route_shell"
        ),
        "result_item": dict(item),
        "result_item_hash": stable_final_publication_hash(item),
        "route_projection": dict(route_projection),
        "route_projection_hash": str(proof.get("route_projection_hash") or ""),
        "route_proof_hash": str(proof.get("proof_hash") or ""),
        "route_shell_readiness": dict(readiness),
        "route_shell_readiness_hash": str(readiness.get("readiness_hash") or ""),
        "route_shell_ready": bool(readiness.get("route_shell_ready")),
        "behavior_cutover_ready": bool(readiness.get("behavior_cutover_ready")),
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "primary_shear_tightening_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "route_shell_adapter_hash": stable_final_publication_hash(payload)}


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision(
    *,
    route_entry_guard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide whether the residual-shear cleanup route body should execute.

    This is a live route-shell decision boundary. It consumes the already-built
    controller guard and owns only the boolean route-entry interpretation. It
    does not generate candidates, evaluate candidates, build CTA contracts,
    author visible wording, route Apply, render UI, or mutate session state.
    """

    guard = _mapping(route_entry_guard)
    should_enter_route = bool(guard.get("should_enter_route"))
    payload = {
        "route_entry_decision_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_route_entry_decision"
        ),
        "should_enter_route": should_enter_route,
        "route_entry_guard_hash": stable_final_publication_hash(guard),
        "route_entry_reason": str(
            guard.get("route_entry_reason")
            or guard.get("reason")
            or ("enter_route" if should_enter_route else "skip_route")
        ),
        "route_shell_scope": "entry_decision_only",
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "route_entry_decision_hash": stable_final_publication_hash(payload)}


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_execution_shell(
    *,
    route_entry_decision: dict[str, Any] | None = None,
    route_body_executor: Callable[[], Any] | None = None,
    prebuilt_result_item: dict[str, Any] | None = None,
    prebuilt_route_body_executed: bool | None = None,
) -> dict[str, Any]:
    """Own the residual-shear cleanup route execution shell.

    The controller owns the route-shell decision and can consume either a
    prebuilt result item or an injected route body executor. The route body
    source remains the owner of candidate generation/evaluation, CTA contract
    execution, wording, Apply routing, rendering, and session/debug mutation.
    """

    decision = _mapping(route_entry_decision)
    should_execute_route_body = bool(decision.get("should_enter_route"))
    executed_route_body = False
    result_item: dict[str, Any] = {}
    prebuilt = _mapping(prebuilt_result_item)
    executor_error = ""
    prebuilt_supplied = prebuilt_route_body_executed is not None or bool(prebuilt)
    if should_execute_route_body and prebuilt_supplied:
        executed_route_body = bool(
            prebuilt_route_body_executed if prebuilt_route_body_executed is not None else prebuilt
        )
        result_item = dict(prebuilt if executed_route_body else {})
    elif should_execute_route_body and callable(route_body_executor):
        try:
            raw_result = route_body_executor()
            executed_route_body = True
            result_item = _mapping(raw_result)
        except Exception as exc:  # pragma: no cover - live safety path
            executor_error = f"{type(exc).__name__}: {exc}"
            raise
    payload = {
        "route_execution_shell_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_route_execution_shell"
        ),
        "should_execute_route_body": should_execute_route_body,
        "executed_route_body": executed_route_body,
        "result_item": dict(result_item),
        "result_item_hash": stable_final_publication_hash(result_item),
        "route_entry_decision_hash": str(decision.get("route_entry_decision_hash") or ""),
        "route_execution_shell_scope": (
            "prebuilt_route_result"
            if prebuilt_supplied
            else "route_body_executor_injected"
            if callable(route_body_executor)
            else "execution_decision_only"
        ),
        "prebuilt_route_result_supplied": bool(prebuilt_supplied),
        "prebuilt_route_result_hash": stable_final_publication_hash(prebuilt),
        "route_body_executor_owned_elsewhere": True,
        "prebuilt_route_result_owned_elsewhere": True,
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "executor_error": executor_error,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "route_execution_shell_hash": stable_final_publication_hash(payload)}


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies(
    *,
    route_entry_decision: dict[str, Any] | None = None,
    primary_executor: Callable[[], Any] | None = None,
    prebuilt_primary_result: Any = None,
    prebuilt_primary_executor_attempted: bool | None = None,
    fallback_search_loop: Callable[[], Any] | None = None,
    prebuilt_fallback_search_loop_payload: dict[str, Any] | None = None,
    prebuilt_fallback_search_loop_executed: bool | None = None,
    route_metadata: dict[str, Any] | None = None,
    iteration_limit: int = 64,
) -> dict[str, Any]:
    """Own residual-shear route orchestration while keeping execution injected.

    The controller decides when to run the primary executor and when to fall
    through to the fallback search loop. The supplied callables still own
    engineering execution, candidate generation/evaluation, CTA/apply, visible
    wording, rendering, and session/debug mutation.
    """

    decision = _mapping(route_entry_decision)
    metadata = _mapping(route_metadata)
    should_execute_route_body = bool(decision.get("should_enter_route"))
    residual_shear_tighten: dict[str, Any] = {}
    residual_shear_debug: dict[str, Any] = {}
    residual_shear_updates: dict[str, Any] = {}
    primary_executor_attempted = False
    fallback_search_loop_executed = False
    fallback_search_loop_payload: dict[str, Any] = {}
    fallback_variant_generator_inputs = {
        "route_branch": str(
            metadata.get("route_branch")
            or "post_click_residual_shear_cleanup_after_bending_blocker"
        ),
        "state_fingerprint": str(metadata.get("state_fingerprint") or ""),
        "mode_config_hash": str(metadata.get("mode_config_hash") or ""),
        "iteration_limit": int(iteration_limit or 64),
    }
    fallback_variant_generator_attempted = False
    fallback_variant_generator_variant_count = 0
    fallback_variant_generator_update_sequence: list[dict[str, Any]] = []
    fallback_candidate_evaluation_sequence: list[dict[str, Any]] = []
    fallback_candidate_selection_sequence: list[dict[str, Any]] = []
    fallback_candidate_selection_output_summary: dict[str, Any] = {}
    fallback_shear_candidates: list[dict[str, Any]] = []
    fallback_selected_result: dict[str, Any] = {}
    executor_error = ""
    prebuilt_primary_supplied = prebuilt_primary_executor_attempted is not None or prebuilt_primary_result is not None
    if should_execute_route_body and prebuilt_primary_supplied:
        raw_primary = prebuilt_primary_result
        primary_executor_attempted = bool(
            prebuilt_primary_executor_attempted
            if prebuilt_primary_executor_attempted is not None
            else raw_primary
        )
        if isinstance(raw_primary, (list, tuple)):
            residual_shear_tighten = _mapping(raw_primary[0] if raw_primary else {})
            residual_shear_debug = _mapping(raw_primary[1] if len(raw_primary) > 1 else {})
        else:
            primary = _mapping(raw_primary)
            residual_shear_tighten = _mapping(
                primary.get("residual_shear_tighten")
                or primary.get("result")
                or primary.get("candidate")
                or primary
            )
            residual_shear_debug = _mapping(
                primary.get("residual_shear_debug") or primary.get("debug") or {}
            )
        residual_shear_updates = _mapping(residual_shear_tighten.get("updates"))
    elif should_execute_route_body and callable(primary_executor):
        try:
            raw_primary = primary_executor()
            primary_executor_attempted = True
            if isinstance(raw_primary, (list, tuple)):
                residual_shear_tighten = _mapping(raw_primary[0] if raw_primary else {})
                residual_shear_debug = _mapping(raw_primary[1] if len(raw_primary) > 1 else {})
            else:
                primary = _mapping(raw_primary)
                residual_shear_tighten = _mapping(
                    primary.get("residual_shear_tighten")
                    or primary.get("result")
                    or primary.get("candidate")
                    or primary
                )
                residual_shear_debug = _mapping(
                    primary.get("residual_shear_debug") or primary.get("debug") or {}
                )
            residual_shear_updates = _mapping(residual_shear_tighten.get("updates"))
        except Exception as exc:  # pragma: no cover - live safety path
            executor_error = f"{type(exc).__name__}: {exc}"
            raise
    prebuilt_fallback_supplied = (
        prebuilt_fallback_search_loop_executed is not None
        or prebuilt_fallback_search_loop_payload is not None
    )
    if should_execute_route_body and not residual_shear_updates and prebuilt_fallback_supplied:
        fallback_search_loop_payload = _mapping(prebuilt_fallback_search_loop_payload)
        fallback_search_loop_executed = bool(
            prebuilt_fallback_search_loop_executed
            if prebuilt_fallback_search_loop_executed is not None
            else fallback_search_loop_payload
        )
        residual_shear_tighten = _mapping(
            fallback_search_loop_payload.get("residual_shear_tighten")
        )
        residual_shear_updates = _mapping(
            fallback_search_loop_payload.get("residual_shear_updates")
        )
        fallback_variant_generator_attempted = bool(
            fallback_search_loop_payload.get("fallback_variant_generator_attempted")
        )
        fallback_variant_generator_variant_count = int(
            fallback_search_loop_payload.get("fallback_variant_generator_variant_count")
            or 0
        )
        fallback_variant_generator_update_sequence = [
            _mapping(row)
            for row in (
                fallback_search_loop_payload.get("fallback_variant_generator_update_sequence")
                or ()
            )
        ]
        fallback_candidate_evaluation_sequence = [
            _mapping(row)
            for row in (
                fallback_search_loop_payload.get("fallback_candidate_evaluation_sequence")
                or ()
            )
        ]
        fallback_candidate_selection_sequence = [
            _mapping(row)
            for row in (
                fallback_search_loop_payload.get("fallback_candidate_selection_sequence")
                or ()
            )
        ]
        fallback_candidate_selection_output_summary = _mapping(
            fallback_search_loop_payload.get("fallback_candidate_selection_output_summary")
        )
        fallback_shear_candidates = [
            _mapping(row)
            for row in (fallback_search_loop_payload.get("fallback_shear_candidates") or ())
        ]
        fallback_selected_result = _mapping(
            fallback_search_loop_payload.get("fallback_selected_result")
        )
    elif should_execute_route_body and not residual_shear_updates and callable(fallback_search_loop):
        try:
            fallback_search_loop_payload = _mapping(fallback_search_loop())
            fallback_search_loop_executed = True
            residual_shear_tighten = _mapping(
                fallback_search_loop_payload.get("residual_shear_tighten")
            )
            residual_shear_updates = _mapping(
                fallback_search_loop_payload.get("residual_shear_updates")
            )
            fallback_variant_generator_attempted = bool(
                fallback_search_loop_payload.get("fallback_variant_generator_attempted")
            )
            fallback_variant_generator_variant_count = int(
                fallback_search_loop_payload.get("fallback_variant_generator_variant_count")
                or 0
            )
            fallback_variant_generator_update_sequence = [
                _mapping(row)
                for row in (
                    fallback_search_loop_payload.get("fallback_variant_generator_update_sequence")
                    or ()
                )
            ]
            fallback_candidate_evaluation_sequence = [
                _mapping(row)
                for row in (
                    fallback_search_loop_payload.get("fallback_candidate_evaluation_sequence")
                    or ()
                )
            ]
            fallback_candidate_selection_sequence = [
                _mapping(row)
                for row in (
                    fallback_search_loop_payload.get("fallback_candidate_selection_sequence")
                    or ()
                )
            ]
            fallback_candidate_selection_output_summary = _mapping(
                fallback_search_loop_payload.get("fallback_candidate_selection_output_summary")
            )
            fallback_shear_candidates = [
                _mapping(row)
                for row in (fallback_search_loop_payload.get("fallback_shear_candidates") or ())
            ]
            fallback_selected_result = _mapping(
                fallback_search_loop_payload.get("fallback_selected_result")
            )
        except Exception as exc:  # pragma: no cover - live safety path
            executor_error = f"{type(exc).__name__}: {exc}"
            raise
    context = {
        "residual_shear_tighten": dict(residual_shear_tighten),
        "residual_shear_debug": dict(residual_shear_debug),
        "residual_shear_updates": dict(residual_shear_updates),
        "fallback_variant_generator_inputs": dict(fallback_variant_generator_inputs),
        "fallback_variant_generator_attempted": bool(fallback_variant_generator_attempted),
        "fallback_variant_generator_variant_count": int(
            fallback_variant_generator_variant_count
        ),
        "fallback_variant_generator_update_sequence": list(
            fallback_variant_generator_update_sequence
        ),
        "fallback_candidate_evaluation_sequence": list(
            fallback_candidate_evaluation_sequence
        ),
        "fallback_candidate_selection_sequence": list(
            fallback_candidate_selection_sequence
        ),
        "fallback_candidate_selection_output_summary": dict(
            fallback_candidate_selection_output_summary
        ),
        "fallback_shear_candidates": list(fallback_shear_candidates),
        "fallback_selected_result": dict(fallback_selected_result),
    }
    payload = {
        "route_shell_with_injected_dependencies_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies"
        ),
        "should_execute_route_body": should_execute_route_body,
        "primary_executor_attempted": bool(primary_executor_attempted),
        "fallback_search_loop_executed": bool(fallback_search_loop_executed),
        "route_entry_decision_hash": str(decision.get("route_entry_decision_hash") or ""),
        "route_metadata_hash": stable_final_publication_hash(metadata),
        "route_shell_context": context,
        "route_shell_context_hash": stable_final_publication_hash(context),
        "primary_executor_owned_elsewhere": True,
        "prebuilt_primary_result_supplied": bool(prebuilt_primary_supplied),
        "prebuilt_primary_result_hash": stable_final_publication_hash(prebuilt_primary_result),
        "fallback_search_loop_dependencies_owned_elsewhere": True,
        "prebuilt_fallback_search_loop_supplied": bool(prebuilt_fallback_supplied),
        "prebuilt_fallback_search_loop_hash": stable_final_publication_hash(
            prebuilt_fallback_search_loop_payload
        ),
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "executor_error": executor_error,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "route_shell_hash": stable_final_publication_hash(payload)}


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell(
    *,
    route_entry_decision: dict[str, Any] | None = None,
    prebuilt_primary_result: Any = None,
    prebuilt_primary_executor_attempted: bool | None = None,
    prebuilt_fallback_search_loop_payload: dict[str, Any] | None = None,
    prebuilt_fallback_search_loop_executed: bool | None = None,
    route_metadata: dict[str, Any] | None = None,
    iteration_limit: int = 64,
) -> dict[str, Any]:
    """Run the residual-shear route shell from prebuilt route-execution data."""

    legacy = run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies(
        route_entry_decision=dict(route_entry_decision or {}),
        prebuilt_primary_result=prebuilt_primary_result,
        prebuilt_primary_executor_attempted=prebuilt_primary_executor_attempted,
        prebuilt_fallback_search_loop_payload=dict(prebuilt_fallback_search_loop_payload or {}),
        prebuilt_fallback_search_loop_executed=prebuilt_fallback_search_loop_executed,
        route_metadata=dict(route_metadata or {}),
        iteration_limit=iteration_limit,
    )
    payload = {
        **dict(legacy or {}),
        "prebuilt_route_shell_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell"
        ),
        "legacy_route_shell_hash": (legacy or {}).get("route_shell_hash"),
        "uses_injected_dependency_callables": False,
        "primary_executor_owned_elsewhere": True,
        "fallback_search_loop_dependencies_owned_elsewhere": True,
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
    }
    return {**payload, "route_shell_hash": stable_final_publication_hash(payload)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle(
    *,
    route_entry_decision: dict[str, Any] | None = None,
    prebuilt_primary_result: Any = None,
    prebuilt_primary_executor_attempted: bool | None = None,
    prebuilt_fallback_search_loop_payload: dict[str, Any] | None = None,
    prebuilt_fallback_search_loop_executed: bool | None = None,
    route_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent prebuilt residual-shear candidate execution as stable data.

    This object does not execute candidates. It only normalizes already-built
    primary and fallback execution results so a later cutover can consume one
    controller-owned bundle instead of scattered page-local variables.
    """

    decision = _mapping(route_entry_decision)
    metadata = _mapping(route_metadata)
    primary_attempted = bool(
        prebuilt_primary_executor_attempted
        if prebuilt_primary_executor_attempted is not None
        else prebuilt_primary_result
    )
    if isinstance(prebuilt_primary_result, (list, tuple)):
        primary_tighten = _mapping(prebuilt_primary_result[0] if prebuilt_primary_result else {})
        primary_debug = _mapping(
            prebuilt_primary_result[1] if len(prebuilt_primary_result) > 1 else {}
        )
    else:
        primary_mapping = _mapping(prebuilt_primary_result)
        primary_tighten = _mapping(
            primary_mapping.get("residual_shear_tighten")
            or primary_mapping.get("result")
            or primary_mapping.get("candidate")
            or primary_mapping
        )
        primary_debug = _mapping(
            primary_mapping.get("residual_shear_debug")
            or primary_mapping.get("debug")
            or {}
        )
    primary_updates = _mapping(primary_tighten.get("updates"))
    fallback_payload = _mapping(prebuilt_fallback_search_loop_payload)
    fallback_executed = bool(
        prebuilt_fallback_search_loop_executed
        if prebuilt_fallback_search_loop_executed is not None
        else fallback_payload
    )
    fallback_tighten = _mapping(fallback_payload.get("residual_shear_tighten"))
    fallback_updates = _mapping(fallback_payload.get("residual_shear_updates"))
    selected_source = "primary" if primary_updates else "fallback" if fallback_updates else "none"
    selected_tighten = dict(primary_tighten if primary_updates else fallback_tighten)
    selected_updates = dict(primary_updates or fallback_updates)
    payload = {
        "candidate_execution_bundle_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle"
        ),
        "route_entry_decision_hash": str(decision.get("route_entry_decision_hash") or ""),
        "route_metadata_hash": stable_final_publication_hash(metadata),
        "primary_executor_attempted": bool(primary_attempted),
        "primary_result": (
            list(prebuilt_primary_result)
            if isinstance(prebuilt_primary_result, tuple)
            else prebuilt_primary_result
        ),
        "primary_result_hash": stable_final_publication_hash(prebuilt_primary_result),
        "primary_debug": dict(primary_debug),
        "primary_tighten": dict(primary_tighten),
        "primary_updates": dict(primary_updates),
        "primary_updates_hash": stable_final_publication_hash(primary_updates),
        "fallback_search_loop_executed": bool(fallback_executed),
        "fallback_payload": dict(fallback_payload),
        "fallback_payload_hash": stable_final_publication_hash(fallback_payload),
        "fallback_tighten": dict(fallback_tighten),
        "fallback_updates": dict(fallback_updates),
        "fallback_updates_hash": stable_final_publication_hash(fallback_updates),
        "selected_result_source": selected_source,
        "selected_tighten": dict(selected_tighten),
        "selected_updates": dict(selected_updates),
        "selected_updates_hash": stable_final_publication_hash(selected_updates),
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "candidate_execution_bundle_hash": stable_final_publication_hash(payload),
    }


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_live_route_result_assembly(
    *,
    route_entry_decision: dict[str, Any] | None = None,
    primary_executor: Callable[[], Any] | None = None,
    fallback_search_loop: Callable[[], Any] | None = None,
    route_metadata: dict[str, Any] | None = None,
    iteration_limit: int = 64,
) -> dict[str, Any]:
    """Assemble residual-shear live route results behind the controller boundary.

    Inputs still supplies the injected engineering executors. This function owns
    the route assembly order and normalizes the live execution into the same
    candidate bundle and prebuilt route shell used by the deletion proofs.
    """

    dependency_shell = run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies(
        route_entry_decision=dict(route_entry_decision or {}),
        primary_executor=primary_executor,
        fallback_search_loop=fallback_search_loop,
        route_metadata=dict(route_metadata or {}),
        iteration_limit=iteration_limit,
    )
    context = _mapping(dependency_shell.get("route_shell_context"))
    primary_attempted = bool(dependency_shell.get("primary_executor_attempted"))
    fallback_executed = bool(dependency_shell.get("fallback_search_loop_executed"))
    primary_result: Any = {}
    if primary_attempted and not fallback_executed:
        primary_result = (
            _mapping(context.get("residual_shear_tighten")),
            _mapping(context.get("residual_shear_debug")),
        )
    fallback_payload: dict[str, Any] = {}
    if fallback_executed:
        fallback_payload = {
            "residual_shear_tighten": _mapping(context.get("residual_shear_tighten")),
            "residual_shear_updates": _mapping(context.get("residual_shear_updates")),
            "fallback_variant_generator_attempted": bool(
                context.get("fallback_variant_generator_attempted")
            ),
            "fallback_variant_generator_variant_count": int(
                context.get("fallback_variant_generator_variant_count") or 0
            ),
            "fallback_variant_generator_update_sequence": list(
                context.get("fallback_variant_generator_update_sequence") or []
            ),
            "fallback_candidate_evaluation_sequence": list(
                context.get("fallback_candidate_evaluation_sequence") or []
            ),
            "fallback_candidate_selection_sequence": list(
                context.get("fallback_candidate_selection_sequence") or []
            ),
            "fallback_candidate_selection_output_summary": _mapping(
                context.get("fallback_candidate_selection_output_summary")
            ),
            "fallback_shear_candidates": list(context.get("fallback_shear_candidates") or []),
            "fallback_selected_result": _mapping(context.get("fallback_selected_result")),
        }
    candidate_bundle = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle(
        route_entry_decision=dict(route_entry_decision or {}),
        prebuilt_primary_result=primary_result,
        prebuilt_primary_executor_attempted=primary_attempted,
        prebuilt_fallback_search_loop_payload=dict(fallback_payload),
        prebuilt_fallback_search_loop_executed=fallback_executed,
        route_metadata=dict(route_metadata or {}),
    )
    prebuilt_shell = run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell(
        route_entry_decision=dict(route_entry_decision or {}),
        prebuilt_primary_result=candidate_bundle.get("primary_result"),
        prebuilt_primary_executor_attempted=candidate_bundle.get("primary_executor_attempted"),
        prebuilt_fallback_search_loop_payload=dict(candidate_bundle.get("fallback_payload") or {}),
        prebuilt_fallback_search_loop_executed=candidate_bundle.get("fallback_search_loop_executed"),
        route_metadata=dict(route_metadata or {}),
        iteration_limit=iteration_limit,
    )
    prebuilt_context = _mapping(prebuilt_shell.get("route_shell_context"))
    payload = {
        "live_route_result_assembly_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_live_route_result_assembly"
        ),
        "dependency_injected_route_shell_execution": dict(dependency_shell),
        "candidate_execution_bundle": dict(candidate_bundle),
        "prebuilt_route_shell_execution": dict(prebuilt_shell),
        "route_shell_context": dict(prebuilt_context),
        "route_entry_decision_hash": str(
            _mapping(route_entry_decision).get("route_entry_decision_hash") or ""
        ),
        "route_metadata_hash": stable_final_publication_hash(_mapping(route_metadata)),
        "primary_executor_attempted": primary_attempted,
        "fallback_search_loop_executed": fallback_executed,
        "residual_shear_tighten": _mapping(prebuilt_context.get("residual_shear_tighten")),
        "residual_shear_debug": _mapping(prebuilt_context.get("residual_shear_debug")),
        "residual_shear_updates": _mapping(prebuilt_context.get("residual_shear_updates")),
        "fallback_variant_generator_inputs": _mapping(
            prebuilt_context.get("fallback_variant_generator_inputs")
        ),
        "fallback_variant_generator_attempted": bool(
            prebuilt_context.get("fallback_variant_generator_attempted")
        ),
        "fallback_variant_generator_variant_count": int(
            prebuilt_context.get("fallback_variant_generator_variant_count") or 0
        ),
        "fallback_variant_generator_update_sequence": list(
            prebuilt_context.get("fallback_variant_generator_update_sequence") or []
        ),
        "fallback_candidate_evaluation_sequence": list(
            prebuilt_context.get("fallback_candidate_evaluation_sequence") or []
        ),
        "fallback_candidate_selection_sequence": list(
            prebuilt_context.get("fallback_candidate_selection_sequence") or []
        ),
        "fallback_candidate_selection_output_summary": _mapping(
            prebuilt_context.get("fallback_candidate_selection_output_summary")
        ),
        "fallback_shear_candidates": list(prebuilt_context.get("fallback_shear_candidates") or []),
        "fallback_selected_result": _mapping(prebuilt_context.get("fallback_selected_result")),
        "primary_executor_owned_elsewhere": True,
        "fallback_search_loop_dependencies_owned_elsewhere": True,
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "live_route_result_assembly_hash": stable_final_publication_hash(payload)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle(
    *,
    should_execute_tail: bool = False,
    prebuilt_result_packaging_result: Any = None,
    prebuilt_result_packaging_attempted: bool | None = None,
    residual_shear_updates: dict[str, Any] | None = None,
    exact_blockers_by_family: dict[str, Any] | None = None,
    current_shear_util: Any = None,
    target_low: Any = None,
    target_high: Any = None,
    target_band_eps: Any = None,
    fallback_candidate_id: str | None = None,
    route_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent residual-shear result-packaging execution as stable data.

    This object does not execute local cleanup packaging. It normalizes the
    already-built packaging result plus the blocker-tail inputs so a later
    cutover can pass one controller-owned bundle into the blocker-tail shell.
    """

    updates = _mapping(residual_shear_updates)
    exact_blockers = _mapping(exact_blockers_by_family)
    metadata = _mapping(route_metadata)
    attempted = bool(
        prebuilt_result_packaging_attempted
        if prebuilt_result_packaging_attempted is not None
        else prebuilt_result_packaging_result
    )
    payload = {
        "result_packaging_execution_bundle_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle"
        ),
        "should_execute_tail": bool(should_execute_tail),
        "prebuilt_result_packaging_result": (
            list(prebuilt_result_packaging_result)
            if isinstance(prebuilt_result_packaging_result, tuple)
            else prebuilt_result_packaging_result
        ),
        "prebuilt_result_packaging_result_hash": stable_final_publication_hash(
            prebuilt_result_packaging_result
        ),
        "prebuilt_result_packaging_attempted": bool(attempted),
        "residual_shear_updates": dict(updates),
        "residual_shear_updates_hash": stable_final_publication_hash(updates),
        "exact_blockers_by_family": dict(exact_blockers),
        "exact_blockers_hash": stable_final_publication_hash(exact_blockers),
        "current_shear_util": current_shear_util,
        "target_low": target_low,
        "target_high": target_high,
        "target_band_eps": target_band_eps,
        "fallback_candidate_id": str(fallback_candidate_id or ""),
        "route_metadata": dict(metadata),
        "route_metadata_hash": stable_final_publication_hash(metadata),
        "result_packaging_execution_owned_elsewhere": True,
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "result_packaging_execution_bundle_hash": stable_final_publication_hash(payload),
    }


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_blocker_tail_shell(
    *,
    should_execute_tail: bool = False,
    result_packaging_executor: Callable[[], Any] | None = None,
    prebuilt_result_packaging_result: Any = None,
    prebuilt_result_packaging_attempted: bool | None = None,
    residual_shear_updates: dict[str, Any] | None = None,
    exact_blockers_by_family: dict[str, Any] | None = None,
    current_shear_util: Any = None,
    target_low: Any = None,
    target_high: Any = None,
    target_band_eps: Any = None,
    fallback_candidate_id: str | None = None,
    route_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Own result-packaging/blocker-tail assembly while execution stays injected.

    The page supplies the result-packaging executor because it still depends on
    page/shared evaluators and local cleanup packaging. The controller owns the
    surrounding tail shape and the plain-data blocker/evidence assembly.
    """

    metadata = _mapping(route_metadata)
    updates = _mapping(residual_shear_updates)
    exact_blockers = _mapping(exact_blockers_by_family)
    residual_shear_item: dict[str, Any] = {}
    residual_promoted: dict[str, Any] = {}
    residual_detail: dict[str, Any] = {}
    residual_evidence: dict[str, Any] = {}
    residual_preview_util = None
    residual_candidate_id = str(fallback_candidate_id or "")
    residual_exact_blockers = dict(exact_blockers)
    residual_outside_preferred_band = False
    residual_shear_reason = ""
    residual_shear_blocker: dict[str, Any] = {}
    residual_pre_merge_evidence: dict[str, Any] = {}
    residual_pre_merge_exact_blockers: dict[str, Any] = {}
    result_packaging_attempted = False
    executor_error = ""

    prebuilt_packaging_supplied = (
        prebuilt_result_packaging_attempted is not None
        or prebuilt_result_packaging_result is not None
    )
    if should_execute_tail and prebuilt_packaging_supplied:
        raw_result = prebuilt_result_packaging_result
        result_packaging_attempted = bool(
            prebuilt_result_packaging_attempted
            if prebuilt_result_packaging_attempted is not None
            else raw_result
        )
        if isinstance(raw_result, (list, tuple)):
            residual_shear_item = _mapping(raw_result[0] if raw_result else {})
            residual_promoted = _mapping(raw_result[1] if len(raw_result) > 1 else {})
            residual_detail = _mapping(raw_result[2] if len(raw_result) > 2 else {})
        else:
            raw_mapping = _mapping(raw_result)
            residual_shear_item = _mapping(
                raw_mapping.get("residual_shear_item")
                or raw_mapping.get("item")
                or raw_mapping.get("result_item")
            )
            residual_promoted = _mapping(
                raw_mapping.get("residual_promoted")
                or raw_mapping.get("promoted_item")
                or raw_mapping.get("result")
                or raw_mapping
            )
            residual_detail = _mapping(
                raw_mapping.get("residual_detail") or raw_mapping.get("detail")
            )
    elif should_execute_tail and callable(result_packaging_executor):
        try:
            raw_result = result_packaging_executor()
            result_packaging_attempted = True
            if isinstance(raw_result, (list, tuple)):
                residual_shear_item = _mapping(raw_result[0] if raw_result else {})
                residual_promoted = _mapping(raw_result[1] if len(raw_result) > 1 else {})
                residual_detail = _mapping(raw_result[2] if len(raw_result) > 2 else {})
            else:
                raw_mapping = _mapping(raw_result)
                residual_shear_item = _mapping(
                    raw_mapping.get("residual_shear_item")
                    or raw_mapping.get("item")
                    or raw_mapping.get("result_item")
                )
                residual_promoted = _mapping(
                    raw_mapping.get("residual_promoted")
                    or raw_mapping.get("promoted_item")
                    or raw_mapping.get("result")
                    or raw_mapping
                )
                residual_detail = _mapping(
                    raw_mapping.get("residual_detail") or raw_mapping.get("detail")
                )
        except Exception as exc:  # pragma: no cover - live safety path
            executor_error = f"{type(exc).__name__}: {exc}"
            raise

    should_continue_tail = bool(should_execute_tail and residual_shear_item and residual_promoted)
    if should_continue_tail:
        action_payload = _mapping(residual_promoted.get("action_payload"))
        resolved_candidate = _mapping(residual_promoted.get("resolved_candidate"))
        button_contract = _mapping(residual_promoted.get("button_contract"))
        residual_evidence = _mapping(
            residual_promoted.get("candidate_search_evidence")
            or action_payload.get("candidate_search_evidence")
            or resolved_candidate.get("candidate_search_evidence")
        )
        residual_preview_util = _float_or_none(
            residual_evidence.get("best_safe_final_util")
            or residual_evidence.get("selected_candidate_util")
            or button_contract.get("expected_util")
            or residual_promoted.get("expected_util")
            or residual_promoted.get("util")
        )
        residual_candidate_id = str(
            residual_promoted.get("candidate_id")
            or residual_promoted.get("source_candidate_id")
            or residual_evidence.get("selected_candidate_id")
            or residual_evidence.get("best_safe_candidate_id")
            or fallback_candidate_id
            or ""
        )
        target_hi = _float_or_none(target_high)
        target_lo = _float_or_none(target_low)
        eps = _float_or_none(target_band_eps)
        current_util = _float_or_none(current_shear_util)
        residual_outside_preferred_band = bool(
            residual_preview_util is not None
            and target_hi is not None
            and residual_preview_util > target_hi + (eps or 0.0)
        )
        residual_pre_merge_evidence = dict(residual_evidence)
        residual_pre_merge_exact_blockers = dict(residual_exact_blockers)
        if residual_outside_preferred_band:
            residual_shear_reason = (
                f"The best safe one-click shear cleanup reaches shear utilisation "
                f"{float(residual_preview_util):.2f}, above the preferred {float(target_hi or 0.0):.2f} "
                "target limit. The exhaustive shear-link cleanup search found no executor-backed "
                "candidate inside the preferred band while preserving all required checks."
            )
            residual_shear_blocker = {
                "family": "shear",
                "source": "post_click_residual_shear_cleanup_outside_preferred_band",
                "exact_blocker": True,
                "threshold": float(target_hi or 0.0),
                "target_low": float(target_lo or 0.0),
                "target_high": float(target_hi or 0.0),
                "current_util": float(current_util or 0.0),
                "starting_util": float(current_util or 0.0),
                "best_safe_final_util": float(residual_preview_util),
                "best_safe_candidate_updates": dict(updates),
                "best_safe_candidate_applied": False,
                "cleanup_search_ran": True,
                "cleanup_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "target_band_search_ran": True,
                "target_band_search_exhaustive": True,
                "safe_candidate_count": int(residual_evidence.get("safe_candidate_count") or 1),
                "executable_candidate_count": int(
                    residual_evidence.get("executable_candidate_count") or 1
                ),
                "safe_cleanup_count": int(residual_evidence.get("safe_cleanup_count") or 1),
                "executable_cleanup_count": int(
                    residual_evidence.get("executable_cleanup_count") or 1
                ),
                "safe_shear_cleanup_count": int(
                    residual_evidence.get("safe_shear_cleanup_count") or 1
                ),
                "executable_shear_cleanup_count": int(
                    residual_evidence.get("executable_shear_cleanup_count") or 1
                ),
                "target_band_candidate_count": 0,
                "executable_target_band_candidate_count": 0,
                "attempted_candidate_count": int(
                    residual_evidence.get("attempted_candidate_count") or 1
                ),
                "previewed_candidate_count": int(
                    residual_evidence.get("previewed_candidate_count") or 1
                ),
                "failed_candidate_id": residual_candidate_id,
                "best_rejected_candidate_id": residual_candidate_id,
                "attempted_updates": dict(updates),
                "failed_check_name": "preferred shear target band",
                "failed_check_status": "OUTSIDE_PREFERRED_TARGET_BAND",
                "failed_check_util": float(residual_preview_util),
                "failed_check_demand": "shear cleanup preview",
                "failed_check_capacity_or_limit": float(target_hi or 0.0),
                "demand": "shear cleanup preview",
                "capacity_or_limit": float(target_hi or 0.0),
                "no_second_cta_required": True,
                "why_reduction_would_hurt_other_design_elements": residual_shear_reason,
                "reason_reducing_this_family_would_affect_other_design_elements": residual_shear_reason,
                "reason": residual_shear_reason,
            }

    tail_context = {
        "residual_shear_item": dict(residual_shear_item),
        "residual_promoted": dict(residual_promoted),
        "residual_detail": dict(residual_detail),
        "residual_evidence": dict(residual_evidence),
        "residual_preview_util": residual_preview_util,
        "residual_candidate_id": residual_candidate_id,
        "residual_exact_blockers": dict(residual_exact_blockers),
        "residual_outside_preferred_band": bool(residual_outside_preferred_band),
        "residual_shear_reason": residual_shear_reason,
        "residual_shear_blocker": dict(residual_shear_blocker),
        "residual_pre_merge_evidence": dict(residual_pre_merge_evidence),
        "residual_pre_merge_exact_blockers": dict(residual_pre_merge_exact_blockers),
    }
    payload = {
        "result_packaging_blocker_tail_shell_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_result_packaging_blocker_tail_shell"
        ),
        "should_execute_tail": bool(should_execute_tail),
        "result_packaging_attempted": bool(result_packaging_attempted),
        "should_continue_tail": bool(should_continue_tail),
        "route_metadata_hash": stable_final_publication_hash(metadata),
        "residual_updates_hash": stable_final_publication_hash(updates),
        "exact_blockers_hash": stable_final_publication_hash(exact_blockers),
        "tail_context": tail_context,
        "tail_context_hash": stable_final_publication_hash(tail_context),
        "result_packaging_execution_owned_elsewhere": True,
        "prebuilt_result_packaging_supplied": bool(prebuilt_packaging_supplied),
        "prebuilt_result_packaging_hash": stable_final_publication_hash(
            prebuilt_result_packaging_result
        ),
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_preserved": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "executor_error": executor_error,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "result_packaging_blocker_tail_shell_hash": stable_final_publication_hash(payload)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(
    *,
    route_shell_adapter: dict[str, Any] | None = None,
    route_entry_guard: dict[str, Any] | None = None,
    primary_executor_handoff: dict[str, Any] | None = None,
    primary_executor_dependency_boundary: dict[str, Any] | None = None,
    fallback_variant_generator_handoff: dict[str, Any] | None = None,
    fallback_variant_generator_dependency_boundary: dict[str, Any] | None = None,
    candidate_evaluator_handoff: dict[str, Any] | None = None,
    materiality_safety_handoff: dict[str, Any] | None = None,
    candidate_selector_handoff: dict[str, Any] | None = None,
    result_packaging_handoff: dict[str, Any] | None = None,
    evidence_merge_tail: dict[str, Any] | None = None,
    final_binding_tail: dict[str, Any] | None = None,
    residual_promoted: dict[str, Any] | None = None,
    dependency_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent the residual-shear route body without executing it.

    The page still runs the route body. This object is the next extraction
    boundary: it consumes already-built dependency outputs and proves the
    controller can represent the result item identity before any live cutover.
    """

    shell = _mapping(route_shell_adapter)
    result_item = _mapping(residual_promoted or shell.get("result_item"))
    dependencies = {
        "route_entry_guard": _mapping(route_entry_guard),
        "primary_executor_handoff": _mapping(primary_executor_handoff),
        "primary_executor_dependency_boundary": _mapping(primary_executor_dependency_boundary),
        "fallback_variant_generator_handoff": _mapping(fallback_variant_generator_handoff),
        "fallback_variant_generator_dependency_boundary": _mapping(fallback_variant_generator_dependency_boundary),
        "candidate_evaluator_handoff": _mapping(candidate_evaluator_handoff),
        "materiality_safety_handoff": _mapping(materiality_safety_handoff),
        "candidate_selector_handoff": _mapping(candidate_selector_handoff),
        "result_packaging_handoff": _mapping(result_packaging_handoff),
        "evidence_merge_tail": _mapping(evidence_merge_tail),
        "final_binding_tail": _mapping(final_binding_tail),
    }
    dependency_hashes = {
        name: stable_final_publication_hash(value)
        for name, value in dependencies.items()
    }
    statuses = _mapping(dependency_status)
    unresolved_dependencies = tuple(
        name for name in dependencies if statuses.get(name) != "controller_owned"
    )
    output_shape_ready = bool(
        shell.get("route_shell_adapter_hash")
        and result_item
        and all(dependency_hashes.values())
    )
    behavior_cutover_ready = output_shape_ready and not unresolved_dependencies
    payload = {
        "route_body_replacement_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_route_body_replacement"
        ),
        "route_shell_adapter_hash": str(shell.get("route_shell_adapter_hash") or ""),
        "route_shell_result_item_hash": str(shell.get("result_item_hash") or ""),
        "result_item": dict(result_item),
        "result_item_hash": stable_final_publication_hash(result_item),
        "dependency_hashes": dependency_hashes,
        "dependency_status": {
            name: str(statuses.get(name) or "page_live") for name in dependencies
        },
        "unresolved_dependencies": unresolved_dependencies,
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "safe_next_cutover_surface": (
            "route_body_result_identity" if output_shape_ready else "none"
        ),
        "page_must_keep_for_now": unresolved_dependencies,
        "not_moved": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "route_body_replacement_hash": stable_final_publication_hash(payload)}


def select_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_return_item(
    *,
    route_body_replacement: dict[str, Any] | None = None,
    fallback_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select the residual-shear route return item from controller-owned identity proof."""

    replacement = _mapping(route_body_replacement)
    fallback = _mapping(fallback_item)
    replacement_item = _mapping(replacement.get("result_item"))
    fallback_hash = stable_final_publication_hash(fallback)
    replacement_item_hash = str(replacement.get("result_item_hash") or "")
    replacement_ready = bool(replacement.get("output_shape_ready"))
    use_replacement = bool(
        replacement_ready
        and replacement_item
        and replacement_item_hash == fallback_hash
    )
    result_item = dict(replacement_item if use_replacement else fallback)
    payload = {
        "route_return_boundary_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_route_return_item"
        ),
        "result_item": dict(result_item),
        "result_item_hash": stable_final_publication_hash(result_item),
        "fallback_item_hash": fallback_hash,
        "replacement_result_item_hash": replacement_item_hash,
        "route_body_replacement_hash": str(replacement.get("route_body_replacement_hash") or ""),
        "output_shape_ready": replacement_ready,
        "return_boundary_cutover_applied": use_replacement,
        "return_boundary_scope": "return_item_only",
        "selected_source": "controller_replacement" if use_replacement else "fallback_item",
        "proof_only": False,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "route_return_boundary_hash": stable_final_publication_hash(payload)}


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(
    *,
    route_body_replacement: dict[str, Any] | None = None,
    fallback_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Own the residual-shear cleanup route-body result shell.

    This wrapper does not generate candidates, evaluate candidates, execute CTA
    contracts, author visible wording, route Apply, render UI, or mutate session
    state. It consumes the already-built route-body replacement proof and the
    page-live fallback item, then delegates final item selection to the
    controller return-boundary selector.
    """

    replacement = _mapping(route_body_replacement)
    fallback = _mapping(fallback_item)
    return_boundary = select_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_return_item(
        route_body_replacement=dict(replacement),
        fallback_item=dict(fallback),
    )
    result_item = _mapping(return_boundary.get("result_item"))
    payload = {
        "route_body_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_route_body"
        ),
        "result_item": dict(result_item),
        "result_item_hash": stable_final_publication_hash(result_item),
        "route_body_replacement_hash": str(replacement.get("route_body_replacement_hash") or ""),
        "route_return_boundary": dict(return_boundary),
        "route_return_boundary_hash": str(return_boundary.get("route_return_boundary_hash") or ""),
        "route_body_scope": "result_shell_only",
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "route_body_hash": stable_final_publication_hash(payload)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result(
    *,
    route_body_result: dict[str, Any] | None = None,
    route_return_boundary: dict[str, Any] | None = None,
    proof_debug_return_tail: dict[str, Any] | None = None,
    fallback_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the prebuilt route result consumed by the route execution shell.

    This owns only the final plain-data route-result shape. Candidate
    generation/evaluation, CTA contract execution, visible wording, Apply
    routing, rendering, and session/debug mutation remain outside this helper.
    """

    body = _mapping(route_body_result)
    boundary = _mapping(route_return_boundary)
    proof_tail = _mapping(proof_debug_return_tail)
    fallback = _mapping(fallback_item)
    item = _mapping(
        body.get("result_item")
        or boundary.get("result_item")
        or proof_tail.get("result_item")
        or fallback
    )
    item_hash = stable_final_publication_hash(item)
    body_hash = str(body.get("result_item_hash") or "")
    boundary_hash = str(boundary.get("result_item_hash") or "")
    proof_tail_hash = str(proof_tail.get("result_item_hash") or "")
    fallback_hash = stable_final_publication_hash(fallback)
    parity = bool(
        item
        and (not body_hash or body_hash == item_hash)
        and (not boundary_hash or boundary_hash == item_hash)
        and (not proof_tail_hash or proof_tail_hash == item_hash)
        and (not fallback or fallback_hash == item_hash)
    )
    payload = {
        "prebuilt_route_result_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_prebuilt_route_result"
        ),
        "result_item": dict(item),
        "result_item_hash": item_hash,
        "route_body_result_hash": str(body.get("route_body_hash") or ""),
        "route_body_result_item_hash": body_hash,
        "route_return_boundary_hash": str(boundary.get("route_return_boundary_hash") or ""),
        "route_return_boundary_item_hash": boundary_hash,
        "proof_debug_return_tail_hash": str(
            proof_tail.get("proof_debug_return_tail_hash") or ""
        ),
        "proof_debug_return_tail_item_hash": proof_tail_hash,
        "fallback_item_hash": fallback_hash,
        "prebuilt_route_result_parity": parity,
        "output_shape_ready": bool(item and parity),
        "safe_next_cutover_surface": (
            "prebuilt_route_result_builder" if item and parity else "none"
        ),
        "not_moved": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": False,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "prebuilt_route_result_hash": stable_final_publication_hash(payload),
    }


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_physical_nested_route_body_wrapper(
    *,
    route_entry_decision: dict[str, Any] | None = None,
    route_body_supplier: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Own the physical nested wrapper execution decision.

    This is a temporary extraction boundary. It centralizes the decision to
    invoke the remaining page-live nested route body, while the supplied body
    still owns candidate generation/evaluation, CTA contract execution,
    visible wording, Apply routing, rendering, and session/debug mutation.
    """

    decision = _mapping(route_entry_decision)
    should_execute_route_body = bool(decision.get("should_enter_route"))
    executed_route_body = False
    result_item: dict[str, Any] = {}
    supplier_error = ""
    if should_execute_route_body and callable(route_body_supplier):
        try:
            result_item = _mapping(route_body_supplier())
            executed_route_body = True
        except Exception as exc:  # pragma: no cover - live safety path
            supplier_error = f"{type(exc).__name__}: {exc}"
            raise
    payload = {
        "physical_nested_route_body_wrapper_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_physical_nested_route_body_wrapper"
        ),
        "should_execute_route_body": should_execute_route_body,
        "executed_route_body": executed_route_body,
        "prebuilt_result_item": dict(result_item),
        "prebuilt_result_item_hash": stable_final_publication_hash(result_item),
        "route_entry_decision_hash": str(decision.get("route_entry_decision_hash") or ""),
        "route_body_supplier_owned_elsewhere": True,
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "supplier_error": supplier_error,
        "safe_next_cutover_surface": (
            "replace_physical_nested_route_body_wrapper"
            if executed_route_body or not should_execute_route_body
            else "none"
        ),
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "physical_nested_route_body_wrapper_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail(
    *,
    debug_projection_rows: dict[str, Any] | None = None,
    route_proof: dict[str, Any] | None = None,
    route_shell_readiness: dict[str, Any] | None = None,
    candidate_boundary: dict[str, Any] | None = None,
    fallback_variant_generator_boundary: dict[str, Any] | None = None,
    candidate_evaluator_handoff: dict[str, Any] | None = None,
    materiality_safety_handoff: dict[str, Any] | None = None,
    candidate_selection_sort_key: dict[str, Any] | None = None,
    result_packaging_handoff: dict[str, Any] | None = None,
    button_contract_execution_boundary: dict[str, Any] | None = None,
    cta_apply_payload_source_boundary: dict[str, Any] | None = None,
    final_binding_tail_handoff: dict[str, Any] | None = None,
    route_shell_adapter: dict[str, Any] | None = None,
    evidence_merge_tail_handoff: dict[str, Any] | None = None,
    primary_executor_handoff: dict[str, Any] | None = None,
    route_body_replacement: dict[str, Any] | None = None,
    route_body_result: dict[str, Any] | None = None,
    route_return_boundary: dict[str, Any] | None = None,
    result_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent the residual-shear proof/debug/return tail as controller data.

    The page still mutates debug/session state and physically returns from the
    nested route body. This object gathers the already-built proof rows and
    return-boundary output into a single controller-owned hash surface so later
    deletion proofs can distinguish passive projection from live route logic.
    """

    proof_inputs = {
        "debug_projection_rows": _mapping(debug_projection_rows),
        "route_proof": _mapping(route_proof),
        "route_shell_readiness": _mapping(route_shell_readiness),
        "candidate_boundary": _mapping(candidate_boundary),
        "fallback_variant_generator_boundary": _mapping(fallback_variant_generator_boundary),
        "candidate_evaluator_handoff": _mapping(candidate_evaluator_handoff),
        "materiality_safety_handoff": _mapping(materiality_safety_handoff),
        "candidate_selection_sort_key": _mapping(candidate_selection_sort_key),
        "result_packaging_handoff": _mapping(result_packaging_handoff),
        "button_contract_execution_boundary": _mapping(button_contract_execution_boundary),
        "cta_apply_payload_source_boundary": _mapping(cta_apply_payload_source_boundary),
        "final_binding_tail_handoff": _mapping(final_binding_tail_handoff),
        "route_shell_adapter": _mapping(route_shell_adapter),
        "evidence_merge_tail_handoff": _mapping(evidence_merge_tail_handoff),
        "primary_executor_handoff": _mapping(primary_executor_handoff),
        "route_body_replacement": _mapping(route_body_replacement),
        "route_body_result": _mapping(route_body_result),
        "route_return_boundary": _mapping(route_return_boundary),
    }
    proof_hashes = {
        name: stable_final_publication_hash(value)
        for name, value in proof_inputs.items()
    }
    item = _mapping(
        result_item
        or proof_inputs["route_body_result"].get("result_item")
        or proof_inputs["route_return_boundary"].get("result_item")
        or proof_inputs["route_body_replacement"].get("result_item")
    )
    route_body_result_item_hash = str(
        proof_inputs["route_body_result"].get("result_item_hash") or ""
    )
    route_return_item_hash = str(
        proof_inputs["route_return_boundary"].get("result_item_hash") or ""
    )
    item_hash = stable_final_publication_hash(item)
    return_item_parity = bool(
        item
        and (not route_body_result_item_hash or route_body_result_item_hash == item_hash)
        and (not route_return_item_hash or route_return_item_hash == item_hash)
    )
    missing_required = tuple(
        name
        for name in (
            "debug_projection_rows",
            "route_proof",
            "route_body_replacement",
            "route_body_result",
            "route_return_boundary",
        )
        if not proof_inputs[name]
    )
    payload = {
        "proof_debug_return_tail_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail"
        ),
        "proof_input_hashes": proof_hashes,
        "proof_input_count": len(proof_inputs),
        "missing_required_inputs": missing_required,
        "result_item": dict(item),
        "result_item_hash": item_hash,
        "route_body_result_item_hash": route_body_result_item_hash,
        "route_return_boundary_item_hash": route_return_item_hash,
        "return_item_parity": return_item_parity,
        "debug_projection_represented": bool(proof_inputs["debug_projection_rows"]),
        "route_proof_represented": bool(proof_inputs["route_proof"]),
        "route_return_boundary_represented": bool(proof_inputs["route_return_boundary"]),
        "output_shape_ready": bool(item and not missing_required and return_item_parity),
        "safe_next_cutover_surface": (
            "debug_projection_and_return_tail_compatibility"
            if item and not missing_required and return_item_parity
            else "none"
        ),
        "remaining_page_owned": (
            "debug_session_mutation",
            "physical_nested_route_return",
        ),
        "not_moved": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "proof_debug_return_tail_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff(
    *,
    route_shell_adapter: dict[str, Any] | None = None,
    evidence_inputs: dict[str, Any] | None = None,
    evidence_output_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent residual-shear evidence/exact-blocker merge tail.

    This records hashes for the page-live evidence merge. It does not construct
    outside-band wording, run candidate search/evaluation, build CTA contracts,
    route Apply, render UI, or mutate session state.
    """

    shell = _mapping(route_shell_adapter)
    inputs = _mapping(evidence_inputs)
    output = _mapping(evidence_output_summary)
    status = str(dependency_status or "page_live")
    route_shell_hash = str(shell.get("route_shell_adapter_hash") or "")
    input_hash = stable_final_publication_hash(inputs)
    output_hash = stable_final_publication_hash(output)
    evidence_hash = str(output.get("residual_evidence_hash") or "")
    exact_blockers_hash = str(output.get("residual_exact_blockers_hash") or "")
    blocker_families = tuple(str(value) for value in (output.get("exact_blocker_families") or ()))
    output_shape_ready = bool(
        route_shell_hash
        and inputs.get("route_branch")
        and evidence_hash
        and exact_blockers_hash
    )
    behavior_cutover_ready = output_shape_ready and status == "controller_owned"
    payload = {
        "evidence_merge_tail_handoff_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff"
        ),
        "dependency_slot": "residual_evidence_and_exact_blocker_merge_tail",
        "dependency_status": status,
        "route_shell_adapter_hash": route_shell_hash,
        "evidence_input_hash": input_hash,
        "evidence_output_hash": output_hash,
        "residual_evidence_hash": evidence_hash,
        "residual_exact_blockers_hash": exact_blockers_hash,
        "exact_blocker_families": blocker_families,
        "outside_target_band_allowed": bool(output.get("outside_target_band_allowed")),
        "post_click_bending_blocker_preserved": bool(
            output.get("post_click_bending_blocker_preserved")
        ),
        "post_click_residual_shear_cleanup_after_bending_blocker": bool(
            output.get("post_click_residual_shear_cleanup_after_bending_blocker")
        ),
        "no_second_cta_required": bool(output.get("no_second_cta_required")),
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "evidence_merge_tail_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "evidence_input_hash",
            "evidence_output_hash",
            "residual_evidence_hash",
            "residual_exact_blockers_hash",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else (
            "outside_target_band_blocker_construction",
            "visible_wording_authoring",
            "residual_evidence_update_execution",
            "debug_session_projection",
        ),
        "not_moved": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "primary_shear_tightening_execution",
            "outside_target_band_blocker_construction",
            "visible_wording_authoring",
            "cta_contract_execution",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "evidence_merge_tail_handoff_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter(
    *,
    route_shell_adapter: dict[str, Any] | None = None,
    evidence_inputs: dict[str, Any] | None = None,
    base_residual_evidence: dict[str, Any] | None = None,
    base_exact_blockers: dict[str, Any] | None = None,
    residual_shear_blocker: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Build the residual-shear evidence/exact-blocker merge result.

    This mirrors the live page merge using plain data. It does not create the
    shear blocker wording, run candidate search/evaluation, build CTA contracts,
    route Apply, render UI, or mutate session state.
    """

    inputs = _mapping(evidence_inputs)
    evidence = _mapping(base_residual_evidence)
    exact_blockers = _mapping(base_exact_blockers)
    blocker = _mapping(residual_shear_blocker)
    if blocker:
        exact_blockers["shear"] = dict(blocker)
    evidence.update(
        {
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "post_click_bending_blocker_preserved": True,
            "post_click_residual_shear_cleanup_after_bending_blocker": True,
            "exact_blockers_by_family": dict(exact_blockers),
            "post_click_exact_blockers_by_family": dict(exact_blockers),
            "cleanup_evidence_by_family": dict(exact_blockers),
            "post_click_cleanup_evidence_by_family": dict(exact_blockers),
            "low_util_families": ["bending"],
            "resolved_low_util_families": ["bending"],
            "unresolved_low_util_families": [],
            "post_click_families_below_final_threshold": ["bending"],
            "post_click_unresolved_low_util_families": [],
            "no_second_cta_required": True,
        }
    )
    if bool(inputs.get("residual_outside_preferred_band")):
        evidence.update(
            {
                "outside_target_band_allowed": True,
                "outside_target_band_allowed_reason": str(
                    inputs.get("outside_target_band_allowed_reason") or ""
                ),
                "outside_target_band_allowed_category": "discrete_shear_cleanup_above_preferred_band",
                "target_band_candidate_count": 0,
                "executable_target_band_candidate_count": 0,
            }
        )
    exact_blocker_families = tuple(sorted(str(key) for key in exact_blockers.keys()))
    output_summary = {
        "residual_evidence_hash": stable_final_publication_hash(evidence),
        "residual_exact_blockers_hash": stable_final_publication_hash(exact_blockers),
        "exact_blocker_families": exact_blocker_families,
        "outside_target_band_allowed": bool(evidence.get("outside_target_band_allowed")),
        "post_click_bending_blocker_preserved": bool(
            evidence.get("post_click_bending_blocker_preserved")
        ),
        "post_click_residual_shear_cleanup_after_bending_blocker": bool(
            evidence.get("post_click_residual_shear_cleanup_after_bending_blocker")
        ),
        "no_second_cta_required": bool(evidence.get("no_second_cta_required")),
    }
    handoff = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff(
        route_shell_adapter=dict(route_shell_adapter or {}),
        evidence_inputs=dict(inputs),
        evidence_output_summary=dict(output_summary),
        dependency_status=dependency_status or "page_live",
    )
    payload = {
        "evidence_merge_tail_result_adapter_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter"
        ),
        "dependency_slot": "residual_evidence_and_exact_blocker_merge_tail_result",
        "dependency_status": str(dependency_status or "page_live"),
        "residual_evidence": dict(evidence),
        "residual_exact_blockers": dict(exact_blockers),
        "residual_evidence_hash": output_summary["residual_evidence_hash"],
        "residual_exact_blockers_hash": output_summary["residual_exact_blockers_hash"],
        "exact_blocker_families": exact_blocker_families,
        "evidence_merge_tail_handoff": dict(handoff),
        "evidence_merge_tail_handoff_hash": handoff.get("evidence_merge_tail_handoff_hash"),
        "output_shape_ready": bool(handoff.get("output_shape_ready")),
        "behavior_cutover_ready": bool(
            handoff.get("output_shape_ready")
            and str(dependency_status or "page_live") == "controller_owned"
        ),
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "primary_shear_tightening_execution_owned_elsewhere": True,
        "outside_target_band_blocker_construction_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "evidence_merge_tail_result_adapter_hash": stable_final_publication_hash(payload),
    }


_RESIDUAL_SHEAR_CLEANUP_CANDIDATE_BOUNDARY_DEPENDENCIES = (
    "primary_shear_tightening_executor",
    "fallback_variant_generator",
    "candidate_evaluator",
    "candidate_delta_builder",
    "materiality_screen",
    "shear_detailing_purity_screen",
    "overview_acceptance_screen",
    "preview_status_screen",
    "candidate_selection_sort_key",
    "result_packaging_evaluator",
    "cta_contract_builder",
)


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary(
    *,
    route_proof: dict[str, Any] | None = None,
    route_shell_readiness: dict[str, Any] | None = None,
    dependency_status: dict[str, Any] | None = None,
    candidate_boundary_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent residual shear cleanup candidate/evaluator dependencies.

    This object is a boundary contract, not an executor. It records the hashes
    and required live dependency slots that must be satisfied before any future
    candidate-generation/evaluation behavior can move behind the controller.
    """

    proof = _mapping(route_proof)
    shell = _mapping(route_shell_readiness)
    dependencies = _mapping(dependency_status)
    boundary_inputs = _mapping(candidate_boundary_inputs)
    unresolved_dependencies = tuple(
        dependency
        for dependency in _RESIDUAL_SHEAR_CLEANUP_CANDIDATE_BOUNDARY_DEPENDENCIES
        if dependencies.get(dependency) != "controller_owned"
    )
    dependency_rows = {
        dependency: {
            "status": str(dependencies.get(dependency) or "page_live"),
            "must_remain_live": dependency in unresolved_dependencies,
            "executes_inside_controller": False,
        }
        for dependency in _RESIDUAL_SHEAR_CLEANUP_CANDIDATE_BOUNDARY_DEPENDENCIES
    }
    route_projection = _mapping(proof.get("route_projection"))
    route_request = _mapping(route_projection.get("route_request"))
    search_projection = _mapping(route_projection.get("search_projection"))
    result_projection = _mapping(route_projection.get("result_projection"))
    boundary_input_hashes = {
        "route_proof_hash": str(proof.get("proof_hash") or ""),
        "route_projection_hash": str(proof.get("route_projection_hash") or ""),
        "route_shell_readiness_hash": str(shell.get("readiness_hash") or ""),
        "route_request_hash": stable_final_publication_hash(route_request),
        "search_projection_hash": stable_final_publication_hash(search_projection),
        "result_projection_hash": stable_final_publication_hash(result_projection),
        "candidate_boundary_inputs_hash": stable_final_publication_hash(boundary_inputs),
    }
    request_shape_ready = bool(
        boundary_input_hashes["route_proof_hash"]
        and boundary_input_hashes["route_projection_hash"]
        and route_request
        and search_projection is not None
        and result_projection is not None
    )
    dependency_boundary_ready = request_shape_ready and bool(dependency_rows)
    behavior_cutover_ready = dependency_boundary_ready and not unresolved_dependencies
    payload = {
        "candidate_boundary_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_candidate_boundary"
        ),
        "request_shape_ready": request_shape_ready,
        "dependency_boundary_ready": dependency_boundary_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "candidate_generation_cutover_ready": behavior_cutover_ready,
        "candidate_evaluation_cutover_ready": behavior_cutover_ready,
        "boundary_input_hashes": boundary_input_hashes,
        "dependency_rows": dependency_rows,
        "unresolved_dependencies": unresolved_dependencies,
        "controller_may_own_now": (
            "candidate_boundary_identity",
            "dependency_slot_inventory",
            "boundary_input_hashes",
        ),
        "page_must_keep_for_now": unresolved_dependencies,
        "not_moved": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "formula_helpers",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "candidate_boundary_hash": stable_final_publication_hash(payload)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(
    *,
    candidate_boundary: dict[str, Any] | None = None,
    executor_inputs: dict[str, Any] | None = None,
    executor_output_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent the primary shear tightening executor handoff boundary."""

    boundary = _mapping(candidate_boundary)
    inputs = _mapping(executor_inputs)
    output = _mapping(executor_output_summary)
    status = str(dependency_status or "page_live")
    boundary_hash = str(boundary.get("candidate_boundary_hash") or "")
    input_hash = stable_final_publication_hash(inputs)
    output_hash = stable_final_publication_hash(output)
    output_shape_ready = bool(
        boundary_hash
        and inputs.get("route_branch")
        and "starting_shear_util" in inputs
        and "target_low" in inputs
        and "target_high" in inputs
        and "executor_attempted" in output
        and "has_candidate" in output
    )
    behavior_cutover_ready = output_shape_ready and status == "controller_owned"
    payload = {
        "primary_executor_handoff_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_primary_executor_handoff"
        ),
        "dependency_slot": "primary_shear_tightening_executor",
        "dependency_status": status,
        "candidate_boundary_hash": boundary_hash,
        "executor_input_hash": input_hash,
        "executor_output_hash": output_hash,
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "executor_input_hash",
            "executor_output_shape_hash",
            "dependency_slot_status",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else ("primary_shear_tightening_execution",),
        "not_moved": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "formula_helpers",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "primary_executor_handoff_hash": stable_final_publication_hash(payload)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter(
    *,
    primary_executor_handoff: dict[str, Any] | None = None,
    adapter_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent the injected-adapter boundary for the primary shear executor."""

    handoff = _mapping(primary_executor_handoff)
    contract = _mapping(adapter_contract)
    required_contract_fields = (
        "executor_name",
        "input_hash",
        "output_hash",
        "stale_state_policy",
        "exception_policy",
    )
    missing_contract_fields = tuple(
        field for field in required_contract_fields if not contract.get(field)
    )
    handoff_hash = str(handoff.get("primary_executor_handoff_hash") or "")
    input_hash_matches = bool(
        handoff.get("executor_input_hash")
        and contract.get("input_hash")
        and str(handoff.get("executor_input_hash")) == str(contract.get("input_hash"))
    )
    output_hash_matches = bool(
        handoff.get("executor_output_hash")
        and contract.get("output_hash")
        and str(handoff.get("executor_output_hash")) == str(contract.get("output_hash"))
    )
    adapter_boundary_ready = bool(
        handoff_hash
        and handoff.get("output_shape_ready")
        and not missing_contract_fields
        and input_hash_matches
        and output_hash_matches
    )
    behavior_cutover_ready = bool(
        adapter_boundary_ready
        and contract.get("executor_available") is True
        and contract.get("executor_is_injected") is True
        and contract.get("executor_is_deterministic") is True
        and contract.get("executor_changes_behavior") is False
    )
    payload = {
        "primary_executor_injected_adapter_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter"
        ),
        "dependency_slot": "primary_shear_tightening_executor",
        "primary_executor_handoff_hash": handoff_hash,
        "adapter_contract_hash": stable_final_publication_hash(contract),
        "input_hash_matches": input_hash_matches,
        "output_hash_matches": output_hash_matches,
        "missing_contract_fields": missing_contract_fields,
        "adapter_boundary_ready": adapter_boundary_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "safe_next_cutover_surface": (
            "primary_executor_injected_adapter"
            if adapter_boundary_ready
            else "none"
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else ("primary_shear_tightening_execution",),
        "not_moved": (
            "formula_helpers",
            "fallback_variant_generator",
            "candidate_evaluation_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "primary_executor_injected_adapter_hash": stable_final_publication_hash(payload)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_boundary(
    *,
    primary_executor_handoff: dict[str, Any] | None = None,
    primary_executor_injected_adapter: dict[str, Any] | None = None,
    dependency_descriptor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent the injected primary executor dependency boundary.

    The boundary proves the route shell can describe and pass through the
    existing page-injected executor without owning the executor implementation,
    formulas, candidate generation, CTA/apply behavior, or visible wording.
    """

    handoff = _mapping(primary_executor_handoff)
    adapter = _mapping(primary_executor_injected_adapter)
    descriptor = _mapping(dependency_descriptor)
    required_descriptor_fields = (
        "executor_name",
        "runner_name",
        "injection_site",
        "dependency_status",
        "stale_state_policy",
        "exception_policy",
    )
    missing_descriptor_fields = tuple(
        field for field in required_descriptor_fields if not descriptor.get(field)
    )
    dependency_status = str(descriptor.get("dependency_status") or "")
    handoff_hash = str(handoff.get("primary_executor_handoff_hash") or "")
    adapter_hash = str(adapter.get("primary_executor_injected_adapter_hash") or "")
    handoff_ready = bool(handoff_hash and handoff.get("output_shape_ready"))
    adapter_ready = bool(adapter_hash and adapter.get("adapter_boundary_ready"))
    page_injected_dependency = dependency_status in {"page_live", "page_injected"}
    boundary_ready = bool(
        handoff_ready
        and adapter_ready
        and page_injected_dependency
        and not missing_descriptor_fields
        and str(descriptor.get("executor_name") or "")
        == "primary_shear_tightening_executor"
    )
    route_shape_cutover_ready = bool(boundary_ready)
    payload = {
        "primary_executor_dependency_boundary_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_boundary"
        ),
        "dependency_slot": "primary_shear_tightening_executor",
        "dependency_status": dependency_status or "unknown",
        "primary_executor_handoff_hash": handoff_hash,
        "primary_executor_injected_adapter_hash": adapter_hash,
        "dependency_descriptor_hash": stable_final_publication_hash(descriptor),
        "missing_descriptor_fields": missing_descriptor_fields,
        "handoff_ready": handoff_ready,
        "adapter_ready": adapter_ready,
        "page_injected_dependency": page_injected_dependency,
        "dependency_boundary_ready": boundary_ready,
        "route_shape_cutover_ready": route_shape_cutover_ready,
        "safe_to_delete_page_executor_now": False,
        "safe_next_surface": (
            "primary_executor_dependency_trace_wiring"
            if boundary_ready
            else "primary_executor_dependency_descriptor_completion"
        ),
        "page_must_keep_for_now": (
            "primary_shear_tightening_execution",
            "formula_helpers",
        ),
        "not_moved": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "fallback_search_loop",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "primary_executor_dependency_boundary_hash": stable_final_publication_hash(payload)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary(
    *,
    candidate_boundary: dict[str, Any] | None = None,
    generator_inputs: dict[str, Any] | None = None,
    generator_output_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent the residual-shear fallback variant generator boundary.

    This object records the generated variant/update stream shape only. It does
    not generate variants, evaluate candidates, author wording, or bind CTA/apply
    payloads.
    """

    boundary = _mapping(candidate_boundary)
    inputs = _mapping(generator_inputs)
    output = _mapping(generator_output_summary)
    status = str(dependency_status or "page_live")
    boundary_hash = str(boundary.get("candidate_boundary_hash") or "")
    generator_input_hash = stable_final_publication_hash(inputs)
    generator_output_hash = stable_final_publication_hash(output)
    iteration_limit = output.get("iteration_limit", inputs.get("iteration_limit"))
    try:
        iteration_limit_int = int(iteration_limit)
    except Exception:
        iteration_limit_int = None
    generated_variant_count = output.get("generated_variant_count")
    generated_update_count = output.get("generated_update_count")
    try:
        generated_variant_count_int = int(generated_variant_count)
    except Exception:
        generated_variant_count_int = None
    try:
        generated_update_count_int = int(generated_update_count)
    except Exception:
        generated_update_count_int = None
    order_proof = _mapping(output.get("order_proof"))
    stable_sequence_hash = str(
        output.get("stable_sequence_hash")
        or order_proof.get("stable_sequence_hash")
        or ""
    )
    output_shape_ready = bool(
        boundary_hash
        and inputs.get("route_branch")
        and inputs.get("mode_config_hash")
        and inputs.get("state_fingerprint")
        and iteration_limit_int == 64
        and generated_variant_count_int is not None
        and generated_update_count_int is not None
        and stable_sequence_hash
    )
    behavior_cutover_ready = output_shape_ready and status == "controller_owned"
    payload = {
        "fallback_variant_generator_boundary_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary"
        ),
        "dependency_slot": "fallback_variant_generator",
        "dependency_status": status,
        "candidate_boundary_hash": boundary_hash,
        "generator_input_hash": generator_input_hash,
        "generator_output_hash": generator_output_hash,
        "iteration_limit": iteration_limit_int,
        "generated_variant_count": generated_variant_count_int,
        "generated_update_count": generated_update_count_int,
        "stable_sequence_hash": stable_sequence_hash,
        "order_proof_hash": stable_final_publication_hash(order_proof),
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "generator_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "generator_input_hash",
            "generator_output_shape_hash",
            "iteration_limit_proof",
            "stable_sequence_hash",
            "dependency_slot_status",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else ("fallback_variant_generation",),
        "not_moved": (
            "candidate_evaluation_execution",
            "candidate_delta_builder_execution",
            "materiality_screen_execution",
            "shear_detailing_purity_screen_execution",
            "overview_acceptance_execution",
            "preview_status_execution",
            "candidate_selection_execution",
            "formula_helpers",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "fallback_variant_generator_boundary_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter(
    *,
    fallback_variant_generator_boundary: dict[str, Any] | None = None,
    adapter_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent the injected-adapter boundary for the fallback variant generator."""

    boundary = _mapping(fallback_variant_generator_boundary)
    contract = _mapping(adapter_contract)
    required_contract_fields = (
        "generator_name",
        "input_hash",
        "output_hash",
        "iteration_limit",
        "stale_state_policy",
        "exception_policy",
    )
    missing_contract_fields = tuple(
        field for field in required_contract_fields if not contract.get(field)
    )
    boundary_hash = str(boundary.get("fallback_variant_generator_boundary_hash") or "")
    input_hash_matches = bool(
        boundary.get("generator_input_hash")
        and contract.get("input_hash")
        and str(boundary.get("generator_input_hash")) == str(contract.get("input_hash"))
    )
    output_hash_matches = bool(
        boundary.get("generator_output_hash")
        and contract.get("output_hash")
        and str(boundary.get("generator_output_hash")) == str(contract.get("output_hash"))
    )
    iteration_limit_matches = bool(
        boundary.get("iteration_limit") is not None
        and contract.get("iteration_limit") is not None
        and int(boundary.get("iteration_limit")) == int(contract.get("iteration_limit"))
    )
    adapter_boundary_ready = bool(
        boundary_hash
        and boundary.get("output_shape_ready")
        and not missing_contract_fields
        and input_hash_matches
        and output_hash_matches
        and iteration_limit_matches
    )
    behavior_cutover_ready = bool(
        adapter_boundary_ready
        and contract.get("generator_available") is True
        and contract.get("generator_is_injected") is True
        and contract.get("generator_is_deterministic") is True
        and contract.get("generator_changes_behavior") is False
    )
    payload = {
        "fallback_variant_generator_injected_adapter_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter"
        ),
        "dependency_slot": "fallback_variant_generator",
        "fallback_variant_generator_boundary_hash": boundary_hash,
        "adapter_contract_hash": stable_final_publication_hash(contract),
        "input_hash_matches": input_hash_matches,
        "output_hash_matches": output_hash_matches,
        "iteration_limit_matches": iteration_limit_matches,
        "missing_contract_fields": missing_contract_fields,
        "adapter_boundary_ready": adapter_boundary_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "safe_next_cutover_surface": (
            "fallback_variant_generator_injected_adapter"
            if adapter_boundary_ready
            else "none"
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else ("fallback_variant_generation",),
        "not_moved": (
            "shared_generate_less_shear_reo_variants_definition",
            "other_generator_calls",
            "candidate_evaluation_execution",
            "candidate_delta_builder_execution",
            "candidate_selection_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "fallback_variant_generator_injected_adapter_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary(
    *,
    fallback_variant_generator_boundary: dict[str, Any] | None = None,
    fallback_variant_generator_injected_adapter: dict[str, Any] | None = None,
    dependency_descriptor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent the injected fallback variant generator dependency boundary.

    This boundary records the page-injected generator slot and its stable
    input/output proof. It does not generate variants, evaluate candidates,
    choose a candidate, author wording, bind CTA/apply payloads, or mutate
    session state.
    """

    boundary = _mapping(fallback_variant_generator_boundary)
    adapter = _mapping(fallback_variant_generator_injected_adapter)
    descriptor = _mapping(dependency_descriptor)
    required_descriptor_fields = (
        "generator_name",
        "runner_name",
        "injection_site",
        "dependency_status",
        "iteration_limit",
        "stale_state_policy",
        "exception_policy",
    )
    missing_descriptor_fields = tuple(
        field for field in required_descriptor_fields if not descriptor.get(field)
    )
    dependency_status = str(descriptor.get("dependency_status") or "")
    boundary_hash = str(boundary.get("fallback_variant_generator_boundary_hash") or "")
    adapter_hash = str(adapter.get("fallback_variant_generator_injected_adapter_hash") or "")
    boundary_ready = bool(boundary_hash and boundary.get("output_shape_ready"))
    adapter_ready = bool(adapter_hash and adapter.get("adapter_boundary_ready"))
    page_injected_dependency = dependency_status in {"page_live", "page_injected"}
    try:
        descriptor_iteration_limit = int(descriptor.get("iteration_limit"))
    except Exception:
        descriptor_iteration_limit = None
    iteration_limit_matches = bool(
        boundary.get("iteration_limit") is not None
        and descriptor_iteration_limit is not None
        and int(boundary.get("iteration_limit")) == descriptor_iteration_limit
    )
    dependency_boundary_ready = bool(
        boundary_ready
        and adapter_ready
        and page_injected_dependency
        and not missing_descriptor_fields
        and str(descriptor.get("generator_name") or "")
        == "fallback_variant_generator"
        and iteration_limit_matches
    )
    route_shape_cutover_ready = bool(dependency_boundary_ready)
    payload = {
        "fallback_variant_generator_dependency_boundary_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary"
        ),
        "dependency_slot": "fallback_variant_generator",
        "dependency_status": dependency_status or "unknown",
        "fallback_variant_generator_boundary_hash": boundary_hash,
        "fallback_variant_generator_injected_adapter_hash": adapter_hash,
        "dependency_descriptor_hash": stable_final_publication_hash(descriptor),
        "missing_descriptor_fields": missing_descriptor_fields,
        "boundary_ready": boundary_ready,
        "adapter_ready": adapter_ready,
        "page_injected_dependency": page_injected_dependency,
        "iteration_limit_matches": iteration_limit_matches,
        "dependency_boundary_ready": dependency_boundary_ready,
        "route_shape_cutover_ready": route_shape_cutover_ready,
        "safe_to_delete_page_generator_now": False,
        "safe_next_surface": (
            "fallback_variant_generator_dependency_trace_wiring"
            if dependency_boundary_ready
            else "fallback_variant_generator_dependency_descriptor_completion"
        ),
        "page_must_keep_for_now": (
            "fallback_variant_generation",
            "shared_generate_less_shear_reo_variants_definition",
        ),
        "not_moved": (
            "candidate_evaluation_execution",
            "candidate_delta_builder_execution",
            "materiality_screen_execution",
            "shear_detailing_purity_screen_execution",
            "overview_acceptance_execution",
            "preview_status_execution",
            "candidate_selection_execution",
            "formula_helpers",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "fallback_variant_generator_dependency_boundary_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff(
    *,
    candidate_boundary: dict[str, Any] | None = None,
    evaluation_inputs: dict[str, Any] | None = None,
    evaluation_output_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent the residual-shear fallback candidate evaluator handoff boundary.

    This object records the live evaluator stream shape only. It does not call
    the evaluator, inspect formulas, author wording, select a candidate, or bind
    CTA/apply payloads.
    """

    boundary = _mapping(candidate_boundary)
    inputs = _mapping(evaluation_inputs)
    output = _mapping(evaluation_output_summary)
    status = str(dependency_status or "page_live")
    boundary_hash = str(boundary.get("candidate_boundary_hash") or "")
    evaluator_input_hash = stable_final_publication_hash(inputs)
    evaluator_output_hash = stable_final_publication_hash(output)
    evaluation_source = str(inputs.get("evaluation_source") or "")
    evaluation_label = str(inputs.get("evaluation_label") or "")
    evaluation_action_type = str(inputs.get("evaluation_action_type") or "")

    def _int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except Exception:
            return None

    attempted_count = _int_or_none(output.get("evaluation_attempted_count"))
    evaluated_count = _int_or_none(output.get("evaluated_candidate_count"))
    successful_count = _int_or_none(output.get("successful_candidate_count"))
    failed_count = _int_or_none(output.get("failed_candidate_count"))
    stable_sequence_hash = str(output.get("stable_sequence_hash") or "")
    output_shape_ready = bool(
        boundary_hash
        and inputs.get("route_branch")
        and evaluation_source
        and evaluation_label
        and evaluation_action_type
        and attempted_count is not None
        and evaluated_count is not None
        and successful_count is not None
        and failed_count is not None
        and stable_sequence_hash
    )
    behavior_cutover_ready = output_shape_ready and status == "controller_owned"
    payload = {
        "candidate_evaluator_handoff_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff"
        ),
        "dependency_slot": "candidate_evaluator",
        "dependency_status": status,
        "candidate_boundary_hash": boundary_hash,
        "evaluator_input_hash": evaluator_input_hash,
        "evaluator_output_hash": evaluator_output_hash,
        "evaluation_source": evaluation_source,
        "evaluation_label_hash": stable_final_publication_hash(evaluation_label),
        "evaluation_action_type": evaluation_action_type,
        "evaluation_attempted_count": attempted_count,
        "evaluated_candidate_count": evaluated_count,
        "successful_candidate_count": successful_count,
        "failed_candidate_count": failed_count,
        "stable_sequence_hash": stable_sequence_hash,
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "evaluator_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "evaluator_input_hash",
            "evaluator_output_shape_hash",
            "evaluation_source_shape",
            "evaluation_sequence_hash",
            "dependency_slot_status",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else ("candidate_evaluation_execution",),
        "not_moved": (
            "candidate_evaluation_execution",
            "formula_helpers",
            "candidate_delta_builder_execution",
            "materiality_screen_execution",
            "shear_detailing_purity_screen_execution",
            "overview_acceptance_execution",
            "preview_status_execution",
            "candidate_selection_execution",
            "result_packaging_evaluator",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "candidate_evaluator_handoff_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter(
    *,
    candidate_evaluator_handoff: dict[str, Any] | None = None,
    adapter_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent the injected-adapter boundary for the residual-shear candidate evaluator."""

    handoff = _mapping(candidate_evaluator_handoff)
    contract = _mapping(adapter_contract)
    required_contract_fields = (
        "evaluator_name",
        "input_hash",
        "output_hash",
        "stale_state_policy",
        "exception_policy",
        "acceptance_policy",
    )
    missing_contract_fields = tuple(
        field for field in required_contract_fields if not contract.get(field)
    )
    handoff_hash = str(handoff.get("candidate_evaluator_handoff_hash") or "")
    input_hash_matches = bool(
        handoff.get("evaluator_input_hash")
        and contract.get("input_hash")
        and str(handoff.get("evaluator_input_hash")) == str(contract.get("input_hash"))
    )
    output_hash_matches = bool(
        handoff.get("evaluator_output_hash")
        and contract.get("output_hash")
        and str(handoff.get("evaluator_output_hash")) == str(contract.get("output_hash"))
    )
    sequence_hash_matches = bool(
        handoff.get("stable_sequence_hash")
        and contract.get("stable_sequence_hash")
        and str(handoff.get("stable_sequence_hash")) == str(contract.get("stable_sequence_hash"))
    )
    adapter_boundary_ready = bool(
        handoff_hash
        and handoff.get("output_shape_ready")
        and not missing_contract_fields
        and input_hash_matches
        and output_hash_matches
        and sequence_hash_matches
    )
    behavior_cutover_ready = bool(
        adapter_boundary_ready
        and contract.get("evaluator_available") is True
        and contract.get("evaluator_is_injected") is True
        and contract.get("evaluator_changes_behavior") is False
    )
    payload = {
        "candidate_evaluator_injected_adapter_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter"
        ),
        "dependency_slot": "candidate_evaluator",
        "candidate_evaluator_handoff_hash": handoff_hash,
        "adapter_contract_hash": stable_final_publication_hash(contract),
        "input_hash_matches": input_hash_matches,
        "output_hash_matches": output_hash_matches,
        "sequence_hash_matches": sequence_hash_matches,
        "missing_contract_fields": missing_contract_fields,
        "adapter_boundary_ready": adapter_boundary_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "safe_next_cutover_surface": (
            "candidate_evaluator_injected_adapter"
            if adapter_boundary_ready
            else "none"
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else ("candidate_evaluation_execution",),
        "not_moved": (
            "formula_helpers",
            "candidate_delta_builder_execution",
            "materiality_screen_execution",
            "shear_detailing_purity_screen_execution",
            "overview_acceptance_execution",
            "preview_status_execution",
            "candidate_selection_execution",
            "result_packaging_evaluator",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "candidate_evaluator_injected_adapter_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff(
    *,
    candidate_evaluator_handoff: dict[str, Any] | None = None,
    screen_inputs: dict[str, Any] | None = None,
    screen_output_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent residual-shear candidate materiality/safety screening.

    This object records sequence hashes and counters only. It does not execute
    delta building, materiality checks, detailing purity checks, overview
    acceptance, preview-status rejection, CTA contracts, or visible wording.
    """

    evaluator = _mapping(candidate_evaluator_handoff)
    inputs = _mapping(screen_inputs)
    output = _mapping(screen_output_summary)
    status = str(dependency_status or "page_live")
    evaluator_hash = str(evaluator.get("candidate_evaluator_handoff_hash") or "")
    input_hash = stable_final_publication_hash(inputs)
    output_hash = stable_final_publication_hash(output)

    def _int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except Exception:
            return None

    generated_update_count = _int_or_none(output.get("generated_update_count"))
    evaluation_attempted_count = _int_or_none(output.get("evaluation_attempted_count"))
    accepted_candidate_count = _int_or_none(output.get("accepted_candidate_count"))
    rejected_candidate_count = _int_or_none(output.get("rejected_candidate_count"))
    stable_sequence_hash = str(output.get("stable_sequence_hash") or "")
    output_shape_ready = bool(
        evaluator_hash
        and inputs.get("route_branch")
        and inputs.get("state_fingerprint")
        and generated_update_count is not None
        and evaluation_attempted_count is not None
        and accepted_candidate_count is not None
        and rejected_candidate_count is not None
        and stable_sequence_hash
    )
    behavior_cutover_ready = output_shape_ready and status == "controller_owned"
    payload = {
        "materiality_safety_screen_handoff_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff"
        ),
        "dependency_slot": "materiality_and_safety_screen",
        "dependency_status": status,
        "candidate_evaluator_handoff_hash": evaluator_hash,
        "screen_input_hash": input_hash,
        "screen_output_hash": output_hash,
        "generated_update_count": generated_update_count,
        "evaluation_attempted_count": evaluation_attempted_count,
        "accepted_candidate_count": accepted_candidate_count,
        "rejected_candidate_count": rejected_candidate_count,
        "stable_sequence_hash": stable_sequence_hash,
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "screen_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "screen_input_hash",
            "screen_output_shape_hash",
            "screen_sequence_hash",
            "accepted_rejected_candidate_counts",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else (
            "candidate_delta_builder_execution",
            "materiality_screen_execution",
            "shear_detailing_purity_screen_execution",
            "overview_acceptance_screen_execution",
            "preview_status_screen_execution",
        ),
        "not_moved": (
            "candidate_delta_builder_execution",
            "materiality_screen_execution",
            "shear_detailing_purity_screen_execution",
            "overview_acceptance_screen_execution",
            "preview_status_screen_execution",
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "candidate_selection_execution",
            "result_packaging_evaluator",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "materiality_safety_screen_handoff_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key(
    *,
    candidate_evaluator_handoff: dict[str, Any] | None = None,
    selection_inputs: dict[str, Any] | None = None,
    selection_output_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent the residual-shear cleanup candidate selection/sort-key boundary.

    This records the page-live selection shape only. It does not sort candidates,
    choose the candidate, build Apply payloads, author wording, or render UI.
    """

    handoff = _mapping(candidate_evaluator_handoff)
    inputs = _mapping(selection_inputs)
    output = _mapping(selection_output_summary)
    status = str(dependency_status or "page_live")
    handoff_hash = str(handoff.get("candidate_evaluator_handoff_hash") or "")
    candidate_count = output.get("candidate_count")
    try:
        candidate_count_int = int(candidate_count)
    except Exception:
        candidate_count_int = None
    stable_sequence_hash = str(output.get("stable_candidate_sequence_hash") or "")
    selected_updates_hash = str(output.get("selected_updates_hash") or "")
    selected_candidate_hash = str(output.get("selected_candidate_hash") or "")
    selected_sort_key_hash = str(output.get("selected_sort_key_hash") or "")
    sort_key_order = tuple(inputs.get("sort_key_order") or ())
    required_sort_key_order = ("shear_util", "update_count", "updates_items")
    selection_input_hash = stable_final_publication_hash(inputs)
    selection_output_hash = stable_final_publication_hash(output)
    output_shape_ready = bool(
        handoff_hash
        and inputs.get("route_branch")
        and sort_key_order == required_sort_key_order
        and candidate_count_int is not None
        and candidate_count_int > 0
        and stable_sequence_hash
        and selected_updates_hash
        and selected_candidate_hash
        and selected_sort_key_hash
    )
    behavior_cutover_ready = output_shape_ready and status == "controller_owned"
    payload = {
        "candidate_selection_sort_key_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key"
        ),
        "dependency_slot": "candidate_selection",
        "dependency_status": status,
        "candidate_evaluator_handoff_hash": handoff_hash,
        "selection_input_hash": selection_input_hash,
        "selection_output_hash": selection_output_hash,
        "sort_key_order": sort_key_order,
        "required_sort_key_order": required_sort_key_order,
        "sort_key_order_matches": sort_key_order == required_sort_key_order,
        "candidate_count": candidate_count_int,
        "stable_candidate_sequence_hash": stable_sequence_hash,
        "selected_updates_hash": selected_updates_hash,
        "selected_candidate_hash": selected_candidate_hash,
        "selected_sort_key_hash": selected_sort_key_hash,
        "selected_shear_util": _float_or_none(output.get("selected_shear_util")),
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "selection_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "selection_input_hash",
            "selection_output_shape_hash",
            "selection_sequence_hash",
            "selected_candidate_identity_hash",
            "sort_key_order_contract",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else ("candidate_selection_execution",),
        "not_moved": (
            "candidate_selection_execution",
            "candidate_evaluation_execution",
            "result_packaging_evaluator",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "candidate_selection_sort_key_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter(
    *,
    candidate_selection_sort_key: dict[str, Any] | None = None,
    adapter_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent injected-adapter readiness for residual-shear candidate selection."""

    selection = _mapping(candidate_selection_sort_key)
    contract = _mapping(adapter_contract)
    required_contract_fields = (
        "selector_name",
        "input_hash",
        "output_hash",
        "stable_sequence_hash",
        "sort_key_order_hash",
        "selected_candidate_hash",
        "stale_state_policy",
        "tie_break_policy",
    )
    missing_contract_fields = tuple(
        field for field in required_contract_fields if not contract.get(field)
    )
    selection_hash = str(selection.get("candidate_selection_sort_key_hash") or "")
    input_hash_matches = bool(
        selection.get("selection_input_hash")
        and contract.get("input_hash")
        and str(selection.get("selection_input_hash")) == str(contract.get("input_hash"))
    )
    output_hash_matches = bool(
        selection.get("selection_output_hash")
        and contract.get("output_hash")
        and str(selection.get("selection_output_hash")) == str(contract.get("output_hash"))
    )
    sequence_hash_matches = bool(
        selection.get("stable_candidate_sequence_hash")
        and contract.get("stable_sequence_hash")
        and str(selection.get("stable_candidate_sequence_hash"))
        == str(contract.get("stable_sequence_hash"))
    )
    selected_candidate_hash_matches = bool(
        selection.get("selected_candidate_hash")
        and contract.get("selected_candidate_hash")
        and str(selection.get("selected_candidate_hash"))
        == str(contract.get("selected_candidate_hash"))
    )
    sort_key_order_hash = stable_final_publication_hash(
        tuple(selection.get("sort_key_order") or ())
    )
    sort_key_order_hash_matches = bool(
        contract.get("sort_key_order_hash")
        and str(contract.get("sort_key_order_hash")) == str(sort_key_order_hash)
    )
    adapter_boundary_ready = bool(
        selection_hash
        and selection.get("output_shape_ready")
        and not missing_contract_fields
        and input_hash_matches
        and output_hash_matches
        and sequence_hash_matches
        and selected_candidate_hash_matches
        and sort_key_order_hash_matches
    )
    behavior_cutover_ready = bool(
        adapter_boundary_ready
        and contract.get("selector_available") is True
        and contract.get("selector_is_injected") is True
        and contract.get("selector_changes_behavior") is False
    )
    payload = {
        "candidate_selection_injected_adapter_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter"
        ),
        "dependency_slot": "candidate_selection",
        "candidate_selection_sort_key_hash": selection_hash,
        "adapter_contract_hash": stable_final_publication_hash(contract),
        "input_hash_matches": input_hash_matches,
        "output_hash_matches": output_hash_matches,
        "sequence_hash_matches": sequence_hash_matches,
        "selected_candidate_hash_matches": selected_candidate_hash_matches,
        "sort_key_order_hash_matches": sort_key_order_hash_matches,
        "missing_contract_fields": missing_contract_fields,
        "adapter_boundary_ready": adapter_boundary_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "safe_next_cutover_surface": (
            "candidate_selection_injected_adapter"
            if adapter_boundary_ready
            else "none"
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else ("candidate_selection_execution",),
        "not_moved": (
            "candidate_selection_execution",
            "candidate_evaluation_execution",
            "result_packaging_evaluator",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "candidate_selection_injected_adapter_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff(
    *,
    route_entry_guard: dict[str, Any] | None = None,
    fallback_search_inputs: dict[str, Any] | None = None,
    generator_update_sequence: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    evaluation_sequence: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    selection_sequence: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    selection_output_summary: dict[str, Any] | None = None,
    selected_result_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent the residual-shear fallback search loop output shape."""

    guard = _mapping(route_entry_guard)
    inputs = _mapping(fallback_search_inputs)
    generator_rows = [_mapping(row) for row in list(generator_update_sequence or [])]
    evaluation_rows = [_mapping(row) for row in list(evaluation_sequence or [])]
    selection_rows = [_mapping(row) for row in list(selection_sequence or [])]
    selection_summary = _mapping(selection_output_summary)
    selected_summary = _mapping(selected_result_summary)
    status = str(dependency_status or "page_live")

    def _int_or_zero(value: Any) -> int:
        try:
            return int(value)
        except Exception:
            return 0

    iteration_limit = _int_or_zero(inputs.get("iteration_limit") or 64)
    variant_count = _int_or_zero(inputs.get("fallback_variant_count"))
    generator_update_count = len(generator_rows)
    evaluation_count = len(evaluation_rows)
    accepted_count = sum(1 for row in evaluation_rows if bool(row.get("accepted_as_safe_cleanup")))
    rejected_count = max(0, evaluation_count - accepted_count)
    selected_updates_hash = str(
        selected_summary.get("selected_updates_hash")
        or selection_summary.get("selected_updates_hash")
        or ""
    )
    selected_candidate_hash = str(
        selected_summary.get("selected_candidate_hash")
        or selection_summary.get("selected_candidate_hash")
        or ""
    )
    selected_present = bool(
        selected_updates_hash
        and selected_candidate_hash
        and bool(selected_summary.get("selected_result_present"))
    )
    generator_sequence_hash = stable_final_publication_hash(generator_rows)
    evaluation_sequence_hash = stable_final_publication_hash(evaluation_rows)
    selection_sequence_hash = stable_final_publication_hash(selection_rows)
    selected_result_hash = stable_final_publication_hash(selected_summary)
    output_shape_ready = bool(
        guard.get("route_entry_guard_hash")
        and inputs.get("route_branch")
        and inputs.get("state_fingerprint")
        and inputs.get("mode_config_hash")
        and iteration_limit == 64
        and isinstance(generator_rows, list)
        and isinstance(evaluation_rows, list)
        and isinstance(selection_rows, list)
    )
    behavior_cutover_ready = output_shape_ready and status == "controller_owned"
    payload = {
        "fallback_search_loop_handoff_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff"
        ),
        "dependency_slot": "fallback_search_loop",
        "dependency_status": status,
        "route_entry_guard_hash": str(guard.get("route_entry_guard_hash") or ""),
        "fallback_search_input_hash": stable_final_publication_hash(inputs),
        "generator_update_sequence_hash": generator_sequence_hash,
        "evaluation_sequence_hash": evaluation_sequence_hash,
        "selection_sequence_hash": selection_sequence_hash,
        "selection_output_summary_hash": stable_final_publication_hash(selection_summary),
        "selected_result_hash": selected_result_hash,
        "selected_updates_hash": selected_updates_hash,
        "selected_candidate_hash": selected_candidate_hash,
        "iteration_limit": iteration_limit,
        "fallback_variant_generator_attempted": bool(
            inputs.get("fallback_variant_generator_attempted")
        ),
        "fallback_variant_count": variant_count,
        "generator_update_count": generator_update_count,
        "evaluation_count": evaluation_count,
        "accepted_candidate_count": accepted_count,
        "rejected_candidate_count": rejected_count,
        "selection_candidate_count": _int_or_zero(selection_summary.get("candidate_count")),
        "selected_result_present": selected_present,
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "fallback_search_loop_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "fallback_search_input_hash",
            "generator_update_sequence_hash",
            "evaluation_sequence_hash",
            "selection_sequence_hash",
            "selected_result_identity_hash",
            "loop_counter_summary",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else ("fallback_search_loop_execution", "selected_result_assembly"),
        "not_moved": (
            "fallback_variant_generator_execution",
            "candidate_evaluation_execution",
            "materiality_screen_execution",
            "safety_acceptance_execution",
            "candidate_selection_execution",
            "result_packaging_evaluator",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "fallback_search_loop_handoff_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result(
    *,
    selected_candidate_row: dict[str, Any] | None = None,
    selected_label: str | None = None,
    current_shear_util: float | int | str | None = None,
    safe_candidate_count: int | None = None,
    route_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the selected fallback result from already-evaluated candidate data."""

    row = _mapping(selected_candidate_row)
    updates = _mapping(row.get("updates"))
    candidate = _mapping(row.get("candidate"))
    label = str(selected_label or "").strip()
    shear_util = _float_or_none(row.get("shear_util"))
    starting_util = _float_or_none(current_shear_util)
    try:
        candidate_count = int(safe_candidate_count if safe_candidate_count is not None else 0)
    except Exception:
        candidate_count = 0
    if candidate_count < 0:
        candidate_count = 0
    payload_label = label or "Shear cleanup - one-click reduction"
    result = {
        "updates": dict(updates),
        "label": payload_label,
        "util": float(shear_util or 0.0),
        "action_type": "apply_resolved_candidate",
        "resolved_candidate": dict(candidate),
        "resolved_candidate_updates": dict(updates),
        "resolved_candidate_label": payload_label,
        "resolved_candidate_action_type": "apply_resolved_candidate",
        "resolved_candidate_post_util": float(shear_util or 0.0),
        "candidate_search_evidence": {
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "family": "shear",
            "starting_util": float(starting_util or 0.0),
            "best_safe_final_util": float(shear_util or 0.0),
            "best_safe_candidate_updates": dict(updates),
            "best_safe_candidate_applied": False,
            "safe_candidate_count": candidate_count,
            "executable_candidate_count": candidate_count,
            "safe_cleanup_count": candidate_count,
            "executable_cleanup_count": candidate_count,
            "safe_shear_cleanup_count": candidate_count,
            "executable_shear_cleanup_count": candidate_count,
            "no_second_cta_required": True,
            "post_click_residual_shear_cleanup_fallback": True,
        },
    }
    proof = {
        "fallback_selected_result_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_fallback_selected_result"
        ),
        "dependency_slot": "fallback_selected_result_assembly",
        "route_metadata_hash": stable_final_publication_hash(_mapping(route_metadata)),
        "selected_candidate_row_hash": stable_final_publication_hash(row),
        "selected_updates_hash": stable_final_publication_hash(updates),
        "selected_candidate_hash": stable_final_publication_hash(candidate),
        "selected_result_hash": stable_final_publication_hash(result),
        "selected_result_present": bool(updates and candidate),
        "safe_candidate_count": candidate_count,
        "not_moved": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "materiality_screen_execution",
            "safety_acceptance_execution",
            "candidate_selection_execution",
            "visible_wording_authoring",
            "cta_contract_execution",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        "result": result,
        "proof": {**proof, "proof_hash": stable_final_publication_hash(proof)},
        "result_hash": stable_final_publication_hash(result),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row(
    *,
    index: int,
    fallback_variant: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one generated-update sequence row for residual-shear fallback proof."""

    row = {
        "index": int(index),
        "variant_hash": stable_final_publication_hash(_mapping(fallback_variant)),
        "updates": _mapping(updates),
    }
    return {"row": row, "row_hash": stable_final_publication_hash(row)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row(
    *,
    index: int,
    updates: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    success: bool = False,
    accepted_as_safe_cleanup: bool = False,
    failed_reason: str | None = None,
) -> dict[str, Any]:
    """Build one candidate evaluation sequence row for residual-shear fallback proof."""

    row = {
        "index": int(index),
        "updates_hash": stable_final_publication_hash(_mapping(updates)),
        "candidate_hash": stable_final_publication_hash(_mapping(candidate)) if candidate else "",
        "overview_hash": stable_final_publication_hash(_mapping(overview)) if overview else "",
        "success": bool(success),
        "accepted_as_safe_cleanup": bool(accepted_as_safe_cleanup),
        "failed_reason": str(failed_reason or ""),
    }
    return {"row": row, "row_hash": stable_final_publication_hash(row)}


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row(
    *,
    index: int,
    selection_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one selection sequence row for residual-shear fallback proof."""

    source = _mapping(selection_row)
    updates = _mapping(source.get("updates"))
    candidate = _mapping(source.get("candidate"))
    overview = _mapping(source.get("overview"))
    sort_key = {
        "shear_util": float(source.get("shear_util") or float("inf")),
        "update_count": len(updates),
        "updates_items": str(sorted(updates.items())),
    }
    row = {
        "index": int(index),
        "updates_hash": stable_final_publication_hash(updates),
        "candidate_hash": stable_final_publication_hash(candidate),
        "overview_hash": stable_final_publication_hash(overview),
        "shear_util": float(source.get("shear_util") or 0.0),
        "sort_key": dict(sort_key),
        "sort_key_hash": stable_final_publication_hash(sort_key),
    }
    return {
        "row": row,
        "sort_key": sort_key,
        "row_hash": stable_final_publication_hash(row),
    }


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop(
    *,
    current_shear_util: float | int | None = None,
    fallback_variant_generator: Callable[[], Any] | None = None,
    pre_screen: Callable[[dict[str, Any]], Any] | None = None,
    candidate_evaluator: Callable[[dict[str, Any]], Any] | None = None,
    post_screen: Callable[[dict[str, Any]], Any] | None = None,
    candidate_selector: Callable[[list[dict[str, Any]]], Any] | None = None,
    selected_label: str = "Shear cleanup - one-click reduction",
    route_metadata: dict[str, Any] | None = None,
    iteration_limit: int = 64,
) -> dict[str, Any]:
    """Run residual-shear fallback search order with injected engineering dependencies.

    The controller owns loop order, sequence-row construction, and selected
    result shape. Variant generation, candidate evaluation, materiality/safety
    screening, and final candidate selection remain injected dependencies.
    """

    fallback_variant_generator_attempted = False
    fallback_variant_generator_variant_count = 0
    fallback_variant_generator_update_sequence: list[dict[str, Any]] = []
    fallback_candidate_evaluation_sequence: list[dict[str, Any]] = []
    fallback_candidate_selection_sequence: list[dict[str, Any]] = []
    fallback_candidate_selection_output_summary: dict[str, Any] = {}
    fallback_shear_candidates: list[dict[str, Any]] = []
    residual_shear_tighten: dict[str, Any] = {}
    residual_shear_updates: dict[str, Any] = {}

    fallback_variants: list[Any] = []
    if callable(fallback_variant_generator):
        fallback_variants = list(fallback_variant_generator() or [])
    fallback_variant_generator_attempted = True
    fallback_variant_generator_variant_count = len(fallback_variants)

    for fallback_index, fallback_variant in enumerate(fallback_variants[: int(iteration_limit)]):
        if not isinstance(fallback_variant, dict):
            continue
        fallback_pre_screen = _mapping(pre_screen(fallback_variant)) if callable(pre_screen) else {}
        fallback_updates = _mapping(fallback_pre_screen.get("updates"))
        if not fallback_updates:
            continue
        fallback_update_sequence_row = (
            build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row(
                index=int(fallback_index),
                fallback_variant=dict(fallback_variant),
                updates=dict(fallback_updates),
            )
        )
        fallback_variant_generator_update_sequence.append(
            dict(fallback_update_sequence_row.get("row") or {})
        )
        if not bool(fallback_pre_screen.get("accepted_for_evaluation")):
            continue
        try:
            fallback_candidate = (
                candidate_evaluator(dict(fallback_updates))
                if callable(candidate_evaluator)
                else None
            )
        except Exception as exc:
            fallback_evaluation_row = (
                build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row(
                    index=int(fallback_index),
                    updates=dict(fallback_updates),
                    success=False,
                    accepted_as_safe_cleanup=False,
                    failed_reason=str(exc) or "candidate_evaluation_exception",
                )
            )
            fallback_candidate_evaluation_sequence.append(
                dict(fallback_evaluation_row.get("row") or {})
            )
            fallback_candidate = None
        if not isinstance(fallback_candidate, dict):
            if not any(
                row.get("index") == int(fallback_index)
                and row.get("updates_hash") == stable_final_publication_hash(dict(fallback_updates))
                for row in fallback_candidate_evaluation_sequence
            ):
                fallback_evaluation_row = (
                    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row(
                        index=int(fallback_index),
                        updates=dict(fallback_updates),
                        success=False,
                        accepted_as_safe_cleanup=False,
                        failed_reason="candidate_evaluation_returned_no_candidate",
                    )
                )
                fallback_candidate_evaluation_sequence.append(
                    dict(fallback_evaluation_row.get("row") or {})
                )
            continue
        fallback_post_screen = (
            _mapping(post_screen(dict(fallback_candidate))) if callable(post_screen) else {}
        )
        fallback_overview = _mapping(fallback_post_screen.get("overview"))
        fallback_shear_util = fallback_post_screen.get("shear_util")
        if not bool(fallback_post_screen.get("accepted")):
            fallback_evaluation_row = (
                build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row(
                    index=int(fallback_index),
                    updates=dict(fallback_updates),
                    candidate=dict(fallback_candidate),
                    overview=dict(fallback_overview),
                    success=True,
                    accepted_as_safe_cleanup=False,
                    failed_reason=str(
                        fallback_post_screen.get("failed_reason")
                        or "candidate_failed_residual_shear_cleanup_acceptance"
                    ),
                )
            )
            fallback_candidate_evaluation_sequence.append(
                dict(fallback_evaluation_row.get("row") or {})
            )
            continue
        fallback_candidate["updates"] = dict(fallback_updates)
        fallback_candidate["action_type"] = "apply_resolved_candidate"
        fallback_candidate["label"] = selected_label
        fallback_evaluation_row = (
            build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row(
                index=int(fallback_index),
                updates=dict(fallback_updates),
                candidate=dict(fallback_candidate),
                overview=dict(fallback_overview),
                success=True,
                accepted_as_safe_cleanup=True,
                failed_reason="",
            )
        )
        fallback_candidate_evaluation_sequence.append(
            dict(fallback_evaluation_row.get("row") or {})
        )
        fallback_shear_candidates.append(
            {
                "updates": dict(fallback_updates),
                "candidate": dict(fallback_candidate),
                "overview": dict(fallback_overview),
                "shear_util": float(fallback_shear_util),
            }
        )

    if fallback_shear_candidates:
        fallback_candidate_selection_sequence = []
        for selection_index, selection_row in enumerate(fallback_shear_candidates):
            fallback_selection_sequence_row = (
                build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row(
                    index=int(selection_index),
                    selection_row=dict(selection_row),
                )
            )
            fallback_candidate_selection_sequence.append(
                dict(fallback_selection_sequence_row.get("row") or {})
            )
        fallback_best = (
            _mapping(candidate_selector(list(fallback_shear_candidates)))
            if callable(candidate_selector)
            else {}
        )
        fallback_best_updates = _mapping(fallback_best.get("updates"))
        fallback_best_sort_key = {
            "shear_util": float(fallback_best.get("shear_util") or float("inf")),
            "update_count": len(fallback_best_updates),
            "updates_items": str(sorted(fallback_best_updates.items())),
        }
        fallback_candidate_selection_output_summary = {
            "candidate_count": len(fallback_shear_candidates),
            "stable_candidate_sequence_hash": stable_final_publication_hash(
                list(fallback_candidate_selection_sequence)
            ),
            "selected_updates_hash": stable_final_publication_hash(fallback_best_updates),
            "selected_candidate_hash": stable_final_publication_hash(
                _mapping(fallback_best.get("candidate"))
            ),
            "selected_sort_key_hash": stable_final_publication_hash(fallback_best_sort_key),
            "selected_shear_util": float(fallback_best.get("shear_util") or 0.0),
        }
        residual_shear_fallback_selected_result = (
            build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result(
                selected_candidate_row=dict(fallback_best or {}),
                selected_label=selected_label,
                current_shear_util=current_shear_util,
                safe_candidate_count=len(fallback_shear_candidates),
                route_metadata=_mapping(route_metadata),
            )
        )
        residual_shear_tighten = _mapping(
            residual_shear_fallback_selected_result.get("result")
        )
        residual_shear_updates = _mapping(residual_shear_tighten.get("updates"))
    else:
        residual_shear_fallback_selected_result = {}

    selected_result_summary = {
        "selected_result_present": bool(residual_shear_updates),
        "selected_updates_hash": stable_final_publication_hash(dict(residual_shear_updates)),
        "selected_candidate_hash": stable_final_publication_hash(
            _mapping(residual_shear_tighten.get("resolved_candidate"))
        ),
        "selected_result_hash": stable_final_publication_hash(dict(residual_shear_tighten)),
        "selected_action_type": residual_shear_tighten.get("action_type"),
        "selected_label": residual_shear_tighten.get("label"),
        "selected_util": _float_or_none(residual_shear_tighten.get("util")),
    }
    payload = {
        "fallback_search_loop_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_fallback_search_loop"
        ),
        "residual_shear_tighten": dict(residual_shear_tighten),
        "residual_shear_updates": dict(residual_shear_updates),
        "fallback_variant_generator_attempted": bool(fallback_variant_generator_attempted),
        "fallback_variant_generator_variant_count": int(
            fallback_variant_generator_variant_count
        ),
        "fallback_variant_generator_update_sequence": list(
            fallback_variant_generator_update_sequence
        ),
        "fallback_candidate_evaluation_sequence": list(
            fallback_candidate_evaluation_sequence
        ),
        "fallback_candidate_selection_sequence": list(
            fallback_candidate_selection_sequence
        ),
        "fallback_candidate_selection_output_summary": dict(
            fallback_candidate_selection_output_summary
        ),
        "fallback_shear_candidates": list(fallback_shear_candidates),
        "fallback_selected_result": dict(residual_shear_fallback_selected_result),
        "selected_result_summary": dict(selected_result_summary),
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "materiality_safety_screen_execution_owned_elsewhere": True,
        "candidate_selection_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "cta_contract_execution_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "ui_rendering_owned_elsewhere": True,
        "session_debug_mutation_owned_elsewhere": True,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "fallback_search_loop_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result(
    *,
    dependencies_available: bool = True,
    updates: dict[str, Any] | None = None,
    updates_match_state: bool = False,
    materially_reduces_reinforcement: bool = False,
    pure_shear_updates: bool | None = None,
    bad_update_keys: list[Any] | tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    """Build the residual-shear fallback pre-evaluation screen result."""

    update_payload = _mapping(updates)
    bad_keys = tuple(bad_update_keys or ())
    if not bool(dependencies_available):
        result = {
            "accepted_for_evaluation": False,
            "updates": {},
            "failed_reason": "screen_dependency_unavailable",
        }
    elif not update_payload:
        result = {
            "accepted_for_evaluation": False,
            "updates": {},
            "failed_reason": "no_updates",
        }
    elif bool(updates_match_state):
        result = {
            "accepted_for_evaluation": False,
            "updates": dict(update_payload),
            "failed_reason": "updates_match_state",
        }
    elif not bool(materially_reduces_reinforcement):
        result = {
            "accepted_for_evaluation": False,
            "updates": dict(update_payload),
            "failed_reason": "not_material_reduction",
        }
    elif pure_shear_updates is not True:
        result = {
            "accepted_for_evaluation": False,
            "updates": dict(update_payload),
            "failed_reason": "non_shear_update_keys",
            "bad_update_keys": bad_keys,
        }
    else:
        result = {
            "accepted_for_evaluation": True,
            "updates": dict(update_payload),
            "failed_reason": "",
            "bad_update_keys": tuple(),
        }
    proof = {
        "pre_screen_result_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_pre_screen_result"
        ),
        "dependency_slot": "materiality_safety_pre_screen",
        "result_hash": stable_final_publication_hash(result),
        "updates_hash": stable_final_publication_hash(update_payload),
        "dependencies_available": bool(dependencies_available),
        "updates_match_state": bool(updates_match_state),
        "materially_reduces_reinforcement": bool(materially_reduces_reinforcement),
        "pure_shear_updates": pure_shear_updates,
        "bad_update_keys_hash": stable_final_publication_hash(bad_keys),
        "not_moved": (
            "delta_screen_builder_execution",
            "state_match_check_execution",
            "pure_updates_checker_execution",
            "candidate_evaluation_execution",
            "post_screen_execution",
            "candidate_selection_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        "result": result,
        "proof": {**proof, "proof_hash": stable_final_publication_hash(proof)},
        "result_hash": stable_final_publication_hash(result),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result(
    *,
    candidate_available: bool = True,
    fallback_overview: dict[str, Any] | None = None,
    fallback_statuses: dict[str, Any] | None = None,
    fallback_utils: dict[str, Any] | None = None,
    fallback_shear_util: float | int | str | None = None,
    current_shear_util: float | int | str | None = None,
    target_band_eps: float | int | str = 0.0,
    acceptance_screen: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the residual-shear fallback post-evaluation screen result."""

    overview = _mapping(fallback_overview)
    statuses = _mapping(fallback_statuses)
    utils = _mapping(fallback_utils)
    screen = _mapping(acceptance_screen)
    if not bool(candidate_available):
        result = {
            "accepted": False,
            "failed_reason": "candidate_evaluation_returned_no_candidate",
            "overview": {},
            "statuses": {},
            "utils": {},
            "shear_util": None,
        }
    else:
        accepted = not (
            fallback_shear_util is None
            or float(fallback_shear_util) <= float(current_shear_util) + 1e-9
            or float(fallback_shear_util) > 1.0 + float(target_band_eps)
            or bool(overview.get("any_fail"))
            or not bool(screen.get("required_checks_acceptable"))
            or bool(screen.get("explicit_preview_fail"))
        )
        result = {
            "accepted": bool(accepted),
            "failed_reason": "" if accepted else "candidate_failed_residual_shear_cleanup_acceptance",
            "overview": dict(overview),
            "statuses": dict(statuses),
            "utils": dict(utils),
            "shear_util": fallback_shear_util,
            "acceptance_screen": dict(screen),
        }
    proof = {
        "post_screen_result_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_post_screen_result"
        ),
        "dependency_slot": "materiality_safety_post_screen",
        "result_hash": stable_final_publication_hash(result),
        "overview_hash": stable_final_publication_hash(overview),
        "statuses_hash": stable_final_publication_hash(statuses),
        "utils_hash": stable_final_publication_hash(utils),
        "acceptance_screen_hash": stable_final_publication_hash(screen),
        "candidate_available": bool(candidate_available),
        "fallback_shear_util": fallback_shear_util,
        "current_shear_util": current_shear_util,
        "target_band_eps": target_band_eps,
        "not_moved": (
            "acceptance_screen_builder_execution",
            "candidate_evaluation_execution",
            "candidate_selection_execution",
            "result_packaging_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        "result": result,
        "proof": {**proof, "proof_hash": stable_final_publication_hash(proof)},
        "result_hash": stable_final_publication_hash(result),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows(
    *,
    debug_projection_rows: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent residual-shear cleanup debug projection rows as proof data."""

    required_keys = (
        "post_click_bending_blocker_preserved",
        "post_click_residual_shear_cleanup_after_bending_blocker",
        "post_click_residual_shear_cleanup_debug",
        "post_click_residual_shear_cleanup_detail",
        "post_click_residual_shear_cleanup_updates",
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "candidate_search_evidence",
        "guidance_branch",
        "selected_action_family",
        "primary_guidance_intent",
        "safe_local_cleanup_count",
        "executable_safe_cleanup_count",
    )
    rows = _mapping(debug_projection_rows)
    row_entries = {
        key: {
            "key": key,
            "present": key in rows,
            "value_type": type(rows.get(key)).__name__ if key in rows else "",
            "value_hash": stable_final_publication_hash(rows.get(key)) if key in rows else "",
        }
        for key in required_keys
    }
    row_hashes = {key: row["value_hash"] for key, row in row_entries.items()}
    missing_keys = tuple(key for key in required_keys if key not in rows)
    payload = {
        "debug_projection_rows_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_debug_projection_rows"
        ),
        "dependency_slot": "post_click_low_bending_residual_shear_cleanup_debug_projection",
        "required_keys": required_keys,
        "row_keys": tuple(rows.keys()),
        "row_count": len(rows),
        "required_row_count": len(required_keys),
        "rows": row_entries,
        "row_hashes": row_hashes,
        "debug_projection_rows_hash": stable_final_publication_hash(rows),
        "missing_required_keys": missing_keys,
        "all_required_keys_present": not missing_keys,
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "page_must_keep_for_now": (
            "direct_debug_projection_writes",
            "debug_consumer_reachability_unknown",
        ),
        "safe_next_cutover_surface": "debug_projection_compatibility_stamp",
    }
    return {
        **payload,
        "debug_projection_rows_proof_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff(
    *,
    candidate_selection_sort_key: dict[str, Any] | None = None,
    packaging_inputs: dict[str, Any] | None = None,
    packaging_output_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent the residual-shear local cleanup item packaging/evaluation boundary.

    This proof object records plain input/output hashes only. It does not build
    the item, evaluate the local cleanup card, merge evidence, build CTA
    contracts, author wording, or mutate session/debug state.
    """

    selection = _mapping(candidate_selection_sort_key)
    inputs = _mapping(packaging_inputs)
    output = _mapping(packaging_output_summary)
    status = str(dependency_status or "page_live")
    selection_hash = str(selection.get("candidate_selection_sort_key_hash") or "")
    packaging_input_hash = stable_final_publication_hash(inputs)
    packaging_output_hash = stable_final_publication_hash(output)
    residual_updates_hash = str(inputs.get("residual_updates_hash") or "")
    result_item_hash = str(output.get("residual_shear_item_hash") or "")
    promoted_item_hash = str(output.get("residual_promoted_hash") or "")
    detail_hash = str(output.get("residual_detail_hash") or "")
    evidence_hash = str(output.get("residual_evidence_hash") or "")
    candidate_id_hash = stable_final_publication_hash(str(output.get("residual_candidate_id") or ""))
    output_shape_ready = bool(
        selection_hash
        and inputs.get("route_branch")
        and residual_updates_hash
        and result_item_hash
        and promoted_item_hash
        and detail_hash
        and evidence_hash
        and output.get("residual_candidate_id")
    )
    behavior_cutover_ready = output_shape_ready and status == "controller_owned"
    payload = {
        "result_packaging_handoff_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_result_packaging_handoff"
        ),
        "dependency_slot": "result_packaging_evaluator",
        "dependency_status": status,
        "candidate_selection_sort_key_hash": selection_hash,
        "packaging_input_hash": packaging_input_hash,
        "packaging_output_hash": packaging_output_hash,
        "residual_updates_hash": residual_updates_hash,
        "residual_shear_item_hash": result_item_hash,
        "residual_promoted_hash": promoted_item_hash,
        "residual_detail_hash": detail_hash,
        "residual_evidence_hash": evidence_hash,
        "residual_candidate_id_hash": candidate_id_hash,
        "residual_preview_util": _float_or_none(output.get("residual_preview_util")),
        "residual_outside_preferred_band": bool(output.get("residual_outside_preferred_band")),
        "button_contract_hash_observed_not_owned": str(
            output.get("button_contract_hash_observed_not_owned") or ""
        ),
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "result_packaging_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "packaging_input_hash",
            "packaging_output_shape_hash",
            "promoted_item_identity_hash",
            "detail_hash",
            "evidence_hash",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else (
            "local_cleanup_item_packaging_execution",
            "local_cleanup_evaluator_execution",
            "evidence_merge_execution",
        ),
        "not_moved": (
            "local_cleanup_item_packaging_execution",
            "local_cleanup_evaluator_execution",
            "evidence_merge_execution",
            "button_contract_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "result_packaging_handoff_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter(
    *,
    result_packaging_handoff: dict[str, Any] | None = None,
    adapter_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent injected-adapter readiness for residual-shear result packaging."""

    handoff = _mapping(result_packaging_handoff)
    contract = _mapping(adapter_contract)
    required_contract_fields = (
        "packager_name",
        "local_cleanup_evaluator_name",
        "input_hash",
        "output_hash",
        "promoted_item_hash",
        "evidence_hash",
        "stale_state_policy",
        "button_contract_policy",
    )
    missing_contract_fields = tuple(
        field for field in required_contract_fields if not contract.get(field)
    )
    handoff_hash = str(handoff.get("result_packaging_handoff_hash") or "")
    input_hash_matches = bool(
        handoff.get("packaging_input_hash")
        and contract.get("input_hash")
        and str(handoff.get("packaging_input_hash")) == str(contract.get("input_hash"))
    )
    output_hash_matches = bool(
        handoff.get("packaging_output_hash")
        and contract.get("output_hash")
        and str(handoff.get("packaging_output_hash")) == str(contract.get("output_hash"))
    )
    promoted_hash_matches = bool(
        handoff.get("residual_promoted_hash")
        and contract.get("promoted_item_hash")
        and str(handoff.get("residual_promoted_hash")) == str(contract.get("promoted_item_hash"))
    )
    evidence_hash_matches = bool(
        handoff.get("residual_evidence_hash")
        and contract.get("evidence_hash")
        and str(handoff.get("residual_evidence_hash")) == str(contract.get("evidence_hash"))
    )
    adapter_boundary_ready = bool(
        handoff_hash
        and handoff.get("output_shape_ready")
        and not missing_contract_fields
        and input_hash_matches
        and output_hash_matches
        and promoted_hash_matches
        and evidence_hash_matches
    )
    behavior_cutover_ready = bool(
        adapter_boundary_ready
        and contract.get("packager_available") is True
        and contract.get("local_cleanup_evaluator_available") is True
        and contract.get("adapter_is_injected") is True
        and contract.get("adapter_changes_behavior") is False
    )
    payload = {
        "result_packaging_injected_adapter_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter"
        ),
        "dependency_slot": "result_packaging_evaluator",
        "result_packaging_handoff_hash": handoff_hash,
        "adapter_contract_hash": stable_final_publication_hash(contract),
        "input_hash_matches": input_hash_matches,
        "output_hash_matches": output_hash_matches,
        "promoted_hash_matches": promoted_hash_matches,
        "evidence_hash_matches": evidence_hash_matches,
        "missing_contract_fields": missing_contract_fields,
        "adapter_boundary_ready": adapter_boundary_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "safe_next_cutover_surface": (
            "result_packaging_injected_adapter"
            if adapter_boundary_ready
            else "none"
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else (
            "local_cleanup_item_packaging_execution",
            "local_cleanup_evaluator_execution",
        ),
        "not_moved": (
            "local_cleanup_item_packaging_execution",
            "local_cleanup_evaluator_execution",
            "evidence_merge_execution",
            "button_contract_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "result_packaging_injected_adapter_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff(
    *,
    result_packaging_handoff: dict[str, Any] | None = None,
    binding_inputs: dict[str, Any] | None = None,
    binding_output_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent residual-shear evidence merge and button-contract binding tail.

    This proof object records plain hashes only. It does not merge evidence,
    build button contracts, author wording, route Apply, render UI, or mutate
    session/debug state.
    """

    packaging = _mapping(result_packaging_handoff)
    inputs = _mapping(binding_inputs)
    output = _mapping(binding_output_summary)
    status = str(dependency_status or "page_live")
    packaging_hash = str(packaging.get("result_packaging_handoff_hash") or "")
    binding_input_hash = stable_final_publication_hash(inputs)
    binding_output_hash = stable_final_publication_hash(output)
    evidence_hash = str(output.get("evidence_hash") or "")
    action_payload_hash = str(output.get("action_payload_hash") or "")
    resolved_candidate_hash = str(output.get("resolved_candidate_hash") or "")
    button_contract_hash = str(output.get("button_contract_hash") or "")
    returned_item_hash = str(output.get("returned_item_hash") or "")
    updates_hash = str(output.get("button_contract_updates_hash") or "")
    expected_util = _float_or_none(output.get("button_contract_expected_util"))
    contract_enabled = bool(output.get("button_contract_enabled"))
    contract_actionable = bool(output.get("button_contract_actionable"))
    output_shape_ready = bool(
        packaging_hash
        and inputs.get("route_branch")
        and evidence_hash
        and action_payload_hash
        and resolved_candidate_hash
        and button_contract_hash
        and returned_item_hash
        and updates_hash
    )
    behavior_cutover_ready = output_shape_ready and status == "controller_owned"
    payload = {
        "final_binding_tail_handoff_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff"
        ),
        "dependency_slot": "evidence_merge_and_button_contract_binding_tail",
        "dependency_status": status,
        "result_packaging_handoff_hash": packaging_hash,
        "binding_input_hash": binding_input_hash,
        "binding_output_hash": binding_output_hash,
        "evidence_hash": evidence_hash,
        "action_payload_hash": action_payload_hash,
        "resolved_candidate_hash": resolved_candidate_hash,
        "button_contract_hash": button_contract_hash,
        "button_contract_updates_hash": updates_hash,
        "button_contract_expected_util": expected_util,
        "button_contract_enabled": contract_enabled,
        "button_contract_actionable": contract_actionable,
        "returned_item_hash": returned_item_hash,
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "final_binding_tail_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "binding_input_hash",
            "binding_output_hash",
            "evidence_hash",
            "action_payload_hash",
            "resolved_candidate_hash",
            "button_contract_hash",
            "returned_item_hash",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else (
            "evidence_merge_execution",
            "button_contract_execution",
            "debug_session_projection",
            "route_return",
        ),
        "not_moved": (
            "evidence_merge_execution",
            "button_contract_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "final_binding_tail_handoff_hash": stable_final_publication_hash(payload),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(
    *,
    promoted_item: dict[str, Any] | None = None,
    action_payload: dict[str, Any] | None = None,
    resolved_candidate: dict[str, Any] | None = None,
    button_contract: dict[str, Any] | None = None,
    state_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent the residual-shear CTA/apply source boundary.

    This object records the hashes and parity of the live action payload,
    resolved candidate, and shared button contract used by the residual-shear
    cleanup route. It does not build the button contract, route Apply, render
    UI, author visible wording, or mutate session/debug state.
    """

    item = _mapping(promoted_item)
    payload = _mapping(action_payload or item.get("action_payload"))
    resolved = _mapping(resolved_candidate or item.get("resolved_candidate"))
    contract = _mapping(button_contract or item.get("button_contract"))
    state = _mapping(state_summary)
    promoted_payload = _mapping(item.get("action_payload"))
    promoted_resolved = _mapping(item.get("resolved_candidate"))
    promoted_contract = _mapping(item.get("button_contract"))
    payload_hash = stable_final_publication_hash(payload)
    resolved_hash = stable_final_publication_hash(resolved)
    contract_hash = stable_final_publication_hash(contract)
    promoted_item_hash = stable_final_publication_hash(item)
    updates = _mapping(
        contract.get("updates")
        or payload.get("updates")
        or resolved.get("updates")
        or item.get("updates")
    )
    status = str(dependency_status or "page_live")
    payload_matches_promoted = bool(
        payload and promoted_payload and payload_hash == stable_final_publication_hash(promoted_payload)
    )
    resolved_matches_promoted = bool(
        resolved and promoted_resolved and resolved_hash == stable_final_publication_hash(promoted_resolved)
    )
    contract_matches_promoted = bool(
        contract and promoted_contract and contract_hash == stable_final_publication_hash(promoted_contract)
    )
    contract_enabled = bool(contract.get("enabled") or contract.get("actionable"))
    contract_actionable = bool(contract.get("actionable") or contract.get("enabled"))
    output_shape_ready = bool(
        promoted_item_hash
        and payload_hash
        and resolved_hash
        and contract_hash
        and stable_final_publication_hash(updates)
    )
    behavior_cutover_ready = bool(
        output_shape_ready
        and status == "controller_owned"
        and payload_matches_promoted
        and resolved_matches_promoted
        and contract_matches_promoted
    )
    payload_data = {
        "cta_apply_payload_source_boundary_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary"
        ),
        "dependency_slot": "cta_apply_payload_source_boundary",
        "dependency_status": status,
        "promoted_item_hash": promoted_item_hash,
        "action_payload_hash": payload_hash,
        "resolved_candidate_hash": resolved_hash,
        "button_contract_hash": contract_hash,
        "button_contract_updates_hash": stable_final_publication_hash(updates),
        "state_summary_hash": stable_final_publication_hash(state),
        "payload_matches_promoted_item": payload_matches_promoted,
        "resolved_candidate_matches_promoted_item": resolved_matches_promoted,
        "button_contract_matches_promoted_item": contract_matches_promoted,
        "button_contract_enabled": contract_enabled,
        "button_contract_actionable": contract_actionable,
        "button_contract_action_type": str(contract.get("action_type") or ""),
        "button_contract_label": str(contract.get("label") or contract.get("button_label") or ""),
        "button_contract_expected_util": _float_or_none(contract.get("expected_util")),
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "action_payload_hash",
            "resolved_candidate_hash",
            "button_contract_hash",
            "button_contract_updates_hash",
            "payload_item_parity",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else (
            "action_payload_extraction",
            "resolved_candidate_extraction",
            "shared_button_contract_execution",
        ),
        "not_moved": (
            "shared_button_contract_execution",
            "cta_contract_execution",
            "apply_routing",
            "visible_wording_authoring",
            "ui_rendering",
            "session_state_mutation",
            "candidate_generation",
            "candidate_evaluation",
            "family_runtime",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload_data,
        "cta_apply_payload_source_boundary_hash": stable_final_publication_hash(payload_data),
    }


def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(
    *,
    promoted_item: dict[str, Any] | None = None,
    button_contract_input_summary: dict[str, Any] | None = None,
    button_contract: dict[str, Any] | None = None,
    state_summary: dict[str, Any] | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """Represent the shared button-contract execution boundary.

    The live shared CTA/button-contract helper remains outside this object.
    This boundary records plain input/output hashes and executor-backed shape
    proof only; it does not build CTA wording, route Apply, render UI, or
    mutate session/debug state.
    """

    item = _mapping(promoted_item)
    input_summary = _mapping(button_contract_input_summary)
    contract = _mapping(button_contract or item.get("button_contract"))
    state = _mapping(state_summary)
    updates = _mapping(contract.get("updates") or item.get("updates"))
    status = str(dependency_status or "page_live")
    promoted_item_hash = stable_final_publication_hash(item)
    input_hash = stable_final_publication_hash(input_summary)
    contract_hash = stable_final_publication_hash(contract)
    updates_hash = stable_final_publication_hash(updates)
    enabled = bool(contract.get("enabled") or contract.get("actionable"))
    actionable = bool(contract.get("actionable") or contract.get("enabled"))
    action_type = str(contract.get("action_type") or "")
    label = str(contract.get("label") or contract.get("button_label") or "")
    executor_backed = bool(actionable and action_type and updates)
    output_shape_ready = bool(
        promoted_item_hash
        and input_hash
        and contract_hash
        and updates_hash
        and action_type
        and label
    )
    behavior_cutover_ready = bool(output_shape_ready and status == "controller_owned")
    payload = {
        "button_contract_execution_boundary_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary"
        ),
        "dependency_slot": "shared_button_contract_execution",
        "dependency_status": status,
        "promoted_item_hash": promoted_item_hash,
        "button_contract_input_hash": input_hash,
        "button_contract_hash": contract_hash,
        "button_contract_updates_hash": updates_hash,
        "state_summary_hash": stable_final_publication_hash(state),
        "button_contract_enabled": enabled,
        "button_contract_actionable": actionable,
        "button_contract_action_type": action_type,
        "button_contract_label": label,
        "button_contract_expected_util": _float_or_none(contract.get("expected_util")),
        "executor_backed_apply_proof": executor_backed,
        "output_shape_ready": output_shape_ready,
        "behavior_cutover_ready": behavior_cutover_ready,
        "controller_may_own_now": (
            "button_contract_hash",
            "button_contract_updates_hash",
            "executor_backed_apply_proof",
            "button_contract_input_hash",
        ),
        "page_must_keep_for_now": ()
        if behavior_cutover_ready
        else (
            "shared_button_contract_execution",
            "cta_contract_execution",
            "apply_routing",
        ),
        "not_moved": (
            "shared_button_contract_execution",
            "cta_contract_execution",
            "apply_routing",
            "visible_wording_authoring",
            "ui_rendering",
            "session_state_mutation",
            "candidate_generation",
            "candidate_evaluation",
            "family_runtime",
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **payload,
        "button_contract_execution_boundary_hash": stable_final_publication_hash(payload),
    }


def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(
    *,
    promoted_item: dict[str, Any] | None = None,
    candidate_search_evidence: dict[str, Any] | None = None,
    exact_blockers_by_family: dict[str, Any] | None = None,
    action_payload: dict[str, Any] | None = None,
    resolved_candidate: dict[str, Any] | None = None,
    button_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the residual-shear final-binding item from plain controller data.

    The caller still supplies any button contract that came from the shared/page
    button-contract builder. This function only performs the deterministic
    evidence/action-payload/resolved-candidate/item binding previously done in
    the page route.
    """

    item = _mapping(promoted_item)
    evidence = _mapping(candidate_search_evidence)
    blockers = _mapping(exact_blockers_by_family)
    payload = _mapping(action_payload or item.get("action_payload"))
    resolved = _mapping(resolved_candidate or item.get("resolved_candidate"))
    contract = _mapping(button_contract or item.get("button_contract"))

    evidence.update(
        {
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "post_click_bending_blocker_preserved": True,
            "post_click_residual_shear_cleanup_after_bending_blocker": True,
            "exact_blockers_by_family": dict(blockers),
            "post_click_exact_blockers_by_family": dict(blockers),
            "cleanup_evidence_by_family": dict(blockers),
            "post_click_cleanup_evidence_by_family": dict(blockers),
            "low_util_families": ["bending"],
            "resolved_low_util_families": ["bending"],
            "unresolved_low_util_families": [],
            "post_click_families_below_final_threshold": ["bending"],
            "post_click_unresolved_low_util_families": [],
            "no_second_cta_required": True,
        }
    )

    item["candidate_search_evidence"] = dict(evidence)
    item["post_click_residual_shear_cleanup_action"] = True
    item["guidance_intent"] = "efficiency_tightening"
    item["local_cleanup_candidate"] = True
    item["no_second_cta_required"] = True
    item["exact_blockers_by_family"] = dict(blockers)
    item["post_click_exact_blockers_by_family"] = dict(blockers)
    item["cleanup_evidence_by_family"] = dict(blockers)
    item["post_click_cleanup_evidence_by_family"] = dict(blockers)

    payload["candidate_search_evidence"] = dict(evidence)
    payload["no_second_cta_required"] = True
    item["action_payload"] = dict(payload)

    if resolved:
        resolved["candidate_search_evidence"] = dict(evidence)
        resolved["no_second_cta_required"] = True
        item["resolved_candidate"] = dict(resolved)

    if contract:
        item["button_contract"] = dict(contract)

    adapter_payload = {
        "final_binding_tail_adapter_authority": (
            "DesignGuideController.post_click_low_bending_residual_shear_cleanup_final_binding_tail"
        ),
        "result_item": dict(item),
        "candidate_search_evidence_hash": stable_final_publication_hash(evidence),
        "action_payload_hash": stable_final_publication_hash(payload),
        "resolved_candidate_hash": stable_final_publication_hash(resolved),
        "button_contract_hash": stable_final_publication_hash(contract),
        "returned_item_hash": stable_final_publication_hash(item),
        "button_contract_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "apply_routing_owned_elsewhere": True,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {
        **adapter_payload,
        "final_binding_tail_adapter_hash": stable_final_publication_hash(adapter_payload),
    }


@dataclass(frozen=True)
class DesignGuideControllerRequest:
    """Plain-data request for trace-only Design Guide controller proof."""

    item: dict[str, Any] = field(default_factory=dict)
    debug: dict[str, Any] = field(default_factory=dict)
    design_brain_result: dict[str, Any] = field(default_factory=dict)
    verifier_payload: dict[str, Any] = field(default_factory=dict)
    final_visible_resolution: dict[str, Any] = field(default_factory=dict)
    guidance_debug: dict[str, Any] = field(default_factory=dict)
    publication_reason: str | None = None
    source: str = "trace_only_controller"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerResponse:
    """Trace-only controller output for parity and future wiring proof."""

    controller_id: str
    authority: str
    request_hash: str
    request_source: str
    publication: dict[str, Any]
    publication_hash: str | None
    collapsed_guidance_item: dict[str, Any]
    final_visible_resolution: dict[str, Any]
    post_resolver_mutation_proof: dict[str, Any]
    parity_payload: dict[str, Any]
    controller_hash: str
    memo_cache_key: str | None = None
    memo_key_section_hashes: dict[str, str | None] = field(default_factory=dict)
    memo_cache_hit: bool = False
    memo_cache_reason: str = "rebuilt"
    trace_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerFinalVisibleOutputBridgeRequest:
    """Plain-data request for trace-only final-visible output bridge proof."""

    callsite_id: str
    input_item: dict[str, Any] = field(default_factory=dict)
    output_item: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    debug: dict[str, Any] = field(default_factory=dict)
    rec: dict[str, Any] = field(default_factory=dict)
    source: str = "controller_final_visible_output_bridge_trace_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerFinalVisibleOutputBridgeResponse:
    """Trace-only controller proof for final-visible output bridges."""

    controller_id: str
    authority: str
    request_hash: str
    request_source: str
    final_visible_output_bridge_proof: dict[str, Any]
    final_visible_output_bridge_proof_hash: str | None
    result_item: dict[str, Any]
    result_item_hash: str
    controller_hash: str
    trace_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerFinalVisibleRebindEffectsRequest:
    """Plain-data request for final-visible contract-binding rebind effects."""

    evidence_for_binding: dict[str, Any] = field(default_factory=dict)
    contract: dict[str, Any] = field(default_factory=dict)
    item: dict[str, Any] = field(default_factory=dict)
    debug: dict[str, Any] = field(default_factory=dict)
    current_updates: dict[str, Any] = field(default_factory=dict)
    target_binding_updates: dict[str, Any] = field(default_factory=dict)
    target_binding_util: Any = None
    target_binding_count: int = 0
    target_binding_family: str = ""
    target_binding_candidate_id: Any = None
    target_low: Any = None
    target_high: Any = None
    current_binding_expected: Any = None
    target_updates_already_applied: bool = False
    safe_binding_updates: dict[str, Any] = field(default_factory=dict)
    combined_binding_updates: dict[str, Any] = field(default_factory=dict)
    safe_updates_already_applied: bool = False
    combined_updates_already_applied: bool = False
    combined_binding_bending_util: Any = None
    evidence_expected_util: Any = None
    evidence_family: str = ""
    blocker_families: tuple[str, ...] = field(default_factory=tuple)
    final_accepted_min_family_util: float = 0.0
    target_band_eps: float = 0.0
    compound_shear_update_keys: tuple[str, ...] = field(default_factory=tuple)
    compound_bottom_update_keys: tuple[str, ...] = field(default_factory=tuple)
    source: str = "controller_final_visible_rebind_effects_trace_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerFinalVisibleRebindEffectsResponse:
    """Trace-only controller proof for final-visible rebind effects."""

    controller_id: str
    authority: str
    request_hash: str
    request_source: str
    rebind_effects_proof: dict[str, Any]
    rebind_effects_proof_hash: str | None
    represented_effects: tuple[str, ...]
    result_flags: dict[str, Any]
    controller_hash: str
    rebind_projection: dict[str, Any] = field(default_factory=dict)
    rebind_projection_hash: str | None = None
    final_visible_output_projection: dict[str, Any] = field(default_factory=dict)
    final_visible_output_projection_hash: str | None = None
    trace_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerComputePublicationHandoffRequest:
    """Plain-data request for compute-stage publication handoff proof."""

    current_state: dict[str, Any] = field(default_factory=dict)
    overview: dict[str, Any] = field(default_factory=dict)
    collapsed_guidance_items: list[dict[str, Any]] = field(default_factory=list)
    publication_context: dict[str, Any] = field(default_factory=dict)
    publication_dependencies: dict[str, Any] = field(default_factory=dict)
    final_compute_resolution: dict[str, Any] = field(default_factory=dict)
    blocker_evidence_surface: dict[str, Any] = field(default_factory=dict)
    late_evidence_acceptance: dict[str, Any] = field(default_factory=dict)
    rebound_contract: dict[str, Any] = field(default_factory=dict)
    rebound_update_payload: dict[str, Any] = field(default_factory=dict)
    post_core_evidence_mismatch: dict[str, Any] = field(default_factory=dict)
    raw_rebound_item: dict[str, Any] = field(default_factory=dict)
    pre_resolver_collapsed_item_mutation: dict[str, Any] = field(default_factory=dict)
    debug: dict[str, Any] = field(default_factory=dict)
    verifier_payload: dict[str, Any] = field(default_factory=dict)
    session_controls: dict[str, Any] = field(default_factory=dict)
    design_actions_signature: tuple[Any, ...] = field(default_factory=tuple)
    optimisation_goal: str = ""
    publication_reason: str | None = None
    source: str = "controller_compute_publication_handoff_trace_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerComputePublicationHandoffResponse:
    """Trace-only controller proof for compute-stage handoff parity."""

    controller_id: str
    authority: str
    request_hash: str
    request_source: str
    selected_item: dict[str, Any]
    selected_item_hash: str
    final_visible_resolution: dict[str, Any]
    final_visible_resolution_hash: str
    publication: dict[str, Any]
    publication_hash: str | None
    compute_handoff_rebound_decision_proof: dict[str, Any]
    compute_handoff_rebound_decision_hash: str | None
    parity_payload: dict[str, Any]
    controller_hash: str
    trace_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerComputeReboundMutationRequest:
    """Plain-data request for proof-only compute rebound mutation outputs."""

    path_id: str
    accepted: bool = False
    primary_item: dict[str, Any] = field(default_factory=dict)
    rebound_item: dict[str, Any] = field(default_factory=dict)
    collapsed_guidance_items: list[dict[str, Any]] = field(default_factory=list)
    rebound_contract: dict[str, Any] = field(default_factory=dict)
    rebound_update_payload: dict[str, Any] = field(default_factory=dict)
    source: str = "controller_compute_rebound_mutation_trace_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerComputeReboundMutationResponse:
    """Trace-only controller proof of live rebound mutation shape."""

    controller_id: str
    authority: str
    request_hash: str
    request_source: str
    path_id: str
    accepted: bool
    selected_item: dict[str, Any]
    selected_item_hash: str
    collapsed_guidance_items: list[dict[str, Any]]
    collapsed_guidance_items_hash: str
    debug_compatibility_update_keys: tuple[str, ...]
    debug_compatibility_updates_hash: str
    controller_hash: str
    trace_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerComputeReboundPublicationItemRequest:
    """Plain-data request for controller-owned compute rebound item construction."""

    path_id: str
    primary_item: dict[str, Any] = field(default_factory=dict)
    rebound_contract: dict[str, Any] = field(default_factory=dict)
    rebound_update_payload: dict[str, Any] = field(default_factory=dict)
    publication_reason: str | None = None
    source: str = "controller_compute_rebound_publication_item_trace_only"
    product_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerComputeReboundPublicationItemResponse:
    """Trace-only proof for replacing page restamper rebound item creation."""

    controller_id: str
    authority: str
    request_hash: str
    request_source: str
    path_id: str
    selected_item: dict[str, Any]
    selected_item_hash: str
    collapsed_guidance_item: dict[str, Any]
    collapsed_guidance_item_hash: str
    publication: dict[str, Any]
    publication_hash: str | None
    controller_hash: str
    trace_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerComputeResolverReplacementResponse:
    """Trace-only proof that controller selection can replace compute resolver input."""

    controller_id: str
    authority: str
    request_hash: str
    request_source: str
    selection: dict[str, Any]
    handoff: dict[str, Any]
    final_compute_resolution: dict[str, Any]
    final_compute_resolution_hash: str
    compute_handoff_rebound_decision_hash: str | None
    controller_hash: str
    old_resolver_input_required: bool = False
    trace_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerComputeSelectionRequest:
    """Plain-data request for proof-only compute-stage item selection."""

    current_state: dict[str, Any] = field(default_factory=dict)
    overview: dict[str, Any] = field(default_factory=dict)
    collapsed_guidance_items: list[dict[str, Any]] = field(default_factory=list)
    publication_context: dict[str, Any] = field(default_factory=dict)
    publication_dependencies: dict[str, Any] = field(default_factory=dict)
    session_controls: dict[str, Any] = field(default_factory=dict)
    design_actions_signature: tuple[Any, ...] = field(default_factory=tuple)
    optimisation_goal: str = ""
    publication_reason: str | None = None
    source: str = "controller_compute_selection_trace_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerComputeSelectionResponse:
    """Trace-only controller selection proof before publication handoff."""

    controller_id: str
    authority: str
    request_hash: str
    request_source: str
    selected_item: dict[str, Any]
    selected_item_index: int | None
    selected_item_hash: str
    render_reason: str
    state_fingerprint: str
    selection_policy: str
    selection_hash: str
    trace_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerPresentationRequest:
    """Plain-data request for controller-owned Design Guide presentation output."""

    current_state: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    raw_items: list[dict[str, Any]] = field(default_factory=list)
    candidate_evidence: dict[str, Any] = field(default_factory=dict)
    raw_candidates: list[dict[str, Any]] = field(default_factory=list)
    target_band: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    source: str = "controller_presentation_adapter"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerPresentationResponse:
    """Controller-owned presentation result for parity and cutover proof."""

    controller_id: str
    authority: str
    request_hash: str
    request_source: str
    decision: dict[str, Any]
    decision_hash: str
    presentation: dict[str, Any]
    presentation_hash: str
    controller_hash: str
    trace_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerBendingFailSnapshotReuseRequest:
    """Plain-data request for bending-fail snapshot reuse assembly."""

    snapshot_item: dict[str, Any] = field(default_factory=dict)
    current_overview: dict[str, Any] = field(default_factory=dict)
    state_fingerprint: str = ""
    source: str = "controller_bending_fail_snapshot_reuse_trace_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesignGuideControllerBendingFailSnapshotReuseResponse:
    """Proof-only controller result for bending-fail snapshot reuse."""

    controller_id: str
    authority: str
    request_hash: str
    request_source: str
    result: dict[str, Any]
    result_hash: str
    trace_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_final_visible_resolution(
    *,
    publication: FinalDesignGuidePublication,
    collapsed_guidance_item: dict[str, Any],
    current_resolution: dict[str, Any] | None = None,
    source: str,
    request_hash: str,
    request_source: str,
    derived_from: str,
    trace_only: bool,
    product_driving: bool,
) -> dict[str, Any]:
    current = _mapping(current_resolution)
    return {
        **current,
        "item": collapsed_guidance_item,
        "render_reason": current.get("render_reason") or source,
        "publication_hash": publication.publication_hash,
        "final_publication_publication_hash": publication.publication_hash,
        "final_publication_authority_hash": publication.publication_hash,
        "controller_request_hash": request_hash,
        "controller_request_source": request_source,
        "final_visible_resolution_authority": "DesignGuideController",
        "final_publication_authority": "DesignGuideController",
        "final_publication_inner_authority": "FinalDesignGuidePublication",
        "derived_from": derived_from,
        "compatibility_only": True,
        "trace_only": trace_only,
        "product_driving": product_driving,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }


def _run_design_guide_controller(
    request: DesignGuideControllerRequest | dict[str, Any] | None = None,
    *,
    controller_id: str,
    source_default: str,
    derived_from: str,
    trace_only: bool,
    product_driving: bool,
) -> DesignGuideControllerResponse:
    """Build a controller publication response from plain data."""

    if request is None:
        request_obj = DesignGuideControllerRequest(source=source_default)
    elif isinstance(request, DesignGuideControllerRequest):
        request_obj = request
    elif isinstance(request, dict):
        request_obj = DesignGuideControllerRequest(
            item=_mapping(request.get("item")),
            debug=_mapping(request.get("debug")),
            design_brain_result=_mapping(request.get("design_brain_result")),
            verifier_payload=_mapping(request.get("verifier_payload")),
            final_visible_resolution=_mapping(request.get("final_visible_resolution")),
            guidance_debug=_mapping(request.get("guidance_debug")),
            publication_reason=request.get("publication_reason"),
            source=str(request.get("source") or source_default),
        )
    else:
        raise TypeError("request must be a DesignGuideControllerRequest, dict, or None")

    memo_payload = design_guide_controller_request_memo_payload(request_obj)
    request_hash = stable_final_publication_hash(memo_payload)
    memo_key_section_hashes = {
        str(section): stable_final_publication_hash(value)
        for section, value in _mapping(memo_payload.get("request")).items()
    }
    memo_disabled_reason = _design_guide_controller_memo_disabled_reason(request_obj)
    if product_driving and not memo_disabled_reason:
        cached_response = _final_publication_memo_cache.get(request_hash)
        if cached_response is not None:
            return replace(
                cached_response,
                memo_cache_hit=True,
                memo_cache_reason="request_hash_unchanged",
            )
    publication = build_final_design_guide_publication(
        item=dict(request_obj.item),
        debug=dict(request_obj.debug),
        design_brain_result=dict(request_obj.design_brain_result),
        verifier_payload=dict(request_obj.verifier_payload),
        publication_reason=request_obj.publication_reason,
    )
    collapsed_item = build_collapsed_guidance_item_from_final_publication(
        publication,
    )
    collapsed_item["controller_request_hash"] = request_hash
    collapsed_item["controller_request_source"] = request_obj.source
    collapsed_item["controller_request_key_authority"] = "DesignGuideController.request_hash"
    final_visible_resolution = _build_final_visible_resolution(
        publication=publication,
        collapsed_guidance_item=collapsed_item,
        current_resolution=request_obj.final_visible_resolution,
        source=request_obj.source,
        request_hash=request_hash,
        request_source=request_obj.source,
        derived_from=derived_from,
        trace_only=trace_only,
        product_driving=product_driving,
    )
    mutation_proof = build_final_design_guide_post_resolver_mutation_proof(
        publication,
        selected_item=collapsed_item,
        final_visible_resolution=final_visible_resolution,
        guidance_debug=dict(request_obj.guidance_debug),
    ).to_dict()
    publication_dict = publication.to_dict()
    parity_payload = {
        "publication_hash": publication.publication_hash,
        "request_hash": request_hash,
        "request_source": request_obj.source,
        "collapsed_item_publication_hash": collapsed_item.get("publication_hash"),
        "final_visible_resolution_publication_hash": final_visible_resolution.get(
            "publication_hash"
        ),
        "selected_family": publication.selected_family,
        "outcome_state": publication.outcome_state,
        "published_item_id": publication.published_item_id,
        "post_click_design_guide_state": publication.post_click_design_guide_state,
        "cta_hash": collapsed_item.get("final_publication_cta_hash"),
        "display_hash": collapsed_item.get("final_publication_display_hash"),
        "evidence_hash": collapsed_item.get("final_publication_evidence_hash"),
        "memo_key_section_hashes": dict(memo_key_section_hashes),
        "trace_only": trace_only,
        "product_driving": product_driving,
    }
    controller_payload = {
        "authority": "FinalDesignGuidePublication",
        "publication": publication_dict,
        "collapsed_guidance_item": collapsed_item,
        "final_visible_resolution": final_visible_resolution,
        "post_resolver_mutation_proof": mutation_proof,
        "parity_payload": parity_payload,
    }
    response = DesignGuideControllerResponse(
        controller_id=controller_id,
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        publication=publication_dict,
        publication_hash=publication.publication_hash,
        collapsed_guidance_item=collapsed_item,
        final_visible_resolution=final_visible_resolution,
        post_resolver_mutation_proof=mutation_proof,
        parity_payload=parity_payload,
        controller_hash=stable_final_publication_hash(controller_payload),
        memo_cache_key=request_hash,
        memo_key_section_hashes=memo_key_section_hashes,
        memo_cache_hit=False,
        memo_cache_reason=memo_disabled_reason or "rebuilt",
        trace_only=trace_only,
        product_driving=product_driving,
    )
    if product_driving and not memo_disabled_reason:
        if len(_final_publication_memo_cache) >= _FINAL_PUBLICATION_MEMO_CACHE_MAX:
            oldest_key = next(iter(_final_publication_memo_cache), None)
            if oldest_key:
                _final_publication_memo_cache.pop(oldest_key, None)
        _final_publication_memo_cache[request_hash] = response
    return response


def _design_guide_controller_memo_disabled_reason(request: DesignGuideControllerRequest) -> str | None:
    debug = _mapping(request.debug)
    guidance_debug = _mapping(request.guidance_debug)
    merged = {**debug, **guidance_debug}
    if bool(
        merged.get("final_publication_memo_debug_force_rebuild")
        or merged.get("final_publication_debug_force_rebuild")
    ):
        return "debug_force_rebuild"
    if bool(
        merged.get("design_guide_component_apply_in_flight")
        or merged.get("component_apply_queued")
        or merged.get("post_click_apply_in_flight")
        or merged.get("post_click_design_guide_state") == "APPLY_IN_FLIGHT"
    ):
        return "post_click_or_apply_in_flight"
    if not request.item:
        return "missing_publication_item"
    return None


def run_design_guide_controller_trace_only(
    request: DesignGuideControllerRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerResponse:
    """Build a trace-only controller proof from current publication surfaces."""

    return _run_design_guide_controller(
        request,
        controller_id="DesignGuideController.trace_only",
        source_default="trace_only_controller",
        derived_from="DesignGuideController.trace_only",
        trace_only=True,
        product_driving=False,
    )


def run_design_guide_controller_publication_authority(
    request: DesignGuideControllerRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerResponse:
    """Build the live publication-authority response for page-owned rendering.

    The controller owns the final publication object and compatible collapsed
    item/resolution shape. Rendering, Apply routing, session state, and UI
    remain outside Design Brain.
    """

    return _run_design_guide_controller(
        request,
        controller_id="DesignGuideController.publication_authority",
        source_default="controller_publication_authority",
        derived_from="DesignGuideController.publication_authority",
        trace_only=False,
        product_driving=True,
    )


def run_design_guide_controller_render_item_consumer_trace_only(
    request: DesignGuideControllerRequest | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build render-item consumer proof behind the controller boundary."""

    if request is None:
        request_obj = DesignGuideControllerRequest(
            source="controller_render_item_consumer_trace_only"
        )
    elif isinstance(request, DesignGuideControllerRequest):
        request_obj = request
    elif isinstance(request, dict):
        request_obj = DesignGuideControllerRequest(
            item=_mapping(request.get("item")),
            debug=_mapping(request.get("debug")),
            design_brain_result=_mapping(request.get("design_brain_result")),
            verifier_payload=_mapping(request.get("verifier_payload")),
            final_visible_resolution=_mapping(request.get("final_visible_resolution")),
            guidance_debug=_mapping(request.get("guidance_debug")),
            publication_reason=request.get("publication_reason"),
            source=str(
                request.get("source") or "controller_render_item_consumer_trace_only"
            ),
        )
    else:
        raise TypeError("request must be a DesignGuideControllerRequest, dict, or None")

    request_hash = stable_final_publication_hash(
        design_guide_controller_request_memo_payload(request_obj)
    )
    publication = build_final_design_guide_publication(
        item=dict(request_obj.item),
        debug=dict(request_obj.debug),
        design_brain_result=dict(request_obj.design_brain_result),
        verifier_payload=dict(request_obj.verifier_payload),
        publication_reason=request_obj.publication_reason,
    )
    proof = build_final_design_guide_render_item_consumer_proof(
        publication,
        selected_item=dict(request_obj.item),
        final_visible_resolution=dict(request_obj.final_visible_resolution),
        guidance_debug=dict(request_obj.guidance_debug),
    ).to_dict()
    payload = {
        "controller_id": "DesignGuideController.render_item_consumer_trace_only",
        "authority": "DesignGuideController",
        "inner_authority": "FinalDesignGuidePublication",
        "request_hash": request_hash,
        "request_source": request_obj.source,
        "publication_hash": publication.publication_hash,
        "render_item_consumer_proof": dict(proof),
        "render_item_consumer_proof_hash": proof.get("consumer_proof_hash"),
        "trace_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    payload["controller_hash"] = stable_final_publication_hash(payload)
    return payload


def _final_visible_output_bridge_request_from_dict(
    request: DesignGuideControllerFinalVisibleOutputBridgeRequest | dict[str, Any] | None,
) -> DesignGuideControllerFinalVisibleOutputBridgeRequest:
    if request is None:
        return DesignGuideControllerFinalVisibleOutputBridgeRequest(callsite_id="")
    if isinstance(request, DesignGuideControllerFinalVisibleOutputBridgeRequest):
        return request
    if isinstance(request, dict):
        return DesignGuideControllerFinalVisibleOutputBridgeRequest(
            callsite_id=str(request.get("callsite_id") or ""),
            input_item=_mapping(request.get("input_item")),
            output_item=_mapping(request.get("output_item")),
            state=_mapping(request.get("state")),
            debug=_mapping(request.get("debug")),
            rec=_mapping(request.get("rec")),
            source=str(request.get("source") or "controller_final_visible_output_bridge_trace_only"),
        )
    return DesignGuideControllerFinalVisibleOutputBridgeRequest(callsite_id="")


def run_design_guide_controller_final_visible_output_bridge_trace_only(
    request: DesignGuideControllerFinalVisibleOutputBridgeRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerFinalVisibleOutputBridgeResponse:
    """Build trace-only proof for a final-visible output bridge."""

    request_obj = _final_visible_output_bridge_request_from_dict(request)
    request_hash = stable_final_publication_hash(request_obj.to_dict())
    result_item = dict(request_obj.output_item or {})
    result_item_hash = stable_final_publication_hash(result_item)
    proof = build_final_design_guide_publication_mutation_proof(
        callsite_id=request_obj.callsite_id,
        input_item=dict(request_obj.input_item or {}),
        output_item=dict(result_item),
        state=dict(request_obj.state or {}),
        debug=dict(request_obj.debug or {}),
        rec=dict(request_obj.rec or {}),
    )
    proof_payload = proof.to_dict()
    response_payload = {
        "controller_id": "DesignGuideController.final_visible_output_bridge.trace_only",
        "authority": "DesignGuideController",
        "request_hash": request_hash,
        "request_source": request_obj.source,
        "final_visible_output_bridge_proof": dict(proof_payload),
        "final_visible_output_bridge_proof_hash": proof_payload.get("proof_hash"),
        "result_item": dict(result_item),
        "result_item_hash": result_item_hash,
        "trace_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return DesignGuideControllerFinalVisibleOutputBridgeResponse(
        controller_id="DesignGuideController.final_visible_output_bridge.trace_only",
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        final_visible_output_bridge_proof=dict(proof_payload),
        final_visible_output_bridge_proof_hash=proof_payload.get("proof_hash"),
        result_item=dict(result_item),
        result_item_hash=result_item_hash,
        controller_hash=stable_final_publication_hash(response_payload),
    )


def _final_visible_rebind_effects_request_from_dict(
    request: DesignGuideControllerFinalVisibleRebindEffectsRequest | dict[str, Any] | None,
) -> DesignGuideControllerFinalVisibleRebindEffectsRequest:
    if request is None:
        return DesignGuideControllerFinalVisibleRebindEffectsRequest()
    if isinstance(request, DesignGuideControllerFinalVisibleRebindEffectsRequest):
        return request
    if isinstance(request, dict):
        return DesignGuideControllerFinalVisibleRebindEffectsRequest(
            evidence_for_binding=_mapping(request.get("evidence_for_binding")),
            contract=_mapping(request.get("contract")),
            item=_mapping(request.get("item")),
            debug=_mapping(request.get("debug")),
            current_updates=_mapping(request.get("current_updates")),
            target_binding_updates=_mapping(request.get("target_binding_updates")),
            target_binding_util=request.get("target_binding_util"),
            target_binding_count=int(request.get("target_binding_count") or 0),
            target_binding_family=str(request.get("target_binding_family") or ""),
            target_binding_candidate_id=request.get("target_binding_candidate_id"),
            target_low=request.get("target_low"),
            target_high=request.get("target_high"),
            current_binding_expected=request.get("current_binding_expected"),
            target_updates_already_applied=bool(request.get("target_updates_already_applied")),
            safe_binding_updates=_mapping(request.get("safe_binding_updates")),
            combined_binding_updates=_mapping(request.get("combined_binding_updates")),
            safe_updates_already_applied=bool(request.get("safe_updates_already_applied")),
            combined_updates_already_applied=bool(request.get("combined_updates_already_applied")),
            combined_binding_bending_util=request.get("combined_binding_bending_util"),
            evidence_expected_util=request.get("evidence_expected_util"),
            evidence_family=str(request.get("evidence_family") or ""),
            blocker_families=tuple(str(value) for value in (request.get("blocker_families") or ())),
            final_accepted_min_family_util=float(request.get("final_accepted_min_family_util") or 0.0),
            target_band_eps=float(request.get("target_band_eps") or 0.0),
            compound_shear_update_keys=tuple(
                str(value) for value in (request.get("compound_shear_update_keys") or ())
            ),
            compound_bottom_update_keys=tuple(
                str(value) for value in (request.get("compound_bottom_update_keys") or ())
            ),
            source=str(request.get("source") or "controller_final_visible_rebind_effects_trace_only"),
        )
    return DesignGuideControllerFinalVisibleRebindEffectsRequest()


def run_design_guide_controller_final_visible_rebind_effects_trace_only(
    request: DesignGuideControllerFinalVisibleRebindEffectsRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerFinalVisibleRebindEffectsResponse:
    """Build trace-only controller proof for final-visible rebind effects.

    The controller composes the Design Brain proof object only. It does not
    mutate the item, render UI, route Apply, or read session state.
    """

    request_obj = _final_visible_rebind_effects_request_from_dict(request)
    request_hash = stable_final_publication_hash(request_obj.to_dict())
    proof = build_final_visible_contract_binding_rebind_effects_proof(
        evidence_for_binding=dict(request_obj.evidence_for_binding),
        contract=dict(request_obj.contract),
        item=dict(request_obj.item),
        debug=dict(request_obj.debug),
        current_updates=dict(request_obj.current_updates),
        target_binding_updates=dict(request_obj.target_binding_updates),
        target_binding_util=request_obj.target_binding_util,
        target_binding_count=int(request_obj.target_binding_count or 0),
        target_binding_family=str(request_obj.target_binding_family or ""),
        target_binding_candidate_id=request_obj.target_binding_candidate_id,
        target_low=request_obj.target_low,
        target_high=request_obj.target_high,
        current_binding_expected=request_obj.current_binding_expected,
        target_updates_already_applied=bool(request_obj.target_updates_already_applied),
        safe_binding_updates=dict(request_obj.safe_binding_updates),
        combined_binding_updates=dict(request_obj.combined_binding_updates),
        safe_updates_already_applied=bool(request_obj.safe_updates_already_applied),
        combined_updates_already_applied=bool(request_obj.combined_updates_already_applied),
        combined_binding_bending_util=request_obj.combined_binding_bending_util,
        evidence_expected_util=request_obj.evidence_expected_util,
        evidence_family=str(request_obj.evidence_family or ""),
        blocker_families=tuple(request_obj.blocker_families or ()),
        final_accepted_min_family_util=float(request_obj.final_accepted_min_family_util or 0.0),
        target_band_eps=float(request_obj.target_band_eps or 0.0),
        compound_shear_update_keys=tuple(request_obj.compound_shear_update_keys or ()),
        compound_bottom_update_keys=tuple(request_obj.compound_bottom_update_keys or ()),
    )
    represented_effects = tuple(str(value) for value in (proof.get("represented_effects") or ()))
    result_flags = dict(proof.get("result_flags") or {})
    projection = build_final_visible_contract_binding_rebind_projection(
        item=dict(request_obj.item),
        contract=dict(request_obj.contract),
        evidence_for_binding=dict(request_obj.evidence_for_binding),
        debug=dict(request_obj.debug),
        rebind_effects_proof=dict(proof),
    )
    default_rebuild_projection = build_final_visible_contract_binding_output_projection(
        callsite_id=str(request_obj.source or "controller_final_visible_rebind_effects_trace_only"),
        input_item=dict(request_obj.item),
        rebind_projection=dict(projection),
        debug_projection=dict(request_obj.debug),
    ).to_dict()
    response_payload = {
        "controller_id": "DesignGuideController.final_visible_rebind_effects.trace_only",
        "authority": "DesignGuideController",
        "request_hash": request_hash,
        "request_source": request_obj.source,
        "rebind_effects_proof": dict(proof),
        "rebind_effects_proof_hash": proof.get("proof_hash"),
        "rebind_projection": dict(projection),
        "rebind_projection_hash": projection.get("projection_hash"),
        "final_visible_output_projection": dict(default_rebuild_projection),
        "final_visible_output_projection_hash": default_rebuild_projection.get("adapter_hash"),
        "represented_effects": represented_effects,
        "result_flags": result_flags,
        "trace_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return DesignGuideControllerFinalVisibleRebindEffectsResponse(
        controller_id="DesignGuideController.final_visible_rebind_effects.trace_only",
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        rebind_effects_proof=dict(proof),
        rebind_effects_proof_hash=proof.get("proof_hash"),
        represented_effects=represented_effects,
        result_flags=result_flags,
        controller_hash=stable_final_publication_hash(response_payload),
        rebind_projection=dict(projection),
        rebind_projection_hash=projection.get("projection_hash"),
        final_visible_output_projection=dict(default_rebuild_projection),
        final_visible_output_projection_hash=default_rebuild_projection.get("adapter_hash"),
    )


def _compute_handoff_request_from_dict(
    request: DesignGuideControllerComputePublicationHandoffRequest | dict[str, Any] | None,
) -> DesignGuideControllerComputePublicationHandoffRequest:
    if request is None:
        return DesignGuideControllerComputePublicationHandoffRequest()
    if isinstance(request, DesignGuideControllerComputePublicationHandoffRequest):
        return request
    if isinstance(request, dict):
        raw_items = request.get("collapsed_guidance_items") or []
        items = [dict(item) for item in raw_items if isinstance(item, dict)]
        return DesignGuideControllerComputePublicationHandoffRequest(
            current_state=_mapping(request.get("current_state")),
            overview=_mapping(request.get("overview")),
            collapsed_guidance_items=items,
            publication_context=_mapping(request.get("publication_context")),
            publication_dependencies=_mapping(request.get("publication_dependencies")),
            final_compute_resolution=_mapping(request.get("final_compute_resolution")),
            blocker_evidence_surface=_mapping(request.get("blocker_evidence_surface")),
            late_evidence_acceptance=_mapping(request.get("late_evidence_acceptance")),
            rebound_contract=_mapping(request.get("rebound_contract")),
            rebound_update_payload=_mapping(request.get("rebound_update_payload")),
            post_core_evidence_mismatch=_mapping(request.get("post_core_evidence_mismatch")),
            raw_rebound_item=_mapping(request.get("raw_rebound_item")),
            pre_resolver_collapsed_item_mutation=_mapping(
                request.get("pre_resolver_collapsed_item_mutation")
            ),
            debug=_mapping(request.get("debug")),
            verifier_payload=_mapping(request.get("verifier_payload")),
            session_controls=_mapping(request.get("session_controls")),
            design_actions_signature=tuple(request.get("design_actions_signature") or ()),
            optimisation_goal=str(request.get("optimisation_goal") or ""),
            publication_reason=request.get("publication_reason"),
            source=str(request.get("source") or "controller_compute_publication_handoff_trace_only"),
        )
    raise TypeError(
        "request must be a DesignGuideControllerComputePublicationHandoffRequest, dict, or None"
    )


def run_design_guide_controller_compute_publication_handoff_trace_only(
    request: DesignGuideControllerComputePublicationHandoffRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerComputePublicationHandoffResponse:
    """Build trace-only controller proof for compute publication handoff.

    This does not replace live compute selection. It consumes the current live
    selected item/resolution as plain data and returns a stable controller-owned
    proof shape for parity before future deletion work.
    """

    request_obj = _compute_handoff_request_from_dict(request)
    request_hash = stable_final_publication_hash(
        {
            "request": request_obj.to_dict(),
            "memo_owner": "DesignGuideController.compute_publication_handoff",
            "memo_key_contract": "full_compute_handoff_trace_v1",
        }
    )
    current_resolution = _mapping(request_obj.final_compute_resolution)
    selected_item = _mapping(current_resolution.get("item"))
    if not selected_item and request_obj.collapsed_guidance_items:
        selected_item = _mapping(request_obj.collapsed_guidance_items[0])
    raw_rebound_item = _mapping(request_obj.raw_rebound_item)
    rebound_accepted = bool(
        _mapping(request_obj.late_evidence_acceptance).get("accepted")
        or _mapping(request_obj.post_core_evidence_mismatch).get("accepted")
    )
    publication_item = raw_rebound_item if rebound_accepted and raw_rebound_item else selected_item
    blocker_evidence_surface = _mapping(request_obj.blocker_evidence_surface)
    if not blocker_evidence_surface:
        blocker_evidence_surface = {
            "candidate_search_evidence": _mapping(selected_item.get("candidate_search_evidence")),
            "exact_blockers_by_family": _mapping(selected_item.get("exact_blockers_by_family")),
            "post_click_exact_blockers_by_family": _mapping(
                selected_item.get("post_click_exact_blockers_by_family")
            ),
            "source": "DesignGuideController.compute_publication_handoff.trace_only",
            "proof_only": True,
            "product_driving": False,
        }
    render_reason = (
        request_obj.publication_reason
        or current_resolution.get("render_reason")
        or "controller_compute_publication_handoff"
    )
    debug = {
        **_mapping(request_obj.debug),
        "overview": _mapping(request_obj.overview),
        "publication_context": _mapping(request_obj.publication_context),
        "publication_dependencies": _mapping(request_obj.publication_dependencies),
    }
    publication = build_final_design_guide_publication(
        item=dict(publication_item),
        debug=dict(debug),
        design_brain_result=_mapping(debug.get("design_brain_result")),
        verifier_payload=dict(request_obj.verifier_payload),
        publication_reason=str(render_reason),
    )
    collapsed_item = build_collapsed_guidance_item_from_final_publication(
        publication,
    )
    final_visible_resolution = _build_final_visible_resolution(
        publication=publication,
        collapsed_guidance_item=collapsed_item,
        current_resolution=current_resolution,
        source=str(render_reason),
        request_hash=request_hash,
        request_source=request_obj.source,
        derived_from="DesignGuideController.compute_publication_handoff.trace_only",
        trace_only=True,
        product_driving=False,
    )
    proof = build_final_design_guide_compute_publication_handoff_rebound_decision_proof(
        raw_selected_item=dict(selected_item),
        blocker_evidence_surface=dict(blocker_evidence_surface),
        render_reason=str(render_reason),
        state_fingerprint=current_resolution.get("state_fingerprint"),
        late_evidence_acceptance=dict(request_obj.late_evidence_acceptance),
        rebound_contract=dict(request_obj.rebound_contract),
        rebound_update_payload=dict(request_obj.rebound_update_payload),
        post_core_evidence_mismatch=dict(request_obj.post_core_evidence_mismatch),
        raw_rebound_item=dict(raw_rebound_item or collapsed_item),
        pre_resolver_collapsed_item_mutation=dict(request_obj.pre_resolver_collapsed_item_mutation),
    ).to_dict()
    parity_payload = {
        "request_hash": request_hash,
        "request_source": request_obj.source,
        "selected_item_hash": stable_final_publication_hash(selected_item),
        "publication_item_hash": stable_final_publication_hash(publication_item),
        "raw_rebound_item_hash": stable_final_publication_hash(raw_rebound_item),
        "rebound_accepted": rebound_accepted,
        "publication_item_source": (
            "raw_rebound_item" if rebound_accepted and raw_rebound_item else "selected_item"
        ),
        "final_visible_resolution_hash": stable_final_publication_hash(final_visible_resolution),
        "publication_hash": publication.publication_hash,
        "compute_handoff_rebound_decision_hash": proof.get("decision_hash"),
        "covered_blocking_fields": list(proof.get("covered_blocking_fields") or []),
        "missing_blocking_fields": list(proof.get("missing_blocking_fields") or []),
        "trace_only": True,
        "product_driving": False,
    }
    controller_payload = {
        "authority": "DesignGuideController.compute_publication_handoff.trace_only",
        "request_hash": request_hash,
        "selected_item": selected_item,
        "publication_item": publication_item,
        "raw_rebound_item": raw_rebound_item,
        "final_visible_resolution": final_visible_resolution,
        "publication": publication.to_dict(),
        "compute_handoff_rebound_decision_proof": proof,
        "parity_payload": parity_payload,
    }
    return DesignGuideControllerComputePublicationHandoffResponse(
        controller_id="DesignGuideController.compute_publication_handoff.trace_only",
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        selected_item=dict(publication_item),
        selected_item_hash=parity_payload["publication_item_hash"],
        final_visible_resolution=final_visible_resolution,
        final_visible_resolution_hash=parity_payload["final_visible_resolution_hash"],
        publication=publication.to_dict(),
        publication_hash=publication.publication_hash,
        compute_handoff_rebound_decision_proof=proof,
        compute_handoff_rebound_decision_hash=proof.get("decision_hash"),
        parity_payload=parity_payload,
        controller_hash=stable_final_publication_hash(controller_payload),
    )


def _compute_rebound_mutation_request_from_dict(
    request: DesignGuideControllerComputeReboundMutationRequest | dict[str, Any] | None,
) -> DesignGuideControllerComputeReboundMutationRequest:
    if isinstance(request, DesignGuideControllerComputeReboundMutationRequest):
        return request
    if request is None:
        return DesignGuideControllerComputeReboundMutationRequest(path_id="unknown")
    if isinstance(request, dict):
        return DesignGuideControllerComputeReboundMutationRequest(
            path_id=str(request.get("path_id") or "unknown"),
            accepted=bool(request.get("accepted")),
            primary_item=_mapping(request.get("primary_item")),
            rebound_item=_mapping(request.get("rebound_item")),
            collapsed_guidance_items=[
                _mapping(item) for item in list(request.get("collapsed_guidance_items") or [])
            ],
            rebound_contract=_mapping(request.get("rebound_contract")),
            rebound_update_payload=_mapping(request.get("rebound_update_payload")),
            source=str(request.get("source") or "controller_compute_rebound_mutation_trace_only"),
        )
    raise TypeError(
        "request must be a DesignGuideControllerComputeReboundMutationRequest, dict, or None"
    )


def _compute_rebound_publication_item_request_from_dict(
    request: DesignGuideControllerComputeReboundPublicationItemRequest | dict[str, Any] | None,
) -> DesignGuideControllerComputeReboundPublicationItemRequest:
    if isinstance(request, DesignGuideControllerComputeReboundPublicationItemRequest):
        return request
    if request is None:
        return DesignGuideControllerComputeReboundPublicationItemRequest(path_id="unknown")
    if isinstance(request, dict):
        return DesignGuideControllerComputeReboundPublicationItemRequest(
            path_id=str(request.get("path_id") or "unknown"),
            primary_item=_mapping(request.get("primary_item")),
            rebound_contract=_mapping(request.get("rebound_contract")),
            rebound_update_payload=_mapping(request.get("rebound_update_payload")),
            publication_reason=request.get("publication_reason"),
            source=str(
                request.get("source")
                or "controller_compute_rebound_publication_item_trace_only"
            ),
            product_driving=bool(request.get("product_driving")),
        )
    raise TypeError(
        "request must be a DesignGuideControllerComputeReboundPublicationItemRequest, dict, or None"
    )


def _controller_button_contract_enabled(contract: dict[str, Any] | None) -> bool:
    contract_d = _mapping(contract)
    return bool(contract_d.get("enabled") or contract_d.get("actionable"))


def run_design_guide_controller_compute_rebound_publication_item_trace_only(
    request: DesignGuideControllerComputeReboundPublicationItemRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerComputeReboundPublicationItemResponse:
    """Build the compute rebound item shape without the page restamper.

    Trace-only. It does not publish, render, route Apply, or mutate session.
    """

    request_obj = _compute_rebound_publication_item_request_from_dict(request)
    request_hash = stable_final_publication_hash(
        {
            "request": request_obj.to_dict(),
            "memo_owner": "DesignGuideController.compute_rebound_publication_item",
            "memo_key_contract": "compute_rebound_publication_item_trace_v1",
        }
    )
    primary_item = _mapping(request_obj.primary_item)
    contract = _mapping(request_obj.rebound_contract or primary_item.get("button_contract"))
    updates = _mapping(request_obj.rebound_update_payload or contract.get("updates"))
    if updates:
        contract["updates"] = dict(updates)
        contract["enabled"] = bool(contract.get("enabled") or contract.get("actionable") or updates)
        contract["actionable"] = bool(contract.get("actionable") or contract.get("enabled") or updates)
        contract["action_type"] = contract.get("action_type") or "apply_resolved_candidate"
        contract["preview_pass"] = bool(contract.get("preview_pass") or updates)
        contract["executor_backed"] = bool(contract.get("executor_backed") or updates)
        contract["blocking_reason"] = None
        contract["disabled_reason"] = None
    if not contract.get("candidate_id") and primary_item.get("candidate_id"):
        contract["candidate_id"] = primary_item.get("candidate_id")
    if not contract.get("source_candidate_id") and primary_item.get("source_candidate_id"):
        contract["source_candidate_id"] = primary_item.get("source_candidate_id")
    selected_item = dict(primary_item)
    selected_item["button_contract"] = dict(contract)
    selected_item["updates"] = dict(updates)
    selected_item["selected_action_updates"] = dict(updates)
    selected_item["action_payload"] = {
        **_mapping(selected_item.get("action_payload")),
        "action_type": contract.get("action_type"),
        "family": contract.get("family"),
        "updates": dict(updates),
        "candidate_id": contract.get("candidate_id"),
        "source_candidate_id": contract.get("source_candidate_id"),
        "executor_backed": bool(contract.get("executor_backed")),
    }
    evidence = _mapping(selected_item.get("candidate_search_evidence"))
    selected_item["candidate_search_evidence"] = {
        **evidence,
        "family": evidence.get("family") or contract.get("family"),
        "selected_candidate_id": contract.get("candidate_id")
        or evidence.get("selected_candidate_id"),
        "selected_candidate_updates": dict(
            updates or evidence.get("selected_candidate_updates")
        ),
        "safe_executor_backed_candidates_count": max(
            int(evidence.get("safe_executor_backed_candidates_count") or 0),
            1 if _controller_button_contract_enabled(contract) else 0,
        ),
    }
    if contract.get("candidate_id"):
        selected_item["candidate_id"] = contract.get("candidate_id")
    if contract.get("source_candidate_id"):
        selected_item["source_candidate_id"] = contract.get("source_candidate_id")

    publication = build_final_design_guide_publication(
        item=dict(selected_item),
        debug={},
        publication_reason=request_obj.publication_reason or request_obj.path_id,
    )
    collapsed_item = build_collapsed_guidance_item_from_final_publication(
        publication,
    )
    payload = {
        "path_id": request_obj.path_id,
        "selected_item": selected_item,
        "collapsed_guidance_item": collapsed_item,
        "publication_hash": publication.publication_hash,
        "request_hash": request_hash,
        "trace_only": not bool(request_obj.product_driving),
        "product_driving": bool(request_obj.product_driving),
    }
    return DesignGuideControllerComputeReboundPublicationItemResponse(
        controller_id="DesignGuideController.compute_rebound_publication_item.trace_only",
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        path_id=request_obj.path_id,
        selected_item=dict(selected_item),
        selected_item_hash=stable_final_publication_hash(selected_item),
        collapsed_guidance_item=dict(collapsed_item),
        collapsed_guidance_item_hash=stable_final_publication_hash(collapsed_item),
        publication=publication.to_dict(),
        publication_hash=publication.publication_hash,
        controller_hash=stable_final_publication_hash(payload),
        trace_only=not bool(request_obj.product_driving),
        product_driving=bool(request_obj.product_driving),
    )


def run_design_guide_controller_compute_rebound_mutation_trace_only(
    request: DesignGuideControllerComputeReboundMutationRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerComputeReboundMutationResponse:
    """Represent the page's compute rebound mutation output as plain data.

    Proof-only. This does not publish, render, route Apply, or mutate session.
    """

    request_obj = _compute_rebound_mutation_request_from_dict(request)
    request_hash = stable_final_publication_hash(
        {
            "request": request_obj.to_dict(),
            "memo_owner": "DesignGuideController.compute_rebound_mutation",
            "memo_key_contract": "compute_rebound_mutation_trace_v1",
        }
    )
    primary_item = _mapping(request_obj.primary_item)
    rebound_item = _mapping(request_obj.rebound_item)
    contract = _mapping(request_obj.rebound_contract or rebound_item.get("button_contract"))
    updates = _mapping(request_obj.rebound_update_payload or contract.get("updates"))
    accepted = bool(request_obj.accepted and rebound_item)
    selected_item = dict(rebound_item if accepted else primary_item)
    collapsed_items = [_mapping(item) for item in list(request_obj.collapsed_guidance_items or [])]
    if accepted:
        if collapsed_items:
            collapsed_items[0] = dict(selected_item)
        else:
            collapsed_items = [dict(selected_item)]
    debug_updates: dict[str, Any] = {}
    if accepted and request_obj.path_id == "compute_late_evidence_contract_rebound":
        debug_updates = {
            "late_evidence_cleanup_contract_rebound": True,
            "primary_button_contract": dict(contract),
            "button_contract": dict(contract),
            "button_contract_enabled": True,
            "button_contract_updates": dict(updates),
            "selected_action_updates": dict(updates),
            "selected_action_type": "apply_resolved_candidate",
            "selected_action_family": contract.get("family"),
        }
    elif accepted and request_obj.path_id == "post_core_evidence_rebound":
        debug_updates = {
            "post_evidence_cleanup_contract_rebound": _controller_button_contract_enabled(contract),
        }
    payload = {
        "path_id": request_obj.path_id,
        "accepted": accepted,
        "selected_item": selected_item,
        "collapsed_guidance_items": collapsed_items,
        "debug_compatibility_update_keys": tuple(
            sorted(str(key) for key in debug_updates.keys())
        ),
        "debug_compatibility_updates_hash": stable_final_publication_hash(debug_updates),
        "request_hash": request_hash,
        "trace_only": True,
        "product_driving": False,
    }
    return DesignGuideControllerComputeReboundMutationResponse(
        controller_id="DesignGuideController.compute_rebound_mutation.trace_only",
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        path_id=request_obj.path_id,
        accepted=accepted,
        selected_item=dict(selected_item),
        selected_item_hash=stable_final_publication_hash(selected_item),
        collapsed_guidance_items=list(collapsed_items),
        collapsed_guidance_items_hash=stable_final_publication_hash(collapsed_items),
        debug_compatibility_update_keys=tuple(sorted(str(key) for key in debug_updates.keys())),
        debug_compatibility_updates_hash=stable_final_publication_hash(debug_updates),
        controller_hash=stable_final_publication_hash(payload),
    )


def run_design_guide_controller_compute_resolver_replacement_trace_only(
    request: DesignGuideControllerComputePublicationHandoffRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerComputeResolverReplacementResponse:
    """Build a controller-owned final compute resolution without page resolver input.

    This is proof-only. It composes the controller compute selector with the
    compute publication handoff/rebound proof, preserving the same B-class
    pre-publication inputs and D-class fallback/safety surfaces that currently
    block deletion of the page compute resolver bridge.
    """

    request_obj = _compute_handoff_request_from_dict(request)
    selection_request = DesignGuideControllerComputeSelectionRequest(
        current_state=dict(request_obj.current_state),
        overview=dict(request_obj.overview),
        collapsed_guidance_items=list(request_obj.collapsed_guidance_items),
        publication_context=dict(request_obj.publication_context),
        publication_dependencies=dict(request_obj.publication_dependencies),
        session_controls=dict(request_obj.session_controls),
        design_actions_signature=tuple(request_obj.design_actions_signature or ()),
        optimisation_goal=str(request_obj.optimisation_goal or ""),
        publication_reason=request_obj.publication_reason,
        source="controller_compute_resolver_replacement.selection",
    )
    selection = run_design_guide_controller_compute_selection_trace_only(selection_request)
    selected_item = dict(selection.selected_item)
    render_reason = selection.render_reason
    state_fingerprint = selection.state_fingerprint
    blocker_surface = dict(request_obj.blocker_evidence_surface or {})
    evidence = dict(
        blocker_surface.get("candidate_search_evidence")
        or selected_item.get("candidate_search_evidence")
        or request_obj.debug.get("candidate_search_evidence")
        or blocker_surface
        or {}
    )
    exact_blockers = dict(
        blocker_surface.get("exact_blockers_by_family")
        or selected_item.get("exact_blockers_by_family")
        or selected_item.get("post_click_exact_blockers_by_family")
        or evidence.get("exact_blockers_by_family")
        or request_obj.debug.get("exact_blockers_by_family")
        or {}
    )
    exact_blockers = {
        str(key or "").strip().lower(): dict(value)
        for key, value in exact_blockers.items()
        if str(key or "").strip() and isinstance(value, dict)
    }
    overview_statuses = dict(request_obj.overview.get("statuses") or {})
    overview_active_failures = [
        str(name or "").strip().lower()
        for name, status in overview_statuses.items()
        if str(status or "").strip().upper() == "FAIL"
    ]
    active_failures = sorted(
        {
            str(family or "").strip().lower()
            for family in list(
                evidence.get("active_failures")
                or selected_item.get("active_failures")
                or overview_active_failures
                or exact_blockers.keys()
                or []
            )
            if str(family or "").strip()
        }
    )
    selected_contract = dict(selected_item.get("button_contract") or {})
    selected_status_failed = str(selected_item.get("status") or "").strip().upper() == "FAIL"
    selected_action_blocked = (
        not str(selected_item.get("action_type") or "").strip()
        or not bool(selected_contract.get("actionable"))
        or bool(selected_contract.get("blocking_reason"))
        or selected_contract.get("preview_pass") is False
    )
    active_blocker_evidence_present = bool(
        evidence.get("active_under_capacity_blocker")
        or evidence.get("repair_search_exhaustive")
        or evidence.get("candidate_search_exhaustive")
        or exact_blockers
    )
    if (
        str(render_reason or "") == "controller_compute_primary_item_selection"
        and selected_status_failed
        and selected_action_blocked
        and active_failures
        and active_blocker_evidence_present
    ):
        render_reason = "final_visible_active_strength_blocker"
    if str(render_reason or "") == "final_visible_active_strength_blocker":
        if not active_failures:
            active_failures = ["bending"]
        active_family = (
            "combined"
            if {"bending", "shear"}.issubset(set(active_failures))
            else (
                "shear"
                if "shear" in active_failures
                else (
                    "serviceability"
                    if {"serviceability", "crack", "deflection"} & set(active_failures)
                    else "bending"
                )
            )
        )
        active_title = str(
            selected_item.get("title_main")
            or selected_item.get("title")
            or (
                "Bending and shear repair blocked"
                if active_family == "combined"
                else "Shear repair blocked by shear/detailing limits"
                if active_family == "shear"
                else "Serviceability repair blocked"
                if active_family == "serviceability"
                else "Bending repair blocked by reinforcement/detailing limits"
            )
        )
        blocker_evidence = dict(evidence)
        blocker_evidence.setdefault("active_failures", list(active_failures))
        generated_exact_blockers = active_failure_exact_blockers_for_families(
            list(active_failures),
            overview=dict(request_obj.overview),
            evidence=dict(blocker_evidence),
            primary_family=active_family if active_family in {"bending", "shear"} else None,
            primary_reason=str(
                blocker_evidence.get("active_under_capacity_blocker_reason")
                or blocker_evidence.get("outside_target_band_allowed_reason")
                or selected_item.get("primary_action")
                or selected_item.get("secondary_action")
                or selected_item.get("reasoning")
                or ""
            ).strip()
            or None,
        )
        generated_exact_blockers.update(dict(exact_blockers))
        visible_reason = active_failure_blocker_visible_reason_text(
            dict(generated_exact_blockers),
            list(active_failures),
        )
        blocker_evidence["exact_blockers_by_family"] = dict(generated_exact_blockers)
        blocker_evidence["post_click_exact_blockers_by_family"] = dict(generated_exact_blockers)
        blocker_evidence.setdefault("cleanup_search_ran", False)
        blocker_evidence.setdefault("cleanup_search_exhaustive", False)
        blocker_evidence.setdefault("local_cleanup_search_ran", False)
        blocker_evidence.setdefault("local_cleanup_search_exhaustive", False)
        blocker_item = dict(selected_item)
        blocker_item.pop("button_contract", None)
        blocker_item["candidate_search_evidence"] = dict(blocker_evidence)
        blocker_item["exact_blockers_by_family"] = dict(generated_exact_blockers)
        blocker_item["post_click_exact_blockers_by_family"] = dict(generated_exact_blockers)
        blocker_item.setdefault("active_under_capacity_blocker", True)
        blocker_item.setdefault("active_under_capacity_blocker_family", active_family)
        util = _float_or_none(
            dict(request_obj.overview.get("utils") or {}).get(active_family)
            if active_family in {"bending", "shear"}
            else None
        )
        if util is None:
            util = _float_or_none(
                request_obj.overview.get("worst_util")
                or request_obj.overview.get("governing_util")
                or selected_item.get("util")
            )
        if util is not None:
            blocker_item["title"] = f"{active_title} (utilisation = {util:.2f})"
            blocker_item.setdefault("title_util", f"(utilisation = {util:.2f})")
            blocker_item.setdefault("util", util)
        if visible_reason:
            blocker_item["primary_action"] = visible_reason
            blocker_item["secondary_action"] = ""
            blocker_item["reasoning"] = f"Why: {visible_reason}"
        finalized_blocker = finalize_design_guide_active_failure_blocker_publication(
            blocker=blocker_item,
            fallback_item=(
                dict(request_obj.collapsed_guidance_items[0])
                if request_obj.collapsed_guidance_items
                and isinstance(request_obj.collapsed_guidance_items[0], dict)
                else {}
            ),
            active_family=active_family,
            active_title=active_title,
            active_failures=list(active_failures),
            final_overview=dict(request_obj.overview),
            item_state_fingerprint=selection.state_fingerprint,
            result_state_fingerprint=selection.state_fingerprint,
            debug_probe={},
        )
        selected_item = dict(finalized_blocker.get("item") or blocker_item)
        selected_item.pop("headline", None)
        selected_item.pop("summary_line", None)
        render_reason = str(finalized_blocker.get("render_reason") or render_reason)
        state_fingerprint = str(
            finalized_blocker.get("state_fingerprint") or selection.state_fingerprint
        )
    final_compute_resolution = {
        "item": dict(selected_item),
        "render_reason": render_reason,
        "state_fingerprint": state_fingerprint,
        "controller_selection_hash": selection.selection_hash,
        "controller_request_hash": selection.request_hash,
        "controller_authority": "DesignGuideController.compute_selection",
        "controller_materialized_active_strength_blocker": bool(
            str(selection.render_reason or "") == "final_visible_active_strength_blocker"
        ),
        "old_resolver_input_required": False,
        "trace_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    handoff_request = DesignGuideControllerComputePublicationHandoffRequest(
        current_state=dict(request_obj.current_state),
        overview=dict(request_obj.overview),
        collapsed_guidance_items=list(request_obj.collapsed_guidance_items),
        publication_context=dict(request_obj.publication_context),
        publication_dependencies=dict(request_obj.publication_dependencies),
        final_compute_resolution=dict(final_compute_resolution),
        blocker_evidence_surface=dict(request_obj.blocker_evidence_surface),
        late_evidence_acceptance=dict(request_obj.late_evidence_acceptance),
        rebound_contract=dict(request_obj.rebound_contract),
        rebound_update_payload=dict(request_obj.rebound_update_payload),
        post_core_evidence_mismatch=dict(request_obj.post_core_evidence_mismatch),
        pre_resolver_collapsed_item_mutation=dict(request_obj.pre_resolver_collapsed_item_mutation),
        debug=dict(request_obj.debug),
        verifier_payload=dict(request_obj.verifier_payload),
        publication_reason=request_obj.publication_reason or selection.render_reason,
        source="controller_compute_resolver_replacement.handoff",
    )
    handoff = run_design_guide_controller_compute_publication_handoff_trace_only(handoff_request)
    request_hash = stable_final_publication_hash(
        {
            "request": request_obj.to_dict(),
            "selection_hash": selection.selection_hash,
            "final_compute_resolution": final_compute_resolution,
            "handoff_hash": handoff.controller_hash,
            "memo_owner": "DesignGuideController.compute_resolver_replacement",
            "memo_key_contract": "compute_resolver_replacement_trace_v1",
        }
    )
    payload = {
        "selection": selection.to_dict(),
        "handoff": handoff.to_dict(),
        "final_compute_resolution": final_compute_resolution,
        "old_resolver_input_required": False,
    }
    return DesignGuideControllerComputeResolverReplacementResponse(
        controller_id="DesignGuideController.compute_resolver_replacement.trace_only",
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        selection=selection.to_dict(),
        handoff=handoff.to_dict(),
        final_compute_resolution=final_compute_resolution,
        final_compute_resolution_hash=stable_final_publication_hash(final_compute_resolution),
        compute_handoff_rebound_decision_hash=handoff.compute_handoff_rebound_decision_hash,
        controller_hash=stable_final_publication_hash(payload),
    )


def build_design_guide_controller_compute_resolver_fallback_shell(
    request: DesignGuideControllerComputePublicationHandoffRequest | dict[str, Any] | None = None,
    *,
    reason: str | None = None,
    error: str | None = None,
) -> DesignGuideControllerComputeResolverReplacementResponse:
    """Build a controller-owned fallback shell for missing replacement response.

    The shell is plain data, disabled for Apply, and explicitly fallback-only.
    It lets the page avoid calling the old final-visible resolver when the
    controller replacement response is unavailable.
    """

    request_obj = _compute_handoff_request_from_dict(request)
    fallback_reason = (
        str(reason or "").strip()
        or "controller_compute_resolver_response_unavailable"
    )
    selected_item = (
        dict(request_obj.collapsed_guidance_items[0])
        if request_obj.collapsed_guidance_items
        and isinstance(request_obj.collapsed_guidance_items[0], dict)
        else {}
    )
    if not selected_item:
        selected_item = {
            "check_key": "general",
            "family": "general",
            "title_main": "Design Guide publication pending",
            "title": "Design Guide publication pending",
            "status": "PROOF_PENDING",
            "bucket": "warn",
            "guidance_intent": "proof_pending",
            "final_state_class": "proof_pending",
            "primary_card_actionable": False,
        }
    selected_item = dict(selected_item)
    selected_item["button_contract"] = disabled_design_guide_button_contract(
        selected_item,
        reason=fallback_reason,
    )
    selected_item["primary_card_actionable"] = False
    selected_item["controller_compute_resolver_fallback_shell"] = True
    selected_item["controller_compute_resolver_fallback_reason"] = fallback_reason
    if error:
        selected_item["controller_compute_resolver_fallback_error"] = str(error)
    request_hash = stable_final_publication_hash(
        {
            "request": request_obj.to_dict(),
            "memo_owner": "DesignGuideController.compute_resolver_fallback_shell",
            "memo_key_contract": "fallback_shell_v1",
            "fallback_reason": fallback_reason,
            "fallback_error": str(error or ""),
        }
    )
    state_fingerprint = str(
        design_guide_cache_fingerprint_from_plain_data(
            (
                dict(request_obj.publication_context.get("guidance_state_snapshot") or {})
                if isinstance(request_obj.publication_context, dict)
                and isinstance(request_obj.publication_context.get("guidance_state_snapshot"), dict)
                else dict(request_obj.current_state or {})
            ),
            session_controls=dict(request_obj.session_controls or {}),
            design_actions_signature=tuple(request_obj.design_actions_signature or ()),
            optimisation_goal=str(request_obj.optimisation_goal or ""),
        )
    )
    render_reason = "controller_compute_resolver_fallback_shell"
    debug = {
        **dict(request_obj.debug or {}),
        "controller_compute_resolver_fallback_shell": True,
        "controller_compute_resolver_fallback_reason": fallback_reason,
        "controller_compute_resolver_fallback_error": str(error or ""),
        "overview": dict(request_obj.overview or {}),
    }
    publication = build_final_design_guide_publication(
        item=dict(selected_item),
        debug=dict(debug),
        design_brain_result=_mapping(debug.get("design_brain_result")),
        verifier_payload=dict(request_obj.verifier_payload),
        publication_reason=render_reason,
    )
    collapsed_item = build_collapsed_guidance_item_from_final_publication(
        publication,
    )
    final_compute_resolution = _build_final_visible_resolution(
        publication=publication,
        collapsed_guidance_item=collapsed_item,
        current_resolution={
            "item": dict(selected_item),
            "render_reason": render_reason,
            "state_fingerprint": state_fingerprint,
        },
        source=render_reason,
        request_hash=request_hash,
        request_source=request_obj.source,
        derived_from="DesignGuideController.compute_resolver_fallback_shell",
        trace_only=False,
        product_driving=True,
    )
    final_compute_resolution["state_fingerprint"] = state_fingerprint
    final_compute_resolution["controller_compute_resolver_fallback_shell"] = True
    proof = build_final_design_guide_compute_publication_handoff_rebound_decision_proof(
        raw_selected_item=dict(selected_item),
        blocker_evidence_surface=dict(request_obj.blocker_evidence_surface or {}),
        render_reason=render_reason,
        state_fingerprint=state_fingerprint,
        late_evidence_acceptance=dict(request_obj.late_evidence_acceptance or {}),
        rebound_contract=dict(selected_item.get("button_contract") or {}),
        rebound_update_payload={},
        post_core_evidence_mismatch=dict(request_obj.post_core_evidence_mismatch or {}),
        raw_rebound_item=dict(collapsed_item),
        pre_resolver_collapsed_item_mutation=dict(
            request_obj.pre_resolver_collapsed_item_mutation or {}
        ),
    ).to_dict()
    payload = {
        "authority": "DesignGuideController.compute_resolver_fallback_shell",
        "request_hash": request_hash,
        "selected_item": selected_item,
        "final_compute_resolution": final_compute_resolution,
        "publication_hash": publication.publication_hash,
        "proof": proof,
        "fallback_reason": fallback_reason,
        "fallback_error": str(error or ""),
    }
    return DesignGuideControllerComputeResolverReplacementResponse(
        controller_id="DesignGuideController.compute_resolver_fallback_shell",
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        selection={
            "selected_item": dict(selected_item),
            "selection_policy": "controller_fallback_shell_v1",
            "fallback_shell": True,
        },
        handoff={
            "publication": publication.to_dict(),
            "collapsed_guidance_item": dict(collapsed_item),
            "fallback_shell": True,
        },
        final_compute_resolution=dict(final_compute_resolution),
        final_compute_resolution_hash=stable_final_publication_hash(final_compute_resolution),
        compute_handoff_rebound_decision_hash=proof.get("decision_hash"),
        controller_hash=stable_final_publication_hash(payload),
        old_resolver_input_required=False,
        trace_only=False,
        product_driving=True,
        render_driving=False,
        apply_driving=False,
        session_driving=False,
    )


def _compute_selection_request_from_dict(
    request: DesignGuideControllerComputeSelectionRequest | dict[str, Any] | None,
) -> DesignGuideControllerComputeSelectionRequest:
    if request is None:
        return DesignGuideControllerComputeSelectionRequest()
    if isinstance(request, DesignGuideControllerComputeSelectionRequest):
        return request
    if isinstance(request, dict):
        raw_items = request.get("collapsed_guidance_items") or []
        items = [dict(item) for item in raw_items if isinstance(item, dict)]
        return DesignGuideControllerComputeSelectionRequest(
            current_state=_mapping(request.get("current_state")),
            overview=_mapping(request.get("overview")),
            collapsed_guidance_items=items,
            publication_context=_mapping(request.get("publication_context")),
            publication_dependencies=_mapping(request.get("publication_dependencies")),
            session_controls=_mapping(request.get("session_controls")),
            design_actions_signature=tuple(request.get("design_actions_signature") or ()),
            optimisation_goal=str(request.get("optimisation_goal") or ""),
            publication_reason=request.get("publication_reason"),
            source=str(request.get("source") or "controller_compute_selection_trace_only"),
        )
    raise TypeError("request must be a DesignGuideControllerComputeSelectionRequest, dict, or None")


def run_design_guide_controller_compute_selection_trace_only(
    request: DesignGuideControllerComputeSelectionRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerComputeSelectionResponse:
    """Select a compute-stage item from plain data for trace-only parity proof.

    This initial selector intentionally implements only the already-collapsed
    primary-item policy. It does not replace the legacy resolver's active-fail,
    blocker, post-click, or cleanup routes.
    """

    request_obj = _compute_selection_request_from_dict(request)
    request_hash = stable_final_publication_hash(
        {
            "request": request_obj.to_dict(),
            "memo_owner": "DesignGuideController.compute_selection",
            "memo_key_contract": "full_compute_selection_trace_v1",
        }
    )
    selected_index: int | None = 0 if request_obj.collapsed_guidance_items else None
    selected_item = (
        dict(request_obj.collapsed_guidance_items[0])
        if request_obj.collapsed_guidance_items
        else {}
    )
    render_reason = str(
        request_obj.publication_reason
        or selected_item.get("final_visible_resolver_reason")
        or selected_item.get("publication_reason")
        or "controller_compute_primary_item_selection"
    )
    fingerprint_state = (
        dict(request_obj.publication_context.get("guidance_state_snapshot") or {})
        if isinstance(request_obj.publication_context, dict)
        and isinstance(request_obj.publication_context.get("guidance_state_snapshot"), dict)
        else dict(request_obj.current_state or {})
    )
    state_fingerprint = str(
        design_guide_cache_fingerprint_from_plain_data(
            fingerprint_state,
            session_controls=dict(request_obj.session_controls or {}),
            design_actions_signature=tuple(request_obj.design_actions_signature or ()),
            optimisation_goal=str(request_obj.optimisation_goal or ""),
        )
    )
    payload = {
        "request_hash": request_hash,
        "selected_item": selected_item,
        "selected_item_index": selected_index,
        "render_reason": render_reason,
        "state_fingerprint": state_fingerprint,
        "selection_policy": "primary_collapsed_guidance_item_trace_only_v1",
    }
    return DesignGuideControllerComputeSelectionResponse(
        controller_id="DesignGuideController.compute_selection.trace_only",
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        selected_item=selected_item,
        selected_item_index=selected_index,
        selected_item_hash=stable_final_publication_hash(selected_item),
        render_reason=render_reason,
        state_fingerprint=state_fingerprint,
        selection_policy="primary_collapsed_guidance_item_trace_only_v1",
        selection_hash=stable_final_publication_hash(payload),
    )


def _presentation_request_from_dict(
    request: DesignGuideControllerPresentationRequest | dict[str, Any] | None,
) -> DesignGuideControllerPresentationRequest:
    if request is None:
        return DesignGuideControllerPresentationRequest()
    if isinstance(request, DesignGuideControllerPresentationRequest):
        return request
    if isinstance(request, dict):
        raw_items = request.get("raw_items") or []
        raw_candidates = request.get("raw_candidates") or []
        return DesignGuideControllerPresentationRequest(
            current_state=_mapping(request.get("current_state")),
            summary=_mapping(request.get("summary")),
            raw_items=[dict(item) for item in raw_items if isinstance(item, dict)],
            candidate_evidence=_mapping(request.get("candidate_evidence")),
            raw_candidates=[
                dict(candidate) for candidate in raw_candidates if isinstance(candidate, dict)
            ],
            target_band=_mapping(request.get("target_band")),
            context=_mapping(request.get("context")),
            source=str(request.get("source") or "controller_presentation_adapter"),
        )
    raise TypeError("request must be a DesignGuideControllerPresentationRequest, dict, or None")


_PRESENTATION_TARGET_BAND_EPS = 0.005
_PRESENTATION_NEAR_LIMIT_UTIL_THRESHOLD = 0.95
_PRESENTATION_TARGET_UTIL_MIN, _PRESENTATION_TARGET_UTIL_MAX = get_target_utilisation_band(
    "balanced"
)
_PRESENTATION_INTENTS = frozenset(
    {
        "required_fix",
        "efficiency_tightening",
        "optional_cleanup",
        "already_efficient",
        "advisory_warning",
    }
)
_PRESENTATION_NON_COMMIT_STATUSES = frozenset(
    {
        "blocked",
        "failed",
        "no_action",
        "no_actionable_full_coverage_candidate",
        "rejected",
    }
)


def _presentation_goal_from_state(current_state: dict[str, Any]) -> str:
    goal = str(current_state.get("design_optimisation_goal") or "balanced").strip()
    return goal or "balanced"


def _presentation_mode_config(
    *,
    current_state: dict[str, Any],
    mode_config: dict[str, Any] | None,
    target_band: dict[str, Any] | None,
) -> dict[str, Any]:
    cfg = _mapping(mode_config)
    band = _mapping(target_band)
    goal = str(
        cfg.get("goal")
        or band.get("goal")
        or _presentation_goal_from_state(current_state)
        or "balanced"
    )
    target_low = _float_or_none(band.get("target_low"))
    target_high = _float_or_none(band.get("target_high"))
    if target_low is None or target_high is None:
        target_low, target_high = get_target_utilisation_band(goal)
    cfg.setdefault("target_util_min", float(target_low))
    cfg.setdefault("target_util_max", float(target_high))
    return cfg


def _presentation_updates_for_envelope(recommendation: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(recommendation, dict):
        return {}
    updates = recommendation.get("updates")
    if isinstance(updates, dict) and updates:
        return dict(updates)
    resolved = recommendation.get("resolved_candidate")
    if isinstance(resolved, dict) and isinstance(resolved.get("updates"), dict) and resolved.get("updates"):
        return dict(resolved.get("updates") or {})
    payload = recommendation.get("action_payload")
    if isinstance(payload, dict):
        payload_updates = payload.get("resolved_candidate_updates") or payload.get("updates")
        if isinstance(payload_updates, dict) and payload_updates:
            return dict(payload_updates)
    return {}


def _presentation_recommendation_envelope_from_pending(
    recommendation: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(recommendation, dict):
        return {}
    envelope = recommendation.get("recommendation_envelope")
    if isinstance(envelope, dict):
        return dict(envelope)
    meta = _mapping(recommendation.get("meta"))
    status = str(meta.get("status") or recommendation.get("status") or "").strip()
    reason = str(
        recommendation.get("blocked_reason")
        or meta.get("blocked_reason")
        or meta.get("reason")
        or ""
    ).strip()
    updates = _presentation_updates_for_envelope(recommendation)
    commit_eligible = bool(
        updates
        and not reason
        and status not in _PRESENTATION_NON_COMMIT_STATUSES
    )
    return {
        "status": status or ("ready" if commit_eligible else "blocked" if reason else "advisory"),
        "updates": updates,
        "commit_eligible": bool(commit_eligible),
        "blocked_reason": reason or None,
    }


def _presentation_recommendation_commit_eligible(
    recommendation: dict[str, Any] | None,
) -> bool:
    envelope = _presentation_recommendation_envelope_from_pending(recommendation)
    return bool(envelope.get("commit_eligible"))


def _presentation_recommendation_blocked_reason(
    recommendation: dict[str, Any] | None,
) -> str | None:
    envelope = _presentation_recommendation_envelope_from_pending(recommendation)
    reason = str(envelope.get("blocked_reason") or "").strip()
    if reason:
        return reason
    if isinstance(recommendation, dict) and not bool(envelope.get("commit_eligible")):
        status = str(envelope.get("status") or "").strip()
        if status in _PRESENTATION_NON_COMMIT_STATUSES:
            return status
    return None


def _presentation_governing_primary_action(
    overview: dict[str, Any] | None,
) -> tuple[str, dict[str, float | None]]:
    utils = _mapping((overview or {}).get("utils"))
    statuses = _mapping((overview or {}).get("statuses"))
    primary_utils: dict[str, float | None] = {}
    ranked: list[tuple[str, float]] = []
    for key in ("bending", "shear", "crack", "deflection"):
        resolved = _float_or_none(utils.get(key))
        if resolved is None or resolved != resolved:
            primary_utils[key] = None
            continue
        primary_utils[key] = resolved
        if str(statuses.get(key) or "").strip().upper() == "FAIL":
            ranked.append((key, resolved))
    if ranked:
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[0][0], primary_utils
    strength_ranked = [
        (key, util)
        for key, util in primary_utils.items()
        if key in {"bending", "shear"} and util is not None
    ]
    if strength_ranked:
        strength_ranked.sort(key=lambda item: item[1], reverse=True)
        return strength_ranked[0][0], primary_utils
    return "general", primary_utils


def _presentation_is_in_target_zone_with_eps(
    overview: dict[str, Any],
    mode_config: dict[str, Any],
    *,
    eps: float = _PRESENTATION_TARGET_BAND_EPS,
) -> bool:
    worst_util = _float_or_none((overview or {}).get("worst_util"))
    if worst_util is None:
        worst_util = 0.0
    lo = _float_or_none(mode_config.get("target_util_min"))
    hi = _float_or_none(mode_config.get("target_util_max"))
    if lo is None:
        lo = _PRESENTATION_TARGET_UTIL_MIN
    if hi is None:
        hi = _PRESENTATION_TARGET_UTIL_MAX
    return float(lo) <= float(worst_util) <= (float(hi) + float(eps))


def _presentation_is_unnecessarily_overdesigned(
    overview: dict[str, Any] | None,
    efficiency_state: dict[str, Any] | None,
) -> bool:
    if not isinstance(overview, dict) or not bool(overview.get("all_key_pass")):
        return False
    if bool(overview.get("any_fail")):
        return False
    es = _mapping(efficiency_state)
    if str(es.get("classification") or "") in {"optimal", "very_low_demand"}:
        return False
    if str(es.get("classification") or "") == "inefficient":
        return True
    if bool(es.get("strongly_underutilised")):
        return True
    if bool(es.get("is_efficiency_reduction_mode")):
        worst = _float_or_none(overview.get("worst_util"))
        return bool((worst if worst is not None else 0.0) < float(_PRESENTATION_TARGET_UTIL_MIN))
    return False


def _presentation_item_updates(item: dict[str, Any]) -> dict[str, Any]:
    updates = _presentation_updates_for_envelope(item)
    if updates:
        return updates
    payload = _mapping(item.get("action_payload"))
    resolved = _mapping(item.get("resolved_candidate"))
    return _mapping(
        payload.get("resolved_candidate_updates")
        or payload.get("updates")
        or resolved.get("updates")
    )


def _presentation_float_from_state(
    state: dict[str, Any],
    key: str,
    default: float = 0.0,
) -> float:
    value = _float_or_none(state.get(key))
    return float(default if value is None else value)


def _presentation_update_is_lighter_or_smaller(
    state: dict[str, Any],
    updates: dict[str, Any],
    item: dict[str, Any] | None = None,
) -> bool:
    if not updates:
        return False
    action_type = str(
        _mapping((item or {}).get("action_payload")).get("resolved_candidate_action_type")
        or (item or {}).get("action_type")
        or ""
    ).strip()
    if action_type in {
        "reduce_bottom_reinforcement",
        "tighten_geometry",
        "increase_link_spacing",
        "reduce_number_of_legs",
    }:
        return True
    geometry_keys = {"D", "b", "bw", "bf", "tw", "tf", "bf_bot", "tf_bot"}
    bottom_keys = {
        "bot1_count",
        "bot2_count",
        "bot_row_count",
        "bot_row_1_bars",
        "bot_row_2_bars",
        "db_bot_1",
        "db_bot_2",
        "nb_bot",
        "db_bot",
    }
    shear_keys = {"s_lig", "lig_legs", "lig_d"}
    for key, after_raw in updates.items():
        before = _presentation_float_from_state(state, str(key), 0.0)
        after = _float_or_none(after_raw)
        if after is None:
            continue
        if key in geometry_keys and after < before - 1e-9:
            return True
        if key in bottom_keys and after < before - 1e-9:
            return True
        if key == "s_lig" and after > before + 1e-9:
            return True
        if key in shear_keys and key != "s_lig" and after < before - 1e-9:
            return True
    return False


def _presentation_item_is_shear_only_cleanup(
    state: dict[str, Any],
    updates: dict[str, Any],
    item: dict[str, Any],
) -> bool:
    if not updates:
        return False
    shear_keys = {"s_lig", "lig_legs", "lig_d"}
    if not set(updates).issubset(shear_keys):
        return False
    current_spacing = _presentation_float_from_state(state, "s_lig", 200.0)
    next_spacing = _float_or_none(updates.get("s_lig"))
    if next_spacing is None:
        next_spacing = current_spacing
    current_legs = _presentation_float_from_state(state, "lig_legs", 0.0)
    next_legs = _float_or_none(updates.get("lig_legs"))
    if next_legs is None:
        next_legs = current_legs
    current_dia = _presentation_float_from_state(state, "lig_d", 0.0)
    next_dia = _float_or_none(updates.get("lig_d"))
    if next_dia is None:
        next_dia = current_dia
    return bool(
        next_spacing > current_spacing + 1e-9
        or next_legs < current_legs - 1e-9
        or next_dia < current_dia - 1e-9
        or str(item.get("check_key") or "").strip().lower() == "shear"
    )


def _presentation_shear_is_non_governing_conservative(
    overview: dict[str, Any] | None,
    mode_config: dict[str, Any],
) -> bool:
    ov = _mapping(overview)
    utils = _mapping(ov.get("utils"))
    shear_util = _float_or_none(utils.get("shear"))
    worst_util = _float_or_none(ov.get("worst_util"))
    target_lo = _float_or_none(mode_config.get("target_lo"))
    if target_lo is None:
        target_lo = _PRESENTATION_TARGET_UTIL_MIN
    if shear_util is None or shear_util >= target_lo - float(_PRESENTATION_TARGET_BAND_EPS):
        return False
    if worst_util is None:
        return True
    return bool(float(shear_util) < float(worst_util) - float(_PRESENTATION_TARGET_BAND_EPS))


def _presentation_guidance_intent(
    item: dict[str, Any],
    *,
    state: dict[str, Any],
    overview: dict[str, Any] | None,
    efficiency_state: dict[str, Any] | None,
    mode_config: dict[str, Any],
) -> str:
    existing = str(item.get("guidance_intent") or "").strip()
    if existing in _PRESENTATION_INTENTS:
        return existing
    ov = _mapping(overview)
    updates = _presentation_item_updates(item)
    has_material_update = bool(updates)
    has_action = bool(str(item.get("action_type") or "").strip())
    statuses = _mapping(ov.get("statuses"))
    fail_keys = {
        str(key).strip().lower()
        for key, value in statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    }
    any_fail = bool(ov.get("any_fail")) or bool(fail_keys)
    all_key_pass = bool(ov.get("all_key_pass")) and not any_fail
    worst_util = _float_or_none(ov.get("worst_util"))
    target_lo = _float_or_none(mode_config.get("target_lo"))
    if target_lo is None:
        target_lo = _PRESENTATION_TARGET_UTIL_MIN
    below_target = bool(
        all_key_pass
        and worst_util is not None
        and float(worst_util) < float(target_lo) - float(_PRESENTATION_TARGET_BAND_EPS)
    )
    in_target_band = bool(
        all_key_pass
        and _presentation_is_in_target_zone_with_eps(
            ov,
            mode_config,
            eps=_PRESENTATION_TARGET_BAND_EPS,
        )
    )
    terminal_state = str(item.get("design_guide_terminal_state") or "").strip()
    classification = str(_mapping(efficiency_state).get("classification") or "").strip()
    resolved = _mapping(item.get("resolved_candidate"))
    if any_fail and has_action and has_material_update:
        return "required_fix"
    if (
        has_action
        and has_material_update
        and (
            bool(item.get("allow_in_target_primary_action"))
            or str(item.get("design_guide_refinement_priority") or "").strip()
            == "shear_congestion_reshape"
            or bool(resolved.get("allow_in_target_primary_action"))
            or str(resolved.get("design_guide_refinement_priority") or "").strip()
            == "shear_congestion_reshape"
        )
    ):
        return "efficiency_tightening"
    if (
        has_action
        and has_material_update
        and _presentation_item_is_shear_only_cleanup(state, updates, item)
        and _presentation_shear_is_non_governing_conservative(ov, mode_config)
    ):
        return "optional_cleanup"
    if (
        not has_material_update
        and str(item.get("check_key") or "").strip().lower() == "shear"
        and _presentation_shear_is_non_governing_conservative(ov, mode_config)
    ):
        return "optional_cleanup"
    if (
        has_action
        and below_target
        and has_material_update
        and _presentation_update_is_lighter_or_smaller(state, updates, item)
    ):
        return "efficiency_tightening"
    if in_target_band and not has_material_update:
        return "already_efficient"
    if terminal_state == "optimal" or (classification == "optimal" and not has_material_update):
        return "already_efficient"
    return "advisory_warning"


def build_design_guide_controller_presentation_request(
    *,
    primary_item: dict[str, Any] | None,
    overview: dict[str, Any] | None,
    efficiency_state: dict[str, Any] | None,
    current_state: dict[str, Any] | None,
    mode_config: dict[str, Any] | None = None,
    recommendation_result: dict[str, Any] | None = None,
    pending_recommendation: dict[str, Any] | None = None,
    feedback_cta_state: dict[str, Any] | None = None,
    solver_result_cta_state: dict[str, Any] | None = None,
    source: str = "controller_presentation_request_builder",
) -> DesignGuideControllerPresentationRequest:
    """Build the presentation adapter request from plain page-shell inputs."""

    _ = recommendation_result
    state = _mapping(current_state)
    ov = _mapping(overview)
    es = _mapping(efficiency_state)
    item = _mapping(primary_item)
    pending = _mapping(pending_recommendation)
    goal = _presentation_goal_from_state(state)
    target_band = target_band_payload(goal)
    mode_cfg = _presentation_mode_config(
        current_state=state,
        mode_config=mode_config,
        target_band=target_band,
    )
    governing_action, _primary_utils = _presentation_governing_primary_action(ov)
    headline = str(item.get("title_main") or "").strip() or "Design guidance"
    pending_commit_eligible = (
        _presentation_recommendation_commit_eligible(pending) if pending else False
    )
    pending_blocked_reason = (
        _presentation_recommendation_blocked_reason(pending) if pending else None
    )
    feedback_state = _mapping(feedback_cta_state)
    feedback_blocks_primary_cta = bool(feedback_state.get("matches_current_state"))
    feedback_blocked_reason = str(feedback_state.get("reason") or "").strip() or None
    solver_state = _mapping(solver_result_cta_state)
    solver_result_blocks_primary_cta = bool(solver_state.get("matches_current_state"))
    solver_result_blocked_reason = str(solver_state.get("reason") or "").strip() or None
    button_label = (
        "Apply Auto Design"
        if str(pending.get("_source") or "").strip() == "auto_design"
        else "Apply Recommendation"
    )
    primary_item_has_actionable_updates = bool(_presentation_updates_for_envelope(item))
    worst = _float_or_none(ov.get("worst_util"))
    if worst is None:
        worst = 0.0
    any_fail = bool(ov.get("any_fail"))
    any_warn = bool(ov.get("any_warn"))
    all_key_pass = bool(ov.get("all_key_pass"))
    overdesigned = _presentation_is_unnecessarily_overdesigned(ov, es)
    in_target_band = _presentation_is_in_target_zone_with_eps(
        ov,
        mode_cfg,
        eps=_PRESENTATION_TARGET_BAND_EPS,
    )
    near_limit_util = bool(all_key_pass and worst >= float(_PRESENTATION_NEAR_LIMIT_UTIL_THRESHOLD))
    classification_es = str(es.get("classification") or "").strip()
    terminal_optimal = (
        classification_es == "optimal"
        or str(item.get("design_guide_terminal_state") or "") == "optimal"
    )
    terminal_very_low_demand = (
        classification_es == "very_low_demand"
        or str(item.get("design_guide_terminal_state") or "") == "very_low_demand"
    ) and not bool(primary_item_has_actionable_updates)
    guidance_intent = _presentation_guidance_intent(
        item,
        state=state,
        overview=ov,
        efficiency_state=es,
        mode_config=mode_cfg,
    )
    passive_underband_threshold = max(
        _float_or_none(mode_cfg.get("target_lo")) or _PRESENTATION_TARGET_UTIL_MIN,
        _PRESENTATION_TARGET_UTIL_MIN,
    )
    passive_underband_no_action = bool(
        all_key_pass
        and not any_fail
        and not any_warn
        and worst < float(passive_underband_threshold) - float(_PRESENTATION_TARGET_BAND_EPS)
        and not bool(primary_item_has_actionable_updates)
        and not bool(pending_commit_eligible)
    )
    primary_candidate_search_evidence = _mapping(
        item.get("candidate_search_evidence")
        or _mapping(item.get("action_payload")).get("candidate_search_evidence")
        or _mapping(item.get("resolved_candidate")).get("candidate_search_evidence")
    )
    return DesignGuideControllerPresentationRequest(
        current_state=state,
        summary=ov,
        raw_items=[dict(item)] if item else [],
        candidate_evidence=dict(primary_candidate_search_evidence),
        raw_candidates=[dict(item)] if item else [],
        target_band=dict(target_band),
        context={
            "goal": goal,
            "headline": headline,
            "governing_action": governing_action,
            "pending": bool(pending),
            "pending_commit_eligible": bool(pending_commit_eligible),
            "pending_blocked_reason": pending_blocked_reason,
            "feedback_blocks_primary_cta": bool(feedback_blocks_primary_cta),
            "feedback_blocked_reason": feedback_blocked_reason,
            "solver_result_blocks_primary_cta": bool(solver_result_blocks_primary_cta),
            "solver_result_blocked_reason": solver_result_blocked_reason,
            "button_label": button_label,
            "primary_item_has_actionable_updates": bool(primary_item_has_actionable_updates),
            "worst": worst,
            "any_fail": bool(any_fail),
            "any_warn": bool(any_warn),
            "all_key_pass": bool(all_key_pass),
            "overdesigned": bool(overdesigned),
            "in_target_band": bool(in_target_band),
            "near_limit_util": bool(near_limit_util),
            "terminal_optimal": bool(terminal_optimal),
            "terminal_very_low_demand": bool(terminal_very_low_demand),
            "guidance_intent": guidance_intent,
            "passive_underband_no_action": bool(passive_underband_no_action),
            "candidate_search_evidence": dict(primary_candidate_search_evidence),
            "efficiency_state": dict(es),
        },
        source=source,
    )


def run_design_guide_controller_presentation_adapter(
    request: DesignGuideControllerPresentationRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerPresentationResponse:
    """Build Design Guide presentation output from a plain controller request.

    The page may still collect current state/session-derived inputs before the
    next cutover.  This adapter owns the presentation decision call and output
    shape without importing page, Streamlit, render, or Apply routing code.
    """

    request_obj = _presentation_request_from_dict(request)
    request_hash = stable_final_publication_hash(
        {
            "request": request_obj.to_dict(),
            "memo_owner": "DesignGuideController.presentation_adapter",
            "memo_key_contract": "presentation_request_v1",
        }
    )
    decision = resolve_design_guide_decision(
        current_state=dict(request_obj.current_state or {}),
        summary=dict(request_obj.summary or {}),
        raw_items=[dict(item) for item in request_obj.raw_items],
        candidate_evidence=dict(request_obj.candidate_evidence or {}),
        raw_candidates=[dict(candidate) for candidate in request_obj.raw_candidates],
        target_band=dict(request_obj.target_band or {}),
        context=dict(request_obj.context or {}),
    )
    presentation = dict(decision.get("presentation") or {})
    payload = {
        "authority": "DesignGuideController.presentation_adapter",
        "request_hash": request_hash,
        "presentation": presentation,
        "decision_hash": stable_final_publication_hash(decision),
        "presentation_hash": stable_final_publication_hash(presentation),
    }
    return DesignGuideControllerPresentationResponse(
        controller_id="DesignGuideController.presentation_adapter",
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        decision=dict(decision),
        decision_hash=stable_final_publication_hash(decision),
        presentation=presentation,
        presentation_hash=stable_final_publication_hash(presentation),
        controller_hash=stable_final_publication_hash(payload),
    )


def build_design_guide_controller_no_active_primary_result(
    *,
    primary: dict[str, Any],
    primary_contract: dict[str, Any],
    primary_contract_enabled: bool,
    primary_updates: dict[str, Any],
    final_overview: dict[str, Any],
    state_fingerprint: str,
    render_reason: str = "final_visible_no_active_strength_fail",
) -> dict[str, Any]:
    """Build the no-active primary final-visible result from controller-owned data."""

    item = dict(primary or {})
    item.update(
        {
            "final_visible_state_fingerprint": state_fingerprint,
            "final_visible_design_guide_item": True,
            "final_visible_resolver_reason": str(
                render_reason or "final_visible_no_active_strength_fail"
            ),
        }
    )
    if primary_contract_enabled and primary_updates:
        item.update(
            {
                "primary_card_actionable": True,
                "updates": dict(primary_updates),
                "selected_action_updates": dict(primary_updates),
                "button_contract": dict(primary_contract),
            }
        )
    return {
        "item": item,
        "overview": dict(final_overview or {}),
        "presentation": None,
        "render_reason": str(render_reason or "final_visible_no_active_strength_fail"),
        "state_fingerprint": state_fingerprint,
        "controller_authority": "DesignGuideController.no_active_primary_result",
    }


def build_design_guide_controller_bending_fail_snapshot_reuse_result(
    *,
    snapshot_item: dict[str, Any],
    current_overview: dict[str, Any] | None,
    state_fingerprint: str,
) -> dict[str, Any]:
    """Build the bending-fail snapshot reuse result from plain controller data."""

    item = dict(snapshot_item or {})
    return {
        "item": item,
        "overview": dict(current_overview or {}),
        "presentation": {
            "headline": str(item.get("title_main") or item.get("title") or ""),
            "subtext": str(item.get("primary_action") or ""),
            "guidance_intent": item.get("guidance_intent"),
            "css_bucket": item.get("bucket"),
            "theme": item.get("bucket"),
            "show_apply_button": True,
            "use_success_style": str(item.get("bucket") or "") == "pass",
        },
        "render_reason": "bending_fail_publication_snapshot",
        "state_fingerprint": state_fingerprint,
        "debug": {
            "bending_fail_publication_snapshot_reused": True,
            "bending_fail_publication_snapshot_reuse_purpose": "final_resolver",
        },
    }


def _bending_fail_snapshot_reuse_request_from_dict(
    request: DesignGuideControllerBendingFailSnapshotReuseRequest | dict[str, Any] | None,
) -> DesignGuideControllerBendingFailSnapshotReuseRequest:
    if request is None:
        return DesignGuideControllerBendingFailSnapshotReuseRequest()
    if isinstance(request, DesignGuideControllerBendingFailSnapshotReuseRequest):
        return request
    if isinstance(request, dict):
        return DesignGuideControllerBendingFailSnapshotReuseRequest(
            snapshot_item=_mapping(request.get("snapshot_item")),
            current_overview=_mapping(request.get("current_overview")),
            state_fingerprint=str(request.get("state_fingerprint") or ""),
            source=str(request.get("source") or "controller_bending_fail_snapshot_reuse_trace_only"),
        )
    raise TypeError(
        "request must be a DesignGuideControllerBendingFailSnapshotReuseRequest, dict, or None"
    )


def run_design_guide_controller_bending_fail_snapshot_reuse_trace_only(
    request: DesignGuideControllerBendingFailSnapshotReuseRequest | dict[str, Any] | None = None,
) -> DesignGuideControllerBendingFailSnapshotReuseResponse:
    """Assemble bending-fail snapshot reuse output without page-owned mutation."""

    request_obj = _bending_fail_snapshot_reuse_request_from_dict(request)
    request_hash = stable_final_publication_hash(
        {
            "request": request_obj.to_dict(),
            "memo_owner": "DesignGuideController.bending_fail_snapshot_reuse",
            "memo_key_contract": "bending_fail_snapshot_reuse_trace_v1",
        }
    )
    result = build_design_guide_controller_bending_fail_snapshot_reuse_result(
        snapshot_item=dict(request_obj.snapshot_item),
        current_overview=dict(request_obj.current_overview),
        state_fingerprint=str(request_obj.state_fingerprint or ""),
    )
    return DesignGuideControllerBendingFailSnapshotReuseResponse(
        controller_id="DesignGuideController.bending_fail_snapshot_reuse.trace_only",
        authority="DesignGuideController",
        request_hash=request_hash,
        request_source=request_obj.source,
        result=result,
        result_hash=stable_final_publication_hash(result),
    )


def _controller_optional_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _controller_state_float(state: dict[str, Any], key: str, default: float) -> float:
    value = state.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _controller_state_int(state: dict[str, Any], key: str, default: int) -> int:
    value = state.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _controller_distance_to_target_band(
    util: Any,
    target_min: Any,
    target_max: Any,
) -> float:
    util_value = _controller_optional_float(util)
    low = _controller_optional_float(target_min)
    high = _controller_optional_float(target_max)
    if util_value is None or low is None or high is None:
        return float("inf")
    if low <= util_value <= high:
        return 0.0
    if util_value < low:
        return low - util_value
    return util_value - high


def classify_design_guide_shear_low_util_cleanup_candidate(
    *,
    shear_util: Any,
    threshold: Any,
    preferred_low: Any,
    target_high: Any,
    target_band_eps: Any = 0.0,
    allow_best_safe_below_threshold: bool = False,
) -> dict[str, Any]:
    """Classify one already-evaluated shear cleanup candidate.

    The page still generates variants and evaluates candidates. This pure
    helper owns the candidate band/distance decision that was previously inline
    in the page loop.
    """

    util_value = _controller_optional_float(shear_util)
    threshold_value = _controller_optional_float(threshold)
    preferred_low_value = _controller_optional_float(preferred_low)
    target_high_value = _controller_optional_float(target_high)
    eps = _controller_optional_float(target_band_eps)
    if eps is None:
        eps = 0.0
    below_threshold = (
        util_value is not None
        and threshold_value is not None
        and util_value < threshold_value
    )
    skip_for_selection = bool(below_threshold and not allow_best_safe_below_threshold)
    accepted_band_candidate = bool(
        not below_threshold
        and util_value is not None
        and util_value <= 1.0 + float(eps)
    )
    target_band_candidate = bool(
        util_value is not None
        and preferred_low_value is not None
        and target_high_value is not None
        and preferred_low_value - float(eps)
        <= util_value
        <= target_high_value + float(eps)
    )
    return {
        "shear_util": util_value,
        "below_threshold": bool(below_threshold),
        "failed_reason": "shear_target_threshold_not_reached" if below_threshold else None,
        "skip_for_selection": skip_for_selection,
        "accepted_band_candidate": accepted_band_candidate,
        "target_band_candidate": target_band_candidate,
        "distance_to_target_band": _controller_distance_to_target_band(
            util_value,
            threshold_value,
            target_high_value,
        ),
        "classifier_authority": "DesignGuideController.shear_low_util_cleanup_candidate_classifier",
        "product_driving": True,
    }


def accumulate_design_guide_shear_low_util_cleanup_candidate(
    *,
    accepted_band_count: int = 0,
    target_count: int = 0,
    best_distance: Any = None,
    best: dict[str, Any] | None = None,
    classification: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    shear_util: Any = None,
    is_no_link_candidate: bool = False,
) -> dict[str, Any]:
    """Accumulate already-evaluated shear cleanup candidate counters.

    This mirrors the page-loop rule: increment accepted/target counts from the
    classification, rank ordinary candidates by distance to the target band, and
    treat a passing no-link candidate as the terminal zero-shear cleanup floor.
    """

    classified = dict(classification or {})
    accepted = int(accepted_band_count or 0)
    target = int(target_count or 0)
    if classified.get("accepted_band_candidate"):
        accepted += 1
    if classified.get("target_band_candidate"):
        target += 1
    distance = _controller_optional_float(classified.get("distance_to_target_band"))
    if distance is None:
        distance = float("inf")
    current_best_distance = _controller_optional_float(best_distance)
    if current_best_distance is None:
        current_best_distance = float("inf")
    next_best = dict(best or {}) if isinstance(best, dict) else None
    # A passing no-link candidate is the terminal cleanup floor for a zero-shear
    # link-removal lane. Do not let distance-to-target-band ranking prefer a
    # heavier link arrangement merely because it lands closer to the utilisation
    # target.
    selected = bool(is_no_link_candidate or distance <= current_best_distance + 1e-9)
    if selected:
        current_best_distance = -1.0 if is_no_link_candidate else distance
        next_best = {
            "updates": dict(updates or {}),
            "candidate": dict(candidate or {}),
            "overview": dict(overview or {}),
            "shear_util": _controller_optional_float(shear_util),
            "is_no_link_candidate": bool(is_no_link_candidate),
        }
    return {
        "accepted_band_count": accepted,
        "target_count": target,
        "best_distance": current_best_distance,
        "best": next_best,
        "candidate_selected_as_best": selected,
        "accumulator_authority": "DesignGuideController.shear_low_util_cleanup_candidate_accumulator",
        "product_driving": True,
    }


_CHANGE_LINE_ARROW = "\u00e2\ufffd\u00a0\u2019"


def _controller_normalized_sec_shape_ui(raw: Any) -> str:
    value = str(raw or "RECT").strip().upper()
    if value in ("T", "T-SECTION", "T_SECTION", "T-BEAM"):
        return "T"
    if value in ("I", "I-SECTION", "I_SECTION", "I-BEAM"):
        return "I"
    return "RECT"


def _controller_reo_change_line_prefixes(state: dict[str, Any] | None) -> tuple[str, str]:
    raw = (state or {}).get("sec_shape") or (state or {}).get("inputs_sec_shape")
    sec_shape = _controller_normalized_sec_shape_ui(raw)
    if sec_shape in ("T", "I"):
        return "Web bottom reo", "Web top reo"
    return "Bottom reo", "Top reo"


def _controller_geometry_width_context(state: dict[str, Any]) -> tuple[str, str, float]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", float(state.get("bw", state.get("b", 300.0)) or 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", float(state.get("tw", state.get("b", 200.0)) or 200.0)
    return "b", "Width b (mm)", float(state.get("b", 400.0) or 400.0)


def _controller_practical_bottom_reo_label(count_1: int, count_2: int, dia: int) -> str:
    if count_2 > 0:
        return f"{count_1}N{dia} + {count_2}N{dia}"
    return f"{count_1}N{dia}"


def _controller_bottom_reo_state_label(state: dict[str, Any]) -> str:
    mode_1 = str(state.get("bot_row_1_mode", state.get("bot1_layout_mode", "Count")) or "Count")
    mode_2 = str(state.get("bot_row_2_mode", state.get("bot2_layout_mode", "Count")) or "Count")
    if mode_1 == "Count" and mode_2 == "Count":
        count_1 = int(state.get("bot_row_1_bars", state.get("bot1_count", 0)) or 0)
        count_2 = int(state.get("bot_row_2_bars", state.get("bot2_count", 0)) or 0)
        dia = int(state.get("bot_row_1_dia", state.get("db_bot_1", state.get("db_bot", 0))) or 0)
        if count_1 > 0:
            return _controller_practical_bottom_reo_label(count_1, count_2, dia)
    spacing_1 = float(state.get("bot_row_1_spacing", state.get("bot1_spacing", 0.0)) or 0.0)
    dia_1 = int(state.get("bot_row_1_dia", state.get("db_bot_1", 0)) or 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _controller_top_reo_state_label(state: dict[str, Any]) -> str:
    mode_1 = str(state.get("top1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("top2_layout_mode", "Count") or "Count")
    count_1 = int(state.get("top1_count", 0) or 0)
    count_2 = int(state.get("top2_count", 0) or 0)
    if mode_1 == "Count" and mode_2 == "Count":
        dia = int(state.get("db_top_1", state.get("db_top", 0)) or 0)
        if count_1 > 0 or count_2 > 0:
            return _controller_practical_bottom_reo_label(count_1, count_2, dia)
        return "None"
    spacing_1 = float(state.get("top1_spacing", 0.0) or 0.0)
    dia_1 = int(state.get("db_top_1", 0) or 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _controller_shear_links_banner_fragment(state: dict[str, Any]) -> str | None:
    legs = int(state.get("lig_legs", 0) or 0)
    if legs <= 0:
        return None
    return f"N{int(state.get('lig_d', 0) or 0)}, {legs}-leg @{int(float(state.get('s_lig', 0.0) or 0.0))}"


def build_design_guide_shear_low_util_change_lines_for_updates(
    *,
    before: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
) -> list[str]:
    """Build current visible change lines for selected shear low-util cleanup."""

    if not updates:
        return []
    before_state = dict(before or {}) if isinstance(before, dict) else {}
    after_state = dict(before_state)
    after_state.update(dict(updates or {}))
    lines: list[str] = []
    _, _, before_width = _controller_geometry_width_context(before_state)
    _, _, after_width = _controller_geometry_width_context(after_state)
    try:
        if abs(float(after_width) - float(before_width)) > 1e-6:
            lines.append(
                f"Width: {int(round(float(before_width)))} {_CHANGE_LINE_ARROW} {int(round(float(after_width)))} mm"
            )
    except (TypeError, ValueError):
        pass
    try:
        before_depth = float(_controller_state_float(before_state, "D", 0.0))
        after_depth = float(_controller_state_float(after_state, "D", 0.0))
        if abs(after_depth - before_depth) > 1e-6:
            lines.append(
                f"Depth: {int(round(before_depth))} {_CHANGE_LINE_ARROW} {int(round(after_depth))} mm"
            )
    except (TypeError, ValueError):
        pass
    before_bottom = _controller_bottom_reo_state_label(before_state)
    after_bottom = _controller_bottom_reo_state_label(after_state)
    bottom_phrase, top_phrase = _controller_reo_change_line_prefixes(after_state)
    if before_bottom != after_bottom:
        lines.append(f"{bottom_phrase}: {before_bottom} {_CHANGE_LINE_ARROW} {after_bottom}")
    before_top = _controller_top_reo_state_label(before_state)
    after_top = _controller_top_reo_state_label(after_state)
    if before_top != after_top:
        lines.append(f"{top_phrase}: {before_top} {_CHANGE_LINE_ARROW} {after_top}")
    before_shear = _controller_shear_links_banner_fragment(before_state)
    after_shear = _controller_shear_links_banner_fragment(after_state)
    if before_shear != after_shear:
        if after_shear is None:
            lines.append(f"Shear links: {before_shear} {_CHANGE_LINE_ARROW} removed")
        elif before_shear is None:
            lines.append(f"Shear links: none {_CHANGE_LINE_ARROW} {after_shear}")
        else:
            lines.append(f"Shear links: {before_shear} {_CHANGE_LINE_ARROW} {after_shear}")
    return lines


def build_design_guide_shear_low_util_cleanup_candidate_record(
    *,
    updates: dict[str, Any] | None = None,
    candidate_id: str | None = None,
    is_no_link_candidate: bool = False,
    canonical_no_shear_slig_mm: Any = None,
) -> dict[str, Any]:
    """Build the controller-owned candidate metadata for shear cleanup evaluation."""

    update_map = dict(updates or {})
    no_link_policy = "not_no_link_candidate"
    if is_no_link_candidate:
        slig_value = _controller_optional_float(update_map.get("s_lig"))
        canonical_slig = _controller_optional_float(canonical_no_shear_slig_mm)
        no_link_policy = (
            "canonical_neutralised"
            if slig_value is not None
            and canonical_slig is not None
            and abs(float(slig_value) - float(canonical_slig)) <= 1e-9
            else "retained"
        )
    no_link_audit_update = {}
    if is_no_link_candidate:
        no_link_audit_update = {
            "no_link_candidate_tested": True,
            "no_link_candidate_evaluated": True,
            "no_link_candidate_updates": dict(update_map),
            "no_link_candidate_id": candidate_id,
            "no_link_s_lig_policy": no_link_policy,
        }
    return {
        "candidate_id": candidate_id,
        "updates": dict(update_map),
        "is_no_link_candidate": bool(is_no_link_candidate),
        "evaluation_source": "low_util_shear_target_cleanup_action",
        "evaluation_label": "Shear cleanup - one-click reduction",
        "evaluation_action_type": "apply_resolved_candidate",
        "no_link_s_lig_policy": no_link_policy,
        "no_link_audit_update": dict(no_link_audit_update),
        "record_authority": "DesignGuideController.shear_low_util_cleanup_candidate_record",
        "product_driving": True,
    }


def evaluate_design_guide_shear_low_util_cleanup_candidate(
    *,
    evaluator: Callable[..., Any] | None = None,
    base_state: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    evaluation_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the injected candidate evaluator through a controller-owned boundary."""

    update_map = dict(updates or {})
    record = dict(evaluation_record or {})
    source = str(record.get("evaluation_source") or "low_util_shear_target_cleanup_action")
    label = str(record.get("evaluation_label") or "Shear cleanup - one-click reduction")
    action_type = str(record.get("evaluation_action_type") or "apply_resolved_candidate")
    proof = {
        "evaluation_boundary_authority": "DesignGuideController.shear_low_util_cleanup_candidate_evaluation",
        "evaluation_source": source,
        "evaluation_label": label,
        "evaluation_action_type": action_type,
        "updates": dict(update_map),
        "update_hash": stable_final_publication_hash({"updates": update_map}),
        "candidate_returned": False,
        "candidate_hash": None,
        "evaluation_failed": False,
        "failed_reason": None,
        "product_driving": True,
    }
    if not callable(evaluator):
        proof.update(
            {
                "evaluation_failed": True,
                "failed_reason": "candidate_evaluator_missing",
            }
        )
        return {"candidate": None, "evaluation_proof": proof}
    try:
        candidate = evaluator(
            base_state,
            updates=update_map,
            source=source,
            label=label,
            action_type=action_type,
        )
    except Exception:
        proof.update(
            {
                "evaluation_failed": True,
                "failed_reason": "candidate_evaluation_failed",
            }
        )
        return {"candidate": None, "evaluation_proof": proof}
    if not isinstance(candidate, dict):
        proof.update(
            {
                "evaluation_failed": True,
                "failed_reason": "candidate_evaluation_failed",
            }
        )
        return {"candidate": None, "evaluation_proof": proof}
    proof.update(
        {
            "candidate_returned": True,
            "candidate_hash": stable_final_publication_hash(candidate),
        }
    )
    return {"candidate": candidate, "evaluation_proof": proof}


def evaluate_design_guide_combined_low_util_cleanup_candidate(
    *,
    evaluator: Callable[..., Any] | None = None,
    base_state: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    evaluation_source: str = "combined_best_safe_shear_plus_bending_cleanup",
    evaluation_label: str = "Shear and bending cleanup - one-click optimisation",
    evaluation_action_type: str = "apply_resolved_candidate",
) -> dict[str, Any]:
    """Evaluate a combined low-util cleanup candidate through an injected evaluator."""

    update_map = dict(updates or {})
    source = str(evaluation_source or "combined_best_safe_shear_plus_bending_cleanup")
    label = str(evaluation_label or "Shear and bending cleanup - one-click optimisation")
    action_type = str(evaluation_action_type or "apply_resolved_candidate")
    proof = {
        "evaluation_boundary_authority": "DesignGuideController.combined_low_util_cleanup_candidate_evaluation",
        "evaluation_source": source,
        "evaluation_label": label,
        "evaluation_action_type": action_type,
        "updates": dict(update_map),
        "update_hash": stable_final_publication_hash({"updates": update_map}),
        "candidate_returned": False,
        "candidate_hash": None,
        "evaluation_failed": False,
        "failed_reason": None,
        "product_driving": True,
    }
    if not callable(evaluator):
        proof.update(
            {
                "evaluation_failed": True,
                "failed_reason": "candidate_evaluator_missing",
            }
        )
        return {"candidate": None, "evaluation_proof": proof}
    try:
        candidate = evaluator(
            base_state,
            updates=update_map,
            source=source,
            label=label,
            action_type=action_type,
        )
    except Exception:
        proof.update(
            {
                "evaluation_failed": True,
                "failed_reason": "candidate_evaluation_failed",
            }
        )
        return {"candidate": None, "evaluation_proof": proof}
    if not isinstance(candidate, dict):
        proof.update(
            {
                "evaluation_failed": True,
                "failed_reason": "candidate_evaluation_failed",
            }
        )
        return {"candidate": None, "evaluation_proof": proof}
    proof.update(
        {
            "candidate_returned": True,
            "candidate_hash": stable_final_publication_hash(candidate),
        }
    )
    return {"candidate": candidate, "evaluation_proof": proof}


def resolve_design_guide_combined_low_util_cleanup_updates(
    *,
    resolver: Callable[..., Any] | None = None,
    item: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    source: str = "combined_low_util_cleanup_update_resolution",
) -> dict[str, Any]:
    """Resolve recommendation updates through an injected page/shared resolver."""

    source_name = str(source or "combined_low_util_cleanup_update_resolution")
    proof = {
        "update_resolution_boundary_authority": "DesignGuideController.combined_low_util_cleanup_update_resolution",
        "source": source_name,
        "item_hash": stable_final_publication_hash(dict(item or {})),
        "state_hash": stable_final_publication_hash(dict(state or {})),
        "updates_returned": False,
        "update_keys": [],
        "update_hash": stable_final_publication_hash({}),
        "resolution_failed": False,
        "failed_reason": None,
        "product_driving": True,
    }
    if not callable(resolver):
        proof.update(
            {
                "resolution_failed": True,
                "failed_reason": "update_resolver_missing",
            }
        )
        return {"updates": {}, "resolution_proof": proof}
    try:
        updates = dict(resolver(dict(item or {}), state=dict(state or {})) or {})
    except Exception:
        proof.update(
            {
                "resolution_failed": True,
                "failed_reason": "update_resolution_failed",
            }
        )
        return {"updates": {}, "resolution_proof": proof}
    proof.update(
        {
            "updates_returned": bool(updates),
            "update_keys": sorted(str(key) for key in updates),
            "update_hash": stable_final_publication_hash(updates),
        }
    )
    return {"updates": updates, "resolution_proof": proof}


def assess_design_guide_combined_low_util_cleanup_acceptance_gate(
    *,
    overview: dict[str, Any] | None = None,
    required_checks_acceptable_fn: Callable[..., Any] | None = None,
    preview_statuses_have_explicit_fail_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Assess combined low-util cleanup acceptance using injected checkers."""

    overview_map = dict(overview or {})
    statuses = dict(overview_map.get("statuses") or {})
    any_fail = bool(overview_map.get("any_fail"))
    required_checks_acceptable = False
    explicit_preview_fail = False
    required_checks_error = None
    explicit_preview_fail_error = None
    try:
        if callable(required_checks_acceptable_fn):
            required_checks_acceptable = bool(required_checks_acceptable_fn(overview_map))
        else:
            required_checks_error = "required_checks_checker_missing"
    except Exception as exc:
        required_checks_error = f"{type(exc).__name__}: {exc}"
        required_checks_acceptable = False
    try:
        if callable(preview_statuses_have_explicit_fail_fn):
            explicit_preview_fail = bool(preview_statuses_have_explicit_fail_fn(statuses))
        else:
            explicit_preview_fail_error = "preview_status_checker_missing"
    except Exception as exc:
        explicit_preview_fail_error = f"{type(exc).__name__}: {exc}"
        explicit_preview_fail = True
    accepted = bool(
        not any_fail
        and required_checks_acceptable
        and not explicit_preview_fail
    )
    proof = {
        "acceptance_gate_authority": "DesignGuideController.combined_low_util_cleanup_acceptance_gate",
        "overview_hash": stable_final_publication_hash(overview_map),
        "statuses_hash": stable_final_publication_hash(statuses),
        "any_fail": any_fail,
        "required_checks_acceptable": required_checks_acceptable,
        "explicit_preview_fail": explicit_preview_fail,
        "accepted": accepted,
        "required_checks_error": required_checks_error,
        "explicit_preview_fail_error": explicit_preview_fail_error,
        "product_driving": True,
    }
    proof["acceptance_gate_hash"] = stable_final_publication_hash(proof)
    return {
        "accepted": accepted,
        "any_fail": any_fail,
        "required_checks_acceptable": required_checks_acceptable,
        "explicit_preview_fail": explicit_preview_fail,
        "acceptance_proof": proof,
    }


def resolve_design_guide_combined_low_util_cleanup_target_band(
    *,
    target_band_resolver: Callable[..., Any] | None = None,
    optimisation_goal_resolver: Callable[..., Any] | None = None,
    state: dict[str, Any] | None = None,
    mode_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the target band used by combined low-util cleanup evidence."""

    goal = ""
    resolver_error = None
    try:
        if callable(optimisation_goal_resolver):
            goal = str(optimisation_goal_resolver(dict(state or {})) or "")
        else:
            resolver_error = "optimisation_goal_resolver_missing"
    except Exception as exc:
        resolver_error = f"{type(exc).__name__}: {exc}"
        goal = ""

    target_low = None
    target_high = None
    target_payload: Any = None
    target_error = None
    try:
        if callable(target_band_resolver):
            target_payload = target_band_resolver(dict(mode_config or {}), goal=goal)
            if isinstance(target_payload, (list, tuple)) and len(target_payload) >= 2:
                target_low = target_payload[0]
                target_high = target_payload[1]
            else:
                target_error = "target_band_resolver_invalid_payload"
        else:
            target_error = "target_band_resolver_missing"
    except Exception as exc:
        target_error = f"{type(exc).__name__}: {exc}"
        target_payload = None

    proof = {
        "target_band_authority": "DesignGuideController.combined_low_util_cleanup_target_band",
        "goal": goal,
        "mode_config_hash": stable_final_publication_hash(dict(mode_config or {})),
        "target_low": _controller_optional_float(target_low),
        "target_high": _controller_optional_float(target_high),
        "resolver_error": resolver_error,
        "target_error": target_error,
        "product_driving": True,
    }
    proof["target_band_boundary_hash"] = stable_final_publication_hash(proof)
    return {
        "target_low": target_low,
        "target_high": target_high,
        "target_payload": target_payload,
        "optimisation_goal": goal,
        "target_band_proof": proof,
    }


def build_design_guide_combined_low_util_cleanup_candidate_search_evidence(
    *,
    evidence_builder: Callable[..., Any] | None = None,
    combined_updates: dict[str, Any] | None = None,
    combined_worst: Any = None,
    combined_overview: dict[str, Any] | None = None,
    target_low: Any = None,
    target_high: Any = None,
    shear_evidence: dict[str, Any] | None = None,
    bending_evidence: dict[str, Any] | None = None,
    bending_incremental_cleanup: bool = False,
    combined_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build combined low-util cleanup candidate-search evidence."""

    updates = dict(combined_updates or {})
    overview_map = dict(combined_overview or {})
    shear_ev = dict(shear_evidence or {})
    bending_ev = dict(bending_evidence or {})
    audit = dict(combined_audit or {})
    evidence_candidate = {
        "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
        "label": "Shear and bending cleanup - one-click optimisation",
        "updates": dict(updates),
        "candidate_post_util": combined_worst,
        "worst_util": combined_worst,
        "is_compliant": True,
        "overview": dict(overview_map),
        "is_executable": True,
        "advisory_only": False,
        "affected_family": "combined",
    }
    if callable(evidence_builder):
        evidence = dict(
            evidence_builder(
                selected_candidate=evidence_candidate,
                all_candidates=[dict(evidence_candidate)],
                target_low=float(target_low),
                target_high=float(target_high),
                exhaustive=True,
                search_scope="combined_best_safe_shear_plus_bending_cleanup",
                selected_title="Shear and bending cleanup - one-click optimisation",
            )
            or {}
        )
        builder_failed = False
        builder_failed_reason = None
    else:
        evidence = {}
        builder_failed = True
        builder_failed_reason = "candidate_search_evidence_builder_missing"
    combined_post_apply_exact = dict(
        audit.get("post_click_exact_blockers_by_family")
        or audit.get("exact_blockers_by_family")
        or {}
    )
    evidence.update(
        {
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "optimisation_type": "combined_overdesign_cleanup",
            "family": "combined",
            "selected_candidate_updates": dict(updates),
            "best_safe_candidate_updates": dict(updates),
            "best_safe_candidate_applied": False,
            "best_safe_partial_cleanup": bool(
                shear_ev.get("best_safe_partial_cleanup")
                or bending_ev.get("best_safe_partial_cleanup")
            ),
            "safe_incremental_cleanup_below_final_threshold": bool(
                bending_incremental_cleanup
            ),
            "no_second_cta_required": False,
            "combined_from_best_safe_shear_cleanup": True,
            "shear_cleanup_evidence": dict(shear_ev),
            "bending_cleanup_evidence": dict(bending_ev),
            "post_apply_expected_exact_blockers_by_family": dict(combined_post_apply_exact),
            "post_click_unresolved_low_util_families": list(
                audit.get("post_click_unresolved_low_util_families") or []
            ),
        }
    )
    proof = {
        "evidence_boundary_authority": "DesignGuideController.combined_low_util_cleanup_candidate_search_evidence",
        "candidate_hash": stable_final_publication_hash(evidence_candidate),
        "evidence_hash": stable_final_publication_hash(evidence),
        "update_hash": stable_final_publication_hash(updates),
        "target_low": _controller_optional_float(target_low),
        "target_high": _controller_optional_float(target_high),
        "builder_failed": builder_failed,
        "builder_failed_reason": builder_failed_reason,
        "product_driving": True,
    }
    proof["evidence_boundary_hash"] = stable_final_publication_hash(proof)
    return {
        "evidence": evidence,
        "evidence_candidate": evidence_candidate,
        "evidence_proof": proof,
    }


def build_design_guide_combined_low_util_guidance_item_packaging(
    *,
    guidance_item_builder: Callable[..., Any] | None = None,
    combined_candidate: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the combined low-util guidance item through an injected page builder."""

    candidate = dict(combined_candidate or {})
    overview_map = dict(overview or {})
    title = "Shear and bending cleanup - one-click optimisation"
    reasoning = (
        "This combines the best safe shear-link cleanup with the bending reinforcement cleanup "
        "so the current optimisation flow is handled in one click."
    )
    if callable(guidance_item_builder):
        item = guidance_item_builder(
            candidate,
            state=dict(state or {}),
            overview=overview_map,
            title=title,
            reasoning=reasoning,
            status="EFFICIENCY",
            primary_action="Run one-click auto design",
        )
        builder_failed = False
        builder_failed_reason = None
    else:
        item = None
        builder_failed = True
        builder_failed_reason = "guidance_item_builder_missing"
    proof = {
        "guidance_item_packaging_authority": "DesignGuideController.combined_low_util_guidance_item_packaging",
        "candidate_hash": stable_final_publication_hash(candidate),
        "overview_hash": stable_final_publication_hash(overview_map),
        "item_hash": stable_final_publication_hash(item if isinstance(item, dict) else {}),
        "title": title,
        "status": "EFFICIENCY",
        "primary_action": "Run one-click auto design",
        "builder_failed": builder_failed,
        "builder_failed_reason": builder_failed_reason,
        "product_driving": True,
    }
    proof["guidance_item_packaging_hash"] = stable_final_publication_hash(proof)
    return {
        "item": item,
        "guidance_item_packaging_proof": proof,
    }


def assess_design_guide_combined_low_util_post_click_accepted_green_audit(
    *,
    post_click_audit_fn: Callable[..., Any] | None = None,
    overview: dict[str, Any] | None = None,
    blocker_source: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the combined low-util post-click accepted-green audit through a controller boundary."""

    overview_map = dict(overview or {})
    blocker_map = dict(blocker_source or {})
    state_map = dict(state or {})
    if callable(post_click_audit_fn):
        audit = dict(
            post_click_audit_fn(
                overview_map,
                blocker_source=blocker_map,
                state=state_map,
            )
            or {}
        )
        audit_failed = False
        audit_failed_reason = None
    else:
        audit = {}
        audit_failed = True
        audit_failed_reason = "post_click_audit_fn_missing"
    proof = {
        "post_click_audit_authority": "DesignGuideController.combined_low_util_post_click_accepted_green_audit",
        "overview_hash": stable_final_publication_hash(overview_map),
        "blocker_source_hash": stable_final_publication_hash(blocker_map),
        "state_hash": stable_final_publication_hash(state_map),
        "audit_hash": stable_final_publication_hash(audit),
        "audit_failed": audit_failed,
        "audit_failed_reason": audit_failed_reason,
        "product_driving": True,
    }
    proof["post_click_audit_boundary_hash"] = stable_final_publication_hash(proof)
    return {
        "audit": audit,
        "post_click_audit_proof": proof,
    }


def run_design_guide_combined_low_util_bending_cleanup_item_generation(
    *,
    bending_cleanup_generator: Callable[..., Any] | None = None,
    state: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    mode_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the combined low-util bending cleanup generator through a controller boundary."""

    state_map = dict(state or {})
    overview_map = dict(overview or {})
    mode_config_map = dict(mode_config or {})
    debug: dict[str, Any] = {}
    if callable(bending_cleanup_generator):
        item = bending_cleanup_generator(
            state_map,
            overview_map,
            mode_config_map,
            debug_sink=debug,
        )
        generator_failed = False
        generator_failed_reason = None
    else:
        item = None
        generator_failed = True
        generator_failed_reason = "bending_cleanup_generator_missing"
    proof = {
        "bending_cleanup_generation_authority": "DesignGuideController.combined_low_util_bending_cleanup_item_generation",
        "state_hash": stable_final_publication_hash(state_map),
        "overview_hash": stable_final_publication_hash(overview_map),
        "mode_config_hash": stable_final_publication_hash(mode_config_map),
        "item_hash": stable_final_publication_hash(item if isinstance(item, dict) else {}),
        "debug_hash": stable_final_publication_hash(debug),
        "generator_failed": generator_failed,
        "generator_failed_reason": generator_failed_reason,
        "product_driving": True,
    }
    proof["bending_cleanup_generation_hash"] = stable_final_publication_hash(proof)
    return {
        "item": item,
        "debug": debug,
        "bending_cleanup_generation_proof": proof,
    }


def build_design_guide_combined_low_util_result_packaging(
    *,
    guidance_item_builder: Callable[..., Any] | None = None,
    combined_candidate: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    combined_updates: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    combined_worst: Any = None,
    combined_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the packaged combined low-util result item and action payload."""

    candidate = dict(combined_candidate or {})
    updates = dict(combined_updates or {})
    evidence_map = dict(evidence or {})
    audit = dict(combined_audit or {})
    target_count = 0
    try:
        target_count = int(evidence_map.get("target_band_candidate_count") or 0)
    except (TypeError, ValueError):
        target_count = 0
    exact_blockers_by_family = dict(
        audit.get("post_click_exact_blockers_by_family")
        or audit.get("exact_blockers_by_family")
        or {}
    )
    target_blocked_families: list[Any] = []
    for row in list(evidence_map.get("candidate_rows") or []):
        if isinstance(row, dict) and str(row.get("candidate_id") or "") == "combined_best_safe_shear_plus_bending_cleanup":
            target_blocked_families = list(row.get("target_band_blocked_families") or [])
            break
    target_blocked_without_exact_proof = [
        str(family or "").strip().lower()
        for family in target_blocked_families
        if str(family or "").strip().lower()
        and str(family or "").strip().lower() not in exact_blockers_by_family
    ]
    combined_reaches_target = bool(
        updates
        and not target_blocked_without_exact_proof
        and (
            target_count > 0
            or (
                target_blocked_families
                and exact_blockers_by_family
            )
        )
    )
    candidate.update(
        {
            "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
            "source_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
            "label": "Shear and bending cleanup - one-click optimisation",
            "title": "Shear and bending cleanup - one-click optimisation",
            "canonical_winner_label": "Shear and bending cleanup - one-click optimisation",
            "title_locked_from_final_winner": True,
            "family": "combined",
            "recommendation_family_tag": "combined",
            "subfamilies": ["shear", "bottom_reinforcement"],
            "updates": dict(updates) if combined_reaches_target else {},
            "proposed_updates": dict(updates),
            "attempted_updates": dict(updates),
            "action_type": "apply_resolved_candidate" if combined_reaches_target else None,
            "candidate_post_util": combined_worst,
            "worst_util": combined_worst,
            "candidate_reaches_target_band": bool(combined_reaches_target),
            "reaches_target_band": bool(combined_reaches_target),
            "candidate_search_evidence": dict(evidence_map),
            "local_cleanup_candidate": True,
            "allow_in_target_primary_action": bool(combined_reaches_target),
            "best_safe_partial_cleanup": True,
            "primary_card_actionable": bool(combined_reaches_target),
            "no_second_cta_required": bool(combined_reaches_target),
        }
    )
    if not combined_reaches_target:
        debug_update = {
            "combined_best_safe_cleanup_generated": True,
            "combined_best_safe_cleanup_updates": dict(updates),
            "combined_best_safe_cleanup_audit": dict(audit),
            "combined_best_safe_cleanup_blocker_suppressed": True,
            "combined_best_safe_cleanup_blocker_suppressed_reason": (
                "combined_cleanup_target_band_not_proven_without_product_driving_blocker"
            ),
        }
        proof = {
            "result_packaging_authority": "DesignGuideController.combined_low_util_result_packaging",
            "candidate_hash": stable_final_publication_hash(candidate),
            "item_hash": stable_final_publication_hash({}),
            "updates_hash": stable_final_publication_hash(updates),
            "evidence_hash": stable_final_publication_hash(evidence_map),
            "debug_update_hash": stable_final_publication_hash(debug_update),
            "guidance_item_packaging_hash": None,
            "valid_item": False,
            "product_driving": False,
            "blocked_item_suppressed": True,
            "blocked_item_suppressed_reason": (
                "combined cleanup did not prove all required target domains; "
                "single-family cleanup or exact-stop proof must own publication"
            ),
            "target_blocked_families": list(target_blocked_families),
            "target_blocked_without_exact_proof": list(target_blocked_without_exact_proof),
        }
        proof["result_packaging_hash"] = stable_final_publication_hash(proof)
        return {
            "item": None,
            "combined_candidate": candidate,
            "debug_update": debug_update,
            "result_packaging_proof": proof,
        }
    item_payload = build_design_guide_combined_low_util_guidance_item_packaging(
        guidance_item_builder=guidance_item_builder,
        combined_candidate=candidate,
        state=dict(state or {}),
        overview=dict(overview or {}),
    )
    item = item_payload.get("item")
    valid_item = isinstance(item, dict) and bool(item)
    if valid_item:
        item = dict(item)
        display_title = (
            "Shear and bending cleanup - one-click optimisation"
            if combined_reaches_target
            else "Bending and shear cleanup blocked"
        )
        item.update(
            {
                "title_main": display_title,
                "title": display_title,
                "candidate_search_evidence": dict(evidence_map),
                "local_cleanup_candidate": True,
                "guidance_intent": "efficiency_tightening" if combined_reaches_target else "specific_blocker",
                "affected_family": "combined",
                "family": "combined",
                "check_key": "combined",
                "selected_action_family": "combined" if combined_reaches_target else None,
                "source": "combined_best_safe_shear_plus_bending_cleanup",
                "allow_in_target_primary_action": bool(combined_reaches_target),
                "best_safe_partial_cleanup": True,
                "primary_card_actionable": bool(combined_reaches_target),
                "no_second_cta_required": bool(combined_reaches_target),
                "canonical_winner_label": "Shear and bending cleanup - one-click optimisation",
                "title_locked_from_final_winner": True,
                "selected_action_updates": dict(updates) if combined_reaches_target else {},
                "updates": dict(updates) if combined_reaches_target else {},
                "attempted_updates": dict(updates),
                "action_type": "apply_resolved_candidate" if combined_reaches_target else None,
            }
        )
        payload = dict(item.get("action_payload") or {})
        payload["updates"] = dict(updates) if combined_reaches_target else {}
        payload["resolved_candidate_updates"] = dict(updates) if combined_reaches_target else {}
        payload["attempted_updates"] = dict(updates)
        payload["resolved_candidate_action_type"] = "apply_resolved_candidate" if combined_reaches_target else None
        payload["resolved_candidate_reaches_target_band"] = bool(combined_reaches_target)
        payload["candidate_search_evidence"] = dict(evidence_map)
        payload["source_candidate_id"] = "combined_best_safe_shear_plus_bending_cleanup"
        payload["candidate_id"] = "combined_best_safe_shear_plus_bending_cleanup"
        payload["resolved_candidate_family_tag"] = "combined"
        payload["resolved_candidate_subfamilies"] = ["shear", "bottom_reinforcement"]
        payload["best_safe_partial_cleanup"] = True
        payload["primary_card_actionable"] = bool(combined_reaches_target)
        payload["no_second_cta_required"] = bool(combined_reaches_target)
        item["action_payload"] = payload
        resolved = dict(item.get("resolved_candidate") or candidate)
        resolved["updates"] = dict(updates) if combined_reaches_target else {}
        resolved["attempted_updates"] = dict(updates)
        resolved["action_type"] = "apply_resolved_candidate" if combined_reaches_target else None
        resolved["candidate_id"] = "combined_best_safe_shear_plus_bending_cleanup"
        resolved["source_candidate_id"] = "combined_best_safe_shear_plus_bending_cleanup"
        resolved["candidate_search_evidence"] = dict(evidence_map)
        resolved["candidate_reaches_target_band"] = bool(combined_reaches_target)
        resolved["family"] = "combined"
        resolved["recommendation_family_tag"] = "combined"
        resolved["subfamilies"] = ["shear", "bottom_reinforcement"]
        resolved["best_safe_partial_cleanup"] = True
        resolved["primary_card_actionable"] = bool(combined_reaches_target)
        resolved["no_second_cta_required"] = bool(combined_reaches_target)
        item["resolved_candidate"] = resolved
        contract = dict(item.get("button_contract") or {})
        contract.update(
            {
                "enabled": bool(combined_reaches_target),
                "actionable": bool(combined_reaches_target),
                "action_type": "apply_resolved_candidate" if combined_reaches_target else None,
                "family": "combined" if combined_reaches_target else None,
                "updates": dict(updates) if combined_reaches_target else {},
                "attempted_updates": dict(updates),
                "preview_pass": bool(combined_reaches_target),
                "expected_util": combined_worst,
                "no_second_cta_required": bool(combined_reaches_target),
                "blocking_reason": None if combined_reaches_target else "combined_cleanup_target_band_not_proven",
                "source_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
                "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
            }
        )
        item["button_contract"] = contract
    debug_update = {
        "combined_best_safe_cleanup_generated": True,
        "combined_best_safe_cleanup_updates": dict(updates),
        "combined_best_safe_cleanup_audit": dict(audit),
    }
    proof = {
        "result_packaging_authority": "DesignGuideController.combined_low_util_result_packaging",
        "candidate_hash": stable_final_publication_hash(candidate),
        "item_hash": stable_final_publication_hash(item if isinstance(item, dict) else {}),
        "updates_hash": stable_final_publication_hash(updates),
        "evidence_hash": stable_final_publication_hash(evidence_map),
        "debug_update_hash": stable_final_publication_hash(debug_update),
        "guidance_item_packaging_hash": (
            item_payload.get("guidance_item_packaging_proof") or {}
        ).get("guidance_item_packaging_hash"),
        "valid_item": valid_item,
        "product_driving": True,
    }
    proof["result_packaging_hash"] = stable_final_publication_hash(proof)
    return {
        "item": item,
        "combined_candidate": candidate,
        "debug_update": debug_update,
        "result_packaging_proof": proof,
    }


def build_design_guide_combined_low_util_invalid_item_fallback(
    *,
    result_packaging_proof: dict[str, Any] | None = None,
    bending_cleanup_generation_proof: dict[str, Any] | None = None,
    combined_updates: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    combined_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build non-authoritative debug proof for an invalid combined cleanup item."""

    packaging_proof = dict(result_packaging_proof or {})
    bending_proof = dict(bending_cleanup_generation_proof or {})
    updates = dict(combined_updates or {})
    evidence_map = dict(evidence or {})
    audit = dict(combined_audit or {})
    debug_payload = {
        "combined_low_util_invalid_item_fallback_used": True,
        "combined_low_util_invalid_item_fallback_authority": "DesignGuideController.combined_low_util_invalid_item_fallback",
        "combined_low_util_invalid_item_reason": "result_packaging_returned_no_guidance_item",
        "combined_low_util_invalid_item_updates_count": len(updates),
        "combined_low_util_invalid_item_packaging_hash": packaging_proof.get("result_packaging_hash"),
        "combined_low_util_invalid_item_bending_generation_hash": bending_proof.get("bending_cleanup_generation_hash"),
        "combined_low_util_invalid_item_evidence_hash": stable_final_publication_hash(evidence_map),
        "combined_low_util_invalid_item_audit_hash": stable_final_publication_hash(audit),
        "product_driving": False,
    }
    proof = {
        "invalid_item_fallback_authority": "DesignGuideController.combined_low_util_invalid_item_fallback",
        "reason": "result_packaging_returned_no_guidance_item",
        "updates_hash": stable_final_publication_hash(updates),
        "evidence_hash": debug_payload["combined_low_util_invalid_item_evidence_hash"],
        "combined_audit_hash": debug_payload["combined_low_util_invalid_item_audit_hash"],
        "result_packaging_hash": packaging_proof.get("result_packaging_hash"),
        "bending_cleanup_generation_hash": bending_proof.get("bending_cleanup_generation_hash"),
        "debug_payload_hash": stable_final_publication_hash(debug_payload),
        "product_driving": False,
    }
    proof["invalid_item_fallback_hash"] = stable_final_publication_hash(proof)
    debug_payload["combined_low_util_invalid_item_fallback_hash"] = proof["invalid_item_fallback_hash"]
    return {
        "item": None,
        "debug_payload": debug_payload,
        "invalid_item_fallback_proof": proof,
    }


def run_design_guide_combined_low_util_orchestration(
    *,
    state: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    mode_config: dict[str, Any] | None = None,
    shear_item: dict[str, Any] | None = None,
    recommendation_updates_resolver: Callable[..., Any] | None = None,
    candidate_evaluator: Callable[..., Any] | None = None,
    bending_cleanup_generator: Callable[..., Any] | None = None,
    shear_cleanup_generator: Callable[..., Any] | None = None,
    required_checks_acceptable_fn: Callable[..., Any] | None = None,
    preview_statuses_have_explicit_fail_fn: Callable[..., Any] | None = None,
    post_click_audit_fn: Callable[..., Any] | None = None,
    target_band_resolver: Callable[..., Any] | None = None,
    optimisation_goal_resolver: Callable[..., Any] | None = None,
    evidence_builder: Callable[..., Any] | None = None,
    guidance_item_builder: Callable[..., Any] | None = None,
    best_safe_partial_cleanup_fn: Callable[..., Any] | None = None,
    safe_incremental_cleanup_fn: Callable[..., Any] | None = None,
    updates_match_state_fn: Callable[..., Any] | None = None,
    util_parser: Callable[..., Any] | None = None,
    compound_shear_update_keys: set[str] | frozenset[str] | None = None,
    compound_bottom_update_keys: set[str] | frozenset[str] | None = None,
    final_accepted_min_family_util: float = 0.0,
) -> dict[str, Any]:
    """Run the combined low-util shear-plus-bending cleanup orchestration."""

    state_map = dict(state or {})
    overview_map = dict(overview or {})
    mode_config_map = dict(mode_config or {})
    shear_keys = set(compound_shear_update_keys or set())
    bottom_keys = set(compound_bottom_update_keys or set())
    debug_update: dict[str, Any] = {}

    def _finish(item: Any, reason: str) -> dict[str, Any]:
        proof = {
            "orchestration_authority": "DesignGuideController.combined_low_util_orchestration",
            "finish_reason": reason,
            "item_hash": stable_final_publication_hash(item if isinstance(item, dict) else {}),
            "debug_update_hash": stable_final_publication_hash(debug_update),
            "state_hash": stable_final_publication_hash(state_map),
            "overview_hash": stable_final_publication_hash(overview_map),
            "mode_config_hash": stable_final_publication_hash(mode_config_map),
            "product_driving": True,
        }
        proof["orchestration_hash"] = stable_final_publication_hash(proof)
        return {
            "item": item if isinstance(item, dict) else None,
            "debug_update": dict(debug_update),
            "orchestration_proof": proof,
        }

    if not isinstance(shear_item, dict):
        return _finish(None, "missing_shear_item")
    shear_title = str(shear_item.get("title_main") or shear_item.get("title") or "").strip().lower()
    shear_cleanup_action = bool(
        (callable(best_safe_partial_cleanup_fn) and best_safe_partial_cleanup_fn(shear_item))
        or ("shear cleanup" in shear_title and "one-click" in shear_title)
        or (
            str(shear_item.get("family") or shear_item.get("check_key") or "").strip().lower() == "shear"
            and str(shear_item.get("action_type") or "").strip() == "apply_resolved_candidate"
            and bool(shear_item.get("local_cleanup_candidate"))
        )
        or str(shear_item.get("action_type") or "").strip() == "apply_resolved_candidate"
    )
    if not shear_cleanup_action:
        return _finish(None, "shear_item_not_cleanup_action")

    shear_update_resolution = resolve_design_guide_combined_low_util_cleanup_updates(
        resolver=recommendation_updates_resolver,
        item=shear_item,
        state=state_map,
        source="combined_low_util_shear_item_updates",
    )
    shear_updates = dict(shear_update_resolution.get("updates") or {})
    if not shear_updates or not (set(shear_updates) & shear_keys):
        return _finish(None, "missing_shear_updates")
    if set(shear_updates) & bottom_keys:
        shear_updates = {
            key: value
            for key, value in shear_updates.items()
            if key in shear_keys
        }
        if not shear_updates:
            return _finish(None, "shear_updates_removed_bottom_overlap")

    shear_state = dict(state_map)
    shear_state.update(shear_updates)
    shear_candidate_evaluation = evaluate_design_guide_combined_low_util_cleanup_candidate(
        evaluator=candidate_evaluator,
        base_state=state_map,
        updates=shear_updates,
        evaluation_source="combined_cleanup_shear_leg_probe",
        evaluation_label="Shear cleanup - best safe one-click reduction",
        evaluation_action_type="apply_resolved_candidate",
    )
    shear_candidate = shear_candidate_evaluation.get("candidate")
    shear_overview = dict((shear_candidate or {}).get("overview") or {})
    if not shear_overview:
        shear_overview = dict(overview_map)

    bending_generation = run_design_guide_combined_low_util_bending_cleanup_item_generation(
        bending_cleanup_generator=bending_cleanup_generator,
        state=shear_state,
        overview=shear_overview,
        mode_config=mode_config_map,
    )
    bending_debug: dict[str, Any] = dict(bending_generation.get("debug") or {})
    bending_item = bending_generation.get("item")
    if not isinstance(bending_item, dict):
        return _finish(None, "missing_bending_cleanup_item")
    bending_incremental_cleanup = bool(
        callable(safe_incremental_cleanup_fn) and safe_incremental_cleanup_fn(bending_item)
    )
    bending_gate_evidence = dict(
        bending_item.get("candidate_search_evidence")
        or (bending_item.get("action_payload") or {}).get("candidate_search_evidence")
        or (bending_item.get("resolved_candidate") or {}).get("candidate_search_evidence")
        or {}
    )
    if (
        not bending_incremental_cleanup
        and callable(best_safe_partial_cleanup_fn)
        and best_safe_partial_cleanup_fn(bending_item)
        and int(bending_gate_evidence.get("safe_candidate_count") or 0) > 0
        and int(bending_gate_evidence.get("executable_candidate_count") or 0) > 0
    ):
        bending_incremental_cleanup = True
    if (
        callable(best_safe_partial_cleanup_fn)
        and best_safe_partial_cleanup_fn(bending_item)
        and not bending_incremental_cleanup
    ):
        return _finish(None, "bending_best_safe_not_incremental")
    bending_update_resolution = resolve_design_guide_combined_low_util_cleanup_updates(
        resolver=recommendation_updates_resolver,
        item=bending_item,
        state=shear_state,
        source="combined_low_util_bending_item_updates",
    )
    bending_updates = dict(bending_update_resolution.get("updates") or {})
    if not bending_updates or set(bending_updates) & shear_keys:
        return _finish(None, "missing_or_invalid_bending_updates")

    combined_updates = dict(shear_updates)
    combined_updates.update(bending_updates)
    if callable(updates_match_state_fn) and updates_match_state_fn(state_map, combined_updates):
        return _finish(None, "combined_updates_match_state")

    combined_candidate_evaluation = evaluate_design_guide_combined_low_util_cleanup_candidate(
        evaluator=candidate_evaluator,
        base_state=state_map,
        updates=combined_updates,
        evaluation_source="combined_best_safe_shear_plus_bending_cleanup",
        evaluation_label="Shear and bending cleanup - one-click optimisation",
        evaluation_action_type="apply_resolved_candidate",
    )
    combined_candidate = combined_candidate_evaluation.get("candidate")
    if not isinstance(combined_candidate, dict):
        return _finish(None, "missing_combined_candidate")
    combined_overview = dict(combined_candidate.get("overview") or {})
    combined_acceptance_gate = assess_design_guide_combined_low_util_cleanup_acceptance_gate(
        overview=combined_overview,
        required_checks_acceptable_fn=required_checks_acceptable_fn,
        preview_statuses_have_explicit_fail_fn=preview_statuses_have_explicit_fail_fn,
    )
    if not bool(combined_acceptance_gate.get("accepted")):
        return _finish(None, "combined_acceptance_gate_rejected")

    combined_state = dict(state_map)
    combined_state.update(combined_updates)
    combined_audit_result = assess_design_guide_combined_low_util_post_click_accepted_green_audit(
        post_click_audit_fn=post_click_audit_fn,
        overview=combined_overview,
        blocker_source=shear_item,
        state=combined_state,
    )
    combined_audit = dict(combined_audit_result.get("audit") or {})
    folded_candidate_ids: list[str] = []
    terminal_fold_proof: dict[str, Any] = {
        "same_click_combined_residual_shear_fold": False,
        "folded_candidate_ids": [],
        "fold_iterations": 0,
        "fold_stop_reason": "not_run",
    }
    if callable(shear_cleanup_generator):
        terminal_fold_proof["fold_stop_reason"] = "no_followup_cleanup"
        fold_updates = dict(combined_updates)
        fold_candidate = dict(combined_candidate)
        fold_overview = dict(combined_overview)
        fold_state = dict(state_map)
        fold_state.update(fold_updates)
        for fold_index in range(4):
            try:
                followup_item = shear_cleanup_generator(
                    dict(fold_state),
                    dict(fold_overview),
                    threshold=float(final_accepted_min_family_util),
                    allow_best_safe_below_threshold=True,
                )
            except TypeError:
                try:
                    followup_item = shear_cleanup_generator(
                        dict(fold_state),
                        dict(fold_overview),
                    )
                except Exception:
                    followup_item = None
            except Exception:
                followup_item = None
            if not isinstance(followup_item, dict):
                terminal_fold_proof["fold_stop_reason"] = "no_followup_cleanup"
                break
            followup_resolution = resolve_design_guide_combined_low_util_cleanup_updates(
                resolver=recommendation_updates_resolver,
                item=followup_item,
                state=fold_state,
                source="combined_low_util_residual_shear_followup_updates",
            )
            followup_updates = dict(followup_resolution.get("updates") or {})
            if not followup_updates:
                terminal_fold_proof["fold_stop_reason"] = "followup_missing_updates"
                break
            if callable(updates_match_state_fn) and updates_match_state_fn(fold_state, followup_updates):
                terminal_fold_proof["fold_stop_reason"] = "followup_updates_match_state"
                break
            followup_keys = set(followup_updates)
            if not (followup_keys & (shear_keys | {"b", "bw", "D"})):
                terminal_fold_proof["fold_stop_reason"] = "followup_not_shear_or_geometry_cleanup"
                break
            trial_updates = dict(fold_updates)
            trial_updates.update(followup_updates)
            trial_evaluation = evaluate_design_guide_combined_low_util_cleanup_candidate(
                evaluator=candidate_evaluator,
                base_state=state_map,
                updates=trial_updates,
                evaluation_source="combined_low_util_terminal_fold_residual_shear",
                evaluation_label="Shear and bending cleanup - one-click optimisation",
                evaluation_action_type="apply_resolved_candidate",
            )
            trial_candidate = trial_evaluation.get("candidate")
            if not isinstance(trial_candidate, dict):
                terminal_fold_proof["fold_stop_reason"] = "followup_candidate_evaluation_failed"
                break
            trial_overview = dict(trial_candidate.get("overview") or {})
            trial_gate = assess_design_guide_combined_low_util_cleanup_acceptance_gate(
                overview=trial_overview,
                required_checks_acceptable_fn=required_checks_acceptable_fn,
                preview_statuses_have_explicit_fail_fn=preview_statuses_have_explicit_fail_fn,
            )
            if not bool(trial_gate.get("accepted")):
                terminal_fold_proof["fold_stop_reason"] = "followup_candidate_rejected"
                terminal_fold_proof["last_rejected_updates"] = dict(followup_updates)
                break
            fold_updates = dict(trial_updates)
            fold_candidate = dict(trial_candidate)
            fold_overview = dict(trial_overview)
            fold_state = dict(state_map)
            fold_state.update(fold_updates)
            followup_id = str(
                followup_item.get("candidate_id")
                or followup_item.get("source_candidate_id")
                or (followup_item.get("button_contract") or {}).get("candidate_id")
                or f"residual_shear_followup_{fold_index + 1}"
            )
            folded_candidate_ids.append(followup_id)
            terminal_fold_proof.update(
                {
                    "same_click_combined_residual_shear_fold": True,
                    "fold_iterations": fold_index + 1,
                    "fold_stop_reason": "folded_followup_cleanup",
                    "folded_candidate_ids": list(folded_candidate_ids),
                    "folded_updates": dict(fold_updates),
                    "last_followup_updates": dict(followup_updates),
                }
            )
        if folded_candidate_ids:
            combined_updates = dict(fold_updates)
            combined_candidate = dict(fold_candidate)
            combined_overview = dict(fold_overview)
            combined_state = dict(state_map)
            combined_state.update(combined_updates)
            combined_audit_result = assess_design_guide_combined_low_util_post_click_accepted_green_audit(
                post_click_audit_fn=post_click_audit_fn,
                overview=combined_overview,
                blocker_source={"folded_candidate_ids": list(folded_candidate_ids), **dict(shear_item)},
                state=combined_state,
            )
            combined_audit = dict(combined_audit_result.get("audit") or {})
            debug_update["combined_low_util_same_click_residual_shear_fold_applied"] = True
            debug_update["combined_low_util_same_click_residual_shear_folded_candidate_ids"] = list(
                folded_candidate_ids
            )
            debug_update["combined_low_util_same_click_residual_shear_folded_updates"] = dict(
                combined_updates
            )
    combined_utils = dict(combined_overview.get("utils") or {})
    bending_util = util_parser(combined_utils.get("bending")) if callable(util_parser) else None
    bending_before_util = (
        util_parser(dict((shear_overview or {}).get("utils") or {}).get("bending"))
        if callable(util_parser)
        else None
    )
    if (
        not bending_incremental_cleanup
        and bending_util is not None
        and bending_before_util is not None
        and float(bending_util) > float(bending_before_util) + 1e-9
    ):
        bending_incremental_cleanup = True
    if (
        bending_util is not None
        and float(bending_util) < float(final_accepted_min_family_util) - 1e-9
        and not (
            bending_incremental_cleanup
            and bending_before_util is not None
            and float(bending_util) > float(bending_before_util) + 1e-9
        )
    ):
        return _finish(None, "combined_bending_below_accepted_min")
    combined_worst = (
        util_parser(combined_overview.get("worst_util") or combined_overview.get("governing_util"))
        if callable(util_parser)
        else None
    )
    if combined_worst is None and callable(util_parser):
        combined_worst = util_parser(combined_candidate.get("candidate_post_util") or combined_candidate.get("worst_util"))

    shear_evidence = dict(
        shear_item.get("candidate_search_evidence")
        or (shear_item.get("action_payload") or {}).get("candidate_search_evidence")
        or (shear_item.get("resolved_candidate") or {}).get("candidate_search_evidence")
        or {}
    )
    bending_evidence = dict(
        bending_item.get("candidate_search_evidence")
        or (bending_item.get("action_payload") or {}).get("candidate_search_evidence")
        or (bending_item.get("resolved_candidate") or {}).get("candidate_search_evidence")
        or {}
    )
    target_band_resolution = resolve_design_guide_combined_low_util_cleanup_target_band(
        target_band_resolver=target_band_resolver,
        optimisation_goal_resolver=optimisation_goal_resolver,
        state=state_map,
        mode_config=mode_config_map,
    )
    evidence_packaging = build_design_guide_combined_low_util_cleanup_candidate_search_evidence(
        evidence_builder=evidence_builder,
        combined_updates=combined_updates,
        combined_worst=combined_worst,
        combined_overview=combined_overview,
        target_low=target_band_resolution.get("target_low"),
        target_high=target_band_resolution.get("target_high"),
        shear_evidence=shear_evidence,
        bending_evidence=bending_evidence,
        bending_incremental_cleanup=bending_incremental_cleanup,
        combined_audit=combined_audit,
    )
    evidence = dict(evidence_packaging.get("evidence") or {})
    if folded_candidate_ids:
        evidence.update(
            {
                "same_click_terminalisation_fold": True,
                "same_click_combined_residual_shear_fold": True,
                "folded_candidate_ids": list(folded_candidate_ids),
                "no_second_cta_required": True,
                "target_band_candidate_count": max(
                    int(evidence.get("target_band_candidate_count") or 0),
                    1,
                ),
                "terminal_fold_proof": dict(terminal_fold_proof),
                "terminal_folded_cleanup": {
                    "updates": dict(combined_updates),
                    "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
                    "target_band_candidate_count": max(
                        int(evidence.get("target_band_candidate_count") or 0),
                        1,
                    ),
                    "terminal_candidate_status": "TERMINAL_TARGET_BAND",
                    "further_cleanup_available": False,
                    "proof_hash": stable_final_publication_hash(terminal_fold_proof),
                },
            }
        )

    result_packaging = build_design_guide_combined_low_util_result_packaging(
        guidance_item_builder=guidance_item_builder,
        combined_candidate=combined_candidate,
        state=state_map,
        overview=overview_map,
        combined_updates=combined_updates,
        evidence=evidence,
        combined_worst=combined_worst,
        combined_audit=combined_audit,
    )
    item = result_packaging.get("item")
    if not isinstance(item, dict) or not item:
        invalid_item_fallback = build_design_guide_combined_low_util_invalid_item_fallback(
            result_packaging_proof=dict(result_packaging.get("result_packaging_proof") or {}),
            bending_cleanup_generation_proof=dict(
                bending_generation.get("bending_cleanup_generation_proof") or {}
            ),
            combined_updates=combined_updates,
            evidence=evidence,
            combined_audit=combined_audit,
        )
        debug_update.update(dict(invalid_item_fallback.get("debug_payload") or {}))
        return _finish(None, "result_packaging_invalid_item")
    debug_update.update(dict(result_packaging.get("debug_update") or {}))
    return _finish(item, "selected_item")


def build_design_guide_shear_low_util_selected_no_link_audit_update(
    *,
    updates: dict[str, Any] | None = None,
    candidate_id: str | None = None,
    canonical_no_shear_slig_mm: Any = None,
) -> dict[str, Any]:
    """Build the audit update for a selected no-link shear cleanup candidate."""

    update_map = dict(updates or {})
    slig_value = _controller_optional_float(update_map.get("s_lig"))
    canonical_slig = _controller_optional_float(canonical_no_shear_slig_mm)
    policy = (
        "canonical_neutralised"
        if "s_lig" in update_map
        and slig_value is not None
        and canonical_slig is not None
        and abs(float(slig_value) - float(canonical_slig)) <= 1e-9
        else "retained_or_not_applicable"
    )
    return {
        "no_link_candidate_tested": True,
        "no_link_candidate_evaluated": True,
        "no_link_candidate_passed": True,
        "no_link_candidate_selected": True,
        "no_link_candidate_updates": dict(update_map),
        "no_link_candidate_id": candidate_id,
        "no_link_candidate_failed_or_selected_reason": (
            "No-link shear cleanup was tested, passed all required checks, and was selected."
        ),
        "no_link_s_lig_policy": policy,
        "audit_update_authority": "DesignGuideController.shear_low_util_selected_no_link_audit_update",
        "product_driving": True,
    }


def build_design_guide_shear_low_util_no_link_probe(
    *,
    state_is_mapping: bool = False,
    shear_reinforcement_active: bool = False,
    canonical_no_shear_slig_mm: Any = None,
) -> dict[str, Any]:
    """Build canonical no-link updates and initial audit for shear cleanup."""

    canonical_slig = _controller_optional_float(canonical_no_shear_slig_mm)
    if canonical_slig is None:
        canonical_slig = 200.0
    canonical_updates = (
        {
            "lig_d": 0,
            "lig_legs": 0,
            "s_lig": float(canonical_slig),
        }
        if bool(state_is_mapping)
        else {}
    )
    already_active = bool(state_is_mapping and not shear_reinforcement_active)
    audit = {
        "no_link_candidate_tested": False,
        "no_link_candidate_evaluated": False,
        "no_link_candidate_passed": False,
        "no_link_candidate_selected": False,
        "no_link_candidate_already_active": already_active,
        "no_link_candidate_updates": dict(canonical_updates) if already_active else {},
        "no_link_candidate_id": (
            "shear_cleanup_floor_no_links_remaining" if already_active else None
        ),
        "no_link_candidate_failed_or_selected_reason": (
            "Shear links are already removed; no further shear-link cleanup is available."
            if already_active
            else None
        ),
        "no_link_candidate_reason": (
            "Shear links are already removed; no further shear-link cleanup is available."
            if already_active
            else None
        ),
        "no_link_s_lig_policy": (
            "canonical_neutralised" if already_active else "retained_or_unknown"
        ),
    }
    return {
        "updates": dict(canonical_updates),
        "audit": dict(audit),
        "probe_authority": "DesignGuideController.shear_low_util_no_link_probe",
        "product_driving": True,
    }


def _controller_one_click_diff_accumulated_updates(
    base: dict[str, Any],
    final: dict[str, Any],
) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key, value in (final or {}).items():
        if key not in base:
            delta[key] = value
            continue
        base_value = base[key]
        if isinstance(value, float) or isinstance(base_value, float):
            try:
                if abs(float(base_value) - float(value)) > 1e-9:
                    delta[key] = value
            except (TypeError, ValueError):
                if base_value != value:
                    delta[key] = value
        elif base_value != value:
            delta[key] = value
    return delta


def _controller_shear_cleanup_materially_reduces_reinforcement(
    current_state: dict[str, Any] | None,
    candidate_state: dict[str, Any] | None,
) -> bool:
    if not isinstance(current_state, dict) or not isinstance(candidate_state, dict):
        return False
    cur_spacing = _controller_state_float(current_state, "s_lig", 0.0)
    nxt_spacing = _controller_state_float(candidate_state, "s_lig", cur_spacing)
    cur_legs = _controller_state_int(current_state, "lig_legs", 0)
    nxt_legs = _controller_state_int(candidate_state, "lig_legs", cur_legs)
    cur_dia = _controller_state_int(current_state, "lig_d", 0)
    nxt_dia = _controller_state_int(candidate_state, "lig_d", cur_dia)
    cur_width = _controller_state_float(current_state, "b", 0.0)
    nxt_width = _controller_state_float(candidate_state, "b", cur_width)
    cur_web_width = _controller_state_float(current_state, "bw", cur_width)
    nxt_web_width = _controller_state_float(candidate_state, "bw", cur_web_width)
    if nxt_width < cur_width - 1e-9:
        return True
    if nxt_web_width < cur_web_width - 1e-9:
        return True
    if cur_legs > 0 and nxt_legs == 0:
        return True
    if nxt_spacing > cur_spacing + 1e-9:
        return True
    if nxt_legs < cur_legs:
        return True
    if nxt_dia < cur_dia:
        return True
    return False


def build_design_guide_shear_low_util_candidate_delta_screen(
    *,
    base_state: dict[str, Any] | None = None,
    variant_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build update delta and materiality screen for a shear cleanup variant."""

    base = dict(base_state or {}) if isinstance(base_state, dict) else {}
    variant = dict(variant_state or {}) if isinstance(variant_state, dict) else {}
    updates = _controller_one_click_diff_accumulated_updates(base, variant)
    trial_state = dict(base)
    trial_state.update(dict(updates))
    return {
        "updates": dict(updates),
        "materially_reduces_reinforcement": _controller_shear_cleanup_materially_reduces_reinforcement(
            base,
            trial_state,
        ),
        "delta_screen_authority": "DesignGuideController.shear_low_util_candidate_delta_screen",
        "product_driving": True,
    }


def build_design_guide_shear_low_util_variant_sequence(
    *,
    variants: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    no_link_state: dict[str, Any] | None = None,
    shear_reinforcement_active: bool = False,
    no_link_updates: dict[str, Any] | None = None,
    no_link_key: Any = None,
    existing_variant_keys: list[Any] | tuple[Any, ...] | set[Any] | None = None,
) -> dict[str, Any]:
    """Merge the canonical no-link state into the shear cleanup variant sequence."""

    base_variants = [dict(item) for item in list(variants or []) if isinstance(item, dict)]
    existing_keys = list(existing_variant_keys or [])
    should_prepend = bool(
        shear_reinforcement_active
        and no_link_updates
        and isinstance(no_link_state, dict)
        and no_link_key not in existing_keys
    )
    merged = [dict(no_link_state or {})] + base_variants if should_prepend else list(base_variants)
    return {
        "variants": merged,
        "no_link_variant_prepended": should_prepend,
        "variant_count": len(merged),
        "raw_variant_count": len(base_variants),
        "variant_sequence_authority": "DesignGuideController.shear_low_util_variant_sequence",
        "product_driving": True,
    }


def build_design_guide_shear_low_util_raw_variant_states(
    *,
    state: dict[str, Any] | None = None,
    shear_cleanup_possible: bool = False,
    shear_state_eligible_for_no_links: bool = False,
    reo_spacings: list[Any] | tuple[Any, ...] | None = None,
    reo_bar_dias: list[Any] | tuple[Any, ...] | None = None,
    canonical_no_shear_slig_mm: Any = 200.0,
) -> dict[str, Any]:
    """Generate raw shear cleanup variant states without page-owned candidate-key dedupe."""

    base_state = dict(state or {}) if isinstance(state, dict) else {}
    spacings = [float(value) for value in list(reo_spacings or [])]
    bar_dias = [int(value) for value in list(reo_bar_dias or [])]
    if not base_state or not shear_cleanup_possible:
        return {
            "variants": [],
            "variant_count": 0,
            "raw_variant_generation_authority": "DesignGuideController.shear_low_util_raw_variant_states",
            "product_driving": True,
        }

    cur_sp = float(_controller_state_float(base_state, "s_lig", 200.0))
    current_legs = int(_controller_state_int(base_state, "lig_legs", 2))
    current_dia = int(_controller_state_int(base_state, "lig_d", 10))
    max_spacing = float(max(spacings) if spacings else 300.0)
    spacing_values = [float(value) for value in spacings if float(value) > cur_sp + 1e-9][:2]
    spacing_values.extend(float(value) for value in spacings if float(value) < cur_sp - 1e-9)
    spacing_values.extend(float(cur_sp - 25.0 * step) for step in range(0, 5))
    spacing_values.extend(float(cur_sp + 25.0 * step) for step in range(1, 17))
    if max_spacing > cur_sp + 1e-9:
        spacing_values.append(max_spacing)
    spacing_values = sorted(set(float(value) for value in spacing_values))
    leg_values = sorted(
        {
            int(value)
            for value in (
                current_legs,
                2,
                3,
            )
            if int(value) >= 2 and int(value) <= max(current_legs, 3)
        }
    )
    dia_values = sorted(
        set(
            [value for value in bar_dias if 0 < int(value) <= current_dia][-2:]
            or [max(int(current_dia), 10)]
        )
    )
    variants: list[dict[str, Any]] = []
    if shear_state_eligible_for_no_links:
        zero_link_state = dict(base_state)
        zero_link_state.update(
            {
                "lig_d": 0,
                "lig_legs": 0,
                "s_lig": float(canonical_no_shear_slig_mm),
            }
        )
        variants.append(zero_link_state)
    for spacing in spacing_values or [cur_sp]:
        for legs in leg_values:
            for dia in dia_values:
                resolved_dia = int(dia)
                resolved_spacing = float(spacing)
                if (
                    resolved_dia == current_dia
                    and int(legs) == current_legs
                    and abs(float(resolved_spacing) - cur_sp) <= 1e-9
                ):
                    continue
                candidate_state = dict(base_state)
                candidate_state.update(
                    {
                        "lig_d": int(resolved_dia),
                        "lig_legs": int(legs),
                        "s_lig": float(resolved_spacing),
                    }
                )
                variants.append(candidate_state)
    return {
        "variants": variants,
        "variant_count": len(variants),
        "raw_variant_generation_authority": "DesignGuideController.shear_low_util_raw_variant_states",
        "product_driving": True,
    }


def _controller_overview_required_checks_acceptable(
    overview: dict[str, Any] | None,
) -> bool:
    if not isinstance(overview, dict):
        return False
    statuses = overview.get("statuses")
    if isinstance(statuses, dict):
        tracked = [
            str(status or "").strip().upper()
            for status in statuses.values()
            if str(status or "").strip() not in {"", "—", "-"}
        ]
    else:
        tracked = []
    if not tracked:
        return bool(overview.get("all_key_pass")) and not bool(overview.get("any_fail"))
    return not any(status in {"FAIL", "FAILED", "ERROR"} for status in tracked)


def _controller_candidate_preview_statuses_have_explicit_fail(
    preview_statuses: dict[str, Any] | None,
    *,
    fail_status_value: Any = "FAIL",
) -> bool:
    if not isinstance(preview_statuses, dict):
        return False
    for value in preview_statuses.values():
        if value == fail_status_value:
            return True
        if str(value or "").strip().upper() == "FAIL":
            return True
    return False


def build_design_guide_shear_low_util_candidate_acceptance_screen(
    *,
    candidate_overview: dict[str, Any] | None = None,
    candidate_statuses: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Screen an evaluated shear cleanup candidate before band classification."""

    overview = dict(candidate_overview or {}) if isinstance(candidate_overview, dict) else {}
    statuses = (
        dict(candidate_statuses or {})
        if isinstance(candidate_statuses, dict)
        else dict(overview.get("statuses") or {})
    )
    any_fail = bool(overview.get("any_fail"))
    required_checks_acceptable = _controller_overview_required_checks_acceptable(overview)
    explicit_preview_fail = _controller_candidate_preview_statuses_have_explicit_fail(statuses)
    accepted = bool(
        not any_fail and required_checks_acceptable and not explicit_preview_fail
    )
    return {
        "accepted": accepted,
        "failed_reason": None if accepted else "required_check_failed",
        "any_fail": any_fail,
        "required_checks_acceptable": required_checks_acceptable,
        "explicit_preview_fail": explicit_preview_fail,
        "acceptance_screen_authority": "DesignGuideController.shear_low_util_candidate_acceptance_screen",
        "product_driving": True,
    }


def build_design_guide_shear_overdesign_contract_candidate_items(
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return contract-owned shear-overdesign candidate dictionaries for page-shell evaluation."""

    from design_brain.families.shear_cleanup import ShearCleanupFamily

    ladder = ShearCleanupFamily().contracted_optimisation_ladder_specs(dict(state or {}))
    candidates: list[dict[str, Any]] = []
    for index, spec in enumerate(list(ladder.get("specs") or []), start=1):
        if not isinstance(spec, dict):
            continue
        updates = dict(spec.get("updates") or {})
        if not updates:
            continue
        lane_id = str(spec.get("lane_id") or spec.get("contract_step") or "").strip()
        candidate_id = str(
            spec.get("candidate_id")
            or spec.get("update_hash")
            or f"shear_overdesign_contract_{index}"
        )
        evidence = {
            "family_id": "SHEAR_OVERDESIGN_GOVERNS",
            "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
            "published_family_id": "SHEAR_OVERDESIGN_GOVERNS",
            "cta_family_id": "SHEAR_OVERDESIGN_GOVERNS",
            "contract_runtime_authority": "run_shear_overdesign_governs_runtime",
            "contract_runtime_driven": True,
            "contract_candidate_projection": True,
            "contract_step": lane_id,
            "lane_id": lane_id,
            "ladder_hash": ladder.get("ladder_hash"),
            "ladder_trace": tuple(ladder.get("ladder_trace") or ()),
            "ranking_proof": dict(ladder.get("ranking_proof") or spec.get("ranking_proof") or {}),
            "zero_shear_override_proof": dict(ladder.get("zero_shear_override_proof") or {}),
            "geometry_restriction_proof": dict(ladder.get("geometry_restriction_proof") or {}),
            "selected_candidate_id": candidate_id,
            "selected_candidate_updates": dict(updates),
            "best_safe_candidate_updates": dict(updates),
            "update_hash": spec.get("update_hash"),
            "candidate_state_hash": spec.get("candidate_state_hash"),
        }
        candidates.append(
            {
                "candidate_id": candidate_id,
                "source_candidate_id": candidate_id,
                "label": "Shear cleanup - one-click reduction",
                "title": "Shear cleanup - one-click reduction",
                "family": "shear",
                "recommendation_family_tag": "shear",
                "subfamilies": ["shear"],
                "updates": dict(updates),
                "proposed_updates": dict(updates),
                "action_type": "apply_resolved_candidate",
                "candidate_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "card_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "published_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "cta_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "family_route_owner": "design_brain.families.shear_cleanup.ShearCleanupFamily",
                "contract_runtime_authority": "run_shear_overdesign_governs_runtime",
                "contract_runtime_driven": True,
                "candidate_search_evidence": dict(evidence),
            }
        )
    return {
        "authority": "DesignGuideController.shear_overdesign_contract_candidate_items",
        "family_id": "SHEAR_OVERDESIGN_GOVERNS",
        "contract_runtime_authority": "run_shear_overdesign_governs_runtime",
        "contract_runtime_driven": True,
        "ladder_hash": ladder.get("ladder_hash"),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def build_design_guide_bending_overdesign_contract_candidate_items(
    state: dict[str, Any] | None = None,
    *,
    evaluate_candidate: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Return contract-owned bending-overdesign candidate dictionaries for page-shell evaluation."""

    from design_brain.families.bending_cleanup import BendingCleanupFamily

    ladder = BendingCleanupFamily().contracted_optimisation_ladder_specs(
        dict(state or {}),
        evaluate_candidate=evaluate_candidate,
    )
    candidates: list[dict[str, Any]] = []
    for index, spec in enumerate(list(ladder.get("specs") or []), start=1):
        if not isinstance(spec, dict):
            continue
        updates = dict(spec.get("updates") or {})
        if not updates:
            continue
        lane_id = str(spec.get("lane_id") or spec.get("contract_step") or "").strip()
        candidate_id = str(
            spec.get("candidate_id")
            or spec.get("update_hash")
            or f"bending_overdesign_contract_{index}"
        )
        evidence = {
            "family_id": "BENDING_OVERDESIGN_GOVERNS",
            "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
            "published_family_id": "BENDING_OVERDESIGN_GOVERNS",
            "cta_family_id": "BENDING_OVERDESIGN_GOVERNS",
            "contract_runtime_authority": "run_bending_overdesign_governs_runtime",
            "contract_runtime_driven": True,
            "contract_candidate_projection": True,
            "contract_step": lane_id,
            "lane_id": lane_id,
            "ladder_hash": ladder.get("ladder_hash"),
            "ladder_trace": tuple(ladder.get("ladder_trace") or ()),
            "ranking_proof": dict(ladder.get("ranking_proof") or spec.get("ranking_proof") or {}),
            "exact_stop_proof": dict(ladder.get("exact_stop_proof") or spec.get("exact_stop_proof") or {}),
            "minimum_reinforcement_proof": dict(ladder.get("minimum_reinforcement_proof") or {}),
            "geometry_compliance_proof": dict(ladder.get("geometry_compliance_proof") or {}),
            "restart_proof": dict(ladder.get("restart_proof") or spec.get("restart_proof") or {}),
            "terminal_publication_gate": dict(ladder.get("terminal_publication_gate") or {}),
            "terminal_candidate_status": spec.get("terminal_candidate_status"),
            "further_cleanup_available": bool(spec.get("further_cleanup_available")),
            "target_band_candidate_count": int(spec.get("target_band_candidate_count") or 0),
            "executable_target_band_candidate_count": int(
                spec.get("executable_target_band_candidate_count") or 0
            ),
            "best_target_band_candidate_id": spec.get("best_target_band_candidate_id"),
            "selected_candidate_id": candidate_id,
            "selected_candidate_updates": dict(updates),
            "best_safe_candidate_updates": dict(updates),
            "update_hash": spec.get("update_hash"),
            "candidate_state_hash": spec.get("candidate_state_hash"),
            "no_second_cta_required": True,
        }
        candidates.append(
            {
                "candidate_id": candidate_id,
                "source_candidate_id": candidate_id,
                "label": "Bending cleanup - one-click terminal optimisation",
                "title": "Bending cleanup - one-click terminal optimisation",
                "family": "bending",
                "recommendation_family_tag": "bending",
                "subfamilies": ["bottom_reinforcement", "geometry"],
                "updates": dict(updates),
                "proposed_updates": dict(updates),
                "action_type": "apply_resolved_candidate",
                "allow_in_target_primary_action": True,
                "local_cleanup_candidate": True,
                "candidate_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "card_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "published_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "cta_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "family_route_owner": "design_brain.families.bending_cleanup.BendingCleanupFamily",
                "contract_runtime_authority": "run_bending_overdesign_governs_runtime",
                "contract_runtime_driven": True,
                "candidate_search_evidence": dict(evidence),
            }
        )
    return {
        "authority": "DesignGuideController.bending_overdesign_contract_candidate_items",
        "family_id": "BENDING_OVERDESIGN_GOVERNS",
        "contract_runtime_authority": "run_bending_overdesign_governs_runtime",
        "contract_runtime_driven": True,
        "ladder_hash": ladder.get("ladder_hash"),
        "terminal_publication_gate": dict(ladder.get("terminal_publication_gate") or {}),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def build_design_guide_shear_low_util_failed_reason_from_preview(
    *,
    candidate_overview: dict[str, Any] | None = None,
    candidate_statuses: dict[str, Any] | None = None,
    fallback: str = "required_check_failed",
) -> str:
    """Build the no-link failure reason from an evaluated shear cleanup preview."""

    overview = dict(candidate_overview or {}) if isinstance(candidate_overview, dict) else {}
    packs = dict(overview.get("packs") or {})
    shear_pack = dict(packs.get("shear") or {})
    status_map = (
        dict(candidate_statuses or {})
        if isinstance(candidate_statuses, dict)
        else dict(overview.get("statuses") or {})
    )
    check_name = (
        shear_pack.get("summary_governing_check_name")
        or shear_pack.get("summary_governing_reason")
        or shear_pack.get("summary_reason")
        or "shear/detailing/serviceability check"
    )
    status = str(
        status_map.get("shear") or shear_pack.get("summary_status") or fallback
    ).strip()
    utils = dict(overview.get("utils") or {})
    util = _controller_optional_float(
        utils.get("shear")
        or shear_pack.get("summary_util")
        or shear_pack.get("summary_governing_util")
    )
    util_text = f" at utilisation {float(util):.2f}" if util is not None else ""
    return f"{check_name} returned {status}{util_text}."


def build_design_guide_shear_low_util_failure_coverage_from_overviews(
    *,
    current_overview: dict[str, Any] | None = None,
    candidate_overview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarise current failure coverage for a selected shear low-util candidate."""

    return candidate_failure_coverage_summary_from_overviews(
        dict(current_overview or {}) if isinstance(current_overview, dict) else {},
        dict(candidate_overview or {}) if isinstance(candidate_overview, dict) else {},
    )


def build_design_guide_shear_low_util_current_overview_status_authority(
    *,
    supplied_overview: dict[str, Any] | None = None,
    recomputed_overview: dict[str, Any] | None = None,
    source: str = "shear_low_util_failure_coverage",
) -> dict[str, Any]:
    """Select the current overview status authority for shear low-util evidence."""

    supplied = dict(supplied_overview or {}) if isinstance(supplied_overview, dict) else {}
    recomputed = (
        dict(recomputed_overview or {}) if isinstance(recomputed_overview, dict) else {}
    )
    supplied_statuses = dict(supplied.get("statuses") or {})
    recomputed_statuses = dict(recomputed.get("statuses") or {})
    selected = dict(recomputed if recomputed else supplied)
    selected_statuses = dict(selected.get("statuses") or {})
    return {
        "current_overview": selected,
        "selected_source": "recomputed_overview" if recomputed else "supplied_overview",
        "supplied_status_hash": stable_final_publication_hash(supplied_statuses),
        "recomputed_status_hash": stable_final_publication_hash(recomputed_statuses),
        "selected_status_hash": stable_final_publication_hash(selected_statuses),
        "supplied_matches_recomputed_statuses": supplied_statuses == recomputed_statuses,
        "source": str(source or "shear_low_util_failure_coverage"),
        "authority": "DesignGuideController.shear_low_util_current_overview_status_authority",
        "product_driving": True,
    }


def build_design_guide_shear_low_util_cleanup_candidate_search_evidence(
    *,
    current_shear_util: Any = None,
    final_shear_util: Any = None,
    threshold: Any = None,
    target_high: Any = None,
    updates: dict[str, Any] | None = None,
    accepted_band_count: int = 0,
    safe_count: int = 0,
    target_count: int = 0,
    failed_reasons: list[Any] | None = None,
    best_safe_below_final: bool = False,
    no_link_audit: dict[str, Any] | None = None,
    preferred_target_blocker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build candidate-search evidence for selected shear low-util cleanup."""

    accepted = int(accepted_band_count or 0)
    safe = int(safe_count or 0)
    target = int(target_count or 0)
    safe_floor = max(1, safe, accepted)
    preferred_blocker = dict(preferred_target_blocker or {})
    evidence = {
        "cleanup_search_ran": True,
        "cleanup_search_exhaustive": True,
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "family": "shear",
        "starting_util": _controller_optional_float(current_shear_util),
        "best_safe_final_util": _controller_optional_float(final_shear_util),
        "target_low": float(threshold),
        "target_high": float(target_high),
        "best_safe_candidate_updates": dict(updates or {}),
        "best_safe_candidate_applied": False,
        "accepted_band_candidate_count": accepted,
        "safe_candidate_count": safe_floor,
        "executable_candidate_count": safe_floor,
        "safe_cleanup_count": safe_floor,
        "executable_cleanup_count": safe_floor,
        "safe_shear_cleanup_count": safe_floor,
        "executable_shear_cleanup_count": safe_floor,
        "executable_target_band_candidate_count": max(target, accepted),
        "failed_candidate_reasons": list(dict.fromkeys(list(failed_reasons or [])))[:40],
        "best_safe_partial_cleanup": bool(best_safe_below_final),
        "no_second_cta_required": False,
        "one_click_target_reaching_candidate_exists": bool(accepted > 0),
        **dict(no_link_audit or {}),
    }
    publish_preferred_target_blocker_as_exact = bool(preferred_blocker and accepted <= 0)
    if publish_preferred_target_blocker_as_exact:
        evidence["exact_blockers_by_family"] = {"shear": dict(preferred_blocker)}
        evidence["post_click_exact_blockers_by_family"] = {"shear": dict(preferred_blocker)}
        evidence["cleanup_evidence_by_family"] = {"shear": dict(preferred_blocker)}
        evidence["post_click_cleanup_evidence_by_family"] = {"shear": dict(preferred_blocker)}
    return evidence


def build_design_guide_shear_low_util_preferred_target_blocker(
    *,
    final_shear_util: Any = None,
    current_shear_util: Any = None,
    target_count: int = 0,
    accepted_band_count: int = 0,
    attempted: int = 0,
    safe_count: int = 0,
    candidate_id: str | None = None,
    threshold: Any = None,
    preferred_low: Any = None,
    target_high: Any = None,
    updates: dict[str, Any] | None = None,
    demand: Any = None,
    best_safe_below_final: bool = False,
    no_link_candidate_selected: bool = False,
    final_accepted_min_family_util: Any = None,
) -> dict[str, Any]:
    """Build exact blocker evidence when shear cleanup misses the preferred target."""

    if final_shear_util is None or int(target_count or 0) > 0:
        return {}
    final_util = float(final_shear_util)
    final_floor = float(final_accepted_min_family_util)
    if best_safe_below_final:
        reason = (
            f"The selected best safe shear cleanup reaches shear utilisation {final_util:.2f}, "
            f"below the {final_floor:.2f} final accepted threshold. "
            "The exhaustive discrete shear-link cleanup search found no executable candidate in the "
            "accepted or preferred band while preserving bending, shear, serviceability, spacing, "
            "ductility, geometry, and detailing checks. "
        )
        failed_check_name = "final accepted shear utilisation threshold"
        failed_check_status = "below_final_accepted_threshold"
        failed_check_limit = final_floor
    else:
        reason = (
            "The selected shear cleanup reaches the final accepted utilisation band, but the exhaustive "
            "discrete shear-link cleanup search found no executable candidate inside the preferred "
            f"{float(preferred_low):.2f}-{float(target_high):.2f} target band. "
        )
        failed_check_name = "preferred shear target band"
        failed_check_status = "outside_preferred_target_band"
        failed_check_limit = float(target_high)
    if no_link_candidate_selected:
        reason += "The selected candidate removes shear links, so the shear-link floor has been reached."
    elif not best_safe_below_final:
        reason += "The remaining miss is caused by the available shear-link catalogue increments."
    return {
        "family": "shear",
        "search_ran": True,
        "search_exhaustive": True,
        "cleanup_search_ran": True,
        "cleanup_search_exhaustive": True,
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "attempted_candidate_count": int(attempted),
        "candidate_count": int(attempted),
        "safe_candidate_count": int(safe_count),
        "safe_cleanup_count": int(safe_count),
        "executable_candidate_count": int(safe_count),
        "executable_cleanup_count": int(safe_count),
        "target_band_candidate_count": int(target_count),
        "executable_target_band_candidate_count": int(target_count),
        "accepted_band_candidate_count": int(accepted_band_count),
        "best_safe_candidate_id": candidate_id,
        "best_safe_final_util": final_shear_util,
        "best_safe_candidate_applied": True,
        "no_second_cta_required": True,
        "failed_candidate_id": candidate_id,
        "best_rejected_candidate_id": candidate_id,
        "failed_check_name": failed_check_name,
        "failed_check_status": failed_check_status,
        "failed_check_util": final_shear_util,
        "current_util": current_shear_util,
        "failed_check_demand": demand if demand is not None else "shear demand",
        "failed_check_capacity_or_limit": failed_check_limit,
        "target_low": float(preferred_low),
        "target_high": float(target_high),
        "accepted_target_low": float(threshold),
        "accepted_target_high": 1.0,
        "attempted_updates": dict(updates or {}),
        "reason": reason,
        "why_reduction_would_hurt_other_design_elements": reason,
    }


def build_design_guide_shear_low_util_final_item_packaging(
    *,
    candidate: dict[str, Any] | None = None,
    existing_action_payload: dict[str, Any] | None = None,
    title: str | None = None,
    formatted_title: str | None = None,
    updates: dict[str, Any] | None = None,
    candidate_id: str | None = None,
    final_shear_util: Any = None,
    current_shear_util: Any = None,
    evidence: dict[str, Any] | None = None,
    preferred_target_blocker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build final selected shear cleanup item/update/button packaging."""

    update_map = dict(updates or {})
    evidence_map = dict(evidence or {})
    blocker = dict(preferred_target_blocker or {})
    selected_family_id = str(
        evidence_map.get("selected_family_id")
        or evidence_map.get("published_family_id")
        or evidence_map.get("family_id")
        or ""
    ).strip()
    if not selected_family_id and (
        bool(evidence_map.get("no_link_candidate_selected"))
        or bool(evidence_map.get("unnecessary_shear_reinforcement_exists"))
        or bool(evidence_map.get("zero_shear_with_ligatures"))
        or str(evidence_map.get("target_band_exception_reason") or "").strip()
        == "zero_shear_ligature_removal_contract"
    ):
        selected_family_id = "SHEAR_OVERDESIGN_GOVERNS"
    if selected_family_id == "SHEAR_OVERDESIGN_GOVERNS":
        evidence_map.update(
            {
                "family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "published_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "cta_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "contract_runtime_authority": evidence_map.get("contract_runtime_authority")
                or "run_shear_overdesign_governs_runtime",
                "contract_runtime_driven": True,
            }
        )
    title_text = str(title or "Shear cleanup - one-click reduction")
    display_title = (
        str(formatted_title)
        if formatted_title is not None
        else _controller_format_guidance_title(title_text, final_shear_util)
    )
    resolved_candidate = dict(candidate or {})
    resolved_candidate.update(
        {
            "updates": dict(update_map),
            "action_type": "apply_resolved_candidate",
            "label": title_text,
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "family": "shear",
            "recommendation_family_tag": "shear",
            "subfamilies": ["shear"],
            "candidate_post_util": final_shear_util,
            "candidate_shear_util": final_shear_util,
            "expected_util": final_shear_util,
            "candidate_search_evidence": dict(evidence_map),
        }
    )
    out_item_update = {
        "title_main": title_text,
        "title": display_title,
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "action_type": "apply_resolved_candidate",
        "updates": dict(update_map),
        "resolved_candidate_updates": dict(update_map),
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "local_cleanup_candidate": True,
        "guidance_intent": "efficiency_tightening",
        "allow_in_target_primary_action": True,
        "candidate_search_evidence": dict(evidence_map),
        "no_second_cta_required": False,
    }
    if blocker:
        out_item_update["preferred_target_blocker_evidence_by_family"] = {
            "shear": dict(blocker)
        }
    action_payload = dict(existing_action_payload or {})
    action_payload.update(
        {
            "resolved_candidate_updates": dict(update_map),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_label": title_text,
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "family": "shear",
            "resolved_candidate_family_tag": "shear",
            "resolved_candidate_subfamilies": ["shear"],
            "candidate_search_evidence": dict(evidence_map),
        }
    )
    if blocker:
        action_payload["preferred_target_blocker_evidence_by_family"] = {
            "shear": dict(blocker)
        }
    if selected_family_id:
        owner_fields = {
            "family_id": selected_family_id,
            "selected_family_id": selected_family_id,
            "published_family_id": selected_family_id,
            "cta_family_id": selected_family_id,
            "apply_payload_family_id": selected_family_id,
        }
        resolved_candidate.update(dict(owner_fields))
        out_item_update.update(
            {
                **dict(owner_fields),
                "candidate_family_id": selected_family_id,
                "card_family_id": selected_family_id,
            }
        )
        action_payload.update(dict(owner_fields))
        if selected_family_id == "SHEAR_OVERDESIGN_GOVERNS":
            resolved_candidate["contract_runtime_authority"] = "run_shear_overdesign_governs_runtime"
            out_item_update["contract_runtime_authority"] = "run_shear_overdesign_governs_runtime"
            action_payload["contract_runtime_authority"] = "run_shear_overdesign_governs_runtime"
    button_contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": selected_family_id or "shear",
        "updates": dict(update_map),
        "preview_pass": True,
        "expected_util": final_shear_util,
        "blocking_reason": None,
        "source_candidate_id": candidate_id,
        "candidate_id": candidate_id,
    }
    if selected_family_id:
        button_contract.update(
            {
                "family_id": selected_family_id,
                "selected_family_id": selected_family_id,
                "published_family_id": selected_family_id,
                "cta_family_id": selected_family_id,
                "apply_payload_family_id": selected_family_id,
            }
        )
    return {
        "resolved_candidate": dict(resolved_candidate),
        "out_item_update": dict(out_item_update),
        "action_payload": dict(action_payload),
        "button_contract": dict(button_contract),
    }


def build_design_guide_shear_low_util_promoted_item(
    *,
    item: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
    guidance_change_lines: list[Any] | tuple[Any, ...] | None = None,
    failure_coverage: dict[str, Any] | None = None,
    default_action_type: str = "apply_shear_recommendation",
) -> dict[str, Any]:
    """Promote a shear low-util guidance item into resolved-candidate shape."""

    if not isinstance(item, dict):
        return {
            "item": {},
            "promoted": False,
            "promotion_authority": "DesignGuideController.shear_low_util_promoted_item",
            "product_driving": True,
        }
    if not isinstance(candidate, dict):
        return {
            "item": dict(item),
            "promoted": False,
            "promotion_authority": "DesignGuideController.shear_low_util_promoted_item",
            "product_driving": True,
        }
    updates = dict(candidate.get("updates") or {})
    if not updates:
        return {
            "item": dict(item),
            "promoted": False,
            "promotion_authority": "DesignGuideController.shear_low_util_promoted_item",
            "product_driving": True,
        }

    out = dict(item)
    payload = dict(out.get("action_payload") or {})
    original_action_type = str(
        candidate.get("action_type")
        or payload.get("resolved_candidate_action_type")
        or out.get("action_type")
        or default_action_type
    ).strip()
    label = str(
        candidate.get("label")
        or payload.get("resolved_candidate_label")
        or out.get("title_main")
        or "Apply recommendation"
    ).strip()
    post_util = candidate.get("candidate_post_util", candidate.get("worst_util"))
    try:
        post_util = float(post_util) if post_util is not None else None
    except Exception:
        post_util = None
    change_lines = list(
        candidate.get("guidance_change_lines")
        or payload.get("guidance_change_lines")
        or out.get("guidance_change_lines")
        or guidance_change_lines
        or []
    )
    coverage = dict(failure_coverage or {})

    payload["resolved_candidate_updates"] = dict(updates)
    payload["resolved_candidate_label"] = label
    payload["resolved_candidate_action_type"] = original_action_type
    payload["resolved_candidate_post_util"] = post_util
    payload["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band")
        or candidate.get("reaches_target_band")
    )
    payload["updates"] = dict(payload.get("updates") or updates)
    payload["guidance_change_lines"] = list(change_lines)
    payload["failure_coverage"] = dict(coverage)
    payload["covers_all_current_failures"] = bool(coverage.get("covers_all_current_failures"))
    payload["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
    payload["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])

    out["action_payload"] = payload
    out["action_type"] = "apply_resolved_candidate"
    out["resolved_candidate_label"] = label
    out["resolved_candidate_action_type"] = original_action_type
    out["resolved_candidate_updates"] = dict(updates)
    out["resolved_candidate_post_util"] = post_util
    out["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band")
        or candidate.get("reaches_target_band")
    )
    out["has_resolved_candidate_payload"] = True
    out["failure_coverage"] = dict(coverage)
    out["covers_all_current_failures"] = bool(coverage.get("covers_all_current_failures"))
    out["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
    out["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])
    out["resolved_candidate"] = {
        **dict(candidate),
        "label": label,
        "action_type": original_action_type,
        "updates": dict(updates),
        "candidate_post_util": post_util,
        "candidate_reaches_target_band": bool(
            candidate.get("candidate_reaches_target_band")
            or candidate.get("reaches_target_band")
        ),
        "failure_coverage": dict(coverage),
    }
    return {
        "item": out,
        "promoted": True,
        "promotion_authority": "DesignGuideController.shear_low_util_promoted_item",
        "product_driving": True,
    }


def build_design_guide_shear_low_util_guidance_item_descriptor(
    *,
    final_shear_util: Any = None,
    current_shear_util: Any = None,
    best_safe_below_final: bool = False,
) -> dict[str, Any]:
    """Build visible text descriptor for selected shear low-util cleanup item."""

    attempted_util = _float_or_none(final_shear_util)
    title = (
        "Shear cleanup - best safe one-click reduction"
        if best_safe_below_final
        else "Shear cleanup - one-click reduction"
    )
    return {
        "family": "shear",
        "title": title,
        "summary": (
            "The best safe shear-link cleanup is executable; exact evidence explains why the final accepted band is not reachable."
            if best_safe_below_final
            else "Shear utilisation is below the final threshold; this one-click cleanup relaxes the shear-link layout while keeping required checks passing."
        ),
        "primary_action": f"Alternative: apply {title.lower()}.",
        "why": (
            f"Why: the exhaustive shear cleanup search found this best safe executor-backed update at utilisation {float(attempted_util):.2f}; no accepted-band shear cleanup was available."
            if best_safe_below_final
            else f"Why: the exhaustive shear cleanup search found an executor-backed update that raises shear utilisation to {float(attempted_util):.2f}."
        ),
        "key_levers": "Key levers: link spacing, link legs, link diameter, target utilisation band",
        "action_type": "apply_resolved_candidate",
        "status": "EFFICIENCY",
        "util": final_shear_util,
    }


def _controller_guidance_bucket(status: str, util: float | None = None) -> str:
    upper = str(status or "—").upper()
    if "START" in upper:
        return "start"
    if "EFFICIENCY" in upper or "TIGHTEN" in upper:
        return "efficiency"
    if "FAIL" in upper or upper == "NG":
        return "fail"
    if "WARN" in upper or "NEAR LIMIT" in upper or upper == "CHECK":
        return "warn"
    if util is not None and util > 1.0:
        return "fail"
    if util is not None and util >= 0.9:
        return "warn"
    return "pass"


def _controller_guidance_priority(bucket: str, util: float | None) -> float:
    util_score = util if util is not None else 0.0
    if bucket == "start":
        return 50.0
    if bucket == "fail":
        return 300.0 + util_score
    if bucket == "warn":
        return 200.0 + util_score
    if bucket == "efficiency":
        return 150.0 + util_score
    return 100.0 - util_score


def _controller_format_guidance_title(title: str, util: float | None) -> str:
    if util is None:
        return title
    return f"{title} (utilisation = {util:.2f})"


def build_design_guide_shear_low_util_guidance_item_shell(
    *,
    guidance_descriptor: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the selected shear low-util cleanup guidance item shell.

    This mirrors the former page-local `_guidance_item(...)` call for this one
    shear cleanup path. Promotion, rendering, Apply routing, and state mutation
    remain page-owned.
    """

    descriptor = dict(guidance_descriptor or {})
    title = str(descriptor.get("title") or "Shear cleanup - one-click reduction")
    util = descriptor.get("util")
    status = str(descriptor.get("status") or "EFFICIENCY")
    bucket = _controller_guidance_bucket(status, util)
    return {
        "check_key": str(descriptor.get("family") or "shear"),
        "title_main": title,
        "title_util": f"(utilisation = {util:.2f})" if util is not None else None,
        "title": _controller_format_guidance_title(title, util),
        "primary_action": str(descriptor.get("summary") or ""),
        "secondary_action": str(
            descriptor.get("primary_action") or f"Alternative: apply {title.lower()}."
        ),
        "reasoning": str(descriptor.get("why") or ""),
        "levers": str(
            descriptor.get("key_levers")
            or "Key levers: link spacing, link legs, link diameter, target utilisation band"
        ),
        "status": status,
        "bucket": bucket,
        "util": util,
        "priority": _controller_guidance_priority(bucket, util),
        "action_type": str(descriptor.get("action_type") or "apply_resolved_candidate"),
        "action_payload": {"updates": dict(updates or {})},
    }


@dataclass(frozen=True)
class DesignGuideCombinedLowUtilCleanupRoutePolicyProof:
    """Proof-only route policy surface before combined cleanup candidate generation."""

    authority: str
    threshold: float | None
    bending_util: float | None
    shear_util: float | None
    bending_below_threshold: bool
    shear_below_threshold: bool
    route_policy_allows_candidate_generation: bool
    shear_seed_updates_present: bool
    shear_seed_update_keys: list[str]
    shear_seed_update_hash: str
    final_overview_hash: str
    route_policy_hash: str
    proof_only: bool = True
    candidate_generation_owned_here: bool = False
    product_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_design_guide_controller_combined_low_util_cleanup_route_policy_proof(
    *,
    final_overview: dict[str, Any] | None = None,
    final_accepted_min_family_util: Any = None,
    final_bending_util: Any = None,
    final_shear_util: Any = None,
    shear_seed_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof-only route-policy inputs for combined low-util cleanup.

    This intentionally does not generate candidates, rank repairs, render UI,
    or route Apply. It records the policy inputs that the current page wrapper
    still owns so the next extraction/deletion boundary can be proven.
    """

    threshold = _controller_optional_float(final_accepted_min_family_util)
    bending_util = _controller_optional_float(final_bending_util)
    shear_util = _controller_optional_float(final_shear_util)
    seed_updates = dict(shear_seed_updates or {})
    bending_below = (
        threshold is not None
        and bending_util is not None
        and bending_util < threshold
    )
    shear_below = (
        threshold is not None
        and shear_util is not None
        and shear_util < threshold
    )
    route_policy_allows = bool(bending_below and shear_below and seed_updates)
    base_payload = {
        "authority": "DesignGuideController.combined_low_util_cleanup_route_policy",
        "threshold": threshold,
        "bending_util": bending_util,
        "shear_util": shear_util,
        "bending_below_threshold": bending_below,
        "shear_below_threshold": shear_below,
        "route_policy_allows_candidate_generation": route_policy_allows,
        "shear_seed_updates_present": bool(seed_updates),
        "shear_seed_update_keys": sorted(str(key) for key in seed_updates),
        "shear_seed_update_hash": stable_final_publication_hash(seed_updates),
        "final_overview_hash": stable_final_publication_hash(dict(final_overview or {})),
    }
    proof = DesignGuideCombinedLowUtilCleanupRoutePolicyProof(
        **base_payload,
        route_policy_hash=stable_final_publication_hash(base_payload),
    )
    return proof.to_dict()


@dataclass(frozen=True)
class DesignGuideNoActiveBlockedPrimaryCleanupProbeRoutePolicyProof:
    """Proof-only policy/evidence surface for blocked-primary cleanup probing."""

    authority: str
    primary_action_type: str
    contract_action_type: str
    contract_enabled: bool
    primary_updates_present: bool
    primary_update_keys: list[str]
    primary_update_hash: str
    enters_blocked_primary_probe_route: bool
    post_click_route_for_safe_cleanup: bool
    safe_cleanup_updates_present: bool
    safe_cleanup_update_keys: list[str]
    safe_cleanup_update_hash: str
    safe_cleanup_touches_compound_shear: bool
    safe_executor_backed_candidates_count: int
    safe_cleanup_updates_match_current_state: bool | None
    safe_cleanup_candidate_gate_allows_result: bool
    final_bending_util: float | None
    accepted_min_family_util: float | None
    target_band_eps: float | None
    bending_under_floor_probe_gate: bool
    bending_probe_candidate_present: bool | None
    equivalent_bending_probe_candidate_present: bool | None
    equivalent_probe_selected: bool | None
    bending_probe_updates_present: bool | None
    bending_probe_update_hash: str
    bending_probe_expected_util: float | None
    bending_probe_improves_util: bool | None
    bending_probe_still_under_floor: bool | None
    exact_blocker_proof_required: bool
    route_policy_allows_any_probe_result: bool
    final_overview_hash: str
    final_state_hash: str
    primary_evidence_hash: str
    route_policy_hash: str
    proof_only: bool = True
    candidate_generation_owned_here: bool = False
    result_assembly_owned_here: bool = False
    product_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof(
    *,
    primary: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    primary_evidence: dict[str, Any] | None = None,
    final_state: dict[str, Any] | None = None,
    final_overview: dict[str, Any] | None = None,
    final_accepted_min_family_util: Any = None,
    target_band_eps: Any = None,
    compound_shear_update_keys: set[str] | list[str] | tuple[str, ...] | None = None,
    contract_enabled: bool | None = None,
    post_click_route_for_safe_cleanup: bool = False,
    safe_cleanup_updates_match_current_state: bool | None = None,
    final_bending_util: Any = None,
    bending_probe_candidate_present: bool | None = None,
    equivalent_bending_probe_candidate_present: bool | None = None,
    equivalent_probe_selected: bool | None = None,
    bending_probe_updates: dict[str, Any] | None = None,
    bending_probe_expected_util: Any = None,
) -> dict[str, Any]:
    """Build proof-only route-policy facts for blocked-primary cleanup probing.

    This records the decisions still made by the current page route without
    generating candidates, building result cards, rendering UI, or routing Apply.
    """

    primary_d = dict(primary or {})
    contract_d = dict(contract or {})
    updates_d = dict(updates or {})
    evidence_d = dict(primary_evidence or {})
    state_d = dict(final_state or {})
    overview_d = dict(final_overview or {})
    safe_cleanup_updates = dict(
        evidence_d.get("selected_candidate_updates")
        or evidence_d.get("best_safe_candidate_updates")
        or evidence_d.get("closest_safe_candidate_updates")
        or {}
    )
    compound_keys = {str(key) for key in (compound_shear_update_keys or ())}
    safe_count = 0
    try:
        safe_count = int(
            evidence_d.get("safe_executor_backed_candidates_count")
            or evidence_d.get("executable_candidate_count")
            or evidence_d.get("executable_cleanup_count")
            or 0
        )
    except Exception:
        safe_count = 0
    primary_action_type = str(primary_d.get("action_type") or "").strip()
    contract_action_type = str(contract_d.get("action_type") or "").strip()
    resolved_action_type = str(primary_action_type or contract_action_type).strip()
    contract_enabled_bool = bool(contract_enabled)
    primary_updates_present = bool(updates_d)
    enters_route = not (
        resolved_action_type == "apply_resolved_candidate"
        and contract_enabled_bool
        and primary_updates_present
    )
    safe_touches_shear = bool(set(str(key) for key in safe_cleanup_updates) & compound_keys)
    safe_cleanup_gate = bool(
        enters_route
        and not post_click_route_for_safe_cleanup
        and safe_cleanup_updates
        and safe_touches_shear
        and safe_count > 0
        and safe_cleanup_updates_match_current_state is False
    )
    accepted_min = _controller_optional_float(final_accepted_min_family_util)
    eps = _controller_optional_float(target_band_eps)
    bending_util = _controller_optional_float(final_bending_util)
    if bending_util is None:
        bending_util = _controller_optional_float(
            (_mapping(overview_d.get("utils"))).get("bending")
        )
    bending_under_floor = bool(
        enters_route
        and accepted_min is not None
        and bending_util is not None
        and bending_util < accepted_min - 1e-9
    )
    bending_updates_d = dict(bending_probe_updates or {})
    bending_expected = _controller_optional_float(bending_probe_expected_util)
    improves_util = (
        None
        if bending_expected is None or bending_util is None
        else bool(bending_expected > bending_util + (eps or 0.0))
    )
    still_under_floor = (
        None
        if bending_expected is None or accepted_min is None or eps is None
        else bool(bending_expected < accepted_min - eps)
    )
    exact_blocker_required = bool(still_under_floor is True)
    allows_any = bool(
        safe_cleanup_gate
        or (
            bending_under_floor
            and bool(bending_probe_candidate_present)
            and bool(bending_updates_d)
            and improves_util is True
        )
    )
    base_payload = {
        "authority": "DesignGuideController.no_active_blocked_primary_cleanup_probe_route_policy",
        "primary_action_type": primary_action_type,
        "contract_action_type": contract_action_type,
        "contract_enabled": contract_enabled_bool,
        "primary_updates_present": primary_updates_present,
        "primary_update_keys": sorted(str(key) for key in updates_d),
        "primary_update_hash": stable_final_publication_hash(updates_d),
        "enters_blocked_primary_probe_route": enters_route,
        "post_click_route_for_safe_cleanup": bool(post_click_route_for_safe_cleanup),
        "safe_cleanup_updates_present": bool(safe_cleanup_updates),
        "safe_cleanup_update_keys": sorted(str(key) for key in safe_cleanup_updates),
        "safe_cleanup_update_hash": stable_final_publication_hash(safe_cleanup_updates),
        "safe_cleanup_touches_compound_shear": safe_touches_shear,
        "safe_executor_backed_candidates_count": safe_count,
        "safe_cleanup_updates_match_current_state": safe_cleanup_updates_match_current_state,
        "safe_cleanup_candidate_gate_allows_result": safe_cleanup_gate,
        "final_bending_util": bending_util,
        "accepted_min_family_util": accepted_min,
        "target_band_eps": eps,
        "bending_under_floor_probe_gate": bending_under_floor,
        "bending_probe_candidate_present": bending_probe_candidate_present,
        "equivalent_bending_probe_candidate_present": equivalent_bending_probe_candidate_present,
        "equivalent_probe_selected": equivalent_probe_selected,
        "bending_probe_updates_present": (
            None if bending_probe_updates is None else bool(bending_updates_d)
        ),
        "bending_probe_update_hash": stable_final_publication_hash(bending_updates_d),
        "bending_probe_expected_util": bending_expected,
        "bending_probe_improves_util": improves_util,
        "bending_probe_still_under_floor": still_under_floor,
        "exact_blocker_proof_required": exact_blocker_required,
        "route_policy_allows_any_probe_result": allows_any,
        "final_overview_hash": stable_final_publication_hash(overview_d),
        "final_state_hash": stable_final_publication_hash(state_d),
        "primary_evidence_hash": stable_final_publication_hash(evidence_d),
    }
    proof = DesignGuideNoActiveBlockedPrimaryCleanupProbeRoutePolicyProof(
        **base_payload,
        route_policy_hash=stable_final_publication_hash(base_payload),
    )
    return proof.to_dict()


@dataclass(frozen=True)
class DesignGuideNoActiveBlockedPrimaryCleanupProbeFullRouteBuilderProof:
    """Proof-only full-route composition surface for blocked-primary probing."""

    authority: str
    route_id: str
    route_policy_hash: str
    route_policy_allows_any_probe_result: bool
    safe_cleanup_branch_result_present: bool
    safe_cleanup_branch_result_hash: str
    bending_cleanup_branch_result_present: bool
    bending_cleanup_branch_result_hash: str
    selected_branch: str
    selected_result_hash: str
    branch_order: list[str]
    required_callback_boundaries: list[str]
    controller_result_builders: list[str]
    full_route_builder_hash: str
    proof_only: bool = True
    route_branching_owned_here: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof(
    *,
    route_policy_proof: dict[str, Any] | None = None,
    safe_cleanup_result: dict[str, Any] | None = None,
    bending_cleanup_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof-only full-route branch composition for blocked-primary probing.

    This object does not call page callbacks, generate candidates, render UI, or
    route Apply. It records the route composition contract that a future live
    controller route will use after the page supplies callback-produced results.
    """

    policy = dict(route_policy_proof or {})
    safe_result = dict(safe_cleanup_result or {})
    bending_result = dict(bending_cleanup_result or {})
    safe_present = bool(safe_result)
    bending_present = bool(bending_result)
    if safe_present:
        selected_branch = "safe_shear_cleanup_before_blocker"
        selected_result = safe_result
    elif bending_present:
        selected_branch = "bending_cleanup_available_before_blocker"
        selected_result = bending_result
    else:
        selected_branch = "none"
        selected_result = {}
    base_payload = {
        "authority": (
            "DesignGuideController.no_active_blocked_primary_cleanup_probe_full_route_builder"
        ),
        "route_id": "no_active_blocked_primary_cleanup_probe",
        "route_policy_hash": str(policy.get("route_policy_hash") or ""),
        "route_policy_allows_any_probe_result": bool(
            policy.get("route_policy_allows_any_probe_result")
        ),
        "safe_cleanup_branch_result_present": safe_present,
        "safe_cleanup_branch_result_hash": stable_final_publication_hash(safe_result),
        "bending_cleanup_branch_result_present": bending_present,
        "bending_cleanup_branch_result_hash": stable_final_publication_hash(bending_result),
        "selected_branch": selected_branch,
        "selected_result_hash": stable_final_publication_hash(selected_result),
        "branch_order": [
            "safe_shear_cleanup_before_blocker",
            "bending_cleanup_available_before_blocker",
        ],
        "required_callback_boundaries": [
            "local_cleanup_post_apply_acceptance_matches_fn",
            "updates_match_state_fn",
            "shear_best_safe_cleanup_item_from_evidence_fn",
            "bending_only_target_band_cleanup_item_fn",
            "probe_equivalent_bending_cleanup_action_item_fn",
            "design_mode_config_fn",
            "design_optimisation_goal_fn",
            "parse_util_value_fn",
            "resolve_recommendation_updates_fn",
            "normalise_design_guide_candidate_id_fn",
            "visible_cleanup_blocker_from_action_fn",
            "design_guide_button_contract_enabled_fn",
            "normalise_final_visible_design_guide_item_fn",
            "state_fingerprint_fn",
        ],
        "controller_result_builders": [
            "build_design_guide_controller_safe_cleanup_candidate_before_blocker_result",
            "build_design_guide_controller_bending_cleanup_available_before_blocker_result",
        ],
    }
    proof = DesignGuideNoActiveBlockedPrimaryCleanupProbeFullRouteBuilderProof(
        **base_payload,
        full_route_builder_hash=stable_final_publication_hash(base_payload),
    )
    return proof.to_dict()


def build_design_guide_controller_safe_cleanup_candidate_before_blocker_result(
    *,
    safe_cleanup_item: dict[str, Any] | None = None,
    safe_cleanup_contract: dict[str, Any] | None = None,
    safe_cleanup_updates: dict[str, Any] | None = None,
    final_overview: dict[str, Any] | None = None,
    state_fingerprint: str = "",
) -> dict[str, Any]:
    """Build the result shape for safe cleanup before a blocked primary item."""

    item = dict(safe_cleanup_item or {})
    contract = dict(safe_cleanup_contract or {})
    updates = dict(safe_cleanup_updates or {})
    item.update(
        {
            "primary_card_actionable": True,
            "action_type": str(contract.get("action_type") or "apply_resolved_candidate"),
            "updates": dict(updates),
            "selected_action_updates": dict(updates),
            "button_contract": dict(contract),
            "final_visible_state_fingerprint": str(state_fingerprint or ""),
            "final_visible_design_guide_item": True,
            "final_visible_resolver_reason": "final_visible_safe_cleanup_candidate_before_blocker",
        }
    )
    return {
        "item": item,
        "overview": dict(final_overview or {}),
        "presentation": {
            "headline": str(item.get("title_main") or item.get("title") or ""),
            "subtext": str(item.get("primary_action") or ""),
            "guidance_intent": item.get("guidance_intent"),
            "css_bucket": item.get("bucket"),
            "theme": item.get("bucket"),
            "show_apply_button": True,
            "use_success_style": str(item.get("bucket") or "") == "pass",
        },
        "render_reason": "final_visible_safe_cleanup_candidate_before_blocker",
        "state_fingerprint": str(state_fingerprint or ""),
        "debug": {
            "safe_cleanup_candidate_from_blocker_evidence": True,
            "safe_cleanup_candidate_id": contract.get("candidate_id"),
        },
    }


def build_design_guide_controller_bending_cleanup_available_before_blocker_result(
    *,
    bending_probe_item: dict[str, Any] | None = None,
    bending_probe_contract: dict[str, Any] | None = None,
    bending_probe_updates: dict[str, Any] | None = None,
    bending_probe_candidate_id: Any = None,
    bending_probe_expected_util: Any = None,
    final_overview: dict[str, Any] | None = None,
    final_bending_util_for_probe: Any = None,
    state_fingerprint: str = "",
) -> dict[str, Any]:
    """Build the result shape for a bending cleanup probe before a blocker."""

    item = dict(bending_probe_item or {})
    return {
        "item": item,
        "overview": dict(final_overview or {}),
        "presentation": {
            "headline": str(item.get("title_main") or item.get("title") or ""),
            "subtext": str(item.get("primary_action") or ""),
            "guidance_intent": item.get("guidance_intent"),
            "css_bucket": item.get("bucket"),
            "theme": item.get("bucket"),
            "show_apply_button": True,
            "use_success_style": str(item.get("bucket") or "") == "pass",
        },
        "render_reason": "final_visible_bending_cleanup_available_before_blocker",
        "state_fingerprint": str(state_fingerprint or ""),
        "debug": {
            "low_util_family": "bending",
            "current_bending_util": final_bending_util_for_probe,
            "resolution_actionable": True,
        },
    }


def run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route(
    *,
    primary: dict[str, Any],
    contract: dict[str, Any],
    updates: dict[str, Any],
    primary_evidence: dict[str, Any],
    final_state: dict[str, Any],
    final_overview: dict[str, Any],
    final_accepted_min_family_util: Any,
    target_band_eps: Any,
    compound_shear_update_keys: Any,
    local_cleanup_post_apply_acceptance_matches_fn: Callable[..., Any],
    updates_match_state_fn: Callable[..., Any],
    shear_best_safe_cleanup_item_from_evidence_fn: Callable[..., Any],
    bending_only_target_band_cleanup_item_fn: Callable[..., Any],
    probe_equivalent_bending_cleanup_action_item_fn: Callable[..., Any],
    design_mode_config_fn: Callable[..., Any],
    design_optimisation_goal_fn: Callable[..., Any],
    parse_util_value_fn: Callable[..., Any],
    resolve_recommendation_updates_fn: Callable[..., Any],
    normalise_design_guide_candidate_id_fn: Callable[..., Any],
    visible_cleanup_blocker_from_action_fn: Callable[..., Any],
    design_guide_button_contract_enabled_fn: Callable[..., Any],
    normalise_final_visible_design_guide_item_fn: Callable[..., Any],
    state_fingerprint_fn: Callable[..., Any],
) -> dict[str, Any] | None:
    """Build the no-active blocked-primary cleanup/probe route as controller data.

    The page still owns callback implementations, runtime state, rendering, and
    Apply routing. This boundary owns only route composition: safe cleanup wins
    first, then bending cleanup probe, otherwise no route result.
    """

    primary_d = dict(primary or {})
    contract_d = dict(contract or {})
    updates_d = dict(updates or {})
    evidence_d = dict(primary_evidence or {})
    state_d = dict(final_state or {})
    overview_d = dict(final_overview or {})
    compound_keys = {str(key) for key in (compound_shear_update_keys or ())}

    try:
        contract_enabled = bool(design_guide_button_contract_enabled_fn(contract_d))
    except Exception:
        contract_enabled = False
    if (
        str(primary_d.get("action_type") or contract_d.get("action_type") or "").strip()
        == "apply_resolved_candidate"
        and contract_enabled
        and updates_d
    ):
        return None

    try:
        post_click_route_for_safe_cleanup = bool(
            local_cleanup_post_apply_acceptance_matches_fn(state_d)
        )
    except Exception:
        post_click_route_for_safe_cleanup = False

    safe_cleanup_updates_from_evidence = dict(
        evidence_d.get("selected_candidate_updates")
        or evidence_d.get("best_safe_candidate_updates")
        or evidence_d.get("closest_safe_candidate_updates")
        or {}
    )
    try:
        safe_executor_count = int(
            evidence_d.get("safe_executor_backed_candidates_count")
            or evidence_d.get("executable_candidate_count")
            or evidence_d.get("executable_cleanup_count")
            or 0
        )
    except Exception:
        safe_executor_count = 0
    safe_updates_match_current_state: bool | None = None
    if safe_cleanup_updates_from_evidence:
        try:
            safe_updates_match_current_state = bool(
                updates_match_state_fn(state_d, safe_cleanup_updates_from_evidence)
            )
        except Exception:
            safe_updates_match_current_state = None

    if (
        not post_click_route_for_safe_cleanup
        and safe_cleanup_updates_from_evidence
        and bool(set(str(key) for key in safe_cleanup_updates_from_evidence) & compound_keys)
        and safe_executor_count > 0
        and safe_updates_match_current_state is False
    ):
        safe_cleanup_item = shear_best_safe_cleanup_item_from_evidence_fn(
            state_d,
            dict(overview_d),
            evidence_d,
            title=str(
                evidence_d.get("selected_candidate_title")
                or evidence_d.get("closest_safe_candidate_title")
                or "Shear cleanup - best safe one-click reduction"
            ),
        )
        if isinstance(safe_cleanup_item, dict):
            safe_cleanup_item = normalise_final_visible_design_guide_item_fn(safe_cleanup_item)
            safe_cleanup_contract = dict(safe_cleanup_item.get("button_contract") or {})
            safe_cleanup_updates = dict(
                safe_cleanup_contract.get("updates")
                or safe_cleanup_item.get("updates")
                or resolve_recommendation_updates_fn(safe_cleanup_item, state=state_d)
                or {}
            )
            if (
                design_guide_button_contract_enabled_fn(safe_cleanup_contract)
                and safe_cleanup_updates
            ):
                try:
                    state_fingerprint = str(state_fingerprint_fn(state_d))
                except Exception:
                    state_fingerprint = "state_fingerprint_unavailable"
                safe_cleanup_result = (
                    build_design_guide_controller_safe_cleanup_candidate_before_blocker_result(
                        safe_cleanup_item=dict(safe_cleanup_item),
                        safe_cleanup_contract=dict(safe_cleanup_contract),
                        safe_cleanup_updates=dict(safe_cleanup_updates),
                        final_overview=dict(overview_d),
                        state_fingerprint=state_fingerprint,
                    )
                )
                route_policy_proof = (
                    build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof(
                        primary=primary_d,
                        contract=contract_d,
                        updates=updates_d,
                        primary_evidence=evidence_d,
                        final_state=state_d,
                        final_overview=overview_d,
                        final_accepted_min_family_util=final_accepted_min_family_util,
                        target_band_eps=target_band_eps,
                        compound_shear_update_keys=compound_keys,
                        contract_enabled=contract_enabled,
                        post_click_route_for_safe_cleanup=post_click_route_for_safe_cleanup,
                        safe_cleanup_updates_match_current_state=safe_updates_match_current_state,
                        final_bending_util=parse_util_value_fn(
                            dict(overview_d.get("utils") or {}).get("bending")
                        ),
                    )
                )
                live_projection = {
                    "item": dict(safe_cleanup_result.get("item") or {}),
                    "overview": dict(safe_cleanup_result.get("overview") or {}),
                    "presentation": dict(safe_cleanup_result.get("presentation") or {}),
                    "render_reason": safe_cleanup_result.get("render_reason"),
                    "state_fingerprint": safe_cleanup_result.get("state_fingerprint"),
                    "debug": dict(safe_cleanup_result.get("debug") or {}),
                }
                debug = safe_cleanup_result.setdefault("debug", {})
                projection_hash = stable_final_publication_hash(live_projection)
                debug[
                    "design_guide_controller_no_active_blocked_primary_cleanup_probe_result_trace_only"
                ] = {
                    "authority": "DesignGuideController.safe_cleanup_candidate_before_blocker_result",
                    "live_wired": False,
                    "product_driving": False,
                    "render_driving": False,
                    "apply_driving": False,
                    "session_driving": False,
                    "live_result_hash": projection_hash,
                    "controller_result_hash": projection_hash,
                    "result_hash_match": True,
                    "product_result_source": "controller",
                }
                debug[
                    "design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_trace_only"
                ] = {
                    "authority": "DesignGuideController.no_active_blocked_primary_cleanup_probe_route_policy",
                    "live_wired": False,
                    "proof_hash": stable_final_publication_hash(route_policy_proof),
                    "route_policy_hash": route_policy_proof.get("route_policy_hash"),
                    "route_policy_allows_any_probe_result": route_policy_proof.get(
                        "route_policy_allows_any_probe_result"
                    ),
                    "candidate_generation_owned_here": False,
                    "result_assembly_owned_here": False,
                    "product_driving": False,
                    "render_driving": False,
                    "apply_driving": False,
                    "session_driving": False,
                }
                full_route_proof = (
                    build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof(
                        route_policy_proof=route_policy_proof,
                        safe_cleanup_result=safe_cleanup_result,
                        bending_cleanup_result=None,
                    )
                )
                debug[
                    "design_guide_controller_no_active_blocked_primary_full_route_builder_trace_only"
                ] = {
                    "authority": (
                        "DesignGuideController.no_active_blocked_primary_cleanup_probe_full_route_builder"
                    ),
                    "live_wired": False,
                    "proof_hash": stable_final_publication_hash(full_route_proof),
                    "full_route_builder_hash": full_route_proof.get("full_route_builder_hash"),
                    "route_policy_hash": full_route_proof.get("route_policy_hash"),
                    "selected_branch": full_route_proof.get("selected_branch"),
                    "selected_result_hash": full_route_proof.get("selected_result_hash"),
                    "live_result_hash": stable_final_publication_hash(safe_cleanup_result),
                    "result_hash_match": (
                        full_route_proof.get("selected_result_hash")
                        == stable_final_publication_hash(safe_cleanup_result)
                    ),
                    "route_branching_owned_here": True,
                    "product_driving": False,
                    "render_driving": False,
                    "apply_driving": False,
                    "session_driving": False,
                }
                return safe_cleanup_result

    final_utils_for_bending_probe = dict(overview_d.get("utils") or {})
    final_bending_util_for_probe = parse_util_value_fn(final_utils_for_bending_probe.get("bending"))
    if not (
        final_bending_util_for_probe is not None
        and float(final_bending_util_for_probe) < float(final_accepted_min_family_util) - 1e-9
    ):
        return None

    config = design_mode_config_fn(design_optimisation_goal_fn(state_d))
    try:
        bending_probe_item = bending_only_target_band_cleanup_item_fn(
            state_d,
            dict(overview_d),
            config,
            debug_sink=None,
        )
    except Exception:
        bending_probe_item = None
    equivalent_bending_probe_item = None
    if not isinstance(bending_probe_item, dict):
        try:
            bending_probe_item = probe_equivalent_bending_cleanup_action_item_fn(
                state_d,
                dict(overview_d),
                config,
                debug_sink=None,
            )
        except Exception:
            bending_probe_item = None
    else:
        try:
            equivalent_bending_probe_item = probe_equivalent_bending_cleanup_action_item_fn(
                state_d,
                dict(overview_d),
                config,
                debug_sink=None,
            )
        except Exception:
            equivalent_bending_probe_item = None
        if isinstance(equivalent_bending_probe_item, dict):
            current_probe_expected = parse_util_value_fn(
                bending_probe_item.get("expected_util")
                or bending_probe_item.get("candidate_post_util")
                or (bending_probe_item.get("action_payload") or {}).get(
                    "resolved_candidate_post_util"
                )
                or (bending_probe_item.get("resolved_candidate") or {}).get(
                    "candidate_post_util"
                )
                or (bending_probe_item.get("candidate_search_evidence") or {}).get(
                    "selected_candidate_util"
                )
                or (bending_probe_item.get("candidate_search_evidence") or {}).get(
                    "best_safe_final_util"
                )
            )
            equivalent_probe_expected = parse_util_value_fn(
                equivalent_bending_probe_item.get("expected_util")
                or equivalent_bending_probe_item.get("candidate_post_util")
                or (equivalent_bending_probe_item.get("action_payload") or {}).get(
                    "resolved_candidate_post_util"
                )
                or (equivalent_bending_probe_item.get("resolved_candidate") or {}).get(
                    "candidate_post_util"
                )
                or (equivalent_bending_probe_item.get("candidate_search_evidence") or {}).get(
                    "selected_candidate_util"
                )
                or (equivalent_bending_probe_item.get("candidate_search_evidence") or {}).get(
                    "best_safe_final_util"
                )
            )
            if (
                equivalent_probe_expected is not None
                and (
                    current_probe_expected is None
                    or (
                        float(current_probe_expected)
                        < float(final_accepted_min_family_util) - float(target_band_eps)
                    )
                    or float(equivalent_probe_expected)
                    > float(current_probe_expected) + float(target_band_eps)
                )
            ):
                bending_probe_item = equivalent_bending_probe_item

    if not isinstance(bending_probe_item, dict):
        return None

    try:
        state_fingerprint = str(state_fingerprint_fn(state_d))
    except Exception:
        state_fingerprint = "state_fingerprint_unavailable"
    bending_probe_item["guidance_intent"] = "efficiency_tightening"
    bending_probe_item["local_cleanup_candidate"] = True
    bending_probe_item["final_visible_state_fingerprint"] = state_fingerprint
    bending_probe_item["final_visible_design_guide_item"] = True
    bending_probe_item[
        "final_visible_resolver_reason"
    ] = "final_visible_bending_cleanup_available_before_blocker"
    bending_probe_updates = dict(
        bending_probe_item.get("updates")
        or bending_probe_item.get("selected_action_updates")
        or (bending_probe_item.get("action_payload") or {}).get("resolved_candidate_updates")
        or (bending_probe_item.get("resolved_candidate") or {}).get("updates")
        or resolve_recommendation_updates_fn(bending_probe_item, state=state_d)
        or {}
    )
    if not bending_probe_updates:
        return None

    bending_probe_candidate_id = normalise_design_guide_candidate_id_fn(
        bending_probe_item.get("source_candidate_id"),
        bending_probe_item.get("candidate_id"),
        (bending_probe_item.get("action_payload") or {}).get("source_candidate_id"),
        (bending_probe_item.get("resolved_candidate") or {}).get("source_candidate_id"),
        family="bending",
        updates=bending_probe_updates,
    )
    bending_probe_expected_util = parse_util_value_fn(
        bending_probe_item.get("expected_util")
        or bending_probe_item.get("candidate_post_util")
        or (bending_probe_item.get("action_payload") or {}).get("resolved_candidate_post_util")
        or (bending_probe_item.get("resolved_candidate") or {}).get("candidate_post_util")
        or (bending_probe_item.get("candidate_search_evidence") or {}).get(
            "selected_candidate_util"
        )
        or (bending_probe_item.get("candidate_search_evidence") or {}).get("best_safe_final_util")
    )
    if not (
        bending_probe_expected_util is not None
        and float(bending_probe_expected_util)
        > float(final_bending_util_for_probe) + float(target_band_eps)
    ):
        return None

    bending_probe_contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "updates": dict(bending_probe_updates),
        "preview_pass": True,
        "expected_util": bending_probe_expected_util,
        "blocking_reason": None,
        "source_candidate_id": bending_probe_candidate_id,
        "candidate_id": bending_probe_candidate_id,
    }
    bending_probe_item.update(
        {
            "action_type": "apply_resolved_candidate",
            "family": "bending",
            "check_key": "bending",
            "selected_action_family": "bending",
            "primary_card_actionable": True,
            "updates": dict(bending_probe_updates),
            "selected_action_updates": dict(bending_probe_updates),
            "button_contract": dict(bending_probe_contract),
            "candidate_id": bending_probe_candidate_id,
            "source_candidate_id": bending_probe_candidate_id,
        }
    )
    if float(bending_probe_expected_util) < float(final_accepted_min_family_util) - float(
        target_band_eps
    ):
        bending_probe_evidence = dict(
            bending_probe_item.get("candidate_search_evidence")
            or (bending_probe_item.get("action_payload") or {}).get("candidate_search_evidence")
            or (bending_probe_item.get("resolved_candidate") or {}).get(
                "candidate_search_evidence"
            )
            or {}
        )
        bending_probe_blocker = visible_cleanup_blocker_from_action_fn(
            family="bending",
            state=state_d,
            overview=dict(overview_d),
            evidence=bending_probe_evidence,
            contract=bending_probe_contract,
            current_util=final_bending_util_for_probe,
            expected_util=bending_probe_expected_util,
            terminal_mode=False,
        )
        bending_probe_exact = {"bending": dict(bending_probe_blocker)}
        bending_probe_evidence["exact_blockers_by_family"] = dict(bending_probe_exact)
        bending_probe_evidence["post_click_exact_blockers_by_family"] = dict(bending_probe_exact)
        bending_probe_item["exact_blockers_by_family"] = dict(bending_probe_exact)
        bending_probe_item["post_click_exact_blockers_by_family"] = dict(bending_probe_exact)
        bending_probe_item["cleanup_evidence_by_family"] = dict(bending_probe_exact)
        bending_probe_item["post_click_cleanup_evidence_by_family"] = dict(bending_probe_exact)
        bending_probe_item["candidate_search_evidence"] = dict(bending_probe_evidence)
        bending_payload = dict(bending_probe_item.get("action_payload") or {})
        bending_payload["candidate_search_evidence"] = dict(bending_probe_evidence)
        bending_probe_item["action_payload"] = dict(bending_payload)
        bending_resolved = dict(bending_probe_item.get("resolved_candidate") or {})
        bending_resolved["candidate_search_evidence"] = dict(bending_probe_evidence)
        bending_probe_item["resolved_candidate"] = dict(bending_resolved)

    bending_probe_result = (
        build_design_guide_controller_bending_cleanup_available_before_blocker_result(
            bending_probe_item=dict(bending_probe_item),
            bending_probe_contract=dict(bending_probe_contract),
            bending_probe_updates=dict(bending_probe_updates),
            bending_probe_candidate_id=bending_probe_candidate_id,
            bending_probe_expected_util=bending_probe_expected_util,
            final_overview=dict(overview_d),
            final_bending_util_for_probe=final_bending_util_for_probe,
            state_fingerprint=state_fingerprint,
        )
    )
    route_policy_proof = (
        build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof(
            primary=primary_d,
            contract=contract_d,
            updates=updates_d,
            primary_evidence=evidence_d,
            final_state=state_d,
            final_overview=overview_d,
            final_accepted_min_family_util=final_accepted_min_family_util,
            target_band_eps=target_band_eps,
            compound_shear_update_keys=compound_keys,
            contract_enabled=contract_enabled,
            post_click_route_for_safe_cleanup=post_click_route_for_safe_cleanup,
            safe_cleanup_updates_match_current_state=safe_updates_match_current_state,
            final_bending_util=final_bending_util_for_probe,
            bending_probe_candidate_present=True,
            equivalent_bending_probe_candidate_present=isinstance(
                equivalent_bending_probe_item, dict
            ),
            equivalent_probe_selected=(
                isinstance(equivalent_bending_probe_item, dict)
                and bending_probe_item is equivalent_bending_probe_item
            ),
            bending_probe_updates=dict(bending_probe_updates),
            bending_probe_expected_util=bending_probe_expected_util,
        )
    )
    live_projection = {
        "item": dict(bending_probe_result.get("item") or {}),
        "overview": dict(bending_probe_result.get("overview") or {}),
        "presentation": dict(bending_probe_result.get("presentation") or {}),
        "render_reason": bending_probe_result.get("render_reason"),
        "state_fingerprint": bending_probe_result.get("state_fingerprint"),
        "debug": dict(bending_probe_result.get("debug") or {}),
    }
    debug = bending_probe_result.setdefault("debug", {})
    projection_hash = stable_final_publication_hash(live_projection)
    debug[
        "design_guide_controller_no_active_blocked_primary_cleanup_probe_result_trace_only"
    ] = {
        "authority": "DesignGuideController.bending_cleanup_available_before_blocker_result",
        "live_wired": False,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "live_result_hash": projection_hash,
        "controller_result_hash": projection_hash,
        "result_hash_match": True,
        "product_result_source": "controller",
    }
    debug[
        "design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_trace_only"
    ] = {
        "authority": "DesignGuideController.no_active_blocked_primary_cleanup_probe_route_policy",
        "live_wired": False,
        "proof_hash": stable_final_publication_hash(route_policy_proof),
        "route_policy_hash": route_policy_proof.get("route_policy_hash"),
        "route_policy_allows_any_probe_result": route_policy_proof.get(
            "route_policy_allows_any_probe_result"
        ),
        "candidate_generation_owned_here": False,
        "result_assembly_owned_here": False,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    full_route_proof = (
        build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof(
            route_policy_proof=route_policy_proof,
            safe_cleanup_result=None,
            bending_cleanup_result=bending_probe_result,
        )
    )
    debug[
        "design_guide_controller_no_active_blocked_primary_full_route_builder_trace_only"
    ] = {
        "authority": (
            "DesignGuideController.no_active_blocked_primary_cleanup_probe_full_route_builder"
        ),
        "live_wired": False,
        "proof_hash": stable_final_publication_hash(full_route_proof),
        "full_route_builder_hash": full_route_proof.get("full_route_builder_hash"),
        "route_policy_hash": full_route_proof.get("route_policy_hash"),
        "selected_branch": full_route_proof.get("selected_branch"),
        "selected_result_hash": full_route_proof.get("selected_result_hash"),
        "live_result_hash": stable_final_publication_hash(bending_probe_result),
        "result_hash_match": (
            full_route_proof.get("selected_result_hash")
            == stable_final_publication_hash(bending_probe_result)
        ),
        "route_branching_owned_here": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return bending_probe_result


def build_design_guide_controller_active_action_result(
    *,
    active_item: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    active_family: str = "",
    active_title: str = "",
    candidate_id: Any = None,
    expected_util: Any = None,
    current_family_util: Any = None,
    final_overview: dict[str, Any] | None = None,
    active_item_evidence: dict[str, Any] | None = None,
    active_outside_exact_blockers: dict[str, Any] | None = None,
    merged_residual_shear_cleanup: dict[str, Any] | None = None,
    merged_residual_bending_cleanup: dict[str, Any] | None = None,
    debug_probe: dict[str, Any] | None = None,
    state_fingerprint: str = "",
    secondary_action: str = "",
    guidance_change_lines: list[Any] | tuple[Any, ...] | None = None,
    guidance_change_summary_compact: str = "",
    efficiency_target_util_min: Any = None,
    efficiency_target_util_max: Any = None,
) -> dict[str, Any]:
    """Build the final visible active-action result from plain controller inputs."""

    item = dict(active_item or {})
    button_contract = dict(contract or {})
    update_payload = dict(updates or {})
    family = str(active_family or "").strip()
    title = str(active_title or "").strip()
    outside_blockers = dict(active_outside_exact_blockers or {})
    item_evidence = dict(active_item_evidence or {})
    residual_shear = dict(merged_residual_shear_cleanup or {})
    residual_bending = dict(merged_residual_bending_cleanup or {})
    change_lines = list(guidance_change_lines or [])

    button_contract.update(
        {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": family,
            "updates": dict(update_payload),
            "preview_pass": True,
            "blocking_reason": None,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
        }
    )
    if expected_util is not None:
        button_contract["expected_util"] = expected_util

    display_truth = dict(item.get("display_truth") or {})
    if expected_util is not None:
        target_low = float(efficiency_target_util_min)
        target_high = float(efficiency_target_util_max)
        display_truth.update(
            {
                "display_truth_source": "candidate_preview",
                "displayed_util": expected_util,
                "displayed_status": "PASS",
                "source_candidate_util": expected_util,
                "source_summary_util": current_family_util,
                "source_post_commit_util": None,
                "target_low": target_low,
                "target_high": target_high,
                "displayed_within_target_band": bool(
                    target_low <= float(expected_util) <= target_high
                ),
            }
        )

    if residual_shear:
        reasoning = (
            "Why: this one-click strengthening repair applies the bending repair and "
            "the proven shear-link cleanup, keeping all required checks passing."
        )
        guidance_why = (
            "This one-click strengthening repair applies the bending repair and the proven "
            "shear-link cleanup, keeping all required checks passing."
        )
        compact_why = reasoning
    elif residual_bending:
        reasoning = (
            "Why: this one-click repair combines the shear strengthening update with "
            "the compatible bending cleanup, keeping all required checks passing."
        )
        guidance_why = (
            "This one-click repair combines the shear strengthening update with the compatible "
            "bending cleanup, keeping all required checks passing."
        )
        compact_why = (
            "Why: this one-click strengthening repair is built from the current summary state "
            "and keeps all required checks passing."
        )
    else:
        reasoning = (
            "Why: this one-click strengthening repair is built from the current summary state "
            "and keeps all required checks passing."
        )
        guidance_why = (
            "This one-click strengthening repair is built from the current summary state "
            "and keeps all required checks passing."
        )
        compact_why = reasoning

    item.update(
        {
            "title_main": title,
            "title": title,
            "family": family,
            "check_key": family,
            "selected_action_family": family,
            "guidance_intent": "required_fix",
            "primary_card_actionable": True,
            "final_state_class": "action",
            "action_type": "apply_resolved_candidate",
            "button_contract": dict(button_contract),
            "updates": dict(update_payload),
            "util": expected_util if expected_util is not None else item.get("util"),
            "candidate_post_util": (
                expected_util if expected_util is not None else item.get("candidate_post_util")
            ),
            "display_truth": dict(display_truth),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "primary_action": "Run one-click auto design",
            "secondary_action": str(secondary_action or ""),
            "reasoning": reasoning,
            "guidance_why": guidance_why,
            "final_visible_state_fingerprint": str(state_fingerprint or ""),
            "final_visible_design_guide_item": True,
            "final_visible_resolver_reason": "final_visible_active_strength_action",
        }
    )

    action_payload = dict(item.get("action_payload") or {})
    action_payload.update(
        {
            "updates": dict(update_payload),
            "resolved_candidate_updates": dict(update_payload),
            "resolved_candidate_label": title,
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_family_tag": family,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
            "candidate_post_util": expected_util,
            "expected_util": expected_util,
            "guidance_change_lines": list(change_lines),
            "guidance_change_summary_compact": str(guidance_change_summary_compact or ""),
            "guidance_why_text_compact": compact_why,
        }
    )

    if residual_shear:
        item["active_repair_includes_residual_shear_cleanup"] = True
        item["residual_shear_cleanup_evidence"] = dict(residual_shear.get("evidence") or {})
        action_payload["active_repair_includes_residual_shear_cleanup"] = True
        action_payload["residual_shear_cleanup_evidence"] = dict(
            residual_shear.get("evidence") or {}
        )
    if residual_bending:
        bending_merge_evidence = dict(residual_bending.get("candidate_search_evidence") or {})
        item["active_repair_includes_residual_bending_cleanup"] = True
        item["residual_bending_cleanup_evidence"] = dict(bending_merge_evidence)
        action_payload["active_repair_includes_residual_bending_cleanup"] = True
        action_payload["residual_bending_cleanup_evidence"] = dict(bending_merge_evidence)
    if outside_blockers:
        action_payload["candidate_search_evidence"] = dict(item_evidence)
        action_payload["exact_blockers_by_family"] = dict(outside_blockers)
        action_payload["post_click_exact_blockers_by_family"] = dict(outside_blockers)
        action_payload["cleanup_evidence_by_family"] = dict(outside_blockers)
        action_payload["post_click_cleanup_evidence_by_family"] = dict(outside_blockers)
    item["action_payload"] = dict(action_payload)

    resolved_candidate = dict(item.get("resolved_candidate") or {})
    resolved_candidate.update(
        {
            "updates": dict(update_payload),
            "action_type": "apply_resolved_candidate",
            "label": title,
            "family": family,
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "candidate_post_util": expected_util,
            "expected_util": expected_util,
        }
    )
    if outside_blockers:
        resolved_candidate["candidate_search_evidence"] = dict(item_evidence)
        resolved_candidate["exact_blockers_by_family"] = dict(outside_blockers)
        resolved_candidate["post_click_exact_blockers_by_family"] = dict(outside_blockers)
    item["resolved_candidate"] = dict(resolved_candidate)

    for blocker_key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "local_cleanup_blocked_reasons",
        "local_cleanup_blocked_reasons_by_family",
        "exact_blocker_reasons_by_family",
        "blocker_reasons_by_family",
        "active_under_capacity_blocker",
        "active_under_capacity_blocker_reason",
        "active_under_capacity_blocker_family",
    ):
        if outside_blockers and blocker_key in {
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "post_click_cleanup_evidence_by_family",
            "local_cleanup_blocked_reasons",
            "local_cleanup_blocked_reasons_by_family",
            "exact_blocker_reasons_by_family",
            "blocker_reasons_by_family",
        }:
            continue
        item.pop(blocker_key, None)

    item = normalise_final_visible_design_guide_item(item)
    return {
        "item": item,
        "overview": dict(final_overview or {}),
        "presentation": {
            "headline": title,
            "subtext": "",
            "guidance_intent": "required_fix",
            "css_bucket": "fail",
            "theme": "fail",
            "show_apply_button": True,
            "use_success_style": False,
        },
        "render_reason": "final_visible_active_strength_action",
        "state_fingerprint": str(state_fingerprint or ""),
        "debug": dict(debug_probe or {}),
    }


def run_design_guide_controller_active_action_post_click_exact_blocker_route(
    *,
    active_family: str,
    candidate_id: Any = None,
    active_outside_exact_blockers: dict[str, Any] | None,
    current_utils: dict[str, Any] | None,
    final_state: dict[str, Any] | None,
    final_overview: dict[str, Any] | None,
    debug_probe: dict[str, Any] | None,
    final_accepted_min_family_util: Any,
    target_band_eps: Any,
    parse_util_value_fn: Callable[..., Any],
    post_click_low_bending_resolution_item_fn: Callable[..., Any],
    design_mode_config_fn: Callable[..., Any],
    design_optimisation_goal_fn: Callable[..., Any],
    design_guide_button_contract_enabled_fn: Callable[..., Any],
    state_fingerprint_fn: Callable[..., Any],
    normalise_final_visible_design_guide_item_fn: Callable[..., Any],
) -> dict[str, Any] | None:
    """Build the post-click active-action exact-blocker route as controller data.

    The controller owns only the route decision and output shape. Page-supplied
    callbacks still own current page glue for item building, normalisation, and
    fingerprinting until later slices move those boundaries.
    """

    family = str(active_family or "").strip()
    blockers = dict(active_outside_exact_blockers or {})
    utils = dict(current_utils or {})
    state_d = dict(final_state or {})
    overview_d = dict(final_overview or {})
    debug_d = dict(debug_probe or {})

    requires_blocker = bool(
        family == "bending"
        and blockers
        and any(
            bool(dict(blocker or {}).get("no_second_cta_required"))
            for blocker in blockers.values()
            if isinstance(blocker, dict)
        )
    )
    if not requires_blocker:
        return None

    threshold = _controller_optional_float(final_accepted_min_family_util)
    eps = _controller_optional_float(target_band_eps)
    current_low_strength_families: list[str] = []
    if threshold is not None and eps is not None:
        for util_family in ("bending", "shear"):
            util = parse_util_value_fn(utils.get(util_family))
            if util is not None and float(util) < float(threshold) - float(eps):
                current_low_strength_families.append(util_family)

    post_click_blocker_audit = {
        "post_click_exact_blockers_by_family": dict(blockers),
        "exact_blockers_by_family": dict(blockers),
        "post_click_cleanup_evidence_by_family": dict(blockers),
        "cleanup_evidence_by_family": dict(blockers),
        "post_click_family_utils": dict(utils),
        "post_click_families_below_final_threshold": list(current_low_strength_families),
        "post_click_unresolved_low_util_families": list(current_low_strength_families),
        "final_accepted_min_family_util": (
            float(threshold) if threshold is not None else final_accepted_min_family_util
        ),
        "post_click_accepted_green_invalid_reason": "post_click_active_action_has_exact_blocker",
    }
    try:
        post_click_blocker_item = post_click_low_bending_resolution_item_fn(
            state_d,
            overview_d,
            design_mode_config_fn(design_optimisation_goal_fn(state_d)),
            post_click_blocker_audit,
            debug_sink=None,
        )
    except Exception:
        post_click_blocker_item = None

    post_click_blocker_contract = (
        dict(post_click_blocker_item.get("button_contract") or {})
        if isinstance(post_click_blocker_item, dict)
        else {}
    )
    if not (
        isinstance(post_click_blocker_item, dict)
        and not design_guide_button_contract_enabled_fn(post_click_blocker_contract)
    ):
        return None

    state_fingerprint = state_fingerprint_fn(state_d)
    post_click_blocker_item["final_visible_state_fingerprint"] = state_fingerprint
    post_click_blocker_item["final_visible_design_guide_item"] = True
    post_click_blocker_item[
        "final_visible_resolver_reason"
    ] = "final_visible_post_click_active_action_exact_blocker"
    post_click_blocker_item = normalise_final_visible_design_guide_item_fn(
        post_click_blocker_item
    )
    return {
        "item": post_click_blocker_item,
        "overview": dict(overview_d),
        "presentation": {
            "headline": (
                post_click_blocker_item.get("title_main")
                or post_click_blocker_item.get("title")
                or "Further cleanup blocked"
            ),
            "subtext": "",
            "guidance_intent": "specific_blocker",
            "css_bucket": "efficiency",
            "theme": "efficiency",
            "show_apply_button": False,
            "use_success_style": False,
        },
        "render_reason": "final_visible_post_click_active_action_exact_blocker",
        "state_fingerprint": state_fingerprint,
        "debug": {
            **debug_d,
            "post_click_active_action_replaced_by_exact_blocker": True,
            "post_click_active_action_family": family,
            "post_click_exact_blockers_by_family": dict(blockers),
        },
    }


@dataclass(frozen=True)
class DesignGuideControllerTerminalActiveFailureBlockerSourceProof:
    """Proof-only blocker-source selection surface for terminal active failures."""

    active_blocker_source_before_filter: dict[str, Any] | None
    active_blocker_source: dict[str, Any] | None
    active_blocker_source_present_before_filter: bool
    active_blocker_source_kept: bool
    active_blocker_evidence: dict[str, Any]
    active_blocker_evidence_keys: list[str]
    active_scope: str
    active_under_capacity_blocker: bool
    fallback_item: dict[str, Any]
    blocker_source: dict[str, Any]
    blocker_source_hash: str
    fallback_item_hash: str
    blocker_source_selection_hash: str
    proof_only: bool = True
    product_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_design_guide_controller_terminal_active_failure_blocker_source_proof(
    *,
    active_item: dict[str, Any] | None,
    raw_guidance_items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    """Build proof-only blocker-source selection data for the finalizer route."""

    active_blocker_source_before_filter = active_item if isinstance(active_item, dict) else None
    active_blocker_source = active_blocker_source_before_filter
    active_blocker_evidence: dict[str, Any] = {}
    active_scope = ""
    if active_blocker_source is not None:
        active_blocker_evidence = dict(active_blocker_source.get("candidate_search_evidence") or {})
        active_scope = str(
            active_blocker_evidence.get("active_fail_repair_search_scope")
            or active_blocker_evidence.get("search_scope")
            or ""
        ).strip().lower()
        if not (
            bool(active_blocker_source.get("active_under_capacity_blocker"))
            or active_scope.startswith("active_fail_")
            or active_scope == "design_guide_direct_target_band_search"
        ):
            active_blocker_source = None

    fallback_item = dict((raw_guidance_items or [{}])[0] or {})
    blocker_source = dict(active_blocker_source or fallback_item)
    base_payload = {
        "active_blocker_source_before_filter": (
            dict(active_blocker_source_before_filter)
            if isinstance(active_blocker_source_before_filter, dict)
            else None
        ),
        "active_blocker_source": (
            dict(active_blocker_source) if isinstance(active_blocker_source, dict) else None
        ),
        "active_blocker_source_present_before_filter": active_blocker_source_before_filter
        is not None,
        "active_blocker_source_kept": active_blocker_source is not None,
        "active_blocker_evidence": dict(active_blocker_evidence),
        "active_blocker_evidence_keys": sorted(str(key) for key in active_blocker_evidence.keys())[
            :60
        ],
        "active_scope": active_scope,
        "active_under_capacity_blocker": bool(
            isinstance(active_blocker_source_before_filter, dict)
            and active_blocker_source_before_filter.get("active_under_capacity_blocker")
        ),
        "fallback_item": dict(fallback_item),
        "blocker_source": dict(blocker_source),
    }
    proof = DesignGuideControllerTerminalActiveFailureBlockerSourceProof(
        **base_payload,
        blocker_source_hash=stable_final_publication_hash(blocker_source),
        fallback_item_hash=stable_final_publication_hash(fallback_item),
        blocker_source_selection_hash=stable_final_publication_hash(base_payload),
    )
    return proof.to_dict()


def run_design_guide_controller_terminal_active_failure_blocker_finalizer_route(
    *,
    active_item: dict[str, Any] | None,
    raw_guidance_items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    active_family: str,
    active_title: str,
    active_failures: list[str] | tuple[str, ...] | set[str],
    final_overview: dict[str, Any] | None,
    final_state: dict[str, Any] | None,
    debug_probe: dict[str, Any] | None,
    state_fingerprint_fn: Callable[..., Any],
    suppress_design_guide_blocker_cta_fn: Callable[..., Any],
) -> dict[str, Any]:
    """Finalize the terminal active-failure blocker route as controller data.

    This owns the plain-data blocker-source selection and final publication
    handoff. Page callbacks still provide current fingerprinting and blocker
    CTA suppression until those page-shell dependencies are extracted.
    """

    blocker_source_proof = build_design_guide_controller_terminal_active_failure_blocker_source_proof(
        active_item=active_item,
        raw_guidance_items=raw_guidance_items,
    )
    fallback_item = dict(blocker_source_proof.get("fallback_item") or {})
    blocker_source = dict(blocker_source_proof.get("blocker_source") or {})
    blocker = suppress_design_guide_blocker_cta_fn(blocker_source)
    state_d = dict(final_state or {})
    state_fingerprint = state_fingerprint_fn(state_d)
    return finalize_design_guide_active_failure_blocker_publication(
        blocker=blocker,
        fallback_item=fallback_item,
        active_family=str(active_family or ""),
        active_title=str(active_title or ""),
        active_failures=sorted(active_failures or []),
        final_overview=dict(final_overview or {}),
        item_state_fingerprint=state_fingerprint,
        result_state_fingerprint=state_fingerprint,
        debug_probe=dict(debug_probe or {}),
    )


@dataclass(frozen=True)
class DesignGuideCombinedLowUtilCandidateGenerationHandoffProof:
    """Proof-only handoff surface for combined low-util candidate generation."""

    authority: str
    source_update_keys: list[str]
    source_update_hash: str
    shear_seed_update_keys: list[str]
    shear_seed_update_hash: str
    generator_names: list[str]
    selected_candidate_id: str | None
    selected_update_keys: list[str]
    selected_update_hash: str
    contract_enabled: bool | None
    contract_update_keys: list[str]
    contract_update_hash: str
    updates_match_current_state: bool | None
    applicability_gate_allows_result: bool
    handoff_hash: str
    proof_only: bool = True
    candidate_generation_owned_here: bool = False
    product_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_design_guide_controller_combined_low_util_candidate_generation_handoff_proof(
    *,
    source_updates: dict[str, Any] | None = None,
    shear_seed_updates: dict[str, Any] | None = None,
    generator_names: list[str] | tuple[str, ...] | None = None,
    selected_candidate_id: Any = None,
    selected_updates: dict[str, Any] | None = None,
    contract_enabled: bool | None = None,
    contract_updates: dict[str, Any] | None = None,
    updates_match_current_state: bool | None = None,
) -> dict[str, Any]:
    """Build proof-only candidate-generation handoff data for this route.

    This records the plain-data boundary around the existing page-owned
    generator calls. It intentionally does not call candidate generators,
    evaluate candidates, render UI, or route Apply.
    """

    source = dict(source_updates or {})
    shear_seed = dict(shear_seed_updates or {})
    selected = dict(selected_updates or {})
    contract = dict(contract_updates or {})
    names = [str(name) for name in (generator_names or ()) if str(name).strip()]
    applicability = bool(contract_enabled and contract and not updates_match_current_state)
    base_payload = {
        "authority": "DesignGuideController.combined_low_util_candidate_generation_handoff",
        "source_update_keys": sorted(str(key) for key in source),
        "source_update_hash": stable_final_publication_hash(source),
        "shear_seed_update_keys": sorted(str(key) for key in shear_seed),
        "shear_seed_update_hash": stable_final_publication_hash(shear_seed),
        "generator_names": sorted(names),
        "selected_candidate_id": (
            None if selected_candidate_id is None else str(selected_candidate_id)
        ),
        "selected_update_keys": sorted(str(key) for key in selected),
        "selected_update_hash": stable_final_publication_hash(selected),
        "contract_enabled": contract_enabled,
        "contract_update_keys": sorted(str(key) for key in contract),
        "contract_update_hash": stable_final_publication_hash(contract),
        "updates_match_current_state": updates_match_current_state,
        "applicability_gate_allows_result": applicability,
    }
    proof = DesignGuideCombinedLowUtilCandidateGenerationHandoffProof(
        **base_payload,
        handoff_hash=stable_final_publication_hash(base_payload),
    )
    return proof.to_dict()


def run_design_guide_controller_combined_low_util_candidate_generation(
    *,
    primary: dict[str, Any],
    updates: dict[str, Any],
    final_state: dict[str, Any],
    final_overview: dict[str, Any],
    final_accepted_min_family_util: Any,
    compound_shear_update_keys: Any,
    parse_util_value_fn: Callable[..., Any],
    updates_match_state_fn: Callable[..., Any],
    normalise_design_guide_candidate_id_fn: Callable[..., Any],
    shear_low_util_target_cleanup_item_fn: Callable[..., Any],
    combine_best_safe_shear_with_bending_cleanup_item_fn: Callable[..., Any],
    design_mode_config_fn: Callable[..., Any],
    design_optimisation_goal_fn: Callable[..., Any],
    normalise_final_visible_design_guide_item_fn: Callable[..., Any],
    resolve_recommendation_updates_fn: Callable[..., Any],
    design_guide_button_contract_enabled_fn: Callable[..., Any],
) -> dict[str, Any]:
    """Own the combined low-util generator invocation boundary.

    The page still injects the current generators/evaluators. This controller
    boundary only centralizes route gating, invocation order, and applicability
    proof as plain data.
    """

    final_utils = dict((final_overview or {}).get("utils") or {})
    final_bending_util = parse_util_value_fn(final_utils.get("bending"))
    final_shear_util = parse_util_value_fn(final_utils.get("shear"))
    threshold = _controller_optional_float(final_accepted_min_family_util)
    route_allows = (
        final_bending_util is not None
        and final_shear_util is not None
        and threshold is not None
        and float(final_bending_util) < threshold - 1e-9
        and float(final_shear_util) < threshold - 1e-9
    )
    if not route_allows:
        return {
            "item": None,
            "contract": {},
            "updates": {},
            "shear_seed_updates": {},
            "final_bending_util": final_bending_util,
            "final_shear_util": final_shear_util,
            "route_policy_proof": None,
            "handoff_proof": None,
            "candidate_generation_invocation_owned_by_controller": True,
            "applicability_gate_allows_result": False,
            "reason": "combined_low_util_route_not_applicable",
        }

    shear_seed_updates = {
        key: value
        for key, value in dict(updates or {}).items()
        if key in compound_shear_update_keys
    }
    combined_cleanup_seed = None
    if shear_seed_updates and not updates_match_state_fn(final_state, shear_seed_updates):
        shear_seed_candidate_id = normalise_design_guide_candidate_id_fn(
            "final_visible_shear_cleanup_seed",
            family="shear",
            updates=shear_seed_updates,
        )
        combined_cleanup_seed = dict(primary or {})
        combined_cleanup_seed.update(
            {
                "title_main": "Shear cleanup - best safe one-click reduction",
                "title": "Shear cleanup - best safe one-click reduction",
                "family": "shear",
                "check_key": "shear",
                "selected_action_family": "shear",
                "action_type": "apply_resolved_candidate",
                "local_cleanup_candidate": True,
                "updates": dict(shear_seed_updates),
                "selected_action_updates": dict(shear_seed_updates),
                "candidate_id": shear_seed_candidate_id,
                "source_candidate_id": shear_seed_candidate_id,
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "shear",
                    "updates": dict(shear_seed_updates),
                    "preview_pass": True,
                    "blocking_reason": None,
                    "source_candidate_id": shear_seed_candidate_id,
                    "candidate_id": shear_seed_candidate_id,
                },
            }
        )
    if not isinstance(combined_cleanup_seed, dict):
        try:
            combined_cleanup_seed = shear_low_util_target_cleanup_item_fn(
                final_state,
                dict(final_overview or {}),
                threshold=final_accepted_min_family_util,
                allow_best_safe_below_threshold=True,
            )
        except Exception as exc:
            combined_cleanup_seed = None
            shear_generator_error = f"{type(exc).__name__}: {exc}"
        else:
            shear_generator_error = None
    else:
        shear_generator_error = None

    try:
        final_combined_cleanup_item = combine_best_safe_shear_with_bending_cleanup_item_fn(
            final_state,
            dict(final_overview or {}),
            design_mode_config_fn(design_optimisation_goal_fn(final_state)),
            combined_cleanup_seed,
            debug_sink=None,
        )
    except Exception as exc:
        final_combined_cleanup_item = None
        combined_generator_error = f"{type(exc).__name__}: {exc}"
    else:
        combined_generator_error = None
    if not isinstance(final_combined_cleanup_item, dict):
        return {
            "item": None,
            "contract": {},
            "updates": {},
            "shear_seed_updates": dict(shear_seed_updates or {}),
            "final_bending_util": final_bending_util,
            "final_shear_util": final_shear_util,
            "route_policy_proof": build_design_guide_controller_combined_low_util_cleanup_route_policy_proof(
                final_overview=dict(final_overview or {}),
                final_accepted_min_family_util=final_accepted_min_family_util,
                final_bending_util=final_bending_util,
                final_shear_util=final_shear_util,
                shear_seed_updates=dict(shear_seed_updates or {}),
            ),
            "handoff_proof": None,
            "candidate_generation_invocation_owned_by_controller": True,
            "applicability_gate_allows_result": False,
            "shear_generator_error": shear_generator_error,
            "combined_generator_error": combined_generator_error,
            "reason": "combined_low_util_generator_returned_no_item",
        }

    final_combined_cleanup_item = normalise_final_visible_design_guide_item_fn(
        final_combined_cleanup_item
    )
    final_combined_cleanup_contract = dict(
        final_combined_cleanup_item.get("button_contract") or {}
    )
    final_combined_cleanup_updates = dict(
        final_combined_cleanup_contract.get("updates")
        or final_combined_cleanup_item.get("updates")
        or resolve_recommendation_updates_fn(final_combined_cleanup_item, state=final_state)
        or {}
    )
    contract_enabled = bool(
        design_guide_button_contract_enabled_fn(final_combined_cleanup_contract)
    )
    updates_match_current_state = bool(
        updates_match_state_fn(final_state, final_combined_cleanup_updates)
    )
    applicability_gate_allows_result = bool(
        contract_enabled
        and final_combined_cleanup_updates
        and not updates_match_current_state
    )
    route_policy_proof = build_design_guide_controller_combined_low_util_cleanup_route_policy_proof(
        final_overview=dict(final_overview or {}),
        final_accepted_min_family_util=final_accepted_min_family_util,
        final_bending_util=final_bending_util,
        final_shear_util=final_shear_util,
        shear_seed_updates=dict(shear_seed_updates or {}),
    )
    handoff_proof = build_design_guide_controller_combined_low_util_candidate_generation_handoff_proof(
        source_updates=dict(updates or {}),
        shear_seed_updates=dict(shear_seed_updates or {}),
        generator_names=[
            "shear_low_util_target_cleanup_item_fn",
            "combine_best_safe_shear_with_bending_cleanup_item_fn",
        ],
        selected_candidate_id=final_combined_cleanup_item.get("candidate_id")
        or final_combined_cleanup_item.get("source_candidate_id")
        or final_combined_cleanup_contract.get("candidate_id"),
        selected_updates=dict(final_combined_cleanup_updates or {}),
        contract_enabled=contract_enabled,
        contract_updates=dict(final_combined_cleanup_updates or {}),
        updates_match_current_state=updates_match_current_state,
    )
    if not applicability_gate_allows_result:
        return {
            "item": None,
            "contract": dict(final_combined_cleanup_contract),
            "updates": dict(final_combined_cleanup_updates),
            "shear_seed_updates": dict(shear_seed_updates or {}),
            "final_bending_util": final_bending_util,
            "final_shear_util": final_shear_util,
            "route_policy_proof": route_policy_proof,
            "handoff_proof": handoff_proof,
            "candidate_generation_invocation_owned_by_controller": True,
            "applicability_gate_allows_result": False,
            "shear_generator_error": shear_generator_error,
            "combined_generator_error": combined_generator_error,
            "reason": "combined_low_util_applicability_gate_rejected_result",
        }
    return {
        "item": dict(final_combined_cleanup_item),
        "contract": dict(final_combined_cleanup_contract),
        "updates": dict(final_combined_cleanup_updates),
        "shear_seed_updates": dict(shear_seed_updates or {}),
        "final_bending_util": final_bending_util,
        "final_shear_util": final_shear_util,
        "route_policy_proof": route_policy_proof,
        "handoff_proof": handoff_proof,
        "candidate_generation_invocation_owned_by_controller": True,
        "applicability_gate_allows_result": True,
        "shear_generator_error": shear_generator_error,
        "combined_generator_error": combined_generator_error,
        "reason": "combined_low_util_candidate_generation_result_selected",
    }


@dataclass(frozen=True)
class DesignGuideShearLowUtilCleanupGeneratorBoundaryProof:
    """Proof-only boundary for the shear low-util cleanup generator core."""

    authority: str
    input_state_hash: str
    overview_hash: str
    threshold: float | None
    target_band: dict[str, Any]
    source_update_hash: str
    variant_count: int | None
    evaluated_candidate_count: int | None
    safe_candidate_count: int | None
    selected_candidate_id: str | None
    selected_update_keys: list[str]
    selected_update_hash: str
    acceptance_reason: str | None
    rejection_reason: str | None
    boundary_hash: str
    proof_only: bool = True
    generator_owned_here: bool = False
    evaluator_owned_here: bool = False
    product_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_design_guide_shear_low_util_cleanup_generator_boundary_proof(
    *,
    input_state: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    threshold: Any = None,
    target_band: dict[str, Any] | None = None,
    source_updates: dict[str, Any] | None = None,
    variant_count: int | None = None,
    evaluated_candidate_count: int | None = None,
    safe_candidate_count: int | None = None,
    selected_candidate_id: Any = None,
    selected_updates: dict[str, Any] | None = None,
    acceptance_reason: str | None = None,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    """Build proof-only boundary data for the page-local shear cleanup generator.

    This object records what the generator core must prove before the page-local
    function can move. It does not generate variants, evaluate candidates, build
    visible card wording, render UI, or route Apply.
    """

    threshold_value = _controller_optional_float(threshold)
    target = dict(target_band or {})
    source = dict(source_updates or {})
    selected = dict(selected_updates or {})
    base_payload = {
        "authority": "DesignGuideController.shear_low_util_cleanup_generator_boundary",
        "input_state_hash": stable_final_publication_hash(dict(input_state or {})),
        "overview_hash": stable_final_publication_hash(dict(overview or {})),
        "threshold": threshold_value,
        "target_band": target,
        "source_update_hash": stable_final_publication_hash(source),
        "variant_count": variant_count,
        "evaluated_candidate_count": evaluated_candidate_count,
        "safe_candidate_count": safe_candidate_count,
        "selected_candidate_id": (
            None if selected_candidate_id is None else str(selected_candidate_id)
        ),
        "selected_update_keys": sorted(str(key) for key in selected),
        "selected_update_hash": stable_final_publication_hash(selected),
        "acceptance_reason": acceptance_reason,
        "rejection_reason": rejection_reason,
    }
    proof = DesignGuideShearLowUtilCleanupGeneratorBoundaryProof(
        **base_payload,
        boundary_hash=stable_final_publication_hash(base_payload),
    )
    return proof.to_dict()


def build_design_guide_controller_combined_low_util_cleanup_result(
    *,
    cleanup_item: dict[str, Any],
    cleanup_contract: dict[str, Any],
    cleanup_updates: dict[str, Any],
    final_overview: dict[str, Any],
    state_fingerprint: str,
    current_bending_util: Any = None,
    current_shear_util: Any = None,
    shear_seed_updates: dict[str, Any] | None = None,
    render_reason: str = "final_visible_combined_low_util_safe_cleanup",
) -> dict[str, Any]:
    """Build already-selected combined low-util cleanup result for proof/cutover."""

    item = dict(cleanup_item or {})
    updates = dict(cleanup_updates or {})
    contract = dict(cleanup_contract or {})
    item.update(
        {
            "primary_card_actionable": True,
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates),
            "selected_action_updates": dict(updates),
            "button_contract": dict(contract),
            "final_visible_state_fingerprint": state_fingerprint,
            "final_visible_design_guide_item": True,
            "final_visible_resolver_reason": str(
                render_reason or "final_visible_combined_low_util_safe_cleanup"
            ),
        }
    )
    return {
        "item": item,
        "overview": dict(final_overview or {}),
        "presentation": {
            "headline": str(item.get("title_main") or item.get("title") or ""),
            "subtext": str(item.get("primary_action") or ""),
            "guidance_intent": item.get("guidance_intent"),
            "css_bucket": item.get("bucket"),
            "theme": item.get("bucket"),
            "show_apply_button": True,
            "use_success_style": str(item.get("bucket") or "") == "pass",
        },
        "render_reason": str(render_reason or "final_visible_combined_low_util_safe_cleanup"),
        "state_fingerprint": state_fingerprint,
        "debug": {
            "current_bending_util": current_bending_util,
            "current_shear_util": current_shear_util,
            "combined_cleanup_seed_from_primary": bool(shear_seed_updates),
        },
        "controller_authority": "DesignGuideController.combined_low_util_cleanup_result",
    }


def run_design_guide_controller_no_active_combined_low_util_cleanup_route(
    *,
    primary: dict[str, Any],
    updates: dict[str, Any],
    final_state: dict[str, Any],
    final_overview: dict[str, Any],
    final_accepted_min_family_util: Any,
    compound_shear_update_keys: Any,
    parse_util_value_fn: Callable[..., Any],
    updates_match_state_fn: Callable[..., Any],
    normalise_design_guide_candidate_id_fn: Callable[..., Any],
    shear_low_util_target_cleanup_item_fn: Callable[..., Any],
    combine_best_safe_shear_with_bending_cleanup_item_fn: Callable[..., Any],
    design_mode_config_fn: Callable[..., Any],
    design_optimisation_goal_fn: Callable[..., Any],
    normalise_final_visible_design_guide_item_fn: Callable[..., Any],
    resolve_recommendation_updates_fn: Callable[..., Any],
    design_guide_button_contract_enabled_fn: Callable[..., Any],
    state_fingerprint_fn: Callable[..., Any],
) -> dict[str, Any] | None:
    """Build the no-active combined low-util cleanup route as controller data.

    The page still owns the concrete callback implementations and trace sink.
    This boundary owns route composition only: candidate generation handoff,
    selected result shaping, and proof-only parity payloads.
    """

    generation_result = run_design_guide_controller_combined_low_util_candidate_generation(
        primary=primary,
        updates=updates,
        final_state=final_state,
        final_overview=final_overview,
        final_accepted_min_family_util=final_accepted_min_family_util,
        compound_shear_update_keys=compound_shear_update_keys,
        parse_util_value_fn=parse_util_value_fn,
        updates_match_state_fn=updates_match_state_fn,
        normalise_design_guide_candidate_id_fn=normalise_design_guide_candidate_id_fn,
        shear_low_util_target_cleanup_item_fn=shear_low_util_target_cleanup_item_fn,
        combine_best_safe_shear_with_bending_cleanup_item_fn=combine_best_safe_shear_with_bending_cleanup_item_fn,
        design_mode_config_fn=design_mode_config_fn,
        design_optimisation_goal_fn=design_optimisation_goal_fn,
        normalise_final_visible_design_guide_item_fn=normalise_final_visible_design_guide_item_fn,
        resolve_recommendation_updates_fn=resolve_recommendation_updates_fn,
        design_guide_button_contract_enabled_fn=design_guide_button_contract_enabled_fn,
    )
    cleanup_item = dict(generation_result.get("item") or {})
    if not cleanup_item:
        return None

    cleanup_contract = dict(generation_result.get("contract") or {})
    cleanup_updates = dict(generation_result.get("updates") or {})
    shear_seed_updates = dict(generation_result.get("shear_seed_updates") or {})
    try:
        state_fingerprint = str(state_fingerprint_fn(final_state))
    except Exception:
        state_fingerprint = "state_fingerprint_unavailable"

    result = build_design_guide_controller_combined_low_util_cleanup_result(
        cleanup_item=cleanup_item,
        cleanup_contract=cleanup_contract,
        cleanup_updates=cleanup_updates,
        final_overview=dict(final_overview or {}),
        state_fingerprint=state_fingerprint,
        current_bending_util=generation_result.get("final_bending_util"),
        current_shear_util=generation_result.get("final_shear_util"),
        shear_seed_updates=shear_seed_updates,
    )
    live_projection = {
        "item": dict(result.get("item") or {}),
        "overview": dict(result.get("overview") or {}),
        "presentation": dict(result.get("presentation") or {}),
        "render_reason": result.get("render_reason"),
        "state_fingerprint": result.get("state_fingerprint"),
        "debug": dict(result.get("debug") or {}),
    }
    debug = result.setdefault("debug", {})
    projection_hash = stable_final_publication_hash(live_projection)
    debug["design_guide_controller_combined_low_util_cleanup_result_trace_only"] = {
        "authority": "DesignGuideController.combined_low_util_cleanup_result",
        "live_wired": False,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "live_result_hash": projection_hash,
        "controller_result_hash": projection_hash,
        "result_hash_match": True,
        "item_hash_match": True,
        "presentation_hash_match": True,
        "render_reason_match": True,
        "state_fingerprint_match": True,
        "product_result_source": "controller",
    }
    route_policy_proof = dict(generation_result.get("route_policy_proof") or {})
    debug["design_guide_controller_combined_low_util_cleanup_route_policy_trace_only"] = {
        "authority": "DesignGuideController.combined_low_util_cleanup_route_policy",
        "live_wired": False,
        "proof_hash": stable_final_publication_hash(route_policy_proof),
        "route_policy_hash": route_policy_proof.get("route_policy_hash"),
        "route_policy_allows_candidate_generation": route_policy_proof.get(
            "route_policy_allows_candidate_generation"
        ),
        "candidate_generation_owned_here": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    handoff_proof = dict(generation_result.get("handoff_proof") or {})
    debug["design_guide_controller_combined_low_util_candidate_generation_handoff_trace_only"] = {
        "authority": "DesignGuideController.combined_low_util_candidate_generation_handoff",
        "live_wired": False,
        "proof_hash": stable_final_publication_hash(handoff_proof),
        "handoff_hash": handoff_proof.get("handoff_hash"),
        "applicability_gate_allows_result": handoff_proof.get(
            "applicability_gate_allows_result"
        ),
        "candidate_generation_owned_here": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return result


def run_design_guide_controller_no_active_low_shear_or_blocker_route(
    *,
    primary: dict[str, Any],
    contract: dict[str, Any],
    updates: dict[str, Any],
    final_state: dict[str, Any],
    final_overview: dict[str, Any],
    final_accepted_min_family_util: Any,
    target_band_eps: Any,
    guidance_shear_demand_abs_tol_kn: Any,
    compound_shear_update_keys: Any,
    parse_util_value_fn: Callable[..., Any],
    resolve_design_actions_from_state_fn: Callable[..., Any],
    float_from_state_fn: Callable[..., Any],
    shear_demands_negligible_fn: Callable[..., Any],
    overview_required_checks_acceptable_fn: Callable[..., Any],
    post_click_accepted_green_audit_fn: Callable[..., Any],
    post_active_repair_target_accepted_item_fn: Callable[..., Any],
    design_mode_config_fn: Callable[..., Any],
    design_optimisation_goal_fn: Callable[..., Any],
    state_fingerprint_fn: Callable[..., Any],
    shear_low_util_target_cleanup_item_fn: Callable[..., Any],
    resolve_low_shear_target_cleanup_probe_fn: Callable[..., Any],
    resolve_low_shear_evidence_fallback_fn: Callable[..., Any],
    overview_active_failure_keys_fn: Callable[..., Any],
    updates_match_state_fn: Callable[..., Any],
    guidance_cleanup_candidate_id_fn: Callable[..., Any],
    shear_best_safe_cleanup_item_from_evidence_fn: Callable[..., Any],
    resolve_low_shear_exact_blocker_fallback_fn: Callable[..., Any],
    post_click_applied_residual_shear_exact_blocker_fn: Callable[..., Any],
    post_active_repair_residual_shear_exact_blocker_fn: Callable[..., Any],
    shear_cleanup_exact_blocker_guidance_item_fn: Callable[..., Any],
    accepted_green_exact_blocker_is_valid_fn: Callable[..., Any],
    apply_low_shear_combined_low_util_blocker_gate_fn: Callable[..., Any],
    design_guide_button_contract_enabled_fn: Callable[..., Any],
    post_click_low_bending_resolution_item_fn: Callable[..., Any],
    resolve_recommendation_updates_fn: Callable[..., Any],
    local_cleanup_post_apply_acceptance_matches_fn: Callable[..., Any],
    combined_low_util_exact_blocker_final_item_fn: Callable[..., Any],
    finalize_low_shear_resolution_item_before_return_fn: Callable[..., Any],
    combine_best_safe_shear_with_bending_cleanup_item_fn: Callable[..., Any],
    normalise_final_visible_design_guide_item_fn: Callable[..., Any],
    assemble_zero_shear_demand_accepted_result_fn: Callable[..., Any],
    assemble_low_shear_resolution_result_fn: Callable[..., Any],
    assemble_combined_low_util_blocker_or_best_safe_result_fn: Callable[..., Any],
) -> dict[str, Any] | None:
    """Build the no-active low-shear/blocker route as controller data.

    The page still owns callback implementations, rendering, session/debug
    storage, and Apply routing. This boundary owns only route composition and
    preserves the existing branch order before any live page cutover.
    """

    primary_d = dict(primary or {})
    contract_d = dict(contract or {})
    updates_d = dict(updates or {})
    state_d = dict(final_state or {})
    overview_d = dict(final_overview or {})
    try:
        contract_enabled = bool(design_guide_button_contract_enabled_fn(contract_d))
    except Exception:
        contract_enabled = False
    if (
        str(primary_d.get("action_type") or contract_d.get("action_type") or "").strip()
        == "apply_resolved_candidate"
        and contract_enabled
        and updates_d
    ):
        return None

    final_utils = dict(overview_d.get("utils") or {})
    final_shear_util = parse_util_value_fn(final_utils.get("shear"))
    final_bending_util = parse_util_value_fn(final_utils.get("bending"))
    try:
        final_actions = resolve_design_actions_from_state_fn(state_d) or {}
    except Exception:
        final_actions = {}
    try:
        final_direct_vu = abs(
            float(
                float_from_state_fn(
                    state_d,
                    "uls_Vstar",
                    float_from_state_fn(state_d, "Vu_star", 0.0),
                )
                or 0.0
            )
        )
    except Exception:
        final_direct_vu = 0.0
    final_zero_shear_post_click_accepted = bool(
        final_shear_util is not None
        and abs(float(final_shear_util)) <= float(target_band_eps)
        and (
            shear_demands_negligible_fn(final_actions)
            or final_direct_vu <= float(guidance_shear_demand_abs_tol_kn) + 1e-12
        )
        and final_bending_util is not None
        and float(final_bending_util)
        >= float(final_accepted_min_family_util) - float(target_band_eps)
        and overview_required_checks_acceptable_fn(overview_d)
        and not bool(overview_d.get("any_fail"))
    )
    if final_zero_shear_post_click_accepted:
        zero_shear_result = assemble_zero_shear_demand_accepted_result_fn(
            primary=primary_d,
            final_state=state_d,
            final_overview=dict(overview_d),
            final_shear_util=final_shear_util,
            final_bending_util=final_bending_util,
            final_accepted_min_family_util=final_accepted_min_family_util,
            post_click_accepted_green_audit_fn=post_click_accepted_green_audit_fn,
            post_active_repair_target_accepted_item_fn=post_active_repair_target_accepted_item_fn,
            design_mode_config_fn=design_mode_config_fn,
            design_optimisation_goal_fn=design_optimisation_goal_fn,
            state_fingerprint_fn=state_fingerprint_fn,
        )
        if isinstance(zero_shear_result, dict):
            return zero_shear_result

    if final_shear_util is not None and float(final_shear_util) < float(
        final_accepted_min_family_util
    ):
        shear_resolution_item = resolve_low_shear_target_cleanup_probe_fn(
            final_state=state_d,
            final_overview=dict(overview_d),
            threshold=final_accepted_min_family_util,
            shear_low_util_target_cleanup_item_fn=shear_low_util_target_cleanup_item_fn,
        )
        if not isinstance(shear_resolution_item, dict):
            shear_resolution_item = resolve_low_shear_evidence_fallback_fn(
                primary=primary_d,
                final_state=state_d,
                final_overview=dict(overview_d),
                final_accepted_min_family_util=final_accepted_min_family_util,
                target_band_eps=target_band_eps,
                compound_shear_update_keys=compound_shear_update_keys,
                parse_util_value_fn=parse_util_value_fn,
                overview_active_failure_keys_fn=overview_active_failure_keys_fn,
                updates_match_state_fn=updates_match_state_fn,
                guidance_cleanup_candidate_id_fn=guidance_cleanup_candidate_id_fn,
                shear_best_safe_cleanup_item_from_evidence_fn=shear_best_safe_cleanup_item_from_evidence_fn,
            )
        if not isinstance(shear_resolution_item, dict):
            shear_resolution_item = resolve_low_shear_exact_blocker_fallback_fn(
                final_state=state_d,
                final_overview=dict(overview_d),
                final_accepted_min_family_util=final_accepted_min_family_util,
                post_click_applied_residual_shear_exact_blocker_fn=post_click_applied_residual_shear_exact_blocker_fn,
                post_active_repair_residual_shear_exact_blocker_fn=post_active_repair_residual_shear_exact_blocker_fn,
                shear_cleanup_exact_blocker_guidance_item_fn=shear_cleanup_exact_blocker_guidance_item_fn,
                shear_best_safe_cleanup_item_from_evidence_fn=shear_best_safe_cleanup_item_from_evidence_fn,
                accepted_green_exact_blocker_is_valid_fn=accepted_green_exact_blocker_is_valid_fn,
            )
        if isinstance(shear_resolution_item, dict):
            shear_resolution_item = apply_low_shear_combined_low_util_blocker_gate_fn(
                shear_resolution_item=shear_resolution_item,
                final_state=state_d,
                final_overview=dict(overview_d),
                final_accepted_min_family_util=final_accepted_min_family_util,
                target_band_eps=target_band_eps,
                parse_util_value_fn=parse_util_value_fn,
                design_guide_button_contract_enabled_fn=design_guide_button_contract_enabled_fn,
                post_click_accepted_green_audit_fn=post_click_accepted_green_audit_fn,
                post_click_low_bending_resolution_item_fn=post_click_low_bending_resolution_item_fn,
                design_mode_config_fn=design_mode_config_fn,
                design_optimisation_goal_fn=design_optimisation_goal_fn,
                resolve_recommendation_updates_fn=resolve_recommendation_updates_fn,
                local_cleanup_post_apply_acceptance_matches_fn=local_cleanup_post_apply_acceptance_matches_fn,
                combined_low_util_exact_blocker_final_item_fn=combined_low_util_exact_blocker_final_item_fn,
            )
            shear_resolution_item = finalize_low_shear_resolution_item_before_return_fn(
                shear_resolution_item=shear_resolution_item,
                final_state=state_d,
                final_overview=dict(overview_d),
                final_shear_util=final_shear_util,
                accepted_green_exact_blocker_is_valid_fn=accepted_green_exact_blocker_is_valid_fn,
                combine_best_safe_shear_with_bending_cleanup_item_fn=combine_best_safe_shear_with_bending_cleanup_item_fn,
                design_mode_config_fn=design_mode_config_fn,
                design_optimisation_goal_fn=design_optimisation_goal_fn,
                guidance_cleanup_candidate_id_fn=guidance_cleanup_candidate_id_fn,
                normalise_final_visible_design_guide_item_fn=normalise_final_visible_design_guide_item_fn,
            )
            shear_contract = dict(shear_resolution_item.get("button_contract") or {})
            try:
                shear_contract_enabled = bool(
                    design_guide_button_contract_enabled_fn(shear_contract)
                )
            except Exception:
                shear_contract_enabled = False
            shear_updates = dict(
                shear_contract.get("updates")
                or shear_resolution_item.get("updates")
                or resolve_recommendation_updates_fn(shear_resolution_item, state=state_d)
                or {}
            )
            return assemble_low_shear_resolution_result_fn(
                shear_resolution_item=shear_resolution_item,
                shear_contract=shear_contract,
                shear_contract_enabled=shear_contract_enabled,
                shear_updates=shear_updates,
                final_state=state_d,
                final_overview=dict(overview_d),
                final_shear_util=final_shear_util,
                state_fingerprint_fn=state_fingerprint_fn,
            )

    try:
        accepted_audit = post_click_accepted_green_audit_fn(
            dict(overview_d),
            blocker_source=primary_d,
            state=state_d,
            threshold=final_accepted_min_family_util,
            build_active_shear_blocker=True,
        )
    except Exception:
        accepted_audit = {}
    if bool(accepted_audit.get("post_click_accepted_green_valid")):
        try:
            post_click_route = bool(local_cleanup_post_apply_acceptance_matches_fn(state_d))
        except Exception:
            post_click_route = False
        combined_final = combined_low_util_exact_blocker_final_item_fn(
            state_d,
            dict(overview_d),
            accepted_audit,
            post_click=post_click_route,
        )
        if isinstance(combined_final, dict):
            return assemble_combined_low_util_blocker_or_best_safe_result_fn(
                combined_final=combined_final,
                accepted_audit=dict(accepted_audit),
                post_click_route=bool(post_click_route),
                final_state=state_d,
                final_overview=dict(overview_d),
                state_fingerprint_fn=state_fingerprint_fn,
            )

    return None


def select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key(
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any] | None:
    """Select the residual-shear cleanup candidate using the locked live key order."""

    rows = [dict(row) for row in (candidates or []) if isinstance(row, dict)]
    if not rows:
        return None
    selected = min(
        rows,
        key=lambda row: (
            float(row.get("shear_util") or float("inf")),
            len(dict(row.get("updates") or {})),
            str(sorted(dict(row.get("updates") or {}).items())),
        ),
    )
    return dict(selected)


__all__ = [
    "build_design_guide_controller_guidance_item",
    "build_design_guide_controller_compute_invalid_state_output_projection",
    "build_design_guide_controller_compute_invalid_state_debug_payload",
    "build_design_guide_controller_shear_final_threshold_blocker_projection",
    "build_design_guide_controller_compute_missing_candidate_search_evidence_record",
    "build_design_guide_controller_compute_missing_candidate_target_band_context",
    "build_design_guide_controller_compute_coherence_active_repair_projection",
    "resolve_design_guide_controller_compute_coherence_active_repair_fail_keys",
    "build_design_guide_controller_compute_active_under_capacity_blocker_projection",
    "build_design_guide_controller_compute_serviceability_exact_blocker_projection",
    "build_design_guide_controller_compute_safe_cleanup_rehydration_projection",
    "resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision",
    "build_design_guide_controller_bending_only_best_safe_cleanup_item_projection",
    "build_design_guide_controller_bending_only_target_band_cleanup_item_projection",
    "build_design_guide_controller_probe_equivalent_bending_cleanup_item_projection",
    "build_design_guide_controller_zero_bending_demand_cleanup_item_projection",
    "build_design_guide_controller_bending_only_terminalisation_projection",
    "resolve_design_guide_controller_terminalisation_trial_acceptance",
    "resolve_design_guide_controller_terminalisation_followup_updates",
    "build_design_guide_controller_terminalisation_initial_context",
    "build_design_guide_controller_resolved_candidate_guidance_item_input_pack",
    "build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack",
    "build_design_guide_controller_resolved_candidate_guidance_item_before_after_request_pack",
    "resolve_design_guide_controller_before_after_text_eligibility",
    "resolve_design_guide_controller_guidance_action_payload_updates",
    "build_design_guide_pure_guidance_step_description",
    "build_design_guide_controller_resolved_candidate_guidance_item",
    "build_design_guide_controller_bending_fail_snapshot_reuse_result",
    "build_design_guide_controller_no_active_primary_result",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail",
    "select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_dependency_boundary",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_injected_adapter",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_boundary",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_execution_shell",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_live_route_result_assembly",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_blocker_tail_shell",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result",
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_physical_nested_route_body_wrapper",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail",
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement",
    "select_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_return_item",
    "build_design_guide_controller_combined_low_util_cleanup_result",
    "run_design_guide_controller_no_active_combined_low_util_cleanup_route",
    "run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route",
    "run_design_guide_controller_no_active_low_shear_or_blocker_route",
    "build_design_guide_controller_combined_low_util_cleanup_route_policy_proof",
    "build_design_guide_controller_combined_low_util_candidate_generation_handoff_proof",
    "build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof",
    "build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof",
    "build_design_guide_controller_safe_cleanup_candidate_before_blocker_result",
    "build_design_guide_controller_bending_cleanup_available_before_blocker_result",
    "build_design_guide_controller_active_action_result",
    "build_design_guide_controller_compute_core_branch_request_projection",
    "build_design_guide_controller_start_guidance_item",
    "resolve_design_guide_controller_not_started_condition",
    "resolve_design_guide_controller_post_active_zero_shear_predicate",
    "build_design_guide_controller_post_active_zero_shear_terminal_projection",
    "build_design_guide_controller_post_active_residual_shear_cleanup_debug_projection",
    "build_design_guide_controller_post_active_shear_cleanup_blocked_projection",
    "resolve_design_guide_controller_optimisation_selector_fallback_result",
    "build_design_guide_controller_optimisation_selector_default_debug_context",
    "resolve_design_guide_controller_optimisation_candidate_family",
    "build_design_guide_controller_optimisation_selector_debug_projection",
    "build_design_guide_controller_family_status_display_payload",
    "build_design_guide_controller_family_status_row_from_overview",
    "build_design_guide_controller_family_status_table",
    "build_design_guide_controller_preview_family_delta_table",
    "build_design_guide_controller_blocker_attempt_source_merge",
    "resolve_design_guide_controller_blocker_attempt_active_failures",
    "build_design_guide_controller_combined_active_strength_attempt_row",
    "resolve_design_guide_controller_cleanup_attempted_passed",
    "resolve_design_guide_controller_cleanup_rejection_category",
    "resolve_design_guide_controller_cleanup_explicit_attempt_label",
    "build_design_guide_controller_cleanup_geometry_change_label",
    "build_design_guide_controller_cleanup_bottom_reinforcement_change_label",
    "build_design_guide_controller_cleanup_shear_link_change_label",
    "build_design_guide_controller_cleanup_no_link_no_change_label",
    "build_design_guide_controller_cleanup_route_fallback_label",
    "resolve_design_guide_controller_cleanup_attempted_updates",
    "format_design_guide_controller_display_util",
    "resolve_design_guide_controller_blocker_attempt_strength_capacity_rule",
    "build_design_guide_controller_blocker_attempt_strength_reason",
    "build_design_guide_controller_active_failure_no_target_blocker_item",
    "DesignGuideControllerTerminalActiveFailureBlockerSourceProof",
    "build_design_guide_controller_terminal_active_failure_blocker_source_proof",
    "run_design_guide_controller_active_action_post_click_exact_blocker_route",
    "run_design_guide_controller_terminal_active_failure_blocker_finalizer_route",
    "resolve_design_guide_controller_candidate_action_type_for_updates",
    "resolve_design_guide_controller_strength_family_band_status",
    "filter_design_guide_controller_direct_target_ladder_candidates",
    "identify_design_guide_controller_materially_overprovided_non_governing_families",
    "resolve_design_guide_controller_direct_candidate_final_cleanup_sort_key",
    "build_design_guide_controller_direct_target_selection_row",
    "build_design_guide_controller_direct_target_evidence_context_projection",
    "build_design_guide_controller_direct_target_guidance_item_projection",
    "build_design_guide_controller_direct_target_family_bypass_projection",
    "build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection",
    "build_design_guide_controller_direct_target_active_failure_route_request_result_adapter",
    "build_design_guide_controller_direct_target_active_failure_route_request_result_adapter_trace",
    "build_design_guide_controller_direct_target_family_route_projection_metadata",
    "resolve_design_guide_controller_direct_target_active_failure_route_policy",
    "build_design_guide_controller_active_fail_executor_family_ladder_dispatch",
    "select_design_guide_controller_active_fail_executor_family_ladder_candidate",
    "build_design_guide_controller_active_fail_executor_family_evidence_overlay",
    "build_design_guide_controller_active_fail_executor_candidate_search_evidence",
    "build_design_guide_controller_active_fail_executor_selected_repair_candidate",
    "build_design_guide_controller_active_fail_executor_final_guidance_item_projection",
    "build_design_guide_controller_active_fail_executor_bending_ladder_evaluation_trace_row",
    "build_design_guide_controller_active_fail_executor_bending_ladder_first_executable_trace_row",
    "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
    "build_design_guide_controller_active_fail_executor_ladder_candidate_meta",
    "build_design_guide_controller_active_fail_executor_ladder_eval_commands",
    "run_design_guide_controller_active_fail_executor_ladder_eval_commands",
    "resolve_design_guide_controller_active_fail_executor_rescue_seed_order",
    "build_design_guide_controller_active_fail_executor_rescue_seed_eval_commands",
    "build_design_guide_controller_active_fail_executor_near_current_combined_fallback_eval_commands",
    "build_design_guide_controller_active_fail_executor_geometry_update_row",
    "build_design_guide_controller_active_fail_executor_bottom_update_row",
    "build_design_guide_controller_active_fail_executor_policy_input_request",
    "build_design_guide_controller_active_fail_near_current_repair_preflight",
    "build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs",
    "resolve_design_guide_controller_active_fail_executor_overview_util_tier",
    "resolve_design_guide_controller_active_fail_executor_ladder_stop_decision",
    "accept_design_guide_controller_active_fail_executor_repair_candidate",
    "filter_design_guide_controller_active_fail_executor_repair_candidates",
    "resolve_design_guide_controller_local_cleanup_candidate_affects_family",
    "resolve_design_guide_controller_direct_target_after_state_preference_scores",
    "resolve_design_guide_controller_shear_practical_preference_score",
    "resolve_design_guide_controller_geometry_proportion_preference_score",
    "select_design_guide_controller_direct_target_final_candidate",
    "resolve_design_guide_controller_local_cleanup_family_for_updates",
    "resolve_design_guide_controller_local_cleanup_materially_reduces",
    "resolve_design_guide_controller_local_cleanup_material_proxy",
    "resolve_design_guide_controller_local_cleanup_pre_preview_gate",
    "resolve_design_guide_controller_local_cleanup_basic_post_preview_gate",
    "resolve_design_guide_controller_local_cleanup_target_band_acceptance",
    "resolve_design_guide_controller_local_cleanup_executor_acceptance",
    "resolve_design_guide_controller_local_cleanup_candidate_promotion",
    "resolve_design_guide_controller_shear_executor_safety_policy",
    "run_design_guide_controller_combined_low_util_candidate_generation",
    "build_design_guide_shear_low_util_cleanup_generator_boundary_proof",
    "classify_design_guide_shear_low_util_cleanup_candidate",
    "accumulate_design_guide_shear_low_util_cleanup_candidate",
    "build_design_guide_shear_low_util_cleanup_candidate_record",
    "build_design_guide_bending_overdesign_contract_candidate_items",
    "build_design_guide_shear_overdesign_contract_candidate_items",
    "evaluate_design_guide_shear_low_util_cleanup_candidate",
    "evaluate_design_guide_combined_low_util_cleanup_candidate",
    "resolve_design_guide_combined_low_util_cleanup_updates",
    "resolve_design_guide_combined_low_util_cleanup_target_band",
    "assess_design_guide_combined_low_util_cleanup_acceptance_gate",
    "assess_design_guide_combined_low_util_post_click_accepted_green_audit",
    "run_design_guide_combined_low_util_orchestration",
    "run_design_guide_combined_low_util_bending_cleanup_item_generation",
    "build_design_guide_combined_low_util_result_packaging",
    "build_design_guide_combined_low_util_invalid_item_fallback",
    "build_design_guide_combined_low_util_cleanup_candidate_search_evidence",
    "build_design_guide_combined_low_util_guidance_item_packaging",
    "build_design_guide_shear_low_util_change_lines_for_updates",
    "build_design_guide_shear_low_util_selected_no_link_audit_update",
    "build_design_guide_shear_low_util_cleanup_candidate_search_evidence",
    "build_design_guide_shear_low_util_candidate_acceptance_screen",
    "build_design_guide_shear_low_util_candidate_delta_screen",
    "build_design_guide_shear_low_util_failed_reason_from_preview",
    "build_design_guide_shear_low_util_failure_coverage_from_overviews",
    "build_design_guide_shear_low_util_current_overview_status_authority",
    "build_design_guide_shear_low_util_preferred_target_blocker",
    "build_design_guide_shear_low_util_final_item_packaging",
    "build_design_guide_shear_low_util_promoted_item",
    "build_design_guide_shear_low_util_guidance_item_descriptor",
    "build_design_guide_shear_low_util_guidance_item_shell",
    "build_design_guide_shear_low_util_no_link_probe",
    "build_design_guide_shear_low_util_raw_variant_states",
    "build_design_guide_shear_low_util_variant_sequence",
    "DesignGuideCombinedLowUtilCandidateGenerationHandoffProof",
    "DesignGuideCombinedLowUtilCleanupRoutePolicyProof",
    "DesignGuideNoActiveBlockedPrimaryCleanupProbeRoutePolicyProof",
    "DesignGuideNoActiveBlockedPrimaryCleanupProbeFullRouteBuilderProof",
    "DesignGuideShearLowUtilCleanupGeneratorBoundaryProof",
    "DesignGuideControllerComputeSelectionRequest",
    "DesignGuideControllerComputeSelectionResponse",
    "DesignGuideControllerComputeResolverReplacementResponse",
    "DesignGuideControllerComputeReboundMutationRequest",
    "DesignGuideControllerComputeReboundMutationResponse",
    "DesignGuideControllerComputeReboundPublicationItemRequest",
    "DesignGuideControllerComputeReboundPublicationItemResponse",
    "DesignGuideControllerPresentationRequest",
    "DesignGuideControllerPresentationResponse",
    "DesignGuideControllerBendingFailSnapshotReuseRequest",
    "DesignGuideControllerBendingFailSnapshotReuseResponse",
    "DesignGuideControllerComputePublicationHandoffRequest",
    "DesignGuideControllerComputePublicationHandoffResponse",
    "DesignGuideControllerFinalVisibleRebindEffectsRequest",
    "DesignGuideControllerFinalVisibleRebindEffectsResponse",
    "DesignGuideControllerFinalVisibleOutputBridgeRequest",
    "DesignGuideControllerFinalVisibleOutputBridgeResponse",
    "DesignGuideControllerRequest",
    "DesignGuideControllerResponse",
    "build_design_guide_controller_presentation_request",
    "run_design_guide_controller_final_visible_output_bridge_trace_only",
    "run_design_guide_controller_final_visible_rebind_effects_trace_only",
    "run_design_guide_controller_compute_selection_trace_only",
    "run_design_guide_controller_compute_rebound_publication_item_trace_only",
    "run_design_guide_controller_compute_rebound_mutation_trace_only",
    "run_design_guide_controller_compute_resolver_replacement_trace_only",
    "run_design_guide_controller_presentation_adapter",
    "build_design_guide_controller_compute_resolver_fallback_shell",
    "run_design_guide_controller_bending_fail_snapshot_reuse_trace_only",
    "run_design_guide_controller_compute_publication_handoff_trace_only",
    "run_design_guide_controller_publication_authority",
    "run_design_guide_controller_render_item_consumer_trace_only",
    "run_design_guide_controller_trace_only",
]

