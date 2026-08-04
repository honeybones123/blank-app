from __future__ import annotations

import copy
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


def _base_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "BENDING_ROWS": [
            {"uid": "bend", "capacity": "120", "action": "90", "util": "0.75", "status": "PASS", "is_primary": True},
        ],
        "SHEAR_ROWS": [
            {"uid": "shear", "capacity": "100", "action": "80", "util": "0.80", "status": "PASS", "is_primary": True},
        ],
        "CRACK_ROWS": [
            {"uid": "crack", "capacity": "0.30", "action": "0.22", "util": "0.73", "status": "PASS"},
        ],
        "DEFLECTION_ROWS": [
            {"uid": "defl", "capacity": "20", "action": "11", "util": "0.55", "status": "PASS", "is_primary": True},
        ],
    }


def _case(case_name: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[dict[str, Any]]]]:
    rows = _base_rows()
    summary_state = {
        "Mu_star": 100.0,
        "Vu_star": 80.0,
        "Tu_star": 0.0,
        "sls_Mstar": 50.0,
        "sls_Vstar": 20.0,
        "sigma_sr": 150.0,
    }
    shear_pack = {
        "summary_display_capacity": "100 kN",
        "summary_display_demand": "80 kN",
        "summary_util": "0.80",
        "summary_status": "PASS",
        "summary_reason": "",
        "summary_governing_check_name": "Sectional shear capacity",
        "summary_governing_source": "canonical",
        "summary_display_source": "canonical",
    }
    if case_name == "spacing_fail":
        shear_pack.update(
            {
                "summary_status": "FAIL",
                "summary_reason": "link spacing exceeds limit",
                "summary_governing_check_name": "Link spacing",
            }
        )
    elif case_name == "fallback":
        shear_pack.update({"summary_status": "", "summary_display_capacity": "", "summary_display_demand": ""})
    elif case_name == "inconsistent_header":
        shear_pack.update(
            {
                "summary_status": "FAIL",
                "summary_util": "0.80",
                "summary_reason": "stale failure",
                "summary_governing_check_name": "stale",
            }
        )
    elif case_name == "sectional_required_shear":
        shear_pack.update(
            {
                "summary_display_source": "sectional_required_shear",
                "summary_util": "9.99",
                "summary_phiVu_kN": 200.0,
                "summary_Veq_kN": 120.0,
            }
        )
    elif case_name == "no_loads":
        summary_state.update(
            {
                "Mu_star": 0.0,
                "Vu_star": 0.0,
                "Tu_star": 0.0,
                "sls_Mstar": 0.0,
                "sls_Vstar": 0.0,
                "sigma_sr": 0.0,
            }
        )
    return summary_state, shear_pack, rows


def _run(module: Any, *, legacy: bool, case_name: str) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    summary_state, shear_pack, rows = _case(case_name)
    rows = copy.deepcopy(rows)
    fake_st = SimpleNamespace(session_state={})
    kwargs = {
        "summary_state": copy.deepcopy(summary_state),
        "shear_pack": copy.deepcopy(shear_pack),
        **rows,
    }
    if legacy:
        originals = {"st": legacy_inputs_page.st}
        try:
            legacy_inputs_page.st = fake_st
            result = module.render_inputs_summary_display_state_current_coordinator(**kwargs)
        finally:
            legacy_inputs_page.st = originals["st"]
    else:
        originals = {"st": route_bridge.st}
        try:
            route_bridge.st = fake_st
            result = module.render_inputs_summary_display_state_current_coordinator(**kwargs)
        finally:
            route_bridge.st = originals["st"]
    return {
        "result": result,
        "rows": {name: kwargs[name] for name in ("BENDING_ROWS", "SHEAR_ROWS", "CRACK_ROWS", "DEFLECTION_ROWS")},
        "session_state": dict(fake_st.session_state),
    }


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    reference_module = legacy_inputs_page
    reference_is_legacy = hasattr(
        legacy_inputs_page,
        "render_inputs_summary_display_state_current_coordinator",
    )
    if not reference_is_legacy:
        reference_module = route_bridge
    for case_name in (
        "canonical",
        "spacing_fail",
        "fallback",
        "inconsistent_header",
        "sectional_required_shear",
        "no_loads",
    ):
        legacy_result = _run(reference_module, legacy=reference_is_legacy, case_name=case_name)
        route_result = _run(route_bridge, legacy=False, case_name=case_name)
        cases[case_name] = {"legacy": legacy_result, "route": route_result}
        checks[f"{case_name}_result_matches_legacy"] = legacy_result["result"] == route_result["result"]
        checks[f"{case_name}_rows_match_legacy"] = legacy_result["rows"] == route_result["rows"]
        checks[f"{case_name}_session_debug_matches_legacy"] = legacy_result["session_state"] == route_result["session_state"]

    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["route_does_not_delegate_summary_display_state"] = (
        "_legacy_inputs_page.render_inputs_summary_display_state_current_coordinator" not in route_source
    )
    checks["inconsistent_header_overrides_to_pass"] = cases["inconsistent_header"]["route"]["result"][8] == "PASS"
    checks["no_loads_neutralizes_all_statuses"] = all(
        row.get("status") == "\u2014"
        for rows in cases["no_loads"]["route"]["rows"].values()
        for row in rows
        if not row.get("is_informational")
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_summary_display_state_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "case_result_summaries": {
            name: {
                "shear_status": case["route"]["result"][8],
                "shear_note": case["route"]["result"][10],
                "debug": case["route"]["session_state"].get("_inputs_visible_shear_summary_debug"),
            }
            for name, case in cases.items()
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_summary_display_state_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_summary_display_state_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Summary Display State Parity",
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
