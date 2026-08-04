from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("contract.json")


def load_bending_and_shear_fail_govern_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("COMBINED_BENDING_SHEAR_FAIL_GOVERNS contract must be a JSON object")
    return data


def family_identity() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("family_identity") or {})


def selection_boundary() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("selection_boundary") or {})


def inputs_contract() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("inputs_contract") or {})


def family_result_schema() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("family_result_schema") or {})


def ownership_contract() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("ownership_contract") or {})


def candidate_source_contract() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("candidate_source_contract") or {})


def target_band_refinement_lane() -> dict[str, Any]:
    source = candidate_source_contract()
    return dict(source.get("target_band_refinement_lane") or {})


def success_contract() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("success_contract") or {})


def target_band() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("target_band") or {})


def interaction_contract() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("interaction_contract") or {})


def exact_stop_rules() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("exact_stop") or {})


def exhausted_rules() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("exhausted") or {})


def ranking_criteria() -> tuple[str, ...]:
    ranking = load_bending_and_shear_fail_govern_contract().get("ranking") or {}
    return tuple(str(value) for value in ranking.get("ordered_criteria") or ())


def invalid_before_ranking() -> tuple[str, ...]:
    ranking = load_bending_and_shear_fail_govern_contract().get("ranking") or {}
    return tuple(str(value) for value in ranking.get("invalid_before_ranking") or ())


def lane_proof_policies() -> dict[str, Any]:
    return dict(load_bending_and_shear_fail_govern_contract().get("lane_proof_policies") or {})


def shared_exclusions() -> tuple[str, ...]:
    return tuple(str(value) for value in load_bending_and_shear_fail_govern_contract().get("shared_exclusions") or ())


def required_gates() -> tuple[str, ...]:
    verification = load_bending_and_shear_fail_govern_contract().get("lock_verification") or {}
    return tuple(str(value) for value in verification.get("required_gates") or ())


def contract_hash() -> str:
    payload = {
        "selection_boundary": selection_boundary(),
        "candidate_source_contract": candidate_source_contract(),
        "target_band_refinement_lane": target_band_refinement_lane(),
        "success_contract": success_contract(),
        "target_band": target_band(),
        "interaction_contract": interaction_contract(),
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
    "candidate_source_contract",
    "contract_hash",
    "exact_stop_rules",
    "exhausted_rules",
    "family_identity",
    "family_result_schema",
    "inputs_contract",
    "interaction_contract",
    "invalid_before_ranking",
    "lane_proof_policies",
    "load_bending_and_shear_fail_govern_contract",
    "ownership_contract",
    "ranking_criteria",
    "required_gates",
    "selection_boundary",
    "shared_exclusions",
    "success_contract",
    "target_band",
    "target_band_refinement_lane",
]
