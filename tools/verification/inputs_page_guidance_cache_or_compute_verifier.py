from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_guidance_cache_or_compute_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_guidance_cache_or_compute_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_get_cached = inputs_page._get_cached_design_guide_guidance
    original_complete = inputs_page._design_guide_cached_debug_bundle_complete
    original_repair = inputs_page._repair_incomplete_design_guide_cache_debug
    original_clear = inputs_page._clear_design_guide_transient_ui_state
    original_apply = inputs_page._apply_guidance_ui_state
    original_compute = inputs_page._compute_design_guidance_items
    original_trace = inputs_page._inputs_pre_widget_trace
    original_st = inputs_page.st
    original_perf_counter = inputs_page.time.perf_counter

    session_state = {
        inputs_page.DESIGN_GUIDE_APPLY_BANNER_KEY: {"banner": True},
        inputs_page.DESIGN_GUIDE_APPLY_BANNER_META_KEY: {"meta": True},
    }
    perf_values = iter([10.0, 10.125, 20.0, 20.5])

    def complete(debug):
        calls.append({"event": "complete", "debug": dict(debug or {})})
        return bool((debug or {}).get("complete"))

    def repair(state, items, debug):
        calls.append({"event": "repair", "state": dict(state), "items": list(items or []), "debug": dict(debug or {})})
        return bool((debug or {}).get("repair"))

    def clear(**kwargs):
        calls.append({"event": "clear", "kwargs": dict(kwargs)})

    def apply(state, **kwargs):
        calls.append({"event": "apply", "state": dict(state), "kwargs": dict(kwargs)})

    def compute(state, **kwargs):
        calls.append({"event": "compute", "state": dict(state), "kwargs": dict(kwargs)})
        return {
            "guidance_items": [{"title": "computed", "action_type": "apply_resolved_candidate"}],
            "debug_trace": {"computed_debug": True},
        }

    def trace(event_name, **kwargs):
        calls.append({"event": "trace", "event_name": event_name, "kwargs": dict(kwargs)})

    def stage_factory(bucket):
        def stage(name: str) -> None:
            calls.append({"event": f"stage_{bucket}", "name": name})
        return stage

    try:
        inputs_page._design_guide_cached_debug_bundle_complete = complete
        inputs_page._repair_incomplete_design_guide_cache_debug = repair
        inputs_page._clear_design_guide_transient_ui_state = clear
        inputs_page._apply_guidance_ui_state = apply
        inputs_page._compute_design_guidance_items = compute
        inputs_page._inputs_pre_widget_trace = trace
        inputs_page.st = SimpleNamespace(session_state=session_state)
        inputs_page.time.perf_counter = lambda: next(perf_values)

        def cache_hit_current(_fingerprint):
            calls.append({"event": "cache_hit_current", "fingerprint": _fingerprint})
            return (
                [{"title": "cached"}],
                {
                    "design_guide_algorithm_version": inputs_page.DESIGN_GUIDE_ALGORITHM_VERSION,
                    "complete": True,
                },
                True,
            )

        inputs_page._get_cached_design_guide_guidance = cache_hit_current
        cache_hit_result = inputs_page.render_design_guide_guidance_cache_or_compute(
            fingerprint="fp-current",
            current_state={"state": "current"},
            sidebar_debug=False,
            stage_fn=stage_factory("hit"),
        )

        def cache_hit_stale(_fingerprint):
            calls.append({"event": "cache_hit_stale", "fingerprint": _fingerprint})
            return (
                [{"title": "cached stale"}],
                {"design_guide_algorithm_version": "stale", "complete": False, "repair": True},
                True,
            )

        inputs_page._get_cached_design_guide_guidance = cache_hit_stale
        stale_result = inputs_page.render_design_guide_guidance_cache_or_compute(
            fingerprint="fp-stale",
            current_state={"state": "stale"},
            sidebar_debug=True,
            stage_fn=stage_factory("stale"),
        )

        def cache_miss(_fingerprint):
            calls.append({"event": "cache_miss", "fingerprint": _fingerprint})
            return ([], {}, False)

        inputs_page._get_cached_design_guide_guidance = cache_miss
        miss_result = inputs_page.render_design_guide_guidance_cache_or_compute(
            fingerprint="fp-miss",
            current_state={"state": "miss"},
            sidebar_debug=False,
            stage_fn=stage_factory("miss"),
        )
    finally:
        inputs_page._get_cached_design_guide_guidance = original_get_cached
        inputs_page._design_guide_cached_debug_bundle_complete = original_complete
        inputs_page._repair_incomplete_design_guide_cache_debug = original_repair
        inputs_page._clear_design_guide_transient_ui_state = original_clear
        inputs_page._apply_guidance_ui_state = original_apply
        inputs_page._compute_design_guidance_items = original_compute
        inputs_page._inputs_pre_widget_trace = original_trace
        inputs_page.st = original_st
        inputs_page.time.perf_counter = original_perf_counter

    expect(
        "cache_hit_path",
        cache_hit_result
        == (
            [{"title": "cached"}],
            {
                "design_guide_algorithm_version": inputs_page.DESIGN_GUIDE_ALGORITHM_VERSION,
                "complete": True,
            },
            True,
            False,
            True,
            True,
            False,
            False,
            False,
        )
        and not any(call["event"] == "compute" for call in calls[:3]),
        f"cache_hit_result={cache_hit_result} calls={calls[:5]}",
    )
    expect(
        "stale_recompute_path",
        stale_result[0] == [{"title": "computed", "action_type": "apply_resolved_candidate"}]
        and stale_result[1] == {"computed_debug": True}
        and stale_result[2:] == (False, True, True, False, True, True, True)
        and inputs_page.DESIGN_GUIDE_APPLY_BANNER_KEY not in session_state
        and inputs_page.DESIGN_GUIDE_APPLY_BANNER_META_KEY not in session_state,
        f"stale_result={stale_result} session_state={session_state}",
    )
    expect(
        "miss_recompute_path",
        miss_result[0] == [{"title": "computed", "action_type": "apply_resolved_candidate"}]
        and miss_result[1] == {"computed_debug": True}
        and miss_result[2:] == (False, True, False, False, False, True, True),
        f"miss_result={miss_result}",
    )
    expect(
        "stage_trace_and_clear_calls",
        {"event": "clear", "kwargs": {"clear_history": False, "preserve_apply_banner": True}} in calls
        and {"event": "stage_stale", "name": "before_apply_ui_state"} in calls
        and {"event": "stage_stale", "name": "before_compute_guidance"} in calls
        and {"event": "stage_stale", "name": "after_compute_guidance"} in calls
        and {"event": "stage_miss", "name": "before_apply_ui_state"} in calls
        and any(
            call["event"] == "trace"
            and call["event_name"] == "_compute_design_guidance_items.for_design_guide"
            and call["kwargs"].get("item_count") == 1
            for call in calls
        ),
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "cache_hit_result": cache_hit_result,
        "stale_result": stale_result,
        "miss_result": miss_result,
        "calls": calls,
        "session_state": session_state,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Guidance Cache Or Compute Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
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
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
