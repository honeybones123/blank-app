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
    json_path = ARTIFACT_DIR / f"inputs_page_summary_display_state_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_summary_display_state_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    route_source = (
        ROOT / "inputs_application" / "page_runtime" / "summaries.py"
    ).read_text(
        encoding="utf-8",
        errors="ignore",
    )
    display_module_source = (
        ROOT / "inputs_page_modules" / "summaries" / "display_state.py"
    ).read_text(encoding="utf-8", errors="ignore")
    pipeline_module_source = (
        ROOT / "inputs_page_modules" / "summaries" / "pipeline.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        display_module_source,
        "render_inputs_summary_display_state",
    )
    route_display_source, _ = _function_source(
        route_source,
        "render_inputs_summary_display_state_current_coordinator",
    )
    render_inputs_source, render_inputs_size = _function_source(shell_source, "render_inputs_page")
    summary_pipeline_source, _ = _function_source(
        pipeline_module_source,
        "render_inputs_summary_pipeline",
    )
    summary_owner_source = summary_pipeline_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("summary_display_state_coordinator_missing")
    if coordinator_size > 225:
        failures.append(f"summary_display_state_coordinator_too_large:{coordinator_size}")

    for required in [
        'summary_state.get("Mu_star", summary_state.get("uls_Mstar", 0.0))',
        'summary_state.get("Vu_star", summary_state.get("uls_Vstar", 0.0))',
        'summary_state.get("Tu_star", 0.0)',
        'summary_state.get("sls_Mstar", 0.0)',
        'summary_state.get("sls_Vstar", 0.0)',
        'summary_state.get("sigma_sr", summary_state.get("sigma_s_sls", 0.0))',
        "no_loads_bending = uls_m == 0.0",
        "no_loads_shear = uls_v == 0.0 and uls_t == 0.0",
        "no_loads_crack = sls_m == 0.0 and sls_v == 0.0 and sigma_sr == 0.0",
        "no_loads_deflection = sls_m == 0.0 and sls_v == 0.0",
        "bending_primary = primary_row_fn(BENDING_ROWS) or {}",
        "shear_primary = primary_row_fn(SHEAR_ROWS) or {}",
        "pick_governing_check_row_fn(CRACK_ROWS)",
        "defl_primary = primary_row_fn(DEFLECTION_ROWS) or {}",
        "def _status_colour_from_summary(status: str) -> str:",
        "sectional_required_shear",
        "summary_phiVu_kN",
        "summary_Veq_kN",
        "visible_shear_has_fail",
        "shear_header_inconsistent_with_rows",
        "visible_row_consistency_override",
        "Fails on governing link spacing, not sectional shear",
        "visible_shear_summary_source",
        "_inputs_visible_shear_summary_debug",
        "def _apply_neutral_override(rows):",
        "_apply_neutral_override(BENDING_ROWS)",
        "_apply_neutral_override(SHEAR_ROWS)",
        "_apply_neutral_override(CRACK_ROWS)",
        "_apply_neutral_override(DEFLECTION_ROWS)",
        "return (",
        "bending_cap",
        "shear_governing_source",
        "defl_colour",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "summary_display_state_fn("
    if call_text not in summary_owner_source:
        failures.append("render_inputs_missing_summary_display_state_call")
    if "render_inputs_summary_display_state_module(" not in route_display_source:
        failures.append("route_summary_display_state_missing_module_delegate")

    for stale in [
        "uls_m = abs(",
        "no_loads_bending =",
        "bending_primary = _primary_row(BENDING_ROWS)",
        "def _status_colour_from_summary",
        "_visible_shear_has_fail",
        "_shear_header_inconsistent_with_rows",
        "visible_row_consistency_override",
        "def _apply_neutral_override(rows):",
        "_apply_neutral_override(BENDING_ROWS)",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    rows_call_index = summary_owner_source.find("summary_rows_from_packs_fn(")
    display_call_index = summary_owner_source.find(call_text)
    guide_cache_index = summary_owner_source.find("summary_guidance_cache_fn(")
    guide_cache_boundary = "summary_guidance_cache_call"
    if guide_cache_index < 0:
        guide_cache_index = summary_owner_source.find("DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY")
        guide_cache_boundary = "inline_guidance_cache"
    summary_render_index = summary_owner_source.find("summary_container_fn(")
    if not (0 <= rows_call_index < display_call_index < guide_cache_index < summary_render_index):
        failures.append(
            "summary_display_state_call_order_changed:"
            f"rows={rows_call_index}:display={display_call_index}:"
            f"guide_cache={guide_cache_index}:{guide_cache_boundary}:summary_render={summary_render_index}"
        )

    payload = {
        "verifier": "inputs_page_summary_display_state_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "render_inputs_size": render_inputs_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Summary Display State Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Render inputs size: `{render_inputs_size}`",
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
