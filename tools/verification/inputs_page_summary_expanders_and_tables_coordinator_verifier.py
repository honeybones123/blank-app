from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_sources(source: str, name: str) -> list[tuple[str, int, int, int]]:
    tree = ast.parse(source)
    lines = source.splitlines()
    matches: list[tuple[str, int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            size = int(node.end_lineno or node.lineno) - int(node.lineno) + 1
            matches.append(
                (
                    "\n".join(lines[int(node.lineno) - 1 : int(node.end_lineno)]),
                    size,
                    int(node.lineno),
                    int(node.end_lineno),
                )
            )
    return matches


def _largest_function_source(source: str, name: str) -> tuple[str, int, int, int]:
    matches = _function_sources(source, name)
    if not matches:
        return "", 0, 0, 0
    return max(matches, key=lambda item: item[1])


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_summary_expanders_and_tables_coordinator_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_summary_expanders_and_tables_coordinator_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size, coordinator_start, coordinator_end = (
        _largest_function_source(
            source,
            "render_inputs_summary_expanders_and_tables_coordinator",
        )
    )
    render_inputs_source, render_inputs_size, _, _ = _largest_function_source(
        source,
        "render_inputs",
    )
    wrapper_matches = _function_sources(source, "_render_inputs_summary_expanders_and_tables")
    wrapper_source, wrapper_size, wrapper_start, wrapper_end = (
        max(wrapper_matches, key=lambda item: item[1]) if wrapper_matches else ("", 0, 0, 0)
    )

    failures: list[str] = []
    if not coordinator_source:
        failures.append("summary_expanders_and_tables_coordinator_missing")
    if coordinator_size > 290:
        failures.append(f"summary_expanders_and_tables_coordinator_too_large:{coordinator_size}")
    if not wrapper_source:
        failures.append("summary_expanders_and_tables_wrapper_missing")
    if wrapper_size > 40:
        failures.append(f"summary_expanders_and_tables_wrapper_too_large:{wrapper_size}")

    for required in [
        "inject_seamless_steps_css()",
        "components.html(",
        "build_inputs_summary_view_model(",
        "build_inputs_summary_html(",
        '"_inputs_summary_extracted_view_model_trace"',
        '"_final_publication_summary_card_html_bypass_debug"',
        '"summary.card_html_build_reuse"',
        "st.markdown(f'<div class=\"summary-card-stack\">{summary_cards_html}</div>'",
        "temporary_wrapper_classification",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    for required in [
        "render_inputs_summary_expanders_and_tables_coordinator(",
        "BENDING_ROWS=BENDING_ROWS",
        "SHEAR_ROWS=SHEAR_ROWS",
        "CRACK_ROWS=CRACK_ROWS",
        "DEFLECTION_ROWS=DEFLECTION_ROWS",
        "shear_summary_status_note=shear_summary_status_note",
        "summary_resolved_actions=summary_resolved_actions",
        "summary_action_fp=summary_action_fp",
    ]:
        if required not in wrapper_source:
            failures.append(f"wrapper_missing_{required}")

    for stale in [
        "build_inputs_summary_view_model(",
        "build_inputs_summary_html(",
        '"_inputs_summary_extracted_view_model_trace"',
        '"_final_publication_summary_card_html_bypass_debug"',
        '"summary.card_html_build_reuse"',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    if "<script>\n(function() {\n  const doc = window.parent.document;" not in coordinator_source:
        failures.append("summary_route_link_script_indent_drift")

    payload = {
        "verifier": "inputs_page_summary_expanders_and_tables_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "coordinator_lines": [coordinator_start, coordinator_end],
        "render_inputs_size": render_inputs_size,
        "wrapper_size": wrapper_size,
        "wrapper_lines": [wrapper_start, wrapper_end],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Summary Expanders And Tables Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Wrapper size: `{wrapper_size}`",
                f"`render_inputs` size: `{render_inputs_size}`",
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
