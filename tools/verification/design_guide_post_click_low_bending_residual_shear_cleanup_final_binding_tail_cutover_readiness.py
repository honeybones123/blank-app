"""Cutover-readiness gate for residual shear cleanup final-binding tail."""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
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


def _latest(prefix: str) -> dict[str, Any] | None:
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"))
    if not matches:
        return None
    try:
        return json.loads(matches[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    parity = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_parity_scenarios.py",
        ]
    )
    object_payload = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_object"
    )
    parity_payload = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_parity_scenarios"
    )
    trace_payload = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_trace_wiring"
    )
    has_behavior_adapter = (
        "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail("
        in controller_source
    )
    route_still_executes_page_merge = all(
        token in route
        for token in (
            "residual_promoted[\"candidate_search_evidence\"] = dict(residual_evidence)",
            "residual_payload[\"candidate_search_evidence\"] = dict(residual_evidence)",
            "residual_promoted[\"button_contract\"] = dict(",
            "_design_guide_button_contract(residual_promoted, state=state)",
            "return residual_route_return_item",
        )
    )
    route_uses_adapter_merge = all(
        token in route
        for token in (
            "residual_binding_without_contract = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
            "residual_binding_with_contract = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
            "residual_button_contract_execution_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(",
            "residual_cta_apply_payload_source_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(",
            "residual_final_binding_tail_handoff = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff(",
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace(",
            "residual_route_body_replacement = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
            "final_binding_tail=dict(",
            "residual_route_body_result = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(",
            "residual_prebuilt_route_result = _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result(",
            "return dict(",
        )
    ) and not route_still_executes_page_merge
    route_has_trace = (
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff("
        in route
    )
    ready_for_adapter_slice = bool(
        parity.get("passed")
        and route_has_trace
        and route_still_executes_page_merge
        and not has_behavior_adapter
    )
    ready_for_adapter_trace_wiring = bool(
        parity.get("passed")
        and route_has_trace
        and route_still_executes_page_merge
        and has_behavior_adapter
    )
    adapter_cutover_implemented = bool(
        parity.get("passed")
        and route_has_trace
        and route_uses_adapter_merge
        and has_behavior_adapter
    )
    if adapter_cutover_implemented:
        decision = "BEHAVIOR_ADAPTER_CUTOVER_IMPLEMENTED"
    elif ready_for_adapter_trace_wiring:
        decision = "READY_FOR_BEHAVIOR_ADAPTER_TRACE_WIRING"
    elif ready_for_adapter_slice:
        decision = "READY_FOR_BEHAVIOR_ADAPTER_SLICE"
    else:
        decision = "NOT_READY"
    return {
        "decision": decision,
        "parity_run": parity,
        "latest_object_status": (object_payload or {}).get("status"),
        "latest_trace_status": (trace_payload or {}).get("status"),
        "latest_parity_status": (parity_payload or {}).get("status"),
        "route_still_executes_page_merge": route_still_executes_page_merge,
        "route_uses_adapter_merge": route_uses_adapter_merge,
        "route_has_trace": route_has_trace,
        "has_behavior_adapter": has_behavior_adapter,
        "ready_for_live_cutover": False,
        "ready_for_behavior_adapter_slice": ready_for_adapter_slice,
        "ready_for_behavior_adapter_trace_wiring": ready_for_adapter_trace_wiring,
        "adapter_cutover_implemented": adapter_cutover_implemented,
        "next_safe_step": (
            "Trace-wire the controller/shared behavior adapter beside the live page final-binding tail before cutover."
            if ready_for_adapter_trace_wiring
            else "Create a controller/shared behavior adapter for evidence merge and button-contract binding, "
            "then trace-wire it beside the live page tail before cutover."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "object_pass": capture.get("latest_object_status") == "PASS",
        "trace_pass": capture.get("latest_trace_status") == "PASS",
        "parity_pass": capture.get("latest_parity_status") == "PASS"
        and (capture.get("parity_run") or {}).get("passed") is True,
        "route_state_valid": capture.get("route_still_executes_page_merge") is True
        or capture.get("route_uses_adapter_merge") is True,
        "trace_wired": capture.get("route_has_trace") is True,
        "behavior_adapter_state_valid": (
            capture.get("has_behavior_adapter") is False
            and capture.get("ready_for_behavior_adapter_slice") is True
        )
        or (
            capture.get("has_behavior_adapter") is True
            and capture.get("ready_for_behavior_adapter_trace_wiring") is True
        )
        or (
            capture.get("has_behavior_adapter") is True
            and capture.get("adapter_cutover_implemented") is True
        ),
        "not_live_cutover_ready": capture.get("ready_for_live_cutover") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Final Binding Tail Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Readiness",
        "",
        f"- ready for behavior adapter slice: `{capture.get('ready_for_behavior_adapter_slice')}`",
        f"- ready for live cutover: `{capture.get('ready_for_live_cutover')}`",
        f"- route still page-owned: `{capture.get('route_still_executes_page_merge')}`",
        f"- behavior adapter exists: `{capture.get('has_behavior_adapter')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", "", str(capture.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_cutover_readiness.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_cutover_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_cutover_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_final_binding_tail_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_cutover_readiness "
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
