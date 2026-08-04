from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _largest_function_source(source: str, name: str) -> tuple[str, int, int, int]:
    tree = ast.parse(source)
    lines = source.splitlines()
    matches: list[tuple[str, int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            matches.append(("\n".join(lines[start - 1 : end]), end - start + 1, start, end))
    if not matches:
        return "", 0, 0, 0
    return max(matches, key=lambda item: item[1])


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_detailed_mode_extra_sections_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_detailed_mode_extra_sections_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    widget_module_source = (
        ROOT / "inputs_page_modules" / "widgets" / "render_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size, coordinator_start, coordinator_end = _largest_function_source(
        widget_module_source,
        "render_inputs_detailed_support_lower_row",
    )
    route_detailed_source, _, _, _ = _largest_function_source(
        route_source,
        "render_inputs_detailed_support_lower_row_current_coordinator",
    )
    widget_sections_source, _, _, _ = _largest_function_source(
        widget_module_source,
        "render_inputs_widget_sections",
    )
    render_inputs_source, render_inputs_size, _, _ = _largest_function_source(
        shell_source,
        "render_inputs_page",
    )

    failures: list[str] = []
    if not coordinator_source:
        failures.append("detailed_mode_extra_sections_coordinator_missing")
    if coordinator_size > 220:
        failures.append(f"detailed_mode_extra_sections_coordinator_too_large:{coordinator_size}")

    for required in [
        "if inputs_detailed_mode:",
        "materials_and_section_2d_fn(sync_callbacks)",
        "page_divider_fn()",
        'sub_mark("shear_torsion")',
        "st_module.columns([1.15, 1.0, 0.85], gap=\"large\")",
        "time_dependent_inputs_fn(sync_callbacks)",
        "ducts_prestress_voids_inputs_fn(sync_callbacks)",
        "st_module.subheader(\"Crack Control Inputs\")",
        "fast_get_param(\"exposure_class\", \"B1\")",
        "key=\"inputs_exposure_class\"",
        "key=\"inputs_crack_member_type\"",
        "key=\"inputs_crack_k1\"",
        "\"inputs_crack_k2\"",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    for required in [
        "detailed_support_lower_row_fn(",
        "inputs_detailed_mode=bool(inputs_detailed_mode)",
        "sync_callbacks=sync_callbacks",
        "fast_get_param=fast_get_param",
        "sub_mark=sub_mark",
    ]:
        if required not in widget_sections_source:
            failures.append(f"widget_sections_call_missing_{required}")
    for required in [
        "render_inputs_detailed_support_lower_row_module(",
        "materials_and_section_2d_fn=_render_materials_and_sectionA_2d",
        "time_dependent_inputs_fn=_render_time_dependent_inputs",
        "ducts_prestress_voids_inputs_fn=_render_ducts_prestress_voids_inputs",
    ]:
        if required not in route_detailed_source:
            failures.append(f"route_wrapper_missing_{required}")

    for stale in [
        "_render_materials_and_sectionA_2d(sync_callbacks)",
        "_render_time_dependent_inputs(sync_callbacks)",
        "_render_ducts_prestress_voids_inputs(sync_callbacks)",
        "st.subheader(\"Crack Control Inputs\")",
        "key=\"inputs_crack_member_type\"",
        "key=\"inputs_crack_k1\"",
        "\"inputs_crack_k2\"",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_detailed_mode_extra_sections_coordinator_verifier",
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
                "# Inputs Page Detailed Mode Extra Sections Coordinator Verifier",
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
