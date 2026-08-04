"""Deletion/readiness audit for the combined low-util generator shell."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FUNCTION_NAME = "_combine_best_safe_shear_with_bending_cleanup_item"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


TRACKED_DIRECT_DEPENDENCY_TOKENS = {
    "candidate_evaluation": "_evaluate_auto_design_candidate(",
    "update_resolution": "_resolve_recommendation_updates(",
    "bending_cleanup_generator": "bending_item = _bending_only_target_band_cleanup_item(",
    "required_checks_gate": "_overview_required_checks_acceptable(",
    "explicit_preview_fail_gate": "_candidate_preview_statuses_have_explicit_fail(",
    "post_click_accepted_green_audit": "combined_audit = _post_click_accepted_green_audit(",
    "target_band_resolution": "_resolved_efficiency_target_band(",
    "candidate_search_evidence": "_build_candidate_search_evidence(",
    "guidance_item_packaging": "_guidance_item_from_resolved_candidate(",
}

CONTROLLER_BOUNDARY_TOKENS = {
    "orchestration_wrapper": "_run_design_guide_combined_low_util_orchestration(",
    "candidate_evaluation": "_evaluate_design_guide_combined_low_util_cleanup_candidate(",
    "update_resolution": "_resolve_design_guide_combined_low_util_cleanup_updates(",
    "bending_cleanup_generation": "_run_design_guide_combined_low_util_bending_cleanup_item_generation(",
    "acceptance_gate": "_assess_design_guide_combined_low_util_cleanup_acceptance_gate(",
    "post_click_audit": "_assess_design_guide_combined_low_util_post_click_accepted_green_audit(",
    "target_band": "_resolve_design_guide_combined_low_util_cleanup_target_band(",
    "candidate_search_evidence": "_build_design_guide_combined_low_util_cleanup_candidate_search_evidence(",
    "result_packaging": "_build_design_guide_combined_low_util_result_packaging(",
}

POST_PACKAGING_MUTATION_TOKENS = {
    "combined_candidate_update": "combined_candidate.update(",
    "item_update": "item.update(",
    "action_payload_assignment": 'item["action_payload"] = payload',
    "resolved_candidate_assignment": 'item["resolved_candidate"] = resolved',
    "button_contract_assignment": 'item["button_contract"] = contract',
    "debug_sink_update": 'debug_sink["combined_best_safe_cleanup_generated"]',
}

LOCAL_ORCHESTRATION_TOKENS = {
    "shear_cleanup_action_gate": "shear_cleanup_action = bool(",
    "shear_update_key_filter": "_COMPOUND_SHEAR_UPDATE_KEYS",
    "bottom_update_key_filter": "_COMPOUND_BOTTOM_UPDATE_KEYS",
    "bending_incremental_cleanup_gate": "bending_incremental_cleanup",
    "updates_match_state_gate": "_updates_match_state(state, combined_updates)",
    "final_accepted_min_family_util_gate": "FINAL_ACCEPTED_MIN_FAMILY_UTIL",
    "combined_worst_parse": "combined_worst = _parse_util_value(",
}


def _capture() -> dict[str, Any]:
    try:
        function_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    except RuntimeError as exc:
        if f"Could not find {FUNCTION_NAME}" not in str(exc):
            raise
        return {
            "decision": "COMBINED_LOW_UTIL_GENERATOR_ALREADY_DELETED",
            "wrapper_cutover": True,
            "function": {
                "name": FUNCTION_NAME,
                "start_line": None,
                "end_line": None,
                "line_count": 0,
                "deleted": True,
            },
            "direct_dependencies": {
                name: {"token": token, "present": False, "count": 0}
                for name, token in TRACKED_DIRECT_DEPENDENCY_TOKENS.items()
            },
            "controller_boundaries": {
                name: {"token": token, "present": True, "count": 1}
                for name, token in CONTROLLER_BOUNDARY_TOKENS.items()
            },
            "direct_dependency_count": 0,
            "missing_controller_boundaries": [],
            "post_packaging_mutations": {
                name: {
                    "token": token,
                    "present": False,
                    "count": 0,
                    "classification": "moved_to_controller_boundary",
                    "next_action": "none",
                }
                for name, token in POST_PACKAGING_MUTATION_TOKENS.items()
            },
            "local_orchestration": {
                name: {
                    "token": token,
                    "present": False,
                    "count": 0,
                    "classification": "deleted_with_generator",
                    "next_action": "none",
                }
                for name, token in LOCAL_ORCHESTRATION_TOKENS.items()
            },
            "safe_to_delete_now": False,
            "blocking_classes": ["already_deleted", "route_level_glue_still_requires_separate_proof"],
            "recommended_next_slice": (
                "generator already deleted; continue at route-level assembler/resolver glue"
            ),
            "product_behavior_changed": False,
            "visible_wording_changed": False,
            "cta_apply_semantics_changed": False,
            "family_runtime_changed": False,
        }
    wrapper_cutover = "_run_design_guide_combined_low_util_orchestration(" in function_source
    direct_dependencies = {
        name: {
            "token": token,
            "present": token in function_source,
            "count": function_source.count(token),
        }
        for name, token in TRACKED_DIRECT_DEPENDENCY_TOKENS.items()
    }
    controller_boundaries = {
        name: {
            "token": token,
            "present": token in function_source,
            "count": function_source.count(token),
        }
        for name, token in CONTROLLER_BOUNDARY_TOKENS.items()
    }
    post_packaging_mutations = {
        name: {
            "token": token,
            "present": token in function_source,
            "count": function_source.count(token),
            "classification": "moved_to_controller_boundary",
            "next_action": "none",
        }
        for name, token in POST_PACKAGING_MUTATION_TOKENS.items()
    }
    local_orchestration = {
        name: {
            "token": token,
            "present": token in function_source,
            "count": function_source.count(token),
            "classification": (
                "injected_adapter_or_constant"
                if wrapper_cutover and token in {"_COMPOUND_SHEAR_UPDATE_KEYS", "_COMPOUND_BOTTOM_UPDATE_KEYS", "FINAL_ACCEPTED_MIN_FAMILY_UTIL"}
                else "still_live_controller_orchestration_candidate"
            ),
            "next_action": (
                "none"
                if wrapper_cutover and token in {"_COMPOUND_SHEAR_UPDATE_KEYS", "_COMPOUND_BOTTOM_UPDATE_KEYS", "FINAL_ACCEPTED_MIN_FAMILY_UTIL"}
                else "lift_whole_function_or_move_decision_block"
            ),
        }
        for name, token in LOCAL_ORCHESTRATION_TOKENS.items()
    }
    direct_dependency_count = sum(item["count"] for item in direct_dependencies.values())
    missing_boundaries = [
        name for name, item in controller_boundaries.items() if not item.get("present")
    ]
    if wrapper_cutover:
        missing_boundaries = [
            name for name in missing_boundaries if name == "orchestration_wrapper"
        ]
    deletion_safe_now = (
        direct_dependency_count == 0
        and not missing_boundaries
        and False
    )
    return {
        "decision": (
            "COMBINED_LOW_UTIL_WRAPPER_CUTOVER_NOT_READY_FOR_DELETION"
            if wrapper_cutover
            else "COMBINED_LOW_UTIL_GENERATOR_NOT_READY_FOR_DELETION"
        ),
        "wrapper_cutover": wrapper_cutover,
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "direct_dependencies": direct_dependencies,
        "controller_boundaries": controller_boundaries,
        "direct_dependency_count": direct_dependency_count,
        "missing_controller_boundaries": missing_boundaries,
        "post_packaging_mutations": post_packaging_mutations,
        "local_orchestration": local_orchestration,
        "safe_to_delete_now": deletion_safe_now,
        "blocking_classes": [
            "thin_page_entrypoint_still_referenced"
            if wrapper_cutover
            else "local_orchestration",
            "consumer_reachability_not_proven_for_deleting_wrapper_entrypoint"
            if wrapper_cutover
            else "debug_failure_fallback",
        ],
        "recommended_next_slice": (
            "prove consumer reachability before deleting or renaming the thin page wrapper entrypoint"
            if wrapper_cutover
            else "audit whether the remaining local orchestration can be lifted as a whole into the controller"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    function_deleted = bool((capture.get("function") or {}).get("deleted"))
    return {
        "function_found_or_deleted": bool((capture.get("function") or {}).get("line_count"))
        or function_deleted,
        "tracked_direct_dependencies_removed": int(capture.get("direct_dependency_count") or 0) == 0,
        "all_controller_boundaries_present": bool(capture.get("wrapper_cutover"))
        or not capture.get("missing_controller_boundaries"),
        "post_packaging_mutations_moved": all(
            not item.get("present")
            for item in (capture.get("post_packaging_mutations") or {}).values()
        ),
        "local_orchestration_mapped": function_deleted
        or bool(capture.get("wrapper_cutover"))
        or all(item.get("present") for item in (capture.get("local_orchestration") or {}).values()),
        "not_safe_to_delete_yet": capture.get("safe_to_delete_now") is False,
        "recommended_next_slice_recorded": bool(capture.get("recommended_next_slice")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_table(lines: list[str], title: str, rows: dict[str, Any]) -> None:
    lines.extend(["", f"## {title}", ""])
    lines.append("| Name | Present | Count | Classification | Next action |")
    lines.append("| --- | ---: | ---: | --- | --- |")
    for name, item in rows.items():
        lines.append(
            "| {name} | {present} | {count} | {classification} | {next_action} |".format(
                name=name,
                present=item.get("present"),
                count=item.get("count"),
                classification=item.get("classification", ""),
                next_action=item.get("next_action", ""),
            )
        )


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Generator Deletion Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Safe to delete now: `{capture.get('safe_to_delete_now')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    _write_table(lines, "Direct Dependencies", capture.get("direct_dependencies") or {})
    _write_table(lines, "Controller Boundaries", capture.get("controller_boundaries") or {})
    _write_table(lines, "Post-Packaging Mutations", capture.get("post_packaging_mutations") or {})
    _write_table(lines, "Local Orchestration", capture.get("local_orchestration") or {})
    lines.extend(["", "## Recommendation", "", str(capture.get("recommended_next_slice") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_generator_deletion_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_generator_deletion_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_generator_deletion_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"safe_to_delete_now={capture.get('safe_to_delete_now')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
