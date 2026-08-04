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
    json_path = ARTIFACT_DIR / f"inputs_page_primary_only_shear_action_handoff_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_primary_only_shear_action_handoff_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_attach = inputs_page._attach_family_status_display_payload
    original_complete = inputs_page._complete_visible_low_util_blocker_evidence
    original_enabled = inputs_page._design_guide_button_contract_enabled
    original_stamp = inputs_page._stamp_zero_bending_demand_exclusion

    def attach(item, *, state):
        calls.append({"event": "attach", "item": dict(item or {}), "state": dict(state or {})})
        out = dict(item or {})
        out["attached"] = True
        return out

    def complete(item, overview, state, *, debug_sink=None):
        calls.append(
            {
                "event": "complete",
                "item": dict(item or {}),
                "overview": dict(overview or {}),
                "state": dict(state or {}),
            }
        )
        out = dict(item or {})
        out["completed"] = True
        if isinstance(debug_sink, dict):
            debug_sink["complete_debug"] = True
        return out

    def contract_enabled(contract):
        calls.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool((contract or {}).get("enabled"))

    def stamp(debug, state, utils):
        calls.append({"event": "stamp", "debug": dict(debug), "state": dict(state), "utils": dict(utils)})
        debug["zero_bending_exclusion_stamped"] = True

    try:
        inputs_page._attach_family_status_display_payload = attach
        inputs_page._complete_visible_low_util_blocker_evidence = complete
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._stamp_zero_bending_demand_exclusion = stamp

        executable_debug = {"existing": "debug"}
        (
            executable_action,
            executable_primary_items,
            executable_guidance_items,
            executable_state,
            executable_presentation,
            executable_debug,
        ) = inputs_page.render_design_guide_primary_only_shear_action_handoff(
            render_shear_action={
                "title_main": "Tighten shear links",
                "button_contract": {"enabled": True, "updates": {"s_lig": 250}},
                "candidate_search_evidence": {"source": "safe"},
            },
            guidance_debug=executable_debug,
            render_current_state_for_shear={"s_lig": 300},
            render_current_overview={"utils": {"shear": 0.62, "bending": 0.9}},
        )

        blocked_debug = {}
        (
            blocked_action,
            blocked_primary_items,
            blocked_guidance_items,
            blocked_state,
            blocked_presentation,
            blocked_debug,
        ) = inputs_page.render_design_guide_primary_only_shear_action_handoff(
            render_shear_action={
                "title_main": "Shear cleanup blocked",
                "button_contract": {"enabled": False, "blocking_reason": "exact blocker"},
                "candidate_search_evidence": {"source": "blocked"},
                "exact_blockers_by_family": {"shear": {"reason": "blocked"}},
                "post_click_exact_blockers_by_family": {"shear": {"reason": "blocked"}},
                "cleanup_evidence_by_family": {"shear": {"reason": "blocked"}},
                "post_click_cleanup_evidence_by_family": {"shear": {"reason": "blocked"}},
            },
            guidance_debug=blocked_debug,
            render_current_state_for_shear={"s_lig": 300},
            render_current_overview={"utils": {"shear": 0.62}},
        )
    finally:
        inputs_page._attach_family_status_display_payload = original_attach
        inputs_page._complete_visible_low_util_blocker_evidence = original_complete
        inputs_page._design_guide_button_contract_enabled = original_enabled
        inputs_page._stamp_zero_bending_demand_exclusion = original_stamp

    expect(
        "executable_handoff",
        executable_action.get("attached") is True
        and executable_action.get("completed") is True
        and executable_primary_items == [executable_action]
        and executable_guidance_items == [executable_action]
        and executable_state == {"s_lig": 300}
        and executable_presentation == {}
        and executable_debug.get("guidance_branch")
        == "post_active_repair_residual_shear_best_safe_action"
        and executable_debug.get("selected_action_type") == "apply_resolved_candidate"
        and executable_debug.get("primary_card_intent") == "efficiency_tightening"
        and executable_debug.get("button_contract_enabled") is True
        and executable_debug.get("button_contract_updates") == {"s_lig": 250}
        and executable_debug.get("design_guide_has_actionable_recommendation") is True
        and executable_debug.get("zero_bending_exclusion_stamped") is True,
        (
            f"action={executable_action} primary={executable_primary_items} "
            f"guidance={executable_guidance_items} debug={executable_debug}"
        ),
    )
    expect(
        "blocked_handoff",
        blocked_primary_items == [blocked_action]
        and blocked_guidance_items == [blocked_action]
        and blocked_state == {"s_lig": 300}
        and blocked_presentation == {}
        and blocked_debug.get("guidance_branch") == "post_click_residual_shear_exact_blocker"
        and blocked_debug.get("selected_action_type") is None
        and blocked_debug.get("primary_card_intent") == "specific_blocker"
        and blocked_debug.get("button_contract_enabled") is False
        and blocked_debug.get("design_guide_has_actionable_recommendation") is False
        and blocked_debug.get("exact_blockers_by_family") == {"shear": {"reason": "blocked"}}
        and blocked_debug.get("post_click_cleanup_evidence_by_family")
        == {"shear": {"reason": "blocked"}},
        f"blocked_action={blocked_action} blocked_debug={blocked_debug}",
    )
    expect(
        "call_coverage",
        len([call for call in calls if call["event"] == "attach"]) == 2
        and len([call for call in calls if call["event"] == "complete"]) == 2
        and len([call for call in calls if call["event"] == "contract_enabled"]) == 2
        and len([call for call in calls if call["event"] == "stamp"]) == 2,
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "executable_action": executable_action,
        "blocked_action": blocked_action,
        "executable_debug": executable_debug,
        "blocked_debug": blocked_debug,
        "calls": calls,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Only Shear Action Handoff Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
