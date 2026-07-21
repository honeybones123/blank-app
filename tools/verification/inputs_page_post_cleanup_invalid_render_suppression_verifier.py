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
        f"inputs_page_post_cleanup_invalid_render_suppression_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_suppression_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_contract_enabled = inputs_page._design_guide_button_contract_enabled
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    contract_enabled_response = True

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(contract_enabled_response)

    def run_case(
        name: str,
        *,
        audit: dict | None = None,
        low_families: list | None = None,
        post_active: bool = False,
        cleanup_before_blocker: bool = False,
        final_resolution: dict | None = None,
        final_item: dict | None = None,
        debug: dict | None = None,
        terminal_state: object = "optimal",
        terminal_source: object = "source",
        contract_enabled_value: bool = True,
    ) -> dict:
        nonlocal events, contract_enabled_response
        events = []
        contract_enabled_response = bool(contract_enabled_value)
        guidance_debug = dict(debug or {})
        result = inputs_page.render_design_guide_post_cleanup_invalid_render_suppression(
            post_cleanup_render_audit=dict(audit or {}),
            post_cleanup_low_families=list(low_families or []),
            post_active_failure_repair_render=bool(post_active),
            final_visible_cleanup_action_before_blocker=bool(cleanup_before_blocker),
            final_visible_resolution=dict(final_resolution or {}),
            final_visible_item=dict(final_item or {}),
            guidance_debug=guidance_debug,
            terminal_state=terminal_state,
            terminal_state_source=terminal_source,
        )
        invalid_render, result_terminal_state, result_terminal_source = result
        case = {
            "name": name,
            "invalid_render": invalid_render,
            "terminal_state": result_terminal_state,
            "terminal_state_source": result_terminal_source,
            "debug": guidance_debug,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._design_guide_button_contract_enabled = contract_enabled

        case = run_case(
            "invalid_audit_suppresses_terminal_state",
            audit={"post_click_accepted_green_valid": False},
            debug={"overview": {"any_fail": False}},
            terminal_state="optimal",
            terminal_source="terminal_source",
        )
        expect(
            "invalid_audit_suppresses_terminal_state",
            case["invalid_render"] is True
            and case["terminal_state"] is None
            and case["terminal_state_source"] == "post_cleanup_acceptance_invalid"
            and case["debug"]["design_guide_terminal_state_suppressed_value"] == "optimal",
            f"case={case}",
        )

        case = run_case(
            "valid_green_without_low_families_not_invalid",
            audit={"post_click_accepted_green_valid": True},
            debug={"overview": {"any_fail": False}},
            terminal_state="optimal",
        )
        expect(
            "valid_green_without_low_families_not_invalid",
            case["invalid_render"] is False
            and case["terminal_state"] == "optimal"
            and case["debug"].get("design_guide_terminal_state_suppressed_reason") is None,
            f"case={case}",
        )

        case = run_case(
            "low_families_make_valid_green_invalid_without_terminal_suppression",
            audit={"post_click_accepted_green_valid": True},
            low_families=["shear"],
            debug={"overview": {"any_fail": False}},
            terminal_state="manual_review",
        )
        expect(
            "low_families_make_valid_green_invalid_without_terminal_suppression",
            case["invalid_render"] is True
            and case["terminal_state"] == "manual_review"
            and case["terminal_state_source"] == "source",
            f"case={case}",
        )

        case = run_case(
            "final_visible_combined_cleanup_enabled_contract_exempts_invalid",
            audit={"post_click_accepted_green_valid": False},
            debug={"overview": {"any_fail": False}},
            final_resolution={"render_reason": "final_visible_combined_low_util_safe_cleanup"},
            final_item={"button_contract": {"enabled": True}},
            terminal_state="very_low_demand",
            contract_enabled_value=True,
        )
        expect(
            "final_visible_combined_cleanup_enabled_contract_exempts_invalid",
            case["invalid_render"] is False
            and case["terminal_state"] == "very_low_demand"
            and [event["event"] for event in case["events"]] == ["contract_enabled"],
            f"case={case}",
        )
    finally:
        inputs_page._design_guide_button_contract_enabled = original_contract_enabled

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "cases": cases,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Suppression Verifier",
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
