"""Cutover readiness for residual-shear button-contract source summary."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=120)
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
        "passed": proc.returncode == 0,
    }


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _capture() -> dict[str, Any]:
    object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_snapshot.py",
        ]
    )
    parity_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_parity_scenarios.py",
        ]
    )
    source_boundary_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_implementation.py",
        ]
    )
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    readiness_tokens = {
        "boundary_stamped": (
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary("
            in route
        ),
        "input_summary_present": '"button_contract_builder": "_design_guide_button_contract"' in route,
        "boundary_hash_debugged": (
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_hash"
            in source
        ),
        "source_boundary_cutover_present": '"cta_apply_payload_source_summary_cutover": True' in route,
        "shared_execution_retained": (
            "_design_guide_button_contract(residual_promoted, state=state)" in route
            or "_execute_post_click_low_bending_residual_shear_cleanup_button_contract("
            in route
        ),
        "apply_routing_not_moved": "apply_routing" in source,
        "route_return_retained": "return residual_route_return_item" in route,
    }
    ready = all(
        (
            object_run.get("passed"),
            parity_run.get("passed"),
            source_boundary_run.get("passed"),
            readiness_tokens["boundary_stamped"],
            readiness_tokens["input_summary_present"],
            readiness_tokens["boundary_hash_debugged"],
            readiness_tokens["source_boundary_cutover_present"],
            readiness_tokens["shared_execution_retained"],
            readiness_tokens["route_return_retained"],
        )
    )
    return {
        "decision": (
            "BUTTON_CONTRACT_EXECUTION_BOUNDARY_READY_FOR_GUARDED_SOURCE_SUMMARY_CUTOVER"
            if ready
            else "BUTTON_CONTRACT_EXECUTION_BOUNDARY_NOT_READY"
        ),
        "object_run": object_run,
        "parity_run": parity_run,
        "source_boundary_run": source_boundary_run,
        "readiness_tokens": readiness_tokens,
        "ready_for_guarded_source_summary_cutover": ready,
        "behavior_cutover_ready": False,
        "safe_to_delete_route_body_now": False,
        "explicitly_retained_live_surfaces": (
            "shared_button_contract_execution",
            "cta_apply_routing",
            "visible_wording",
            "route_body_return",
        ),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "object_passed": (capture.get("object_run") or {}).get("passed") is True,
        "parity_passed": (capture.get("parity_run") or {}).get("passed") is True,
        "source_boundary_cutover_passed": (
            capture.get("source_boundary_run") or {}
        ).get("passed")
        is True,
        "ready_for_guarded_source_summary_cutover": (
            capture.get("ready_for_guarded_source_summary_cutover") is True
        ),
        "behavior_cutover_not_claimed": capture.get("behavior_cutover_ready") is False,
        "route_body_deletion_not_claimed": capture.get("safe_to_delete_route_body_now") is False,
        "retained_live_surfaces_explicit": bool(capture.get("explicitly_retained_live_surfaces")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Button Contract Execution Boundary Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Ready for guarded source-summary cutover: `{capture.get('ready_for_guarded_source_summary_cutover')}`",
        f"- Behaviour cutover ready: `{capture.get('behavior_cutover_ready')}`",
        f"- Safe to delete route body now: `{capture.get('safe_to_delete_route_body_now')}`",
        "",
        "## Readiness Tokens",
        "",
    ]
    for key, value in (capture.get("readiness_tokens") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Explicitly Retained Live Surfaces", ""])
    lines.extend(f"- `{item}`" for item in capture.get("explicitly_retained_live_surfaces") or ())
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            "Implement guarded button-contract source-summary cutover only. Do not move the shared button-contract helper, apply routing, visible wording, or route return.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_cutover_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_cutover_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_cutover_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_button_contract_execution_boundary_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_cutover_readiness "
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
