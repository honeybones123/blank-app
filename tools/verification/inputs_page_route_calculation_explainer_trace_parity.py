from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "BENDING_ROWS": [
            {"uid": "bend_1", "label": "Bending", "status": "PASS", "utilisation": "0.82"},
        ],
        "SHEAR_ROWS": [
            {"uid": "shear_1", "label": "Shear", "status": "NEAR LIMIT", "utilisation": "0.94"},
        ],
        "CRACK_ROWS": [
            {"uid": "crack_1", "label": "Crack", "status": "PASS", "utilisation": "0.61"},
        ],
        "DEFLECTION_ROWS": [
            {"uid": "defl_1", "label": "Deflection", "status": "FAIL", "utilisation": "1.08"},
        ],
    }


def _run_route(module: Any) -> dict[str, Any]:
    traces: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {}
    fake_st = SimpleNamespace(session_state=session_state)

    def trace_fn(*args, **kwargs):
        traces.append({"args": list(args), "kwargs": dict(kwargs)})

    rows = _rows()
    from inputs_page_modules.summaries.pipeline import (
        InputsSummaryCalculationSource,
    )

    summary_source = InputsSummaryCalculationSource(
        bending_rows=tuple(rows["BENDING_ROWS"]),
        shear_rows=tuple(rows["SHEAR_ROWS"]),
        crack_rows=tuple(rows["CRACK_ROWS"]),
        deflection_rows=tuple(rows["DEFLECTION_ROWS"]),
        results_version=7,
        summary_action_fp=("a", 1),
    )
    original_st = module.st
    try:
        module.st = fake_st
        module.render_inputs_calculation_fragment_current_coordinator(
            summary_source=summary_source,
            trace_fn=trace_fn,
        )
    finally:
        module.st = original_st
    return {"traces": traces, "session_state": session_state}


def _run_module() -> dict[str, Any]:
    from inputs_page_modules.calculations.trace import render_inputs_calculation_explainer_trace

    traces: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {}
    fake_st = SimpleNamespace(session_state=session_state)

    def trace_fn(*args, **kwargs):
        traces.append({"args": list(args), "kwargs": dict(kwargs)})

    rows = _rows()
    render_inputs_calculation_explainer_trace(
        st_module=fake_st,
        **rows,
        results_version=7,
        summary_action_fp=("a", 1),
        trace_fn=trace_fn,
    )
    return {"traces": traces, "session_state": session_state}


def main() -> int:
    from inputs_application.page_runtime import calculations as calculation_owner

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    module_result = _run_module()
    route_result = _run_route(calculation_owner)
    route_source = (
        ROOT / "inputs_application" / "page_runtime" / "calculations.py"
    ).read_text(
        encoding="utf-8",
        errors="replace",
    )
    module_source = (ROOT / "inputs_page_modules" / "calculations" / "trace.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks = {
        "trace_events_match_module": module_result["traces"] == route_result["traces"],
        "session_trace_matches_module": module_result["session_state"].get(
            "_inputs_calculation_explainer_view_model_trace"
        )
        == route_result["session_state"].get("_inputs_calculation_explainer_view_model_trace"),
        "typed_owner_delegates_to_calculation_trace_module": (
            "render_inputs_calculation_explainer_trace(" in route_source
        ),
        "module_builds_calculation_view_model": (
            "build_inputs_calculation_explainer_view_model(" in module_source
        ),
        "typed_owner_does_not_import_legacy_bridges": (
            "inputs_page_route_coordinators" not in route_source
            and "inputs_page_app_contract_bridge" not in route_source
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_calculation_explainer_trace_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "trace_payload_keys": sorted(
            (route_result["session_state"].get("_inputs_calculation_explainer_view_model_trace") or {}).keys()
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_calculation_explainer_trace_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_calculation_explainer_trace_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Calculation Explainer Trace Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *(f"- `{name}`: `{passed}`" for name, passed in checks.items()),
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
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
