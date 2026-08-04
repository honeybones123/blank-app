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
    json_path = ARTIFACT_DIR / f"inputs_page_flange_reinforcement_section_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_flange_reinforcement_section_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size, coordinator_start, coordinator_end = (
        _largest_function_source(source, "render_inputs_flange_reinforcement_section_coordinator")
    )
    render_inputs_source, render_inputs_size, _, _ = _largest_function_source(
        source,
        "render_inputs",
    )

    failures: list[str] = []
    if not coordinator_source:
        failures.append("flange_reinforcement_section_coordinator_missing")
    if coordinator_size > 290:
        failures.append(f"flange_reinforcement_section_coordinator_too_large:{coordinator_size}")

    for required in [
        'sec_shape_for_flange in ("T", "I")',
        '"### Flange reinforcement"',
        "Only used for T and I sections",
        '"Enable top flange bars"',
        '"Mirror top left/right"',
        '"Enable bottom flange bars"',
        '"Mirror bottom left/right"',
        '"Enable top flange transverse"',
        '"Enable bottom flange transverse"',
        "build_flange_reinforcement_basic_widget_payloads(",
        "build_flange_transverse_basic_widget_payloads(",
        "build_inputs_widget_group_view_model(",
        '"flange_reinforcement_basic"',
        '"flange_transverse_basic"',
        '"flange_reinforcement_basic_widget_metadata_hash"',
        '"flange_transverse_basic_widget_metadata_hash"',
        "trace_fn(",
        '"inputs_widget_metadata_trace"',
        "phase5c_render_trace_fn(",
        '"flange_reinforcement_render_complete"',
        'sub_mark_fn("reinforcement")',
        "page_divider()",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    for forbidden in [
        "_phase5c_render_trace(",
        "_inputs_pre_widget_trace(",
        "_sub_mark(",
        "fast_get_param(",
        "_phase5c_flange_started",
        "_flange_widget_metadata_trace",
        "_flange_widget_payloads",
        "_flange_transverse_payloads",
        "_flange_group_vm",
        "_flange_transverse_group_vm",
    ]:
        if forbidden in coordinator_source:
            failures.append(f"coordinator_retains_render_inputs_local_{forbidden}")

    for required in [
        "render_inputs_flange_reinforcement_section_coordinator(",
        "sync_callbacks=sync_callbacks",
        "phase5c_render_trace_fn=_phase5c_render_trace",
        "trace_fn=_inputs_pre_widget_trace",
        "sub_mark_fn=_sub_mark",
        "fast_get_param_fn=fast_get_param",
        "if inputs_detailed_mode:",
    ]:
        if required not in render_inputs_source:
            failures.append(f"render_inputs_call_missing_{required}")

    for stale in [
        '"### Flange reinforcement"',
        '"Enable top flange bars"',
        '"Enable bottom flange bars"',
        '"Enable top flange transverse"',
        "build_flange_reinforcement_basic_widget_payloads(",
        "build_flange_transverse_basic_widget_payloads(",
        '"flange_reinforcement_render_complete"',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_flange_reinforcement_section_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "coordinator_lines": [coordinator_start, coordinator_end],
        "render_inputs_size": render_inputs_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Flange Reinforcement Section Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
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
