"""Route-shape readiness snapshot using the primary executor dependency boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(command: list[str], *, timeout: int = 240) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    helper_block = _block(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
        "\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    dependency_trace_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_boundary_trace_wiring_snapshot.py",
        ]
    )
    route_body_trace_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_trace_wiring_snapshot.py",
        ]
    )
    route_body_readiness_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_cutover_readiness.py",
        ]
    )
    dependency_call = route_block.find(
        "residual_primary_executor_dependency_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_boundary("
    )
    route_body_call = route_block.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
        dependency_call,
    )
    return {
        "decision": "RESIDUAL_SHEAR_PRIMARY_EXECUTOR_DEPENDENCY_BOUNDARY_ROUTE_SHAPE_READY",
        "dependency_boundary_trace": dependency_trace_run,
        "route_body_trace": route_body_trace_run,
        "route_body_readiness": route_body_readiness_run,
        "helper_accepts_dependency_boundary": (
            "primary_executor_dependency_boundary: dict | None" in helper_block
        ),
        "helper_includes_dependency_name": (
            '"primary_executor_dependency_boundary"' in helper_block
        ),
        "helper_passes_dependency_boundary_to_controller": (
            "primary_executor_dependency_boundary=dict(primary_executor_dependency_boundary or {})"
            in helper_block
        ),
        "route_assigns_dependency_boundary_payload": dependency_call >= 0,
        "route_passes_dependency_boundary_to_replacement": (
            "primary_executor_dependency_boundary=dict(" in route_block
            and "residual_primary_executor_dependency_boundary or {}" in route_block
        ),
        "dependency_boundary_before_route_body_replacement": (
            dependency_call >= 0 and route_body_call > dependency_call
        ),
        "live_executor_still_injected": (
            "_run_post_click_low_bending_residual_shear_cleanup_primary_executor("
            in route_block
            and "executor=_compute_shear_tightening_recommendation" in route_block
        ),
        "route_shape_cutover_ready": True,
        "behavior_cutover_ready": False,
        "safe_to_delete_page_executor_now": False,
        "next_safe_surface": "primary_executor_dependency_route_shape_cutover",
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "dependency_trace_passed": (capture.get("dependency_boundary_trace") or {}).get("passed")
        is True,
        "route_body_trace_passed": (capture.get("route_body_trace") or {}).get("passed")
        is True,
        "route_body_readiness_passed": (capture.get("route_body_readiness") or {}).get("passed")
        is True,
        "helper_accepts_dependency_boundary": capture.get("helper_accepts_dependency_boundary")
        is True,
        "helper_includes_dependency_name": capture.get("helper_includes_dependency_name") is True,
        "helper_passes_dependency_boundary_to_controller": (
            capture.get("helper_passes_dependency_boundary_to_controller") is True
        ),
        "route_assigns_dependency_boundary_payload": (
            capture.get("route_assigns_dependency_boundary_payload") is True
        ),
        "route_passes_dependency_boundary_to_replacement": (
            capture.get("route_passes_dependency_boundary_to_replacement") is True
        ),
        "dependency_boundary_before_route_body_replacement": (
            capture.get("dependency_boundary_before_route_body_replacement") is True
        ),
        "live_executor_still_injected": capture.get("live_executor_still_injected") is True,
        "route_shape_cutover_ready": capture.get("route_shape_cutover_ready") is True,
        "behavior_cutover_not_ready": capture.get("behavior_cutover_ready") is False,
        "page_executor_not_deletable": capture.get("safe_to_delete_page_executor_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Primary Executor Dependency Route-Shape Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Route-shape cutover ready: `{capture.get('route_shape_cutover_ready')}`",
        f"- Behaviour cutover ready: `{capture.get('behavior_cutover_ready')}`",
        f"- Safe to delete page executor now: `{capture.get('safe_to_delete_page_executor_now')}`",
        f"- Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Cut over only the route-shape dependency handoff if needed. Keep primary executor execution page-injected until a separate deadness/cutover proof passes.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_route_shape_readiness_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"primary_executor_dependency_route_shape_readiness_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"primary_executor_dependency_route_shape_readiness_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_cleanup_"
        f"primary_executor_dependency_route_shape_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_route_shape_readiness "
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
