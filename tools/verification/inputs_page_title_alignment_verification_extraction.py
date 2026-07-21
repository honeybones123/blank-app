"""Verify title-alignment verification extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "title_alignment_verification.py"
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

    bridge_node = _function_node(bridge_source, "_design_guide_title_alignment_verification_record")
    module_node = _function_node(module_source, "_design_guide_title_alignment_verification_record")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    dependency_block = module_source.split("def bind_title_alignment_verification_dependencies", 1)[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 16,
        "bridge_binds_dependencies": "_bind_title_alignment_verification_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_design_guide_title_alignment_verification_record_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 180,
        "module_has_dependency_binder": "def bind_title_alignment_verification_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "dependency_binder_excludes_local_nt": '"_nt"' not in dependency_block,
        "module_keeps_alignment_contract_surface": (
            "DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT" in module_source
            and "selector_display_chain_mismatch" in module_source
            and "title_family_mismatch" in module_source
            and "terminal_optimal_no_recommendation" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import title_alignment_verification as extracted

    original = bridge._design_guide_title_alignment_verification_record_extracted
    call_record: dict = {}

    def _fake_extracted(
        *,
        guidance_items: list[dict],
        guidance_debug: dict | None,
        disp_state: dict,
        recommendation_result: dict | None,
        pending_recommendation: dict | None,
    ) -> dict:
        call_record.update(
            {
                "guidance_items": list(guidance_items),
                "guidance_debug": dict(guidance_debug or {}),
                "disp_state": dict(disp_state),
                "recommendation_result": dict(recommendation_result or {}),
                "pending_recommendation": dict(pending_recommendation or {}),
                "bound_event": (
                    getattr(extracted, "DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT", None)
                    == bridge.DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT
                ),
                "bound_first_actionable": (
                    getattr(extracted, "_first_actionable_guidance_item", None)
                    is bridge._first_actionable_guidance_item
                ),
                "bound_resolve_updates": (
                    getattr(extracted, "_resolve_recommendation_updates", None)
                    is bridge._resolve_recommendation_updates
                ),
            }
        )
        return {"event": "fake_alignment"}

    try:
        bridge._design_guide_title_alignment_verification_record_extracted = _fake_extracted
        returned = bridge._design_guide_title_alignment_verification_record(
            guidance_items=[{"title_main": "A"}],
            guidance_debug={"selector": "A"},
            disp_state={"D": 600},
            recommendation_result={"title": "A"},
            pending_recommendation={"title": "A"},
        )
    finally:
        bridge._design_guide_title_alignment_verification_record_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT", None)
        == bridge.DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT
        and getattr(extracted, "_compound_subfamilies_from_updates", None)
        is bridge._compound_subfamilies_from_updates
        and getattr(extracted, "_label_consistent_with_updates_families", None)
        is bridge._label_consistent_with_updates_families
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"event": "fake_alignment"}
        and call_record.get("guidance_items") == [{"title_main": "A"}]
        and call_record.get("guidance_debug") == {"selector": "A"}
        and call_record.get("disp_state") == {"D": 600}
        and call_record.get("recommendation_result") == {"title": "A"}
        and call_record.get("pending_recommendation") == {"title": "A"}
        and call_record.get("bound_event") is True
        and call_record.get("bound_first_actionable") is True
        and call_record.get("bound_resolve_updates") is True
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
    json_path = ARTIFACTS / f"inputs_page_title_alignment_verification_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_title_alignment_verification_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Title Alignment Verification Extraction",
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
