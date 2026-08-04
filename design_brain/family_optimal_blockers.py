"""Family-owned optimal/no-action blocker taxonomy.

This module defines the difference between:

* unsafe/no-result blockers, which may remain BLOCKED/ERROR, and
* safe optimal exact-stop blockers, which should publish a green no-action
  Design Guide card with an engineering explanation.

It is data-only Design Brain policy. It does not import page code, render UI,
route Apply, read session state, or run engineering formulas.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from hashlib import sha256
import json
from typing import Any, Mapping


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "pass", "passed", "proven"}
    return False


def _walk_text(value: Any) -> list[str]:
    rows: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            rows.append(str(key))
            rows.extend(_walk_text(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            rows.extend(_walk_text(item))
    elif value not in (None, "", [], {}):
        rows.append(str(value))
    return rows


@dataclass(frozen=True)
class FamilyOptimalBlockerRule:
    family_id: str
    blocker_codes: tuple[str, ...]
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FamilyOptimalNoActionProof:
    family_id: str | None
    safe_optimal_no_action: bool
    safe_current_design_proven: bool
    exhaustive_search_proven: bool
    target_band_reached: bool
    exact_stop_proven: bool
    family_blocker_codes: tuple[str, ...] = ()
    family_blocker_reasons: tuple[str, ...] = ()
    unsafe_reasons: tuple[str, ...] = ()
    proof_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


FAMILY_OPTIMAL_BLOCKERS: dict[str, FamilyOptimalBlockerRule] = {
    "BENDING_OVERDESIGN_GOVERNS": FamilyOptimalBlockerRule(
        family_id="BENDING_OVERDESIGN_GOVERNS",
        blocker_codes=(
            "AST_MIN_GOVERNS",
            "KU_GOVERNS_AFTER_REO_AND_GEOMETRY_EXHAUSTED",
            "GEOMETRY_LOCKED",
            "WIDTH_LOCKED",
            "DEPTH_LOCKED",
            "REINFORCEMENT_LOCKED",
            "BAR_FIT_BLOCKED",
            "SPACING_BLOCKED",
            "SERVICEABILITY_BLOCKED",
            "DETAILING_BLOCKED",
            "NO_SMALLER_SAFE_REO_ARRANGEMENT",
        ),
        description="Bending cleanup may stop outside target only after reo reduction, geometry relief, and restarted arrangement search are exhausted.",
    ),
    "SHEAR_OVERDESIGN_GOVERNS": FamilyOptimalBlockerRule(
        family_id="SHEAR_OVERDESIGN_GOVERNS",
        blocker_codes=(
            "MIN_SHEAR_REO_GOVERNS",
            "ZERO_SHEAR_LIGATURES_REMOVED_OR_PROVEN_REQUIRED",
            "LINKS_ALREADY_REMOVED",
            "SPACING_MAX_GOVERNS",
            "LEG_COUNT_MIN_GOVERNS",
            "BAR_SIZE_MIN_GOVERNS",
            "GEOMETRY_LOCKED",
            "WIDTH_REDUCTION_BLOCKED",
            "DEPTH_REDUCTION_BLOCKED",
            "BENDING_WOULD_FAIL",
            "SERVICEABILITY_BLOCKED",
            "DETAILING_BLOCKED",
        ),
        description="Shear cleanup may stop outside target only after ligature cleanup and allowed geometry/detailing reductions are exhausted.",
    ),
    "COMBINED_OVERDESIGN": FamilyOptimalBlockerRule(
        family_id="COMBINED_OVERDESIGN",
        blocker_codes=(
            "COMBINED_SEARCH_EXHAUSTED",
            "BENDING_BLOCKER_GOVERNS",
            "SHEAR_BLOCKER_GOVERNS",
            "GEOMETRY_LOCKED",
            "REINFORCEMENT_LOCKED",
            "SERVICEABILITY_BLOCKED",
            "DETAILING_BLOCKED",
            "NO_SAFE_FOLDED_CLEANUP",
        ),
        description="Combined cleanup may stop only after coupled bending, shear, geometry, and reinforcement cleanup are exhausted.",
    ),
    "COMBINED_OVERDESIGN_GOVERNS": FamilyOptimalBlockerRule(
        family_id="COMBINED_OVERDESIGN_GOVERNS",
        blocker_codes=(
            "COMBINED_SEARCH_EXHAUSTED",
            "BENDING_BLOCKER_GOVERNS",
            "SHEAR_BLOCKER_GOVERNS",
            "GEOMETRY_LOCKED",
            "REINFORCEMENT_LOCKED",
            "SERVICEABILITY_BLOCKED",
            "DETAILING_BLOCKED",
            "NO_SAFE_FOLDED_CLEANUP",
        ),
        description="Combined cleanup may stop only after coupled bending, shear, geometry, and reinforcement cleanup are exhausted.",
    ),
    "MIN_BENDING_REO_GOVERNS": FamilyOptimalBlockerRule(
        family_id="MIN_BENDING_REO_GOVERNS",
        blocker_codes=("AST_MIN_GOVERNS", "NO_SAFE_GEOMETRY_RELIEF", "GEOMETRY_LOCKED"),
        description="Minimum bending reinforcement can explain residual overcapacity only after valid relief paths are exhausted.",
    ),
    "MIN_SHEAR_REO_GOVERNS": FamilyOptimalBlockerRule(
        family_id="MIN_SHEAR_REO_GOVERNS",
        blocker_codes=("MIN_SHEAR_REO_GOVERNS", "LINKS_REQUIRED_BY_CODE", "GEOMETRY_LOCKED"),
        description="Minimum shear reinforcement can explain residual overcapacity only after valid cleanup paths are exhausted.",
    ),
    "TARGET_BAND_REACHED": FamilyOptimalBlockerRule(
        family_id="TARGET_BAND_REACHED",
        blocker_codes=("TARGET_BAND_REACHED",),
        description="No blocker required because the design is already in the target band.",
    ),
    "EXACT_STOP_PROVEN": FamilyOptimalBlockerRule(
        family_id="EXACT_STOP_PROVEN",
        blocker_codes=("EXACT_STOP_PROVEN", "EXHAUSTIVE_SEARCH_PROVEN"),
        description="Exact stop is green when the design is safe and all valid improvement paths were exhausted.",
    ),
}


_UNSAFE_TEXT_MARKERS = (
    "family contract violation",
    "missing_updates",
    "missing update",
    "stale_primary_design_guide_payload",
    "preview did not pass",
    "unsafe",
    "under_capacity",
    "capacity is low",
    "active failure",
    "failing",
    "failed utilisation",
    "no repair proof",
)

_SAFE_STATUS_MARKERS = ("PASS", "GOOD", "OK", "ACCEPTED", "NEAR_LIMIT", "NEAR LIMIT")

_EXHAUSTIVE_KEYS = (
    "repair_search_exhaustive",
    "cleanup_search_exhaustive",
    "local_cleanup_search_exhaustive",
    "target_band_search_exhaustive",
    "search_exhaustive",
    "all_paths_exhausted",
    "exhausted",
)

_EXACT_STOP_KEYS = (
    "exact_stop_proven",
    "exact_stop",
    "exact_stop_proof",
    "exact_blocker_proof",
    "exact_blockers_by_family",
    "post_click_exact_blockers_by_family",
)


def family_optimal_blocker_contract() -> dict[str, Any]:
    return {
        "schema": "design_brain.family_optimal_blockers.v1",
        "meaning": "safe no-action exact-stop blockers publish as green optimal, not red blocked",
        "families": {family: rule.to_dict() for family, rule in FAMILY_OPTIMAL_BLOCKERS.items()},
    }


def _collect_blocker_reasons(*sources: Any) -> tuple[str, ...]:
    reasons: list[str] = []
    for source in sources:
        source_d = _mapping(source)
        for key in (
            "outside_target_band_allowed_reason",
            "active_under_capacity_blocker_reason",
            "blocker_reason",
            "blocking_reason",
            "exact_blocker_reason",
            "no_valid_repair_reason",
            "exhausted_reason",
        ):
            value = _text(source_d.get(key))
            if value:
                reasons.append(value)
        for key in (
            "blocker_reasons_by_family",
            "exact_blocker_reasons_by_family",
            "failed_candidate_reasons",
            "rejected_target_band_candidate_reasons",
        ):
            value = source_d.get(key)
            if isinstance(value, Mapping):
                reasons.extend(_text(item) for item in value.values() if _text(item))
            elif isinstance(value, (list, tuple)):
                reasons.extend(_text(item) for item in value if _text(item))
        for key in ("exact_blockers_by_family", "post_click_exact_blockers_by_family"):
            value = source_d.get(key)
            if isinstance(value, Mapping):
                for item in value.values():
                    item_d = _mapping(item)
                    reason = _text(item_d.get("reason") or item_d.get("blocker") or item_d.get("code"))
                    if reason:
                        reasons.append(reason)
    seen: set[str] = set()
    out: list[str] = []
    for reason in reasons:
        normalised = " ".join(reason.split())
        if normalised and normalised.lower() not in seen:
            seen.add(normalised.lower())
            out.append(normalised)
    return tuple(out)


def _detect_blocker_codes(family_id: str | None, reasons: tuple[str, ...], *sources: Any) -> tuple[str, ...]:
    family = str(family_id or "").strip().upper()
    allowed = set((FAMILY_OPTIMAL_BLOCKERS.get(family) or FamilyOptimalBlockerRule(family, (), "")).blocker_codes)
    text = " ".join([*reasons, *_walk_text(list(sources))]).lower()
    candidates: set[str] = set()
    keyword_map = {
        "AST_MIN_GOVERNS": ("as_min", "ast_min", "minimum tensile", "minimum bending reinforcement"),
        "KU_GOVERNS_AFTER_REO_AND_GEOMETRY_EXHAUSTED": ("ku", "k_u", "ductility", "neutral axis"),
        "GEOMETRY_LOCKED": ("geometry locked", "geometry_lock", "locked geometry"),
        "WIDTH_LOCKED": ("width locked", "width_lock"),
        "DEPTH_LOCKED": ("depth locked", "depth_lock"),
        "REINFORCEMENT_LOCKED": ("reo locked", "reinforcement locked", "rebar locked"),
        "BAR_FIT_BLOCKED": ("bar fit", "cannot fit", "fit blocked"),
        "SPACING_BLOCKED": ("spacing", "clear spacing"),
        "SERVICEABILITY_BLOCKED": ("serviceability", "crack", "deflection"),
        "DETAILING_BLOCKED": ("detailing", "cover", "ligature fit"),
        "MIN_SHEAR_REO_GOVERNS": ("minimum shear", "min shear"),
        "LINKS_ALREADY_REMOVED": ("links already removed", "ligatures already removed", "removed"),
        "SPACING_MAX_GOVERNS": ("maximum spacing", "spacing max"),
        "LEG_COUNT_MIN_GOVERNS": ("minimum legs", "leg count"),
        "BAR_SIZE_MIN_GOVERNS": ("minimum bar", "bar size"),
        "BENDING_WOULD_FAIL": ("bending would fail", "bending fail"),
        "COMBINED_SEARCH_EXHAUSTED": ("combined", "exhausted"),
        "NO_SAFE_FOLDED_CLEANUP": ("folded", "no safe"),
        "EXACT_STOP_PROVEN": ("exact stop", "exact_stop"),
        "EXHAUSTIVE_SEARCH_PROVEN": ("exhaustive", "exhausted"),
        "TARGET_BAND_REACHED": ("target band",),
    }
    for code, markers in keyword_map.items():
        if allowed and code not in allowed:
            continue
        if any(marker in text for marker in markers):
            candidates.add(code)
    for code in allowed:
        if code.lower() in text:
            candidates.add(code)
    return tuple(sorted(candidates))


def build_family_optimal_no_action_proof(
    *,
    family_id: str | None,
    cta_enabled: bool = False,
    item: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    exact_stop_proof: dict[str, Any] | None = None,
    target_band_proof: dict[str, Any] | None = None,
) -> FamilyOptimalNoActionProof:
    family = str(family_id or "").strip().upper() or None
    item_d = _mapping(item)
    evidence_d = _mapping(evidence)
    exact_d = _mapping(exact_stop_proof)
    target_d = _mapping(target_band_proof)

    all_text = " ".join(_walk_text({"item": item_d, "evidence": evidence_d, "exact": exact_d})).lower()
    unsafe_reasons: list[str] = []
    if cta_enabled:
        unsafe_reasons.append("cta_is_enabled")
    if any(marker in all_text for marker in _UNSAFE_TEXT_MARKERS):
        # Exact-stop families may contain words like "failed candidate" in
        # rejected-candidate evidence; only treat this as unsafe when the item
        # itself is not visibly safe.
        item_status = str(item_d.get("status") or item_d.get("critical_status") or "").strip().upper()
        if item_status not in _SAFE_STATUS_MARKERS:
            unsafe_reasons.append("unsafe_or_failure_marker_present")
    if item_d.get("family_match_violation_reason") or "contract violation" in all_text:
        unsafe_reasons.append("family_contract_violation")

    status_values = {
        str(item_d.get("status") or "").strip().upper(),
        str(item_d.get("critical_status") or "").strip().upper(),
        str(item_d.get("badge") or "").strip().upper(),
    }
    safe_current = bool(status_values & set(_SAFE_STATUS_MARKERS)) or _truthy(evidence_d.get("all_checks_pass"))
    target_reached = _truthy(target_d.get("target_band_reached")) or _truthy(
        evidence_d.get("candidate_reaches_target_band")
    )
    exhaustive = any(_truthy(evidence_d.get(key)) or _truthy(exact_d.get(key)) for key in _EXHAUSTIVE_KEYS)
    exact_stop = bool(exact_d) or any(_truthy(evidence_d.get(key)) for key in _EXACT_STOP_KEYS)
    reasons = _collect_blocker_reasons(evidence_d, exact_d, item_d)
    codes = _detect_blocker_codes(family, reasons, evidence_d, exact_d, item_d)
    family_has_taxonomy = family in FAMILY_OPTIMAL_BLOCKERS

    safe_optimal = (
        not unsafe_reasons
        and not cta_enabled
        and safe_current
        and (
            target_reached
            or (
                family_has_taxonomy
                and (exact_stop or exhaustive)
                and (bool(codes) or bool(reasons))
            )
        )
    )
    payload = {
        "family_id": family,
        "safe_optimal_no_action": safe_optimal,
        "safe_current_design_proven": safe_current,
        "exhaustive_search_proven": exhaustive,
        "target_band_reached": target_reached,
        "exact_stop_proven": exact_stop,
        "family_blocker_codes": codes,
        "family_blocker_reasons": reasons,
        "unsafe_reasons": tuple(unsafe_reasons),
    }
    return FamilyOptimalNoActionProof(
        family_id=family,
        safe_optimal_no_action=safe_optimal,
        safe_current_design_proven=safe_current,
        exhaustive_search_proven=exhaustive,
        target_band_reached=target_reached,
        exact_stop_proven=exact_stop,
        family_blocker_codes=codes,
        family_blocker_reasons=reasons,
        unsafe_reasons=tuple(unsafe_reasons),
        proof_hash=_stable_hash(payload),
    )
