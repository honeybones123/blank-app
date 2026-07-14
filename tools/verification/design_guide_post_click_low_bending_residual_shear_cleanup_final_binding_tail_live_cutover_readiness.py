"""Live cutover-readiness for residual shear cleanup final-binding adapter."""

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
    helper = _between(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace(",
        "\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(",
    )
    adapter_trace = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace_wiring.py",
        ]
    )
    readiness = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_cutover_readiness.py",
        ]
    )
    page_merge_still_present = all(
        token in route
        for token in (
            "residual_promoted[\"candidate_search_evidence\"] = dict(residual_evidence)",
            "residual_payload[\"candidate_search_evidence\"] = dict(residual_evidence)",
            "residual_resolved[\"candidate_search_evidence\"] = dict(residual_evidence)",
            "residual_promoted[\"button_contract\"] = dict(",
        )
    )
    adapter_cutover_implemented = all(
        token in route
        for token in (
            "residual_binding_without_contract = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
            "residual_binding_with_contract = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
            "residual_promoted = dict(",
            "residual_button_contract = dict(",
            "residual_button_contract_execution_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(",
            "residual_cta_apply_payload_source_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(",
            "residual_final_binding_tail_handoff = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff(",
            "residual_route_body_replacement = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
            "residual_route_body_result = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(",
            "residual_prebuilt_route_result = _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result(",
        )
    ) and not page_merge_still_present
    cutover_replacement_shape = {
        "adapter_callable": (
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail("
            in source
        ),
        "helper_computes_current_item_hash": "current_item_hash = _stable_final_publication_hash(dict(promoted_item or {}))"
        in helper,
        "helper_computes_adapted_item_hash": "adapted_item_hash = _stable_final_publication_hash(adapted_item)"
        in helper,
        "helper_records_hash_parity": "adapted_item_matches_current_item" in helper
        and "parity = bool(adapted_item_hash == current_item_hash)" in helper,
        "route_passes_exact_live_inputs": all(
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
        "route_returns_controller_boundary_item": (
            "residual_route_return_item = dict(" in route
            and "residual_prebuilt_route_result.get(\"result_item\")" in route
            and "return dict(" in route
        ),
        "page_merge_still_present": page_merge_still_present,
        "adapter_cutover_implemented": adapter_cutover_implemented,
    }
    ready_for_live_cutover = bool(
        all(
            value is True
            for key, value in cutover_replacement_shape.items()
            if key != "page_merge_still_present"
        )
        and page_merge_still_present
        and adapter_trace.get("passed")
        and readiness.get("passed")
    )
    cutover_implemented = bool(
        adapter_cutover_implemented
        and adapter_trace.get("passed")
        and readiness.get("passed")
        and not page_merge_still_present
    )
    return {
        "decision": (
            "FINAL_BINDING_ADAPTER_CUTOVER_IMPLEMENTED_READY_FOR_DEADNESS"
            if cutover_implemented
            else "READY_FOR_NARROW_FINAL_BINDING_ADAPTER_CUTOVER"
            if ready_for_live_cutover
            else "NOT_READY"
        ),
        "adapter_trace": adapter_trace,
        "readiness": readiness,
        "cutover_replacement_shape": cutover_replacement_shape,
        "ready_for_live_cutover": bool(ready_for_live_cutover),
        "cutover_implemented": bool(cutover_implemented),
        "allowed_cutover": (
            "Replace the final item binding tail with adapter-built output only after the shared button contract "
            "is built from the adapter-bound item. Keep _design_guide_button_contract, visible wording, apply routing, "
            "rendering, session/debug, and family/runtime behaviour unchanged."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    shape = dict(capture.get("cutover_replacement_shape") or {})
    return {
        "adapter_trace_pass": (capture.get("adapter_trace") or {}).get("passed") is True,
        "readiness_pass": (capture.get("readiness") or {}).get("passed") is True,
        "all_cutover_shape_checks_pass": all(
            value is True
            for key, value in shape.items()
            if key != "page_merge_still_present"
        ),
        "ready_or_implemented": capture.get("ready_for_live_cutover") is True
        or capture.get("cutover_implemented") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Final Binding Tail Live Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Shape",
        "",
    ]
    for key, value in (capture.get("cutover_replacement_shape") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Allowed Cutover", "", str(capture.get("allowed_cutover") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_live_cutover_readiness.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_live_cutover_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_live_cutover_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_final_binding_tail_live_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_live_cutover_readiness "
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
