from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("contract.json")


def load_shear_fail_governs_contract() -> dict[str, Any]:
    """Load the SHEAR_FAIL_GOVERNS machine-readable family contract."""

    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("SHEAR_FAIL_GOVERNS contract must be a JSON object")
    return data


def required_locked_snapshot_fields() -> tuple[str, ...]:
    contract = load_shear_fail_governs_contract()
    repair_ladder = contract.get("repair_ladder") or {}
    return tuple(str(value) for value in repair_ladder.get("locked_snapshot_fields") or ())


def required_family_inputs() -> dict[str, tuple[str, ...]]:
    contract = load_shear_fail_governs_contract()
    inputs = contract.get("required_family_inputs") or {}
    if not isinstance(inputs, dict):
        raise ValueError("required_family_inputs must be a JSON object")
    return {
        str(category): tuple(str(value) for value in values)
        for category, values in inputs.items()
        if isinstance(values, list)
    }


def family_result_schema() -> dict[str, Any]:
    contract = load_shear_fail_governs_contract()
    schema = contract.get("family_result_schema") or {}
    if not isinstance(schema, dict):
        raise ValueError("family_result_schema must be a JSON object")
    return dict(schema)


def internal_strategy_ladder() -> dict[str, Any]:
    contract = load_shear_fail_governs_contract()
    ladder = contract.get("internal_strategy_ladder") or {}
    if not isinstance(ladder, dict):
        raise ValueError("internal_strategy_ladder must be a JSON object")
    return dict(ladder)


def internal_strategy_lanes() -> tuple[dict[str, Any], ...]:
    ladder = internal_strategy_ladder()
    lanes = ladder.get("lanes") or ()
    if not isinstance(lanes, list):
        raise ValueError("internal_strategy_ladder.lanes must be a JSON array")
    return tuple(dict(value) for value in lanes if isinstance(value, dict))


def internal_ladder_hash() -> str:
    ladder = internal_strategy_ladder()
    payload = {
        "family_id": ladder.get("family_id"),
        "entry_condition": ladder.get("entry_condition"),
        "lanes": ladder.get("lanes") or [],
        "ranking": ladder.get("ranking") or {},
        "required_outputs": ladder.get("required_outputs") or [],
        "global_family_rules": ladder.get("global_family_rules") or [],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def ranking_criteria() -> tuple[str, ...]:
    ladder = internal_strategy_ladder()
    ranking = ladder.get("ranking") or {}
    if not isinstance(ranking, dict):
        raise ValueError("internal_strategy_ladder.ranking must be a JSON object")
    return tuple(str(value) for value in ranking.get("ordered_criteria") or ())


def required_family_outputs() -> tuple[str, ...]:
    ladder = internal_strategy_ladder()
    return tuple(str(value) for value in ladder.get("required_outputs") or ())


def shared_exclusions() -> tuple[str, ...]:
    contract = load_shear_fail_governs_contract()
    return tuple(str(value) for value in contract.get("shared_exclusions") or ())


def allowed_blockers() -> tuple[str, ...]:
    contract = load_shear_fail_governs_contract()
    blockers = contract.get("blockers") or {}
    return tuple(str(value) for value in blockers.get("allowed") or ())


def required_gates() -> tuple[str, ...]:
    contract = load_shear_fail_governs_contract()
    verification = contract.get("lock_verification") or {}
    return tuple(str(value) for value in verification.get("required_gates") or ())


def expected_ladder_snapshots() -> dict[str, dict[str, Any]]:
    contract = load_shear_fail_governs_contract()
    repair_ladder = contract.get("repair_ladder") or {}
    snapshots = repair_ladder.get("expected_ladder_snapshots") or {}
    if not isinstance(snapshots, dict):
        raise ValueError("expected_ladder_snapshots must be a JSON object")
    return {str(key): dict(value) for key, value in snapshots.items() if isinstance(value, dict)}


def family_identity() -> dict[str, Any]:
    contract = load_shear_fail_governs_contract()
    identity = contract.get("family_identity") or {}
    if not isinstance(identity, dict):
        raise ValueError("family_identity must be a JSON object")
    return dict(identity)


__all__ = [
    "CONTRACT_PATH",
    "allowed_blockers",
    "expected_ladder_snapshots",
    "family_identity",
    "family_result_schema",
    "internal_ladder_hash",
    "internal_strategy_ladder",
    "internal_strategy_lanes",
    "load_shear_fail_governs_contract",
    "ranking_criteria",
    "required_family_inputs",
    "required_family_outputs",
    "required_gates",
    "required_locked_snapshot_fields",
    "shared_exclusions",
]
