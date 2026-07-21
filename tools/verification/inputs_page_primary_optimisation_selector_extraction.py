"""Verify primary optimisation selector extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "primary_optimisation_selector.py"
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

    bridge_node = _function_node(bridge_source, "_select_primary_optimisation_candidate")
    module_node = _function_node(module_source, "_select_primary_optimisation_candidate")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    dependency_block = module_source.split("def bind_primary_optimisation_selector_dependencies", 1)[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 18,
        "bridge_binds_dependencies": "_bind_primary_optimisation_selector_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_select_primary_optimisation_candidate_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 190,
        "module_has_dependency_binder": "def bind_primary_optimisation_selector_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "dependency_binder_excludes_false_positive_r": '"r"' not in dependency_block,
        "module_keeps_selector_evidence_contract": (
            "candidate_search_evidence" in module_source
            and "primary_optimisation_selection_owner" in module_source
            and "direct_target_band_search" in module_source
            and "overdesign_stepwise_fallback_used" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import primary_optimisation_selector as extracted

    original = bridge._select_primary_optimisation_candidate_extracted
    call_record: dict = {}

    def _fake_extracted(
        *,
        state: dict,
        overview: dict | None,
        mode_config: dict | None,
        governing_action: str,
        candidates: list[dict],
        overdesign_stepwise_band_fallback: bool = False,
    ) -> dict:
        call_record.update(
            {
                "state": dict(state),
                "overview": dict(overview or {}),
                "mode_config": dict(mode_config or {}),
                "governing_action": governing_action,
                "candidates": list(candidates),
                "overdesign_stepwise_band_fallback": overdesign_stepwise_band_fallback,
                "bound_target_band_eps": getattr(extracted, "TARGET_BAND_EPS", None) == bridge.TARGET_BAND_EPS,
                "bound_candidate_evidence": (
                    getattr(extracted, "_build_candidate_search_evidence", None)
                    is bridge._build_candidate_search_evidence
                ),
                "bound_direct_target_band_item": (
                    getattr(extracted, "_direct_target_band_guidance_item", None)
                    is bridge._direct_target_band_guidance_item
                ),
            }
        )
        return {"selected_candidate": {"title_main": "fake"}, "selector_debug": {"ok": True}}

    try:
        bridge._select_primary_optimisation_candidate_extracted = _fake_extracted
        returned = bridge._select_primary_optimisation_candidate(
            state={"D": 600},
            overview={"all_key_pass": True},
            mode_config={"goal": "balanced"},
            governing_action="bending",
            candidates=[{"title_main": "Candidate"}],
            overdesign_stepwise_band_fallback=True,
        )
    finally:
        bridge._select_primary_optimisation_candidate_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "TARGET_BAND_EPS", None) == bridge.TARGET_BAND_EPS
        and getattr(extracted, "_optimisation_candidate_family", None)
        is bridge._optimisation_candidate_family
        and getattr(extracted, "_guidance_action_updates", None)
        is bridge._guidance_action_updates
        and getattr(extracted, "_build_candidate_search_evidence", None)
        is bridge._build_candidate_search_evidence
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"selected_candidate": {"title_main": "fake"}, "selector_debug": {"ok": True}}
        and call_record.get("state") == {"D": 600}
        and call_record.get("overview") == {"all_key_pass": True}
        and call_record.get("mode_config") == {"goal": "balanced"}
        and call_record.get("governing_action") == "bending"
        and call_record.get("candidates") == [{"title_main": "Candidate"}]
        and call_record.get("overdesign_stepwise_band_fallback") is True
        and call_record.get("bound_target_band_eps") is True
        and call_record.get("bound_candidate_evidence") is True
        and call_record.get("bound_direct_target_band_item") is True
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
    json_path = ARTIFACTS / f"inputs_page_primary_optimisation_selector_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_primary_optimisation_selector_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Optimisation Selector Extraction",
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
