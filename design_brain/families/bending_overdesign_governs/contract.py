from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("contract.json")


def load_bending_overdesign_governs_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("BENDING_OVERDESIGN_GOVERNS contract must be a JSON object")
    return data


def family_identity() -> dict[str, Any]:
    return dict(load_bending_overdesign_governs_contract().get("family_identity") or {})


def required_family_inputs() -> dict[str, tuple[str, ...]]:
    inputs = load_bending_overdesign_governs_contract().get("required_family_inputs") or {}
    return {
        str(key): tuple(str(value) for value in values)
        for key, values in inputs.items()
        if isinstance(values, list)
    }


def family_result_schema() -> dict[str, Any]:
    return dict(load_bending_overdesign_governs_contract().get("family_result_schema") or {})


def internal_strategy_ladder() -> dict[str, Any]:
    return dict(load_bending_overdesign_governs_contract().get("internal_strategy_ladder") or {})


def internal_strategy_lanes() -> tuple[dict[str, Any], ...]:
    lanes = internal_strategy_ladder().get("lanes") or []
    if not isinstance(lanes, list):
        raise ValueError("internal_strategy_ladder.lanes must be an array")
    return tuple(dict(lane) for lane in lanes if isinstance(lane, dict))


def ranking_criteria() -> tuple[str, ...]:
    ranking = internal_strategy_ladder().get("ranking") or {}
    return tuple(str(value) for value in ranking.get("ordered_criteria") or ())


def required_family_outputs() -> tuple[str, ...]:
    return tuple(str(value) for value in internal_strategy_ladder().get("required_outputs") or ())


def minimum_reinforcement_rules() -> dict[str, Any]:
    return dict(load_bending_overdesign_governs_contract().get("minimum_reinforcement") or {})


def minimum_reinforcement_geometry_relief_rules() -> dict[str, Any]:
    return dict(load_bending_overdesign_governs_contract().get("minimum_reinforcement_geometry_relief") or {})


def geometry_rules() -> dict[str, Any]:
    return dict(load_bending_overdesign_governs_contract().get("geometry_rules") or {})


def lane_proof_policies() -> dict[str, Any]:
    return dict(load_bending_overdesign_governs_contract().get("lane_proof_policies") or {})


def shared_exclusions() -> tuple[str, ...]:
    return tuple(str(value) for value in load_bending_overdesign_governs_contract().get("shared_exclusions") or ())


def allowed_blockers() -> tuple[str, ...]:
    blockers = load_bending_overdesign_governs_contract().get("blockers") or {}
    return tuple(str(value) for value in blockers.get("allowed") or ())


def required_gates() -> tuple[str, ...]:
    verification = load_bending_overdesign_governs_contract().get("lock_verification") or {}
    return tuple(str(value) for value in verification.get("required_gates") or ())


def internal_ladder_hash() -> str:
    payload = {
        "ladder": internal_strategy_ladder(),
        "minimum_reinforcement": minimum_reinforcement_rules(),
        "minimum_reinforcement_geometry_relief": minimum_reinforcement_geometry_relief_rules(),
        "geometry_rules": geometry_rules(),
        "lane_proof_policies": lane_proof_policies(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "CONTRACT_PATH",
    "allowed_blockers",
    "family_identity",
    "family_result_schema",
    "geometry_rules",
    "internal_ladder_hash",
    "internal_strategy_ladder",
    "internal_strategy_lanes",
    "lane_proof_policies",
    "load_bending_overdesign_governs_contract",
    "minimum_reinforcement_geometry_relief_rules",
    "minimum_reinforcement_rules",
    "ranking_criteria",
    "required_family_inputs",
    "required_family_outputs",
    "required_gates",
    "shared_exclusions",
]
