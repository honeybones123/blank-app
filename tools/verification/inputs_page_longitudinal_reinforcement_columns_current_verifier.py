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


def _require_all(source: str, required: list[str], failures: list[str], prefix: str) -> None:
    for item in required:
        if item not in source:
            failures.append(f"{prefix}_missing_{item}")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_longitudinal_reinforcement_columns_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_longitudinal_reinforcement_columns_current_{timestamp}.md"
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
    bottom_source, bottom_size = _function_source(
        widget_module_source,
        "render_inputs_bottom_reinforcement_column",
    )
    top_source, top_size = _function_source(
        widget_module_source,
        "render_inputs_top_reinforcement_column",
    )
    render_inputs_source, _ = _function_source(shell_source, "render_inputs_page")
    widget_owner_source, _ = _function_source(widget_module_source, "render_inputs_widget_sections")

    failures: list[str] = []
    if not bottom_source:
        failures.append("bottom_reinforcement_column_coordinator_missing")
    if not top_source:
        failures.append("top_reinforcement_column_coordinator_missing")
    if bottom_size > 110:
        failures.append(f"bottom_reinforcement_column_coordinator_too_large:{bottom_size}")
    if top_size > 95:
        failures.append(f"top_reinforcement_column_coordinator_too_large:{top_size}")

    _require_all(
        bottom_source,
        [
            "with col_bot_reo:",
            "before_longitudinal_widget_render",
            "inputs_rowgap_bot",
            "fast_mode:bottom_recommendation",
            "detailed_mode:bottom_recommendation",
            "render_longitudinal_reo_row_config_controls_fn(",
            "H_BOT_REO_WIDGET_ALIGN",
            "render_longitudinal_reo_rows_fn(",
            "inputs_cover_bot",
            "Bottom cover (mm)",
        ],
        failures,
        "bottom_coordinator",
    )
    _require_all(
        top_source,
        [
            "with col_top_reo:",
            "before_longitudinal_widget_render_top",
            "inputs_rowgap_top",
            "Edit top web bars directly here",
            "render_longitudinal_reo_row_config_controls_fn(",
            "render_longitudinal_reo_rows_fn(",
            "inputs_cover_top",
            "Top cover (mm)",
        ],
        failures,
        "top_coordinator",
    )

    bottom_call = "bottom_reinforcement_column_fn("
    top_call = "top_reinforcement_column_fn("
    if bottom_call not in widget_owner_source:
        failures.append("render_inputs_missing_bottom_reinforcement_column_call")
    if top_call not in widget_owner_source:
        failures.append("render_inputs_missing_top_reinforcement_column_call")

    for stale in [
        "before_longitudinal_widget_render",
        "inputs_rowgap_bot",
        "fast_mode:bottom_recommendation",
        "inputs_cover_bot",
        "before_longitudinal_widget_render_top",
        "inputs_rowgap_top",
        "Edit top web bars directly here",
        "inputs_cover_top",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    geometry_index = widget_owner_source.find("geometry_materials_top_section_fn(")
    bottom_index = widget_owner_source.find(bottom_call)
    top_index = widget_owner_source.find(top_call)
    shear_index = widget_owner_source.find("shear_reinforcement_column_fn(")
    if not (0 <= geometry_index < bottom_index < top_index < shear_index):
        failures.append(
            "longitudinal_reinforcement_call_order_changed:"
            f"geometry={geometry_index}:bottom={bottom_index}:top={top_index}:shear={shear_index}"
        )

    payload = {
        "verifier": "inputs_page_longitudinal_reinforcement_columns_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "bottom_coordinator_size": bottom_size,
        "top_coordinator_size": top_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Longitudinal Reinforcement Columns Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Bottom coordinator size: `{bottom_size}`",
                f"Top coordinator size: `{top_size}`",
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
