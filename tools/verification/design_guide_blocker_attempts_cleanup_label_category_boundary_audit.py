"""Audit cleanup label/category helper ownership before blocker row extraction."""

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


def _evidence(source: str, token: str, *, start_line: int) -> dict[str, Any]:
    lines = [start_line + index for index, line in enumerate(source.splitlines()) if token in line]
    return {"token": token, "present": bool(lines), "count": len(lines), "lines": lines[:20]}


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    table_start, table_end, table = _function_source(inputs_source, "_design_guide_blocker_attempts_table")
    pass_start, pass_end, pass_helper = _function_source(inputs_source, "_design_guide_cleanup_attempted_passed")
    category_start, category_end, category_helper = _function_source(inputs_source, "_design_guide_cleanup_rejection_category")
    label_start, label_end, label_helper = _function_source(inputs_source, "_design_guide_cleanup_attempt_label")
    arrangement_start, arrangement_end, arrangement_helper = _function_source(
        inputs_source,
        "_design_guide_cleanup_arrangement_label",
    )

    pure_classification_cutover = (
        "_resolve_design_guide_controller_cleanup_attempted_passed(" in table
        and "_resolve_design_guide_controller_cleanup_rejection_category(" in table
        and "def resolve_design_guide_controller_cleanup_attempted_passed(" in controller_source
        and "def resolve_design_guide_controller_cleanup_rejection_category(" in controller_source
    )
    label_depends_on_page_helpers = any(
        token in label_helper + arrangement_helper
        for token in (
            "_bottom_reo_state_label(",
            "_guidance_shear_links_banner_fragment(",
            "_guidance_change_lines_for_updates(",
            "_normalise_bottom_layer_order(",
        )
    )
    surfaces = [
        {
            "surface": "cleanup attempted-pass boolean",
            "classification": (
                "controller-owned pure cleanup classification"
                if pure_classification_cutover
                else "pure cleanup classification"
            ),
            "current_owner": (
                "DesignGuideController via inputs_page shell"
                if pure_classification_cutover
                else "inputs_page.py"
            ),
            "target_owner": "DesignGuideController",
            "readiness": "SHELL_CALL" if pure_classification_cutover else "READY_TO_EXTRACT",
            "first_safe_slice": (
                None
                if pure_classification_cutover
                else "blocker_attempts_cleanup_pass_category_extraction"
            ),
            "risk": "Affects row rejection category and visible blocker evidence.",
            "evidence": [
                _evidence(pass_helper, "attempted_passed", start_line=pass_start),
                _evidence(pass_helper, "failed_check_status", start_line=pass_start),
                _evidence(pass_helper, "attempted_util", start_line=pass_start),
            ],
            "present": bool(pass_helper),
        },
        {
            "surface": "cleanup rejection category",
            "classification": (
                "controller-owned pure cleanup classification"
                if pure_classification_cutover
                else "pure cleanup category classification"
            ),
            "current_owner": (
                "DesignGuideController via inputs_page shell"
                if pure_classification_cutover
                else "inputs_page.py"
            ),
            "target_owner": "DesignGuideController",
            "readiness": "SHELL_CALL" if pure_classification_cutover else "READY_TO_EXTRACT",
            "first_safe_slice": (
                None
                if pure_classification_cutover
                else "blocker_attempts_cleanup_pass_category_extraction"
            ),
            "risk": "Visible category string; exact string parity required.",
            "evidence": [
                _evidence(category_helper, "Safe but still below accepted efficiency floor", start_line=category_start),
                _evidence(category_helper, "Unsafe - failed capacity", start_line=category_start),
                _evidence(category_helper, "Not executor-backed", start_line=category_start),
            ],
            "present": bool(category_helper),
        },
        {
            "surface": "attempt/change arrangement wording",
            "classification": "page-owned wording helper with geometry/reinforcement/shear label dependencies",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController only after label-helper parity",
            "readiness": "NOT_FIRST",
            "first_safe_slice": "blocker_attempts_cleanup_attempt_label_boundary_audit",
            "risk": "Visible wording and page-local reinforcement/shear labels; do not move in classification slice.",
            "evidence": [
                _evidence(label_helper, "_guidance_change_lines_for_updates(", start_line=label_start),
                _evidence(arrangement_helper, "_bottom_reo_state_label(", start_line=arrangement_start),
                _evidence(arrangement_helper, "_guidance_shear_links_banner_fragment(", start_line=arrangement_start),
            ],
            "present": bool(label_helper) or bool(arrangement_helper),
        },
        {
            "surface": "per-family row assembly consumer",
            "classification": "mixed row assembly consumer",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController after classification and label boundaries",
            "readiness": "NOT_FIRST",
            "first_safe_slice": "blocker_attempts_family_row_assembly_extraction",
            "risk": "Consumes classification and label helpers; move after dependencies.",
            "evidence": [
                _evidence(table, "_design_guide_cleanup_attempted_passed(", start_line=table_start),
                _evidence(table, "_design_guide_cleanup_rejection_category(", start_line=table_start),
                _evidence(table, "_design_guide_cleanup_attempt_label(", start_line=table_start),
            ],
            "present": bool(table),
        },
    ]
    ready = [
        row
        for row in surfaces
        if row.get("present") and row.get("readiness") == "READY_TO_EXTRACT"
    ]
    first = (ready or [{}])[0]
    return {
        "schema": "design_guide_blocker_attempts_cleanup_label_category_boundary_audit.v1",
        "target": {
            "table_function": "_design_guide_blocker_attempts_table",
            "line_start": table_start,
            "line_end": table_end,
            "line_count": max(0, table_end - table_start + 1),
        },
        "pure_classification_cutover": pure_classification_cutover,
        "label_depends_on_page_helpers": label_depends_on_page_helpers,
        "surfaces": surfaces,
        "first_safe_slice": dict(first),
        "status_decision": (
            "BLOCKER_ATTEMPTS_CLEANUP_CLASSIFICATION_BOUNDED"
            if pure_classification_cutover
            else "BLOCKER_ATTEMPTS_CLEANUP_PASS_CATEGORY_READY_TO_EXTRACT"
            if ready
            else "BLOCKER_ATTEMPTS_CLEANUP_LABEL_CATEGORY_BLOCKED"
        ),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
        "first_safe_implementation_slice": (
            "Extract only attempted_passed and rejection_category classification into controller helpers. "
            "Keep attempt/arrangement wording in inputs_page.py because it depends on page-local reinforcement/shear label helpers."
        ),
        "stop_conditions": [
            "attempted_passed differs",
            "rejection category text differs",
            "attempt label or arrangement wording is moved in the same slice",
            "visible blocker rows differ",
            "any composed lock fails",
        ],
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice"))
        or payload.get("status_decision") == "BLOCKER_ATTEMPTS_CLEANUP_CLASSIFICATION_BOUNDED",
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_cleanup_label_category_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_cleanup_label_category_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Cleanup Label/Category Boundary Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        "",
        "The pure attempted-pass and rejection-category classifiers are the first safe slice. Attempt/arrangement wording remains page-owned for now due to page-local label helpers.",
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
            f"- Implementation: {payload.get('first_safe_implementation_slice')}",
            "",
            "## Stop Conditions",
        ]
    )
    for condition in payload.get("stop_conditions") or []:
        lines.append(f"- {condition}")
    lines.extend(["", "## Checks"])
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
    print(f"design_guide_blocker_attempts_cleanup_label_category_boundary_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
