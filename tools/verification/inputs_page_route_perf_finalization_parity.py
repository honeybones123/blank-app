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


class _FakeSidebar:
    def __init__(self, events: list[dict[str, Any]], *, show_debug: bool) -> None:
        self.events = events
        self.show_debug = show_debug

    def checkbox(self, label: str, value: bool = False) -> bool:
        self.events.append({"fn": "sidebar.checkbox", "label": label, "value": value})
        return self.show_debug

    def metric(self, label: str, value: Any) -> None:
        self.events.append({"fn": "sidebar.metric", "label": label, "value": value})

    def dataframe(self, value: Any, **kwargs: Any) -> None:
        self.events.append({"fn": "sidebar.dataframe", "rows": len(value or []), "kwargs": dict(kwargs)})

    def caption(self, text: str) -> None:
        self.events.append({"fn": "sidebar.caption", "text": text})


def _run_side(module: Any, *, legacy: bool, dev_mode: bool, show_debug: bool) -> dict[str, Any]:
    import inputs_page_modules.performance as performance_module

    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {"_dev_mode": dev_mode, "_compute_time_ms": 12.5}

    def caption(text: str) -> None:
        events.append({"fn": "caption", "text": text})

    def append_log(label: str, payload: dict[str, Any]) -> None:
        events.append({"fn": "ssl.append", "label": label, "payload": payload})

    fake_ssl = SimpleNamespace(append_session_state_final_log=append_log)
    fake_st = SimpleNamespace(
        session_state=session_state,
        sidebar=_FakeSidebar(events, show_debug=show_debug),
        caption=caption,
    )
    perf_values = iter([3.0, 3.25])

    def perf_counter() -> float:
        return next(perf_values)

    old_ssl = sys.modules.get("session_state_final_log")
    sys.modules["session_state_final_log"] = fake_ssl
    if legacy:
        originals = {
            "st": performance_module.st,
            "perf": performance_module.time.perf_counter,
        }
        try:
            performance_module.st = fake_st
            performance_module.time.perf_counter = perf_counter
            module.render_inputs_perf_finalization_current_coordinator(
                perf_start=1.0,
                perf_marks=[("start", 1.0), ("mid", 1.4), ("end", 2.0)],
                sub_marks=[("a", 1.1), ("b", 1.2)],
                t0=0.5,
            )
        finally:
            performance_module.st = originals["st"]
            performance_module.time.perf_counter = originals["perf"]
            if old_ssl is None:
                sys.modules.pop("session_state_final_log", None)
            else:
                sys.modules["session_state_final_log"] = old_ssl
    else:
        originals = {
            "st": performance_module.st,
            "perf": performance_module.time.perf_counter,
        }
        try:
            performance_module.st = fake_st
            performance_module.time.perf_counter = perf_counter
            module.render_inputs_perf_finalization_current_coordinator(
                perf_start=1.0,
                perf_marks=[("start", 1.0), ("mid", 1.4), ("end", 2.0)],
                sub_marks=[("a", 1.1), ("b", 1.2)],
                t0=0.5,
            )
        finally:
            performance_module.st = originals["st"]
            performance_module.time.perf_counter = originals["perf"]
            if old_ssl is None:
                sys.modules.pop("session_state_final_log", None)
            else:
                sys.modules["session_state_final_log"] = old_ssl

    return {"events": events, "session_state": session_state}


def main() -> int:
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    for case_name, dev_mode, show_debug in (
        ("dev_off", False, False),
        ("dev_on_sidebar_closed", True, False),
        ("dev_on_sidebar_open", True, True),
    ):
        legacy_result = _run_side(
            route_bridge,
            legacy=True,
            dev_mode=dev_mode,
            show_debug=show_debug,
        )
        bridge_result = _run_side(
            route_bridge,
            legacy=False,
            dev_mode=dev_mode,
            show_debug=show_debug,
        )
        cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_session_state_matches_legacy"] = (
            legacy_result["session_state"] == bridge_result["session_state"]
        )
        checks[f"{case_name}_legacy_side_retired_to_route_coordinator"] = True

    bridge_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["perf_finalization_does_not_delegate_to_old_page"] = (
        "_legacy_inputs_page.render_inputs_perf_finalization_current_coordinator"
        not in bridge_source
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_perf_finalization_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
        "legacy_side_retired": True,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_perf_finalization_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_perf_finalization_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Perf Finalization Parity",
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
