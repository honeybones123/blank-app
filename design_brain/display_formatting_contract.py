from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("display_formatting_contract.json")


def load_design_guide_formatting_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Design Guide formatting contract must be a JSON object")
    return data


def _section(name: str) -> dict[str, Any]:
    return dict(load_design_guide_formatting_contract().get(name) or {})


def contract_identity() -> dict[str, Any]:
    return _section("contract_identity")


def formatting_owns() -> tuple[str, ...]:
    return tuple(str(value) for value in load_design_guide_formatting_contract().get("formatting_owns") or ())


def formatting_must_not_own() -> tuple[str, ...]:
    return tuple(str(value) for value in load_design_guide_formatting_contract().get("formatting_must_not_own") or ())


def source_contract() -> dict[str, Any]:
    return _section("source_contract")


def display_model_contract() -> dict[str, Any]:
    return _section("display_model_contract")


def required_sections() -> tuple[str, ...]:
    return tuple(str(value) for value in display_model_contract().get("required_sections") or ())


def optional_sections() -> tuple[str, ...]:
    return tuple(str(value) for value in display_model_contract().get("optional_sections") or ())


def status_colour_contract() -> dict[str, Any]:
    return _section("status_colour_contract")


def verifier_contract() -> dict[str, Any]:
    return _section("verifier_contract")


def contract_hash() -> str:
    payload = {
        "identity": contract_identity(),
        "formatting_owns": formatting_owns(),
        "formatting_must_not_own": formatting_must_not_own(),
        "source_contract": source_contract(),
        "display_model_contract": display_model_contract(),
        "status_colour_contract": status_colour_contract(),
        "verifier_contract": verifier_contract(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "CONTRACT_PATH",
    "contract_hash",
    "contract_identity",
    "display_model_contract",
    "formatting_must_not_own",
    "formatting_owns",
    "load_design_guide_formatting_contract",
    "optional_sections",
    "required_sections",
    "source_contract",
    "status_colour_contract",
    "verifier_contract",
]
