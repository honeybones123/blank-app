"""Verify Batch Design route isolation after the module cutover."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
INPUTS_ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
APP_ENTRYPOINTS = [ROOT / "app.py", ROOT / "streamlit_app.py"]

FORBIDDEN_INPUTS_PAGE_TOKENS = {
    "SpaceGassExcelImporter",
    "SpaceGassPdfImporter",
    "validate_batch_cases",
    "run_batch_design",
    "assign_beam_case",
    "assign_batch_cases",
    "BatchBeamCase",
    "BatchDesignResult",
    "BatchAssignmentResult",
    "BatchImportWarning",
    "BatchValidationResult",
    "batch_design_imported_rows",
    "batch_design_import_errors",
    "batch_design_import_warnings",
    "BEAM_MANAGER_EDITABLE_COLUMNS",
    "BEAM_MANAGER_STATUS_COLUMNS",
    "BEAM_MANAGER_TABLE_COLUMNS",
    "BEAM_MANAGER_NUMERIC_COLUMNS",
    "BEAM_MANAGER_INT_COLUMNS",
    "def _beam_option_labels",
    "def _build_beam_schedule_df",
    "def _build_schedule_preview_df",
    "def _coerce_beam_schedule_value",
    "def _sync_beam_records_from_schedule_df",
    "build_beam_schedule_rows",
    "build_beam_schedule_export_rows",
}

FORBIDDEN_ACTIVE_SECTION_TOKENS = FORBIDDEN_INPUTS_PAGE_TOKENS | {
    'st.markdown("### Batch design")',
    "st.tabs(",
    "st.file_uploader(",
    "st.data_editor(",
    "st.download_button(",
}


def _call_names(source: str) -> list[str]:
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.append(func.id)
        elif isinstance(func, ast.Attribute):
            names.append(func.attr)
    return names


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return "\n".join(lines[node.lineno - 1 : end])
    return ""


def _active_batch_section(source: str) -> str:
    current = _function_source(source, "render_inputs_batch_design_manager_coordinator")
    if current:
        return current
    start = source.find('render_timing_mark("inputs_page.widget_section_render_start", section="batch_design")')
    if start < 0:
        start = source.find('section="batch_design"')
    end = source.find('_mark("beam_manager")', start)
    if start < 0 or end < 0:
        return ""
    return source[start:end]


def run_check() -> dict:
    shell_source = INPUTS_PAGE.read_text(encoding="utf-8-sig")
    route_source = INPUTS_ROUTE_COORDINATORS.read_text(encoding="utf-8-sig")
    inputs_source = shell_source + "\n" + route_source
    inputs_calls = _call_names(route_source)
    active_section = _active_batch_section(route_source)

    entrypoint_hits = {}
    for path in APP_ENTRYPOINTS:
        if path.exists():
            text = path.read_text(encoding="utf-8-sig")
            entrypoint_hits[str(path.relative_to(ROOT))] = text.count("render_batch_design_page(")

    forbidden_inputs_hits = sorted(token for token in FORBIDDEN_INPUTS_PAGE_TOKENS if token in shell_source)
    forbidden_section_hits = sorted(
        token for token in FORBIDDEN_ACTIVE_SECTION_TOKENS if token in active_section
    )

    checks = {
        "inputs_page_has_renderer_import": "from batch_design.ui.page import BatchDesignPageContext, render_batch_design_page" in route_source,
        "inputs_page_render_call_count": inputs_calls.count("render_batch_design_page"),
        "inputs_page_batch_heading_count": shell_source.count('st.markdown("### Batch design")'),
        "active_section_found": bool(active_section),
        "active_section_has_renderer_call": "render_batch_design_page(" in active_section,
        "forbidden_inputs_page_hits": forbidden_inputs_hits,
        "forbidden_active_section_hits": forbidden_section_hits,
        "app_entrypoint_render_call_counts": entrypoint_hits,
    }
    failures = []
    if not checks["inputs_page_has_renderer_import"]:
        failures.append("inputs_page_missing_batch_design_renderer_import")
    if checks["inputs_page_render_call_count"] != 1:
        failures.append("inputs_page_render_batch_design_page_call_count_not_one")
    if checks["inputs_page_batch_heading_count"] != 0:
        failures.append("inputs_page_still_renders_batch_design_heading_inline")
    if not checks["active_section_found"]:
        failures.append("active_batch_section_not_found")
    if not checks["active_section_has_renderer_call"]:
        failures.append("active_batch_section_missing_renderer_call")
    if forbidden_inputs_hits:
        failures.append("batch_design_business_logic_token_found_in_inputs_page")
    if forbidden_section_hits:
        failures.append("batch_design_inline_ui_or_business_logic_found_in_active_section")
    if any(count for count in entrypoint_hits.values()):
        failures.append("additional_app_entrypoint_calls_batch_design_renderer")

    return {
        "schema": "batch_design_route_isolation.v1",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
    }


def main() -> int:
    result = run_check()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
