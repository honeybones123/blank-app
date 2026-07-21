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
    json_path = ARTIFACT_DIR / f"inputs_page_top_section_layout_slots_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_top_section_layout_slots_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_top_section_layout_slots_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("top_section_layout_slots_coordinator_missing")
    if coordinator_size > 60:
        failures.append(f"top_section_layout_slots_coordinator_too_large:{coordinator_size}")
    for required in [
        'fast_model_render_state = {"rendered": False}',
        "bottom_slot = None",
        "shear_slot = None",
        "model_slot = None",
        "if inputs_detailed_mode:",
        "st.columns([1.15, 1.85], gap=\"large\")",
        "actions_slot = st.container()",
        "geometry_slot = st.container()",
        "st.columns([1.0, 1.5], gap=\"medium\")",
        "model_slot = st.container()",
        "render_inputs_fast_model_into_slot_coordinator(",
        'render_order="inline_with_design_actions"',
        "right_diagram = None",
        "return (",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_inputs_top_section_layout_slots_coordinator(",
        "inputs_detailed_mode=bool(inputs_detailed_mode)",
        "render_trace_started=_render_trace_started",
        "phase5c_render_trace_fn=_phase5c_render_trace",
        "update_user_latency_metrics_fn=_update_user_latency_metrics",
        "sync_callbacks=sync_callbacks",
    ]:
        if required not in render_inputs_source:
            failures.append(f"render_inputs_missing_{required}")
    for stale in [
        "_fast_model_render_state = {\"rendered\": False}",
        "left_inputs, right_diagram = st.columns([1.15, 1.85], gap=\"large\")",
        "fast_left, fast_right = st.columns([1.0, 1.5], gap=\"medium\")",
        'render_order="inline_with_design_actions"',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_top_section_layout_slots_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Top Section Layout Slots Coordinator Verifier",
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
