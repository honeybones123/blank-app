"""Verify efficiency executor-promotion extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "efficiency_executor_promotion.py"
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

    name = "_try_promote_efficiency_item_to_executor_backed_candidate"
    bridge_node = _function_node(bridge_source, name)
    module_node = _function_node(module_source, name)
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 16,
        "bridge_binds_dependencies": "_bind_efficiency_executor_promotion_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_try_promote_efficiency_item_to_executor_backed_candidate_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 90,
        "module_has_dependency_binder": "def bind_efficiency_executor_promotion_dependencies" in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import efficiency_executor_promotion as extracted

    sentinel_item = {"sentinel": "efficiency_executor_promotion"}
    sentinel_meta = {"meta": "delegated"}
    original = bridge._try_promote_efficiency_item_to_executor_backed_candidate_extracted

    def _fake_extracted(
        item: dict | None,
        *,
        state: dict,
        blocked_reason: str | None = None,
    ) -> tuple[dict | None, dict]:
        return (
            dict(sentinel_item),
            {
                **dict(sentinel_meta),
                "item": dict(item or {}),
                "state": dict(state),
                "blocked_reason": blocked_reason,
                "bound_preview_contract": getattr(extracted, "_design_guide_preview_contract_for_updates", None)
                is bridge._design_guide_preview_contract_for_updates,
                "bound_executor_contract": getattr(extracted, "_guidance_executor_actionability_contract", None)
                is bridge._guidance_executor_actionability_contract,
            },
        )

    try:
        bridge._try_promote_efficiency_item_to_executor_backed_candidate_extracted = _fake_extracted
        promoted, meta = bridge._try_promote_efficiency_item_to_executor_backed_candidate(
            {"bucket": "efficiency", "title_main": "Candidate"},
            state={"D": 600},
            blocked_reason="verification_reason",
        )
    finally:
        bridge._try_promote_efficiency_item_to_executor_backed_candidate_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_design_guide_preview_contract_for_updates", None)
        is bridge._design_guide_preview_contract_for_updates
        and getattr(extracted, "_guidance_executor_actionability_contract", None)
        is bridge._guidance_executor_actionability_contract
        and getattr(extracted, "EFFICIENCY_TARGET_UTIL_MIN", None) == bridge.EFFICIENCY_TARGET_UTIL_MIN
        and getattr(extracted, "EFFICIENCY_TARGET_UTIL_MAX", None) == bridge.EFFICIENCY_TARGET_UTIL_MAX
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        promoted == sentinel_item
        and meta.get("meta") == "delegated"
        and meta.get("item") == {"bucket": "efficiency", "title_main": "Candidate"}
        and meta.get("state") == {"D": 600}
        and meta.get("blocked_reason") == "verification_reason"
        and meta.get("bound_preview_contract") is True
        and meta.get("bound_executor_contract") is True
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
    json_path = ARTIFACTS / f"inputs_page_efficiency_executor_promotion_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_efficiency_executor_promotion_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Efficiency Executor-Promotion Extraction",
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
