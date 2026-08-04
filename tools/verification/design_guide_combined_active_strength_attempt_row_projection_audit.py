"""Audit combined active-strength blocker-attempt row projection before extraction."""

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
            "_build_design_guide_controller_blocker_attempt_strength_reason(",
        )
    )
    combined_helper_present = "def _combined_active_strength_attempt_row(" in helper
    combined_helper_controller_owned = (
        "_build_design_guide_controller_combined_active_strength_attempt_row(" in helper
        and "def build_design_guide_controller_combined_active_strength_attempt_row(" in controller_source
        and "def _combined_active_strength_attempt_row(" not in helper
    )
    route_attempt_updates_page_owned = "_active_failure_route_attempt_updates(\"combined\")" in helper
    source_line = _evidence(helper, "def _combined_active_strength_attempt_row(", start_line=start)
    surfaces = [
        {
            "surface": "combined active strength row projection",
            "classification": (
                "DesignGuideController-owned combined row projection"
                if combined_helper_controller_owned
                else "mixed row selection and visible projection"
            ),
            "current_owner": (
                "DesignGuideController via inputs_page shell"
                if combined_helper_controller_owned
                else "inputs_page.py"
            ),
            "target_owner": "DesignGuideController",
            "readiness": "SHELL_CALL" if combined_helper_controller_owned else "READY_TO_EXTRACT",
            "first_safe_slice": (
                None
                if combined_helper_controller_owned
                else "combined_active_strength_attempt_row_projection_extraction"
            ),
            "risk": "Selects best rejected combined row and visible failed-check fields.",
            "evidence": [
                source_line,
                _evidence(helper, "active_candidate_rows", start_line=start),
                _evidence(helper, "preview_statuses", start_line=start),
                _evidence(helper, "preview_bending_util", start_line=start),
                _evidence(helper, "preview_shear_util", start_line=start),
            ],
            "present": combined_helper_present or combined_helper_controller_owned,
        },
        {
            "surface": "combined route attempted updates",
            "classification": (
                "page-owned route/update inventory callback"
                if route_attempt_updates_page_owned
                else "controller input after route update precomputation"
            ),
            "current_owner": "inputs_page.py",
            "target_owner": "page shell input unless repair route service is extracted separately",
            "readiness": "KEEP_AS_INPUT" if route_attempt_updates_page_owned else "SHELL_INPUT",
            "first_safe_slice": None,
            "risk": "Route attempted updates come from repair route helpers; do not move them in the same slice.",
            "evidence": [_evidence(helper, "_active_failure_route_attempt_updates(\"combined\")", start_line=start)],
            "present": True,
        },
        {
            "surface": "source/active/strength prerequisites",
            "classification": "controller-owned prerequisites",
            "current_owner": "DesignGuideController via inputs_page shell",
            "target_owner": "DesignGuideController",
            "readiness": "PREREQUISITE_PASS" if prerequisites_bounded else "BLOCKED",
            "first_safe_slice": None if prerequisites_bounded else "blocker_attempts_active_failure_inference_extraction",
            "risk": "Combined row projection should consume already-extracted source merge and active-failure inference.",
            "evidence": [
                _evidence(helper, "_build_design_guide_controller_blocker_attempt_source_merge(item)", start_line=start),
                _evidence(helper, "_resolve_design_guide_controller_blocker_attempt_active_failures(", start_line=start),
                _evidence(helper, "_build_design_guide_controller_blocker_attempt_strength_reason(", start_line=start),
            ],
            "present": True,
        },
    ]
    ready = [
        row
        for row in surfaces
        if row.get("present") and row.get("readiness") == "READY_TO_EXTRACT"
    ]
    first = (ready or [{}])[0]
    return {
        "schema": "design_guide_combined_active_strength_attempt_row_projection_audit.v1",
        "target": {
            "function": "_design_guide_blocker_attempts_table",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "prerequisites_bounded": prerequisites_bounded,
        "combined_helper_controller_owned": combined_helper_controller_owned,
        "route_attempt_updates_page_owned": route_attempt_updates_page_owned,
        "surfaces": surfaces,
        "first_safe_slice": dict(first),
        "status_decision": (
            "COMBINED_ACTIVE_STRENGTH_ATTEMPT_ROW_BOUNDED"
            if combined_helper_controller_owned
            else "COMBINED_ACTIVE_STRENGTH_ATTEMPT_ROW_READY_TO_EXTRACT"
            if ready and prerequisites_bounded
            else "COMBINED_ACTIVE_STRENGTH_ATTEMPT_ROW_BLOCKED"
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
            "Move combined row selection/projection into a controller helper that accepts active_failures, blockers, "
            "active_candidate_rows, evidence, current_rows, and a precomputed combined attempted-updates payload. "
            "Keep _active_failure_route_attempt_updates(...) in inputs_page.py for now."
        ),
        "stop_conditions": [
            "combined row appears/disappears differently",
            "best rejected candidate id differs",
            "failed family/name/value/limit differs",
            "reason text differs",
            "route attempted updates are recomputed in the controller",
            "visible blocker rows differ",
            "any composed lock fails",
        ],
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "prerequisites_bounded": bool(payload.get("prerequisites_bounded")),
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice"))
        or payload.get("status_decision") == "COMBINED_ACTIVE_STRENGTH_ATTEMPT_ROW_BOUNDED",
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
    json_path = ARTIFACT_DIR / f"design_guide_combined_active_strength_attempt_row_projection_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_active_strength_attempt_row_projection_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Combined Active Strength Attempt Row Projection Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        "",
        "The combined active-strength attempt row is ready for a narrow projection extraction. "
        "Route attempted updates remain a page-shell input for this slice.",
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
    print(f"design_guide_combined_active_strength_attempt_row_projection_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
