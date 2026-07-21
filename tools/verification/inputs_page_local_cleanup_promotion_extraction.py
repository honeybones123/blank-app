"""Verify local-cleanup promotion extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "local_cleanup_promotion.py"
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

    bridge_node = _function_node(bridge_source, "_maybe_promote_safe_local_cleanup_primary")
    module_node = _function_node(module_source, "_maybe_promote_safe_local_cleanup_primary")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 25,
        "bridge_binds_dependencies": "_bind_local_cleanup_promotion_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_maybe_promote_safe_local_cleanup_primary_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 300,
        "module_has_dependency_binder": "def bind_local_cleanup_promotion_dependencies" in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import local_cleanup_promotion as extracted

    sentinel = {"sentinel": "local_cleanup_promotion"}
    original = bridge._maybe_promote_safe_local_cleanup_primary_extracted

    def _fake_extracted(
        guidance_items: list[dict] | None,
        *,
        state: dict,
        overview: dict | None,
        efficiency_state: dict | None,
        mode_config: dict | None,
        debug_sink: dict | None = None,
        source: str = "design_guide_local_cleanup_promoter",
    ) -> tuple[list[dict], dict]:
        return (
            list(guidance_items or []),
            {
                "result": dict(sentinel),
                "state": dict(state),
                "overview": dict(overview or {}),
                "efficiency_state": dict(efficiency_state or {}),
                "mode_config": dict(mode_config or {}),
                "debug_sink": dict(debug_sink or {}),
                "source": source,
                "bound_direct": getattr(extracted, "_direct_target_band_guidance_item", None)
                is bridge._direct_target_band_guidance_item,
            },
        )

    try:
        bridge._maybe_promote_safe_local_cleanup_primary_extracted = _fake_extracted
        wrapped_items, wrapped_meta = bridge._maybe_promote_safe_local_cleanup_primary(
            [{"title_main": "Candidate"}],
            state={"D": 600},
            overview={"worst_util": 0.9},
            efficiency_state={"classification": "cleanup"},
            mode_config={"goal": "balanced"},
            debug_sink={"trace": True},
            source="verification",
        )
    finally:
        bridge._maybe_promote_safe_local_cleanup_primary_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_direct_target_band_guidance_item", None)
        is bridge._direct_target_band_guidance_item
        and getattr(extracted, "TARGET_BAND_EPS", None) == bridge.TARGET_BAND_EPS
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        wrapped_items == [{"title_main": "Candidate"}]
        and wrapped_meta.get("result") == sentinel
        and wrapped_meta.get("state") == {"D": 600}
        and wrapped_meta.get("overview") == {"worst_util": 0.9}
        and wrapped_meta.get("efficiency_state") == {"classification": "cleanup"}
        and wrapped_meta.get("mode_config") == {"goal": "balanced"}
        and wrapped_meta.get("debug_sink") == {"trace": True}
        and wrapped_meta.get("source") == "verification"
        and wrapped_meta.get("bound_direct") is True
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
    json_path = ARTIFACTS / f"inputs_page_local_cleanup_promotion_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_local_cleanup_promotion_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Local-Cleanup Promotion Extraction",
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
