from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_same_page_rerun_non_landing_decision


INPUTS_PAGE = ROOT / "inputs_page.py"
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


def _old_decision(dispatch_state: Any, cached_results: Any, bundle: Any) -> bool:
    if not dispatch_state:
        return False
    if isinstance(cached_results, dict) and bool(cached_results):
        return True
    if isinstance(bundle, dict):
        verifier = dict(bundle.get("final_publication_verifier_payload") or {})
        render_trace = dict(bundle.get("design_guide_render_eligibility_trace") or {})
        overview = dict(bundle.get("current_overview") or bundle.get("overview") or {})
        if any(
            bool(value)
            for value in (
                verifier.get("publication_hash"),
                verifier.get("selected_family_id"),
                verifier.get("outcome_state"),
                render_trace.get("contract_required_design_brain_eligibility"),
                overview.get("all_key_pass"),
                overview.get("any_fail"),
                bundle.get("active_failures"),
                bundle.get("active_failure_keys"),
            )
        ):
            return True
    return False


def _scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "no_dispatch", "dispatch": None, "cached": {"x": 1}, "bundle": {"active_failures": ["x"]}},
        {"name": "dispatch_no_state", "dispatch": True, "cached": {}, "bundle": {}},
        {"name": "cached_results", "dispatch": True, "cached": {"result": 1}, "bundle": {}},
        {
            "name": "publication_hash",
            "dispatch": True,
            "cached": {},
            "bundle": {"final_publication_verifier_payload": {"publication_hash": "abc"}},
        },
        {
            "name": "render_contract_required",
            "dispatch": True,
            "cached": {},
            "bundle": {"design_guide_render_eligibility_trace": {"contract_required_design_brain_eligibility": True}},
        },
        {"name": "overview_pass", "dispatch": True, "cached": {}, "bundle": {"current_overview": {"all_key_pass": True}}},
        {"name": "overview_fail", "dispatch": True, "cached": {}, "bundle": {"overview": {"any_fail": True}}},
        {"name": "active_failures", "dispatch": True, "cached": {}, "bundle": {"active_failures": ["bending"]}},
        {"name": "active_failure_keys", "dispatch": True, "cached": {}, "bundle": {"active_failure_keys": ["shear"]}},
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Same-Page Rerun Non-Landing Decision Cutover",
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
    source = _read(INPUTS_PAGE)
    helper = _function_window(source, "_inputs_same_page_rerun_has_non_landing_state")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_decision(row["dispatch"], row["cached"], row["bundle"])
        new = build_inputs_same_page_rerun_non_landing_decision(
            dispatch_state=row["dispatch"],
            cached_results=row["cached"],
            debug_bundle=row["bundle"],
        )
        match = old == bool(new.should_suppress_landing)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": bool(new.should_suppress_landing),
                "reason": new.reason,
                "display_hash": new.display_hash,
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": old, "new": bool(new.should_suppress_landing)})
    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_same_page_rerun_non_landing_decision(" in helper,
        "page_helper_keeps_session_reads": "st.session_state.get" in helper,
        "old_indicator_policy_removed_from_page": "publication_hash" not in helper
        and "contract_required_design_brain_eligibility" not in helper
        and "active_failure_keys" not in helper,
        "session_builder_exists": "def build_inputs_same_page_rerun_non_landing_decision(" in builders,
        "session_model_exists": "class InputsSamePageRerunNonLandingDecision" in models,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "INPUTS_SESSION_SAME_PAGE_RERUN_NON_LANDING_DECISION_LOCKED" if not failures else "INPUTS_SESSION_SAME_PAGE_RERUN_NON_LANDING_DECISION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_same_page_rerun_non_landing_decision_cutover",
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
    json_path = VERIFICATION_DIR / f"inputs_session_same_page_rerun_non_landing_decision_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_same_page_rerun_non_landing_decision_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_same_page_rerun_non_landing_decision_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
