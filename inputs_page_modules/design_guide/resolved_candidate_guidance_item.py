"""Resolved-candidate guidance item packaging for the Inputs page Design Guide."""

from __future__ import annotations

from typing import Any


_RESOLVED_CANDIDATE_GUIDANCE_ITEM_DEPENDENCIES: tuple[str, ...] = (
    "_candidate_failure_coverage_summary",
    "_guidance_before_after_text",
    "_guidance_change_lines_for_updates",
    "_guidance_compact_change_text",
    "_guidance_compact_why_text",
    "_guidance_default_alternatives_text",
    "_guidance_expected_util_text",
    "_guidance_item",
    "_resolve_recommendation_updates",
    "_resolve_canonical_guidance_title_from_candidate",
)


def bind_resolved_candidate_guidance_item_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _RESOLVED_CANDIDATE_GUIDANCE_ITEM_DEPENDENCIES
            if name in namespace
        }
    )


def _ensure_guidance_item_resolved_candidate_payload(item: dict, state: dict | None = None) -> None:
    if not isinstance(item, dict):
        return
    action_type = str(item.get("action_type") or "").strip()
    if not action_type:
        return
    payload = dict(item.get("action_payload") or {})
    resolved_candidate = item.get("resolved_candidate")
    resolved_updates: dict = {}
    if isinstance(resolved_candidate, dict):
        candidate_updates = resolved_candidate.get("updates")
        if isinstance(candidate_updates, dict) and candidate_updates:
            resolved_updates = dict(candidate_updates)
    if not resolved_updates:
        payload_updates = payload.get("resolved_candidate_updates")
        if isinstance(payload_updates, dict) and payload_updates:
            resolved_updates = dict(payload_updates)
    if not resolved_updates:
        resolved_updates = _resolve_recommendation_updates(item, state=state)
    if not resolved_updates:
        item["has_resolved_candidate_payload"] = False
        item["action_payload"] = payload
        return
    if str(item.get("canonical_winner_label") or "").strip():
        label = str(item.get("canonical_winner_label")).strip()
    elif isinstance(resolved_candidate, dict) and str(
        resolved_candidate.get("canonical_winner_label") or "",
    ).strip():
        label = str(resolved_candidate.get("canonical_winner_label")).strip()
    else:
        label = str(
            payload.get("resolved_candidate_label")
            or item.get("title_main")
            or "Apply recommendation",
        ).strip()
    candidate_action_type = str(
        payload.get("resolved_candidate_action_type")
        or action_type
        or "apply_compound_guidance"
    ).strip()
    resolved_candidate_payload = dict(resolved_candidate or {})
    resolved_candidate_payload["updates"] = dict(resolved_updates)
    if item.get("title_locked_from_final_winner") and str(item.get("canonical_winner_label") or "").strip():
        _cl = str(item.get("canonical_winner_label")).strip()
        resolved_candidate_payload["label"] = _cl
        resolved_candidate_payload["canonical_winner_label"] = _cl
        resolved_candidate_payload["title_locked_from_final_winner"] = True
    else:
        resolved_candidate_payload["label"] = str(
            resolved_candidate_payload.get("label") or label,
        ).strip()
    resolved_candidate_payload["action_type"] = str(
        resolved_candidate_payload.get("action_type") or candidate_action_type
    ).strip()
    if payload.get("resolved_candidate_post_util") is not None:
        resolved_candidate_payload["candidate_post_util"] = payload.get("resolved_candidate_post_util")
    if payload.get("resolved_candidate_reaches_target_band") is not None:
        resolved_candidate_payload["candidate_reaches_target_band"] = bool(
            payload.get("resolved_candidate_reaches_target_band"),
        )
    payload["resolved_candidate_updates"] = dict(resolved_updates)
    payload["resolved_candidate_label"] = label
    payload["resolved_candidate_action_type"] = candidate_action_type
    payload["updates"] = dict(payload.get("updates") or resolved_updates)
    item["action_payload"] = payload
    item["resolved_candidate"] = resolved_candidate_payload
    item["has_resolved_candidate_payload"] = True


def _promote_guidance_item_to_resolved_candidate(
    item: dict | None,
    candidate: dict | None,
    *,
    state: dict,
) -> dict | None:
    if not isinstance(item, dict) or not isinstance(candidate, dict):
        return item
    updates = dict(candidate.get("updates") or {})
    if not updates:
        return item

    out = dict(item)
    payload = dict(out.get("action_payload") or {})
    original_action_type = str(
        candidate.get("action_type")
        or payload.get("resolved_candidate_action_type")
        or out.get("action_type")
        or "apply_shear_recommendation"
    ).strip()
    label = str(
        candidate.get("label")
        or payload.get("resolved_candidate_label")
        or out.get("title_main")
        or "Apply recommendation"
    ).strip()
    post_util = candidate.get("candidate_post_util", candidate.get("worst_util"))
    try:
        post_util = float(post_util) if post_util is not None else None
    except Exception:
        post_util = None
    change_lines = list(
        candidate.get("guidance_change_lines")
        or payload.get("guidance_change_lines")
        or out.get("guidance_change_lines")
        or _guidance_change_lines_for_updates(state, updates)
        or []
    )
    failure_coverage = _candidate_failure_coverage_summary(state, candidate)

    payload["resolved_candidate_updates"] = dict(updates)
    payload["resolved_candidate_label"] = label
    payload["resolved_candidate_action_type"] = original_action_type
    payload["resolved_candidate_post_util"] = post_util
    payload["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band")
        or candidate.get("reaches_target_band")
    )
    payload["updates"] = dict(payload.get("updates") or updates)
    payload["guidance_change_lines"] = list(change_lines)
    payload["failure_coverage"] = dict(failure_coverage)
    payload["covers_all_current_failures"] = bool(failure_coverage.get("covers_all_current_failures"))
    payload["covered_fail_keys"] = list(failure_coverage.get("covered_fail_keys") or [])
    payload["remaining_fail_keys"] = list(failure_coverage.get("remaining_fail_keys") or [])

    out["action_payload"] = payload
    out["action_type"] = "apply_resolved_candidate"
    out["resolved_candidate_label"] = label
    out["resolved_candidate_action_type"] = original_action_type
    out["resolved_candidate_updates"] = dict(updates)
    out["resolved_candidate_post_util"] = post_util
    out["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band")
        or candidate.get("reaches_target_band")
    )
    out["has_resolved_candidate_payload"] = True
    out["failure_coverage"] = dict(failure_coverage)
    out["covers_all_current_failures"] = bool(failure_coverage.get("covers_all_current_failures"))
    out["covered_fail_keys"] = list(failure_coverage.get("covered_fail_keys") or [])
    out["remaining_fail_keys"] = list(failure_coverage.get("remaining_fail_keys") or [])
    out["resolved_candidate"] = {
        **dict(candidate),
        "label": label,
        "action_type": original_action_type,
        "updates": dict(updates),
        "candidate_post_util": post_util,
        "candidate_reaches_target_band": bool(
            candidate.get("candidate_reaches_target_band")
            or candidate.get("reaches_target_band")
        ),
        "failure_coverage": dict(failure_coverage),
    }
    return out


def _guidance_item_from_resolved_candidate(
    candidate: dict,
    *,
    state: dict,
    overview: dict,
    title: str | None = None,
    reasoning: str | None = None,
    status: str = "FAIL",
    primary_action: str = "Apply recommendation",
) -> dict:
    if not isinstance(candidate, dict):
        return {}
    updates = dict(candidate.get("updates") or {})
    if not updates:
        return {}

    raw_label = str(
        candidate.get("resolved_candidate_label_raw")
        or candidate.get("label")
        or title
        or "Apply recommendation",
    ).strip()
    if bool(candidate.get("title_locked_from_final_winner")):
        label = str(
            candidate.get("canonical_winner_label")
            or raw_label
            or candidate.get("label")
            or "",
        ).strip() or raw_label
    else:
        label = _resolve_canonical_guidance_title_from_candidate(
            candidate,
            updates,
            state=state,
            spec_label=None,
            fallback_title=str(title or raw_label or ""),
        )
    family_tag = (
        candidate.get("recommendation_family_tag")
        or candidate.get("family_tag")
        or candidate.get("family")
        or "resolved_candidate"
    )
    subfamilies = list(candidate.get("subfamilies") or []) if isinstance(candidate.get("subfamilies"), list) else []
    alternatives_text = str(
        candidate.get("guidance_alternatives_text_compact")
        or _guidance_default_alternatives_text(state, updates, subfamilies)
        or "",
    ).strip()

    change_lines = list(
        candidate.get("guidance_change_lines")
        or candidate.get("recommendation_change_lines")
        or _guidance_change_lines_for_updates(state, updates)
        or []
    )

    candidate_post_util = candidate.get("worst_util")
    try:
        candidate_post_util = float(candidate_post_util) if candidate_post_util is not None else None
    except Exception:
        candidate_post_util = None

    resolved_action_type = "apply_resolved_candidate"
    original_candidate_action_type = str(
        candidate.get("action_type")
        or candidate.get("resolved_candidate_action_type")
        or "apply_compound_guidance"
    )

    action_payload = {
        "resolved_candidate_updates": updates,
        "resolved_candidate_label": label,
        "resolved_candidate_action_type": original_candidate_action_type,
        "resolved_candidate_family_tag": family_tag,
        "resolved_candidate_subfamilies": subfamilies,
        "resolved_candidate_post_util": candidate_post_util,
        "resolved_candidate_reaches_target_band": bool(
            candidate.get("candidate_reaches_target_band") or candidate.get("reaches_target_band")
        ),
        "force_direct_apply": True,
        "label": label,
        "updates": updates,
        "guidance_change_lines": change_lines,
        "guidance_change_summary_compact": _guidance_compact_change_text(change_lines),
        "guidance_expected_util_text": _guidance_expected_util_text(candidate_post_util),
        "guidance_why_text_compact": _guidance_compact_why_text(
            {
                "reasoning": reasoning or str(candidate.get("reasoning") or ""),
                "action_payload": {},
            },
        ),
        "guidance_alternatives_text_compact": alternatives_text,
    }
    explicit_family_fields = (
        "family_id",
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "apply_payload_family_id",
        "candidate_family_id",
        "card_family_id",
    )
    for field in explicit_family_fields:
        value = str(candidate.get(field) or "").strip()
        if value:
            action_payload[field] = value
    failure_coverage = _candidate_failure_coverage_summary(state, candidate)
    action_payload["failure_coverage"] = dict(failure_coverage)
    action_payload["compound_shear_augmented"] = bool(candidate.get("compound_shear_augmented"))
    action_payload["covers_all_current_failures"] = bool(failure_coverage.get("covers_all_current_failures"))
    action_payload["covered_fail_keys"] = list(failure_coverage.get("covered_fail_keys") or [])
    action_payload["remaining_fail_keys"] = list(failure_coverage.get("remaining_fail_keys") or [])
    candidate_search_evidence = dict(candidate.get("candidate_search_evidence") or {})
    if candidate_search_evidence:
        action_payload["candidate_search_evidence"] = dict(candidate_search_evidence)
        action_payload["source_candidate_id"] = candidate_search_evidence.get("selected_candidate_id")

    item = _guidance_item(
        "general",
        label,
        primary_action,
        None,
        reasoning or str(candidate.get("reasoning") or "This option brings the design into the target range in one move."),
        "Key levers: geometry and reinforcement updates selected by one-click convergence ranking",
        resolved_action_type,
        action_payload,
        status=status,
        util=overview.get("worst_util"),
        guidance_change_lines=change_lines,
        guidance_before_after=_guidance_before_after_text(
            {
                "action_type": resolved_action_type,
                "action_payload": action_payload,
                "recommendation_change_lines": change_lines,
            },
            state,
        ),
    )

    # Optional duplicated top-level mirrors for easier debugging only.
    item["resolved_candidate_label"] = label
    item["resolved_candidate_action_type"] = original_candidate_action_type
    item["resolved_candidate_family_tag"] = family_tag
    item["resolved_candidate_subfamilies"] = subfamilies
    item["resolved_candidate_updates"] = updates
    item["resolved_candidate_post_util"] = candidate_post_util
    item["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band") or candidate.get("reaches_target_band"),
    )
    if candidate_search_evidence:
        item["candidate_search_evidence"] = dict(candidate_search_evidence)
        item["candidate_id"] = candidate_search_evidence.get("selected_candidate_id")
        item["source_candidate_id"] = candidate_search_evidence.get("selected_candidate_id")
    for field in explicit_family_fields:
        value = str(candidate.get(field) or "").strip()
        if value:
            item[field] = value
    item["compound_shear_augmented"] = bool(candidate.get("compound_shear_augmented"))
    item["failure_coverage"] = dict(failure_coverage)
    item["covers_all_current_failures"] = bool(failure_coverage.get("covers_all_current_failures"))
    item["covered_fail_keys"] = list(failure_coverage.get("covered_fail_keys") or [])
    item["remaining_fail_keys"] = list(failure_coverage.get("remaining_fail_keys") or [])
    item["resolved_candidate"] = {
        **dict(candidate or {}),
        "label": label,
        "action_type": original_candidate_action_type,
        "updates": dict(updates),
        "candidate_post_util": candidate_post_util,
        "candidate_reaches_target_band": bool(
            candidate.get("candidate_reaches_target_band") or candidate.get("reaches_target_band"),
        ),
        "compound_shear_augmented": bool(candidate.get("compound_shear_augmented")),
        "failure_coverage": dict(failure_coverage),
        "candidate_search_evidence": dict(candidate_search_evidence),
        "candidate_id": candidate_search_evidence.get("selected_candidate_id") if candidate_search_evidence else candidate.get("candidate_id"),
        "source_candidate_id": candidate_search_evidence.get("selected_candidate_id") if candidate_search_evidence else candidate.get("source_candidate_id"),
    }
    for field in explicit_family_fields:
        value = str(candidate.get(field) or "").strip()
        if value:
            item["resolved_candidate"][field] = value
    item["resolved_candidate_title_raw"] = raw_label
    item["has_resolved_candidate_payload"] = True
    _canon = str(candidate.get("canonical_winner_label") or "").strip()
    if bool(candidate.get("title_locked_from_final_winner")) and _canon:
        item["canonical_winner_label"] = _canon
        item["title_locked_from_final_winner"] = True

    return item
