"""Verify candidate-family governing-domain classifier extraction."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "candidate_family_classification.py"
COMPUTE = ROOT / "inputs_page_modules" / "auto_design_compute.py"
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
    compute_source = COMPUTE.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "_candidate_family_matches_governing_domain")
    module_node = _function_node(module_source, "_candidate_family_matches_governing_domain")
    module_tree = ast.parse(module_source)
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    dependency_section = compute_source.partition("def bind_legacy_auto_design_dependencies")[0]
    imports_streamlit = any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(alias.name == "streamlit" for alias in getattr(node, "names", []))
        for node in ast.walk(module_tree)
    )
    uses_st_name = any(isinstance(node, ast.Name) and node.id == "st" for node in ast.walk(module_tree))

    from inputs_page_modules.design_guide.candidate_family_classification import (
        _candidate_family_matches_governing_domain as classifier,
    )
    import inputs_page_app_contract_bridge as bridge
    import inputs_page_modules.auto_design_compute as compute

    matrix = {
        "bending_strength": classifier("bending_strength_depth", "bending"),
        "bottom_reduction": classifier("bottom_reduction_light", "bending"),
        "geometry_reduction": classifier("geometry_reduction_width", "bending"),
        "bending_named_geometry": classifier("geometry", "bending"),
        "shear_spacing_reduction": classifier("spacing_reduction", "shear"),
        "shear_depth_increase": classifier("depth_increase", "shear"),
        "shear_variant_spacing": classifier("shear_spacing_refine", "shear"),
        "shear_variant_links": classifier("shear_links_refine", "shear"),
        "shear_adjust_excluded": classifier("shear_adjust", "shear"),
        "shear_layout_cleanup_excluded": classifier("shear_spacing_layout_cleanup", "shear"),
        "generic_cleanup_excluded": classifier("spacing_cleanup", "shear"),
        "empty_excluded": classifier("", "shear"),
        "unknown_domain_excluded": classifier("geometry", "crack"),
    }

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 2,
        "bridge_delegates_to_extracted_module": "_candidate_family_matches_governing_domain_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 60,
        "module_is_pure_no_streamlit": not imports_streamlit and not uses_st_name,
        "module_is_pure_no_bridge_import": "inputs_page_app_contract_bridge" not in module_source,
        "compute_imports_classifier_directly": "candidate_family_classification import" in compute_source,
        "compute_dependency_list_no_longer_binds_classifier": "'_candidate_family_matches_governing_domain'" not in dependency_section
        and '"_candidate_family_matches_governing_domain"' not in dependency_section,
        "compute_runtime_uses_extracted_classifier": getattr(compute, "_candidate_family_matches_governing_domain", None)
        is classifier,
        "bridge_runtime_delegates_to_extracted_classifier": bridge._candidate_family_matches_governing_domain("geometry", "bending") is True,
        "bending_family_matrix": all(
            matrix[key]
            for key in (
                "bending_strength",
                "bottom_reduction",
                "geometry_reduction",
                "bending_named_geometry",
            )
        ),
        "shear_family_matrix": all(
            matrix[key]
            for key in (
                "shear_spacing_reduction",
                "shear_depth_increase",
                "shear_variant_spacing",
                "shear_variant_links",
            )
        ),
        "excluded_family_matrix": not any(
            matrix[key]
            for key in (
                "shear_adjust_excluded",
                "shear_layout_cleanup_excluded",
                "generic_cleanup_excluded",
                "empty_excluded",
                "unknown_domain_excluded",
            )
        ),
    }

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "matrix": matrix,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_candidate_family_classification_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_candidate_family_classification_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Candidate Family Classification Extraction",
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
