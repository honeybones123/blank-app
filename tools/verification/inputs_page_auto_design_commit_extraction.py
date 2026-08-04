"""Verify auto-design commit extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "auto_design_commit.py"
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

    bridge_node = _function_node(bridge_source, "_commit_auto_design_candidate_to_shared")
    module_node = _function_node(module_source, "_commit_auto_design_candidate_to_shared")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 3,
        "bridge_binds_dependencies": "_bind_auto_design_commit_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_commit_auto_design_candidate_to_shared_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 119,
        "module_has_dependency_binder": "def bind_auto_design_commit_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_commit_contract_surface": all(
            token in module_source
            for token in (
                "DG ALT APPLY ENTRY",
                "auto_design_commit",
                "_hydrated_from_shared_map",
                "Cleared row widget keys after auto-design commit",
                "inputs_page.py:_commit_auto_design_candidate_to_shared",
                "H121",
                "auto_design_commit:canonical_convenience",
                "finalize_auto_design_publish",
                "set_run_design_clicked=True",
                "_commit_auto_design_candidate_to_shared_debug",
                "invalidated_recommendation_cache_keys",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import auto_design_commit as extracted

    original = bridge._commit_auto_design_candidate_to_shared_extracted
    call_record: dict = {}

    def _fake_extracted(candidate: dict) -> dict:
        call_record.update(
            {
                "candidate": dict(candidate),
                "bound_st": getattr(extracted, "st", None) is bridge.st,
                "bound_set_shared": getattr(extracted, "_set_shared_updates", None)
                is bridge._set_shared_updates,
                "bound_normalise": getattr(extracted, "_normalise_invalid_shear_state_updates", None)
                is bridge._normalise_invalid_shear_state_updates,
                "bound_invalidate": getattr(extracted, "_invalidate_design_guide_caches", None)
                is bridge._invalidate_design_guide_caches,
                "bound_publish": getattr(extracted, "finalize_auto_design_publish", None)
                is bridge.finalize_auto_design_publish,
            }
        )
        return {"D": 650}

    try:
        bridge._commit_auto_design_candidate_to_shared_extracted = _fake_extracted
        returned = bridge._commit_auto_design_candidate_to_shared({"state": {"D": 650}})
    finally:
        bridge._commit_auto_design_candidate_to_shared_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "_set_shared_updates", None) is bridge._set_shared_updates
        and getattr(extracted, "_normalise_invalid_shear_state_updates", None)
        is bridge._normalise_invalid_shear_state_updates
        and getattr(extracted, "_invalidate_design_guide_caches", None)
        is bridge._invalidate_design_guide_caches
        and getattr(extracted, "finalize_auto_design_publish", None) is bridge.finalize_auto_design_publish
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"D": 650}
        and call_record.get("candidate") == {"state": {"D": 650}}
        and call_record.get("bound_st") is True
        and call_record.get("bound_set_shared") is True
        and call_record.get("bound_normalise") is True
        and call_record.get("bound_invalidate") is True
        and call_record.get("bound_publish") is True
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
    json_path = ARTIFACTS / f"inputs_page_auto_design_commit_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_auto_design_commit_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Auto Design Commit Extraction",
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
