"""Verify candidate material-worsening comparison extraction from the Inputs bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "auto_design_scoring.py"
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

    name = "candidate_materially_worsens"
    bridge_node = _function_node(bridge_source, name)
    module_node = _function_node(module_source, name)
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 16,
        "bridge_passes_typed_runtime": "runtime=_build_auto_design_scoring_runtime()" in bridge_body,
        "bridge_delegates_to_extracted_module": "_candidate_materially_worsens_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 94,
        "module_has_frozen_typed_runtime": (
            "@dataclass(frozen=True)" in module_source
            and "class AutoDesignScoringRuntime" in module_source
            and "def bind_auto_design_scoring_dependencies" not in module_source
            and "globals()" not in module_source
        ),
        "module_exports_material_worsening": '"candidate_materially_worsens"' in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_rejection_contract": all(
            token in module_source
            for token in (
                "heavier_bottom_steel_without_ductility_gain",
                "heavier_bottom_steel_lower_Mu_star_over_phiMu",
                "inputs_page.py:candidate_materially_worsens",
                "H31_DUCTILITY",
                "H31_STEEL",
                "H31",
                "low_reo",
                "shallow",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    original = bridge._candidate_materially_worsens_extracted
    call_record: dict = {}

    def _fake_extracted(
        new_candidate: dict,
        old_candidate: dict,
        mode_config: dict,
        *,
        phase: str,
        runtime,
    ) -> bool:
        call_record.update(
            {
                "new_candidate": dict(new_candidate),
                "old_candidate": dict(old_candidate),
                "mode_config": dict(mode_config),
                "phase": phase,
                "runtime_type": type(runtime).__name__,
                "bound_debug_log": runtime.agent_debug_log is bridge._agent_debug_log,
                "bound_failed_labels": runtime.failed_check_labels is bridge._failed_check_labels,
                "bound_util_gap": runtime.utilisation_gap is bridge.utilisation_gap,
                "bound_complexity": runtime.compute_reo_complexity is bridge.compute_reo_complexity,
            }
        )
        return True

    try:
        bridge._candidate_materially_worsens_extracted = _fake_extracted
        returned = bridge.candidate_materially_worsens(
            {"is_compliant": True, "worst_util": 0.92},
            {"is_compliant": True, "worst_util": 0.90},
            {"search_strategy": "balanced"},
            phase="verification",
        )
    finally:
        bridge._candidate_materially_worsens_extracted = original

    checks["bridge_runtime_delegates_with_arguments"] = (
        returned is True
        and call_record.get("new_candidate") == {"is_compliant": True, "worst_util": 0.92}
        and call_record.get("old_candidate") == {"is_compliant": True, "worst_util": 0.90}
        and call_record.get("mode_config") == {"search_strategy": "balanced"}
        and call_record.get("phase") == "verification"
        and call_record.get("runtime_type") == "AutoDesignScoringRuntime"
        and call_record.get("bound_debug_log") is True
        and call_record.get("bound_failed_labels") is True
        and call_record.get("bound_util_gap") is True
        and call_record.get("bound_complexity") is True
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
    json_path = ARTIFACTS / f"inputs_page_candidate_material_worsening_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_candidate_material_worsening_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Candidate Material-Worsening Extraction",
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
