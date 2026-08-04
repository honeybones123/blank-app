from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("contract.json")


def load_shear_overdesign_governs_contract() -> dict[str, Any]:
    """Load the SHEAR_OVERDESIGN_GOVERNS machine-readable family contract."""

    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("SHEAR_OVERDESIGN_GOVERNS contract must be a JSON object")
    return data


def family_identity() -> dict[str, Any]:
    identity = load_shear_overdesign_governs_contract().get("family_identity") or {}
    if not isinstance(identity, dict):
        raise ValueError("family_identity must be a JSON object")
    return dict(identity)


def required_family_inputs() -> dict[str, tuple[str, ...]]:
    inputs = load_shear_overdesign_governs_contract().get("required_family_inputs") or {}
    if not isinstance(inputs, dict):
        raise ValueError("required_family_inputs must be a JSON object")
    return {
        str(category): tuple(str(value) for value in values)
        for category, values in inputs.items()
        if isinstance(values, list)
    }


def family_result_schema() -> dict[str, Any]:
    schema = load_shear_overdesign_governs_contract().get("family_result_schema") or {}
    if not isinstance(schema, dict):
        raise ValueError("family_result_schema must be a JSON object")
    return dict(schema)


def zero_shear_override() -> dict[str, Any]:
    override = load_shear_overdesign_governs_contract().get("zero_shear_override") or {}
    if not isinstance(override, dict):
        raise ValueError("zero_shear_override must be a JSON object")
    return dict(override)


def internal_strategy_ladder() -> dict[str, Any]:
    ladder = load_shear_overdesign_governs_contract().get("internal_strategy_ladder") or {}
    if not isinstance(ladder, dict):
        raise ValueError("internal_strategy_ladder must be a JSON object")
    return dict(ladder)


def internal_strategy_lanes() -> tuple[dict[str, Any], ...]:
    lanes = internal_strategy_ladder().get("lanes") or ()
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
        "geometry_restrictions": geometry_restrictions(),
        "zero_shear_override": zero_shear_override(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def ranking_criteria() -> tuple[str, ...]:
    ranking = internal_strategy_ladder().get("ranking") or {}
    if not isinstance(ranking, dict):
        raise ValueError("internal_strategy_ladder.ranking must be a JSON object")
    return tuple(str(value) for value in ranking.get("ordered_criteria") or ())


def required_family_outputs() -> tuple[str, ...]:
    return tuple(str(value) for value in internal_strategy_ladder().get("required_outputs") or ())


def geometry_restrictions() -> dict[str, Any]:
    restrictions = load_shear_overdesign_governs_contract().get("geometry_restrictions") or {}
    if not isinstance(restrictions, dict):
        raise ValueError("geometry_restrictions must be a JSON object")
    return dict(restrictions)


def lane_proof_policies() -> dict[str, Any]:
    policies = load_shear_overdesign_governs_contract().get("lane_proof_policies") or {}
    if not isinstance(policies, dict):
        raise ValueError("lane_proof_policies must be a JSON object")
    return dict(policies)


def terminal_rules() -> dict[str, Any]:
    rules = load_shear_overdesign_governs_contract().get("terminal_rules") or {}
    if not isinstance(rules, dict):
        raise ValueError("terminal_rules must be a JSON object")
    return dict(rules)


def shared_exclusions() -> tuple[str, ...]:
    return tuple(str(value) for value in load_shear_overdesign_governs_contract().get("shared_exclusions") or ())


def allowed_blockers() -> tuple[str, ...]:
    blockers = load_shear_overdesign_governs_contract().get("blockers") or {}
    return tuple(str(value) for value in blockers.get("allowed") or ())


def required_gates() -> tuple[str, ...]:
    verification = load_shear_overdesign_governs_contract().get("lock_verification") or {}
    return tuple(str(value) for value in verification.get("required_gates") or ())


__all__ = [
    "CONTRACT_PATH",
    "allowed_blockers",
    "family_identity",
    "family_result_schema",
    "geometry_restrictions",
    "internal_ladder_hash",
    "internal_strategy_ladder",
    "internal_strategy_lanes",
    "lane_proof_policies",
    "load_shear_overdesign_governs_contract",
    "ranking_criteria",
    "required_family_inputs",
    "required_family_outputs",
    "required_gates",
    "shared_exclusions",
    "terminal_rules",
    "zero_shear_override",
]
