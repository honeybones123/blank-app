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
    json_path = ARTIFACT_DIR / f"inputs_page_summary_container_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_summary_container_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (
        ROOT / "inputs_application" / "page_runtime" / "summaries.py"
    ).read_text(encoding="utf-8", errors="ignore")
    summary_module_source = (
        ROOT / "inputs_page_modules" / "summaries" / "render_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    summary_pipeline_module_source = (
        ROOT / "inputs_page_modules" / "summaries" / "pipeline.py"
    ).read_text(encoding="utf-8", errors="ignore")
    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    workspace_source = (
        ROOT / "inputs_application" / "engineering_workspace.py"
    ).read_text(encoding="utf-8", errors="ignore")
    tail_runtime_source = (
        ROOT / "inputs_application" / "page_runtime" / "tail.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_summary_container_current_coordinator",
    )
    module_owner_source, module_owner_size = _function_source(
        summary_module_source,
        "render_inputs_summary_container_current",
    )
    render_inputs_source, render_inputs_size = _function_source(shell_source, "render_inputs_page")
    route_summary_pipeline_source, _ = _function_source(
        source,
        "render_inputs_summary_pipeline_current_coordinator",
    )
    summary_pipeline_source, _ = _function_source(
        summary_pipeline_module_source,
        "render_inputs_summary_pipeline",
    )
    tail_source, _ = _function_source(
        tail_runtime_source,
        "render_inputs_tail_current_coordinator",
    )
    workspace_render_source, _ = _function_source(
        workspace_source,
        "render_engineering_workspace",
    )
    summary_owner_source = summary_pipeline_source or route_summary_pipeline_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("summary_container_coordinator_missing")
    if not module_owner_source:
        failures.append("summary_container_module_owner_missing")
    if coordinator_size > 80:
        failures.append(f"summary_container_coordinator_too_large:{coordinator_size}")
    if module_owner_size > 110:
        failures.append(f"summary_container_module_owner_too_large:{module_owner_size}")

    for required in [
        "payload = dict(locals())",
        '"st_module": st',
        '"result_cache_key": RESULT_CACHE_KEY',
        '"inputs_show_landing_dashboard_fn": inputs_show_landing_dashboard',
        '"render_landing_card_fn": render_landing_card',
        '"render_summary_expanders_and_tables_fn": render_inputs_summary_expanders_and_tables_current_coordinator',
        "render_inputs_summary_container_current_module(**payload)",
    ]:
        if required not in coordinator_source:
            failures.append(f"route_wrapper_missing_{required}")

    for required in [
        "def render_summary_table(results):",
        "_ = results",
        "render_summary_expanders_and_tables_fn(",
        "with summary_container:",
        'st_module.title("Inputs")',
        "show_landing = inputs_show_landing_dashboard_fn()",
        "render_landing_card_fn(sync_callbacks=sync_callbacks, st_module=st_module)",
        "render_summary_table(st_module.session_state.get(result_cache_key))",
    ]:
        if required not in module_owner_source:
            failures.append(f"module_owner_missing_{required}")

    call_text = "summary_container_fn("
    if call_text not in summary_owner_source:
        failures.append("render_inputs_missing_summary_container_call")
    if "summary_container_fn=render_inputs_summary_container_current_coordinator" not in route_summary_pipeline_source:
        failures.append("route_summary_pipeline_missing_container_wrapper_injection")

    for stale in [
        "def render_summary_table(results):",
        "with summary_container:",
        'st.title("Inputs")',
        "show_landing = inputs_show_landing_dashboard()",
        "render_landing_card(sync_callbacks=sync_callbacks)",
        "render_summary_table(st.session_state.get(RESULT_CACHE_KEY))",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")
        if stale in coordinator_source:
            failures.append(f"route_wrapper_still_owns_{stale}")

    finalization_index = summary_owner_source.find("summary_row_finalization_fn(")
    container_index = summary_owner_source.find(call_text)
    mark_index = summary_owner_source.find('mark("render_summary")')
    tail_index = render_inputs_source.find("_INPUTS_PAGE_RUNTIME.render_tail(")
    scroll_index = tail_source.find("render_inputs_post_summary_actions_and_dev_audit_current_coordinator(")
    summary_pipeline_index = workspace_render_source.find(
        "render_inputs_summary_fragment_section"
    )
    workspace_index = render_inputs_source.find(
        "_render_engineering_workspace(page_context=page_context)"
    )
    if scroll_index < 0:
        scroll_index = tail_source.find("post_summary_actions_fn=render_inputs_post_summary_actions_and_dev_audit_current_coordinator")
    if not (
        0 <= summary_pipeline_index
        and 0 <= workspace_index < tail_index
        and 0 <= scroll_index
    ):
        failures.append(
            "summary_pipeline_parent_call_order_changed:"
            f"summary_pipeline={summary_pipeline_index}:tail={tail_index}:"
            f"post_summary_actions={scroll_index}"
        )
    if not (0 <= finalization_index < container_index < mark_index):
        failures.append(
            "summary_container_call_order_changed:"
            f"finalization={finalization_index}:container={container_index}:"
            f"mark={mark_index}:post_summary_actions={scroll_index}"
        )

    payload = {
        "verifier": "inputs_page_summary_container_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "module_owner_size": module_owner_size,
        "render_inputs_size": render_inputs_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Summary Container Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Module owner size: `{module_owner_size}`",
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
