from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.design_guide import serviceability_preflight


APPLICATION = ROOT / "inputs_application" / "serviceability_preflight.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "serviceability_preflight.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _bind(overview: dict | Exception, calls: list[dict[str, Any]]) -> None:
    def collect_design_overview(state: dict) -> dict:
        calls.append({"kind": "overview", "state": dict(state)})
        if isinstance(overview, Exception):
            raise overview
        return dict(overview)

    def parse_util_value(value: Any) -> float | None:
        try:
            return float(value)
        except Exception:
            return None

    def build_blocker(*, state: dict, overview: dict, active_failures: list[str], evidence: dict) -> dict:
        calls.append(
            {
                "kind": "blocker",
                "state": dict(state),
                "active_failures": list(active_failures),
                "evidence": dict(evidence),
            }
        )
        return {
            "title_main": "Serviceability governs",
            "candidate_search_evidence": dict(evidence),
            "button_contract": {"mode": "blocked"},
            "guidance_intent": "blocked_serviceability",
        }

    serviceability_preflight.bind_serviceability_preflight_dependencies(
        {
            "_collect_design_overview": collect_design_overview,
            "_parse_util_value": parse_util_value,
            "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence": build_blocker,
        }
    )


def _case_results() -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    _bind(RuntimeError("overview failed"), calls)
    raised_result = serviceability_preflight._serviceability_governs_preflight_payload({"D": 600})

    calls_bending: list[dict[str, Any]] = []
    _bind({"statuses": {"bending": "FAIL", "crack": "FAIL"}}, calls_bending)
    bending_result = serviceability_preflight._serviceability_governs_preflight_payload({"D": 600})

    calls_crack: list[dict[str, Any]] = []
    crack_overview = {
        "statuses": {"crack": "FAIL", "deflection": "PASS"},
        "packs": {
            "crack": {
                "rows": [
                    {
                        "title": "Crack width",
                        "status": "FAIL",
                        "util": "1.23",
                        "value": "0.42 mm",
                        "limit": "0.30 mm",
                    }
                ]
            }
        },
    }
    _bind(crack_overview, calls_crack)
    crack_result = serviceability_preflight._serviceability_governs_preflight_payload({"D": 600})

    calls_deflection: list[dict[str, Any]] = []
    deflection_overview = {
        "statuses": {"deflection": "FAIL"},
        "packs": {"deflection": {"rows": [{"status": "FAIL", "calculated": "L/210", "requirement": "L/250"}]}},
    }
    _bind(deflection_overview, calls_deflection)
    deflection_result = serviceability_preflight._serviceability_governs_preflight_payload({"D": 600})

    crack_evidence = (
        (crack_result or {}).get("debug_trace", {}).get("candidate_search_evidence", {})
        if isinstance(crack_result, dict)
        else {}
    )
    deflection_debug = (deflection_result or {}).get("debug_trace", {}) if isinstance(deflection_result, dict) else {}

    return [
        {
            "name": "overview_exception_returns_none",
            "passed": raised_result is None,
            "calls": calls,
        },
        {
            "name": "bending_or_shear_failures_do_not_use_serviceability_preflight",
            "passed": bending_result is None and not any(row.get("kind") == "blocker" for row in calls_bending),
            "calls": calls_bending,
        },
        {
            "name": "crack_failure_builds_serviceability_governs_blocker_payload",
            "passed": isinstance(crack_result, dict)
            and len(crack_result.get("guidance_items") or []) == 1
            and crack_result["debug_trace"]["guidance_branch"] == "serviceability_governs_preflight_blocker"
            and crack_result["debug_trace"]["active_failures"] == ["crack"]
            and crack_evidence["selected_family_id"] == "SERVICEABILITY_GOVERNS"
            and crack_evidence["failed_check_name"] == "Crack width"
            and crack_evidence["failed_check_util"] == 1.23
            and crack_evidence["failed_check_demand"] == "0.42 mm"
            and crack_evidence["failed_check_capacity_or_limit"] == "0.30 mm"
            and any(row.get("kind") == "blocker" for row in calls_crack),
            "result": crack_result,
            "calls": calls_crack,
        },
        {
            "name": "deflection_failure_uses_deflection_primary_and_debug_contract",
            "passed": isinstance(deflection_result, dict)
            and deflection_debug["active_failures"] == ["deflection"]
            and deflection_debug["primary_button_contract"] == {"mode": "blocked"}
            and deflection_debug["primary_guidance_intent"] == "blocked_serviceability"
            and deflection_debug["candidate_search_evidence"]["failed_check_name"]
            == "deflection serviceability check",
            "result": deflection_result,
            "calls": calls_deflection,
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Serviceability Preflight Extraction",
        "",
        f"## Decision: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    application_source = _read(APPLICATION)
    module_source = _read(MODULE)
    application_helper = _function_source(application_source, "serviceability_governs_preflight_payload")
    module_helper = _function_source(module_source, "_serviceability_governs_preflight_payload")
    cases = _case_results()
    checks = {
        "application_exists": APPLICATION.exists(),
        "application_owns_preflight_body": "SERVICEABILITY_GOVERNS" in application_helper
        and "serviceability_preflight_family_route" in application_helper,
        "page_export_is_thin_delegate": len(module_helper.splitlines()) <= 18,
        "page_export_binds_compatibility_dependencies": "def bind_serviceability_preflight_dependencies" in module_source,
        "page_export_delegates_to_application": "serviceability_governs_preflight_payload(state, runtime=runtime)" in module_helper,
        "page_export_removed_preflight_body": "SERVICEABILITY_GOVERNS" not in module_helper,
        "application_does_not_import_page_modules": "inputs_page_modules" not in application_source,
        "application_does_not_import_bridge": "inputs_page_app_contract_bridge" not in application_source,
        "application_does_not_import_streamlit": "import streamlit" not in application_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = "INPUTS_PAGE_SERVICEABILITY_PREFLIGHT_EXTRACTION_LOCKED" if not failures else "GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_serviceability_preflight_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "case_results": cases,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_serviceability_preflight_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_serviceability_preflight_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_serviceability_preflight_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
