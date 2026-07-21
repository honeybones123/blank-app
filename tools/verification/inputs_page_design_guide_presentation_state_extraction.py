"""Verify Design Guide presentation-state extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "presentation_state.py"
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

    bridge_node = _function_node(bridge_source, "_build_design_guide_presentation_state")
    module_node = _function_node(module_source, "_build_design_guide_presentation_state")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 45,
        "bridge_binds_dependencies": "_bind_presentation_state_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_build_design_guide_presentation_state_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 150,
        "module_has_dependency_binder": "def bind_presentation_state_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_presentation_contract_surface": (
            "Design Guide presentation contract" in module_source
            and "_design_guide_engine_decision" in module_source
            and "resolve_design_guide_decision" in module_source
            and "target_band_payload" in module_source
            and "passive_underband_no_action" in module_source
            and "candidate_search_evidence" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import presentation_state as extracted

    original = bridge._build_design_guide_presentation_state_extracted
    call_record: dict = {}

    def _fake_extracted(
        *,
        primary_item: dict | None,
        overview: dict | None,
        efficiency_state: dict | None,
        disp_state: dict,
        mode_config: dict | None,
        recommendation_result: dict | None = None,
        pending_recommendation: dict | None = None,
    ) -> dict:
        call_record.update(
            {
                "primary_item": dict(primary_item or {}),
                "overview": dict(overview or {}),
                "efficiency_state": dict(efficiency_state or {}),
                "disp_state": dict(disp_state),
                "mode_config": dict(mode_config or {}),
                "recommendation_result": dict(recommendation_result or {}),
                "pending_recommendation": dict(pending_recommendation or {}),
                "bound_streamlit": getattr(extracted, "st", None) is bridge.st,
                "bound_engine": (
                    getattr(extracted, "resolve_design_guide_decision", None)
                    is bridge.resolve_design_guide_decision
                ),
                "bound_truth": (
                    getattr(extracted, "_design_guide_display_truth_for_item", None)
                    is bridge._design_guide_display_truth_for_item
                ),
            }
        )
        return {"bucket": "fake"}

    try:
        bridge._build_design_guide_presentation_state_extracted = _fake_extracted
        returned = bridge._build_design_guide_presentation_state(
            primary_item={"title_main": "Primary"},
            overview={"worst_util": 0.9},
            efficiency_state={"classification": "optimal"},
            disp_state={"D": 600},
            mode_config={"target_lo": 0.85},
            recommendation_result={"updates": {"D": 650}},
            pending_recommendation={"_source": "auto_design"},
        )
    finally:
        bridge._build_design_guide_presentation_state_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "resolve_design_guide_decision", None)
        is bridge.resolve_design_guide_decision
        and getattr(extracted, "target_band_payload", None) is bridge.target_band_payload
        and getattr(extracted, "_one_click_feedback_cta_state", None)
        is bridge._one_click_feedback_cta_state
        and getattr(extracted, "_recommendation_updates_for_envelope", None)
        is bridge._recommendation_updates_for_envelope
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"bucket": "fake"}
        and call_record.get("primary_item") == {"title_main": "Primary"}
        and call_record.get("overview") == {"worst_util": 0.9}
        and call_record.get("efficiency_state") == {"classification": "optimal"}
        and call_record.get("disp_state") == {"D": 600}
        and call_record.get("mode_config") == {"target_lo": 0.85}
        and call_record.get("recommendation_result") == {"updates": {"D": 650}}
        and call_record.get("pending_recommendation") == {"_source": "auto_design"}
        and call_record.get("bound_streamlit") is True
        and call_record.get("bound_engine") is True
        and call_record.get("bound_truth") is True
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
    json_path = ARTIFACTS / f"inputs_page_design_guide_presentation_state_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_design_guide_presentation_state_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Presentation State Extraction",
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
