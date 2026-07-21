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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_item_packaging_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_item_packaging_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "_design_guide_button_contract",
        "_cleanup_evidence_has_executable_target_band_proof",
        "_disable_cleanup_item_without_target_band_proof",
        "_design_guide_display_truth_for_item",
        "_design_mode_config",
        "_design_optimisation_goal",
        "_design_guide_apply_display_truth_to_items",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}

    failures: list[str] = []
    cases: list[dict] = []
    calls: list[str] = []
    target_proven = True

    def fake_button_contract(item, *, state):
        calls.append("button_contract")
        return {"enabled": True, "expected_util": "0.91", "contract_family": item.get("family")}

    def fake_target_proof(evidence, *, expected_util, state, contract, item):
        calls.append("target_proof")
        if expected_util != 0.91:
            failures.append(f"target_proof_expected_util_mismatch:{expected_util}")
        if contract.get("contract_family") != item.get("family"):
            failures.append("target_proof_contract_item_family_mismatch")
        return bool(target_proven)

    def fake_disable(item, *, evidence, state, contract, expected_util):
        calls.append("disable_without_proof")
        disabled_item = dict(item)
        disabled_contract = dict(contract)
        disabled_contract["enabled"] = False
        disabled_contract["disabled_without_target_band_proof"] = True
        disabled_item["disabled_without_target_band_proof"] = True
        return disabled_item, disabled_contract, False

    def fake_display_truth(item, *, state, overview, mode_config):
        calls.append("display_truth")
        return {"truth": True, "overview_seen": dict(overview)}

    def fake_design_goal(state):
        calls.append("design_goal")
        return "balanced"

    def fake_design_mode(goal):
        calls.append("design_mode")
        return {"goal": goal}

    def fake_apply_display_truth(items, *, state, overview, mode_config):
        calls.append("apply_display_truth")
        stamped = [dict(item) for item in items]
        stamped[0]["display_truth_applied"] = True
        return stamped

    def run_case(name: str, *, proof: bool) -> None:
        nonlocal target_proven
        calls.clear()
        target_proven = proof
        item, contract, proven = inputs_page.render_design_guide_presentation_bending_cleanup_item_packaging(
            presentation_bending_item={"action_payload": {"pre": True}, "resolved_candidate": {"pre": True}},
            presentation_bending_title="Reduce bottom steel",
            presentation_bending_family="bending",
            presentation_bending_subfamilies=["geometry"],
            presentation_bending_candidate_id="cand-1",
            presentation_bending_evidence={"selected_candidate_util": "0.88", "target_band_candidate_count": 2},
            presentation_bending_updates={"bottom_bar_dia": 16},
            guidance_disp_state={"D": 500},
            guidance_debug={"overview": {"utils": {"bending": 0.88}}},
        )
        cases.append({"name": name, "proven": proven, "contract": contract, "calls": list(calls)})
        expected_calls = ["button_contract", "target_proof", "display_truth", "apply_display_truth"]
        for expected_call in expected_calls:
            if expected_call not in calls:
                failures.append(f"{name}:missing_call:{expected_call}:calls={calls}")
        if not proof and "disable_without_proof" not in calls:
            failures.append(f"{name}:missing_disable_without_proof")
        if proof and "disable_without_proof" in calls:
            failures.append(f"{name}:unexpected_disable_without_proof")
        if proven is not proof:
            failures.append(f"{name}:proven:expected={proof}:actual={proven}")
        if item.get("title") != "Reduce bottom steel" or item.get("family") != "bending":
            failures.append(f"{name}:item_identity_mismatch:{item}")
        if item.get("updates") != {"bottom_bar_dia": 16}:
            failures.append(f"{name}:updates_mismatch:{item.get('updates')}")
        payload = dict(item.get("action_payload") or {})
        resolved = dict(item.get("resolved_candidate") or {})
        if payload.get("resolved_candidate_updates") != {"bottom_bar_dia": 16}:
            failures.append(f"{name}:payload_updates_mismatch:{payload}")
        if payload.get("resolved_candidate_reaches_target_band") is not proof:
            failures.append(f"{name}:payload_target_flag_mismatch:{payload}")
        if resolved.get("candidate_reaches_target_band") is not proof:
            failures.append(f"{name}:resolved_target_flag_mismatch:{resolved}")
        if item.get("button_contract") != contract:
            failures.append(f"{name}:button_contract_not_stamped")
        if item.get("display_truth") != {"truth": True, "overview_seen": {"utils": {"bending": 0.88}}}:
            failures.append(f"{name}:display_truth_mismatch:{item.get('display_truth')}")
        if item.get("display_truth_applied") is not True:
            failures.append(f"{name}:display_truth_application_missing")

    try:
        inputs_page._design_guide_button_contract = fake_button_contract
        inputs_page._cleanup_evidence_has_executable_target_band_proof = fake_target_proof
        inputs_page._disable_cleanup_item_without_target_band_proof = fake_disable
        inputs_page._design_guide_display_truth_for_item = fake_display_truth
        inputs_page._design_mode_config = fake_design_mode
        inputs_page._design_optimisation_goal = fake_design_goal
        inputs_page._design_guide_apply_display_truth_to_items = fake_apply_display_truth

        run_case("target_proven_stamps_payload_resolved_contract_and_display_truth", proof=True)
        run_case("missing_target_proof_disables_item_and_stamps_false_target_flags", proof=False)
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_item_packaging_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Item Packaging Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: `{case['proven']}`" for case in cases),
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
