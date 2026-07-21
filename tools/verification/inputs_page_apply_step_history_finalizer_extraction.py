"""Verify apply step-history finalizer extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "apply_step_history_finalizer.py"
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

    bridge_node = _function_node(bridge_source, "_finalize_design_guide_apply_step_history")
    module_node = _function_node(module_source, "_finalize_design_guide_apply_step_history")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 11,
        "bridge_binds_dependencies": "_bind_apply_step_history_finalizer_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_finalize_design_guide_apply_step_history_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 108,
        "module_has_dependency_binder": "def bind_apply_step_history_finalizer_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_apply_step_history_contract_surface": all(
            token in module_source
            for token in (
                "DESIGN_GUIDE_PENDING_STEP_CTX_KEY",
                "DESIGN_GUIDE_STEP_HISTORY_KEY",
                "DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY",
                "build_inputs_design_guide_apply_step_history_entry_plan",
                "_collect_design_overview",
                "_compute_bottom_reo_recommendation",
                "_guidance_apply_change_lines",
                "_signature_dict_for_step_history",
                "guidance:",
                "recommendation_label_at_step_start",
                "one_click_candidate_label_at_step_start",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import apply_step_history_finalizer as extracted

    original = bridge._finalize_design_guide_apply_step_history_extracted
    call_record: dict = {}

    def _fake_extracted(*, prior_state: dict, source: str, applied_candidate: dict | None) -> None:
        call_record.update(
            {
                "prior_state": dict(prior_state),
                "source": source,
                "applied_candidate": dict(applied_candidate or {}),
                "bound_st": getattr(extracted, "st", None) is bridge.st,
                "bound_shared_snapshot": getattr(extracted, "_shared_state_snapshot", None)
                is bridge._shared_state_snapshot,
                "bound_entry_plan": getattr(
                    extracted,
                    "build_inputs_design_guide_apply_step_history_entry_plan",
                    None,
                )
                is bridge.build_inputs_design_guide_apply_step_history_entry_plan,
                "bound_pending_key": getattr(extracted, "DESIGN_GUIDE_PENDING_STEP_CTX_KEY", None)
                is bridge.DESIGN_GUIDE_PENDING_STEP_CTX_KEY,
            }
        )
        return None

    try:
        bridge._finalize_design_guide_apply_step_history_extracted = _fake_extracted
        returned = bridge._finalize_design_guide_apply_step_history(
            prior_state={"D": 650.0},
            source="guidance:apply",
            applied_candidate={"recommendation_family_tag": "BENDING"},
        )
    finally:
        bridge._finalize_design_guide_apply_step_history_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "_shared_state_snapshot", None) is bridge._shared_state_snapshot
        and getattr(extracted, "build_inputs_design_guide_apply_step_history_entry_plan", None)
        is bridge.build_inputs_design_guide_apply_step_history_entry_plan
        and getattr(extracted, "DESIGN_GUIDE_PENDING_STEP_CTX_KEY", None)
        is bridge.DESIGN_GUIDE_PENDING_STEP_CTX_KEY
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned is None
        and call_record.get("prior_state") == {"D": 650.0}
        and call_record.get("source") == "guidance:apply"
        and call_record.get("applied_candidate") == {"recommendation_family_tag": "BENDING"}
        and call_record.get("bound_st") is True
        and call_record.get("bound_shared_snapshot") is True
        and call_record.get("bound_entry_plan") is True
        and call_record.get("bound_pending_key") is True
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
    json_path = ARTIFACTS / f"inputs_page_apply_step_history_finalizer_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_apply_step_history_finalizer_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Apply Step History Finalizer Extraction",
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
