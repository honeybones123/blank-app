"""Verify shear local-cleanup extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "shear_local_cleanup.py"
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

    bridge_node = _function_node(bridge_source, "_best_safe_shear_local_cleanup_recommendation")
    module_node = _function_node(module_source, "_best_safe_shear_local_cleanup_recommendation")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 12,
        "bridge_binds_dependencies": "_bind_shear_local_cleanup_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_best_safe_shear_local_cleanup_recommendation_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 220,
        "module_has_dependency_binder": "def bind_shear_local_cleanup_dependencies" in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import shear_local_cleanup as extracted

    sentinel = {"sentinel": "shear_local_cleanup"}
    original = bridge._best_safe_shear_local_cleanup_recommendation_extracted

    def _fake_extracted(
        state: dict,
        overview: dict,
        first_recommendation: dict | None,
    ) -> dict:
        return {
            "result": dict(sentinel),
            "state": dict(state),
            "overview": dict(overview),
            "first_recommendation": dict(first_recommendation or {}),
            "bound_no_shear_spacing": getattr(extracted, "CANONICAL_NO_SHEAR_SLIG_MM", None)
            == bridge.CANONICAL_NO_SHEAR_SLIG_MM,
        }

    try:
        bridge._best_safe_shear_local_cleanup_recommendation_extracted = _fake_extracted
        wrapped = bridge._best_safe_shear_local_cleanup_recommendation(
            {"D": 600},
            {"worst_util": 0.9},
            {"updates": {"s_lig": 250}},
        )
    finally:
        bridge._best_safe_shear_local_cleanup_recommendation_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "CANONICAL_NO_SHEAR_SLIG_MM", None)
        == bridge.CANONICAL_NO_SHEAR_SLIG_MM
        and getattr(extracted, "_evaluate_auto_design_candidate", None)
        is bridge._evaluate_auto_design_candidate
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        wrapped.get("result") == sentinel
        and wrapped.get("state") == {"D": 600}
        and wrapped.get("overview") == {"worst_util": 0.9}
        and wrapped.get("first_recommendation") == {"updates": {"s_lig": 250}}
        and wrapped.get("bound_no_shear_spacing") is True
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
    json_path = ARTIFACTS / f"inputs_page_shear_local_cleanup_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_shear_local_cleanup_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Shear Local-Cleanup Extraction",
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
