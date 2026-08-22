# bending_core.py
import math
from typing import Any, Mapping
import streamlit as st

from bending_layer_semantics import resolve_bending_faces
from state_runtime_gateway import (
    get_param,
    resolve_design_actions,
    update_results,
)
from calculations.bending import (
    bar_area_mm2,
    compute_bending_capacity_legacy,
    compute_sls_bending_values,
    compute_stress_strain_state_values,
    effective_depth_centroid_mm,
    effective_depth_with_links_mm,
    hogging_tension_effective_depth_mm,
    layout_bars_in_rows as _layout_bars_in_rows,
    minimum_moment_capacity_kNm,
    solve_bending_capacity,
)
from calculations.materials import derive_concrete_modulus_from_fc
from inputs_application.authoritative_check_packs import current_authoritative_family
from inputs_application.active_beam_engineering_state import (
    resolve_active_beam_engineering_state,
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

def _compute_bending_capacity_pure_impl(
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
    lig_diameter_mm=None,
):
    """
    Pure function version of bending capacity calculation.
    All inputs must be passed as arguments (no get_param calls).
    """
    if lig_diameter_mm is None:
        lig_diameter_mm = float(get_param("lig_d", 0.0) or 0.0)
    return compute_bending_capacity_legacy(
        b=b,
        D=D,
        fc=fc,
        fsy=fsy,
        Ast=Ast,
        Mu_star=Mu_star,
        phi=phi,
        d_input=d_input,
        cover_bot=cover_bot,
        db_bot=db_bot,
        nb_bot=nb_bot,
        rowgap_bot=rowgap_bot,
        lig_diameter_mm=lig_diameter_mm,
    )


def _effective_depth_centroid_pure(
    b,
    D,
    nb_bot,
    db_bot,
    cover_bot,
    rowgap_bot,
    lig_diameter_mm=None,
):
    """Pure function version of effective depth calculation."""
    if lig_diameter_mm is None:
        lig_diameter_mm = float(get_param("lig_d", 0.0) or 0.0)
    return effective_depth_centroid_mm(
        b,
        D,
        nb_bot,
        db_bot,
        cover_bot,
        rowgap_bot,
        lig_diameter_mm,
    )


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
    phi = get_param("phi_bend")
    d_input = get_param("d")
    cover_bot = get_param("cover_bot")
    db_bot = get_param("db_bot")
    nb_bot = get_param("nb_bot")
    rowgap_bot = get_param("rowgap_bot")
    lig_diameter_mm = float(get_param("lig_d", 0.0) or 0.0)

    # Call cached pure function (with debug bypass)
    _compute_fn = _get_compute_bending_capacity_pure()
    actions = resolve_design_actions()
    Mu_star = float(actions.get("Mu", get_param("Mu_star") or 0.0) or 0.0)
    results = _compute_fn(
        b=b, D=D, fc=fc, fsy=fsy, Ast=get_param("Ast_bot"), Mu_star=Mu_star, phi=phi,
        d_input=d_input, cover_bot=cover_bot, db_bot=db_bot,
        nb_bot=nb_bot, rowgap_bot=rowgap_bot, lig_diameter_mm=lig_diameter_mm
    )
    if st.session_state.get("_dev_mode", False):
        dbg = dict(st.session_state.get("_debug_d_consistency", {}))
        dbg["calc_engine_d_mm"] = float(results.get("d", d_input) or 0.0)
        st.session_state["_debug_d_consistency"] = dbg
    
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
    
    # 2) Minimum moment capacity (Tab 2 rule)
    Mx_min_req = None
    if Mcr is not None and not (isinstance(Mcr, float) and math.isnan(Mcr)):
        Mx_min_req = minimum_moment_capacity_kNm(Mcr)
    
    # 3) Neutral axis ratio + limit
    k_u = ku if not (isinstance(ku, float) and math.isnan(ku)) else None
    k_u_lim = 0.36  # Teaching limit (AS 3600 limit for ductile design)

    has_sagging_case = bool(actions.get("has_sagging_case", False))
    has_hogging_case = bool(actions.get("has_hogging_case", False))
    inputs = {
        "b": b,
        "D": D,
        "fc": fc,
        "fsy": fsy,
        "phi_bend": phi,
        "Ast_bot": get_param("Ast_bot"),
        "Ast_top": get_param("Ast_top"),
        "d": get_param("d"),
        "do": get_param("do"),
    }
    bending_pos = solve_bending_capacity("positive", float(actions.get("Mu_pos", 0.0) or 0.0), inputs)
    bending_neg = solve_bending_capacity("negative", float(actions.get("Mu_neg", 0.0) or 0.0), inputs)

    active_utils = []
    if has_sagging_case:
        active_utils.append(("Positive bending", float(bending_pos.get("util", 0.0) or 0.0)))
    if has_hogging_case:
        active_utils.append(("Negative bending", float(bending_neg.get("util", 0.0) or 0.0)))
    if active_utils:
        governing_case, governing_util = max(active_utils, key=lambda x: x[1])
    else:
        governing_case, governing_util = "", 0.0

    if governing_case == "Negative bending":
        phi_mu_compat = float(bending_neg.get("phi_Mu_kNm", 0.0) or 0.0)
        mu_util_compat = float(bending_neg.get("util", 0.0) or 0.0)
    elif governing_case == "Positive bending":
        phi_mu_compat = float(bending_pos.get("phi_Mu_kNm", 0.0) or 0.0)
        mu_util_compat = float(bending_pos.get("util", 0.0) or 0.0)
    else:
        phi_mu_compat = float(bending_pos.get("phi_Mu_kNm", phi_Mu_cap) or 0.0)
        mu_util_compat = 0.0

    uls_c_mm: float | None = None
    uls_gamma: float | None = None
    try:
        _c_p = bending_pos.get("dn_mm")
        _g_p = bending_pos.get("gamma")
        if _c_p is not None and _g_p is not None:
            _c_f = float(_c_p)
            _g_f = float(_g_p)
            if math.isfinite(_c_f) and math.isfinite(_g_f) and _c_f > 0.0 and _g_f > 0.0:
                uls_c_mm = _c_f
                uls_gamma = _g_f
    except (TypeError, ValueError):
        uls_c_mm = None
        uls_gamma = None

    update_results(
        phi_Mu_cap=phi_mu_compat,
        Mu_utilisation=mu_util_compat,
        phi_Mu_pos_kNm=float(bending_pos.get("phi_Mu_kNm", 0.0) or 0.0),
        phi_Mu_neg_kNm=float(bending_neg.get("phi_Mu_kNm", 0.0) or 0.0),
        Mu_nom_pos_kNm=float(bending_pos.get("Mu_nom_kNm", 0.0) or 0.0),
        Mu_nom_neg_kNm=float(bending_neg.get("Mu_nom_kNm", 0.0) or 0.0),
        bending_util_pos=float(bending_pos.get("util", 0.0) or 0.0),
        bending_util_neg=float(bending_neg.get("util", 0.0) or 0.0),
        bending_status_pos=str(bending_pos.get("status", "")),
        bending_status_neg=str(bending_neg.get("status", "")),
        bending_has_sagging_case=bool(has_sagging_case),
        bending_has_hogging_case=bool(has_hogging_case),
        bending_has_positive_case=bool(has_sagging_case),
        bending_has_negative_case=bool(has_hogging_case),
        bending_governing_case=str(governing_case or ""),
        bending_util_governing=float(governing_util),
        As_min_req=As_min_req,
        Mx_min_req=Mx_min_req,
        k_u=k_u,
        k_u_lim=k_u_lim,
        bending_uls_c_pos_mm=float(uls_c_mm) if uls_c_mm is not None else 0.0,
        bending_uls_gamma_pos=float(uls_gamma) if uls_gamma is not None else 0.0,
    )

    return results


def compute_sls_bending_values_from_state(publish: bool = True) -> float | None:
    """
    Compute SLS bending values from shared state and preserve legacy publication.

    This is the non-page adapter for the pure calculations.bending SLS helper.
    It intentionally owns session/result side effects so orchestration does not
    need to import bending_page.
    """
    b = get_param("b")
    D = get_param("D")
    d = get_param("d")
    Ast = get_param("Ast_bot")
    Ec = get_param("Ec")
    Es = get_param("Es")
    Mu_star = get_param("sls_Mstar")
    nb_bot = get_param("nb_bot")
    db_bot = get_param("db_bot")
    cover_bot = get_param("cover_bot")
    rowgap_bot = get_param("rowgap_bot")
    nb_top = get_param("nb_top")
    db_top = get_param("db_top")
    cover_top = get_param("cover_top")

    sls_values = compute_sls_bending_values(
        b=b,
        D=D,
        d=d,
        Ast=Ast,
        Ec=Ec,
        Es=Es,
        Mu_star=Mu_star,
        nb_bot=nb_bot,
        db_bot=db_bot,
        cover_bot=cover_bot,
        rowgap_bot=rowgap_bot,
        nb_top=nb_top,
        db_top=db_top,
        cover_top=cover_top,
    )
    if sls_values is None:
        return None

    dn_sls = sls_values["dn_sls"]
    kappa = sls_values["kappa"]
    eps_top = sls_values["eps_top"]
    fs_outer = sls_values["fs_outer"]
    eps_s_outer = sls_values["eps_s_outer"]
    y_outer = sls_values["y_outer"]

    try:
        st.session_state["bending_sls_dn"] = float(dn_sls)
        st.session_state["bending_sls_kappa"] = float(kappa)
        st.session_state["bending_sls_eps_top"] = float(eps_top)
        if fs_outer is not None:
            st.session_state["bending_sls_fs_outer"] = float(fs_outer)
        if eps_s_outer is not None:
            st.session_state["bending_sls_eps_s_outer"] = float(eps_s_outer)
        if y_outer is not None:
            st.session_state["bending_sls_y_tension_outer"] = float(y_outer)
        if eps_s_outer is not None and y_outer is not None:
            st.session_state["bending_sls_eps_bot"] = float(eps_s_outer)
            st.session_state["bending_sls_y_bot"] = float(y_outer)

        if publish and fs_outer is not None:
            update_results(
                sigma_s_sls=float(fs_outer),
                bending_sls_fs_outer=float(fs_outer),
                bending_sls_dn_mm=float(dn_sls),
            )
        return fs_outer
    except Exception:
        return None


def compute_sigma_s_sls_for_crack(publish: bool = True) -> float:
    """
    Compute service tensile steel stress for crack checks and publish to results.
    Must NOT depend on bending UI tabs.
    """
    fs_tension = None
    try:
        fs_tension = compute_sls_bending_values_from_state(publish=publish)
    except Exception:
        fs_tension = None

    if fs_tension is None:
        try:
            fs_tension = float(get_param("bending_sls_fs_outer", 0.0))
        except Exception:
            fs_tension = 0.0

    fs_tension = 0.0 if fs_tension is None else float(fs_tension)
    if publish:
        update_results(sigma_s_sls=fs_tension, sigma_sr=fs_tension)
    return fs_tension


# ============================
# STRESS–STRAIN STATE
# ============================
def _stress_strain_state(
    state: str,
    moment_sign: str = "positive",
    *,
    input_state: Mapping[str, Any] | None = None,
    authoritative_bending: Mapping[str, Any] | None = None,
):
    """
    Compute neutral axis and strain/stress info for the demo diagram.
    Uses real shared parameters where possible, but returns a complete
    dict with geometry and materials so the plotting helper doesn't
    need to call get_param again.

    moment_sign:
      - "positive" (sagging): bottom tension steel, compression at top; c is NA depth from top.
      - "negative" (hogging): top tension steel, compression at bottom; c is NA depth from bottom.
    """
    # Resolve one revision-bound source before reading any diagram input.  The
    # previous implementation mixed mutable widget mirrors (geometry and d)
    # with a newer authoritative neutral axis after Design Brain Apply.
    # That produced a visually plausible but impossible hybrid diagram and
    # then cached it under the new revision.  Explicit callers can provide the
    # same immutable projection used for the section layout; compatibility
    # callers are routed through the active-beam snapshot boundary here.
    if input_state is None:
        input_values = dict(
            resolve_active_beam_engineering_state(st.session_state).values
        )
    else:
        input_values = dict(input_state)

    def _input(name: str, default: Any = None) -> Any:
        value = input_values.get(name, default)
        return default if value is None else value

    b = float(_input("b", 400.0) or 400.0)
    D = float(_input("D", 600.0) or 600.0)
    fc = _input("fc")
    fsy = _input("fsy")
    As = _input("Ast_bot")
    Ec = _input("Ec")
    Es = _input("Es")

    # Fallbacks if missing / zero
    if fc is None:
        fc = 32.0
    if fsy is None or fsy == 0:
        fsy = 500.0
    if Ec is None or Ec == 0:
        Ec = derive_concrete_modulus_from_fc(fc)
    if Es is None or Es == 0:
        Es = 200000.0

    nb_bot = _input("nb_bot")
    db_bot = _input("db_bot", _input("db_bot_1"))
    cover_bot = _input("cover_bot")
    rowgap_bot = _input("rowgap_bot")
    lig_diameter_mm = float(_input("lig_d", 0.0) or 0.0)

    # ``rebuild_engineering_derived_state`` publishes the true multi-row
    # centroid.  Only old/migration sessions need the legacy fallback solve.
    d = float(_input("d", 0.0) or 0.0)
    if d <= 0.0:
        d = _effective_depth_centroid_pure(
            b,
            D,
            nb_bot,
            db_bot,
            cover_bot,
            rowgap_bot,
            lig_diameter_mm,
        )
    if d in (None, 0):
        if cover_bot is None:
            cover_bot = 40.0
        if db_bot is None:
            db_bot = 24.0
        d = effective_depth_with_links_mm(
            D_mm=D,
            cover_to_ligs_mm=cover_bot,
            lig_diameter_mm=lig_diameter_mm,
            bar_diameter_mm=db_bot,
        )

    # If As missing or zero, estimate from nb_bot & db_bot
    if As is None or As == 0:
        nb_bot = _input("nb_bot", 3)
        db_bot = _input("db_bot", _input("db_bot_1", 24.0))
        As = bar_area_mm2(nb_bot, db_bot)

    authoritative = (
        dict(authoritative_bending)
        if authoritative_bending is not None
        else current_authoritative_family(st.session_state, "bending")
    )

    _, _, is_hogging = resolve_bending_faces(moment_sign)
    # d_plot = tension steel centroid y measured from top; d_f = depth compression face → tension steel
    d_plot = float(d)
    d_f = float(d)
    if is_hogging:
        As = _input("Ast_top")
        do_mm = float(_input("do", 0.0) or 0.0)
        Df = float(D or 0.0)
        cover_top = _input("cover_top")
        db_top = _input("db_top", _input("db_top_1"))
        nb_top = _input("nb_top")
        d_f = hogging_tension_effective_depth_mm(Df, do_mm)
        if d_f <= 1e-6 and Df > 0:
            ct = cover_top if cover_top is not None else 40.0
            dt = db_top if db_top is not None else 16.0
            d_plot = ct + dt / 2.0
            d_f = max(0.0, Df - d_plot)
        else:
            d_plot = max(0.0, Df - d_f)
        if As is None or As == 0:
            nb_t = int(nb_top) if nb_top is not None else 2
            db_t = float(db_top) if db_top is not None else 16.0
            As = bar_area_mm2(nb_t, db_t)

    # The published effective depth is the exact centroid used by the current
    # authoritative layer model.  Use it for the ULS strain line rather than
    # independently reducing the row arrangement a second time.
    try:
        authoritative_d = float(authoritative.get("d_mm")) if authoritative else float("nan")
    except (AttributeError, TypeError, ValueError):
        authoritative_d = float("nan")
    if math.isfinite(authoritative_d) and authoritative_d > 0.0:
        d_f = authoritative_d
        d_plot = max(0.0, float(D) - authoritative_d) if is_hogging else authoritative_d

    state_values = compute_stress_strain_state_values(
        state=state,
        b=b,
        D=D,
        d_plot=d_plot,
        d_f=d_f,
        fc=fc,
        fsy=fsy,
        As=As,
        Ec=Ec,
        Es=Es,
    )
    # Carry the revision-bound material stiffness into the pure figure
    # builder.  Plotting must not reacquire an older widget mirror after a
    # Design Brain revision has already been committed.
    state_values.update(Ec=float(Ec), Es=float(Es))

    # The ULS diagram is explanatory evidence for the calculation cards.  Its
    # strain line must therefore use the same revision-matched neutral-axis
    # solution, not the retired single-layer diagram approximation.
    if state == "ULS":
        try:
            dn = float(authoritative.get("dn_mm")) if authoritative else float("nan")
            d_authoritative = float(authoritative.get("d_mm")) if authoritative else float("nan")
            if math.isfinite(dn) and math.isfinite(d_authoritative) and dn > 1e-9:
                state_values.update(
                    c=dn,
                    eps_c=-0.003,
                    eps_s=0.003 * (d_authoritative - dn) / dn,
                    d=d_plot,
                )
        except (AttributeError, TypeError, ValueError):
            pass

    return state_values

    # AS3600 α2–γ
