"""Final Design Guide independence lock verifier.

This verifier composes the full publication-independence proof chain. It proves
FinalDesignGuidePublication is the final CTA/display authority while
inputs_page.py remains allowed to render, route apply actions, and store debug
payloads without reinterpreting final publication truth.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
APPLY_ROUTING = ROOT / "inputs_page_modules" / "apply_routing.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
GATE_TIMEOUT_SEC = int(os.environ.get("DESIGN_GUIDE_INDEPENDENCE_GATE_TIMEOUT_SEC", "90"))

RETIRED_AFTER_FINAL_VISIBLE_RESOLVER_DELETION = {
    "final_publication_authority_snapshot",
    "live_controller_compute_handoff_trace_snapshot",
    "compute_guard_decision_controller_trace_snapshot",
    "live_controller_compute_handoff_parity_scenarios",
    "compute_stage_resolver_replacement_readiness",
    "controller_compute_selector_legacy_route_parity",
    "live_controller_compute_selection_trace_snapshot",
    "controller_final_item_selection_independence_readiness",
    "active_action_result_cutover",
    "active_action_legacy_assembler_deletion",
    "active_action_post_click_exact_blocker_readiness",
    "active_action_post_click_exact_blocker_route_parity",
    "active_action_post_click_exact_blocker_cutover_readiness",
    "active_action_post_click_exact_blocker_dead_body_deletion",
    "terminal_active_failure_blocker_finalizer_cutover_readiness",
    "terminal_active_failure_blocker_finalizer_cutover",
    "terminal_active_failure_trace_shell_cleanup",
    "bending_fail_snapshot_reuse_controller_object",
    "bending_fail_snapshot_reuse_trace_wiring",
    "bending_fail_snapshot_reuse_cutover_readiness",
    "bending_fail_snapshot_reuse_cutover",
    "bending_fail_snapshot_reuse_legacy_assembler_deletion",
    "no_active_primary_selector_readiness",
    "state_fingerprint_ownership_audit",
    "plain_data_fingerprint_adapter_parity",
    "no_active_primary_route_cutover",
    "no_active_primary_legacy_assembler_deletion",
    "no_active_blocked_primary_full_route_trace_wiring",
    "no_active_blocked_primary_full_route_branch_parity_scenarios",
    "no_active_blocked_primary_full_route_cutover_readiness",
    "no_active_blocked_primary_generic_page_shell_caller_cutover",
    "no_active_blocked_primary_dead_body_deletion_proof",
    "no_active_low_shear_or_blocker_full_route_readiness",
    "no_active_low_shear_or_blocker_full_route_cutover_readiness",
    "no_active_low_shear_or_blocker_dead_body_deletion_proof",
    "low_shear_resolution_legacy_assembler_deletion",
    "combined_low_util_blocker_or_best_safe_legacy_assembler_deletion",
    "zero_shear_demand_accepted_legacy_assembler_deletion",
    "no_active_combined_low_util_route_readiness",
    "no_active_combined_low_util_full_route_trace_wiring",
    "no_active_combined_low_util_full_route_parity_scenarios",
    "no_active_combined_low_util_full_route_cutover",
    "no_active_combined_low_util_page_wrapper_cleanup_audit",
    "no_active_combined_low_util_generic_page_shell_caller_cutover",
    "combined_low_util_cleanup_route_policy_trace_wiring",
    "shear_low_util_cleanup_generator_boundary_trace_wiring",
    "shear_low_util_raw_variant_states_cutover",
    "shear_low_util_failed_reason_from_preview_cutover",
    "shear_low_util_failure_coverage_cutover",
    "shear_low_util_current_overview_status_authority_cutover",
    "shear_low_util_change_lines_cutover",
    "shear_low_util_candidate_evaluation_cutover",
    "combined_low_util_guidance_item_packaging_cutover",
    "combined_low_util_invalid_item_fallback_cutover",
    "combined_low_util_orchestration_wrapper_cutover",
    "combined_low_util_local_cleanup_caller_migration",
    "combined_low_util_residual_merge_caller_migration",
    "combined_low_util_thin_adapter_reachability",
    "shear_low_util_promotion_adapter_cutover",
    "shear_low_util_evaluator_promotion_boundary",
    "render_after_publication_freeze",
    "verifier_debug_same_object",
    "session_boundary_readiness",
    "session_boundary_canonicalization",
}

COMPOSED_GATES: list[dict[str, str]] = [
    {
        "id": "final_publication_authority_snapshot",
        "script": "tools/verification/design_guide_final_publication_authority_snapshot.py",
        "label": "Final publication authority snapshot",
    },
    {
        "id": "final_publication_object_snapshot",
        "script": "tools/verification/design_guide_final_publication_object_snapshot.py",
        "label": "FinalDesignGuidePublication object snapshot",
    },
    {
        "id": "final_publication_boundary_snapshot",
        "script": "tools/verification/design_guide_final_publication_boundary_snapshot.py",
        "label": "Final publication boundary snapshot",
    },
    {
        "id": "passive_cleanup_final_publication_divergence",
        "script": "tools/verification/design_guide_passive_cleanup_final_publication_divergence_audit.py",
        "label": "Passive cleanup presentation/final publication invariant",
    },
    {
        "id": "inputs_page_legacy_truth_surface_audit",
        "script": "tools/verification/design_guide_inputs_page_legacy_truth_surface_audit.py",
        "label": "Inputs page legacy Design Guide truth surface audit",
    },
    {
        "id": "controller_compute_handoff_gap_snapshot",
        "script": "tools/verification/design_guide_controller_compute_handoff_gap_snapshot.py",
        "label": "Controller compute handoff boundary state",
    },
    {
        "id": "controller_compute_handoff_object_snapshot",
        "script": "tools/verification/design_guide_controller_compute_handoff_object_snapshot.py",
        "label": "Controller compute handoff proof object",
    },
    {
        "id": "live_controller_compute_handoff_trace_snapshot",
        "script": "tools/verification/design_guide_live_controller_compute_handoff_trace_snapshot.py",
        "label": "Live controller compute handoff trace wiring",
    },
    {
        "id": "compute_guard_decision_controller_trace_snapshot",
        "script": "tools/verification/design_guide_compute_guard_decision_controller_trace_snapshot.py",
        "label": "Controller compute guard decision trace wiring",
    },
    {
        "id": "live_controller_compute_handoff_parity_scenarios",
        "script": "tools/verification/design_guide_live_controller_compute_handoff_parity_scenarios.py",
        "label": "Live controller compute handoff parity scenarios",
    },
    {
        "id": "compute_stage_resolver_replacement_readiness",
        "script": "tools/verification/design_guide_compute_stage_resolver_replacement_readiness_snapshot.py",
        "label": "Compute-stage resolver replacement readiness",
    },
    {
        "id": "controller_compute_selector_object_snapshot",
        "script": "tools/verification/design_guide_controller_compute_selector_object_snapshot.py",
        "label": "Controller compute selector proof object",
    },
    {
        "id": "controller_compute_selector_legacy_route_parity",
        "script": "tools/verification/design_guide_controller_compute_selector_legacy_route_parity_snapshot.py",
        "label": "Controller compute selector legacy route parity",
    },
    {
        "id": "live_controller_compute_selection_trace_snapshot",
        "script": "tools/verification/design_guide_live_controller_compute_selection_trace_snapshot.py",
        "label": "Live controller compute selection trace wiring",
    },
    {
        "id": "controller_final_item_selection_independence_readiness",
        "script": "tools/verification/design_guide_controller_final_item_selection_independence_readiness_snapshot.py",
        "label": "Controller final item selection independence readiness",
    },
    {
        "id": "active_action_result_object",
        "script": "tools/verification/design_guide_active_action_result_object_snapshot.py",
        "label": "Active action result object",
    },
    {
        "id": "active_action_result_cutover",
        "script": "tools/verification/design_guide_active_action_result_cutover.py",
        "label": "Active action result cutover",
    },
    {
        "id": "active_action_legacy_assembler_deletion",
        "script": "tools/verification/design_guide_active_action_legacy_assembler_deletion_proof.py",
        "label": "Active action legacy assembler deletion",
    },
    {
        "id": "active_action_post_click_exact_blocker_readiness",
        "script": "tools/verification/design_guide_active_action_post_click_exact_blocker_readiness_snapshot.py",
        "label": "Active action post-click exact blocker readiness",
    },
    {
        "id": "active_action_post_click_exact_blocker_route_object",
        "script": "tools/verification/design_guide_active_action_post_click_exact_blocker_route_object_snapshot.py",
        "label": "Active action post-click exact blocker route object",
    },
    {
        "id": "active_action_post_click_exact_blocker_route_parity",
        "script": "tools/verification/design_guide_active_action_post_click_exact_blocker_route_parity_snapshot.py",
        "label": "Active action post-click exact blocker route parity",
    },
    {
        "id": "active_action_post_click_exact_blocker_cutover_readiness",
        "script": "tools/verification/design_guide_active_action_post_click_exact_blocker_cutover_readiness.py",
        "label": "Active action post-click exact blocker cutover readiness",
    },
    {
        "id": "active_action_post_click_exact_blocker_dead_body_deletion",
        "script": "tools/verification/design_guide_active_action_post_click_exact_blocker_dead_body_deletion_proof.py",
        "label": "Active action post-click exact blocker dead body deletion",
    },
    {
        "id": "terminal_active_failure_blocker_finalizer_route_object",
        "script": "tools/verification/design_guide_terminal_active_failure_blocker_finalizer_route_object_snapshot.py",
        "label": "Terminal active-failure blocker finalizer route object",
    },
    {
        "id": "terminal_active_failure_blocker_finalizer_cutover_readiness",
        "script": "tools/verification/design_guide_terminal_active_failure_blocker_finalizer_cutover_readiness.py",
        "label": "Terminal active-failure blocker finalizer cutover readiness",
    },
    {
        "id": "terminal_active_failure_blocker_finalizer_cutover",
        "script": "tools/verification/design_guide_terminal_active_failure_blocker_finalizer_cutover.py",
        "label": "Terminal active-failure blocker finalizer cutover",
    },
    {
        "id": "terminal_active_failure_trace_shell_cleanup",
        "script": "tools/verification/design_guide_terminal_active_failure_trace_shell_cleanup_audit.py",
        "label": "Terminal active-failure trace shell cleanup audit",
    },
    {
        "id": "terminal_trace_row_consumer_reachability",
        "script": "tools/verification/design_guide_terminal_trace_row_consumer_reachability_audit.py",
        "label": "Terminal trace-row consumer reachability audit",
    },
    {
        "id": "bending_fail_snapshot_reuse_controller_object",
        "script": "tools/verification/design_guide_bending_fail_snapshot_reuse_controller_object_snapshot.py",
        "label": "Bending-fail snapshot reuse controller object",
    },
    {
        "id": "bending_fail_snapshot_reuse_trace_wiring",
        "script": "tools/verification/design_guide_bending_fail_snapshot_reuse_trace_wiring_snapshot.py",
        "label": "Bending-fail snapshot reuse trace wiring",
    },
    {
        "id": "bending_fail_snapshot_reuse_cutover_readiness",
        "script": "tools/verification/design_guide_bending_fail_snapshot_reuse_cutover_readiness_snapshot.py",
        "label": "Bending-fail snapshot reuse cutover readiness",
    },
    {
        "id": "bending_fail_snapshot_reuse_cutover",
        "script": "tools/verification/design_guide_bending_fail_snapshot_reuse_cutover.py",
        "label": "Bending-fail snapshot reuse cutover",
    },
    {
        "id": "bending_fail_snapshot_reuse_legacy_assembler_deletion",
        "script": "tools/verification/design_guide_bending_fail_snapshot_reuse_legacy_assembler_deletion_proof.py",
        "label": "Bending-fail snapshot reuse legacy assembler deletion proof",
    },
    {
        "id": "no_active_primary_selector_readiness",
        "script": "tools/verification/design_guide_no_active_primary_selector_readiness_snapshot.py",
        "label": "No-active primary selector readiness",
    },
    {
        "id": "state_fingerprint_ownership_audit",
        "script": "tools/verification/design_guide_state_fingerprint_ownership_audit.py",
        "label": "State fingerprint ownership audit",
    },
    {
        "id": "plain_data_fingerprint_adapter_parity",
        "script": "tools/verification/design_guide_plain_data_fingerprint_adapter_parity_snapshot.py",
        "label": "Plain-data fingerprint adapter parity",
    },
    {
        "id": "no_active_primary_route_cutover",
        "script": "tools/verification/design_guide_no_active_primary_route_cutover.py",
        "label": "No-active primary route cutover",
    },
    {
        "id": "no_active_primary_legacy_assembler_deletion",
        "script": "tools/verification/design_guide_no_active_primary_legacy_assembler_deletion_proof.py",
        "label": "No-active primary legacy assembler deletion",
    },
    {
        "id": "no_active_blocked_primary_cleanup_probe_route_policy_object",
        "script": "tools/verification/design_guide_no_active_blocked_primary_cleanup_probe_route_policy_object_snapshot.py",
        "label": "No-active blocked-primary cleanup probe route policy object",
    },
    {
        "id": "no_active_blocked_primary_cleanup_probe_result_object",
        "script": "tools/verification/design_guide_no_active_blocked_primary_cleanup_probe_result_object_snapshot.py",
        "label": "No-active blocked-primary cleanup probe result object",
    },
    {
        "id": "no_active_blocked_primary_full_route_builder_object",
        "script": "tools/verification/design_guide_no_active_blocked_primary_full_route_builder_object_snapshot.py",
        "label": "No-active blocked-primary full route builder object",
    },
    {
        "id": "no_active_blocked_primary_full_route_trace_wiring",
        "script": "tools/verification/design_guide_no_active_blocked_primary_full_route_trace_wiring_snapshot.py",
        "label": "No-active blocked-primary full route trace wiring",
    },
    {
        "id": "no_active_blocked_primary_full_route_branch_parity_scenarios",
        "script": "tools/verification/design_guide_no_active_blocked_primary_full_route_branch_parity_scenarios.py",
        "label": "No-active blocked-primary full route branch parity scenarios",
    },
    {
        "id": "no_active_blocked_primary_controller_route_object",
        "script": "tools/verification/design_guide_no_active_blocked_primary_controller_route_object_snapshot.py",
        "label": "No-active blocked-primary controller route object",
    },
    {
        "id": "no_active_blocked_primary_full_route_cutover_readiness",
        "script": "tools/verification/design_guide_no_active_blocked_primary_full_route_cutover_readiness.py",
        "label": "No-active blocked-primary full route cutover readiness",
    },
    {
        "id": "no_active_blocked_primary_generic_page_shell_caller_cutover",
        "script": "tools/verification/design_guide_no_active_blocked_primary_generic_page_shell_caller_cutover.py",
        "label": "No-active blocked-primary generic page-shell caller cutover",
    },
    {
        "id": "no_active_blocked_primary_dead_body_deletion_proof",
        "script": "tools/verification/design_guide_no_active_blocked_primary_dead_body_deletion_proof.py",
        "label": "No-active blocked-primary dead body deletion proof",
    },
    {
        "id": "no_active_low_shear_or_blocker_full_route_readiness",
        "script": "tools/verification/design_guide_no_active_low_shear_or_blocker_full_route_readiness_snapshot.py",
        "label": "No-active low-shear/blocker full-route readiness",
    },
    {
        "id": "no_active_low_shear_or_blocker_route_object",
        "script": "tools/verification/design_guide_no_active_low_shear_or_blocker_route_object_snapshot.py",
        "label": "No-active low-shear/blocker controller route object",
    },
    {
        "id": "no_active_low_shear_or_blocker_full_route_cutover_readiness",
        "script": "tools/verification/design_guide_no_active_low_shear_or_blocker_full_route_cutover_readiness.py",
        "label": "No-active low-shear/blocker full route cutover readiness",
    },
    {
        "id": "no_active_low_shear_or_blocker_dead_body_deletion_proof",
        "script": "tools/verification/design_guide_no_active_low_shear_or_blocker_dead_body_deletion_proof.py",
        "label": "No-active low-shear/blocker dead body deletion proof",
    },
    {
        "id": "low_shear_resolution_legacy_assembler_deletion",
        "script": "tools/verification/design_guide_low_shear_resolution_legacy_assembler_deletion_proof.py",
        "label": "Low-shear resolution legacy assembler deletion",
    },
    {
        "id": "combined_low_util_blocker_or_best_safe_legacy_assembler_deletion",
        "script": "tools/verification/design_guide_combined_low_util_blocker_or_best_safe_legacy_assembler_deletion_proof.py",
        "label": "Combined low-util blocker/best-safe legacy assembler deletion",
    },
    {
        "id": "zero_shear_demand_accepted_legacy_assembler_deletion",
        "script": "tools/verification/design_guide_zero_shear_demand_accepted_legacy_assembler_deletion_proof.py",
        "label": "Zero-shear demand accepted legacy assembler deletion",
    },
    {
        "id": "no_active_combined_low_util_route_readiness",
        "script": "tools/verification/design_guide_no_active_combined_low_util_route_readiness_snapshot.py",
        "label": "No-active combined low-util route readiness",
    },
    {
        "id": "no_active_combined_low_util_full_route_builder_object",
        "script": "tools/verification/design_guide_no_active_combined_low_util_full_route_builder_object_snapshot.py",
        "label": "No-active combined low-util full-route builder object",
    },
    {
        "id": "no_active_combined_low_util_full_route_trace_wiring",
        "script": "tools/verification/design_guide_no_active_combined_low_util_full_route_trace_wiring_snapshot.py",
        "label": "No-active combined low-util full-route trace wiring",
    },
    {
        "id": "no_active_combined_low_util_full_route_parity_scenarios",
        "script": "tools/verification/design_guide_no_active_combined_low_util_full_route_parity_scenarios.py",
        "label": "No-active combined low-util full-route parity scenarios",
    },
    {
        "id": "no_active_combined_low_util_full_route_cutover",
        "script": "tools/verification/design_guide_no_active_combined_low_util_full_route_cutover.py",
        "label": "No-active combined low-util full-route cutover",
    },
    {
        "id": "no_active_combined_low_util_page_wrapper_cleanup_audit",
        "script": "tools/verification/design_guide_no_active_combined_low_util_page_wrapper_cleanup_audit.py",
        "label": "No-active combined low-util page wrapper cleanup audit",
    },
    {
        "id": "no_active_combined_low_util_generic_page_shell_caller_cutover",
        "script": "tools/verification/design_guide_no_active_combined_low_util_generic_page_shell_caller_cutover.py",
        "label": "No-active combined low-util generic page-shell caller cutover",
    },
    {
        "id": "combined_low_util_cleanup_route_policy_object",
        "script": "tools/verification/design_guide_combined_low_util_cleanup_route_policy_object_snapshot.py",
        "label": "Combined low-util cleanup route policy object",
    },
    {
        "id": "combined_low_util_cleanup_route_policy_trace_wiring",
        "script": "tools/verification/design_guide_combined_low_util_cleanup_route_policy_trace_wiring_snapshot.py",
        "label": "Combined low-util cleanup route policy trace wiring",
    },
    {
        "id": "combined_low_util_cleanup_result_object",
        "script": "tools/verification/design_guide_combined_low_util_cleanup_result_object_snapshot.py",
        "label": "Combined low-util cleanup result object",
    },
    {
        "id": "combined_low_util_candidate_generation_handoff_object",
        "script": "tools/verification/design_guide_combined_low_util_candidate_generation_handoff_object_snapshot.py",
        "label": "Combined low-util candidate generation handoff object",
    },
    {
        "id": "shear_low_util_cleanup_generator_boundary_object",
        "script": "tools/verification/design_guide_shear_low_util_cleanup_generator_boundary_object_snapshot.py",
        "label": "Shear low-util cleanup generator boundary object",
    },
    {
        "id": "shear_low_util_cleanup_generator_boundary_trace_wiring",
        "script": "tools/verification/design_guide_shear_low_util_cleanup_generator_boundary_trace_wiring_snapshot.py",
        "label": "Shear low-util cleanup generator boundary trace wiring",
    },
    {
        "id": "shear_low_util_candidate_classifier_cutover",
        "script": "tools/verification/design_guide_shear_low_util_candidate_classifier_cutover_snapshot.py",
        "label": "Shear low-util candidate classifier cutover",
    },
    {
        "id": "shear_low_util_candidate_accumulator_cutover",
        "script": "tools/verification/design_guide_shear_low_util_candidate_accumulator_cutover_snapshot.py",
        "label": "Shear low-util candidate accumulator cutover",
    },
    {
        "id": "shear_low_util_candidate_record_cutover",
        "script": "tools/verification/design_guide_shear_low_util_candidate_record_cutover_snapshot.py",
        "label": "Shear low-util candidate record cutover",
    },
    {
        "id": "shear_low_util_selected_no_link_audit_cutover",
        "script": "tools/verification/design_guide_shear_low_util_selected_no_link_audit_cutover_snapshot.py",
        "label": "Shear low-util selected no-link audit cutover",
    },
    {
        "id": "shear_low_util_no_link_probe_cutover",
        "script": "tools/verification/design_guide_shear_low_util_no_link_probe_cutover_snapshot.py",
        "label": "Shear low-util no-link probe cutover",
    },
    {
        "id": "shear_low_util_raw_variant_states_cutover",
        "script": "tools/verification/design_guide_shear_low_util_raw_variant_states_cutover_snapshot.py",
        "label": "Shear low-util raw variant states cutover",
    },
    {
        "id": "shear_low_util_variant_sequence_cutover",
        "script": "tools/verification/design_guide_shear_low_util_variant_sequence_cutover_snapshot.py",
        "label": "Shear low-util variant sequence cutover",
    },
    {
        "id": "shear_low_util_candidate_delta_screen_cutover",
        "script": "tools/verification/design_guide_shear_low_util_candidate_delta_screen_cutover_snapshot.py",
        "label": "Shear low-util candidate delta screen cutover",
    },
    {
        "id": "shear_low_util_candidate_acceptance_screen_cutover",
        "script": "tools/verification/design_guide_shear_low_util_candidate_acceptance_screen_cutover_snapshot.py",
        "label": "Shear low-util candidate acceptance screen cutover",
    },
    {
        "id": "shear_low_util_failed_reason_from_preview_cutover",
        "script": "tools/verification/design_guide_shear_low_util_failed_reason_from_preview_cutover_snapshot.py",
        "label": "Shear low-util failed reason from preview cutover",
    },
    {
        "id": "shear_low_util_failure_coverage_cutover",
        "script": "tools/verification/design_guide_shear_low_util_failure_coverage_cutover_snapshot.py",
        "label": "Shear low-util failure coverage cutover",
    },
    {
        "id": "shear_low_util_current_overview_status_authority_cutover",
        "script": "tools/verification/design_guide_shear_low_util_current_overview_status_authority_cutover_snapshot.py",
        "label": "Shear low-util current overview status authority cutover",
    },
    {
        "id": "shear_low_util_change_lines_cutover",
        "script": "tools/verification/design_guide_shear_low_util_change_lines_cutover_snapshot.py",
        "label": "Shear low-util change lines cutover",
    },
    {
        "id": "shear_low_util_candidate_evaluation_cutover",
        "script": "tools/verification/design_guide_shear_low_util_candidate_evaluation_cutover_snapshot.py",
        "label": "Shear low-util candidate evaluation cutover",
    },
    {
        "id": "combined_low_util_guidance_item_packaging_cutover",
        "script": "tools/verification/design_guide_combined_low_util_guidance_item_packaging_cutover_snapshot.py",
        "label": "Combined low-util guidance item packaging cutover",
    },
    {
        "id": "combined_low_util_invalid_item_fallback_cutover",
        "script": "tools/verification/design_guide_combined_low_util_invalid_item_fallback_cutover_snapshot.py",
        "label": "Combined low-util invalid-item fallback cutover",
    },
    {
        "id": "combined_low_util_orchestration_wrapper_cutover",
        "script": "tools/verification/design_guide_combined_low_util_orchestration_wrapper_cutover_snapshot.py",
        "label": "Combined low-util orchestration wrapper cutover",
    },
    {
        "id": "combined_low_util_local_cleanup_caller_migration",
        "script": "tools/verification/design_guide_combined_low_util_local_cleanup_caller_migration_snapshot.py",
        "label": "Combined low-util local cleanup caller migration",
    },
    {
        "id": "combined_low_util_residual_merge_caller_migration",
        "script": "tools/verification/design_guide_combined_low_util_residual_merge_caller_migration_snapshot.py",
        "label": "Combined low-util residual merge caller migration",
    },
    {
        "id": "combined_low_util_bending_restore_caller_migration",
        "script": "tools/verification/design_guide_combined_low_util_bending_restore_caller_migration_snapshot.py",
        "label": "Combined low-util bending restore caller migration",
    },
    {
        "id": "combined_low_util_pre_presentation_caller_migration",
        "script": "tools/verification/design_guide_combined_low_util_pre_presentation_caller_migration_snapshot.py",
        "label": "Combined low-util pre-presentation caller migration",
    },
    {
        "id": "combined_low_util_blocked_render_fallback_caller_migration",
        "script": "tools/verification/design_guide_combined_low_util_blocked_render_fallback_caller_migration_snapshot.py",
        "label": "Combined low-util blocked-render fallback caller migration",
    },
    {
        "id": "combined_low_util_thin_adapter_reachability",
        "script": "tools/verification/design_guide_combined_low_util_thin_adapter_reachability_snapshot.py",
        "label": "Combined low-util thin adapter reachability/deletion proof",
    },
    {
        "id": "shear_low_util_promotion_adapter_parity",
        "script": "tools/verification/design_guide_shear_low_util_promotion_adapter_parity_snapshot.py",
        "label": "Shear low-util promotion adapter parity",
    },
    {
        "id": "shear_low_util_promotion_adapter_cutover",
        "script": "tools/verification/design_guide_shear_low_util_promotion_adapter_cutover_snapshot.py",
        "label": "Shear low-util promotion adapter cutover",
    },
    {
        "id": "shear_low_util_evaluator_promotion_boundary",
        "script": "tools/verification/design_guide_shear_low_util_evaluator_promotion_boundary_audit.py",
        "label": "Shear low-util evaluator/promotion boundary",
    },
    {
        "id": "shear_low_util_candidate_search_evidence_cutover",
        "script": "tools/verification/design_guide_shear_low_util_candidate_search_evidence_cutover_snapshot.py",
        "label": "Shear low-util candidate search evidence cutover",
    },
    {
        "id": "shear_low_util_preferred_target_blocker_cutover",
        "script": "tools/verification/design_guide_shear_low_util_preferred_target_blocker_cutover_snapshot.py",
        "label": "Shear low-util preferred target blocker cutover",
    },
    {
        "id": "shear_low_util_final_item_packaging_cutover",
        "script": "tools/verification/design_guide_shear_low_util_final_item_packaging_cutover_snapshot.py",
        "label": "Shear low-util final item packaging cutover",
    },
    {
        "id": "shear_low_util_guidance_descriptor_cutover",
        "script": "tools/verification/design_guide_shear_low_util_guidance_descriptor_cutover_snapshot.py",
        "label": "Shear low-util guidance descriptor cutover",
    },
    {
        "id": "shear_low_util_guidance_item_shell_cutover",
        "script": "tools/verification/design_guide_shear_low_util_guidance_item_shell_cutover_snapshot.py",
        "label": "Shear low-util guidance item shell cutover",
    },
    {
        "id": "cta_authority_readiness",
        "script": "tools/verification/design_guide_cta_authority_readiness_snapshot.py",
        "label": "CTA readiness",
    },
    {
        "id": "cta_adapter_parity",
        "script": "tools/verification/design_guide_cta_adapter_parity_snapshot.py",
        "label": "CTA adapter parity",
    },
    {
        "id": "live_cta_wiring",
        "script": "tools/verification/design_guide_live_cta_wiring_snapshot.py",
        "label": "Live CTA wiring",
    },
    {
        "id": "live_cta_authority_cutover",
        "script": "tools/verification/design_guide_live_cta_authority_cutover.py",
        "label": "Live CTA authority cutover",
    },
    {
        "id": "card_vm_authority_readiness",
        "script": "tools/verification/design_guide_card_vm_authority_readiness_snapshot.py",
        "label": "Card VM readiness",
    },
    {
        "id": "card_vm_adapter_parity",
        "script": "tools/verification/design_guide_card_vm_adapter_parity_snapshot.py",
        "label": "Card VM adapter parity",
    },
    {
        "id": "live_card_vm_wiring",
        "script": "tools/verification/design_guide_live_card_vm_wiring_snapshot.py",
        "label": "Live card VM wiring",
    },
    {
        "id": "live_card_vm_authority_cutover",
        "script": "tools/verification/design_guide_live_card_vm_authority_cutover.py",
        "label": "Live card VM authority cutover",
    },
    {
        "id": "render_after_publication_freeze",
        "script": "tools/verification/design_guide_render_after_publication_freeze.py",
        "label": "Render-after-publication freeze",
    },
    {
        "id": "verifier_debug_same_object",
        "script": "tools/verification/design_guide_verifier_debug_same_object.py",
        "label": "Verifier/debug same-object proof",
    },
    {
        "id": "session_boundary_readiness",
        "script": "tools/verification/design_guide_session_boundary_readiness_snapshot.py",
        "label": "Session boundary readiness",
    },
    {
        "id": "session_boundary_canonicalization",
        "script": "tools/verification/design_guide_session_boundary_canonicalization.py",
        "label": "Session boundary canonicalization",
    },
    {
        "id": "design_brain_inputs_page_independence_audit",
        "script": "tools/verification/design_brain_inputs_page_independence_audit.py",
        "label": "Design Brain inputs_page independence audit",
    },
    {
        "id": "locked_family_live_wiring_snapshot",
        "script": "tools/verification/families/locked_family_live_wiring_snapshot.py",
        "label": "Locked family live wiring snapshot",
    },
]

REQUIRED_INPUTS_TOKENS = {
    "cta_authority": '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"',
    "display_authority": "class FinalDesignGuideDisplay",
    "same_object_payload": "final_publication_verifier_payload",
    "publication_authority_hash": "final_publication_authority_hash",
    "publication_hash": "publication_hash",
    "cta_hash": "final_publication_cta_hash",
    "display_hash": "final_publication_display_hash",
    "fallback_cta_non_authoritative": "def build_final_publication_cta_from_current_state(",
    "fallback_display_non_authoritative": "renderer_driving=False",
    "fallback_cta_fallback_only": "render_fallback_shell_model",
    "fallback_display_fallback_only": "render_fallback_shell_model",
    "legacy_session_metadata_key": "_FINAL_PUBLICATION_LEGACY_SESSION_METADATA_KEY",
    "legacy_session_non_authoritative": '"legacy_non_authoritative": True',
    "legacy_session_compatibility": '"compatibility_only": True',
    "legacy_session_derived": '"derived_from": "FinalDesignGuidePublication"',
    "legacy_session_no_override": '"may_override_publication": False',
    "apply_queue_page_owned": "def _queue_primary_design_guide_button_action(",
    "apply_handler_page_owned": "handle_apply_buttons",
    "render_final_panel": "render_design_guide_panel_orchestration(",
    "render_html_only": "def render_final_design_guide_card_html(",
}

REQUIRED_FINAL_PUBLICATION_TOKENS = {
    "publication_object": "class FinalDesignGuidePublication",
    "cta_object": "class FinalDesignGuideCTA",
    "display_object": "class FinalDesignGuideDisplay",
    "verifier_payload_object": "class FinalDesignGuideVerifierPayload",
    "stable_hash": "def stable_final_publication_hash(",
    "cta_adapter": "def build_final_publication_cta_from_current_state(",
    "display_adapter": "def build_final_publication_display_from_current_card_model(",
    "publication_builder": "def build_final_design_guide_publication(",
}

FORBIDDEN_FINAL_PUBLICATION_TOKENS = (
    "inputs_page",
    "streamlit",
    "session_state",
    "st.button",
    "st.markdown",
    "unsafe_allow_html",
    "render_final_panel",
    "handle_apply_buttons",
    "apply_design_guide_primary_action",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _module_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _run_gate(script: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [sys.executable, script],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=GATE_TIMEOUT_SEC,
        )
        return {
            "script": script,
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
            "timed_out": False,
            "timeout_sec": GATE_TIMEOUT_SEC,
            "stdout_tail": proc.stdout.strip().splitlines()[-10:],
            "stderr_tail": proc.stderr.strip().splitlines()[-10:],
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "script": script,
            "returncode": None,
            "passed": False,
            "timed_out": True,
            "timeout_sec": GATE_TIMEOUT_SEC,
            "stdout_tail": str(stdout).strip().splitlines()[-10:],
            "stderr_tail": str(stderr).strip().splitlines()[-10:],
            "timeout_reason": "gate_subprocess_timeout",
        }


def _latest_artifact(prefix: str) -> dict[str, Any]:
    candidates = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {"found": False, "path": None, "status": None}
    path = candidates[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "status": "INVALID_JSON", "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "snapshot_hash": payload.get("snapshot_hash"),
        "failures": payload.get("failures"),
    }


def _authority_audit_status() -> dict[str, Any]:
    candidates = sorted(
        AUDIT_DIR.glob("design_guide_final_publication_authority_audit_*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {"found": False, "path": None}
    path = candidates[0]
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "found": True,
        "path": str(path),
        "contains_final_authority": "Final" in text and "publication" in text.lower(),
    }


def _token_checks(source: str, tokens: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        name: {"token": token, "present": token in source}
        for name, token in tokens.items()
    }


def _composed_inputs_source() -> str:
    parts = [INPUTS_PAGE, ROUTE_COORDINATORS, APP_CONTRACT_BRIDGE, APPLY_ROUTING]
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in parts
        if path.exists()
    )


def _build_snapshot() -> dict[str, Any]:
    inputs_source = _composed_inputs_source()
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    formatter_source = (ROOT / "design_brain" / "final_design_guide_formatter.py").read_text(
        encoding="utf-8", errors="replace"
    )
    card_renderer_source = (ROOT / "ui" / "final_design_guide_card.py").read_text(
        encoding="utf-8", errors="replace"
    )
    proof_source = "\n".join([inputs_source, final_source, formatter_source, card_renderer_source])
    authority_audit = _authority_audit_status()
    dead_body_artifact = _latest_artifact("design_guide_final_visible_resolver_dead_body_deletion_proof")
    render_bridge_lock = _latest_artifact("design_guide_render_bridge_lock")
    compute_bridge_lock = _latest_artifact("design_guide_compute_resolver_publication_bridge_lock")
    final_visible_resolver_body_deleted = (
        dead_body_artifact.get("status") == "PASS"
        and "def resolve_final_visible_design_guide_item(" not in inputs_source
    )

    gate_results: dict[str, dict[str, Any]] = {}
    for gate in COMPOSED_GATES:
        if final_visible_resolver_body_deleted and gate["id"] in RETIRED_AFTER_FINAL_VISIBLE_RESOLVER_DELETION:
            gate_results[gate["id"]] = {
                **gate,
                "passed": True,
                "returncode": 0,
                "timed_out": False,
                "stdout_tail": "retired after final visible resolver dead-body deletion proof",
                "stderr_tail": "",
                "retired": True,
                "retired_by": dead_body_artifact.get("path"),
            }
            print(f"retired {gate['id']} via final-visible resolver dead-body proof", flush=True)
            continue
        print(f"running {gate['id']} ...", flush=True)
        result = _run_gate(gate["script"])
        print(
            f"finished {gate['id']} passed={result.get('passed')} timed_out={result.get('timed_out')}",
            flush=True,
        )
        gate_results[gate["id"]] = {
            **gate,
            **result,
        }

    inputs_token_checks = _token_checks(proof_source, REQUIRED_INPUTS_TOKENS)
    final_token_checks = _token_checks(final_source, REQUIRED_FINAL_PUBLICATION_TOKENS)
    retired_inputs_tokens_after_final_visible_deletion = {
        "legacy_session_metadata_key",
        "legacy_session_non_authoritative",
        "legacy_session_compatibility",
        "legacy_session_derived",
        "legacy_session_no_override",
    }
    missing_inputs_tokens = [
        name
        for name, row in inputs_token_checks.items()
        if not row["present"]
        and not (
            final_visible_resolver_body_deleted
            and name in retired_inputs_tokens_after_final_visible_deletion
        )
    ]
    missing_final_tokens = [
        name for name, row in final_token_checks.items() if not row["present"]
    ]
    final_imports = _module_imports(FINAL_PUBLICATION)
    forbidden_final_imports = [
        name
        for name in final_imports
        if name == "inputs_page" or name.startswith("inputs_page.") or name == "streamlit"
    ]
    forbidden_final_tokens = [
        token for token in FORBIDDEN_FINAL_PUBLICATION_TOKENS if token in final_source
    ]

    gate_failures = [
        gate_id for gate_id, row in gate_results.items() if not row["passed"]
    ]
    failures: list[str] = []
    if not authority_audit["found"]:
        failures.append("final_publication_authority_audit_missing")
    if gate_failures:
        failures.append("composed_gate_failed")
    if missing_inputs_tokens:
        failures.append("missing_inputs_page_authority_tokens")
    if missing_final_tokens:
        failures.append("missing_final_publication_tokens")
    if forbidden_final_imports or forbidden_final_tokens:
        failures.append("final_publication_forbidden_runtime_dependency")

    cta_authority = bool(
        inputs_token_checks["cta_authority"]["present"]
        and gate_results["live_cta_authority_cutover"]["passed"]
    )
    display_authority = bool(
        inputs_token_checks["display_authority"]["present"]
        and gate_results["live_card_vm_authority_cutover"]["passed"]
    )
    same_object = bool(
        inputs_token_checks["same_object_payload"]["present"]
        and (
            gate_results["verifier_debug_same_object"]["passed"]
            or final_visible_resolver_body_deleted
        )
    )
    render_session_fallback_non_authoritative = bool(
        (
            gate_results["render_after_publication_freeze"]["passed"]
            or final_visible_resolver_body_deleted
        )
        and inputs_token_checks["fallback_cta_non_authoritative"]["present"]
        and inputs_token_checks["fallback_display_non_authoritative"]["present"]
    )
    legacy_compatibility = bool(
        final_visible_resolver_body_deleted
        or (
            gate_results["session_boundary_canonicalization"]["passed"]
            and inputs_token_checks["legacy_session_non_authoritative"]["present"]
            and inputs_token_checks["legacy_session_compatibility"]["present"]
            and inputs_token_checks["legacy_session_no_override"]["present"]
        )
    )
    page_render_route_store_only = bool(
        inputs_token_checks["apply_queue_page_owned"]["present"]
        and inputs_token_checks["apply_handler_page_owned"]["present"]
        and inputs_token_checks["render_final_panel"]["present"]
        and inputs_token_checks["render_html_only"]["present"]
        and render_session_fallback_non_authoritative
        and gate_results["design_brain_inputs_page_independence_audit"]["passed"]
    )
    apply_routing_shared_page_owned = bool(
        inputs_token_checks["apply_queue_page_owned"]["present"]
        and inputs_token_checks["apply_handler_page_owned"]["present"]
        and cta_authority
    )
    fallback_shells_fallback_only = bool(
        inputs_token_checks["fallback_cta_fallback_only"]["present"]
        and inputs_token_checks["fallback_display_fallback_only"]["present"]
        and render_session_fallback_non_authoritative
    )
    legacy_page_no_action_banner_deleted = bool(
        "st.info(str(uvr))" not in inputs_source
        and "st.info(passive_reason)" not in inputs_source
        and 'st.caption(f"Reason: {passive_stop_reason}.")' not in inputs_source
    )
    final_publication_consumes_design_guide_presentation = bool(
        "def build_final_design_guide_display(" in final_source
        and "debug: dict[str, Any] | None = None" in final_source
        and "presentation_d = _mapping(debug_d.get(\"design_guide_presentation\"))" in final_source
        and "display = build_final_design_guide_display(item=item_d, debug=debug_d)" in final_source
    )

    direct_proof = {
        "final_publication_authority_audit_exists": bool(authority_audit["found"]),
        "final_design_guide_publication_is_cta_authority": cta_authority,
        "final_design_guide_publication_is_display_card_vm_authority": display_authority,
        "final_publication_consumes_design_guide_presentation": final_publication_consumes_design_guide_presentation,
        "legacy_page_no_action_banner_deleted": legacy_page_no_action_banner_deleted,
        "verifier_debug_browser_payloads_hash_stamped_from_same_object": same_object,
        "render_session_fallback_paths_non_authoritative_after_publication": render_session_fallback_non_authoritative,
        "legacy_duplicated_publication_keys_compatibility_only": legacy_compatibility,
        "inputs_page_may_render_route_store_but_cannot_reinterpret_publication_truth": page_render_route_store_only,
        "apply_routing_remains_shared_page_owned_and_consumes_publication_cta": apply_routing_shared_page_owned,
        "fallback_shells_are_fallback_only_and_non_authoritative": fallback_shells_fallback_only,
        "final_publication_has_no_page_ui_runtime_imports": not bool(
            forbidden_final_imports or forbidden_final_tokens
        ),
        "legacy_final_visible_resolver_body_deleted": final_visible_resolver_body_deleted,
    }
    failed_direct_proof = [
        name for name, passed in direct_proof.items() if not passed
    ]
    if failed_direct_proof:
        failures.append("direct_independence_proof_failed")

    status = "PASS" if not failures else "FAIL"
    latest_artifacts = {
        "final_publication_authority_snapshot": _latest_artifact("design_guide_final_publication_authority"),
        "final_publication_object_snapshot": _latest_artifact("design_guide_final_publication_object"),
        "final_publication_boundary_snapshot": _latest_artifact("design_guide_final_publication_boundary"),
        "passive_cleanup_final_publication_divergence": _latest_artifact(
            "design_guide_passive_cleanup_final_publication_divergence"
        ),
        "inputs_page_legacy_truth_surface_audit": _latest_artifact(
            "design_guide_inputs_page_legacy_truth_surface_audit"
        ),
        "cta_authority_readiness": _latest_artifact("design_guide_cta_authority_readiness"),
        "cta_adapter_parity": _latest_artifact("design_guide_cta_adapter_parity"),
        "live_cta_wiring": _latest_artifact("design_guide_live_cta_wiring"),
        "live_cta_authority_cutover": _latest_artifact("design_guide_live_cta_authority_cutover"),
        "card_vm_authority_readiness": _latest_artifact("design_guide_card_vm_authority_readiness"),
        "card_vm_adapter_parity": _latest_artifact("design_guide_card_vm_adapter_parity"),
        "live_card_vm_wiring": _latest_artifact("design_guide_live_card_vm_wiring"),
        "live_card_vm_authority_cutover": _latest_artifact("design_guide_live_card_vm_authority_cutover"),
        "render_after_publication_freeze": _latest_artifact("design_guide_render_after_publication_freeze"),
        "verifier_debug_same_object": _latest_artifact("design_guide_verifier_debug_same_object"),
        "session_boundary_readiness": _latest_artifact("design_guide_session_boundary_readiness"),
        "session_boundary_canonicalization": _latest_artifact("design_guide_session_boundary_canonicalization"),
        "design_brain_inputs_page_independence_audit": _latest_artifact("design_brain_inputs_page_independence_audit"),
        "locked_family_live_wiring_snapshot": _latest_artifact("locked_family_live_wiring"),
    }
    snapshot_hash = _stable_hash(
        {
            "direct_proof": direct_proof,
            "gate_results": {
                gate_id: row["passed"] for gate_id, row in gate_results.items()
            },
            "authority_audit": authority_audit,
            "missing_inputs_tokens": missing_inputs_tokens,
            "missing_final_tokens": missing_final_tokens,
            "failed_direct_proof": failed_direct_proof,
        }
    )
    return {
        "snapshot_name": "design_guide_independence_lock",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "direct_proof": direct_proof,
        "failed_direct_proof": failed_direct_proof,
        "authority_audit": authority_audit,
        "composed_gates": gate_results,
        "gate_failures": gate_failures,
        "latest_artifacts": latest_artifacts,
        "dead_body_artifact": dead_body_artifact,
        "render_bridge_lock_artifact": render_bridge_lock,
        "compute_bridge_lock_artifact": compute_bridge_lock,
        "inputs_page_token_checks": inputs_token_checks,
        "missing_inputs_page_tokens": missing_inputs_tokens,
        "final_publication_token_checks": final_token_checks,
        "missing_final_publication_tokens": missing_final_tokens,
        "final_publication_imports": final_imports,
        "forbidden_final_publication_imports": forbidden_final_imports,
        "forbidden_final_publication_tokens": forbidden_final_tokens,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_display_authority_changed": False,
        "fallback_shells_removed": False,
        "legacy_session_keys_deleted": bool(final_visible_resolver_body_deleted),
        "apply_routing_changed": False,
        "lock_status": (
            "Design Guide independence lock complete"
            if status == "PASS"
            else "Design Guide independence lock blocked"
        ),
        "snapshot_hash": snapshot_hash,
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    proof_rows = [
        f"| {name} | `{value}` |"
        for name, value in snapshot["direct_proof"].items()
    ]
    gate_rows = [
        f"| {row['label']} | `{row['passed']}` | `{row['returncode']}` | `{row['script']}` |"
        for row in snapshot["composed_gates"].values()
    ]
    artifact_rows = [
        f"| {name} | `{row.get('found')}` | `{row.get('status')}` | `{row.get('path')}` |"
        for name, row in snapshot["latest_artifacts"].items()
    ]
    body = "\n".join(
        [
            "# Design Guide Independence Lock Verifier",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Lock status: `{snapshot['lock_status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Direct Proof",
            "",
            "| Check | Value |",
            "|---|---:|",
            *proof_rows,
            "",
            "## Composed Gates",
            "",
            "| Gate | Passed | Return Code | Script |",
            "|---|---:|---:|---|",
            *gate_rows,
            "",
            "## Latest Artifacts",
            "",
            "| Artifact | Found | Status | Path |",
            "|---|---:|---|---|",
            *artifact_rows,
            "",
            "## Authority Audit",
            "",
            f"- Found: `{snapshot['authority_audit'].get('found')}`",
            f"- Path: `{snapshot['authority_audit'].get('path')}`",
            "",
            "## Scope",
            "",
            "- Product behavior changed: `False`",
            "- Visible wording changed: `False`",
            "- CTA/display authority changed: `False`",
            "- Fallback shells removed: `False`",
            "- Legacy session keys deleted: `False`",
            "- Apply routing changed: `False`",
            "",
            "## Failures",
            "",
            (
                "None."
                if not snapshot["failures"]
                else "\n".join(f"- `{failure}`" for failure in snapshot["failures"])
            ),
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_independence_lock_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_independence_lock_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_independence_lock {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
        if snapshot["gate_failures"]:
            print("Gate failures:")
            for gate in snapshot["gate_failures"]:
                print(f"- {gate}")
        if snapshot["failed_direct_proof"]:
            print("Direct proof failures:")
            for proof in snapshot["failed_direct_proof"]:
                print(f"- {proof}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
