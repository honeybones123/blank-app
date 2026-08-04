"""DesignGuideController trace-only parity snapshot.

Proof-only. This verifier proves a controller facade can reproduce the current
FinalDesignGuidePublication authority shape without becoming live product,
render, apply, session, or UI authority.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
INPUTS_PAGE = ROOT / "inputs_page.py"

REQUIRED_LOCK_ARTIFACTS = {
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
}

FORBIDDEN_CONTROLLER_TOKENS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "design_guide_page",
    "render_final_panel",
    "playwright",
    "browser",
    "route_apply",
    "apply_payload_binding",
}

EXPECTED_PAGE_OWNED_TOKENS = {
    "collapsed_guidance_bridge": "_collapsed_guidance_item_from_final_publication_authority",
    "final_visible_resolution_bridge": "_final_visible_resolution_from_final_publication_authority",
    "apply_payload_recording": "_record_rendered_design_guide_primary_apply_payload",
}


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "passed": False}
    path = paths[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "JSON_ERROR",
            "passed": False,
            "error": str(exc),
        }
    status = snapshot.get("status") or snapshot.get("result") or snapshot.get("lock_status")
    return {
        "found": True,
        "path": str(path),
        "status": status,
        "passed": status == "PASS" or str(status or "").endswith("locked"),
    }


def _case_payloads() -> list[dict[str, Any]]:
    return [
        {
            "name": "pass_design",
            "expected_outcome": "PASS",
            "item": {
                "published_item_id": "pass-001",
                "selected_family_id": "DESIGN_IS_EFFICIENT",
                "status": "PASS",
                "bucket": "pass",
                "title": "Design is efficient",
                "summary_line": "All checks pass.",
                "pill": "PASS",
                "candidate_search_evidence": {"selected_family_id": "DESIGN_IS_EFFICIENT"},
            },
            "debug": {},
            "publication_reason": "pass_final_visible",
        },
        {
            "name": "action_repair",
            "expected_outcome": "ACTION",
            "item": {
                "published_item_id": "action-001",
                "selected_family_id": "BENDING_FAIL_GOVERNS",
                "status": "ACTION",
                "bucket": "action",
                "title": "Strengthening required",
                "summary_line": "Apply the proposed repair.",
                "pill": "ACTION",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "label": "Apply",
                    "action_type": "apply_candidate",
                    "family": "BENDING_FAIL_GOVERNS",
                    "source_candidate_id": "action-001",
                    "updates": {"D": 650},
                },
                "action_payload": {
                    "source_candidate_id": "action-001",
                    "updates": {"D": 650},
                },
                "candidate_search_evidence": {"selected_family_id": "BENDING_FAIL_GOVERNS"},
            },
            "debug": {},
            "publication_reason": "action_final_visible",
        },
        {
            "name": "blocked_design",
            "expected_outcome": "BLOCKED",
            "item": {
                "published_item_id": "blocked-001",
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "status": "BLOCKED",
                "bucket": "fail",
                "title": "Design Guide blocker proof incomplete",
                "summary_line": "Repair is blocked by checked route evidence.",
                "pill": "BLOCKED",
                "blocking_reason": "No valid shear repair candidate remained inside checked limits.",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "disabled_reason": "No valid shear repair candidate remained inside checked limits.",
                    "family": "SHEAR_FAIL_GOVERNS",
                },
                "exact_blockers_by_family": {
                    "SHEAR_FAIL_GOVERNS": {"blocked": True, "reason": "no_valid_candidate"}
                },
                "candidate_search_evidence": {"selected_family_id": "SHEAR_FAIL_GOVERNS"},
            },
            "debug": {},
            "publication_reason": "blocked_final_visible",
        },
        {
            "name": "error_design",
            "expected_outcome": "ERROR",
            "item": {
                "published_item_id": "error-001",
                "selected_family_id": "DESIGN_GUIDE_ERROR",
                "status": "ERROR",
                "bucket": "error",
                "title": "Design Guide error",
                "summary_line": "Publication could not be completed.",
                "pill": "ERROR",
            },
            "debug": {},
            "publication_reason": "error_final_visible",
        },
        {
            "name": "proof_pending_design",
            "expected_outcome": "PROOF_PENDING",
            "item": {
                "published_item_id": "pending-001",
                "selected_family_id": "PROOF_PENDING",
                "title": "Checking design guidance",
                "summary_line": "Reviewing strength and cleanup options.",
                "pill": "PENDING",
            },
            "debug": {},
            "publication_reason": "pending_final_visible",
        },
    ]


def _run_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        DesignGuideControllerRequest,
        run_design_guide_controller_trace_only,
    )
    from design_brain.final_publication import build_final_design_guide_publication

    results: list[dict[str, Any]] = []
    for case in _case_payloads():
        direct = build_final_design_guide_publication(
            item=case["item"],
            debug=case["debug"],
            publication_reason=case["publication_reason"],
        )
        response = run_design_guide_controller_trace_only(
            DesignGuideControllerRequest(
                item=case["item"],
                debug=case["debug"],
                final_visible_resolution={"render_reason": case["publication_reason"]},
                publication_reason=case["publication_reason"],
                source=f"{case['name']}_trace",
            )
        )
        result = {
            "name": case["name"],
            "expected_outcome": case["expected_outcome"],
            "direct_publication_hash": direct.publication_hash,
            "controller_publication_hash": response.publication_hash,
            "controller_hash": response.controller_hash,
            "direct_outcome": direct.outcome_state,
            "controller_outcome": response.parity_payload.get("outcome_state"),
            "direct_selected_family": direct.selected_family,
            "controller_selected_family": response.parity_payload.get("selected_family"),
            "collapsed_publication_hash": response.collapsed_guidance_item.get("publication_hash"),
            "resolution_publication_hash": response.final_visible_resolution.get("publication_hash"),
            "trace_only": response.trace_only,
            "product_driving": response.product_driving,
            "render_driving": response.render_driving,
            "apply_driving": response.apply_driving,
            "session_driving": response.session_driving,
        }
        result["passed"] = all(
            [
                result["direct_publication_hash"] == result["controller_publication_hash"],
                result["direct_publication_hash"] == result["collapsed_publication_hash"],
                result["direct_publication_hash"] == result["resolution_publication_hash"],
                result["direct_outcome"] == result["expected_outcome"],
                result["controller_outcome"] == result["expected_outcome"],
                result["direct_selected_family"] == result["controller_selected_family"],
                result["trace_only"] is True,
                result["product_driving"] is False,
                result["render_driving"] is False,
                result["apply_driving"] is False,
                result["session_driving"] is False,
            ]
        )
        results.append(result)
    return results


def _source_checks() -> dict[str, Any]:
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    page_source = INPUTS_PAGE.read_text(encoding="utf-8")
    forbidden_hits = {
        token: token in controller_source
        for token in sorted(FORBIDDEN_CONTROLLER_TOKENS)
        if token in controller_source
    }
    page_owned_present = {
        name: token in page_source for name, token in EXPECTED_PAGE_OWNED_TOKENS.items()
    }
    live_controller_calls = (
        "run_design_guide_controller_trace_only(" in page_source
        or "_run_design_guide_controller_trace_only(" in page_source
    )
    live_trace_wiring_present = "_stamp_design_guide_controller_trace_only_parity" in page_source
    live_trace_non_authoritative = all(
        token in page_source
        for token in (
            '"design_guide_controller_trace_only_product_driving"] = False',
            '"design_guide_controller_trace_only_render_driving"] = False',
            '"design_guide_controller_trace_only_apply_driving"] = False',
            '"design_guide_controller_trace_only_session_driving"] = False',
        )
    )
    return {
        "forbidden_controller_hits": forbidden_hits,
        "page_owned_boundaries_present": page_owned_present,
        "inputs_page_uses_controller_live": live_controller_calls,
        "live_trace_wiring_present": live_trace_wiring_present,
        "live_trace_non_authoritative": live_trace_non_authoritative,
        "controller_clean": not forbidden_hits,
        "page_boundaries_retained": all(page_owned_present.values()),
        "trace_only_wiring_allowed": (not live_controller_calls)
        or (live_trace_wiring_present and live_trace_non_authoritative),
    }


def _write_report(snapshot: dict[str, Any], json_path: Path, md_path: Path) -> None:
    lines = [
        "# DesignGuideController Trace-Only Parity Snapshot",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Summary",
        "",
        f"- Controller trace-only parity: `{snapshot['controller_trace_only_parity']}`",
        f"- Product behavior changed: `{snapshot['product_behavior_changed']}`",
        f"- Inputs page live-wired to controller: `{snapshot['source_checks']['inputs_page_uses_controller_live']}`",
        "",
        "## Case Results",
        "",
        "| Case | Expected | Direct | Controller | Hash parity | Passed |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in snapshot["cases"]:
        lines.append(
            "| {name} | {expected} | {direct} | {controller} | {hash_parity} | {passed} |".format(
                name=case["name"],
                expected=case["expected_outcome"],
                direct=case["direct_outcome"],
                controller=case["controller_outcome"],
                hash_parity=case["direct_publication_hash"]
                == case["controller_publication_hash"],
                passed=case["passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Source Boundary",
            "",
            f"- Controller forbidden ownership hits: `{snapshot['source_checks']['forbidden_controller_hits']}`",
            f"- Page-owned boundaries retained: `{snapshot['source_checks']['page_owned_boundaries_present']}`",
            f"- Live trace wiring present: `{snapshot['source_checks']['live_trace_wiring_present']}`",
            f"- Live trace wiring non-authoritative: `{snapshot['source_checks']['live_trace_non_authoritative']}`",
            "",
            "## Required Lock Artifacts",
            "",
            "| Gate | Found | Status | Path |",
            "| --- | --- | --- | --- |",
        ]
    )
    for name, lock in snapshot["required_locks"].items():
        lines.append(f"| {name} | {lock['found']} | {lock['status']} | `{lock['path']}` |")
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            (
                "Use the live trace wiring snapshot to compare controller hashes "
                "against already-published `FinalDesignGuidePublication` hashes "
                "before any controller authority move."
            ),
        ]
    )
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases = _run_cases()
    source_checks = _source_checks()
    locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCK_ARTIFACTS.items()}
    status = "PASS"
    if not all(case["passed"] for case in cases):
        status = "FAIL"
    if not source_checks["controller_clean"]:
        status = "FAIL"
    if not source_checks["page_boundaries_retained"]:
        status = "FAIL"
    if not source_checks["trace_only_wiring_allowed"]:
        status = "FAIL"
    if not all(lock["passed"] for lock in locks.values()):
        status = "FAIL"
    snapshot = {
        "status": status,
        "snapshot": "design_guide_controller_trace_only_parity",
        "timestamp": timestamp,
        "controller_trace_only_parity": all(case["passed"] for case in cases),
        "product_behavior_changed": False,
        "cases": cases,
        "source_checks": source_checks,
        "required_locks": locks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_controller_trace_only_parity_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_controller_trace_only_parity_{timestamp}.md"
    _write_report(snapshot, json_path, md_path)
    print(f"status: {status}")
    print(f"json: {json_path}")
    print(f"report: {md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

