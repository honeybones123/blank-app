from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_active_guard_and_local_cleanup_adapter_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_active_guard_and_local_cleanup_adapter_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []
    stage_events: list[str] = []
    trace_events: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "overview": "render_design_guide_overview_refresh_and_active_guard_setup",
        "geometry": "render_design_guide_geometry_detailing_guard_branch",
        "locked": "render_design_guide_locked_no_repair_active_failure_guard",
        "active": "render_design_guide_active_failure_visible_truth_priority_branch",
        "post_active": "render_design_guide_post_active_repair_local_cleanup_setup",
        "final_adapter": "render_design_guide_final_local_cleanup_adapter_promotion_branch",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def stage(name: str) -> None:
        calls.append({"event": "stage", "name": name})
        stage_events.append(name)

    def trace(name: str, **kwargs) -> None:
        trace_events.append({"name": name, "kwargs": dict(kwargs)})

    def overview(**kwargs):
        calls.append(
            {
                "event": "overview",
                "items": list(kwargs.get("guidance_items") or []),
                "debug_is_trace": kwargs.get("guidance_debug") is kwargs.get("debug_trace"),
            }
        )
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["overview"] = True
        return (
            debug,
            {"statuses": {"bending": "FAIL"}, "utils": {"bending": 1.2}},
            {"mode": "locked"},
            {"bending"},
            {"id": "primary", "check_key": "cleanup"},
            "cleanup",
            {"updates": {"b": 300}},
            "apply_resolved_candidate",
            {"b": 300},
            False,
            "repair blocked by test",
            {"evidence": True},
            False,
            True,
            {"governing_state": "BENDING_FAIL_GOVERNS"},
        )

    def geometry(**kwargs):
        calls.append(
            {
                "event": "geometry",
                "classifier": dict(kwargs.get("render_governing_classifier") or {}),
                "active": sorted(kwargs.get("active_fail_keys_for_render") or []),
            }
        )
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["geometry"] = True
        return (
            debug,
            [{"id": "geometry_checked"}],
            [{"id": "geometry_raw"}],
            {"bending"},
            {"id": "geometry_checked", "check_key": "cleanup"},
            "cleanup",
        )

    def locked(**kwargs):
        calls.append(
            {
                "event": "locked",
                "active": sorted(kwargs.get("active_fail_keys_for_render") or []),
                "locked": bool(kwargs.get("primary_guard_is_locked_no_repair")),
            }
        )
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["locked"] = True
        return debug, set(kwargs.get("active_fail_keys_for_render") or set())

    def active(**kwargs):
        calls.append(
            {
                "event": "active",
                "primary_key": kwargs.get("primary_guard_key"),
                "source": kwargs.get("terminal_state_source"),
                "rr": kwargs.get("recommendation_result"),
            }
        )
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["active"] = True
        return (
            debug,
            [{"id": "active_priority"}],
            [{"id": "active_raw"}],
            None,
            "active_failure_visible_truth_takes_priority",
            None,
        )

    def post_active(**kwargs):
        calls.append({"event": "post_active", "items": list(kwargs.get("guidance_items") or [])})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["post_active"] = True
        return debug, True, [{"id": "seed"}], 0.42, True, True

    def final_adapter(**kwargs):
        calls.append(
            {
                "event": "final_adapter",
                "seed": list(kwargs.get("local_cleanup_seed_items") or []),
                "skip": bool(kwargs.get("skip_final_local_cleanup_adapter")),
                "efficiency": dict(kwargs.get("efficiency_state") or {}),
            }
        )
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["final_adapter"] = True
        return (
            debug,
            [{"id": "final_adapter_item"}],
            "optimal",
            "adapter_kept_terminal",
            True,
            False,
        )

    try:
        inputs_page.render_design_guide_overview_refresh_and_active_guard_setup = overview
        inputs_page.render_design_guide_geometry_detailing_guard_branch = geometry
        inputs_page.render_design_guide_locked_no_repair_active_failure_guard = locked
        inputs_page.render_design_guide_active_failure_visible_truth_priority_branch = active
        inputs_page.render_design_guide_post_active_repair_local_cleanup_setup = post_active
        inputs_page.render_design_guide_final_local_cleanup_adapter_promotion_branch = final_adapter

        result = inputs_page.render_design_guide_active_guard_and_local_cleanup_adapter_pipeline(
            guidance_debug={"initial": True},
            guidance_disp_state={"state": True},
            guidance_items=[{"id": "start"}],
            guidance_items_raw=[{"id": "start_raw"}],
            terminal_state="initial_terminal",
            terminal_state_source="initial_source",
            recommendation_result={"rr": "initial"},
            efficiency_state={"eta": 0.9},
            stage=stage,
            trace=trace,
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    (
        output_debug,
        output_items,
        output_raw,
        output_terminal_state,
        output_terminal_source,
        output_rr,
        output_overview,
        output_mode,
        output_post_active,
        output_adapter_ran,
        output_adapter_promoted,
    ) = result

    expect(
        "call_order",
        [call["event"] for call in calls]
        == [
            "stage",
            "overview",
            "stage",
            "geometry",
            "locked",
            "active",
            "post_active",
            "final_adapter",
        ],
        f"calls={calls}",
    )
    expect(
        "stage_order",
        stage_events == ["post_plan.after_sidebar_or_debug_bundle", "post_plan.after_dg_overview"],
        f"stage_events={stage_events}",
    )
    expect(
        "state_flow",
        output_debug.get("final_adapter") is True
        and output_items == [{"id": "final_adapter_item"}]
        and output_raw == [{"id": "active_raw"}]
        and output_terminal_state == "optimal"
        and output_terminal_source == "adapter_kept_terminal"
        and output_rr is None
        and output_overview == {"statuses": {"bending": "FAIL"}, "utils": {"bending": 1.2}}
        and output_mode == {"mode": "locked"}
        and output_post_active is True
        and output_adapter_ran is True
        and output_adapter_promoted is False,
        f"result={result}",
    )
    expect(
        "handoff_arguments",
        calls[1]["debug_is_trace"] is True
        and calls[3]["classifier"] == {"governing_state": "BENDING_FAIL_GOVERNS"}
        and calls[5]["source"] == "initial_source"
        and calls[6]["items"] == [{"id": "active_priority"}]
        and calls[7]["seed"] == [{"id": "seed"}]
        and calls[7]["skip"] is True
        and calls[7]["efficiency"] == {"eta": 0.9},
        f"calls={calls}",
    )

    module = ast.parse((ROOT / "inputs_page.py").read_text(encoding="utf-8"))
    fast_panel = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_render_fast_design_guidance_panel"
    )
    fast_calls = [
        node.func.id
        for node in ast.walk(fast_panel)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    removed_direct_calls = {
        "render_design_guide_overview_refresh_and_active_guard_setup",
        "render_design_guide_geometry_detailing_guard_branch",
        "render_design_guide_locked_no_repair_active_failure_guard",
        "render_design_guide_active_failure_visible_truth_priority_branch",
        "render_design_guide_post_active_repair_local_cleanup_setup",
        "render_design_guide_final_local_cleanup_adapter_promotion_branch",
    }
    expect(
        "fast_panel_delegates_once_without_inline_helper_calls",
        fast_calls.count("render_design_guide_active_guard_and_local_cleanup_adapter_pipeline") == 1
        and not (removed_direct_calls & set(fast_calls)),
        (
            "pipeline_calls="
            f"{fast_calls.count('render_design_guide_active_guard_and_local_cleanup_adapter_pipeline')} "
            f"direct={sorted(removed_direct_calls & set(fast_calls))}"
        ),
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "calls": calls,
        "stage_events": stage_events,
        "trace_events": trace_events,
        "result": result,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active Guard And Local Cleanup Adapter Pipeline Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
