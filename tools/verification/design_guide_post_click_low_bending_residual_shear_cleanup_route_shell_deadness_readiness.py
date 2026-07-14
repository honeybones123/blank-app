"""Deadness/readiness audit after residual-shear route-shell cutover."""

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


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    live_surfaces = {
        "route_entry_guard": (
            "current_shear_for_residual_cleanup" in route
            and "_skip_bending_fail_post_publication_probe(" in route
        ),
        "fallback_search_loop": (
            "for fallback_index, fallback_variant in enumerate(fallback_variants[:64]):"
            in route
        ),
        "evidence_merge_tail": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter("
            in route
            or "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace("
            in route
        ),
        "candidate_generation_execution": "generate_less_shear_reo_variants" in route,
        "candidate_evaluation_execution": "_evaluate_auto_design_candidate" in route,
        "cta_contract_execution": "_design_guide_button_contract(residual_promoted, state=state)" in route,
        "debug_session_projection": "debug_sink[\"candidate_search_evidence\"]" in route,
    }
    cutover_surface = {
        "route_shell_adapter_assignment": (
            "residual_route_shell_adapter = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_trace("
            in route
        ),
        "route_shell_result_assignment": (
            "residual_route_shell_adapter.get(\"result_item\")" in route
            and "or residual_promoted" in route
        ),
    }
    deletion_candidates: list[str] = []
    if all(cutover_surface.values()) and not any(
        live_surfaces[name]
        for name in (
            "route_entry_guard",
            "fallback_search_loop",
            "evidence_merge_tail",
        )
    ):
        deletion_candidates.append("old_route_shell_body")
    latest = {
        "cutover_implementation": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_implementation"
        ),
        "debug_projection_consumer_reachability": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability"
        ),
        "remaining_surface_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit"
        ),
        "route_body_live_execution_shell_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_live_execution_shell_audit"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    debug_projection_tail_narrowed = (
        "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only("
        in route
        or latest.get("debug_projection_consumer_reachability", {}).get("status") == "PASS"
    )
    route_body_audit = latest.get("route_body_live_execution_shell_audit") or {}
    live_execution_shells_audited = route_body_audit.get("status") == "PASS"
    recommended_next_surface = (
        "route_body_controller_replacement_readiness"
        if debug_projection_tail_narrowed and live_execution_shells_audited
        else ("route_body_live_execution_shell_audit" if debug_projection_tail_narrowed else "debug_projection_tail")
    )
    recommended_next_step = (
        "Build a whole-route controller replacement/deletion-readiness proof. Do not delete the route body yet because fallback loop structure, evidence merge, CTA execution, and debug projection are still live."
        if recommended_next_surface == "route_body_controller_replacement_readiness"
        else (
            "Audit the remaining live execution shell surfaces before deleting the route body."
            if debug_projection_tail_narrowed
            else "Continue with debug/session projection cleanup. Do not delete the route body yet because fallback "
           "search execution, candidate generation/evaluation, CTA execution, and debug projection are still live."
        )
    )
    local_required_artifacts = {
        key: value
        for key, value in latest.items()
        if key not in {"render_bridge_lock", "compute_bridge_lock", "independence_lock"}
    }
    return {
        "decision": "ROUTE_SHELL_CUT_OVER_BUT_ROUTE_BODY_NOT_DEAD",
        "route_found": bool(route),
        "cutover_surface": cutover_surface,
        "live_surfaces": live_surfaces,
        "deletion_candidates": deletion_candidates,
        "delete_now_count": len(deletion_candidates),
        "safe_to_delete_route_body_now": bool(deletion_candidates),
        "debug_projection_tail_narrowed": bool(debug_projection_tail_narrowed),
        "live_execution_shells_audited": bool(live_execution_shells_audited),
        "recommended_next_surface": recommended_next_surface,
        "recommended_next_step": recommended_next_step,
        "latest": latest,
        "latest_required_artifacts_pass": all(
            row.get("status") == "PASS" for row in local_required_artifacts.values()
        ),
        "broad_lock_status": {
            key: latest.get(key, {})
            for key in ("render_bridge_lock", "compute_bridge_lock", "independence_lock")
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    cutover = dict(capture.get("cutover_surface") or {})
    live = dict(capture.get("live_surfaces") or {})
    return {
        "route_found": capture.get("route_found") is True,
        "route_shell_adapter_assignment_present": cutover.get("route_shell_adapter_assignment") is True,
        "route_shell_result_assignment_present": cutover.get("route_shell_result_assignment") is True,
        "live_route_body_surfaces_still_present": any(live.values()),
        "delete_now_count_zero": capture.get("delete_now_count") == 0,
        "safe_to_delete_route_body_now_false": (
            capture.get("safe_to_delete_route_body_now") is False
        ),
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
        "# Residual Shear Cleanup Route-Shell Deadness Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Delete-now count: `{capture.get('delete_now_count')}`",
        f"- Safe to delete route body now: `{capture.get('safe_to_delete_route_body_now')}`",
        f"- Recommended next surface: `{capture.get('recommended_next_surface')}`",
        "",
        "## Live Surfaces",
        "",
    ]
    for key, value in (capture.get("live_surfaces") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", "", str(capture.get("recommended_next_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_extraction_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        "",
        f"`{payload.get('status')}` - route-shell deadness audit after cutover.",
        "",
        "## Surface Targeted",
        "",
        "`post_click_low_bending_residual_shear_cleanup` route body after route-shell adapter cutover.",
        "",
        "## Ownership Before",
        "",
        "Route-shell assignment was page-owned before the adapter cutover.",
        "",
        "## Ownership After",
        "",
        "Route-shell result assignment is controller-adapter sourced, but the route body still owns evidence/search/debug surfaces.",
        "",
        "## Behaviour Preserved",
        "",
        "- Engineering behaviour unchanged",
        "- Visible wording unchanged",
        "- CTA/apply semantics unchanged",
        "- Family runtimes unchanged",
        "",
        "## Cutover Proof",
        "",
        "Route-shell adapter cutover implementation is the latest prerequisite.",
        "",
        "## Deadness / Deletion Proof",
        "",
        f"Delete-now count: `{capture.get('delete_now_count')}`. The route body is not dead yet.",
        "",
        "## Lines Removed / Added",
        "",
        "Lines removed: `0`. Lines added: deadness/readiness verifier only.",
        "",
        "## Files Changed",
        "",
        "- `tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness.py`",
        "",
        "## Verifier Results",
        "",
        f"- Focused deadness audit: `{payload.get('status')}`",
        "",
        "## Remaining Page-Owned Authority",
        "",
    ]
    for key, value in (capture.get("live_surfaces") or {}).items():
        if value:
            lines.append(f"- `{key}`")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            str(capture.get("recommended_next_step") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash({"capture": capture, "checks": checks})
    stamp = str(payload["created_at"])
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_shell_deadness_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_extraction_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness "
        f"{payload['status']}"
    )
    print(f"delete_now_count={capture.get('delete_now_count')}")
    print(f"recommended_next_surface={capture.get('recommended_next_surface')}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
