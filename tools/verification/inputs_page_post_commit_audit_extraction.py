"""Verify one-click post-commit audit extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "post_commit_audit.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")

    bridge_node = _function_node(bridge_source, "_one_click_post_commit_audit")
    bridge_subset_node = _function_node(bridge_source, "_one_click_post_commit_audit_subset")
    bridge_passes_node = _function_node(bridge_source, "_one_click_commit_audit_passes")
    bridge_green_node = _function_node(bridge_source, "_post_click_accepted_green_audit")
    module_node = _function_node(module_source, "_one_click_post_commit_audit")
    module_subset_node = _function_node(module_source, "_one_click_post_commit_audit_subset")
    module_passes_node = _function_node(module_source, "_one_click_commit_audit_passes")
    module_green_node = _function_node(module_source, "_post_click_accepted_green_audit")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_subset_body = ast.get_source_segment(bridge_source, bridge_subset_node) or ""
    bridge_passes_body = ast.get_source_segment(bridge_source, bridge_passes_node) or ""
    bridge_green_body = ast.get_source_segment(bridge_source, bridge_green_node) or ""
    module_passes_body = ast.get_source_segment(module_source, module_passes_node) or ""
    module_green_body = ast.get_source_segment(module_source, module_green_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 3,
        "bridge_binds_dependencies": "_bind_post_commit_audit_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_one_click_post_commit_audit_extracted" in bridge_body,
        "bridge_subset_wrapper_is_tiny": (
            bridge_subset_node.end_lineno or bridge_subset_node.lineno
        ) - bridge_subset_node.lineno + 1 <= 3,
        "bridge_subset_binds_dependencies": "_bind_post_commit_audit_dependencies(globals())" in bridge_subset_body,
        "bridge_subset_delegates_to_extracted_module": "_one_click_post_commit_audit_subset_extracted" in bridge_subset_body,
        "bridge_passes_wrapper_is_tiny": (
            bridge_passes_node.end_lineno or bridge_passes_node.lineno
        ) - bridge_passes_node.lineno + 1 <= 16,
        "bridge_passes_binds_dependencies": "_bind_post_commit_audit_dependencies(globals())" in bridge_passes_body,
        "bridge_passes_delegates_to_extracted_module": "_one_click_commit_audit_passes_extracted" in bridge_passes_body,
        "bridge_green_wrapper_is_tiny": (
            bridge_green_node.end_lineno or bridge_green_node.lineno
        ) - bridge_green_node.lineno + 1 <= 16,
        "bridge_green_binds_dependencies": "_bind_post_commit_audit_dependencies(globals())" in bridge_green_body,
        "bridge_green_delegates_to_extracted_module": "_post_click_accepted_green_audit_extracted" in bridge_green_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 120,
        "module_contains_subset_body": (
            module_subset_node.end_lineno or module_subset_node.lineno
        ) - module_subset_node.lineno + 1 >= 110,
        "module_contains_passes_body": (
            module_passes_node.end_lineno or module_passes_node.lineno
        ) - module_passes_node.lineno + 1 >= 65,
        "module_contains_green_audit_body": (
            module_green_node.end_lineno or module_green_node.lineno
        ) - module_green_node.lineno + 1 >= 60,
        "module_has_dependency_binder": "def bind_post_commit_audit_dependencies" in module_source,
        "module_binds_shared_defaults": '"SHARED_DEFAULTS"' in module_source,
        "module_binds_beam_status_fail": '"BEAM_STATUS_FAIL"' in module_source,
        "module_binds_green_audit_dependencies": all(
            token in module_source
            for token in (
                '"FINAL_ACCEPTED_MIN_FAMILY_UTIL"',
                '"_final_accepted_meaningful_family_utils"',
                '"_governing_family_for_local_cleanup"',
                '"_accepted_green_exact_blockers_by_family"',
                '"_shear_overprovision_floor_exact_blocker"',
                '"_shear_low_util_active_links_exact_blocker"',
                '"_bending_low_util_floor_exact_blocker"',
                '"_accepted_green_cleanup_evidence_by_family"',
            )
        ),
        "module_subset_is_not_borrowed_from_bridge": '"_one_click_post_commit_audit_subset"' not in (
            module_source.split("_POST_COMMIT_AUDIT_DEPENDENCIES", 1)[1].split(")", 1)[0]
        ),
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_post_commit_contract_surface": all(
            token in module_source
            for token in (
                "applied_final_updates",
                "audited_commit_updates",
                "ignored_commit_update_keys",
                "has_row_model_updates",
                "post_commit_shared_subset",
                "post_commit_matches_intended_updates",
                "post_commit_mismatch_keys",
                "post_commit_live_worst_util",
                "post_commit_eval_shared_worst_util",
                "post_commit_eval_shared_packed_worst_util",
                "post_commit_eval_summary_worst_util",
                "post_commit_summary_state_subset",
                "one_click_post_commit_audit_shared_eval",
                "one_click_post_commit_audit_summary_eval",
            )
        ),
        "module_keeps_passes_contract_surface": all(
            token in module_passes_body
            for token in (
                "post_commit_missing_validation",
                "post_commit_mismatch",
                "post_commit_no_util_improvement_partial_path",
                "post_commit_no_util_improvement_best_effort_cleanup",
                "post_commit_util_exceeds_limit",
                "post_commit_no_fail_count_improvement_best_effort_cleanup",
                "post_commit_fail_status",
            )
        ),
        "module_keeps_green_audit_contract_surface": all(
            token in module_green_body
            for token in (
                "final_accepted_min_family_util",
                "post_click_family_utils",
                "post_click_family_utils_meaningful",
                "post_click_families_below_final_threshold",
                "post_click_unresolved_low_util_families",
                "post_click_excluded_families",
                "post_click_materially_overprovided_families",
                "post_click_unresolved_overprovided_families",
                "post_click_cleanup_evidence_by_family",
                "post_click_exact_blockers_by_family",
                "post_click_accepted_green_valid",
                "post_click_accepted_green_invalid_reason",
                "post_click_materially_overprovided_threshold",
                "post_click_governing_family",
                "unresolved_meaningful_family_util_below_",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import post_commit_audit as extracted

    original = bridge._one_click_post_commit_audit_extracted
    original_subset = bridge._one_click_post_commit_audit_subset_extracted
    original_passes = bridge._one_click_commit_audit_passes_extracted
    original_green = bridge._post_click_accepted_green_audit_extracted
    call_record: dict = {}
    subset_call_record: dict = {}
    passes_call_record: dict = {}
    green_call_record: dict = {}

    def _fake_extracted(intended: dict) -> dict:
        call_record.update(
            {
                "intended": dict(intended),
                "bound_shared": getattr(extracted, "_shared_state_snapshot", None) is bridge._shared_state_snapshot,
                "bound_summary": getattr(extracted, "_resolved_inputs_summary_state", None)
                is bridge._resolved_inputs_summary_state,
                "bound_overview": getattr(extracted, "_collect_design_overview", None)
                is bridge._collect_design_overview,
                "bound_eval": getattr(extracted, "evaluate_candidate_full", None)
                is bridge.evaluate_candidate_full,
                "bound_shared_defaults": getattr(extracted, "SHARED_DEFAULTS", None) is bridge.SHARED_DEFAULTS,
            }
        )
        return {"applied_final_updates": dict(intended)}

    def _fake_subset(intended: dict) -> dict:
        subset_call_record.update(
            {
                "intended": dict(intended),
                "bound_shared_defaults": getattr(extracted, "SHARED_DEFAULTS", None) is bridge.SHARED_DEFAULTS,
            }
        )
        return {
            "audited_updates": {"D": intended.get("D")},
            "ignored_keys": ["Ast_bot"],
            "has_row_model_updates": False,
            "ignored_row_model_legacy_mirror_keys": [],
        }

    def _fake_passes(commit_audit: dict | None, **kwargs) -> tuple[bool, str]:
        passes_call_record.update(
            {
                "commit_audit": dict(commit_audit or {}),
                "kwargs": dict(kwargs),
                "bound_beam_status_fail": getattr(extracted, "BEAM_STATUS_FAIL", None) == bridge.BEAM_STATUS_FAIL,
            }
        )
        return True, "delegated"

    def _fake_green(overview: dict | None, **kwargs) -> dict:
        green_call_record.update(
            {
                "overview": dict(overview or {}),
                "kwargs": dict(kwargs),
                "bound_final_threshold": getattr(extracted, "FINAL_ACCEPTED_MIN_FAMILY_UTIL", None)
                == bridge.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
                "bound_family_utils": getattr(extracted, "_final_accepted_meaningful_family_utils", None)
                is bridge._final_accepted_meaningful_family_utils,
                "bound_governing": getattr(extracted, "_governing_family_for_local_cleanup", None)
                is bridge._governing_family_for_local_cleanup,
                "bound_exact_blockers": getattr(extracted, "_accepted_green_exact_blockers_by_family", None)
                is bridge._accepted_green_exact_blockers_by_family,
                "bound_shear_floor": getattr(extracted, "_shear_overprovision_floor_exact_blocker", None)
                is bridge._shear_overprovision_floor_exact_blocker,
                "bound_shear_active": getattr(extracted, "_shear_low_util_active_links_exact_blocker", None)
                is bridge._shear_low_util_active_links_exact_blocker,
                "bound_bending_floor": getattr(extracted, "_bending_low_util_floor_exact_blocker", None)
                is bridge._bending_low_util_floor_exact_blocker,
            }
        )
        return {"post_click_accepted_green_valid": True, "delegated": True}

    try:
        bridge._one_click_post_commit_audit_extracted = _fake_extracted
        bridge._one_click_post_commit_audit_subset_extracted = _fake_subset
        bridge._one_click_commit_audit_passes_extracted = _fake_passes
        bridge._post_click_accepted_green_audit_extracted = _fake_green
        returned = bridge._one_click_post_commit_audit({"D": 650})
        subset_returned = bridge._one_click_post_commit_audit_subset({"D": 650, "Ast_bot": 1200})
        passes_returned = bridge._one_click_commit_audit_passes(
            {"post_commit_matches_intended_updates": True},
            partial_progress_commit=True,
            pre_commit_worst_util=1.2,
        )
        green_returned = bridge._post_click_accepted_green_audit(
            {"statuses": {"bending": "PASS"}},
            blocker_source={"x": 1},
            state={"D": 650},
            threshold=0.73,
            build_active_shear_blocker=False,
        )
    finally:
        bridge._one_click_post_commit_audit_extracted = original
        bridge._one_click_post_commit_audit_subset_extracted = original_subset
        bridge._one_click_commit_audit_passes_extracted = original_passes
        bridge._post_click_accepted_green_audit_extracted = original_green

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_shared_state_snapshot", None) is bridge._shared_state_snapshot
        and getattr(extracted, "_resolved_inputs_summary_state", None) is bridge._resolved_inputs_summary_state
        and getattr(extracted, "_collect_design_overview", None) is bridge._collect_design_overview
        and getattr(extracted, "evaluate_candidate_full", None) is bridge.evaluate_candidate_full
        and getattr(extracted, "SHARED_DEFAULTS", None) is bridge.SHARED_DEFAULTS
        and getattr(extracted, "BEAM_STATUS_FAIL", None) == bridge.BEAM_STATUS_FAIL
        and getattr(extracted, "FINAL_ACCEPTED_MIN_FAMILY_UTIL", None) == bridge.FINAL_ACCEPTED_MIN_FAMILY_UTIL
        and getattr(extracted, "_final_accepted_meaningful_family_utils", None)
        is bridge._final_accepted_meaningful_family_utils
        and getattr(extracted, "_governing_family_for_local_cleanup", None)
        is bridge._governing_family_for_local_cleanup
        and getattr(extracted, "_accepted_green_exact_blockers_by_family", None)
        is bridge._accepted_green_exact_blockers_by_family
        and getattr(extracted, "_shear_overprovision_floor_exact_blocker", None)
        is bridge._shear_overprovision_floor_exact_blocker
        and getattr(extracted, "_shear_low_util_active_links_exact_blocker", None)
        is bridge._shear_low_util_active_links_exact_blocker
        and getattr(extracted, "_bending_low_util_floor_exact_blocker", None)
        is bridge._bending_low_util_floor_exact_blocker
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"applied_final_updates": {"D": 650}}
        and call_record.get("intended") == {"D": 650}
        and call_record.get("bound_shared") is True
        and call_record.get("bound_summary") is True
        and call_record.get("bound_overview") is True
        and call_record.get("bound_eval") is True
        and call_record.get("bound_shared_defaults") is True
    )
    checks["bridge_subset_runtime_delegates_with_arguments"] = (
        subset_returned
        == {
            "audited_updates": {"D": 650},
            "ignored_keys": ["Ast_bot"],
            "has_row_model_updates": False,
            "ignored_row_model_legacy_mirror_keys": [],
        }
        and subset_call_record.get("intended") == {"D": 650, "Ast_bot": 1200}
        and subset_call_record.get("bound_shared_defaults") is True
    )
    checks["bridge_passes_runtime_delegates_with_arguments"] = (
        passes_returned == (True, "delegated")
        and passes_call_record.get("commit_audit") == {"post_commit_matches_intended_updates": True}
        and passes_call_record.get("kwargs", {}).get("partial_progress_commit") is True
        and passes_call_record.get("kwargs", {}).get("pre_commit_worst_util") == 1.2
        and passes_call_record.get("bound_beam_status_fail") is True
    )
    checks["bridge_green_runtime_delegates_with_arguments"] = (
        green_returned == {"post_click_accepted_green_valid": True, "delegated": True}
        and green_call_record.get("overview") == {"statuses": {"bending": "PASS"}}
        and green_call_record.get("kwargs", {}).get("blocker_source") == {"x": 1}
        and green_call_record.get("kwargs", {}).get("state") == {"D": 650}
        and green_call_record.get("kwargs", {}).get("threshold") == 0.73
        and green_call_record.get("kwargs", {}).get("build_active_shear_blocker") is False
        and green_call_record.get("bound_final_threshold") is True
        and green_call_record.get("bound_family_utils") is True
        and green_call_record.get("bound_governing") is True
        and green_call_record.get("bound_exact_blockers") is True
        and green_call_record.get("bound_shear_floor") is True
        and green_call_record.get("bound_shear_active") is True
        and green_call_record.get("bound_bending_floor") is True
    )

    extracted.bind_post_commit_audit_dependencies({"BEAM_STATUS_FAIL": bridge.BEAM_STATUS_FAIL})
    pass_cases = {
        "valid": extracted._one_click_commit_audit_passes(
            {
                "post_commit_matches_intended_updates": True,
                "post_commit_live_worst_util": 0.98,
                "post_commit_live_statuses": {"bending": "PASS"},
            }
        ),
        "mismatch": extracted._one_click_commit_audit_passes(
            {
                "post_commit_matches_intended_updates": False,
                "post_commit_live_worst_util": 0.98,
                "post_commit_live_statuses": {"bending": "PASS"},
            }
        ),
        "util_exceeds": extracted._one_click_commit_audit_passes(
            {
                "post_commit_matches_intended_updates": True,
                "post_commit_live_worst_util": 1.02,
                "post_commit_live_statuses": {"bending": "PASS"},
            }
        ),
        "fail_status": extracted._one_click_commit_audit_passes(
            {
                "post_commit_matches_intended_updates": True,
                "post_commit_live_worst_util": 0.98,
                "post_commit_live_statuses": {"bending": bridge.BEAM_STATUS_FAIL},
            }
        ),
        "partial_progress_pass": extracted._one_click_commit_audit_passes(
            {
                "post_commit_matches_intended_updates": True,
                "post_commit_live_worst_util": 1.10,
                "post_commit_live_statuses": {"bending": "FAIL"},
            },
            partial_progress_commit=True,
            pre_commit_worst_util=1.20,
        ),
        "best_effort_fail_count_pass": extracted._one_click_commit_audit_passes(
            {
                "post_commit_matches_intended_updates": True,
                "post_commit_live_worst_util": 0.90,
                "post_commit_live_statuses": {"bending": "PASS"},
            },
            best_effort_cleanup_commit=True,
            pre_commit_worst_util=1.00,
            pre_commit_statuses={"bending": "FAIL"},
        ),
    }
    checks["module_passes_runtime_cases"] = (
        pass_cases["valid"] == (True, "")
        and pass_cases["mismatch"] == (False, "post_commit_mismatch")
        and pass_cases["util_exceeds"] == (False, "post_commit_util_exceeds_limit")
        and pass_cases["fail_status"] == (False, "post_commit_fail_status")
        and pass_cases["partial_progress_pass"] == (True, "")
        and pass_cases["best_effort_fail_count_pass"] == (True, "")
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "bridge_subset_wrapper_lines": (
            bridge_subset_node.end_lineno or bridge_subset_node.lineno
        ) - bridge_subset_node.lineno + 1,
        "bridge_passes_wrapper_lines": (
            bridge_passes_node.end_lineno or bridge_passes_node.lineno
        ) - bridge_passes_node.lineno + 1,
        "bridge_green_wrapper_lines": (
            bridge_green_node.end_lineno or bridge_green_node.lineno
        ) - bridge_green_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
        "module_subset_function_lines": (
            module_subset_node.end_lineno or module_subset_node.lineno
        ) - module_subset_node.lineno + 1,
        "module_passes_function_lines": (
            module_passes_node.end_lineno or module_passes_node.lineno
        ) - module_passes_node.lineno + 1,
        "module_green_function_lines": (
            module_green_node.end_lineno or module_green_node.lineno
        ) - module_green_node.lineno + 1,
        "passes_runtime_cases": pass_cases,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_post_commit_audit_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_post_commit_audit_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Commit Audit Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Bridge subset wrapper lines: {result['bridge_subset_wrapper_lines']}",
                f"- Bridge passes wrapper lines: {result['bridge_passes_wrapper_lines']}",
                f"- Bridge accepted-green wrapper lines: {result['bridge_green_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                f"- Extracted module subset function lines: {result['module_subset_function_lines']}",
                f"- Extracted module passes function lines: {result['module_passes_function_lines']}",
                f"- Extracted module accepted-green function lines: {result['module_green_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(result["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
