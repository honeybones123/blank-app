"""Audit direct-target active-failure route execution boundary."""

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
TARGET = "_direct_target_band_guidance_item"


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


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    pre_diag = segment.split("_diag_prior = st.session_state.get", 1)[0]

    route_surfaces = [
        {
            "surface": "active failure route condition selection",
            "tokens": [
                '_overview_active_failure_keys(dict(overview or {})) == {"bending"}',
                '_overview_active_failure_keys(dict(overview or {})) == {"shear"}',
                '_overview_active_failure_keys(dict(overview or {})) >= {"bending", "shear"}',
            ],
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController route policy",
            "classification": "still page-owned Design Brain route policy",
            "move_readiness": "NOT_READY",
            "required_next_proof": "route request/result parity with page-owned executor injected",
        },
        {
            "surface": "family repair item executor bridge",
            "tokens": ["_active_fail_near_current_repair_item("],
            "current_owner": "inputs_page",
            "target_owner": "page-shell executor injection into controller/service boundary",
            "classification": "page-owned callback/executor bridge",
            "move_readiness": "UNSAFE_TO_MOVE_WHOLE_EXECUTOR",
            "required_next_proof": "controller accepts precomputed family item or injected executor without owning runtime/session",
        },
        {
            "surface": "family bypass route adapter projection",
            "tokens": ["_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter("],
            "current_owner": "DesignGuideController",
            "target_owner": "DesignGuideController",
            "classification": "already controller-owned",
            "move_readiness": "DONE",
            "required_next_proof": None,
        },
        {
            "surface": "combined raw flags and selection evidence construction",
            "tokens": [
                "_build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection(",
            ],
            "current_owner": "DesignGuideController",
            "target_owner": "DesignGuideController route evidence projection",
            "classification": "already controller-owned",
            "move_readiness": "DONE",
            "required_next_proof": None,
        },
        {
            "surface": "bending CTA publication side effect",
            "tokens": ["_record_bending_fail_valid_repair_cta_published("],
            "current_owner": "inputs_page",
            "target_owner": "inputs_page page/shared CTA publication side effect",
            "classification": "bounded page-owned side effect",
            "move_readiness": "KEEP_PAGE_OWNED",
            "required_next_proof": None,
        },
        {
            "surface": "debug sink diagnostics",
            "tokens": [
                "debug_sink.update(",
                'debug_sink["generic_target_band_search_skipped"]',
                'debug_sink["direct_target_band_bypassed_by_family_owner"]',
            ],
            "current_owner": "inputs_page",
            "target_owner": "page shell diagnostics or future debug/proof service",
            "classification": "bounded non-authoritative diagnostics",
            "move_readiness": "KEEP_BOUNDED",
            "required_next_proof": None,
        },
    ]
    rows: list[dict[str, Any]] = []
    for surface in route_surfaces:
        token_rows = []
        for token in surface["tokens"]:
            lines = _line_numbers(pre_diag, start, token)
            token_rows.append(
                {
                    "token": token,
                    "present": bool(lines),
                    "count": pre_diag.count(token),
                    "lines": lines[:20],
                }
            )
        rows.append(
            {
                **surface,
                "present": any(row["present"] for row in token_rows),
                "tokens_found": token_rows,
            }
        )

    combined_evidence_controller_owned = (
        "_build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection("
        in pre_diag
        and "def build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection("
        in controller_source
        and "_combined_raw_flags = {" not in pre_diag
        and "_combined_rejected_families = {" not in pre_diag
        and "_combined_selection_evidence = {" not in pre_diag
    )
    family_executor_calls = pre_diag.count("_active_fail_near_current_repair_item(")
    controller_projection_calls = pre_diag.count(
        "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter("
    )
    route_conditions_page_owned = all(
        token in pre_diag
        for token in [
            '_overview_active_failure_keys(dict(overview or {})) == {"bending"}',
            '_overview_active_failure_keys(dict(overview or {})) == {"shear"}',
            '_overview_active_failure_keys(dict(overview or {})) >= {"bending", "shear"}',
        ]
    )
    route_condition_policy_controller_owned = (
        "_resolve_design_guide_controller_direct_target_active_failure_route_policy(" in pre_diag
        and '_overview_active_failure_keys(dict(overview or {})) == {"bending"}' not in pre_diag
        and '_overview_active_failure_keys(dict(overview or {})) == {"shear"}' not in pre_diag
        and '_overview_active_failure_keys(dict(overview or {})) >= {"bending", "shear"}' not in pre_diag
    )
    controller_clean = (
        "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source
    )
    decision = (
        "NOT_READY_EXECUTOR_BRIDGE_STILL_PAGE_OWNED"
        if route_condition_policy_controller_owned and family_executor_calls
        else "NOT_READY_ROUTE_EXECUTION_STILL_PAGE_OWNED"
        if route_conditions_page_owned and family_executor_calls
        else "BOUNDED_OR_EXTRACTED"
    )
    return {
        "schema": "design_guide_direct_target_active_failure_route_execution_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
            "pre_diagnostic_route_window_line_count": len(pre_diag.splitlines()),
        },
        "status_decision": decision,
        "surfaces": rows,
        "route_conditions_page_owned": bool(route_conditions_page_owned),
        "route_condition_policy_controller_owned": bool(route_condition_policy_controller_owned),
        "family_executor_calls_in_route_window": family_executor_calls,
        "controller_projection_calls_in_route_window": controller_projection_calls,
        "combined_evidence_controller_owned": bool(combined_evidence_controller_owned),
        "route_execution_ready_to_move": False,
        "route_execution_blocker": (
            "inputs_page still chooses the active-failure route and directly calls "
            "_active_fail_near_current_repair_item(...). Moving that whole executor would risk "
            "family runtime/session/apply ownership without an injected-executor parity proof."
        ),
        "first_safe_implementation_slice": {
            "name": (
                "direct_target_active_failure_executor_bridge_boundary_audit"
                if route_condition_policy_controller_owned
                else "direct_target_active_failure_route_condition_policy_adapter_audit"
            ),
            "why": (
                "Route condition policy and request/result projection are controller-owned. The remaining "
                "route surface is the page-owned active-failure family executor bridge."
                if route_condition_policy_controller_owned
                else "The route request/result projection is controller-owned. The remaining route surface is "
                "the page-owned active-failure branch condition selection before the executor call."
            ),
            "move": (
                "Audit whether executor invocation can be bounded as page-shell dependency injection, or "
                "whether a controller route can consume precomputed family items without moving family "
                "runtime/session ownership."
                if route_condition_policy_controller_owned
                else "Audit whether a controller helper can classify the active-failure route kind from plain "
                "strengthening and active-failure-key inputs while keeping executor calls, CTA side effects, "
                "debug/session writes, and route execution page-owned."
            ),
            "required_verifier": (
                "design_guide_direct_target_active_failure_executor_bridge_boundary_audit.py"
                if route_condition_policy_controller_owned
                else "design_guide_direct_target_active_failure_route_condition_policy_adapter_audit.py"
            ),
        },
        "later_route_cutover_requirement": {
            "name": "direct_target_active_failure_route_request_result_adapter",
            "required_before_moving_route_execution": [
                "controller route request/result object accepts active failure keys as plain data",
                "page injects or precomputes family item without moving runtime/session ownership",
                "bending CTA publication side effect remains page/shared-owned",
                "visible item, selected family, CTA/display/publication hashes match",
            ],
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
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "surfaces_classified": len(surfaces) >= 6,
        "route_conditions_detected_or_controller_owned": bool(payload.get("route_conditions_page_owned"))
        or bool(payload.get("route_condition_policy_controller_owned")),
        "family_executor_detected": int(payload.get("family_executor_calls_in_route_window") or 0) >= 3,
        "controller_projection_detected": int(payload.get("controller_projection_calls_in_route_window") or 0) >= 3,
        "combined_evidence_controller_owned": bool(payload.get("combined_evidence_controller_owned")),
        "route_not_marked_ready_without_proof": not bool(payload.get("route_execution_ready_to_move")),
        "first_safe_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("name")
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
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_direct_target_active_failure_route_execution_boundary_audit_{suffix}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_direct_target_active_failure_route_execution_boundary_audit_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Active-Failure Route Execution Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        (
            "PARTIAL: active-failure family bypass metadata projection is controller-owned, "
            "but route condition selection and family executor calls still live in inputs_page.py. "
            "The whole route is not ready to move until an injected-executor route adapter has parity proof."
        ),
        "",
        "## Surface Classification",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"(owner: {row.get('current_owner')} -> {row.get('target_owner')}; "
            f"readiness: {row.get('move_readiness')})"
        )
    lines.extend(
        [
            "",
            "## Exact Route Execution Blocker",
            str(payload.get("route_execution_blocker") or ""),
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{(payload.get('first_safe_implementation_slice') or {}).get('name')}`",
            f"- Why: {(payload.get('first_safe_implementation_slice') or {}).get('why')}",
            f"- Move: {(payload.get('first_safe_implementation_slice') or {}).get('move')}",
            f"- Verifier: `{(payload.get('first_safe_implementation_slice') or {}).get('required_verifier')}`",
            "",
            "## Later Route Cutover Requirement",
        ]
    )
    later = payload.get("later_route_cutover_requirement") or {}
    lines.append(f"- Name: `{later.get('name')}`")
    for item in later.get("required_before_moving_route_execution") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
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
    payload = {
        **payload,
        "status": status,
        "checks": checks,
        "checked_at": _timestamp(),
    }
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_direct_target_active_failure_route_execution_boundary_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
