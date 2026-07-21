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


class _FakeStreamlit:
    def __init__(self, session_state: dict[str, Any]) -> None:
        self.session_state = session_state


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_sidebar_debug_initial_context_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_sidebar_debug_initial_context_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "st": inputs_page.st,
        "_guidance_item_is_resolved_one_click": inputs_page._guidance_item_is_resolved_one_click,
        "_guidance_item_expected_util": inputs_page._guidance_item_expected_util,
        "_overview_debug_summary": inputs_page._overview_debug_summary,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_mode_config": inputs_page._design_mode_config,
        "_is_in_target_zone_with_eps": inputs_page._is_in_target_zone_with_eps,
        "_design_guide_display_truth_for_item": inputs_page._design_guide_display_truth_for_item,
        "_design_guide_status_from_overview": inputs_page._design_guide_status_from_overview,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        terminal_state: str | None,
        render_plan: dict[str, Any],
        expected_displayed_id: str | None,
        expected_post_apply_expected: float | None,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        session_state = {
            inputs_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY: {"expected_post_util": "0.91"},
            inputs_page.DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY: {"trial": True},
        }
        guidance_items = [
            {
                "id": "primary",
                "action_type": "apply",
                "title_main": "Primary",
                "status": "WARN",
                "util": 1.05,
                "action_payload": {"payload": True},
                "resolved_candidate": {"resolved": True},
                "candidate_search_evidence": {"evidence": "primary"},
                "button_contract": {"enabled": True, "family": "bending"},
                "expected": 0.93,
            },
            {"id": "secondary", "action_type": "info", "title_main": "Secondary"},
        ]
        guidance_debug = {"overview": {"worst_util": "0.90", "all_key_pass": True}}
        guidance_disp_state = {"goal": "unit_goal"}

        def _is_resolved(item):
            events.append({"event": "is_resolved", "id": dict(item or {}).get("id")})
            return dict(item or {}).get("id") == "primary"

        def _expected_util(item):
            events.append({"event": "expected_util", "id": dict(item or {}).get("id")})
            return dict(item or {}).get("expected")

        def _overview_summary(state, overview):
            events.append({"event": "overview_summary", "state": dict(state or {}), "overview": dict(overview or {})})
            return {"summary": True, "worst_util": overview.get("worst_util")}

        def _goal(state):
            events.append({"event": "goal", "state": dict(state or {})})
            return "goal-unit"

        def _mode_config(goal):
            events.append({"event": "mode_config", "goal": goal})
            return {"mode": goal}

        def _in_target(overview, mode_config, *, eps):
            events.append({"event": "in_target", "mode_config": dict(mode_config or {}), "eps": eps})
            return True

        def _status(overview):
            events.append({"event": "status", "overview": dict(overview or {})})
            return "PASS"

        def _display_truth(item, **kwargs):
            events.append(
                {
                    "event": "display_truth",
                    "source_override": kwargs.get("source_override"),
                    "post_commit_util": kwargs.get("post_commit_util"),
                    "post_commit_status": kwargs.get("post_commit_status"),
                }
            )
            return {"truth": True, "post_commit_util": kwargs.get("post_commit_util")}

        try:
            inputs_page.st = _FakeStreamlit(session_state)
            inputs_page._guidance_item_is_resolved_one_click = _is_resolved
            inputs_page._guidance_item_expected_util = _expected_util
            inputs_page._overview_debug_summary = _overview_summary
            inputs_page._design_optimisation_goal = _goal
            inputs_page._design_mode_config = _mode_config
            inputs_page._is_in_target_zone_with_eps = _in_target
            inputs_page._design_guide_status_from_overview = _status
            inputs_page._design_guide_display_truth_for_item = _display_truth
            result = inputs_page.render_design_guide_sidebar_debug_initial_context(
                guidance_items=[dict(item) for item in guidance_items],
                guidance_debug=dict(guidance_debug),
                guidance_disp_state=dict(guidance_disp_state),
                render_plan=dict(render_plan),
                terminal_state=terminal_state,
            )
        finally:
            _restore()

        (
            last_apply_route,
            gsum,
            ov,
            primary_item,
            primary_payload,
            primary_card_is_resolved_one_click,
            primary_card_expected_util_value,
            primary_card_expected_util_rendered,
            trial_geom,
            live_design_summary,
            post_apply_expected,
            post_apply_live_worst,
            mode_cfg_live,
            post_apply_live_in_target_band,
            post_apply_display_truth,
            post_apply_matches,
            displayed_primary_item,
            displayed_primary_payload,
            displayed_primary_resolved,
            displayed_primary_candidate_search_evidence,
            displayed_primary_button_contract,
        ) = result
        case = {
            "name": name,
            "events": events,
            "last_apply_route": last_apply_route,
            "gsum": gsum,
            "overview": ov,
            "primary_id": primary_item.get("id") if isinstance(primary_item, dict) else None,
            "primary_payload": primary_payload,
            "primary_card_is_resolved_one_click": primary_card_is_resolved_one_click,
            "primary_card_expected_util_value": primary_card_expected_util_value,
            "primary_card_expected_util_rendered": primary_card_expected_util_rendered,
            "trial_geom": trial_geom,
            "live_design_summary": live_design_summary,
            "post_apply_expected": post_apply_expected,
            "post_apply_live_worst": post_apply_live_worst,
            "mode_cfg_live": mode_cfg_live,
            "post_apply_live_in_target_band": post_apply_live_in_target_band,
            "post_apply_display_truth": post_apply_display_truth,
            "post_apply_matches": post_apply_matches,
            "displayed_primary_id": displayed_primary_item.get("id") if isinstance(displayed_primary_item, dict) else None,
            "displayed_primary_payload": displayed_primary_payload,
            "displayed_primary_resolved": displayed_primary_resolved,
            "displayed_primary_candidate_search_evidence": displayed_primary_candidate_search_evidence,
            "displayed_primary_button_contract": displayed_primary_button_contract,
        }
        cases.append(case)

        if case["displayed_primary_id"] != expected_displayed_id:
            failures.append(f"{name}_displayed_primary_mismatch:{case['displayed_primary_id']}")
        if case["post_apply_expected"] != expected_post_apply_expected:
            failures.append(f"{name}_post_apply_expected_mismatch:{case['post_apply_expected']}")
        if case["post_apply_live_worst"] != 0.90:
            failures.append(f"{name}_post_apply_live_worst_mismatch:{case['post_apply_live_worst']}")
        if case["post_apply_matches"] is not True:
            failures.append(f"{name}_post_apply_matches_mismatch:{case['post_apply_matches']}")
        if case["gsum"][0] != {"action_type": "apply", "title_main": "Primary", "status": "WARN", "util": 1.05}:
            failures.append(f"{name}_gsum_mismatch:{case['gsum']}")
        if case["primary_card_expected_util_rendered"] is not True:
            failures.append(f"{name}_primary_expected_rendered_mismatch:{case}")
        return case

    _run_case(
        "primary_only",
        terminal_state="blocked",
        render_plan={"render_primary_only": True, "visible_guidance_items": [{"id": "visible"}]},
        expected_displayed_id="primary",
        expected_post_apply_expected=0.91,
    )
    _run_case(
        "visible_items",
        terminal_state="blocked",
        render_plan={
            "render_primary_only": False,
            "visible_guidance_items": [
                {
                    "id": "visible",
                    "action_payload": {"visible_payload": True},
                    "resolved_candidate": {"visible_resolved": True},
                    "button_contract": {"enabled": False},
                }
            ],
        },
        expected_displayed_id="visible",
        expected_post_apply_expected=0.91,
    )
    terminal = _run_case(
        "terminal_no_displayed_primary",
        terminal_state="optimal",
        render_plan={"render_primary_only": True, "visible_guidance_items": [{"id": "visible"}]},
        expected_displayed_id=None,
        expected_post_apply_expected=0.91,
    )
    if terminal["displayed_primary_button_contract"] != {}:
        failures.append(f"terminal_contract_mismatch:{terminal['displayed_primary_button_contract']}")

    payload = {
        "verifier": "inputs_page_sidebar_debug_initial_context_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Sidebar Debug Initial Context Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` displayed_primary: `{case['displayed_primary_id']}`, post_apply_matches: `{case['post_apply_matches']}`"
                    for case in cases
                ),
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
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
