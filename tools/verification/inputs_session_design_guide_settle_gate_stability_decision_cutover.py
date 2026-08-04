from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_settle_gate_stability_decision


INPUTS_PAGE = ROOT / "inputs_page.py"
SESSION_BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
SESSION_MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
SESSION_INIT = ROOT / "inputs_page_modules" / "session" / "__init__.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


CONTRACT = "design_guide_family_settle_gate"
CONTRACT_FILE = "design_brain/contracts/design_guide_family_settle_gate.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    window = source.split(marker, 1)[1].split("\ndef ", 1)[0]
    return window.split("\n", 1)[1] if "\n" in window else window


def _old_stability_decision(
    *,
    gate_state: Mapping[str, Any],
    current_perf: float,
    delay_ms: int,
    snapshot_hit: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    gate = dict(gate_state or {})
    gate["panel_pass_count"] = int(gate.get("panel_pass_count", 0) or 0) + 1
    first_seen = float(gate.get("first_seen_perf") or current_perf)
    elapsed_ms = max(0.0, (current_perf - first_seen) * 1000.0)
    stable = bool(snapshot_hit or elapsed_ms >= float(delay_ms))
    gate["stable_for_fingerprint"] = stable
    decision = {
        "contract_boundary_checked": True,
        "contract": CONTRACT,
        "contract_file": CONTRACT_FILE,
        "fingerprint": str(gate.get("current_fingerprint") or ""),
        "fingerprint_first_seen_timestamp": gate.get("first_seen_timestamp"),
        "fingerprint_elapsed_ms": round(elapsed_ms, 3),
        "required_settle_ms": delay_ms,
        "stable": stable,
        "snapshot_hit": bool(snapshot_hit),
        "expensive_publication_allowed": stable,
        "panel_pass_count": int(gate.get("panel_pass_count", 0) or 0),
        "expensive_publication_count": int(gate.get("expensive_publication_count", 0) or 0),
        "skipped_expensive_publication_count": int(
            gate.get("skipped_expensive_publication_count", 0) or 0
        ),
        "fingerprint_changes_seen": int(gate.get("fingerprint_changes_seen", 0) or 0),
        "first_stable_publication_timestamp": gate.get("first_stable_publication_timestamp"),
    }
    return gate, decision


def _scenarios() -> list[dict[str, Any]]:
    base_gate = {
        "version": "2026-06-09.1",
        "current_fingerprint": "('beam', 1)",
        "first_seen_perf": 10.0,
        "first_seen_timestamp": "2026-07-15T23:10:00.000",
        "last_seen_perf": 10.1,
        "last_seen_timestamp": "2026-07-15T23:10:00.100",
        "panel_pass_count": 2,
        "expensive_publication_count": 3,
        "skipped_expensive_publication_count": 4,
        "fingerprint_changes_seen": 5,
        "first_stable_publication_timestamp": "2026-07-15T23:10:01.000",
    }
    return [
        {
            "name": "delay_not_met_no_snapshot",
            "gate": base_gate,
            "now": 10.2,
            "delay_ms": 500,
            "snapshot_hit": False,
        },
        {
            "name": "delay_met_no_snapshot",
            "gate": base_gate,
            "now": 10.8,
            "delay_ms": 500,
            "snapshot_hit": False,
        },
        {
            "name": "snapshot_hit_before_delay",
            "gate": base_gate,
            "now": 10.2,
            "delay_ms": 500,
            "snapshot_hit": True,
        },
        {
            "name": "missing_first_seen_defaults_elapsed_zero",
            "gate": {
                "current_fingerprint": "('beam', 2)",
                "panel_pass_count": 0,
            },
            "now": 10.2,
            "delay_ms": 500,
            "snapshot_hit": False,
        },
        {
            "name": "missing_counters_default_to_zero",
            "gate": {
                "current_fingerprint": "('beam', 3)",
                "first_seen_perf": 9.0,
            },
            "now": 10.2,
            "delay_ms": 500,
            "snapshot_hit": False,
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Settle Gate Stability Decision Cutover",
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
        old_gate, old_decision = _old_stability_decision(
            gate_state=row["gate"],
            current_perf=row["now"],
            delay_ms=row["delay_ms"],
            snapshot_hit=row["snapshot_hit"],
        )
        new = build_inputs_design_guide_settle_gate_stability_decision(
            gate_state=row["gate"],
            current_perf=row["now"],
            delay_ms=row["delay_ms"],
            snapshot_hit=row["snapshot_hit"],
            contract=CONTRACT,
            contract_file=CONTRACT_FILE,
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
                "stable": bool(new.stable),
                "elapsed_ms": new.elapsed_ms,
                "panel_pass_count": new.panel_pass_count,
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
        "helper_delegates_to_session_builder": "build_inputs_design_guide_settle_gate_stability_decision(" in helper,
        "helper_keeps_delay_builder": "_design_guide_settle_gate_delay_ms()" in helper,
        "helper_keeps_snapshot_hit_call": "_design_guide_settle_gate_snapshot_hit_for_state(current_state, fingerprint)" in helper,
        "helper_keeps_snapshot_hit_trace": "design_guide_settle_gate.snapshot_hit" in helper,
        "helper_keeps_fingerprint_seen_trace": "design_guide_settle_gate.fingerprint_seen" in helper,
        "helper_keeps_stable_trace": "design_guide_settle_gate.stable" in helper,
        "old_inline_panel_pass_increment_removed": "gate[\"panel_pass_count\"] = int(gate.get(\"panel_pass_count\", 0) or 0) + 1" not in helper,
        "old_inline_elapsed_calc_removed": "elapsed_ms = max(0.0, (now - first_seen) * 1000.0)" not in helper,
        "old_inline_stable_assignment_removed": "gate[\"stable_for_fingerprint\"] = stable" not in helper,
        "old_inline_decision_dict_removed": "\"contract_boundary_checked\": True" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_settle_gate_stability_decision(" in builders,
        "session_model_exists": "class InputsDesignGuideSettleGateStabilityDecision" in models,
        "session_init_exports_builder": "build_inputs_design_guide_settle_gate_stability_decision" in init_source,
        "session_init_exports_model": "InputsDesignGuideSettleGateStabilityDecision" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_STABILITY_DECISION_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_STABILITY_DECISION_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_settle_gate_stability_decision_cutover",
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
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_settle_gate_stability_decision_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_settle_gate_stability_decision_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_settle_gate_stability_decision_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
