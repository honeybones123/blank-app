from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import ast


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class _FakeSidebar:
    def __init__(self, events: list[dict[str, Any]], *, checkbox_value: bool) -> None:
        self.events = events
        self.checkbox_value = checkbox_value

    def toggle(self, label: str, **kwargs: Any) -> bool:
        self.events.append({"fn": "toggle", "label": label, "kwargs": dict(kwargs)})
        return bool(kwargs.get("value", False))

    def checkbox(self, label: str, **kwargs: Any) -> bool:
        self.events.append({"fn": "checkbox", "label": label, "kwargs": dict(kwargs)})
        return self.checkbox_value

    def markdown(self, text: str) -> None:
        self.events.append({"fn": "markdown", "text": text})

    def json(self, value: Any) -> None:
        self.events.append({"fn": "json", "value": value})

    def code(self, value: str) -> None:
        self.events.append({"fn": "code", "value": value})


def _run_route(module: Any, *, checkbox_value: bool) -> list[dict[str, Any]]:
    import inputs_page_route_coordinators as route_bridge

    events: list[dict[str, Any]] = []
    session_state = {
        "page_slug": "inputs",
        "actions_source": "manual",
        "uls_Mstar": 240,
        "final_shear_truth_resolved": True,
        "_inputs_summary_debug_bundle": {"source": "test", "n": 1},
    }
    fake_st = SimpleNamespace(
        session_state=session_state,
        sidebar=_FakeSidebar(events, checkbox_value=checkbox_value),
    )
    originals = {
        "st": route_bridge.st,
        "key": route_bridge.DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY,
    }
    try:
        route_bridge.st = fake_st
        route_bridge.DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY = (
            "inputs_design_guide_debug_sidebar_v1"
        )
        module.render_inputs_dev_session_debug_sidebar_coordinator(ss={"page_slug": "inputs"})
    finally:
        route_bridge.st = originals["st"]
        route_bridge.DESIGN_GUIDE_SIDEBAR_DEBUG_TOGGLE_KEY = originals["key"]
    return events


def _run_module(*, checkbox_value: bool) -> list[dict[str, Any]]:
    from inputs_page_modules.session.dev_debug_sidebar import (
        render_inputs_dev_session_debug_sidebar,
    )

    events: list[dict[str, Any]] = []
    state = {
        "page_slug": "inputs",
        "actions_source": "manual",
        "uls_Mstar": 240,
        "final_shear_truth_resolved": True,
        "_inputs_summary_debug_bundle": {"source": "test", "n": 1},
    }
    fake_st = SimpleNamespace(sidebar=_FakeSidebar(events, checkbox_value=checkbox_value))
    render_inputs_dev_session_debug_sidebar(
        sidebar_module=fake_st,
        state=state,
        ss={"page_slug": "inputs"},
        design_guide_sidebar_debug_toggle_key="inputs_design_guide_debug_sidebar_v1",
    )
    return events


def _module_imports_are_clean() -> dict[str, Any]:
    module_path = ROOT / "inputs_page_modules" / "session" / "dev_debug_sidebar.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden = [
        imported
        for imported in imports
        if imported == "streamlit"
        or imported.startswith("streamlit.")
        or imported == "inputs_page"
        or imported.startswith("inputs_page.")
        or imported == "inputs_page_route_coordinators"
    ]
    return {"imports": imports, "forbidden": forbidden, "clean": not forbidden}


def main() -> int:
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    for case_name, checkbox_value in (("collapsed", False), ("expanded", True)):
        module_events = _run_module(checkbox_value=checkbox_value)
        route_events = _run_route(
            route_bridge,
            checkbox_value=checkbox_value,
        )
        cases[case_name] = {"module": module_events, "route": route_events}
        checks[f"{case_name}_events_match_module"] = module_events == route_events

    bridge_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    clean_imports = _module_imports_are_clean()
    checks["dev_sidebar_does_not_delegate_to_old_page"] = (
        "_legacy_inputs_page.render_inputs_dev_session_debug_sidebar_coordinator"
        not in bridge_source
    )
    checks["route_delegates_to_session_module"] = (
        "render_inputs_dev_session_debug_sidebar_module(" in bridge_source
    )
    checks["route_no_longer_owns_debug_key_list"] = (
        "debug_keys = [" not in bridge_source
        and "Inputs summary state debug" not in bridge_source
    )
    checks["module_imports_are_clean"] = clean_imports["clean"]
    checks["expanded_includes_summary_debug_code"] = any(
        event.get("fn") == "code" and json.loads(event.get("value") or "{}").get("source") == "test"
        for event in cases["expanded"]["route"]
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_dev_session_debug_sidebar_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
        "module_imports": clean_imports,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_dev_session_debug_sidebar_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_dev_session_debug_sidebar_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Dev Session Debug Sidebar Parity",
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
