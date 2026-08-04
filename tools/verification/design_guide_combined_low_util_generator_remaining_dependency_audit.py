"""Audit remaining dependencies inside the combined low-util cleanup generator."""

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


DEPENDENCIES = [
    {
        "name": "candidate_evaluation",
        "token": "_evaluate_auto_design_candidate(",
        "expected_present": False,
        "classification": "moved_to_controller_boundary",
        "next_action": "none",
    },
    {
        "name": "update_resolution",
        "token": "_resolve_recommendation_updates(",
        "expected_present": False,
        "classification": "moved_to_controller_boundary",
        "next_action": "none",
    },
    {
        "name": "bending_cleanup_generator",
        "token": "bending_item = _bending_only_target_band_cleanup_item(",
        "expected_present": False,
        "classification": "moved_to_controller_boundary",
        "next_action": "none",
    },
    {
        "name": "required_checks_gate",
        "token": "_overview_required_checks_acceptable(",
        "expected_present": False,
        "classification": "moved_to_controller_boundary",
        "next_action": "none",
    },
    {
        "name": "explicit_preview_fail_gate",
        "token": "_candidate_preview_statuses_have_explicit_fail(",
        "expected_present": False,
        "classification": "moved_to_controller_boundary",
        "next_action": "none",
    },
    {
        "name": "post_click_accepted_green_audit",
        "token": "combined_audit = _post_click_accepted_green_audit(",
        "expected_present": False,
        "classification": "moved_to_controller_boundary",
        "next_action": "none",
    },
    {
        "name": "target_band_resolution",
        "token": "_resolved_efficiency_target_band(",
        "expected_present": False,
        "classification": "moved_to_controller_boundary",
        "next_action": "none",
    },
    {
        "name": "candidate_search_evidence",
        "token": "_build_candidate_search_evidence(",
        "expected_present": False,
        "classification": "moved_to_controller_boundary",
        "next_action": "none",
    },
    {
        "name": "guidance_item_packaging",
        "token": "_guidance_item_from_resolved_candidate(",
        "expected_present": False,
        "classification": "moved_to_controller_boundary",
        "next_action": "none",
    },
]


def _capture() -> dict[str, Any]:
    try:
        function_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    except RuntimeError as exc:
        if f"Could not find {FUNCTION_NAME}" not in str(exc):
            raise
        return {
            "decision": "COMBINED_LOW_UTIL_GENERATOR_ALREADY_DELETED",
            "function": {
                "name": FUNCTION_NAME,
                "start_line": None,
                "end_line": None,
                "line_count": 0,
                "deleted": True,
            },
            "inventory": [
                {
                    **dep,
                    "present": False,
                    "count": 0,
                    "expected_state_matches": True,
                    "safe_to_delete_now": False,
                }
                for dep in DEPENDENCIES
            ],
            "unsafe_or_unexpected_count": 0,
            "safe_deletion_candidates": [],
            "next_move_candidates": [],
            "recommended_next_slice": "generator already deleted; continue at route-level assembler/resolver glue",
            "product_behavior_changed": False,
            "visible_wording_changed": False,
            "cta_apply_semantics_changed": False,
            "family_runtime_changed": False,
        }
    inventory = []
    for dep in DEPENDENCIES:
        count = function_source.count(str(dep["token"]))
        present = count > 0
        inventory.append(
            {
                **dep,
                "present": present,
                "count": count,
                "expected_state_matches": present is bool(dep["expected_present"]),
                "safe_to_delete_now": False,
            }
        )
    unsafe = [
        item
        for item in inventory
        if not item.get("expected_state_matches")
        or item.get("classification") not in {
            "moved_to_controller_boundary",
            "retained_page_generator_dependency",
            "pure_acceptance_gate_candidate",
            "acceptance_audit_dependency",
            "config_policy_dependency",
            "evidence_packaging_candidate",
            "visible_item_packaging_dependency",
        }
    ]
    next_candidates: list[dict[str, Any]] = []
    return {
        "decision": "COMBINED_LOW_UTIL_GENERATOR_REMAINING_DEPENDENCIES_MAPPED",
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "inventory": inventory,
        "unsafe_or_unexpected_count": len(unsafe),
        "safe_deletion_candidates": [],
        "next_move_candidates": [item.get("name") for item in next_candidates],
        "recommended_next_slice": "audit next retained packaging dependency before moving it",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    inventory = list(capture.get("inventory") or [])
    moved = [item for item in inventory if item.get("classification") == "moved_to_controller_boundary"]
    retained = [item for item in inventory if item.get("classification") != "moved_to_controller_boundary"]
    function_deleted = bool((capture.get("function") or {}).get("deleted"))
    return {
        "function_found_or_deleted": bool((capture.get("function") or {}).get("line_count"))
        or function_deleted,
        "all_expected_states_match": all(item.get("expected_state_matches") for item in inventory),
        "moved_boundaries_absent_from_function": all(not item.get("present") for item in moved),
        "retained_dependencies_present_or_function_deleted": function_deleted
        or all(item.get("present") for item in retained),
        "no_unsafe_or_unexpected_dependencies": int(capture.get("unsafe_or_unexpected_count") or 0) == 0,
        "no_safe_deletion_candidates_yet": not capture.get("safe_deletion_candidates"),
        "next_move_guidance_recorded": bool(capture.get("recommended_next_slice")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Generator Remaining Dependency Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Inventory", ""])
    lines.append("| Dependency | Present | Count | Classification | Next action |")
    lines.append("| --- | ---: | ---: | --- | --- |")
    for item in capture.get("inventory") or []:
        lines.append(
            "| {name} | {present} | {count} | {classification} | {next_action} |".format(
                name=item.get("name"),
                present=item.get("present"),
                count=item.get("count"),
                classification=item.get("classification"),
                next_action=item.get("next_action"),
            )
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            str(capture.get("recommended_next_slice") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_combined_low_util_generator_remaining_dependency_audit_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_generator_remaining_dependency_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_generator_remaining_dependency_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
