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


class _Expander:
    def __init__(self, events: list[dict[str, Any]], label: str, expanded: bool) -> None:
        self.events = events
        self.label = label
        self.expanded = expanded

    def __enter__(self):
        self.events.append({"fn": "expander_enter", "label": self.label, "expanded": self.expanded})
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.events.append({"fn": "expander_exit", "label": self.label})
        return False


class _FakeSidebar:
    def __init__(self, events: list[dict[str, Any]], *, clear_pressed: bool) -> None:
        self.events = events
        self.clear_pressed = clear_pressed

    def divider(self) -> None:
        self.events.append({"fn": "divider"})

    def caption(self, text: str) -> None:
        self.events.append({"fn": "caption", "text": text})

    def button(self, label: str, **kwargs: Any) -> bool:
        self.events.append({"fn": "button", "label": label, "kwargs": dict(kwargs)})
        return self.clear_pressed

    def warning(self, text: str) -> None:
        self.events.append({"fn": "warning", "text": text})

    def code(self, value: str) -> None:
        self.events.append({"fn": "code", "value": value})

    def expander(self, label: str, *, expanded: bool = False):
        self.events.append({"fn": "expander", "label": label, "expanded": expanded})
        return _Expander(self.events, label, expanded)


class _FakeStreamlit:
    def __init__(self, session_state: dict[str, Any], events: list[dict[str, Any]], *, clear_pressed: bool) -> None:
        self.session_state = session_state
        self.sidebar = _FakeSidebar(events, clear_pressed=clear_pressed)
        self.events = events

    def json(self, value: Any) -> None:
        self.events.append({"fn": "json", "value": value})

    def rerun(self) -> None:
        self.events.append({"fn": "rerun"})


def _session_state(*, enabled: bool) -> dict[str, Any]:
    return {
        "inputs_design_guide_debug_sidebar_v1": enabled,
        "_force_auto_redesign": True,
        "_auto_design_auto_invoke": False,
        "_auto_design_request_source": "test-source",
        "_auto_design_requested_at_ts": 123.4,
        "auto_design_invoke_pending": True,
        "auto_design_idle_reason": "idle",
        "auto_design_invoke_set": True,
        "auto_design_invoke_consumed": False,
        "canonical_convenience_resync_applied": True,
        "canonical_convenience_fields_updated": ["nb_bot"],
        "convenience_field_drift_detected": False,
        "_dg_live_breadcrumb": {
            "label": "render",
            "ts": "2026-07-18T23:00:00",
            "extra": {"phase": "test"},
        },
        "_design_guide_debug_bundle": {
            "guidance_branch": "branch",
            "governing_action": "bending",
            "primary_utils": {"bending": 0.91},
            "selected_action_type": "apply",
            "selected_title": "Recommendation",
            "guidance_items_summary": ["item"],
            "overview": {
                "utils": {"shear": 0.82},
                "statuses": {"shear": "PASS"},
                "stage3_shear_truth_debug": {"status": "ok"},
            },
            "current_design_summary": {"n": 1},
            "next_mode_recommendation": "tighten",
            "bottom_tightening": "ok",
            "design_guide_shear_truth_source": "published",
            "stage3_remaining_issue_class": "none",
            "stage3_shear_truth_debug": {"path": "final"},
            "fingerprints": {"fp": "abc"},
            "resolved_guidance_actions": {"Mu": 100},
            "design_guide_step_history_compact": [{"step": 1}],
        },
        "_design_guide_reco_trace": [
            {"event": "accepted", "id": 1},
            {"event": "rejected", "id": 2},
        ],
        "_design_guide_rank_trace": ["rank"],
        "_design_guide_apply_banner_payload": {"banner": True},
        "_design_guide_apply_banner_meta": {"meta": True},
        "_design_guide_cached_fingerprint": "fp",
        "_design_guide_cached_items": ["cached"],
        "_design_guide_cached_debug": {"debug": True},
        "_design_guide_fp": "simple-fp",
        "_design_guide_cache": ["simple"],
        "_design_guide_pending_step_ctx": {"ctx": True},
        "_design_guide_step_history": [{"step": 1}],
        "_design_guide_first_target_band_step": 1,
        "_design_guide_history_anchor": {"anchor": True},
    }


def _run(module: Any, *, legacy: bool, enabled: bool, clear_pressed: bool) -> dict[str, Any]:
    import inputs_page_route_coordinators as route_bridge

    events: list[dict[str, Any]] = []
    session_state = _session_state(enabled=enabled)
    fake_st = _FakeStreamlit(session_state, events, clear_pressed=clear_pressed)
    if legacy:
        originals = {"st": route_bridge.st}
        try:
            route_bridge.st = fake_st
            module.render_design_guide_debug_sidebar(
                st_module=fake_st,
                sidebar_debug_enabled_fn=route_bridge._design_guide_sidebar_debug_enabled,
                clear_transient_ui_state_fn=route_bridge._clear_design_guide_transient_ui_state,
                auto_design_invoke_debug_snapshot_fn=route_bridge._auto_design_invoke_debug_snapshot,
                debug_bundle_key=route_bridge.DESIGN_GUIDE_DEBUG_BUNDLE_KEY,
                reco_trace_key=route_bridge.DESIGN_GUIDE_RECO_TRACE_KEY,
            )
        finally:
            route_bridge.st = originals["st"]
    else:
        originals = {"st": route_bridge.st}
        try:
            route_bridge.st = fake_st
            module.render_design_guide_debug_sidebar_current_coordinator()
        finally:
            route_bridge.st = originals["st"]
    return {"events": events, "session_state": session_state}


def main() -> int:
    import inputs_page_modules.design_guide.debug_sidebar as debug_sidebar_module
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    for case_name, enabled, clear_pressed in (
        ("disabled", False, False),
        ("enabled", True, False),
        ("clear_pressed", True, True),
    ):
        legacy_result = _run(
            debug_sidebar_module,
            legacy=True,
            enabled=enabled,
            clear_pressed=clear_pressed,
        )
        route_result = _run(
            route_bridge,
            legacy=False,
            enabled=enabled,
            clear_pressed=clear_pressed,
        )
        cases[case_name] = {"legacy": legacy_result, "route": route_result}
        checks[f"{case_name}_events_match"] = legacy_result["events"] == route_result["events"]
        checks[f"{case_name}_session_keys_match"] = sorted(legacy_result["session_state"].keys()) == sorted(
            route_result["session_state"].keys()
        )

    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["debug_sidebar_does_not_delegate_to_old_page"] = (
        "_legacy_inputs_page._render_design_guide_debug_sidebar" not in route_source
    )
    checks["route_wrapper_delegates_to_debug_sidebar_module"] = (
        "render_design_guide_debug_sidebar(" in route_source
        and "inputs_page_modules.design_guide.debug_sidebar" in route_source
    )
    checks["enabled_contains_rejection_count"] = any(
        event.get("fn") == "json"
        and isinstance(event.get("value"), dict)
        and event["value"].get("rejection_count") == 1
        for event in cases["enabled"]["route"]["events"]
    )
    checks["clear_pressed_reruns"] = any(
        event.get("fn") == "rerun" for event in cases["clear_pressed"]["route"]["events"]
    )

    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_design_guide_debug_sidebar_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "case_event_counts": {
            name: {
                "legacy": len(case["legacy"]["events"]),
                "route": len(case["route"]["events"]),
            }
            for name, case in cases.items()
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_design_guide_debug_sidebar_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_design_guide_debug_sidebar_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Design Guide Debug Sidebar Parity",
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
