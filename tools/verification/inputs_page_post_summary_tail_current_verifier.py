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
    json_path = ARTIFACT_DIR / f"inputs_page_post_summary_tail_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_summary_tail_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (
        ROOT / "inputs_application" / "page_runtime" / "tail.py"
    ).read_text(encoding="utf-8", errors="ignore")
    tail_module_source_text = (ROOT / "inputs_page_modules" / "tail.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    shell_path = ROOT / "inputs_page_shell.py"
    shell_source = (shell_path if shell_path.exists() else ROOT / "inputs_page.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    perf_module_source = (ROOT / "inputs_page_modules" / "performance.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    actions_source, actions_size = _function_source(
        tail_module_source_text,
        "render_inputs_post_summary_actions_and_dev_audit",
    )
    debug_source, debug_size = _function_source(
        tail_module_source_text,
        "render_inputs_debug_audit",
    )
    perf_source, perf_size = _function_source(
        perf_module_source,
        "render_inputs_perf_finalization_current_coordinator",
    )
    render_inputs_source, render_inputs_size = _function_source(shell_source, "render_inputs_page")
    summary_pipeline_source, _ = _function_source(
        _read_text := (
            ROOT / "inputs_page_modules" / "summaries" / "pipeline.py"
        ).read_text(encoding="utf-8", errors="ignore"),
        "render_inputs_summary_pipeline",
    )
    tail_source, tail_size = _function_source(tail_module_source_text, "render_inputs_tail")
    route_tail_source, _ = _function_source(source, "render_inputs_tail_current_coordinator")
    tail_owner_source = tail_source or render_inputs_source

    failures: list[str] = []
    if not actions_source:
        failures.append("post_summary_actions_coordinator_missing")
    if not debug_source:
        failures.append("debug_audit_coordinator_missing")
    if not perf_source:
        failures.append("perf_finalization_coordinator_missing")
    if actions_size > 40:
        failures.append(f"post_summary_actions_coordinator_too_large:{actions_size}")
    if debug_size > 35:
        failures.append(f"debug_audit_coordinator_too_large:{debug_size}")
    if perf_size > 80:
        failures.append(f"perf_finalization_coordinator_too_large:{perf_size}")

    for required in [
        "inject_scroll_to_design_actions_fn()",
        "apply_buttons_fn()",
        "auto_design_fn()",
        "Inputs dev render audit (end of render_inputs)",
        "old_auto_design_panel_rendered",
        "H_INPUTS_DEV_RENDER_AUDIT",
    ]:
        if required not in actions_source:
            failures.append(f"actions_coordinator_missing_{required}")

    for required in [
        "inputs_debug_audit and before_state is not None",
        "after_widgets_state = st_module.session_state",
        "STATE CHANGED DURING RENDER",
        "input_page_tab_keys",
        "shared_defaults",
        "WARNING: DIRECT SHARED WRITE",
        "---- INPUTS PAGE LOAD END ----",
    ]:
        if required not in debug_source:
            failures.append(f"debug_coordinator_missing_{required}")

    for required in [
        "perf_end = time.perf_counter()",
        "for i in range(1, len(perf_marks)):",
        '"section": f"{prev_label} \\u2192 {curr_label}"',
        "for i in range(1, len(sub_marks)):",
        'st.session_state["_perf_log"]',
        "session_state_final_log",
        "inputs_render_perf",
        'st.sidebar.checkbox(',
        '"Show performance debug"',
        'st.sidebar.metric("Inputs render (ms)", perf.get("total_ms", 0))',
        'st.caption(f"Inputs render: {(time.perf_counter() - t0) * 1000:.1f} ms")',
    ]:
        if required not in perf_source:
            failures.append(f"perf_coordinator_missing_{required}")

    for stale in [
        "_inputs_inject_scroll_to_design_actions()",
        "_handle_inputs_apply_buttons_current_coordinator()",
        "_handle_inputs_auto_design_current_coordinator()",
        "Inputs dev render audit (end of render_inputs)",
        "_INPUTS_DEBUG_AUDIT and before_state is not None",
        "STATE CHANGED DURING RENDER",
        "_perf_end = time.perf_counter()",
        "inputs_render_perf",
        "Show performance debug",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    summary_mark_index = summary_pipeline_source.find('mark("render_summary")')
    summary_pipeline_index = render_inputs_source.find(
        "_render_engineering_workspace(page_context=page_context)"
    )
    tail_index = render_inputs_source.find(
        "_INPUTS_PAGE_RUNTIME.render_tail("
    )
    actions_index = tail_owner_source.find("post_summary_actions_fn(")
    debug_index = tail_owner_source.find("debug_audit_fn(")
    design_debug_index = tail_owner_source.find("design_guide_debug_sidebar_fn()")
    end_mark_index = tail_owner_source.find('mark("end")')
    perf_index = tail_owner_source.find("perf_finalization_fn(")
    route_delegates_index = route_tail_source.find("render_inputs_tail_module(")
    if not (0 <= summary_pipeline_index < tail_index):
        failures.append(
            "post_summary_tail_parent_order_changed:"
            f"summary_pipeline={summary_pipeline_index}:tail={tail_index}"
        )
    if route_delegates_index < 0:
        failures.append("route_tail_missing_tail_module_delegate")
    if not (0 <= summary_mark_index and 0 <= actions_index < debug_index < design_debug_index < end_mark_index < perf_index):
        failures.append(
            "post_summary_tail_call_order_changed:"
            f"summary_mark={summary_mark_index}:actions={actions_index}:debug={debug_index}:"
            f"design_debug={design_debug_index}:end_mark={end_mark_index}:perf={perf_index}"
        )

    payload = {
        "verifier": "inputs_page_post_summary_tail_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "actions_size": actions_size,
        "debug_size": debug_size,
        "perf_size": perf_size,
        "tail_size": tail_size,
        "render_inputs_size": render_inputs_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Summary Tail Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Actions coordinator size: `{actions_size}`",
                f"Debug coordinator size: `{debug_size}`",
                f"Perf coordinator size: `{perf_size}`",
                f"Render inputs size: `{render_inputs_size}`",
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

