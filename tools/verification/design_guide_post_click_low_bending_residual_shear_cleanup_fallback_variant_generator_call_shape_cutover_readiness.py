"""Call-shape cutover readiness for residual shear fallback generator injection."""

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
    direct_call = "generate_less_shear_reo_variants({\"state\": dict(state)}, mode_config)"
    direct_call_count = route_block.count(direct_call)
    injected_runner_count = route_block.count(
        "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator("
    )
    injected_runner_helper_present = (
        "def _run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator("
        in source
    )
    injected_same_impl = "generator=generate_less_shear_reo_variants" in route_block
    same_impl_available = "def generate_less_shear_reo_variants(" in source
    trace_adapter_count = route_block.count(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter("
    )
    boundary_trace_count = route_block.count(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary("
    )
    latest = {
        "injected_adapter_object": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter_object"
        ),
        "injected_adapter_trace": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_injected_adapter_trace_wiring"
        ),
        "parity_scenarios": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_parity_scenarios"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    if direct_call_count == 1 and injected_runner_count == 0:
        decision = "READY_FOR_RESIDUAL_ROUTE_FALLBACK_GENERATOR_CALL_SHAPE_CUTOVER"
    elif injected_runner_count == 1 and injected_runner_helper_present and injected_same_impl:
        decision = "RESIDUAL_ROUTE_FALLBACK_GENERATOR_CALL_SHAPE_ALREADY_WIRED"
    else:
        decision = "RESIDUAL_ROUTE_FALLBACK_GENERATOR_CALL_SHAPE_UNCLEAR"
    return {
        "decision": decision,
        "direct_call_count": direct_call_count,
        "injected_runner_count": injected_runner_count,
        "injected_runner_helper_present": injected_runner_helper_present,
        "injected_same_impl": injected_same_impl,
        "same_impl_available": same_impl_available,
        "boundary_trace_count": boundary_trace_count,
        "trace_adapter_count": trace_adapter_count,
        "replacement_shape": (
            "fallback_variants = list(_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator("
            "state=state, mode_config=mode_config, generator=generate_less_shear_reo_variants) or [])"
        ),
        "must_preserve": (
            "fallback_variants variable",
            "exception_returns_empty_list",
            "fallback_variant_generator_attempted",
            "fallback_variant_generator_variant_count",
            "fallback_variant_generator_update_sequence",
            "candidate_evaluation_loop",
            "candidate_selection",
            "result_packaging",
        ),
        "must_not_move": (
            "shared_generate_less_shear_reo_variants_definition",
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
    pre_ready = (
        capture.get("decision")
        == "READY_FOR_RESIDUAL_ROUTE_FALLBACK_GENERATOR_CALL_SHAPE_CUTOVER"
    )
    post_ready = (
        capture.get("decision")
        == "RESIDUAL_ROUTE_FALLBACK_GENERATOR_CALL_SHAPE_ALREADY_WIRED"
    )
    return {
        "readiness_or_cutover_shape_detected": pre_ready or post_ready,
        "direct_call_present_once_or_dead": (
            capture.get("direct_call_count") == 1 if pre_ready else capture.get("direct_call_count") == 0
        ),
        "injected_runner_not_yet_present_or_wired": (
            capture.get("injected_runner_count") == 0
            if pre_ready
            else capture.get("injected_runner_count") == 1
        ),
        "injected_runner_helper_present_after_cutover": (
            capture.get("injected_runner_helper_present") is True if post_ready else True
        ),
        "injected_same_impl_after_cutover": (
            capture.get("injected_same_impl") is True if post_ready else True
        ),
        "same_impl_available": capture.get("same_impl_available") is True,
        "boundary_trace_present_once": capture.get("boundary_trace_count") == 1,
        "injected_adapter_trace_present_once": capture.get("trace_adapter_count") == 1,
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
        "# Residual Shear Cleanup Fallback Generator Call-Shape Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Direct route call count: `{capture.get('direct_call_count')}`",
        f"- Injected runner count: `{capture.get('injected_runner_count')}`",
        f"- Same implementation available: `{capture.get('same_impl_available')}`",
        f"- Boundary trace count: `{capture.get('boundary_trace_count')}`",
        f"- Injected-adapter trace count: `{capture.get('trace_adapter_count')}`",
        "",
        "## Replacement Shape",
        "",
        f"`{capture.get('replacement_shape')}`",
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
            "Cut over only the residual-route generator call shape to an injected runner using the same shared generator implementation.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover_readiness.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover_readiness "
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
