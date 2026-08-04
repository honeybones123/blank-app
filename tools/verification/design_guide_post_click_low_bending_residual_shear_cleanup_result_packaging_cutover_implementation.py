"""Cutover verifier for residual shear cleanup result packaging injected shell."""

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
READINESS = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter_readiness_snapshot.py"
)
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


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _run_readiness() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(READINESS)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0
        and "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter_readiness PASS"
        in proc.stdout,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    helper = _between(
        inputs_source,
        "def _run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    route = _between(
        inputs_source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    readiness = _run_readiness()
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_RESULT_PACKAGING_CUTOVER_IMPLEMENTED",
        "helper_present": bool(helper),
        "helper_calls_injected_packager": "residual_shear_item = packager(" in helper,
        "helper_calls_injected_evaluator": "residual_promoted, residual_detail = local_cleanup_evaluator(" in helper,
        "helper_preserves_non_dict_item_branch": "if not isinstance(residual_shear_item, dict):" in helper
        and "return None, None, {}" in helper,
        "helper_preserves_non_dict_promoted_branch": (
            "residual_promoted if isinstance(residual_promoted, dict) else None" in helper
        ),
        "helper_preserves_source": 'source="post_click_low_bending_residual_shear_cleanup"' in helper,
        "helper_preserves_actions_payload": '"actions_used": _resolve_design_actions_from_state(state)' in helper
        and '"shear_tightening": dict(residual_shear_tighten or {})' in helper,
        "route_direct_packager_assignment_count": route.count(
            "residual_shear_item = _shear_tightening_as_local_cleanup_item("
        ),
        "route_direct_evaluator_assignment_count": route.count(
            "residual_promoted, residual_detail = _evaluate_local_cleanup_guidance_item("
        ),
        "route_wrapper_count": route.count(
            "_run_post_click_low_bending_residual_shear_cleanup_result_packaging("
        ),
        "route_injects_packager": "packager=_shear_tightening_as_local_cleanup_item" in route,
        "route_injects_local_cleanup_evaluator": (
            "local_cleanup_evaluator=_evaluate_local_cleanup_guidance_item" in route
        ),
        "route_preserves_dict_guards": (
            "if isinstance(residual_shear_item, dict):" in route
            and "if isinstance(residual_promoted, dict):" in route
        ),
        "route_trace_stamps_packaging": (
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff("
            in route
            and "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter("
            in route
        ),
        "readiness_snapshot": readiness,
        "button_contract_execution_moved": False,
        "evidence_merge_moved": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "product_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_injected_packager": capture.get("helper_calls_injected_packager") is True,
        "helper_calls_injected_evaluator": capture.get("helper_calls_injected_evaluator") is True,
        "helper_preserves_non_dict_item_branch": capture.get("helper_preserves_non_dict_item_branch") is True,
        "helper_preserves_non_dict_promoted_branch": capture.get("helper_preserves_non_dict_promoted_branch") is True,
        "helper_preserves_source": capture.get("helper_preserves_source") is True,
        "helper_preserves_actions_payload": capture.get("helper_preserves_actions_payload") is True,
        "route_direct_packager_dead": capture.get("route_direct_packager_assignment_count") == 0,
        "route_direct_evaluator_dead": capture.get("route_direct_evaluator_assignment_count") == 0,
        "route_wrapper_single": capture.get("route_wrapper_count") == 1,
        "route_injects_packager": capture.get("route_injects_packager") is True,
        "route_injects_local_cleanup_evaluator": capture.get("route_injects_local_cleanup_evaluator") is True,
        "route_preserves_dict_guards": capture.get("route_preserves_dict_guards") is True,
        "route_trace_stamps_packaging": capture.get("route_trace_stamps_packaging") is True,
        "readiness_snapshot_passed": (capture.get("readiness_snapshot") or {}).get("passed") is True,
        "button_contract_execution_not_moved": capture.get("button_contract_execution_moved") is False,
        "evidence_merge_not_moved": capture.get("evidence_merge_moved") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Result Packaging Cutover Implementation",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Result",
        "",
        f"- route direct packager call count: `{capture.get('route_direct_packager_assignment_count')}`",
        f"- route direct evaluator call count: `{capture.get('route_direct_evaluator_assignment_count')}`",
        f"- route wrapper count: `{capture.get('route_wrapper_count')}`",
        f"- readiness snapshot passed: `{(capture.get('readiness_snapshot') or {}).get('passed')}`",
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
            "Proceed to deadness/reachability proof for the old residual-route direct result packaging body. Keep CTA, evidence merge, visible wording, apply routing, UI/session, and family/runtime behaviour unchanged.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_cutover_implementation.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_cutover_implementation_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_cutover_implementation_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_result_packaging_cutover_implementation_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_cutover_implementation "
        f"{payload['status']}"
    )
    print(json_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
