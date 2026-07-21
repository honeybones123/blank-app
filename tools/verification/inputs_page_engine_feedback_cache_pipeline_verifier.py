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
    json_path = ARTIFACT_DIR / f"inputs_page_engine_feedback_cache_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_engine_feedback_cache_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []
    stage_events: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "engine": "render_design_guide_engine_presentation_selection",
        "feedback": "render_design_guide_one_click_feedback_debug_state",
        "rebind": "render_design_guide_engine_rebind_outer_probe",
        "restamp_maps": "render_design_guide_restamp_exact_blocker_maps_in_evidence",
        "restamp_current": "render_design_guide_restamp_exact_blocker_current_utils",
        "bundle_update": "render_design_guide_debug_bundle_engine_update_stamping",
        "persist": "render_design_guide_feedback_session_state_persistence",
        "cache": "_set_cached_design_guide_guidance",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}
    original_bundle = inputs_page.st.session_state.get(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY)
    had_original_bundle = inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY in inputs_page.st.session_state

    def stage(name: str) -> None:
        calls.append({"event": "stage", "name": name})
        stage_events.append(name)

    def engine(**kwargs):
        calls.append({"event": "engine", "terminal": kwargs.get("terminal_state")})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["engine"] = True
        return (
            {
                "card": {"candidate_search_evidence": {"family": "bending"}, "exact_blockers_by_family": {"bending": {"reason": "engine"}}},
                "target_band_outcome": {"preview_util": 0.9},
                "debug": {"decision_reason": "test"},
            },
            {"headline": "engine presentation"},
            debug,
        )

    def feedback(**kwargs):
        calls.append({"event": "feedback", "overview": dict(kwargs.get("dg_overview") or {})})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["feedback"] = True
        return debug, "blocked", "reason", {"fp": 1}, {"current": 1}, True, False, True, {"feedback": True}

    def rebind(**kwargs):
        calls.append({"event": "rebind"})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["rebind"] = True
        return debug

    def restamp_maps(payload, visible_utils_for_exact_blockers):
        calls.append(
            {
                "event": "restamp_maps",
                "keys": sorted(dict(payload or {}).keys()),
                "visible_utils": dict(visible_utils_for_exact_blockers or {}),
            }
        )
        out = dict(payload or {})
        out["restamped_maps"] = True
        return out

    def restamp_current(payload, visible_utils_for_exact_blockers):
        calls.append(
            {
                "event": "restamp_current",
                "keys": sorted(dict(payload or {}).keys()),
                "visible_utils": dict(visible_utils_for_exact_blockers or {}),
            }
        )
        out = dict(payload or {})
        out["restamped_current"] = True
        return out

    def bundle_update(**kwargs):
        calls.append(
            {
                "event": "bundle_update",
                "engine_card": dict(kwargs.get("engine_card") or {}),
                "exact": dict(kwargs.get("engine_exact_blockers_for_update") or {}),
                "cleanup": dict(kwargs.get("engine_cleanup_evidence_for_update") or {}),
            }
        )
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["bundle_update"] = True
        kwargs["stage"]("post_plan.after_debug_bundle_engine_update")
        return debug

    def persist(**kwargs):
        calls.append({"event": "persist", "status": kwargs.get("oc_feedback_status")})

    def cache(fingerprint, items, debug):
        calls.append({"event": "cache", "fingerprint": fingerprint, "items": list(items or []), "debug": dict(debug or {})})

    try:
        inputs_page.render_design_guide_engine_presentation_selection = engine
        inputs_page.render_design_guide_one_click_feedback_debug_state = feedback
        inputs_page.render_design_guide_engine_rebind_outer_probe = rebind
        inputs_page.render_design_guide_restamp_exact_blocker_maps_in_evidence = restamp_maps
        inputs_page.render_design_guide_restamp_exact_blocker_current_utils = restamp_current
        inputs_page.render_design_guide_debug_bundle_engine_update_stamping = bundle_update
        inputs_page.render_design_guide_feedback_session_state_persistence = persist
        inputs_page._set_cached_design_guide_guidance = cache
        inputs_page.st.session_state[inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = {"existing": True}

        result = inputs_page.render_design_guide_engine_feedback_cache_pipeline(
            guidance_items=[{"id": "primary"}],
            guidance_items_raw=[{"id": "raw"}],
            guidance_debug={"overview": {"utils": {"bending": 0.4}}},
            guidance_disp_state={"state": True},
            terminal_state="optimal",
            dg_presentation={"headline": "initial"},
            dg_overview={"utils": {"bending": 0.75}},
            visible_utils_for_exact_blockers={"shear": 0.6},
            fingerprint="fp-test",
            stage=stage,
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])
        if had_original_bundle:
            inputs_page.st.session_state[inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = original_bundle
        else:
            try:
                del inputs_page.st.session_state[inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY]
            except Exception:
                pass

    output_engine, output_presentation, output_debug, output_visible_utils = result
    events = [call["event"] for call in calls]
    expect(
        "call_order",
        events
        == [
            "engine",
            "feedback",
            "rebind",
            "stage",
            "restamp_maps",
            "restamp_maps",
            "restamp_maps",
            "restamp_maps",
            "restamp_current",
            "restamp_current",
            "restamp_current",
            "restamp_current",
            "bundle_update",
            "stage",
            "persist",
            "cache",
            "stage",
        ],
        f"events={events} calls={calls}",
    )
    expect(
        "state_flow",
        output_engine.get("card", {}).get("candidate_search_evidence") == {"family": "bending"}
        and output_presentation == {"headline": "engine presentation"}
        and output_debug.get("design_guide_presentation") == {"headline": "engine presentation"}
        and output_debug.get("bundle_update") is True
        and output_visible_utils == {"bending": 0.4}
        and calls[-2]["fingerprint"] == "fp-test"
        and calls[-2]["items"] == [{"id": "raw"}],
        f"result={result} calls={calls}",
    )
    expect(
        "stage_order",
        stage_events
        == [
            "post_plan.before_debug_bundle_engine_update",
            "post_plan.after_debug_bundle_engine_update",
            "post_plan.after_set_cached_guidance",
        ],
        f"stage_events={stage_events}",
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
        "render_design_guide_engine_presentation_selection",
        "render_design_guide_one_click_feedback_debug_state",
        "render_design_guide_engine_rebind_outer_probe",
        "render_design_guide_debug_bundle_engine_update_stamping",
        "render_design_guide_feedback_session_state_persistence",
        "_set_cached_design_guide_guidance",
    }
    expect(
        "fast_panel_delegates_once_without_inline_helper_calls",
        fast_calls.count("render_design_guide_engine_feedback_cache_pipeline") == 1
        and not (removed_direct_calls & set(fast_calls)),
        (
            "pipeline_calls="
            f"{fast_calls.count('render_design_guide_engine_feedback_cache_pipeline')} "
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
        "result": result,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Engine Feedback Cache Pipeline Verifier",
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
