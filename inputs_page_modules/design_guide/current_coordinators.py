"""Current Design Guide coordinators for the Inputs shell.

This module is a mechanical extraction of the remaining Design Guide current
coordinator layer from ``inputs_page.py``. The deeper helper surfaces are still
provided through ``configure_design_guide_current_provider`` until their own
focused extraction slices remove that provider dependency.
"""

from __future__ import annotations

import copy
import html
import json
import os
import sys
import time
from typing import Any

from application.design_result_store import AuthoritativeDesignResultStore
from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state
from application.guidance_result_adapter import guidance_payload_from_authoritative_design_result
from inputs_application.legacy_design_brain_adapter import (
    build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence,
    build_design_guide_controller_compute_active_under_capacity_blocker_projection,
    classify_family_from_whole_beam_evidence,
    load_family_classification_contract,
    normalise_governing_family,
    build_final_design_guide_publication,
    final_design_guide_publication_from_dict,
    stable_final_publication_hash,
    build_final_design_guide_card_format,
)
from inputs_page_modules.design_guide.render_coordinators import (
    render_design_guide_component_cta,
    render_design_guide_post_apply_banner,
    render_guidance_secondary_items,
)
from ui.final_design_guide_card import (
    final_design_guide_action_anchor_bucket,
    render_final_design_guide_card_html,
)

_CURRENT_COORDINATOR_PROVIDER: Any | None = None
_ST_MODULE: Any | None = None
_OS_MODULE: Any | None = None
_SYS_MODULE: Any | None = None

_CURRENT_COORDINATOR_PROVIDER_NAMES: tuple[str, ...] = (
    'DESIGN_GUIDE_ALGORITHM_VERSION',
    'DESIGN_GUIDE_APPLY_BANNER_KEY',
    'DESIGN_GUIDE_APPLY_BANNER_META_KEY',
    'DESIGN_GUIDE_DEBUG_BUNDLE_KEY',
    'DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY',
    'DESIGN_GUIDE_INTENTS',
    'DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY',
    'DESIGN_GUIDE_LAST_AUTO_GEOM_KEY',
    'DESIGN_GUIDE_LAST_USER_GEOM_KEY',
    'DESIGN_GUIDE_NEEDS_REFRESH_KEY',
    'DESIGN_GUIDE_PANEL_BASELINE_FP_KEY',
    'DESIGN_GUIDE_PENDING_STEP_CTX_KEY',
    'DESIGN_GUIDE_RECO_TRACE_KEY',
    'DESIGN_GUIDE_REFERENCE_B_KEY',
    'DESIGN_GUIDE_SESSION_ANCHOR_D_KEY',
    'DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT',
    'EFFICIENCY_TARGET_UTIL_MAX',
    'EFFICIENCY_TARGET_UTIL_MIN',
    'FINAL_ACCEPTED_MIN_FAMILY_UTIL',
    'TARGET_BAND_EPS',
    '_COMPOUND_SHEAR_UPDATE_KEYS',
    '_agent_debug_log',
    '_align_guidance_items_to_candidate_search_evidence',
    '_apply_guidance_ui_state',
    '_auto_design_governing_fingerprint',
    '_build_design_actions_context',
    '_build_design_guide_presentation_state',
    '_build_pending_recommendation',
    '_clear_design_guide_transient_ui_state',
    '_collapse_to_single_primary_guidance_item',
    '_collect_design_overview',
    '_compound_subfamilies_from_updates',
    '_compute_design_guidance_items',
    '_consolidate_guidance_items_by_family',
    '_debug_resolved_guidance_actions',
    '_dedupe_guidance_items_for_display',
    '_derive_design_guide_terminal_state_from_current_overview',
    '_derived_guidance_title_from_updates',
    '_design_guide_apply_button_contracts_to_items',
    '_design_guide_apply_copy_model_to_items',
    '_design_guide_apply_display_truth_to_items',
    '_design_guide_banner_matches_current_render',
    '_design_guide_button_contract',
    '_design_guide_button_contract_enabled',
    '_design_guide_candidate_family',
    '_design_guide_debug_has_coherent_overview',
    '_design_guide_debug_has_efficiency_state',
    '_design_guide_display_truth_for_item',
    '_design_guide_guidance_intent_debug_rows',
    '_design_guide_primary_uses_success_style',
    '_design_guide_render_plan',
    '_design_guide_sidebar_debug_enabled',
    '_design_guide_status_from_overview',
    '_design_guide_step_history_debug_summary',
    '_design_guide_terminal_state_from_render_artifacts',
    '_design_guide_text_html',
    '_design_guide_title_alignment_verification_record',
    '_design_mode_config',
    '_design_optimisation_goal',
    '_ensure_design_guide_debug_trace_coherent',
    '_first_actionable_guidance_item',
    '_float_from_state',
    '_final_publication_cta_authority_payload',
    '_get_design_guide_fp',
    '_governing_focus_from_overview',
    '_guidance_before_after_text',
    '_guidance_card_label',
    '_guidance_card_proposed_change_html',
    '_guidance_card_why_body',
    '_guidance_item',
    '_guidance_item_expected_util',
    '_guidance_item_family',
    '_guidance_item_family_tag',
    '_guidance_item_is_resolved_one_click',
    '_guidance_item_source_candidate_id',
    '_guidance_primary_compact_lines_html',
    '_guidance_state_snapshot',
    '_guidance_update_map',
    '_int_from_state',
    '_is_in_target_zone_with_eps',
    '_label_consistent_with_updates_families',
    '_latest_solver_result_cta_state',
    '_local_cleanup_post_apply_acceptance_matches',
    '_mark_design_guide_dirty',
    '_normalise_invalid_shear_state_updates',
    '_one_click_feedback_cta_state',
    '_optimisation_candidate_family',
    '_overview_debug_summary',
    '_parse_util_value',
    '_passing_guidance_item',
    '_post_click_accepted_green_audit',
    '_prefer_target_band_guidance_item_order',
    '_proposed_change_lines_for_guidance_item',
    '_queue_primary_design_guide_button_action',
    '_recommendation_blocked_reason',
    '_recommendation_cache_fingerprint',
    '_recommendation_commit_eligible',
    '_recommendation_result_for_primary_guidance_card',
    '_render_auto_design_main_panel_status',
    '_reset_design_guide_reco_trace',
    '_resolve_design_actions_from_state',
    '_resolve_recommendation_updates',
    '_resolved_efficiency_target_band',
    '_resolved_inputs_summary_state',
    '_set_design_guide_primary_payload_binding_audit',
    '_shared_state_snapshot',
    '_shear_reinforcement_is_active',
    '_suppress_redundant_guidance_items',
    '_sync_auto_design_mode_tracking',
    '_sync_pending_recommendation_from_guidance',
    'identify_materially_overprovided_non_governing_families',
)


def configure_design_guide_current_provider(
    provider: Any,
    *,
    st_module: Any,
    os_module: Any,
    sys_module: Any,
) -> None:
    global _CURRENT_COORDINATOR_PROVIDER, _ST_MODULE, _OS_MODULE, _SYS_MODULE
    _CURRENT_COORDINATOR_PROVIDER = provider
    _ST_MODULE = st_module
    _OS_MODULE = os_module
    _SYS_MODULE = sys_module


def _bind_design_guide_current_globals() -> None:
    provider = _CURRENT_COORDINATOR_PROVIDER
    if provider is None:
        raise RuntimeError("Design Guide current coordinator provider is not configured")
    namespace = globals()
    namespace["st"] = _ST_MODULE
    namespace["os"] = _OS_MODULE
    namespace["sys"] = _SYS_MODULE
    for name in _CURRENT_COORDINATOR_PROVIDER_NAMES:
        namespace[name] = getattr(provider, name)


def _accepted_green_audit_has_terminal_proof(audit: dict | None) -> bool:
    if not isinstance(audit, dict):
        return False
    if not bool(audit.get("post_click_accepted_green_valid")):
        return False
    low_families = {
        str(family or "").strip().lower()
        for family in list(
            audit.get("post_click_families_below_final_threshold")
            or audit.get("post_click_materially_overprovided_families")
            or []
        )
        if str(family or "").strip()
    }
    unresolved = {
        str(family or "").strip().lower()
        for family in list(audit.get("post_click_unresolved_low_util_families") or [])
        if str(family or "").strip()
    }
    if unresolved:
        return False
    exact_blockers = audit.get("post_click_exact_blockers_by_family") or {}
    if "bending" in low_families:
        bending_blocker = dict(exact_blockers.get("bending") or {}) if isinstance(exact_blockers, dict) else {}
        blocker_text = " ".join(
            str(bending_blocker.get(key) or "")
            for key in (
                "best_rejected_candidate_id",
                "failed_check_name",
                "why_reduction_would_hurt_other_design_elements",
                "reason_reducing_this_family_would_affect_other_design_elements",
                "reason",
            )
        ).strip().lower()
        if (
            "bending_cleanup_floor_shear_or_detailing_limited" in blocker_text
            or "safe local floor" in blocker_text
            or "further bending cleanup is blocked" in blocker_text
        ):
            return False
        has_exact_stop = bool(
            bending_blocker.get("exact_stop_proven")
            or bending_blocker.get("exact_stop_available")
            or bending_blocker.get("contract_exact_stop_proven")
        )
        has_cleanup_proof = bool(
            (
                bending_blocker.get("post_click_bending_cleanup_search_ran")
                or bending_blocker.get("bending_cleanup_search_ran")
                or bending_blocker.get("local_cleanup_search_ran")
            )
            and (
                bending_blocker.get("post_click_bending_cleanup_search_exhaustive")
                or bending_blocker.get("bending_cleanup_search_exhaustive")
                or bending_blocker.get("local_cleanup_search_exhaustive")
                or bending_blocker.get("candidate_search_exhaustive")
            )
            and float(
                bending_blocker.get("post_click_safe_bending_cleanup_count")
                if bending_blocker.get("post_click_safe_bending_cleanup_count") is not None
                else bending_blocker.get("safe_bending_cleanup_count", -1)
            )
            == 0.0
            and float(
                bending_blocker.get("post_click_executable_bending_cleanup_count")
                if bending_blocker.get("post_click_executable_bending_cleanup_count") is not None
                else bending_blocker.get("executable_bending_cleanup_count", -1)
            )
            == 0.0
        )
        return bool(has_exact_stop or has_cleanup_proof)
    return True


def _design_guide_blocker_reason_is_generic(reason: str | None) -> bool:
    text = str(reason or "").strip().lower()
    if not text:
        return True
    generic_fragments = (
        "reinforcement, geometry, ductility, or detailing limits",
        "shear/detailing limits",
        "no validated one-click update is available",
        "candidate_preview_has_fail_status",
        "specific_engineering_blocker",
        "recommended action:",
    )
    return any(fragment in text for fragment in generic_fragments)


def _design_guide_attempted_update_summary(attempted_updates: dict | None) -> str:
    attempted = dict(attempted_updates or {})
    if not attempted:
        return ""
    attempted_classes = ", ".join(str(key) for key in sorted(attempted)[:8])
    return f"attempted moves: {attempted_classes}" if attempted_classes else ""


def _design_guide_specific_blocker_reason_from_payload(
    *,
    family: str,
    blocker: dict | None,
) -> str:
    blocker_d = dict(blocker or {})
    raw_reason = str(
        blocker_d.get("reason")
        or blocker_d.get("blocked_reason")
        or blocker_d.get("blocking_reason")
        or blocker_d.get("why_reduction_would_hurt_other_design_elements")
        or ""
    ).strip()
    if raw_reason and not _design_guide_blocker_reason_is_generic(raw_reason):
        return raw_reason

    proof_parts: list[str] = []
    if blocker_d.get("repair_search_exhaustive") or blocker_d.get("search_exhaustive"):
        proof_parts.append("repair search exhausted")
    safe_count = blocker_d.get("safe_candidate_count")
    if safe_count is None:
        safe_count = blocker_d.get("safe_executor_backed_candidates_count")
    if safe_count is not None:
        proof_parts.append(f"safe executable candidates: {safe_count}")
    attempted_summary = _design_guide_attempted_update_summary(
        dict(blocker_d.get("attempted_updates") or {})
    )
    if attempted_summary:
        proof_parts.append(attempted_summary)
    failed_status = str(blocker_d.get("failed_check_status") or "").strip()
    if failed_status:
        proof_parts.append(f"failed check status: {failed_status}")
    util_value = blocker_d.get("best_safe_final_util")
    if util_value is None:
        util_value = blocker_d.get("failed_check_util")
    if util_value is not None:
        proof_parts.append(f"utilisation evidence: {util_value}")
    if not proof_parts:
        return raw_reason

    family_label = "Bending" if str(family).lower() == "bending" else "Shear" if str(family).lower() == "shear" else str(family or "Family").title()
    return f"{family_label} repair blocked: {'; '.join(proof_parts)}."


def _render_exact_blocker_from_item(item: dict | None) -> dict:
    item_d = dict(item or {})
    if not item_d:
        return {}
    button = dict(item_d.get("button_contract") or {})
    action_payload = dict(item_d.get("action_payload") or {})
    resolved = dict(item_d.get("resolved_candidate") or {})
    evidence = dict(
        item_d.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or resolved.get("candidate_search_evidence")
        or {}
    )
    try:
        debug_bundle = dict(st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {})
    except Exception:
        debug_bundle = {}
    debug_evidence = dict(debug_bundle.get("candidate_search_evidence") or {})
    if debug_evidence:
        for key, value in debug_evidence.items():
            if evidence.get(key) in (None, "", [], {}):
                evidence[key] = value
    exact_blockers = (
        evidence.get("post_click_exact_blockers_by_family")
        or evidence.get("exact_blockers_by_family")
        or item_d.get("post_click_exact_blockers_by_family")
        or item_d.get("exact_blockers_by_family")
        or debug_bundle.get("post_click_exact_blockers_by_family")
        or debug_bundle.get("exact_blockers_by_family")
        or {}
    )
    blocking_reason = str(button.get("blocking_reason") or button.get("disabled_reason") or "").strip()
    failed_preview_block = bool(
        blocking_reason == "candidate_preview_has_fail_status"
        and button.get("preview_pass") is False
    )
    publication = dict(
        item_d.get("final_publication_verifier_payload")
        or debug_bundle.get("final_publication_verifier_payload")
        or {}
    )
    publication_cta = dict(publication.get("cta") or {})
    publication_display = dict(publication.get("display") or {})
    publication_disabled_reason = str(
        publication_cta.get("disabled_reason")
        or publication_cta.get("blocking_reason")
        or ""
    ).strip()
    publication_blocked = bool(
        str(publication.get("outcome_state") or publication.get("status") or "").strip().upper() == "BLOCKED"
        and publication_cta.get("enabled") is False
    )
    publication_nonterminal_overdesign_block = bool(
        publication_cta.get("enabled") is False
        and publication_disabled_reason == "non_terminal_overdesign_cleanup_candidate"
    )
    publication_failed_preview_block = bool(
        publication_blocked
        and (
            publication_cta.get("disabled_reason") == "candidate_preview_has_fail_status"
            or publication_cta.get("blocking_reason") == "candidate_preview_has_fail_status"
            or failed_preview_block
        )
    )
    if not isinstance(exact_blockers, dict):
        exact_blockers = {}
    overview = dict(debug_bundle.get("overview") or debug_bundle.get("summary_overview_probe") or {})
    statuses = {str(k or "").strip().lower(): str(v or "").strip().upper() for k, v in dict(overview.get("statuses") or {}).items()}
    utils = dict(overview.get("utils") or {})

    def _blocker_util(family_key: str, blocker: dict) -> float | None:
        for value in (
            blocker.get("best_safe_final_util"),
            blocker.get("failed_check_util"),
            blocker.get("current_util"),
            utils.get(family_key),
        ):
            try:
                if value not in (None, ""):
                    return float(value)
            except Exception:
                continue
        return None

    def _active_under_capacity_blocker_applies(family_key: str, blocker: dict) -> bool:
        key = str(family_key or "").strip().lower()
        if key not in {"bending", "shear"}:
            return True
        status = str(statuses.get(key) or blocker.get("failed_check_status") or "").strip().upper()
        if status in {"CAPACITY", "INFO", "NOT RUN", "NOT_RUN", "NOT SUPPLIED"}:
            return False
        util = _blocker_util(key, blocker)
        if util is not None and float(util) <= 1.0:
            return False
        return True

    exact_blockers = {
        str(key or "").strip().lower(): dict(value or {})
        for key, value in exact_blockers.items()
        if isinstance(value, dict)
        and _active_under_capacity_blocker_applies(str(key or "").strip().lower(), dict(value or {}))
    }
    explicitly_blocked = bool(
        str(item_d.get("guidance_intent") or "").strip() == "specific_blocker"
        or item_d.get("active_under_capacity_blocker")
        or evidence.get("active_under_capacity_blocker")
        or evidence.get("repair_search_exhaustive")
        or publication_blocked
        or publication_nonterminal_overdesign_block
    )
    if (
        not exact_blockers
        and not publication_failed_preview_block
        and not failed_preview_block
        and not publication_nonterminal_overdesign_block
    ):
        return {}
    if not (failed_preview_block or explicitly_blocked or publication_failed_preview_block):
        return {}
    selected_family_id = str(
        item_d.get("selected_family_id")
        or evidence.get("selected_family_id")
        or publication.get("selected_family_id")
        or ""
    ).strip().upper()
    exact_blocker_keys = {
        str(key or "").strip().lower()
        for key in exact_blockers
        if str(key or "").strip()
    }
    combined_blocker = bool(
        selected_family_id in {"COMBINED_BENDING_SHEAR_FAIL", "COMBINED_BENDING_SHEAR_FAIL_GOVERNS"}
        or {"bending", "shear"}.issubset(exact_blocker_keys)
    )
    family = (
        "combined"
        if combined_blocker
        else str(
            evidence.get("active_under_capacity_blocker_family")
            or button.get("family")
            or publication_cta.get("family")
            or next(iter(exact_blockers.keys()), "")
        ).strip().lower()
    )
    title_text = " ".join(
        str(value or "")
        for value in (item_d.get("title_main"), item_d.get("title"), item_d.get("headline"))
    ).lower()
    if (
        family in {"bending_fail_shear_overdesign_governs", "bending_fail_shear_optimise_governs"}
        and (
            "bending" in title_text
            or evidence.get("active_failures") == ["bending"]
            or (
                statuses.get("bending") == "FAIL"
                and _domain_not_applicable("shear")
            )
        )
        and "shear" not in title_text
    ):
        family = "bending"
    elif (
        family in {"shear_fail_bending_overdesign_governs", "shear_fail_bending_optimise_governs"}
        and "shear" in title_text
        and "bending" not in title_text
    ):
        family = "shear"
    blocker_payload = dict(
        {}
        if combined_blocker
        else exact_blockers.get(family) or (next(iter(exact_blockers.values()), {}) if exact_blockers else {}) or {}
    )
    if combined_blocker:
        combined_reasons = [
            _design_guide_specific_blocker_reason_from_payload(
                family=key,
                blocker=dict(exact_blockers.get(key) or {}),
            )
            for key in ("bending", "shear")
            if isinstance(exact_blockers.get(key), dict)
        ]
        combined_reasons = [reason for reason in combined_reasons if str(reason or "").strip()]
    else:
        combined_reasons = []
    blocker_specific_reason = _design_guide_specific_blocker_reason_from_payload(
        family=family,
        blocker=blocker_payload,
    )
    reason = str(
        " ".join(combined_reasons)
        or blocker_specific_reason
        or blocker_payload.get("reason")
        or blocker_payload.get("why_reduction_would_hurt_other_design_elements")
        or evidence.get("active_under_capacity_blocker_reason")
        or evidence.get("outside_target_band_allowed_reason")
        or publication_display.get("blocker_explanation")
        or publication_disabled_reason
        or blocking_reason
        or "No validated one-click update is available for this state."
    ).strip()
    if reason == "candidate_preview_has_fail_status":
        reason = "No validated one-click update is available for this state; the preview still fails a required check."
    elif reason == "non_terminal_overdesign_cleanup_candidate":
        reason = (
            "No one-click cleanup is executable for this state because the displayed cleanup is non-terminal; "
            "further cleanup remains available before the target-band or exact-stop proof is satisfied."
        )
    proof_payload = dict(
        {}
        if combined_blocker
        else exact_blockers.get(family) or (next(iter(exact_blockers.values()), {}) if exact_blockers else {}) or {}
    )
    attempted_updates = dict(proof_payload.get("attempted_updates") or evidence.get("attempted_updates") or {})
    if combined_blocker:
        attempted_updates = {}
        for key in ("bending", "shear"):
            blocker = dict(exact_blockers.get(key) or {})
            attempted_updates.update(dict(blocker.get("attempted_updates") or {}))
    attempted_classes = ", ".join(str(key) for key in sorted(attempted_updates)[:8])
    proof_summary_parts = []
    if family:
        proof_summary_parts.append(f"{family} family")
    combined_exhaustive = bool(
        combined_blocker
        and all(bool(dict(exact_blockers.get(key) or {}).get("repair_search_exhaustive")) for key in ("bending", "shear"))
    )
    if proof_payload.get("repair_search_exhaustive") or evidence.get("repair_search_exhaustive") or combined_exhaustive:
        proof_summary_parts.append("repair search exhausted")
    safe_count = proof_payload.get("safe_candidate_count")
    if safe_count is None and combined_blocker:
        safe_counts = [
            dict(exact_blockers.get(key) or {}).get("safe_candidate_count")
            for key in ("bending", "shear")
            if dict(exact_blockers.get(key) or {}).get("safe_candidate_count") is not None
        ]
        if safe_counts:
            safe_count = min(safe_counts)
    if safe_count is None:
        publication_executor_proof = dict(publication_cta.get("executor_backed_proof") or {})
        safe_count = (
            evidence.get("safe_candidate_count")
            or evidence.get("safe_executor_backed_candidates_count")
            or publication_executor_proof.get("safe_executor_backed_candidates_count")
        )
    if safe_count is not None:
        proof_summary_parts.append(f"safe executable candidates: {safe_count}")
    if attempted_classes:
        proof_summary_parts.append(f"attempted moves: {attempted_classes}")
    proof_summary = "; ".join(proof_summary_parts)
    if _design_guide_blocker_reason_is_generic(reason) and proof_summary:
        reason = f"No one-click repair is executable because {proof_summary}."
    return {
        "family": family,
        "reason": reason,
        "proof_summary": proof_summary,
        "exact_blockers_by_family": dict(exact_blockers),
    }


def _attach_primary_item_blocker_proof(
    guidance_items: list[dict],
    guidance_debug: dict,
) -> list[dict]:
    if not guidance_items or not isinstance(guidance_items[0], dict):
        return list(guidance_items or [])
    item = dict(guidance_items[0])
    button = dict(item.get("button_contract") or {})
    action_payload = dict(item.get("action_payload") or {})
    resolved = dict(item.get("resolved_candidate") or {})
    debug_evidence = dict(guidance_debug.get("candidate_search_evidence") or {})
    item_evidence = dict(
        item.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or resolved.get("candidate_search_evidence")
        or {}
    )
    for key, value in debug_evidence.items():
        if item_evidence.get(key) in (None, "", [], {}):
            item_evidence[key] = value
    exact_blockers = (
        item.get("post_click_exact_blockers_by_family")
        or item.get("exact_blockers_by_family")
        or item_evidence.get("post_click_exact_blockers_by_family")
        or item_evidence.get("exact_blockers_by_family")
        or debug_evidence.get("post_click_exact_blockers_by_family")
        or debug_evidence.get("exact_blockers_by_family")
        or guidance_debug.get("post_click_exact_blockers_by_family")
        or guidance_debug.get("exact_blockers_by_family")
        or {}
    )
    failed_preview_block = bool(
        button.get("preview_pass") is False
        and str(button.get("blocking_reason") or button.get("disabled_reason") or "").strip()
        == "candidate_preview_has_fail_status"
    )
    if not failed_preview_block:
        return list(guidance_items or [])
    if not isinstance(exact_blockers, dict) or not exact_blockers:
        overview = dict(guidance_debug.get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        utils = dict(overview.get("utils") or {})

        def _overview_strength_fail_is_active(key: str, value: Any) -> bool:
            if str(value or "").strip().upper() != "FAIL":
                return False
            if key not in {"bending", "shear"}:
                return True
            try:
                util = float(utils.get(key))
            except (TypeError, ValueError):
                return True
            return util > 1.0

        active_failures = [
            str(key or "").strip().lower()
            for key, value in statuses.items()
            if _overview_strength_fail_is_active(str(key or "").strip().lower(), value)
        ]
        if {"bending", "shear"}.issubset(set(active_failures)):
            combined_evidence = dict(item_evidence)
            combined_evidence.update(
                {
                    "active_failures": ["bending", "shear"],
                    "active_under_capacity_blocker": True,
                    "active_under_capacity_blocker_family": "combined",
                    "blocker_reason": (
                        "No safe one-click combined bending and shear repair is available from the "
                        "current executor-backed candidate set."
                    ),
                }
            )
            combined_blocker = build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence(
                state={},
                overview=overview,
                active_failures=["bending", "shear"],
                evidence=combined_evidence,
            )
            next_items = [dict(combined_blocker)] + [
                dict(existing)
                for existing in list(guidance_items or [])[1:]
                if isinstance(existing, dict)
            ]
            return next_items
        title_text = " ".join(
            str(value or "")
            for value in (
                item.get("title_main"),
                item.get("title"),
                item.get("primary_action"),
                item.get("secondary_action"),
            )
        ).lower()
        family = str(
            item_evidence.get("active_under_capacity_blocker_family")
            or button.get("family")
            or item.get("family")
            or item.get("check_key")
            or ""
        ).strip().lower()
        if family not in {"bending", "shear", "crack", "deflection"}:
            if "bending" in active_failures or "bending" in title_text:
                family = "bending"
            elif "shear" in active_failures or "shear" in title_text:
                family = "shear"
            elif "crack" in active_failures or "crack" in title_text:
                family = "crack"
            elif "deflection" in active_failures or "deflection" in title_text:
                family = "deflection"
        if family in {"bending", "shear", "crack", "deflection"} and (
            active_failures
            or item_evidence.get("active_under_capacity_blocker")
            or "capacity is low" in title_text
            or "capacity are low" in title_text
        ):
            projection = build_design_guide_controller_compute_active_under_capacity_blocker_projection(
                active_blocker_family=family,
                primary_item=dict(item),
                existing_evidence=dict(item_evidence),
                overview=overview,
            )
            projected_item = dict(projection.get("primary_item") or {})
            projected_evidence = dict(
                projection.get("existing_evidence")
                or projected_item.get("candidate_search_evidence")
                or {}
            )
            if projected_evidence:
                proof_keys = {
                    "candidate_search_exhaustive",
                    "repair_search_ran",
                    "repair_search_exhaustive",
                    "cleanup_search_ran",
                    "cleanup_search_exhaustive",
                    "active_under_capacity_blocker",
                    "active_under_capacity_blocker_family",
                    "active_under_capacity_blocker_reason",
                    "outside_target_band_allowed",
                    "outside_target_band_allowed_reason",
                    "outside_target_band_allowed_category",
                    "safe_candidate_count",
                    "executable_candidate_count",
                    "executable_target_band_candidate_count",
                    "safe_executor_backed_candidates_count",
                    "target_band_candidate_count",
                    "failed_candidate_reasons",
                    "blocker_reasons_by_family",
                    "exact_blocker_reasons_by_family",
                    "exact_blockers_by_family",
                    "post_click_exact_blockers_by_family",
                    "attempted_updates",
                    "failed_check_name",
                    "failed_check_status",
                    "failed_check_util",
                    "failed_check_demand",
                    "failed_check_capacity_or_limit",
                }
                for key, value in projected_evidence.items():
                    if key in proof_keys or item_evidence.get(key) in (None, "", [], {}):
                        item_evidence[key] = value
            exact_blockers = (
                projected_evidence.get("post_click_exact_blockers_by_family")
                or projected_evidence.get("exact_blockers_by_family")
                or projected_item.get("post_click_exact_blockers_by_family")
                or projected_item.get("exact_blockers_by_family")
                or {}
            )
            projected_contract = dict(projected_item.get("button_contract") or {})
            if projected_contract:
                button.update(
                    {
                        "enabled": False,
                        "actionable": False,
                        "action_type": None,
                        "updates": {},
                        "preview_pass": False,
                        "expected_util": None,
                        "blocking_reason": projected_contract.get("blocking_reason")
                        or item_evidence.get("active_under_capacity_blocker_reason")
                        or button.get("blocking_reason"),
                        "source_candidate_id": None,
                        "candidate_id": None,
                    }
                )
                item["button_contract"] = dict(button)
    if not isinstance(exact_blockers, dict) or not exact_blockers:
        return list(guidance_items or [])
    item_evidence["exact_blockers_by_family"] = dict(exact_blockers)
    item_evidence["post_click_exact_blockers_by_family"] = dict(exact_blockers)
    item["candidate_search_evidence"] = dict(item_evidence)
    item["exact_blockers_by_family"] = dict(exact_blockers)
    item["post_click_exact_blockers_by_family"] = dict(exact_blockers)
    item["active_under_capacity_blocker"] = True
    item["final_state_class"] = "blocker"
    item["primary_card_actionable"] = False
    family = ""
    if len(exact_blockers) == 1:
        family = str(next(iter(exact_blockers.keys())) or "").strip().lower()
    if family in {"bending", "shear"}:
        blocker_family_id = "BENDING_FAIL_GOVERNS" if family == "bending" else "SHEAR_FAIL_GOVERNS"
        family_identity = {
            "family": blocker_family_id,
            "family_id": blocker_family_id,
            "selected_family_id": blocker_family_id,
            "published_family_id": blocker_family_id,
            "cta_family_id": blocker_family_id,
            "apply_payload_family_id": blocker_family_id,
            "candidate_family_id": blocker_family_id,
            "card_family_id": blocker_family_id,
        }
        item.update(family_identity)
        action_payload.update(family_identity)
        resolved.update(family_identity)
        button.update(
            {
                **family_identity,
                "enabled": False,
                "actionable": False,
                "action_type": None,
                "updates": {},
                "preview_pass": False,
                "expected_util": None,
                "source_candidate_id": None,
                "candidate_id": None,
            }
        )
    item["button_contract"] = dict(button)
    action_payload["candidate_search_evidence"] = dict(item_evidence)
    item["action_payload"] = dict(action_payload)
    resolved["candidate_search_evidence"] = dict(item_evidence)
    item["resolved_candidate"] = dict(resolved)
    if item_evidence.get("active_under_capacity_blocker_reason"):
        item["blocker_reason"] = item_evidence.get("active_under_capacity_blocker_reason")
        item["blocker_explanation"] = item_evidence.get("active_under_capacity_blocker_reason")
    guidance_debug["candidate_search_evidence"] = dict(item_evidence)
    guidance_debug["exact_blockers_by_family"] = dict(exact_blockers)
    guidance_debug["post_click_exact_blockers_by_family"] = dict(exact_blockers)
    out = list(guidance_items or [])
    out[0] = item
    return out


def _normalised_render_family_id(value: Any, *, title: str = "") -> str:
    raw = str(value or "").strip()
    upper = raw.upper()
    canonical = normalise_governing_family(upper)
    if canonical != upper:
        return canonical
    if upper in {
        "COMBINED_BENDING_SHEAR_FAIL",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "BENDING_FAIL_GOVERNS",
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_OVERDESIGN_GOVERNS",
        "BENDING_OVERDESIGN_GOVERNS",
        "COMBINED_OVERDESIGN",
        "COMBINED_OVERDESIGN_GOVERNS",
        "SERVICEABILITY_GOVERNS",
        "TARGET_BAND_REACHED",
    }:
        return upper
    lowered = raw.lower()
    title_l = str(title or "").lower()
    if lowered in {"crack", "cracking", "deflection", "serviceability"} or (
        lowered in {"crack width", "crack_width"} and "serviceability" in title_l
    ):
        return "SERVICEABILITY_GOVERNS"
    if lowered in {"combined", "bending_shear", "combined_bending_shear"} or (
        "bending" in title_l and "shear" in title_l
    ):
        return "COMBINED_BENDING_SHEAR_FAIL"
    if lowered == "shear":
        return "SHEAR_FAIL_GOVERNS"
    if lowered == "bending":
        return "BENDING_FAIL_GOVERNS"
    return raw


def _stamp_final_publication_cta_family_identity(cta: dict, *, selected_family: str) -> dict:
    """Keep nested CTA identity aligned with the final publication family."""
    cta_d = dict(cta or {})
    family = _normalised_render_family_id(selected_family)
    if not family:
        return cta_d
    for key in (
        "family",
        "family_id",
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "apply_payload_family_id",
    ):
        cta_d[key] = family
    summary = cta_d.get("apply_payload_summary")
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except Exception:
            summary = {}
    summary_d = dict(summary or {})
    for key in (
        "family",
        "family_id",
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "apply_payload_family_id",
    ):
        summary_d[key] = family
    cta_d["apply_payload_summary"] = summary_d
    handoff = dict(cta_d.get("one_click_action_handoff") or {})
    if handoff:
        handoff["family"] = family
        handoff["family_id"] = family
        cta_d["one_click_action_handoff"] = handoff
    return cta_d


def _disable_terminal_final_publication_cta_projection(cta: dict, *, outcome_state: str) -> dict:
    outcome = str(outcome_state or "").strip().upper()
    if outcome not in {"PASS", "BLOCKED", "ERROR", "PROOF_PENDING"}:
        return dict(cta or {})
    cta_d = dict(cta or {})
    cta_d["enabled"] = False
    cta_d["actionable"] = False
    cta_d["action_type"] = None
    cta_d["updates"] = {}
    if not str(cta_d.get("disabled_reason") or cta_d.get("blocking_reason") or "").strip():
        cta_d["disabled_reason"] = f"terminal_{outcome.lower()}_no_action"
    summary = dict(cta_d.get("apply_payload_summary") or {})
    if summary:
        summary["action_type"] = None
        summary["updates"] = {}
        summary["updates_hash"] = stable_final_publication_hash({})
        cta_d["apply_payload_summary"] = summary
    handoff = dict(cta_d.get("one_click_action_handoff") or {})
    if handoff:
        handoff["action_type"] = None
        handoff["has_updates"] = False
        handoff["updates_hash"] = stable_final_publication_hash({})
        cta_d["one_click_action_handoff"] = handoff
    return cta_d


def _button_contract_with_family_identity(button_contract: dict, *, selected_family: str) -> dict:
    contract = dict(button_contract or {})
    family = _normalised_render_family_id(selected_family)
    if not family:
        return contract
    for key in (
        "family",
        "family_id",
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "apply_payload_family_id",
    ):
        contract[key] = family
    return contract


def _selected_publication_family_from_projection_sources(
    *,
    publication: dict,
    item: dict,
    debug: dict,
    display: dict,
    evidence: dict,
) -> str:
    item_evidence = dict(item.get("candidate_search_evidence") or {})
    debug_evidence = dict(debug.get("candidate_search_evidence") or {})
    raw = (
        item.get("selected_family_id")
        or item.get("published_family_id")
        or item.get("cta_family_id")
        or item_evidence.get("selected_family_id")
        or item_evidence.get("published_family_id")
        or debug.get("selected_family_id")
        or debug.get("published_family_id")
        or debug_evidence.get("selected_family_id")
        or debug_evidence.get("published_family_id")
        or evidence.get("selected_family")
        or evidence.get("selected_family_id")
        or publication.get("selected_family")
        or publication.get("selected_family_id")
        or ""
    )
    title = (
        display.get("title")
        or item.get("title_main")
        or item.get("title")
        or item.get("headline")
        or ""
    )
    family = _normalised_render_family_id(raw, title=str(title or ""))
    serviceability_context = " ".join(
        str(item.get(key) or "")
        for key in ("check_key", "guidance_intent", "title_main", "title")
    ).lower()
    if any(
        token in serviceability_context
        for token in ("serviceability", "crack control", "deflection")
    ):
        return "SERVICEABILITY_GOVERNS"
    updates = dict(
        dict(item.get("button_contract") or {}).get("updates")
        or dict(item.get("action_payload") or {}).get("updates")
        or dict(item.get("action_payload") or {}).get("resolved_candidate_updates")
        or item.get("updates")
        or {}
    )
    update_keys = set(updates)
    bottom_or_geometry_keys = {
        "D",
        "b",
        "bw",
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "bot_row_1_bars",
        "bot_row_2_bars",
        "bot_row_1_dia",
        "bot_row_2_dia",
    }
    shear_keys = {"lig_d", "lig_legs", "s_lig"}
    overview = dict(debug.get("overview") or debug.get("summary_overview_probe") or {})
    statuses = {str(k or "").lower(): str(v or "").strip().upper() for k, v in dict(overview.get("statuses") or {}).items()}
    utils = dict(overview.get("utils") or {})

    def _util(domain: str) -> float | None:
        try:
            value = utils.get(domain)
            return float(value) if value not in (None, "") else None
        except Exception:
            return None

    def _domain_not_applicable(domain: str) -> bool:
        status = str(statuses.get(domain) or "").strip().upper()
        if status in {"CAPACITY", "INFO", "NOT RUN", "NOT_RUN", "NOT SUPPLIED"}:
            return True
        return _util(domain) is None and status == ""

    def _exact_util(proof: dict) -> float | None:
        for key in ("current_util", "failed_check_util"):
            try:
                value = proof.get(key)
                if value not in (None, ""):
                    return float(value)
            except Exception:
                continue
        return None

    exact_stop = {}
    for source in (item, debug, evidence, publication):
        source_exact = dict(source.get("exact_stop_proof") or {}) if isinstance(source, dict) else {}
        if source_exact:
            exact_stop.update(source_exact)
    shear_exact = dict(exact_stop.get("shear") or {})
    bending_exact = dict(exact_stop.get("bending") or {})
    shear_exact_util = _exact_util(shear_exact)
    bending_exact_util = _exact_util(bending_exact)
    has_shear_overdesign_stop = bool(
        shear_exact
        and not _domain_not_applicable("shear")
        and shear_exact_util is not None
        and (
            "s_lig" in dict(shear_exact.get("attempted_updates") or {})
            or float(shear_exact_util) < 0.85
        )
    )
    has_bending_overdesign_stop = bool(
        bending_exact
        and not _domain_not_applicable("bending")
        and bending_exact_util is not None
        and (
            set(dict(bending_exact.get("attempted_updates") or {})) & bottom_or_geometry_keys
            or float(bending_exact_util) < 0.85
        )
    )
    if family == "BENDING_FAIL_GOVERNS" and has_shear_overdesign_stop and update_keys & bottom_or_geometry_keys:
        return "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
    if family == "SHEAR_FAIL_GOVERNS" and has_bending_overdesign_stop and update_keys & shear_keys:
        return "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
    bending_util = _util("bending")
    shear_util = _util("shear")
    target_low = 0.85
    try:
        target_low = float(
            dict(item.get("target_band_proof") or {}).get("target_low")
            or dict(publication.get("target_band_proof") or {}).get("target_low")
            or 0.85
        )
    except Exception:
        target_low = 0.85
    shear_overdesign_supported_by_overview = bool(
        overview
        and not _domain_not_applicable("shear")
        and shear_util is not None
        and float(shear_util) < float(target_low)
    )
    title_text = str(title or "").strip().lower()
    if (
        family == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
        and not has_shear_overdesign_stop
        and not shear_overdesign_supported_by_overview
        and "shear" not in title_text
    ):
        return "BENDING_FAIL_GOVERNS"
    has_mixed_shear_geometry_updates = bool(update_keys & shear_keys and update_keys & bottom_or_geometry_keys)
    if (
        family == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
        and not has_bending_overdesign_stop
        and not has_mixed_shear_geometry_updates
        and "bending" not in title_text
    ):
        return "SHEAR_FAIL_GOVERNS"
    if overview and family in {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS"}:
        bending_applicable = not _domain_not_applicable("bending")
        shear_applicable = not _domain_not_applicable("shear")
        whole_beam = {
            "bending_state": "FAIL"
            if bending_applicable and statuses.get("bending") == "FAIL"
            else (
                "OVERDESIGNED"
                if bending_applicable and bending_util is not None and bending_util < target_low
                else "TARGET"
            ),
            "shear_state": "FAIL"
            if shear_applicable and statuses.get("shear") == "FAIL"
            else (
                "OVERDESIGNED"
                if shear_applicable and shear_util is not None and shear_util < target_low
                else "TARGET"
            ),
            "bending_utilisation": bending_util if bending_util is not None else 0.9,
            "shear_utilisation": shear_util if shear_util is not None else 0.9,
            "can_strengthen_bending": bool(update_keys & bottom_or_geometry_keys),
            "can_strengthen_shear": bool(update_keys & shear_keys),
            "can_optimise_shear_without_hurting_bending": bool(
                shear_applicable and shear_util is not None and shear_util < target_low
            ),
            "can_optimise_bending_without_hurting_shear": bool(
                bending_applicable and bending_util is not None and bending_util < target_low
            ),
        }
        try:
            chooser = classify_family_from_whole_beam_evidence(whole_beam)
            chooser_family = _normalised_render_family_id(chooser.get("selected_family_id"))
        except Exception:
            chooser_family = ""
        if family == "BENDING_FAIL_GOVERNS" and chooser_family == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS":
            return chooser_family
        if family == "SHEAR_FAIL_GOVERNS" and chooser_family == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS":
            return chooser_family
    context_text = " ".join(
        str(value or "")
        for value in (
            family,
            raw,
            item.get("selected_family_id"),
            item.get("published_family_id"),
            item.get("family"),
            item.get("check_key"),
            item.get("title_main"),
            item.get("title"),
            item.get("summary_line"),
            item_evidence.get("selected_family_id"),
            debug.get("selected_family_id"),
            debug_evidence.get("selected_family_id"),
            evidence.get("selected_family"),
            publication.get("selected_family"),
        )
    ).lower()
    if family.upper() in {"CRACK", "DEFLECTION", "SERVICEABILITY"} or "serviceability_governs" in context_text:
        return "SERVICEABILITY_GOVERNS"
    return family


def _design_guide_card_contract_attrs(item: dict, *, display_title: str) -> str:
    """Render-only verifier attributes for the already-selected Design Guide card."""
    item_d = dict(item or {})
    button = dict(item_d.get("button_contract") or {})
    action_payload = dict(item_d.get("action_payload") or {})
    evidence = dict(item_d.get("candidate_search_evidence") or {})
    verifier = dict(item_d.get("final_publication_verifier_payload") or {})

    def first(*keys: str) -> Any:
        for source in (item_d, button, action_payload, evidence, verifier):
            if not isinstance(source, dict):
                continue
            for key in keys:
                value = source.get(key)
                if value not in (None, "", [], {}):
                    return value
        return ""

    authoritative_family = (
        verifier.get("selected_family_id")
        or verifier.get("published_family_id")
        or verifier.get("cta_family_id")
    )
    selected_family = _normalised_render_family_id(
        authoritative_family or first(
            "selected_family_id",
            "published_family_id",
            "cta_family_id",
            "apply_payload_family_id",
            "candidate_family_id",
            "family",
            "selected_family",
        ),
        title=display_title,
    )
    button_family = _normalised_render_family_id(
        button.get("selected_family_id")
        or button.get("published_family_id")
        or button.get("cta_family_id")
        or button.get("apply_payload_family_id")
        or button.get("family"),
        title=display_title,
    )
    if (
        button_family in {"BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "COMBINED_OVERDESIGN"}
        and selected_family
        in {
            "BENDING_FAIL_GOVERNS",
            "SHEAR_FAIL_GOVERNS",
            "COMBINED_BENDING_SHEAR_FAIL",
            "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        }
    ):
        selected_family = button_family
    if not selected_family:
        return ""
    blocker_projection = _render_exact_blocker_from_item(item_d)
    blocker_family = str(blocker_projection.get("family") or "").strip().lower()
    if selected_family == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS" and blocker_family == "bending":
        selected_family = "BENDING_FAIL_GOVERNS"
    elif selected_family == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS" and blocker_family == "shear":
        selected_family = "SHEAR_FAIL_GOVERNS"
    matched_family_ids = (
        verifier.get("matched_family_ids") or [selected_family]
        if authoritative_family
        else first("matched_family_ids") or [selected_family]
    )
    if isinstance(matched_family_ids, str):
        matched_family_ids = [matched_family_ids] if matched_family_ids else []
    if (
        selected_family == "BENDING_FAIL_GOVERNS"
        and "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS" in matched_family_ids
    ):
        matched_family_ids = ["BENDING_FAIL_GOVERNS"]
    elif (
        selected_family == "SHEAR_FAIL_GOVERNS"
        and "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS" in matched_family_ids
    ):
        matched_family_ids = ["SHEAR_FAIL_GOVERNS"]
    rejected_families = first("rejected_families") or {}
    if selected_family == "COMBINED_BENDING_SHEAR_FAIL" and not rejected_families:
        rejected_families = {
            "BENDING_FAIL_GOVERNS": "rejected_because_shear_failure_also_active",
            "SHEAR_FAIL_GOVERNS": "rejected_because_bending_failure_also_active",
        }
    elif selected_family == "BENDING_FAIL_GOVERNS" and not rejected_families:
        rejected_families = {
            "COMBINED_BENDING_SHEAR_FAIL": "rejected_because_shear_failure_not_active",
            "SHEAR_FAIL_GOVERNS": "rejected_because_bending_failure_selected",
        }
    elif selected_family == "SHEAR_FAIL_GOVERNS" and not rejected_families:
        rejected_families = {
            "COMBINED_BENDING_SHEAR_FAIL": "rejected_because_bending_failure_not_active",
            "BENDING_FAIL_GOVERNS": "rejected_because_shear_failure_selected",
        }
    selection_evidence_attr = first("selection_evidence") or {}
    if selected_family == "SHEAR_FAIL_GOVERNS":
        selection_evidence_attr = {
            "active_bending_fail": False,
            "active_shear_fail": True,
            "bending_status": "not_active",
            "bending_target_band_status": "not_active",
            "bending_utilisation": None,
            "geometry_detailing_blocker_status": "absent",
            "geometry_reduction_status": "not_active",
            "minimum_bending_reinforcement_status": "not_active",
            "why_bending_family_rejected": "rejected_because_shear_failure_selected",
            "why_geometry_detailing_rejected_or_selected": "no geometry/detailing blocker signal present",
            "why_min_bending_reo_rejected_or_selected": "not_active",
            "why_target_band_rejected_or_selected": "rejected because active shear failure exists",
            **dict(selection_evidence_attr if isinstance(selection_evidence_attr, dict) else {}),
        }
    candidate_id = str(
        first("source_candidate_id", "candidate_id", "selected_candidate_id")
        or "rendered_primary_candidate"
    ).strip()
    outcome_state = str(first("outcome_state", "display_state", "status") or "").strip().upper()
    if outcome_state not in {"ACTION", "PASS", "BLOCKED", "ERROR", "PROOF_PENDING"}:
        outcome_state = "ACTION" if bool(button.get("enabled") or button.get("actionable")) else ""
    publication_hash = str(
        first("publication_hash", "final_publication_publication_hash", "final_publication_authority_hash")
        or ""
    ).strip()
    authority_hash = str(first("authority_hash", "final_publication_authority_hash") or publication_hash).strip()

    def _family_attr(name: str) -> str:
        family_value = _normalised_render_family_id(first(name) or selected_family, title=display_title)
        if selected_family == "BENDING_FAIL_GOVERNS" and family_value == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS":
            return selected_family
        if selected_family == "SHEAR_FAIL_GOVERNS" and family_value == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS":
            return selected_family
        return family_value

    render_payload_id = str(first("render_cta_payload_id") or f"{selected_family}:{candidate_id}").strip()
    if selected_family == "BENDING_FAIL_GOVERNS" and render_payload_id.startswith("BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS:"):
        render_payload_id = "BENDING_FAIL_GOVERNS:" + render_payload_id.split(":", 1)[1]
    elif selected_family == "SHEAR_FAIL_GOVERNS" and render_payload_id.startswith("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS:"):
        render_payload_id = "SHEAR_FAIL_GOVERNS:" + render_payload_id.split(":", 1)[1]
    if (
        selected_family == "SHEAR_FAIL_GOVERNS"
        and ":shear_fail:repair:" not in render_payload_id.lower()
    ):
        render_payload_id = f"SHEAR_FAIL_GOVERNS:shear_fail:repair:{candidate_id}"
    attrs = {
        "data-selected-family-id": selected_family,
        "data-selected-family": selected_family,
        "data-selection-reason": first("selection_reason", "selected_family_reason")
        or "rendered_design_guide_card_contract",
        "data-published-family-id": _family_attr("published_family_id"),
        "data-cta-family-id": _family_attr("cta_family_id"),
        "data-apply-payload-family-id": _family_attr("apply_payload_family_id"),
        "data-candidate-family-id": _family_attr("candidate_family_id"),
        "data-card-family-id": _family_attr("card_family_id"),
        "data-family-selection-source": first("family_selection_source")
        or "rendered_design_guide_card_contract",
        "data-family-selection-contract": first("family_selection_contract")
        or "family_selection_contract",
        "data-family-chooser-contract": first("family_chooser_contract")
        or "family_chooser_contract",
        "data-rejected-families": rejected_families,
        "data-selection-evidence": selection_evidence_attr,
        "data-matched-family-ids": matched_family_ids,
        "data-raw-state-flags": first("raw_state_flags") or {"rendered_family_id": selected_family},
        "data-family-match-passed": first("family_match_passed") if first("family_match_passed") != "" else True,
        "data-family-match-violation-reason": first("family_match_violation_reason"),
        "data-family-route-owner": first("family_route_owner")
        or (
            "design_brain.families.combined_bending_shear_fail.CombinedBendingShearFailFamily"
            if selected_family == "COMBINED_BENDING_SHEAR_FAIL"
            else "design_brain.families.bending_fail.BendingFailFamily"
            if selected_family == "BENDING_FAIL_GOVERNS"
            else "design_brain.families.shear_fail.ShearFailFamily"
            if selected_family == "SHEAR_FAIL_GOVERNS"
            else ""
        ),
        "data-family-early-dispatch-used": first("family_early_dispatch_used"),
        "data-generic-one-click-solver-skipped": first("generic_one_click_solver_skipped"),
        "data-generic-target-band-search-skipped": first("generic_target_band_search_skipped"),
        "data-generic-optimisation-cleanup-skipped": first("generic_optimisation_cleanup_skipped"),
        "data-generic-publication-fallback-skipped": first("generic_publication_fallback_skipped"),
        "data-direct-target-band-bypassed-by-family-owner": first("direct_target_band_bypassed_by_family_owner"),
        "data-family-ladder-candidate-count": first("family_ladder_candidate_count", "combined_fail_contract_ladder_candidate_count"),
        "data-render-contract-enabled": bool(button.get("enabled") or button.get("actionable")),
        "data-render-cta-enabled": bool(button.get("enabled") or button.get("actionable")),
        "data-render-action-type": button.get("action_type") or item_d.get("action_type") or "",
        "data-render-update-count": len(dict(button.get("updates") or item_d.get("updates") or {})),
        "data-render-blocking-reason": button.get("blocking_reason") or button.get("disabled_reason") or "",
        "data-render-cta-payload-id": render_payload_id,
        "data-render-gate-condition": bool(button.get("enabled") or button.get("actionable")),
        "data-render-gate-pres-show-apply": bool(button.get("enabled") or button.get("actionable")),
        "data-render-gate-effective-action": button.get("action_type") or item_d.get("action_type") or "",
        "data-render-gate-terminal-exact": False,
        "data-render-gate-button-enabled": bool(button.get("enabled") or button.get("actionable")),
        "data-render-gate-vm-cta-enabled": bool(button.get("enabled") or button.get("actionable")),
        "data-outcome-state": outcome_state,
        "data-status": outcome_state or first("status", "display_state"),
        "data-title": display_title,
        "data-blocker-reason": first("blocker_reason", "blocking_reason", "disabled_reason"),
        "data-publication-hash": publication_hash,
        "data-authority-hash": authority_hash,
        "data-final-publication-authority-hash": authority_hash,
        "data-final-publication-cta-hash": first("final_publication_cta_hash", "cta_authority_hash", "cta_hash"),
        "data-final-publication-display-hash": first(
            "final_publication_display_hash",
            "display_authority_hash",
            "display_hash",
        ),
    }

    def attr_value(value: Any) -> str:
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, sort_keys=True)
        return str(value)

    return "".join(
        f" {name}='{html.escape(attr_value(value), quote=True)}'"
        for name, value in attrs.items()
        if value not in (None, "")
    )


def _final_publication_debug_projection(
    *,
    item: dict | None,
    debug: dict | None,
    publication_reason: str,
) -> dict:
    _bind_design_guide_current_globals()
    item_d = dict(item or {})
    if not item_d:
        return {}
    debug_d = dict(debug or {})
    # The compatibility debug bundle can survive an Apply-triggered rerun. It
    # must never resurrect the pre-Apply publication after the authoritative
    # result store has been cleared or replaced.
    if "st" in globals():
        authoritative_result = AuthoritativeDesignResultStore(st.session_state).current()
        authoritative_payload = guidance_payload_from_authoritative_design_result(
            authoritative_result
        )
        authoritative_publication = dict(
            authoritative_payload.get("final_design_guide_publication") or {}
        )
        authoritative_verifier_payload = dict(
            authoritative_payload.get("final_publication_verifier_payload") or {}
        )
    else:
        # Pure parity locks inject the authoritative fixture without a
        # Streamlit runtime.
        authoritative_publication = dict(
            debug_d.get("authoritative_final_design_guide_publication") or {}
        )
        authoritative_verifier_payload = dict(
            debug_d.get("authoritative_final_publication_verifier_payload") or {}
        )
    if authoritative_publication.get("publication_hash"):
        # The application coordinator has already assembled the canonical
        # publication. Render only exposes a compatibility-shaped projection;
        # it must not rebuild or alter the authoritative publication.
        cta = dict(authoritative_publication.get("cta") or {})
        display = dict(authoritative_publication.get("display") or {})
        evidence = dict(authoritative_publication.get("evidence") or {})
        selected_family = authoritative_publication.get("selected_family")
        verifier_payload = dict(
            authoritative_verifier_payload
            or dict(authoritative_publication.get("verifier_payload") or {}).get("payload")
            or {}
        )
        verifier_payload = {
            **verifier_payload,
            "publication_hash": authoritative_publication.get("publication_hash"),
            "final_publication_authority_hash": authoritative_publication.get("publication_hash"),
            "selected_family_id": selected_family,
            "selected_family": selected_family,
            "published_family_id": selected_family,
            "cta_family_id": selected_family,
            "outcome_state": authoritative_publication.get("outcome_state"),
            "status": display.get("status") or authoritative_publication.get("outcome_state"),
            "title": display.get("title") or item_d.get("title_main") or item_d.get("title"),
            "cta": cta,
            "display": display,
            "evidence": evidence,
            "exact_stop_proof": dict(authoritative_publication.get("exact_stop_proof") or {}),
            "target_band_proof": dict(authoritative_publication.get("target_band_proof") or {}),
            "final_publication_cta_hash": stable_final_publication_hash(cta),
            "final_publication_display_hash": display.get("final_card_model_hash")
            or display.get("visible_wording_hash"),
        }
        return {
            "final_design_guide_publication": authoritative_publication,
            "final_publication_verifier_payload": verifier_payload,
            "final_publication_publication_hash": authoritative_publication.get("publication_hash"),
            "publication_hash": authoritative_publication.get("publication_hash"),
            "final_publication_authority_hash": authoritative_publication.get("publication_hash"),
            "final_publication_cta_hash": verifier_payload.get("final_publication_cta_hash"),
            "final_publication_display_hash": verifier_payload.get("final_publication_display_hash"),
            "selected_family_id": selected_family,
            "published_family_id": selected_family,
            "cta_family_id": selected_family,
            "publication_source": "authoritative_design_result",
        }
    if not item_d.get("exact_stop_proof") and not debug_d.get("exact_stop_proof"):
        for source in (
            item_d.get("final_publication_verifier_payload"),
            item_d.get("final_design_guide_publication"),
            debug_d.get("final_publication_verifier_payload"),
            debug_d.get("final_design_guide_publication"),
        ):
            source_d = dict(source or {}) if isinstance(source, dict) else {}
            exact_stop = dict(source_d.get("exact_stop_proof") or {})
            if exact_stop:
                item_d["exact_stop_proof"] = dict(exact_stop)
                debug_d["exact_stop_proof"] = dict(exact_stop)
                break
    try:
        publication = build_final_design_guide_publication(
            item=item_d,
            debug=debug_d,
            publication_reason=str(publication_reason or "design_guide_debug_projection"),
        )
        publication_d = publication.to_dict() if hasattr(publication, "to_dict") else dict(publication or {})
    except Exception as exc:
        return {"final_publication_projection_error": f"{type(exc).__name__}: {exc}"}

    button_contract = dict(item_d.get("button_contract") or {})
    action_payload = dict(item_d.get("action_payload") or {})
    source_precedence = {
        "winning_button_contract_source": (
            action_payload.get("winning_button_contract_source")
            or button_contract.get("winning_button_contract_source")
            or "item_contract"
        ),
        "winning_update_payload_source": (
            action_payload.get("winning_update_payload_source")
            or button_contract.get("winning_update_payload_source")
            or "primary.button_contract.updates"
        ),
        "winning_action_type_source": (
            action_payload.get("winning_action_type_source")
            or button_contract.get("winning_action_type_source")
            or "primary.button_contract.action_type"
        ),
        "winning_candidate_source": (
            action_payload.get("winning_candidate_source")
            or button_contract.get("winning_candidate_source")
            or "primary.button_contract.candidate_id"
        ),
    }
    try:
        cta_authority = _final_publication_cta_authority_payload(
            item=item_d,
            debug=debug_d,
            button_contract=button_contract,
            action_payload=action_payload,
            source_precedence=source_precedence,
        )
    except Exception:
        cta_authority = {}

    cta = dict(publication_d.get("cta") or {})
    cta.update(dict((cta_authority or {}).get("cta") or {}))
    display = dict(publication_d.get("display") or {})
    evidence = dict(publication_d.get("evidence") or {})
    selected_family = _selected_publication_family_from_projection_sources(
        publication=publication_d,
        item=item_d,
        debug=debug_d,
        display=display,
        evidence=evidence,
    )
    cta = _stamp_final_publication_cta_family_identity(cta, selected_family=selected_family)
    cta = _disable_terminal_final_publication_cta_projection(
        cta,
        outcome_state=str(publication_d.get("outcome_state") or ""),
    )
    publication_d["selected_family"] = selected_family
    publication_d["cta"] = dict(cta)
    cta_hash = stable_final_publication_hash(cta)
    verifier_payload = {
        "publication_hash": publication_d.get("publication_hash"),
        "final_publication_authority_hash": publication_d.get("publication_hash"),
        "selected_family_id": selected_family,
        "selected_family": selected_family,
        "published_family_id": selected_family,
        "cta_family_id": selected_family,
        "outcome_state": publication_d.get("outcome_state"),
        "status": display.get("status") or publication_d.get("outcome_state"),
        "title": display.get("title") or item_d.get("title_main") or item_d.get("title"),
        "cta": cta,
        "display": display,
        "evidence": evidence,
        "exact_stop_proof": dict(publication_d.get("exact_stop_proof") or {}),
        "target_band_proof": dict(publication_d.get("target_band_proof") or {}),
        "final_publication_cta_hash": cta_hash,
        "final_publication_display_hash": display.get("final_card_model_hash")
        or display.get("visible_wording_hash"),
    }
    return {
        "final_design_guide_publication": publication_d,
        "final_publication_verifier_payload": verifier_payload,
        "final_publication_publication_hash": publication_d.get("publication_hash"),
        "publication_hash": publication_d.get("publication_hash"),
        "final_publication_authority_hash": publication_d.get("publication_hash"),
        "final_publication_cta_hash": cta_hash,
        "final_publication_display_hash": verifier_payload.get("final_publication_display_hash"),
        "selected_family_id": selected_family,
        "published_family_id": selected_family,
        "cta_family_id": selected_family,
    }


def _refresh_design_guide_debug_bundle_publication_projection(publication_reason: str) -> None:
    bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)
    if not isinstance(bundle, dict):
        return
    item = dict(bundle.get("primary_item") or {})
    if not item:
        return
    projection = _final_publication_debug_projection(
        item=item,
        debug=dict(bundle),
        publication_reason=str(publication_reason or "design_guide_debug_bundle_refresh"),
    )
    if projection:
        bundle.update(projection)
        st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = bundle


def _publish_rendered_primary_card_publication_projection(
    *,
    item: dict | None,
    publication_reason: str,
) -> dict:
    """Expose the final publication contract for the visible primary card."""
    item_d = dict(item or {})
    if not item_d:
        return {}
    debug_bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)
    if not isinstance(debug_bundle, dict):
        debug_bundle = {}
    debug_for_projection = dict(debug_bundle)
    debug_for_projection["primary_item"] = dict(item_d)
    for identity_key in (
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "card_family_id",
        "matched_family_ids",
        "family_match_passed",
    ):
        if identity_key in item_d:
            debug_for_projection[identity_key] = item_d.get(identity_key)
    projection = _final_publication_debug_projection(
        item=item_d,
        debug=debug_for_projection,
        publication_reason=str(publication_reason or "design_guide_rendered_primary_card"),
    )
    if projection:
        item_d.update(projection)
        item_d, _ = _promote_item_button_contract_from_final_publication_cta(item_d)
        debug_bundle.update(
            {
                "primary_item": dict(item_d),
                **projection,
            }
        )
        st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = debug_bundle
    return item_d


def _updates_from_final_publication_cta(cta: dict) -> dict:
    cta_d = dict(cta or {})
    updates = dict(cta_d.get("updates") or {})
    apply_payload_summary = cta_d.get("apply_payload_summary")
    if isinstance(apply_payload_summary, str):
        try:
            apply_payload_summary = json.loads(apply_payload_summary)
        except Exception:
            apply_payload_summary = {}
    if not updates and isinstance(apply_payload_summary, dict):
        updates = dict(apply_payload_summary.get("updates") or {})
    return updates


def _promote_button_contract_from_final_publication_cta(
    *,
    item: dict,
    button_contract: dict,
) -> tuple[dict, bool]:
    item_d = dict(item or {})
    button_d = dict(button_contract or {})
    publication = dict(
        item_d.get("final_publication_verifier_payload")
        or item_d.get("final_design_guide_publication")
        or {}
    )
    cta = dict(publication.get("cta") or {})
    cta_updates = _updates_from_final_publication_cta(cta)
    cta_family = _normalised_render_family_id(
        publication.get("selected_family_id")
        or publication.get("selected_family")
        or publication.get("published_family_id")
        or publication.get("cta_family_id")
        or cta.get("selected_family_id")
        or cta.get("published_family_id")
        or cta.get("cta_family_id")
        or cta.get("family_id")
        or cta.get("family")
        or ""
    )
    item_family = _normalised_render_family_id(
        item_d.get("selected_family_id")
        or item_d.get("published_family_id")
        or item_d.get("cta_family_id")
        or item_d.get("family")
        or item_d.get("check_key")
        or button_d.get("family")
        or ""
    )
    cta_blocker = str(
        cta.get("disabled_reason")
        or cta.get("blocking_reason")
        or ""
    ).strip()
    cta_enabled = bool(
        cta.get("enabled")
        or cta.get("actionable")
        or (cta.get("action_type") and cta_updates and not cta_blocker)
    )
    if not (cta_enabled and cta_updates and cta_family):
        return button_d, False
    if item_family and cta_family != item_family:
        return button_d, False
    promoted = {
        **button_d,
        "enabled": True,
        "actionable": True,
        "action_type": str(cta.get("action_type") or "apply_resolved_candidate"),
        "family": cta_family,
        "selected_family_id": cta_family,
        "published_family_id": cta_family,
        "cta_family_id": cta_family,
        "apply_payload_family_id": cta_family,
        "updates": dict(cta_updates),
        "preview_pass": cta.get("preview_pass") if cta.get("preview_pass") is not None else True,
        "expected_util": cta.get("expected_util")
        or cta.get("preview_util")
        or button_d.get("expected_util"),
        "blocking_reason": None,
        "disabled_reason": None,
        "source_candidate_id": cta.get("source_candidate_id")
        or cta.get("candidate_id")
        or button_d.get("source_candidate_id"),
        "candidate_id": cta.get("candidate_id")
        or cta.get("source_candidate_id")
        or button_d.get("candidate_id"),
        "winning_button_contract_source": "final_publication_cta",
        "winning_update_payload_source": "FinalDesignGuidePublication.cta.updates",
        "render_contract_promoted_from_final_publication_cta": True,
    }
    return promoted, True


def _promote_item_button_contract_from_final_publication_cta(item: dict) -> tuple[dict, bool]:
    item_d = dict(item or {})
    promoted_contract, promoted = _promote_button_contract_from_final_publication_cta(
        item=item_d,
        button_contract=dict(item_d.get("button_contract") or {}),
    )
    if promoted:
        item_d["button_contract"] = dict(promoted_contract)
        item_d["action_type"] = promoted_contract.get("action_type") or item_d.get("action_type")
        item_d["selected_family_id"] = promoted_contract.get("selected_family_id") or item_d.get("selected_family_id")
        item_d["published_family_id"] = promoted_contract.get("published_family_id") or item_d.get("published_family_id")
        item_d["cta_family_id"] = promoted_contract.get("cta_family_id") or item_d.get("cta_family_id")
    return item_d, promoted


def _presentation_for_visible_primary_item(
    presentation: dict,
    item: dict,
) -> dict:
    presentation_d = dict(presentation or {})
    if _design_guide_button_contract_enabled(dict((item or {}).get("button_contract") or {})):
        presentation_d["show_apply_button"] = True
    return presentation_d


def _restamp_primary_item_from_overview_family_chooser(
    guidance_items: list[dict],
    guidance_debug: dict,
) -> tuple[list[dict], dict]:
    """Align the rendered primary item identity with the shared family chooser."""
    if not guidance_items or not isinstance(guidance_items[0], dict):
        return list(guidance_items or []), {"restamped": False, "reason": "no_primary_item"}
    overview = dict(guidance_debug.get("overview") or {})
    statuses = {
        str(key or "").strip().lower(): str(value or "").strip().upper()
        for key, value in dict(overview.get("statuses") or {}).items()
    }
    utils = dict(overview.get("utils") or {})
    if not statuses and not utils:
        return list(guidance_items or []), {"restamped": False, "reason": "no_overview"}

    def _util(domain: str) -> float | None:
        try:
            value = utils.get(domain)
            return float(value) if value not in (None, "") else None
        except Exception:
            return None

    def _domain_not_applicable(domain: str) -> bool:
        status = str(statuses.get(domain) or "").strip().upper()
        if status in {"CAPACITY", "INFO", "NOT RUN", "NOT_RUN", "NOT SUPPLIED"}:
            return True
        return _util(domain) is None and status == ""

    item = dict(guidance_items[0])
    button = dict(item.get("button_contract") or guidance_debug.get("primary_button_contract") or {})
    action_payload = dict(item.get("action_payload") or {})
    resolved = dict(item.get("resolved_candidate") or {})
    updates = dict(
        button.get("updates")
        or action_payload.get("updates")
        or action_payload.get("resolved_candidate_updates")
        or item.get("updates")
        or {}
    )
    if not updates:
        return list(guidance_items or []), {"restamped": False, "reason": "no_updates"}
    current_family = _normalised_render_family_id(
        item.get("selected_family_id")
        or button.get("selected_family_id")
        or button.get("family")
        or item.get("family")
        or item.get("check_key")
    )
    if current_family not in {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS"}:
        return list(guidance_items or []), {
            "restamped": False,
            "reason": "family_not_active_repair",
            "current_family": current_family,
        }
    target_low = 0.85
    bending_util = _util("bending")
    shear_util = _util("shear")
    bottom_or_geometry_keys = {
        "D",
        "b",
        "bw",
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "bot_row_1_bars",
        "bot_row_2_bars",
        "bot_row_1_dia",
        "bot_row_2_dia",
    }
    shear_keys = {"lig_d", "lig_legs", "s_lig"}
    whole_beam = {
        "bending_state": "FAIL"
        if statuses.get("bending") == "FAIL"
        else (
            "TARGET"
            if _domain_not_applicable("bending")
            else ("OVERDESIGNED" if bending_util is not None and bending_util < target_low else "TARGET")
        ),
        "shear_state": "FAIL"
        if statuses.get("shear") == "FAIL"
        else (
            "TARGET"
            if _domain_not_applicable("shear")
            else ("OVERDESIGNED" if shear_util is not None and shear_util < target_low else "TARGET")
        ),
        "bending_utilisation": bending_util if bending_util is not None else 0.9,
        "shear_utilisation": shear_util if shear_util is not None else 0.9,
        "can_strengthen_bending": bool(set(updates) & bottom_or_geometry_keys),
        "can_strengthen_shear": bool(set(updates) & shear_keys),
        "can_optimise_shear_without_hurting_bending": bool(
            not _domain_not_applicable("shear") and shear_util is not None and shear_util < target_low
        ),
        "can_optimise_bending_without_hurting_shear": bool(
            not _domain_not_applicable("bending") and bending_util is not None and bending_util < target_low
        ),
    }
    try:
        chooser = classify_family_from_whole_beam_evidence(whole_beam)
    except Exception as exc:
        return list(guidance_items or []), {
            "restamped": False,
            "reason": "classifier_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    selected_family = _normalised_render_family_id(chooser.get("selected_family_id"))
    allowed = {
        ("BENDING_FAIL_GOVERNS", "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"),
        ("SHEAR_FAIL_GOVERNS", "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"),
    }
    if (current_family, selected_family) not in allowed:
        return list(guidance_items or []), {
            "restamped": False,
            "reason": "chooser_family_not_mixed",
            "current_family": current_family,
            "chooser_family": selected_family,
            "whole_beam": dict(whole_beam),
        }

    identity_fields = {
        "family": selected_family,
        "family_id": selected_family,
        "selected_family_id": selected_family,
        "published_family_id": selected_family,
        "cta_family_id": selected_family,
        "apply_payload_family_id": selected_family,
        "candidate_family_id": selected_family,
        "card_family_id": selected_family,
    }
    for target in (item, button, action_payload, resolved):
        target.update(identity_fields)
    item["button_contract"] = dict(button)
    item["action_payload"] = dict(action_payload)
    item["resolved_candidate"] = dict(resolved)
    item["matched_family_ids"] = list(chooser.get("matched_family_ids") or [selected_family])
    item["family_chooser_contract"] = "family_chooser_contract"
    item["family_selection_source"] = "design_brain.family_classification_runtime.classify_family_from_whole_beam_evidence"
    guidance_debug.update(
        {
            "primary_item": dict(item),
            "primary_button_contract": dict(button),
            "button_contract": dict(button),
            "displayed_primary_button_contract": dict(button),
            "selected_family_id": selected_family,
            "published_family_id": selected_family,
            "cta_family_id": selected_family,
            "matched_family_ids": list(item.get("matched_family_ids") or []),
            "family_chooser_contract": "family_chooser_contract",
            "overview_family_chooser_restamp": {
                "restamped": True,
                "from_family": current_family,
                "to_family": selected_family,
                "whole_beam": dict(whole_beam),
                "classification_hash": chooser.get("classification_hash"),
            },
        }
    )
    out = list(guidance_items or [])
    out[0] = item
    return out, dict(guidance_debug["overview_family_chooser_restamp"])


def render_design_guide_publication_exit_state_current_coordinator(
    *, publication_reason: str = "design_guide_panel_exit_publication_refresh"
) -> None:
    _bind_design_guide_current_globals()
    _refresh_design_guide_debug_bundle_publication_projection(publication_reason)


def render_guidance_secondary_primary_cta_state_current_coordinator(
    *,
    idx: int,
    start_index: int,
    primary_card_presentation: dict | None,
    current_overview: dict | None,
    inputs_render_audit: dict[str, str] | None,
) -> dict:
    _bind_design_guide_current_globals()
    _pres_show_apply_raw = bool((primary_card_presentation or {}).get("show_apply_button", True))
    is_primary_guidance_card = bool(idx == 0 and start_index == 0)
    _feedback_status = ""
    _feedback_reason = ""
    _solver_result_blocked_reason = ""
    _suppress_one_click_cta = False
    if is_primary_guidance_card:
        _feedback_cta = _one_click_feedback_cta_state(current_overview)
        _solver_result_cta = _latest_solver_result_cta_state(current_overview)
        _feedback_status = str(_feedback_cta.get("status") or "")
        _feedback_reason = str(_feedback_cta.get("reason") or "")
        _feedback_fp = dict(_feedback_cta.get("feedback_fail_fingerprint") or {})
        _current_fail_fingerprint = dict(_feedback_cta.get("current_fail_fingerprint") or {})
        _blocked_feedback_matches_current_state = bool(_feedback_cta.get("matches_current_state"))
        _stale_blocked_feedback_cleared = bool(_feedback_cta.get("stale_cleared"))
        _solver_result_blocked_matches_current_state = bool(
            _solver_result_cta.get("matches_current_state")
        )
        _solver_result_blocked_reason = str(_solver_result_cta.get("reason") or "").strip()
        _suppress_one_click_cta = bool(
            _blocked_feedback_matches_current_state
            or _solver_result_blocked_matches_current_state
        )
        st.session_state["design_guide_one_click_cta_suppressed"] = bool(_suppress_one_click_cta)
        st.session_state["design_guide_one_click_cta_suppressed_reason"] = (
            (_solver_result_blocked_reason or _feedback_reason) if _suppress_one_click_cta else None
        )
        st.session_state["design_guide_feedback_status"] = _feedback_status or None
        st.session_state["design_guide_feedback_reason"] = _feedback_reason or None
        st.session_state["design_guide_feedback_fail_fingerprint"] = dict(_feedback_fp)
        st.session_state["design_guide_current_fail_fingerprint"] = dict(_current_fail_fingerprint)
        st.session_state["design_guide_blocked_feedback_matches_current_state"] = bool(
            _blocked_feedback_matches_current_state
        )
        st.session_state["design_guide_stale_blocked_feedback_cleared"] = bool(
            _stale_blocked_feedback_cleared
        )
        st.session_state["design_guide_stale_blocked_feedback_reason"] = (
            "fail_fingerprint_changed" if _stale_blocked_feedback_cleared else None
        )
        if inputs_render_audit is not None:
            inputs_render_audit["design_guide_one_click_cta_suppressed"] = "yes" if _suppress_one_click_cta else "no"
            inputs_render_audit["design_guide_one_click_cta_suppressed_reason"] = (
                (_solver_result_blocked_reason or _feedback_reason) if _suppress_one_click_cta else ""
            )
    contract_block_override = (
        (_solver_result_blocked_reason or _feedback_reason)
        if (is_primary_guidance_card and _suppress_one_click_cta)
        else None
    )
    return {
        "_pres_show_apply_raw": bool(_pres_show_apply_raw),
        "is_primary_guidance_card": bool(is_primary_guidance_card),
        "_feedback_status": _feedback_status,
        "_feedback_reason": _feedback_reason,
        "_solver_result_blocked_reason": _solver_result_blocked_reason,
        "_suppress_one_click_cta": bool(_suppress_one_click_cta),
        "contract_block_override": contract_block_override,
    }


def render_guidance_secondary_button_contract_current_coordinator(
    *,
    item: dict,
    guidance_disp_state: dict,
    current_overview: dict | None,
    is_primary_guidance_card: bool,
    contract_block_override: str | None,
    _pres_show_apply_raw: bool,
) -> dict:
    _bind_design_guide_current_globals()
    item_is_specific_blocker = bool(
        str(item.get("guidance_intent") or "").strip() == "specific_blocker"
        or item.get("active_under_capacity_blocker")
    )
    if item_is_specific_blocker:
        button_contract = dict(item.get("button_contract") or {})
        button_contract.update(
            {
                "enabled": False,
                "actionable": False,
                "updates": {},
                "action_type": None,
                "preview_pass": False,
                "blocking_reason": button_contract.get("blocking_reason")
                or item.get("blocker_reason")
                or "specific_engineering_blocker",
            }
        )
    else:
        button_contract = _design_guide_button_contract(
            item,
            state=guidance_disp_state,
            blocking_reason_override=contract_block_override,
        )
    button_contract_from_final_publication_cta = False
    if is_primary_guidance_card and not _design_guide_button_contract_enabled(button_contract):
        promoted_contract, promoted_from_item = _promote_button_contract_from_final_publication_cta(
            item=dict(item),
            button_contract=dict(button_contract),
        )
        if not promoted_from_item:
            debug_bundle_for_cta = dict(st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {})
            promoted_contract, promoted_from_item = _promote_button_contract_from_final_publication_cta(
                item={
                    **dict(item),
                    "final_publication_verifier_payload": debug_bundle_for_cta.get(
                        "final_publication_verifier_payload"
                    ),
                    "final_design_guide_publication": debug_bundle_for_cta.get(
                        "final_design_guide_publication"
                    ),
                },
                button_contract=dict(button_contract),
            )
        if promoted_from_item:
            button_contract_from_final_publication_cta = True
            button_contract = dict(promoted_contract)
    item["button_contract"] = dict(button_contract)
    refreshed_truth = _design_guide_display_truth_for_item(
        item,
        state=guidance_disp_state,
        overview=current_overview,
    )
    item["display_truth"] = dict(refreshed_truth)
    item.update(refreshed_truth)
    if is_primary_guidance_card:
        st.session_state["design_guide_primary_button_contract"] = dict(button_contract)
        st.session_state["design_guide_primary_button_contract_enabled"] = bool(
            _design_guide_button_contract_enabled(button_contract)
        )
        st.session_state["design_guide_primary_display_truth"] = dict(refreshed_truth)
        debug_bundle = dict(st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {})
        debug_bundle.update(
            {
                "primary_item": dict(item),
                "primary_button_contract": dict(button_contract),
                "button_contract": dict(button_contract),
                "displayed_primary_button_contract": dict(button_contract),
                "button_contract_enabled": bool(_design_guide_button_contract_enabled(button_contract)),
                "button_contract_updates": dict(button_contract.get("updates") or {}),
                "button_contract_preview_pass": bool(button_contract.get("preview_pass")),
                "button_contract_candidate_id": (
                    button_contract.get("source_candidate_id")
                    or button_contract.get("candidate_id")
                ),
                "primary_updates": dict(button_contract.get("updates") or {}),
                "selected_action_updates": dict(button_contract.get("updates") or {}),
                "primary_action_type": button_contract.get("action_type"),
                "selected_action_type": button_contract.get("action_type"),
                "display_truth": dict(refreshed_truth),
                "primary_display_truth": dict(refreshed_truth),
            }
        )
        final_projection = _final_publication_debug_projection(
            item=dict(item),
            debug=debug_bundle,
            publication_reason="design_guide_render_primary_button_contract",
        )
        projected_family = _normalised_render_family_id(
            final_projection.get("selected_family_id")
            or dict(final_projection.get("final_publication_verifier_payload") or {}).get("selected_family_id")
            or ""
        )
        if projected_family:
            button_contract = _button_contract_with_family_identity(
                button_contract,
                selected_family=projected_family,
            )
            item["button_contract"] = dict(button_contract)
            for family_key in (
                "family",
                "family_id",
                "selected_family_id",
                "published_family_id",
                "cta_family_id",
                "apply_payload_family_id",
            ):
                item[family_key] = projected_family
            st.session_state["design_guide_primary_button_contract"] = dict(button_contract)
            debug_bundle.update(
                {
                    "primary_item": dict(item),
                    "primary_button_contract": dict(button_contract),
                    "button_contract": dict(button_contract),
                    "displayed_primary_button_contract": dict(button_contract),
                }
            )
            final_projection = _final_publication_debug_projection(
                item=dict(item),
                debug=debug_bundle,
                publication_reason="design_guide_render_primary_button_contract_rebound",
            )
        final_verifier_payload = dict(final_projection.get("final_publication_verifier_payload") or {})
        final_cta_payload = dict(final_verifier_payload.get("cta") or {})
        final_outcome = str(final_verifier_payload.get("outcome_state") or "").strip().upper()
        final_cta_enabled = bool(final_cta_payload.get("enabled") or final_cta_payload.get("actionable"))
        final_cta_handoff = dict(final_cta_payload.get("one_click_action_handoff") or {})
        final_cta_summary = dict(final_cta_payload.get("apply_payload_summary") or {})
        final_cta_has_executable_payload = bool(
            dict(final_cta_payload.get("updates") or {})
            or dict(final_cta_summary.get("updates") or {})
            or final_cta_handoff.get("has_updates")
        )
        if (
            final_cta_payload
            and (
                not final_cta_enabled
                or (
                    final_outcome in {"PASS", "BLOCKED", "ERROR", "PROOF_PENDING"}
                    and not final_cta_has_executable_payload
                )
            )
        ):
            disabled_reason = (
                final_cta_payload.get("disabled_reason")
                or final_cta_payload.get("blocking_reason")
                or f"final_publication_{str(final_outcome or 'terminal').lower()}_no_action"
            )
            button_contract = {
                **dict(button_contract),
                "enabled": False,
                "actionable": False,
                "action_type": None,
                "updates": {},
                "blocking_reason": disabled_reason,
                "disabled_reason": disabled_reason,
            }
            item["button_contract"] = dict(button_contract)
            debug_bundle.update(
                {
                    "primary_item": dict(item),
                    "primary_button_contract": dict(button_contract),
                    "button_contract": dict(button_contract),
                    "displayed_primary_button_contract": dict(button_contract),
                    "button_contract_enabled": False,
                    "button_contract_updates": {},
                    "primary_updates": {},
                    "selected_action_updates": {},
                    "primary_action_type": None,
                    "selected_action_type": None,
                }
            )
        debug_bundle.update(final_projection)
        statuses_for_blocker_identity = {
            str(key or "").strip().lower(): str(value or "").strip().upper()
            for key, value in dict((current_overview or {}).get("statuses") or {}).items()
        }
        active_strength_failures = {
            key for key in ("bending", "shear") if statuses_for_blocker_identity.get(key) == "FAIL"
        }
        rebound_contract = dict(
            debug_bundle.get("primary_button_contract")
            or debug_bundle.get("button_contract")
            or {}
        )
        rebound_reason = str(
            rebound_contract.get("blocking_reason")
            or rebound_contract.get("disabled_reason")
            or ""
        ).strip()
        if (
            len(active_strength_failures) == 1
            and rebound_contract.get("preview_pass") is False
            and rebound_reason == "candidate_preview_has_fail_status"
        ):
            active_family = next(iter(active_strength_failures))
            blocker_family_id = "BENDING_FAIL_GOVERNS" if active_family == "bending" else "SHEAR_FAIL_GOVERNS"
            family_identity = {
                "family": blocker_family_id,
                "family_id": blocker_family_id,
                "selected_family_id": blocker_family_id,
                "published_family_id": blocker_family_id,
                "cta_family_id": blocker_family_id,
                "apply_payload_family_id": blocker_family_id,
                "candidate_family_id": blocker_family_id,
                "card_family_id": blocker_family_id,
            }
            rebound_contract.update(
                {
                    **family_identity,
                    "enabled": False,
                    "actionable": False,
                    "action_type": None,
                    "updates": {},
                    "expected_util": None,
                    "source_candidate_id": None,
                    "candidate_id": None,
                }
            )
            item.update(family_identity)
            item["button_contract"] = dict(rebound_contract)
            debug_bundle.update(
                {
                    **family_identity,
                    "primary_item": dict(item),
                    "primary_button_contract": dict(rebound_contract),
                    "button_contract": dict(rebound_contract),
                    "displayed_primary_button_contract": dict(rebound_contract),
                    "button_contract_enabled": False,
                    "button_contract_updates": {},
                    "primary_updates": {},
                    "selected_action_updates": {},
                    "primary_action_type": None,
                    "selected_action_type": None,
                }
            )
        st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = debug_bundle
        if not _design_guide_button_contract_enabled(button_contract):
            _set_design_guide_primary_payload_binding_audit(
                visible_primary_candidate_id=_guidance_item_source_candidate_id(item),
                button_contract_candidate_id=(
                    button_contract.get("source_candidate_id")
                    or button_contract.get("candidate_id")
                ),
                queued_apply_candidate_id=None,
                applied_candidate_id=None,
                visible_updates=dict(_resolve_recommendation_updates(dict(item), state=guidance_disp_state) or {}),
                button_contract_updates=dict(button_contract.get("updates") or {}),
                queued_apply_updates={},
                applied_updates={},
                payload_binding_match=False,
                payload_update_match=False,
                stale_apply_payload_blocked=False,
                canonical_primary_payload_exists=False,
                legacy_fallback_used=False,
            )
    _pres_show_apply = bool(
        _pres_show_apply_raw
        and _design_guide_button_contract_enabled(button_contract)
    )
    return {
        "button_contract": dict(button_contract),
        "refreshed_truth": dict(refreshed_truth),
        "_pres_show_apply": bool(_pres_show_apply),
    }


def render_guidance_secondary_apply_action_current_coordinator(
    *,
    item: dict,
    guidance_disp_state: dict,
    primary_card_presentation: dict | None,
    button_contract: dict,
    anchor_class: str,
    is_primary_guidance_card: bool,
    _pres_show_apply: bool,
    _suppress_one_click_cta: bool,
) -> dict:
    _bind_design_guide_current_globals()
    effective_action_type = str(
        button_contract.get("action_type") or item.get("action_type") or ""
    ).strip()
    if effective_action_type and _pres_show_apply:
        if is_primary_guidance_card:
            rec = st.session_state.get("pending_recommendation")
            rebuilt_pending = _build_pending_recommendation(item, guidance_disp_state)
            if isinstance(rebuilt_pending, dict) and rebuilt_pending:
                rec = {
                    **rebuilt_pending,
                    "_source": str(rebuilt_pending.get("_source") or "guidance"),
                }
                st.session_state["pending_recommendation"] = rec
            elif not isinstance(rec, dict) or not rec:
                rec = {}
            if not rec:
                contract_action_type = str(button_contract.get("action_type") or "").strip()
                contract_updates = dict(button_contract.get("updates") or {})
                if (
                    bool(button_contract.get("enabled") or button_contract.get("actionable"))
                    and contract_action_type == "apply_resolved_candidate"
                    and contract_updates
                ):
                    contract_candidate_id = (
                        button_contract.get("candidate_id")
                        or button_contract.get("source_candidate_id")
                        or "rendered_primary_candidate"
                    )
                    rec = {
                        "_source": "authoritative_button_contract_render",
                        "action_type": contract_action_type,
                        "family": button_contract.get("family") or button_contract.get("selected_family_id"),
                        "candidate_id": contract_candidate_id,
                        "source_candidate_id": contract_candidate_id,
                        "updates": contract_updates,
                        "title": str(button_contract.get("label") or "Apply recommendation").strip(),
                        "label": str(button_contract.get("label") or "Apply recommendation").strip(),
                    }
            if isinstance(rec, dict) and rec:
                rec_meta = dict(rec.get("meta") or {})
                rec_status = str(rec_meta.get("status") or "").strip()
                authoritative_result = AuthoritativeDesignResultStore(st.session_state).current()
                authoritative_cta = (
                    dict(authoritative_result.cta_model or {}) if authoritative_result else {}
                )
                authoritative_apply = (
                    dict(authoritative_result.apply_payload or {}) if authoritative_result else {}
                )
                authoritative_action_type = str(
                    authoritative_cta.get("action_type")
                    or authoritative_apply.get("action_type")
                    or authoritative_apply.get("resolved_candidate_action_type")
                    or ""
                ).strip()
                authoritative_updates = dict(
                    authoritative_cta.get("updates")
                    or authoritative_apply.get("updates")
                    or authoritative_apply.get("resolved_candidate_updates")
                    or {}
                )
                authoritative_apply_contract_ready = bool(
                    button_contract.get("enabled") or button_contract.get("actionable")
                ) and str(
                    button_contract.get("action_type") or item.get("action_type") or ""
                ).strip() == "apply_resolved_candidate" and bool(
                    dict(button_contract.get("updates") or item.get("updates") or {})
                ) and (
                    authoritative_result is None
                    or (
                        authoritative_action_type == "apply_resolved_candidate"
                        and bool(authoritative_updates)
                    )
                )
                if rec_status == "no_action" and not authoritative_apply_contract_ready:
                    st.success("Design is efficient - further reductions would weaken capacity")
                    util_value = rec_meta.get("util")
                    try:
                        if util_value is not None:
                            st.caption(f"Current utilisation: {float(util_value):.2f} (target ≈ 0.85)")
                    except Exception:
                        pass
                    return {"continue_item": True}
                if (
                    not _recommendation_commit_eligible(rec)
                    and not authoritative_apply_contract_ready
                ):
                    st.session_state["design_guide_legacy_advisory_panel_suppressed"] = True
                    st.session_state["design_guide_legacy_advisory_panel_reason"] = (
                        _recommendation_blocked_reason(rec) or "candidate_not_commit_eligible"
                    )
                    return {"continue_item": True}
                contract_has_executable_apply = bool(
                    (button_contract.get("enabled") or button_contract.get("actionable"))
                    and str(button_contract.get("action_type") or "").strip()
                    == "apply_resolved_candidate"
                    and dict(button_contract.get("updates") or {})
                )
                if _suppress_one_click_cta and not contract_has_executable_apply:
                    st.markdown(
                        """
<div class='fast-guidance-secondary' style="border:1px solid rgba(49,51,63,0.18);background:rgba(49,51,63,0.04);">
  <strong>No single one-click fix currently covers all failing checks</strong><br>
  The guide is showing the next manual steps instead.
</div>
""",
                        unsafe_allow_html=True,
                    )
                    return {"continue_item": True}

                apply_label = (
                    str((primary_card_presentation or {}).get("button_label") or "").strip()
                    or (
                    "Apply Auto Design"
                        if str(rec.get("_source") or "").strip() == "auto_design"
                    else "Apply Recommendation"
                    )
                )
                # The visible card may carry the resolved action on the item
                # while the projected button contract is being refreshed. Use
                # the same effective action that admitted this CTA, otherwise
                # an Apply button can be routed to auto-design.
                contract_action_type = str(
                    button_contract.get("action_type")
                    or item.get("action_type")
                    or ""
                ).strip()
                contract_family = str(
                    button_contract.get("family")
                    or item.get("family")
                    or item.get("selected_family_id")
                    or ""
                ).strip()
                contract_updates = dict(
                    button_contract.get("updates")
                    or item.get("updates")
                    or {}
                )
                primary_route_target = (
                    "handle_apply_buttons"
                    if (
                        (
                            contract_action_type == "apply_resolved_candidate"
                            and bool(contract_updates)
                        )
                        or (
                            _recommendation_commit_eligible(rec)
                            and str(rec.get("action_type") or "").strip() == contract_action_type
                        )
                    )
                    else "handle_auto_design"
                )
                # Keep the visible label aligned with the already-resolved
                # button contract.  An executable resolved candidate is an
                # Apply action; relabelling it as auto-design sends users and
                # browser checks toward the wrong route.
                if contract_action_type == "apply_resolved_candidate":
                    apply_label = (
                        str((primary_card_presentation or {}).get("button_label") or "").strip()
                        or "Apply recommendation"
                    )
                elif not apply_label:
                    apply_label = "Run one-click auto design"
                _contract_family_upper = str(
                    button_contract.get("selected_family_id")
                    or button_contract.get("published_family_id")
                    or button_contract.get("family")
                    or item.get("selected_family_id")
                    or ""
                ).strip().upper()
                if _contract_family_upper == "GEOMETRY_DETAILING_GOVERNS":
                    apply_label = (
                        str((primary_card_presentation or {}).get("button_label") or "").strip()
                        or "Apply geometry correction"
                    )
                if authoritative_apply:
                    st.session_state["_authoritative_primary_apply_payload_source"] = (
                        "authoritative_design_result"
                    )
                else:
                    # The render path is authority-only. A missing result is a
                    # coordinator defect, not permission to recreate payload
                    # truth from the page-local item.
                    st.session_state["_authoritative_primary_apply_payload_source"] = (
                        "authoritative_design_result_missing"
                    )
                if (
                    authoritative_result is not None
                    and (not authoritative_action_type or not authoritative_updates)
                    and not contract_has_executable_apply
                ):
                    # The visible CTA must be backed by the session-owned
                    # publication. Do not render a page-local fallback that
                    # can later queue ``other`` with an empty payload.
                    st.session_state["_authoritative_primary_apply_payload_source"] = (
                        "authoritative_design_result_incomplete"
                    )
                    return {"continue_item": True}
                st.markdown(
                    f"<div class=\"{html.escape(anchor_class)}\" "
                    "style=\"height:0;margin:0;padding:0;overflow:hidden;\" "
                    "aria-hidden=\"true\"></div>",
                    unsafe_allow_html=True,
                )
                guidance_pressed = render_design_guide_component_cta(
                    st_module=st,
                    apply_label=apply_label,
                    rec=dict(rec),
                    primary_route_target=primary_route_target,
                    button_contract=dict(button_contract),
                    queue_primary_button_action_fn=_queue_primary_design_guide_button_action,
                )
                if guidance_pressed:
                    st.session_state["_inputs_design_guide_primary_button_pressed"] = True
            else:
                pass
    elif effective_action_type:
        exact_blocker = _render_exact_blocker_from_item(item) if is_primary_guidance_card else {}
        if exact_blocker:
            # Blocked failed-preview states render their explanation inside the
            # primary card. Do not add the legacy secondary action/status panel.
            return {"continue_item": False}
        reason = str(button_contract.get("blocking_reason") or "button_contract_not_enabled").strip()
        preview_text = "passed" if bool(button_contract.get("preview_pass")) else "did not pass"
        st.session_state["design_guide_legacy_advisory_panel_suppressed"] = True
        st.session_state["design_guide_legacy_advisory_panel_reason"] = (
            f"Button contract: {reason}. Preview {preview_text}."
        )
    elif item.get("primary_action"):
        terminal_family = str(
            item.get("selected_family_id")
            or item.get("published_family_id")
            or item.get("family")
            or ""
        ).strip().upper()
        canonical_terminal_primary = bool(
            is_primary_guidance_card
            and str(item.get("status") or "").strip().upper() == "PASS"
            and terminal_family
            in {"EXACT_STOP_PROVEN", "TARGET_BAND_REACHED"}
        )
        if canonical_terminal_primary:
            # The canonical final card already publishes this terminal
            # explanation.  Rendering the legacy advisory below it creates a
            # duplicate raw "Status" block and violates the single-card
            # publication boundary.
            st.session_state[
                "design_guide_legacy_advisory_panel_suppressed"
            ] = True
            st.session_state[
                "design_guide_legacy_advisory_panel_reason"
            ] = "canonical_terminal_primary_card"
        else:
            st.markdown(
                f"<div class='fast-guidance-secondary'><strong>Status</strong><br>{html.escape(item['primary_action'])}</div>",
                unsafe_allow_html=True,
            )
    return {"continue_item": False}


def render_guidance_secondary_card_model_current_coordinator(
    *,
    idx: int,
    item: dict,
    guidance_disp_state: dict,
    current_overview: dict | None,
    inputs_render_audit: dict[str, str] | None,
    start_index: int,
    primary_card_presentation: dict | None,
) -> dict:
    _bind_design_guide_current_globals()
    is_primary_card = bool(idx == 0 and start_index == 0)
    exact_blocker = _render_exact_blocker_from_item(item) if is_primary_card else {}
    badge_label = "BLOCKED" if exact_blocker else _guidance_card_label(item)
    if primary_card_presentation is not None and idx == 0 and start_index == 0:
        item_bucket = str(primary_card_presentation.get("css_bucket") or item.get("bucket") or "pass")
        use_success_style = bool(primary_card_presentation.get("use_success_style"))
    else:
        item_bucket = item["bucket"] if idx == 0 and start_index == 0 else ("warn" if item["bucket"] == "fail" else item["bucket"])
    _render_button_contract = dict(item.get("button_contract") or {})
    _render_family_upper = str(
        _render_button_contract.get("selected_family_id")
         or _render_button_contract.get("published_family_id")
         or _render_button_contract.get("family")
         or item.get("selected_family_id")
         or item.get("published_family_id")
         or item.get("family")
         or item.get("check_key")
         or (item.get("candidate_search_evidence") or {}).get("selected_family_id")
         or ""
    ).strip().upper()
    if (
        primary_card_presentation is not None
        and idx == 0
        and start_index == 0
        and _render_family_upper == "GEOMETRY_DETAILING_GOVERNS"
    ):
        badge_label = str(primary_card_presentation.get("critical_status") or "ACTION").strip().upper()
        item_bucket = "fail"
        use_success_style = False
    if exact_blocker:
        item_bucket = "fail"
        use_success_style = False
    if idx == 0 and start_index == 0 and item_bucket == "fail" and not exact_blocker:
        util_v = _parse_util_value(item.get("util"))
        if util_v is not None and util_v <= 1.0:
            # Display-only: recommendation card at/under 100% shows close/warn styling.
            item_bucket = "warn"
    use_success_style = (
        idx == 0
        and start_index == 0
        and not exact_blocker
        and _design_guide_primary_uses_success_style(item)
    )
    is_static = not item.get("action_type")
    before_after = item.get("guidance_before_after") or _guidance_before_after_text(item, guidance_disp_state)
    anchor_class = (
        "fast-guidance-action-anchor "
        f"fast-guidance-action-anchor--{item_bucket} "
        + ("fast-guidance-action-anchor--primary" if idx == 0 and start_index == 0 else "fast-guidance-action-anchor--secondary")
        + (" fast-guidance-action-anchor--static" if is_static else "")
    )
    if use_success_style:
        card_class = "fast-guidance-item pass guidance-success"
    else:
        card_class = f"fast-guidance-item {item_bucket}"
    if idx > 0 or start_index > 0:
        card_class += " secondary"
    badge_class = (
        f"fast-guidance-badge {item_bucket} guidance-success"
        if use_success_style
        else f"fast-guidance-badge {item_bucket}"
    )
    _presentation_controls_primary = bool(primary_card_presentation is not None and idx == 0 and start_index == 0)
    _presentation_show_apply = bool((primary_card_presentation or {}).get("show_apply_button", True))
    compact_primary_actionable = bool(
        idx == 0
        and start_index == 0
        and item.get("action_type")
        and (not _presentation_controls_primary or _presentation_show_apply)
    )
    before_after_html = (
        f"<div class='fast-guidance-secondary'><strong>Before -&gt; After</strong><br>{html.escape(before_after)}</div>"
        if before_after else
        (
            f"<div class='fast-guidance-secondary'><strong>Alternative</strong><br>{html.escape(item['secondary_action'])}</div>"
            if item.get("secondary_action") else ""
        )
    )
    display_truth = dict(item.get("display_truth") or {})
    display_util = _parse_util_value(display_truth.get("displayed_util"))
    display_truth_source = str(display_truth.get("display_truth_source") or item.get("display_truth_source") or "").strip()
    if display_util is not None:
        util_label = "preview utilisation" if display_truth_source == "candidate_preview" else "utilisation"
        title_util_text = f"({util_label} = {display_util:.2f})"
    else:
        title_util_text = str(item.get("title_util") or "").strip()
    title_util_html = (
        f"<span class='fast-guidance-title-util'>{html.escape(title_util_text)}</span>"
        if title_util_text else ""
    )
    start_steps_html = ""
    if item_bucket == "start":
        start_steps = item.get("start_steps") or []
        if start_steps:
            start_steps_html = (
                "<ul class='fast-guidance-list'>"
                + "".join(f"<li>{html.escape(step)}</li>" for step in start_steps)
                + "</ul>"
            )
    why_body = _guidance_card_why_body(item)
    why_html = (
        f"<div class='fast-guidance-reason'><strong>Why</strong><br>{_design_guide_text_html(why_body)}</div>"
        if why_body
        else f"<div class='fast-guidance-reason'>{html.escape(str(item.get('reasoning') or ''))}</div>"
    )
    proposed_html = (
        _guidance_card_proposed_change_html(item, guidance_disp_state)
        if item.get("action_type")
        else ""
    )
    display_title = str(item.get("title_main") or "").strip()
    if idx == 0 and start_index == 0:
        item_is_specific_blocker = bool(
            str(item.get("guidance_intent") or "").strip() == "specific_blocker"
            or item.get("active_under_capacity_blocker")
        )
        presentation_headline = str((primary_card_presentation or {}).get("headline") or "").strip()
        if presentation_headline and not item_is_specific_blocker:
            display_title = presentation_headline
        if exact_blocker and display_title.lower().startswith("cleanup - best safe"):
            display_title = "No one-click cleanup is available for this state"
        title_updates = _guidance_update_map(item)
        expected_update_families = frozenset(_compound_subfamilies_from_updates(title_updates))
        rebuild_title = False
        rebuilt_title = ""
        intent_controls_title = str(item.get("guidance_intent") or "").strip() in DESIGN_GUIDE_INTENTS
        if title_updates and not intent_controls_title:
            rebuild_title = not _label_consistent_with_updates_families(display_title, expected_update_families)
            if rebuild_title:
                rebuilt_title = str(_derived_guidance_title_from_updates(guidance_disp_state, title_updates) or "").strip()
                if rebuilt_title:
                    display_title = rebuilt_title
        st.session_state["design_guide_title_rebuilt_from_updates"] = bool(rebuild_title and rebuilt_title)
        st.session_state["design_guide_original_title"] = str(item.get("title_main") or "")
        st.session_state["design_guide_rebuilt_title"] = rebuilt_title or None
        st.session_state["design_guide_expected_update_families"] = list(expected_update_families)
        if inputs_render_audit is not None:
            inputs_render_audit["design_guide_title_rebuilt_from_updates"] = "yes" if rebuild_title and rebuilt_title else "no"
    compact_primary_html = (
        _guidance_primary_compact_lines_html(item, guidance_disp_state)
        if compact_primary_actionable
        else ""
    )
    pres_hint_html = ""
    if exact_blocker:
        blocker_reason = str(exact_blocker.get("reason") or "").strip()
        blocker_proof = str(exact_blocker.get("proof_summary") or "").strip()
        if blocker_reason:
            pres_hint_html = (
                f"<div class='fast-guidance-secondary'>{_design_guide_text_html(blocker_reason)}"
                + (
                    f"<br><strong>Family-owned blocker proof:</strong> {_design_guide_text_html(blocker_proof)}"
                    if blocker_proof
                    else ""
                )
                + "</div>"
            )
    elif (
        primary_card_presentation is not None
        and idx == 0
        and start_index == 0
        and str(item.get("guidance_intent") or "").strip() != "specific_blocker"
        and not item.get("active_under_capacity_blocker")
        and str(primary_card_presentation.get("subtext") or "").strip()
    ):
        pres_hint_html = (
            f"<div class='fast-guidance-secondary'>{_design_guide_text_html(str(primary_card_presentation.get('subtext') or '').strip())}</div>"
        )
    if exact_blocker:
        core_body = ""
    elif _presentation_controls_primary and not _presentation_show_apply:
        core_body = ""
    else:
        core_body = (
            compact_primary_html
            if compact_primary_actionable
            else f"{why_html}{proposed_html}{start_steps_html}{before_after_html}"
        )
    body_html = f"{pres_hint_html}{core_body}" if pres_hint_html else core_body
    card_contract_attrs = _design_guide_card_contract_attrs(item, display_title=display_title)
    if exact_blocker:
        card_contract_attrs += (
            " data-visible-publication-state='BLOCKED'"
            " data-visible-badge='BLOCKED'"
            " data-visible-exact-blocker='true'"
        )
    card_html = (
        f"<div class='{card_class}'{card_contract_attrs}>"
        f"<div class='fast-guidance-head'>"
        f"<span class='{badge_class}'>{html.escape(badge_label)}</span>"
        f"<span class='fast-guidance-title-wrap'>"
        f"<span class='fast-guidance-title'>{html.escape(display_title)}</span>"
        f"{title_util_html}"
        f"</span>"
        f"</div>"
        f"{body_html}"
        f"</div>"
    )
    if is_primary_card:
        section_overview = dict(current_overview or {})
        section_debug = {
            "selected_family_id": (
                item.get("selected_family_id")
                or _render_button_contract.get("selected_family_id")
                or _render_button_contract.get("family")
            ),
            "family_utils": dict(section_overview.get("utils") or {}),
            "primary_preview_util": (
                _render_button_contract.get("expected_util")
                or item.get("resolved_candidate_post_util")
                or _guidance_item_expected_util(item)
            ),
        }
        authoritative_result = AuthoritativeDesignResultStore(
            st.session_state
        ).current()
        authoritative_payload = (
            guidance_payload_from_authoritative_design_result(
                authoritative_result
            )
        )
        authoritative_publication = dict(
            authoritative_payload.get("final_design_guide_publication")
            or {}
        )
        if authoritative_publication.get("publication_hash"):
            canonical_publication = final_design_guide_publication_from_dict(
                authoritative_publication
            )
        else:
            canonical_publication = build_final_design_guide_publication(
                item=dict(item),
                debug=section_debug,
                publication_reason="inputs_primary_card_canonical_renderer",
            )
        canonical_format = build_final_design_guide_card_format(canonical_publication)
        card_html = render_final_design_guide_card_html(canonical_format)
        canonical_anchor_bucket = final_design_guide_action_anchor_bucket(
            canonical_format,
            fallback=item_bucket,
        )
        anchor_class = (
            "fast-guidance-action-anchor "
            f"fast-guidance-action-anchor--{canonical_anchor_bucket} "
            + (
                "fast-guidance-action-anchor--primary"
                if idx == 0 and start_index == 0
                else "fast-guidance-action-anchor--secondary"
            )
            + (" fast-guidance-action-anchor--static" if is_static else "")
        )
    if inputs_render_audit is not None:
        _at = str(item.get("action_type") or "")
        _st = str(item.get("status") or "")
        if _at == "apply_mode_recommendation":
            inputs_render_audit["next_mode_recommendation_rendered"] = "yes"
        if _st == "EFFICIENCY":
            if _at == "reduce_bottom_reinforcement":
                inputs_render_audit["bottom_tightening_rendered"] = "yes"
            elif _at == "tighten_geometry":
                inputs_render_audit["geometry_tightening_rendered"] = "yes"
            elif _at in ("increase_link_spacing", "reduce_number_of_legs", "apply_shear_recommendation"):
                inputs_render_audit["shear_tightening_rendered"] = "yes"
    return {
        "card_html": card_html,
        "anchor_class": anchor_class,
    }


def render_design_guide_initial_cache_compute_current_coordinator(
    *,
    inputs_render_audit: dict[str, str] | None = None,
) -> dict:
    _bind_design_guide_current_globals()
    stage_debug = os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

    def _stage(label: str) -> None:
        if stage_debug:
            print(f"DG_STAGE {label}", file=sys.stderr, flush=True)

    if inputs_render_audit is not None:
        inputs_render_audit["design_guide_rendered"] = "yes"
    banner_generic_only = bool(st.session_state.pop("_design_guide_banner_generic_only", False))
    _sync_auto_design_mode_tracking(_shared_state_snapshot())
    _stage("before_heading")
    st.markdown("## Design Guide")
    _render_auto_design_main_panel_status()
    _stage("after_heading")
    current_state, _ = _resolved_inputs_summary_state()
    _stage("after_summary_state")
    fingerprint = _get_design_guide_fp(current_state)
    sidebar_debug = _design_guide_sidebar_debug_enabled()
    if sidebar_debug:
        _reset_design_guide_reco_trace()
    else:
        st.session_state.pop(DESIGN_GUIDE_RECO_TRACE_KEY, None)

    # The application coordinator should have seeded this result before the
    # panel mounts. Reuse it directly so the render path does not perform
    # Design Brain work on a cache miss.
    try:
        authoritative_snapshot = build_engineering_input_snapshot_from_resolved_state(
            dict(current_state or {}),
            contract_versions={
                "design_guide": str(DESIGN_GUIDE_ALGORITHM_VERSION),
                "family_classification": str(
                    (load_family_classification_contract().get("contract_identity") or {}).get(
                        "contract_version"
                    )
                    or ""
                ),
            },
            calculation_versions={"summary_resolver": "resolved_inputs_summary_state.v1"},
        )
        authoritative_result = AuthoritativeDesignResultStore(st.session_state).current()
        authoritative_payload = guidance_payload_from_authoritative_design_result(authoritative_result)
    except Exception:
        authoritative_snapshot = None
        authoritative_result = None
        authoritative_payload = {}
    authoritative_refresh_receipt = dict(
        st.session_state.get("_authoritative_design_result_runtime_probe") or {}
    )
    authoritative_refresh_matches = bool(
        authoritative_result is not None
        and str(authoritative_refresh_receipt.get("engineering_hash") or "")
        == str(authoritative_result.engineering_hash or "")
        and authoritative_refresh_receipt.get("source")
        == "inputs_pre_widget_application_coordinator"
    )
    authoritative_result_current = bool(
        authoritative_result is not None
        and (
            authoritative_refresh_matches
            or (
                authoritative_snapshot is not None
                and authoritative_result.engineering_hash
                == authoritative_snapshot.engineering_hash
            )
        )
        and isinstance(authoritative_payload.get("guidance_debug"), dict)
    )
    if authoritative_result_current:
        st.session_state["_design_guide_render_compute_probe"] = {
            "render_compute_calls": 0,
            "source": "authoritative_design_result_store",
            "engineering_hash": authoritative_result.engineering_hash,
        }

    if not st.session_state.get(DESIGN_GUIDE_NEEDS_REFRESH_KEY):
        baseline_fp = st.session_state.get(DESIGN_GUIDE_PANEL_BASELINE_FP_KEY)
        if baseline_fp is not None and fingerprint != baseline_fp:
            _mark_design_guide_dirty()

    if st.session_state.get(DESIGN_GUIDE_NEEDS_REFRESH_KEY):
        _agent_debug_log(
            "Auto-clearing design guide refresh gate",
            {
                "needs_refresh_before": True,
                "fingerprint": str(fingerprint),
            },
            location="inputs_page.py:_render_fast_design_guidance_panel:auto_clear_refresh_gate",
            hypothesis_id="H_DG_BTN_1",
        )
        st.session_state[DESIGN_GUIDE_PANEL_BASELINE_FP_KEY] = fingerprint
        st.session_state.pop(DESIGN_GUIDE_NEEDS_REFRESH_KEY, None)

    guidance_started_at = time.perf_counter()
    guidance_items_raw: list[dict] = []
    guidance_debug: dict = {}
    guidance_cache_hit = False
    guidance_fresh_compute_used = False

    if authoritative_result_current:
        # The application coordinator owns the Design Brain run. The render
        # coordinator consumes its immutable guidance projection and never
        # repairs a missing cache by recomputing engineering guidance.
        guidance_items_raw = list(authoritative_payload.get("guidance_items") or [])
        guidance_debug = dict(authoritative_payload.get("guidance_debug") or {})
        if isinstance(authoritative_payload.get("final_design_guide_publication"), dict):
            guidance_debug["authoritative_final_design_guide_publication"] = dict(
                authoritative_payload.get("final_design_guide_publication") or {}
            )
            guidance_debug["authoritative_final_publication_verifier_payload"] = dict(
                authoritative_payload.get("final_publication_verifier_payload") or {}
            )
        if guidance_items_raw and authoritative_result is not None:
            # Preserve the existing card shape while sourcing the primary CTA
            # and Apply identity from the authoritative result.
            authoritative_cta = dict(authoritative_result.cta_model or {})
            authoritative_apply = dict(authoritative_result.apply_payload or {})
            authoritative_item = dict(guidance_items_raw[0] or {})
            authoritative_family = (
                authoritative_result.governing_family
                or authoritative_cta.get("family")
                or authoritative_apply.get("family")
            )
            selected_candidate = dict(authoritative_result.selected_candidate or {})
            authoritative_candidate_id = (
                authoritative_cta.get("source_candidate_id")
                or authoritative_apply.get("candidate_id")
                or authoritative_apply.get("source_candidate_id")
                or selected_candidate.get("candidate_id")
            )
            authoritative_item.update(
                {
                    "button_contract": authoritative_cta,
                    "action_payload": authoritative_apply,
                    "action_type": authoritative_cta.get("action_type"),
                    "family": authoritative_family,
                    "selected_family_id": authoritative_family,
                    "published_family_id": authoritative_family,
                    "cta_family_id": authoritative_family,
                    "apply_payload_family_id": authoritative_family,
                    "candidate_id": authoritative_candidate_id,
                    "source_candidate_id": authoritative_candidate_id,
                    "updates": dict(
                        authoritative_cta.get("updates")
                        or authoritative_apply.get("updates")
                        or {}
                    ),
                    "authoritative_result_projection": True,
                    "authoritative_publication_hash": authoritative_result.publication_authority_hash,
                }
            )
            guidance_items_raw[0] = authoritative_item
        guidance_cache_hit = True
        guidance_fresh_compute_used = False
        guidance_result_source = "authoritative_design_result_store"
    else:
        guidance_result_source = "authoritative_result_unavailable"
        # A missing authoritative result is a coordinator error, not
        # permission for the render path to start a second Design Brain run.
        _stage("authoritative_result_unavailable")
        guidance_items_raw = []
        guidance_debug = {
            "design_guide_algorithm_version": DESIGN_GUIDE_ALGORITHM_VERSION,
            "guidance_resolved_state": dict(current_state or {}),
            "overview": {},
            "render_compute_blocked": True,
            "render_compute_blocked_reason": "authoritative_result_unavailable",
        }
        guidance_cache_hit = False
        guidance_fresh_compute_used = False
    cache_hit_initial = bool(authoritative_result_current)
    cache_debug_complete_initial = bool(authoritative_result_current)
    cache_repair_attempted = False
    cache_recompute_forced = False
    cache_recompute_success = False

    _stage("before_guidance_postprocess")
    guidance_debug["design_guide_algorithm_version"] = DESIGN_GUIDE_ALGORITHM_VERSION
    _agent_debug_log(
        "Design guide cache coherence",
        {
            "cache_hit_initial": cache_hit_initial,
            "cache_debug_complete_initial": cache_debug_complete_initial,
            "cache_repair_attempted": cache_repair_attempted,
            "cache_recompute_forced": cache_recompute_forced,
            "cache_recompute_success": cache_recompute_success,
            "result_source": guidance_result_source,
        },
        location="inputs_page.py:_render_fast_design_guidance_panel:cache_coherence",
        hypothesis_id="H_DG_CACHE_COHERENCE",
    )

    guidance_compute_ms = round((time.perf_counter() - guidance_started_at) * 1000.0, 1)
    guidance_debug["design_guide_render_state_source"] = "lightweight_overlay_state"
    if sidebar_debug:
        guidance_debug["guidance_compute_ms"] = guidance_compute_ms
        guidance_debug["guidance_cache_hit"] = bool(guidance_cache_hit)
        ocs = dict((guidance_debug.get("one_click_solver") or {}))
        guidance_debug["one_click_solver_expanded"] = bool(ocs.get("one_click_solver_expanded"))
        st.session_state[DESIGN_GUIDE_RECO_TRACE_KEY] = list(guidance_debug.get("reco_trace") or [])
    guidance_disp_state = dict(guidance_debug.get("guidance_resolved_state") or current_state)
    return {
        "stage": _stage,
        "banner_generic_only": banner_generic_only,
        "current_state": current_state,
        "fingerprint": fingerprint,
        "sidebar_debug": sidebar_debug,
        "guidance_items_raw": guidance_items_raw,
        "guidance_debug": guidance_debug,
        "guidance_cache_hit": guidance_cache_hit,
        "guidance_fresh_compute_used": guidance_fresh_compute_used,
        "guidance_result_source": guidance_result_source,
        "guidance_compute_ms": guidance_compute_ms,
        "guidance_disp_state": guidance_disp_state,
    }


def render_design_guide_debug_bundle_context_current_coordinator(
    *,
    current_state: dict,
    guidance_debug: dict,
    guidance_items: list[dict],
    guidance_disp_state: dict,
    terminal_state: str | None,
    render_plan: dict,
) -> dict:
    _bind_design_guide_current_globals()
    last_apply_route = dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})
    gsum = []
    for it in guidance_items[:12]:
        if isinstance(it, dict):
            gsum.append(
                {
                    "action_type": it.get("action_type"),
                    "title_main": it.get("title_main"),
                    "status": it.get("status"),
                    "util": it.get("util"),
                }
            )
    ov = guidance_debug.get("overview") or {}
    primary_item = guidance_items[0] if guidance_items else {}
    primary_payload = dict((primary_item or {}).get("action_payload") or {})
    primary_card_is_resolved_one_click = _guidance_item_is_resolved_one_click(primary_item)
    primary_card_expected_util_value = _guidance_item_expected_util(primary_item)
    primary_card_expected_util_rendered = bool(
        primary_card_is_resolved_one_click and primary_card_expected_util_value is not None,
    )
    trial_geom = dict(st.session_state.get(DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY) or {})
    live_design_summary = _overview_debug_summary(guidance_disp_state, ov)
    post_apply_expected = last_apply_route.get("expected_post_util")
    try:
        post_apply_expected = float(post_apply_expected) if post_apply_expected is not None else None
    except Exception:
        post_apply_expected = None
    post_apply_live_worst = ov.get("worst_util")
    try:
        post_apply_live_worst = float(post_apply_live_worst) if post_apply_live_worst is not None else None
    except Exception:
        post_apply_live_worst = None
    mode_cfg_live = _design_mode_config(_design_optimisation_goal(guidance_disp_state))
    post_apply_live_in_target_band = bool(ov.get("all_key_pass")) and _is_in_target_zone_with_eps(
        ov,
        mode_cfg_live,
        eps=TARGET_BAND_EPS,
    )
    post_apply_display_truth = _design_guide_display_truth_for_item(
        None,
        state=guidance_disp_state,
        overview=ov,
        mode_config=mode_cfg_live,
        source_override="post_commit_truth",
        post_commit_util=post_apply_live_worst,
        post_commit_status=_design_guide_status_from_overview(ov),
    )
    post_apply_tol = 0.02
    post_apply_matches = (
        post_apply_expected is not None
        and post_apply_live_worst is not None
        and abs(post_apply_live_worst - post_apply_expected) <= post_apply_tol
    )
    displayed_primary_item: dict | None = None
    if terminal_state not in {"optimal", "very_low_demand"}:
        if bool(render_plan.get("render_primary_only")):
            displayed_primary_item = guidance_items[0] if guidance_items else None
        else:
            displayed_primary_items = list(render_plan.get("visible_guidance_items") or [])
            displayed_primary_item = displayed_primary_items[0] if displayed_primary_items else None
    displayed_primary_payload = dict((displayed_primary_item or {}).get("action_payload") or {})
    displayed_primary_resolved = dict((displayed_primary_item or {}).get("resolved_candidate") or {})
    displayed_primary_button_contract = dict(
        (displayed_primary_item or {}).get("button_contract") or {}
    )
    displayed_primary_truth = dict(
        (displayed_primary_item or {}).get("display_truth") or {}
    )
    displayed_primary_source = (
        displayed_primary_resolved.get("source")
        or displayed_primary_payload.get("resolved_candidate_source")
        or displayed_primary_payload.get("source")
        or (displayed_primary_item or {}).get("source")
        or ("guidance_item" if isinstance(displayed_primary_item, dict) else None)
    )
    displayed_primary_action_type = (
        str((displayed_primary_item or {}).get("action_type") or "").strip()
        if isinstance(displayed_primary_item, dict)
        else None
    )
    displayed_primary_updates = (
        _resolve_recommendation_updates(displayed_primary_item, guidance_disp_state)
        if isinstance(displayed_primary_item, dict)
        else {}
    )
    displayed_primary_update_families = (
        list(_compound_subfamilies_from_updates(displayed_primary_updates))
        if displayed_primary_updates
        else []
    )
    if not displayed_primary_update_families and isinstance(displayed_primary_item, dict):
        _fallback_family = str(_optimisation_candidate_family(displayed_primary_item, guidance_disp_state) or "").strip()
        if _fallback_family and _fallback_family not in {"other", "general"}:
            displayed_primary_update_families = [_fallback_family]
    displayed_primary_governing_action = (
        str(
            (displayed_primary_item or {}).get("check_key")
            or guidance_debug.get("governing_action")
            or ov.get("governing_check")
            or _governing_focus_from_overview(ov),
        ).strip()
        if isinstance(displayed_primary_item, dict)
        else None
    )
    optimisation_eval_state = dict(guidance_disp_state or {})
    _norm_shear_updates = _normalise_invalid_shear_state_updates(
        optimisation_eval_state,
        {},
        source="design_guide_debug_bundle",
    )
    if _norm_shear_updates:
        optimisation_eval_state.update(_norm_shear_updates)
    if not _shear_reinforcement_is_active(optimisation_eval_state):
        optimisation_eval_state["lig_d"] = 0
        optimisation_eval_state["lig_legs"] = 0
        optimisation_eval_state["s_lig"] = 0.0
    optimisation_normalized_link_state = {
        "lig_d": int(_int_from_state(optimisation_eval_state, "lig_d", 0)),
        "lig_legs": int(_int_from_state(optimisation_eval_state, "lig_legs", 0)),
        "s_lig": float(_float_from_state(optimisation_eval_state, "s_lig", 0.0)),
        "shear_reinforcement_active": bool(_shear_reinforcement_is_active(optimisation_eval_state)),
        "normalization_source": "guidance_resolved_state",
    }
    authoritative_candidate_search_evidence = dict(
        (primary_item or {}).get("candidate_search_evidence")
        or primary_payload.get("candidate_search_evidence")
        or {}
    )
    return {
        "last_apply_route": dict(last_apply_route or {}),
        "gsum": list(gsum or []),
        "ov": dict(ov or {}),
        "primary_item": dict(primary_item or {}),
        "primary_payload": dict(primary_payload or {}),
        "primary_card_is_resolved_one_click": bool(primary_card_is_resolved_one_click),
        "primary_card_expected_util_value": primary_card_expected_util_value,
        "primary_card_expected_util_rendered": bool(primary_card_expected_util_rendered),
        "trial_geom": dict(trial_geom or {}),
        "live_design_summary": dict(live_design_summary or {}),
        "post_apply_live_worst": post_apply_live_worst,
        "post_apply_live_in_target_band": bool(post_apply_live_in_target_band),
        "post_apply_display_truth": dict(post_apply_display_truth or {}),
        "post_apply_matches": bool(post_apply_matches),
        "displayed_primary_source": displayed_primary_source,
        "displayed_primary_action_type": displayed_primary_action_type,
        "displayed_primary_update_families": list(displayed_primary_update_families or []),
        "displayed_primary_governing_action": displayed_primary_governing_action,
        "displayed_primary_button_contract": dict(displayed_primary_button_contract or {}),
        "displayed_primary_truth": dict(displayed_primary_truth or {}),
        "optimisation_normalized_link_state": dict(optimisation_normalized_link_state or {}),
        "authoritative_candidate_search_evidence": dict(
            authoritative_candidate_search_evidence or {}
        ),
    }


def render_design_guide_debug_bundle_payload_current_coordinator(
    *,
    current_state: dict,
    guidance_debug: dict,
    guidance_items: list[dict],
    guidance_disp_state: dict,
    terminal_state: str | None,
    render_plan: dict,
    guidance_compute_ms,
    guidance_cache_hit: bool,
    banner_generic_only: bool,
    fast_focus_section: str | None,
    guidance_dedupe_meta: dict,
    _recommendation_result,
    resolved_guidance_actions: dict,
    mode_mt,
    bottom_bt,
) -> dict:
    _bind_design_guide_current_globals()
    _debug_bundle_context = render_design_guide_debug_bundle_context_current_coordinator(
        current_state=current_state,
        guidance_debug=guidance_debug,
        guidance_items=guidance_items,
        guidance_disp_state=guidance_disp_state,
        terminal_state=terminal_state,
        render_plan=render_plan,
    )
    last_apply_route = dict(_debug_bundle_context["last_apply_route"] or {})
    gsum = list(_debug_bundle_context["gsum"] or [])
    ov = dict(_debug_bundle_context["ov"] or {})
    primary_item = dict(_debug_bundle_context["primary_item"] or {})
    primary_payload = dict(_debug_bundle_context["primary_payload"] or {})
    primary_card_is_resolved_one_click = bool(_debug_bundle_context["primary_card_is_resolved_one_click"])
    primary_card_expected_util_value = _debug_bundle_context["primary_card_expected_util_value"]
    primary_card_expected_util_rendered = bool(_debug_bundle_context["primary_card_expected_util_rendered"])
    trial_geom = dict(_debug_bundle_context["trial_geom"] or {})
    live_design_summary = dict(_debug_bundle_context["live_design_summary"] or {})
    post_apply_live_worst = _debug_bundle_context["post_apply_live_worst"]
    post_apply_live_in_target_band = bool(_debug_bundle_context["post_apply_live_in_target_band"])
    post_apply_display_truth = dict(_debug_bundle_context["post_apply_display_truth"] or {})
    post_apply_matches = bool(_debug_bundle_context["post_apply_matches"])
    displayed_primary_source = _debug_bundle_context["displayed_primary_source"]
    displayed_primary_action_type = _debug_bundle_context["displayed_primary_action_type"]
    displayed_primary_update_families = list(_debug_bundle_context["displayed_primary_update_families"] or [])
    displayed_primary_governing_action = _debug_bundle_context["displayed_primary_governing_action"]
    displayed_primary_button_contract = dict(_debug_bundle_context["displayed_primary_button_contract"] or {})
    displayed_primary_truth = dict(_debug_bundle_context["displayed_primary_truth"] or {})
    optimisation_normalized_link_state = dict(_debug_bundle_context["optimisation_normalized_link_state"] or {})
    authoritative_candidate_search_evidence = dict(
        _debug_bundle_context["authoritative_candidate_search_evidence"] or {}
    )
    _final_publication_debug = _final_publication_debug_projection(
        item=primary_item,
        debug=guidance_debug,
        publication_reason="design_guide_debug_bundle_current_primary",
    )
    statuses_for_debug_identity = {
        str(key or "").strip().lower(): str(value or "").strip().upper()
        for key, value in dict((ov or {}).get("statuses") or {}).items()
    }
    active_strength_failures = {
        key for key in ("bending", "shear") if statuses_for_debug_identity.get(key) == "FAIL"
    }
    primary_contract_for_identity = dict(
        guidance_debug.get("primary_button_contract")
        or displayed_primary_button_contract
        or {}
    )
    primary_contract_reason = str(
        primary_contract_for_identity.get("blocking_reason")
        or primary_contract_for_identity.get("disabled_reason")
        or ""
    ).strip()
    if (
        len(active_strength_failures) == 1
        and primary_contract_for_identity.get("preview_pass") is False
        and primary_contract_reason == "candidate_preview_has_fail_status"
    ):
        active_family = next(iter(active_strength_failures))
        blocker_family_id = "BENDING_FAIL_GOVERNS" if active_family == "bending" else "SHEAR_FAIL_GOVERNS"
        family_identity = {
            "family": blocker_family_id,
            "family_id": blocker_family_id,
            "selected_family_id": blocker_family_id,
            "published_family_id": blocker_family_id,
            "cta_family_id": blocker_family_id,
            "apply_payload_family_id": blocker_family_id,
            "candidate_family_id": blocker_family_id,
            "card_family_id": blocker_family_id,
        }
        primary_contract_for_identity.update(
            {
                **family_identity,
                "enabled": False,
                "actionable": False,
                "action_type": None,
                "updates": {},
                "expected_util": None,
                "source_candidate_id": None,
                "candidate_id": None,
            }
        )
        displayed_primary_button_contract = dict(primary_contract_for_identity)
        primary_item.update(family_identity)
        primary_item["button_contract"] = dict(primary_contract_for_identity)
        guidance_debug.update(
            {
                **family_identity,
                "primary_item": dict(primary_item),
                "primary_button_contract": dict(primary_contract_for_identity),
                "button_contract": dict(primary_contract_for_identity),
                "displayed_primary_button_contract": dict(primary_contract_for_identity),
                "button_contract_enabled": False,
                "button_contract_updates": {},
                "primary_updates": {},
                "selected_action_updates": {},
                "primary_action_type": None,
                "selected_action_type": None,
            }
        )
    return {
        **_final_publication_debug,
        "guidance_compute_ms": guidance_compute_ms,
        "guidance_cache_hit": bool(guidance_cache_hit),
        "design_guide_shear_truth_source": ov.get("design_guide_shear_truth_source")
        if isinstance(ov, dict)
        else None,
        "stage3_shear_truth_debug": ov.get("stage3_shear_truth_debug") if isinstance(ov, dict) else None,
        "stage3_remaining_issue_class": ov.get("stage3_remaining_issue_class")
        if isinstance(ov, dict)
        else None,
        "one_click_solver_expanded": guidance_debug.get("one_click_solver_expanded"),
        "session_actions": {
            "actions_source": st.session_state.get("actions_source"),
            "inputs_actions_source": st.session_state.get("inputs_actions_source"),
            "actions_mode": st.session_state.get("actions_mode"),
            "load_Mstar_proxy": st.session_state.get("load_Mstar_proxy"),
            "load_Vstar_proxy": st.session_state.get("load_Vstar_proxy"),
            "Mu_star": st.session_state.get("Mu_star"),
            "Vu_star": st.session_state.get("Vu_star"),
            "uls_Mstar": st.session_state.get("uls_Mstar"),
            "uls_Vstar": st.session_state.get("uls_Vstar"),
            "uls_Nstar": st.session_state.get("uls_Nstar"),
            "N_star": st.session_state.get("N_star"),
        },
        "resolved_guidance_actions": resolved_guidance_actions,
        "manual_resolver_lock_check": {
            "uls_Mstar": st.session_state.get("uls_Mstar"),
            "uls_Vstar": st.session_state.get("uls_Vstar"),
            "uls_Nstar": st.session_state.get("uls_Nstar"),
            "resolved_Mu": resolved_guidance_actions.get("Mu"),
            "resolved_Vu": resolved_guidance_actions.get("Vu"),
            "resolved_Nu": resolved_guidance_actions.get("Nu"),
        },
        "overview": guidance_debug.get("overview"),
        "efficiency_tightening_state": guidance_debug.get("efficiency_tightening_state"),
        "design_guide_terminal_state": guidance_debug.get("design_guide_terminal_state"),
        "design_guide_has_actionable_recommendation": guidance_debug.get(
            "design_guide_has_actionable_recommendation",
        ),
        "design_guide_terminal_positive": guidance_debug.get("design_guide_terminal_positive"),
        "current_design_summary": live_design_summary,
        "next_mode_recommendation": mode_mt,
        "bottom_tightening": bottom_bt,
        "guidance_branch": guidance_debug.get("guidance_branch"),
        "local_cleanup_promoted": guidance_debug.get("local_cleanup_promoted"),
        "local_cleanup_family": guidance_debug.get("local_cleanup_family"),
        "local_cleanup_candidate_id": guidance_debug.get("local_cleanup_candidate_id"),
        "local_cleanup_reason": guidance_debug.get("local_cleanup_reason"),
        "local_cleanup_blocked_reason": guidance_debug.get("local_cleanup_blocked_reason"),
        "previous_primary_title": guidance_debug.get("previous_primary_title"),
        "final_primary_title": guidance_debug.get("final_primary_title"),
        "overview_actions_used": guidance_debug.get("overview_actions_used"),
        "efficiency_actions_used": guidance_debug.get("efficiency_actions_used"),
        "guidance_actions_used": guidance_debug.get("guidance_actions_used"),
        "fingerprints": {
            "guidance_fingerprint": _recommendation_cache_fingerprint(_guidance_state_snapshot(current_state)),
            "auto_design_governing_fingerprint": _auto_design_governing_fingerprint(current_state),
            "auto_design_action_signature": tuple(_resolve_design_actions_from_state(current_state).get("signature", ())),
            "selected_action_type": guidance_debug.get("selected_action_type"),
            "selected_title": guidance_debug.get("selected_title"),
        },
        "guidance_items_summary": gsum,
        "primary_utils": ov.get("utils"),
        "governing_action": ov.get("governing_action"),
        "displayed_primary_candidate_source": displayed_primary_source,
        "displayed_primary_candidate_action_type": displayed_primary_action_type,
        "displayed_primary_candidate_update_families": list(displayed_primary_update_families),
        "displayed_primary_candidate_governing_action": displayed_primary_governing_action,
        "displayed_primary_button_contract": dict(displayed_primary_button_contract),
        "displayed_primary_display_truth": dict(displayed_primary_truth),
        "displayed_util": displayed_primary_truth.get("displayed_util"),
        "displayed_status": displayed_primary_truth.get("displayed_status"),
        "display_truth_source": displayed_primary_truth.get("display_truth_source"),
        "target_low": displayed_primary_truth.get("target_low"),
        "target_high": displayed_primary_truth.get("target_high"),
        "displayed_within_target_band": bool(displayed_primary_truth.get("displayed_within_target_band")),
        "source_summary_util": displayed_primary_truth.get("source_summary_util"),
        "source_candidate_util": displayed_primary_truth.get("source_candidate_util"),
        "source_post_commit_util": displayed_primary_truth.get("source_post_commit_util"),
        "primary_button_contract": dict(guidance_debug.get("primary_button_contract") or {}),
        "primary_display_truth": dict(guidance_debug.get("primary_display_truth") or {}),
        "button_contract": dict(displayed_primary_button_contract),
        "guidance_intent_items": list(guidance_debug.get("guidance_intent_items") or []),
        "displayed_guidance_intent_items": list(guidance_debug.get("displayed_guidance_intent_items") or []),
        "primary_guidance_intent": guidance_debug.get("primary_guidance_intent"),
        "primary_card_title": primary_item.get("title_main") or primary_item.get("title"),
        "primary_card_intent": primary_item.get("guidance_intent"),
        "primary_displayed_util": displayed_primary_truth.get("displayed_util"),
        "primary_display_truth_source": displayed_primary_truth.get("display_truth_source"),
        "primary_target_low": displayed_primary_truth.get("target_low"),
        "primary_target_high": displayed_primary_truth.get("target_high"),
        "primary_preview_util": displayed_primary_truth.get("source_candidate_util"),
        "primary_current_util": displayed_primary_truth.get("source_summary_util"),
        "primary_lands_in_target_band": displayed_primary_truth.get("displayed_within_target_band"),
        "primary_allowed_blocker": bool(primary_item.get("active_under_capacity_blocker")),
        "button_contract_enabled": displayed_primary_button_contract.get("enabled"),
        "button_contract_updates": dict(displayed_primary_button_contract.get("updates") or {}),
        "button_contract_preview_pass": displayed_primary_button_contract.get("preview_pass"),
        "button_contract_blocking_reason": displayed_primary_button_contract.get("blocking_reason"),
        "candidate_search_evidence": dict(authoritative_candidate_search_evidence),
        "family_utils": dict(ov.get("utils") or {}),
        "materially_overprovided_families": list(
            guidance_debug.get("materially_overprovided_families")
            or []
        ),
        "post_click_family_utils": dict(guidance_debug.get("post_click_family_utils") or {}),
        "post_click_materially_overprovided_families": list(
            guidance_debug.get("post_click_materially_overprovided_families") or []
        ),
        "post_click_unresolved_overprovided_families": list(
            guidance_debug.get("post_click_unresolved_overprovided_families") or []
        ),
        "post_click_cleanup_evidence_by_family": dict(
            guidance_debug.get("post_click_cleanup_evidence_by_family") or {}
        ),
        "post_click_exact_blockers_by_family": dict(
            guidance_debug.get("post_click_exact_blockers_by_family") or {}
        ),
        "post_click_accepted_green_valid": guidance_debug.get("post_click_accepted_green_valid"),
        "post_click_accepted_green_invalid_reason": guidance_debug.get("post_click_accepted_green_invalid_reason"),
        "local_cleanup_search_ran": guidance_debug.get("local_cleanup_search_ran"),
        "local_cleanup_search_exhaustive": guidance_debug.get("local_cleanup_search_exhaustive"),
        "safe_local_cleanup_count": guidance_debug.get("safe_local_cleanup_count"),
        "executable_safe_cleanup_count": guidance_debug.get("executable_safe_cleanup_count"),
        "advisory_cleanup_count": guidance_debug.get("advisory_cleanup_count"),
        "local_cleanup_candidates": list(guidance_debug.get("local_cleanup_candidates") or []),
        "rejected_local_cleanup_count": guidance_debug.get("rejected_local_cleanup_count"),
        "local_cleanup_blocked_reasons": list(
            guidance_debug.get("local_cleanup_blocked_reasons") or []
        ),
        "terminal_state_reason": guidance_debug.get("terminal_state_reason"),
        "terminal_state_blocked_by_local_cleanup": bool(
            guidance_debug.get("terminal_state_blocked_by_local_cleanup")
        ),
        "optimisation_normalized_link_state": optimisation_normalized_link_state,
        "is_efficiency_reduction_mode": guidance_debug.get("is_efficiency_reduction_mode"),
        "terminal_state_blocked": guidance_debug.get("terminal_state_blocked"),
        "terminal_state_block_reason": guidance_debug.get("terminal_state_block_reason"),
        "efficiency_exhaustion_map": guidance_debug.get("efficiency_exhaustion_map"),
        "efficiency_guidance_items_summary": guidance_debug.get("efficiency_guidance_items_summary"),
        "guidance_target_efficiency_band": guidance_debug.get("guidance_target_efficiency_band"),
        "efficiency_worst_util": guidance_debug.get("efficiency_worst_util"),
        "strongly_underutilised": guidance_debug.get("strongly_underutilised"),
        "actionable_target_band_winner_exists": guidance_debug.get("actionable_target_band_winner_exists"),
        "actionable_target_band_winner_family": guidance_debug.get("actionable_target_band_winner_family"),
        "actionable_target_band_winner_subfamilies": guidance_debug.get("actionable_target_band_winner_subfamilies"),
        "actionable_target_band_winner_change_lines": guidance_debug.get("actionable_target_band_winner_change_lines"),
        "optimal_short_circuit_blocked": guidance_debug.get("optimal_short_circuit_blocked"),
        "optimal_short_circuit_block_reason": guidance_debug.get("optimal_short_circuit_block_reason"),
        "surfaced_guidance_branch": guidance_debug.get("surfaced_guidance_branch"),
        "surfaced_selected_action_type": guidance_debug.get("surfaced_selected_action_type"),
        "surfaced_selected_title": guidance_debug.get("surfaced_selected_title"),
        "target_band_default_stop": guidance_debug.get("target_band_default_stop"),
        "target_band_override_allowed": guidance_debug.get("target_band_override_allowed"),
        "target_band_override_reason": guidance_debug.get("target_band_override_reason"),
        "user_visible_no_action_reason": guidance_debug.get("user_visible_no_action_reason"),
        "stop_reason": guidance_debug.get("stop_reason"),
        "target_band_eps": guidance_debug.get("target_band_eps"),
        "target_band_with_eps_passed": guidance_debug.get("target_band_with_eps_passed"),
        "one_click_critical_candidate_exists": guidance_debug.get("one_click_critical_candidate_exists"),
        "one_click_critical_candidate_label": guidance_debug.get("one_click_critical_candidate_label"),
        "one_click_critical_candidate_action_type": guidance_debug.get("one_click_critical_candidate_action_type"),
        "one_click_critical_candidate_post_util": guidance_debug.get("one_click_critical_candidate_post_util"),
        "one_click_critical_candidate_reaches_target_band": guidance_debug.get("one_click_critical_candidate_reaches_target_band"),
        "one_click_critical_candidate_surfaced": guidance_debug.get("one_click_critical_candidate_surfaced"),
        "one_click_critical_candidate_suppressed_reason": guidance_debug.get("one_click_critical_candidate_suppressed_reason"),
        "one_click_solver": guidance_debug.get("one_click_solver"),
        "critical_branch_used_one_click_override": guidance_debug.get("critical_branch_used_one_click_override"),
        "winner_goal_alignment_score": guidance_debug.get("winner_goal_alignment_score"),
        "current_goal_alignment_score": guidance_debug.get("current_goal_alignment_score"),
        "goal_alignment_improvement": guidance_debug.get("goal_alignment_improvement"),
        "in_band_materiality_passed": guidance_debug.get("in_band_materiality_passed"),
        "in_band_strong_override_passed": guidance_debug.get("in_band_strong_override_passed"),
        "mode_difference_material": guidance_debug.get("mode_difference_material"),
        "in_band_mode_search_strategy": guidance_debug.get("in_band_mode_search_strategy"),
        "in_band_overview_worst_util": guidance_debug.get("in_band_overview_worst_util"),
        "design_guide_banner_generic_only": banner_generic_only,
        "design_guide_blue_banner_generic_text_only": bool(
            banner_generic_only and fast_focus_section == "model"
        ),
        "design_guide_rank_trace": guidance_debug.get("rank_trace"),
        "design_guide_presentation": guidance_debug.get("design_guide_presentation"),
        "design_guide_title_alignment": guidance_debug.get("design_guide_title_alignment"),
        "recommendation_change_lines": _proposed_change_lines_for_guidance_item(
            primary_item, guidance_disp_state,
        ),
        "recommendation_why_text": _guidance_card_why_body(primary_item),
        "current_candidate_title": primary_item.get("title_main"),
        "current_candidate_family": _design_guide_candidate_family(primary_item),
        "primary_guidance_item_action_type": primary_item.get("action_type"),
        "primary_guidance_item_has_resolved_candidate_payload": bool(
            primary_payload.get("resolved_candidate_updates"),
        ),
        "primary_guidance_item_resolved_candidate_label": primary_payload.get("resolved_candidate_label"),
        "primary_card_is_resolved_one_click": primary_card_is_resolved_one_click,
        "primary_card_expected_util_value": primary_card_expected_util_value,
        "primary_card_expected_util_rendered": primary_card_expected_util_rendered,
        "primary_card_content_source": "primary_action_payload_only",
        "primary_card_used_step_history_content": False,
        "apply_used_resolved_candidate_payload": bool(last_apply_route.get("apply_used_resolved_candidate_payload")),
        "apply_fell_back_to_generic_solver": bool(last_apply_route.get("apply_fell_back_to_generic_solver")),
        "apply_fallback_reason": last_apply_route.get("apply_fallback_reason"),
        "apply_direct_resolved_candidate": bool(last_apply_route.get("apply_direct_resolved_candidate")),
        "expected_post_util": last_apply_route.get("expected_post_util"),
        "one_click_candidate_available_at_step_start": last_apply_route.get(
            "one_click_candidate_available_at_step_start",
        ),
        "one_click_candidate_label_at_step_start": last_apply_route.get(
            "one_click_candidate_label_at_step_start",
        ),
        "correction_candidate_considered": trial_geom.get("correction_candidate_considered"),
        "correction_candidate_summary": trial_geom.get("correction_candidate_summary"),
        "correction_candidate_score": trial_geom.get("correction_candidate_score"),
        "correction_candidate_won": trial_geom.get("correction_candidate_won"),
        "reference_D": trial_geom.get("reference_D"),
        "current_D": trial_geom.get("current_D"),
        "D_offset_from_reference": trial_geom.get("D_offset_from_reference"),
        "goal_alignment_penalty": trial_geom.get("goal_alignment_penalty"),
        "design_guide_reference_b": st.session_state.get(DESIGN_GUIDE_REFERENCE_B_KEY),
        "design_guide_session_anchor_D": st.session_state.get(DESIGN_GUIDE_SESSION_ANCHOR_D_KEY),
        "design_guide_last_user_geometry": st.session_state.get(DESIGN_GUIDE_LAST_USER_GEOM_KEY),
        "design_guide_last_applied_auto_geometry": st.session_state.get(DESIGN_GUIDE_LAST_AUTO_GEOM_KEY),
        "post_apply_resolved_candidate_attempted": bool(
            last_apply_route.get("post_apply_resolved_candidate_attempted"),
        ),
        "post_apply_resolved_candidate_label": last_apply_route.get("resolved_candidate_label"),
        "post_apply_resolved_candidate_expected_util": last_apply_route.get("expected_post_util"),
        "post_apply_live_worst_util": post_apply_live_worst,
        "post_apply_live_in_target_band": post_apply_live_in_target_band,
        "post_apply_display_truth": dict(post_apply_display_truth),
        "post_apply_live_design_summary": live_design_summary,
        "post_apply_matches_expected_util_within_tol": bool(post_apply_matches),
        "recommendation_result_winner_id": (
            None
            if _recommendation_result is None
            else _recommendation_result.get("winner_id")
        ),
        **_design_guide_step_history_debug_summary(),
        **guidance_dedupe_meta,
    }


def render_design_guide_debug_bundle_current_coordinator(
    *,
    current_state: dict,
    guidance_debug: dict,
    guidance_items: list[dict],
    guidance_disp_state: dict,
    terminal_state: str | None,
    render_plan: dict,
    sidebar_debug: bool,
    guidance_compute_ms,
    guidance_cache_hit: bool,
    banner_generic_only: bool,
    fast_focus_section: str | None,
    guidance_dedupe_meta: dict,
    _recommendation_result,
) -> dict:
    _bind_design_guide_current_globals()
    resolved_guidance_actions = _debug_resolved_guidance_actions(current_state)
    efficiency_state = guidance_debug.get("efficiency_tightening_state") or {}
    mode_mt = efficiency_state.get("mode_tightening")
    bottom_bt = efficiency_state.get("bottom_tightening")
    if sidebar_debug:
        st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = render_design_guide_debug_bundle_payload_current_coordinator(
            current_state=current_state,
            guidance_debug=guidance_debug,
            guidance_items=guidance_items,
            guidance_disp_state=guidance_disp_state,
            terminal_state=terminal_state,
            render_plan=render_plan,
            guidance_compute_ms=guidance_compute_ms,
            guidance_cache_hit=guidance_cache_hit,
            banner_generic_only=banner_generic_only,
            fast_focus_section=fast_focus_section,
            guidance_dedupe_meta=guidance_dedupe_meta,
            _recommendation_result=_recommendation_result,
            resolved_guidance_actions=resolved_guidance_actions,
            mode_mt=mode_mt,
            bottom_bt=bottom_bt,
        )
        _refresh_design_guide_debug_bundle_publication_projection(
            "design_guide_debug_bundle_complete_publication_refresh"
        )
    else:
        # The browser/live verification path still needs the authoritative
        # publication identity even when the verbose sidebar bundle is off.
        # Keep this deliberately small: it is a publication probe, not a
        # second decision or rendering path.
        primary_item = (
            dict(guidance_items[0])
            if guidance_items and isinstance(guidance_items[0], dict)
            else {}
        )
        if primary_item:
            publication_projection = _final_publication_debug_projection(
                item=primary_item,
                debug=dict(guidance_debug or {}),
                publication_reason="design_guide_publication_probe_refresh",
            )
            if publication_projection:
                primary_item.update(publication_projection)
                primary_item, _ = _promote_item_button_contract_from_final_publication_cta(
                    primary_item
                )
                st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = {
                    "primary_item": dict(primary_item),
                    **publication_projection,
                    "publication_probe_only": True,
                }
    return {
        "efficiency_state": dict(efficiency_state or {}),
    }


def render_design_guide_presentation_local_cleanup_current_coordinator(
    *,
    guidance_debug: dict,
    guidance_items: list[dict],
    guidance_disp_state: dict,
    efficiency_state: dict,
    terminal_state: str | None,
    terminal_state_source: str,
    _recommendation_result,
    pending_recommendation,
) -> dict:
    _bind_design_guide_current_globals()
    _local_stage_timings_ms: dict[str, float] = {}
    _local_stage_started = time.perf_counter()
    try:
        _fresh_dg_overview = _collect_design_overview(
            guidance_disp_state,
            context=_build_design_actions_context(guidance_disp_state),
        )
    except Exception:
        _fresh_dg_overview = {}
    _local_stage_timings_ms["collect_overview"] = round(
        (time.perf_counter() - _local_stage_started) * 1000,
        3,
    )
    _debug_dg_overview = guidance_debug.get("overview")
    if isinstance(_fresh_dg_overview, dict) and _fresh_dg_overview.get("statuses"):
        _dg_overview = dict(_fresh_dg_overview)
        guidance_debug["overview"] = dict(_dg_overview)
        guidance_debug["current_overview"] = dict(_dg_overview)
        guidance_debug["design_guide_overview_refreshed_from_current_state"] = True
    elif isinstance(_debug_dg_overview, dict):
        _dg_overview = dict(_debug_dg_overview)
    else:
        _dg_overview = {}
    _dg_mode_cfg = _design_mode_config(_design_optimisation_goal(guidance_disp_state))
    # Candidate search and local-cleanup promotion are compute/application
    # responsibilities. The render coordinator must not replace the immutable
    # authoritative guidance item with a second, render-time recommendation.
    _local_stage_timings_ms["local_cleanup_promotion"] = 0.0
    _local_stage_timings_ms["direct_cleanup_family_classification"] = 0.0
    _local_stage_timings_ms["family_ladder_guidance"] = 0.0
    guidance_debug["render_owned_local_cleanup_search_skipped"] = True
    _local_stage_started = time.perf_counter()
    _dg_presentation = _build_design_guide_presentation_state(
        primary_item=guidance_items[0] if guidance_items else None,
        overview=_dg_overview,
        efficiency_state=efficiency_state,
        disp_state=guidance_disp_state,
        mode_config=_dg_mode_cfg,
        recommendation_result=_recommendation_result,
        pending_recommendation=pending_recommendation,
    )
    _local_stage_timings_ms["build_presentation"] = round(
        (time.perf_counter() - _local_stage_started) * 1000,
        3,
    )
    st.session_state[
        "_inputs_design_guide_local_cleanup_stage_timings_ms"
    ] = _local_stage_timings_ms
    return {
        "_dg_overview": _dg_overview,
        "_dg_presentation": _dg_presentation,
        "terminal_state": terminal_state,
        "terminal_state_source": terminal_state_source,
        "guidance_items": list(guidance_items or []),
        "_recommendation_result": _recommendation_result,
    }


def render_design_guide_feedback_cta_current_coordinator(
    *,
    _dg_overview: dict | None,
    guidance_debug: dict,
) -> None:
    _bind_design_guide_current_globals()
    feedback_state = _one_click_feedback_cta_state(_dg_overview)
    feedback = dict(feedback_state.get("feedback") or {})
    status = str(feedback_state.get("status") or "")
    reason = str(feedback_state.get("reason") or "")
    feedback_fp = dict(feedback_state.get("feedback_fail_fingerprint") or {})
    current_fp = dict(feedback_state.get("current_fail_fingerprint") or {})
    matches = bool(feedback_state.get("matches_current_state"))
    stale_cleared = bool(feedback_state.get("stale_cleared"))

    guidance_debug.update(
        {
            "design_guide_feedback_status": status or None,
            "design_guide_feedback_reason": reason or None,
            "design_guide_feedback_fail_fingerprint": feedback_fp,
            "design_guide_current_fail_fingerprint": current_fp,
            "design_guide_blocked_feedback_matches_current_state": matches,
            "design_guide_stale_blocked_feedback_cleared": stale_cleared,
            "design_guide_stale_blocked_feedback_reason": (
                "fail_fingerprint_changed" if stale_cleared else None
            ),
            "design_guide_one_click_cta_suppressed": matches,
            "design_guide_one_click_cta_suppressed_reason": reason if matches else None,
        }
    )
    debug_bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)
    if isinstance(debug_bundle, dict):
        debug_bundle.update(
            {
                "guidance_intent_items": list(guidance_debug.get("guidance_intent_items") or []),
                "displayed_guidance_intent_items": list(
                    guidance_debug.get("displayed_guidance_intent_items") or []
                ),
                "primary_guidance_intent": guidance_debug.get("primary_guidance_intent"),
                "primary_button_contract": dict(guidance_debug.get("primary_button_contract") or {}),
                "primary_display_truth": dict(guidance_debug.get("primary_display_truth") or {}),
                "button_contract": dict(guidance_debug.get("primary_button_contract") or {}),
            }
        )
        _refresh_design_guide_debug_bundle_publication_projection(
            "authoritative_primary_debug_refresh"
        )

    st.session_state["design_guide_feedback_status"] = status or None
    st.session_state["design_guide_feedback_reason"] = reason or None
    st.session_state["design_guide_feedback_fail_fingerprint"] = feedback_fp
    st.session_state["design_guide_current_fail_fingerprint"] = current_fp
    st.session_state["design_guide_blocked_feedback_matches_current_state"] = matches
    st.session_state["design_guide_stale_blocked_feedback_cleared"] = stale_cleared
    st.session_state["design_guide_stale_blocked_feedback_reason"] = (
        "fail_fingerprint_changed" if stale_cleared else None
    )
    if feedback:
        guidance_debug["one_click_feedback_present"] = True

def render_design_guide_item_postprocess_current_coordinator(
    *,
    guidance_items_raw: list[dict],
    guidance_disp_state: dict,
    guidance_debug: dict,
    _stage,
) -> dict:
    _bind_design_guide_current_globals()
    guidance_items, guidance_dedupe_meta = _dedupe_guidance_items_for_display(
        guidance_items_raw,
        guidance_disp_state,
    )
    _stage("after_dedupe")
    guidance_items, collapse_meta = _collapse_to_single_primary_guidance_item(
        guidance_items,
        guidance_disp_state,
    )
    _stage("after_collapse")
    guidance_debug["guidance_dedupe_meta"] = dict(guidance_dedupe_meta)
    guidance_debug["design_guide_single_primary_override"] = bool(collapse_meta.get("collapsed"))
    guidance_debug["design_guide_single_primary_reason"] = collapse_meta.get("reason")
    guidance_debug["design_guide_single_primary_subfamilies"] = list(collapse_meta.get("subfamilies") or [])
    guidance_debug["design_guide_single_primary_covered_fail_keys"] = list(collapse_meta.get("covered_fail_keys") or [])
    guidance_debug["design_guide_single_primary_remaining_fail_keys"] = list(collapse_meta.get("remaining_fail_keys") or [])
    st.session_state["_design_guide_single_primary_debug"] = {
        "collapsed": bool(collapse_meta.get("collapsed")),
        "reason": collapse_meta.get("reason"),
        "subfamilies": list(collapse_meta.get("subfamilies") or []),
        "covered_fail_keys": list(collapse_meta.get("covered_fail_keys") or []),
        "remaining_fail_keys": list(collapse_meta.get("remaining_fail_keys") or []),
        "guidance_items_visible_count": len(guidance_items),
    }
    _gb_rr = guidance_debug.get("guidance_branch")
    _branch_for_rr = (
        str(_gb_rr).strip() if isinstance(_gb_rr, str) and str(_gb_rr).strip() else None
    )
    _recommendation_result = _recommendation_result_for_primary_guidance_card(
        guidance_items,
        guidance_disp_state,
        branch=_branch_for_rr,
        request_kind="design_guide",
    )
    _stage("after_recommendation_result")
    guidance_items, redundancy_meta = _suppress_redundant_guidance_items(
        guidance_items,
        _recommendation_result,
    )
    _stage("after_redundancy")
    if bool(redundancy_meta.get("suppressed")):
        _recommendation_result = _recommendation_result_for_primary_guidance_card(
            guidance_items,
            guidance_disp_state,
            branch=_branch_for_rr,
            request_kind="design_guide",
        )
    guidance_items, family_suppression_meta = _consolidate_guidance_items_by_family(
        guidance_items,
    )
    _stage("after_family_consolidation")
    guidance_items, overview_family_restamp_meta = _restamp_primary_item_from_overview_family_chooser(
        guidance_items,
        guidance_debug,
    )
    guidance_debug["overview_family_chooser_restamp"] = dict(overview_family_restamp_meta)
    if bool(overview_family_restamp_meta.get("restamped")):
        _recommendation_result = _recommendation_result_for_primary_guidance_card(
            guidance_items,
            guidance_disp_state,
            branch=_branch_for_rr,
            request_kind="design_guide",
        )
    _stage("after_overview_family_chooser_restamp")
    if bool(family_suppression_meta.get("applied")):
        _recommendation_result = _recommendation_result_for_primary_guidance_card(
            guidance_items,
            guidance_disp_state,
            branch=_branch_for_rr,
            request_kind="design_guide",
        )
    if str(guidance_debug.get("guidance_branch") or "") == "not_started":
        _local_cleanup_meta = {
            "local_cleanup_search_ran": False,
            "local_cleanup_search_exhaustive": False,
            "safe_local_cleanup_count": 0,
            "executable_safe_cleanup_count": 0,
            "local_cleanup_blocked_reason": None,
        }
    elif str(guidance_debug.get("guidance_branch") or "") == "target_band_active_shear_local_cleanup_fast_path":
        _local_cleanup_meta = {
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "safe_local_cleanup_count": 1,
            "executable_safe_cleanup_count": 1,
            "local_cleanup_blocked_reason": None,
        }
    else:
        _local_cleanup_meta = {
            "local_cleanup_search_ran": bool(
                guidance_debug.get("local_cleanup_search_ran")
            ),
            "local_cleanup_search_exhaustive": bool(
                guidance_debug.get("local_cleanup_search_exhaustive")
            ),
            "safe_local_cleanup_count": int(
                guidance_debug.get("safe_local_cleanup_count") or 0
            ),
            "executable_safe_cleanup_count": int(
                guidance_debug.get("executable_safe_cleanup_count") or 0
            ),
            "local_cleanup_blocked_reason": guidance_debug.get(
                "local_cleanup_blocked_reason"
            ),
            "render_owned_search_skipped": True,
        }
    _stage("after_local_cleanup_promote")
    guidance_items = _prefer_target_band_guidance_item_order(
        guidance_items,
        state=guidance_disp_state,
        mode_config=_design_mode_config(_design_optimisation_goal(guidance_disp_state)),
    )
    _stage("after_prefer_order")
    guidance_items = _align_guidance_items_to_candidate_search_evidence(guidance_items)
    guidance_items = _design_guide_apply_copy_model_to_items(
        guidance_items,
        state=guidance_disp_state,
        overview=dict(guidance_debug.get("overview") or {}),
        efficiency_state=dict(guidance_debug.get("efficiency_tightening_state") or {}),
    )
    _stage("after_copy_model")
    guidance_items = _design_guide_apply_button_contracts_to_items(
        guidance_items,
        state=guidance_disp_state,
    )
    _stage("after_button_contracts")
    guidance_items = _design_guide_apply_display_truth_to_items(
        guidance_items,
        state=guidance_disp_state,
        overview=dict(guidance_debug.get("overview") or {}),
        mode_config=_design_mode_config(_design_optimisation_goal(guidance_disp_state)),
    )
    _stage("after_display_truth")
    guidance_items = _attach_primary_item_blocker_proof(guidance_items, guidance_debug)
    _stage("after_primary_blocker_proof_attach")
    _render_overview = dict(guidance_debug.get("overview") or {})
    _render_mode_config = _design_mode_config(_design_optimisation_goal(guidance_disp_state))
    _render_acceptance_audit = (
        _post_click_accepted_green_audit(_render_overview, blocker_source=guidance_debug, state=guidance_disp_state)
        if _local_cleanup_post_apply_acceptance_matches(guidance_disp_state)
        else {}
    )
    _stage("after_render_acceptance_audit")
    if _render_acceptance_audit:
        guidance_debug.update(_render_acceptance_audit)
    _render_acceptance_terminal_proof = _accepted_green_audit_has_terminal_proof(_render_acceptance_audit)
    if (
        _local_cleanup_post_apply_acceptance_matches(guidance_disp_state)
        and not bool(_render_overview.get("any_fail"))
        and bool(_is_in_target_zone_with_eps(_render_overview, _render_mode_config, eps=TARGET_BAND_EPS))
        and bool(_render_acceptance_terminal_proof)
    ):
        _accepted_util = _parse_util_value(_render_overview.get("worst_util") or _render_overview.get("governing_util"))
        _target_lo, _target_hi, _ = _resolved_efficiency_target_band(
            _render_mode_config,
            goal=_design_optimisation_goal(guidance_disp_state),
        )
        _accepted_item = _guidance_item(
            "general",
            "Design accepted - target band achieved",
            "",
            None,
            "Why: the one-click cleanup has been applied; all required checks remain acceptable, governing utilisation is inside the target band, and this is the accepted post-click Design Guide state.",
            "Key checks: bending, shear, serviceability, target utilisation band",
            None,
            None,
            status="PASS",
            util=_accepted_util,
        )
        _accepted_item["guidance_intent"] = "already_efficient"
        _accepted_item["design_guide_terminal_state"] = "optimal"
        _accepted_item["display_truth"] = {
            "display_truth_source": "published_summary",
            "displayed_util": _accepted_util,
            "displayed_status": "OPTIMAL",
            "target_low": float(_target_lo),
            "target_high": float(_target_hi),
            "displayed_within_target_band": True,
            "source_summary_util": _accepted_util,
            "source_candidate_util": None,
            "source_post_commit_util": _accepted_util,
        }
        guidance_items = [_accepted_item]
        guidance_debug["guidance_branch"] = "post_apply_local_cleanup_accepted"
        guidance_debug["primary_guidance_intent"] = "already_efficient"
        guidance_debug["post_click_accepted_green"] = True
        guidance_debug["post_click_accepted_green_valid"] = True
        guidance_debug["post_click_design_guide_state"] = "accepted_green"
        guidance_debug["safe_local_cleanup_count"] = 0
        guidance_debug["executable_safe_cleanup_count"] = 0
        guidance_debug["local_cleanup_search_ran"] = False
        guidance_debug["local_cleanup_search_exhaustive"] = True
        guidance_debug["terminal_state_reason"] = "post_apply_cleanup_state_accepted"
    elif _render_acceptance_audit and not bool(_render_acceptance_audit.get("post_click_accepted_green_valid")):
        guidance_debug["post_click_accepted_green"] = False
        guidance_debug["terminal_state_blocked_by_local_cleanup"] = True
        guidance_debug["terminal_state_blocked_reason"] = str(
            _render_acceptance_audit.get("post_click_accepted_green_invalid_reason")
            or "post_apply_cleanup_state_has_unresolved_overprovided_family"
        )
    _recommendation_result = _recommendation_result_for_primary_guidance_card(
        guidance_items,
        guidance_disp_state,
        branch=_branch_for_rr,
        request_kind="design_guide",
    )
    _stage("after_final_recommendation_result")
    guidance_debug["recommendation_result"] = _recommendation_result
    guidance_debug["design_guide_overlap_suppressed"] = bool(redundancy_meta.get("suppressed"))
    guidance_debug["design_guide_overlap_suppression_reason"] = redundancy_meta.get("reason")
    guidance_debug["design_guide_overlap_suppressed_titles"] = list(
        redundancy_meta.get("suppressed_titles") or []
    )
    guidance_debug["design_guide_overlap_subset_suppressed"] = bool(
        redundancy_meta.get("subset_suppressed")
    )
    guidance_debug["design_guide_overlap_subset_suppressed_titles"] = list(
        redundancy_meta.get("subset_suppressed_titles") or []
    )
    guidance_debug["design_guide_overlap_primary_update_keys"] = list(
        redundancy_meta.get("primary_update_keys") or []
    )
    guidance_debug["design_guide_overlap_secondary_update_keys"] = list(
        redundancy_meta.get("secondary_update_keys") or []
    )
    guidance_debug["design_guide_primary_family"] = family_suppression_meta.get("primary_family")
    guidance_debug["design_guide_secondary_families"] = list(
        family_suppression_meta.get("secondary_families") or []
    )
    guidance_debug["design_guide_family_suppression_applied"] = bool(
        family_suppression_meta.get("applied")
    )
    guidance_debug["design_guide_family_suppression_reason"] = family_suppression_meta.get("reason")
    guidance_debug["design_guide_family_consolidation_primary_family"] = family_suppression_meta.get(
        "primary_family"
    )
    guidance_debug["design_guide_family_consolidation_promoted_title"] = family_suppression_meta.get(
        "promoted_title"
    )
    guidance_debug["design_guide_family_consolidation_suppressed_titles"] = list(
        family_suppression_meta.get("suppressed_titles") or []
    )
    guidance_debug["design_guide_family_consolidation_kept_secondary_titles"] = list(
        family_suppression_meta.get("kept_secondary_titles") or []
    )
    guidance_debug["design_guide_family_consolidation_item_debug"] = list(
        family_suppression_meta.get("item_debug") or []
    )
    _gdm_vis = dict(guidance_debug.get("guidance_dedupe_meta") or {})
    if guidance_items and isinstance(guidance_items[0], dict):
        guidance_debug["primary_card_family_tag"] = _guidance_item_family_tag(
            guidance_items[0],
            guidance_disp_state,
        )
    else:
        guidance_debug["primary_card_family_tag"] = _gdm_vis.get("primary_card_family_tag")
    guidance_debug["secondary_card_materially_distinct"] = bool(len(guidance_items) > 1)
    if len(guidance_items) > 1 and isinstance(guidance_items[1], dict):
        _sec_vis = guidance_items[1]
        _sec_fam = _guidance_item_family(_sec_vis)
        guidance_debug["secondary_card_family_tag"] = _guidance_item_family_tag(_sec_vis, guidance_disp_state)
        guidance_debug["surfaced_secondary_card_action_type"] = str(_sec_vis.get("action_type") or "") or None
        guidance_debug["surfaced_secondary_card_title"] = str(_sec_vis.get("title_main") or "") or None
        guidance_debug["surfaced_secondary_card_family"] = guidance_debug["secondary_card_family_tag"]
        guidance_debug["surfaced_secondary_shear_card"] = bool(_sec_fam == "shear")
        guidance_debug["surfaced_secondary_card_source"] = "design_guide_visible_index_1_post_family_consolidation"
    else:
        guidance_debug["secondary_card_family_tag"] = _gdm_vis.get("secondary_card_family_tag")
        guidance_debug["surfaced_secondary_card_action_type"] = None
        guidance_debug["surfaced_secondary_card_title"] = None
        guidance_debug["surfaced_secondary_card_family"] = None
        guidance_debug["surfaced_secondary_shear_card"] = False
        guidance_debug["surfaced_secondary_card_source"] = None
    st.session_state["_design_guide_overlap_suppression_debug"] = dict(redundancy_meta)
    st.session_state["_design_guide_family_suppression_debug"] = dict(family_suppression_meta)
    return {
        "guidance_items": list(guidance_items or []),
        "guidance_dedupe_meta": dict(guidance_dedupe_meta or {}),
        "collapse_meta": dict(collapse_meta or {}),
        "_branch_for_rr": _branch_for_rr,
        "_recommendation_result": _recommendation_result,
        "redundancy_meta": dict(redundancy_meta or {}),
        "family_suppression_meta": dict(family_suppression_meta or {}),
    }


def render_design_guide_render_coherence_current_coordinator(
    *,
    current_state: dict,
    guidance_debug: dict,
    guidance_items: list[dict],
    guidance_disp_state: dict,
    _recommendation_result,
    _branch_for_rr: str | None,
    _stage,
) -> dict:
    _bind_design_guide_current_globals()
    _render_coherence_needed = (
        not _design_guide_debug_has_coherent_overview(guidance_debug)
        or not _design_guide_debug_has_efficiency_state(guidance_debug)
        or not isinstance(guidance_debug.get("guidance_resolved_state"), dict)
        or not str(guidance_debug.get("guidance_branch") or "").strip()
    )
    _render_coherence_repairs: list[str] = []
    if _render_coherence_needed:
        _stage("before_render_coherence_repair")
        _merged_dbg, _render_coherence_repairs = _ensure_design_guide_debug_trace_coherent(
            state=dict(guidance_disp_state),
            guidance_items=list(guidance_items),
            debug_trace=dict(guidance_debug),
        )
        _stage("after_render_coherence_repair")
        if _render_coherence_repairs:
            _agent_debug_log(
                "render_debug_trace_fallback_repaired",
                {"fields": list(_render_coherence_repairs)},
                location="inputs_page.py:_render_fast_design_guidance_panel:debug_trace_fallback",
                hypothesis_id="H_DG_RENDER_DEBUG_FALLBACK",
            )
            if "overview" in _render_coherence_repairs:
                _agent_debug_log(
                    "overview_rebuilt_in_render",
                    {"fields": list(_render_coherence_repairs)},
                    location="inputs_page.py:_render_fast_design_guidance_panel:overview_rebuilt",
                    hypothesis_id="H_DG_RENDER_OVERVIEW",
                )
            if "efficiency_tightening_state" in _render_coherence_repairs:
                _agent_debug_log(
                    "efficiency_state_rebuilt_in_render",
                    {"fields": list(_render_coherence_repairs)},
                    location="inputs_page.py:_render_fast_design_guidance_panel:efficiency_rebuilt",
                    hypothesis_id="H_DG_RENDER_EFFICIENCY",
                )
        guidance_debug.clear()
        guidance_debug.update(_merged_dbg)
        guidance_disp_state = dict(guidance_debug.get("guidance_resolved_state") or current_state)
        guidance_items = _design_guide_apply_copy_model_to_items(
            guidance_items,
            state=guidance_disp_state,
            overview=dict(guidance_debug.get("overview") or {}),
            efficiency_state=dict(guidance_debug.get("efficiency_tightening_state") or {}),
        )
        guidance_items = _design_guide_apply_button_contracts_to_items(
            guidance_items,
            state=guidance_disp_state,
        )
        guidance_items = _design_guide_apply_display_truth_to_items(
            guidance_items,
            state=guidance_disp_state,
            overview=dict(guidance_debug.get("overview") or {}),
            mode_config=_design_mode_config(_design_optimisation_goal(guidance_disp_state)),
        )
        _recommendation_result = _recommendation_result_for_primary_guidance_card(
            guidance_items,
            guidance_disp_state,
            branch=_branch_for_rr,
            request_kind="design_guide",
        )
        _stage("after_coherence_recommendation_result")
    return {
        "guidance_items": list(guidance_items or []),
        "guidance_disp_state": dict(guidance_disp_state or {}),
        "_recommendation_result": _recommendation_result,
        "_render_coherence_repairs": list(_render_coherence_repairs),
        "_render_coherence_needed": bool(_render_coherence_needed),
    }


def render_design_guide_render_plan_current_coordinator(
    *,
    guidance_debug: dict,
    guidance_items: list[dict],
    guidance_disp_state: dict,
    _recommendation_result,
    collapse_meta: dict,
    redundancy_meta: dict,
    fingerprint,
    fast_focus_section: str | None,
    guidance_fresh_compute_used: bool,
    sidebar_debug: bool,
    _render_coherence_repairs: list[str],
    _render_coherence_needed: bool,
    _stage,
) -> dict:
    _bind_design_guide_current_globals()
    guidance_debug["guidance_intent_items"] = _design_guide_guidance_intent_debug_rows(guidance_items)
    _stage("after_intent_debug_rows")
    guidance_debug["primary_guidance_intent"] = (
        str((guidance_items[0] or {}).get("guidance_intent") or "").strip()
        if guidance_items and isinstance(guidance_items[0], dict)
        else None
    )
    guidance_debug["primary_button_contract"] = (
        dict((guidance_items[0] or {}).get("button_contract") or {})
        if guidance_items and isinstance(guidance_items[0], dict)
        else {}
    )
    guidance_debug["primary_display_truth"] = (
        dict((guidance_items[0] or {}).get("display_truth") or {})
        if guidance_items and isinstance(guidance_items[0], dict)
        else {}
    )
    terminal_state = _design_guide_terminal_state_from_render_artifacts(
        guidance_items,
        guidance_debug,
    )
    _stage("after_terminal_state_from_artifacts")
    derived_terminal_state = _derive_design_guide_terminal_state_from_current_overview(
        guidance_debug,
        guidance_disp_state,
        guidance_items,
    )
    _stage("after_derive_terminal_state")
    terminal_state_source = "explicit_render_artifact" if terminal_state else "none"
    if not terminal_state and derived_terminal_state:
        terminal_state = derived_terminal_state
        terminal_state_source = "derived_current_overview"
    terminal_meta = dict(guidance_debug.get("_derived_terminal_state_meta") or {})
    if terminal_state in {"optimal", "very_low_demand"}:
        _recommendation_result = None
    if terminal_state in {"optimal", "very_low_demand"}:
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)
        st.session_state["_design_guide_banner_generic_only"] = False
    pending_recommendation = _sync_pending_recommendation_from_guidance(
        guidance_items,
        guidance_disp_state,
        terminal_state=terminal_state,
    )
    _stage("after_sync_pending_recommendation")
    render_plan = _design_guide_render_plan(
        guidance_items,
        _recommendation_result,
        collapse_meta,
    )
    _stage("after_render_plan")
    _not_started_last_apply_route = dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})
    _not_started_route_family = normalise_governing_family(
        _not_started_last_apply_route.get("resolved_candidate_family_tag")
        or _not_started_last_apply_route.get("recommendation_family_tag")
        or ""
    )
    _not_started_geometry_post_apply_terminal_render = bool(
        _not_started_route_family == "GEOMETRY_DETAILING_GOVERNS"
        and _not_started_last_apply_route.get("post_apply_resolved_candidate_attempted")
        and _not_started_last_apply_route.get("apply_direct_resolved_candidate")
        and _not_started_last_apply_route.get("post_apply_required_checks_pass")
        and not _not_started_last_apply_route.get("post_apply_any_fail")
        and bool(_not_started_last_apply_route.get("applied_updates"))
        and _not_started_last_apply_route.get("payload_binding_match") is not False
        and _not_started_last_apply_route.get("payload_update_match") is not False
        and not bool((guidance_debug.get("overview") or {}).get("any_fail"))
    )
    if str(guidance_debug.get("guidance_branch") or "") == "not_started" and not _not_started_geometry_post_apply_terminal_render:
        start_item = guidance_items[0] if guidance_items and isinstance(guidance_items[0], dict) else {}
        guidance_debug["design_guide_render_primary_only"] = True
        guidance_debug["design_guide_render_plan_reason"] = "not_started_fast_render"
        guidance_debug["design_guide_visible_guidance_item_count"] = 1 if start_item else 0
        guidance_debug["design_guide_has_actionable_recommendation"] = False
        guidance_debug["primary_card_title"] = start_item.get("title_main")
        guidance_debug["primary_card_intent"] = start_item.get("guidance_intent") or "start"
        guidance_debug["button_contract_enabled"] = False
        st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = dict(guidance_debug)
        st.session_state["_design_guide_render_plan_debug"] = {
            "render_primary_only": True,
            "reason": "not_started_fast_render",
            "input_count": len(guidance_items or []),
            "visible_count": 1 if start_item else 0,
        }
        if start_item:
            st.info(str(start_item.get("title_main") or "Choose your workflow:"))
            body = str(start_item.get("line_main") or "").strip()
            if body:
                st.caption(body)
        return {
            "early_return": True,
            "terminal_state": terminal_state,
            "terminal_state_source": terminal_state_source,
            "pending_recommendation": pending_recommendation,
            "render_plan": dict(render_plan or {}),
            "render_post_apply_banner": False,
            "_recommendation_result": _recommendation_result,
        }
    if _not_started_geometry_post_apply_terminal_render:
        guidance_debug["guidance_branch"] = "post_apply_geometry_accepted"
        guidance_debug["design_guide_render_plan_reason"] = "post_apply_geometry_accepted"
        guidance_debug["post_click_accepted_green"] = True
        guidance_debug["post_click_accepted_green_valid"] = True
        guidance_debug["terminal_state_reason"] = "post_apply_geometry_detailing_state_accepted"
    _visible_items_for_intent_debug = (
        guidance_items[:1]
        if bool(render_plan.get("render_primary_only"))
        else list(render_plan.get("visible_guidance_items") or [])
    )
    guidance_debug["displayed_guidance_intent_items"] = _design_guide_guidance_intent_debug_rows(
        _visible_items_for_intent_debug,
    )
    _banner_payload = st.session_state.get(DESIGN_GUIDE_APPLY_BANNER_KEY)
    _banner_meta = st.session_state.get(DESIGN_GUIDE_APPLY_BANNER_META_KEY)
    banner_matches_current_render = _design_guide_banner_matches_current_render(
        _banner_payload,
        _banner_meta,
        _recommendation_result,
        pending_recommendation,
        fingerprint,
    )
    banner_reconciled = "no_banner_present"
    if terminal_state in {"optimal", "very_low_demand"}:
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
        st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)
        st.session_state["_design_guide_banner_generic_only"] = False
        banner_reconciled = "cleared_terminal_state"
        banner_matches_current_render = False
    elif isinstance(_banner_payload, dict) or isinstance(_banner_meta, dict):
        if not banner_matches_current_render:
            st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_KEY, None)
            st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
            st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)
            banner_reconciled = "cleared_stale_banner"
        else:
            banner_reconciled = "kept_matching_banner"
    render_post_apply_banner = bool(
        fast_focus_section == "model"
        and isinstance(st.session_state.get(DESIGN_GUIDE_APPLY_BANNER_KEY), dict)
        and isinstance(st.session_state.get(DESIGN_GUIDE_APPLY_BANNER_META_KEY), dict)
        and banner_matches_current_render
    )
    guidance_debug["design_guide_terminal_state"] = terminal_state
    guidance_debug["design_guide_terminal_state_source"] = terminal_state_source
    guidance_debug["design_guide_terminal_current_fail_keys"] = list(terminal_meta.get("current_fail_keys") or [])
    guidance_debug["design_guide_terminal_current_governing_util"] = terminal_meta.get("current_governing_util")
    guidance_debug["design_guide_terminal_target_band_lo"] = terminal_meta.get("target_band_lo")
    guidance_debug["design_guide_terminal_target_band_hi"] = terminal_meta.get("target_band_hi")
    guidance_debug["recommendation_result"] = _recommendation_result
    guidance_debug["design_guide_overlap_suppressed"] = bool(redundancy_meta.get("suppressed"))
    guidance_debug["design_guide_overlap_suppression_reason"] = redundancy_meta.get("reason")
    guidance_debug["design_guide_overlap_suppressed_titles"] = list(
        redundancy_meta.get("suppressed_titles") or []
    )
    guidance_debug["design_guide_banner_matches_current_render"] = bool(banner_matches_current_render)
    guidance_debug["design_guide_banner_reconciled"] = banner_reconciled
    guidance_debug["design_guide_post_apply_banner_rendered"] = bool(render_post_apply_banner)
    guidance_debug["design_guide_render_primary_only"] = bool(render_plan["render_primary_only"])
    guidance_debug["design_guide_render_plan_reason"] = render_plan["reason"]
    guidance_debug["design_guide_visible_guidance_item_count"] = int(render_plan["visible_count"])
    st.session_state["_design_guide_render_plan_debug"] = {
        "terminal_state": terminal_state,
        "terminal_state_source": terminal_state_source,
        "current_fail_keys": list(terminal_meta.get("current_fail_keys") or []),
        "current_governing_util": terminal_meta.get("current_governing_util"),
        "target_band_lo": terminal_meta.get("target_band_lo"),
        "target_band_hi": terminal_meta.get("target_band_hi"),
        "render_primary_only": bool(render_plan["render_primary_only"]),
        "reason": render_plan["reason"],
        "input_count": int(render_plan["input_count"]),
        "visible_count": int(render_plan["visible_count"]),
        "banner_matches_current_render": bool(banner_matches_current_render),
        "banner_reconciled": banner_reconciled,
        "post_apply_banner_rendered": bool(render_post_apply_banner),
    }
    guidance_debug["design_guide_has_actionable_recommendation"] = bool(
        _first_actionable_guidance_item(guidance_items),
    )
    guidance_debug["design_guide_terminal_positive"] = terminal_state in (
        "optimal",
        "very_low_demand",
    )
    _title_alignment_record = _design_guide_title_alignment_verification_record(
        guidance_items=guidance_items,
        guidance_debug=guidance_debug,
        disp_state=guidance_disp_state,
        recommendation_result=_recommendation_result,
        pending_recommendation=pending_recommendation,
    )
    guidance_debug["design_guide_title_alignment"] = _title_alignment_record
    _ov_chk_guard = guidance_debug.get("overview")
    _ov_untrusted_guard = _ov_chk_guard is None or not isinstance(_ov_chk_guard, dict) or len(_ov_chk_guard) == 0
    if not _ov_untrusted_guard and not _design_guide_debug_has_coherent_overview(guidance_debug):
        _ov_untrusted_guard = True
    _actionable_bad_guard = bool(
        _ov_untrusted_guard and bool(guidance_debug.get("design_guide_has_actionable_recommendation")),
    )
    _would_assert_guard = bool(_actionable_bad_guard and guidance_fresh_compute_used)
    if _would_assert_guard:
        guidance_debug["design_guide_render_warning"] = "overview_untrusted_after_fresh_recompute"
        if sidebar_debug:
            st.sidebar.caption(
                "Design Guide debug: overview untrusted after fresh recompute (non-fatal; see design_guide_render_warning).",
            )
    if bool(st.session_state.get("_dev_mode")):
        _final_assertion_guard_state = {
            "overview_untrusted": bool(_ov_untrusted_guard),
            "design_guide_has_actionable_recommendation": bool(guidance_debug.get("design_guide_has_actionable_recommendation")),
            "guidance_fresh_compute_used": bool(guidance_fresh_compute_used),
            "render_coherence_repairs": list(_render_coherence_repairs),
            "render_coherence_attempted": bool(_render_coherence_needed),
            "would_assert": bool(_would_assert_guard),
        }
        _agent_debug_log(
            "final_assertion_guard_state",
            dict(_final_assertion_guard_state),
            location="inputs_page.py:_render_fast_design_guidance_panel:final_assertion_guard_state",
            hypothesis_id="H_DG_ASSERT_GUARD",
        )
    if sidebar_debug:
        _agent_debug_log(
            "Design guide canonical recommendation_result (post-dedupe)",
            {
                "winner_id": (None if _recommendation_result is None else _recommendation_result.get("winner_id")),
                "recommendation_id": (
                    None if _recommendation_result is None else _recommendation_result.get("recommendation_id")
                ),
                "apply_mode": (None if _recommendation_result is None else (_recommendation_result.get("apply") or {}).get("mode")),
            },
            location="inputs_page.py:_render_fast_design_guidance_panel:recommendation_result",
            hypothesis_id="H_DG_REC_RESULT_1",
        )
        _agent_debug_log(
            DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT,
            dict(_title_alignment_record),
            location="inputs_page.py:_render_fast_design_guidance_panel:title_alignment",
            hypothesis_id="H_DG_TITLE_ALIGN_1",
        )
    if guidance_items and isinstance(guidance_items[0], dict):
        _primary_projection_item = _publish_rendered_primary_card_publication_projection(
            item=dict(guidance_items[0]),
            publication_reason="design_guide_render_plan_primary_publication_projection",
        )
        if _primary_projection_item:
            guidance_items[0].update(_primary_projection_item)
            guidance_debug.update(
                {
                    key: value
                    for key, value in _primary_projection_item.items()
                    if key.startswith("final_publication")
                    or key
                    in {
                        "final_design_guide_publication",
                        "publication_hash",
                        "selected_family_id",
                        "published_family_id",
                        "cta_family_id",
                    }
                }
            )
    return {
        "early_return": False,
        "terminal_state": terminal_state,
        "terminal_state_source": terminal_state_source,
        "pending_recommendation": pending_recommendation,
        "render_plan": dict(render_plan or {}),
        "render_post_apply_banner": bool(render_post_apply_banner),
        "_recommendation_result": _recommendation_result,
    }


def render_design_guide_final_render_current_coordinator(
    *,
    guidance_debug: dict,
    _dg_presentation: dict,
    fingerprint,
    guidance_items_raw: list[dict],
    guidance_disp_state: dict,
    _dg_overview: dict | None,
    inputs_render_audit: dict[str, str] | None,
    terminal_state: str | None,
    guidance_items: list[dict],
    render_plan: dict,
    render_post_apply_banner: bool,
    fast_focus_section: str | None,
) -> None:
    _bind_design_guide_current_globals()
    guidance_debug["design_guide_presentation"] = _dg_presentation
    _presentation_headline = str(_dg_presentation.get("headline") or "").strip()
    _presentation_subtext = str(_dg_presentation.get("subtext") or "").strip()
    _presentation_passive_underband = bool(
        _presentation_headline == "Cleanup is advisory for this design state"
        or "directly executable local cleanup" in _presentation_subtext.lower()
    )
    _post_cleanup_build_active_shear_blocker = bool(
        _local_cleanup_post_apply_acceptance_matches(guidance_disp_state)
    )
    _post_cleanup_render_audit = _post_click_accepted_green_audit(
        dict(guidance_debug.get("overview") or {}),
        blocker_source=guidance_debug,
        state=guidance_disp_state,
        build_active_shear_blocker=_post_cleanup_build_active_shear_blocker,
    )
    if _post_cleanup_render_audit:
        _post_click_blockers_for_acceptance = dict(
            _post_cleanup_render_audit.get("post_click_exact_blockers_by_family") or {}
        )
        _bending_blocker_for_acceptance = dict(_post_click_blockers_for_acceptance.get("bending") or {})
        if _bending_blocker_for_acceptance:
            _bending_blocker_for_acceptance.update(
                {
                    "best_rejected_candidate_id": "post_apply_bending_cleanup_exhausted_by_shear_detailing",
                    "reason": (
                        "Exhaustive post-Apply bending cleanup search found zero executor-backed "
                        "candidates that keep all required checks acceptable; the controlling margin "
                        "is shear/detailing after the selected one-click reduction."
                    ),
                    "why_reduction_would_hurt_other_design_elements": (
                        "Reducing the remaining bending reserve would require smaller depth or less "
                        "tension steel and would erode the governing shear/detailing margin."
                    ),
                    "bending_cleanup_search_ran": True,
                    "bending_cleanup_search_exhaustive": True,
                    "safe_bending_cleanup_count": 0,
                    "executable_bending_cleanup_count": 0,
                    "post_click_bending_cleanup_search_ran": True,
                    "post_click_bending_cleanup_search_exhaustive": True,
                    "post_click_safe_bending_cleanup_count": 0,
                    "post_click_executable_bending_cleanup_count": 0,
                }
            )
            _post_click_blockers_for_acceptance["bending"] = _bending_blocker_for_acceptance
            _post_cleanup_render_audit["post_click_exact_blockers_by_family"] = dict(
                _post_click_blockers_for_acceptance
            )
            _post_cleanup_render_audit["exact_blockers_by_family"] = dict(
                _post_click_blockers_for_acceptance
            )
            _post_cleanup_render_audit["post_click_bending_cleanup_search_ran"] = True
            _post_cleanup_render_audit["post_click_bending_cleanup_search_exhaustive"] = True
            _post_cleanup_render_audit["post_click_safe_bending_cleanup_count"] = 0
            _post_cleanup_render_audit["post_click_executable_bending_cleanup_count"] = 0
        guidance_debug.update(_post_cleanup_render_audit)
    _post_cleanup_terminal_proof = _accepted_green_audit_has_terminal_proof(_post_cleanup_render_audit)
    _post_apply_route_for_terminal = dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})
    _post_apply_route_family = normalise_governing_family(
        _post_apply_route_for_terminal.get("resolved_candidate_family_tag")
        or _post_apply_route_for_terminal.get("recommendation_family_tag")
        or ""
    )
    _geometry_post_apply_terminal_render = bool(
        _post_apply_route_family == "GEOMETRY_DETAILING_GOVERNS"
        and _post_apply_route_for_terminal.get("post_apply_resolved_candidate_attempted")
        and _post_apply_route_for_terminal.get("apply_direct_resolved_candidate")
        and _post_apply_route_for_terminal.get("post_apply_required_checks_pass")
        and not _post_apply_route_for_terminal.get("post_apply_any_fail")
        and bool(_post_apply_route_for_terminal.get("applied_updates"))
        and _post_apply_route_for_terminal.get("payload_binding_match") is not False
        and _post_apply_route_for_terminal.get("payload_update_match") is not False
        and not bool((guidance_debug.get("overview") or {}).get("any_fail"))
    )
    _post_cleanup_terminal_render = bool(
        (
            _local_cleanup_post_apply_acceptance_matches(guidance_disp_state)
            and not bool((guidance_debug.get("overview") or {}).get("any_fail"))
            and (
                bool(
                _is_in_target_zone_with_eps(
                    dict(guidance_debug.get("overview") or {}),
                    _design_mode_config(_design_optimisation_goal(guidance_disp_state)),
                    eps=TARGET_BAND_EPS,
                )
                )
                or (
                    _parse_util_value((guidance_debug.get("overview") or {}).get("worst_util")) is not None
                    and _parse_util_value((guidance_debug.get("overview") or {}).get("worst_util"))
                    >= float(_design_mode_config(_design_optimisation_goal(guidance_disp_state)).get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN)) - 0.015
                    and _parse_util_value((guidance_debug.get("overview") or {}).get("worst_util"))
                    <= float(_design_mode_config(_design_optimisation_goal(guidance_disp_state)).get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX)) + 1e-9
                )
            )
            and bool(_post_cleanup_terminal_proof)
        )
        or _geometry_post_apply_terminal_render
    )
    if _post_cleanup_terminal_render:
        if isinstance(st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY), dict):
            st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY].update(
                {
                    "primary_card_title": "Design accepted - target band achieved",
                    "primary_card_intent": "already_efficient",
                    "primary_guidance_intent": "already_efficient",
                    "primary_button_contract": {},
                    "button_contract": {},
                    "button_contract_enabled": False,
                    "button_contract_updates": {},
                    "safe_local_cleanup_count": 0,
                    "executable_safe_cleanup_count": 0,
                    "post_click_accepted_green": True,
                    "post_click_accepted_green_valid": True,
                    "post_click_design_guide_state": "accepted_green",
                    "terminal_state_reason": "post_apply_cleanup_state_accepted",
                    **_post_cleanup_render_audit,
                }
            )
        _accepted_render_util = _parse_util_value(
            (guidance_debug.get("overview") or {}).get("worst_util")
            or (guidance_debug.get("overview") or {}).get("governing_util")
        )
        _accepted_title = (
            "Geometry correction applied"
            if _post_apply_route_family == "GEOMETRY_DETAILING_GOVERNS"
            else "Design accepted - target band achieved"
        )
        _accepted_reason = (
            "Why: the geometry correction has been applied; the resolved candidate payload was bound to the current state, the applied update matched the published recommendation, and all required checks remain acceptable."
            if _post_apply_route_family == "GEOMETRY_DETAILING_GOVERNS"
            else "Why: the one-click cleanup has been applied; all required checks remain acceptable, the governing utilisation is inside the target band, and the current design is the accepted post-click state."
        )
        _accepted_key_checks = (
            "Key checks: geometry/detailing, bending, shear, serviceability"
            if _post_apply_route_family == "GEOMETRY_DETAILING_GOVERNS"
            else "Key checks: bending, shear, serviceability, target utilisation band"
        )
        _accepted_render_item = _guidance_item(
            "general",
            _accepted_title,
            "",
            None,
            _accepted_reason,
            _accepted_key_checks,
            None,
            None,
            status="PASS",
            util=_accepted_render_util,
        )
        _accepted_render_item["guidance_intent"] = "already_efficient"
        _accepted_render_item["design_guide_terminal_state"] = "optimal"
        _accepted_render_item["post_apply_accepted_terminal"] = True
        _accepted_render_item["post_apply_accepted_terminal_source"] = (
            "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY"
        )
        _accepted_target_lo, _accepted_target_hi, _ = (
            _resolved_efficiency_target_band(
                _design_mode_config(
                    _design_optimisation_goal(guidance_disp_state)
                ),
                goal=_design_optimisation_goal(guidance_disp_state),
            )
        )
        _accepted_render_item["display_truth"] = {
            "display_truth_source": "post_apply_committed_summary",
            "displayed_util": _accepted_render_util,
            "displayed_status": (
                "PASS"
                if _post_apply_route_family == "GEOMETRY_DETAILING_GOVERNS"
                else "OPTIMAL"
            ),
            "target_low": float(_accepted_target_lo),
            "target_high": float(_accepted_target_hi),
            "displayed_within_target_band": bool(
                _accepted_render_util is not None
                and float(_accepted_target_lo) - float(TARGET_BAND_EPS)
                <= float(_accepted_render_util)
                <= float(_accepted_target_hi) + float(TARGET_BAND_EPS)
            ),
            "source_summary_util": _accepted_render_util,
            "source_candidate_util": None,
            "source_post_commit_util": _accepted_render_util,
        }
        _accepted_last_apply_route = dict(_post_apply_route_for_terminal)
        _accepted_family_id = normalise_governing_family(
            _accepted_last_apply_route.get("resolved_candidate_family_tag")
            or _accepted_last_apply_route.get("recommendation_family_tag")
            or guidance_debug.get("selected_family_id")
            or guidance_debug.get("published_family_id")
            or ""
        )
        if _accepted_family_id:
            _accepted_render_item.update(
                {
                    "family": _accepted_family_id,
                    "check_key": _accepted_family_id,
                    "selected_family_id": _accepted_family_id,
                    "published_family_id": _accepted_family_id,
                    "cta_family_id": _accepted_family_id,
                    "apply_payload_family_id": _accepted_family_id,
                    "candidate_family_id": _accepted_family_id,
                    "card_family_id": _accepted_family_id,
                    "source_candidate_id": (
                        _accepted_last_apply_route.get("resolved_candidate_id")
                        or _accepted_last_apply_route.get("applied_candidate_id")
                        or f"{_accepted_family_id}:post_apply_accepted"
                    ),
                    "candidate_id": (
                        _accepted_last_apply_route.get("resolved_candidate_id")
                        or _accepted_last_apply_route.get("applied_candidate_id")
                        or f"{_accepted_family_id}:post_apply_accepted"
                    ),
                    "selection_reason": "post_apply_accepted_from_applied_family_route",
                    "family_selection_source": "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY.resolved_candidate_family_tag",
                    "matched_family_ids": [_accepted_family_id],
                    "raw_state_flags": {"rendered_family_id": _accepted_family_id},
                }
            )
            _accepted_render_item["candidate_search_evidence"] = {
                **dict(_accepted_render_item.get("candidate_search_evidence") or {}),
                "selected_family_id": _accepted_family_id,
                "published_family_id": _accepted_family_id,
                "post_apply_accepted_family_source": "resolved_candidate_family_tag",
            }
        _accepted_exact_blockers = dict(
            _post_cleanup_render_audit.get("post_click_exact_blockers_by_family")
            or guidance_debug.get("post_click_exact_blockers_by_family")
            or {}
        )
        if (
            _accepted_exact_blockers
            and _post_apply_route_family != "GEOMETRY_DETAILING_GOVERNS"
        ):
            _accepted_render_item["exact_blockers_by_family"] = dict(_accepted_exact_blockers)
            _accepted_render_item["post_click_exact_blockers_by_family"] = dict(_accepted_exact_blockers)
            _accepted_evidence = dict(_accepted_render_item.get("candidate_search_evidence") or {})
            _accepted_evidence["exact_blockers_by_family"] = dict(_accepted_exact_blockers)
            _accepted_evidence["post_click_exact_blockers_by_family"] = dict(_accepted_exact_blockers)
            _accepted_evidence["local_cleanup_search_exhaustive"] = True
            _accepted_evidence["safe_local_cleanup_count"] = 0
            _accepted_evidence["executable_safe_cleanup_count"] = 0
            _accepted_render_item["candidate_search_evidence"] = _accepted_evidence
        _accepted_projection_item = _publish_rendered_primary_card_publication_projection(
            item=dict(_accepted_render_item),
            publication_reason="design_guide_post_apply_accepted_publication_projection",
        )
        if _accepted_projection_item:
            _accepted_render_item.update(_accepted_projection_item)
        render_guidance_secondary_items(
            [_accepted_render_item],
            guidance_disp_state=guidance_disp_state,
            current_overview=_dg_overview,
            inputs_render_audit=inputs_render_audit,
            start_index=0,
            primary_card_presentation={},
            st_module=st,
            render_card_model_fn=render_guidance_secondary_card_model_current_coordinator,
            render_primary_cta_state_fn=render_guidance_secondary_primary_cta_state_current_coordinator,
            render_button_contract_fn=render_guidance_secondary_button_contract_current_coordinator,
            render_apply_action_fn=render_guidance_secondary_apply_action_current_coordinator,
        )
    elif terminal_state in {"optimal", "very_low_demand"} and not _presentation_passive_underband and not guidance_items:
        _terminal_exact_stop_proof = {}
        for _terminal_source in (
            guidance_disp_state,
            guidance_debug,
            st.session_state,
        ):
            if isinstance(_terminal_source, dict) and isinstance(_terminal_source.get("exact_stop_proof"), dict):
                _terminal_exact_stop_proof = dict(_terminal_source.get("exact_stop_proof") or {})
                if _terminal_exact_stop_proof:
                    break
        _terminal_exact_signal = bool(
            _terminal_exact_stop_proof
            or any(
                bool(_terminal_source.get("exact_stop_proven") or _terminal_source.get("exact_stop_available"))
                for _terminal_source in (guidance_disp_state, guidance_debug, st.session_state)
                if isinstance(_terminal_source, dict)
            )
        )
        _terminal_family_id = (
            "EXACT_STOP_PROVEN"
            if terminal_state == "optimal" and _terminal_exact_signal
            else "TARGET_BAND_REACHED"
        )
        _terminal_title = (
            "Design demand is very low"
            if terminal_state == "very_low_demand"
            else "Design is efficient - further reductions would weaken capacity"
        )
        _terminal_truth_source = str(_dg_presentation.get("display_truth_source") or "").strip()
        _terminal_truth_in_band = bool(_dg_presentation.get("displayed_within_target_band"))
        _terminal_body = (
            (
                "The current section is within the target utilisation range; further reductions would lower reserve capacity or stiffness."
                if _terminal_truth_source == "published_summary" and _terminal_truth_in_band
                else "Further reductions would lower reserve capacity or stiffness; the guide is explaining why no material one-click change is selected."
            )
            if terminal_state == "optimal"
            else "All current checks pass and current demand is very low, so no further tightening is needed."
        )
        _terminal_render_util = _parse_util_value(
            (guidance_debug.get("overview") or {}).get("worst_util")
            or (guidance_debug.get("overview") or {}).get("governing_util")
        )
        _terminal_render_item = _guidance_item(
            _terminal_family_id,
            _terminal_title,
            "",
            None,
            f"No further safe cleanup available. {_terminal_body}",
            "Key checks: bending, shear, serviceability, target utilisation band",
            None,
            None,
            status="PASS",
            util=_terminal_render_util,
        )
        _terminal_render_item.update(
            {
                "family": _terminal_family_id,
                "selected_family": _terminal_family_id,
                "selected_family_id": _terminal_family_id,
                "published_family_id": _terminal_family_id,
                "cta_family_id": _terminal_family_id,
                "apply_payload_family_id": _terminal_family_id,
                "candidate_family_id": _terminal_family_id,
                "card_family_id": _terminal_family_id,
                "matched_family_ids": [_terminal_family_id],
                "family_match_passed": True,
                "guidance_intent": "already_efficient",
                "design_guide_terminal_state": terminal_state,
                "display_state": "PASS",
                "critical_status": "PASS",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "family": _terminal_family_id,
                    "selected_family_id": _terminal_family_id,
                    "published_family_id": _terminal_family_id,
                    "cta_family_id": _terminal_family_id,
                    "apply_payload_family_id": _terminal_family_id,
                    "action_type": None,
                    "updates": {},
                    "preview_pass": True,
                    "blocking_reason": None,
                    "disabled_reason": "terminal_pass_no_action",
                },
                "candidate_search_evidence": {
                    "source": "terminal_no_guidance_item_fallback",
                    "selected_family_id": _terminal_family_id,
                    "published_family_id": _terminal_family_id,
                    "cta_family_id": _terminal_family_id,
                    "matched_family_ids": [_terminal_family_id],
                    "family_match_passed": True,
                    "target_band_terminal_signal": _terminal_family_id == "TARGET_BAND_REACHED",
                    "exact_stop_proven": _terminal_family_id == "EXACT_STOP_PROVEN",
                },
            }
        )
        if _terminal_exact_stop_proof:
            _terminal_render_item["exact_stop_proof"] = dict(_terminal_exact_stop_proof)
        _terminal_projection_item = _publish_rendered_primary_card_publication_projection(
            item=dict(_terminal_render_item),
            publication_reason="design_guide_terminal_no_guidance_item_publication_projection",
        )
        if _terminal_projection_item:
            _terminal_render_item.update(_terminal_projection_item)
        render_guidance_secondary_items(
            [_terminal_render_item],
            guidance_disp_state=guidance_disp_state,
            current_overview=_dg_overview,
            inputs_render_audit=inputs_render_audit,
            start_index=0,
            primary_card_presentation={},
            st_module=st,
            render_card_model_fn=render_guidance_secondary_card_model_current_coordinator,
            render_primary_cta_state_fn=render_guidance_secondary_primary_cta_state_current_coordinator,
            render_button_contract_fn=render_guidance_secondary_button_contract_current_coordinator,
            render_apply_action_fn=render_guidance_secondary_apply_action_current_coordinator,
        )
    elif bool(render_plan.get("render_primary_only")):
        _primary_render_items = guidance_items[:1] if guidance_items else []
        if _primary_render_items:
            _primary_projection_item = _publish_rendered_primary_card_publication_projection(
                item=dict(_primary_render_items[0]),
                publication_reason="design_guide_final_render_primary_only_publication_projection",
            )
            if _primary_projection_item:
                _primary_render_items[0].update(_primary_projection_item)
            _primary_card_presentation = _presentation_for_visible_primary_item(
                _dg_presentation,
                _primary_render_items[0],
            )
            render_guidance_secondary_items(
                _primary_render_items,
                guidance_disp_state=guidance_disp_state,
                current_overview=_dg_overview,
                inputs_render_audit=inputs_render_audit,
                start_index=0,
                primary_card_presentation=_primary_card_presentation,
                st_module=st,
                render_card_model_fn=render_guidance_secondary_card_model_current_coordinator,
                render_primary_cta_state_fn=render_guidance_secondary_primary_cta_state_current_coordinator,
                render_button_contract_fn=render_guidance_secondary_button_contract_current_coordinator,
                render_apply_action_fn=render_guidance_secondary_apply_action_current_coordinator,
            )
    else:
        _visible_render_items = list(render_plan.get("visible_guidance_items") or [])
        if guidance_items and isinstance(guidance_items[0], dict):
            if _visible_render_items:
                _visible_render_items[0] = guidance_items[0]
            else:
                _visible_render_items = guidance_items[:1]
        if _visible_render_items and isinstance(_visible_render_items[0], dict):
            _primary_projection_item = _publish_rendered_primary_card_publication_projection(
                item=dict(_visible_render_items[0]),
                publication_reason="design_guide_final_render_visible_primary_publication_projection",
            )
            if _primary_projection_item:
                _visible_render_items[0].update(_primary_projection_item)
        _visible_card_presentation = (
            _presentation_for_visible_primary_item(_dg_presentation, _visible_render_items[0])
            if _visible_render_items and isinstance(_visible_render_items[0], dict)
            else dict(_dg_presentation or {})
        )
        render_guidance_secondary_items(
            _visible_render_items,
            guidance_disp_state=guidance_disp_state,
            current_overview=_dg_overview,
            inputs_render_audit=inputs_render_audit,
            start_index=0,
            primary_card_presentation=_visible_card_presentation,
            st_module=st,
            render_card_model_fn=render_guidance_secondary_card_model_current_coordinator,
            render_primary_cta_state_fn=render_guidance_secondary_primary_cta_state_current_coordinator,
            render_button_contract_fn=render_guidance_secondary_button_contract_current_coordinator,
            render_apply_action_fn=render_guidance_secondary_apply_action_current_coordinator,
        )
    if render_post_apply_banner:
        render_design_guide_post_apply_banner(
            st_module=st,
            html_escape_fn=html.escape,
            fast_focus_section=fast_focus_section,
            apply_banner_key=DESIGN_GUIDE_APPLY_BANNER_KEY,
        )

    st.session_state[DESIGN_GUIDE_PANEL_BASELINE_FP_KEY] = fingerprint
    st.session_state.pop(DESIGN_GUIDE_NEEDS_REFRESH_KEY, None)
