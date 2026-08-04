from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CALCULATION_OWNER = (
    ROOT / "inputs_application" / "page_runtime" / "calculations.py"
)
WORKSPACE = ROOT / "inputs_application" / "engineering_workspace.py"
MODULE_ROOT = ROOT / "inputs_page_modules" / "calculations"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


APPROVED_PAGE_SHELL_FUNCTIONS = {
    "render_inputs_calculation_fragment_current_coordinator": (
        "typed_calculation_fragment_owner"
    ),
}

APPROVED_PAGE_SHELL_TOKENS = (
    "render_inputs_calculation_explainer_trace(",
)

MODULE_TRACE_TOKENS = (
    "build_inputs_calculation_explainer_source_snapshot(",
    "build_inputs_calculation_explainer_source_hash(",
    "build_inputs_calculation_explainer_view_model(",
    "_inputs_calculation_explainer_view_model_trace",
    "inputs_calculation_explainer_view_model_trace",
)

FORBIDDEN_DEAD_TAIL_TOKENS = (
    "bending_table_html = cached_generate_summary_table_html",
    "shear_table_html = cached_generate_summary_table_html",
    "crack_table_html = cached_generate_summary_table_html",
    "defl_table_html = cached_generate_summary_table_html",
    "Custom CSS for top-level expandable rows",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_ranges(source: str) -> dict[str, dict[str, int]]:
    tree = ast.parse(source)
    ranges: dict[str, dict[str, int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ranges[node.name] = {
                "start": int(node.lineno),
                "end": int(getattr(node, "end_lineno", node.lineno)),
            }
    return ranges


def _module_checks() -> dict[str, Any]:
    sources = {
        path.name: _read(path)
        for path in MODULE_ROOT.glob("*.py")
    }
    combined = "\n".join(sources.values())
    imports: list[str] = []
    for source in sources.values():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
    return {
        "module_files": sorted(sources),
        "models_present": "models.py" in sources,
        "builders_present": "builders.py" in sources,
        "contracts_present": "contracts.py" in sources,
        "source_builder_present": "def build_inputs_calculation_explainer_source_snapshot(" in sources.get("builders.py", ""),
        "view_model_builder_present": "def build_inputs_calculation_explainer_view_model(" in sources.get("builders.py", ""),
        "imports_streamlit": any(imported == "streamlit" or imported.startswith("streamlit.") for imported in imports),
        "imports_inputs_page": any(imported == "inputs_page" or imported.startswith("inputs_page.") for imported in imports),
        "imports_solver_modules": any(
            imported in {
                "build_bending_check_rows_from_state",
                "build_shear_check_rows_from_state",
                "build_crack_check_rows_from_state",
                "build_deflection_check_rows_from_state",
                "run_shear_calc",
                "compute_bending_capacity_from_state",
            }
            for imported in imports
        ),
        "combined_source": combined,
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Calculations Remaining Surface Audit",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "## Page Surfaces",
        "",
    ]
    for surface in payload["page_surfaces"]:
        lines.append(
            f"- `{surface['name']}` lines `{surface['start']}`-`{surface['end']}`: `{surface['classification']}`"
        )
    lines.extend(["", "## Checks", ""])
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            payload["next_safe_slice"],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    live_surface = (
        source
        + "\n"
        + _read(CALCULATION_OWNER)
        + "\n"
        + _read(WORKSPACE)
    )
    ranges = _function_ranges(_read(CALCULATION_OWNER))
    page_surfaces = [
        {
            "name": name,
            "start": ranges.get(name, {}).get("start"),
            "end": ranges.get(name, {}).get("end"),
            "classification": classification,
        }
        for name, classification in APPROVED_PAGE_SHELL_FUNCTIONS.items()
        if name in ranges
    ]
    module_checks = _module_checks()
    combined_module_source = str(module_checks.get("combined_source") or "")
    checks = {
        "typed_calculation_owner_present": all(name in ranges for name in APPROVED_PAGE_SHELL_FUNCTIONS),
        "typed_owner_delegates_to_calculation_trace_module": all(token in live_surface for token in APPROVED_PAGE_SHELL_TOKENS),
        "calculation_is_real_workspace_fragment": (
            'fragment_name="calculation"' in live_surface
        ),
        "module_trace_builds_payload": all(token in combined_module_source for token in MODULE_TRACE_TOKENS),
        "dead_legacy_renderer_tail_absent": not any(token in live_surface for token in FORBIDDEN_DEAD_TAIL_TOKENS),
        "module_models_present": bool(module_checks["models_present"]),
        "module_builders_present": bool(module_checks["builders_present"]),
        "module_contracts_present": bool(module_checks["contracts_present"]),
        "module_source_builder_present": bool(module_checks["source_builder_present"]),
        "module_view_model_builder_present": bool(module_checks["view_model_builder_present"]),
        "module_imports_streamlit": bool(module_checks["imports_streamlit"]),
        "module_imports_inputs_page": bool(module_checks["imports_inputs_page"]),
        "module_imports_solver_modules": bool(module_checks["imports_solver_modules"]),
    }
    failures = [
        key for key, value in checks.items()
        if (key.startswith("module_imports_") and value) or (not key.startswith("module_imports_") and not value)
    ]
    decision = (
        "CALCULATION_EXPLAINER_INPUTS_PAGE_SURFACE_LOCK_READY"
        if not failures
        else "CALCULATION_EXPLAINER_REMAINING_SURFACES_NEED_WORK"
    )
    next_safe_slice = (
        "Keep the typed Calculation fragment locked while broad browser verification remains paused."
        if not failures
        else "Resolve the listed remaining calculation/explainer surface failures before locking this domain."
    )
    payload = {
        "audit": "inputs_calculations_remaining_surface_audit",
        "timestamp": timestamp,
        "decision": decision,
        "page_surfaces": page_surfaces,
        "module_checks": module_checks,
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "next_safe_slice": next_safe_slice,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_calculations_remaining_surface_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_calculations_remaining_surface_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_calculations_remaining_surface_audit", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
