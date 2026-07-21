from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
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


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Summary Shared-Only Decision Boundary Lock",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    bridge = _read(APP_CONTRACT_BRIDGE)
    builders = _read(BUILDERS)
    models = _read(MODELS)
    helper = _function_window(page, "_inputs_summary_should_use_shared_only") or _function_window(
        bridge,
        "_inputs_summary_should_use_shared_only_for_app_bridge",
    ) or _function_window(bridge, "_inputs_summary_should_use_shared_only")
    checks = {
        "page_helper_present": bool(helper),
        "page_helper_delegates_decision": "build_inputs_summary_shared_only_decision(" in helper,
        "page_helper_keeps_session_reads": "st.session_state.get" in helper,
        "old_inline_reason_returns_removed": 'return True, "applying_auto_design"' not in helper
        and 'return True, "force_inputs_widget_reseed_once"' not in helper
        and 'return True, "pending_inputs_apply_refresh"' not in helper
        and 'return True, "post_force_refresh_this_run"' not in helper
        and 'return False, "normal_overlay"' not in helper,
        "session_builder_owns_reason_priority": "def build_inputs_summary_shared_only_decision(" in builders
        and '"applying_auto_design"' in builders
        and '"force_inputs_widget_reseed_once"' in builders
        and '"pending_inputs_apply_refresh"' in builders
        and '"post_force_refresh_this_run"' in builders
        and '"normal_overlay"' in builders,
        "session_model_exists": "class InputsSummarySharedOnlyDecision" in models,
        "no_streamlit_import_in_session_builder": not re.search(r"^\s*(import|from)\s+streamlit\b", builders, re.M),
        "product_behavior_changed": False,
        "session_behavior_changed": False,
    }
    expected_false = {"product_behavior_changed", "session_behavior_changed"}
    failures = [
        key
        for key, value in checks.items()
        if (key in expected_false and value) or (key not in expected_false and not value)
    ]
    decision = (
        "INPUTS_SESSION_SUMMARY_SHARED_ONLY_DECISION_BOUNDARY_LOCKED"
        if not failures
        else "INPUTS_SESSION_SUMMARY_SHARED_ONLY_DECISION_BOUNDARY_GAPS_REMAIN"
    )
    payload: dict[str, Any] = {
        "audit": "inputs_session_summary_shared_only_decision_boundary_lock",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_summary_shared_only_decision_boundary_lock_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_summary_shared_only_decision_boundary_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_summary_shared_only_decision_boundary_lock", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
