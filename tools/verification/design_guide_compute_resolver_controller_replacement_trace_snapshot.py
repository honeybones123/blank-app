"""Proof-only controller replacement trace for the compute resolver bridge.

This verifier proves DesignGuideController can compose compute selection and
compute publication handoff/rebound proof without being fed the old
resolve_final_visible_design_guide_item(...) output. It does not replace the
live resolver or delete compute helpers.
"""

from __future__ import annotations

from datetime import datetime
import ast
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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
INPUTS_PAGE = ROOT / "inputs_page.py"

from tools.verification.design_guide_live_compute_publication_handoff_rebound_parity_scenarios import (  # noqa: E402
    SCENARIO_NAMES,
    _proof_inputs,
    _scenarios,
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "payload": {}}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "payload": payload,
    }


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return "\n".join(lines[node.lineno - 1 : int(getattr(node, "end_lineno", node.lineno))])
    return ""


def _request_without_old_resolver(case: dict[str, Any]) -> dict[str, Any]:
    proof_inputs = _proof_inputs(case)
    item = dict(case["item"])
    return {
        "current_state": {
            "scenario": case["name"],
            "family": item.get("family"),
            "candidate_id": item.get("candidate_id"),
        },
        "overview": {
            "scenario": case["name"],
            "any_fail": item.get("status") in {"ACTION", "BLOCKED"},
            "worst_util": 1.0 if item.get("status") in {"ACTION", "BLOCKED"} else 0.9,
        },
        "collapsed_guidance_items": [dict(item)],
        "publication_context": {"scenario": case["name"], "source": "controller_replacement_trace"},
        "publication_dependencies": {"scenario": case["name"], "source": "controller_replacement_trace"},
        "blocker_evidence_surface": dict(proof_inputs.get("blocker_evidence_surface") or {}),
        "late_evidence_acceptance": dict(case.get("late_acceptance") or {}),
        "rebound_contract": dict(case.get("rebound_contract") or {}),
        "rebound_update_payload": dict((case.get("rebound_contract") or {}).get("updates") or {}),
        "post_core_evidence_mismatch": dict(case.get("post_core_mismatch") or {}),
        "pre_resolver_collapsed_item_mutation": dict(proof_inputs["pre_resolver_collapsed_item_mutation"]),
        "debug": {
            "candidate_search_evidence": dict(item.get("candidate_search_evidence") or {}),
            "post_click_design_guide_state": item.get("post_click_design_guide_state"),
            "design_brain_result": {
                "selected_family": item.get("selected_family_id") or item.get("family"),
                "outcome_state": item.get("status"),
            },
        },
        "verifier_payload": {"scenario": case["name"], "source": "controller_replacement_trace"},
        "publication_reason": case["render_reason"],
        "source": "controller_compute_resolver_replacement_trace_scenarios",
    }


def _scenario_result(case: dict[str, Any]) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_compute_resolver_replacement_trace_only,
    )

    request = _request_without_old_resolver(case)
    first = run_design_guide_controller_compute_resolver_replacement_trace_only(request)
    second = run_design_guide_controller_compute_resolver_replacement_trace_only(request)
    item = dict(case["item"])
    handoff = dict(first.handoff or {})
    proof = dict(handoff.get("compute_handoff_rebound_decision_proof") or {})
    final_resolution = dict(first.final_compute_resolution or {})
    expected_updates = dict((case.get("rebound_contract") or {}).get("updates") or {})
    mismatches: list[str] = []
    if first.request_hash != second.request_hash:
        mismatches.append("request_hash_unstable")
    if first.controller_hash != second.controller_hash:
        mismatches.append("controller_hash_unstable")
    if first.final_compute_resolution_hash != second.final_compute_resolution_hash:
        mismatches.append("final_compute_resolution_hash_unstable")
    if first.compute_handoff_rebound_decision_hash != second.compute_handoff_rebound_decision_hash:
        mismatches.append("decision_hash_unstable")
    if first.selection.get("selected_item_hash") != _stable_hash(item):
        mismatches.append("selection_item_hash_mismatch")
    if final_resolution.get("item") != item:
        mismatches.append("final_resolution_item_mismatch")
    if final_resolution.get("render_reason") != case["render_reason"]:
        mismatches.append("render_reason_mismatch")
    if final_resolution.get("old_resolver_input_required") is not False:
        mismatches.append("old_resolver_input_required")
    if proof.get("missing_blocking_fields"):
        mismatches.append("missing_blocking_fields")
    if len(dict(proof.get("field_hashes") or {})) != 9:
        mismatches.append("field_hash_count_mismatch")
    if dict(proof.get("rebound_update_payload_summary") or {}).get("update_hash") != _stable_hash(
        expected_updates
    ):
        mismatches.append("rebound_update_hash_mismatch")
    if not (
        first.trace_only
        and not first.product_driving
        and not first.render_driving
        and not first.apply_driving
        and not first.session_driving
    ):
        mismatches.append("replacement_trace_drives_product_surface")
    return {
        "scenario": case["name"],
        "status": "PASS" if not mismatches else "FAIL",
        "mismatches": mismatches,
        "request_hash": first.request_hash,
        "controller_hash": first.controller_hash,
        "final_compute_resolution_hash": first.final_compute_resolution_hash,
        "decision_hash": first.compute_handoff_rebound_decision_hash,
        "selected_item_matches": final_resolution.get("item") == item,
        "render_reason_matches": final_resolution.get("render_reason") == case["render_reason"],
        "all_9_blocking_fields_present": len(dict(proof.get("field_hashes") or {})) == 9
        and not proof.get("missing_blocking_fields"),
        "old_resolver_input_required": final_resolution.get("old_resolver_input_required"),
        "trace_only_not_product_driving": (
            first.trace_only
            and not first.product_driving
            and not first.render_driving
            and not first.apply_driving
            and not first.session_driving
        ),
    }


def _build_payload() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    function_source = _function_source(
        CONTROLLER, "run_design_guide_controller_compute_resolver_replacement_trace_only"
    )
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    scenarios = [_scenario_result(case) for case in _scenarios()]
    failures: list[str] = []
    if [row["scenario"] for row in scenarios] != list(SCENARIO_NAMES):
        failures.append("scenario_coverage_mismatch")
    if any(row["status"] != "PASS" for row in scenarios):
        failures.append("scenario_replacement_trace_mismatch")
    source_guards = {
        "replacement_function_exists": bool(function_source),
        "replacement_function_does_not_call_old_resolver": "resolve_final_visible_design_guide_item(" not in function_source,
        "replacement_function_does_not_read_old_request_resolution": "request_obj.final_compute_resolution" not in function_source,
        "product_path_still_has_old_resolver_call": "final_compute_resolution = resolve_final_visible_design_guide_item(" in inputs_source,
        "product_path_has_trace_wiring": "_run_design_guide_controller_compute_resolver_replacement_trace_only(" in inputs_source,
        "product_path_not_replaced_by_controller": "final_compute_resolution = _run_design_guide_controller_compute_resolver_replacement_trace_only(" not in inputs_source,
    }
    if not all(source_guards.values()):
        failures.append("source_guard_failed")
    latest = {
        "compute_stage_resolver_deletion_readiness": _latest(
            "design_guide_compute_stage_resolver_deletion_readiness"
        ),
        "remaining_compatibility_helper_deletion_readiness": _latest(
            "design_guide_remaining_compatibility_helper_deletion_readiness"
        ),
    }
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "failures": failures,
        "summary": {
            "scenario_count": len(scenarios),
            "all_scenarios_passed": all(row["status"] == "PASS" for row in scenarios),
            "old_resolver_input_required": False,
            "product_path_cut_over": False,
            "product_behavior_changed": False,
        },
        "source_guards": source_guards,
        "scenarios": scenarios,
        "latest_artifacts": latest,
        "next_safe_step": (
            "Trace-wire run_design_guide_controller_compute_resolver_replacement_trace_only beside the "
            "current compute resolver call in inputs_page.py. Do not replace the live resolver until the "
            "live trace proves parity in product state."
        ),
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "summary": payload["summary"],
            "source_guards": source_guards,
            "scenarios": [
                {
                    "scenario": row["scenario"],
                    "controller_hash": row["controller_hash"],
                    "final_compute_resolution_hash": row["final_compute_resolution_hash"],
                    "decision_hash": row["decision_hash"],
                    "mismatches": row["mismatches"],
                }
                for row in scenarios
            ],
        }
    )
    return payload


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Compute Resolver Controller Replacement Trace Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Snapshot hash: `{payload['snapshot_hash']}`",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in payload["summary"].items())
    lines.extend(
        [
            "",
            "## Source Guards",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in payload["source_guards"].items())
    lines.extend(
        [
            "",
            "## Scenarios",
            "",
            "| Scenario | Status | Selected | Reason | Fields | Old Resolver Input | Trace Only | Mismatches |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["scenarios"]:
        lines.append(
            "| {scenario} | `{status}` | `{selected}` | `{reason}` | `{fields}` | `{old}` | `{trace}` | {mismatches} |".format(
                scenario=row["scenario"],
                status=row["status"],
                selected=row["selected_item_matches"],
                reason=row["render_reason_matches"],
                fields=row["all_9_blocking_fields_present"],
                old=row["old_resolver_input_required"],
                trace=row["trace_only_not_product_driving"],
                mismatches=", ".join(row["mismatches"]) or "none",
            )
        )
    lines.extend(["", "## Next Safe Step", "", payload["next_safe_step"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    stamp = payload["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_resolver_controller_replacement_trace_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_resolver_controller_replacement_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_guide_compute_resolver_controller_replacement_trace {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload["failures"]:
        print("failures=" + json.dumps(payload["failures"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
