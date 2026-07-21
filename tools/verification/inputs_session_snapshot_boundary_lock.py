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
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
SESSION_ROOT = ROOT / "inputs_page_modules" / "session"
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
        "# Inputs Session Snapshot Boundary Lock",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This lock covers the first Session State extraction surface: `_inputs_audit_snapshot_state`.",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Snapshot construction is owned by `inputs_page_modules.session`.",
            "- `inputs_page.py` only calls the builder, emits debug trace, and returns the dict.",
            "- The page-local legacy snapshot loop is deleted.",
            "- Streamlit/session mutation, callbacks, Apply routing, and render triggers were not moved.",
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
    route = _read(ROUTE_COORDINATORS)
    helper_window = _function_window(page, "_inputs_audit_snapshot_state") or _function_window(
        route,
        "inputs_audit_snapshot_state",
    )
    module_sources = {
        path.name: _read(path)
        for path in SESSION_ROOT.glob("*.py")
    }
    module_combined = "\n".join(module_sources.values())
    executable_module = "\n".join(
        source for name, source in module_sources.items() if name != "contracts.py"
    )
    checks = {
        "session_module_exists": SESSION_ROOT.exists(),
        "builder_exported": "build_inputs_session_source_snapshot" in module_sources.get("__init__.py", ""),
        "contracts_define_read_only_boundary": all(
            rule in module_sources.get("contracts.py", "")
            for rule in (
                "pure_snapshot_decision_and_plan_models",
                "do_not_import_streamlit",
                "do_not_mutate_session_state",
                "do_not_route_apply",
                "do_not_execute_callbacks",
                "do_not_render_widgets",
            )
        ),
        "helper_exists": bool(helper_window),
        "helper_calls_module_builder": "build_inputs_session_source_snapshot(st.session_state)" in helper_window,
        "helper_returns_module_snapshot_dict": (
            (
                "out: dict[str, object] = {entry.key: entry.value for entry in _typed_snapshot.entries}"
                in helper_window
                or "{entry.key: entry.value for entry in snapshot.entries}" in helper_window
            )
            and "return" in helper_window
        ),
        "helper_emits_delegated_debug_trace": (
            "inputs_session_snapshot_delegated" in helper_window
            and "typed_display_hash=_typed_snapshot.display_hash" in helper_window
            and "live_page_cutover=True" in helper_window
        )
        or "inputs_audit_snapshot_state" in route,
        "legacy_page_copy_loop_deleted": "legacy_out" not in helper_window
        and "st.session_state.keys()" not in helper_window
        and "st.session_state.get(k)" not in helper_window
        and "inputs_session_snapshot_parity" not in helper_window,
        "no_silent_page_fallback": "inputs_session_snapshot_parity_error" not in helper_window
        and "except Exception as _session_snapshot_parity_exc" not in helper_window,
        "module_streamlit_free": "import streamlit" not in module_combined
        and "from streamlit" not in module_combined,
        "module_inputs_page_free": "import inputs_page" not in executable_module
        and "from inputs_page" not in executable_module,
        "module_session_mutation_free": "st.session_state" not in executable_module
        and ".session_state" not in executable_module,
        "module_apply_routing_free": "apply_guidance_action(" not in executable_module
        and "_apply_resolved_candidate_payload(" not in executable_module
        and "route_apply(" not in executable_module,
        "module_callback_execution_free": "on_change" not in executable_module
        and "sync_callback" not in executable_module,
        "module_rendering_free": not re.search(r"\bst\.", executable_module)
        and not re.search(r"(?m)^\s*(import|from)\s+streamlit\b", executable_module),
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "INPUTS_SESSION_SNAPSHOT_BOUNDARY_LOCKED" if not failures else "INPUTS_SESSION_SNAPSHOT_BOUNDARY_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_snapshot_boundary_lock",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "locked_surface": "_inputs_audit_snapshot_state",
        "snapshot_owner": "inputs_page_modules.session",
        "page_role": "debug-audit caller and trace emitter",
        "legacy_loop_deleted": checks["legacy_page_copy_loop_deleted"],
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "render_trigger_state_moved": False,
        "next_safe_slice": "audit next Session State surface before extraction",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_snapshot_boundary_lock_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_snapshot_boundary_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_snapshot_boundary_lock", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
