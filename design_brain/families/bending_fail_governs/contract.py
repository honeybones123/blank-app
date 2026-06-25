from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("contract.json")


def load_bending_fail_governs_contract() -> dict[str, Any]:
    """Load the BENDING_FAIL_GOVERNS machine-readable family contract."""

    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("BENDING_FAIL_GOVERNS contract must be a JSON object")
    return data


def required_locked_snapshot_fields() -> tuple[str, ...]:
    contract = load_bending_fail_governs_contract()
    repair_ladder = contract.get("repair_ladder") or {}
    return tuple(str(value) for value in repair_ladder.get("locked_snapshot_fields") or ())


def utilisation_definitions() -> dict[str, dict[str, Any]]:
    contract = load_bending_fail_governs_contract()
    definitions = contract.get("utilisation_definitions") or {}
    if not isinstance(definitions, dict):
        raise ValueError("utilisation_definitions must be a JSON object")
    return {str(key): dict(value) for key, value in definitions.items() if isinstance(value, dict)}


def required_family_inputs() -> tuple[str, ...]:
    contract = load_bending_fail_governs_contract()
    return tuple(str(value) for value in contract.get("required_family_inputs") or ())


def depth_width_rule() -> dict[str, Any]:
    contract = load_bending_fail_governs_contract()
    rule = contract.get("depth_width_rule") or {}
    if not isinstance(rule, dict):
        raise ValueError("depth_width_rule must be a JSON object")
    return dict(rule)


def internal_strategy_ladder() -> dict[str, Any]:
    contract = load_bending_fail_governs_contract()
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
    return str(ladder.get("ladder_hash") or "")


def calculate_internal_ladder_hash() -> str:
    ladder = internal_strategy_ladder()
    payload = {key: value for key, value in ladder.items() if key != "ladder_hash"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def global_family_rules() -> tuple[str, ...]:
    ladder = internal_strategy_ladder()
    return tuple(str(value) for value in ladder.get("global_family_rules") or ())


def required_family_outputs() -> tuple[str, ...]:
    ladder = internal_strategy_ladder()
    return tuple(str(value) for value in ladder.get("required_outputs") or ())


def shared_exclusions() -> tuple[str, ...]:
    contract = load_bending_fail_governs_contract()
    return tuple(str(value) for value in contract.get("shared_exclusions") or ())


def allowed_blockers() -> tuple[str, ...]:
    contract = load_bending_fail_governs_contract()
    blockers = contract.get("blockers") or {}
    return tuple(str(value) for value in blockers.get("allowed") or ())


def required_gates() -> tuple[str, ...]:
    contract = load_bending_fail_governs_contract()
    verification = contract.get("lock_verification") or {}
    return tuple(str(value) for value in verification.get("required_gates") or ())


def expected_ladder_snapshots() -> dict[str, dict[str, Any]]:
    contract = load_bending_fail_governs_contract()
    repair_ladder = contract.get("repair_ladder") or {}
    snapshots = repair_ladder.get("expected_ladder_snapshots") or {}
    if not isinstance(snapshots, dict):
        raise ValueError("expected_ladder_snapshots must be a JSON object")
    return {str(key): dict(value) for key, value in snapshots.items() if isinstance(value, dict)}


def family_identity() -> dict[str, Any]:
    contract = load_bending_fail_governs_contract()
    identity = contract.get("family_identity") or {}
    if not isinstance(identity, dict):
        raise ValueError("family_identity must be a JSON object")
    return dict(identity)


__all__ = [
    "CONTRACT_PATH",
    "allowed_blockers",
    "calculate_internal_ladder_hash",
    "depth_width_rule",
    "expected_ladder_snapshots",
    "family_identity",
    "global_family_rules",
    "internal_ladder_hash",
    "internal_strategy_ladder",
    "internal_strategy_lanes",
    "load_bending_fail_governs_contract",
    "required_family_inputs",
    "required_family_outputs",
    "required_gates",
    "required_locked_snapshot_fields",
    "shared_exclusions",
    "utilisation_definitions",
]
