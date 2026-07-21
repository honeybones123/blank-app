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
    json_path = ARTIFACT_DIR / (
        f"inputs_page_post_cleanup_terminal_accepted_green_fallback_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_terminal_accepted_green_fallback_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_render = inputs_page._render_guidance_secondary_items
    original_st = inputs_page.st
    failures: list[str] = []
    events: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def render_secondary(
        items,
        *,
        guidance_disp_state,
        current_overview,
        inputs_render_audit,
        start_index,
        primary_card_presentation,
    ):
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

    debug_bundle: dict = {}
    fake_st = SimpleNamespace(
        session_state={inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY: debug_bundle}
    )
    guidance_debug = {"overview": {"worst_util": 0.87, "governing_util": 0.91}}
    post_cleanup_render_audit = {
        "post_click_accepted_green_valid": True,
        "post_cleanup_render_reason": "accepted_after_cleanup",
    }
    try:
        inputs_page._render_guidance_secondary_items = render_secondary
        inputs_page.st = fake_st
        result_item = inputs_page.render_design_guide_post_cleanup_terminal_accepted_green_fallback(
            guidance_debug=guidance_debug,
            guidance_disp_state={"b": 300},
            dg_overview={"worst_util": 0.87},
            inputs_render_audit={"audit": True},
            post_cleanup_render_audit=post_cleanup_render_audit,
            stage=stage,
        )
    finally:
        inputs_page._render_guidance_secondary_items = original_render
        inputs_page.st = original_st

    render_events = [event for event in events if event["event"] == "render_secondary"]
    stage_events = [event for event in events if event["event"] == "stage"]
    expect(
        "debug_bundle",
        debug_bundle["primary_card_title"] == "Design accepted - target band achieved"
        and debug_bundle["primary_card_intent"] == "already_efficient"
        and debug_bundle["primary_guidance_intent"] == "already_efficient"
        and debug_bundle["primary_button_contract"] == {}
        and debug_bundle["button_contract"] == {}
        and debug_bundle["button_contract_enabled"] is False
        and debug_bundle["button_contract_updates"] == {}
        and debug_bundle["safe_local_cleanup_count"] == 0
        and debug_bundle["executable_safe_cleanup_count"] == 0
        and debug_bundle["post_click_accepted_green"] is True
        and debug_bundle["post_click_accepted_green_valid"] is True
        and debug_bundle["post_click_design_guide_state"] == "accepted_green"
        and debug_bundle["terminal_state_reason"] == "post_apply_cleanup_state_accepted"
        and debug_bundle["post_cleanup_render_reason"] == "accepted_after_cleanup",
        f"debug_bundle={debug_bundle}",
    )
    expect(
        "accepted_item",
        result_item["title_main"] == "Design accepted - target band achieved"
        and result_item["status"] == "PASS"
        and result_item["util"] == 0.87
        and result_item["guidance_intent"] == "already_efficient"
        and result_item["design_guide_terminal_state"] == "optimal",
        f"result_item={result_item}",
    )
    expect(
        "render_and_stage",
        len(render_events) == 1
        and render_events[0]["items"] == [result_item]
        and render_events[0]["guidance_disp_state"] == {"b": 300}
        and render_events[0]["current_overview"] == {"worst_util": 0.87}
        and render_events[0]["inputs_render_audit"] == {"audit": True}
        and render_events[0]["start_index"] == 0
        and render_events[0]["primary_card_presentation"] == {}
        and stage_events == [
            {"event": "stage", "marker": "post_plan.after_render_accepted_item"}
        ],
        f"events={events}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "events": events,
        "result_item": result_item,
        "debug_bundle": debug_bundle,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Terminal Accepted Green Fallback Verifier",
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
