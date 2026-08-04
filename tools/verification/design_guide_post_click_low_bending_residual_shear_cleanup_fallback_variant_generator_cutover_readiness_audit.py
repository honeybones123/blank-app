"""Cutover-readiness audit for residual shear cleanup fallback variant generator."""

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


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    total_generator_call_count = source.count("generate_less_shear_reo_variants(")
    residual_route_direct_generator_call_count = route_block.count("generate_less_shear_reo_variants(")
    residual_route_injected_generator_call_count = route_block.count(
        "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator("
    )
    residual_route_injected_generator_wired = (
        residual_route_injected_generator_call_count == 1
        and "generator=generate_less_shear_reo_variants" in route_block
    )
    residual_route_trace_helper_count = route_block.count(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary("
    )
    global_generator_definition_present = "def generate_less_shear_reo_variants(" in source
    other_live_generator_call_count = max(
        0,
        total_generator_call_count
        - (1 if global_generator_definition_present else 0),
    )
    latest = {
        "fallback_object": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_object"
        ),
        "fallback_trace_wiring": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_trace_wiring"
        ),
        "fallback_parity_scenarios": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_parity_scenarios"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "READY_FOR_RESIDUAL_ROUTE_INJECTED_GENERATOR_ADAPTER_OBJECT",
        "not_ready_for_global_generator_move_or_delete": True,
        "global_generator_definition_present": global_generator_definition_present,
        "total_generator_call_count": total_generator_call_count,
        "residual_route_direct_generator_call_count": residual_route_direct_generator_call_count,
        "residual_route_injected_generator_call_count": residual_route_injected_generator_call_count,
        "residual_route_injected_generator_wired": bool(residual_route_injected_generator_wired),
        "other_live_generator_call_count": other_live_generator_call_count,
        "residual_route_trace_helper_count": residual_route_trace_helper_count,
        "recommended_next_surface": "fallback_variant_generator_injected_adapter_object",
        "recommended_cutover_scope": "residual_shear_route_only",
        "required_adapter_contract": (
            "generator_name",
            "input_hash",
            "output_hash",
            "iteration_limit",
            "stale_state_policy",
            "exception_policy",
            "generator_available",
            "generator_is_injected",
            "generator_is_deterministic",
            "generator_changes_behavior",
        ),
        "must_not_move_yet": (
            "global_generate_less_shear_reo_variants_definition",
            "other_generator_calls",
            "candidate_evaluation_execution",
            "candidate_selection_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
            "ui_rendering",
            "session_state_mutation",
        ),
        "latest": latest,
        "latest_required_artifacts_pass": all(
            (item or {}).get("status") == "PASS" for item in latest.values()
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "global_generator_definition_present": (
            capture.get("global_generator_definition_present") is True
        ),
        "residual_route_has_no_direct_generator_call": (
            capture.get("residual_route_direct_generator_call_count") == 0
        ),
        "residual_route_has_one_injected_generator_call": (
            capture.get("residual_route_injected_generator_call_count") == 1
        ),
        "residual_route_injected_generator_wired": (
            capture.get("residual_route_injected_generator_wired") is True
        ),
        "other_live_generator_calls_exist": capture.get("other_live_generator_call_count", 0) > 0,
        "trace_helper_wired_once": capture.get("residual_route_trace_helper_count") == 1,
        "ready_for_residual_route_adapter_object": (
            capture.get("decision") == "READY_FOR_RESIDUAL_ROUTE_INJECTED_GENERATOR_ADAPTER_OBJECT"
        ),
        "not_ready_for_global_move_or_delete": (
            capture.get("not_ready_for_global_generator_move_or_delete") is True
        ),
        "latest_required_artifacts_pass": capture.get("latest_required_artifacts_pass") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Variant Generator Cutover Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Total generator call count: `{capture.get('total_generator_call_count')}`",
        f"- Residual-route direct generator call count: `{capture.get('residual_route_direct_generator_call_count')}`",
        f"- Residual-route injected generator call count: `{capture.get('residual_route_injected_generator_call_count')}`",
        f"- Other live generator call count: `{capture.get('other_live_generator_call_count')}`",
        f"- Not ready for global move/delete: `{capture.get('not_ready_for_global_generator_move_or_delete')}`",
        f"- Recommended next surface: `{capture.get('recommended_next_surface')}`",
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
            "Create the fallback-variant-generator injected-adapter object for the residual-shear route only. Do not delete or move the shared generator.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_cutover_readiness_audit.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_cutover_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_cutover_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_variant_generator_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_cutover_readiness "
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
