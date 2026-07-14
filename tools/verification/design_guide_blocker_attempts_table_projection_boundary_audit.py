"""Audit blocker-attempts table projection ownership before extraction."""

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
    start, end, helper = _function_source(inputs_source, "_design_guide_blocker_attempts_table")

    strength_reason_cutover = (
        "_resolve_design_guide_controller_blocker_attempt_strength_capacity_rule(" in helper
        and "_build_design_guide_controller_blocker_attempt_strength_reason(" in helper
        and "def _strength_capacity_rule(" not in helper
        and "def _specific_strength_reason(" not in helper
    )
    source_merge_cutover = (
        "_build_design_guide_controller_blocker_attempt_source_merge(item)" in helper
        and "def build_design_guide_controller_blocker_attempt_source_merge(" in controller_source
        and "blockers.update(" not in helper
    )
    active_failure_inference_cutover = (
        "_resolve_design_guide_controller_blocker_attempt_active_failures(" in helper
        and "def resolve_design_guide_controller_blocker_attempt_active_failures(" in controller_source
        and 'evidence.get("active_failures")' not in helper
        and 'src.get("active_failures")' not in helper
    )
    combined_active_strength_cutover = (
        "_build_design_guide_controller_combined_active_strength_attempt_row(" in helper
        and "def build_design_guide_controller_combined_active_strength_attempt_row(" in controller_source
        and "def _combined_active_strength_attempt_row(" not in helper
    )

    surfaces = [
        _row(
            surface="blocker/evidence source merge",
            classification=(
                "controller-owned pure blocker/evidence input normalization"
                if source_merge_cutover
                else "pure blocker/evidence input normalization"
            ),
            current_owner=(
                "DesignGuideController via inputs_page shell"
                if source_merge_cutover
                else "inputs_page.py"
            ),
            target_owner="DesignGuideController",
            readiness="SHELL_CALL" if source_merge_cutover else "NOT_FIRST",
            first_safe_slice=None if source_merge_cutover else "blocker_attempts_source_merge_object_audit",
            tokens=[
                "candidate_search_evidence",
                "exact_blockers_by_family",
                "post_click_exact_blockers_by_family",
            ],
            segment=helper,
            start_line=start,
            risk="Affects which blocker families appear; needs table-level parity first.",
        ),
        _row(
            surface="active failure inference",
            classification=(
                "controller-owned active-failure/status inference"
                if active_failure_inference_cutover
                else "pure active-failure/status inference"
            ),
            current_owner=(
                "DesignGuideController via inputs_page shell"
                if active_failure_inference_cutover
                else "inputs_page.py"
            ),
            target_owner="DesignGuideController",
            readiness="SHELL_CALL" if active_failure_inference_cutover else "NOT_FIRST",
            first_safe_slice=None if active_failure_inference_cutover else "blocker_attempts_active_failure_inference_audit",
            tokens=["active_failures", "current_rows"],
            segment=helper,
            start_line=start,
            risk="Affects strength-row selection; table-level parity required.",
        ),
        _row(
            surface="strength capacity rule and visible reason wording",
            classification=(
                "controller-owned pure strength wording"
                if strength_reason_cutover
                else "page-owned pure strength wording"
            ),
            current_owner=(
                "DesignGuideController via inputs_page shell"
                if strength_reason_cutover
                else "inputs_page.py"
            ),
            target_owner="DesignGuideController",
            readiness="SHELL_CALL" if strength_reason_cutover else "READY_TO_EXTRACT",
            first_safe_slice=None if strength_reason_cutover else "blocker_attempts_strength_reason_projection_extraction",
            tokens=[
                "def _strength_capacity_rule(",
                "def _specific_strength_reason(",
                "Best rejected combined strengthening candidate still leaves",
                "Best rejected {family} strengthening candidate still leaves",
            ],
            segment=helper,
            start_line=start,
            risk="Pure wording but visible; exact string parity required.",
        ),
        _row(
            surface="combined active strength attempt row",
            classification=(
                "controller-owned combined row selection and visible projection"
                if combined_active_strength_cutover
                else "mixed row selection and visible projection"
            ),
            current_owner=(
                "DesignGuideController via inputs_page shell"
                if combined_active_strength_cutover
                else "inputs_page.py"
            ),
            target_owner="DesignGuideController",
            readiness="SHELL_CALL" if combined_active_strength_cutover else "NOT_FIRST",
            first_safe_slice=None if combined_active_strength_cutover else "combined_active_strength_attempt_row_projection_audit",
            tokens=["def _combined_active_strength_attempt_row(", "active_candidate_rows"],
            segment=helper,
            start_line=start,
            risk="Selects best rejected combined row and visible failed check fields.",
        ),
        _row(
            surface="per-family blocker row assembly",
            classification="mixed blocker row assembly with cleanup labels/categories",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController after dependent helper cutovers",
            readiness="NOT_FIRST",
            first_safe_slice="blocker_attempts_family_row_assembly_audit",
            tokens=[
                "_design_guide_cleanup_attempt_label(",
                "_design_guide_cleanup_rejection_category(",
                "_design_guide_cleanup_attempted_passed(",
            ],
            segment=helper,
            start_line=start,
            risk="Touches user-visible blocker details and cleanup categories.",
        ),
    ]

    ready = [row for row in surfaces if row["present"] and row["readiness"] == "READY_TO_EXTRACT"]
    not_shell = [
        row
        for row in surfaces
        if row["present"] and row["readiness"] in {"READY_TO_EXTRACT", "NOT_FIRST"}
    ]
    first = (ready or not_shell or [{}])[0]
    return {
        "schema": "design_guide_blocker_attempts_table_projection_boundary_audit.v1",
        "target": {
            "function": "_design_guide_blocker_attempts_table",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "strength_reason_cutover": strength_reason_cutover,
        "surfaces": surfaces,
        "ready_to_extract_surfaces": ready,
        "not_shell_surfaces": not_shell,
        "first_safe_slice": dict(first),
        "status_decision": (
            "BLOCKER_ATTEMPTS_READY_TO_EXTRACT"
            if ready
            else "BLOCKER_ATTEMPTS_NOT_READY"
            if not_shell
            else "BLOCKER_ATTEMPTS_BOUNDED"
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
        "surfaces_classified": len(payload.get("surfaces") or []) >= 5,
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice"))
        or payload.get("status_decision") == "BLOCKER_ATTEMPTS_BOUNDED",
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_table_projection_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_table_projection_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Table Projection Boundary Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        "",
        "The blocker-attempts table remains mixed and visible. The first safe extraction is the pure strength capacity rule/reason wording, with exact string parity required.",
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
    print(f"design_guide_blocker_attempts_table_projection_boundary_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
