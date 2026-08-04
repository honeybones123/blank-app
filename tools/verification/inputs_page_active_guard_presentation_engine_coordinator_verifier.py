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


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_active_guard_presentation_engine_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_active_guard_presentation_engine_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "render_design_guide_resolved_actions_and_efficiency_state_setup": inputs_page.render_design_guide_resolved_actions_and_efficiency_state_setup,
        "render_design_guide_sidebar_debug_bundle_pipeline": inputs_page.render_design_guide_sidebar_debug_bundle_pipeline,
        "render_design_guide_active_guard_and_local_cleanup_adapter_pipeline": inputs_page.render_design_guide_active_guard_and_local_cleanup_adapter_pipeline,
        "render_design_guide_terminal_overprovided_family_cleanup_coordinator": inputs_page.render_design_guide_terminal_overprovided_family_cleanup_coordinator,
        "render_design_guide_pre_presentation_cleanup_pipeline": inputs_page.render_design_guide_pre_presentation_cleanup_pipeline,
        "_build_design_guide_presentation_state": inputs_page._build_design_guide_presentation_state,
        "render_design_guide_active_strength_repair_presentation_pipeline": inputs_page.render_design_guide_active_strength_repair_presentation_pipeline,
        "render_design_guide_engine_feedback_cache_pipeline": inputs_page.render_design_guide_engine_feedback_cache_pipeline,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(name: str, *, sidebar_debug: bool):
        calls: list[dict[str, Any]] = []
        stage_calls: list[str] = []
        trace_calls: list[dict[str, Any]] = []

        def resolved(**kwargs):
            calls.append({"event": "resolved", "kwargs": dict(kwargs)})
            return {"actions": True}, {"efficiency": True}, "mode-mt", "bottom-bt"

        def sidebar(**kwargs):
            calls.append({"event": "sidebar", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["sidebar"] = True
            return debug

        def active_guard(**kwargs):
            calls.append({"event": "active_guard", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["active_guard"] = True
            return (
                debug,
                [{"title_main": "Guarded"}],
                [{"title_main": "Raw guarded"}],
                "optimal",
                "active_guard_source",
                {"rr": "active_guard"},
                {"overview": True},
                {"mode": True},
                False,
                True,
                False,
            )

        def overprovided(**kwargs):
            calls.append({"event": "overprovided", "kwargs": dict(kwargs)})
            return (
                [{"title_main": "Overprovided"}],
                {"rr": "overprovided"},
                "very_low_demand",
                "overprovided_source",
                {"engine": "early"},
                {"headline": "early"},
                {"reason": "overprovided"},
            )

        def pre_presentation(**kwargs):
            calls.append({"event": "pre_presentation", "kwargs": dict(kwargs)})
            return [{"title_main": "Pre presentation"}], {"rr": "pre_presentation"}

        def build_presentation(**kwargs):
            calls.append({"event": "build_presentation", "kwargs": dict(kwargs)})
            return {"headline": "built", "primary": dict(kwargs["primary_item"] or {})}

        def active_strength(**kwargs):
            calls.append({"event": "active_strength", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["active_strength"] = True
            return [{"title_main": "Strength"}], {"headline": "strength"}, debug

        def engine(**kwargs):
            calls.append({"event": "engine", "kwargs": dict(kwargs)})
            debug = dict(kwargs["guidance_debug"])
            debug["engine"] = True
            return (
                {"engine": "final"},
                {"headline": "final"},
                debug,
                {"bending": 0.95},
            )

        try:
            inputs_page.render_design_guide_resolved_actions_and_efficiency_state_setup = resolved
            inputs_page.render_design_guide_sidebar_debug_bundle_pipeline = sidebar
            inputs_page.render_design_guide_active_guard_and_local_cleanup_adapter_pipeline = active_guard
            inputs_page.render_design_guide_terminal_overprovided_family_cleanup_coordinator = overprovided
            inputs_page.render_design_guide_pre_presentation_cleanup_pipeline = pre_presentation
            inputs_page._build_design_guide_presentation_state = build_presentation
            inputs_page.render_design_guide_active_strength_repair_presentation_pipeline = active_strength
            inputs_page.render_design_guide_engine_feedback_cache_pipeline = engine
            result = inputs_page.render_design_guide_active_guard_presentation_engine_coordinator(
                current_state={"depth": 500},
                guidance_items=[{"title_main": "Input"}],
                guidance_debug={"start": True},
                guidance_disp_state={"depth": 600},
                guidance_items_raw=[{"title_main": "Raw"}],
                terminal_state=None,
                terminal_state_source="input_source",
                recommendation_result={"rr": "input"},
                render_plan={"reason": "input"},
                pending_recommendation={"pending": True},
                guidance_compute_ms=12.5,
                guidance_cache_hit=True,
                guidance_dedupe_meta={"dedupe": True},
                banner_generic_only=False,
                fast_focus_section="guide",
                sidebar_debug=sidebar_debug,
                visible_utils_for_exact_blockers={"old": 1},
                collapsed_guidance_items=[{"collapsed": True}],
                fingerprint="fp-1",
                stage=lambda label: stage_calls.append(label),
                trace=lambda label, **payload: trace_calls.append({"label": label, "payload": payload}),
            )
        finally:
            _restore()
        case = {
            "name": name,
            "sidebar_debug": sidebar_debug,
            "result": result,
            "calls": calls,
            "stage_calls": stage_calls,
            "trace_calls": trace_calls,
        }
        cases.append(case)
        return case

    case = _run_case("sidebar_enabled", sidebar_debug=True)
    if [call["event"] for call in case["calls"]] != [
        "resolved",
        "sidebar",
        "active_guard",
        "overprovided",
        "pre_presentation",
        "build_presentation",
        "active_strength",
        "engine",
    ]:
        failures.append(f"sidebar_call_order_mismatch:{case}")
    result = case["result"]
    if result != (
        [{"title_main": "Strength"}],
        {
            "start": True,
            "sidebar": True,
            "active_guard": True,
            "active_strength": True,
            "engine": True,
        },
        [{"title_main": "Raw guarded"}],
        "very_low_demand",
        "overprovided_source",
        {"rr": "pre_presentation"},
        {"overview": True},
        {"mode": True},
        False,
        {"engine": "final"},
        {"headline": "final"},
        {"bending": 0.95},
    ):
        failures.append(f"sidebar_result_mismatch:{case}")
    sidebar_kwargs = case["calls"][1]["kwargs"]
    if sidebar_kwargs.get("resolved_guidance_actions") != {"actions": True}:
        failures.append(f"sidebar_resolved_actions_mismatch:{case}")
    if sidebar_kwargs.get("recommendation_result") != {"rr": "input"}:
        failures.append(f"sidebar_recommendation_mismatch:{case}")
    active_guard_kwargs = case["calls"][2]["kwargs"]
    if active_guard_kwargs.get("efficiency_state") != {"efficiency": True}:
        failures.append(f"active_guard_efficiency_state_mismatch:{case}")
    overprovided_kwargs = case["calls"][3]["kwargs"]
    if overprovided_kwargs.get("render_plan") != {"reason": "input"}:
        failures.append(f"overprovided_render_plan_mismatch:{case}")
    build_kwargs = case["calls"][5]["kwargs"]
    if build_kwargs.get("pending_recommendation") != {"pending": True}:
        failures.append(f"build_pending_mismatch:{case}")
    active_strength_kwargs = case["calls"][6]["kwargs"]
    if active_strength_kwargs.get("collapsed_guidance_items") != [{"collapsed": True}]:
        failures.append(f"active_strength_collapsed_mismatch:{case}")
    engine_kwargs = case["calls"][7]["kwargs"]
    if engine_kwargs.get("fingerprint") != "fp-1":
        failures.append(f"engine_fingerprint_mismatch:{case}")

    case = _run_case("sidebar_disabled", sidebar_debug=False)
    if [call["event"] for call in case["calls"]] != [
        "resolved",
        "active_guard",
        "overprovided",
        "pre_presentation",
        "build_presentation",
        "active_strength",
        "engine",
    ]:
        failures.append(f"no_sidebar_call_order_mismatch:{case}")

    payload = {
        "verifier": "inputs_page_active_guard_presentation_engine_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active Guard Presentation Engine Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` calls={[call['event'] for call in case['calls']]}" for case in cases),
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
