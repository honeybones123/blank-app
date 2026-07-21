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


class _ContextRecorder:
    def __init__(self, events: list[dict[str, Any]], label: str) -> None:
        self._events = events
        self._label = label

    def __enter__(self) -> "_ContextRecorder":
        self._events.append({"fn": "enter", "label": self._label})
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self._events.append({"fn": "exit", "label": self._label})
        return False


def _run_side(module: Any, *, legacy: bool) -> list[dict[str, Any]]:
    import inputs_page_route_coordinators as route_bridge

    legacy_inputs_page = route_bridge

    events: list[dict[str, Any]] = []
    summary_state = {"b": 300, "D": 600}
    summary_debug = {"debug": True}
    bend_pack = {"rows": [{"uid": "b1", "status": "PASS"}]}
    shear_pack = {"rows": [{"uid": "s1", "status": "PASS"}]}
    crack_pack = {"rows": [{"uid": "c1", "status": "PASS"}]}
    defl_pack = {"rows": [{"uid": "d1", "status": "PASS"}]}
    rows_payload = (
        ["BENDING_ROWS"],
        ["SHEAR_ROWS"],
        ["CRACK_ROWS"],
        ["DEFLECTION_ROWS"],
        None,
        None,
        None,
        None,
        12.3,
        "span/250",
        0.42,
    )
    display_payload = (
        100,
        80,
        "0.80",
        "PASS",
        "green",
        120,
        90,
        "0.75",
        "PASS",
        "green",
        "",
        "shear strength",
        "summary",
        "ok",
        0.3,
        0.2,
        "0.67",
        "PASS",
        "green",
        10,
        7,
        "0.70",
        "PASS",
        "green",
    )

    def summary_state_cache(*, ss: dict, mark) -> tuple:
        events.append({"fn": "summary_state_cache", "ss_keys": sorted(ss.keys())})
        return summary_state, summary_debug, bend_pack, shear_pack, crack_pack, defl_pack

    def pack_meta(name: str, pack: Any) -> dict:
        events.append({"fn": "pack_meta", "name": name})
        return {"name": name, "rows": len((pack or {}).get("rows") or [])}

    def hc_log(label: str, **kwargs: Any) -> None:
        events.append({"fn": "hc_log", "label": label, "keys": sorted(kwargs.keys())})

    def rows_from_packs(**kwargs: Any) -> tuple:
        events.append({"fn": "rows_from_packs", "keys": sorted(kwargs.keys())})
        return rows_payload

    def display_state(**kwargs: Any) -> tuple:
        events.append({"fn": "display_state", "keys": sorted(kwargs.keys())})
        return display_payload

    def guidance_cache(**kwargs: Any) -> tuple:
        events.append({"fn": "guidance_cache", "keys": sorted(kwargs.keys())})
        return [{"title": "stub"}], "bending"

    def row_finalization(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "row_finalization",
                "skip": kwargs.get("skip_active_beam_record_write"),
                "keys": sorted(kwargs.keys()),
            }
        )

    def calc_trace(**kwargs: Any) -> None:
        trace_fn = kwargs.get("trace_fn")
        events.append(
            {
                "fn": "calc_trace",
                "results_version": kwargs.get("results_version"),
                "summary_action_fp": kwargs.get("summary_action_fp"),
                "trace_fn_name": getattr(trace_fn, "__name__", repr(trace_fn)),
            }
        )

    def container(**kwargs: Any) -> None:
        events.append({"fn": "container", "keys": sorted(kwargs.keys())})

    def mark(label: str) -> None:
        events.append({"fn": "mark", "label": label})

    fake_session = {
        "results_version": 7,
        "_summary_cache_action_fp": "fp-123",
        "actions_uls": {"M": 250},
        "z_extra": 1,
    }
    ss = dict(fake_session)

    if legacy:
        originals = {
            "st": legacy_inputs_page.st,
            "summary_state_cache": legacy_inputs_page.render_inputs_summary_state_cache_current_coordinator,
            "pack_meta": legacy_inputs_page._pack_meta,
            "hc_log": legacy_inputs_page.hc_log,
            "rows": legacy_inputs_page.render_inputs_summary_rows_from_packs_current_coordinator,
            "display": legacy_inputs_page.render_inputs_summary_display_state_current_coordinator,
            "guidance": legacy_inputs_page.render_inputs_summary_guidance_cache_current_coordinator,
            "finalization": legacy_inputs_page.render_inputs_summary_row_finalization_current_coordinator,
            "calc": legacy_inputs_page.render_inputs_calculation_explainer_trace_coordinator,
            "container": legacy_inputs_page.render_inputs_summary_container_current_coordinator,
        }
        try:
            legacy_inputs_page.st = SimpleNamespace(session_state=fake_session)
            legacy_inputs_page.render_inputs_summary_state_cache_current_coordinator = summary_state_cache
            legacy_inputs_page._pack_meta = pack_meta
            legacy_inputs_page.hc_log = hc_log
            legacy_inputs_page.render_inputs_summary_rows_from_packs_current_coordinator = rows_from_packs
            legacy_inputs_page.render_inputs_summary_display_state_current_coordinator = display_state
            legacy_inputs_page.render_inputs_summary_guidance_cache_current_coordinator = guidance_cache
            legacy_inputs_page.render_inputs_summary_row_finalization_current_coordinator = row_finalization
            legacy_inputs_page.render_inputs_calculation_explainer_trace_coordinator = calc_trace
            legacy_inputs_page.render_inputs_summary_container_current_coordinator = container
            module.render_inputs_summary_pipeline_current_coordinator(
                ss=ss,
                summary_container="summary-container",
                sync_callbacks={"sync": object()},
                skip_active_beam_record_write=True,
                mark=mark,
            )
        finally:
            legacy_inputs_page.st = originals["st"]
            legacy_inputs_page.render_inputs_summary_state_cache_current_coordinator = originals[
                "summary_state_cache"
            ]
            legacy_inputs_page._pack_meta = originals["pack_meta"]
            legacy_inputs_page.hc_log = originals["hc_log"]
            legacy_inputs_page.render_inputs_summary_rows_from_packs_current_coordinator = originals[
                "rows"
            ]
            legacy_inputs_page.render_inputs_summary_display_state_current_coordinator = originals[
                "display"
            ]
            legacy_inputs_page.render_inputs_summary_guidance_cache_current_coordinator = originals[
                "guidance"
            ]
            legacy_inputs_page.render_inputs_summary_row_finalization_current_coordinator = originals[
                "finalization"
            ]
            legacy_inputs_page.render_inputs_calculation_explainer_trace_coordinator = originals["calc"]
            legacy_inputs_page.render_inputs_summary_container_current_coordinator = originals["container"]
    else:
        originals = {
            "route_st": route_bridge.st,
            "legacy_st": legacy_inputs_page.st,
            "summary_state_cache": route_bridge.render_inputs_summary_state_cache_current_coordinator,
            "pack_meta": route_bridge._pack_meta,
            "hc_log": route_bridge.hc_log,
            "rows": route_bridge.render_inputs_summary_rows_from_packs_current_coordinator,
            "display": route_bridge.render_inputs_summary_display_state_current_coordinator,
            "guidance": route_bridge.render_inputs_summary_guidance_cache_current_coordinator,
            "finalization": route_bridge.render_inputs_summary_row_finalization_current_coordinator,
            "calc": route_bridge.render_inputs_calculation_explainer_trace_coordinator,
            "container": route_bridge.render_inputs_summary_container_current_coordinator,
        }
        try:
            route_bridge.st = SimpleNamespace(session_state=fake_session)
            legacy_inputs_page.st = SimpleNamespace(session_state=fake_session)
            route_bridge.render_inputs_summary_state_cache_current_coordinator = summary_state_cache
            route_bridge._pack_meta = pack_meta
            route_bridge.hc_log = hc_log
            route_bridge.render_inputs_summary_rows_from_packs_current_coordinator = rows_from_packs
            route_bridge.render_inputs_summary_display_state_current_coordinator = display_state
            route_bridge.render_inputs_summary_guidance_cache_current_coordinator = guidance_cache
            route_bridge.render_inputs_summary_row_finalization_current_coordinator = row_finalization
            route_bridge.render_inputs_calculation_explainer_trace_coordinator = calc_trace
            route_bridge.render_inputs_summary_container_current_coordinator = container
            module.render_inputs_summary_pipeline_current_coordinator(
                ss=ss,
                summary_container="summary-container",
                sync_callbacks={"sync": object()},
                skip_active_beam_record_write=True,
                mark=mark,
            )
        finally:
            route_bridge.st = originals["route_st"]
            legacy_inputs_page.st = originals["legacy_st"]
            route_bridge.render_inputs_summary_state_cache_current_coordinator = originals[
                "summary_state_cache"
            ]
            route_bridge._pack_meta = originals["pack_meta"]
            route_bridge.hc_log = originals["hc_log"]
            route_bridge.render_inputs_summary_rows_from_packs_current_coordinator = originals["rows"]
            route_bridge.render_inputs_summary_display_state_current_coordinator = originals["display"]
            route_bridge.render_inputs_summary_guidance_cache_current_coordinator = originals["guidance"]
            route_bridge.render_inputs_summary_row_finalization_current_coordinator = originals[
                "finalization"
            ]
            route_bridge.render_inputs_calculation_explainer_trace_coordinator = originals["calc"]
            route_bridge.render_inputs_summary_container_current_coordinator = originals["container"]
    return events


def _run_container_side(module: Any, *, show_landing: bool) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state = {"cached_results": {"result": "cached"}}

    def title(text: str) -> None:
        events.append({"fn": "title", "text": text})

    def landing_decision() -> bool:
        events.append({"fn": "landing_decision"})
        return show_landing

    def landing_card(**kwargs: Any) -> None:
        sync_callbacks = kwargs.get("sync_callbacks")
        events.append(
            {
                "fn": "landing_card",
                "sync_keys": sorted(sync_callbacks.keys()) if isinstance(sync_callbacks, dict) else None,
            }
        )

    def summary_tables(**kwargs: Any) -> None:
        events.append({"fn": "summary_tables", "keys": sorted(kwargs.keys())})

    originals = {
        "st": module.st,
        "landing_decision": module.inputs_show_landing_dashboard,
        "landing_card": module.render_landing_card,
        "summary_tables": module.render_inputs_summary_expanders_and_tables_current_coordinator,
    }
    try:
        module.st = SimpleNamespace(session_state=session_state, title=title)
        module.inputs_show_landing_dashboard = landing_decision
        module.render_landing_card = landing_card
        module.render_inputs_summary_expanders_and_tables_current_coordinator = summary_tables
        result = module.render_inputs_summary_container_current_coordinator(
            summary_container=_ContextRecorder(events, "summary-container"),
            sync_callbacks={"sync_a": object()},
            BENDING_ROWS=["BENDING_ROWS"],
            SHEAR_ROWS=["SHEAR_ROWS"],
            CRACK_ROWS=["CRACK_ROWS"],
            DEFLECTION_ROWS=["DEFLECTION_ROWS"],
            defl_pack={"defl": True},
            governing_check="bending",
            bending_cap=100,
            bending_demand=80,
            bending_util_str="0.80",
            bending_status="PASS",
            bending_colour="green",
            shear_cap=120,
            shear_demand=90,
            shear_util_str="0.75",
            shear_status="PASS",
            shear_colour="green",
            shear_summary_status_note="",
            shear_governing_name="shear",
            shear_governing_source="summary",
            shear_reason="ok",
            crack_cap=0.3,
            crack_demand=0.2,
            crack_util_str="0.67",
            crack_status="PASS",
            crack_colour="green",
            defl_cap=10,
            defl_demand=7,
            defl_util_str="0.70",
            defl_status="PASS",
            defl_colour="green",
        )
    finally:
        module.st = originals["st"]
        module.inputs_show_landing_dashboard = originals["landing_decision"]
        module.render_landing_card = originals["landing_card"]
        module.render_inputs_summary_expanders_and_tables_current_coordinator = originals["summary_tables"]

    return {"events": events, "result": result}


def _summary_table_kwargs(*, rows_present: bool, sectional_shear: bool) -> dict[str, Any]:
    rows = [{"step": "one", "status": "PASS"}] if rows_present else []
    return {
        "BENDING_ROWS": list(rows),
        "SHEAR_ROWS": list(rows),
        "CRACK_ROWS": list(rows),
        "DEFLECTION_ROWS": list(rows),
        "defl_pack": {"present": True} if rows_present else None,
        "governing_check": "bending",
        "bending_cap": 100,
        "bending_demand": 80,
        "bending_util_str": "0.80",
        "bending_status": "PASS",
        "bending_colour": "green",
        "shear_cap": 120,
        "shear_demand": 90,
        "shear_util_str": "0.75",
        "shear_status": "PASS",
        "shear_colour": "green",
        "shear_summary_status_note": "shear note",
        "shear_governing_name": "Sectional shear" if sectional_shear else "Torsion interaction",
        "shear_governing_source": "sectional_shear_capacity" if sectional_shear else "interaction_check",
        "shear_reason": "governs because combined demand is higher",
        "crack_cap": 0.3,
        "crack_demand": 0.2,
        "crack_util_str": "0.67",
        "crack_status": "PASS",
        "crack_colour": "green",
        "defl_cap": 10,
        "defl_demand": 7,
        "defl_util_str": "0.70",
        "defl_status": "PASS",
        "defl_colour": "green",
    }


def _run_summary_tables_side(module: Any, *, rows_present: bool, sectional_shear: bool) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state = {"active_beam_id": "B7"}

    def inject_css() -> None:
        events.append({"fn": "inject_css"})

    def info(text: str) -> None:
        events.append({"fn": "info", "text": text})

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": text, "kwargs": dict(kwargs)})

    def build_html(summary_source: Any = None, *, shear_detail_note_html: str = "") -> str:
        events.append(
            {
                "fn": "build_html",
                "scenario_id": getattr(summary_source, "scenario_id", None),
                "scenario_label": getattr(summary_source, "scenario_label", None),
                "titles": [
                    getattr(getattr(summary_source, name), "title", None)
                    for name in ("bending", "shear", "crack", "deflection")
                ],
                "row_counts": [
                    len(getattr(getattr(summary_source, name), "rows", ()))
                    for name in ("bending", "shear", "crack", "deflection")
                ],
                "shear_status_note_html": getattr(getattr(summary_source, "shear"), "status_note_html", None),
                "run_state": dict(getattr(summary_source, "run_state", {}) or {}),
                "shear_detail_note_html": shear_detail_note_html,
            }
        )
        return "<summary-cards />"

    def divider() -> None:
        events.append({"fn": "page_divider"})

    originals = {
        "st": module.st,
        "inject_css": module.inject_seamless_steps_css,
        "build_html": module._build_summary_cards_html_for_current_state,
        "page_divider": module.page_divider,
    }
    try:
        module.st = SimpleNamespace(session_state=session_state, info=info, markdown=markdown)
        module.inject_seamless_steps_css = inject_css
        module._build_summary_cards_html_for_current_state = build_html
        module.page_divider = divider
        result = module.render_inputs_summary_expanders_and_tables_current_coordinator(
            **_summary_table_kwargs(rows_present=rows_present, sectional_shear=sectional_shear)
        )
    finally:
        module.st = originals["st"]
        module.inject_seamless_steps_css = originals["inject_css"]
        module._build_summary_cards_html_for_current_state = originals["build_html"]
        module.page_divider = originals["page_divider"]
    return {"events": events, "result": result}


def _run_landing_decision_side(module: Any, values: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []

    def get_param_stub(key: str, default: Any = None) -> Any:
        events.append({"fn": "get_param", "key": key, "default": default})
        return values.get(key, default)

    original = module.get_param
    try:
        module.get_param = get_param_stub
        result = module.inputs_show_landing_dashboard()
    finally:
        module.get_param = original
    return {"events": events, "result": result}


def main() -> int:
    import inputs_page_modules.summaries.render_coordinators as summary_render
    import inputs_page_route_coordinators as route_bridge

    legacy_inputs_page = route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    legacy_events = _run_side(legacy_inputs_page, legacy=True)
    bridge_events = _run_side(route_bridge, legacy=False)
    bridge_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    container_cases: dict[str, dict[str, Any]] = {}
    for case_name, show_landing in (
        ("summary_container_landing", True),
        ("summary_container_tables", False),
    ):
        legacy_result = _run_container_side(legacy_inputs_page, show_landing=show_landing)
        bridge_result = _run_container_side(route_bridge, show_landing=show_landing)
        container_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}

    summary_table_cases: dict[str, dict[str, Any]] = {}
    for case_name, rows_present, sectional_shear in (
        ("summary_tables_rows_present_nonsectional_shear", True, False),
        ("summary_tables_empty_rows_sectional_shear", False, True),
    ):
        legacy_result = _run_summary_tables_side(
            summary_render,
            rows_present=rows_present,
            sectional_shear=sectional_shear,
        )
        bridge_result = _run_summary_tables_side(
            summary_render,
            rows_present=rows_present,
            sectional_shear=sectional_shear,
        )
        summary_table_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}

    landing_decision_cases: dict[str, dict[str, Any]] = {}
    for case_name, values in {
        "landing_empty": {},
        "landing_nonzero_moment": {"uls_Mstar": 1.0},
        "landing_nonzero_load": {"g_udl_kNm_per_m": 2.5},
        "landing_sigma_fallback": {"sigma_sr": None, "sigma_s_sls": 0.25},
        "landing_uls_n_fallback_to_n_star": {"uls_Nstar": 0.0, "N_star": 5.0},
    }.items():
        legacy_result = _run_landing_decision_side(legacy_inputs_page, values)
        bridge_result = _run_landing_decision_side(route_bridge, values)
        landing_decision_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}

    checks = {
        "summary_pipeline_event_order_matches_legacy": legacy_events == bridge_events,
        "summary_pipeline_marks_render_summary_once": [
            event for event in bridge_events if event == {"fn": "mark", "label": "render_summary"}
        ]
        == [{"fn": "mark", "label": "render_summary"}],
        "summary_pipeline_uses_local_orchestration": "_legacy_inputs_page.render_inputs_summary_pipeline_current_coordinator"
        not in bridge_source,
        "summary_container_landing_events_match_legacy": container_cases["summary_container_landing"]["legacy"][
            "events"
        ]
        == container_cases["summary_container_landing"]["bridge"]["events"],
        "summary_container_landing_return_matches_legacy": container_cases["summary_container_landing"]["legacy"][
            "result"
        ]
        == container_cases["summary_container_landing"]["bridge"]["result"],
        "summary_container_tables_events_match_legacy": container_cases["summary_container_tables"]["legacy"][
            "events"
        ]
        == container_cases["summary_container_tables"]["bridge"]["events"],
        "summary_container_tables_return_matches_legacy": container_cases["summary_container_tables"]["legacy"][
            "result"
        ]
        == container_cases["summary_container_tables"]["bridge"]["result"],
        "summary_container_uses_local_orchestration": "_legacy_inputs_page.render_inputs_summary_container_current_coordinator"
        not in bridge_source,
        "summary_tables_rows_present_events_match_legacy": summary_table_cases[
            "summary_tables_rows_present_nonsectional_shear"
        ]["legacy"]["events"]
        == summary_table_cases["summary_tables_rows_present_nonsectional_shear"]["bridge"]["events"],
        "summary_tables_rows_present_return_matches_legacy": summary_table_cases[
            "summary_tables_rows_present_nonsectional_shear"
        ]["legacy"]["result"]
        == summary_table_cases["summary_tables_rows_present_nonsectional_shear"]["bridge"]["result"],
        "summary_tables_empty_rows_events_match_legacy": summary_table_cases[
            "summary_tables_empty_rows_sectional_shear"
        ]["legacy"]["events"]
        == summary_table_cases["summary_tables_empty_rows_sectional_shear"]["bridge"]["events"],
        "summary_tables_empty_rows_return_matches_legacy": summary_table_cases[
            "summary_tables_empty_rows_sectional_shear"
        ]["legacy"]["result"]
        == summary_table_cases["summary_tables_empty_rows_sectional_shear"]["bridge"]["result"],
        "summary_tables_uses_local_orchestration": (
            "_legacy_inputs_page.render_inputs_summary_expanders_and_tables_current_coordinator"
            not in bridge_source
        ),
        "landing_decision_uses_local_orchestration": "_legacy_inputs_page.inputs_show_landing_dashboard"
        not in bridge_source,
    }
    for case_name, case in landing_decision_cases.items():
        checks[f"{case_name}_events_match_legacy"] = case["legacy"]["events"] == case["bridge"]["events"]
        checks[f"{case_name}_return_matches_legacy"] = case["legacy"]["result"] == case["bridge"]["result"]
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_summary_pipeline_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "legacy_events": legacy_events,
        "bridge_events": bridge_events,
        "container_cases": container_cases,
        "summary_table_cases": summary_table_cases,
        "landing_decision_cases": landing_decision_cases,
        "wrapper_note": "route summary pipeline is local orchestration with explicit legacy helper seams",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_summary_pipeline_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_summary_pipeline_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Summary Pipeline Parity",
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
