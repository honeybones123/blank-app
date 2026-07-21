"""Verify full candidate evaluation extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "candidate_full_evaluation.py"
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

    bridge_node = _function_node(bridge_source, "evaluate_candidate_full_for_app_bridge")
    module_node = _function_node(module_source, "evaluate_candidate_full_for_app_bridge")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_prefix = bridge_source[: bridge_source.index("def evaluate_candidate_full_for_app_bridge")]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 16,
        "bridge_keeps_speed_profile_decorator": '@speed_profiled("candidate_preview_evaluation.evaluate_candidate_full", category="compute")' in bridge_prefix[-240:],
        "bridge_binds_dependencies": "_bind_candidate_full_evaluation_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_evaluate_candidate_full_for_app_bridge_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 170,
        "module_has_dependency_binder": "def bind_candidate_full_evaluation_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_evaluation_contract_surface": (
            "candidate_preview_evaluation.evaluate_candidate_full" in module_source
            and "get_rerun_pure_cache" in module_source
            and "set_rerun_pure_cache" in module_source
            and "build_full_candidate_evaluation_result_projection" in module_source
            and "_log_phi_mu_capacity_mismatch_for_app_bridge" in module_source
            and "bending_present" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import candidate_full_evaluation as extracted

    original = bridge._evaluate_candidate_full_for_app_bridge_extracted
    call_record: dict = {}

    def _fake_extracted(
        candidate_state: dict,
        *,
        source: str = "full_eval",
        label: str | None = None,
        action_type: str | None = None,
        updates: dict | None = None,
    ) -> dict:
        call_record.update(
            {
                "candidate_state": dict(candidate_state),
                "source": source,
                "label": label,
                "action_type": action_type,
                "updates": dict(updates or {}),
                "bound_streamlit": getattr(extracted, "st", None) is bridge.st,
                "bound_cache_get": getattr(extracted, "get_rerun_pure_cache", None) is bridge.get_rerun_pure_cache,
                "bound_projection": (
                    getattr(extracted, "build_full_candidate_evaluation_result_projection", None)
                    is bridge.build_full_candidate_evaluation_result_projection
                ),
                "bound_overview": getattr(extracted, "_collect_design_overview", None) is bridge._collect_design_overview,
            }
        )
        return {"candidate_status": "fake"}

    try:
        bridge._evaluate_candidate_full_for_app_bridge_extracted = _fake_extracted
        returned = bridge.evaluate_candidate_full_for_app_bridge(
            {"D": 600},
            source="unit",
            label="Candidate",
            action_type="apply",
            updates={"D": 650},
        )
    finally:
        bridge._evaluate_candidate_full_for_app_bridge_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "stable_fingerprint_for_payload", None)
        is bridge.stable_fingerprint_for_payload
        and getattr(extracted, "get_rerun_pure_cache", None) is bridge.get_rerun_pure_cache
        and getattr(extracted, "set_rerun_pure_cache", None) is bridge.set_rerun_pure_cache
        and getattr(extracted, "build_full_candidate_evaluation_result_projection", None)
        is bridge.build_full_candidate_evaluation_result_projection
        and getattr(extracted, "_evaluate_bending_with_bottom_state_for_app_bridge", None)
        is bridge._evaluate_bending_with_bottom_state_for_app_bridge
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"candidate_status": "fake"}
        and call_record.get("candidate_state") == {"D": 600}
        and call_record.get("source") == "unit"
        and call_record.get("label") == "Candidate"
        and call_record.get("action_type") == "apply"
        and call_record.get("updates") == {"D": 650}
        and call_record.get("bound_streamlit") is True
        and call_record.get("bound_cache_get") is True
        and call_record.get("bound_projection") is True
        and call_record.get("bound_overview") is True
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
    json_path = ARTIFACTS / f"inputs_page_candidate_full_evaluation_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_candidate_full_evaluation_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Candidate Full Evaluation Extraction",
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
