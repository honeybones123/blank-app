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
    json_path = ARTIFACT_DIR / f"inputs_page_live_shell_composition_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_live_shell_composition_current_{timestamp}.md"
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
    summary_module_source = (
        ROOT / "inputs_page_modules" / "summaries" / "pipeline.py"
    ).read_text(encoding="utf-8", errors="ignore")
    tail_module_source = (ROOT / "inputs_page_modules" / "tail.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    render_inputs_source, render_inputs_size = _function_source(shell_source, "render_inputs_page")
    old_render_inputs_source, old_render_inputs_size = _function_source(shell_source, "render_inputs")
    setup_source, setup_size = _function_source(route_source, "render_inputs_page_setup_current_coordinator")
    widget_source, widget_size = _function_source(widget_module_source, "render_inputs_widget_sections")
    summary_source, summary_size = _function_source(summary_module_source, "render_inputs_summary_pipeline")
    tail_source, tail_size = _function_source(tail_module_source, "render_inputs_tail")

    failures: list[str] = []
    if old_render_inputs_size:
        failures.append(f"old_render_inputs_still_present:{old_render_inputs_size}")
    if render_inputs_size > 55:
        failures.append(f"shell_render_inputs_page_too_large:{render_inputs_size}")

    expected_calls = [
        "render_inputs_page_setup_current_coordinator(ss=ss)",
        "render_inputs_widget_sections_current_coordinator(",
        "render_inputs_summary_pipeline_current_coordinator(",
        "render_inputs_tail_current_coordinator(",
    ]
    for call in expected_calls:
        if call not in render_inputs_source:
            failures.append(f"shell_render_inputs_page_missing_{call}")

    call_positions = [render_inputs_source.find(call) for call in expected_calls]
    if not all(pos >= 0 for pos in call_positions) or call_positions != sorted(call_positions):
        failures.append(f"shell_render_inputs_page_call_order_changed:{call_positions}")

    forbidden_page_ownership = [
        "render_inputs_initial_session_state_coordinator(",
        "render_inputs_param_snapshot_coordinator(",
        "render_inputs_top_section_layout_slots_coordinator(",
        "render_inputs_post_widget_autopersist_current_coordinator(",
        "render_inputs_summary_state_cache_current_coordinator(",
        "render_inputs_post_summary_actions_and_dev_audit_current_coordinator(",
        "_render_design_guide_debug_sidebar()",
        "render_inputs_perf_finalization_current_coordinator(",
    ]
    for forbidden in forbidden_page_ownership:
        if forbidden in render_inputs_source:
            failures.append(f"shell_render_inputs_page_still_owns_{forbidden}")

    required_setup = [
        "render_inputs_initial_session_state_coordinator(ss=ss)",
        'inputs_hydration_trace_log("render_inputs_entry"',
        "PARAMS, fast_get_param = render_inputs_param_snapshot_coordinator()",
        "render_inputs_perf_marker_setup_coordinator(ss=ss)",
        "render_inputs_batch_design_manager_coordinator(",
        "render_inputs_design_mode_selector_coordinator(",
        '"summary_container": summary_container',
    ]
    for required in required_setup:
        if required not in setup_source:
            failures.append(f"setup_missing_{required}")

    required_widget = [
        "top_section_layout_slots_fn(",
        "design_actions_section_fn(",
        "geometry_materials_top_section_fn(",
        "bottom_reinforcement_column_fn(",
        "top_reinforcement_column_fn(",
        "shear_reinforcement_column_fn(",
        "flange_reinforcement_fn(",
        "detailed_support_lower_row_fn(",
        "return post_widget_autopersist_fn(ss=ss)",
    ]
    for required in required_widget:
        if required not in widget_source:
            failures.append(f"widget_sections_missing_{required}")

    required_summary = [
        "summary_state_cache_fn(ss=ss, mark=mark)",
        "summary_container_fn(",
        'mark("render_summary")',
    ]
    for required in required_summary:
        if required not in summary_source:
            failures.append(f"summary_pipeline_missing_{required}")

    required_tail = [
        "post_summary_actions_fn(",
        "debug_audit_fn(before_state=before_state)",
        "design_guide_debug_sidebar_fn()",
        'mark("end")',
        "perf_finalization_fn(",
    ]
    for required in required_tail:
        if required not in tail_source:
            failures.append(f"tail_missing_{required}")

    payload = {
        "verifier": "inputs_page_live_shell_composition_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "shell_render_inputs_page_size": render_inputs_size,
        "old_render_inputs_size": old_render_inputs_size,
        "setup_size": setup_size,
        "widget_sections_size": widget_size,
        "summary_pipeline_size": summary_size,
        "tail_size": tail_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Live Shell Composition Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Render inputs size: `{render_inputs_size}`",
                f"Setup coordinator size: `{setup_size}`",
                f"Widget sections coordinator size: `{widget_size}`",
                f"Summary pipeline coordinator size: `{summary_size}`",
                f"Tail coordinator size: `{tail_size}`",
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
