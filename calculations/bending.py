from __future__ import annotations

import math
from typing import Any

from calculations.design_actions import resolve_design_actions_from_state


def resolve_bending_faces(moment_sign: str) -> tuple[str, str, bool]:
    """
    From the active bending case (display / demand sign).

    Returns:
        tension_face: "bottom" | "top"
        compression_face: "top" | "bottom"
        is_hogging: True if moment_sign is negative (hogging)
    """
    sign = str(moment_sign or "positive").strip().lower()
    is_hogging = sign == "negative"
    if is_hogging:
        return "top", "bottom", True
    return "bottom", "top", False


def _collect_reo_layout_rows(reo_layout: dict, side: str) -> list[dict]:
    if not reo_layout:
        return []
    keys = (
        ["top", "top_flange", "top_web", "top_left", "top_right"]
        if side == "top"
        else ["bottom", "bottom_flange", "bottom_web", "bottom_left", "bottom_right"]
    )
    out: list[dict] = []
    for key in keys:
        value = reo_layout.get(key)
        if not value:
            continue
        out += value if isinstance(value, list) else [value]
    return out


def resolve_bending_layer_geometry(
    layout: dict[str, Any] | None,
    *,
    moment_sign: str,
    D: float,
    fallback_y_tension: float,
) -> dict[str, Any]:
    """
    Resolve centroids, d / d', and extreme compression fibre from section layout.

    fallback_y_tension: y of tension steel from top (mm) when layout has no bars.
    """
    tension_face, compression_face, is_hogging = resolve_bending_faces(moment_sign)
    Df = float(D or 0.0)
    y_comp_extreme = 0.0 if tension_face == "bottom" else Df
    y_tension = float(fallback_y_tension)
    y_compression_steel: float | None = None

    tension_layer_coords: list[dict[str, Any]] = []
    compression_layer_coords: list[dict[str, Any]] = []

    if not layout:
        d_mm = y_tension if tension_face == "bottom" else max(0.0, Df - y_tension)
        return {
            "tension_face": tension_face,
            "compression_face": compression_face,
            "is_hogging": is_hogging,
            "plot_neg": is_hogging,
            "y_comp_extreme": y_comp_extreme,
            "compression_block_face": "top" if tension_face == "bottom" else "bottom",
            "y_tension_centroid": y_tension,
            "y_compression_steel_centroid": y_compression_steel,
            "d_value": d_mm,
            "d_prime_value": None,
            "tension_layer_coords": tension_layer_coords,
            "compression_layer_coords": compression_layer_coords,
        }

    pts = layout.get("reo_points") or []
    if pts:
        for point in pts:
            layer = point.get("layer")
            if layer == tension_face:
                tension_layer_coords.append(dict(point))
            elif layer == compression_face:
                compression_layer_coords.append(dict(point))
        b_ys = [float(point["y"]) for point in pts if point.get("layer") == "bottom"]
        t_ys = [float(point["y"]) for point in pts if point.get("layer") == "top"]
        if tension_face == "bottom":
            if b_ys:
                y_tension = max(b_ys)
            if t_ys:
                y_compression_steel = sum(t_ys) / len(t_ys)
        else:
            if t_ys:
                y_tension = min(t_ys)
            if b_ys:
                y_compression_steel = sum(b_ys) / len(b_ys)
    else:
        reo_layout = layout.get("reo_layout")
        if reo_layout and isinstance(reo_layout, dict):
            b_ys = []
            for layer_data in _collect_reo_layout_rows(reo_layout, "bottom"):
                try:
                    b_ys.append(float(layer_data["y"]))
                except Exception:
                    pass
            t_ys = []
            for layer_data in _collect_reo_layout_rows(reo_layout, "top"):
                try:
                    t_ys.append(float(layer_data["y"]))
                except Exception:
                    pass
            if tension_face == "bottom":
                if b_ys:
                    y_tension = max(b_ys)
                if t_ys:
                    y_compression_steel = sum(t_ys) / len(t_ys)
            else:
                if t_ys:
                    y_tension = min(t_ys)
                if b_ys:
                    y_compression_steel = sum(b_ys) / len(b_ys)

    d_mm = y_tension if tension_face == "bottom" else max(0.0, Df - y_tension)
    d_prime_mm: float | None = None
    if y_compression_steel is not None:
        if tension_face == "bottom":
            d_prime_mm = max(0.0, float(y_compression_steel))
        else:
            d_prime_mm = max(0.0, Df - float(y_compression_steel))

    return {
        "tension_face": tension_face,
        "compression_face": compression_face,
        "is_hogging": is_hogging,
        "plot_neg": is_hogging,
        "y_comp_extreme": y_comp_extreme,
        "compression_block_face": "top" if tension_face == "bottom" else "bottom",
        "y_tension_centroid": y_tension,
        "y_compression_steel_centroid": y_compression_steel,
        "d_value": d_mm,
        "d_prime_value": d_prime_mm,
        "tension_layer_coords": tension_layer_coords,
        "compression_layer_coords": compression_layer_coords,
    }


def layout_bars_in_rows(n_bars, b, cover, db, min_spacing, n_rows_max=2):
    """
    Lay out bars in 1-2 rows and return a list of (x_rel, row_index).
    """
    if n_bars is None or n_bars <= 0:
        return []

    n_bars = int(n_bars)
    inner = max(b - 2 * cover, db)

    if n_bars == 1:
        n_per_row = [1]
    else:
        spacing_1row = inner / (n_bars - 1)
        if spacing_1row >= min_spacing or n_rows_max == 1:
            n_per_row = [n_bars]
        else:
            n1 = math.ceil(n_bars / 2)
            n2 = n_bars - n1
            n_per_row = [n1, n2]

    coords = []
    bar_index = 0
    for row_idx, n_in_row in enumerate(n_per_row):
        if n_in_row <= 0:
            continue

        if n_in_row == 1:
            xs = [b / 2.0]
        else:
            inner = max(b - 2 * cover, db)
            spacing_row = inner / (n_in_row - 1)
            spacing_row = max(spacing_row, min_spacing)
            xs = [cover + spacing_row * i for i in range(n_in_row)]

        for x in xs:
            coords.append((x, row_idx))
            bar_index += 1
            if bar_index >= n_bars:
                break
        if bar_index >= n_bars:
            break

    return coords


def effective_depth_with_links_mm(
    D_mm: float,
    cover_to_ligs_mm: float,
    lig_diameter_mm: float,
    bar_diameter_mm: float,
) -> float:
    """
    Canonical effective depth for bottom tension steel.

    d = D - (cover_to_ligs + lig_diameter + 0.5 * bar_diameter)
    """
    Df = float(D_mm or 0.0)
    cover_f = float(cover_to_ligs_mm or 0.0)
    lig_f = float(lig_diameter_mm or 0.0)
    bar_f = float(bar_diameter_mm or 0.0)
    return max(0.0, Df - (cover_f + lig_f + 0.5 * bar_f))


def bottom_tension_effective_depth_fallback_mm(
    D_mm: float,
    cover_bot_mm: float,
    bar_diameter_mm: float,
) -> float:
    """Page-report fallback d = D - cover_bot - 0.5 db, preserving legacy behavior."""
    return float(D_mm) - float(cover_bot_mm) - 0.5 * float(bar_diameter_mm)


def effective_depth_centroid_mm(
    b,
    D,
    nb_bot,
    db_bot,
    cover_bot,
    rowgap_bot,
    lig_diameter_mm,
):
    """Pure effective-depth calculation used by legacy sagging capacity."""
    _ = (b, nb_bot, rowgap_bot)
    if D in (None, 0) or db_bot in (None, 0) or cover_bot in (None, 0):
        return None
    return effective_depth_with_links_mm(
        D_mm=float(D or 0.0),
        cover_to_ligs_mm=float(cover_bot or 0.0),
        lig_diameter_mm=float(lig_diameter_mm or 0.0),
        bar_diameter_mm=float(db_bot or 0.0),
    )


def bar_area_mm2(count: float, diameter_mm: float) -> float:
    """Area of identical circular reinforcing bars in mm2."""
    return float(count or 0.0) * math.pi * float(diameter_mm or 0.0) ** 2 / 4.0


def stress_block_factors(fc_mpa: float) -> tuple[float, float]:
    """AS 3600 rectangular stress-block factors (alpha2, gamma)."""
    fc = float(fc_mpa or 0.0)
    alpha2 = max(0.67, 0.85 - 0.0015 * fc)
    gamma = max(0.67, 0.97 - 0.0025 * fc)
    return float(alpha2), float(gamma)


def minimum_moment_capacity_kNm(Mcr_kNm: float | None) -> float:
    """Minimum design moment capacity from the existing teaching Tab 2 rule."""
    if Mcr_kNm is None:
        return float("nan")
    try:
        mcr = float(Mcr_kNm)
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(mcr):
        return float("nan")
    return 1.2 * mcr


def nominal_capacity_from_phi_capacity_kNm(
    phi_capacity_kNm: float,
    phi: float | None,
) -> float:
    """Nominal moment capacity from phi-reduced capacity, preserving page fallback."""
    phi_value = float(phi or 0.0)
    if phi_value <= 0.0:
        return float("nan")
    return float(phi_capacity_kNm) / phi_value


def compression_block_lever_arm_values(
    *,
    dn_mm: float,
    gamma: float,
    d_mm: float,
) -> dict[str, float]:
    """Rectangular compression-block depth and internal lever arm."""
    dn = float(dn_mm or 0.0)
    gamma_value = float(gamma or 0.0)
    d = float(d_mm or 0.0)
    a = gamma_value * dn
    z = d - 0.5 * a
    return {
        "a": a,
        "z": z,
    }


def uls_bending_report_values(
    *,
    b: float,
    d: float,
    fc: float,
    fsy: float,
    Ast: float,
    phi: float,
    Mu_star: float,
    Es: float,
    eps_cu: float = 0.003,
    ku_limit: float = 0.36,
) -> dict[str, Any]:
    """Scalar ULS bending values used by report/check-card displays."""
    b_value = float(b or 0.0)
    d_value = float(d or 0.0)
    fc_value = float(fc or 0.0)
    fsy_value = float(fsy or 0.0)
    Ast_value = float(Ast or 0.0)
    phi_value = float(phi or 0.0)
    Mu_star_value = float(Mu_star or 0.0)
    Es_value = float(Es or 0.0)
    eps_cu_value = float(eps_cu or 0.0)
    ku_limit_value = float(ku_limit or 0.0)

    alpha2, gamma = stress_block_factors(fc_value)
    T = Ast_value * fsy_value
    denom = alpha2 * fc_value * b_value * gamma
    dn = T / denom if denom > 0.0 else float("nan")
    lever_arm = compression_block_lever_arm_values(dn_mm=dn, gamma=gamma, d_mm=d_value)
    a = lever_arm["a"] if dn == dn else float("nan")
    z = lever_arm["z"] if a == a else float("nan")
    Mu_nom = T * z / 1e6 if z == z else 0.0
    phi_Mu_cap = phi_value * Mu_nom
    C_N = alpha2 * fc_value * b_value * a if a == a else float("nan")
    C_kN = C_N / 1000.0 if C_N == C_N else float("nan")
    T_kN = T / 1000.0
    eps_s = (
        eps_cu_value * (d_value - dn) / dn
        if dn == dn and dn > 1e-9
        else float("nan")
    )
    eps_sy = fsy_value / Es_value if Es_value > 1e-9 else float("nan")
    ku = dn / d_value if d_value else float("nan")
    ku_ok = (0.0 < ku <= ku_limit_value) if ku == ku else None
    Mu_ok = Mu_star_value <= phi_Mu_cap if phi_Mu_cap > 0.0 else None
    Mu_util = Mu_star_value / phi_Mu_cap if phi_Mu_cap > 0.0 else float("nan")

    return {
        "alpha2": alpha2,
        "gamma": gamma,
        "T_N": T,
        "T_kN": T_kN,
        "denom": denom,
        "dn": dn,
        "a": a,
        "z": z,
        "Mu_nom": Mu_nom,
        "phi_Mu_cap": phi_Mu_cap,
        "C_N": C_N,
        "C_kN": C_kN,
        "eps_cu": eps_cu_value,
        "eps_s": eps_s,
        "eps_sy": eps_sy,
        "ku": ku,
        "ku_limit": ku_limit_value,
        "ku_ok": ku_ok,
        "Mu_ok": Mu_ok,
        "Mu_util": Mu_util,
    }


def decode_bars_or_spacing(entry, b, cover_side, bar_dia):
    """
    Interpret a reinforcement entry as either bar count or spacing.

    Returns (mode, n_eff, s_eff), where mode is "N" for count and "S" for
    spacing. The bar_dia argument is retained for the legacy call contract.
    """
    _ = bar_dia
    try:
        val = float(entry)
    except Exception:
        return "N", 0, 0.0

    try:
        b_val = float(b)
    except Exception:
        b_val = 0.0
    try:
        cs_val = float(cover_side)
    except Exception:
        cs_val = 0.0

    L_centroid = max(0.0, b_val - 2.0 * cs_val)

    if val <= 0.0 or L_centroid <= 0.0:
        return "N", 0, 0.0

    if val < 30.0:
        n = int(round(val))
        n = max(1, n)

        if n == 1:
            s_eff = L_centroid
        else:
            s_eff = L_centroid / (n - 1)

        return "N", n, s_eff

    s_target = val
    n = int(L_centroid // s_target) + 1
    n = max(1, n)

    return "S", n, s_target


def compute_bending_capacity_legacy(
    *,
    b,
    D,
    fc,
    fsy,
    Ast,
    Mu_star,
    phi,
    d_input,
    cover_bot,
    db_bot,
    nb_bot,
    rowgap_bot,
    lig_diameter_mm,
) -> dict:
    """
    Legacy sagging-only rectangular stress-block capacity calculation.

    This preserves the historical result shape used by bending_core and
    minimum-strength checks while making the calculation input-complete.
    """
    d_centroid = effective_depth_centroid_mm(
        b,
        D,
        nb_bot,
        db_bot,
        cover_bot,
        rowgap_bot,
        lig_diameter_mm,
    )
    # ``d_input`` is the canonical area-weighted centroid published by the
    # shared reinforcement layout.  The scalar fallback can only represent a
    # single row and must not replace that exact multi-row value.
    d = d_input if d_input not in (None, 0) else d_centroid

    if None in (b, D, d, fc, fsy, Ast, Mu_star):
        return {
            "phi_Mu_cap": 0.0,
            "Mu_util": float("nan"),
            "c": float("nan"),
            "a": float("nan"),
            "z": float("nan"),
            "ku": float("nan"),
            "alpha2": 0.85,
            "gamma": 0.85,
            "phi": phi,
            "fctf": float("nan"),
            "I_gross": float("nan"),
            "Z_gross": float("nan"),
            "Mcr": float("nan"),
            "As_min": float("nan"),
            "d": d,
        }

    fctf = 0.6 * math.sqrt(fc)
    I_gross = b * D**3 / 12.0
    Z_gross = b * D**2 / 6.0
    Mcr = fctf * Z_gross / 1e6

    As_min = float("nan")
    if (
        d not in (None, 0)
        and fsy not in (None, 0)
        and b not in (None, 0)
        and fctf not in (None, 0)
    ):
        As_min = 0.4 * fctf * b * d / fsy

    alpha2, gamma = stress_block_factors(fc)

    T = Ast * fsy
    denom = alpha2 * fc * b * gamma
    if denom <= 0:
        return {
            "phi_Mu_cap": 0.0,
            "Mu_util": float("nan"),
            "c": float("nan"),
            "a": float("nan"),
            "z": float("nan"),
            "ku": float("nan"),
            "alpha2": alpha2,
            "gamma": gamma,
            "phi": phi,
            "fctf": fctf,
            "I_gross": I_gross,
            "Z_gross": Z_gross,
            "Mcr": Mcr,
            "As_min": As_min,
            "d": d,
        }

    c = T / denom
    lever_arm = compression_block_lever_arm_values(dn_mm=c, gamma=gamma, d_mm=d)
    a = lever_arm["a"]
    z = lever_arm["z"]
    Mu_nom = T * z / 1e6
    phi_Mu_cap = phi * Mu_nom
    Mu_util = Mu_star / phi_Mu_cap if phi_Mu_cap > 0 else float("inf")
    ku = c / d if d not in (None, 0) else float("nan")

    return {
        "phi_Mu_cap": phi_Mu_cap,
        "Mu_util": Mu_util,
        "c": c,
        "a": a,
        "z": z,
        "ku": ku,
        "alpha2": alpha2,
        "gamma": gamma,
        "phi": phi,
        "fctf": fctf,
        "I_gross": I_gross,
        "Z_gross": Z_gross,
        "Mcr": Mcr,
        "As_min": As_min,
        "d": d,
    }


def compute_bending_capacity_from_state_values(
    state: dict[str, Any],
    *,
    lig_diameter_mm: float,
) -> dict[str, Any]:
    """
    Aggregate legacy and signed bending capacity checks from an explicit state dict.

    lig_diameter_mm is explicit so Streamlit/session fallback behavior stays in the
    adapter instead of this pure calculation module.
    """
    st_state = state if hasattr(state, "get") else {}
    b = float(st_state.get("b") or 0.0)
    D = float(st_state.get("D") or 0.0)
    fc = float(st_state.get("fc") or 0.0)
    fsy = float(st_state.get("fsy") or 0.0)
    phi = float(st_state.get("phi_bend") or 0.8)

    Ast_bot = float(st_state.get("Ast_bot") or 0.0)
    Ast_top = float(st_state.get("Ast_top") or 0.0)
    d_pos = float(st_state.get("d") or 0.0)
    do_mm = float(st_state.get("do") or 0.0)

    cover_bot = float(st_state.get("cover_bot") or 0.0)
    db_bot = float(st_state.get("db_bot") or 0.0)
    nb_bot = float(st_state.get("nb_bot") or 0.0)
    rowgap_bot = float(st_state.get("rowgap_bot") or 0.0)

    actions = resolve_design_actions_from_state(st_state)
    Mu_star = float(actions.get("Mu", 0.0) or 0.0)
    Mu_pos_star = float(actions.get("Mu_pos", 0.0) or 0.0)
    Mu_neg_star = float(actions.get("Mu_neg", 0.0) or 0.0)
    has_sagging_case = bool(actions.get("has_sagging_case", False))
    has_hogging_case = bool(actions.get("has_hogging_case", False))

    legacy_results = compute_bending_capacity_legacy(
        b=b,
        D=D,
        fc=fc,
        fsy=fsy,
        Ast=Ast_bot,
        Mu_star=Mu_star,
        phi=phi,
        d_input=d_pos,
        cover_bot=cover_bot,
        db_bot=db_bot,
        nb_bot=nb_bot,
        rowgap_bot=rowgap_bot,
        lig_diameter_mm=lig_diameter_mm,
    )

    section_inputs = {
        "b": b,
        "D": D,
        "fc": fc,
        "fsy": fsy,
        "phi_bend": phi,
        "Ast_bot": Ast_bot,
        "d": d_pos,
        "Ast_top": Ast_top,
        "do": do_mm,
    }
    bend_pos = solve_bending_capacity("positive", Mu_pos_star, section_inputs)
    bend_neg = solve_bending_capacity("negative", Mu_neg_star, section_inputs)

    active_utils: list[tuple[str, float]] = []
    if has_sagging_case:
        active_utils.append(("Positive bending", float(bend_pos.get("util", 0.0) or 0.0)))
    if has_hogging_case:
        active_utils.append(("Negative bending", float(bend_neg.get("util", 0.0) or 0.0)))

    if active_utils:
        governing_case, util = max(active_utils, key=lambda x: x[1])
    else:
        governing_case, util = "", 0.0
    if governing_case == "Negative bending":
        phi_mu_governing = float(bend_neg.get("phi_Mu_kNm", 0.0) or 0.0)
    elif governing_case == "Positive bending":
        phi_mu_governing = float(bend_pos.get("phi_Mu_kNm", 0.0) or 0.0)
    else:
        phi_mu_governing = float(legacy_results.get("phi_Mu_cap", 0.0) or 0.0)

    return {
        "actions": actions,
        "Mu_star": Mu_star,
        "Mu_pos_star": Mu_pos_star,
        "Mu_neg_star": Mu_neg_star,
        "has_sagging_case": has_sagging_case,
        "has_hogging_case": has_hogging_case,
        "legacy": legacy_results,
        "bending_pos": bend_pos,
        "bending_neg": bend_neg,
        "governing_case": governing_case,
        "governing_util": float(util),
        "governing_phi_mu_kNm": float(phi_mu_governing),
        "Ast_bot": Ast_bot,
    }


def hogging_tension_effective_depth_mm(D: float, do_mm: float) -> float:
    """
    Hogging effective depth d: distance from the bottom compression fibre to the
    centroid of top tension steel.
    """
    df = float(D or 0.0)
    do_v = float(do_mm or 0.0)
    if df <= 0.0:
        return max(0.0, do_v)
    if do_v <= 0.0:
        return 0.0
    if do_v >= 0.35 * df:
        return do_v
    return max(0.0, df - do_v)


def compute_sls_bending_values(
    *,
    b,
    D,
    d,
    Ast,
    Ec,
    Es,
    Mu_star,
    nb_bot,
    db_bot,
    cover_bot,
    rowgap_bot,
    nb_top,
    db_top,
    cover_top,
) -> dict | None:
    """
    Compute simplified cracked-section SLS bending values.

    This is the pure calculation core previously embedded in
    bending_page._compute_sls_bending_values. It intentionally does not read or
    write Streamlit/session state.
    """
    if not (d and Ast and Ec and Es and b and D and Mu_star is not None):
        return None

    Ms = Mu_star

    layers_tension = []
    if nb_bot > 0 and db_bot > 0 and cover_bot > 0:
        As_bar_bot = math.pi * db_bot**2 / 4.0
        r_bot = db_bot / 2.0
        y_row0 = D - cover_bot - r_bot
        _ = (As_bar_bot, y_row0, rowgap_bot)
        layers_tension.append(
            {
                "name": "T1",
                "label": "Bottom tension steel",
                "y": d,
                "As": Ast,
            }
        )
    else:
        layers_tension.append(
            {
                "name": "T1",
                "label": "Bottom tension steel",
                "y": d,
                "As": Ast,
            }
        )

    comp_layer = None
    if nb_top > 0 and db_top > 0:
        As_top = nb_top * math.pi * db_top**2 / 4.0
        y_top = cover_top + db_top / 2.0
        comp_layer = {
            "name": "C1",
            "label": "Top steel (compression layer)",
            "y": y_top,
            "As": As_top,
        }
    _ = comp_layer

    n = Es / Ec if Ec > 0 else 0.0

    nAs = n * Ast
    if nAs > 0 and b > 0:
        a_coeff = b / 2.0
        b_coeff = nAs
        c_coeff = -nAs * d

        discriminant = b_coeff**2 - 4 * a_coeff * c_coeff
        if discriminant >= 0:
            dn_sls = (-b_coeff + math.sqrt(discriminant)) / (2 * a_coeff)
            dn_sls = max(1.0, min(dn_sls, D))
        else:
            dn_sls = d / 2.0
    else:
        dn_sls = d / 2.0

    Icr = (b * dn_sls**3 / 3.0) + nAs * (d - dn_sls) ** 2

    Ms_Nmm = Ms * 1e6
    kappa = Ms_Nmm / (Ec * Icr) if (Ec > 0 and Icr > 0) else 0.0

    eps_top = kappa * (0.0 - dn_sls)

    deepest = max(layers_tension, key=lambda layer: layer["y"], default=None)
    fs_outer = None
    eps_s_outer = None
    y_outer = None

    if deepest:
        y_outer = deepest["y"]
        eps_s_outer = kappa * (y_outer - dn_sls)
        fs_outer = Es * eps_s_outer

    return {
        "dn_sls": dn_sls,
        "Icr": Icr,
        "kappa": kappa,
        "eps_top": eps_top,
        "fs_outer": fs_outer,
        "eps_s_outer": eps_s_outer,
        "y_outer": y_outer,
    }


def sls_report_display_values(
    *,
    Ms_kNm: float,
    Ec: float,
    Es: float,
    d: float,
    dn_sls: float,
    kappa_sls: float,
    eps_top_sls: float | None = None,
) -> dict:
    """Derived SLS values used by the bending report display boxes."""
    n_sls = Es / Ec if Ec > 0 else 0.0
    Ms_Nmm = Ms_kNm * 1e6
    Icr = Ms_Nmm / (Ec * kappa_sls) if (Ec > 0 and kappa_sls != 0) else 0.0
    eps_top_display = (
        eps_top_sls if eps_top_sls is not None else kappa_sls * (0.0 - dn_sls)
    )
    eps_s_computed = kappa_sls * (d - dn_sls)
    fs_computed = Es * eps_s_computed
    return {
        "n_sls": n_sls,
        "Icr": Icr,
        "eps_top": eps_top_display,
        "eps_s": eps_s_computed,
        "fs": fs_computed,
    }


def bending_summary_check_values(
    *,
    Ast: float | None,
    As_min: float | None,
    Mu_star_kNm: float | None,
    phi_Mu_cap_kNm: float | None,
    Mu_util: float | None,
    Mcr_kNm: float | None,
    ku: float | None,
    ku_limit: float = 0.36,
) -> dict[str, Any]:
    """Derived summary check values used by the bending page cards."""
    if Mcr_kNm is not None and not (
        isinstance(Mcr_kNm, float) and math.isnan(Mcr_kNm)
    ):
        Mu_min = minimum_moment_capacity_kNm(Mcr_kNm)
    else:
        Mu_min = float("nan")

    As_ok = None
    if Ast is not None and As_min and not math.isnan(As_min):
        As_ok = Ast >= As_min

    Mu_ok = None
    if phi_Mu_cap_kNm and phi_Mu_cap_kNm > 0 and Mu_star_kNm is not None:
        Mu_ok = Mu_star_kNm <= phi_Mu_cap_kNm

    Mu_min_ok = None
    Mu_min_util = None
    if (
        phi_Mu_cap_kNm
        and phi_Mu_cap_kNm > 0
        and Mu_min is not None
        and not (isinstance(Mu_min, float) and math.isnan(Mu_min))
        and Mu_min > 0
    ):
        Mu_min_ok = phi_Mu_cap_kNm >= Mu_min
        Mu_min_util = Mu_min / phi_Mu_cap_kNm

    ku_val = ku if (ku is not None and not math.isnan(ku)) else None
    ku_ok = (ku_val is not None) and (ku_val <= ku_limit)

    return {
        "Mu_min": Mu_min,
        "As_ok": As_ok,
        "Mu_ok": Mu_ok,
        "Mu_min_ok": Mu_min_ok,
        "Mu_min_util": Mu_min_util,
        "ku_limit": ku_limit,
        "ku_val": ku_val,
        "ku_ok": ku_ok,
        "Mu_util": Mu_util,
    }


def solve_bending_capacity(moment_sign: str, M_star_kNm: float, inputs: dict) -> dict:
    """Solve signed flexural capacity for sagging/hogging demand."""
    sign = str(moment_sign or "positive").strip().lower()
    if sign not in {"positive", "negative"}:
        sign = "positive"

    tension_face, compression_face, _is_hog = resolve_bending_faces(sign)

    b = float(inputs.get("b", 0.0) or 0.0)
    D = float(inputs.get("D", 0.0) or 0.0)
    fc = float(inputs.get("fc", 0.0) or 0.0)
    fsy = float(inputs.get("fsy", 0.0) or 0.0)
    phi = float(inputs.get("phi_bend", 0.85) or 0.85)

    if tension_face == "bottom":
        Ast = float(inputs.get("Ast_bot", 0.0) or 0.0)
        d_mm = float(inputs.get("d", 0.0) or 0.0)
        tension_steel_label = "Bottom reinforcement"
    else:
        Ast = float(inputs.get("Ast_top", 0.0) or 0.0)
        do_mm = float(inputs.get("do", 0.0) or 0.0)
        d_mm = hogging_tension_effective_depth_mm(D, do_mm)
        tension_steel_label = "Top reinforcement"

    alpha2, gamma = stress_block_factors(fc)

    if min(b, D, fc, fsy, phi, Ast, d_mm) <= 0.0:
        return {
            "moment_sign": sign,
            "M_star_kNm": float(max(0.0, M_star_kNm)),
            "phi_Mu_kNm": 0.0,
            "Mu_nom_kNm": 0.0,
            "util": 0.0 if float(max(0.0, M_star_kNm)) <= 0.0 else float("inf"),
            "status": "\u2014",
            "dn_mm": float("nan"),
            "ku": float("nan"),
            "phi": phi,
            "tension_face": tension_face,
            "compression_face": compression_face,
            "tension_steel_label": tension_steel_label,
            "alpha2": alpha2,
            "gamma": gamma,
            "d_mm": d_mm,
            "Ast_tension_mm2": Ast,
        }

    T = Ast * fsy
    denom = alpha2 * fc * b * gamma
    c = T / denom if denom > 0 else float("nan")
    lever_arm = compression_block_lever_arm_values(dn_mm=c, gamma=gamma, d_mm=d_mm)
    a = lever_arm["a"] if c == c else float("nan")
    z = lever_arm["z"] if a == a else float("nan")
    Mu_nom = T * z / 1e6 if z == z else 0.0
    phi_Mu = phi * Mu_nom
    M_star = float(max(0.0, M_star_kNm))
    util = M_star / phi_Mu if phi_Mu > 0 else (0.0 if M_star <= 0 else float("inf"))
    ku = c / d_mm if d_mm > 0 else float("nan")

    if M_star <= 1e-9:
        status = "INFO"
    elif util <= 1.0:
        status = "PASS"
    else:
        status = "FAIL"

    return {
        "moment_sign": sign,
        "M_star_kNm": M_star,
        "phi_Mu_kNm": float(phi_Mu),
        "Mu_nom_kNm": float(Mu_nom),
        "util": float(util),
        "status": status,
        "dn_mm": float(c),
        "ku": float(ku),
        "phi": float(phi),
        "tension_face": tension_face,
        "compression_face": compression_face,
        "tension_steel_label": tension_steel_label,
        "alpha2": float(alpha2),
        "gamma": float(gamma),
        "d_mm": float(d_mm),
        "Ast_tension_mm2": float(Ast),
    }


def compute_stress_strain_state_values(
    *,
    state: str,
    b: float,
    D: float,
    d_plot: float,
    d_f: float,
    fc: float,
    fsy: float,
    As: float,
    Ec: float,
    Es: float,
) -> dict[str, float]:
    """
    Pure neutral-axis / strain-state solve used by the bending demo diagram.
    """
    b = float(b)
    D = float(D)
    d_plot = float(d_plot)
    d_f = float(d_f)
    fc = float(fc)
    fsy = float(fsy)
    As = float(As)
    Ec = float(Ec)
    Es = float(Es)

    alpha2, gamma = stress_block_factors(fc)

    eps_cu_uls = 0.003
    eps_c_sls = 0.0008
    eps_ext_unc = 0.0002

    if state == "ULS":
        denom = alpha2 * fc * b * gamma
        if denom > 0:
            c = As * fsy / denom
        else:
            c = D / 2.0
        c = min(max(c, 1.0), D - 1.0)

        eps_c = -eps_cu_uls
        eps_s = -eps_c * (d_f - c) / c
        fs_t = fsy
        return dict(
            b=b, D=D, d=d_plot, c=c,
            eps_c=eps_c, eps_s=eps_s,
            gamma=gamma, fs_t=fs_t,
            fc=fc, fsy=fsy, alpha2=alpha2,
        )

    if state in ("SLS", "SLS (cracked)"):
        n = Es / Ec if Ec not in (None, 0) else 0.0
        if n == 0.0 or As in (None, 0) or b in (None, 0):
            c = D / 2.0
        else:
            a_quad = 0.5 * b
            b_coef = n * As
            c_coef = -n * As * d_f
            if a_quad == 0:
                c = D / 2.0
            else:
                discr = b_coef ** 2 - 4 * a_quad * c_coef
                if discr < 0:
                    c = D / 2.0
                else:
                    r1 = (-b_coef + math.sqrt(discr)) / (2 * a_quad)
                    r2 = (-b_coef - math.sqrt(discr)) / (2 * a_quad)
                    cands = [r for r in (r1, r2) if 0 < r < D]
                    c = cands[0] if cands else D / 2.0

        c = min(max(c, 1.0), D - 1.0)
        eps_c = -eps_c_sls
        eps_s = -eps_c * (d_f - c) / c
        fs_t = Es * eps_s
        return dict(
            b=b, D=D, d=d_plot, c=c,
            eps_c=eps_c, eps_s=eps_s,
            gamma=gamma, fs_t=fs_t,
            fc=fc, fsy=fsy, alpha2=alpha2,
        )

    c = D / 2.0
    eps_c = -eps_ext_unc
    eps_s = eps_ext_unc * (d_f - c) / c
    fs_t = Ec * abs(eps_s)
    return dict(
        b=b, D=D, d=d_plot, c=c,
        eps_c=eps_c, eps_s=eps_s,
        gamma=1.0, fs_t=fs_t,
        fc=fc, fsy=fsy, alpha2=alpha2,
    )
