from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("output_formatting_contract.json")


def load_design_guide_output_wording_contract() -> dict[str, Any]:
    """Load the machine-readable Design Guide output wording contract."""

    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Design Guide output wording contract must be a JSON object")
    return data


def allowed_title_status_formats() -> dict[str, Any]:
    contract = load_design_guide_output_wording_contract()
    formats = contract.get("allowed_title_status_formats") or {}
    if not isinstance(formats, dict):
        raise ValueError("allowed_title_status_formats must be a JSON object")
    return dict(formats)


def allowed_reason_why_rows() -> dict[str, Any]:
    contract = load_design_guide_output_wording_contract()
    rows = contract.get("allowed_reason_why_rows") or {}
    if not isinstance(rows, dict):
        raise ValueError("allowed_reason_why_rows must be a JSON object")
    return dict(rows)


def blocker_wording_categories() -> tuple[str, ...]:
    contract = load_design_guide_output_wording_contract()
    return tuple(str(value) for value in contract.get("blocker_wording_categories") or ())


def cleanup_no_repair_wording() -> dict[str, Any]:
    contract = load_design_guide_output_wording_contract()
    wording = contract.get("cleanup_no_repair_wording") or {}
    if not isinstance(wording, dict):
        raise ValueError("cleanup_no_repair_wording must be a JSON object")
    return dict(wording)


def exact_blocker_fallback_wording() -> dict[str, Any]:
    contract = load_design_guide_output_wording_contract()
    wording = contract.get("exact_blocker_fallback_wording") or {}
    if not isinstance(wording, dict):
        raise ValueError("exact_blocker_fallback_wording must be a JSON object")
    return dict(wording)


def ladder_stop_evidence_wording() -> dict[str, Any]:
    contract = load_design_guide_output_wording_contract()
    wording = contract.get("ladder_stop_evidence_wording") or {}
    if not isinstance(wording, dict):
        raise ValueError("ladder_stop_evidence_wording must be a JSON object")
    return dict(wording)


def cta_display_wording_expectations() -> dict[str, Any]:
    contract = load_design_guide_output_wording_contract()
    expectations = contract.get("cta_display_wording_expectations") or {}
    if not isinstance(expectations, dict):
        raise ValueError("cta_display_wording_expectations must be a JSON object")
    return dict(expectations)


def required_render_model_fields() -> tuple[str, ...]:
    contract = load_design_guide_output_wording_contract()
    return tuple(str(value) for value in contract.get("required_render_model_fields") or ())


def required_html_model_hash_fields() -> tuple[str, ...]:
    contract = load_design_guide_output_wording_contract()
    return tuple(str(value) for value in contract.get("required_hash_fields") or ())


def required_snapshot_cases() -> dict[str, dict[str, Any]]:
    contract = load_design_guide_output_wording_contract()
    cases = contract.get("required_snapshot_cases") or {}
    if not isinstance(cases, dict):
        raise ValueError("required_snapshot_cases must be a JSON object")
    return {str(key): dict(value) for key, value in cases.items() if isinstance(value, dict)}


def required_output_wording_gates() -> tuple[str, ...]:
    contract = load_design_guide_output_wording_contract()
    return tuple(str(value) for value in contract.get("required_gates") or ())


__all__ = [
    "CONTRACT_PATH",
    "allowed_reason_why_rows",
    "allowed_title_status_formats",
    "blocker_wording_categories",
    "cleanup_no_repair_wording",
    "cta_display_wording_expectations",
    "exact_blocker_fallback_wording",
    "ladder_stop_evidence_wording",
    "load_design_guide_output_wording_contract",
    "required_html_model_hash_fields",
    "required_output_wording_gates",
    "required_render_model_fields",
    "required_snapshot_cases",
]
