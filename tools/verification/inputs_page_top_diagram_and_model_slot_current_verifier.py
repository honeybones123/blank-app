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
    json_path = ARTIFACT_DIR / f"inputs_page_top_diagram_and_model_slot_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_top_diagram_and_model_slot_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_geometry_materials_top_section_current_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs_widget_sections_current_coordinator")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("top_diagram_and_model_slot_current_coordinator_missing")
    if coordinator_size > 200:
        failures.append(f"top_diagram_and_model_slot_current_coordinator_too_large:{coordinator_size}")

    for required in [
        "if inputs_detailed_mode and right_diagram is not None:",
        "inputs-diagram-materials-group",
        "_render_section_2d_diagram_block()",
        "_render_inputs_materials_subsection(sync_callbacks",
        "if inputs_detailed_mode:",
        "_render_fast_model_block(",
        "page_divider()",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "render_inputs_geometry_materials_top_section_current_coordinator("
    if call_text not in render_inputs_source:
        failures.append("widget_sections_missing_top_diagram_and_model_slot_call")

    for stale in [
        "inputs-diagram-materials-group",
        "_render_section_2d_diagram_block()",
        "_render_fast_model_block(",
    ]:
        if stale in render_inputs_source:
            failures.append(f"widget_sections_still_owns_{stale}")

    top_mark_index = coordinator_source.find('mark("top_inputs_widgets")')
    call_index = render_inputs_source.find(call_text)
    materials_mark_index = coordinator_source.find('sub_mark("materials")')
    render_diagrams_mark_index = coordinator_source.find('mark("render_diagrams")')
    if not (0 <= call_index and 0 <= top_mark_index < materials_mark_index < render_diagrams_mark_index):
        failures.append(
            "top_diagram_and_model_slot_call_order_changed:"
            f"top={top_mark_index}:call={call_index}:materials={materials_mark_index}:"
            f"diagrams={render_diagrams_mark_index}"
        )

    payload = {
        "verifier": "inputs_page_top_diagram_and_model_slot_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Top Diagram And Model Slot Current Verifier",
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
