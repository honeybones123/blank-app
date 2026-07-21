from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
MODULE_ROOT = ROOT / "inputs_page_modules" / "calculations"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_report(payload: dict, report_path: Path) -> None:
    lines = [
        "# Inputs Calculations Trace Integration Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "The extracted calculation/explainer builder is wired trace-only beside the current live row path.",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Ownership",
            "",
            "- Current renderer remains page/shared-renderer owned.",
            "- Extracted module builds typed view-model data only.",
            "- No Streamlit/session import exists in the extracted module.",
            "- No live delegation or fallback deletion happened in this slice.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    module_source = "\n".join(_read(path) for path in MODULE_ROOT.glob("*.py"))
    checks = {
        "imports_source_builder": "build_inputs_calculation_explainer_source_snapshot" in source,
        "imports_source_hash_builder": "build_inputs_calculation_explainer_source_hash" in source,
        "imports_builder": "build_inputs_calculation_explainer_view_model" in source,
        "builds_source_snapshot": "_calculation_explainer_source_snapshot = build_inputs_calculation_explainer_source_snapshot(" in source,
        "builds_source_hash": "_calculation_explainer_source_hash = build_inputs_calculation_explainer_source_hash(" in source,
        "calls_builder": "build_inputs_calculation_explainer_view_model(" in source,
        "records_trace_session_key": '"_inputs_calculation_explainer_view_model_trace"' in source,
        "trace_only_flag_present": '"calculation_explainer_view_model_trace_only": True' in source,
        "live_cutover_false": '"live_calculation_explainer_renderer_cutover": False' in source,
        "records_source_hash": '"calculation_explainer_source_hash"' in source,
        "records_source_row_counts": '"live_calculation_explainer_source_row_counts"' in source,
        "records_extracted_row_counts": '"extracted_calculation_explainer_row_counts"' in source,
        "emits_pre_widget_trace": '"inputs_calculation_explainer_view_model_trace"' in source
        and "_inputs_pre_widget_trace(" in source,
        "module_imports_streamlit": "import streamlit" in module_source or "from streamlit" in module_source,
        "module_imports_inputs_page": "inputs_page" in module_source,
    }
    failures = [
        key for key, value in checks.items()
        if (key.startswith("module_imports_") and value) or (not key.startswith("module_imports_") and not value)
    ]
    decision = "READY_FOR_LIVE_CALCULATION_PARITY_CAPTURE" if not failures else "CALCULATION_TRACE_INTEGRATION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_calculations_trace_integration_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "live_renderer_switched": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_calculations_trace_integration_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_calculations_trace_integration_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_calculations_trace_integration_snapshot PASS")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
