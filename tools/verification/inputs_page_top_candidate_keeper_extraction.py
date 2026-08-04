"""Verify top-candidate keeper extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


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

    bridge_node = _function_node(bridge_source, "_keep_top_candidates")
    bridge_dominates_node = _function_node(bridge_source, "_candidate_dominates_for_mode")
    module_node = _function_node(module_source, "_keep_top_candidates")
    module_dominates_node = _function_node(module_source, "_candidate_dominates_for_mode")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_dominates_body = ast.get_source_segment(bridge_source, bridge_dominates_node) or ""
    dependency_section = module_source.partition("def bind_top_candidate_keeper_dependencies")[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 5,
        "bridge_binds_dependencies": "_bind_top_candidate_keeper_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_keep_top_candidates_extracted" in bridge_body,
        "bridge_dominates_wrapper_is_small": (bridge_dominates_node.end_lineno or bridge_dominates_node.lineno) - bridge_dominates_node.lineno + 1 <= 4,
        "bridge_dominates_binds_dependencies": "_bind_top_candidate_keeper_dependencies(globals())" in bridge_dominates_body,
        "bridge_dominates_delegates_to_extracted_module": "_candidate_dominates_for_mode_extracted" in bridge_dominates_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 150,
        "module_contains_dominates_body": (module_dominates_node.end_lineno or module_dominates_node.lineno) - module_dominates_node.lineno + 1 >= 65,
        "module_dependency_list_no_longer_binds_dominates": '"_candidate_dominates_for_mode"' not in dependency_section,
        "module_has_dominates_low_level_dependency": '"_candidate_util_distance"' in dependency_section,
        "module_has_dependency_binder": "def bind_top_candidate_keeper_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_candidate_ranking_contract_surface": all(
            token in module_source
            for token in (
                "reo_complexity",
                "H_SHALLOW_WIDTH_FIRST",
                "H_TRUE_SHALLOW",
                "H_SHALLOW_COMPARE",
                "H304",
                "H304_DUCTILITY",
                "discarded_dominated",
                "discarded_limit",
                "Ranked kept auto-design candidates",
            )
        ),
        "module_preserves_debug_wording": (
            "Depth selected before width in shallower_beam mode — verify ranking justification" in module_source
            and "Selected candidate is not materially shallower — verify shallower_beam ranking" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import top_candidate_keeper as extracted

    original = bridge._keep_top_candidates_extracted
    call_record: dict = {}

    def _fake_extracted(candidates: list[dict], mode_config: dict, *, limit: int) -> list[dict]:
        call_record.update(
            {
                "candidates": list(candidates),
                "mode_config": dict(mode_config),
                "limit": limit,
                "bound_streamlit": getattr(extracted, "st", None) is bridge.st,
                "bound_complexity": getattr(extracted, "compute_reo_complexity", None)
                is bridge.compute_reo_complexity,
                "bound_sort": getattr(extracted, "_candidate_sort_key_for_mode", None)
                is bridge._candidate_sort_key_for_mode,
                "bound_debug": getattr(extracted, "_agent_debug_log", None) is bridge._agent_debug_log,
                "bound_dominates": getattr(extracted, "_candidate_dominates_for_mode", None)
                is bridge._candidate_dominates_for_mode_extracted,
                "dominates_not_bridge_wrapper": getattr(extracted, "_candidate_dominates_for_mode", None)
                is not bridge._candidate_dominates_for_mode,
                "bound_util_distance": getattr(extracted, "_candidate_util_distance", None)
                is bridge._candidate_util_distance,
            }
        )
        return [{"label": "fake kept"}]

    try:
        bridge._keep_top_candidates_extracted = _fake_extracted
        returned = bridge._keep_top_candidates(
            [{"state": {"D": 600}, "is_compliant": True}],
            {"search_strategy": "balanced"},
            limit=2,
        )
    finally:
        bridge._keep_top_candidates_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "compute_reo_complexity", None) is bridge.compute_reo_complexity
        and getattr(extracted, "_candidate_sort_key_for_mode", None) is bridge._candidate_sort_key_for_mode
        and getattr(extracted, "_agent_debug_log", None) is bridge._agent_debug_log
        and getattr(extracted, "_candidate_dominates_for_mode", None)
        is bridge._candidate_dominates_for_mode_extracted
        and getattr(extracted, "_candidate_dominates_for_mode", None)
        is not bridge._candidate_dominates_for_mode
        and getattr(extracted, "_candidate_util_distance", None) is bridge._candidate_util_distance
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == [{"label": "fake kept"}]
        and call_record.get("candidates") == [{"state": {"D": 600}, "is_compliant": True}]
        and call_record.get("mode_config") == {"search_strategy": "balanced"}
        and call_record.get("limit") == 2
        and call_record.get("bound_streamlit") is True
        and call_record.get("bound_complexity") is True
        and call_record.get("bound_sort") is True
        and call_record.get("bound_debug") is True
        and call_record.get("bound_dominates") is True
        and call_record.get("dominates_not_bridge_wrapper") is True
        and call_record.get("bound_util_distance") is True
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_top_candidate_keeper_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_top_candidate_keeper_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Top Candidate Keeper Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
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
