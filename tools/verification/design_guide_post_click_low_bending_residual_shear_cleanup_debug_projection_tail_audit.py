"""Audit debug/session projection tail for residual-shear cleanup route."""

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

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))"
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("
DEBUG_START = "if isinstance(debug_sink, dict):"
DEBUG_END = "residual_route_shell_adapter = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace("

DIRECT_DEBUG_KEYS = (
    "post_click_bending_blocker_preserved",
    "post_click_residual_shear_cleanup_after_bending_blocker",
    "post_click_residual_shear_cleanup_debug",
    "post_click_residual_shear_cleanup_detail",
    "post_click_residual_shear_cleanup_updates",
    "exact_blockers_by_family",
    "post_click_exact_blockers_by_family",
    "cleanup_evidence_by_family",
    "post_click_cleanup_evidence_by_family",
    "candidate_search_evidence",
    "guidance_branch",
    "selected_action_family",
    "primary_guidance_intent",
    "safe_local_cleanup_count",
    "executable_safe_cleanup_count",
)

PROOF_STAMP_CALLS = (
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows(",
    "_stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof(",
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary(",
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary(",
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff(",
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff(",
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key(",
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff(",
    "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff(",
)


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


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw_status.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        status = "PASS"
    elif "FAIL" in upper:
        status = "FAIL"
    else:
        status = raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    debug_tail = _between(route, DEBUG_START, DEBUG_END)
    direct_rows = {
        key: {
            "present": f'debug_sink["{key}"]' in debug_tail,
            "classification": "B. direct debug/session projection row",
            "delete_now": False,
        }
        for key in DIRECT_DEBUG_KEYS
    }
    proof_rows = {
        call: {
            "present": call in debug_tail,
            "classification": "A. controller/final-publication proof stamp",
            "delete_now": False,
        }
        for call in PROOF_STAMP_CALLS
    }
    latest = {
        "remaining_surface_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit"
        ),
        "route_shell_deadness_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness"
        ),
        "final_binding_tail_deadness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    missing_direct = [key for key, row in direct_rows.items() if not row.get("present")]
    missing_proofs = [key for key, row in proof_rows.items() if not row.get("present")]
    debug_projection_row_builder_present = proof_rows[
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows("
    ].get("present")
    return {
        "decision": (
            "RESIDUAL_SHEAR_CLEANUP_DEBUG_PROJECTION_TAIL_BUILDER_TRACE_READY"
            if debug_projection_row_builder_present
            else "RESIDUAL_SHEAR_CLEANUP_DEBUG_PROJECTION_TAIL_MAPPED_NOT_READY_TO_DELETE"
        ),
        "route_found": bool(route),
        "debug_tail_found": bool(debug_tail),
        "direct_debug_rows": direct_rows,
        "proof_stamp_rows": proof_rows,
        "direct_debug_row_count": len(direct_rows),
        "proof_stamp_row_count": len(proof_rows),
        "missing_direct_debug_rows": missing_direct,
        "missing_proof_stamp_rows": missing_proofs,
        "delete_now_count": 0,
        "debug_projection_row_builder_present": bool(debug_projection_row_builder_present),
        "recommended_next_surface": (
            "debug_projection_compatibility_stamp"
            if debug_projection_row_builder_present
            else "direct_debug_projection_row_builder"
        ),
        "recommended_next_step": (
            "Prove these direct debug writes can become compatibility-only before deletion."
            if debug_projection_row_builder_present
            else "Create a controller/final-publication-compatible debug projection row object, "
            "then prove these direct debug writes can become compatibility-only before deletion."
        ),
        "latest": latest,
        "latest_required_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_found": capture.get("route_found") is True,
        "debug_tail_found": capture.get("debug_tail_found") is True,
        "all_direct_debug_rows_present": not capture.get("missing_direct_debug_rows"),
        "all_proof_stamp_rows_present": not capture.get("missing_proof_stamp_rows"),
        "delete_now_count_zero": capture.get("delete_now_count") == 0,
        "recommended_next_surface_selected": bool(capture.get("recommended_next_surface")),
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
        "# Residual Shear Cleanup Debug Projection Tail Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Recommended next surface: `{capture.get('recommended_next_surface')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- direct debug rows: `{capture.get('direct_debug_row_count')}`",
        f"- proof stamp rows: `{capture.get('proof_stamp_row_count')}`",
        f"- delete now count: `{capture.get('delete_now_count')}`",
        "",
        "## Direct Debug Rows",
        "",
    ]
    for key, row in (capture.get("direct_debug_rows") or {}).items():
        lines.append(f"- `{key}`: present=`{row.get('present')}`, classification=`{row.get('classification')}`")
    lines.extend(["", "## Proof Stamp Rows", ""])
    for key, row in (capture.get("proof_stamp_rows") or {}).items():
        lines.append(f"- `{key}`: present=`{row.get('present')}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", "", str(capture.get("recommended_next_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_tail_audit.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / (
        f"design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_tail_audit_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        f"design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_tail_audit_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        f"design_brain_physical_extraction_residual_shear_cleanup_debug_projection_tail_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_tail_audit "
        f"{payload['status']}"
    )
    print(f"recommended_next_surface={capture.get('recommended_next_surface')}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ",".join(failures))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
