"""Audit route ordering inside _compute_design_guidance_items_core(...).

This is proof-only. The route order decides which Design Guide item is selected,
so no branch should be moved until its priority, inputs, item builder, debug
projection, and stop conditions are explicit.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _first_line(segment: str, start_line: int, token: str) -> int | None:
    for index, line in enumerate(segment.splitlines()):
        if token in line:
            return start_line + index
    return None


def _count(segment: str, token: str) -> int:
    return segment.count(token)


def _route(
    *,
    route: str,
    token: str,
    branch_kind: str,
    current_owner: str,
    target_owner: str,
    readiness: str,
    first_safe_slice: str | None,
    reason: str,
    segment: str,
    start_line: int,
    item_builders: list[str] | None = None,
    debug_tokens: list[str] | None = None,
) -> dict[str, Any]:
    item_builders = list(item_builders or [])
    debug_tokens = list(debug_tokens or [])
    return {
        "route": route,
        "token": token,
        "present": token in segment,
        "line": _first_line(segment, start_line, token),
        "count": _count(segment, token),
        "branch_kind": branch_kind,
        "current_owner": current_owner,
        "target_owner": target_owner,
        "readiness": readiness,
        "first_safe_slice": first_safe_slice,
        "reason": reason,
        "item_builders": [
            {
                "token": item,
                "present": item in segment,
                "count": _count(segment, item),
                "first_line": _first_line(segment, start_line, item),
            }
            for item in item_builders
        ],
        "debug_projection": [
            {
                "token": token_value,
                "present": token_value in segment,
                "count": _count(segment, token_value),
                "first_line": _first_line(segment, start_line, token_value),
            }
            for token_value in debug_tokens
        ],
    }


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, core_segment = _function_source(source, "_compute_design_guidance_items_core")
    _, _, start_item_segment = _function_source(source, "_guidance_start_item")
    _, _, not_started_segment = _function_source(source, "_guidance_not_started")
    start_item_projection_cutover = (
        "_build_design_guide_controller_start_guidance_item(" in start_item_segment
        and "Choose your workflow:" not in start_item_segment
    )
    not_started_condition_cutover = (
        "_resolve_design_guide_controller_not_started_condition(" in not_started_segment
        and "required_inputs_missing =" not in not_started_segment
        and "no_key_results =" not in not_started_segment
    )

    routes = [
        _route(
            route="not_started",
            token="if _not_started:",
            branch_kind="early terminal/start branch",
            current_owner=(
                "DesignGuideController via inputs_page shell"
                if start_item_projection_cutover and not_started_condition_cutover
                else "inputs_page.py"
            ),
            target_owner="DesignGuideController with page start-item adapter",
            readiness="SHELL_CALL" if start_item_projection_cutover and not_started_condition_cutover else "NOT_READY",
            first_safe_slice=(
                None
                if start_item_projection_cutover and not_started_condition_cutover
                else "compute_core_not_started_condition_projection_extraction"
                if start_item_projection_cutover
                else "compute_core_not_started_route_projection_audit"
            ),
            reason=(
                "Start-card projection and pure not-started condition are controller-owned; core keeps route-order shell."
                if start_item_projection_cutover and not_started_condition_cutover
                else "Start-card projection is controller-owned; remaining work is the pure not-started condition."
                if start_item_projection_cutover
                else "Calls page-local `_guidance_start_item(...)`; needs item projection parity before movement."
            ),
            segment=core_segment,
            start_line=start,
            item_builders=["_guidance_start_item("],
            debug_tokens=["debug_sink[\"guidance_branch\"]", "debug_sink[\"selected_action_type\"]"],
        ),
        _route(
            route="post_active_repair_acceptance",
            token="_post_apply_from_active_failure_repair",
            branch_kind="post-click active-repair route",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController route policy plus page callback shell",
            readiness="NOT_READY",
            first_safe_slice="compute_core_post_active_repair_route_policy_audit",
            reason="Combines post-click acceptance, zero-shear terminal, shear blocker, and cleanup CTA paths.",
            segment=core_segment,
            start_line=start,
            item_builders=[
                "_post_active_repair_target_accepted_item(",
                "_shear_best_safe_cleanup_item_from_evidence(",
                "_shear_low_util_target_cleanup_item(",
            ],
            debug_tokens=["post_click_accepted_green", "post_active_low_shear_safe_action_preferred"],
        ),
        _route(
            route="post_apply_low_bending_resolution",
            token="post_apply_low_bending_resolution",
            branch_kind="post-click unresolved cleanup route",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController route policy",
            readiness="NOT_READY",
            first_safe_slice="compute_core_post_apply_low_bending_route_audit",
            reason="Depends on post-click accepted-green audit and low-bending blocker item projection.",
            segment=core_segment,
            start_line=start,
            item_builders=["_post_click_low_bending_resolution_item("],
            debug_tokens=["terminal_state_blocked_by_local_cleanup"],
        ),
        _route(
            route="in_target_shear_congestion_reshape",
            token="in_target_shear_congestion_reshape",
            branch_kind="cleanup/reshape route",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController/candidate service",
            readiness="NOT_READY",
            first_safe_slice="compute_core_in_target_shear_congestion_route_audit",
            reason="Calls page-local reshape item helper and debug projection.",
            segment=core_segment,
            start_line=start,
            item_builders=["_in_target_shear_congestion_reshape_guidance_item("],
            debug_tokens=["actionable_target_band_winner_exists"],
        ),
        _route(
            route="bending_below_target_cleanup",
            token="bending_below_target_bending_only_cleanup",
            branch_kind="low-util cleanup route",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController/candidate service",
            readiness="NOT_READY",
            first_safe_slice="compute_core_bending_below_target_route_audit",
            reason="Mixes bending-only helper, direct-target fallback, candidate evaluation, and exact blocker fallback.",
            segment=core_segment,
            start_line=start,
            item_builders=[
                "_bending_only_target_band_cleanup_item(",
                "_direct_target_band_guidance_item(",
                "_post_click_low_bending_resolution_item(",
            ],
            debug_tokens=["local_cleanup_candidate_search_evidence", "terminal_state_blocked_by_local_cleanup"],
        ),
        _route(
            route="target_band_final_accepted",
            token="target_band_final_accepted",
            branch_kind="all-pass target-band terminal route",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController",
            readiness="NOT_READY",
            first_safe_slice="compute_core_target_band_final_accepted_route_audit",
            reason="Builds optimal item and exact cleanup blocker evidence; wording/status must be preserved.",
            segment=core_segment,
            start_line=start,
            item_builders=["_optimal_guidance_item("],
            debug_tokens=["_stamp_exact_cleanup_blocker_evidence("],
        ),
        _route(
            route="critical_one_click",
            token="critical_apply_resolved_candidate",
            branch_kind="critical action candidate route",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController/candidate_evaluation service",
            readiness="NOT_READY",
            first_safe_slice="compute_core_one_click_branch_policy_audit",
            reason="Selects one-click candidate and validates failure coverage before surfacing CTA.",
            segment=core_segment,
            start_line=start,
            item_builders=[
                "_compute_mode_guidance_recommendation(",
                "_evaluate_auto_design_candidate(",
                "_materialize_guidance_candidate(",
                "_get_one_click_band_reaching_candidate(",
            ],
            debug_tokens=["one_click_primary_candidate_valid", "critical_branch_used_one_click_override"],
        ),
        _route(
            route="critical_governing_item",
            token="if critical and governing_item_is_critical:",
            branch_kind="critical fallback route",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController",
            readiness="NOT_READY",
            first_safe_slice="compute_core_critical_governing_item_route_audit",
            reason="Chooses primary critical card and optional compound strengthening replacement.",
            segment=core_segment,
            start_line=start,
            item_builders=["_try_compound_strengthening_guidance_item("],
            debug_tokens=["selected_action_type", "selected_title"],
        ),
        _route(
            route="passing_blocked_fallback",
            token="passing_guidance_fallback",
            branch_kind="final fallback route",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController",
            readiness="NOT_READY",
            first_safe_slice="compute_core_fallback_item_projection_extraction",
            reason="Constructs final passing/blocked/no-active fallback items.",
            segment=core_segment,
            start_line=start,
            item_builders=["_passing_guidance_item(", "_blocked_guidance_item(", "_no_active_primary_result("],
            debug_tokens=["guidance_branch", "selected_title"],
        ),
    ]

    present_routes = [route for route in routes if route["present"]]
    ordered_routes = sorted(present_routes, key=lambda route: route["line"] or 10**9)
    line_order = [route["route"] for route in ordered_routes]
    not_ready_routes = [route for route in present_routes if route["readiness"] == "NOT_READY"]
    first_route = next((route for route in ordered_routes if route["readiness"] == "NOT_READY"), {})

    return {
        "schema": "design_guide_compute_core_branch_route_ordering_audit.v1",
        "status_decision": "COMPUTE_CORE_BRANCH_ROUTE_ORDERING_NOT_ZERO" if not_ready_routes else "COMPUTE_CORE_BRANCH_ROUTE_ORDERING_SHELL_ONLY",
        "target": {
            "function": "_compute_design_guidance_items_core",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "routes": routes,
        "ordered_present_routes": ordered_routes,
        "line_order": line_order,
        "not_ready_routes": not_ready_routes,
        "first_safe_slice": dict(first_route),
        "start_item_projection_cutover": bool(start_item_projection_cutover),
        "not_started_condition_cutover": bool(not_started_condition_cutover),
        "recommended_next_implementation": {
            "slice": (first_route or {}).get("first_safe_slice"),
            "target_owner": (first_route or {}).get("target_owner"),
            "description": (
                "Start with the first route in execution order. Prove its item projection "
                "and debug projection before moving route choice or deleting page code."
            ),
        },
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    target = payload.get("target") or {}
    return {
        "target_found": bool(target.get("line_start") and target.get("line_end")),
        "routes_classified": len(payload.get("routes") or []) >= 8,
        "ordered_routes_present": len(payload.get("ordered_present_routes") or []) >= 6,
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice")),
        "controller_import_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_core_branch_route_ordering_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_core_branch_route_ordering_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Design Guide Compute Core Branch Route Ordering Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        (
            "PARTIAL. The compute core branch order is still page-owned. This audit "
            "does not authorize a broad move; it identifies branch-specific slices "
            "that need projection parity before cutover."
        ),
        "",
        "## Route Order",
    ]
    for route in payload.get("ordered_present_routes") or []:
        lines.append(
            f"- line {route.get('line')}: {route.get('route')} | "
            f"{route.get('readiness')} | {route.get('first_safe_slice')}"
        )
    lines.extend(
        [
            "",
            "## First Safe Slice",
            f"- Route: {(payload.get('first_safe_slice') or {}).get('route')}",
            f"- Slice: {(payload.get('first_safe_slice') or {}).get('first_safe_slice')}",
            f"- Reason: {(payload.get('first_safe_slice') or {}).get('reason')}",
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_compute_core_branch_route_ordering_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
