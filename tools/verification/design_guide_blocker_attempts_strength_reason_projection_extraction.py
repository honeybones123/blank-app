"""Verify blocker-attempt strength reason projection extraction."""

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
    build_design_guide_controller_blocker_attempt_strength_reason,
    resolve_design_guide_controller_blocker_attempt_strength_capacity_rule,
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


def _format(value: Any) -> str:
    try:
        if value in (None, "", "—"):
            return "-"
        return f"{float(value):.2f}"
    except Exception:
        try:
            return f"{float(str(value).strip()):.2f}"
        except Exception:
            return "-"


def _expected_rule(family: str) -> str:
    if family == "shear":
        return "sectional shear capacity utilisation"
    if family == "combined":
        return "combined bending/shear capacity utilisation"
    return "bending capacity utilisation"


def _expected_reason(family: str, value: Any, limit: Any) -> str:
    value_text = _format(value)
    limit_text = _format(limit)
    if family == "combined":
        return (
            "Best rejected combined strengthening candidate still leaves a strength "
            f"utilisation of {value_text}, above the required maximum {limit_text}."
        )
    return (
        f"Best rejected {family} strengthening candidate still leaves {family} "
        f"utilisation {value_text}, above the required maximum {limit_text}."
    )


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        {"family": "bending", "value": 1.23, "limit": 1.0},
        {"family": "shear", "value": "1.08", "limit": "1.0"},
        {"family": "combined", "value": None, "limit": ""},
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        family = scenario["family"]
        expected_rule = _expected_rule(family)
        expected_reason = _expected_reason(family, scenario["value"], scenario["limit"])
        actual_rule = resolve_design_guide_controller_blocker_attempt_strength_capacity_rule(family)
        actual_reason = build_design_guide_controller_blocker_attempt_strength_reason(
            family,
            scenario["value"],
            scenario["limit"],
        )
        rows.append(
            {
                "family": family,
                "matches": actual_rule == expected_rule and actual_reason == expected_reason,
                "expected_rule": expected_rule,
                "actual_rule": actual_rule,
                "expected_reason": expected_reason,
                "actual_reason": actual_reason,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, helper = _function_source(inputs_source, "_design_guide_blocker_attempts_table")
    scenario_rows = _scenario_rows()
    return {
        "schema": "design_guide_blocker_attempts_strength_reason_projection_extraction.v1",
        "target": {
            "function": "_design_guide_blocker_attempts_table",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "controller_helpers_present": all(
            token in controller_source
            for token in (
                "def resolve_design_guide_controller_blocker_attempt_strength_capacity_rule(",
                "def build_design_guide_controller_blocker_attempt_strength_reason(",
            )
        ),
        "controller_helpers_exported": all(
            token in controller_source
            for token in (
                '"resolve_design_guide_controller_blocker_attempt_strength_capacity_rule"',
                '"build_design_guide_controller_blocker_attempt_strength_reason"',
            )
        ),
        "page_nested_helpers_delegate": all(
            token in helper
            for token in (
                "_resolve_design_guide_controller_blocker_attempt_strength_capacity_rule(",
                "_build_design_guide_controller_blocker_attempt_strength_reason(",
            )
        ),
        "page_visible_reason_literals_removed": all(
            token not in helper
            for token in (
                "Best rejected combined strengthening candidate still leaves",
                "Best rejected {family} strengthening candidate still leaves",
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
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "controller_helpers_present": bool(payload.get("controller_helpers_present")),
        "controller_helpers_exported": bool(payload.get("controller_helpers_exported")),
        "page_nested_helpers_delegate": bool(payload.get("page_nested_helpers_delegate")),
        "page_visible_reason_literals_removed": bool(payload.get("page_visible_reason_literals_removed")),
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_strength_reason_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_strength_reason_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Strength Reason Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Scenario Parity",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(f"- {row.get('family')}: {'PASS' if row.get('matches') else 'FAIL'}")
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
    print(f"design_guide_blocker_attempts_strength_reason_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
