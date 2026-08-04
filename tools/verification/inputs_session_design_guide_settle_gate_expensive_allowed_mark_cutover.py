from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_settle_gate_expensive_allowed_mark


INPUTS_PAGE = ROOT / "inputs_page.py"
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


def _old_expensive_allowed_mark(
    gate_state: dict[str, Any],
    decision: dict[str, Any],
    *,
    current_timestamp: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    gate = dict(gate_state or {})
    gate["expensive_publication_count"] = int(gate.get("expensive_publication_count", 0) or 0) + 1
    if not gate.get("first_stable_publication_timestamp"):
        gate["first_stable_publication_timestamp"] = current_timestamp
    gate["expensive_publication_allowed_for_fingerprint"] = True
    next_decision = dict(decision or {})
    next_decision["expensive_publication_count"] = int(gate.get("expensive_publication_count", 0) or 0)
    next_decision["first_stable_publication_timestamp"] = gate.get("first_stable_publication_timestamp")
    return gate, next_decision


def _scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "empty_gate", "gate": {}, "decision": {}},
        {
            "name": "existing_count_no_timestamp",
            "gate": {"expensive_publication_count": 2, "current_fingerprint": "abc"},
            "decision": {"fingerprint": "abc", "snapshot_hit": True},
        },
        {
            "name": "existing_timestamp_preserved",
            "gate": {"expensive_publication_count": 5, "first_stable_publication_timestamp": "old-ts"},
            "decision": {"fingerprint_elapsed_ms": 2300.0},
        },
        {
            "name": "string_count",
            "gate": {"expensive_publication_count": "7"},
            "decision": {"required_settle_ms": 2200},
        },
        {
            "name": "none_count",
            "gate": {"expensive_publication_count": None},
            "decision": {"snapshot_hit": False},
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Settle Gate Expensive Allowed Mark Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenario_results'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- session writes moved: `{payload['session_writes_moved']}`",
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
    helper = _function_window(source, "_design_guide_settle_gate_mark_expensive_allowed")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)
    current_timestamp = "2026-07-15T22:00:00.000"

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old_gate, old_decision = _old_expensive_allowed_mark(
            dict(row["gate"]),
            dict(row["decision"]),
            current_timestamp=current_timestamp,
        )
        new = build_inputs_design_guide_settle_gate_expensive_allowed_mark(
            gate_state=dict(row["gate"]),
            decision=dict(row["decision"]),
            current_timestamp=current_timestamp,
        )
        match = old_gate == dict(new.gate_state) and old_decision == dict(new.decision) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old_gate": old_gate,
                "new_gate": dict(new.gate_state),
                "old_decision": old_decision,
                "new_decision": dict(new.decision),
                "display_hash_present": bool(new.display_hash),
            }
        )
        if not match:
            mismatches.append(
                {
                    "scenario": row["name"],
                    "old_gate": old_gate,
                    "new_gate": dict(new.gate_state),
                    "old_decision": old_decision,
                    "new_decision": dict(new.decision),
                }
            )

    checks = {
        "helper_delegates_to_session_builder": "build_inputs_design_guide_settle_gate_expensive_allowed_mark(" in helper,
        "helper_keeps_timestamp_creation": "datetime.now().isoformat(timespec=\"milliseconds\")" in helper,
        "helper_keeps_session_write": "st.session_state[DESIGN_GUIDE_FAMILY_SETTLE_GATE_KEY]" in helper,
        "helper_keeps_trace": "_inputs_pre_widget_trace(" in helper,
        "old_inline_increment_removed": "gate[\"expensive_publication_count\"] = int(" not in helper,
        "old_inline_timestamp_policy_removed": "if not gate.get(\"first_stable_publication_timestamp\")" not in helper,
        "old_inline_decision_update_removed": "decision[\"expensive_publication_count\"] = int(" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_settle_gate_expensive_allowed_mark(" in builders,
        "session_model_exists": "class InputsDesignGuideSettleGateExpensiveAllowedMark" in models,
        "session_init_exports_builder": "build_inputs_design_guide_settle_gate_expensive_allowed_mark" in init_source,
        "session_init_exports_model": "InputsDesignGuideSettleGateExpensiveAllowedMark" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_EXPENSIVE_ALLOWED_MARK_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_EXPENSIVE_ALLOWED_MARK_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_settle_gate_expensive_allowed_mark_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenario_results": scenario_results,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "session_reads_moved": False,
        "session_writes_moved": False,
        "timestamp_creation_moved": False,
        "trace_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_settle_gate_expensive_allowed_mark_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_settle_gate_expensive_allowed_mark_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_settle_gate_expensive_allowed_mark_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
