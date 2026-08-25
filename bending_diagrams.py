# bending_diagrams.py
import math
import os
import numpy as np
import streamlit as st

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import logging

from state_and_helpers import get_param
import strain_display
from bending_core import _layout_bars_in_rows, _stress_strain_state

logger = logging.getLogger(__name__)
from bending_layer_semantics import resolve_bending_faces, resolve_bending_layer_geometry
from section_layout import compute_section_layout
from plotly_section import make_sectionA_figure
from section_props.plot import apply_section_axes
from ui.diagrams.stress_strain_diagram import (
    inject_figure_into_subplot as _stress_diagram_inject_figure_into_subplot,
    plot_strain_profile as _stress_diagram_plot_strain_profile,
    plot_stress_strain_profiles as _stress_diagram_plot_stress_strain_profiles,
    make_material_stress_strain_curves_figure as _stress_diagram_make_material_stress_strain_curves_figure,
    make_sls_stress_block_figure as _stress_diagram_make_sls_stress_block_figure,
    make_uls_force_model_figure as _stress_diagram_make_uls_force_model_figure,
    make_uls_stress_block_figure as _stress_diagram_make_uls_stress_block_figure,
)

# ------------------------------------------------------------
# Global styling constants
# ------------------------------------------------------------
LINE_THICK = 1.0   # main outlines
LINE_MED   = 0.8   # normal lines
LINE_THIN  = 0.6   # light lines

FS_TITLE  = 8      # diagram titles
FS_LABEL  = 7      # axis labels / main text
FS_ANNOT  = 5      # small annotations

ARROW_SCALE = 4    # small arrowheads for everything

def _inject_figure_into_subplot(parent_fig, child_fig, *, row: int, col: int, xref: str, yref: str):
    """
    Copy traces + shapes + annotations from child_fig into a subplot
    of parent_fig (created by make_subplots).
    """
    return _stress_diagram_inject_figure_into_subplot(
        parent_fig,
        child_fig,
        row=row,
        col=col,
        xref=xref,
        yref=yref,
    )


def _norm_shape_name(s: str) -> str:
    """Normalise shape names across the app so diagrams behave consistently."""
    s = (s or "").strip()
    lo = s.lower()

    # Rect
    if "rectangle" in lo or lo == "rect":
        return "Rectangular"

    # T / I
    if lo in {"t", "t section", "t-section", "t beam"} or lo.startswith("t"):
        return "T-Section"
    if lo in {"i", "i section", "i-section", "i beam"} or lo.startswith("i"):
        return "I-Section"

    # Already normalised?
    if "t-section" in lo:
        return "T-Section"
    if "i-section" in lo:
        return "I-Section"
    if "rectangular" in lo:
        return "Rectangular"

    # Fallback – return as-is
    return s


def _get_current_shape_from_session() -> str:
    """Best-effort read of current shape selection from session state."""
    import streamlit as st
    raw = (
        st.session_state.get("shape_name")
        or st.session_state.get("sec_shape")
        or st.session_state.get("section_shape")
        or st.session_state.get("geometry_section_shape")
        or "Rectangular"
    )
    return _norm_shape_name(str(raw))


def _get_layers(reo_layout: dict, side: str):
    if not reo_layout:
        return []
    keys = []
    if side == "top":
        keys = [
            "top",
            "top_flange",
            "top_web",
            "top_left",
            "top_right",
            "top_flange_left",
            "top_flange_right",
        ]
    else:
        keys = [
            "bottom",
            "bottom_flange",
            "bottom_web",
            "bottom_left",
            "bottom_right",
            "bottom_flange_left",
            "bottom_flange_right",
        ]

    out = []
    for k in keys:
        v = reo_layout.get(k)
        if not v:
            continue
        out += v if isinstance(v, list) else [v]
    return out


# ------------------------------------------------------------
# Helper: parabolic concrete stress (for Parabolic view)
# (kept for possible future use – current parabolic block
#  uses a simple textbook 2z − z² profile directly)
# ------------------------------------------------------------
def _sigma_c_parabolic(eps, sigma_peak, eps0=0.002, eps_cu=0.003):
    """
    Simple Hognestad-style parabolic + linear softening model.

    eps        : compressive strain (>= 0, concrete)
    sigma_peak : peak compressive stress used for this diagram (MPa)
                 (we use alpha2 * f'c so the scale matches the ULS block)
    """
    if eps <= 0.0:
        return 0.0
    if eps <= eps0:
        x = eps / eps0
        return sigma_peak * (2.0 * x - x**2)
    if eps <= eps_cu:
        return sigma_peak * (eps_cu - eps) / (eps_cu - eps0)
    return 0.0


# ------------------------------------------------------------
# DIAGRAM LAYOUT / LABEL SPACING CONVENTIONS
# ------------------------------------------------------------
# We keep all labels a consistent distance from each diagram so
# the 3 panels look aligned and clean. Rules:
#
# 1) SECTION PANEL (col 1)
#    - Section rectangle spans x = 0 → b, y = 0 → D.
#    - All vertical depth arrows (d, d_n, etc.) sit on the SAME
#      vertical line, a fixed distance to the right of the beam:
#
#        margin_right_section = 0.20 * b      # arrow line
#        text_dx_section      = 0.04 * b      # extra for label text
#
#      So:
#        x_d  = b + margin_right_section
#        x_dn = b + margin_right_section
#
#      Labels:
#        d-label   at (x_d  + text_dx_section,  d  / 2)
#        d_n-label at (x_dn + text_dx_section,  c  / 2)
#
#    - NO other "magic" x-offsets should be used for depth labels
#      in this panel – they must all derive from these margins.
#
# 2) STRAIN PANEL (col 2)
#    - Depth axis runs y = 0 → D.
#    - We keep labels close to their points using a fixed pixel
#      y-shift rather than ad-hoc coordinates:
#
#        eps_label_shift = 12  # pixels
#
#      So:
#        ε_c label: yshift = -eps_label_shift  (above top fibre)
#        ε_s label: yshift = +eps_label_shift  (below steel point)
#
#    - Any other strain labels should reuse this same yshift
#      pattern (above = -shift, below = +shift).
#
# 3) STRESS PANEL (col 3)
#    - Compression region for concrete sits between:
#        x = x_axis → x_block_right
#        y = block_top → block_bottom
#    - Top stress width arrow + label (α₂ f'c or E_c ε_c)
#      sit in a fixed "top band" above the block:
#
#        top_band_arrow_y = -0.06 * D   # arrow line
#        top_band_label_y = -0.12 * D   # label text
#
#      The width arrow is centred between x_axis and x_block_right,
#      and the label is centred at the same x, at top_band_label_y.
#
#    - Depth arrow on the right (γ d_n or d_n) uses a single
#      horizontal margin beyond the block:
#
#        margin_right_stress = 0.08 * D
#        text_dx_stress      = 0.04 * D
#
#      So:
#        x_gc (depth arrow line) = x_block_right + margin_right_stress
#        depth label text at x = x_gc + text_dx_stress,
#        y = 0.5 * (block_top + block_bottom).
#
#    - All right-hand labels in this panel (depth labels) should
#      reuse these margins, not introduce new offsets.
#
# 4) SLS STRESS-BLOCK FIGURES
#    - For _make_sls_stress_block_figure and related SLS figures,
#      we mirror the stress panel conventions using D_ref instead
#      of D:
#
#        top_band_arrow_y = -0.06 * D_ref
#        top_band_label_y = -0.12 * D_ref
#
#      The "E_c ε_c" arrow + label must use those y-positions so
#      they visually line up with the main stress panel.
#
# Summary:
#   - Section panel → 0.20b arrow, 0.24b labels (to the right).
#   - Strain panel → fixed ±eps_label_shift yshift.
#   - Stress panels → 0.06D arrow band, 0.12D label band above,
#     0.08D right margin + 0.04D label offset for depth labels.
#   - Do NOT add new arbitrary offsets; reuse these margins.
# ------------------------------------------------------------

# ============================================================
#  MAIN 3-PANEL SECTION / STRAIN / STRESS DIAGRAM
# ============================================================
def _plot_stress_strain_profiles(
    state_dict, state_label=None, layout=None, moment_sign: str = "positive"
):
    """Build the shared 3-panel figure from resolved engineering state.

    Bending-page reuse is owned by the bounded diagram-bundle presentation
    cache.  Keeping this builder free of session cache ownership prevents two
    competing invalidation paths.
    """
    return _stress_diagram_plot_stress_strain_profiles(
        state_dict,
        state_label=state_label,
        layout=layout,
        moment_sign=moment_sign,
    )


def _plot_strain_profile(
    state_dict, state_label=None, layout=None, moment_sign: str = "positive"
):
    """Compatibility wrapper for the shared single-panel strain diagram builder."""
    return _stress_diagram_plot_strain_profile(
        state_dict,
        state_label=state_label,
        layout=layout,
        moment_sign=moment_sign,
    )


# ============================================================
#  MATERIAL STRESS-STRAIN CURVES (for info box)
# ============================================================
def _plot_material_stress_strain_curves():
    """
    Plot concrete and steel stress-strain curves.

    State/result lookup stays here; the Plotly figure construction lives in
    ``ui.diagrams.stress_strain_diagram``.
    """
    try:
        from inputs_application.active_beam_engineering_state import (
            resolve_active_beam_engineering_state,
        )

        material_state = dict(
            resolve_active_beam_engineering_state(st.session_state).values
        )
        fc = float(material_state.get("fc", 40.0))
        fsy = float(material_state.get("fsy", 500.0))
        Ec = float(material_state.get("Ec", 30000.0))
        Es = float(material_state.get("Es", 200000.0))
    except Exception:
        fc, fsy, Ec, Es = 40.0, 500.0, 30000.0, 200000.0

    eps_s_sls = None
    fs_s_sls = None

    try:
        eps_s_from_state = st.session_state.get("bending_sls_eps_bot", None)
        if eps_s_from_state is not None:
            eps_s_sls = float(eps_s_from_state)
    except Exception:
        pass

    try:
        fs_ser_shared = get_param("sigma_s_sls", None)
        if fs_ser_shared is not None:
            fs_s_sls = float(fs_ser_shared)
    except Exception:
        pass

    try:
        sls_state = _stress_strain_state("SLS")
    except Exception:
        sls_state = None

    if sls_state is not None:
        if eps_s_sls is None:
            try:
                eps_s_sls = float(sls_state.get("eps_s", 0.0))
            except Exception:
                pass
        if fs_s_sls is None:
            try:
                fs_s_sls = float(sls_state.get("fs_t", 0.0))
            except Exception:
                pass

    if eps_s_sls is None and fs_s_sls is not None:
        eps_s_sls = fs_s_sls / Es
    if fs_s_sls is None and eps_s_sls is not None:
        fs_s_sls = Es * eps_s_sls
    if eps_s_sls is None or fs_s_sls is None:
        fs_s_sls = 0.6 * fsy
        eps_s_sls = fs_s_sls / Es

    try:
        uls_state = _stress_strain_state("ULS")
    except Exception:
        uls_state = None

    eps_y_ref = fsy / Es
    if uls_state is not None:
        try:
            eps_s_uls = float(uls_state.get("eps_s", eps_y_ref))
        except Exception:
            eps_s_uls = eps_y_ref
        try:
            fs_s_uls = float(uls_state.get("fs_t", fsy))
        except Exception:
            fs_s_uls = fsy
    else:
        eps_s_uls = eps_y_ref
        fs_s_uls = fsy

    eps_c_sls = None
    try:
        eps_top_state = st.session_state.get("bending_sls_eps_top", None)
        if eps_top_state is not None:
            eps_c_sls = float(eps_top_state)
    except Exception:
        pass

    return _stress_diagram_make_material_stress_strain_curves_figure(
        fc=fc,
        fsy=fsy,
        Ec=Ec,
        Es=Es,
        eps_s_sls=eps_s_sls,
        fs_s_sls=fs_s_sls,
        eps_s_uls=eps_s_uls,
        fs_s_uls=fs_s_uls,
        eps_c_sls=eps_c_sls,
    )


# ============================================================
#  ULS STRESS BLOCK FIGURE (1.1 / 1.3 VARIANTS)
# ============================================================
#  ULS STRESS BLOCK FIGURE (1.1 / 1.4 VARIANTS)
# ============================================================
def _make_uls_stress_block_figure(
    b_mm: float,
    D_mm: float,
    d_mm: float,
    dn_mm: float,
    a_mm: float,
    alpha2: float,
    gamma: float,
    fc: float,
    fsy: float,
    show_lever_arm: bool = False,  # kept for API, not used
    show_dn: bool = True,
    show_alpha_label: bool = True,
    show_C: bool = False,
    C_N: float | None = None,
    variant: str = "11",
    moment_sign: str = "positive",
):
    return _stress_diagram_make_uls_stress_block_figure(
        b_mm=b_mm,
        D_mm=D_mm,
        d_mm=d_mm,
        dn_mm=dn_mm,
        a_mm=a_mm,
        alpha2=alpha2,
        gamma=gamma,
        fc=fc,
        fsy=fsy,
        show_lever_arm=show_lever_arm,
        show_dn=show_dn,
        show_alpha_label=show_alpha_label,
        show_C=show_C,
        C_N=C_N,
        variant=variant,
        moment_sign=moment_sign,
    )


# ============================================================
#  SIMPLE ULS FORCE MODEL FIGURE (1.6)
# ============================================================
def _make_uls_force_model_figure(
    D_mm: float,
    d_mm: float,
    a_mm: float,
    C_N: float | None = None,
    T_N: float | None = None,
    moment_sign: str = "positive",
    dn_mm: float | None = None,
):
    return _stress_diagram_make_uls_force_model_figure(
        D_mm=D_mm,
        d_mm=d_mm,
        a_mm=a_mm,
        C_N=C_N,
        T_N=T_N,
        moment_sign=moment_sign,
        dn_mm=dn_mm,
    )


# ============================================================
#  NEW: SLS STRESS-BLOCK / SECTION FIGURE FOR 3.3
# ============================================================
def _make_sls_stress_block_figure(
    D_mm: float,
    d_mm: float,
    dn_mm: float,
    include_comp: bool = False,
    d_comp_mm: float | None = None,
    moment_sign: str = "positive",
):
    """
    SLS stress-block figure for Step 3.2 (cracked section), rebuilt to MATCH the
    main 3-panel Stress diagram conventions:

    - Same axis layout (x_axis=0.1, usable_width=0.7)
    - Same top-band arrow + label positions (-0.06D, -0.12D)
    - Same right-side depth arrow spacing concept
    - Triangular compression block to d_n
    - Multiple tension layers shown automatically (T1, T2, ...) with stress in MPa

    moment_sign must match the active bending tab (positive = sagging, negative = hogging)
    so compression block and tension steel layers swap consistently with the main diagrams.

    Uses session_state:
      bending_sls_dn, bending_sls_eps_top, bending_sls_eps_bot, bending_sls_y_bot
    and section_layout.compute_section_layout() for bar layer depths.
    """

    # -------------------------
    # Pull layout (bar layers)
    # -------------------------
    try:
        layout = compute_section_layout()
        D = float(layout.get("D", D_mm))
        reo_layout = layout.get("reo_layout", None)
    except Exception:
        D = float(D_mm if D_mm else 600.0)
        reo_layout = None

    if not D or D <= 0:
        D = 600.0

    D_draw = float(D)

    # -------------------------
    # Pull SLS state (preferred)
    # -------------------------
    try:
        dn_sls = st.session_state.get("bending_sls_dn", None)
        eps_top_sls = st.session_state.get("bending_sls_eps_top", None)  # solver: compression negative
        # (eps_bot_sls and y_bot_sls exist but we don't need them if we have dn + eps_top)
    except Exception:
        dn_sls, eps_top_sls = None, None

    # Neutral axis depth
    try:
        c = float(dn_sls) if dn_sls is not None else float(dn_mm)
    except Exception:
        c = float(dn_mm)

    c = max(1e-6, min(float(D), float(c)))

    # Material props (elastic SLS)
    try:
        Ec = float(get_param("Ec", 30000.0))  # MPa
        Es = float(get_param("Es", 200000.0))  # MPa
    except Exception:
        Ec, Es = 30000.0, 200000.0

    tension_face, _, is_hogging = resolve_bending_faces(moment_sign)

    try:
        kappa = float(st.session_state.get("bending_sls_kappa", 0) or 0)
    except Exception:
        kappa = 0.0

    # Concrete stress scale at the extreme compression fibre (elastic SLS)
    if is_hogging:
        try:
            eps_extreme = kappa * (float(D) - float(c))
        except Exception:
            eps_extreme = 0.0
        if abs(eps_extreme) < 1e-12:
            try:
                eps_extreme = float(eps_top_sls) if eps_top_sls is not None else -0.0002
            except Exception:
                eps_extreme = -0.0002
        sigma_c_top = Ec * abs(float(eps_extreme))

        def eps_at_y(y: float) -> float:
            return kappa * (float(y) - float(c))
    else:
        try:
            eps_top = float(eps_top_sls) if eps_top_sls is not None else -0.0002
        except Exception:
            eps_top = -0.0002

        sigma_c_top = Ec * abs(eps_top)  # MPa

        def eps_at_y(y: float) -> float:
            return eps_top * (1.0 - float(y) / float(c))

    # -------------------------
    # Collect tension layers
    # -------------------------
    tension_layers = []  # list of (y, label, sigma_MPa)

    if reo_layout and isinstance(reo_layout, dict):
        ys = []
        for layer in _get_layers(reo_layout, tension_face):
            try:
                ys.append(float(layer["y"]))
            except Exception:
                pass
        if tension_face == "bottom":
            ys_t = [y for y in ys if y > c + 1e-6]
            ys_t.sort(reverse=True)
        else:
            ys_t = [y for y in ys if y < c - 1e-6]
            ys_t.sort()
        for i, y in enumerate(ys_t, start=1):
            sig = Es * eps_at_y(y)
            tension_layers.append((y, f"T{i}", float(sig)))

    else:
        try:
            y = float(d_mm)
        except Exception:
            y = float(D * 0.9) if tension_face == "bottom" else float(D * 0.1)
        sig = Es * eps_at_y(y)
        tension_layers.append((y, "T1", float(sig)))

    # optional compression steel arrow (if requested)
    comp_layer = None
    if include_comp and d_comp_mm is not None:
        try:
            ycs = float(d_comp_mm)
            sigcs = Es * eps_at_y(ycs)  # likely compression negative
            comp_layer = (ycs, "Cₛ", float(sigcs))
        except Exception:
            comp_layer = None

    return _stress_diagram_make_sls_stress_block_figure(
        D_mm=D_mm,
        d_mm=d_mm,
        dn_mm=dn_mm,
        d_comp_mm=d_comp_mm,
        D_draw=D_draw,
        c=c,
        sigma_c_top=sigma_c_top,
        tension_layers=tension_layers,
        comp_layer=comp_layer,
        is_hogging=is_hogging,
    )


def make_sls_transformed_section_figure(result: dict):
    """Show the cracked transformed-section geometry used by SLS Check 2."""

    depth = float(result.get("depth_mm", 0.0) or 0.0)
    shape = str(result.get("section_shape", "RECT") or "RECT").upper()
    width = float(result.get("width_mm", 1.0) or 1.0)
    flange_width = float(result.get("flange_width_mm", width) or width)
    flange_thickness = float(result.get("flange_thickness_mm", 0.0) or 0.0)
    web_width = float(result.get("web_width_mm", width) or width)
    dn_from_top = float(result.get("neutral_axis_depth_from_top_mm", 0.0) or 0.0)
    compression_face = str(result.get("compression_face", "top") or "top")
    layers = tuple(result.get("layers", ()) or ())
    if depth <= 0.0:
        depth = 1.0

    fig = go.Figure()
    max_width = max(width, flange_width, web_width, 1.0)
    centre_x = 0.40

    def x_bounds(segment_width: float) -> tuple[float, float]:
        half = 0.22 * float(segment_width) / max_width
        return centre_x - half, centre_x + half

    if shape == "T":
        physical_segments = (
            (0.0, flange_thickness, flange_width),
            (flange_thickness, depth, web_width),
        )
    elif shape == "I":
        physical_segments = (
            (0.0, flange_thickness, flange_width),
            (flange_thickness, depth - flange_thickness, web_width),
            (depth - flange_thickness, depth, flange_width),
        )
    else:
        physical_segments = ((0.0, depth, width),)
    if compression_face == "top":
        compression_y0, compression_y1 = 0.0, dn_from_top
        cracked_y0, cracked_y1 = dn_from_top, depth
    else:
        compression_y0, compression_y1 = dn_from_top, depth
        cracked_y0, cracked_y1 = 0.0, dn_from_top
    for start, end, segment_width in physical_segments:
        x0, x1 = x_bounds(segment_width)
        active_start = max(start, compression_y0)
        active_end = min(end, compression_y1)
        if active_end > active_start:
            fig.add_shape(
                type="rect", x0=x0, x1=x1, y0=active_start, y1=active_end,
                line=dict(color="#60a5fa", width=1),
                fillcolor="rgba(96,165,250,0.22)",
            )
        cracked_start = max(start, cracked_y0)
        cracked_end = min(end, cracked_y1)
        if cracked_end > cracked_start:
            fig.add_shape(
                type="rect", x0=x0, x1=x1, y0=cracked_start, y1=cracked_end,
                line=dict(color="#cbd5e1", width=1, dash="dot"),
                fillcolor="rgba(248,250,252,0.65)",
            )
        fig.add_shape(
            type="rect", x0=x0, x1=x1, y0=start, y1=end,
            line=dict(color="#0f172a", width=2), fillcolor="rgba(255,255,255,0)",
        )
    fig.add_shape(
        type="line", x0=0.10, x1=0.90, y0=dn_from_top, y1=dn_from_top,
        line=dict(color="#7c3aed", width=2, dash="dash"),
    )
    fig.add_annotation(
        x=0.92, y=dn_from_top, text="Trial d<sub>n</sub>", yshift=-15,
        showarrow=False, xanchor="left", font=dict(color="#6d28d9", size=10),
    )
    fig.add_annotation(
        x=0.40, y=(compression_y0 + compression_y1) / 2.0,
        text="Active concrete<br>compression region", showarrow=False,
        font=dict(color="#1d4ed8", size=11),
    )
    fig.add_annotation(
        x=0.40, y=(cracked_y0 + cracked_y1) / 2.0,
        text="Cracked concrete tension<br>inactive", showarrow=False,
        font=dict(color="#64748b", size=11),
    )

    colours = {"tension": "#dc2626", "compression": "#2563eb", "neutral": "#64748b"}
    symbols = {"tension": "circle", "compression": "square", "neutral": "diamond"}
    for index, layer in enumerate(layers):
        y = float(layer.get("depth_from_top_mm", 0.0) or 0.0)
        state = str(layer.get("state", "neutral") or "neutral")
        included = bool(layer.get("included", True))
        factor = float(layer.get("transformed_factor", 0.0) or 0.0)
        layer_id = str(layer.get("layer_id", f"L{index + 1}"))
        label = str(layer.get("label", layer_id))
        fig.add_trace(go.Scatter(
            x=[0.40], y=[y], mode="markers",
            marker=dict(
                size=12,
                color=colours.get(state, "#64748b"),
                symbol=symbols.get(state, "circle"),
                line=dict(color="#ffffff", width=1),
                opacity=1.0 if included else 0.4,
            ),
            name=f"{label}: {state}", hoverinfo="name", showlegend=False,
        ))
        factor_text = "omitted" if not included else f"{factor:.3g} A<sub>s</sub>"
        near_neutral_axis = abs(y - dn_from_top) < 0.08 * depth
        fig.add_annotation(
            x=0.66, y=y,
            text=f"{layer_id} — {state}<br>{factor_text}",
            yshift=18 if near_neutral_axis else 0,
            showarrow=False, xanchor="left", align="left",
            font=dict(color=colours.get(state, "#64748b"), size=9),
        )

    fig.add_annotation(
        x=0.50, y=1.08, xref="paper", yref="paper",
        text="n → trial d<sub>n</sub> → classify layers → transformed equilibrium",
        showarrow=False, font=dict(color="#0f172a", size=12),
    )
    fig.update_xaxes(range=[0.0, 1.35], visible=False, fixedrange=True)
    fig.update_yaxes(range=[depth * 1.04, -depth * 0.04], visible=False, fixedrange=True)
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=20, t=55, b=10),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        showlegend=False,
    )
    return fig
