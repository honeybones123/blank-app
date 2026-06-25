from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("contract.json")


def load_shear_fail_bending_overdesign_governs_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS contract must be a JSON object")
    return data


def _section(name: str) -> dict[str, Any]:
    return dict(load_shear_fail_bending_overdesign_governs_contract().get(name) or {})


def family_identity() -> dict[str, Any]:
    return _section("family_identity")


def selection_boundary() -> dict[str, Any]:
    return _section("selection_boundary")


def inputs_contract() -> dict[str, Any]:
    return _section("inputs_contract")


def family_result_schema() -> dict[str, Any]:
    return _section("family_result_schema")


def ownership_contract() -> dict[str, Any]:
    return _section("ownership_contract")


def candidate_source_contract() -> dict[str, Any]:
    return _section("candidate_source_contract")


def priority_contract() -> dict[str, Any]:
    return _section("priority_contract")


def success_contract() -> dict[str, Any]:
    return _section("success_contract")


def bending_protection() -> dict[str, Any]:
    return _section("bending_protection")


def target_band() -> dict[str, Any]:
    return _section("target_band")


def interaction_contract() -> dict[str, Any]:
    return _section("interaction_contract")


def exact_stop_rules() -> dict[str, Any]:
    return _section("exact_stop")


def exhausted_rules() -> dict[str, Any]:
    return _section("exhausted")


def evidence_contract() -> dict[str, Any]:
    return _section("evidence_contract")


def ranking_criteria() -> tuple[str, ...]:
    ranking = _section("ranking")
    return tuple(str(value) for value in ranking.get("ordered_criteria") or ())


def invalid_before_ranking() -> tuple[str, ...]:
    ranking = _section("ranking")
    return tuple(str(value) for value in ranking.get("invalid_before_ranking") or ())


def lane_proof_policies() -> dict[str, Any]:
    return _section("lane_proof_policies")


def shared_exclusions() -> tuple[str, ...]:
    return tuple(str(value) for value in load_shear_fail_bending_overdesign_governs_contract().get("shared_exclusions") or ())


def required_gates() -> tuple[str, ...]:
    verification = _section("lock_verification")
    return tuple(str(value) for value in verification.get("required_gates") or ())


def contract_hash() -> str:
    payload = {
        "selection_boundary": selection_boundary(),
        "candidate_source_contract": candidate_source_contract(),
        "priority_contract": priority_contract(),
        "success_contract": success_contract(),
        "bending_protection": bending_protection(),
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
    "bending_protection",
    "candidate_source_contract",
    "contract_hash",
    "evidence_contract",
    "exact_stop_rules",
    "exhausted_rules",
    "family_identity",
    "family_result_schema",
    "inputs_contract",
    "interaction_contract",
    "invalid_before_ranking",
    "lane_proof_policies",
    "load_shear_fail_bending_overdesign_governs_contract",
    "ownership_contract",
    "priority_contract",
    "ranking_criteria",
    "required_gates",
    "selection_boundary",
    "shared_exclusions",
    "success_contract",
    "target_band",
]
