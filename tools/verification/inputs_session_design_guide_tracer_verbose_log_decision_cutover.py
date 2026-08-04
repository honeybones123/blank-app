from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_tracer_verbose_log_decision


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


def _old_decision(row: dict[str, Any]) -> bool:
    if bool(row["dev_mode"]):
        return True
    return str(row["tracer_debug_env"] or "").strip().lower() in ("1", "true", "yes", "on")


def _scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "disabled", "dev_mode": False, "tracer_debug_env": None, "expected_reason": "disabled"},
        {"name": "dev_mode", "dev_mode": True, "tracer_debug_env": None, "expected_reason": "dev_mode"},
        {"name": "env_1", "dev_mode": False, "tracer_debug_env": "1", "expected_reason": "design_guide_tracer_debug_env"},
        {"name": "env_true", "dev_mode": False, "tracer_debug_env": "true", "expected_reason": "design_guide_tracer_debug_env"},
        {"name": "env_yes", "dev_mode": False, "tracer_debug_env": "yes", "expected_reason": "design_guide_tracer_debug_env"},
        {"name": "env_on", "dev_mode": False, "tracer_debug_env": "on", "expected_reason": "design_guide_tracer_debug_env"},
        {"name": "env_false", "dev_mode": False, "tracer_debug_env": "false", "expected_reason": "disabled"},
        {"name": "dev_mode_precedence", "dev_mode": True, "tracer_debug_env": "false", "expected_reason": "dev_mode"},
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Tracer Verbose Log Decision Cutover",
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
    helper = _function_window(source, "_design_guide_tracer_verbose_log")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_decision(row)
        new = build_inputs_design_guide_tracer_verbose_log_decision(
            dev_mode=row["dev_mode"],
            tracer_debug_env=row["tracer_debug_env"],
        )
        match = old == bool(new.verbose_log) and new.reason == row["expected_reason"] and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": bool(new.verbose_log),
                "reason": new.reason,
                "display_hash": new.display_hash,
            }
        )
        if not match:
            mismatches.append(
                {
                    "scenario": row["name"],
                    "old": old,
                    "new": bool(new.verbose_log),
                    "reason": new.reason,
                    "expected_reason": row["expected_reason"],
                }
            )

    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_design_guide_tracer_verbose_log_decision(" in helper,
        "page_helper_keeps_session_read": 'st.session_state.get("_dev_mode")' in helper,
        "page_helper_keeps_env_read": 'os.environ.get("DESIGN_GUIDE_TRACER_DEBUG")' in helper,
        "old_env_policy_removed_from_page": '"true"' not in helper and '"yes"' not in helper and '"on"' not in helper,
        "session_builder_exists": "def build_inputs_design_guide_tracer_verbose_log_decision(" in builders,
        "session_model_exists": "class InputsDesignGuideTracerVerboseLogDecision" in models,
        "session_init_exports_builder": "build_inputs_design_guide_tracer_verbose_log_decision" in init_source,
        "session_init_exports_model": "InputsDesignGuideTracerVerboseLogDecision" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_TRACER_VERBOSE_LOG_DECISION_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_TRACER_VERBOSE_LOG_DECISION_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_tracer_verbose_log_decision_cutover",
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
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_tracer_verbose_log_decision_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_tracer_verbose_log_decision_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_tracer_verbose_log_decision_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
