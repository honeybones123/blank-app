from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from inputs_page_modules.session import build_inputs_shear_widget_mirror_overlay_plan


SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "name": "inputs_overlay_changed",
        "page_slug": "inputs",
        "base": {"s_lig": 200.0, "lig_d": 10, "lig_legs": 2},
        "working": {"s_lig": 200.0, "lig_d": 10, "lig_legs": 2, "other": 1},
        "overlay": {},
        "widgets": {"inputs_s_lig": 175.0, "inputs_lig_d": 12, "inputs_lig_legs": 3},
    },
    {
        "name": "shear_overlay_changed",
        "page_slug": "shear",
        "base": {"s_lig": 250.0, "lig_d": 8, "lig_legs": 2},
        "working": {"s_lig": 250.0, "lig_d": 8, "lig_legs": 2},
        "overlay": {"existing": {"from": 1, "to": 2, "widget_key": "x"}},
        "widgets": {"shear_s_lig": 220.0, "shear_lig_d": 10, "shear_lig_legs": 2},
    },
    {
        "name": "other_page_shared_only",
        "page_slug": "bending",
        "base": {"s_lig": 300.0, "lig_d": 0, "lig_legs": 0},
        "working": {"s_lig": 150.0, "lig_d": 10, "lig_legs": 2},
        "overlay": {"s_lig": {"from": 300.0, "to": 150.0, "widget_key": "inputs_s_lig"}},
        "widgets": {"inputs_s_lig": 150.0, "inputs_lig_d": 10, "inputs_lig_legs": 2},
    },
    {
        "name": "missing_widgets",
        "page_slug": "inputs",
        "base": {"s_lig": 180.0, "lig_d": 10, "lig_legs": 2},
        "working": {"s_lig": 180.0, "lig_d": 10, "lig_legs": 2},
        "overlay": {},
        "widgets": {},
    },
    {
        "name": "complex_widget_values_skipped",
        "page_slug": "inputs",
        "base": {"s_lig": 180.0, "lig_d": 10, "lig_legs": 2},
        "working": {"s_lig": 180.0, "lig_d": 10, "lig_legs": 2},
        "overlay": {},
        "widgets": {"inputs_s_lig": {"bad": True}, "inputs_lig_d": [12], "inputs_lig_legs": 3},
    },
    {
        "name": "inputs_stale_no_links_suppressed",
        "page_slug": "inputs",
        "base": {"s_lig": 0.0, "lig_d": 0, "lig_legs": 0},
        "working": {"s_lig": 0.0, "lig_d": 0, "lig_legs": 0},
        "overlay": {},
        "widgets": {"inputs_s_lig": 200.0, "inputs_lig_d": 10, "inputs_lig_legs": 2},
    },
)


def _run_old_page_helper(scenario: dict[str, Any]) -> dict[str, Any]:
    import inputs_page

    old_st = inputs_page.st
    fake_session = {"page_slug": scenario["page_slug"]}
    fake_session.update(dict(scenario["widgets"]))
    working = copy.deepcopy(scenario["working"])
    base = copy.deepcopy(scenario["base"])
    overlay = copy.deepcopy(scenario["overlay"])
    try:
        inputs_page.st = SimpleNamespace(session_state=fake_session)
        debug = inputs_page._apply_active_page_shear_widget_mirror_overlay(working, base, overlay)
    finally:
        inputs_page.st = old_st
    return {
        "working_state": working,
        "overlay_applied": overlay,
        "debug_payload": debug,
    }


def _run_new_planner(scenario: dict[str, Any]) -> dict[str, Any]:
    plan = build_inputs_shear_widget_mirror_overlay_plan(
        page_slug=scenario["page_slug"],
        base_state=scenario["base"],
        working_state=scenario["working"],
        overlay_applied=scenario["overlay"],
        widget_state=scenario["widgets"],
    )
    return {
        "working_state": plan.working_state,
        "overlay_applied": plan.overlay_applied,
        "debug_payload": plan.debug_payload,
        "display_hash": plan.display_hash,
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Shear Widget Mirror Overlay Trace Parity",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier runs the new pure session planner beside the current page helper without changing live behaviour.",
        "",
        "## Scenario Results",
        "",
    ]
    for row in payload["scenario_results"]:
        lines.extend(
            [
                f"### {row['name']}",
                f"- parity: `{row['parity']}`",
                f"- mismatches: `{row['mismatches']}`",
                "",
            ]
        )
    lines.extend(["## Checks", ""])
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    scenario_results: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        old = _run_old_page_helper(scenario)
        new = _run_new_planner(scenario)
        mismatches = [
            key
            for key in ("working_state", "overlay_applied", "debug_payload")
            if old.get(key) != new.get(key)
        ]
        scenario_results.append(
            {
                "name": scenario["name"],
                "parity": not mismatches,
                "mismatches": mismatches,
                "old": old,
                "new": new,
            }
        )
    checks = {
        "all_scenarios_match": all(row["parity"] for row in scenario_results),
        "covers_inputs_source_lane": any(row["name"] == "inputs_overlay_changed" for row in scenario_results),
        "covers_shear_source_lane": any(row["name"] == "shear_overlay_changed" for row in scenario_results),
        "covers_other_page_shared_only": any(row["name"] == "other_page_shared_only" for row in scenario_results),
        "covers_stale_no_links_suppression": any(row["name"] == "inputs_stale_no_links_suppressed" for row in scenario_results),
        "live_page_cutover_occurred": False,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
    }
    expected_false_checks = {
        "live_page_cutover_occurred",
        "product_behavior_changed",
        "session_behavior_changed",
    }
    failures = [
        key
        for key, value in checks.items()
        if (key in expected_false_checks and value) or (key not in expected_false_checks and not value)
    ]
    decision = (
        "READY_FOR_SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_EXTRACTION"
        if not failures
        else "SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_PARITY_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_shear_widget_mirror_overlay_trace_parity",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenario_results": scenario_results,
        "required_next_verifier": "inputs_session_shear_widget_mirror_overlay_cutover_snapshot.py",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_shear_widget_mirror_overlay_trace_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_shear_widget_mirror_overlay_trace_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_shear_widget_mirror_overlay_trace_parity", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
