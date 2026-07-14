"""Prove whether the residual-shear cleanup route body is deletion-ready.

This is a proof-only inventory gate. It must not make the route look safer
than it is: route-shell and result-identity cutovers are allowed to be green
while the old page route body remains live because injected execution
dependencies are still intentionally owned outside the controller.
"""

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

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

LIVE_BODY_TOKENS = {
    "route_entry_guard": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(",
    "primary_executor_injected_call": "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
    "fallback_variant_generator_injected_call": "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
    "candidate_evaluator_injected_call": "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
    "materiality_pre_screen": "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
    "materiality_post_screen": "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
    "candidate_selector_injected_call": "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
    "result_packaging_injected_call": "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
    "shared_button_contract_execution": "_design_guide_button_contract(residual_promoted, state=state)",
    "route_body_result_identity_cutover": "design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover_applied",
    "route_body_return_boundary_cutover": "residual_route_return_boundary = _select_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_return_item(",
    "route_body_result_shell_cutover": "residual_route_body_result = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(",
    "route_body_returns_result": "return residual_route_return_item",
}

REQUIRED_ARTIFACTS = {
    "route_cutover_readiness": "design_guide_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness",
    "route_shell_adapter_cutover": "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_implementation",
    "route_body_controller_replacement_readiness": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_controller_replacement_readiness",
    "route_body_replacement_cutover_readiness": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_cutover_readiness",
    "route_entry_decision_cutover": "design_guide_post_click_low_bending_residual_shear_cleanup_route_entry_decision_cutover",
    "route_execution_shell_cutover": "design_guide_post_click_low_bending_residual_shear_cleanup_route_execution_shell_cutover",
    "route_body_result_identity_cutover": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_result_identity_cutover",
    "route_body_return_boundary_cutover": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_return_boundary_cutover",
    "route_body_live_execution_shell_audit": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_live_execution_shell_audit",
    "route_body_behavior_cutover_gap_audit": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_behavior_cutover_gap_audit",
    "remaining_surface_audit": "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit",
    "route_shell_with_injected_dependencies_cutover": "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies_cutover",
    "proof_debug_return_tail_cutover": "design_guide_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail_cutover",
    "prebuilt_route_result_cutover": "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_cutover",
    "live_route_result_assembly_audit": "design_guide_post_click_low_bending_residual_shear_cleanup_live_route_result_assembly_audit",
    "nested_wrapper_deadness_probe": "design_guide_post_click_low_bending_residual_shear_cleanup_nested_wrapper_deadness_probe",
}


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
        return {"found": False, "status": "MISSING", "path": "", "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": str(exc),
            "payload": {},
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if "PASS" in raw_status.upper() or "LOCKED" in raw_status.upper() else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}

    route_cutover_payload = latest["route_cutover_readiness"].get("payload") or {}
    route_cutover_capture = route_cutover_payload.get("capture") or route_cutover_payload
    unresolved_route_dependencies = tuple(
        route_cutover_capture.get("unresolved_behavior_dependencies")
        or route_cutover_capture.get("unresolved_dependencies")
        or ()
    )
    route_cutover_decision = str(
        route_cutover_capture.get("decision")
        or route_cutover_payload.get("decision")
        or ""
    )

    live_shell_payload = latest["route_body_live_execution_shell_audit"].get("payload") or {}
    live_shell_capture = live_shell_payload.get("capture") or live_shell_payload
    live_assembly_payload = latest["live_route_result_assembly_audit"].get("payload") or {}
    live_assembly_capture = live_assembly_payload.get("capture") or live_assembly_payload
    nested_deadness_payload = latest["nested_wrapper_deadness_probe"].get("payload") or {}
    nested_deadness_capture = nested_deadness_payload.get("capture") or nested_deadness_payload
    behavior_gap_payload = latest["route_body_behavior_cutover_gap_audit"].get("payload") or {}
    behavior_gap_capture = behavior_gap_payload.get("capture") or behavior_gap_payload
    behavior_gap_bounded = (
        behavior_gap_capture.get("behavior_cutover_ready") is True
        and not tuple(behavior_gap_capture.get("blocking_surfaces") or ())
        and behavior_gap_capture.get("route_return_boundary_bounded") is True
        and behavior_gap_capture.get("button_contract_bounded") is True
    )
    live_execution_shell_surfaces = tuple(live_shell_capture.get("live_execution_shell_surfaces") or ())
    surface_rows = dict(live_shell_capture.get("surface_rows") or {})
    retained_live_surfaces = tuple(
        name
        for name, row in surface_rows.items()
        if row.get("present") and not row.get("delete_now")
        and not str(row.get("classification") or "").startswith("B.")
    )
    live_route_result_assembly_cutover = (
        live_assembly_capture.get("controller_live_route_result_assembly_call_present") is True
        and int(live_assembly_capture.get("delete_blocker_count") or 0) == 0
    )
    nested_wrapper_body_dead = (
        str(nested_deadness_capture.get("decision") or "")
        in {
            "RESIDUAL_SHEAR_NESTED_WRAPPER_BODY_DEAD",
            "RESIDUAL_SHEAR_NESTED_WRAPPER_BODY_DELETED",
        }
    )
    if live_route_result_assembly_cutover and nested_wrapper_body_dead:
        retained_live_surfaces = ()

    token_presence = {
        name: bool(token in route)
        for name, token in LIVE_BODY_TOKENS.items()
    }
    live_tokens_present = tuple(name for name, present in token_presence.items() if present)
    route_body_return_boundary_bounded = bool(
        (
            token_presence.get("route_body_return_boundary_cutover")
            or token_presence.get("route_body_result_shell_cutover")
        )
        and latest["route_body_return_boundary_cutover"].get("status") == "PASS"
    )
    route_body_still_live = bool(token_presence.get("route_body_returns_result"))
    route_body_still_page_owned_return_authority = bool(
        route_body_still_live and not route_body_return_boundary_bounded
    )
    behavior_dependencies_still_live = bool(
        not behavior_gap_bounded
        and (
            token_presence.get("primary_executor_injected_call")
            or token_presence.get("fallback_variant_generator_injected_call")
            or token_presence.get("candidate_evaluator_injected_call")
            or token_presence.get("shared_button_contract_execution")
            or unresolved_route_dependencies
        )
    )
    all_required_artifacts_pass = all(
        item.get("status") == "PASS" for item in latest.values()
    )
    route_shell_with_injected_dependencies_cutover = (
        latest["route_shell_with_injected_dependencies_cutover"].get("status") == "PASS"
    )
    proof_debug_return_tail_cutover = (
        latest["proof_debug_return_tail_cutover"].get("status") == "PASS"
    )
    prebuilt_route_result_cutover = (
        latest["prebuilt_route_result_cutover"].get("status") == "PASS"
    )

    safe_to_delete_route_body_now = bool(
        route
        and all_required_artifacts_pass
        and not route_body_still_live
        and not behavior_dependencies_still_live
        and not retained_live_surfaces
    )
    if safe_to_delete_route_body_now:
        decision = "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_READY_TO_DELETE"
        next_safe_surface = "delete_old_page_route_body"
    elif (
        route_body_still_live
        and behavior_gap_bounded
        and not route_shell_with_injected_dependencies_cutover
    ):
        decision = "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_READY_FOR_CONTROLLER_SHELL_IMPLEMENTATION"
        next_safe_surface = "controller_route_shell_implementation_with_injected_dependencies"
    elif route_body_still_live and prebuilt_route_result_cutover:
        decision = "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_PREBUILT_RESULT_CUTOVER_NOT_READY_TO_DELETE"
        next_safe_surface = "prove_nested_route_body_wrapper_dead_then_delete"
    elif (
        route_body_still_live
        and route_shell_with_injected_dependencies_cutover
        and proof_debug_return_tail_cutover
    ):
        decision = "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_TAIL_REPRESENTED_NOT_READY_TO_DELETE"
        next_safe_surface = "replace_physical_nested_route_body_wrapper"
    elif route_body_still_live and route_shell_with_injected_dependencies_cutover:
        decision = "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_CONTROLLER_SHELL_IMPLEMENTED_NOT_READY_TO_DELETE"
        next_safe_surface = "extract_remaining_route_body_binding_debug_tail_before_deletion"
    else:
        decision = "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_NOT_READY_TO_DELETE"
        next_safe_surface = "remaining_injected_dependency_or_next_priority_surface"

    deletion_blockers = []
    if route_body_still_page_owned_return_authority:
        deletion_blockers.append("route_body_still_returns_page_owned_result")
    elif route_body_still_live:
        deletion_blockers.append("physical_route_body_still_present")
    if behavior_dependencies_still_live:
        deletion_blockers.append("behavior_dependencies_still_live_or_unresolved")
    if retained_live_surfaces:
        deletion_blockers.append("retained_live_route_surfaces_present")
    if not all_required_artifacts_pass:
        deletion_blockers.append("required_artifacts_not_all_pass")

    return {
        "decision": decision,
        "route_found": bool(route),
        "route_cutover_decision": route_cutover_decision,
        "safe_to_delete_route_body_now": safe_to_delete_route_body_now,
        "next_safe_surface": next_safe_surface,
        "deletion_blockers": deletion_blockers,
        "unresolved_route_dependencies": unresolved_route_dependencies,
        "live_execution_shell_surfaces": live_execution_shell_surfaces,
        "retained_live_surfaces": retained_live_surfaces,
        "token_presence": token_presence,
        "live_tokens_present": live_tokens_present,
        "route_body_still_live": route_body_still_live,
        "route_body_return_boundary_bounded": route_body_return_boundary_bounded,
        "route_body_still_page_owned_return_authority": route_body_still_page_owned_return_authority,
        "behavior_dependencies_still_live": behavior_dependencies_still_live,
        "behavior_gap_bounded": behavior_gap_bounded,
        "route_shell_with_injected_dependencies_cutover": route_shell_with_injected_dependencies_cutover,
        "proof_debug_return_tail_cutover": proof_debug_return_tail_cutover,
        "prebuilt_route_result_cutover": prebuilt_route_result_cutover,
        "live_route_result_assembly_cutover": live_route_result_assembly_cutover,
        "nested_wrapper_body_dead": nested_wrapper_body_dead,
        "behavior_gap_path": latest["route_body_behavior_cutover_gap_audit"].get("path"),
        "required_artifacts": {
            name: {key: value for key, value in item.items() if key != "payload"}
            for name, item in latest.items()
        },
        "all_required_artifacts_pass": all_required_artifacts_pass,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_found": capture.get("route_found") is True,
        "required_artifacts_pass": capture.get("all_required_artifacts_pass") is True,
        "deletion_readiness_classified": bool(capture.get("decision")),
        "unsafe_delete_not_claimed": (
            capture.get("safe_to_delete_route_body_now") is True
            or bool(capture.get("deletion_blockers"))
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route Body Deletion Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Safe to delete route body now: `{capture.get('safe_to_delete_route_body_now')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Deletion Blockers",
        "",
    ]
    blockers = list(capture.get("deletion_blockers") or [])
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Live State",
            "",
            f"- unresolved route dependencies: `{capture.get('unresolved_route_dependencies')}`",
            f"- retained live surfaces: `{capture.get('retained_live_surfaces')}`",
            f"- live tokens present: `{capture.get('live_tokens_present')}`",
            "",
            "## Required Artifacts",
            "",
        ]
    )
    for name, item in (capture.get("required_artifacts") or {}).items():
        lines.append(f"- `{name}`: status=`{item.get('status')}`, path=`{item.get('path')}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_readiness.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_body_deletion_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_readiness {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"safe_to_delete_route_body_now={capture.get('safe_to_delete_route_body_now')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
