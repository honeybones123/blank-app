from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_pre_presentation_action_publication_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_presentation_action_publication_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_button_contract": inputs_page._design_guide_button_contract,
        "_cleanup_evidence_has_executable_target_band_proof": inputs_page._cleanup_evidence_has_executable_target_band_proof,
        "_design_guide_display_truth_for_item": inputs_page._design_guide_display_truth_for_item,
        "_design_guide_apply_display_truth_to_items": inputs_page._design_guide_apply_display_truth_to_items,
        "_recommendation_result_for_primary_guidance_card": inputs_page._recommendation_result_for_primary_guidance_card,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _install_common(*, target_proven: bool, contract: dict | None = None) -> dict[str, list]:
        calls: dict[str, list] = {"contract": [], "proof": [], "truth": [], "apply_truth": [], "recommendation": []}
        contract_payload = dict(
            contract
            if contract is not None
            else {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "updates": {"bottom_bars": 4},
                "expected_util": 0.88,
                "target_band_contract_blocked": True,
                "blocking_reason": "old",
                "disabled_reason": "old",
            }
        )

        def _contract(item, *, state):
            calls["contract"].append({"item": dict(item), "state": dict(state)})
            return dict(contract_payload)

        def _proof(evidence, *, expected_util, state, contract, item):
            calls["proof"].append(
                {
                    "evidence": dict(evidence),
                    "expected_util": expected_util,
                    "state": dict(state),
                    "contract": dict(contract),
                    "item": dict(item),
                }
            )
            return bool(target_proven)

        def _truth(item, *, state, overview, mode_config):
            calls["truth"].append(
                {
                    "item": dict(item),
                    "state": dict(state),
                    "overview": dict(overview),
                    "mode_config": dict(mode_config),
                }
            )
            return {"display_truth_source": "synthetic", "displayed_util": 0.88}

        def _apply_truth(items, *, state, overview, mode_config):
            calls["apply_truth"].append(
                {
                    "items": [dict(item) for item in items],
                    "state": dict(state),
                    "overview": dict(overview),
                    "mode_config": dict(mode_config),
                }
            )
            result = []
            for item in items:
                item_copy = dict(item)
                item_copy["truth_applied"] = True
                result.append(item_copy)
            return result

        def _recommendation(items, state, *, branch, request_kind):
            calls["recommendation"].append(
                {
                    "items": [dict(item) for item in items],
                    "state": dict(state),
                    "branch": branch,
                    "request_kind": request_kind,
                }
            )
            return {
                "items": [dict(item) for item in items],
                "state": dict(state),
                "branch": branch,
                "request_kind": request_kind,
            }

        inputs_page._design_guide_button_contract = _contract
        inputs_page._cleanup_evidence_has_executable_target_band_proof = _proof
        inputs_page._design_guide_display_truth_for_item = _truth
        inputs_page._design_guide_apply_display_truth_to_items = _apply_truth
        inputs_page._recommendation_result_for_primary_guidance_card = _recommendation
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "efficiency"
        inputs_page._design_guide_button_contract_enabled = lambda contract_arg: bool(contract_arg.get("enabled"))
        return calls

    def _call(*, family: str, evidence: dict | None = None, util: float | None = 0.88, debug: dict | None = None):
        return inputs_page.render_design_guide_pre_presentation_action_publication(
            bending_action_item={"existing": True},
            bending_action_title="Cleanup action",
            bending_action_family=family,
            bending_action_subfamilies=["bottom_reinforcement"],
            bending_action_candidate_id="candidate-1",
            pre_presentation_updates={"bottom_bars": 4},
            pre_presentation_util=util,
            pre_presentation_evidence=dict(evidence or {"target_band_candidate_count": 1, "safe_executor_backed_candidates_count": 3}),
            pre_presentation_overview={"utils": {"bending": 0.5}},
            pre_presentation_utils={"bending": 0.5, "shear": 0.9},
            guidance_disp_state={"depth": 500},
            guidance_debug=debug if debug is not None else {},
        )

    debug: dict[str, Any] = {}
    try:
        calls = _install_common(target_proven=True)
        guidance_items, recommendation, item = _call(family="bending", debug=debug)
    finally:
        _restore()
    cases.append({"name": "target_proven_bending", "item": item, "debug": dict(debug), "recommendation": recommendation, "calls": calls})
    if len(guidance_items) != 1 or guidance_items[0].get("truth_applied") is not True:
        failures.append(f"target_proven_guidance_items_mismatch:{guidance_items}")
    if item.get("family_id") != "BENDING_OVERDESIGN_GOVERNS":
        failures.append(f"target_proven_family_id_mismatch:{item}")
    if item.get("button_contract", {}).get("enabled") is not True:
        failures.append(f"target_proven_contract_not_enabled:{item.get('button_contract')}")
    if item.get("button_contract", {}).get("target_band_contract_blocked") is not None:
        failures.append(f"target_proven_block_flag_not_removed:{item.get('button_contract')}")
    if item.get("action_payload", {}).get("resolved_candidate_reaches_target_band") is not True:
        failures.append(f"target_proven_payload_flag_missing:{item.get('action_payload')}")
    if item.get("resolved_candidate", {}).get("candidate_reaches_target_band") is not True:
        failures.append(f"target_proven_resolved_flag_missing:{item.get('resolved_candidate')}")
    if debug.get("selected_action_type") != "apply_resolved_candidate":
        failures.append(f"target_proven_debug_action_mismatch:{debug}")
    if debug.get("selected_action_family") != "bending":
        failures.append(f"target_proven_debug_family_mismatch:{debug}")
    if debug.get("primary_guidance_intent") != "efficiency_tightening":
        failures.append(f"target_proven_debug_intent_mismatch:{debug}")
    if debug.get("safe_local_cleanup_count") != 3:
        failures.append(f"target_proven_safe_count_mismatch:{debug}")
    if recommendation.get("branch") != "bending_below_target_bending_only_cleanup":
        failures.append(f"target_proven_recommendation_branch_mismatch:{recommendation}")
    if not calls["proof"] or calls["proof"][0].get("expected_util") != 0.88:
        failures.append(f"target_proven_proof_call_mismatch:{calls['proof']}")

    debug = {}
    try:
        calls = _install_common(target_proven=False)
        guidance_items, recommendation, item = _call(family="bending", debug=debug)
    finally:
        _restore()
    cases.append({"name": "target_not_proven_blocks_action", "item": item, "debug": dict(debug), "recommendation": recommendation, "calls": calls})
    if item.get("action_type") is not None:
        failures.append(f"blocked_item_action_type_mismatch:{item}")
    if item.get("updates") != {}:
        failures.append(f"blocked_item_updates_mismatch:{item}")
    if item.get("guidance_intent") != "specific_blocker":
        failures.append(f"blocked_item_intent_mismatch:{item}")
    blocked_contract = dict(item.get("button_contract") or {})
    if blocked_contract.get("enabled") is not False or blocked_contract.get("actionable") is not False:
        failures.append(f"blocked_contract_enabled_mismatch:{blocked_contract}")
    if blocked_contract.get("blocking_reason") != "cleanup_target_band_not_proven":
        failures.append(f"blocked_contract_reason_mismatch:{blocked_contract}")
    if blocked_contract.get("target_band_contract_blocked") is not True:
        failures.append(f"blocked_contract_flag_mismatch:{blocked_contract}")
    if debug.get("selected_action_type") is not None or debug.get("selected_action_family") is not None:
        failures.append(f"blocked_debug_action_mismatch:{debug}")
    if debug.get("primary_guidance_intent") != "specific_blocker":
        failures.append(f"blocked_debug_intent_mismatch:{debug}")
    if debug.get("button_contract_enabled") is not False:
        failures.append(f"blocked_debug_contract_enabled_mismatch:{debug}")

    terminal_evidence = {
        "terminal_candidate_status": "TERMINAL_TARGET_BAND",
        "target_band_candidate_count": 2,
        "safe_executor_backed_candidates_count": 4,
    }
    debug = {}
    try:
        calls = _install_common(target_proven=True)
        guidance_items, recommendation, item = _call(
            family="combined",
            evidence=terminal_evidence,
            util=0.91,
            debug=debug,
        )
    finally:
        _restore()
    cases.append({"name": "terminal_combined_publication", "item": item, "debug": dict(debug), "recommendation": recommendation, "calls": calls})
    if item.get("family_id") != "COMBINED_OVERDESIGN":
        failures.append(f"terminal_combined_family_id_mismatch:{item}")
    if item.get("button_contract", {}).get("terminal_candidate_status") != "TERMINAL_TARGET_BAND":
        failures.append(f"terminal_combined_contract_status_mismatch:{item.get('button_contract')}")
    if item.get("action_payload", {}).get("terminal_candidate_status") != "TERMINAL_TARGET_BAND":
        failures.append(f"terminal_combined_payload_status_mismatch:{item.get('action_payload')}")
    if item.get("resolved_candidate", {}).get("terminal_candidate_status") != "TERMINAL_TARGET_BAND":
        failures.append(f"terminal_combined_resolved_status_mismatch:{item.get('resolved_candidate')}")
    if item.get("button_contract", {}).get("no_second_cta_required") is not True:
        failures.append(f"terminal_combined_contract_cta_mismatch:{item.get('button_contract')}")
    if debug.get("materially_overprovided_families") != ["bending", "shear"]:
        failures.append(f"terminal_combined_material_families_mismatch:{debug}")
    if debug.get("selected_action_family") != "combined":
        failures.append(f"terminal_combined_selected_family_mismatch:{debug}")
    if debug.get("family_utils") != {"bending": 0.5, "shear": 0.9}:
        failures.append(f"terminal_combined_family_utils_mismatch:{debug}")

    payload = {
        "verifier": "inputs_page_pre_presentation_action_publication_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre Presentation Action Publication Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
