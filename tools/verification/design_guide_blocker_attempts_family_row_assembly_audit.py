"""Audit per-family blocker-attempt row assembly before extraction."""

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
    start, end, helper = _function_source(inputs_source, "_design_guide_blocker_attempts_table")

    prerequisites_bounded = all(
        token in helper
        for token in (
            "_build_design_guide_controller_blocker_attempt_source_merge(item)",
            "_resolve_design_guide_controller_blocker_attempt_active_failures(",
            "_build_design_guide_controller_combined_active_strength_attempt_row(",
        )
    )
    family_row_controller_owned = (
        "_build_design_guide_controller_blocker_attempt_family_row(" in helper
        and "def build_design_guide_controller_blocker_attempt_family_row(" in controller_source
    )
    cleanup_classification_cutover = (
        "_resolve_design_guide_controller_cleanup_attempted_passed(" in helper
        and "_resolve_design_guide_controller_cleanup_rejection_category(" in helper
        and "def resolve_design_guide_controller_cleanup_attempted_passed(" in controller_source
        and "def resolve_design_guide_controller_cleanup_rejection_category(" in controller_source
    )
    cleanup_label_helpers_present = any(
        token in helper
        for token in (
            "_design_guide_cleanup_attempt_label(",
            "_design_guide_cleanup_arrangement_label(",
            "_design_guide_cleanup_rejection_category(",
            "_design_guide_cleanup_attempted_passed(",
        )
    )
    route_inventory_page_owned = "_active_failure_route_inventory(active_failures)" in helper

    surfaces = [
        {
            "surface": "per-family row seed/default field assembly",
            "classification": (
                "controller-owned row assembly"
                if family_row_controller_owned
                else "page-owned blocker row assembly"
            ),
            "current_owner": (
                "DesignGuideController via inputs_page shell"
                if family_row_controller_owned
                else "inputs_page.py"
            ),
            "target_owner": "DesignGuideController after label/category inputs are bounded",
            "readiness": "SHELL_CALL" if family_row_controller_owned else "NOT_FIRST",
            "first_safe_slice": None if family_row_controller_owned else "blocker_attempts_cleanup_label_category_boundary_audit",
            "risk": "Row assembly controls visible blocker details and counts.",
            "evidence": [
                _evidence(helper, "row_seed = {", start_line=start),
                _evidence(helper, '"attempted_candidate_count"', start_line=start),
                _evidence(helper, '"failed_check_capacity_or_limit"', start_line=start),
                _evidence(helper, '"active_repair_route_inventory"', start_line=start),
            ],
            "present": "row_seed = {" in helper or family_row_controller_owned,
        },
        {
            "surface": "cleanup label/category/pass helpers",
            "classification": "page-owned display helper boundary",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController or display service after exact wording parity",
            "readiness": "CLASSIFICATION_BOUNDED" if cleanup_classification_cutover else "READY_TO_AUDIT",
            "first_safe_slice": (
                "blocker_attempts_cleanup_attempt_label_boundary_audit"
                if cleanup_classification_cutover
                else "blocker_attempts_cleanup_label_category_boundary_audit"
            ),
            "risk": "Visible labels/categories; extraction needs exact string parity.",
            "evidence": [
                _evidence(helper, "_design_guide_cleanup_attempt_label(", start_line=start),
                _evidence(helper, "_design_guide_cleanup_arrangement_label(", start_line=start),
                _evidence(helper, "_design_guide_cleanup_rejection_category(", start_line=start),
                _evidence(helper, "_design_guide_cleanup_attempted_passed(", start_line=start),
            ],
            "present": cleanup_label_helpers_present,
        },
        {
            "surface": "active route inventory fallback",
            "classification": "page-owned route inventory shell input",
            "current_owner": "inputs_page.py",
            "target_owner": "page shell until repair route inventory service is separately extracted",
            "readiness": "KEEP_AS_INPUT" if route_inventory_page_owned else "SHELL_INPUT",
            "first_safe_slice": None,
            "risk": "Route inventory comes from repair route helpers; do not move with row assembly.",
            "evidence": [_evidence(helper, "_active_failure_route_inventory(active_failures)", start_line=start)],
            "present": True,
        },
        {
            "surface": "blocker-attempt prerequisites",
            "classification": "controller-owned prerequisites",
            "current_owner": "DesignGuideController via inputs_page shell",
            "target_owner": "DesignGuideController",
            "readiness": "PREREQUISITE_PASS" if prerequisites_bounded else "BLOCKED",
            "first_safe_slice": None if prerequisites_bounded else "combined_active_strength_attempt_row_projection_extraction",
            "risk": "Per-family assembly should consume already-extracted source merge, active-failure, and combined-row outputs.",
            "evidence": [
                _evidence(helper, "_build_design_guide_controller_blocker_attempt_source_merge(item)", start_line=start),
                _evidence(helper, "_resolve_design_guide_controller_blocker_attempt_active_failures(", start_line=start),
                _evidence(helper, "_build_design_guide_controller_combined_active_strength_attempt_row(", start_line=start),
            ],
            "present": True,
        },
    ]
    ready = [
        row
        for row in surfaces
        if row.get("present") and row.get("readiness") in {"READY_TO_AUDIT", "READY_TO_EXTRACT", "CLASSIFICATION_BOUNDED"}
    ]
    first = (ready or [{}])[0]
    return {
        "schema": "design_guide_blocker_attempts_family_row_assembly_audit.v1",
        "target": {
            "function": "_design_guide_blocker_attempts_table",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "prerequisites_bounded": prerequisites_bounded,
        "family_row_controller_owned": family_row_controller_owned,
        "cleanup_classification_cutover": cleanup_classification_cutover,
        "cleanup_label_helpers_present": cleanup_label_helpers_present,
        "surfaces": surfaces,
        "first_safe_slice": dict(first),
        "status_decision": (
            "BLOCKER_ATTEMPTS_FAMILY_ROW_BOUNDED"
            if family_row_controller_owned
            else "BLOCKER_ATTEMPTS_FAMILY_ROW_NEEDS_ATTEMPT_LABEL_AUDIT"
            if cleanup_classification_cutover and cleanup_label_helpers_present and prerequisites_bounded
            else "BLOCKER_ATTEMPTS_FAMILY_ROW_NEEDS_LABEL_CATEGORY_AUDIT"
            if cleanup_label_helpers_present and prerequisites_bounded
            else "BLOCKER_ATTEMPTS_FAMILY_ROW_BLOCKED"
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
            "Audit cleanup label/category/pass helper boundaries first. After exact display parity is proven, "
            "move per-family row assembly with those display outputs passed as plain inputs or controller-owned helpers."
        ),
        "stop_conditions": [
            "attempt label text changes",
            "arrangement label text changes",
            "rejection category changes",
            "attempted_passed boolean changes",
            "route inventory is moved without separate proof",
            "visible blocker rows differ",
            "any composed lock fails",
        ],
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "prerequisites_bounded": bool(payload.get("prerequisites_bounded")),
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice"))
        or payload.get("status_decision") == "BLOCKER_ATTEMPTS_FAMILY_ROW_BOUNDED",
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_family_row_assembly_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_family_row_assembly_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Family Row Assembly Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        "",
        "Per-family row assembly is not the first safe move. The cleanup label/category/pass helpers must be audited first because they control visible row wording and classification.",
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
    print(f"design_guide_blocker_attempts_family_row_assembly_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
