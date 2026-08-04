"""Design Guide button-contract assembly coordination."""

from __future__ import annotations

from typing import Any, Callable

from design_brain.publication import normalise_design_guide_candidate_id
from inputs_page_modules.design_guide.item_identity import (
    _guidance_item_family,
    _guidance_item_source_candidate_id,
)

_BUTTON_CONTRACT_DEPENDENCIES: tuple[str, ...] = (
    "_design_guide_preview_contract_for_updates",
    "_ensure_guidance_item_resolved_candidate_payload",
    "_guidance_executor_actionability_contract",
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


def _canonical_button_contract_family(item: dict | None, family: Any) -> str:
    raw = str(family or "").strip()
    raw_lower = raw.lower()
    raw_upper = raw.upper()
    canonical_ids = {
        "BENDING_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_OVERDESIGN_GOVERNS",
        "COMBINED_OVERDESIGN",
        "COMBINED_OVERDESIGN_GOVERNS",
        "COMBINED_BENDING_SHEAR_FAIL",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
        "GEOMETRY_DETAILING_GOVERNS",
        "SERVICEABILITY_GOVERNS",
        "LOCKED_NO_REPAIR",
    }
    if raw_upper in canonical_ids:
        return raw_upper
    item_d = dict(item or {}) if isinstance(item, dict) else {}
    selected_family = str(
        item_d.get("selected_family_id")
        or item_d.get("published_family_id")
        or item_d.get("cta_family_id")
        or item_d.get("apply_payload_family_id")
        or item_d.get("candidate_family_id")
        or item_d.get("card_family_id")
        or ""
    ).strip().upper()
    if selected_family in canonical_ids and raw_lower in {
        "",
        "bending",
        "shear",
        "combined",
        "bending_shear",
        "combined_bending_shear",
        "crack",
        "cracking",
        "deflection",
        "serviceability",
        "geometry",
        "geometry_detailing",
        "detailing",
        "spacing",
        "cover",
    }:
        return selected_family
    text = " ".join(
        str(value or "")
        for value in (
            item_d.get("selected_family_id"),
            item_d.get("published_family_id"),
            item_d.get("cta_family_id"),
            item_d.get("apply_payload_family_id"),
            item_d.get("guidance_intent"),
            item_d.get("title_main"),
            item_d.get("title"),
            item_d.get("primary_action"),
            item_d.get("secondary_action"),
            item_d.get("status"),
            item_d.get("bucket"),
        )
    ).lower()
    cleanup_intent = bool(
        "efficiency_tightening" in text
        or "optional_cleanup" in text
        or "cleanup" in text
        or "optimisation" in text
        or "optimization" in text
        or "overdesign" in text
        or "reserve is high" in text
        or "conservative" in text
    )
    if cleanup_intent and raw_lower == "bending":
        return "BENDING_OVERDESIGN_GOVERNS"
    if cleanup_intent and raw_lower == "shear":
        return "SHEAR_OVERDESIGN_GOVERNS"
    if cleanup_intent and raw_lower in {"combined", "bending_shear", "combined_bending_shear"}:
        return "COMBINED_OVERDESIGN"
    if raw_lower in {"crack", "cracking", "deflection", "serviceability"}:
        return "SERVICEABILITY_GOVERNS"
    if raw_lower in {"geometry", "geometry_detailing", "detailing", "spacing", "cover"}:
        return "GEOMETRY_DETAILING_GOVERNS"
    if raw_lower == "bending" and "bending_fail_governs" in text:
        return "BENDING_FAIL_GOVERNS"
    if raw_lower == "shear" and "shear_fail_governs" in text:
        return "SHEAR_FAIL_GOVERNS"
    if raw_lower in {"combined", "bending_shear", "combined_bending_shear"} and (
        "combined_bending_shear_fail" in text or "bending and shear" in text
    ):
        return "COMBINED_BENDING_SHEAR_FAIL"
    return raw


def _guidance_item_expected_util(item: dict | None) -> float | None:
    if not isinstance(item, dict):
        return None
    payload = item.get("action_payload")
    payload = dict(payload) if isinstance(payload, dict) else {}
    value = payload.get("expected_governing_util")
    if value is None:
        value = payload.get("resolved_candidate_post_util")
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _design_guide_button_contract(
    item: dict | None,
    *,
    state: dict,
    blocking_reason_override: str | None = None,
    preview_contract: Callable[..., tuple] | None = None,
    ensure_resolved_payload: Callable[..., None] | None = None,
    executor_contract: Callable[..., tuple] | None = None,
    resolve_updates: Callable[..., dict] | None = None,
) -> dict:
    preview_updates = (
        preview_contract or _design_guide_preview_contract_for_updates
    )
    ensure_payload = (
        ensure_resolved_payload
        or _ensure_guidance_item_resolved_candidate_payload
    )
    check_executor = (
        executor_contract or _guidance_executor_actionability_contract
    )
    resolve_item_updates = (
        resolve_updates or _resolve_recommendation_updates
    )
    action_type = str((item or {}).get("action_type") or "").strip()
    effective_action_type = action_type
    family = _canonical_button_contract_family(item, _guidance_item_family(item))
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
            ensure_payload(work, state=state)
            updates = dict(resolve_item_updates(work, state=state) or {})
            payload = dict(work.get("action_payload") or {})
            if payload.get("resolved_candidate_updates"):
                effective_action_type = "apply_resolved_candidate"
        except Exception:
            updates = {}
        if not updates:
            blocking_reason = blocking_reason or "missing_updates"
        if family == "GEOMETRY_DETAILING_GOVERNS":
            executor_allowed, executor_reason = True, None
        else:
            try:
                executor_allowed, executor_reason = check_executor(
                    work,
                    state=state,
                )
            except Exception:
                executor_allowed, executor_reason = False, "executor_contract_exception"
        if not executor_allowed:
            blocking_reason = blocking_reason or executor_reason or "executor_contract_blocked"
        if updates:
            if family == "GEOMETRY_DETAILING_GOVERNS":
                preview_pass = bool(work.get("geometry_detailing_preview_pass") is True)
                if not preview_pass:
                    blocking_reason = blocking_reason or "geometry_detailing_preview_failed"
            else:
                preview_pass, preview_util, preview_reason = preview_updates(
                    state,
                    updates,
                )
                if expected_util is None:
                    expected_util = preview_util
                if not preview_pass:
                    blocking_reason = blocking_reason or preview_reason or "preview_failed"

    source_candidate_id = normalise_design_guide_candidate_id(
        _guidance_item_source_candidate_id(item),
        family=family,
        updates=updates,
    )
    item_d = dict(item or {}) if isinstance(item, dict) else {}
    existing_contract = dict(item_d.get("button_contract") or {})
    action_payload = dict(item_d.get("action_payload") or {})
    candidate_evidence = dict(
        item_d.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or {}
    )
    family_safe_pass_fallback = bool(
        item_d.get("family_safe_pass_fallback")
        or existing_contract.get("family_safe_pass_fallback")
        or action_payload.get("family_safe_pass_fallback")
        or candidate_evidence.get("family_safe_pass_fallback")
    )
    family_safe_pass_fallback_intent = str(
        item_d.get("guidance_intent")
        or existing_contract.get("family_safe_pass_fallback_intent")
        or action_payload.get("family_safe_pass_fallback_intent")
        or candidate_evidence.get("family_safe_pass_fallback_intent")
        or ""
    ).strip()
    actionable = bool(action_type and updates and executor_allowed and not blocking_reason)
    enabled = bool(actionable and preview_pass and blocking_reason is None)
    return {
        "enabled": bool(enabled),
        "actionable": bool(actionable),
        "action_type": effective_action_type or None,
        "family": family,
        "selected_family_id": family,
        "published_family_id": family,
        "cta_family_id": family,
        "apply_payload_family_id": family,
        "updates": dict(updates),
        "preview_pass": bool(preview_pass),
        "expected_util": expected_util,
        "blocking_reason": blocking_reason,
        "source_candidate_id": source_candidate_id,
        "candidate_id": source_candidate_id,
        "family_safe_pass_fallback": family_safe_pass_fallback,
        "family_safe_pass_fallback_intent": (
            family_safe_pass_fallback_intent
            if family_safe_pass_fallback
            else None
        ),
    }


__all__ = [
    "bind_button_contract_dependencies",
    "_design_guide_button_contract",
]
