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
        f"inputs_page_final_active_repair_presentation_packaging_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_final_active_repair_presentation_packaging_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_design_guide_apply_button_contracts_to_items": inputs_page._design_guide_apply_button_contracts_to_items,
        "_resolve_recommendation_updates": inputs_page._resolve_recommendation_updates,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_evaluate_auto_design_candidate": inputs_page._evaluate_auto_design_candidate,
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    preview_to_return: dict | None = None

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def apply_contracts(items, *, state):
        events.append({"event": "apply_contracts", "items": list(items or []), "state": dict(state or {})})
        return [dict(item) for item in list(items or []) if isinstance(item, dict)]

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

    def run_case(
        name: str,
        *,
        item,
        keys: set[str],
        preview,
    ):
        nonlocal events, preview_to_return
        events = []
        preview_to_return = dict(preview) if isinstance(preview, dict) else preview
        debug: dict = {}
        result = inputs_page.render_design_guide_final_active_repair_presentation_packaging(
            final_active_repair_item=item,
            final_active_fail_keys_for_render=set(keys),
            guidance_items=[{"title_main": "Original primary"}],
            guidance_disp_state={"D": 500},
            guidance_debug=debug,
            dg_presentation={"headline": "Original"},
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
            packaged,
        ) = result
        case = {
            "name": name,
            "items": result_items,
            "terminal_state": terminal_state,
            "terminal_state_source": terminal_state_source,
            "presentation": presentation,
            "render_plan": render_plan,
            "packaged": packaged,
            "guidance_debug": dict(debug),
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._design_guide_apply_button_contracts_to_items = apply_contracts
        inputs_page._resolve_recommendation_updates = resolve_updates
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._evaluate_auto_design_candidate = evaluate

        case = run_case(
            "non_dict_noop",
            item=None,
            keys={"bending"},
            preview=None,
        )
        expect(
            "non_dict_noop",
            case["items"] == [{"title_main": "Original primary"}]
            and case["terminal_state"] == "terminal-before"
            and case["packaged"] is False
            and case["events"] == [],
            f"case={case}",
        )

        case = run_case(
            "disabled_contract_noop",
            item={
                "action_type": "apply_resolved_candidate",
                "button_contract": {
                    "enabled": False,
                    "action_type": "apply_resolved_candidate",
                    "updates": {"D": 525},
                },
            },
            keys={"bending"},
            preview=None,
        )
        expect(
            "disabled_contract_noop",
            case["packaged"] is False
            and case["items"] == [{"title_main": "Original primary"}],
            f"case={case}",
        )

        case = run_case(
            "bending_family_preview_packaged",
            item={
                "action_type": "apply_resolved_candidate",
                "selected_family_id": "BENDING_FAIL_GOVERNS",
                "button_contract": {
                    "enabled": True,
                    "action_type": "apply_resolved_candidate",
                    "updates": {"D": 525},
                },
                "action_payload": {"updates": {"D": 500}},
                "resolved_candidate": {"updates": {"D": 500}},
                "exact_blockers_by_family": {"bending": {"reason": "old"}},
            },
            keys={"bending"},
            preview={"overview": {"utils": {"bending": 0.92}}},
        )
        primary = dict(case["items"][0] or {})
        contract = dict(primary.get("button_contract") or {})
        debug = dict(case["guidance_debug"] or {})
        expect(
            "bending_family_preview_packaged",
            case["packaged"] is True
            and case["terminal_state"] is None
            and case["terminal_state_source"] == "final_active_failure_repair_override"
            and primary.get("title_main") == "Bending capacity is low"
            and primary.get("family") == "bending"
            and primary.get("primary_card_actionable") is True
            and "exact_blockers_by_family" not in primary,
            f"case={case}",
        )
        expect(
            "bending_family_preview_packaged",
            contract.get("expected_util") == 0.92
            and contract.get("family") == "bending"
            and contract.get("family_id") == "BENDING_FAIL_GOVERNS"
            and contract.get("updates") == {"D": 525},
            f"contract={contract}",
        )
        expect(
            "bending_family_preview_packaged",
            debug.get("guidance_branch") == "final_active_failure_repair_override"
            and debug.get("selected_action_family") == "bending"
            and debug.get("primary_displayed_util") == 0.92,
            f"debug={debug}",
        )
        expect(
            "bending_family_preview_packaged",
            case["presentation"].get("headline") == "Bending capacity is low"
            and case["presentation"].get("show_apply_button") is True
            and case["render_plan"].get("reason") == "final_active_failure_repair_override",
            f"presentation={case['presentation']} render_plan={case['render_plan']}",
        )

        case = run_case(
            "combined_family_worst_util_packaged",
            item={
                "action_type": "apply_resolved_candidate",
                "button_contract": {
                    "enabled": True,
                    "action_type": "apply_resolved_candidate",
                    "updates": {"D": 525, "s_lig": 180},
                },
            },
            keys={"bending", "shear"},
            preview={"overview": {"worst_util": 1.03}},
        )
        primary = dict(case["items"][0] or {})
        contract = dict(primary.get("button_contract") or {})
        expect(
            "combined_family_worst_util_packaged",
            case["packaged"] is True
            and primary.get("title_main") == "Bending and shear capacity are low"
            and primary.get("family") == "combined"
            and contract.get("expected_util") == 1.03
            and contract.get("updates") == {"D": 525, "s_lig": 180},
            f"case={case}",
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    payload = {
        "verifier": "inputs_page_final_active_repair_presentation_packaging_verifier",
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
                "# Inputs Page Final Active Repair Presentation Packaging",
                "",
                f"Timestamp: {timestamp}",
                "",
                f"Status: {payload['status']}",
                "",
                "Scope:",
                "- Guards the extracted final active repair presentation packaging coordinator.",
                "- Verifies no-op gates, contract/display truth stamping, presentation updates, render-plan updates, blocker removal, and debug sync.",
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
