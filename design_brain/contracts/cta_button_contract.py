from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("cta_button_contract.json")


def load_cta_button_contract() -> dict[str, Any]:
    """Load the Design Guide CTA/button source-precedence contract."""

    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("CTA/button contract must be a JSON object")
    return data


def cta_button_source_precedence_order() -> tuple[str, ...]:
    contract = load_cta_button_contract()
    source_precedence = contract.get("source_precedence") or {}
    return tuple(str(value) for value in source_precedence.get("button_contract") or ())


def cta_payload_source_precedence_order() -> dict[str, tuple[str, ...]]:
    contract = load_cta_button_contract()
    payload_precedence = contract.get("payload_precedence") or {}
    if not isinstance(payload_precedence, dict):
        raise ValueError("payload_precedence must be a JSON object")
    return {
        str(key): tuple(str(value) for value in values)
        for key, values in payload_precedence.items()
        if isinstance(values, list)
    }


def cta_source_payload_labels() -> dict[str, dict[str, str]]:
    contract = load_cta_button_contract()
    payload_precedence = contract.get("payload_precedence") or {}
    labels = payload_precedence.get("source_payload_labels") or {}
    if not isinstance(labels, dict):
        raise ValueError("source_payload_labels must be a JSON object")
    out: dict[str, dict[str, str]] = {}
    for key, value in labels.items():
        if isinstance(value, dict):
            out[str(key)] = {str(inner_key): str(inner_value) for inner_key, inner_value in value.items()}
    return out


def required_cta_proof_fields() -> tuple[str, ...]:
    contract = load_cta_button_contract()
    return tuple(str(value) for value in contract.get("required_proof_fields") or ())


def required_cta_source_record_fields() -> tuple[str, ...]:
    contract = load_cta_button_contract()
    return tuple(str(value) for value in contract.get("required_source_record_fields") or ())


def allowed_cta_states() -> tuple[str, ...]:
    contract = load_cta_button_contract()
    return tuple(str(value) for value in contract.get("allowed_cta_states") or ())


def required_cta_gates() -> tuple[str, ...]:
    contract = load_cta_button_contract()
    return tuple(str(value) for value in contract.get("required_gates") or ())


def cta_candidate_source_keys() -> tuple[str, ...]:
    contract = load_cta_button_contract()
    source_precedence = contract.get("source_precedence") or {}
    return tuple(str(value) for value in source_precedence.get("candidate_source_keys") or ())


def cta_focused_scenario_expected_winners() -> dict[str, str]:
    contract = load_cta_button_contract()
    source_precedence = contract.get("source_precedence") or {}
    winners = source_precedence.get("focused_scenario_expected_winners") or {}
    if not isinstance(winners, dict):
        raise ValueError("focused_scenario_expected_winners must be a JSON object")
    return {str(key): str(value) for key, value in winners.items()}


__all__ = [
    "CONTRACT_PATH",
    "allowed_cta_states",
    "cta_button_source_precedence_order",
    "cta_candidate_source_keys",
    "cta_focused_scenario_expected_winners",
    "cta_payload_source_precedence_order",
    "cta_source_payload_labels",
    "load_cta_button_contract",
    "required_cta_gates",
    "required_cta_proof_fields",
    "required_cta_source_record_fields",
]
