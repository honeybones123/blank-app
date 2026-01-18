# bending_page.py
# ============================
# BENDING PAGE
# ============================

import math
import textwrap
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

from state_and_helpers import (
    get_sync_callbacks,
    get_param,
    update_results,
    init_shared_session_state,
    DEBUG_MODE,
    debug_print,
)
from widgets_helpers import apply_global_widget_css, apply_calcbox_css, number_row, select_row, show_reo_message, apply_step_expander_css, apply_step_summary_expander_css, info_i_button, page_divider
from bending_core import _fmt, _compute_bending_capacity, _stress_strain_state
from bending_diagrams import (
    _plot_stress_strain_profiles,
    _plot_material_stress_strain_curves,
)
from bending_tabs import render_uls_tab, render_min_strength_tab, render_sls_tab
from ui_seamless_steps import (
    inject_seamless_steps_css,
    render_clickable_summary_table,
    bind_summary_clicks,
    step_card,
)

# Safe option lists for reinforcement inputs
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]


def _coalesce_num(v, default: float) -> float:
    """Return default only if v is None (preserves 0)."""
    return default if v is None else float(v)


# Conditional caching: bypass in debug mode, cache in production
def _get_build_beam_3d_figure_pure():
    """Get the cached or uncached version of _build_beam_3d_figure_pure based on debug mode."""
    try:
        from src.debug.cache_control import cache_enabled
        if cache_enabled():
            # Caching enabled: use cache
            return st.cache_resource(show_spinner=False)(_build_beam_3d_figure_pure_impl)
        else:
            # Cache bypass enabled: return unwrapped function
            return _build_beam_3d_figure_pure_impl
    except ImportError:
        # Debug module not available: use cache
        return st.cache_resource(show_spinner=False)(_build_beam_3d_figure_pure_impl)

def _build_beam_3d_figure_pure_impl(b, D, L, Mu_star, phi_Mu_cap, c, strain_state, 
                                reo_layout, cover_bot, cover_top, 
                                cover_side, rowgap_bot, rowgap_top, lig_d, lig_legs, s_lig, 
):
    """
    Pure function version of 3D beam figure generation.
    All inputs must be passed as arguments (no get_param calls).
    
    Args:
        reo_layout: Pre-computed reinforcement layout dict from compute_longitudinal_reo_layout()
    
    3D visualisation:
      - Concrete prism
      - Longitudinal reo with consistent cover (matched to Inputs page intent)
      - Simple stirrups
      - Neutral axis plane
    """

    # ---------- Basic sanity checks ----------
    try:
        vals = [b, D, L, Mu_star, phi_Mu_cap, c]
        if any(v is None for v in vals):
            return None
        b = float(b)
        D = float(D)
        L = float(L)
        Mu_star = float(Mu_star)
        phi_Mu_cap = float(phi_Mu_cap)
        c = float(c)
        if any(math.isnan(v) for v in (b, D, L, Mu_star, phi_Mu_cap, c)):
            return None
    except Exception:
        return None

    if phi_Mu_cap <= 0.0 or D <= 0.0 or b <= 0.0 or L <= 0.0:
        return None

    # ---------- Curvature + NA depth (state-dependent) ----------
    eps_cu = 0.003
    phi_u = eps_cu / max(c, 1e-9)

    # base utilisation
    base_r = Mu_star / phi_Mu_cap if phi_Mu_cap > 0 else 0.0
    base_r = float(max(0.0, min(1.0, base_r)))

    # scale by state (robust to extended labels like "ULS – Parabolic")
    state_low = (strain_state or "").lower()
    if state_low.startswith("uls"):
        r = base_r
    elif state_low.startswith("sls"):
        r = 0.6 * base_r
    else:  # "Uncracked" / anything else
        r = 0.0

    c0 = D / 2.0  # uncracked NA
    if r <= 0.0:
        phi = 0.0
        c_now = c0
    else:
        phi = r * phi_u
        c_now = (1.0 - r) * c0 + r * c

    # Note: phi and c_now are calculated but not stored in session_state here
    # (session_state modifications are done in the wrapper function)

    traces: list[go.BaseTraceType] = []

    # =======================================================
    #  Concrete prism
    # =======================================================
    vx = np.array([0, L, L, 0, 0, L, L, 0])
    vy = np.array([0, 0, b, b, 0, 0, b, b])
    vz = np.array([0, 0, 0, 0, D, D, D, D])
    tri_i = [0, 0, 0, 4, 4, 1, 5, 2, 6, 3, 7, 6]
    tri_j = [1, 2, 3, 5, 7, 5, 6, 6, 7, 7, 4, 2]
    tri_k = [2, 3, 0, 6, 4, 2, 7, 3, 4, 0, 5, 1]

    traces.append(
        go.Mesh3d(
            x=vx,
            y=vy,
            z=vz,
            i=tri_i,
            j=tri_j,
            k=tri_k,
            color="#cccccc",
            opacity=0.25,
            flatshading=True,
            hoverinfo="skip",
            showscale=False,
            name="Concrete",
        )
    )

    # =======================================================
    #  Longitudinal bars - use provided reo_layout
    # =======================================================
    lw_base = 0.4

    # Bottom bars - draw each layer separately
    # BOTTOM reinforcement is BLUE
    for layer_data in reo_layout["bottom"]:
        x_positions = layer_data["x"]
        y_pos = layer_data["y"]  # This is the y coordinate in 2D (section view)
        db = layer_data["db"]
        # Convert 2D y to 3D z (y in 2D section = z in 3D beam)
        z_pos = y_pos
        line_w = max(2.0, abs(db) * lw_base)
        for x_pos in x_positions:
            traces.append(
                go.Scatter3d(
                    x=[0, L],
                    y=[x_pos, x_pos],  # x in 2D section = y in 3D beam
                    z=[z_pos, z_pos],
                    mode="lines",
                    line=dict(width=line_w, color="blue"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    # Top bars - draw each layer separately
    # TOP reinforcement is RED
    for layer_data in reo_layout["top"]:
        x_positions = layer_data["x"]
        y_pos = layer_data["y"]  # This is the y coordinate in 2D (section view)
        db = layer_data["db"]
        # Convert 2D y to 3D z (y in 2D section = z in 3D beam)
        z_pos = y_pos
        line_w = max(2.0, abs(db) * lw_base)
        for x_pos in x_positions:
            traces.append(
                go.Scatter3d(
                    x=[0, L],
                    y=[x_pos, x_pos],  # x in 2D section = y in 3D beam
                    z=[z_pos, z_pos],
                    mode="lines",
                    line=dict(width=line_w, color="red"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    # =======================================================
    #  Stirrups – use same concrete covers as reo
    # =======================================================
    if lig_d > 0 and s_lig > 0 and lig_legs >= 2:
        s_eff = max(40.0, float(s_lig))
        n_hoops = int(max(1, min(80, round(L / s_eff))))
        xs = np.linspace(s_eff / 2.0, L - s_eff / 2.0, n_hoops)

        # stirrup centre lines based on side cover
        y_left = cover_side + 0.5 * lig_d
        y_right = b - cover_side - 0.5 * lig_d

        # vertical: centre lines based on top/bottom cover
        z_top_c = cover_top + 0.5 * lig_d
        z_bot_c = D - (cover_bot + 0.5 * lig_d)

        min_z = 5.0
        max_z = D - 5.0
        z_top_c = float(np.clip(z_top_c, min_z, max_z))
        z_bot_c = float(np.clip(z_bot_c, min_z, max_z))

        lw = max(1.5, abs(lig_d) * 0.35)

        for x0 in xs:
            Xs = [x0] * 5
            Ys = [y_left, y_right, y_right, y_left, y_left]
            Zs = [z_top_c, z_top_c, z_bot_c, z_bot_c, z_top_c]
            traces.append(
                go.Scatter3d(
                    x=Xs,
                    y=Ys,
                    z=Zs,
                    mode="lines",
                    line=dict(width=lw, color="black"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    # =======================================================
    #  Neutral axis plane
    # =======================================================
    Xg, Yg = np.meshgrid(np.linspace(0, L, 2), np.linspace(0, b, 2))
    Zg = np.full_like(Xg, c_now)
    traces.append(
        go.Surface(
            x=Xg,
            y=Yg,
            z=Zg,
            colorscale=[[0, "orange"], [1, "orange"]],
            showscale=False,
            opacity=0.55,
            name="NA",
        )
    )

    # =======================================================
    #  Layout
    # =======================================================
    fig = go.Figure(data=traces)
    fig.update_layout(
        scene=dict(
            xaxis_title="Length (mm)",
            yaxis_title="Width (mm)",
            zaxis_title="Depth from top (mm)",
            zaxis=dict(autorange="reversed"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.45, y=1.35, z=0.95)),
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        height=350,
        showlegend=False,
    )
    return fig


def _build_beam_3d_figure(b, D, L, Mu_star, phi_Mu_cap, c, strain_state: str = "ULS", layout=None):
    """
    Wrapper function that reads from session state and calls the cached pure function.
    
    Args:
        layout: Optional pre-computed section layout dict. If None, will compute from session state.
    """
    # Get all inputs from results (matches shear pattern)
    results = st.session_state.get("results", {})
    
    # --- ARCHITECTURE LOCK: bending diagrams must use results (with fallback to shared) ---
    # Note: Geometry values (b, D, d) are not in results - they're in shared state.
    # The guard ensures results dict exists and diagrams use the fallback pattern correctly.
    if st.session_state.get("_dev_mode", False):
        if "results" not in st.session_state:
            raise RuntimeError(
                "[ARCHITECTURE VIOLATION] Bending diagrams require results dict to exist. "
                "Call update_results() or run compute functions first."
            )
    
    # If layout is provided, extract reo_layout from it
    if layout is not None:
        reo_layout = layout.get("reo_layout")
        if reo_layout is None:
            # Fallback to computing from session state using results
            from section_layout import compute_longitudinal_reo_layout
            reo_layout = compute_longitudinal_reo_layout(
                b=results.get("b", b), D=results.get("D", D),
                cover_bot=results.get("cover_bot", 40.0), cover_top=results.get("cover_top", 40.0), cover_side=results.get("cover_side", 40.0),
                nb_or_s_bot_1=results.get("nb_or_s_bot_1", 4.0), db_bot_1=results.get("db_bot_1", 20.0),
                nb_or_s_bot_2=results.get("nb_or_s_bot_2", 0.0), db_bot_2=results.get("db_bot_2", 20.0),
                nb_or_s_top_1=results.get("nb_or_s_top_1", 2.0), db_top_1=results.get("db_top_1", 16.0),
                nb_or_s_top_2=results.get("nb_or_s_top_2", 0.0), db_top_2=results.get("db_top_2", 16.0),
                rowgap_bot=results.get("rowgap_bot", 60.0), rowgap_top=results.get("rowgap_top", 60.0),
            )
    else:
        # Compute from session state using results
        from section_layout import compute_longitudinal_reo_layout
        reo_layout = compute_longitudinal_reo_layout(
            b=results.get("b", b), D=results.get("D", D),
            cover_bot=results.get("cover_bot", 40.0), cover_top=results.get("cover_top", 40.0), cover_side=results.get("cover_side", 40.0),
            nb_or_s_bot_1=results.get("nb_or_s_bot_1", 4.0), db_bot_1=results.get("db_bot_1", 20.0),
            nb_or_s_bot_2=results.get("nb_or_s_bot_2", 0.0), db_bot_2=results.get("db_bot_2", 20.0),
            nb_or_s_top_1=results.get("nb_or_s_top_1", 2.0), db_top_1=results.get("db_top_1", 16.0),
            nb_or_s_top_2=results.get("nb_or_s_top_2", 0.0), db_top_2=results.get("db_top_2", 16.0),
            rowgap_bot=results.get("rowgap_bot", 60.0), rowgap_top=results.get("rowgap_top", 60.0),
        )
    
    # Get ligature spacing from results
    s_lig = results.get("s_lig", get_param("s_lig", 200.0))
    s_lig = float(s_lig) if s_lig is not None else 200.0
    
    # Cache-busting for debug mode
    debug_bust = None
    try:
        from src.debug.debug_flags import is_debug_enabled
        import hashlib
        import json
        if is_debug_enabled():
            # Create a signature from all dimension inputs
            dim_sig = {
                "b": results.get("b", b),
                "D": results.get("D", D),
                "L": results.get("L", L),
                "d": results.get("d", get_param("d", 560.0)),
                "cover_bot": results.get("cover_bot", 40.0),
                "cover_top": results.get("cover_top", 40.0),
                "cover_side": results.get("cover_side", 40.0),
            }
            debug_bust = hashlib.sha1(json.dumps(dim_sig, sort_keys=True).encode()).hexdigest()[:8]
    except ImportError:
        pass

    # Get cached or uncached version based on debug mode
    _build_fn = _get_build_beam_3d_figure_pure()
    return _build_fn(
        b, D, L, Mu_star, phi_Mu_cap, c, strain_state,
        reo_layout, results.get("cover_bot", 40.0), results.get("cover_top", 40.0),
        results.get("cover_side", 40.0), results.get("rowgap_bot", 60.0), results.get("rowgap_top", 60.0), 
        results.get("lig_d", 10.0), results.get("lig_legs", 2), s_lig, debug_bust=debug_bust
    )


def build_bending_report(top_results: dict, params: dict) -> dict:
    """
    Build the bending report structure (tabs + calc boxes) from computed values.
    
    This function replicates the calc box structure from render_uls_tab, 
    render_min_strength_tab, and render_sls_tab, but without UI rendering.
    
    Args:
        top_results: Dict from _compute_bending_capacity() with all calculated values
        params: Dict with inputs: b, D, fc, fsy, Ast, d, phi, Mu_star, Ec, Es, etc.
    
    Returns:
        dict with module_title, summary, and tabs structure
    """
    from reporting.report_content import make_calc_box, make_tab, make_module_report
    import math
    
    # Extract parameters
    b = params.get("b", 400.0)
    D = params.get("D", 600.0)
    fc = params.get("fc", 32.0)
    fsy = params.get("fsy", 500.0)
    Ast = params.get("Ast", 0.0)
    d = params.get("d", 560.0)
    phi = params.get("phi", 0.85)
    Mu_star = params.get("Mu_star_uls", params.get("Mu_star", 0.0))
    Mu_star_sls = params.get("Mu_star_sls", None)
    Ec = params.get("Ec", 30000.0)
    Es = params.get("Es", 200000.0)
    
    # Extract results
    phi_Mu_cap = top_results.get("phi_Mu_cap", 0.0)
    Mu_util = top_results.get("Mu_util", 0.0)
    
    # Build summary
    outcome = "PASS" if (Mu_util is not None and Mu_util <= 1.0) else "FAIL" if Mu_util is not None else "N/A"
    summary = [
        ("Demand", f"{Mu_star:.1f} kNm"),
        ("Capacity", f"{phi_Mu_cap:.1f} kNm"),
        ("Utilisation", f"{Mu_util:.2f}" if Mu_util is not None and not math.isnan(Mu_util) else "N/A"),
        ("Outcome", outcome),
    ]
    
    # ULS tab calculations (matching render_uls_tab logic)
    uls_boxes = []
    if phi_Mu_cap > 0 and d and Ast:
        # Stress-block factors
        alpha2_raw = 0.85 - 0.0015 * fc
        gamma_raw = 0.97 - 0.0025 * fc
        alpha2_uls = max(0.67, alpha2_raw)
        gamma_uls = max(0.67, gamma_raw)
        
        # Pre-compute ULS internal forces / geometry
        T = Ast * fsy  # N
        denom_uls = alpha2_uls * fc * b * gamma_uls
        dn = T / denom_uls if denom_uls > 0 else float("nan")
        a_uls = gamma_uls * dn
        z_uls = d - 0.5 * a_uls
        Mu_nom_uls = T * z_uls / 1e6
        phi_Mu_cap_uls = phi * Mu_nom_uls
        C_N = alpha2_uls * fc * b * a_uls  # N
        C_kN = C_N / 1000.0 if C_N is not None else float("nan")
        T_kN = T / 1000.0
        
        # 1.1 Stress-block parameters
        # Create diagram callable for box 1.1
        def diagram_1_1_fn():
            from bending_diagrams import _make_uls_stress_block_figure
            return _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=False,
                show_dn=False,
                show_alpha_label=True,
                show_C=False,
                C_N=None,
                variant="11",
            )
        
        uls_boxes.append(make_calc_box(
            "1.1",
            "Stress-block parameters (alpha2 and gamma)",
            "info",
            f"alpha2 = {alpha2_uls:.3f}, gamma = {gamma_uls:.3f}",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Stress block factor alpha2", "eq": "alpha2 = 0.85 - 0.0015*f'c (>= 0.67)", "sub": f"= 0.85 - 0.0015*{fc:.1f} = {alpha2_uls:.3f}"},
                {"label": "Stress block factor gamma", "eq": "gamma = 0.97 - 0.0025*f'c (>= 0.67)", "sub": f"= 0.97 - 0.0025*{fc:.1f} = {gamma_uls:.3f}"},
            ],
            diagram=diagram_1_1_fn,  # Store callable for later export
        ))
        
        # 1.2 Concrete compressive force C
        uls_boxes.append(make_calc_box(
            "1.2",
            "Concrete compressive force C",
            "info",
            f"C = {C_kN:.1f} kN",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Compression force", "eq": "C = alpha2*f'c*b*a/1000", "sub": f"= {alpha2_uls:.3f}*{fc:.1f}*{b:.0f}*{a_uls:.1f}/1000 = {C_kN:.1f} kN"},
            ],
        ))
        
        # 1.3 Steel area and tension force T
        uls_boxes.append(make_calc_box(
            "1.3",
            "Steel area and tension force T",
            "info",
            f"T = {T_kN:.1f} kN",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Tension force", "eq": "T = Ast*fsy/1000", "sub": f"= {Ast:.0f}*{fsy:.0f}/1000 = {T_kN:.1f} kN"},
            ],
        ))
        
        # 1.4 Neutral axis depth d_n and block depth a
        def diagram_1_4_fn():
            from bending_diagrams import _make_uls_stress_block_figure
            return _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=False,
                show_dn=True,
                show_alpha_label=False,
                show_C=True,
                C_N=C_N,
                variant="13",
            )
        
        uls_boxes.append(make_calc_box(
            "1.4",
            "Neutral axis depth d_n and block depth a",
            "info",
            f"d_n = {dn:.1f} mm, a = {a_uls:.1f} mm",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Equilibrium", "eq": "T = alpha2*f'c*b*gamma*c/1000", "sub": "Rearrange for c"},
                {"label": "Neutral axis", "eq": "c = T*1000/(alpha2*f'c*b*gamma)", "sub": f"= {T_kN:.1f}*1000/({alpha2_uls:.3f}*{fc:.1f}*{b:.0f}*{gamma_uls:.3f}) = {dn:.1f} mm"},
                {"label": "Block depth", "eq": "a = gamma*c", "sub": f"= {gamma_uls:.3f}*{dn:.1f} = {a_uls:.1f} mm"},
            ],
            diagram=diagram_1_4_fn,
        ))
        
        # 1.5 Neutral axis ratio k_u
        ku = dn / d if d else float("nan")
        ku_lim = 0.36
        ku_ok = (0.0 < ku <= ku_lim) if not math.isnan(ku) else None
        ku_status = "pass" if ku_ok is True else "fail" if ku_ok is False else "info"
        uls_boxes.append(make_calc_box(
            "1.5",
            "Neutral axis ratio k_u",
            ku_status,
            f"k_u = {ku:.3f} vs k_u,lim = {ku_lim:.2f} → {'PASS' if ku_ok else 'FAIL' if ku_ok is False else '—'}",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Ratio", "eq": "k_u = c/d", "sub": f"= {dn:.1f}/{d:.1f} = {ku:.3f}"},
            ],
        ))
        
        # 1.6 Lever arm z and moment capacity
        def diagram_1_6_fn():
            from bending_diagrams import _make_uls_force_model_figure
            from reporting.fig_export import call_with_supported_kwargs
            # Use signature-safe call - function expects D_mm, d_mm, a_mm, C_N, T_N
            return call_with_supported_kwargs(
                _make_uls_force_model_figure,
                D_mm=D or 0.0,
                d_mm=d,
                a_mm=a_uls,
                C_N=C_N,
                T_N=T,
                # Also pass aliases in case function accepts different names
                b_mm=b or 0.0,
                b=b or 0.0,
                dn_mm=dn,
                z_mm=z_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
            )
        
        uls_boxes.append(make_calc_box(
            "1.6",
            "Lever arm z and moment capacity",
            "info",
            f"phiM_u,cap = {phi_Mu_cap_uls:.2f} kNm",
            "AS 3600:2018 Cl. 8.1.3, 2.2",
            [
                {"label": "Lever arm", "eq": "z = d - a/2", "sub": f"= {d:.1f} - {a_uls:.1f}/2 = {z_uls:.1f} mm"},
                {"label": "Nominal", "eq": "M_u = T*z/1000/1000", "sub": f"= {T_kN:.1f}*{z_uls:.1f}/1000 = {Mu_nom_uls:.2f} kNm"},
                {"label": "Design", "eq": "phiM_u = phi*M_u", "sub": f"= {phi:.2f}*{Mu_nom_uls:.2f} = {phi_Mu_cap_uls:.2f} kNm"},
            ],
            diagram=diagram_1_6_fn,
        ))
        
        # 1.7 Flexural capacity check
        Mu_ok = Mu_star <= phi_Mu_cap_uls if (Mu_star is not None and phi_Mu_cap_uls > 0) else None
        Mu_status = "pass" if Mu_ok is True else "fail" if Mu_ok is False else "info"
        Mu_util_val = Mu_star / phi_Mu_cap_uls if phi_Mu_cap_uls > 0 else float("nan")
        uls_boxes.append(make_calc_box(
            "1.7",
            "Flexural capacity check",
            Mu_status,
            f"M_u* = {Mu_star:.2f} kNm vs phiM_u,cap = {phi_Mu_cap_uls:.2f} kNm → {'PASS' if Mu_ok else 'FAIL' if Mu_ok is False else 'N/A'}",
            "AS 3600:2018 Cl. 2.2",
            [
                {"label": "Utilisation", "eq": "Util = M_u*/phiM_u,cap", "sub": f"= {Mu_star:.2f}/{phi_Mu_cap_uls:.2f} = {Mu_util_val:.2f}"},
            ],
        ))
    
    # Minimum strength tab (matching render_min_strength_tab logic)
    min_boxes = []
    if phi_Mu_cap > 0:
        fctf = top_results.get("fctf", 0.0)
        Z_gross = top_results.get("Z_gross", 0.0)
        Mcr = top_results.get("Mcr", 0.0)
        As_min = top_results.get("As_min", 0.0)
        
        fctf_as = fctf
        Zg = Z_gross
        Mcr_as = Mcr
        Mu_min_as = 1.2 * Mcr_as if (Mcr_as is not None and not math.isnan(Mcr_as)) else float("nan")
        Ast_min_as = As_min
        
        # 2.1 f_ct,f
        min_boxes.append(make_calc_box(
            "2.1",
            "Concrete flexural tensile strength f_ct,f",
            "info",
            f"f_ct,f = {fctf_as:.3f} MPa",
            "AS 3600:2018 (simplified)",
            [
                {"label": "Tensile strength", "eq": "f_ct,f = 0.6*sqrt(f'c)", "sub": f"= 0.6*sqrt({fc:.1f}) = {fctf_as:.3f} MPa"},
            ],
        ))
        
        # 2.2 Z_g
        min_boxes.append(make_calc_box(
            "2.2",
            "Gross section modulus Z_g",
            "info",
            f"Z_g = {Zg:.3e} mm³",
            "AS 3600:2018",
            [
                {"label": "Section modulus", "eq": "Z_g = b*D^2/6", "sub": f"= {b:.0f}*{D:.0f}^2/6 = {Zg:.3e} mm³"},
            ],
        ))
        
        # 2.3 M_cr
        min_boxes.append(make_calc_box(
            "2.3",
            "Cracking moment M_cr",
            "info",
            f"M_cr = {Mcr_as:.2f} kNm",
            "AS 3600:2018",
            [
                {"label": "Cracking moment", "eq": "M_cr = f_ct,f*Z_g/10^6", "sub": f"= {fctf_as:.3f}*{Zg:.3e}/10^6 = {Mcr_as:.2f} kNm"},
            ],
        ))
        
        # 2.4 Minimum required capacity
        Mu_min_ok = phi_Mu_cap >= Mu_min_as if (phi_Mu_cap > 0 and Mu_min_as > 0) else None
        Mu_min_status = "pass" if Mu_min_ok is True else "fail" if Mu_min_ok is False else "info"
        min_boxes.append(make_calc_box(
            "2.4",
            "Minimum required design capacity (M_u,cap)_min",
            Mu_min_status,
            f"phiM_u,cap = {phi_Mu_cap:.2f} kNm vs (M_u,cap)_min = {Mu_min_as:.2f} kNm → {'PASS' if Mu_min_ok else 'FAIL' if Mu_min_ok is False else 'N/A'}",
            "AS 3600:2018 (teaching)",
            [
                {"label": "Minimum capacity", "eq": "(M_u,cap)_min = 1.2*M_cr", "sub": f"= 1.2*{Mcr_as:.2f} = {Mu_min_as:.2f} kNm"},
            ],
        ))
        
        # 2.5 Minimum tensile reinforcement
        As_ok = Ast >= Ast_min_as if (Ast is not None and Ast_min_as is not None and not math.isnan(Ast_min_as)) else None
        As_status = "pass" if As_ok is True else "fail" if As_ok is False else "info"
        min_boxes.append(make_calc_box(
            "2.5",
            "Minimum tensile reinforcement A_st,min",
            As_status,
            f"A_st = {Ast:.1f} mm² vs A_st,min = {Ast_min_as:.1f} mm² → {'PASS' if As_ok else 'FAIL' if As_ok is False else 'N/A'}",
            "AS 3600:2018 (simplified)",
            [
                {"label": "Minimum steel", "eq": "A_st,min = 0.4*(f_ct,f/f_sy)*b*d", "sub": f"= 0.4*({fctf_as:.3f}/{fsy:.0f})*{b:.0f}*{d:.0f} = {Ast_min_as:.1f} mm²"},
            ],
        ))
    
    # SLS tab - read from session_state if available (computed by render_sls_tab)
    sls_boxes = []
    Ms = params.get("Mu_star_sls", Mu_star)  # service moment (kNm)
    if Mu_star_sls is not None:
        try:
            debug_print(f"[BENDING_REPORT_ACTIONS] uls_M={Mu_star} sls_M={Mu_star_sls}")
        except Exception:
            pass
    
    # Try to read SLS values from session_state (if SLS tab has been run)
    try:
        dn_sls = st.session_state.get("bending_sls_dn", None)
        kappa_sls = st.session_state.get("bending_sls_kappa", None)
        eps_top_sls = st.session_state.get("bending_sls_eps_top", None)
        fs_outer = st.session_state.get("bending_sls_fs_outer", None)
    except Exception:
        dn_sls = None
        kappa_sls = None
        eps_top_sls = None
        fs_outer = None
    
    if dn_sls is not None and kappa_sls is not None and Ec > 0 and Es > 0 and b > 0 and Ast > 0 and d > 0:
        # SLS values are available - build calc boxes
        n_sls = Es / Ec if Ec > 0 else 0.0
        
        # 3.1 Modular ratio
        sls_boxes.append(make_calc_box(
            "3.1",
            "Modular ratio n = E_s / E_c",
            "info",
            f"n = {n_sls:.2f}",
            "AS 3600:2018 SLS",
            [
                {"label": "Modular ratio", "eq": "n = E_s / E_c", "sub": f"= {Es:.0f} / {Ec:.0f} = {n_sls:.2f}"},
            ],
        ))
        
        # 3.2 Neutral axis depth d_n
        def diagram_3_2_fn():
            from bending_diagrams import _make_sls_stress_block_figure
            from reporting.fig_export import call_with_supported_kwargs
            # Get bar layout info for diagram
            nb_top = st.session_state.get("nb_top", 0) or 0
            db_top = st.session_state.get("db_top", 0.0) or 0.0
            cover_top = st.session_state.get("cover_top", 0.0) or 0.0
            include_comp = (nb_top > 0)
            d_comp = cover_top + db_top/2.0 if (nb_top > 0 and db_top > 0) else None
            # Use signature-safe call
            return call_with_supported_kwargs(
                _make_sls_stress_block_figure,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn_sls,
                include_comp=include_comp,
                d_comp_mm=d_comp,
                # Also pass aliases
                D=D or 0.0,
                d=d,
                dn=dn_sls,
            )
        
        sls_boxes.append(make_calc_box(
            "3.2",
            "Neutral axis depth d_n (cracked section)",
            "info",
            f"d_n = {dn_sls:.1f} mm",
            "AS 3600:2018 SLS",
            [
                {"label": "Cracked section", "eq": "Equilibrium: C = T (transformed areas)", "sub": "Solved numerically"},
                {"label": "Result", "eq": "d_n", "sub": f"= {dn_sls:.1f} mm"},
            ],
            diagram=diagram_3_2_fn,
        ))
        
        # 3.3 Cracked moment of inertia I_cr
        # Compute Icr from kappa (since kappa = Ms/(Ec*Icr), we have Icr = Ms/(Ec*kappa))
        # This gives us the actual Icr used in the SLS tab (which includes full bar layout)
        Ms_Nmm = Ms * 1e6
        Icr = Ms_Nmm / (Ec * kappa_sls) if (Ec > 0 and kappa_sls != 0) else 0.0
        
        sls_boxes.append(make_calc_box(
            "3.3",
            "Cracked moment of inertia I_cr",
            "info",
            f"I_cr = {Icr:,.2f} mm⁴",
            "AS 3600:2018 SLS",
            [
                {"label": "Formula", "eq": "I_cr = b*d_n^3/3 + Σ(n*A_s*(d_i - d_n)^2)", "sub": "Includes all steel layers"},
                {"label": "Result", "eq": "I_cr", "sub": f"= {Icr:,.2f} mm⁴"},
            ],
        ))
        
        # 3.4 Curvature
        sls_boxes.append(make_calc_box(
            "3.4",
            "Curvature at service moment",
            "info",
            f"κ = {kappa_sls:.3e} mm⁻¹",
            "AS 3600:2018 SLS",
            [
                {"label": "Curvature", "eq": "κ = M_s / (E_c * I_cr)", "sub": f"= {Ms:.2f}*10^6 / ({Ec:.0f} * {Icr:,.2f}) = {kappa_sls:.3e} mm⁻¹"},
            ],
        ))
        
        # 3.5 Strain distribution (top fibre)
        if eps_top_sls is not None:
            sls_boxes.append(make_calc_box(
                "3.5",
                "Strain distribution ε(y) = κ(y − d_n)",
                "info",
                f"ε_top = {eps_top_sls:.5f}",
                "AS 3600:2018 SLS",
                [
                    {"label": "Top fibre strain", "eq": "ε_top = κ*(0 - d_n)", "sub": f"= {kappa_sls:.3e}*({-dn_sls:.1f}) = {eps_top_sls:.5f}"},
                ],
            ))
        else:
            eps_top_computed = kappa_sls * (0.0 - dn_sls)
            sls_boxes.append(make_calc_box(
                "3.5",
                "Strain distribution ε(y) = κ(y − d_n)",
                "info",
                f"ε_top = {eps_top_computed:.5f}",
                "AS 3600:2018 SLS",
                [
                    {"label": "Top fibre strain", "eq": "ε_top = κ*(0 - d_n)", "sub": f"= {kappa_sls:.3e}*({-dn_sls:.1f}) = {eps_top_computed:.5f}"},
                ],
            ))
        
        # 3.6 Steel stresses (outermost tension layer if available)
        if fs_outer is not None:
            sls_boxes.append(make_calc_box(
                "3.6",
                "Steel stresses at SLS",
                "info",
                f"f_s,outer = {fs_outer:.1f} MPa",
                "AS 3600:2018 SLS",
                [
                    {"label": "Outermost tension layer", "eq": "f_s = E_s * ε_s", "sub": f"= {fs_outer:.1f} MPa"},
                ],
            ))
        else:
            # Compute from curvature and depth
            eps_s_computed = kappa_sls * (d - dn_sls)
            fs_computed = Es * eps_s_computed
            sls_boxes.append(make_calc_box(
                "3.6",
                "Steel stresses at SLS",
                "info",
                f"f_s ≈ {fs_computed:.1f} MPa",
                "AS 3600:2018 SLS",
                [
                    {"label": "Steel strain", "eq": "ε_s = κ*(d - d_n)", "sub": f"= {kappa_sls:.3e}*({d:.1f} - {dn_sls:.1f}) = {eps_s_computed:.5f}"},
                    {"label": "Steel stress", "eq": "f_s = E_s * ε_s", "sub": f"= {Es:.0f} * {eps_s_computed:.5f} = {fs_computed:.1f} MPa"},
                ],
            ))
    else:
        # SLS values not available - show warning box
        sls_boxes.append(make_calc_box(
            "SLS",
            "SLS checks not available",
            "warn",
            "Run SLS checks (or Run all checks) before exporting.",
            "",
            [
                {"label": "Note", "eq": "", "sub": "SLS cracked-section analysis requires running the SLS tab in the app."},
            ],
        ))
    
    # Build tabs
    tabs = [
        make_tab("ULS Checks", uls_boxes),
        make_tab("SLS Checks", sls_boxes),
        make_tab("Minimum strength checks", min_boxes),
    ]
    
    # Build module report
    report = make_module_report("Bending (ULS)", tabs)
    report["summary"] = summary  # Add summary to report
    return report


def _compute_sls_bending_values():
    """
    Compute SLS bending values (cracked section analysis) without UI rendering.
    This replicates the logic from render_sls_tab() but without Streamlit UI calls.
    
    Stores results in st.session_state under keys:
    - bending_sls_dn: neutral axis depth (mm)
    - bending_sls_kappa: curvature (mm^-1)
    - bending_sls_eps_top: top fibre strain
    - bending_sls_fs_outer: outermost tension layer stress (MPa)
    - bending_sls_y_tension_outer: depth to outermost tension layer (mm)
    - bending_sls_eps_s_outer: strain in outermost tension layer
    
    Returns:
        fs_outer: Outermost tension layer stress (MPa), or None if not computed
    """
    import streamlit as st
    import math
    from state_and_helpers import get_param
    
    # Pull shared values for calculations (matches shear pattern)
    inputs = _get_bending_inputs_from_shared_state()
    b = inputs["b"]
    D = inputs["D"]
    d = inputs["d"]
    Ast = inputs["Ast_bot"]
    Ec = inputs["Ec"]
    Es = inputs["Es"]
    Mu_star = inputs["Mu_star_sls"]
    
    # Bar layout
    nb_bot = inputs["nb_bot"]
    db_bot = inputs["db_bot"]
    cover_bot = inputs["cover_bot"]
    rowgap_bot = inputs["rowgap_bot"]
    
    nb_top = get_param("nb_top")
    db_top = get_param("db_top")
    cover_top = get_param("cover_top")
    
    if not (d and Ast and Ec and Es and b and D and Mu_star is not None):
        return None  # Not enough info
    
    Ms = Mu_star  # service moment (kNm)
    
    # Build steel layers (simplified - single layer for now)
    layers_tension = []
    if nb_bot > 0 and db_bot > 0 and cover_bot > 0:
        As_bar_bot = math.pi * db_bot**2 / 4.0
        r_bot = db_bot / 2.0
        y_row0 = D - cover_bot - r_bot
        # For simplicity, use single equivalent layer
        layers_tension.append({
            "name": "T1",
            "label": "Bottom tension steel",
            "y": d,
            "As": Ast,
        })
    else:
        layers_tension.append({
            "name": "T1",
            "label": "Bottom tension steel",
            "y": d,
            "As": Ast,
        })
    
    # Compression layer (if present)
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
    
    # Modular ratio
    n = Es / Ec if Ec > 0 else 0.0
    
    # Solve for neutral axis depth (simplified - use transformed area method)
    # For single tension layer: n*As*(d - dn) = b*dn^2/2
    # Rearranging: b*dn^2/2 + n*As*dn - n*As*d = 0
    # Using quadratic formula
    nAs = n * Ast
    if nAs > 0 and b > 0:
        # Quadratic: (b/2)*dn^2 + nAs*dn - nAs*d = 0
        a_coeff = b / 2.0
        b_coeff = nAs
        c_coeff = -nAs * d
        
        discriminant = b_coeff**2 - 4 * a_coeff * c_coeff
        if discriminant >= 0:
            dn_sls = (-b_coeff + math.sqrt(discriminant)) / (2 * a_coeff)
            dn_sls = max(1.0, min(dn_sls, D))  # Clamp
        else:
            dn_sls = d / 2.0  # Fallback
    else:
        dn_sls = d / 2.0  # Fallback
    
    # Cracked moment of inertia (simplified)
    Icr = (b * dn_sls**3 / 3.0) + nAs * (d - dn_sls)**2
    
    # Curvature
    Ms_Nmm = Ms * 1e6
    kappa = Ms_Nmm / (Ec * Icr) if (Ec > 0 and Icr > 0) else 0.0
    
    # Top fibre strain
    eps_top = kappa * (0.0 - dn_sls)
    
    # Outermost tension layer stress
    deepest = max(layers_tension, key=lambda l: l["y"], default=None)
    fs_outer = None
    eps_s_outer = None
    y_outer = None
    
    if deepest:
        y_outer = deepest["y"]
        eps_s_outer = kappa * (y_outer - dn_sls)
        fs_outer = Es * eps_s_outer
    
    # Store in session state
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
        
        # Publish for other pages (crack/deflection)
        if fs_outer is not None:
            from state_and_helpers import update_results
            update_results(sigma_s_sls=float(fs_outer), bending_sls_fs_outer=float(fs_outer))
        return fs_outer
    except Exception:
        pass
    return None


def compute_bending_results(publish: bool = True) -> dict:
    """
    Compute bending results without UI rendering.
    Includes ULS, SLS, and minimum strength checks.
    
    Args:
        publish: If True, update results via update_results(). Always True for now.
    
    Returns:
        dict with computed results
    """
    import streamlit as st
    from state_and_helpers import recalc_derived_values, get_param
    recalc_derived_values()
    
    # Call existing compute function (which already calls update_results)
    results = _compute_bending_capacity()
    
    # Compute SLS values (ensures they're available for report building)
    _compute_sls_bending_values()
    
    # Pull shared values for calculations (matches shear pattern)
    inputs = _get_bending_inputs_from_shared_state()
    params = {
        "b": inputs["b"],
        "D": inputs["D"],
        "fc": inputs["fc"],
        "fsy": inputs["fsy"],
        "Ast": inputs["Ast_bot"],
        "d": inputs["d"],
        "phi": inputs["phi"],
        "Mu_star_uls": inputs["Mu_star_uls"],
        "Mu_star_sls": inputs["Mu_star_sls"],
        "Ec": inputs["Ec"],
        "Es": inputs["Es"],
    }
    
    # Build and store report
    report = build_bending_report(results, params)
    
    # Store report in results dict
    if "results" not in st.session_state:
        st.session_state["results"] = {}
    st.session_state["results"]["bending_report"] = report
    
    return {
        "phi_Mu_cap": results.get("phi_Mu_cap", 0.0),
        "Mu_utilisation": results.get("Mu_util", 0.0),
    }


def _get_bending_inputs_from_shared_state():
    """
    Read all bending inputs from shared canonical keys only.
    Matches shear's pattern: reads directly from shared state, no defaults, no fallbacks.
    """
    from state_and_helpers import get_param
    
    return {
        "b": get_param("b"),
        "D": get_param("D"),
        "L": get_param("L"),
        "d": get_param("d"),
        "cover_bot": get_param("cover_bot"),
        "cover_top": get_param("cover_top"),
        "cover_side": get_param("cover_side"),
        "fc": get_param("fc"),
        "fsy": get_param("fsy"),
        "Ec": get_param("Ec"),
        "Es": get_param("Es"),
        "phi": get_param("phi_bend"),
        "Mu_star_uls": get_param("Mu_star"),
        "Mu_star_sls": get_param("sls_Mstar"),
        "Ast_bot": get_param("Ast_bot"),
        "nb_or_s_bot_1": get_param("nb_or_s_bot_1"),
        "db_bot_1": get_param("db_bot_1"),
        "nb_or_s_bot_2": get_param("nb_or_s_bot_2"),
        "db_bot_2": get_param("db_bot_2"),
        "nb_or_s_top_1": get_param("nb_or_s_top_1"),
        "db_top_1": get_param("db_top_1"),
        "nb_or_s_top_2": get_param("nb_or_s_top_2"),
        "db_top_2": get_param("db_top_2"),
        "rowgap_bot": get_param("rowgap_bot"),
        "rowgap_top": get_param("rowgap_top"),
        "lig_legs": get_param("lig_legs"),
        "lig_d": get_param("lig_d"),
        "s_lig": get_param("s_lig"),
        "nb_bot": get_param("nb_bot"),
        "db_bot": get_param("db_bot"),
        "nb_top": get_param("nb_top"),
        "db_top": get_param("db_top"),
    }


def make_bending_sig_from_shared_state() -> dict:
    """
    Build a complete signature dict from shared state for cache keys.
    Includes all inputs that affect bending calculations and diagrams.
    """
    return _get_bending_inputs_from_shared_state()


def get_bending_inputs_from_shared_state():
    """
    Read all bending inputs from shared canonical keys only.
    Returns a dict with all dimensions and material properties.
    Treats 0 as valid - only uses defaults if value is None.
    """
    return make_bending_sig_from_shared_state()


def render_bending():
    # NOTE: init_shared_session_state() is called by app.py router before this function runs.
    # Pages must NOT call init/hydrate themselves - the router owns the lifecycle.
    
    from state_and_helpers import _write_sync_trace_line
    _write_sync_trace_line("\n=== PAGE RENDER: bending ===")
    
    # Handle cross-page navigation from Inputs page
    from jump_nav import get_jump_uid
    get_jump_uid()
    
    sync_callbacks = get_sync_callbacks()
    apply_global_widget_css()
    apply_calcbox_css()
    
    # Inject seamless steps CSS (for summary table + calc details)
    inject_seamless_steps_css()
    
    # Initialize page-local active mode state (UI-only, not in shared state)
    if "bending_active_mode" not in st.session_state:
        st.session_state["bending_active_mode"] = "ULS"
    
    # Debug-only dimension triage panel
    if DEBUG_MODE:
        try:
            from src.debug.debug_flags import is_debug_enabled
            if is_debug_enabled():
                with st.expander("🔧 DEBUG: Dimension Triage", expanded=False):
                    st.markdown("### Shared Canonical Keys")
                    shared_dims = {
                        "b": st.session_state.get("b"),
                        "D": st.session_state.get("D"),
                        "L": st.session_state.get("L"),
                        "d": st.session_state.get("d"),
                        "cover_bot": st.session_state.get("cover_bot"),
                        "cover_top": st.session_state.get("cover_top"),
                        "cover_side": st.session_state.get("cover_side"),
                    }
                    st.json(shared_dims)
                    
                    st.markdown("### Widget Keys (if available)")
                    widget_dims = {}
                    from state_and_helpers import TAB_KEYS
                    for widget_key in ["bending_b", "bending_D", "bending_L", "inputs_b", "inputs_D", "inputs_L"]:
                        if widget_key in st.session_state:
                            shared_key = TAB_KEYS.get(widget_key, "N/A")
                            widget_dims[f"{widget_key} → {shared_key}"] = st.session_state[widget_key]
                    if widget_dims:
                        st.json(widget_dims)
                    else:
                        st.write("No widget keys found")
                    
                    st.markdown("### Values Passed to Bending Core")
                    inputs = get_bending_inputs_from_shared_state()
                    st.json({
                        "b": inputs["b"],
                        "D": inputs["D"],
                        "L": inputs["L"],
                        "d": inputs["d"],
                        "cover_bot": inputs["cover_bot"],
                        "cover_top": inputs["cover_top"],
                        "cover_side": inputs["cover_side"],
                    })
                    
                    st.markdown("### Key Audit (dimension-like keys)")
                    dim_like_keys = {}
                    for key in sorted(st.session_state.keys()):
                        if any(term in key.lower() for term in ["b", "width", "d", "depth", "h", "cover", "dimension"]):
                            dim_like_keys[key] = st.session_state[key]
                    if dim_like_keys:
                        st.json(dim_like_keys)
        except ImportError:
            pass
    
    # Remove green background from inline math (Streamlit wraps math in code tags)
    # But preserve katex rendering by only targeting background, not font styling
    st.markdown(
        """
<style>
/* Remove green background from code elements in markdown paragraphs (these contain math) */
/* But don't override font-family so katex can render properly */
.stMarkdown p code {
    background-color: transparent !important;
    border: none !important;
    padding: 0 !important;
}
/* Ensure katex elements render properly */
.stMarkdown p code .katex,
.stMarkdown p .katex {
    font-family: KaTeX_Main, "Times New Roman", serif !important;
}
</style>
""",
        unsafe_allow_html=True,
    )
    
    # Debug helpers (temporary - remove after verification)
    if DEBUG_MODE:
        with st.sidebar:
            st.write("**Debug:**")
            st.write("jump_to:", st.session_state.get("jump_to"))
            open_steps = {k: v for k, v in st.session_state.items() if k.startswith("step_open_") and v}
            if open_steps:
                st.write("open steps:", open_steps)

    # Container so title + summary + 3D sit at the very top (like Inputs page)
    top_container = st.container()

    # ---------------- Sidebar glossary ----------------
    with st.sidebar.expander("📘 Glossary – Bending terms", expanded=False):
        st.markdown(
            """
            **Mu*** – Factored design bending moment at the critical section (kNm).  
            **b** – Beam/web width (mm).  
            **D** – Overall section depth (mm).  
            **d** – Effective depth to **centroid of tension steel** (mm).  
            **Ast,bot** – Area of bottom (tension) reinforcement (mm²).  
            **As_min** – Minimum required tensile steel for ductile behaviour.  
            **f'c** – Concrete cylinder strength (MPa).  
            **fsy** – Steel yield strength (MPa).  
            **Ec, Es** – Elastic moduli of concrete and steel (MPa).  

            **c** – Neutral axis depth from the top fibre (mm).  
            **a = γc** – Equivalent rectangular stress block depth (mm).  
            **kᵤ = c/d** – Neutral axis depth ratio (ductility indicator).  
            **α₂, γ** – AS 3600-style stress block factors.  
            **ϕ** – Strength reduction factor for bending.  

            **M_cr** – Cracking moment (kNm) based on f_ct,f and gross section.  
            **M_u** – Nominal flexural capacity (kNm).  
            **ϕM_u,cap** – Design flexural capacity (kNm).  
            **Utilisation** – M_u* / ϕM_u,cap → should be ≤ 1.0.  
            """
        )

    # Sync ULS load to Mu_star (contract-compliant via update_results)
    Mu_star_uls_val = get_param("uls_Mstar")
    if Mu_star_uls_val is not None:
        update_results(Mu_star=float(Mu_star_uls_val), Mu_star_kNm=float(Mu_star_uls_val))

    # ---------------- Top result summary (+ shared 3D NA view data) ----------------
    top_results = _compute_bending_capacity()
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")
    Mu_star_sls = get_param("sls_Mstar", Mu_star)
    
    # Compute SLS values BEFORE building summary (ensures sigma_s_sls is published)
    fs_outer_sls = _compute_sls_bending_values()

    phi_Mu_cap_top = top_results["phi_Mu_cap"]
    
    # ============================================================
    # COMPUTE CACHED LAYOUT ONCE - reuse for all diagrams
    # ============================================================
    from section_layout import compute_section_layout_cached
    
    # Get all inputs from results (matches shear pattern)
    results = st.session_state.get("results", {})
    
    # --- ARCHITECTURE LOCK: bending diagrams must use results (with fallback to shared) ---
    # Note: Geometry values (b, D, d) are not in results - they're in shared state.
    # The guard ensures results dict exists and diagrams use the fallback pattern correctly.
    if st.session_state.get("_dev_mode", False):
        if "results" not in st.session_state:
            raise RuntimeError(
                "[ARCHITECTURE VIOLATION] Bending diagrams require results dict to exist. "
                "Call update_results() or run compute functions first."
            )
    
    # Filter signature to only include parameters that compute_section_layout_cached accepts
    layout_sig = {
        "b": results.get("b", get_param("b", 400.0)),
        "D": results.get("D", get_param("D", 600.0)),
        "cover_bot": results.get("cover_bot", get_param("cover_bot", 40.0)),
        "cover_top": results.get("cover_top", get_param("cover_top", 40.0)),
        "cover_side": results.get("cover_side", get_param("cover_side", 40.0)),
        "nb_or_s_bot_1": results.get("nb_or_s_bot_1", get_param("nb_or_s_bot_1", 4.0)),
        "db_bot_1": results.get("db_bot_1", get_param("db_bot_1", 20.0)),
        "nb_or_s_bot_2": results.get("nb_or_s_bot_2", get_param("nb_or_s_bot_2", 0.0)),
        "db_bot_2": results.get("db_bot_2", get_param("db_bot_2", 20.0)),
        "nb_or_s_top_1": results.get("nb_or_s_top_1", get_param("nb_or_s_top_1", 2.0)),
        "db_top_1": results.get("db_top_1", get_param("db_top_1", 16.0)),
        "nb_or_s_top_2": results.get("nb_or_s_top_2", get_param("nb_or_s_top_2", 0.0)),
        "db_top_2": results.get("db_top_2", get_param("db_top_2", 16.0)),
        "rowgap_bot": results.get("rowgap_bot", get_param("rowgap_bot", 60.0)),
        "rowgap_top": results.get("rowgap_top", get_param("rowgap_top", 60.0)),
        "lig_legs": results.get("lig_legs", get_param("lig_legs", 2)),
        "lig_d": results.get("lig_d", get_param("lig_d", 10.0)),
    }
    
    # Compute cached layout once using filtered signature
    from section_layout import compute_section_layout_cached
    cached_layout = compute_section_layout_cached(**layout_sig)
    Mu_util_top = top_results["Mu_util"]
    ku_top = top_results["ku"]
    As_min_top = top_results["As_min"]
    c_top = top_results["c"]
    Mcr_top = top_results["Mcr"]
    # Minimum-strength design moment from Tab 2 logic: M_u,min = 1.2 M_cr
    if Mcr_top is not None and not (
        isinstance(Mcr_top, float) and math.isnan(Mcr_top)
    ):
        Mu_min_top = 1.2 * Mcr_top
    else:
        Mu_min_top = float("nan")

    def _status_colour(flag):
        if flag is None:
            return "Not calculated", "#e0e0e0"
        return ("OK", "#d5f5d5") if flag else ("Check", "#f8d0d0")

    # checks for summary card
    As_ok = None
    if Ast is not None and As_min_top and not math.isnan(As_min_top):
        As_ok = Ast >= As_min_top

    # Flexural check: Mu* ≤ ϕMu,cap
    Mu_ok = None
    if phi_Mu_cap_top and phi_Mu_cap_top > 0 and Mu_star is not None:
        Mu_ok = Mu_star <= phi_Mu_cap_top

    # Minimum strength requirement: ϕMu,cap ≥ Mu,min
    Mu_min_ok = None
    Mu_min_util = None
    if (
        phi_Mu_cap_top
        and phi_Mu_cap_top > 0
        and Mu_min_top is not None
        and not (isinstance(Mu_min_top, float) and math.isnan(Mu_min_top))
        and Mu_min_top > 0
    ):
        Mu_min_ok = phi_Mu_cap_top >= Mu_min_top
        Mu_min_util = Mu_min_top / phi_Mu_cap_top

    As_status, As_colour = _status_colour(As_ok)
    Mu_status, Mu_colour = _status_colour(Mu_ok)
    Mu_min_status, Mu_min_colour = _status_colour(Mu_min_ok)
    # ku_ok is defined later and used directly in the summary row (not via _status_colour)

    Ast_str = f"{Ast:.1f} mm²" if Ast not in (None, float("nan")) else "—"
    As_min_str = (
        f"{As_min_top:.1f} mm²" if As_min_top and not math.isnan(As_min_top) else "—"
    )
    phiMu_str = (
        f"{phi_Mu_cap_top:.2f} kNm"
        if phi_Mu_cap_top and phi_Mu_cap_top > 0
        else "—"
    )
    Mu_star_str = f"{Mu_star:.2f} kNm" if Mu_star not in (None, float("nan")) else "—"
    Mu_util_str = (
        f"{Mu_util_top:.3f}" if phi_Mu_cap_top and phi_Mu_cap_top > 0 else "—"
    )

    Mu_min_str = (
        f"{Mu_min_top:.2f} kNm"
        if Mu_min_top is not None
        and not (isinstance(Mu_min_top, float) and math.isnan(Mu_min_top))
        else "—"
    )
    Mu_min_util_str = f"{Mu_min_util:.3f}" if Mu_min_util is not None else "—"

    # kᵤ utilisation and status (for summary table)
    ku_lim = 0.36
    ku_val = ku_top if (ku_top is not None and not math.isnan(ku_top)) else None
    ku_ok = (ku_val is not None) and (ku_val <= ku_lim)
    
    c_str = (
        f"{c_top:.2f} mm" if c_top is not None and not math.isnan(c_top) else "—"
    )
    a_str = (
        f"{(top_results['a'] or float('nan')):.2f} mm"
        if "a" in top_results and not math.isnan(top_results["a"])
        else "—"
    )

    # SLS steel stress for summary (use local variable from computation, not session_state)
    def _as_float_or_nan(v):
        try:
            if v is None:
                return float("nan")
            return float(v)
        except Exception:
            return float("nan")

    fs_val = _as_float_or_nan(fs_outer_sls)
    
    # Fallback to session_state if local computation didn't produce a value
    if (math.isnan(fs_val)) or (abs(fs_val) < 1e-9):
        fs_ser = st.session_state.get("sigma_s_sls", None)
        fs_fallback = st.session_state.get("bending_sls_fs_outer", None)
        fs_val = _as_float_or_nan(fs_ser)
        if (math.isnan(fs_val)) or (abs(fs_val) < 1e-9):
            fs_val = _as_float_or_nan(fs_fallback)

    fs_ser_str = "—" if math.isnan(fs_val) else f"{fs_val:.1f} MPa"

    # Canonical bending state shared by 3D & bottom radios (ULS / SLS / Uncracked)
    state_options = ["ULS", "SLS (cracked)", "Uncracked"]
    canonical_state = st.session_state.get("bending_state", "ULS")
    if canonical_state not in state_options:
        canonical_state = "ULS"

    # Summary rows in deflection-style format
    rows_summary = [
        {
            "Check": "Steel area Ast,bot",
            "Value": Ast_str,
            "Limit": f"As,min = {As_min_str}",
            "Utilisation": "—",
            "Status": As_status,
        },
        {
            "Check": "Flexural capacity",
            "Value": f"ϕM\u2093,cap = {phiMu_str}",
            "Limit": f"M\u2093* = {Mu_star_str}",
            "Utilisation": Mu_util_str,
            "Status": Mu_status,
        },
        {
            "Check": "Minimum strength",
            "Value": f"ϕM\u2093,cap = {phiMu_str}",
            "Limit": f"M\u2093,min = {Mu_min_str}",
            "Utilisation": Mu_min_util_str,
            "Status": Mu_min_status,
        },
        {
            "Check": "Neutral axis ratio kᵤ",
            "Value": f"{ku_val:.3f}" if ku_val is not None else "—",
            "Limit": f"{ku_lim:.2f}",
            "Utilisation": f"{(ku_val/ku_lim):.3f}" if ku_val is not None else "—",
            "Status": "OK" if ku_ok else "Check",
        },
        {
            "Check": "SLS steel stress f\u209b,ser",
            "Value": fs_ser_str,
            "Limit": "SLS (for crack/deflection)",
            "Utilisation": "—",
            "Status": "—",
        },
        {
            "Check": "Neutral axis depth d\u2099",
            "Value": f"d\u2099 = {c_str}",
            "Limit": "",
            "Utilisation": "—",
            "Status": "—",
        },
        {
            "Check": "Stress block depth a = γc",
            "Value": f"a = {a_str}",
            "Limit": "",
            "Utilisation": "—",
            "Status": "—",
        },
    ]

    summary_df = pd.DataFrame(rows_summary)

    def _highlight_status(row):
        status = row.get("Status", "")
        if status == "OK":
            color = "#d9ead3"
        elif status in ("Check", "NG"):
            color = "#f4cccc"
        else:
            color = ""
        return [f"background-color: {color}"] * len(row)

    styled_summary = summary_df.style.apply(_highlight_status, axis=1)

    # ---------------- TOP CONTAINER – Title + 3D in one row, summary full-width below ----------------
    with top_container:
        top_left, top_right = st.columns([0.58, 0.42])

        with top_left:
            st.title("Bending Capacity")

            st.markdown(
                """
This page computes **ultimate flexural capacity**, **strain compatibility**, and
**service-stress outputs** in accordance with **AS 3600:2018 Clause 8**, including:
"""
            )

            st.markdown(r"""
- **Ultimate moment capacity** (Cl. 8.1.3)  
    $$\phi M_{u,\mathrm{cap}} = \phi\,T\,(d - 0.5\,\gamma x_u)$$

- **Steel stress at serviceability**, used in crack-width and deflection checks.  
    $$f_{s,\mathrm{ser}} = E_s\,\varepsilon_s$$
""")

        with top_right:
            # Small spacer to nudge diagram down slightly
            st.markdown("")
            
            # --- Replace old 3D model with curved "2D-looking-3D" diagram ---
            from curved_beam_diagram import render_curved_beam_fig
            
            try:
                # Get parameters from shared state (convert mm to meters for consistency with function)
                inputs = get_bending_inputs_from_shared_state()
                L_m = inputs["L"] / 1000.0  # mm -> m
                D_m = inputs["D"] / 1000.0    # mm -> m
                b_m = inputs["b"] / 1000.0    # mm -> m
                # Convert c_top from mm to m (ULS neutral axis depth)
                if c_top is not None and not (isinstance(c_top, float) and math.isnan(c_top)):
                    dn_uls_m = float(c_top) / 1000.0  # mm -> m
                else:
                    dn_uls_m = 0.21 * D_m  # fallback: 21% of depth (already in meters)
                
                # Draw figure with fixed curvature of 0.4
                if D_m > 0 and L_m > 0 and dn_uls_m > 0:
                    fig_beam = render_curved_beam_fig(
                        L=L_m,          # meters
                        D=D_m,          # meters
                        b=b_m,          # meters
                        dn_uls=dn_uls_m,  # meters - ULS neutral axis depth only
                        ts_centroid_y=None,  # leave None if you already compute Ts centroid elsewhere later
                        curvature=0.4,  # fixed curvature
                        title=None,
                    )
                    st.pyplot(fig_beam, clear_figure=True)
                else:
                    st.info(
                        "Curved beam view will appear once geometry and moment capacity are defined."
                    )
            except Exception as e:
                st.warning("3D view failed to render (browser/graphics). Try refreshing the page.")
            
            # Debug readout (debug mode only)
            if DEBUG_MODE:
                try:
                    from src.debug.debug_flags import is_debug_enabled
                    if is_debug_enabled():
                        st.caption("🔧 DEBUG: Top Layer 1 bars")
                        st.write(f"Widget (inputs_nb_or_s_top_1): {st.session_state.get('inputs_nb_or_s_top_1', 'N/A')}")
                        st.write(f"Shared (nb_or_s_top_1): {st.session_state.get('nb_or_s_top_1', 'N/A')}")
                        st.write(f"Layout value used: {nb_or_s_top_1_layout}")
                        st.write(f"Derived (nb_top): {st.session_state.get('nb_top', 'N/A')}")
                        st.write(f"Derived (Ast_top): {st.session_state.get('Ast_top', 'N/A')}")
                except ImportError:
                    pass

        # Summary table spans full width under the heading + 3D row (deflection-style)
        st.subheader("Bending – Summary")

        # Map summary rows -> REAL calc step UIDs in bending_tabs.py
        check_to_uid = {
            "Steel area Ast,bot": "bending_min_2_5",
            "Flexural capacity": "bending_uls_1_7",
            "Minimum strength": "bending_min_2_4",
            "Neutral axis ratio kᵤ": "bending_uls_1_5",
            "SLS steel stress fₛ,ser": "bending_sls_3_7",
        }
        
        # Map checks to their tabs
        check_to_tab = {
            "Steel area Ast,bot": "Minimum strength checks",
            "Flexural capacity": "ULS Checks",
            "Minimum strength": "Minimum strength checks",
            "Neutral axis ratio kᵤ": "ULS Checks",
            "SLS steel stress fₛ,ser": "SLS Checks",
        }

        # Build ROWS list for render_clickable_summary_table (only include rows with UIDs)
        # Format matches test app: check, value, limit, util, status, ok, uid, tab
        ROWS = []
        for row in rows_summary:
            check = row["Check"]
            uid = check_to_uid.get(check)
            tab = check_to_tab.get(check)
            if uid:  # Only include rows that have a matching calc step
                # Determine ok status for styling (True=pass/green, False=fail/red, None=neutral)
                status_str = row.get("Status", "")
                ok = None
                if status_str == "OK":
                    ok = True
                elif status_str == "Check" or status_str == "FAIL":
                    ok = False
                
                ROWS.append({
                    "uid": uid,
                    "title": check,  # or "check" - both work
                    "value": row.get("Value", ""),
                    "limit": row.get("Limit", ""),
                    "util": row.get("Utilisation", ""),
                    "status": status_str,
                    "ok": ok,
                    "tab": tab,
                    "is_primary": (check == "Flexural capacity"),
                })
        
        # Sort ROWS so Flexural capacity is first
        priority = {
            "Flexural capacity": 0,
            "Steel area Ast,bot": 1,
            "Minimum strength": 2,
            "Neutral axis ratio kᵤ": 3,
            "SLS steel stress fₛ,ser": 4,
        }
        ROWS.sort(key=lambda r: priority.get(r["title"], 99))

        # Render summary table using shared helper
        clicked_uid = render_clickable_summary_table(ROWS, key_prefix="bend_summary")
        
        # Handle clicked summary row: set mode, expand step, set pending scroll
        if clicked_uid:
            # Map UID to mode
            def uid_to_mode(uid):
                """Map a step UID to its mode (ULS, SLS, or MIN)."""
                if uid.startswith("bending_uls_"):
                    return "ULS"
                elif uid.startswith("bending_sls_"):
                    return "SLS"
                elif uid.startswith("bending_min_"):
                    return "MIN"
                else:
                    return "ULS"  # Default to ULS for unknown UIDs
            
            # Set the active mode based on clicked UID
            target_mode = uid_to_mode(clicked_uid)
            st.session_state["bending_active_mode"] = target_mode
            
            # Expand the step that matches clicked_uid
            open_key = f"step_open_{clicked_uid}"
            st.session_state[open_key] = True
            
            # Set pending scroll (will be handled after content renders)
            st.session_state["bending_pending_scroll_uid"] = clicked_uid
        
        # Bind JavaScript for opening expanders and scrolling
        bind_summary_clicks()

    # Persist canonical bending state for the rest of the page (and next rerun)
    st.session_state["bending_state"] = canonical_state

    # Persist canonical bending state for the rest of the page (and next rerun)
    st.session_state["bending_state"] = canonical_state

    # values for later
    phi_Mu_cap = top_results["phi_Mu_cap"]
    c = top_results["c"]
    a = top_results["a"]
    z = top_results["z"]
    ku = top_results["ku"]
    alpha2 = top_results["alpha2"]
    gamma = top_results["gamma"]
    phi = top_results["phi"]
    fctf = top_results["fctf"]
    Z_gross = top_results["Z_gross"]
    Mcr = top_results["Mcr"]
    As_min = top_results["As_min"]
    d = top_results["d"]

    # shared values
    b = get_param("b")
    D = get_param("D")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ec = get_param("Ec")
    Es = get_param("Es")
    Mu_star = get_param("Mu_star")
    L_shared = get_param("L")
    nb_bot = get_param("nb_bot")
    db_bot = get_param("db_bot")
    cover_bot = get_param("cover_bot")
    nb_top = get_param("nb_top")
    db_top = get_param("db_top")
    cover_top = get_param("cover_top")

    # local copies for table
    fc_local = fc if fc is not None else 40.0
    cover_bot_local = cover_bot if cover_bot is not None else 40.0
    db_bot_local = db_bot if db_bot is not None else 20.0
    nb_bot_local = int(nb_bot) if nb_bot is not None else 4
    D_local = D if D is not None else 600.0

    d_eff = d
    if d_eff is None or (isinstance(d_eff, float) and math.isnan(d_eff)):
        d_eff = D_local - cover_bot_local - 0.5 * db_bot_local

    Ast_bot = Ast
    if Ast_bot is None or (isinstance(Ast_bot, float) and math.isnan(Ast_bot)):
        Ast_bot = nb_bot_local * math.pi * db_bot_local**2 / 4.0

    alpha2_raw = 0.85 - 0.0015 * fc_local
    gamma_raw = 0.97 - 0.0025 * fc_local
    alpha2_sb = max(0.67, alpha2_raw)
    gamma_sb = max(0.67, gamma_raw)
    phi_b = get_param("phi_bend", 0.85)
    ku_sb = ku if ku is not None else float("nan")

    Mu_min = (
        1.2 * Mcr
        if (Mcr is not None and not (isinstance(Mcr, float) and math.isnan(Mcr)))
        else float("nan")
    )
    Mu_nom_report = phi_Mu_cap / phi if phi and phi > 0 else float("nan")

    page_divider()

    # ---------------- 3-column layout for Design Actions + Geometry + Materials ----------------
    col_actions, col_geom, col_mat = st.columns(3)

    with col_actions:
        # Heading row with info popover for source of design actions
        col_title, col_info = st.columns([0.92, 0.08])
        with col_title:
            st.subheader("Design Actions for Bending")
        with col_info:
            with info_i_button(help_text="Source of design actions (M*, V*)"):
                # Initialize session state key if not present
                if "bending_action_source" not in st.session_state:
                    st.session_state["bending_action_source"] = "manual"
                
                action_source = st.radio(
                    "Source of design actions (M, V):",
                    ["Manual design actions (inputs below)", "Teaching SFD/BMD page"],
                    index=0 if st.session_state["bending_action_source"] == "manual" else 1,
                    key="bending_action_source_radio",
                )
                
                # Update session state based on selection
                if action_source == "Manual design actions (inputs below)":
                    st.session_state["bending_action_source"] = "manual"
                else:
                    st.session_state["bending_action_source"] = "sfd_bmd"
        
        # Show caption with current selection
        current_source = st.session_state.get("bending_action_source", "manual")
        if current_source == "manual":
            st.caption("Design actions: Manual")
        else:
            st.caption("Design actions: From SFD/BMD")

        # Get current values (widget key takes precedence if exists, otherwise use shared key)
        Mu_star_val = _coalesce_num(st.session_state.get("bending_Mu_star", get_param("uls_Mstar", 500.0)), 500.0)
        N_star_val = _coalesce_num(st.session_state.get("bending_N_star", get_param("N_star", 0.0)), 0.0)
        P_star_val = _coalesce_num(st.session_state.get("bending_P_star", get_param("P_star", 0.0)), 0.0)
        phi_b_val = _coalesce_num(st.session_state.get("bending_phi_b", get_param("phi_bend", 0.85)), 0.85)
        
        number_row(
            "Design moment Mu* (kNm)",
            "bending_Mu_star",
            Mu_star_val,
            sync_callbacks,
            help_text=(
                "Factored design bending moment at the critical section. "
                "Increasing Mu* increases bending demand and utilisation."
            ),
        )
        number_row(
            "Axial force N* (kN)",
            "bending_N_star",
            N_star_val,
            sync_callbacks,
            help_text=(
                "Axial force acting with bending. Compression (negative in many "
                "conventions) can reduce tension in the steel; tension increases demand."
            ),
        )
        number_row(
            "Prestress force P* (kN)",
            "bending_P_star",
            P_star_val,
            sync_callbacks,
            help_text=(
                "Prestress / pre-compression in the section. Increasing P* typically "
                "reduces tensile demand in the bottom reinforcement."
            ),
        )
        number_row(
            "Bending strength factor ϕb",
            "bending_phi_b",
            phi_b_val,
            sync_callbacks,
            help_text=(
                "Strength reduction factor for bending (AS 3600 ϕ-factor). "
                "This multiplies the nominal capacity to give ϕM_u,cap."
            ),
        )

    with col_geom:
        st.subheader("Geometry")
        # Get current values (widget key takes precedence if exists, otherwise use shared key)
        b_val = _coalesce_num(st.session_state.get("bending_b", get_param("b", 400.0)), 400.0)
        D_val = _coalesce_num(st.session_state.get("bending_D", get_param("D", 600.0)), 600.0)
        L_val = _coalesce_num(st.session_state.get("bending_L", get_param("L", 3000.0)), 3000.0)
        
        number_row(
            "Width b (mm)",
            "bending_b",
            b_val,
            sync_callbacks,
            help_text=(
                "Section width. Increasing b increases compression block area and "
                "reduces required tensile steel for a given Mu*."
            ),
        )
        number_row(
            "Depth D (mm)",
            "bending_D",
            D_val,
            sync_callbacks,
            help_text=(
                "Overall section depth. Larger D increases lever arm (d) and "
                "typically increases bending capacity."
            ),
        )
        number_row(
            "Span L (mm)",
            "bending_L",
            L_val,
            sync_callbacks,
            help_text=(
                "Member span. Used mainly for serviceability checks and linking to "
                "deflection; not directly in φMu,cap here."
            ),
        )

    with col_mat:
        st.subheader("Materials")
        # Get current values (widget key takes precedence if exists, otherwise use shared key)
        fc_val = _coalesce_num(st.session_state.get("bending_fc", get_param("fc", 40.0)), 40.0)
        fsy_val = _coalesce_num(st.session_state.get("bending_fsy", get_param("fsy", 500.0)), 500.0)
        Ec_val = _coalesce_num(st.session_state.get("bending_Ec", get_param("Ec", 30000.0)), 30000.0)
        Es_val = _coalesce_num(st.session_state.get("bending_Es", get_param("Es", 200000.0)), 200000.0)
        
        number_row(
            "Concrete strength f'c (MPa)",
            "bending_fc",
            fc_val,
            sync_callbacks,
            help_text=(
                "Concrete compressive strength. Higher f'c increases compression "
                "capacity and may reduce required steel, but also changes ductility limits."
            ),
        )
        number_row(
            "Steel yield fsy (MPa)",
            "bending_fsy",
            fsy_val,
            sync_callbacks,
            help_text=(
                "Yield strength of reinforcing steel. Higher fsy increases the "
                "force carried by a given area of steel."
            ),
        )
        number_row(
            "Ec (MPa)",
            "bending_Ec",
            Ec_val,
            sync_callbacks,
            help_text=(
                "Short-term modulus of concrete. Mainly affects stiffness and "
                "SLS behaviour rather than φMu,cap."
            ),
        )
        number_row(
            "Es (MPa)",
            "bending_Es",
            Es_val,
            sync_callbacks,
            help_text=(
                "Steel modulus. Typically ~200,000 MPa; affects cracked-section "
                "stiffness and strain calculations."
            ),
        )

    page_divider()

    # Center reinforcement inputs with equal spacers
    spacer_left, content_col, spacer_right = st.columns([1, 8, 1], gap="medium")
    
    with content_col:
        r1, r2 = st.columns(2, gap="large")

        # Render both headings first to ensure same baseline
        with r1:
            st.subheader("Bottom Longitudinal Reinforcement")
        with r2:
            st.subheader("Top Longitudinal Reinforcement")
        
        # Display messages for bottom reinforcement (in r1)
        with r1:
            if st.session_state.get("_reo_msg_bot_auto_layer2", False):
                show_reo_message("auto_layer2", layer="Bottom Layer 1")
                st.session_state["_reo_msg_bot_auto_layer2"] = False  # Clear after showing
            
            if st.session_state.get("_reo_msg_bot_layer2_overwritten", False):
                show_reo_message("layer2_overwritten", layer="Bottom Layer 1")
                st.session_state["_reo_msg_bot_layer2_overwritten"] = False  # Clear after showing
            
            if st.session_state.get("_reo_error_bot_1", False):
                show_reo_message("layout_invalid", layer="Bottom Layer 1")
                st.session_state["_reo_error_bot_1"] = False  # Clear after showing
            
            warning_bot_1 = st.session_state.get("_reo_warning_bot_1")
            if warning_bot_1:
                # Extract s_min if available
                s_min_val = st.session_state.get("_reo_s_min_bot_1", 25.0)
                show_reo_message("spacing_clamped", layer="Bottom Layer 1", s_min=s_min_val)
                st.session_state["_reo_warning_bot_1"] = None  # Clear after showing
                st.session_state["_reo_s_min_bot_1"] = None
        
        # Display messages for top reinforcement (in r2)
        with r2:
            if st.session_state.get("_reo_msg_top_auto_layer2", False):
                show_reo_message("auto_layer2", layer="Top Layer 1")
                st.session_state["_reo_msg_top_auto_layer2"] = False  # Clear after showing
            
            if st.session_state.get("_reo_msg_top_layer2_overwritten", False):
                show_reo_message("layer2_overwritten", layer="Top Layer 1")
                st.session_state["_reo_msg_top_layer2_overwritten"] = False  # Clear after showing
            
            if st.session_state.get("_reo_error_top_1", False):
                show_reo_message("layout_invalid", layer="Top Layer 1")
                st.session_state["_reo_error_top_1"] = False  # Clear after showing
            
            warning_top_1 = st.session_state.get("_reo_warning_top_1")
            if warning_top_1:
                # Extract s_min if available
                s_min_val = st.session_state.get("_reo_s_min_top_1", 25.0)
                show_reo_message("spacing_clamped", layer="Top Layer 1", s_min=s_min_val)
                st.session_state["_reo_warning_top_1"] = None  # Clear after showing
                st.session_state["_reo_s_min_top_1"] = None
        
        # Now render all reo inputs in parallel to ensure alignment
        with r1:
            # Layer 1 mode
            select_row(
                "Layer 1 layout mode",
                "bending_bot1_layout_mode",
                REO_LAYOUT_MODE,
                "Count",
                sync_callbacks,
                help_text="Count vs spacing.",
                use_columns=False,
            )

            mode = st.session_state.get("bending_bot1_layout_mode", st.session_state.get("bot1_layout_mode", "Count"))

            if mode == "Count":
                select_row(
                    "Layer 1 bars (count)",
                    "bending_bot1_count",
                    REO_COUNTS_0_12,
                    4,
                    sync_callbacks,
                    help_text="0–12",
                    use_columns=False,
                )
            else:
                select_row(
                    "Layer 1 bar spacing (mm)",
                    "bending_bot1_spacing",
                    REO_SPACINGS,
                    200,
                    sync_callbacks,
                    help_text="75–300",
                    use_columns=False,
                )

            select_row(
                "Layer 1 bar Ø (mm)",
                "bending_db_bot_1",
                REO_BAR_DIAS,
                20,
                sync_callbacks,
                help_text="Nominal bar diameter for Layer 1 (mm).",
                use_columns=False,
            )
            
            # Layer 2 mode
            select_row(
                "Layer 2 layout mode",
                "bending_bot2_layout_mode",
                REO_LAYOUT_MODE,
                "Count",
                sync_callbacks,
                help_text="Count vs spacing.",
                use_columns=False,
            )

            mode2 = st.session_state.get("bending_bot2_layout_mode", st.session_state.get("bot2_layout_mode", "Count"))

            if mode2 == "Count":
                select_row(
                    "Layer 2 bars (count)",
                    "bending_bot2_count",
                    REO_COUNTS_0_12,
                    0,
                    sync_callbacks,
                    help_text="0–12",
                    use_columns=False,
                )
            else:
                select_row(
                    "Layer 2 bar spacing (mm)",
                    "bending_bot2_spacing",
                    REO_SPACINGS,
                    200,
                    sync_callbacks,
                    help_text="75–300",
                    use_columns=False,
                )

            select_row(
                "Layer 2 bar Ø (mm)",
                "bending_db_bot_2",
                REO_BAR_DIAS,
                20,
                sync_callbacks,
                help_text="Nominal bar diameter for Layer 2 (mm).",
                use_columns=False,
            )
            
            rowgap_bot_val = float(st.session_state.get("bending_rowgap_bot", get_param("rowgap_bot", 60.0)))

            number_row(
                "Row gap (mm)",
                "bending_rowgap_bot",
                rowgap_bot_val,
                sync_callbacks,
                help_text="Clear vertical gap between Layer 1 and Layer 2 (mm).",
            )
            
            # Get current cover value (widget key takes precedence if exists, otherwise use shared key)
            cover_bot_val = _coalesce_num(st.session_state.get("bending_cover_bot", get_param("cover_bot", 40.0)), 40.0)
            
            number_row(
                "Bottom cover (mm)",
                "bending_cover_bot",
                cover_bot_val,
                sync_callbacks,
                help_text=(
                    "Concrete cover to bottom reinforcement. Increasing cover reduces "
                    "effective depth d and reduces φMu,cap, but may be required for durability."
                ),
            )

        with r2:
            # Layer 1 mode
            select_row(
                "Layer 1 layout mode",
                "bending_top1_layout_mode",
                REO_LAYOUT_MODE,
                "Count",
                sync_callbacks,
                help_text="Count vs spacing.",
                use_columns=False,
            )

            mode = st.session_state.get("bending_top1_layout_mode", st.session_state.get("top1_layout_mode", "Count"))

            if mode == "Count":
                select_row(
                    "Layer 1 bars (count)",
                    "bending_top1_count",
                    REO_COUNTS_0_12,
                    2,
                    sync_callbacks,
                    help_text="0–12",
                    use_columns=False,
                )
            else:
                select_row(
                    "Layer 1 bar spacing (mm)",
                    "bending_top1_spacing",
                    REO_SPACINGS,
                    200,
                    sync_callbacks,
                    help_text="75–300",
                    use_columns=False,
                )

            select_row(
                "Layer 1 bar Ø (mm)",
                "bending_db_top_1",
                REO_BAR_DIAS,
                16,
                sync_callbacks,
                help_text="Nominal bar diameter for Layer 1 (mm).",
                use_columns=False,
            )
            
            # Layer 2 mode
            select_row(
                "Layer 2 layout mode",
                "bending_top2_layout_mode",
                REO_LAYOUT_MODE,
                "Count",
                sync_callbacks,
                help_text="Count vs spacing.",
                use_columns=False,
            )

            mode2 = st.session_state.get("bending_top2_layout_mode", st.session_state.get("top2_layout_mode", "Count"))

            if mode2 == "Count":
                select_row(
                    "Layer 2 bars (count)",
                    "bending_top2_count",
                    REO_COUNTS_0_12,
                    0,
                    sync_callbacks,
                    help_text="0–12",
                    use_columns=False,
                )
            else:
                select_row(
                    "Layer 2 bar spacing (mm)",
                    "bending_top2_spacing",
                    REO_SPACINGS,
                    200,
                    sync_callbacks,
                    help_text="75–300",
                    use_columns=False,
                )
            
            select_row(
                "Layer 2 bar Ø (mm)",
                "bending_db_top_2",
                REO_BAR_DIAS,
                16,
                sync_callbacks,
                help_text="Nominal bar diameter for Layer 2 (mm).",
                use_columns=False,
            )
            
            rowgap_top_val = float(st.session_state.get("bending_rowgap_top", get_param("rowgap_top", 60.0)))

            number_row(
                "Row gap (mm)",
                "bending_rowgap_top",
                rowgap_top_val,
                sync_callbacks,
                help_text="Clear vertical gap between Layer 1 and Layer 2 (mm).",
            )
            
            # Get current cover value (widget key takes precedence if exists, otherwise use shared key)
            cover_top_val = _coalesce_num(
                st.session_state.get("bending_cover_top", get_param("cover_top", 40.0)),
                40.0,
            )
            
            number_row(
                "Top cover (mm)",
                "bending_cover_top",
                cover_top_val,
                sync_callbacks,
                help_text=(
                    "Concrete cover to top reinforcement. Affects effective depth to "
                    "compression reinforcement and durability."
                ),
            )

    page_divider()

    # --- GLOBAL CONCRETE STRESS MODEL (shared across all states) ---
    # Initialize global state key if not present
    if "concrete_stress_model" not in st.session_state:
        st.session_state["concrete_stress_model"] = "rectangular"
    
    # Heading row with info popover
    col_title, col_info = st.columns([0.95, 0.05])
    with col_title:
        st.markdown("### Section & stress–strain model")
    with col_info:
        with info_i_button(help_text="Concrete stress model options"):
            st.markdown("**Concrete stress model**")
            use_parabolic = st.checkbox(
                "Use parabolic (non-linear) stress block",
                value=(st.session_state["concrete_stress_model"] == "parabolic"),
                key="bending_parabolic_toggle",
            )
            if use_parabolic:
                st.session_state["concrete_stress_model"] = "parabolic"
            else:
                st.session_state["concrete_stress_model"] = "rectangular"
            
            st.markdown("""
            **Rectangular (AS 3600):** Standard simplified stress block used in AS 3600 design.
            
            **Parabolic (non-linear):** More accurate representation of concrete stress distribution, 
            showing the non-linear relationship between strain and stress.
            """)
    
    # Show the current model label (always visible)
    current_model = st.session_state.get("concrete_stress_model", "rectangular")
    if current_model == "parabolic":
        model_display = "Parabolic (non-linear)"
    else:
        model_display = "Rectangular (AS 3600)"
    st.markdown(f"**{model_display}**")

    # --- STATE RADIO (ULS / SLS / Uncracked) ---
    state_options = ["ULS", "SLS (cracked)", "Uncracked"]
    main_state = st.radio(
        "State:",
        state_options,
        key="bending_state_main",
        horizontal=True,
        index=state_options.index(canonical_state),
    )

    # --- Build label for the 3-panel diagram using global concrete_stress_model ---
    stress_model = st.session_state.get("concrete_stress_model", "rectangular")
    
    if main_state == "ULS":
        if stress_model == "parabolic":
            diagram_state_label = "uls – parabolic"
        else:
            diagram_state_label = "uls – rectangular"
    elif main_state.startswith("SLS"):
        if stress_model == "parabolic":
            diagram_state_label = "sls – parabolic"
        else:
            diagram_state_label = "sls – linear"
    else:  # Uncracked
        if stress_model == "parabolic":
            diagram_state_label = "uncracked – parabolic"
        else:
            diagram_state_label = "uncracked – linear"

    # Persist for the diagram function
    st.session_state["bending_strain_state_local"] = diagram_state_label

    # --- Placeholders so we can render *after* the tabs but keep them visually above ---
    matcurves_placeholder = st.empty()
    diagram_placeholder = st.empty()

    # Underlying strain-state math uses the solver's labels
    if main_state.startswith("ULS"):
        state_for_math = "ULS"
    elif main_state.startswith("SLS"):
        state_for_math = "SLS"
    else:
        state_for_math = "Uncracked"

    # ---------------- Step-by-step tabs ----------------
    apply_step_summary_expander_css()
    
    # Render tabs - always render all tabs with content
    # This ensures anchors exist for scrolling regardless of which tab is visible
    # Streamlit will handle tab switching, and JavaScript will switch to correct tab on summary clicks
    tab1, tab2, tab3 = st.tabs(["ULS Checks", "SLS Checks", "Minimum strength checks"])
    
    # Always render all tabs with their content
    # This ensures all anchors exist for scrolling
    with tab1:
        render_uls_tab(
            top_results, b, D, fc, fsy, Ast_bot, d_eff,
            summary_mode=False,  # no longer used
        )
    
    with tab2:
        render_sls_tab(
            top_results, b, D, d_eff, Ast_bot, Ec, Es, Mu_star_sls,
            summary_mode=False,
        )
    
    with tab3:
        render_min_strength_tab(
            top_results, b, D, fc, fsy, Ast_bot,
            summary_mode=False,
        )
    
    # Get current active mode (set by summary table clicks or defaults to ULS)
    # JavaScript will switch to the correct tab based on the tab name in the summary table click
    # The active_mode is used to determine which tab should be shown programmatically
    
    # Handle pending scroll after content has rendered
    pending_scroll_uid = st.session_state.get("bending_pending_scroll_uid")
    if pending_scroll_uid:
        # Import jump_nav functions
        from jump_nav import scroll_to_jump_after_render
        
        # Set jump_to for scroll function
        st.session_state["jump_to"] = pending_scroll_uid
        
        # Scroll after content has rendered
        scroll_to_jump_after_render()
        
        # Clear pending scroll
        del st.session_state["bending_pending_scroll_uid"]

    # --------------------------------------------------
    # Now build the 3-panel diagram, using the SLS results
    # that render_sls_tab has just written into session_state.
    # --------------------------------------------------
    with diagram_placeholder.container():
        ss_state = _stress_strain_state(state_for_math)
        
        # For SLS, add cracked-section neutral axis from the solve
        if state_for_math == "SLS":
            try:
                dn_cracked = st.session_state.get("bending_sls_dn", None)
                if dn_cracked is not None:
                    # Build nested SLS structure with cracked NA
                    ss_state["sls"] = {
                        "dn_cracked": float(dn_cracked),
                        "dn": float(dn_cracked),  # also set as dn for backward compatibility
                        "eps_c_top": st.session_state.get("bending_sls_eps_top"),
                        "eps_s_layers": [],  # will be populated if available
                        "sig_s_layers": [],
                        "y_layers": [],
                    }
            except Exception:
                pass
        
        fig_ss = _plot_stress_strain_profiles(
            ss_state,
            state_label=diagram_state_label,
            layout=cached_layout,  # Pass cached layout to avoid recomputation
        )
        try:
            st.plotly_chart(fig_ss, width="stretch", config={"displayModeBar": False})
        except Exception as e:
            st.warning("3D view failed to render (browser/graphics). Try disabling 3D view or refreshing the page.")

    # --------------------------------------------------
    # Material stress–strain curves (concrete + steel),
    # rendered *after* SLS tab but shown above it.
    # --------------------------------------------------
    with matcurves_placeholder.container():
        with st.expander("ℹ️ Stress–strain model & material behaviour", expanded=False):
            st.markdown(
                f"""
**Current state:** `{main_state}`  

This diagram shows how **concrete** and **steel** share strain in a reinforced
concrete section, and how we go from **strain → stress → force**:

- In the **elastic range** we use **Hooke's law**  

  - Steel:  $\\sigma_s = E_s \\, \\varepsilon_s$  

  - Concrete (short-term):  $\\sigma_c = E_c \\, \\varepsilon_c$  

- Once we know the **stress** we get the **resultant force** by  
  $$F = \\sigma \\; A$$  

  where $A$ is the relevant steel or concrete area (e.g. $A_{{st}}$ for tension bars,
  $b \\times a$ for the ULS concrete block).

- For **steel** we assume a **linear elastic** branch up to the yield stress
  $f_{{sy}}$ (your session value, typically about 500 MPa), then a near-horizontal
  plastic region with slight hardening and softening – similar to a test curve.

- For **concrete in compression** we use a **non-linear parabolic** stress–strain curve.
  At ULS we replace this with the **AS 3600 rectangular** $\\alpha_2$–$\\gamma$
  stress block, chosen so it has the **same resultant force and lever arm** as
  the underlying parabolic distribution.

- At **SLS** and in the *uncracked* state we still assume a **linear strain profile**,
  but with lower stresses (service-level actions). The vertical dotted lines on
  the plots mark the **SLS** and **ULS** points for concrete and steel.

**Sign convention note**

- In the main section/strain diagrams on this page, **tension steel strains are negative**
  (ε < 0) and compression is positive – this matches typical reinforced concrete
  sign conventions.

- In the **steel material curve below**, we instead plot the **magnitude**
  $|\\varepsilon_s| \\ge 0$ on the x-axis. So any negative steel strains read from the
  ULS/SLS diagrams have been converted to **positive values here**, but they still
  represent the **tension capacity** of the steel.

The difference between the concrete and steel curves – mainly their **slopes**
($E_c$ vs $E_s$) – is what drives the different **forces** that develop at SLS and ULS
for the same strain pattern.

"""
            )
            fig_mat = _plot_material_stress_strain_curves()
            try:
                st.plotly_chart(
                    fig_mat,
                    width="stretch",
                    config={"displayModeBar": False},
                )
            except Exception as e:
                st.warning("Material curves view failed to render (browser/graphics). Try refreshing the page.")
    
    # Handle scroll after all content is rendered (for cross-page navigation from Inputs)
    from jump_nav import scroll_to_jump_after_render
    scroll_to_jump_after_render()
    
    # Debug: dump session state inventory
    try:
        from state_and_helpers import dump_session_state_inventory
        dump_session_state_inventory("bending", sync_callbacks=sync_callbacks, out_dir=".")
    except Exception:
        pass
    


# ============================
# MAIN GUARD
# ============================
if __name__ == "__main__":
    render_bending()