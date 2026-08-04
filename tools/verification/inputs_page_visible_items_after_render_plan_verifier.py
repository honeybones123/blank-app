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
    json_path = ARTIFACT_DIR / f"inputs_page_visible_items_after_render_plan_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_visible_items_after_render_plan_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_trace = inputs_page._inputs_pre_widget_trace
    original_enabled = inputs_page._design_guide_button_contract_enabled
    original_render = inputs_page._render_guidance_secondary_items

    def trace(event_name, **kwargs):
        calls.append({"event": "trace", "event_name": event_name, "kwargs": dict(kwargs)})

    def enabled(contract):
        contract = dict(contract or {})
        calls.append({"event": "contract_enabled", "contract": contract})
        return bool(contract.get("enabled"))

    def render_items(items, **kwargs):
        calls.append({"event": "render_items", "items": list(items or []), "kwargs": dict(kwargs)})

    stage_events: list[str] = []

    def stage(name: str) -> None:
        stage_events.append(name)
        calls.append({"event": "stage", "name": name})

    try:
        inputs_page._inputs_pre_widget_trace = trace
        inputs_page._design_guide_button_contract_enabled = enabled
        inputs_page._render_guidance_secondary_items = render_items

        rendered_items = inputs_page.render_design_guide_visible_items_after_render_plan(
            render_plan={
                "visible_guidance_items": [
                    {"title": "old first"},
                    {"label": "second", "selected_family_id": "shear"},
                ],
                "reason": "visible_reason",
            },
            guidance_items=[
                {
                    "title_main": "new first",
                    "family": "bending",
                    "guidance_intent": "specific_blocker",
                    "action_type": "apply_resolved_candidate",
                    "bucket": "primary",
                    "button_contract": {"enabled": True, "family": "bending"},
                }
            ],
            guidance_disp_state={"state": "visible"},
            dg_overview={"overview": True},
            inputs_render_audit={"audit": True},
            dg_presentation={"headline": "presentation"},
            stage_fn=stage,
        )
    finally:
        inputs_page._inputs_pre_widget_trace = original_trace
        inputs_page._design_guide_button_contract_enabled = original_enabled
        inputs_page._render_guidance_secondary_items = original_render

    expected_first = {
        "title_main": "new first",
        "family": "bending",
        "guidance_intent": "specific_blocker",
        "action_type": "apply_resolved_candidate",
        "bucket": "primary",
        "button_contract": {"enabled": True, "family": "bending"},
    }
    expected_rendered = [
        expected_first,
        {"label": "second", "selected_family_id": "shear"},
    ]
    trace_call = next((call for call in calls if call["event"] == "trace"), {})
    render_call = next((call for call in calls if call["event"] == "render_items"), {})

    expect(
        "visible_item_replacement",
        rendered_items == expected_rendered,
        f"rendered_items={rendered_items}",
    )
    expect(
        "trace_payload",
        trace_call
        == {
            "event": "trace",
            "event_name": "_render_fast_design_guidance_panel.render_visible_items_payload",
            "kwargs": {
                "item_count": 2,
                "first_title": "new first",
                "first_family": "bending",
                "first_guidance_intent": "specific_blocker",
                "first_action_type": "apply_resolved_candidate",
                "first_bucket": "primary",
                "first_button_contract_enabled": True,
                "render_plan_reason": "visible_reason",
                "has_primary_card_presentation": True,
            },
        },
        f"trace_call={trace_call}",
    )
    expect(
        "stage_and_render_order",
        [call["event"] for call in calls]
        == ["contract_enabled", "trace", "stage", "render_items", "stage"]
        and stage_events
        == [
            "post_plan.before_render_visible_items",
            "post_plan.after_render_visible_items",
        ]
        and render_call.get("items") == expected_rendered
        and render_call.get("kwargs")
        == {
            "guidance_disp_state": {"state": "visible"},
            "current_overview": {"overview": True},
            "inputs_render_audit": {"audit": True},
            "start_index": 0,
            "primary_card_presentation": {"headline": "presentation"},
        },
        f"calls={calls} stage_events={stage_events}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "calls": calls,
        "stage_events": stage_events,
        "rendered_items": rendered_items,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Visible Items After Render Plan Verifier",
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
