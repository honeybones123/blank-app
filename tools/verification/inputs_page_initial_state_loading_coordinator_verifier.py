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


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_initial_state_loading_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_initial_state_loading_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "st": inputs_page.st,
        "_shared_state_snapshot": inputs_page._shared_state_snapshot,
        "_sync_auto_design_mode_tracking": inputs_page._sync_auto_design_mode_tracking,
        "_resolved_inputs_summary_state": inputs_page._resolved_inputs_summary_state,
        "_inputs_pre_widget_trace": inputs_page._inputs_pre_widget_trace,
        "render_design_guide_terminal_before_loading": inputs_page.render_design_guide_terminal_before_loading,
        "render_design_guide_heading_section": inputs_page.render_design_guide_heading_section,
        "_get_design_guide_fp": inputs_page._get_design_guide_fp,
        "_design_guide_sidebar_debug_enabled": inputs_page._design_guide_sidebar_debug_enabled,
        "_reset_design_guide_reco_trace": inputs_page._reset_design_guide_reco_trace,
        "_mark_design_guide_dirty": inputs_page._mark_design_guide_dirty,
        "_agent_debug_log": inputs_page._agent_debug_log,
        "render_design_guide_loading": inputs_page.render_design_guide_loading,
        "perf_counter": inputs_page.time.perf_counter,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            if name == "perf_counter":
                inputs_page.time.perf_counter = value
            else:
                setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        session: dict[str, Any] | None = None,
        terminal_before_loading: bool = False,
        sidebar_debug: bool = False,
        loading_rendered: bool = False,
    ):
        calls: list[dict[str, Any]] = []
        audit: dict[str, str] = {}
        session_state = dict(session or {})
        shared_state = {"inputs_detailed_mode": False}
        state = {"depth": 500}

        def call(event: str, **payload: Any) -> None:
            calls.append({"event": event, **payload})

        try:
            inputs_page.st = SimpleNamespace(session_state=session_state)
            inputs_page._shared_state_snapshot = lambda: dict(shared_state)
            inputs_page._sync_auto_design_mode_tracking = lambda snapshot: call("sync", snapshot=snapshot)
            inputs_page._resolved_inputs_summary_state = lambda: (dict(state), {"summary": True})
            inputs_page._inputs_pre_widget_trace = lambda label, **payload: call("trace", label=label, payload=payload)
            inputs_page.render_design_guide_terminal_before_loading = (
                lambda *, current_state, inputs_render_audit, stage: (
                    call("terminal_before_loading", current_state=current_state),
                    terminal_before_loading,
                )[1]
            )
            inputs_page.render_design_guide_heading_section = lambda *, stage: call("heading")
            inputs_page._get_design_guide_fp = lambda current_state: f"fp:{current_state['depth']}"
            inputs_page._design_guide_sidebar_debug_enabled = lambda: sidebar_debug
            inputs_page._reset_design_guide_reco_trace = lambda: call("reset_reco_trace")

            def mark_dirty() -> None:
                call("mark_dirty")
                session_state[inputs_page.DESIGN_GUIDE_NEEDS_REFRESH_KEY] = True

            inputs_page._mark_design_guide_dirty = mark_dirty
            inputs_page._agent_debug_log = lambda message, payload, **kwargs: call(
                "agent_debug_log", message=message, payload=payload, kwargs=kwargs
            )
            inputs_page.render_design_guide_loading = lambda **kwargs: (
                call("loading", fingerprint=kwargs["fingerprint"]),
                ({"allowed": True}, loading_rendered),
            )[1]
            ticks = iter([10.0, 10.125])
            inputs_page.time.perf_counter = lambda: next(ticks, 10.125)

            result = inputs_page.render_design_guide_initial_state_and_loading_coordinator(
                inputs_render_audit=audit,
                panel_trace_started=9.5,
                stage=lambda label: call("stage", label=label),
            )
        finally:
            _restore()
        case = {
            "name": name,
            "result": result,
            "audit": audit,
            "session_state": session_state,
            "calls": calls,
        }
        cases.append(case)
        return case

    case = _run_case(
        "terminal_before_loading_returns_early",
        session={"_design_guide_banner_generic_only": True},
        terminal_before_loading=True,
    )
    if case["result"] != ({"depth": 500}, None, False, {}, True, True):
        failures.append(f"terminal_result_mismatch:{case}")
    if any(call["event"] in {"heading", "loading"} for call in case["calls"]):
        failures.append(f"terminal_unexpected_downstream_call:{case}")
    if case["audit"].get("design_guide_rendered") != "yes":
        failures.append(f"terminal_audit_missing:{case}")

    case = _run_case("normal_loading_path")
    if case["result"] != ({"depth": 500}, "fp:500", False, {"allowed": True}, False, False):
        failures.append(f"normal_result_mismatch:{case}")
    if case["session_state"].get(inputs_page.DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY) is not None:
        failures.append(f"normal_cache_items_default_mismatch:{case}")
    if case["session_state"].get(inputs_page.DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY) is not None:
        failures.append(f"normal_cache_fp_default_mismatch:{case}")
    if inputs_page.DESIGN_GUIDE_RECO_TRACE_KEY in case["session_state"]:
        failures.append(f"normal_reco_trace_not_popped:{case}")
    if [call["event"] for call in case["calls"] if call["event"] in {"heading", "loading"}] != ["heading", "loading"]:
        failures.append(f"normal_call_order_mismatch:{case}")

    case = _run_case(
        "publication_fingerprint_dirty_gate",
        session={inputs_page.DESIGN_GUIDE_PUBLICATION_FP_KEY: "old-fp"},
    )
    if "mark_dirty" not in [call["event"] for call in case["calls"]]:
        failures.append(f"dirty_mark_missing:{case}")
    if case["session_state"].get(inputs_page.DESIGN_GUIDE_PANEL_BASELINE_FP_KEY) != "fp:500":
        failures.append(f"dirty_baseline_not_set:{case}")
    if inputs_page.DESIGN_GUIDE_NEEDS_REFRESH_KEY in case["session_state"]:
        failures.append(f"dirty_refresh_not_cleared:{case}")

    case = _run_case(
        "existing_refresh_gate_cleared",
        session={inputs_page.DESIGN_GUIDE_NEEDS_REFRESH_KEY: True},
    )
    if not any(call["event"] == "agent_debug_log" for call in case["calls"]):
        failures.append(f"refresh_debug_log_missing:{case}")
    if case["session_state"].get(inputs_page.DESIGN_GUIDE_PANEL_BASELINE_FP_KEY) != "fp:500":
        failures.append(f"refresh_baseline_not_set:{case}")
    if inputs_page.DESIGN_GUIDE_NEEDS_REFRESH_KEY in case["session_state"]:
        failures.append(f"refresh_not_cleared:{case}")

    case = _run_case(
        "sidebar_debug_resets_trace",
        session={inputs_page.DESIGN_GUIDE_RECO_TRACE_KEY: ["old"]},
        sidebar_debug=True,
    )
    if case["result"][2] is not True:
        failures.append(f"sidebar_flag_mismatch:{case}")
    if "reset_reco_trace" not in [call["event"] for call in case["calls"]]:
        failures.append(f"sidebar_reset_missing:{case}")

    payload = {
        "verifier": "inputs_page_initial_state_loading_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Initial State Loading Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` result={case['result']}" for case in cases),
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
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
