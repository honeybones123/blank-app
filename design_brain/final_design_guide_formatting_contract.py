from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("final_design_guide_formatting_contract.json")


def load_final_design_guide_formatting_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Final Design Guide formatting contract must be a JSON object")
    return data


def _section(name: str) -> dict[str, Any]:
    return dict(load_final_design_guide_formatting_contract().get(name) or {})


def contract_identity() -> dict[str, Any]:
    return _section("contract_identity")


def allowed_inputs() -> tuple[str, ...]:
    return tuple(str(value) for value in load_final_design_guide_formatting_contract().get("allowed_inputs") or ())


def forbidden_inputs() -> tuple[str, ...]:
    return tuple(str(value) for value in load_final_design_guide_formatting_contract().get("forbidden_inputs") or ())


def outcome_state_mapping() -> dict[str, Any]:
    return _section("outcome_state_mapping")


def status_colour_contract() -> dict[str, Any]:
    return _section("status_colour_contract")


def field_sources() -> dict[str, Any]:
    return _section("field_sources")


def section_order() -> tuple[str, ...]:
    return tuple(str(value) for value in load_final_design_guide_formatting_contract().get("section_order") or ())


def current_row_contract() -> dict[str, Any]:
    return _section("current_row_contract")


def preview_row_contract() -> dict[str, Any]:
    return _section("preview_row_contract")


def cta_display_binding() -> dict[str, Any]:
    return _section("cta_display_binding")


def fallback_and_proof_pending() -> dict[str, Any]:
    return _section("fallback_and_proof_pending")


def required_test_ids() -> tuple[str, ...]:
    return tuple(str(value) for value in load_final_design_guide_formatting_contract().get("required_test_ids") or ())


def verifier_contract() -> dict[str, Any]:
    return _section("verifier_contract")


def contract_hash() -> str:
    payload = {
        "contract_identity": contract_identity(),
        "allowed_inputs": allowed_inputs(),
        "forbidden_inputs": forbidden_inputs(),
        "outcome_state_mapping": outcome_state_mapping(),
        "status_colour_contract": status_colour_contract(),
        "field_sources": field_sources(),
        "section_order": section_order(),
        "current_row_contract": current_row_contract(),
        "preview_row_contract": preview_row_contract(),
        "cta_display_binding": cta_display_binding(),
        "fallback_and_proof_pending": fallback_and_proof_pending(),
        "required_test_ids": required_test_ids(),
        "verifier_contract": verifier_contract(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "CONTRACT_PATH",
    "allowed_inputs",
    "contract_hash",
    "contract_identity",
    "cta_display_binding",
    "current_row_contract",
    "fallback_and_proof_pending",
    "field_sources",
    "forbidden_inputs",
    "load_final_design_guide_formatting_contract",
    "outcome_state_mapping",
    "preview_row_contract",
    "required_test_ids",
    "section_order",
    "status_colour_contract",
    "verifier_contract",
]
