"""Auto-design candidate commit coordination for the Inputs app bridge."""

from __future__ import annotations

import sys
from typing import Any

from inputs_page_modules.debug_output import safe_debug_print


_AUTO_DESIGN_COMMIT_DEPENDENCIES: tuple[str, ...] = (
    "_agent_debug_log",
    "_apply_canonical_convenience_resync_to_shared",
    "_invalidate_design_guide_caches",
    "_normalise_invalid_shear_state_updates",
    "_set_shared_updates",
    "_shared_state_snapshot",
    "finalize_auto_design_publish",
    "st",
)


def bind_auto_design_commit_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _AUTO_DESIGN_COMMIT_DEPENDENCIES
            if name in namespace
        }
    )


def _commit_auto_design_candidate_to_shared(candidate: dict) -> dict:
    safe_debug_print(
        "DG ALT APPLY ENTRY\n"
        "function=_commit_auto_design_candidate_to_shared\n",
        file=sys.stderr,
        end="",
        flush=True,
    )
    if not candidate:
        return {}

    candidate_state = dict(candidate.get("state") or {})
    if not candidate_state:
        return {}
    pre_commit_state = _shared_state_snapshot()

    tracked_keys = [
        "b", "bw", "D", "tw", "bf", "tf", "bf_bot", "tf_bot",
        "cover_top", "cover_bot", "cover_side",
        "rowgap_top", "rowgap_bot",
        "lig_d", "lig_legs", "s_lig",
        "n_ducts", "duct_dia",
        "k_d_option", "k_v_method",
        "bot_row_count", "top_row_count",
        "bot1_layout_mode", "bot1_count", "bot1_spacing", "db_bot_1",
        "bot2_layout_mode", "bot2_count", "bot2_spacing", "db_bot_2",
        "top1_layout_mode", "top1_count", "top1_spacing", "db_top_1",
        "top2_layout_mode", "top2_count", "top2_spacing", "db_top_2",
        "bot_row_1_mode", "bot_row_1_bars", "bot_row_1_spacing", "bot_row_1_dia",
        "bot_row_2_mode", "bot_row_2_bars", "bot_row_2_spacing", "bot_row_2_dia",
        "bot_row_3_mode", "bot_row_3_bars", "bot_row_3_spacing", "bot_row_3_dia",
        "bot_row_4_mode", "bot_row_4_bars", "bot_row_4_spacing", "bot_row_4_dia",
        "top_row_1_mode", "top_row_1_bars", "top_row_1_spacing", "top_row_1_dia",
        "top_row_2_mode", "top_row_2_bars", "top_row_2_spacing", "top_row_2_dia",
        "top_row_3_mode", "top_row_3_bars", "top_row_3_spacing", "top_row_3_dia",
        "top_row_4_mode", "top_row_4_bars", "top_row_4_spacing", "top_row_4_dia",
    ]

    updates: dict[str, float | int | str | bool | None] = {}
    for key in tracked_keys:
        if key in candidate_state:
            updates[key] = candidate_state.get(key)
    updates = _normalise_invalid_shear_state_updates(
        _shared_state_snapshot(),
        updates,
        source="auto_design_commit",
    )

    _set_shared_updates(updates, source="auto_design_commit")

    hydrated_map = st.session_state.get("_hydrated_from_shared_map")
    cleared_widget_keys: set[str] = set()

    alias_widget_keys: dict[str, list[str]] = {
        "db_bot_1": ["inputs_db_bot_1", "inputs_nb_or_s_bot_1"],
        "db_bot_2": ["inputs_db_bot_2", "inputs_nb_or_s_bot_2"],
        "db_top_1": ["inputs_db_top_1", "inputs_nb_or_s_top_1"],
        "db_top_2": ["inputs_db_top_2", "inputs_nb_or_s_top_2"],
        "bot1_layout_mode": ["inputs_bot1_layout_mode"],
        "bot1_count": ["inputs_bot1_count"],
        "bot1_spacing": ["inputs_bot1_spacing"],
        "bot2_layout_mode": ["inputs_bot2_layout_mode"],
        "bot2_count": ["inputs_bot2_count"],
        "bot2_spacing": ["inputs_bot2_spacing"],
        "top1_layout_mode": ["inputs_top1_layout_mode"],
        "top1_count": ["inputs_top1_count"],
        "top1_spacing": ["inputs_top1_spacing"],
        "top2_layout_mode": ["inputs_top2_layout_mode"],
        "top2_count": ["inputs_top2_count"],
        "top2_spacing": ["inputs_top2_spacing"],
    }

    for key in list(updates.keys()):
        widget_keys_to_clear = [f"inputs_{key}"]
        widget_keys_to_clear.extend(alias_widget_keys.get(key, []))
        if key.startswith(("bot_row_", "top_row_")):
            widget_keys_to_clear.append(f"inputs_{key}")
        for widget_key in widget_keys_to_clear:
            st.session_state.pop(widget_key, None)
            st.session_state.pop(f"_cached_{widget_key}", None)
            cleared_widget_keys.add(widget_key)

    if isinstance(hydrated_map, dict):
        for key in updates:
            hydrated_map.pop(f"inputs_{key}", None)
            for widget_key in alias_widget_keys.get(key, []):
                hydrated_map.pop(widget_key, None)
        for widget_key in cleared_widget_keys:
            hydrated_map.pop(widget_key, None)

    for key in list(updates.keys()):
        st.session_state.pop(f"_cached_inputs_{key}", None)

    invalidated_recommendation_cache_keys = _invalidate_design_guide_caches(
        reason="auto_design_commit",
        updated_keys=list(updates.keys()),
        )
    _agent_debug_log(
        "Cleared row widget keys after auto-design commit",
        {
            "updated_keys": sorted(list(updates.keys())),
            "cleared_widget_keys": sorted(cleared_widget_keys),
            "remaining_inputs_bot_row_1_dia": st.session_state.get("inputs_bot_row_1_dia"),
            "shared_bot_row_1_dia": st.session_state.get("bot_row_1_dia"),
            "remaining_inputs_db_bot_1": st.session_state.get("inputs_db_bot_1"),
            "shared_db_bot_1": st.session_state.get("db_bot_1"),
        },
        location="inputs_page.py:_commit_auto_design_candidate_to_shared",
        hypothesis_id="H121",
    )
    _apply_canonical_convenience_resync_to_shared(source="auto_design_commit:canonical_convenience")
    publish_payload = finalize_auto_design_publish(
        updated_keys=sorted(list(updates.keys())),
        source="auto_design_commit",
        focus_section="shear" if any(k in {"lig_d", "lig_legs", "s_lig"} for k in updates.keys()) else None,
        set_run_design_clicked=True,
    )
    st.session_state["_commit_auto_design_candidate_to_shared_debug"] = {
        "updated_keys": sorted(list(updates.keys())),
        "invalidated_recommendation_cache_keys": invalidated_recommendation_cache_keys,
        "publish_payload": dict(publish_payload),
    }
    return updates
