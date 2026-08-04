"""Application-owned geometry trial updates used by bottom recommendations."""

from __future__ import annotations

from inputs_application.legacy_design_brain_adapter import (
    resolve_design_guide_controller_guidance_action_generated_updates,
)
from inputs_application.geometry_search_policy import (
    rescue_geometry_width_for_depth_ratio,
)
from inputs_application.recommendation_support import resolve_geometry_width_context


def bottom_recommendation_geometry_trial_updates(
    action_type: str,
    payload: dict,
    *,
    state: dict,
) -> dict | None:
    if action_type not in {"increase_width", "increase_depth"}:
        raise ValueError(
            f"unsupported bottom recommendation geometry trial: {action_type}"
        )
    generated_payload = dict(payload or {})
    if action_type == "increase_width":
        width_key, _, current_width = resolve_geometry_width_context(state)
        generated_payload["resolved_width_key"] = width_key
        generated_payload["current_width"] = current_width
    resolution = (
        resolve_design_guide_controller_guidance_action_generated_updates(
            action_type=action_type,
            payload=generated_payload,
            state=state,
        )
    )
    updates = resolution.get("updates") if resolution.get("handled") else None
    return rescue_geometry_width_for_depth_ratio(state, updates)


__all__ = ["bottom_recommendation_geometry_trial_updates"]
