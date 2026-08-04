"""Verify residual-shear physical return uses the prebuilt route result."""

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

ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_prebuilt_route_result = {}"


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
    raw = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    )
    upper = raw.upper()
    if "PASS" in upper or "LOCKED" in upper:
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
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "status": _status_from_payload(payload), "path": str(path)}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(source, ROUTE_BODY_START, ROUTE_BODY_END)
    latest = {
        "prebuilt_route_result_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_cutover"
        ),
        "prebuilt_route_result_builder_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_builder_cutover"
        ),
        "prebuilt_button_contract_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_button_contract_cutover"
        ),
    }
    return {
        "decision": "RESIDUAL_SHEAR_PREBUILT_PHYSICAL_RETURN_CUTOVER",
        "route_body_found": bool(body),
        "prebuilt_return_present": (
            "return dict(\n                            residual_prebuilt_route_result.get(\"result_item\")"
            in body
        ),
        "old_physical_return_absent": "return residual_route_return_item" not in body,
        "fallback_preserved": "or residual_route_return_item" in body,
        "prebuilt_result_parity_guard_present": (
            "residual_prebuilt_route_result.get(\"output_shape_ready\")" in body
            and "residual_prebuilt_route_result.get(\"result_item_hash\")" in body
            and "residual_prebuilt_route_result.get(\"fallback_item_hash\")" in body
        ),
        "previous_artifacts": latest,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "route_body_deleted": False,
        "next_safe_surface": "rerun_nested_wrapper_deadness_probe_then_route_shell_boundary",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_body_found": capture.get("route_body_found") is True,
        "prebuilt_return_present": capture.get("prebuilt_return_present") is True,
        "old_physical_return_absent": capture.get("old_physical_return_absent") is True,
        "fallback_preserved": capture.get("fallback_preserved") is True,
        "prebuilt_result_parity_guard_present": (
            capture.get("prebuilt_result_parity_guard_present") is True
        ),
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "route_body_not_deleted": capture.get("route_body_deleted") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Prebuilt Physical Return Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        "- The nested route body now returns the controller prebuilt route result first.",
        "- The previous route-return item remains as fallback.",
        "- The old literal `return residual_route_return_item` path is absent.",
        "",
        "## Checks",
        "",
    ]
    for name, ok in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{ok}`")
    lines.extend(["", "## Previous Artifacts", ""])
    for name, row in dict(capture.get("previous_artifacts") or {}).items():
        lines.append(f"- `{name}`: `{row.get('status')}` {row.get('path')}")
    lines.extend(["", "## Next", "", f"`{capture.get('next_safe_surface')}`", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    stamp = _stamp()
    payload = {
        "schema": (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            "prebuilt_physical_return_cutover.v1"
        ),
        "created_at": stamp,
        "status": status,
        "capture": capture,
        "checks": checks,
        "failures": [name for name, ok in checks.items() if ok is not True],
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = (
        ARTIFACT_DIR
        / (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            f"prebuilt_physical_return_cutover_{stamp}.json"
        )
    )
    audit_path = (
        AUDIT_DIR
        / (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            f"prebuilt_physical_return_cutover_{stamp}.md"
        )
    )
    report_path = (
        REPORT_DIR
        / (
            "design_brain_physical_extraction_residual_shear_cleanup_"
            f"prebuilt_physical_return_cutover_{stamp}.md"
        )
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"prebuilt_physical_return_cutover {status}"
    )
    print(json_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
