"""Focused parity scenarios for the controller compute handoff trace.

This verifier proves the new DesignGuideController compute handoff response is
stable and aligned with the same scenario surface already used by the compute
handoff/rebound proof. It is proof-only and does not replace the live resolver.
"""

from __future__ import annotations

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
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not matches:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = matches[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _controller_request(case: dict[str, Any]) -> dict[str, Any]:
    proof_inputs = _proof_inputs(case)
    item = dict(case["item"])
    debug = {
        "candidate_search_evidence": dict(item.get("candidate_search_evidence") or {}),
        "post_click_design_guide_state": item.get("post_click_design_guide_state"),
        "stale_fresh_proof": dict(item.get("stale_fresh_proof") or {}),
        "design_brain_result": {
            "selected_family": item.get("selected_family_id") or item.get("family"),
            "outcome_state": item.get("status"),
        },
    }
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
        "publication_context": {"scenario": case["name"], "source": "controller_parity_scenarios"},
        "publication_dependencies": {"scenario": case["name"], "source": "controller_parity_scenarios"},
        "final_compute_resolution": {
            "item": dict(item),
            "render_reason": case["render_reason"],
            "state_fingerprint": proof_inputs["state_fingerprint"],
        },
        "late_evidence_acceptance": dict(case.get("late_acceptance") or {}),
        "rebound_contract": dict(case.get("rebound_contract") or {}),
        "rebound_update_payload": dict((case.get("rebound_contract") or {}).get("updates") or {}),
        "post_core_evidence_mismatch": dict(case.get("post_core_mismatch") or {}),
        "pre_resolver_collapsed_item_mutation": dict(proof_inputs["pre_resolver_collapsed_item_mutation"]),
        "debug": debug,
        "verifier_payload": {"scenario": case["name"], "source": "controller_parity_scenarios"},
        "publication_reason": case["render_reason"],
        "source": "controller_compute_handoff_parity_scenarios",
    }


def _scenario_result(case: dict[str, Any]) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_compute_publication_handoff_trace_only,
    )

    request = _controller_request(case)
    first = run_design_guide_controller_compute_publication_handoff_trace_only(request)
    second = run_design_guide_controller_compute_publication_handoff_trace_only(request)
    item = dict(case["item"])
    proof = dict(first.compute_handoff_rebound_decision_proof or {})
    publication = dict(first.publication or {})
    evidence = dict(publication.get("evidence") or {})
    field_hashes = dict(proof.get("field_hashes") or {})
    expected_selected_hash = _stable_hash(item)
    expected_updates = dict((case.get("rebound_contract") or {}).get("updates") or {})
    update_hash = _stable_hash(expected_updates)
    mismatches: list[str] = []

    if first.request_hash != second.request_hash:
        mismatches.append("request_hash_unstable")
    if first.controller_hash != second.controller_hash:
        mismatches.append("controller_hash_unstable")
    if first.publication_hash != second.publication_hash:
        mismatches.append("publication_hash_unstable")
    if first.compute_handoff_rebound_decision_hash != second.compute_handoff_rebound_decision_hash:
        mismatches.append("compute_handoff_decision_hash_unstable")
    if first.selected_item_hash != expected_selected_hash:
        mismatches.append("selected_item_hash_mismatch")
    if publication.get("selected_family") != item.get("selected_family_id"):
        mismatches.append("publication_selected_family_mismatch")
    if publication.get("publication_reason") != case["render_reason"]:
        mismatches.append("publication_reason_mismatch")
    if proof.get("missing_blocking_fields"):
        mismatches.append("missing_blocking_fields")
    if len(field_hashes) != 9:
        mismatches.append("field_hash_count_mismatch")
    if (
        proof.get("rebound_update_payload_summary", {}).get("update_hash")
        != update_hash
    ):
        mismatches.append("rebound_update_hash_mismatch")
    if evidence.get("compute_publication_evidence_hash") is None:
        mismatches.append("publication_missing_compute_evidence_hash")
    if first.product_driving or first.render_driving or first.apply_driving or first.session_driving:
        mismatches.append("controller_trace_drives_product_surface")

    return {
        "scenario": case["name"],
        "status": "PASS" if not mismatches else "FAIL",
        "mismatches": mismatches,
        "request_hash": first.request_hash,
        "controller_hash": first.controller_hash,
        "publication_hash": first.publication_hash,
        "selected_item_hash": first.selected_item_hash,
        "final_visible_resolution_hash": first.final_visible_resolution_hash,
        "compute_handoff_rebound_decision_hash": first.compute_handoff_rebound_decision_hash,
        "stable_hashes": (
            first.request_hash == second.request_hash
            and first.controller_hash == second.controller_hash
            and first.publication_hash == second.publication_hash
            and first.compute_handoff_rebound_decision_hash
            == second.compute_handoff_rebound_decision_hash
        ),
        "selected_item_hash_matches_live_item": first.selected_item_hash == expected_selected_hash,
        "publication_selected_family_matches": publication.get("selected_family") == item.get("selected_family_id"),
        "publication_reason_matches": publication.get("publication_reason") == case["render_reason"],
        "all_9_blocking_field_hashes_present": len(field_hashes) == 9 and not proof.get("missing_blocking_fields"),
        "rebound_update_hash_matches": (
            proof.get("rebound_update_payload_summary", {}).get("update_hash") == update_hash
        ),
        "trace_only_not_product_driving": (
            first.trace_only
            and not first.product_driving
            and not first.render_driving
            and not first.apply_driving
            and not first.session_driving
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Live Controller Compute Handoff Parity Scenarios",
        "",
        f"Status: `{payload['status']}`",
        f"Snapshot hash: `{payload['snapshot_hash']}`",
        "",
        "## Summary",
        "",
        f"- Scenario count: `{len(payload['scenarios'])}`",
        f"- All scenarios passed: `{payload['all_scenarios_passed']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        f"- Resolver replaced: `{payload['resolver_replaced']}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status | Stable | Selected | Family | Reason | Fields | Update | Trace only | Mismatches |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            "| {scenario} | `{status}` | `{stable}` | `{selected}` | `{family}` | `{reason}` | `{fields}` | `{update}` | `{trace}` | {mismatch} |".format(
                scenario=row["scenario"],
                status=row["status"],
                stable=row["stable_hashes"],
                selected=row["selected_item_hash_matches_live_item"],
                family=row["publication_selected_family_matches"],
                reason=row["publication_reason_matches"],
                fields=row["all_9_blocking_field_hashes_present"],
                update=row["rebound_update_hash_matches"],
                trace=row["trace_only_not_product_driving"],
                mismatch=", ".join(row["mismatches"]) or "none",
            )
        )
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommended_next_slice"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    live_trace = _latest("design_guide_live_controller_compute_handoff_trace")
    scenario_results = [_scenario_result(case) for case in _scenarios()]
    names = [row["scenario"] for row in scenario_results]
    failures: list[str] = []
    if names != list(SCENARIO_NAMES):
        failures.append("scenario_coverage_mismatch")
    if not live_trace.get("passed"):
        failures.append("live_controller_compute_handoff_trace_not_passed")
    if any(row["status"] != "PASS" for row in scenario_results):
        failures.append("controller_scenario_parity_mismatch")
    payload = {
        "schema": "design_guide_live_controller_compute_handoff_parity_scenarios.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "scenarios": scenario_results,
        "all_scenarios_passed": all(row["status"] == "PASS" for row in scenario_results),
        "source_live_trace_artifact": live_trace.get("path"),
        "live_trace_passed": bool(live_trace.get("passed")),
        "resolver_replaced": False,
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(
            {
                "scenario_results": [
                    {
                        "scenario": row["scenario"],
                        "request_hash": row["request_hash"],
                        "controller_hash": row["controller_hash"],
                        "publication_hash": row["publication_hash"],
                        "decision_hash": row["compute_handoff_rebound_decision_hash"],
                        "mismatches": row["mismatches"],
                    }
                    for row in scenario_results
                ],
                "resolver_replaced": False,
                "product_behavior_changed": False,
            }
        ),
        "recommended_next_slice": (
            "If this remains PASS, create a replacement-readiness snapshot for the compute-stage "
            "resolver call. Do not replace the resolver until the readiness snapshot proves the "
            "controller trace covers the live browser/post-click/stale cases."
        ),
    }
    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_live_controller_compute_handoff_parity_scenarios_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_controller_compute_handoff_parity_scenarios_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)
    print(f"design_guide_live_controller_compute_handoff_parity_scenarios {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
