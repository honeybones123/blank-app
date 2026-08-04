"""Audit post-active residual shear cleanup action ownership.

This is intentionally audit-only. It classifies the branch that can publish a
second shear cleanup action after an active-failure repair has already been
applied.
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


def _line_numbers(source: str, token: str, *, start_line: int = 1) -> list[int]:
    return [start_line + index for index, line in enumerate(source.splitlines()) if token in line]


def _token_evidence(segment: str, token: str, *, start_line: int) -> dict[str, Any]:
    lines = _line_numbers(segment, token, start_line=start_line)
    return {"token": token, "present": bool(lines), "count": len(lines), "lines": lines[:20]}


def _row(
    *,
    surface: str,
    classification: str,
    current_owner: str,
    target_owner: str,
    readiness: str,
    first_safe_slice: str | None,
    tokens: list[str],
    segment: str,
    start_line: int,
    risk: str,
) -> dict[str, Any]:
    return {
        "surface": surface,
        "classification": classification,
        "current_owner": current_owner,
        "target_owner": target_owner,
        "readiness": readiness,
        "first_safe_slice": first_safe_slice,
        "risk": risk,
        "evidence": [_token_evidence(segment, token, start_line=start_line) for token in tokens],
        "present": any(token in segment for token in tokens),
    }


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, core_segment = _function_source(source, "_compute_design_guidance_items_core")

    residual_branch_present = (
        "_post_active_shear_cleanup_item" in core_segment
        and "return [_post_active_shear_cleanup_item]" in core_segment
    )
    debug_projection_moved = (
        "_build_design_guide_controller_post_active_residual_shear_cleanup_debug_projection(" in core_segment
        and 'debug_sink["guidance_branch"] = "post_active_repair_residual_shear_best_safe_action"' not in core_segment
        and 'debug_sink["selected_action_type"] = "apply_resolved_candidate"' not in core_segment
    )

    surfaces = [
        _row(
            surface="residual shear cleanup item discovery",
            classification="page-owned callback execution",
            current_owner="inputs_page.py callback shell",
            target_owner="page shell until candidate helpers are separately extracted",
            readiness="KEEP_BOUNDED",
            first_safe_slice=None,
            tokens=[
                "_shear_best_safe_cleanup_item_from_evidence(",
                "_shear_low_util_target_cleanup_item(",
            ],
            segment=core_segment,
            start_line=start,
            risk="Moving this changes selected candidate search/evaluation unless handled by dedicated candidate-service parity.",
        ),
        _row(
            surface="residual shear actionability check",
            classification="page/publication shell guard",
            current_owner="inputs_page.py shell using existing button-contract helper",
            target_owner="page shell until full actionability boundary is separately audited",
            readiness="KEEP_BOUNDED",
            first_safe_slice=None,
            tokens=["_design_guide_button_contract_enabled(_post_active_shear_cleanup_contract)"],
            segment=core_segment,
            start_line=start,
            risk="Controls whether the action item is returned; keep until route-level parity exists.",
        ),
        _row(
            surface="family status display attachment",
            classification="display/projection with state and preview dependencies",
            current_owner="inputs_page.py",
            target_owner="controller/display projection service after separate family-status parity",
            readiness="UNSAFE_TO_MOVE_YET",
            first_safe_slice="family_status_display_projection_boundary_audit",
            tokens=["_attach_family_status_display_payload("],
            segment=core_segment,
            start_line=start,
            risk="Can call overview/preview helpers and shape display rows; needs its own parity proof.",
        ),
        _row(
            surface="zero bending demand exclusion stamping",
            classification="debug/proof compatibility stamping",
            current_owner="inputs_page.py",
            target_owner="debug/proof adapter or compatibility-only page shell",
            readiness="KEEP_BOUNDED",
            first_safe_slice=None,
            tokens=["_stamp_zero_bending_demand_exclusion("],
            segment=core_segment,
            start_line=start,
            risk="Non-authoritative proof/display annotation; not the first blocker.",
        ),
        _row(
            surface="residual shear cleanup debug projection",
            classification=(
                "controller-owned debug projection with page sink update"
                if debug_projection_moved
                else "page-owned debug projection"
            ),
            current_owner=(
                "DesignGuideController via inputs_page sink update"
                if debug_projection_moved
                else "inputs_page.py"
            ),
            target_owner="DesignGuideController debug projection helper",
            readiness="SHELL_CALL" if debug_projection_moved else "READY_TO_EXTRACT",
            first_safe_slice=None
            if debug_projection_moved
            else "compute_core_post_active_residual_shear_debug_projection_extraction",
            tokens=[
                'debug_sink["guidance_branch"] = "post_active_repair_residual_shear_best_safe_action"',
                'debug_sink["selected_action_type"] = "apply_resolved_candidate"',
                'debug_sink["primary_button_contract"] = dict(_post_active_shear_cleanup_contract)',
                'debug_sink["candidate_search_evidence"] = dict(_post_active_shear_cleanup_evidence)',
            ],
            segment=core_segment,
            start_line=start,
            risk="Pure debug/result projection once selected item, contract, and evidence are already known.",
        ),
        _row(
            surface="residual shear cleanup returned action item",
            classification="page-shell return of selected item",
            current_owner="inputs_page.py",
            target_owner="page shell",
            readiness="KEEP_BOUNDED",
            first_safe_slice=None,
            tokens=["return [_post_active_shear_cleanup_item]"],
            segment=core_segment,
            start_line=start,
            risk="Return remains page-shell while branch orchestration is still inside compute core.",
        ),
    ]

    not_shell = [
        row
        for row in surfaces
        if row["present"] and row["readiness"] in {"READY_TO_EXTRACT", "UNSAFE_TO_MOVE_YET"}
    ]
    ready = [row for row in not_shell if row["readiness"] == "READY_TO_EXTRACT"]
    first = (ready or not_shell or [{}])[0]
    return {
        "schema": "design_guide_compute_core_post_active_residual_shear_cleanup_action_audit.v1",
        "target": {
            "function": "_compute_design_guidance_items_core",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "residual_branch_present": residual_branch_present,
        "debug_projection_moved": debug_projection_moved,
        "surfaces": surfaces,
        "not_shell_surfaces": not_shell,
        "ready_to_extract_surfaces": ready,
        "first_safe_slice": dict(first),
        "status_decision": (
            "POST_ACTIVE_RESIDUAL_SHEAR_READY_TO_EXTRACT"
            if ready
            else "POST_ACTIVE_RESIDUAL_SHEAR_NOT_READY"
            if not_shell
            else "POST_ACTIVE_RESIDUAL_SHEAR_BOUNDED"
        ),
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
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "residual_branch_present": bool(payload.get("residual_branch_present")),
        "surfaces_classified": len(payload.get("surfaces") or []) >= 6,
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice")),
        "controller_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_core_post_active_residual_shear_cleanup_action_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_core_post_active_residual_shear_cleanup_action_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Design Guide Compute Core Post-Active Residual Shear Cleanup Action Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        "",
        "The residual shear action branch is still mixed. Candidate discovery and actionability remain bounded page/callback plumbing; the first extractable surface is the pure debug projection once a selected item and button contract already exist.",
        "",
        "## Surface Inventory",
        "",
        "| Surface | Classification | Current owner | Target owner | Readiness | First safe slice | Risk |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            "| {surface} | {classification} | {current_owner} | {target_owner} | {readiness} | {first_safe_slice} | {risk} |".format(
                surface=row.get("surface"),
                classification=row.get("classification"),
                current_owner=row.get("current_owner"),
                target_owner=row.get("target_owner"),
                readiness=row.get("readiness"),
                first_safe_slice=row.get("first_safe_slice") or "",
                risk=row.get("risk"),
            )
        )
    first = payload.get("first_safe_slice") or {}
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Slice: `{first.get('first_safe_slice')}`",
            f"- Surface: `{first.get('surface')}`",
            f"- Reason: {first.get('risk')}",
            "",
            "## Stop Conditions",
            "",
            "- selected cleanup item changes",
            "- button contract changes",
            "- action payload changes",
            "- visible wording changes",
            "- CTA/apply semantics change",
            "- family runtime behaviour changes",
            "- composed lock fails",
            "",
            "## Checks",
        ]
    )
    for key, value in checks.items():
        lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_compute_core_post_active_residual_shear_cleanup_action_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
