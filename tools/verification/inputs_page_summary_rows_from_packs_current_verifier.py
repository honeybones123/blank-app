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
    json_path = ARTIFACT_DIR / f"inputs_page_summary_rows_from_packs_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_summary_rows_from_packs_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    route_source = (
        ROOT / "inputs_application" / "page_runtime" / "summaries.py"
    ).read_text(
        encoding="utf-8",
        errors="ignore",
    )
    rows_module_source = (
        ROOT / "inputs_page_modules" / "summaries" / "rows_from_packs.py"
    ).read_text(encoding="utf-8", errors="ignore")
    pipeline_module_source = (
        ROOT / "inputs_page_modules" / "summaries" / "pipeline.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        rows_module_source,
        "render_inputs_summary_rows_from_packs",
    )
    route_rows_source, _ = _function_source(
        route_source,
        "render_inputs_summary_rows_from_packs_current_coordinator",
    )
    render_inputs_source, render_inputs_size = _function_source(shell_source, "render_inputs_page")
    summary_pipeline_source, _ = _function_source(
        pipeline_module_source,
        "render_inputs_summary_pipeline",
    )
    summary_owner_source = summary_pipeline_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("summary_rows_from_packs_coordinator_missing")
    if coordinator_size > 100:
        failures.append(f"summary_rows_from_packs_coordinator_too_large:{coordinator_size}")

    for required in [
        "bend_err = bend_pack is None",
        "shear_err = shear_pack is None",
        "crack_err = crack_pack is None",
        "defl_err = defl_pack is None",
        'BENDING_ROWS = [_normalise_row(row, "bending")',
        'shear_summary_src = shear_pack_d.get("summary_rows")',
        'shear_mcft_src = shear_pack_d.get("mcft_detail_rows")',
        'st_module.session_state.get("show_mcft_breakdown", False)',
        'SHEAR_ROWS = [_normalise_row(row, "shear")',
        'CRACK_ROWS = [_normalise_row(row, "crack")',
        "Bending checks failed",
        "Shear checks failed",
        "Crack checks failed",
        'DEFLECTION_ROWS = [_normalise_row(row, "deflection")',
        "Deflection checks failed",
        'defl_summary.get("summary_delta_total_mm")',
        'defl_summary.get("summary_defl_limit_mm")',
        'defl_summary.get("summary_util_total")',
        "return (",
        "BENDING_ROWS",
        "SHEAR_ROWS",
        "CRACK_ROWS",
        "DEFLECTION_ROWS",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "summary_rows_from_packs_fn("
    if call_text not in summary_owner_source:
        failures.append("render_inputs_missing_summary_rows_from_packs_call")
    if "render_inputs_summary_rows_from_packs_module(" not in route_rows_source:
        failures.append("route_summary_rows_from_packs_missing_module_delegate")

    for stale in [
        "bend_err = bend_pack is None",
        "_shear_summary_src = _sp.get(\"summary_rows\")",
        "Bending checks failed",
        "Shear checks failed",
        "Crack checks failed",
        "Deflection checks failed",
        "defl_summary.get(\"summary_delta_total_mm\")",
        "defl_summary.get(\"summary_defl_limit_mm\")",
        "defl_summary.get(\"summary_util_total\")",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    summary_cache_index = summary_owner_source.find("summary_state_cache_fn(")
    pack_log_index = summary_owner_source.find('hc_log_fn(\n        "summary.pack_meta"')
    state_log_index = summary_owner_source.find('hc_log_fn(\n        "state.snapshot"')
    rows_call_index = summary_owner_source.find(call_text)
    status_index = summary_owner_source.find("summary_display_state_fn(")
    status_boundary = "summary_display_state_call"
    if status_index < 0:
        status_index = summary_owner_source.find("uls_m = abs(")
        status_boundary = "inline_display_state"
    if not (0 <= summary_cache_index < pack_log_index < state_log_index < rows_call_index < status_index):
        failures.append(
            "summary_rows_from_packs_call_order_changed:"
            f"summary_cache={summary_cache_index}:pack_log={pack_log_index}:"
            f"state_log={state_log_index}:rows_call={rows_call_index}:"
            f"status={status_index}:{status_boundary}"
        )

    payload = {
        "verifier": "inputs_page_summary_rows_from_packs_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "render_inputs_size": render_inputs_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Summary Rows From Packs Current Verifier",
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
