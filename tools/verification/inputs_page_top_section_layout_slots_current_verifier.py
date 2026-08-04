from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_source(source: str, name: str) -> tuple[str, int]:
    tree = ast.parse(source)
    matches: list[tuple[int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            matches.append((node.end_lineno - node.lineno + 1, node.lineno, node.end_lineno))
    if not matches:
        return "", 0
    size, start, end = max(matches, key=lambda item: item[0])
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end]), size


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_top_section_layout_slots_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_top_section_layout_slots_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (
        ROOT / "inputs_application" / "page_runtime" / "widgets.py"
    ).read_text(encoding="utf-8", errors="ignore")
    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    setup_runtime_source = (
        ROOT / "inputs_application" / "page_runtime" / "setup.py"
    ).read_text(encoding="utf-8", errors="ignore")
    widget_module_source = (
        ROOT / "inputs_page_modules" / "widgets" / "render_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_top_section_layout_slots_coordinator",
    )
    render_inputs_source, _ = _function_source(shell_source, "render_inputs_page")
    setup_source, _ = _function_source(
        setup_runtime_source,
        "render_inputs_page_setup_current_coordinator",
    )
    widget_sections_source, _ = _function_source(
        source,
        "render_inputs_widget_sections_current_coordinator",
    )
    widget_owner_source, _ = _function_source(
        widget_module_source,
        "render_inputs_widget_sections",
    )

    failures: list[str] = []
    if not coordinator_source:
        failures.append("top_section_layout_slots_coordinator_missing")
    if coordinator_size > 45:
        failures.append(f"top_section_layout_slots_coordinator_too_large:{coordinator_size}")
    for required in [
        "bottom_slot = None",
        "shear_slot = None",
        "model_slot = None",
        "if inputs_detailed_mode:",
        "st.columns([1.15, 1.85], gap=\"large\")",
        "st.columns([1.0, 1.5], gap=\"medium\")",
        "actions_slot = st.container()",
        "geometry_slot = st.container()",
        "model_slot = st.container()",
        "right_diagram = None",
        "return bottom_slot, shear_slot, model_slot, actions_slot, geometry_slot, right_diagram",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    if "render_design_guide_panel_orchestration(" in coordinator_source:
        failures.append("layout_slots_still_own_design_guide")

    call_text = "top_section_layout_slots_fn("
    if call_text not in widget_owner_source:
        failures.append("render_inputs_missing_top_section_layout_call")
    if (
        "top_section_layout_slots_fn="
        "render_inputs_top_section_layout_slots_coordinator"
        not in widget_sections_source
    ):
        failures.append("runtime_widget_wrapper_missing_layout_injection")
    for stale in [
        "bottom_slot = None",
        "shear_slot = None",
        "model_slot = None",
        "left_inputs, right_diagram = st.columns([1.15, 1.85], gap=\"large\")",
        "fast_left, fast_right = st.columns([1.0, 1.5], gap=\"medium\")",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    setup_call_index = render_inputs_source.find(
        "_INPUTS_PAGE_RUNTIME.render_page_setup("
    )
    widget_call_index = render_inputs_source.find(
        "_render_engineering_workspace(page_context=page_context)"
    )
    selector_index = coordinator_source.find("if inputs_detailed_mode:")
    call_index = widget_owner_source.find(call_text)
    actions_index = widget_owner_source.find("design_actions_section_fn(")
    if not (0 <= setup_call_index < widget_call_index):
        failures.append(
            "top_section_parent_call_order_changed:"
            f"setup_call={setup_call_index}:widget_call={widget_call_index}"
        )
    if not (0 <= selector_index and 0 <= call_index < actions_index):
        failures.append(
            "top_section_layout_call_order_changed:"
            f"selector={selector_index}:call={call_index}:actions={actions_index}"
        )

    payload = {
        "verifier": "inputs_page_top_section_layout_slots_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Top Section Layout Slots Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
