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
    json_path = ARTIFACT_DIR / f"inputs_page_summary_expanders_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_summary_expanders_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page_modules" / "summaries" / "render_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    route_source = (
        ROOT / "inputs_application" / "page_runtime" / "summaries.py"
    ).read_text(
        encoding="utf-8",
        errors="ignore",
    )
    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    pipeline_module_source = (
        ROOT / "inputs_page_modules" / "summaries" / "pipeline.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_summary_expanders_and_tables_current_coordinator",
    )
    container_source, container_size = _function_source(
        source,
        "render_inputs_summary_container_current",
    )
    runtime_container_source, _ = _function_source(
        route_source,
        "render_inputs_summary_container_current_coordinator",
    )
    render_inputs_source, render_inputs_size = _function_source(shell_source, "render_inputs_page")
    summary_pipeline_source, _ = _function_source(
        pipeline_module_source,
        "render_inputs_summary_pipeline",
    )
    summary_owner_source = summary_pipeline_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("summary_expanders_coordinator_missing")
    if coordinator_size > 140:
        failures.append(f"summary_expanders_coordinator_too_large:{coordinator_size}")

    for required in [
        "inject_seamless_steps_css()",
        "Bending results not available yet. Check inputs or visit Bending page for details.",
        "Shear results not available yet. Check inputs or visit Shear page for details.",
        "Crack results not available yet. Check inputs or visit Crack Control page for details.",
        "Deflection results not available yet. Check inputs or visit Deflection page for details.",
        "shear_governing_source == \"sectional_shear_capacity\"",
        "Governing check:",
        "Reason:",
        "InputsSummarySourceSnapshot(",
        "InputsSummaryCardSource(",
        "summary_cards_html = _build_summary_cards_html_for_current_state(",
        "st.markdown(summary_cards_html, unsafe_allow_html=True)",
        "page_divider()",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "render_summary_expanders_and_tables_fn("
    if call_text not in container_source:
        failures.append("summary_container_missing_summary_expanders_call")
    if (
        '"render_summary_expanders_and_tables_fn": '
        "render_inputs_summary_expanders_and_tables_current_coordinator"
        not in runtime_container_source
    ):
        failures.append("runtime_container_missing_expanders_injection")

    for stale in [
        "def _render_inputs_summary_expanders_and_tables()",
        ".inputs-top-level-row",
        ".summary-table",
        "bending_table_html = _generate_summary_table_html(BENDING_ROWS)",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    finalization_index = summary_owner_source.find(
        "summary_row_finalization_fn("
    )
    summary_table_def_index = container_source.find("def render_summary_table(results):")
    call_index = container_source.find(call_text)
    with_summary_index = container_source.find("with summary_container:")
    render_summary_call_index = container_source.find(
        "render_summary_table(st_module.session_state.get(result_cache_key))"
    )
    container_call_index = summary_owner_source.find("summary_container_fn(")
    mark_index = summary_owner_source.find('mark("render_summary")')
    if not (0 <= finalization_index < container_call_index < mark_index):
        failures.append(
            "summary_expanders_container_call_order_changed:"
            f"finalization={finalization_index}:container_call={container_call_index}:mark={mark_index}"
        )
    if not (0 <= summary_table_def_index < call_index < with_summary_index < render_summary_call_index):
        failures.append(
            "summary_expanders_call_order_changed:"
            f"finalization={finalization_index}:summary_table_def={summary_table_def_index}:"
            f"call={call_index}:with_summary={with_summary_index}:"
            f"render_summary_call={render_summary_call_index}:container_size={container_size}"
        )

    payload = {
        "verifier": "inputs_page_summary_expanders_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "render_inputs_size": render_inputs_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Summary Expanders Current Verifier",
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
