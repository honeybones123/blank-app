from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import (
    build_inputs_design_guide_settle_gate_delay_decision,
    build_inputs_design_guide_settle_gate_enabled_decision,
)


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


def _old_delay(raw: Any, default_delay_ms: int) -> int:
    text = str(raw or "").strip()
    if text:
        try:
            return max(250, min(8000, int(float(text))))
        except Exception:
            pass
    return int(default_delay_ms)


def _old_enabled(browser_mode: Any, enabled_raw: Any) -> bool:
    truthy = {"1", "true", "yes", "on"}
    if str(browser_mode or "").strip().lower() in truthy:
        return False
    return str(enabled_raw or "").strip().lower() in truthy


def _delay_scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "default", "raw": None, "default": 2200},
        {"name": "valid", "raw": "3000", "default": 2200},
        {"name": "lower_bound", "raw": "50", "default": 2200},
        {"name": "upper_bound", "raw": "9000", "default": 2200},
        {"name": "float", "raw": "1234.5", "default": 2200},
        {"name": "invalid", "raw": "bad", "default": 2200},
    ]


def _enabled_scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "default_disabled", "browser": None, "enabled": None},
        {"name": "env_enabled_1", "browser": None, "enabled": "1"},
        {"name": "env_enabled_true", "browser": None, "enabled": "true"},
        {"name": "env_disabled_false", "browser": None, "enabled": "false"},
        {"name": "browser_mode_disables", "browser": "1", "enabled": "1"},
        {"name": "browser_mode_yes_disables", "browser": "yes", "enabled": "on"},
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Settle Gate Env Decision Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- delay scenarios checked: `{len(payload['delay_scenarios'])}`",
        f"- enabled scenarios checked: `{len(payload['enabled_scenarios'])}`",
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
    delay_helper = _function_window(source, "_design_guide_settle_gate_delay_ms")
    enabled_helper = _function_window(source, "_design_guide_settle_gate_enabled")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    delay_results = []
    enabled_results = []
    mismatches = []
    for row in _delay_scenarios():
        old = _old_delay(row["raw"], row["default"])
        new = build_inputs_design_guide_settle_gate_delay_decision(
            delay_env=row["raw"],
            default_delay_ms=row["default"],
        )
        match = old == int(new.delay_ms) and bool(new.display_hash)
        delay_results.append({"scenario": row["name"], "match": match, "old": old, "new": int(new.delay_ms)})
        if not match:
            mismatches.append({"kind": "delay", "scenario": row["name"], "old": old, "new": int(new.delay_ms)})
    for row in _enabled_scenarios():
        old = _old_enabled(row["browser"], row["enabled"])
        new = build_inputs_design_guide_settle_gate_enabled_decision(
            browser_test_mode_env=row["browser"],
            settle_gate_enabled_env=row["enabled"],
        )
        match = old == bool(new.enabled) and bool(new.display_hash)
        enabled_results.append({"scenario": row["name"], "match": match, "old": old, "new": bool(new.enabled)})
        if not match:
            mismatches.append({"kind": "enabled", "scenario": row["name"], "old": old, "new": bool(new.enabled)})

    checks = {
        "delay_helper_delegates_to_session_builder": "build_inputs_design_guide_settle_gate_delay_decision(" in delay_helper,
        "enabled_helper_delegates_to_session_builder": "build_inputs_design_guide_settle_gate_enabled_decision(" in enabled_helper,
        "page_helpers_keep_env_reads": "os.environ.get" in delay_helper and "os.environ.get" in enabled_helper,
        "old_delay_policy_removed_from_page": "max(250" not in delay_helper and "min(8000" not in delay_helper,
        "old_enabled_truthy_policy_removed_from_page": '"true"' not in enabled_helper and '"yes"' not in enabled_helper,
        "session_delay_builder_exists": "def build_inputs_design_guide_settle_gate_delay_decision(" in builders,
        "session_enabled_builder_exists": "def build_inputs_design_guide_settle_gate_enabled_decision(" in builders,
        "session_delay_model_exists": "class InputsDesignGuideSettleGateDelayDecision" in models,
        "session_enabled_model_exists": "class InputsDesignGuideSettleGateEnabledDecision" in models,
        "session_init_exports_builders": "build_inputs_design_guide_settle_gate_delay_decision" in init_source
        and "build_inputs_design_guide_settle_gate_enabled_decision" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_ENV_DECISION_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_SETTLE_GATE_ENV_DECISION_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_settle_gate_env_decision_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "delay_scenarios": delay_results,
        "enabled_scenarios": enabled_results,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "streamlit_reads_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_settle_gate_env_decision_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_settle_gate_env_decision_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_settle_gate_env_decision_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
