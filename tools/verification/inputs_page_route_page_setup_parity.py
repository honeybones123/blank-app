from __future__ import annotations

import json
import importlib.util
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


def _load_archived_legacy_inputs_page():
    candidates = sorted((ROOT / "artifacts" / "audits").glob("legacy_inputs_page_removed_*.py"))
    if not candidates:
        raise RuntimeError("No archived legacy inputs_page reference found for parity comparison")
    path = candidates[-1]
    spec = importlib.util.spec_from_file_location("_archived_legacy_inputs_page", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load archived legacy inputs_page reference: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalise_value(value: Any) -> Any:
    if callable(value):
        return f"callable:{getattr(value, '__name__', type(value).__name__)}"
    if isinstance(value, dict):
        return {str(key): _normalise_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalise_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalise_value(item) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return f"object:{type(value).__name__}"


def _normalise_context(context: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalise_value(value) for key, value in context.items()}


def _run_side(module: Any, *, legacy: bool, debug_enabled: bool) -> dict[str, Any]:
    legacy_inputs_page = module
    import inputs_page_route_coordinators as route_bridge

    events: list[dict[str, Any]] = []
    ss: dict[str, Any] = {"page_slug": "inputs", "beam_order": ["B1"], "active_beam_id": "B1"}

    def initial_session(*, ss: dict) -> None:
        events.append({"fn": "initial_session", "ss_keys": sorted(ss.keys())})
        ss.setdefault("_result_cache", None)

    def hydration_trace(phase: str, **extra: object) -> None:
        events.append({"fn": "hydration_trace", "phase": phase, "extra": dict(extra)})

    def fast_get_param(key: str, default: Any = None) -> Any:
        return {"d": 500, "b": 300}.get(key, default)

    def param_snapshot() -> tuple[dict[str, Any], Any]:
        events.append({"fn": "param_snapshot"})
        return {"d": 500, "b": 300}, fast_get_param

    def perf_marker_setup(*, ss: dict) -> tuple:
        events.append({"fn": "perf_marker_setup"})
        perf_marks: list[tuple[str, float]] = []
        sub_marks: list[tuple[str, float]] = []

        def mark(label: str) -> None:
            events.append({"fn": "mark", "label": label})
            perf_marks.append((label, float(len(perf_marks) + 1)))

        def sub_mark(label: str) -> None:
            events.append({"fn": "sub_mark", "label": label})
            sub_marks.append((label, float(len(sub_marks) + 1)))

        return 10.0, 11.0, perf_marks, sub_marks, mark, sub_mark

    def page_load_start(*, ss: dict) -> float:
        events.append({"fn": "page_load_start", "ss_keys": sorted(ss.keys())})
        return 12.0

    def startup_hydration(*, ss: dict, mark) -> None:
        events.append({"fn": "startup_hydration", "mark": getattr(mark, "__name__", repr(mark))})

    def pre_widget_setup(*, ss: dict, fast_get_param) -> tuple:
        events.append({"fn": "pre_widget_setup", "d": fast_get_param("d")})
        return True, "geometry", {"sync_a": object()}, {"audit": "live"}

    def audit_snapshot() -> dict[str, Any]:
        events.append({"fn": "audit_snapshot"})
        return {"before": "state"}

    def dev_sidebar(*, ss: dict) -> None:
        events.append({"fn": "dev_sidebar"})

    def summary_container() -> str:
        events.append({"fn": "summary_container"})
        return "summary-container"

    def batch_context(*, ss: dict) -> tuple[dict[str, str], list[str], str]:
        events.append({"fn": "batch_context"})
        return {"B1": "Beam 1"}, ["B1"], "B1"

    def batch_manager(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "batch_manager",
                "beam_labels": dict(kwargs.get("beam_labels") or {}),
                "beam_order": list(kwargs.get("beam_order") or []),
                "active_beam_id": kwargs.get("active_beam_id"),
            }
        )

    def page_divider() -> None:
        events.append({"fn": "page_divider"})

    def design_mode_selector(*, sync_callbacks: dict) -> bool:
        events.append({"fn": "design_mode_selector", "sync_keys": sorted(sync_callbacks.keys())})
        return False

    if legacy:
        originals = {
            "debug": legacy_inputs_page._INPUTS_DEBUG_AUDIT,
            "st": legacy_inputs_page.st,
            "initial": legacy_inputs_page.render_inputs_initial_session_state_coordinator,
            "trace": legacy_inputs_page._inputs_hydration_trace_log,
            "params": legacy_inputs_page.render_inputs_param_snapshot_coordinator,
            "perf": legacy_inputs_page.render_inputs_perf_marker_setup_coordinator,
            "load": legacy_inputs_page.render_inputs_page_load_start_coordinator,
            "startup": legacy_inputs_page.render_inputs_startup_hydration_coordinator,
            "pre_widget": legacy_inputs_page.render_inputs_pre_widget_apply_and_render_setup_coordinator,
            "audit": legacy_inputs_page._inputs_audit_snapshot_state,
            "sidebar": legacy_inputs_page.render_inputs_dev_session_debug_sidebar_coordinator,
            "batch_context": legacy_inputs_page.render_inputs_batch_design_context_coordinator,
            "batch_manager": legacy_inputs_page.render_inputs_batch_design_manager_coordinator,
            "divider": legacy_inputs_page.page_divider,
            "mode": legacy_inputs_page.render_inputs_design_mode_selector_coordinator,
        }
        try:
            legacy_inputs_page._INPUTS_DEBUG_AUDIT = debug_enabled
            legacy_inputs_page.st = SimpleNamespace(container=summary_container)
            legacy_inputs_page.render_inputs_initial_session_state_coordinator = initial_session
            legacy_inputs_page._inputs_hydration_trace_log = hydration_trace
            legacy_inputs_page.render_inputs_param_snapshot_coordinator = param_snapshot
            legacy_inputs_page.render_inputs_perf_marker_setup_coordinator = perf_marker_setup
            legacy_inputs_page.render_inputs_page_load_start_coordinator = page_load_start
            legacy_inputs_page.render_inputs_startup_hydration_coordinator = startup_hydration
            legacy_inputs_page.render_inputs_pre_widget_apply_and_render_setup_coordinator = pre_widget_setup
            legacy_inputs_page._inputs_audit_snapshot_state = audit_snapshot
            legacy_inputs_page.render_inputs_dev_session_debug_sidebar_coordinator = dev_sidebar
            legacy_inputs_page.render_inputs_batch_design_context_coordinator = batch_context
            legacy_inputs_page.render_inputs_batch_design_manager_coordinator = batch_manager
            legacy_inputs_page.page_divider = page_divider
            legacy_inputs_page.render_inputs_design_mode_selector_coordinator = design_mode_selector
            context = module.render_inputs_page_setup_current_coordinator(ss=ss)
        finally:
            legacy_inputs_page._INPUTS_DEBUG_AUDIT = originals["debug"]
            legacy_inputs_page.st = originals["st"]
            legacy_inputs_page.render_inputs_initial_session_state_coordinator = originals["initial"]
            legacy_inputs_page._inputs_hydration_trace_log = originals["trace"]
            legacy_inputs_page.render_inputs_param_snapshot_coordinator = originals["params"]
            legacy_inputs_page.render_inputs_perf_marker_setup_coordinator = originals["perf"]
            legacy_inputs_page.render_inputs_page_load_start_coordinator = originals["load"]
            legacy_inputs_page.render_inputs_startup_hydration_coordinator = originals["startup"]
            legacy_inputs_page.render_inputs_pre_widget_apply_and_render_setup_coordinator = originals[
                "pre_widget"
            ]
            legacy_inputs_page._inputs_audit_snapshot_state = originals["audit"]
            legacy_inputs_page.render_inputs_dev_session_debug_sidebar_coordinator = originals["sidebar"]
            legacy_inputs_page.render_inputs_batch_design_context_coordinator = originals["batch_context"]
            legacy_inputs_page.render_inputs_batch_design_manager_coordinator = originals["batch_manager"]
            legacy_inputs_page.page_divider = originals["divider"]
            legacy_inputs_page.render_inputs_design_mode_selector_coordinator = originals["mode"]
    else:
        originals = {
            "initial": route_bridge.render_inputs_initial_session_state_coordinator,
            "trace": route_bridge.inputs_hydration_trace_log,
            "params": route_bridge.render_inputs_param_snapshot_coordinator,
            "perf": route_bridge.render_inputs_perf_marker_setup_coordinator,
            "load": route_bridge.render_inputs_page_load_start_coordinator,
            "startup": route_bridge.render_inputs_startup_hydration_coordinator,
            "pre_widget": route_bridge.render_inputs_pre_widget_apply_and_render_setup_coordinator,
            "debug": route_bridge.inputs_debug_audit_enabled,
            "audit": route_bridge.inputs_audit_snapshot_state,
            "sidebar": route_bridge.render_inputs_dev_session_debug_sidebar_coordinator,
            "container": route_bridge.create_summary_container,
            "batch_context": route_bridge.render_inputs_batch_design_context_coordinator,
            "batch_manager": route_bridge.render_inputs_batch_design_manager_coordinator,
            "divider": route_bridge.render_inputs_page_divider_coordinator,
            "mode": route_bridge.render_inputs_design_mode_selector_coordinator,
        }
        try:
            route_bridge.render_inputs_initial_session_state_coordinator = initial_session
            route_bridge.inputs_hydration_trace_log = hydration_trace
            route_bridge.render_inputs_param_snapshot_coordinator = param_snapshot
            route_bridge.render_inputs_perf_marker_setup_coordinator = perf_marker_setup
            route_bridge.render_inputs_page_load_start_coordinator = page_load_start
            route_bridge.render_inputs_startup_hydration_coordinator = startup_hydration
            route_bridge.render_inputs_pre_widget_apply_and_render_setup_coordinator = pre_widget_setup
            route_bridge.inputs_debug_audit_enabled = lambda: debug_enabled
            route_bridge.inputs_audit_snapshot_state = audit_snapshot
            route_bridge.render_inputs_dev_session_debug_sidebar_coordinator = dev_sidebar
            route_bridge.create_summary_container = summary_container
            route_bridge.render_inputs_batch_design_context_coordinator = batch_context
            route_bridge.render_inputs_batch_design_manager_coordinator = batch_manager
            route_bridge.render_inputs_page_divider_coordinator = page_divider
            route_bridge.render_inputs_design_mode_selector_coordinator = design_mode_selector
            context = module.render_inputs_page_setup_current_coordinator(ss=ss)
        finally:
            route_bridge.render_inputs_initial_session_state_coordinator = originals["initial"]
            route_bridge.inputs_hydration_trace_log = originals["trace"]
            route_bridge.render_inputs_param_snapshot_coordinator = originals["params"]
            route_bridge.render_inputs_perf_marker_setup_coordinator = originals["perf"]
            route_bridge.render_inputs_page_load_start_coordinator = originals["load"]
            route_bridge.render_inputs_startup_hydration_coordinator = originals["startup"]
            route_bridge.render_inputs_pre_widget_apply_and_render_setup_coordinator = originals[
                "pre_widget"
            ]
            route_bridge.inputs_debug_audit_enabled = originals["debug"]
            route_bridge.inputs_audit_snapshot_state = originals["audit"]
            route_bridge.render_inputs_dev_session_debug_sidebar_coordinator = originals["sidebar"]
            route_bridge.create_summary_container = originals["container"]
            route_bridge.render_inputs_batch_design_context_coordinator = originals["batch_context"]
            route_bridge.render_inputs_batch_design_manager_coordinator = originals["batch_manager"]
            route_bridge.render_inputs_page_divider_coordinator = originals["divider"]
            route_bridge.render_inputs_design_mode_selector_coordinator = originals["mode"]

    return {"events": events, "context": _normalise_context(context)}


def main() -> int:
    legacy_inputs_page = _load_archived_legacy_inputs_page()
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}

    for debug_enabled in (False, True):
        case_name = "debug_on" if debug_enabled else "debug_off"
        legacy_result = _run_side(legacy_inputs_page, legacy=True, debug_enabled=debug_enabled)
        bridge_result = _run_side(route_bridge, legacy=False, debug_enabled=debug_enabled)
        cases[case_name] = {
            "legacy": legacy_result,
            "bridge": bridge_result,
        }
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_context_matches_legacy"] = legacy_result["context"] == bridge_result["context"]
        checks[f"{case_name}_audit_snapshot_expected"] = (
            any(event["fn"] == "audit_snapshot" for event in bridge_result["events"]) == debug_enabled
        )

    bridge_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["page_setup_uses_local_orchestration"] = (
        "_legacy_inputs_page.render_inputs_page_setup_current_coordinator" not in bridge_source
    )
    checks["page_setup_marks_start_and_beam_manager"] = [
        event for event in cases["debug_off"]["bridge"]["events"] if event["fn"] in {"mark", "sub_mark"}
    ] == [
        {"fn": "mark", "label": "start"},
        {"fn": "mark", "label": "beam_manager"},
        {"fn": "sub_mark", "label": "start"},
    ]

    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_page_setup_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
        "wrapper_note": "route page setup is local orchestration with explicit legacy helper seams",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_page_setup_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_page_setup_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Page Setup Parity",
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
