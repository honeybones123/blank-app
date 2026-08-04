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

from design_brain.families.serviceability_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    contract_hash,
    exact_stop_rules,
    exhausted_rules,
    family_identity,
    family_result_schema,
    geometry_rules,
    governing_checks,
    inputs_contract,
    invalid_before_ranking,
    lane_proof_policies,
    load_serviceability_governs_contract,
    ownership_contract,
    ranking_criteria,
    repair_ladder,
    required_gates,
    selection_boundary,
    serviceability_contract_lane_order,
    shared_exclusions,
    strength_protection,
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
    "success_contract",
    "governing_checks",
    "target_band",
    "repair_ladder",
    "strength_protection",
    "geometry_rules",
    "exact_stop",
    "exhausted",
    "ranking",
    "lane_proof_policies",
    "shared_exclusions",
    "lock_verification",
}
EXPECTED_LANE_ORDER = (
    "BOTTOM_REINFORCEMENT_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "COMBINED_GEOMETRY_REINFORCEMENT_SEARCH",
    "EXACT_STOP",
    "EXHAUSTED",
)
EXPECTED_RANKING = (
    "serviceability compliance achieved",
    "smallest geometry increase",
    "smallest reinforcement increase",
    "constructability",
    "cost proxy",
)
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
    for forbidden in ("publication", "cta_contract", "apply_routing"):
        if forbidden in contract:
            failures.append(f"forbidden_top_level_contract_section:{forbidden}")
    identity = family_identity()
    if identity.get("family_id") != "SERVICEABILITY_GOVERNS":
        failures.append("family_id_mismatch")
    if identity.get("package") != "design_brain.families.serviceability_governs":
        failures.append("package_mismatch")
    boundary = selection_boundary()
    failures.extend(
        f"selection_boundary_missing:{term}"
        for term in _contains_all(
            list(boundary.get("must_not") or []),
            ["perform classification", "choose another family", "override family selection", "perform family arbitration"],
        )
    )
    if "SERVICEABILITY_GOVERNS" not in str(boundary.get("starts_after") or ""):
        failures.append("selection_boundary_start_mismatch")
    inputs = inputs_contract()
    required_groups = set(str(value) for value in inputs.get("required_groups") or [])
    for group in ("geometry", "reinforcement", "material_properties", "actions", "constraints"):
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
    ownership = ownership_contract()
    failures.extend(
        f"ownership_family_missing:{term}"
        for term in _contains_all(
            list(ownership.get("family_owns") or []),
            [
                "serviceability failure detection",
                "serviceability candidate generation",
                "serviceability repair ladder execution",
                "serviceability recommendation selection",
                "serviceability exact stop proof",
                "serviceability exhausted proof",
                "serviceability blockers",
            ],
        )
    )
    failures.extend(
        f"family_blocker_missing:{term}"
        for term in _contains_all(
            list(ownership.get("family_blockers_owned") or []),
            ["geometry limits", "constructability limits", "maximum practical beam dimensions", "detailing constraints"],
        )
    )
    checks = governing_checks()
    failures.extend(
        f"governing_check_missing:{term}"
        for term in _contains_all(
            list(checks.get("family_owns") or []),
            ["deflection checks", "crack control checks", "serviceability utilisation metrics"],
        )
    )
    success = success_contract()
    failures.extend(
        f"success_requirement_missing:{term}"
        for term in _contains_all(
            list(success.get("valid_serviceability_repair_requires") or []),
            ["serviceability improves", "serviceability becomes compliant", "strength remains compliant"],
        )
    )
    band = target_band()
    if band.get("serviceability_utilisation_upper") != 1.0:
        failures.append("serviceability_utilisation_upper_mismatch")
    if serviceability_contract_lane_order() != EXPECTED_LANE_ORDER:
        failures.append("serviceability_lane_order_mismatch")
    ladder = repair_ladder()
    restart_after = dict(ladder.get("restart_after") or {})
    if "BOTTOM_REINFORCEMENT_INCREASE" not in restart_after.get("DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH", []):
        failures.append("depth_restart_rule_missing")
    if "BOTTOM_REINFORCEMENT_INCREASE" not in restart_after.get("WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH", []):
        failures.append("width_restart_rule_missing")
    strength = strength_protection()
    failures.extend(
        f"strength_protection_missing:{term}"
        for term in _contains_all(
            list(strength.get("invalid_before_ranking") or []),
            ["bending failure created", "shear failure created", "strength compliance not maintained"],
        )
    )
    geometry = geometry_rules()
    failures.extend(
        f"geometry_rule_missing:{term}"
        for term in _contains_all(
            list(geometry.get("requires") or []),
            ["all geometry constraints satisfied", "constructability maintained", "beam proportion limits maintained"],
        )
    )
    failures.extend(
        f"exact_stop_missing:{term}"
        for term in _contains_all(
            list(exact_stop_rules().get("allowed_when") or []),
            ["serviceability compliant", "strength compliant", "no higher-ranked"],
        )
    )
    failures.extend(
        f"exhausted_missing:{term}"
        for term in _contains_all(
            list(exhausted_rules().get("requires") or []),
            ["all ladder branches attempted", "no valid compliant repair exists", "specific blocker"],
        )
    )
    if tuple(ranking_criteria()) != EXPECTED_RANKING:
        failures.append("ranking_criteria_order_mismatch")
    failures.extend(
        f"invalid_before_ranking_missing:{term}"
        for term in _contains_all(
            list(invalid_before_ranking()),
            ["candidate creates bending failure", "candidate creates shear failure"],
        )
    )
    policies = lane_proof_policies()
    for section in ("repair_validity", "ladder_order", "terminal"):
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
    source = (ROOT / "design_brain" / "families" / "serviceability_governs" / "contract.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    forbidden = ["inputs_page", "streamlit", "st.session_state", "button_contract", "publication"]
    return [f"forbidden_contract_source_term:{term}" for term in forbidden if term in source]


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"serviceability_governs_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_governs_contract_check_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SERVICEABILITY_GOVERNS Contract Check",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                f"- contract_hash: `{snapshot['contract_hash']}`",
                f"- lane_order: `{snapshot['lane_order']}`",
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    contract = load_serviceability_governs_contract()
    failures = _validate_contract(contract) + _validate_source_clean()
    snapshot = {
        "schema": "serviceability_governs_contract_check.v1",
        "result": "PASS" if not failures else "FAIL",
        "contract_path": str(CONTRACT_PATH),
        "contract_hash": contract_hash(),
        "family_identity": family_identity(),
        "lane_order": list(serviceability_contract_lane_order()),
        "ranking_criteria": list(ranking_criteria()),
        "shared_exclusions": list(shared_exclusions()),
        "required_gates": list(required_gates()),
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("SERVICEABILITY_GOVERNS contract check FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SERVICEABILITY_GOVERNS contract check PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
