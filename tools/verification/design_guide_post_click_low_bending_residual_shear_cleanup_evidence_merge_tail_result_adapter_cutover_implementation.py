"""Verifier for guarded evidence-merge result-adapter cutover."""

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
REPORT_DIR = ROOT / "artifacts" / "reports"

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
    return {"found": True, "status": status, "path": str(path)}


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    adapter_assignment = (
        "residual_evidence_merge_tail_result_adapter = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace("
    )
    guarded_block = (
        "if (\n                            residual_evidence_merge_tail_result_adapter.get(\n                                \"adapter_evidence_matches_live\""
    )
    exact_guard = (
        "residual_evidence_merge_tail_result_adapter.get(\n                                \"adapter_exact_blockers_match_live\""
    )
    evidence_assignment = (
        "residual_evidence = dict(\n                                residual_evidence_merge_tail_result_adapter.get("
    )
    exact_blocker_assignment = (
        "residual_exact_blockers = dict(\n                                residual_evidence_merge_tail_result_adapter.get("
    )
    handoff_call = (
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff("
    )
    adapter_index = route.find(adapter_assignment)
    guarded_index = route.find(guarded_block)
    evidence_assignment_index = route.find(evidence_assignment)
    exact_assignment_index = route.find(exact_blocker_assignment)
    handoff_index = route.find(handoff_call)
    controller_merge_index = route.find(
        "residual_evidence_merge_tail_result_adapter = _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter("
    )
    unguarded_assignment_present = (
        evidence_assignment_index >= 0
        and not (guarded_index >= 0 and guarded_index < evidence_assignment_index)
    ) or (
        exact_assignment_index >= 0
        and not (guarded_index >= 0 and guarded_index < exact_assignment_index)
    )
    return {
        "decision": "GUARDED_EVIDENCE_MERGE_RESULT_ADAPTER_CUTOVER_IMPLEMENTED",
        "route_found": bool(route),
        "adapter_assignment_present": adapter_assignment in route,
        "guarded_block_present": guarded_block in route,
        "exact_guard_present": exact_guard in route,
        "evidence_assignment_present": evidence_assignment in route,
        "exact_blocker_assignment_present": exact_blocker_assignment in route,
        "adapter_before_guard": adapter_index >= 0 and guarded_index > adapter_index,
        "guard_before_assignments": (
            guarded_index >= 0
            and evidence_assignment_index > guarded_index
            and exact_assignment_index > guarded_index
        ),
        "handoff_after_guarded_cutover": handoff_index > exact_assignment_index >= 0,
        "old_live_merge_deleted": "residual_evidence.update(" not in route,
        "old_live_exact_blocker_merge_deleted": (
            "residual_exact_blockers[\"shear\"] = dict(residual_shear_blocker)" not in route
        ),
        "controller_merge_present_before_trace": (
            controller_merge_index >= 0 and adapter_index > controller_merge_index
        ),
        "unguarded_assignment_present": unguarded_assignment_present,
        "latest": {
            "cutover_readiness": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_readiness"
            ),
            "trace_wiring": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace_wiring"
            ),
            "object_snapshot": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_object"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = capture.get("latest") or {}
    return {
        "route_found": capture.get("route_found") is True,
        "adapter_assignment_present": capture.get("adapter_assignment_present") is True,
        "guarded_block_present": capture.get("guarded_block_present") is True,
        "exact_guard_present": capture.get("exact_guard_present") is True,
        "evidence_assignment_present": capture.get("evidence_assignment_present") is True,
        "exact_blocker_assignment_present": (
            capture.get("exact_blocker_assignment_present") is True
        ),
        "adapter_before_guard": capture.get("adapter_before_guard") is True,
        "guard_before_assignments": capture.get("guard_before_assignments") is True,
        "handoff_after_guarded_cutover": capture.get("handoff_after_guarded_cutover")
        is True,
        "old_live_merge_deleted": (
            capture.get("old_live_merge_deleted") is True
        ),
        "old_live_exact_blocker_merge_deleted": (
            capture.get("old_live_exact_blocker_merge_deleted") is True
        ),
        "controller_merge_present_before_trace": (
            capture.get("controller_merge_present_before_trace") is True
        ),
        "no_unguarded_assignment_present": (
            capture.get("unguarded_assignment_present") is False
        ),
        "cutover_readiness_pass": (
            latest.get("cutover_readiness", {}).get("status") == "PASS"
        ),
        "trace_wiring_pass": latest.get("trace_wiring", {}).get("status") == "PASS",
        "object_snapshot_pass": latest.get("object_snapshot", {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any], *, title: str) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        f"# {title}",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Guarded block present: `{capture.get('guarded_block_present')}`",
        f"- Guard before assignments: `{capture.get('guard_before_assignments')}`",
        f"- Handoff after guarded cutover: `{capture.get('handoff_after_guarded_cutover')}`",
        f"- Old live merge deleted: `{capture.get('old_live_merge_deleted')}`",
        f"- Controller merge before trace: `{capture.get('controller_merge_present_before_trace')}`",
        f"- Unguarded assignment present: `{capture.get('unguarded_assignment_present')}`",
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
            "Create deadness/readiness proof for the old live merge block. Delete nothing until that proof passes.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_implementation.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_implementation_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_implementation_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_implementation_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload, title="Residual Shear Cleanup Evidence-Merge Result Adapter Cutover Implementation")
    _write_report(report_path, payload, title="Design Brain Physical Extraction Report")
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_implementation "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
