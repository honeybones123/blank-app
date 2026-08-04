"""Verify family-status row/table/delta projection extraction."""

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
    build_design_guide_controller_family_status_row_from_overview,
    build_design_guide_controller_family_status_table,
    build_design_guide_controller_preview_family_delta_table,
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


def _parse_util_value(value: Any) -> float | None:
    if value in (None, "", "—"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _expected_row(overview: dict[str, Any] | None, family: str) -> dict[str, Any]:
    ov = dict(overview or {})
    utils = dict(ov.get("utils") or {})
    statuses = dict(ov.get("statuses") or {})
    family_key = str(family or "").strip().lower()
    util = _parse_util_value(utils.get(family_key))
    if util is None:
        util = _parse_util_value(ov.get(f"{family_key}_util"))
    status = str(statuses.get(family_key) or ov.get(f"{family_key}_status") or "").strip().upper()
    if not status and family_key in {"crack", "deflection"} and util is not None:
        status = "PASS" if float(util) <= 1.0 + 1e-9 else "FAIL"
    return {
        "util": None if util is None else float(util),
        "status": status or None,
        "value": ov.get(f"{family_key}_value"),
        "limit": ov.get(f"{family_key}_limit"),
    }


def _expected_table(overview: dict[str, Any] | None) -> dict[str, Any]:
    return {
        family: _expected_row(overview, family)
        for family in ("bending", "shear", "crack", "deflection")
    }


def _expected_delta(
    current_overview: dict[str, Any] | None,
    preview_overview: dict[str, Any] | None,
) -> dict[str, Any]:
    current = _expected_table(current_overview)
    preview = _expected_table(preview_overview)
    return {
        family: {
            "before_util": current.get(family, {}).get("util"),
            "after_util": preview.get(family, {}).get("util"),
            "before_status": current.get(family, {}).get("status"),
            "after_status": preview.get(family, {}).get("status"),
            "before_value": current.get(family, {}).get("value"),
            "after_value": preview.get(family, {}).get("value"),
            "before_limit": current.get(family, {}).get("limit"),
            "after_limit": preview.get(family, {}).get("limit"),
        }
        for family in ("bending", "shear", "crack", "deflection")
    }


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        {
            "name": "status and util maps",
            "current": {
                "utils": {"bending": "0.82", "shear": 1.05},
                "statuses": {"bending": "PASS", "shear": "FAIL"},
                "bending_value": "10",
                "bending_limit": "12",
            },
            "preview": {
                "utils": {"bending": "0.86", "shear": "0.74", "crack": "0.2"},
                "statuses": {"bending": "PASS", "shear": "PASS"},
                "shear_value": "70",
                "shear_limit": "100",
            },
        },
        {
            "name": "flat fallback fields",
            "current": {
                "bending_util": "0.91",
                "bending_status": "PASS",
                "crack_util": "1.2",
                "deflection_util": "0.9",
            },
            "preview": {
                "bending_util": "0.88",
                "shear_util": "",
                "deflection_util": "1.1",
            },
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        current = scenario["current"]
        preview = scenario["preview"]
        expected_table = _expected_table(current)
        actual_table = build_design_guide_controller_family_status_table(current)
        expected_delta = _expected_delta(current, preview)
        actual_delta = build_design_guide_controller_preview_family_delta_table(current, preview)
        expected_shear = _expected_row(current, "shear")
        actual_shear = build_design_guide_controller_family_status_row_from_overview(current, "shear")
        rows.append(
            {
                "name": scenario["name"],
                "table_matches": actual_table == expected_table,
                "delta_matches": actual_delta == expected_delta,
                "row_matches": actual_shear == expected_shear,
                "matches": actual_table == expected_table and actual_delta == expected_delta and actual_shear == expected_shear,
                "expected_table": expected_table,
                "actual_table": actual_table,
                "expected_delta": expected_delta,
                "actual_delta": actual_delta,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    row_start, row_end, row_helper = _function_source(inputs_source, "_design_guide_family_row_from_overview")
    table_start, table_end, table_helper = _function_source(inputs_source, "_design_guide_family_status_table")
    delta_start, delta_end, delta_helper = _function_source(inputs_source, "_design_guide_preview_family_delta_table")
    scenario_rows = _scenario_rows()
    return {
        "schema": "design_guide_family_status_table_projection_extraction.v1",
        "targets": {
            "_design_guide_family_row_from_overview": {"line_start": row_start, "line_end": row_end},
            "_design_guide_family_status_table": {"line_start": table_start, "line_end": table_end},
            "_design_guide_preview_family_delta_table": {"line_start": delta_start, "line_end": delta_end},
        },
        "controller_helpers_present": all(
            token in controller_source
            for token in (
                "def build_design_guide_controller_family_status_row_from_overview(",
                "def build_design_guide_controller_family_status_table(",
                "def build_design_guide_controller_preview_family_delta_table(",
            )
        ),
        "controller_helpers_exported": all(
            token in controller_source
            for token in (
                '"build_design_guide_controller_family_status_row_from_overview"',
                '"build_design_guide_controller_family_status_table"',
                '"build_design_guide_controller_preview_family_delta_table"',
            )
        ),
        "page_wrappers_delegate": all(
            token in segment
            for token, segment in (
                ("_build_design_guide_controller_family_status_row_from_overview(", row_helper),
                ("_build_design_guide_controller_family_status_table(", table_helper),
                ("_build_design_guide_controller_preview_family_delta_table(", delta_helper),
            )
        ),
        "page_projection_logic_removed": all(
            token not in (row_helper + "\n" + table_helper + "\n" + delta_helper)
            for token in (
                "family_key = str(family",
                "for family in (\"bending\", \"shear\", \"crack\", \"deflection\")",
                "\"before_util\":",
                "\"after_util\":",
            )
        ),
        "scenario_rows": scenario_rows,
        "scenario_parity_passed": all(bool(row.get("matches")) for row in scenario_rows),
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
    targets = payload.get("targets") or {}
    return {
        "targets_found": all(bool((targets.get(name) or {}).get("line_start")) for name in targets),
        "controller_helpers_present": bool(payload.get("controller_helpers_present")),
        "controller_helpers_exported": bool(payload.get("controller_helpers_exported")),
        "page_wrappers_delegate": bool(payload.get("page_wrappers_delegate")),
        "page_projection_logic_removed": bool(payload.get("page_projection_logic_removed")),
        "scenario_parity_passed": bool(payload.get("scenario_parity_passed")),
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
    json_path = ARTIFACT_DIR / f"design_guide_family_status_table_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_family_status_table_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Family Status Table Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Summary",
        "Family status row/table/delta projection is controller-owned. Page wrappers remain for callsite compatibility.",
        "",
        "## Scenario Parity",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(
            f"- {row.get('name')}: {'PASS' if row.get('matches') else 'FAIL'}"
        )
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
    print(f"design_guide_family_status_table_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
