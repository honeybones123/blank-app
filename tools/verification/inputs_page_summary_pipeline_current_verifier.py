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
    json_path = ARTIFACT_DIR / f"inputs_page_summary_pipeline_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_summary_pipeline_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (
        ROOT / "inputs_application" / "page_runtime" / "summaries.py"
    ).read_text(encoding="utf-8", errors="ignore")
    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    pipeline_module_source = (ROOT / "inputs_page_modules" / "summaries" / "pipeline.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    widget_module_source = (ROOT / "inputs_page_modules" / "widgets" / "render_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    workspace_source = (
        ROOT / "inputs_application" / "engineering_workspace.py"
    ).read_text(encoding="utf-8", errors="ignore")
    workspace_render_source, _ = _function_source(
        workspace_source,
        "render_engineering_workspace",
    )
    coordinator_source, coordinator_size = _function_source(
        pipeline_module_source,
        "render_inputs_summary_pipeline",
    )
    route_pipeline_source, _ = _function_source(source, "render_inputs_summary_pipeline_current_coordinator")
    render_inputs_source, render_inputs_size = _function_source(shell_source, "render_inputs_page")
    widget_sections_source, _ = _function_source(widget_module_source, "render_inputs_widget_sections")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("summary_pipeline_coordinator_missing")
    if coordinator_size > 175:
        failures.append(f"summary_pipeline_coordinator_too_large:{coordinator_size}")
    if render_inputs_size > 220:
        failures.append(f"render_inputs_not_reduced:{render_inputs_size}")

    required_in_coordinator = [
        "summary_state_cache_fn(ss=ss, mark=mark)",
        'hc_log_fn(\n        "summary.pack_meta"',
        'hc_log_fn(\n        "state.snapshot"',
        "summary_rows_from_packs_fn(",
        "summary_display_state_fn(",
        "summary_guidance_cache_fn(",
        "summary_row_finalization_fn(",
        "summary_container_fn(",
        'mark("render_summary")',
    ]
    for required in required_in_coordinator:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "render_inputs_summary_fragment_section"
    if workspace_render_source.count(call_text) != 1:
        failures.append(
            "workspace_summary_fragment_call_count:"
            f"{workspace_render_source.count(call_text)}"
        )
    if "render_inputs_summary_pipeline_module(" not in route_pipeline_source:
        failures.append("route_summary_pipeline_missing_module_delegate")

    stale_in_render_inputs = [
        "render_inputs_summary_state_cache_current_coordinator(ss=ss, mark=_mark)",
        'hc_log(\n        "summary.pack_meta"',
        'hc_log(\n        "state.snapshot"',
        "render_inputs_summary_rows_from_packs_current_coordinator(",
        "render_inputs_summary_display_state_current_coordinator(",
        "render_inputs_summary_guidance_cache_current_coordinator(",
        "render_inputs_summary_row_finalization_current_coordinator(",
        "render_inputs_summary_container_current_coordinator(",
        '_mark("render_summary")',
    ]
    for stale in stale_in_render_inputs:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    autopersist_index = widget_sections_source.find("post_widget_autopersist_fn(ss=ss)")
    widget_sections_index = workspace_render_source.find(
        "render_inputs_widget_fragment_section"
    )
    summary_pipeline_index = workspace_render_source.find(call_text)
    post_summary_index = render_inputs_source.find(
        "_render_engineering_workspace(page_context=page_context)"
    )
    tail_index = render_inputs_source.find(
        "_INPUTS_PAGE_RUNTIME.render_tail("
    )
    if not (0 <= autopersist_index):
        failures.append(f"summary_pipeline_missing_widget_autopersist:autopersist={autopersist_index}")
    if not (
        0 <= summary_pipeline_index < widget_sections_index
        and 0 <= post_summary_index < tail_index
    ):
        failures.append(
            "summary_pipeline_call_order_changed:"
            f"autopersist={autopersist_index}:summary_pipeline={summary_pipeline_index}:"
            f"post_summary={post_summary_index}:tail={tail_index}"
        )

    payload = {
        "verifier": "inputs_page_summary_pipeline_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "render_inputs_size": render_inputs_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Summary Pipeline Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
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
