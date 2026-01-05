# bending_core.py
import math
import streamlit as st

from state_and_helpers import (
    get_param,
    update_results,
)


# ------------------------------------------------------------
#  Small formatting helper for tables
# ------------------------------------------------------------
def _fmt(val, pattern="{:.2f}"):
    """Safe formatter for table values."""
    try:
        if val is None:
            return "—"
        if isinstance(val, float) and math.isnan(val):
            return "—"
        return pattern.format(val)
    except Exception:
        return "—"


# ------------------------------------------------------------
#  BAR LAYOUT HELPER (used by several figures)
# ------------------------------------------------------------
def _layout_bars_in_rows(n_bars, b, cover, db, min_spacing, n_rows_max=2):
    """
    Lay out bars in 1–2 rows and return a list of (x_rel, row_index).
    """
    if n_bars is None or n_bars <= 0:
        return []

    n_bars = int(n_bars)
    inner = max(b - 2 * cover, db)

    # Try to fit in 1 row
    if n_bars == 1:
        n_per_row = [1]
    else:
        spacing_1row = inner / (n_bars - 1)
        if spacing_1row >= min_spacing or n_rows_max == 1:
            n_per_row = [n_bars]
        else:
            # Simple 2-row layout
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


# ------------------------------------------------------------
#  Helper – bottom tensile centroid depth
# ------------------------------------------------------------
def _effective_depth_centroid(b, D, nb_bot, db_bot, cover_bot, rowgap_bot):
    """
    Return effective depth d to the CENTROID of bottom tensile reinforcement.
    Pure function wrapper - all inputs passed as arguments (matches shear pattern).
    """
    return _effective_depth_centroid_pure(b, D, nb_bot, db_bot, cover_bot, rowgap_bot)


# ------------------------------------------------------------
#  BENDING CAPACITY CALC (α2–γ stress block, AS3600 Cl. 8.1.3)
# ------------------------------------------------------------
# Conditional caching: bypass in debug mode, cache in production
def _get_compute_bending_capacity_pure():
    """Get the cached or uncached version based on debug mode."""
    try:
        from src.debug.cache_control import cache_enabled
        if cache_enabled():
            # Caching enabled: use cache
            return st.cache_data(_compute_bending_capacity_pure_impl)
        else:
            # Cache bypass enabled: return unwrapped function
            return _compute_bending_capacity_pure_impl
    except ImportError:
        # Debug module not available: use cache
        return st.cache_data(_compute_bending_capacity_pure_impl)

def _compute_bending_capacity_pure_impl(b, D, fc, fsy, Ast, Mu_star, phi, d_input, cover_bot, db_bot, nb_bot, rowgap_bot):
    """
    Pure function version of bending capacity calculation.
    All inputs must be passed as arguments (no get_param calls).
    """
    # Effective depth
    d_centroid = _effective_depth_centroid_pure(b, D, nb_bot, db_bot, cover_bot, rowgap_bot)
    d = d_centroid if d_centroid not in (None, 0) else d_input

    # Missing-info fallback
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

    # Concrete flexural tensile strength (AS 3600-style)
    fctf = 0.6 * math.sqrt(fc)

    # Gross section properties and cracking moment
    I_gross = b * D**3 / 12.0
    Z_gross = b * D**2 / 6.0
    Mcr = fctf * Z_gross / 1e6  # kNm

    # As_min per AS 3600-style expression
    As_min = float("nan")
    if (
        d not in (None, 0)
        and fsy not in (None, 0)
        and b not in (None, 0)
        and fctf not in (None, 0)
    ):
        As_min = 0.4 * fctf * b * d / fsy

    # Stress-block factors
    alpha2_raw = 0.85 - 0.0015 * fc
    gamma_raw = 0.97 - 0.0025 * fc
    alpha2 = max(0.67, alpha2_raw)
    gamma = max(0.67, gamma_raw)

    # Flexural capacity
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
    a = gamma * c
    z = d - 0.5 * a
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


def _effective_depth_centroid_pure(b, D, nb_bot, db_bot, cover_bot, rowgap_bot):
    """Pure function version of effective depth calculation."""
    if b in (None, 0) or D in (None, 0) or nb_bot in (None, 0) or db_bot in (None, 0) or cover_bot in (None, 0):
        return None

    nb_bot = int(nb_bot)
    db_bot = float(db_bot)
    cover_bot = float(cover_bot)
    rowgap_bot = float(rowgap_bot) if rowgap_bot not in (None, 0) else 0.0

    # Bottom row depth (to bar centre) from top fibre
    d_row0 = D - cover_bot - db_bot / 2.0

    # Horizontal layout (bars per row)
    min_spacing_bot = 2.0 * db_bot
    layout = _layout_bars_in_rows(
        n_bars=nb_bot,
        b=b,
        cover=cover_bot,
        db=db_bot,
        min_spacing=min_spacing_bot,
        n_rows_max=2,
    )

    if not layout:
        return d_row0

    # Vertical layout (row spacing)
    row_pitch_bot = db_bot + rowgap_bot

    y_positions = []
    for _, row_idx in layout:
        y_positions.append(d_row0 - row_idx * row_pitch_bot)

    if not y_positions:
        return d_row0

    return sum(y_positions) / len(y_positions)


def _compute_bending_capacity():
    """
    Compute a simple φMu,cap using a rectangular stress block.
    Reads from shared state and calls the cached pure function (matches shear pattern).

    IMPORTANT:
      • d is depth to CENTROID of tensile reo
      • fctf, Mcr and As_min follow AS 3600-style expressions
    """
    # Pull shared values for calculations (matches shear pattern)
    b = get_param("b")
    D = get_param("D")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")
    phi = get_param("phi_bend")
    d_input = get_param("d")
    cover_bot = get_param("cover_bot")
    db_bot = get_param("db_bot")
    nb_bot = get_param("nb_bot")
    rowgap_bot = get_param("rowgap_bot")

    # Call cached pure function (with debug bypass)
    _compute_fn = _get_compute_bending_capacity_pure()
    results = _compute_fn(
        b=b, D=D, fc=fc, fsy=fsy, Ast=Ast, Mu_star=Mu_star, phi=phi,
        d_input=d_input, cover_bot=cover_bot, db_bot=db_bot,
        nb_bot=nb_bot, rowgap_bot=rowgap_bot
    )
    
    # Extract values for update_results
    phi_Mu_cap = results["phi_Mu_cap"]
    Mu_util = results["Mu_util"]
    ku = results["ku"]
    As_min = results["As_min"]
    Mcr = results["Mcr"]

    # --------------------------------------------------
    # Minimum strength + ductility values
    # (for Inputs page summary table)
    # --------------------------------------------------
    
    # 1) Minimum steel area As_min_req (already calculated as As_min)
    As_min_req = As_min if not (isinstance(As_min, float) and math.isnan(As_min)) else None
    
    # 2) Minimum moment Mx_min_req = 1.2 * Mcr (Tab 2 rule)
    Mx_min_req = None
    if Mcr is not None and not (isinstance(Mcr, float) and math.isnan(Mcr)):
        Mx_min_req = 1.2 * Mcr
    
    # 3) Neutral axis ratio + limit
    k_u = ku if not (isinstance(ku, float) and math.isnan(ku)) else None
    k_u_lim = 0.36  # Teaching limit (AS 3600 limit for ductile design)

    update_results(
        phi_Mu_cap=phi_Mu_cap,
        Mu_utilisation=Mu_util,
        As_min_req=As_min_req,
        Mx_min_req=Mx_min_req,
        k_u=k_u,
        k_u_lim=k_u_lim,
    )

    return results


# ============================
# STRESS–STRAIN STATE
# ============================
def _stress_strain_state(state: str):
    """
    Compute neutral axis and strain/stress info for the demo diagram.
    Uses real shared parameters where possible, but returns a complete
    dict with geometry and materials so the plotting helper doesn't
    need to call get_param again.
    """
    # Try to use real values from the app; fall back to teaching defaults
    b = get_param("b") or 300.0
    D = get_param("D") or 600.0
    fc = get_param("fc")
    fsy = get_param("fsy")
    As = get_param("Ast_bot")
    Ec = get_param("Ec")
    Es = get_param("Es")

    # Fallbacks if missing / zero
    if fc is None:
        fc = 32.0
    if fsy is None or fsy == 0:
        fsy = 500.0
    if Ec is None or Ec == 0:
        Ec = 4700 * math.sqrt(fc)
    if Es is None or Es == 0:
        Es = 200000.0

    # Effective depth to centroid of bottom steel
    # Pull shared values for calculations (matches shear pattern)
    b = get_param("b")
    D = get_param("D")
    nb_bot = get_param("nb_bot")
    db_bot = get_param("db_bot")
    cover_bot = get_param("cover_bot")
    rowgap_bot = get_param("rowgap_bot")
    
    d = _effective_depth_centroid_pure(b, D, nb_bot, db_bot, cover_bot, rowgap_bot)
    if d in (None, 0):
        cover_bot = cover_bot or 40.0
        db_bot = db_bot or 24.0
        d = D - cover_bot - db_bot / 2.0

    # If As missing or zero, estimate from nb_bot & db_bot
    if As is None or As == 0:
        nb_bot = get_param("nb_bot") or 3
        db_bot = get_param("db_bot") or 24.0
        As = nb_bot * math.pi * db_bot**2 / 4.0

    # AS3600 α2–γ
    alpha2_raw = 0.85 - 0.0015 * fc
    gamma_raw = 0.97 - 0.0025 * fc
    alpha2 = max(0.67, alpha2_raw)
    gamma = max(0.67, gamma_raw)

    # Default strains
    eps_cu_uls = 0.003
    eps_c_sls = 0.0008
    eps_ext_unc = 0.0002

    # ----- ULS state -----
    if state == "ULS":
        denom = alpha2 * fc * b * gamma
        if denom > 0:
            c = As * fsy / denom
        else:
            c = D / 2.0

        c = min(max(c, 1.0), D - 1.0)

        eps_c = -eps_cu_uls
        eps_s = -eps_c * (d - c) / c
        fs_t = fsy  # tension steel at approx. yield

        return dict(
            b=b, D=D, d=d, c=c,
            eps_c=eps_c, eps_s=eps_s,
            gamma=gamma, fs_t=fs_t,
            fc=fc, fsy=fsy, alpha2=alpha2,
        )

    # ----- SLS cracked state -----
    if state == "SLS (cracked)":
        n = Es / Ec if Ec not in (None, 0) else 0.0

        if n == 0.0 or As in (None, 0) or b in (None, 0):
            c = D / 2.0
        else:
            a_quad = 0.5 * b
            b_coef = n * As
            c_coef = -n * As * d

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
        eps_s = -eps_c * (d - c) / c
        fs_t = Es * eps_s

        return dict(
            b=b, D=D, d=d, c=c,
            eps_c=eps_c, eps_s=eps_s,
            gamma=gamma, fs_t=fs_t,
            fc=fc, fsy=fsy, alpha2=alpha2,
        )

    # ----- Uncracked state -----
    c = D / 2.0
    eps_c = -eps_ext_unc
    eps_s = eps_ext_unc * (d - c) / c
    fs_t = Ec * abs(eps_s)

    return dict(
        b=b, D=D, d=d, c=c,
        eps_c=eps_c, eps_s=eps_s,
        gamma=1.0, fs_t=fs_t,
        fc=fc, fsy=fsy, alpha2=alpha2,
    )
