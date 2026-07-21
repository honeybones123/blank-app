"""Current Design Guide coordinators for the Inputs shell.

This module is a mechanical extraction of the remaining Design Guide current
coordinator layer from ``inputs_page.py``. The deeper helper surfaces are still
provided through ``configure_design_guide_current_provider`` until their own
focused extraction slices remove that provider dependency.
"""

from __future__ import annotations

import html
import json
import os
import sys
import time
from typing import Any

from design_brain.final_publication import build_final_design_guide_publication
from inputs_page_modules.design_guide.render_coordinators import (
    render_design_guide_component_cta,
    render_design_guide_post_apply_banner,
    render_guidance_secondary_items,
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
    'DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY',
    'DESIGN_GUIDE_RECO_TRACE_KEY',
    'DESIGN_GUIDE_REFERENCE_B_KEY',
    'DESIGN_GUIDE_SESSION_ANCHOR_D_KEY',
    'DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY',
    'DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY',
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
    '_design_guide_cached_debug_bundle_complete',
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
    '_direct_target_band_guidance_item',
    '_ensure_design_guide_debug_trace_coherent',
    '_evaluate_auto_design_candidate',
    '_first_actionable_guidance_item',
    '_float_from_state',
    '_final_publication_cta_authority_payload',
    '_get_cached_design_guide_guidance',
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
    '_maybe_promote_safe_local_cleanup_primary',
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
    '_record_rendered_design_guide_primary_apply_payload',
    '_render_auto_design_main_panel_status',
    '_repair_incomplete_design_guide_cache_debug',
    '_reset_design_guide_reco_trace',
    '_resolve_design_actions_from_state',
    '_resolve_recommendation_updates',
    '_resolved_efficiency_target_band',
    '_resolved_inputs_summary_state',
    '_set_cached_design_guide_guidance',
    '_set_design_guide_primary_payload_binding_audit',
    '_shared_state_snapshot',
    '_shear_reinforcement_is_active',
    '_shear_tightening_as_local_cleanup_item',
    '_suppress_redundant_guidance_items',
    '_sync_auto_design_mode_tracking',
    '_sync_pending_recommendation_from_guidance',
    'identify_materially_overprovided_non_governing_families',
    'legacy_item_from_decision',
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
    unresolved = list(audit.get("post_click_unresolved_low_util_families") or [])
    if unresolved:
        return False
    exact_blockers = audit.get("post_click_exact_blockers_by_family") or {}
    return isinstance(exact_blockers, dict) and bool(exact_blockers)


def _normalised_render_family_id(value: Any, *, title: str = "") -> str:
    raw = str(value or "").strip()
    upper = raw.upper()
    if upper in {
        "COMBINED_BENDING_SHEAR_FAIL",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "BENDING_FAIL_GOVERNS",
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
    if lowered in {"combined", "bending_shear", "combined_bending_shear"} or (
        "bending" in title_l and "shear" in title_l
    ):
        return "COMBINED_BENDING_SHEAR_FAIL"
    if lowered == "shear":
        return "SHEAR_FAIL_GOVERNS"
    if lowered == "bending":
        return "BENDING_FAIL_GOVERNS"
    return raw


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

    selected_family = _normalised_render_family_id(
        first(
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
    if not selected_family:
        return ""
    matched_family_ids = first("matched_family_ids") or [selected_family]
    if isinstance(matched_family_ids, str):
        matched_family_ids = [matched_family_ids] if matched_family_ids else []
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
    candidate_id = str(
        first("source_candidate_id", "candidate_id", "selected_candidate_id")
        or "rendered_primary_candidate"
    ).strip()
    attrs = {
        "data-selected-family-id": selected_family,
        "data-selected-family": selected_family,
        "data-selection-reason": first("selection_reason", "selected_family_reason")
        or "rendered_design_guide_card_contract",
        "data-published-family-id": _normalised_render_family_id(
            first("published_family_id") or selected_family,
            title=display_title,
        ),
        "data-cta-family-id": _normalised_render_family_id(
            first("cta_family_id") or selected_family,
            title=display_title,
        ),
        "data-apply-payload-family-id": _normalised_render_family_id(
            first("apply_payload_family_id") or selected_family,
            title=display_title,
        ),
        "data-candidate-family-id": _normalised_render_family_id(
            first("candidate_family_id") or selected_family,
            title=display_title,
        ),
        "data-card-family-id": _normalised_render_family_id(
            first("card_family_id") or selected_family,
            title=display_title,
        ),
        "data-family-selection-source": first("family_selection_source")
        or "rendered_design_guide_card_contract",
        "data-family-selection-contract": first("family_selection_contract")
        or "family_selection_contract",
        "data-family-chooser-contract": first("family_chooser_contract")
        or "family_chooser_contract",
        "data-rejected-families": rejected_families,
        "data-selection-evidence": first("selection_evidence") or {},
        "data-matched-family-ids": matched_family_ids,
        "data-raw-state-flags": first("raw_state_flags") or {"rendered_family_id": selected_family},
        "data-family-match-passed": first("family_match_passed") if first("family_match_passed") != "" else True,
        "data-family-match-violation-reason": first("family_match_violation_reason"),
        "data-family-route-owner": first("family_route_owner")
        or (
            "design_brain.families.combined_bending_shear_fail.CombinedBendingShearFailFamily"
            if selected_family == "COMBINED_BENDING_SHEAR_FAIL"
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
        "data-render-cta-payload-id": first("render_cta_payload_id")
        or f"{selected_family}:{candidate_id}",
        "data-render-gate-condition": bool(button.get("enabled") or button.get("actionable")),
        "data-render-gate-pres-show-apply": bool(button.get("enabled") or button.get("actionable")),
        "data-render-gate-effective-action": button.get("action_type") or item_d.get("action_type") or "",
        "data-render-gate-terminal-exact": False,
        "data-render-gate-button-enabled": bool(button.get("enabled") or button.get("actionable")),
        "data-render-gate-vm-cta-enabled": bool(button.get("enabled") or button.get("actionable")),
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

    cta = dict((cta_authority or {}).get("cta") or publication_d.get("cta") or {})
    display = dict(publication_d.get("display") or {})
    evidence = dict(publication_d.get("evidence") or {})
    selected_family = str(
        publication_d.get("selected_family")
        or item_d.get("selected_family_id")
        or item_d.get("published_family_id")
        or item_d.get("cta_family_id")
        or button_contract.get("family")
        or ""
    ).strip()
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
        "final_publication_cta_hash": (cta_authority or {}).get("cta_hash"),
        "final_publication_display_hash": display.get("final_card_model_hash")
        or display.get("visible_wording_hash"),
    }
    return {
        "final_design_guide_publication": publication_d,
        "final_publication_verifier_payload": verifier_payload,
        "final_publication_publication_hash": publication_d.get("publication_hash"),
        "publication_hash": publication_d.get("publication_hash"),
        "final_publication_authority_hash": publication_d.get("publication_hash"),
        "final_publication_cta_hash": (cta_authority or {}).get("cta_hash"),
        "final_publication_display_hash": verifier_payload.get("final_publication_display_hash"),
        "selected_family_id": selected_family,
        "published_family_id": selected_family,
        "cta_family_id": selected_family,
    }


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
    if is_primary_guidance_card and _design_guide_button_contract_enabled(button_contract):
        contract_updates = dict(button_contract.get("updates") or {})
        if set(contract_updates) and set(contract_updates).issubset(_COMPOUND_SHEAR_UPDATE_KEYS):
            current_shear_util = _parse_util_value(dict((current_overview or {}).get("utils") or {}).get("shear"))
            if current_shear_util is not None and float(current_shear_util) < float(FINAL_ACCEPTED_MIN_FAMILY_UTIL):
                trial_state = dict(guidance_disp_state)
                trial_state.update(contract_updates)
                preview_shear_util = None
                try:
                    preview_candidate = _evaluate_auto_design_candidate(
                        guidance_disp_state,
                        updates=contract_updates,
                        source="design_guide_render_shear_family_threshold_probe",
                        label=str(item.get("title_main") or "Design Guide candidate"),
                        action_type=str(button_contract.get("action_type") or item.get("action_type") or ""),
                    )
                    preview_shear_util = _parse_util_value(
                        dict((preview_candidate or {}).get("overview") or {}).get("utils", {}).get("shear")
                    )
                except Exception:
                    preview_shear_util = None
                if preview_shear_util is None or float(preview_shear_util) < float(FINAL_ACCEPTED_MIN_FAMILY_UTIL):
                    button_contract = {
                        **dict(button_contract),
                        "actionable": False,
                        "blocking_reason": "blocked_shear_cleanup_does_not_reach_final_family_threshold",
                    }
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
        if not _design_guide_button_contract_enabled(button_contract):
            st.session_state.pop(DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY, None)
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
    if item.get("action_type") and _pres_show_apply:
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
            if isinstance(rec, dict) and rec:
                rec_meta = dict(rec.get("meta") or {})
                rec_status = str(rec_meta.get("status") or "").strip()
                if rec_status == "no_action":
                    st.success("Design is efficient - further reductions would weaken capacity")
                    util_value = rec_meta.get("util")
                    try:
                        if util_value is not None:
                            st.caption(f"Current utilisation: {float(util_value):.2f} (target ≈ 0.85)")
                    except Exception:
                        pass
                    return {"continue_item": True}
                if not _recommendation_commit_eligible(rec):
                    blocked_reason = _recommendation_blocked_reason(rec) or "candidate_not_commit_eligible"
                    st.markdown(
                        f"""
<div class='fast-guidance-secondary' style="border:1px solid rgba(49,51,63,0.18);background:rgba(49,51,63,0.04);">
  <strong>Recommendation is advisory, not directly executable</strong><br>
  Commit gate: {html.escape(blocked_reason)}.
</div>
""",
                        unsafe_allow_html=True,
                    )
                    return {"continue_item": True}
                if _suppress_one_click_cta:
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
                contract_action_type = str(button_contract.get("action_type") or "").strip()
                contract_family = str(button_contract.get("family") or "").strip()
                primary_route_target = (
                    "handle_apply_buttons"
                    if (
                        contract_action_type == "apply_resolved_candidate"
                        or (
                            _recommendation_commit_eligible(rec)
                            and str(rec.get("action_type") or "").strip() == contract_action_type
                        )
                    )
                    else "handle_auto_design"
                )
                apply_label = (
                    "Run one-click auto design"
                )
                _record_rendered_design_guide_primary_apply_payload(
                    item=dict(item),
                    rec=dict(rec),
                    button_contract=dict(button_contract),
                    state=guidance_disp_state,
                )
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
    elif item.get("action_type"):
        reason = str(button_contract.get("blocking_reason") or "button_contract_not_enabled").strip()
        preview_text = "passed" if bool(button_contract.get("preview_pass")) else "did not pass"
        st.markdown(
            f"""
<div class='fast-guidance-secondary' style="border:1px solid rgba(49,51,63,0.18);background:rgba(49,51,63,0.04);">
  <strong>Recommendation is advisory, not directly executable</strong><br>
  Button contract: {html.escape(reason)}. Preview {html.escape(preview_text)}.
</div>
""",
            unsafe_allow_html=True,
        )
    elif item.get("primary_action"):
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
    inputs_render_audit: dict[str, str] | None,
    start_index: int,
    primary_card_presentation: dict | None,
) -> dict:
    _bind_design_guide_current_globals()
    badge_label = _guidance_card_label(item)
    if primary_card_presentation is not None and idx == 0 and start_index == 0:
        item_bucket = str(primary_card_presentation.get("css_bucket") or item.get("bucket") or "pass")
        use_success_style = bool(primary_card_presentation.get("use_success_style"))
    else:
        item_bucket = item["bucket"] if idx == 0 and start_index == 0 else ("warn" if item["bucket"] == "fail" else item["bucket"])
    if idx == 0 and start_index == 0 and item_bucket == "fail":
        util_v = _parse_util_value(item.get("util"))
        if util_v is not None and util_v <= 1.0:
            # Display-only: recommendation card at/under 100% shows close/warn styling.
            item_bucket = "warn"
    use_success_style = (
        idx == 0
        and start_index == 0
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
    if (
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
    if _presentation_controls_primary and not _presentation_show_apply:
        core_body = ""
    else:
        core_body = (
            compact_primary_html
            if compact_primary_actionable
            else f"{why_html}{proposed_html}{start_steps_html}{before_after_html}"
        )
    body_html = f"{pres_hint_html}{core_body}" if pres_hint_html else core_body
    card_contract_attrs = _design_guide_card_contract_attrs(item, display_title=display_title)
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
    st.markdown("### Design Guide")
    _render_auto_design_main_panel_status()
    _stage("after_heading")
    current_state, _ = _resolved_inputs_summary_state()
    _stage("after_summary_state")
    if DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY not in st.session_state:
        st.session_state[DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY] = None
    if DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY not in st.session_state:
        st.session_state[DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY] = None
    fingerprint = _get_design_guide_fp(current_state)
    sidebar_debug = _design_guide_sidebar_debug_enabled()
    if sidebar_debug:
        _reset_design_guide_reco_trace()
    else:
        st.session_state.pop(DESIGN_GUIDE_RECO_TRACE_KEY, None)

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

    cached_items, cached_debug, cache_hit = _get_cached_design_guide_guidance(fingerprint)
    cache_hit_initial = bool(cache_hit)
    cache_debug_complete_initial = _design_guide_cached_debug_bundle_complete(dict(cached_debug or {}))
    cache_repair_attempted = False
    cache_recompute_forced = False
    cache_recompute_success = False

    force_recompute = not cache_hit_initial
    if cache_hit_initial:
        guidance_items_raw = list(cached_items or [])
        guidance_debug = dict(cached_debug or {})
        if str(guidance_debug.get("design_guide_algorithm_version") or "") != DESIGN_GUIDE_ALGORITHM_VERSION:
            force_recompute = True
            cache_recompute_forced = True
            guidance_debug["cache_recompute_reason"] = "design_guide_algorithm_version_changed"
        cache_repair_attempted = bool(
            _repair_incomplete_design_guide_cache_debug(
                current_state,
                guidance_items_raw,
                guidance_debug,
            ),
        )

    if force_recompute:
        _stage("before_apply_ui_state")
        cache_recompute_forced = True
        if cache_hit_initial:
            _clear_design_guide_transient_ui_state(clear_history=False, preserve_apply_banner=True)
        _apply_guidance_ui_state(
            current_state,
            preserve_apply_banner=True,
        )
        _stage("before_compute_guidance")
        guidance_payload = _compute_design_guidance_items(
            current_state,
            guidance_debug_verbose=sidebar_debug,
            debug_enabled=sidebar_debug,
        )
        _stage("after_compute_guidance")
        guidance_items_raw = list(guidance_payload.get("guidance_items") or [])
        guidance_debug = dict(guidance_payload.get("debug_trace") or {})
        primary_item = guidance_items_raw[0] if guidance_items_raw else {}
        if str((primary_item or {}).get("action_type") or "") == "apply_resolved_candidate":
            st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_KEY, None)
            st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)
        guidance_cache_hit = False
        guidance_fresh_compute_used = True
        cache_recompute_success = True
    else:
        guidance_cache_hit = True

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
    engine_decision_debug = dict(
        guidance_debug.get("design_guide_engine_decision")
        or st.session_state.get("_design_guide_engine_decision")
        or {}
    )
    engine_card_debug = dict(engine_decision_debug.get("card") or {})
    engine_button_debug = dict(engine_decision_debug.get("button_contract") or {})
    engine_outcome_debug = dict(engine_decision_debug.get("target_band_outcome") or {})
    engine_trace_debug = dict(engine_decision_debug.get("debug") or {})
    engine_candidate_search_evidence = dict(
        engine_card_debug.get("candidate_search_evidence")
        or engine_trace_debug.get("candidate_search_evidence")
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
        "engine_decision_debug": dict(engine_decision_debug or {}),
        "engine_card_debug": dict(engine_card_debug or {}),
        "engine_button_debug": dict(engine_button_debug or {}),
        "engine_outcome_debug": dict(engine_outcome_debug or {}),
        "engine_trace_debug": dict(engine_trace_debug or {}),
        "engine_candidate_search_evidence": dict(engine_candidate_search_evidence or {}),
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
    engine_decision_debug = dict(_debug_bundle_context["engine_decision_debug"] or {})
    engine_card_debug = dict(_debug_bundle_context["engine_card_debug"] or {})
    engine_button_debug = dict(_debug_bundle_context["engine_button_debug"] or {})
    engine_outcome_debug = dict(_debug_bundle_context["engine_outcome_debug"] or {})
    engine_trace_debug = dict(_debug_bundle_context["engine_trace_debug"] or {})
    engine_candidate_search_evidence = dict(_debug_bundle_context["engine_candidate_search_evidence"] or {})
    _final_publication_debug = _final_publication_debug_projection(
        item=primary_item,
        debug=guidance_debug,
        publication_reason="design_guide_debug_bundle_current_primary",
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
        "primary_card_title": engine_card_debug.get("title"),
        "primary_card_intent": engine_card_debug.get("intent"),
        "primary_displayed_util": engine_card_debug.get("displayed_util"),
        "primary_display_truth_source": engine_card_debug.get("display_truth_source"),
        "primary_target_low": engine_card_debug.get("target_low"),
        "primary_target_high": engine_card_debug.get("target_high"),
        "primary_preview_util": engine_outcome_debug.get("preview_util"),
        "primary_current_util": engine_outcome_debug.get("current_util"),
        "primary_lands_in_target_band": engine_outcome_debug.get("lands_in_target_band"),
        "primary_allowed_blocker": engine_outcome_debug.get("allowed_blocker"),
        "button_contract_enabled": engine_button_debug.get("enabled"),
        "button_contract_updates": dict(engine_button_debug.get("updates") or {}),
        "button_contract_preview_pass": engine_button_debug.get("preview_pass"),
        "button_contract_blocking_reason": engine_button_debug.get("blocking_reason"),
        "design_guide_engine_decision": dict(engine_decision_debug),
        "design_guide_engine_decision_reason": engine_trace_debug.get("decision_reason"),
        "design_guide_engine_suppressed_count": engine_trace_debug.get("suppressed_count"),
        "design_guide_engine_suppressed_reasons": list(engine_trace_debug.get("suppressed_reasons") or []),
        "candidate_search_evidence": dict(engine_candidate_search_evidence),
        "family_utils": dict(engine_decision_debug.get("family_utils") or engine_card_debug.get("family_utils") or {}),
        "materially_overprovided_families": list(
            engine_decision_debug.get("materially_overprovided_families")
            or engine_card_debug.get("materially_overprovided_families")
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
        "local_cleanup_search_ran": (
            engine_decision_debug.get("local_cleanup_search_ran")
            if engine_decision_debug.get("local_cleanup_search_ran") is not None
            else engine_card_debug.get("local_cleanup_search_ran")
        ),
        "local_cleanup_search_exhaustive": (
            engine_decision_debug.get("local_cleanup_search_exhaustive")
            if engine_decision_debug.get("local_cleanup_search_exhaustive") is not None
            else engine_card_debug.get("local_cleanup_search_exhaustive")
        ),
        "safe_local_cleanup_count": (
            engine_decision_debug.get("safe_local_cleanup_count")
            if engine_decision_debug.get("safe_local_cleanup_count") is not None
            else engine_card_debug.get("safe_local_cleanup_count")
        ),
        "executable_safe_cleanup_count": (
            engine_decision_debug.get("executable_safe_cleanup_count")
            if engine_decision_debug.get("executable_safe_cleanup_count") is not None
            else engine_card_debug.get("executable_safe_cleanup_count")
        ),
        "advisory_cleanup_count": (
            engine_decision_debug.get("advisory_cleanup_count")
            if engine_decision_debug.get("advisory_cleanup_count") is not None
            else engine_card_debug.get("advisory_cleanup_count")
        ),
        "local_cleanup_candidates": list(
            engine_decision_debug.get("local_cleanup_candidates")
            or engine_card_debug.get("local_cleanup_candidates")
            or []
        ),
        "rejected_local_cleanup_count": (
            engine_decision_debug.get("rejected_local_cleanup_count")
            if engine_decision_debug.get("rejected_local_cleanup_count") is not None
            else engine_card_debug.get("rejected_local_cleanup_count")
        ),
        "local_cleanup_blocked_reasons": list(
            engine_decision_debug.get("local_cleanup_blocked_reasons")
            or engine_card_debug.get("local_cleanup_blocked_reasons")
            or []
        ),
        "terminal_state_reason": (
            engine_decision_debug.get("terminal_state_reason")
            or engine_card_debug.get("terminal_state_reason")
        ),
        "terminal_state_blocked_by_local_cleanup": bool(
            engine_decision_debug.get("terminal_state_blocked_by_local_cleanup")
            or engine_card_debug.get("terminal_state_blocked_by_local_cleanup")
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
    _dg_overview = guidance_debug.get("overview")
    if not isinstance(_dg_overview, dict):
        try:
            _dg_overview = _collect_design_overview(
                guidance_disp_state,
                context=_build_design_actions_context(guidance_disp_state),
            )
        except Exception:
            _dg_overview = {}
    _dg_mode_cfg = _design_mode_config(_design_optimisation_goal(guidance_disp_state))
    _local_cleanup_seed_items = guidance_items
    if not _local_cleanup_seed_items:
        try:
            _local_cleanup_seed_items = [_passing_guidance_item(guidance_disp_state, _dg_overview)]
        except Exception:
            _local_cleanup_seed_items = []
    _skip_final_local_cleanup_adapter = (
        str(guidance_debug.get("guidance_branch") or "")
        == "target_band_active_shear_local_cleanup_fast_path"
    )
    if _local_cleanup_seed_items and not _skip_final_local_cleanup_adapter:
        _render_local_cleanup_items, _render_local_cleanup_meta = _maybe_promote_safe_local_cleanup_primary(
            _local_cleanup_seed_items,
            state=guidance_disp_state,
            overview=dict(_dg_overview or {}),
            efficiency_state=dict(efficiency_state or {}),
            mode_config=_dg_mode_cfg,
            debug_sink=guidance_debug,
            source="render_fast_design_guidance_panel_final_adapter",
        )
        if bool((_render_local_cleanup_meta or {}).get("local_cleanup_promoted")):
            guidance_items = list(_render_local_cleanup_items or [])
            terminal_state = None
            terminal_state_source = "blocked_by_safe_local_cleanup"
            guidance_debug["design_guide_terminal_state"] = None
            guidance_debug["design_guide_terminal_state_source"] = terminal_state_source
            guidance_debug["design_guide_has_actionable_recommendation"] = True
        elif terminal_state in {"optimal", "very_low_demand"}:
            _family_utils, _material_families, _governing_family = identify_materially_overprovided_non_governing_families(_dg_overview)
            if _material_families:
                try:
                    _direct_cleanup_item = _direct_target_band_guidance_item(
                        guidance_disp_state,
                        dict(_dg_overview or {}),
                        _dg_mode_cfg,
                        strengthening=False,
                        debug_sink=guidance_debug,
                    )
                except Exception:
                    _direct_cleanup_item = None
                if isinstance(_direct_cleanup_item, dict) and _guidance_item_is_resolved_one_click(_direct_cleanup_item):
                    _direct_cleanup_item["guidance_intent"] = "optional_cleanup"
                    _direct_cleanup_item["local_cleanup_candidate"] = True
                    guidance_items = [_direct_cleanup_item]
                    terminal_state = None
                    terminal_state_source = "blocked_by_safe_local_cleanup"
                    guidance_debug["family_utils"] = dict(_family_utils)
                    guidance_debug["materially_overprovided_families"] = list(_material_families)
                    guidance_debug["local_cleanup_search_ran"] = True
                    guidance_debug["local_cleanup_search_exhaustive"] = True
                    _direct_evidence = dict(_direct_cleanup_item.get("candidate_search_evidence") or {})
                    guidance_debug["local_cleanup_candidate_search_evidence"] = dict(_direct_evidence)
                    guidance_debug["safe_local_cleanup_count"] = int(_direct_evidence.get("safe_executor_backed_candidates_count") or 1)
                    guidance_debug["local_cleanup_candidate_inventory"] = list(_direct_evidence.get("safe_executor_backed_candidates") or [])
                    guidance_debug["local_cleanup_candidate_inventory_count"] = len(guidance_debug["local_cleanup_candidate_inventory"])
                    guidance_debug["candidate_inventory_count"] = guidance_debug["local_cleanup_candidate_inventory_count"]
                    guidance_debug["terminal_state_blocked_by_local_cleanup"] = True
                    guidance_debug["design_guide_terminal_state"] = None
                    guidance_debug["design_guide_terminal_state_source"] = terminal_state_source
                    guidance_debug["design_guide_has_actionable_recommendation"] = True
    _dg_presentation = _build_design_guide_presentation_state(
        primary_item=guidance_items[0] if guidance_items else None,
        overview=_dg_overview,
        efficiency_state=efficiency_state,
        disp_state=guidance_disp_state,
        mode_config=_dg_mode_cfg,
        recommendation_result=_recommendation_result,
        pending_recommendation=pending_recommendation,
    )
    _dg_engine_decision = dict(st.session_state.get("_design_guide_engine_decision") or {})
    if (
        _local_cleanup_post_apply_acceptance_matches(guidance_disp_state)
        and terminal_state in {"optimal", "very_low_demand"}
    ):
        _dg_engine_decision = {}
        st.session_state["_design_guide_engine_decision"] = {}
    _engine_presentation = dict(_dg_engine_decision.get("presentation") or {})
    if _engine_presentation:
        _dg_presentation = _engine_presentation
    if guidance_items and isinstance(guidance_items[0], dict):
        _engine_terminal_item = legacy_item_from_decision(
            guidance_items[0],
            _dg_engine_decision,
        )
        if isinstance(_engine_terminal_item, dict) and _engine_terminal_item is not guidance_items[0]:
            guidance_items[0] = _engine_terminal_item
            _terminal_display_truth = dict(_engine_terminal_item.get("display_truth") or {})
            _terminal_button_contract = dict(_engine_terminal_item.get("button_contract") or {})
            guidance_debug["primary_guidance_intent"] = "already_efficient"
            guidance_debug["guidance_intent_items"] = _design_guide_guidance_intent_debug_rows(guidance_items)
            guidance_debug["displayed_guidance_intent_items"] = list(
                guidance_debug["guidance_intent_items"]
            )
            guidance_debug["primary_button_contract"] = dict(_terminal_button_contract)
            guidance_debug["primary_display_truth"] = dict(_terminal_display_truth)
            guidance_debug["selected_action_type"] = None
            guidance_debug["selected_title"] = _engine_terminal_item.get("title_main")
            guidance_debug["guidance_branch"] = "already_efficient_target_band_achieved"
            guidance_debug["design_guide_terminal_state"] = "optimal"
            guidance_debug["design_guide_has_actionable_recommendation"] = False
            guidance_debug["design_guide_terminal_positive"] = True
            _terminal_overview = dict(guidance_debug.get("overview") or {})
            _, _terminal_material_families, _ = identify_materially_overprovided_non_governing_families(_terminal_overview)
            if "shear" in {str(f or "").strip().lower() for f in _terminal_material_families}:
                _terminal_shear_cleanup = _shear_tightening_as_local_cleanup_item(
                    guidance_disp_state,
                    _terminal_overview,
                    dict(guidance_debug.get("efficiency_tightening_state") or {}),
                )
                if isinstance(_terminal_shear_cleanup, dict) and _guidance_item_is_resolved_one_click(_terminal_shear_cleanup):
                    guidance_items[0] = _terminal_shear_cleanup
                    _dg_engine_decision = {}
                    st.session_state["_design_guide_engine_decision"] = {}
                    _dg_presentation = {}
                    terminal_state = None
                    guidance_debug["primary_guidance_intent"] = "optional_cleanup"
                    guidance_debug["guidance_intent_items"] = _design_guide_guidance_intent_debug_rows(guidance_items)
                    guidance_debug["displayed_guidance_intent_items"] = list(guidance_debug["guidance_intent_items"])
                    guidance_debug["primary_button_contract"] = dict(_terminal_shear_cleanup.get("button_contract") or {})
                    guidance_debug["primary_display_truth"] = dict(_terminal_shear_cleanup.get("display_truth") or {})
                    guidance_debug["selected_action_type"] = _terminal_shear_cleanup.get("action_type")
                    guidance_debug["selected_title"] = _terminal_shear_cleanup.get("title_main")
                    guidance_debug["guidance_branch"] = "terminal_shear_material_cleanup_override"
                    guidance_debug["design_guide_terminal_state"] = None
                    guidance_debug["design_guide_has_actionable_recommendation"] = True
                    guidance_debug["design_guide_terminal_positive"] = False
                    guidance_debug["materially_overprovided_families"] = list(_terminal_material_families)
                    guidance_debug["local_cleanup_search_ran"] = True
                    guidance_debug["local_cleanup_search_exhaustive"] = True
                    guidance_debug["safe_local_cleanup_count"] = 1
                    guidance_debug["executable_safe_cleanup_count"] = 1
                    _recommendation_result = _recommendation_result_for_primary_guidance_card(
                        guidance_items,
                        guidance_disp_state,
                        branch=guidance_debug.get("guidance_branch"),
                        request_kind="design_guide",
                    )
                    guidance_debug["recommendation_result"] = _recommendation_result
    return {
        "_dg_overview": _dg_overview,
        "_dg_presentation": _dg_presentation,
        "_dg_engine_decision": dict(_dg_engine_decision or {}),
        "terminal_state": terminal_state,
        "terminal_state_source": terminal_state_source,
        "guidance_items": list(guidance_items or []),
        "_recommendation_result": _recommendation_result,
    }


def render_design_guide_feedback_cta_current_coordinator(
    *,
    _dg_overview: dict | None,
    guidance_debug: dict,
    _dg_engine_decision: dict,
) -> None:
    _bind_design_guide_current_globals()
    _feedback_cta_state = _one_click_feedback_cta_state(_dg_overview)
    _oc_feedback = dict(_feedback_cta_state.get("feedback") or {})
    _oc_feedback_status = str(_feedback_cta_state.get("status") or "")
    _oc_feedback_reason = str(_feedback_cta_state.get("reason") or "")
    _oc_feedback_fp = dict(_feedback_cta_state.get("feedback_fail_fingerprint") or {})
    _dg_current_fail_fingerprint = dict(_feedback_cta_state.get("current_fail_fingerprint") or {})
    _blocked_feedback_matches_current_state = bool(_feedback_cta_state.get("matches_current_state"))
    _stale_blocked_feedback_cleared = bool(_feedback_cta_state.get("stale_cleared"))
    guidance_debug["design_guide_feedback_status"] = _oc_feedback_status or None
    guidance_debug["design_guide_feedback_reason"] = _oc_feedback_reason or None
    guidance_debug["design_guide_feedback_fail_fingerprint"] = dict(_oc_feedback_fp)
    guidance_debug["design_guide_current_fail_fingerprint"] = dict(_dg_current_fail_fingerprint)
    guidance_debug["design_guide_blocked_feedback_matches_current_state"] = bool(
        _blocked_feedback_matches_current_state
    )
    guidance_debug["design_guide_stale_blocked_feedback_cleared"] = bool(
        _stale_blocked_feedback_cleared
    )
    guidance_debug["design_guide_stale_blocked_feedback_reason"] = (
        "fail_fingerprint_changed" if _stale_blocked_feedback_cleared else None
    )
    _cta_suppressed = bool(_blocked_feedback_matches_current_state)
    guidance_debug["design_guide_one_click_cta_suppressed"] = bool(_cta_suppressed)
    guidance_debug["design_guide_one_click_cta_suppressed_reason"] = (
        _oc_feedback_reason if _cta_suppressed else None
    )
    guidance_debug["design_guide_engine_decision"] = dict(_dg_engine_decision)
    if isinstance(st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY), dict):
        _engine_card = dict(_dg_engine_decision.get("card") or {})
        _engine_button = dict(_dg_engine_decision.get("button_contract") or {})
        _engine_outcome = dict(_dg_engine_decision.get("target_band_outcome") or {})
        _engine_trace = dict(_dg_engine_decision.get("debug") or {})
        _engine_candidate_search_evidence = dict(
            _engine_card.get("candidate_search_evidence")
            or _engine_trace.get("candidate_search_evidence")
            or {}
        )
        st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY].update(
            {
                "design_guide_engine_decision": dict(_dg_engine_decision),
                "primary_card_title": _engine_card.get("title"),
                "primary_card_intent": _engine_card.get("intent"),
                "primary_displayed_util": _engine_card.get("displayed_util"),
                "primary_display_truth_source": _engine_card.get("display_truth_source"),
                "primary_target_low": _engine_card.get("target_low"),
                "primary_target_high": _engine_card.get("target_high"),
                "primary_preview_util": _engine_outcome.get("preview_util"),
                "primary_current_util": _engine_outcome.get("current_util"),
                "primary_lands_in_target_band": _engine_outcome.get("lands_in_target_band"),
                "primary_allowed_blocker": _engine_outcome.get("allowed_blocker"),
                "button_contract_enabled": _engine_button.get("enabled"),
                "button_contract_updates": dict(_engine_button.get("updates") or {}),
                "button_contract_preview_pass": _engine_button.get("preview_pass"),
                "button_contract_blocking_reason": _engine_button.get("blocking_reason"),
                "design_guide_engine_decision_reason": _engine_trace.get("decision_reason"),
                "design_guide_engine_suppressed_count": _engine_trace.get("suppressed_count"),
                "design_guide_engine_suppressed_reasons": list(_engine_trace.get("suppressed_reasons") or []),
                "candidate_search_evidence": dict(_engine_candidate_search_evidence),
                "family_utils": dict(
                    _dg_engine_decision.get("family_utils")
                    or _engine_card.get("family_utils")
                    or guidance_debug.get("family_utils")
                    or {}
                ),
                "materially_overprovided_families": list(
                    _dg_engine_decision.get("materially_overprovided_families")
                    or _engine_card.get("materially_overprovided_families")
                    or guidance_debug.get("materially_overprovided_families")
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
                "local_cleanup_search_ran": (
                    _dg_engine_decision.get("local_cleanup_search_ran")
                    if _dg_engine_decision.get("local_cleanup_search_ran") is not None
                    else (
                        _engine_card.get("local_cleanup_search_ran")
                        if _engine_card.get("local_cleanup_search_ran") is not None
                        else guidance_debug.get("local_cleanup_search_ran")
                    )
                ),
                "local_cleanup_search_exhaustive": (
                    _dg_engine_decision.get("local_cleanup_search_exhaustive")
                    if _dg_engine_decision.get("local_cleanup_search_exhaustive") is not None
                    else (
                        _engine_card.get("local_cleanup_search_exhaustive")
                        if _engine_card.get("local_cleanup_search_exhaustive") is not None
                        else guidance_debug.get("local_cleanup_search_exhaustive")
                    )
                ),
                "safe_local_cleanup_count": (
                    _dg_engine_decision.get("safe_local_cleanup_count")
                    if _dg_engine_decision.get("safe_local_cleanup_count") is not None
                    else (
                        _engine_card.get("safe_local_cleanup_count")
                        if _engine_card.get("safe_local_cleanup_count") is not None
                        else guidance_debug.get("safe_local_cleanup_count")
                    )
                ),
                "executable_safe_cleanup_count": (
                    _dg_engine_decision.get("executable_safe_cleanup_count")
                    if _dg_engine_decision.get("executable_safe_cleanup_count") is not None
                    else (
                        _engine_card.get("executable_safe_cleanup_count")
                        if _engine_card.get("executable_safe_cleanup_count") is not None
                        else guidance_debug.get("executable_safe_cleanup_count")
                    )
                ),
                "advisory_cleanup_count": (
                    _dg_engine_decision.get("advisory_cleanup_count")
                    if _dg_engine_decision.get("advisory_cleanup_count") is not None
                    else (
                        _engine_card.get("advisory_cleanup_count")
                        if _engine_card.get("advisory_cleanup_count") is not None
                        else guidance_debug.get("advisory_cleanup_count")
                    )
                ),
                "local_cleanup_candidates": list(
                    _dg_engine_decision.get("local_cleanup_candidates")
                    or _engine_card.get("local_cleanup_candidates")
                    or []
                ),
                "local_cleanup_candidate_inventory": list(
                    _dg_engine_decision.get("local_cleanup_candidate_inventory")
                    or _engine_card.get("local_cleanup_candidate_inventory")
                    or []
                ),
                "local_cleanup_candidate_inventory_count": (
                    _dg_engine_decision.get("local_cleanup_candidate_inventory_count")
                    if _dg_engine_decision.get("local_cleanup_candidate_inventory_count") is not None
                    else _engine_card.get("local_cleanup_candidate_inventory_count")
                ),
                "candidate_inventory_count": (
                    _dg_engine_decision.get("candidate_inventory_count")
                    if _dg_engine_decision.get("candidate_inventory_count") is not None
                    else _engine_card.get("candidate_inventory_count")
                ),
                "rejected_local_cleanup_count": (
                    _dg_engine_decision.get("rejected_local_cleanup_count")
                    if _dg_engine_decision.get("rejected_local_cleanup_count") is not None
                    else _engine_card.get("rejected_local_cleanup_count")
                ),
                "local_cleanup_blocked_reasons": list(
                    _dg_engine_decision.get("local_cleanup_blocked_reasons")
                    or _engine_card.get("local_cleanup_blocked_reasons")
                    or []
                ),
                "local_cleanup_blocked_reasons_by_family": dict(
                    _dg_engine_decision.get("local_cleanup_blocked_reasons_by_family")
                    or _engine_card.get("local_cleanup_blocked_reasons_by_family")
                    or {}
                ),
                "unsupported_cleanup_families": list(
                    _dg_engine_decision.get("unsupported_cleanup_families")
                    or _engine_card.get("unsupported_cleanup_families")
                    or []
                ),
                "terminal_state_reason": (
                    _dg_engine_decision.get("terminal_state_reason")
                    or _engine_card.get("terminal_state_reason")
                ),
                "terminal_state_blocked_by_local_cleanup": bool(
                    _dg_engine_decision.get("terminal_state_blocked_by_local_cleanup")
                    or _engine_card.get("terminal_state_blocked_by_local_cleanup")
                ),
                "guidance_intent_items": list(guidance_debug.get("guidance_intent_items") or []),
                "displayed_guidance_intent_items": list(
                    guidance_debug.get("displayed_guidance_intent_items") or []
                ),
                "primary_guidance_intent": guidance_debug.get("primary_guidance_intent"),
                "primary_button_contract": dict(guidance_debug.get("primary_button_contract") or {}),
                "primary_display_truth": dict(guidance_debug.get("primary_display_truth") or {}),
                "displayed_primary_button_contract": dict(
                    guidance_debug.get("primary_button_contract") or {}
                ),
                "displayed_primary_display_truth": dict(
                    guidance_debug.get("primary_display_truth") or {}
                ),
                "button_contract": dict(guidance_debug.get("primary_button_contract") or {}),
            }
        )
    st.session_state["design_guide_feedback_status"] = guidance_debug["design_guide_feedback_status"]
    st.session_state["design_guide_feedback_reason"] = guidance_debug["design_guide_feedback_reason"]
    st.session_state["design_guide_feedback_fail_fingerprint"] = dict(_oc_feedback_fp)
    st.session_state["design_guide_current_fail_fingerprint"] = dict(_dg_current_fail_fingerprint)
    st.session_state["design_guide_blocked_feedback_matches_current_state"] = bool(
        _blocked_feedback_matches_current_state
    )
    st.session_state["design_guide_stale_blocked_feedback_cleared"] = bool(
        _stale_blocked_feedback_cleared
    )
    st.session_state["design_guide_stale_blocked_feedback_reason"] = (
        "fail_fingerprint_changed" if _stale_blocked_feedback_cleared else None
    )
    if _oc_feedback:
        feedback_status = _oc_feedback_status.lower()
        feedback_reason = _oc_feedback_reason or "unknown"
        feedback_label = str(_oc_feedback.get("winning_label") or "").strip()
        message = (
            f"One-click found a candidate, but it was {feedback_status}: {feedback_reason}."
            if feedback_label
            else f"No one-click change was applied. Reason: {feedback_reason}."
        )
        if feedback_status in {"blocked", "rejected"}:
            st.warning(message)
        else:
            st.info(message)


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
        guidance_items, _local_cleanup_meta = _maybe_promote_safe_local_cleanup_primary(
            guidance_items,
            state=guidance_disp_state,
            overview=dict(guidance_debug.get("overview") or {}),
            efficiency_state=dict(guidance_debug.get("efficiency_tightening_state") or {}),
            mode_config=_design_mode_config(_design_optimisation_goal(guidance_disp_state)),
            debug_sink=guidance_debug,
            source="render_fast_design_guidance_panel",
        )
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
        and (
            bool(_is_in_target_zone_with_eps(_render_overview, _render_mode_config, eps=TARGET_BAND_EPS))
            or _render_acceptance_terminal_proof
        )
        and bool(_render_acceptance_audit.get("post_click_accepted_green_valid"))
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
    if str(guidance_debug.get("guidance_branch") or "") == "not_started":
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
    _set_cached_design_guide_guidance(fingerprint, guidance_items_raw, guidance_debug)
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
        guidance_debug.update(_post_cleanup_render_audit)
    _post_cleanup_terminal_proof = _accepted_green_audit_has_terminal_proof(_post_cleanup_render_audit)
    _post_cleanup_terminal_render = bool(
        (
            _local_cleanup_post_apply_acceptance_matches(guidance_disp_state)
            or (
                not _shear_reinforcement_is_active(guidance_disp_state)
                and bool(_post_cleanup_render_audit.get("post_click_accepted_green_valid"))
            )
        )
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
            or _post_cleanup_terminal_proof
        )
        and bool(_post_cleanup_render_audit.get("post_click_accepted_green_valid"))
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
        _accepted_render_item = _guidance_item(
            "general",
            "Design accepted - target band achieved",
            "",
            None,
            "Why: the one-click cleanup has been applied; all required checks remain acceptable, the governing utilisation is inside the target band, and the current design is the accepted post-click state.",
            "Key checks: bending, shear, serviceability, target utilisation band",
            None,
            None,
            status="PASS",
            util=_accepted_render_util,
        )
        _accepted_render_item["guidance_intent"] = "already_efficient"
        _accepted_render_item["design_guide_terminal_state"] = "optimal"
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
        st.success(_terminal_title)
        st.caption(_terminal_body)
    elif bool(render_plan.get("render_primary_only")):
        _primary_render_items = guidance_items[:1] if guidance_items else []
        if _primary_render_items:
            render_guidance_secondary_items(
                _primary_render_items,
                guidance_disp_state=guidance_disp_state,
                current_overview=_dg_overview,
                inputs_render_audit=inputs_render_audit,
                start_index=0,
                primary_card_presentation=_dg_presentation,
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
        render_guidance_secondary_items(
            _visible_render_items,
            guidance_disp_state=guidance_disp_state,
            current_overview=_dg_overview,
            inputs_render_audit=inputs_render_audit,
            start_index=0,
            primary_card_presentation=_dg_presentation,
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
