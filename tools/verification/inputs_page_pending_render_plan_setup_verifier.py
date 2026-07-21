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
    json_path = ARTIFACT_DIR / f"inputs_page_pending_render_plan_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pending_render_plan_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    if not hasattr(inputs_page, "_sync_pending_recommendation_from_guidance"):
        current_source = (ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        panel_source = (ROOT / "inputs_page_modules" / "design_guide" / "panel_coordinators.py").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        failures = []
        for token in (
            "def render_design_guide_render_plan_current_coordinator(",
            "_sync_pending_recommendation_from_guidance(",
            "_design_guide_render_plan(",
            "\"pending_recommendation\": pending_recommendation",
            "\"render_plan\": dict(render_plan or {})",
        ):
            if token not in current_source:
                failures.append(f"current_missing:{token}")
        for token in (
            "current_owner.render_design_guide_render_plan_current_coordinator(",
            "pending_recommendation = _render_plan_result[\"pending_recommendation\"]",
            "render_plan = dict(_render_plan_result[\"render_plan\"] or {})",
        ):
            if token not in panel_source:
                failures.append(f"panel_missing:{token}")
        payload = {
            "verifier": "inputs_page_pending_render_plan_setup_verifier",
            "status": "PASS" if not failures else "FAIL",
            "mode": "permanent_shell_current_coordinator",
            "failures": failures,
            "retired_inputs_page_symbol_probe": True,
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        report_path.write_text(
            "\n".join(
                [
                    "# Inputs Page Pending Recommendation Render Plan Setup Verifier",
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

    originals: dict[str, Any] = {
        "_sync_pending_recommendation_from_guidance": inputs_page._sync_pending_recommendation_from_guidance,
        "_design_guide_render_plan": inputs_page._design_guide_render_plan,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for original_name, original_value in originals.items():
            setattr(inputs_page, original_name, original_value)

    events: list[dict[str, Any]] = []
    guidance_items = [{"id": "primary"}]
    state = {"D": 500}
    collapse_meta = {"collapsed": True}
    recommendation_result = {"winner_id": "winner"}

    def _sync(items, state_arg, *, terminal_state):
        events.append(
            {
                "event": "sync",
                "items": list(items),
                "state": dict(state_arg),
                "terminal_state": terminal_state,
            }
        )
        return {"pending": terminal_state or "action"}

    def _plan(items, recommendation_arg, collapse_arg):
        events.append(
            {
                "event": "plan",
                "items": list(items),
                "recommendation": dict(recommendation_arg or {}),
                "collapse": dict(collapse_arg or {}),
            }
        )
        return {
            "render_primary_only": False,
            "visible_guidance_items": list(items),
            "visible_count": len(items),
            "reason": "unit",
            "input_count": len(items),
        }

    try:
        inputs_page._sync_pending_recommendation_from_guidance = _sync
        inputs_page._design_guide_render_plan = _plan

        pending = inputs_page.render_design_guide_pending_recommendation(
            guidance_items=guidance_items,
            guidance_disp_state=state,
            terminal_state="optimal",
        )
        render_plan = inputs_page.render_design_guide_render_plan_setup(
            guidance_items=guidance_items,
            recommendation_result=recommendation_result,
            collapse_meta=collapse_meta,
        )
    finally:
        _restore()

    cases.append(
        {
            "name": "pending_and_render_plan_passthrough",
            "events": events,
            "pending": pending,
            "render_plan": render_plan,
        }
    )

    if [event["event"] for event in events] != ["sync", "plan"]:
        failures.append(f"events_mismatch:{events}")
    sync_event = events[0] if events else {}
    if sync_event.get("terminal_state") != "optimal":
        failures.append(f"sync_terminal_mismatch:{sync_event}")
    if sync_event.get("items") != guidance_items or sync_event.get("state") != state:
        failures.append(f"sync_payload_mismatch:{sync_event}")
    if pending != {"pending": "optimal"}:
        failures.append(f"pending_mismatch:{pending}")
    plan_event = events[1] if len(events) > 1 else {}
    if plan_event.get("recommendation") != recommendation_result or plan_event.get("collapse") != collapse_meta:
        failures.append(f"plan_payload_mismatch:{plan_event}")
    if render_plan.get("visible_guidance_items") != guidance_items or render_plan.get("visible_count") != 1:
        failures.append(f"render_plan_mismatch:{render_plan}")

    payload = {
        "verifier": "inputs_page_pending_render_plan_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pending Recommendation Render Plan Setup Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(f"- `{case['name']}` events: `{[event['event'] for event in case['events']]}`" for case in cases),
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
