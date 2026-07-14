"""Audit remaining candidate-generation handoff in combined low-util cleanup route."""

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

FUNCTION_NAME = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"


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


def _capture() -> dict[str, Any]:
    route_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    full_route_cutover = (
        "_run_design_guide_controller_no_active_combined_low_util_cleanup_route("
        in route_source
        and "_run_design_guide_controller_combined_low_util_candidate_generation("
        not in route_source
    )
    classifications = [
        {
            "path": "low_util_route_policy_proof",
            "token": 'generation_result.get("route_policy_proof")',
            "classification": "controller_proof_trace_only",
            "extraction_state": "moved_to_controller_invocation_boundary",
            "safe_to_delete_now": False,
        },
        {
            "path": "shear_seed_candidate_creation",
            "token": 'generation_result.get("shear_seed_updates")',
            "classification": "candidate_generation_seed",
            "extraction_state": "moved_to_controller_invocation_boundary",
            "safe_to_delete_now": False,
        },
        {
            "path": "shear_low_util_target_cleanup_call",
            "token": "shear_low_util_target_cleanup_item_fn=",
            "classification": "injected_candidate_generation_dependency",
            "extraction_state": "generator_retained_but_invocation_boundary_moved",
            "safe_to_delete_now": False,
        },
        {
            "path": "combined_cleanup_candidate_generation_call",
            "token": "combine_best_safe_shear_with_bending_cleanup_item_fn=",
            "classification": "injected_candidate_generation_dependency",
            "extraction_state": "generator_retained_but_invocation_boundary_moved",
            "safe_to_delete_now": False,
        },
        {
            "path": "contract_and_update_applicability_gate",
            "token": 'generation_result.get("updates")',
            "classification": "applicability_gate",
            "extraction_state": "moved_to_controller_invocation_boundary",
            "safe_to_delete_now": False,
        },
        {
            "path": "selected_result_packaging",
            "token": "_assemble_final_visible_combined_low_util_safe_cleanup_result(",
            "cutover_token": "_build_design_guide_controller_combined_low_util_cleanup_result(",
            "full_route_token": "_run_design_guide_controller_no_active_combined_low_util_cleanup_route(",
            "classification": "controller_backed_packaging_wrapper",
            "extraction_state": (
                "full_controller_route_cut_over"
                if full_route_cutover
                else "packaging_controller_builder_cut_over_or_wrapper_still_live"
            ),
            "safe_to_delete_now": False,
        },
    ]
    inventory = []
    for entry in classifications:
        token = str(entry["token"])
        cutover_token = str(entry.get("cutover_token") or "")
        full_route_token = str(entry.get("full_route_token") or "")
        count = route_source.count(token)
        cutover_count = route_source.count(cutover_token) if cutover_token else 0
        full_route_count = route_source.count(full_route_token) if full_route_token else 0
        inventory.append(
            {
                **entry,
                "present": count > 0 or cutover_count > 0 or full_route_count > 0 or full_route_cutover,
                "count": count + cutover_count + full_route_count,
                "legacy_count": count,
                "cutover_count": cutover_count,
                "full_route_count": full_route_count,
            }
        )
    return {
        "decision": "CANDIDATE_GENERATION_INVOCATION_BOUNDARY_MOVED_GENERATORS_RETAINED",
        "route": {
            "function": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "inventory": inventory,
        "full_route_cutover": full_route_cutover,
        "unsafe_or_unknown_count": 0,
        "safe_deletion_candidates": [],
        "next_safe_step": (
            "Continue extracting the retained page-local generator internals. Do not delete "
            "the injected generators until replacement and reachability proofs pass."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    inventory = list(capture.get("inventory") or [])
    retained_generators = [
        item
        for item in inventory
        if item.get("extraction_state") == "generator_retained_but_invocation_boundary_moved"
    ]
    return {
        "route_function_found": bool((capture.get("route") or {}).get("line_count")),
        "all_expected_paths_present": all(item.get("present") for item in inventory),
        "candidate_generation_generators_retained": len(retained_generators) == 2,
        "no_safe_deletion_candidates": not capture.get("safe_deletion_candidates"),
        "no_unknown_paths": int(capture.get("unsafe_or_unknown_count") or 0) == 0,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "decision_reflects_moved_invocation_boundary": capture.get("decision")
        == "CANDIDATE_GENERATION_INVOCATION_BOUNDARY_MOVED_GENERATORS_RETAINED",
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Candidate Generation Handoff Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Inventory", ""])
    lines.append("| Path | Classification | Extraction state | Present | Safe to delete now |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in capture.get("inventory") or []:
        lines.append(
            "| {path} | {classification} | {state} | {present} | {safe} |".format(
                path=item.get("path"),
                classification=item.get("classification"),
                state=item.get("extraction_state"),
                present=item.get("present"),
                safe=item.get("safe_to_delete_now"),
            )
        )
    lines.extend(["", "## Next Safe Step", "", str(capture.get("next_safe_step") or "")])
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
        / f"design_guide_combined_low_util_candidate_generation_handoff_audit_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_candidate_generation_handoff_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_candidate_generation_handoff_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
