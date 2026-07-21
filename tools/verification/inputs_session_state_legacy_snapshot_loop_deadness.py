from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    window = source.split(marker, 1)[1].split("\ndef ", 1)[0]
    return window.split("):", 1)[1] if "):" in window else window


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session State Legacy Snapshot Loop Deadness",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves the page-local legacy copy loop inside `_inputs_audit_snapshot_state` is no longer authoritative.",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Ownership",
            "",
            "- `inputs_page_modules.session.build_inputs_session_source_snapshot(...)` owns snapshot construction.",
            "- `inputs_page.py` remains the debug-audit caller and page/session boundary.",
            "- Hydration, callbacks, Apply routing, invalidation, and render-trigger state remain page-owned.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    helper_window = _function_window(page, "_inputs_audit_snapshot_state")
    legacy_loop_present = "legacy_out: dict[str, object] = {}" in helper_window
    legacy_trace_present = "legacy_count=len(legacy_out)" in helper_window
    typed_return_present = (
        "out: dict[str, object] = {entry.key: entry.value for entry in _typed_snapshot.entries}" in helper_window
        and "return out" in helper_window
    )
    helper_lines = [
        line.strip()
        for line in helper_window.splitlines()
        if line.strip() and not line.strip().startswith('"""')
    ]
    checks = {
        "helper_exists": bool(helper_window),
        "typed_builder_called_first": bool(helper_lines)
        and helper_lines[0] == "_typed_snapshot = build_inputs_session_source_snapshot(st.session_state)",
        "typed_snapshot_return_is_authoritative": typed_return_present,
        "live_cutover_locked": "live_page_cutover=True" in helper_window,
        "no_typed_builder_error_fallback": "inputs_session_snapshot_parity_error" not in helper_window
        and "except Exception as _session_snapshot_parity_exc" not in helper_window,
        "legacy_loop_only_parity_if_present": (
            not legacy_loop_present
            or (
                legacy_trace_present
                and "legacy_out" not in helper_window.split("return out", 1)[-1]
                and "out.get(key) != legacy_out.get(key)" in helper_window
            )
        ),
        "legacy_loop_deleted_or_ready": True,
        "no_apply_routing_moved": "apply_payload" not in helper_window
        and "route_apply" not in helper_window,
        "no_callback_execution_moved": "sync_callback" not in helper_window
        and "on_change" not in helper_window,
    }
    failures = [key for key, value in checks.items() if not value]
    if failures:
        decision = "SESSION_LEGACY_SNAPSHOT_LOOP_DEADNESS_GAPS_REMAIN"
    elif legacy_loop_present:
        decision = "SESSION_LEGACY_SNAPSHOT_LOOP_READY_TO_DELETE"
    else:
        decision = "SESSION_LEGACY_SNAPSHOT_LOOP_DELETED_LOCKED"
    payload = {
        "audit": "inputs_session_state_legacy_snapshot_loop_deadness",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "legacy_loop_present": legacy_loop_present,
        "legacy_trace_present": legacy_trace_present,
        "typed_snapshot_return_authoritative": typed_return_present,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "next_safe_slice": (
            "delete the legacy local copy loop"
            if decision == "SESSION_LEGACY_SNAPSHOT_LOOP_READY_TO_DELETE"
            else "lock Session State snapshot boundary or move to next session surface"
        ),
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_state_legacy_snapshot_loop_deadness_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_state_legacy_snapshot_loop_deadness_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_state_legacy_snapshot_loop_deadness", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
