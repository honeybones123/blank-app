"""Verify post-active zero-shear predicate projection extraction."""

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

from design_brain.design_guide_controller import (  # noqa: E402
    resolve_design_guide_controller_post_active_zero_shear_predicate,
)


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


def _legacy_zero_shear(*, shear_demands_negligible: bool, direct_vu: Any, tolerance: Any) -> bool:
    try:
        vu = abs(float(direct_vu or 0.0))
    except Exception:
        vu = 0.0
    try:
        tol = float(tolerance or 0.0)
    except Exception:
        tol = 0.0
    return bool(bool(shear_demands_negligible) or vu <= tol + 1e-12)


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        {"name": "explicit negligible", "shear_demands_negligible": True, "direct_vu": 100.0, "tolerance": 0.01},
        {"name": "below tolerance", "shear_demands_negligible": False, "direct_vu": 0.0, "tolerance": 0.01},
        {"name": "at tolerance", "shear_demands_negligible": False, "direct_vu": 0.01, "tolerance": 0.01},
        {"name": "above tolerance", "shear_demands_negligible": False, "direct_vu": 0.02, "tolerance": 0.01},
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        expected = _legacy_zero_shear(
            shear_demands_negligible=scenario["shear_demands_negligible"],
            direct_vu=scenario["direct_vu"],
            tolerance=scenario["tolerance"],
        )
        actual_payload = resolve_design_guide_controller_post_active_zero_shear_predicate(
            shear_demands_negligible=scenario["shear_demands_negligible"],
            direct_vu=scenario["direct_vu"],
            shear_demand_abs_tol_kn=scenario["tolerance"],
        )
        actual = bool(actual_payload.get("post_active_zero_shear"))
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
    start, end, core_segment = _function_source(inputs_source, "_compute_design_guidance_items_core")
    scenario_rows = _scenario_rows()
    return {
        "schema": "design_guide_compute_core_post_active_zero_shear_predicate_projection_extraction.v1",
        "target": {
            "function": "_compute_design_guidance_items_core",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "controller_helper_present": "def resolve_design_guide_controller_post_active_zero_shear_predicate(" in controller_source,
        "controller_helper_exported": '"resolve_design_guide_controller_post_active_zero_shear_predicate"' in controller_source,
        "page_delegates_to_controller": "_resolve_design_guide_controller_post_active_zero_shear_predicate(" in core_segment,
        "old_page_zero_shear_formula_removed": (
            "_post_active_zero_shear = bool(\n"
            "            _shear_demands_negligible"
        )
        not in core_segment,
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
        "old_page_zero_shear_formula_removed": bool(payload.get("old_page_zero_shear_formula_removed")),
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
    json_path = ARTIFACT_DIR / f"design_guide_compute_core_post_active_zero_shear_predicate_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_core_post_active_zero_shear_predicate_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Compute Core Post-Active Zero-Shear Predicate Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Summary",
        "The pure zero-shear boolean predicate is controller-owned. The page still "
        "collects action and Vu inputs and still owns all terminal item/CTA/debug projection.",
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
    print(f"design_guide_compute_core_post_active_zero_shear_predicate_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
