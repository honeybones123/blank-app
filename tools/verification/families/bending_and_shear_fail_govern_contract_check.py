from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.bending_and_shear_fail_govern.contract import (  # noqa: E402
    CONTRACT_PATH,
    candidate_source_contract,
    contract_hash,
    exact_stop_rules,
    exhausted_rules,
    family_identity,
    family_result_schema,
    inputs_contract,
    interaction_contract,
    invalid_before_ranking,
    lane_proof_policies,
    load_bending_and_shear_fail_govern_contract,
    ownership_contract,
    ranking_criteria,
    required_gates,
    selection_boundary,
    shared_exclusions,
    success_contract,
    target_band,
    target_band_refinement_lane,
)


REQUIRED_TOP_LEVEL_KEYS = {
    "schema",
    "family_identity",
    "selection_boundary",
    "entry_contract",
    "inputs_contract",
    "family_result_schema",
    "ownership_contract",
    "candidate_source_contract",
    "success_contract",
    "target_band",
    "interaction_contract",
    "exact_stop",
    "exhausted",
    "ranking",
    "lane_proof_policies",
    "shared_exclusions",
    "lock_verification",
}
EXPECTED_RANKING = [
    "repairs both bending and shear",
    "both checks inside target band",
    "worst utilisation closest to target band",
    "smallest geometry increase",
    "smallest reinforcement increase",
    "constructability",
    "cost proxy",
]
REQUIRED_RESULT_FIELDS = {"status", "selected_recommendation", "candidate_repairs", "exhausted_reason", "evidence"}
REQUIRED_SHARED_EXCLUSIONS = {
    "family selection",
    "family arbitration",
    "publication",
    "CTA generation",
    "CTA rendering",
    "apply routing",
    "one-click orchestration",
    "session state",
    "UI rendering",
    "recommendation publication",
    "source precedence",
    "visible wording",
    "user wording",
    "debug rendering",
}


def _contains_all(values: list[Any], required: list[str]) -> list[str]:
    text = "\n".join(str(value).lower() for value in values)
    return [term for term in required if term.lower() not in text]


def _validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    failures.extend(f"missing_top_level_key:{key}" for key in sorted(REQUIRED_TOP_LEVEL_KEYS - set(contract)))
    for forbidden in ("publication", "cta_contract", "repair_ladder"):
        if forbidden in contract:
            failures.append(f"forbidden_top_level_contract_section:{forbidden}")

    identity = family_identity()
    if identity.get("family_id") != "COMBINED_BENDING_SHEAR_FAIL_GOVERNS":
        failures.append("family_id_mismatch")
    if identity.get("runtime_family_id") != "COMBINED_BENDING_SHEAR_FAIL":
        failures.append("runtime_family_id_mismatch")
    if identity.get("package") != "design_brain.families.bending_and_shear_fail_govern":
        failures.append("package_mismatch")
    if "legacy_delegate" in identity:
        failures.append("legacy_delegate_present")

    boundary = selection_boundary()
    must_not = list(boundary.get("must_not") or [])
    failures.extend(
        f"selection_boundary_missing:{term}"
        for term in _contains_all(
            must_not,
            ["perform classification", "choose another family", "override family selection", "perform family arbitration"],
        )
    )
    if "SelectedFamily == COMBINED_BENDING_SHEAR_FAIL" not in str(boundary.get("starts_after") or ""):
        failures.append("selection_boundary_start_mismatch")

    inputs = inputs_contract()
    required_groups = set(str(value) for value in inputs.get("required_groups") or [])
    for group in ("geometry", "reinforcement", "material_properties", "actions", "constraints", "bending_fail_candidates", "shear_fail_candidates"):
        if group not in required_groups:
            failures.append(f"required_input_group_missing:{group}")
    failures.extend(
        f"forbidden_input_state_missing:{term}"
        for term in _contains_all(list(inputs.get("forbidden_state") or []), ["session state", "UI state", "publication state", "CTA state"])
    )

    result_schema = family_result_schema()
    if result_schema.get("result_type") != "FamilyResult":
        failures.append("family_result_type_mismatch")
    result_fields = set(str(value) for value in result_schema.get("required_fields") or [])
    failures.extend(f"family_result_field_missing:{field}" for field in sorted(REQUIRED_RESULT_FIELDS - result_fields))

    ownership = ownership_contract()
    failures.extend(
        f"ownership_combined_missing:{term}"
        for term in _contains_all(
            list(ownership.get("combined_family_owns") or []),
            ["combined candidate merge", "combined candidate ranking", "combined selected recommendation", "combined exact stop proof", "combined exhausted proof"],
        )
    )
    failures.extend(
        f"ownership_bending_missing:{term}"
        for term in _contains_all(list(ownership.get("bending_fail_governs_owns") or []), ["bending repair ladder", "bending candidate generation"])
    )
    failures.extend(
        f"ownership_shear_missing:{term}"
        for term in _contains_all(list(ownership.get("shear_fail_governs_owns") or []), ["shear repair ladder", "shear candidate generation"])
    )

    source = candidate_source_contract()
    allowed_sources = set(str(value) for value in source.get("allowed_sources") or [])
    if allowed_sources != {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS", "APPROVED_COMBINED_MERGE_RULE"}:
        failures.append("candidate_source_allowed_sources_mismatch")
    if source.get("must_not_duplicate_ladders") is not True:
        failures.append("candidate_source_does_not_prohibit_ladder_duplication")
    failures.extend(
        f"approved_merge_rule_missing:{term}"
        for term in _contains_all(
            list(source.get("approved_merge_rules") or []),
            ["target-band refinement", "approved shared geometry", "bending reinforcement", "shear reinforcement"],
        )
    )
    refinement = target_band_refinement_lane()
    if refinement.get("lane_id") != "APPROVED_COMBINED_TARGET_BAND_REFINEMENT":
        failures.append("target_band_refinement_lane_id_mismatch")
    if refinement.get("allowed") is not True:
        failures.append("target_band_refinement_not_allowed")
    if refinement.get("must_use_only_contract_update_keys") is not True:
        failures.append("target_band_refinement_update_key_boundary_missing")
    if refinement.get("exact_stop_requires_evaluated_target_band") is not True:
        failures.append("target_band_refinement_exact_stop_guard_missing")

    success = success_contract()
    failures.extend(
        f"success_requirement_missing:{term}"
        for term in _contains_all(
            list(success.get("valid_combined_repair_requires") or []),
            ["bending utilisation improves", "shear utilisation improves", "bending becomes compliant", "shear becomes compliant"],
        )
    )
    if success.get("partial_repair_candidates_are_diagnostic_only") is not True:
        failures.append("partial_repair_not_diagnostic_only")

    band = target_band()
    if band.get("bending_lower") != 0.85 or band.get("shear_lower") != 0.85:
        failures.append("target_band_lower_mismatch")
    if band.get("bending_upper") != 1.0 or band.get("shear_upper") != 1.0:
        failures.append("target_band_upper_mismatch")
    if band.get("candidate_lane") != "APPROVED_COMBINED_TARGET_BAND_REFINEMENT":
        failures.append("target_band_candidate_lane_mismatch")

    interactions = interaction_contract()
    for key in ("geometry_update_keys", "bending_reinforcement_update_keys", "shear_reinforcement_update_keys"):
        if not list(interactions.get(key) or []):
            failures.append(f"interaction_keys_empty:{key}")
    failures.extend(
        f"geometry_recheck_missing:{term}"
        for term in _contains_all(list(interactions.get("geometry_recheck_required") or []), ["bending", "shear", "minimum reinforcement", "geometry ratio", "constructability"])
    )

    exact_text = list(exact_stop_rules().get("allowed_when") or [])
    failures.extend(
        f"exact_stop_missing:{term}"
        for term in _contains_all(exact_text, ["bending compliant", "shear compliant", "bending inside target band", "shear inside target band", "no higher-ranked"])
    )
    exhausted_text = list(exhausted_rules().get("requires") or [])
    failures.extend(
        f"exhausted_missing:{term}"
        for term in _contains_all(exhausted_text, ["all bending-fail candidates attempted", "all shear-fail candidates attempted", "no valid combined repair exists", "specific blocker"])
    )

    if list(ranking_criteria()) != EXPECTED_RANKING:
        failures.append("ranking_criteria_order_mismatch")
    failures.extend(
        f"invalid_before_ranking_missing:{term}"
        for term in _contains_all(list(invalid_before_ranking()), ["bending remains underdesigned", "shear remains underdesigned", "constructability violated"])
    )

    policies = lane_proof_policies()
    if (policies.get("combined_repair_validity") or {}).get("case_b", {}).get("expected") != "candidate not selected":
        failures.append("partial_bending_only_case_missing")
    if (policies.get("combined_repair_validity") or {}).get("case_c", {}).get("expected") != "candidate not selected":
        failures.append("partial_shear_only_case_missing")
    if "terminal" not in policies:
        failures.append("terminal_policy_missing")
    refinement_policy = policies.get("target_band_refinement") or {}
    if refinement_policy.get("lane_id") != "APPROVED_COMBINED_TARGET_BAND_REFINEMENT":
        failures.append("target_band_refinement_policy_missing")
    failures.extend(
        f"target_band_refinement_required_proof_missing:{term}"
        for term in _contains_all(
            list(refinement_policy.get("required_proof") or []),
            ["target-band candidates counted", "safe fallback candidates counted", "fallback reason emitted"],
        )
    )

    exclusions = set(shared_exclusions())
    failures.extend(f"shared_exclusion_missing:{term}" for term in sorted(REQUIRED_SHARED_EXCLUSIONS - exclusions))

    verification = contract.get("lock_verification") or {}
    for verifier in verification.get("required_verifiers") or []:
        if not (ROOT / str(verifier)).exists():
            failures.append(f"required_verifier_missing:{verifier}")
    if not required_gates():
        failures.append("required_gates_empty")
    return failures


def _validate_source_clean() -> list[str]:
    failures: list[str] = []
    contract_source = (ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "contract.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    forbidden = ["inputs_page", "streamlit", "st.session_state", "button_contract", "publication"]
    for term in forbidden:
        if term in contract_source:
            failures.append(f"forbidden_contract_source_term:{term}")
    return failures


def _write_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# COMBINED_BENDING_SHEAR_FAIL_GOVERNS Contract Check",
        "",
        f"Status: {output.get('status')}",
        "",
        "## Contract",
        "",
        f"- contract_json: `{output.get('contract_path')}`",
        f"- contract_hash: `{output.get('contract_hash')}`",
        "",
        "## Failures",
        "",
    ]
    lines.extend([f"- {failure}" for failure in output.get("failures") or []] or ["- none"])
    lines.extend(["", "## Output", "", f"- `{output.get('artifact')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    contract = load_bending_and_shear_fail_govern_contract()
    failures = _validate_contract(contract) + _validate_source_clean()
    status = "PASS" if not failures else "FAIL"
    artifact = {
        "schema": "combined_bending_shear_fail_governs_contract_check.v1",
        "status": status,
        "contract_path": str(CONTRACT_PATH),
        "contract_hash": contract_hash(),
        "family_identity": family_identity(),
        "selection_boundary": selection_boundary(),
        "candidate_source_contract": candidate_source_contract(),
        "target_band_refinement_lane": target_band_refinement_lane(),
        "ranking_criteria": list(ranking_criteria()),
        "shared_exclusions": list(shared_exclusions()),
        "required_gates": list(required_gates()),
        "failures": failures,
    }
    artifact_path = ARTIFACT_DIR / f"combined_bending_shear_fail_governs_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_governs_contract_check_{stamp}.md"
    artifact["artifact"] = str(artifact_path)
    artifact["report"] = str(report_path)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(artifact, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
