from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_has_design_actions_or_loads_decision


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


def _old_decision(values: dict[str, Any], tolerance: float = 1e-15) -> bool:
    def _num(value: Any) -> float:
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    return any(abs(_num(value)) >= tolerance for value in values.values())


def _scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "all_zero", "values": {"uls_Mstar": 0.0, "uls_Vstar": 0.0}},
        {"name": "positive_moment", "values": {"uls_Mstar": 1.0, "uls_Vstar": 0.0}},
        {"name": "negative_proxy", "values": {"load_Mstar_neg_proxy": -2.5}},
        {"name": "string_number", "values": {"inputs_load_Vstar_proxy": "3.2"}},
        {"name": "none_and_blank", "values": {"uls_Nstar": None, "Tu_star": ""}},
        {"name": "invalid_string", "values": {"P_star": "not-a-number"}},
        {"name": "below_tolerance", "values": {"sls_Mstar": 1e-16}},
        {"name": "at_tolerance", "values": {"sls_Vstar": 1e-15}},
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Has Design Actions Or Loads Decision Cutover",
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
    helper = _function_window(source, "inputs_has_design_actions_or_loads")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_decision(row["values"])
        new = build_inputs_has_design_actions_or_loads_decision(action_values=row["values"])
        match = old == bool(new.has_design_actions_or_loads)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": bool(new.has_design_actions_or_loads),
                "nonzero_keys": list(new.nonzero_keys),
                "display_hash": new.display_hash,
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": old, "new": bool(new.has_design_actions_or_loads)})
    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_has_design_actions_or_loads_decision(" in helper,
        "page_helper_keeps_get_param_fallback": "get_param_fn" in helper,
        "page_helper_collects_explicit_action_values": "action_values = {" in helper,
        "old_numeric_policy_removed_from_page": "def _num(" not in helper and "abs(_num(" not in helper,
        "session_builder_exists": "def build_inputs_has_design_actions_or_loads_decision(" in builders,
        "session_model_exists": "class InputsHasDesignActionsOrLoadsDecision" in models,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "INPUTS_SESSION_HAS_DESIGN_ACTIONS_OR_LOADS_DECISION_LOCKED" if not failures else "INPUTS_SESSION_HAS_DESIGN_ACTIONS_OR_LOADS_DECISION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_has_design_actions_or_loads_decision_cutover",
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
    json_path = VERIFICATION_DIR / f"inputs_session_has_design_actions_or_loads_decision_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_has_design_actions_or_loads_decision_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_has_design_actions_or_loads_decision_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
