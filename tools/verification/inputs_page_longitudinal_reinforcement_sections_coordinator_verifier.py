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
    json_path = ARTIFACT_DIR / f"inputs_page_longitudinal_reinforcement_sections_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_longitudinal_reinforcement_sections_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size, coordinator_start, coordinator_end = (
        _largest_function_source(source, "render_inputs_longitudinal_reinforcement_sections_coordinator")
    )
    render_inputs_source, render_inputs_size, _, _ = _largest_function_source(
        source,
        "render_inputs",
    )

    failures: list[str] = []
    if not coordinator_source:
        failures.append("longitudinal_reinforcement_sections_coordinator_missing")
    if coordinator_size > 230:
        failures.append(f"longitudinal_reinforcement_sections_coordinator_too_large:{coordinator_size}")

    for required in [
        "with col_bot_reo:",
        "with col_top_reo:",
        "_browser_recipe_hydrate_inputs_reo_widget_mirrors(",
        '"render_inputs:before_bottom_reo_widgets"',
        '"render_inputs:before_top_reo_widgets"',
        "_longitudinal_reo_widget_audit_snapshot(",
        "main_longitudinal_reo_pair_labels(",
        "_render_bottom_recommendation_panel(",
        "render_longitudinal_reo_row_config_controls(",
        "render_longitudinal_reo_rows(",
        "number_row(",
        '"inputs_cover_bot"',
        '"inputs_cover_top"',
        "render_inputs_longitudinal_reinforcement_widget_metadata_coordinator(",
        'section="bot"',
        'section="top"',
        "phase5c_render_trace_fn(",
        '"bottom_reinforcement_render_complete"',
        '"top_reinforcement_render_complete"',
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    for forbidden in [
        "_phase5c_render_trace(",
        "fast_get_param(",
        "_sec_shape_reo_ui",
        "_is_ti_reo_ui",
        "_bot_hdr",
        "_top_hdr",
    ]:
        if forbidden in coordinator_source:
            failures.append(f"coordinator_retains_render_inputs_local_{forbidden}")

    for required in [
        "render_inputs_longitudinal_reinforcement_sections_coordinator(",
        "col_bot_reo=col_bot_reo",
        "col_top_reo=col_top_reo",
        "inputs_detailed_mode=bool(inputs_detailed_mode)",
        "sync_callbacks=sync_callbacks",
        "phase5c_render_trace_fn=_phase5c_render_trace",
        "fast_get_param_fn=fast_get_param",
        "# --- Shear + Materials (third column) ---",
    ]:
        if required not in render_inputs_source:
            failures.append(f"render_inputs_call_missing_{required}")

    for stale in [
        '"render_inputs:before_bottom_reo_widgets"',
        '"render_inputs:before_top_reo_widgets"',
        "main_longitudinal_reo_pair_labels(",
        '"bottom_reinforcement_render_complete"',
        '"top_reinforcement_render_complete"',
        'section="bot"',
        'section="top"',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_longitudinal_reinforcement_sections_coordinator_verifier",
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
                "# Inputs Page Longitudinal Reinforcement Sections Coordinator Verifier",
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
