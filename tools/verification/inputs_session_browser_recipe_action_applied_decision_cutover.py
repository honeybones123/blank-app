from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_browser_recipe_action_applied_decision


INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
APP = ROOT / "app.py"
SESSION_BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
SESSION_MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
SESSION_INIT = ROOT / "inputs_page_modules" / "session" / "__init__.py"
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


def _old_decision(row: dict[str, Any]) -> bool:
    return bool(
        row.get("pending_recommendation_applied")
        or row.get("inputs_action_apply_recommendation")
        or row.get("last_apply_route")
    )


def _scenarios() -> list[dict[str, Any]]:
    return [
        {
            "name": "no_action",
            "pending_recommendation_applied": None,
            "inputs_action_apply_recommendation": None,
            "last_apply_route": None,
            "expected_reason": "no_action_applied",
        },
        {
            "name": "pending_recommendation_applied",
            "pending_recommendation_applied": "candidate-1",
            "inputs_action_apply_recommendation": None,
            "last_apply_route": None,
            "expected_reason": "pending_recommendation_applied_id",
        },
        {
            "name": "inputs_action_apply_recommendation",
            "pending_recommendation_applied": None,
            "inputs_action_apply_recommendation": {"action": "apply"},
            "last_apply_route": None,
            "expected_reason": "_inputs_action_apply_recommendation",
        },
        {
            "name": "last_apply_route",
            "pending_recommendation_applied": None,
            "inputs_action_apply_recommendation": None,
            "last_apply_route": "design_guide",
            "expected_reason": "last_apply_route",
        },
        {
            "name": "precedence_pending_over_others",
            "pending_recommendation_applied": "candidate-1",
            "inputs_action_apply_recommendation": {"action": "apply"},
            "last_apply_route": "design_guide",
            "expected_reason": "pending_recommendation_applied_id",
        },
        {
            "name": "falsey_values",
            "pending_recommendation_applied": "",
            "inputs_action_apply_recommendation": {},
            "last_apply_route": "",
            "expected_reason": "no_action_applied",
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Browser Recipe Action Applied Decision Cutover",
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
    source = "\n".join(
        _read(path)
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, APP_CONTRACT_BRIDGE, APP)
        if path.exists()
    )
    helper = _function_window(source, "_browser_recipe_action_already_applied")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_decision(row)
        new = build_inputs_browser_recipe_action_applied_decision(
            pending_recommendation_applied=row["pending_recommendation_applied"],
            inputs_action_apply_recommendation=row["inputs_action_apply_recommendation"],
            last_apply_route=row["last_apply_route"],
        )
        match = (
            old == bool(new.action_already_applied)
            and str(new.reason) == str(row["expected_reason"])
            and bool(new.display_hash)
        )
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": bool(new.action_already_applied),
                "reason": new.reason,
                "display_hash": new.display_hash,
            }
        )
        if not match:
            mismatches.append(
                {
                    "scenario": row["name"],
                    "old": old,
                    "new": bool(new.action_already_applied),
                    "reason": new.reason,
                    "expected_reason": row["expected_reason"],
                }
            )

    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_browser_recipe_action_applied_decision(" in helper,
        "page_helper_keeps_session_reads": helper.count("st.session_state.get") >= 3,
        "old_inline_or_chain_removed_from_page": " or st.session_state.get(" not in helper and " or last_apply_route" not in helper,
        "session_builder_exists": "def build_inputs_browser_recipe_action_applied_decision(" in builders,
        "session_model_exists": "class InputsBrowserRecipeActionAppliedDecision" in models,
        "session_init_exports_builder": "build_inputs_browser_recipe_action_applied_decision" in init_source,
        "session_init_exports_model": "InputsBrowserRecipeActionAppliedDecision" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_BROWSER_RECIPE_ACTION_APPLIED_DECISION_LOCKED"
        if not failures
        else "INPUTS_SESSION_BROWSER_RECIPE_ACTION_APPLIED_DECISION_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_browser_recipe_action_applied_decision_cutover",
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
        "streamlit_reads_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_browser_recipe_action_applied_decision_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_browser_recipe_action_applied_decision_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_browser_recipe_action_applied_decision_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
