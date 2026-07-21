"""Verify primary one-click validation extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "primary_one_click_validation.py"
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

    bridge_node = _function_node(bridge_source, "_candidate_is_valid_primary_one_click")
    module_node = _function_node(module_source, "_candidate_is_valid_primary_one_click")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 5,
        "bridge_binds_dependencies": "_bind_primary_one_click_validation_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_candidate_is_valid_primary_one_click_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 108,
        "module_has_dependency_binder": "def bind_primary_one_click_validation_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_validation_contract_surface": all(
            token in module_source
            for token in (
                "missing_candidate",
                "candidate_preview_has_fail_status",
                "single_fail_or_no_fail",
                "full_failure_coverage",
                "partial_failure_coverage",
                "covers_all_current_failures",
                "covered_fail_keys",
                "remaining_fail_keys",
                "requires_full_coverage",
                "BEAM_STATUS_FAIL",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import primary_one_click_validation as extracted

    original = bridge._candidate_is_valid_primary_one_click_extracted
    call_record: dict = {}

    def _fake_extracted(candidate: dict | None, overview: dict) -> tuple[bool, dict]:
        call_record.update(
            {
                "candidate": dict(candidate or {}),
                "overview": dict(overview or {}),
                "bound_full_coverage": getattr(
                    extracted,
                    "_requires_full_coverage_for_primary_one_click",
                    None,
                )
                is bridge._requires_full_coverage_for_primary_one_click,
                "bound_preview_fail": getattr(
                    extracted,
                    "_candidate_preview_statuses_have_explicit_fail",
                    None,
                )
                is bridge._candidate_preview_statuses_have_explicit_fail,
                "bound_fail_status": getattr(extracted, "BEAM_STATUS_FAIL", None)
                is bridge.BEAM_STATUS_FAIL,
            }
        )
        return True, {"valid": True, "reason": "fake_valid"}

    try:
        bridge._candidate_is_valid_primary_one_click_extracted = _fake_extracted
        returned = bridge._candidate_is_valid_primary_one_click(
            {"overview": {"statuses": {"shear": "PASS"}}},
            {"statuses": {"shear": "FAIL"}},
        )
    finally:
        bridge._candidate_is_valid_primary_one_click_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_requires_full_coverage_for_primary_one_click", None)
        is bridge._requires_full_coverage_for_primary_one_click
        and getattr(extracted, "_candidate_preview_statuses_have_explicit_fail", None)
        is bridge._candidate_preview_statuses_have_explicit_fail
        and getattr(extracted, "BEAM_STATUS_FAIL", None) is bridge.BEAM_STATUS_FAIL
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == (True, {"valid": True, "reason": "fake_valid"})
        and call_record.get("candidate") == {"overview": {"statuses": {"shear": "PASS"}}}
        and call_record.get("overview") == {"statuses": {"shear": "FAIL"}}
        and call_record.get("bound_full_coverage") is True
        and call_record.get("bound_preview_fail") is True
        and call_record.get("bound_fail_status") is True
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
    json_path = ARTIFACTS / f"inputs_page_primary_one_click_validation_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_primary_one_click_validation_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary One Click Validation Extraction",
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
