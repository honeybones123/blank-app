"""Application-owned interpretation of Design Guide action payloads."""

from __future__ import annotations

from typing import Any


_PAYLOAD_OWNER = "DesignGuideController.guidance_action_payload_updates"
_GENERATED_OWNER = "DesignGuideController.guidance_action_generated_updates"


def resolve_design_guide_action_payload_updates(
    *, action_type: str, payload: dict[str, Any] | None
) -> dict[str, Any]:
    """Resolve explicit updates from a plain action payload."""

    action = str(action_type or "")
    payload_dict = dict(payload or {}) if isinstance(payload, dict) else {}

    if action == "apply_resolved_candidate":
        resolved_updates = payload_dict.get("resolved_candidate_updates")
        if isinstance(resolved_updates, dict) and resolved_updates:
            updates = dict(resolved_updates)
        else:
            explicit_updates = payload_dict.get("updates")
            updates = (
                dict(explicit_updates)
                if isinstance(explicit_updates, dict) and explicit_updates
                else None
            )
        return {"handled": True, "updates": updates, "owner": _PAYLOAD_OWNER}

    if action in {"apply_compound_guidance", "apply_mode_recommendation"}:
        explicit_updates = payload_dict.get("updates")
        return {
            "handled": True,
            "updates": dict(explicit_updates) if isinstance(explicit_updates, dict) else None,
            "owner": _PAYLOAD_OWNER,
        }

    if action == "apply_bottom_recommendation":
        explicit_updates = payload_dict.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            return {
                "handled": True,
                "updates": None if bool(payload_dict.get("updates_match_state")) else dict(explicit_updates),
                "owner": _PAYLOAD_OWNER,
            }
        return {"handled": False, "updates": None, "owner": _PAYLOAD_OWNER}

    if action == "apply_geometry_recommendation":
        explicit_updates = payload_dict.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            return {"handled": True, "updates": dict(explicit_updates), "owner": _PAYLOAD_OWNER}
        return {"handled": False, "updates": None, "owner": _PAYLOAD_OWNER}

    if action in {
        "apply_shear_recommendation",
        "increase_link_spacing",
        "reduce_number_of_legs",
        "tighten_geometry",
    }:
        explicit_updates = payload_dict.get("updates")
        if isinstance(explicit_updates, dict):
            return {"handled": True, "updates": dict(explicit_updates), "owner": _PAYLOAD_OWNER}
        return {"handled": False, "updates": None, "owner": _PAYLOAD_OWNER}

    return {"handled": False, "updates": None, "owner": _PAYLOAD_OWNER}


def resolve_design_guide_action_generated_updates(
    *,
    action_type: str,
    payload: dict[str, Any] | None,
    state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve generated geometry/detailing updates from plain state."""

    action = str(action_type or "")
    payload_dict = dict(payload or {}) if isinstance(payload, dict) else {}
    state_dict = dict(state or {}) if isinstance(state, dict) else {}
    if action == "increase_depth":
        current_d = float(state_dict.get("D", 600.0) or 600.0)
        delta_mm = float(payload_dict.get("delta_mm", 50) or 50.0)
        new_d = max(100.0, current_d + delta_mm)
        return {
            "handled": True,
            "updates": {"D": float(int(round(new_d / 10.0) * 10))},
            "owner": _GENERATED_OWNER,
        }

    if action == "increase_width":
        width_key = str(payload_dict.get("resolved_width_key") or "").strip()
        if not width_key:
            return {"handled": False, "updates": None, "owner": _GENERATED_OWNER}
        current_width = float(payload_dict.get("current_width", state_dict.get(width_key, 300.0)) or 300.0)
        delta_mm = float(payload_dict.get("delta_mm", 50) or 50.0)
        new_width = max(100.0, current_width + delta_mm)
        return {
            "handled": True,
            "updates": {width_key: float(int(round(new_width / 10.0) * 10))},
            "owner": _GENERATED_OWNER,
        }

    if action == "reduce_link_spacing":
        current_spacing = float(payload_dict.get("current_spacing", state_dict.get("s_lig", 200.0)) or 200.0)
        delta_mm = float(payload_dict.get("delta_mm", 25) or 25.0)
        minimum_spacing = float(payload_dict.get("minimum_spacing", 75.0) or 75.0)
        new_spacing = max(minimum_spacing, current_spacing - delta_mm)
        return {
            "handled": True,
            "updates": {"s_lig": float(int(round(new_spacing / 5.0) * 5))},
            "owner": _GENERATED_OWNER,
        }

    return {"handled": False, "updates": None, "owner": _GENERATED_OWNER}


__all__ = [
    "resolve_design_guide_action_generated_updates",
    "resolve_design_guide_action_payload_updates",
]
