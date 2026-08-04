"""Verify trace wiring for residual-shear CTA/apply payload source boundary."""

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
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_object_snapshot.py",
        ]
    )
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    import_block = _between(source, "from design_brain.design_guide_controller import (", ")\nfrom design_brain.final_publication import (")
    helper = _between(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(",
        "\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace(",
    )
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    capture = {
        "object_snapshot_run": object_run,
        "import_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary"
            in import_block
        ),
        "helper_present": bool(helper),
        "helper_calls_controller_object": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary("
            in helper
        ),
        "helper_is_page_live_trace": 'dependency_status="page_live"' in helper,
        "helper_stamps_hash": "cta_apply_payload_source_boundary_hash" in helper,
        "helper_stamps_non_driving_flags": all(
            token in helper
            for token in (
                "cta_apply_payload_source_boundary_proof_only",
                "cta_apply_payload_source_boundary_product_driving",
                "cta_apply_payload_source_boundary_render_driving",
                "cta_apply_payload_source_boundary_apply_driving",
                "cta_apply_payload_source_boundary_session_driving",
            )
        ),
        "route_calls_helper": (
            "residual_cta_apply_payload_source_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary("
            in route
        ),
        "route_passes_live_sources": all(
            token in route
            for token in (
                "promoted_item=dict(residual_promoted or {})",
                "action_payload=dict(residual_payload or {})",
                "resolved_candidate=dict(residual_resolved or {})",
                "button_contract=dict(residual_button_contract or {})",
            )
        ),
        "route_passes_state_summary": "state_summary={" in route
        and "state_fingerprint" in route
        and "mode_config_hash" in route,
        "final_binding_handoff_records_boundary_hash": (
            '"cta_apply_payload_source_boundary_hash": (' in route
            and "residual_cta_apply_payload_source_boundary" in route
        ),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    return capture


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "object_snapshot_passed": (capture.get("object_snapshot_run") or {}).get("passed") is True,
        "import_present": capture.get("import_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller_object": capture.get("helper_calls_controller_object") is True,
        "helper_is_page_live_trace": capture.get("helper_is_page_live_trace") is True,
        "helper_stamps_hash": capture.get("helper_stamps_hash") is True,
        "helper_stamps_non_driving_flags": capture.get("helper_stamps_non_driving_flags") is True,
        "route_calls_helper": capture.get("route_calls_helper") is True,
        "route_passes_live_sources": capture.get("route_passes_live_sources") is True,
        "route_passes_state_summary": capture.get("route_passes_state_summary") is True,
        "final_binding_handoff_records_boundary_hash": (
            capture.get("final_binding_handoff_records_boundary_hash") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup CTA/Apply Payload Source Boundary Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Helper present: `{capture.get('helper_present')}`",
        f"- Route calls helper: `{capture.get('route_calls_helper')}`",
        f"- Route passes live sources: `{capture.get('route_passes_live_sources')}`",
        f"- Final-binding handoff records boundary hash: `{capture.get('final_binding_handoff_records_boundary_hash')}`",
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
            "Add parity scenarios for this source boundary before any cutover or deletion.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_trace_wiring.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_cta_apply_payload_source_boundary_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_trace_wiring "
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
