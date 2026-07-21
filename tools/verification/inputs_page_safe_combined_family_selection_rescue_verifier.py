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
        f"inputs_page_safe_combined_family_selection_rescue_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_safe_combined_family_selection_rescue_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_parse_util_value": inputs_page._parse_util_value,
        "_float_from_state": inputs_page._float_from_state,
        "_design_guide_button_contract": inputs_page._design_guide_button_contract,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    contract_response: dict = {}
    contract_enabled_response = True

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def parse_util(value):
        events.append({"event": "parse_util", "value": value})
        if value is None:
            return None
        return float(value)

    def float_from_state(state, key, default=None):
        events.append({"event": "float_from_state", "key": key})
        return dict(state or {}).get(key, default)

    def button_contract(item, *, state):
        events.append({"event": "button_contract", "item": dict(item or {}), "state": dict(state or {})})
        return dict(contract_response or {})

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(contract_enabled_response)

    def run_case(
        name: str,
        *,
        item: dict,
        resolution: dict,
        debug: dict,
        family_debug: dict,
        family_applied: bool,
        disp_state: dict,
        contract: dict,
        enabled: bool,
    ) -> dict:
        nonlocal events, contract_response, contract_enabled_response
        events = []
        contract_response = dict(contract or {})
        contract_enabled_response = bool(enabled)
        guidance_debug = dict(debug or {})
        result_resolution = dict(resolution or {})
        result_item, result_resolution = (
            inputs_page.render_design_guide_safe_combined_family_selection_rescue(
                final_visible_item=dict(item or {}),
                final_visible_resolution=result_resolution,
                guidance_debug=guidance_debug,
                current_state={"D": 500},
                guidance_disp_state=dict(disp_state or {}),
                family_selection_debug=dict(family_debug or {}),
                family_selection_item_applied=bool(family_applied),
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
        inputs_page._float_from_state = float_from_state
        inputs_page._design_guide_button_contract = button_contract
        inputs_page._design_guide_button_contract_enabled = contract_enabled

        shear_key = sorted(inputs_page._COMPOUND_SHEAR_UPDATE_KEYS)[0]
        bottom_key = sorted(inputs_page._COMPOUND_BOTTOM_UPDATE_KEYS)[0]

        case = run_case(
            "no_family_failure_noop",
            item={"title_main": "Original"},
            resolution={"render_reason": "before"},
            debug={"seed": True},
            family_debug={"family_match_passed": True},
            family_applied=True,
            disp_state={"uls_Vstar": 50.0},
            contract={"enabled": True},
            enabled=True,
        )
        expect(
            "no_family_failure_noop",
            case["item"] == {"title_main": "Original"}
            and case["resolution"] == {"render_reason": "before"}
            and case["debug"] == {"seed": True}
            and case["events"] == [],
            f"case={case}",
        )

        proof = {
            "safe_cleanup_candidate_found": True,
            "updates": {shear_key: 180, bottom_key: 3},
            "candidate_id": "combo-1",
            "expected_util": 0.9,
            "candidate_reaches_target_band": True,
            "executor_backed": True,
            "preview_pass": True,
            "label": "Combined cleanup",
        }
        case = run_case(
            "successful_safe_combined_rescue",
            item={"title_main": "Boundary item", "candidate_search_evidence": {"existing": True}},
            resolution={"render_reason": "family_selection_contract_boundary"},
            debug={"design_brain_safe_combined_cleanup_proof": proof},
            family_debug={"family_match_passed": False},
            family_applied=True,
            disp_state={"uls_Vstar": 40.0, "load_Vstar_proxy": 0.0},
            contract={"enabled": True, "updates": {shear_key: 180, bottom_key: 3}},
            enabled=True,
        )
        evidence = dict(case["item"].get("candidate_search_evidence") or {})
        expect(
            "successful_safe_combined_rescue",
            case["item"]["title_main"] == "Combined cleanup"
            and case["item"]["family"] == "combined"
            and case["item"]["button_contract"] == {"enabled": True, "updates": {shear_key: 180, bottom_key: 3}}
            and case["item"]["expected_util"] == 0.9
            and case["resolution"]["render_reason"] == "final_visible_combined_low_util_safe_cleanup"
            and case["resolution"]["item"]["title_main"] == "Combined cleanup"
            and case["debug"]["family_selection_combined_cleanup_rescue"] is True
            and case["debug"]["family_match_passed"] is True
            and evidence["selected_candidate_id"] == "combo-1"
            and evidence["selected_candidate_updates"] == {shear_key: 180, bottom_key: 3}
            and "button_contract" in [event["event"] for event in case["events"]]
            and "contract_enabled" in [event["event"] for event in case["events"]],
            f"case={case}",
        )

        low_proof = dict(proof)
        low_proof["expected_util"] = 0.1
        case = run_case(
            "invalid_rescue_sets_boundary_presentation",
            item={"title_main": "Boundary item", "summary_line": "Need family match"},
            resolution={"presentation": {"existing": True}},
            debug={"design_brain_safe_combined_cleanup_proof": low_proof},
            family_debug={"family_match_passed": False},
            family_applied=True,
            disp_state={"uls_Vstar": 40.0},
            contract={"enabled": True},
            enabled=True,
        )
        expect(
            "invalid_rescue_sets_boundary_presentation",
            case["item"]["title_main"] == "Boundary item"
            and case["resolution"]["render_reason"] == "family_selection_contract_boundary"
            and case["resolution"]["presentation"]["headline"] == "Boundary item"
            and case["resolution"]["presentation"]["subtext"] == "Need family match"
            and case["resolution"]["presentation"]["show_apply_button"] is False
            and case["debug"].get("family_selection_combined_cleanup_rescue") is None,
            f"case={case}",
        )
    finally:
        inputs_page._parse_util_value = originals["_parse_util_value"]
        inputs_page._float_from_state = originals["_float_from_state"]
        inputs_page._design_guide_button_contract = originals["_design_guide_button_contract"]
        inputs_page._design_guide_button_contract_enabled = originals[
            "_design_guide_button_contract_enabled"
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
                "# Inputs Page Safe Combined Family Selection Rescue Verifier",
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
        print("SAFE_COMBINED_FAMILY_SELECTION_RESCUE_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("SAFE_COMBINED_FAMILY_SELECTION_RESCUE_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
