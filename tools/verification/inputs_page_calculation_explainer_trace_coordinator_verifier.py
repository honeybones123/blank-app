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
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            matches.append(("\n".join(lines[start - 1 : end]), end - start + 1, start, end))
    return matches


def _largest_function_source(source: str, name: str) -> tuple[str, int, int, int]:
    matches = _function_sources(source, name)
    if not matches:
        return "", 0, 0, 0
    return max(matches, key=lambda item: item[1])


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_calculation_explainer_trace_coordinator_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_calculation_explainer_trace_coordinator_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8", errors="ignore")
    pipeline_source_text = (ROOT / "inputs_page_modules" / "summaries" / "pipeline.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    coordinator_source, coordinator_size, coordinator_start, coordinator_end = (
        _largest_function_source(source, "render_inputs_calculation_explainer_trace_coordinator")
    )
    pipeline_source, pipeline_size, _, _ = _largest_function_source(
        pipeline_source_text,
        "render_inputs_summary_pipeline",
    )

    failures: list[str] = []
    if not coordinator_source:
        failures.append("calculation_explainer_trace_coordinator_missing")
    if coordinator_size > 90:
        failures.append(f"calculation_explainer_trace_coordinator_too_large:{coordinator_size}")

    for required in [
        '"calculation_explainer_view_model_trace_attempted": True',
        '"calculation_explainer_view_model_trace_source": "inputs_page_modules.calculations"',
        '"temporary_wrapper_classification": "THIN_WRAPPER_KEEP_TEMPORARILY"',
        "build_inputs_calculation_explainer_source_snapshot(",
        "build_inputs_calculation_explainer_view_model(",
        "build_inputs_calculation_explainer_source_hash(",
        '"_inputs_calculation_explainer_view_model_trace"',
        "trace_fn(",
        '"inputs_calculation_explainer_view_model_trace"',
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    for required in [
        "calculation_explainer_trace_fn(",
        "BENDING_ROWS=BENDING_ROWS",
        "SHEAR_ROWS=SHEAR_ROWS",
        "CRACK_ROWS=CRACK_ROWS",
        "DEFLECTION_ROWS=DEFLECTION_ROWS",
        "results_version=results_version",
        "summary_action_fp=summary_action_fp",
        "trace_fn=pre_widget_trace_fn",
    ]:
        if required not in pipeline_source:
            failures.append(f"summary_pipeline_call_missing_{required}")

    for stale in [
        "build_inputs_calculation_explainer_source_snapshot(",
        "build_inputs_calculation_explainer_view_model(",
        "build_inputs_calculation_explainer_source_hash(",
        '"_inputs_calculation_explainer_view_model_trace"',
        '"calculation_explainer_view_model_trace_attempted": True',
    ]:
        if stale in pipeline_source:
            failures.append(f"summary_pipeline_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_calculation_explainer_trace_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "coordinator_lines": [coordinator_start, coordinator_end],
        "summary_pipeline_size": pipeline_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Calculation Explainer Trace Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"`render_inputs_summary_pipeline_current_coordinator` size: `{pipeline_size}`",
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
