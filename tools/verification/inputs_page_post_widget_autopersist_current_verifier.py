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
    json_path = ARTIFACT_DIR / f"inputs_page_post_widget_autopersist_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_widget_autopersist_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    route_source = (
        ROOT / "inputs_application" / "page_runtime" / "widgets.py"
    ).read_text(encoding="utf-8", errors="ignore")
    summaries_runtime_source = (
        ROOT / "inputs_application" / "page_runtime" / "summaries.py"
    ).read_text(encoding="utf-8", errors="ignore")
    workspace_source = (
        ROOT / "inputs_application" / "engineering_workspace.py"
    ).read_text(encoding="utf-8", errors="ignore")
    workspace_render_source, _ = _function_source(
        workspace_source,
        "render_engineering_workspace",
    )
    coordinator_source, coordinator_size = _function_source(
        route_source,
        "render_inputs_post_widget_autopersist_current_coordinator",
    )
    render_inputs_source, _ = _function_source(shell_source, "render_inputs_page")
    if not render_inputs_source:
        render_inputs_source, _ = _function_source(shell_source, "render_inputs")
    widget_sections_source, _ = _function_source(route_source, "render_inputs_widget_sections_current_coordinator")
    summary_pipeline_source, _ = _function_source(
        summaries_runtime_source,
        "render_inputs_summary_pipeline_current_coordinator",
    )
    widget_owner_source = widget_sections_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("post_widget_autopersist_coordinator_missing")
    if coordinator_size > 18:
        failures.append(f"post_widget_autopersist_coordinator_too_large:{coordinator_size}")

    for required in [
        "_beam_skip_auto_persist_once",
        "inputs_dirty",
        "_apply_canonical_convenience_resync(",
        "source=\"inputs_page:inputs_dirty_autopersist\"",
        "persist_active_beam_from_shared()",
        "return skip_active_beam_record_write",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "post_widget_autopersist_fn=render_inputs_post_widget_autopersist_current_coordinator"
    if call_text not in widget_owner_source:
        failures.append("render_inputs_missing_post_widget_autopersist_call")

    for stale in [
        "_beam_skip_auto_persist_once",
        "_apply_canonical_convenience_resync_to_shared(source=\"inputs_page:inputs_dirty_autopersist\")",
        "_apply_canonical_convenience_resync_to_shared_for_app_bridge(",
        "persist_active_beam_from_shared()",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    detailed_index = widget_owner_source.find("detailed_support_lower_row_fn=render_inputs_detailed_support_lower_row_current_coordinator")
    autopersist_index = widget_owner_source.find(call_text)
    widget_call_index = workspace_render_source.find(
        "render_inputs_widget_fragment_section"
    )
    summary_pipeline_call_index = workspace_render_source.find(
        "render_inputs_summary_fragment_section"
    )
    summary_index = summary_pipeline_source.find("summary_state_cache_fn=render_inputs_summary_state_cache_current_coordinator")
    update_summary_index = summary_pipeline_source.find("summary_row_finalization_fn=render_inputs_summary_row_finalization_current_coordinator")
    if not (0 <= summary_pipeline_call_index < widget_call_index):
        failures.append(
            "post_widget_parent_call_order_changed:"
            f"widget={widget_call_index}:summary_pipeline={summary_pipeline_call_index}"
        )
    if not (0 <= detailed_index < autopersist_index and 0 <= summary_index < update_summary_index):
        failures.append(
            "post_widget_autopersist_call_order_changed:"
            f"detailed={detailed_index}:autopersist={autopersist_index}:summary={summary_index}:update={update_summary_index}"
        )

    payload = {
        "verifier": "inputs_page_post_widget_autopersist_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Widget Autopersist Current Verifier",
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
