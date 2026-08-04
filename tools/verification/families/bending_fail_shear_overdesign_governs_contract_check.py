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

from design_brain.families.bending_fail_shear_overdesign_governs.contract import (  # noqa: E402
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
    load_bending_fail_shear_overdesign_governs_contract,
    ownership_contract,
    priority_contract,
    ranking_criteria,
    required_gates,
    selection_boundary,
    shared_exclusions,
    shear_protection,
    success_contract,
    target_band,
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
    "priority_contract",
    "success_contract",
    "shear_protection",
    "target_band",
    "interaction_contract",
    "exact_stop",
    "exhausted",
    "ranking",
    "evidence_contract",
    "lane_proof_policies",
    "shared_exclusions",
    "lock_verification",
}
FORBIDDEN_TOP_LEVEL_KEYS = {"repair_ladder", "optimisation_ladder", "publication", "cta_contract"}
EXPECTED_ALLOWED_SOURCES = {
    "BENDING_FAIL_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "APPROVED_MIXED_MERGE_RULE",
}
EXPECTED_RANKING = (
    "repairs bending failure",
    "maintains shear compliance",
    "bending utilisation closest to target band",
    "shear utilisation closest to target band",
    "smallest geometry increase",
    "smallest reinforcement increase",
    "constructability",
    "cost proxy",
)
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
    failures.extend(f"forbidden_top_level_key:{key}" for key in sorted(FORBIDDEN_TOP_LEVEL_KEYS & set(contract)))

    identity = family_identity()
    if identity.get("family_id") != "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS":
        failures.append("family_id_mismatch")
    if identity.get("package") != "design_brain.families.bending_fail_shear_overdesign_governs":
        failures.append("package_mismatch")

    boundary = selection_boundary()
    if "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS" not in str(boundary.get("starts_after") or ""):
        failures.append("selection_boundary_start_mismatch")
    failures.extend(
        f"selection_boundary_missing:{term}"
        for term in _contains_all(
            list(boundary.get("must_not") or []),
            ["perform classification", "choose another family", "override family selection", "perform family arbitration"],
        )
    )

    inputs = inputs_contract()
    required_groups = set(str(value) for value in inputs.get("required_groups") or [])
    for group in (
        "geometry",
        "reinforcement",
        "material_properties",
        "actions",
        "constraints",
        "bending_fail_candidates",
        "shear_overdesign_candidates",
    ):
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
        f"mixed_ownership_missing:{term}"
        for term in _contains_all(
            list(ownership.get("mixed_family_owns") or []),
            ["candidate merge", "candidate ranking", "recommendation selection", "exact stop proof", "exhausted proof"],
        )
    )
    failures.extend(
        f"mixed_must_not_own_missing:{term}"
        for term in _contains_all(
            list(ownership.get("mixed_family_must_not_own") or []),
            ["bending repair ladder", "shear optimisation ladder", "publication", "CTA rendering", "apply routing"],
        )
    )

    source = candidate_source_contract()
    if set(str(value) for value in source.get("allowed_sources") or []) != EXPECTED_ALLOWED_SOURCES:
        failures.append("candidate_source_allowed_sources_mismatch")
    if source.get("must_not_duplicate_ladders") is not True:
        failures.append("candidate_source_does_not_prohibit_ladder_duplication")
    if source.get("mandatory_source") != "BENDING_FAIL_GOVERNS":
        failures.append("mandatory_source_mismatch")
    if source.get("opportunistic_source") != "SHEAR_OVERDESIGN_GOVERNS":
        failures.append("opportunistic_source_mismatch")
    failures.extend(
        f"candidate_source_forbidden_missing:{term}"
        for term in _contains_all(
            list(source.get("forbidden_sources") or []),
            ["internally generated bending repair ladder", "internally generated shear optimisation ladder"],
        )
    )

    priority = priority_contract()
    if priority.get("mandatory_objective") != "bending repair":
        failures.append("mandatory_objective_mismatch")
    if priority.get("opportunistic_objective") != "shear optimisation":
        failures.append("opportunistic_objective_mismatch")
    failures.extend(
        f"priority_rule_missing:{term}"
        for term in _contains_all(
            list(priority.get("rules") or []),
            ["repairing bending failure is mandatory", "shear optimisation is secondary", "never leave bending underdesign unresolved"],
        )
    )

    success = success_contract()
    failures.extend(
        f"success_requirement_missing:{term}"
        for term in _contains_all(
            list(success.get("valid_mixed_recommendation_requires") or []),
            ["bending becomes compliant", "shear remains compliant", "code compliance maintained", "constructability maintained"],
        )
    )
    failures.extend(
        f"success_must_not_accept_missing:{term}"
        for term in _contains_all(
            list(success.get("must_not_accept") or []),
            ["candidate leaves bending underdesign unresolved", "candidate creates shear underdesign"],
        )
    )

    shear = shear_protection()
    if shear.get("shear_capacity_ratio_min") != 1.0:
        failures.append("shear_capacity_ratio_min_mismatch")
    failures.extend(
        f"shear_protection_missing:{term}"
        for term in _contains_all(list(shear.get("invalid_before_ranking") or []), ["phiVu / Vstar < 1.00", "candidate creates shear underdesign"])
    )

    band = target_band()
    if band.get("bending_lower") != 0.85 or band.get("bending_upper") != 1.0:
        failures.append("bending_target_band_mismatch")
    if band.get("shear_lower") != 0.85 or band.get("shear_upper") != 1.0:
        failures.append("shear_target_band_mismatch")

    interaction = interaction_contract()
    for key in ("geometry_update_keys", "bending_reinforcement_update_keys", "shear_reinforcement_update_keys"):
        if not list(interaction.get(key) or []):
            failures.append(f"interaction_keys_empty:{key}")
    failures.extend(
        f"geometry_recheck_missing:{term}"
        for term in _contains_all(
            list(interaction.get("geometry_recheck_required") or []),
            ["bending", "shear", "minimum reinforcement", "geometry limits", "constructability"],
        )
    )

    failures.extend(
        f"exact_stop_missing:{term}"
        for term in _contains_all(
            list(exact_stop_rules().get("allowed_when") or []),
            ["bending compliant", "shear compliant", "no higher-ranked candidate exists", "further shear optimisation"],
        )
    )
    failures.extend(
        f"exhausted_missing:{term}"
        for term in _contains_all(
            list(exhausted_rules().get("requires") or []),
            ["all bending repair candidates attempted", "all shear optimisation candidates attempted", "all approved merge candidates attempted", "no valid recommendation exists", "specific blocker exists"],
        )
    )

    if tuple(ranking_criteria()) != EXPECTED_RANKING:
        failures.append("ranking_criteria_order_mismatch")
    failures.extend(
        f"invalid_before_ranking_missing:{term}"
        for term in _contains_all(
            list(invalid_before_ranking()),
            ["candidate leaves bending underdesign unresolved", "candidate creates shear underdesign", "candidate violates code compliance", "candidate violates constructability"],
        )
    )

    policies = lane_proof_policies()
    for section in ("candidate_source", "priority", "shear_protection", "terminal"):
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
    source = (ROOT / "design_brain" / "families" / "bending_fail_shear_overdesign_governs" / "contract.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    forbidden = [
        "inputs_page",
        "streamlit",
        "st.session_state",
        "run_bending_fail_governs_ladder_runtime",
        "run_shear_overdesign_governs_runtime",
        "button_contract",
        "publication",
    ]
    return [f"forbidden_contract_source_term:{term}" for term in forbidden if term in source]


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_shear_overdesign_governs_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_shear_overdesign_governs_contract_check_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS Contract Check",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Boundary",
                "",
                "- Bending repair is mandatory.",
                "- Shear optimisation is opportunistic.",
                "- Mixed family owns merge/ranking/selection only.",
                "",
                "## Checks",
                "",
                f"- contract_hash: `{snapshot['contract_hash']}`",
                f"- allowed_sources: `{snapshot['allowed_sources']}`",
                f"- ranking_criteria: `{snapshot['ranking_criteria']}`",
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    contract = load_bending_fail_shear_overdesign_governs_contract()
    failures = _validate_contract(contract) + _validate_source_clean()
    snapshot = {
        "schema": "bending_fail_shear_overdesign_governs_contract_check.v1",
        "result": "PASS" if not failures else "FAIL",
        "contract_path": str(CONTRACT_PATH),
        "contract_hash": contract_hash(),
        "family_identity": family_identity(),
        "allowed_sources": list(candidate_source_contract().get("allowed_sources") or []),
        "priority_contract": priority_contract(),
        "ranking_criteria": list(ranking_criteria()),
        "shared_exclusions": list(shared_exclusions()),
        "required_gates": list(required_gates()),
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS contract check FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS contract check PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
