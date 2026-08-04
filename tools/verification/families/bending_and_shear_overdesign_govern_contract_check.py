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

from design_brain.families.bending_and_shear_overdesign_govern.contract import (  # noqa: E402
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
    load_bending_and_shear_overdesign_govern_contract,
    minimum_reinforcement_protection,
    ownership_contract,
    ranking_criteria,
    required_gates,
    selection_boundary,
    shared_exclusions,
    success_contract,
    target_band,
    underdesign_protection,
    zero_shear_protection,
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
    "underdesign_protection",
    "target_band",
    "interaction_contract",
    "minimum_reinforcement_protection",
    "zero_shear_protection",
    "exact_stop",
    "exhausted",
    "ranking",
    "lane_proof_policies",
    "shared_exclusions",
    "lock_verification",
}
EXPECTED_RANKING = [
    "both checks remain compliant",
    "both checks move toward target band",
    "worst utilisation closest to target band",
    "smallest reinforcement quantity",
    "smallest beam volume",
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
    for forbidden in ("publication", "cta_contract", "optimisation_ladder", "repair_ladder"):
        if forbidden in contract:
            failures.append(f"forbidden_top_level_contract_section:{forbidden}")

    identity = family_identity()
    if identity.get("family_id") != "COMBINED_OVERDESIGN_GOVERNS":
        failures.append("family_id_mismatch")
    if identity.get("runtime_family_id") != "COMBINED_OVERDESIGN":
        failures.append("runtime_family_id_mismatch")
    if identity.get("package") != "design_brain.families.bending_and_shear_overdesign_govern":
        failures.append("package_mismatch")
    if "legacy_delegate" in identity:
        failures.append("legacy_delegate_present")

    boundary = selection_boundary()
    failures.extend(
        f"selection_boundary_missing:{term}"
        for term in _contains_all(
            list(boundary.get("must_not") or []),
            ["perform classification", "choose another family", "override family selection", "perform family arbitration"],
        )
    )
    if "COMBINED_OVERDESIGN" not in str(boundary.get("starts_after") or ""):
        failures.append("selection_boundary_start_mismatch")

    inputs = inputs_contract()
    required_groups = set(str(value) for value in inputs.get("required_groups") or [])
    for group in (
        "geometry",
        "reinforcement",
        "material_properties",
        "actions",
        "constraints",
        "bending_overdesign_candidates",
        "shear_overdesign_candidates",
    ):
        if group not in required_groups:
            failures.append(f"required_input_group_missing:{group}")
    failures.extend(
        f"forbidden_input_state_missing:{term}"
        for term in _contains_all(
            list(inputs.get("forbidden_state") or []),
            ["session state", "UI state", "publication state", "CTA state"],
        )
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
            [
                "combined optimisation candidate merge",
                "combined optimisation candidate ranking",
                "combined recommendation selection",
                "combined exact stop proof",
                "combined exhausted proof",
            ],
        )
    )
    failures.extend(
        f"ownership_combined_must_not_missing:{term}"
        for term in _contains_all(
            list(ownership.get("combined_family_must_not_own") or []),
            ["bending optimisation ladder", "shear optimisation ladder", "publication", "CTA rendering", "apply routing"],
        )
    )
    failures.extend(
        f"ownership_bending_missing:{term}"
        for term in _contains_all(
            list(ownership.get("bending_overdesign_governs_owns") or []),
            ["reinforcement optimisation ladder", "geometry optimisation ladder", "bending overdesign candidate generation"],
        )
    )
    failures.extend(
        f"ownership_shear_missing:{term}"
        for term in _contains_all(
            list(ownership.get("shear_overdesign_governs_owns") or []),
            ["shear reinforcement optimisation ladder", "ligature removal logic", "shear overdesign candidate generation"],
        )
    )

    source = candidate_source_contract()
    allowed_sources = set(str(value) for value in source.get("allowed_sources") or [])
    expected_sources = {"BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "APPROVED_COMBINED_MERGE_RULE"}
    if allowed_sources != expected_sources:
        failures.append("candidate_source_allowed_sources_mismatch")
    if source.get("must_not_duplicate_ladders") is not True:
        failures.append("candidate_source_does_not_prohibit_ladder_duplication")
    failures.extend(
        f"candidate_source_forbidden_missing:{term}"
        for term in _contains_all(
            list(source.get("forbidden_sources") or []),
            ["internally generated bending optimisation ladder", "internally generated shear optimisation ladder"],
        )
    )

    success = success_contract()
    failures.extend(
        f"success_requirement_missing:{term}"
        for term in _contains_all(
            list(success.get("valid_combined_optimisation_requires") or []),
            ["bending remains compliant", "shear remains compliant", "code compliance maintained", "constructability maintained"],
        )
    )
    if success.get("partial_optimisation_candidates_are_diagnostic_only") is not True:
        failures.append("partial_optimisation_not_diagnostic_only")

    underdesign = underdesign_protection()
    if underdesign.get("bending_capacity_ratio_min") != 1.0:
        failures.append("bending_capacity_ratio_min_mismatch")
    if underdesign.get("shear_capacity_ratio_min") != 1.0:
        failures.append("shear_capacity_ratio_min_mismatch")
    failures.extend(
        f"underdesign_invalid_missing:{term}"
        for term in _contains_all(list(underdesign.get("invalid_before_ranking") or []), ["phiMu", "phiVu"])
    )

    band = target_band()
    if band.get("bending_lower") != 0.85 or band.get("shear_lower") != 0.85:
        failures.append("target_band_lower_mismatch")
    if band.get("bending_upper") != 1.0 or band.get("shear_upper") != 1.0:
        failures.append("target_band_upper_mismatch")

    interactions = interaction_contract()
    for key in ("geometry_update_keys", "bending_reinforcement_update_keys", "shear_reinforcement_update_keys"):
        if not list(interactions.get(key) or []):
            failures.append(f"interaction_keys_empty:{key}")
    failures.extend(
        f"geometry_recheck_missing:{term}"
        for term in _contains_all(
            list(interactions.get("geometry_recheck_required") or []),
            ["bending", "shear", "minimum reinforcement", "geometry limits", "constructability"],
        )
    )

    min_reo = minimum_reinforcement_protection()
    if min_reo.get("as_must_be_greater_than_or_equal_to_as_min") is not True:
        failures.append("minimum_reinforcement_boundary_missing")

    zero_shear = zero_shear_protection()
    if zero_shear.get("must_not_preserve_unnecessary_shear_reinforcement_when_removal_is_compliant") is not True:
        failures.append("zero_shear_removal_preference_missing")

    failures.extend(
        f"exact_stop_missing:{term}"
        for term in _contains_all(
            list(exact_stop_rules().get("allowed_when") or []),
            ["bending compliant", "shear compliant", "bending inside target band", "shear inside target band", "no higher-ranked"],
        )
    )
    failures.extend(
        f"exhausted_missing:{term}"
        for term in _contains_all(
            list(exhausted_rules().get("requires") or []),
            ["all bending optimisation candidates attempted", "all shear optimisation candidates attempted", "no further compliant optimisation exists", "specific blocker"],
        )
    )

    if list(ranking_criteria()) != EXPECTED_RANKING:
        failures.append("ranking_criteria_order_mismatch")
    failures.extend(
        f"invalid_before_ranking_missing:{term}"
        for term in _contains_all(
            list(invalid_before_ranking()),
            ["candidate creates bending underdesign", "candidate creates shear underdesign", "candidate violates minimum reinforcement"],
        )
    )

    policies = lane_proof_policies()
    for section in (
        "candidate_source",
        "underdesign_protection",
        "minimum_reinforcement",
        "zero_shear",
        "geometry_interaction",
        "terminal",
    ):
        if section not in policies:
            failures.append(f"lane_policy_missing:{section}")

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
    package_root = ROOT / "design_brain" / "families" / "bending_and_shear_overdesign_govern"
    combined_shell = (ROOT / "design_brain" / "families" / "combined_cleanup.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in package_root.glob("*.py")
    )
    forbidden_source_terms = [
        "inputs_page",
        "streamlit",
        "st.session_state",
        "button_contract",
        "record_design_guide_publication_snapshot",
        "build_design_guide_apply_button_contract",
    ]
    for term in forbidden_source_terms:
        if term in source:
            failures.append(f"forbidden_contract_package_source_term:{term}")
    forbidden_ladder_terms = [
        "run_bending_overdesign_governs_runtime",
        "run_shear_overdesign_governs_runtime",
    ]
    for term in forbidden_ladder_terms:
        if term in source or term in combined_shell:
            failures.append(f"combined_overdesign_owns_forbidden_ladder_term:{term}")
    return failures


def _write_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# COMBINED_OVERDESIGN_GOVERNS Contract Check",
        "",
        f"Status: {output.get('status')}",
        "",
        "## Contract",
        "",
        f"- contract_json: `{output.get('contract_path')}`",
        f"- contract_hash: `{output.get('contract_hash')}`",
        "",
        "## Ownership Boundary",
        "",
        "- combined family owns merge/ranking/selection/evidence only",
        "- bending and shear overdesign families keep their own optimisation ladders",
        "- shared CTA/publication/apply/UI/session ownership remains outside",
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
    contract = load_bending_and_shear_overdesign_govern_contract()
    failures = _validate_contract(contract) + _validate_source_clean()
    status = "PASS" if not failures else "FAIL"
    artifact = {
        "schema": "combined_overdesign_governs_contract_check.v1",
        "status": status,
        "contract_path": str(CONTRACT_PATH),
        "contract_hash": contract_hash(),
        "family_identity": family_identity(),
        "selection_boundary": selection_boundary(),
        "candidate_source_contract": candidate_source_contract(),
        "ranking_criteria": list(ranking_criteria()),
        "shared_exclusions": list(shared_exclusions()),
        "required_gates": list(required_gates()),
        "failures": failures,
    }
    artifact_path = ARTIFACT_DIR / f"combined_overdesign_governs_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_overdesign_governs_contract_check_{stamp}.md"
    artifact["artifact"] = str(artifact_path)
    artifact["report"] = str(report_path)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(artifact, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
