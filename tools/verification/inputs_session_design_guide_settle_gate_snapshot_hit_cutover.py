from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_settle_gate_snapshot_hit_decision


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


def _old_snapshot_hit(
    *,
    cached_publication_available: bool,
    snapshot_state_fingerprint: Any,
    current_state_fingerprint: Any,
) -> bool:
    if bool(cached_publication_available):
        return True
    if isinstance({"state_fingerprint": snapshot_state_fingerprint}, dict):
        return str(snapshot_state_fingerprint or "") == str(current_state_fingerprint or "") and bool(
            str(snapshot_state_fingerprint or "")
        )
    return False


def _scenarios() -> list[dict[str, Any]]:
    return [
        {
            "name": "cached_publication_hit",
            "cached": True,
            "snapshot_fp": None,
            "current_fp": None,
        },
        {
            "name": "snapshot_match",
            "cached": False,
            "snapshot_fp": "abc",
            "current_fp": "abc",
        },
        {
            "name": "snapshot_mismatch",
            "cached": False,
            "snapshot_fp": "abc",
            "current_fp": "def",
        },
        {
            "name": "missing_snapshot",
            "cached": False,
            "snapshot_fp": None,
            "current_fp": "def",
        },
        {
            "name": "empty_snapshot",
            "cached": False,
            "snapshot_fp": "",
            "current_fp": "",
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Settle Gate Snapshot Hit Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenario_results'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- session reads moved: `{payload['session_reads_moved']}`",
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
    helper = _function_window(source, "_design_guide_settle_gate_snapshot_hit_for_state")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_snapshot_hit(
            cached_publication_available=row["cached"],
            snapshot_state_fingerprint=row["snapshot_fp"],
            current_state_fingerprint=row["current_fp"],
        )
        new = build_inputs_design_guide_settle_gate_snapshot_hit_decision(
            cached_publication_available=row["cached"],
            snapshot_state_fingerprint=row["snapshot_fp"],
            current_state_fingerprint=row["current_fp"],
        )
        match = bool(old) == bool(new.snapshot_hit) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": bool(old),
                "new": bool(new.snapshot_hit),
                "source": new.source,
                "display_hash_present": bool(new.display_hash),
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": bool(old), "new": bool(new.snapshot_hit)})

    checks = {
        "helper_delegates_to_session_builder": "build_inputs_design_guide_settle_gate_snapshot_hit_decision(" in helper,
        "helper_keeps_cached_publication_check": "_design_guide_settle_gate_cached_publication_available(fingerprint)" in helper,
        "helper_keeps_session_read": "st.session_state.get(_BENDING_FAIL_PUBLICATION_SNAPSHOT_KEY)" in helper,
        "helper_keeps_bending_snapshot_fingerprint_callback": "_bending_fail_publication_snapshot_state_fingerprint(" in helper,
        "old_inline_snapshot_compare_removed": "str(snapshot.get(\"state_fingerprint\") or \"\") == str(current_fp)" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_settle_gate_snapshot_hit_decision(" in builders,
        "session_model_exists": "class InputsDesignGuideSettleGateSnapshotHitDecision" in models,
        "session_init_exports_builder": "build_inputs_design_guide_settle_gate_snapshot_hit_decision" in init_source,
        "session_init_exports_model": "InputsDesignGuideSettleGateSnapshotHitDecision" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_SNAPSHOT_HIT_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_SNAPSHOT_HIT_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_settle_gate_snapshot_hit_cutover",
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
        "bending_snapshot_fingerprint_callback_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_settle_gate_snapshot_hit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_settle_gate_snapshot_hit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_settle_gate_snapshot_hit_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
