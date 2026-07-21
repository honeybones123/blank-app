"""Guidance item display dedupe coordination."""

from __future__ import annotations

from typing import Any


_GUIDANCE_ITEM_DEDUPE_DEPENDENCIES: tuple[str, ...] = (
    "_guidance_action_updates",
    "_guidance_item_family_tag",
    "_guidance_item_payload_fingerprint",
)


def bind_guidance_item_dedupe_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _GUIDANCE_ITEM_DEDUPE_DEPENDENCIES
            if name in namespace
        }
    )


def _dedupe_guidance_items_for_display(items: list[dict], state: dict) -> tuple[list[dict], dict]:
    def _effective_updates(item: dict) -> dict:
        at = str(item.get("action_type") or "")
        pl = dict(item.get("action_payload") or {})
        if at == "apply_compound_guidance":
            return dict(pl.get("updates") or {})
        try:
            return dict(_guidance_action_updates(at, pl, state=state) or {})
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
        fp = _guidance_item_payload_fingerprint(it, state)
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
