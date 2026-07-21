"""Verify bottom-recommendation selector extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "bottom_recommendation_selector.py"
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

    bridge_node = _function_node(bridge_source, "_pick_best_bottom_recommendation_by_selector")
    module_node = _function_node(module_source, "_pick_best_bottom_recommendation_by_selector")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 14,
        "bridge_binds_dependencies": "_bind_bottom_recommendation_selector_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_pick_best_bottom_recommendation_by_selector_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 145,
        "module_has_dependency_binder": "def bind_bottom_recommendation_selector_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_selector_contract_surface": (
            "strict_band_winner_accept" in module_source
            and "strict_band_reject" in module_source
            and "selector_top_valid" in module_source
            and "final_selector_band_winner_seen" in module_source
            and "ductility_not_improved" in module_source
            and "bending_util_not_improved" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import bottom_recommendation_selector as extracted

    original = bridge._pick_best_bottom_recommendation_by_selector_extracted
    call_record: dict = {}

    def _fake_extracted(
        candidates: list[dict],
        *,
        state: dict,
        seed_candidate: dict,
        mode_config: dict,
    ) -> dict:
        call_record.update(
            {
                "candidates": list(candidates),
                "state": dict(state),
                "seed_candidate": dict(seed_candidate),
                "mode_config": dict(mode_config),
                "bound_selector": (
                    getattr(extracted, "_select_best_auto_design_candidate", None)
                    is bridge._select_best_auto_design_candidate
                ),
                "bound_trace": (
                    getattr(extracted, "_merge_design_guide_rank_trace", None)
                    is bridge._merge_design_guide_rank_trace
                ),
                "bound_strict": (
                    getattr(extracted, "_is_strictly_rejectable_band_winner", None)
                    is bridge._is_strictly_rejectable_band_winner
                ),
            }
        )
        return {"label": "fake winner"}

    try:
        bridge._pick_best_bottom_recommendation_by_selector_extracted = _fake_extracted
        returned = bridge._pick_best_bottom_recommendation_by_selector(
            [{"label": "A"}],
            state={"D": 600},
            seed_candidate={"overview": {"utils": {"bending": 0.95}}},
            mode_config={"target_util_min": 0.85},
        )
    finally:
        bridge._pick_best_bottom_recommendation_by_selector_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_select_best_auto_design_candidate", None)
        is bridge._select_best_auto_design_candidate
        and getattr(extracted, "_candidate_ductility_governs", None)
        is bridge._candidate_ductility_governs
        and getattr(extracted, "_candidate_ductility_util", None)
        is bridge._candidate_ductility_util
        and getattr(extracted, "_merge_design_guide_rank_trace", None)
        is bridge._merge_design_guide_rank_trace
        and getattr(extracted, "_updates_match_state", None) is bridge._updates_match_state
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"label": "fake winner"}
        and call_record.get("candidates") == [{"label": "A"}]
        and call_record.get("state") == {"D": 600}
        and call_record.get("seed_candidate") == {"overview": {"utils": {"bending": 0.95}}}
        and call_record.get("mode_config") == {"target_util_min": 0.85}
        and call_record.get("bound_selector") is True
        and call_record.get("bound_trace") is True
        and call_record.get("bound_strict") is True
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
    json_path = ARTIFACTS / f"inputs_page_bottom_recommendation_selector_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_bottom_recommendation_selector_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Bottom Recommendation Selector Extraction",
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
