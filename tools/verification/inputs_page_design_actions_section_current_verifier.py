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
    json_path = ARTIFACT_DIR / f"inputs_page_design_actions_section_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_actions_section_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    widget_module_source = (
        ROOT / "inputs_page_modules" / "widgets" / "render_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        widget_module_source,
        "render_inputs_design_actions_section",
    )
    route_design_actions_source, _ = _function_source(
        route_source,
        "render_inputs_design_actions_section_current_coordinator",
    )
    render_inputs_source, _ = _function_source(shell_source, "render_inputs_page")
    widget_sections_source, _ = _function_source(widget_module_source, "render_inputs_widget_sections")
    widget_owner_source = widget_sections_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("design_actions_section_current_coordinator_missing")
    if coordinator_size > 190:
        failures.append(f"design_actions_section_current_coordinator_too_large:{coordinator_size}")

    for required in [
        "design_actions_anchor_id",
        "## Design Actions",
        "Manual design actions (inputs below)",
        "Teaching SFD/BMD page (|M|max, |V|max)",
        "inputs_use_calculated_actions",
        "itk_calculated_intent",
        "Use calculated design actions",
        "View SLS loads",
        "inputs_loads_edit_toggle",
        "actions_source",
        "actions_mode",
        "loads_edit_mode",
        "commit_design_action_widgets_to_shared_fn(previous_prefix)",
        "mirror_design_action_proxies_from_shared_fn(",
        "_force_design_action_widget_hydrate",
        "Locked: Loads are controlled by the Design page (SFD/BMD). Edit loads there.",
        "hydrate_design_action_widgets_from_shared_fn(",
        "design_action_widget_specs_fn(selected_prefix)",
        "render_design_action_number_row_fn(",
        "reconcile_design_action_widgets_with_shared_fn(selected_prefix)",
        "debug_check_design_action_consistency_fn(shared_state_snapshot_fn())",
        'sub_mark("loads")',
        'sub_mark("design_actions")',
        "st_module.rerun()",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "design_actions_section_fn("
    if call_text not in widget_owner_source:
        failures.append("render_inputs_missing_design_actions_section_call")
    if "render_inputs_design_actions_section_module(" not in route_design_actions_source:
        failures.append("route_design_actions_section_missing_module_delegate")

    for stale in [
        "## Design Actions",
        "inputs_use_calculated_actions",
        "_inputs_use_calculated_actions_user_intent",
        "Use calculated design actions",
        "View SLS loads",
        "_render_design_action_number_row(",
        "_reconcile_design_action_widgets_with_shared(selected_prefix)",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    layout_index = widget_owner_source.find("top_section_layout_slots_fn(")
    actions_index = widget_owner_source.find(call_text)
    geometry_index = widget_owner_source.find("geometry_materials_top_section_fn(")
    if not (0 <= layout_index < actions_index < geometry_index):
        failures.append(
            "design_actions_call_order_changed:"
            f"layout={layout_index}:actions={actions_index}:geometry={geometry_index}"
        )

    payload = {
        "verifier": "inputs_page_design_actions_section_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Actions Section Current Verifier",
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
