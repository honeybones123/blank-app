"""Explicit session mutation for clearing Inputs widget cache aliases."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping


_ALIAS_WIDGET_KEYS: dict[str, tuple[str, ...]] = {
    "db_bot_1": ("inputs_db_bot_1", "inputs_nb_or_s_bot_1"),
    "db_bot_2": ("inputs_db_bot_2", "inputs_nb_or_s_bot_2"),
    "db_top_1": ("inputs_db_top_1", "inputs_nb_or_s_top_1"),
    "db_top_2": ("inputs_db_top_2", "inputs_nb_or_s_top_2"),
    "bot1_layout_mode": ("inputs_bot1_layout_mode",),
    "bot1_count": ("inputs_bot1_count",),
    "bot1_spacing": ("inputs_bot1_spacing",),
    "bot2_layout_mode": ("inputs_bot2_layout_mode",),
    "bot2_count": ("inputs_bot2_count",),
    "bot2_spacing": ("inputs_bot2_spacing",),
    "top1_layout_mode": ("inputs_top1_layout_mode",),
    "top1_count": ("inputs_top1_count",),
    "top1_spacing": ("inputs_top1_spacing",),
    "top2_layout_mode": ("inputs_top2_layout_mode",),
    "top2_count": ("inputs_top2_count",),
    "top2_spacing": ("inputs_top2_spacing",),
}
_SHEAR_WIDGET_TRIO = ("inputs_lig_d", "inputs_lig_legs", "inputs_s_lig")


def clear_inputs_widget_cache_for_shared_updates(
    session_state: MutableMapping[str, Any],
    updates: Mapping[str, Any] | None,
) -> set[str]:
    if not updates:
        return set()
    update_keys = tuple(str(key) for key in updates)
    clear_shear_trio = any(key in {"s_lig", "lig_d", "lig_legs"} for key in update_keys)
    cleared: set[str] = set()
    hydrated_map = session_state.get("_hydrated_from_shared_map")
    for key in update_keys:
        widget_keys = [f"inputs_{key}", *_ALIAS_WIDGET_KEYS.get(key, ())]
        if clear_shear_trio:
            widget_keys.extend(_SHEAR_WIDGET_TRIO)
        for widget_key in widget_keys:
            session_state.pop(widget_key, None)
            session_state.pop(f"_cached_{widget_key}", None)
            cleared.add(widget_key)
    if isinstance(hydrated_map, dict):
        for widget_key in cleared:
            hydrated_map.pop(widget_key, None)
    for key in update_keys:
        session_state.pop(f"_cached_inputs_{key}", None)
    return cleared


__all__ = ["clear_inputs_widget_cache_for_shared_updates"]
