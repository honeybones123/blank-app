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
    json_path = ARTIFACT_DIR / f"inputs_page_active_strength_repair_presentation_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_active_strength_repair_presentation_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []
    stage_events: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "fail_key": "render_design_guide_active_strength_fail_key_setup",
        "identity": "render_design_guide_active_strength_repair_identity_setup",
        "item": "render_design_guide_active_strength_repair_item_setup",
        "evidence": "render_design_guide_active_strength_repair_evidence_update_setup",
        "evaluate": "_evaluate_auto_design_candidate",
        "payload": "render_design_guide_active_strength_repair_payload_stamping",
        "band": "_resolved_efficiency_target_band",
        "mode": "_design_mode_config",
        "goal": "_design_optimisation_goal",
        "distance": "_candidate_search_distance_to_band",
        "exact": "_exact_cleanup_blocker_for_outside_target_action",
        "stamp": "render_design_guide_active_strength_repair_presentation_debug_stamping",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def stage(name: str) -> None:
        calls.append({"event": "stage", "name": name})
        stage_events.append(name)

    def fail_key(**kwargs):
        calls.append({"event": "fail_key", "headline": dict(kwargs.get("dg_presentation") or {}).get("headline")})
        return {"bending"}

    def identity(**kwargs):
        calls.append({"event": "identity", "keys": sorted(kwargs.get("active_strength_fail_keys_for_card") or [])})
        return "bending", "Bending capacity is low", "BENDING_FAIL_GOVERNS"

    def item(**kwargs):
        calls.append({"event": "item", "title": kwargs.get("active_repair_title")})
        return (
            {
                "id": "repair",
                "action_type": "apply_resolved_candidate",
                "button_contract": {"enabled": True},
                "action_payload": {"payload": True},
                "resolved_candidate": {"resolved": True},
            },
            {"enabled": True, "updates": {"b": 360}, "candidate_id": "repair-a"},
        )

    def evidence(**kwargs):
        calls.append({"event": "evidence", "family": kwargs.get("active_repair_family")})
        return (
            dict(kwargs.get("active_repair_item") or {}),
            dict(kwargs.get("active_repair_contract") or {}),
            {"generated_count": 1},
            {"b": 360},
            0.7,
            {"updates": {"b": 360}},
        )

    def evaluate(*args, **kwargs):
        calls.append({"event": "evaluate", "source": kwargs.get("source"), "updates": dict(kwargs.get("updates") or {})})
        return {"overview": {"utils": {"bending": 0.62}}, "candidate_post_util": 0.62}

    def payload(**kwargs):
        calls.append({"event": "payload", "expected": kwargs.get("active_repair_expected_util")})
        item_out = dict(kwargs.get("active_repair_item") or {})
        payload_out = dict(item_out.get("action_payload") or {"payload": True})
        resolved_out = dict(item_out.get("resolved_candidate") or {"resolved": True})
        return item_out, payload_out, resolved_out

    def exact(**kwargs):
        calls.append({"event": "exact", "family": kwargs.get("family"), "final": kwargs.get("final_util")})
        return {"reason": "accepted-band cleanup blocked", "family": kwargs.get("family")}

    def stamp(**kwargs):
        calls.append(
            {
                "event": "stamp",
                "title": kwargs.get("active_repair_title"),
                "expected": kwargs.get("active_repair_expected_util"),
                "collapsed": list(kwargs.get("collapsed_guidance_items") or []),
                "evidence": dict(kwargs.get("active_repair_evidence") or {}),
            }
        )
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["stamped"] = True
        presentation = dict(kwargs.get("dg_presentation") or {})
        presentation["headline"] = kwargs.get("active_repair_title")
        return [dict(kwargs.get("active_repair_item") or {}, stamped=True)], presentation, debug

    try:
        inputs_page.render_design_guide_active_strength_fail_key_setup = fail_key
        inputs_page.render_design_guide_active_strength_repair_identity_setup = identity
        inputs_page.render_design_guide_active_strength_repair_item_setup = item
        inputs_page.render_design_guide_active_strength_repair_evidence_update_setup = evidence
        inputs_page._evaluate_auto_design_candidate = evaluate
        inputs_page.render_design_guide_active_strength_repair_payload_stamping = payload
        inputs_page._resolved_efficiency_target_band = lambda *args, **kwargs: (0.85, 1.0, 0.925)
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "balanced"
        inputs_page._candidate_search_distance_to_band = lambda util, low, high: round(low - util, 3)
        inputs_page._exact_cleanup_blocker_for_outside_target_action = exact
        inputs_page.render_design_guide_active_strength_repair_presentation_debug_stamping = stamp

        result = inputs_page.render_design_guide_active_strength_repair_presentation_pipeline(
            guidance_items=[{"id": "initial", "action_type": "apply_resolved_candidate"}],
            dg_overview={"statuses": {"bending": "FAIL"}},
            dg_presentation={"headline": "Bending capacity is low"},
            guidance_debug={"overview": {"utils": {"bending": 0.4}}},
            debug_trace={"overview": {"statuses": {"bending": "FAIL"}}},
            guidance_disp_state={"state": True},
            collapsed_guidance_items=[{"id": "collapsed"}],
            stage=stage,
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    output_items, output_presentation, output_debug = result
    expect(
        "call_order",
        [call["event"] for call in calls]
        == ["stage", "fail_key", "identity", "item", "evidence", "evaluate", "payload", "exact", "stamp"],
        f"calls={calls}",
    )
    expect(
        "stage_order",
        stage_events == ["post_plan.after_presentation_state"],
        f"stage_events={stage_events}",
    )
    stamp_call = calls[-1] if calls else {}
    expect(
        "evidence_and_output_flow",
        output_debug.get("stamped") is True
        and output_items
        and output_items[0].get("stamped") is True
        and output_presentation.get("headline") == "Bending capacity is low"
        and stamp_call.get("expected") == 0.62
        and stamp_call.get("collapsed") == [{"id": "collapsed"}]
        and stamp_call.get("evidence", {}).get("selected_candidate_util") == 0.62
        and stamp_call.get("evidence", {}).get("exact_blockers_by_family") == {
            "bending": {"family": "bending", "reason": "accepted-band cleanup blocked"}
        },
        f"result={result} calls={calls}",
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
        "render_design_guide_active_strength_fail_key_setup",
        "render_design_guide_active_strength_repair_identity_setup",
        "render_design_guide_active_strength_repair_item_setup",
        "render_design_guide_active_strength_repair_evidence_update_setup",
        "render_design_guide_active_strength_repair_payload_stamping",
        "render_design_guide_active_strength_repair_presentation_debug_stamping",
    }
    expect(
        "fast_panel_delegates_once_without_inline_helper_calls",
        fast_calls.count("render_design_guide_active_strength_repair_presentation_pipeline") == 1
        and not (removed_direct_calls & set(fast_calls)),
        (
            "pipeline_calls="
            f"{fast_calls.count('render_design_guide_active_strength_repair_presentation_pipeline')} "
            f"direct={sorted(removed_direct_calls & set(fast_calls))}"
        ),
    )
    pipeline_calls = [
        node
        for node in ast.walk(fast_panel)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "render_design_guide_active_strength_repair_presentation_pipeline"
    ]
    debug_trace_keywords = [
        keyword.value
        for call in pipeline_calls
        for keyword in call.keywords
        if keyword.arg == "debug_trace"
    ]
    expect(
        "caller_passes_bound_guidance_debug_as_debug_trace",
        len(debug_trace_keywords) == 1
        and isinstance(debug_trace_keywords[0], ast.Name)
        and debug_trace_keywords[0].id == "guidance_debug",
        f"debug_trace_keywords={debug_trace_keywords}",
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
                "# Inputs Page Active Strength Repair Presentation Pipeline Verifier",
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
