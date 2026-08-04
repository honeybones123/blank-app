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


def _clear_session() -> None:
    import streamlit as st

    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)


def _seed_session(state: dict[str, Any]) -> None:
    import streamlit as st
    from state_and_helpers import SHARED_DEFAULTS

    _clear_session()
    for key, default in SHARED_DEFAULTS.items():
        st.session_state[key] = state.get(key, default)
    for key, value in state.items():
        st.session_state[key] = value


def _canonical_case(state: dict[str, Any]) -> dict[str, Any]:
    import inputs_page_app_contract_bridge as bridge

    legacy_fields = bridge._canonical_convenience_fields_from_state(dict(state))
    bridge_fields = bridge._canonical_convenience_fields_from_state_for_app_bridge(dict(state))
    return {
        "fields_match": legacy_fields == bridge_fields,
        "legacy_fields": legacy_fields,
        "bridge_fields": bridge_fields,
    }


def _apply_resync_case(state: dict[str, Any]) -> dict[str, Any]:
    import inputs_page_app_contract_bridge as bridge
    import streamlit as st

    legacy_calls: list[tuple[str, Any, str]] = []
    bridge_calls: list[tuple[str, Any, str]] = []
    original_bridge_set_shared = bridge.set_shared
    original_bridge_agent_debug = getattr(bridge, "_agent_debug_log", None)

    def _legacy_set_shared(key, value, *, source=""):
        legacy_calls.append((str(key), value, str(source)))
        st.session_state[str(key)] = value

    def _bridge_set_shared(key, value, *, source=""):
        bridge_calls.append((str(key), value, str(source)))
        st.session_state[str(key)] = value

    try:
        if original_bridge_agent_debug is not None:
            bridge._agent_debug_log = lambda *args, **kwargs: None

        bridge.set_shared = _legacy_set_shared
        _seed_session(state)
        legacy_return = bridge._apply_canonical_convenience_resync_to_shared(
            source="parity:legacy"
        )
        legacy_session = {
            key: st.session_state.get(key)
            for key in (
                "canonical_convenience_resync_source",
                "canonical_convenience_resync_valid",
                "canonical_convenience_resync_reason",
                "canonical_convenience_resync_skipped",
                "canonical_convenience_resync_skip_reason",
                "canonical_convenience_resync_applied",
                "canonical_convenience_fields_updated",
                "convenience_field_drift_detected",
            )
        }

        bridge.set_shared = _bridge_set_shared
        _seed_session(state)
        bridge_return = bridge._apply_canonical_convenience_resync_to_shared_for_app_bridge(
            source="parity:legacy"
        )
        bridge_session = {
            key: st.session_state.get(key)
            for key in legacy_session
        }
    finally:
        bridge.set_shared = original_bridge_set_shared
        if original_bridge_agent_debug is not None:
            bridge._agent_debug_log = original_bridge_agent_debug

    return {
        "return_match": legacy_return == bridge_return,
        "session_match": legacy_session == bridge_session,
        "set_shared_calls_match": legacy_calls == bridge_calls,
        "legacy_return": legacy_return,
        "bridge_return": bridge_return,
        "legacy_session": legacy_session,
        "bridge_session": bridge_session,
        "legacy_set_shared_calls": legacy_calls,
        "bridge_set_shared_calls": bridge_calls,
    }


def _route_case(session_state: dict[str, Any]) -> dict[str, Any]:
    import inputs_page_route_coordinators as route

    calls: list[tuple[str, Any]] = []
    original_resync = route._apply_canonical_convenience_resync_to_shared_for_app_bridge
    original_persist = route.persist_active_beam_from_shared

    def _resync(*, source: str):
        calls.append(("resync", source))
        return {"source": source}

    def _persist():
        calls.append(("persist", None))

    ss = dict(session_state)
    try:
        route._apply_canonical_convenience_resync_to_shared_for_app_bridge = _resync
        route.persist_active_beam_from_shared = _persist
        result = route.render_inputs_post_widget_autopersist_current_coordinator(ss=ss)
    finally:
        route._apply_canonical_convenience_resync_to_shared_for_app_bridge = original_resync
        route.persist_active_beam_from_shared = original_persist
    return {
        "result": result,
        "session": ss,
        "calls": calls,
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    base = {
        "sec_shape": "RECT",
        "b": 300,
        "D": 600,
        "cover_top": 40,
        "cover_bot": 40,
        "cover_side": 40,
        "rowgap_top": 60,
        "rowgap_bot": 60,
        "lig_d": 10,
        "lig_legs": 2,
        "bot1_count": 3,
        "bot2_count": 2,
        "db_bot_1": 20,
        "db_bot_2": 16,
        "top1_count": 2,
        "top2_count": 0,
        "db_top_1": 16,
        "db_top_2": 16,
    }
    t_state = {
        **base,
        "sec_shape": "T",
        "b": 700,
        "bf": 700,
        "tf": 120,
        "bw": 250,
        "bot1_count": 4,
        "db_bot_1": 24,
    }
    no_bars = {
        **base,
        "bot1_count": 0,
        "bot2_count": 0,
        "top1_count": 0,
        "top2_count": 0,
        "db_bot_1": 0,
        "db_bot_2": 0,
        "db_top_1": 0,
        "db_top_2": 0,
    }

    canonical_cases = {
        "rect_two_rows": _canonical_case(base),
        "t_section": _canonical_case(t_state),
        "no_bars": _canonical_case(no_bars),
    }
    apply_cases = {
        "rect_two_rows": _apply_resync_case(base),
        "no_bars": _apply_resync_case(no_bars),
    }
    route_cases = {
        "skip_once": _route_case({"_beam_skip_auto_persist_once": True, "inputs_dirty": True}),
        "dirty": _route_case({"_beam_skip_auto_persist_once": False, "inputs_dirty": True}),
        "clean": _route_case({"_beam_skip_auto_persist_once": False, "inputs_dirty": False}),
    }

    checks = {
        "all_canonical_fields_match_legacy": all(case["fields_match"] for case in canonical_cases.values()),
        "all_apply_returns_match_legacy": all(case["return_match"] for case in apply_cases.values()),
        "all_apply_sessions_match_legacy": all(case["session_match"] for case in apply_cases.values()),
        "all_apply_set_shared_calls_match_legacy": all(case["set_shared_calls_match"] for case in apply_cases.values()),
        "route_skip_clears_flag_without_side_effects": (
            route_cases["skip_once"]["result"] is True
            and route_cases["skip_once"]["session"].get("_beam_skip_auto_persist_once") is False
            and route_cases["skip_once"]["calls"] == []
        ),
        "route_dirty_resyncs_then_persists": (
            route_cases["dirty"]["result"] is False
            and route_cases["dirty"]["calls"] == [
                ("resync", "inputs_page:inputs_dirty_autopersist"),
                ("persist", None),
            ]
        ),
        "route_clean_has_no_side_effects": (
            route_cases["clean"]["result"] is False
            and route_cases["clean"]["calls"] == []
        ),
    }
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    bridge_source = (ROOT / "inputs_page_app_contract_bridge.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["route_post_widget_no_old_page_delegate"] = (
        "_legacy_inputs_page.render_inputs_post_widget_autopersist_current_coordinator" not in route_source
    )
    checks["app_bridge_canonical_resync_no_old_page_delegate"] = (
        "_legacy_inputs_page._apply_canonical_convenience_resync_to_shared" not in bridge_source
        and "_legacy_inputs_page._canonical_convenience_fields_from_state" not in bridge_source
        and "_legacy_inputs_page._build_canonical_design_state_pack" not in bridge_source
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_post_widget_autopersist_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "canonical_cases": canonical_cases,
        "apply_cases": apply_cases,
        "route_cases": route_cases,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_post_widget_autopersist_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_post_widget_autopersist_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Post Widget Autopersist Parity",
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
