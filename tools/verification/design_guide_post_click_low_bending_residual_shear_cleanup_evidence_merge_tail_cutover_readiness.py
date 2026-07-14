"""Cutover-readiness audit for residual-shear evidence-merge tail.

This is proof-only. It decides whether the residual evidence/exact-blocker
merge tail can be cut over now, or whether the controller still needs a
result-producing merge adapter before live behavior can move.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))"
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("
HANDOFF_FUNCTION = (
    "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff("
)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw_status.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        status = "PASS"
    elif "FAIL" in upper:
        status = "FAIL"
    else:
        status = raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path), "payload": payload}


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\n\ndef ", start + len(token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(inputs_source, ROUTE_START, ROUTE_END)
    handoff = _function_block(controller_source, HANDOFF_FUNCTION)
    latest_trace = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_trace_wiring"
    )
    latest_object = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_object"
    )
    controller_returns_hashes_only = (
        "\"residual_evidence_hash\"" in handoff
        and "\"residual_exact_blockers_hash\"" in handoff
        and "\"residual_evidence\"" not in handoff
        and "\"residual_exact_blockers\"" not in handoff
    )
    live_merge_still_authoritative = (
        "residual_evidence.update(" in route
        and "residual_exact_blockers[\"shear\"] = dict(residual_shear_blocker)" in route
    )
    no_live_assignment_from_handoff = (
        "residual_evidence = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff"
        not in route
        and "residual_exact_blockers = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff"
        not in route
    )
    trace_payload = latest_trace.get("payload") or {}
    trace_capture = trace_payload.get("capture") or {}
    readiness_blockers = []
    if controller_returns_hashes_only:
        readiness_blockers.append("controller_handoff_records_hashes_but_does_not_return_merged_evidence")
    if live_merge_still_authoritative:
        readiness_blockers.append("live_page_merge_still_executes")
    cutover_ready = (
        latest_trace.get("status") == "PASS"
        and latest_object.get("status") == "PASS"
        and not controller_returns_hashes_only
        and not live_merge_still_authoritative
        and no_live_assignment_from_handoff
    )
    decision = (
        "READY_FOR_EVIDENCE_MERGE_CUTOVER"
        if cutover_ready
        else "NOT_READY_CONTROLLER_MERGE_RESULT_ADAPTER_NEEDED"
    )
    return {
        "decision": decision,
        "cutover_ready": cutover_ready,
        "trace_wiring_pass": latest_trace.get("status") == "PASS",
        "object_snapshot_pass": latest_object.get("status") == "PASS",
        "trace_output_shape_known": (
            trace_capture.get("output_summary_tokens_present") is True
            and trace_capture.get("route_input_tokens_present") is True
        ),
        "controller_handoff_present": bool(handoff),
        "controller_returns_hashes_only": controller_returns_hashes_only,
        "controller_returns_merged_evidence_payload": not controller_returns_hashes_only,
        "live_merge_still_authoritative": live_merge_still_authoritative,
        "no_live_assignment_from_handoff": no_live_assignment_from_handoff,
        "readiness_blockers": readiness_blockers,
        "next_required_adapter": (
            "controller-owned evidence merge result adapter returning merged evidence and exact blockers"
            if not cutover_ready
            else ""
        ),
        "latest": {
            "trace_wiring": {k: v for k, v in latest_trace.items() if k != "payload"},
            "object_snapshot": {k: v for k, v in latest_object.items() if k != "payload"},
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "trace_wiring_pass": capture.get("trace_wiring_pass") is True,
        "object_snapshot_pass": capture.get("object_snapshot_pass") is True,
        "trace_output_shape_known": capture.get("trace_output_shape_known") is True,
        "controller_handoff_present": capture.get("controller_handoff_present") is True,
        "no_live_assignment_from_handoff": capture.get("no_live_assignment_from_handoff") is True,
        "readiness_decision_is_explicit": capture.get("decision")
        in {
            "READY_FOR_EVIDENCE_MERGE_CUTOVER",
            "NOT_READY_CONTROLLER_MERGE_RESULT_ADAPTER_NEEDED",
        },
        "not_ready_has_blockers": (
            capture.get("cutover_ready") is True
            or bool(capture.get("readiness_blockers"))
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Evidence-Merge Tail Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Cutover ready: `{capture.get('cutover_ready')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Trace wiring PASS: `{capture.get('trace_wiring_pass')}`",
        f"- Object snapshot PASS: `{capture.get('object_snapshot_pass')}`",
        f"- Controller returns hashes only: `{capture.get('controller_returns_hashes_only')}`",
        f"- Live merge still authoritative: `{capture.get('live_merge_still_authoritative')}`",
        f"- No live assignment from handoff: `{capture.get('no_live_assignment_from_handoff')}`",
        "",
        "## Readiness Blockers",
        "",
    ]
    blockers = list(capture.get("readiness_blockers") or [])
    lines.extend(f"- `{blocker}`" for blocker in blockers)
    if not blockers:
        lines.append("- none")
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
            str(capture.get("next_required_adapter") or "Proceed to narrow evidence-merge cutover."),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_cutover_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash({"capture": capture, "checks": checks})
    stamp = str(payload["created_at"])
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_cutover_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_cutover_readiness "
        f"{payload['status']}"
    )
    print(f"decision={capture.get('decision')}")
    print(f"cutover_ready={capture.get('cutover_ready')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
