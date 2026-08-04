from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_settle_gate_fingerprint_update


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


def _old_fingerprint_update(
    *,
    gate_state: Mapping[str, Any],
    fingerprint: Any,
    current_perf: float,
    current_timestamp: str,
) -> dict[str, Any]:
    gate = dict(gate_state or {})
    fp_text = str(fingerprint)
    previous_fp = str(gate.get("current_fingerprint") or "")
    if previous_fp and previous_fp != fp_text:
        gate["fingerprint_changes_seen"] = int(gate.get("fingerprint_changes_seen", 0) or 0) + 1
    if previous_fp != fp_text:
        gate["current_fingerprint"] = fp_text
        gate["first_seen_perf"] = current_perf
        gate["first_seen_timestamp"] = current_timestamp
        gate["last_seen_perf"] = current_perf
        gate["last_seen_timestamp"] = current_timestamp
        gate["stable_for_fingerprint"] = False
        gate["expensive_publication_allowed_for_fingerprint"] = False
    else:
        gate["last_seen_perf"] = current_perf
        gate["last_seen_timestamp"] = current_timestamp
    return gate


def _scenarios() -> list[dict[str, Any]]:
    return [
        {
            "name": "first_fingerprint",
            "gate": {
                "version": "2026-06-09.1",
                "panel_pass_count": 0,
                "fingerprint_changes_seen": 0,
            },
            "fingerprint": ("beam", 1),
            "now": 10.25,
            "timestamp": "2026-07-15T23:10:00.000",
        },
        {
            "name": "same_fingerprint_updates_last_seen_only",
            "gate": {
                "version": "2026-06-09.1",
                "current_fingerprint": "('beam', 1)",
                "first_seen_perf": 8.0,
                "first_seen_timestamp": "2026-07-15T23:09:58.000",
                "last_seen_perf": 9.0,
                "last_seen_timestamp": "2026-07-15T23:09:59.000",
                "stable_for_fingerprint": True,
                "expensive_publication_allowed_for_fingerprint": True,
                "fingerprint_changes_seen": 2,
            },
            "fingerprint": ("beam", 1),
            "now": 10.25,
            "timestamp": "2026-07-15T23:10:00.000",
        },
        {
            "name": "changed_fingerprint_invalidates_previous",
            "gate": {
                "version": "2026-06-09.1",
                "current_fingerprint": "('beam', 1)",
                "first_seen_perf": 8.0,
                "first_seen_timestamp": "2026-07-15T23:09:58.000",
                "last_seen_perf": 9.0,
                "last_seen_timestamp": "2026-07-15T23:09:59.000",
                "stable_for_fingerprint": True,
                "expensive_publication_allowed_for_fingerprint": True,
                "fingerprint_changes_seen": 2,
            },
            "fingerprint": ("beam", 2),
            "now": 10.25,
            "timestamp": "2026-07-15T23:10:00.000",
        },
        {
            "name": "changed_fingerprint_missing_count_defaults_to_one",
            "gate": {
                "version": "2026-06-09.1",
                "current_fingerprint": "('beam', 1)",
                "stable_for_fingerprint": True,
                "expensive_publication_allowed_for_fingerprint": True,
            },
            "fingerprint": ("beam", 2),
            "now": 10.25,
            "timestamp": "2026-07-15T23:10:00.000",
        },
        {
            "name": "empty_previous_does_not_increment_change_count",
            "gate": {
                "version": "2026-06-09.1",
                "current_fingerprint": "",
                "fingerprint_changes_seen": 4,
            },
            "fingerprint": ("beam", 2),
            "now": 10.25,
            "timestamp": "2026-07-15T23:10:00.000",
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Settle Gate Fingerprint Update Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenario_results'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- session reads moved: `{payload['session_reads_moved']}`",
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
    helper = _function_window(source, "_design_guide_settle_gate_decision")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old_gate = _old_fingerprint_update(
            gate_state=row["gate"],
            fingerprint=row["fingerprint"],
            current_perf=row["now"],
            current_timestamp=row["timestamp"],
        )
        new = build_inputs_design_guide_settle_gate_fingerprint_update(
            gate_state=row["gate"],
            fingerprint=row["fingerprint"],
            current_perf=row["now"],
            current_timestamp=row["timestamp"],
        )
        match = old_gate == dict(new.gate_state) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old_gate": old_gate,
                "new_gate": dict(new.gate_state),
                "previous_fingerprint": new.previous_fingerprint,
                "current_fingerprint": new.current_fingerprint,
                "fingerprint_changed": bool(new.fingerprint_changed),
                "invalidated_previous_fingerprint": bool(new.invalidated_previous_fingerprint),
                "fingerprint_changes_seen": int(new.fingerprint_changes_seen),
                "display_hash_present": bool(new.display_hash),
            }
        )
        if not match:
            mismatches.append(
                {
                    "scenario": row["name"],
                    "old_gate": old_gate,
                    "new_gate": dict(new.gate_state),
                }
            )

    checks = {
        "helper_delegates_to_session_builder": "build_inputs_design_guide_settle_gate_fingerprint_update(" in helper,
        "helper_keeps_time_creation": "time.perf_counter()" in helper and "datetime.now().isoformat" in helper,
        "helper_keeps_session_state_source": "_design_guide_settle_gate_state()" in helper,
        "helper_keeps_invalidation_trace": "design_guide_settle_gate.invalidate" in helper,
        "helper_keeps_snapshot_hit_call": "_design_guide_settle_gate_snapshot_hit_for_state(current_state, fingerprint)" in helper,
        "old_inline_fingerprint_change_increment_removed": "gate[\"fingerprint_changes_seen\"] = int(gate.get(\"fingerprint_changes_seen\", 0) or 0) + 1" not in helper,
        "old_inline_current_fingerprint_assignment_removed": "gate[\"current_fingerprint\"] = fp_text" not in helper,
        "old_inline_first_seen_assignment_removed": "gate[\"first_seen_perf\"] = now" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_settle_gate_fingerprint_update(" in builders,
        "session_model_exists": "class InputsDesignGuideSettleGateFingerprintUpdate" in models,
        "session_init_exports_builder": "build_inputs_design_guide_settle_gate_fingerprint_update" in init_source,
        "session_init_exports_model": "InputsDesignGuideSettleGateFingerprintUpdate" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_FINGERPRINT_UPDATE_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_FINGERPRINT_UPDATE_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_settle_gate_fingerprint_update_cutover",
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
        "trace_ownership_moved": False,
        "snapshot_hit_ownership_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_settle_gate_fingerprint_update_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_settle_gate_fingerprint_update_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_settle_gate_fingerprint_update_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
