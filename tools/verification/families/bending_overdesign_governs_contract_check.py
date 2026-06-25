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

from design_brain.families.bending_overdesign_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    allowed_blockers,
    family_identity,
    family_result_schema,
    geometry_rules,
    internal_ladder_hash,
    internal_strategy_lanes,
    lane_proof_policies,
    load_bending_overdesign_governs_contract,
    minimum_reinforcement_geometry_relief_rules,
    minimum_reinforcement_rules,
    ranking_criteria,
    required_family_inputs,
    required_family_outputs,
    required_gates,
    shared_exclusions,
)


REQUIRED_TOP_LEVEL_KEYS = {
    "schema",
    "family_identity",
    "classification",
    "required_family_inputs",
    "family_result_schema",
    "internal_strategy_ladder",
    "minimum_reinforcement",
    "geometry_rules",
    "lane_proof_policies",
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
    "BOTTOM_REINFORCEMENT_REDUCTION",
    "LAYER_REDUCTION",
    "WIDTH_REDUCTION",
    "DEPTH_REDUCTION",
    "EXACT_STOP",
    "EXHAUSTED",
]

EXPECTED_RANKING_CRITERIA = [
    "target band achieved",
    "smallest reinforcement quantity",
    "smallest beam volume",
    "constructability",
    "cost proxy",
]

REQUIRED_SHARED_EXCLUSIONS = {
    "CTA generation",
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

ALLOWED_REINFORCEMENT_UPDATE_KEYS = {
    "bot1_count",
    "db_bot_1",
    "bot2_count",
    "db_bot_2",
    "bot_row_count",
    "bot_row_1_bars",
    "bot_row_1_dia",
    "bot_row_2_bars",
    "bot_row_2_dia",
}

ALLOWED_GEOMETRY_UPDATE_KEYS = {
    "b",
    "bw",
    "D",
    "beam_width",
    "beam_depth",
    "beam_width_mm",
    "beam_depth_mm",
}


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
    if identity.get("family_id") != "BENDING_OVERDESIGN_GOVERNS":
        failures.append("family_id_mismatch")
    if identity.get("package") != "design_brain.families.bending_overdesign_governs":
        failures.append("package_mismatch")
    if identity.get("legacy_delegate") != "design_brain.families.bending_cleanup.BendingCleanupFamily":
        failures.append("legacy_delegate_mismatch")
    if identity.get("public_api") != "evaluate_bending_overdesign_governs":
        failures.append("public_api_mismatch")

    classification = contract.get("classification") or {}
    missing_entry = _contains_all_text(
        list(classification.get("governs_when") or []) + [classification.get("entry_condition")],
        [
            "bending passes",
            "no underdesign family",
            "valid optimisation opportunity",
            "outside efficiency target band",
        ],
    )
    failures.extend(f"classification_entry_missing:{term}" for term in missing_entry)
    missing_must_not = _contains_all_text(
        list(classification.get("must_not_govern_when") or []),
        ["bending underdesign", "shear underdesign", "combined bending and shear underdesign"],
    )
    failures.extend(f"classification_must_not_missing:{term}" for term in missing_must_not)

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
    reinforcement_keys = set(str(value) for value in lane_by_id.get("BOTTOM_REINFORCEMENT_REDUCTION", {}).get("allowed_update_keys") or [])
    if not reinforcement_keys or not reinforcement_keys <= ALLOWED_REINFORCEMENT_UPDATE_KEYS:
        failures.append("bottom_reinforcement_lane_allowed_update_keys_mismatch")
    layer_keys = set(str(value) for value in lane_by_id.get("LAYER_REDUCTION", {}).get("allowed_update_keys") or [])
    if not layer_keys or not layer_keys <= ALLOWED_REINFORCEMENT_UPDATE_KEYS:
        failures.append("layer_reduction_lane_allowed_update_keys_mismatch")
    width_keys = set(lane_by_id.get("WIDTH_REDUCTION", {}).get("allowed_update_keys") or [])
    if not {"b", "bw"} <= width_keys or not width_keys <= ({"b", "bw"} | ALLOWED_REINFORCEMENT_UPDATE_KEYS):
        failures.append("width_reduction_allowed_update_keys_mismatch")
    if set(lane_by_id.get("DEPTH_REDUCTION", {}).get("allowed_update_keys") or []) != {"D", "beam_depth"}:
        failures.append("depth_reduction_allowed_update_keys_mismatch")
    if lane_by_id.get("WIDTH_REDUCTION", {}).get("restart_reinforcement_search") is not True:
        failures.append("width_reduction_does_not_restart_reinforcement_search")
    if lane_by_id.get("DEPTH_REDUCTION", {}).get("restart_reinforcement_search") is not True:
        failures.append("depth_reduction_does_not_restart_reinforcement_search")
    if lane_by_id.get("EXACT_STOP", {}).get("output") != "EXACT_STOP":
        failures.append("exact_stop_output_mismatch")
    if lane_by_id.get("EXHAUSTED", {}).get("output") != "EXHAUSTED":
        failures.append("exhausted_output_mismatch")

    if list(ranking_criteria()) != EXPECTED_RANKING_CRITERIA:
        failures.append("ranking_criteria_order_mismatch")

    min_reo = minimum_reinforcement_rules()
    if min_reo.get("hard_boundary") is not True:
        failures.append("minimum_reinforcement_not_hard_boundary")
    if min_reo.get("as_provided_must_be_greater_than_or_equal_to_as_min") is not True:
        failures.append("minimum_reinforcement_as_gte_as_min_missing")
    min_reo_text = "\n".join(
        str(value)
        for value in (
            list(min_reo.get("discard_before_ranking_when") or [])
            + list(min_reo.get("valid_blockers") or [])
            + list(min_reo.get("specific_blocker_evidence_required") or [])
        )
    )
    for term in ("As < As_min", "As = As_min", "lightest compliant", "minimum reinforcement", "Ast-min", "width-reduction"):
        if term.lower() not in min_reo_text.lower():
            failures.append(f"minimum_reinforcement_rule_missing:{term}")
    min_relief = minimum_reinforcement_geometry_relief_rules()
    if not min_relief:
        failures.append("minimum_reinforcement_geometry_relief_rules_missing")
    relief_text = "\n".join(
        str(value)
        for value in (
            list(min_relief.get("required_when") or [])
            + list(min_relief.get("must_evaluate") or [])
            + list(min_relief.get("exhausted_only_when") or [])
            + list(min_relief.get("visible_blocker_terms") or [])
        )
    )
    for term in ("width reduction", "As_min", "bottom reinforcement", "Ast-min", "minimum bending reinforcement"):
        if term.lower() not in relief_text.lower():
            failures.append(f"minimum_reinforcement_geometry_relief_missing:{term}")

    geometry = geometry_rules()
    if geometry.get("geometry_reduction_allowed") is not True:
        failures.append("geometry_reduction_not_allowed_by_contract")
    geometry_allowed = set(str(value) for value in geometry.get("allowed_update_keys") or [])
    failures.extend(
        f"geometry_allowed_key_missing:{key}"
        for key in sorted(ALLOWED_GEOMETRY_UPDATE_KEYS - geometry_allowed)
    )
    if geometry.get("width_increment_mm") != -25:
        failures.append("width_increment_not_minus_25")
    if geometry.get("depth_increment_mm") != -25:
        failures.append("depth_increment_not_minus_25")
    restart = set(str(value) for value in geometry.get("restart_after_geometry_reduction") or [])
    if {"bottom reinforcement search", "layer search"} - restart:
        failures.append("geometry_reduction_restart_rules_missing")
    geometry_requires = "\n".join(str(value) for value in geometry.get("requires") or [])
    for term in ("bending remains compliant", "geometry constraints", "beam proportion", "constructability", "As_min relief"):
        if term.lower() not in geometry_requires.lower():
            failures.append(f"geometry_requirement_missing:{term}")

    policies = lane_proof_policies()
    bottom_policy = policies.get("bottom_reinforcement_reduction") or {}
    if bottom_policy.get("lane_id") != "BOTTOM_REINFORCEMENT_REDUCTION":
        failures.append("bottom_policy_lane_id_mismatch")
    if list(bottom_policy.get("example_sequence") or []) != ["5-N24", "4-N24", "4-N20", "3-N24", "3-N20"]:
        failures.append("bottom_policy_example_sequence_mismatch")
    bottom_terminal = "\n".join(str(value) for value in bottom_policy.get("terminates_when") or [])
    if "As < As_min".lower() not in bottom_terminal.lower():
        failures.append("bottom_policy_does_not_terminate_at_min_reinforcement")

    layer_policy = policies.get("layer_reduction") or {}
    if layer_policy.get("lane_id") != "LAYER_REDUCTION":
        failures.append("layer_policy_lane_id_mismatch")
    if list(layer_policy.get("search") or []) != ["multi-layer", "single-layer"]:
        failures.append("layer_policy_search_order_mismatch")

    for policy_key, lane_id in (("width_reduction", "WIDTH_REDUCTION"), ("depth_reduction", "DEPTH_REDUCTION")):
        policy = policies.get(policy_key) or {}
        if policy.get("lane_id") != lane_id:
            failures.append(f"{policy_key}_policy_lane_id_mismatch")
        if policy.get("increment_mm") != -25:
            failures.append(f"{policy_key}_policy_increment_mismatch")
        if policy.get("restarts_bottom_reinforcement_search") is not True:
            failures.append(f"{policy_key}_policy_does_not_restart_bottom_reinforcement")
        if policy.get("restarts_layer_search") is not True:
            failures.append(f"{policy_key}_policy_does_not_restart_layer")
    width_policy = policies.get("width_reduction") or {}
    if width_policy.get("minimum_reinforcement_relief") is not True:
        failures.append("width_policy_missing_minimum_reinforcement_relief")
    width_requirements = set(str(value) for value in width_policy.get("restarted_candidate_requirements") or [])
    expected_width_requirements = {
        "width-only candidate",
        "width plus restarted bottom reinforcement candidate",
        "width plus restarted layer reduction candidate",
    }
    failures.extend(
        f"width_policy_restarted_requirement_missing:{requirement}"
        for requirement in sorted(expected_width_requirements - width_requirements)
    )

    min_cases = policies.get("minimum_reinforcement_cases") or {}
    expected_min_cases = {
        "case_a": "optimisation may continue",
        "case_b": "reinforcement reduction branch stops",
        "case_c": "candidate rejected",
        "case_d": "minimum reinforcement blocker evidence published",
        "case_e": "candidate never appears in ranked recommendations",
    }
    for case_id, expected in expected_min_cases.items():
        if (min_cases.get(case_id) or {}).get("expected") != expected:
            failures.append(f"minimum_reinforcement_{case_id}_expected_mismatch")

    terminal = policies.get("terminal") or {}
    terminal_text = "\n".join(
        str(value)
        for value in (list(terminal.get("exact_stop_allowed_when") or []) + list(terminal.get("exhausted_requires") or []))
    )
    for term in ("target band reached", "no higher-ranked", "all optimisation branches attempted", "specific blocker evidence"):
        if term.lower() not in terminal_text.lower():
            failures.append(f"terminal_policy_missing:{term}")

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
    package_source = (ROOT / "design_brain" / "families" / "bending_overdesign_governs" / "__init__.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    contract_source = (ROOT / "design_brain" / "families" / "bending_overdesign_governs" / "contract.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    combined = f"{package_source}\n{contract_source}"
    forbidden = [
        "inputs_page",
        "streamlit",
        "st.session_state",
        "apply_resolved_candidate",
        "button_contract",
    ]
    for term in forbidden:
        if term in combined:
            failures.append(f"forbidden_package_source_term:{term}")
    other_family_hits = [
        term
        for term in (
            "bending_fail_governs",
            "BENDING_FAIL_GOVERNS",
            "shear_fail_governs",
            "SHEAR_FAIL_GOVERNS",
            "shear_overdesign_governs",
            "SHEAR_OVERDESIGN_GOVERNS",
        )
        if term in combined
    ]
    failures.extend(f"other_family_reference_in_bending_overdesign_package:{term}" for term in other_family_hits)
    return failures


def _write_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_OVERDESIGN_GOVERNS Contract Check",
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
            "- `As >= As_min` is a hard boundary and candidates below minimum reinforcement are discarded before ranking.",
            "- Width/depth reductions are contract lanes only when bending, geometry, proportion, and constructability remain compliant.",
            "- Shared CTA/publication/apply/UI/session/debug ownership remains outside the family.",
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

    contract = load_bending_overdesign_governs_contract()
    failures = _validate_contract_shape(contract) + _validate_no_forbidden_source_movement()
    status = "PASS" if not failures else "FAIL"
    artifact = {
        "schema": "bending_overdesign_governs_contract_check.v1",
        "status": status,
        "contract_path": str(CONTRACT_PATH),
        "family_identity": family_identity(),
        "classification": contract.get("classification"),
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
        "minimum_reinforcement": minimum_reinforcement_rules(),
        "geometry_rules": geometry_rules(),
        "lane_proof_policies": lane_proof_policies(),
        "shared_exclusions": list(shared_exclusions()),
        "allowed_blockers": list(allowed_blockers()),
        "required_gates": list(required_gates()),
        "failures": failures,
    }
    artifact_path = ARTIFACT_DIR / f"bending_overdesign_governs_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_overdesign_governs_contract_check_{stamp}.md"
    artifact["artifact"] = str(artifact_path)
    artifact["report"] = str(report_path)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(artifact, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
