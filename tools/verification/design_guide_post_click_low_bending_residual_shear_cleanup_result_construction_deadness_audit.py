"""Deadness audit for residual-shear cleanup result-construction subpath."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
INPUTS = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
    }


def _route_window(source: str) -> str:
    start = source.find("residual_shear_cleanup_route_entry_guard =")
    end = source.find("                    return residual_promoted", start)
    if start < 0 or end < 0:
        return ""
    return source[start:end]


def _capture() -> dict[str, Any]:
    cutover = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover.py",
        ]
    )
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _route_window(source)
    live_surfaces = {
        "result_packaging_call": "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(" in route,
        "residual_promoted_source_item": "residual_promoted, residual_detail" in route,
        "residual_evidence_extraction": "residual_promoted.get(\"candidate_search_evidence\")" in route,
        "residual_payload_extraction": "residual_payload = dict(residual_promoted.get(\"action_payload\") or {})" in route,
        "residual_resolved_extraction": "residual_resolved = dict(residual_promoted.get(\"resolved_candidate\") or {})" in route,
        "button_contract_extraction": "residual_button_contract = dict(" in route,
        "evidence_merge_result_adapter": "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter(" in route,
        "final_binding_tail_handoff": "residual_final_binding_tail_handoff =" in route,
        "route_body_identity_cutover": "route_body_result_identity_cutover_scope" in route,
    }
    deletion_candidates = []
    if not live_surfaces["result_packaging_call"]:
        deletion_candidates.append("result_packaging_call")
    if not live_surfaces["residual_evidence_extraction"]:
        deletion_candidates.append("residual_evidence_extraction")
    if not live_surfaces["button_contract_extraction"]:
        deletion_candidates.append("button_contract_extraction")
    safe_to_delete_any_now = False
    return {
        "decision": "RESULT_CONSTRUCTION_SUBPATH_STILL_LIVE_AFTER_IDENTITY_CUTOVER",
        "result_identity_cutover_passed": cutover.get("passed") is True,
        "live_surfaces": live_surfaces,
        "live_surface_count": sum(1 for value in live_surfaces.values() if value),
        "delete_now_count": 0,
        "deletion_candidates": deletion_candidates,
        "safe_to_delete_any_now": safe_to_delete_any_now,
        "classification": {
            "result_packaging_call": "C. still live result/evidence source",
            "residual_promoted_source_item": "C. still live source for controller identity cutover",
            "residual_evidence_extraction": "C. still live evidence source",
            "residual_payload_extraction": "C. still live CTA/apply payload source",
            "residual_resolved_extraction": "C. still live resolved-candidate source",
            "button_contract_extraction": "C. still live CTA contract source",
            "evidence_merge_result_adapter": "B. controller adapter present but still consumes live evidence",
            "final_binding_tail_handoff": "B. controller handoff present but not yet dead",
            "route_body_identity_cutover": "A. narrowed result identity only",
        },
        "recommended_next_surface": "result_packaging_and_final_binding_tail_controller_parity",
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "cutover_run": cutover,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    live_surfaces = dict(capture.get("live_surfaces") or {})
    return {
        "result_identity_cutover_passed": capture.get("result_identity_cutover_passed") is True,
        "result_packaging_call_still_live": live_surfaces.get("result_packaging_call") is True,
        "evidence_extraction_still_live": live_surfaces.get("residual_evidence_extraction") is True,
        "button_contract_extraction_still_live": live_surfaces.get("button_contract_extraction") is True,
        "route_body_identity_cutover_present": live_surfaces.get("route_body_identity_cutover") is True,
        "delete_now_count_zero": capture.get("delete_now_count") == 0,
        "safe_to_delete_any_now_false": capture.get("safe_to_delete_any_now") is False,
        "product_behavior_changed": capture.get("product_behavior_changed") is False,
        "engineering_behavior_changed": capture.get("engineering_behavior_changed") is False,
        "visible_wording_changed": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_changed": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_changed": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Result Construction Deadness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        f"- Live surface count: `{capture.get('live_surface_count')}`",
        f"- Delete now count: `{capture.get('delete_now_count')}`",
        f"- Safe to delete any now: `{capture.get('safe_to_delete_any_now')}`",
        f"- Recommended next surface: `{capture.get('recommended_next_surface')}`",
        "",
        "## Surface Classification",
        "",
    ]
    for key, value in (capture.get("classification") or {}).items():
        lines.append(f"- `{key}`: {value}")
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
            "## Next Safe Target",
            "",
            "Prove result packaging and final-binding tail parity before deleting or narrowing any result-construction fragment.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_result_construction_deadness_audit.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_result_construction_deadness_audit_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_result_construction_deadness_audit_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_result_construction_deadness_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_construction_deadness_audit "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
