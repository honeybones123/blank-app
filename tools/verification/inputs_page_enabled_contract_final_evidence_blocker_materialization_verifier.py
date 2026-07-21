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
        f"inputs_page_enabled_contract_final_evidence_blocker_materialization_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_enabled_contract_final_evidence_blocker_materialization_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_parse_util_value": inputs_page._parse_util_value,
        "_resolved_efficiency_target_band": inputs_page._resolved_efficiency_target_band,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_guide_family_summary_util": inputs_page._design_guide_family_summary_util,
        "_normalise_design_guide_candidate_id": inputs_page._normalise_design_guide_candidate_id,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    enabled_response = True

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(enabled_response)

    def parse_util(value):
        events.append({"event": "parse_util", "value": value})
        if value is None:
            return None
        return float(value)

    def target_band(config, *, goal):
        events.append({"event": "target_band", "config": config, "goal": goal})
        return 0.85, 0.95, "balanced"

    def mode_config(goal):
        events.append({"event": "mode_config", "goal": goal})
        return {"goal": goal}

    def optimisation_goal(state):
        events.append({"event": "optimisation_goal", "state": dict(state or {})})
        return "balanced"

    def family_summary_util(overview, family):
        events.append({"event": "family_summary_util", "family": family})
        return dict(overview or {}).get(family, 0.8)

    def normalise_candidate_id(*, family, updates):
        events.append(
            {
                "event": "normalise_candidate_id",
                "family": family,
                "updates": dict(updates or {}),
            }
        )
        return f"{family}-normalised"

    def run_case(
        name: str,
        *,
        item: dict,
        contract: dict,
        debug: dict | None = None,
        state: dict | None = None,
        overview: dict | None = None,
        enabled: bool = True,
    ) -> dict:
        nonlocal events, enabled_response
        events = []
        enabled_response = bool(enabled)
        guidance_debug = dict(debug or {})
        result_item = (
            inputs_page.render_design_guide_enabled_contract_final_evidence_blocker_materialization(
                final_visible_item=dict(item or {}),
                final_visible_contract=dict(contract or {}),
                guidance_debug=guidance_debug,
                guidance_disp_state=dict(state or {}),
                dg_overview=dict(overview or {}),
            )
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
        inputs_page._parse_util_value = parse_util
        inputs_page._resolved_efficiency_target_band = target_band
        inputs_page._design_mode_config = mode_config
        inputs_page._design_optimisation_goal = optimisation_goal
        inputs_page._design_guide_family_summary_util = family_summary_util
        inputs_page._normalise_design_guide_candidate_id = normalise_candidate_id

        bottom_key = sorted(inputs_page._COMPOUND_BOTTOM_UPDATE_KEYS)[0]

        case = run_case(
            "disabled_contract_noop",
            item={"title_main": "Original"},
            contract={"enabled": False, "family": "bending", "expected_util": 0.8},
            debug={"exact_blockers_by_family": {}},
            enabled=False,
        )
        expect(
            "disabled_contract_noop",
            case["item"] == {"title_main": "Original"}
            and case["debug"] == {"exact_blockers_by_family": {}}
            and [event["event"] for event in case["events"]] == ["contract_enabled"],
            f"case={case}",
        )

        case = run_case(
            "bending_below_accepted_materializes_exact_blocker",
            item={
                "candidate_search_evidence": {
                    "attempted_candidate_count": 4,
                    "safe_candidate_count": 2,
                },
                "action_payload": {},
                "resolved_candidate": {},
            },
            contract={
                "enabled": True,
                "family": "bending",
                "expected_util": 0.8,
                "updates": {"D": 600},
                "candidate_id": "bend-1",
            },
            debug={"exact_blockers_by_family": {}},
            overview={"bending": 0.7},
            enabled=True,
        )
        blocker = case["debug"]["exact_blockers_by_family"]["bending"]
        expect(
            "bending_below_accepted_materializes_exact_blocker",
            blocker["failed_check_status"] == "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD"
            and blocker["failed_check_name"] == "final accepted bending utilisation threshold"
            and blocker["best_safe_candidate_id"] == "bend-1"
            and blocker["attempted_candidate_count"] == 4
            and blocker["safe_candidate_count"] == 2
            and blocker["failed_check_util"] == 0.8
            and blocker["current_util"] == 0.7
            and case["item"]["exact_blockers_by_family"] == case["debug"]["exact_blockers_by_family"]
            and case["item"]["candidate_search_evidence"]["post_click_exact_blockers_by_family"]
            == case["debug"]["exact_blockers_by_family"]
            and case["item"]["action_payload"]["candidate_search_evidence"]["exact_blockers_by_family"]
            == case["debug"]["exact_blockers_by_family"]
            and case["item"]["resolved_candidate"]["candidate_search_evidence"]["cleanup_evidence_by_family"]
            == case["debug"]["exact_blockers_by_family"],
            f"case={case}",
        )

        case = run_case(
            "existing_exact_blocker_is_not_overwritten",
            item={"candidate_search_evidence": {"existing": True}},
            contract={
                "enabled": True,
                "family": "bending",
                "expected_util": 0.8,
                "updates": {"D": 600},
            },
            debug={"exact_blockers_by_family": {"bending": {"keep": True}}},
            enabled=True,
        )
        expect(
            "existing_exact_blocker_is_not_overwritten",
            case["debug"]["exact_blockers_by_family"] == {"bending": {"keep": True}}
            and "exact_blockers_by_family" not in case["item"],
            f"case={case}",
        )

        case = run_case(
            "combined_contract_selects_preview_family_outside_preferred_band",
            item={
                "family_status_preview": {
                    "bending": {"before_util": 0.9, "after_util": 0.94},
                    "shear": {"before_util": 0.8, "after_util": 0.97},
                },
                "candidate_search_evidence": {"candidate_count": 3},
            },
            contract={
                "enabled": True,
                "family": "combined",
                "expected_util": 0.9,
                "updates": {"s_lig": 160, bottom_key: 3},
                "source_candidate_id": "combo-1",
            },
            debug={"exact_blockers_by_family": {}},
            overview={"shear": 0.8, "bending": 0.9},
            enabled=True,
        )
        blocker = case["debug"]["exact_blockers_by_family"]["shear"]
        expect(
            "combined_contract_selects_preview_family_outside_preferred_band",
            blocker["family"] == "shear"
            and blocker["failed_check_status"] == "outside_preferred_target_band"
            and blocker["failed_check_name"] == "preferred shear target band"
            and blocker["best_safe_final_util"] == 0.97
            and blocker["failed_check_capacity_or_limit"] == 0.95
            and case["item"]["post_click_exact_blockers_by_family"] == {
                "shear": blocker
            },
            f"case={case}",
        )
    finally:
        inputs_page._design_guide_button_contract_enabled = originals[
            "_design_guide_button_contract_enabled"
        ]
        inputs_page._parse_util_value = originals["_parse_util_value"]
        inputs_page._resolved_efficiency_target_band = originals[
            "_resolved_efficiency_target_band"
        ]
        inputs_page._design_mode_config = originals["_design_mode_config"]
        inputs_page._design_optimisation_goal = originals["_design_optimisation_goal"]
        inputs_page._design_guide_family_summary_util = originals[
            "_design_guide_family_summary_util"
        ]
        inputs_page._normalise_design_guide_candidate_id = originals[
            "_normalise_design_guide_candidate_id"
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
                "# Inputs Page Enabled Contract Final Evidence Blocker Materialization Verifier",
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
        print("ENABLED_CONTRACT_FINAL_EVIDENCE_BLOCKER_MATERIALIZATION_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("ENABLED_CONTRACT_FINAL_EVIDENCE_BLOCKER_MATERIALIZATION_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
