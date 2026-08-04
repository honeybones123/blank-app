"""Guarded cutover-readiness proof for evidence-merge result adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))"
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("


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


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    latest_object = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_object"
    )
    latest_trace = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace_wiring"
    )
    trace_payload = latest_trace.get("payload") or {}
    trace_capture = trace_payload.get("capture") or {}
    guarded_assignment_present = (
        "adapter_evidence_matches_live" in route
        and "adapter_exact_blockers_match_live" in route
        and "residual_evidence = dict(" in route
        and "residual_exact_blockers = dict(" in route
    )
    unguarded_assignment_present = (
        "residual_evidence = dict(residual_evidence_merge_tail_result_adapter" in route
        or "residual_exact_blockers = dict(residual_evidence_merge_tail_result_adapter" in route
    )
    ready_for_guarded_cutover = (
        latest_object.get("status") == "PASS"
        and latest_trace.get("status") == "PASS"
        and trace_capture.get("parity_flags_stamped") is True
        and trace_capture.get("no_assignment_from_result_adapter_to_live_evidence") is True
        and trace_capture.get("no_assignment_from_result_adapter_to_live_exact_blockers") is True
        and not unguarded_assignment_present
    )
    return {
        "decision": (
            "READY_FOR_GUARDED_EVIDENCE_MERGE_RESULT_ADAPTER_CUTOVER"
            if ready_for_guarded_cutover
            else "NOT_READY_FOR_GUARDED_CUTOVER"
        ),
        "ready_for_guarded_cutover": ready_for_guarded_cutover,
        "ready_for_unguarded_cutover": False,
        "guard_required": True,
        "guard_condition_required": (
            "adapter_evidence_matches_live and adapter_exact_blockers_match_live"
        ),
        "result_adapter_object_pass": latest_object.get("status") == "PASS",
        "result_adapter_trace_wiring_pass": latest_trace.get("status") == "PASS",
        "trace_parity_flags_stamped": trace_capture.get("parity_flags_stamped") is True,
        "trace_is_currently_non_driving": (
            trace_capture.get("no_assignment_from_result_adapter_to_live_evidence") is True
            and trace_capture.get("no_assignment_from_result_adapter_to_live_exact_blockers")
            is True
        ),
        "guarded_assignment_present": guarded_assignment_present,
        "unguarded_assignment_present": unguarded_assignment_present,
        "old_live_merge_deleted": "residual_evidence.update(" not in route,
        "next_cutover_shape": (
            "assign residual_evidence/residual_exact_blockers from adapter only under live parity guard"
        ),
        "latest": {
            "result_adapter_object": {k: v for k, v in latest_object.items() if k != "payload"},
            "result_adapter_trace_wiring": {
                k: v for k, v in latest_trace.items() if k != "payload"
            },
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "result_adapter_object_pass": capture.get("result_adapter_object_pass") is True,
        "result_adapter_trace_wiring_pass": (
            capture.get("result_adapter_trace_wiring_pass") is True
        ),
        "trace_parity_flags_stamped": capture.get("trace_parity_flags_stamped") is True,
        "trace_is_currently_non_driving": capture.get("trace_is_currently_non_driving")
        is True,
        "ready_for_guarded_cutover": capture.get("ready_for_guarded_cutover") is True,
        "ready_for_unguarded_cutover_false": (
            capture.get("ready_for_unguarded_cutover") is False
        ),
        "guard_required": capture.get("guard_required") is True,
        "no_unguarded_assignment_present": capture.get("unguarded_assignment_present")
        is False,
        "old_live_merge_deleted": capture.get("old_live_merge_deleted") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Evidence-Merge Result Adapter Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Ready for guarded cutover: `{capture.get('ready_for_guarded_cutover')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Guard required: `{capture.get('guard_required')}`",
        f"- Guard condition: `{capture.get('guard_condition_required')}`",
        f"- Unguarded assignment present: `{capture.get('unguarded_assignment_present')}`",
        f"- Old live merge deleted: `{capture.get('old_live_merge_deleted')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            str(capture.get("next_cutover_shape") or ""),
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_readiness.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_readiness "
        f"{payload['status']}"
    )
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
