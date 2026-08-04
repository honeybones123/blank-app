"""Typed crack evaluation for Inputs candidates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from inputs_application.recommendation_evaluation import effective_bottom_design_state
from inputs_application.recommendation_support import design_width_value
from inputs_application.state_utils import float_from_state
from state_and_helpers import effective_depth_with_links_mm


@dataclass(frozen=True)
class CrackEvaluationRuntime:
    sls_outer_steel_stress: Callable[..., float | None]
    design_width: Callable[[dict], float]
    effective_bottom: Callable[[dict, dict | None], dict]
    effective_bottom_spacing: Callable[..., float]
    float_from_state: Callable[[dict, str, float], float]
    effective_depth_with_links: Callable[..., float]


def effective_bottom_spacing(
    state: dict,
    bottom_updates: dict | None = None,
) -> float:
    from section_layout import compute_bar_layout_pure

    if bottom_updates:
        count = int(bottom_updates.get("bot1_count", 0) or 0)
        diameter = float(bottom_updates.get("db_bot_1", 0.0) or 0.0)
    else:
        count = int(
            float(
                state.get("bot1_count", state.get("nb_bot", 0))
                or 0
            )
        )
        diameter = float(
            state.get("db_bot_1", state.get("db_bot", 0.0))
            or 0.0
        )
    if count <= 1 or diameter <= 0.0:
        return float_from_state(state, "s_bot", 0.0)
    layout = compute_bar_layout_pure(
        b=design_width_value(state),
        cover_side=float_from_state(state, "cover_side", 40.0),
        nb_or_s=float(count),
        db=diameter,
        s_min=max(diameter, 25.0),
        rowgap=float_from_state(state, "rowgap_bot", 60.0),
    )
    return float(
        layout.get("s_actual", float_from_state(state, "s_bot", 0.0)) or 0.0
    )


def compute_sls_outer_steel_stress(
    state: dict,
    *,
    bottom_updates: dict | None = None,
) -> float | None:
    bottom_state = effective_bottom_design_state(state, bottom_updates)
    width = design_width_value(state)
    depth = float_from_state(state, "D", 600.0)
    effective_depth = float(bottom_state.get("d_centroid", 0.0) or 0.0)
    steel_area = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    concrete_modulus = float_from_state(state, "Ec", 30000.0)
    steel_modulus = float_from_state(state, "Es", 200000.0)
    moment = float_from_state(
        state,
        "sls_Mstar",
        float_from_state(state, "uls_Mstar", 0.0),
    )
    if not (
        width > 0.0
        and depth > 0.0
        and effective_depth > 0.0
        and steel_area > 0.0
        and concrete_modulus > 0.0
        and steel_modulus > 0.0
    ):
        return None
    transformed_steel = (steel_modulus / concrete_modulus) * steel_area
    if transformed_steel <= 0.0:
        return None
    a_coeff = width / 2.0
    discriminant = transformed_steel**2 + (
        4.0 * a_coeff * transformed_steel * effective_depth
    )
    if discriminant >= 0.0 and a_coeff > 0.0:
        neutral_axis = (
            -transformed_steel + math.sqrt(discriminant)
        ) / (2.0 * a_coeff)
        neutral_axis = max(1.0, min(neutral_axis, depth))
    else:
        neutral_axis = effective_depth / 2.0
    cracked_inertia = (
        width * neutral_axis**3 / 3.0
        + transformed_steel * (effective_depth - neutral_axis) ** 2
    )
    if cracked_inertia <= 0.0:
        return None
    curvature = (moment * 1e6) / (concrete_modulus * cracked_inertia)
    return float(steel_modulus * curvature * (effective_depth - neutral_axis))


def build_crack_evaluation_runtime() -> CrackEvaluationRuntime:
    return CrackEvaluationRuntime(
        sls_outer_steel_stress=compute_sls_outer_steel_stress,
        design_width=design_width_value,
        effective_bottom=effective_bottom_design_state,
        effective_bottom_spacing=effective_bottom_spacing,
        float_from_state=float_from_state,
        effective_depth_with_links=effective_depth_with_links_mm,
    )


def _evaluate_crack_with_state_for_app_bridge(
    state: dict,
    *,
    bottom_updates: dict | None = None,
    runtime: CrackEvaluationRuntime,
) -> dict | None:
    from calculations.crack_control import (
        calc_eps_diff,
        calc_sr_max,
        table_sigma_max_A,
        table_sigma_max_B,
    )

    bottom_state = runtime.effective_bottom(state, bottom_updates)
    sigma_sr = runtime.sls_outer_steel_stress(
        state,
        bottom_updates=bottom_updates,
    )
    bar_diameter = float(bottom_state.get("db_bot", 0.0) or 0.0)
    ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    b = runtime.float_from_state(state, "b_crack", runtime.design_width(state))
    D = runtime.float_from_state(state, "D", 600.0)
    cover_bot = runtime.float_from_state(state, "cover_bot", 40.0)
    spacing = runtime.effective_bottom_spacing(state, bottom_updates=bottom_updates)
    fc = runtime.float_from_state(state, "fc", 32.0)
    Ec = runtime.float_from_state(state, "Ec", 30000.0)
    Es = runtime.float_from_state(state, "Es", 200000.0)
    fsy = runtime.float_from_state(state, "fsy", 500.0)
    phi_ce = runtime.float_from_state(state, "phi_cc_t", 2.0)
    eps_cs = runtime.float_from_state(state, "eps_cs_total_micro", 300.0) * 1e-6
    wmax_choice = runtime.float_from_state(state, "wmax_char_limit", 0.3)
    member_type = str(state.get("crack_member_type", "Primarily flexure") or "Primarily flexure")
    k1 = runtime.float_from_state(state, "crack_k1", 0.8)
    k2 = runtime.float_from_state(
        state,
        "crk_k2",
        runtime.float_from_state(state, "crack_k2", 0.5),
    )
    if sigma_sr is None or bar_diameter <= 0.0 or ast <= 0.0 or b <= 0.0 or D <= 0.0 or wmax_choice <= 0.0:
        return None
    lig_diameter = runtime.float_from_state(state, "lig_d", 10.0)
    d_eff = runtime.effective_depth_with_links(
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
    "CrackEvaluationRuntime",
    "_evaluate_crack_with_state_for_app_bridge",
]
