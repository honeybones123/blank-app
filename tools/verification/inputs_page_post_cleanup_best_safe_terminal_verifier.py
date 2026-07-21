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
        f"inputs_page_post_cleanup_best_safe_terminal_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_best_safe_terminal_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_parse_util_value": inputs_page._parse_util_value,
        "_overview_active_failure_keys": inputs_page._overview_active_failure_keys,
        "_local_cleanup_post_apply_acceptance_matches": inputs_page._local_cleanup_post_apply_acceptance_matches,
        "_combined_low_util_exact_blocker_final_item": inputs_page._combined_low_util_exact_blocker_final_item,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    contract_enabled_response = True
    active_failure_keys_response: set[str] = set()
    acceptance_matches_response = True
    combined_item_response: dict | None = None

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(contract_enabled_response)

    def parse_util(value):
        events.append({"event": "parse_util", "value": value})
        if value is None:
            return None
        return float(value)

    def active_failure_keys(overview):
        events.append({"event": "active_failure_keys", "overview": dict(overview or {})})
        return set(active_failure_keys_response)

    def acceptance_matches(state):
        events.append({"event": "acceptance_matches", "state": dict(state or {})})
        return bool(acceptance_matches_response)

    def combined_item(state, overview, audit, *, post_click):
        events.append(
            {
                "event": "combined_item",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "audit": dict(audit or {}),
                "post_click": bool(post_click),
            }
        )
        return dict(combined_item_response or {}) if combined_item_response is not None else None

    def run_case(
        name: str,
        *,
        final_resolution: dict | None = None,
        final_item: dict | None = None,
        audit: dict | None = None,
        overview: dict | None = None,
        presentation: dict | None = None,
        debug: dict | None = None,
        state: dict | None = None,
        guidance_items: list | None = None,
        render_plan: dict | None = None,
        terminal_state="terminal",
        terminal_state_source="source",
        contract_enabled: bool = True,
        active_failures: set[str] | None = None,
        acceptance_matches_value: bool = True,
        combined: dict | None = None,
    ) -> dict:
        nonlocal events, contract_enabled_response, active_failure_keys_response
        nonlocal acceptance_matches_response, combined_item_response
        events = []
        contract_enabled_response = bool(contract_enabled)
        active_failure_keys_response = set(active_failures or set())
        acceptance_matches_response = bool(acceptance_matches_value)
        combined_item_response = dict(combined) if combined is not None else None
        guidance_debug = dict(debug or {})
        result = inputs_page.render_design_guide_post_cleanup_best_safe_terminal(
            final_visible_resolution=dict(final_resolution or {}),
            final_visible_item=dict(final_item or {}),
            post_cleanup_render_audit=dict(audit or {}),
            dg_overview=dict(overview or {}),
            dg_presentation=dict(presentation or {}),
            guidance_debug=guidance_debug,
            guidance_disp_state=dict(state or {}),
            guidance_items=list(guidance_items or []),
            render_plan=dict(render_plan or {}),
            terminal_state=terminal_state,
            terminal_state_source=terminal_state_source,
        )
        (
            cleanup_before_blocker,
            result_items,
            result_plan,
            result_presentation,
            result_terminal_state,
            result_terminal_source,
        ) = result
        case = {
            "name": name,
            "cleanup_before_blocker": cleanup_before_blocker,
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
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._parse_util_value = parse_util
        inputs_page._overview_active_failure_keys = active_failure_keys
        inputs_page._local_cleanup_post_apply_acceptance_matches = acceptance_matches
        inputs_page._combined_low_util_exact_blocker_final_item = combined_item

        case = run_case(
            "cleanup_action_before_blocker_flag",
            final_resolution={"render_reason": "final_visible_bending_cleanup_available_before_blocker"},
            final_item={"button_contract": {"enabled": True}},
            contract_enabled=True,
        )
        expect(
            "cleanup_action_before_blocker_flag",
            case["cleanup_before_blocker"] is True
            and [event["event"] for event in case["events"]] == [
                "contract_enabled",
                "active_failure_keys",
            ],
            f"case={case}",
        )

        accepted_blocker = {
            "best_safe_final_util": 0.9,
            "accepted_band_candidate_count": 1,
            "executable_candidate_count": 1,
        }
        case = run_case(
            "deferred_accepted_action_suppresses_terminal_publication",
            audit={
                "post_click_accepted_green_valid": True,
                "post_click_families_below_final_threshold": ["bending", "shear"],
                "post_click_exact_blockers_by_family": {
                    "bending": dict(accepted_blocker),
                    "shear": {"best_safe_final_util": 0.7},
                },
            },
            overview={},
            presentation={"headline": "before"},
            guidance_items=[{"title_main": "before"}],
            render_plan={"reason": "before"},
            combined={"title_main": "Should not publish"},
        )
        event_names = [event["event"] for event in case["events"]]
        expect(
            "deferred_accepted_action_suppresses_terminal_publication",
            case["guidance_items"] == [{"title_main": "before"}]
            and case["render_plan"] == {"reason": "before"}
            and case["presentation"] == {"headline": "before"}
            and "combined_item" not in event_names,
            f"case={case}",
        )

        combined = {
            "title_main": "Design accepted - best safe result",
            "primary_action": "No further safe cleanup.",
            "button_contract": {"enabled": False},
            "display_truth": {"accepted": True},
            "candidate_search_evidence": {"source": "combined"},
            "exact_blockers_by_family": {"bending": {"reason": "blocked"}},
            "post_click_exact_blockers_by_family": {"shear": {"reason": "blocked"}},
            "cleanup_evidence_by_family": {"bending": {"reason": "blocked"}},
            "post_click_cleanup_evidence_by_family": {"shear": {"reason": "blocked"}},
        }
        case = run_case(
            "combined_best_safe_terminal_publishes",
            audit={
                "post_click_accepted_green_valid": True,
                "post_click_unresolved_low_util_families": [],
                "post_click_families_below_final_threshold": ["bending", "shear"],
                "post_click_exact_blockers_by_family": {
                    "bending": {"best_safe_final_util": 0.7},
                    "shear": {"best_safe_final_util": 0.75},
                },
                "audit_seed": True,
            },
            overview={"any_fail": False},
            presentation={"old": True},
            debug={"overview": {"from_debug": True}},
            state={"D": 500},
            guidance_items=[{"title_main": "before"}],
            render_plan={"reason": "before"},
            terminal_state="old-terminal",
            terminal_state_source="old-source",
            combined=combined,
        )
        expect(
            "combined_best_safe_terminal_publishes",
            case["guidance_items"] == [combined]
            and case["render_plan"]["reason"] == "post_click_combined_low_util_best_safe_final"
            and case["presentation"]["headline"] == "Design accepted - best safe result"
            and case["presentation"]["show_apply_button"] is False
            and case["terminal_state"] is None
            and case["terminal_state_source"] == "post_click_combined_low_util_best_safe_final"
            and case["debug"]["guidance_branch"] == "post_click_combined_low_util_best_safe_final"
            and case["debug"]["selected_action_type"] is None
            and case["debug"]["selected_action_family"] == "combined"
            and case["debug"]["primary_button_contract"] == {"enabled": False}
            and case["debug"]["button_contract_updates"] == {}
            and case["debug"]["candidate_search_evidence"] == {"source": "combined"}
            and case["debug"]["active_fail_repaired_green_with_secondary_blocker"] is True
            and case["debug"]["render_plan_debug"]["visible_count"] == 1,
            f"case={case}",
        )

        case = run_case(
            "active_failures_suppress_terminal_publication",
            audit={
                "post_click_accepted_green_valid": True,
                "post_click_unresolved_low_util_families": [],
                "post_click_families_below_final_threshold": ["bending", "shear"],
                "post_click_exact_blockers_by_family": {
                    "bending": {"best_safe_final_util": 0.7},
                    "shear": {"best_safe_final_util": 0.75},
                },
            },
            active_failures={"bending"},
            guidance_items=[{"title_main": "before"}],
            render_plan={"reason": "before"},
            combined=combined,
        )
        expect(
            "active_failures_suppress_terminal_publication",
            case["guidance_items"] == [{"title_main": "before"}]
            and "guidance_branch" not in case["debug"],
            f"case={case}",
        )
    finally:
        inputs_page._design_guide_button_contract_enabled = originals[
            "_design_guide_button_contract_enabled"
        ]
        inputs_page._parse_util_value = originals["_parse_util_value"]
        inputs_page._overview_active_failure_keys = originals["_overview_active_failure_keys"]
        inputs_page._local_cleanup_post_apply_acceptance_matches = originals[
            "_local_cleanup_post_apply_acceptance_matches"
        ]
        inputs_page._combined_low_util_exact_blocker_final_item = originals[
            "_combined_low_util_exact_blocker_final_item"
        ]

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Best Safe Terminal Verifier",
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
        print("POST_CLEANUP_BEST_SAFE_TERMINAL_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("POST_CLEANUP_BEST_SAFE_TERMINAL_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
