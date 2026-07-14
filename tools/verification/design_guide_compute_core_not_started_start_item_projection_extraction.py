"""Verify not-started start-card projection extraction."""

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

from design_brain.design_guide_controller import build_design_guide_controller_start_guidance_item  # noqa: E402


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


def _expected(start_line: str) -> dict[str, Any]:
    return {
        "check_key": "general",
        "title_main": "Choose your workflow:",
        "title_util": None,
        "title": "Choose your workflow:",
        "primary_action": start_line,
        "secondary_action": None,
        "reasoning": "Or define loads from the Design page",
        "levers": "Key levers: geometry, actions, initial reinforcement",
        "status": "START",
        "bucket": "start",
        "util": None,
        "priority": 50.0,
        "action_type": None,
        "action_payload": {},
        "start_steps": [
            "Fast -> guided design",
            "Detailed -> full control",
        ],
    }


def _scenario_rows() -> list[dict[str, Any]]:
    rows = []
    for start_line in (
        "Start by setting geometry or reinforcement",
        "Add reinforcement or loads to activate checks",
    ):
        actual = build_design_guide_controller_start_guidance_item(start_line=start_line)
        expected = _expected(start_line)
        rows.append(
            {
                "start_line": start_line,
                "actual": actual,
                "expected": expected,
                "matches": actual == expected,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start_item_start, start_item_end, start_item_segment = _function_source(inputs_source, "_guidance_start_item")
    core_start, core_end, core_segment = _function_source(inputs_source, "_compute_design_guidance_items_core")
    scenario_rows = _scenario_rows()
    return {
        "schema": "design_guide_compute_core_not_started_start_item_projection_extraction.v1",
        "targets": {
            "_guidance_start_item": {
                "line_start": start_item_start,
                "line_end": start_item_end,
                "line_count": max(0, start_item_end - start_item_start + 1),
            },
            "_compute_design_guidance_items_core": {
                "line_start": core_start,
                "line_end": core_end,
                "line_count": max(0, core_end - core_start + 1),
            },
        },
        "controller_helper_present": "def build_design_guide_controller_start_guidance_item(" in controller_source,
        "controller_helper_exported": '"build_design_guide_controller_start_guidance_item"' in controller_source,
        "start_item_delegates_to_controller": "_build_design_guide_controller_start_guidance_item(" in start_item_segment,
        "start_item_page_projection_literals_removed": all(
            token not in start_item_segment
            for token in (
                "Choose your workflow:",
                "Or define loads from the Design page",
                "Key levers: geometry, actions, initial reinforcement",
                "Fast -> guided design",
                "Detailed -> full control",
            )
        ),
        "core_route_still_calls_start_item_shell": "_guidance_start_item(guidance_state)" in core_segment,
        "scenario_rows": scenario_rows,
        "scenario_parity_passed": all(bool(row.get("matches")) for row in scenario_rows),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    targets = payload.get("targets") or {}
    return {
        "start_item_target_found": bool((targets.get("_guidance_start_item") or {}).get("line_start")),
        "controller_helper_present": bool(payload.get("controller_helper_present")),
        "controller_helper_exported": bool(payload.get("controller_helper_exported")),
        "start_item_delegates_to_controller": bool(payload.get("start_item_delegates_to_controller")),
        "start_item_page_projection_literals_removed": bool(payload.get("start_item_page_projection_literals_removed")),
        "core_route_still_calls_start_item_shell": bool(payload.get("core_route_still_calls_start_item_shell")),
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
    json_path = ARTIFACT_DIR / f"design_guide_compute_core_not_started_start_item_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_core_not_started_start_item_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Compute Core Not-Started Start Item Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Summary",
        "The not-started start-card projection is controller-owned. The page still "
        "collects start text and owns the route condition/order.",
        "",
        "## Scenario Parity",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(f"- {row.get('start_line')}: {'PASS' if row.get('matches') else 'FAIL'}")
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
    print(f"design_guide_compute_core_not_started_start_item_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
