from __future__ import annotations

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
    json_path = ARTIFACT_DIR / (
        "inputs_page_post_cleanup_early_shear_refreshed_action_debug_render_return_"
        f"{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        "inputs_page_post_cleanup_early_shear_refreshed_action_debug_render_return_"
        f"{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []
    render_calls: list[dict] = []
    stage_calls: list[str] = []
    session_key = inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY
    original_render = inputs_page._render_guidance_secondary_items
    original_session_present = session_key in inputs_page.st.session_state
    original_session_value = inputs_page.st.session_state.get(session_key)

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def render_items(
        items,
        *,
        guidance_disp_state,
        current_overview,
        inputs_render_audit,
        start_index,
        primary_card_presentation,
    ):
        render_calls.append(
            {
                "items": list(items or []),
                "guidance_disp_state": dict(guidance_disp_state or {}),
                "current_overview": dict(current_overview or {}),
                "inputs_render_audit": dict(inputs_render_audit or {}),
                "start_index": start_index,
                "primary_card_presentation": dict(primary_card_presentation or {}),
            }
        )

    def stage(marker: str) -> None:
        stage_calls.append(marker)

    def reset_case_session(value_marker):
        nonlocal render_calls, stage_calls
        render_calls = []
        stage_calls = []
        inputs_page.st.session_state.pop(session_key, None)
        if value_marker is not None:
            inputs_page.st.session_state[session_key] = value_marker

    try:
        inputs_page._render_guidance_secondary_items = render_items

        reset_case_session({"existing": "keep"})
        noop_action = {
            "title_main": "Noop",
            "candidate_search_evidence": {"keep": "yes"},
        }
        noop_debug = {"preexisting": True}
        noop_result = (
            inputs_page.render_design_guide_post_cleanup_early_shear_refreshed_action_debug_render_return(
                early_shear_cleanup_contract_renderable=False,
                early_shear_cleanup_action=noop_action,
                early_shear_cleanup_contract={"updates": {"s_lig": 150}},
                early_shear_cleanup_state={"D": 500},
                early_shear_cleanup_overview={"util": 0.75},
                guidance_debug=noop_debug,
                inputs_render_audit={"audit": "noop"},
                stage=stage,
            )
        )
        cases.append(
            {
                "name": "not_renderable_noop",
                "result": noop_result,
                "action": dict(noop_action),
                "guidance_debug": dict(noop_debug),
                "session_debug": dict(inputs_page.st.session_state.get(session_key) or {}),
                "render_calls": list(render_calls),
                "stage_calls": list(stage_calls),
            }
        )
        expect("not_renderable_noop", noop_result is False, f"result={noop_result}")
        expect(
            "not_renderable_noop",
            "button_contract" not in noop_action,
            f"action={noop_action}",
        )
        expect(
            "not_renderable_noop",
            noop_action["candidate_search_evidence"] == {"keep": "yes"},
            f"evidence={noop_action['candidate_search_evidence']}",
        )
        expect(
            "not_renderable_noop",
            noop_debug == {"preexisting": True},
            f"guidance_debug={noop_debug}",
        )
        expect(
            "not_renderable_noop",
            inputs_page.st.session_state.get(session_key) == {"existing": "keep"},
            f"session={inputs_page.st.session_state.get(session_key)}",
        )
        expect("not_renderable_noop", render_calls == [], f"render_calls={render_calls}")
        expect("not_renderable_noop", stage_calls == [], f"stage_calls={stage_calls}")

        reset_case_session({"existing": "keep"})
        render_action = {
            "title_main": "Tighten shear",
            "candidate_search_evidence": {
                "keep": "yes",
                "exact_blockers_by_family": {"stale": True},
                "post_click_exact_blockers_by_family": {"stale": True},
                "cleanup_evidence_by_family": {"stale": True},
                "post_click_cleanup_evidence_by_family": {"stale": True},
            },
        }
        render_contract = {
            "enabled": True,
            "updates": {"s_lig": 150},
            "expected_util": 0.82,
        }
        render_debug = {"preexisting": True}
        render_result = (
            inputs_page.render_design_guide_post_cleanup_early_shear_refreshed_action_debug_render_return(
                early_shear_cleanup_contract_renderable=True,
                early_shear_cleanup_action=render_action,
                early_shear_cleanup_contract=render_contract,
                early_shear_cleanup_state={"D": 500},
                early_shear_cleanup_overview={"util": 0.75},
                guidance_debug=render_debug,
                inputs_render_audit={"audit": "render"},
                stage=stage,
            )
        )
        render_session = dict(inputs_page.st.session_state.get(session_key) or {})
        cases.append(
            {
                "name": "renderable_updates_existing_session_and_renders",
                "result": render_result,
                "action": dict(render_action),
                "guidance_debug": dict(render_debug),
                "session_debug": render_session,
                "render_calls": list(render_calls),
                "stage_calls": list(stage_calls),
            }
        )
        expect(
            "renderable_updates_existing_session_and_renders",
            render_result is True,
            f"result={render_result}",
        )
        expect(
            "renderable_updates_existing_session_and_renders",
            render_action.get("button_contract") == render_contract,
            f"button_contract={render_action.get('button_contract')}",
        )
        expect(
            "renderable_updates_existing_session_and_renders",
            render_action.get("candidate_search_evidence") == {"keep": "yes"},
            f"evidence={render_action.get('candidate_search_evidence')}",
        )
        expected_debug_fields = {
            "guidance_branch": "early_shear_overdesign_safe_cleanup_action",
            "selected_title": "Tighten shear",
            "selected_action_type": "apply_resolved_candidate",
            "selected_action_family": "shear",
            "primary_card_title": "Tighten shear",
            "primary_card_intent": "efficiency_tightening",
            "primary_guidance_intent": "efficiency_tightening",
            "primary_button_contract": render_contract,
            "button_contract": render_contract,
            "button_contract_enabled": True,
            "button_contract_updates": {"s_lig": 150},
            "candidate_search_evidence": {"keep": "yes"},
            "design_guide_terminal_state": None,
            "design_guide_terminal_positive": False,
            "design_guide_has_actionable_recommendation": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
        }
        for key, expected_value in expected_debug_fields.items():
            expect(
                "renderable_updates_existing_session_and_renders",
                render_debug.get(key) == expected_value,
                f"{key}={render_debug.get(key)}",
            )
            expect(
                "renderable_updates_existing_session_and_renders",
                render_session.get(key) == expected_value,
                f"session_{key}={render_session.get(key)}",
            )
        expect(
            "renderable_updates_existing_session_and_renders",
            render_session.get("existing") == "keep",
            f"session_existing={render_session.get('existing')}",
        )
        expect(
            "renderable_updates_existing_session_and_renders",
            len(render_calls) == 1,
            f"render_calls={render_calls}",
        )
        if render_calls:
            render_call = render_calls[0]
            expect(
                "renderable_updates_existing_session_and_renders",
                render_call["items"] == [render_action],
                f"items={render_call['items']}",
            )
            expect(
                "renderable_updates_existing_session_and_renders",
                render_call["guidance_disp_state"] == {"D": 500},
                f"state={render_call['guidance_disp_state']}",
            )
            expect(
                "renderable_updates_existing_session_and_renders",
                render_call["current_overview"] == {"util": 0.75},
                f"overview={render_call['current_overview']}",
            )
            expect(
                "renderable_updates_existing_session_and_renders",
                render_call["inputs_render_audit"] == {"audit": "render"},
                f"audit={render_call['inputs_render_audit']}",
            )
            expect(
                "renderable_updates_existing_session_and_renders",
                render_call["start_index"] == 0,
                f"start_index={render_call['start_index']}",
            )
            expect(
                "renderable_updates_existing_session_and_renders",
                render_call["primary_card_presentation"] == {},
                f"primary_card_presentation={render_call['primary_card_presentation']}",
            )
        expect(
            "renderable_updates_existing_session_and_renders",
            stage_calls == ["post_plan.after_early_shear_overdesign_action"],
            f"stage_calls={stage_calls}",
        )

        reset_case_session(None)
        new_session_action = {
            "title_main": "Create bundle",
            "candidate_search_evidence": {"keep": "new"},
        }
        new_session_debug = {"preexisting": "new"}
        new_session_result = (
            inputs_page.render_design_guide_post_cleanup_early_shear_refreshed_action_debug_render_return(
                early_shear_cleanup_contract_renderable=True,
                early_shear_cleanup_action=new_session_action,
                early_shear_cleanup_contract={"updates": {"D": 525}},
                early_shear_cleanup_state={"D": 525},
                early_shear_cleanup_overview={"util": 0.8},
                guidance_debug=new_session_debug,
                inputs_render_audit={},
                stage=stage,
            )
        )
        new_session_bundle = dict(inputs_page.st.session_state.get(session_key) or {})
        cases.append(
            {
                "name": "renderable_creates_session_bundle",
                "result": new_session_result,
                "action": dict(new_session_action),
                "guidance_debug": dict(new_session_debug),
                "session_debug": new_session_bundle,
                "render_calls": list(render_calls),
                "stage_calls": list(stage_calls),
            }
        )
        expect(
            "renderable_creates_session_bundle",
            new_session_result is True,
            f"result={new_session_result}",
        )
        expect(
            "renderable_creates_session_bundle",
            new_session_bundle == new_session_debug,
            f"session={new_session_bundle}",
        )
        expect(
            "renderable_creates_session_bundle",
            stage_calls == ["post_plan.after_early_shear_overdesign_action"],
            f"stage_calls={stage_calls}",
        )
    finally:
        inputs_page._render_guidance_secondary_items = original_render
        inputs_page.st.session_state.pop(session_key, None)
        if original_session_present:
            inputs_page.st.session_state[session_key] = original_session_value

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_refreshed_action_debug_render_return_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(
        json.dumps(payload_out, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post-Cleanup Early Shear Refreshed Action Debug Render Return",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload_out['status']}",
                "",
                "Scope:",
                "- Guards the extracted refreshed-action debug/session/render-return coordinator.",
                "- Verifies the non-renderable branch has no side effects.",
                "- Verifies stale blocker evidence pruning, debug bundle stamping, secondary render call shape, and stage marker on the consumed path.",
                "",
                "Cases:",
                *[f"- {case['name']}" for case in cases],
                "",
                "Failures:",
                *(f"- {failure}" for failure in failures),
                "" if failures else "- None",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(payload_out, indent=2, sort_keys=True, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
