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
        f"inputs_page_final_visible_render_plan_presentation_sync_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_final_visible_render_plan_presentation_sync_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_parse_util_value": inputs_page._parse_util_value,
        "_overview_active_failure_keys": inputs_page._overview_active_failure_keys,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def parse_util(value):
        events.append({"event": "parse_util", "value": value})
        if value is None:
            return None
        return float(value)

    def active_failure_keys(overview):
        events.append({"event": "active_failure_keys", "overview": dict(overview or {})})
        statuses = dict(dict(overview or {}).get("statuses") or {})
        return {key for key, status in statuses.items() if status == "FAIL"}

    def run_case(
        name: str,
        *,
        item: dict,
        resolution: dict,
        dg_overview: dict,
        dg_presentation: dict | None = None,
        render_plan: dict | None = None,
        terminal_state="terminal",
        terminal_state_source="source",
    ) -> dict:
        nonlocal events
        events = []
        guidance_debug: dict = {}
        result = inputs_page.render_design_guide_final_visible_render_plan_presentation_sync(
            final_visible_item=dict(item or {}),
            final_visible_resolution=dict(resolution or {}),
            dg_overview=dict(dg_overview or {}),
            dg_presentation=dict(dg_presentation or {}) if dg_presentation is not None else None,
            render_plan=dict(render_plan or {}) if render_plan is not None else None,
            guidance_debug=guidance_debug,
            terminal_state=terminal_state,
            terminal_state_source=terminal_state_source,
        )
        (
            result_item,
            result_resolution,
            result_overview,
            result_presentation,
            guidance_items,
            result_render_plan,
            result_terminal_state,
            result_terminal_state_source,
        ) = result
        case = {
            "name": name,
            "item": result_item,
            "resolution": result_resolution,
            "overview": result_overview,
            "presentation": result_presentation,
            "guidance_items": guidance_items,
            "render_plan": result_render_plan,
            "terminal_state": result_terminal_state,
            "terminal_state_source": result_terminal_state_source,
            "debug": guidance_debug,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._parse_util_value = parse_util
        inputs_page._overview_active_failure_keys = active_failure_keys

        case = run_case(
            "basic_render_plan_and_debug",
            item={
                "title_main": "Primary",
                "family": "bending",
                "guidance_intent": "required_fix",
                "button_contract": {"enabled": True},
            },
            resolution={
                "render_reason": "reason-a",
                "state_fingerprint": "fp-a",
                "presentation": {"headline": "Primary", "show_apply_button": True},
                "debug": {"resolver": True},
            },
            dg_overview={"statuses": {"bending": "PASS"}},
            dg_presentation={"theme": "old"},
            render_plan={"existing": True},
        )
        expect(
            "basic_render_plan_and_debug",
            case["resolution"]["item"]["title_main"] == "Primary"
            and case["guidance_items"] == [case["item"]]
            and case["render_plan"]["render_primary_only"] is True
            and case["render_plan"]["visible_count"] == 1
            and case["render_plan"]["reason"] == "reason-a"
            and case["presentation"]["headline"] == "Primary"
            and case["presentation"]["theme"] == "old"
            and case["debug"]["final_visible_design_guide_resolver"]["state_fingerprint"] == "fp-a"
            and case["debug"]["primary_card_title"] == "Primary"
            and case["debug"]["primary_guidance_intent"] == "required_fix"
            and case["terminal_state"] == "terminal",
            f"case={case}",
        )

        case = run_case(
            "same_click_cleanup_merge_presentation",
            item={
                "title": "Merged cleanup",
                "same_click_cleanup_merge": True,
                "guidance_intent": "",
                "button_contract": {"expected_util": 0.93},
            },
            resolution={"render_reason": "reason-b"},
            dg_overview={"statuses": {"bending": "PASS", "shear": "PASS"}},
            dg_presentation={"headline": "before"},
        )
        expect(
            "same_click_cleanup_merge_presentation",
            case["presentation"]["headline"] == "Merged cleanup"
            and case["presentation"]["subtext"] == "governing utilisation moves to 0.93"
            and case["presentation"]["guidance_intent"] == "efficiency_tightening"
            and case["presentation"]["css_bucket"] == "efficiency"
            and case["presentation"]["show_apply_button"] is True
            and "parse_util" in [event["event"] for event in case["events"]],
            f"case={case}",
        )

        case = run_case(
            "active_failure_clears_terminal_state",
            item={"title_main": "Failure item", "check_key": "shear"},
            resolution={"render_reason": "active-failure"},
            dg_overview={"statuses": {"shear": "FAIL"}},
            terminal_state="old-terminal",
            terminal_state_source="old-source",
        )
        expect(
            "active_failure_clears_terminal_state",
            case["terminal_state"] is None
            and case["terminal_state_source"] == "active-failure"
            and "active_failure_keys" in [event["event"] for event in case["events"]],
            f"case={case}",
        )
    finally:
        inputs_page._parse_util_value = originals["_parse_util_value"]
        inputs_page._overview_active_failure_keys = originals["_overview_active_failure_keys"]

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Visible Render Plan Presentation Sync Verifier",
                "",
                f"Status: {payload['status']}",
                "",
                "## Cases",
                "",
                *[
                    f"- {case['name']}: {len(case['events'])} events"
                    for case in cases
                ],
                "",
                "## Artifacts",
                "",
                f"- JSON: `{json_path.relative_to(ROOT)}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if failures:
        print("FINAL_VISIBLE_RENDER_PLAN_PRESENTATION_SYNC_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("FINAL_VISIBLE_RENDER_PLAN_PRESENTATION_SYNC_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
