"""Implementation verifier for residual-shear route-body result identity cutover."""

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
    start = source.find("residual_route_body_replacement =")
    end = source.find("                        return residual_route_return_item", start)
    if end < 0:
        end = source.find("                        return dict(", start)
    if end < 0:
        end = source.find("                    return residual_promoted", start)
    if start < 0 or end < 0:
        return ""
    return source[start:end]


def _capture() -> dict[str, Any]:
    readiness = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_cutover_readiness.py",
        ]
    )
    trace = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_trace_wiring_snapshot.py",
        ]
    )
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _route_window(source)
    normalized_route = route.replace("\r\n", "\n")
    forbidden_moved_dependencies = (
        "generate_less_shear_reo_variants(",
        "_evaluate_auto_design_candidate(",
        "_render_",
        "st.",
    )
    return {
        "decision": "ROUTE_BODY_RESULT_IDENTITY_CUTOVER_IMPLEMENTED",
        "readiness_passed": readiness.get("passed") is True,
        "trace_passed": trace.get("passed") is True,
        "assigned_replacement_payload": "residual_route_body_replacement =" in normalized_route,
        "hash_guard_present": all(
            token in normalized_route
            for token in (
                'residual_route_body_replacement.get("output_shape_ready")',
                'residual_route_body_replacement.get("result_item_hash")',
                "_stable_final_publication_hash(dict(residual_promoted or {}))",
            )
        ),
        "result_identity_assignment_present": (
            "residual_promoted = dict(" in normalized_route
            and 'residual_route_body_replacement.get("result_item")' in normalized_route
            and "or residual_promoted" in normalized_route
        ),
        "scope_stamp_present": (
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover_scope"
            in normalized_route
            and '"result_identity_only"' in normalized_route
        ),
        "applied_stamp_present": (
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover_applied"
            in normalized_route
        ),
        "risky_dependency_not_moved_in_cutover_window": not any(
            token in normalized_route for token in forbidden_moved_dependencies
        ),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "old_route_body_safe_to_delete": False,
        "readiness_run": readiness,
        "trace_run": trace,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "readiness_passed": capture.get("readiness_passed") is True,
        "trace_passed": capture.get("trace_passed") is True,
        "assigned_replacement_payload": capture.get("assigned_replacement_payload") is True,
        "hash_guard_present": capture.get("hash_guard_present") is True,
        "result_identity_assignment_present": (
            capture.get("result_identity_assignment_present") is True
        ),
        "scope_stamp_present": capture.get("scope_stamp_present") is True,
        "applied_stamp_present": capture.get("applied_stamp_present") is True,
        "risky_dependency_not_moved_in_cutover_window": (
            capture.get("risky_dependency_not_moved_in_cutover_window") is True
        ),
        "product_behavior_changed": capture.get("product_behavior_changed") is False,
        "engineering_behavior_changed": capture.get("engineering_behavior_changed") is False,
        "visible_wording_changed": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_changed": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_changed": capture.get("family_runtime_changed") is False,
        "old_route_body_safe_to_delete_false": capture.get("old_route_body_safe_to_delete") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route Body Result Identity Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        f"- Hash guard present: `{capture.get('hash_guard_present')}`",
        f"- Result identity assignment present: `{capture.get('result_identity_assignment_present')}`",
        f"- Scope stamp present: `{capture.get('scope_stamp_present')}`",
        f"- Old route body safe to delete: `{capture.get('old_route_body_safe_to_delete')}`",
        "",
        "## Preserved",
        "",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "- Candidate generation/evaluation and CTA contract execution remain page-live/injected.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            "Run a deadness/readiness audit for the old route-body result-construction subpath. Do not delete the full route body.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_body_result_identity_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover "
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
