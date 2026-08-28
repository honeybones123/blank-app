"""MCFT strain and force-resolution diagram builders."""

from __future__ import annotations

import math

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import strain_display


MCFT_CHECK4_FACE_X_HALF = 1.15
# Base y-axis extent (fraction of depth) for the shared Check 4 beam-face frame.
# This now lives in the actual diagram builder rather than a page-shell monkeypatch.
MCFT_CHECK4_Y_PAD = 0.18
# The strain-profile view needs a little more true data-space headroom so it reads
# as zoomed out without changing the outer Streamlit/Plotly wrapper dimensions.
MCFT_CHECK4_STRAIN_Y_PAD = 0.25
# Pull display x toward the beam face (x=0) for the MCFT point/tick/labels only — not a calc change.
MCFT_CHECK4_EPSX_VISUAL_INWARD = 0.40
# Small compression cue at top (display x < 0); tension at bottom (x > 0). Keeps a shallow C→T line through x_vis.
MCFT_CHECK4_SCHEMATIC_TREND_COMP_TOP = 0.10
# Short horizontal stub at top fibre: strain magnitude as fraction of emax (display x, compression left).
MCFT_CHECK4_TOP_COMP_CUE_FRAC = 0.22
# Layout: shift Check 4 diagram down slightly (strain + force modes); extra band for force column headings.
MCFT_CHECK4_TOP_MARGIN_SHIFT_PX = 44
MCFT_CHECK4_TOP_MARGIN_FORCE_HEADINGS_PX = 92
# Force-resolution only: extra normalized depth above y=0 so the sketch sits lower; headings stay in top margin.
MCFT_CHECK4_FORCE_DIAGRAM_AXIS_TOP_GAP = 0.11


def _mcft_schematic_strain_trend_endpoints(x_vis: float) -> tuple[float, float]:
    """
    Indicative strain trend (display x): conventional sketch — compression left of the beam face at top,
    tension right at bottom, single crossing of x=0. Straight line through (x_vis, y_mid) at y=0.5
    so (x_top + x_bot) / 2 = x_vis. Teaching only — not from analysis.
    """
    m = MCFT_CHECK4_SCHEMATIC_TREND_COMP_TOP
    if x_vis < 0.0:
        m = max(m, -2.0 * x_vis + 0.05)
    x_top = -m
    x_bot = 2.0 * x_vis + m
    return x_top, x_bot


def _compute_mcft_strain_symmetric_half_range_eps_x(eps_x_mcft: float) -> float:
    """Half-width in strain units for symmetric framing (MCFT εx only; no flexural top/bot labels)."""
    emax = max(abs(eps_x_mcft), 1e-6)
    label_offset = 0.05 * emax
    left_extents: list[float] = []
    right_extents: list[float] = []
    if eps_x_mcft < 0.0:
        left_extents.append(abs(eps_x_mcft) + label_offset)
    elif eps_x_mcft > 0.0:
        right_extents.append(eps_x_mcft + label_offset)
    if eps_x_mcft < 0.0:
        label_x_mid = eps_x_mcft - label_offset
    else:
        label_x_mid = eps_x_mcft + label_offset
    callout_x = label_x_mid + (0.12 * emax if eps_x_mcft >= 0.0 else -0.12 * emax)
    if callout_x < 0.0:
        left_extents.append(abs(callout_x))
    else:
        right_extents.append(callout_x)
    L = max(left_extents) if left_extents else 0.0
    R = max(right_extents) if right_extents else 0.0
    half_core = max(L, R)
    if half_core < 1e-6:
        half_core = 1e-4
    span_sym = 2.0 * half_core
    pad = 0.20 * span_sym
    half_range = half_core + pad
    if half_range < 1e-4:
        half_range = 1e-4
    return half_range


def _add_mcft_shared_beam_face(fig: go.Figure, y_top: float, y_bot: float) -> None:
    """Single shared internal web face at x = 0 (same geometry in both Check 4 modes)."""
    fig.add_shape(
        type="line",
        x0=0,
        x1=0,
        y0=y_top,
        y1=y_bot,
        line=dict(width=4, color="black"),
        layer="below",
    )


def _apply_mcft_check4_layout(
    fig: go.Figure,
    height: int,
    y_top: float,
    y_bot: float,
    *,
    extra_top_margin: int = 0,
    extend_y_top_norm: float = 0.0,
    vertical_pad: float | None = None,
) -> None:
    """Identical frame for strain and force-resolution views (face registers at x = 0).

    extend_y_top_norm: extra headroom in normalized depth above y_top (force mode only), lowers sketch in the axes.
    vertical_pad: optional data-space zoom-out around the full-depth beam-face line.
    """
    pad = MCFT_CHECK4_Y_PAD if vertical_pad is None else max(0.0, float(vertical_pad))
    # Widen plot bounds in y only; beam face stays y_top..y_bot in data space (unchanged geometry).
    _y_top_axis = y_top - pad - max(0.0, float(extend_y_top_norm))
    y_axis_range = [y_bot + pad, _y_top_axis]
    fig.update_layout(
        width=640,
        height=int(height),
        margin=dict(t=16 + int(extra_top_margin), b=40, l=60, r=20),
        xaxis=dict(
            visible=False,
            range=[-MCFT_CHECK4_FACE_X_HALF, MCFT_CHECK4_FACE_X_HALF],
            fixedrange=True,
            zeroline=False,
            showgrid=False,
        ),
        yaxis=dict(
            visible=False,
            showticklabels=False,
            showgrid=False,
            autorange=False,
            range=y_axis_range,
            zeroline=False,
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )


def _mcft_bending_zone_mid_depths(
    eps_top_uls: float,
    eps_bot_uls: float,
    *,
    y_top: float = 0.0,
    y_bot: float = 1.0,
) -> tuple[float, float]:
    """
    Mid-depth of compression and tension zones from ULS linear strains (same NA as strain diagram).
    y is normalized depth: 0 = top, 1 = bottom (bending page convention).
    """
    eps_diff = eps_bot_uls - eps_top_uls
    if abs(eps_diff) < 1e-9:
        return 0.5 * (y_top + y_bot), 0.5 * (y_top + y_bot)

    y_na = y_top + (y_bot - y_top) * (0.0 - eps_top_uls) / eps_diff
    y_na = max(y_top, min(y_bot, y_na))

    if eps_top_uls < 0.0 and eps_bot_uls > 0.0:
        # Sagging: compression above NA, tension below
        y_mid_comp = 0.5 * (y_top + y_na)
        y_mid_ten = 0.5 * (y_na + y_bot)
        return y_mid_comp, y_mid_ten
    if eps_top_uls > 0.0 and eps_bot_uls < 0.0:
        # Hogging: tension above NA, compression below
        y_mid_ten = 0.5 * (y_top + y_na)
        y_mid_comp = 0.5 * (y_na + y_bot)
        return y_mid_comp, y_mid_ten
    # Same sign (no NA in section): schematic placement
    if eps_top_uls < 0.0:
        return 0.5 * (y_top + y_bot), 0.85 * y_bot + 0.15 * y_top
    return 0.15 * y_bot + 0.85 * y_top, 0.5 * (y_top + y_bot)


def _mcft_force_resultant_depths_norm(
    *,
    D_mm: float,
    c_mm: float,
    gamma: float,
    tension_steel_y_from_top_mm: float,
    moment_sign: str,
    y_top: float = 0.0,
    y_bot: float = 1.0,
) -> tuple[float, float] | None:
    """
    Normalized depths (0 = top, 1 = bottom) for illustrative C and T on the Check 4 force diagram.

    C: centroid of the equivalent rectangular compression block (mid-depth of the block), using
    block depth a = gamma * c with c measured from the compression face (same convention as
    bending_core._stress_strain_state ULS).

    T: depth to the tensile steel centroid from the top fibre (d_plot from _stress_strain_state).

    Returns None if geometry is unusable; caller should fall back to _mcft_bending_zone_mid_depths.
    """
    D = float(D_mm)
    if D <= 1e-6:
        return None
    c = max(0.0, float(c_mm))
    g = float(gamma)
    if g <= 1e-9:
        return None
    a = min(g * c, D - 1e-6)
    if a <= 1e-6:
        return None

    sign = str(moment_sign or "positive").strip().lower()
    hogging = sign in ("negative", "hogging")

    if not hogging:
        y_c = 0.5 * a / D
    else:
        y_c = 1.0 - 0.5 * a / D

    y_t = float(tension_steel_y_from_top_mm) / D
    y_t = max(y_top, min(y_bot, y_t))

    margin = 0.018
    y_c = max(y_top + margin, min(y_bot - margin, y_c))
    y_t = max(y_top + margin, min(y_bot - margin, y_t))
    return y_c, y_t


def _add_mcft_force_resolution_overlay(
    fig: go.Figure,
    *,
    y_mid_compression: float,
    y_mid_tension: float,
    theta_deg: float | None = None,
) -> None:
    """
    Illustrative internal forces on the shared ε=0 beam face (Check 4).
    Mixed coordinates: schematic x in [-1, 1] for C/T; legacy 0–10 sketch mapping for other cues.
    Depth y in [0, 1] (0 = top).

    Diagonal compression strut plus flange C/T resultants; N*, V*, M* cues on the left.
    Adds paper-space column headings (section actions vs internal resolution); does not move force geometry.
    """
    ox = lambda v: (float(v) - 5.0) / 5.0
    oy = lambda v: 1.0 - (float(v) / 10.0)
    y_to_legacy_y = lambda y_norm: 10.0 * (1.0 - float(y_norm))

    lo_y = min(y_mid_compression, y_mid_tension)
    hi_y = max(y_mid_compression, y_mid_tension)
    mid_y = 0.5 * (lo_y + hi_y)
    # Same depth as strut head / internal face (y_head) — legacy sketch y for N* / V* alignment.
    _legacy_y_face_mid = y_to_legacy_y(mid_y)

    def _ann_arrow(
        ax0: float,
        ay0: float,
        x0: float,
        y0: float,
        *,
        color: str = "rgba(45,45,45,0.88)",
        width: float = 1.35,
        xref: str = "x",
        yref: str = "y",
    ) -> None:
        fig.add_annotation(
            x=x0,
            y=y0,
            ax=ax0,
            ay=ay0,
            xref=xref,
            yref=yref,
            axref=xref,
            ayref=yref,
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.65,
            arrowwidth=width,
            arrowcolor=color,
            standoff=0,
            startstandoff=0,
        )

    def _ann_arrow_legacy(
        ax0: float,
        ay0: float,
        x0: float,
        y0: float,
        *,
        color: str = "rgba(45,45,45,0.88)",
        width: float = 1.35,
    ) -> None:
        _ann_arrow(ox(ax0), oy(ay0), ox(x0), oy(y0), color=color, width=width)

    y_face_hi = lo_y + 0.04
    y_face_lo = hi_y - 0.04
    if y_face_hi >= y_face_lo:
        y_face_hi, y_face_lo = mid_y - 0.18, mid_y + 0.18
    # N* — horizontal axial left of V*, toward the face (same height as red V_eq cue on the right)
    _n_tail_x, _n_head_x = 1.05, 2.18
    _ann_arrow_legacy(_n_tail_x, _legacy_y_face_mid, _n_head_x, _legacy_y_face_mid)
    fig.add_annotation(
        x=ox(0.5 * (_n_tail_x + _n_head_x)),
        y=oy(_legacy_y_face_mid + 0.06),
        text="N*",
        showarrow=False,
        yanchor="bottom",
        font=dict(size=11, color="rgba(35,35,35,0.92)"),
    )

    # M* — semicircular internal couple (left of N* / V*; CCW with C into face, T outward at tension level)
    r_m = max(0.085, 0.5 * (hi_y - lo_y))
    xc_m = -0.58
    mid_m = mid_y
    moment_arc_x: list[float] = []
    moment_arc_y: list[float] = []
    # Sweep 3π/2 → π/2: arc runs compression level → bulge left → tension level (counterclockwise couple).
    for i in range(33):
        t = 1.5 * math.pi - math.pi * (i / 32.0)
        moment_arc_x.append(xc_m + r_m * math.cos(t))
        moment_arc_y.append(mid_m + r_m * math.sin(t))
    fig.add_trace(
        go.Scatter(
            x=moment_arc_x,
            y=moment_arc_y,
            mode="lines",
            line=dict(color="rgba(45,45,45,0.9)", width=1.85),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_annotation(
        x=max(-0.92, xc_m - r_m - 0.06),
        y=mid_m,
        xref="x",
        yref="y",
        text="M*",
        showarrow=False,
        font=dict(size=11, color="rgba(35,35,35,0.92)"),
    )

    # V* geometry (norm x/y) — defined before strut so the diagonal can be shifted to intersect the vertical V*.
    _half_y_v = 0.058
    _vstar_leg_x = 3.12
    _vstar_xn = ox(_vstar_leg_x)
    _vstar_y_axis = mid_y - 0.048

    # Diagonal compression strut: top-right near C → face at mid-depth at MCFT θ (inward; not toward T).
    _th = float(theta_deg) if theta_deg is not None else 36.0
    _th = max(1.0, min(89.0, _th))
    theta_r = math.radians(_th)
    y_t = float(y_mid_tension)
    y_c = float(y_mid_compression)
    tan_t = math.tan(theta_r)
    if abs(tan_t) < 1e-5:
        tan_t = 1e-5

    x_head, y_head = 0.0, float(mid_y)
    if y_c < y_t:
        y_tail = float(y_c)
        d_run = max(y_head - y_tail, 1e-6)
        x_tail = d_run / tan_t
        if x_tail > 0.92:
            x_tail = 0.92
            y_tail = y_head - x_tail * tan_t
        if y_tail > y_c:
            y_tail = float(y_c)
            x_tail = max((y_head - y_tail) / tan_t, 1e-6)
    else:
        y_tail = float(y_c)
        d_run = max(y_tail - y_head, 1e-6)
        x_tail = d_run / tan_t
        if x_tail > 0.92:
            x_tail = 0.92
            y_tail = y_head + x_tail * tan_t
        if y_tail < y_c:
            y_tail = float(y_c)
            x_tail = max((y_tail - y_head) / tan_t, 1e-6)

    _strut_len_scale = 0.24
    x_tail = x_head + _strut_len_scale * (x_tail - x_head)
    y_tail = y_head + _strut_len_scale * (y_tail - y_head)

    _strut_h_cc_shift = 0.042
    x_head = x_head + _strut_h_cc_shift
    x_tail = x_tail + _strut_h_cc_shift
    # Slide strut: inboard end on V* — diagonal crosses shear.
    _dx_strut_to_vstar = _vstar_xn - x_head
    x_head_strut = x_head + _dx_strut_to_vstar
    x_tail_strut = x_tail + _dx_strut_to_vstar

    # θ label: mid-depth of beam (mid_y); x kept near diagonal strut.
    _xm_strut = 0.5 * (x_tail_strut + x_head_strut)
    _tsx = x_head_strut - x_tail_strut
    _tsy = y_head - y_tail
    _tsl = math.hypot(_tsx, _tsy) or 1.0
    _tnx = _tsy / _tsl
    _ax_ang = _xm_strut + 0.10 * _tnx + 0.004
    _ay_ang = float(mid_y) - 0.012
    _ax_ang = max(-0.90, min(0.92, _ax_ang))
    _ay_ang = max(0.04, min(0.96, _ay_ang))

    # Diagonal strut: dark translucent line.
    _strut_diag_line = "rgba(28,28,28,0.30)"

    fig.add_annotation(
        x=x_head_strut,
        y=y_head,
        ax=x_tail_strut,
        ay=y_tail,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=0.72,
        arrowwidth=1.55,
        arrowcolor=_strut_diag_line,
        standoff=0,
        startstandoff=0,
    )

    # MCFT θ — dotted segment just under label (trace drawn first so text stays on top).
    _theta_dot_y = _ay_ang + 0.019
    fig.add_trace(
        go.Scatter(
            x=[_ax_ang - 0.195, _ax_ang + 0.058],
            y=[_theta_dot_y, _theta_dot_y],
            mode="lines",
            line=dict(color="rgba(55,55,55,0.82)", width=1.1, dash="dot"),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_annotation(
        x=_ax_ang,
        y=_ay_ang,
        xref="x",
        yref="y",
        text=f"θ = {_th:.1f}°",
        showarrow=False,
        xanchor="center",
        yanchor="middle",
        font=dict(size=9, color="rgba(55,55,55,0.92)"),
    )

    # C — horizontal into the face at compression resultant (stress-block centroid when section data supplied)
    _ann_arrow(
        0.88,
        y_mid_compression,
        0.06,
        y_mid_compression,
        color="rgba(180,55,55,0.88)",
        width=1.25,
    )
    fig.add_annotation(
        x=0.16,
        y=y_mid_compression + 0.07,
        xref="x",
        yref="y",
        text="C = −|M*/d_v| + 0.5N* + 0.5V_eq·cot θ",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=10, color="rgba(180,55,55,0.82)"),
        bgcolor="rgba(255,255,255,0.68)",
    )

    # V* — vertical shear (x/y defined above with strut so they intersect).
    _ann_arrow(
        _vstar_xn,
        _vstar_y_axis - _half_y_v,
        _vstar_xn,
        _vstar_y_axis + _half_y_v,
        color="rgba(45,45,45,0.88)",
        width=1.35,
    )
    fig.add_annotation(
        x=min(0.92, _vstar_xn + 0.012),
        y=mid_y - 0.082,
        xref="x",
        yref="y",
        text="V*",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=11, color="rgba(35,35,35,0.92)"),
    )

    # T — horizontal outward at tensile steel centroid (when section data supplied)
    _ann_arrow(
        0.06,
        y_mid_tension,
        0.88,
        y_mid_tension,
        color="rgba(30,90,180,0.88)",
        width=1.25,
    )
    fig.add_annotation(
        x=0.16,
        y=y_mid_tension + 0.075,
        xref="x",
        yref="y",
        text="T = |M*/d_v| + 0.5N* + 0.5V_eq·cot θ",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=10, color="rgba(30,90,180,0.82)"),
        bgcolor="rgba(255,255,255,0.68)",
    )

    # Tangential arrowhead at the arc start (lo_y chord end); flipped to point opposite to CCW sweep.
    if len(moment_arc_x) >= 2:
        xe, ye = moment_arc_x[0], moment_arc_y[0]
        xp, yp = moment_arc_x[1], moment_arc_y[1]
        tx, ty = xp - xe, yp - ye
        tlen = math.hypot(tx, ty) or 1.0
        tx, ty = tx / tlen, ty / tlen
        ah = 0.038
        fig.add_annotation(
            x=xe,
            y=ye,
            ax=xe + ah * tx,
            ay=ye + ah * ty,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.75,
            arrowwidth=1.65,
            arrowcolor="rgba(45,45,45,0.92)",
            standoff=0,
            startstandoff=0,
        )

    # Mid-depth note: two lines, left edge just right of the vertical face (C/T arrows at x ≈ 0.06).
    fig.add_annotation(
        xref="x",
        yref="y",
        x=0.10,
        y=mid_y,
        xanchor="left",
        yanchor="middle",
        text="Axial, moment and shear effects are resolved into flange forces<br>shared between the top and bottom flanges.",
        showarrow=False,
        font=dict(size=8, color="rgba(95,95,95,0.92)"),
    )

    # Column headings (paper coords — no change to data positions of forces / strut / arcs)
    _hdr_title = "rgba(35,35,35,0.96)"
    _hdr_sub = "rgba(105,105,105,0.95)"
    # Plotly: positive yshift moves the annotation up (toward the top of the figure).
    _hdr_y_title_px = 6
    _hdr_y_sub_px = -14
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.30,
        y=1.0,
        xanchor="center",
        yanchor="top",
        yshift=_hdr_y_title_px,
        text="<b>Section actions</b>",
        showarrow=False,
        font=dict(size=12, color=_hdr_title),
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.30,
        y=1.0,
        xanchor="center",
        yanchor="top",
        yshift=_hdr_y_sub_px,
        text="Design actions at the section",
        showarrow=False,
        font=dict(size=9, color=_hdr_sub),
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.74,
        y=1.0,
        xanchor="center",
        yanchor="top",
        yshift=_hdr_y_title_px,
        text="<b>Internal force resolution</b>",
        showarrow=False,
        font=dict(size=12, color=_hdr_title),
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.74,
        y=1.0,
        xanchor="center",
        yanchor="top",
        yshift=_hdr_y_sub_px,
        text="Equivalent internal resisting forces<br>on the beam face",
        showarrow=False,
        font=dict(size=9, color=_hdr_sub),
    )


def make_mcft_longitudinal_strain_profile_fig(
    eps_top_uls: float,
    eps_x_mcft: float,
    eps_bot_uls: float,
    title: str = "Longitudinal strain profile",
    height: int = 430,
    *,
    force_resolution: bool = False,
    force_section_D_mm: float | None = None,
    force_section_c_mm: float | None = None,
    force_section_gamma: float | None = None,
    force_tension_steel_y_from_top_mm: float | None = None,
    force_moment_sign: str = "positive",
    force_theta_deg: float | None = None,
):
    """
    Check 4 MCFT longitudinal strain: mid-depth ε_x at the internal beam face (primary); short red stub
    at top (compression), horizontal cue at bottom from the face to the grey dashed trend endpoint (intersection),
    mid-depth tick for ε_x; optional faint grey dashed indicative trend. Same shared beam face as the
    force-resolution toggle.

    AS 3600 sign convention: ε < 0 = compression (red, left of face), ε > 0 = tension (blue, right).

    Args:
        eps_top_uls: Fallback for force diagram C/T depths when section geometry kwargs are omitted.
        eps_x_mcft: Governing longitudinal strain from MCFT (AS 3600 Cl. 8.2.4.2.2).
        eps_bot_uls: Fallback for force diagram C/T depths when section geometry kwargs are omitted.
        force_resolution: If True, show illustrative internal forces on the same ε=0 beam face.
        force_section_D_mm, force_section_c_mm, force_section_gamma, force_tension_steel_y_from_top_mm,
        force_moment_sign: Optional section data (same convention as bending_core._stress_strain_state ULS)
            so C is drawn at the rectangular stress-block centroid and T at the tensile steel centroid.
            If any required piece is missing, C/T fall back to mid-depths from eps_top_uls / eps_bot_uls.
        force_theta_deg: Strut angle θ (degrees) for the red diagonal strut; defaults in the overlay if omitted.
    """
    def _safe(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    # AS 3600 sign convention: compression negative, tension positive
    eps_top_uls = _safe(eps_top_uls)
    eps_x_mcft = _safe(eps_x_mcft)
    eps_bot_uls = _safe(eps_bot_uls)

    # Depth coordinates: top at y=0.0, bottom at y=1.0 (normalized)
    # With autorange="reversed", y=0 appears at top, y=1 appears at bottom
    y_top = 0.0
    y_mid = 0.5
    y_bot = 1.0

    fig = go.Figure()

    _add_mcft_shared_beam_face(fig, y_top, y_bot)

    if force_resolution:
        y_mid_comp, y_mid_ten = _mcft_bending_zone_mid_depths(
            eps_top_uls,
            eps_bot_uls,
            y_top=y_top,
            y_bot=y_bot,
        )
        try:
            Df = float(force_section_D_mm) if force_section_D_mm is not None else None
            cf = float(force_section_c_mm) if force_section_c_mm is not None else None
            gf = float(force_section_gamma) if force_section_gamma is not None else None
            d_steel = (
                float(force_tension_steel_y_from_top_mm)
                if force_tension_steel_y_from_top_mm is not None
                else None
            )
            if Df is not None and cf is not None and gf is not None and d_steel is not None:
                res = _mcft_force_resultant_depths_norm(
                    D_mm=Df,
                    c_mm=cf,
                    gamma=gf,
                    tension_steel_y_from_top_mm=d_steel,
                    moment_sign=force_moment_sign,
                    y_top=y_top,
                    y_bot=y_bot,
                )
                if res is not None:
                    y_mid_comp, y_mid_ten = res
        except Exception:
            pass
        _add_mcft_force_resolution_overlay(
            fig,
            y_mid_compression=y_mid_comp,
            y_mid_tension=y_mid_ten,
            theta_deg=force_theta_deg,
        )
    else:
        half_range_eps = _compute_mcft_strain_symmetric_half_range_eps_x(eps_x_mcft)
        sx_scale = MCFT_CHECK4_FACE_X_HALF / half_range_eps

        def sx(eps: float) -> float:
            return float(eps) * sx_scale

        emax_temp = max(abs(eps_x_mcft), 1e-6)
        color_mid_tick = "red" if eps_x_mcft < 0 else "blue"
        vis_scale = 1.0 - MCFT_CHECK4_EPSX_VISUAL_INWARD
        x_vis = sx(eps_x_mcft) * vis_scale

        # Indicative strain trend (teaching only): compression above / tension below ε=0, through (x_vis, y_mid).
        _x_trend_top, _x_trend_bot = _mcft_schematic_strain_trend_endpoints(x_vis)
        fig.add_trace(
            go.Scatter(
                x=[_x_trend_top, _x_trend_bot],
                y=[y_top, y_bot],
                mode="lines",
                line=dict(
                    width=0.85,
                    color="rgba(120,120,120,0.32)",
                    dash="dash",
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        # Reference cue: compression at top fibre (short stub left of beam face — not a full profile).
        x_top_comp = sx(-MCFT_CHECK4_TOP_COMP_CUE_FRAC * emax_temp) * vis_scale
        x_top_comp = max(x_top_comp, -0.88 * MCFT_CHECK4_FACE_X_HALF)
        fig.add_shape(
            type="line",
            x0=0,
            y0=y_top,
            x1=x_top_comp,
            y1=y_top,
            line=dict(width=1.35, color="rgba(200,50,50,0.9)"),
            layer="below",
        )

        # Bottom fibre cue: beam face → same x as dashed schematic at y_bot (intersects the dashed line).
        x_end_bot = float(_x_trend_bot)
        bot_cue_color = (
            "rgba(30,100,200,0.55)"
            if x_end_bot > 1e-9
            else ("rgba(200,50,50,0.9)" if x_end_bot < -1e-9 else "rgba(90,90,90,0.75)")
        )
        if abs(x_end_bot) > 1e-9:
            _bot_cue_width = 1.0 if x_end_bot > 1e-9 else 1.35
            fig.add_shape(
                type="line",
                x0=0,
                y0=y_bot,
                x1=x_end_bot,
                y1=y_bot,
                line=dict(width=_bot_cue_width, color=bot_cue_color),
                layer="above",
            )

        # Mid-depth: strain level used for MCFT (beam face → ε_x); matches point colour (blue tension / red compression).
        fig.add_shape(
            type="line",
            x0=0,
            y0=y_mid,
            x1=x_vis,
            y1=y_mid,
            line=dict(
                color=color_mid_tick,
                width=1.55,
            ),
            layer="below",
        )
        fig.add_trace(
            go.Scatter(
                x=[x_vis],
                y=[y_mid],
                mode="markers",
                marker=dict(size=20, color=color_mid_tick, line=dict(width=2.4, color="black")),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        emax = max(abs(eps_x_mcft), 1e-6)
        label_offset = 0.05 * emax
        if eps_x_mcft < 0.0:
            label_x_mid = eps_x_mcft - label_offset
            xanchor_mid = "right"
            state_mid = "(compression)"
        else:
            label_x_mid = eps_x_mcft + label_offset
            xanchor_mid = "left"
            state_mid = "(tension)"
        fig.add_annotation(
            x=sx(label_x_mid) * vis_scale + 0.11,
            y=y_mid + 0.06 * (y_bot - y_top),
            text=f"ε<sub>x</sub> = {eps_x_mcft:.5f}<br><span style='font-size:11px'>mid-depth (MCFT)</span><br><span style='font-size:10px'>{state_mid}</span>",
            showarrow=False,
            font=dict(size=12, color=color_mid_tick),
            xanchor=xanchor_mid,
            yshift=0,
            bgcolor="rgba(255,255,255,0.85)",
        )
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.035,
            text="Indicative strain trend only — not a calculated full-depth strain profile.",
            showarrow=False,
            font=dict(size=9, color="rgba(95,95,95,0.98)"),
            xanchor="center",
            yanchor="bottom",
        )

    _apply_mcft_check4_layout(
        fig,
        height,
        y_top,
        y_bot,
        extra_top_margin=MCFT_CHECK4_TOP_MARGIN_SHIFT_PX
        + (MCFT_CHECK4_TOP_MARGIN_FORCE_HEADINGS_PX if force_resolution else 0),
        extend_y_top_norm=MCFT_CHECK4_FORCE_DIAGRAM_AXIS_TOP_GAP if force_resolution else 0.0,
        vertical_pad=MCFT_CHECK4_Y_PAD if force_resolution else MCFT_CHECK4_STRAIN_Y_PAD,
    )
    return fig


def plot_shear_step4_middepth_strain_diagram(
    b_mm: float,
    D_mm: float,
    eps_x: float,
    *,
    title: str = "Mid-depth longitudinal strain",
):
    """
    Bending-style strain diagram for Step 4.
    Shows section rectangle + strain panel with linear profile and εx at mid-depth.
    """
    b = float(b_mm)
    D = float(D_mm)
    epsx = float(eps_x)

    # Interpretation based on sign
    if epsx >= 0:
        strain_state = "tension at mid-depth"
    else:
        strain_state = "compression at mid-depth"

    # Create subplots: Section (left) and Strain (right)
    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.4, 0.6],
        horizontal_spacing=0.15,
        subplot_titles=["Section", "Strain"],
    )

    # =====================================================
    # 1) SECTION PANEL (left)
    # =====================================================
    # Outer section rectangle
    fig.add_shape(
        type="rect",
        x0=0, y0=0, x1=b, y1=D,
        line=dict(width=3, color="black"),
        fillcolor="white",
        layer="below",
        row=1, col=1,
    )

    # Mid-depth line (y = D/2) - dashed
    y_mid = 0.5 * D
    fig.add_shape(
        type="line",
        x0=0, y0=y_mid, x1=b, y1=y_mid,
        line=dict(width=2, color="black", dash="dash"),
        layer="above",
        row=1, col=1,
    )

    # Small marker point at mid-depth (center)
    fig.add_trace(
        go.Scatter(
            x=[0.5 * b],
            y=[y_mid],
            mode="markers",
            marker=dict(size=10, color="black"),
            hoverinfo="skip",
            showlegend=False,
        ),
        row=1, col=1,
    )

    # Section axes setup
    fig.update_xaxes(visible=False, range=[-0.08*b, 1.08*b], row=1, col=1)
    fig.update_yaxes(visible=False, range=[-0.06*D, 1.06*D], scaleanchor="x1", scaleratio=1, row=1, col=1)

    # =====================================================
    # 2) STRAIN PANEL (right) - matching bending style
    # =====================================================
    panel_x_center = 0.5
    half_w = 0.35
    eps_max = max(abs(epsx), 1e-4) * 1.3

    def strain_to_x(eps_display: float) -> float:
        """Map display ε (compression < 0 left, tension > 0 right) → panel x."""
        return strain_display.strain_display_to_panel_x(
            eps_display,
            panel_x_center=panel_x_center,
            half_w=half_w,
            eps_scale_max=eps_max,
        )

    x_mid = panel_x_center  # neutral axis (ε = 0)
    x_epsx = strain_to_x(epsx)

    # Vertical depth line at ε = 0 (strain axis)
    fig.add_shape(
        type="line",
        x0=panel_x_center,
        y0=0,
        x1=panel_x_center,
        y1=D,
        line=dict(color="black", width=1.0),
        row=1, col=2,
    )

    # Simplified linear strain profile: assume linear from top to bottom through mid-depth
    # For visualization, create a reasonable profile that passes through εx at mid-depth
    # Linear interpolation: eps = eps_top + (eps_bot - eps_top) * (y / D)
    # At y = D/2: epsx = eps_top + (eps_bot - eps_top) * 0.5
    # Solve: eps_top = 2*epsx - eps_bot
    # Use reasonable estimates for visualization
    if epsx >= 0:
        # Tension at mid-depth: assume less tension at top, more at bottom
        eps_bot_est = epsx * 1.8
        eps_top_est = 2.0 * epsx - eps_bot_est
    else:
        # Compression at mid-depth: assume more compression at top, less at bottom
        eps_bot_est = epsx * 0.2
        eps_top_est = 2.0 * epsx - eps_bot_est

    x_top = strain_to_x(eps_top_est)
    x_bot = strain_to_x(eps_bot_est)

    # Strain line (top → mid → bottom)
    fig.add_trace(
        go.Scatter(
            x=[x_top, x_epsx, x_bot],
            y=[0, y_mid, D],
            mode="lines",
            line=dict(color="black", width=1.5),
            hoverinfo="skip",
            showlegend=False,
        ),
        row=1, col=2,
    )

    # Mid-depth horizontal line and label (ε_x) - the key value
    tick_color = "blue" if epsx >= 0.0 else "red"
    fig.add_shape(
        type="line",
        x0=panel_x_center,
        y0=y_mid,
        x1=x_epsx,
        y1=y_mid,
        line=dict(color=tick_color, width=2.0),
        row=1, col=2,
    )

    label_x, xanchor = strain_display.strain_label_anchor_display(
        epsx, x_epsx, offset=0.02
    )

    fig.add_annotation(
        x=label_x,
        y=y_mid,
        text=rf"$\varepsilon_x$ = {epsx:.5f}<br><span style='font-size:11px'>{strain_state}</span>",
        showarrow=False,
        font=dict(size=12, color=tick_color),
        yshift=0,
        xanchor=xanchor,
        row=1, col=2,
    )

    # Strain panel axes setup
    fig.update_xaxes(visible=False, range=[0.0, 1.0], row=1, col=2)
    fig.update_yaxes(visible=False, range=[-0.06*D, 1.06*D], scaleanchor="x2", scaleratio=1, row=1, col=2)

    # AS 3600 strain limits note (small, non-dominant)
    fig.add_annotation(
        x=0.5,
        y=-0.12 * D,
        xref="x2", yref="y2",
        text=r"AS 3600 limits: $-2.0\times10^{-4} \le \varepsilon_x \le 3.0\times10^{-3}$",
        showarrow=False,
        font=dict(size=11, color="rgba(60,60,60,0.85)"),
        row=1, col=2,
    )

    # Overall layout
    fig.update_layout(
        margin=dict(l=6, r=6, t=40, b=6),
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig


def plot_step4_mcft_strain_diagram(
    D_mm: float,
    eps_mid: float,
    eps_top: float,
    eps_bot: float,
    *,
    title: str = "Longitudinal strain profile",
):
    """
    Longitudinal strain profile for Step 4 MCFT (display convention: compression ε < 0 left, tension ε > 0 right).
    """
    D = float(D_mm)
    e_mid = float(eps_mid)
    e_top = float(eps_top)
    e_bot = float(eps_bot)

    # y=0 top, y=D bottom
    y_top, y_mid, y_bot = 0.0, 0.5 * D, D

    # Build a simple linear profile line through the three points
    fig = go.Figure()

    # Vertical ε=0 axis (explicitly at x=0)
    fig.add_shape(
        type="line",
        x0=0, x1=0,
        y0=-0.05*D, y1=1.05*D,
        line=dict(width=4, color="black"),
        layer="below",
    )

    # Profile line (top -> mid -> bottom)
    fig.add_trace(go.Scatter(
        x=[e_top, e_mid, e_bot],
        y=[y_top, y_mid, y_bot],
        mode="lines+markers",
        line=dict(width=3, color="black"),
        marker=dict(size=12, color="black"),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Horizontal lines from zero axis to strain values (display AS 3600 sense)
    emax = max(abs(e_top), abs(e_mid), abs(e_bot), 1e-6)
    offset = 0.02 * emax

    # Top strain horizontal line and label
    color_top = strain_display.strain_color_display(e_top)
    fig.add_shape(
        type="line",
        x0=0, y0=y_top, x1=e_top, y1=y_top,
        line=dict(color=color_top, width=2.0),
    )
    label_x_top, xanchor_top = strain_display.strain_label_anchor_display(
        e_top, e_top, offset=offset
    )
    state_top = "(compression)" if e_top < 0.0 else "(tension)"
    fig.add_annotation(
        x=label_x_top, y=y_top,
        text=f"ε<sub>top</sub> = {e_top:.5f}<br><span style='font-size:10px'>{state_top}</span>",
        showarrow=False,
        font=dict(size=12, color=color_top),
        xanchor=xanchor_top,
        yshift=-12,
        bgcolor="rgba(255,255,255,0.7)",
    )
    
    # Mid-depth strain horizontal line and label (ε_x) - highlighted
    color_mid = strain_display.strain_color_display(e_mid)
    fig.add_shape(
        type="line",
        x0=0, y0=y_mid, x1=e_mid, y1=y_mid,
        line=dict(color=color_mid, width=2.0),
    )
    label_x_mid, xanchor_mid = strain_display.strain_label_anchor_display(
        e_mid, e_mid, offset=offset
    )
    state_mid = "(compression)" if e_mid < 0.0 else "(tension)"
    fig.add_annotation(
        x=label_x_mid, y=y_mid,
        text=f"ε<sub>x</sub> = {e_mid:.5f}<br><span style='font-size:11px'>mid-depth (MCFT)</span><br><span style='font-size:10px'>{state_mid}</span>",
        showarrow=False,
        font=dict(size=12, color=color_mid),
        xanchor=xanchor_mid,
        yshift=0,
        bgcolor="rgba(255,255,255,0.7)",
    )
    
    # Bottom strain horizontal line and label
    color_bot = strain_display.strain_color_display(e_bot)
    fig.add_shape(
        type="line",
        x0=0, y0=y_bot, x1=e_bot, y1=y_bot,
        line=dict(color=color_bot, width=2.0),
    )
    label_x_bot, xanchor_bot = strain_display.strain_label_anchor_display(
        e_bot, e_bot, offset=offset
    )
    state_bot = "(compression)" if e_bot < 0.0 else "(tension)"
    fig.add_annotation(
        x=label_x_bot, y=y_bot,
        text=f"ε<sub>bot</sub> = {e_bot:.5f}<br><span style='font-size:10px'>{state_bot}</span>",
        showarrow=False,
        font=dict(size=12, color=color_bot),
        xanchor=xanchor_bot,
        yshift=12,
        bgcolor="rgba(255,255,255,0.7)",
    )

    # Title
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.06,
        text=f"<b>{title}</b>",
        showarrow=False,
        font=dict(size=18, color="rgba(70,70,90,0.85)"),
        align="center",
    )

    # Subtitle (small)
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.02,
        text="<span style='font-size:12px'>ε<sub>x</sub> evaluated at mid-depth (MCFT – AS 3600 Cl. 8.2.4.2.2)</span>",
        showarrow=False,
        font=dict(size=12, color="rgba(70,70,90,0.75)"),
        align="center",
    )

    # AS 3600 limits annotation (context only, no bounding boxes)
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.98,
        text="<span style='font-size:11px'>AS 3600 limits: −2.0×10⁻⁴ ≤ ε<sub>x</sub> ≤ 3.0×10⁻³</span>",
        showarrow=False,
        font=dict(size=11, color="rgba(70,70,90,0.7)"),
        align="center",
    )

    # Axes formatting: ensure x=0 is always visible
    xmin = min(e_top, e_mid, e_bot, 0.0)
    xmax = max(e_top, e_mid, e_bot, 0.0)
    pad = 0.15 * (xmax - xmin if (xmax - xmin) > 0 else 1.0e-4)
    
    fig.update_xaxes(visible=False, range=[xmin - pad, xmax + pad])
    fig.update_yaxes(visible=False, range=[-0.10*D, 1.25*D])

    fig.update_layout(
        margin=dict(l=10, r=10, t=80, b=10),
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig


def make_step4_longitudinal_strain_diagram(
    D_mm: float,
    eps_x: float,
    eps_top: float,
    eps_bot: float,
    eps_min: float = -2.0e-4,
    eps_max: float = 3.0e-3,
    height_px: int = 540,
):
    """
    Step 4 diagram: longitudinal strain profile for MCFT.
    Display: compression ε < 0 left, tension ε > 0 right (same as bending strain panel).
    """
    # Guardrails
    def _safe(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    D = float(D_mm)
    eps_x = _safe(eps_x)
    eps_top = _safe(eps_top)
    eps_bot = _safe(eps_bot)

    # y-coordinates: top, mid, bottom (real depth coordinates like bending)
    y_top = 0.0
    y_mid = 0.5 * D
    y_bot = D

    # Build figure
    fig = go.Figure()

    # Vertical reference axis (zero strain line, like bending strain panel)
    fig.add_shape(
        type="line",
        x0=0, y0=y_top - 0.05*D, x1=0, y1=y_bot + 0.05*D,
        line=dict(width=3, color="black"),
        layer="below",
    )

    # Strain profile line: connect (eps_top,y_top) -> (eps_x,y_mid) -> (eps_bot,y_bot)
    # This is the main strain distribution line (like bending strain panel)
    # Shows the linear strain profile from top to bottom
    fig.add_trace(go.Scatter(
        x=[eps_top, eps_x, eps_bot],
        y=[y_top, y_mid, y_bot],
        mode="lines+markers",
        line=dict(width=3.5, color="black"),
        marker=dict(size=12, color="black"),
        hoverinfo="skip",
        showlegend=False,
    ))

    lo = 0.02 * max(abs(eps_top), abs(eps_x), abs(eps_bot), 1e-6)
    color_top = strain_display.strain_color_display(eps_top)
    color_mid = strain_display.strain_color_display(eps_x)
    color_bot = strain_display.strain_color_display(eps_bot)

    # Horizontal "ticks" from zero axis to each strain value (display convention)
    fig.add_shape(
        type="line",
        x0=0, y0=y_top, x1=eps_top, y1=y_top,
        line=dict(color=color_top, width=2.0),
    )
    fig.add_shape(
        type="line",
        x0=0, y0=y_mid, x1=eps_x, y1=y_mid,
        line=dict(color=color_mid, width=2.0),
    )
    fig.add_shape(
        type="line",
        x0=0, y0=y_bot, x1=eps_bot, y1=y_bot,
        line=dict(color=color_bot, width=2.0),
    )

    label_x_top, xanchor_top = strain_display.strain_label_anchor_display(
        eps_top, eps_top, offset=lo
    )
    fig.add_annotation(
        x=label_x_top, y=y_top,
        text=f"ε<sub>top</sub> = {eps_top:.5f}",
        showarrow=False,
        font=dict(size=12, color=color_top),
        xanchor=xanchor_top,
        yshift=-10,
    )

    label_x_mid, xanchor_mid = strain_display.strain_label_anchor_display(
        eps_x, eps_x, offset=lo
    )
    fig.add_annotation(
        x=label_x_mid, y=y_mid,
        text=f"ε<sub>x</sub> = {eps_x:.5f}<br><span style='font-size:11px'>mid-depth (MCFT)</span>",
        showarrow=False,
        font=dict(size=12, color=color_mid),
        xanchor=xanchor_mid,
        yshift=0,
    )

    label_x_bot, xanchor_bot = strain_display.strain_label_anchor_display(
        eps_bot, eps_bot, offset=lo
    )
    fig.add_annotation(
        x=label_x_bot, y=y_bot,
        text=f"ε<sub>bot</sub> = {eps_bot:.5f}",
        showarrow=False,
        font=dict(size=12, color=color_bot),
        xanchor=xanchor_bot,
        yshift=10,
    )

    # Title (match bending style - subtle grey, paper coordinates)
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.06,
        text="<b>Longitudinal strain profile</b>",
        showarrow=False,
        font=dict(size=18, color="rgba(70,70,90,0.85)"),
        align="center",
    )

    # Limits annotation (top caption, paper coordinates)
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.12,
        text="AS 3600 limits: -2.0×10⁻⁴ ≤ ε<sub>x</sub> ≤ 3.0×10⁻³",
        showarrow=False,
        font=dict(size=13, color="rgba(70,70,90,0.85)"),
        align="center",
    )

    # Axis framing: big, clean, no clutter
    # Keep x-range tight around values, but include limits so users "see" the clamp region
    x_lo = min(eps_top, eps_x, eps_bot, eps_min)
    x_hi = max(eps_top, eps_x, eps_bot, eps_max)
    pad = 0.12 * (x_hi - x_lo if (x_hi - x_lo) > 0 else 1.0)

    # y-range like bending: range=[D*1.05, -0.18*D] (so "top" appears at top)
    fig.update_layout(
        margin=dict(l=10, r=10, t=70, b=10),
        height=height_px,
        xaxis=dict(
            visible=False,
            range=[x_lo - pad, x_hi + pad],
        ),
        yaxis=dict(
            visible=False,
            range=[D * 1.05, -0.18 * D],  # Inverted so top appears at top
            scaleanchor="x",
            scaleratio=1,
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig