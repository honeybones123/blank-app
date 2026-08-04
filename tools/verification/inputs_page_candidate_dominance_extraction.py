"""Verify candidate dominance extraction for top-candidate trimming."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "top_candidate_keeper.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "_candidate_dominates_for_mode")
    module_node = _function_node(module_source, "_candidate_dominates_for_mode")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    dependency_section = module_source.partition("def bind_top_candidate_keeper_dependencies")[0]

    from inputs_page_modules.app_bridge import top_candidate_keeper as extracted

    extracted.bind_top_candidate_keeper_dependencies(
        {
            "_candidate_util_distance": lambda candidate, mode_config: float(candidate.get("util_gap", 0.0) or 0.0),
            "_shallower_beam_metrics": lambda candidate, baseline: dict(candidate.get("shallow_metrics") or {}),
            "compute_reo_complexity": lambda candidate: float(candidate.get("computed_complexity", 0.0) or 0.0),
        }
    )

    better = {
        "is_compliant": True,
        "util_gap": 0.02,
        "reo_complexity": 2.0,
        "depth": 500.0,
        "row_count": 2,
        "bar_count": 4,
        "shallow_metrics": {
            "materially_shallower": True,
            "width_growth": 10.0,
            "reinforcement_growth": 20.0,
        },
    }
    worse = {
        "is_compliant": True,
        "util_gap": 0.04,
        "reo_complexity": 3.0,
        "depth": 550.0,
        "row_count": 3,
        "bar_count": 6,
        "shallow_metrics": {
            "materially_shallower": False,
            "width_growth": 30.0,
            "reinforcement_growth": 40.0,
        },
    }
    equal = dict(better)
    non_compliant = {**better, "is_compliant": False}

    scenarios = {
        "balanced_better_dominates": extracted._candidate_dominates_for_mode(
            better,
            worse,
            {"search_strategy": "balanced"},
        ),
        "balanced_equal_does_not_dominate": extracted._candidate_dominates_for_mode(
            better,
            equal,
            {"search_strategy": "balanced"},
        ),
        "non_compliant_does_not_dominate": extracted._candidate_dominates_for_mode(
            better,
            non_compliant,
            {"search_strategy": "balanced"},
        ),
        "low_reo_better_dominates": extracted._candidate_dominates_for_mode(
            better,
            worse,
            {"search_strategy": "low_reo"},
        ),
        "shallow_better_dominates": extracted._candidate_dominates_for_mode(
            better,
            worse,
            {"search_strategy": "shallow"},
        ),
    }

    import inputs_page_app_contract_bridge as bridge

    original = bridge._candidate_dominates_for_mode_extracted
    delegate_call: dict[str, Any] = {}

    def _fake_extracted(candidate_a: dict, candidate_b: dict, mode_config: dict) -> bool:
        delegate_call.update(
            {
                "candidate_a": dict(candidate_a),
                "candidate_b": dict(candidate_b),
                "mode_config": dict(mode_config),
                "module_owner": extracted._candidate_dominates_for_mode is original,
            }
        )
        return True

    try:
        bridge._candidate_dominates_for_mode_extracted = _fake_extracted
        wrapped = bridge._candidate_dominates_for_mode(
            {"label": "a"},
            {"label": "b"},
            {"search_strategy": "balanced"},
        )
    finally:
        bridge._candidate_dominates_for_mode_extracted = original

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 4,
        "bridge_binds_dependencies": "_bind_top_candidate_keeper_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_candidate_dominates_for_mode_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 65,
        "module_dependency_list_no_longer_binds_dominates": '"_candidate_dominates_for_mode"' not in dependency_section,
        "module_has_util_distance_dependency": '"_candidate_util_distance"' in dependency_section,
        "balanced_better_dominates": scenarios["balanced_better_dominates"] is True,
        "balanced_equal_does_not_dominate": scenarios["balanced_equal_does_not_dominate"] is False,
        "non_compliant_does_not_dominate": scenarios["non_compliant_does_not_dominate"] is False,
        "low_reo_better_dominates": scenarios["low_reo_better_dominates"] is True,
        "shallow_better_dominates": scenarios["shallow_better_dominates"] is True,
        "bridge_runtime_delegates": wrapped is True
        and delegate_call.get("candidate_a") == {"label": "a"}
        and delegate_call.get("candidate_b") == {"label": "b"}
        and delegate_call.get("mode_config") == {"search_strategy": "balanced"},
        "bridge_runtime_preserves_module_owner": delegate_call.get("module_owner") is True,
    }

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "scenarios": scenarios,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_candidate_dominance_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_candidate_dominance_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Candidate Dominance Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {check}: {'PASS' if passed else 'FAIL'}" for check, passed in checks.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(result["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
