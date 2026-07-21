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
        f"inputs_page_combined_visible_safe_cleanup_restamp_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_combined_visible_safe_cleanup_restamp_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_parse_util_value": inputs_page._parse_util_value,
        "_evaluate_auto_design_candidate": inputs_page._evaluate_auto_design_candidate,
        "_overview_active_failure_keys": inputs_page._overview_active_failure_keys,
        "_disabled_design_guide_button_contract": inputs_page._disabled_design_guide_button_contract,
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

    def evaluate_candidate(state, *, updates, source, label, action_type):
        events.append(
            {
                "event": "evaluate_candidate",
                "state": dict(state or {}),
                "updates": dict(updates or {}),
                "source": source,
                "label": label,
                "action_type": action_type,
            }
        )
        return {"overview": {"utils": {"bending": 0.91}, "worst_util": 0.92}}

    def active_failure_keys(overview):
        events.append({"event": "active_failure_keys", "overview": dict(overview or {})})
        statuses = dict(dict(overview or {}).get("statuses") or {})
        return {key for key, status in statuses.items() if status == "FAIL"}

    def disabled_contract(item, *, family, reason):
        events.append(
            {
                "event": "disabled_contract",
                "title": dict(item or {}).get("title_main"),
                "family": family,
                "reason": reason,
            }
        )
        return {
            "enabled": False,
            "family": family,
            "blocking_reason": reason,
            "updates": {},
        }

    def run_case(
        name: str,
        *,
        item: dict,
        resolution: dict,
        debug: dict | None = None,
    ) -> dict:
        nonlocal events
        events = []
        guidance_debug = dict(debug or {})
        result_item, result_resolution = (
            inputs_page.render_design_guide_combined_visible_safe_cleanup_restamp(
                final_visible_item=dict(item or {}),
                final_visible_resolution=dict(resolution or {}),
                guidance_debug=guidance_debug,
                current_state={"D": 500},
            )
        )
        case = {
            "name": name,
            "item": result_item,
            "resolution": result_resolution,
            "debug": guidance_debug,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._parse_util_value = parse_util
        inputs_page._evaluate_auto_design_candidate = evaluate_candidate
        inputs_page._overview_active_failure_keys = active_failure_keys
        inputs_page._disabled_design_guide_button_contract = disabled_contract

        shear_key = sorted(inputs_page._COMPOUND_SHEAR_UPDATE_KEYS)[0]
        bottom_key = sorted(inputs_page._COMPOUND_BOTTOM_UPDATE_KEYS)[0]
        updates = {shear_key: 180, bottom_key: 3}

        case = run_case(
            "non_combined_cleanup_noop",
            item={"title_main": "Original"},
            resolution={"render_reason": "before"},
            debug={"seed": True},
        )
        expect(
            "non_combined_cleanup_noop",
            case["item"] == {"title_main": "Original"}
            and case["resolution"] == {"render_reason": "before"}
            and case["debug"] == {"seed": True}
            and case["events"] == [],
            f"case={case}",
        )

        case = run_case(
            "combined_cleanup_contract_restamped",
            item={
                "title_main": "Old title",
                "button_contract": {"updates": dict(updates)},
                "family_status_current": {
                    "bending": {"status": "PASS"},
                    "shear": {"status": "PASS"},
                },
                "candidate_search_evidence": {
                    "selected_candidate_title": "Combined cleanup",
                    "selected_candidate_id": "combo-1",
                    "selected_candidate_util": 0.9,
                },
            },
            resolution={"render_reason": "final_visible_combined_low_util_safe_cleanup"},
        )
        expect(
            "combined_cleanup_contract_restamped",
            case["item"]["title_main"] == "Combined cleanup"
            and case["item"]["family"] == "combined"
            and case["item"]["button_contract"]["enabled"] is True
            and case["item"]["button_contract"]["updates"] == updates
            and case["item"]["action_payload"]["resolved_candidate_updates"] == updates
            and case["item"]["resolved_candidate"]["updates"] == updates
            and case["resolution"]["presentation"]["show_apply_button"] is True
            and case["resolution"]["presentation"]["css_bucket"] == "efficiency"
            and case["debug"]["final_visible_combined_cleanup_contract_restamped"] is True
            and "evaluate_candidate" in [event["event"] for event in case["events"]],
            f"case={case}",
        )

        case = run_case(
            "combined_cleanup_exact_stop",
            item={
                "title_main": "Old title",
                "button_contract": {"updates": dict(updates)},
                "candidate_search_evidence": {
                    "selected_candidate_id": "combo-2",
                    "selected_candidate_util": 0.8,
                },
            },
            resolution={"render_reason": "final_visible_combined_low_util_safe_cleanup"},
        )
        expect(
            "combined_cleanup_exact_stop",
            case["item"]["title_main"] == "Design is efficient - no further safe cleanup available"
            and case["item"]["family"] == "general"
            and case["item"]["button_contract"]["enabled"] is False
            and case["item"]["updates"] == {}
            and case["resolution"]["render_reason"] == "final_visible_combined_low_util_exact_stop"
            and case["resolution"]["presentation"]["show_apply_button"] is False
            and case["resolution"]["presentation"]["use_success_style"] is True
            and case["debug"]["final_visible_combined_cleanup_exact_stop"] is True
            and "disabled_contract" in [event["event"] for event in case["events"]],
            f"case={case}",
        )
    finally:
        inputs_page._parse_util_value = originals["_parse_util_value"]
        inputs_page._evaluate_auto_design_candidate = originals["_evaluate_auto_design_candidate"]
        inputs_page._overview_active_failure_keys = originals["_overview_active_failure_keys"]
        inputs_page._disabled_design_guide_button_contract = originals[
            "_disabled_design_guide_button_contract"
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
                "# Inputs Page Combined Visible Safe Cleanup Restamp Verifier",
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
        print("COMBINED_VISIBLE_SAFE_CLEANUP_RESTAMP_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("COMBINED_VISIBLE_SAFE_CLEANUP_RESTAMP_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
