from __future__ import annotations

import math


# AS 3600:2018 Table 8.6.2.2(A) - maximum steel stress for tension or flexure.
# Structure: {db_mm: {wmax_mm: sigma_max_MPa}}
TABLE_8_6_2_2A = {
    10: {0.2: 190, 0.3: 265, 0.4: 335},
    12: {0.2: 175, 0.3: 245, 0.4: 305},
    16: {0.2: 155, 0.3: 215, 0.4: 270},
    20: {0.2: 140, 0.3: 195, 0.4: 240},
    24: {0.2: 125, 0.3: 175, 0.4: 215},
    28: {0.2: 115, 0.3: 160, 0.4: 200},
    32: {0.2: 105, 0.3: 150, 0.4: 185},
    36: {0.2: 100, 0.3: 140, 0.4: 175},
    40: {0.2: 90, 0.3: 130, 0.4: 165},
}

# AS 3600:2018 Table 8.6.2.2(B) - maximum steel stress for flexure vs spacing.
# Structure: {spacing_mm: {wmax_mm: sigma_max_MPa}}
TABLE_8_6_2_2B = {
    50: {0.2: 200, 0.3: 300, 0.4: 400},
    100: {0.2: 170, 0.3: 270, 0.4: 360},
    150: {0.2: 155, 0.3: 245, 0.4: 330},
    200: {0.2: 145, 0.3: 225, 0.4: 300},
    250: {0.2: 135, 0.3: 210, 0.4: 280},
    300: {0.2: 125, 0.3: 200, 0.4: 260},
}


def nearest_table_key(mapping: dict, value: float) -> int:
    """Return integer key in mapping closest to value."""
    keys = sorted(mapping.keys())
    return min(keys, key=lambda key: abs(key - value))


def table_sigma_max_a(db_mm: float, wmax_mm: float) -> float:
    """Lookup sigma_s,max from Table 8.6.2.2(A) using nearest db and wmax."""
    wopt = min([0.2, 0.3, 0.4], key=lambda value: abs(value - wmax_mm))
    db_key = nearest_table_key(TABLE_8_6_2_2A, db_mm)
    return TABLE_8_6_2_2A[db_key][wopt]


def table_sigma_max_b(spacing_mm: float, wmax_mm: float) -> float:
    """Lookup sigma_s,max from Table 8.6.2.2(B) using nearest spacing and wmax."""
    wopt = min([0.2, 0.3, 0.4], key=lambda value: abs(value - wmax_mm))
    spacing_key = nearest_table_key(TABLE_8_6_2_2B, spacing_mm)
    return TABLE_8_6_2_2B[spacing_key][wopt]


def calc_eps_diff(
    sigma_sr: float,
    Es: float,
    fct_eff: float,
    rho_eff: float,
    ne: float,
    eps_cs: float,
) -> float:
    """
    Strain difference from AS 3600:2018 8.6.2.3(2).

    All strains are dimensionless.
    """
    if rho_eff <= 0:
        return 0.0

    term1 = sigma_sr / Es
    term2 = 0.6 * fct_eff / (Es * rho_eff) * (1.0 + ne * rho_eff)
    eps_diff = term1 - term2 + eps_cs

    eps_min = 0.6 * sigma_sr / Es
    return max(eps_diff, eps_min)


def calc_sr_max(c_mm: float, db_mm: float, rho_eff: float, k1: float, k2: float) -> float:
    """
    Maximum crack spacing from AS 3600:2018 8.6.2.3(3), in mm.
    """
    if rho_eff <= 0:
        return 0.0
    return 3.4 * c_mm + 0.3 * k1 * k2 * db_mm / rho_eff


def average_active_bar_spacing_mm(spacing_values) -> float | None:
    """Average active crack-bar spacings, preserving the empty-list no-override rule."""
    vals = list(spacing_values or [])
    if not vals:
        return None
    return float(sum(float(v) for v in vals) / max(len(vals), 1))


def microstrain_to_strain(microstrain: float) -> float:
    """Convert microstrain to dimensionless strain."""
    return float(microstrain or 0.0) * 1e-6


def compute_crack_control_values(
    *,
    b: float,
    D: float,
    c: float,
    db: float,
    spacing: float,
    Ast: float,
    fc: float,
    Ec: float,
    Es: float,
    fsy: float,
    wmax_choice: float,
    member_type: str,
    sigma_sr: float,
    phi_ce: float,
    eps_cs: float,
    k1: float,
    k2: float,
    crack_tension_face: str = "bottom",
) -> dict:
    """
    Pure crack-control table and direct-width calculations.

    The caller owns session reads, active reinforcement resolution, report publishing,
    and result publication.
    """
    d_eff = D - c - db / 2.0 if crack_tension_face == "bottom" else c + db / 2.0
    height_eff = min(2.5 * c, max(D - d_eff, 0.0), D / 2.0)
    Aceff = b * max(height_eff, 1.0)
    rho_eff = Ast / Aceff if Aceff > 0 else 0.0

    sigma_table_A = table_sigma_max_A(db, wmax_choice)
    sigma_table_B = table_sigma_max_B(spacing, wmax_choice)
    if member_type == "Primarily tension":
        sigma_table_combined = sigma_table_A
    else:
        sigma_table_combined = max(sigma_table_A, sigma_table_B)

    sigma_08fsy = 0.8 * fsy
    sigma_allow_table = min(sigma_table_combined, sigma_08fsy)
    utilisation_table = sigma_sr / sigma_allow_table if sigma_allow_table > 0 else 0.0
    passes_table = utilisation_table <= 1.0

    fct_eff = 0.6 * math.sqrt(max(fc, 1.0))
    ne = (1.0 + phi_ce) * Es / Ec if Ec > 0 else 0.0
    eps_diff = calc_eps_diff(
        sigma_sr=sigma_sr,
        Es=Es,
        fct_eff=fct_eff,
        rho_eff=rho_eff,
        ne=ne,
        eps_cs=eps_cs,
    )
    sr_max = calc_sr_max(c_mm=c, db_mm=db, rho_eff=rho_eff, k1=k1, k2=k2)
    w_calc = sr_max * eps_diff
    utilisation_w = w_calc / wmax_choice if wmax_choice > 0 else 0.0
    passes_w = utilisation_w <= 1.0

    return {
        "d_eff": d_eff,
        "height_eff": height_eff,
        "Aceff": Aceff,
        "rho_eff": rho_eff,
        "sigma_table_A": sigma_table_A,
        "sigma_table_B": sigma_table_B,
        "sigma_table_combined": sigma_table_combined,
        "sigma_08fsy": sigma_08fsy,
        "sigma_allow_table": sigma_allow_table,
        "utilisation_table": utilisation_table,
        "passes_table": passes_table,
        "fct_eff": fct_eff,
        "ne": ne,
        "eps_diff": eps_diff,
        "sr_max": sr_max,
        "w_calc": w_calc,
        "utilisation_w": utilisation_w,
        "passes_w": passes_w,
    }


def pick_governing_check_row(rows: list) -> dict | None:
    """Return the non-informational row with highest numeric utilisation."""
    numeric_rows: list[tuple[float, dict]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("is_informational"):
            continue
        util_raw = row.get("util")
        if util_raw is None or util_raw == "" or util_raw == "—":
            continue
        try:
            util_val = float(util_raw)
        except (TypeError, ValueError):
            continue
        numeric_rows.append((util_val, row))
    if not numeric_rows:
        return None
    numeric_rows.sort(key=lambda x: x[0], reverse=True)
    return numeric_rows[0][1]


# Legacy public names used by the existing pages/core modules.
_nearest_key = nearest_table_key
table_sigma_max_A = table_sigma_max_a
table_sigma_max_B = table_sigma_max_b
