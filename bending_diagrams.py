# bending_diagrams.py
import math
import os
import hashlib
import json
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
_BENDING_MAIN_FIGURE_CACHE_KEY = "_bending_main_stress_strain_figure_cache"
_BENDING_MAIN_FIGURE_SESSION_KEYS = (
    "shape_name",
    "sec_shape",
    "section_shape",
    "geometry_section_shape",
    "bending_sls_dn",
    "bending_sls_eps_top",
    "bending_sls_eps_bot",
    "bending_sls_kappa",
    "bending_sls_eps_s_outer",
    "eps_s_sls_bot",
    "eps_s_sls_bottom",
    "eps_s_bottom_sls",
)


def _bending_main_figure_fingerprint(
    state_dict,
    *,
    state_label,
    layout,
    moment_sign: str,
) -> str:
    """Fingerprint every state dependency read by the shared 3-panel builder."""
    session_inputs = {
        key: st.session_state.get(key) for key in _BENDING_MAIN_FIGURE_SESSION_KEYS
    }
    param_inputs = {
        "d": get_param("d", None),
        "sigma_s_sls": get_param("sigma_s_sls", None),
        "Ec": get_param("Ec", 30000.0),
        "fsy": get_param("fsy", 500.0),
        "Es": get_param("Es", 200000.0),
    }
    payload = {
        "version": 1,
        "state_dict": state_dict,
        "state_label": state_label,
        "layout": layout,
        "moment_sign": str(moment_sign or "positive"),
        "session_inputs": session_inputs,
        "param_inputs": param_inputs,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _plot_stress_strain_profiles(
    state_dict, state_label=None, layout=None, moment_sign: str = "positive"
):
    """Return the shared 3-panel figure, reusing only identical presentation state.

    The cache is deliberately session-local and single-entry. It owns no
    engineering result: all calculation state is resolved before this wrapper,
    and any dependency read by the shared figure builder invalidates the key.
    Dev mode bypasses caching so diagram consistency diagnostics still execute.
    """
    if layout is None or state_label is None or st.session_state.get("_dev_mode", False):
        return _stress_diagram_plot_stress_strain_profiles(
            state_dict,
            state_label=state_label,
            layout=layout,
            moment_sign=moment_sign,
        )

    fingerprint = _bending_main_figure_fingerprint(
        state_dict,
        state_label=state_label,
        layout=layout,
        moment_sign=moment_sign,
    )
    cached = st.session_state.get(_BENDING_MAIN_FIGURE_CACHE_KEY)
    if (
        isinstance(cached, dict)
        and cached.get("fingerprint") == fingerprint
        and cached.get("figure") is not None
    ):
        return cached["figure"]

    figure = _stress_diagram_plot_stress_strain_profiles(
        state_dict,
        state_label=state_label,
        layout=layout,
        moment_sign=moment_sign,
    )
    st.session_state[_BENDING_MAIN_FIGURE_CACHE_KEY] = {
        "fingerprint": fingerprint,
        "figure": figure,
    }
    return figure


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
        fc = float(get_param("fc", 40.0))
        fsy = float(get_param("fsy", 500.0))
        Ec = float(get_param("Ec", 30000.0))
        Es = float(get_param("Es", 200000.0))
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
