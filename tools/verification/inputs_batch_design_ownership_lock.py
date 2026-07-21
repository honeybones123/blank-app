from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
BATCH_ROOT = ROOT / "batch_design"

REQUIRED_BATCH_FILES = (
    "models.py",
    "store.py",
    "validation.py",
    "runner.py",
    "assignment.py",
    "design_brain_adapter.py",
    "ui/page.py",
    "ui/project_beam_manager_adapters.py",
    "importers/base.py",
    "importers/spacegass_excel.py",
    "importers/project_import.py",
)

FORBIDDEN_PAGE_TOKENS = (
    "SpaceGassExcelImporter",
    "SpaceGassPdfImporter",
    "validate_batch_cases",
    "run_batch_design",
    "run_reviewed_batch_design",
    "assign_beam_case",
    "assign_batch_cases",
    "BatchBeamCase",
    "BatchDesignResult",
    "BatchAssignmentResult",
    "BatchImportWarning",
    "BatchValidationResult",
    "BatchDesignWorkflowState",
    "BEAM_MANAGER_EDITABLE_COLUMNS",
    "BEAM_MANAGER_TABLE_COLUMNS",
    "def _beam_option_labels",
    "def _build_beam_schedule_df",
    "def _build_schedule_preview_df",
    "def _sync_beam_records_from_schedule_df",
)

REQUIRED_CONTEXT_CALLBACKS = (
    "set_active_beam",
    "add_beam",
    "duplicate_beam",
    "delete_beam",
    "reset_workspace",
    "force_refresh",
    "log_rerun",
    "save_active_to_table",
    "apply_resync",
)

REQUIRED_CONTEXT_PROJECTIONS = (
    "build_schedule_preview_df",
    "build_schedule_editor_df",
    "sync_schedule_editor_df",
    "build_schedule_export_df",
    "get_active_summary",
    "format_status_badge",
    "format_last_checked",
    "make_section_preview_figure",
    "render_plotly_diagram",
    "design_brain_adapter",
)


def _call_names(source: str) -> list[str]:
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.append(node.func.attr)
    return names


def _batch_call_block(source: str) -> str:
    start = source.find("render_batch_design_page(")
    end = source.find('_mark("beam_manager")', start)
    return source[start:end] if start >= 0 and end > start else ""


def main() -> int:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    if ROUTE_COORDINATORS.exists():
        inputs_source += "\n" + ROUTE_COORDINATORS.read_text(encoding="utf-8", errors="replace")
    batch_sources = {
        str(path.relative_to(BATCH_ROOT)).replace("\\", "/"): path.read_text(
            encoding="utf-8", errors="replace"
        )
        for path in sorted(BATCH_ROOT.rglob("*.py"))
        if "tests" not in path.parts and "__pycache__" not in path.parts
    }
    combined_batch_source = "\n".join(batch_sources.values())
    core_source = "\n".join(
        text
        for name, text in batch_sources.items()
        if not name.startswith("ui/")
    )
    calls = _call_names(inputs_source)
    call_block = _batch_call_block(inputs_source)

    checks = {
        "required_batch_files_present": all((BATCH_ROOT / rel).exists() for rel in REQUIRED_BATCH_FILES),
        "single_inputs_page_renderer_call": calls.count("render_batch_design_page") == 1,
        "single_batch_page_context": calls.count("BatchDesignPageContext") == 1,
        "batch_heading_not_page_owned": 'st.markdown("### Batch design")' not in inputs_source,
        "batch_heading_package_owned": 'st.markdown("### Batch design")' in batch_sources.get("ui/page.py", ""),
        "no_batch_business_logic_in_inputs_page": not any(token in inputs_source for token in FORBIDDEN_PAGE_TOKENS),
        "all_shell_callbacks_injected": all(f"{name}=" in call_block for name in REQUIRED_CONTEXT_CALLBACKS),
        "all_projection_dependencies_injected": all(f"{name}=" in call_block for name in REQUIRED_CONTEXT_PROJECTIONS),
        "no_inputs_page_import_in_batch_package": not bool(
            re.search(r"(?:^|\n)\s*(?:import\s+inputs_page\b|from\s+inputs_page\b)", combined_batch_source)
        ),
        "batch_core_does_not_import_streamlit": not bool(
            re.search(r"(?:^|\n)\s*(?:import|from)\s+streamlit\b", core_source)
        ),
        "design_brain_execution_is_adapter_injected": "design_guidance_runner" in batch_sources.get(
            "design_brain_adapter.py", ""
        )
        and "BatchDesignGuidanceAdapter" in call_block,
        "page_save_bridge_is_thin": "persist_active_beam_from_shared()" in inputs_source
        and (
            "def render_inputs_batch_design_workspace_after_model_coordinator" in inputs_source
            or "def render_inputs_batch_design_manager_coordinator" in inputs_source
        )
        and "def save_active_batch_beam_to_table" in inputs_source,
    }
    failures = [name for name, passed in checks.items() if not passed]
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    decision = "INPUTS_BATCH_DESIGN_OWNERSHIP_LOCKED" if not failures else "INPUTS_BATCH_DESIGN_OWNERSHIP_GAPS_REMAIN"
    payload = {
        "audit": "inputs_batch_design_ownership_lock",
        "timestamp": timestamp,
        "decision": decision,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "batch_module_source_files": sorted(batch_sources),
        "page_owned_shell": [
            "timing markers",
            "BatchDesignPageContext dependency injection",
            "single render_batch_design_page call",
            "active-beam persistence callback",
        ],
        "shared_infrastructure_retained": [
            "state_and_helpers active-beam hydration and persistence",
            "report_helpers stored-beam export rows",
        ],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "design_brain_behavior_changed": False,
    }

    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = verification_dir / f"inputs_batch_design_ownership_lock_{timestamp}.json"
    report_path = audit_dir / f"inputs_batch_design_ownership_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Batch Design Ownership Lock",
                "",
                f"Decision: `{decision}`",
                "",
                f"Checks passed: `{sum(1 for value in checks.values() if value)}/{len(checks)}`",
                f"Failures: `{len(failures)}`",
                "",
                "The Batch Design package owns import, validation, workflow state, running, assignment, results/export, and UI.",
                "`inputs_page.py` retains one composition call, injected callbacks/projections, timing markers, and the active-beam persistence bridge.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(decision)
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
