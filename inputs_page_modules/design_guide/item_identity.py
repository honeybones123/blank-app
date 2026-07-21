"""Design Guide item identity helpers."""

from __future__ import annotations


def _guidance_item_source_candidate_id(item: dict | None) -> str | None:
    if not isinstance(item, dict):
        return None
    payload = dict(item.get("action_payload") or {})
    resolved = dict(item.get("resolved_candidate") or {})
    for key in (
        "source_candidate_id",
        "candidate_id",
        "resolved_candidate_id",
        "local_cleanup_candidate_id",
        "canonical_candidate_id",
    ):
        value = item.get(key)
        if value is None:
            value = payload.get(key)
        if value is None:
            value = resolved.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return None


def _guidance_item_family(item: dict | None) -> str:
    if not isinstance(item, dict):
        return "unknown"
    explicit_family = str(
        item.get("selected_family_id")
        or item.get("family_id")
        or item.get("cta_family_id")
        or item.get("published_family_id")
        or ""
    ).strip()
    if not explicit_family:
        payload = dict(item.get("action_payload") or {})
        resolved = dict(item.get("resolved_candidate") or {})
        explicit_family = str(
            payload.get("selected_family_id")
            or payload.get("family_id")
            or payload.get("cta_family_id")
            or payload.get("apply_payload_family_id")
            or resolved.get("selected_family_id")
            or resolved.get("family_id")
            or resolved.get("cta_family_id")
            or resolved.get("apply_payload_family_id")
            or ""
        ).strip()
    if explicit_family in {
        "SHEAR_OVERDESIGN_GOVERNS",
        "BENDING_OVERDESIGN_GOVERNS",
        "COMBINED_OVERDESIGN",
        "COMBINED_OVERDESIGN_GOVERNS",
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    }:
        return explicit_family
    action_type = str(item.get("action_type") or "").strip()
    if action_type in {
        "apply_shear_recommendation",
        "increase_link_spacing",
        "reduce_number_of_legs",
        "reduce_link_spacing",
    }:
        return "shear"
    if action_type in {
        "apply_bottom_recommendation",
        "reduce_bottom_reinforcement",
        "reduce_bar_spacing",
        "apply_geometry_recommendation",
        "increase_depth",
        "increase_width",
        "tighten_geometry",
    }:
        return "bending"
    payload = dict(item.get("action_payload") or {})
    updates = dict(payload.get("updates") or payload.get("resolved_candidate_updates") or {})
    keys = set(updates.keys())

    shear_keys = {"lig_d", "lig_legs", "s_lig"}
    bottom_keys = {"db_bot", "db_bot_1", "db_bot_2", "bot1_count", "bot2_count", "nb_bot"}
    geom_keys = {"b", "D"}

    has_shear = bool(keys & shear_keys)
    has_bottom = bool(keys & bottom_keys)
    has_geom = bool(keys & geom_keys)

    if has_shear and (has_bottom or has_geom):
        return "combined"
    if has_shear:
        return "shear"
    if has_bottom or has_geom:
        return "bending"
    return "other"


__all__ = [
    "_guidance_item_family",
    "_guidance_item_source_candidate_id",
]
