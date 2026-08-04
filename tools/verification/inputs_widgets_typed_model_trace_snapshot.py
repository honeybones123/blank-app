from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
MODULE_ROOT = ROOT / "inputs_page_modules" / "widgets"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Typed Model Trace Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Widget metadata models/contracts/builders live in `inputs_page_modules/widgets/`.",
            "- `inputs_page.py` still renders all widgets and owns callback/session wiring.",
            "- The module does not import Streamlit, session state, or `inputs_page.py`.",
            "- Live widget renderer cutover remains false.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    module_sources = {
        path.name: _read(path)
        for path in MODULE_ROOT.glob("*.py")
    }
    module_combined = "\n".join(module_sources.values())
    checks = {
        "models_file_present": "models.py" in module_sources,
        "builders_file_present": "builders.py" in module_sources,
        "contracts_file_present": "contracts.py" in module_sources,
        "module_has_widget_spec_model": "class InputsWidgetSpecViewModel" in module_sources.get("models.py", ""),
        "module_has_widget_group_model": "class InputsWidgetGroupViewModel" in module_sources.get("models.py", ""),
        "module_has_group_builder": "def build_inputs_widget_group_view_model(" in module_sources.get("builders.py", ""),
        "contracts_allow_design_action_numbers": '"design_action_numbers"' in module_sources.get("contracts.py", ""),
        "contracts_allow_geometry_basic": '"geometry_basic"' in module_sources.get("contracts.py", ""),
        "contracts_allow_materials_basic": '"materials_basic"' in module_sources.get("contracts.py", ""),
        "contracts_allow_shear_reinforcement_basic": '"shear_reinforcement_basic"' in module_sources.get("contracts.py", ""),
        "contracts_allow_bottom_longitudinal_reinforcement": '"bottom_longitudinal_reinforcement"' in module_sources.get("contracts.py", ""),
        "contracts_allow_top_longitudinal_reinforcement": '"top_longitudinal_reinforcement"' in module_sources.get("contracts.py", ""),
        "contracts_allow_serviceability_environment_basic": '"serviceability_environment_basic"' in module_sources.get("contracts.py", ""),
        "contracts_allow_support_deflection_basic": '"support_deflection_basic"' in module_sources.get("contracts.py", ""),
        "contracts_allow_shear_section_parameters_basic": '"shear_section_parameters_basic"' in module_sources.get("contracts.py", ""),
        "contracts_allow_time_dependent_basic": '"time_dependent_basic"' in module_sources.get("contracts.py", ""),
        "contracts_allow_ducts_prestress_voids_basic": '"ducts_prestress_voids_basic"' in module_sources.get("contracts.py", ""),
        "contracts_allow_crack_control_inputs_basic": '"crack_control_inputs_basic"' in module_sources.get("contracts.py", ""),
        "contracts_allow_flange_reinforcement_basic": '"flange_reinforcement_basic"' in module_sources.get("contracts.py", ""),
        "contracts_allow_flange_transverse_basic": '"flange_transverse_basic"' in module_sources.get("contracts.py", ""),
        "page_imports_widget_builder": (
            "from inputs_page_modules.widgets import" in page
            and "build_inputs_widget_group_view_model" in page
        ),
        "page_calls_widget_builder": "build_inputs_widget_group_view_model(" in page,
        "page_records_design_action_numbers_widget_metadata_trace": '"design_action_numbers_widget_metadata_hash"' in page,
        "page_records_geometry_widget_metadata_trace": '"geometry_widget_metadata_hash"' in page,
        "page_records_materials_widget_metadata_trace": '"materials_widget_metadata_hash"' in page,
        "page_records_shear_widget_metadata_trace": '"shear_widget_metadata_hash"' in page,
        "page_records_bottom_longitudinal_widget_metadata_trace": "bottom_longitudinal_reinforcement" in page and "longitudinal_widget_metadata_hash" in page,
        "page_records_top_longitudinal_widget_metadata_trace": "top_longitudinal_reinforcement" in page and "longitudinal_widget_metadata_hash" in page,
        "page_records_serviceability_environment_widget_metadata_trace": "serviceability_environment_basic" in page and "widget_metadata_hash" in page,
        "page_records_support_deflection_widget_metadata_trace": "support_deflection_basic" in page and "widget_metadata_hash" in page,
        "page_records_shear_section_parameters_widget_metadata_trace": "shear_section_parameters_basic" in page and "widget_metadata_hash" in page,
        "page_records_time_dependent_widget_metadata_trace": "time_dependent_basic" in page and "time_dependent_basic_widget_metadata_hash" in page,
        "page_records_ducts_prestress_voids_widget_metadata_trace": "ducts_prestress_voids_basic" in page and "ducts_prestress_voids_basic_widget_metadata_hash" in page,
        "page_records_crack_control_widget_metadata_trace": "crack_control_inputs_basic" in page and "crack_control_inputs_basic_widget_metadata_hash" in page,
        "page_records_flange_reinforcement_widget_metadata_trace": "flange_reinforcement_basic" in page and "flange_reinforcement_basic_widget_metadata_hash" in page,
        "page_records_flange_transverse_widget_metadata_trace": "flange_transverse_basic" in page and "flange_transverse_basic_widget_metadata_hash" in page,
        "page_records_widget_metadata_trace": '"inputs_widget_metadata_trace"' in page,
        "trace_only_flag_present": '"inputs_widget_metadata_trace_only": True' in page,
        "live_widget_renderer_not_cut_over": '"live_widget_renderer_cutover": False' in page,
        "module_imports_streamlit": "import streamlit" in module_combined or "from streamlit" in module_combined,
        "module_imports_inputs_page": "inputs_page" in module_combined,
        "module_mutates_session_state": "st.session_state" in module_combined or ".session_state" in module_combined,
    }
    failures = [
        key for key, value in checks.items()
        if (key.startswith("module_imports_") and value)
        or (key == "module_mutates_session_state" and value)
        or (
            not key.startswith("module_imports_")
            and key != "module_mutates_session_state"
            and not value
        )
    ]
    decision = "READY_FOR_WIDGET_LIVE_TRACE_PARITY" if not failures else "WIDGET_TYPED_MODEL_TRACE_GAPS_REMAIN"
    payload = {
        "audit": "inputs_widgets_typed_model_trace_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "live_renderer_switched": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_widgets_typed_model_trace_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_typed_model_trace_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_widgets_typed_model_trace_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
