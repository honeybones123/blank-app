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
        f"inputs_page_post_active_repair_green_acceptance_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_active_repair_green_acceptance_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_overview_active_failure_keys": inputs_page._overview_active_failure_keys,
        "_post_active_repair_target_accepted_item": inputs_page._post_active_repair_target_accepted_item,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_recommendation_result_for_primary_guidance_card": (
            inputs_page._recommendation_result_for_primary_guidance_card
        ),
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    active_failure_keys_response: set[str] = set()
    accepted_item_response: object = None

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def active_failure_keys(overview):
        events.append({"event": "active_failure_keys", "overview": dict(overview or {})})
        return set(active_failure_keys_response)

    def design_goal(state):
        events.append({"event": "design_goal", "state": dict(state or {})})
        return "target"

    def design_config(goal):
        events.append({"event": "design_config", "goal": goal})
        return {"goal": goal}

    def accepted_item(state, overview, config, audit, *, debug_sink, allow_required_checks_terminal):
        events.append(
            {
                "event": "accepted_item",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "config": dict(config or {}),
                "audit": dict(audit or {}),
                "allow_required_checks_terminal": bool(allow_required_checks_terminal),
            }
        )
        debug_sink["accepted_item_called"] = True
        return dict(accepted_item_response) if isinstance(accepted_item_response, dict) else accepted_item_response

    def recommendation(items, state, *, branch, request_kind):
        events.append(
            {
                "event": "recommendation",
                "items": [dict(item or {}) for item in items],
                "state": dict(state or {}),
                "branch": branch,
                "request_kind": request_kind,
            }
        )
        return {"branch": branch, "request_kind": request_kind, "item_count": len(items)}

    def run_case(
        name: str,
        *,
        post_active: bool = True,
        audit: dict | None = None,
        terminal_render: bool = True,
        invalid_render: bool = True,
        low_families: list | None = None,
        overview: dict | None = None,
        presentation: dict | None = None,
        debug: dict | None = None,
        state: dict | None = None,
        items: list | None = None,
        render_plan: dict | None = None,
        terminal_state="terminal",
        terminal_source="source",
        active_failures: set[str] | None = None,
        accepted_response: object = None,
    ) -> dict:
        nonlocal events, active_failure_keys_response, accepted_item_response
        events = []
        active_failure_keys_response = set(active_failures or set())
        accepted_item_response = accepted_response
        guidance_debug = dict(debug or {})
        result = inputs_page.render_design_guide_post_active_repair_green_acceptance(
            post_active_failure_repair_render=post_active,
            post_cleanup_render_audit=dict(audit or {}),
            post_cleanup_terminal_render=terminal_render,
            post_cleanup_low_families=list(low_families or []),
            dg_overview=dict(overview or {}),
            dg_presentation=dict(presentation or {}),
            guidance_debug=guidance_debug,
            guidance_disp_state=dict(state or {}),
            guidance_items=list(items or []),
            render_plan=dict(render_plan or {}),
            terminal_state=terminal_state,
            terminal_state_source=terminal_source,
        )
        (
            result_terminal_render,
            result_invalid_render,
            result_audit,
            result_low_families,
            result_items,
            result_plan,
            result_presentation,
            result_terminal_state,
            result_terminal_source,
        ) = result
        case = {
            "name": name,
            "post_cleanup_terminal_render": result_terminal_render,
            "post_cleanup_invalid_render": result_invalid_render,
            "post_cleanup_render_audit": result_audit,
            "post_cleanup_low_families": result_low_families,
            "guidance_items": result_items,
            "render_plan": result_plan,
            "presentation": result_presentation,
            "terminal_state": result_terminal_state,
            "terminal_state_source": result_terminal_source,
            "debug": guidance_debug,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._overview_active_failure_keys = active_failure_keys
        inputs_page._post_active_repair_target_accepted_item = accepted_item
        inputs_page._design_mode_config = design_config
        inputs_page._design_optimisation_goal = design_goal
        inputs_page._recommendation_result_for_primary_guidance_card = recommendation

        case = run_case(
            "active_failure_overview_resets_post_cleanup_render",
            audit={"post_click_accepted_green_valid": True},
            low_families=["bending"],
            overview={"any_fail": True},
            items=[{"title_main": "before"}],
            render_plan={"reason": "before"},
            active_failures={"bending"},
            accepted_response={"title_main": "should not publish"},
        )
        expect(
            "active_failure_overview_resets_post_cleanup_render",
            case["post_cleanup_terminal_render"] is False
            and case["post_cleanup_invalid_render"] is False
            and case["post_cleanup_render_audit"] == {}
            and case["post_cleanup_low_families"] == []
            and [event["event"] for event in case["events"]] == ["active_failure_keys"],
            f"case={case}",
        )

        accepted = {
            "title_main": "Design accepted - best safe result",
            "primary_action": "No apply needed.",
            "button_contract": {"enabled": False},
        }
        case = run_case(
            "post_active_repair_green_acceptance_publishes",
            audit={"post_click_accepted_green_valid": True},
            debug={"overview": {"any_fail": False}},
            state={"b": 300},
            items=[{"title_main": "before"}],
            render_plan={"reason": "before"},
            terminal_state="old_terminal",
            terminal_source="old_source",
            accepted_response=accepted,
        )
        event_names = [event["event"] for event in case["events"]]
        expect(
            "post_active_repair_green_acceptance_publishes",
            case["guidance_items"] == [accepted]
            and case["terminal_state"] is None
            and case["terminal_state_source"] == "active_fail_repaired_target_accepted"
            and case["presentation"]["headline"] == accepted["title_main"]
            and case["presentation"]["show_apply_button"] is False
            and case["render_plan"]["reason"] == "post_active_repair_best_safe_green"
            and case["debug"]["post_active_repair_green_acceptance_published"] is True
            and case["debug"]["recommendation_result"]["branch"]
            == "post_active_repair_target_accepted_with_secondary_blocker"
            and event_names == [
                "active_failure_keys",
                "design_goal",
                "design_config",
                "accepted_item",
                "recommendation",
            ],
            f"case={case}",
        )

        case = run_case(
            "accepted_item_non_dict_noops",
            audit={"post_click_accepted_green_valid": True},
            debug={"overview": {"any_fail": False}},
            items=[{"title_main": "before"}],
            render_plan={"reason": "before"},
            terminal_state="old_terminal",
            terminal_source="old_source",
            accepted_response=None,
        )
        expect(
            "accepted_item_non_dict_noops",
            case["guidance_items"] == [{"title_main": "before"}]
            and case["render_plan"] == {"reason": "before"}
            and case["terminal_state"] == "old_terminal"
            and case["terminal_state_source"] == "old_source"
            and case["debug"].get("post_active_repair_green_acceptance_published") is None,
            f"case={case}",
        )

        case = run_case(
            "accepted_green_audit_gate_blocks_publish",
            audit={"post_click_accepted_green_valid": False},
            debug={"overview": {"any_fail": False}},
            items=[{"title_main": "before"}],
            render_plan={"reason": "before"},
            accepted_response=accepted,
        )
        expect(
            "accepted_green_audit_gate_blocks_publish",
            case["guidance_items"] == [{"title_main": "before"}]
            and case["render_plan"] == {"reason": "before"}
            and [event["event"] for event in case["events"]] == ["active_failure_keys"],
            f"case={case}",
        )
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "cases": cases,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Active Repair Green Acceptance Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Cases",
                "",
                *[f"- `{case['name']}`" for case in cases],
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verdict": payload["verdict"],
                "json": str(json_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
