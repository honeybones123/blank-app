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

from inputs_page_modules.design_guide import efficiency_tightening_state


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "efficiency_tightening_state.py"
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


def _bind_helpers(*, active_shear: bool = True, shear_growth: bool = False) -> None:
    efficiency_tightening_state.bind_efficiency_tightening_state_dependencies(
        {
            "_shear_reinforcement_is_active": lambda state: active_shear,
            "_shear_change_is_reinforcement_growth": lambda old, new: shear_growth,
            "_resolve_geometry_width_context": lambda state: ("b", "width", float(state.get("b", 0.0) or 0.0)),
            "_float_from_state": lambda state, key, default=0.0: float(state.get(key, default) or default),
        }
    )


def _case_results() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    _bind_helpers(active_shear=False)
    ex = efficiency_tightening_state._build_efficiency_exhaustion_map(
        state={"D": 500, "b": 300},
        overview={},
        conservative=False,
        bottom_tighten=None,
        shear_tighten=None,
        geometry_tighten=None,
        shear_cleanup_possible=False,
        shear_overdesign_cleanup_eligible=False,
        bending_inefficient=False,
        shear_inefficient=False,
    )
    cases.append(
        {
            "name": "inactive_shear_is_resolved",
            "passed": ex["shear_cleanup"]["accepted"] is True
            and ex["depth_reduction"]["rejected_reason"] == "efficiency_branch_inactive",
            "ex": ex,
        }
    )

    _bind_helpers(active_shear=True, shear_growth=True)
    ex = efficiency_tightening_state._build_efficiency_exhaustion_map(
        state={"D": 500, "b": 300},
        overview={},
        conservative=True,
        bottom_tighten={"updates": {"bottom_bar_dia": 16}},
        shear_tighten={"updates": {"s_lig": 150}, "candidate_type": "shear_spacing"},
        geometry_tighten={"updates": {"D": 475, "b": 275}},
        shear_cleanup_possible=True,
        shear_overdesign_cleanup_eligible=True,
        bending_inefficient=True,
        shear_inefficient=True,
    )
    cases.append(
        {
            "name": "growth_shear_rejected_but_bottom_and_geometry_accepted",
            "passed": ex["shear_cleanup"]["rejected_reason"] == "shear_tightening_was_growth_not_reduction"
            and ex["bottom_reo_reduction"]["accepted"] is True
            and ex["depth_reduction"]["accepted"] is True
            and ex["width_reduction"]["accepted"] is True,
            "ex": ex,
        }
    )

    _bind_helpers(active_shear=True, shear_growth=False)
    ex = efficiency_tightening_state._build_efficiency_exhaustion_map(
        state={"D": 500, "b": 300},
        overview={},
        conservative=True,
        bottom_tighten=None,
        shear_tighten={"updates": {"s_lig": 250}, "candidate_type": "shear_spacing"},
        geometry_tighten={"updates": {"D": 500, "b": 300}},
        shear_cleanup_possible=True,
        shear_overdesign_cleanup_eligible=True,
        bending_inefficient=True,
        shear_inefficient=True,
    )
    cases.append(
        {
            "name": "safe_shear_reduction_and_no_geometry_delta",
            "passed": ex["shear_cleanup"]["accepted"] is True
            and ex["bottom_reo_reduction"]["rejected_reason"] == "no_safe_bottom_reduction_candidate"
            and ex["depth_reduction"]["rejected_reason"] == "no_depth_reduction_in_selected_geometry_trial"
            and ex["width_reduction"]["rejected_reason"] == "no_width_reduction_in_selected_geometry_trial",
            "ex": ex,
        }
    )

    _bind_helpers(active_shear=True)
    ex = efficiency_tightening_state._build_efficiency_exhaustion_map(
        state={"D": 500, "b": 300},
        overview={},
        conservative=True,
        bottom_tighten=None,
        shear_tighten=None,
        geometry_tighten=None,
        shear_cleanup_possible=True,
        shear_overdesign_cleanup_eligible=False,
        bending_inefficient=False,
        shear_inefficient=False,
    )
    cases.append(
        {
            "name": "truth_blocks_shear_cleanup",
            "passed": ex["shear_cleanup"]["rejected_reason"] == "shear_overdesign_cleanup_blocked_governing_truth"
            and ex["bottom_reo_reduction"]["rejected_reason"] == "bending_not_inefficient_vs_guidance_threshold"
            and ex["depth_reduction"]["rejected_reason"] == "geometry_tightening_unavailable",
            "ex": ex,
        }
    )
    return cases


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Efficiency Exhaustion Map Extraction",
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
    bridge_helper = _function_source(bridge_source, "_build_efficiency_exhaustion_map")
    module_helper = _function_source(module_source, "_build_efficiency_exhaustion_map")
    cases = _case_results()
    checks = {
        "module_exports_helper": "_build_efficiency_exhaustion_map" in module_source,
        "module_dependency_no_longer_injects_helper": '"_build_efficiency_exhaustion_map"' not in module_source.split(
            "def bind_efficiency_tightening_state_dependencies", 1
        )[0],
        "bridge_imports_extracted_helper": "_build_efficiency_exhaustion_map_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 28,
        "bridge_binds_efficiency_dependencies": "_bind_efficiency_tightening_state_dependencies(globals())" in bridge_helper,
        "bridge_removed_exhaustion_body": "shear_tightening_was_growth_not_reduction" not in bridge_helper,
        "module_keeps_exhaustion_body": "shear_tightening_was_growth_not_reduction" in module_helper,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = "INPUTS_PAGE_EFFICIENCY_EXHAUSTION_MAP_EXTRACTION_LOCKED" if not failures else "GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_efficiency_exhaustion_map_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "case_results": cases,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_efficiency_exhaustion_map_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_efficiency_exhaustion_map_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_efficiency_exhaustion_map_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
