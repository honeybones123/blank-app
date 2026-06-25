"""Synthetic snapshot for the resolver no-active-failure route.

This is branch-level coverage for ``resolve_final_visible_design_guide_item``.
It does not claim the product gates naturally reach this route; it proves that
when the resolver is given a no-active-failure publication context, the route
publishes a stable final visible item and emits the expected runtime trace.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ARTIFACT_DIR = REPO / "artifacts" / "verification"
TRACE_DIR = REPO / "artifacts" / "traces"


def _stable_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _parse_util(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_trace_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 600.0,
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": 80.0,
        "uls_Vstar": 60.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
    }


def _overview(
    *,
    combined_low_util: bool = False,
    bending_cleanup_before_blocker: bool = False,
    bending_cleanup_exact_blocker: bool = False,
    low_shear_resolution: bool = False,
    low_shear_evidence_fallback: bool = False,
    low_shear_exact_blocker_fallback: bool = False,
    zero_shear_demand_accepted: bool = False,
    combined_low_util_blocker: bool = False,
    combined_low_util_best_safe: bool = False,
    debug_bundle_evidence_rebind: bool = False,
) -> dict[str, Any]:
    bending_util = 0.56 if (combined_low_util or bending_cleanup_before_blocker or bending_cleanup_exact_blocker or combined_low_util_blocker or combined_low_util_best_safe) else 0.91
    shear_util = (
        0.0
        if zero_shear_demand_accepted
        else 0.58
        if (combined_low_util or low_shear_resolution or low_shear_evidence_fallback or low_shear_exact_blocker_fallback or combined_low_util_blocker or combined_low_util_best_safe)
        else 0.88
    )
    return {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": bending_util, "shear": shear_util, "crack": 0.0, "deflection": 0.0},
        "any_fail": False,
        "all_key_pass": True,
        "worst_util": min(bending_util, shear_util),
        "governing_util": min(bending_util, shear_util),
    }


def _primary_item(
    *,
    combined_low_util: bool = False,
    safe_cleanup_before_blocker: bool = False,
    bending_cleanup_before_blocker: bool = False,
    low_shear_resolution: bool = False,
    low_shear_evidence_fallback: bool = False,
    low_shear_exact_blocker_fallback: bool = False,
    zero_shear_demand_accepted: bool = False,
    combined_low_util_blocker: bool = False,
    combined_low_util_best_safe: bool = False,
    debug_bundle_evidence_rebind: bool = False,
) -> dict[str, Any]:
    updates = {"s_lig": 180}
    candidate_id = (
        "synthetic_combined_low_util_safe_cleanup"
        if combined_low_util
        else "synthetic_combined_low_util_blocker_primary"
        if (combined_low_util_blocker or combined_low_util_best_safe)
        else "synthetic_debug_bundle_rebind_primary"
        if debug_bundle_evidence_rebind
        else "synthetic_bending_cleanup_before_blocker"
        if bending_cleanup_before_blocker
        else "synthetic_low_shear_evidence_fallback"
        if low_shear_evidence_fallback
        else "synthetic_low_shear_exact_blocker_primary"
        if low_shear_exact_blocker_fallback
        else "synthetic_zero_shear_demand_accepted_primary"
        if zero_shear_demand_accepted
        else "synthetic_low_shear_primary_blocked"
        if low_shear_resolution
        else "synthetic_safe_cleanup_before_blocker"
        if safe_cleanup_before_blocker
        else "synthetic_no_active_shear_cleanup"
    )
    family = "combined" if (combined_low_util or combined_low_util_blocker or combined_low_util_best_safe) else "bending" if bending_cleanup_before_blocker else "shear"
    evidence = {
        "source": "synthetic_no_active_route_fixture",
        "family": family,
        "selected_candidate_id": candidate_id,
        "selected_candidate_updates": {} if (bending_cleanup_before_blocker or low_shear_resolution or low_shear_exact_blocker_fallback or zero_shear_demand_accepted or combined_low_util_blocker or combined_low_util_best_safe or debug_bundle_evidence_rebind) else dict(updates),
        "selected_candidate_util": 0.89 if low_shear_evidence_fallback else 0.88 if not combined_low_util else 0.86,
        "best_safe_candidate_id": candidate_id if low_shear_evidence_fallback else None,
        "best_safe_candidate_updates": dict(updates) if low_shear_evidence_fallback else {},
        "best_safe_final_util": 0.89 if low_shear_evidence_fallback else None,
        "target_band_candidate_count": 0,
        "safe_executor_backed_candidates_count": 0 if (bending_cleanup_before_blocker or low_shear_evidence_fallback) else 1,
        "one_click_target_reaching_candidate_exists": bool(low_shear_evidence_fallback),
    }
    contract = {
        "enabled": not (safe_cleanup_before_blocker or bending_cleanup_before_blocker or low_shear_resolution or low_shear_evidence_fallback or low_shear_exact_blocker_fallback or zero_shear_demand_accepted or combined_low_util_blocker or combined_low_util_best_safe or debug_bundle_evidence_rebind),
        "actionable": not (safe_cleanup_before_blocker or bending_cleanup_before_blocker or low_shear_resolution or low_shear_evidence_fallback or low_shear_exact_blocker_fallback or zero_shear_demand_accepted or combined_low_util_blocker or combined_low_util_best_safe or debug_bundle_evidence_rebind),
        "action_type": "apply_resolved_candidate",
        "family": family,
        "updates": {} if (safe_cleanup_before_blocker or bending_cleanup_before_blocker or low_shear_resolution or low_shear_evidence_fallback or low_shear_exact_blocker_fallback or zero_shear_demand_accepted or combined_low_util_blocker or combined_low_util_best_safe or debug_bundle_evidence_rebind) else dict(updates),
        "preview_pass": not (safe_cleanup_before_blocker or bending_cleanup_before_blocker or low_shear_resolution or low_shear_evidence_fallback or low_shear_exact_blocker_fallback or zero_shear_demand_accepted or combined_low_util_blocker or combined_low_util_best_safe or debug_bundle_evidence_rebind),
        "blocking_reason": (
            "Synthetic primary is blocked so safe cleanup evidence is considered."
            if safe_cleanup_before_blocker
            else "Synthetic primary is blocked so bending cleanup evidence is considered."
            if bending_cleanup_before_blocker
            else "Synthetic primary is blocked so low-shear evidence fallback is considered."
            if low_shear_evidence_fallback
            else "Synthetic primary is blocked so residual shear exact blocker fallback is considered."
            if low_shear_exact_blocker_fallback
            else "Synthetic primary is blocked so zero-shear demand acceptance is considered."
            if zero_shear_demand_accepted
            else "Synthetic primary is blocked so low-shear cleanup evidence is considered."
            if low_shear_resolution
            else "Synthetic primary is blocked so combined exact-blocker evidence is considered."
            if (combined_low_util_blocker or combined_low_util_best_safe)
            else "Synthetic primary is blocked so debug-bundle evidence is considered."
            if debug_bundle_evidence_rebind
            else None
        ),
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "expected_util": 0.88 if not combined_low_util else 0.86,
    }
    return {
        "title_main": (
            "Combined cleanup - synthetic no-active route"
            if combined_low_util
            else "Shear cleanup - synthetic no-active route"
        ),
        "title": (
            "Combined cleanup - synthetic no-active route"
            if combined_low_util
            else "Shear cleanup - synthetic no-active route"
        ),
        "family": family,
        "check_key": family,
        "selected_action_family": family,
        "selected_family": family,
        "published_family_id": "COMBINED_NO_ACTIVE_SYNTHETIC" if combined_low_util else "SHEAR_NO_ACTIVE_SYNTHETIC",
        "apply_payload_family_id": family,
        "status": "ACTION" if not (safe_cleanup_before_blocker or bending_cleanup_before_blocker or low_shear_resolution or low_shear_evidence_fallback or low_shear_exact_blocker_fallback or zero_shear_demand_accepted or combined_low_util_blocker or combined_low_util_best_safe or debug_bundle_evidence_rebind) else "BLOCKED",
        "bucket": "pass" if not (safe_cleanup_before_blocker or bending_cleanup_before_blocker or low_shear_resolution or low_shear_evidence_fallback or low_shear_exact_blocker_fallback or zero_shear_demand_accepted or combined_low_util_blocker or combined_low_util_best_safe or debug_bundle_evidence_rebind) else "warn",
        "guidance_intent": (
            "efficiency_tightening"
            if not (safe_cleanup_before_blocker or bending_cleanup_before_blocker or low_shear_resolution or low_shear_evidence_fallback or low_shear_exact_blocker_fallback or zero_shear_demand_accepted or combined_low_util_blocker or combined_low_util_best_safe or debug_bundle_evidence_rebind)
            else "specific_blocker"
        ),
        "action_type": "apply_resolved_candidate",
        "primary_card_actionable": True,
        "updates": dict(updates),
        "selected_action_updates": dict(updates),
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "candidate_search_evidence": dict(evidence),
        "button_contract": dict(contract),
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates),
            "resolved_candidate_updates": dict(updates),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "family": family,
            "candidate_search_evidence": dict(evidence),
        },
        "resolved_candidate": {
            "updates": dict(updates),
            "family": family,
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "candidate_search_evidence": dict(evidence),
        },
    }


def _combined_low_util_item() -> dict[str, Any]:
    updates = {"s_lig": 170, "bot1_count": 5}
    evidence = {
        "source": "synthetic_combined_low_util_safe_cleanup",
        "family": "combined",
        "selected_candidate_id": "synthetic_combined_low_util_safe_cleanup",
        "selected_candidate_updates": dict(updates),
        "selected_candidate_util": 0.86,
        "target_band_candidate_count": 0,
        "safe_executor_backed_candidates_count": 1,
    }
    contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "combined",
        "updates": dict(updates),
        "preview_pass": True,
        "blocking_reason": None,
        "candidate_id": "synthetic_combined_low_util_safe_cleanup",
        "source_candidate_id": "synthetic_combined_low_util_safe_cleanup",
        "expected_util": 0.86,
    }
    return {
        "title_main": "Combined cleanup - synthetic safe one-click route",
        "title": "Combined cleanup - synthetic safe one-click route",
        "family": "combined",
        "check_key": "combined",
        "selected_action_family": "combined",
        "selected_family": "combined",
        "published_family_id": "COMBINED_LOW_UTIL_SAFE_SYNTHETIC",
        "apply_payload_family_id": "combined",
        "status": "ACTION",
        "bucket": "pass",
        "guidance_intent": "efficiency_tightening",
        "action_type": "apply_resolved_candidate",
        "primary_card_actionable": True,
        "updates": dict(updates),
        "selected_action_updates": dict(updates),
        "candidate_id": "synthetic_combined_low_util_safe_cleanup",
        "source_candidate_id": "synthetic_combined_low_util_safe_cleanup",
        "candidate_search_evidence": dict(evidence),
        "button_contract": dict(contract),
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates),
            "resolved_candidate_updates": dict(updates),
            "candidate_id": "synthetic_combined_low_util_safe_cleanup",
            "source_candidate_id": "synthetic_combined_low_util_safe_cleanup",
            "family": "combined",
            "candidate_search_evidence": dict(evidence),
        },
        "resolved_candidate": {
            "updates": dict(updates),
            "family": "combined",
            "candidate_id": "synthetic_combined_low_util_safe_cleanup",
            "source_candidate_id": "synthetic_combined_low_util_safe_cleanup",
            "candidate_search_evidence": dict(evidence),
        },
    }


def _safe_cleanup_before_blocker_item() -> dict[str, Any]:
    updates = {"s_lig": 160}
    evidence = {
        "source": "synthetic_safe_cleanup_before_blocker",
        "family": "shear",
        "selected_candidate_id": "synthetic_safe_cleanup_before_blocker",
        "selected_candidate_updates": dict(updates),
        "selected_candidate_util": 0.87,
        "target_band_candidate_count": 0,
        "safe_executor_backed_candidates_count": 1,
    }
    contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "shear",
        "updates": dict(updates),
        "preview_pass": True,
        "blocking_reason": None,
        "candidate_id": "synthetic_safe_cleanup_before_blocker",
        "source_candidate_id": "synthetic_safe_cleanup_before_blocker",
        "expected_util": 0.87,
    }
    return {
        "title_main": "Shear cleanup - synthetic safe cleanup before blocker",
        "title": "Shear cleanup - synthetic safe cleanup before blocker",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "selected_family": "shear",
        "published_family_id": "SHEAR_SAFE_CLEANUP_BEFORE_BLOCKER_SYNTHETIC",
        "apply_payload_family_id": "shear",
        "status": "ACTION",
        "bucket": "pass",
        "guidance_intent": "efficiency_tightening",
        "action_type": "apply_resolved_candidate",
        "primary_card_actionable": True,
        "updates": dict(updates),
        "selected_action_updates": dict(updates),
        "candidate_id": "synthetic_safe_cleanup_before_blocker",
        "source_candidate_id": "synthetic_safe_cleanup_before_blocker",
        "candidate_search_evidence": dict(evidence),
        "button_contract": dict(contract),
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates),
            "resolved_candidate_updates": dict(updates),
            "candidate_id": "synthetic_safe_cleanup_before_blocker",
            "source_candidate_id": "synthetic_safe_cleanup_before_blocker",
            "family": "shear",
            "candidate_search_evidence": dict(evidence),
        },
        "resolved_candidate": {
            "updates": dict(updates),
            "family": "shear",
            "candidate_id": "synthetic_safe_cleanup_before_blocker",
            "source_candidate_id": "synthetic_safe_cleanup_before_blocker",
            "candidate_search_evidence": dict(evidence),
        },
    }


def _bending_cleanup_before_blocker_item(*, exact_blocker: bool = False) -> dict[str, Any]:
    updates = {"bot1_count": 5}
    expected_util = 0.80 if exact_blocker else 0.91
    evidence = {
        "source": "synthetic_bending_cleanup_before_blocker",
        "family": "bending",
        "selected_candidate_id": "synthetic_bending_cleanup_before_blocker",
        "selected_candidate_updates": dict(updates),
        "selected_candidate_util": expected_util,
        "target_band_candidate_count": 0,
        "safe_executor_backed_candidates_count": 1,
    }
    contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "updates": dict(updates),
        "preview_pass": True,
        "blocking_reason": None,
        "candidate_id": "synthetic_bending_cleanup_before_blocker",
        "source_candidate_id": "synthetic_bending_cleanup_before_blocker",
        "expected_util": expected_util,
    }
    return {
        "title_main": "Bending cleanup - synthetic before blocker",
        "title": "Bending cleanup - synthetic before blocker",
        "family": "bending",
        "check_key": "bending",
        "selected_action_family": "bending",
        "selected_family": "bending",
        "published_family_id": "BENDING_CLEANUP_BEFORE_BLOCKER_SYNTHETIC",
        "apply_payload_family_id": "bending",
        "status": "ACTION",
        "bucket": "pass",
        "guidance_intent": "efficiency_tightening",
        "action_type": "apply_resolved_candidate",
        "primary_card_actionable": True,
        "updates": dict(updates),
        "selected_action_updates": dict(updates),
        "candidate_id": "synthetic_bending_cleanup_before_blocker",
        "source_candidate_id": "synthetic_bending_cleanup_before_blocker",
        "candidate_search_evidence": dict(evidence),
        "button_contract": dict(contract),
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates),
            "resolved_candidate_updates": dict(updates),
            "candidate_id": "synthetic_bending_cleanup_before_blocker",
            "source_candidate_id": "synthetic_bending_cleanup_before_blocker",
            "family": "bending",
            "candidate_search_evidence": dict(evidence),
        },
        "resolved_candidate": {
            "updates": dict(updates),
            "family": "bending",
            "candidate_id": "synthetic_bending_cleanup_before_blocker",
            "source_candidate_id": "synthetic_bending_cleanup_before_blocker",
            "candidate_search_evidence": dict(evidence),
        },
    }


def _bending_cleanup_exact_blocker(*args, **kwargs) -> dict[str, Any]:
    return {
        "family": "bending",
        "reason": "synthetic bending cleanup remains below accepted utilisation",
        "exact_blocker": True,
        "candidate_id": "synthetic_bending_cleanup_before_blocker",
        "selected_updates": {"bot1_count": 5},
        "current_util": kwargs.get("current_util"),
        "expected_util": kwargs.get("expected_util"),
        "target_low": kwargs.get("target_low"),
        "target_high": kwargs.get("target_high"),
        "source": "synthetic_no_active_bending_cleanup_exact_blocker_fixture",
    }


def _low_shear_resolution_item() -> dict[str, Any]:
    updates = {"s_lig": 150}
    evidence = {
        "source": "synthetic_low_shear_resolution",
        "family": "shear",
        "selected_candidate_id": "synthetic_low_shear_resolution",
        "selected_candidate_updates": dict(updates),
        "selected_candidate_util": 0.89,
        "best_safe_candidate_id": "synthetic_low_shear_resolution",
        "best_safe_candidate_updates": dict(updates),
        "best_safe_final_util": 0.89,
        "target_band_candidate_count": 1,
        "safe_executor_backed_candidates_count": 1,
        "one_click_target_reaching_candidate_exists": True,
    }
    contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "shear",
        "updates": dict(updates),
        "preview_pass": True,
        "blocking_reason": None,
        "candidate_id": "synthetic_low_shear_resolution",
        "source_candidate_id": "synthetic_low_shear_resolution",
        "expected_util": 0.89,
    }
    return {
        "title_main": "Shear cleanup - synthetic low-shear resolution",
        "title": "Shear cleanup - synthetic low-shear resolution",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "selected_family": "shear",
        "published_family_id": "SHEAR_LOW_RESOLUTION_SYNTHETIC",
        "apply_payload_family_id": "shear",
        "status": "ACTION",
        "bucket": "pass",
        "guidance_intent": "efficiency_tightening",
        "action_type": "apply_resolved_candidate",
        "primary_card_actionable": True,
        "updates": dict(updates),
        "selected_action_updates": dict(updates),
        "candidate_id": "synthetic_low_shear_resolution",
        "source_candidate_id": "synthetic_low_shear_resolution",
        "candidate_search_evidence": dict(evidence),
        "button_contract": dict(contract),
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates),
            "resolved_candidate_updates": dict(updates),
            "candidate_id": "synthetic_low_shear_resolution",
            "source_candidate_id": "synthetic_low_shear_resolution",
            "family": "shear",
            "candidate_search_evidence": dict(evidence),
        },
        "resolved_candidate": {
            "updates": dict(updates),
            "family": "shear",
            "candidate_id": "synthetic_low_shear_resolution",
            "source_candidate_id": "synthetic_low_shear_resolution",
            "candidate_search_evidence": dict(evidence),
        },
    }


def _low_shear_exact_blocker() -> dict[str, Any]:
    exact = {
        "shear": {
            "exact_blocker": True,
            "reason": "Synthetic residual shear exact blocker for no-active low-shear fixture.",
            "failed_check_name": "shear",
            "failed_check_util": 0.58,
            "attempted_candidate_count": 1,
            "previewed_candidate_count": 1,
            "target_band_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        }
    }
    return {
        "family": "shear",
        "failed_check_name": "shear",
        "failed_check_util": 0.58,
        "best_safe_candidate_applied": True,
        "exact_blocker": True,
        "exact_blockers_by_family": copy.deepcopy(exact),
        "post_click_exact_blockers_by_family": copy.deepcopy(exact),
        "cleanup_evidence_by_family": copy.deepcopy(exact),
        "post_click_cleanup_evidence_by_family": copy.deepcopy(exact),
        "reason": "Synthetic residual shear exact blocker for no-active low-shear fixture.",
    }


def _low_shear_exact_blocker_item(blocker: dict[str, Any] | None = None, *args, **kwargs) -> dict[str, Any]:
    exact = dict((blocker or {}).get("exact_blockers_by_family") or _low_shear_exact_blocker().get("exact_blockers_by_family") or {})
    evidence = {
        "source": "synthetic_low_shear_exact_blocker",
        "family": "shear",
        "exact_blocker": True,
        "exact_blockers_by_family": copy.deepcopy(exact),
        "post_click_exact_blockers_by_family": copy.deepcopy(exact),
        "cleanup_evidence_by_family": copy.deepcopy(exact),
        "post_click_cleanup_evidence_by_family": copy.deepcopy(exact),
        "safe_candidate_count": 0,
        "executable_candidate_count": 0,
        "target_band_candidate_count": 0,
    }
    disabled_contract = {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": "shear",
        "updates": {},
        "preview_pass": False,
        "expected_util": None,
        "blocking_reason": "low_shear_exact_blocker",
        "source_candidate_id": None,
        "candidate_id": None,
    }
    return {
        "title_main": "Further shear cleanup blocked - synthetic exact blocker",
        "title": "Further shear cleanup blocked - synthetic exact blocker",
        "primary_action": "Synthetic exact blocker prevents further shear cleanup.",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "selected_family": "shear",
        "published_family_id": "SHEAR_LOW_EXACT_BLOCKER_SYNTHETIC",
        "apply_payload_family_id": "shear",
        "status": "EFFICIENCY",
        "bucket": "efficiency",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "button_contract": dict(disabled_contract),
        "selected_action_updates": {},
        "updates": {},
        "action_payload": {},
        "resolved_candidate": {},
        "candidate_search_evidence": dict(evidence),
        "exact_blockers_by_family": copy.deepcopy(exact),
        "post_click_exact_blockers_by_family": copy.deepcopy(exact),
        "cleanup_evidence_by_family": copy.deepcopy(exact),
        "post_click_cleanup_evidence_by_family": copy.deepcopy(exact),
    }


def _zero_shear_accepted_item() -> dict[str, Any]:
    return {
        "title_main": "Zero shear demand accepted - synthetic no-active route",
        "title": "Zero shear demand accepted - synthetic no-active route",
        "primary_action": "No shear cleanup is required for the current demand.",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "selected_family": "shear",
        "published_family_id": "SHEAR_ZERO_DEMAND_ACCEPTED_SYNTHETIC",
        "apply_payload_family_id": "shear",
        "status": "PASS",
        "bucket": "pass",
        "guidance_intent": "accepted_state",
        "primary_card_actionable": False,
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": "shear",
            "updates": {},
            "preview_pass": True,
            "blocking_reason": None,
            "source_candidate_id": None,
            "candidate_id": None,
        },
        "selected_action_updates": {},
        "updates": {},
        "action_payload": {},
        "resolved_candidate": {},
        "candidate_search_evidence": {
            "source": "synthetic_zero_shear_demand_accepted",
            "family": "shear",
            "post_click_zero_shear_demand_accepted": True,
        },
    }


def _combined_exact_blockers() -> dict[str, dict[str, Any]]:
    return {
        "bending": {
            "exact_blocker": True,
            "reason": "Synthetic bending exact blocker for no-active combined low-util fixture.",
            "failed_check_name": "bending",
            "failed_check_util": 0.56,
            "attempted_candidate_count": 1,
            "previewed_candidate_count": 1,
            "target_band_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        },
        "shear": {
            "exact_blocker": True,
            "reason": "Synthetic shear exact blocker for no-active combined low-util fixture.",
            "failed_check_name": "shear",
            "failed_check_util": 0.58,
            "attempted_candidate_count": 1,
            "previewed_candidate_count": 1,
            "target_band_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        },
    }


def _combined_low_util_blocker_audit() -> dict[str, Any]:
    exact = _combined_exact_blockers()
    utils = {"bending": 0.56, "shear": 0.58, "crack": 0.0, "deflection": 0.0}
    return {
        "post_click_accepted_green_valid": True,
        "post_click_families_below_final_threshold": ["bending", "shear"],
        "post_click_unresolved_low_util_families": ["bending", "shear"],
        "post_click_family_utils": dict(utils),
        "post_click_exact_blockers_by_family": copy.deepcopy(exact),
        "exact_blockers_by_family": copy.deepcopy(exact),
        "post_click_cleanup_evidence_by_family": copy.deepcopy(exact),
        "cleanup_evidence_by_family": copy.deepcopy(exact),
    }


def _combined_low_util_blocker_final_item(*args, **kwargs) -> dict[str, Any]:
    audit = dict(args[2] if len(args) >= 3 and isinstance(args[2], dict) else kwargs.get("audit") or {})
    exact = dict(audit.get("post_click_exact_blockers_by_family") or audit.get("exact_blockers_by_family") or _combined_exact_blockers())
    evidence = {
        "source": "synthetic_combined_low_util_blocker",
        "family": "combined",
        "low_util_families": ["bending", "shear"],
        "exact_blockers_by_family": copy.deepcopy(exact),
        "post_click_exact_blockers_by_family": copy.deepcopy(exact),
        "cleanup_evidence_by_family": copy.deepcopy(exact),
        "post_click_cleanup_evidence_by_family": copy.deepcopy(exact),
        "safe_candidate_count": 0,
        "executable_candidate_count": 0,
        "target_band_candidate_count": 0,
    }
    disabled_contract = {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": "combined",
        "updates": {},
        "preview_pass": False,
        "expected_util": None,
        "blocking_reason": "combined_low_util_exact_blockers",
        "source_candidate_id": None,
        "candidate_id": None,
    }
    return {
        "title_main": "Further cleanup blocked - synthetic combined exact blockers",
        "title": "Further cleanup blocked - synthetic combined exact blockers",
        "primary_action": "Synthetic exact blockers prevent further bending and shear cleanup.",
        "family": "combined",
        "check_key": "combined",
        "selected_action_family": "combined",
        "selected_family": "combined",
        "published_family_id": "COMBINED_LOW_UTIL_BLOCKER_SYNTHETIC",
        "apply_payload_family_id": "combined",
        "status": "EFFICIENCY",
        "bucket": "efficiency",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "button_contract": dict(disabled_contract),
        "selected_action_updates": {},
        "updates": {},
        "action_payload": {},
        "resolved_candidate": {},
        "candidate_search_evidence": dict(evidence),
        "exact_blockers_by_family": copy.deepcopy(exact),
        "post_click_exact_blockers_by_family": copy.deepcopy(exact),
        "cleanup_evidence_by_family": copy.deepcopy(exact),
        "post_click_cleanup_evidence_by_family": copy.deepcopy(exact),
        "combined_overdesign_cleanup_final": True,
        "multi_family_blocker": True,
    }


def _debug_bundle_rebind_payload() -> dict[str, Any]:
    updates = {"s_lig": 155, "bot1_count": 5}
    evidence = {
        "source": "synthetic_debug_bundle_evidence_rebind",
        "family": "combined",
        "selected_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
        "selected_candidate_updates": dict(updates),
        "selected_candidate_util": 0.9,
        "closest_safe_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
        "closest_safe_candidate_updates": dict(updates),
        "closest_safe_candidate_util": 0.9,
        "safe_candidate_count": 1,
        "executable_candidate_count": 1,
    }
    return {"candidate_search_evidence": dict(evidence)}


def _dependencies(
    active_item: dict[str, Any],
    overview: dict[str, Any],
    *,
    combined_low_util: bool = False,
    safe_cleanup_before_blocker: bool = False,
    bending_cleanup_before_blocker: bool = False,
    bending_cleanup_exact_blocker: bool = False,
    low_shear_resolution: bool = False,
    low_shear_evidence_fallback: bool = False,
    low_shear_exact_blocker_fallback: bool = False,
    zero_shear_demand_accepted: bool = False,
    combined_low_util_blocker: bool = False,
    combined_low_util_best_safe: bool = False,
    debug_bundle_evidence_rebind: bool = False,
):
    from design_brain.publication import DesignGuidePublicationDependencies

    null = lambda *args, **kwargs: None
    false = lambda *args, **kwargs: False
    identity_state = lambda state=None, *args, **kwargs: dict(state or {})
    combined_item = _combined_low_util_item() if combined_low_util else None
    safe_cleanup_item = (
        _safe_cleanup_before_blocker_item()
        if (safe_cleanup_before_blocker or low_shear_evidence_fallback)
        else None
    )
    bending_cleanup_item = (
        _bending_cleanup_before_blocker_item(exact_blocker=bending_cleanup_exact_blocker)
        if (bending_cleanup_before_blocker or bending_cleanup_exact_blocker)
        else None
    )
    low_shear_item = _low_shear_resolution_item() if low_shear_resolution else None
    debug_overview = {
        **dict(overview),
        "any_fail": False,
        "all_key_pass": True,
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.9, "shear": 0.9, "crack": 0.0, "deflection": 0.0},
        "worst_util": 0.9,
        "governing_util": 0.9,
    }

    return DesignGuidePublicationDependencies(
        active_fail_near_current_repair_item=null,
        active_repair_with_residual_shear_target_cleanup=null,
        bending_fail_publication_snapshot_for_state=null,
        bending_only_target_band_cleanup_item=(
            (lambda *args, **kwargs: copy.deepcopy(bending_cleanup_item))
            if isinstance(bending_cleanup_item, dict)
            else null
        ),
        build_bending_check_rows_from_state=lambda *args, **kwargs: [],
        build_design_actions_context=lambda state=None, *args, **kwargs: {"state": dict(state or {})},
        build_shear_check_rows_from_state=lambda *args, **kwargs: [],
        collect_design_overview=lambda *args, **kwargs: dict(overview),
        combine_best_safe_shear_with_bending_cleanup_item=(
            (lambda *args, **kwargs: copy.deepcopy(combined_item))
            if isinstance(combined_item, dict)
            else null
        ),
        combined_low_util_exact_blocker_final_item=(
            _combined_low_util_blocker_final_item
            if (combined_low_util_blocker or combined_low_util_best_safe)
            else null
        ),
        design_guide_apply_button_contracts_to_items=lambda items, *args, **kwargs: [
            copy.deepcopy(item) for item in list(items or [])
        ],
        design_guide_preview_contract_for_updates=lambda *args, **kwargs: (True, 0.88, None),
        design_mode_config=lambda *args, **kwargs: {"target_lo": 0.85, "target_hi": 1.0},
        design_optimisation_goal=lambda *args, **kwargs: "balanced",
        direct_target_band_guidance_item=null,
        evaluate_auto_design_candidate=(
            (lambda *args, **kwargs: {"overview": dict(debug_overview), "worst_util": 0.9})
            if debug_bundle_evidence_rebind
            else (lambda *args, **kwargs: {"overview": dict(overview), "worst_util": 0.88})
        ),
        exact_cleanup_blocker_for_outside_target_action=(
            _bending_cleanup_exact_blocker if bending_cleanup_exact_blocker else null
        ),
        float_from_state=lambda state, key, default=None: _parse_util(dict(state or {}).get(key)) or default,
        guidance_change_lines_for_updates=lambda state, updates: [f"{key}: {value}" for key, value in dict(updates or {}).items()],
        guidance_cleanup_candidate_id=lambda *args, **kwargs: "synthetic_no_active_shear_cleanup",
        guidance_compact_change_text=lambda lines: "; ".join(str(line) for line in list(lines or [])),
        guidance_default_alternatives_text=lambda *args, **kwargs: "Synthetic alternatives.",
        guidance_item_from_resolved_candidate=lambda candidate, *args, **kwargs: dict(candidate or {}),
        guidance_state_snapshot=identity_state,
        local_cleanup_post_apply_acceptance_matches=(
            (lambda *args, **kwargs: True) if combined_low_util_best_safe else false
        ),
        overview_active_failure_keys=lambda ov=None: set(),
        overview_required_checks_acceptable=lambda *args, **kwargs: True,
        parse_util_value=_parse_util,
        post_active_repair_residual_shear_exact_blocker=(
            (lambda *args, **kwargs: copy.deepcopy(_low_shear_exact_blocker()))
            if low_shear_exact_blocker_fallback
            else null
        ),
        post_active_repair_target_accepted_item=(
            (lambda *args, **kwargs: copy.deepcopy(_zero_shear_accepted_item()))
            if zero_shear_demand_accepted
            else null
        ),
        post_click_accepted_green_audit=(
            (lambda *args, **kwargs: _combined_low_util_blocker_audit())
            if (combined_low_util_blocker or combined_low_util_best_safe)
            else (lambda *args, **kwargs: {})
        ),
        post_click_applied_residual_shear_exact_blocker=(
            (lambda *args, **kwargs: copy.deepcopy(_low_shear_exact_blocker()))
            if low_shear_exact_blocker_fallback
            else null
        ),
        post_click_low_bending_resolution_item=null,
        probe_equivalent_bending_cleanup_action_item=null,
        resolve_design_actions_from_state=lambda *args, **kwargs: {},
        resolve_recommendation_updates=lambda item, *args, **kwargs: dict((item or {}).get("updates") or {}),
        resolved_inputs_summary_state=lambda: ({}, {}),
        shared_state_snapshot=lambda: {},
        shear_best_safe_cleanup_item_from_evidence=(
            (lambda *args, **kwargs: copy.deepcopy(safe_cleanup_item))
            if isinstance(safe_cleanup_item, dict)
            else null
        ),
        shear_cleanup_exact_blocker_guidance_item=(
            _low_shear_exact_blocker_item if low_shear_exact_blocker_fallback else null
        ),
        shear_demands_negligible=false,
        shear_low_util_target_cleanup_item=(
            (lambda *args, **kwargs: copy.deepcopy(active_item))
            if combined_low_util
            else (lambda *args, **kwargs: copy.deepcopy(low_shear_item))
            if isinstance(low_shear_item, dict)
            else null
        ),
        suppress_design_guide_blocker_cta=false,
        updates_match_state=false,
        visible_cleanup_blocker_from_action=(
            _bending_cleanup_exact_blocker if bending_cleanup_exact_blocker else null
        ),
    )


def _trace_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    route_events = [
        row
        for row in rows
        if row.get("event") == "resolver_route"
        and (
            str(row.get("route_event") or "").startswith("no_active")
            or str(row.get("route_event") or "").startswith("return_no_active")
            or str(row.get("route_event") or "").startswith("low_shear")
            or str(row.get("route_event") or "") == "enter_no_active_failure_route"
        )
    ]
    events = [str(row.get("route_event") or "") for row in route_events]
    return_rows = [row for row in route_events if str(row.get("route_event") or "").startswith("return_no_active")]
    return_payload = dict((return_rows[-1].get("payload") if return_rows else {}) or {})
    primary_summary = dict(return_payload.get("primary") or return_payload.get("item") or {})
    return {
        "trace_row_count": len(rows),
        "no_active_event_count": len(route_events),
        "no_active_events": events,
        "route_entered": "enter_no_active_failure_route" in events,
        "return_events": [str(row.get("route_event") or "") for row in return_rows],
        "final_return_event": str(return_rows[-1].get("route_event") or "") if return_rows else None,
        "final_trace_item_hash": primary_summary.get("hash"),
        "final_trace_family": primary_summary.get("family"),
        "final_trace_selected_action_family": primary_summary.get("selected_action_family"),
        "final_trace_button_contract_enabled": primary_summary.get("button_contract_enabled"),
        "final_trace_button_contract_hash": primary_summary.get("button_contract_hash"),
        "final_trace_render_reason": return_payload.get("render_reason"),
    }


def _run_scenario(
    module: Any,
    context_type: Any,
    *,
    timestamp: str,
    name: str,
    combined_low_util: bool = False,
    safe_cleanup_before_blocker: bool = False,
    bending_cleanup_before_blocker: bool = False,
    bending_cleanup_exact_blocker: bool = False,
    low_shear_resolution: bool = False,
    low_shear_evidence_fallback: bool = False,
    low_shear_exact_blocker_fallback: bool = False,
    zero_shear_demand_accepted: bool = False,
    combined_low_util_blocker: bool = False,
    combined_low_util_best_safe: bool = False,
    debug_bundle_evidence_rebind: bool = False,
    expected_render_reason: str,
    expected_selected_action_family: str,
    expected_button_enabled: bool = True,
    expected_exact_blockers: bool = False,
    expected_final_visible_marker: bool = True,
    expected_final_visible_resolver_reason: str | None = "__expected_render_reason__",
    expected_trace_events: list[str] | None = None,
) -> dict[str, Any]:
    trace_path = TRACE_DIR / f"resolver_no_active_route_fixture_7DC_{timestamp}_{name}.jsonl"
    previous_trace_enabled = os.environ.get("DESIGN_GUIDE_RUNTIME_TRACE")
    previous_trace_scenario = os.environ.get("DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO")
    previous_trace_path = os.environ.get("DESIGN_GUIDE_RUNTIME_TRACE_PATH")
    previous_debug_bundle_present = False
    previous_debug_bundle: Any = None
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"NO_ACTIVE_FIXTURE_{name}"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)

    state = _base_state()
    if zero_shear_demand_accepted:
        state["uls_Vstar"] = 0.0
    overview = _overview(
        combined_low_util=combined_low_util,
        bending_cleanup_before_blocker=bending_cleanup_before_blocker,
        bending_cleanup_exact_blocker=bending_cleanup_exact_blocker,
        low_shear_resolution=low_shear_resolution,
        low_shear_evidence_fallback=low_shear_evidence_fallback,
        low_shear_exact_blocker_fallback=low_shear_exact_blocker_fallback,
        zero_shear_demand_accepted=zero_shear_demand_accepted,
        combined_low_util_blocker=combined_low_util_blocker,
        combined_low_util_best_safe=combined_low_util_best_safe,
        debug_bundle_evidence_rebind=debug_bundle_evidence_rebind,
    )
    primary = _primary_item(
        combined_low_util=combined_low_util,
        safe_cleanup_before_blocker=safe_cleanup_before_blocker,
        bending_cleanup_before_blocker=bending_cleanup_before_blocker,
        low_shear_resolution=low_shear_resolution,
        low_shear_evidence_fallback=low_shear_evidence_fallback,
        low_shear_exact_blocker_fallback=low_shear_exact_blocker_fallback,
        zero_shear_demand_accepted=zero_shear_demand_accepted,
        combined_low_util_blocker=combined_low_util_blocker,
        combined_low_util_best_safe=combined_low_util_best_safe,
        debug_bundle_evidence_rebind=debug_bundle_evidence_rebind,
    )

    try:
        if debug_bundle_evidence_rebind:
            import streamlit as st

            key = module.DESIGN_GUIDE_DEBUG_BUNDLE_KEY
            previous_debug_bundle_present = key in st.session_state
            previous_debug_bundle = copy.deepcopy(st.session_state.get(key)) if previous_debug_bundle_present else None
            st.session_state[key] = _debug_bundle_rebind_payload()
        result = module.resolve_final_visible_design_guide_item(
            state,
            overview,
            [copy.deepcopy(primary)],
            publication_context=context_type(
                current_summary_state=dict(state),
                current_overview=dict(overview),
                candidate_items=[copy.deepcopy(primary)],
                resolved_inputs_summary=dict(state),
                final_seed_state=dict(state),
                guidance_state_snapshot=dict(state),
                current_design_overview=dict(overview),
                direct_failure_state={},
            ),
            publication_dependencies=_dependencies(
                primary,
                overview,
                combined_low_util=combined_low_util,
                safe_cleanup_before_blocker=safe_cleanup_before_blocker,
                bending_cleanup_before_blocker=bending_cleanup_before_blocker,
                bending_cleanup_exact_blocker=bending_cleanup_exact_blocker,
                low_shear_resolution=low_shear_resolution,
                low_shear_evidence_fallback=low_shear_evidence_fallback,
                low_shear_exact_blocker_fallback=low_shear_exact_blocker_fallback,
                zero_shear_demand_accepted=zero_shear_demand_accepted,
                combined_low_util_blocker=combined_low_util_blocker,
                combined_low_util_best_safe=combined_low_util_best_safe,
                debug_bundle_evidence_rebind=debug_bundle_evidence_rebind,
            ),
        )
    finally:
        if debug_bundle_evidence_rebind:
            try:
                import streamlit as st

                key = module.DESIGN_GUIDE_DEBUG_BUNDLE_KEY
                if previous_debug_bundle_present:
                    st.session_state[key] = previous_debug_bundle
                else:
                    st.session_state.pop(key, None)
            except Exception:
                pass
        if previous_trace_enabled is None:
            os.environ.pop("DESIGN_GUIDE_RUNTIME_TRACE", None)
        else:
            os.environ["DESIGN_GUIDE_RUNTIME_TRACE"] = previous_trace_enabled
        if previous_trace_scenario is None:
            os.environ.pop("DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO", None)
        else:
            os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = previous_trace_scenario
        if previous_trace_path is None:
            os.environ.pop("DESIGN_GUIDE_RUNTIME_TRACE_PATH", None)
        else:
            os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = previous_trace_path

    rows = _load_trace_rows(trace_path)
    trace = _trace_summary(rows)
    item = dict(result.get("item") or {})
    contract = dict(item.get("button_contract") or {})
    payload = dict(item.get("action_payload") or {})
    evidence = dict(
        item.get("candidate_search_evidence")
        or payload.get("candidate_search_evidence")
        or {}
    )
    blockers = dict(item.get("exact_blockers_by_family") or {})
    post_click_blockers = dict(item.get("post_click_exact_blockers_by_family") or {})
    failures: list[str] = []
    if not trace.get("route_entered"):
        failures.append("no_active_route_not_entered")
    if result.get("render_reason") != expected_render_reason:
        failures.append("unexpected_render_reason")
    expected_resolver_reason = (
        expected_render_reason
        if expected_final_visible_resolver_reason == "__expected_render_reason__"
        else expected_final_visible_resolver_reason
    )
    if bool(item.get("final_visible_design_guide_item") is True) != bool(expected_final_visible_marker):
        failures.append("final_visible_marker_missing")
    if expected_resolver_reason is not None and item.get("final_visible_resolver_reason") != expected_resolver_reason:
        failures.append("final_visible_resolver_reason_mismatch")
    if bool(contract.get("enabled")) != bool(expected_button_enabled):
        failures.append("button_contract_enabled_mismatch")
    if bool(blockers or post_click_blockers) != bool(expected_exact_blockers):
        failures.append("exact_blocker_state_mismatch")
    if item.get("selected_action_family") != expected_selected_action_family:
        failures.append("selected_action_family_changed")
    missing_trace_events = [
        event
        for event in list(expected_trace_events or [])
        if event not in set(trace.get("no_active_events") or [])
    ]
    if missing_trace_events:
        failures.append("expected_trace_events_missing")

    return {
        "name": name,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "missing_trace_events": missing_trace_events,
        "trace_path": str(trace_path),
        "trace": trace,
        "result": {
            "render_reason": result.get("render_reason"),
            "state_fingerprint": result.get("state_fingerprint"),
            "item_hash": _stable_hash(item),
            "button_contract_hash": _stable_hash(contract),
            "action_payload_hash": _stable_hash(payload),
            "evidence_hash": _stable_hash(evidence),
            "selected_family": item.get("selected_family") or item.get("family"),
            "published_family": item.get("published_family_id"),
            "apply_family": item.get("apply_payload_family_id"),
            "selected_action_family": item.get("selected_action_family"),
            "button_contract_enabled": bool(contract.get("enabled")),
            "button_contract_actionable": bool(contract.get("actionable")),
            "button_contract_action_type": contract.get("action_type"),
            "button_contract_family": contract.get("family"),
            "button_contract_candidate_id": contract.get("candidate_id") or contract.get("source_candidate_id"),
            "exact_blocker_families": sorted(str(key) for key in blockers.keys()),
            "post_click_exact_blocker_families": sorted(str(key) for key in post_click_blockers.keys()),
            "repair_no_repair_evidence_state": {
                "has_exact_blockers": bool(blockers),
                "has_post_click_exact_blockers": bool(post_click_blockers),
                "evidence_keys": sorted(str(key) for key in evidence.keys()),
            },
        },
    }


def main() -> int:
    import inputs_page as module
    from design_brain.publication import DesignGuidePublicationContext

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    scenarios = [
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="final_primary",
            combined_low_util=False,
            expected_render_reason="final_visible_no_active_strength_fail",
            expected_selected_action_family="shear",
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="combined_low_util_safe_cleanup",
            combined_low_util=True,
            expected_render_reason="final_visible_combined_low_util_safe_cleanup",
            expected_selected_action_family="combined",
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="safe_cleanup_candidate_before_blocker",
            safe_cleanup_before_blocker=True,
            expected_render_reason="final_visible_safe_cleanup_candidate_before_blocker",
            expected_selected_action_family="shear",
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="bending_cleanup_available_before_blocker",
            bending_cleanup_before_blocker=True,
            expected_render_reason="final_visible_bending_cleanup_available_before_blocker",
            expected_selected_action_family="bending",
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="bending_cleanup_exact_blocker_before_blocker",
            bending_cleanup_before_blocker=True,
            bending_cleanup_exact_blocker=True,
            expected_render_reason="final_visible_bending_cleanup_available_before_blocker",
            expected_selected_action_family="bending",
            expected_exact_blockers=True,
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="low_shear_resolution",
            low_shear_resolution=True,
            expected_render_reason="final_visible_low_shear_resolution",
            expected_selected_action_family="shear",
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="zero_shear_demand_accepted",
            zero_shear_demand_accepted=True,
            expected_render_reason="final_visible_zero_shear_demand_accepted",
            expected_selected_action_family="shear",
            expected_button_enabled=False,
            expected_final_visible_marker=False,
            expected_final_visible_resolver_reason=None,
            expected_trace_events=[
                "low_shear_exact_blocker_decision_gate",
            ],
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="low_shear_evidence_fallback",
            low_shear_evidence_fallback=True,
            expected_render_reason="final_visible_low_shear_resolution",
            expected_selected_action_family="shear",
            expected_trace_events=[
                "low_shear_evidence_fallback_gate",
                "low_shear_evidence_fallback_result",
            ],
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="low_shear_exact_blocker_fallback",
            low_shear_exact_blocker_fallback=True,
            expected_render_reason="final_visible_low_shear_resolution",
            expected_selected_action_family="shear",
            expected_button_enabled=False,
            expected_exact_blockers=True,
            expected_trace_events=[
                "low_shear_exact_blocker_fallback_result",
            ],
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="combined_low_util_blocker",
            combined_low_util_blocker=True,
            expected_render_reason="final_visible_combined_low_util_blocker",
            expected_selected_action_family="combined",
            expected_button_enabled=False,
            expected_exact_blockers=True,
            expected_final_visible_marker=False,
            expected_final_visible_resolver_reason=None,
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="combined_low_util_best_safe",
            combined_low_util_best_safe=True,
            expected_render_reason="final_visible_combined_low_util_best_safe",
            expected_selected_action_family="combined",
            expected_button_enabled=False,
            expected_exact_blockers=True,
            expected_final_visible_marker=False,
            expected_final_visible_resolver_reason=None,
        ),
        _run_scenario(
            module,
            DesignGuidePublicationContext,
            timestamp=timestamp,
            name="debug_bundle_evidence_rebind",
            debug_bundle_evidence_rebind=True,
            expected_render_reason="final_visible_no_active_strength_fail",
            expected_selected_action_family="combined",
            expected_button_enabled=True,
        ),
    ]
    failures = [
        f"{scenario['name']}:{failure}"
        for scenario in scenarios
        for failure in list(scenario.get("failures") or [])
    ]
    status = "PASS" if not failures else "FAIL"
    primary_scenario = scenarios[0]
    report = {
        "schema": "resolver_no_active_route_fixture_snapshot.v1",
        "scope": "synthetic_branch_level_proof_not_product_path_discovery",
        "status": status,
        "failures": failures,
        "scenarios": scenarios,
        "trace_path": primary_scenario.get("trace_path"),
        "trace": primary_scenario.get("trace"),
        "result": primary_scenario.get("result"),
    }
    output = ARTIFACT_DIR / f"resolver_no_active_route_fixture_snapshot_7DC_{timestamp}.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{status}: {output}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
