"""Canonical identity for Inputs design candidates."""

from __future__ import annotations

from calculations.design_actions import resolve_design_actions_from_state as resolve_design_actions


AUTO_DESIGN_CANDIDATE_KEY_TRACKED_FIELDS: tuple[str, ...] = (
    "sec_shape",
    "b",
    "bw",
    "tw",
    "D",
    "bf",
    "tf",
    "bf_bot",
    "tf_bot",
    "fc",
    "fsy",
    "Ec",
    "Es",
    "phi_bend",
    "phi_shear",
    "cover_top",
    "cover_bot",
    "cover_side",
    "rowgap_top",
    "rowgap_bot",
    "design_optimisation_goal",
    "optimisation_lock_geometry",
    "Ast_top",
    "Tu_star",
    "P_star",
    "lig_d",
    "lig_legs",
    "s_lig",
    "bot_row_count",
    "bot1_layout_mode",
    "bot1_count",
    "db_bot_1",
    "bot2_layout_mode",
    "bot2_count",
    "db_bot_2",
    "bot_row_1_mode",
    "bot_row_1_bars",
    "bot_row_1_spacing",
    "bot_row_1_dia",
    "bot_row_2_mode",
    "bot_row_2_bars",
    "bot_row_2_spacing",
    "bot_row_2_dia",
)


def make_auto_design_candidate_key(state: dict) -> tuple:
    actions = resolve_design_actions(state)
    key_parts = [
        (key, str(state.get(key)))
        for key in AUTO_DESIGN_CANDIDATE_KEY_TRACKED_FIELDS
    ]
    key_parts.extend(
        [
            ("resolved_Mu", str(actions.get("Mu"))),
            ("resolved_Vu", str(actions.get("Vu"))),
            ("resolved_Nu", str(actions.get("Nu"))),
            ("resolved_SLS_M", str(actions.get("SLS_M"))),
            ("resolved_SLS_V", str(actions.get("SLS_V"))),
            ("resolved_source", str(actions.get("source"))),
        ]
    )
    return tuple(key_parts)


def candidate_cache_key(state: dict) -> tuple:
    return make_auto_design_candidate_key(state)


__all__ = [
    "AUTO_DESIGN_CANDIDATE_KEY_TRACKED_FIELDS",
    "candidate_cache_key",
    "make_auto_design_candidate_key",
]
