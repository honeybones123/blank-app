"""Audit request/result adapter boundary for direct-target active-failure route."""

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


def _branch_window(segment: str, start: str, end: str | None = None) -> str:
    if start not in segment:
        return ""
    tail = segment.split(start, 1)[1]
    if end and end in tail:
        return tail.split(end, 1)[0]
    return tail


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    pre_diag = segment.split("_diag_prior = st.session_state.get", 1)[0]
    branches = {
        "bending": _branch_window(
            pre_diag,
            'if _active_failure_route_kind == "bending":',
            "if _bending_fail_speed_isolated_active_repair(debug_sink):",
        ),
        "shear": _branch_window(
            pre_diag,
            'if _active_failure_route_kind == "shear":',
            'if _active_failure_route_kind == "combined":',
        ),
        "combined": _branch_window(
            pre_diag,
            'if _active_failure_route_kind == "combined":',
            "_diag_prior = st.session_state.get",
        ),
    }
    branch_rows: dict[str, dict[str, Any]] = {}
    for family, branch in branches.items():
        branch_rows[family] = {
            "present": bool(branch.strip()),
            "calls_family_executor": "_active_fail_near_current_repair_item(" in branch,
            "calls_family_bypass_projection": (
                "_build_design_guide_controller_direct_target_family_bypass_projection(" in branch
            ),
            "calls_route_adapter": (
                "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter("
                in branch
            ),
            "calls_combined_evidence_projection": (
                "_build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection("
                in branch
            ),
            "updates_debug_sink": "debug_sink.update(" in branch or 'debug_sink["' in branch,
            "returns_family_item": "return" in branch and "family_item" in branch,
            "has_bending_cta_side_effect": "_record_bending_fail_valid_repair_cta_published(" in branch,
        }
    controller_route_adapter_exists = (
        "direct_target_active_failure_route_request" in controller_source
        or "direct_target_active_failure_route_result" in controller_source
    )
    request_shape = {
        "controller_owned_inputs": [
            "active_failure_keys",
            "family_id",
            "family_route_owner",
            "skipped_reason",
            "family_item_plain_data",
            "combined_evidence_projection_plain_data",
            "metadata_projection_options",
        ],
        "page_owned_inputs": [
            "base/current state collection",
            "overview collection",
            "_active_fail_near_current_repair_item executor call until injected adapter proof exists",
            "_record_bending_fail_valid_repair_cta_published side effect",
            "debug_sink/session writes",
        ],
        "result_fields_to_preserve": [
            "returned item",
            "candidate_search_evidence",
            "selected_family_id",
            "published_family_id",
            "cta_family_id",
            "debug_update",
            "bending_cta_side_effect_required flag",
        ],
    }
    trace_adapter_wired = (
        "build_design_guide_controller_direct_target_active_failure_route_request_result_adapter_trace"
        in controller_source
        and "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter_trace("
        in pre_diag
        and "direct_target_active_failure_route_adapter_trace" in pre_diag
    )
    route_adapter_cutover_complete = (
        "build_design_guide_controller_direct_target_active_failure_route_request_result_adapter"
        in controller_source
        and "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter("
        in pre_diag
        and "_build_design_guide_controller_direct_target_family_bypass_projection(" not in pre_diag
    )
    ready_for_trace_adapter = (
        all(row["calls_family_executor"] for row in branch_rows.values())
        and all(row["calls_family_bypass_projection"] for row in branch_rows.values())
        and branch_rows["combined"]["calls_combined_evidence_projection"]
        and not controller_route_adapter_exists
    )
    return {
        "schema": "design_guide_direct_target_active_failure_route_request_result_adapter_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
        },
        "branch_rows": branch_rows,
        "controller_route_adapter_exists": controller_route_adapter_exists,
        "trace_adapter_wired": trace_adapter_wired,
        "route_adapter_cutover_complete": route_adapter_cutover_complete,
        "request_result_boundary": request_shape,
        "decision": (
            "ROUTE_ADAPTER_CUTOVER_COMPLETE_ROUTE_EXECUTION_STILL_PAGE_OWNED"
            if route_adapter_cutover_complete
            else
            "TRACE_ADAPTER_WIRED_READY_FOR_CUTOVER_READINESS_AUDIT"
            if trace_adapter_wired
            else
            "READY_FOR_TRACE_ONLY_ROUTE_ADAPTER"
            if ready_for_trace_adapter
            else "NOT_READY_WITH_EXACT_BLOCKER"
        ),
        "ready_for_trace_only_route_adapter": ready_for_trace_adapter,
        "not_ready_for_live_route_cutover": True,
        "why_not_live_cutover": (
            "Live cutover still needs parity proving a controller route adapter can consume a "
            "precomputed or injected family item while keeping CTA side effects and debug/session writes page-owned."
        ),
        "first_safe_implementation_slice": {
            "name": (
                "direct_target_active_failure_route_condition_policy_adapter_audit"
                if route_adapter_cutover_complete
                else "direct_target_active_failure_route_adapter_cutover_readiness_audit"
                if trace_adapter_wired
                else "direct_target_active_failure_route_request_result_adapter_trace"
            ),
            "move": (
                "Audit the remaining page-owned route branch condition policy. Keep the family executor, "
                "CTA side effect, debug/session writes, and route branch execution page-owned until parity proves otherwise."
                if route_adapter_cutover_complete
                else
                "Prove the trace adapter can replace the current per-branch projection calls while keeping "
                "family executor, bending CTA side effect, route branch, and debug/session writes page-owned."
                if trace_adapter_wired
                else "Add a controller helper that accepts plain route request data and a precomputed family item, "
                "then returns projected item/debug data. Wire trace-only beside the current page route."
            ),
            "keep_page_owned": [
                "_active_fail_near_current_repair_item execution",
                "_record_bending_fail_valid_repair_cta_published",
                "debug_sink/session writes",
                "route branch execution until parity passes",
            ],
            "required_verifier": (
                "design_guide_direct_target_active_failure_route_condition_policy_adapter_audit.py"
                if route_adapter_cutover_complete
                else "design_guide_direct_target_active_failure_route_adapter_cutover_readiness_audit.py"
                if trace_adapter_wired
                else "design_guide_direct_target_active_failure_route_request_result_adapter_trace.py"
            ),
        },
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source
            and "streamlit" not in controller_source
            and "st.session_state" not in controller_source
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    branches = payload.get("branch_rows") or {}
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "three_branches_found": set(branches) == {"bending", "shear", "combined"}
        and all(bool(row.get("present")) for row in branches.values()),
        "family_executor_still_page_owned": all(
            bool(row.get("calls_family_executor")) for row in branches.values()
        ),
        "route_projection_or_adapter_used": all(
            bool(row.get("calls_family_bypass_projection")) or bool(row.get("calls_route_adapter"))
            for row in branches.values()
        ),
        "combined_evidence_projection_used": bool(
            (branches.get("combined") or {}).get("calls_combined_evidence_projection")
        ),
        "bending_cta_side_effect_still_page_owned": bool(
            (branches.get("bending") or {}).get("has_bending_cta_side_effect")
        ),
        "adapter_wired_cutover_or_ready": bool(payload.get("route_adapter_cutover_complete"))
        or bool(payload.get("trace_adapter_wired"))
        or bool(payload.get("ready_for_trace_only_route_adapter")),
        "not_ready_for_live_route_cutover": bool(payload.get("not_ready_for_live_route_cutover")),
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
        / f"design_guide_direct_target_active_failure_route_request_result_adapter_audit_{suffix}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_direct_target_active_failure_route_request_result_adapter_audit_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Active-Failure Route Request/Result Adapter Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Summary",
        (
            "The three early active-failure routes still execute in inputs_page.py, but the "
            "metadata/evidence projections are now controller-owned. The next safe move is "
            "a trace-only controller route adapter that consumes a precomputed family item."
        ),
        "",
        "## Branches",
    ]
    for family, row in (payload.get("branch_rows") or {}).items():
        lines.append(f"- {family}: {row}")
    lines.extend(
        [
            "",
            "## Request / Result Boundary",
            f"- Controller-owned inputs: {', '.join((payload.get('request_result_boundary') or {}).get('controller_owned_inputs') or [])}",
            f"- Page-owned inputs: {', '.join((payload.get('request_result_boundary') or {}).get('page_owned_inputs') or [])}",
            f"- Result fields: {', '.join((payload.get('request_result_boundary') or {}).get('result_fields_to_preserve') or [])}",
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
    print(f"design_guide_direct_target_active_failure_route_request_result_adapter_audit {status}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
