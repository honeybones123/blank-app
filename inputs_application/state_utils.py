"""Explicit state utilities shared by Inputs application coordinators."""

from __future__ import annotations

from typing import Any, Mapping

from inputs_application.action_source_control import (
    authoritative_action_source_projection,
)
from inputs_application.state_projection import build_guidance_state_snapshot
from state_and_helpers import RESULT_KEYS, SHARED_DEFAULTS, resolve_design_actions


GUIDANCE_PROOF_KEYS = (
    "exact_stop_available",
    "exact_stop_proven",
    "exact_stop_proof",
    "target_band_reached",
    "target_band_proof",
)


def application_guidance_context(
    resolved_state: Mapping[str, Any],
    session_state: Mapping[str, Any],
) -> dict[str, Any]:
    context = dict(resolved_state or {})
    for key in GUIDANCE_PROOF_KEYS:
        if key in session_state:
            context[key] = session_state.get(key)
    return context


def shared_state_snapshot(session_state: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = {
        key: session_state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }
    snapshot.update(authoritative_action_source_projection(session_state))
    return snapshot


def guidance_state_snapshot(state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return build_guidance_state_snapshot(
        dict(state or {}),
        result_keys=RESULT_KEYS,
        shared_defaults=SHARED_DEFAULTS,
    )


def float_from_state(state: Mapping[str, Any], key: str, default: float) -> float:
    value = state.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def updates_match_state(
    state: Mapping[str, Any],
    updates: Mapping[str, Any],
) -> bool:
    for key, expected in updates.items():
        actual = state.get(key)
        if isinstance(expected, float):
            try:
                if abs(float(actual) - expected) > 1e-9:
                    return False
            except Exception:
                return False
        elif actual != expected:
            return False
    return True


def state_with_resolved_design_actions(
    state: Mapping[str, Any],
    actions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project resolved design actions into an isolated engineering snapshot."""

    resolved = guidance_state_snapshot(state)
    action_values = dict(actions or resolve_design_actions(resolved))
    projections = {
        "uls_Mstar": ("Mu", "uls_Mstar"),
        "uls_Vstar": ("Vu", "uls_Vstar"),
        "uls_Nstar": ("Nu", "uls_Nstar"),
        "Mu_star": ("Mu", "Mu_star"),
        "Vu_star": ("Vu", "Vu_star"),
        "N_star": ("Nu", "N_star"),
        "sls_Mstar": ("SLS_M", "sls_Mstar"),
        "sls_Vstar": ("SLS_V", "sls_Vstar"),
        "Tu_star": ("Tu", "Tu_star"),
        "P_star": ("Pu", "P_star"),
    }
    for target, (action_key, fallback_key) in projections.items():
        resolved[target] = float(
            action_values.get(
                action_key,
                float_from_state(resolved, fallback_key, 0.0),
            )
            or 0.0
        )
    resolved["uls_Mstar_pos_manual"] = float_from_state(
        resolved,
        "uls_Mstar_pos_manual",
        max(0.0, resolved["uls_Mstar"]),
    )
    resolved["uls_Mstar_neg_manual"] = float_from_state(
        resolved,
        "uls_Mstar_neg_manual",
        max(0.0, -resolved["uls_Mstar"]),
    )
    resolved["sls_Mstar_pos_manual"] = float_from_state(
        resolved,
        "sls_Mstar_pos_manual",
        max(0.0, resolved["sls_Mstar"]),
    )
    resolved["sls_Mstar_neg_manual"] = float_from_state(
        resolved,
        "sls_Mstar_neg_manual",
        max(0.0, -resolved["sls_Mstar"]),
    )
    resolved["actions_uls"] = {
        "M": resolved["uls_Mstar"],
        "V": resolved["uls_Vstar"],
        "N": resolved["uls_Nstar"],
        "T": resolved["Tu_star"],
        "P": resolved["P_star"],
    }
    return resolved


def uls_action_from_state(state: Mapping[str, Any], action: str) -> float:
    resolved_actions = resolve_design_actions(dict(state))
    resolved_key = {
        "M": "Mu",
        "V": "Vu",
        "N": "Nu",
        "T": "Tu",
        "P": "Pu",
    }.get(action)
    if resolved_key is not None and resolved_actions.get(resolved_key) is not None:
        return float(resolved_actions[resolved_key])
    fallback_key = {
        "M": "uls_Mstar",
        "V": "uls_Vstar",
        "N": "uls_Nstar",
        "T": "Tu_star",
        "P": "P_star",
    }.get(action)
    return float_from_state(state, fallback_key, 0.0) if fallback_key else 0.0


def shear_state_label(state: Mapping[str, Any]) -> str:
    legs = int(state.get("lig_legs", 0) or 0)
    if legs <= 0:
        return "No ligs"
    return (
        f"{legs}-leg "
        f"N{int(state.get('lig_d', 0) or 0)} @ "
        f"{int(float(state.get('s_lig', 0.0) or 0.0))}"
    )


def bottom_reo_state_label(state: Mapping[str, Any]) -> str:
    mode_1 = str(state.get("bot1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("bot2_layout_mode", "Count") or "Count")
    if mode_1 == "Count" and mode_2 == "Count":
        count_1 = int(state.get("bot1_count", 0) or 0)
        count_2 = int(state.get("bot2_count", 0) or 0)
        dia = int(state.get("db_bot_1", state.get("db_bot", 0)) or 0)
        if count_1 > 0:
            return (
                f"{count_1}N{dia} + {count_2}N{dia}"
                if count_2 > 0
                else f"{count_1}N{dia}"
            )
    spacing_1 = float(state.get("bot1_spacing", 0.0) or 0.0)
    dia_1 = int(state.get("db_bot_1", 0) or 0)
    return f"N{dia_1} @ {int(spacing_1)}"


__all__ = [
    "GUIDANCE_PROOF_KEYS",
    "application_guidance_context",
    "bottom_reo_state_label",
    "float_from_state",
    "guidance_state_snapshot",
    "shared_state_snapshot",
    "shear_state_label",
    "state_with_resolved_design_actions",
    "updates_match_state",
]
