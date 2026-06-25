"""Read-only governing-state classifier for Design Brain diagnostics.

This module classifies already-computed Design Guide payloads. It does not
generate candidates, rank candidates, evaluate formulas, apply updates,
publish UI, or decide CTAs.
"""

from __future__ import annotations

from typing import Any


TARGET_LOW_DEFAULT = 0.85
TARGET_HIGH_DEFAULT = 1.0

_FAIL_STATUSES = {"FAIL", "FAILED", "ERROR", "NG"}
_PASS_STATUSES = {"PASS", "OK", "ACCEPTED", "OPTIMAL", "NEAR LIMIT", "WARN"}
_MAJOR_FAMILIES = {"bending", "shear"}
_SERVICEABILITY_FAMILIES = {"crack", "deflection", "serviceability"}
_DETAILING_FAMILIES = {"spacing", "detailing", "geometry", "cover", "ductility"}


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_family(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"sectional_shear", "sectional shear"}:
        return "shear"
    if text == "service":
        return "serviceability"
    return text


def _normalised_statuses(summary: dict, evidence: dict, debug: dict) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for source in (
        _as_dict(summary.get("statuses")),
        _as_dict(evidence.get("statuses")),
        _as_dict(debug.get("statuses")),
    ):
        for family, status in source.items():
            fam = _normalise_family(family)
            if fam:
                statuses[fam] = str(status or "").strip().upper()
    family_status_current = _as_dict(evidence.get("family_status_current") or debug.get("family_status_current"))
    for family, row in family_status_current.items():
        fam = _normalise_family(family)
        status = str(_as_dict(row).get("status") or "").strip().upper()
        if fam and status:
            statuses[fam] = status
    return statuses


def _normalised_utils(summary: dict, evidence: dict, debug: dict) -> dict[str, float]:
    utils: dict[str, float] = {}
    for source in (
        _as_dict(summary.get("utils")),
        _as_dict(evidence.get("utils")),
        _as_dict(evidence.get("family_utils")),
        _as_dict(debug.get("family_utils")),
    ):
        for family, value in source.items():
            fam = _normalise_family(family)
            parsed = _as_float(value)
            if fam and parsed is not None:
                utils[fam] = float(parsed)
    family_status_current = _as_dict(evidence.get("family_status_current") or debug.get("family_status_current"))
    for family, row in family_status_current.items():
        fam = _normalise_family(family)
        parsed = _as_float(_as_dict(row).get("util"))
        if fam and parsed is not None:
            utils.setdefault(fam, float(parsed))
    return utils


def _active_failures(summary: dict, evidence: dict, debug: dict) -> list[str]:
    failures: set[str] = set()
    for raw in (
        evidence.get("active_failures"),
        debug.get("active_failures"),
        summary.get("fail_keys"),
        debug.get("fail_keys"),
    ):
        if isinstance(raw, (list, tuple, set)):
            for item in raw:
                fam = _normalise_family(item)
                if fam:
                    failures.add(fam)
    for family, status in _normalised_statuses(summary, evidence, debug).items():
        if status in _FAIL_STATUSES:
            failures.add(family)
    for family, util in _normalised_utils(summary, evidence, debug).items():
        if family in _MAJOR_FAMILIES and float(util) > 1.0:
            failures.add(family)
    if "combined" in failures:
        failures.discard("combined")
        failures.update({"bending", "shear"})
    return sorted(failures)


def _target_band(evidence: dict, debug: dict, primary: dict) -> tuple[float, float]:
    target_low = _as_float(
        evidence.get("target_low")
        or debug.get("target_low")
        or primary.get("target_low")
        or _as_dict(primary.get("display_truth")).get("target_low")
    )
    target_high = _as_float(
        evidence.get("target_high")
        or debug.get("target_high")
        or primary.get("target_high")
        or _as_dict(primary.get("display_truth")).get("target_high")
    )
    if target_low is None or target_high is None or target_low >= target_high:
        return TARGET_LOW_DEFAULT, TARGET_HIGH_DEFAULT
    return float(target_low), float(target_high)


def _active_overdesigns(summary: dict, evidence: dict, debug: dict, target_low: float) -> list[str]:
    statuses = _normalised_statuses(summary, evidence, debug)
    utils = _normalised_utils(summary, evidence, debug)
    out: list[str] = []
    for family in ("bending", "shear"):
        util = utils.get(family)
        if util is None or float(util) >= float(target_low):
            continue
        status = statuses.get(family, "")
        if status and status not in _PASS_STATUSES:
            continue
        out.append(family)
    return out


def _evidence_maps(evidence: dict, debug: dict, primary: dict) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
        "local_cleanup_blocked_reasons_by_family",
    ):
        by_family: dict[str, dict] = {}
        for source in (
            evidence.get(key),
            debug.get(key),
            primary.get(key),
            _as_dict(primary.get("action_payload")).get(key),
            _as_dict(primary.get("resolved_candidate")).get(key),
        ):
            if not isinstance(source, dict):
                continue
            for family, row in source.items():
                fam = _normalise_family(family)
                if not fam:
                    continue
                if isinstance(row, dict):
                    by_family[fam] = {**by_family.get(fam, {}), **dict(row)}
                elif isinstance(row, list):
                    by_family[fam] = {**by_family.get(fam, {}), "reasons": list(row)}
                elif row not in (None, ""):
                    by_family[fam] = {**by_family.get(fam, {}), "reason": str(row)}
        if by_family:
            merged[key] = by_family
    return merged


def _flatten_evidence_text(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, dict):
            parts.extend(_flatten_evidence_text(k, v) for k, v in value.items())
        elif isinstance(value, (list, tuple, set)):
            parts.extend(_flatten_evidence_text(v) for v in value)
        elif value not in (None, ""):
            parts.append(str(value))
    return " ".join(parts).lower()


def _active_constraints(evidence: dict, debug: dict, primary: dict) -> list[str]:
    maps = _evidence_maps(evidence, debug, primary)
    constraints: set[str] = set()
    text = _flatten_evidence_text(maps, evidence.get("local_cleanup_blocked_reasons"), debug.get("local_cleanup_blocked_reasons"))
    for token, label in (
        ("geometry", "geometry"),
        ("depth", "geometry"),
        ("width", "geometry"),
        ("spacing", "spacing_detailing"),
        ("detailing", "spacing_detailing"),
        ("ductility", "spacing_detailing"),
        ("cover", "spacing_detailing"),
        ("serviceability", "serviceability"),
        ("deflection", "serviceability"),
        ("crack", "serviceability"),
        ("minimum", "minimum_reinforcement"),
        ("min reo", "minimum_reinforcement"),
        ("lig", "minimum_shear_reinforcement"),
        ("link", "minimum_shear_reinforcement"),
    ):
        if token in text:
            constraints.add(label)
    if any(token in text for token in ("geometry lock", "reinforcement lock", "shear lock", "locked input")):
        constraints.add("locked_input")
    for lock_key in (
        "optimisation_lock_geometry",
        "geometry_locked",
        "lock_geometry",
        "reinforcement_lock",
        "shear_lock",
    ):
        if primary.get(lock_key) or debug.get(lock_key) or evidence.get(lock_key):
            constraints.add("locked_input")
    return sorted(constraints)


def _exact_stop_possible(evidence: dict, debug: dict, primary: dict) -> bool:
    maps = _evidence_maps(evidence, debug, primary)
    for by_family in maps.values():
        for row in by_family.values():
            if not isinstance(row, dict):
                continue
            if bool(
                row.get("exact_blocker")
                or row.get("cleanup_search_exhaustive")
                or row.get("local_cleanup_search_exhaustive")
                or row.get("repair_search_exhaustive")
                or row.get("target_band_search_exhaustive")
                or row.get("candidate_search_exhaustive")
            ):
                return True
    return bool(
        evidence.get("cleanup_search_exhaustive")
        or evidence.get("local_cleanup_search_exhaustive")
        or evidence.get("target_band_search_exhaustive")
        or evidence.get("candidate_search_exhaustive")
        or evidence.get("repair_search_exhaustive")
    )


def _candidate_action_required(primary: dict, debug: dict, evidence: dict) -> bool:
    contract = _as_dict(primary.get("button_contract") or debug.get("primary_button_contract") or debug.get("button_contract"))
    updates = _as_dict(
        contract.get("updates")
        or primary.get("updates")
        or primary.get("selected_action_updates")
        or evidence.get("selected_candidate_updates")
    )
    return bool(
        (contract.get("enabled") or contract.get("actionable") or debug.get("button_contract_enabled"))
        and updates
        and str(contract.get("action_type") or primary.get("action_type") or "").strip()
    )


def _target_reached(summary: dict, evidence: dict, debug: dict, primary: dict, low: float, high: float) -> bool:
    display_truth = _as_dict(primary.get("display_truth") or debug.get("primary_display_truth"))
    for value in (
        display_truth.get("displayed_util"),
        display_truth.get("source_summary_util"),
        summary.get("worst_util"),
        summary.get("governing_util"),
    ):
        util = _as_float(value)
        if util is not None and float(low) <= float(util) <= float(high):
            return True
    return False


def _state_from_constraints(active_constraints: list[str], text: str) -> str | None:
    if "minimum_shear_reinforcement" in active_constraints and (
        "shear" in text or "lig" in text or "link" in text
    ):
        return "MIN_SHEAR_REO_GOVERNS"
    if "minimum_reinforcement" in active_constraints and "bending" in text:
        return "MIN_BENDING_REO_GOVERNS"
    if "geometry" in active_constraints:
        return "GEOMETRY_GOVERNS_OPTIMISATION_STOP"
    if "spacing_detailing" in active_constraints:
        return "SPACING_DETAILING_GOVERNS_OPTIMISATION_STOP"
    if "serviceability" in active_constraints:
        return "SERVICEABILITY_GOVERNS_OPTIMISATION_STOP"
    return None


def classify_governing_state(
    *,
    payload: dict | None = None,
    primary: dict | None = None,
    summary: dict | None = None,
    evidence: dict | None = None,
    debug: dict | None = None,
    result: dict | None = None,
) -> dict[str, Any]:
    """Return read-only governing-state diagnostics for an existing payload."""
    payload_d = _as_dict(payload)
    debug_d = _as_dict(debug or payload_d.get("debug_trace"))
    result_d = _as_dict(result or payload_d.get("design_brain_result") or debug_d.get("design_brain_result"))
    primary_d = _as_dict(primary)
    if not primary_d:
        items = _as_list(payload_d.get("guidance_items"))
        primary_d = dict(items[0]) if items and isinstance(items[0], dict) else {}
    summary_d = _as_dict(summary or debug_d.get("overview") or _as_dict(primary_d.get("candidate_search_evidence")).get("overview"))
    evidence_d = _as_dict(evidence)
    if not evidence_d:
        evidence_d = _as_dict(
            _as_dict(result_d.get("evidence")).get("candidate_search")
            or primary_d.get("candidate_search_evidence")
            or _as_dict(primary_d.get("action_payload")).get("candidate_search_evidence")
            or _as_dict(primary_d.get("resolved_candidate")).get("candidate_search_evidence")
            or debug_d.get("candidate_search_evidence")
            or debug_d.get("local_cleanup_candidate_search_evidence")
        )

    low, high = _target_band(evidence_d, debug_d, primary_d)
    active_failures = _active_failures(summary_d, evidence_d, debug_d)
    active_overdesigns = _active_overdesigns(summary_d, evidence_d, debug_d, low)
    active_constraints = _active_constraints(evidence_d, debug_d, primary_d)
    exact_stop = _exact_stop_possible(evidence_d, debug_d, primary_d)
    action_required = _candidate_action_required(primary_d, debug_d, evidence_d)
    target_reached = _target_reached(summary_d, evidence_d, debug_d, primary_d, low, high)

    maps = _evidence_maps(evidence_d, debug_d, primary_d)
    evidence_text = _flatten_evidence_text(
        primary_d,
        evidence_d,
        debug_d.get("terminal_state_reason"),
        debug_d.get("local_cleanup_blocked_reasons"),
        maps,
    )

    governing_state = "UNKNOWN"
    primary_driver = None
    diagnostic_reasons: list[str] = []

    active_set = set(active_failures)
    if {"bending", "shear"}.issubset(active_set):
        governing_state = "COMBINED_BENDING_SHEAR_FAIL"
        primary_driver = "combined_strength_failure"
    elif "bending" in active_set:
        governing_state = "BENDING_FAIL_GOVERNS"
        primary_driver = "bending"
    elif "shear" in active_set:
        governing_state = "SHEAR_FAIL_GOVERNS"
        primary_driver = "shear"
    elif active_set & _SERVICEABILITY_FAMILIES:
        governing_state = "SERVICEABILITY_FAIL_GOVERNS"
        primary_driver = sorted(active_set & _SERVICEABILITY_FAMILIES)[0]
    elif active_set & _DETAILING_FAMILIES:
        governing_state = "GEOMETRY_DETAILING_FAIL_GOVERNS"
        primary_driver = sorted(active_set & _DETAILING_FAMILIES)[0]
    elif "locked_input" in active_constraints and not action_required:
        governing_state = "LOCKED_NO_REPAIR"
        primary_driver = "locked_input"
    elif exact_stop and not action_required:
        constraint_state = _state_from_constraints(active_constraints, evidence_text)
        governing_state = constraint_state or "EXACT_STOP_PROVEN"
        primary_driver = (active_constraints[0] if active_constraints else "exact_stop")
    elif target_reached and not action_required and not active_overdesigns:
        governing_state = "TARGET_BAND_REACHED"
        primary_driver = "target_band"
    elif {"bending", "shear"}.issubset(set(active_overdesigns)):
        governing_state = "COMBINED_OVERDESIGN"
        primary_driver = "combined_overdesign"
    elif "bending" in active_overdesigns:
        governing_state = "BENDING_OVERDESIGN_GOVERNS"
        primary_driver = "bending"
    elif "shear" in active_overdesigns:
        governing_state = "SHEAR_OVERDESIGN_GOVERNS"
        primary_driver = "shear"
    else:
        constraint_state = _state_from_constraints(active_constraints, evidence_text)
        if constraint_state:
            governing_state = constraint_state
            primary_driver = active_constraints[0] if active_constraints else "constraint"

    if active_failures:
        diagnostic_reasons.append("active_failures_present")
    if active_overdesigns:
        diagnostic_reasons.append("active_overdesigns_present")
    if active_constraints:
        diagnostic_reasons.append("active_constraints_present")
    if action_required:
        diagnostic_reasons.append("candidate_action_required")
    if exact_stop:
        diagnostic_reasons.append("exact_stop_possible")
    if target_reached:
        diagnostic_reasons.append("target_band_reached")
    if governing_state == "UNKNOWN":
        diagnostic_reasons.append("no_governing_state_signal_found")

    secondary_drivers = [
        item
        for item in list(active_failures) + list(active_overdesigns) + list(active_constraints)
        if item != primary_driver
    ]

    return {
        "governing_state": governing_state,
        "primary_driver": primary_driver,
        "secondary_drivers": list(dict.fromkeys(secondary_drivers)),
        "active_failures": list(active_failures),
        "active_overdesigns": list(active_overdesigns),
        "active_constraints": list(active_constraints),
        "candidate_action_required": bool(action_required),
        "exact_stop_possible": bool(exact_stop),
        "diagnostic_reasons": list(dict.fromkeys(diagnostic_reasons)),
        "target_band": {"low": float(low), "high": float(high)},
        "read_only": True,
    }


__all__ = ["classify_governing_state"]
