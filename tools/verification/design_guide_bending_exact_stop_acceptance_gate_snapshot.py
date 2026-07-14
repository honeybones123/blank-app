from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.publication import accepted_green_exact_blocker_is_valid


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _base_bending_blocker() -> dict:
    return {
        "family": "bending",
        "source": "post_click_bending_cleanup_exhaustive_search",
        "exact_blocker": True,
        "search_ran": True,
        "search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "target_band_search_ran": True,
        "target_band_search_exhaustive": True,
        "failed_check_name": "final accepted bending utilisation threshold",
        "failed_check_status": "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD",
        "failed_check_util": 0.10,
        "failed_check_demand": 30.0,
        "failed_check_capacity_or_limit": 0.85,
        "current_util": 0.10,
        "threshold": 0.85,
        "attempted_candidate_count": 6,
        "failed_candidate_id": "post_click_bending_cleanup_best_safe_below_threshold",
        "best_rejected_candidate_id": "post_click_bending_cleanup_best_safe_below_threshold",
        "attempted_updates": {"bot1_count": 6, "db_bot_1": 20},
        "reason": "the exact target-band search found no safe executor-backed option.",
        "why_reduction_would_hurt_other_design_elements": (
            "Ductility (k_u / ku) governs the remaining bending cleanup boundary."
        ),
        "best_safe_candidate_applied": True,
        "no_second_cta_required": False,
        "executable_candidate_count": 0,
        "executable_cleanup_count": 0,
        "target_band_candidate_count": 0,
        "executable_target_band_candidate_count": 0,
        "exact_stop_cleanup_proof_chain_complete": False,
        "every_valid_cleanup_path_exhausted_for_contract_defined_reasons": False,
        "reo_reduction_attempted_first_for_ductility": False,
        "width_reduction_as_min_relief_checked": False,
        "depth_reduction_as_min_relief_checked": False,
        "width_reduction_progressive_relief_exhausted_to_contract_bounds": False,
        "depth_reduction_progressive_relief_exhausted_to_contract_bounds": False,
        "progressive_geometry_relief_exhausted_to_contract_bounds": False,
        "width_reduction_restarted_reinforcement_candidate_count": 0,
        "depth_reduction_restarted_reinforcement_candidate_count": 0,
        "bottom_reo_layer_search_restarted_after_geometry_relief": False,
        "layer_search_restarted_after_geometry_relief": False,
    }


def _base_shear_blocker() -> dict:
    return {
        "family": "shear",
        "source": "post_click_residual_shear_cleanup_search",
        "exact_blocker": True,
        "search_ran": True,
        "search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "target_band_search_ran": True,
        "target_band_search_exhaustive": True,
        "failed_check_name": "final accepted shear utilisation threshold",
        "failed_check_status": "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD",
        "failed_check_util": 0.93,
        "failed_check_demand": 200.0,
        "failed_check_capacity_or_limit": 0.85,
        "current_util": 0.93,
        "threshold": 0.85,
        "attempted_candidate_count": 4,
        "failed_candidate_id": "post_click_residual_shear_cleanup_best_safe",
        "best_rejected_candidate_id": "post_click_residual_shear_cleanup_best_safe",
        "attempted_updates": {"lig_spacing": 300, "lig_legs": 2},
        "reason": "no executable shear cleanup reaches the accepted band without failing a required check.",
        "best_safe_candidate_applied": True,
        "no_second_cta_required": True,
        "executable_candidate_count": 0,
        "executable_cleanup_count": 0,
        "target_band_candidate_count": 0,
        "executable_target_band_candidate_count": 0,
    }


def main() -> int:
    bending_without_proof = _base_bending_blocker()
    bending_with_proof = {
        **_base_bending_blocker(),
        "no_second_cta_required": True,
        "exact_stop_cleanup_proof_chain_complete": True,
        "every_valid_cleanup_path_exhausted_for_contract_defined_reasons": True,
        "reo_reduction_attempted_first_for_ductility": True,
        "width_reduction_as_min_relief_checked": True,
        "depth_reduction_as_min_relief_checked": True,
        "width_reduction_progressive_relief_exhausted_to_contract_bounds": True,
        "depth_reduction_progressive_relief_exhausted_to_contract_bounds": True,
        "progressive_geometry_relief_exhausted_to_contract_bounds": True,
        "width_reduction_restarted_reinforcement_candidate_count": 3,
        "depth_reduction_restarted_reinforcement_candidate_count": 8,
        "bottom_reo_layer_search_restarted_after_geometry_relief": True,
        "layer_search_restarted_after_geometry_relief": True,
    }
    bending_partial_geometry_proof = {
        **bending_with_proof,
        "progressive_geometry_relief_exhausted_to_contract_bounds": False,
        "depth_reduction_progressive_relief_exhausted_to_contract_bounds": False,
    }
    bending_generic_source_low_util_without_proof = {
        **_base_bending_blocker(),
        "source": "design_guide_bending_only_cleanup_search",
        "failed_check_status": "PASS",
        "failed_check_util": 0.06,
        "current_util": 0.06,
        "threshold": 0.85,
        "failed_check_capacity_or_limit": 0.85,
    }
    bending_missing_family_low_util_without_proof = {
        **bending_generic_source_low_util_without_proof,
        "family": "",
        "failed_check_name": "positive bending final accepted utilisation threshold",
        "why_reduction_would_hurt_other_design_elements": (
            "Ductility k_u and As_min govern the remaining bottom reinforcement cleanup."
        ),
    }
    shear_blocker = _base_shear_blocker()
    inputs_page_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    candidate_evaluation_source = (ROOT / "design_brain" / "candidate_evaluation.py").read_text(encoding="utf-8")
    page_terminal_gate_requires_no_out_of_target_families = (
        "allow_required_checks_terminal_without_exact_blockers = (" in inputs_page_source
        and "and not out_of_target_families" in inputs_page_source
    )
    page_terminal_gate_does_not_erase_out_of_target_families = (
        "if bool(allow_required_checks_terminal) and not in_target_families:\n        out_of_target_families = []"
        not in inputs_page_source
    )
    page_terminal_gate_requires_exact_blockers_even_when_required_checks_terminal = (
        "unresolved_out_of_target = (\n        [\n            family\n            for family in out_of_target_families\n            if family not in exact_blockers\n        ]"
        in inputs_page_source
    )
    bending_cleanup_not_deferred_below_final_floor = (
        "bending_below_final_accepted_floor = bool(" in inputs_page_source
        and "_defer_expensive_cleanup_exact_proof_for_fast_render() and not bending_below_final_accepted_floor"
        in inputs_page_source
        and "bending_only_target_band_cleanup_item:2026-07-11.contract_lane_geometry_relief"
        in inputs_page_source
    )
    bending_cleanup_uses_contract_lane_geometry_relief = (
        "for trial_width in width_trials:\n            for trial_depth in depth_trials:" not in candidate_evaluation_source
        and "for trial_width in width_trials:\n            for trial_bars, trial_dia in sorted(practical_bottom_trials):" in candidate_evaluation_source
    )

    results = {
        "bending_without_proof_rejected": not accepted_green_exact_blocker_is_valid(
            bending_without_proof
        ),
        "bending_generic_source_low_util_without_proof_rejected": not accepted_green_exact_blocker_is_valid(
            bending_generic_source_low_util_without_proof
        ),
        "bending_missing_family_low_util_without_proof_rejected": not accepted_green_exact_blocker_is_valid(
            bending_missing_family_low_util_without_proof
        ),
        "bending_partial_geometry_proof_rejected": not accepted_green_exact_blocker_is_valid(
            bending_partial_geometry_proof
        ),
        "bending_with_full_proof_accepted": accepted_green_exact_blocker_is_valid(
            bending_with_proof
        ),
        "shear_path_unchanged": accepted_green_exact_blocker_is_valid(shear_blocker),
        "page_terminal_gate_requires_no_out_of_target_families": page_terminal_gate_requires_no_out_of_target_families,
        "page_terminal_gate_does_not_erase_out_of_target_families": page_terminal_gate_does_not_erase_out_of_target_families,
        "page_terminal_gate_requires_exact_blockers_even_when_required_checks_terminal": page_terminal_gate_requires_exact_blockers_even_when_required_checks_terminal,
        "bending_cleanup_not_deferred_below_final_floor": bending_cleanup_not_deferred_below_final_floor,
        "bending_cleanup_uses_contract_lane_geometry_relief": bending_cleanup_uses_contract_lane_geometry_relief,
    }
    payload = {
        "schema": "design_guide_bending_exact_stop_acceptance_gate_snapshot.v1",
        "passed": all(results.values()),
        "results": results,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_bending_exact_stop_acceptance_gate_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_exact_stop_acceptance_gate_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide bending exact-stop acceptance gate",
                "",
                f"Result: {'PASS' if payload['passed'] else 'FAIL'}",
                "",
                f"- bending without proof rejected: {results['bending_without_proof_rejected']}",
                f"- bending generic-source low-util without proof rejected: {results['bending_generic_source_low_util_without_proof_rejected']}",
                f"- bending missing-family low-util without proof rejected: {results['bending_missing_family_low_util_without_proof_rejected']}",
                f"- bending partial geometry proof rejected: {results['bending_partial_geometry_proof_rejected']}",
                f"- bending with full proof accepted: {results['bending_with_full_proof_accepted']}",
                f"- shear path unchanged: {results['shear_path_unchanged']}",
                f"- page terminal gate requires no out-of-target families: {results['page_terminal_gate_requires_no_out_of_target_families']}",
                f"- page terminal gate does not erase out-of-target families: {results['page_terminal_gate_does_not_erase_out_of_target_families']}",
                f"- page terminal gate requires exact blockers even when required-checks terminal is requested: {results['page_terminal_gate_requires_exact_blockers_even_when_required_checks_terminal']}",
                f"- bending cleanup is not deferred below the final accepted floor: {results['bending_cleanup_not_deferred_below_final_floor']}",
                f"- bending cleanup geometry relief follows contract lanes instead of a width-depth cross-product: {results['bending_cleanup_uses_contract_lane_geometry_relief']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(("PASS" if payload["passed"] else "FAIL") + f": {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
