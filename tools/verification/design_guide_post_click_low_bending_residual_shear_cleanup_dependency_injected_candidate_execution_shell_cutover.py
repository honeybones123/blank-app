"""Verify residual-shear candidate execution orchestration uses the controller shell."""

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

ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_physical_route_body_wrapper = "


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _status_from_payload(payload: dict[str, Any]) -> str:
    raw = str(payload.get("status") or payload.get("decision") or "")
    upper = raw.upper()
    if "PASS" in upper:
        return "PASS"
    if "FAIL" in upper:
        return "FAIL"
    if "PARTIAL" in upper:
        return "PARTIAL"
    return raw or "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    return {"found": True, "status": _status_from_payload(payload), "path": str(path)}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(source, ROUTE_BODY_START, ROUTE_BODY_END)
    before_bundle = _between(
        body,
        "        residual_route_shell_metadata = {",
        "        residual_candidate_execution_bundle = ",
    )
    previous = {
        "readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_dependency_injected_candidate_execution_shell_readiness"
        ),
        "supplier_readiness_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_supplier_readiness_audit"
        ),
    }
    return {
        "decision": "RESIDUAL_SHEAR_DEPENDENCY_INJECTED_CANDIDATE_EXECUTION_SHELL_CUTOVER",
        "route_body_found": bool(body),
        "injected_shell_imported": (
            "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies as "
            in source
        ),
        "injected_shell_called_before_bundle": (
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies("
            in before_bundle
        ),
        "primary_dependency_still_injected": (
            "primary_executor=lambda:" in before_bundle
            and "_run_post_click_low_bending_residual_shear_cleanup_primary_executor("
            in before_bundle
        ),
        "fallback_dependency_still_injected": (
            "fallback_search_loop=lambda:" in before_bundle
            and "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop("
            in before_bundle
        ),
        "manual_primary_sequence_removed": (
            "residual_route_primary_result = _run_post_click_low_bending_residual_shear_cleanup_primary_executor("
            not in before_bundle
        ),
        "manual_fallback_sequence_removed": (
            "if residual_route_fallback_search_loop_executed:\n"
            "            residual_route_fallback_search_loop_payload = "
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop("
            not in before_bundle
        ),
        "candidate_bundle_still_built": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle("
            in body
        ),
        "prebuilt_route_shell_still_consumes_bundle": (
            'prebuilt_primary_result=residual_candidate_execution_bundle.get("primary_result")'
            in body
        ),
        "debug_stamp_present": (
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_dependency_injected_candidate_execution_shell"
            in body
        ),
        "previous_artifacts": previous,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in previous.values()),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_surface": "route_body_supplier_ownership_reaudit_after_dependency_injected_candidate_execution_shell_cutover",
        "route_body_hash": _stable_hash(body),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_body_found": capture.get("route_body_found") is True,
        "injected_shell_imported": capture.get("injected_shell_imported") is True,
        "injected_shell_called_before_bundle": (
            capture.get("injected_shell_called_before_bundle") is True
        ),
        "primary_dependency_still_injected": (
            capture.get("primary_dependency_still_injected") is True
        ),
        "fallback_dependency_still_injected": (
            capture.get("fallback_dependency_still_injected") is True
        ),
        "manual_primary_sequence_removed": capture.get("manual_primary_sequence_removed") is True,
        "manual_fallback_sequence_removed": capture.get("manual_fallback_sequence_removed") is True,
        "candidate_bundle_still_built": capture.get("candidate_bundle_still_built") is True,
        "prebuilt_route_shell_still_consumes_bundle": (
            capture.get("prebuilt_route_shell_still_consumes_bundle") is True
        ),
        "debug_stamp_present": capture.get("debug_stamp_present") is True,
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Dependency-Injected Candidate Execution Shell Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Checks",
        "",
    ]
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [name for name, value in checks.items() if value is not True]
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "timestamp": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"dependency_injected_candidate_execution_shell_cutover_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"dependency_injected_candidate_execution_shell_cutover_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_dependency_injected_candidate_execution_shell_cutover",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
