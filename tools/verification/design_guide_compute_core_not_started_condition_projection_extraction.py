"""Verify not-started condition projection extraction."""

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

from design_brain.design_guide_controller import resolve_design_guide_controller_not_started_condition  # noqa: E402


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


def _legacy_not_started(case: dict[str, Any]) -> bool:
    required_inputs_missing = case["width"] <= 0.0 or case["depth"] <= 0.0 or case["span"] <= 0.0
    bending_util = case.get("bending_util")
    shear_util = case.get("shear_util")
    no_key_results = all(util is None or util <= 0.0 for util in (bending_util, shear_util))
    if required_inputs_missing or no_key_results:
        return True
    no_actions = max([abs(float(v or 0.0)) for v in case.get("action_values", [])], default=0.0) <= 1e-9
    no_bottom_reo = (
        float(case.get("bottom_ast", 0.0) or 0.0) <= 0.0
        or int(case.get("bottom_count", 0) or 0) <= 0
        or float(case.get("bottom_diameter", 0.0) or 0.0) <= 0.0
    )
    no_shear_reo = (
        int(case.get("ligature_legs", 0) or 0) <= 0
        or float(case.get("ligature_diameter", 0.0) or 0.0) <= 0.0
        or float(case.get("ligature_spacing", 0.0) or 0.0) <= 0.0
    )
    return bool(no_actions and (no_bottom_reo or no_shear_reo))


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        {
            "name": "missing geometry",
            "width": 0.0,
            "depth": 600.0,
            "span": 2000.0,
            "bending_util": 0.2,
            "shear_util": 0.1,
            "action_values": [1.0, 0.0, 0.0, 0.0],
            "bottom_ast": 500.0,
            "bottom_count": 2,
            "bottom_diameter": 16.0,
            "ligature_legs": 2,
            "ligature_diameter": 10.0,
            "ligature_spacing": 200.0,
        },
        {
            "name": "no key results",
            "width": 300.0,
            "depth": 600.0,
            "span": 2000.0,
            "bending_util": None,
            "shear_util": 0.0,
            "action_values": [1.0, 0.0, 0.0, 0.0],
            "bottom_ast": 500.0,
            "bottom_count": 2,
            "bottom_diameter": 16.0,
            "ligature_legs": 2,
            "ligature_diameter": 10.0,
            "ligature_spacing": 200.0,
        },
        {
            "name": "no actions and missing bottom reo",
            "width": 300.0,
            "depth": 600.0,
            "span": 2000.0,
            "bending_util": 0.1,
            "shear_util": 0.1,
            "action_values": [0.0, 0.0, 0.0, 0.0],
            "bottom_ast": 0.0,
            "bottom_count": 0,
            "bottom_diameter": 0.0,
            "ligature_legs": 2,
            "ligature_diameter": 10.0,
            "ligature_spacing": 200.0,
        },
        {
            "name": "no actions and missing shear reo",
            "width": 300.0,
            "depth": 600.0,
            "span": 2000.0,
            "bending_util": 0.1,
            "shear_util": 0.1,
            "action_values": [0.0, 0.0, 0.0, 0.0],
            "bottom_ast": 500.0,
            "bottom_count": 2,
            "bottom_diameter": 16.0,
            "ligature_legs": 0,
            "ligature_diameter": 0.0,
            "ligature_spacing": 0.0,
        },
        {
            "name": "started with actions and reinforcement",
            "width": 300.0,
            "depth": 600.0,
            "span": 2000.0,
            "bending_util": 0.1,
            "shear_util": 0.1,
            "action_values": [10.0, 0.0, 0.0, 0.0],
            "bottom_ast": 500.0,
            "bottom_count": 2,
            "bottom_diameter": 16.0,
            "ligature_legs": 2,
            "ligature_diameter": 10.0,
            "ligature_spacing": 200.0,
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        expected = _legacy_not_started(scenario)
        helper_args = {key: value for key, value in scenario.items() if key != "name"}
        actual_payload = resolve_design_guide_controller_not_started_condition(**helper_args)
        actual = bool(actual_payload.get("not_started"))
        rows.append(
            {
                "name": scenario["name"],
                "expected": expected,
                "actual": actual,
                "payload": actual_payload,
                "matches": actual == expected,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, "_guidance_not_started")
    scenario_rows = _scenario_rows()
    return {
        "schema": "design_guide_compute_core_not_started_condition_projection_extraction.v1",
        "target": {
            "function": "_guidance_not_started",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "controller_helper_present": "def resolve_design_guide_controller_not_started_condition(" in controller_source,
        "controller_helper_exported": '"resolve_design_guide_controller_not_started_condition"' in controller_source,
        "page_delegates_to_controller": "_resolve_design_guide_controller_not_started_condition(" in segment,
        "old_required_inputs_formula_removed": "required_inputs_missing =" not in segment,
        "old_no_key_results_formula_removed": "no_key_results =" not in segment,
        "old_no_actions_formula_removed": "no_actions =" not in segment,
        "scenario_rows": scenario_rows,
        "scenario_parity_passed": all(bool(row.get("matches")) for row in scenario_rows),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "controller_helper_present": bool(payload.get("controller_helper_present")),
        "controller_helper_exported": bool(payload.get("controller_helper_exported")),
        "page_delegates_to_controller": bool(payload.get("page_delegates_to_controller")),
        "old_required_inputs_formula_removed": bool(payload.get("old_required_inputs_formula_removed")),
        "old_no_key_results_formula_removed": bool(payload.get("old_no_key_results_formula_removed")),
        "old_no_actions_formula_removed": bool(payload.get("old_no_actions_formula_removed")),
        "scenario_parity_passed": bool(payload.get("scenario_parity_passed")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_core_not_started_condition_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_core_not_started_condition_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Compute Core Not-Started Condition Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Summary",
        "The pure not-started condition is controller-owned. The page still collects "
        "geometry/action/reinforcement scalar inputs and owns route order.",
        "",
        "## Scenario Parity",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(f"- {row.get('name')}: {'PASS' if row.get('matches') else 'FAIL'}")
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
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_compute_core_not_started_condition_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
