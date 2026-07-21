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
        f"inputs_page_post_cleanup_terminal_residual_width_render_packaging_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_terminal_residual_width_render_packaging_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_render = inputs_page._render_guidance_secondary_items
    failures: list[str] = []
    events: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def render_secondary(items, *, guidance_disp_state, current_overview, inputs_render_audit, start_index, primary_card_presentation):
        events.append(
            {
                "event": "render_secondary",
                "items": [dict(item or {}) for item in items],
                "guidance_disp_state": dict(guidance_disp_state or {}),
                "current_overview": dict(current_overview or {}),
                "inputs_render_audit": dict(inputs_render_audit or {}),
                "start_index": start_index,
                "primary_card_presentation": dict(primary_card_presentation or {}),
            }
        )

    def stage(marker):
        events.append({"event": "stage", "marker": marker})

    try:
        inputs_page._render_guidance_secondary_items = render_secondary
        guidance_debug: dict = {}
        item = {
            "title": "Residual width cleanup",
            "action_type": "existing_action",
        }
        contract = {
            "enabled": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear_overdesign_governs",
        }
        updates = {"b": 250}
        result_item = inputs_page.render_design_guide_post_cleanup_terminal_residual_width_render_packaging(
            post_cleanup_residual_width_item=dict(item),
            post_cleanup_residual_width_contract=dict(contract),
            post_cleanup_residual_width_updates=dict(updates),
            guidance_debug=guidance_debug,
            guidance_disp_state={"b": 300},
            dg_overview={"worst_util": 0.4},
            inputs_render_audit={"audit": True},
            stage=stage,
        )
    finally:
        inputs_page._render_guidance_secondary_items = original_render

    render_events = [event for event in events if event["event"] == "render_secondary"]
    stage_events = [event for event in events if event["event"] == "stage"]
    expect(
        "item_packaging",
        result_item["local_cleanup_candidate"] is True
        and result_item["source"] == "post_cleanup_terminal_render_shear_overdesign_residual_width_cleanup"
        and result_item["button_contract"] == contract
        and result_item["action_type"] == "apply_resolved_candidate"
        and result_item["updates"] == updates
        and result_item["selected_action_updates"] == updates
        and result_item["selected_action_family"] == "shear_overdesign_governs"
        and result_item["selected_family_id"] == "SHEAR_OVERDESIGN_GOVERNS"
        and result_item["render_gate_condition"]
        == "post_cleanup_terminal_render_blocked_by_residual_width_cleanup",
        f"result_item={result_item}",
    )
    expect(
        "debug_packaging",
        guidance_debug["guidance_branch"] == "post_cleanup_terminal_render_residual_width_cleanup"
        and guidance_debug["selected_family_id"] == "SHEAR_OVERDESIGN_GOVERNS"
        and guidance_debug["primary_guidance_intent"] == "efficiency_tightening"
        and guidance_debug["post_cleanup_terminal_suppressed_by_residual_width_cleanup"] is True
        and guidance_debug["post_cleanup_terminal_residual_width_updates"] == updates
        and guidance_debug["post_click_accepted_green"] is False
        and guidance_debug["post_click_design_guide_state"] == "cleanup_action_available"
        and guidance_debug["button_contract"] == contract
        and guidance_debug["button_contract_enabled"] is True
        and guidance_debug["button_contract_updates"] == updates,
        f"guidance_debug={guidance_debug}",
    )
    expect(
        "render_and_stage",
        len(render_events) == 1
        and render_events[0]["items"] == [result_item]
        and render_events[0]["guidance_disp_state"] == {"b": 300}
        and render_events[0]["current_overview"] == {"worst_util": 0.4}
        and render_events[0]["inputs_render_audit"] == {"audit": True}
        and render_events[0]["start_index"] == 0
        and render_events[0]["primary_card_presentation"]["guidance_intent"] == "efficiency_tightening"
        and render_events[0]["primary_card_presentation"]["show_apply_button"] is True
        and stage_events == [
            {"event": "stage", "marker": "post_plan.after_render_residual_width_cleanup_item"}
        ],
        f"events={events}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "events": events,
        "result_item": result_item,
        "guidance_debug": guidance_debug,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Terminal Residual Width Render Packaging Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                f"JSON: `{json_path}`",
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
