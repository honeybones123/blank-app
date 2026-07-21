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
        f"inputs_page_final_active_repair_item_acquisition_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_final_active_repair_item_acquisition_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_resolve_recommendation_updates": inputs_page._resolve_recommendation_updates,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_active_fail_near_current_repair_item": inputs_page._active_fail_near_current_repair_item,
        "_direct_target_band_guidance_item": inputs_page._direct_target_band_guidance_item,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    active_repair_return: dict | None = None
    direct_repair_return: dict | None = None

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def resolve_updates(item, *, state):
        events.append({"event": "resolve_updates", "item": dict(item or {}), "state": dict(state or {})})
        return dict((item or {}).get("updates") or {})

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(dict(contract or {}).get("enabled"))

    def active_repair(state, overview, active_keys):
        events.append(
            {
                "event": "active_repair",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "active_keys": sorted(active_keys or []),
            }
        )
        return dict(active_repair_return or {}) if isinstance(active_repair_return, dict) else active_repair_return

    def direct_repair(state, overview, mode_config, *, strengthening, debug_sink):
        events.append(
            {
                "event": "direct_repair",
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "mode_config": dict(mode_config or {}),
                "strengthening": strengthening,
            }
        )
        if isinstance(debug_sink, dict):
            debug_sink["direct_repair_stub_called"] = True
        return dict(direct_repair_return or {}) if isinstance(direct_repair_return, dict) else direct_repair_return

    def mode_config(goal):
        events.append({"event": "mode_config", "goal": goal})
        return {"goal": goal}

    def goal(state):
        events.append({"event": "goal", "state": dict(state or {})})
        return "goal-x"

    def run_case(
        name: str,
        *,
        final_primary_item: dict,
        final_active_fail_keys_for_render: set[str],
        guidance_debug: dict,
        active_item: dict | None,
        direct_item: dict | None,
    ):
        nonlocal events, active_repair_return, direct_repair_return
        events = []
        active_repair_return = dict(active_item or {}) if isinstance(active_item, dict) else active_item
        direct_repair_return = dict(direct_item or {}) if isinstance(direct_item, dict) else direct_item
        item = inputs_page.render_design_guide_final_active_repair_item_acquisition(
            guidance_disp_state={"D": 500},
            dg_overview={"statuses": {"bending": "FAIL", "shear": "FAIL"}},
            guidance_debug=guidance_debug,
            final_primary_item=final_primary_item,
            final_active_fail_keys_for_render=set(final_active_fail_keys_for_render),
        )
        cases.append(
            {
                "name": name,
                "item": item,
                "guidance_debug": dict(guidance_debug),
                "events": list(events),
            }
        )
        return item, guidance_debug, list(events)

    try:
        inputs_page._resolve_recommendation_updates = resolve_updates
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._active_fail_near_current_repair_item = active_repair
        inputs_page._direct_target_band_guidance_item = direct_repair
        inputs_page._design_mode_config = mode_config
        inputs_page._design_optimisation_goal = goal

        item, debug, event_log = run_case(
            "no_active_keys_noop",
            final_primary_item={},
            final_active_fail_keys_for_render=set(),
            guidance_debug={},
            active_item=None,
            direct_item=None,
        )
        expect("no_active_keys_noop", item is None, f"item={item}")
        expect("no_active_keys_noop", event_log == [], f"events={event_log}")

        item, debug, event_log = run_case(
            "already_actionable_primary_noop",
            final_primary_item={
                "action_type": "apply_resolved_candidate",
                "button_contract": {
                    "enabled": True,
                    "action_type": "apply_resolved_candidate",
                    "updates": {"D": 525},
                },
            },
            final_active_fail_keys_for_render={"bending"},
            guidance_debug={},
            active_item={"candidate_search_evidence": {}},
            direct_item=None,
        )
        expect("already_actionable_primary_noop", item is None, f"item={item}")
        expect(
            "already_actionable_primary_noop",
            "active_repair" not in [event["event"] for event in event_log],
            f"events={event_log}",
        )

        item, debug, event_log = run_case(
            "shear_family_acquisition_stamps_owner",
            final_primary_item={"selected_family_id": "SHEAR_FAIL_GOVERNS"},
            final_active_fail_keys_for_render={"shear"},
            guidance_debug={},
            active_item={"candidate_search_evidence": {"seed": True}},
            direct_item=None,
        )
        evidence = dict((item or {}).get("candidate_search_evidence") or {})
        expect(
            "shear_family_acquisition_stamps_owner",
            isinstance(item, dict)
            and item.get("selected_family_id") == "SHEAR_FAIL_GOVERNS"
            and evidence.get("family_route_owner") == "design_brain.families.shear_fail.ShearFailFamily",
            f"item={item}",
        )
        expect(
            "shear_family_acquisition_stamps_owner",
            debug.get("generic_target_band_search_skipped_reason") == "selected_family_shear_fail_governs"
            and debug.get("final_active_repair_owner") == "design_brain.families.shear_fail.ShearFailFamily",
            f"debug={debug}",
        )

        item, debug, event_log = run_case(
            "bending_family_acquisition_stamps_owner",
            final_primary_item={"selected_family_id": "BENDING_FAIL_GOVERNS"},
            final_active_fail_keys_for_render={"bending"},
            guidance_debug={},
            active_item={"candidate_search_evidence": {"seed": True}},
            direct_item=None,
        )
        evidence = dict((item or {}).get("candidate_search_evidence") or {})
        expect(
            "bending_family_acquisition_stamps_owner",
            isinstance(item, dict)
            and item.get("selected_family_id") == "BENDING_FAIL_GOVERNS"
            and evidence.get("family_route_owner") == "design_brain.families.bending_fail.BendingFailFamily",
            f"item={item}",
        )
        expect(
            "bending_family_acquisition_stamps_owner",
            debug.get("generic_target_band_search_skipped_reason") == "selected_family_bending_fail_governs"
            and debug.get("final_active_repair_owner") == "design_brain.families.bending_fail.BendingFailFamily",
            f"debug={debug}",
        )

        item, debug, event_log = run_case(
            "combined_active_keys_use_direct_target_repair",
            final_primary_item={},
            final_active_fail_keys_for_render={"bending", "shear"},
            guidance_debug={},
            active_item=None,
            direct_item={"candidate_search_evidence": {"direct": True}},
        )
        expect(
            "combined_active_keys_use_direct_target_repair",
            isinstance(item, dict) and item.get("candidate_search_evidence", {}).get("direct") is True,
            f"item={item}",
        )
        expect(
            "combined_active_keys_use_direct_target_repair",
            "direct_repair" in [event["event"] for event in event_log]
            and debug.get("direct_repair_stub_called") is True,
            f"events={event_log} debug={debug}",
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    payload = {
        "verifier": "inputs_page_final_active_repair_item_acquisition_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Active Repair Item Acquisition",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload['status']}",
                "",
                "Scope:",
                "- Guards the extracted final active repair item acquisition coordinator.",
                "- Verifies no-op gates, already-actionable primary gate, shear/bending owner stamping, and direct target acquisition.",
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
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
