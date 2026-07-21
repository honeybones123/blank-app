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
        f"inputs_page_visible_publication_contract_boundaries_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_visible_publication_contract_boundaries_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_normalise_visible_optimisation_contract": (
            inputs_page._normalise_visible_optimisation_contract
        ),
        "enforce_underdesign_repair_publication_boundary": (
            inputs_page.enforce_underdesign_repair_publication_boundary
        ),
        "enforce_family_selection_publication_contract": (
            inputs_page.enforce_family_selection_publication_contract
        ),
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    normalised_item = None
    underdesign_response = None
    family_response = None

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def normalise(item, *, state, overview, debug_sink):
        events.append(
            {
                "event": "normalise",
                "item": dict(item or {}),
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "debug": dict(debug_sink or {}),
            }
        )
        return dict(normalised_item) if isinstance(normalised_item, dict) else normalised_item

    def underdesign(payload):
        events.append({"event": "underdesign", "payload": dict(payload or {})})
        return dict(underdesign_response) if isinstance(underdesign_response, dict) else underdesign_response

    def family(payload):
        events.append({"event": "family", "payload": dict(payload or {})})
        return dict(family_response) if isinstance(family_response, dict) else family_response

    def run_case(
        name: str,
        *,
        item: dict,
        resolution: dict,
        debug: dict,
        normalised,
        underdesign_payload,
        family_payload,
    ) -> dict:
        nonlocal events, normalised_item, underdesign_response, family_response
        events = []
        normalised_item = dict(normalised) if isinstance(normalised, dict) else normalised
        underdesign_response = (
            dict(underdesign_payload) if isinstance(underdesign_payload, dict) else underdesign_payload
        )
        family_response = (
            dict(family_payload) if isinstance(family_payload, dict) else family_payload
        )
        guidance_debug = dict(debug or {})
        final_resolution = dict(resolution or {})
        result = inputs_page.render_design_guide_visible_publication_contract_boundaries(
            final_visible_item=dict(item or {}),
            final_visible_resolution=final_resolution,
            guidance_debug=guidance_debug,
            current_state={"D": 500},
            dg_overview={"utils": {"bending": 0.9}},
            final_active_fail_keys_for_render={"shear", "bending"},
        )
        result_item, result_resolution, family_debug, family_item_applied = result
        case = {
            "name": name,
            "item": result_item,
            "resolution": result_resolution,
            "family_debug": family_debug,
            "family_item_applied": family_item_applied,
            "debug": guidance_debug,
            "events": events,
        }
        cases.append(case)
        return case

    try:
        inputs_page._normalise_visible_optimisation_contract = normalise
        inputs_page.enforce_underdesign_repair_publication_boundary = underdesign
        inputs_page.enforce_family_selection_publication_contract = family

        case = run_case(
            "normalise_only_boundaries_non_dict",
            item={"title_main": "Initial", "family_status_current": {"bending": "PASS"}},
            resolution={"overview": {"utils": {"bending": 0.8}}, "design_brain_result": {"from": "resolution"}},
            debug={"design_brain_result": {"from": "debug"}},
            normalised={"title_main": "Normalised", "family_status_current": {"bending": "PASS"}},
            underdesign_payload=None,
            family_payload=None,
        )
        under_event = next(event for event in case["events"] if event["event"] == "underdesign")
        family_event = next(event for event in case["events"] if event["event"] == "family")
        expect(
            "normalise_only_boundaries_non_dict",
            case["item"]["title_main"] == "Normalised"
            and case["resolution"]["overview"] == {"utils": {"bending": 0.8}}
            and case["family_debug"] == {}
            and case["family_item_applied"] is False
            and under_event["payload"]["guidance_items"][0]["title_main"] == "Normalised"
            and under_event["payload"]["design_brain_result"] == {"from": "debug"}
            and under_event["payload"]["active_failures"] == ["bending", "shear"]
            and family_event["payload"]["guidance_items"][0]["title_main"] == "Normalised",
            f"case={case}",
        )

        case = run_case(
            "underdesign_boundary_failure_rewrites_item_and_presentation",
            item={"title_main": "Initial"},
            resolution={"presentation": {"existing": True}},
            debug={},
            normalised=None,
            underdesign_payload={
                "debug_trace": {
                    "contract_boundary_checked": True,
                    "contract_boundary_contract": {"kind": "underdesign"},
                    "contract_boundary_passed": False,
                    "contract_boundary_violation_reason": "underdesign",
                    "blocked_publication_type": "unsafe",
                },
                "guidance_items": [
                    {"title_main": "Required repair", "reasoning": "Repair first"}
                ],
            },
            family_payload=None,
        )
        expect(
            "underdesign_boundary_failure_rewrites_item_and_presentation",
            case["item"]["title_main"] == "Required repair"
            and case["resolution"]["item"]["title_main"] == "Required repair"
            and case["resolution"]["render_reason"] == "underdesign_repair_invariant_boundary"
            and case["resolution"]["presentation"]["headline"] == "Required repair"
            and case["resolution"]["presentation"]["show_apply_button"] is False
            and case["debug"]["contract_boundary_checked"] is True
            and case["debug"]["contract_boundary_passed"] is False
            and case["family_item_applied"] is False,
            f"case={case}",
        )

        case = run_case(
            "family_selection_applies_item_and_returns_debug",
            item={"title_main": "Initial"},
            resolution={"overview": {"utils": {"bending": 0.8}}},
            debug={},
            normalised=None,
            underdesign_payload={"debug_trace": {}, "guidance_items": [{"title_main": "Initial"}]},
            family_payload={
                "debug_trace": {
                    "family_match_passed": False,
                    "family_match_violation_reason": "mismatch",
                },
                "guidance_items": [
                    {"title_main": "Family boundary item", "summary_line": "Boundary"}
                ],
            },
        )
        expect(
            "family_selection_applies_item_and_returns_debug",
            case["item"]["title_main"] == "Family boundary item"
            and case["resolution"]["item"]["title_main"] == "Family boundary item"
            and case["family_debug"] == {
                "family_match_passed": False,
                "family_match_violation_reason": "mismatch",
            }
            and case["family_item_applied"] is True
            and case["debug"]["family_match_passed"] is False,
            f"case={case}",
        )
    finally:
        inputs_page._normalise_visible_optimisation_contract = originals[
            "_normalise_visible_optimisation_contract"
        ]
        inputs_page.enforce_underdesign_repair_publication_boundary = originals[
            "enforce_underdesign_repair_publication_boundary"
        ]
        inputs_page.enforce_family_selection_publication_contract = originals[
            "enforce_family_selection_publication_contract"
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
                "# Inputs Page Visible Publication Contract Boundaries Verifier",
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
        print("VISIBLE_PUBLICATION_CONTRACT_BOUNDARIES_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("VISIBLE_PUBLICATION_CONTRACT_BOUNDARIES_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
