"""Verify severe-shear escalation debug-log extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "severe_shear_escalation_log.py"
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

    bridge_node = _function_node(bridge_source, "_log_severe_shear_escalation")
    module_node = _function_node(module_source, "_log_severe_shear_escalation")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 18,
        "bridge_binds_dependencies": "_bind_severe_shear_escalation_log_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_log_severe_shear_escalation_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 170,
        "module_has_dependency_binder": "def bind_severe_shear_escalation_log_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_debug_log_contract_surface": (
            "Severe shear escalation candidates" in module_source
            and "H_SHEAR_ESCALATION" in module_source
            and "inputs_page.py:severe_shear_escalation" in module_source
            and "family_comparison" in module_source
            and "final_selected_reason" in module_source
            and "end_of_run_summary" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import severe_shear_escalation_log as extracted

    original = bridge._log_severe_shear_escalation_extracted
    call_record: dict = {}

    def _fake_extracted(
        *,
        source: str,
        seed_candidate: dict,
        severity_band: str,
        candidates: list[dict],
        selected: dict | None,
        family_audit: dict[str, list[dict]] | None = None,
    ) -> None:
        call_record.update(
            {
                "source": source,
                "seed_candidate": dict(seed_candidate),
                "severity_band": severity_band,
                "candidates": list(candidates),
                "selected": dict(selected or {}),
                "family_audit": dict(family_audit or {}),
                "bound_streamlit": getattr(extracted, "st", None) is bridge.st,
                "bound_debug_log": getattr(extracted, "_agent_debug_log", None) is bridge._agent_debug_log,
                "bound_goal": getattr(extracted, "_design_optimisation_goal", None) is bridge._design_optimisation_goal,
                "bound_reserves": getattr(extracted, "_secondary_action_reserves", None) is bridge._secondary_action_reserves,
            }
        )

    try:
        bridge._log_severe_shear_escalation_extracted = _fake_extracted
        returned = bridge._log_severe_shear_escalation(
            source="unit",
            seed_candidate={"state": {"D": 600}},
            severity_band="severe",
            candidates=[{"candidate_key": "a"}],
            selected={"candidate_key": "a"},
            family_audit={"spacing tighter": [{"candidate_key": "a", "selected": True}]},
        )
    finally:
        bridge._log_severe_shear_escalation_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "_agent_debug_log", None) is bridge._agent_debug_log
        and getattr(extracted, "_design_optimisation_goal", None) is bridge._design_optimisation_goal
        and getattr(extracted, "_geometry_lock_enabled", None) is bridge._geometry_lock_enabled
        and getattr(extracted, "_secondary_action_reserves", None) is bridge._secondary_action_reserves
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned is None
        and call_record.get("source") == "unit"
        and call_record.get("seed_candidate") == {"state": {"D": 600}}
        and call_record.get("severity_band") == "severe"
        and call_record.get("candidates") == [{"candidate_key": "a"}]
        and call_record.get("selected") == {"candidate_key": "a"}
        and call_record.get("family_audit") == {"spacing tighter": [{"candidate_key": "a", "selected": True}]}
        and call_record.get("bound_streamlit") is True
        and call_record.get("bound_debug_log") is True
        and call_record.get("bound_goal") is True
        and call_record.get("bound_reserves") is True
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
    json_path = ARTIFACTS / f"inputs_page_severe_shear_escalation_log_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_severe_shear_escalation_log_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Severe Shear Escalation Log Extraction",
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
