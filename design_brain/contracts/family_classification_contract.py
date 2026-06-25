from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("family_classification_contract.json")


def load_family_classification_contract() -> dict[str, Any]:
    """Load the Design Brain family-classification contract."""

    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Family classification contract must be a JSON object")
    return data


def family_classification_contract_version() -> str:
    contract = load_family_classification_contract()
    identity = contract.get("contract_identity") or {}
    return str(identity.get("contract_version") or "")


def allowed_family_ids() -> tuple[str, ...]:
    contract = load_family_classification_contract()
    return tuple(str(value) for value in contract.get("allowed_family_ids") or ())


def classification_priority_order() -> tuple[str, ...]:
    contract = load_family_classification_contract()
    return tuple(str(value) for value in contract.get("classification_priority_order") or ())


def utilisation_bands() -> dict[str, dict[str, Any]]:
    contract = load_family_classification_contract()
    bands = contract.get("utilisation_bands") or {}
    if not isinstance(bands, dict):
        raise ValueError("utilisation_bands must be a JSON object")
    return {str(key): dict(value) for key, value in bands.items() if isinstance(value, dict)}


def classification_rules() -> dict[str, dict[str, Any]]:
    contract = load_family_classification_contract()
    rules = contract.get("classification_rules") or {}
    if not isinstance(rules, dict):
        raise ValueError("classification_rules must be a JSON object")
    return {str(key): dict(value) for key, value in rules.items() if isinstance(value, dict)}


def classification_rule_for(family_id: str) -> dict[str, Any]:
    rules = classification_rules()
    family = str(family_id or "").strip()
    if family not in rules:
        raise KeyError(f"Unknown family classification rule: {family}")
    return dict(rules[family])


def required_input_evidence() -> tuple[str, ...]:
    return required_state_inputs()


def required_state_inputs() -> tuple[str, ...]:
    contract = load_family_classification_contract()
    return tuple(str(value) for value in contract.get("required_state_inputs") or ())


def required_utilisation_status_fields() -> tuple[str, ...]:
    contract = load_family_classification_contract()
    return tuple(str(value) for value in contract.get("required_utilisation_status_fields") or ())


def selected_family_output_required_fields() -> tuple[str, ...]:
    contract = load_family_classification_contract()
    schema = contract.get("selected_family_output_schema") or {}
    return tuple(str(value) for value in schema.get("required_fields") or ())


def inactive_family_evidence_required_fields() -> tuple[str, ...]:
    contract = load_family_classification_contract()
    schema = contract.get("inactive_family_evidence_schema") or {}
    return tuple(str(value) for value in schema.get("required_fields") or ())


def shared_page_owned_exclusions() -> tuple[str, ...]:
    contract = load_family_classification_contract()
    return tuple(str(value) for value in contract.get("shared_page_owned_exclusions") or ())


def global_protection_rules() -> tuple[str, ...]:
    contract = load_family_classification_contract()
    return tuple(str(value) for value in contract.get("global_protection_rules") or ())


def required_family_classification_gates() -> tuple[str, ...]:
    contract = load_family_classification_contract()
    return tuple(str(value) for value in contract.get("required_gates") or ())


def terminal_family_ids() -> tuple[str, ...]:
    rules = classification_rules()
    return tuple(
        family_id
        for family_id in classification_priority_order()
        if str((rules.get(family_id) or {}).get("rule_type") or "") == "terminal"
    )


__all__ = [
    "CONTRACT_PATH",
    "allowed_family_ids",
    "classification_priority_order",
    "classification_rule_for",
    "classification_rules",
    "family_classification_contract_version",
    "global_protection_rules",
    "inactive_family_evidence_required_fields",
    "load_family_classification_contract",
    "required_family_classification_gates",
    "required_input_evidence",
    "required_state_inputs",
    "required_utilisation_status_fields",
    "selected_family_output_required_fields",
    "shared_page_owned_exclusions",
    "terminal_family_ids",
    "utilisation_bands",
]
