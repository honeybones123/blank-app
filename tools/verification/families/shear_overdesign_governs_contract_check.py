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

from design_brain.families.shear_overdesign_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    allowed_blockers,
    family_identity,
    family_result_schema,
    geometry_restrictions,
    internal_ladder_hash,
    internal_strategy_lanes,
    lane_proof_policies,
    load_shear_overdesign_governs_contract,
    ranking_criteria,
    required_family_inputs,
    required_family_outputs,
    required_gates,
    shared_exclusions,
    terminal_rules,
    zero_shear_override,
)


REQUIRED_TOP_LEVEL_KEYS = {
    "schema",
    "family_identity",
    "classification",
    "zero_shear_override",
    "required_family_inputs",
    "family_result_schema",
    "internal_strategy_ladder",
    "geometry_restrictions",
    "lane_proof_policies",
    "terminal_rules",
    "blockers",
    "shared_exclusions",
    "lock_verification",
}

REQUIRED_INPUT_CATEGORIES = {
    "geometry",
    "reinforcement",
    "material_properties",
    "actions",
    "constraints",
}

REQUIRED_FAMILY_RESULT_FIELDS = {
    "status",
    "selected_recommendation",
    "candidate_repairs",
    "exhausted_reason",
    "evidence",
}

EXPECTED_CONTRACT_LANE_ORDER = [
    "SPACING_INCREASE",
    "BAR_SIZE_REDUCTION",
    "LEG_COUNT_REDUCTION",
    "LIGATURE_REMOVAL",
    "EXACT_STOP",
    "EXHAUSTED",
]

EXPECTED_RANKING_CRITERIA = [
    "target band achieved",
    "no unnecessary ligatures remain",
    "least reinforcement quantity",
    "constructability",
    "cost proxy",
]

REQUIRED_SHARED_EXCLUSIONS = {
    "CTA rendering",
    "CTA source precedence",
    "publication",
    "selected-family publication gate",
    "apply routing",
    "one-click orchestration",
    "visible wording",
    "user wording",
    "UI rendering",
    "session state",
    "debug rendering",
    "source precedence",
}

REQUIRED_GEOMETRY_PROHIBITIONS = {
    "b",
    "bw",
    "D",
    "beam_width",
    "beam_depth",
    "beam_width_mm",
    "beam_depth_mm",
}

ALLOWED_SHEAR_UPDATE_KEYS = {"s_lig", "lig_d", "lig_legs"}
EXPECTED_SPACING_SEARCH = [100, 125, 150, 175, 200, 250, 300]
EXPECTED_BAR_SIZE_SEARCH = ["N16", "N12", "N10"]
EXPECTED_LEG_COUNT_SEARCH = [6, 4, 2]


def _contains_all_text(values: list[Any], required_terms: list[str]) -> list[str]:
    text = "\n".join(str(value).lower() for value in values)
    return [term for term in required_terms if term.lower() not in text]


def _validate_contract_shape(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(contract.keys()))
    failures.extend(f"missing_top_level_key:{key}" for key in missing)
    if "publication" in contract:
        failures.append("publication_must_not_be_family_owned")
    if "runtime" in contract:
        failures.append("runtime_must_not_be_defined_in_contract_phase")

    identity = family_identity()
    if identity.get("family_id") != "SHEAR_OVERDESIGN_GOVERNS":
        failures.append("family_id_mismatch")
    if identity.get("package") != "design_brain.families.shear_overdesign_governs":
        failures.append("package_mismatch")
    if identity.get("legacy_delegate") != "design_brain.families.shear_cleanup.ShearCleanupFamily":
        failures.append("legacy_delegate_mismatch")
    if identity.get("public_api") != "evaluate_shear_overdesign_governs":
        failures.append("public_api_mismatch")

    classification = contract.get("classification") or {}
    missing_entry = _contains_all_text(
        list(classification.get("governs_when") or []) + [classification.get("entry_condition")],
        [
            "shear compliant",
            "reduction opportunity exists",
            "no underdesign family active",
            "outside efficiency target band",
            "unnecessary shear reinforcement exists",
        ],
    )
    failures.extend(f"classification_entry_missing:{term}" for term in missing_entry)
    missing_must_not = _contains_all_text(
        list(classification.get("must_not_govern_when") or []),
        ["bending underdesign", "shear underdesign", "combined bending and shear underdesign"],
    )
    failures.extend(f"classification_must_not_missing:{term}" for term in missing_must_not)

    override = zero_shear_override()
    override_text_values = (
        list(override.get("activates_when") or [])
        + list(override.get("must_not") or [])
        + [override.get("purpose")]
    )
    missing_override = _contains_all_text(
        override_text_values,
        ["V* = 0 or negligible", "ligatures exist", "beam contains design actions"],
    )
    failures.extend(f"zero_shear_override_missing:{term}" for term in missing_override)
    requires = override.get("requires") or {}
    if requires.get("negligible_shear_action") is not True:
        failures.append("zero_shear_override_negligible_shear_action_not_required")
    if requires.get("ligatures_exist") is not True:
        failures.append("zero_shear_override_ligatures_exist_not_required")
    if requires.get("design_actions_present") is not True:
        failures.append("zero_shear_override_design_actions_present_not_required")
    if override.get("family_cannot_terminate_solely_because_utilisation_is_zero") is not True:
        failures.append("zero_shear_can_terminate_solely_because_utilisation_zero")

    inputs = required_family_inputs()
    failures.extend(
        f"required_family_input_category_missing:{category}"
        for category in sorted(REQUIRED_INPUT_CATEGORIES - set(inputs))
    )
    for category in REQUIRED_INPUT_CATEGORIES:
        if category in inputs and not inputs[category]:
            failures.append(f"required_family_input_category_empty:{category}")

    result_schema = family_result_schema()
    if result_schema.get("result_type") != "FamilyResult":
        failures.append("family_result_schema_type_mismatch")
    result_fields = set(str(value) for value in result_schema.get("required_fields") or ())
    failures.extend(
        f"family_result_required_field_missing:{field}"
        for field in sorted(REQUIRED_FAMILY_RESULT_FIELDS - result_fields)
    )
    outputs = set(required_family_outputs())
    failures.extend(
        f"internal_strategy_required_output_missing:{field}"
        for field in sorted(REQUIRED_FAMILY_RESULT_FIELDS - outputs)
    )

    lanes = list(internal_strategy_lanes())
    lane_order = [str(lane.get("lane_id") or "") for lane in lanes]
    if lane_order != EXPECTED_CONTRACT_LANE_ORDER:
        failures.append("internal_strategy_lane_order_mismatch")
    indexes = [lane.get("lane_index") for lane in lanes]
    if indexes != list(range(len(lanes))):
        failures.append("internal_strategy_lane_indexes_not_contiguous")
    lane_by_id = {str(lane.get("lane_id") or ""): lane for lane in lanes}
    for lane in lanes:
        lane_id = str(lane.get("lane_id") or "")
        if not str(lane.get("purpose") or "").strip():
            failures.append(f"internal_strategy_lane_missing_purpose:{lane_id}")
        if not list(lane.get("required_evidence") or []):
            failures.append(f"internal_strategy_lane_missing_required_evidence:{lane_id}")
        allowed_update_keys = set(str(value) for value in lane.get("allowed_update_keys") or [])
        if allowed_update_keys and not allowed_update_keys <= ALLOWED_SHEAR_UPDATE_KEYS:
            failures.append(f"lane_allows_non_shear_update_keys:{lane_id}:{sorted(allowed_update_keys - ALLOWED_SHEAR_UPDATE_KEYS)}")
    if lane_by_id.get("LIGATURE_REMOVAL", {}).get("zero_shear_override_lane") is not True:
        failures.append("ligature_removal_not_marked_zero_shear_override_lane")
    if lane_by_id.get("EXACT_STOP", {}).get("output") != "EXACT_STOP":
        failures.append("exact_stop_output_mismatch")
    if lane_by_id.get("EXHAUSTED", {}).get("output") != "EXHAUSTED":
        failures.append("exhausted_output_mismatch")

    restrictions = geometry_restrictions()
    if restrictions.get("geometry_reduction_prohibited") is not True:
        failures.append("geometry_reduction_not_prohibited")
    prohibited = set(str(value) for value in restrictions.get("prohibited_update_keys") or [])
    failures.extend(
        f"geometry_prohibited_key_missing:{key}"
        for key in sorted(REQUIRED_GEOMETRY_PROHIBITIONS - prohibited)
    )
    allowed = set(str(value) for value in restrictions.get("allowed_update_keys") or [])
    if allowed != ALLOWED_SHEAR_UPDATE_KEYS:
        failures.append("geometry_restriction_allowed_update_keys_not_shear_only")

    policies = lane_proof_policies()
    spacing_policy = policies.get("spacing_increase") or {}
    if spacing_policy.get("lane_id") != "SPACING_INCREASE":
        failures.append("spacing_policy_lane_id_mismatch")
    if list(spacing_policy.get("spacing_search_mm") or []) != EXPECTED_SPACING_SEARCH:
        failures.append("spacing_policy_search_order_mismatch")
    if set(str(value) for value in spacing_policy.get("allowed_update_keys") or []) != {"s_lig"}:
        failures.append("spacing_policy_allowed_update_keys_mismatch")

    bar_policy = policies.get("bar_size_reduction") or {}
    if bar_policy.get("lane_id") != "BAR_SIZE_REDUCTION":
        failures.append("bar_size_policy_lane_id_mismatch")
    if list(bar_policy.get("bar_size_search") or []) != EXPECTED_BAR_SIZE_SEARCH:
        failures.append("bar_size_policy_search_order_mismatch")
    if bar_policy.get("restarts_spacing_search") is not True:
        failures.append("bar_size_policy_does_not_restart_spacing")

    leg_policy = policies.get("leg_count_reduction") or {}
    if leg_policy.get("lane_id") != "LEG_COUNT_REDUCTION":
        failures.append("leg_count_policy_lane_id_mismatch")
    if list(leg_policy.get("leg_count_search") or []) != EXPECTED_LEG_COUNT_SEARCH:
        failures.append("leg_count_policy_search_order_mismatch")
    if leg_policy.get("restarts_spacing_search") is not True:
        failures.append("leg_count_policy_does_not_restart_spacing")
    if leg_policy.get("restarts_bar_size_search") is not True:
        failures.append("leg_count_policy_does_not_restart_bar_size")

    removal_policy = policies.get("ligature_removal") or {}
    if removal_policy.get("lane_id") != "LIGATURE_REMOVAL":
        failures.append("ligature_removal_policy_lane_id_mismatch")
    if dict(removal_policy.get("canonical_update") or {}) != {"lig_legs": 0, "lig_d": 0, "s_lig": 0}:
        failures.append("ligature_removal_canonical_update_mismatch")

    terminal_policy = policies.get("terminal") or {}
    if terminal_policy.get("zero_shear_exhausted_forbidden_while_ligatures_remain_without_code_requirement") is not True:
        failures.append("terminal_policy_allows_zero_shear_exhausted_with_removable_ligatures")

    zero_policy = policies.get("zero_shear") or {}
    if (zero_policy.get("case_a") or {}).get("expected") != "family activates":
        failures.append("zero_shear_case_a_expected_activation_missing")
    if (zero_policy.get("case_b") or {}).get("expected") != "remove ligatures":
        failures.append("zero_shear_case_b_expected_removal_missing")
    if (zero_policy.get("case_c") or {}).get("expected") != "no optimisation required":
        failures.append("zero_shear_case_c_expected_no_optimisation_missing")

    geometry_policy = policies.get("geometry_restriction") or {}
    if geometry_policy.get("prohibits_width_reduction") is not True:
        failures.append("geometry_policy_does_not_prohibit_width_reduction")
    if geometry_policy.get("prohibits_depth_reduction") is not True:
        failures.append("geometry_policy_does_not_prohibit_depth_reduction")
    if set(str(value) for value in geometry_policy.get("allowed_update_keys") or []) != ALLOWED_SHEAR_UPDATE_KEYS:
        failures.append("geometry_policy_allowed_update_keys_mismatch")

    if list(ranking_criteria()) != EXPECTED_RANKING_CRITERIA:
        failures.append("ranking_criteria_order_mismatch")

    terminals = terminal_rules()
    if not isinstance(terminals.get("exact_stop"), dict) or terminals["exact_stop"].get("required") is not True:
        failures.append("exact_stop_rule_missing")
    if not isinstance(terminals.get("exhausted"), dict) or terminals["exhausted"].get("required") is not True:
        failures.append("exhausted_rule_missing")

    exclusions = set(shared_exclusions())
    failures.extend(f"shared_exclusion_missing:{field}" for field in sorted(REQUIRED_SHARED_EXCLUSIONS - exclusions))

    verification = contract.get("lock_verification") or {}
    for verifier in verification.get("required_verifiers") or []:
        if not (ROOT / str(verifier)).exists():
            failures.append(f"required_verifier_missing:{verifier}")
    if not allowed_blockers():
        failures.append("allowed_blockers_empty")
    if not required_gates():
        failures.append("required_gates_empty")

    return failures


def _validate_no_forbidden_source_movement() -> list[str]:
    failures: list[str] = []
    package_source = (ROOT / "design_brain" / "families" / "shear_overdesign_governs" / "__init__.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    contract_source = (ROOT / "design_brain" / "families" / "shear_overdesign_governs" / "contract.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    combined = f"{package_source}\n{contract_source}"
    forbidden = ["inputs_page", "streamlit", "st.session_state", "apply_resolved_candidate", "button_contract"]
    for term in forbidden:
        if term in combined:
            failures.append(f"forbidden_package_source_term:{term}")
    bending_hits = [term for term in ("bending_fail_governs", "BENDING_FAIL_GOVERNS") if term in combined]
    failures.extend(f"bending_reference_in_shear_overdesign_package:{term}" for term in bending_hits)
    return failures


def _write_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# SHEAR_OVERDESIGN_GOVERNS Contract Check",
        "",
        f"Status: {output.get('status')}",
        "",
        "## Contract",
        "",
        f"- contract_json: `{output.get('contract_path')}`",
        f"- family_id: `{output.get('family_identity', {}).get('family_id')}`",
        f"- internal_ladder_hash: `{output.get('internal_ladder_hash')}`",
        "",
        "## Lane Order",
        "",
    ]
    lines.extend(
        f"- Lane {lane.get('lane_index')}: `{lane.get('lane_id')}` - {lane.get('title')}"
        for lane in output.get("internal_strategy_lane_order") or []
    )
    lines.extend(["", "## Protected Rules", ""])
    lines.extend(
        [
            "- Zero-shear override requires negligible shear action, existing ligatures, and design actions.",
            "- Geometry reduction is prohibited; only `s_lig`, `lig_d`, and `lig_legs` are allowed update keys.",
        ]
    )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in output.get("failures") or []] or ["- none"])
    lines.extend(["", "## Output", "", f"- `{output.get('artifact')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")

    contract = load_shear_overdesign_governs_contract()
    failures = _validate_contract_shape(contract) + _validate_no_forbidden_source_movement()
    status = "PASS" if not failures else "FAIL"
    artifact = {
        "schema": "shear_overdesign_governs_contract_check.v1",
        "status": status,
        "contract_path": str(CONTRACT_PATH),
        "family_identity": family_identity(),
        "classification": contract.get("classification"),
        "zero_shear_override": zero_shear_override(),
        "required_family_inputs": {key: list(value) for key, value in required_family_inputs().items()},
        "family_result_schema": family_result_schema(),
        "internal_strategy_lane_order": [
            {
                "lane_index": lane.get("lane_index"),
                "lane_id": lane.get("lane_id"),
                "title": lane.get("title"),
            }
            for lane in internal_strategy_lanes()
        ],
        "internal_ladder_hash": internal_ladder_hash(),
        "ranking_criteria": list(ranking_criteria()),
        "required_family_outputs": list(required_family_outputs()),
        "geometry_restrictions": geometry_restrictions(),
        "lane_proof_policies": lane_proof_policies(),
        "terminal_rules": terminal_rules(),
        "shared_exclusions": list(shared_exclusions()),
        "allowed_blockers": list(allowed_blockers()),
        "required_gates": list(required_gates()),
        "failures": failures,
    }
    artifact_path = ARTIFACT_DIR / f"shear_overdesign_governs_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_governs_contract_check_{stamp}.md"
    artifact["artifact"] = str(artifact_path)
    artifact["report"] = str(report_path)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(artifact, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
