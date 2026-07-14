"""Shadow runtime for the Design Brain family-classification contract.

This module is intentionally not product-driving. It consumes normalized
whole-beam evidence, evaluates the machine-readable classification contract in
priority order, and returns a stable proof result. It does not publish
recommendations, render CTA, execute family ladders, or import page runtime code.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from design_brain.family_classification import load_family_classification_contract


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:16]


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "pass", "passed", "active", "proven"}
    return bool(value)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _state(value: Any) -> str:
    return str(value or "").strip().upper()


def _target(value: float) -> bool:
    return 0.85 <= value <= 1.0


def _acceptable(value: float) -> bool:
    return value <= 1.0


def normalise_whole_beam_evidence(evidence: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(evidence or {})
    bending_util = _as_float(source.get("bending_utilisation"))
    shear_util = _as_float(source.get("shear_utilisation"))
    out = {
        "bending_utilisation": bending_util,
        "shear_utilisation": shear_util,
        "bending_state": _state(source.get("bending_state")),
        "shear_state": _state(source.get("shear_state")),
        "serviceability_state": _state(source.get("serviceability_state")),
        "geometry_detailing_state": _state(source.get("geometry_detailing_state")),
        "minimum_bending_reo_state": _state(source.get("minimum_bending_reo_state")),
        "minimum_shear_reo_state": _state(source.get("minimum_shear_reo_state")),
        "geometry_locked": _as_bool(source.get("geometry_locked")),
        "reo_locked": _as_bool(source.get("reo_locked")),
        "can_strengthen_bending": _as_bool(source.get("can_strengthen_bending")),
        "can_strengthen_shear": _as_bool(source.get("can_strengthen_shear")),
        "can_optimise_bending_without_hurting_shear": _as_bool(
            source.get("can_optimise_bending_without_hurting_shear")
        ),
        "can_optimise_shear_without_hurting_bending": _as_bool(
            source.get("can_optimise_shear_without_hurting_bending")
        ),
        "exact_stop_available": _as_bool(source.get("exact_stop_available")),
        "no_valid_repair_available": _as_bool(source.get("no_valid_repair_available")),
        "zero_shear_with_ligatures": _as_bool(source.get("zero_shear_with_ligatures")),
        "unnecessary_shear_reinforcement_exists": _as_bool(
            source.get("unnecessary_shear_reinforcement_exists")
        ),
        "shear_cleanup_possible": _as_bool(source.get("shear_cleanup_possible")),
    }
    out["bending_fail"] = bending_util > 1.0
    out["shear_fail"] = shear_util > 1.0
    out["bending_target"] = _target(bending_util)
    out["shear_target"] = _target(shear_util)
    out["bending_overdesigned"] = bending_util < 0.85
    zero_shear_ligature_cleanup = bool(
        out["zero_shear_with_ligatures"]
        or out["unnecessary_shear_reinforcement_exists"]
        or out["shear_cleanup_possible"]
    )
    out["shear_overdesigned"] = bool(shear_util < 0.85 or zero_shear_ligature_cleanup)
    out["strength_checks_acceptable"] = _acceptable(bending_util) and _acceptable(shear_util)
    out["serviceability_fail"] = out["serviceability_state"] == "FAIL"
    out["geometry_blocked"] = out["geometry_detailing_state"] == "BLOCKED"
    out["repair_or_optimisation_required"] = bool(
        out["bending_fail"]
        or out["shear_fail"]
        or out["serviceability_fail"]
        or out["geometry_blocked"]
        or out["bending_overdesigned"]
        or out["shear_overdesigned"]
        or out["minimum_bending_reo_state"] == "GOVERNS"
        or out["minimum_shear_reo_state"] == "GOVERNS"
    )
    contract_input = {key: out.get(key) for key in (
        "bending_utilisation",
        "shear_utilisation",
        "bending_state",
        "shear_state",
        "serviceability_state",
        "geometry_detailing_state",
        "minimum_bending_reo_state",
        "minimum_shear_reo_state",
        "geometry_locked",
        "reo_locked",
        "can_strengthen_bending",
        "can_strengthen_shear",
        "can_optimise_bending_without_hurting_shear",
        "can_optimise_shear_without_hurting_bending",
        "exact_stop_available",
        "no_valid_repair_available",
        "zero_shear_with_ligatures",
        "unnecessary_shear_reinforcement_exists",
        "shear_cleanup_possible",
    )}
    out["raw_evidence_hash"] = _stable_hash(contract_input)
    return out


FamilyPredicate = Callable[[dict[str, Any]], bool]


def _both_can_safely_reduce(e: dict[str, Any]) -> bool:
    return bool(
        e["can_optimise_bending_without_hurting_shear"]
        and e["can_optimise_shear_without_hurting_bending"]
    )


FAMILY_PREDICATES: dict[str, FamilyPredicate] = {
    "EXACT_STOP_PROVEN": lambda e: (
        e["exact_stop_available"]
        and e["strength_checks_acceptable"]
        and not e["serviceability_fail"]
        and not e["geometry_blocked"]
        and not e["bending_overdesigned"]
        and not e["shear_overdesigned"]
        and e["minimum_bending_reo_state"] != "GOVERNS"
        and e["minimum_shear_reo_state"] != "GOVERNS"
    ),
    "LOCKED_NO_REPAIR": lambda e: (
        (
            e["no_valid_repair_available"]
            and not e["serviceability_fail"]
            and not (
                e["bending_fail"]
                and not e["shear_fail"]
                and not e["serviceability_fail"]
            )
        )
        or (
            e["repair_or_optimisation_required"]
            and not e["serviceability_fail"]
            and (e["geometry_locked"] or e["reo_locked"])
            and not (
                e["can_strengthen_bending"]
                or e["can_strengthen_shear"]
                or e["can_optimise_bending_without_hurting_shear"]
                or e["can_optimise_shear_without_hurting_bending"]
            )
            and not (
                e["bending_fail"]
                and not e["shear_fail"]
                and not e["serviceability_fail"]
            )
        )
    ),
    "GEOMETRY_DETAILING_GOVERNS": lambda e: e["geometry_blocked"],
    "BENDING_AND_SHEAR_FAIL_GOVERN": lambda e: e["bending_fail"] and e["shear_fail"],
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": lambda e: (
        e["bending_fail"]
        and e["shear_overdesigned"]
        and e["can_strengthen_bending"]
        and e["can_optimise_shear_without_hurting_bending"]
    ),
    "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS": lambda e: (
        e["bending_fail"]
        and e["shear_overdesigned"]
        and e["can_strengthen_bending"]
        and e["can_optimise_shear_without_hurting_bending"]
    ),
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": lambda e: (
        e["shear_fail"]
        and e["bending_overdesigned"]
        and e["can_strengthen_shear"]
        and e["can_optimise_bending_without_hurting_shear"]
    ),
    "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS": lambda e: (
        e["shear_fail"]
        and e["bending_overdesigned"]
        and e["can_strengthen_shear"]
        and e["can_optimise_bending_without_hurting_shear"]
    ),
    "BENDING_FAIL_GOVERNS": lambda e: (
        e["bending_fail"]
        and not e["shear_fail"]
        and (e["shear_target"] or not e["can_optimise_shear_without_hurting_bending"])
    ),
    "SHEAR_FAIL_GOVERNS": lambda e: (
        e["shear_fail"]
        and not e["bending_fail"]
        and (e["bending_target"] or not e["can_optimise_bending_without_hurting_shear"])
    ),
    "SERVICEABILITY_GOVERNS": lambda e: (
        e["strength_checks_acceptable"]
        and e["serviceability_fail"]
    ),
    "COMBINED_OVERDESIGN": lambda e: (
        (
            (e["bending_overdesigned"] and e["shear_overdesigned"] and _both_can_safely_reduce(e))
            or (
                e["minimum_bending_reo_state"] == "GOVERNS"
                and e["minimum_shear_reo_state"] == "GOVERNS"
            )
        )
        and not e["serviceability_fail"]
    ),
    "BENDING_OVERDESIGN_GOVERNS": lambda e: (
        (e["bending_overdesigned"] or e["minimum_bending_reo_state"] == "GOVERNS")
        and e["shear_target"]
        and not e["serviceability_fail"]
    ),
    "SHEAR_OVERDESIGN_GOVERNS": lambda e: (
        (e["shear_overdesigned"] or e["minimum_shear_reo_state"] == "GOVERNS")
        and e["bending_target"]
        and not e["serviceability_fail"]
    ),
    "TARGET_BAND_REACHED": lambda e: (
        e["bending_target"]
        and e["shear_target"]
        and not e["serviceability_fail"]
        and not e["geometry_blocked"]
        and e["minimum_bending_reo_state"] != "GOVERNS"
        and e["minimum_shear_reo_state"] != "GOVERNS"
    ),
}


def classify_family_from_whole_beam_evidence(evidence: dict[str, Any] | None) -> dict[str, Any]:
    contract = load_family_classification_contract()
    normalized = normalise_whole_beam_evidence(evidence)
    rules = contract.get("classification_rules") or {}
    matched: list[str] = []
    inactive: dict[str, dict[str, Any]] = {}
    selected_family_id = ""
    selected_priority: int | None = None
    selected_rule: dict[str, Any] = {}

    for index, family_id in enumerate(contract.get("classification_priority_order") or [], start=1):
        predicate = FAMILY_PREDICATES.get(str(family_id))
        eligible = bool(predicate(normalized)) if predicate is not None else False
        if eligible:
            matched.append(str(family_id))
        if eligible and not selected_family_id:
            selected_family_id = str(family_id)
            selected_priority = int((rules.get(family_id) or {}).get("priority") or index)
            selected_rule = dict(rules.get(family_id) or {})
        inactive[str(family_id)] = {
            "family_id": str(family_id),
            "evaluated": True,
            "eligible": eligible,
            "rejection_reason": None if eligible else f"contract condition not matched for {family_id}",
            "evidence": {
                "condition_summary": (rules.get(family_id) or {}).get("condition_summary"),
                "required_evidence": list((rules.get(family_id) or {}).get("required_evidence") or []),
            },
            "priority_rank": index,
        }

    if not selected_family_id:
        selected_family_id = "LOCKED_NO_REPAIR"
        selected_priority = int((rules.get(selected_family_id) or {}).get("priority") or 2)
        selected_rule = dict(rules.get(selected_family_id) or {})
        inactive.setdefault(
            selected_family_id,
            {
                "family_id": selected_family_id,
                "evaluated": True,
                "eligible": False,
                "rejection_reason": "fallback because no contract rule matched",
                "evidence": {},
                "priority_rank": selected_priority,
            },
        )

    terminal_status = selected_rule.get("terminal_status")
    blocked_reason = None
    if selected_family_id == "LOCKED_NO_REPAIR":
        blocked_reason = "locked_inputs_or_no_valid_repair"

    base_result = {
        "selected_family_id": selected_family_id,
        "classification_reason": selected_rule.get("condition_summary")
        or f"classified_by_contract_priority:{selected_family_id}",
        "classification_priority": selected_priority,
        "bending_state": normalized.get("bending_state"),
        "shear_state": normalized.get("shear_state"),
        "governing_checks": {
            "bending_utilisation": normalized.get("bending_utilisation"),
            "shear_utilisation": normalized.get("shear_utilisation"),
            "serviceability_state": normalized.get("serviceability_state"),
            "geometry_detailing_state": normalized.get("geometry_detailing_state"),
        },
        "inactive_family_evidence": inactive,
        "terminal_status": terminal_status,
        "blocked_reason": blocked_reason,
        "contract_version": ((contract.get("contract_identity") or {}).get("contract_version") or ""),
        "matched_family_ids": matched,
        "whole_beam_state": normalized,
    }
    base_result["classification_hash"] = _stable_hash(
        {
            "selected_family_id": base_result["selected_family_id"],
            "classification_priority": base_result["classification_priority"],
            "governing_checks": base_result["governing_checks"],
            "terminal_status": base_result["terminal_status"],
            "blocked_reason": base_result["blocked_reason"],
            "matched_family_ids": base_result["matched_family_ids"],
            "whole_beam_state": base_result["whole_beam_state"],
        }
    )
    return base_result


__all__ = [
    "classify_family_from_whole_beam_evidence",
    "normalise_whole_beam_evidence",
]
