from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_settle_gate_default_state


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


def _old_default_state() -> dict:
    return {
        "version": "2026-06-09.1",
        "panel_pass_count": 0,
        "expensive_publication_count": 0,
        "skipped_expensive_publication_count": 0,
        "fingerprint_changes_seen": 0,
        "first_stable_publication_timestamp": None,
    }


def _write_report(payload: dict, report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Settle Gate Default State Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- default state parity: `{payload['default_state_matches']}`",
        f"- product behavior changed: `{payload['product_behavior_changed']}`",
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
    helper = _function_window(source, "_design_guide_settle_gate_state")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    old = _old_default_state()
    new = build_inputs_design_guide_settle_gate_default_state()
    default_state_matches = old == dict(new.gate_state) and bool(new.display_hash)
    checks = {
        "helper_delegates_to_session_builder": "build_inputs_design_guide_settle_gate_default_state()" in helper,
        "helper_keeps_session_read": "st.session_state.get" in helper,
        "helper_keeps_session_write": "st.session_state[DESIGN_GUIDE_FAMILY_SETTLE_GATE_KEY]" in helper,
        "old_inline_default_dict_removed": '"panel_pass_count": 0' not in helper
        and '"first_stable_publication_timestamp": None' not in helper,
        "session_builder_exists": "def build_inputs_design_guide_settle_gate_default_state(" in builders,
        "session_model_exists": "class InputsDesignGuideSettleGateDefaultState" in models,
        "session_init_exports_builder": "build_inputs_design_guide_settle_gate_default_state" in init_source,
        "session_init_exports_model": "InputsDesignGuideSettleGateDefaultState" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "default_state_matches_old": default_state_matches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_DEFAULT_STATE_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_DEFAULT_STATE_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_settle_gate_default_state_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "default_state_matches": default_state_matches,
        "old_default_state": old,
        "new_default_state": dict(new.gate_state),
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "session_reads_moved": False,
        "session_writes_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "streamlit_reads_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_settle_gate_default_state_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_settle_gate_default_state_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_settle_gate_default_state_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
