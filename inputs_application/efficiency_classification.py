"""Application-owned efficiency and non-governing family classification."""

from __future__ import annotations

import math

from inputs_application.policy_constants import EFFICIENCY_TARGET_UTIL_MIN


def overview_family_utils(overview: dict | None) -> dict[str, float]:
    source = overview if isinstance(overview, dict) else {}
    out: dict[str, float] = {}
    for key, value in dict(source.get("utils") or {}).items():
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed):
            out[str(key or "").strip().lower()] = parsed
    for key, pack in dict(source.get("packs") or {}).items():
        if not isinstance(pack, dict):
            continue
        family = str(key or "").strip().lower()
        if family == "serviceability":
            family = "deflection"
        for field in ("summary_util", "util", "governing_util", "max_util"):
            try:
                parsed = float(pack.get(field))
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                out.setdefault(family, parsed)
                break
    for family in (
        "bending",
        "shear",
        "crack",
        "deflection",
        "serviceability",
        "ductility",
    ):
        for field in (f"{family}_util", f"{family}_utilisation"):
            if family in out:
                continue
            try:
                parsed = float(source.get(field))
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                out[family] = parsed
    return out


def governing_family(
    overview: dict | None,
    family_utils: dict[str, float],
) -> str | None:
    source = overview if isinstance(overview, dict) else {}
    explicit = str(source.get("governing_family") or "").strip().lower()
    if explicit and explicit not in {
        "overview_worst_util",
        "governing",
        "overall",
    }:
        return explicit
    check = str(source.get("governing_check") or "").strip().lower()
    if "shear" in check:
        return "shear"
    if "bend" in check or "moment" in check:
        return "bending"
    if "deflect" in check:
        return "deflection"
    if "crack" in check:
        return "crack"
    if family_utils:
        try:
            return max(family_utils.items(), key=lambda item: item[1])[0]
        except Exception:
            return None
    return None


def identify_materially_overprovided_non_governing_families(
    overview: dict | None,
    *,
    threshold: float = 0.70,
) -> tuple[dict[str, float], list[str], str | None]:
    family_utils = overview_family_utils(overview)
    governing = governing_family(overview, family_utils)
    families = [
        family
        for family, util in sorted(family_utils.items())
        if family != governing
        and float(util) < float(threshold)
        and not (
            family
            in {
                "crack",
                "deflection",
                "serviceability",
                "geometry",
            }
            and float(util) <= 1e-9
        )
    ]
    return family_utils, families, governing


def is_unnecessarily_overdesigned(
    overview: dict | None,
    efficiency_state: dict | None,
    *,
    recommendation_result: dict | None = None,
) -> bool:
    del recommendation_result
    if not isinstance(overview, dict) or not bool(overview.get("all_key_pass")):
        return False
    if bool(overview.get("any_fail")):
        return False
    state = efficiency_state if isinstance(efficiency_state, dict) else {}
    classification = str(state.get("classification") or "")
    if classification in {"optimal", "very_low_demand"}:
        return False
    if classification == "inefficient":
        return True
    if bool(state.get("strongly_underutilised")):
        return True
    if bool(state.get("is_efficiency_reduction_mode")):
        try:
            worst = float(overview.get("worst_util", 0.0) or 0.0)
        except (TypeError, ValueError):
            worst = 0.0
        if worst < EFFICIENCY_TARGET_UTIL_MIN:
            return True
    return False


__all__ = [
    "governing_family",
    "identify_materially_overprovided_non_governing_families",
    "is_unnecessarily_overdesigned",
    "overview_family_utils",
]
