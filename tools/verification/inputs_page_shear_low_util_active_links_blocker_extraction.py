"""Verify shear low-util active-links blocker extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "shear_low_util_active_links_blocker.py"
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

    bridge_node = _function_node(bridge_source, "_shear_low_util_active_links_exact_blocker")
    module_node = _function_node(module_source, "_shear_low_util_active_links_exact_blocker")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 12,
        "bridge_binds_dependencies": "_bind_shear_low_util_active_links_blocker_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_shear_low_util_active_links_exact_blocker_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 170,
        "module_has_dependency_binder": "def bind_shear_low_util_active_links_blocker_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_blocker_contract_surface": (
            "FINAL_ACCEPTED_MIN_FAMILY_UTIL" in module_source
            and "accepted_green_shear_low_util_blocker_probe" in module_source
            and "final accepted shear utilisation threshold" in module_source
            and "Further shear-link cleanup" in module_source
            and "why_reduction_would_hurt_other_design_elements" in module_source
            and "attempted_candidate_count" in module_source
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import shear_low_util_active_links_blocker as extracted

    original = bridge._shear_low_util_active_links_exact_blocker_extracted
    call_record: dict = {}

    def _fake_extracted(
        state: dict | None,
        overview: dict | None,
        *,
        threshold: float,
    ) -> dict:
        call_record.update(
            {
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "threshold": threshold,
                "bound_active": (
                    getattr(extracted, "_shear_reinforcement_is_active", None)
                    is bridge._shear_reinforcement_is_active
                ),
                "bound_eval": (
                    getattr(extracted, "_evaluate_auto_design_candidate_for_app_bridge", None)
                    is bridge._evaluate_auto_design_candidate_for_app_bridge
                ),
                "bound_variants": (
                    getattr(extracted, "_generate_less_shear_reo_variants_for_app_bridge", None)
                    is bridge._generate_less_shear_reo_variants_for_app_bridge
                ),
            }
        )
        return {"family": "shear", "failed_check_status": "BLOCKED"}

    try:
        bridge._shear_low_util_active_links_exact_blocker_extracted = _fake_extracted
        returned = bridge._shear_low_util_active_links_exact_blocker(
            {"lig_legs": 2},
            {"utils": {"shear": 0.62}},
            threshold=0.85,
        )
    finally:
        bridge._shear_low_util_active_links_exact_blocker_extracted = original

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_shear_reinforcement_is_active", None)
        is bridge._shear_reinforcement_is_active
        and getattr(extracted, "_parse_util_value", None) is bridge._parse_util_value
        and getattr(extracted, "_design_mode_config", None) is bridge._design_mode_config
        and getattr(extracted, "_evaluate_auto_design_candidate_for_app_bridge", None)
        is bridge._evaluate_auto_design_candidate_for_app_bridge
        and getattr(extracted, "_guidance_cleanup_candidate_id", None)
        is bridge._guidance_cleanup_candidate_id
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"family": "shear", "failed_check_status": "BLOCKED"}
        and call_record.get("state") == {"lig_legs": 2}
        and call_record.get("overview") == {"utils": {"shear": 0.62}}
        and call_record.get("threshold") == 0.85
        and call_record.get("bound_active") is True
        and call_record.get("bound_eval") is True
        and call_record.get("bound_variants") is True
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
    json_path = ARTIFACTS / f"inputs_page_shear_low_util_active_links_blocker_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_shear_low_util_active_links_blocker_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Shear Low Util Active Links Blocker Extraction",
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
