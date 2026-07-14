from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.bending_fail_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    allowed_blockers,
    calculate_internal_ladder_hash,
    depth_width_rule,
    expected_ladder_snapshots,
    family_identity,
    global_family_rules,
    internal_ladder_hash,
    internal_strategy_ladder,
    internal_strategy_lanes,
    load_bending_fail_governs_contract,
    required_family_inputs,
    required_family_outputs,
    required_gates,
    required_locked_snapshot_fields,
    shared_exclusions,
    utilisation_definitions,
)


REQUIRED_TOP_LEVEL_KEYS = {
    "schema",
    "family_identity",
    "classification",
    "utilisation_definitions",
    "family_objective",
    "required_family_inputs",
    "depth_width_rule",
    "internal_strategy_ladder",
    "repair_ladder",
    "blockers",
    "shared_exclusions",
    "publication",
    "lock_verification",
}

EXPECTED_UTILISATION_DEFINITIONS = {
    "FAIL": {"operator": ">", "threshold": 1.0},
    "TARGET": {
        "lower_operator": ">=",
        "lower_threshold": 0.85,
        "upper_operator": "<=",
        "upper_threshold": 1.0,
    },
    "OVERDESIGNED": {"operator": "<", "threshold": 0.85},
}

REQUIRED_FAMILY_INPUTS = {
    "bending utilisation",
    "shear utilisation",
    "serviceability state",
    "geometry/detailing state",
    "beam width",
    "beam depth",
    "depth/width ratio",
    "reinforcement arrangement",
    "spacing",
    "cover",
    "congestion status",
    "geometry locked status",
    "reinforcement locked status",
    "target band limits",
    "exact stop status",
}

REQUIRED_FAMILY_OUTPUTS = {
    "family_id",
    "selected_strategy_lane",
    "ladder_trace",
    "selected_recommendation",
    "accepted_lane_evidence",
    "rejected_lane_evidence",
    "final_bending_utilisation",
    "target_band_status",
    "exact_stop_status",
    "blocked_reason",
    "blocked_reason_source",
    "terminal_status",
    "repair_blocked",
    "internal_cap_only",
    "hard_blocker_proven",
    "contract_strategy_exhaustion_proven",
    "contract_strategies_checked",
    "contract_strategies_blocked",
    "contract_strategies_remaining",
    "implementation_caps_hit",
    "geometry_locks_used",
    "project_constraints_used",
    "detailing_constraints_used",
    "repair_reason_proof",
    "cta_intent_proof",
    "contract_version",
    "ladder_hash",
}

REQUIRED_SHARED_EXCLUSIONS = {
    "family classification",
    "CTA rendering",
    "CTA source precedence",
    "publication gate",
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


def _run_locked_regression() -> dict[str, Any]:
    command = [sys.executable, "tools/verification/families/bending_fail_governs_locked_regression.py"]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    artifact = None
    for line in str(completed.stdout or "").splitlines():
        text = line.strip()
        if text.startswith("PASS:") or text.startswith("FAIL:"):
            artifact = text.split(":", 1)[1].strip()
            break
    artifact_path = Path(artifact) if artifact else None
    if artifact_path is not None and not artifact_path.is_absolute():
        artifact_path = ROOT / artifact_path
    return {
        "command": command,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "artifact": str(artifact_path) if artifact_path else None,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
    }


def _source_contains(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    return needle in path.read_text(encoding="utf-8", errors="replace")


def _latest_locked_artifact() -> Path | None:
    artifacts = sorted(
        ARTIFACT_DIR.glob("bending_fail_governs_locked_regression_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return artifacts[0] if artifacts else None


def _validate_contract_shape(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(contract.keys()))
    failures.extend(f"missing_top_level_key:{key}" for key in missing)

    identity = family_identity()
    if identity.get("family_id") != "BENDING_FAIL_GOVERNS":
        failures.append("family_id_mismatch")
    if identity.get("package") != "design_brain.families.bending_fail_governs":
        failures.append("package_mismatch")
    if "legacy_delegate" in identity:
        failures.append("legacy_delegate_present")
    if "public_api" in identity:
        failures.append("public_api_present")

    definitions = utilisation_definitions()
    if set(definitions) != set(EXPECTED_UTILISATION_DEFINITIONS):
        failures.append("utilisation_definitions_keys_mismatch")
    for band_name, expected in EXPECTED_UTILISATION_DEFINITIONS.items():
        actual = definitions.get(band_name) or {}
        for key, expected_value in expected.items():
            value = actual.get(key)
            if isinstance(expected_value, float):
                try:
                    actual_value = float(value)
                except (TypeError, ValueError):
                    failures.append(f"utilisation_definition_invalid:{band_name}:{key}")
                    continue
                if actual_value != expected_value:
                    failures.append(f"utilisation_definition_mismatch:{band_name}:{key}")
            elif value != expected_value:
                failures.append(f"utilisation_definition_mismatch:{band_name}:{key}")

    inputs = set(required_family_inputs())
    failures.extend(f"required_family_input_missing:{field}" for field in sorted(REQUIRED_FAMILY_INPUTS - inputs))

    ratio_rule = depth_width_rule()
    if float(ratio_rule.get("maximum_preferred_ratio") or 0.0) != 2.0:
        failures.append("depth_width_ratio_limit_mismatch")
    ratio_outcomes = set(str(value) for value in ratio_rule.get("when_ratio_exceeds_limit") or [])
    if "depth growth strategy becomes blocked" not in ratio_outcomes:
        failures.append("depth_width_rule_missing_depth_block")
    if "width strategy becomes preferred" not in ratio_outcomes:
        failures.append("depth_width_rule_missing_width_preferred")

    ladder = internal_strategy_ladder()
    if ladder.get("family_id") != "BENDING_FAIL_GOVERNS":
        failures.append("internal_strategy_ladder_family_id_mismatch")
    if not bool(ladder.get("one_family_one_contract_one_ladder")):
        failures.append("one_family_one_contract_one_ladder_not_true")
    if internal_ladder_hash() != calculate_internal_ladder_hash():
        failures.append("internal_ladder_hash_mismatch")
    lanes = list(internal_strategy_lanes())
    if len(lanes) != 8:
        failures.append("internal_strategy_lane_count_mismatch")
    indexes = [lane.get("lane_index") for lane in lanes]
    if indexes != list(range(len(lanes))):
        failures.append("internal_strategy_lane_indexes_not_contiguous")
    lane_ids = [str(lane.get("lane_id") or "") for lane in lanes]
    if len(lane_ids) != len(set(lane_ids)):
        failures.append("internal_strategy_lane_ids_not_unique")
    for lane in lanes:
        lane_id = str(lane.get("lane_id") or "")
        if not str(lane.get("purpose") or "").strip():
            failures.append(f"internal_strategy_lane_missing_purpose:{lane_id}")
        if not list(lane.get("required_evidence") or []):
            failures.append(f"internal_strategy_lane_missing_required_evidence:{lane_id}")
        if lane_id not in {"geometry_sanity", "exact_stop", "no_valid_strategy"}:
            if not (
                lane.get("failure_transition")
                or lane.get("success_transition")
                or lane.get("acceptance_transition")
            ):
                failures.append(f"internal_strategy_lane_missing_transition:{lane_id}")
    lane_by_id = {str(lane.get("lane_id") or ""): lane for lane in lanes}
    if "depth/width ratio reaches 2.0" not in set(lane_by_id.get("depth_increase", {}).get("stop_conditions") or []):
        failures.append("depth_increase_missing_ratio_stop_condition")
    if "target band reached" not in set(lane_by_id.get("depth_increase", {}).get("stop_conditions") or []):
        failures.append("depth_increase_missing_target_band_stop_condition")
    if "do not continue once clear spacing reaches approximately 100 mm" not in set(
        lane_by_id.get("single_layer_bottom_reinforcement", {}).get("limits") or []
    ):
        failures.append("single_layer_missing_clear_spacing_limit")
    if "capacity must use actual reinforcement centroid, not bottom-row assumptions" not in set(
        lane_by_id.get("multi_layer_reinforcement", {}).get("rules") or []
    ):
        failures.append("multi_layer_missing_actual_centroid_rule")
    if lane_by_id.get("exact_stop", {}).get("output") != "EXACT_STOP":
        failures.append("exact_stop_output_mismatch")
    if lane_by_id.get("no_valid_strategy", {}).get("output") != "NO_VALID_STRATEGY":
        failures.append("no_valid_strategy_output_mismatch")

    rules = set(global_family_rules())
    required_rule_fragments = [
        "Strategy order is deterministic.",
        "Do not jump directly to width while valid depth growth remains.",
        "Do not use multi-layer reinforcement before width unless width is locked.",
        "After any geometry change, retry reinforcement strategies.",
        "Every rejected lane must record a rejection reason.",
        "Every accepted lane must record acceptance evidence.",
        "Exactly one final family outcome is permitted: selected recommendation, exact stop, or no valid strategy.",
    ]
    for rule in required_rule_fragments:
        if rule not in rules:
            failures.append(f"global_family_rule_missing:{rule}")

    outputs = set(required_family_outputs())
    failures.extend(f"required_family_output_missing:{field}" for field in sorted(REQUIRED_FAMILY_OUTPUTS - outputs))

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
    blocker_contract = contract.get("blockers") or {}
    valid_blocker_proof = set(str(value) for value in blocker_contract.get("valid_repair_blocked_proof") or [])
    required_valid_blocker_fragments = {
        "geometry locked",
        "depth locked and width locked",
        "project maximum depth reached",
        "project maximum width reached",
        "all contract-permitted BENDING_FAIL_GOVERNS repair strategies exhausted with explicit terminal evidence",
    }
    failures.extend(
        f"valid_repair_blocked_proof_missing:{field}"
        for field in sorted(required_valid_blocker_fragments - valid_blocker_proof)
    )
    implementation_cap_terms = set(str(value) for value in blocker_contract.get("implementation_cap_only_not_terminal") or [])
    required_cap_terms = {
        "internal search exhausted",
        "bounded move set exhausted",
        "bounded ladder exhausted",
        "candidate cap reached",
        "depth step cap reached",
        "width step cap reached",
        "maximum checked move-set depth reached",
        "maximum checked move-set width reached",
        "no generated candidates",
    }
    failures.extend(
        f"implementation_cap_only_not_terminal_missing:{field}"
        for field in sorted(required_cap_terms - implementation_cap_terms)
    )
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


def _validate_locked_regression_source() -> list[str]:
    failures: list[str] = []
    source_path = ROOT / "tools" / "verification" / "families" / "bending_fail_governs_locked_regression.py"
    if not _source_contains(source_path, "load_bending_fail_governs_contract") and not _source_contains(source_path, "required_locked_snapshot_fields"):
        failures.append("locked_regression_does_not_load_contract")
    if "EXPECTED_UNLOCKED_LADDER_HASH" in source_path.read_text(encoding="utf-8", errors="replace"):
        failures.append("locked_regression_still_hardcodes_old_expected_hash_constants")
    return failures


def _validate_locked_artifact(artifact_path: Path | None) -> list[str]:
    failures: list[str] = []
    if artifact_path is None or not artifact_path.exists():
        return ["locked_regression_artifact_missing"]
    artifact = _load_json(artifact_path)
    if artifact.get("contract_path") != str(CONTRACT_PATH):
        failures.append("locked_artifact_contract_path_mismatch")
    required_fields = list(required_locked_snapshot_fields())
    artifact_fields = list(artifact.get("required_snapshot_fields") or [])
    if artifact_fields != required_fields:
        failures.append("locked_artifact_required_snapshot_fields_mismatch")
    required_snapshots = list((load_bending_fail_governs_contract().get("lock_verification") or {}).get("required_snapshots") or [])
    artifact_snapshots = list(artifact.get("required_snapshots") or [])
    if artifact_snapshots != required_snapshots:
        failures.append("locked_artifact_required_snapshots_mismatch")
    direct_snapshots = artifact.get("direct_ladder_snapshots") or {}
    for snapshot_name in required_snapshots:
        snapshot = direct_snapshots.get(snapshot_name)
        if not isinstance(snapshot, dict):
            failures.append(f"locked_artifact_snapshot_missing:{snapshot_name}")
            continue
        for field in required_fields:
            if field not in snapshot:
                failures.append(f"locked_artifact_snapshot_field_missing:{snapshot_name}:{field}")
    return failures


def _write_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Contract Check",
        "",
        f"Status: {output.get('status')}",
        "",
        "## Contract",
        "",
        f"- contract_json: `{output.get('contract_path')}`",
        f"- locked_regression_artifact: `{output.get('locked_regression', {}).get('artifact')}`",
        f"- product_path_smoke_status: `{output.get('locked_regression_artifact_summary', {}).get('product_path_smoke_status')}`",
        f"- product_path_smoke_blocked_reason: `{output.get('locked_regression_artifact_summary', {}).get('product_path_smoke_blocked_reason')}`",
        "",
        "## Internal Strategy Ladder",
        "",
        f"- internal_ladder_hash: `{output.get('internal_ladder_hash')}`",
        f"- calculated_internal_ladder_hash: `{output.get('calculated_internal_ladder_hash')}`",
        "",
        "Lane order:",
        "",
    ]
    for lane in output.get("internal_strategy_lane_order") or []:
        lines.append(f"- Lane {lane.get('lane_index')}: `{lane.get('lane_id')}` - {lane.get('title')}")
    lines.extend([
        "",
        "## Checked Source Of Truth",
        "",
        "- JSON contract loaded through `contract.py`",
        "- internal strategy ladder loaded from `contract.json`",
        "- utilisation bands, depth/width rule, lane evidence, outputs, and shared exclusions validated",
        "- locked regression consumes contract fields",
        "- required snapshot fields validated against generated artifact",
        "",
        "## Failures",
        "",
    ])
    lines.extend([f"- {failure}" for failure in output.get("failures") or []] or ["- none"])
    lines.extend(
        [
            "",
            "## Output",
            "",
            f"- `{output.get('artifact')}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")

    contract = load_bending_fail_governs_contract()
    locked_regression = _run_locked_regression()
    artifact_path = Path(str(locked_regression.get("artifact") or "")) if locked_regression.get("artifact") else _latest_locked_artifact()
    locked_regression_artifact = _load_json(artifact_path) if artifact_path and artifact_path.exists() else {}

    failures = (
        _validate_contract_shape(contract)
        + _validate_locked_regression_source()
        + _validate_locked_artifact(artifact_path)
    )
    if locked_regression.get("status") != "PASS":
        failures.append("locked_regression_failed")

    status = "PASS" if not failures else "FAIL"
    artifact = {
        "schema": "bending_fail_governs_contract_check.v1",
        "status": status,
        "contract_path": str(CONTRACT_PATH),
        "family_identity": family_identity(),
        "required_locked_snapshot_fields": list(required_locked_snapshot_fields()),
        "utilisation_definitions": utilisation_definitions(),
        "required_family_inputs": list(required_family_inputs()),
        "depth_width_rule": depth_width_rule(),
        "internal_strategy_lane_order": [
            {
                "lane_index": lane.get("lane_index"),
                "lane_id": lane.get("lane_id"),
                "title": lane.get("title"),
            }
            for lane in internal_strategy_lanes()
        ],
        "internal_ladder_hash": internal_ladder_hash(),
        "calculated_internal_ladder_hash": calculate_internal_ladder_hash(),
        "global_family_rules": list(global_family_rules()),
        "required_family_outputs": list(required_family_outputs()),
        "shared_exclusions": list(shared_exclusions()),
        "allowed_blockers": list(allowed_blockers()),
        "required_gates": list(required_gates()),
        "locked_regression": locked_regression,
        "locked_regression_artifact_summary": {
            "status": locked_regression_artifact.get("status"),
            "product_path_smoke_status": locked_regression_artifact.get("product_path_smoke_status"),
            "product_path_smoke_blocked_reason": locked_regression_artifact.get("product_path_smoke_blocked_reason"),
            "ready_to_mark_locked_next": locked_regression_artifact.get("ready_to_mark_locked_next"),
        },
        "failures": failures,
    }
    artifact_path_out = ARTIFACT_DIR / f"bending_fail_governs_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_contract_check_{stamp}.md"
    artifact["artifact"] = str(artifact_path_out)
    artifact["report"] = str(report_path)
    artifact_path_out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(artifact, report_path)
    print(f"{status}: {artifact_path_out}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
