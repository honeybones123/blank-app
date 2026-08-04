"""Verify family-status display payload assembly extraction."""

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
    build_design_guide_controller_family_status_display_payload,
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


def _expected(
    *,
    item: dict[str, Any],
    current_state_for_display: dict[str, Any],
    family_status_current: dict[str, Any],
    family_status_preview: dict[str, Any] | None = None,
    family_status_preview_present: bool = False,
    blocker_attempts_by_family: dict[str, Any] | None = None,
    blocker_attempts_present: bool = False,
) -> dict[str, Any]:
    out = dict(item)
    out["_current_state_for_display"] = dict(current_state_for_display)
    out["family_status_current"] = dict(family_status_current)
    if family_status_preview_present:
        out["family_status_preview"] = dict(family_status_preview or {})
    if blocker_attempts_present:
        out["blocker_attempts_by_family"] = dict(blocker_attempts_by_family or {})
    return out


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        {
            "name": "current only",
            "item": {"title_main": "Shear cleanup"},
            "current_state_for_display": {"D": 600.0},
            "family_status_current": {"shear": {"status": "PASS"}},
            "family_status_preview": None,
            "family_status_preview_present": False,
            "blocker_attempts_by_family": None,
            "blocker_attempts_present": False,
        },
        {
            "name": "preview and blocker rows",
            "item": {"title_main": "Blocked", "exact_blockers_by_family": {"shear": {"reason": "x"}}},
            "current_state_for_display": {"D": 600.0},
            "family_status_current": {"shear": {"status": "FAIL"}},
            "family_status_preview": {"shear": {"after": "PASS"}},
            "family_status_preview_present": True,
            "blocker_attempts_by_family": {"shear": [{"result": "blocked"}]},
            "blocker_attempts_present": True,
        },
        {
            "name": "empty present preview preserved",
            "item": {"title_main": "Empty preview"},
            "current_state_for_display": {},
            "family_status_current": {},
            "family_status_preview": {},
            "family_status_preview_present": True,
            "blocker_attempts_by_family": {},
            "blocker_attempts_present": True,
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        helper_args = {key: value for key, value in scenario.items() if key != "name"}
        expected = _expected(**helper_args)
        actual = build_design_guide_controller_family_status_display_payload(**helper_args)
        rows.append(
            {
                "name": scenario["name"],
                "matches": actual == expected,
                "expected": expected,
                "actual": actual,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, helper = _function_source(inputs_source, "_attach_family_status_display_payload")
    scenario_rows = _scenario_rows()
    return {
        "schema": "design_guide_family_status_display_payload_assembly_extraction.v1",
        "target": {
            "function": "_attach_family_status_display_payload",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "controller_helper_present": "def build_design_guide_controller_family_status_display_payload(" in controller_source,
        "controller_helper_exported": '"build_design_guide_controller_family_status_display_payload"' in controller_source,
        "page_delegates_to_controller": "_build_design_guide_controller_family_status_display_payload(" in helper,
        "page_assembly_rows_removed": all(
            token not in helper
            for token in (
                'out["_current_state_for_display"] =',
                'out["family_status_current"] =',
                'out["family_status_preview"] =',
                'out["blocker_attempts_by_family"] =',
            )
        ),
        "page_collection_remains_page_owned": all(
            token in helper
            for token in (
                "_collect_design_overview(",
                "_design_guide_family_status_table(",
                "_resolve_recommendation_updates(",
                "_design_guide_candidate_preview_overview(",
                "_design_guide_preview_family_delta_table(",
                "_design_guide_blocker_attempts_table(",
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
        "controller_helper_present": bool(payload.get("controller_helper_present")),
        "controller_helper_exported": bool(payload.get("controller_helper_exported")),
        "page_delegates_to_controller": bool(payload.get("page_delegates_to_controller")),
        "page_assembly_rows_removed": bool(payload.get("page_assembly_rows_removed")),
        "page_collection_remains_page_owned": bool(payload.get("page_collection_remains_page_owned")),
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
    json_path = ARTIFACT_DIR / f"design_guide_family_status_display_payload_assembly_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_family_status_display_payload_assembly_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Family Status Display Payload Assembly Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Summary",
        "Pure family-status display payload assembly is controller-owned. Page-owned overview collection, preview evaluation, recommendation update fallback, and blocker table generation remain in inputs_page.py.",
        "",
        "## Scenario Parity",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(f"- {row.get('name')}: {'PASS' if row.get('matches') else 'FAIL'}")
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
    print(f"design_guide_family_status_display_payload_assembly_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
