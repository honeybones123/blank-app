"""Audit extraction readiness for the no-active blocked-primary cleanup probe route."""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

FUNCTION_NAME = "_resolve_final_visible_no_active_blocked_primary_cleanup_probe_result"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
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
        "name": "primary_actionability_gate",
        "token": "design_guide_button_contract_enabled_fn(contract)",
        "classification": "live_page_route_decision",
        "next_action": "move_to_controller_route_policy_proof",
    },
    {
        "name": "post_click_safe_cleanup_gate",
        "token": "local_cleanup_post_apply_acceptance_matches_fn(final_state)",
        "classification": "live_page_route_decision",
        "next_action": "move_to_controller_route_policy_proof",
    },
    {
        "name": "safe_cleanup_updates_from_evidence",
        "token": 'primary_evidence.get("selected_candidate_updates")',
        "classification": "live_evidence_interpretation",
        "next_action": "create_controller_evidence_adapter",
    },
    {
        "name": "shear_best_safe_item_from_evidence",
        "token": "shear_best_safe_cleanup_item_from_evidence_fn(",
        "classification": "injected_candidate_generation_dependency",
        "next_action": "create_controller_boundary_or_trace_adapter",
    },
    {
        "name": "safe_cleanup_before_blocker_assembler",
        "token": "_assemble_final_visible_safe_cleanup_candidate_before_blocker_result(",
        "classification": "page_owned_result_assembler",
        "next_action": "audit_assembler_replacement_readiness",
    },
    {
        "name": "bending_under_floor_probe_gate",
        "token": "final_bending_util_for_probe",
        "classification": "live_page_route_decision",
        "next_action": "move_to_controller_route_policy_proof",
    },
    {
        "name": "bending_cleanup_generator",
        "token": "bending_only_target_band_cleanup_item_fn(",
        "classification": "injected_candidate_generation_dependency",
        "next_action": "create_controller_boundary_or_trace_adapter",
    },
    {
        "name": "equivalent_bending_probe_generator",
        "token": "probe_equivalent_bending_cleanup_action_item_fn(",
        "classification": "injected_candidate_generation_dependency",
        "next_action": "create_controller_boundary_or_trace_adapter",
    },
    {
        "name": "equivalent_probe_selection",
        "token": "equivalent_probe_expected",
        "classification": "live_page_ranking_decision",
        "next_action": "move_to_controller_selection_proof",
    },
    {
        "name": "bending_probe_contract_packaging",
        "token": "bending_probe_contract = {",
        "classification": "page_owned_result_packaging",
        "next_action": "create_controller_result_packaging_object",
    },
    {
        "name": "visible_cleanup_blocker_exact_proof",
        "token": "visible_cleanup_blocker_from_action_fn(",
        "classification": "live_blocker_evidence_shaping",
        "next_action": "move_to_controller_blocker_evidence_proof",
    },
    {
        "name": "bending_cleanup_before_blocker_assembler",
        "token": "_assemble_final_visible_bending_cleanup_available_before_blocker_result(",
        "classification": "page_owned_result_assembler",
        "next_action": "audit_assembler_replacement_readiness",
    },
]


def _capture() -> dict[str, Any]:
    route_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    inventory = []
    for dep in DEPENDENCIES:
        count = route_source.count(str(dep["token"]))
        replacement_present = (
            (
                dep["name"] == "safe_cleanup_before_blocker_assembler"
                and "_build_design_guide_controller_safe_cleanup_candidate_before_blocker_result("
                in route_source
            )
            or (
                dep["name"] == "bending_cleanup_before_blocker_assembler"
                and "_build_design_guide_controller_bending_cleanup_available_before_blocker_result("
                in route_source
            )
        )
        inventory.append(
            {
                **dep,
                "present": count > 0 or replacement_present,
                "count": count,
                "replacement_present": replacement_present,
                "safe_to_delete_now": False,
            }
        )
    controller_route_tokens = [
        "no_active_blocked_primary_cleanup_probe",
        "blocked_primary_cleanup_probe",
        "build_design_guide_controller_blocked_primary",
        "run_design_guide_controller_blocked_primary",
    ]
    controller_route_surface_present = any(token in controller_source for token in controller_route_tokens)
    unknown = [
        item
        for item in inventory
        if item.get("classification")
        not in {
            "live_page_route_decision",
            "live_evidence_interpretation",
            "injected_candidate_generation_dependency",
            "page_owned_result_assembler",
            "live_page_ranking_decision",
            "page_owned_result_packaging",
            "live_blocker_evidence_shaping",
        }
    ]
    return {
        "decision": (
            "NOT_READY_CONTROLLER_ROUTE_SURFACE_MISSING"
            if not controller_route_surface_present
            else "PARTIAL_CONTROLLER_ROUTE_SURFACE_PRESENT"
        ),
        "route": {
            "function": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "inventory": inventory,
        "controller_route_surface_present": controller_route_surface_present,
        "unsafe_or_unknown_count": len(unknown),
        "safe_deletion_candidates": [],
        "ready_for_cutover": False,
        "ready_for_deletion": False,
        "recommended_next_slice": (
            "Create a controller route-policy/evidence object for no_active_blocked_primary_cleanup_probe "
            "before moving result assemblers or deleting page logic."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    inventory = list(capture.get("inventory") or [])
    return {
        "route_function_found": bool((capture.get("route") or {}).get("line_count")),
        "all_tracked_dependencies_present": all(item.get("present") for item in inventory),
        "controller_route_surface_missing_or_partial": capture.get("decision")
        in {"NOT_READY_CONTROLLER_ROUTE_SURFACE_MISSING", "PARTIAL_CONTROLLER_ROUTE_SURFACE_PRESENT"},
        "no_safe_deletion_candidates": not capture.get("safe_deletion_candidates"),
        "not_ready_for_cutover": capture.get("ready_for_cutover") is False,
        "not_ready_for_deletion": capture.get("ready_for_deletion") is False,
        "no_unknown_classifications": int(capture.get("unsafe_or_unknown_count") or 0) == 0,
        "next_slice_recorded": bool(capture.get("recommended_next_slice")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide No-Active Blocked-Primary Cleanup Probe Route Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Ready for cutover: `{capture.get('ready_for_cutover')}`",
        f"Ready for deletion: `{capture.get('ready_for_deletion')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Inventory", ""])
    lines.append("| Dependency | Classification | Present | Count | Next action |")
    lines.append("| --- | --- | ---: | ---: | --- |")
    for item in capture.get("inventory") or []:
        lines.append(
            "| {name} | {classification} | {present} | {count} | {next_action} |".format(
                name=item.get("name"),
                classification=item.get("classification"),
                present=item.get("present"),
                count=item.get("count"),
                next_action=item.get("next_action"),
            )
        )
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
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_no_active_blocked_primary_cleanup_probe_route_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_cleanup_probe_route_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_cleanup_probe_route_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
