"""Guidance item display dedupe coordination."""

from __future__ import annotations

from typing import Any, Callable

from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.state_utils import (
    float_from_state,
    guidance_state_snapshot,
)
from inputs_page_modules.design_guide.update_families import (
    _compound_subfamilies_from_updates,
)

_GUIDANCE_ITEM_DEDUPE_DEPENDENCIES: tuple[str, ...] = (
    "_guidance_action_updates",
)


def bind_guidance_item_dedupe_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _GUIDANCE_ITEM_DEDUPE_DEPENDENCIES
            if name in namespace
        }
    )


def _guidance_item_payload_fingerprint(
    item: dict,
    state: dict,
    *,
    action_updates: Callable[..., dict | None],
) -> tuple:
    action_type = str(item.get("action_type") or "")
    payload = dict(item.get("action_payload") or {})

    def _normalise(value: object) -> object:
        if isinstance(value, float):
            return round(value, 4)
        if isinstance(value, (int, str, bool)) or value is None:
            return value
        return str(value)

    if action_type == "apply_compound_guidance":
        updates = dict(payload.get("updates") or {})
        return (
            "apply_compound_guidance",
            tuple(
                sorted(
                    (key, _normalise(updates[key]))
                    for key in sorted(updates)
                )
            ),
        )
    try:
        updates = action_updates(
            action_type,
            payload,
            state=state,
        ) or {}
    except Exception:
        updates = {}
    return (
        action_type,
        tuple(
            sorted(
                (key, _normalise(updates[key]))
                for key in sorted(updates)
            )
        ),
    )


def _compound_geometry_deltas(
    state: dict,
    updates: dict,
) -> tuple[float, float, float, float]:
    baseline = guidance_state_snapshot(state)
    candidate = dict(baseline)
    candidate.update(updates)
    depth_before = float(float_from_state(baseline, "D", 0.0) or 0.0)
    depth_after = float(
        float_from_state(candidate, "D", depth_before) or depth_before
    )
    _, _, width_before_raw = resolve_geometry_width_context(baseline)
    width_before = float(width_before_raw or 0.0)
    _, _, width_after_raw = resolve_geometry_width_context(candidate)
    width_after = float(width_after_raw or width_before)
    return depth_before, depth_after, width_before, width_after


def _family_tag_from_compound_updates(updates: dict, state: dict) -> str:
    subfamilies = set(_compound_subfamilies_from_updates(updates))
    if subfamilies >= {"geometry", "bottom_reo"}:
        depth_before, depth_after, width_before, width_after = (
            _compound_geometry_deltas(state, updates)
        )
        if (
            depth_after > depth_before + 0.5
            and width_after > width_before + 0.5
        ):
            return "compound_depth_width_bottom"
        if depth_after > depth_before + 0.5:
            return "compound_depth_bottom"
        if width_after > width_before + 0.5:
            return "compound_width_bottom"
        return "compound_geometry_bottom"
    if subfamilies >= {"shear", "bottom_reo"}:
        return "shear_bottom_compound"
    if subfamilies >= {"geometry", "shear"}:
        return "compound_geometry_shear"
    return "compound_other"


def _guidance_item_family_tag(item: dict, state: dict) -> str:
    action_type = str(item.get("action_type") or "")
    payload = dict(item.get("action_payload") or {})
    if action_type == "apply_compound_guidance":
        return _family_tag_from_compound_updates(
            dict(payload.get("updates") or {}),
            state,
        )
    if action_type == "apply_bottom_recommendation":
        return "pure_bottom_reo"
    if action_type == "increase_width":
        return "pure_geometry_width"
    if action_type == "increase_depth":
        return "pure_geometry_depth"
    if action_type in ("apply_geometry_recommendation", "tighten_geometry"):
        return "geometry_recommendation"
    if action_type in (
        "apply_shear_recommendation",
        "increase_link_spacing",
        "reduce_number_of_legs",
        "reduce_link_spacing",
    ):
        return "shear_adjust"
    if action_type == "apply_mode_recommendation":
        return "mode_guidance"
    if action_type == "reduce_bottom_reinforcement":
        return "bottom_reduction"
    return action_type or "unknown"


def _dedupe_guidance_items_for_display(
    items: list[dict],
    state: dict,
    *,
    action_updates: Callable[..., dict | None] | None = None,
) -> tuple[list[dict], dict]:
    resolve_action_updates = action_updates or _guidance_action_updates

    def _effective_updates(item: dict) -> dict:
        at = str(item.get("action_type") or "")
        pl = dict(item.get("action_payload") or {})
        if at == "apply_compound_guidance":
            return dict(pl.get("updates") or {})
        try:
            return dict(resolve_action_updates(at, pl, state=state) or {})
        except Exception:
            return {}

    def _materially_distinct(a: dict, b: dict) -> bool:
        if str(a.get("check_key") or "") != str(b.get("check_key") or ""):
            return True
        fa = _guidance_item_family_tag(a, state)
        fb = _guidance_item_family_tag(b, state)
        if fa == fb:
            return False
        ua = _effective_updates(a)
        ub = _effective_updates(b)
        if not ua and not ub:
            return False
        ka = set(ua.keys())
        kb = set(ub.keys())
        if not ka and not kb:
            return False
        if ka == kb:
            # Same changed fields is usually a wording variant; keep one.
            return False
        overlap = len(ka & kb)
        union = max(len(ka | kb), 1)
        overlap_ratio = float(overlap) / float(union)
        if overlap_ratio >= 0.75:
            return False
        return True

    before = len(items)
    dropped: list[dict] = []
    out: list[dict] = []
    seen: set[tuple] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        fp = _guidance_item_payload_fingerprint(
            it,
            state,
            action_updates=resolve_action_updates,
        )
        if fp in seen:
            dropped.append(
                {
                    "title_main": it.get("title_main"),
                    "action_type": it.get("action_type"),
                    "dropped_reason": "duplicate_action_payload",
                    "family_tag": _guidance_item_family_tag(it, state),
                },
            )
            continue
        seen.add(fp)
        if out and (not _materially_distinct(out[0], it)):
            dropped.append(
                {
                    "title_main": it.get("title_main"),
                    "action_type": it.get("action_type"),
                    "dropped_reason": "near_duplicate_primary_overlap",
                    "family_tag": _guidance_item_family_tag(it, state),
                },
            )
            continue
        out.append(it)
    if len(out) > 2:
        for it in out[2:]:
            dropped.append(
                {
                    "title_main": it.get("title_main"),
                    "action_type": it.get("action_type"),
                    "dropped_reason": "only_primary_and_one_distinct_alternative_allowed",
                    "family_tag": _guidance_item_family_tag(it, state),
                },
            )
        out = out[:2]
    return out, {
        "guidance_items_before_dedupe_count": before,
        "guidance_items_after_dedupe_count": len(out),
        "dropped_guidance_items_summary": dropped,
        "primary_card_family_tag": _guidance_item_family_tag(out[0], state) if out else None,
        "secondary_card_family_tag": _guidance_item_family_tag(out[1], state) if len(out) > 1 else None,
        "secondary_card_materially_distinct": bool(len(out) > 1),
    }
