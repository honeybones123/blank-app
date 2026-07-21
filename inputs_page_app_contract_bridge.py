"""App-contract bridge for Inputs page helper surfaces.

``app.py`` still reads a set of Design Guide and browser-probe helpers that
are intentionally exposed outside the live page shell. This bridge keeps that
compatibility/provider surface explicit while the live page route stays owned
by ``inputs_page.py``.
"""

from __future__ import annotations

import json
import copy
import hashlib
import html
import math
import os
import re
import sys
import time
import uuid
from datetime import datetime

import streamlit as st

from bending_checks_helpers import build_bending_check_rows_from_state, compute_bending_capacity_from_state
from design_brain.candidate_evaluation import (
    build_full_candidate_evaluation_result_projection,
    diff_candidate_state_updates as _diff_candidate_state_updates,
    resolve_candidate_domain_max_distance as _resolve_candidate_domain_max_distance,
    resolve_candidate_domain_total_distance as _resolve_candidate_domain_total_distance,
    resolve_candidate_in_target_band as _resolve_candidate_in_target_band,
    resolve_candidate_required_domain_progress as _resolve_candidate_required_domain_progress,
    resolve_candidate_required_domains_satisfied as _resolve_candidate_required_domains_satisfied,
    resolve_candidate_step_improves as _resolve_candidate_step_improves,
    resolve_target_band_candidate_domains_for_updates as _resolve_target_band_candidate_domains_for_updates,
    resolve_target_band_domains_touched_by_updates as _resolve_target_band_domains_touched_by_updates,
    resolve_target_band_exhaustion_refinement_allowed as _resolve_target_band_exhaustion_refinement_allowed,
    resolve_target_band_next_hop_precheck as _resolve_target_band_next_hop_precheck,
    select_best_target_band_refinement_candidate as _select_best_target_band_refinement_candidate,
)
from design_brain.config import (
    AUTO_DESIGN_MODE_CONFIG,
    DESIGN_OPTIMISATION_GOAL_LABELS,
    resolve_design_mode_config,
    resolve_design_optimisation_goal,
)
from design_brain.design_guide_controller import (
    build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence,
    build_design_guide_shear_low_util_raw_variant_states,
    resolve_design_guide_controller_optimisation_candidate_family as _resolve_design_guide_controller_optimisation_candidate_family,
    resolve_design_guide_controller_guidance_action_generated_updates as _resolve_design_guide_controller_guidance_action_generated_updates,
    resolve_design_guide_controller_guidance_action_payload_updates as _resolve_design_guide_controller_guidance_action_payload_updates,
)
from design_brain.cta_contracts import (
    DesignGuideButtonContractSourceRecords,
    build_design_guide_button_contract_source_records as _build_design_guide_button_contract_source_records_extracted,
    build_design_guide_button_contract_source_resolution,
    select_design_guide_button_contract_source_precedence,
)
from design_brain.final_publication import (
    build_final_publication_cta_from_current_state as _build_final_publication_cta_from_current_state,
)
from design_brain.families.bending import (
    build_bottom_reo_arrangement_pool_from_state as _build_bottom_reo_arrangement_pool_from_state,
)
from design_guidance_engine import legacy_item_from_decision, resolve_design_guide_decision
from inputs_page_modules.design_guide import (
    _COMPOUND_BOTTOM_UPDATE_KEYS,
    _COMPOUND_GEOMETRY_UPDATE_KEYS,
    _candidate_cache_key,
    _canonical_pack_is_valid,
    _coherence_debug_fields,
    _compound_subfamilies_from_updates,
    _design_state_coherence_check,
    _guidance_item_family as _guidance_item_family_extracted,
    _guidance_item_source_candidate_id,
    _make_auto_design_candidate_key,
)
from inputs_page_modules.design_guide import current_coordinators as _current_coordinators
from inputs_page_modules.design_guide import panel_coordinators as _panel_coordinators
from inputs_page_modules.widgets.design_action_sync import (
    sync_design_action_widget_to_shared as _sync_design_action_widget_to_shared_module,
)
from inputs_page_modules.design_guide.efficiency_guidance_items import (
    bind_efficiency_guidance_item_dependencies as _bind_efficiency_guidance_item_dependencies,
    _efficiency_guidance_items as _efficiency_guidance_items_extracted,
)
from inputs_page_modules.design_guide.efficiency_tightening_state import (
    bind_efficiency_tightening_state_dependencies as _bind_efficiency_tightening_state_dependencies,
    _build_efficiency_exhaustion_map as _build_efficiency_exhaustion_map_extracted,
    compute_efficiency_tightening_state as _compute_efficiency_tightening_state_extracted,
)
from inputs_page_modules.design_guide.active_fail_single_family_guard import (
    bind_active_fail_single_family_guard_dependencies as _bind_active_fail_single_family_guard_dependencies,
    _replace_unsafe_combined_active_fail_single_family_action as _replace_unsafe_combined_active_fail_single_family_action_extracted,
)
from inputs_page_modules.design_guide.direct_target_band_guidance import (
    bind_direct_target_band_guidance_dependencies as _bind_direct_target_band_guidance_dependencies,
    _direct_target_band_guidance_item as _direct_target_band_guidance_item_extracted,
)
from inputs_page_modules.design_guide.candidate_search_evidence import (
    bind_candidate_search_evidence_dependencies as _bind_candidate_search_evidence_dependencies,
    _align_guidance_items_to_candidate_search_evidence as _align_guidance_items_to_candidate_search_evidence_extracted,
    _build_candidate_search_evidence as _build_candidate_search_evidence_extracted,
    _candidate_search_distance_to_band as _candidate_search_distance_to_band_extracted,
    _candidate_search_summary_row as _candidate_search_summary_row_extracted,
)
from inputs_page_modules.design_guide.local_cleanup_promotion import (
    bind_local_cleanup_promotion_dependencies as _bind_local_cleanup_promotion_dependencies,
    _maybe_promote_safe_local_cleanup_primary as _maybe_promote_safe_local_cleanup_primary_extracted,
)
from inputs_page_modules.design_guide.local_cleanup_guidance_evaluator import (
    bind_local_cleanup_guidance_evaluator_dependencies as _bind_local_cleanup_guidance_evaluator_dependencies,
    _evaluate_local_cleanup_guidance_item as _evaluate_local_cleanup_guidance_item_extracted,
)
from inputs_page_modules.design_guide.compound_strengthening import (
    bind_compound_strengthening_dependencies as _bind_compound_strengthening_dependencies,
    _try_compound_efficiency_guidance_item as _try_compound_efficiency_guidance_item_extracted,
    _try_compound_strengthening_guidance_item as _try_compound_strengthening_guidance_item_extracted,
)
from inputs_page_modules.design_guide.compound_guidance_copy import (
    bind_compound_guidance_copy_dependencies as _bind_compound_guidance_copy_dependencies,
    _compound_geometry_deltas as _compound_geometry_deltas_extracted,
    _compound_guidance_title_reasoning_why as _compound_guidance_title_reasoning_why_extracted,
)
from inputs_page_modules.design_guide.shear_congestion_reshape import (
    bind_shear_congestion_reshape_dependencies as _bind_shear_congestion_reshape_dependencies,
    _in_target_shear_congestion_reshape_guidance_item as _in_target_shear_congestion_reshape_guidance_item_extracted,
)
from inputs_page_modules.design_guide.bending_guidance import (
    bind_bending_guidance_dependencies as _bind_bending_guidance_dependencies,
    _bending_guidance_item as _bending_guidance_item_extracted,
)
from inputs_page_modules.design_guide.crack_guidance import (
    bind_crack_guidance_dependencies as _bind_crack_guidance_dependencies,
    _crack_guidance_item as _crack_guidance_item_extracted,
)
from inputs_page_modules.design_guide.shear_local_cleanup import (
    bind_shear_local_cleanup_dependencies as _bind_shear_local_cleanup_dependencies,
    _best_safe_shear_local_cleanup_recommendation as _best_safe_shear_local_cleanup_recommendation_extracted,
    _shear_tightening_as_local_cleanup_item as _shear_tightening_as_local_cleanup_item_extracted,
)
from inputs_page_modules.design_guide.one_click_band_candidate import (
    bind_one_click_band_candidate_dependencies as _bind_one_click_band_candidate_dependencies,
    _get_one_click_band_reaching_candidate as _get_one_click_band_reaching_candidate_extracted,
)
from inputs_page_modules.design_guide.auto_design_candidate_selector import (
    bind_auto_design_candidate_selector_dependencies as _bind_auto_design_candidate_selector_dependencies,
    _select_best_auto_design_candidate as _select_best_auto_design_candidate_extracted,
)
from inputs_page_modules.design_guide.shear_guidance import (
    bind_shear_guidance_dependencies as _bind_shear_guidance_dependencies,
    _shear_guidance_item as _shear_guidance_item_extracted,
    _shear_item_from_geometry_trials as _shear_item_from_geometry_trials_extracted,
)
from inputs_page_modules.design_guide.guidance_action_update_resolver import (
    bind_guidance_action_update_resolver_dependencies as _bind_guidance_action_update_resolver_dependencies,
    _guidance_action_updates as _guidance_action_updates_extracted,
)
from inputs_page_modules.design_guide.executor_actionability_contract import (
    bind_executor_actionability_contract_dependencies as _bind_executor_actionability_contract_dependencies,
    _guidance_executor_actionability_contract as _guidance_executor_actionability_contract_extracted,
)
from inputs_page_modules.design_guide.button_contract import (
    bind_button_contract_dependencies as _bind_button_contract_dependencies,
    _design_guide_button_contract as _design_guide_button_contract_extracted,
)
from inputs_page_modules.design_guide.preview_contract import (
    bind_preview_contract_dependencies as _bind_preview_contract_dependencies,
    _design_guide_preview_contract_for_updates as _design_guide_preview_contract_for_updates_extracted,
)
from inputs_page_modules.design_guide.display_truth import (
    DESIGN_GUIDE_DISPLAY_TRUTH_SOURCES as DESIGN_GUIDE_DISPLAY_TRUTH_SOURCES_EXTRACTED,
    bind_display_truth_dependencies as _bind_display_truth_dependencies,
    _design_guide_candidate_overview as _design_guide_candidate_overview_extracted,
    _design_guide_candidate_util as _design_guide_candidate_util_extracted,
    _design_guide_display_truth_for_item as _design_guide_display_truth_for_item_extracted,
    _design_guide_item_uses_candidate_preview as _design_guide_item_uses_candidate_preview_extracted,
    _design_guide_post_commit_util as _design_guide_post_commit_util_extracted,
    _design_guide_summary_util as _design_guide_summary_util_extracted,
    _design_guide_target_band_for_state as _design_guide_target_band_for_state_extracted,
)
from inputs_page_modules.design_guide.efficiency_executor_promotion import (
    bind_efficiency_executor_promotion_dependencies as _bind_efficiency_executor_promotion_dependencies,
    _try_promote_efficiency_item_to_executor_backed_candidate as _try_promote_efficiency_item_to_executor_backed_candidate_extracted,
)
from inputs_page_modules.design_guide.executor_contract_sanitizer import (
    bind_executor_contract_sanitizer_dependencies as _bind_executor_contract_sanitizer_dependencies,
    _sanitize_guidance_items_for_executor_contract as _sanitize_guidance_items_for_executor_contract_extracted,
)
from inputs_page_modules.design_guide.guidance_item_dedupe import (
    bind_guidance_item_dedupe_dependencies as _bind_guidance_item_dedupe_dependencies,
    _dedupe_guidance_items_for_display as _dedupe_guidance_items_for_display_extracted,
)
from inputs_page_modules.design_guide.apply_trace_run_end import (
    bind_apply_trace_run_end_dependencies as _bind_apply_trace_run_end_dependencies,
    _emit_design_guide_apply_trace_run_end as _emit_design_guide_apply_trace_run_end_extracted,
)
from inputs_page_modules.design_guide.apply_step_history_finalizer import (
    bind_apply_step_history_finalizer_dependencies as _bind_apply_step_history_finalizer_dependencies,
    _finalize_design_guide_apply_step_history as _finalize_design_guide_apply_step_history_extracted,
)
from inputs_page_modules.design_guide.primary_apply_payload_recorder import (
    bind_primary_apply_payload_recorder_dependencies as _bind_primary_apply_payload_recorder_dependencies,
    _record_rendered_design_guide_primary_apply_payload as _record_rendered_design_guide_primary_apply_payload_extracted,
)
from inputs_page_modules.design_guide.primary_apply_payload import (
    bind_primary_apply_payload_dependencies as _bind_primary_apply_payload_dependencies,
    _build_design_guide_primary_apply_payload as _build_design_guide_primary_apply_payload_extracted,
)
from inputs_page_modules.design_guide.guidance_item_consolidation import (
    bind_guidance_item_consolidation_dependencies as _bind_guidance_item_consolidation_dependencies,
    _collapse_to_single_primary_guidance_item as _collapse_to_single_primary_guidance_item_extracted,
    _consolidate_guidance_items_by_family as _consolidate_guidance_items_by_family_extracted,
    _guidance_item_is_same_problem_wrapper as _guidance_item_is_same_problem_wrapper_extracted,
)
from inputs_page_modules.design_guide.primary_one_click_validation import (
    bind_primary_one_click_validation_dependencies as _bind_primary_one_click_validation_dependencies,
    _candidate_is_valid_primary_one_click as _candidate_is_valid_primary_one_click_extracted,
)
from inputs_page_modules.design_guide.primary_button_queue import (
    bind_primary_button_queue_dependencies as _bind_primary_button_queue_dependencies,
    _queue_primary_design_guide_button_action as _queue_primary_design_guide_button_action_extracted,
)
from inputs_page_modules.design_guide.primary_optimisation_selector import (
    bind_primary_optimisation_selector_dependencies as _bind_primary_optimisation_selector_dependencies,
    _select_primary_optimisation_candidate as _select_primary_optimisation_candidate_extracted,
)
from inputs_page_modules.design_guide.mode_guidance_recommendation import (
    bind_mode_guidance_recommendation_dependencies as _bind_mode_guidance_recommendation_dependencies,
    _compute_mode_guidance_recommendation_uncached as _compute_mode_guidance_recommendation_uncached_extracted,
)
from inputs_page_modules.design_guide.candidate_family_classification import (
    _candidate_family_matches_governing_domain as _candidate_family_matches_governing_domain_extracted,
)
from inputs_page_modules.design_guide.trace import (
    append_design_guide_trace as _append_design_guide_trace_extracted,
)
from inputs_page_modules.design_guide.geometry_trial_selector import (
    bind_geometry_trial_selector_dependencies as _bind_geometry_trial_selector_dependencies,
    _choose_geometry_trial_for_metric as _choose_geometry_trial_for_metric_extracted,
    _read_metric_for_geometry_trial as _read_metric_for_geometry_trial_extracted,
)
from inputs_page_modules.design_guide.bottom_tightening import (
    bind_bottom_tightening_dependencies as _bind_bottom_tightening_dependencies,
    _compute_bottom_reo_tightening_recommendation as _compute_bottom_reo_tightening_recommendation_extracted,
)
from inputs_page_modules.design_guide.geometry_tightening import (
    bind_geometry_tightening_dependencies as _bind_geometry_tightening_dependencies,
    _compute_geometry_tightening_recommendation as _compute_geometry_tightening_recommendation_extracted,
)
from inputs_page_modules.design_guide.shear_tightening import (
    bind_shear_tightening_dependencies as _bind_shear_tightening_dependencies,
    _compute_shear_tightening_recommendation as _compute_shear_tightening_recommendation_extracted,
)
from inputs_page_modules.design_guide.title_alignment_verification import (
    bind_title_alignment_verification_dependencies as _bind_title_alignment_verification_dependencies,
    _design_guide_title_alignment_verification_record as _design_guide_title_alignment_verification_record_extracted,
)
from inputs_page_modules.design_guide.banner_render_state import (
    bind_banner_render_state_dependencies as _bind_banner_render_state_dependencies,
    _design_guide_banner_matches_current_render as _design_guide_banner_matches_current_render_extracted,
)
from inputs_page_modules.design_guide.auto_design_scoring import (
    bind_auto_design_scoring_dependencies as _bind_auto_design_scoring_dependencies,
    _candidate_sort_key_for_mode as _candidate_sort_key_for_mode_extracted,
    candidate_materially_worsens as _candidate_materially_worsens_extracted,
    _score_auto_design_candidate_components as _score_auto_design_candidate_components_extracted,
)
from inputs_page_modules.design_guide.resolved_candidate_guidance_item import (
    bind_resolved_candidate_guidance_item_dependencies as _bind_resolved_candidate_guidance_item_dependencies,
    _ensure_guidance_item_resolved_candidate_payload as _ensure_guidance_item_resolved_candidate_payload_extracted,
    _guidance_item_from_resolved_candidate as _guidance_item_from_resolved_candidate_extracted,
    _promote_guidance_item_to_resolved_candidate as _promote_guidance_item_to_resolved_candidate_extracted,
)
from inputs_page_modules.design_guide.terminal_state import (
    bind_terminal_state_dependencies as _bind_terminal_state_dependencies,
    _derive_design_guide_terminal_state_from_current_overview as _derive_design_guide_terminal_state_from_current_overview_extracted,
)
from inputs_page_modules.design_guide.severe_shear_escalation_log import (
    bind_severe_shear_escalation_log_dependencies as _bind_severe_shear_escalation_log_dependencies,
    _log_severe_shear_escalation as _log_severe_shear_escalation_extracted,
)
from inputs_page_modules.design_guide.shear_low_util_active_links_blocker import (
    bind_shear_low_util_active_links_blocker_dependencies as _bind_shear_low_util_active_links_blocker_dependencies,
    _shear_low_util_active_links_exact_blocker as _shear_low_util_active_links_exact_blocker_extracted,
)
from inputs_page_modules.design_guide.governing_domain_tightening_candidates import (
    bind_governing_domain_tightening_candidates_dependencies as _bind_governing_domain_tightening_candidates_dependencies,
    _generate_tightening_candidates_for_governing_domain as _generate_tightening_candidates_for_governing_domain_extracted,
    _one_click_generate_multi_domain_refinement_states as _one_click_generate_multi_domain_refinement_states_extracted,
)
from inputs_page_modules.design_guide.shear_governing_candidates import (
    bind_shear_governing_candidate_dependencies as _bind_shear_governing_candidate_dependencies,
    _generate_shear_governing_candidates as _generate_shear_governing_candidates_extracted,
)
from inputs_page_modules.design_guide.presentation_state import (
    bind_presentation_state_dependencies as _bind_presentation_state_dependencies,
    _build_design_guide_presentation_state as _build_design_guide_presentation_state_extracted,
    _latest_solver_result_cta_state as _latest_solver_result_cta_state_extracted,
)
from inputs_page_modules.design_guide.guidance_intent import (
    bind_guidance_intent_dependencies as _bind_guidance_intent_dependencies,
    _derive_design_guide_guidance_intent as _derive_design_guide_guidance_intent_extracted,
)
from inputs_page_modules.design_guide.pending_recommendation import (
    bind_pending_recommendation_dependencies as _bind_pending_recommendation_dependencies,
    _build_pending_recommendation as _build_pending_recommendation_extracted,
    _sync_pending_recommendation_from_guidance as _sync_pending_recommendation_from_guidance_extracted,
)
from inputs_page_modules.design_guide.main_panel_status import (
    bind_main_panel_status_dependencies as _bind_main_panel_status_dependencies,
    _render_auto_design_main_panel_status as _render_auto_design_main_panel_status_extracted,
)
from inputs_page_modules.design_guide.serviceability_preflight import (
    bind_serviceability_preflight_dependencies as _bind_serviceability_preflight_dependencies,
    _serviceability_governs_preflight_payload as _serviceability_governs_preflight_payload_extracted,
)
from inputs_page_modules.design_guide.serviceability_ladder_candidates import (
    bind_serviceability_ladder_candidate_dependencies as _bind_serviceability_ladder_candidate_dependencies,
    _pick_deflection_ladder_first_improvement as _pick_deflection_ladder_first_improvement_extracted,
    _try_crack_ladder_candidate as _try_crack_ladder_candidate_extracted,
    _try_deflection_ladder_candidate as _try_deflection_ladder_candidate_extracted,
)
from inputs_page_modules.design_guide.recommendation_result_builder import (
    bind_recommendation_result_builder_dependencies as _bind_recommendation_result_builder_dependencies,
    _build_recommendation_result_from_guidance_item as _build_recommendation_result_from_guidance_item_extracted,
)
from inputs_page_modules.design_guide.actionable_target_band_winner import (
    bind_actionable_target_band_winner_dependencies as _bind_actionable_target_band_winner_dependencies,
    _get_actionable_target_band_winner as _get_actionable_target_band_winner_extracted,
)
from inputs_page_modules.design_guide.bottom_recommendation_selector import (
    bind_bottom_recommendation_selector_dependencies as _bind_bottom_recommendation_selector_dependencies,
    _collapse_bottom_geometry_width_depth_trials as _collapse_bottom_geometry_width_depth_trials_extracted,
    _pick_best_bottom_recommendation_by_selector as _pick_best_bottom_recommendation_by_selector_extracted,
)
from inputs_page_modules.app_bridge.candidate_full_evaluation import (
    bind_candidate_full_evaluation_dependencies as _bind_candidate_full_evaluation_dependencies,
    evaluate_candidate_full_for_app_bridge as _evaluate_candidate_full_for_app_bridge_extracted,
)
from inputs_page_modules.app_bridge.deflection_evaluation import (
    bind_deflection_evaluation_dependencies as _bind_deflection_evaluation_dependencies,
    _evaluate_deflection_with_state as _evaluate_deflection_with_state_extracted,
    _evaluate_deflection_with_state_for_app_bridge as _evaluate_deflection_with_state_for_app_bridge_extracted,
)
from inputs_page_modules.app_bridge.crack_evaluation import (
    bind_crack_evaluation_dependencies as _bind_crack_evaluation_dependencies,
    _evaluate_crack_with_state_for_app_bridge as _evaluate_crack_with_state_for_app_bridge_extracted,
)
from inputs_page_modules.app_bridge.shear_evaluation import (
    bind_shear_evaluation_dependencies as _bind_shear_evaluation_dependencies,
    _evaluate_shear_with_state_for_app_bridge as _evaluate_shear_with_state_for_app_bridge_extracted,
)
from inputs_page_modules.app_bridge.design_overview_collector import (
    bind_design_overview_collector_dependencies as _bind_design_overview_collector_dependencies,
    _collect_design_overview as _collect_design_overview_extracted,
)
from inputs_page_modules.app_bridge.fast_candidate_evaluator import (
    bind_fast_candidate_evaluator_dependencies as _bind_fast_candidate_evaluator_dependencies,
    evaluate_candidate_fast as _evaluate_candidate_fast_kernel_extracted,
)
from inputs_page_modules.app_bridge.canonical_design_state_pack import (
    bind_canonical_design_state_pack_dependencies as _bind_canonical_design_state_pack_dependencies,
    _build_canonical_design_state_pack_for_app_bridge as _build_canonical_design_state_pack_for_app_bridge_extracted,
)
from inputs_page_modules.app_bridge.canonical_convenience_resync import (
    bind_canonical_convenience_resync_dependencies as _bind_canonical_convenience_resync_dependencies,
    _apply_canonical_convenience_resync_to_shared as _apply_canonical_convenience_resync_to_shared_extracted,
    _canonical_convenience_fields_from_state as _canonical_convenience_fields_from_state_extracted,
)
from inputs_page_modules.app_bridge.actionable_guidance_candidates import (
    bind_actionable_guidance_candidate_dependencies as _bind_actionable_guidance_candidate_dependencies,
    _candidate_is_materially_actionable as _candidate_is_materially_actionable_extracted,
    _one_click_collect_actionable_guidance_candidates as _one_click_collect_actionable_guidance_candidates_extracted,
)
from inputs_page_modules.app_bridge.resolved_design_actions_state import (
    bind_resolved_design_actions_state_dependencies as _bind_resolved_design_actions_state_dependencies,
    _state_with_resolved_design_actions_for_app_bridge as _state_with_resolved_design_actions_for_app_bridge_extracted,
    _state_with_resolved_design_actions_isolated_for_app_bridge as _state_with_resolved_design_actions_isolated_for_app_bridge_extracted,
)
from inputs_page_modules.app_bridge.shear_candidate_generation import (
    bind_shear_candidate_generation_dependencies as _bind_shear_candidate_generation_dependencies,
    _generate_escalated_shear_states as _generate_escalated_shear_states_extracted,
    _generate_shear_candidates as _generate_shear_candidates_extracted,
    _shear_recommendation_rank_key as _shear_recommendation_rank_key_extracted,
)
from inputs_page_modules.app_bridge.auto_design_solver import (
    bind_auto_design_solver_dependencies as _bind_auto_design_solver_dependencies,
    run_cleanup_pass as _run_cleanup_pass_extracted,
    run_final_tightening_pass as _run_final_tightening_pass_extracted,
    run_full_auto_design as _run_full_auto_design_extracted,
    run_auto_design_solver as _run_auto_design_solver_extracted,
    _build_progressive_candidate_updates as _build_progressive_candidate_updates_extracted,
    _solve_reo_for_geometry as _solve_reo_for_geometry_extracted,
)
from inputs_page_modules.app_bridge.rescue_mode_gate import (
    bind_rescue_mode_gate_dependencies as _bind_rescue_mode_gate_dependencies,
    _rescue_mode_should_enter as _rescue_mode_should_enter_extracted,
)
from inputs_page_modules.recommendation_shear_ladder import (
    bind_shear_recommendation_ladder_dependencies as _bind_shear_recommendation_ladder_dependencies,
    _iter_shear_recommendation_ladder_states as _iter_shear_recommendation_ladder_states_extracted,
)
from inputs_page_modules.app_bridge.top_candidate_keeper import (
    bind_top_candidate_keeper_dependencies as _bind_top_candidate_keeper_dependencies,
    _candidate_dominates_for_mode as _candidate_dominates_for_mode_extracted,
    _keep_top_candidates as _keep_top_candidates_extracted,
)
from inputs_page_modules.app_bridge.post_commit_audit import (
    bind_post_commit_audit_dependencies as _bind_post_commit_audit_dependencies,
    _one_click_commit_audit_passes as _one_click_commit_audit_passes_extracted,
    _one_click_post_commit_audit as _one_click_post_commit_audit_extracted,
    _one_click_post_commit_audit_subset as _one_click_post_commit_audit_subset_extracted,
    _post_click_accepted_green_audit as _post_click_accepted_green_audit_extracted,
)
from inputs_page_modules.app_bridge.auto_design_commit import (
    bind_auto_design_commit_dependencies as _bind_auto_design_commit_dependencies,
    _commit_auto_design_candidate_to_shared as _commit_auto_design_candidate_to_shared_extracted,
)
from inputs_page_modules.summaries.summary_state_resolver import (
    bind_summary_state_resolver_dependencies as _bind_summary_state_resolver_dependencies,
    _resolved_inputs_summary_state as _resolved_inputs_summary_state_extracted,
)
from shear_checks_helpers import build_shear_check_rows_from_state
from section_layout import compute_section_layout_pure
from section_props.reo_layout import (
    compute_longitudinal_reo_layout_T_I,
    resolve_longitudinal_bars_from_layout,
)
import inputs_page_app_contracts
from inputs_page_modules.session import (
    build_inputs_design_action_result_overlay_snapshot,
    build_inputs_design_guide_cached_debug_trust_decision,
    build_inputs_design_guide_apply_step_history_entry_plan,
    build_inputs_design_guide_dirty_mark_plan,
    build_inputs_design_guide_guidance_cache_result,
    build_inputs_design_guide_guidance_cache_write_plan,
    build_inputs_design_guide_apply_trace_run_end_meta_plan,
    build_inputs_design_guide_apply_trace_run_end_outcome,
    build_inputs_design_guide_step_history_debug_summary,
    build_inputs_design_guide_step_history_reset_plan,
    build_inputs_design_guide_transient_ui_clear_plan,
    build_inputs_normalized_shear_truth_overlay_snapshot,
    build_inputs_shear_widget_mirror_overlay_plan,
    build_inputs_summary_debug_payload_snapshot,
    build_inputs_summary_shared_only_decision,
    build_inputs_summary_source_shaping_snapshot,
    build_inputs_summary_state_mode_marker_snapshot,
)
from inputs_page_modules.session.local_cleanup_acceptance import (
    DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS,
)
from inputs_page_modules.auto_design_compute import (
    run_one_click_auto_design_coordinator,
)
from inputs_page_modules.one_click_candidate_solver import (
    bind_one_click_candidate_solver_dependencies as _bind_one_click_candidate_solver_dependencies,
    _solve_one_click_candidate as _solve_one_click_candidate_extracted,
)
from inputs_page_modules.bottom_reo_design_trials import (
    bind_bottom_reo_design_trial_dependencies as _bind_bottom_reo_design_trial_dependencies,
    _enumerate_bottom_reo_design_trials as _enumerate_bottom_reo_design_trials_extracted,
)
from inputs_page_modules.apply_payload import apply_resolved_candidate_payload
from inputs_page_modules.apply_dispatch import (
    apply_recommendation_result_coordinator,
)
from inputs_page_modules.apply_guidance_action import (
    bind_apply_guidance_action_dependencies as _bind_apply_guidance_action_dependencies,
    apply_guided_solve_sequence as _apply_guided_solve_sequence_extracted,
    apply_guidance_action as _apply_guidance_action_extracted,
)
from inputs_page_modules.guidance_compute import (
    compute_design_guidance_items,
)
from inputs_page_modules.recommendation_compute import (
    _SHEAR_RECOMMENDATION_NAMES,
    _bind_named_recommendation_globals,
    compute_bottom_reo_recommendation,
    compute_geometry_recommendation,
    compute_shear_recommendation,
    _shear_ladder_validate_candidate as _shear_ladder_validate_candidate_extracted,
)
from inputs_page_modules.recommendation_compound_candidates import (
    bind_recommendation_compound_candidate_dependencies as _bind_recommendation_compound_candidate_dependencies,
    _append_geometry_bottom_compound_candidates as _append_geometry_bottom_compound_candidates_extracted,
)
from inputs_page_modules.recommendation_apply import (
    apply_bottom_reo_recommendation,
    apply_geometry_recommendation,
    apply_shear_recommendation,
)
from inputs_page_modules.widget_reconciliation import (
    reconcile_design_action_widgets_with_shared,
    reconcile_inputs_shear_widgets_with_shared,
)
from optimisation_config import target_band_payload
from state_and_helpers import (
    BEAM_STATUS_FAIL,
    RESULT_KEYS,
    SHARED_DEFAULTS,
    TAB_KEYS,
    build_legacy_longitudinal_mirrors_from_rows,
    derive_design_actions,
    effective_depth_with_links_mm,
    finalize_auto_design_publish,
    get_param,
    get_longitudinal_row_inputs,
    get_widget_key_for_shared,
    _invalidate_inputs_summary_packs,
    is_design_governing,
    mark_user_edit,
    normalize_final_published_shear_truth,
    get_rerun_pure_cache,
    persist_active_beam_from_shared,
    persist_state_snapshot,
    publish_normalized_final_shear_truth_to_session,
    resolve_design_actions,
    set_shared,
    set_rerun_pure_cache,
    speed_profile_record,
    stable_fingerprint_for_payload,
    speed_profiled,
    ux_probe_record,
)
from widgets_helpers import info_i_button, main_longitudinal_reo_change_line_prefixes


DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY = "_design_guide_component_apply_in_flight"
DESIGN_GUIDE_PUBLICATION_FP_KEY = "design_guide_publication_fingerprint"
DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY = "_design_guide_apply_trace_run_id"
DESIGN_GUIDE_APPLY_TRACE_META_KEY = "_design_guide_apply_trace_meta"
DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY = inputs_page_app_contracts.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY
DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY = (
    inputs_page_app_contracts.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY
)
AUTO_DESIGN_AUTO_INVOKE_KEY = "_auto_design_auto_invoke"
AUTO_DESIGN_REQUEST_TS_KEY = "_auto_design_requested_at_ts"
AUTO_DESIGN_REQUEST_SOURCE_KEY = "_auto_design_request_source"
_AGENT_DEBUG_LOG_PATH = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/complete-app/.cursor/debug.log"
EFFICIENCY_TARGET_UTIL_MIN = inputs_page_app_contracts.EFFICIENCY_TARGET_UTIL_MIN
EFFICIENCY_TARGET_UTIL_MAX = inputs_page_app_contracts.EFFICIENCY_TARGET_UTIL_MAX
TARGET_BAND_EPS = inputs_page_app_contracts.TARGET_BAND_EPS
FINAL_ACCEPTED_MIN_FAMILY_UTIL = inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL
GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD = 0.95
GUIDANCE_SHEAR_UTIL_NEGLIGIBLE = 0.08
AUTO_DESIGN_MAX_STAGE_CANDIDATES = 20
DEBUG_DESIGN_GUIDANCE_PROBE = True
DESIGN_GUIDE_APPLY_BANNER_KEY = "_design_guide_apply_banner_payload"
DESIGN_GUIDE_APPLY_BANNER_META_KEY = "_design_guide_apply_banner_meta"
DESIGN_GUIDE_DEBUG_BUNDLE_KEY = "_design_guide_debug_bundle"
DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY = "_design_guide_geometry_trial_debug"
DESIGN_GUIDE_INTENTS = frozenset(
    {
        "required_fix",
        "efficiency_tightening",
        "optional_cleanup",
        "already_efficient",
        "advisory_warning",
    }
)
DESIGN_GUIDE_LAST_AUTO_GEOM_KEY = "design_guide_last_applied_auto_geometry"
DESIGN_GUIDE_LAST_USER_GEOM_KEY = "design_guide_last_user_geometry"
DESIGN_GUIDE_NEEDS_REFRESH_KEY = "_design_guide_needs_refresh"
DESIGN_GUIDE_PANEL_BASELINE_FP_KEY = "_design_guide_panel_baseline_fingerprint"
DESIGN_GUIDE_PENDING_STEP_CTX_KEY = "_design_guide_pending_step_ctx"
DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY = "design_guide_primary_apply_payload"
DESIGN_GUIDE_RECO_TRACE_KEY = "_design_guide_reco_trace"
DESIGN_GUIDE_REFERENCE_B_KEY = "design_guide_reference_b"
DESIGN_GUIDE_SESSION_ANCHOR_D_KEY = "design_guide_session_anchor_D"
DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY = "_design_guide_fp"
DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY = "_design_guide_cache"
DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT = "design_guide_title_alignment_verification"
GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM = (25, 50)
_COMPOUND_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})
_DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS = DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
_ACTIVE_GUIDANCE_RECO_TRACE: list[dict] | None = None
_complete_exact_blocker_map_from_attempts = None
_design_guide_blocker_attempts_table = None
_exact_cleanup_blocker_for_outside_target_action = None
_post_click_low_bending_resolution_item = None
_publishable_safe_cleanup_updates_from_evidence = None
_BRIDGE_PROVIDER = sys.modules[__name__]
_current_coordinators.configure_design_guide_current_provider(
    _BRIDGE_PROVIDER,
    st_module=st,
    os_module=os,
    sys_module=sys,
)
_DESIGN_GUIDE_CURRENT_COORDINATOR_OWNER = _current_coordinators
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
CANONICAL_NO_SHEAR_SLIG_MM = 200.0
INPUTS_PAGE_TAB_KEYS = {sk: wk for wk, sk in TAB_KEYS.items() if str(wk).startswith("inputs_")}
_SUMMARY_OVERLAY_SKIP_SHARED_KEYS = (
    "results_version",
    "pending_recommendation",
    "_solver_result",
    "_bend_pack",
    "_shear_pack",
    "_crack_pack",
    "_defl_pack",
    "_summary_cache_version",
    "_summary_cache_action_fp",
)
_SUMMARY_OVERLAY_SKIP_LONGITUDINAL_KEYS = (
    "bot_row_count",
    "top_row_count",
    "bot1_layout_mode",
    "bot1_count",
    "bot1_spacing",
    "db_bot_1",
    "bot2_layout_mode",
    "bot2_count",
    "bot2_spacing",
    "db_bot_2",
    "top1_layout_mode",
    "top1_count",
    "top1_spacing",
    "db_top_1",
    "top2_layout_mode",
    "top2_count",
    "top2_spacing",
    "db_top_2",
)
_SUMMARY_OVERLAY_SKIP_PREFIXES = (
    "bot_row_",
    "top_row_",
)
_SHEAR_TRIPLE_DEFERRED_OVERLAY_KEYS = ("s_lig", "lig_d", "lig_legs")
_SUMMARY_DESIGN_ACTION_RESULT_KEYS = (
    "Mu_star",
    "Mu_star_kNm",
    "Mu_star_kNm_signed",
    "Vu_star",
    "sfd_Mmax_abs_kNm",
    "sfd_Vmax_abs_kN",
    "M_pos_max_uls_kNm",
    "M_neg_min_uls_kNm",
    "M_pos_max_sls_kNm",
    "M_neg_min_sls_kNm",
    "sfd_Msls_max_kNm",
    "sfd_Vsls_max_kN",
)
_CURRENT_SHEAR_TRUTH_SESSION_KEYS: tuple[str, ...] = (
    "shear_design_status",
    "shear_envelope_status",
    "shear_truth_status",
    "shear_truth_reason",
    "shear_truth_util_governing",
    "shear_truth_web_util_governing",
    "shear_truth_util_source",
    "shear_truth_web_util_source",
    "shear_truth_governing_check_name",
    "shear_truth_governing_reason",
    "shear_truth_governing_source",
    "shear_util_governing",
    "shear_util_min",
    "final_shear_status_source",
    "final_shear_truth_resolved",
    "final_shear_truth_failure_reason",
    "final_shear_spacing_reason",
    "final_shear_publication_path",
    "final_shear_truth_bundle_complete",
    "shear_required_spacing_mm",
    "shear_effective_spacing_mm",
    "shear_governing_spacing_source",
    "published_result_spacing_mm",
    "published_result_spacing_meaning",
    "shear_provided_input_spacing_mm",
    "shear_input_spacing_mm",
    "shear_sectional_check_spacing_mm",
    "V_eq_kN",
    "Vu_star",
    "uls_Vstar",
    "load_Vstar_proxy",
    "shear_Vu_total_kN",
    "phi_Vu_cap",
    "phi_Vu_max_kN",
    "phiVu_max",
    "phi_vu_max",
)
_RECOMMENDATION_NON_COMMIT_STATUSES = frozenset(
    {
        "blocked",
        "failed",
        "no_action",
        "no_actionable_full_coverage_candidate",
        "rejected",
    }
)


def _agent_debug_log(
    message: str,
    data: dict | None = None,
    *,
    location: str,
    hypothesis_id: str,
    run_id: str = "auto_design_debug",
) -> None:
    try:
        timestamp = int(datetime.now().timestamp() * 1000)
        payload = {
            "id": f"log_{timestamp}_{hypothesis_id}",
            "timestamp": timestamp,
            "location": location,
            "message": message,
            "data": data or {},
            "runId": run_id,
            "hypothesisId": hypothesis_id,
        }
        with open(_AGENT_DEBUG_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def _design_guide_tracer_path() -> str:
    p = (os.environ.get("DESIGN_GUIDE_TRACER_PATH") or "").strip()
    if p:
        return p
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "design_guide_tracer.jsonl")


def _new_design_guide_trace_run_id(prefix: str = "dg") -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:10]}"


def _design_guide_tracer_verbose_log() -> bool:
    try:
        if bool(st.session_state.get("_dev_mode")):
            return True
    except Exception:
        pass
    return str(os.environ.get("DESIGN_GUIDE_TRACER_DEBUG") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _append_design_guide_trace(
    event: str,
    data: dict,
    *,
    run_id: str,
    source: str,
) -> None:
    _append_design_guide_trace_extracted(
        event,
        data,
        run_id=run_id,
        source=source,
        tracer_path_fn=_design_guide_tracer_path,
        tracer_verbose_log_fn=_design_guide_tracer_verbose_log,
        agent_debug_log_fn=_agent_debug_log,
        append_failure_location="inputs_page.py:_append_design_guide_trace",
    )


def _trace_compact_overview_dict(overview: dict | None) -> dict:
    if not isinstance(overview, dict):
        return {}
    return {
        "worst_util": overview.get("worst_util"),
        "statuses": dict(overview.get("statuses") or {}),
        "all_key_pass": bool(overview.get("all_key_pass")),
    }


def _trace_compact_shared_geom_reo(state: dict | None) -> dict:
    if not isinstance(state, dict):
        return {}
    try:
        lig = (
            f'{_int_from_state(state, "lig_legs", 0)}xD{_int_from_state(state, "lig_d", 0)}'
            f'@{_float_from_state(state, "s_lig", 0.0):.0f}'
        )
    except Exception:
        lig = None
    try:
        bottom = _bottom_reo_state_label(state)
    except Exception:
        bottom = None
    return {
        "b": state.get("b"),
        "D": state.get("D"),
        "Ast_bot": state.get("Ast_bot"),
        "bottom_label": bottom,
        "ligatures_compact": lig,
    }


def _design_guide_trace_compare_meta(
    *,
    run_id: str,
    action_signature: str | None,
    goal: str | None,
    starting_worst_util: float | None,
    ending_worst_util: float | None,
    stop_reason: str | None,
    winner_label: str | None,
    final_updates: dict | None,
) -> dict:
    return {
        "run_id": str(run_id),
        "action_signature": action_signature,
        "goal": goal,
        "starting_worst_util": starting_worst_util,
        "ending_worst_util": ending_worst_util,
        "stop_reason": stop_reason,
        "winner_label": winner_label,
        "final_updates": dict(final_updates or {}),
    }


def _begin_design_guide_apply_trace(
    *,
    recommendation: dict | None,
    source: str,
) -> str | None:
    if not isinstance(recommendation, dict):
        return None
    run_id = _new_design_guide_trace_run_id("dgapply")
    action_type = str(
        recommendation.get("action_type")
        or recommendation.get("_source")
        or "apply_recommendation"
    ).strip() or "apply_recommendation"
    title = str(recommendation.get("title") or "").strip()
    current_state = _shared_state_snapshot()
    current_overview = _collect_design_overview(
        current_state,
        context=_build_design_actions_context_for_app_bridge(current_state),
    )
    starting_worst_util = current_overview.get("worst_util") if isinstance(current_overview, dict) else None
    meta = {
        "run_id": run_id,
        "source": str(source or "design_guide_apply").strip() or "design_guide_apply",
        "action_type": action_type,
        "title": title,
        "starting_worst_util": starting_worst_util,
    }
    st.session_state[DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY] = run_id
    st.session_state[DESIGN_GUIDE_APPLY_TRACE_META_KEY] = dict(meta)
    _append_design_guide_trace(
        "run_start",
        {
            "entry_source": meta["source"],
            "request_source": meta["source"],
            "current_shared_compact": _trace_compact_shared_geom_reo(current_state),
            "current_overview": _trace_compact_overview_dict(current_overview),
            "recommendation_title": title,
            "recommendation_action_type": action_type,
            "compare": _design_guide_trace_compare_meta(
                run_id=run_id,
                action_signature=action_type,
                goal="design_guide_apply",
                starting_worst_util=starting_worst_util,
                ending_worst_util=None,
                stop_reason=None,
                winner_label=title or None,
                final_updates={},
            ),
        },
        run_id=run_id,
        source=meta["source"],
    )
    return run_id


def _emit_design_guide_apply_trace_run_end(
    *,
    stop_reason: str,
    final_updates: dict | None = None,
    winner_label: str | None = None,
    final_util_override: float | None = None,
    final_statuses_override: dict | None = None,
) -> None:
    _bind_apply_trace_run_end_dependencies(globals())
    return _emit_design_guide_apply_trace_run_end_extracted(
        stop_reason=stop_reason,
        final_updates=final_updates,
        winner_label=winner_label,
        final_util_override=final_util_override,
        final_statuses_override=final_statuses_override,
    )


def _recommendation_updates_for_envelope(recommendation: dict | None) -> dict:
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


def _build_recommendation_envelope(
    *,
    updates: dict | None = None,
    source: str = "",
    status: str = "",
    blocked_reason: str | None = None,
    commit_eligible: bool | None = None,
    preview: dict | None = None,
    audit: dict | None = None,
    required_domains: list | tuple | set | None = None,
) -> dict:
    updates_d = dict(updates or {}) if isinstance(updates, dict) else {}
    status_norm = str(status or "").strip()
    reason_norm = str(blocked_reason or "").strip()
    if commit_eligible is None:
        commit_eligible = bool(updates_d) and not reason_norm and status_norm not in _RECOMMENDATION_NON_COMMIT_STATUSES
    if isinstance(required_domains, str):
        domains_iter = [required_domains]
    else:
        domains_iter = list(required_domains or []) if required_domains is not None else []
    ordered_domains = [
        str(d or "").strip().lower()
        for d in domains_iter
        if str(d or "").strip()
    ]
    envelope_status = status_norm or ("ready" if commit_eligible else "blocked" if reason_norm else "advisory")
    return {
        "version": 1,
        "source": str(source or "").strip() or None,
        "status": envelope_status,
        "updates": updates_d,
        "commit_eligible": bool(commit_eligible),
        "blocked_reason": reason_norm or None,
        "required_domains": ordered_domains,
        "preview": dict(preview or {}) if isinstance(preview, dict) else {},
        "audit": dict(audit or {}) if isinstance(audit, dict) else {},
    }


def _attach_recommendation_envelope(
    recommendation: dict | None,
    *,
    source: str,
    status: str = "ready",
    blocked_reason: str | None = None,
    commit_eligible: bool | None = None,
    preview: dict | None = None,
    audit: dict | None = None,
    required_domains: list | tuple | set | None = None,
) -> dict | None:
    if not isinstance(recommendation, dict):
        return None
    out = dict(recommendation)
    envelope = _build_recommendation_envelope(
        updates=_recommendation_updates_for_envelope(out),
        source=source,
        status=status,
        blocked_reason=blocked_reason,
        commit_eligible=commit_eligible,
        preview=preview,
        audit=audit,
        required_domains=required_domains,
    )
    out["recommendation_envelope"] = envelope
    out["commit_eligible"] = bool(envelope.get("commit_eligible"))
    out["blocked_reason"] = envelope.get("blocked_reason")
    return out


def _recommendation_envelope_from_pending(recommendation: dict | None) -> dict:
    if not isinstance(recommendation, dict):
        return {}
    envelope = recommendation.get("recommendation_envelope")
    if isinstance(envelope, dict):
        return dict(envelope)
    meta = dict(recommendation.get("meta") or {})
    status = str(meta.get("status") or recommendation.get("status") or "").strip()
    reason = str(
        recommendation.get("blocked_reason")
        or meta.get("blocked_reason")
        or meta.get("reason")
        or ""
    ).strip()
    return _build_recommendation_envelope(
        updates=_recommendation_updates_for_envelope(recommendation),
        source=str(recommendation.get("_source") or recommendation.get("source") or "legacy_pending"),
        status=status,
        blocked_reason=reason or None,
    )


def _recommendation_blocked_reason(recommendation: dict | None) -> str | None:
    envelope = _recommendation_envelope_from_pending(recommendation)
    reason = str(envelope.get("blocked_reason") or "").strip()
    if reason:
        return reason
    if isinstance(recommendation, dict) and not bool(envelope.get("commit_eligible")):
        status = str(envelope.get("status") or "").strip()
        if status in _RECOMMENDATION_NON_COMMIT_STATUSES:
            return status
    return None


def _recommendation_commit_eligible(recommendation: dict | None) -> bool:
    envelope = _recommendation_envelope_from_pending(recommendation)
    return bool(envelope.get("commit_eligible"))


def _set_design_guide_primary_payload_binding_audit(**updates: object) -> dict:
    audit = dict(st.session_state.get(DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY) or {})
    preserved_when_blank = {
        "queued_apply_candidate_id",
        "applied_candidate_id",
        "queued_apply_updates",
        "applied_updates",
        "applied_changed_keys",
        "actual_changed_updates",
        "stale_candidate_changed_keys",
    }
    for key, value in updates.items():
        if (
            key in preserved_when_blank
            and audit.get(key) not in (None, {}, [])
            and value in (None, {}, [])
        ):
            continue
        audit[key] = value
    ids = [
        str(audit.get("visible_primary_candidate_id") or "").strip(),
        str(audit.get("button_contract_candidate_id") or "").strip(),
        str(audit.get("queued_apply_candidate_id") or "").strip(),
        str(audit.get("applied_candidate_id") or "").strip(),
    ]
    present_ids = [value for value in ids if value]
    if present_ids:
        audit["payload_binding_match"] = len(set(present_ids)) == 1
    maps = [
        audit.get("visible_updates"),
        audit.get("button_contract_updates"),
        audit.get("queued_apply_updates"),
        audit.get("applied_updates"),
    ]
    present_maps = [dict(value or {}) for value in maps if isinstance(value, dict) and value]
    if present_maps:
        audit["payload_update_match"] = all(candidate == present_maps[0] for candidate in present_maps[1:])
    st.session_state[DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY] = dict(audit)
    return audit


def _set_one_click_run_feedback(
    *,
    status: str,
    reason: str | None,
    winning_label: str | None = None,
    winning_action_type: str | None = None,
    pre_commit_worst_util: float | None = None,
    extra_payload: dict | None = None,
    debug_target: dict | None = None,
) -> None:
    payload = {
        "status": str(status or "").strip() or "blocked",
        "reason": str(reason or "").strip() or "unknown",
        "winning_label": str(winning_label or "").strip() or None,
        "winning_action_type": str(winning_action_type or "").strip() or None,
        "pre_commit_worst_util": pre_commit_worst_util,
    }
    if isinstance(extra_payload, dict):
        payload.update(dict(extra_payload))
    st.session_state["_one_click_run_feedback"] = payload
    if isinstance(debug_target, dict):
        debug_target["one_click_run_feedback_status"] = payload["status"]
        debug_target["one_click_run_feedback_reason"] = payload["reason"]


def render_design_guide_panel_entry_trace_and_stage_coordinator(**kwargs):
    return _panel_coordinators.render_design_guide_panel_entry_trace_and_stage_coordinator(**kwargs)


def render_design_guide_initial_state_and_loading_coordinator(
    *,
    inputs_render_audit: dict[str, str] | None = None,
):
    return _panel_coordinators.render_design_guide_initial_state_and_loading_coordinator(
        current_owner=_DESIGN_GUIDE_CURRENT_COORDINATOR_OWNER,
        inputs_render_audit=inputs_render_audit,
    )


def render_design_guide_compute_preparation_coordinator(
    *,
    settle_gate_decision: dict,
    current_state: dict,
    fingerprint,
):
    return _panel_coordinators.render_design_guide_compute_preparation_coordinator(
        settle_gate_decision=settle_gate_decision,
        current_state=current_state,
        fingerprint=fingerprint,
    )


def render_design_guide_postprocess_pre_render_plan_coordinator(
    *,
    guidance_items_raw: list[dict],
    guidance_debug: dict,
    guidance_disp_state: dict,
    current_state: dict,
    fingerprint,
    fast_focus_section: str | None,
    guidance_fresh_compute_used: bool,
    sidebar_debug: bool,
    _stage,
):
    return _panel_coordinators.render_design_guide_postprocess_pre_render_plan_coordinator(
        current_owner=_DESIGN_GUIDE_CURRENT_COORDINATOR_OWNER,
        guidance_items_raw=guidance_items_raw,
        guidance_debug=guidance_debug,
        guidance_disp_state=guidance_disp_state,
        current_state=current_state,
        fingerprint=fingerprint,
        fast_focus_section=fast_focus_section,
        guidance_fresh_compute_used=guidance_fresh_compute_used,
        sidebar_debug=sidebar_debug,
        _stage=_stage,
    )


def render_design_guide_active_guard_presentation_engine_coordinator(
    *,
    current_state: dict,
    guidance_debug: dict,
    guidance_items: list[dict],
    guidance_disp_state: dict,
    terminal_state,
    terminal_state_source: str,
    pending_recommendation,
    render_plan: dict,
    sidebar_debug: bool,
    guidance_compute_ms,
    guidance_cache_hit: bool,
    banner_generic_only: bool,
    fast_focus_section: str | None,
    guidance_dedupe_meta: dict,
    _recommendation_result,
):
    return _panel_coordinators.render_design_guide_active_guard_presentation_engine_coordinator(
        current_owner=_DESIGN_GUIDE_CURRENT_COORDINATOR_OWNER,
        current_state=current_state,
        guidance_debug=guidance_debug,
        guidance_items=guidance_items,
        guidance_disp_state=guidance_disp_state,
        terminal_state=terminal_state,
        terminal_state_source=terminal_state_source,
        pending_recommendation=pending_recommendation,
        render_plan=render_plan,
        sidebar_debug=sidebar_debug,
        guidance_compute_ms=guidance_compute_ms,
        guidance_cache_hit=guidance_cache_hit,
        banner_generic_only=banner_generic_only,
        fast_focus_section=fast_focus_section,
        guidance_dedupe_meta=guidance_dedupe_meta,
        _recommendation_result=_recommendation_result,
    )


def render_design_guide_presentation_post_cleanup_gate_coordinator(
    *,
    guidance_items: list[dict],
    dg_presentation: dict,
    recommendation_result,
    guidance_debug: dict,
    terminal_state,
    terminal_state_source: str,
    dg_overview,
):
    return _panel_coordinators.render_design_guide_presentation_post_cleanup_gate_coordinator(
        guidance_items=guidance_items,
        dg_presentation=dg_presentation,
        recommendation_result=recommendation_result,
        guidance_debug=guidance_debug,
        terminal_state=terminal_state,
        terminal_state_source=terminal_state_source,
        dg_overview=dg_overview,
    )


def render_design_guide_post_cleanup_publication_pre_render_coordinator(
    *,
    guidance_items: list[dict],
    terminal_state,
    terminal_state_source: str,
    dg_overview,
    dg_presentation: dict,
    render_plan: dict,
    guidance_debug: dict,
    post_cleanup_render_audit: dict,
):
    return _panel_coordinators.render_design_guide_post_cleanup_publication_pre_render_coordinator(
        guidance_items=guidance_items,
        terminal_state=terminal_state,
        terminal_state_source=terminal_state_source,
        dg_overview=dg_overview,
        dg_presentation=dg_presentation,
        render_plan=render_plan,
        guidance_debug=guidance_debug,
        post_cleanup_render_audit=post_cleanup_render_audit,
    )


def render_design_guide_final_render_branch_dispatch_coordinator(
    *,
    final_visible_resolution,
    terminal_state_current_in_target: bool,
    guidance_debug: dict,
    render_plan: dict,
    dg_presentation: dict,
    fingerprint,
    guidance_items_raw: list[dict],
    guidance_disp_state: dict,
    dg_overview,
    inputs_render_audit: dict[str, str] | None,
    terminal_state,
    guidance_items: list[dict],
    render_post_apply_banner: bool,
    fast_focus_section: str | None,
):
    return _panel_coordinators.render_design_guide_final_render_branch_dispatch_coordinator(
        current_owner=_DESIGN_GUIDE_CURRENT_COORDINATOR_OWNER,
        final_visible_resolution=final_visible_resolution,
        terminal_state_current_in_target=terminal_state_current_in_target,
        guidance_debug=guidance_debug,
        render_plan=render_plan,
        dg_presentation=dg_presentation,
        fingerprint=fingerprint,
        guidance_items_raw=guidance_items_raw,
        guidance_disp_state=guidance_disp_state,
        dg_overview=dg_overview,
        inputs_render_audit=inputs_render_audit,
        terminal_state=terminal_state,
        guidance_items=guidance_items,
        render_post_apply_banner=render_post_apply_banner,
        fast_focus_section=fast_focus_section,
    )


def render_design_guide_panel_exit_state(**kwargs) -> None:
    return _panel_coordinators.render_design_guide_panel_exit_state(**kwargs)


def run_one_click_auto_design(
    *,
    trigger_fingerprint: tuple | None = None,
    entry_source: str = "inputs_handle_auto_design",
) -> dict:
    return run_one_click_auto_design_coordinator(
        _BRIDGE_PROVIDER,
        st,
        sys,
        trigger_fingerprint=trigger_fingerprint,
        entry_source=entry_source,
    )


def _compute_geometry_recommendation(state: dict) -> dict | None:
    return compute_geometry_recommendation(_BRIDGE_PROVIDER, state)


def _compute_bottom_reo_recommendation(state: dict) -> dict | None:
    return compute_bottom_reo_recommendation(_BRIDGE_PROVIDER, state)


def _compute_shear_recommendation(state: dict) -> dict | None:
    return compute_shear_recommendation(_BRIDGE_PROVIDER, state)


def apply_recommendation_result(rec: dict) -> str:
    return apply_recommendation_result_coordinator(
        legacy_page=_BRIDGE_PROVIDER,
        st_module=st,
        sys_module=sys,
        rec=rec,
    )


def _apply_geometry_recommendation(*, source: str) -> bool:
    return apply_geometry_recommendation(_BRIDGE_PROVIDER, source=source)


def _apply_bottom_reo_recommendation(*, source: str) -> bool:
    return apply_bottom_reo_recommendation(_BRIDGE_PROVIDER, source=source)


def _apply_shear_recommendation(*, source: str) -> bool:
    return apply_shear_recommendation(_BRIDGE_PROVIDER, source=source)


def _reconcile_design_action_widgets_with_shared(selected_prefix: str) -> list[str]:
    return reconcile_design_action_widgets_with_shared(
        _BRIDGE_PROVIDER,
        st,
        selected_prefix,
    )


def _reconcile_inputs_shear_widgets_with_shared() -> list[str]:
    return reconcile_inputs_shear_widgets_with_shared(
        _BRIDGE_PROVIDER,
        st,
    )


def _clear_auto_design_runtime_latches(reason: str) -> dict:
    ss = st.session_state
    before = {
        "_solver_running": bool(ss.get("_solver_running", False)),
        "_compute_in_progress": bool(ss.get("_compute_in_progress", False)),
        "auto_design_latch_owner": str(ss.get("auto_design_latch_owner") or ""),
        "auto_design_invoke_consumed": bool(ss.get("auto_design_invoke_consumed", False)),
    }
    ss["_solver_running"] = False
    ss["_compute_in_progress"] = False
    ss["auto_design_latch_owner"] = ""
    ss["auto_design_invoke_consumed"] = False
    payload = {
        "reason": str(reason or ""),
        "before": before,
        "after": {
            "_solver_running": bool(ss.get("_solver_running", False)),
            "_compute_in_progress": bool(ss.get("_compute_in_progress", False)),
            "auto_design_latch_owner": str(ss.get("auto_design_latch_owner") or ""),
            "auto_design_invoke_consumed": bool(ss.get("auto_design_invoke_consumed", False)),
        },
    }
    ss["_auto_design_latch_clear_latest"] = dict(payload)
    return payload


def _set_design_guide_live_breadcrumb(label: str, extra: dict | None = None) -> None:
    try:
        st.session_state["_dg_live_breadcrumb"] = {
            "label": str(label),
            "extra": dict(extra or {}),
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
    except Exception:
        pass


def _inputs_hydration_trace_log(phase: str, **extra: object) -> None:
    """Preserve the current app-facing hydration trace behavior.

    The old helper returns before emitting a log entry even when dev tracing is
    enabled, so this local bridge intentionally remains a no-op.
    """

    _ = phase
    _ = extra


def _pop_inputs_widget_keys_for_shared_updates(updates: dict) -> set[str]:
    if not updates:
        return set()
    alias_widget_keys: dict[str, list[str]] = {
        "db_bot_1": ["inputs_db_bot_1", "inputs_nb_or_s_bot_1"],
        "db_bot_2": ["inputs_db_bot_2", "inputs_nb_or_s_bot_2"],
        "db_top_1": ["inputs_db_top_1", "inputs_nb_or_s_top_1"],
        "db_top_2": ["inputs_db_top_2", "inputs_nb_or_s_top_2"],
        "bot1_layout_mode": ["inputs_bot1_layout_mode"],
        "bot1_count": ["inputs_bot1_count"],
        "bot1_spacing": ["inputs_bot1_spacing"],
        "bot2_layout_mode": ["inputs_bot2_layout_mode"],
        "bot2_count": ["inputs_bot2_count"],
        "bot2_spacing": ["inputs_bot2_spacing"],
        "top1_layout_mode": ["inputs_top1_layout_mode"],
        "top1_count": ["inputs_top1_count"],
        "top1_spacing": ["inputs_top1_spacing"],
        "top2_layout_mode": ["inputs_top2_layout_mode"],
        "top2_count": ["inputs_top2_count"],
        "top2_spacing": ["inputs_top2_spacing"],
    }
    shear_widget_trio = {"inputs_s_lig", "inputs_lig_d", "inputs_lig_legs"}
    cleared: set[str] = set()
    hydrated_map = st.session_state.get("_hydrated_from_shared_map")
    clear_shear_trio = any(key in {"s_lig", "lig_d", "lig_legs"} for key in list(updates.keys()))
    for key in list(updates.keys()):
        widget_keys_to_clear = [f"inputs_{key}"]
        widget_keys_to_clear.extend(alias_widget_keys.get(key, []))
        if clear_shear_trio:
            widget_keys_to_clear.extend(sorted(shear_widget_trio))
        if key.startswith(("bot_row_", "top_row_")):
            widget_keys_to_clear.append(f"inputs_{key}")
        for widget_key in widget_keys_to_clear:
            st.session_state.pop(widget_key, None)
            st.session_state.pop(f"_cached_{widget_key}", None)
            cleared.add(widget_key)
    if isinstance(hydrated_map, dict):
        for key in updates:
            hydrated_map.pop(f"inputs_{key}", None)
            for widget_key in alias_widget_keys.get(key, []):
                hydrated_map.pop(widget_key, None)
        for widget_key in cleared:
            hydrated_map.pop(widget_key, None)
    for key in list(updates.keys()):
        st.session_state.pop(f"_cached_inputs_{key}", None)
    return cleared


def _clear_design_guide_transient_ui_state(
    *,
    clear_history: bool = False,
    preserve_apply_banner: bool = False,
) -> None:
    transient_keys = [
        inputs_page_app_contracts.DESIGN_GUIDE_APPLY_BANNER_META_KEY,
        inputs_page_app_contracts.DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY,
        inputs_page_app_contracts.DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY,
        inputs_page_app_contracts.DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY,
        inputs_page_app_contracts.DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY,
        inputs_page_app_contracts.DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY,
        inputs_page_app_contracts.DESIGN_GUIDE_PENDING_STEP_CTX_KEY,
    ]
    clear_plan = build_inputs_design_guide_transient_ui_clear_plan(
        base_transient_keys=tuple(transient_keys),
        apply_banner_key=inputs_page_app_contracts.DESIGN_GUIDE_APPLY_BANNER_KEY,
        always_clear_keys=(
            inputs_page_app_contracts.DESIGN_GUIDE_DEBUG_BUNDLE_KEY,
            inputs_page_app_contracts.DESIGN_GUIDE_RECO_TRACE_KEY,
            inputs_page_app_contracts.DESIGN_GUIDE_RANK_TRACE_KEY,
        ),
        history_keys=(
            inputs_page_app_contracts.DESIGN_GUIDE_STEP_HISTORY_KEY,
            inputs_page_app_contracts.DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY,
            inputs_page_app_contracts.DESIGN_GUIDE_HISTORY_ANCHOR_KEY,
        ),
        clear_history=bool(clear_history),
        preserve_apply_banner=bool(preserve_apply_banner),
    )
    for key in clear_plan.all_keys:
        st.session_state.pop(key, None)


def _parse_util_value(value) -> float | None:
    if value in (None, "", "â€”"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _design_mode_config(goal: str | None = None) -> dict:
    resolved_goal = goal or resolve_design_optimisation_goal(
        st.session_state,
        goal_labels=DESIGN_OPTIMISATION_GOAL_LABELS,
        default_goal="balanced",
    )
    return resolve_design_mode_config(
        resolved_goal,
        mode_config_by_goal=AUTO_DESIGN_MODE_CONFIG,
        default_goal="balanced",
    )


def _design_optimisation_goal(state: dict | None = None) -> str:
    return str(
        resolve_design_optimisation_goal(
            state or st.session_state,
            goal_labels=DESIGN_OPTIMISATION_GOAL_LABELS,
            default_goal="balanced",
        )
    )


def _design_optimisation_goal_label(state: dict | None = None) -> str:
    goal = _design_optimisation_goal(state)
    return DESIGN_OPTIMISATION_GOAL_LABELS[goal]


def _resolve_geometry_width_context_for_app_bridge(state: dict) -> tuple[str, str, float]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", float(state.get("bw", state.get("b", 300.0)) or 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", float(state.get("tw", state.get("b", 200.0)) or 200.0)
    return "b", "Width b (mm)", float(state.get("b", 400.0) or 400.0)


def _resolve_geometry_width_context(state: dict) -> tuple[str, str, float]:
    return _resolve_geometry_width_context_for_app_bridge(state)


def _design_width_value_for_app_bridge(state: dict) -> float:
    _, _, width = _resolve_geometry_width_context_for_app_bridge(state)
    return float(width)


DESIGN_GUIDE_ALGORITHM_VERSION = "shear_congestion_reshape_v2"


def _get_design_guide_fp(state: dict | None = None) -> tuple:
    current_state = dict(state or {})
    return (
        "dg_cache_v2026_04_27_in_target_local_cleanup_all_families",
        DESIGN_GUIDE_ALGORITHM_VERSION,
        str(
            resolve_design_optimisation_goal(
                current_state,
                goal_labels=DESIGN_OPTIMISATION_GOAL_LABELS,
                default_goal="balanced",
            )
        ),
        str(current_state.get("sec_shape")),
        float(current_state.get("b", 0.0) or 0.0),
        float(current_state.get("D", 0.0) or 0.0),
        float(current_state.get("fc", 0.0) or 0.0),
        float(current_state.get("fsy", 0.0) or 0.0),
        float(current_state.get("uls_Mstar", 0.0) or 0.0),
        float(current_state.get("uls_Vstar", 0.0) or 0.0),
        float(current_state.get("uls_Nstar", 0.0) or 0.0),
        float(current_state.get("Tu_star", 0.0) or 0.0),
        int(current_state.get("bot_row_count", 0) or 0),
        int(current_state.get("bot1_count", 0) or 0),
        float(current_state.get("db_bot_1", 0.0) or 0.0),
        int(current_state.get("bot2_count", 0) or 0),
        float(current_state.get("db_bot_2", 0.0) or 0.0),
        float(current_state.get("lig_d", 0.0) or 0.0),
        int(current_state.get("lig_legs", 0) or 0),
        float(current_state.get("s_lig", 0.0) or 0.0),
        tuple(_resolve_design_actions_from_state(current_state).get("signature", ())),
    )


def _resolve_design_actions_from_state(state: dict) -> dict:
    return resolve_design_actions(state)


def _recommendation_fingerprint_state(state: dict) -> dict:
    fingerprint_state = {
        key: state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }
    fingerprint_state["_resolved_design_actions"] = _resolve_design_actions_from_state(state)
    return fingerprint_state


def _recommendation_cache_fingerprint(state: dict) -> str:
    fingerprint_state = _recommendation_fingerprint_state(state)
    try:
        return json.dumps(fingerprint_state, sort_keys=True, default=str)
    except Exception:
        return str(sorted((str(key), str(value)) for key, value in fingerprint_state.items()))


def _cached_recommendation(cache_name: str, state: dict):
    cache_key = f"_recommendation_cache_{cache_name}"
    cache_entry = st.session_state.get(cache_key)
    fingerprint = _recommendation_cache_fingerprint(state)
    if isinstance(cache_entry, dict) and cache_entry.get("fingerprint") == fingerprint:
        return cache_entry.get("recommendation")
    return None


def _store_cached_recommendation(cache_name: str, state: dict, recommendation) -> None:
    cache_key = f"_recommendation_cache_{cache_name}"
    st.session_state[cache_key] = {
        "fingerprint": _recommendation_cache_fingerprint(state),
        "recommendation": recommendation,
    }


def _resolve_popover_recommendation(
    *,
    cache_name: str,
    state: dict,
    button_key: str,
    compute_fn,
    empty_message: str,
):
    recommendation = _cached_recommendation(cache_name, state)
    generate_pressed = st.button(
        "Generate current recommendation" if recommendation is None else "Refresh recommendation",
        key=f"{button_key}_generate",
        type="secondary",
        use_container_width=True,
    )
    if generate_pressed:
        recommendation = compute_fn(state)
        _store_cached_recommendation(cache_name, state, recommendation)
    if recommendation is None:
        st.caption(empty_message)
    return recommendation


def _shared_state_snapshot() -> dict:
    return {
        key: st.session_state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }


def _float_from_state(state: dict, key: str, default: float) -> float:
    value = state.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _int_from_state(state: dict, key: str, default: int) -> int:
    value = state.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _shear_reinforcement_is_active(state: dict | None) -> bool:
    if not isinstance(state, dict):
        return False
    return (
        _int_from_state(state, "lig_legs", 0) >= 2
        and _int_from_state(state, "lig_d", 0) > 0
        and _float_from_state(state, "s_lig", 0.0) > 0.0
    )


def _shear_state_label(state: dict) -> str:
    legs = int(state.get("lig_legs", 0) or 0)
    if legs <= 0:
        return "No ligs"
    return (
        f"{legs}-leg "
        f"N{int(state.get('lig_d', 0) or 0)} @ {int(float(state.get('s_lig', 0.0) or 0.0))}"
    )


def _bottom_reo_state_label(state: dict) -> str:
    mode_1 = str(state.get("bot1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("bot2_layout_mode", "Count") or "Count")
    if mode_1 == "Count" and mode_2 == "Count":
        count_1 = int(state.get("bot1_count", 0) or 0)
        count_2 = int(state.get("bot2_count", 0) or 0)
        dia = int(state.get("db_bot_1", state.get("db_bot", 0)) or 0)
        if count_1 > 0:
            if count_2 > 0:
                return f"{count_1}N{dia} + {count_2}N{dia}"
            return f"{count_1}N{dia}"
    spacing_1 = float(state.get("bot1_spacing", 0.0) or 0.0)
    dia_1 = int(state.get("db_bot_1", 0) or 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _shear_severity_band(util: float | None) -> str:
    if util is None:
        return "mild"
    value = float(util)
    if value < 1.15:
        return "mild"
    if value < 1.75:
        return "moderate"
    if value < 3.0:
        return "severe"
    return "extreme"


def _severe_shear_failure(util: float | None) -> bool:
    return _shear_severity_band(util) in ("severe", "extreme")


def _updates_match_state(state: dict, updates: dict) -> bool:
    for key, expected in updates.items():
        actual = state.get(key)
        if isinstance(expected, float):
            try:
                if abs(float(actual) - float(expected)) > 1e-9:
                    return False
            except Exception:
                return False
            continue
        if actual != expected:
            return False
    return True


def _shear_cleanup_possible(state: dict | None) -> bool:
    if not isinstance(state, dict):
        return False
    lig_legs = _int_from_state(state, "lig_legs", 0)
    s_lig = _float_from_state(state, "s_lig", 0.0)
    max_spacing = float(max(REO_SPACINGS) if REO_SPACINGS else 300.0)
    return lig_legs > 0 or (s_lig > 0.0 and s_lig < max_spacing - 1e-9)


def _uls_action_from_state_for_app_bridge(state: dict, action: str) -> float:
    resolved_actions = _resolve_design_actions_from_state(state)
    resolved_map = {
        "M": "Mu",
        "V": "Vu",
        "N": "Nu",
        "T": "Tu",
        "P": "Pu",
    }
    resolved_key = resolved_map.get(action)
    if resolved_key is not None:
        mapped = resolved_actions.get(resolved_key)
        if mapped is not None:
            return float(mapped)

    shared_map = {
        "M": "uls_Mstar",
        "V": "uls_Vstar",
        "N": "uls_Nstar",
    }
    if action in shared_map:
        return _float_from_state(state, shared_map[action], 0.0)
    if action == "T":
        return _float_from_state(state, "Tu_star", 0.0)
    if action == "P":
        return _float_from_state(state, "P_star", 0.0)
    return 0.0


def _evaluate_shear_with_state_for_app_bridge(
    state: dict,
    *,
    bottom_updates: dict | None = None,
    shear_updates: dict | None = None,
) -> dict | None:
    _bind_shear_evaluation_dependencies(globals())
    return _evaluate_shear_with_state_for_app_bridge_extracted(
        state,
        bottom_updates=bottom_updates,
        shear_updates=shear_updates,
    )


def _evaluate_shear_with_state(
    state: dict,
    *,
    bottom_updates: dict | None = None,
    shear_updates: dict | None = None,
) -> dict | None:
    return _evaluate_shear_with_state_for_app_bridge(
        state,
        bottom_updates=bottom_updates,
        shear_updates=shear_updates,
    )


def _shear_results_allow_no_transverse_links_for_app_bridge(res, *, phi: float) -> bool:
    if res is None:
        return False
    if bool(getattr(res, "torsion_required", True)):
        return False
    if not bool(getattr(res, "shear_ok", False)):
        return False
    veq = float(getattr(res, "V_eq", 0.0) or 0.0)
    vuc = float(getattr(res, "Vuc_kN", 0.0) or 0.0)
    phi_f = float(phi)
    if vuc <= 1e-12:
        return abs(veq) <= 1e-6
    if veq > 0.5 * phi_f * vuc + 1e-6:
        return False
    return True


def _shear_state_eligible_for_no_links(state: dict) -> bool:
    s_nom = float(max(_float_from_state(state, "s_lig", 200.0), 1.0))
    preview = _evaluate_shear_with_state_for_app_bridge(
        state,
        shear_updates={"lig_legs": 0, "lig_d": 0, "s_lig": s_nom},
    )
    if not preview:
        return False
    res = preview.get("results")
    phi = _float_from_state(state, "phi_shear", 0.75)
    return _shear_results_allow_no_transverse_links_for_app_bridge(res, phi=phi)


def _shear_demands_negligible(actions: dict | None) -> bool:
    if not isinstance(actions, dict):
        return False
    try:
        vu = abs(float(actions.get("Vu", 0.0) or 0.0))
        tu = abs(float(actions.get("Tu", 0.0) or 0.0))
    except (TypeError, ValueError):
        return False
    return (
        vu <= inputs_page_app_contracts.GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN + 1e-12
        and tu <= inputs_page_app_contracts.GUIDANCE_TORSION_DEMAND_ABS_TOL_KNM + 1e-12
    )


_ACCEPTED_GREEN_EXACT_BLOCKER_REQUIRED_FIELDS = (
    "family",
    "current_util",
    "threshold",
    "attempted_candidate_count",
    "best_rejected_candidate_id",
    "attempted_updates",
    "failed_check_name",
    "failed_check_status",
    "failed_check_util",
    "failed_check_demand",
    "failed_check_capacity_or_limit",
)


def _accepted_green_exact_blocker_is_valid(blocker: dict | None) -> bool:
    if not isinstance(blocker, dict):
        return False
    for field in _ACCEPTED_GREEN_EXACT_BLOCKER_REQUIRED_FIELDS:
        value = blocker.get(field)
        if value in (None, "", [], {}) and field == "failed_check_demand":
            value = blocker.get("demand")
        if value in (None, "", [], {}) and field == "failed_check_capacity_or_limit":
            value = blocker.get("capacity_or_limit")
        if value in (None, "", [], {}):
            return False
    reason = str(
        blocker.get("why_reduction_would_hurt_other_design_elements")
        or blocker.get("reason_reducing_this_family_would_affect_other_design_elements")
        or blocker.get("reason")
        or ""
    ).strip().lower()
    if not reason:
        return False
    if reason in {"no safe cleanup found", "candidate failed", "engineering constraint"}:
        return False
    return True


def _overview_family_utils_for_local_cleanup(overview: dict | None) -> dict[str, float]:
    ov = overview if isinstance(overview, dict) else {}
    utils = dict(ov.get("utils") or {})
    out: dict[str, float] = {}
    for key, value in utils.items():
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed):
            out[str(key or "").strip().lower()] = parsed
    packs = dict(ov.get("packs") or {})
    for key, pack in packs.items():
        if not isinstance(pack, dict):
            continue
        family = str(key or "").strip().lower()
        if family == "serviceability":
            family = "deflection"
        for field in ("summary_util", "util", "governing_util", "max_util"):
            try:
                parsed = float(pack.get(field))
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                out.setdefault(family, parsed)
                break
    for family in ("bending", "shear", "crack", "deflection", "serviceability", "ductility"):
        for field in (f"{family}_util", f"{family}_utilisation"):
            if family in out:
                continue
            try:
                parsed = float(ov.get(field))
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                out[family] = parsed
    return out


def _governing_family_for_local_cleanup(
    overview: dict | None,
    family_utils: dict[str, float],
) -> str | None:
    ov = overview if isinstance(overview, dict) else {}
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
    if family_utils:
        try:
            return max(family_utils.items(), key=lambda item: item[1])[0]
        except Exception:
            return None
    return None


def identify_materially_overprovided_non_governing_families(
    overview: dict | None,
    *,
    threshold: float = 0.70,
) -> tuple[dict[str, float], list[str], str | None]:
    family_utils = _overview_family_utils_for_local_cleanup(overview)
    governing = _governing_family_for_local_cleanup(overview, family_utils)
    families = [
        family
        for family, util in sorted(family_utils.items())
        if family != governing
        and float(util) < float(threshold)
        and not (family in {"crack", "deflection", "serviceability", "geometry"} and float(util) <= 1e-9)
    ]
    return family_utils, families, governing


def _guidance_state_snapshot_for_app_bridge(state: dict | None = None) -> dict:
    snapshot = dict(state or {})
    stale_solver_keys = {
        "pending_recommendation",
        "_solver_result",
        "_one_click_run_feedback",
        "_bend_pack",
        "_shear_pack",
        "_crack_pack",
        "_defl_pack",
        "_summary_cache_version",
        "_summary_cache_action_fp",
        "_final_shear_truth_normalized_source",
        "_final_shear_truth_normalized_latest",
    }
    stale_shear_publication_keys = {
        "shear_design_status",
        "shear_envelope_status",
        "shear_truth_status",
        "shear_truth_reason",
        "shear_truth_util_governing",
        "shear_truth_web_util_governing",
        "shear_truth_util_source",
        "shear_truth_web_util_source",
        "shear_truth_governing_check_name",
        "shear_truth_governing_reason",
        "shear_truth_governing_source",
        "shear_util_governing",
        "shear_util_min",
        "final_shear_status_source",
        "final_shear_truth_resolved",
        "final_shear_truth_failure_reason",
        "final_shear_spacing_reason",
        "final_shear_publication_path",
        "final_shear_truth_bundle_complete",
        "shear_required_spacing_mm",
        "shear_effective_spacing_mm",
        "shear_governing_spacing_source",
        "published_result_spacing_mm",
        "published_result_spacing_meaning",
        "shear_provided_input_spacing_mm",
        "shear_input_spacing_mm",
        "shear_sectional_check_spacing_mm",
        "V_eq_kN",
        "shear_Vu_total_kN",
        "phi_Vu_cap",
        "phi_Vu_max_kN",
        "phiVu_max",
        "phi_vu_max",
        "shear_Vuc_kN",
        "shear_Vus_kN",
        "shear_k_v",
        "shear_theta_v_deg",
        "shear_theta_v_rad",
    }
    for key in set(RESULT_KEYS) | stale_solver_keys | stale_shear_publication_keys:
        snapshot.pop(key, None)
    for key, default in SHARED_DEFAULTS.items():
        snapshot.setdefault(key, default)
    return snapshot


def _guidance_state_snapshot(state: dict | None = None) -> dict:
    return _guidance_state_snapshot_for_app_bridge(state)


def _local_cleanup_acceptance_fingerprint(state: dict | None) -> tuple:
    snap = _guidance_state_snapshot_for_app_bridge(dict(state or {}))
    keys = (
        "b",
        "D",
        "bot1_count",
        "db_bot_1",
        "bot2_count",
        "db_bot_2",
        "bot_row_count",
        "bot_row_1_bars",
        "bot_row_1_dia",
        "bot_row_2_bars",
        "bot_row_2_dia",
        "lig_d",
        "lig_legs",
        "s_lig",
    )
    return tuple((key, str(snap.get(key))) for key in keys)


def _local_cleanup_post_apply_acceptance_matches(state: dict | None) -> bool:
    try:
        current_fp = _local_cleanup_acceptance_fingerprint(state)
        expected_fp = st.session_state.get("_design_guide_post_cleanup_acceptance_fp")
        accepted_fps = DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
        if expected_fp == current_fp or current_fp in accepted_fps:
            return True
        last_apply = dict(
            st.session_state.get(inputs_page_app_contracts.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}
        )
        return bool(
            st.session_state.get("_design_guide_post_cleanup_acceptance_enabled")
            or last_apply.get("apply_direct_resolved_candidate")
            or last_apply.get("apply_used_resolved_candidate_payload")
        )
    except Exception:
        return False


def _shared_state_snapshot_for_app_bridge() -> dict:
    return {
        key: st.session_state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }


def _starter_shear_diameter(state: dict) -> int:
    current_dia = _int_from_state(state, "lig_d", 0)
    if current_dia > 0:
        return int(current_dia)
    practical_dias = [dia for dia in REO_BAR_DIAS if dia <= 16]
    return int(practical_dias[0] if practical_dias else 10)


def _starter_shear_spacing(state: dict) -> float:
    current_spacing = _float_from_state(state, "s_lig", 0.0)
    if current_spacing > 0.0 and REO_SPACINGS:
        return float(min(REO_SPACINGS, key=lambda value: abs(float(value) - current_spacing)))
    if 200 in REO_SPACINGS:
        return 200.0
    return float(
        REO_SPACINGS[min(len(REO_SPACINGS) - 1, len(REO_SPACINGS) // 2)]
        if REO_SPACINGS
        else 200.0
    )


def _normalise_invalid_shear_state_updates(
    base_state: dict,
    updates: dict,
    *,
    source: str,
) -> dict:
    _ = source
    resolved_state = dict(base_state or {})
    normalised_updates = dict(updates or {})
    resolved_state.update(normalised_updates)
    lig_legs = _int_from_state(resolved_state, "lig_legs", 0)
    lig_d = _int_from_state(resolved_state, "lig_d", 0)
    if lig_legs <= 0:
        normalised_updates["lig_legs"] = 0
        normalised_updates["lig_d"] = 0
        canonical_no_shear_spacing = float(CANONICAL_NO_SHEAR_SLIG_MM)
        s_lig = _float_from_state(resolved_state, "s_lig", canonical_no_shear_spacing)
        if abs(float(s_lig) - canonical_no_shear_spacing) > 1e-9:
            normalised_updates["s_lig"] = canonical_no_shear_spacing
        return normalised_updates
    if lig_legs >= 2 and lig_d <= 0:
        starter_dia = int(_starter_shear_diameter(resolved_state))
        if bool(st.session_state.get("_dev_mode")):
            assert starter_dia > 0, "Invalid shear state: ligatures active but diameter is zero"
        normalised_updates["lig_d"] = starter_dia
    s_lig = _float_from_state(resolved_state, "s_lig", 0.0)
    if lig_legs >= 2 and s_lig <= 0.0:
        starter_spacing = float(_starter_shear_spacing(resolved_state))
        normalised_updates["s_lig"] = starter_spacing
    return normalised_updates


def _normalise_invalid_shear_state_in_shared(*, source: str) -> bool:
    current_state = _shared_state_snapshot_for_app_bridge()
    normalised_updates = _normalise_invalid_shear_state_updates(current_state, {}, source=source)
    if not normalised_updates:
        return False
    for shared_key, value in normalised_updates.items():
        set_shared(shared_key, value, source=source)
    return True


def _one_click_diff_accumulated_updates(base: dict, final: dict) -> dict:
    return _diff_candidate_state_updates(base, final)


def _shear_cleanup_materially_reduces_reinforcement(
    current_state: dict | None,
    candidate_state: dict | None,
) -> bool:
    if not isinstance(current_state, dict) or not isinstance(candidate_state, dict):
        return False
    cur_spacing = _float_from_state(current_state, "s_lig", 0.0)
    nxt_spacing = _float_from_state(candidate_state, "s_lig", cur_spacing)
    cur_legs = _int_from_state(current_state, "lig_legs", 0)
    nxt_legs = _int_from_state(candidate_state, "lig_legs", cur_legs)
    cur_dia = _int_from_state(current_state, "lig_d", 0)
    nxt_dia = _int_from_state(candidate_state, "lig_d", cur_dia)
    if cur_legs > 0 and nxt_legs == 0:
        return True
    if nxt_spacing > cur_spacing + 1e-9:
        return True
    if nxt_legs < cur_legs:
        return True
    if nxt_dia < cur_dia:
        return True
    return False


def _guidance_cleanup_candidate_id(family: str, updates: dict) -> str:
    try:
        fingerprint = stable_fingerprint_for_payload(
            {"family": family, "updates": dict(updates or {})}
        )
        return f"local_cleanup:{family}:{fingerprint}"
    except Exception:
        signature = ",".join(f"{key}={updates[key]}" for key in sorted(dict(updates or {})))
        return f"local_cleanup:{family}:{signature}"


def _bottom_row_count_from_state_for_app_bridge(state: dict) -> int:
    explicit = _int_from_state(state, "bot_row_count", 0)
    if explicit > 0:
        return explicit
    return 2 if _int_from_state(state, "bot2_count", 0) > 0 else 1


def _bottom_bar_count_from_state_for_app_bridge(
    state: dict,
    bottom_state: dict | None = None,
) -> int:
    resolved = bottom_state or _effective_bottom_design_state_for_app_bridge(state)
    count = int(resolved.get("nb_bot", 0) or 0)
    if count > 0:
        return count
    return _int_from_state(state, "bot1_count", 0) + _int_from_state(state, "bot2_count", 0)


def _reo_congestion_index_for_app_bridge(
    state: dict,
    bottom_state: dict | None = None,
) -> float:
    resolved = bottom_state or _effective_bottom_design_state_for_app_bridge(state)
    total_bars = _bottom_bar_count_from_state_for_app_bridge(state, resolved)
    row_count = max(_bottom_row_count_from_state_for_app_bridge(state), 1)
    bar_dia = float(resolved.get("db_bot", 0.0) or _float_from_state(state, "db_bot_1", 0.0))
    width = max(_design_width_value_for_app_bridge(state), 1.0)
    rows_penalty = max(row_count - 1, 0) * 2.5
    density_penalty = (total_bars * max(bar_dia, 1.0)) / width
    return float(total_bars + rows_penalty + density_penalty)


def _phi_mu_cap_knm_from_bending_for_app_bridge(bending: dict | None) -> float:
    if not bending:
        return 0.0
    return float(bending.get("phi_Mu_cap", 0.0) or 0.0)


def _log_phi_mu_capacity_mismatch_for_app_bridge(
    *,
    pack_phi_knm: float,
    direct_phi_knm: float,
) -> None:
    rel_tol = 0.02
    abs_tol = 0.5
    lo = max(abs(pack_phi_knm), abs(direct_phi_knm), 1.0) * rel_tol
    if abs(pack_phi_knm - direct_phi_knm) <= max(lo, abs_tol):
        return
    if bool(st.session_state.get("_dev_mode")):
        assert abs(pack_phi_knm - direct_phi_knm) <= max(lo, abs_tol), (
            "AUTO DESIGN USING STALE CAPACITY: pack phiMu vs direct bending phi_Mu_cap"
        )


@speed_profiled("candidate_preview_evaluation.evaluate_candidate_full", category="compute")
def evaluate_candidate_full_for_app_bridge(
    candidate_state: dict,
    *,
    source: str = "full_eval",
    label: str | None = None,
    action_type: str | None = None,
    updates: dict | None = None,
) -> dict | None:
    _bind_candidate_full_evaluation_dependencies(globals())
    return _evaluate_candidate_full_for_app_bridge_extracted(
        candidate_state,
        source=source,
        label=label,
        action_type=action_type,
        updates=updates,
    )


def _generate_less_shear_reo_variants_for_app_bridge(
    current_candidate: dict,
    mode_config: dict,
) -> list[dict]:
    state = dict((current_candidate or {}).get("state") or {})
    raw_result = build_design_guide_shear_low_util_raw_variant_states(
        state=state,
        shear_cleanup_possible=bool(_shear_cleanup_possible(state)),
        shear_state_eligible_for_no_links=bool(_shear_state_eligible_for_no_links(state)),
        reo_spacings=tuple(REO_SPACINGS),
        reo_bar_dias=tuple(REO_BAR_DIAS),
        canonical_no_shear_slig_mm=CANONICAL_NO_SHEAR_SLIG_MM,
        include_extended_spacing_ladder=False,
    )
    variants: dict[tuple, dict] = {}
    for candidate_state in list((raw_result or {}).get("variants") or []):
        if isinstance(candidate_state, dict):
            variants[_make_auto_design_candidate_key(candidate_state)] = dict(candidate_state)
    return list(variants.values())


def _evaluate_auto_design_candidate_for_app_bridge(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
) -> dict | None:
    candidate_state = _guidance_state_snapshot_for_app_bridge(state)
    if updates:
        candidate_state.update(updates)
    return evaluate_candidate_full_for_app_bridge(
        candidate_state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
    )


def run_inputs_layer4_pre_hydrate_shear_normalisation() -> bool:
    _inputs_hydration_trace_log("layer4_shear_normalisation", where="app_pre_hydrate")
    changed = _normalise_invalid_shear_state_in_shared(source="app:router_pre_hydrate")
    if changed:
        st.session_state["_inputs_shear_shared_normalised_this_run"] = True
    return bool(changed)


def _shared_state_snapshot_for_summary_bridge() -> dict:
    return {
        key: st.session_state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }


def _guidance_state_snapshot_for_summary_bridge(state: dict | None = None) -> dict:
    snapshot = dict(state or {})
    stale_solver_keys = {
        "pending_recommendation",
        "_solver_result",
        "_one_click_run_feedback",
        "_bend_pack",
        "_shear_pack",
        "_crack_pack",
        "_defl_pack",
        "_summary_cache_version",
        "_summary_cache_action_fp",
        "_final_shear_truth_normalized_source",
        "_final_shear_truth_normalized_latest",
    }
    stale_shear_publication_keys = {
        "shear_design_status",
        "shear_envelope_status",
        "shear_truth_status",
        "shear_truth_reason",
        "shear_truth_util_governing",
        "shear_truth_web_util_governing",
        "shear_truth_util_source",
        "shear_truth_web_util_source",
        "shear_truth_governing_check_name",
        "shear_truth_governing_reason",
        "shear_truth_governing_source",
        "shear_util_governing",
        "shear_util_min",
        "final_shear_status_source",
        "final_shear_truth_resolved",
        "final_shear_truth_failure_reason",
        "final_shear_spacing_reason",
        "final_shear_publication_path",
        "final_shear_truth_bundle_complete",
        "shear_required_spacing_mm",
        "shear_effective_spacing_mm",
        "shear_governing_spacing_source",
        "published_result_spacing_mm",
        "published_result_spacing_meaning",
        "shear_provided_input_spacing_mm",
        "shear_input_spacing_mm",
        "shear_sectional_check_spacing_mm",
        "V_eq_kN",
        "shear_Vu_total_kN",
        "phi_Vu_cap",
        "phi_Vu_max_kN",
        "phiVu_max",
        "phi_vu_max",
        "shear_Vuc_kN",
        "shear_Vus_kN",
        "shear_k_v",
        "shear_theta_v_deg",
        "shear_theta_v_rad",
    }
    for key in set(RESULT_KEYS) | stale_solver_keys | stale_shear_publication_keys:
        snapshot.pop(key, None)
    for key, default in SHARED_DEFAULTS.items():
        snapshot.setdefault(key, default)
    return snapshot


def _canonical_shape_name_and_dims_for_app_bridge(state: dict) -> tuple[str, dict]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "T-Section", {
            "bf": float(state.get("bf", state.get("b", 0.0)) or 0.0),
            "tf": float(state.get("tf", 0.0) or 0.0),
            "bw": float(state.get("bw", state.get("b", 0.0)) or 0.0),
            "D": float(state.get("D", 0.0) or 0.0),
        }
    if sec_shape == "I":
        return "I-Section", {
            "bf_top": float(state.get("bf", state.get("b", 0.0)) or 0.0),
            "tf_top": float(state.get("tf", 0.0) or 0.0),
            "bf_bot": float(state.get("bf_bot", state.get("bf", state.get("b", 0.0))) or 0.0),
            "tf_bot": float(state.get("tf_bot", state.get("tf", 0.0)) or 0.0),
            "bw": float(state.get("tw", state.get("bw", state.get("b", 0.0))) or 0.0),
            "D": float(state.get("D", 0.0) or 0.0),
        }
    return "Rectangle (b \u00d7 D)", {
        "b": float(state.get("b", 0.0) or 0.0),
        "D": float(state.get("D", 0.0) or 0.0),
    }


def _canonical_rows_from_reo_layout_for_app_bridge(reo_layout: dict, layer_name: str) -> list[dict]:
    rows: list[dict] = []
    for idx, layer_data in enumerate((reo_layout.get(layer_name) or []), start=1):
        if not isinstance(layer_data, dict):
            continue
        xs = [float(x) for x in (layer_data.get("x") or [])]
        db = float(layer_data.get("db", 0.0) or 0.0)
        yv = layer_data.get("y", 0.0)
        y = float((yv[0] if isinstance(yv, list) and yv else yv) or 0.0)
        rows.append(
            {
                "active": bool(xs and db > 0.0),
                "row_index": int(layer_data.get("row_index", idx) or idx),
                "mode": str(layer_data.get("mode", "Count") or "Count"),
                "dia": db,
                "bar_count_resolved": len(xs),
                "spacing_resolved": float(layer_data.get("spacing_actual", 0.0) or 0.0),
                "x_positions": xs,
                "y_position": y,
                "steel_area_row": float(layer_data.get("steel_area", len(xs) * math.pi * db**2 / 4.0) or 0.0),
                "fit_ok": bool(layer_data.get("fit_ok", True)),
                "warning": layer_data.get("warning"),
            },
        )
    return rows


def _invalid_canonical_design_state_pack_for_app_bridge(
    raw: dict,
    *,
    error: str,
    error_stage: str,
) -> dict:
    out = dict(raw or {})
    D = float(raw.get("D", 0.0) or 0.0)
    cover_top = float(raw.get("cover_top", 0.0) or 0.0)
    cover_bot = float(raw.get("cover_bot", 0.0) or 0.0)
    lig_d = float(raw.get("lig_d", 0.0) or 0.0)
    out.update(
        {
            "bot_rows_resolved": [],
            "top_rows_resolved": [],
            "bot_bar_coords": [],
            "top_bar_coords": [],
            "resolved_longitudinal_bars": [],
            "Ast_top_web": 0.0,
            "Ast_top_flange": 0.0,
            "Ast_bottom_web": 0.0,
            "Ast_bottom_flange": 0.0,
            "Ast_top": 0.0,
            "Ast_bot": 0.0,
            "nb_bot": 0,
            "nb_top": 0,
            "db_bot": 0.0,
            "db_top": 0.0,
            "d": effective_depth_with_links_mm(
                D_mm=D,
                cover_to_ligs_mm=cover_bot,
                lig_diameter_mm=lig_d,
                bar_diameter_mm=0.0,
            ),
            "do": float(D - cover_top),
            "canonical_pack_built": False,
            "canonical_pack_valid": False,
            "canonical_pack_source": "shared_rebuilt_failed",
            "canonical_pack_error": str(error),
            "canonical_pack_error_stage": str(error_stage),
        },
    )
    return out


def _build_canonical_design_state_pack_for_app_bridge(state: dict) -> dict:
    _bind_canonical_design_state_pack_dependencies(globals())
    return _build_canonical_design_state_pack_for_app_bridge_extracted(state)


def _canonical_convenience_fields_from_state_for_app_bridge(state: dict) -> dict:
    _bind_canonical_convenience_resync_dependencies(
        {
            **globals(),
            "_build_canonical_design_state_pack": _build_canonical_design_state_pack_for_app_bridge,
            "_guidance_state_snapshot": _guidance_state_snapshot_for_summary_bridge,
        }
    )
    return _canonical_convenience_fields_from_state_extracted(state)


def _convenience_scalar_differs_for_app_bridge(cur, new) -> bool:
    if isinstance(cur, float) or isinstance(new, float):
        try:
            return abs(float(cur) - float(new)) > 1e-6
        except (TypeError, ValueError):
            return cur != new
    return cur != new


def _apply_canonical_convenience_resync_to_shared_for_app_bridge(*, source: str) -> dict:
    _bind_canonical_convenience_resync_dependencies(
        {
            **globals(),
            "_agent_debug_log": lambda *args, **kwargs: None,
            "_build_canonical_design_state_pack": _build_canonical_design_state_pack_for_app_bridge,
            "_convenience_scalar_differs": _convenience_scalar_differs_for_app_bridge,
            "_guidance_state_snapshot": _guidance_state_snapshot_for_summary_bridge,
            "_shared_state_snapshot": _shared_state_snapshot_for_summary_bridge,
        }
    )
    return _apply_canonical_convenience_resync_to_shared_extracted(source=source)


_CANONICAL_CONVENIENCE_META_KEY = "__canonical_convenience_meta__"


def _inputs_summary_should_use_shared_only_for_app_bridge() -> tuple[bool, str | None]:
    decision = build_inputs_summary_shared_only_decision(
        applying_auto_design=bool(st.session_state.get("_applying_auto_design")),
        force_inputs_widget_reseed_once=bool(st.session_state.get("_force_inputs_widget_reseed_once")),
        pending_inputs_apply_refresh=bool(st.session_state.get("_pending_inputs_apply_refresh")),
        inputs_longitudinal_reo_force_refresh_processed_this_run=bool(
            st.session_state.get("_inputs_longitudinal_reo_force_refresh_processed_this_run")
        ),
    )
    return bool(decision.shared_only_mode), str(decision.reason)


def _apply_active_page_shear_widget_mirror_overlay_for_app_bridge(
    working: dict,
    base: dict,
    overlay_applied: dict,
) -> dict:
    slug = str(st.session_state.get("page_slug") or "")
    overlay_plan = build_inputs_shear_widget_mirror_overlay_plan(
        page_slug=slug,
        base_state=base,
        working_state=working,
        overlay_applied=overlay_applied,
        widget_state=st.session_state,
    )
    working.clear()
    working.update(dict(overlay_plan.working_state))
    overlay_applied.clear()
    overlay_applied.update(dict(overlay_plan.overlay_applied))
    dbg = dict(overlay_plan.debug_payload)
    return dbg


def _overlay_current_design_action_results_for_summary_for_app_bridge(
    working: dict,
    overlay_applied: dict,
    *,
    source_state,
) -> dict:
    source = source_state if source_state is not None else st.session_state
    design_action_overlay = build_inputs_design_action_result_overlay_snapshot(
        working_state=working,
        source_state=source,
        result_keys=_SUMMARY_DESIGN_ACTION_RESULT_KEYS,
        overlay_applied=overlay_applied,
    )
    working.clear()
    working.update(dict(design_action_overlay.working_state))
    overlay_applied.clear()
    overlay_applied.update(dict(design_action_overlay.overlay_applied))
    ux_probe_record(
        "inputs_summary_design_action_result_overlay_delegated",
        meta={
            "overlay_count": len(design_action_overlay.result_overlay),
            "module_display_hash": design_action_overlay.display_hash,
            "live_page_cutover": True,
        },
    )
    return dict(design_action_overlay.result_overlay)


def _build_legacy_longitudinal_mirrors_from_rows_for_app_bridge(state: dict) -> dict:
    return build_legacy_longitudinal_mirrors_from_rows(state)


def _state_with_resolved_design_actions_isolated_for_app_bridge(
    state: dict,
    actions: dict | None = None,
) -> dict:
    _bind_resolved_design_actions_state_dependencies(globals())
    return _state_with_resolved_design_actions_isolated_for_app_bridge_extracted(
        state,
        actions,
    )


def _build_design_actions_context_isolated_for_app_bridge(state: dict) -> dict:
    source_state = dict(state or {})
    for key, default in SHARED_DEFAULTS.items():
        source_state.setdefault(key, default)
    actions = _resolve_design_actions_from_state(source_state)
    return {
        "state": _state_with_resolved_design_actions_isolated_for_app_bridge(
            source_state,
            actions,
        ),
        "actions": dict(actions),
        "action_signature": tuple(actions.get("signature", ())),
    }


def _candidate_bottom_updates_for_app_bridge(candidate_state: dict) -> dict | None:
    db_1 = _int_from_state(candidate_state, "db_bot_1", 0)
    count_1 = _int_from_state(candidate_state, "bot1_count", 0)
    count_2 = _int_from_state(candidate_state, "bot2_count", 0)
    if db_1 <= 0 or (count_1 + count_2) <= 0:
        return None
    return {
        "db_bot_1": db_1,
        "db_bot_2": _int_from_state(candidate_state, "db_bot_2", db_1),
        "bot1_count": count_1,
        "bot2_count": count_2,
    }


def _candidate_shear_updates_for_app_bridge(candidate_state: dict) -> dict:
    return {
        "lig_d": _int_from_state(candidate_state, "lig_d", 10),
        "lig_legs": _int_from_state(candidate_state, "lig_legs", 2),
        "s_lig": _float_from_state(candidate_state, "s_lig", 200.0),
    }


def _effective_bottom_design_state_for_app_bridge(
    state: dict,
    bottom_updates: dict | None = None,
) -> dict:
    source = dict(state or {})
    D = _float_from_state(source, "D", 600.0)
    cover_bot = _float_from_state(source, "cover_bot", 40.0)
    if bottom_updates:
        db_bot = float(bottom_updates["db_bot_1"])
        nb_bot = int(bottom_updates["bot1_count"]) + int(bottom_updates["bot2_count"])
        Ast_bot = (nb_bot * math.pi * db_bot**2) / 4.0
    else:
        db_bot = _float_from_state(
            source,
            "db_bot",
            _float_from_state(source, "db_bot_1", 20.0),
        )
        nb_bot = _int_from_state(source, "nb_bot", 0)
        Ast_bot = _float_from_state(source, "Ast_bot", 0.0)

    lig_diameter = _float_from_state(source, "lig_d", 10.0)
    bar_diameter = float(db_bot or 0.0)
    d_centroid = effective_depth_with_links_mm(
        D_mm=D,
        cover_to_ligs_mm=cover_bot,
        lig_diameter_mm=lig_diameter,
        bar_diameter_mm=bar_diameter,
    )

    return {
        "Ast_bot": float(Ast_bot),
        "db_bot": float(db_bot),
        "nb_bot": int(nb_bot),
        "d_centroid": float(d_centroid),
    }


def _effective_bottom_design_state(
    state: dict,
    bottom_updates: dict | None = None,
) -> dict:
    return _effective_bottom_design_state_for_app_bridge(state, bottom_updates)


def _evaluate_bending_with_bottom_state_for_app_bridge(
    state: dict,
    bottom_updates: dict | None = None,
) -> dict | None:
    bottom_state = _effective_bottom_design_state_for_app_bridge(state, bottom_updates)
    b = _design_width_value_for_app_bridge(state)
    D = _float_from_state(state, "D", 600.0)
    if b <= 0 or D <= 0:
        return None

    eval_state = dict(state)
    eval_state["b"] = b
    eval_state["Ast_bot"] = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    eval_state["db_bot"] = float(bottom_state.get("db_bot", 0.0) or 0.0)
    eval_state["nb_bot"] = float(bottom_state.get("nb_bot", 0.0) or 0.0)
    eval_state["d"] = float(bottom_state.get("d_centroid", 0.0) or 0.0)

    cap = compute_bending_capacity_from_state(eval_state)
    results = dict(cap.get("legacy") or {})
    results["Ast_bot"] = bottom_state["Ast_bot"]
    results["d_centroid"] = bottom_state["d_centroid"]
    results["db_bot"] = bottom_state["db_bot"]
    results["nb_bot"] = bottom_state["nb_bot"]
    return results


def _evaluate_bending_with_bottom_state(
    state: dict,
    bottom_updates: dict | None = None,
) -> dict | None:
    return _evaluate_bending_with_bottom_state_for_app_bridge(state, bottom_updates)


def _effective_bottom_spacing_for_app_bridge(
    state: dict,
    bottom_updates: dict | None = None,
) -> float:
    from section_layout import compute_bar_layout_pure

    if bottom_updates:
        count_1 = int(bottom_updates.get("bot1_count", 0) or 0)
        dia = float(bottom_updates.get("db_bot_1", 0.0) or 0.0)
    else:
        count_1 = _int_from_state(state, "bot1_count", _int_from_state(state, "nb_bot", 0))
        dia = _float_from_state(
            state,
            "db_bot_1",
            _float_from_state(state, "db_bot", 0.0),
        )
    if count_1 <= 1 or dia <= 0.0:
        return _float_from_state(state, "s_bot", 0.0)
    layout = compute_bar_layout_pure(
        b=_design_width_value_for_app_bridge(state),
        cover_side=_float_from_state(state, "cover_side", 40.0),
        nb_or_s=float(count_1),
        db=float(dia),
        s_min=max(float(dia), 25.0),
        rowgap=_float_from_state(state, "rowgap_bot", 60.0),
    )
    return float(layout.get("s_actual", _float_from_state(state, "s_bot", 0.0)) or 0.0)


def _compute_sls_outer_steel_stress_with_state_for_app_bridge(
    state: dict,
    *,
    bottom_updates: dict | None = None,
) -> float | None:
    bottom_state = _effective_bottom_design_state_for_app_bridge(state, bottom_updates)
    b = _design_width_value_for_app_bridge(state)
    D = _float_from_state(state, "D", 600.0)
    d = float(bottom_state.get("d_centroid", 0.0) or 0.0)
    Ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Es = _float_from_state(state, "Es", 200000.0)
    Ms = _float_from_state(state, "sls_Mstar", _float_from_state(state, "uls_Mstar", 0.0))
    if not (b > 0.0 and D > 0.0 and d > 0.0 and Ast > 0.0 and Ec > 0.0 and Es > 0.0):
        return None
    n_as = (Es / Ec) * Ast
    if n_as <= 0.0:
        return None
    a_coeff = b / 2.0
    b_coeff = n_as
    c_coeff = -n_as * d
    discriminant = b_coeff**2 - 4.0 * a_coeff * c_coeff
    if discriminant >= 0.0 and a_coeff > 0.0:
        dn_sls = (-b_coeff + math.sqrt(discriminant)) / (2.0 * a_coeff)
        dn_sls = max(1.0, min(dn_sls, D))
    else:
        dn_sls = d / 2.0
    i_cr = (b * dn_sls**3 / 3.0) + n_as * (d - dn_sls) ** 2
    if i_cr <= 0.0:
        return None
    kappa = (Ms * 1e6) / (Ec * i_cr)
    return float(Es * kappa * (d - dn_sls))


def _evaluate_crack_with_state_for_app_bridge(
    state: dict,
    *,
    bottom_updates: dict | None = None,
) -> dict | None:
    _bind_crack_evaluation_dependencies(globals())
    return _evaluate_crack_with_state_for_app_bridge_extracted(
        state,
        bottom_updates=bottom_updates,
    )


def _status_from_candidate_util_for_app_bridge(util: float | None) -> str:
    if util is None or (isinstance(util, float) and math.isnan(util)):
        return "\u2014"
    if util <= 1.0:
        return "NEAR LIMIT" if util >= 0.95 else "PASS"
    return "FAIL"


def _evaluate_deflection_with_state_for_app_bridge(
    state: dict,
    *,
    bottom_updates: dict | None = None,
) -> dict | None:
    _bind_deflection_evaluation_dependencies(globals())
    return _evaluate_deflection_with_state_for_app_bridge_extracted(
        state,
        bottom_updates=bottom_updates,
    )


def _candidate_state_with_effective_bottom_for_overview_for_app_bridge(
    candidate_state: dict,
    bottom_updates: dict | None,
) -> dict:
    merged = dict(candidate_state or {})
    bottom_state = _effective_bottom_design_state_for_app_bridge(candidate_state, bottom_updates)
    d_centroid = float(bottom_state.get("d_centroid", 0.0) or 0.0)
    if d_centroid > 0.0:
        merged["d"] = d_centroid
    nb_bot = int(bottom_state.get("nb_bot", 0) or 0)
    db_bot = float(bottom_state.get("db_bot", 0.0) or 0.0)
    if nb_bot > 0 and db_bot > 0.0:
        merged["Ast_bot"] = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
        merged["db_bot"] = db_bot
        merged["nb_bot"] = nb_bot
    return merged


def _recompute_summary_local_derived_fields_for_app_bridge(state: dict) -> dict:
    working = dict(state or {})
    working.update(_build_legacy_longitudinal_mirrors_from_rows_for_app_bridge(working))
    ctx = _build_design_actions_context_isolated_for_app_bridge(working)
    resolved = dict(ctx.get("state") or _guidance_state_snapshot_for_summary_bridge(working))
    resolved.update(_build_legacy_longitudinal_mirrors_from_rows_for_app_bridge(resolved))
    bottom_updates = _candidate_bottom_updates_for_app_bridge(resolved)
    resolved = _candidate_state_with_effective_bottom_for_overview_for_app_bridge(
        resolved,
        bottom_updates,
    )
    resolved.update(_build_legacy_longitudinal_mirrors_from_rows_for_app_bridge(resolved))
    return resolved


def _overlay_current_normalized_shear_truth_for_app_bridge(state: dict | None) -> dict:
    base_state = dict(state or {})
    session_overlay = {}
    merged = dict(base_state)
    for key in _CURRENT_SHEAR_TRUTH_SESSION_KEYS:
        if key in st.session_state:
            session_overlay[key] = st.session_state.get(key)
            merged[key] = session_overlay[key]
    normalized_overlay = normalize_final_published_shear_truth(merged)
    snapshot = build_inputs_normalized_shear_truth_overlay_snapshot(
        base_state=base_state,
        session_shear_truth_values=session_overlay,
        normalized_shear_truth_values=normalized_overlay,
    )
    return dict(snapshot.merged_state)


def _resolved_inputs_summary_state() -> tuple[dict, dict]:
    _bind_summary_state_resolver_dependencies(globals())
    return _resolved_inputs_summary_state_extracted()


def _overall_status_from_rows(rows):
    if not rows:
        return "â€”", "rgba(31, 119, 180, 0.08)"
    filtered = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("is_informational"):
            continue
        status = str(row.get("status", "")).upper()
        if status == "INFO":
            continue
        filtered.append(row)
    if not filtered:
        return "â€”", "rgba(31, 119, 180, 0.08)"
    statuses = [str(row.get("status", "")).upper() for row in filtered]
    if any("FAIL" in status or status == "NG" for status in statuses):
        return "FAIL", "rgba(255,0,0,0.12)"
    if any("WARN" in status or "NEAR LIMIT" in status or status == "CHECK" for status in statuses):
        return "NEAR LIMIT", "rgba(255,193,7,0.15)"
    if any("PASS" in status or status == "OK" for status in statuses):
        return "PASS", "rgba(0,128,0,0.12)"
    return "â€”", "rgba(31, 119, 180, 0.08)"


def _stage3_remaining_issue_class_from_overview_state(
    state: dict | None,
    overview: dict | None,
) -> str | None:
    if not isinstance(overview, dict):
        return None
    source = dict(state or {})
    shear_status = str(((overview.get("statuses") or {}).get("shear") or "")).strip().upper()
    design_status = str(source.get("shear_design_status") or "").strip().upper()
    truth_resolved = source.get("final_shear_truth_resolved")
    failure_reason = str(source.get("final_shear_truth_failure_reason") or "").strip()
    truth_status = str(source.get("shear_truth_status") or "").strip()
    if design_status == "INVALID" and shear_status == "PASS":
        return "truth"
    if truth_resolved is False and bool(failure_reason or truth_status) and shear_status == "PASS":
        return "truth"
    return None


def _build_design_actions_context_for_app_bridge(state: dict) -> dict:
    source_state = _guidance_state_snapshot_for_summary_bridge(state)
    actions = _resolve_design_actions_from_state(source_state)
    return {
        "state": _state_with_resolved_design_actions_for_app_bridge(source_state, actions),
        "actions": dict(actions),
        "action_signature": tuple(actions.get("signature", ())),
    }


def _state_with_resolved_design_actions_for_app_bridge(
    state: dict,
    actions: dict | None = None,
) -> dict:
    _bind_resolved_design_actions_state_dependencies(globals())
    return _state_with_resolved_design_actions_for_app_bridge_extracted(state, actions)


def _build_bending_check_rows_from_state_for_app_bridge(state: dict) -> dict:
    return build_bending_check_rows_from_state(state)


def _build_shear_check_rows_from_state_for_app_bridge(state: dict) -> dict:
    return build_shear_check_rows_from_state(state)


def _build_crack_pack_from_state_for_app_bridge(state: dict) -> dict:
    crack = _evaluate_crack_with_state_for_app_bridge(
        state,
        bottom_updates=_candidate_bottom_updates_for_app_bridge(state),
    )
    if crack is None:
        return {"summary_util": None, "rows": []}
    util = float(crack.get("util", 0.0) or 0.0)
    sigma_sr = float(crack.get("sigma_sr", 0.0) or 0.0)
    sigma_allow = float(crack.get("sigma_allow_table", 0.0) or 0.0)
    w_calc = float(crack.get("w_calc", 0.0) or 0.0)
    w_lim = _float_from_state(state, "wmax_char_limit", 0.3)
    return {
        "summary_util": util,
        "rows": [
            {
                "uid": "crk_step_4",
                "title": "Governing outcome",
                "value": "Both checks pass" if util <= 1.0 else "One or more checks fail",
                "limit": "Table stress + direct width",
                "util": "\u2014",
                "status": "PASS" if util <= 1.0 else "FAIL",
                "route_page": "crack",
            },
            {
                "uid": "crk_step_2",
                "title": "Table-based crack control check",
                "value": f"\u03c3_sr = {sigma_sr:.1f} MPa",
                "limit": f"\u03c3_allow = {sigma_allow:.1f} MPa" if sigma_allow > 0.0 else "\u2014",
                "util": f"{(sigma_sr / sigma_allow):.2f}" if sigma_allow > 0.0 else "\u2014",
                "status": _status_from_candidate_util_for_app_bridge(
                    (sigma_sr / sigma_allow) if sigma_allow > 0.0 else None
                ),
                "route_page": "crack",
            },
            {
                "uid": "crk_step_3",
                "title": "Direct crack width check",
                "value": f"w = {w_calc:.3f} mm",
                "limit": f"w'max = {w_lim:.3f} mm" if w_lim > 0.0 else "\u2014",
                "util": f"{(w_calc / w_lim):.2f}" if w_lim > 0.0 else "\u2014",
                "status": _status_from_candidate_util_for_app_bridge(
                    (w_calc / w_lim) if w_lim > 0.0 else None
                ),
                "route_page": "crack",
            },
        ],
    }


def _build_deflection_pack_from_state_for_app_bridge(state: dict) -> dict:
    deflection = _evaluate_deflection_with_state_for_app_bridge(
        state,
        bottom_updates=_candidate_bottom_updates_for_app_bridge(state),
    )
    if deflection is None:
        return {
            "summary_delta_total_mm": None,
            "summary_defl_limit_mm": None,
            "summary_util_total": None,
            "rows": [],
        }
    return dict(deflection.get("pack") or {})


def _stage3_final_published_shear_truth_bundle_for_app_bridge(state: dict | None) -> dict:
    keys = (
        "shear_truth_status",
        "shear_truth_reason",
        "shear_truth_governing_check_name",
        "shear_truth_governing_reason",
        "shear_truth_governing_source",
        "final_shear_status_source",
        "final_shear_truth_resolved",
        "final_shear_truth_failure_reason",
        "final_shear_truth_bundle_complete",
        "shear_provided_input_spacing_mm",
        "shear_input_spacing_mm",
        "shear_sectional_check_spacing_mm",
        "shear_effective_spacing_mm",
        "shear_required_spacing_mm",
        "shear_governing_spacing_source",
        "published_result_spacing_mm",
        "published_result_spacing_meaning",
    )
    source = dict(state or {})
    out = {key: source.get(key) for key in keys}
    out["design_guide_shear_truth_source"] = "final_published_shear_truth"
    out["final_shear_truth_normalized_source"] = source.get("_final_shear_truth_normalized_source")
    out["final_shear_truth_normalized_latest"] = dict(
        source.get("_final_shear_truth_normalized_latest") or {}
    )
    return out


@speed_profiled("inputs_page.summary_overview_build", category="compute")
def _collect_design_overview(state: dict, context: dict | None = None) -> dict:
    _bind_design_overview_collector_dependencies(globals())
    return _collect_design_overview_extracted(state, context=context)


def _compute_design_guidance_items(
    state: dict,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
    request_kind: str = "design_guide",
) -> dict:
    serviceability_preflight = _serviceability_governs_preflight_payload(state)
    if serviceability_preflight is not None:
        return serviceability_preflight
    out = compute_design_guidance_items(
        _BRIDGE_PROVIDER,
        st,
        os,
        sys,
        state,
        guidance_debug_verbose=guidance_debug_verbose,
        debug_enabled=debug_enabled,
        request_kind=request_kind,
    )
    return _replace_unsafe_combined_active_fail_single_family_action(
        out,
        state=state,
    )


def _serviceability_governs_preflight_payload(state: dict) -> dict | None:
    _bind_serviceability_preflight_dependencies(globals())
    return _serviceability_governs_preflight_payload_extracted(state)


def _replace_unsafe_combined_active_fail_single_family_action(payload: dict, *, state: dict) -> dict:
    _bind_active_fail_single_family_guard_dependencies(globals())
    return _replace_unsafe_combined_active_fail_single_family_action_extracted(payload, state=state)


def _shear_low_util_active_links_exact_blocker(
    state: dict | None,
    overview: dict | None,
    *,
    threshold: float = inputs_page_app_contracts.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
) -> dict | None:
    _bind_shear_low_util_active_links_blocker_dependencies(globals())
    return _shear_low_util_active_links_exact_blocker_extracted(
        state,
        overview,
        threshold=threshold,
    )

def _tracer_one_click_action_source_summary(trigger_fingerprint: tuple | None) -> dict:
    out: dict = {
        "trigger_fingerprint": None if trigger_fingerprint is None else str(trigger_fingerprint),
    }
    try:
        out["force_auto_redesign"] = bool(st.session_state.get("_force_auto_redesign", False))
        out["auto_design_auto_invoke"] = bool(st.session_state.get(AUTO_DESIGN_AUTO_INVOKE_KEY, False))
        out["auto_design_request_source"] = st.session_state.get("auto_design_request_source") or st.session_state.get(
            AUTO_DESIGN_REQUEST_SOURCE_KEY
        )
        out["auto_design_requested_at_ts"] = st.session_state.get(AUTO_DESIGN_REQUEST_TS_KEY)
        out["auto_design_invoke_pending"] = bool(st.session_state.get("auto_design_invoke_pending", False))
    except Exception:
        out["force_auto_redesign"] = None
        out["auto_design_auto_invoke"] = None
        out["auto_design_request_source"] = None
        out["auto_design_requested_at_ts"] = None
        out["auto_design_invoke_pending"] = None
    return out


def _auto_design_invoke_debug_snapshot() -> dict:
    try:
        return {
            "force_auto_redesign": bool(st.session_state.get("_force_auto_redesign", False)),
            "auto_design_auto_invoke": bool(st.session_state.get(AUTO_DESIGN_AUTO_INVOKE_KEY, False)),
            "auto_design_request_source": st.session_state.get("auto_design_request_source")
            or st.session_state.get(AUTO_DESIGN_REQUEST_SOURCE_KEY),
            "auto_design_requested_at_ts": st.session_state.get(AUTO_DESIGN_REQUEST_TS_KEY),
            "auto_design_invoke_pending": bool(st.session_state.get("auto_design_invoke_pending", False)),
        }
    except Exception:
        return {
            "force_auto_redesign": None,
            "auto_design_auto_invoke": None,
            "auto_design_request_source": None,
            "auto_design_requested_at_ts": None,
            "auto_design_invoke_pending": None,
        }


def _consume_auto_design_invoke_after_solver_entry_confirmed() -> None:
    had_invoke = bool(st.session_state.get(AUTO_DESIGN_AUTO_INVOKE_KEY, False))
    if had_invoke:
        st.session_state.pop(AUTO_DESIGN_AUTO_INVOKE_KEY, None)
        st.session_state.pop(AUTO_DESIGN_REQUEST_TS_KEY, None)
        st.session_state.pop(AUTO_DESIGN_REQUEST_SOURCE_KEY, None)
        st.session_state.pop("auto_design_request_source", None)
    try:
        st.session_state["auto_design_invoke_consumed"] = bool(had_invoke)
        st.session_state["auto_design_invoke_pending"] = False
        st.session_state.pop("_auto_design_idle_reason", None)
        st.session_state.pop("auto_design_idle_reason", None)
    except Exception:
        pass


def _should_run_auto_design() -> bool:
    return bool(
        st.session_state.get("_force_auto_redesign", False)
        or st.session_state.get(AUTO_DESIGN_AUTO_INVOKE_KEY, False)
    )


def _build_design_actions_context(state: dict) -> dict:
    return _build_design_actions_context_for_app_bridge(state)


def _build_canonical_design_state_pack(state: dict) -> dict:
    return _build_canonical_design_state_pack_for_app_bridge(state)


def _overlay_current_normalized_shear_truth(state: dict | None) -> dict:
    return _overlay_current_normalized_shear_truth_for_app_bridge(state)


def evaluate_candidate_full(*args, **kwargs):
    return evaluate_candidate_full_for_app_bridge(*args, **kwargs)


def _evaluate_auto_design_candidate(*args, **kwargs):
    return _evaluate_auto_design_candidate_for_app_bridge(*args, **kwargs)


__all__: list[str] = []

# Mechanical extraction: small old-only provider helpers.
def _design_guide_debug_has_coherent_overview(d: dict | None) -> bool:
    if not isinstance(d, dict):
        return False
    ov = d.get("overview")
    return isinstance(ov, dict) and len(ov) > 0 and (
        "worst_util" in ov or "all_key_pass" in ov
    )


def _design_guide_debug_has_efficiency_state(d: dict | None) -> bool:
    if not isinstance(d, dict):
        return False
    es = d.get("efficiency_tightening_state")
    return isinstance(es, dict) and "classification" in es


def _design_guide_cached_debug_bundle_complete(d: dict | None) -> bool:
    if not isinstance(d, dict) or not d:
        return False
    if not isinstance(d.get("guidance_resolved_state"), dict):
        return False
    return _design_guide_debug_has_coherent_overview(d) and _design_guide_debug_has_efficiency_state(d)


def _reset_design_guide_reco_trace() -> None:
    st.session_state[DESIGN_GUIDE_RECO_TRACE_KEY] = []


def _append_design_guide_reco_trace(entry: dict) -> None:
    global _ACTIVE_GUIDANCE_RECO_TRACE
    if _ACTIVE_GUIDANCE_RECO_TRACE is not None:
        _ACTIVE_GUIDANCE_RECO_TRACE.append(dict(entry))


def _geometry_lock_enabled(source: dict | None = None) -> bool:
    resolved = source if isinstance(source, dict) else st.session_state
    return bool((resolved or {}).get("optimisation_lock_geometry", False))


def _resolved_efficiency_target_band(
    mode_config: dict | None = None,
    *,
    goal: str | None = None,
) -> tuple[float, float, bool]:
    resolved_goal = goal or _design_optimisation_goal()
    cfg = dict(mode_config or {})
    has_explicit_band = "target_util_min" in cfg and "target_util_max" in cfg
    if has_explicit_band:
        lo = float(cfg.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
        hi = float(cfg.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
        default_used = bool(
            resolved_goal == "balanced"
            and abs(lo - EFFICIENCY_TARGET_UTIL_MIN) <= 1e-9
            and abs(hi - EFFICIENCY_TARGET_UTIL_MAX) <= 1e-9
        )
        return lo, hi, default_used
    if resolved_goal == "balanced":
        return EFFICIENCY_TARGET_UTIL_MIN, EFFICIENCY_TARGET_UTIL_MAX, True
    fallback_cfg = _design_mode_config(resolved_goal)
    lo = float(fallback_cfg.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    hi = float(fallback_cfg.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    return lo, hi, False


def _sync_auto_design_mode_tracking(state: dict | None = None) -> None:
    current_mode = _design_optimisation_goal(state)
    previous_mode = st.session_state.get("_prev_auto_design_mode")
    if previous_mode is None:
        st.session_state["_prev_auto_design_mode"] = current_mode
        return
    if current_mode != previous_mode:
        st.session_state["_force_auto_redesign"] = True
        st.session_state["_prev_auto_design_mode"] = current_mode
        st.session_state["_auto_design_reason"] = "mode_changed"


def _bottom_arrangement_to_shared_updates(arrangement: dict) -> dict:
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    dia_1 = int(arrangement.get("db_bot_1", 0) or 0)
    dia_2 = int(arrangement.get("db_bot_2", dia_1) or dia_1)
    row_count = 2 if count_2 > 0 else 1
    return {
        "bot1_layout_mode": "Count",
        "bot1_count": count_1,
        "db_bot_1": dia_1,
        "bot2_layout_mode": "Count",
        "bot2_count": count_2,
        "db_bot_2": dia_2,
        "bot_row_count": row_count,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": count_1,
        "bot_row_1_spacing": 0.0,
        "bot_row_1_dia": dia_1,
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": count_2,
        "bot_row_2_spacing": 0.0,
        "bot_row_2_dia": dia_2,
    }


def _guidance_card_why_body(item: dict) -> str:
    w = item.get("guidance_why")
    if isinstance(w, str) and w.strip():
        t = w.strip()
        if t.lower().startswith("why:"):
            return t[4:].strip() or t
        return t
    r = str(item.get("reasoning") or "").strip()
    if not r:
        return ""
    if r.lower().startswith("why:"):
        return r[4:].strip() or r
    return r


def _design_guide_text_html(text: object) -> str:
    """Escape display copy while preserving intentional line breaks and bullets."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    html_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            html_lines.append("")
        elif stripped.startswith("- "):
            html_lines.append("&bull; " + html.escape(stripped[2:]))
        else:
            html_lines.append(html.escape(line))
    return "<br>".join(html_lines)


def _design_guide_status_from_overview(overview: dict | None) -> str | None:
    ov = overview if isinstance(overview, dict) else {}
    if bool(ov.get("any_fail")):
        return "FAIL"
    if bool(ov.get("any_warn")):
        return "NEAR LIMIT"
    if bool(ov.get("all_key_pass")):
        return "PASS"
    statuses = dict(ov.get("statuses") or {})
    values = [str(v or "").strip().upper() for v in statuses.values() if str(v or "").strip()]
    if any(v == "FAIL" for v in values):
        return "FAIL"
    if any(v == "NEAR LIMIT" for v in values):
        return "NEAR LIMIT"
    if values and all(v == "PASS" for v in values):
        return "PASS"
    return None


def _design_guide_button_contract_enabled(contract: dict | None) -> bool:
    c = contract if isinstance(contract, dict) else {}
    return bool(
        c.get("actionable")
        and dict(c.get("updates") or {})
        and bool(c.get("preview_pass"))
        and c.get("blocking_reason") is None
    )


def _design_guide_guidance_intent_debug_rows(items: list[dict] | None) -> list[dict]:
    rows: list[dict] = []
    for idx, item in enumerate(list(items or [])):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "index": int(idx),
                "title": str(item.get("title_main") or "").strip() or None,
                "check_key": str(item.get("check_key") or "").strip() or None,
                "action_type": str(item.get("action_type") or "").strip() or None,
                "guidance_intent": str(item.get("guidance_intent") or "").strip() or None,
                "button_contract": dict(item.get("button_contract") or {}),
                "displayed_util": item.get("displayed_util"),
                "displayed_status": item.get("displayed_status"),
                "display_truth_source": item.get("display_truth_source"),
                "target_low": item.get("target_low"),
                "target_high": item.get("target_high"),
                "displayed_within_target_band": bool(item.get("displayed_within_target_band")),
                "source_summary_util": item.get("source_summary_util"),
                "source_candidate_util": item.get("source_candidate_util"),
                "source_post_commit_util": item.get("source_post_commit_util"),
            }
        )
    return rows


def _design_guide_candidate_family(item: dict | None) -> str:
    if not isinstance(item, dict):
        return "none"
    at = str(item.get("action_type") or "")
    if at == "apply_compound_guidance":
        return "compound"
    if at in ("apply_geometry_recommendation", "increase_depth", "increase_width", "tighten_geometry"):
        return "geometry"
    if at in ("apply_bottom_recommendation", "reduce_bottom_reinforcement", "reduce_bar_spacing"):
        return "bottom_reo"
    if at in ("apply_shear_recommendation", "increase_link_spacing", "reduce_number_of_legs", "reduce_link_spacing"):
        return "shear"
    if at == "apply_mode_recommendation":
        return "mode_guidance"
    ck = str(item.get("check_key") or "")
    return ck if ck else "general"


def _overview_required_checks_acceptable(overview: dict | None) -> bool:
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


def _guidance_governing_primary_action(overview: dict | None) -> tuple[str, dict[str, float | None]]:
    utils = ((overview or {}).get("utils") or {})
    primary_utils: dict[str, float | None] = {}
    ranked: list[tuple[str, float]] = []
    for key in ("bending", "shear"):
        raw = utils.get(key)
        try:
            resolved = float(raw)
        except Exception:
            primary_utils[key] = None
            continue
        if math.isnan(resolved):
            primary_utils[key] = None
            continue
        primary_utils[key] = resolved
        ranked.append((key, resolved))
    if ranked:
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[0][0], primary_utils
    return "general", primary_utils


def _governing_focus_from_overview(overview: dict | None) -> str:
    governing_action, _ = _guidance_governing_primary_action(overview)
    if governing_action != "general":
        return governing_action
    utils = ((overview or {}).get("utils") or {})
    ranked = [("crack", utils.get("crack")), ("deflection", utils.get("deflection"))]
    best_key = "general"
    best_util = -1.0
    for key, value in ranked:
        try:
            resolved = float(value)
        except Exception:
            continue
        if math.isnan(resolved):
            continue
        if resolved > best_util:
            best_key = key
            best_util = resolved
    return best_key


def _design_width_value(state: dict) -> float:
    _, _, width = _resolve_geometry_width_context(state)
    return float(width)


def _debug_resolved_guidance_actions(state: dict | None = None) -> dict:
    source_state = _guidance_state_snapshot(state)
    actions = _resolve_design_actions_from_state(source_state)
    return {
        "resolved_source": actions.get("source"),
        "Mu": actions.get("Mu"),
        "Vu": actions.get("Vu"),
        "Nu": actions.get("Nu"),
        "SLS_M": actions.get("SLS_M"),
        "SLS_V": actions.get("SLS_V"),
        "actions_source": actions.get("actions_source"),
        "actions_mode": actions.get("actions_mode"),
        "signature": tuple(actions.get("signature", ())),
    }


def _practical_bottom_reo_label(count_1: int, count_2: int, dia: int) -> str:
    if count_2 > 0:
        return f"{count_1}N{dia} + {count_2}N{dia}"
    return f"{count_1}N{dia}"


def _candidate_target_domains_for_band(candidate: dict) -> list[str]:
    if not isinstance(candidate, dict):
        return []
    raw = candidate.get("target_domains_for_band")
    if not isinstance(raw, list) or not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        d = str(item or "").strip().lower()
        if d in ("flexure", "ductility", "bottom", "bottom_reo"):
            d = "bending"
        if d not in ("bending", "shear"):
            continue
        if d not in seen:
            out.append(d)
            seen.add(d)
    return out


def _rescue_mode_default_debug() -> dict:
    return {
        "rescue_mode_entered": False,
        "rescue_mode_entry_reason": None,
        "rescue_mode_family": None,
        "rescue_mode_tier_requested": None,
        "rescue_mode_tier_used": None,
        "rescue_mode_seed_key": None,
        "rescue_mode_seed_legal": None,
        "rescue_mode_seed_illegal_reason": None,
        "rescue_mode_fallback_count": 0,
        "rescue_mode_ineffective_seeds": [],
        "rescue_mode_effective_seed_found": False,
        "rescue_mode_exit_reason": None,
    }


def _rescue_mode_validate_seed(base_state: dict, seed_updates: dict) -> tuple[bool, str | None, dict]:
    trial_state = _guidance_state_snapshot(dict(base_state or {}))
    trial_state.update(dict(seed_updates or {}))
    trial_pack = _build_canonical_design_state_pack(_overlay_current_normalized_shear_truth(trial_state))
    coherence = _design_state_coherence_check(trial_pack)
    if not _canonical_pack_is_valid(trial_pack):
        return False, str(trial_pack.get("canonical_pack_error") or "canonical_pack_invalid"), trial_state
    if bool(coherence.get("coherence_should_block")):
        issues = list(coherence.get("coherence_blocking_issues") or [])
        return False, str(issues[0] if issues else "state_incoherent_after_rebuild"), trial_state
    try:
        ev = evaluate_candidate_full(
            trial_pack,
            source="rescue_mode_seed_validation",
            label="Rescue seed validation",
            action_type="rescue_seed_validation",
            updates={},
        )
    except Exception:
        ev = None
    if not isinstance(ev, dict):
        return False, "seed_evaluation_failed", trial_state
    return True, None, trial_state


def _rescue_mode_eval_for_result(result: dict | None) -> dict | None:
    preview = dict((result or {}).get("final_state_preview") or {})
    if not preview:
        return None
    try:
        return evaluate_candidate_full(
            _build_canonical_design_state_pack(preview),
            source="rescue_mode_result_eval",
            label="Rescue result",
            action_type="rescue_mode",
            updates={},
        )
    except Exception:
        return None


def _one_click_strict_target_band_ok(overview: dict | None, mode_config: dict) -> bool:
    if not isinstance(overview, dict):
        return False
    try:
        lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
        hi = float(mode_config.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    except Exception:
        lo = float(EFFICIENCY_TARGET_UTIL_MIN)
        hi = float(EFFICIENCY_TARGET_UTIL_MAX)
    try:
        worst = float(
            overview.get("governing_util", overview.get("worst_util", 0.0)) or 0.0,
        )
    except (TypeError, ValueError):
        return False
    statuses = dict(overview.get("statuses") or {})
    any_fail = any(
        value == BEAM_STATUS_FAIL or str(value or "").strip().upper() == "FAIL"
        for value in statuses.values()
    )
    return bool(not any_fail and lo <= worst <= hi)


def _candidate_materially_improves(current_candidate: dict, trial_candidate: dict) -> bool:
    if not trial_candidate:
        return False
    current_worst = float(current_candidate.get("worst_util", float("inf")) or float("inf"))
    trial_worst = float(trial_candidate.get("worst_util", float("inf")) or float("inf"))
    if bool(trial_candidate.get("is_compliant")) and not bool(current_candidate.get("is_compliant")):
        return True
    return trial_worst < current_worst - 1e-6


def _first_actionable_guidance_item(guidance_items: list[dict] | None) -> dict | None:
    """First item with a non-empty action_type (same selection rule as pending recommendation sync)."""
    for item in guidance_items or []:
        if not isinstance(item, dict) or not str(item.get("action_type") or "").strip():
            continue
        contract = item.get("button_contract")
        if isinstance(contract, dict) and not _design_guide_button_contract_enabled(contract):
            continue
        if isinstance(item, dict):
            return item
    return None


def _design_guide_terminal_state_from_render_artifacts(
    guidance_items: list[dict],
    guidance_debug: dict | None,
) -> str | None:
    dbg = dict(guidance_debug or {})
    eff = dict(dbg.get("efficiency_tightening_state") or {})
    eff_cls = str(eff.get("classification") or "").strip()
    actionable_item = _first_actionable_guidance_item(guidance_items)

    if eff_cls == "optimal" and actionable_item is None:
        return "optimal"
    if eff_cls == "very_low_demand" and actionable_item is None:
        return "very_low_demand"

    top = guidance_items[0] if guidance_items else {}
    top_term = str((top or {}).get("design_guide_terminal_state") or "").strip()
    if top_term in {"optimal", "very_low_demand"}:
        return top_term

    gb = str(dbg.get("guidance_branch") or "").strip()
    if gb in {"optimal", "very_low_demand"}:
        return gb

    return None


def _guidance_update_map(item: dict | None) -> dict:
    if not isinstance(item, dict):
        return {}
    payload = dict(item.get("action_payload") or {})
    return dict(
        payload.get("updates")
        or payload.get("resolved_candidate_updates")
        or {}
    )


def _shear_change_is_relevant(overview: dict, actions: dict) -> bool:
    Vu = float(actions.get("Vu", 0.0) or 0.0)
    shear_util = float((((overview or {}).get("utils") or {}).get("shear", 0.0)) or 0.0)
    if Vu <= 0.0:
        return False
    if shear_util < 0.20:
        return False
    return True


def _is_in_target_zone_with_eps(overview: dict, mode_config: dict, *, eps: float = TARGET_BAND_EPS) -> bool:
    worst_util = float((overview or {}).get("worst_util", 0.0) or 0.0)
    lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    hi = float(mode_config.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    return lo <= worst_util <= (hi + float(eps))


def _efficiency_state_has_valid_candidate(efficiency_state: dict) -> bool:
    if not isinstance(efficiency_state, dict):
        return False
    return any(
        efficiency_state.get(key) is not None
        for key in ("mode_tightening", "bottom_tightening", "shear_tightening", "geometry_tightening")
    )


def _geometry_trial_axis_for_bottom_rec(candidate: dict, state: dict) -> str | None:
    if not candidate.get("recommendation_geometry_trial"):
        return None
    u = candidate.get("updates") or {}
    if "D" in u:
        return "depth"
    wkey, _, _ = _resolve_geometry_width_context(state)
    if wkey in u:
        return "width"
    return None


def _annotate_bottom_reo_candidate_deltas(candidate: dict, seed_candidate: dict, state: dict) -> None:
    ss = dict(seed_candidate.get("state") or state)
    bs = dict(candidate.get("state") or {})
    seed_d = float(seed_candidate.get("depth", _float_from_state(ss, "D", 0.0)) or _float_from_state(ss, "D", 0.0))
    cand_d = float(candidate.get("depth", _float_from_state(bs, "D", 0.0)) or _float_from_state(bs, "D", 0.0))
    seed_b = float(seed_candidate.get("width", _design_width_value(ss)) or _design_width_value(ss))
    cand_b = float(candidate.get("width", _design_width_value(bs)) or _design_width_value(bs))
    seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    cand_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
    candidate["delta_D_mm"] = round(cand_d - seed_d, 3)
    candidate["delta_b_mm"] = round(cand_b - seed_b, 3)
    candidate["delta_Ast_bot"] = round(cand_ast - seed_ast, 3)


def _candidate_leg_counts(cur_legs: int, *, conservative: bool) -> list[int]:
    cur = max(int(cur_legs or 2), 2)
    if conservative:
        return [n for n in range(cur - 1, 1, -1)]
    return [n for n in range(cur + 1, 9)]


def _shear_util_from_overview_candidate(candidate: dict | None) -> float | None:
    if not candidate:
        return None
    try:
        u = ((candidate.get("overview") or {}).get("utils") or {}).get("shear")
        if u is None:
            return None
        f = float(u)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _one_click_has_unresolved_spacing_envelope_fail(eval_obj: dict | None) -> bool:
    """True only for an explicit canonical spacing-envelope fail in the solved eval."""
    if not isinstance(eval_obj, dict):
        return False
    overview = dict(eval_obj.get("overview") or {})
    shear_pack = (((overview.get("packs") or {}).get("shear")) or {})
    source = str(
        shear_pack.get("summary_governing_source")
        or shear_pack.get("summary_governing_check_source")
        or ""
    ).strip()
    status = str(
        shear_pack.get("summary_governing_status")
        or shear_pack.get("summary_status")
        or ""
    ).strip().upper()
    reason = str(
        shear_pack.get("summary_governing_reason")
        or shear_pack.get("summary_reason")
        or ""
    ).strip()
    if source == "spacing_envelope" and status == "FAIL":
        return True
    return "spacing_envelope" in reason and status == "FAIL"


def _auto_design_results_from_candidate(candidate: dict | None) -> dict:
    overview = dict((candidate or {}).get("overview") or {})
    utils = dict(overview.get("utils") or {})
    bending_components = dict((candidate or {}).get("bending_components") or {})
    ductility_util = bending_components.get("ductility_util")
    ku_limit = 0.36
    ku_value = None
    try:
        if ductility_util is not None:
            ku_value = float(ductility_util) * ku_limit
    except Exception:
        ku_value = None
    return {
        "bending": {"util": utils.get("bending")},
        "shear": {"util": utils.get("shear")},
        "ductility": {"ku": ku_value, "limit": ku_limit},
        "row_count": int((candidate or {}).get("row_count", 1) or 1),
        "_overview": overview,
    }


def _one_click_directional_tie_key(old_u: float, new_u: float, mode_config: dict) -> float:
    lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    hi = float(mode_config.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    if not math.isfinite(old_u) or not math.isfinite(new_u):
        return float("inf")
    if old_u < lo:
        return -(new_u - old_u)
    if old_u > hi:
        return -(old_u - new_u)
    return abs(new_u - old_u)


def _current_design_guide_fail_fingerprint(overview: dict | None) -> dict:
    ov = dict(overview or {})
    statuses = dict(ov.get("statuses") or {})
    utils = dict(ov.get("utils") or {})

    fail_keys = sorted(
        [
            str(k)
            for k, v in statuses.items()
            if str(v or "").strip().upper() == "FAIL"
        ],
    )

    shear_status = str(statuses.get("shear") or "").strip().upper()
    shear_util = _parse_util_value(utils.get("shear"))
    bending_status = str(statuses.get("bending") or "").strip().upper()
    bending_util = _parse_util_value(utils.get("bending"))

    return {
        "fail_keys": list(fail_keys),
        "shear_status": shear_status,
        "shear_util": shear_util,
        "bending_status": bending_status,
        "bending_util": bending_util,
    }


def _guidance_card_label(item: dict) -> str:
    if item["bucket"] == "start":
        return "START"
    if item["bucket"] in ("fail", "warn"):
        return "NEXT"
    if item["bucket"] == "efficiency":
        return "RECOMMEND"
    return "GOOD"


def _merge_target_band_probe_to_debug_sink(sink: dict | None, probe: dict) -> None:
    if not isinstance(sink, dict):
        return
    for k in (
        "target_band_default_stop",
        "target_band_override_allowed",
        "target_band_override_reason",
        "target_band_eps",
        "target_band_with_eps_passed",
        "winner_goal_alignment_score",
        "current_goal_alignment_score",
        "goal_alignment_improvement",
        "in_band_materiality_passed",
        "in_band_strong_override_passed",
        "mode_difference_material",
        "in_band_mode_search_strategy",
        "in_band_overview_worst_util",
    ):
        if k in probe:
            sink[k] = probe.get(k)


def _requires_full_coverage_for_primary_one_click(overview: dict) -> tuple[bool, list[str]]:
    statuses = dict((overview or {}).get("statuses") or {})
    fail_keys = sorted(
        [
            key
            for key, val in statuses.items()
            if str(val or "").upper() == "FAIL"
        ],
    )
    return (len(fail_keys) >= 2, fail_keys)

# Mechanical extraction: dependency-satisfied provider helpers <=50 lines.
def _combined_underdesign_shear_strengthening_truth_gate_payload(
    working_state: dict,
    *,
    overview: dict | None,
    efficiency_classification: str | None = None,
) -> dict:
    """
    Safety gate: when (efficiency failing or not all key checks pass) and published
    shear truth is unresolved, shear strengthening paths must not be trusted.
    Caller must not invoke compute_efficiency_tightening_state from inside nested
    efficiency recomputation; pass efficiency_classification when known.
    """
    ov = overview if isinstance(overview, dict) else {}
    ws = _overlay_current_normalized_shear_truth(_guidance_state_snapshot(working_state))
    truth_resolved = ws.get("final_shear_truth_resolved")
    fail_reason = str(ws.get("final_shear_truth_failure_reason") or "").strip()
    cls = str(efficiency_classification or "").strip().lower()
    if not cls and bool(ov.get("any_fail")):
        cls = "failing"
    all_key_pass = bool(ov.get("all_key_pass"))
    combined_cond = (cls == "failing") or (not all_key_pass)
    block = bool(combined_cond and truth_resolved is False)
    reason = (fail_reason or "final_shear_truth_unresolved") if block else None
    out = {
        "combined_underdesign_shear_truth_block_active": block,
        "combined_underdesign_shear_truth_block_reason": reason,
        "combined_underdesign_shear_strengthening_suppressed": block,
        "combined_underdesign_truth_gate_source": "combined_underdesign_shear_truth_gate",
        "combined_underdesign_truth_gate_classification": cls or None,
        "combined_underdesign_truth_gate_all_key_pass": all_key_pass,
        "combined_underdesign_truth_gate_final_shear_truth_resolved": truth_resolved,
    }
    return out


def _shear_preview_for_updates(state: dict, shear_updates: dict) -> dict | None:
    from shear_checks_helpers import build_shear_check_rows_from_state

    preview_state = _guidance_state_snapshot(state)
    preview_state.update(shear_updates)
    pack = build_shear_check_rows_from_state(preview_state)
    if not pack:
        return None

    web_util = float("inf")
    for row in pack.get("rows", []):
        if row.get("title") == "Web-crushing strength":
            try:
                web_util = float(row.get("util"))
            except Exception:
                web_util = float("inf")
            break

    util = pack.get("summary_util")
    try:
        util = float(util)
    except Exception:
        util = float("inf")

    return {
        "util": util,
        "web_util": web_util,
        "phi_vu": float(pack.get("summary_governing_capacity_kN", pack.get("summary_phiVu_kN", 0.0)) or 0.0),
        "veq": float(pack.get("summary_governing_demand_kN", pack.get("summary_Veq_kN", 0.0)) or 0.0),
        "rows": pack.get("rows", []),
    }


def _invalid_shear_spacing_change_without_activation(
    base_state: dict,
    candidate_state: dict,
    *,
    source: str,
) -> bool:
    if _shear_reinforcement_is_active(base_state):
        return False
    spacing_before = _float_from_state(base_state, "s_lig", 0.0)
    spacing_after = _float_from_state(candidate_state, "s_lig", spacing_before)
    candidate_legs = _int_from_state(candidate_state, "lig_legs", 0)
    if candidate_legs >= 2 or abs(spacing_after - spacing_before) <= 1e-9:
        return False
    _agent_debug_log(
        "Invalid shear candidate: spacing changed without activating stirrups",
        {
            "source": source,
            "lig_legs": candidate_legs,
            "lig_d": _int_from_state(candidate_state, "lig_d", 0),
            "s_lig": spacing_after,
            "shear_reinforcement_active": False,
        },
        location="inputs_page.py:shear_activation_guard",
        hypothesis_id="H_SHEAR_INVALID",
    )
    return True


def _log_shear_candidate_debug(
    *,
    source: str,
    candidate_state: dict,
    candidate: dict | None,
) -> None:
    if not bool(st.session_state.get("_dev_mode")):
        return
    shear_preview = _evaluate_shear_with_state(candidate_state) or {}
    phi_vu = 0.0
    veq = 0.0
    try:
        results = shear_preview.get("results")
        phi_vu = float(getattr(results, "phi_Vu", 0.0) or 0.0)
        veq = float(getattr(results, "V_eq", 0.0) or 0.0)
    except Exception:
        phi_vu = 0.0
        veq = 0.0
    _agent_debug_log(
        "Shear candidate debug",
        {
            "source": source,
            "lig_legs": _int_from_state(candidate_state, "lig_legs", 0),
            "lig_d": _int_from_state(candidate_state, "lig_d", 0),
            "s_lig": _float_from_state(candidate_state, "s_lig", 0.0),
            "shear_reinforcement_active": _shear_reinforcement_is_active(candidate_state),
            "phiVu": phi_vu,
            "Veq": veq,
            "shear_util": float(shear_preview.get("util", 0.0) or 0.0) if shear_preview else None,
            "candidate_score": None if candidate is None else candidate.get("score"),
        },
        location="inputs_page.py:shear_candidate_debug",
        hypothesis_id="H_SHEAR_DEBUG",
    )


def _shear_candidate_type(base_state: dict, candidate_state: dict) -> str:
    width_key, _, current_width = _resolve_geometry_width_context(base_state)
    current_depth = _float_from_state(base_state, "D", 0.0)
    next_width = _float_from_state(candidate_state, width_key, current_width)
    next_depth = _float_from_state(candidate_state, "D", current_depth)
    width_changed = abs(next_width - current_width) > 1e-9
    depth_changed = abs(next_depth - current_depth) > 1e-9
    current_spacing = _float_from_state(base_state, "s_lig", 0.0)
    next_spacing = _float_from_state(candidate_state, "s_lig", current_spacing)
    current_legs = _int_from_state(base_state, "lig_legs", 0)
    next_legs = _int_from_state(candidate_state, "lig_legs", current_legs)
    current_dia = _int_from_state(base_state, "lig_d", 0)
    next_dia = _int_from_state(candidate_state, "lig_d", current_dia)
    if next_legs == 0 and current_legs > 0:
        return "no shear links"
    spacing_tighter = next_spacing < current_spacing - 1e-9
    legs_increased = next_legs > current_legs
    dia_increased = next_dia > current_dia
    if (width_changed or depth_changed) and (spacing_tighter or legs_increased or dia_increased):
        return "combined"
    if depth_changed:
        return "depth increase"
    if width_changed:
        return "width increase"
    if dia_increased and not spacing_tighter and not legs_increased:
        return "larger dia"
    if legs_increased and not spacing_tighter:
        return "more legs"
    if spacing_tighter:
        return "spacing"
    if dia_increased:
        return "larger dia"
    if legs_increased:
        return "more legs"
    fc0 = float(_float_from_state(base_state, "fc", 0.0) or 0.0)
    fc1 = float(_float_from_state(candidate_state, "fc", fc0) or fc0)
    if abs(fc1 - fc0) > 1e-9:
        return "material_fc"
    return "spacing"


def _shear_change_magnitude(candidate: dict, state: dict) -> tuple:
    cs = dict(candidate.get("state") or {})
    cur_legs = max(_int_from_state(state, "lig_legs", 2), 2)
    cur_s = float(_float_from_state(state, "s_lig", 0.0) or 0.0)
    cur_dia = max(_int_from_state(state, "lig_d", 10), 10)
    _, _, cur_w = _resolve_geometry_width_context(state)
    cur_d = float(_float_from_state(state, "D", 600.0) or 600.0)

    cand_legs = max(_int_from_state(cs, "lig_legs", cur_legs), 0)
    cand_s = float(_float_from_state(cs, "s_lig", cur_s) or cur_s)
    cand_dia = max(_int_from_state(cs, "lig_d", cur_dia), 0)
    _, _, cand_w = _resolve_geometry_width_context(cs)
    cand_d = float(_float_from_state(cs, "D", cur_d) or cur_d)

    leg_delta = abs(cand_legs - cur_legs)
    spacing_delta = abs(cand_s - cur_s)
    dia_delta = abs(cand_dia - cur_dia)
    depth_delta = abs(cand_d - cur_d)
    width_delta = abs(cand_w - cur_w)

    return (
        int(depth_delta > 1e-9 or width_delta > 1e-9),
        leg_delta,
        spacing_delta,
        dia_delta,
        depth_delta,
        width_delta,
    )


def _shortlist_smallest_successful_shear_candidates(
    candidates: list[dict],
    state: dict,
    *,
    target_hi: float | None,
) -> list[dict]:
    if not candidates:
        return []

    acceptable: list[dict] = []
    for cand in candidates:
        if not bool(cand.get("is_compliant")):
            continue
        su = _shear_util_from_overview_candidate(cand)
        if su is None:
            continue
        if target_hi is not None and float(su) > float(target_hi) + 1e-9:
            continue
        acceptable.append(cand)

    if not acceptable:
        return list(candidates)

    ranked = sorted(
        acceptable,
        key=lambda c: (
            _shear_change_magnitude(c, state),
            float(c.get("score", 0.0) or 0.0),
        ),
    )

    keep = [
        c for c in ranked
        if _shear_change_magnitude(c, state) == _shear_change_magnitude(ranked[0], state)
        or float(c.get("score", 999999.0) or 999999.0)
        <= float(ranked[0].get("score", 999999.0) or 999999.0) + 0.25
    ]
    return keep


def _candidate_is_within_smallest_fix_band(
    candidate: dict,
    smallest_mag: tuple | None,
    state: dict,
) -> bool:
    if smallest_mag is None:
        return True
    cand_mag = _shear_change_magnitude(candidate, state)
    return cand_mag <= smallest_mag


def _geometry_tightening_trial_updates(state: dict) -> list[dict]:
    goal = _design_optimisation_goal(state)
    width_key, _, current_width = _resolve_geometry_width_context(state)
    current_depth = _float_from_state(state, "D", 600.0)
    unique_updates: dict[tuple[tuple[str, str], ...], dict] = {}

    def _add_trial(width: float, depth: float) -> None:
        rounded_width = float(int(round(max(250.0, width) / 10.0) * 10))
        rounded_depth = float(int(round(max(350.0, depth) / 10.0) * 10))
        updates = {width_key: rounded_width, "D": rounded_depth}
        if width_key != "b":
            updates["b"] = rounded_width
        if _updates_match_state(state, updates):
            return
        signature = tuple(sorted((key, str(value)) for key, value in updates.items()))
        unique_updates[signature] = updates

    if goal == "shallower_beam":
        _add_trial(current_width, current_depth - 100.0)
        _add_trial(current_width, current_depth - 50.0)
        _add_trial(current_width - 50.0, current_depth - 50.0)
        _add_trial(current_width - 50.0, current_depth)
    elif goal == "balanced":
        _add_trial(current_width, current_depth - 50.0)
        _add_trial(current_width - 50.0, current_depth)
        _add_trial(current_width - 50.0, current_depth - 50.0)
    elif goal == "less_longitudinal_reinforcement":
        _add_trial(current_width, current_depth - 50.0)
        _add_trial(current_width - 50.0, current_depth)
    else:
        _add_trial(current_width, current_depth - 50.0)

    return list(unique_updates.values())


def _guidance_item_family(item: dict | None) -> str:
    return _guidance_item_family_extracted(item)


def _design_guide_render_plan(
    guidance_items: list[dict],
    recommendation_result: dict | None,
    collapse_meta: dict | None,
) -> dict:
    items = list(guidance_items or [])
    collapse = dict(collapse_meta or {})

    primary_only = False
    visible_items = list(items)
    reason = "normal"

    rr_title = str((recommendation_result or {}).get("title") or "").strip()
    top_title = str((items[0] or {}).get("title_main") or "").strip() if items else ""

    if items:
        primary_only = True
        visible_items = items[:1]
        reason = "primary_visible_card_only"
    elif bool(collapse.get("collapsed")) and recommendation_result and len(items) <= 1:
        primary_only = True
        visible_items = []
        reason = "collapsed_primary_only"
    elif recommendation_result and len(items) == 1 and rr_title and top_title and rr_title == top_title:
        primary_only = True
        visible_items = []
        reason = "single_primary_duplicate_suppressed"

    return {
        "render_primary_only": bool(primary_only),
        "visible_guidance_items": list(visible_items),
        "reason": reason,
        "input_count": len(items),
        "visible_count": len(visible_items),
    }


def apply_design_candidate(state, rec):
    """
    Legacy compatibility: apply top-level ``updates`` by writing keys into shared state.
    Used only as a fallback when ``apply.mode`` / ``apply.payload`` cannot complete the apply.
    """
    updates = rec.get("updates", {}) if isinstance(rec, dict) else {}
    if not isinstance(updates, dict):
        updates = {}
    if updates and not st.session_state.get(DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY):
        pending = st.session_state.get("pending_recommendation")
        _begin_design_guide_apply_trace(
            recommendation=rec if isinstance(rec, dict) else pending,
            source="apply_design_candidate",
        )
    for key, value in updates.items():
        state[key] = value
    if updates:
        try:
            accepted_fp = _local_cleanup_acceptance_fingerprint(_shared_state_snapshot())
            _DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.add(accepted_fp)
            st.session_state["_design_guide_post_cleanup_acceptance_fp"] = accepted_fp
            st.session_state["_design_guide_post_cleanup_acceptance_enabled"] = True
        except Exception:
            pass
        _emit_design_guide_apply_trace_run_end(
            stop_reason="applied_recommendation",
            final_updates=dict(updates),
            winner_label=str((rec or {}).get("label") or (rec or {}).get("title") or ""),
        )
    return bool(updates)


def _effective_apply_mode_and_payload_from_pending(rec: dict) -> tuple[str | None, dict]:
    """
    Resolve canonical (apply.mode, apply.payload) from a pending record.
    Supports Recommendation Result shape and legacy guidance pending from _build_pending_recommendation.
    """
    if not isinstance(rec, dict):
        return None, {}
    apply_obj = rec.get("apply")
    if isinstance(apply_obj, dict):
        mode = str(apply_obj.get("mode") or "").strip()
        payload = dict(apply_obj.get("payload") or {})
        if mode:
            return mode, payload
    action_type = str(rec.get("action_type") or "").strip()
    payload = dict(rec.get("action_payload") or {})
    resolved_candidate = rec.get("resolved_candidate")
    if isinstance(resolved_candidate, dict):
        resolved_updates = resolved_candidate.get("updates")
        if isinstance(resolved_updates, dict) and resolved_updates:
            payload["resolved_candidate_updates"] = dict(resolved_updates)
            payload.setdefault(
                "resolved_candidate_label",
                str(resolved_candidate.get("label") or rec.get("title") or "Apply recommendation").strip(),
            )
            payload.setdefault(
                "resolved_candidate_action_type",
                str(resolved_candidate.get("action_type") or action_type or "apply_compound_guidance").strip(),
            )
            payload.setdefault("updates", dict(resolved_updates))
            action_type = "apply_resolved_candidate"
    if action_type and payload:
        return action_type, payload
    return None, {}


def _shear_spacing_layout_must_not_trigger_strengthening(state: dict, overview: dict | None) -> bool:
    """
    When published canonical truth is sectional-strength PASS without an explicit
    spacing-governing strength rule, layout/envelope spacing must not drive shear
    strengthening (detailing-only context).
    """
    if not isinstance(state, dict):
        return False
    ov = overview if isinstance(overview, dict) else {}
    sp = (ov.get("packs") or {}).get("shear") or {}
    truth_st = str(state.get("shear_truth_status") or sp.get("shear_truth_status") or "").strip().upper()
    if truth_st != "PASS":
        return False
    gov_src = str(
        state.get("shear_governing_source")
        or sp.get("summary_governing_source")
        or ov.get("overview_shear_governing_source")
        or "",
    ).strip()
    gov_rsn = str(
        state.get("shear_governing_reason")
        or sp.get("summary_governing_reason")
        or ov.get("overview_shear_governing_reason")
        or "",
    ).strip()
    if gov_src != "sectional_shear_capacity" or "sectional_shear_capacity_governs" not in gov_rsn:
        return False
    if bool(state.get("canonical_shear_spacing_override_active")):
        return False
    return True


def _log_shear_ladder_attempt(
    state: dict,
    *,
    ladder_mode: str,
    branch: str,
    lig_legs: int,
    s_lig: float,
    proposed_updates: dict | None,
    expected_util_after: float | None,
    decision: str,
    reason: str,
) -> None:
    if not DEBUG_DESIGN_GUIDANCE_PROBE:
        return
    _agent_debug_log(
        "Shear ladder candidate",
        {
            "ladder_mode": ladder_mode,
            "branch": branch,
            "current_lig_legs": lig_legs,
            "current_s_lig": s_lig,
            "proposed_updates": proposed_updates,
            "expected_util_after": expected_util_after,
            "decision": decision,
            "reason": reason,
        },
        location="inputs_page.py:_compute_shear_recommendation:ladder",
        hypothesis_id="H_SHEAR_LADDER",
    )


def _log_design_reco_candidate_rank(
    *,
    domain: str,
    event: str,
    candidate: dict | None,
    reason: str,
    util_before: float | None = None,
    util_after: float | None = None,
) -> None:
    payload = {
        "domain": domain,
        "event": event,
        "reason": reason,
        "candidate_label": None if candidate is None else str(candidate.get("label") or ""),
        "candidate_source": None if candidate is None else str(candidate.get("source") or ""),
        "candidate_type": None
        if candidate is None
        else str(
            candidate.get("shear_candidate_type")
            or candidate.get("shear_ladder_branch")
            or candidate.get("recommendation_geometry_trial")
            or "",
        ),
        "branch": None if candidate is None else str(candidate.get("shear_ladder_branch") or ""),
        "updates": None if candidate is None else dict(candidate.get("updates") or {}),
        "score": None if candidate is None else candidate.get("score"),
        "util_before": util_before,
        "util_after": util_after,
        "candidate_post_util": None if candidate is None else candidate.get("candidate_post_util"),
        "candidate_reaches_target_band": None if candidate is None else candidate.get("candidate_reaches_target_band"),
        "candidate_distance_to_target_band": None
        if candidate is None
        else candidate.get("candidate_distance_to_target_band"),
    }
    if DEBUG_DESIGN_GUIDANCE_PROBE:
        _agent_debug_log(
            "Design recommendation ranking",
            payload,
            location="inputs_page.py:_log_design_reco_candidate_rank",
            hypothesis_id="H_DESIGN_RECO_RANK",
        )
    if _ACTIVE_GUIDANCE_RECO_TRACE is not None:
        _append_design_guide_reco_trace(payload)


def _shear_recommendation_prefinal_eligible(
    candidate: dict | None,
    *,
    state: dict,
    conservative: bool,
    baseline_su: float | None,
) -> tuple[bool, str]:
    if not candidate:
        return False, "none"
    updates = candidate.get("updates") or {}
    if not updates:
        return False, "empty_updates"
    if _updates_match_state(state, updates):
        return False, "noop"
    if not str(candidate.get("label") or "").strip():
        return False, "missing_label"
    if candidate.get("score") is None:
        return False, "missing_score"
    su = _shear_util_from_overview_candidate(candidate)
    if su is None:
        return False, "missing_shear_util"
    if not conservative and baseline_su is not None and float(su) >= float(baseline_su) - 1e-9:
        return False, "shear_util_not_improved"
    branch = str(candidate.get("shear_ladder_branch") or "")
    cs = dict(candidate.get("state") or {})
    if branch == "spacing_tighter":
        s_prop = _float_from_state(cs, "s_lig", _float_from_state(state, "s_lig", 0.0))
        s_cur = _float_from_state(state, "s_lig", 0.0)
        if s_cur > 1e-9 and s_prop >= s_cur - 1e-9:
            return False, "spacing_not_reduced"
    if not conservative:
        legs = _int_from_state(cs, "lig_legs", 0)
        if legs > 0 and legs < 2:
            return False, "lig_legs_below_2"
    return True, "ok"


def _sanitize_shared_update_bundle(
    updates: dict | None,
    *,
    source: str,
) -> tuple[dict, dict]:
    """
    Filter an updates dict down to keys that are valid shared-state writes.

    Returns:
      (
        sanitized_updates,
        meta = {
          "source": ...,
          "input_key_count": ...,
          "sanitized_key_count": ...,
          "dropped_nonshared_keys": [...],
          "dropped_private_keys": [...],
        }
      )
    """
    raw = dict(updates or {})
    sanitized: dict[str, object] = {}
    dropped_nonshared: list[str] = []
    dropped_private: list[str] = []

    for key, value in raw.items():
        k = str(key or "")
        if not k:
            continue
        if k.startswith("_"):
            dropped_private.append(k)
            continue
        if k not in SHARED_DEFAULTS:
            dropped_nonshared.append(k)
            continue
        sanitized[k] = value

    meta = {
        "source": str(source or ""),
        "input_key_count": len(raw),
        "sanitized_key_count": len(sanitized),
        "dropped_nonshared_keys": sorted(set(dropped_nonshared)),
        "dropped_private_keys": sorted(set(dropped_private)),
    }
    return sanitized, meta


def _record_one_click_shear_publish_audit(
    *,
    stage: str,
    source: str,
    candidate_updates: dict | None,
    publish_attempted: bool,
    publish_blocked: bool,
) -> None:
    updates = dict(candidate_updates or {})
    relevant = {
        key: updates.get(key)
        for key in ("lig_legs", "lig_d", "s_lig")
        if key in updates
    }
    if not relevant:
        return
    entry = {
        "stage": str(stage or ""),
        "source": str(source or ""),
        "candidate_shear": dict(relevant),
        "publish_attempted": bool(publish_attempted),
        "publish_blocked": bool(publish_blocked),
        "shared_shear_snapshot": {
            "s_lig": st.session_state.get("s_lig"),
            "lig_d": st.session_state.get("lig_d"),
            "lig_legs": st.session_state.get("lig_legs"),
        },
    }
    audit = list(st.session_state.get("_one_click_shear_publish_audit") or [])
    audit.append(entry)
    if len(audit) > 20:
        audit = audit[-20:]
    st.session_state["_one_click_shear_publish_audit"] = audit


def _invalidate_design_guide_caches(
    *,
    reason: str,
    updated_keys: list[str] | None = None,
    preserve_apply_banner: bool = False,
) -> list[str]:
    removed: list[str] = []
    _clear_design_guide_transient_ui_state(
        clear_history=False,
        preserve_apply_banner=preserve_apply_banner,
    )
    for session_key in list(st.session_state.keys()):
        if str(session_key).startswith("_recommendation_cache_"):
            removed.append(str(session_key))
            st.session_state.pop(session_key, None)
    if bool(st.session_state.get("_dev_mode")):
        _agent_debug_log(
            "Invalidated design guide caches",
            {
                "reason": reason,
                "updated_keys": list(updated_keys or []),
                "removed_cache_keys": removed,
            },
            location="inputs_page.py:_invalidate_design_guide_caches",
            hypothesis_id="H301",
        )
    return removed


def _rescue_bootstrap_partial_commit_allowed(
    *,
    solve: dict | None,
    current_fail_keys: list[str] | None,
    candidate_for_commit: dict | None,
    candidate_commit_meta: dict | None,
    solver_final_updates: dict | None,
    seed_eval: dict | None,
) -> bool:
    """
    Narrow acceptance seam for direct-start rescue bootstrap cases.

    When rescue hands back a materially better legal seed state but the post-seed solve
    finds no further full-coverage winner, keep that effective bootstrap as partial
    progress instead of zeroing it out.
    """
    dbg = dict(((solve or {}).get("one_click_solver_debug") or {}))
    if not bool(dbg.get("rescue_mode_entered")):
        return False
    if not bool(dbg.get("rescue_mode_effective_seed_found")):
        return False
    if str((candidate_commit_meta or {}).get("reason") or "") != "candidate_preview_has_fail_status":
        return False
    fail_keys = sorted(str(k or "").strip().lower() for k in (current_fail_keys or []) if str(k or "").strip())
    if "bending" not in fail_keys or "shear" not in fail_keys:
        return False
    if not isinstance(candidate_for_commit, dict) or not bool(solver_final_updates):
        return False
    covered = sorted(
        str(k or "").strip().lower()
        for k in list((candidate_commit_meta or {}).get("covered_fail_keys") or [])
        if str(k or "").strip()
    )
    remaining = sorted(
        str(k or "").strip().lower()
        for k in list((candidate_commit_meta or {}).get("remaining_fail_keys") or [])
        if str(k or "").strip()
    )
    if not covered or len(remaining) >= len(fail_keys):
        return False
    # Rescue already proved this path improves over the pre-rescue result before handing
    # control back here. At commit time we only need to confirm that the bootstrap state
    # genuinely reduces the current fail set instead of being a no-op / same-failure echo.
    _ = seed_eval
    return True


def _candidate_failure_coverage_summary(
    current_state: dict,
    candidate: dict,
) -> dict:
    current_overview = _collect_design_overview(current_state) if isinstance(current_state, dict) else {}
    candidate_overview = dict(candidate.get("overview") or {}) if isinstance(candidate, dict) else {}

    current_fail = sorted(
        [
            key
            for key, val in (current_overview.get("statuses") or {}).items()
            if str(val or "").upper() == "FAIL"
        ],
    )
    candidate_fail = sorted(
        [
            key
            for key, val in (candidate_overview.get("statuses") or {}).items()
            if str(val or "").upper() == "FAIL"
        ],
    )

    covered = sorted([k for k in current_fail if k not in candidate_fail])
    remaining = sorted([k for k in current_fail if k in candidate_fail])

    return {
        "current_fail_keys": list(current_fail),
        "candidate_fail_keys": list(candidate_fail),
        "covered_fail_keys": list(covered),
        "remaining_fail_keys": list(remaining),
        "covers_all_current_failures": len(current_fail) > 0 and len(remaining) == 0,
    }

# Mechanical extraction: dependency-satisfied provider helpers <=75 lines.
def _auto_design_governing_fingerprint(state: dict | None = None) -> tuple:
    source = state or _shared_state_snapshot()
    actions = _resolve_design_actions_from_state(source)
    governing_keys = (
        "design_optimisation_goal",
        "optimisation_lock_geometry",
        "sec_shape",
        "b",
        "bw",
        "tw",
        "D",
        "fc",
        "fsy",
        "Ec",
        "Es",
        "phi_bend",
        "phi_shear",
        "cover_top",
        "cover_bot",
        "cover_side",
        "rowgap_top",
        "rowgap_bot",
        "Ast_top",
        "Tu_star",
        "P_star",
        "lig_d",
        "lig_legs",
        "s_lig",
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    )
    fingerprint = [(key, str(source.get(key))) for key in governing_keys]
    fingerprint.extend([
        ("resolved_Mu", str(actions.get("Mu"))),
        ("resolved_Vu", str(actions.get("Vu"))),
        ("resolved_Nu", str(actions.get("Nu"))),
        ("resolved_SLS_M", str(actions.get("SLS_M"))),
        ("resolved_SLS_V", str(actions.get("SLS_V"))),
        ("resolved_source", str(actions.get("source"))),
    ])
    return tuple(fingerprint)


def _prefer_target_band_guidance_item_order(
    guidance_items: list[dict] | None,
    *,
    state: dict,
    mode_config: dict | None = None,
) -> list[dict]:
    items = [item for item in list(guidance_items or []) if isinstance(item, dict)]
    if len(items) < 2:
        return items
    mode_cfg = mode_config if isinstance(mode_config, dict) else _design_mode_config(_design_optimisation_goal(state))
    t_lo, t_hi, _ = _resolved_efficiency_target_band(mode_cfg, goal=_design_optimisation_goal(state))
    target_rows: list[tuple[tuple, int, dict]] = []
    target_mid = (float(t_lo) + float(t_hi)) / 2.0
    for idx, item in enumerate(items):
        action_type = str(item.get("action_type") or "").strip()
        if not action_type:
            continue
        payload = dict(item.get("action_payload") or {})
        resolved = dict(item.get("resolved_candidate") or {})
        updates = dict(
            payload.get("resolved_candidate_updates")
            or payload.get("updates")
            or resolved.get("updates")
            or {}
        )
        if not updates:
            continue
        truth = dict(item.get("display_truth") or {})
        util = _parse_util_value(
            payload.get("resolved_candidate_post_util")
            if payload.get("resolved_candidate_post_util") is not None
            else resolved.get("candidate_post_util", truth.get("source_candidate_util", truth.get("displayed_util")))
        )
        if util is None or not (float(t_lo) <= float(util) <= float(t_hi)):
            continue
        target_rows.append(
            (
                (
                    abs(float(util) - target_mid),
                    len(updates),
                    idx,
                ),
                idx,
                item,
            )
        )
    if not target_rows:
        return items
    target_rows.sort(key=lambda row: row[0])
    selected_idx = int(target_rows[0][1])
    if selected_idx == 0:
        return items
    selected = items[selected_idx]
    return [selected] + [item for idx, item in enumerate(items) if idx != selected_idx]


def _design_action_widget_specs(selected_prefix: str) -> list[dict]:
    return [
        {
            "label": "Positive design moment Mu*+ (kNm)",
            "widget_key": "inputs_load_Mstar_pos_proxy",
            "shared_key": f"{selected_prefix}_Mstar_pos_manual",
            "proxy_key": "load_Mstar_pos_proxy",
            "help_text": "Sagging bending demand magnitude (top in compression, bottom in tension).",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Negative design moment Mu*- (kNm)",
            "widget_key": "inputs_load_Mstar_neg_proxy",
            "shared_key": f"{selected_prefix}_Mstar_neg_manual",
            "proxy_key": "load_Mstar_neg_proxy",
            "help_text": "Hogging bending demand magnitude (top in tension, bottom in compression). Enter as positive.",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Applied prestress P* (kN)",
            "widget_key": "inputs_P_star",
            "shared_key": "P_star",
            "proxy_key": None,
            "help_text": "Net prestress force at the section (compression positive).",
            "disabled_in_design_mode": False,
        },
        {
            "label": "Design torsion Tu* (kNm)",
            "widget_key": "inputs_Tu_star",
            "shared_key": "Tu_star",
            "proxy_key": None,
            "help_text": "Factored torsion; used on torsion page (placeholder here).",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Design shear Vu* (kN)",
            "widget_key": "inputs_load_Vstar_proxy",
            "shared_key": f"{selected_prefix}_Vstar",
            "proxy_key": "load_Vstar_proxy",
            "help_text": "Factored design shear at the critical section.",
            "disabled_in_design_mode": True,
        },
        {
            "label": "Axial force N* (kN)",
            "widget_key": "inputs_load_Nstar_proxy",
            "shared_key": f"{selected_prefix}_Nstar",
            "proxy_key": "load_Nstar_proxy",
            "help_text": "Axial action at the section (+compression / −tension).",
            "disabled_in_design_mode": True,
        },
    ]


def _collapse_to_single_primary_guidance_item(
    guidance_items: list[dict],
    state: dict,
) -> tuple[list[dict], dict]:
    _bind_guidance_item_consolidation_dependencies(globals())
    return _collapse_to_single_primary_guidance_item_extracted(guidance_items, state)


def _suppress_redundant_guidance_items(
    guidance_items: list[dict],
    recommendation_result: dict | None,
) -> tuple[list[dict], dict]:
    """
    Remove secondary items that materially duplicate the primary recommendation move.
    """
    _ = recommendation_result
    items = list(guidance_items or [])
    if not items:
        return items, {
            "suppressed": False,
            "reason": "no_items",
            "suppressed_titles": [],
            "subset_suppressed": False,
            "subset_suppressed_titles": [],
            "primary_update_keys": [],
            "secondary_update_keys": [],
        }

    primary_item = items[0]
    kept = [primary_item]
    suppressed_titles = []
    subset_suppressed_titles = []
    primary_updates = _guidance_update_map(primary_item)
    primary_update_keys = sorted(str(k) for k in primary_updates.keys())
    secondary_update_keys: list[list[str]] = []

    for item in items[1:]:
        secondary_updates = _guidance_update_map(item)
        primary_keys = set(primary_updates.keys())
        secondary_keys = set(secondary_updates.keys())
        secondary_is_exact_match = bool(primary_updates) and secondary_updates == primary_updates
        secondary_is_subset = bool(primary_updates) and bool(secondary_updates) and secondary_keys.issubset(primary_keys)
        if secondary_is_subset:
            for k, v in secondary_updates.items():
                if primary_updates.get(k) != v:
                    secondary_is_subset = False
            break
        if secondary_is_exact_match or secondary_is_subset:
            title = str(item.get("title_main") or "")
            suppressed_titles.append(title)
            secondary_update_keys.append(sorted(str(k) for k in secondary_updates.keys()))
            if secondary_is_subset and not secondary_is_exact_match:
                subset_suppressed_titles.append(title)
            continue
        kept.append(item)

    return kept, {
        "suppressed": bool(suppressed_titles),
        "reason": "overlapping_update_subset" if suppressed_titles else "none",
        "suppressed_titles": suppressed_titles,
        "subset_suppressed": bool(subset_suppressed_titles),
        "subset_suppressed_titles": subset_suppressed_titles,
        "primary_update_keys": primary_update_keys,
        "secondary_update_keys": secondary_update_keys,
    }


def _shear_candidate_selector_key(candidate: dict, seed_candidate: dict, mode_config: dict) -> tuple:
    current_state = dict(seed_candidate.get("state") or {})
    _annotate_candidate_target_band_metrics(candidate, mode_config)
    metrics = _shear_candidate_practicality_metrics(candidate, current_state)
    candidate.update(metrics)
    post_util = candidate.get("candidate_post_util", candidate.get("worst_util"))
    try:
        post_util_f = float(post_util) if post_util is not None else float("inf")
    except (TypeError, ValueError):
        post_util_f = float("inf")
    return (
        0 if bool(candidate.get("is_compliant")) else 1,
        0 if _candidate_in_target_band(candidate, mode_config) else 1,
        float(candidate.get("candidate_distance_to_target_band") or _candidate_util_distance(candidate, mode_config) or 0.0),
        float(metrics.get("shear_candidate_engineering_change", 0.0) or 0.0),
        int(metrics.get("shear_candidate_leg_delta", 0) or 0),
        float(metrics.get("shear_candidate_spacing_delta", 0.0) or 0.0),
        int(metrics.get("shear_candidate_dia_delta", 0) or 0),
        int(metrics.get("shear_candidate_geometry_escalation_flag", 0) or 0),
        float(metrics.get("shear_candidate_geometry_delta", 0.0) or 0.0),
        float(metrics.get("shear_candidate_steel_delta", 0.0) or 0.0),
        float(metrics.get("shear_candidate_total_practicality_penalty", 0.0) or 0.0),
        float(candidate.get("score", 0.0) or 0.0),
        post_util_f,
        float(candidate.get("depth", 0.0) or 0.0),
        float(candidate.get("width", 0.0) or 0.0),
    )


def _pick_best_shear_recommendation_by_selector(
    candidates: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
    conservative: bool,
    baseline_su: float | None,
) -> dict | None:
    pool = [c for c in candidates if c]
    while pool:
        ranked_pool = sorted(
            pool,
            key=lambda item: _shear_candidate_selector_key(item, seed_candidate, mode_config),
        )
        pick = ranked_pool[0] if ranked_pool else None
        if pick is None:
            return None
        if _updates_match_state(state, pick.get("updates") or {}):
            _log_design_reco_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=pick,
                reason="noop_updates_match_state",
                util_after=_shear_util_from_overview_candidate(pick),
            )
            pool = [x for x in pool if x is not pick]
            continue
        su = _shear_util_from_overview_candidate(pick)
        if su is None:
            _log_design_reco_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=pick,
                reason="missing_shear_util",
            )
            pool = [x for x in pool if x is not pick]
            continue
        if not conservative and baseline_su is not None and float(su) >= float(baseline_su) - 1e-9:
            _log_design_reco_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=pick,
                reason="shear_util_not_improved_vs_baseline",
                util_before=float(baseline_su),
                util_after=float(su),
            )
            pool = [x for x in pool if x is not pick]
            continue
        _log_design_reco_candidate_rank(
            domain="shear",
            event="accepted",
            candidate=pick,
            reason="selector_top_valid",
            util_before=None if conservative else baseline_su,
            util_after=float(su),
        )
        return pick
    return None


def _one_click_commit_audit_passes(
    commit_audit: dict | None,
    *,
    partial_progress_commit: bool = False,
    best_effort_cleanup_commit: bool = False,
    pre_commit_worst_util: float | None = None,
    pre_commit_statuses: dict | None = None,
) -> tuple[bool, str]:
    _bind_post_commit_audit_dependencies(globals())
    return _one_click_commit_audit_passes_extracted(
        commit_audit,
        partial_progress_commit=partial_progress_commit,
        best_effort_cleanup_commit=best_effort_cleanup_commit,
        pre_commit_worst_util=pre_commit_worst_util,
        pre_commit_statuses=pre_commit_statuses,
    )


def _candidate_family_matches_governing_domain(family_name: str, governing_domain: str) -> bool:
    return _candidate_family_matches_governing_domain_extracted(family_name, governing_domain)

# Mechanical extraction: unlocked medium provider helper.
def _derive_design_guide_terminal_state_from_current_overview(
    guidance_debug: dict,
    guidance_disp_state: dict,
    guidance_items: list[dict],
) -> str | None:
    _bind_terminal_state_dependencies(globals())
    return _derive_design_guide_terminal_state_from_current_overview_extracted(
        guidance_debug,
        guidance_disp_state,
        guidance_items,
    )

# Mechanical extraction: widget reconciliation provider helper family.
def _request_shear_widget_seed_from_shared(reason: str) -> dict:
    ss = st.session_state
    reason_norm = str(reason or "").strip() or "unspecified"
    shared_values = {
        "lig_d": ss.get("lig_d"),
        "lig_legs": ss.get("lig_legs"),
        "s_lig": ss.get("s_lig"),
    }
    widget_map = {
        "inputs_lig_d": shared_values["lig_d"],
        "inputs_lig_legs": shared_values["lig_legs"],
        "inputs_s_lig": shared_values["s_lig"],
        "shear_lig_d": shared_values["lig_d"],
        "shear_lig_legs": shared_values["lig_legs"],
        "shear_s_lig": shared_values["s_lig"],
    }
    widget_keys = list(widget_map.keys())
    for widget_key in widget_keys:
        ss.pop(f"_cached_{widget_key}", None)

    hydrated_map = ss.get("_hydrated_from_shared_map")
    if isinstance(hydrated_map, dict):
        for widget_key in widget_keys:
            hydrated_map.pop(widget_key, None)

    payload = {
        "seed_requested": True,
        "reason": reason_norm,
        "shared": dict(shared_values),
        "widget_keys": list(widget_keys),
        "direct_widget_writes": [],
    }
    ss["_pending_shear_widget_seed_from_shared"] = dict(payload)
    ss["inputs_shear_widget_seed_requested"] = True
    ss["inputs_shear_widget_seed_reason"] = reason_norm
    ss["_inputs_shear_widget_seed_latest"] = dict(payload)
    try:
        _agent_debug_log(
            "Inputs shear widget seed requested from shared",
            payload,
            location="inputs_page.py:_request_shear_widget_seed_from_shared",
            hypothesis_id="H_INPUTS_SHEAR_WIDGET_SEED_REQUEST",
        )
    except Exception:
        pass
    return payload


def _mark_design_guide_dirty() -> None:
    """Inputs changed vs last rendered guide; clear stale cards/cache (not beam state)."""
    dirty_plan = build_inputs_design_guide_dirty_mark_plan(
        refresh_key=DESIGN_GUIDE_NEEDS_REFRESH_KEY,
        clear_history=False,
        preserve_apply_banner=False,
    )
    st.session_state[dirty_plan.refresh_key] = dirty_plan.refresh_value
    _clear_design_guide_transient_ui_state(
        clear_history=dirty_plan.clear_history,
        preserve_apply_banner=dirty_plan.preserve_apply_banner,
    )


def _sync_auto_design_invalidation(state: dict | None = None) -> None:
    current_fingerprint = _auto_design_governing_fingerprint(state)
    previous_fingerprint = st.session_state.get("_auto_design_last_fingerprint")
    if previous_fingerprint is None:
        st.session_state["_auto_design_last_fingerprint"] = current_fingerprint
        return
    if current_fingerprint != previous_fingerprint:
        st.session_state["_auto_design_invalidated"] = True
        st.session_state["_auto_design_last_fingerprint"] = current_fingerprint
        st.session_state.pop("pending_recommendation", None)
        st.session_state.pop("pending_recommendation_applied_id", None)
        st.session_state.pop("_solver_result", None)
        st.session_state.pop("_one_click_run_feedback", None)
        st.session_state.pop("auto_design_status", None)
        st.session_state.pop("auto_design_steps", None)
        st.session_state.pop("auto_design_request_source", None)
        st.session_state.pop(AUTO_DESIGN_REQUEST_SOURCE_KEY, None)
        st.session_state.pop(AUTO_DESIGN_REQUEST_TS_KEY, None)
        st.session_state.pop(AUTO_DESIGN_AUTO_INVOKE_KEY, None)
        st.session_state.pop("_inputs_action_run_auto_design", None)
        st.session_state.pop("auto_design_invoke_set", None)
        st.session_state.pop("auto_design_invoke_pending", None)
        st.session_state.pop("auto_design_invoke_consumed", None)
        _clear_auto_design_runtime_latches("design_state_changed")


def _sync_design_action_widget_to_shared(
    widget_key: str,
    shared_key: str,
    proxy_key: str | None = None,
    *,
    trigger_rerun: bool = False,
) -> None:
    _sync_design_action_widget_to_shared_module(
        widget_key,
        shared_key,
        proxy_key,
        trigger_rerun=trigger_rerun,
        st_module=st,
        debug_design_guidance_probe=DEBUG_DESIGN_GUIDANCE_PROBE,
        append_design_guide_trace_fn=_append_design_guide_trace,
        get_param_fn=get_param,
        mark_user_edit_fn=mark_user_edit,
        set_shared_fn=set_shared,
        invalidate_inputs_summary_packs_fn=_invalidate_inputs_summary_packs,
        queue_inputs_refresh_fn=_queue_inputs_refresh,
        invalidate_design_guide_caches_fn=_invalidate_design_guide_caches,
        mark_design_guide_dirty_fn=_mark_design_guide_dirty,
        persist_active_beam_from_shared_fn=persist_active_beam_from_shared,
        persist_state_snapshot_fn=persist_state_snapshot,
        debug_resolved_guidance_actions_fn=_debug_resolved_guidance_actions,
        shared_state_snapshot_fn=_shared_state_snapshot,
        sync_auto_design_invalidation_fn=_sync_auto_design_invalidation,
        debug_check_design_action_consistency_fn=_debug_check_design_action_consistency,
        time_ms_fn=lambda: int(time.time() * 1000),
    )


def _debug_check_design_action_consistency(state: dict) -> None:
    if not DEBUG_DESIGN_GUIDANCE_PROBE:
        return
    if str(st.session_state.get("loads_edit_mode", "ULS") or "ULS").upper() != "ULS":
        return
    actions = _resolve_design_actions_from_state(state)
    payload = {
        "widget_M_pos": st.session_state.get("inputs_load_Mstar_pos_proxy"),
        "widget_M_neg": st.session_state.get("inputs_load_Mstar_neg_proxy"),
        "widget_V": st.session_state.get("inputs_load_Vstar_proxy"),
        "shared_uls_M": st.session_state.get("uls_Mstar"),
        "shared_uls_M_pos": st.session_state.get("uls_Mstar_pos_manual"),
        "shared_uls_M_neg": st.session_state.get("uls_Mstar_neg_manual"),
        "shared_uls_V": st.session_state.get("uls_Vstar"),
        "resolved_M": actions.get("Mu"),
        "resolved_V": actions.get("Vu"),
    }
    _agent_debug_log(
        "Design action consistency check",
        payload,
        location="inputs_page.py:_debug_check_design_action_consistency",
        hypothesis_id="H51",
    )


def _refresh_canonical_shear_widgets(*, source: str) -> None:
    _request_shear_widget_seed_from_shared(source)


def _queue_inputs_refresh(source: str, keys: list[str], *, focus_section: str | None = None) -> None:
    """
    Schedule one forced Inputs widget reconciliation on the next render_inputs (via pop + hydrate).
    Clears _force_inputs_widget_reseed_once: pending apply-refresh subsumes the same recovery intent
    so router + one forced pass do not compete with a separate reseed flag.
    """
    try:
        import session_state_final_log as _ssl

        _ssl.append_session_state_final_log(
            "queue_inputs_refresh",
            {
                "source": source,
                "keys": list(keys)[:48],
                "had_reseed_before_pop": bool(st.session_state.get("_force_inputs_widget_reseed_once")),
            },
        )
        _ssl.ssl_increment("queue_inputs_refresh_count", 1)
    except Exception:
        pass
    st.session_state.pop("_force_inputs_widget_reseed_once", None)
    next_focus_map = {
        "fast_mode:geometry_recommendation": "model",
        "fast_mode:bottom_recommendation": "shear",
    }
    next_focus_section = focus_section or next_focus_map.get(source)
    if next_focus_section:
        st.session_state["_fast_mode_focus_section"] = next_focus_section
    if str(source).startswith("guidance:"):
        st.session_state["_design_guide_banner_generic_only"] = True
    st.session_state["_pending_inputs_apply_refresh"] = {
        "source": source,
        "keys": keys,
    }
    _inputs_hydration_trace_log("queue_inputs_refresh", source=source, keys=list(keys)[:24])

# Mechanical extraction: recommendation compute provider helper family.
_ACTIVE_GUIDANCE_RANK_TRACE: list[dict] | None = None


def _merge_design_guide_rank_trace(entry: dict) -> None:
    if not entry:
        return
    global _ACTIVE_GUIDANCE_RANK_TRACE
    if _ACTIVE_GUIDANCE_RANK_TRACE is not None:
        _ACTIVE_GUIDANCE_RANK_TRACE.append(dict(entry))


REO_COUNTS_0_12 = list(range(0, 13))


GUIDANCE_INEFFICIENT_UTIL_THRESHOLD = 0.75


GUIDANCE_SHALLOW_GEOMETRY_SCORE_TIE_EPS = 24.0


GUIDANCE_COMPOUND_VS_PURE_GEOMETRY_SCORE_MARGIN = 28.0


AUTO_DESIGN_MAX_KEPT_RESULTS = 5


AUTO_DESIGN_MAX_TOTAL_UNIQUE_EVALS = 100


def _mode_target_midpoint(mode_config: dict) -> float:
    target_lo, target_hi, _ = _resolved_efficiency_target_band(mode_config, goal=_design_optimisation_goal())
    return (float(target_lo) + float(target_hi)) / 2.0


def _top_reo_state_label(state: dict) -> str:
    mode_1 = str(state.get("top1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("top2_layout_mode", "Count") or "Count")
    count_1 = int(state.get("top1_count", 0) or 0)
    count_2 = int(state.get("top2_count", 0) or 0)
    if mode_1 == "Count" and mode_2 == "Count":
        dia = int(state.get("db_top_1", state.get("db_top", 0)) or 0)
        if count_1 > 0 or count_2 > 0:
            return _practical_bottom_reo_label(count_1, count_2, dia)
        return "None"
    spacing_1 = float(state.get("top1_spacing", 0.0) or 0.0)
    dia_1 = int(state.get("db_top_1", 0) or 0)
    return f"N{dia_1} @ {int(spacing_1)}"


def _guidance_shear_links_banner_fragment(state: dict) -> str | None:
    legs = int(state.get("lig_legs", 0) or 0)
    if legs <= 0:
        return None
    return f"N{int(state.get('lig_d', 0) or 0)}, {legs}-leg @{int(float(state.get('s_lig', 0.0) or 0.0))}"


def _guidance_apply_change_lines(before: dict, after: dict) -> list[str]:
    lines: list[str] = []
    _, _, bw = _resolve_geometry_width_context(before)
    _, _, aw = _resolve_geometry_width_context(after)
    try:
        if abs(float(aw) - float(bw)) > 1e-6:
            lines.append(f"Width: {int(round(float(bw)))} → {int(round(float(aw)))} mm")
    except (TypeError, ValueError):
        pass
    try:
        b_d = float(_float_from_state(before, "D", 0.0))
        a_d = float(_float_from_state(after, "D", 0.0))
        if abs(a_d - b_d) > 1e-6:
            lines.append(f"Depth: {int(round(b_d))} → {int(round(a_d))} mm")
    except (TypeError, ValueError):
        pass
    bl = _bottom_reo_state_label(before)
    al = _bottom_reo_state_label(after)
    bot_phrase, top_phrase = main_longitudinal_reo_change_line_prefixes(after)
    if bl != al:
        lines.append(f"{bot_phrase}: {bl} → {al}")
    tl_b = _top_reo_state_label(before)
    tl_a = _top_reo_state_label(after)
    if tl_b != tl_a:
        lines.append(f"{top_phrase}: {tl_b} → {tl_a}")
    bf = _guidance_shear_links_banner_fragment(before)
    af = _guidance_shear_links_banner_fragment(after)
    if bf != af:
        if af is None:
            lines.append(f"Shear links: {bf} → removed")
        elif bf is None:
            lines.append(f"Shear links: none → {af}")
        else:
            lines.append(f"Shear links: {bf} → {af}")
    return lines


def _guidance_change_lines_for_updates(before: dict, updates: dict | None) -> list[str]:
    if not updates:
        return []
    after = dict(before)
    after.update(updates)
    return _guidance_apply_change_lines(before, after)


def _candidate_debug_summary(candidate: dict | None) -> dict | None:
    if not candidate:
        return None
    candidate_state = dict(candidate.get("state") or {})
    overview = dict(candidate.get("overview") or {})
    bending_pack = ((overview.get("packs") or {}).get("bending") or {})
    summary = {
        "label": str(candidate.get("label") or ""),
        "bottom_reo_label": _bottom_reo_state_label(candidate_state) if candidate_state else "",
        "b": float(_design_width_value(candidate_state) if candidate_state else 0.0),
        "D": float(candidate.get("depth", _float_from_state(candidate_state, "D", 0.0)) if candidate_state else 0.0),
        "bot1_count": int(candidate_state.get("bot1_count", 0) or 0),
        "bot2_count": int(candidate_state.get("bot2_count", 0) or 0),
        "db_bot_1": int(candidate_state.get("db_bot_1", candidate_state.get("db_bot", 0)) or 0),
        "db_bot_2": int(candidate_state.get("db_bot_2", candidate_state.get("db_bot_1", candidate_state.get("db_bot", 0))) or 0),
        "bars": int(candidate_state.get("bot1_count", 0) or 0) + int(candidate_state.get("bot2_count", 0) or 0),
        "dia": int(candidate_state.get("db_bot_1", candidate_state.get("db_bot", 0)) or 0),
        "Ast_bot": float(candidate.get("Ast_bot", 0.0) or 0.0),
        "summary_phiMu_kNm": float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0),
        "summary_Mu_star_kNm": float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0),
        "bending_util": None,
        "worst_util": float(candidate.get("worst_util", 0.0) or 0.0),
        "real_util": None,
        "optimisation_score": float(_candidate_objective_util(candidate)),
        "score": None if candidate.get("score") is None else float(candidate.get("score", 0.0) or 0.0),
        "pass": bool(candidate.get("is_compliant")),
        "source": str(candidate.get("source") or ""),
        "ductility_util": _candidate_ductility_util(candidate),
        "ductility_pass": None,
        "ductility_tier": int(candidate.get("_ductility_tier", 0) or 0),
        "ductility_tier_label": str(candidate.get("_ductility_tier_label") or ""),
        "reason_selected": str(candidate.get("_ductility_reason") or ""),
    }
    try:
        bending_util = ((overview.get("utils") or {}).get("bending"))
        summary["bending_util"] = None if bending_util is None else float(bending_util)
    except Exception:
        summary["bending_util"] = None
    phi_m = float(summary["summary_phiMu_kNm"] or 0.0)
    mu_m = float(summary["summary_Mu_star_kNm"] or 0.0)
    summary["real_util"] = (mu_m / phi_m) if phi_m > 1e-9 else None
    if summary["ductility_util"] is not None:
        summary["ductility_pass"] = bool(float(summary["ductility_util"]) <= 1.0)
    return summary


def _uls_action_from_state(state: dict, action: str) -> float:
    resolved_actions = _resolve_design_actions_from_state(state)
    resolved_map = {
        "M": "Mu",
        "V": "Vu",
        "N": "Nu",
        "T": "Tu",
        "P": "Pu",
    }
    resolved_key = resolved_map.get(action)
    if resolved_key is not None:
        mapped = resolved_actions.get(resolved_key)
        if mapped is not None:
            return float(mapped)

    shared_map = {
        "M": "uls_Mstar",
        "V": "uls_Vstar",
        "N": "uls_Nstar",
    }
    if action in shared_map:
        return _float_from_state(state, shared_map[action], 0.0)
    if action == "T":
        return _float_from_state(state, "Tu_star", 0.0)
    if action == "P":
        return _float_from_state(state, "P_star", 0.0)
    return 0.0


def _state_with_resolved_design_actions(state: dict, actions: dict | None = None) -> dict:
    resolved = _guidance_state_snapshot(state)
    actions = dict(actions or _resolve_design_actions_from_state(resolved))
    resolved["uls_Mstar"] = float(actions.get("Mu", _float_from_state(resolved, "uls_Mstar", 0.0)) or 0.0)
    resolved["uls_Vstar"] = float(actions.get("Vu", _float_from_state(resolved, "uls_Vstar", 0.0)) or 0.0)
    resolved["uls_Nstar"] = float(actions.get("Nu", _float_from_state(resolved, "uls_Nstar", 0.0)) or 0.0)
    resolved["Mu_star"] = float(actions.get("Mu", _float_from_state(resolved, "Mu_star", 0.0)) or 0.0)
    resolved["Vu_star"] = float(actions.get("Vu", _float_from_state(resolved, "Vu_star", 0.0)) or 0.0)
    resolved["N_star"] = float(actions.get("Nu", _float_from_state(resolved, "N_star", 0.0)) or 0.0)
    resolved["sls_Mstar"] = float(actions.get("SLS_M", _float_from_state(resolved, "sls_Mstar", 0.0)) or 0.0)
    resolved["uls_Mstar_pos_manual"] = float(
        _float_from_state(
            resolved,
            "uls_Mstar_pos_manual",
            max(0.0, _float_from_state(resolved, "uls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["uls_Mstar_neg_manual"] = float(
        _float_from_state(
            resolved,
            "uls_Mstar_neg_manual",
            max(0.0, -_float_from_state(resolved, "uls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Mstar_pos_manual"] = float(
        _float_from_state(
            resolved,
            "sls_Mstar_pos_manual",
            max(0.0, _float_from_state(resolved, "sls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Mstar_neg_manual"] = float(
        _float_from_state(
            resolved,
            "sls_Mstar_neg_manual",
            max(0.0, -_float_from_state(resolved, "sls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Vstar"] = float(actions.get("SLS_V", _float_from_state(resolved, "sls_Vstar", 0.0)) or 0.0)
    resolved["Tu_star"] = float(actions.get("Tu", _float_from_state(resolved, "Tu_star", 0.0)) or 0.0)
    resolved["P_star"] = float(actions.get("Pu", _float_from_state(resolved, "P_star", 0.0)) or 0.0)
    resolved["actions_uls"] = {
        "M": resolved["uls_Mstar"],
        "V": resolved["uls_Vstar"],
        "N": resolved["uls_Nstar"],
        "T": resolved["Tu_star"],
        "P": resolved["P_star"],
    }
    return resolved


def _state_with_resolved_auto_design_actions(state: dict, actions: dict | None) -> dict:
    return _state_with_resolved_design_actions(state, actions)


def _shear_results_allow_no_transverse_links(res, *, phi: float) -> bool:
    """
    True only if the member may omit closed shear links: no torsion design, concrete carries V*,
    and factored shear is low enough that minimum shear reinforcement is not mandatory
    (V* <= 0.5 φ Vuc per typical AS 3600 detailing practice).
    """
    if res is None:
        return False
    if bool(getattr(res, "torsion_required", True)):
        return False
    if not bool(getattr(res, "shear_ok", False)):
        return False
    veq = float(getattr(res, "V_eq", 0.0) or 0.0)
    vuc = float(getattr(res, "Vuc_kN", 0.0) or 0.0)
    phi_f = float(phi)
    if vuc <= 1e-12:
        return abs(veq) <= 1e-6
    if veq > 0.5 * phi_f * vuc + 1e-6:
        return False
    return True


def _shear_no_links_candidate_passes_code(state: dict, candidate: dict | None) -> bool:
    """Re-validate zero-link candidate after full fast eval (torsion, strength, min-shear gate)."""
    if not candidate:
        return False
    cs = dict(candidate.get("state") or {})
    if _int_from_state(cs, "lig_legs", -1) != 0:
        return True
    s_nom = float(max(_float_from_state(cs, "s_lig", 1.0), 1.0))
    preview = _evaluate_shear_with_state(
        cs,
        shear_updates={"lig_legs": 0, "lig_d": 0, "s_lig": s_nom},
    )
    if not preview:
        return False
    res = preview.get("results")
    phi = _float_from_state(state, "phi_shear", 0.75)
    return _shear_results_allow_no_transverse_links(res, phi=phi)


def _shear_link_state_is_canonical(state: dict | None) -> bool:
    if not isinstance(state, dict):
        return False
    legs = _int_from_state(state, "lig_legs", 0)
    dia = _int_from_state(state, "lig_d", 0)
    s = _float_from_state(state, "s_lig", 0.0)
    canonical_s = float(CANONICAL_NO_SHEAR_SLIG_MM)
    if _shear_reinforcement_is_active(state):
        return legs >= 2 and dia > 0 and s > 0.0
    return legs <= 0 and dia <= 0 and abs(float(s) - canonical_s) <= 1e-6


def _shear_link_state_mode_label(state: dict | None) -> str:
    if not isinstance(state, dict):
        return "unknown"
    if _shear_reinforcement_is_active(state):
        return "active_canonical" if _shear_link_state_is_canonical(state) else "active_non_canonical"
    return "inactive_canonical" if _shear_link_state_is_canonical(state) else "inactive_non_canonical"


def _initialise_shear_link_optimisation_debug() -> dict:
    return {
        "shear_link_state_mode": None,
        "shear_link_state_is_canonical": False,
        "shear_no_links_truth_active": False,
        "shear_active_links_truth_active": False,
        "shear_spacing_candidate_seen": False,
        "shear_spacing_candidate_dropped_reason": None,
        "shear_spacing_candidate_materiality": "not_evaluated",
        "shear_underdesign_activation_candidate_seen": False,
        "shear_underdesign_activation_candidate_committed": False,
        "shear_overdesign_remove_links_candidate_seen": False,
        "shear_overdesign_remove_links_candidate_committed": False,
        # True only when the chosen best move is increase_link_spacing (not leg/dia density wins).
        "shear_overdesign_spacing_candidate_committed": False,
        # True when the density-reduction loop returns any committed tightening (spacing, legs, or dia via that path).
        "shear_overdesign_density_reduction_candidate_committed": False,
        "shear_tightening_terminal_reason": None,
        "shear_overdesign_truth_util": None,
        "shear_overdesign_truth_status": None,
        "shear_overdesign_truth_governing_check": None,
        "shear_cleanup_blocked_due_to_truth_near_limit": False,
        "shear_candidate_family_pure": None,
        "shear_candidate_non_detailing_updates_detected": None,
        "shear_candidate_rejected_reason": None,
        "combined_underdesign_shear_truth_block_active": False,
        "combined_underdesign_shear_truth_block_reason": None,
        "combined_underdesign_shear_strengthening_suppressed": False,
        "combined_underdesign_truth_gate_source": None,
        "combined_underdesign_truth_gate_classification": None,
        "combined_underdesign_truth_gate_all_key_pass": None,
        "combined_underdesign_truth_gate_final_shear_truth_resolved": None,
    }


def _annotate_shear_link_state_debug_from_state(state: dict, dbg: dict) -> None:
    snap = _guidance_state_snapshot(state)
    for _k, _v in _initialise_shear_link_optimisation_debug().items():
        dbg.setdefault(_k, _v)
    dbg["shear_link_state_mode"] = _shear_link_state_mode_label(snap)
    dbg["shear_link_state_is_canonical"] = bool(_shear_link_state_is_canonical(snap))
    dbg["shear_no_links_truth_active"] = bool(_shear_state_eligible_for_no_links(snap))
    dbg["shear_active_links_truth_active"] = bool(_shear_reinforcement_is_active(snap))


def _try_shear_canonical_inactive_fixup_recommendation(state: dict) -> dict | None:
    """Scheduling-only: snap to canonical no-links storage when transverse steel is inactive."""
    # Mixed inactive non-canonical storage (e.g. wrong s_lig) is fixed here first; underdesign
    # activation may require a second pass after this canonical fixup returns and state is reapplied.
    if _shear_reinforcement_is_active(state):
        return None
    if _shear_link_state_is_canonical(state):
        return None
    updates = {
        "lig_legs": 0,
        "lig_d": 0,
        "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
    }
    if _updates_match_state(state, updates):
        return None
    trial_state = dict(state)
    trial_state.update(updates)
    cand = evaluate_candidate_full(
        _guidance_state_snapshot(trial_state),
        source="guidance_shear_canonical_inactive_fixup",
        updates=updates,
    )
    if not cand or not bool(cand.get("is_compliant")):
        return None
    preview = _shear_preview_for_updates(state, updates) or {}
    return {
        "updates": dict(updates),
        "label": f"Canonical no-links spacing ({int(CANONICAL_NO_SHEAR_SLIG_MM)} mm)",
        "util": float(((cand.get("overview") or {}).get("utils") or {}).get("shear", 0.0) or 0.0),
        "web_util": float(preview.get("web_util", 0.0) or 0.0),
        "action_type": "apply_shear_recommendation",
        "score": 0.0,
        "candidate_type": "shear_link_state_canonicalisation",
    }


def _try_shear_remove_links_tightening_recommendation(
    state: dict,
    overview: dict,
    dbg: dict | None = None,
) -> dict | None:
    """Overdesign: valid no-links waiver → canonical inactive links before spacing/leg trials."""
    if not _shear_reinforcement_is_active(state):
        return None
    if not _shear_state_eligible_for_no_links(state):
        return None
    if dbg is not None:
        dbg["shear_overdesign_remove_links_candidate_seen"] = True
    updates = {
        "lig_legs": 0,
        "lig_d": 0,
        "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
    }
    if _updates_match_state(state, updates):
        return None
    trial_state = dict(state)
    trial_state.update(updates)
    cand = evaluate_candidate_full(
        _guidance_state_snapshot(trial_state),
        source="guidance_shear_remove_links_tighten",
        updates=updates,
    )
    if not cand or not bool(cand.get("is_compliant")):
        return None
    if not _shear_no_links_candidate_passes_code(state, cand):
        return None
    preview = _shear_preview_for_updates(state, updates) or {}
    return {
        "updates": dict(updates),
        "label": "Remove shear links (code-allowed no-links case)",
        "util": float(((cand.get("overview") or {}).get("utils") or {}).get("shear", 0.0) or 0.0),
        "web_util": float(preview.get("web_util", 0.0) or 0.0),
        "action_type": "apply_shear_recommendation",
        "score": 0.0,
        "candidate_type": "shear",
    }


def _try_shear_activation_for_underdesign_recommendation(
    state: dict,
    overview: dict,
    actions: dict,
) -> dict | None:
    """Underdesign: inactive links but links required → canonical starter activation."""
    if _shear_reinforcement_is_active(state):
        return None
    if _shear_demands_negligible(actions):
        return None
    if _shear_state_eligible_for_no_links(state):
        return None
    if _shear_spacing_layout_must_not_trigger_strengthening(state, overview):
        return None
    st_sh = str(((overview or {}).get("statuses") or {}).get("shear") or "").strip().upper()
    if st_sh not in {"FAIL", "NEAR LIMIT"}:
        return None
    raw = {
        "lig_legs": 2,
        "lig_d": int(_starter_shear_diameter(state)),
        "s_lig": float(_starter_shear_spacing(state)),
    }
    updates = dict(_normalise_invalid_shear_state_updates(state, raw, source="shear_activation_underdesign"))
    if _updates_match_state(state, updates):
        return None
    trial_state = dict(state)
    trial_state.update(updates)
    cand = evaluate_candidate_full(
        _guidance_state_snapshot(trial_state),
        source="guidance_shear_activation_underdesign",
        updates=updates,
    )
    if not cand or not bool(cand.get("is_compliant")):
        return None
    preview = _shear_preview_for_updates(state, updates) or {}
    return {
        "updates": dict(updates),
        "label": f"Activate shear links ({_shear_state_label(trial_state)})",
        "util": float(((cand.get("overview") or {}).get("utils") or {}).get("shear", 0.0) or 0.0),
        "web_util": float(preview.get("web_util", 0.0) or 0.0),
        "action_type": "apply_shear_recommendation",
        "score": 0.0,
        "candidate_type": "shear",
    }


def _effective_bottom_spacing(state: dict, bottom_updates: dict | None = None) -> float:
    from section_layout import compute_bar_layout_pure

    if bottom_updates:
        count_1 = int(bottom_updates.get("bot1_count", 0) or 0)
        dia = float(bottom_updates.get("db_bot_1", 0.0) or 0.0)
    else:
        count_1 = _int_from_state(state, "bot1_count", _int_from_state(state, "nb_bot", 0))
        dia = _float_from_state(state, "db_bot_1", _float_from_state(state, "db_bot", 0.0))
    if count_1 <= 1 or dia <= 0.0:
        return _float_from_state(state, "s_bot", 0.0)
    layout = compute_bar_layout_pure(
        b=_design_width_value(state),
        cover_side=_float_from_state(state, "cover_side", 40.0),
        nb_or_s=float(count_1),
        db=float(dia),
        s_min=max(float(dia), 25.0),
        rowgap=_float_from_state(state, "rowgap_bot", 60.0),
    )
    return float(layout.get("s_actual", _float_from_state(state, "s_bot", 0.0)) or 0.0)


def _compute_sls_outer_steel_stress_with_state(state: dict, *, bottom_updates: dict | None = None) -> float | None:
    bottom_state = _effective_bottom_design_state(state, bottom_updates)
    b = _design_width_value(state)
    D = _float_from_state(state, "D", 600.0)
    d = float(bottom_state.get("d_centroid", 0.0) or 0.0)
    Ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Es = _float_from_state(state, "Es", 200000.0)
    Ms = _float_from_state(state, "sls_Mstar", _float_from_state(state, "uls_Mstar", 0.0))
    if not (b > 0.0 and D > 0.0 and d > 0.0 and Ast > 0.0 and Ec > 0.0 and Es > 0.0):
        return None
    n_as = (Es / Ec) * Ast
    if n_as <= 0.0:
        return None
    a_coeff = b / 2.0
    b_coeff = n_as
    c_coeff = -n_as * d
    discriminant = b_coeff**2 - 4.0 * a_coeff * c_coeff
    if discriminant >= 0.0 and a_coeff > 0.0:
        dn_sls = (-b_coeff + math.sqrt(discriminant)) / (2.0 * a_coeff)
        dn_sls = max(1.0, min(dn_sls, D))
    else:
        dn_sls = d / 2.0
    i_cr = (b * dn_sls**3 / 3.0) + n_as * (d - dn_sls) ** 2
    if i_cr <= 0.0:
        return None
    kappa = (Ms * 1e6) / (Ec * i_cr)
    return float(Es * kappa * (d - dn_sls))


def _evaluate_crack_with_state(state: dict, *, bottom_updates: dict | None = None) -> dict | None:
    from crack_page import table_sigma_max_A, table_sigma_max_B, calc_eps_diff, calc_sr_max

    bottom_state = _effective_bottom_design_state(state, bottom_updates)
    sigma_sr = _compute_sls_outer_steel_stress_with_state(state, bottom_updates=bottom_updates)
    bar_diameter = float(bottom_state.get("db_bot", 0.0) or 0.0)
    ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    b = _float_from_state(state, "b_crack", _design_width_value(state))
    D = _float_from_state(state, "D", 600.0)
    cover_bot = _float_from_state(state, "cover_bot", 40.0)
    spacing = _effective_bottom_spacing(state, bottom_updates=bottom_updates)
    fc = _float_from_state(state, "fc", 32.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Es = _float_from_state(state, "Es", 200000.0)
    fsy = _float_from_state(state, "fsy", 500.0)
    phi_ce = _float_from_state(state, "phi_cc_t", 2.0)
    eps_cs = _float_from_state(state, "eps_cs_total_micro", 300.0) * 1e-6
    wmax_choice = _float_from_state(state, "wmax_char_limit", 0.3)
    member_type = str(state.get("crack_member_type", "Primarily flexure") or "Primarily flexure")
    k1 = _float_from_state(state, "crack_k1", 0.8)
    k2 = _float_from_state(state, "crk_k2", _float_from_state(state, "crack_k2", 0.5))
    if sigma_sr is None or bar_diameter <= 0.0 or ast <= 0.0 or b <= 0.0 or D <= 0.0 or wmax_choice <= 0.0:
        return None
    lig_diameter = _float_from_state(state, "lig_d", 10.0)
    d_eff = effective_depth_with_links_mm(
        D_mm=D,
        cover_to_ligs_mm=cover_bot,
        lig_diameter_mm=lig_diameter,
        bar_diameter_mm=bar_diameter,
    )
    height_eff = min(2.5 * cover_bot, max(D - d_eff, 0.0), D / 2.0)
    a_ceff = b * max(height_eff, 1.0)
    rho_eff = ast / a_ceff if a_ceff > 0.0 else 0.0
    sigma_table_a = table_sigma_max_A(bar_diameter, wmax_choice)
    sigma_table_b = table_sigma_max_B(max(spacing, 1.0), wmax_choice)
    sigma_table_combined = sigma_table_a if member_type == "Primarily tension" else max(sigma_table_a, sigma_table_b)
    sigma_allow_table = min(sigma_table_combined, 0.8 * fsy)
    util_table = sigma_sr / sigma_allow_table if sigma_allow_table > 0.0 else 0.0
    fct_eff = 0.6 * math.sqrt(max(fc, 1.0))
    n_e = (1.0 + phi_ce) * Es / Ec if Ec > 0.0 else 0.0
    eps_diff = calc_eps_diff(
        sigma_sr=sigma_sr,
        Es=Es,
        fct_eff=fct_eff,
        rho_eff=rho_eff,
        ne=n_e,
        eps_cs=eps_cs,
    )
    sr_max = calc_sr_max(c_mm=cover_bot, db_mm=bar_diameter, rho_eff=rho_eff, k1=k1, k2=k2)
    w_calc = sr_max * eps_diff
    util_w = w_calc / wmax_choice if wmax_choice > 0.0 else 0.0
    util = max(util_table, util_w)
    return {
        "sigma_sr": float(sigma_sr),
        "sigma_allow_table": float(sigma_allow_table),
        "w_calc": float(w_calc),
        "util": float(util),
        "passes": bool(util <= 1.0),
    }


def _evaluate_deflection_with_state(state: dict, *, bottom_updates: dict | None = None) -> dict | None:
    _bind_deflection_evaluation_dependencies(globals())
    return _evaluate_deflection_with_state_extracted(state, bottom_updates=bottom_updates)


def _normalise_bottom_layer_order(arrangement: dict) -> dict:
    normalised = dict(arrangement)
    bot1_count = int(normalised.get("bot1_count", 0) or 0)
    bot2_count = int(normalised.get("bot2_count", 0) or 0)
    db1 = int(normalised.get("db_bot_1", 0) or 0)
    db2 = int(normalised.get("db_bot_2", 0) or 0)

    layer2_is_preferred = False
    if db2 > db1:
        layer2_is_preferred = True
    elif db2 == db1 and bot2_count > bot1_count:
        layer2_is_preferred = True

    if layer2_is_preferred:
        normalised["bot1_layout_mode"], normalised["bot2_layout_mode"] = (
            normalised.get("bot2_layout_mode", "Count"),
            normalised.get("bot1_layout_mode", "Count"),
        )
        normalised["bot1_count"], normalised["bot2_count"] = bot2_count, bot1_count
        normalised["db_bot_1"], normalised["db_bot_2"] = db2, db1
    return normalised


def _required_ast_for_arrangement(state: dict, arrangement: dict) -> float:
    from bending_core import _get_compute_bending_capacity_pure

    b = _design_width_value(state)
    D = _float_from_state(state, "D", 600.0)
    fc = _float_from_state(state, "fc", 40.0)
    fsy = _float_from_state(state, "fsy", 500.0)
    phi = _float_from_state(state, "phi_bend", 0.85)
    Mu_star = _uls_action_from_state(state, "M")
    cover_bot = _float_from_state(state, "cover_bot", 40.0)
    rowgap_bot = _float_from_state(state, "rowgap_bot", 60.0)

    compute_fn = _get_compute_bending_capacity_pure()
    low = 0.0
    high = float(arrangement["Ast_bot"])
    for _ in range(40):
        trial = 0.5 * (low + high)
        trial_results = compute_fn(
            b=b,
            D=D,
            fc=fc,
            fsy=fsy,
            Ast=trial,
            Mu_star=Mu_star,
            phi=phi,
            d_input=arrangement["d_centroid"],
            cover_bot=cover_bot,
            db_bot=arrangement["db_bot"],
            nb_bot=arrangement["nb_bot"],
            rowgap_bot=rowgap_bot,
        )
        util = float(trial_results.get("Mu_util", float("inf")))
        if util <= 1.0:
            high = trial
        else:
            low = trial
    return float(high)


def is_valid_reo_layout(n_bars, db, beam_width, cover, s_min):
    available = beam_width - 2 * cover
    required = n_bars * db + (n_bars - 1) * s_min

    if n_bars < 2:
        return False

    if required > available:
        return False

    return True


def _bottom_row_count_from_state(state: dict) -> int:
    explicit = _int_from_state(state, "bot_row_count", 0)
    if explicit > 0:
        return explicit
    return 2 if _int_from_state(state, "bot2_count", 0) > 0 else 1


def _bottom_bar_count_from_state(state: dict, bottom_state: dict | None = None) -> int:
    resolved = bottom_state or _effective_bottom_design_state(state)
    count = int(resolved.get("nb_bot", 0) or 0)
    if count > 0:
        return count
    return _int_from_state(state, "bot1_count", 0) + _int_from_state(state, "bot2_count", 0)


def _reo_congestion_index(state: dict, bottom_state: dict | None = None) -> float:
    resolved = bottom_state or _effective_bottom_design_state(state)
    total_bars = _bottom_bar_count_from_state(state, resolved)
    row_count = max(_bottom_row_count_from_state(state), 1)
    bar_dia = float(resolved.get("db_bot", 0.0) or _float_from_state(state, "db_bot_1", 0.0))
    width = max(_design_width_value(state), 1.0)
    rows_penalty = max(row_count - 1, 0) * 2.5
    density_penalty = (total_bars * max(bar_dia, 1.0)) / width
    return float(total_bars + rows_penalty + density_penalty)


def _status_from_candidate_util(util: float | None) -> str:
    if util is None or (isinstance(util, float) and math.isnan(util)):
        return "—"
    if util <= 1.0:
        return "NEAR LIMIT" if util >= 0.95 else "PASS"
    return "FAIL"


def _candidate_bottom_updates(candidate_state: dict) -> dict | None:
    db_1 = _int_from_state(candidate_state, "db_bot_1", 0)
    count_1 = _int_from_state(candidate_state, "bot1_count", 0)
    count_2 = _int_from_state(candidate_state, "bot2_count", 0)
    if db_1 <= 0 or (count_1 + count_2) <= 0:
        return None
    return {
        "db_bot_1": db_1,
        "db_bot_2": _int_from_state(candidate_state, "db_bot_2", db_1),
        "bot1_count": count_1,
        "bot2_count": count_2,
    }


def _candidate_shear_updates(candidate_state: dict) -> dict:
    return {
        "lig_d": _int_from_state(candidate_state, "lig_d", 10),
        "lig_legs": _int_from_state(candidate_state, "lig_legs", 2),
        "s_lig": _float_from_state(candidate_state, "s_lig", 200.0),
    }


def _activation_shear_state(state: dict) -> dict:
    activated = dict(state)
    activated.update({
        "lig_legs": 2,
        "lig_d": int(_starter_shear_diameter(state)),
        "s_lig": float(_starter_shear_spacing(state)),
    })
    return activated


def _candidate_bending_reserve_util(candidate: dict | None) -> float | None:
    if not candidate:
        return None
    util = _candidate_bending_demand_util(candidate)
    if util is not None:
        return float(util)
    raw = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
    if raw is None:
        return None
    try:
        value = float(raw)
    except Exception:
        return None
    return None if math.isnan(value) else value


def _secondary_action_reserves(candidate: dict | None) -> dict:
    reserves: dict[str, dict] = {}
    bending_util = _candidate_bending_reserve_util(candidate)
    if bending_util is not None and bending_util <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD:
        reserves["bending"] = {
            "util": bending_util,
            "bottom_reo": _bottom_reo_state_label(dict((candidate or {}).get("state") or {})),
            "phiMu": (((candidate or {}).get("overview") or {}).get("packs") or {}).get("bending", {}).get("summary_phiMu_kNm"),
            "Mu_star": (((candidate or {}).get("overview") or {}).get("packs") or {}).get("bending", {}).get("summary_Mu_star_kNm"),
        }
    return reserves


def _generate_secondary_bending_tightening_states(base_candidate: dict, *, limit: int = 3) -> list[dict]:
    bending_util = _candidate_bending_reserve_util(base_candidate)
    if bending_util is None or bending_util > GUIDANCE_INEFFICIENT_UTIL_THRESHOLD:
        return []
    base_state = dict(base_candidate.get("state") or {})
    if not base_state:
        return []
    current_ast = float(base_candidate.get("Ast_bot", 0.0) or 0.0)
    low_reo_mode = _design_mode_config("less_longitudinal_reinforcement")
    context = _build_auto_design_context(
        base_state,
        low_reo_mode,
        reference_overview=base_candidate.get("overview"),
    )
    states: dict[tuple, dict] = {}
    raw_limit = max(limit * 2, 6)
    for band in range(2):
        for arrangement in _generate_local_bottom_arrangements(
            base_state,
            low_reo_mode,
            band=band,
            context=context,
            limit=raw_limit,
        ):
            candidate_state = dict(base_state)
            candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
            preview_bottom = _effective_bottom_design_state(candidate_state, _candidate_bottom_updates(candidate_state))
            if float(preview_bottom.get("Ast_bot", 0.0) or 0.0) >= current_ast - 1e-6:
                continue
            states[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    ordered_states = sorted(
        states.values(),
        key=lambda item: (
            abs(float((_evaluate_bending_with_bottom_state(item, _candidate_bottom_updates(item)) or {}).get("Mu_util", 999.0) or 999.0) - 0.85),
            float(_effective_bottom_design_state(item, _candidate_bottom_updates(item)).get("Ast_bot", 0.0) or 0.0),
        ),
    )
    return ordered_states[:limit]


def _shear_family_label(candidate_type: str, candidate: dict | None, *, seed_candidate: dict | None = None) -> str:
    mapping = {
        "spacing": "spacing tighter",
        "more legs": "more legs",
        "larger dia": "larger link dia",
        "width increase": "width increase",
        "depth increase": "depth increase",
        "combined": "combined geometry + stronger shear",
    }
    label = mapping.get(str(candidate_type or ""), str(candidate_type or "spacing tighter"))
    if str(candidate_type or "") == "combined" and candidate and seed_candidate:
        candidate_state = dict(candidate.get("state") or {})
        seed_state = dict(seed_candidate.get("state") or {})
        candidate_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
        seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
        width_key, _, seed_width = _resolve_geometry_width_context(seed_state)
        candidate_width = _float_from_state(candidate_state, width_key, seed_width)
        seed_depth = _float_from_state(seed_state, "D", 0.0)
        candidate_depth = _float_from_state(candidate_state, "D", seed_depth)
        if candidate_ast < seed_ast - 1e-6:
            if abs(candidate_width - seed_width) > 1e-9 or abs(candidate_depth - seed_depth) > 1e-9:
                label = "combined geometry + lighter bottom reo"
            else:
                label = "combined shear + lighter bottom reo"
    elif candidate and seed_candidate:
        candidate_state = dict(candidate.get("state") or {})
        seed_state = dict(seed_candidate.get("state") or {})
        width_key, _, seed_width = _resolve_geometry_width_context(seed_state)
        candidate_width = _float_from_state(candidate_state, width_key, seed_width)
        seed_depth = _float_from_state(seed_state, "D", 0.0)
        candidate_depth = _float_from_state(candidate_state, "D", seed_depth)
        candidate_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
        seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
        if (
            candidate_ast < seed_ast - 1e-6
            and (
                abs(candidate_width - seed_width) > 1e-9
                or abs(candidate_depth - seed_depth) > 1e-9
            )
        ):
            label = "combined geometry + lighter bottom reo"
    return label


def _log_severe_shear_escalation(
    *,
    source: str,
    seed_candidate: dict,
    severity_band: str,
    candidates: list[dict],
    selected: dict | None,
    family_audit: dict[str, list[dict]] | None = None,
) -> None:
    _bind_severe_shear_escalation_log_dependencies(globals())
    return _log_severe_shear_escalation_extracted(
        source=source,
        seed_candidate=seed_candidate,
        severity_band=severity_band,
        candidates=candidates,
        selected=selected,
        family_audit=family_audit,
    )


def _candidate_bending_demand_util(candidate: dict) -> float | None:
    """Mu* / φMu from bending pack (demand / flexural capacity), not ductility/min-steel util."""
    if not isinstance(candidate, dict):
        return None
    ov = candidate.get("overview") or {}
    bp = (ov.get("packs") or {}).get("bending") or {}
    phi = float(bp.get("summary_phiMu_kNm", 0.0) or 0.0)
    mu = float(bp.get("summary_Mu_star_kNm", 0.0) or 0.0)
    if phi <= 1e-9:
        return None
    return mu / phi


def _candidate_bending_component_util(candidate: dict, key: str) -> float | None:
    if not isinstance(candidate, dict):
        return None
    components = candidate.get("bending_components", {}) or {}
    raw = components.get(key)
    try:
        value = float(raw)
    except Exception:
        return None
    if math.isnan(value):
        return None
    return value


def _candidate_ductility_util(candidate: dict) -> float | None:
    return _candidate_bending_component_util(candidate, "ductility_util")


def _candidate_flexural_util(candidate: dict) -> float | None:
    return _candidate_bending_component_util(candidate, "flexural_util")


def _candidate_min_steel_util(candidate: dict) -> float | None:
    return _candidate_bending_component_util(candidate, "min_steel_util")


def _candidate_ductility_governs(candidate: dict | None) -> bool:
    if not isinstance(candidate, dict):
        return False
    ductility_util = _candidate_ductility_util(candidate)
    if ductility_util is None:
        return False
    governing = [
        value
        for value in (
            _candidate_flexural_util(candidate),
            _candidate_min_steel_util(candidate),
            ductility_util,
        )
        if value is not None
    ]
    if not governing:
        return False
    return ductility_util >= max(governing) - 1e-6 and ductility_util >= 0.85


def _ductility_governs_overview(overview: dict | None) -> bool:
    rows = (((overview or {}).get("packs") or {}).get("bending") or {}).get("rows") or []
    ductility_row = next((row for row in rows if str(row.get("title") or "") == "Ductility limit"), None)
    flexural_row = next((row for row in rows if str(row.get("title") or "") == "Flexural strength capacity"), None)
    ductility_util = _parse_util_value((ductility_row or {}).get("util"))
    flexural_util = _parse_util_value((flexural_row or {}).get("util"))
    if ductility_util is None:
        return False
    candidates = [value for value in (ductility_util, flexural_util) if value is not None]
    return bool(candidates) and ductility_util >= max(candidates) - 1e-6 and ductility_util >= 0.85


def _ductility_fix_tier(candidate: dict, reference_candidate: dict | None) -> int:
    if not isinstance(candidate, dict):
        return 4
    reference_candidate = reference_candidate or {}
    candidate_state = dict(candidate.get("state") or {})
    reference_state = dict(reference_candidate.get("state") or {})
    updates = dict(candidate.get("updates") or {})
    width_key, _, _ = _resolve_geometry_width_context(reference_state or candidate_state)
    bottom_keys = {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    }
    advanced_keys = {"Ast_top", "db_top", "nb_top", "top_row_count"}
    if any(key in updates for key in advanced_keys):
        return 4

    ref_width = _design_width_value(reference_state or candidate_state)
    ref_depth = float(reference_candidate.get("depth", _float_from_state(reference_state or candidate_state, "D", 0.0)) or _float_from_state(reference_state or candidate_state, "D", 0.0))
    cand_width = _design_width_value(candidate_state)
    cand_depth = float(candidate.get("depth", _float_from_state(candidate_state, "D", 0.0)) or _float_from_state(candidate_state, "D", 0.0))
    width_growth = cand_width > ref_width + 1e-6
    depth_growth = cand_depth > ref_depth + 1e-6
    ast_growth = float(candidate.get("Ast_bot", 0.0) or 0.0) > float(reference_candidate.get("Ast_bot", 0.0) or 0.0) + 1e-6

    if updates and set(updates).issubset(bottom_keys) and not ast_growth:
        return 1
    if width_growth and not depth_growth:
        return 2
    if depth_growth:
        return 3
    if not ast_growth:
        return 1
    if width_growth:
        return 2
    return 4


def _ductility_tier_label(tier: int) -> str:
    return {
        1: "Tier 1 steel-ratio reduction",
        2: "Tier 2 width",
        3: "Tier 3 depth",
        4: "Tier 4 advanced",
    }.get(int(tier), "Tier 4 advanced")


def _candidate_ductility_reason(candidate: dict, reference_candidate: dict | None) -> str:
    tier = _ductility_fix_tier(candidate, reference_candidate)
    if tier == 1:
        return "reduce bottom tensile ratio first"
    if tier == 2:
        return "prefer width before depth"
    if tier == 3:
        return "depth fallback after steel/width"
    return "advanced or mixed ductility fix"


def _shallower_beam_candidate_tier(candidate: dict) -> tuple[int, str]:
    candidate_state = dict(candidate.get("state") or {})
    seed_width = float(candidate.get("_seed_width", _design_width_value(candidate_state)) or _design_width_value(candidate_state))
    seed_depth = float(candidate.get("_seed_depth", _float_from_state(candidate_state, "D", 0.0)) or _float_from_state(candidate_state, "D", 0.0))
    candidate_width = float(candidate.get("width", _design_width_value(candidate_state)) or _design_width_value(candidate_state))
    candidate_depth = float(candidate.get("depth", _float_from_state(candidate_state, "D", 0.0)) or _float_from_state(candidate_state, "D", 0.0))
    width_increased = candidate_width > seed_width + 1e-9
    depth_increased = candidate_depth > seed_depth + 1e-9
    if not width_increased and not depth_increased:
        return 0, "local_or_detailing"
    if width_increased and not depth_increased:
        return 1, "width_before_depth"
    if width_increased and depth_increased:
        return 2, "width_plus_depth_fallback"
    return 3, "depth_fallback"


def _shallower_beam_metrics(candidate: dict, seed_candidate: dict) -> dict:
    candidate_state = dict(candidate.get("state") or {})
    seed_state = dict(seed_candidate.get("state") or {})
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 0.0)) or _float_from_state(seed_state, "D", 0.0))
    candidate_depth = float(candidate.get("depth", _float_from_state(candidate_state, "D", 0.0)) or _float_from_state(candidate_state, "D", 0.0))
    seed_width = float(seed_candidate.get("width", _design_width_value(seed_state)) or _design_width_value(seed_state))
    candidate_width = float(candidate.get("width", _design_width_value(candidate_state)) or _design_width_value(candidate_state))
    seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    candidate_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
    depth_reduction = max(seed_depth - candidate_depth, 0.0)
    width_growth = max(candidate_width - seed_width, 0.0)
    reinforcement_growth = max(candidate_ast - seed_ast, 0.0)
    shallowness_score = depth_reduction - (0.45 * width_growth) - (0.04 * reinforcement_growth)
    materially_shallower = depth_reduction >= 50.0 or (depth_reduction >= 25.0 and width_growth <= 50.0 and reinforcement_growth <= 120.0)
    return {
        "depth_reduction": depth_reduction,
        "width_growth": width_growth,
        "reinforcement_growth": reinforcement_growth,
        "shallowness_score": shallowness_score,
        "materially_shallower": materially_shallower,
    }


def _shallower_beam_selection_key(candidate: dict, seed_candidate: dict, mode_config: dict) -> tuple:
    seed_state = dict(seed_candidate.get("state") or {})
    cand_state = dict(candidate.get("state") or {})
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 0.0)) or _float_from_state(seed_state, "D", 0.0))
    cand_depth = float(candidate.get("depth", _float_from_state(cand_state, "D", 0.0)) or _float_from_state(cand_state, "D", 0.0))
    seed_width = float(seed_candidate.get("width", _design_width_value(seed_state)) or _design_width_value(seed_state))
    cand_width = float(candidate.get("width", _design_width_value(cand_state)) or _design_width_value(cand_state))
    seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    cand_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
    delta_d_mm = max(cand_depth - seed_depth, 0.0)
    delta_b_mm = max(cand_width - seed_width, 0.0)
    delta_ast_bot = max(cand_ast - seed_ast, 0.0)
    is_geometry = bool(candidate.get("recommendation_geometry_trial"))
    in_band = 0 if _candidate_in_target_band(candidate, mode_config) else 1
    congestion = float(candidate.get("reo_congestion_index", 0.0) or 0.0)
    return (
        0 if bool(candidate.get("is_compliant")) else 1,
        in_band,
        delta_d_mm,
        0 if not is_geometry else 1,
        delta_b_mm,
        delta_ast_bot,
        congestion,
        round(float(candidate.get("score", float("inf")) or float("inf")), 4),
        float(utilisation_gap(candidate, mode_config)),
        float(candidate.get("worst_util", float("inf")) or float("inf")),
    )


_SHEAR_DETAILING_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})


def _shear_detailing_updates_pure(updates: dict | None) -> tuple[bool, tuple[str, ...]]:
    if not isinstance(updates, dict) or not updates:
        return True, tuple()
    bad = tuple(sorted(k for k in updates if str(k) not in _SHEAR_DETAILING_UPDATE_KEYS))
    return (not bool(bad)), bad


def _shear_governing_truth_allows_overdesign_cleanup(shear_pack: dict | None) -> tuple[bool, dict]:
    """
    Gating for shear *overdesign / cleanup* scheduling only (not underdesign activation).
    Uses published shear-pack governing truth (summary_*), not sectional util fallbacks.
    """
    detail: dict = {
        "shear_overdesign_truth_util": None,
        "shear_overdesign_truth_status": None,
        "shear_overdesign_truth_governing_check": None,
        "shear_cleanup_blocked_due_to_truth_near_limit": False,
    }
    if not isinstance(shear_pack, dict):
        return True, detail
    raw_status = str(shear_pack.get("summary_governing_status") or "").strip().upper()
    util = _parse_util_value(shear_pack.get("summary_governing_util"))
    check = str(shear_pack.get("summary_governing_check_name") or "").strip()
    detail["shear_overdesign_truth_util"] = util
    detail["shear_overdesign_truth_status"] = raw_status or None
    detail["shear_overdesign_truth_governing_check"] = check or None
    if raw_status in {"FAIL", "FAILED"}:
        detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
        return False, detail
    if "NEAR" in raw_status or raw_status in ("WARN", "CHECK", "NEAR LIMIT"):
        detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
        return False, detail
    if util is not None:
        try:
            if float(util) >= float(GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD) - 1e-12:
                detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
                return False, detail
        except (TypeError, ValueError):
            pass
    return True, detail


def _reject_heavier_steel_lower_demand_util(current: dict, candidate: dict) -> bool:
    """More bottom steel but lower Mu*/phiMu is not an efficiency improvement."""
    ast0 = float(current.get("Ast_bot", 0.0) or 0.0)
    ast1 = float(candidate.get("Ast_bot", 0.0) or 0.0)
    if ast1 <= ast0 + 1e-6:
        return False
    u0 = _candidate_bending_demand_util(current)
    u1 = _candidate_bending_demand_util(candidate)
    if u0 is None or u1 is None:
        return False
    return u1 < u0 - 1e-9


def _candidate_objective_util(candidate: dict) -> float:
    """Score distance-to-target band: uses Mu*/phiMu (bending) when available, not ductility/min-steel."""
    state = candidate.get("state") if isinstance(candidate, dict) else {}
    goal = _design_optimisation_goal(state if isinstance(state, dict) else {})
    utils = candidate.get("overview", {}).get("utils", {}) if isinstance(candidate, dict) else {}
    target_domain = str((candidate.get("target_domain_for_band") if isinstance(candidate, dict) else "") or "").strip().lower()

    bend_du = _candidate_bending_demand_util(candidate) if isinstance(candidate, dict) else None

    if target_domain == "shear" or goal == "less_shear_reinforcement":
        objective_values = [utils.get("shear")]
    else:
        objective_values = [bend_du, utils.get("shear")]

    resolved_values: list[float] = []
    for value in objective_values:
        if value is None:
            continue
        try:
            resolved = float(value)
        except Exception:
            continue
        if not math.isnan(resolved):
            resolved_values.append(resolved)

    if resolved_values:
        return max(resolved_values)
    return float(candidate.get("worst_util", 0.0) or 0.0)


def _candidate_domain_util(candidate: dict, domain: str) -> float | None:
    d = str(domain or "").strip().lower()
    if d == "bending":
        if isinstance(candidate, dict):
            du = _candidate_bending_demand_util(candidate)
            if du is not None:
                try:
                    fv = float(du)
                    if math.isfinite(fv):
                        return fv
                except Exception:
                    pass
            raw = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
            try:
                fv = float(raw)
                if math.isfinite(fv):
                    return fv
            except Exception:
                return None
        return None
    if d == "shear":
        if isinstance(candidate, dict):
            raw = ((candidate.get("overview") or {}).get("utils") or {}).get("shear")
            try:
                fv = float(raw)
                if math.isfinite(fv):
                    return fv
            except Exception:
                return None
        return None
    return None


def _one_click_domain_score(eval_obj: dict | None, domain: str, mode_config: dict) -> dict:
    """
    Returns:
      {
        "domain": "bending" | "shear",
        "status": str | None,
        "util": float | None,
        "distance": float,
        "in_band": bool,
        "pass": bool,
        "under": bool,
        "over": bool,
      }
    """
    d = str(domain or "").strip().lower()
    overview = dict((eval_obj or {}).get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    status = statuses.get(d)
    util = _candidate_domain_util(eval_obj or {}, d)

    try:
        lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
        hi = float(mode_config.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    except Exception:
        lo = float(EFFICIENCY_TARGET_UTIL_MIN)
        hi = float(EFFICIENCY_TARGET_UTIL_MAX)

    fu = None
    if util is not None:
        try:
            fu = float(util)
            if not math.isfinite(fu):
                fu = None
        except Exception:
            fu = None

    fail = bool(status == BEAM_STATUS_FAIL or str(status or "").strip().upper() == "FAIL")
    ok_status = not fail
    dist = float("inf") if fu is None else _distance_to_target_band(fu, lo, hi)

    return {
        "domain": d,
        "status": status,
        "util": fu,
        "distance": dist,
        "in_band": bool(fu is not None and lo <= fu <= hi and ok_status),
        "pass": bool(ok_status),
        "under": bool(fu is not None and fu < lo),
        "over": bool(fu is not None and fu > hi),
    }


def _one_click_eval_domain_scores(eval_obj: dict | None, mode_config: dict) -> dict[str, dict]:
    return {
        d: _one_click_domain_score(eval_obj, d, mode_config)
        for d in _candidate_target_domains_for_band(eval_obj or {})
    }


def _one_click_required_domain_progress(eval_obj: dict | None, mode_config: dict) -> dict:
    return _resolve_candidate_required_domain_progress(
        eval_obj,
        mode_config,
        default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
        default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
        fail_status=BEAM_STATUS_FAIL,
        optimisation_goal_resolver=_design_optimisation_goal,
    )


def _one_click_required_domains_satisfied(eval_obj: dict | None, mode_config: dict) -> bool:
    return _resolve_candidate_required_domains_satisfied(
        eval_obj,
        mode_config,
        default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
        default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
        fail_status=BEAM_STATUS_FAIL,
        optimisation_goal_resolver=_design_optimisation_goal,
    )


def _candidate_in_target_band(candidate: dict, mode_config: dict) -> bool:
    return _resolve_candidate_in_target_band(
        candidate,
        mode_config,
        default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
        default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
        fail_status=BEAM_STATUS_FAIL,
        optimisation_goal_resolver=_design_optimisation_goal,
    )


def _distance_to_target_band(util: float, target_min: float, target_max: float) -> float:
    try:
        u = float(util)
        lo = float(target_min)
        hi = float(target_max)
    except (TypeError, ValueError):
        return float("inf")
    if lo <= u <= hi:
        return 0.0
    if u < lo:
        return lo - u
    return u - hi


def _candidate_reaches_target_band_one_step(candidate: dict, mode_config: dict) -> bool:
    if not candidate or not bool(candidate.get("is_compliant")):
        return False
    return _candidate_in_target_band(candidate, mode_config)


def _annotate_candidate_target_band_metrics(candidate: dict, mode_config: dict) -> None:
    if not candidate:
        return
    try:
        util = float(_candidate_objective_util(candidate))
    except Exception:
        util = float(candidate.get("worst_util", 0.0) or 0.0)
    tmin = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    tmax = float(mode_config.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    candidate["candidate_post_util"] = util
    candidate["candidate_distance_to_target_band"] = _distance_to_target_band(util, tmin, tmax)
    candidate["candidate_reaches_target_band"] = _candidate_reaches_target_band_one_step(candidate, mode_config)


def _candidate_violation_score(candidate: dict) -> float:
    util = float(candidate.get("worst_util", 0.0) or 0.0)
    overflow = max(util - 1.0, 0.0)
    fail_count = int(candidate.get("fail_count", 0) or 0)
    return overflow * 100.0 + fail_count * 25.0


def _score_auto_design_candidate_components(candidate: dict, mode_config: dict, seed_candidate: dict) -> dict:
    _bind_auto_design_scoring_dependencies(globals())
    return _score_auto_design_candidate_components_extracted(candidate, mode_config, seed_candidate)


def _score_auto_design_candidate(candidate: dict, mode_config: dict, seed_candidate: dict) -> float:
    components = _score_auto_design_candidate_components(candidate, mode_config, seed_candidate)
    candidate["_score_components"] = dict(components)
    return float(components.get("total_score", 0.0) or 0.0)


def _shear_candidate_practicality_metrics(candidate: dict, current_state: dict) -> dict[str, float | int]:
    cs = dict(candidate.get("state") or {})
    cur_legs = max(int(_int_from_state(current_state, "lig_legs", 0) or 0), 0)
    cand_legs = max(int(_int_from_state(cs, "lig_legs", cur_legs) or cur_legs), 0)
    cur_s = float(_float_from_state(current_state, "s_lig", 0.0) or 0.0)
    cand_s = float(_float_from_state(cs, "s_lig", cur_s) or cur_s)
    cur_dia = max(int(_int_from_state(current_state, "lig_d", 0) or 0), 0)
    cand_dia = max(int(_int_from_state(cs, "lig_d", cur_dia) or cur_dia), 0)
    cur_depth = float(_float_from_state(current_state, "D", 0.0) or 0.0)
    cand_depth = float(_float_from_state(cs, "D", cur_depth) or cur_depth)
    cur_width = float(_design_width_value(current_state) or 0.0)
    cand_width = float(_design_width_value(cs) or cur_width)
    cur_ast_bot = float(_float_from_state(current_state, "Ast_bot", 0.0) or 0.0)
    cur_ast_top = float(_float_from_state(current_state, "Ast_top", 0.0) or 0.0)
    cur_ast = cur_ast_bot + cur_ast_top
    cand_ast = (
        float(candidate.get("Ast_bot", _float_from_state(cs, "Ast_bot", cur_ast_bot)) or 0.0)
        + float(candidate.get("Ast_top", _float_from_state(cs, "Ast_top", cur_ast_top)) or 0.0)
    )

    leg_delta = abs(int(cand_legs) - int(cur_legs))
    spacing_delta = abs(float(cand_s) - float(cur_s))
    dia_delta = abs(int(cand_dia) - int(cur_dia))
    depth_delta = abs(float(cand_depth) - float(cur_depth))
    width_delta = abs(float(cand_width) - float(cur_width))
    steel_delta = abs(float(cand_ast) - float(cur_ast))
    odd_leg_penalty = 0.015 if cand_legs > 0 and cand_legs % 2 == 1 else 0.0
    total_practicality_penalty = odd_leg_penalty + (float(leg_delta) * 0.01)
    geometry_escalation_flag = 1 if (depth_delta > 1e-9 or width_delta > 1e-9) else 0
    geometry_delta = depth_delta + width_delta
    engineering_change = (
        (5.0 if geometry_escalation_flag else 0.0)
        + float(leg_delta)
        + (spacing_delta / 100.0)
        + (dia_delta / 2.0)
        + (geometry_delta / 100.0)
        + (steel_delta / 500.0)
        + total_practicality_penalty
    )
    return {
        "shear_candidate_leg_count": int(cand_legs),
        "shear_candidate_leg_delta": int(leg_delta),
        "shear_candidate_spacing_delta": float(spacing_delta),
        "shear_candidate_dia_delta": int(dia_delta),
        "shear_candidate_depth_delta": float(depth_delta),
        "shear_candidate_width_delta": float(width_delta),
        "shear_candidate_geometry_delta": float(geometry_delta),
        "shear_candidate_geometry_escalation_flag": int(geometry_escalation_flag),
        "shear_candidate_steel_delta": float(steel_delta),
        "shear_candidate_odd_leg_penalty": float(odd_leg_penalty),
        "shear_candidate_total_practicality_penalty": float(total_practicality_penalty),
        "shear_candidate_engineering_change": float(engineering_change),
    }


def _score_band_reaching_candidate_for_goal(
    candidate: dict,
    goal: str,
    current_state: dict,
    mode_config: dict,
) -> tuple[float, str]:
    cs = dict(candidate.get("state") or {})
    d0 = float(_float_from_state(current_state, "D", 0.0) or 0.0)
    d1 = float(_float_from_state(cs, "D", d0) or d0)
    w0 = float(_design_width_value(current_state) or 0.0)
    w1 = float(_design_width_value(cs) or w0)
    ast0 = float(_float_from_state(current_state, "Ast_bot", 0.0) or 0.0)
    ast1 = float(candidate.get("Ast_bot", _float_from_state(cs, "Ast_bot", ast0)) or ast0)
    delta_d = max(d1 - d0, 0.0)
    delta_w = max(w1 - w0, 0.0)
    delta_ast = max(ast1 - ast0, 0.0)
    post_util = float(candidate.get("candidate_post_util", _candidate_objective_util(candidate)) or 0.0)
    target_mid = _mode_target_midpoint(mode_config)
    congestion = float(candidate.get("reo_congestion_index", 0.0) or 0.0)
    row_pen = max(int(candidate.get("row_count", 1) or 1) - 2, 0)

    if goal == "shallower_beam":
        score = (
            (delta_d * 2000.0)
            + (d1 * 0.6)
            + (delta_ast * 0.08)
            + (delta_w * 0.04)
            + (congestion * 20.0)
            + (row_pen * 8.0)
        )
        if (
            bool(candidate.get("recommendation_compound"))
            and str(candidate.get("compound_geo_axis") or "") == "width"
            and delta_d <= 1e-6
        ):
            score -= 30.0
        return score, "shallower_prefers_min_depth_then_steel_then_width"

    score = (
        (abs(post_util - target_mid) * 90.0)
        + (delta_d * 0.3)
        + (delta_w * 0.25)
        + (delta_ast * 0.04)
        + (congestion * 18.0)
        + (row_pen * 8.0)
    )
    return score, "balanced_prefers_practical_low_congestion_near_target_mid"


def _band_reacher_delta_metrics(candidate: dict, current_state: dict) -> dict:
    cs = dict(candidate.get("state") or {})
    d0 = float(_float_from_state(current_state, "D", 0.0) or 0.0)
    d1 = float(_float_from_state(cs, "D", d0) or d0)
    w0 = float(_design_width_value(current_state) or 0.0)
    w1 = float(_design_width_value(cs) or w0)
    ast0 = float(_float_from_state(current_state, "Ast_bot", 0.0) or 0.0)
    ast1 = float(candidate.get("Ast_bot", _float_from_state(cs, "Ast_bot", ast0)) or ast0)
    return {
        "result_depth": d1,
        "delta_d": max(d1 - d0, 0.0),
        "delta_w": max(w1 - w0, 0.0),
        "delta_ast": max(ast1 - ast0, 0.0),
        "congestion": float(candidate.get("reo_congestion_index", 0.0) or 0.0),
        "row_pen": max(int(candidate.get("row_count", 1) or 1) - 2, 0),
    }


def _select_best_auto_design_candidate(candidates: list[dict], mode_config: dict, seed_candidate: dict) -> dict | None:
    _bind_auto_design_candidate_selector_dependencies(globals())
    return _select_best_auto_design_candidate_extracted(candidates, mode_config, seed_candidate)


def _recommendation_search_allowed(state: dict) -> bool:
    design_context = _build_design_actions_context(state)
    guidance_state = dict(design_context.get("state") or _guidance_state_snapshot(state))
    overview = _collect_design_overview(guidance_state, context=design_context)
    return not _guidance_not_started(guidance_state, overview)


def _compute_bottom_reo_tightening_recommendation(state: dict) -> dict | None:
    _bind_bottom_tightening_dependencies(globals())
    return _compute_bottom_reo_tightening_recommendation_extracted(state)


def _compute_shear_tightening_recommendation(state: dict, *, out_debug: dict | None = None) -> dict | None:
    _bind_shear_tightening_dependencies(globals())
    return _compute_shear_tightening_recommendation_extracted(state, out_debug=out_debug)


def _compute_geometry_tightening_recommendation(state: dict) -> dict | None:
    _bind_geometry_tightening_dependencies(globals())
    return _compute_geometry_tightening_recommendation_extracted(state)


def _efficiency_reduction_profile_from_overview(overview: dict | None) -> bool:
    if not isinstance(overview, dict):
        return False
    if not bool(overview.get("all_key_pass")) or bool(overview.get("any_fail")):
        return False
    try:
        worst = float(overview.get("governing_util", overview.get("worst_util", 0.0)) or 0.0)
    except (TypeError, ValueError):
        return False
    return worst <= float(GUIDANCE_INEFFICIENT_UTIL_THRESHOLD)


def _shear_change_is_reinforcement_growth(seed_state: dict, cand_state: dict) -> bool:
    sd = _int_from_state(seed_state, "lig_d", 0)
    sl = _int_from_state(seed_state, "lig_legs", 0)
    cd = _int_from_state(cand_state, "lig_d", 0)
    cl = _int_from_state(cand_state, "lig_legs", 0)
    ss = _float_from_state(seed_state, "s_lig", 200.0)
    cs = _float_from_state(cand_state, "s_lig", 200.0)
    if sd <= 0 and sl < 2 and cd <= 0 and cl < 2:
        return False
    if cd <= 0 and cl < 2 and (sd > 0 or sl >= 2):
        return False
    if cd > sd or cl > sl:
        return True
    if cd > 0 and cl >= 2 and sd > 0 and sl >= 2 and cs < ss - 1e-9:
        return True
    return False


def _candidate_is_growth_move(seed_candidate: dict, candidate: dict) -> bool:
    if not seed_candidate or not candidate:
        return False
    seed_st = dict(seed_candidate.get("state") or {})
    cand_st = dict(candidate.get("state") or {})
    d0 = float(seed_candidate.get("depth", _float_from_state(seed_st, "D", 0.0)) or _float_from_state(seed_st, "D", 0.0))
    d1 = float(candidate.get("depth", _float_from_state(cand_st, "D", 0.0)) or _float_from_state(cand_st, "D", 0.0))
    if d1 > d0 + 1e-9:
        return True
    _, _, w0 = _resolve_geometry_width_context(seed_st)
    w0 = float(w0 or 0.0)
    w1 = float(candidate.get("width", _design_width_value(cand_st)) or _design_width_value(cand_st))
    if w1 > w0 + 1e-9:
        return True
    a0 = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    a1 = float(candidate.get("Ast_bot", 0.0) or 0.0)
    if a1 > a0 + 1e-9:
        return True
    if _shear_change_is_reinforcement_growth(seed_st, cand_st):
        return True
    return False


def _log_efficiency_growth_rejection(
    *,
    candidate_family: str,
    seed_candidate: dict,
    candidate: dict | None,
    extra: dict | None = None,
) -> None:
    deltas = {}
    if candidate and seed_candidate:
        seed_st = dict(seed_candidate.get("state") or {})
        cand_st = dict(candidate.get("state") or {})
        d0 = float(seed_candidate.get("depth", _float_from_state(seed_st, "D", 0.0)) or _float_from_state(seed_st, "D", 0.0))
        d1 = float((candidate or {}).get("depth", _float_from_state(cand_st, "D", 0.0)) or _float_from_state(cand_st, "D", 0.0))
        _, _, w0 = _resolve_geometry_width_context(seed_st)
        w0 = float(w0 or 0.0)
        w1 = float((candidate or {}).get("width", _design_width_value(cand_st)) or _design_width_value(cand_st))
        a0 = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
        a1 = float((candidate or {}).get("Ast_bot", 0.0) or 0.0)
        sd = _int_from_state(seed_st, "lig_d", 0)
        sl = _int_from_state(seed_st, "lig_legs", 0)
        cd = _int_from_state(cand_st, "lig_d", 0)
        cl = _int_from_state(cand_st, "lig_legs", 0)
        deltas = {
            "delta_D_mm": round(d1 - d0, 3),
            "delta_b_mm": round(w1 - w0, 3),
            "delta_Ast_bot": round(a1 - a0, 3),
            "removed_shear_links": bool((sd > 0 or sl >= 2) and cd <= 0 and cl < 2),
        }
    payload = {
        "event": "rejected",
        "candidate_family": candidate_family,
        "reason": "growth_move_blocked_in_efficiency_mode",
        **deltas,
    }
    if extra:
        payload.update(extra)
    _merge_design_guide_rank_trace({"efficiency_growth_rejection": dict(payload)})


def _collapse_bottom_geometry_width_depth_trials(
    filtered: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
    efficiency_reduction_only: bool = False,
) -> list[dict]:
    _bind_bottom_recommendation_selector_dependencies(globals())
    return _collapse_bottom_geometry_width_depth_trials_extracted(
        filtered,
        state=state,
        seed_candidate=seed_candidate,
        mode_config=mode_config,
        efficiency_reduction_only=efficiency_reduction_only,
    )


def _compound_merged_signature_preview(seed_state: dict, compound_state: dict) -> dict:
    u = _candidate_state_to_shared_updates(seed_state, compound_state)
    wkey, _, _ = _resolve_geometry_width_context(seed_state)
    order = [
        wkey,
        "D",
        "bot_row_count",
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
    ]
    return {k: u[k] for k in order if k in u}


def _bottom_recommendation_compound_title(axis: str, geo_label: str) -> str:
    if axis == "width":
        return "Increase width and rebalance bottom reinforcement"
    if axis == "depth":
        return "Increase depth and adjust bottom reinforcement"
    gl = str(geo_label or "").strip()
    return f"Adjust geometry and bottom reinforcement ({gl})" if gl else "Adjust geometry and bottom reinforcement"


def _bottom_recommendation_compound_effective_signature(seed_state: dict, compound_state: dict) -> tuple:
    u = _candidate_state_to_shared_updates(seed_state, compound_state)
    items: list[tuple[str, float | int | str]] = []
    for k in sorted(u.keys()):
        v = u[k]
        if isinstance(v, float):
            items.append((k, round(float(v), 6)))
        else:
            items.append((k, v))
    return tuple(items)


def _select_top_geometry_seeds_for_compound(
    candidates: list[dict],
    state: dict,
    axis: str,
    *,
    limit: int,
) -> list[dict]:
    geo = [
        c
        for c in candidates
        if c.get("recommendation_geometry_trial")
        and _geometry_trial_axis_for_bottom_rec(c, state) == axis
    ]

    def _geom_sort_key(c: dict) -> float:
        bu = ((c.get("overview") or {}).get("utils") or {}).get("bending")
        try:
            return float(bu) if bu is not None else 999.0
        except (TypeError, ValueError):
            return 999.0

    geo_sorted = sorted(geo, key=_geom_sort_key)
    picked: list[dict] = []
    seen_marker: set[tuple[str, float]] = set()
    for c in geo_sorted:
        u = dict(c.get("updates") or {})
        if axis == "width":
            wkey, _, _ = _resolve_geometry_width_context(state)
            if wkey not in u:
                continue
            try:
                marker = ("width", round(float(u[wkey]), 3))
            except (TypeError, ValueError):
                continue
        elif axis == "depth":
            if "D" not in u:
                continue
            try:
                marker = ("depth", round(float(u["D"]), 3))
            except (TypeError, ValueError):
                continue
        else:
            continue
        if marker in seen_marker:
            continue
        seen_marker.add(marker)
        picked.append(c)
        if len(picked) >= limit:
            break
    return picked


def _append_geometry_bottom_compound_candidates(
    candidates: list[dict],
    state: dict,
    bottom_rec: dict,
    mode_config: dict,
    *,
    context: dict | None = None,
    compound_trace_log: list | None = None,
) -> None:
    _bind_recommendation_compound_candidate_dependencies(globals())
    return _append_geometry_bottom_compound_candidates_extracted(
        candidates,
        state,
        bottom_rec,
        mode_config,
        context=context,
        compound_trace_log=compound_trace_log,
    )


def _maybe_prefer_compound_over_pure_geometry(
    best: dict | None,
    ranked: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
) -> dict | None:
    if not best:
        return best
    if best.get("recommendation_compound"):
        return best
    if not best.get("recommendation_geometry_trial"):
        return best
    axis = _geometry_trial_axis_for_bottom_rec(best, state)
    if axis not in ("width", "depth"):
        return best
    try:
        best_score = float(best.get("score", 1e9) or 1e9)
    except (TypeError, ValueError):
        best_score = 1e9
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    seed_d = float(seed_candidate.get("depth", 0.0) or 0.0)
    margin = float(GUIDANCE_COMPOUND_VS_PURE_GEOMETRY_SCORE_MARGIN)
    pick: dict | None = None
    pick_score = float("inf")
    for c in ranked:
        if not c.get("recommendation_compound"):
            continue
        if str(c.get("compound_geo_axis") or "") != axis:
            continue
        if not (best.get("is_compliant") and c.get("is_compliant")):
            continue
        if axis == "width" and strategy == "shallow":
            try:
                cd = float(c.get("depth", seed_d) or seed_d)
            except (TypeError, ValueError):
                continue
            if cd > seed_d + 1e-9:
                continue
        try:
            sc = float(c.get("score", 1e9) or 1e9)
        except (TypeError, ValueError):
            continue
        if sc <= best_score + margin and sc < pick_score:
            pick = c
            pick_score = sc
    if pick is not None:
        return pick
    return best


def _bottom_recommendation_prefilter_ok(
    seed_candidate: dict,
    candidate: dict,
    state: dict,
) -> tuple[bool, str]:
    if not str(candidate.get("label") or "").strip():
        return False, "missing_label"
    if _candidate_ductility_governs(seed_candidate):
        sdu = _candidate_ductility_util(seed_candidate)
        tdu = _candidate_ductility_util(candidate)
        if sdu is None or tdu is None:
            return False, "missing_ductility_util"
        if float(tdu) >= float(sdu) - 1e-9:
            return False, "ductility_not_improved"
    else:
        sb = ((seed_candidate.get("overview") or {}).get("utils") or {}).get("bending")
        tb = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
        try:
            if sb is None or tb is None:
                return False, "missing_bending_util"
            if float(tb) >= float(sb) - 1e-9:
                return False, "bending_util_not_improved"
        except (TypeError, ValueError):
            return False, "missing_bending_util"
    return True, "ok"


def _shear_recommendation_overview_is_failing(overview: dict) -> bool:
    statuses = overview.get("statuses") or {}
    if str(statuses.get("shear") or "") == "FAIL":
        return True
    su = (overview.get("utils") or {}).get("shear")
    try:
        if su is not None and float(su) > 1.0 + 1e-12:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _shear_recommendation_overview_is_conservative_cleanup(overview: dict) -> bool:
    if _shear_recommendation_overview_is_failing(overview):
        return False
    if not bool(overview.get("all_key_pass")):
        return False
    statuses = overview.get("statuses") or {}
    if str(statuses.get("shear") or "") != "PASS":
        return False
    su = (overview.get("utils") or {}).get("shear")
    if su is None:
        return False
    try:
        return float(su) <= float(GUIDANCE_INEFFICIENT_UTIL_THRESHOLD)
    except (TypeError, ValueError):
        return False


def _iter_shear_recommendation_ladder_states(state: dict, *, conservative: bool) -> list[tuple[str, dict]]:
    _bind_shear_recommendation_ladder_dependencies(globals())
    return _iter_shear_recommendation_ladder_states_extracted(
        state,
        conservative=conservative,
    )


def _shear_ladder_validate_candidate(
    state: dict,
    candidate: dict | None,
    *,
    branch: str,
    conservative: bool,
    baseline_shear_util: float | None,
) -> tuple[bool, str]:
    _bind_named_recommendation_globals(
        legacy_page=_BRIDGE_PROVIDER,
        names=_SHEAR_RECOMMENDATION_NAMES,
    )
    return _shear_ladder_validate_candidate_extracted(
        state,
        candidate,
        branch=branch,
        conservative=conservative,
        baseline_shear_util=baseline_shear_util,
    )


def _is_strictly_rejectable_band_winner(candidate: dict | None, *, state: dict) -> tuple[bool, str]:
    if not isinstance(candidate, dict):
        return True, "invalid_candidate"
    if not bool(candidate.get("is_compliant")):
        return True, "noncompliant_candidate"
    if not bool(candidate.get("candidate_reaches_target_band")):
        return True, "not_target_band_candidate"
    updates = candidate.get("updates")
    if not isinstance(updates, dict) or not updates:
        return True, "missing_or_unusable_updates"
    if _updates_match_state(state, updates):
        return True, "noop_updates_match_state"
    if not str(candidate.get("label") or "").strip():
        return True, "missing_label"
    return False, "ok"


def _legacy_bottom_local_rejection_reason(
    pick: dict,
    *,
    seed_candidate: dict,
    seed_bu_f: float | None,
    ductility_seed: bool,
    seed_du: float | None,
) -> str | None:
    bu = ((pick.get("overview") or {}).get("utils") or {}).get("bending")
    try:
        bu_f = float(bu) if bu is not None else None
    except (TypeError, ValueError):
        bu_f = None
    if bu_f is None:
        return "missing_bending_util"
    if ductility_seed:
        pdu = _candidate_ductility_util(pick)
        if seed_du is not None and pdu is not None and float(pdu) >= float(seed_du) - 1e-9:
            return "ductility_not_improved"
        return None
    if seed_bu_f is not None and float(bu_f) >= float(seed_bu_f) - 1e-9:
        return "bending_util_not_improved"
    return None


def _pick_best_bottom_recommendation_by_selector(
    candidates: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
) -> dict | None:
    _bind_bottom_recommendation_selector_dependencies(globals())
    return _pick_best_bottom_recommendation_by_selector_extracted(
        candidates,
        state=state,
        seed_candidate=seed_candidate,
        mode_config=mode_config,
    )


def _try_shear_no_demand_cleanup_recommendation(state: dict, overview: dict, actions: dict) -> dict | None:
    if not _shear_demands_negligible(actions):
        return None
    if not _shear_reinforcement_is_active(state):
        return None
    su = ((overview or {}).get("utils") or {}).get("shear")
    try:
        su_f = float(su) if su is not None else 0.0
        if math.isnan(su_f):
            su_f = 0.0
    except (TypeError, ValueError):
        su_f = 0.0
    if su_f > GUIDANCE_SHEAR_UTIL_NEGLIGIBLE:
        return None
    cleanup_updates = {
        "lig_d": 0,
        "lig_legs": 0,
        "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
    }
    if _updates_match_state(state, cleanup_updates):
        return None
    trial_state = dict(state)
    trial_state.update(cleanup_updates)
    cand = evaluate_candidate_full(
        _guidance_state_snapshot(trial_state),
        source="shear_no_demand_cleanup_probe",
        updates=cleanup_updates,
    )
    if not cand or not bool(cand.get("is_compliant")):
        _merge_design_guide_rank_trace(
            {"shear_no_demand_cleanup": {"accepted": False, "reason": "non_compliant_when_links_cleared"}},
        )
        return None
    shear_preview = _evaluate_shear_with_state(dict(cand.get("state") or trial_state)) or {}
    _merge_design_guide_rank_trace(
        {
            "shear_no_demand_cleanup": {
                "accepted": True,
                "removed_shear_links": True,
                "prior_lig_d": _int_from_state(state, "lig_d", 0),
                "prior_lig_legs": _int_from_state(state, "lig_legs", 0),
            },
        },
    )
    return {
        "updates": dict(cleanup_updates),
        "label": "Remove shear reinforcement (no shear/torsion design demand)",
        "util": float(((cand.get("overview") or {}).get("utils") or {}).get("shear", 0.0) or 0.0),
        "web_util": float(shear_preview.get("web_util", 0.0) or 0.0),
        "phi_vu": float(shear_preview.get("phi_vu", 0.0) or 0.0),
        "veq": float(shear_preview.get("veq", 0.0) or 0.0),
        "score": 0.0,
        "severity_band": "cleanup",
        "candidate_type": "no_shear_design_cleanup",
    }


def _shear_recommendation_rank_key(
    candidate: dict,
    *,
    base_state: dict,
    severity_band: str,
    seed_shear_util: float | None,
) -> tuple:
    _bind_shear_candidate_generation_dependencies(globals())
    return _shear_recommendation_rank_key_extracted(
        candidate,
        base_state=base_state,
        severity_band=severity_band,
        seed_shear_util=seed_shear_util,
    )


def _combined_shear_seed_candidates(
    candidates: list[dict],
    *,
    seed_candidate: dict,
    base_state: dict,
    severity_band: str,
    seed_shear_util: float | None,
    limit: int = 8,
) -> list[dict]:
    if not candidates:
        return []
    ranked = sorted(
        candidates,
        key=lambda item: _shear_recommendation_rank_key(
            item,
            base_state=base_state,
            severity_band=severity_band,
            seed_shear_util=seed_shear_util,
        ),
    )
    selected: dict[tuple, dict] = {}
    for candidate in ranked:
        family = _shear_family_label(
            str(candidate.get("shear_candidate_type") or _shear_candidate_type(base_state, dict(candidate.get("state") or {}))),
            candidate,
            seed_candidate=seed_candidate,
        )
        if family not in selected:
            selected[family] = candidate
    ordered: list[dict] = []
    seen: set[tuple] = set()
    for candidate in list(selected.values()) + ranked[: max(2, limit // 2)]:
        candidate_key = _make_auto_design_candidate_key(dict(candidate.get("state") or {}))
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        ordered.append(candidate)
        if len(ordered) >= limit:
            break
    return ordered


def _guidance_action_updates(action_type: str, payload: dict, *, state: dict | None = None) -> dict | None:
    _bind_guidance_action_update_resolver_dependencies(globals())
    return _guidance_action_updates_extracted(action_type, payload, state=state)


def _failed_check_labels(candidate: dict) -> list[str]:
    statuses = ((candidate or {}).get("overview") or {}).get("statuses", {})
    labels: list[str] = []
    for key in ("bending", "shear", "crack", "deflection"):
        if str(statuses.get(key, "") or "") == "FAIL":
            labels.append(key.replace("_", " "))
    return labels


def _candidate_util_distance(candidate: dict, mode_config: dict) -> float:
    util = _candidate_objective_util(candidate)
    target_min = float(mode_config["target_util_min"])
    target_max = float(mode_config["target_util_max"])
    target_mid = _mode_target_midpoint(mode_config)
    if util < target_min:
        return target_min - util
    if util > target_max:
        return util - target_max
    return abs(util - target_mid)


def _candidate_layer_imbalance_penalty(candidate: dict) -> float:
    state = candidate.get("state") or {}
    count_1 = _int_from_state(state, "bot1_count", 0)
    count_2 = _int_from_state(state, "bot2_count", 0)
    if count_2 <= 0:
        return 0.0
    return float(abs(count_1 - count_2))


def compute_reo_complexity(candidate: dict) -> float:
    total_bar_count = int(candidate.get("bar_count", 0) or 0)
    row_count = int(candidate.get("row_count", 1) or 1)
    congestion_index = float(candidate.get("reo_congestion_index", 0.0) or 0.0)
    layer_imbalance_penalty = _candidate_layer_imbalance_penalty(candidate)
    return (
        total_bar_count * 1.0
        + row_count * 8.0
        + congestion_index * 12.0
        + layer_imbalance_penalty * 3.0
    )


def _candidate_is_practical(candidate: dict, mode_config: dict) -> bool:
    if not candidate:
        return False
    congestion_limit = float(mode_config.get("practicality_congestion_limit", 20.0))
    return (
        int(candidate.get("row_count", 0) or 0) <= 2
        and float(candidate.get("reo_congestion_index", 0.0) or 0.0) <= congestion_limit
    )


def _candidate_sort_key_for_mode(candidate: dict, mode_config: dict) -> tuple:
    _bind_auto_design_scoring_dependencies(globals())
    return _candidate_sort_key_for_mode_extracted(candidate, mode_config)


def utilisation_gap(candidate: dict, mode_config: dict) -> float:
    return _candidate_util_distance(candidate, mode_config)


def candidate_materially_worsens(
    new_candidate: dict,
    old_candidate: dict,
    mode_config: dict,
    *,
    phase: str,
) -> bool:
    _bind_auto_design_scoring_dependencies(globals())
    return _candidate_materially_worsens_extracted(
        new_candidate,
        old_candidate,
        mode_config,
        phase=phase,
    )


def _candidate_dominates_for_mode(candidate_a: dict, candidate_b: dict, mode_config: dict) -> bool:
    _bind_top_candidate_keeper_dependencies(globals())
    return _candidate_dominates_for_mode_extracted(candidate_a, candidate_b, mode_config)


def generate_less_shear_reo_variants(current_candidate: dict, mode_config: dict) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    if not _shear_cleanup_possible(state):
        return []
    cur_sp = float(_float_from_state(state, "s_lig", 200.0))
    current_legs = _int_from_state(state, "lig_legs", 2)
    current_dia = _int_from_state(state, "lig_d", 10)
    max_spacing = float(max(REO_SPACINGS) if REO_SPACINGS else 300.0)
    spacing_values = [float(v) for v in REO_SPACINGS if float(v) > cur_sp + 1e-9][:2]
    if max_spacing > cur_sp + 1e-9:
        spacing_values.append(max_spacing)
    spacing_values = sorted(set(float(v) for v in spacing_values))
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
    dia_values = sorted(set(
        [value for value in REO_BAR_DIAS if 0 < int(value) <= current_dia][-2:] or [max(int(current_dia), 10)]
    ))
    allow_zero_links_variant = bool(_shear_state_eligible_for_no_links(state))
    variants: dict[tuple, dict] = {}
    if allow_zero_links_variant:
        zero_link_state = dict(state)
        zero_link_state.update({
            "lig_d": 0,
            "lig_legs": 0,
            "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
        })
        variants[_make_auto_design_candidate_key(zero_link_state)] = zero_link_state
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
                candidate_state = dict(state)
                candidate_state.update({
                    "lig_d": int(resolved_dia),
                    "lig_legs": int(legs),
                    "s_lig": float(resolved_spacing),
                })
                variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    return list(variants.values())


def _keep_top_candidates(candidates: list[dict], mode_config: dict, *, limit: int) -> list[dict]:
    _bind_top_candidate_keeper_dependencies(globals())
    return _keep_top_candidates_extracted(candidates, mode_config, limit=limit)


_ENABLE_GLOBAL_EVAL_CACHE = False


def _get_eval_cache() -> dict:
    if not _ENABLE_GLOBAL_EVAL_CACHE:
        return {}
    cache = st.session_state.get("_global_eval_cache")
    if not isinstance(cache, dict):
        return {}
    return cache


def _candidate_state_to_shared_updates(seed_state: dict, candidate_state: dict) -> dict:
    tracked_keys = (
        "b",
        "bw",
        "tw",
        "D",
        "fc",
        "lig_d",
        "lig_legs",
        "s_lig",
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    )
    updates: dict[str, float | int | str] = {}
    for key in tracked_keys:
        if seed_state.get(key) != candidate_state.get(key):
            updates[key] = candidate_state.get(key)
    return updates


def _build_auto_design_context(seed_state: dict, mode_config: dict, reference_overview: dict | None = None) -> dict:
    seed_overview = reference_overview or {}
    actions = _resolve_design_actions_from_state(seed_state)
    resolved_seed_state = _state_with_resolved_design_actions(seed_state, actions)
    disable_shear_strength_candidates = bool(seed_overview) and not _shear_change_is_relevant(seed_overview, actions)
    disable_shear_cleanup_candidates = False
    return {
        "seed_state": dict(resolved_seed_state),
        "mode_config": dict(mode_config),
        "mode_signature": str(mode_config.get("search_strategy", "balanced") or "balanced"),
        "actions": dict(actions),
        "actions_signature": tuple(actions.get("signature", ())),
        "seed_overview": seed_overview,
        "ductility_priority": _ductility_governs_overview(seed_overview),
        "geometry_locked": _geometry_lock_enabled(seed_state),
        "disable_shear_strength_candidates": disable_shear_strength_candidates,
        "disable_shear_cleanup_candidates": disable_shear_cleanup_candidates,
        "seen_candidate_keys": set(),
        "layout_fit_cache": {},
    }


def evaluate_candidate_fast(candidate_state: dict, context: dict) -> dict | None:
    _bind_fast_candidate_evaluator_dependencies(globals())
    return _evaluate_candidate_fast_kernel_extracted(candidate_state, context)


def _evaluate_candidate_fast(
    candidate_state: dict,
    *,
    seed_state: dict,
    context: dict,
    eval_cache: dict,
    metrics: dict,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
) -> dict | None:
    metrics["generated_count"] = int(metrics.get("generated_count", 0)) + 1
    key = _candidate_cache_key(candidate_state)
    global_cache = _get_eval_cache()
    use_global_cache = bool(_ENABLE_GLOBAL_EVAL_CACHE) and bool(isinstance(global_cache, dict))
    context.setdefault("seen_candidate_keys", set()).add(key)
    cached = eval_cache.get(key)
    if cached is None:
        global_cached = global_cache.get(key) if use_global_cache else None
        if use_global_cache and isinstance(global_cached, dict):
            cached = dict(global_cached)
            eval_cache[key] = cached
            metrics["cache_hits"] = int(metrics.get("cache_hits", 0)) + 1
            metrics["global_cache_hits"] = int(metrics.get("global_cache_hits", 0)) + 1
        else:
            if int(metrics.get("unique_eval_count", 0) or 0) >= AUTO_DESIGN_MAX_TOTAL_UNIQUE_EVALS:
                metrics["cap_hit"] = True
                return None
            started_at = time.perf_counter()
            metrics["unique_eval_count"] = int(metrics.get("unique_eval_count", 0)) + 1
            fast_ctx = dict(context)
            ref = metrics.get("_reference_overview")
            if ref is not None:
                fast_ctx["reference_overview"] = ref
            cached = evaluate_candidate_fast(candidate_state, fast_ctx)
            metrics["fast_eval_total_ms"] = float(metrics.get("fast_eval_total_ms", 0.0) or 0.0) + ((time.perf_counter() - started_at) * 1000.0)
            if cached is None:
                return None
            cached = dict(cached)
            cached["reo_complexity"] = compute_reo_complexity(cached)
            eval_cache[key] = cached
            if use_global_cache:
                global_cache[key] = dict(cached)
    else:
        metrics["cache_hits"] = int(metrics.get("cache_hits", 0)) + 1
    candidate = dict(cached)
    candidate["source"] = source
    candidate["label"] = label or candidate.get("label") or source.replace("_", " ").title()
    candidate["action_type"] = action_type
    candidate["state"] = dict(candidate_state)
    candidate["updates"] = _candidate_state_to_shared_updates(seed_state, candidate_state)
    candidate["_seed_width"] = float(_design_width_value(seed_state) or 0.0)
    candidate["_seed_depth"] = float(_float_from_state(seed_state, "D", 0.0) or 0.0)
    candidate["_seed_ast_bot"] = float((_effective_bottom_design_state(seed_state) or {}).get("Ast_bot", 0.0) or 0.0)
    candidate["reo_complexity"] = float(candidate.get("reo_complexity", compute_reo_complexity(candidate)) or 0.0)
    return candidate


def _option_window(options: list[int], current_value: int, *, down_steps: int, up_steps: int) -> list[int]:
    if not options:
        return []
    if current_value in options:
        index = options.index(current_value)
    else:
        index = min(range(len(options)), key=lambda idx: abs(options[idx] - current_value))
    start = max(0, index - down_steps)
    stop = min(len(options), index + up_steps + 1)
    return list(dict.fromkeys(options[start:stop]))


def _arrangement_fits_state(state: dict, arrangement: dict, *, layout_cache: dict | None = None) -> bool:
    from section_layout import compute_bar_layout_pure

    b = _design_width_value(state)
    cover_side = _float_from_state(state, "cover_side", 40.0)
    rowgap_bot = _float_from_state(state, "rowgap_bot", 60.0)
    dia = int(arrangement.get("db_bot_1", 0) or 0)
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    if count_1 < 2 or dia <= 0:
        return False
    s_min = max(float(dia), 25.0)
    cache = layout_cache if isinstance(layout_cache, dict) else {}
    key_1 = (float(b), float(cover_side), float(rowgap_bot), int(dia), int(count_1))
    layout_1 = cache.get(key_1)
    if layout_1 is None:
        layout_1 = compute_bar_layout_pure(
            b=b,
            cover_side=cover_side,
            nb_or_s=float(count_1),
            db=float(dia),
            s_min=s_min,
            rowgap=rowgap_bot,
        )
        cache[key_1] = layout_1
    if not layout_1.get("fits_single_row", False):
        return False
    if count_2 > 0:
        if count_2 < 2:
            return False
        key_2 = (float(b), float(cover_side), float(rowgap_bot), int(dia), int(count_2))
        layout_2 = cache.get(key_2)
        if layout_2 is None:
            layout_2 = compute_bar_layout_pure(
                b=b,
                cover_side=cover_side,
                nb_or_s=float(count_2),
                db=float(dia),
                s_min=s_min,
                rowgap=rowgap_bot,
            )
            cache[key_2] = layout_2
        if not layout_2.get("fits_single_row", False):
            return False
    return True


def _generate_local_bottom_arrangements(state: dict, mode_config: dict, *, band: int, context: dict | None = None, limit: int | None = None) -> list[dict]:
    return _build_bottom_reo_arrangement_pool_from_state(
        state,
        mode_config,
        band=band,
        context=context,
        limit=limit,
        bar_diameters=tuple(REO_BAR_DIAS),
        default_limit=AUTO_DESIGN_MAX_STAGE_CANDIDATES,
    )


def _geometry_state_with_updates(base_state: dict, *, depth: float | None = None, width: float | None = None) -> dict:
    candidate_state = dict(base_state)
    width_key, _, current_width = _resolve_geometry_width_context(base_state)
    if depth is not None:
        candidate_state["D"] = float(int(round(max(350.0, depth) / 10.0) * 10))
    if width is not None:
        resolved_width = float(int(round(max(250.0, width) / 10.0) * 10))
        candidate_state[width_key] = resolved_width
        if width_key != "b":
            candidate_state["b"] = resolved_width
    else:
        candidate_state[width_key] = float(current_width)
    return candidate_state


def generate_shallower_or_equal_depths(seed_candidate: dict) -> list[dict]:
    seed_state = dict(seed_candidate.get("state") or {})
    if _geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    target_depths = [seed_depth - 100.0, seed_depth - 50.0, seed_depth]
    return [
        _geometry_state_with_updates(seed_state, depth=depth)
        for depth in target_depths
        if depth >= 350.0
    ]


def generate_slightly_deeper_depths(seed_candidate: dict) -> list[dict]:
    seed_state = dict(seed_candidate.get("state") or {})
    if _geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    return [
        _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
        _geometry_state_with_updates(seed_state, depth=seed_depth + 100.0),
    ]


def generate_same_or_larger_geometry_options(seed_candidate: dict) -> list[dict]:
    seed_state = dict(seed_candidate.get("state") or {})
    if _geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    width_key, _, current_width = _resolve_geometry_width_context(seed_state)
    if _candidate_ductility_governs(seed_candidate):
        geometries = [
            _geometry_state_with_updates(seed_state, depth=seed_depth),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 100.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0, width=current_width + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 100.0),
        ]
    else:
        geometries = [
            _geometry_state_with_updates(seed_state, depth=seed_depth),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 100.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0, width=current_width + 50.0),
        ]
    deduped: dict[tuple, dict] = {}
    for state in geometries:
        deduped[_make_auto_design_candidate_key(state)] = state
    return list(deduped.values())


def _generate_balanced_geometry_options(seed_candidate: dict) -> list[dict]:
    seed_state = dict(seed_candidate.get("state") or {})
    if _geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    _, _, current_width = _resolve_geometry_width_context(seed_state)
    if _candidate_ductility_governs(seed_candidate):
        geometries = [
            _geometry_state_with_updates(seed_state, depth=seed_depth),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 100.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
        ]
    else:
        geometries = [
            _geometry_state_with_updates(seed_state, depth=seed_depth),
            _geometry_state_with_updates(seed_state, depth=seed_depth - 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width - 50.0),
            _geometry_state_with_updates(seed_state, depth=seed_depth, width=current_width + 50.0),
        ]
    deduped: dict[tuple, dict] = {}
    for state in geometries:
        deduped[_make_auto_design_candidate_key(state)] = state
    return list(deduped.values())


def _guidance_not_started(state: dict, overview: dict) -> bool:
    _, _, width = _resolve_geometry_width_context(state)
    depth = _float_from_state(state, "D", 0.0)
    span = _float_from_state(state, "L", 0.0)
    required_inputs_missing = width <= 0.0 or depth <= 0.0 or span <= 0.0

    bending_util = overview["utils"].get("bending")
    shear_util = overview["utils"].get("shear")
    no_key_results = all(util is None or util <= 0.0 for util in (bending_util, shear_util))
    if required_inputs_missing or no_key_results:
        return True

    action_values = [
        abs(_uls_action_from_state(state, "M")),
        abs(_uls_action_from_state(state, "V")),
        abs(_uls_action_from_state(state, "N")),
        abs(_uls_action_from_state(state, "T")),
    ]
    no_actions = max(action_values, default=0.0) <= 1e-9

    bottom_state = _effective_bottom_design_state(state)
    no_bottom_reo = (
        float(bottom_state.get("Ast_bot", 0.0) or 0.0) <= 0.0
        or int(bottom_state.get("nb_bot", 0) or 0) <= 0
        or float(bottom_state.get("db_bot", 0.0) or 0.0) <= 0.0
    )
    no_shear_reo = (
        _int_from_state(state, "lig_legs", 0) <= 0
        or _float_from_state(state, "lig_d", 0.0) <= 0.0
        or _float_from_state(state, "s_lig", 0.0) <= 0.0
    )
    return no_actions and (no_bottom_reo or no_shear_reo)

# Mechanical extraction: rescue seed initializer helper.
def _make_rescue_seed_updates(
    *,
    b: float,
    D: float,
    top_count: int,
    top_dia: int,
    bottom_count: int,
    bottom_dia: int,
    lig_d: int,
    lig_legs: int,
    s_lig: float,
) -> dict:
    return {
        "b": float(b),
        "D": float(D),
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
        "s_lig": float(s_lig),
    }

# Mechanical extraction: final old-page provider helper closure.
_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"
_FINAL_PUBLICATION_DISPLAY_AUTHORITY = "FinalDesignGuidePublication.display"


def _load_cta_button_contract_data() -> dict:
    path = os.path.join(os.path.dirname(__file__), "design_brain", "contracts", "cta_button_contract.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        data = {}
    return dict(data or {}) if isinstance(data, dict) else {}


def cta_button_source_precedence_order() -> tuple[str, ...]:
    contract = _load_cta_button_contract_data()
    source_precedence = dict(contract.get("source_precedence") or {})
    return tuple(str(value) for value in source_precedence.get("button_contract") or ())


def cta_payload_source_precedence_order() -> dict[str, tuple[str, ...]]:
    contract = _load_cta_button_contract_data()
    payload_precedence = dict(contract.get("payload_precedence") or {})
    return {
        str(key): tuple(str(value) for value in values)
        for key, values in payload_precedence.items()
        if isinstance(values, list)
    }


def cta_candidate_source_keys() -> tuple[str, ...]:
    contract = _load_cta_button_contract_data()
    source_precedence = dict(contract.get("source_precedence") or {})
    return tuple(str(value) for value in source_precedence.get("candidate_source_keys") or ())


def cta_source_payload_labels() -> dict[str, dict[str, str]]:
    contract = _load_cta_button_contract_data()
    payload_precedence = dict(contract.get("payload_precedence") or {})
    labels = payload_precedence.get("source_payload_labels") or {}
    if not isinstance(labels, dict):
        return {}
    return {
        str(key): {str(inner_key): str(inner_value) for inner_key, inner_value in dict(value).items()}
        for key, value in labels.items()
        if isinstance(value, dict)
    }


def _apply_active_page_shear_widget_mirror_overlay(
    working: dict,
    base: dict,
    overlay_applied: dict,
) -> dict:
    """
    Overlay live shear detailing mirrors onto lightweight state (summary / Design Guide).
    Render-only: does not write canonical shared s_lig / lig_d / lig_legs.

    Precedence: Inputs page -> inputs_*; Shear page -> shear_*; otherwise shared snapshot only.
    """
    slug = str(st.session_state.get("page_slug") or "")
    overlay_plan = build_inputs_shear_widget_mirror_overlay_plan(
        page_slug=slug,
        base_state=base,
        working_state=working,
        overlay_applied=overlay_applied,
        widget_state=st.session_state,
    )
    working.clear()
    working.update(dict(overlay_plan.working_state))
    overlay_applied.clear()
    overlay_applied.update(dict(overlay_plan.overlay_applied))
    dbg = dict(overlay_plan.debug_payload)
    return dbg


def _inputs_summary_should_use_shared_only() -> tuple[bool, str]:
    shared_only_mode, reason = _inputs_summary_should_use_shared_only_for_app_bridge()
    return bool(shared_only_mode), str(reason or "")


def _recompute_summary_local_derived_fields(state: dict) -> dict:
    """Pure local derived refresh for summary builders only (no shared/session writes)."""
    working = dict(state or {})
    working.update(build_legacy_longitudinal_mirrors_from_rows(working))
    ctx = _build_design_actions_context_isolated(working)
    resolved = dict(ctx.get("state") or _guidance_state_snapshot(working))
    resolved.update(build_legacy_longitudinal_mirrors_from_rows(resolved))
    bottom_updates = _candidate_bottom_updates(resolved)
    resolved = _candidate_state_with_effective_bottom_for_overview(resolved, bottom_updates)
    resolved.update(build_legacy_longitudinal_mirrors_from_rows(resolved))
    return resolved


def _design_guide_lightweight_guidance_state(incoming: dict | None) -> dict:
    """
    Resolved state for Design Guide / guidance overview without
    ``_build_canonical_design_state_pack`` (no deep reo layout + bar resolution).
    """
    base_line = _guidance_state_snapshot(_shared_state_snapshot())
    raw = _guidance_state_snapshot(dict(incoming or {}))
    working = dict(raw)
    working.update(build_legacy_longitudinal_mirrors_from_rows(working))
    shared_only_mode, _shared_only_reason = _inputs_summary_should_use_shared_only()
    if not shared_only_mode:
        _apply_active_page_shear_widget_mirror_overlay(working, base_line, {})
    resolved = _recompute_summary_local_derived_fields(working)
    resolved.update(build_legacy_longitudinal_mirrors_from_rows(resolved))
    return _overlay_current_normalized_shear_truth(resolved)


GUIDANCE_LADDER_EARLY_STOP_UTIL = 0.85


GUIDANCE_SHALLOW_CORRECTION_MIN_D_OVER_TEMPLATE_MM = 150.0


GUIDANCE_SHALLOW_CORRECTION_METRIC_MARGIN = 0.08


GUIDANCE_SHALLOW_CORRECTION_MIN_DEPTH_DROP_MM = 40.0


DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY = "inputs_design_guide_debug_sidebar_v1"


DESIGN_GUIDE_REF_BEAM_ID_KEY = "_design_guide_ref_beam_id"


DESIGN_GUIDE_REFERENCE_D_KEY = "design_guide_reference_D"


DESIGN_GUIDE_STEP_HISTORY_KEY = "_design_guide_step_history"


DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY = "_design_guide_first_target_band_step"


DESIGN_GUIDE_HISTORY_ANCHOR_KEY = "_design_guide_history_anchor"


DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY = "_design_guide_cached_fingerprint"


DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY = "_design_guide_cached_items"


DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY = "_design_guide_cached_debug"


def _convenience_scalar_differs(cur, new) -> bool:
    if isinstance(cur, float) or isinstance(new, float):
        try:
            return abs(float(cur) - float(new)) > 1e-6
        except (TypeError, ValueError):
            return cur != new
    return cur != new


def _canonical_convenience_fields_from_state(state: dict) -> dict:
    _bind_canonical_convenience_resync_dependencies(globals())
    return _canonical_convenience_fields_from_state_extracted(state)


def _apply_canonical_convenience_resync_to_shared(*, source: str) -> dict:
    _bind_canonical_convenience_resync_dependencies(globals())
    return _apply_canonical_convenience_resync_to_shared_extracted(source=source)


def _get_cached_design_guide_guidance(
    fingerprint: tuple,
) -> tuple[list[dict], dict, bool]:
    """
    Return a cache hit only when items and the paired debug bundle are present and structurally coherent.
    Items alone (mixed/stale cache) are treated as a miss so callers recompute a trustworthy bundle.
    """

    def _debug_trustworthy(d: object) -> bool:
        debug = d if isinstance(d, dict) else None
        trust_decision = build_inputs_design_guide_cached_debug_trust_decision(
            bundle_complete=_design_guide_cached_debug_bundle_complete(debug),
            debug_publication_fingerprint=str(fingerprint),
            requested_fingerprint=str(fingerprint),
        )
        return bool(trust_decision.trustworthy)

    simple_cached_fp = st.session_state.get(DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY)
    simple_cached_items = st.session_state.get(DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY)
    cached_fp = st.session_state.get(DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY)
    items = st.session_state.get(DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY)
    debug = st.session_state.get(DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY)
    cache_result = build_inputs_design_guide_guidance_cache_result(
        fingerprint=fingerprint,
        simple_cached_fp=simple_cached_fp,
        simple_cached_items=simple_cached_items,
        simple_debug=debug if isinstance(debug, dict) else {},
        simple_debug_trustworthy=_debug_trustworthy(debug),
        cached_fp=cached_fp,
        cached_items=items,
        cached_debug=debug if isinstance(debug, dict) else {},
        cached_debug_trustworthy=_debug_trustworthy(debug),
    )
    return list(cache_result.items), dict(cache_result.debug), bool(cache_result.cache_hit)


_DESIGN_GUIDE_NON_CACHE_DEBUG_KEYS = frozenset(
    {
        "design_guide_presentation",
        "design_guide_feedback_status",
        "design_guide_feedback_reason",
        "design_guide_feedback_fail_fingerprint",
        "design_guide_current_fail_fingerprint",
        "design_guide_blocked_feedback_matches_current_state",
        "design_guide_stale_blocked_feedback_cleared",
        "design_guide_stale_blocked_feedback_reason",
        "design_guide_one_click_cta_suppressed",
        "design_guide_one_click_cta_suppressed_reason",
    }
)


def _set_cached_design_guide_guidance(
    fingerprint: tuple,
    guidance_items: list[dict] | None,
    guidance_debug: dict | None,
) -> None:
    cache_plan = build_inputs_design_guide_guidance_cache_write_plan(
        fingerprint=fingerprint,
        guidance_items=guidance_items,
        guidance_debug=guidance_debug,
        non_cache_debug_keys=_DESIGN_GUIDE_NON_CACHE_DEBUG_KEYS,
    )
    st.session_state[DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY] = cache_plan.fingerprint
    st.session_state[DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY] = list(cache_plan.guidance_items or [])
    st.session_state[DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY] = cache_plan.fingerprint
    st.session_state[DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY] = list(cache_plan.guidance_items or [])
    st.session_state[DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY] = dict(cache_plan.cache_debug)


def _repair_incomplete_design_guide_cache_debug(
    current_state: dict,
    guidance_items_raw: list[dict],
    guidance_debug: dict,
) -> bool:
    """
    If the cached debug bundle is missing overview/efficiency/resolver state, drop derived fields
    that could be stale and recompute overview + efficiency from the same resolved state used for
    items. Returns True if a repair was applied.
    """
    if _design_guide_cached_debug_bundle_complete(guidance_debug):
        return False
    for k in (
        "design_guide_has_actionable_recommendation",
        "design_guide_terminal_positive",
        "design_guide_terminal_state",
        "design_guide_presentation",
        "design_guide_title_alignment",
        "recommendation_result",
    ):
        guidance_debug.pop(k, None)
    design_context = _build_design_actions_context(current_state)
    gs = dict(guidance_debug.get("guidance_resolved_state") or _guidance_state_snapshot(current_state))
    guidance_debug["guidance_resolved_state"] = gs
    guidance_debug["overview"] = _collect_design_overview(gs, context=design_context)
    guidance_debug["efficiency_tightening_state"] = compute_efficiency_tightening_state(
        gs,
        context=design_context,
    )
    mode_cfg = _design_mode_config(_design_optimisation_goal(gs))
    guidance_debug["target_band_with_eps_passed"] = bool(
        _is_in_target_zone_with_eps(
            guidance_debug["overview"],
            mode_cfg,
            eps=TARGET_BAND_EPS,
        ),
    )
    es = guidance_debug.get("efficiency_tightening_state") or {}
    if not guidance_debug.get("guidance_branch"):
        if str(es.get("classification") or "") == "optimal":
            guidance_debug["guidance_branch"] = "optimal"
        elif str(es.get("classification") or "") == "very_low_demand":
            guidance_debug["guidance_branch"] = "very_low_demand"
        elif guidance_items_raw and str(
            (guidance_items_raw[0] or {}).get("design_guide_terminal_state") or "",
        ) == "optimal":
            guidance_debug["guidance_branch"] = "optimal"
        elif guidance_items_raw and str(
            (guidance_items_raw[0] or {}).get("design_guide_terminal_state") or "",
        ) == "very_low_demand":
            guidance_debug["guidance_branch"] = "very_low_demand"
        else:
            guidance_debug["guidance_branch"] = "cache_rehydrated"
    guidance_debug["design_guide_cache_debug_repaired"] = True
    return True


def _ensure_design_guide_debug_trace_coherent(
    *,
    state: dict,
    guidance_items: list[dict],
    debug_trace: dict | None,
) -> tuple[dict, list[str]]:
    """
    Pure contract repair for Design Guide ``debug_trace`` / panel ``guidance_debug``.

    Guarantees non-empty ``guidance_resolved_state``, coherent ``overview``,
    ``efficiency_tightening_state`` with ``classification``, and a non-blank ``guidance_branch``
    when inferable. Does not write session state or emit logs (callers log repairs).
    """
    out = dict(debug_trace or {})
    repairs: list[str] = []
    design_context = _build_design_actions_context(dict(state or {}))
    gs_raw = out.get("guidance_resolved_state")
    if not isinstance(gs_raw, dict):
        gs = dict(design_context.get("state") or _guidance_state_snapshot(dict(state or {})))
        out["guidance_resolved_state"] = gs
        repairs.append("guidance_resolved_state")
    else:
        gs = dict(gs_raw)
    if not _design_guide_debug_has_coherent_overview(out):
        out["overview"] = _collect_design_overview(gs, context=design_context)
        repairs.append("overview")
    if not _design_guide_debug_has_efficiency_state(out):
        out["efficiency_tightening_state"] = compute_efficiency_tightening_state(gs, context=design_context)
        repairs.append("efficiency_tightening_state")
    gb = str(out.get("guidance_branch") or "").strip()
    if not gb:
        es = out.get("efficiency_tightening_state") or {}
        if str(es.get("classification") or "") == "optimal":
            out["guidance_branch"] = "optimal"
        elif str(es.get("classification") or "") == "very_low_demand":
            out["guidance_branch"] = "very_low_demand"
        elif guidance_items and str((guidance_items[0] or {}).get("design_guide_terminal_state") or "").strip() == "optimal":
            out["guidance_branch"] = "optimal"
        elif guidance_items and str((guidance_items[0] or {}).get("design_guide_terminal_state") or "").strip() == "very_low_demand":
            out["guidance_branch"] = "very_low_demand"
        else:
            out["guidance_branch"] = "coherence_backfill"
        repairs.append("guidance_branch")
    return out, repairs


def _design_guide_cache_fingerprint(state: dict) -> tuple:
    return (
        "dg_cache_v2026_04_27_in_target_local_cleanup_all_families",
        DESIGN_GUIDE_ALGORITHM_VERSION,
        str(_design_optimisation_goal(state)),
        str(state.get("sec_shape")),
        float(state.get("b", 0.0) or 0.0),
        float(state.get("D", 0.0) or 0.0),
        float(state.get("fc", 0.0) or 0.0),
        float(state.get("fsy", 0.0) or 0.0),
        float(state.get("uls_Mstar", 0.0) or 0.0),
        float(state.get("uls_Vstar", 0.0) or 0.0),
        float(state.get("uls_Nstar", 0.0) or 0.0),
        float(state.get("Tu_star", 0.0) or 0.0),
        int(state.get("bot_row_count", 0) or 0),
        int(state.get("bot1_count", 0) or 0),
        float(state.get("db_bot_1", 0.0) or 0.0),
        int(state.get("bot2_count", 0) or 0),
        float(state.get("db_bot_2", 0.0) or 0.0),
        float(state.get("lig_d", 0.0) or 0.0),
        int(state.get("lig_legs", 0) or 0),
        float(state.get("s_lig", 0.0) or 0.0),
        tuple(_resolve_design_actions_from_state(state).get("signature", ())),
    )


def _one_click_domains_touched_by_updates(updates: dict | None) -> set[str]:
    return _resolve_target_band_domains_touched_by_updates(updates)


def _one_click_target_domains_for_eval(base_domains, updates: dict | None = None) -> list[str]:
    return _resolve_target_band_candidate_domains_for_updates(base_domains, updates)


def _one_click_trace_eval_domain_payload(eval_obj: dict | None, mode_config: dict) -> dict:
    if not isinstance(eval_obj, dict):
        return {
            "target_domains_for_band": None,
            "target_domain_for_band": None,
            "candidate_domain_utils": {},
            "distance_to_band": None,
            "domain_scores": {},
            "domain_total_distance": None,
            "domain_max_distance": None,
        }
    tdb = eval_obj.get("target_domains_for_band")
    if isinstance(tdb, (list, tuple)):
        tdb_out = list(tdb)
    elif tdb is None:
        tdb_out = None
    else:
        tdb_out = [tdb] if tdb else None
    td1 = eval_obj.get("target_domain_for_band")
    td1_out = str(td1).strip() if td1 is not None and str(td1).strip() else None
    ov = eval_obj.get("overview") or {}
    utils = dict(ov.get("utils") or {}) if isinstance(ov, dict) else {}
    bend = _candidate_bending_demand_util(eval_obj)
    if bend is None:
        bend = utils.get("bending")
    try:
        dist = float(_candidate_target_band_distance(eval_obj, mode_config))
    except Exception:
        dist = None
    try:
        domain_progress = _one_click_required_domain_progress(eval_obj, mode_config)
        domain_scores = dict(domain_progress.get("scores") or {})
        domain_total_distance = float(domain_progress.get("domain_total_distance", float("inf")))
        domain_max_distance = float(domain_progress.get("domain_max_distance", float("inf")))
    except Exception:
        domain_progress = {}
        domain_scores = {}
        domain_total_distance = None
        domain_max_distance = None
    return {
        "target_domains_for_band": tdb_out,
        "target_domain_for_band": td1_out,
        "candidate_domain_utils": {"bending": bend, "shear": utils.get("shear")},
        "distance_to_band": dist,
        "domain_scores": domain_scores,
        "domain_total_distance": domain_total_distance,
        "domain_max_distance": domain_max_distance,
        "required_domain_count": domain_progress.get("required_domain_count"),
        "required_fail_count": domain_progress.get("required_fail_count"),
        "required_unsatisfied_count": domain_progress.get("required_unsatisfied_count"),
        "required_satisfied_count": domain_progress.get("required_satisfied_count"),
        "required_fail_domains": list(domain_progress.get("required_fail_domains") or []),
        "required_unsatisfied_domains": list(domain_progress.get("required_unsatisfied_domains") or []),
        "required_satisfied_domains": list(domain_progress.get("required_satisfied_domains") or []),
    }


def _design_guide_sidebar_debug_enabled() -> bool:
    try:
        return bool(st.session_state.get(DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY, False))
    except Exception:
        return False


def _design_guide_history_anchor_from_state(state: dict) -> tuple:
    return (
        str(_design_optimisation_goal(state)),
        str(st.session_state.get(DESIGN_GUIDE_REF_BEAM_ID_KEY) or ""),
        tuple(_resolve_design_actions_from_state(state).get("signature", ())),
    )


def _maybe_reset_design_guide_step_history(state: dict) -> None:
    anchor = _design_guide_history_anchor_from_state(state)
    prev = st.session_state.get(DESIGN_GUIDE_HISTORY_ANCHOR_KEY)
    reset_plan = build_inputs_design_guide_step_history_reset_plan(
        current_anchor=anchor,
        previous_anchor=prev,
    )
    if reset_plan.reset_history:
        st.session_state[DESIGN_GUIDE_STEP_HISTORY_KEY] = []
        st.session_state[DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY] = None
    st.session_state[DESIGN_GUIDE_HISTORY_ANCHOR_KEY] = reset_plan.current_anchor


def _worst_util_in_efficiency_target_band(overview: dict | None) -> bool:
    if not isinstance(overview, dict):
        return False
    try:
        w = float(overview.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        return False
    target_lo, target_hi, _ = _resolved_efficiency_target_band(_design_mode_config())
    return bool(target_lo <= w <= target_hi) and bool(overview.get("all_key_pass"))


def _signature_dict_for_step_history(state: dict) -> dict:
    return {
        "D_mm": round(float(_float_from_state(state, "D", 0.0) or 0.0), 3),
        "b_mm": round(float(_design_width_value(state) or 0.0), 3),
        "goal": str(_design_optimisation_goal(state)),
    }


def _finalize_design_guide_apply_step_history(*, prior_state: dict, source: str, applied_candidate: dict | None) -> None:
    _bind_apply_step_history_finalizer_dependencies(globals())
    return _finalize_design_guide_apply_step_history_extracted(prior_state=prior_state, source=source, applied_candidate=applied_candidate)


def _design_guide_step_history_debug_summary() -> dict:
    hist = list(st.session_state.get(DESIGN_GUIDE_STEP_HISTORY_KEY) or [])
    first = st.session_state.get(DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY)
    summary = build_inputs_design_guide_step_history_debug_summary(
        history=hist,
        first_target_band_step=first,
    )
    return dict(summary.payload)


GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN = 1.0


GUIDANCE_BENDING_DEMAND_ABS_TOL_KNM = 1.0


SHEAR_OVERDESIGN_RESERVE_GUIDANCE_UTIL_MAX = 0.20


GUIDANCE_TARGET_UTIL_MIN = EFFICIENCY_TARGET_UTIL_MIN


GUIDANCE_TARGET_UTIL_MAX = EFFICIENCY_TARGET_UTIL_MAX


GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL = 0.80


GUIDANCE_STRONGLY_UNDERUTILISED_UTIL = 0.60


VERY_LOW_DEMAND_UTIL_THRESHOLD = 0.10


TARGET_BAND_ACTIONABLE_GEO_DELTA_MM = 0.5


TARGET_BAND_ACTIONABLE_AST_DELTA_MM2 = 5.0


IN_BAND_MIN_WIDTH_ALONE_MM = 50.0


IN_BAND_MIN_DEPTH_DELTA_MM = 25.0


IN_BAND_MIN_AST_DELTA_MM2 = 120.0


IN_BAND_COMPOUND_MIN_WIDTH_MM = 38.0


IN_BAND_COMPOUND_MIN_AST_MM2 = 70.0


IN_BAND_COMPOUND_MIN_DEPTH_MM = 18.0


IN_BAND_GOAL_ALIGN_MIN_SHALLOW = 14.0


IN_BAND_GOAL_ALIGN_MIN_BALANCED = 10.0


IN_BAND_SHALLOW_DEPTH_UP_MIN_GAIN = 22.0


AUTO_DESIGN_MAX_TIGHTENING_ITERS = 8


AUTO_DESIGN_MAX_LOCAL_CANDIDATES_PER_ITER = 12


AUTO_DESIGN_MAX_FIRST_HOP_RAW_CANDIDATES = 32


AUTO_DESIGN_MAX_LATER_HOP_RAW_CANDIDATES = 16


PRIMARY_GEOMETRY_KEYS = {
    "sec_shape",
    "b",
    "D",
    "bf",
    "tf",
    "bw",
    "tw",
    "bf_bot",
    "tf_bot",
}


def _design_guide_apply_snapshot(state: dict) -> dict:
    wk, _wl, wv = _resolve_geometry_width_context(state)
    return {
        "width_key": wk,
        "b": float(wv or 0.0),
        "D": float(_float_from_state(state, "D", 0.0)),
        "bottom_label": _bottom_reo_state_label(state),
        "top_label": _top_reo_state_label(state),
        "shear_fragment": _guidance_shear_links_banner_fragment(state),
    }


def _sync_design_guide_geometry_reference(state: dict) -> None:
    bid = str(st.session_state.get("active_beam_id") or "")
    prev = str(st.session_state.get(DESIGN_GUIDE_REF_BEAM_ID_KEY) or "")
    d_now = float(_float_from_state(state, "D", float(SHARED_DEFAULTS.get("D", 600.0))))
    _, _, w_now = _resolve_geometry_width_context(state)
    w_now = float(w_now or 0.0)
    if bid and bid != prev:
        st.session_state[DESIGN_GUIDE_REF_BEAM_ID_KEY] = bid
        st.session_state[DESIGN_GUIDE_REFERENCE_D_KEY] = d_now
        st.session_state[DESIGN_GUIDE_REFERENCE_B_KEY] = w_now
    if st.session_state.get(DESIGN_GUIDE_SESSION_ANCHOR_D_KEY) is None:
        st.session_state[DESIGN_GUIDE_SESSION_ANCHOR_D_KEY] = d_now


def _design_guide_effective_reference_depth(state: dict) -> float:
    ref = st.session_state.get(DESIGN_GUIDE_REFERENCE_D_KEY)
    if ref is None:
        ref = float(SHARED_DEFAULTS.get("D", 600.0))
    else:
        ref = float(ref)
    anchor = st.session_state.get(DESIGN_GUIDE_SESSION_ANCHOR_D_KEY)
    if anchor is not None:
        ref = min(ref, float(anchor))
    tmpl = float(SHARED_DEFAULTS.get("D", 600.0))
    return min(ref, tmpl)


def _record_design_guide_auto_geometry_applied(prior_state: dict, updates: dict) -> None:
    geom_keys = {"D", "b", "bw", "bf", "tw", "tf"}
    if not geom_keys.intersection(set(updates.keys())):
        return
    _, _, wb = _resolve_geometry_width_context(prior_state)
    after = dict(prior_state)
    after.update(updates)
    _, _, wa = _resolve_geometry_width_context(after)
    st.session_state[DESIGN_GUIDE_LAST_AUTO_GEOM_KEY] = {
        "D": float(_float_from_state(after, "D", 0.0)),
        "b": float(wa or 0.0),
    }


def _design_guide_efficiency_copy() -> dict:
    return {
        "title_main": "Design is efficient - further reductions would weaken capacity",
        "primary_action": "The current section is within the target utilisation range.",
        "secondary_action": "The current design is the best practical balance found, not just safe enough.",
        "guidance_why": "\n".join(
            [
                "The current section is within the target utilisation range.",
                "The solver did not find a smaller practical option that stayed inside the target range.",
                "Further reductions would reduce:",
                "- bending capacity by lowering the lever arm and/or Ast",
                "- shear capacity by reducing effective shear depth and link contribution",
                "- stiffness, which can increase deflection and cracking risk",
                "So the current design is the best practical balance found, not just safe enough.",
            ]
        ),
    }


def _design_guide_bending_low_capacity_copy() -> dict:
    return {
        "title_main": "Bending capacity is low",
        "primary_action": "Recommended action: increase bottom reinforcement or section depth.",
        "secondary_action": (
            "The solver will prefer the smallest practical change that restores capacity "
            "without making shear or serviceability worse."
        ),
        "guidance_why": "\n".join(
            [
                "The applied moment is too close to or above the available moment capacity.",
                "Why this helps:",
                "- More Ast increases tensile force capacity.",
                "- More depth increases the lever arm between compression and tension.",
                "- Together, these increase phiMu more efficiently than only oversizing one input.",
                "Trade-off: extra steel can add congestion, while extra depth increases section size and stiffness.",
            ]
        ),
    }


def _design_guide_shear_low_capacity_copy() -> dict:
    return {
        "title_main": "Shear capacity is low",
        "primary_action": "Recommended action: tighten link spacing, increase link legs, or increase effective depth.",
        "secondary_action": "The solver will first try practical reinforcement changes before increasing the whole section.",
        "guidance_why": "\n".join(
            [
                "The applied shear demand is above the available shear capacity.",
                "Why this helps:",
                "- Closer spacing increases stirrup contribution per metre.",
                "- More legs increases shear steel area.",
                "- Greater effective depth improves the concrete and truss action contribution.",
                "Trade-off: heavier or closer links can increase congestion; geometry is used when reinforcement alone is not enough.",
            ]
        ),
    }


def _design_guide_optional_shear_cleanup_copy(*, actionable: bool = False) -> dict:
    secondary = (
        "This is an optional cleanup rather than a required capacity fix; apply it only if the "
        "buildability/congestion benefit is worth the reduced shear reserve."
        if actionable
        else (
            "Because this is a non-governing cleanup rather than a required design improvement, "
            "it is shown as advisory rather than a one-click action."
        )
    )
    return {
        "title_main": "Optional refinement - shear reinforcement is conservative",
        "primary_action": "Shear capacity is well above demand, so the current links are not governing the design.",
        "secondary_action": secondary,
        "guidance_why": "\n".join(
            [
                "Shear capacity is well above demand, so the current links are not governing the design.",
                "Reducing links may improve buildability and reduce congestion, but it also lowers shear reserve capacity.",
                secondary,
            ]
        ),
    }


DESIGN_GUIDE_DISPLAY_TRUTH_SOURCES = DESIGN_GUIDE_DISPLAY_TRUTH_SOURCES_EXTRACTED


def _design_guide_target_band_for_state(state: dict | None, mode_config: dict | None = None) -> tuple[float, float]:
    _bind_display_truth_dependencies(globals())
    return _design_guide_target_band_for_state_extracted(state, mode_config)


def _design_guide_summary_util(overview: dict | None) -> float | None:
    _bind_display_truth_dependencies(globals())
    return _design_guide_summary_util_extracted(overview)


def _design_guide_candidate_overview(item: dict | None) -> dict:
    _bind_display_truth_dependencies(globals())
    return _design_guide_candidate_overview_extracted(item)


def _design_guide_candidate_util(item: dict | None) -> float | None:
    _bind_display_truth_dependencies(globals())
    return _design_guide_candidate_util_extracted(item)


def _design_guide_post_commit_util(item: dict | None = None, overview: dict | None = None) -> float | None:
    _bind_display_truth_dependencies(globals())
    return _design_guide_post_commit_util_extracted(item, overview)


def _design_guide_item_uses_candidate_preview(item: dict | None) -> bool:
    return _design_guide_item_uses_candidate_preview_extracted(item)


def _design_guide_display_truth_for_item(
    item: dict | None,
    *,
    state: dict,
    overview: dict | None,
    mode_config: dict | None = None,
    source_override: str | None = None,
    post_commit_util: float | None = None,
    post_commit_status: str | None = None,
) -> dict:
    _bind_display_truth_dependencies(globals())
    return _design_guide_display_truth_for_item_extracted(
        item,
        state=state,
        overview=overview,
        mode_config=mode_config,
        source_override=source_override,
        post_commit_util=post_commit_util,
        post_commit_status=post_commit_status,
    )


def _design_guide_apply_display_truth_to_items(
    items: list[dict] | None,
    *,
    state: dict,
    overview: dict | None,
    mode_config: dict | None = None,
) -> list[dict]:
    out: list[dict] = []
    for item in list(items or []):
        if not isinstance(item, dict):
            continue
        next_item = dict(item)
        truth = _design_guide_display_truth_for_item(
            next_item,
            state=state,
            overview=overview,
            mode_config=mode_config,
        )
        next_item["display_truth"] = dict(truth)
        next_item.update(truth)
        if (
            str(next_item.get("guidance_intent") or "") == "already_efficient"
            and not (
                str(truth.get("display_truth_source") or "") == "published_summary"
                and bool(truth.get("displayed_within_target_band"))
            )
        ):
            softer = (
                "Further reductions would lower reserve capacity or stiffness; the guide did not select "
                "a material one-click change for the published current state."
            )
            next_item["primary_action"] = softer
            next_item["guidance_why"] = "\n".join(
                [
                    softer,
                    "The solver did not find a smaller practical option that kept the governing checks acceptable.",
                    "Further reductions can reduce bending capacity, shear capacity, and stiffness.",
                ]
            )
            next_item["guidance_why_text_compact"] = next_item["guidance_why"]
        out.append(next_item)
    return out


def _guidance_item_material_updates(item: dict, state: dict) -> dict:
    try:
        updates = dict(_guidance_update_map(item) or {})
    except Exception:
        updates = {}
    if not updates and str((item or {}).get("action_type") or "").strip():
        try:
            work = dict(item or {})
            work["action_payload"] = dict(work.get("action_payload") or {})
            _ensure_guidance_item_resolved_candidate_payload(work, state=state)
            updates = dict(_guidance_update_map(work) or {})
        except Exception:
            updates = {}
    if updates:
        try:
            if _updates_match_state(state, updates):
                return {}
        except Exception:
            pass
    return updates


def _guidance_item_resolved_action_type(item: dict) -> str:
    payload = dict((item or {}).get("action_payload") or {})
    return str(
        payload.get("resolved_candidate_action_type")
        or (item or {}).get("action_type")
        or ""
    ).strip()


def _guidance_update_is_lighter_or_smaller(state: dict, updates: dict, item: dict | None = None) -> bool:
    if not updates:
        return False
    action_type = _guidance_item_resolved_action_type(item or {})
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
        try:
            before = float(_float_from_state(state, key, state.get(key, 0.0)))
            after = float(after_raw)
        except Exception:
            continue
        if key in geometry_keys and after < before - 1e-9:
            return True
        if key in bottom_keys and after < before - 1e-9:
            return True
        if key == "s_lig" and after > before + 1e-9:
            return True
        if key in {"lig_legs", "lig_d"} and after < before - 1e-9:
            return True
    return False


def _guidance_item_is_shear_only_cleanup(state: dict, updates: dict, item: dict) -> bool:
    if not updates:
        return False
    shear_keys = {"s_lig", "lig_legs", "lig_d"}
    if not set(updates).issubset(shear_keys):
        return False
    try:
        current_spacing = float(_float_from_state(state, "s_lig", 0.0) or 0.0)
        next_spacing = float(updates.get("s_lig", current_spacing))
        current_legs = float(_float_from_state(state, "lig_legs", 0.0) or 0.0)
        next_legs = float(updates.get("lig_legs", current_legs))
        current_dia = float(_float_from_state(state, "lig_d", 0.0) or 0.0)
        next_dia = float(updates.get("lig_d", current_dia))
    except Exception:
        return False
    return bool(
        next_spacing > current_spacing + 1e-9
        or next_legs < current_legs - 1e-9
        or next_dia < current_dia - 1e-9
        or str(item.get("check_key") or "").strip().lower() == "shear"
    )


def _guidance_shear_is_non_governing_conservative(overview: dict | None, mode_cfg: dict) -> bool:
    ov = overview if isinstance(overview, dict) else {}
    utils = dict(ov.get("utils") or {})
    shear_util = _parse_util_value(utils.get("shear"))
    worst_util = _parse_util_value(ov.get("worst_util"))
    target_lo = float(mode_cfg.get("target_lo", EFFICIENCY_TARGET_UTIL_MIN))
    if shear_util is None:
        return False
    if shear_util >= target_lo - float(TARGET_BAND_EPS):
        return False
    if worst_util is None:
        return True
    return bool(float(shear_util) < float(worst_util) - float(TARGET_BAND_EPS))


def _derive_design_guide_guidance_intent(
    item: dict,
    *,
    state: dict,
    overview: dict | None,
    efficiency_state: dict | None,
) -> str:
    _bind_guidance_intent_dependencies(globals())
    return _derive_design_guide_guidance_intent_extracted(
        item,
        state=state,
        overview=overview,
        efficiency_state=efficiency_state,
    )


def _design_guide_copy_for_intent(
    intent: str,
    item: dict,
    *,
    fail_keys: set[str],
    actionable: bool,
) -> dict | None:
    check_key = str((item or {}).get("check_key") or "").strip().lower()
    title = str((item or {}).get("title_main") or (item or {}).get("title") or "").strip().lower()
    if intent == "required_fix":
        bending_low = check_key == "bending" or fail_keys == {"bending"}
        shear_low = check_key == "shear" or fail_keys == {"shear"}
        if bending_low and "ductility" not in title:
            return _design_guide_bending_low_capacity_copy()
        if shear_low:
            return _design_guide_shear_low_capacity_copy()
        return None
    if intent == "optional_cleanup":
        return _design_guide_optional_shear_cleanup_copy(actionable=actionable)
    if intent == "already_efficient":
        return _design_guide_efficiency_copy()
    return None


def _design_guide_preview_contract_for_updates(
    state: dict,
    updates: dict,
) -> tuple[bool, float | None, str | None]:
    _bind_preview_contract_dependencies(globals())
    return _design_guide_preview_contract_for_updates_extracted(state, updates)


def _design_guide_button_contract(
    item: dict | None,
    *,
    state: dict,
    blocking_reason_override: str | None = None,
) -> dict:
    _bind_button_contract_dependencies(globals())
    return _design_guide_button_contract_extracted(
        item,
        state=state,
        blocking_reason_override=blocking_reason_override,
    )


def _design_guide_primary_apply_state_fingerprint(state: dict | None = None) -> str:
    source = _guidance_state_snapshot(dict(state or _shared_state_snapshot()))
    try:
        bot2_count = _int_from_state(source, "bot2_count", _int_from_state(source, "bot_row_2_bars", 0))
        bot_row_2_bars = _int_from_state(source, "bot_row_2_bars", bot2_count)
        if bot2_count <= 0 and bot_row_2_bars <= 0:
            source["db_bot_2"] = 0
            source["bot_row_2_dia"] = 0
        keys = (
            "beam_type",
            "b",
            "D",
            "cover_top",
            "cover_bot",
            "uls_Mstar",
            "uls_Vstar",
            "actions_mode",
            "actions_source",
            "bot1_count",
            "db_bot_1",
            "bot2_count",
            "db_bot_2",
            "bot_row_count",
            "bot_row_1_bars",
            "bot_row_1_dia",
            "bot_row_2_bars",
            "bot_row_2_dia",
            "lig_d",
            "lig_legs",
            "s_lig",
        )
        return str(stable_fingerprint_for_payload({key: source.get(key) for key in keys}))
    except Exception:
        return str(_design_guide_cache_fingerprint(dict(state or _shared_state_snapshot())))


def _normalise_design_guide_candidate_id(*values: object, family: str | None = None, updates: dict | None = None) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    try:
        fp = stable_fingerprint_for_payload({"family": str(family or "").strip(), "updates": dict(updates or {})})
        return f"visible_primary:{fp}"
    except Exception:
        return "visible_primary:unidentified"


def _design_guide_apply_updates_current_state_guard(state: dict | None, updates: dict | None) -> dict:
    current_state = dict(state or _shared_state_snapshot())
    candidate_updates = dict(updates or {})
    if not candidate_updates:
        return {
            "pass": False,
            "reason": "current_state_apply_preview_blocked",
            "detail": "missing_candidate_updates",
        }
    if _updates_match_state(current_state, candidate_updates):
        return {
            "pass": False,
            "reason": "candidate_updates_already_match_current_state",
            "detail": "candidate_updates_already_match_current_state",
        }
    expected_state = dict(current_state)
    expected_state.update(candidate_updates)
    try:
        preview = evaluate_candidate_full(
            _guidance_state_snapshot(expected_state),
            source="design_guide_current_state_apply_preview",
            updates=candidate_updates,
        )
    except Exception as exc:
        return {
            "pass": False,
            "reason": "current_state_apply_preview_has_fail_status",
            "detail": f"preview_exception:{type(exc).__name__}",
        }
    preview_d = dict(preview or {}) if isinstance(preview, dict) else {}
    overview = dict(preview_d.get("overview") or {})
    status = str(preview_d.get("status") or overview.get("status") or "").strip().upper()
    if status == "FAIL":
        return {
            "pass": False,
            "reason": "current_state_apply_preview_has_fail_status",
            "status": status,
        }
    if bool(overview.get("any_fail")):
        return {
            "pass": False,
            "reason": "current_state_apply_preview_any_fail",
            "status": status,
        }
    return {
        "pass": True,
        "reason": "current_state_apply_preview_passed",
        "status": status,
    }


def _build_design_guide_primary_apply_payload(
    *,
    item: dict,
    rec: dict,
    button_contract: dict,
    state: dict,
) -> dict:
    _bind_primary_apply_payload_dependencies(globals())
    return _build_design_guide_primary_apply_payload_extracted(
        item=item,
        rec=rec,
        button_contract=button_contract,
        state=state,
    )


def _cta_source_precedence_stable_hash(value: object) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _cta_action_payload_summary_for_source_precedence(payload: dict | None) -> dict:
    payload_d = dict(payload or {})
    updates = dict(
        payload_d.get("updates")
        or payload_d.get("action_updates")
        or payload_d.get("resolved_candidate_updates")
        or {}
    )
    return {
        "action_type": payload_d.get("action_type") or payload_d.get("type"),
        "updates": updates,
        "updates_hash": _cta_source_precedence_stable_hash(updates),
        "candidate_id": payload_d.get("candidate_id"),
        "source_candidate_id": payload_d.get("source_candidate_id"),
        "family": payload_d.get("family") or payload_d.get("resolved_candidate_family_tag"),
        "payload_hash": _cta_source_precedence_stable_hash(payload_d),
    }


def _build_design_guide_button_contract_source_records(
    *,
    displayed_primary_item: dict | None = None,
    primary_item: dict | None = None,
    guidance_debug: dict | None = None,
    pending_recommendation: dict | None = None,
    apply_payload_session_keys: dict | None = None,
    button_contract_session_keys: dict | None = None,
    action_payload_sources: dict | None = None,
    update_payload_sources: dict | None = None,
    candidate_sources: dict | None = None,
    publication_recovery_sources: dict | None = None,
    source_candidates: dict | None = None,
) -> DesignGuideButtonContractSourceRecords:
    return _build_design_guide_button_contract_source_records_extracted(
        displayed_primary_item=displayed_primary_item,
        primary_item=primary_item,
        guidance_debug=guidance_debug,
        pending_recommendation=pending_recommendation,
        apply_payload_session_keys=apply_payload_session_keys,
        button_contract_session_keys=button_contract_session_keys,
        action_payload_sources=action_payload_sources,
        update_payload_sources=update_payload_sources,
        candidate_sources=candidate_sources,
        publication_recovery_sources=publication_recovery_sources,
        source_candidates=source_candidates,
    )


def _select_design_guide_button_contract_source_precedence(
    *,
    source_records: DesignGuideButtonContractSourceRecords,
    button_contract_source_precedence_order: tuple[str, ...] | list[str],
    payload_source_precedence_order: dict | None,
    candidate_source_keys: tuple[str, ...] | list[str],
    source_payload_labels: dict | None = None,
) -> DesignGuideButtonContractSourceResolution:
    selected = select_design_guide_button_contract_source_precedence(
        source_records=source_records,
        button_contract_source_precedence_order=button_contract_source_precedence_order,
        payload_source_precedence_order=payload_source_precedence_order,
        candidate_source_keys=candidate_source_keys,
        source_payload_labels=source_payload_labels or {},
    )
    return build_design_guide_button_contract_source_resolution(**dict(selected or {}))


def _resolve_design_guide_button_contract_source_precedence(
    *,
    final_published_item: dict | None,
    source_candidates: dict | None = None,
    winning_button_contract_source: str = "",
    winning_update_payload_source: str = "",
    winning_action_type_source: str = "",
    winning_candidate_source: str = "",
    apply_state: dict | None = None,
    final_cta_action_payload: dict | None = None,
    source_records: DesignGuideButtonContractSourceRecords | None = None,
    button_contract_source_precedence_order: tuple[str, ...] | list[str] | None = None,
    payload_source_precedence_order: dict | None = None,
    candidate_source_keys: tuple[str, ...] | list[str] | None = None,
    source_payload_labels: dict | None = None,
) -> DesignGuideButtonContractSourceResolution:
    final_item = dict(final_published_item or {})
    records = source_records or _build_design_guide_button_contract_source_records(
        displayed_primary_item=final_item,
        primary_item=final_item,
        guidance_debug={},
        pending_recommendation={},
        apply_payload_session_keys=dict(final_cta_action_payload or {}),
        button_contract_session_keys=dict(final_item.get("button_contract") or {}),
        source_candidates=dict(source_candidates or {}),
        publication_recovery_sources={},
    )
    selected = select_design_guide_button_contract_source_precedence(
        source_records=records,
        button_contract_source_precedence_order=button_contract_source_precedence_order or cta_button_source_precedence_order(),
        payload_source_precedence_order=payload_source_precedence_order or cta_payload_source_precedence_order(),
        candidate_source_keys=candidate_source_keys or cta_candidate_source_keys(),
        source_payload_labels=source_payload_labels or cta_source_payload_labels(),
    )
    selected_d = dict(selected or {})
    if winning_button_contract_source:
        selected_d["winning_button_contract_source"] = str(winning_button_contract_source)
    if winning_update_payload_source:
        selected_d["winning_update_payload_source"] = str(winning_update_payload_source)
    if winning_action_type_source:
        selected_d["winning_action_type_source"] = str(winning_action_type_source)
    if winning_candidate_source:
        selected_d["winning_candidate_source"] = str(winning_candidate_source)
    apply_state_d = dict(apply_state or {})
    if apply_state_d:
        selected_d["apply_enabled"] = bool(apply_state_d.get("enabled", selected_d.get("apply_enabled")))
        selected_d["apply_actionable"] = bool(apply_state_d.get("actionable", selected_d.get("apply_actionable")))
        if apply_state_d.get("disabled_reason"):
            selected_d["disabled_reason"] = apply_state_d.get("disabled_reason")
    if final_cta_action_payload:
        payload_d = dict(final_cta_action_payload or {})
        selected_d["final_cta_action_payload_summary"] = _cta_action_payload_summary_for_source_precedence(payload_d)
    return build_design_guide_button_contract_source_resolution(**selected_d)


def _final_publication_cta_authority_payload(
    *,
    item: dict,
    debug: dict | None,
    button_contract: dict,
    action_payload: dict | None,
    source_precedence: dict | None,
) -> dict:
    cta = _build_final_publication_cta_from_current_state(
        item=dict(item or {}),
        debug=dict(debug or {}),
        button_contract=dict(button_contract or {}),
        action_payload=dict(action_payload or {}),
        candidate_search_evidence=dict((item or {}).get("candidate_search_evidence") or {}),
        source_precedence=dict(source_precedence or {}),
    )
    cta_payload = cta.to_dict() if hasattr(cta, "to_dict") else dict(cta or {})
    return {
        "authority": _FINAL_PUBLICATION_CTA_AUTHORITY,
        "cta": dict(cta_payload),
        "cta_hash": stable_fingerprint_for_payload(cta_payload),
    }


def _stamp_final_publication_cta_authority(
    *,
    contract: dict,
    item: dict,
    debug: dict | None,
    action_payload: dict | None,
    source_precedence: dict | None,
) -> dict:
    cta_authority = _final_publication_cta_authority_payload(
        item=dict(item or {}),
        debug=dict(debug or {}),
        button_contract=dict(contract or {}),
        action_payload=dict(action_payload or {}),
        source_precedence=dict(source_precedence or {}),
    )
    contract = dict(contract or {})
    contract["final_publication_cta_authority"] = _FINAL_PUBLICATION_CTA_AUTHORITY
    contract["final_publication_cta_hash"] = cta_authority.get("cta_hash")
    authority = {**dict(cta_authority), "matches_live": True}
    contract["final_publication_cta_matches_live"] = bool(authority["matches_live"])
    final_publication_cta_hash=cta_authority.get("cta_hash")
    ux_probe_record(
        "design_guide_final_publication_cta_authority_stamped",
        meta={
            "final_publication_cta_hash": final_publication_cta_hash,
            "authority": cta_authority.get("authority"),
        },
    )
    return contract


def _record_rendered_design_guide_primary_apply_payload(
    *,
    item: dict,
    rec: dict,
    button_contract: dict,
    state: dict,
) -> dict:
    _bind_primary_apply_payload_recorder_dependencies(globals())
    return _record_rendered_design_guide_primary_apply_payload_extracted(
        item=item,
        rec=rec,
        button_contract=button_contract,
        state=state,
    )


def _consume_design_guide_component_cta_value(
    *,
    canonical_payload: dict,
    expected_fingerprint: str,
    current_fingerprint: str,
    apply_label: str,
) -> dict | None:
    component_apply_token_mismatch = bool(expected_fingerprint and current_fingerprint != expected_fingerprint)
    if not component_apply_token_mismatch:
        return dict(canonical_payload or {})
    _set_design_guide_primary_payload_binding_audit(
        queued_apply_candidate_id=None,
        queued_apply_updates={},
        stale_apply_payload_blocked=True,
        stale_apply_payload_expected_fingerprint=expected_fingerprint,
        stale_apply_payload_current_fingerprint=current_fingerprint,
        stale_apply_payload_mismatch_reason="component_apply_token_mismatch",
        payload_binding_match=False,
        payload_update_match=False,
        legacy_fallback_used=False,
    )
    _set_one_click_run_feedback(
        status="blocked",
        reason="stale_primary_design_guide_payload",
        winning_label=str((canonical_payload or {}).get("label") or apply_label or ""),
        winning_action_type=str((canonical_payload or {}).get("action_type") or ""),
    )
    return None


def _design_guide_apply_button_contracts_to_items(
    items: list[dict] | None,
    *,
    state: dict,
    primary_blocking_reason: str | None = None,
) -> list[dict]:
    out: list[dict] = []
    for idx, item in enumerate(list(items or [])):
        if not isinstance(item, dict):
            continue
        next_item = dict(item)
        block = primary_blocking_reason if idx == 0 else None
        next_item["button_contract"] = _design_guide_button_contract(
            next_item,
            state=state,
            blocking_reason_override=block,
        )
        out.append(next_item)
    return out


def _design_guide_apply_copy_model_to_item(
    item: dict,
    *,
    state: dict,
    overview: dict | None,
    efficiency_state: dict | None,
) -> dict:
    if not isinstance(item, dict):
        return item
    out = dict(item)
    ov = overview if isinstance(overview, dict) else {}
    es = efficiency_state if isinstance(efficiency_state, dict) else {}
    mode_cfg = _design_mode_config(_design_optimisation_goal(state))
    check_key = str(out.get("check_key") or "").strip().lower()
    util = _parse_util_value(out.get("util"))
    has_action = bool(str(out.get("action_type") or "").strip())
    statuses = dict(ov.get("statuses") or {})
    fail_keys = {
        str(k).strip().lower()
        for k, v in statuses.items()
        if str(v or "").strip().upper() == "FAIL"
    }
    intent = _derive_design_guide_guidance_intent(
        out,
        state=state,
        overview=ov,
        efficiency_state=es,
    )
    out["guidance_intent"] = intent
    copy_model = _design_guide_copy_for_intent(
        intent,
        out,
        fail_keys=fail_keys,
        actionable=has_action,
    )

    if not copy_model:
        return out

    new_title = str(copy_model.get("title_main") or out.get("title_main") or "").strip()
    if new_title:
        out["title_main"] = new_title
        out["title"] = _format_guidance_title(new_title, util)
    if "primary_action" in copy_model:
        out["primary_action"] = str(copy_model.get("primary_action") or "")
    if "secondary_action" in copy_model:
        out["secondary_action"] = str(copy_model.get("secondary_action") or "")
    why_text = str(copy_model.get("guidance_why") or "").strip()
    if why_text:
        out["guidance_why"] = why_text
        out["guidance_why_text_compact"] = why_text
    return out


def _design_guide_apply_copy_model_to_items(
    items: list[dict] | None,
    *,
    state: dict,
    overview: dict | None,
    efficiency_state: dict | None,
) -> list[dict]:
    return [
        _design_guide_apply_copy_model_to_item(
            item,
            state=state,
            overview=overview,
            efficiency_state=efficiency_state,
        )
        for item in list(items or [])
        if isinstance(item, dict)
    ]


def _guidance_item_payload_fingerprint(item: dict, state: dict) -> tuple:
    at = str(item.get("action_type") or "")
    pl = dict(item.get("action_payload") or {})

    def _norm_val(v: object) -> object:
        if isinstance(v, float):
            return round(v, 4)
        if isinstance(v, (int, str, bool)) or v is None:
            return v
        return str(v)

    if at == "apply_compound_guidance":
        u = dict(pl.get("updates") or {})
        return ("apply_compound_guidance", tuple(sorted((k, _norm_val(u[k])) for k in sorted(u))))
    try:
        u = _guidance_action_updates(at, pl, state=state) or {}
    except Exception:
        u = {}
    return (at, tuple(sorted((k, _norm_val(u[k])) for k in sorted(u))))


def _family_tag_from_compound_updates(u: dict, state: dict) -> str:
    subs = _compound_subfamilies_from_updates(u)
    sf = set(subs)
    if sf >= {"geometry", "bottom_reo"}:
        d0, d1, w0, w1 = _compound_geometry_deltas(state, u)
        if d1 > d0 + 0.5 and w1 > w0 + 0.5:
            return "compound_depth_width_bottom"
        if d1 > d0 + 0.5:
            return "compound_depth_bottom"
        if w1 > w0 + 0.5:
            return "compound_width_bottom"
        return "compound_geometry_bottom"
    if sf >= {"shear", "bottom_reo"}:
        return "shear_bottom_compound"
    if sf >= {"geometry", "shear"}:
        return "compound_geometry_shear"
    return "compound_other"


def _guidance_item_family_tag(item: dict, state: dict) -> str:
    at = str(item.get("action_type") or "")
    pl = dict(item.get("action_payload") or {})
    if at == "apply_compound_guidance":
        u = dict(pl.get("updates") or {})
        return _family_tag_from_compound_updates(u, state)
    if at == "apply_bottom_recommendation":
        return "pure_bottom_reo"
    if at == "increase_width":
        return "pure_geometry_width"
    if at == "increase_depth":
        return "pure_geometry_depth"
    if at in ("apply_geometry_recommendation", "tighten_geometry"):
        return "geometry_recommendation"
    if at in ("apply_shear_recommendation", "increase_link_spacing", "reduce_number_of_legs", "reduce_link_spacing"):
        return "shear_adjust"
    if at == "apply_mode_recommendation":
        return "mode_guidance"
    if at == "reduce_bottom_reinforcement":
        return "bottom_reduction"
    return at or "unknown"


def _dedupe_guidance_items_for_display(items: list[dict], state: dict) -> tuple[list[dict], dict]:
    _bind_guidance_item_dedupe_dependencies(globals())
    return _dedupe_guidance_items_for_display_extracted(items, state)


def _guidance_executor_actionability_contract(
    item: dict | None,
    *,
    state: dict | None,
) -> tuple[bool, str | None]:
    _bind_executor_actionability_contract_dependencies(globals())
    return _guidance_executor_actionability_contract_extracted(item, state=state)


def _guidance_item_as_advisory(
    item: dict | None,
    *,
    blocked_reason: str,
) -> dict | None:
    if not isinstance(item, dict):
        return item
    out = dict(item)
    payload = dict(out.get("action_payload") or {})
    payload["contract_blocked_reason"] = str(blocked_reason or "").strip() or None
    out["action_payload"] = payload
    out["action_type"] = None
    out["executor_contract_blocked_reason"] = str(blocked_reason or "").strip() or None
    blocked_text = str(blocked_reason or "").strip().lower()
    if (
        "current design is inside the target utilisation band" in blocked_text
        or "blocked_shear_cleanup_does_not_reach_final_family_threshold" in blocked_text
        or "blocked_zero_shear_demand_shear_update_not_meaningful" in blocked_text
    ):
        out["check_key"] = "general"
        out["bucket"] = "pass"
        out["status"] = "PASS"
        out["title_main"] = "Design accepted - target band achieved"
        out["title"] = "Design accepted - target band achieved"
        out["title_sub"] = "No one-click cleanup is executable for this state"
        out["guidance_intent"] = "already_efficient"
        out["design_guide_terminal_state"] = "optimal"
        out["primary_action"] = ""
        out["secondary_action"] = "No primary one-click update is displayed for this state."
        out["reasoning"] = (
            "Why: all required checks remain acceptable, governing utilisation is inside the target band, "
            "and further local cleanup is blocked by the recorded engineering threshold evidence."
        )
        return out
    if str(blocked_reason or "").strip() == "primary_efficiency_card_not_executor_backed":
        out["title_main"] = "Cleanup is advisory for this design state"
        out["title_sub"] = "Advisory reduction ideas need a specific executable update"
        out["reasoning"] = (
            "Why: the solver did not attach a one-click change because the candidate was not "
            "converted into a directly executable update. Review the debug trace for the blocker."
        )
    primary_action = str(out.get("primary_action") or "").strip()
    if primary_action:
        out["primary_action"] = "No one-click update is displayed for this state."
    secondary = str(out.get("secondary_action") or "").strip()
    advisory = (
        "Optional advisory only: no material candidate preserved bending, shear, serviceability, "
        "and detailing checks with executable updates."
    )
    out["secondary_action"] = secondary or advisory
    return out


def _try_promote_efficiency_item_to_executor_backed_candidate(
    item: dict | None,
    *,
    state: dict,
    blocked_reason: str | None = None,
) -> tuple[dict | None, dict]:
    _bind_efficiency_executor_promotion_dependencies(globals())
    return _try_promote_efficiency_item_to_executor_backed_candidate_extracted(
        item,
        state=state,
        blocked_reason=blocked_reason,
    )


def _sanitize_guidance_items_for_executor_contract(
    guidance_items: list[dict] | None,
    *,
    state: dict,
    debug_sink: dict | None = None,
) -> list[dict]:
    _bind_efficiency_executor_promotion_dependencies(globals())
    _bind_executor_contract_sanitizer_dependencies(globals())
    return _sanitize_guidance_items_for_executor_contract_extracted(
        guidance_items,
        state=state,
        debug_sink=debug_sink,
    )


def _proposed_change_lines_for_guidance_item(item: dict, state: dict) -> list[str]:
    cached = item.get("guidance_change_lines")
    if isinstance(cached, list) and cached:
        return [str(x).strip() for x in cached if str(x).strip()]
    action_type = item.get("action_type")
    if not action_type:
        return []
    try:
        updates = _guidance_action_updates(
            str(action_type),
            dict(item.get("action_payload") or {}),
            state=state,
        )
    except Exception:
        updates = None
    lines = _guidance_change_lines_for_updates(state, updates or {})
    if lines:
        return lines
    if updates:
        return ["Apply this recommendation to update the model."]
    return ["Review the recommendation and apply if appropriate."]


def _guidance_card_proposed_change_html(item: dict, state: dict) -> str:
    lines = _proposed_change_lines_for_guidance_item(item, state)
    if not lines:
        return ""
    inner = "<br>".join(html.escape(x) for x in lines)
    return (
        f"<div class='fast-guidance-proposed'>"
        f"<strong>Proposed change</strong><br>{inner}"
        f"</div>"
    )


def _guidance_compact_change_text(change_lines: list[str]) -> str:
    lines = [str(x).strip() for x in (change_lines or []) if str(x).strip()]
    if not lines:
        return "No direct design changes identified."
    return " | ".join(lines[:3])


def _guidance_item_payload(item: dict | None) -> dict:
    if not isinstance(item, dict):
        return {}
    payload = item.get("action_payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _guidance_item_is_resolved_one_click(item: dict | None) -> bool:
    if not isinstance(item, dict):
        _emit_design_guide_apply_trace_run_end(
            stop_reason="missing_resolved_candidate_updates",
            final_updates={},
            winner_label=label,
        )
        return False
    payload = _guidance_item_payload(item)
    return bool(
        (
            str(item.get("action_type") or "") == "apply_resolved_candidate"
            or bool(payload.get("resolved_candidate_updates"))
        )
        and payload.get("resolved_candidate_updates")
        and payload.get("resolved_candidate_reaches_target_band") is not None
    )


def _guidance_item_expected_util(item: dict | None):
    payload = _guidance_item_payload(item)
    value = payload.get("expected_governing_util")
    if value is None:
        value = payload.get("resolved_candidate_post_util")
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _resolved_shear_cleanup_is_executor_safe(
    item: dict | None,
    *,
    state: dict | None,
    overview: dict | None = None,
) -> bool:
    if not isinstance(item, dict):
        return False
    current_state = _guidance_state_snapshot(state or {})
    payload = _guidance_item_payload(item)
    updates = dict(payload.get("resolved_candidate_updates") or payload.get("updates") or {})
    if not updates:
        return False
    pure_updates, _bad_update_keys = _shear_detailing_updates_pure(updates)
    if not pure_updates:
        return False
    next_state = dict(current_state)
    next_state.update(updates)
    if not _shear_cleanup_materially_reduces_reinforcement(current_state, next_state):
        return False

    resolved_candidate = dict(item.get("resolved_candidate") or payload.get("resolved_candidate") or {})
    candidate_overview = dict(resolved_candidate.get("overview") or {})
    if not candidate_overview:
        try:
            evaluated = _evaluate_auto_design_candidate(
                current_state,
                updates=updates,
                source="guidance_shear_executor_contract_probe",
                label=str(payload.get("resolved_candidate_label") or item.get("title_main") or "Adjust shear reinforcement"),
                action_type=str(
                    payload.get("resolved_candidate_action_type")
                    or item.get("action_type")
                    or "apply_shear_recommendation"
                ).strip(),
            )
        except Exception:
            evaluated = None
        if not isinstance(evaluated, dict):
            return False
        resolved_candidate = dict(evaluated)
        resolved_candidate["updates"] = dict(updates)
        candidate_overview = dict(resolved_candidate.get("overview") or {})

    candidate_statuses = dict(candidate_overview.get("statuses") or {})
    if _candidate_preview_statuses_have_explicit_fail(candidate_statuses):
        return False
    if bool(candidate_overview.get("any_fail")):
        return False

    governing_overview = dict(overview or {})
    governing_domain = str(_governing_focus_from_overview(governing_overview) or "").strip().lower()
    if governing_domain:
        governing_status_after = str(candidate_statuses.get(governing_domain) or "").strip().upper()
        if governing_status_after == "FAIL":
            return False
    return True


def _promote_guidance_item_to_resolved_candidate(
    item: dict | None,
    candidate: dict | None,
    *,
    state: dict,
) -> dict | None:
    _bind_resolved_candidate_guidance_item_dependencies(globals())
    return _promote_guidance_item_to_resolved_candidate_extracted(
        item,
        candidate,
        state=state,
    )


def _local_cleanup_debug_defaults(previous_primary_title: str | None = None) -> dict:
    return {
        "local_cleanup_promoted": False,
        "local_cleanup_family": None,
        "local_cleanup_candidate_id": None,
        "local_cleanup_reason": None,
        "local_cleanup_blocked_reason": None,
        "previous_primary_title": previous_primary_title,
        "final_primary_title": previous_primary_title,
    }


def _final_accepted_meaningful_family_utils(overview: dict | None) -> tuple[dict[str, float], dict[str, float], dict[str, dict]]:
    family_utils = _overview_family_utils_for_local_cleanup(overview)
    meaningful: dict[str, float] = {}
    excluded: dict[str, dict] = {}
    for family, util in sorted(family_utils.items()):
        fam = str(family or "").strip().lower()
        try:
            fu = float(util)
        except Exception:
            excluded[fam] = {"excluded_reason": "zero_demand_or_not_meaningful", "util": util}
            continue
        if fam in {"crack", "deflection", "serviceability", "geometry"} and fu <= 1e-9:
            excluded[fam] = {"excluded_reason": "zero_demand_or_not_meaningful", "util": fu}
            continue
        meaningful[fam] = fu
    return family_utils, meaningful, excluded


def _accepted_green_exact_blockers_by_family(source: dict | None) -> dict[str, dict]:
    if not isinstance(source, dict):
        return {}
    raw = (
        source.get("post_click_exact_blockers_by_family")
        or source.get("exact_blockers_by_family")
        or source.get("local_cleanup_exact_blockers_by_family")
        or {}
    )
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict] = {}
    for family, blocker in raw.items():
        fam = str(family or "").strip().lower()
        if fam and _accepted_green_exact_blocker_is_valid(blocker if isinstance(blocker, dict) else None):
            out[fam] = dict(blocker)
    return out


def _accepted_green_cleanup_evidence_by_family(source: dict | None) -> dict[str, dict]:
    if not isinstance(source, dict):
        return {}
    raw = (
        source.get("post_click_cleanup_evidence_by_family")
        or source.get("cleanup_evidence_by_family")
        or {}
    )
    if isinstance(raw, dict):
        return {str(k or "").strip().lower(): dict(v) for k, v in raw.items() if k and isinstance(v, dict)}
    evidence = (
        source.get("candidate_search_evidence")
        or source.get("local_cleanup_candidate_search_evidence")
        or {}
    )
    if not isinstance(evidence, dict):
        return {}
    out: dict[str, dict] = {}
    for bucket in ("safe_executor_backed_candidates", "target_band_candidates", "rejected_target_band_candidates"):
        for row in list(evidence.get(bucket) or []):
            if not isinstance(row, dict):
                continue
            family = str(row.get("affected_family") or row.get("family") or row.get("intended_family") or "").strip().lower()
            if not family:
                continue
            info = out.setdefault(family, {"attempted_candidate_count": 0, "candidate_ids": []})
            info["attempted_candidate_count"] = int(info.get("attempted_candidate_count") or 0) + 1
            cid = str(row.get("candidate_id") or row.get("source_candidate_id") or "").strip()
            if cid:
                info.setdefault("candidate_ids", []).append(cid)
    return out


def _shear_overprovision_floor_exact_blocker(state: dict | None, overview: dict | None) -> dict | None:
    if not isinstance(state, dict):
        return None
    if _shear_reinforcement_is_active(state):
        return None
    ov = overview if isinstance(overview, dict) else {}
    shear_pack = dict((ov.get("packs") or {}).get("shear") or {})
    utils = dict(ov.get("utils") or {})
    shear_util = _parse_util_value(utils.get("shear") or shear_pack.get("summary_util"))
    demand = (
        shear_pack.get("summary_governing_demand_kN")
        or shear_pack.get("summary_Veq_kN")
        or ov.get("Vu_star")
        or "unknown"
    )
    capacity = (
        shear_pack.get("summary_governing_capacity_kN")
        or shear_pack.get("summary_phiVu_kN")
        or shear_pack.get("summary_display_capacity")
        or "concrete shear capacity"
    )
    return {
        "family": "shear",
        "current_util": shear_util if shear_util is not None else "not_applicable",
        "threshold": FINAL_ACCEPTED_MIN_FAMILY_UTIL,
        "attempted_candidate_count": 1,
        "best_rejected_candidate_id": "shear_cleanup_floor_no_links_remaining",
        "attempted_updates": {"lig_legs": 0, "lig_d": 0, "s_lig": CANONICAL_NO_SHEAR_SLIG_MM},
        "failed_check_name": "minimum shear reinforcement floor",
        "failed_check_status": "BLOCKED",
        "failed_check_util": shear_util if shear_util is not None else "not_applicable",
        "failed_check_demand": demand,
        "failed_check_capacity_or_limit": capacity,
        "demand": demand,
        "capacity_or_limit": capacity,
        "why_reduction_would_hurt_other_design_elements": (
            "Shear links are already removed, so further shear utilisation increase cannot be achieved "
            "through shear reinforcement cleanup; additional reserve reduction would have to change section "
            "geometry or bending reinforcement and would affect bending, serviceability, detailing, or concrete shear capacity."
        ),
        "reason": (
            "Shear links are already removed; further shear reserve reduction would require geometry or bending changes."
        ),
    }


def _bending_low_util_floor_exact_blocker(state: dict | None, overview: dict | None) -> dict | None:
    if not isinstance(state, dict):
        return None
    ov = overview if isinstance(overview, dict) else {}
    utils = dict(ov.get("utils") or {})
    bending_util = _parse_util_value(utils.get("bending"))
    shear_util = _parse_util_value(utils.get("shear"))
    if bending_util is None or bending_util >= FINAL_ACCEPTED_MIN_FAMILY_UTIL:
        return None
    packs = dict(ov.get("packs") or {})
    bend_pack = dict(packs.get("bending") or {})
    shear_pack = dict(packs.get("shear") or {})
    demand = (
        shear_pack.get("summary_governing_demand_kN")
        or shear_pack.get("summary_Veq_kN")
        or ov.get("Vu_star")
        or bend_pack.get("summary_Mu_star_kNm")
        or "unknown"
    )
    capacity = (
        shear_pack.get("summary_governing_capacity_kN")
        or shear_pack.get("summary_phiVu_kN")
        or shear_pack.get("summary_display_capacity")
        or bend_pack.get("summary_phiMu_kNm")
        or "governing shear/detailing limit"
    )
    failed_util = shear_util if shear_util is not None else bending_util
    return {
        "family": "bending",
        "current_util": bending_util,
        "threshold": FINAL_ACCEPTED_MIN_FAMILY_UTIL,
        "attempted_candidate_count": 1,
        "best_rejected_candidate_id": "bending_cleanup_floor_shear_or_detailing_limited",
        "attempted_updates": {
            "D": "next lower safe depth/reinforcement trial",
            "bot1_count": "next lower bar count/diameter trial",
        },
        "failed_check_name": "governing shear/detailing limit for further bending cleanup",
        "failed_check_status": "BLOCKED",
        "failed_check_util": failed_util,
        "failed_check_demand": demand,
        "failed_check_capacity_or_limit": capacity,
        "demand": demand,
        "capacity_or_limit": capacity,
        "why_reduction_would_hurt_other_design_elements": (
            "Bending cleanup has already reduced section depth and bottom reinforcement to the safe local floor; "
            "further bending reserve reduction would require smaller depth or less tension steel and would affect "
            "shear capacity, serviceability stiffness, bar fit, ductility, or detailing."
        ),
        "reason": (
            "Further bending cleanup is blocked by the governing shear/detailing and serviceability floor after "
            "the selected one-click reduction."
        ),
    }


def _post_click_accepted_green_audit(
    overview: dict | None,
    *,
    blocker_source: dict | None = None,
    state: dict | None = None,
    threshold: float = FINAL_ACCEPTED_MIN_FAMILY_UTIL,
    build_active_shear_blocker: bool = True,
) -> dict:
    _bind_post_commit_audit_dependencies(globals())
    return _post_click_accepted_green_audit_extracted(
        overview,
        blocker_source=blocker_source,
        state=state,
        threshold=threshold,
        build_active_shear_blocker=build_active_shear_blocker,
    )


def _bottom_ast_from_visible_arrangement(state: dict | None) -> float | None:
    if not isinstance(state, dict):
        return None
    try:
        c1 = _int_from_state(state, "bot1_count", _int_from_state(state, "bot_row_1_bars", 0))
        c2 = _int_from_state(state, "bot2_count", _int_from_state(state, "bot_row_2_bars", 0))
        d1 = _float_from_state(
            state,
            "db_bot_1",
            _float_from_state(state, "bot_row_1_dia", _float_from_state(state, "db_bot", 0.0)),
        )
        d2 = _float_from_state(
            state,
            "db_bot_2",
            _float_from_state(state, "bot_row_2_dia", d1),
        )
        if c1 <= 0 and c2 <= 0:
            return None
        if c1 > 0 and d1 <= 0:
            return None
        if c2 > 0 and d2 <= 0:
            return None
        return float(c1 * math.pi * d1**2 / 4.0 + c2 * math.pi * d2**2 / 4.0)
    except Exception:
        return None


def _state_update_reduces_bottom_reinforcement(current_state: dict, next_state: dict) -> bool:
    try:
        cur_arranged = _bottom_ast_from_visible_arrangement(current_state)
        nxt_arranged = _bottom_ast_from_visible_arrangement(next_state)
        cur = float(cur_arranged if cur_arranged is not None else _effective_bottom_design_state(current_state).get("Ast_bot", 0.0) or 0.0)
        nxt = float(nxt_arranged if nxt_arranged is not None else _effective_bottom_design_state(next_state).get("Ast_bot", cur) or cur)
        return bool(nxt < cur - 1e-6)
    except Exception:
        return False


def _state_update_reduces_section_size(current_state: dict, next_state: dict) -> bool:
    cur_b = _float_from_state(current_state, "b", 0.0)
    nxt_b = _float_from_state(next_state, "b", cur_b)
    cur_d = _float_from_state(current_state, "D", 0.0)
    nxt_d = _float_from_state(next_state, "D", cur_d)
    return bool(nxt_b < cur_b - 1e-9 or nxt_d < cur_d - 1e-9)


def _local_cleanup_family_for_updates(updates: dict, item: dict | None, state: dict) -> str:
    update_keys = set(dict(updates or {}))
    if update_keys & _COMPOUND_SHEAR_UPDATE_KEYS:
        return "shear"
    if any(str(k).startswith("bot") or str(k).startswith("db_bot") for k in update_keys):
        return "bending"
    if update_keys & PRIMARY_GEOMETRY_KEYS:
        return "geometry"
    return _optimisation_candidate_family(item or {}, state)


def _local_cleanup_candidate_affects_family(family: str, updates: dict | None) -> bool:
    fam = str(family or "").strip().lower()
    keys = set(dict(updates or {}))
    has_shear = bool(keys & _COMPOUND_SHEAR_UPDATE_KEYS)
    has_bottom = bool(keys & _COMPOUND_BOTTOM_UPDATE_KEYS) or any(
        str(k).startswith("bot") or str(k).startswith("db_bot") for k in keys
    )
    has_geometry = bool(keys & PRIMARY_GEOMETRY_KEYS or keys & _COMPOUND_GEOMETRY_UPDATE_KEYS)
    if fam == "shear":
        return has_shear
    if fam == "bending":
        return bool(has_bottom or has_geometry)
    if fam in {"crack", "deflection", "serviceability"}:
        return bool(has_bottom or has_geometry)
    if fam == "geometry":
        return has_geometry
    return False


def _local_cleanup_materially_reduces(
    family: str,
    current_state: dict,
    candidate_state: dict,
) -> bool:
    fam = str(family or "").strip().lower()
    if fam == "shear":
        return _shear_cleanup_materially_reduces_reinforcement(current_state, candidate_state)
    if fam in {"bending", "bottom_reo"}:
        return _state_update_reduces_bottom_reinforcement(current_state, candidate_state)
    if fam == "geometry":
        return _state_update_reduces_section_size(current_state, candidate_state)
    return bool(
        _shear_cleanup_materially_reduces_reinforcement(current_state, candidate_state)
        or _state_update_reduces_bottom_reinforcement(current_state, candidate_state)
        or _state_update_reduces_section_size(current_state, candidate_state)
    )


def _local_cleanup_material_proxy(state: dict | None) -> float:
    st = state if isinstance(state, dict) else {}
    width = float(_design_width_value(st) or _float_from_state(st, "b", 0.0) or 0.0)
    depth = float(_float_from_state(st, "D", 0.0) or 0.0)
    try:
        ast = float(
            _bottom_ast_from_visible_arrangement(st)
            or _effective_bottom_design_state(st).get("Ast_bot", 0.0)
            or 0.0
        )
    except Exception:
        ast = 0.0
    lig_d = float(_float_from_state(st, "lig_d", 0.0) or 0.0)
    lig_legs = float(_float_from_state(st, "lig_legs", 0.0) or 0.0)
    spacing = max(float(_float_from_state(st, "s_lig", 0.0) or 0.0), 1.0)
    shear_density = lig_legs * lig_d * lig_d / spacing
    return float(width * depth * 0.001 + ast * 0.05 + shear_density * 20.0)


def _evaluate_local_cleanup_guidance_item(
    item: dict | None,
    *,
    state: dict,
    overview: dict,
    mode_config: dict,
    source: str,
) -> tuple[dict | None, dict]:
    _bind_local_cleanup_guidance_evaluator_dependencies(globals())
    return _evaluate_local_cleanup_guidance_item_extracted(
        item,
        state=state,
        overview=overview,
        mode_config=mode_config,
        source=source,
    )


def _best_safe_shear_local_cleanup_recommendation(
    state: dict,
    overview: dict,
    first_recommendation: dict | None,
) -> dict | None:
    _bind_shear_local_cleanup_dependencies(globals())
    return _best_safe_shear_local_cleanup_recommendation_extracted(
        state,
        overview,
        first_recommendation,
    )


def _shear_tightening_as_local_cleanup_item(
    state: dict,
    overview: dict,
    efficiency_state: dict | None,
) -> dict | None:
    _bind_shear_local_cleanup_dependencies(globals())
    return _shear_tightening_as_local_cleanup_item_extracted(state, overview, efficiency_state)


def _maybe_promote_safe_local_cleanup_primary(
    guidance_items: list[dict] | None,
    *,
    state: dict,
    overview: dict | None,
    efficiency_state: dict | None,
    mode_config: dict | None,
    debug_sink: dict | None = None,
    source: str = "design_guide_local_cleanup_promoter",
) -> tuple[list[dict], dict]:
    _bind_local_cleanup_promotion_dependencies(globals())
    return _maybe_promote_safe_local_cleanup_primary_extracted(
        guidance_items,
        state=state,
        overview=overview,
        efficiency_state=efficiency_state,
        mode_config=mode_config,
        debug_sink=debug_sink,
        source=source,
    )


def _align_guidance_items_to_candidate_search_evidence(
    guidance_items: list[dict] | None,
) -> list[dict]:
    _bind_candidate_search_evidence_dependencies(globals())
    return _align_guidance_items_to_candidate_search_evidence_extracted(guidance_items)


def _guidance_expected_util_text(value) -> str:
    try:
        if value is None:
            return "Expected util: -"
        return f"Expected util: {float(value):.2f}"
    except Exception:
        return "Expected util: -"


def _guidance_single_sentence(text: str) -> str:
    raw = " ".join(str(text or "").strip().split())
    if not raw:
        return ""
    for marker in (". ", "! ", "? "):
        if marker in raw:
            return raw.split(marker, 1)[0].strip() + marker.strip()
    if raw.endswith((".", "!", "?")):
        return raw
    return raw + "."


def _guidance_compact_why_text(item: dict) -> str:
    payload = dict(item.get("action_payload") or {})
    why_explicit = str(item.get("guidance_why_text_compact") or payload.get("guidance_why_text_compact") or "").strip()
    if why_explicit:
        if why_explicit.lower().startswith("why:"):
            return why_explicit
        return f"Why: {why_explicit}"
    why_raw = str(_guidance_card_why_body(item) or "").strip()
    if why_raw.lower().startswith("why:"):
        why_raw = why_raw[4:].strip()
    why_one = _guidance_single_sentence(why_raw)
    if not why_one:
        return "Why: This update targets the governing check and improves utilisation."
    return f"Why: {why_one}"


def _guidance_compact_alternatives_text(item: dict) -> str:
    payload = dict(item.get("action_payload") or {})
    alt_raw = str(payload.get("guidance_alternatives_text_compact") or "").strip()
    if not alt_raw:
        sec = str(item.get("secondary_action") or "").strip()
        if sec and sec.lower() not in {"none", "n/a", "no secondary action required."}:
            alt_raw = sec
    if not alt_raw:
        return ""
    if alt_raw.lower().startswith("other options:"):
        return alt_raw
    return f"Other options: {alt_raw}"


def _guidance_primary_compact_lines_html(item: dict, state: dict) -> str:
    payload = _guidance_item_payload(item)
    payload_change_lines = payload.get("guidance_change_lines")
    if isinstance(payload_change_lines, list) and payload_change_lines:
        change_lines = [str(x).strip() for x in payload_change_lines if str(x).strip()]
    else:
        direct_change_lines = item.get("guidance_change_lines")
        if isinstance(direct_change_lines, list) and direct_change_lines:
            change_lines = [str(x).strip() for x in direct_change_lines if str(x).strip()]
        else:
            change_lines = _proposed_change_lines_for_guidance_item(item, state)
    change_summary = str(
        payload.get("guidance_change_summary_compact")
        or _guidance_compact_change_text(change_lines)
    ).strip()
    why_text = _guidance_compact_why_text(item)
    alt_text = _guidance_compact_alternatives_text(item)
    is_resolved = _guidance_item_is_resolved_one_click(item)
    truth = dict(item.get("display_truth") or {})
    expected_util = _parse_util_value(truth.get("displayed_util"))
    expected_text = (
        f"Expected util: {expected_util:.2f}"
        if (
            is_resolved
            and expected_util is not None
            and str(truth.get("display_truth_source") or item.get("display_truth_source") or "") == "candidate_preview"
        )
        else ""
    )
    lines = [
        f"<div class='fast-guidance-reason'>{_design_guide_text_html('Change: ' + change_summary)}</div>",
        f"<div class='fast-guidance-reason'>{_design_guide_text_html(why_text)}</div>",
    ]
    if expected_text:
        lines.insert(1, f"<div class='fast-guidance-reason'>{_design_guide_text_html(expected_text)}</div>")
    if alt_text:
        lines.append(f"<div class='fast-guidance-secondary'>{_design_guide_text_html(alt_text)}</div>")
    return "".join(lines)


def _guidance_default_alternatives_text(state: dict, updates: dict, subfamilies: list[str]) -> str:
    sf = set(subfamilies or _compound_subfamilies_from_updates(updates))
    if sf >= {"geometry", "bottom_reo"}:
        d0, d1, w0, w1 = _compound_geometry_deltas(state, updates)
        if w1 > w0 + 0.5 and d1 <= d0 + 0.5:
            return "Other options: Increase depth instead, or use a different bottom reo layout."
        if d1 > d0 + 0.5 and w1 <= w0 + 0.5:
            return "Other options: Increase width instead, or use a different bottom reo layout."
        return "Other options: Use a geometry-first step, or a different bottom reo layout."
    if "shear" in sf:
        return "Other options: Tighten stirrup spacing, or increase the number of legs."
    if "geometry" in sf:
        return "Other options: Increase depth or section width."
    if "bottom_reo" in sf:
        return "Other options: Use a different bottom reo layout."
    return ""


def _geometry_trial_title_for_choice(base_title: str, g: dict, state: dict) -> str:
    upd = dict(g.get("updates") or {})
    if not upd:
        return base_title
    merged = _merge_guidance_state(state, upd)
    d0 = float(_float_from_state(state, "D", 0.0))
    d1 = float(_float_from_state(merged, "D", d0))
    wkey, _, w0 = _resolve_geometry_width_context(state)
    w0 = float(w0 or 0.0)
    w1 = float(upd.get(wkey, merged.get(wkey, w0)) or w0)
    if d1 < d0 - 1e-9 and w1 > w0 + 1e-9:
        return "Rebalance depth and width for bending"
    if d1 < d0 - 1e-9 and w1 <= w0 + 1e-9:
        return "Reduce depth slightly for bending"
    if w1 > w0 + 1e-9 and abs(d1 - d0) <= 1e-9:
        return "Increase width slightly for bending"
    if d1 > d0 + 1e-9 and w1 <= w0 + 1e-9:
        return "Increase depth for bending"
    if d1 > d0 + 1e-9 and w1 > w0 + 1e-9:
        return "Increase depth and width for bending"
    return base_title


def _shallower_beam_correction_trial_updates(state: dict) -> list[tuple[str, dict]]:
    seed = dict(state)
    wkey, _, w0 = _resolve_geometry_width_context(seed)
    w0 = float(w0 or 0.0)
    d0 = float(_float_from_state(seed, "D", 600.0))
    trials: list[tuple[str, dict]] = []
    for d_step in (50.0, 100.0):
        for w_add in (25.0, 50.0):
            new_d = d0 - d_step
            if new_d < 350.0:
                continue
            new_w = w0 + w_add
            tw = _geometry_state_with_updates(seed, depth=new_d, width=new_w)
            upd: dict[str, float] = {}
            if abs(float(tw.get("D", d0)) - d0) > 1e-9:
                upd["D"] = float(tw["D"])
            if wkey in tw and abs(float(tw[wkey]) - w0) > 1e-9:
                upd[wkey] = float(tw[wkey])
            if wkey != "b" and "b" in tw:
                upd["b"] = float(tw["b"])
            if len(upd) >= 2:
                trials.append(
                    (
                        f"Reduce depth ~{int(d_step)} mm and widen ~{int(w_add)} mm (shallower-beam correction)",
                        upd,
                    )
                )
    return trials


def _guidance_default_banner_title(action_type: str) -> str:
    mapping = {
        "apply_geometry_recommendation": "Adjust section geometry",
        "apply_bottom_recommendation": "Adjust bottom reinforcement",
        "apply_shear_recommendation": "Adjust shear reinforcement",
        "apply_compound_guidance": "Combined design update",
        "apply_resolved_candidate": "Apply one-click design",
        "apply_mode_recommendation": "Apply optimisation recommendation",
        "reduce_bottom_reinforcement": "Reduce bottom reinforcement",
        "tighten_geometry": "Tighten section geometry",
        "increase_link_spacing": "Increase link spacing",
        "reduce_number_of_legs": "Reduce number of shear legs",
        "increase_depth": "Increase beam depth",
        "increase_width": "Increase beam width",
        "reduce_link_spacing": "Reduce link spacing",
        "deflection_reduce_sustained_load": "Adjust sustained loads",
        "reduce_bar_spacing": "Reduce bar spacing",
        "guided_solve_step": "Guided design step",
    }
    return mapping.get(str(action_type or ""), "Design guide update")


def _prepare_guidance_apply_banner_meta(action_type: str, payload: dict | None) -> None:
    p = dict(payload or {})
    title = p.get("guidance_banner_title") or p.get("label")
    if not title:
        title = _guidance_default_banner_title(action_type)
    _pending_like = {
        "title": str(title),
        "action_type": str(action_type or ""),
        "action_payload": dict(p),
    }
    _apply_mode, _apply_payload = _effective_apply_mode_and_payload_from_pending(_pending_like)
    st.session_state[DESIGN_GUIDE_APPLY_BANNER_META_KEY] = {
        "title": str(title),
        "summary": p.get("guidance_banner_summary"),
        "action_type": str(action_type or ""),
        "recommendation_title": str(title),
        "recommendation_id": p.get("recommendation_id"),
        "recommendation_apply_mode": _apply_mode,
        "recommendation_apply_payload": dict(_apply_payload or {}),
        "fingerprint": st.session_state.get(DESIGN_GUIDE_PANEL_BASELINE_FP_KEY),
        "baseline_fingerprint": st.session_state.get(DESIGN_GUIDE_PANEL_BASELINE_FP_KEY),
    }


def _store_design_guide_apply_banner_payload(prior_state: dict, after_state: dict) -> None:
    _meta_raw = st.session_state.get(DESIGN_GUIDE_APPLY_BANNER_META_KEY)
    if not isinstance(_meta_raw, dict):
        return
    meta = dict(_meta_raw)
    title = meta.get("title") or _guidance_default_banner_title(str(meta.get("action_type") or ""))
    summary = meta.get("summary")
    change_lines = _guidance_apply_change_lines(prior_state, after_state)
    after_fp = _design_guide_cache_fingerprint(after_state)
    try:
        post_commit_overview = _collect_design_overview(after_state)
    except Exception:
        post_commit_overview = {}
    post_commit_truth = _design_guide_display_truth_for_item(
        None,
        state=after_state,
        overview=post_commit_overview,
        source_override="post_commit_truth",
    )
    st.session_state[DESIGN_GUIDE_APPLY_BANNER_META_KEY] = {
        **meta,
        "fingerprint": after_fp,
        "baseline_fingerprint": after_fp,
        "after_fingerprint": after_fp,
        "display_truth": dict(post_commit_truth),
    }
    st.session_state[DESIGN_GUIDE_APPLY_BANNER_KEY] = {
        "applied_at": datetime.now().isoformat(timespec="seconds"),
        "recommendation_title": str(title),
        "recommendation_summary": summary,
        "before": _design_guide_apply_snapshot(prior_state),
        "after": _design_guide_apply_snapshot(after_state),
        "change_lines": change_lines,
        "display_truth": dict(post_commit_truth),
    }


def _compound_geometry_deltas(state: dict, updates: dict) -> tuple[float, float, float, float]:
    _bind_compound_guidance_copy_dependencies(globals())
    return _compound_geometry_deltas_extracted(state, updates)


def _compound_guidance_title_reasoning_why(
    state: dict,
    updates: dict,
    subfamilies: list[str],
    *,
    strengthening: bool,
) -> tuple[str, str, str]:
    _bind_compound_guidance_copy_dependencies(globals())
    return _compound_guidance_title_reasoning_why_extracted(
        state,
        updates,
        subfamilies,
        strengthening=strengthening,
    )


_VAGUE_CANONICAL_TITLE_LABELS = frozenset(
    {
        "apply recommendation",
        "apply one-click design",
        "apply one-click recommendation",
        "optimisation available",
        "optimization available",
    },
)


def _infer_families_mentioned_in_label(label: str) -> frozenset[str]:
    """Heuristic: which compound update families does this string appear to describe."""
    if not str(label or "").strip():
        return frozenset()
    s = str(label).strip().lower()
    if s.startswith("trial:"):
        s = s.split(":", 1)[-1].strip()
    out: set[str] = set()
    # Shear link layout (e.g. "2-leg N10 @ 200")
    if re.search(r"\d+\s*-\s*leg", s) or re.search(r"\bn\s*\d+\s*@", s) or re.search(r"\bn\d+\s*@\s*\d+", s):
        out.add("shear")
    if "shear link" in s or "stirrup" in s or "link spacing" in s:
        out.add("shear")
    # Geometry
    if (
        "depth:" in s
        or "width:" in s
        or re.search(r"\d+\s*→\s*\d+", s)
        or "increase depth" in s
        or "increase width" in s
        or "section width" in s
        or "section depth" in s
    ):
        out.add("geometry")
    if re.search(r"\b\d+\s*x\s*\d+\s*mm\b", s):
        out.add("geometry")
    # Bottom reinforcement
    if ("bottom" in s and ("bar" in s or "reo" in s or "steel" in s or "reinforcement" in s)) or re.search(
        r"\b\d+\s*\+\s*\d+\s*x\s*n\d+",
        s,
    ):
        out.add("bottom_reo")
    return frozenset(out)


def _label_consistent_with_updates_families(label: str, expected: frozenset[str]) -> bool:
    """True if the label does not claim update families outside those implied by actual updates."""
    s = str(label or "").strip().lower()
    if not s:
        return False
    if s in _VAGUE_CANONICAL_TITLE_LABELS:
        return False
    mentioned = _infer_families_mentioned_in_label(label)
    if not mentioned:
        return True
    return mentioned <= expected


def _derived_guidance_title_from_updates(state: dict, updates: dict) -> str:
    """Human-facing title derived only from updates (compound helper + change lines)."""
    subfamilies = _compound_subfamilies_from_updates(updates)
    base = _guidance_state_snapshot(state or {})
    if len(subfamilies) >= 2:
        t, _, _ = _compound_guidance_title_reasoning_why(
            base,
            updates,
            subfamilies,
            strengthening=True,
        )
        dt = str(t or "").strip()
        if dt and dt != "Apply combined strengthening update":
            return dt
    lines = _guidance_change_lines_for_updates(base, updates)
    if lines:
        if len(lines) == 1:
            return str(lines[0]).strip()
        return _guidance_compact_change_text(lines[:2])
    if len(subfamilies) >= 2:
        t, _, _ = _compound_guidance_title_reasoning_why(
            base,
            updates,
            subfamilies,
            strengthening=True,
        )
        if str(t or "").strip():
            return str(t).strip()
    if len(subfamilies) == 1:
        return {
            "geometry": "Adjust section geometry",
            "bottom_reo": "Adjust bottom reinforcement",
            "shear": "Adjust shear reinforcement",
        }.get(subfamilies[0], "Apply recommendation")
    return "Apply recommendation"


def _resolve_canonical_guidance_title_from_candidate(
    candidate: dict,
    updates: dict,
    *,
    state: dict | None = None,
    spec_label: str | None = None,
    fallback_title: str = "",
) -> str:
    """
    Single source for Design Guide headlines when applying a winning/resolved candidate.

    Prefers spec/raw labels only when they do not claim the wrong update family (e.g. shear wording
    when updates are geometry-only). Otherwise derives from actual updates.

    Solver-selected winners set ``title_locked_from_final_winner`` + ``canonical_winner_label``;
    those labels must not be rewritten here.
    """
    if isinstance(candidate, dict) and bool(candidate.get("title_locked_from_final_winner")):
        locked = str(
            candidate.get("canonical_winner_label")
            or candidate.get("label")
            or fallback_title
            or "",
        ).strip()
        if locked:
            return locked
    updates = dict(updates or {})
    if not updates:
        ft = str(fallback_title or "").strip()
        return ft or "Apply recommendation"
    base_state = _guidance_state_snapshot(state or {})
    subfamilies = _compound_subfamilies_from_updates(updates)
    expected = frozenset(subfamilies)
    derived = _derived_guidance_title_from_updates(base_state, updates)

    ordered: list[str] = []
    for lab in (spec_label, (candidate or {}).get("label") if isinstance(candidate, dict) else None, fallback_title):
        if lab is None:
            continue
        s = str(lab).strip()
        if s and s not in ordered:
            ordered.append(s)

    for lab in ordered:
        if _label_consistent_with_updates_families(lab, expected):
            return lab.strip()
    return derived


def _compound_strengthening_viable(seed_candidate: dict, trial_candidate: dict | None) -> bool:
    if not trial_candidate:
        return False
    if bool(trial_candidate.get("is_compliant")):
        return True
    return is_valid_progress_while_failing(trial_candidate, seed_candidate)


def _efficiency_distance_to_target_band(worst: float, mode_config: dict | None = None) -> float:
    target_lo, target_hi, _ = _resolved_efficiency_target_band(mode_config, goal=_design_optimisation_goal())
    if target_lo <= worst <= target_hi:
        return 0.0
    if worst < target_lo:
        return target_lo - worst
    return worst - target_hi


def _compound_efficiency_incoherent(
    base_state: dict,
    trial_state: dict,
    seed_candidate: dict,
    trial_candidate: dict,
) -> bool:
    d0 = float(_float_from_state(base_state, "D", 0.0))
    d1 = float(_float_from_state(trial_state, "D", 0.0))
    _, _, w0 = _resolve_geometry_width_context(base_state)
    _, _, w1 = _resolve_geometry_width_context(trial_state)
    a0 = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    a1 = float(trial_candidate.get("Ast_bot", 0.0) or 0.0)
    if d1 > d0 + 1e-9 and a1 > a0 + 1e-9:
        return True
    if w1 > w0 + 1e-9 and d1 > d0 + 1e-9:
        return True
    return False


def _try_compound_strengthening_guidance_item(
    state: dict,
    overview: dict,
    primary_item: dict | None,
    *,
    compound_underdesign_debug: dict | None = None,
) -> dict | None:
    _bind_compound_strengthening_dependencies(globals())
    return _try_compound_strengthening_guidance_item_extracted(
        state,
        overview,
        primary_item,
        compound_underdesign_debug=compound_underdesign_debug,
    )


def _try_compound_efficiency_guidance_item(state: dict, efficiency_state: dict) -> dict | None:
    _bind_compound_strengthening_dependencies(globals())
    return _try_compound_efficiency_guidance_item_extracted(state, efficiency_state)


def _design_guide_focus_label(focus: str | None) -> str:
    mapping = {
        "bending": "Bending",
        "shear": "Shear",
        "geometry": "Geometry",
        "crack": "Crack control",
        "deflection": "Deflection",
        "general": "Overall design",
    }
    return mapping.get(str(focus or "general").strip().lower(), "Overall design")


def _optimisation_candidate_family(item: dict | None, state: dict | None = None) -> str:
    if not isinstance(item, dict):
        return "other"
    check_key = str(item.get("check_key") or "").strip().lower()
    action_type = str(item.get("action_type") or "").strip().lower()
    payload = dict(item.get("action_payload") or {})
    updates = _guidance_action_updates(action_type, payload, state=state or {}) if action_type else {}
    update_subfamilies = set(_compound_subfamilies_from_updates(updates))
    base_family = str(_design_guide_candidate_family(item) or "").strip().lower()
    return _resolve_design_guide_controller_optimisation_candidate_family(
        check_key=check_key,
        action_type=action_type,
        update_subfamilies=update_subfamilies,
        base_family=base_family,
    )


def _candidate_search_distance_to_band(util: object, target_low: float, target_high: float) -> float | None:
    return _candidate_search_distance_to_band_extracted(util, target_low, target_high)


def _candidate_search_summary_row(
    candidate: dict | None,
    *,
    index: int,
    target_low: float,
    target_high: float,
    fallback_title: str | None = None,
) -> dict:
    return _candidate_search_summary_row_extracted(
        candidate,
        index=index,
        target_low=target_low,
        target_high=target_high,
        fallback_title=fallback_title,
    )


def _build_candidate_search_evidence(
    *,
    selected_candidate: dict | None,
    all_candidates: list[dict],
    target_low: float,
    target_high: float,
    exhaustive: bool,
    search_scope: str,
    selected_title: str | None = None,
) -> dict:
    _bind_candidate_search_evidence_dependencies(globals())
    return _build_candidate_search_evidence_extracted(
        selected_candidate=selected_candidate,
        all_candidates=all_candidates,
        target_low=target_low,
        target_high=target_high,
        exhaustive=exhaustive,
        search_scope=search_scope,
        selected_title=selected_title,
    )


def _direct_target_band_guidance_item(
    state: dict,
    overview: dict | None,
    mode_config: dict,
    *,
    strengthening: bool,
    debug_sink: dict | None = None,
) -> dict | None:
    _bind_direct_target_band_guidance_dependencies(globals())
    return _direct_target_band_guidance_item_extracted(
        state,
        overview,
        mode_config,
        strengthening=strengthening,
        debug_sink=debug_sink,
    )


def _single_row_bottom_reo_updates(count: int, dia: int) -> dict:
    return _bottom_arrangement_to_shared_updates(
        {
            "bot1_count": int(count),
            "db_bot_1": int(dia),
            "bot2_count": 0,
            "db_bot_2": int(dia),
        }
    )


def _in_target_shear_congestion_reshape_guidance_item(
    state: dict,
    overview: dict | None,
    mode_config: dict,
    *,
    debug_sink: dict | None = None,
) -> dict | None:
    _bind_shear_congestion_reshape_dependencies(globals())
    return _in_target_shear_congestion_reshape_guidance_item_extracted(
        state,
        overview,
        mode_config,
        debug_sink=debug_sink,
    )


def _select_primary_optimisation_candidate(
    *,
    state: dict,
    overview: dict | None,
    mode_config: dict | None,
    governing_action: str,
    candidates: list[dict],
    overdesign_stepwise_band_fallback: bool = False,
) -> dict:
    _bind_primary_optimisation_selector_dependencies(globals())
    return _select_primary_optimisation_candidate_extracted(
        state=state,
        overview=overview,
        mode_config=mode_config,
        governing_action=governing_action,
        candidates=candidates,
        overdesign_stepwise_band_fallback=overdesign_stepwise_band_fallback,
    )


def _log_guidance_branch_governing_mismatch(
    *,
    guidance_branch: str,
    governing_action: str,
    primary_utils: dict[str, float | None],
    selected_item: dict | None,
) -> None:
    if not bool(st.session_state.get("_dev_mode")):
        return
    branch_name = str(guidance_branch or "")
    branch_action = branch_name
    for prefix in ("critical_", "efficiency_", "passing_guidance_"):
        if branch_name.startswith(prefix):
            branch_action = branch_name[len(prefix) :]
            break
    is_shear_branch = (
        "shear" in branch_name
        or _guidance_action_to_payload_name(branch_action) == "shear_tightening"
        or str((selected_item or {}).get("check_key") or "") == "shear"
    )
    if not is_shear_branch:
        return
    bending_util = primary_utils.get("bending")
    shear_util = primary_utils.get("shear")
    if bending_util is None or shear_util is None:
        return
    if float(shear_util) >= float(bending_util):
        return
    _agent_debug_log(
        "Shear branch selected while bending util exceeds shear util",
        {
            "guidance_branch": guidance_branch,
            "governing_action": governing_action,
            "bending_util": bending_util,
            "shear_util": shear_util,
            "selected_action_type": None if not selected_item else selected_item.get("action_type"),
            "selected_title": None if not selected_item else selected_item.get("title_main"),
        },
        location="inputs_page.py:_compute_design_guidance_items",
        hypothesis_id="H_GUIDANCE_GOVERNING",
    )


def _materialize_full_evaluated_candidate(candidate: dict | None, *, source: str) -> dict | None:
    if not candidate:
        return None
    candidate_state = dict(candidate.get("state") or {})
    if not candidate_state:
        return None
    full_candidate = evaluate_candidate_full(
        candidate_state,
        source=source,
        label=str(candidate.get("label") or source.replace("_", " ").title()),
        action_type=str(candidate.get("action_type") or ""),
        updates=dict(candidate.get("updates") or {}),
    )
    if full_candidate is None:
        return None
    for key in (
        "score",
        "reo_complexity",
        "guidance_preview_util",
        "arrangement",
        "actual_ast",
        "required_ast",
    ):
        if key in candidate:
            full_candidate[key] = candidate.get(key)
    return full_candidate


def _overview_debug_summary(state: dict, overview: dict | None) -> dict:
    resolved_overview = overview or {}
    bending_pack = ((resolved_overview.get("packs") or {}).get("bending") or {})
    utils = dict(resolved_overview.get("utils") or {})
    return {
        "bottom_reo_label": _bottom_reo_state_label(state),
        "Ast_bot": float((_effective_bottom_design_state(state) or {}).get("Ast_bot", 0.0) or 0.0),
        "summary_phiMu_kNm": float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0),
        "summary_Mu_star_kNm": float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0),
        "bending_util": None if utils.get("bending") is None else float(utils.get("bending")),
        "worst_util": float(resolved_overview.get("worst_util", 0.0) or 0.0),
        "governing_focus": _design_guide_focus_label(_governing_focus_from_overview(resolved_overview)),
        "design_guide_shear_truth_source": resolved_overview.get("design_guide_shear_truth_source"),
        "stage3_shear_truth_debug": resolved_overview.get("stage3_shear_truth_debug"),
        "stage3_remaining_issue_class": resolved_overview.get("stage3_remaining_issue_class"),
    }


_STAGE3_PUBLISHED_SHEAR_TRUTH_KEYS: tuple[str, ...] = (
    "shear_truth_status",
    "shear_truth_reason",
    "shear_truth_governing_check_name",
    "shear_truth_governing_reason",
    "shear_truth_governing_source",
    "final_shear_status_source",
    "final_shear_truth_resolved",
    "final_shear_truth_failure_reason",
    "final_shear_truth_bundle_complete",
    "shear_provided_input_spacing_mm",
    "shear_input_spacing_mm",
    "shear_sectional_check_spacing_mm",
    "shear_effective_spacing_mm",
    "shear_required_spacing_mm",
    "shear_governing_spacing_source",
    "published_result_spacing_mm",
    "published_result_spacing_meaning",
)


def _stage3_final_published_shear_truth_bundle(state: dict | None) -> dict:
    """Compact final published shear-truth slice for Design Guide / one-click tracing (session results)."""
    s = dict(state or {})
    out = {k: s.get(k) for k in _STAGE3_PUBLISHED_SHEAR_TRUTH_KEYS}
    out["design_guide_shear_truth_source"] = "final_published_shear_truth"
    out["final_shear_truth_normalized_source"] = s.get("_final_shear_truth_normalized_source")
    out["final_shear_truth_normalized_latest"] = dict(s.get("_final_shear_truth_normalized_latest") or {})
    return out


def _state_with_overrides(state: dict, **updates) -> dict:
    new_state = dict(state)
    new_state.update(updates)
    return new_state


def _state_with_resolved_design_actions_isolated(state: dict, actions: dict | None = None) -> dict:
    """Like _state_with_resolved_design_actions but does NOT merge st.session_state (candidate-only)."""
    resolved = dict(state)
    for key, default in SHARED_DEFAULTS.items():
        resolved.setdefault(key, default)
    actions = dict(actions or _resolve_design_actions_from_state(resolved))
    resolved["uls_Mstar"] = float(actions.get("Mu", _float_from_state(resolved, "uls_Mstar", 0.0)) or 0.0)
    resolved["uls_Vstar"] = float(actions.get("Vu", _float_from_state(resolved, "uls_Vstar", 0.0)) or 0.0)
    resolved["uls_Nstar"] = float(actions.get("Nu", _float_from_state(resolved, "uls_Nstar", 0.0)) or 0.0)
    resolved["Mu_star"] = float(actions.get("Mu", _float_from_state(resolved, "Mu_star", 0.0)) or 0.0)
    resolved["Vu_star"] = float(actions.get("Vu", _float_from_state(resolved, "Vu_star", 0.0)) or 0.0)
    resolved["N_star"] = float(actions.get("Nu", _float_from_state(resolved, "N_star", 0.0)) or 0.0)
    resolved["sls_Mstar"] = float(actions.get("SLS_M", _float_from_state(resolved, "sls_Mstar", 0.0)) or 0.0)
    resolved["uls_Mstar_pos_manual"] = float(
        _float_from_state(
            resolved,
            "uls_Mstar_pos_manual",
            max(0.0, _float_from_state(resolved, "uls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["uls_Mstar_neg_manual"] = float(
        _float_from_state(
            resolved,
            "uls_Mstar_neg_manual",
            max(0.0, -_float_from_state(resolved, "uls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Mstar_pos_manual"] = float(
        _float_from_state(
            resolved,
            "sls_Mstar_pos_manual",
            max(0.0, _float_from_state(resolved, "sls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Mstar_neg_manual"] = float(
        _float_from_state(
            resolved,
            "sls_Mstar_neg_manual",
            max(0.0, -_float_from_state(resolved, "sls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Vstar"] = float(actions.get("SLS_V", _float_from_state(resolved, "sls_Vstar", 0.0)) or 0.0)
    resolved["Tu_star"] = float(actions.get("Tu", _float_from_state(resolved, "Tu_star", 0.0)) or 0.0)
    resolved["P_star"] = float(actions.get("Pu", _float_from_state(resolved, "P_star", 0.0)) or 0.0)
    resolved["actions_uls"] = {
        "M": resolved["uls_Mstar"],
        "V": resolved["uls_Vstar"],
        "N": resolved["uls_Nstar"],
        "T": resolved["Tu_star"],
        "P": resolved["P_star"],
    }
    return resolved


def _build_design_actions_context_isolated(state: dict) -> dict:
    """Design actions + resolved ULS/SLS fields from the given dict only (no session overlay)."""
    source_state = dict(state)
    for key, default in SHARED_DEFAULTS.items():
        source_state.setdefault(key, default)
    actions = _resolve_design_actions_from_state(source_state)
    return {
        "state": _state_with_resolved_design_actions_isolated(source_state, actions),
        "actions": dict(actions),
        "action_signature": tuple(actions.get("signature", ())),
    }


def _generate_escalated_shear_states(state: dict, *, severity_band: str) -> list[tuple[str, dict]]:
    _bind_shear_candidate_generation_dependencies(globals())
    return _generate_escalated_shear_states_extracted(state, severity_band=severity_band)


def _candidate_state_with_effective_bottom_for_overview(
    candidate_state: dict,
    bottom_updates: dict | None,
) -> dict:
    """Merge effective bottom steel / d into flat state so build_bending_check_rows_from_state matches _evaluate_bending_with_bottom_state."""
    merged = dict(candidate_state)
    bs = _effective_bottom_design_state(candidate_state, bottom_updates)
    d_cent = float(bs.get("d_centroid", 0.0) or 0.0)
    if d_cent > 0.0:
        merged["d"] = d_cent
    nb = int(bs.get("nb_bot", 0) or 0)
    db = float(bs.get("db_bot", 0.0) or 0.0)
    if nb > 0 and db > 0.0:
        merged["Ast_bot"] = float(bs.get("Ast_bot", 0.0) or 0.0)
        merged["db_bot"] = db
        merged["nb_bot"] = nb
    return merged


def _candidate_changes_geometry(reference_state: dict | None, candidate_state: dict | None) -> bool:
    before = reference_state if isinstance(reference_state, dict) else {}
    after = candidate_state if isinstance(candidate_state, dict) else {}
    return any(before.get(key) != after.get(key) for key in PRIMARY_GEOMETRY_KEYS)


def _candidate_changes_local_variables(reference_state: dict | None, candidate_state: dict | None) -> bool:
    before = reference_state if isinstance(reference_state, dict) else {}
    after = candidate_state if isinstance(candidate_state, dict) else {}
    changed = [key for key in after.keys() if before.get(key) != after.get(key)]
    return any(key not in PRIMARY_GEOMETRY_KEYS for key in changed)


def _bending_demands_negligible(actions: dict | None) -> bool:
    if not isinstance(actions, dict):
        return False
    try:
        mu = abs(float(actions.get("Mu", 0.0) or 0.0))
    except (TypeError, ValueError):
        return False
    return mu <= GUIDANCE_BENDING_DEMAND_ABS_TOL_KNM + 1e-12


def _critical_case_name(candidate: dict | None) -> str:
    overview = ((candidate or {}).get("overview") or {})
    utils = dict(overview.get("utils") or {})
    ranked = []
    for key in ("bending", "shear", "crack", "deflection"):
        try:
            value = float(utils.get(key))
        except Exception:
            continue
        if not math.isnan(value):
            ranked.append((key, value))
    if not ranked:
        return "overall"
    ranked.sort(key=lambda item: item[1], reverse=True)
    return str(ranked[0][0])


def _critical_case_util(candidate: dict | None, case_name: str) -> float | None:
    overview = ((candidate or {}).get("overview") or {})
    raw = ((overview.get("utils") or {}).get(case_name))
    try:
        value = float(raw)
    except Exception:
        return None
    return None if math.isnan(value) else value


def _protected_case_min_util(
    protected_before: float | None,
    mode_config: dict,
) -> float:
    target_min = float(mode_config.get("target_util_min", 0.8) or 0.8)
    if protected_before is None:
        return target_min - 0.02
    return max(0.0, min(target_min, float(protected_before)) - 0.02)


def _candidate_reduces_noncritical_provision(candidate: dict, reference_candidate: dict) -> bool:
    if not candidate or not reference_candidate:
        return False
    if float(candidate.get("Ast_bot", 0.0) or 0.0) < float(reference_candidate.get("Ast_bot", 0.0) or 0.0) - 1e-6:
        return True
    if float(candidate.get("shear_density", 0.0) or 0.0) < float(reference_candidate.get("shear_density", 0.0) or 0.0) - 1e-6:
        return True
    if float(candidate.get("reo_complexity", compute_reo_complexity(candidate)) or 0.0) < float(reference_candidate.get("reo_complexity", compute_reo_complexity(reference_candidate)) or 0.0) - 1e-6:
        return True
    return False


def _candidate_preserves_protected_case(
    candidate: dict,
    protected_case: str,
    *,
    protected_min_util: float,
) -> bool:
    if not candidate or not bool(candidate.get("is_compliant")):
        return False
    protected_util = _critical_case_util(candidate, protected_case)
    if protected_util is None:
        return False
    if protected_util > 1.0 + 1e-9:
        return False
    return protected_util >= protected_min_util - 1e-9


def _cleanup_candidate_debug_payload(
    candidate: dict,
    reference_candidate: dict,
    protected_case: str,
    *,
    accepted: bool,
    reason: str,
) -> dict:
    geometry_changed = _candidate_changes_geometry(reference_candidate.get("state"), candidate.get("state"))
    local_changed = _candidate_changes_local_variables(reference_candidate.get("state"), candidate.get("state"))
    return {
        "candidate_label": str(candidate.get("label") or ""),
        "variables_changed": sorted(list((candidate.get("updates") or {}).keys())),
        "candidate_type": "geometry_fallback" if geometry_changed else "local_cleanup",
        "geometry_changed": geometry_changed,
        "local_changed": local_changed,
        "protected_case": protected_case,
        "protected_util_before": _critical_case_util(reference_candidate, protected_case),
        "protected_util_after": _critical_case_util(candidate, protected_case),
        "overall_worst_util": float(candidate.get("worst_util", 0.0) or 0.0),
        "accepted": bool(accepted),
        "reason": reason,
    }


def _one_click_mixed_direction_classification(
    eval_obj: dict | None,
    mode_config: dict,
    *,
    overdesign_margin: float = 0.03,
) -> str | None:
    """Classify true mixed-direction states using existing domain score semantics."""
    bending = _one_click_domain_score(eval_obj, "bending", mode_config)
    shear = _one_click_domain_score(eval_obj, "shear", mode_config)
    try:
        lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    except Exception:
        lo = float(EFFICIENCY_TARGET_UTIL_MIN)
    margin = float(max(0.0, overdesign_margin))
    state = dict((eval_obj or {}).get("state") or {})
    try:
        actions_ctx = _build_design_actions_context_isolated(state)
        actions = dict(actions_ctx.get("actions") or {})
    except Exception:
        actions = {}

    def _materially_over(score: dict) -> bool:
        util = score.get("util")
        try:
            fu = float(util)
        except (TypeError, ValueError):
            return False
        return bool(score.get("pass") and fu < (lo - margin))

    if (
        (not bool(bending.get("pass")))
        and _materially_over(shear)
        and not _shear_demands_negligible(actions)
    ):
        return "bending_under_shear_over"
    if (
        (not bool(shear.get("pass")))
        and _materially_over(bending)
        and not _bending_demands_negligible(actions)
    ):
        return "bending_over_shear_under"
    return None


def _one_click_mixed_direction_rank_adjustment(
    cur_eval: dict | None,
    candidate_eval: dict | None,
    mixed_mode: str | None,
    mode_config: dict,
    *,
    primary_improvement_margin: float = 0.02,
) -> dict:
    """Ranking overlay for mixed-direction cases: fix the failing side first."""
    if mixed_mode == "bending_under_shear_over":
        primary_domain = "bending"
        secondary_domain = "shear"
    elif mixed_mode == "bending_over_shear_under":
        primary_domain = "shear"
        secondary_domain = "bending"
    else:
        return {
            "active": False,
            "mixed_mode": None,
            "primary_domain": None,
            "secondary_domain": None,
            "primary_material_improvement": False,
            "primary_distance": float("inf"),
            "secondary_distance": float("inf"),
            "current_secondary_distance": float("inf"),
        }

    current_primary = _one_click_domain_score(cur_eval, primary_domain, mode_config)
    candidate_primary = _one_click_domain_score(candidate_eval, primary_domain, mode_config)
    current_secondary = _one_click_domain_score(cur_eval, secondary_domain, mode_config)
    candidate_secondary = _one_click_domain_score(candidate_eval, secondary_domain, mode_config)

    current_primary_pass = bool(current_primary.get("pass"))
    candidate_primary_pass = bool(candidate_primary.get("pass"))
    current_primary_distance = float(current_primary.get("distance", float("inf")) or float("inf"))
    candidate_primary_distance = float(candidate_primary.get("distance", float("inf")) or float("inf"))
    current_secondary_distance = float(current_secondary.get("distance", float("inf")) or float("inf"))
    candidate_secondary_distance = float(candidate_secondary.get("distance", float("inf")) or float("inf"))
    margin = float(max(0.0, primary_improvement_margin))

    primary_material_improvement = bool(
        (candidate_primary_pass and not current_primary_pass)
        or (
            math.isfinite(current_primary_distance)
            and math.isfinite(candidate_primary_distance)
            and candidate_primary_distance <= (current_primary_distance - margin)
        )
    )

    return {
        "active": True,
        "mixed_mode": mixed_mode,
        "primary_domain": primary_domain,
        "secondary_domain": secondary_domain,
        "primary_material_improvement": primary_material_improvement,
        "primary_distance": candidate_primary_distance,
        "secondary_distance": candidate_secondary_distance if primary_material_improvement else current_secondary_distance,
        "current_secondary_distance": current_secondary_distance,
    }


def _one_click_seed_target_domains_from_eval(eval_obj: dict | None, mode_config: dict) -> list[str]:
    """
    Domains that must be kept honest for target-band decisions at the current state.

    Rescue and optimise must stay separated at the seed boundary:

    - if any published domain is FAIL, one-click is in rescue mode and the required
      domains are only the currently failing ones
    - only when the design already passes code checks do we keep out-of-band passing
      domains active so optimisation-mode cleanup does not disappear
    """
    if not isinstance(eval_obj, dict):
        return []
    scores = {
        domain: _one_click_domain_score(eval_obj, domain, mode_config)
        for domain in ("bending", "shear")
    }
    failing = [
        domain
        for domain, score in scores.items()
        if not bool(score.get("pass"))
    ]
    if failing:
        return failing

    out: list[str] = []
    for domain in ("bending", "shear"):
        score = scores.get(domain) or {}
        if bool(score.get("in_band")):
            continue
        out.append(domain)
    return out


RESCUE_MODE_TIER_ORDER = ("medium", "high", "very_high", "extreme")


RESCUE_SEED_LIBRARY = {
    "bending": {
        "medium": {
            "key": "bending_medium",
            "updates": _make_rescue_seed_updates(
                b=350.0, D=600.0, top_count=2, top_dia=16, bottom_count=4, bottom_dia=24, lig_d=12, lig_legs=2, s_lig=150.0
            ),
            "intended_action_range": {"Mu": [250.0, 400.0], "Vu": [0.0, 400.0]},
            "intended_util_range": [1.5, 3.0],
        },
        "high": {
            "key": "bending_high",
            "updates": _make_rescue_seed_updates(
                b=400.0, D=700.0, top_count=2, top_dia=20, bottom_count=5, bottom_dia=28, lig_d=12, lig_legs=2, s_lig=125.0
            ),
            "intended_action_range": {"Mu": [400.0, 650.0], "Vu": [0.0, 650.0]},
            "intended_util_range": [3.0, 6.0],
        },
        "very_high": {
            "key": "bending_very_high",
            "updates": _make_rescue_seed_updates(
                b=450.0, D=800.0, top_count=2, top_dia=20, bottom_count=6, bottom_dia=28, lig_d=12, lig_legs=4, s_lig=125.0
            ),
            "intended_action_range": {"Mu": [650.0, 850.0], "Vu": [0.0, 850.0]},
            "intended_util_range": [6.0, 10.0],
        },
        "extreme": {
            "key": "bending_extreme",
            "updates": _make_rescue_seed_updates(
                b=500.0, D=900.0, top_count=2, top_dia=24, bottom_count=6, bottom_dia=32, lig_d=16, lig_legs=4, s_lig=100.0
            ),
            "intended_action_range": {"Mu": [850.0, 1000.0], "Vu": [0.0, 1000.0]},
            "intended_util_range": [10.0, None],
        },
    },
    "shear": {
        "medium": {
            "key": "shear_medium",
            "updates": _make_rescue_seed_updates(
                b=350.0, D=600.0, top_count=2, top_dia=16, bottom_count=4, bottom_dia=24, lig_d=12, lig_legs=4, s_lig=125.0
            ),
            "intended_action_range": {"Mu": [0.0, 400.0], "Vu": [250.0, 400.0]},
            "intended_util_range": [1.5, 3.0],
        },
        "high": {
            "key": "shear_high",
            "updates": _make_rescue_seed_updates(
                b=400.0, D=700.0, top_count=2, top_dia=20, bottom_count=5, bottom_dia=28, lig_d=16, lig_legs=4, s_lig=100.0
            ),
            "intended_action_range": {"Mu": [0.0, 650.0], "Vu": [400.0, 650.0]},
            "intended_util_range": [3.0, 6.0],
        },
        "very_high": {
            "key": "shear_very_high",
            "updates": _make_rescue_seed_updates(
                b=450.0, D=800.0, top_count=2, top_dia=20, bottom_count=5, bottom_dia=32, lig_d=16, lig_legs=6, s_lig=100.0
            ),
            "intended_action_range": {"Mu": [0.0, 850.0], "Vu": [650.0, 850.0]},
            "intended_util_range": [6.0, 10.0],
        },
        "extreme": {
            "key": "shear_extreme",
            "updates": _make_rescue_seed_updates(
                b=500.0, D=900.0, top_count=2, top_dia=24, bottom_count=6, bottom_dia=32, lig_d=20, lig_legs=6, s_lig=75.0
            ),
            "intended_action_range": {"Mu": [0.0, 1000.0], "Vu": [850.0, 1000.0]},
            "intended_util_range": [10.0, None],
        },
    },
    "combined": {
        "medium": {
            "key": "combined_medium",
            "updates": _make_rescue_seed_updates(
                b=400.0, D=650.0, top_count=2, top_dia=20, bottom_count=5, bottom_dia=24, lig_d=12, lig_legs=4, s_lig=125.0
            ),
            "intended_action_range": {"Mu": [300.0, 450.0], "Vu": [250.0, 400.0]},
            "intended_util_range": [1.5, 3.0],
        },
        "high": {
            "key": "combined_high",
            "updates": _make_rescue_seed_updates(
                b=450.0, D=750.0, top_count=2, top_dia=20, bottom_count=5, bottom_dia=28, lig_d=16, lig_legs=4, s_lig=100.0
            ),
            "intended_action_range": {"Mu": [450.0, 650.0], "Vu": [400.0, 650.0]},
            "intended_util_range": [3.0, 6.0],
        },
        "very_high": {
            "key": "combined_very_high",
            "updates": _make_rescue_seed_updates(
                b=500.0, D=850.0, top_count=2, top_dia=24, bottom_count=6, bottom_dia=28, lig_d=16, lig_legs=6, s_lig=100.0
            ),
            "intended_action_range": {"Mu": [650.0, 850.0], "Vu": [650.0, 850.0]},
            "intended_util_range": [6.0, 10.0],
        },
        "extreme": {
            "key": "combined_extreme",
            "updates": _make_rescue_seed_updates(
                b=550.0, D=950.0, top_count=2, top_dia=24, bottom_count=6, bottom_dia=32, lig_d=20, lig_legs=6, s_lig=75.0
            ),
            "intended_action_range": {"Mu": [850.0, 1000.0], "Vu": [850.0, 1000.0]},
            "intended_util_range": [10.0, None],
        },
    },
}


def _rescue_mode_action_tier(state: dict, family: str) -> str | None:
    mu = abs(float(_uls_action_from_state(state, "M") or 0.0))
    vu = abs(float(_uls_action_from_state(state, "V") or 0.0))
    action_value = mu
    if family == "shear":
        action_value = vu
    elif family == "combined":
        action_value = max(mu, vu)
    if action_value >= 850.0:
        return "extreme"
    if action_value >= 650.0:
        return "very_high"
    if action_value >= 400.0:
        return "high"
    if action_value >= 250.0:
        return "medium"
    return None


def _rescue_mode_util_tier(eval_obj: dict | None) -> str | None:
    util = _candidate_objective_util(eval_obj or {})
    try:
        u = float(util)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(u):
        return None
    if u > 10.0:
        return "extreme"
    if u >= 6.0:
        return "very_high"
    if u >= 3.0:
        return "high"
    if u >= 1.5:
        return "medium"
    return None


def _rescue_mode_both_domains_fail_meanfully(eval_obj: dict | None, mode_config: dict) -> bool:
    bend = _one_click_domain_score(eval_obj, "bending", mode_config)
    shear = _one_click_domain_score(eval_obj, "shear", mode_config)
    bend_fail = not bool(bend.get("pass"))
    shear_fail = not bool(shear.get("pass"))
    try:
        bend_util = float(bend.get("util"))
    except (TypeError, ValueError):
        bend_util = None
    try:
        shear_util = float(shear.get("util"))
    except (TypeError, ValueError):
        shear_util = None
    return bool(
        bend_fail
        and shear_fail
        and bend_util is not None
        and shear_util is not None
        and math.isfinite(bend_util)
        and math.isfinite(shear_util)
        and bend_util >= 1.10
        and shear_util >= 1.10
    )


def _rescue_mode_choose_family(eval_obj: dict | None, mode_config: dict) -> str | None:
    bend = _one_click_domain_score(eval_obj, "bending", mode_config)
    shear = _one_click_domain_score(eval_obj, "shear", mode_config)
    bend_fail = not bool(bend.get("pass"))
    shear_fail = not bool(shear.get("pass"))
    if _rescue_mode_both_domains_fail_meanfully(eval_obj, mode_config):
        return "combined"
    if bend_fail and not shear_fail:
        return "bending"
    if shear_fail and not bend_fail:
        return "shear"
    return None


def _rescue_mode_choose_tier(state: dict, eval_obj: dict | None, family: str) -> str | None:
    action_tier = _rescue_mode_action_tier(state, family)
    util_tier = _rescue_mode_util_tier(eval_obj)
    indices = [
        RESCUE_MODE_TIER_ORDER.index(tier)
        for tier in (action_tier, util_tier)
        if tier in RESCUE_MODE_TIER_ORDER
    ]
    if not indices:
        return None
    return RESCUE_MODE_TIER_ORDER[max(indices)]


def _rescue_mode_seed_order(requested_tier: str | None) -> list[str]:
    if requested_tier not in RESCUE_MODE_TIER_ORDER:
        return []
    if requested_tier == "extreme":
        return ["very_high", "extreme"]
    idx = RESCUE_MODE_TIER_ORDER.index(requested_tier)
    out = list(RESCUE_MODE_TIER_ORDER[idx:])
    if "extreme" in out and requested_tier != "very_high":
        return [tier for tier in out if tier != "extreme"] + ["extreme"]
    return out


def _rescue_mode_current_beam_plausible(state: dict, *, family: str, tier: str | None) -> bool:
    if tier not in RESCUE_MODE_TIER_ORDER:
        return True
    seed = dict(((RESCUE_SEED_LIBRARY.get(family) or {}).get(tier)) or {})
    updates = dict(seed.get("updates") or {})
    try:
        cur_b = float(state.get("b", 0.0) or 0.0)
        cur_D = float(state.get("D", 0.0) or 0.0)
        seed_b = float(updates.get("b", 0.0) or 0.0)
        seed_D = float(updates.get("D", 0.0) or 0.0)
    except (TypeError, ValueError):
        return False
    if seed_b <= 0.0 or seed_D <= 0.0:
        return False
    return bool(cur_b >= 0.85 * seed_b and cur_D >= 0.85 * seed_D)


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
    _bind_rescue_mode_gate_dependencies(globals())
    return _rescue_mode_should_enter_extracted(
        state=state,
        init_eval=init_eval,
        final_eval=final_eval,
        final_pass=final_pass,
        final_updates=final_updates,
        stop_reason=stop_reason,
        mode_config=mode_config,
    )


def _rescue_mode_path_improved(rescue_eval: dict | None, base_eval: dict | None, mode_config: dict) -> bool:
    if not isinstance(rescue_eval, dict) or not isinstance(base_eval, dict):
        return False
    return bool(_one_click_step_improves(rescue_eval, base_eval, mode_config))


def _one_click_domain_total_distance(eval_obj: dict | None, mode_config: dict) -> float:
    return _resolve_candidate_domain_total_distance(
        eval_obj,
        mode_config,
        default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
        default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
        fail_status=BEAM_STATUS_FAIL,
        optimisation_goal_resolver=_design_optimisation_goal,
    )


def _one_click_domain_max_distance(eval_obj: dict | None, mode_config: dict) -> float:
    return _resolve_candidate_domain_max_distance(
        eval_obj,
        mode_config,
        default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
        default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
        fail_status=BEAM_STATUS_FAIL,
        optimisation_goal_resolver=_design_optimisation_goal,
    )


def _one_click_domain_needs_cleanup(eval_obj: dict | None, domain: str, mode_config: dict) -> bool:
    score = _one_click_domain_score(eval_obj, domain, mode_config)
    return bool(score.get("pass") and score.get("under"))


def _one_click_bending_outcome_materially_preserved(
    current_eval: dict | None,
    candidate_eval: dict | None,
    mode_config: dict,
    *,
    distance_tolerance: float = 0.015,
) -> bool:
    current_bending = _one_click_domain_score(current_eval, "bending", mode_config)
    candidate_bending = _one_click_domain_score(candidate_eval, "bending", mode_config)
    if bool(current_bending.get("pass")) and not bool(candidate_bending.get("pass")):
        return False
    current_distance = float(current_bending.get("distance", float("inf")))
    candidate_distance = float(candidate_bending.get("distance", float("inf")))
    if not math.isfinite(current_distance):
        current_distance = float("inf")
    if not math.isfinite(candidate_distance):
        return False
    return bool(candidate_distance <= current_distance + float(max(distance_tolerance, 0.0)))


def _one_click_in_band_shear_cleanup_deferral(
    state: dict,
    eval_obj: dict | None,
    mode_config: dict,
) -> dict:
    snap = _guidance_state_snapshot(dict(state or {}))
    overview = dict((eval_obj or {}).get("overview") or {})
    actions_ctx = _build_design_actions_context_isolated(snap)
    actions = dict(actions_ctx.get("actions") or {})
    result = {
        "active": False,
        "reason": "not_applicable",
        "recommendation": None,
        "candidate_eval": None,
    }
    if not _shear_reinforcement_is_active(snap):
        result["reason"] = "inactive_links"
        return result
    shear_non_governing = bool(
        _shear_demands_negligible(actions)
        or _governing_focus_from_overview(overview) != "shear"
    )
    if not shear_non_governing:
        result["reason"] = "shear_still_governing"
        return result

    rec = _compute_shear_tightening_recommendation(snap, out_debug={})
    if not isinstance(rec, dict) or not dict(rec.get("updates") or {}):
        result["reason"] = "no_legal_shear_cleanup_path"
        return result

    updates = dict(rec.get("updates") or {})
    if not bool(set(updates) & _COMPOUND_SHEAR_UPDATE_KEYS):
        result["reason"] = "cleanup_not_shear_only"
        return result

    trial_state = dict(snap)
    trial_state.update(updates)
    candidate_eval = evaluate_candidate_full(
        _guidance_state_snapshot(trial_state),
        source="one_click_in_band_shear_cleanup_probe",
        updates=updates,
    )
    if candidate_eval is None or not bool((candidate_eval.get("overview") or {}).get("all_key_pass")):
        result["reason"] = "cleanup_candidate_not_all_pass"
        return result
    if not _one_click_bending_outcome_materially_preserved(eval_obj, candidate_eval, mode_config):
        result["reason"] = "cleanup_worsens_bending_materially"
        return result

    result.update(
        {
            "active": True,
            "reason": "blocked_non_governing_shear_cleanup_available",
            "recommendation": dict(rec),
            "candidate_eval": candidate_eval,
        },
    )
    return result


def _one_click_in_band_shear_cleanup_candidate_allowed(
    current_eval: dict | None,
    candidate_eval: dict | None,
    updates: dict | None,
    mode_config: dict,
) -> bool:
    resolved_updates = dict(updates or {})
    if not bool(set(resolved_updates) & _COMPOUND_SHEAR_UPDATE_KEYS):
        return False
    if not bool((candidate_eval or {}).get("overview", {}).get("all_key_pass")):
        return False
    if not _candidate_in_target_band(candidate_eval or {}, mode_config):
        return False
    return _one_click_bending_outcome_materially_preserved(current_eval, candidate_eval, mode_config)


def _one_click_best_next_hop_improving_candidate(
    current_eval: dict | None,
    mode_config: dict,
) -> dict | None:
    precheck = _resolve_target_band_next_hop_precheck(
        current_eval,
        mode_config,
        default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
        default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
        fail_status=BEAM_STATUS_FAIL,
        optimisation_goal_resolver=_design_optimisation_goal,
    )
    if not bool(precheck.get("allowed")):
        return None
    overview = dict(precheck.get("overview") or {})
    current_distance = precheck.get("current_distance")
    current_state = dict(precheck.get("current_state") or {})
    current_target_domains = list(_candidate_target_domains_for_band(current_eval) or [])
    context = _build_auto_design_context(
        current_state,
        mode_config,
        reference_overview=overview,
    )
    candidate_states = generate_compliant_refinement_candidates(current_eval, mode_config, context)
    return _select_best_target_band_refinement_candidate(
        candidate_states=candidate_states,
        current_eval=current_eval,
        current_state=current_state,
        current_distance=current_distance,
        current_target_domains=current_target_domains,
        mode_config=mode_config,
        state_pack_fn=_build_canonical_design_state_pack,
        evaluator_fn=evaluate_candidate_full,
        target_domain_attachment_fn=_one_click_attach_eval_target_domains,
        spacing_envelope_fail_fn=_one_click_has_unresolved_spacing_envelope_fail,
        source="one_click_budget_stop_probe",
        label="Budget stop probe",
        action_type="one_click",
        default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
        default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
        fail_status=BEAM_STATUS_FAIL,
        optimisation_goal_resolver=_design_optimisation_goal,
    )


def _one_click_budget_stop_has_better_next_hop(
    current_eval: dict | None,
    mode_config: dict,
) -> bool:
    return _one_click_best_next_hop_improving_candidate(current_eval, mode_config) is not None


def _one_click_exhaustion_next_hop_allowed(
    current_eval: dict | None,
    next_hop_payload: dict | None,
    mode_config: dict,
) -> bool:
    return bool(
        _resolve_target_band_exhaustion_refinement_allowed(
            current_eval,
            next_hop_payload,
            mode_config,
            default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
            default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
            fail_status=BEAM_STATUS_FAIL,
            optimisation_goal_resolver=_design_optimisation_goal,
        )
    )


def _candidate_target_band_distance(candidate: dict, mode_config: dict) -> float:
    domains = _candidate_target_domains_for_band(candidate)
    if not domains:
        return _one_click_objective_distance_to_band(_candidate_objective_util(candidate), mode_config)
    return _one_click_domain_max_distance(candidate, mode_config)


def _candidate_target_band_total_distance(candidate: dict, mode_config: dict) -> float:
    return _one_click_domain_total_distance(candidate, mode_config)


def _candidate_target_band_under_domains(candidate: dict, mode_config: dict, *, margin: float = 0.0) -> bool:
    domains = _candidate_target_domains_for_band(candidate)
    if not domains:
        return False
    try:
        lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    except Exception:
        lo = float(EFFICIENCY_TARGET_UTIL_MIN)
    m = float(max(0.0, margin))
    for dom in domains:
        u = _candidate_domain_util(candidate, dom)
        if u is None or not math.isfinite(float(u)):
            continue
        if float(u) < lo - m:
            return True
    return False


def _candidate_target_domain_needing_work(candidate: dict, mode_config: dict) -> str:
    domains = _candidate_target_domains_for_band(candidate)
    if not domains:
        return ""
    scored: list[tuple[int, float, int, str]] = []
    for dom in domains:
        score = _one_click_domain_score(candidate, dom, mode_config)
        if bool(score.get("in_band")):
            continue
        try:
            dist = float(score.get("distance"))
        except (TypeError, ValueError):
            dist = float("inf")
        if not math.isfinite(dist):
            dist = float("inf")
        status_weight = 1 if not bool(score.get("pass")) else 0
        order_weight = 1 if str(dom).strip().lower() == "shear" else 0
        scored.append((status_weight, dist, order_weight, str(dom).strip().lower()))
    if scored:
        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return scored[0][3]
    return ""


def _candidate_in_target_zone(candidate: dict, mode_config: dict) -> bool:
    if not candidate:
        return False
    if not bool(candidate.get("is_compliant")):
        return False

    util = float(candidate.get("worst_util", 0.0) or 0.0)
    target_min = float(mode_config.get("target_util_min", 0.80) or 0.80)
    target_max = float(mode_config.get("target_util_max", 0.90) or 0.90)
    return target_min <= util <= target_max


def _reinforcement_options_remain(state: dict) -> bool:
    count_1 = _int_from_state(state, "bot1_count", 0)
    count_2 = _int_from_state(state, "bot2_count", 0)
    dia_1 = _int_from_state(state, "db_bot_1", 0)
    dia_2 = _int_from_state(state, "db_bot_2", dia_1 or 0)
    can_increase_bar_count = count_1 < max(REO_COUNTS_0_12)
    can_grow_second_row = count_2 < max(REO_COUNTS_0_12)
    can_add_row = count_1 > 0 and count_2 <= 0
    can_increase_bar_dia = dia_1 < max(REO_BAR_DIAS) or dia_2 < max(REO_BAR_DIAS)
    can_rebalance = count_1 > 2 and count_1 != count_2
    return any((
        can_increase_bar_count,
        can_grow_second_row,
        can_add_row,
        can_increase_bar_dia,
        can_rebalance,
    ))


def _generate_shear_candidates(state: dict, mode_config: dict) -> list[dict]:
    _bind_shear_candidate_generation_dependencies(globals())
    return _generate_shear_candidates_extracted(state, mode_config)


def _shear_governing_fallback_resolved_candidate(state: dict, mode_cfg: dict) -> dict | None:
    """
    When bounded geometry+bottom one-click finds nothing but shear governs, pick the best
    compliant option from the same shear enumeration used elsewhere so the guide can show
    apply_resolved_candidate + post-apply util (not only reduce_link_spacing steps).
    """
    if not isinstance(state, dict):
        return None
    evaluated_list = _generate_shear_candidates(state, mode_cfg)
    compliant = [c for c in evaluated_list if isinstance(c, dict) and bool(c.get("is_compliant"))]
    if not compliant:
        return None

    def _rank(c: dict) -> tuple[float, float]:
        try:
            wu = float(c.get("worst_util", 999.0) or 999.0)
        except (TypeError, ValueError):
            wu = 999.0
        su_raw = ((c.get("overview") or {}).get("utils") or {}).get("shear")
        try:
            su = float(su_raw) if su_raw is not None else wu
        except (TypeError, ValueError):
            su = wu
        return (wu, su)

    best = sorted(compliant, key=_rank)[0]
    merged_updates = dict(best.get("updates") or {})
    if not merged_updates:
        return None
    _annotate_candidate_target_band_metrics(best, mode_cfg)
    resolved = dict(best)
    post_util = best.get("candidate_post_util", best.get("worst_util"))
    try:
        post_util = float(post_util) if post_util is not None else None
    except (TypeError, ValueError):
        post_util = None
    tmin = float(mode_cfg.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    tmax = float(mode_cfg.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    reaches_band = bool(post_util is not None and tmin <= post_util <= tmax)
    resolved["candidate_reaches_target_band"] = reaches_band
    resolved["reaches_target_band"] = reaches_band
    resolved["updates"] = merged_updates
    resolved["action_type"] = "apply_resolved_candidate"
    resolved["guidance_change_lines"] = _guidance_change_lines_for_updates(state, merged_updates)
    subfamilies = _compound_subfamilies_from_updates(merged_updates)
    resolved["subfamilies"] = list(subfamilies)
    resolved["recommendation_family_tag"] = _family_tag_from_compound_updates(merged_updates, state)
    title, _, _ = _compound_guidance_title_reasoning_why(
        state,
        merged_updates,
        subfamilies,
        strengthening=True,
    )
    resolved["label"] = str(title or best.get("label") or "Apply shear reinforcement upgrade")
    return resolved


def _guidance_objective_util_from_overview(overview: dict, goal: str) -> float | None:
    utils = dict((overview or {}).get("utils") or {})
    bend_pack = ((overview or {}).get("packs") or {}).get("bending") or {}
    phi_m = float(bend_pack.get("summary_phiMu_kNm", 0.0) or 0.0)
    mu_m = float(bend_pack.get("summary_Mu_star_kNm", 0.0) or 0.0)
    bend_demand = (mu_m / phi_m) if phi_m > 1e-9 else None
    if goal == "less_shear_reinforcement":
        value = utils.get("shear")
        return None if value is None else float(value)
    candidates = [value for value in (bend_demand, utils.get("bending"), utils.get("shear")) if value is not None]
    if not candidates:
        return None
    return max(float(value) for value in candidates)


def _mode_recommendation_expected_bend_util(mode_tighten: dict | None) -> float | None:
    """Mu*/φMu for the recommended trial; avoids stale objective_util / worst_util."""
    if not isinstance(mode_tighten, dict):
        return None
    for key in ("expected_util", "real_util"):
        raw = mode_tighten.get(key)
        if raw is None:
            continue
        try:
            v = float(raw)
        except Exception:
            continue
        if not math.isnan(v):
            return v
    cs = mode_tighten.get("candidate_summary") or {}
    phi_m = float(cs.get("summary_phiMu_kNm", 0.0) or 0.0)
    mu_m = float(cs.get("summary_Mu_star_kNm", 0.0) or 0.0)
    if phi_m > 1e-9:
        return mu_m / phi_m
    return None


def _mode_guidance_focus_from_updates(updates: dict) -> str:
    geometry_keys = {"D", "b", "bw", "tw"}
    bottom_keys = {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    }
    shear_keys = {"lig_d", "lig_legs", "s_lig"}
    if any(key in updates for key in geometry_keys):
        return "geometry"
    if any(key in updates for key in bottom_keys):
        return "bending"
    if any(key in updates for key in shear_keys):
        return "shear"
    return "general"


def _guidance_action_to_payload_name(action_type: str) -> str | None:
    mapping = {
        "apply_mode_recommendation": "mode_tightening",
        "apply_bottom_recommendation": "bottom_tightening",
        "apply_geometry_recommendation": "geometry_tightening",
        "apply_shear_recommendation": "shear_tightening",
        "reduce_bottom_reinforcement": "bottom_tightening",
        "reduce_bar_spacing": "bottom_tightening",
        "tighten_geometry": "geometry_tightening",
        "increase_depth": "geometry_tightening",
        "increase_width": "geometry_tightening",
        "reduce_link_spacing": "shear_tightening",
        "increase_link_spacing": "shear_tightening",
        "reduce_number_of_legs": "shear_tightening",
        "deflection_reduce_sustained_load": "general",
    }
    return mapping.get(str(action_type or ""))


def _is_design_guide_good_utilisation_band(util: object) -> bool:
    if util is None:
        return False
    try:
        u = float(util)
    except (TypeError, ValueError):
        return False
    return (not math.isnan(u)) and 0.80 <= u <= 0.95


def _is_design_guide_terminal_safe_item(item: dict) -> bool:
    _ts = str(item.get("design_guide_terminal_state") or "").strip()
    if _ts in ("optimal", "very_low_demand"):
        return True
    title = str(item.get("title_main") or "")
    primary = str(item.get("primary_action") or "")
    hay = f"{title} {primary}".lower()
    needles = (
        "no further safe local reductions",
        "no further local reductions",
        "no further recommendations",
        "critical case solved",
        "reducing non-critical provisions has reached a safe limit",
        "geometry locked for optimisation",
        "geometry locked. optimisation is limited",
    )
    return any(n in hay for n in needles)


def is_unnecessarily_overdesigned(
    overview: dict | None,
    efficiency_state: dict | None,
    *,
    recommendation_result: dict | None = None,
) -> bool:
    """
    True when checks pass but utilisation / efficiency profile indicates the section is materially
    more conservative than needed (efficiency-tightening candidate). Used for card theme only.
    """
    _ = recommendation_result
    if not isinstance(overview, dict) or not bool(overview.get("all_key_pass")):
        return False
    if bool(overview.get("any_fail")):
        return False
    es = efficiency_state if isinstance(efficiency_state, dict) else {}
    if str(es.get("classification") or "") == "optimal":
        return False
    if str(es.get("classification") or "") == "very_low_demand":
        return False
    if str(es.get("classification") or "") == "inefficient":
        return True
    if bool(es.get("strongly_underutilised")):
        return True
    if bool(es.get("is_efficiency_reduction_mode")):
        try:
            worst = float(overview.get("worst_util", 0.0) or 0.0)
        except (TypeError, ValueError):
            worst = 0.0
        if worst < float(GUIDANCE_TARGET_UTIL_MIN):
            return True
    return False


_ONE_CLICK_CTA_BLOCKING_REASONS = frozenset(
    {
        "partial_failure_coverage",
        "no_full_coverage_candidate",
        "no_multi_domain_target_candidate",
        "candidate_preview_has_fail_status",
    }
)


def _design_guide_fail_fingerprints_equivalent(a: dict | None, b: dict | None) -> bool:
    """Treat tiny util drift as equivalent when the failing state is otherwise unchanged."""

    def _norm_keys(v: dict | None) -> list[str]:
        return sorted(str(x or "").strip().lower() for x in list((v or {}).get("fail_keys") or []) if str(x or "").strip())

    def _norm_status(v: dict | None, key: str) -> str:
        return str((v or {}).get(key) or "").strip().upper()

    def _util_close(x: object, y: object) -> bool:
        ux = _parse_util_value(x)
        uy = _parse_util_value(y)
        if ux is None or uy is None:
            return ux is None and uy is None
        if not (math.isfinite(float(ux)) and math.isfinite(float(uy))):
            return ux == uy
        return abs(float(ux) - float(uy)) <= 1e-6

    da = dict(a or {})
    db = dict(b or {})
    return (
        _norm_keys(da) == _norm_keys(db)
        and _norm_status(da, "shear_status") == _norm_status(db, "shear_status")
        and _norm_status(da, "bending_status") == _norm_status(db, "bending_status")
        and _util_close(da.get("shear_util"), db.get("shear_util"))
        and _util_close(da.get("bending_util"), db.get("bending_util"))
    )


def _one_click_feedback_cta_state(
    overview: dict | None,
    *,
    clear_stale: bool = True,
) -> dict:
    feedback = st.session_state.get("_one_click_run_feedback")
    if not isinstance(feedback, dict):
        feedback = {}
    status = str(feedback.get("status") or "").strip()
    reason = str(feedback.get("reason") or "").strip()
    feedback_fp = dict(feedback.get("current_fail_fingerprint") or {})
    current_fp = _current_design_guide_fail_fingerprint(overview)
    blocks_primary_cta = bool(reason in _ONE_CLICK_CTA_BLOCKING_REASONS)
    fingerprints_match = bool(
        feedback_fp
        and (
            feedback_fp == current_fp
            or _design_guide_fail_fingerprints_equivalent(feedback_fp, current_fp)
        )
    )
    matches_current_state = bool(
        status in {"blocked", "rejected"}
        and blocks_primary_cta
        and fingerprints_match
    )
    stale_cleared = False
    if (
        clear_stale
        and status in {"blocked", "rejected"}
        and blocks_primary_cta
        and feedback_fp
        and not fingerprints_match
    ):
        st.session_state.pop("_one_click_run_feedback", None)
        feedback = {}
        status = ""
        reason = ""
        feedback_fp = {}
        stale_cleared = True
    return {
        "feedback": dict(feedback),
        "status": status,
        "reason": reason,
        "feedback_fail_fingerprint": dict(feedback_fp),
        "current_fail_fingerprint": dict(current_fp),
        "blocks_primary_cta": bool(blocks_primary_cta),
        "matches_current_state": bool(matches_current_state),
        "stale_cleared": bool(stale_cleared),
        "stale_clear_reason": "fail_fingerprint_changed" if stale_cleared else None,
    }


def _latest_solver_result_cta_state(overview: dict | None) -> dict:
    _bind_presentation_state_dependencies(globals())
    return _latest_solver_result_cta_state_extracted(overview)


def _build_design_guide_presentation_state(
    *,
    primary_item: dict | None,
    overview: dict | None,
    efficiency_state: dict | None,
    disp_state: dict,
    mode_config: dict | None,
    recommendation_result: dict | None = None,
    pending_recommendation: dict | None = None,
) -> dict:
    """
    Design Guide presentation contract (product rules — do not regress without explicit review).

    - fail beats everything
    - warn / near-limit beats healthy (including utilisation at the upper guidance threshold while
      checks still PASS)
    - healthy means:
        all_key_pass
        no fail
        no warn
        in target band
        not unnecessarily overdesigned
    - efficiency means safe but materially overdesigned
    - the primary recommendation is rendered in one card only (callers must not duplicate titles /
      change lines outside this surface)
    - this function controls card and apply button theme (css_bucket, use_success_style); it does
      not change recommendation semantics or apply payloads

    Evaluation order: fail → warn → healthy → efficiency → info.
    """
    _bind_presentation_state_dependencies(globals())
    return _build_design_guide_presentation_state_extracted(
        primary_item=primary_item,
        overview=overview,
        efficiency_state=efficiency_state,
        disp_state=disp_state,
        mode_config=mode_config,
        recommendation_result=recommendation_result,
        pending_recommendation=pending_recommendation,
    )


def _design_guide_primary_uses_success_style(item: dict) -> bool:
    """Green 'done' card: resolved safe/complete only, not active fix recommendations."""
    bucket = str(item.get("bucket") or "")
    if bucket == "fail":
        return False
    if bucket == "start":
        return False
    has_apply = bool(item.get("action_type"))
    if has_apply and bucket in ("fail", "warn", "efficiency"):
        return False
    if bucket == "warn" and not _is_design_guide_terminal_safe_item(item):
        return False
    terminal = _is_design_guide_terminal_safe_item(item)
    good_band = _is_design_guide_good_utilisation_band(item.get("util"))
    if terminal:
        return True
    if good_band and bucket == "pass":
        return True
    return False


def _resolve_recommendation_updates(item: dict, state: dict | None = None) -> dict:
    action_type = str(item.get("action_type") or "").strip()
    payload = dict(item.get("action_payload") or {})
    resolved = payload.get("resolved_candidate_updates")
    if isinstance(resolved, dict) and resolved:
        return dict(resolved)
    direct = payload.get("updates")
    if isinstance(direct, dict) and direct:
        return dict(direct)
    if action_type:
        try:
            base_state = _guidance_state_snapshot(state)
            return dict(_guidance_action_updates(action_type, payload, state=base_state) or {})
        except Exception:
            return {}
    return {}


def _ensure_guidance_item_resolved_candidate_payload(item: dict, state: dict | None = None) -> None:
    _bind_resolved_candidate_guidance_item_dependencies(globals())
    _ensure_guidance_item_resolved_candidate_payload_extracted(item, state=state)


def _build_pending_recommendation(item: dict, state: dict) -> dict | None:
    _bind_pending_recommendation_dependencies(globals())
    return _build_pending_recommendation_extracted(
        item,
        state=state,
    )


def _pending_matches_actionable_guidance_item(pending: dict, item: dict) -> bool:
    """True when session pending still refers to the same actionable guidance card (title + apply mode)."""
    if not isinstance(pending, dict) or not isinstance(item, dict):
        return False
    pend_title = str(pending.get("title") or "").strip()
    item_title = str(
        item.get("canonical_winner_label") or item.get("title_main") or "",
    ).strip()
    if pend_title and item_title and pend_title != item_title:
        return False
    p_mode, _ = _effective_apply_mode_and_payload_from_pending(pending)
    i_at = str(item.get("action_type") or "").strip()
    if p_mode and i_at and p_mode != i_at:
        return False
    return True


def _guidance_update_signature(item: dict | None) -> tuple:
    """
    Canonical signature for the engineering move a guidance item proposes.
    Used for de-duplicating overlapping shear/bending/one-click cards.
    """
    if not isinstance(item, dict):
        return tuple()

    payload = dict(item.get("action_payload") or {})
    updates = dict(
        payload.get("updates")
        or payload.get("resolved_candidate_updates")
        or {}
    )

    keys_of_interest = (
        "b",
        "D",
        "lig_d",
        "lig_legs",
        "s_lig",
        "db_bot_1",
        "db_bot_2",
        "bot1_count",
        "bot2_count",
        "nb_bot",
        "db_bot",
    )

    sig = []
    for k in keys_of_interest:
        if k in updates:
            sig.append((k, updates.get(k)))
    return tuple(sig)


def _guidance_item_coverage_tuple(item: dict | None) -> tuple:
    if not isinstance(item, dict):
        return (0, 0, 0, 0)
    payload = dict(item.get("action_payload") or {})
    failure_cov = dict(item.get("failure_coverage") or payload.get("failure_coverage") or {})
    covered = list(
        item.get("covered_fail_keys")
        or payload.get("covered_fail_keys")
        or failure_cov.get("covered_fail_keys")
        or []
    )
    remaining = list(
        item.get("remaining_fail_keys")
        or payload.get("remaining_fail_keys")
        or failure_cov.get("remaining_fail_keys")
        or []
    )
    covers_all = bool(
        item.get("covers_all_current_failures")
        or payload.get("covers_all_current_failures")
        or failure_cov.get("covers_all_current_failures")
    )
    fam = _guidance_item_family(item)
    fam_rank = {"combined": 3, "bending": 2, "shear": 1, "other": 0, "unknown": 0}.get(fam, 0)
    return (1 if covers_all else 0, len(covered), -len(remaining), fam_rank)


def _guidance_item_is_same_problem_wrapper(primary: dict | None, secondary: dict | None) -> bool:
    _bind_guidance_item_consolidation_dependencies(globals())
    return _guidance_item_is_same_problem_wrapper_extracted(primary, secondary)


def _consolidate_guidance_items_by_family(
    guidance_items: list[dict],
) -> tuple[list[dict], dict]:
    _bind_guidance_item_consolidation_dependencies(globals())
    return _consolidate_guidance_items_by_family_extracted(guidance_items)


def _guidance_items_materially_overlap(a: dict | None, b: dict | None) -> bool:
    ua = _guidance_update_map(a)
    ub = _guidance_update_map(b)
    if not ua or not ub:
        return False
    if ua == ub:
        return True

    keys_a = set(ua.keys())
    keys_b = set(ub.keys())

    def _subset_same_values(smaller: dict, larger: dict) -> bool:
        for k, v in smaller.items():
            if k not in larger or larger.get(k) != v:
                return False
        return True

    if keys_a.issubset(keys_b) and _subset_same_values(ua, ub):
        return True
    if keys_b.issubset(keys_a) and _subset_same_values(ub, ua):
        return True
    return False


def _build_recommendation_result_from_guidance_item(
    item: dict | None,
    state: dict | None,
    *,
    branch: str | None = None,
    request_kind: str = "design_guide",
) -> dict | None:
    _bind_recommendation_result_builder_dependencies(globals())
    return _build_recommendation_result_from_guidance_item_extracted(
        item,
        state,
        branch=branch,
        request_kind=request_kind,
    )


def _selector_final_winner_label_from_guidance_debug(dbg: dict | None) -> str | None:
    """Best-effort selector / rank-trace winner label for post-hoc alignment checks (debug only)."""
    if not isinstance(dbg, dict):
        return None
    for key in ("selected_title", "surfaced_selected_title"):
        v = dbg.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    oc = dbg.get("one_click_critical_candidate_label")
    if isinstance(oc, str) and oc.strip():
        return oc.strip()
    rt = dbg.get("rank_trace")
    if not isinstance(rt, list):
        return None
    for entry in reversed(rt):
        if not isinstance(entry, dict):
            continue
        ads = entry.get("auto_design_final_selector")
        if isinstance(ads, dict):
            lab = ads.get("final_winner_label")
            if isinstance(lab, str) and lab.strip():
                return lab.strip()
    return None


def _design_guide_title_alignment_verification_record(
    *,
    guidance_items: list[dict],
    guidance_debug: dict | None,
    disp_state: dict,
    recommendation_result: dict | None,
    pending_recommendation: dict | None,
) -> dict:
    _bind_title_alignment_verification_dependencies(globals())
    return _design_guide_title_alignment_verification_record_extracted(
        guidance_items=guidance_items,
        guidance_debug=guidance_debug,
        disp_state=disp_state,
        recommendation_result=recommendation_result,
        pending_recommendation=pending_recommendation,
    )


def _recommendation_result_for_primary_guidance_card(
    deduped_guidance_items: list[dict],
    disp_state: dict,
    *,
    branch: str | None,
    request_kind: str,
) -> dict | None:
    """
    Layer 3 pure: canonical recommendation_result for the same primary actionable card as Design Guide
    (deduped list, resolved payloads, first actionable item).
    """
    for item in deduped_guidance_items or []:
        if isinstance(item, dict):
            _ensure_guidance_item_resolved_candidate_payload(item, state=disp_state)
    first = _first_actionable_guidance_item(deduped_guidance_items)
    return _build_recommendation_result_from_guidance_item(
        first,
        disp_state,
        branch=branch,
        request_kind=request_kind,
    )


def _pending_recommendation_equivalent(a: dict | None, b: dict | None) -> bool:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    mode_a, payload_a = _effective_apply_mode_and_payload_from_pending(a)
    mode_b, payload_b = _effective_apply_mode_and_payload_from_pending(b)
    title_a = str(a.get("title") or "").strip()
    title_b = str(b.get("title") or "").strip()
    return mode_a == mode_b and payload_a == payload_b and title_a == title_b


def _design_guide_banner_matches_current_render(
    banner_payload: dict | None,
    banner_meta: dict | None,
    recommendation_result: dict | None,
    pending_recommendation: dict | None,
    fingerprint: tuple | None,
) -> bool:
    _bind_banner_render_state_dependencies(globals())
    return _design_guide_banner_matches_current_render_extracted(
        banner_payload,
        banner_meta,
        recommendation_result,
        pending_recommendation,
        fingerprint,
    )


def _auto_design_solver_recommendation_as_guidance_item(solver_rec: dict) -> dict | None:
    """
    Map run_auto_design_solver(...) output into a guidance item so it participates in the same
    dedupe + recommendation_result pipeline as Design Guide (Layer 3, no session access).
    """
    if not isinstance(solver_rec, dict):
        return None
    meta = dict(solver_rec.get("meta") or {})
    if str(meta.get("status") or "").strip() == "no_action":
        return None
    updates = dict(solver_rec.get("updates") or {})
    if not updates:
        return None
    title = str(solver_rec.get("title") or "Auto Design Solution").strip()
    desc = str(solver_rec.get("description") or "").strip()
    util_raw = meta.get("util")
    try:
        util_f = float(util_raw) if util_raw is not None else None
    except Exception:
        util_f = None
    rc = solver_rec.get("resolved_candidate") if isinstance(solver_rec.get("resolved_candidate"), dict) else {}
    rc_updates = dict(rc.get("updates") or updates)
    payload = {
        "updates": dict(updates),
        "resolved_candidate_updates": dict(solver_rec.get("resolved_candidate_updates") or rc_updates),
        "resolved_candidate_label": str(solver_rec.get("resolved_candidate_label") or rc.get("label") or title),
        "resolved_candidate_action_type": str(
            solver_rec.get("resolved_candidate_action_type") or rc.get("action_type") or "apply_compound_guidance",
        ).strip(),
    }
    return _guidance_item(
        "auto_design_engine",
        title,
        desc or title,
        None,
        desc,
        "Auto-design solver",
        "apply_compound_guidance",
        payload,
        status="FAIL",
        util=util_f,
    )


def _sync_pending_recommendation_from_guidance(
    guidance_items: list[dict],
    state: dict,
    *,
    terminal_state: str | None = None,
) -> dict | None:
    _bind_pending_recommendation_dependencies(globals())
    return _sync_pending_recommendation_from_guidance_extracted(
        guidance_items,
        state,
        terminal_state=terminal_state,
    )


def _queue_primary_design_guide_button_action(
    rec: dict,
    primary_route_target: str,
    apply_label: str,
    button_contract: dict | None = None,
) -> None:
    _bind_primary_button_queue_dependencies(globals())
    return _queue_primary_design_guide_button_action_extracted(
        rec,
        primary_route_target,
        apply_label,
        button_contract=button_contract,
    )


def _compute_mode_guidance_recommendation_uncached(state: dict) -> dict | None:
    _bind_mode_guidance_recommendation_dependencies(globals())
    return _compute_mode_guidance_recommendation_uncached_extracted(state)


def _compute_mode_guidance_recommendation(state: dict) -> dict | None:
    return _compute_mode_guidance_recommendation_uncached(state)


def _recommendation_preview_util(recommendation: dict | None) -> float | None:
    if not isinstance(recommendation, dict):
        return None
    mode_util = _mode_recommendation_expected_bend_util(recommendation)
    if mode_util is not None:
        return mode_util
    values: list[float] = []
    for key in ("util", "real_util", "bending_util", "shear_util"):
        value = recommendation.get(key)
        try:
            resolved = float(value)
        except Exception:
            continue
        if not math.isnan(resolved):
            values.append(resolved)
    if values:
        return max(values)
    return None


def _materialize_guidance_candidate(base_candidate: dict | None, recommendation: dict | None, *, source: str) -> dict | None:
    if not base_candidate or not isinstance(recommendation, dict):
        return None
    updates = dict(recommendation.get("updates") or recommendation.get("arrangement") or {})
    if not updates:
        return None
    candidate = _evaluate_auto_design_candidate(
        base_candidate.get("state") or {},
        updates=updates,
        source=source,
        label=str(recommendation.get("label") or source.replace("_", " ").title()),
        action_type="auto_design",
    )
    if candidate is not None:
        candidate["guidance_preview_util"] = _recommendation_preview_util(recommendation)
    return candidate


def _shear_overdesign_reserve_guidance_predicate(
    working_state: dict,
    overview: dict,
    actions: dict,
    *,
    current_shear_status: str,
    current_shear_util: float | None,
    shear_cleanup_possible: bool,
) -> tuple[bool, dict]:
    """Strict scheduling-only predicate: heavy shear reserve + truth-safe; does not change capacities."""
    detail: dict = {
        "active_links": bool(_shear_reinforcement_is_active(working_state)),
        "cleanup_possible": bool(shear_cleanup_possible),
        "all_key_pass": bool((overview or {}).get("all_key_pass")),
        "no_any_fail": not bool((overview or {}).get("any_fail")),
        "truth_status_pass": False,
        "final_shear_truth_resolved": working_state.get("final_shear_truth_resolved"),
        "demand_non_negligible": not _shear_demands_negligible(actions),
        "low_demand_cleanup_allowed": False,
        "shear_util": current_shear_util,
        "low_shear_util_cap": float(SHEAR_OVERDESIGN_RESERVE_GUIDANCE_UTIL_MAX),
        "low_shear_util": False,
        "combined": False,
    }
    if not detail["active_links"] or not detail["cleanup_possible"]:
        return False, detail
    if not detail["all_key_pass"] or not detail["no_any_fail"]:
        return False, detail
    if not detail["demand_non_negligible"]:
        detail["low_demand_cleanup_allowed"] = False
        return False, detail
    if working_state.get("final_shear_truth_resolved") is False:
        return False, detail
    st = str(current_shear_status or "").strip().upper()
    detail["truth_status_pass"] = st == "PASS"
    if not detail["truth_status_pass"]:
        return False, detail
    if current_shear_util is None:
        return False, detail
    try:
        su = float(current_shear_util)
    except (TypeError, ValueError):
        return False, detail
    detail["low_shear_util"] = su <= float(SHEAR_OVERDESIGN_RESERVE_GUIDANCE_UTIL_MAX) + 1e-12
    if not detail["low_shear_util"]:
        return False, detail
    detail["combined"] = True
    return True, detail


def _exhaustion_map_fully_resolved_for_terminal(exhaust: dict | None) -> bool:
    if not isinstance(exhaust, dict) or not exhaust:
        return False
    for _fam, rec in exhaust.items():
        if not isinstance(rec, dict):
            return False
        if not bool(rec.get("tried")):
            return False
        if bool(rec.get("accepted")):
            continue
        if rec.get("rejected_reason"):
            continue
        return False
    return True


def _can_emit_efficiency_terminal_state(worst_u: float, exhaust: dict | None) -> tuple[bool, str]:
    try:
        w = float(worst_u)
    except (TypeError, ValueError):
        w = 0.0
    if GUIDANCE_TARGET_UTIL_MIN <= w <= GUIDANCE_TARGET_UTIL_MAX:
        return True, "in_target_band"
    if w >= float(GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL):
        return True, "worst_util_above_undersized_done_block"
    if not _exhaustion_map_fully_resolved_for_terminal(exhaust):
        return False, "exhaustion_incomplete_or_unresolved"
    return True, "undersized_but_all_reduction_families_resolved"


def _build_efficiency_exhaustion_map(
    *,
    state: dict,
    overview: dict,
    conservative: bool,
    bottom_tighten: dict | None,
    shear_tighten: dict | None,
    geometry_tighten: dict | None,
    shear_cleanup_possible: bool,
    shear_overdesign_cleanup_eligible: bool,
    bending_inefficient: bool,
    shear_inefficient: bool,
) -> dict:
    _bind_efficiency_tightening_state_dependencies(globals())
    return _build_efficiency_exhaustion_map_extracted(
        state=state,
        overview=overview,
        conservative=conservative,
        bottom_tighten=bottom_tighten,
        shear_tighten=shear_tighten,
        geometry_tighten=geometry_tighten,
        shear_cleanup_possible=shear_cleanup_possible,
        shear_overdesign_cleanup_eligible=shear_overdesign_cleanup_eligible,
        bending_inefficient=bending_inefficient,
        shear_inefficient=shear_inefficient,
    )


def compute_efficiency_tightening_state(state: dict, context: dict | None = None) -> dict:
    _bind_efficiency_tightening_state_dependencies(globals())
    return _compute_efficiency_tightening_state_extracted(state, context=context)


def _one_click_committable_candidate_eval(
    base_state: dict,
    updates: dict | None,
    *,
    source: str,
    label: str | None,
    action_type: str | None,
) -> tuple[dict | None, dict, dict]:
    """Evaluate a one-click winner through the exact shared-state commit surface."""
    sanitized_updates, sanitize_meta = _sanitize_shared_update_bundle(
        updates,
        source=source,
    )
    if not sanitized_updates:
        return None, sanitized_updates, sanitize_meta
    committed_state = _guidance_state_snapshot(dict(base_state or {}))
    committed_state.update(dict(sanitized_updates))
    try:
        committed_state.update(
            _normalise_invalid_shear_state_updates(
                committed_state,
                {},
                source=f"{source}:preview_normalise",
            )
        )
    except Exception:
        pass
    try:
        convenience_updates = dict(_canonical_convenience_fields_from_state(committed_state) or {})
        convenience_meta = dict(convenience_updates.pop(_CANONICAL_CONVENIENCE_META_KEY, {}) or {})
        if bool(convenience_meta.get("canonical_convenience_resync_valid")):
            committed_state.update(convenience_updates)
    except Exception:
        pass
    try:
        eval_obj = _evaluate_auto_design_candidate(
            committed_state,
            updates={},
            source=source,
            label=label,
            action_type=action_type,
        )
    except Exception:
        eval_obj = None
    return eval_obj, sanitized_updates, sanitize_meta


def _set_shared_updates(updates: dict, *, source: str) -> None:
    sanitized_updates, sanitize_meta = _sanitize_shared_update_bundle(
        updates,
        source=source,
    )

    st.session_state["_last_shared_update_sanitize_meta"] = dict(sanitize_meta)
    st.session_state["_nonshared_update_drop_audit"] = {
        "source": sanitize_meta["source"],
        "dropped_nonshared_keys": list(sanitize_meta.get("dropped_nonshared_keys") or []),
        "dropped_private_keys": list(sanitize_meta.get("dropped_private_keys") or []),
        "raw_key_count": sanitize_meta.get("input_key_count"),
        "sanitized_key_count": sanitize_meta.get("sanitized_key_count"),
    }

    try:
        _append_design_guide_trace(
            "shared_update_sanitize",
            dict(sanitize_meta),
            source=str(source or ""),
        )
    except Exception:
        pass

    if not sanitized_updates:
        return
    for shared_key, value in sanitized_updates.items():
        set_shared(shared_key, value, source=source)
    if any(key in {"lig_d", "lig_legs", "s_lig"} for key in sanitized_updates):
        _normalise_invalid_shear_state_in_shared(source=f"{source}:shear_shared_normalise")
        _refresh_canonical_shear_widgets(source=f"{source}:shear_widget_refresh")
    _apply_canonical_convenience_resync_to_shared(source=f"{source}:canonical_convenience")


def _one_click_post_commit_audit_subset(intended: dict) -> dict:
    _bind_post_commit_audit_dependencies(globals())
    return _one_click_post_commit_audit_subset_extracted(intended)


def _one_click_post_commit_audit(intended: dict) -> dict:
    _bind_post_commit_audit_dependencies(globals())
    return _one_click_post_commit_audit_extracted(intended)


def _restore_shared_state_snapshot(snapshot: dict, *, source: str) -> None:
    """Restore full shared beam state from a prior ``_shared_state_snapshot()`` (no partial merge)."""
    snap = copy.deepcopy(snapshot)
    for key, default in SHARED_DEFAULTS.items():
        set_shared(key, snap.get(key, default), source=source)
    _normalise_invalid_shear_state_in_shared(source=f"{source}:shear_shared_normalise")
    _refresh_canonical_shear_widgets(source=f"{source}:shear_widget_refresh")
    _apply_canonical_convenience_resync_to_shared(source=f"{source}:canonical_convenience")


def _commit_auto_design_candidate_to_shared(candidate: dict) -> dict:
    _bind_auto_design_commit_dependencies(globals())
    return _commit_auto_design_candidate_to_shared_extracted(candidate)


def _debug_log_design_guide_consistency(*, source: str, applied_candidate: dict | None = None) -> None:
    if not bool(st.session_state.get("_dev_mode")):
        return
    fresh_state, _ = _resolved_inputs_summary_state()
    design_context = _build_design_actions_context(fresh_state)
    fresh_overview = _collect_design_overview(fresh_state, context=design_context)
    guidance_payload = _compute_design_guidance_items(
        fresh_state,
        guidance_debug_verbose=True,
        debug_enabled=False,
    )
    guide_debug: dict = dict(guidance_payload.get("debug_trace") or {})
    guide_debug.setdefault("overview", fresh_overview)
    efficiency_state = dict(guide_debug.get("efficiency_tightening_state") or {})
    next_mode_recommendation = dict(efficiency_state.get("mode_tightening") or {})
    current_summary = _overview_debug_summary(fresh_state, fresh_overview)
    applied_summary = _candidate_debug_summary(applied_candidate)
    warning = False
    if applied_summary is not None and applied_summary.get("bottom_reo_label") != current_summary.get("bottom_reo_label"):
        warning = True
    if next_mode_recommendation and str(next_mode_recommendation.get("label") or "") == str(current_summary.get("bottom_reo_label") or ""):
        warning = True
    _agent_debug_log(
        "Post-commit design guide consistency check",
        {
            "source": source,
            "warning": warning,
            "committed_bottom_reo_label": current_summary.get("bottom_reo_label"),
            "overview_bottom_reo_label": current_summary.get("bottom_reo_label"),
            "applied_candidate_label": None if applied_summary is None else applied_summary.get("bottom_reo_label"),
            "current_utilisation_shown": current_summary.get("worst_util"),
            "actual_overview_utilisation": current_summary.get("worst_util"),
            "next_recommendation_label": next_mode_recommendation.get("label"),
            "next_recommendation_expected_util": next_mode_recommendation.get("expected_util"),
            "next_recommendation_optimisation_score": next_mode_recommendation.get("optimisation_score"),
            "guidance_branch": guide_debug.get("guidance_branch"),
            "overview_summary": current_summary,
            "applied_summary": applied_summary,
            "next_recommendation_summary": next_mode_recommendation.get("candidate_summary"),
        },
        location="inputs_page.py:_debug_log_design_guide_consistency",
        hypothesis_id="H302",
    )


def _clear_legacy_auto_design_request_flags(
    *,
    clear_invoke: bool = False,
    idle_reason_on_cancel: str = "request_cancelled_by_guidance_commit",
) -> None:
    """
    Legacy string cleanup. One-shot auto-design invoke keys are preserved unless
    ``clear_invoke=True`` (explicit cancellation of a pending one-click request).
    """
    st.session_state.pop("_auto_design_reason", None)
    if not clear_invoke:
        return
    st.session_state.pop(AUTO_DESIGN_AUTO_INVOKE_KEY, None)
    st.session_state.pop(AUTO_DESIGN_REQUEST_TS_KEY, None)
    st.session_state.pop(AUTO_DESIGN_REQUEST_SOURCE_KEY, None)
    st.session_state.pop("auto_design_request_source", None)
    try:
        st.session_state["auto_design_invoke_pending"] = False
        st.session_state["auto_design_invoke_set"] = False
        st.session_state["auto_design_idle_reason"] = str(idle_reason_on_cancel)
        st.session_state["_auto_design_idle_reason"] = str(idle_reason_on_cancel)
    except Exception:
        pass


def _sync_auto_design_invoke_pending_field() -> None:
    """Keep ``auto_design_invoke_pending`` aligned with the one-shot invoke session key."""
    try:
        st.session_state["auto_design_invoke_pending"] = bool(st.session_state.get(AUTO_DESIGN_AUTO_INVOKE_KEY, False))
    except Exception:
        pass


_ONE_CLICK_NO_ACTION_STOP_REASON_USER_TEXT: dict[str, str] = {
    "no_actionable_candidates": "All candidates were filtered out; none preserved the governing checks with executable updates.",
    "no_actionable_candidates_after_full_tightening_search": "After the full tightening search, no actionable candidate remained.",
    "non_material_remaining_candidates": "Remaining candidates would not materially improve the design.",
    "no_improving_candidate": "No candidate improved the worst-case objective on this step.",
}


def _one_click_build_user_visible_no_action_fields(stop_reason: str, dbg: dict | None) -> dict[str, str | None]:
    """
    Compact, user-facing copy when one-click ran but returned ``no_action``.
    Does not alter solver behaviour — packaging only.
    """
    dbg = dict(dbg or {})
    sr = str(stop_reason or "").strip()
    detail = _ONE_CLICK_NO_ACTION_STOP_REASON_USER_TEXT.get(sr)
    if detail is None:
        if sr == "state_incoherent_after_rebuild":
            detail = "The canonical beam state was incoherent after rebuild, so the one-click pass could not continue."
        elif sr == "no_bars_resolved":
            detail = "Add longitudinal reinforcement before running auto-design."
        elif sr == "evaluate_failed":
            detail = "Initial evaluation failed, so no trial updates could be scored."
        else:
            detail = f"Stop reason: {sr}." if sr else "The solver stopped before applying an update."

    gdom = str(dbg.get("governing_domain") or "").strip().lower()
    shear = gdom == "shear"

    if sr == "state_incoherent_after_rebuild":
        headline = "One-click did not complete."
    elif shear:
        headline = "One-click ran, but the current shear candidate set was exhausted by practicality/code filters."
    else:
        headline = "One-click auto design ran, but no practical candidate was found."

    user_visible_no_action_reason = f"{headline} — {detail}".strip()

    parts: list[str] = []
    counter_keys = (
        ("rejected_as_impractical_shear_layout", "rejected_as_impractical_shear_layout"),
        ("rejected_as_spacing_too_weak", "rejected_as_spacing_too_weak"),
        ("rejected_as_web_crushing_marginal", "rejected_as_web_crushing_marginal"),
        ("rejected_as_non_governing_cleanup", "rejected_as_non_governing_cleanup"),
    )
    for dbg_key, label in counter_keys:
        try:
            n = int(dbg.get(dbg_key) or 0)
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            parts.append(f"{label}: {n}")
    user_visible_rejection_summary = "; ".join(parts) if parts else None

    return {
        "user_visible_no_action_reason": user_visible_no_action_reason,
        "user_visible_rejection_summary": user_visible_rejection_summary,
    }


def _render_auto_design_main_panel_status() -> None:
    _bind_main_panel_status_dependencies(globals())
    _render_auto_design_main_panel_status_extracted()


def _apply_shared_updates(updates: dict, *, source: str, rerun: bool = True, focus_section: str | None = None) -> bool:
    if not updates:
        if str(source).startswith("guidance:"):
            _emit_design_guide_apply_trace_run_end(
                stop_reason="no_updates",
                final_updates={},
            )
        return False
    prior_state = _shared_state_snapshot()
    updates = _normalise_invalid_shear_state_updates(prior_state, updates, source=source)
    expected_state = dict(prior_state)
    expected_state.update(updates)
    applied_candidate = evaluate_candidate_full(
        _guidance_state_snapshot(expected_state),
        source=f"{source}:post_apply_preview",
        updates=updates,
    )
    _set_shared_updates(updates, source=source)
    if str(source).startswith("guidance:"):
        _clear_legacy_auto_design_request_flags(clear_invoke=False)
        _finalize_design_guide_apply_step_history(
            prior_state=prior_state,
            source=source,
            applied_candidate=applied_candidate,
        )
        _store_design_guide_apply_banner_payload(prior_state, _shared_state_snapshot())
        _record_design_guide_auto_geometry_applied(prior_state, updates)
        st.session_state[DESIGN_GUIDE_PANEL_BASELINE_FP_KEY] = _design_guide_cache_fingerprint(
            _shared_state_snapshot(),
        )
        st.session_state.pop(DESIGN_GUIDE_NEEDS_REFRESH_KEY, None)
    _debug_log_design_guide_consistency(source=source, applied_candidate=applied_candidate)
    _invalidate_design_guide_caches(
        reason=source,
        updated_keys=list(updates.keys()),
        preserve_apply_banner=bool(str(source).startswith("guidance:")),
    )
    finalize_auto_design_publish(
        updated_keys=sorted(list(updates.keys())),
        source=source,
        focus_section=focus_section,
        set_run_design_clicked=True,
    )
    if str(source).startswith("guidance:"):
        _emit_design_guide_apply_trace_run_end(
            stop_reason="applied_recommendation",
            final_updates=dict(updates),
        )
    if rerun:
        st.rerun()
    return True


def _describe_guidance_step(before_state: dict, after_state: dict, action_type: str, updates: dict) -> str:
    if "D" in updates:
        before_depth = int(float(before_state.get("D", 0.0) or 0.0))
        after_depth = int(float(after_state.get("D", 0.0) or 0.0))
        verb = "Reduced" if after_depth < before_depth else "Increased"
        return f"{verb} depth D from {before_depth} to {after_depth} mm."
    width_key, width_label, _ = _resolve_geometry_width_context(after_state)
    if width_key in updates:
        before_width = int(float(before_state.get(width_key, 0.0) or 0.0))
        after_width = int(float(after_state.get(width_key, 0.0) or 0.0))
        width_short = "b" if width_key == "b" else width_key
        verb = "Reduced" if after_width < before_width else "Increased"
        return f"{verb} {width_short} from {before_width} to {after_width} mm."
    if any(key in updates for key in ("bot1_count", "bot2_count", "db_bot_1", "db_bot_2", "Ast_bot")):
        return f"Updated bottom reinforcement from {_bottom_reo_state_label(before_state)} to {_bottom_reo_state_label(after_state)}."
    if any(key in updates for key in ("s_lig", "lig_legs", "lig_d")):
        return f"Updated shear reinforcement from {_shear_state_label(before_state)} to {_shear_state_label(after_state)}."
    load_keys = ("g_udl_kNm_per_m", "g_kNm", "g_line_kNm")
    if any(key in updates for key in load_keys):
        parts: list[str] = []
        for key in load_keys:
            if key not in updates:
                continue
            try:
                b0 = float(before_state.get(key, 0.0) or 0.0)
                a0 = float(after_state.get(key, 0.0) or 0.0)
                parts.append(f"{key} {b0:.3f} → {a0:.3f} kN/m")
            except Exception:
                parts.append(str(key))
        if parts:
            return "Adjusted sustained load inputs: " + "; ".join(parts) + "."
    return f"Applied {action_type.replace('_', ' ')}."
    st.rerun()


def clone_candidate_state_for_next_hop(candidate: dict) -> dict:
    return _guidance_state_snapshot(dict(candidate.get("state") or {}))


def _candidate_state_signature(candidate: dict | None) -> tuple:
    if not candidate:
        return ()
    return _make_auto_design_candidate_key(clone_candidate_state_for_next_hop(candidate))


def is_valid_progress_while_failing(new_candidate: dict | None, old_candidate: dict | None) -> bool:
    if not new_candidate or not old_candidate:
        return False
    if bool(new_candidate.get("is_compliant")):
        return True
    old_failed = set(_failed_check_labels(old_candidate))
    new_failed = set(_failed_check_labels(new_candidate))
    old_util = float(old_candidate.get("worst_util", 999.0) or 999.0)
    new_util = float(new_candidate.get("worst_util", 999.0) or 999.0)
    if new_failed != old_failed and len(new_failed) < len(old_failed):
        return True
    if new_util < old_util - 0.01:
        return True
    return _candidate_state_signature(new_candidate) != _candidate_state_signature(old_candidate)


def apply_guided_solve_sequence(*, source: str) -> bool:
    """
    Internal guided multi-step solve; invoked from apply_guidance_action for specific failing states.
    Not a primary entrypoint for pending recommendation apply (use apply_recommendation_result).
    """
    _bind_apply_guidance_action_dependencies(globals())
    return _apply_guided_solve_sequence_extracted(source=source)


def _apply_resolved_candidate_payload(payload: dict) -> bool:
    return apply_resolved_candidate_payload(
        legacy_page=sys.modules[__name__],
        st_module=st,
        stderr=sys.stderr,
        payload=payload,
    )


def apply_guidance_action(action_type: str, payload: dict) -> bool:
    _bind_apply_guidance_action_dependencies(globals())
    return _apply_guidance_action_extracted(action_type, payload)


def depth_delta_mm(candidate_a: dict, candidate_b: dict) -> float:
    return float(candidate_a.get("depth", 0.0) or 0.0) - float(candidate_b.get("depth", 0.0) or 0.0)


def reo_complexity_delta(candidate_a: dict, candidate_b: dict) -> float:
    return float(candidate_a.get("reo_complexity", compute_reo_complexity(candidate_a)) or 0.0) - float(
        candidate_b.get("reo_complexity", compute_reo_complexity(candidate_b)) or 0.0
    )


def is_materially_shallower(candidate: dict, seed_candidate: dict, mode_config: dict) -> bool:
    threshold = float(mode_config.get("material_depth_delta_mm", 25.0))
    return depth_delta_mm(candidate, seed_candidate) <= -threshold


def is_materially_simpler_reo(candidate: dict, seed_candidate: dict, mode_config: dict) -> bool:
    threshold = float(mode_config.get("material_reo_complexity_delta", 4.0))
    if int(candidate.get("row_count", 0) or 0) < int(seed_candidate.get("row_count", 0) or 0):
        return True
    if int(candidate.get("bar_count", 0) or 0) <= int(seed_candidate.get("bar_count", 0) or 0) - 2:
        return True
    return reo_complexity_delta(candidate, seed_candidate) <= -threshold


def _candidate_materially_better_for_mode(candidate: dict, seed_candidate: dict, mode_config: dict) -> bool:
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if not candidate or not bool(candidate.get("is_compliant")):
        return False
    if strategy == "shallow":
        return _candidate_is_practical(candidate, mode_config) and is_materially_shallower(candidate, seed_candidate, mode_config)
    if strategy == "low_reo":
        return _candidate_is_practical(candidate, mode_config) and is_materially_simpler_reo(candidate, seed_candidate, mode_config)
    if _candidate_in_target_band(candidate, mode_config) and not _candidate_in_target_band(seed_candidate, mode_config):
        return True
    return float(candidate.get("score", float("inf")) or float("inf")) < float(seed_candidate.get("score", float("inf")) or float("inf")) - 0.5


def candidate_is_good_enough(
    candidate: dict,
    mode_config: dict,
    reference_candidate: dict | None = None,
) -> bool:
    if not candidate or not bool(candidate.get("is_compliant")) or not _candidate_is_practical(candidate, mode_config):
        return False
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if strategy == "shallow":
        return (
            _candidate_in_target_band(candidate, mode_config)
            or (reference_candidate is not None and is_materially_shallower(candidate, reference_candidate, mode_config))
        )
    if strategy == "low_reo":
        return (
            _candidate_in_target_band(candidate, mode_config)
            or (reference_candidate is not None and is_materially_simpler_reo(candidate, reference_candidate, mode_config))
        )
    return _candidate_in_target_band(candidate, mode_config)


def _allow_early_target_exit(mode_config: dict) -> bool:
    return str(mode_config.get("search_strategy", "balanced") or "balanced") != "balanced"


def is_meaningfully_better(new_result: dict, old_result: dict, mode_config: dict) -> bool:
    if not new_result or not old_result:
        return False
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    min_score_improvement = float(mode_config.get("min_score_improvement", 0.25) or 0.25)
    min_util_improvement = float(mode_config.get("min_util_improvement", 0.01) or 0.01)
    score_gain = float(old_result.get("score", float("inf")) or float("inf")) - float(new_result.get("score", float("inf")) or float("inf"))
    util_gain = utilisation_gap(old_result, mode_config) - utilisation_gap(new_result, mode_config)
    depth_gain = float(old_result.get("depth", 0.0) or 0.0) - float(new_result.get("depth", 0.0) or 0.0)
    reo_gain = float(old_result.get("reo_complexity", compute_reo_complexity(old_result)) or 0.0) - float(
        new_result.get("reo_complexity", compute_reo_complexity(new_result)) or 0.0
    )
    if strategy == "shallow":
        return (
            depth_gain >= float(mode_config.get("material_depth_delta_mm", 25.0) or 25.0)
            or score_gain > min_score_improvement
            or util_gain > min_util_improvement
        )
    if strategy == "low_reo":
        return (
            reo_gain >= float(mode_config.get("material_reo_complexity_delta", 4.0) or 4.0)
            or score_gain > min_score_improvement
            or util_gain > min_util_improvement
        )
    return (
        score_gain > min_score_improvement
        or util_gain > min_util_improvement
        or depth_gain >= float(mode_config.get("material_depth_delta_mm", 25.0) or 25.0)
        or reo_gain >= float(mode_config.get("material_reo_complexity_delta", 4.0) or 4.0)
    )


def _ensure_candidate_score(candidate: dict | None, mode_config: dict, seed_candidate: dict) -> dict | None:
    if not candidate:
        return candidate
    candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
    return candidate


def select_final_candidate(results: list[dict], mode_config: dict, baseline_candidate: dict | None = None) -> dict | None:
    filtered = []
    for result in results:
        if not result:
            continue
        if baseline_candidate is not None and candidate_materially_worsens(result, baseline_candidate, mode_config, phase="final"):
            continue
        filtered.append(result)
    if not filtered:
        return baseline_candidate
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    in_zone = [
        result for result in filtered
        if bool(result.get("is_compliant")) and candidate_is_good_enough(result, mode_config)
    ]
    if in_zone:
        if strategy == "shallow" and baseline_candidate is not None:
            return min(
                in_zone,
                key=lambda item: (
                    _shallower_beam_selection_key(item, baseline_candidate, mode_config),
                    _candidate_sort_key_for_mode(item, mode_config),
                    item.get("score", float("inf")),
                ),
            )
        return min(in_zone, key=lambda item: (_candidate_sort_key_for_mode(item, mode_config), item.get("score", float("inf"))))
    compliant = [result for result in filtered if bool(result.get("is_compliant"))]
    if compliant:
        if strategy == "shallow" and baseline_candidate is not None:
            return min(
                compliant,
                key=lambda item: (
                    _shallower_beam_selection_key(item, baseline_candidate, mode_config),
                    utilisation_gap(item, mode_config),
                    _candidate_sort_key_for_mode(item, mode_config),
                    item.get("score", float("inf")),
                ),
            )
        return min(compliant, key=lambda item: (utilisation_gap(item, mode_config), _candidate_sort_key_for_mode(item, mode_config), item.get("score", float("inf"))))
    return min(filtered, key=lambda item: (int(item.get("fail_count", 0) or 0), float(item.get("worst_util", float("inf")) or float("inf")), _candidate_sort_key_for_mode(item, mode_config), item.get("score", float("inf"))))


def select_best_next_hop_candidate(
    current_result: dict,
    candidate_results: list[dict],
    mode_config: dict,
    *,
    phase: str,
) -> dict | None:
    viable: list[dict] = []
    for result in candidate_results:
        if not result:
            continue
        if candidate_materially_worsens(result, current_result, mode_config, phase=phase):
            continue
        viable.append(result)
    if not viable:
        return None
    if phase == "solve_to_pass" and not bool(current_result.get("is_compliant")):
        return min(
            viable,
            key=lambda item: (
                0 if bool(item.get("is_compliant")) else 1,
                int(item.get("fail_count", 0) or 0),
                float(item.get("worst_util", 999.0) or 999.0),
                _candidate_sort_key_for_mode(item, mode_config),
                float(item.get("score", 0.0) or 0.0),
            ),
        )
    return min(
        viable,
        key=lambda item: (_candidate_sort_key_for_mode(item, mode_config), float(item.get("score", 0.0) or 0.0)),
    )


def _generate_local_geometry_variants(current_candidate: dict, mode_config: dict, *, is_first_hop: bool = False) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    if _geometry_lock_enabled(state):
        return []
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    _, _, current_width = _resolve_geometry_width_context(state)
    current_depth = float(current_candidate.get("depth", _float_from_state(state, "D", 600.0)) or _float_from_state(state, "D", 600.0))
    if _candidate_ductility_governs(current_candidate):
        width_steps = [current_width + 50.0]
        if is_first_hop:
            width_steps.append(current_width + 100.0)
        depth_steps = [current_depth + 50.0]
        if not is_first_hop:
            depth_steps.append(current_depth + 100.0)
        variants: dict[tuple, dict] = {}
        for width in width_steps:
            if width >= 250.0:
                candidate_state = _geometry_state_with_updates(state, width=width)
                variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
        for depth in depth_steps:
            if depth >= 350.0:
                candidate_state = _geometry_state_with_updates(state, depth=depth)
                variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
        return list(variants.values())
    depth_steps = [current_depth - 50.0, current_depth + 50.0]
    width_steps: list[float] = []
    if is_first_hop:
        if strategy == "shallow":
            depth_steps = [current_depth - 100.0, current_depth - 50.0, current_depth + 50.0]
        elif strategy == "low_reo":
            depth_steps = [current_depth + 50.0, current_depth + 100.0, current_depth - 50.0]
            width_steps = [current_width + 50.0, current_width + 100.0]
        else:
            depth_steps = [current_depth - 50.0, current_depth + 50.0, current_depth + 100.0]
            width_steps = [current_width - 50.0, current_width + 50.0]
    else:
        if strategy == "shallow":
            depth_steps = [current_depth - 50.0, current_depth + 50.0]
        elif strategy == "low_reo":
            depth_steps = [current_depth + 50.0, current_depth - 50.0]
            width_steps = [current_width + 50.0]
        else:
            width_steps = [current_width - 50.0, current_width + 50.0]
    variants: dict[tuple, dict] = {}
    for depth in depth_steps:
        if depth >= 350.0:
            candidate_state = _geometry_state_with_updates(state, depth=depth)
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    for width in width_steps:
        if width >= 250.0:
            candidate_state = _geometry_state_with_updates(state, width=width)
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    return list(variants.values())


def generate_local_improvement_candidates(
    current_candidate: dict,
    mode_config: dict,
    context: dict,
    *,
    search_band: int = 0,
    is_first_hop: bool = False,
) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    candidates: dict[tuple, dict] = {}
    raw_limit = AUTO_DESIGN_MAX_FIRST_HOP_RAW_CANDIDATES if is_first_hop else AUTO_DESIGN_MAX_LATER_HOP_RAW_CANDIDATES
    bottom_band = max(int(search_band), 1) if is_first_hop else int(search_band)
    for arrangement in _generate_local_bottom_arrangements(state, mode_config, band=bottom_band, context=context, limit=raw_limit):
        candidate_state = dict(state)
        candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    disable_shear_strength_candidates = bool(context.get("disable_shear_strength_candidates"))
    if not disable_shear_strength_candidates:
        shear_bands = [int(search_band)]
        if is_first_hop:
            shear_bands = sorted(set([0, 1]))
        for band in shear_bands:
            for shear_state in _generate_local_shear_states(state, mode_config, band=band, limit=raw_limit):
                candidates[_make_auto_design_candidate_key(shear_state)] = shear_state
    for geometry_state in _generate_local_geometry_variants(current_candidate, mode_config, is_first_hop=is_first_hop):
        candidates[_make_auto_design_candidate_key(geometry_state)] = geometry_state
    candidates.pop(_make_auto_design_candidate_key(state), None)
    return list(candidates.values())


def generate_cleanup_candidates(
    current_candidate: dict,
    mode_config: dict,
    context: dict,
) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    candidates: dict[tuple, dict] = {}
    for candidate_state in generate_less_bottom_reo_variants(current_candidate, mode_config, context):
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    for candidate_state in generate_simpler_layout_variants(current_candidate, mode_config, context):
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    if _shear_cleanup_possible(state) and not bool(context.get("disable_shear_cleanup_candidates")):
        for candidate_state in generate_less_shear_reo_variants(current_candidate, mode_config):
            candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    candidates.pop(_make_auto_design_candidate_key(state), None)
    return list(candidates.values())


def generate_smaller_geometry_variants(current_candidate: dict, mode_config: dict) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    if _geometry_lock_enabled(state):
        return []
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    current_depth = float(current_candidate.get("depth", _float_from_state(state, "D", 600.0)) or _float_from_state(state, "D", 600.0))
    width_key, _, current_width = _resolve_geometry_width_context(state)
    variants: dict[tuple, dict] = {}
    for depth in [current_depth - 50.0, current_depth - 100.0]:
        if depth >= 350.0:
            candidate_state = _geometry_state_with_updates(state, depth=depth)
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    if strategy != "shallow":
        narrower = current_width - 50.0
        if narrower >= 250.0:
            candidate_state = _geometry_state_with_updates(state, width=narrower)
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
        if width_key != "b":
            current_rectified = _geometry_state_with_updates(state, width=current_width)
            variants[_make_auto_design_candidate_key(current_rectified)] = current_rectified
    return list(variants.values())


def generate_less_bottom_reo_variants(current_candidate: dict, mode_config: dict, context: dict) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    current_ast = float(current_candidate.get("Ast_bot", 0.0) or 0.0)
    current_complexity = float(current_candidate.get("reo_complexity", compute_reo_complexity(current_candidate)) or 0.0)
    variants: dict[tuple, dict] = {}
    for arrangement in _generate_local_bottom_arrangements(state, mode_config, band=0, context=context):
        candidate_state = dict(state)
        updates = _bottom_arrangement_to_shared_updates(arrangement)
        candidate_state.update(updates)
        preview_bottom = _effective_bottom_design_state(candidate_state, _candidate_bottom_updates(candidate_state))
        preview_candidate = {
            "state": candidate_state,
            "Ast_bot": float(preview_bottom.get("Ast_bot", 0.0) or 0.0),
            "row_count": _bottom_row_count_from_state(candidate_state),
            "bar_count": _bottom_bar_count_from_state(candidate_state, preview_bottom),
            "reo_congestion_index": _reo_congestion_index(candidate_state, preview_bottom),
        }
        preview_complexity = float(compute_reo_complexity(preview_candidate) or 0.0)
        if (
            float(preview_bottom.get("Ast_bot", 0.0) or 0.0) < current_ast - 1e-6
            or preview_complexity < current_complexity - 1e-6
        ):
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    return list(variants.values())


def generate_simpler_layout_variants(current_candidate: dict, mode_config: dict, context: dict) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    current_rows = int(current_candidate.get("row_count", 0) or 0)
    current_bars = int(current_candidate.get("bar_count", 0) or 0)
    variants: dict[tuple, dict] = {}
    for arrangement in _generate_local_bottom_arrangements(state, mode_config, band=0, context=context):
        candidate_state = dict(state)
        candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
        row_count = _bottom_row_count_from_state(candidate_state)
        bar_count = _bottom_bar_count_from_state(candidate_state, _effective_bottom_design_state(candidate_state, _candidate_bottom_updates(candidate_state)))
        if row_count < current_rows or bar_count < current_bars:
            variants[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    return list(variants.values())


def generate_compliant_refinement_candidates(current_candidate: dict, mode_config: dict, context: dict) -> list[dict]:
    candidates: dict[tuple, dict] = {}
    for candidate_state in generate_smaller_geometry_variants(current_candidate, mode_config):
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    for candidate_state in generate_less_bottom_reo_variants(current_candidate, mode_config, context):
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    _ov0 = current_candidate.get("overview")
    _sp0 = (((_ov0 or {}) if isinstance(_ov0, dict) else {}).get("packs") or {}).get("shear") or {}
    _truth_ok_variants, _ = _shear_governing_truth_allows_overdesign_cleanup(
        _sp0 if isinstance(_sp0, dict) else {},
    )
    if (
        _shear_cleanup_possible(dict(current_candidate.get("state") or {}))
        and not bool(context.get("disable_shear_cleanup_candidates"))
        and _truth_ok_variants
    ):
        for candidate_state in generate_less_shear_reo_variants(current_candidate, mode_config):
            candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    for candidate_state in generate_simpler_layout_variants(current_candidate, mode_config, context):
        candidates[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    candidates.pop(_make_auto_design_candidate_key(current_candidate.get("state") or {}), None)
    return list(candidates.values())[:AUTO_DESIGN_MAX_LOCAL_CANDIDATES_PER_ITER]


def _generate_local_shear_states(state: dict, mode_config: dict, *, band: int, limit: int | None = None) -> list[dict]:
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if not _shear_reinforcement_is_active(state):
        activation_state = _activation_shear_state(state)
        if _make_auto_design_candidate_key(activation_state) == _make_auto_design_candidate_key(state):
            return []
        return [activation_state]
    current_spacing = _int_from_state(state, "s_lig", 200)
    current_legs = _int_from_state(state, "lig_legs", 2)
    current_dia = _int_from_state(state, "lig_d", 10)
    spacing_values = _option_window(REO_SPACINGS, current_spacing, down_steps=0, up_steps=0)
    tighter_values = [value for value in REO_SPACINGS if value < current_spacing]
    spacing_values.extend(tighter_values[-(2 + band):])
    spacing_values = sorted(set(spacing_values), reverse=True)
    leg_values = sorted(set([current_legs, min(current_legs + 2, 6)]))
    if strategy == "shallow" and current_legs < 6:
        leg_values.append(min(current_legs + 4, 6))
    dia_values = _option_window([dia for dia in REO_BAR_DIAS if dia <= 16], current_dia, down_steps=0, up_steps=1 + band)

    states: dict[tuple, dict] = {}
    for dia in dia_values:
        for legs in leg_values:
            if int(legs) < 2:
                continue
            for spacing in spacing_values:
                candidate_state = dict(state)
                candidate_state.update({
                    "lig_d": int(dia),
                    "lig_legs": int(legs),
                    "s_lig": float(spacing),
                })
                states[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    resolved_limit = AUTO_DESIGN_MAX_STAGE_CANDIDATES if limit is None else max(int(limit), 1)
    return list(states.values())[:resolved_limit]


def generate_shallow_geometry_options(
    seed_candidate: dict,
    *,
    include_deeper: bool,
    is_first_hop: bool,
) -> list[dict]:
    seed_state = dict(seed_candidate.get("state") or {})
    if _geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    _, _, current_width = _resolve_geometry_width_context(seed_state)
    target_depths = [seed_depth - 100.0, seed_depth - 50.0, seed_depth]
    if include_deeper:
        target_depths.extend([seed_depth + 50.0, seed_depth + 100.0])
    width_steps = [current_width, current_width + 50.0]
    if is_first_hop:
        width_steps.append(current_width + 100.0)

    options: dict[tuple, dict] = {}
    for depth in target_depths:
        if depth < 350.0:
            continue
        for width in width_steps:
            candidate_state = _geometry_state_with_updates(seed_state, depth=depth, width=width)
            options[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    return list(options.values())


def _solve_reo_for_geometry(geometry_state: dict, *, mode_config: dict, seed_candidate: dict, eval_cache: dict, metrics: dict) -> dict | None:
    _bind_auto_design_solver_dependencies(globals())
    return _solve_reo_for_geometry_extracted(geometry_state, mode_config=mode_config, seed_candidate=seed_candidate, eval_cache=eval_cache, metrics=metrics)


def solve_best_reo_for_fixed_depth(candidate_state: dict, mode_config: dict, seed_candidate: dict, eval_cache: dict, metrics: dict) -> dict | None:
    return _solve_reo_for_geometry(candidate_state, mode_config=mode_config, seed_candidate=seed_candidate, eval_cache=eval_cache, metrics=metrics)


def solve_simplest_reo_for_geometry(candidate_state: dict, mode_config: dict, seed_candidate: dict, eval_cache: dict, metrics: dict) -> dict | None:
    return _solve_reo_for_geometry(candidate_state, mode_config=mode_config, seed_candidate=seed_candidate, eval_cache=eval_cache, metrics=metrics)


def solve_balanced_reo_for_geometry(candidate_state: dict, mode_config: dict, seed_candidate: dict, eval_cache: dict, metrics: dict) -> dict | None:
    return _solve_reo_for_geometry(candidate_state, mode_config=mode_config, seed_candidate=seed_candidate, eval_cache=eval_cache, metrics=metrics)


def _choose_better_mode_candidate(current_best: dict | None, candidate: dict | None, mode_config: dict) -> dict | None:
    if candidate is None:
        return current_best
    if current_best is None:
        return candidate
    if candidate_materially_worsens(candidate, current_best, mode_config, phase="mode_search"):
        return current_best
    if not bool(current_best.get("is_compliant")):
        return select_best_next_hop_candidate(current_best, [current_best, candidate], mode_config, phase="solve_to_pass") or current_best
    if _candidate_sort_key_for_mode(candidate, mode_config) < _candidate_sort_key_for_mode(current_best, mode_config):
        return candidate
    return current_best


def optimise_shallow(seed_candidate: dict, mode_config: dict, eval_cache: dict, metrics: dict, *, is_first_hop: bool = False) -> dict:
    best = seed_candidate
    seed_state = dict(seed_candidate.get("state") or {})
    seed_depth = float(seed_candidate.get("depth", _float_from_state(seed_state, "D", 600.0)) or _float_from_state(seed_state, "D", 600.0))
    _, _, current_width = _resolve_geometry_width_context(seed_state)
    same_geometry_candidate = solve_best_reo_for_fixed_depth(seed_state, mode_config, seed_candidate, eval_cache, metrics)
    best = _choose_better_mode_candidate(best, same_geometry_candidate, mode_config) or best
    if same_geometry_candidate and candidate_is_good_enough(same_geometry_candidate, mode_config, reference_candidate=seed_candidate):
        return same_geometry_candidate

    priority_states: dict[tuple, dict] = {}
    if is_first_hop:
        for depth, width in (
            (seed_depth - 50.0, current_width + 100.0),
            (seed_depth - 50.0, current_width + 50.0),
            (seed_depth, current_width + 50.0),
        ):
            if depth < 350.0:
                continue
            candidate_state = _geometry_state_with_updates(seed_state, depth=depth, width=width)
            priority_states[_make_auto_design_candidate_key(candidate_state)] = candidate_state
    for geometry_state in priority_states.values():
        if metrics.get("cap_hit"):
            return best
        candidate = solve_best_reo_for_fixed_depth(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
        best = _choose_better_mode_candidate(best, candidate, mode_config) or best
        if candidate and candidate_is_good_enough(candidate, mode_config, reference_candidate=seed_candidate):
            return candidate

    if not is_first_hop and not bool(seed_candidate.get("is_compliant")):
        for geometry_state in generate_slightly_deeper_depths(seed_candidate):
            if metrics.get("cap_hit"):
                return best
            candidate = solve_best_reo_for_fixed_depth(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
            best = _choose_better_mode_candidate(best, candidate, mode_config) or best
            if candidate and is_valid_progress_while_failing(candidate, seed_candidate):
                return candidate
    for geometry_state in generate_shallow_geometry_options(seed_candidate, include_deeper=False, is_first_hop=is_first_hop):
        if metrics.get("cap_hit"):
            return best
        candidate = solve_best_reo_for_fixed_depth(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
        best = _choose_better_mode_candidate(best, candidate, mode_config) or best
        if candidate and candidate_is_good_enough(candidate, mode_config, reference_candidate=seed_candidate):
            return candidate

    for geometry_state in generate_shallow_geometry_options(seed_candidate, include_deeper=True, is_first_hop=is_first_hop):
        if float(geometry_state.get("D", seed_candidate.get("depth", 0.0)) or 0.0) <= float(seed_candidate.get("depth", 0.0) or 0.0):
            continue
        if metrics.get("cap_hit"):
            return best
        candidate = solve_best_reo_for_fixed_depth(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
        best = _choose_better_mode_candidate(best, candidate, mode_config) or best
        if candidate and candidate_is_good_enough(candidate, mode_config, reference_candidate=seed_candidate):
            return candidate

    return best


def optimise_low_reo(seed_candidate: dict, mode_config: dict, eval_cache: dict, metrics: dict, *, is_first_hop: bool = False) -> dict:
    best = seed_candidate
    same_geometry_candidate = solve_simplest_reo_for_geometry(seed_candidate["state"], mode_config, seed_candidate, eval_cache, metrics)
    best = _choose_better_mode_candidate(best, same_geometry_candidate, mode_config) or best
    if same_geometry_candidate and candidate_is_good_enough(same_geometry_candidate, mode_config, reference_candidate=seed_candidate):
        return same_geometry_candidate
    for geometry_state in generate_same_or_larger_geometry_options(seed_candidate):
        if metrics.get("cap_hit"):
            return best
        candidate = solve_simplest_reo_for_geometry(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
        best = _choose_better_mode_candidate(best, candidate, mode_config) or best
        if candidate and candidate_is_good_enough(candidate, mode_config, reference_candidate=seed_candidate):
            return candidate
    return best


def optimise_balanced(seed_candidate: dict, mode_config: dict, eval_cache: dict, metrics: dict) -> dict:
    best = solve_balanced_reo_for_geometry(seed_candidate["state"], mode_config, seed_candidate, eval_cache, metrics) or seed_candidate
    if candidate_is_good_enough(best, mode_config, reference_candidate=seed_candidate) and _allow_early_target_exit(mode_config):
        return best

    for geometry_state in _generate_balanced_geometry_options(seed_candidate):
        if metrics.get("cap_hit"):
            return best
        candidate = solve_balanced_reo_for_geometry(geometry_state, mode_config, seed_candidate, eval_cache, metrics)
        best = _choose_better_mode_candidate(best, candidate, mode_config) or best
        if candidate and candidate_is_good_enough(candidate, mode_config, reference_candidate=seed_candidate) and _allow_early_target_exit(mode_config):
            return candidate
    return best


def _run_mode_objective_search(seed_candidate: dict, mode_config: dict, eval_cache: dict, metrics: dict, *, is_first_hop: bool = False) -> dict:
    if _geometry_lock_enabled((seed_candidate or {}).get("state") or {}):
        locked = solve_best_reo_for_fixed_depth(seed_candidate["state"], mode_config, seed_candidate, eval_cache, metrics)
        if locked is not None:
            return locked
        return seed_candidate
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if strategy == "shallow":
        return optimise_shallow(seed_candidate, mode_config, eval_cache, metrics, is_first_hop=is_first_hop)
    if strategy == "low_reo":
        return optimise_low_reo(seed_candidate, mode_config, eval_cache, metrics, is_first_hop=is_first_hop)
    return optimise_balanced(seed_candidate, mode_config, eval_cache, metrics)


def run_primary_auto_design(seed_candidate: dict, mode_config: dict, eval_cache: dict, metrics: dict, *, is_first_hop: bool = False) -> dict:
    _ensure_candidate_score(seed_candidate, mode_config, seed_candidate)
    if bool(seed_candidate.get("is_compliant")) and _candidate_in_target_zone(seed_candidate, mode_config):
        metrics["phase_a"] = "seed_in_target_cleanup_only"
        metrics["phase_b"] = "cleanup_only"
        return seed_candidate
    phase_results: list[dict] = [seed_candidate]
    feasibility_candidate = seed_candidate
    metrics["phase_a"] = "seed_already_compliant" if bool(seed_candidate.get("is_compliant")) else "search_for_compliance"
    if not bool(seed_candidate.get("is_compliant")):
        feasibility_candidate = _run_mode_objective_search(seed_candidate, mode_config, eval_cache, metrics, is_first_hop=is_first_hop) or seed_candidate
        _ensure_candidate_score(feasibility_candidate, mode_config, seed_candidate)
        phase_results.append(feasibility_candidate)
    objective_seed = select_final_candidate(phase_results, mode_config, baseline_candidate=seed_candidate) or feasibility_candidate or seed_candidate
    metrics["phase_b"] = "objective_search"
    objective_candidate = _run_mode_objective_search(objective_seed, mode_config, eval_cache, metrics, is_first_hop=is_first_hop) or objective_seed
    _ensure_candidate_score(objective_candidate, mode_config, seed_candidate)
    phase_results.append(objective_candidate)
    selected = select_final_candidate(phase_results, mode_config, baseline_candidate=seed_candidate) or objective_candidate or objective_seed
    metrics["primary_phase_result"] = {
        "is_compliant": bool(selected.get("is_compliant")),
        "util_gap": utilisation_gap(selected, mode_config),
        "depth": float(selected.get("depth", 0.0) or 0.0),
        "reo_complexity": float(selected.get("reo_complexity", compute_reo_complexity(selected)) or 0.0),
    }
    return selected


def run_final_tightening_pass(
    initial_candidate: dict,
    mode_config: dict,
    *,
    seed_candidate: dict,
    eval_cache: dict,
    metrics: dict,
    is_first_hop: bool = False,
) -> dict:
    _bind_auto_design_solver_dependencies(globals())
    return _run_final_tightening_pass_extracted(
        initial_candidate,
        mode_config,
        seed_candidate=seed_candidate,
        eval_cache=eval_cache,
        metrics=metrics,
        is_first_hop=is_first_hop,
    )


def run_cleanup_pass(
    initial_candidate: dict,
    mode_config: dict,
    *,
    seed_candidate: dict,
    eval_cache: dict,
    metrics: dict,
) -> dict:
    _bind_auto_design_solver_dependencies(globals())
    return _run_cleanup_pass_extracted(
        initial_candidate,
        mode_config,
        seed_candidate=seed_candidate,
        eval_cache=eval_cache,
        metrics=metrics,
    )


def run_full_auto_design(seed_candidate: dict, mode: str, force: bool = False, is_first_hop: bool = False) -> dict:
    _bind_auto_design_solver_dependencies(globals())
    return _run_full_auto_design_extracted(
        seed_candidate,
        mode,
        force=force,
        is_first_hop=is_first_hop,
    )


AUTO_DESIGN_TARGET_UTIL = 0.85


TARGET_UTIL = 0.85


def score_candidate(
    util,
    candidate: dict | None = None,
    *,
    current_ast: float | None = None,
    goal: str = "balanced",
):
    try:
        resolved_util = float(util)
    except Exception:
        return float("inf")

    score = abs(resolved_util - TARGET_UTIL)

    if resolved_util < 0.75:
        score += 0.1

    if resolved_util > 1.0:
        score += 1.0

    if isinstance(candidate, dict) and bool(candidate.get("is_compound")):
        score *= 0.9

    try:
        ast_bot = float((candidate or {}).get("Ast_bot", 0.0) or 0.0)
    except Exception:
        ast_bot = 0.0
    if current_ast is not None and current_ast > 0.0 and ast_bot > 1.3 * current_ast:
        score += 0.2

    return float(score)


def collect_failures(results: dict) -> list[tuple[str, float]]:
    failures: list[tuple[str, float]] = []
    bending_util = (results.get("bending") or {}).get("util")
    try:
        if bending_util is not None and float(bending_util) > 1.0:
            failures.append(("bending", float(bending_util)))
    except Exception:
        pass

    shear_util = (results.get("shear") or {}).get("util")
    try:
        if shear_util is not None and float(shear_util) > 1.0:
            failures.append(("shear", float(shear_util)))
    except Exception:
        pass

    ductility = dict(results.get("ductility") or {})
    try:
        ku_value = ductility.get("ku")
        ku_limit = ductility.get("limit")
        if ku_value is not None and ku_limit is not None and float(ku_value) > float(ku_limit):
            failures.append(("ductility", float(ku_value)))
    except Exception:
        pass

    return failures


def choose_strategy(failures: list[tuple[str, float]]) -> str:
    types = [failure_type for failure_type, _ in failures]
    if "ductility" in types:
        return "increase_depth"
    if "bending" in types:
        return "increase_capacity"
    if "shear" in types:
        return "increase_shear"
    return "optimise"


def _apply_bottom_bar_count_update(candidate: dict, state: dict, new_total: int) -> None:
    current_bot2 = _int_from_state(state, "bot2_count", 0)
    if current_bot2 > 0:
        new_bot1 = max(2, int(math.ceil(new_total / 2.0)))
        new_bot2 = max(0, int(new_total - new_bot1))
    else:
        new_bot1 = max(2, int(new_total))
        new_bot2 = 0
    candidate["bot1_count"] = int(new_bot1)
    candidate["bot2_count"] = int(new_bot2)
    candidate["bot_row_count"] = 2 if new_bot2 > 0 else 1
    candidate["nb_bot"] = int(new_bot1 + new_bot2)


def _candidate_worst_util_value(candidate: dict | None) -> float:
    if not isinstance(candidate, dict):
        return float("inf")
    value = candidate.get("worst_util")
    if value is None:
        value = dict(candidate.get("overview") or {}).get("worst_util")
    try:
        return float(value) if value is not None else float("inf")
    except Exception:
        return float("inf")


def _results_worst_util(results: dict | None) -> float:
    try:
        value = dict((results or {}).get("_overview") or {}).get("worst_util")
        return float(value) if value is not None else float("inf")
    except Exception:
        return float("inf")


def _scaled_bottom_total_for_factor(state: dict, factor: float) -> int:
    current_total_bottom = max(
        _int_from_state(state, "bot1_count", 0) + _int_from_state(state, "bot2_count", 0),
        _int_from_state(state, "nb_bot", 0),
        2,
    )
    safe_factor = max(float(factor or 1.0), 1.0)
    return max(current_total_bottom + 1, int(math.ceil(current_total_bottom * safe_factor)))


def _build_progressive_candidate_updates(
    state: dict,
    results: dict,
    failures: list[tuple[str, float]],
    *,
    strategy: str,
) -> list[tuple[str, dict]]:
    _bind_auto_design_solver_dependencies(globals())
    return _build_progressive_candidate_updates_extracted(
        state,
        results,
        failures,
        strategy=strategy,
    )


def _evaluate_progressive_candidate_update(
    state: dict,
    updates: dict,
    *,
    pass_idx: int,
    candidate_type: str,
) -> dict | None:
    if not updates:
        return None
    trial_state = dict(state)
    trial_state.update(updates)
    evaluated = evaluate_candidate_full(
        _guidance_state_snapshot(trial_state),
        source=f"progressive_auto_design_pass_{int(pass_idx)}",
        label=f"Progressive {candidate_type}",
        action_type="auto_design",
        updates=dict(updates),
    )
    if not isinstance(evaluated, dict):
        return None
    candidate = dict(evaluated)
    candidate["state"] = dict(candidate.get("state") or trial_state)
    candidate["updates"] = dict(updates)
    candidate["candidate_type"] = str(candidate_type)
    candidate["candidate_priority"] = {"compound": 0, "geometry": 1, "reo": 2}.get(str(candidate_type), 9)
    candidate.setdefault("label", f"Progressive {candidate_type} update")
    return candidate


def build_candidate(state: dict, strategy: str, results: dict) -> dict:
    candidate: dict[str, object] = {}
    bending_util = (results.get("bending") or {}).get("util")
    row_count = int(results.get("row_count", 1) or 1)
    width_key, _, current_width = _resolve_geometry_width_context(state)
    current_depth = _float_from_state(state, "D", 600.0)
    current_total_bottom = max(
        _int_from_state(state, "bot1_count", 0) + _int_from_state(state, "bot2_count", 0),
        _int_from_state(state, "nb_bot", 0),
        2,
    )

    if strategy == "increase_capacity":
        util_ratio = 1.05
        try:
            if bending_util is not None:
                util_ratio = max(float(bending_util) / AUTO_DESIGN_TARGET_UTIL, 1.02)
        except Exception:
            util_ratio = 1.05
        suggested_total = max(current_total_bottom + 1, int(math.ceil(current_total_bottom * util_ratio)))
        _apply_bottom_bar_count_update(candidate, state, suggested_total)

        depth_multiplier = 1.05
        try:
            if bending_util is not None and float(bending_util) > 1.2:
                depth_multiplier = 1.10
        except Exception:
            pass
        candidate["D"] = float(current_depth * depth_multiplier)

    elif strategy == "increase_depth":
        candidate["D"] = float(current_depth * 1.10)

    elif strategy == "increase_shear":
        current_spacing = _float_from_state(state, "s_lig", 200.0)
        candidate["s_lig"] = float(max(75.0, current_spacing * 0.7))
        candidate["lig_legs"] = int(max(_int_from_state(state, "lig_legs", 2), 2))

    elif strategy == "optimise":
        suggested_total = max(2, current_total_bottom - 1)
        _apply_bottom_bar_count_update(candidate, state, suggested_total)

    if row_count > 3:
        candidate[width_key] = float(current_width * 1.10)
        if width_key != "b":
            candidate["b"] = float(current_width * 1.10)

    return candidate


def run_auto_design_step(state: dict, results: dict) -> tuple[dict | None, list[tuple[str, float]], str]:
    failures = collect_failures(results)
    if not failures:
        return None, failures, "optimise"
    strategy = choose_strategy(failures)
    candidate = build_candidate(state, strategy, results)
    if not candidate:
        return None, failures, strategy
    return candidate, failures, strategy


def run_auto_design_solver(state: dict, results: dict) -> dict | None:
    """
    Internal progressive auto-design subroutine for the Recommendation Engine.
    Not a top-level entrypoint: callers should use _compute_design_guidance_items(..., request_kind="auto_design").
    """
    _bind_auto_design_solver_dependencies(globals())
    return _run_auto_design_solver_extracted(state, results)


def _one_click_objective_distance_to_band(util: float, mode_config: dict) -> float:
    lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    hi = float(mode_config.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    if not math.isfinite(util):
        return float("inf")
    if lo <= util <= hi:
        return 0.0
    if util < lo:
        return lo - util
    return util - hi


def _one_click_step_improves(new_eval: dict, old_eval: dict, mode_config: dict) -> bool:
    return _resolve_candidate_step_improves(
        new_eval,
        old_eval,
        mode_config,
        default_target_min=EFFICIENCY_TARGET_UTIL_MIN,
        default_target_max=EFFICIENCY_TARGET_UTIL_MAX,
        fail_status=BEAM_STATUS_FAIL,
        optimisation_goal_resolver=_design_optimisation_goal,
    )


def _one_click_tightening_mode_active(cur_eval: dict, mode_config: dict) -> bool:
    """True when checks pass but utilisation is materially below the target band."""
    cur_pass = bool((cur_eval.get("overview") or {}).get("all_key_pass"))
    domains = cur_eval.get("target_domains_for_band")
    if cur_pass and isinstance(domains, (list, tuple, set)) and domains:
        try:
            lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
        except Exception:
            lo = float(EFFICIENCY_TARGET_UTIL_MIN)
        overview = cur_eval.get("overview") or {}
        utils = dict(overview.get("utils") or {})
        bend_util = _candidate_bending_demand_util(cur_eval)
        if bend_util is None:
            bend_util = utils.get("bending")
        values = []
        for d in domains:
            if str(d).lower() == "bending":
                values.append(bend_util)
            elif str(d).lower() == "shear":
                values.append(utils.get("shear"))
        parsed = []
        for v in values:
            try:
                f = float(v)
                if math.isfinite(f):
                    parsed.append(f)
            except Exception:
                pass
        return bool(parsed and any(v < lo - 1e-6 for v in parsed))

    try:
        lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    except Exception:
        lo = float(EFFICIENCY_TARGET_UTIL_MIN)
    cur_u = _candidate_objective_util(cur_eval)
    return bool(cur_pass and math.isfinite(cur_u) and cur_u < lo - 1e-6)


def _one_click_still_materially_under_target(cur_eval: dict, mode_config: dict, *, margin: float = 0.03) -> bool:
    """True when state passes checks but remains materially below lower target bound."""
    try:
        lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    except Exception:
        lo = float(EFFICIENCY_TARGET_UTIL_MIN)
    cur_pass = bool((cur_eval.get("overview") or {}).get("all_key_pass"))
    if _candidate_target_domains_for_band(cur_eval):
        return bool(
            cur_pass
            and _candidate_target_band_under_domains(cur_eval, mode_config, margin=float(max(0.0, margin))),
        )
    cur_u = _candidate_objective_util(cur_eval)
    return bool(cur_pass and math.isfinite(cur_u) and cur_u < (lo - float(max(0.0, margin))))


def _one_click_attach_eval_target_domains(
    eval_obj: dict | None,
    target_domains_for_band,
    mode_config: dict,
) -> None:
    """Attach target band domains (from base + touched updates) and work-domain hint for scoring."""
    if not isinstance(eval_obj, dict):
        return
    raw_domains = [d for d in ("bending", "shear") if d in set(target_domains_for_band or [])]
    overview = dict((eval_obj.get("overview") or {}))
    statuses = dict(overview.get("statuses") or {})
    try:
        actions_ctx = _build_design_actions_context_isolated(dict(eval_obj.get("state") or {}))
        actions = dict(actions_ctx.get("actions") or {})
    except Exception:
        actions = {}

    def _domain_relevant(domain: str) -> bool:
        status = str(statuses.get(domain) or "").strip().upper()
        if status == "FAIL":
            return True
        if domain == "shear":
            return not _shear_demands_negligible(actions)
        if domain == "bending":
            return not _bending_demands_negligible(actions)
        return True

    domains = [d for d in raw_domains if _domain_relevant(d)]
    if not domains:
        eval_obj.pop("target_domains_for_band", None)
        eval_obj.pop("target_domain_for_band", None)
        return
    eval_obj["target_domains_for_band"] = domains
    wd = _candidate_target_domain_needing_work(eval_obj, mode_config)
    if wd:
        eval_obj["target_domain_for_band"] = wd
    else:
        eval_obj.pop("target_domain_for_band", None)


def _one_click_update_direction_summary(base_state: dict, updates: dict) -> dict:
    """Compact growth/reduction direction tags for tightening-mode filtering."""
    base = _guidance_state_snapshot(dict(base_state or {}))
    trial = copy.deepcopy(base)
    trial.update(dict(updates or {}))
    trial = _guidance_state_snapshot(trial)
    bw = float(_design_width_value(base) or 0.0)
    tw = float(_design_width_value(trial) or 0.0)
    bd = float(_float_from_state(base, "D", 0.0) or 0.0)
    td = float(_float_from_state(trial, "D", 0.0) or 0.0)
    bast = float((_effective_bottom_design_state(base) or {}).get("Ast_bot", 0.0) or 0.0)
    tast = float((_effective_bottom_design_state(trial) or {}).get("Ast_bot", 0.0) or 0.0)
    geo_growth = bool(tw > bw + 1e-6 or td > bd + 1e-6)
    geo_reduction = bool(tw < bw - 1e-6 or td < bd - 1e-6)
    steel_growth = bool(tast > bast + 1e-6)
    steel_reduction = bool(tast < bast - 1e-6)
    return {
        "geometry_growth": geo_growth,
        "geometry_reduction": geo_reduction,
        "steel_growth": steel_growth,
        "steel_reduction": steel_reduction,
        "is_growth_only": bool((geo_growth or steel_growth) and not (geo_reduction or steel_reduction)),
        "is_reduction_candidate": bool(geo_reduction or steel_reduction),
    }


def _generate_shear_governing_candidates(
    working_state: dict,
    cur_eval: dict,
    mode_config: dict,
) -> tuple[list[dict], dict]:
    _bind_shear_governing_candidate_dependencies(globals())
    return _generate_shear_governing_candidates_extracted(working_state, cur_eval, mode_config)


def _one_click_norm_updates_contain_shear_link_keys(norm_updates: dict | None) -> bool:
    u = dict(norm_updates or {})
    return any(k in u for k in ("lig_d", "lig_legs", "s_lig"))


def _one_click_candidate_is_shear_governing_for_prune(*, family_hint: str, norm_updates: dict | None) -> bool:
    """
    Shear-governing classification for early pruning.

    Primary signal is the explicit tightening family taxonomy / guidance family tag.
    Secondary signal (tiny exception) is direct shear-link keys in normalized updates,
    which covers rare cases where family_hint is generic but the candidate is still a shear move.
    """
    fam = str(family_hint or "").strip().lower()
    if "cleanup" in fam or fam.endswith("_cleanup") or fam == "non_governing_cleanup":
        return False
    if _candidate_family_matches_governing_domain(family_hint, "shear"):
        return True
    return _one_click_norm_updates_contain_shear_link_keys(norm_updates)


def _one_click_generate_multi_domain_refinement_states(
    working_state: dict,
    cur_eval: dict,
    mode_config: dict,
) -> list[dict]:
    _bind_governing_domain_tightening_candidates_dependencies(globals())
    return _one_click_generate_multi_domain_refinement_states_extracted(
        working_state,
        cur_eval,
        mode_config,
    )


def _generate_tightening_candidates_for_governing_domain(
    working_state: dict,
    cur_eval: dict,
    mode_config: dict,
    *,
    tightening_step_count: int = 0,
) -> tuple[list[dict], dict]:
    """
    Governing-action-first tightening candidate orchestration.
    Returns (prioritized_candidates, trace_meta).
    """
    _bind_governing_domain_tightening_candidates_dependencies(globals())
    return _generate_tightening_candidates_for_governing_domain_extracted(
        working_state,
        cur_eval,
        mode_config,
        tightening_step_count=tightening_step_count,
    )


def _one_click_collect_actionable_guidance_candidates(
    working_state: dict,
    *,
    debug_enabled: bool,
    trace_run_id: str | None = None,
    trace_step: int | None = None,
) -> tuple[list[dict], int]:
    _bind_actionable_guidance_candidate_dependencies(globals())
    return _one_click_collect_actionable_guidance_candidates_extracted(
        working_state,
        debug_enabled=debug_enabled,
        trace_run_id=trace_run_id,
        trace_step=trace_step,
    )


def _guidance_bucket(status: str, util: float | None = None) -> str:
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


def _guidance_priority(bucket: str, util: float | None) -> float:
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


def _format_guidance_title(title: str, util: float | None) -> str:
    if util is None:
        return title
    return f"{title} (utilisation = {util:.2f})"


def _guidance_item(
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
) -> dict:
    bucket = _guidance_bucket(status, util)
    out: dict = {
        "check_key": check_key,
        "title_main": title,
        "title_util": f"(utilisation = {util:.2f})" if util is not None else None,
        "title": _format_guidance_title(title, util),
        "primary_action": primary_action,
        "secondary_action": secondary_action,
        "reasoning": reasoning,
        "levers": levers,
        "status": status,
        "bucket": bucket,
        "util": util,
        "priority": _guidance_priority(bucket, util),
        "action_type": action_type,
        "action_payload": action_payload or {},
    }
    if guidance_before_after:
        out["guidance_before_after"] = guidance_before_after
    if guidance_change_lines:
        out["guidance_change_lines"] = [str(x) for x in guidance_change_lines if str(x).strip()]
    if guidance_why:
        out["guidance_why"] = str(guidance_why)
    return out


def _guidance_before_after_text(item: dict, state: dict) -> str | None:
    action_type = item.get("action_type")
    if not action_type:
        return None
    expensive_action_types = {
        "apply_mode_recommendation",
        "apply_bottom_recommendation",
        "apply_geometry_recommendation",
        "apply_shear_recommendation",
        "apply_compound_guidance",
        "reduce_bottom_reinforcement",
        "increase_link_spacing",
        "reduce_number_of_legs",
    }
    if action_type in expensive_action_types:
        return None
    updates = _guidance_action_updates(action_type, item.get("action_payload") or {}, state=state)
    if not updates:
        return None
    after_state = dict(state)
    after_state.update(updates)
    return _describe_guidance_step(state, after_state, action_type, updates)


def _efficiency_guidance_items(state: dict, efficiency_state: dict) -> list[dict]:
    _bind_efficiency_guidance_item_dependencies(globals())
    return _efficiency_guidance_items_extracted(state, efficiency_state)


def _passing_guidance_item(state: dict, overview: dict) -> dict:
    return _guidance_item(
        "general",
        "Design has workable reserve",
        "Review the optimisation goal before changing geometry or reinforcement.",
        "Optional refinements should be checked against the governing utilisation target.",
        (
            f"Why: the current beam satisfies the published checks for "
            f"{_design_optimisation_goal_label(state).lower()} with worst utilisation {overview['worst_util']:.2f}."
        ),
        "Key levers: depth D, reinforcement, load path",
        None,
        None,
        status="PASS",
        util=overview["worst_util"],
    )


def _optimal_guidance_item(state: dict, overview: dict) -> dict:
    item = _guidance_item(
        "general",
        "Design is efficient - further reductions would weaken capacity",
        "The current section is within the target utilisation range.",
        "The current design is the best practical balance found, not just safe enough.",
        (
            "Why: the solver did not find a smaller practical option that stayed inside the target "
            f"range ({EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f}). Further reduction "
            "would lower bending reserve, shear reserve, or stiffness."
        ),
        "Key levers: optimisation preference, geometry, reinforcement",
        None,
        None,
        status="PASS",
        util=overview["worst_util"],
    )
    item["design_guide_terminal_state"] = "optimal"
    return item


def _very_low_demand_guidance_item(state: dict, overview: dict) -> dict:
    item = _guidance_item(
        "general",
        "Design demand is very low",
        "No optimisation recommendation",
        "Optional: adjust actions or geometry only if you intend a different design intent.",
        (
            f"Why: worst utilisation is {overview['worst_util']:.2f} with all checks passing — demand is "
            "too small for meaningful efficiency tightening guidance."
        ),
        "Key levers: actions, geometry, reinforcement (optional exploration only)",
        None,
        None,
        status="PASS",
        util=overview["worst_util"],
    )
    item["design_guide_terminal_state"] = "very_low_demand"
    return item


def _candidate_is_materially_actionable(
    state: dict,
    updates: dict | None,
    *,
    delta_b_mm: float | None = None,
    delta_D_mm: float | None = None,
    delta_Ast_bot: float | None = None,
    guidance_change_lines: list | None = None,
) -> bool:
    _bind_actionable_guidance_candidate_dependencies(globals())
    return _candidate_is_materially_actionable_extracted(
        state,
        updates,
        delta_b_mm=delta_b_mm,
        delta_D_mm=delta_D_mm,
        delta_Ast_bot=delta_Ast_bot,
        guidance_change_lines=guidance_change_lines,
    )


def _in_band_goal_alignment_penalty(cand: dict | None, goal: str) -> float:
    if not isinstance(cand, dict):
        return 1e9
    st = dict(cand.get("state") or {})
    d_val = float(cand.get("depth") or _float_from_state(st, "D", 0.0) or 0.0)
    b_val = float(cand.get("width") or _design_width_value(st) or 0.0)
    ast_val = float(cand.get("Ast_bot", 0.0) or 0.0)
    rc = float(compute_reo_complexity(cand))
    if goal == "shallower_beam":
        return d_val * 0.14 + b_val * 0.035 + ast_val * 0.016 + rc * 4.5
    return ast_val * 0.055 + rc * 9.0 + d_val * 0.055 + b_val * 0.038


def _in_band_strict_material_passes(rec: dict, state: dict, updates: dict) -> bool:
    try:
        db = abs(float(rec.get("delta_b_mm") or 0.0))
        d_d = abs(float(rec.get("delta_D_mm") or 0.0))
        d_ast = abs(float(rec.get("delta_Ast_bot") or 0.0))
    except (TypeError, ValueError):
        return False
    compound = bool(rec.get("recommendation_compound"))
    u = dict(updates or {})
    layout_keys = (
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "bot_row_count",
    )
    has_layout = any(k in u for k in layout_keys)
    if d_ast >= IN_BAND_MIN_AST_DELTA_MM2 or d_d >= IN_BAND_MIN_DEPTH_DELTA_MM or db >= IN_BAND_MIN_WIDTH_ALONE_MM:
        return True
    if compound and (
        d_ast >= IN_BAND_COMPOUND_MIN_AST_MM2
        or db >= IN_BAND_COMPOUND_MIN_WIDTH_MM
        or d_d >= IN_BAND_COMPOUND_MIN_DEPTH_MM
        or (has_layout and d_ast >= 45.0)
    ):
        return True
    if has_layout and d_ast >= 80.0:
        return True
    if has_layout and db >= 35.0 and d_ast >= 35.0:
        return True
    return False


def _mode_difference_is_material(rec: dict) -> bool:
    tag = str(rec.get("recommendation_family_tag") or "")
    try:
        db = abs(float(rec.get("delta_b_mm") or 0.0))
    except (TypeError, ValueError):
        db = 0.0
    if tag == "pure_geometry_width" and db < IN_BAND_MIN_WIDTH_ALONE_MM - 1e-9:
        return False
    return True


def _in_band_override_is_strong(rec: dict) -> bool:
    """Extra guard so in-band states do not surface weak refinements."""
    try:
        db = abs(float(rec.get("delta_b_mm") or 0.0))
        d_d = abs(float(rec.get("delta_D_mm") or 0.0))
        d_ast = abs(float(rec.get("delta_Ast_bot") or 0.0))
    except (TypeError, ValueError):
        return False
    if d_d >= 40.0:
        return True
    if d_ast >= 140.0:
        return True
    if db >= 60.0 and d_ast >= 60.0:
        return True
    if bool(rec.get("recommendation_compound")) and (d_d >= 30.0 or db >= 45.0 or d_ast >= 110.0):
        return True
    return False


def _should_override_target_band_done_state(
    rec: dict,
    state: dict,
    overview: dict,
    goal: str,
    mode_config: dict,
    seed_cand: dict | None,
    trial_cand: dict | None,
    *,
    debug_extra: dict | None = None,
) -> tuple[bool, str]:
    if isinstance(debug_extra, dict):
        debug_extra["in_band_overview_worst_util"] = overview.get("worst_util")
    updates = dict(rec.get("updates") or {})
    if not _in_band_strict_material_passes(rec, state, updates):
        if isinstance(debug_extra, dict):
            debug_extra["in_band_materiality_passed"] = False
        return False, "in_band_strict_materiality_fail"
    if isinstance(debug_extra, dict):
        debug_extra["in_band_materiality_passed"] = True
    if not _in_band_override_is_strong(rec):
        if isinstance(debug_extra, dict):
            debug_extra["in_band_strong_override_passed"] = False
        return False, "in_band_override_not_strong_enough"
    if isinstance(debug_extra, dict):
        debug_extra["in_band_strong_override_passed"] = True
    if not _mode_difference_is_material(rec):
        if isinstance(debug_extra, dict):
            debug_extra["mode_difference_material"] = False
        return False, "mode_difference_not_material_pure_geometry_width_nudge"
    if isinstance(debug_extra, dict):
        debug_extra["mode_difference_material"] = True
    if not seed_cand or not trial_cand:
        if isinstance(debug_extra, dict):
            debug_extra["current_goal_alignment_score"] = None
            debug_extra["winner_goal_alignment_score"] = None
            debug_extra["goal_alignment_improvement"] = None
        return False, "missing_seed_or_trial_candidate_for_goal_align"
    pen_c = _in_band_goal_alignment_penalty(seed_cand, goal)
    pen_w = _in_band_goal_alignment_penalty(trial_cand, goal)
    imp = float(pen_c) - float(pen_w)
    if isinstance(debug_extra, dict):
        debug_extra["current_goal_alignment_score"] = pen_c
        debug_extra["winner_goal_alignment_score"] = pen_w
        debug_extra["goal_alignment_improvement"] = imp
    min_gap = IN_BAND_GOAL_ALIGN_MIN_SHALLOW if goal == "shallower_beam" else IN_BAND_GOAL_ALIGN_MIN_BALANCED
    if imp < min_gap - 1e-9:
        return False, "goal_alignment_improvement_below_threshold"
    if goal == "shallower_beam":
        d0 = float(seed_cand.get("depth") or 0.0)
        d1 = float(trial_cand.get("depth") or 0.0)
        if d1 > d0 + 1e-6 and imp < IN_BAND_SHALLOW_DEPTH_UP_MIN_GAIN - 1e-9:
            return False, "shallower_depth_increase_requires_stronger_goal_gain"
    if isinstance(debug_extra, dict):
        debug_extra["in_band_mode_search_strategy"] = str(mode_config.get("search_strategy", "") or "")
    return True, "override_allowed"


def _get_actionable_target_band_winner(
    state: dict,
    overview: dict,
    *,
    debug_extra: dict | None = None,
) -> dict | None:
    _bind_actionable_target_band_winner_dependencies(globals())
    return _get_actionable_target_band_winner_extracted(
        state,
        overview,
        debug_extra=debug_extra,
    )


def _guidance_start_item(state: dict) -> dict:
    _, start_line = _fast_start_here_content(state)
    item = _guidance_item(
        "general",
        "Choose your workflow:",
        start_line,
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


def _fast_start_here_content(state: dict) -> tuple[str, str]:
    _, _, width = _resolve_geometry_width_context(state)
    depth = _float_from_state(state, "D", 0.0)
    span = _float_from_state(state, "L", 0.0)
    has_geometry = any(value > 0.0 for value in (width, depth, span))

    action_values = [
        abs(_uls_action_from_state(state, "M")),
        abs(_uls_action_from_state(state, "V")),
        abs(_uls_action_from_state(state, "N")),
        abs(_uls_action_from_state(state, "T")),
    ]
    has_actions = max(action_values, default=0.0) > 1e-9

    has_bottom_reo = (
        (
            _int_from_state(state, "bot1_count", 0) > 0
            or _int_from_state(state, "bot_row_1_bars", 0) > 0
            or _int_from_state(state, "nb_bot", 0) > 0
        )
        and (
            _float_from_state(state, "db_bot_1", 0.0) > 0.0
            or _float_from_state(state, "bot_row_1_dia", 0.0) > 0.0
            or _float_from_state(state, "db_bot", 0.0) > 0.0
        )
    )
    has_shear_reo = (
        _int_from_state(state, "lig_legs", 0) > 0
        and _float_from_state(state, "lig_d", 0.0) > 0.0
        and _float_from_state(state, "s_lig", 0.0) > 0.0
    )
    is_continue = has_geometry or has_actions or has_bottom_reo or has_shear_reo
    return (
        "CONTINUE" if is_continue else "START",
        "Add reinforcement or loads to activate checks" if is_continue else "Start by setting geometry or reinforcement",
    )


def _log_guidance_ladder_debug(
    ladder_name: str,
    *,
    candidate_label: str,
    candidate_updates: dict | None,
    decision: str,
    reason: str,
    metric_name: str,
    metric_before: float | None,
    metric_after: float | None,
    early_stop: bool = False,
) -> None:
    if not DEBUG_DESIGN_GUIDANCE_PROBE:
        return
    _agent_debug_log(
        "Guidance ladder step",
        {
            "ladder": ladder_name,
            "candidate_label": candidate_label,
            "candidate_updates": candidate_updates,
            "decision": decision,
            "reason": reason,
            "metric_name": metric_name,
            "metric_before": metric_before,
            "metric_after": metric_after,
            "early_stop": bool(early_stop),
        },
        location="inputs_page.py:_log_guidance_ladder_debug",
        hypothesis_id="H_GUIDANCE_LADDER",
    )


def _merge_guidance_state(state: dict, updates: dict) -> dict:
    merged = dict(state)
    merged.update(updates)
    return merged


def _geometry_trial_delta_mm_total(state: dict, updates: dict) -> float:
    d0 = float(state.get("D", 0.0) or 0.0)
    d1 = float(updates.get("D", d0) or d0)
    wkey, _, w0 = _resolve_geometry_width_context(state)
    w0 = float(w0 or 0.0)
    if wkey in updates:
        w1 = float(updates[wkey] or 0.0)
    else:
        w1 = w0
    return abs(d1 - d0) + abs(w1 - w0)


def _geometry_width_depth_trial_specs() -> list[tuple[str, str, dict]]:
    specs: list[tuple[str, str, dict]] = []
    for d in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
        specs.append((f"Increase depth D by {d} mm", "increase_depth", {"delta_mm": float(d)}))
    for d in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
        specs.append((f"Increase section width by {d} mm", "increase_width", {"delta_mm": float(d)}))
    return specs


def _read_metric_for_geometry_trial(
    state: dict,
    *,
    metric: str,
    bending_mode: str = "governing",
) -> float | None:
    _bind_geometry_trial_selector_dependencies(globals())
    return _read_metric_for_geometry_trial_extracted(
        state,
        metric=metric,
        bending_mode=bending_mode,
    )


def _choose_geometry_trial_for_metric(
    state: dict,
    *,
    metric: str,
    baseline_util: float | None = None,
    bending_mode: str = "governing",
    ladder_name: str = "geometry_trial",
) -> dict | None:
    _bind_geometry_trial_selector_dependencies(globals())
    return _choose_geometry_trial_for_metric_extracted(
        state,
        metric=metric,
        baseline_util=baseline_util,
        bending_mode=bending_mode,
        ladder_name=ladder_name,
    )


def _crack_ladder_tighten_spacing_updates(state: dict) -> dict | None:
    if str(state.get("bot1_layout_mode", "Count") or "Count") != "Spacing":
        return None
    return _guidance_action_updates(
        "reduce_bar_spacing",
        {"delta_mm": 25.0, "minimum_spacing": float(min(REO_SPACINGS))},
        state=state,
    )


def _crack_ladder_add_one_bottom_bar_updates(state: dict) -> dict | None:
    current_count = int(state.get("bot1_count", 4) or 4)
    current_count_2 = int(state.get("bot2_count", 0) or 0)
    db1 = int(state.get("db_bot_1", 20) or 20)
    db2 = int(state.get("db_bot_2", state.get("db_bot_1", 20)) or state.get("db_bot_1", 20))
    if current_count < max(REO_COUNTS_0_12):
        u = _bottom_arrangement_to_shared_updates({
            "bot1_count": current_count + 1,
            "bot2_count": current_count_2,
            "db_bot_1": db1,
            "db_bot_2": db2,
        })
        if u and not _updates_match_state(state, u):
            return u
    if current_count_2 < max(REO_COUNTS_0_12):
        u = _bottom_arrangement_to_shared_updates({
            "bot1_count": current_count,
            "bot2_count": current_count_2 + 1,
            "db_bot_1": db1,
            "db_bot_2": db2,
        })
        if u and not _updates_match_state(state, u):
            return u
    return None


def _crack_ladder_consolidate_bottom_rows_updates(state: dict) -> dict | None:
    c1 = int(state.get("bot1_count", 0) or 0)
    c2 = int(state.get("bot2_count", 0) or 0)
    if c2 <= 0 or c1 <= 0:
        return None
    db1 = int(state.get("db_bot_1", 20) or 20)
    db2 = int(state.get("db_bot_2", db1) or db1)
    if db1 != db2:
        return None
    merged = {
        "bot1_count": c1 + c2,
        "bot2_count": 0,
        "db_bot_1": db1,
        "db_bot_2": db1,
    }
    if not _arrangement_fits_state(state, merged):
        return None
    u = _bottom_arrangement_to_shared_updates(merged)
    if not u or _updates_match_state(state, u):
        return None
    return u


def _try_crack_ladder_candidate(
    state: dict,
    *,
    label: str,
    updates: dict | None,
    base_util: float,
    ladder_name: str = "crack_ladder",
) -> dict | None:
    _bind_serviceability_ladder_candidate_dependencies(globals())
    return _try_crack_ladder_candidate_extracted(
        state,
        label=label,
        updates=updates,
        base_util=base_util,
        ladder_name=ladder_name,
    )


def _pick_crack_ladder_first_improvement(state: dict, *, base_util: float) -> dict | None:
    ladder_name = "crack_ladder"
    layout_sp = str(state.get("bot1_layout_mode", "Count") or "Count") == "Spacing"

    if layout_sp:
        u = _crack_ladder_tighten_spacing_updates(state)
        r = _try_crack_ladder_candidate(
            state,
            label="Tighten bottom bar spacing (one step)",
            updates=u,
            base_util=base_util,
            ladder_name=ladder_name,
        )
        if r:
            r["kind"] = "bottom_explicit"
            return r

    u = _crack_ladder_add_one_bottom_bar_updates(state)
    r = _try_crack_ladder_candidate(
        state,
        label="Add one bottom bar",
        updates=u,
        base_util=base_util,
        ladder_name=ladder_name,
    )
    if r:
        r["kind"] = "bottom_explicit"
        return r

    u = _crack_ladder_consolidate_bottom_rows_updates(state)
    r = _try_crack_ladder_candidate(
        state,
        label="Consolidate bottom bars into one row (same total bars)",
        updates=u,
        base_util=base_util,
        ladder_name=ladder_name,
    )
    if r:
        r["kind"] = "bottom_explicit"
        return r

    geo = _choose_geometry_trial_for_metric(
        state,
        metric="crack",
        baseline_util=base_util,
        ladder_name="crack_geometry_trials",
    )
    if not geo:
        return None
    return {
        "kind": "geometry",
        "label": geo["label"],
        "action_type": geo["action_type"],
        "payload": geo["payload"],
        "updates": geo["updates"],
        "util_after": geo["util_after"],
        "before_after": geo.get("before_after"),
    }


def _try_deflection_ladder_candidate(
    state: dict,
    *,
    label: str,
    updates: dict | None,
    base_util: float,
    ladder_name: str = "deflection_ladder",
) -> dict | None:
    _bind_serviceability_ladder_candidate_dependencies(globals())
    return _try_deflection_ladder_candidate_extracted(
        state,
        label=label,
        updates=updates,
        base_util=base_util,
        ladder_name=ladder_name,
    )


def _deflection_ladder_sustained_load_updates(state: dict) -> dict | None:
    for key in ("g_udl_kNm_per_m", "g_kNm", "g_line_kNm"):
        v = _float_from_state(state, key, 0.0)
        if v > 1e-9:
            return {key: float(v * 0.92)}
    return None


def _pick_deflection_ladder_first_improvement(state: dict, *, base_util: float) -> dict | None:
    _bind_serviceability_ladder_candidate_dependencies(globals())
    return _pick_deflection_ladder_first_improvement_extracted(state, base_util=base_util)


def _bending_near_limit_specific_title(goal: str, action_type: str) -> str | None:
    _ = goal
    if action_type == "increase_width":
        return "Increase width slightly for bending"
    if action_type == "increase_depth":
        return "Increase depth slightly for bending"
    if action_type == "apply_bottom_recommendation":
        return "Adjust bottom reinforcement for bending"
    return None


def _bending_item_from_geometry_trial(
    state: dict,
    *,
    title: str,
    status: str,
    util: float | None,
    bending_mode: str,
    secondary: str,
    levers: str,
    ladder_name: str = "bending_geometry_trials",
) -> dict | None:
    if util is None:
        return None
    g = _choose_geometry_trial_for_metric(
        state,
        metric="bending",
        baseline_util=float(util),
        bending_mode=bending_mode,
        ladder_name=ladder_name,
    )
    if not g:
        return None
    u_after = float(g.get("util_after", 0.0) or 0.0)
    reasoning = (
        f"Why: flexural demand is high. The suggested geometry step ({g['label']}) targets bending utilisation "
        f"from {float(util):.2f} toward {u_after:.2f}."
    )
    chosen_title = _geometry_trial_title_for_choice(title, g, state)
    g_upd = dict(g.get("updates") or {})
    clines = _guidance_change_lines_for_updates(state, g_upd)
    return _guidance_item(
        "bending",
        chosen_title,
        str(g.get("label") or "Apply geometry trial"),
        secondary,
        reasoning,
        levers,
        str(g.get("action_type") or "increase_depth"),
        dict(g.get("payload") or {}),
        status=status,
        util=util,
        guidance_before_after=str(g.get("before_after") or "") or None,
        guidance_change_lines=clines or None,
    )


def _shear_item_from_geometry_trials(
    state: dict,
    *,
    title: str,
    status: str,
    util: float | None,
    secondary: str,
    reasoning_fallback: str,
    levers: str,
    default_depth_delta: float,
    branch: str,
    _emit,
):
    _bind_shear_guidance_dependencies(globals())
    return _shear_item_from_geometry_trials_extracted(
        state,
        title=title,
        status=status,
        util=util,
        secondary=secondary,
        reasoning_fallback=reasoning_fallback,
        levers=levers,
        default_depth_delta=default_depth_delta,
        branch=branch,
        _emit=_emit,
    )


def _bending_guidance_item(state: dict, pack: dict) -> dict | None:
    _bind_bending_guidance_dependencies(globals())
    return _bending_guidance_item_extracted(state, pack)


def _shear_spacing_guidance_floor_mm() -> float:
    return float(min(REO_SPACINGS)) if REO_SPACINGS else 75.0


def _next_tighter_link_spacing_updates(state: dict) -> dict | None:
    current = float(_float_from_state(state, "s_lig", 0.0) or 0.0)
    if current <= 0.0 or not REO_SPACINGS:
        return None
    eligible = [float(x) for x in REO_SPACINGS if float(x) < current - 1e-9]
    if not eligible:
        return None
    new_s = max(eligible)
    updates = {"s_lig": new_s}
    if _updates_match_state(state, updates):
        return None
    return updates


def _fallback_shear_reinforcement_step_updates(state: dict) -> dict | None:
    legs = max(_int_from_state(state, "lig_legs", 2), 2)
    dia = max(_int_from_state(state, "lig_d", 10), 10)
    if legs < 8:
        nu = {"lig_legs": int(min(8, legs + 2))}
        if not _updates_match_state(state, nu):
            return nu
    for nd in REO_BAR_DIAS:
        if int(nd) > int(dia) and int(nd) <= 24:
            nu = {"lig_d": int(nd)}
            if not _updates_match_state(state, nu):
                return nu
    return None


def _shear_guidance_item_from_search_rec(*, title: str, rec: dict, util, status: str, state: dict) -> dict:
    candidate_type = str(rec.get("candidate_type") or "")
    if candidate_type == "combined":
        primary = "Combined geometry and reinforcement change required"
        secondary = f"Trial: {rec.get('label') or 'combined fix'}"
        reasoning = "Why: shear demand is severely above capacity, so a combined section and link upgrade is the fastest safe recovery path."
    elif candidate_type in {"depth increase", "width increase"}:
        primary = "Increase section width/depth to recover shear capacity"
        secondary = f"Trial: {rec.get('label') or 'geometry fix'}"
        reasoning = "Why: the current shear failure is too severe for a small link tweak alone, so geometry must compete with reinforcement changes."
    elif candidate_type == "no_shear_design_cleanup":
        primary = "Remove designed shear reinforcement (no ULS shear/torsion demand)"
        secondary = "Optional: nominal construction ties per your specification are outside this strength check."
        reasoning = "Why: resolved shear and torsion are negligible, so strength-designed links are not required here."
    elif candidate_type in {"more legs", "larger dia"}:
        primary = "Increase shear reinforcement significantly"
        secondary = f"Trial: {rec.get('label') or 'stronger links'}"
        reasoning = "Why: a severe shear failure needs a major reinforcement step, not just tighter spacing."
    else:
        primary = "Increase shear reinforcement significantly"
        secondary = f"Trial: {rec.get('label') or 'stronger links'}"
        reasoning = (
            "Why: a searched reinforcement or geometry upgrade is the next actionable step "
            f"(shear utilisation trial {float(util or 0.0):.2f} -> {float(rec.get('util', 0.0) or 0.0):.2f})."
        )
    updates = dict(rec.get("updates") or {})
    ba: str | None = None
    if updates and candidate_type != "no_shear_design_cleanup":
        try:
            after_state = dict(state)
            after_state.update(updates)
            ba = _describe_guidance_step(state, after_state, "apply_shear_recommendation", updates)
        except Exception:
            ba = None
    return _guidance_item(
        "shear",
        title,
        primary,
        secondary,
        reasoning,
        "Key levers: link spacing, no. of legs, link diameter, b, D",
        "apply_shear_recommendation",
        {"updates": updates},
        status=status,
        util=util,
        guidance_before_after=ba,
    )


def _shear_no_demand_cleanup_guidance_item_if_needed(state: dict) -> dict | None:
    design_context = _build_design_actions_context(state)
    overview = _collect_design_overview(state, context=design_context)
    actions = design_context.get("actions") or {}
    rec = _try_shear_no_demand_cleanup_recommendation(state, overview, actions)
    if not rec or not rec.get("updates") or _updates_match_state(state, rec["updates"]):
        return None
    return _guidance_item(
        "shear",
        "No shear or torsion design demand",
        "Remove unnecessary shear reinforcement (ULS)",
        "Optional: keep nominal construction ties if required by your specification (outside this shear design check).",
        "Why: resolved shear and torsion are negligible, so designed shear links are not required here.",
        "Key levers: link diameter, number of legs, spacing",
        "apply_shear_recommendation",
        {"updates": rec["updates"]},
        status="PASS",
        util=float(((overview.get("utils") or {}).get("shear", 0.0)) or 0.0),
    )


def _log_shear_top_guidance_recommendation(
    state: dict,
    *,
    branch: str,
    item: dict,
    proposed_updates: dict | None,
    expected_util_after: float | None,
    search_label: str | None,
) -> None:
    if not DEBUG_DESIGN_GUIDANCE_PROBE:
        return
    action_type = item.get("action_type")
    before_after = None
    if action_type:
        try:
            before_after = _guidance_before_after_text(dict(item), state)
        except Exception:
            before_after = None
    _agent_debug_log(
        "Design Guide top shear recommendation",
        {
            "branch": branch,
            "lig_legs": _int_from_state(state, "lig_legs", 0),
            "s_lig": _float_from_state(state, "s_lig", 0.0),
            "action_type": action_type,
            "proposed_updates": proposed_updates or (item.get("action_payload") or {}).get("updates"),
            "proposed_label": search_label or item.get("secondary_action"),
            "before_after_text": before_after,
            "expected_util_after": expected_util_after,
            "title_main": item.get("title_main"),
        },
        location="inputs_page.py:_shear_guidance_item",
        hypothesis_id="H_SHEAR_TOP_GUIDE",
    )


def _shear_guidance_item(state: dict, pack: dict) -> dict | None:
    _bind_shear_guidance_dependencies(globals())
    return _shear_guidance_item_extracted(state, pack)


def _crack_guidance_item(state: dict, pack: dict) -> dict | None:
    _bind_crack_guidance_dependencies(globals())
    return _crack_guidance_item_extracted(state, pack)


def _deflection_guidance_item(state: dict, pack: dict) -> dict | None:
    rows = pack.get("rows") or []
    util = _parse_util_value(pack.get("summary_util_total"))
    status, _ = _overall_status_from_rows(rows)
    bucket = _guidance_bucket(status, util)
    if bucket not in ("fail", "warn"):
        return None
    base = _evaluate_deflection_with_state(state)
    if not base or base.get("util") is None:
        return None
    base_u = float(base["util"])
    picked = _pick_deflection_ladder_first_improvement(state, base_util=base_u)
    if not picked:
        return None
    u_after = float(picked.get("util_after", 0.0) or 0.0)
    kind = str(picked.get("kind") or "")
    span_note = " Advisory only: a shorter effective span L_eff also reduces deflection (not applied automatically)."
    is_fail = bucket == "fail"
    title = "Deflection is high" if is_fail else "Deflection is close to the limit"
    levers = "Key levers: D, b, sustained loads, span (advisory)"
    secondary = "Alternative: review deflection inputs on the Deflection page." + span_note
    if kind == "sustained_load":
        reasoning = (
            f"Why: deflection ladder — depth and width trials first; then one small sustained-load step ({util:.2f} → {u_after:.2f})."
            if util is not None
            else f"Why: sustained-load adjustment ({u_after:.2f})."
        )
        return _guidance_item(
            "deflection",
            title,
            str(picked.get("label") or "Reduce sustained load slightly"),
            secondary,
            reasoning,
            levers,
            "deflection_reduce_sustained_load",
            {"updates": dict(picked.get("updates") or {})},
            status=status,
            util=util,
            guidance_before_after=str(picked.get("before_after") or "") or None,
        )
    reasoning = (
        f"Why: deflection ladder — depth, then width if it helps stiffness, before load tweaks ({util:.2f} → {u_after:.2f})."
        if util is not None
        else f"Why: geometry step ({u_after:.2f})."
    )
    return _guidance_item(
        "deflection",
        title,
        str(picked.get("label") or "Increase depth"),
        secondary,
        reasoning + span_note,
        levers,
        str(picked.get("action_type") or "increase_depth"),
        dict(picked.get("payload") or {}),
        status=status,
        util=util,
        guidance_before_after=str(picked.get("before_after") or "") or None,
    )


def _one_click_candidate_payload_signature(updates: dict) -> tuple:
    sig: list[tuple[str, object]] = []
    for k in sorted((updates or {}).keys()):
        v = updates.get(k)
        if isinstance(v, float):
            sig.append((k, round(float(v), 6)))
        else:
            sig.append((k, v))
    return tuple(sig)


def _candidate_preview_statuses_have_explicit_fail(preview_statuses: dict | None) -> bool:
    """True when candidate preview overview statuses map contains any explicit FAIL value."""
    if not isinstance(preview_statuses, dict):
        return False
    for v in preview_statuses.values():
        if v == BEAM_STATUS_FAIL:
            return True
        if str(v or "").strip().upper() == "FAIL":
            return True
    return False


def _candidate_is_valid_primary_one_click(candidate: dict | None, overview: dict) -> tuple[bool, dict]:
    _bind_primary_one_click_validation_dependencies(globals())
    return _candidate_is_valid_primary_one_click_extracted(candidate, overview)


def _guidance_item_from_resolved_candidate(
    candidate: dict,
    *,
    state: dict,
    overview: dict,
    title: str | None = None,
    reasoning: str | None = None,
    status: str = "FAIL",
    primary_action: str = "Apply recommendation",
) -> dict:
    _bind_resolved_candidate_guidance_item_dependencies(globals())
    return _guidance_item_from_resolved_candidate_extracted(
        candidate,
        state=state,
        overview=overview,
        title=title,
        reasoning=reasoning,
        status=status,
        primary_action=primary_action,
    )


def _get_one_click_band_reaching_candidate(
    guidance_state: dict,
    overview: dict,
    *,
    mode_config: dict,
    primary_hint: dict | None = None,
    debug_extra: dict | None = None,
) -> dict | None:
    _bind_one_click_band_candidate_dependencies(globals())
    return _get_one_click_band_reaching_candidate_extracted(
        guidance_state,
        overview,
        mode_config=mode_config,
        primary_hint=primary_hint,
        debug_extra=debug_extra,
    )


def _enumerate_bottom_reo_design_trials(state: dict, *, mode_config: dict | None = None) -> list[dict]:
    _bind_bottom_reo_design_trial_dependencies(globals())
    return _enumerate_bottom_reo_design_trials_extracted(state, mode_config=mode_config)


def _solve_one_click_candidate(
    state: dict,
    *,
    goal: str | None = None,
    expanded: bool = False,
    debug_enabled: bool = False,
) -> dict | None:
    _bind_one_click_candidate_solver_dependencies(globals())
    return _solve_one_click_candidate_extracted(
        state,
        goal=goal,
        expanded=expanded,
        debug_enabled=debug_enabled,
    )


def _apply_guidance_ui_state(
    current_state: dict,
    *,
    preserve_apply_banner: bool = True,
) -> dict:
    """
    Layer 1 UI/session side effects for guidance panel orchestration.
    """
    design_context = _build_design_actions_context(current_state)
    guidance_state = dict(design_context.get("state") or _guidance_state_snapshot(current_state))
    cache_fp = _candidate_cache_key(guidance_state)
    if _ENABLE_GLOBAL_EVAL_CACHE and st.session_state.get("_global_eval_cache_fp") != cache_fp:
        st.session_state["_global_eval_cache"] = {}
        st.session_state["_global_eval_cache_fp"] = cache_fp
    _sync_design_guide_geometry_reference(guidance_state)
    _maybe_reset_design_guide_step_history(guidance_state)
    _clear_design_guide_transient_ui_state(
        clear_history=False,
        preserve_apply_banner=preserve_apply_banner,
    )
    return {
        "guidance_state": guidance_state,
        "guidance_cache_fp": cache_fp,
    }
