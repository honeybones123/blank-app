from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_settle_gate_waiting_mark


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


def _old_waiting_mark(gate_state: dict[str, Any], decision: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    gate = dict(gate_state or {})
    next_decision = dict(decision or {})
    gate["skipped_expensive_publication_count"] = int(
        gate.get("skipped_expensive_publication_count", 0) or 0
    ) + 1
    next_decision["skipped_expensive_publication_count"] = int(
        gate.get("skipped_expensive_publication_count", 0) or 0
    )
    return gate, next_decision


def _scenarios() -> list[dict[str, Any]]:
    return [
        {
            "name": "empty_gate_empty_decision",
            "gate": {},
            "decision": {},
        },
        {
            "name": "existing_count",
            "gate": {"skipped_expensive_publication_count": 4, "current_fingerprint": "abc"},
            "decision": {"fingerprint": "abc", "fingerprint_elapsed_ms": 100.0},
        },
        {
            "name": "string_count",
            "gate": {"skipped_expensive_publication_count": "7"},
            "decision": {"required_settle_ms": 2200},
        },
        {
            "name": "none_count",
            "gate": {"skipped_expensive_publication_count": None},
            "decision": {"snapshot_hit": False},
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Settle Gate Waiting Mark Cutover",
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
    helper = _function_window(source, "_design_guide_settle_gate_mark_waiting")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old_gate, old_decision = _old_waiting_mark(dict(row["gate"]), dict(row["decision"]))
        new = build_inputs_design_guide_settle_gate_waiting_mark(
            gate_state=dict(row["gate"]),
            decision=dict(row["decision"]),
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
        "helper_delegates_to_session_builder": "build_inputs_design_guide_settle_gate_waiting_mark(" in helper,
        "helper_keeps_session_write": "st.session_state[DESIGN_GUIDE_FAMILY_SETTLE_GATE_KEY]" in helper,
        "helper_keeps_trace": "_inputs_pre_widget_trace(" in helper,
        "old_inline_increment_removed": "skipped_expensive_publication_count\"] = int(" not in helper
        and "skipped_expensive_publication_count\", 0) or 0" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_settle_gate_waiting_mark(" in builders,
        "session_model_exists": "class InputsDesignGuideSettleGateWaitingMark" in models,
        "session_init_exports_builder": "build_inputs_design_guide_settle_gate_waiting_mark" in init_source,
        "session_init_exports_model": "InputsDesignGuideSettleGateWaitingMark" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_WAITING_MARK_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_WAITING_MARK_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_settle_gate_waiting_mark_cutover",
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
        "trace_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_settle_gate_waiting_mark_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_settle_gate_waiting_mark_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_settle_gate_waiting_mark_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
