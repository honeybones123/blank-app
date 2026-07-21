from __future__ import annotations

import json
import sys
import ast
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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_render_plan_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_render_plan_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    if not hasattr(inputs_page, "render_design_guide_final_recommendation_and_overlap_debug"):
        current_source = (ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        panel_source = (ROOT / "inputs_page_modules" / "design_guide" / "panel_coordinators.py").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        for token in (
            "def render_design_guide_render_coherence_current_coordinator(",
            "def render_design_guide_render_plan_current_coordinator(",
            "_sync_pending_recommendation_from_guidance(",
            "_design_guide_render_plan(",
            "_design_guide_title_alignment_verification_record(",
        ):
            expect(f"current_missing_{token}", token in current_source, "current coordinator token missing")
        for token in (
            "current_owner.render_design_guide_render_coherence_current_coordinator(",
            "current_owner.render_design_guide_render_plan_current_coordinator(",
            "if bool(_render_plan_result.get(\"early_return\")):",
            "pending_recommendation = _render_plan_result[\"pending_recommendation\"]",
            "render_plan = dict(_render_plan_result[\"render_plan\"] or {})",
        ):
            expect(f"panel_missing_{token}", token in panel_source, "panel coordinator token missing")
        payload = {
            "verifier": "inputs_page_pre_render_plan_pipeline_verifier",
            "status": "PASS" if not failures else "FAIL",
            "mode": "permanent_shell_current_coordinator",
            "failures": failures,
            "retired_inputs_page_granular_probe": True,
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        report_path.write_text(
            "\n".join(
                [
                    "# Inputs Page Pre Render Plan Pipeline Verifier",
                    "",
                    f"Status: `{payload['status']}`",
                    "",
                    "Mode: `permanent_shell_current_coordinator`",
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
            print("failures=" + ",".join(failures))
            return 1
        return 0

    originals = {
        "final_recommendation": inputs_page.render_design_guide_final_recommendation_and_overlap_debug,
        "coherence": inputs_page.render_design_guide_coherence_repair,
        "primary_intent": inputs_page.render_design_guide_primary_intent_display_truth,
        "blocker_materialization": inputs_page.render_design_guide_specific_blocker_proof_materialization,
        "terminal": inputs_page.render_design_guide_terminal_state_derivation,
        "pending": inputs_page.render_design_guide_pending_recommendation,
        "render_plan": inputs_page.render_design_guide_render_plan_setup,
        "not_started": inputs_page.render_design_guide_not_started_fast_render,
        "banner": inputs_page.render_design_guide_displayed_intent_and_banner_reconcile,
        "debug_fields": inputs_page.render_design_guide_render_plan_debug_fields,
        "title_guard": inputs_page.render_design_guide_title_alignment_and_assertion_guard,
    }

    stage_events: list[str] = []

    def stage(name: str) -> None:
        stage_events.append(name)
        calls.append({"event": "stage", "name": name})

    def final_recommendation(**kwargs):
        calls.append(
            {
                "event": "final_recommendation",
                "recommendation_needed": bool(kwargs.get("recommendation_needed")),
            }
        )
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["final_recommendation_called"] = bool(kwargs.get("recommendation_needed"))
        return debug, {"rr": "final"}

    def coherence(**kwargs):
        calls.append({"event": "coherence", "rr": dict(kwargs.get("current_recommendation_result") or {})})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["coherence"] = True
        state = dict(kwargs.get("guidance_disp_state") or {})
        state["coherent"] = True
        items = [dict(item, coherent=True) for item in list(kwargs.get("guidance_items") or [])]
        return debug, state, items, {"rr": "coherent"}, True, ["overview"]

    def primary_intent(**kwargs):
        calls.append({"event": "primary_intent"})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["primary_intent"] = True
        return debug, [dict(item, intent=True) for item in list(kwargs.get("guidance_items") or [])]

    def blocker_materialization(**kwargs):
        calls.append({"event": "blocker_materialization"})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["blocker_materialized"] = True
        return debug, [dict(item, blocker=True) for item in list(kwargs.get("guidance_items") or [])]

    def terminal(**kwargs):
        calls.append({"event": "terminal", "rr": dict(kwargs.get("current_recommendation_result") or {})})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["terminal"] = True
        return debug, {"rr": "terminal"}, "optimal", "derived", {"current_fail_keys": ["bending"]}

    def pending(**kwargs):
        calls.append({"event": "pending", "terminal_state": kwargs.get("terminal_state")})
        return {"pending": True}

    def render_plan(**kwargs):
        calls.append({"event": "render_plan", "collapse": dict(kwargs.get("collapse_meta") or {})})
        return {"visible_guidance_items": list(kwargs.get("guidance_items") or []), "reason": "test"}

    not_started_flag = {"value": False}

    def not_started(**kwargs):
        calls.append({"event": "not_started", "flag": bool(not_started_flag["value"])})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["not_started_checked"] = True
        return bool(not_started_flag["value"]), debug

    def banner(**kwargs):
        calls.append({"event": "banner", "pending": dict(kwargs.get("pending_recommendation") or {})})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["banner"] = True
        return debug, [{"visible": True}], True, "kept_matching_banner", True

    def debug_fields(**kwargs):
        calls.append({"event": "debug_fields", "banner": bool(kwargs.get("render_post_apply_banner"))})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["debug_fields"] = True
        return debug

    def title_guard(**kwargs):
        calls.append(
            {
                "event": "title_guard",
                "coherence_needed": bool(kwargs.get("render_coherence_needed")),
                "coherence_repairs": list(kwargs.get("render_coherence_repairs") or []),
            }
        )
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["title_guard"] = True
        return debug

    try:
        inputs_page.render_design_guide_final_recommendation_and_overlap_debug = final_recommendation
        inputs_page.render_design_guide_coherence_repair = coherence
        inputs_page.render_design_guide_primary_intent_display_truth = primary_intent
        inputs_page.render_design_guide_specific_blocker_proof_materialization = blocker_materialization
        inputs_page.render_design_guide_terminal_state_derivation = terminal
        inputs_page.render_design_guide_pending_recommendation = pending
        inputs_page.render_design_guide_render_plan_setup = render_plan
        inputs_page.render_design_guide_not_started_fast_render = not_started
        inputs_page.render_design_guide_displayed_intent_and_banner_reconcile = banner
        inputs_page.render_design_guide_render_plan_debug_fields = debug_fields
        inputs_page.render_design_guide_title_alignment_and_assertion_guard = title_guard

        normal_result = inputs_page.render_design_guide_pre_render_plan_pipeline(
            guidance_items=[{"id": "primary"}],
            guidance_debug={},
            guidance_disp_state={"case": "normal"},
            current_state={"case": "current"},
            recommendation_result={"rr": "initial"},
            recommendation_needed=False,
            branch_for_recommendation="branch",
            redundancy_meta={"redundant": False},
            family_suppression_meta={"applied": False},
            collapse_meta={"collapsed": True},
            fingerprint="fp",
            terminal_state=None,
            fast_focus_section="guide",
            guidance_fresh_compute_used=True,
            sidebar_debug=True,
            stage=stage,
        )

        not_started_flag["value"] = True
        early_result = inputs_page.render_design_guide_pre_render_plan_pipeline(
            guidance_items=[{"id": "primary"}],
            guidance_debug={},
            guidance_disp_state={"case": "early"},
            current_state={"case": "current"},
            recommendation_result={"rr": "initial"},
            recommendation_needed=True,
            branch_for_recommendation="branch",
            redundancy_meta={},
            family_suppression_meta={},
            collapse_meta={},
            fingerprint="fp",
            terminal_state=None,
            fast_focus_section="guide",
            guidance_fresh_compute_used=False,
            sidebar_debug=False,
            stage=stage,
        )
    finally:
        inputs_page.render_design_guide_final_recommendation_and_overlap_debug = originals["final_recommendation"]
        inputs_page.render_design_guide_coherence_repair = originals["coherence"]
        inputs_page.render_design_guide_primary_intent_display_truth = originals["primary_intent"]
        inputs_page.render_design_guide_specific_blocker_proof_materialization = originals["blocker_materialization"]
        inputs_page.render_design_guide_terminal_state_derivation = originals["terminal"]
        inputs_page.render_design_guide_pending_recommendation = originals["pending"]
        inputs_page.render_design_guide_render_plan_setup = originals["render_plan"]
        inputs_page.render_design_guide_not_started_fast_render = originals["not_started"]
        inputs_page.render_design_guide_displayed_intent_and_banner_reconcile = originals["banner"]
        inputs_page.render_design_guide_render_plan_debug_fields = originals["debug_fields"]
        inputs_page.render_design_guide_title_alignment_and_assertion_guard = originals["title_guard"]

    (
        normal_debug,
        normal_state,
        normal_items,
        normal_rr,
        normal_early,
        normal_repairs,
        normal_terminal_state,
        normal_terminal_source,
        normal_terminal_meta,
        normal_pending,
        normal_render_plan,
        normal_banner_matches,
        normal_visible_items,
        normal_render_banner,
        normal_banner_reconciled,
        normal_coherence_needed,
    ) = normal_result
    (
        early_debug,
        _early_state,
        _early_items,
        _early_rr,
        early_early,
        _early_repairs,
        _early_terminal_state,
        _early_terminal_source,
        _early_terminal_meta,
        _early_pending,
        _early_render_plan,
        early_banner_matches,
        early_visible_items,
        early_render_banner,
        early_banner_reconciled,
        _early_coherence_needed,
    ) = early_result

    expect(
        "normal_path_outputs",
        normal_debug.get("title_guard") is True
        and normal_state.get("coherent") is True
        and normal_items == [{"id": "primary", "coherent": True, "intent": True, "blocker": True}]
        and normal_rr == {"rr": "terminal"}
        and normal_early is False
        and normal_repairs == ["overview"]
        and normal_terminal_state == "optimal"
        and normal_terminal_source == "derived"
        and normal_terminal_meta == {"current_fail_keys": ["bending"]}
        and normal_pending == {"pending": True}
        and normal_render_plan.get("reason") == "test"
        and normal_banner_matches is True
        and normal_visible_items == [{"visible": True}]
        and normal_render_banner is True
        and normal_banner_reconciled == "kept_matching_banner"
        and normal_coherence_needed is True,
        f"normal_result={normal_result}",
    )
    expect(
        "early_path_skips_banner_and_debug_fields",
        early_early is True
        and early_debug.get("not_started_checked") is True
        and early_banner_matches is False
        and early_visible_items == []
        and early_render_banner is False
        and early_banner_reconciled == "not_started_fast_rendered"
        and not any(call["event"] == "banner" and call["pending"] == {"pending": True} for call in calls[-5:]),
        f"early_result={early_result} calls={calls}",
    )
    expect(
        "call_order_and_recommendation_needed",
        [call["event"] for call in calls[:13]]
        == [
            "final_recommendation",
            "coherence",
            "primary_intent",
            "blocker_materialization",
            "terminal",
            "pending",
            "stage",
            "render_plan",
            "stage",
            "not_started",
            "banner",
            "debug_fields",
            "title_guard",
        ]
        and calls[0]["recommendation_needed"] is False
        and any(call["event"] == "final_recommendation" and call["recommendation_needed"] is True for call in calls),
        f"calls={calls}",
    )
    module = ast.parse((ROOT / "inputs_page.py").read_text(encoding="utf-8"))
    fast_panel = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_render_fast_design_guidance_panel"
    )
    pipeline_calls = [
        node
        for node in ast.walk(fast_panel)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "render_design_guide_pre_render_plan_pipeline"
    ]
    terminal_state_keywords = [
        keyword.value
        for call in pipeline_calls
        for keyword in call.keywords
        if keyword.arg == "terminal_state"
    ]
    expect(
        "caller_does_not_pass_unbound_terminal_state",
        len(pipeline_calls) == 1
        and len(terminal_state_keywords) == 1
        and isinstance(terminal_state_keywords[0], ast.Constant)
        and terminal_state_keywords[0].value is None,
        f"pipeline_calls={len(pipeline_calls)} terminal_state_keywords={terminal_state_keywords}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "normal_result": normal_result,
        "early_result": early_result,
        "calls": calls,
        "stage_events": stage_events,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre Render Plan Pipeline Verifier",
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
