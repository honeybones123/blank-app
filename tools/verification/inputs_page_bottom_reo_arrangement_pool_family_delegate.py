from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
FAMILY = ROOT / "design_brain" / "families" / "bending.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _scenario_rows() -> list[dict[str, Any]]:
    import inputs_page_app_contract_bridge as bridge
    from design_brain.families.bending import build_bottom_reo_arrangement_pool_from_state

    scenarios = [
        {
            "name": "balanced_rect_band0",
            "state": {
                "sec_shape": "RECT",
                "b": 400.0,
                "cover_side": 40.0,
                "rowgap_bot": 60.0,
                "bot1_count": 5,
                "bot2_count": 0,
                "db_bot_1": 16,
            },
            "mode_config": {"search_strategy": "balanced"},
            "band": 0,
            "context": {},
            "limit": None,
        },
        {
            "name": "shallow_t_band1_limited",
            "state": {
                "sec_shape": "T",
                "b": 600.0,
                "bw": 320.0,
                "cover_side": 35.0,
                "rowgap_bot": 55.0,
                "bot1_count": 4,
                "bot2_count": 2,
                "db_bot_1": 20,
            },
            "mode_config": {"search_strategy": "shallow"},
            "band": 1,
            "context": {},
            "limit": 7,
        },
        {
            "name": "ductility_priority_i_low_reo",
            "state": {
                "sec_shape": "I",
                "b": 500.0,
                "tw": 280.0,
                "cover_side": 45.0,
                "rowgap_bot": 65.0,
                "bot1_count": 7,
                "bot2_count": 3,
                "db_bot_1": 24,
            },
            "mode_config": {"search_strategy": "low_reo"},
            "band": 1,
            "context": {"ductility_priority": True},
            "limit": 9,
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        bridge_context = dict(scenario["context"])
        family_context = dict(scenario["context"])
        actual = bridge._generate_local_bottom_arrangements(
            dict(scenario["state"]),
            dict(scenario["mode_config"]),
            band=int(scenario["band"]),
            context=bridge_context,
            limit=scenario["limit"],
        )
        expected = build_bottom_reo_arrangement_pool_from_state(
            dict(scenario["state"]),
            dict(scenario["mode_config"]),
            band=int(scenario["band"]),
            context=family_context,
            limit=scenario["limit"],
            bar_diameters=tuple(bridge.REO_BAR_DIAS),
            default_limit=bridge.AUTO_DESIGN_MAX_STAGE_CANDIDATES,
        )
        rows.append(
            {
                "name": scenario["name"],
                "matches_family": actual == expected,
                "actual_count": len(actual),
                "expected_count": len(expected),
                "actual": actual,
                "expected": expected,
                "bridge_context_has_layout_cache": isinstance(bridge_context.get("layout_fit_cache"), dict),
                "family_context_has_layout_cache": isinstance(family_context.get("layout_fit_cache"), dict),
            }
        )
    return rows


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Bottom Reo Arrangement Pool Family Delegate",
        "",
        f"## Decision: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    bridge_source = _read(BRIDGE)
    family_source = _read(FAMILY)
    bridge_helper = _function_source(bridge_source, "_generate_local_bottom_arrangements")
    family_helper = _function_source(family_source, "build_bottom_reo_arrangement_pool_from_state")
    family_pool = _function_source(family_source, "build_bottom_reo_arrangement_pool")
    scenarios = _scenario_rows()
    checks = {
        "family_from_state_helper_exists": bool(family_helper),
        "family_pool_helper_exists": bool(family_pool),
        "bridge_imports_family_helper": "_build_bottom_reo_arrangement_pool_from_state" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 12,
        "bridge_delegates_to_family_from_state": "_build_bottom_reo_arrangement_pool_from_state(" in bridge_helper,
        "bridge_passes_bar_diameters_and_default_limit": "bar_diameters=tuple(REO_BAR_DIAS)" in bridge_helper
        and "default_limit=AUTO_DESIGN_MAX_STAGE_CANDIDATES" in bridge_helper,
        "bridge_no_longer_owns_arrangement_generation": all(
            token not in bridge_helper
            for token in (
                "_option_window(",
                "_normalise_bottom_layer_order(",
                "_arrangement_fits_state(",
                "count_1_values",
                "count_2_values",
                "dia_values",
                "_arrangement_rank",
            )
        ),
        "family_helper_has_no_ui_or_session": all(
            token not in family_helper
            for token in ("streamlit", "st.session_state", "inputs_page", "button_contract")
        ),
        "all_scenarios_match_family": all(row["matches_family"] for row in scenarios),
        "layout_cache_context_preserved": all(
            row["bridge_context_has_layout_cache"] and row["family_context_has_layout_cache"]
            for row in scenarios
        ),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"scenario:{row['name']}" for row in scenarios if not row["matches_family"])
    decision = (
        "INPUTS_PAGE_BOTTOM_REO_ARRANGEMENT_POOL_FAMILY_DELEGATE_LOCKED"
        if not failures
        else "GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_page_bottom_reo_arrangement_pool_family_delegate",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenario_rows": scenarios,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_bottom_reo_arrangement_pool_family_delegate_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_bottom_reo_arrangement_pool_family_delegate_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_bottom_reo_arrangement_pool_family_delegate", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
