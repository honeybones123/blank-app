"""Design Guide banner render-state comparison helpers."""

from __future__ import annotations

from typing import Any


_BANNER_RENDER_STATE_DEPENDENCIES: tuple[str, ...] = (
    "_pending_recommendation_equivalent",
)


def bind_banner_render_state_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _BANNER_RENDER_STATE_DEPENDENCIES
            if name in namespace
        }
    )


def _design_guide_banner_matches_current_render(
    banner_payload: dict | None,
    banner_meta: dict | None,
    recommendation_result: dict | None,
    pending_recommendation: dict | None,
    fingerprint: tuple | None,
) -> bool:
    if not isinstance(banner_payload, dict):
        return False
    if not isinstance(banner_meta, dict):
        return False
    if not isinstance(recommendation_result, dict) and not isinstance(pending_recommendation, dict):
        return False

    banner_fp = banner_meta.get("fingerprint")
    if banner_fp is None:
        banner_fp = banner_meta.get("baseline_fingerprint")
    if fingerprint is None or banner_fp is None or banner_fp != fingerprint:
        return False

    banner_title = str(
        banner_meta.get("recommendation_title")
        or banner_payload.get("recommendation_title")
        or banner_meta.get("title")
        or "",
    ).strip()
    banner_mode = str(banner_meta.get("recommendation_apply_mode") or "").strip()
    banner_apply_payload = dict(banner_meta.get("recommendation_apply_payload") or {})
    banner_recommendation_id = str(banner_meta.get("recommendation_id") or "").strip()

    if not banner_title:
        return False

    banner_reference: dict[str, object] = {
        "title": banner_title,
    }
    if banner_recommendation_id:
        banner_reference["recommendation_id"] = banner_recommendation_id
    if banner_mode:
        banner_reference["apply"] = {
            "mode": banner_mode,
            "payload": dict(banner_apply_payload),
        }
    elif banner_apply_payload:
        banner_reference["action_type"] = str(banner_meta.get("action_type") or "").strip()
        banner_reference["action_payload"] = dict(banner_apply_payload)
    else:
        return False

    if isinstance(pending_recommendation, dict):
        if not _pending_recommendation_equivalent(banner_reference, pending_recommendation):
            return False

    if isinstance(recommendation_result, dict):
        rr_id = str(recommendation_result.get("recommendation_id") or "").strip()
        if banner_recommendation_id and rr_id and banner_recommendation_id != rr_id:
            return False
        if not _pending_recommendation_equivalent(banner_reference, recommendation_result):
            return False

    return True
