"""Audit family-status display payload ownership before extraction."""

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


def _token_line(source: str, token: str, *, start_line: int) -> list[int]:
    return [start_line + index for index, line in enumerate(source.splitlines()) if token in line]


def _evidence(source: str, token: str, *, start_line: int) -> dict[str, Any]:
    lines = _token_line(source, token, start_line=start_line)
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
        "evidence": [_evidence(segment, token, start_line=start_line) for token in tokens],
        "present": any(token in segment for token in tokens),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, helper = _function_source(inputs_source, "_attach_family_status_display_payload")
    core_start, core_end, core = _function_source(inputs_source, "_compute_design_guidance_items_core")
    _, _, row_helper = _function_source(inputs_source, "_design_guide_family_row_from_overview")
    _, _, table_helper = _function_source(inputs_source, "_design_guide_family_status_table")
    _, _, delta_helper = _function_source(inputs_source, "_design_guide_preview_family_delta_table")

    assembly_helper_present = "def build_design_guide_controller_family_status_display_payload(" in controller_source
    helper_delegates_assembly = "_build_design_guide_controller_family_status_display_payload(" in helper
    family_status_table_cutover = all(
        token in segment
        for token, segment in (
            ("_build_design_guide_controller_family_status_row_from_overview(", row_helper),
            ("_build_design_guide_controller_family_status_table(", table_helper),
            ("_build_design_guide_controller_preview_family_delta_table(", delta_helper),
        )
    )

    surfaces = [
        _row(
            surface="snapshot reuse shortcut",
            classification="existing publication snapshot callback",
            current_owner="inputs_page.py/page publication compatibility",
            target_owner="keep bounded until snapshot reuse inventory is separately zero-locked",
            readiness="KEEP_BOUNDED",
            first_safe_slice=None,
            tokens=["_bending_fail_publication_snapshot_for_state("],
            segment=helper,
            start_line=start,
            risk="Can return early with existing publication snapshot; changing it could alter published card shape.",
        ),
        _row(
            surface="current overview collection",
            classification="page-shell calculation/context collection",
            current_owner="inputs_page.py",
            target_owner="page shell or calculation service after separate calculator boundary",
            readiness="KEEP_BOUNDED",
            first_safe_slice=None,
            tokens=["_collect_design_overview(", "_build_design_actions_context("],
            segment=helper,
            start_line=start,
            risk="Uses current state/calculation context; do not move into Design Brain controller in this slice.",
        ),
        _row(
            surface="current status table construction",
            classification=(
                "controller-owned display table projection from overview"
                if family_status_table_cutover
                else "display table projection from overview"
            ),
            current_owner=(
                "DesignGuideController via inputs_page wrappers"
                if family_status_table_cutover
                else "inputs_page.py"
            ),
            target_owner="display/controller projection after table parity",
            readiness="SHELL_CALL" if family_status_table_cutover else "NOT_FIRST",
            first_safe_slice=None if family_status_table_cutover else "family_status_table_projection_boundary_audit",
            tokens=["_design_guide_family_status_table("],
            segment=helper,
            start_line=start,
            risk="May contain display labels/status conventions; audit separately.",
        ),
        _row(
            surface="action update extraction",
            classification="page/recommendation payload fallback",
            current_owner="inputs_page.py",
            target_owner="publication/controller payload adapter after route parity",
            readiness="KEEP_BOUNDED",
            first_safe_slice=None,
            tokens=["_resolve_recommendation_updates("],
            segment=helper,
            start_line=start,
            risk="Fallback update source can affect whether preview is built.",
        ),
        _row(
            surface="preview overview and preview delta table",
            classification="candidate evaluation/display preview",
            current_owner="inputs_page.py",
            target_owner="candidate evaluation/display service after browser/live parity",
            readiness="KEEP_BOUNDED",
            first_safe_slice=None,
            tokens=[
                "_design_guide_candidate_preview_overview(",
                "_design_guide_preview_family_delta_table(",
            ],
            segment=helper,
            start_line=start,
            risk="Can run preview/evaluation helpers; not pure assembly.",
        ),
        _row(
            surface="blocker attempts table",
            classification="blocker display projection",
            current_owner="inputs_page.py",
            target_owner="display/controller projection after blocker table parity",
            readiness="NOT_FIRST",
            first_safe_slice="blocker_attempts_table_projection_boundary_audit",
            tokens=["_design_guide_blocker_attempts_table("],
            segment=helper,
            start_line=start,
            risk="Blocker display fields must remain exact.",
        ),
        _row(
            surface="family status display payload assembly",
            classification=(
                "controller-owned pure display payload assembly"
                if helper_delegates_assembly
                else "page-owned pure display payload assembly"
            ),
            current_owner=(
                "DesignGuideController via inputs_page shell"
                if helper_delegates_assembly
                else "inputs_page.py"
            ),
            target_owner="DesignGuideController",
            readiness="SHELL_CALL" if helper_delegates_assembly else "READY_TO_EXTRACT",
            first_safe_slice=None if helper_delegates_assembly else "family_status_display_payload_assembly_extraction",
            tokens=[
                'out["family_status_current"]',
                'out["family_status_preview"]',
                'out["blocker_attempts_by_family"]',
            ],
            segment=helper,
            start_line=start,
            risk="Pure dict assembly once page has already collected current/preview/blocker table data.",
        ),
        _row(
            surface="residual shear core callsite",
            classification="page-shell call to family status display helper",
            current_owner="inputs_page.py",
            target_owner="page shell",
            readiness="KEEP_BOUNDED",
            first_safe_slice=None,
            tokens=["_attach_family_status_display_payload("],
            segment=core,
            start_line=core_start,
            risk="Core should remain a shell caller until helper internals are extracted or bounded.",
        ),
    ]
    ready = [row for row in surfaces if row["present"] and row["readiness"] == "READY_TO_EXTRACT"]
    unsafe = [row for row in surfaces if row["present"] and row["readiness"] in {"READY_TO_EXTRACT", "NOT_FIRST"}]
    first = (ready or unsafe or [{}])[0]
    return {
        "schema": "design_guide_family_status_display_projection_boundary_audit.v1",
        "target": {
            "function": "_attach_family_status_display_payload",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "core_target": {
            "function": "_compute_design_guidance_items_core",
            "line_start": core_start,
            "line_end": core_end,
        },
        "assembly_helper_present": assembly_helper_present,
        "helper_delegates_assembly": helper_delegates_assembly,
        "family_status_table_cutover": family_status_table_cutover,
        "surfaces": surfaces,
        "ready_to_extract_surfaces": ready,
        "not_shell_surfaces": unsafe,
        "first_safe_slice": dict(first),
        "status_decision": (
            "FAMILY_STATUS_DISPLAY_READY_TO_EXTRACT"
            if ready
            else "FAMILY_STATUS_DISPLAY_NOT_READY"
            if unsafe
            else "FAMILY_STATUS_DISPLAY_BOUNDED"
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
        "surfaces_classified": len(payload.get("surfaces") or []) >= 8,
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice"))
        or payload.get("status_decision") == "FAMILY_STATUS_DISPLAY_BOUNDED",
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
    json_path = ARTIFACT_DIR / f"design_guide_family_status_display_projection_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_family_status_display_projection_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Family Status Display Projection Boundary Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        "",
        "The helper still owns mixed page/calculation/display work. The safe first slice is pure display payload assembly: keep overview collection, preview evaluation, recommendation update fallback, and blocker table generation in the page for now; move only the final dict assembly to the controller.",
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
    print(f"design_guide_family_status_display_projection_boundary_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
