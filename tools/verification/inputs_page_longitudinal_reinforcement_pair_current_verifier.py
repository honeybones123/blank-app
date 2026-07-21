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
    json_path = ARTIFACT_DIR / f"inputs_page_longitudinal_reinforcement_pair_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_longitudinal_reinforcement_pair_current_{timestamp}.md"
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
    coordinator_source, coordinator_size = _function_source(
        widget_module_source,
        "render_inputs_widget_sections",
    )
    render_inputs_source, _ = _function_source(shell_source, "render_inputs_page")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("longitudinal_reinforcement_pair_render_orchestration_missing")
    if not bottom_source:
        failures.append("bottom_reinforcement_column_current_coordinator_missing")
    if not top_source:
        failures.append("top_reinforcement_column_module_missing")
    if coordinator_size > 130:
        failures.append(f"longitudinal_reinforcement_pair_render_orchestration_too_large:{coordinator_size}")

    combined_source = "\n".join([coordinator_source, bottom_source, top_source])
    for required in [
        "with col_bot_reo:",
        "with col_top_reo:",
        "before_longitudinal_widget_render",
        "before_longitudinal_widget_render_top",
        "inputs_rowgap_bot",
        "inputs_rowgap_top",
        "inputs_apply_bottom_recommendation",
        "fast_mode:bottom_recommendation",
        "detailed_mode:bottom_recommendation",
        "render_longitudinal_reo_row_config_controls",
        "render_longitudinal_reo_rows",
        "section=\"bot\"",
        "section=\"top\"",
        "inputs_cover_bot",
        "inputs_cover_top",
        "Bottom cover (mm)",
        "Top cover (mm)",
        "H_BOT_REO_WIDGET_ALIGN",
    ]:
        if required not in combined_source:
            failures.append(f"coordinator_missing_{required}")

    bottom_call = "bottom_reinforcement_column_fn("
    top_call = "top_reinforcement_column_fn("
    if bottom_call not in coordinator_source:
        failures.append("render_orchestration_missing_bottom_reinforcement_column_call")
    if top_call not in coordinator_source:
        failures.append("render_orchestration_missing_top_reinforcement_column_call")

    for stale in [
        "inputs_apply_bottom_recommendation",
        "Bottom cover (mm)",
        "Top cover (mm)",
        "H_BOT_REO_WIDGET_ALIGN",
        "before_longitudinal_widget_render_top",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    columns_index = coordinator_source.find("col_bot_reo, col_top_reo, col_shear_mat = create_reinforcement_columns_fn()")
    bottom_index = coordinator_source.find(bottom_call)
    top_index = coordinator_source.find(top_call)
    shear_index = coordinator_source.find("shear_reinforcement_column_fn(")
    if not (0 <= columns_index < bottom_index < top_index < shear_index):
        failures.append(
            "longitudinal_reinforcement_pair_call_order_changed:"
            f"columns={columns_index}:bottom={bottom_index}:top={top_index}:shear={shear_index}"
        )

    payload = {
        "verifier": "inputs_page_longitudinal_reinforcement_pair_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "bottom_size": bottom_size,
        "top_size": top_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Longitudinal Reinforcement Pair Current Verifier",
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
