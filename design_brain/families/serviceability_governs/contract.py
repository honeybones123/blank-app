from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("contract.json")


def load_serviceability_governs_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("SERVICEABILITY_GOVERNS contract must be a JSON object")
    return data


def family_identity() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("family_identity") or {})


def selection_boundary() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("selection_boundary") or {})


def inputs_contract() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("inputs_contract") or {})


def family_result_schema() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("family_result_schema") or {})


def ownership_contract() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("ownership_contract") or {})


def success_contract() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("success_contract") or {})


def governing_checks() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("governing_checks") or {})


def target_band() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("target_band") or {})


def repair_ladder() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("repair_ladder") or {})


def serviceability_contract_lane_order() -> tuple[str, ...]:
    ladder = repair_ladder()
    return tuple(str(value) for value in ladder.get("ordered_lanes") or ())


def strength_protection() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("strength_protection") or {})


def geometry_rules() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("geometry_rules") or {})


def exact_stop_rules() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("exact_stop") or {})


def exhausted_rules() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("exhausted") or {})


def ranking_criteria() -> tuple[str, ...]:
    ranking = load_serviceability_governs_contract().get("ranking") or {}
    return tuple(str(value) for value in ranking.get("ordered_criteria") or ())


def invalid_before_ranking() -> tuple[str, ...]:
    ranking = load_serviceability_governs_contract().get("ranking") or {}
    return tuple(str(value) for value in ranking.get("invalid_before_ranking") or ())


def lane_proof_policies() -> dict[str, Any]:
    return dict(load_serviceability_governs_contract().get("lane_proof_policies") or {})


def shared_exclusions() -> tuple[str, ...]:
    return tuple(str(value) for value in load_serviceability_governs_contract().get("shared_exclusions") or ())


def required_gates() -> tuple[str, ...]:
    verification = load_serviceability_governs_contract().get("lock_verification") or {}
    return tuple(str(value) for value in verification.get("required_gates") or ())


def contract_hash() -> str:
    payload = {
        "selection_boundary": selection_boundary(),
        "success_contract": success_contract(),
        "governing_checks": governing_checks(),
        "target_band": target_band(),
        "repair_ladder": repair_ladder(),
        "strength_protection": strength_protection(),
        "geometry_rules": geometry_rules(),
        "exact_stop": exact_stop_rules(),
        "exhausted": exhausted_rules(),
        "ranking": {
            "ordered_criteria": ranking_criteria(),
            "invalid_before_ranking": invalid_before_ranking(),
        },
        "lane_proof_policies": lane_proof_policies(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "CONTRACT_PATH",
    "contract_hash",
    "exact_stop_rules",
    "exhausted_rules",
    "family_identity",
    "family_result_schema",
    "geometry_rules",
    "governing_checks",
    "inputs_contract",
    "invalid_before_ranking",
    "lane_proof_policies",
    "load_serviceability_governs_contract",
    "ownership_contract",
    "ranking_criteria",
    "repair_ladder",
    "required_gates",
    "selection_boundary",
    "serviceability_contract_lane_order",
    "shared_exclusions",
    "strength_protection",
    "success_contract",
    "target_band",
]
