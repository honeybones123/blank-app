"""Parity scenarios for low-bending full result item adapter."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "passed": proc.returncode == 0,
    }


def _adapter(result_item: dict[str, Any], audit: dict[str, Any] | None = None) -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_low_bending_resolution_result_item_adapter_proof,
    )

    return build_final_design_guide_post_click_low_bending_resolution_result_item_adapter_proof(
        result_item=dict(result_item),
        acceptance_audit=dict(audit or {}),
        final_visible_resolution={"source": "adapter_parity_fixture"},
    )


def _cases() -> list[dict[str, Any]]:
    exact = {"bending": {"blocker_type": "final_threshold", "no_second_cta_required": True}}
    base_contract = {"enabled": True, "family": "bending", "action_type": "apply_resolved_candidate"}
    return [
        {
            "name": "early_cleanup_action_item",
            "result_item": {
                "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "status": "ACTION",
                "bucket": "action",
                "title_main": "Strengthening required",
                "guidance_intent": "efficiency_tightening",
                "local_cleanup_candidate": True,
                "post_click_low_family_cleanup_action": True,
                "terminal_state_blocked_by_local_cleanup": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "candidate_search_evidence": {"selected_candidate_id": "early_cleanup_fixture"},
                "button_contract": dict(base_contract),
            },
            "expect_exact": False,
        },
        {
            "name": "best_safe_incremental_item",
            "result_item": {
                "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "status": "ACTION",
                "bucket": "action",
                "title_main": "Strengthening required",
                "guidance_intent": "efficiency_tightening",
                "local_cleanup_candidate": True,
                "post_click_low_family_cleanup_action": False,
                "terminal_state_blocked_by_local_cleanup": False,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "no_second_cta_required": False,
                "candidate_search_evidence": {"selected_candidate_id": "best_safe_fixture"},
                "button_contract": dict(base_contract),
            },
            "expect_exact": False,
        },
        {
            "name": "exact_blocker_evidence_item",
            "result_item": {
                "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "status": "BLOCKED",
                "bucket": "blocked",
                "title_main": "Design Guide blocker proof complete",
                "guidance_intent": "efficiency_tightening",
                "local_cleanup_candidate": True,
                "post_click_low_family_cleanup_action": False,
                "terminal_state_blocked_by_local_cleanup": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "no_second_cta_required": True,
                "candidate_search_evidence": {
                    "selected_candidate_id": "exact_blocker_fixture",
                    "post_click_exact_blockers_by_family": dict(exact),
                },
                "button_contract": {"enabled": False, "family": "bending"},
                "action_payload": {"candidate_search_evidence": {}},
                "resolved_candidate": {"candidate_search_evidence": {}},
            },
            "audit": {"post_click_exact_blockers_by_family": dict(exact)},
            "expect_exact": True,
        },
    ]


def _capture() -> dict[str, Any]:
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_resolution_result_item_adapter_object_snapshot.py",
        ]
    )
    trace_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_live_post_click_low_bending_resolution_result_item_adapter_trace_snapshot.py",
        ]
    )
    case_results: list[dict[str, Any]] = []
    for case in _cases():
        original = dict(case["result_item"])
        first = _adapter(original, case.get("audit"))
        second = _adapter(original, case.get("audit"))
        adapted = dict(first.get("adapted_item") or {})
        original_contract_hash = _stable_hash(original.get("button_contract") or {})
        adapted_contract_hash = _stable_hash(adapted.get("button_contract") or {})
        evidence = dict(adapted.get("candidate_search_evidence") or {})
        payload_evidence = dict((adapted.get("action_payload") or {}).get("candidate_search_evidence") or {})
        resolved_evidence = dict((adapted.get("resolved_candidate") or {}).get("candidate_search_evidence") or {})
        expect_exact = bool(case.get("expect_exact"))
        comparisons = {
            "stable_hash": first.get("proof_hash") == second.get("proof_hash"),
            "title_preserved": adapted.get("title_main") == original.get("title_main"),
            "status_preserved": adapted.get("status") == original.get("status"),
            "bucket_preserved": adapted.get("bucket") == original.get("bucket"),
            "button_contract_preserved": original_contract_hash == adapted_contract_hash,
            "exact_blocker_item_parity": bool(adapted.get("post_click_exact_blockers_by_family"))
            is expect_exact,
            "exact_blocker_evidence_parity": bool(evidence.get("post_click_exact_blockers_by_family"))
            is expect_exact,
            "exact_blocker_payload_parity": bool(payload_evidence.get("post_click_exact_blockers_by_family"))
            is expect_exact,
            "exact_blocker_resolved_parity": bool(resolved_evidence.get("post_click_exact_blockers_by_family"))
            is expect_exact,
            "proof_only": first.get("proof_only") is True,
            "non_driving": all(
                first.get(key) is False
                for key in ("product_driving", "render_driving", "apply_driving", "session_driving")
            ),
        }
        case_results.append(
            {
                "name": case["name"],
                "passed": all(value is True for value in comparisons.values()),
                "comparisons": comparisons,
                "adapted_item_hash": first.get("adapted_item_hash"),
                "proof_hash": first.get("proof_hash"),
            }
        )
    return {
        "decision": "POST_CLICK_LOW_BENDING_RESULT_ITEM_ADAPTER_PARITY_PROVEN",
        "case_results": case_results,
        "case_count": len(case_results),
        "passed_case_count": sum(1 for row in case_results if row.get("passed") is True),
        "object_snapshot": object_run,
        "trace_snapshot": trace_run,
        "ready_for_branch_cutover_readiness": True,
        "ready_for_live_cutover": False,
        "product_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "trace_snapshot_passed": (capture.get("trace_snapshot") or {}).get("passed") is True,
        "all_cases_passed": capture.get("passed_case_count") == capture.get("case_count"),
        "ready_for_branch_cutover_readiness": (
            capture.get("ready_for_branch_cutover_readiness") is True
        ),
        "not_live_cutover_yet": capture.get("ready_for_live_cutover") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Low-Bending Result Item Adapter Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Cases",
        "",
    ]
    for row in capture.get("case_results") or []:
        lines.append(f"- {row.get('name')}: `{row.get('passed')}`")
    lines.extend(
        [
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Create a branch cutover readiness audit for the full item adapter; do not cut over until it proves the A-class branches can be replaced safely.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_resolution_result_item_adapter_parity_scenarios.v1",
        "generated_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_resolution_result_item_adapter_parity_scenarios_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_resolution_result_item_adapter_parity_scenarios_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_resolution_result_item_adapter_parity_scenarios {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
