"""Committed engineering snapshot projection.

The projection consumes a resolved Inputs state dictionary and returns the
pure ``EngineeringInputSnapshot`` used by the application run coordinator.
Only engineering-affecting values are copied. UI/session/render-only state is
deliberately excluded so Streamlit reruns, expanded panels, and local loading
flags cannot perturb the engineering hash.
"""

from __future__ import annotations

from typing import Any, Mapping

from design_brain.authority import EngineeringInputSnapshot


GEOMETRY_INPUT_KEYS: tuple[str, ...] = (
    "sec_shape",
    "b",
    "bw",
    "tw",
    "D",
    "d",
    "bf",
    "tf",
    "bf_bot",
    "tf_bot",
    "span_m",
    "L",
)

MATERIAL_INPUT_KEYS: tuple[str, ...] = (
    "fc",
    "fsy",
    "Ec",
    "Es",
    "phi_bend",
    "phi_shear",
)

REINFORCEMENT_INPUT_KEYS: tuple[str, ...] = (
    "cover_top",
    "cover_bot",
    "cover_side",
    "rowgap_top",
    "rowgap_bot",
    "Ast_top",
    "Ast_bot",
    "bot_row_count",
    "bot1_layout_mode",
    "bot1_count",
    "db_bot_1",
    "bot1_spacing",
    "bot2_layout_mode",
    "bot2_count",
    "db_bot_2",
    "bot2_spacing",
    "bot_row_1_mode",
    "bot_row_1_bars",
    "bot_row_1_spacing",
    "bot_row_1_dia",
    "bot_row_2_mode",
    "bot_row_2_bars",
    "bot_row_2_spacing",
    "bot_row_2_dia",
    "lig_d",
    "lig_legs",
    "s_lig",
)

DESIGN_ACTION_INPUT_KEYS: tuple[str, ...] = (
    "uls_Mstar",
    "uls_Mstar_pos_manual",
    "uls_Mstar_neg_manual",
    "uls_Vstar",
    "uls_Nstar",
    "Tu_star",
    "P_star",
    "Mu_star",
    "Mu_star_manual",
    "Mu_star_pos_manual",
    "Mu_star_neg_manual",
    "Vu_star",
    "Nu_star",
    "sls_Mstar",
    "sls_Mstar_pos_manual",
    "sls_Mstar_neg_manual",
    "sls_Vstar",
    "sls_Nstar",
    "w_sls_kNm_per_m",
    "P_sls_kN",
)

DESIGN_SETTING_INPUT_KEYS: tuple[str, ...] = (
    "design_optimisation_goal",
    "loads_edit_mode",
    "loads_edit_toggle",
    "defl_limit_ratio",
    "exposure_class",
    "ductility_class",
    "design_code",
)

UI_ONLY_STATE_KEYS: frozenset[str] = frozenset(
    {
        "active_tab",
        "active_tabs",
        "selected_tab",
        "expanded_panels",
        "scroll_state",
        "camera_settings",
        "help_toggles",
        "fullscreen_state",
        "loading_flags",
        "timestamp",
        "timestamps",
        "guidance_cache_hit",
        "guidance_compute_ms",
        "design_guide_rendered",
    }
)


def _pick(state: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: state.get(key) for key in keys if key in state and key not in UI_ONLY_STATE_KEYS}


def _first_present(state: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = state.get(key)
        if value is not None:
            return value
    return None


def _resolved_design_actions(state: Mapping[str, Any]) -> dict[str, Any]:
    actions = _pick(state, DESIGN_ACTION_INPUT_KEYS)
    actions["resolved"] = {
        "Mu": _first_present(state, "uls_Mstar", "Mu_star", "Mu_star_manual"),
        "Vu": _first_present(state, "uls_Vstar", "Vu_star"),
        "Nu": _first_present(state, "uls_Nstar", "Nu_star"),
        "Tu": _first_present(state, "Tu_star"),
        "Pu": _first_present(state, "P_star"),
        "SLS_M": _first_present(state, "sls_Mstar"),
        "SLS_V": _first_present(state, "sls_Vstar"),
        "SLS_N": _first_present(state, "sls_Nstar"),
    }
    return actions


def _resolved_reinforcement(state: Mapping[str, Any]) -> dict[str, Any]:
    reinforcement = _pick(state, REINFORCEMENT_INPUT_KEYS)
    # Canonical row fields own engineering identity. The legacy spacing aliases
    # remain in the snapshot for compatibility, but cannot independently
    # perturb the hash when the corresponding canonical row field is present.
    for legacy_key, canonical_key in (
        ("bot1_spacing", "bot_row_1_spacing"),
        ("bot2_spacing", "bot_row_2_spacing"),
    ):
        if canonical_key in state:
            reinforcement[legacy_key] = state.get(canonical_key)
    return reinforcement


def _lock_state(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): state[key]
        for key in sorted(state)
        if str(key).startswith("optimisation_lock_") or str(key).startswith("lock_")
    }


def build_engineering_input_snapshot_from_resolved_state(
    state: Mapping[str, Any],
    *,
    contract_versions: Mapping[str, Any] | None = None,
    calculation_versions: Mapping[str, Any] | None = None,
) -> EngineeringInputSnapshot:
    """Project the resolved Inputs state into an engineering-only snapshot."""

    if not isinstance(state, Mapping):
        raise TypeError("state must be a mapping")
    return EngineeringInputSnapshot(
        geometry=_pick(state, GEOMETRY_INPUT_KEYS),
        materials=_pick(state, MATERIAL_INPUT_KEYS),
        reinforcement=_resolved_reinforcement(state),
        design_actions=_resolved_design_actions(state),
        design_settings=_pick(state, DESIGN_SETTING_INPUT_KEYS),
        locked_variables=_lock_state(state),
        unlocked_variables={},
        contract_versions=dict(contract_versions or {}),
        calculation_versions=dict(calculation_versions or {}),
    )


__all__ = [
    "DESIGN_ACTION_INPUT_KEYS",
    "DESIGN_SETTING_INPUT_KEYS",
    "GEOMETRY_INPUT_KEYS",
    "MATERIAL_INPUT_KEYS",
    "REINFORCEMENT_INPUT_KEYS",
    "UI_ONLY_STATE_KEYS",
    "build_engineering_input_snapshot_from_resolved_state",
]
