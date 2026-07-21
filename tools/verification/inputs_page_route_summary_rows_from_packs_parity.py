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


def _packs() -> dict[str, Any]:
    return {
        "bend_pack": {
            "rows": [
                {"uid": "bend", "title": "Bend", "calculated": "100", "requirement": "80", "status": "PASS"},
                {"uid": "bend_info", "status": "INFO", "is_informational": True},
            ]
        },
        "shear_pack": {
            "rows": [
                {"uid": "shear_row", "value": "50", "limit": "60", "status": "FAIL", "util": "1.2"},
            ],
            "summary_rows": [
                {"uid": "shear_summary", "capacity": "90", "action": "70", "status": "PASS"},
            ],
            "mcft_detail_rows": [
                {"uid": "shear_mcft", "capacity": "95", "action": "80", "status": "NEAR LIMIT"},
            ],
        },
        "crack_pack": {
            "rows": [
                {"uid": "crack", "capacity": "", "calculated": "0.25", "requirement": "0.30", "status": "PASS"},
            ]
        },
        "defl_pack": {
            "rows": [
                {"uid": "defl", "value": "12", "limit": "20", "status": "WARN"},
            ],
            "summary_delta_total_mm": 12.3,
            "summary_defl_limit_mm": 20.0,
            "summary_util_total": 0.615,
        },
    }


def _run(module: Any, *, legacy: bool, show_mcft: bool, missing: bool) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    packs = copy.deepcopy(_packs())
    if missing:
        packs["bend_pack"] = None
        packs["shear_pack"] = None
        packs["crack_pack"] = None
        packs["defl_pack"] = None
    fake_st = SimpleNamespace(session_state={"show_mcft_breakdown": show_mcft})
    if legacy:
        originals = {"st": legacy_inputs_page.st}
        try:
            legacy_inputs_page.st = fake_st
            result = module.render_inputs_summary_rows_from_packs_current_coordinator(**packs)
        finally:
            legacy_inputs_page.st = originals["st"]
    else:
        originals = {"st": route_bridge.st}
        try:
            route_bridge.st = fake_st
            result = module.render_inputs_summary_rows_from_packs_current_coordinator(**packs)
        finally:
            route_bridge.st = originals["st"]
    return {"result": result}


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    reference_module = legacy_inputs_page
    reference_is_legacy = hasattr(
        legacy_inputs_page,
        "render_inputs_summary_rows_from_packs_current_coordinator",
    )
    if not reference_is_legacy:
        reference_module = route_bridge
    for case_name, show_mcft, missing in (
        ("normal_no_mcft", False, False),
        ("normal_with_mcft", True, False),
        ("missing_packs", False, True),
    ):
        legacy_result = _run(
            reference_module,
            legacy=reference_is_legacy,
            show_mcft=show_mcft,
            missing=missing,
        )
        route_result = _run(
            route_bridge,
            legacy=False,
            show_mcft=show_mcft,
            missing=missing,
        )
        cases[case_name] = {"legacy": legacy_result, "route": route_result}
        checks[f"{case_name}_result_matches_legacy"] = legacy_result["result"] == route_result["result"]

    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["route_does_not_delegate_summary_rows_from_packs"] = (
        "_legacy_inputs_page.render_inputs_summary_rows_from_packs_current_coordinator" not in route_source
    )
    checks["mcft_case_includes_extra_row"] = len(cases["normal_with_mcft"]["route"]["result"][1]) == 2
    checks["missing_case_marks_all_errors"] = cases["missing_packs"]["route"]["result"][4:8] == (
        True,
        True,
        True,
        True,
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_summary_rows_from_packs_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "case_row_counts": {
            name: {
                "legacy": [len(part) if isinstance(part, list) else part for part in case["legacy"]["result"][:4]],
                "route": [len(part) if isinstance(part, list) else part for part in case["route"]["result"][:4]],
            }
            for name, case in cases.items()
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_summary_rows_from_packs_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_summary_rows_from_packs_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Summary Rows From Packs Parity",
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
