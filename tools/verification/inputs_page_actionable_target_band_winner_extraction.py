"""Verify actionable target-band winner extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "actionable_target_band_winner.py"
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

    bridge_node = _function_node(bridge_source, "_get_actionable_target_band_winner")
    module_node = _function_node(module_source, "_get_actionable_target_band_winner")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 12,
        "bridge_binds_dependencies": "_bind_actionable_target_band_winner_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_get_actionable_target_band_winner_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 150,
        "module_has_dependency_binder": "def bind_actionable_target_band_winner_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_target_band_contract_surface": (
            "already_in_efficiency_target_band" in module_source
            and "near_upper_band_border_stop_default" in module_source
            and "target_band_default_stop" in module_source
            and "target_band_override_allowed" in module_source
            and "target_band_actionable_winner_check" in module_source
            and "apply_bottom_recommendation" in module_source
        ),
        "module_preserves_unreachable_compatibility_tail": (
            "return None\n    rec = _compute_bottom_reo_recommendation(state)" in module_source
            and "wu:.2f" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import actionable_target_band_winner as extracted

    original = bridge._get_actionable_target_band_winner_extracted
    call_record: dict = {}

    def _fake_extracted(
        state: dict,
        overview: dict,
        *,
        debug_extra: dict | None = None,
    ) -> dict | None:
        call_record.update(
            {
                "state": dict(state),
                "overview": dict(overview),
                "debug_extra": debug_extra,
                "bound_goal": getattr(extracted, "_design_optimisation_goal", None) is bridge._design_optimisation_goal,
                "bound_parse": getattr(extracted, "_parse_util_value", None) is bridge._parse_util_value,
                "bound_eval": getattr(extracted, "evaluate_candidate_full", None) is bridge.evaluate_candidate_full,
            }
        )
        if isinstance(debug_extra, dict):
            debug_extra["fake_called"] = True
        return {"title_main": "fake target band"}

    debug_extra: dict = {}
    try:
        bridge._get_actionable_target_band_winner_extracted = _fake_extracted
        returned = bridge._get_actionable_target_band_winner(
            {"D": 600},
            {"all_key_pass": True, "worst_util": 0.88},
            debug_extra=debug_extra,
        )
    finally:
        bridge._get_actionable_target_band_winner_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "EFFICIENCY_TARGET_UTIL_MIN", None) == bridge.EFFICIENCY_TARGET_UTIL_MIN
        and getattr(extracted, "EFFICIENCY_TARGET_UTIL_MAX", None) == bridge.EFFICIENCY_TARGET_UTIL_MAX
        and getattr(extracted, "TARGET_BAND_EPS", None) == bridge.TARGET_BAND_EPS
        and getattr(extracted, "_design_optimisation_goal", None) is bridge._design_optimisation_goal
        and getattr(extracted, "_parse_util_value", None) is bridge._parse_util_value
        and getattr(extracted, "evaluate_candidate_full", None) is bridge.evaluate_candidate_full
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"title_main": "fake target band"}
        and call_record.get("state") == {"D": 600}
        and call_record.get("overview") == {"all_key_pass": True, "worst_util": 0.88}
        and call_record.get("debug_extra") is debug_extra
        and debug_extra.get("fake_called") is True
        and call_record.get("bound_goal") is True
        and call_record.get("bound_parse") is True
        and call_record.get("bound_eval") is True
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
    json_path = ARTIFACTS / f"inputs_page_actionable_target_band_winner_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_actionable_target_band_winner_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Actionable Target Band Winner Extraction",
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
