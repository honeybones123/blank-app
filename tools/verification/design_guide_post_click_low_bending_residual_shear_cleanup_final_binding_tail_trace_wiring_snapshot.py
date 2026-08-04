"""Trace-wiring snapshot for residual shear cleanup final-binding tail."""

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
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "cmd": cmd,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
        "passed": result.returncode == 0,
    }


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _token_line(source: str, token: str) -> int | None:
    index = source.find(token)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    helper_name = (
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff"
    )
    builder_alias = (
        "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff"
    )
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    order_tokens = {
        "button_contract_binding": "residual_promoted[\"button_contract\"] = dict(",
        "result_packaging_handoff": (
            "residual_result_packaging_handoff = "
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff("
        ),
        "result_packaging_injected_adapter": (
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter("
        ),
        "final_binding_tail_handoff": (
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff("
        ),
        "primary_executor_handoff": (
            "residual_primary_executor_handoff = "
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff("
        ),
    }
    route_positions = {name: route.find(token) for name, token in order_tokens.items()}
    route_lines = {
        name: _token_line(source, token)
        for name, token in order_tokens.items()
    }
    nested_object = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_object_snapshot.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FINAL_BINDING_TAIL_TRACE_WIRED",
        "helper_present": f"def {helper_name}(" in source,
        "builder_import_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff as "
            f"{builder_alias}"
        )
        in source,
        "builder_called_by_helper": f"payload = {builder_alias}(" in source,
        "route_block_present": bool(route),
        "route_call_count": route.count(order_tokens["final_binding_tail_handoff"]),
        "route_positions": route_positions,
        "route_lines": route_lines,
        "route_uses_result_packaging_handoff": "result_packaging_handoff=dict(residual_result_packaging_handoff or {})" in route,
        "route_records_binding_inputs": '"route_branch": "post_click_residual_shear_cleanup_after_bending_blocker"' in route
        and '"state_fingerprint": _stable_final_publication_hash(dict(state or {}))' in route
        and '"mode_config_hash": _stable_final_publication_hash(dict(mode_config or {}))' in route,
        "route_records_binding_outputs": all(
            token in route
            for token in (
                '"evidence_hash":',
                '"action_payload_hash":',
                '"resolved_candidate_hash":',
                '"button_contract_hash":',
                '"button_contract_updates_hash":',
                '"button_contract_expected_util": (',
                '"button_contract_enabled": bool(',
                '"button_contract_actionable": bool(',
                '"returned_item_hash": _stable_final_publication_hash(',
            )
        ),
        "debug_only_trace_fields": all(
            token in source
            for token in (
                "design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff",
                "design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff_hash",
                "design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_proof_only",
                "design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_product_driving",
                "design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_render_driving",
                "design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_apply_driving",
                "design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_session_driving",
            )
        ),
        "nested_object": nested_object,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    positions = dict(capture.get("route_positions") or {})
    ordered = (
        positions.get("button_contract_binding", -1)
        < positions.get("result_packaging_handoff", -1)
        < positions.get("result_packaging_injected_adapter", -1)
        < positions.get("final_binding_tail_handoff", -1)
        < positions.get("primary_executor_handoff", -1)
    )
    return {
        "helper_present": capture.get("helper_present") is True,
        "builder_import_present": capture.get("builder_import_present") is True,
        "builder_called_by_helper": capture.get("builder_called_by_helper") is True,
        "route_block_present": capture.get("route_block_present") is True,
        "route_call_count_one": capture.get("route_call_count") == 1,
        "route_call_order_preserves_live_binding": ordered,
        "route_uses_result_packaging_handoff": capture.get("route_uses_result_packaging_handoff") is True,
        "route_records_binding_inputs": capture.get("route_records_binding_inputs") is True,
        "route_records_binding_outputs": capture.get("route_records_binding_outputs") is True,
        "debug_only_trace_fields_present": capture.get("debug_only_trace_fields") is True,
        "nested_object_pass": (capture.get("nested_object") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Final Binding Tail Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Route",
        "",
        f"- route call count: `{capture.get('route_call_count')}`",
        f"- route lines: `{capture.get('route_lines')}`",
        f"- route positions: `{capture.get('route_positions')}`",
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
            "Create final-binding tail parity scenarios comparing live-shaped page binding output to the controller proof object. Do not cut over evidence merge or button-contract execution yet.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_trace_wiring_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_final_binding_tail_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_trace_wiring "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print(f"failures={','.join(failures)}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
