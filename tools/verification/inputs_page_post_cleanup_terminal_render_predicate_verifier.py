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
        f"inputs_page_post_cleanup_terminal_render_predicate_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_terminal_render_predicate_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_mode_config": inputs_page._design_mode_config,
        "_local_cleanup_post_apply_acceptance_matches": inputs_page._local_cleanup_post_apply_acceptance_matches,
        "_shear_reinforcement_is_active": inputs_page._shear_reinforcement_is_active,
        "_is_in_target_zone_with_eps": inputs_page._is_in_target_zone_with_eps,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    local_acceptance = False
    shear_active = True
    in_target = False

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def optimisation_goal(state):
        events.append({"event": "goal", "state": dict(state or {})})
        return "goal-x"

    def mode_config(goal):
        events.append({"event": "mode_config", "goal": goal})
        return {"target_util_min": 0.85, "target_util_max": 1.0}

    def acceptance_matches(state):
        events.append({"event": "acceptance", "state": dict(state or {})})
        return bool(local_acceptance)

    def shear_reinforcement_active(state):
        events.append({"event": "shear_active", "state": dict(state or {})})
        return bool(shear_active)

    def is_in_target_zone(overview, mode_config, *, eps):
        events.append(
            {
                "event": "in_target",
                "overview": dict(overview or {}),
                "mode_config": dict(mode_config or {}),
                "eps": eps,
            }
        )
        return bool(in_target)

    def run_case(
        name: str,
        *,
        guidance_debug: dict,
        audit: dict,
        terminal_unresolved: list,
        acceptance: bool,
        shear_is_active: bool,
        target_zone: bool,
        expected: bool,
        expected_events: list[str],
    ) -> None:
        nonlocal events, local_acceptance, shear_active, in_target
        events = []
        local_acceptance = acceptance
        shear_active = shear_is_active
        in_target = target_zone
        result = inputs_page.render_design_guide_post_cleanup_terminal_render_predicate(
            guidance_disp_state={"D": 500, "s_lig": 200},
            guidance_debug=dict(guidance_debug),
            post_cleanup_render_audit=dict(audit),
            terminal_green_unresolved_for_render=list(terminal_unresolved),
        )
        cases.append(
            {
                "name": name,
                "result": result,
                "expected": expected,
                "events": list(events),
            }
        )
        expect(name, result is expected, f"result={result}")
        expect(
            name,
            [event["event"] for event in events] == expected_events,
            f"events={events}",
        )

    try:
        inputs_page._design_optimisation_goal = optimisation_goal
        inputs_page._design_mode_config = mode_config
        inputs_page._local_cleanup_post_apply_acceptance_matches = acceptance_matches
        inputs_page._shear_reinforcement_is_active = shear_reinforcement_active
        inputs_page._is_in_target_zone_with_eps = is_in_target_zone

        run_case(
            "local_acceptance_and_target_zone_allows_terminal",
            guidance_debug={"overview": {"any_fail": False, "worst_util": 0.9}},
            audit={"post_click_accepted_green_valid": True},
            terminal_unresolved=[],
            acceptance=True,
            shear_is_active=True,
            target_zone=True,
            expected=True,
            expected_events=["acceptance", "goal", "mode_config", "in_target"],
        )
        run_case(
            "inactive_shear_rebar_and_valid_audit_allows_terminal_with_worst_util_fallback",
            guidance_debug={"overview": {"any_fail": False, "worst_util": 0.86}},
            audit={"post_click_accepted_green_valid": True},
            terminal_unresolved=[],
            acceptance=False,
            shear_is_active=False,
            target_zone=False,
            expected=True,
            expected_events=[
                "acceptance",
                "shear_active",
                "goal",
                "mode_config",
                "in_target",
                "goal",
                "mode_config",
                "goal",
                "mode_config",
            ],
        )
        run_case(
            "any_fail_blocks_terminal",
            guidance_debug={"overview": {"any_fail": True, "worst_util": 0.9}},
            audit={"post_click_accepted_green_valid": True},
            terminal_unresolved=[],
            acceptance=True,
            shear_is_active=True,
            target_zone=True,
            expected=False,
            expected_events=["acceptance"],
        )
        run_case(
            "invalid_accepted_green_audit_blocks_terminal",
            guidance_debug={"overview": {"any_fail": False, "worst_util": 0.9}},
            audit={"post_click_accepted_green_valid": False},
            terminal_unresolved=[],
            acceptance=True,
            shear_is_active=True,
            target_zone=True,
            expected=False,
            expected_events=["acceptance", "goal", "mode_config", "in_target"],
        )
        run_case(
            "audit_low_families_block_terminal",
            guidance_debug={"overview": {"any_fail": False, "worst_util": 0.9}},
            audit={
                "post_click_accepted_green_valid": True,
                "post_click_unresolved_low_util_families": ["shear"],
            },
            terminal_unresolved=[],
            acceptance=True,
            shear_is_active=True,
            target_zone=True,
            expected=False,
            expected_events=["acceptance", "goal", "mode_config", "in_target"],
        )
        run_case(
            "terminal_guard_unresolved_blocks_terminal",
            guidance_debug={"overview": {"any_fail": False, "worst_util": 0.9}},
            audit={"post_click_accepted_green_valid": True},
            terminal_unresolved=["bending"],
            acceptance=True,
            shear_is_active=True,
            target_zone=True,
            expected=False,
            expected_events=["acceptance", "goal", "mode_config", "in_target"],
        )
        run_case(
            "below_worst_util_and_not_target_blocks_terminal",
            guidance_debug={"overview": {"any_fail": False, "worst_util": 0.83}},
            audit={"post_click_accepted_green_valid": True},
            terminal_unresolved=[],
            acceptance=True,
            shear_is_active=True,
            target_zone=False,
            expected=False,
            expected_events=[
                "acceptance",
                "goal",
                "mode_config",
                "in_target",
                "goal",
                "mode_config",
            ],
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    payload_out = {
        "verifier": "inputs_page_post_cleanup_terminal_render_predicate_verifier",
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
                "# Inputs Page Post-Cleanup Terminal Render Predicate",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload_out['status']}",
                "",
                "Scope:",
                "- Guards the extracted post-cleanup terminal render predicate coordinator.",
                "- Verifies acceptance route, inactive-shear-rebar route, worst-util fallback, and blocking gates.",
                "- Confirms no audit, session, Apply, CTA, or rendering behavior is owned by this helper.",
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
