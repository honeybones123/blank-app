"""Resolved design-action state projection for app-bridge callers."""

from __future__ import annotations

from typing import Any


_RESOLVED_DESIGN_ACTIONS_STATE_DEPENDENCIES: tuple[str, ...] = (
    "SHARED_DEFAULTS",
    "_float_from_state",
    "_guidance_state_snapshot_for_summary_bridge",
    "_resolve_design_actions_from_state",
)


def bind_resolved_design_actions_state_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _RESOLVED_DESIGN_ACTIONS_STATE_DEPENDENCIES
            if name in namespace
        }
    )


def _apply_resolved_design_action_fields(
    resolved: dict,
    actions: dict | None = None,
) -> dict:
    actions = dict(actions or _resolve_design_actions_from_state(resolved))
    resolved["uls_Mstar"] = float(
        actions.get("Mu", _float_from_state(resolved, "uls_Mstar", 0.0)) or 0.0
    )
    resolved["uls_Vstar"] = float(
        actions.get("Vu", _float_from_state(resolved, "uls_Vstar", 0.0)) or 0.0
    )
    resolved["uls_Nstar"] = float(
        actions.get("Nu", _float_from_state(resolved, "uls_Nstar", 0.0)) or 0.0
    )
    resolved["Mu_star"] = float(
        actions.get("Mu", _float_from_state(resolved, "Mu_star", 0.0)) or 0.0
    )
    resolved["Vu_star"] = float(
        actions.get("Vu", _float_from_state(resolved, "Vu_star", 0.0)) or 0.0
    )
    resolved["N_star"] = float(
        actions.get("Nu", _float_from_state(resolved, "N_star", 0.0)) or 0.0
    )
    resolved["sls_Mstar"] = float(
        actions.get("SLS_M", _float_from_state(resolved, "sls_Mstar", 0.0)) or 0.0
    )
    resolved["uls_Mstar_pos_manual"] = float(
        _float_from_state(
            resolved,
            "uls_Mstar_pos_manual",
            max(0.0, _float_from_state(resolved, "uls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["uls_Mstar_neg_manual"] = float(
        _float_from_state(
            resolved,
            "uls_Mstar_neg_manual",
            max(0.0, -_float_from_state(resolved, "uls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Mstar_pos_manual"] = float(
        _float_from_state(
            resolved,
            "sls_Mstar_pos_manual",
            max(0.0, _float_from_state(resolved, "sls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Mstar_neg_manual"] = float(
        _float_from_state(
            resolved,
            "sls_Mstar_neg_manual",
            max(0.0, -_float_from_state(resolved, "sls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Vstar"] = float(
        actions.get("SLS_V", _float_from_state(resolved, "sls_Vstar", 0.0)) or 0.0
    )
    resolved["Tu_star"] = float(
        actions.get("Tu", _float_from_state(resolved, "Tu_star", 0.0)) or 0.0
    )
    resolved["P_star"] = float(
        actions.get("Pu", _float_from_state(resolved, "P_star", 0.0)) or 0.0
    )
    resolved["actions_uls"] = {
        "M": resolved["uls_Mstar"],
        "V": resolved["uls_Vstar"],
        "N": resolved["uls_Nstar"],
        "T": resolved["Tu_star"],
        "P": resolved["P_star"],
    }
    return resolved


def _state_with_resolved_design_actions_isolated_for_app_bridge(
    state: dict,
    actions: dict | None = None,
) -> dict:
    resolved = dict(state or {})
    for key, default in SHARED_DEFAULTS.items():
        resolved.setdefault(key, default)
    return _apply_resolved_design_action_fields(resolved, actions)


def _state_with_resolved_design_actions_for_app_bridge(
    state: dict,
    actions: dict | None = None,
) -> dict:
    resolved = _guidance_state_snapshot_for_summary_bridge(state)
    return _apply_resolved_design_action_fields(resolved, actions)


__all__ = [
    "bind_resolved_design_actions_state_dependencies",
    "_state_with_resolved_design_actions_for_app_bridge",
    "_state_with_resolved_design_actions_isolated_for_app_bridge",
]
