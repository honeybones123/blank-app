"""Crack evaluation coordination for Inputs app-bridge candidates."""

from __future__ import annotations

import math
from typing import Any


_CRACK_EVALUATION_DEPENDENCIES: tuple[str, ...] = (
    "_compute_sls_outer_steel_stress_with_state_for_app_bridge",
    "_design_width_value_for_app_bridge",
    "_effective_bottom_design_state_for_app_bridge",
    "_effective_bottom_spacing_for_app_bridge",
    "_float_from_state",
    "effective_depth_with_links_mm",
)


def bind_crack_evaluation_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _CRACK_EVALUATION_DEPENDENCIES
            if name in namespace
        }
    )


def _evaluate_crack_with_state_for_app_bridge(
    state: dict,
    *,
    bottom_updates: dict | None = None,
) -> dict | None:
    from crack_page import table_sigma_max_A, table_sigma_max_B, calc_eps_diff, calc_sr_max

    bottom_state = _effective_bottom_design_state_for_app_bridge(state, bottom_updates)
    sigma_sr = _compute_sls_outer_steel_stress_with_state_for_app_bridge(
        state,
        bottom_updates=bottom_updates,
    )
    bar_diameter = float(bottom_state.get("db_bot", 0.0) or 0.0)
    ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    b = _float_from_state(state, "b_crack", _design_width_value_for_app_bridge(state))
    D = _float_from_state(state, "D", 600.0)
    cover_bot = _float_from_state(state, "cover_bot", 40.0)
    spacing = _effective_bottom_spacing_for_app_bridge(state, bottom_updates=bottom_updates)
    fc = _float_from_state(state, "fc", 32.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Es = _float_from_state(state, "Es", 200000.0)
    fsy = _float_from_state(state, "fsy", 500.0)
    phi_ce = _float_from_state(state, "phi_cc_t", 2.0)
    eps_cs = _float_from_state(state, "eps_cs_total_micro", 300.0) * 1e-6
    wmax_choice = _float_from_state(state, "wmax_char_limit", 0.3)
    member_type = str(state.get("crack_member_type", "Primarily flexure") or "Primarily flexure")
    k1 = _float_from_state(state, "crack_k1", 0.8)
    k2 = _float_from_state(state, "crk_k2", _float_from_state(state, "crack_k2", 0.5))
    if sigma_sr is None or bar_diameter <= 0.0 or ast <= 0.0 or b <= 0.0 or D <= 0.0 or wmax_choice <= 0.0:
        return None
    lig_diameter = _float_from_state(state, "lig_d", 10.0)
    d_eff = effective_depth_with_links_mm(
        D_mm=D,
        cover_to_ligs_mm=cover_bot,
        lig_diameter_mm=lig_diameter,
        bar_diameter_mm=bar_diameter,
    )
    height_eff = min(2.5 * cover_bot, max(D - d_eff, 0.0), D / 2.0)
    a_ceff = b * max(height_eff, 1.0)
    rho_eff = ast / a_ceff if a_ceff > 0.0 else 0.0
    sigma_table_a = table_sigma_max_A(bar_diameter, wmax_choice)
    sigma_table_b = table_sigma_max_B(max(spacing, 1.0), wmax_choice)
    sigma_table_combined = sigma_table_a if member_type == "Primarily tension" else max(sigma_table_a, sigma_table_b)
    sigma_allow_table = min(sigma_table_combined, 0.8 * fsy)
    util_table = sigma_sr / sigma_allow_table if sigma_allow_table > 0.0 else 0.0
    fct_eff = 0.6 * math.sqrt(max(fc, 1.0))
    n_e = (1.0 + phi_ce) * Es / Ec if Ec > 0.0 else 0.0
    eps_diff = calc_eps_diff(
        sigma_sr=sigma_sr,
        Es=Es,
        fct_eff=fct_eff,
        rho_eff=rho_eff,
        ne=n_e,
        eps_cs=eps_cs,
    )
    sr_max = calc_sr_max(c_mm=cover_bot, db_mm=bar_diameter, rho_eff=rho_eff, k1=k1, k2=k2)
    w_calc = sr_max * eps_diff
    util_w = w_calc / wmax_choice if wmax_choice > 0.0 else 0.0
    util = max(util_table, util_w)
    return {
        "sigma_sr": float(sigma_sr),
        "sigma_allow_table": float(sigma_allow_table),
        "w_calc": float(w_calc),
        "util": float(util),
        "passes": bool(util <= 1.0),
    }


__all__ = [
    "bind_crack_evaluation_dependencies",
    "_evaluate_crack_with_state_for_app_bridge",
]
