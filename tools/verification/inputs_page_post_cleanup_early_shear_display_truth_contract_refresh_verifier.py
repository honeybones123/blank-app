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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_display_truth_contract_refresh_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_display_truth_contract_refresh_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_design_guide_apply_button_contracts_to_items": inputs_page._design_guide_apply_button_contracts_to_items,
        "_design_guide_apply_display_truth_to_items": inputs_page._design_guide_apply_display_truth_to_items,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_guide_button_contract": inputs_page._design_guide_button_contract,
        "_cleanup_evidence_has_executable_target_band_proof": inputs_page._cleanup_evidence_has_executable_target_band_proof,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
    }

    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    display_items_to_return: list | None = None
    contract_to_return: dict = {}
    proof_to_return = True
    enabled_to_return = True

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def apply_contracts(items, *, state):
        events.append({"event": "apply_contracts", "items": list(items or []), "state": dict(state or {})})
        return [{"after_contract": True, **dict(item)} for item in list(items or [])]

    def apply_display(items, *, state, overview, mode_config):
        events.append(
            {
                "event": "apply_display",
                "items": list(items or []),
                "state": dict(state or {}),
                "overview": dict(overview or {}),
                "mode_config": dict(mode_config or {}),
            }
        )
        if display_items_to_return is not None:
            return list(display_items_to_return)
        return [{"after_display": True, **dict(item)} for item in list(items or [])]

    def mode_config(goal):
        events.append({"event": "mode_config", "goal": goal})
        return {"mode": goal}

    def optimisation_goal(state):
        events.append({"event": "goal", "state": dict(state or {})})
        return "goal-x"

    def button_contract(action, *, state):
        events.append({"event": "button_contract", "action": dict(action or {}), "state": dict(state or {})})
        return dict(contract_to_return)

    def target_proof(evidence, *, expected_util, state):
        events.append(
            {
                "event": "target_proof",
                "evidence": dict(evidence or {}),
                "expected_util": expected_util,
                "state": dict(state or {}),
            }
        )
        return bool(proof_to_return)

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(enabled_to_return)

    def run_case(
        name: str,
        *,
        action: dict,
        contract: dict,
        display_items,
        proof: bool,
        enabled: bool,
        expected_action: dict,
        expected_expected_util,
        expected_renderable: bool,
    ) -> None:
        nonlocal events, display_items_to_return, contract_to_return, proof_to_return, enabled_to_return
        events = []
        display_items_to_return = display_items
        contract_to_return = dict(contract)
        proof_to_return = proof
        enabled_to_return = enabled
        result = inputs_page.render_design_guide_post_cleanup_early_shear_display_truth_contract_refresh(
            early_shear_cleanup_action=dict(action),
            early_shear_cleanup_state={"D": 500},
            early_shear_cleanup_overview={"utils": {"shear": 0.82}},
        )
        (
            refreshed_action,
            refreshed_items,
            refreshed_contract,
            evidence,
            expected_util,
            renderable,
        ) = result
        cases.append(
            {
                "name": name,
                "action": refreshed_action,
                "items": refreshed_items,
                "contract": refreshed_contract,
                "evidence": evidence,
                "expected_util": expected_util,
                "renderable": renderable,
                "events": list(events),
            }
        )
        expect(name, refreshed_action == expected_action, f"action={refreshed_action}")
        expect(name, refreshed_contract == contract, f"contract={refreshed_contract}")
        expect(name, expected_util == expected_expected_util, f"expected_util={expected_util}")
        expect(name, renderable is expected_renderable, f"renderable={renderable}")
        event_names = [event["event"] for event in events]
        expect(
            name,
            event_names == ["apply_contracts", "goal", "mode_config", "apply_display", "button_contract", "target_proof", "contract_enabled"],
            f"event_names={event_names}",
        )
        proof_events = [event for event in events if event["event"] == "target_proof"]
        if proof_events:
            expect(name, proof_events[0]["expected_util"] == expected_expected_util, "proof_expected_util_mismatch")

    try:
        inputs_page._design_guide_apply_button_contracts_to_items = apply_contracts
        inputs_page._design_guide_apply_display_truth_to_items = apply_display
        inputs_page._design_mode_config = mode_config
        inputs_page._design_optimisation_goal = optimisation_goal
        inputs_page._design_guide_button_contract = button_contract
        inputs_page._cleanup_evidence_has_executable_target_band_proof = target_proof
        inputs_page._design_guide_button_contract_enabled = contract_enabled

        run_case(
            "display_item_selected_and_best_safe_util_precedence",
            action={
                "title_main": "Source",
                "candidate_search_evidence": {"best_safe_final_util": "0.91"},
            },
            contract={"enabled": True, "expected_util": 0.77, "updates": {"s_lig": 150}},
            display_items=[
                {
                    "title_main": "Display",
                    "candidate_search_evidence": {"best_safe_final_util": "0.91"},
                }
            ],
            proof=True,
            enabled=True,
            expected_action={
                "title_main": "Display",
                "candidate_search_evidence": {"best_safe_final_util": "0.91"},
            },
            expected_expected_util=0.91,
            expected_renderable=True,
        )
        run_case(
            "display_empty_falls_back_to_original_and_contract_expected_used",
            action={"title_main": "Source", "candidate_search_evidence": {}},
            contract={"enabled": True, "expected_util": 0.74, "updates": {"s_lig": 175}},
            display_items=[],
            proof=True,
            enabled=True,
            expected_action={"title_main": "Source", "candidate_search_evidence": {}},
            expected_expected_util=0.74,
            expected_renderable=True,
        )
        run_case(
            "proof_or_enabled_blocks_renderable",
            action={"title_main": "Blocked", "candidate_search_evidence": {"selected_candidate_util": "0.8"}},
            contract={"enabled": False, "expected_util": 0.74},
            display_items=None,
            proof=True,
            enabled=False,
            expected_action={
                "after_display": True,
                "after_contract": True,
                "title_main": "Blocked",
                "candidate_search_evidence": {"selected_candidate_util": "0.8"},
            },
            expected_expected_util=0.8,
            expected_renderable=False,
        )
    finally:
        for name, original in originals.items():
            setattr(inputs_page, name, original)

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_display_truth_contract_refresh_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear Display Truth Contract Refresh Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: renderable `{case['renderable']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload_out["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
