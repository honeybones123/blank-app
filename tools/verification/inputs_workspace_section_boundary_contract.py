"""Focused structural contract for Inputs workspace section ownership."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "inputs_application" / "engineering_workspace.py"
PAGE_PATH = ROOT / "inputs_page.py"
WIDGETS_PATH = ROOT / "inputs_application" / "page_runtime" / "widgets.py"
SETUP_PATH = ROOT / "inputs_application" / "page_runtime" / "setup.py"


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def main() -> int:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    page_source = PAGE_PATH.read_text(encoding="utf-8")
    widgets_source = WIDGETS_PATH.read_text(encoding="utf-8")
    setup_source = SETUP_PATH.read_text(encoding="utf-8")
    render_source = _function_source(source, "render_engineering_workspace")
    setup_render_source = _function_source(
        setup_source,
        "render_inputs_pre_widget_apply_and_render_setup_coordinator",
    )
    section_names = (
        "prepare_engineering_workspace_transaction",
        "render_inputs_summary_fragment_section",
        "render_inputs_calculation_fragment_section",
        "render_inputs_controls_fragment_section",
        "render_inputs_design_guide_fragment_section",
        "render_inputs_widget_fragment_section",
    )
    positions = [render_source.find(name) for name in section_names]
    design_guide_position = render_source.find(
        "render_inputs_design_guide_fragment_section"
    )
    widget_position = render_source.find("render_inputs_widget_fragment_section")
    design_guide_section_source = _function_source(
        source,
        "render_inputs_design_guide_fragment_section",
    )
    input_section_source = _function_source(
        source,
        "render_inputs_widget_fragment_section",
    )
    checks = {
        "all_named_section_boundaries_exist": all(
            _function_source(source, name) for name in section_names
        ),
        "one_authoritative_transaction_boundary": (
            render_source.count("prepare_engineering_workspace_transaction(")
            == 1
        ),
        "workspace_transaction_begins_design_guide_refresh": (
            "DesignGuideFragmentStore(st_module.session_state)"
            in _function_source(
                source,
                "prepare_engineering_workspace_transaction",
            )
            and ".begin_refresh(" in _function_source(
                source,
                "prepare_engineering_workspace_transaction",
            )
            and ".publish(" not in _function_source(
                source,
                "prepare_engineering_workspace_transaction",
            )
        ),
        "design_guide_section_owns_single_replacement_slot": (
            design_guide_section_source.count(
                "design_guide_slot = st_module.empty()"
            )
            == 1
            and "design_guide_slot=design_guide_slot"
            in design_guide_section_source
            and "fragment_state=fragment_state.to_dict()"
            in design_guide_section_source
            and "fragment_store.publish(" in design_guide_section_source
            and "fragment_store.clear()" in design_guide_section_source
        ),
        "page_setup_does_not_refresh_authoritative_result": (
            "_ensure_authoritative_design_result_current_coordinator("
            not in setup_render_source
            and "refresh_inputs_authoritative_design_result("
            not in setup_render_source
        ),
        "section_order_is_explicit": (
            all(position >= 0 for position in positions)
            and positions == sorted(positions)
        ),
        "engineering_workspace_is_one_outer_fragment": (
            'fragment_name="engineering_workspace"' in page_source
            and "render_fn=_render_engineering_workspace" in page_source
            and "run_inputs_fragment(" in page_source
        ),
        "coupled_sections_render_inside_workspace": all(
            f"{name}(" in render_source
            for name in (
                "render_inputs_summary_fragment_section",
                "render_inputs_calculation_fragment_section",
                "render_inputs_design_guide_fragment_section",
                "render_inputs_widget_fragment_section",
            )
        )
        and "from inputs_page_modules.fragments import run_inputs_fragment" not in source
        and "run_inputs_fragment(" not in render_source,
        "design_guide_remains_above_widgets": (
            design_guide_position >= 0
            and widget_position >= 0
            and design_guide_position < widget_position
        ),
        "engineering_input_fragment_has_no_app_scope_promotion": (
            "workspace_revision > authoritative_revision" not in input_section_source
            and 'st_module.rerun(scope="app")' not in input_section_source
        ),
        "diagram_plot_keeps_local_fragment_boundary": (
            "from inputs_application.diagram_fragments import run_inputs_diagram_fragment"
            in widgets_source
            and "run_inputs_diagram_fragment(" in widgets_source
        ),
        "summary_reads_transaction_before_design_guide": (
            positions[0] < positions[1] < positions[4]
        ),
        "legacy_monolithic_direct_calls_absent": not any(
            token in render_source
            for token in (
                "runtime.render_summary(",
                "runtime.render_design_guide(",
                "runtime.render_widgets(",
            )
        ),
    }
    payload = {
        "schema": "inputs_workspace_section_boundary_contract.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
