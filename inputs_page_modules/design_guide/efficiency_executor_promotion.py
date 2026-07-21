"""Efficiency-card promotion to executor-backed Design Guide candidates."""

from __future__ import annotations

from typing import Any


_EFFICIENCY_EXECUTOR_PROMOTION_DEPENDENCIES: tuple[str, ...] = (
    "EFFICIENCY_TARGET_UTIL_MAX",
    "EFFICIENCY_TARGET_UTIL_MIN",
    "_design_guide_preview_contract_for_updates",
    "_evaluate_auto_design_candidate",
    "_guidance_change_lines_for_updates",
    "_guidance_executor_actionability_contract",
    "_guidance_item_is_resolved_one_click",
    "_guidance_state_snapshot",
    "_post_click_accepted_green_audit",
    "_promote_guidance_item_to_resolved_candidate",
    "_resolve_recommendation_updates",
)


def bind_efficiency_executor_promotion_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _EFFICIENCY_EXECUTOR_PROMOTION_DEPENDENCIES
            if name in namespace
        }
    )


def _try_promote_efficiency_item_to_executor_backed_candidate(
    item: dict | None,
    *,
    state: dict,
    blocked_reason: str | None = None,
) -> tuple[dict | None, dict]:
    meta: dict = {
        "attempted": False,
        "promoted": False,
        "blocked_reason": blocked_reason,
        "updates": {},
        "preview_pass": None,
        "preview_reason": None,
        "executor_allowed": None,
        "executor_reason": None,
    }
    if not isinstance(item, dict):
        meta["blocked_reason"] = "invalid_guidance_item"
        return None, meta
    if str(item.get("bucket") or "").strip().lower() != "efficiency":
        meta["blocked_reason"] = "not_efficiency_item"
        return None, meta
    if _guidance_item_is_resolved_one_click(item):
        meta["blocked_reason"] = "already_resolved_one_click"
        return item, meta
    current_state = _guidance_state_snapshot(state or {})
    try:
        updates = dict(_resolve_recommendation_updates(item, state=current_state) or {})
    except Exception:
        updates = {}
    meta["updates"] = dict(updates)
    if not updates:
        meta["blocked_reason"] = "missing_recommendation_updates"
        return None, meta
    meta["attempted"] = True
    preview_pass, preview_util, preview_reason = _design_guide_preview_contract_for_updates(
        current_state,
        updates,
    )
    meta["preview_pass"] = bool(preview_pass)
    meta["preview_reason"] = preview_reason
    meta["preview_util"] = preview_util
    if not preview_pass:
        meta["blocked_reason"] = preview_reason or "candidate_preview_failed"
        return None, meta
    try:
        final_candidate = _evaluate_auto_design_candidate(
            current_state,
            updates=updates,
            source="design_guide_executor_final_acceptance_probe",
            label=str(item.get("title_main") or "Final tightening - reduce conservative reinforcement"),
            action_type=str(item.get("action_type") or "apply_compound_guidance"),
        )
    except Exception:
        final_candidate = None
    if isinstance(final_candidate, dict):
        final_state = dict(current_state)
        final_state.update(updates)
        final_audit = _post_click_accepted_green_audit(
            dict(final_candidate.get("overview") or {}),
            blocker_source=dict(final_candidate),
            state=final_state,
        )
        meta["final_accepted_green_valid"] = bool(final_audit.get("post_click_accepted_green_valid"))
        meta["final_unresolved_low_util_families"] = list(
            final_audit.get("post_click_unresolved_low_util_families") or []
        )
        if not bool(final_audit.get("post_click_accepted_green_valid")):
            meta["blocked_reason"] = str(
                final_audit.get("post_click_accepted_green_invalid_reason")
                or "candidate_final_accepted_state_unresolved_low_util"
            )
            return None, meta

    candidate = {
        "updates": dict(updates),
        "label": str(item.get("title_main") or "Final tightening - reduce conservative reinforcement"),
        "action_type": str(item.get("action_type") or "apply_compound_guidance"),
        "candidate_post_util": preview_util,
        "worst_util": preview_util,
        "candidate_reaches_target_band": bool(
            preview_util is not None
            and float(EFFICIENCY_TARGET_UTIL_MIN) <= float(preview_util) <= float(EFFICIENCY_TARGET_UTIL_MAX)
        ),
        "guidance_change_lines": _guidance_change_lines_for_updates(current_state, updates),
    }
    promoted = _promote_guidance_item_to_resolved_candidate(
        item,
        candidate,
        state=current_state,
    )
    if not isinstance(promoted, dict):
        meta["blocked_reason"] = "candidate_promotion_failed"
        return None, meta
    allowed, executor_reason = _guidance_executor_actionability_contract(promoted, state=current_state)
    meta["executor_allowed"] = bool(allowed)
    meta["executor_reason"] = executor_reason
    if not allowed:
        meta["blocked_reason"] = executor_reason or "executor_contract_blocked"
        return None, meta
    meta["promoted"] = True
    meta["blocked_reason"] = None
    return promoted, meta
