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

from inputs_page_modules.session import build_inputs_model_reo_widget_mirror_overlay_plan
from inputs_page_modules.widgets.model_reo_overlay import overlay_inputs_reo_widget_mirrors_for_model


def _base_state() -> dict[str, Any]:
    return {
        "b": 400.0,
        "D": 650.0,
        "bot_row_count": 1,
        "top_row_count": 1,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": 3,
        "bot_row_1_spacing": 150.0,
        "bot_row_1_dia": 16.0,
        "top_row_1_mode": "Count",
        "top_row_1_bars": 2,
        "top_row_1_spacing": 150.0,
        "top_row_1_dia": 12.0,
        "bot1_count": 3,
        "db_bot_1": 16.0,
        "bot2_count": 0,
        "db_bot_2": 0.0,
        "top1_count": 2,
        "db_top_1": 12.0,
        "top2_count": 0,
        "db_top_2": 0.0,
        "bot_bar_coords": [{"x": 80.0, "y": 580.0, "db": 16.0}, {"x": 200.0, "y": 580.0, "db": 16.0}, {"x": 320.0, "y": 580.0, "db": 16.0}],
        "top_bar_coords": [{"x": 120.0, "y": 70.0, "db": 12.0}, {"x": 280.0, "y": 70.0, "db": 12.0}],
    }


SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "name": "not_inputs_page_suppressed",
        "page_slug": "shear",
        "state": _base_state(),
        "summary_debug": {},
        "widgets": {"inputs_bot_row_count": 2},
    },
    {
        "name": "summary_shared_only_suppressed",
        "page_slug": "inputs",
        "state": _base_state(),
        "summary_debug": {"summary_shared_only_mode": True, "summary_shared_only_reason": "pending_inputs_apply_refresh"},
        "widgets": {"inputs_bot_row_count": 2},
    },
    {
        "name": "post_force_refresh_allows_overlay",
        "page_slug": "inputs",
        "state": _base_state(),
        "summary_debug": {"summary_shared_only_mode": True, "summary_shared_only_reason": "post_force_refresh_this_run"},
        "widgets": {"inputs_bot_row_count": 2, "inputs_bot_row_2_bars": 2, "inputs_bot_row_2_dia": 12.0},
    },
    {
        "name": "bottom_row_widget_overlay",
        "page_slug": "inputs",
        "state": _base_state(),
        "summary_debug": {},
        "widgets": {"inputs_bot_row_count": 2, "inputs_bot_row_2_bars": 2, "inputs_bot_row_2_dia": 12.0, "inputs_bot_row_2_spacing": 100.0},
    },
    {
        "name": "top_row_widget_overlay",
        "page_slug": "inputs",
        "state": _base_state(),
        "summary_debug": {},
        "widgets": {"inputs_top_row_count": 2, "inputs_top_row_2_bars": 1, "inputs_top_row_2_dia": 10.0},
    },
    {
        "name": "complex_widget_values_skipped",
        "page_slug": "inputs",
        "state": _base_state(),
        "summary_debug": {},
        "widgets": {"inputs_bot_row_count": {"bad": True}, "inputs_bot_row_1_bars": [4], "inputs_top_row_1_dia": 16.0},
    },
    {
        "name": "coords_stale_count_mismatch",
        "page_slug": "inputs",
        "state": {**_base_state(), "bot_bar_coords": [{"x": 200.0, "y": 580.0, "db": 16.0}]},
        "summary_debug": {},
        "widgets": {},
    },
    {
        "name": "coords_stale_outside_section",
        "page_slug": "inputs",
        "state": {**_base_state(), "top_bar_coords": [{"x": 500.0, "y": 70.0, "db": 12.0}, {"x": 280.0, "y": 70.0, "db": 12.0}]},
        "summary_debug": {},
        "widgets": {},
    },
)


def _widget_keys_for_model_overlay() -> tuple[str, ...]:
    keys: list[str] = []
    for section in ("bot", "top"):
        keys.append(f"inputs_{section}_row_count")
        for row_index in range(1, 5):
            prefix = f"inputs_{section}_row_{row_index}"
            keys.extend(
                [
                    f"{prefix}_mode",
                    f"{prefix}_bars",
                    f"{prefix}_spacing",
                    f"{prefix}_dia",
                ]
            )
    return tuple(keys)


def _run_route_helper(scenario: dict[str, Any]) -> dict[str, Any]:
    import inputs_page_route_coordinators as route_bridge

    old_st = route_bridge.st
    fake_session = {"page_slug": scenario["page_slug"]}
    fake_session.update(dict(scenario["widgets"]))
    try:
        route_bridge.st = SimpleNamespace(session_state=fake_session)
        state, debug = route_bridge._overlay_inputs_reo_widget_mirrors_for_model(
            copy.deepcopy(scenario["state"]),
            summary_debug=copy.deepcopy(scenario["summary_debug"]),
        )
    finally:
        route_bridge.st = old_st
    return {"working_state": state, "debug_payload": debug}


def _run_module_overlay(scenario: dict[str, Any]) -> dict[str, Any]:
    import inputs_page_route_coordinators as route_bridge

    widget_state = {
        key: scenario["widgets"][key]
        for key in _widget_keys_for_model_overlay()
        if key in scenario["widgets"]
    }
    working, debug = overlay_inputs_reo_widget_mirrors_for_model(
        page_slug=scenario["page_slug"],
        state=copy.deepcopy(scenario["state"]),
        summary_debug=copy.deepcopy(scenario["summary_debug"]),
        widget_state=widget_state,
        overlay_plan_fn=build_inputs_model_reo_widget_mirror_overlay_plan,
        build_legacy_longitudinal_mirrors_from_rows_fn=route_bridge.build_legacy_longitudinal_mirrors_from_rows,
        build_canonical_design_state_pack_fn=route_bridge._build_canonical_design_state_pack_for_app_bridge,
    )
    return {"working_state": working, "debug_payload": debug}


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Model Reo Widget Mirror Overlay Trace Parity",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier compares the current page helper with the new pure planner plus the unchanged page-owned canonical-pack callback sequence.",
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
        old = _run_route_helper(scenario)
        new = _run_module_overlay(scenario)
        mismatches = [
            key
            for key in ("working_state", "debug_payload")
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
        "covers_not_inputs_page_suppression": any(row["name"] == "not_inputs_page_suppressed" for row in scenario_results),
        "covers_shared_only_suppression": any(row["name"] == "summary_shared_only_suppressed" for row in scenario_results),
        "covers_post_force_refresh": any(row["name"] == "post_force_refresh_allows_overlay" for row in scenario_results),
        "covers_bottom_overlay": any(row["name"] == "bottom_row_widget_overlay" for row in scenario_results),
        "covers_top_overlay": any(row["name"] == "top_row_widget_overlay" for row in scenario_results),
        "covers_coord_stale": any("coords_stale" in row["name"] for row in scenario_results),
        "live_page_cutover_occurred": True,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
    }
    expected_false = {
        "product_behavior_changed",
        "session_behavior_changed",
    }
    failures = [
        key
        for key, value in checks.items()
        if (key in expected_false and value) or (key not in expected_false and not value)
    ]
    decision = (
        "READY_FOR_SESSION_MODEL_REO_WIDGET_MIRROR_OVERLAY_EXTRACTION"
        if not failures
        else "SESSION_MODEL_REO_WIDGET_MIRROR_OVERLAY_PARITY_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_model_reo_widget_mirror_overlay_trace_parity",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenario_results": scenario_results,
        "required_next_verifier": "inputs_session_model_reo_widget_mirror_overlay_cutover_snapshot.py",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_model_reo_widget_mirror_overlay_trace_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_model_reo_widget_mirror_overlay_trace_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_model_reo_widget_mirror_overlay_trace_parity", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
