"""Verify Design Guide banner render-state extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "banner_render_state.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")

    bridge_node = _function_node(bridge_source, "_design_guide_banner_matches_current_render")
    module_node = _function_node(module_source, "_design_guide_banner_matches_current_render")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 15,
        "bridge_binds_dependencies": "_bind_banner_render_state_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_design_guide_banner_matches_current_render_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 55,
        "module_has_dependency_binder": "def bind_banner_render_state_dependencies" in module_source,
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_banner_contract_surface": all(
            token in module_source
            for token in (
                "baseline_fingerprint",
                "recommendation_apply_mode",
                "recommendation_apply_payload",
                "recommendation_id",
                "_pending_recommendation_equivalent",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import banner_render_state as extracted

    original = bridge._design_guide_banner_matches_current_render_extracted
    call_record: dict = {}

    def _fake_extracted(
        banner_payload: dict | None,
        banner_meta: dict | None,
        recommendation_result: dict | None,
        pending_recommendation: dict | None,
        fingerprint: tuple | None,
    ) -> bool:
        call_record.update(
            {
                "banner_payload": dict(banner_payload or {}),
                "banner_meta": dict(banner_meta or {}),
                "recommendation_result": dict(recommendation_result or {}),
                "pending_recommendation": dict(pending_recommendation or {}),
                "fingerprint": fingerprint,
                "bound_equivalence": getattr(extracted, "_pending_recommendation_equivalent", None)
                is bridge._pending_recommendation_equivalent,
            }
        )
        return True

    try:
        bridge._design_guide_banner_matches_current_render_extracted = _fake_extracted
        returned = bridge._design_guide_banner_matches_current_render(
            {"recommendation_title": "A"},
            {"fingerprint": ("fp",), "recommendation_apply_payload": {"updates": {"D": 650}}},
            {"title": "A"},
            {"title": "A"},
            ("fp",),
        )
    finally:
        bridge._design_guide_banner_matches_current_render_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_pending_recommendation_equivalent", None)
        is bridge._pending_recommendation_equivalent
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned is True
        and call_record.get("banner_payload") == {"recommendation_title": "A"}
        and call_record.get("banner_meta") == {
            "fingerprint": ("fp",),
            "recommendation_apply_payload": {"updates": {"D": 650}},
        }
        and call_record.get("recommendation_result") == {"title": "A"}
        and call_record.get("pending_recommendation") == {"title": "A"}
        and call_record.get("fingerprint") == ("fp",)
        and call_record.get("bound_equivalence") is True
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
    json_path = ARTIFACTS / f"inputs_page_banner_render_state_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_banner_render_state_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Banner Render State Extraction",
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
