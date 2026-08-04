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
        f"inputs_page_post_apply_residual_width_cleanup_selection_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_apply_residual_width_cleanup_selection_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_shear_low_util_target_cleanup_item": inputs_page._shear_low_util_target_cleanup_item,
        "_shear_overdesign_contract_width_cleanup_item": (
            inputs_page._shear_overdesign_contract_width_cleanup_item
        ),
        "_live_shear_overdesign_contract_width_cleanup_item": (
            inputs_page._live_shear_overdesign_contract_width_cleanup_item
        ),
        "_resolve_recommendation_updates": inputs_page._resolve_recommendation_updates,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_updates_match_state": inputs_page._updates_match_state,
        "_guidance_state_snapshot": inputs_page._guidance_state_snapshot,
        "_shared_state_snapshot": inputs_page._shared_state_snapshot,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    low_item_response: object = None
    over_item_response: object = None
    live_item_response: object = None
    resolved_updates_response: dict = {}
    updates_match_response = False
    shared_state_response: dict = {"shared": True}
    guidance_snapshot_response: dict = {"snapshot": True}

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def as_response(value):
        return dict(value) if isinstance(value, dict) else value

    def low_item(state, overview, *, threshold, allow_best_safe_below_threshold):
        events.append(
            {
                "event": "low_item",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "threshold": threshold,
                "allow_best_safe_below_threshold": bool(allow_best_safe_below_threshold),
            }
        )
        return as_response(low_item_response)

    def over_item(state, overview, *, threshold, allow_best_safe_below_threshold):
        events.append(
            {
                "event": "over_item",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "threshold": threshold,
                "allow_best_safe_below_threshold": bool(allow_best_safe_below_threshold),
            }
        )
        return as_response(over_item_response)

    def live_item(overview, *, threshold, allow_best_safe_below_threshold):
        events.append(
            {
                "event": "live_item",
                "overview": dict(overview or {}),
                "threshold": threshold,
                "allow_best_safe_below_threshold": bool(allow_best_safe_below_threshold),
            }
        )
        return as_response(live_item_response)

    def resolve_updates(item, state=None):
        events.append({"event": "resolve_updates", "item": dict(item or {}), "state": dict(state or {})})
        return dict(resolved_updates_response or {})

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(dict(contract or {}).get("enabled"))

    def updates_match(state, updates):
        events.append({"event": "updates_match", "state": dict(state or {}), "updates": dict(updates or {})})
        return bool(updates_match_response)

    def shared_state():
        events.append({"event": "shared_state"})
        return dict(shared_state_response)

    def guidance_snapshot(snapshot):
        events.append({"event": "guidance_snapshot", "snapshot": dict(snapshot or {})})
        return dict(guidance_snapshot_response)

    def run_case(
        name: str,
        *,
        in_target: bool = False,
        overview: dict | None = None,
        state: dict | None = None,
        low_response: object = None,
        over_response: object = None,
        live_response: object = None,
        resolved_updates: dict | None = None,
        updates_match: bool = False,
        shared_response: dict | None = None,
        guidance_response: dict | None = None,
    ) -> dict:
        nonlocal events, low_item_response, over_item_response, live_item_response
        nonlocal resolved_updates_response, updates_match_response
        nonlocal shared_state_response, guidance_snapshot_response
        events = []
        low_item_response = low_response
        over_item_response = over_response
        live_item_response = live_response
        resolved_updates_response = dict(resolved_updates or {})
        updates_match_response = bool(updates_match)
        shared_state_response = dict(shared_response or {"shared": True})
        guidance_snapshot_response = dict(guidance_response or {"snapshot": True})
        result = inputs_page.render_design_guide_post_apply_residual_width_cleanup_selection(
            post_apply_terminal_in_target_band=bool(in_target),
            post_apply_terminal_overview=dict(overview or {}),
            guidance_disp_state=dict(state or {}),
        )
        item, contract, updates, match_state, is_cleanup = result
        case = {
            "name": name,
            "item": item,
            "contract": contract,
            "updates": updates,
            "match_state": match_state,
            "is_cleanup": is_cleanup,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._shear_low_util_target_cleanup_item = low_item
        inputs_page._shear_overdesign_contract_width_cleanup_item = over_item
        inputs_page._live_shear_overdesign_contract_width_cleanup_item = live_item
        inputs_page._resolve_recommendation_updates = resolve_updates
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._updates_match_state = updates_match
        inputs_page._shared_state_snapshot = shared_state
        inputs_page._guidance_state_snapshot = guidance_snapshot

        low = {"title": "low", "button_contract": {"enabled": True, "updates": {"b": 250}}}
        case = run_case(
            "low_util_candidate_selected_when_actionable",
            low_response=low,
            state={"b": 300},
        )
        expect(
            "low_util_candidate_selected_when_actionable",
            case["item"] == low
            and case["contract"] == low["button_contract"]
            and case["updates"] == {"b": 250}
            and case["match_state"] == {"b": 300}
            and case["is_cleanup"] is True
            and [event["event"] for event in case["events"]] == [
                "low_item",
                "contract_enabled",
                "updates_match",
                "contract_enabled",
                "updates_match",
            ],
            f"case={case}",
        )

        over = {"title": "over", "button_contract": {"enabled": True, "updates": {"b": 260}}}
        case = run_case(
            "overdesign_candidate_selected_when_low_not_actionable",
            low_response={"title": "low", "button_contract": {"enabled": False, "updates": {}}},
            over_response=over,
            state={"b": 300},
        )
        expect(
            "overdesign_candidate_selected_when_low_not_actionable",
            case["item"] == over
            and case["contract"] == over["button_contract"]
            and case["is_cleanup"] is True
            and [event["event"] for event in case["events"]].count("over_item") == 1,
            f"case={case}",
        )

        live = {"title": "live", "button_contract": {"enabled": True, "updates": {"b": 270}}}
        case = run_case(
            "live_candidate_selected_after_static_candidates_not_actionable",
            low_response={"title": "low", "button_contract": {"enabled": False}},
            over_response={"title": "over", "button_contract": {"enabled": False}},
            live_response=live,
            state={"b": 300},
            updates_match=True,
            shared_response={"raw": True},
            guidance_response={"live_state": True},
        )
        expect(
            "live_candidate_selected_after_static_candidates_not_actionable",
            case["item"] == live
            and case["match_state"] == {"live_state": True}
            and case["is_cleanup"] is False
            and "shared_state" in [event["event"] for event in case["events"]]
            and "guidance_snapshot" in [event["event"] for event in case["events"]],
            f"case={case}",
        )

        case = run_case(
            "in_target_skips_candidate_factories",
            in_target=True,
            low_response=low,
            over_response=over,
            live_response=live,
            state={"b": 300},
        )
        expect(
            "in_target_skips_candidate_factories",
            case["item"] is None
            and case["contract"] == {}
            and case["updates"] == {}
            and case["is_cleanup"] is False
            and [event["event"] for event in case["events"]] == [],
            f"case={case}",
        )
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "cases": cases,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Apply Residual Width Cleanup Selection Verifier",
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
