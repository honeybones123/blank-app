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
        f"inputs_page_active_failure_target_action_item_initialization_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_active_failure_target_action_item_initialization_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_mode_config": inputs_page._design_mode_config,
        "_resolved_efficiency_target_band": inputs_page._resolved_efficiency_target_band,
        "_overview_active_failure_keys": inputs_page._overview_active_failure_keys,
        "_active_repair_with_residual_shear_target_cleanup": inputs_page._active_repair_with_residual_shear_target_cleanup,
        "_evaluate_auto_design_candidate": inputs_page._evaluate_auto_design_candidate,
        "_guidance_item_from_resolved_candidate": inputs_page._guidance_item_from_resolved_candidate,
        "_candidate_search_distance_to_band": inputs_page._candidate_search_distance_to_band,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    residual_cleanup_to_return: dict = {}
    preview_to_return: dict | None = None

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def goal(state):
        events.append({"event": "goal", "state": dict(state or {})})
        return "goal-x"

    def mode_config(goal_value):
        events.append({"event": "mode_config", "goal": goal_value})
        return {"goal": goal_value}

    def target_band(mode_cfg, *, goal):
        events.append({"event": "target_band", "mode_cfg": dict(mode_cfg or {}), "goal": goal})
        return 0.85, 1.0, {"source": "stub"}

    def active_failures(overview):
        events.append({"event": "active_failures", "overview": dict(overview or {})})
        return set(dict(overview or {}).get("failures") or [])

    def residual_cleanup(state, updates, *, active_family, mode_config):
        events.append(
            {
                "event": "residual_cleanup",
                "state": dict(state or {}),
                "updates": dict(updates or {}),
                "active_family": active_family,
                "mode_config": dict(mode_config or {}),
            }
        )
        return dict(residual_cleanup_to_return or {})

    def evaluate_candidate(state, *, updates, source, label, action_type):
        events.append(
            {
                "event": "evaluate",
                "state": dict(state or {}),
                "updates": dict(updates or {}),
                "source": source,
                "label": label,
                "action_type": action_type,
            }
        )
        return dict(preview_to_return) if isinstance(preview_to_return, dict) else preview_to_return

    def guidance_item(candidate, *, state, overview, title, reasoning, status, primary_action):
        events.append(
            {
                "event": "guidance_item",
                "candidate": dict(candidate or {}),
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "title": title,
                "reasoning": reasoning,
                "status": status,
                "primary_action": primary_action,
            }
        )
        return {
            "title_main": title,
            "title": title,
            "family": dict(candidate or {}).get("family"),
            "candidate_id": dict(candidate or {}).get("candidate_id"),
            "action_payload": {"updates": dict(dict(candidate or {}).get("updates") or {})},
        }

    def distance_to_band(util, low, high):
        events.append({"event": "distance", "util": util, "low": low, "high": high})
        if util < low:
            return low - util
        if util > high:
            return util - high
        return 0.0

    def run_case(
        name: str,
        *,
        guidance_items: list,
        guidance_debug: dict,
        residual_cleanup: dict,
        preview,
    ):
        nonlocal events, residual_cleanup_to_return, preview_to_return
        events = []
        residual_cleanup_to_return = dict(residual_cleanup or {})
        preview_to_return = dict(preview) if isinstance(preview, dict) else preview
        result_items, action_item = (
            inputs_page.render_design_guide_active_failure_target_action_item_initialization(
                guidance_items=guidance_items,
                guidance_debug=guidance_debug,
                guidance_disp_state={"D": 500},
            )
        )
        cases.append(
            {
                "name": name,
                "result_items": result_items,
                "action_item": action_item,
                "guidance_debug": dict(guidance_debug),
                "events": list(events),
            }
        )
        return result_items, action_item, guidance_debug, list(events)

    try:
        inputs_page._design_optimisation_goal = goal
        inputs_page._design_mode_config = mode_config
        inputs_page._resolved_efficiency_target_band = target_band
        inputs_page._overview_active_failure_keys = active_failures
        inputs_page._active_repair_with_residual_shear_target_cleanup = residual_cleanup
        inputs_page._evaluate_auto_design_candidate = evaluate_candidate
        inputs_page._guidance_item_from_resolved_candidate = guidance_item
        inputs_page._candidate_search_distance_to_band = distance_to_band

        items, action_item, debug, event_log = run_case(
            "no_guidance_items_noop",
            guidance_items=[],
            guidance_debug={"overview": {"any_fail": True}},
            residual_cleanup={},
            preview=None,
        )
        expect("no_guidance_items_noop", items == [], f"items={items}")
        expect("no_guidance_items_noop", action_item is None, f"action_item={action_item}")
        expect("no_guidance_items_noop", event_log == [], f"events={event_log}")

        source_items = [
            {
                "title_main": "Bending capacity is low",
                "family": "bending",
                "candidate_search_evidence": {
                    "target_band_candidate_count": 1,
                    "selected_candidate_updates": {"D": 525},
                    "selected_candidate_util": 0.9,
                    "selected_candidate_id": "cand-1",
                },
            }
        ]
        items, action_item, debug, event_log = run_case(
            "gate_false_when_overview_not_failed",
            guidance_items=list(source_items),
            guidance_debug={"overview": {"any_fail": False}},
            residual_cleanup={},
            preview=None,
        )
        expect("gate_false_when_overview_not_failed", items == source_items, f"items={items}")
        expect("gate_false_when_overview_not_failed", action_item is None, f"action_item={action_item}")
        expect(
            "gate_false_when_overview_not_failed",
            "evaluate" not in [event["event"] for event in event_log],
            f"events={event_log}",
        )

        success_debug = {"overview": {"any_fail": True, "failures": ["bending"]}}
        items, action_item, debug, event_log = run_case(
            "in_band_bending_action_item_replaces_guidance_items",
            guidance_items=list(source_items),
            guidance_debug=success_debug,
            residual_cleanup={},
            preview={"overview": {"utils": {"bending": 0.91}}},
        )
        expect(
            "in_band_bending_action_item_replaces_guidance_items",
            isinstance(action_item, dict),
            f"action_item={action_item}",
        )
        expect(
            "in_band_bending_action_item_replaces_guidance_items",
            items == [action_item],
            f"items={items} action_item={action_item}",
        )
        expect(
            "in_band_bending_action_item_replaces_guidance_items",
            action_item.get("guidance_intent") == "required_fix"
            and action_item.get("primary_card_actionable") is True,
            f"action_item={action_item}",
        )
        expect(
            "in_band_bending_action_item_replaces_guidance_items",
            action_item.get("button_contract", {}).get("updates") == {"D": 525}
            and action_item.get("button_contract", {}).get("expected_util") == 0.91,
            f"button_contract={action_item.get('button_contract')}",
        )
        expect(
            "in_band_bending_action_item_replaces_guidance_items",
            debug.get("selected_action_family") == "bending"
            and debug.get("button_contract_enabled") is True
            and debug.get("button_contract_updates") == {"D": 525},
            f"debug={debug}",
        )
        expect(
            "in_band_bending_action_item_replaces_guidance_items",
            "guidance_item" in [event["event"] for event in event_log],
            f"events={event_log}",
        )

        combined_items = [
            {
                "title_main": "Bending and shear capacity are low",
                "family": "combined",
                "candidate_search_evidence": {
                    "target_band_candidate_count": 1,
                    "selected_candidate_updates": {"D": 525},
                    "selected_candidate_util": 0.9,
                    "selected_candidate_id": "cand-combined",
                },
            }
        ]
        combined_debug = {"overview": {"any_fail": True, "failures": ["bending", "shear"]}}
        items, action_item, debug, event_log = run_case(
            "merged_shear_cleanup_updates_action_and_evidence",
            guidance_items=list(combined_items),
            guidance_debug=combined_debug,
            residual_cleanup={
                "updates": {"D": 525, "s_lig": 180},
                "evidence": {"merged": True},
            },
            preview={"overview": {"worst_util": 1.04}},
        )
        expect(
            "merged_shear_cleanup_updates_action_and_evidence",
            isinstance(action_item, dict),
            f"action_item={action_item}",
        )
        expect(
            "merged_shear_cleanup_updates_action_and_evidence",
            action_item.get("active_repair_includes_residual_shear_cleanup") is True,
            f"action_item={action_item}",
        )
        expect(
            "merged_shear_cleanup_updates_action_and_evidence",
            action_item.get("button_contract", {}).get("updates") == {"D": 525, "s_lig": 180},
            f"button_contract={action_item.get('button_contract')}",
        )
        expect(
            "merged_shear_cleanup_updates_action_and_evidence",
            debug.get("candidate_search_evidence", {}).get("merged") is True,
            f"debug={debug}",
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    payload_out = {
        "verifier": "inputs_page_active_failure_target_action_item_initialization_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(
        json.dumps(payload_out, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active Failure Target Action Item Initialization",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload_out['status']}",
                "",
                "Scope:",
                "- Guards the extracted active-failure target action item initializer.",
                "- Verifies no-op gating, guidance item replacement, button contract stamping, debug sync, and merged residual shear cleanup stamping.",
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
    print(json.dumps(payload_out, indent=2, sort_keys=True, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
