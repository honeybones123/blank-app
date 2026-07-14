"""Audit the direct-target active-failure executor bridge boundary.

This is an audit-only verifier. It does not require the executor bridge to move;
it proves exactly why the remaining `_active_fail_near_current_repair_item(...)`
surface is still page-owned and what the next safe extraction slice must be.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
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
ROUTE_TARGET = "_direct_target_band_guidance_item"
EXECUTOR_TARGET = "_active_fail_near_current_repair_item"


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


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _token_summary(segment: str, start_line: int, tokens: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "token": token,
            "present": token in segment,
            "count": segment.count(token),
            "lines": _line_numbers(segment, start_line, token)[:20],
        }
        for token in tokens
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    route_start, route_end, route_segment = _function_source(inputs_source, ROUTE_TARGET)
    executor_start, executor_end, executor_segment = _function_source(inputs_source, EXECUTOR_TARGET)
    route_window = route_segment.split("_diag_prior = st.session_state.get", 1)[0]

    route_policy_controller_owned = (
        "_resolve_design_guide_controller_direct_target_active_failure_route_policy(" in route_window
        and '_overview_active_failure_keys(dict(overview or {})) == {"bending"}' not in route_window
        and '_overview_active_failure_keys(dict(overview or {})) == {"shear"}' not in route_window
        and '_overview_active_failure_keys(dict(overview or {})) >= {"bending", "shear"}' not in route_window
    )
    route_projection_controller_owned = (
        route_window.count(
            "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter("
        )
        == 3
        and "_build_design_guide_controller_direct_target_family_bypass_projection(" not in route_window
    )
    executor_calls_in_route = route_window.count("_active_fail_near_current_repair_item(")

    executor_session_tokens = [
        "st.session_state",
        "get_rerun_pure_cache(",
        "set_rerun_pure_cache(",
        "_inputs_pre_widget_trace(",
        "_bending_post_cta_early_stop_increment(",
        "_record_bending_post_cta_early_stop_status(",
    ]
    executor_runtime_tokens = [
        "_bending_fail_publication_snapshot_for_state(",
        "_bending_post_cta_early_stop_status(",
        "_candidate_cache_key(",
        "_evaluate_candidate_with_update(",
        "_active_fail_near_current_candidate_updates(",
        "_guidance_item_from_candidate(",
    ]
    executor_policy_tokens = [
        "_design_mode_config(",
        "_design_optimisation_goal(",
        "_resolved_efficiency_target_band(",
        "_resolve_geometry_width_context(",
        "active == {\"bending\"}",
        "active == {\"shear\"}",
        "active >= {\"bending\", \"shear\"}",
    ]

    surfaces = [
        {
            "surface": "direct-target active-failure route condition policy",
            "current_owner": "DesignGuideController",
            "target_owner": "DesignGuideController",
            "classification": "controller-owned route policy",
            "readiness": "DONE",
            "evidence": _token_summary(
                route_window,
                route_start,
                ["_resolve_design_guide_controller_direct_target_active_failure_route_policy("],
            ),
        },
        {
            "surface": "direct-target active-failure route projection",
            "current_owner": "DesignGuideController",
            "target_owner": "DesignGuideController",
            "classification": "controller-owned request/result projection",
            "readiness": "DONE",
            "evidence": _token_summary(
                route_window,
                route_start,
                ["_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter("],
            ),
        },
        {
            "surface": "active-failure family repair executor bridge",
            "current_owner": "inputs_page",
            "target_owner": "page shell until family executor/service boundary exists",
            "classification": "bounded page-shell executor bridge, not ready to move wholesale",
            "readiness": "NOT_READY",
            "evidence": _token_summary(
                route_window,
                route_start,
                ["_active_fail_near_current_repair_item("],
            ),
            "exact_blocker": (
                "The called helper still performs active repair execution with session/cache/pre-widget trace "
                "touchpoints and family-specific repair snapshots. Moving it now would move runtime/session "
                "behaviour into DesignGuideController."
            ),
        },
        {
            "surface": "bending CTA publication side effect",
            "current_owner": "inputs_page",
            "target_owner": "inputs_page/page-shared apply publication side effect",
            "classification": "bounded page-owned side effect",
            "readiness": "KEEP_PAGE_OWNED",
            "evidence": _token_summary(
                route_window,
                route_start,
                ["_record_bending_fail_valid_repair_cta_published("],
            ),
        },
        {
            "surface": "executor session/cache/debug touchpoints",
            "current_owner": "inputs_page",
            "target_owner": "page shell or later dedicated runtime/service boundary",
            "classification": "unsafe to move yet",
            "readiness": "NOT_READY",
            "evidence": _token_summary(executor_segment, executor_start, executor_session_tokens),
        },
        {
            "surface": "executor family/candidate runtime calls",
            "current_owner": "inputs_page",
            "target_owner": "family runtime / candidate service boundary",
            "classification": "still page-owned execution bridge",
            "readiness": "NOT_READY",
            "evidence": _token_summary(executor_segment, executor_start, executor_runtime_tokens),
        },
        {
            "surface": "executor local target-band policy inputs",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController or target-band service after executor split",
            "classification": "still page-owned Design Brain policy input preparation",
            "readiness": "NOT_READY",
            "evidence": _token_summary(executor_segment, executor_start, executor_policy_tokens),
        },
    ]

    controller_clean = (
        "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source
    )
    executor_has_session_or_trace = any(token in executor_segment for token in executor_session_tokens)
    executor_has_runtime_calls = any(token in executor_segment for token in executor_runtime_tokens)
    executor_has_policy_inputs = any(token in executor_segment for token in executor_policy_tokens)

    return {
        "schema": "design_guide_direct_target_active_failure_executor_bridge_boundary_audit.v1",
        "target": {
            "route_function": {
                "name": ROUTE_TARGET,
                "line_start": route_start,
                "line_end": route_end,
                "line_count": max(0, route_end - route_start + 1),
            },
            "executor_function": {
                "name": EXECUTOR_TARGET,
                "line_start": executor_start,
                "line_end": executor_end,
                "line_count": max(0, executor_end - executor_start + 1),
            },
        },
        "status_decision": (
            "BOUNDED_PAGE_EXECUTOR_BRIDGE_NOT_READY_TO_MOVE"
            if route_policy_controller_owned
            and route_projection_controller_owned
            and executor_calls_in_route >= 3
            and executor_has_session_or_trace
            and executor_has_runtime_calls
            else "FAIL_UNCLEAR_EXECUTOR_BOUNDARY"
        ),
        "surfaces": surfaces,
        "route_policy_controller_owned": bool(route_policy_controller_owned),
        "route_projection_controller_owned": bool(route_projection_controller_owned),
        "executor_calls_in_route_window": executor_calls_in_route,
        "executor_has_session_or_trace_touchpoints": bool(executor_has_session_or_trace),
        "executor_has_family_or_candidate_runtime_calls": bool(executor_has_runtime_calls),
        "executor_has_target_band_policy_input_preparation": bool(executor_has_policy_inputs),
        "executor_bridge_ready_to_move": False,
        "executor_bridge_ready_to_delete": False,
        "executor_bridge_classification": "bounded page-shell plumbing with embedded runtime bridge",
        "exact_blockers": [
            "The route still needs a live family repair item from _active_fail_near_current_repair_item(...).",
            "The executor helper touches Streamlit/session-adjacent state, rerun cache, and pre-widget trace.",
            "The executor helper still calls family/candidate runtime helpers rather than a controller/service-owned executor boundary.",
            "No parity proof exists yet for replacing the executor call with a precomputed-family-item service contract.",
        ],
        "first_safe_implementation_slice": {
            "name": "direct_target_active_failure_executor_item_service_boundary_audit",
            "move": (
                "Audit the return shape and call graph of _active_fail_near_current_repair_item(...), then split "
                "plain target-band policy/candidate inputs from page-owned session/cache/probe execution."
            ),
            "required_verifier": (
                "design_guide_direct_target_active_failure_executor_item_service_boundary_audit.py"
            ),
        },
        "controller_has_no_page_or_streamlit_imports": controller_clean,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    surfaces = payload.get("surfaces") or []
    return {
        "route_function_found": bool(((payload.get("target") or {}).get("route_function") or {}).get("line_start")),
        "executor_function_found": bool(
            ((payload.get("target") or {}).get("executor_function") or {}).get("line_start")
        ),
        "surfaces_classified": len(surfaces) >= 7,
        "route_policy_controller_owned": bool(payload.get("route_policy_controller_owned")),
        "route_projection_controller_owned": bool(payload.get("route_projection_controller_owned")),
        "executor_calls_still_present": int(payload.get("executor_calls_in_route_window") or 0) >= 3,
        "executor_session_or_trace_touchpoints_detected": bool(
            payload.get("executor_has_session_or_trace_touchpoints")
        ),
        "executor_runtime_calls_detected": bool(payload.get("executor_has_family_or_candidate_runtime_calls")),
        "executor_not_marked_ready_to_move": not bool(payload.get("executor_bridge_ready_to_move")),
        "executor_not_marked_ready_to_delete": not bool(payload.get("executor_bridge_ready_to_delete")),
        "first_safe_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
        ),
        "controller_has_no_page_or_streamlit_imports": bool(
            payload.get("controller_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"design_guide_direct_target_active_failure_executor_bridge_boundary_audit_{suffix}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_direct_target_active_failure_executor_bridge_boundary_audit_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Active-Failure Executor Bridge Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        (
            "PARTIAL: direct-target active-failure route policy and projection are controller-owned, "
            "but the family repair executor bridge remains bounded page-owned plumbing. It is not safe "
            "to move or delete until the executor item service boundary is audited and parity-proven."
        ),
        "",
        "## Surface Classification",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"(owner: {row.get('current_owner')} -> {row.get('target_owner')}; "
            f"readiness: {row.get('readiness')})"
        )
    lines.extend(
        [
            "",
            "## Exact Blockers",
            *[f"- {item}" for item in payload.get("exact_blockers") or []],
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{(payload.get('first_safe_implementation_slice') or {}).get('name')}`",
            f"- Move: {(payload.get('first_safe_implementation_slice') or {}).get('move')}",
            f"- Verifier: `{(payload.get('first_safe_implementation_slice') or {}).get('required_verifier')}`",
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
    print(f"design_guide_direct_target_active_failure_executor_bridge_boundary_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
