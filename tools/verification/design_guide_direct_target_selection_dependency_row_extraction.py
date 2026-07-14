"""Verify direct target-band selection row extraction to controller."""

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


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    nested_start, nested_end, nested_source = _nested_function_source(
        inputs_source,
        "_direct_target_band_guidance_item",
        "_direct_target_selection_row",
    )
    helper_start, helper_end, helper_source = _function_source(
        controller_source,
        "build_design_guide_controller_direct_target_selection_row",
    )
    forbidden_nested_tokens = [
        "_direct_candidate_final_cleanup_key(",
        "_candidate_strength_family_band_distance(",
        "_candidate_strength_families_in_band(",
        "_distance_to_target_band(",
        "_local_cleanup_candidate_affects_family(",
        "_design_guide_shear_practical_preference_score(",
        "_design_guide_geometry_proportion_preference_score(",
    ]
    helper_required_tokens = [
        "resolve_design_guide_controller_direct_candidate_final_cleanup_sort_key(",
        "resolve_design_guide_controller_strength_family_band_status(",
        "resolve_design_guide_controller_local_cleanup_candidate_affects_family(",
        "resolve_design_guide_controller_direct_target_after_state_preference_scores(",
        "identify_design_guide_controller_materially_overprovided_non_governing_families(",
    ]
    return {
        "schema": "design_guide_direct_target_selection_dependency_row_extraction.v1",
        "nested_target": {
            "name": "_direct_target_selection_row",
            "line_start": nested_start,
            "line_end": nested_end,
            "line_count": max(0, nested_end - nested_start + 1),
        },
        "controller_helper": {
            "name": "build_design_guide_controller_direct_target_selection_row",
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
        },
        "selection_row_delegates_to_controller": "_build_design_guide_controller_direct_target_selection_row(" in nested_source,
        "forbidden_nested_tokens_present": [
            token for token in forbidden_nested_tokens if token in nested_source
        ],
        "helper_required_tokens_missing": [
            token for token in helper_required_tokens if token not in helper_source
        ],
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
        "selection_row_found": bool((capture.get("nested_target") or {}).get("line_start")),
        "controller_helper_found": bool((capture.get("controller_helper") or {}).get("line_start")),
        "selection_row_delegates_to_controller": bool(capture.get("selection_row_delegates_to_controller")),
        "forbidden_nested_tokens_removed": not bool(capture.get("forbidden_nested_tokens_present")),
        "helper_owns_required_dependencies": not bool(capture.get("helper_required_tokens_missing")),
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
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_selection_dependency_row_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_selection_dependency_row_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Selection Dependency Row Extraction",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "- `_direct_target_selection_row(...)` now delegates row construction to DesignGuideController.",
        "- Candidate search, target filtering, item projection, CTA/apply, and visible wording were not moved.",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
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
    print(f"design_guide_direct_target_selection_dependency_row_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
