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

from inputs_page_modules.design_guide import terminal_state


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "terminal_state.py"
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


def _parse_util_value(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _first_actionable_guidance_item(items: list[dict]) -> dict | None:
    for item in items or []:
        if isinstance(item, dict) and item.get("actionable"):
            return item
    return None


def _run_cases() -> list[dict[str, Any]]:
    terminal_state.bind_terminal_state_dependencies(
        {
            "_candidate_cache_key": lambda state: f"fp:{sorted(dict(state).items())}",
            "_design_guide_terminal_state_from_render_artifacts": (
                lambda items, debug: debug.get("existing_terminal")
            ),
            "_first_actionable_guidance_item": _first_actionable_guidance_item,
            "_parse_util_value": _parse_util_value,
        }
    )
    cases = [
        {
            "name": "explicit_terminal_artifact_preserved",
            "debug": {
                "existing_terminal": "optimal",
                "overview": {"statuses": {}, "worst_util": 0.5},
            },
            "state": {"D": 500},
            "items": [],
            "expected": "optimal",
            "expected_source": "explicit_render_artifact",
        },
        {
            "name": "actionable_in_target_primary_blocks_terminal_state",
            "debug": {
                "overview": {"statuses": {}, "worst_util": 0.86},
                "efficiency_tightening_state": {"target_band_lo": 0.82, "target_band_hi": 0.92},
            },
            "state": {"D": 500},
            "items": [
                {
                    "actionable": True,
                    "allow_in_target_primary_action": True,
                    "title_main": "Refine depth",
                }
            ],
            "expected": None,
            "expected_source": "blocked_by_in_target_primary_refinement",
        },
        {
            "name": "in_target_pass_derives_optimal",
            "debug": {
                "overview": {"statuses": {"bending": "PASS"}, "worst_util": 0.86},
                "efficiency_tightening_state": {"target_band_lo": 0.82, "target_band_hi": 0.92},
            },
            "state": {"D": 500},
            "items": [],
            "expected": "optimal",
            "expected_source": "derived_current_overview",
        },
        {
            "name": "very_low_demand_derives_low_state",
            "debug": {
                "overview": {"statuses": {}, "worst_util": 0.12},
                "efficiency_tightening_state": {"target_band_lo": 0.82, "target_band_hi": 0.92},
            },
            "state": {"D": 500},
            "items": [],
            "expected": "very_low_demand",
            "expected_source": "derived_current_overview",
        },
        {
            "name": "failing_status_suppresses_terminal_state",
            "debug": {
                "overview": {"statuses": {"shear": "FAIL"}, "worst_util": 1.12},
            },
            "state": {"D": 500},
            "items": [],
            "expected": None,
            "expected_source": "none",
        },
    ]
    results: list[dict[str, Any]] = []
    for case in cases:
        debug = dict(case["debug"])
        result = terminal_state._derive_design_guide_terminal_state_from_current_overview(
            debug,
            dict(case["state"]),
            list(case["items"]),
        )
        meta = dict(debug.get("_derived_terminal_state_meta") or {})
        passed = result == case["expected"] and meta.get("source") == case["expected_source"]
        results.append(
            {
                "name": case["name"],
                "passed": passed,
                "result": result,
                "expected": case["expected"],
                "source": meta.get("source"),
                "expected_source": case["expected_source"],
                "meta": meta,
            }
        )
    return results


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Terminal State Current Overview Extraction",
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
    module_source = _read(MODULE)
    bridge_helper = _function_source(
        bridge_source,
        "_derive_design_guide_terminal_state_from_current_overview",
    )
    module_helper = _function_source(
        module_source,
        "_derive_design_guide_terminal_state_from_current_overview",
    )
    case_results = _run_cases()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helper": (
            "_derive_design_guide_terminal_state_from_current_overview_extracted" in bridge_source
        ),
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 14,
        "bridge_binds_module_dependencies": "_bind_terminal_state_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": (
            "_derive_design_guide_terminal_state_from_current_overview_extracted(" in bridge_helper
        ),
        "bridge_removed_terminal_derivation_body": '"blocked_by_in_target_primary_refinement"' not in bridge_helper
        and '"derived_current_overview"' not in bridge_helper,
        "module_keeps_terminal_derivation_body": '"blocked_by_in_target_primary_refinement"' in module_helper
        and '"derived_current_overview"' in module_helper,
        "all_cases_pass": all(row["passed"] for row in case_results),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in case_results if not row["passed"])
    decision = "INPUTS_PAGE_TERMINAL_STATE_CURRENT_OVERVIEW_EXTRACTION_LOCKED" if not failures else "GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_terminal_state_current_overview_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "case_results": case_results,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_terminal_state_current_overview_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_state_current_overview_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_terminal_state_current_overview_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
