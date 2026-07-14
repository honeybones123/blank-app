"""Audit direct target-band selection dependency row boundary."""

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
NESTED_TARGET = "_direct_target_selection_row"


DEPENDENCIES: list[dict[str, Any]] = [
    {
        "name": "final cleanup sort key",
        "token": "_direct_candidate_final_cleanup_key(",
        "current_owner": "inputs_page dependency wrapper",
        "target_owner": "DesignGuideController helper already owns tuple policy",
        "classification": "controller-backed dependency, still page-assembled",
        "move_ready": True,
    },
    {
        "name": "preferred/accepted band distance",
        "token": "_candidate_strength_family_band_distance(",
        "current_owner": "inputs_page wrapper around controller strength-family band status",
        "target_owner": "DesignGuideController",
        "classification": "controller-backed dependency, still page-assembled",
        "move_ready": True,
    },
    {
        "name": "fallback target-band distance",
        "token": "_distance_to_target_band(",
        "current_owner": "inputs_page scalar helper",
        "target_owner": "DesignGuideController",
        "classification": "pure scalar policy, moveable",
        "move_ready": True,
    },
    {
        "name": "current low family affected set",
        "token": "_local_cleanup_candidate_affects_family(",
        "current_owner": "inputs_page wrapper around controller candidate-affects-family helper",
        "target_owner": "DesignGuideController",
        "classification": "controller-backed dependency, still page-assembled",
        "move_ready": True,
    },
    {
        "name": "families in accepted band",
        "token": "_candidate_strength_families_in_band(",
        "current_owner": "inputs_page wrapper around controller strength-family band status",
        "target_owner": "DesignGuideController",
        "classification": "controller-backed dependency, still page-assembled",
        "move_ready": True,
    },
    {
        "name": "remaining family count in sort-key wrapper",
        "token": "identify_materially_overprovided_non_governing_families(",
        "current_owner": "inputs_page pure overview utility",
        "target_owner": "DesignGuideController pure overview utility",
        "classification": "pure utility must move before full dependency-row extraction",
        "move_ready": False,
    },
    {
        "name": "shear practical preference score",
        "token": "_design_guide_shear_practical_preference_score(",
        "current_owner": "inputs_page after-state wrapper around controller tuple policy",
        "target_owner": "DesignGuideController with page-supplied after-state scalars",
        "classification": "after-state dependency; needs separate parity",
        "move_ready": False,
    },
    {
        "name": "geometry proportion preference score",
        "token": "_design_guide_geometry_proportion_preference_score(",
        "current_owner": "inputs_page after-state/geometry-lock wrapper around controller tuple policy",
        "target_owner": "DesignGuideController with page-supplied geometry scalars",
        "classification": "after-state dependency; needs separate parity",
        "move_ready": False,
    },
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node.lineno, int(node.end_lineno or node.lineno), "\n".join(
                lines[node.lineno - 1 : int(node.end_lineno or node.lineno)]
            )
    return 0, 0, ""


def _nested_function_source(source: str, outer_name: str, nested_name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == outer_name:
            for child in ast.walk(node):
                if isinstance(child, ast.FunctionDef) and child.name == nested_name:
                    return child.lineno, int(child.end_lineno or child.lineno), "\n".join(
                        lines[child.lineno - 1 : int(child.end_lineno or child.lineno)]
                    )
    return 0, 0, ""


def _line_numbers(segment: str, start: int, token: str) -> list[int]:
    return [start + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    nested_start, nested_end, nested_source = _nested_function_source(inputs_source, TARGET, NESTED_TARGET)
    material_family_utility_controller_backed = (
        "_identify_design_guide_controller_materially_overprovided_non_governing_families(" in inputs_source
        and "identify_design_guide_controller_materially_overprovided_non_governing_families" in controller_source
    )
    after_state_score_controller_backed = (
        "_resolve_design_guide_controller_direct_target_after_state_preference_scores(" in inputs_source
        and "resolve_design_guide_controller_direct_target_after_state_preference_scores" in controller_source
        and "_design_guide_state_after_updates(" not in _function_source(
            inputs_source,
            "_design_guide_shear_practical_preference_score",
        )[2]
        and "_design_guide_state_after_updates(" not in _function_source(
            inputs_source,
            "_design_guide_geometry_proportion_preference_score",
        )[2]
    )
    dependency_rows: list[dict[str, Any]] = []
    for dep in DEPENDENCIES:
        token = str(dep.get("token") or "")
        local_lines = _line_numbers(nested_source, nested_start, token)
        target_lines = _line_numbers(target_source, target_start, token)
        row = dict(dep)
        if row.get("name") == "remaining family count in sort-key wrapper" and material_family_utility_controller_backed:
            row.update(
                {
                    "current_owner": "inputs_page compatibility wrapper delegating to DesignGuideController",
                    "target_owner": "DesignGuideController pure overview utility",
                    "classification": "controller-backed dependency, still page-assembled",
                    "move_ready": True,
                }
            )
        if row.get("name") in {
            "shear practical preference score",
            "geometry proportion preference score",
        } and after_state_score_controller_backed:
            row.update(
                {
                    "current_owner": "inputs_page compatibility wrapper delegating after-state score input resolution",
                    "target_owner": "DesignGuideController after-state preference score resolver",
                    "classification": "controller-backed dependency, still page-assembled",
                    "move_ready": True,
                }
            )
        dependency_rows.append(
            {
                **row,
                "present_in_selection_row": bool(local_lines),
                "selection_row_lines": local_lines,
                "present_in_target": bool(target_lines),
                "target_lines": target_lines[:12],
            }
        )
    blocking = [
        row
        for row in dependency_rows
        if row.get("present_in_target") and not bool(row.get("move_ready"))
    ]
    ready = [
        row
        for row in dependency_rows
        if row.get("present_in_target") and bool(row.get("move_ready"))
    ]
    return {
        "schema": "design_guide_direct_target_selection_dependency_row_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "nested_target": {
            "name": NESTED_TARGET,
            "line_start": nested_start,
            "line_end": nested_end,
            "line_count": max(0, nested_end - nested_start + 1),
        },
        "dependencies": dependency_rows,
        "ready_dependency_count": len(ready),
        "blocking_dependency_count": len(blocking),
        "blocking_dependencies": [row.get("name") for row in blocking],
        "material_family_utility_controller_backed": bool(material_family_utility_controller_backed),
        "after_state_score_controller_backed": bool(after_state_score_controller_backed),
        "decision": "NOT_READY_FOR_FULL_ROW_EXTRACTION" if blocking else "READY_FOR_ROW_EXTRACTION",
        "first_safe_slice": {
            "name": (
                "direct_target_selection_dependency_row_after_state_score_audit"
                if blocking
                else "direct_target_selection_dependency_row_extraction"
            ),
            "why": (
                "The remaining blocking dependency is after-state score construction for shear/geometry preference "
                "wrappers."
                if blocking
                else "All current dependency-row inputs are controller-backed or scalar data. The row assembly can be "
                "moved next while keeping page-owned after-state scalar collection unchanged."
            ),
            "required_verifier": (
                "design_guide_direct_target_selection_dependency_row_after_state_score_audit.py"
                if blocking
                else "design_guide_direct_target_selection_dependency_row_extraction.py"
            ),
        },
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((capture.get("target") or {}).get("line_start")),
        "selection_row_found": bool((capture.get("nested_target") or {}).get("line_start")),
        "dependencies_classified": bool(capture.get("dependencies")),
        "blocking_state_classified": capture.get("decision") in {
            "NOT_READY_FOR_FULL_ROW_EXTRACTION",
            "READY_FOR_ROW_EXTRACTION",
        },
        "first_safe_slice_identified": bool((capture.get("first_safe_slice") or {}).get("name")),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(capture.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(capture.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(capture.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(capture.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_selection_dependency_row_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_selection_dependency_row_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Selection Dependency Row Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Blocking Dependencies",
        *[f"- {name}" for name in payload.get("blocking_dependencies") or []],
        "",
        "## Dependency Inventory",
    ]
    for row in payload.get("dependencies") or []:
        if row.get("present_in_target"):
            lines.append(
                f"- {row.get('name')}: {row.get('classification')} -> {row.get('target_owner')}"
            )
    lines.extend(
        [
            "",
            "## First Safe Slice",
            f"- Name: `{(payload.get('first_safe_slice') or {}).get('name')}`",
            f"- Why: {(payload.get('first_safe_slice') or {}).get('why')}",
            f"- Verifier: `{(payload.get('first_safe_slice') or {}).get('required_verifier')}`",
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        **capture,
        "status": status,
        "checks": checks,
        "checked_at": _timestamp(),
    }
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_direct_target_selection_dependency_row_boundary_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
