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


def _run_side(module: Any, *, legacy: bool, debug_enabled: bool, before_state: dict | None) -> list[dict[str, Any]]:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    events: list[dict[str, Any]] = []
    fake_session = {
        "b": 350,
        "D": 600,
        "inputs_b": 300,
        "untouched": "same",
    }
    fake_shared_defaults = {"b": 300, "D": 600, "untouched": "same"}
    fake_tab_keys = {"b": "inputs_b"}

    def log_debug(message: str, value: Any = None) -> None:
        events.append({"message": message, "value": value})

    if legacy:
        originals = {
            "debug": legacy_inputs_page._INPUTS_DEBUG_AUDIT,
            "st": legacy_inputs_page.st,
            "log_debug": legacy_inputs_page.log_debug,
            "shared_defaults": legacy_inputs_page.SHARED_DEFAULTS,
            "tab_keys": legacy_inputs_page.INPUTS_PAGE_TAB_KEYS,
        }
        try:
            legacy_inputs_page._INPUTS_DEBUG_AUDIT = debug_enabled
            legacy_inputs_page.st = SimpleNamespace(session_state=fake_session)
            legacy_inputs_page.log_debug = log_debug
            legacy_inputs_page.SHARED_DEFAULTS = fake_shared_defaults
            legacy_inputs_page.INPUTS_PAGE_TAB_KEYS = fake_tab_keys
            module.render_inputs_debug_audit_current_coordinator(before_state=before_state)
        finally:
            legacy_inputs_page._INPUTS_DEBUG_AUDIT = originals["debug"]
            legacy_inputs_page.st = originals["st"]
            legacy_inputs_page.log_debug = originals["log_debug"]
            legacy_inputs_page.SHARED_DEFAULTS = originals["shared_defaults"]
            legacy_inputs_page.INPUTS_PAGE_TAB_KEYS = originals["tab_keys"]
    else:
        originals = {
            "debug": route_bridge._INPUTS_DEBUG_AUDIT,
            "st": route_bridge.st,
            "log_debug": route_bridge.log_debug,
            "shared_defaults": route_bridge.SHARED_DEFAULTS,
            "tab_keys": route_bridge.INPUTS_PAGE_TAB_KEYS,
        }
        try:
            route_bridge._INPUTS_DEBUG_AUDIT = debug_enabled
            route_bridge.st = SimpleNamespace(session_state=fake_session)
            route_bridge.log_debug = log_debug
            route_bridge.SHARED_DEFAULTS = fake_shared_defaults
            route_bridge.INPUTS_PAGE_TAB_KEYS = fake_tab_keys
            module.render_inputs_debug_audit_current_coordinator(before_state=before_state)
        finally:
            route_bridge._INPUTS_DEBUG_AUDIT = originals["debug"]
            route_bridge.st = originals["st"]
            route_bridge.log_debug = originals["log_debug"]
            route_bridge.SHARED_DEFAULTS = originals["shared_defaults"]
            route_bridge.INPUTS_PAGE_TAB_KEYS = originals["tab_keys"]
    return events


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    for case_name, debug_enabled, before_state in (
        ("debug_off", False, {"b": 300, "D": 600, "untouched": "same"}),
        ("debug_on_none_before", True, None),
        ("debug_on_changed", True, {"b": 300, "D": 600, "untouched": "same"}),
    ):
        legacy_events = _run_side(
            legacy_inputs_page,
            legacy=True,
            debug_enabled=debug_enabled,
            before_state=before_state,
        )
        bridge_events = _run_side(
            route_bridge,
            legacy=False,
            debug_enabled=debug_enabled,
            before_state=before_state,
        )
        cases[case_name] = {"legacy": legacy_events, "bridge": bridge_events}
        checks[f"{case_name}_events_match_legacy"] = legacy_events == bridge_events

    bridge_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["debug_audit_does_not_delegate_to_old_page"] = (
        "_legacy_inputs_page.render_inputs_debug_audit_current_coordinator" not in bridge_source
    )
    checks["debug_on_changed_emits_load_end"] = cases["debug_on_changed"]["bridge"][-1:] == [
        {"message": "---- INPUTS PAGE LOAD END ----", "value": None}
    ]
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_debug_audit_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_debug_audit_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_debug_audit_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Debug Audit Parity",
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
