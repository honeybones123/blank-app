"""Contract-owned Design Guide family classification.

The chooser classifies raw engineering state flags into exactly one governing
family. It does not generate candidates, rank candidates, evaluate formulas,
publish UI, render CTAs, or execute apply payloads.
"""

from __future__ import annotations

from typing import Any, Callable

from design_brain.family_classification_runtime import classify_family_from_whole_beam_evidence


FAMILY_CHOOSER_CONTRACT_ID = "family_chooser_contract"
FAMILY_CHOOSER_CONTRACT_VERSION = 3
FAMILY_SELECTION_CONTRACT_VIOLATION = "FAMILY_SELECTION_CONTRACT_VIOLATION"
USE_CONTRACT_FAMILY_CLASSIFIER = False

FAMILY_IDS: tuple[str, ...] = (
    "SERVICEABILITY_GOVERNS",
    "COMBINED_BENDING_SHEAR_FAIL",
    "GEOMETRY_DETAILING_GOVERNS",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "COMBINED_OVERDESIGN",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "TARGET_BAND_REACHED",
    "EXACT_STOP_PROVEN",
    "LOCKED_NO_REPAIR",
)

RAW_FLAG_KEYS: tuple[str, ...] = (
    "geometry_detailing_fail",
    "serviceability_fail",
    "bending_fail",
    "shear_fail",
    "min_bending_reo_fail",
    "min_shear_reo_fail",
    "bending_overdesigned",
    "shear_overdesigned",
    "zero_shear_with_ligatures",
    "unnecessary_shear_reinforcement_exists",
    "shear_cleanup_possible",
    "bending_within_target_band",
    "shear_within_target_band",
    "locked_repair_blocked",
    "legal_repair_exists",
    "repair_required",
    "exact_stop_proven",
    "bending_acceptable",
    "shear_acceptable",
)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "pass", "failed", "fail", "active", "proven"}
    return bool(value)


def _raw(flags: dict[str, Any], key: str) -> bool:
    return _truthy(flags.get(key))


def normalise_raw_state_flags(flags: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(flags or {})
    out = {key: _raw(source, key) for key in RAW_FLAG_KEYS}
    zero_shear_ligature_cleanup = bool(
        out["zero_shear_with_ligatures"]
        or out["unnecessary_shear_reinforcement_exists"]
        or out["shear_cleanup_possible"]
    )
    if zero_shear_ligature_cleanup and not out["shear_fail"]:
        out["shear_overdesigned"] = True
        out["shear_acceptable"] = True
    out["active_combined_bending_shear_failure"] = bool(out["bending_fail"] and out["shear_fail"])
    out["any_strength_fail"] = bool(out["bending_fail"] or out["shear_fail"])
    out["any_min_reo_fail"] = bool(out["min_bending_reo_fail"] or out["min_shear_reo_fail"])
    out["any_failure"] = bool(
        out["geometry_detailing_fail"]
        or out["serviceability_fail"]
        or out["bending_fail"]
        or out["shear_fail"]
        or out["min_bending_reo_fail"]
        or out["min_shear_reo_fail"]
    )
    out["any_overdesign"] = bool(out["bending_overdesigned"] or out["shear_overdesigned"])
    for key, value in source.items():
        if key not in out:
            out[key] = value
    return out


def _whole_beam_evidence_from_raw_flags(
    flags: dict[str, Any],
    evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    source = dict(evidence or {})
    explicit = source.get("whole_beam_evidence") or source.get("whole_beam_state")
    if isinstance(explicit, dict):
        out = dict(explicit)
    else:
        out = {}
    def _value(key: str, default: Any) -> Any:
        if key in source:
            return source.get(key)
        if key in flags:
            return flags.get(key)
        return default

    bending_util_default = 1.1 if flags["bending_fail"] else (0.75 if flags["bending_overdesigned"] else 0.9)
    shear_util_default = 1.1 if flags["shear_fail"] else (0.75 if flags["shear_overdesigned"] else 0.9)
    out.setdefault("bending_utilisation", _value("bending_utilisation", bending_util_default))
    out.setdefault("shear_utilisation", _value("shear_utilisation", shear_util_default))
    out.setdefault(
        "bending_state",
        _value("bending_state", "FAIL" if flags["bending_fail"] else ("OVERDESIGNED" if flags["bending_overdesigned"] else "TARGET")),
    )
    out.setdefault(
        "shear_state",
        _value("shear_state", "FAIL" if flags["shear_fail"] else ("OVERDESIGNED" if flags["shear_overdesigned"] else "TARGET")),
    )
    out.setdefault("serviceability_state", _value("serviceability_state", "FAIL" if flags["serviceability_fail"] else "PASS"))
    out.setdefault(
        "geometry_detailing_state",
        _value("geometry_detailing_state", "BLOCKED" if flags["geometry_detailing_fail"] else "PASS"),
    )
    out.setdefault(
        "minimum_bending_reo_state",
        _value("minimum_bending_reo_state", "GOVERNS" if flags["min_bending_reo_fail"] else "PASS"),
    )
    out.setdefault(
        "minimum_shear_reo_state",
        _value("minimum_shear_reo_state", "GOVERNS" if flags["min_shear_reo_fail"] else "PASS"),
    )
    out.setdefault("geometry_locked", _value("geometry_locked", bool(flags.get("locked_repair_blocked"))))
    out.setdefault("reo_locked", _value("reo_locked", bool(flags.get("locked_repair_blocked"))))
    out.setdefault("can_strengthen_bending", _value("can_strengthen_bending", bool(flags["bending_fail"] and flags["legal_repair_exists"])))
    out.setdefault("can_strengthen_shear", _value("can_strengthen_shear", bool(flags["shear_fail"] and flags["legal_repair_exists"])))
    out.setdefault(
        "can_optimise_bending_without_hurting_shear",
        _value("can_optimise_bending_without_hurting_shear", False),
    )
    out.setdefault(
        "can_optimise_shear_without_hurting_bending",
        _value("can_optimise_shear_without_hurting_bending", False),
    )
    out.setdefault("exact_stop_available", _value("exact_stop_available", bool(flags["exact_stop_proven"])))
    out.setdefault("no_valid_repair_available", _value("no_valid_repair_available", bool(flags["locked_repair_blocked"] and not flags["legal_repair_exists"])))
    out.setdefault("zero_shear_with_ligatures", _value("zero_shear_with_ligatures", bool(flags.get("zero_shear_with_ligatures"))))
    out.setdefault(
        "unnecessary_shear_reinforcement_exists",
        _value("unnecessary_shear_reinforcement_exists", bool(flags.get("unnecessary_shear_reinforcement_exists"))),
    )
    out.setdefault("shear_cleanup_possible", _value("shear_cleanup_possible", bool(flags.get("shear_cleanup_possible"))))
    return out


def _classify_family_from_contract_runtime(
    flags: dict[str, Any],
    *,
    evidence: dict[str, Any] | None,
    contract_version: int | None,
) -> dict[str, Any]:
    whole_beam = _whole_beam_evidence_from_raw_flags(flags, evidence)
    result = classify_family_from_whole_beam_evidence(whole_beam)
    selected = str(result.get("selected_family_id") or "")
    matched = list(result.get("matched_family_ids") or [])
    selection_evidence = dict(evidence or {})
    selection_evidence.update(
        {
            "source": "design_brain.family_classification_runtime.classify_family_from_whole_beam_evidence",
            "raw_state_flags": dict(flags),
            "whole_beam_state": dict(result.get("whole_beam_state") or {}),
            "matched_family_ids": list(matched),
            "classification_contract": "family_classification_contract",
            "classification_contract_version": result.get("contract_version") or contract_version,
            "classification_hash": result.get("classification_hash"),
            "contract_classifier_product_active": True,
        }
    )
    return {
        "contract_checked": True,
        "contract_version": result.get("contract_version") or contract_version or FAMILY_CHOOSER_CONTRACT_VERSION,
        "selected_family": selected,
        "selected_family_id": selected,
        "selection_reason": result.get("classification_reason"),
        "selected_family_reason": result.get("classification_reason"),
        "classification_reason": result.get("classification_reason"),
        "classification_priority": result.get("classification_priority"),
        "governing_checks": result.get("governing_checks"),
        "inactive_family_evidence": result.get("inactive_family_evidence"),
        "terminal_status": result.get("terminal_status"),
        "blocked_reason": result.get("blocked_reason"),
        "classification_hash": result.get("classification_hash"),
        "matched_family_ids": matched,
        "raw_state_flags": dict(flags),
        "whole_beam_state": dict(result.get("whole_beam_state") or {}),
        "active_failures": [
            name
            for name, active in (
                ("bending", bool((result.get("whole_beam_state") or {}).get("bending_fail"))),
                ("shear", bool((result.get("whole_beam_state") or {}).get("shear_fail"))),
                ("serviceability", bool((result.get("whole_beam_state") or {}).get("serviceability_fail"))),
                ("geometry_detailing", bool((result.get("whole_beam_state") or {}).get("geometry_blocked"))),
            )
            if active
        ],
        "active_overdesigns": [
            name
            for name, active in (
                ("bending", bool((result.get("whole_beam_state") or {}).get("bending_overdesigned"))),
                ("shear", bool((result.get("whole_beam_state") or {}).get("shear_overdesigned"))),
            )
            if active
        ],
        "active_stops": [
            name
            for name, active in (
                ("target_band", selected == "TARGET_BAND_REACHED"),
                ("exact_stop", selected == "EXACT_STOP_PROVEN"),
            )
            if active
        ],
        "rejected_families": {
            family_id: record.get("rejection_reason")
            for family_id, record in (result.get("inactive_family_evidence") or {}).items()
            if family_id not in matched
        },
        "selection_evidence": selection_evidence,
        "selection_conflicts": [],
        "classification_passed": bool(selected),
        "family_selection_not_proven": not bool(selected),
    }


def _no_parent_or_strength_failure(flags: dict[str, Any]) -> bool:
    return not (
        flags["geometry_detailing_fail"]
        or flags["serviceability_fail"]
        or flags["bending_fail"]
        or flags["shear_fail"]
    )


def _no_failure(flags: dict[str, Any]) -> bool:
    return not (
        flags["geometry_detailing_fail"]
        or flags["serviceability_fail"]
        or flags["bending_fail"]
        or flags["shear_fail"]
        or flags["min_bending_reo_fail"]
        or flags["min_shear_reo_fail"]
    )


def _no_parent_strength_or_serviceability_failure(flags: dict[str, Any]) -> bool:
    return not (
        flags["serviceability_fail"]
        or flags["bending_fail"]
        or flags["shear_fail"]
    )


FamilyPredicate = Callable[[dict[str, Any]], bool]


def _prune_secondary_overdesign_matches(matched: list[str], flags: dict[str, Any]) -> list[str]:
    """Let active repair ownership outrank secondary overdesign cleanup."""

    out = list(matched or [])
    if (
        "SHEAR_FAIL_GOVERNS" in out
        and "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS" in out
        and flags["shear_fail"]
        and not flags["bending_fail"]
    ):
        out = [family for family in out if family != "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"]
    return out


FAMILY_DEFINITIONS: dict[str, FamilyPredicate] = {
    "SERVICEABILITY_GOVERNS": lambda f: f["serviceability_fail"] and not f["geometry_detailing_fail"],
    "LOCKED_NO_REPAIR": lambda f: (
        bool(f["repair_required"] or f["bending_fail"] or f["shear_fail"] or f["serviceability_fail"])
        and f["locked_repair_blocked"]
        and not f["legal_repair_exists"]
        and not f["serviceability_fail"]
        and not (
            f["bending_fail"]
            and not f["shear_fail"]
            and not f["serviceability_fail"]
        )
    ),
    "GEOMETRY_DETAILING_GOVERNS": lambda f: f["geometry_detailing_fail"],
    "COMBINED_BENDING_SHEAR_FAIL": lambda f: (
        not f["serviceability_fail"]
        and not f["geometry_detailing_fail"]
        and not f["locked_repair_blocked"]
        and f["bending_fail"]
        and f["shear_fail"]
    ),
    "BENDING_FAIL_GOVERNS": lambda f: (
        not f["serviceability_fail"]
        and not f["geometry_detailing_fail"]
        and f["bending_fail"]
        and not f["shear_fail"]
        and not f["shear_overdesigned"]
    ),
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": lambda f: (
        not f["serviceability_fail"]
        and not f["geometry_detailing_fail"]
        and not f["locked_repair_blocked"]
        and f["bending_fail"]
        and not f["shear_fail"]
        and f["shear_overdesigned"]
    ),
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": lambda f: (
        not f["serviceability_fail"]
        and not f["geometry_detailing_fail"]
        and not f["locked_repair_blocked"]
        and not f["bending_fail"]
        and f["shear_fail"]
        and f["bending_overdesigned"]
    ),
    "SHEAR_FAIL_GOVERNS": lambda f: (
        not f["serviceability_fail"]
        and not f["geometry_detailing_fail"]
        and not f["locked_repair_blocked"]
        and not f["bending_fail"]
        and f["shear_fail"]
        and not f["bending_overdesigned"]
    ),
    "COMBINED_OVERDESIGN": lambda f: (
        _no_parent_strength_or_serviceability_failure(f)
        and (
            (f["bending_overdesigned"] and f["shear_overdesigned"])
            or (f["min_bending_reo_fail"] and f["min_shear_reo_fail"])
        )
    ),
    "BENDING_OVERDESIGN_GOVERNS": lambda f: (
        _no_parent_strength_or_serviceability_failure(f)
        and (f["bending_overdesigned"] or f["min_bending_reo_fail"])
        and not f["shear_overdesigned"]
        and not f["min_shear_reo_fail"]
        and bool(f["min_bending_reo_fail"] or f["shear_within_target_band"] or f.get("shear_acceptable"))
    ),
    "SHEAR_OVERDESIGN_GOVERNS": lambda f: (
        _no_parent_strength_or_serviceability_failure(f)
        and (f["shear_overdesigned"] or f["min_shear_reo_fail"])
        and not f["bending_overdesigned"]
        and not f["min_bending_reo_fail"]
        and bool(f["min_shear_reo_fail"] or f["bending_within_target_band"] or f.get("bending_acceptable"))
    ),
    "TARGET_BAND_REACHED": lambda f: (
        _no_failure(f)
        and not f["bending_overdesigned"]
        and not f["shear_overdesigned"]
        and bool(f["bending_within_target_band"] or f.get("bending_acceptable"))
        and bool(f["shear_within_target_band"] or f.get("shear_acceptable"))
    ),
    "EXACT_STOP_PROVEN": lambda f: (
        _no_failure(f)
        and not f["bending_overdesigned"]
        and not f["shear_overdesigned"]
        and f["exact_stop_proven"]
    ),
}


def classify_family_from_raw_flags(
    raw_state_flags: dict[str, Any] | None,
    *,
    evidence: dict[str, Any] | None = None,
    contract_version: int | None = None,
) -> dict[str, Any]:
    flags = normalise_raw_state_flags(raw_state_flags)
    if USE_CONTRACT_FAMILY_CLASSIFIER:
        return _classify_family_from_contract_runtime(
            flags,
            evidence=evidence,
            contract_version=contract_version,
        )
    matched = [
        family_id
        for family_id, predicate in FAMILY_DEFINITIONS.items()
        if bool(predicate(flags))
    ]
    raw_matched = list(matched)
    matched = _prune_secondary_overdesign_matches(matched, flags)
    conflicts: list[str] = []
    if not matched:
        conflicts.append("zero_family_matches")
    if len(matched) > 1:
        conflicts.append("multiple_family_matches")
    selected = matched[0] if len(matched) == 1 else FAMILY_SELECTION_CONTRACT_VIOLATION
    reason = (
        f"classified_by_mutually_exclusive_definition:{selected}"
        if len(matched) == 1
        else ("zero_match_unclassified_state" if not matched else "multi_match_overlapping_family_definitions")
    )
    rejected = {
        family_id: _rejection_reason(family_id, selected, flags)
        for family_id in FAMILY_IDS
        if family_id not in matched
    }
    active_failures = []
    if flags["bending_fail"]:
        active_failures.append("bending")
    if flags["shear_fail"]:
        active_failures.append("shear")
    if flags["serviceability_fail"]:
        active_failures.append("serviceability")
    if flags["geometry_detailing_fail"]:
        active_failures.append("geometry_detailing")
    active_overdesigns = []
    if flags["bending_overdesigned"]:
        active_overdesigns.append("bending")
    if flags["shear_overdesigned"]:
        active_overdesigns.append("shear")
    active_stops = []
    if flags["bending_within_target_band"] and flags["shear_within_target_band"]:
        active_stops.append("target_band")
    if flags["exact_stop_proven"]:
        active_stops.append("exact_stop")
    selection_evidence = dict(evidence or {})
    selection_evidence.update(
        {
            "source": "design_brain.family_chooser.classify_family_from_raw_flags",
            "raw_state_flags": dict(flags),
            "raw_matched_family_ids": list(raw_matched),
            "matched_family_ids": list(matched),
            "classification_conflicts": list(conflicts),
            "classification_contract": FAMILY_CHOOSER_CONTRACT_ID,
            "classification_contract_version": contract_version or FAMILY_CHOOSER_CONTRACT_VERSION,
            "secondary_overdesign_match_pruned": raw_matched != matched,
        }
    )
    return {
        "contract_checked": True,
        "contract_version": contract_version or FAMILY_CHOOSER_CONTRACT_VERSION,
        "selected_family": selected,
        "selected_family_id": selected,
        "selection_reason": reason,
        "selected_family_reason": reason,
        "matched_family_ids": list(matched),
        "raw_state_flags": dict(flags),
        "active_failures": active_failures,
        "active_overdesigns": active_overdesigns,
        "active_stops": active_stops,
        "rejected_families": rejected,
        "selection_evidence": selection_evidence,
        "selection_conflicts": conflicts,
        "classification_passed": len(matched) == 1,
        "family_selection_not_proven": len(matched) != 1,
    }


def _rejection_reason(family_id: str, selected_family_id: str, flags: dict[str, Any]) -> str:
    if selected_family_id == FAMILY_SELECTION_CONTRACT_VIOLATION:
        return "not matched by explicit state definition"
    if family_id == "COMBINED_BENDING_SHEAR_FAIL":
        if not flags["bending_fail"]:
            return "rejected because bending_fail is false"
        if not flags["shear_fail"]:
            return "rejected because shear_fail is false"
    if family_id == "BENDING_FAIL_GOVERNS" and not flags["bending_fail"]:
        return "rejected because bending_fail is false"
    if family_id == "SHEAR_FAIL_GOVERNS" and not flags["shear_fail"]:
        return "rejected because shear_fail is false"
    if family_id.endswith("OVERDESIGN") or "OVERDESIGN" in family_id:
        if flags["any_failure"]:
            return "rejected because failure state is active"
    if family_id == "TARGET_BAND_REACHED" and flags["any_failure"]:
        return "rejected because failure state is active"
    if family_id == "EXACT_STOP_PROVEN" and flags["any_failure"]:
        return "rejected because failure state is active"
    return f"rejected because {selected_family_id} state definition matched"


__all__ = [
    "FAMILY_CHOOSER_CONTRACT_ID",
    "FAMILY_CHOOSER_CONTRACT_VERSION",
    "FAMILY_SELECTION_CONTRACT_VIOLATION",
    "FAMILY_IDS",
    "RAW_FLAG_KEYS",
    "USE_CONTRACT_FAMILY_CLASSIFIER",
    "classify_family_from_raw_flags",
    "normalise_raw_state_flags",
]
