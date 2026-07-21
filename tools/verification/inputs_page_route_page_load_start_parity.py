from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _run_side(module: Any, *, legacy: bool, debug_enabled: bool, preset_skip: Any) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge
    import state_and_helpers

    events: list[dict[str, Any]] = []
    fake_session = {"inputs_b": 300, "inputs_D": 600}
    ss: dict[str, Any] = {}
    if preset_skip != "__missing__":
        ss["_beam_skip_auto_persist_once"] = preset_skip

    def log_debug(message: str, value: Any = None) -> None:
        events.append({"fn": "log_debug", "message": message, "value": value})

    def trace_line(line: str, filename: str = "sync_callback_trace.txt") -> None:
        events.append({"fn": "trace", "line": line, "filename": filename})

    def beam_init() -> None:
        events.append({"fn": "beam_init"})

    fake_defaults = {"b": 300, "D": 600}
    fake_tab_keys = {"b": "inputs_b", "D": "inputs_D"}

    if legacy:
        originals = {
            "debug": legacy_inputs_page._INPUTS_DEBUG_AUDIT,
            "log_debug": legacy_inputs_page.log_debug,
            "shared_defaults": legacy_inputs_page.SHARED_DEFAULTS,
            "tab_keys": legacy_inputs_page.INPUTS_PAGE_TAB_KEYS,
            "st": legacy_inputs_page.st,
            "ensure": legacy_inputs_page.ensure_beam_project_initialized,
            "trace": state_and_helpers._write_sync_trace_line,
            "perf": legacy_inputs_page.time.perf_counter,
        }
        try:
            legacy_inputs_page._INPUTS_DEBUG_AUDIT = debug_enabled
            legacy_inputs_page.log_debug = log_debug
            legacy_inputs_page.SHARED_DEFAULTS = fake_defaults
            legacy_inputs_page.INPUTS_PAGE_TAB_KEYS = fake_tab_keys
            legacy_inputs_page.st = SimpleNamespace(session_state=fake_session)
            legacy_inputs_page.ensure_beam_project_initialized = beam_init
            state_and_helpers._write_sync_trace_line = trace_line
            legacy_inputs_page.time.perf_counter = lambda: 123.456
            returned = module.render_inputs_page_load_start_coordinator(ss=ss)
        finally:
            legacy_inputs_page._INPUTS_DEBUG_AUDIT = originals["debug"]
            legacy_inputs_page.log_debug = originals["log_debug"]
            legacy_inputs_page.SHARED_DEFAULTS = originals["shared_defaults"]
            legacy_inputs_page.INPUTS_PAGE_TAB_KEYS = originals["tab_keys"]
            legacy_inputs_page.st = originals["st"]
            legacy_inputs_page.ensure_beam_project_initialized = originals["ensure"]
            state_and_helpers._write_sync_trace_line = originals["trace"]
            legacy_inputs_page.time.perf_counter = originals["perf"]
    else:
        originals = {
            "debug": route_bridge._INPUTS_DEBUG_AUDIT,
            "log_debug": route_bridge.log_debug,
            "shared_defaults": route_bridge.SHARED_DEFAULTS,
            "tab_keys": route_bridge.INPUTS_PAGE_TAB_KEYS,
            "st": route_bridge.st,
            "ensure": route_bridge.ensure_beam_project_initialized,
            "trace": route_bridge._write_sync_trace_line,
            "perf": route_bridge.time.perf_counter,
        }
        try:
            route_bridge._INPUTS_DEBUG_AUDIT = debug_enabled
            route_bridge.log_debug = log_debug
            route_bridge.SHARED_DEFAULTS = fake_defaults
            route_bridge.INPUTS_PAGE_TAB_KEYS = fake_tab_keys
            route_bridge.st = SimpleNamespace(session_state=fake_session)
            route_bridge.ensure_beam_project_initialized = beam_init
            route_bridge._write_sync_trace_line = trace_line
            route_bridge.time.perf_counter = lambda: 123.456
            returned = module.render_inputs_page_load_start_coordinator(ss=ss)
        finally:
            route_bridge._INPUTS_DEBUG_AUDIT = originals["debug"]
            route_bridge.log_debug = originals["log_debug"]
            route_bridge.SHARED_DEFAULTS = originals["shared_defaults"]
            route_bridge.INPUTS_PAGE_TAB_KEYS = originals["tab_keys"]
            route_bridge.st = originals["st"]
            route_bridge.ensure_beam_project_initialized = originals["ensure"]
            route_bridge._write_sync_trace_line = originals["trace"]
            route_bridge.time.perf_counter = originals["perf"]

    return {"events": events, "returned": returned, "ss": ss}


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    for case_name, debug_enabled, preset_skip in (
        ("debug_off_missing_skip", False, "__missing__"),
        ("debug_on_missing_skip", True, "__missing__"),
        ("debug_on_existing_skip_false", True, False),
    ):
        legacy_result = _run_side(
            legacy_inputs_page,
            legacy=True,
            debug_enabled=debug_enabled,
            preset_skip=preset_skip,
        )
        bridge_result = _run_side(
            route_bridge,
            legacy=False,
            debug_enabled=debug_enabled,
            preset_skip=preset_skip,
        )
        cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["returned"] == bridge_result["returned"]
        checks[f"{case_name}_session_side_effects_match_legacy"] = legacy_result["ss"] == bridge_result["ss"]

    bridge_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["page_load_start_does_not_delegate_to_old_page"] = (
        "_legacy_inputs_page.render_inputs_page_load_start_coordinator" not in bridge_source
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_page_load_start_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
        "wrapper_note": "route page-load start is locally implemented plumbing",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_page_load_start_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_page_load_start_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Page Load Start Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *(f"- `{name}`: `{passed}`" for name, passed in checks.items()),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
