from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_landing_dashboard_visibility_decision


INPUTS_PAGE = ROOT / "inputs_page.py"
LANDING_HELPERS = ROOT / "inputs_page_modules" / "landing.py"
SESSION_BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
SESSION_MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    window = source.split(marker, 1)[1].split("\ndef ", 1)[0]
    return window.split("\n", 1)[1] if "\n" in window else window


def _old_decision(
    *,
    same_page: bool,
    design_values: dict[str, Any],
    load_values: dict[str, Any],
    capacity_context_matches: bool,
) -> bool:
    def _num(value: Any) -> float:
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    if same_page:
        return False
    no_design_actions = all(abs(_num(value)) < 1e-15 for value in design_values.values())
    no_loads = all(abs(_num(value)) < 1e-15 for value in load_values.values())
    if no_design_actions and no_loads:
        return not bool(capacity_context_matches)
    return False


def _scenarios() -> list[dict[str, Any]]:
    zero_design = {
        "uls_Mstar": 0,
        "uls_Vstar": 0,
        "sls_Mstar": 0,
        "sls_Vstar": 0,
        "sls_Nstar": 0,
        "Tu_star": 0,
        "uls_Nstar_or_N_star": 0,
        "P_star": 0,
    }
    zero_load = {"g_udl_kNm_per_m": 0, "q_udl_kNm_per_m": 0}
    return [
        {"name": "empty_show", "same": False, "design": zero_design, "load": zero_load, "capacity": False},
        {"name": "same_page_suppressed", "same": True, "design": zero_design, "load": zero_load, "capacity": False},
        {"name": "capacity_context_suppressed", "same": False, "design": zero_design, "load": zero_load, "capacity": True},
        {"name": "uls_action_present", "same": False, "design": {**zero_design, "uls_Mstar": 1.0}, "load": zero_load, "capacity": False},
        {"name": "load_present", "same": False, "design": zero_design, "load": {"g_udl_kNm_per_m": 0.1, "q_udl_kNm_per_m": 0}, "capacity": False},
        {"name": "invalid_string_zero", "same": False, "design": {**zero_design, "P_star": "x"}, "load": zero_load, "capacity": False},
        {"name": "at_tolerance_action", "same": False, "design": {**zero_design, "Tu_star": 1e-15}, "load": zero_load, "capacity": False},
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Landing Dashboard Visibility Decision Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenarios'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- product behavior changed: `{payload['product_behavior_changed']}`",
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
    source = _read(LANDING_HELPERS)
    helper = _function_window(source, "inputs_show_landing_dashboard")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_decision(
            same_page=row["same"],
            design_values=row["design"],
            load_values=row["load"],
            capacity_context_matches=row["capacity"],
        )
        new = build_inputs_landing_dashboard_visibility_decision(
            same_page_rerun_has_non_landing_state=row["same"],
            design_action_values=row["design"],
            load_values=row["load"],
            capacity_context_matches=row["capacity"],
        )
        match = old == bool(new.show_landing_dashboard)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": bool(new.show_landing_dashboard),
                "reason": new.reason,
                "display_hash": new.display_hash,
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": old, "new": bool(new.show_landing_dashboard)})
    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_landing_dashboard_visibility_decision(" in helper,
        "page_helper_keeps_get_param_fallback": "get_param_fn" in helper,
        "page_helper_keeps_capacity_context_argument": "capacity_context_matches" in helper,
        "old_local_no_design_boolean_removed": "no_design_actions =" not in helper and "no_loads =" not in helper,
        "session_builder_exists": "def build_inputs_landing_dashboard_visibility_decision(" in builders,
        "session_model_exists": "class InputsLandingDashboardVisibilityDecision" in models,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "INPUTS_SESSION_LANDING_DASHBOARD_VISIBILITY_DECISION_LOCKED" if not failures else "INPUTS_SESSION_LANDING_DASHBOARD_VISIBILITY_DECISION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_landing_dashboard_visibility_decision_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenarios": scenario_results,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_landing_dashboard_visibility_decision_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_landing_dashboard_visibility_decision_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_landing_dashboard_visibility_decision_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
