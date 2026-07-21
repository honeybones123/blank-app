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
        f"inputs_page_primary_button_debug_exact_completion_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_primary_button_debug_exact_completion_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_complete_exact_blocker_map_from_attempts": inputs_page._complete_exact_blocker_map_from_attempts,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    enabled_response = False
    completed_exact_response: dict = {}

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(enabled_response)

    def complete_exact(existing, attempts):
        events.append(
            {
                "event": "complete_exact",
                "existing": dict(existing or {}),
                "attempts": dict(attempts or {}),
            }
        )
        return dict(completed_exact_response or {})

    def run_case(
        name: str,
        *,
        item: dict,
        contract: dict,
        debug: dict | None = None,
        enabled: bool = False,
        completed_exact: dict | None = None,
    ) -> dict:
        nonlocal events, enabled_response, completed_exact_response
        events = []
        enabled_response = bool(enabled)
        completed_exact_response = dict(completed_exact or {})
        guidance_debug = dict(debug or {})
        result_item = inputs_page.render_design_guide_primary_button_debug_and_exact_completion(
            final_visible_item=dict(item or {}),
            final_visible_contract=dict(contract or {}),
            guidance_debug=guidance_debug,
        )
        case = {
            "name": name,
            "item": result_item,
            "debug": guidance_debug,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._complete_exact_blocker_map_from_attempts = complete_exact

        case = run_case(
            "debug_stamps_without_exact_completion",
            item={
                "family_status_current": {"bending": {"status": "PASS"}},
                "family_status_preview": {"bending": {"after_util": 0.9}},
                "blocker_attempts_by_family": {"bending": {"attempted": True}},
            },
            contract={"enabled": True, "family": "bending", "updates": {"D": 600}},
            enabled=True,
        )
        expect(
            "debug_stamps_without_exact_completion",
            case["debug"]["primary_button_contract"] == {
                "enabled": True,
                "family": "bending",
                "updates": {"D": 600},
            }
            and case["debug"]["button_contract_enabled"] is True
            and case["debug"]["button_contract_updates"] == {"D": 600}
            and case["debug"]["family_status_current"] == {"bending": {"status": "PASS"}}
            and case["debug"]["family_status_preview"] == {"bending": {"after_util": 0.9}}
            and case["debug"]["blocker_attempts_by_family"] == {"bending": {"attempted": True}}
            and case["debug"]["exact_blockers_by_family"] == {}
            and [event["event"] for event in case["events"]] == [
                "contract_enabled",
                "complete_exact",
            ],
            f"case={case}",
        )

        completed_exact = {
            "shear": {
                "family": "shear",
                "reason": "no executable cleanup",
            }
        }
        case = run_case(
            "completed_exact_propagates_to_item_evidence_and_debug",
            item={
                "exact_blockers_by_family": {"bending": {"family": "bending"}},
                "post_click_exact_blockers_by_family": {"shear": {"stale": True}},
                "blocker_attempts_by_family": {"shear": {"attempted": True}},
                "candidate_search_evidence": {"existing": True},
            },
            contract={"enabled": False, "updates": {}},
            enabled=False,
            completed_exact=completed_exact,
        )
        expect(
            "completed_exact_propagates_to_item_evidence_and_debug",
            case["item"]["exact_blockers_by_family"] == completed_exact
            and case["item"]["post_click_exact_blockers_by_family"] == completed_exact
            and case["item"]["candidate_search_evidence"]["existing"] is True
            and case["item"]["candidate_search_evidence"]["exact_blockers_by_family"] == completed_exact
            and case["item"]["candidate_search_evidence"]["post_click_exact_blockers_by_family"] == completed_exact
            and case["debug"]["exact_blockers_by_family"] == completed_exact
            and case["debug"]["post_click_exact_blockers_by_family"] == completed_exact
            and case["events"][1]["existing"] == {
                "bending": {"family": "bending"},
                "shear": {"stale": True},
            },
            f"case={case}",
        )

        case = run_case(
            "post_click_exact_falls_back_to_exact",
            item={
                "exact_blockers_by_family": {"bending": {"family": "bending"}},
            },
            contract={},
            enabled=False,
        )
        expect(
            "post_click_exact_falls_back_to_exact",
            case["debug"]["exact_blockers_by_family"] == {"bending": {"family": "bending"}}
            and case["debug"]["post_click_exact_blockers_by_family"] == {
                "bending": {"family": "bending"}
            },
            f"case={case}",
        )
    finally:
        inputs_page._design_guide_button_contract_enabled = originals[
            "_design_guide_button_contract_enabled"
        ]
        inputs_page._complete_exact_blocker_map_from_attempts = originals[
            "_complete_exact_blocker_map_from_attempts"
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
                "# Inputs Page Primary Button Debug Exact Completion Verifier",
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
        print("PRIMARY_BUTTON_DEBUG_EXACT_COMPLETION_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("PRIMARY_BUTTON_DEBUG_EXACT_COMPLETION_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
