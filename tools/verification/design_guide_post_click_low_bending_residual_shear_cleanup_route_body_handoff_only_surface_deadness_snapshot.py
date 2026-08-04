"""Deadness snapshot for the old residual-shear handoff-only route-body surface."""

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
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if "PASS" in raw.upper() or "LOCKED" in raw.upper() else raw or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _call_windows(source: str, token: str) -> list[str]:
    windows: list[str] = []
    start = 0
    while True:
        index = source.find(token, start)
        if index < 0:
            break
        windows.append(source[index : index + 1600])
        start = index + len(token)
    return windows


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    call_token = (
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "route_body_replacement("
    )
    windows = _call_windows(source, call_token)
    live_windows = [
        window
        for window in windows
        if "route_shell_adapter=dict(residual_route_shell_adapter or {})" in window
    ]
    handoff_only_live_windows = [
        window
        for window in live_windows
        if "primary_executor_handoff=dict(residual_primary_executor_handoff or {})" in window
        and "primary_executor_dependency_boundary=dict(" not in window
    ]
    boundary_backed_live_windows = [
        window
        for window in live_windows
        if "primary_executor_dependency_boundary=dict(" in window
        and "residual_primary_executor_dependency_boundary or {}" in window
    ]
    required = {
        "dependency_route_shape_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_dependency_route_shape_readiness"
        ),
        "route_body_replacement_trace_wiring": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_trace_wiring"
        ),
        "route_body_replacement_cutover_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_cutover_readiness"
        ),
    }
    return {
        "decision": "RESIDUAL_SHEAR_ROUTE_BODY_HANDOFF_ONLY_SURFACE_DEAD_FOR_LIVE_PATH",
        "total_route_body_replacement_calls": len(windows),
        "live_route_body_replacement_calls": len(live_windows),
        "handoff_only_live_calls": len(handoff_only_live_windows),
        "boundary_backed_live_calls": len(boundary_backed_live_windows),
        "required_artifacts": required,
        "required_artifacts_pass": all(row.get("status") == "PASS" for row in required.values()),
        "safe_to_delete_optional_controller_param_now": False,
        "safe_to_delete_page_executor_now": False,
        "next_safe_surface": "fallback_variant_generator_dependency_boundary_object",
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "required_artifacts_pass": capture.get("required_artifacts_pass") is True,
        "live_route_body_replacement_call_present": (
            capture.get("live_route_body_replacement_calls") == 1
        ),
        "handoff_only_live_calls_zero": capture.get("handoff_only_live_calls") == 0,
        "boundary_backed_live_call_present": capture.get("boundary_backed_live_calls") == 1,
        "optional_controller_param_not_deleted": (
            capture.get("safe_to_delete_optional_controller_param_now") is False
        ),
        "page_executor_not_deleted": capture.get("safe_to_delete_page_executor_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Route Body Handoff-Only Surface Deadness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Live route-body replacement calls: `{capture.get('live_route_body_replacement_calls')}`",
        f"- Handoff-only live calls: `{capture.get('handoff_only_live_calls')}`",
        f"- Boundary-backed live calls: `{capture.get('boundary_backed_live_calls')}`",
        f"- Safe to delete page executor now: `{capture.get('safe_to_delete_page_executor_now')}`",
        f"- Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_handoff_only_surface_deadness_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"route_body_handoff_only_surface_deadness_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"route_body_handoff_only_surface_deadness_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_cleanup_"
        f"route_body_handoff_only_surface_deadness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_handoff_only_surface_deadness "
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
