from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _sample_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "BENDING_ROWS": [
            {"uid": "flexure_capacity", "status": "PASS"},
            {"uid": "unknown_bending", "status": "FAIL", "tab": "custom"},
            {"uid": "info_bending", "status": "INFO", "is_informational": True},
        ],
        "SHEAR_ROWS": [
            {"uid": "shear_capacity", "status": "NEAR LIMIT"},
            {"uid": "unknown_shear", "status": "NG"},
        ],
        "CRACK_ROWS": [
            {"uid": "crack_width", "status": "PASS", "ok": False},
            {"uid": "crack_info", "status": "INFO"},
        ],
        "DEFLECTION_ROWS": [
            {"uid": "deflection_total", "status": "FAIL"},
            {"uid": "deflection_unknown"},
        ],
    }


def _run(module: Any, *, legacy: bool, skip: bool) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    rows = copy.deepcopy(_sample_rows())
    calls: list[dict[str, Any]] = []

    def update_active_beam_summary_from_results(**kwargs: Any) -> None:
        calls.append(copy.deepcopy(kwargs))

    if legacy:
        originals = {"update": legacy_inputs_page.update_active_beam_summary_from_results}
        try:
            legacy_inputs_page.update_active_beam_summary_from_results = update_active_beam_summary_from_results
            module.render_inputs_summary_row_finalization_current_coordinator(
                skip_active_beam_record_write=skip,
                **rows,
            )
        finally:
            legacy_inputs_page.update_active_beam_summary_from_results = originals["update"]
    else:
        originals = {"update": route_bridge.update_active_beam_summary_from_results}
        try:
            route_bridge.update_active_beam_summary_from_results = update_active_beam_summary_from_results
            module.render_inputs_summary_row_finalization_current_coordinator(
                skip_active_beam_record_write=skip,
                **rows,
            )
        finally:
            route_bridge.update_active_beam_summary_from_results = originals["update"]
    return {"rows": rows, "calls": calls}


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    for case_name, skip in (("write", False), ("skip", True)):
        legacy_result = _run(legacy_inputs_page, legacy=True, skip=skip)
        route_result = _run(route_bridge, legacy=False, skip=skip)
        cases[case_name] = {"legacy": legacy_result, "route": route_result}
        checks[f"{case_name}_rows_match_legacy"] = legacy_result["rows"] == route_result["rows"]
        checks[f"{case_name}_update_calls_match_legacy"] = legacy_result["calls"] == route_result["calls"]

    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["route_does_not_delegate_summary_row_finalization"] = (
        "_legacy_inputs_page.render_inputs_summary_row_finalization_current_coordinator" not in route_source
    )
    checks["skip_mode_does_not_write_summary"] = len(cases["skip"]["route"]["calls"]) == 0
    checks["write_mode_writes_summary_once"] = len(cases["write"]["route"]["calls"]) == 1
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_summary_row_finalization_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "case_update_call_counts": {
            name: {
                "legacy": len(case["legacy"]["calls"]),
                "route": len(case["route"]["calls"]),
            }
            for name, case in cases.items()
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_summary_row_finalization_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_summary_row_finalization_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Summary Row Finalization Parity",
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
