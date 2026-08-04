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
        f"inputs_page_final_active_failure_payload_rebuild_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_final_active_failure_payload_rebuild_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "session_state": inputs_page.st.session_state,
        "_resolve_recommendation_updates": inputs_page._resolve_recommendation_updates,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_evaluate_auto_design_candidate": inputs_page._evaluate_auto_design_candidate,
        "_overview_required_checks_acceptable": inputs_page._overview_required_checks_acceptable,
        "_guidance_item_from_resolved_candidate": inputs_page._guidance_item_from_resolved_candidate,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    preview_to_return: dict | None = None
    required_checks_ok = True

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def resolve_updates(item, *, state):
        events.append({"event": "resolve_updates", "item": dict(item or {}), "state": dict(state or {})})
        return dict((item or {}).get("updates") or {})

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(dict(contract or {}).get("enabled"))

    def evaluate(state, *, updates, source, label, action_type):
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

    def required_checks(overview):
        events.append({"event": "required_checks", "overview": dict(overview or {})})
        return bool(required_checks_ok)

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
            "action_type": dict(candidate or {}).get("action_type"),
            "action_payload": {"updates": dict(dict(candidate or {}).get("updates") or {})},
        }

    def run_case(
        name: str,
        *,
        active_keys: set[str],
        guidance_items: list,
        binding_audit: dict,
        preview,
        required_ok: bool = True,
    ):
        nonlocal events, preview_to_return, required_checks_ok
        events = []
        preview_to_return = dict(preview) if isinstance(preview, dict) else preview
        required_checks_ok = bool(required_ok)
        inputs_page.st.session_state = {
            inputs_page.DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY: dict(binding_audit or {})
        }
        debug: dict = {}
        result = inputs_page.render_design_guide_final_active_failure_payload_rebuild(
            final_active_fail_keys_for_render=set(active_keys),
            guidance_items=list(guidance_items or []),
            guidance_disp_state={"D": 500},
            guidance_debug=debug,
            dg_overview={"statuses": {"bending": "FAIL", "shear": "FAIL"}},
            dg_presentation={"headline": "Before"},
            terminal_state="terminal-before",
            terminal_state_source="source-before",
            render_plan={"reason": "before"},
        )
        (
            result_items,
            terminal_state,
            terminal_state_source,
            presentation,
            render_plan,
            rebuilt,
        ) = result
        case = {
            "name": name,
            "items": result_items,
            "terminal_state": terminal_state,
            "terminal_state_source": terminal_state_source,
            "presentation": presentation,
            "render_plan": render_plan,
            "rebuilt": rebuilt,
            "guidance_debug": dict(debug),
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._resolve_recommendation_updates = resolve_updates
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._evaluate_auto_design_candidate = evaluate
        inputs_page._overview_required_checks_acceptable = required_checks
        inputs_page._guidance_item_from_resolved_candidate = guidance_item

        case = run_case(
            "already_actionable_noop",
            active_keys={"bending"},
            guidance_items=[
                {
                    "action_type": "apply_resolved_candidate",
                    "button_contract": {
                        "enabled": True,
                        "action_type": "apply_resolved_candidate",
                        "updates": {"D": 525},
                    },
                }
            ],
            binding_audit={"visible_updates": {"D": 530}},
            preview={"overview": {"any_fail": False, "worst_util": 0.9}},
        )
        expect(
            "already_actionable_noop",
            case["rebuilt"] is False
            and case["terminal_state"] == "terminal-before"
            and "evaluate" not in [event["event"] for event in case["events"]],
            f"case={case}",
        )

        case = run_case(
            "no_binding_updates_noop",
            active_keys={"bending"},
            guidance_items=[{"title_main": "No action"}],
            binding_audit={},
            preview={"overview": {"any_fail": False, "worst_util": 0.9}},
        )
        expect(
            "no_binding_updates_noop",
            case["rebuilt"] is False
            and case["items"] == [{"title_main": "No action"}],
            f"case={case}",
        )

        case = run_case(
            "preview_still_fails_noop",
            active_keys={"shear"},
            guidance_items=[{"title_main": "No action"}],
            binding_audit={"visible_updates": {"s_lig": 180}},
            preview={"overview": {"any_fail": True, "worst_util": 1.2}},
        )
        expect(
            "preview_still_fails_noop",
            case["rebuilt"] is False
            and "guidance_item" not in [event["event"] for event in case["events"]],
            f"case={case}",
        )

        case = run_case(
            "bending_rebuild_from_visible_updates",
            active_keys={"bending"},
            guidance_items=[{"title_main": "No action"}],
            binding_audit={
                "visible_updates": {"D": 525},
                "visible_primary_candidate_id": "visible-candidate-1",
            },
            preview={"overview": {"any_fail": False, "worst_util": 0.93}},
        )
        primary = dict(case["items"][0] or {})
        contract = dict(primary.get("button_contract") or {})
        evidence = dict(primary.get("candidate_search_evidence") or {})
        debug = dict(case["guidance_debug"] or {})
        expect(
            "bending_rebuild_from_visible_updates",
            case["rebuilt"] is True
            and case["terminal_state"] is None
            and case["terminal_state_source"] == "final_active_failure_payload_rebuild"
            and primary.get("title_main") == "Bending capacity is low"
            and primary.get("primary_card_actionable") is True,
            f"case={case}",
        )
        expect(
            "bending_rebuild_from_visible_updates",
            contract.get("updates") == {"D": 525}
            and contract.get("expected_util") == 0.93
            and evidence.get("selected_candidate_id") == "visible-candidate-1"
            and evidence.get("outside_target_band_allowed") is True,
            f"contract={contract} evidence={evidence}",
        )
        expect(
            "bending_rebuild_from_visible_updates",
            debug.get("guidance_branch") == "final_active_failure_payload_rebuild"
            and debug.get("selected_action_family") == "bending"
            and debug.get("button_contract_updates") == {"D": 525},
            f"debug={debug}",
        )

        case = run_case(
            "combined_rebuild_from_button_contract_updates",
            active_keys={"bending", "shear"},
            guidance_items=[{"title_main": "No action"}],
            binding_audit={
                "button_contract_updates": {"D": 525, "s_lig": 180},
                "button_contract_candidate_id": "button-candidate-1",
            },
            preview={"overview": {"any_fail": False, "governing_util": 1.01}},
        )
        primary = dict(case["items"][0] or {})
        evidence = dict(primary.get("candidate_search_evidence") or {})
        expect(
            "combined_rebuild_from_button_contract_updates",
            case["rebuilt"] is True
            and primary.get("family") == "combined"
            and primary.get("title_main") == "Bending and shear capacity are low"
            and evidence.get("combined_strengthening_searched") is True
            and evidence.get("selected_candidate_id") == "button-candidate-1",
            f"case={case}",
        )
    finally:
        inputs_page.st.session_state = originals["session_state"]
        for name, original in originals.items():
            if name != "session_state":
                setattr(inputs_page, name, original)

    payload = {
        "verifier": "inputs_page_final_active_failure_payload_rebuild_verifier",
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
                "# Inputs Page Final Active Failure Payload Rebuild",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload['status']}",
                "",
                "Scope:",
                "- Guards the extracted final active failure payload rebuild coordinator.",
                "- Verifies no-op gates, failed-preview gate, visible-update rebuild, button-contract-update rebuild, contract stamping, evidence stamping, and debug sync.",
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
