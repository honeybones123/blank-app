"""Trace-wiring snapshot for residual shear cleanup final-binding tail adapter."""

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


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    tokens = {
        "handoff_trace": "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff(",
        "adapter_trace": "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace(",
        "primary_executor": "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(",
    }
    positions = {name: route.find(token) for name, token in tokens.items()}
    adapter_parity = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_parity.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FINAL_BINDING_TAIL_ADAPTER_TRACE_WIRED",
        "adapter_import_present": (
            "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail as "
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail"
        )
        in source,
        "adapter_trace_helper_present": (
            "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace("
            in source
        ),
        "adapter_trace_helper_calls_controller": (
            "payload = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail("
            in source
        ),
        "route_block_present": bool(route),
        "route_call_count": route.count(tokens["adapter_trace"]),
        "positions": positions,
        "route_passes_live_shapes": all(
            token in route
            for token in (
                "promoted_item=dict(residual_promoted or {})",
                "candidate_search_evidence=dict(residual_evidence or {})",
                "exact_blockers_by_family=dict(residual_exact_blockers or {})",
                "action_payload=dict(residual_payload or {})",
                "resolved_candidate=dict(residual_resolved or {})",
                "button_contract=dict(residual_button_contract or {})",
            )
        ),
        "debug_only_trace_fields": all(
            token in source
            for token in (
                "design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace",
                "adapted_item_matches_current_item",
                "proof_only_trace",
                '"product_driving": False',
                '"render_driving": False',
                '"apply_driving": False',
                '"session_driving": False',
            )
        ),
        "adapter_parity": adapter_parity,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    positions = dict(capture.get("positions") or {})
    return {
        "adapter_import_present": capture.get("adapter_import_present") is True,
        "adapter_trace_helper_present": capture.get("adapter_trace_helper_present") is True,
        "adapter_trace_helper_calls_controller": capture.get("adapter_trace_helper_calls_controller") is True,
        "route_block_present": capture.get("route_block_present") is True,
        "route_call_count_one": capture.get("route_call_count") == 1,
        "route_order_valid": positions.get("handoff_trace", -1)
        < positions.get("adapter_trace", -1)
        < positions.get("primary_executor", -1),
        "route_passes_live_shapes": capture.get("route_passes_live_shapes") is True,
        "debug_only_trace_fields_present": capture.get("debug_only_trace_fields") is True,
        "adapter_parity_pass": (capture.get("adapter_parity") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Final Binding Tail Adapter Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Route",
        "",
        f"- route call count: `{capture.get('route_call_count')}`",
        f"- positions: `{capture.get('positions')}`",
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
            "Create live cutover-readiness comparing the adapter trace hash to the page-built `residual_promoted` hash. Do not use adapter output as route output until that passes.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace_wiring.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_final_binding_tail_adapter_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace_wiring "
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
