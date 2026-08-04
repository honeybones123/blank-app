"""Shear widget seed request coordination."""

from __future__ import annotations

from typing import Any, Callable


_SHEAR_SHARED_KEYS = ("lig_d", "lig_legs", "s_lig")
_SHEAR_WIDGET_KEY_MAP = {
    "inputs_lig_d": "lig_d",
    "inputs_lig_legs": "lig_legs",
    "inputs_s_lig": "s_lig",
    "shear_lig_d": "lig_d",
    "shear_lig_legs": "lig_legs",
    "shear_s_lig": "s_lig",
}


def request_shear_widget_seed_from_shared(
    *,
    state: dict,
    reason: str,
    agent_debug_log_fn: Callable[..., None],
) -> dict:
    reason_norm = str(reason or "").strip() or "unspecified"
    shared_values = {key: state.get(key) for key in _SHEAR_SHARED_KEYS}
    widget_map = {
        widget_key: shared_values[shared_key]
        for widget_key, shared_key in _SHEAR_WIDGET_KEY_MAP.items()
    }
    widget_keys = list(widget_map.keys())
    for widget_key in widget_keys:
        state.pop(f"_cached_{widget_key}", None)

    hydrated_map = state.get("_hydrated_from_shared_map")
    if isinstance(hydrated_map, dict):
        for widget_key in widget_keys:
            hydrated_map.pop(widget_key, None)

    payload = {
        "seed_requested": True,
        "reason": reason_norm,
        "shared": dict(shared_values),
        "widget_keys": list(widget_keys),
        "direct_widget_writes": [],
    }
    state["_pending_shear_widget_seed_from_shared"] = dict(payload)
    state["inputs_shear_widget_seed_requested"] = True
    state["inputs_shear_widget_seed_reason"] = reason_norm
    state["_inputs_shear_widget_seed_latest"] = dict(payload)
    try:
        agent_debug_log_fn(
            "Inputs shear widget seed requested from shared",
            payload,
            location="inputs_page.py:_request_shear_widget_seed_from_shared",
            hypothesis_id="H_INPUTS_SHEAR_WIDGET_SEED_REQUEST",
        )
    except Exception:
        pass
    return payload


__all__ = ["request_shear_widget_seed_from_shared"]
