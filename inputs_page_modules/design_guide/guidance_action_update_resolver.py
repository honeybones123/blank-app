"""Design Guide action-update resolution coordination for the Inputs page."""

from __future__ import annotations

from typing import Any


_GUIDANCE_ACTION_UPDATE_RESOLVER_DEPENDENCIES: tuple[str, ...] = (
    "REO_COUNTS_0_12",
    "REO_SPACINGS",
    "_bottom_arrangement_to_shared_updates",
    "_compute_bottom_reo_recommendation",
    "_compute_bottom_reo_tightening_recommendation",
    "_compute_geometry_recommendation",
    "_compute_geometry_tightening_recommendation",
    "_compute_shear_recommendation",
    "_compute_shear_tightening_recommendation",
    "_int_from_state",
    "_resolve_design_guide_controller_guidance_action_generated_updates",
    "_resolve_design_guide_controller_guidance_action_payload_updates",
    "_resolve_geometry_width_context",
    "_shared_state_snapshot",
    "_updates_match_state",
)


def bind_guidance_action_update_resolver_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _GUIDANCE_ACTION_UPDATE_RESOLVER_DEPENDENCIES
            if name in namespace
        }
    )


def _guidance_action_updates(action_type: str, payload: dict, *, state: dict | None = None) -> dict | None:
    current_state = state or _shared_state_snapshot()
    payload = payload or {}
    if action_type != "apply_bottom_recommendation":
        payload_resolution = _resolve_design_guide_controller_guidance_action_payload_updates(
            action_type=action_type,
            payload=payload,
        )
        if bool(payload_resolution.get("handled")):
            return payload_resolution.get("updates")

    if action_type == "apply_geometry_recommendation":
        recommendation = _compute_geometry_recommendation(current_state)
        return dict((recommendation or {}).get("updates") or {})

    if action_type == "apply_bottom_recommendation":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            bottom_update_result = _resolve_design_guide_controller_guidance_action_payload_updates(
                action_type=action_type,
                payload={
                    **dict(payload),
                    "updates_match_state": bool(_updates_match_state(current_state, explicit_updates)),
                },
            )
            if bool(bottom_update_result.get("handled")):
                return bottom_update_result.get("updates")
        recommendation = _compute_bottom_reo_recommendation(current_state)
        if recommendation and recommendation.get("updates"):
            return recommendation.get("updates")
        arrangement = (recommendation or {}).get("arrangement")
        return _bottom_arrangement_to_shared_updates(arrangement) if isinstance(arrangement, dict) else None

    if action_type == "apply_shear_recommendation":
        recommendation = _compute_shear_recommendation(current_state)
        return (recommendation or {}).get("updates")

    if action_type == "reduce_bottom_reinforcement":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict):
            if any(
                key.startswith("bot_row_") for key in explicit_updates
            ) or "bot_row_count" in explicit_updates:
                return explicit_updates
            return _bottom_arrangement_to_shared_updates(explicit_updates)
        recommendation = _compute_bottom_reo_tightening_recommendation(current_state)
        arrangement = (recommendation or {}).get("arrangement")
        return _bottom_arrangement_to_shared_updates(arrangement) if isinstance(arrangement, dict) else None

    if action_type == "increase_link_spacing":
        recommendation = _compute_shear_tightening_recommendation(current_state)
        if recommendation and recommendation.get("action_type") == "increase_link_spacing":
            return recommendation.get("updates")
        return None

    if action_type == "reduce_number_of_legs":
        recommendation = _compute_shear_tightening_recommendation(current_state)
        if recommendation and recommendation.get("action_type") == "reduce_number_of_legs":
            return recommendation.get("updates")
        return None

    if action_type == "tighten_geometry":
        recommendation = _compute_geometry_tightening_recommendation(current_state)
        return (recommendation or {}).get("updates")

    generated_payload = dict(payload)
    if action_type == "increase_width":
        width_key, _, current_width = _resolve_geometry_width_context(current_state)
        generated_payload["resolved_width_key"] = width_key
        generated_payload["current_width"] = current_width
    if action_type == "reduce_link_spacing":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            if _updates_match_state(current_state, explicit_updates):
                return None
            return dict(explicit_updates)
        generated_payload["current_spacing"] = float(current_state.get("s_lig", 200.0) or 200.0)
        generated_payload["minimum_spacing"] = float(payload.get("minimum_spacing", min(REO_SPACINGS)) or min(REO_SPACINGS))
    generated_resolution = _resolve_design_guide_controller_guidance_action_generated_updates(
        action_type=action_type,
        payload=generated_payload,
        state=current_state,
    )
    if bool(generated_resolution.get("handled")):
        generated_updates = generated_resolution.get("updates")
        if action_type == "reduce_link_spacing" and isinstance(generated_updates, dict):
            if _updates_match_state(current_state, generated_updates):
                return None
        return generated_updates

    updates: dict[str, float | int | str] = {}

    if action_type == "deflection_reduce_sustained_load":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            if _updates_match_state(current_state, explicit_updates):
                return None
            return dict(explicit_updates)
        return None

    elif action_type == "reduce_bar_spacing":
        delta_mm = float(payload.get("delta_mm", 25) or 25.0)
        minimum_spacing = float(payload.get("minimum_spacing", min(REO_SPACINGS)) or min(REO_SPACINGS))
        layout_mode = str(current_state.get("bot1_layout_mode", "Count") or "Count")
        if layout_mode == "Spacing":
            current_spacing = float(current_state.get("bot1_spacing", 200.0) or 200.0)
            new_spacing = max(minimum_spacing, current_spacing - delta_mm)
            resolved_spacing = float(int(round(new_spacing / 5.0) * 5))
            updates["bot1_spacing"] = resolved_spacing
            updates["bot_row_1_mode"] = "Spacing"
            updates["bot_row_1_spacing"] = resolved_spacing
            updates["bot_row_count"] = max(_int_from_state(current_state, "bot_row_count", 1), 1)
        else:
            current_count = int(current_state.get("bot1_count", 4) or 4)
            if current_count < max(REO_COUNTS_0_12):
                updates.update(_bottom_arrangement_to_shared_updates({
                    "bot1_count": current_count + 1,
                    "bot2_count": int(current_state.get("bot2_count", 0) or 0),
                    "db_bot_1": int(current_state.get("db_bot_1", 20) or 20),
                    "db_bot_2": int(current_state.get("db_bot_2", current_state.get("db_bot_1", 20)) or current_state.get("db_bot_1", 20)),
                }))
            else:
                current_count_2 = int(current_state.get("bot2_count", 0) or 0)
                if current_count_2 < max(REO_COUNTS_0_12):
                    updates.update(_bottom_arrangement_to_shared_updates({
                        "bot1_count": current_count,
                        "bot2_count": current_count_2 + 1,
                        "db_bot_1": int(current_state.get("db_bot_1", 20) or 20),
                        "db_bot_2": int(current_state.get("db_bot_2", current_state.get("db_bot_1", 20)) or current_state.get("db_bot_1", 20)),
                    }))

    return updates or None
