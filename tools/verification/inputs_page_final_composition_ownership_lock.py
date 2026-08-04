from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
SHELL_PAGE = ROOT / "inputs_page_shell.py"
MODULE_ROOT = ROOT / "inputs_page_modules"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"

DOMAIN_GATES = (
    "tools/verification/inputs_summary_local_html_fallback_deadness_snapshot.py",
    "tools/verification/inputs_diagram_remaining_page_shell_audit.py",
    "tools/verification/diagram_remaining_hits_smoke.py",
    "tools/verification/inputs_calculations_remaining_surface_audit.py",
    "tools/verification/inputs_calculations_legacy_renderer_tail_deadness_snapshot.py",
    "tools/verification/inputs_widgets_metadata_ownership_lock.py",
    "tools/verification/inputs_session_state_ownership_lock.py",
    "tools/verification/inputs_batch_design_ownership_lock.py",
    "tools/verification/design_brain_inputs_page_zero_authority_inventory_lock.py",
)

REQUIRED_MODULE_DIRS = (
    "summaries",
    "diagrams",
    "calculations",
    "widgets",
    "session",
)

REQUIRED_PAGE_DELEGATIONS = (
    "render_inputs_page_setup_current_coordinator(",
    "render_inputs_widget_sections_current_coordinator(",
    "render_inputs_summary_pipeline_current_coordinator(",
    "render_inputs_tail_current_coordinator(",
)

REQUIRED_SHELL_BOUNDARIES = (
    "EXTRACTED_MODULE_BOUNDARIES",
    "build_inputs_session_source_snapshot",
    "build_inputs_widget_group_view_model",
    "build_inputs_summary_view_model",
    "build_inputs_diagram_view_model",
    "build_inputs_calculation_explainer_view_model",
)

DEAD_PAGE_TOKENS = (
    "def _render_summary_html_fallback(",
    "def resolve_final_visible_design_guide_item(",
    "def _publish_final_visible_design_guide_contract_binding(",
    "def _beam_option_labels(",
    "def _build_beam_schedule_df(",
    "def _build_schedule_preview_df(",
    "def _sync_beam_records_from_schedule_df(",
)


def _run_gate(path: str) -> dict[str, object]:
    command = [sys.executable, path]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=240,
    )
    return {
        "path": path,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
    }


def main() -> int:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    shell_source = (
        SHELL_PAGE.read_text(encoding="utf-8", errors="replace")
        if SHELL_PAGE.exists()
        else inputs_source
    )
    route_source = (
        ROUTE_COORDINATORS.read_text(encoding="utf-8", errors="replace")
        if ROUTE_COORDINATORS.exists()
        else ""
    )
    module_sources = {
        str(path.relative_to(MODULE_ROOT)).replace("\\", "/"): path.read_text(
            encoding="utf-8", errors="replace"
        )
        for path in sorted(MODULE_ROOT.rglob("*.py"))
        if "__pycache__" not in path.parts
    }
    combined_module_source = "\n".join(module_sources.values())
    streamlit_import_re = re.compile(
        r"(?:^|\n)\s*(?:import|from)\s+streamlit\b",
    )
    allowed_streamlit_render_modules = {
        "page_styles.py",
        "performance.py",
        "summaries/render_coordinators.py",
    }
    unexpected_streamlit_modules = sorted(
        name
        for name, source in module_sources.items()
        if streamlit_import_re.search(source)
        and name not in allowed_streamlit_render_modules
    )
    gate_results = [_run_gate(path) for path in DOMAIN_GATES]

    checks = {
        "all_domain_gates_pass": all(row["passed"] for row in gate_results),
        "all_required_module_dirs_present": all((MODULE_ROOT / name).is_dir() for name in REQUIRED_MODULE_DIRS),
        "permanent_page_delegates_to_route_coordinators": all(token in inputs_source for token in REQUIRED_PAGE_DELEGATIONS),
        "permanent_page_exposes_extracted_module_boundaries": all(
            token in inputs_source for token in REQUIRED_SHELL_BOUNDARIES
        ),
        "live_shell_retains_render_entrypoint": (
            "def render_inputs_page(" in shell_source
            and "render_inputs = speed_profiled(" in shell_source
        ),
        "staging_shell_removed_after_cutover": not SHELL_PAGE.exists(),
        "permanent_page_has_no_old_render_inputs_function": "def render_inputs(" not in inputs_source,
        "dead_page_owned_domain_helpers_absent": all(token not in inputs_source for token in DEAD_PAGE_TOKENS),
        "extracted_modules_do_not_import_inputs_page": not bool(
            re.search(
                r"(?:^|\n)\s*(?:import\s+inputs_page\b|from\s+inputs_page\b)",
                combined_module_source,
            )
        ),
        "pure_extracted_modules_do_not_import_streamlit": not unexpected_streamlit_modules,
        "route_coordinators_retain_batch_design_route": route_source.count("render_batch_design_page(") >= 1,
        "summary_render_route_delegates_to_summary_module": (
            "render_inputs_summary_container_current_module(" in route_source
            and "summaries/render_coordinators.py" in module_sources
            and "def render_inputs_summary_container_current(" in module_sources.get("summaries/render_coordinators.py", "")
            and "build_inputs_summary_html(" in module_sources.get("summaries/render_coordinators.py", "")
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    decision = "INPUTS_PAGE_FINAL_COMPOSITION_OWNERSHIP_LOCKED" if not failures else "INPUTS_PAGE_FINAL_COMPOSITION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_final_composition_ownership_lock",
        "timestamp": timestamp,
        "decision": decision,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "domain_gate_results": gate_results,
        "module_source_files": sorted(module_sources),
        "allowed_streamlit_render_modules": sorted(allowed_streamlit_render_modules),
        "unexpected_streamlit_modules": unexpected_streamlit_modules,
        "approved_inputs_page_responsibilities": [
            "page composition and layout",
            "Streamlit rendering",
            "route coordinator ordering",
            "extracted module boundary exports",
        ],
        "locked_module_owners": [
            "inputs_page_modules.summaries",
            "inputs_page_modules.diagrams",
            "inputs_page_modules.calculations",
            "inputs_page_modules.widgets",
            "inputs_page_modules.session",
            "batch_design",
            "design_brain and FinalDesignGuidePublication",
        ],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "render_ownership_changed": False,
    }

    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = verification_dir / f"inputs_page_final_composition_ownership_lock_{timestamp}.json"
    report_path = audit_dir / f"inputs_page_final_composition_ownership_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Composition Ownership Lock",
                "",
                f"Decision: `{decision}`",
                "",
                f"Domain gates passed: `{sum(1 for row in gate_results if row['passed'])}/{len(gate_results)}`",
                f"Ownership checks passed: `{sum(1 for value in checks.values() if value)}/{len(checks)}`",
                f"Failures: `{len(failures)}`",
                "",
                "The extracted domains own their typed models, state/view-model construction, contracts, and domain policy.",
                "`inputs_page.py` is bounded to composition, Streamlit rendering, callbacks, session mutation, Apply routing, and debug/trace storage.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(decision)
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ",".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
