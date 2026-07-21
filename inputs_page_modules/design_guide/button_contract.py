"""Design Guide button-contract assembly coordination."""

from __future__ import annotations

from typing import Any


_BUTTON_CONTRACT_DEPENDENCIES: tuple[str, ...] = (
    "_design_guide_preview_contract_for_updates",
    "_ensure_guidance_item_resolved_candidate_payload",
    "_guidance_executor_actionability_contract",
    "_guidance_item_expected_util",
    "_guidance_item_family",
    "_guidance_item_source_candidate_id",
    "_normalise_design_guide_candidate_id",
    "_resolve_recommendation_updates",
)


def bind_button_contract_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _BUTTON_CONTRACT_DEPENDENCIES
            if name in namespace
        }
    )


def _design_guide_button_contract(
    item: dict | None,
    *,
    state: dict,
    blocking_reason_override: str | None = None,
) -> dict:
    action_type = str((item or {}).get("action_type") or "").strip()
    effective_action_type = action_type
    family = _guidance_item_family(item)
    updates: dict = {}
    expected_util = _guidance_item_expected_util(item)
    preview_pass = False
    blocking_reason = str(blocking_reason_override or "").strip() or None
    executor_allowed = False
    executor_reason: str | None = None

    if not isinstance(item, dict):
        blocking_reason = blocking_reason or "invalid_guidance_item"
    elif not action_type:
        blocking_reason = blocking_reason or "missing_action_type"
    else:
        work = dict(item)
        work["action_payload"] = dict(work.get("action_payload") or {})
        try:
            _ensure_guidance_item_resolved_candidate_payload(work, state=state)
            updates = dict(_resolve_recommendation_updates(work, state=state) or {})
            payload = dict(work.get("action_payload") or {})
            if payload.get("resolved_candidate_updates"):
                effective_action_type = "apply_resolved_candidate"
        except Exception:
            updates = {}
        if not updates:
            blocking_reason = blocking_reason or "missing_updates"
        try:
            executor_allowed, executor_reason = _guidance_executor_actionability_contract(
                work,
                state=state,
            )
        except Exception:
            executor_allowed, executor_reason = False, "executor_contract_exception"
        if not executor_allowed:
            blocking_reason = blocking_reason or executor_reason or "executor_contract_blocked"
        if updates:
            preview_pass, preview_util, preview_reason = _design_guide_preview_contract_for_updates(
                state,
                updates,
            )
            if expected_util is None:
                expected_util = preview_util
            if not preview_pass:
                blocking_reason = blocking_reason or preview_reason or "preview_failed"

    source_candidate_id = _normalise_design_guide_candidate_id(
        _guidance_item_source_candidate_id(item),
        family=family,
        updates=updates,
    )
    actionable = bool(action_type and updates and executor_allowed and not blocking_reason)
    return {
        "actionable": bool(actionable),
        "action_type": effective_action_type or None,
        "family": family,
        "updates": dict(updates),
        "preview_pass": bool(preview_pass),
        "expected_util": expected_util,
        "blocking_reason": blocking_reason,
        "source_candidate_id": source_candidate_id,
        "candidate_id": source_candidate_id,
    }


__all__ = [
    "bind_button_contract_dependencies",
    "_design_guide_button_contract",
]
