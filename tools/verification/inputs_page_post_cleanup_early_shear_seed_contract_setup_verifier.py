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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_seed_contract_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_seed_contract_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_contract_builder = inputs_page._design_guide_button_contract
    original_target_proof = inputs_page._cleanup_evidence_has_executable_target_band_proof

    failures: list[str] = []
    cases: list[dict] = []
    contract_to_return: dict = {}
    proof_to_return = False
    proof_calls: list[dict] = []

    def fake_contract_builder(action, *, state):
        return dict(contract_to_return)

    def fake_target_proof(evidence, *, expected_util, state):
        proof_calls.append(
            {
                "evidence": dict(evidence or {}),
                "expected_util": expected_util,
                "state": dict(state or {}),
            }
        )
        return bool(proof_to_return)

    def run_case(
        name: str,
        *,
        source_contract: dict,
        proof: bool,
        evidence: dict,
        updates: dict,
        candidate_id: str,
        expected_contract: dict,
        expected_util,
        expected_proof: bool,
    ) -> None:
        nonlocal contract_to_return, proof_to_return, proof_calls
        contract_to_return = dict(source_contract)
        proof_to_return = proof
        proof_calls = []
        contract, expected, has_proof = (
            inputs_page.render_design_guide_post_cleanup_early_shear_seed_contract_setup(
                early_shear_cleanup_action={"action": "source"},
                early_shear_cleanup_state={"D": 500},
                early_shear_cleanup_seed_evidence=evidence,
                early_shear_cleanup_seed_updates=updates,
                early_shear_cleanup_candidate_id=candidate_id,
            )
        )
        cases.append(
            {
                "name": name,
                "contract": contract,
                "expected_util": expected,
                "has_proof": has_proof,
                "proof_calls": list(proof_calls),
            }
        )
        if contract != expected_contract:
            failures.append(f"{name}:contract:expected={expected_contract}:actual={contract}")
        if expected != expected_util:
            failures.append(f"{name}:expected_util:expected={expected_util}:actual={expected}")
        if has_proof is not expected_proof:
            failures.append(f"{name}:proof:expected={expected_proof}:actual={has_proof}")
        if len(proof_calls) != 1:
            failures.append(f"{name}:proof_call_count:expected=1:actual={len(proof_calls)}")
        elif proof_calls[0]["expected_util"] != expected_util:
            failures.append(
                f"{name}:proof_expected_util:expected={expected_util}:actual={proof_calls[0]['expected_util']}"
            )

    try:
        inputs_page._design_guide_button_contract = fake_contract_builder
        inputs_page._cleanup_evidence_has_executable_target_band_proof = fake_target_proof

        run_case(
            "enabled_contract_preserved",
            source_contract={
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "shear",
                "updates": {"s_lig": 150},
                "preview_pass": True,
                "expected_util": 0.91,
                "source_candidate_id": "existing",
                "candidate_id": "existing",
            },
            proof=True,
            evidence={"best_safe_final_util": "0.91"},
            updates={"s_lig": 150},
            candidate_id="fallback-id",
            expected_contract={
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "shear",
                "updates": {"s_lig": 150},
                "preview_pass": True,
                "expected_util": 0.91,
                "source_candidate_id": "existing",
                "candidate_id": "existing",
            },
            expected_util=0.91,
            expected_proof=True,
        )

        run_case(
            "disabled_contract_with_target_proof_builds_fallback",
            source_contract={"enabled": False, "actionable": False},
            proof=True,
            evidence={"selected_candidate_util": "0.88"},
            updates={"lig_legs": 4},
            candidate_id="candidate-4",
            expected_contract={
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "shear",
                "updates": {"lig_legs": 4},
                "preview_pass": True,
                "expected_util": 0.88,
                "blocking_reason": None,
                "source_candidate_id": "candidate-4",
                "candidate_id": "candidate-4",
            },
            expected_util=0.88,
            expected_proof=True,
        )

        run_case(
            "disabled_contract_without_target_proof_stays_disabled",
            source_contract={"enabled": False, "actionable": False, "blocking_reason": "no proof"},
            proof=False,
            evidence={"closest_safe_candidate_util": "0.72"},
            updates={"s_lig": 175},
            candidate_id="candidate-5",
            expected_contract={"enabled": False, "actionable": False, "blocking_reason": "no proof"},
            expected_util=0.72,
            expected_proof=False,
        )
    finally:
        inputs_page._design_guide_button_contract = original_contract_builder
        inputs_page._cleanup_evidence_has_executable_target_band_proof = original_target_proof

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_seed_contract_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear Seed Contract Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: proof `{case['has_proof']}`" for case in cases),
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
