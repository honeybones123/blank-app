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

from design_brain.families.shear_fail_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    allowed_blockers,
    expected_ladder_snapshots,
    family_identity,
    family_result_schema,
    internal_ladder_hash,
    internal_strategy_lanes,
    load_shear_fail_governs_contract,
    ranking_criteria,
    required_family_inputs,
    required_family_outputs,
    required_gates,
    required_locked_snapshot_fields,
    shared_exclusions,
)


REQUIRED_TOP_LEVEL_KEYS = {
    "schema",
    "family_identity",
    "classification",
    "required_family_inputs",
    "family_result_schema",
    "internal_strategy_ladder",
    "repair_ladder",
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
    "SPACING_REDUCTION",
    "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "BAR_SIZE_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "EXACT_STOP",
    "EXHAUSTED",
    "NO_VALID_REPAIR",
]

EXPECTED_RANKING_CRITERIA = [
    "target band achieved",
    "smallest geometry change",
    "smallest reinforcement increase",
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
    "UI rendering",
    "session state",
    "debug rendering",
}


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _source_contains(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    return needle in path.read_text(encoding="utf-8", errors="replace")


def _latest_locked_artifact() -> Path | None:
    artifacts = sorted(
        ARTIFACT_DIR.glob("shear_fail_governs_locked_regression_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return artifacts[0] if artifacts else None


def _validate_contract_shape(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(contract.keys()))
    failures.extend(f"missing_top_level_key:{key}" for key in missing)
    if "publication" in contract:
        failures.append("publication_must_not_be_family_owned")

    identity = family_identity()
    if identity.get("family_id") != "SHEAR_FAIL_GOVERNS":
        failures.append("family_id_mismatch")
    if identity.get("package") != "design_brain.families.shear_fail_governs":
        failures.append("package_mismatch")
    if "legacy_delegate" in identity:
        failures.append("legacy_delegate_present")
    if "public_api" in identity:
        failures.append("public_api_present")

    classification = contract.get("classification") or {}
    if classification.get("entry_condition") != "shear underdesign governs":
        failures.append("entry_condition_mismatch")

    inputs = required_family_inputs()
    input_categories = set(inputs)
    failures.extend(
        f"required_family_input_category_missing:{category}"
        for category in sorted(REQUIRED_INPUT_CATEGORIES - input_categories)
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
    for lane in lanes:
        lane_id = str(lane.get("lane_id") or "")
        if not str(lane.get("purpose") or "").strip():
            failures.append(f"internal_strategy_lane_missing_purpose:{lane_id}")
        if not list(lane.get("required_evidence") or []):
            failures.append(f"internal_strategy_lane_missing_required_evidence:{lane_id}")
    lane_by_id = {str(lane.get("lane_id") or ""): lane for lane in lanes}
    if lane_by_id.get("DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH", {}).get("success_transition") != "SPACING_REDUCTION":
        failures.append("depth_increase_does_not_restart_reinforcement_search")
    if lane_by_id.get("WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH", {}).get("success_transition") != "SPACING_REDUCTION":
        failures.append("width_increase_does_not_restart_reinforcement_search")
    if lane_by_id.get("LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH", {}).get("success_transition") != "SPACING_REDUCTION":
        failures.append("leg_count_increase_does_not_restart_reinforcement_search")
    if lane_by_id.get("EXACT_STOP", {}).get("output") != "EXACT_STOP":
        failures.append("exact_stop_output_mismatch")
    if lane_by_id.get("EXHAUSTED", {}).get("output") != "EXHAUSTED":
        failures.append("exhausted_output_mismatch")
    if lane_by_id.get("NO_VALID_REPAIR", {}).get("output") != "NO_VALID_REPAIR":
        failures.append("no_valid_repair_output_mismatch")

    if list(ranking_criteria()) != EXPECTED_RANKING_CRITERIA:
        failures.append("ranking_criteria_order_mismatch")

    exclusions = set(shared_exclusions())
    failures.extend(f"shared_exclusion_missing:{field}" for field in sorted(REQUIRED_SHARED_EXCLUSIONS - exclusions))

    verification = contract.get("lock_verification") or {}
    for verifier in verification.get("required_verifiers") or []:
        if not (ROOT / str(verifier)).exists():
            failures.append(f"required_verifier_missing:{verifier}")

    if not required_locked_snapshot_fields():
        failures.append("locked_snapshot_fields_empty")
    if not allowed_blockers():
        failures.append("allowed_blockers_empty")
    if not required_gates():
        failures.append("required_gates_empty")
    if set(verification.get("required_snapshots") or []) != set(expected_ladder_snapshots().keys()):
        failures.append("required_snapshots_do_not_match_expected_ladder_snapshots")

    blocked_not_top_level = set((contract.get("blockers") or {}).get("not_top_level_families") or [])
    known_governing_families = {
        "BENDING_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "BENDING_AND_SHEAR_FAIL_GOVERN",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "LOCKED_NO_REPAIR",
        "EXACT_STOP_PROVEN",
        "TARGET_BAND_REACHED",
    }
    overlap = sorted(str(value) for value in blocked_not_top_level if str(value).upper() in known_governing_families)
    failures.extend(f"blocked_concept_declared_top_level_family:{value}" for value in overlap)
    return failures


def _validate_legacy_locked_regression_source() -> list[str]:
    failures: list[str] = []
    source_path = ROOT / "tools" / "verification" / "families" / "shear_fail_governs_locked_regression.py"
    if not _source_contains(source_path, "load_shear_fail_governs_contract") and not _source_contains(source_path, "required_locked_snapshot_fields"):
        failures.append("legacy_locked_regression_does_not_load_contract")
    if "EXPECTED_UNLOCKED_LADDER_HASH" in source_path.read_text(encoding="utf-8", errors="replace"):
        failures.append("legacy_locked_regression_still_hardcodes_old_expected_hash_constants")
    return failures


def _validate_runtime_authority_source() -> list[str]:
    failures: list[str] = []
    runtime_path = ROOT / "design_brain" / "families" / "shear_fail_governs" / "runtime.py"
    family_path = ROOT / "design_brain" / "families" / "shear_fail.py"
    package_path = ROOT / "design_brain" / "families" / "shear_fail_governs" / "__init__.py"
    if not _source_contains(runtime_path, "def run_shear_fail_governs_ladder_runtime"):
        failures.append("runtime_authority_function_missing")
    if not _source_contains(runtime_path, "load_shear_fail_governs_contract"):
        failures.append("runtime_does_not_load_contract")
    if not _source_contains(family_path, "run_shear_fail_governs_ladder_runtime"):
        failures.append("family_specs_not_runtime_driven")
    if not _source_contains(family_path, "runtime_authority"):
        failures.append("family_specs_missing_runtime_authority_evidence")
    if not _source_contains(package_path, "run_shear_fail_governs_ladder_runtime"):
        failures.append("package_runtime_export_missing")
    if _source_contains(package_path, "evaluate_" + "shear_fail_governs"):
        failures.append("deleted_compatibility_api_still_present")
    return failures


def _write_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# SHEAR_FAIL_GOVERNS Contract Check",
        "",
        f"Status: {output.get('status')}",
        "",
        "## Contract",
        "",
        f"- contract_json: `{output.get('contract_path')}`",
        f"- legacy_locked_regression_artifact: `{output.get('legacy_locked_regression_artifact')}`",
        "",
        "## Checked Source Of Truth",
        "",
        "- JSON contract loaded through `contract.py`",
        "- lock entry condition, required inputs, FamilyResult schema, strategy ladder, ranking criteria, and ownership exclusions validated",
        "- post-cutover contract runtime authority validated",
        "- legacy pre-cutover locked regression is retained as historical evidence only and is not an authority gate",
        "",
        "## Lock Contract",
        "",
        f"- entry_condition: `{output.get('entry_condition')}`",
        f"- internal_ladder_hash: `{output.get('internal_ladder_hash')}`",
        "",
        "Lane order:",
        "",
    ]
    for lane in output.get("internal_strategy_lane_order") or []:
        lines.append(f"- Lane {lane.get('lane_index')}: `{lane.get('lane_id')}` - {lane.get('title')}")
    lines.extend([
        "",
        "Ranking criteria:",
        "",
    ])
    lines.extend([f"- {criterion}" for criterion in output.get("ranking_criteria") or []])
    lines.extend([
        "",
        "Shared/page-owned exclusions:",
        "",
    ])
    lines.extend([f"- {exclusion}" for exclusion in output.get("shared_exclusions") or []])
    lines.extend([
        "",
        "## Failures",
        "",
    ])
    lines.extend([f"- {failure}" for failure in output.get("failures") or []] or ["- none"])
    lines.extend(["", "## Output", "", f"- `{output.get('artifact')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")

    contract = load_shear_fail_governs_contract()
    legacy_artifact_path = _latest_locked_artifact()

    failures = (
        _validate_contract_shape(contract)
        + _validate_legacy_locked_regression_source()
        + _validate_runtime_authority_source()
    )

    status = "PASS" if not failures else "FAIL"
    artifact = {
        "schema": "shear_fail_governs_contract_check.v1",
        "status": status,
        "contract_path": str(CONTRACT_PATH),
        "family_identity": family_identity(),
        "entry_condition": (contract.get("classification") or {}).get("entry_condition"),
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
        "shared_exclusions": list(shared_exclusions()),
        "required_locked_snapshot_fields": list(required_locked_snapshot_fields()),
        "allowed_blockers": list(allowed_blockers()),
        "required_gates": list(required_gates()),
        "runtime_authority": "run_shear_fail_governs_ladder_runtime",
        "legacy_locked_regression_authority": "historical_only_not_final_lock_authority",
        "legacy_locked_regression_artifact": str(legacy_artifact_path) if legacy_artifact_path else None,
        "failures": failures,
    }
    artifact_path_out = ARTIFACT_DIR / f"shear_fail_governs_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_governs_contract_check_{stamp}.md"
    artifact["artifact"] = str(artifact_path_out)
    artifact["report"] = str(report_path)
    artifact_path_out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(artifact, report_path)
    print(f"{status}: {artifact_path_out}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
