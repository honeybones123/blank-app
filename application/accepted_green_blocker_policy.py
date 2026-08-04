"""Application-owned validation for accepted-green blocker evidence.

This policy is deliberately independent of the Design Brain package.  It
validates the evidence contract consumed by the application when deciding
whether an accepted-green blocker may be published.
"""

from __future__ import annotations

import json
from typing import Any


ACCEPTED_GREEN_EXACT_BLOCKER_REQUIRED_FIELDS = (
    "family",
    "search_ran",
    "search_exhaustive",
    "current_util",
    "threshold",
    "attempted_candidate_count",
    "executable_candidate_count",
    "target_band_candidate_count",
    "executable_target_band_candidate_count",
    "failed_candidate_id",
    "best_rejected_candidate_id",
    "attempted_updates",
    "failed_check_name",
    "failed_check_status",
    "failed_check_util",
    "failed_check_demand",
    "failed_check_capacity_or_limit",
)


def _parse_util_value(value: Any) -> float | None:
    if value in (None, "", "\u00e2\u20ac\u201d"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _normalise_blocker(blocker: dict | None) -> dict:
    if not isinstance(blocker, dict):
        return {}
    out = dict(blocker)
    family = str(out.get("family") or "").strip().lower()
    search_ran = bool(
        out.get("search_ran")
        or out.get("repair_search_ran")
        or out.get("target_band_search_ran")
        or out.get("cleanup_search_ran")
        or out.get("local_cleanup_search_ran")
        or (family and out.get(f"{family}_cleanup_search_ran"))
        or (family and out.get(f"post_click_{family}_cleanup_search_ran"))
    )
    search_exhaustive = bool(
        out.get("search_exhaustive")
        or out.get("repair_search_exhaustive")
        or out.get("target_band_search_exhaustive")
        or out.get("cleanup_search_exhaustive")
        or out.get("local_cleanup_search_exhaustive")
        or (family and out.get(f"{family}_cleanup_search_exhaustive"))
        or (family and out.get(f"post_click_{family}_cleanup_search_exhaustive"))
    )
    out["search_ran"] = bool(search_ran)
    out["search_exhaustive"] = bool(search_exhaustive)
    if search_ran:
        out.setdefault("cleanup_search_ran", True)
        out.setdefault("local_cleanup_search_ran", True)
    if search_exhaustive:
        out.setdefault("cleanup_search_exhaustive", True)
        out.setdefault("local_cleanup_search_exhaustive", True)
    out.setdefault("executable_candidate_count", out.get("executable_cleanup_count") or 0)
    out.setdefault("target_band_candidate_count", 0)
    out.setdefault("executable_target_band_candidate_count", 0)
    rejected_id = (
        out.get("failed_candidate_id")
        or out.get("best_rejected_candidate_id")
        or out.get("attempted_candidate_id")
        or out.get("no_link_candidate_id")
    )
    if rejected_id:
        out.setdefault("failed_candidate_id", rejected_id)
        out.setdefault("best_rejected_candidate_id", rejected_id)
    if out.get("failed_check_util") in (None, "", [], {}):
        out["failed_check_util"] = out.get("failed_check_value") or out.get("current_util")
    if out.get("failed_check_capacity_or_limit") in (None, "", [], {}):
        out["failed_check_capacity_or_limit"] = (
            out.get("failed_check_limit")
            or out.get("capacity_or_limit")
            or out.get("threshold")
        )
    return out


def accepted_green_exact_blocker_is_valid(blocker: dict | None) -> bool:
    """Return whether blocker evidence satisfies the publication contract."""

    blocker = _normalise_blocker(blocker)
    if not blocker:
        return False
    family = str(blocker.get("family") or "").strip().lower()
    source = str(blocker.get("source") or "").strip().lower()
    blocker_text = json.dumps(blocker, sort_keys=True, default=str).lower()
    if not family and any(
        token in blocker_text
        for token in (
            "bending",
            "bottom reinforcement",
            "bottom_reo",
            "ductility",
            "k_u",
            "ku",
            "as_min",
            "ast-min",
            "minimum tensile",
            "minimum bending",
        )
    ):
        family = "bending"
    current_util = _parse_util_value(
        blocker.get("current_util")
        if blocker.get("current_util") not in (None, "", [], {})
        else blocker.get("failed_check_util")
    )
    accepted_threshold = _parse_util_value(
        blocker.get("threshold")
        if blocker.get("threshold") not in (None, "", [], {})
        else blocker.get("failed_check_capacity_or_limit")
    )
    if not bool(blocker.get("search_ran")) or not bool(blocker.get("search_exhaustive")):
        return False
    if int(blocker.get("executable_candidate_count") or blocker.get("executable_cleanup_count") or 0) > 0:
        if not (bool(blocker.get("best_safe_candidate_applied")) and bool(blocker.get("no_second_cta_required"))):
            return False
    if (
        int(blocker.get("target_band_candidate_count") or 0) > 0
        and int(blocker.get("executable_target_band_candidate_count") or 0) > 0
    ):
        return False
    for field in ACCEPTED_GREEN_EXACT_BLOCKER_REQUIRED_FIELDS:
        value = blocker.get(field)
        if value in (None, "", [], {}) and field == "failed_check_demand":
            value = blocker.get("demand")
        if value in (None, "", [], {}) and field == "failed_check_capacity_or_limit":
            value = blocker.get("capacity_or_limit")
        if value in (None, "", [], {}):
            return False
    bending_below_accepted_threshold = (
        family == "bending"
        and current_util is not None
        and accepted_threshold is not None
        and float(current_util) < float(accepted_threshold) - 1e-9
    )
    if family == "bending" and (
        bending_below_accepted_threshold
        or source == "post_click_bending_cleanup_exhaustive_search"
        or source == "pre_render_bending_cleanup_exhaustive_search"
        or str(blocker.get("failed_check_status") or "").strip().upper()
        in {
            "BLOCKED_BY_MINIMUM_BENDING_REINFORCEMENT",
            "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD",
        }
    ):
        if not bool(blocker.get("exact_stop_cleanup_proof_chain_complete")):
            return False
        if not bool(blocker.get("every_valid_cleanup_path_exhausted_for_contract_defined_reasons")):
            return False
        if not bool(blocker.get("reo_reduction_attempted_first_for_ductility")):
            return False
        if not bool(blocker.get("width_reduction_as_min_relief_checked")):
            return False
        if not bool(blocker.get("depth_reduction_as_min_relief_checked")):
            return False
        if not bool(blocker.get("progressive_geometry_relief_exhausted_to_contract_bounds")):
            return False
        if not bool(blocker.get("width_reduction_progressive_relief_exhausted_to_contract_bounds")):
            return False
        if not bool(blocker.get("depth_reduction_progressive_relief_exhausted_to_contract_bounds")):
            return False
        if int(blocker.get("width_reduction_restarted_reinforcement_candidate_count") or 0) <= 0:
            return False
        if int(blocker.get("depth_reduction_restarted_reinforcement_candidate_count") or 0) <= 0:
            return False
        if not bool(blocker.get("bottom_reo_layer_search_restarted_after_geometry_relief")):
            return False
        if not bool(blocker.get("layer_search_restarted_after_geometry_relief")):
            return False
    reason = str(
        blocker.get("why_reduction_would_hurt_other_design_elements")
        or blocker.get("reason_reducing_this_family_would_affect_other_design_elements")
        or blocker.get("reason")
        or ""
    ).strip().lower()
    if not reason:
        return False
    if reason in {"no safe cleanup found", "candidate failed", "engineering constraint"}:
        return False
    return True


__all__ = ["accepted_green_exact_blocker_is_valid"]
