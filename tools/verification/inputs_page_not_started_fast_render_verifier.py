from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_not_started_fast_render_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_not_started_fast_render_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "info": inputs_page.st.info,
        "caption": inputs_page.st.caption,
    }
    session_keys = [
        inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY,
        "_design_guide_render_plan_debug",
    ]
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        inputs_page.st.info = originals["info"]
        inputs_page.st.caption = originals["caption"]
        for key in session_keys:
            try:
                inputs_page.st.session_state.pop(key, None)
            except Exception:
                pass

    def _run_case(
        name: str,
        *,
        guidance_items: list[dict],
        guidance_debug: dict[str, Any],
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def _info(value):
            events.append({"event": "info", "value": value})

        def _caption(value):
            events.append({"event": "caption", "value": value})

        try:
            inputs_page.st.info = _info
            inputs_page.st.caption = _caption
            handled, out_debug = inputs_page.render_design_guide_not_started_fast_render(
                guidance_items=[dict(item) for item in guidance_items],
                guidance_debug=dict(guidance_debug),
            )
            session_debug = dict(inputs_page.st.session_state.get(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {})
            render_plan_debug = dict(inputs_page.st.session_state.get("_design_guide_render_plan_debug") or {})
        finally:
            _restore()

        case = {
            "name": name,
            "handled": handled,
            "events": events,
            "debug": out_debug,
            "session_debug": session_debug,
            "render_plan_debug": render_plan_debug,
        }
        cases.append(case)
        return case

    noop = _run_case(
        "non_not_started_noop",
        guidance_items=[{"title_main": "Start"}],
        guidance_debug={"guidance_branch": "active"},
    )
    if noop["handled"] or noop["events"] or noop["session_debug"] or noop["render_plan_debug"]:
        failures.append(f"noop_mismatch:{noop}")
    if noop["debug"] != {"guidance_branch": "active"}:
        failures.append(f"noop_debug_mutated:{noop['debug']}")

    handled = _run_case(
        "not_started_with_item",
        guidance_items=[
            {
                "title_main": "Choose your workflow:",
                "line_main": "Pick a starting workflow.",
                "guidance_intent": "start",
            }
        ],
        guidance_debug={"guidance_branch": "not_started", "existing": True},
    )
    if handled["handled"] is not True:
        failures.append(f"handled_false:{handled}")
    if handled["events"] != [
        {"event": "info", "value": "Choose your workflow:"},
        {"event": "caption", "value": "Pick a starting workflow."},
    ]:
        failures.append(f"handled_events_mismatch:{handled['events']}")
    expected_debug = {
        "design_guide_render_primary_only": True,
        "design_guide_render_plan_reason": "not_started_fast_render",
        "design_guide_visible_guidance_item_count": 1,
        "design_guide_has_actionable_recommendation": False,
        "primary_card_title": "Choose your workflow:",
        "primary_card_intent": "start",
        "button_contract_enabled": False,
    }
    for key, expected in expected_debug.items():
        if handled["debug"].get(key) != expected:
            failures.append(f"handled_{key}_mismatch:{handled['debug'].get(key)}")
    if handled["session_debug"] != handled["debug"]:
        failures.append(f"handled_session_debug_mismatch:{handled['session_debug']}")
    if handled["render_plan_debug"] != {
        "render_primary_only": True,
        "reason": "not_started_fast_render",
        "input_count": 1,
        "visible_count": 1,
    }:
        failures.append(f"handled_render_plan_debug_mismatch:{handled['render_plan_debug']}")

    empty = _run_case(
        "not_started_empty_item_list",
        guidance_items=[],
        guidance_debug={"guidance_branch": "not_started"},
    )
    if empty["handled"] is not True:
        failures.append(f"empty_handled_false:{empty}")
    if empty["events"]:
        failures.append(f"empty_events_mismatch:{empty['events']}")
    if empty["debug"].get("design_guide_visible_guidance_item_count") != 0:
        failures.append(f"empty_visible_count_mismatch:{empty['debug']}")
    if empty["debug"].get("primary_card_title") is not None:
        failures.append(f"empty_title_mismatch:{empty['debug'].get('primary_card_title')}")
    if empty["debug"].get("primary_card_intent") != "start":
        failures.append(f"empty_intent_mismatch:{empty['debug'].get('primary_card_intent')}")
    if empty["render_plan_debug"].get("input_count") != 0 or empty["render_plan_debug"].get("visible_count") != 0:
        failures.append(f"empty_render_plan_mismatch:{empty['render_plan_debug']}")

    payload = {
        "verifier": "inputs_page_not_started_fast_render_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Not Started Fast Render Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(f"- `{case['name']}` handled: `{case['handled']}`, events: `{case['events']}`" for case in cases),
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


if __name__ == "__main__":
    raise SystemExit(main())
