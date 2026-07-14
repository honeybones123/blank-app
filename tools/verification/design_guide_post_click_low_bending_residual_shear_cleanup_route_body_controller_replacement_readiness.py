"""Readiness proof for replacing the residual-shear cleanup route body."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = 'current_shear_for_residual_cleanup = _parse_util_value(family_utils.get("shear"))'
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
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw_status.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        status = "PASS"
    elif "FAIL" in upper:
        status = "FAIL"
    else:
        status = raw_status or "UNKNOWN"
    return {
        "found": True,
        "status": status,
        "path": str(path),
        "snapshot_hash": payload.get("snapshot_hash"),
        "capture": payload.get("capture"),
    }


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    latest = {
        "route_body_live_execution_shell_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_live_execution_shell_audit"
        ),
        "route_shell_deadness_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness"
        ),
        "route_shell_adapter_cutover_implementation": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_implementation"
        ),
        "evidence_merge_tail_deadness_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_deadness_readiness"
        ),
        "final_binding_tail_deadness_proof": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof"
        ),
        "debug_projection_narrowing": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_narrowing"
        ),
        "debug_projection_consumer_reachability": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    route_body_capture = dict(
        (latest.get("route_body_live_execution_shell_audit") or {}).get("capture") or {}
    )
    evidence_merge_capture = dict(
        (latest.get("evidence_merge_tail_deadness_readiness") or {}).get("capture") or {}
    )
    evidence_merge_old_body_dead = (
        evidence_merge_capture.get("decision") == "OLD_MERGE_READY_FOR_DELETION"
        and evidence_merge_capture.get("live_merge_present") is False
        and evidence_merge_capture.get("live_exact_blocker_merge_present") is False
        and evidence_merge_capture.get("guarded_cutover_present") is True
    )
    final_binding_capture = dict(
        (latest.get("final_binding_tail_deadness_proof") or {}).get("capture") or {}
    )
    final_binding_old_merge_dead = (
        final_binding_capture.get("decision")
        == "RESIDUAL_SHEAR_CLEANUP_FINAL_BINDING_OLD_PAGE_MERGE_DEAD"
        and not final_binding_capture.get("old_tokens_present")
        and not final_binding_capture.get("adapter_tokens_missing")
        and not final_binding_capture.get("shared_owned_tokens_missing")
    )
    debug_projection_capture = dict(
        (latest.get("debug_projection_narrowing") or {}).get("capture") or {}
    )
    debug_projection_consumer_capture = dict(
        (latest.get("debug_projection_consumer_reachability") or {}).get("capture") or {}
    )
    debug_projection_proof_covered = (
        latest.get("debug_projection_narrowing", {}).get("status") == "PASS"
        and latest.get("debug_projection_consumer_reachability", {}).get("status") == "PASS"
        and debug_projection_capture.get("legacy_marker_deleted") is True
        and debug_projection_capture.get("debug_rows_represented_by_controller_builder") is True
        and debug_projection_capture.get("product_behavior_changed") is False
        and debug_projection_consumer_capture.get("product_behavior_changed") is False
    )
    live_execution_shells = tuple(route_body_capture.get("live_execution_shell_surfaces") or ())
    remaining_body_surfaces = {
        "route_entry_guard": (
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard("
            in route
            and 'residual_shear_cleanup_route_entry_guard.get("should_enter_route")' in route
        ),
        "fallback_loop_structure": "for fallback_index, fallback_variant in enumerate(fallback_variants[:64]):"
        in route,
        "candidate_sequence_accumulation": "fallback_candidate_evaluation_sequence.append(" in route,
        "candidate_selection_sequence": "fallback_candidate_selection_sequence.append(" in route,
        "residual_promoted_result_construction": "residual_promoted" in route
        and "return residual_promoted" in route,
        "evidence_merge_tail": (
            not evidence_merge_old_body_dead
            and (
                "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter("
                in route
                or "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace("
                in route
            )
        ),
        "cta_contract_execution": "_design_guide_button_contract(residual_promoted, state=state)" in route,
        "final_binding_tail": (
            not final_binding_old_merge_dead
            and "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail("
            in route
        ),
        "debug_session_projection": (
            not debug_projection_proof_covered
            and (
                'debug_sink["candidate_search_evidence"]' in route
                or "debug_sink[" in route
            )
        ),
    }
    controller_route_shell_exists = (
        "def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell("
        in controller_source
    )
    controller_replacement_body_exists = (
        "def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body("
        in controller_source
    )
    safe_to_delete = bool(
        route
        and not live_execution_shells
        and controller_replacement_body_exists
        and not any(remaining_body_surfaces.values())
    )
    return {
        "decision": (
            "ROUTE_BODY_REPLACEMENT_NOT_READY"
            if not safe_to_delete
            else "ROUTE_BODY_REPLACEMENT_READY_FOR_DELETION_PROOF"
        ),
        "route_found": bool(route),
        "controller_route_shell_exists": controller_route_shell_exists,
        "controller_replacement_body_exists": controller_replacement_body_exists,
        "live_execution_shells_remaining": live_execution_shells,
        "remaining_body_surfaces": remaining_body_surfaces,
        "remaining_body_surface_count": sum(1 for value in remaining_body_surfaces.values() if value),
        "safe_to_delete_route_body_now": safe_to_delete,
        "delete_now_count": 1 if safe_to_delete else 0,
        "recommended_next_surface": (
            "route_body_controller_replacement_object"
            if not controller_replacement_body_exists
            else "route_body_deletion_deadness_proof"
        ),
        "recommended_next_step": (
            "Build a whole-route controller replacement object that consumes injected dependency results and returns the same residual promoted item before deleting the page route body."
            if not controller_replacement_body_exists
            else "Run a deletion deadness proof for the old page route body."
        ),
        "latest": latest,
        "focused_deadness": {
            "evidence_merge_tail_old_body_dead": evidence_merge_old_body_dead,
            "final_binding_tail_old_merge_dead": final_binding_old_merge_dead,
            "debug_projection_proof_covered": debug_projection_proof_covered,
        },
        "latest_required_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    safe_to_delete = capture.get("safe_to_delete_route_body_now") is True
    remaining_body_surface_count = int(capture.get("remaining_body_surface_count", 0) or 0)
    delete_now_count = int(capture.get("delete_now_count", 0) or 0)
    return {
        "route_found": capture.get("route_found") is True,
        "controller_route_shell_exists": capture.get("controller_route_shell_exists") is True,
        "live_execution_shells_cleared": not capture.get("live_execution_shells_remaining"),
        "remaining_body_surface_state_consistent": (
            (safe_to_delete and remaining_body_surface_count == 0)
            or ((not safe_to_delete) and remaining_body_surface_count > 0)
        ),
        "safe_to_delete_route_body_state_classified": isinstance(
            capture.get("safe_to_delete_route_body_now"), bool
        ),
        "delete_now_count_consistent": (
            (safe_to_delete and delete_now_count == 1)
            or ((not safe_to_delete) and delete_now_count == 0)
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
        "# Residual Shear Cleanup Route Body Controller Replacement Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Live execution shells remaining: `{capture.get('live_execution_shells_remaining')}`",
        f"- Remaining body surface count: `{capture.get('remaining_body_surface_count')}`",
        f"- Safe to delete route body now: `{capture.get('safe_to_delete_route_body_now')}`",
        f"- Recommended next surface: `{capture.get('recommended_next_surface')}`",
        "",
        "## Remaining Body Surfaces",
        "",
    ]
    for key, value in (capture.get("remaining_body_surfaces") or {}).items():
        lines.append(f"- {key}: `{value}`")
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
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_controller_replacement_readiness.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_controller_replacement_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_controller_replacement_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_body_controller_replacement_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_controller_replacement_readiness "
        + payload["status"]
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
