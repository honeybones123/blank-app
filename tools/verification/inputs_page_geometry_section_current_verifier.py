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
    json_path = ARTIFACT_DIR / f"inputs_page_geometry_section_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_geometry_section_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_geometry_section_current_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("geometry_section_current_coordinator_missing")
    if coordinator_size > 115:
        failures.append(f"geometry_section_current_coordinator_too_large:{coordinator_size}")

    for required in [
        "Geometry & Materials",
        "Geometry",
        "inputs_apply_geometry_recommendation",
        "fast_mode:geometry_recommendation",
        "detailed_mode:geometry_recommendation",
        "shape_options = [\"RECT\", \"T\", \"I\"]",
        "inputs_sec_shape",
        "Section shape",
        "inputs_D",
        "inputs_L",
        "inputs_cover_side",
        "inputs_b",
        "inputs_bf",
        "inputs_tf",
        "inputs_bw",
        "inputs_tw",
        "Width b (mm)",
        "Flange width bf (mm)",
        "Top flange width bf (mm)",
        "_render_inputs_materials_subsection(sync_callbacks, show_heading=False)",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "render_inputs_geometry_section_current_coordinator("
    if call_text not in render_inputs_source:
        failures.append("render_inputs_missing_geometry_section_call")

    for stale in [
        "Geometry & Materials",
        "inputs_apply_geometry_recommendation",
        "Section shape",
        "Width b (mm)",
        "Flange width bf (mm)",
        "Top flange width bf (mm)",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    actions_mark_index = render_inputs_source.find('_sub_mark("design_actions")')
    geometry_call_index = render_inputs_source.find(call_text)
    geometry_mark_index = render_inputs_source.find('_sub_mark("geometry")')
    top_inputs_index = render_inputs_source.find('_mark("top_inputs_widgets")')
    if not (0 <= actions_mark_index < geometry_call_index < geometry_mark_index < top_inputs_index):
        failures.append(
            "geometry_call_order_changed:"
            f"actions={actions_mark_index}:geometry_call={geometry_call_index}:"
            f"geometry_mark={geometry_mark_index}:top_inputs={top_inputs_index}"
        )

    payload = {
        "verifier": "inputs_page_geometry_section_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Geometry Section Current Verifier",
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
