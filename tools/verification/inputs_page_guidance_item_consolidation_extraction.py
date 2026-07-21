"""Verify guidance item consolidation extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "guidance_item_consolidation.py"
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

    bridge_node = _function_node(bridge_source, "_consolidate_guidance_items_by_family")
    bridge_same_problem_node = _function_node(bridge_source, "_guidance_item_is_same_problem_wrapper")
    bridge_collapse_node = _function_node(bridge_source, "_collapse_to_single_primary_guidance_item")
    module_node = _function_node(module_source, "_consolidate_guidance_items_by_family")
    module_same_problem_node = _function_node(module_source, "_guidance_item_is_same_problem_wrapper")
    module_collapse_node = _function_node(module_source, "_collapse_to_single_primary_guidance_item")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_same_problem_body = ast.get_source_segment(bridge_source, bridge_same_problem_node) or ""
    bridge_collapse_body = ast.get_source_segment(bridge_source, bridge_collapse_node) or ""
    module_collapse_body = ast.get_source_segment(module_source, module_collapse_node) or ""
    dependency_section = module_source.partition("def bind_guidance_item_consolidation_dependencies")[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 5,
        "bridge_binds_dependencies": "_bind_guidance_item_consolidation_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_consolidate_guidance_items_by_family_extracted" in bridge_body,
        "bridge_same_problem_wrapper_is_tiny": (
            (bridge_same_problem_node.end_lineno or bridge_same_problem_node.lineno)
            - bridge_same_problem_node.lineno
            + 1
            <= 3
        ),
        "bridge_same_problem_delegates_to_extracted_module": (
            "_guidance_item_is_same_problem_wrapper_extracted" in bridge_same_problem_body
        ),
        "bridge_collapse_wrapper_is_tiny": (
            (bridge_collapse_node.end_lineno or bridge_collapse_node.lineno)
            - bridge_collapse_node.lineno
            + 1
            <= 6
        ),
        "bridge_collapse_binds_dependencies": "_bind_guidance_item_consolidation_dependencies(globals())"
        in bridge_collapse_body,
        "bridge_collapse_delegates_to_extracted_module": (
            "_collapse_to_single_primary_guidance_item_extracted" in bridge_collapse_body
        ),
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 104,
        "module_owns_same_problem_wrapper_body": (
            (module_same_problem_node.end_lineno or module_same_problem_node.lineno)
            - module_same_problem_node.lineno
            + 1
            >= 70
        ),
        "module_owns_collapse_body": (
            (module_collapse_node.end_lineno or module_collapse_node.lineno)
            - module_collapse_node.lineno
            + 1
            >= 60
        ),
        "module_has_dependency_binder": "def bind_guidance_item_consolidation_dependencies" in module_source,
        "module_binds_collapse_dependencies": all(
            token in dependency_section
            for token in (
                '"_candidate_cache_key"',
                '"_first_actionable_guidance_item"',
            )
        ),
        "module_no_longer_binds_guidance_item_family": '"_guidance_item_family"' not in dependency_section
        and "'_guidance_item_family'" not in dependency_section,
        "module_imports_guidance_item_family_directly": "item_identity import _guidance_item_family" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_consolidation_contract_surface": all(
            token in module_source
            for token in (
                "no_items",
                "promoted_later_better_primary",
                "family_overlap_with_primary",
                "same_problem_wrapper",
                "same_family_no_coverage_gain",
                "kept_distinct_secondary",
                "suppressed_titles",
                "kept_secondary_titles",
                "item_debug",
                "_guidance_item_coverage_tuple",
                "_guidance_items_materially_overlap",
                "_guidance_update_map",
            )
        ),
        "module_keeps_collapse_contract_surface": all(
            token in module_collapse_body
            for token in (
                "no_items",
                "no_actionable_primary",
                "primary_compound_candidate_covers_all_failures",
                "primary_not_comprehensive_compound_candidate",
                "covers_all_current_failures",
                "resolved_candidate_subfamilies",
                "compound_shear_augmented",
                "covered_fail_keys",
                "remaining_fail_keys",
                "state_fp",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import guidance_item_consolidation as extracted
    from inputs_page_modules.design_guide.item_identity import _guidance_item_family as extracted_family

    original = bridge._consolidate_guidance_items_by_family_extracted
    original_collapse = bridge._collapse_to_single_primary_guidance_item_extracted
    call_record: dict = {}
    collapse_call_record: dict = {}

    def _fake_extracted(guidance_items: list[dict]) -> tuple[list[dict], dict]:
        call_record.update(
            {
                "items": list(guidance_items),
                "bound_family": getattr(extracted, "_guidance_item_family", None)
                is bridge._guidance_item_family_extracted,
                "family_not_bridge_wrapper": getattr(extracted, "_guidance_item_family", None)
                is not bridge._guidance_item_family,
                "bound_coverage": getattr(extracted, "_guidance_item_coverage_tuple", None)
                is bridge._guidance_item_coverage_tuple,
                "bound_overlap": getattr(extracted, "_guidance_items_materially_overlap", None)
                is bridge._guidance_items_materially_overlap,
                "bound_update_map": getattr(extracted, "_guidance_update_map", None)
                is bridge._guidance_update_map,
            }
        )
        return list(guidance_items), {"reason": "fake"}

    def _fake_collapse(guidance_items: list[dict], state: dict) -> tuple[list[dict], dict]:
        collapse_call_record.update(
            {
                "items": list(guidance_items),
                "state": dict(state),
                "bound_first_actionable": getattr(extracted, "_first_actionable_guidance_item", None)
                is bridge._first_actionable_guidance_item,
                "bound_candidate_cache_key": getattr(extracted, "_candidate_cache_key", None)
                is bridge._candidate_cache_key,
            }
        )
        return list(guidance_items), {"reason": "fake_collapse"}

    try:
        bridge._consolidate_guidance_items_by_family_extracted = _fake_extracted
        bridge._collapse_to_single_primary_guidance_item_extracted = _fake_collapse
        returned = bridge._consolidate_guidance_items_by_family([{"title_main": "A"}])
        collapse_returned = bridge._collapse_to_single_primary_guidance_item(
            [{"title_main": "A"}],
            {"D": 650},
        )
    finally:
        bridge._consolidate_guidance_items_by_family_extracted = original
        bridge._collapse_to_single_primary_guidance_item_extracted = original_collapse

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_guidance_item_family", None) is bridge._guidance_item_family_extracted
        and getattr(extracted, "_guidance_item_family", None) is extracted_family
        and getattr(extracted, "_guidance_item_family", None) is not bridge._guidance_item_family
        and getattr(extracted, "_guidance_item_coverage_tuple", None)
        is bridge._guidance_item_coverage_tuple
        and getattr(extracted, "_guidance_items_materially_overlap", None)
        is bridge._guidance_items_materially_overlap
        and getattr(extracted, "_guidance_update_map", None)
        is bridge._guidance_update_map
        and getattr(extracted, "_first_actionable_guidance_item", None)
        is bridge._first_actionable_guidance_item
        and getattr(extracted, "_candidate_cache_key", None)
        is bridge._candidate_cache_key
        and getattr(extracted, "_guidance_item_is_same_problem_wrapper", None)
        is bridge._guidance_item_is_same_problem_wrapper_extracted
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == ([{"title_main": "A"}], {"reason": "fake"})
        and call_record.get("items") == [{"title_main": "A"}]
        and call_record.get("bound_family") is True
        and call_record.get("family_not_bridge_wrapper") is True
        and call_record.get("bound_coverage") is True
        and call_record.get("bound_overlap") is True
        and call_record.get("bound_update_map") is True
    )
    checks["bridge_collapse_runtime_delegates_with_arguments"] = (
        collapse_returned == ([{"title_main": "A"}], {"reason": "fake_collapse"})
        and collapse_call_record.get("items") == [{"title_main": "A"}]
        and collapse_call_record.get("state") == {"D": 650}
        and collapse_call_record.get("bound_first_actionable") is True
        and collapse_call_record.get("bound_candidate_cache_key") is True
    )

    extracted.bind_guidance_item_consolidation_dependencies(
        {
            "_first_actionable_guidance_item": lambda items: next(
                (item for item in items if isinstance(item, dict) and item.get("action_type")),
                None,
            ),
            "_candidate_cache_key": lambda state: f"D={state.get('D')}",
            "_guidance_item_coverage_tuple": lambda item: tuple(item.get("coverage") or ()),
            "_guidance_items_materially_overlap": lambda a, b: False,
            "_guidance_update_map": lambda item: dict(item.get("updates") or {}),
        }
    )
    compound_item = {
        "title_main": "Compound",
        "action_type": "apply_resolved_candidate",
        "covers_all_current_failures": True,
        "subfamilies": ["bending", "shear"],
        "compound_shear_augmented": True,
        "action_payload": {
            "failure_coverage": {
                "covers_all_current_failures": True,
                "covered_fail_keys": ["bending", "shear"],
                "remaining_fail_keys": [],
            }
        },
    }
    collapsed_items, collapsed_meta = extracted._collapse_to_single_primary_guidance_item(
        [compound_item, {"title_main": "Secondary", "action_type": "increase_depth"}],
        {"D": 650},
    )
    uncollapsed_items, uncollapsed_meta = extracted._collapse_to_single_primary_guidance_item(
        [
            {
                "title_main": "Single",
                "action_type": "apply_resolved_candidate",
                "subfamilies": ["bending"],
                "action_payload": {
                    "failure_coverage": {
                        "covered_fail_keys": ["bending"],
                        "remaining_fail_keys": ["shear"],
                    }
                },
            }
        ],
        {"D": 700},
    )
    checks["module_collapse_runtime_cases"] = (
        collapsed_items == [compound_item]
        and collapsed_meta.get("collapsed") is True
        and collapsed_meta.get("reason") == "primary_compound_candidate_covers_all_failures"
        and collapsed_meta.get("covered_fail_keys") == ["bending", "shear"]
        and collapsed_meta.get("compound_shear_augmented") is True
        and collapsed_meta.get("state_fp") == "D=650"
        and uncollapsed_items[0].get("title_main") == "Single"
        and uncollapsed_meta.get("collapsed") is False
        and uncollapsed_meta.get("reason") == "primary_not_comprehensive_compound_candidate"
        and uncollapsed_meta.get("remaining_fail_keys") == ["shear"]
        and uncollapsed_meta.get("state_fp") == "D=700"
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "bridge_same_problem_wrapper_lines": (
            (bridge_same_problem_node.end_lineno or bridge_same_problem_node.lineno)
            - bridge_same_problem_node.lineno
            + 1
        ),
        "bridge_collapse_wrapper_lines": (
            (bridge_collapse_node.end_lineno or bridge_collapse_node.lineno)
            - bridge_collapse_node.lineno
            + 1
        ),
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
        "module_same_problem_wrapper_lines": (
            (module_same_problem_node.end_lineno or module_same_problem_node.lineno)
            - module_same_problem_node.lineno
            + 1
        ),
        "module_collapse_function_lines": (
            (module_collapse_node.end_lineno or module_collapse_node.lineno)
            - module_collapse_node.lineno
            + 1
        ),
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_guidance_item_consolidation_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_guidance_item_consolidation_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Guidance Item Consolidation Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Bridge same-problem wrapper lines: {result['bridge_same_problem_wrapper_lines']}",
                f"- Bridge collapse wrapper lines: {result['bridge_collapse_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                f"- Extracted same-problem wrapper lines: {result['module_same_problem_wrapper_lines']}",
                f"- Extracted collapse function lines: {result['module_collapse_function_lines']}",
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
