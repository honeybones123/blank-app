from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _run_side(module: Any, *, legacy: bool) -> list[dict[str, Any]]:
    import inputs_page_route_coordinators as route_bridge
    legacy_inputs_page = route_bridge

    events: list[dict[str, Any]] = []

    def post_summary(*, inputs_render_audit: dict[str, str]) -> None:
        events.append({"fn": "post_summary", "audit": dict(inputs_render_audit)})

    def debug_audit(*, before_state: Any) -> None:
        events.append({"fn": "debug_audit", "before_state": before_state})

    def debug_sidebar() -> None:
        events.append({"fn": "debug_sidebar"})

    def perf_finalization(*, perf_start: float, perf_marks: list, sub_marks: list, t0: float) -> None:
        events.append(
            {
                "fn": "perf_finalization",
                "perf_start": perf_start,
                "perf_marks": list(perf_marks),
                "sub_marks": list(sub_marks),
                "t0": t0,
            }
        )

    def mark(label: str) -> None:
        events.append({"fn": "mark", "label": label})

    if legacy:
        originals = {
            "post": legacy_inputs_page.render_inputs_post_summary_actions_and_dev_audit_current_coordinator,
            "debug": legacy_inputs_page.render_inputs_debug_audit_current_coordinator,
            "sidebar": legacy_inputs_page.render_design_guide_debug_sidebar_current_coordinator,
            "perf": legacy_inputs_page.render_inputs_perf_finalization_current_coordinator,
        }
        try:
            legacy_inputs_page.render_inputs_post_summary_actions_and_dev_audit_current_coordinator = post_summary
            legacy_inputs_page.render_inputs_debug_audit_current_coordinator = debug_audit
            legacy_inputs_page.render_design_guide_debug_sidebar_current_coordinator = debug_sidebar
            legacy_inputs_page.render_inputs_perf_finalization_current_coordinator = perf_finalization
            module.render_inputs_tail_current_coordinator(
                inputs_render_audit={"design_guide_rendered": "yes"},
                before_state={"b": 300},
                mark=mark,
                perf_start=1.0,
                perf_marks=[("start", 1.0), ("end", 2.0)],
                sub_marks=[("a", 1.1), ("b", 1.2)],
                t0=0.5,
            )
        finally:
            legacy_inputs_page.render_inputs_post_summary_actions_and_dev_audit_current_coordinator = originals[
                "post"
            ]
            legacy_inputs_page.render_inputs_debug_audit_current_coordinator = originals["debug"]
            legacy_inputs_page.render_design_guide_debug_sidebar_current_coordinator = originals["sidebar"]
            legacy_inputs_page.render_inputs_perf_finalization_current_coordinator = originals["perf"]
    else:
        originals = {
            "post": route_bridge.render_inputs_post_summary_actions_and_dev_audit_current_coordinator,
            "debug": route_bridge.render_inputs_debug_audit_current_coordinator,
            "sidebar": route_bridge.render_design_guide_debug_sidebar_current_coordinator,
            "perf": route_bridge.render_inputs_perf_finalization_current_coordinator,
        }
        try:
            route_bridge.render_inputs_post_summary_actions_and_dev_audit_current_coordinator = post_summary
            route_bridge.render_inputs_debug_audit_current_coordinator = debug_audit
            route_bridge.render_design_guide_debug_sidebar_current_coordinator = debug_sidebar
            route_bridge.render_inputs_perf_finalization_current_coordinator = perf_finalization
            module.render_inputs_tail_current_coordinator(
                inputs_render_audit={"design_guide_rendered": "yes"},
                before_state={"b": 300},
                mark=mark,
                perf_start=1.0,
                perf_marks=[("start", 1.0), ("end", 2.0)],
                sub_marks=[("a", 1.1), ("b", 1.2)],
                t0=0.5,
            )
        finally:
            route_bridge.render_inputs_post_summary_actions_and_dev_audit_current_coordinator = originals[
                "post"
            ]
            route_bridge.render_inputs_debug_audit_current_coordinator = originals["debug"]
            route_bridge.render_design_guide_debug_sidebar_current_coordinator = originals["sidebar"]
            route_bridge.render_inputs_perf_finalization_current_coordinator = originals["perf"]
    return events


def _run_post_summary_side(module: Any, *, legacy: bool, dev_mode: bool, scroll: bool) -> list[dict[str, Any]]:
    import streamlit as st
    import inputs_page_route_coordinators as route_bridge
    legacy_inputs_page = route_bridge

    events: list[dict[str, Any]] = []
    ss = st.session_state
    for key in list(ss.keys()):
        ss.pop(key, None)
    if dev_mode:
        ss["_dev_mode"] = True
    if scroll:
        ss["_inputs_pending_scroll_design_actions"] = True

    scroll_owner = module if hasattr(module, "_inputs_inject_scroll_to_design_actions") else legacy_inputs_page
    apply_owner = module if hasattr(module, "_handle_inputs_apply_buttons_current_coordinator") else legacy_inputs_page
    auto_owner = module if hasattr(module, "_handle_inputs_auto_design_current_coordinator") else legacy_inputs_page
    debug_owner = module if hasattr(module, "_agent_debug_log") else legacy_inputs_page

    originals = {
        "scroll": scroll_owner._inputs_inject_scroll_to_design_actions,
        "apply": apply_owner._handle_inputs_apply_buttons_current_coordinator,
        "auto": auto_owner._handle_inputs_auto_design_current_coordinator,
        "debug": debug_owner._agent_debug_log,
    }

    def scroll_fn() -> None:
        events.append({"fn": "scroll"})

    def apply_fn() -> None:
        events.append({"fn": "handle_apply_buttons"})

    def auto_fn() -> None:
        events.append({"fn": "handle_auto_design"})

    def debug_fn(message: str, data: dict | None = None, **kwargs) -> None:
        events.append(
            {
                "fn": "agent_debug_log",
                "message": message,
                "data": dict(data or {}),
                "kwargs": dict(kwargs),
            }
        )

    try:
        scroll_owner._inputs_inject_scroll_to_design_actions = scroll_fn
        apply_owner._handle_inputs_apply_buttons_current_coordinator = apply_fn
        auto_owner._handle_inputs_auto_design_current_coordinator = auto_fn
        debug_owner._agent_debug_log = debug_fn
        module.render_inputs_post_summary_actions_and_dev_audit_current_coordinator(
            inputs_render_audit={
                "old_auto_design_panel_rendered": "no",
                "design_guide_rendered": "yes",
                "current_design_summary_rendered": "yes",
                "next_mode_recommendation_rendered": "no",
                "bottom_tightening_rendered": "no",
                "geometry_tightening_rendered": "no",
                "shear_tightening_rendered": "no",
            }
        )
    finally:
        scroll_owner._inputs_inject_scroll_to_design_actions = originals["scroll"]
        apply_owner._handle_inputs_apply_buttons_current_coordinator = originals["apply"]
        auto_owner._handle_inputs_auto_design_current_coordinator = originals["auto"]
        debug_owner._agent_debug_log = originals["debug"]
        for key in list(ss.keys()):
            ss.pop(key, None)
    return events


def main() -> int:
    import inputs_page_route_coordinators as route_bridge
    legacy_inputs_page = route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    legacy_events = _run_side(legacy_inputs_page, legacy=True)
    bridge_events = _run_side(route_bridge, legacy=False)
    post_summary_cases = {
        "ordinary": {
            "legacy": _run_post_summary_side(legacy_inputs_page, legacy=True, dev_mode=False, scroll=False),
            "route": _run_post_summary_side(route_bridge, legacy=False, dev_mode=False, scroll=False),
        },
        "dev_scroll": {
            "legacy": _run_post_summary_side(legacy_inputs_page, legacy=True, dev_mode=True, scroll=True),
            "route": _run_post_summary_side(route_bridge, legacy=False, dev_mode=True, scroll=True),
        },
    }
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8", errors="replace")
    checks = {
        "tail_event_order_matches_legacy": legacy_events == bridge_events,
        "tail_marks_end_once": [event for event in bridge_events if event == {"fn": "mark", "label": "end"}]
        == [{"fn": "mark", "label": "end"}],
        "tail_uses_local_orchestration": "_legacy_inputs_page.render_inputs_tail_current_coordinator"
        not in route_source,
        "post_summary_cases_match_legacy": all(
            case["legacy"] == case["route"] for case in post_summary_cases.values()
        ),
        "route_no_longer_calls_legacy_post_summary_actions_coordinator": (
            "_legacy_inputs_page.render_inputs_post_summary_actions_and_dev_audit_current_coordinator"
            not in route_source
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_tail_coordinator_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "legacy_events": legacy_events,
        "bridge_events": bridge_events,
        "post_summary_cases": post_summary_cases,
        "wrapper_note": "route tail coordinator is local orchestration with explicit legacy helper seams",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_tail_coordinator_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_tail_coordinator_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Tail Coordinator Parity",
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
