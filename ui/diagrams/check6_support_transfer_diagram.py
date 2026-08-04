"""Check 6 shear support-transfer diagram builder."""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

from bending_layer_semantics import resolve_bending_layer_geometry
from section_layout import compute_shear_reo_layout_pure


def _check6_norm_support_token(raw: str) -> str:
    return str(raw or "").strip().lower()


def _check6_stirrup_xs_mm(*, L_seg_mm: float, s_mm: float, max_lines: int = 14) -> list[float]:
    s = max(float(s_mm), 1.0)
    L = max(float(L_seg_mm), s * 0.5)
    xs: list[float] = []
    x = 0.5 * s
    while x <= L - 1e-6 and len(xs) < max_lines:
        xs.append(x)
        x += s
    return xs


def _check6_crack_ray_hits_vertical_stirrup(
    xd: float,
    x0: float,
    y0: float,
    ux: float,
    uy: float,
    y_stirr_bot: float,
    y_stirr_top: float,
    t_max: float,
) -> bool:
    """True if the crack ray from (x0,y0) with unit-ish (ux,uy) crosses x=xd within stirrup height."""
    if abs(ux) < 1e-9:
        return False
    t = (float(xd) - float(x0)) / float(ux)
    if t < -1e-5 or t > float(t_max) + 1e-4:
        return False
    yi = float(y0) + t * float(uy)
    y_lo = min(float(y_stirr_bot), float(y_stirr_top))
    y_hi = max(float(y_stirr_bot), float(y_stirr_top))
    return y_lo - 1e-3 <= yi <= y_hi + 1e-3


def _check6_shear_cage_y_range_mm(
    *,
    layout: dict | None,
    shape_kind: str,
    dims: dict,
    reo: dict,
    D: float,
    lig_d: float,
    lig_legs: int,
) -> tuple[float, float]:
    reo_pts = (layout or {}).get("reo_points") if layout else None
    cover_bot = float(reo.get("cover_bot", 40.0))
    cover_top = float(reo.get("cover_top", 40.0))
    cover_side = float(reo.get("cover_side", min(cover_top, cover_bot)))
    if shape_kind == "RECT":
        b = float(dims.get("b", 300.0))
        sl = compute_shear_reo_layout_pure(
            b,
            D,
            cover_bot,
            cover_top,
            cover_side,
            float(lig_d),
            int(max(0, lig_legs)),
            list(reo_pts or []),
        )
        cg = sl.get("cage") or {}
    else:
        cg = (layout or {}).get("cage") or {}
    y0 = float(cg.get("y0", cover_top + 5.0))
    y1 = float(cg.get("y1", D - cover_bot - 5.0))
    if y1 <= y0:
        y0, y1 = cover_top + 5.0, D - cover_bot - 5.0
    return y0, y1


def _check6_draw_support_symbol(
    fig: go.Figure,
    *,
    x_ref: float,
    y_beam_bottom: float,
    D: float,
    kind: str,
    L_seg_mm: float,
) -> tuple[float, float]:
    """
    Draw support at plot x = x_ref (mm, same coords as beam). Styling matches
    ``shear_visuals._add_side_view_pinned_support`` / ``_add_side_view_fixed_support``.
    Returns (y_ground, node_x_display).
    """
    xc = float(x_ref)
    outline = "rgba(35,35,35,1.0)"
    fill_tri = "rgba(35,35,35,0.12)"
    ground_col = "rgba(80,80,80,0.85)"
    fill_wall = "rgba(45,45,45,0.15)"
    # Smaller than full shear side-view proportions so the sketch stays compact.
    _s6 = 0.68
    tri_depth = max(0.28 * D, 80.0) * _s6
    tri_hw = max(0.03 * float(L_seg_mm), 90.0) * _s6
    y_ground = y_beam_bottom - tri_depth - 0.08 * D

    k = _check6_norm_support_token(kind)

    if k == "free":
        tick = max(0.02 * D, 5.0) * _s6
        fig.add_shape(
            type="line",
            x0=xc - tick,
            y0=y_beam_bottom,
            x1=xc + tick,
            y1=y_beam_bottom,
            line=dict(color=outline, width=1.4),
        )
        return y_beam_bottom - 0.06 * D, xc

    if k == "fixed":
        hatch_dx = max(0.02 * float(L_seg_mm), 50.0) * _s6
        y_min = y_beam_bottom - 0.55 * D
        y_max = y_beam_bottom + 1.55 * D
        fig.add_shape(
            type="line",
            x0=xc,
            y0=y_min,
            x1=xc,
            y1=y_max,
            line=dict(color=outline, width=5),
        )
        for frac in (0.08, 0.28, 0.48, 0.68, 0.88):
            y_val = y_min + frac * (y_max - y_min)
            fig.add_shape(
                type="line",
                x0=xc - hatch_dx,
                y0=y_val + 0.10 * D,
                x1=xc,
                y1=y_val - 0.04 * D,
                line=dict(color="rgba(80,80,80,0.82)", width=1.0),
            )
        return y_ground, xc

    if k == "internal":
        pad_w = tri_hw * 1.85
        rx0 = x_ref - pad_w
        rx1 = x_ref + pad_w
        fig.add_shape(
            type="rect",
            x0=min(rx0, rx1),
            y0=y_ground - 0.04 * D,
            x1=max(rx0, rx1),
            y1=y_beam_bottom,
            line=dict(color="rgba(31,42,68,0)", width=0),
            fillcolor=fill_wall,
        )
        a0, a1 = x_ref - pad_w * 0.55, x_ref
        fig.add_shape(
            type="line",
            x0=min(a0, a1),
            y0=y_beam_bottom,
            x1=max(a0, a1),
            y1=y_ground - 0.02 * D,
            line=dict(color=outline, width=1.2),
        )
        b0, b1 = x_ref + pad_w * 0.55, x_ref
        fig.add_shape(
            type="line",
            x0=min(b0, b1),
            y0=y_beam_bottom,
            x1=max(b0, b1),
            y1=y_ground - 0.02 * D,
            line=dict(color=outline, width=1.2),
        )
        h0, h1 = x_ref - pad_w * 1.1, x_ref + pad_w * 1.1
        fig.add_shape(
            type="line",
            x0=min(h0, h1),
            y0=y_ground - 0.02 * D,
            x1=max(h0, h1),
            y1=y_ground - 0.02 * D,
            line=dict(color=ground_col, width=1.0),
        )
        return y_ground - 0.02 * D, xc

    # pinned / roller: triangle (apex at soffit, base below) — same geometry as side view
    tri = (
        f"M {xc - tri_hw:.4f},{y_beam_bottom - tri_depth:.4f} "
        f"L {xc + tri_hw:.4f},{y_beam_bottom - tri_depth:.4f} "
        f"L {xc:.4f},{y_beam_bottom:.4f} Z"
    )
    fig.add_shape(
        type="path",
        path=tri,
        line=dict(color=outline, width=1.4),
        fillcolor=fill_tri,
    )
    fig.add_shape(
        type="line",
        x0=xc - tri_hw * 1.15,
        y0=y_ground,
        x1=xc + tri_hw * 1.15,
        y1=y_ground,
        line=dict(color=ground_col, width=1.0),
    )
    if k == "roller":
        roller_r = max(0.04 * tri_depth, 28.0)
        cy = y_ground - roller_r * 1.4
        fig.add_shape(
            type="circle",
            xref="x",
            yref="y",
            x0=xc - roller_r,
            y0=cy - roller_r,
            x1=xc + roller_r,
            y1=cy + roller_r,
            line=dict(color=outline, width=1.15),
            fillcolor="rgba(255,255,255,0.55)",
        )
    return y_ground, xc


def _check6_shape_kind_and_dims(layout: dict | None) -> tuple[str, dict]:
    layout = layout or {}
    dims = dict(layout.get("dims") or {})
    sn = str(layout.get("shape_name") or "")
    if sn.startswith("T-Section"):
        return "T", dims
    if sn.startswith("I-Section"):
        return "I", dims
    Dv = float(layout.get("D") or dims.get("D") or 600.0)
    dims.setdefault("b", float(layout.get("b") or 300.0))
    dims.setdefault("D", Dv)
    return "RECT", dims


def _check6_section_inset_polygon_uv(shape_kind: str, dims: dict) -> tuple[list[tuple[float, float]], float]:
    """Section polygon in (u,v): u horizontal, v down from top; returns (points, width_u)."""
    if shape_kind == "T":
        bf = float(dims["bf"])
        tf = float(dims["tf"])
        bw = float(dims["bw"])
        D = float(dims["D"])
        x0 = (bf - bw) / 2.0
        x1 = x0 + bw
        pts = [
            (0.0, 0.0),
            (bf, 0.0),
            (bf, tf),
            (x1, tf),
            (x1, D),
            (x0, D),
            (x0, tf),
            (0.0, tf),
            (0.0, 0.0),
        ]
        return pts, bf
    if shape_kind == "I":
        bf = float(dims["bf"])
        tf = float(dims["tf"])
        tw = float(dims["tw"])
        D = float(dims["D"])
        x0 = (bf - tw) / 2.0
        x1 = x0 + tw
        pts = [
            (0.0, 0.0),
            (bf, 0.0),
            (bf, tf),
            (x1, tf),
            (x1, D - tf),
            (bf, D - tf),
            (bf, D),
            (0.0, D),
            (0.0, D - tf),
            (x0, D - tf),
            (x0, tf),
            (0.0, tf),
            (0.0, 0.0),
        ]
        return pts, bf
    b = float(dims["b"])
    D = float(dims["D"])
    return [(0.0, 0.0), (b, 0.0), (b, D), (0.0, D), (0.0, 0.0)], b


def _check6_y_display(D_mm: float, v_from_top: float) -> float:
    """Map section v (0=top) to display y (0=soffit, D=top)."""
    return float(D_mm) - float(v_from_top)


def _check6_tension_ast_mm2(layout: dict | None, tension_face: str) -> float:
    """Sum tension steel area (mm²) from layout reo_points, else reo counts."""
    pts = (layout or {}).get("reo_points") or []
    s = 0.0
    for p in pts:
        if str(p.get("layer")) != str(tension_face):
            continue
        try:
            db = float(p.get("db", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if db > 0:
            s += math.pi * (db**2) / 4.0
    if s > 1e-6:
        return float(s)
    reo = (layout or {}).get("reo") or {}
    try:
        if tension_face == "bottom":
            n = int(float(reo.get("nb_bot", 0) or 0))
            db = float(reo.get("db_bot", reo.get("db_bot_1", 0.0)) or 0.0)
        else:
            n = int(float(reo.get("nb_top", 0) or 0))
            db = float(reo.get("db_top", reo.get("db_top_1", 0.0)) or 0.0)
    except (TypeError, ValueError):
        n, db = 0, 0.0
    if n > 0 and db > 0:
        return float(n) * math.pi * (db**2) / 4.0
    return 0.0


def _check6_uls_dn_mm(*, fc_mpa: float, b_mm: float, fsy_mpa: float, Ast_mm2: float) -> float:
    """Rectangular stress-block neutral axis depth d_n (mm), same ULS factors as bending tab 1.4."""
    fc = max(float(fc_mpa), 1e-6)
    b = max(float(b_mm), 1e-6)
    fsy = max(float(fsy_mpa), 1e-6)
    Ast = max(float(Ast_mm2), 0.0)
    if Ast <= 1e-6:
        return float("nan")
    alpha2_raw = 0.85 - 0.0015 * fc
    gamma_raw = 0.97 - 0.0025 * fc
    alpha2 = max(0.67, alpha2_raw)
    gamma = max(0.67, gamma_raw)
    T = Ast * fsy
    denom = alpha2 * fc * b * gamma
    if denom <= 1e-12:
        return float("nan")
    return T / denom


def _check6_v_na_from_dn_mm(*, D: float, dn_mm: float, compression_face: str) -> float:
    """Distance from top fibre to NA (mm, v coordinate) from d_n and compression face."""
    Df = max(float(D), 1e-6)
    dn = float(dn_mm)
    if not math.isfinite(dn) or dn <= 0:
        return 0.5 * Df
    dn = max(1e-6, min(dn, Df - 1e-6))
    if str(compression_face) == "bottom":
        return Df - dn
    return dn


def _check6_crack_bezier_setup(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    tension_face: str,
    D_mm: float,
    bulge_scale: float = 1.0,
) -> tuple[
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
] | None:
    """
    Cubic geometry for the crack **mean line**: same toe/tip anchors as the θ_v chord, with a mild
    arch toward compression. The jagged black crack and the smooth backbone for the green offset
    both sample this curve; ``bulge_scale`` scales the arch (historical default ≈1.28 → ~0.155 arch).
    """
    bs = max(0.55, min(2.2, float(bulge_scale)))
    arch_scale = 0.155 * (bs / 1.28)
    arch_scale = max(0.075, min(0.215, float(arch_scale)))
    geom = _check6_arched_transfer_bezier_geom(
        float(xa),
        float(ya),
        float(xb),
        float(yb),
        tension_face=str(tension_face),
        D_mm=float(D_mm),
        arch_scale=arch_scale,
    )
    if geom is None:
        return _check6_collinear_bezier_geom_from_chord(
            float(xa), float(ya), float(xb), float(yb)
        )
    return geom


def _check6_bezier_der_at_t(
    xa: float,
    ya: float,
    cx1: float,
    cy1: float,
    cx2: float,
    cy2: float,
    xb: float,
    yb: float,
    t: float,
) -> tuple[float, float]:
    u = 1.0 - t
    ddx = 3.0 * u * u * (cx1 - xa) + 6.0 * u * t * (cx2 - cx1) + 3.0 * t * t * (xb - cx2)
    ddy = 3.0 * u * u * (cy1 - ya) + 6.0 * u * t * (cy2 - cy1) + 3.0 * t * t * (yb - cy2)
    return ddx, ddy


def _check6_bezier_unit_tangents_at_ends(
    geom: tuple[float, ...],
) -> tuple[tuple[float, float], tuple[float, float]]:
    xa, ya, cx1, cy1, cx2, cy2, xb, yb = geom[:8]

    def _unit(t: float) -> tuple[float, float]:
        ddx, ddy = _check6_bezier_der_at_t(xa, ya, cx1, cy1, cx2, cy2, xb, yb, t)
        Ln = math.hypot(ddx, ddy)
        if Ln < 1e-12:
            return (1.0, 0.0)
        return ddx / Ln, ddy / Ln

    return _unit(0.0), _unit(1.0)


def _check6_unit_toe_to_tip_crack(
    *,
    support_side: str,
    tension_face: str,
    theta_v_rad: float,
) -> tuple[float, float]:
    """
    Unit vector **toe → crack tip** with **θ_v** = angle from **horizontal** (into-span, +x display)
    to the crack, CCW positive. Matches ``cot θ_v`` shear-steel geometry (mean line, not strut normal).

    Bottom tension: ``(|cos θ|, |sin θ|)`` with into-span horizontal sign; top tension: downward legs.
    """
    th = max(math.radians(1.0), min(theta_v_rad, math.radians(89.0)))
    cx, sy = math.cos(th), math.sin(th)
    sn = str(support_side or "left").strip().lower()
    tf = str(tension_face or "bottom").strip().lower()
    if tf == "bottom":
        if sn == "right":
            return -cx, sy
        if sn == "internal":
            return -cx, sy
        return cx, sy
    if sn == "right":
        return -cx, -sy
    if sn == "internal":
        return -cx, -sy
    return cx, -sy


def _check6_collinear_bezier_geom_from_chord(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
) -> tuple[float, float, float, float, float, float, float, float, float, float, float] | None:
    """Cubic control points on the chord so Bézier derivatives match the straight θ crack."""
    xa, ya, xb, yb = float(xa), float(ya), float(xb), float(yb)
    dx, dy = xb - xa, yb - ya
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    t1, t2 = 1.0 / 3.0, 2.0 / 3.0
    nx, ny = -dy / L, dx / L
    cx1 = xa + t1 * dx
    cy1 = ya + t1 * dy
    cx2 = xa + t2 * dx
    cy2 = ya + t2 * dy
    return (xa, ya, cx1, cy1, cx2, cy2, xb, yb, nx, ny, L)


def _check6_arched_transfer_bezier_geom(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    tension_face: str,
    D_mm: float,
    arch_scale: float = 0.050,
) -> tuple[float, float, float, float, float, float, float, float, float, float, float] | None:
    """
    Mild cubic arch between endpoints (same tangents as gentle transfer curve).
    Bow lifts slightly toward the compression zone for bottom tension (readable, compact).
    """
    xa, ya, xb, yb = float(xa), float(ya), float(xb), float(yb)
    dx, dy = xb - xa, yb - ya
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    D = max(float(D_mm), 1.0)
    nx, ny = -dy / L, dx / L
    bulge = float(arch_scale) * min(L, 0.85 * D)
    if str(tension_face).strip().lower() == "bottom":
        if ny < 0:
            nx, ny = -nx, -ny
    else:
        if ny > 0:
            nx, ny = -nx, -ny
    ox, oy = nx * bulge, ny * bulge
    t1, t2 = 1.0 / 3.0, 2.0 / 3.0
    cx1 = xa + t1 * dx + ox
    cy1 = ya + t1 * dy + oy
    cx2 = xa + t2 * dx + ox
    cy2 = ya + t2 * dy + oy
    return (xa, ya, cx1, cy1, cx2, cy2, xb, yb, nx, ny, L)


def _check6_soft_jagged_on_bezier(
    geom: tuple[float, ...],
    *,
    D_mm: float,
    n: int = 44,
) -> list[tuple[float, float]]:
    """Jagged crack with smooth cubic centerline (same jitter style as straight chord)."""
    if geom is None or len(geom) < 11:
        return []
    xa, ya, cx1, cy1, cx2, cy2, xb, yb, _, _, L = geom[:11]
    L = max(float(L), 1e-9)
    D = max(float(D_mm), 1.0)
    arch_len = float(
        math.hypot(xb - xa, yb - ya) + 0.35 * math.hypot(cx2 - cx1, cy2 - cy1)
    )

    def _bez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        uu, tt = u * u, t * t
        b0, b1, b2, b3 = u * uu, 3.0 * uu * t, 3.0 * u * tt, t * tt
        return (
            b0 * xa + b1 * cx1 + b2 * cx2 + b3 * xb,
            b0 * ya + b1 * cy1 + b2 * cy2 + b3 * yb,
        )

    def _dbez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        ddx = 3.0 * u * u * (cx1 - xa) + 6.0 * u * t * (cx2 - cx1) + 3.0 * t * t * (xb - cx2)
        ddy = 3.0 * u * u * (cy1 - ya) + 6.0 * u * t * (cy2 - cy1) + 3.0 * t * t * (yb - cy2)
        return ddx, ddy

    jag_amp = max(3.2, 0.035 * min(arch_len, 0.52 * D))
    jag_amp = min(jag_amp, 0.060 * D)
    salt = 0.0017 * (xa + 2.3 * ya + 1.1 * xb + yb)
    out: list[tuple[float, float]] = []
    nn = max(12, int(n))
    for i in range(nn + 1):
        t = i / nn
        bx, by = _bez(t)
        ddx, ddy = _dbez(t)
        tlen = math.hypot(ddx, ddy)
        if tlen < 1e-9:
            px, py = 0.0, 1.0
        else:
            px, py = -ddy / tlen, ddx / tlen
        taper = math.sin(math.pi * t) ** 0.82
        if i == 0 or i == nn:
            off = 0.0
        else:
            j = float(i)
            wobble = math.sin(15.2 * j + salt) * math.cos(7.1 * j + 0.41 * salt)
            wobble += 0.45 * math.sin(27.0 * j * j / (nn + 1.0) + 1.3 * salt)
            wobble += 0.28 * math.sin(31.0 * j + 0.9 * salt)
            off = jag_amp * taper * max(-1.0, min(1.0, wobble))
        bx += off * px
        by += off * py
        out.append((bx, by))
    return out


def _check6_bezier_to_smooth_path_svg(
    geom: tuple[float, ...],
    *,
    n: int = 56,
) -> str:
    """Dense polyline approximating the cubic (for mean green / smooth crack paths)."""
    if geom is None or len(geom) < 8:
        return ""
    xa, ya, cx1, cy1, cx2, cy2, xb, yb = geom[:8]

    def _bez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        uu, tt = u * u, t * t
        b0, b1, b2, b3 = u * uu, 3.0 * uu * t, 3.0 * u * tt, t * tt
        return (
            b0 * xa + b1 * cx1 + b2 * cx2 + b3 * xb,
            b0 * ya + b1 * cy1 + b2 * cy2 + b3 * yb,
        )

    nn = max(16, int(n))
    parts: list[str] = []
    for i in range(nn + 1):
        bx, by = _bez(i / nn)
        parts.append(f"{'M' if i == 0 else 'L'} {bx:.4f},{by:.4f}")
    return " ".join(parts)


def _check6_smooth_bezier_polyline_list(
    geom: tuple[float, ...],
    *,
    n: int = 72,
) -> list[tuple[float, float]]:
    if geom is None or len(geom) < 8:
        return []
    xa, ya, cx1, cy1, cx2, cy2, xb, yb = geom[:8]

    def _bez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        uu, tt = u * u, t * t
        b0, b1, b2, b3 = u * uu, 3.0 * uu * t, 3.0 * u * tt, t * tt
        return (
            b0 * xa + b1 * cx1 + b2 * cx2 + b3 * xb,
            b0 * ya + b1 * cy1 + b2 * cy2 + b3 * yb,
        )

    nn = max(16, int(n))
    return [_bez(i / nn) for i in range(nn + 1)]


def _check6_soft_jagged_chord(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    D_mm: float,
    jag_scale: float = 0.78,
) -> list[tuple[float, float]]:
    """Straight crack chord with mild jagged styling (centered on θ_v mean line)."""
    xa, ya, xb, yb = float(xa), float(ya), float(xb), float(yb)
    dx, dy = xb - xa, yb - ya
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return []
    nx, ny = -dy / L, dx / L
    D = max(float(D_mm), 1.0)
    n = 40
    jag_amp = max(2.8, 0.030 * min(L, 0.52 * D)) * float(jag_scale)
    jag_amp = min(jag_amp, 0.052 * D)
    salt = 0.0017 * (xa + 2.3 * ya + 1.1 * xb + yb)
    out: list[tuple[float, float]] = []
    for i in range(n + 1):
        t = i / n
        bx = xa + t * dx
        by = ya + t * dy
        taper = math.sin(math.pi * t) ** 0.82
        if i == 0 or i == n:
            off = 0.0
        else:
            j = float(i)
            wobble = math.sin(15.2 * j + salt) * math.cos(7.1 * j + 0.41 * salt)
            wobble += 0.45 * math.sin(27.0 * j * j / (n + 1.0) + 1.3 * salt)
            wobble += 0.28 * math.sin(31.0 * j + 0.9 * salt)
            off = jag_amp * taper * max(-1.0, min(1.0, wobble))
        bx += off * nx
        by += off * ny
        out.append((bx, by))
    return out


def _check6_soft_crack_polyline(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    tension_face: str,
    D_mm: float,
    bulge_scale: float = 1.0,
    jag_scale: float = 1.0,
) -> list[tuple[float, float]]:
    """
    Same geometry as the black crack: Bézier + jagged samples. Empty if degenerate chord.
    """
    geom = _check6_crack_bezier_setup(
        xa, ya, xb, yb, tension_face=tension_face, D_mm=D_mm, bulge_scale=bulge_scale
    )
    if geom is None:
        return []
    xa, ya, cx1, cy1, cx2, cy2, xb, yb, nx, ny, L = geom
    D = max(float(D_mm), 1.0)

    def _bez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        uu, tt = u * u, t * t
        b0, b1, b2, b3 = u * uu, 3.0 * uu * t, 3.0 * u * tt, t * tt
        return (
            b0 * xa + b1 * cx1 + b2 * cx2 + b3 * xb,
            b0 * ya + b1 * cy1 + b2 * cy2 + b3 * yb,
        )

    def _dbez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        ddx = 3.0 * u * u * (cx1 - xa) + 6.0 * u * t * (cx2 - cx1) + 3.0 * t * t * (xb - cx2)
        ddy = 3.0 * u * u * (cy1 - ya) + 6.0 * u * t * (cy2 - cy1) + 3.0 * t * t * (yb - cy2)
        return ddx, ddy

    n = 40
    js = max(0.0, float(jag_scale))
    jag_amp = max(3.5, 0.038 * min(L, 0.52 * D)) * js
    jag_amp *= max(0.72, min(1.45, float(bulge_scale)))
    jag_amp = min(jag_amp, 0.065 * D * js)
    salt = 0.0017 * (xa + 2.3 * ya + 1.1 * xb + yb)
    out: list[tuple[float, float]] = []
    for i in range(n + 1):
        t = i / n
        bx, by = _bez(t)
        ddx, ddy = _dbez(t)
        tlen = math.hypot(ddx, ddy)
        if tlen < 1e-9:
            px, py = nx, ny
        else:
            px, py = -ddy / tlen, ddx / tlen
        taper = math.sin(math.pi * t) ** 0.82
        if i == 0 or i == n:
            off = 0.0
        else:
            j = float(i)
            wobble = math.sin(15.2 * j + salt) * math.cos(7.1 * j + 0.41 * salt)
            wobble += 0.45 * math.sin(27.0 * j * j / (n + 1.0) + 1.3 * salt)
            wobble += 0.28 * math.sin(31.0 * j + 0.9 * salt)
            off = jag_amp * taper * max(-1.0, min(1.0, wobble))
        bx += off * px
        by += off * py
        out.append((bx, by))
    return out


def _check6_smooth_crack_polyline(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    tension_face: str,
    D_mm: float,
    n: int = 64,
    bulge_scale: float = 1.0,
) -> list[tuple[float, float]]:
    """Same Bézier backbone as the black crack, sampled smoothly (no perpendicular jag)."""
    geom = _check6_crack_bezier_setup(
        xa, ya, xb, yb, tension_face=tension_face, D_mm=D_mm, bulge_scale=bulge_scale
    )
    if geom is None:
        return []
    xa, ya, cx1, cy1, cx2, cy2, xb, yb, _, _, _ = geom

    def _bez(t: float) -> tuple[float, float]:
        u = 1.0 - t
        uu, tt = u * u, t * t
        b0, b1, b2, b3 = u * uu, 3.0 * uu * t, 3.0 * u * tt, t * tt
        return (
            b0 * xa + b1 * cx1 + b2 * cx2 + b3 * xb,
            b0 * ya + b1 * cy1 + b2 * cy2 + b3 * yb,
        )

    nn = max(16, int(n))
    return [_bez(i / nn) for i in range(nn + 1)]


def _check6_soft_crack_path_svg(
    xa: float,
    ya: float,
    xb: float,
    yb: float,
    *,
    tension_face: str,
    D_mm: float,
) -> str:
    """
    Cubic Bézier backbone from A to B (bow toward compression), then sampled to a polyline with
    subtle perpendicular jitter so it reads as a slightly jagged crack (stable, not random per frame).
    """
    pts = _check6_soft_crack_polyline(
        xa, ya, xb, yb, tension_face=tension_face, D_mm=D_mm
    )
    if not pts:
        return ""
    parts: list[str] = []
    for i, (bx, by) in enumerate(pts):
        parts.append(f"{'M' if i == 0 else 'L'} {bx:.4f},{by:.4f}")
    return " ".join(parts)


def _check6_polyline_to_path_svg(pts: list[tuple[float, float]]) -> str:
    if len(pts) < 2:
        return ""
    parts: list[str] = []
    for i, (bx, by) in enumerate(pts):
        parts.append(f"{'M' if i == 0 else 'L'} {bx:.4f},{by:.4f}")
    return " ".join(parts)


def _check6_scaled_rgba_alpha(color: str, alpha_scale: float) -> str:
    """Match ``shear_visuals._scaled_rgba_alpha`` for MCFT flow pulse styling."""
    if not color.startswith("rgba(") or not color.endswith(")"):
        return color
    parts = [part.strip() for part in color[5:-1].split(",")]
    if len(parts) != 4:
        return color
    try:
        alpha = float(parts[3])
    except ValueError:
        return color
    scaled_alpha = max(0.0, min(1.0, alpha * alpha_scale))
    return f"rgba({parts[0]},{parts[1]},{parts[2]},{scaled_alpha:.3f})"


def _check6_append_points_min_sep(
    acc: list[tuple[float, float]],
    pts: list[tuple[float, float]],
    *,
    min_sep: float = 0.18,
) -> None:
    for px, py in pts:
        if not acc:
            acc.append((float(px), float(py)))
            continue
        lx, ly = acc[-1]
        if math.hypot(float(px) - lx, float(py) - ly) >= float(min_sep):
            acc.append((float(px), float(py)))


def _check6_linear_sample(
    x0: float, y0: float, x1: float, y1: float, *, n: int
) -> list[tuple[float, float]]:
    n = max(2, int(n))
    out: list[tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    return out


def _check6_tie_x_toward_support(
    *,
    tie_xa: float,
    tie_xb: float,
    support_face_x: float,
) -> float:
    ta, tb = (tie_xa, tie_xb) if tie_xa <= tie_xb else (tie_xb, tie_xa)
    return ta if abs(ta - support_face_x) <= abs(tb - support_face_x) else tb


def _check6_build_shear_transfer_flow_combined_pts(
    *,
    cx_c: float,
    y_c_top: float,
    y_c_bottom: float,
    mean_green_pts: list[tuple[float, float]],
    y_steel: float,
    tie_xa: float,
    tie_xb: float,
    support_face_x: float,
    D: float,
    L_seg: float,
) -> tuple[list[tuple[float, float]], tuple[int, int]]:
    """
    One polyline: top of C → down C → crack tip on green path → along green toward Ast →
    along tie toward the support (matches Check 5 load-transfer read).

    Returns ``(points, (end_red_incl, end_green_incl))`` where inclusive indices mark the last
    vertex of the red (vertical C), green (bridge + transfer + drop to Ast), and blue is the remainder.
    """
    if len(mean_green_pts) < 2:
        return [], (0, 0)
    D = max(float(D), 1.0)
    Ls = max(float(L_seg), 1.0)
    gtip = mean_green_pts[-1]
    gtoe = mean_green_pts[0]
    acc: list[tuple[float, float]] = []
    n_vert = max(10, min(48, int(abs(y_c_top - y_c_bottom) / max(0.012 * D, 4.0)) + 4))
    _check6_append_points_min_sep(
        acc, _check6_linear_sample(cx_c, y_c_top, cx_c, y_c_bottom, n=n_vert)
    )
    end_red = max(0, len(acc) - 1)
    bridge_n = max(
        2,
        min(
            16,
            int(
                math.hypot(float(gtip[0]) - cx_c, float(gtip[1]) - y_c_bottom)
                / max(0.015 * Ls, 5.0)
            )
            + 2,
        ),
    )
    _check6_append_points_min_sep(
        acc,
        _check6_linear_sample(cx_c, y_c_bottom, float(gtip[0]), float(gtip[1]), n=bridge_n),
    )
    for k in range(len(mean_green_pts) - 1, -1, -1):
        _check6_append_points_min_sep(acc, [mean_green_pts[k]])
    gx0, gy0 = float(gtoe[0]), float(gtoe[1])
    if abs(gy0 - float(y_steel)) > 0.8:
        _check6_append_points_min_sep(
            acc, _check6_linear_sample(gx0, gy0, gx0, float(y_steel), n=4)
        )
    end_green = max(end_red, len(acc) - 1)
    x_tie_goal = _check6_tie_x_toward_support(
        tie_xa=float(tie_xa),
        tie_xb=float(tie_xb),
        support_face_x=float(support_face_x),
    )
    t_lo, t_hi = (tie_xa, tie_xb) if tie_xa <= tie_xb else (tie_xb, tie_xa)
    x_on = min(max(gx0, t_lo), t_hi)
    n_tie = max(
        6,
        min(
            40,
            int(abs(x_on - x_tie_goal) / max(0.018 * Ls, 6.0)) + 4,
        ),
    )
    _check6_append_points_min_sep(
        acc,
        _check6_linear_sample(x_on, float(y_steel), x_tie_goal, float(y_steel), n=n_tie),
    )
    return acc, (end_red, end_green)


def _check6_add_mcft_style_flow_pulse(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    *,
    color: str = "rgba(46,125,50,0.95)",
    reverse_along_path: bool = True,
    flow_segment_ends: tuple[int, int] | None = None,
    flow_arrowhead: bool = False,
    flow_colors_rgb: tuple[str, str, str] = ("#c41e3a", "#2e7d32", "#1565c0"),
    line_shape: str = "spline",
) -> None:
    """
    Dashed path + sliding ``meta.animate_flow`` window (same pattern as MCFT principal-stress
    diagrams). Default ``line_shape="spline"`` smooths along the polyline; use ``"linear"`` when
    the path mixes straight legs (e.g. vertical **C** + diagonal bridge) so Plotly does not bow the
    bridge segment to meet the next curve.
    """
    if len(pts) < 3:
        return
    ls = str(line_shape or "spline").strip().lower()
    use_spline = ls == "spline"
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    line_kw: dict = dict(
        color=_check6_scaled_rgba_alpha(color, 0.95),
        width=3.2,
        dash="12px,10px",
    )
    if use_spline:
        line_kw["shape"] = "spline"
        line_kw["smoothing"] = 0.64
    else:
        line_kw["shape"] = "linear"
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            line=line_kw,
            opacity=0.96,
            hoverinfo="skip",
            showlegend=False,
        )
    )
    path_pts = list(reversed(pts)) if reverse_along_path else list(pts)
    if len(path_pts) < 5:
        return
    window = max(3, min(7, max(4, len(path_pts) // 2)))
    fx = [float(p[0]) for p in path_pts]
    fy = [float(p[1]) for p in path_pts]
    npath = len(fx)
    cr, cg, cb = flow_colors_rgb
    er, eg = -1, max(0, npath - 1)
    if flow_segment_ends is not None:
        er0, eg0 = int(flow_segment_ends[0]), int(flow_segment_ends[1])
        if reverse_along_path:
            er = max(0, npath - 1 - eg0)
            eg = max(0, npath - 1 - er0)
        else:
            er, eg = er0, eg0
    pulse_meta: dict = {
        "animate_flow": True,
        "flow_x": fx,
        "flow_y": fy,
        "window": window,
        "step": 1,
    }
    if flow_arrowhead:
        pulse_meta["flow_end_red"] = er
        pulse_meta["flow_end_green"] = eg
        pulse_meta["flow_color_red"] = cr
        pulse_meta["flow_color_green"] = cg
        pulse_meta["flow_color_blue"] = cb
    line_trace_index = len(fig.data)
    pulse_line_kw: dict = dict(
        color=_check6_scaled_rgba_alpha(color, 1.0),
        width=3.8,
    )
    if use_spline:
        pulse_line_kw["shape"] = "spline"
        pulse_line_kw["smoothing"] = 0.64
    else:
        pulse_line_kw["shape"] = "linear"
    fig.add_trace(
        go.Scatter(
            x=fx[:window],
            y=fy[:window],
            mode="lines",
            line=pulse_line_kw,
            opacity=0.98,
            hoverinfo="skip",
            showlegend=False,
            meta=pulse_meta,
        )
    )
    if flow_arrowhead and len(fx) >= 2:
        lead = min(max(window - 1, 0), npath - 1)
        lx0 = max(0, lead - 1)
        dx = float(fx[lead] - fx[lx0]) if lead > lx0 else float(fx[min(1, npath - 1)] - fx[0])
        dy = float(fy[lead] - fy[lx0]) if lead > lx0 else float(fy[min(1, npath - 1)] - fy[0])
        if abs(dx) + abs(dy) < 1e-9 and lead < npath - 1:
            dx = float(fx[lead + 1] - fx[lead])
            dy = float(fy[lead + 1] - fy[lead])
        ang0 = math.degrees(math.atan2(dy, dx)) - 90.0
        col0 = cg
        if flow_segment_ends is not None:
            if er >= 0 and lead <= er:
                col0 = cr
            elif lead <= eg:
                col0 = cg
            else:
                col0 = cb
        if col0 == cb:
            ang0 += 180.0
        fig.add_trace(
            go.Scatter(
                x=[fx[lead]],
                y=[fy[lead]],
                mode="markers",
                marker=dict(
                    symbol="triangle-up",
                    size=9,
                    angle=ang0,
                    color=col0,
                    line=dict(width=0.5, color="rgba(255,255,255,0.92)"),
                ),
                hoverinfo="skip",
                showlegend=False,
                meta={
                    "animate_flow_arrow": True,
                    "flow_follow_line_index": line_trace_index,
                },
            )
        )


def _check6_trim_polyline_at_ast_elevation(
    pts: list[tuple[float, float]],
    *,
    y_ast: float,
    tension_face: str,
) -> tuple[list[tuple[float, float]], float, int]:
    """
    Drop the tension-side tail: keep only the polyline from the Ast horizontal (y_ast) toward
    compression. Display y increases toward the top fibre; bottom tension → keep y >= y_ast.

    Returns (trimmed_points, t_index_offset, n_orig) so Bézier normals use
    t = (t_index_offset + k) / max(1, n_orig - 1) for trimmed index k.
    """
    n_orig = len(pts)
    if n_orig < 2:
        return (list(pts), 0.0, n_orig)
    y_s = float(y_ast)
    bottom_tension = str(tension_face).strip().lower() == "bottom"
    eps = 1e-6
    for i in range(n_orig - 1):
        x0, y0 = float(pts[i][0]), float(pts[i][1])
        x1, y1 = float(pts[i + 1][0]), float(pts[i + 1][1])
        if bottom_tension:
            if y0 >= y_s - eps:
                out = [(x0, y0)] + [
                    (float(pts[j][0]), float(pts[j][1])) for j in range(i + 1, n_orig)
                ]
                return (out, float(i), n_orig)
            if y0 < y_s - eps and y1 >= y_s - eps and abs(y1 - y0) > 1e-12:
                tseg = (y_s - y0) / (y1 - y0)
                if 0.0 <= tseg <= 1.0:
                    xi = x0 + tseg * (x1 - x0)
                    out = [(xi, y_s)] + [
                        (float(pts[j][0]), float(pts[j][1])) for j in range(i + 1, n_orig)
                    ]
                    return (out, float(i) + tseg, n_orig)
        else:
            if y0 <= y_s + eps:
                out = [(x0, y0)] + [
                    (float(pts[j][0]), float(pts[j][1])) for j in range(i + 1, n_orig)
                ]
                return (out, float(i), n_orig)
            if y0 > y_s + eps and y1 <= y_s + eps and abs(y1 - y0) > 1e-12:
                tseg = (y_s - y0) / (y1 - y0)
                if 0.0 <= tseg <= 1.0:
                    xi = x0 + tseg * (x1 - x0)
                    out = [(xi, y_s)] + [
                        (float(pts[j][0]), float(pts[j][1])) for j in range(i + 1, n_orig)
                    ]
                    return (out, float(i) + tseg, n_orig)
    return ([], 0.0, n_orig)


def _check6_add_green_ccw_flow_on_polyline(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    *,
    x_shift_mm: float,
    D_mm: float,
    L_seg_mm: float,
    y_bot: float,
    y_top: float,
    green: str = "#2e7d32",
    crack_bezier_geom: tuple[float, ...] | None = None,
    wall_x_mm: float | None = None,
    wall_at_start: bool = False,
    suppress_wall_extension_at_tension: bool = False,
    bezier_t_index_offset: float = 0.0,
    bezier_n_orig: int | None = None,
    y_ast_clip: float | None = None,
    ast_clip_tension_face: str | None = None,
) -> None:
    """
    Smooth crack backbone offset by a constant perpendicular distance (same side as +x) so the
    green–crack gap reads even top vs bottom; clamped inside the beam. If needed, drops points from
    the compression end; extends along the Bézier tangent to the wall; arrows reversed along path.
    When the polyline is trimmed at Ast, set suppress_wall_extension_at_tension so the tension-side
    wall stub is not redrawn below that cut. y_ast_clip + ast_clip_tension_face keep the offset path
    and arrows on the compression side of the blue Ast (offset can otherwise cross y_steel).
    """
    if len(pts) < 4:
        return
    Ls = max(float(L_seg_mm), 1.0)
    D = max(float(D_mm), 1.0)
    x_m = max(0.018 * Ls, 0.022 * D, 12.0)
    y_m = max(0.014 * D, 8.0)
    x_lo_b = x_m
    x_hi_b = Ls - x_m
    y_lo_b = float(y_bot) + y_m
    y_hi_b = float(y_top) - y_m
    if x_hi_b <= x_lo_b or y_hi_b <= y_lo_b:
        return

    y_ast = float(y_ast_clip) if y_ast_clip is not None else None
    ast_tf = str(ast_clip_tension_face or "").strip().lower()
    ast_bottom = y_ast is not None and ast_tf == "bottom"
    ast_top = y_ast is not None and ast_tf == "top"

    desired = float(x_shift_mm)
    gap_min = max(0.022 * Ls, 0.026 * D, 18.0)
    n_param = int(bezier_n_orig) if bezier_n_orig is not None else len(pts)
    t_idx0 = float(bezier_t_index_offset)
    geom = crack_bezier_geom
    xa_g, ya_g, cx1_g, cy1_g, cx2_g, cy2_g, xb_g, yb_g = (
        (geom[:8] if geom is not None else (0.0,) * 8)
    )

    def _offset_normal_at_t(t: float) -> tuple[float, float]:
        if geom is None:
            return (1.0, 0.0)
        ddx, ddy = _check6_bezier_der_at_t(
            xa_g, ya_g, cx1_g, cy1_g, cx2_g, cy2_g, xb_g, yb_g, t
        )
        ln = math.hypot(ddx, ddy)
        if ln < 1e-12:
            return (1.0, 0.0)
        nx_n, ny_n = -ddy / ln, ddx / ln
        if nx_n < 0.0:
            nx_n, ny_n = -nx_n, -ny_n
        return nx_n, ny_n

    def _max_feasible_gap(pts_work: list[tuple[float, float]]) -> float:
        if geom is None:
            mx = max(float(x) for x, _ in pts_work)
            return min(desired, max(0.0, x_hi_b - mx))
        g = desired
        for i, (x, y) in enumerate(pts_work):
            t = min(1.0, max(0.0, (t_idx0 + i) / max(1, n_param - 1)))
            nx_n, ny_n = _offset_normal_at_t(t)
            x, y = float(x), float(y)
            if nx_n > 1e-9:
                g = min(g, (x_hi_b - x) / nx_n)
            elif nx_n < -1e-9:
                g = min(g, (x - x_lo_b) / (-nx_n))
            if ny_n > 1e-9:
                g = min(g, (y_hi_b - y) / ny_n)
            elif ny_n < -1e-9:
                g = min(g, (y - y_lo_b) / (-ny_n))
        return max(0.0, min(desired, g))

    pts_work = list(pts)
    while True:
        if len(pts_work) < 4:
            return
        gap_try = _max_feasible_gap(pts_work)
        if gap_try >= gap_min or len(pts_work) == 4:
            break
        pts_work.pop(-1)

    gap = _max_feasible_gap(pts_work)

    shifted: list[tuple[float, float]] = []
    for i, (x, y) in enumerate(pts_work):
        x, y = float(x), float(y)
        if geom is None:
            xr, yr = x + gap, y
        else:
            t = min(1.0, max(0.0, (t_idx0 + i) / max(1, n_param - 1)))
            nx_n, ny_n = _offset_normal_at_t(t)
            xr, yr = x + gap * nx_n, y + gap * ny_n
        if ast_bottom:
            yr = max(yr, y_ast)
        elif ast_top:
            yr = min(yr, y_ast)
        xr = min(max(xr, x_lo_b), x_hi_b)
        yr = min(max(yr, y_lo_b), y_hi_b)
        if ast_bottom:
            yr = max(yr, y_ast)
        elif ast_top:
            yr = min(yr, y_ast)
        shifted.append((xr, yr))

    wx = float(wall_x_mm) if wall_x_mm is not None and crack_bezier_geom is not None else None
    if wx is not None and len(shifted) >= 2:
        tan0, tan1 = _check6_bezier_unit_tangents_at_ends(crack_bezier_geom)
        if wall_at_start and not suppress_wall_extension_at_tension:
            px, py = shifted[0]
            dx, dy = -tan0[0], -tan0[1]
            if abs(dx) > 1e-6:
                s = (wx - px) / dx
                if s > 0.0 and math.isfinite(s):
                    ny = py + s * dy
                    ny = min(max(ny, y_lo_b), y_hi_b)
                    if ast_bottom:
                        ny = max(ny, y_ast)
                    elif ast_top:
                        ny = min(ny, y_ast)
                    shifted.insert(0, (wx, ny))
        else:
            px, py = shifted[-1]
            dx, dy = tan1[0], tan1[1]
            if abs(dx) > 1e-6:
                s = (wx - px) / dx
                if s > 0.0 and math.isfinite(s):
                    ny = py + s * dy
                    ny = min(max(ny, y_lo_b), y_hi_b)
                    if ast_bottom:
                        ny = max(ny, y_ast)
                    elif ast_top:
                        ny = min(ny, y_ast)
                    shifted.append((wx, ny))

    if y_ast is not None and ast_tf in ("bottom", "top"):
        shifted_t, _, _ = _check6_trim_polyline_at_ast_elevation(
            shifted, y_ast=y_ast, tension_face=ast_tf
        )
        if len(shifted_t) < 2:
            return
        shifted = shifted_t

    path_g = _check6_polyline_to_path_svg(shifted)
    if path_g:
        fig.add_shape(
            type="path",
            path=path_g,
            line=dict(color=green, width=2),
        )
    x_lo_arr = min(x_lo_b, wx) if wx is not None else x_lo_b
    x_hi_arr = max(x_hi_b, wx) if wx is not None else x_hi_b
    y_lo_arr = max(y_lo_b, y_ast) if ast_bottom else y_lo_b
    y_hi_arr = min(y_hi_b, y_ast) if ast_top else y_hi_b
    half = max(0.024 * D, 10.0)
    n = len(shifted)
    n_arrows = 8
    step = max(1, (n - 4) // max(n_arrows, 1))
    arrow_indices = list(range(2, n - 2, step))
    if arrow_indices:
        arrow_indices.pop(0)
    for i in arrow_indices:
        px, py = shifted[i]
        qx, qy = shifted[i + 1]
        rx, ry = shifted[i - 1]
        tx, ty = qx - rx, qy - ry
        tlen = math.hypot(tx, ty)
        if tlen < 1e-9:
            continue
        tx, ty = tx / tlen, ty / tlen
        # Reversed along path: arrowhead toward decreasing arc-length (support / tension end)
        x_tip = min(max(px - tx * half, x_lo_arr), x_hi_arr)
        y_tip = min(max(py - ty * half, y_lo_arr), y_hi_arr)
        x_tail = min(max(px + tx * half, x_lo_arr), x_hi_arr)
        y_tail = min(max(py + ty * half, y_lo_arr), y_hi_arr)
        fig.add_annotation(
            x=x_tip,
            y=y_tip,
            ax=x_tail,
            ay=y_tail,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.78,
            arrowwidth=1.85,
            arrowcolor=green,
        )

    i_start = 2
    if n > i_start + 1:
        px, py = shifted[i_start]
        qx, qy = shifted[i_start + 1]
        rx, ry = shifted[i_start - 1]
        tx, ty = qx - rx, qy - ry
        tlen = math.hypot(tx, ty)
        if tlen >= 1e-9:
            tx, ty = tx / tlen, ty / tlen
            x_tip = min(max(px - tx * half, x_lo_arr), x_hi_arr)
            y_tip = min(max(py - ty * half, y_lo_arr), y_hi_arr)
            x_tail = min(max(px + tx * half, x_lo_arr), x_hi_arr)
            y_tail = min(max(py + ty * half, y_lo_arr), y_hi_arr)
            fig.add_annotation(
                x=x_tip,
                y=y_tip,
                ax=x_tail,
                ay=y_tail,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=0.78,
                arrowwidth=1.85,
                arrowcolor=green,
            )

    # Three black arrows: normal to the path, along the green offset direction (into the web /
    # away from the crack); anchor shifted slightly along that normal so they clear the green stroke.
    lo_i, hi_i = 2, n - 3
    if n >= 4 and hi_i >= lo_i:
        black_half = max(0.034 * D, 15.0)
        seen_bi: set[int] = set()
        for frac in (0.30, 0.5, 0.8):
            bi = lo_i + int(round((hi_i - lo_i) * frac))
            bi = min(max(bi, lo_i), hi_i)
            if bi in seen_bi:
                continue
            seen_bi.add(bi)
            px, py = shifted[bi]
            t_b = min(1.0, max(0.0, (t_idx0 + bi) / max(1, n_param - 1)))
            if geom is not None:
                ox, oy = _offset_normal_at_t(t_b)
            else:
                qx, qy = shifted[bi + 1]
                rx, ry = shifted[bi - 1]
                ttx, tty = qx - rx, qy - ry
                tl = math.hypot(ttx, tty)
                if tl < 1e-9:
                    continue
                ttx, tty = ttx / tl, tty / tl
                crx, cry = tty, -ttx
                if crx > 0.0:
                    crx, cry = -tty, ttx
                tl2 = math.hypot(crx, cry)
                if tl2 < 1e-9:
                    continue
                ox, oy = -crx / tl2, -cry / tl2
            bx, by = -ox, -oy
            sep_mm = max(0.038 * D, 15.0)
            cx = px + ox * sep_mm
            cy = py + oy * sep_mm
            x_tip = min(max(cx - bx * black_half, x_lo_arr), x_hi_arr)
            y_tip = min(max(cy - by * black_half, y_lo_arr), y_hi_arr)
            x_tail = min(max(cx + bx * black_half, x_lo_arr), x_hi_arr)
            y_tail = min(max(cy + by * black_half, y_lo_arr), y_hi_arr)
            fig.add_annotation(
                x=x_tip,
                y=y_tip,
                ax=x_tail,
                ay=y_tail,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=0.72,
                arrowwidth=1.9,
                arrowcolor="#111111",
            )


def _check6_polyline_unit_tangent(
    pts: list[tuple[float, float]], i: int
) -> tuple[float, float]:
    n = len(pts)
    if n < 2:
        return (1.0, 0.0)
    if i <= 0:
        dx = float(pts[1][0]) - float(pts[0][0])
        dy = float(pts[1][1]) - float(pts[0][1])
    elif i >= n - 1:
        dx = float(pts[n - 1][0]) - float(pts[n - 2][0])
        dy = float(pts[n - 1][1]) - float(pts[n - 2][1])
    else:
        dx = float(pts[i + 1][0]) - float(pts[i - 1][0])
        dy = float(pts[i + 1][1]) - float(pts[i - 1][1])
    ln = math.hypot(dx, dy)
    if ln < 1e-12:
        return (1.0, 0.0)
    return dx / ln, dy / ln


def _check6_unit_normal_from_tangent_toward_compression(
    tx: float, ty: float, compression_face: str
) -> tuple[float, float]:
    n0x, n0y = -float(ty), float(tx)
    refy = 1.0 if str(compression_face).strip().lower() == "top" else -1.0
    if n0y * refy < 0.0:
        n0x, n0y = -n0x, -n0y
    return n0x, n0y


def _check6_polyline_offset_toward_compression(
    pts: list[tuple[float, float]],
    *,
    gap_mm: float,
    compression_face: str,
    D_mm: float,
    L_seg_mm: float,
    y_bot: float,
    y_top: float,
    normal_sign: float = 1.0,
) -> list[tuple[float, float]]:
    if len(pts) < 2 or float(gap_mm) <= 0:
        return []
    Ls = max(float(L_seg_mm), 1.0)
    D = max(float(D_mm), 1.0)
    x_m = max(0.018 * Ls, 0.022 * D, 12.0)
    y_m = max(0.014 * D, 8.0)
    x_lo, x_hi = x_m, Ls - x_m
    y_lo, y_hi = float(y_bot) + y_m, float(y_top) - y_m
    if x_hi <= x_lo or y_hi <= y_lo:
        return []
    g = float(gap_mm)
    sgn = float(normal_sign)
    out: list[tuple[float, float]] = []
    n = len(pts)
    for i in range(n):
        tx, ty = _check6_polyline_unit_tangent(pts, i)
        nx, ny = _check6_unit_normal_from_tangent_toward_compression(
            tx, ty, compression_face
        )
        x = float(pts[i][0]) + g * nx * sgn
        y = float(pts[i][1]) + g * ny * sgn
        x = min(max(x, x_lo), x_hi)
        y = min(max(y, y_lo), y_hi)
        out.append((x, y))
    return out


def _check6_add_green_black_flow_arrows_on_polyline(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    *,
    D_mm: float,
    L_seg_mm: float,
    y_bot: float,
    y_top: float,
    green: str = "#2e7d32",
    show_green_tangent_arrows: bool = True,
) -> None:
    """Green arrows along local tangent (toward toe); black perpendicular, open end left of green, head right (L→R)."""
    if len(pts) < 5:
        return
    Ls = max(float(L_seg_mm), 1.0)
    D = max(float(D_mm), 1.0)
    x_m = max(0.018 * Ls, 0.022 * D, 12.0)
    y_m = max(0.014 * D, 8.0)
    x_lo_arr = x_m
    x_hi_arr = Ls - x_m
    y_lo_arr = float(y_bot) + y_m
    y_hi_arr = float(y_top) - y_m
    if x_hi_arr <= x_lo_arr or y_hi_arr <= y_lo_arr:
        return

    half = max(0.024 * D, 10.0)
    n_pts = len(pts)
    if show_green_tangent_arrows:
        n_arrows = 8
        step = max(1, (n_pts - 4) // max(n_arrows, 1))
        arrow_indices = list(range(2, n_pts - 2, step))
        if arrow_indices:
            arrow_indices.pop(0)
        for i in arrow_indices:
            if i <= 0 or i >= n_pts - 1:
                continue
            px, py = pts[i]
            tx, ty = _check6_polyline_unit_tangent(pts, i)
            if math.hypot(tx, ty) < 1e-12:
                continue
            gx_tip = min(max(px - tx * half, x_lo_arr), x_hi_arr)
            gy_tip = min(max(py - ty * half, y_lo_arr), y_hi_arr)
            gx_tail = min(max(px + tx * half, x_lo_arr), x_hi_arr)
            gy_tail = min(max(py + ty * half, y_lo_arr), y_hi_arr)
            fig.add_annotation(
                x=gx_tip,
                y=gy_tip,
                ax=gx_tail,
                ay=gy_tail,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=0.78,
                arrowwidth=1.85,
                arrowcolor=green,
            )

        i_start = 2
        if n_pts > i_start + 1:
            px, py = pts[i_start]
            tx, ty = _check6_polyline_unit_tangent(pts, i_start)
            if math.hypot(tx, ty) >= 1e-12:
                gx_tip = min(max(px - tx * half, x_lo_arr), x_hi_arr)
                gy_tip = min(max(py - ty * half, y_lo_arr), y_hi_arr)
                gx_tail = min(max(px + tx * half, x_lo_arr), x_hi_arr)
                gy_tail = min(max(py + ty * half, y_lo_arr), y_hi_arr)
                fig.add_annotation(
                    x=gx_tip,
                    y=gy_tip,
                    ax=gx_tail,
                    ay=gy_tail,
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    text="",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=0.78,
                    arrowwidth=1.85,
                    arrowcolor=green,
                )

    lo_i, hi_i = 2, n_pts - 3
    if hi_i >= lo_i:
        sep_tail = max(0.052 * D, 20.0)
        sep_head = max(0.041 * D, 16.0)
        gap_from_green = max(0.034 * D, 15.0)
        # Parallel offset (+n_r): arrow line does not pass through the green polyline (clear gap).
        seen_bi: set[int] = set()
        for frac in (0.30, 0.5, 0.8):
            bi = lo_i + int(round((hi_i - lo_i) * frac))
            bi = min(max(bi, lo_i), hi_i)
            if bi in seen_bi:
                continue
            seen_bi.add(bi)
            px, py = pts[bi]
            tx, ty = _check6_polyline_unit_tangent(pts, bi)
            if math.hypot(tx, ty) < 1e-12:
                continue
            # Right-hand normal to forward tangent (toe → tip): tail on +n_r, head on −n_r.
            rx, ry = float(ty), -float(tx)
            rlen = math.hypot(rx, ry)
            if rlen < 1e-12:
                continue
            rx, ry = rx / rlen, ry / rlen
            tail_x = px + (sep_tail + gap_from_green) * rx
            tail_y = py + (sep_tail + gap_from_green) * ry
            head_x = px + (gap_from_green - sep_head) * rx
            head_y = py + (gap_from_green - sep_head) * ry
            tail_x = min(max(tail_x, x_lo_arr), x_hi_arr)
            tail_y = min(max(tail_y, y_lo_arr), y_hi_arr)
            head_x = min(max(head_x, x_lo_arr), x_hi_arr)
            head_y = min(max(head_y, y_lo_arr), y_hi_arr)
            # Plotly: arrow from (ax,ay) to (x,y); arrowhead at (x,y). Open end left, head right of green.
            fig.add_annotation(
                x=tail_x,
                y=tail_y,
                ax=head_x,
                ay=head_y,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=0.72,
                arrowwidth=1.9,
                arrowcolor="#111111",
            )


def _check6_shear_ligatures_active(
    *, s_mm: float, lig_legs: int, asv_mm2: float | None = None
) -> bool:
    """True only when current shear ligatures are present (no placeholder stirrups)."""
    if float(s_mm) <= 1e-6:
        return False
    if int(lig_legs) < 2:
        return False
    if asv_mm2 is not None and float(asv_mm2) <= 1e-6:
        return False
    return True


def _check6_add_mcft_mechanism_labels(
    fig: go.Figure,
    *,
    D: float,
    L_seg: float,
    L_d_core: float,
    crack_pts: list[tuple[float, float]],
    mean_green_pts: list[tuple[float, float]],
    theta_lbl_x: float,
    theta_lbl_y: float,
    cx_c: float,
    y_c_top: float,
    y_c_bot: float,
    y_steel: float,
    ast_lbl_x: float,
    ast_arrow_x0: float,
    ast_arrow_x1: float,
    tension_face: str,
    side_n: str,
    y_bot_beam: float,
    y_top_beam: float,
    y_stirr_bot: float,
    y_stirr_top: float,
    stirrup_xds: list[float],
    show_region_labels: bool,
    support_X: float,
    x_disp,
) -> None:
    """
    Check 5 only: V_cr / V_ca / V_cc / V_d beside crack, green strut, compression block, and tie.
    Positions are nudged to reduce overlap with linework and each other (no geometry changes).
    """
    if len(crack_pts) < 3 or len(mean_green_pts) < 2:
        return
    Df = max(float(D), 1.0)
    Ls = max(float(L_seg), 1.0)
    tf = str(tension_face).strip().lower()
    sn = str(side_n).strip().lower()

    t_samp = 0.46
    nc, ng = len(crack_pts), len(mean_green_pts)
    ic = min(max(int(round(t_samp * (nc - 1))), 1), nc - 2)
    ig = min(max(int(round(t_samp * (ng - 1))), 1), ng - 2)
    crx, cry = float(crack_pts[ic][0]), float(crack_pts[ic][1])
    gpx, gpy = float(mean_green_pts[ig][0]), float(mean_green_pts[ig][1])
    dgx, dgy = gpx - crx, gpy - cry
    glen = math.hypot(dgx, dgy)
    if glen < 1e-6:
        return
    ux, uy = dgx / glen, dgy / glen
    off_cr = max(0.026 * Df, 16.0)
    off_ca = max(0.028 * Df, 17.0)
    vcr_x, vcr_y = crx - ux * off_cr, cry - uy * off_cr
    vca_x, vca_y = gpx + ux * off_ca, gpy + uy * off_ca

    # V_cc: compression-side block (top fibre for sagging, bottom for hogging)
    c_hw = max(0.028 * Df, 11.0)
    if tf == "bottom":
        y_cc = float(y_c_top) - max(0.022 * Df, 10.0)
        vcc_y = min(max(y_cc, float(y_c_bot) + c_hw), float(y_c_top) - 0.012 * Df)
    else:
        y_cc = float(y_c_bot) + max(0.022 * Df, 10.0)
        vcc_y = min(max(y_cc, float(y_c_bot) + 0.012 * Df), float(y_c_top) - c_hw)
    if sn == "right":
        vcc_x = float(cx_c) - max(0.055 * Df, 22.0)
        vcc_ax = "right"
    elif sn == "internal":
        vcc_x = float(cx_c) - max(0.048 * Df, 20.0)
        vcc_ax = "right"
    else:
        vcc_x = float(cx_c) + max(0.055 * Df, 22.0)
        vcc_ax = "left"

    # V_d: beside blue Ast / crack crossing — offset up and to the span-ward side in x
    ys = float(y_steel)
    ast_lo = min(float(ast_arrow_x0), float(ast_arrow_x1))
    ast_hi = max(float(ast_arrow_x0), float(ast_arrow_x1))
    crack_cross: list[tuple[float, float]] = []
    for k in range(len(crack_pts) - 1):
        x0, y0 = float(crack_pts[k][0]), float(crack_pts[k][1])
        x1, y1 = float(crack_pts[k + 1][0]), float(crack_pts[k + 1][1])
        if abs(y1 - y0) < 1e-9:
            continue
        y_lo, y_hi = (y0, y1) if y0 <= y1 else (y1, y0)
        if y_lo - 1e-6 <= ys <= y_hi + 1e-6:
            t = (ys - y0) / (y1 - y0)
            if -1e-5 <= t <= 1.0 + 1e-5:
                xi = x0 + t * (x1 - x0)
                crack_cross.append((xi, ys))
    if crack_cross:
        in_ast = [
            p
            for p in crack_cross
            if ast_lo - 0.12 * Ls <= p[0] <= ast_hi + 0.12 * Ls
        ]
        pool = in_ast if in_ast else crack_cross
        if sn == "right":
            ix, iy = min(pool, key=lambda p: p[0])
        else:
            ix, iy = max(pool, key=lambda p: p[0])
    else:
        ast_mid = 0.5 * (ast_lo + ast_hi)
        ix, iy = ast_mid, ys
        best_d = 1e18
        best_xy = (ix, iy)
        for k in range(len(crack_pts) - 1):
            x0, y0 = float(crack_pts[k][0]), float(crack_pts[k][1])
            x1, y1 = float(crack_pts[k + 1][0]), float(crack_pts[k + 1][1])
            abx, aby = x1 - x0, y1 - y0
            al = abx * abx + aby * aby
            if al < 1e-18:
                continue
            t = max(0.0, min(1.0, ((ast_mid - x0) * abx + (ys - y0) * aby) / al))
            qx, qy = x0 + t * abx, y0 + t * aby
            d = math.hypot(ast_mid - qx, ys - qy)
            if d < best_d:
                best_d = d
                best_xy = (qx, qy)
        ix, iy = best_xy
    step_x = max(0.030 * Df, 16.0)
    step_y = max(0.032 * Df, 17.0)
    dir_x = -1.0 if sn == "right" else 1.0
    vd_x = ix + dir_x * step_x
    vd_y = iy + step_y
    vd_yanchor = "bottom"
    vd_xanchor = "left" if dir_x > 0 else "right"
    vd_x = min(max(vd_x, 0.05 * Ls), Ls - 0.05 * Ls)
    vd_y = min(max(vd_y, float(y_bot_beam) + 0.04 * Df), float(y_top_beam) - 0.04 * Df)

    # Region label apertures (below soffit)
    reg_y: float | None = None
    reg_x1: float | None = None
    reg_x2: float | None = None
    if show_region_labels:
        reg_y = float(y_bot_beam) - max(0.056 * Df, 28.0)
        L_rem = max(L_seg - L_d_core, 0.08 * L_seg)
        if sn == "right":
            reg_x1 = float(x_disp(0.52 * L_d_core))
            reg_x2 = float(x_disp(L_d_core + 0.50 * L_rem))
        elif sn == "internal":
            reg_x1 = float(support_X) + 0.42 * min(
                L_d_core, max(L_seg - support_X, 1.0) * 0.92
            )
            reg_x2 = max(0.06 * L_seg, support_X * 0.42)
        else:
            reg_x1 = float(x_disp(0.48 * L_d_core))
            reg_x2 = float(x_disp(L_d_core + 0.50 * L_rem))

    min_l = max(0.048 * Df, 26.0)
    pts: list[list[float]] = [
        [vcr_x, vcr_y],
        [vca_x, vca_y],
        [vcc_x, vcc_y],
        [vd_x, vd_y],
    ]

    def _too_close_stirrup(px: float, py: float) -> bool:
        ys_lo = min(float(y_stirr_bot), float(y_stirr_top))
        ys_hi = max(float(y_stirr_bot), float(y_stirr_top))
        vm = max(0.02 * Df, 6.0)
        for xv in stirrup_xds:
            if abs(float(px) - float(xv)) < max(0.018 * Df, 7.0):
                if ys_lo - vm <= py <= ys_hi + vm:
                    return True
        return False

    def _dist_to_seg(
        px: float, py: float, ax: float, ay: float, bx: float, by: float
    ) -> float:
        abx, aby = bx - ax, by - ay
        t = ((px - ax) * abx + (py - ay) * aby) / max(abx * abx + aby * aby, 1e-12)
        t = max(0.0, min(1.0, t))
        qx, qy = ax + t * abx, ay + t * aby
        return math.hypot(px - qx, py - qy)

    def _min_dist_polyline(px: float, py: float, poly: list[tuple[float, float]]) -> float:
        m = 1e18
        for k in range(len(poly) - 1):
            m = min(
                m,
                _dist_to_seg(
                    px,
                    py,
                    float(poly[k][0]),
                    float(poly[k][1]),
                    float(poly[k + 1][0]),
                    float(poly[k + 1][1]),
                ),
            )
        return m

    def _repel_from_features(
        px: float, py: float, *, vd_label: bool = False
    ) -> tuple[float, float]:
        x, y = float(px), float(py)
        # Theta label
        dth = math.hypot(x - float(theta_lbl_x), y - float(theta_lbl_y))
        if dth < max(0.10 * Df, 36.0):
            s = max(0.10 * Df, 36.0) - dth + 4.0
            if dth > 1e-6:
                x += s * (x - theta_lbl_x) / dth
                y += s * (y - theta_lbl_y) / dth
            else:
                x += s
        # Vertical compression resultant
        if abs(x - float(cx_c)) < max(0.032 * Df, 14.0):
            if float(y_c_bot) - 0.02 * Df <= y <= float(y_c_top) + 0.02 * Df:
                step = max(0.042 * Df, 18.0)
                x += step if x >= float(cx_c) else -step
        # Ast horizontal bar (keep V_d readable beside crack–Ast crossing)
        if not vd_label and abs(y - float(y_steel)) < max(0.022 * Df, 10.0):
            lo, hi = (
                (min(ast_arrow_x0, ast_arrow_x1), max(ast_arrow_x0, ast_arrow_x1))
                if ast_arrow_x0 <= ast_arrow_x1
                else (min(ast_arrow_x1, ast_arrow_x0), max(ast_arrow_x1, ast_arrow_x0))
            )
            if lo - 0.03 * Ls <= x <= hi + 0.03 * Ls:
                y += max(0.034 * Df, 14.0) if y >= float(y_steel) else -max(0.034 * Df, 14.0)
        # Crack / green polylines
        if not vd_label:
            if _min_dist_polyline(x, y, crack_pts) < max(0.018 * Df, 9.0):
                x -= ux * max(0.022 * Df, 10.0)
                y -= uy * max(0.022 * Df, 10.0)
            if _min_dist_polyline(x, y, mean_green_pts) < max(0.018 * Df, 9.0):
                x += ux * max(0.022 * Df, 10.0)
                y += uy * max(0.022 * Df, 10.0)
        if _too_close_stirrup(x, y):
            x += max(0.035 * Df, 14.0) * (1.0 if x < 0.5 * Ls else -1.0)
        if reg_y is not None and reg_x1 is not None and reg_x2 is not None:
            if abs(y - reg_y) < max(0.05 * Df, 22.0):
                rx_lo = min(reg_x1, reg_x2) - 0.06 * Ls
                rx_hi = max(reg_x1, reg_x2) + 0.06 * Ls
                if rx_lo <= x <= rx_hi:
                    y = reg_y + max(0.08 * Df, 30.0)
        x = min(max(x, 0.04 * Ls), Ls - 0.04 * Ls)
        y = min(max(y, float(y_bot_beam) + 0.03 * Df), float(y_top_beam) - 0.03 * Df)
        return x, y

    for _ in range(14):
        for i in range(len(pts)):
            pts[i][0], pts[i][1] = _repel_from_features(
                pts[i][0], pts[i][1], vd_label=(i == 3)
            )
        moved = False
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dx = pts[j][0] - pts[i][0]
                dy = pts[j][1] - pts[i][1]
                d = math.hypot(dx, dy)
                if d < min_l and d > 1e-9:
                    push = 0.52 * (min_l - d)
                    fx, fy = dx / d, dy / d
                    pts[i][0] -= fx * push
                    pts[i][1] -= fy * push
                    pts[j][0] += fx * push
                    pts[j][1] += fy * push
                    moved = True
        if not moved:
            break
        for i in range(len(pts)):
            pts[i][0], pts[i][1] = _repel_from_features(
                pts[i][0], pts[i][1], vd_label=(i == 3)
            )

    halo = dict(
        bgcolor="rgba(255,255,255,0.90)",
        borderpad=3,
        bordercolor="rgba(255,255,255,0)",
    )
    col_cr = "rgba(38,40,44,0.96)"
    col_ca = "#1b5e20"
    col_cc = "#c41e3a"
    col_vd = "#1565c0"

    fig.add_annotation(
        x=pts[0][0],
        y=pts[0][1],
        text="<i>V</i><sub>cr</sub>",
        showarrow=False,
        font=dict(size=10, color=col_cr),
        xref="x",
        yref="y",
        xanchor="center",
        yanchor="middle",
        **halo,
    )
    fig.add_annotation(
        x=pts[1][0],
        y=pts[1][1],
        text="<i>V</i><sub>ca</sub>",
        showarrow=False,
        font=dict(size=10, color=col_ca),
        xref="x",
        yref="y",
        xanchor="center",
        yanchor="middle",
        **halo,
    )
    fig.add_annotation(
        x=pts[2][0],
        y=pts[2][1],
        text="<i>V</i><sub>cc</sub>",
        showarrow=False,
        font=dict(size=10, color=col_cc),
        xref="x",
        yref="y",
        xanchor=vcc_ax,
        yanchor="middle",
        **halo,
    )
    fig.add_annotation(
        x=pts[3][0],
        y=pts[3][1],
        text="<i>V</i><sub>d</sub>",
        showarrow=False,
        font=dict(size=10, color=col_vd),
        xref="x",
        yref="y",
        xanchor=vd_xanchor,
        yanchor=vd_yanchor,
        **halo,
    )


def _check6_add_web_crushing_stm_overlay(
    fig: go.Figure,
    *,
    D: float,
    L_seg: float,
    support_face_x: float,
    x_toe: float,
    y_toe: float,
    y_steel: float,
    y_top_beam: float,
    y_bot_beam: float,
    tension_face: str,
    side_n: str,
    theta_v_deg: float,
    pad_x_toe: float,
) -> None:
    """
    D-region strut-and-tie sketch for web-crushing: red diagonal strut at governing **θ_v**
    (same convention as ``_check6_unit_toe_to_tip_crack`` / MCFT crack), tie cue at Ast,
    d_v bracket, and V_u,max label.
    """
    Df = max(float(D), 1.0)
    Ls = max(float(L_seg), 1.0)
    pad = max(float(pad_x_toe), 6.0)
    tf = str(tension_face).strip().lower()
    sn = str(side_n or "left").strip().lower()
    if tf == "bottom":
        y_comp = float(y_top_beam) - max(0.042 * Df, 13.0)
    else:
        y_comp = float(y_bot_beam) + max(0.042 * Df, 13.0)

    lo = min(float(support_face_x), float(x_toe))
    hi = max(float(support_face_x), float(x_toe))
    tie_inset = max(0.026 * Ls, 11.0)
    x_tie0 = lo + tie_inset
    x_tie1 = hi - tie_inset
    if x_tie1 <= x_tie0 + 2.0:
        x_tie0, x_tie1 = lo, hi

    x_strut_bot = min(max(float(support_face_x), x_tie0), x_tie1)

    x0, y0 = float(x_strut_bot), float(y_steel)
    y_lo = float(y_bot_beam) + 0.018 * Df
    y_hi = float(y_top_beam) - 0.018 * Df

    th = math.radians(max(1.0, min(float(theta_v_deg), 89.0)))
    uxn, uyn = _check6_unit_toe_to_tip_crack(
        support_side=sn,
        tension_face=tf,
        theta_v_rad=th,
    )
    uln = math.hypot(uxn, uyn)
    if uln > 1e-9:
        uxn, uyn = uxn / uln, uyn / uln
    # Half-line from tie toward compression (same θ; flip 180° if needed).
    if (float(y_comp) - y0) * uyn < 0:
        uxn, uyn = -uxn, -uyn

    # End on compression band so strut lies exactly at θ_v (slope dy/dx = uyn/uxn).
    if abs(uyn) > 1e-6:
        t_ray = (float(y_comp) - y0) / uyn
        x1 = x0 + uxn * t_ray
        y1 = float(y_comp)
    elif abs(uxn) > 1e-6:
        t_ray = max(0.2 * Ls, 40.0)
        x1 = x0 + uxn * t_ray
        y1 = y0
    else:
        x1, y1 = x0 + 0.25 * Ls, y_comp

    def _clip_preserving_slope() -> None:
        nonlocal x1, y1
        if x1 < pad or x1 > Ls - pad:
            x1 = min(max(x1, pad), Ls - pad)
            if abs(uxn) > 1e-6:
                y1 = y0 + (uyn / uxn) * (x1 - x0)
        if y1 < y_lo or y1 > y_hi:
            y1 = min(max(y1, y_lo), y_hi)
            if abs(uyn) > 1e-6:
                x1 = x0 + (uxn / uyn) * (y1 - y0)

    _clip_preserving_slope()
    _clip_preserving_slope()

    c_red = "#c41e3a"
    ast_blue = "#1565c0"
    teach_col = "rgba(55,71,79,0.78)"

    fig.add_trace(
        go.Scatter(
            x=[x0, x1],
            y=[y0, y1],
            mode="lines",
            line=dict(color=c_red, width=3.6),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    xm, ym = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    # θ label: just above the blue Ast line (y_steel); x biased left (support-ward).
    theta_x = 0.58 * float(x0) + 0.42 * float(x_toe)
    theta_x -= max(0.030 * Ls, 20.0)
    theta_x = min(max(theta_x, pad + max(0.02 * Ls, 10.0)), Ls - pad - max(0.02 * Ls, 10.0))
    if tf == "bottom":
        theta_y = float(y_steel) + max(0.007 * Df, 5.0)
        theta_yanchor = "bottom"
    else:
        theta_y = float(y_steel) - max(0.007 * Df, 5.0)
        theta_yanchor = "top"
    span_sign = 1.0 if uxn >= 0.0 else -1.0
    theta_xanchor = "right" if span_sign > 0 else "left"
    fig.add_annotation(
        x=theta_x,
        y=theta_y,
        text=f"θ = {float(theta_v_deg):.1f}°",
        showarrow=False,
        font=dict(size=8, color="rgba(31,42,68,0.90)"),
        xref="x",
        yref="y",
        xanchor=theta_xanchor,
        yanchor=theta_yanchor,
    )
    fig.add_annotation(
        x=xm - 0.012 * Ls * uxn,
        y=ym - 0.020 * Df * abs(uyn) - 0.012 * Df,
        text="<i>Diagonal compression strut</i>",
        showarrow=False,
        font=dict(size=8, color="rgba(196,30,58,0.92)"),
        xref="x",
        yref="y",
    )
    # Tie (Ast): span-ward of θ (same text row); anchors keep a gap for left vs right support.
    tie_ast_x = float(theta_x) + span_sign * max(0.048 * Ls, 36.0)
    tie_ast_x = min(max(tie_ast_x, pad + max(0.015 * Ls, 10.0)), Ls - pad - max(0.015 * Ls, 10.0))
    tie_xanchor = "left" if span_sign > 0 else "right"
    fig.add_annotation(
        x=tie_ast_x,
        y=theta_y,
        text="<i>Tie (</i><b>Ast</b><i>)</i>",
        showarrow=False,
        font=dict(size=8, color=ast_blue),
        xref="x",
        yref="y",
        xanchor=tie_xanchor,
        yanchor=theta_yanchor,
    )

    x_dv = float(x_toe) - max(0.016 * Ls, 9.0)
    x_dv = max(pad, min(x_dv, Ls - pad))
    y_lo_dv = min(float(y_steel), float(y_comp))
    y_hi_dv = max(float(y_steel), float(y_comp))
    if y_hi_dv - y_lo_dv > max(0.05 * Df, 14.0):
        fig.add_shape(
            type="line",
            x0=x_dv,
            y0=y_lo_dv,
            x1=x_dv,
            y1=y_hi_dv,
            line=dict(color=teach_col, width=1.25, dash="dot"),
        )
        fig.add_annotation(
            x=x_dv - max(0.014 * Ls, 8.0),
            y=0.5 * (y_lo_dv + y_hi_dv),
            text="<i>d<sub>v</sub></i>",
            showarrow=False,
            font=dict(size=8, color=teach_col),
            xref="x",
            yref="y",
            xanchor="right",
            yanchor="middle",
        )

    fig.add_annotation(
        x=0.5 * (lo + hi),
        y=float(y_bot_beam) - max(0.048 * Df, 24.0),
        text="<i>V</i><sub>u,max</sub> web-crushing limit",
        showarrow=False,
        font=dict(size=9, color="rgba(31,42,68,0.88)"),
        xref="x",
        yref="y",
        xanchor="center",
        yanchor="top",
    )


def build_shear_check6_support_transfer_diagram(
    *,
    layout: dict | None,
    D_mm: float,
    d_mm: float,
    moment_sign: str,
    support_draw_kind: str,
    critical_support_side: str,
    s_lig_mm: float,
    lig_legs: int,
    lig_d_mm: float = 10.0,
    asv_mm2: float | None = None,
    height: int = 320,
    fc_mpa: float | None = None,
    fsy_mpa: float | None = None,
    theta_v_deg: float | None = None,
    d_v_mm: float | None = None,
    show_mean_crack_guideline: bool = True,
    show_mean_green_flow_pulse: bool = True,
    show_mean_green_flow_arrows: bool = True,
    show_green_strut_flow: bool = False,
    show_compression_resultant: bool = True,
    show_shear_teaching_overlay: bool = False,
    show_region_labels: bool = True,
    show_mcft_mechanism_labels: bool = False,
    crack_bulge_scale: float = 1.28,
    crack_jag_scale: float = 0.88,
    web_crushing_stm: bool = False,
) -> go.Figure:
    """
    Local support-region schematic: ~1.5d–2d D-region from the critical support plus ~0.5d–1.0d
    into the adjacent shear span. L_d_core is unchanged from the band formulas; the flexural-shear
    run uses the same nominal L_span_extra scaled by flex_leg_scale (no cap that re-balances D vs flex).
    x_fs = distance from the governing support face into the span (mm);
    display X places the support on the window boundary (left end → X=0, right end → X=L_seg).

    Optional display variants (Check 5 vs Check 7): omit mean crack guideline, strut-flow overlay,
    compression ``C``, green/black load-path arrows (``show_mean_green_flow_arrows``), and teaching
    geometry via the ``show_*`` flags. Check 5 defaults omit the
    grey ``d_v`` / ``d_v cot θ_v`` teaching overlay; Step 7 passes ``show_shear_teaching_overlay=True``
    for that construction only. When the mean crack guideline is enabled, the green path is a
    parallel offset (normal to the path) of the crack’s smooth arched Bézier centreline (same
    backbone as the black crack, without jag). With ``show_mean_green_flow_pulse`` and
    ``show_compression_resultant``, the pulse follows one
    continuous path: top of **C** → down **C** → green transfer curve (tip to Ast) → **Ast** tie
    toward the support (same MCFT dashed + sliding-window animation). Otherwise the pulse is green-only
    or hidden when the pulse flag is off (solid green + optional tangent arrows). Black normal arrows
    are unchanged. The θ marker at the
    toe shows the angle from the bottom beam edge to the *drawn* crack tangent (not the nominal MCFT
    input). All stirrups render as one dark grey.

    ``show_mcft_mechanism_labels`` (Check 5): adds italic subscript labels ``V_cr``, ``V_ca``,
    ``V_cc``, ``V_d`` beside the crack, green strut, compression block, and tie; geometry unchanged.

    ``web_crushing_stm`` (Check 9): same beam/support/inset/stirrups/Ast as Checks 5/7, but omits the
    MCFT crack/green path and draws a D-region strut-and-tie overlay (red strut, tie at Ast) for the
    web-crushing schematic.
    """
    fig = go.Figure()
    mean_green_for_flow: list[tuple[float, float]] = []
    flow_c_cx: float | None = None
    flow_c_y_top: float | None = None
    flow_c_y_bot: float | None = None
    shape_kind, dims = _check6_shape_kind_and_dims(layout)
    D = max(float(D_mm), 1.0)
    d_use = max(float(d_mm), 0.01 * D)
    d_v_use = float(d_v_mm) if d_v_mm is not None else d_use
    d_v_use = max(d_v_use, 0.05 * D, 1.0)
    L_d_core = max(1.5 * d_use, min(2.0 * d_use, 0.52 * D))
    L_span_extra = max(0.5 * d_use, min(1.0 * d_use, 0.30 * D))
    # D-depth stays per formulas; flexural-shear leg lengthened by a fixed factor (no L_seg squeeze).
    flex_leg_scale = 2.75
    L_raw = float(L_d_core) + float(L_span_extra) * flex_leg_scale
    L_seg_cap = max(4.25 * d_use, 1.22 * D, L_raw)
    L_seg = max(2.0 * d_use, min(L_raw, L_seg_cap))

    inset_pts_uv, width_sec = _check6_section_inset_polygon_uv(shape_kind, dims)
    width_sec = max(float(width_sec), 1.0)
    inset_span_mm = min(
        width_sec,
        max(0.52 * L_seg, 0.45 * d_use, 0.30 * D, 200.0),
    )
    inset_span_mm *= 0.5
    # Slightly wider grey band toward the span (left when inset is on the right, etc.).
    grey_extend_mm = max(0.062 * L_seg, 0.09 * D, 32.0)
    grey_span_mm = min(inset_span_mm + grey_extend_mm, 0.90 * L_seg)

    reo = (layout or {}).get("reo") or {}
    try:
        cover_bot = float(reo.get("cover_bot", 40.0))
        cover_top = float(reo.get("cover_top", 40.0))
        db_bot = float(reo.get("db_bot", reo.get("db_bot_1", 20.0)))
        db_top = float(reo.get("db_top", reo.get("db_top_1", 16.0)))
    except Exception:
        cover_bot, cover_top, db_bot, db_top = 40.0, 40.0, 20.0, 16.0

    ms = str(moment_sign or "positive").strip().lower()
    lig_d = float(reo.get("lig_d", 0.0) or 0.0)
    fallback_y = (
        D - (cover_bot + lig_d + 0.5 * db_bot) if ms != "negative" else cover_top + 0.5 * db_top
    )
    layer_geom = resolve_bending_layer_geometry(
        layout,
        moment_sign=str(moment_sign or "positive"),
        D=D,
        fallback_y_tension=fallback_y,
    )
    y_tension_v = float(layer_geom["y_tension_centroid"])
    tension_face = str(layer_geom["tension_face"])
    compression_face = str(layer_geom["compression_face"])

    y_steel = _check6_y_display(D, y_tension_v)

    side_n = str(critical_support_side or "left").strip().lower()
    if side_n not in ("left", "right", "internal"):
        side_n = "left"

    # x_fs: 0 at support face, increases into the governing shear span (same convention for all cases).
    if side_n == "internal":
        x_sup_disp = 0.5 * L_seg

        def x_disp(x_fs: float) -> float:
            return x_sup_disp + float(x_fs)

        support_X = x_sup_disp
        inset_on_right = True
    elif side_n == "right":

        def x_disp(x_fs: float) -> float:
            return L_seg - float(x_fs)

        support_X = L_seg
        inset_on_right = False
    else:

        def x_disp(x_fs: float) -> float:
            return float(x_fs)

        support_X = 0.0
        inset_on_right = True

    yt = _check6_y_display(D, 0.0)
    yb = _check6_y_display(D, D)
    y_top_beam, y_bot_beam = yt, yb

    # Flexural-shear fill: vertical leading edge at crack toe x (same x as crack origin below).
    pad_x_toe = max(0.012 * L_seg, 0.04 * d_use, 8.0)
    margin_y = max(0.006 * D, 1.5)
    x_fs_boundary = float(L_d_core)
    if str(tension_face).strip().lower() == "bottom":
        y_toe = float(y_bot_beam) + margin_y
    else:
        y_toe = float(y_top_beam) - margin_y
    if side_n == "internal":
        x_toe = float(support_X) - x_fs_boundary
    else:
        x_toe = float(x_disp(x_fs_boundary))
    x_toe = min(max(x_toe, pad_x_toe), float(L_seg) - pad_x_toe)

    if inset_on_right:
        flex_x0 = float(x_toe)
        flex_span = max(float(L_seg) - flex_x0, max(0.02 * float(L_seg), 1.0))
    else:
        flex_x0 = 0.0
        flex_span = float(grey_span_mm)

    def xf_sect(u: float) -> float:
        return flex_x0 + (float(u) / width_sec) * flex_span

    def add_path_raw(path: str, *, width: float = 2, color: str = "#1f2a44", fill: str = "rgba(0,0,0,0)"):
        fig.add_shape(
            type="path",
            path=path,
            line=dict(color=color, width=width),
            fillcolor=fill,
        )

    def path_from_points_disp(xy: list[tuple[float, float]], close: bool = False) -> str:
        parts: list[str] = []
        for i, (xa, ya) in enumerate(xy):
            parts.append(f"{'M' if i == 0 else 'L'} {float(xa):.4f},{ya:.4f}")
        if close:
            parts.append("Z")
        return " ".join(parts)

    inset_xy_disp = [(xf_sect(u), _check6_y_display(D, v)) for u, v in inset_pts_uv]
    # Filled section only — no stroked outline (avoids vertical web / flange lines in the sketch).
    add_path_raw(
        path_from_points_disp(inset_xy_disp, close=True),
        width=0,
        color="rgba(0,0,0,0)",
        fill="rgba(31,42,68,0.10)",
    )

    beam_outline = "#1f2a44"
    add_path_raw(
        path_from_points_disp([(0.0, yt), (L_seg, yt), (L_seg, yb), (0.0, yb)], close=True),
        width=2,
        color=beam_outline,
        fill="rgba(0,0,0,0)",
    )

    if shape_kind == "T":
        tf = float(dims["tf"])
        y_int = _check6_y_display(D, tf)
        fig.add_shape(
            type="line",
            x0=0.0,
            y0=y_int,
            x1=L_seg,
            y1=y_int,
            line=dict(color="rgba(31,42,68,0.35)", width=1, dash="dot"),
        )
    elif shape_kind == "I":
        tf = float(dims["tf"])
        y_top_int = _check6_y_display(D, tf)
        y_bot_int = _check6_y_display(D, D - tf)
        fig.add_shape(
            type="line",
            x0=0.0,
            y0=y_top_int,
            x1=L_seg,
            y1=y_top_int,
            line=dict(color="rgba(31,42,68,0.35)", width=1, dash="dot"),
        )
        fig.add_shape(
            type="line",
            x0=0.0,
            y0=y_bot_int,
            x1=L_seg,
            y1=y_bot_int,
            line=dict(color="rgba(31,42,68,0.35)", width=1, dash="dot"),
        )

    cage_y0, cage_y1 = _check6_shear_cage_y_range_mm(
        layout=layout,
        shape_kind=shape_kind,
        dims=dims,
        reo=reo,
        D=D,
        lig_d=float(lig_d_mm),
        lig_legs=int(lig_legs),
    )
    y_stirr_top = _check6_y_display(D, cage_y0)
    y_stirr_bot = _check6_y_display(D, cage_y1)
    stirrup_color = "rgba(52,52,56,0.92)"
    draw_stirrups = _check6_shear_ligatures_active(
        s_mm=float(s_lig_mm), lig_legs=int(lig_legs), asv_mm2=asv_mm2
    )

    ast_blue = "#1565c0"
    tie_x0_fs = max(0.06 * L_seg, 0.05 * d_use)
    tie_x1_fs = min(0.94 * L_seg, L_seg - 0.04 * d_use)
    fig.add_shape(
        type="line",
        x0=x_disp(tie_x0_fs),
        y0=y_steel,
        x1=x_disp(tie_x1_fs),
        y1=y_steel,
        line=dict(color=ast_blue, width=3),
    )

    # ULS d_n for NA / small C marker only (crack does not terminate at C or the support face).
    b_mm = float(dims.get("b", width_sec))
    Ast_t = _check6_tension_ast_mm2(layout, tension_face)
    dn_mm: float
    if (
        fc_mpa is not None
        and fsy_mpa is not None
        and Ast_t > 1e-6
        and math.isfinite(float(fc_mpa))
        and math.isfinite(float(fsy_mpa))
    ):
        dn_mm = _check6_uls_dn_mm(
            fc_mpa=float(fc_mpa),
            b_mm=b_mm,
            fsy_mpa=float(fsy_mpa),
            Ast_mm2=Ast_t,
        )
    else:
        dn_mm = float("nan")
    if not math.isfinite(dn_mm) or dn_mm <= 0:
        dn_mm = max(0.12 * D, 0.35 * min(d_use, D))
    dn_mm = max(1.0, min(float(D) - 1.0, float(dn_mm)))
    v_na = _check6_v_na_from_dn_mm(D=D, dn_mm=dn_mm, compression_face=compression_face)
    c_y_line = _check6_y_display(D, v_na)
    delta_cz = max(0.012 * D, 3.0)

    if side_n == "right":
        support_face_x = float(L_seg)
    elif side_n == "internal":
        support_face_x = float(support_X)
    else:
        support_face_x = 0.0

    # x_toe / y_toe: same as above (crack origin at D-region boundary).

    theta_use_deg = float(theta_v_deg) if theta_v_deg is not None else 36.0
    theta_use_rad = math.radians(max(1.0, min(theta_use_deg, 89.0)))
    ux, uy = _check6_unit_toe_to_tip_crack(
        support_side=side_n,
        tension_face=tension_face,
        theta_v_rad=theta_use_rad,
    )

    if compression_face == "top":
        y_tip_tgt = min(
            y_top_beam - 0.035 * D,
            c_y_line + 1.35 * max(delta_cz, 0.01 * D),
        )
    else:
        y_tip_tgt = max(
            y_bot_beam + 0.035 * D,
            c_y_line - 1.35 * max(delta_cz, 0.01 * D),
        )
    y_tip_tgt = min(
        max(y_tip_tgt, y_bot_beam + 0.04 * D),
        y_top_beam - 0.04 * D,
    )

    if abs(uy) > 1e-6:
        t_geom = (float(y_tip_tgt) - float(y_toe)) / uy
        x_tip = float(x_toe) + t_geom * ux
        y_tip = float(y_toe) + t_geom * uy
    else:
        x_tip = float(x_toe) + 0.45 * float(L_seg) * (1.0 if ux > 0 else -1.0)
        y_tip = float(y_tip_tgt)

    pad_span = max(0.035 * L_seg, 0.05 * d_use, 8.0)
    if side_n == "left":
        x_tip = min(max(x_tip, x_toe + pad_span), L_seg - pad_span)
    elif side_n == "right":
        x_tip = max(min(x_tip, x_toe - pad_span), pad_span)
    else:
        if ux < -1e-9:
            x_tip = max(pad_span, min(x_tip, x_toe - pad_span))
        else:
            x_tip = min(L_seg - pad_span, max(x_tip, x_toe + pad_span))

    if abs(ux) > 1e-9:
        y_tip = float(y_toe) + (float(x_tip) - float(x_toe)) / ux * uy
        y_tip = min(max(y_tip, y_bot_beam + 0.02 * D), y_top_beam - 0.02 * D)

    x_toe = float(x_toe)
    y_toe = float(y_toe)
    x_tip = float(x_tip)
    y_tip = float(y_tip)

    uln = math.hypot(ux, uy)
    if uln > 1e-9:
        ux, uy = ux / uln, uy / uln

    web_stm = bool(web_crushing_stm)
    if web_stm:
        show_mean_crack_guideline = False
        show_mean_green_flow_pulse = False
        show_mean_green_flow_arrows = False
        show_green_strut_flow = False
        show_compression_resultant = False
        show_shear_teaching_overlay = False
        show_mcft_mechanism_labels = False
        show_region_labels = False

    crack_geom = None
    crack_pts: list[tuple[float, float]] = []
    if not web_stm:
        crack_geom = _check6_crack_bezier_setup(
            x_toe,
            y_toe,
            x_tip,
            y_tip,
            tension_face=tension_face,
            D_mm=D,
            bulge_scale=float(crack_bulge_scale),
        )
        if crack_geom is None:
            crack_geom = _check6_collinear_bezier_geom_from_chord(
                x_toe, y_toe, x_tip, y_tip
            )

        crack_pts = _check6_soft_crack_polyline(
            x_toe,
            y_toe,
            x_tip,
            y_tip,
            tension_face=tension_face,
            D_mm=D,
            bulge_scale=float(crack_bulge_scale),
            jag_scale=float(crack_jag_scale),
        )
    # θ arc/label: governing θ_v from check (toe→tip unit vector), not the jagged polyline.
    theta_lbl_x = float(x_toe)
    theta_lbl_y = float(y_toe)
    if not web_stm:
        tdx, tdy = float(ux), float(uy)
        if str(tension_face).strip().lower() == "bottom":
            if side_n == "right":
                edx, edy = -1.0, 0.0
            elif side_n == "internal" and float(ux) < -1e-9:
                edx, edy = -1.0, 0.0
            else:
                edx, edy = 1.0, 0.0
        else:
            if side_n == "right":
                edx, edy = -1.0, 0.0
            elif side_n == "internal" and float(ux) < -1e-9:
                edx, edy = -1.0, 0.0
            else:
                edx, edy = 1.0, 0.0
        a_edge = math.atan2(edy, edx)
        a_tan = math.atan2(tdy, tdx)
        da = (a_tan - a_edge + math.pi) % (2 * math.pi) - math.pi
        if da > math.pi / 2:
            da -= 2 * math.pi
        elif da < -math.pi / 2:
            da += 2 * math.pi
        a_arc0 = a_edge
        a_arc1 = a_edge + da
        r_arc = max(0.036 * D, 0.026 * L_seg, 12.0)
        n_theta = 10
        arc_pts_theta: list[tuple[float, float]] = []
        for i in range(n_theta + 1):
            tt = i / n_theta
            aa = a_arc0 + tt * (a_arc1 - a_arc0)
            arc_pts_theta.append(
                (x_toe + r_arc * math.cos(aa), y_toe + r_arc * math.sin(aa))
            )
        arc_path = _check6_polyline_to_path_svg(arc_pts_theta)
        if arc_path:
            fig.add_shape(
                type="path",
                path=arc_path,
                line=dict(color="rgba(46,105,65,0.58)", width=1.35),
            )
        am = a_arc0 + 0.34 * (a_arc1 - a_arc0)
        r_lbl = r_arc * 1.45
        theta_shift_x = max(0.058 * D, 40.0)
        theta_lbl_x = x_toe + r_lbl * math.cos(am) + theta_shift_x
        theta_lbl_y = y_toe + r_lbl * math.sin(am)
        theta_lbl_x = min(float(theta_lbl_x), float(L_seg) - max(0.018 * L_seg, 10.0))
        fig.add_annotation(
            x=theta_lbl_x,
            y=theta_lbl_y,
            text=f"θ = {float(theta_use_deg):.1f}°",
            showarrow=False,
            font=dict(size=8, color="rgba(20,70,35,0.92)"),
            xref="x",
            yref="y",
        )

    if not web_stm:
        crack_d = _check6_polyline_to_path_svg(crack_pts)
        if crack_d:
            fig.add_shape(
                type="path",
                path=crack_d,
                line=dict(color="#111111", width=2),
            )

    t_ray = math.hypot(x_tip - x_toe, y_tip - y_toe)
    stirrup_xs_hit: list[float] = []
    stirrup_xd_list: list[float] = []
    if draw_stirrups:
        for xs_fs in _check6_stirrup_xs_mm(
            L_seg_mm=float(L_seg), s_mm=float(s_lig_mm), max_lines=28
        ):
            xd = x_disp(xs_fs)
            stirrup_xd_list.append(float(xd))
            if show_shear_teaching_overlay:
                hit = _check6_crack_ray_hits_vertical_stirrup(
                    xd,
                    x_toe,
                    y_toe,
                    ux,
                    uy,
                    y_stirr_bot,
                    y_stirr_top,
                    t_ray,
                )
                if hit:
                    stirrup_xs_hit.append(xd)
            fig.add_shape(
                type="line",
                x0=xd,
                y0=y_stirr_bot,
                x1=xd,
                y1=y_stirr_top,
                line=dict(color=stirrup_color, width=1.25),
            )

    if show_mean_crack_guideline:
        smooth_backbone = _check6_smooth_crack_polyline(
            x_toe,
            y_toe,
            x_tip,
            y_tip,
            tension_face=tension_face,
            D_mm=D,
            n=80,
            bulge_scale=float(crack_bulge_scale),
        )
        mean_green_offset_pts = []
        if smooth_backbone:
            ggap = max(0.026 * D, 17.0, 0.0095 * float(L_seg))
            mean_green_offset_pts = _check6_polyline_offset_toward_compression(
                smooth_backbone,
                gap_mm=ggap,
                compression_face=compression_face,
                D_mm=D,
                L_seg_mm=float(L_seg),
                y_bot=y_bot_beam,
                y_top=y_top_beam,
                normal_sign=-1.0,
            )
        if len(mean_green_offset_pts) >= 2:
            mean_tr, _, _ = _check6_trim_polyline_at_ast_elevation(
                mean_green_offset_pts,
                y_ast=float(y_steel),
                tension_face=tension_face,
            )
            if len(mean_tr) >= 2:
                mean_green_offset_pts = mean_tr
        if len(mean_green_offset_pts) >= 2:
            mean_green_for_flow = list(mean_green_offset_pts)
            use_pulse = bool(show_mean_green_flow_pulse)
            if not use_pulse:
                pg_mean = _check6_polyline_to_path_svg(mean_green_offset_pts)
                if pg_mean:
                    fig.add_shape(
                        type="path",
                        path=pg_mean,
                        line=dict(
                            color="#2e7d32",
                            width=2.1,
                            dash="12px,10px",
                        ),
                    )
            if (
                bool(show_mean_green_flow_arrows)
                and len(mean_green_offset_pts) >= 5
            ):
                _check6_add_green_black_flow_arrows_on_polyline(
                    fig,
                    mean_green_offset_pts,
                    D_mm=D,
                    L_seg_mm=float(L_seg),
                    y_bot=y_bot_beam,
                    y_top=y_top_beam,
                    show_green_tangent_arrows=not use_pulse,
                )

    if not web_stm:
        green_pts = [
            (
                x_toe + (x_tip - x_toe) * (i / 72.0),
                y_toe + (y_tip - y_toe) * (i / 72.0),
            )
            for i in range(73)
        ]
        green_pts, green_t0, green_n = _check6_trim_polyline_at_ast_elevation(
            green_pts, y_ast=y_steel, tension_face=tension_face
        )
    else:
        green_pts = []
        green_t0, green_n = 0.0, 1.0
    green_shift = max(0.088 * D, 58.0)
    if (
        show_green_strut_flow
        and len(green_pts) >= 4
        and crack_geom is not None
    ):
        _check6_add_green_ccw_flow_on_polyline(
            fig,
            green_pts,
            x_shift_mm=green_shift,
            D_mm=D,
            L_seg_mm=float(L_seg),
            y_bot=y_bot_beam,
            y_top=y_top_beam,
            crack_bezier_geom=crack_geom,
            wall_x_mm=None,
            wall_at_start=False,
            suppress_wall_extension_at_tension=True,
            bezier_t_index_offset=green_t0,
            bezier_n_orig=green_n,
            y_ast_clip=float(y_steel),
            ast_clip_tension_face=tension_face,
        )

    teach_col = "rgba(55,71,79,0.85)"
    if (
        show_shear_teaching_overlay
        and draw_stirrups
        and str(tension_face).strip().lower() == "bottom"
        and math.tan(theta_use_rad) > 1e-6
    ):
        cot_t = 1.0 / math.tan(theta_use_rad)
        k_fit = 1.0
        horiz_need = float(d_v_use) * cot_t
        if horiz_need > 0.46 * float(L_seg):
            k_fit = (0.46 * float(L_seg)) / horiz_need
        dvv = float(d_v_use) * k_fit
        horiz_run_mm = dvv * cot_t
        xh_dir = 1.0 if ux >= 0.0 else -1.0
        beam_h = abs(y_bot_beam - y_top_beam)
        sign_up = -1.0 if y_top_beam < y_toe else 1.0
        step_v = min((dvv / D) * beam_h, abs(y_toe - y_top_beam) * 0.88)
        x_v1, y_v1 = x_toe, y_toe + sign_up * step_v
        x_h1, y_h1 = x_v1 + xh_dir * horiz_run_mm, y_v1
        fig.add_shape(
            type="line",
            x0=x_toe,
            y0=y_toe,
            x1=x_v1,
            y1=y_v1,
            line=dict(color=teach_col, width=1.25, dash="dot"),
        )
        fig.add_shape(
            type="line",
            x0=x_v1,
            y0=y_v1,
            x1=x_h1,
            y1=y_h1,
            line=dict(color=teach_col, width=1.25, dash="dot"),
        )
        fig.add_annotation(
            x=0.5 * (x_toe + x_v1) - 0.018 * D,
            y=0.5 * (y_toe + y_v1),
            text="<i>d<sub>v</sub></i>",
            showarrow=False,
            font=dict(size=8, color=teach_col),
        )
        fig.add_annotation(
            x=0.5 * (x_v1 + x_h1),
            y=y_v1 + (0.022 * D if sign_up < 0 else -0.022 * D),
            text="<i>d<sub>v</sub> cot θ<sub>v</sub></i>",
            showarrow=False,
            font=dict(size=8, color=teach_col),
        )
        n_pred = float(d_v_use) * cot_t / max(float(s_lig_mm), 1.0)
        n_hit = len(stirrup_xs_hit)
        n_line = (
            f"<i>n</i> ≈ <i>d<sub>v</sub> cot θ<sub>v</sub> / s</i> "
            f"≈ {n_pred:.1f} stirrup sets &nbsp;|&nbsp; crossed: {n_hit}"
        )
        fig.add_annotation(
            x=0.5 * (x_toe + x_tip),
            y=float(y_bot_beam) - max(0.044 * D, 22.0),
            text=n_line + "<br><span style=\"font-size:8px\">"
            "<i>V</i><sub>s</sub> ∝ <i>A</i><sub>sv</sub> <i>f</i><sub>sy</sub> "
            "(<i>d</i><sub>v</sub> cot θ<sub>v</sub> / <i>s</i>) — schematic</span>",
            showarrow=False,
            font=dict(size=9, color="rgba(31,42,68,0.80)"),
            xanchor="center",
            yanchor="top",
            align="center",
        )

    sup_kind_raw = str(support_draw_kind or "pinned")
    y_ground, node_x = _check6_draw_support_symbol(
        fig,
        x_ref=support_X,
        y_beam_bottom=y_bot_beam,
        D=D,
        kind=sup_kind_raw,
        L_seg_mm=float(L_seg),
    )
    # Compression C: starts at top fibre (sagging) or bottom fibre (hogging); lower/upper end ties to crack tip
    # where possible; span-ward x from crack tip.
    c_red = "#c41e3a"
    c_span_x = max(0.024 * L_seg, 13.0)
    min_c_depth = max(0.040 * D, 14.0)
    min_gap = max(0.018 * D, 8.0)
    y_tip_f = float(y_tip)
    if show_compression_resultant:
        if tension_face == "bottom":
            y_c_top = y_top_beam - max(0.015 * D, 5.0)
            if y_c_top - y_tip_f >= min_gap:
                y_c_bot = max(y_bot_beam + 0.02 * D, y_tip_f)
            else:
                y_c_bot = y_c_top - min_c_depth
                y_c_bot = max(y_bot_beam + 0.02 * D, y_c_bot)
            if side_n == "right":
                cx_c = max(pad_x_toe, float(x_tip) - c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
            elif side_n == "internal":
                cx_c = max(pad_x_toe, float(x_tip) - 0.68 * c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
            else:
                cx_c = min(float(L_seg) - pad_x_toe, float(x_tip) + c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
        else:
            y_c_bot = y_bot_beam + max(0.015 * D, 5.0)
            y_c_top = max(y_c_bot + min_gap, y_tip_f)
            y_c_top = min(y_c_top, y_top_beam - max(0.015 * D, 5.0))
            if y_c_top - y_c_bot < min_c_depth:
                y_c_top = y_c_bot + min_c_depth
                y_c_top = min(y_c_top, y_top_beam - max(0.012 * D, 4.0))
            if side_n == "right":
                cx_c = max(pad_x_toe, float(x_tip) - c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
            elif side_n == "internal":
                cx_c = max(pad_x_toe, float(x_tip) - 0.68 * c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
            else:
                cx_c = min(float(L_seg) - pad_x_toe, float(x_tip) + c_span_x)
                c_lbl_x = cx_c - 0.078 * D
                c_xanchor = "right"
        if y_c_bot >= y_c_top - 1e-6:
            y_c_bot = min(y_c_top - min_c_depth, y_c_top - 0.015 * D)
            y_c_bot = max(y_bot_beam + 0.02 * D, y_c_bot)
        flow_c_cx = float(cx_c)
        flow_c_y_top = float(y_c_top)
        flow_c_y_bot = float(y_c_bot)
        fig.add_shape(
            type="line",
            x0=cx_c,
            y0=y_c_bot,
            x1=cx_c,
            y1=y_c_top,
            line=dict(color=c_red, width=2.2),
        )
        fig.add_annotation(
            x=c_lbl_x,
            y=0.5 * (y_c_top + y_c_bot),
            text="<b>C</b>",
            showarrow=False,
            font=dict(size=11, color=c_red),
            xanchor=c_xanchor,
        )
        # Horizontal compression-direction cue (+x), upper part of the compression block
        _cz_top = float(y_c_top)
        _cz_bot = float(y_c_bot)
        _arr_y = _cz_top - max(0.026 * D, 10.0)
        _arr_y = min(
            max(_arr_y, _cz_bot + max(0.016 * D, 6.0)),
            _cz_top - max(0.006 * D, 2.5),
        )
        _arr_len = max(0.11 * L_seg, 0.21 * D, 38.0)
        _x_head = min(
            float(L_seg) - max(0.055 * L_seg, pad_x_toe),
            max(float(cx_c) + 0.14 * L_seg, 0.24 * L_seg),
        )
        _x_tail = max(float(pad_x_toe), _x_head - _arr_len)
        if _x_head > _x_tail + 1.0:
            fig.add_annotation(
                x=_x_head,
                y=_arr_y,
                ax=_x_tail,
                ay=_arr_y,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.05,
                arrowwidth=2.8,
                arrowcolor=c_red,
            )
    fig.add_annotation(
        x=x_disp(min(0.20 * L_d_core, 0.14 * L_seg)),
        y=y_steel,
        ax=x_disp(min(0.88 * L_seg, L_seg - 0.06 * d_use)),
        ay=y_steel,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.0,
        arrowwidth=2.5,
        arrowcolor=ast_blue,
    )
    ast_inset_fs = max(0.07 * L_seg, 0.06 * d_use, 22.0)
    if side_n == "right":
        ast_lbl_x = x_disp(L_seg - ast_inset_fs)
    elif side_n == "internal":
        ast_lbl_x = x_disp(-min(0.13 * L_seg, 0.42 * L_seg))
    else:
        ast_lbl_x = x_disp(ast_inset_fs)
    if not web_stm:
        fig.add_annotation(
            x=ast_lbl_x,
            y=y_steel + (0.05 * D if tension_face == "bottom" else -0.05 * D),
            text="<b>Ast</b>",
            showarrow=False,
            font=dict(size=13, color=ast_blue),
            xanchor="left",
        )

    if web_stm:
        _check6_add_web_crushing_stm_overlay(
            fig,
            D=D,
            L_seg=float(L_seg),
            support_face_x=float(support_face_x),
            x_toe=float(x_toe),
            y_toe=float(y_toe),
            y_steel=float(y_steel),
            y_top_beam=float(y_top_beam),
            y_bot_beam=float(y_bot_beam),
            tension_face=str(tension_face),
            side_n=str(side_n),
            theta_v_deg=float(theta_use_deg),
            pad_x_toe=float(pad_x_toe),
        )

    if (
        show_mean_crack_guideline
        and bool(show_mean_green_flow_pulse)
        and len(mean_green_for_flow) >= 2
    ):
        if (
            show_compression_resultant
            and flow_c_cx is not None
            and flow_c_y_top is not None
            and flow_c_y_bot is not None
        ):
            flow_combined, flow_seg = _check6_build_shear_transfer_flow_combined_pts(
                cx_c=float(flow_c_cx),
                y_c_top=float(flow_c_y_top),
                y_c_bottom=float(flow_c_y_bot),
                mean_green_pts=mean_green_for_flow,
                y_steel=float(y_steel),
                tie_xa=float(x_disp(tie_x0_fs)),
                tie_xb=float(x_disp(tie_x1_fs)),
                support_face_x=float(support_face_x),
                D=float(D),
                L_seg=float(L_seg),
            )
            if len(flow_combined) >= 3:
                _check6_add_mcft_style_flow_pulse(
                    fig,
                    flow_combined,
                    color="rgba(46,125,50,0.95)",
                    reverse_along_path=False,
                    flow_segment_ends=flow_seg,
                    flow_arrowhead=True,
                    line_shape="linear",
                )
        else:
            _check6_add_mcft_style_flow_pulse(
                fig,
                mean_green_for_flow,
                color="rgba(46,125,50,0.95)",
                reverse_along_path=True,
                flow_arrowhead=True,
            )

    # Region labels below the beam soffit (display y < y_bot_beam; y increases upward).
    if show_region_labels:
        y_reg_lbl = float(y_bot_beam) - max(0.056 * D, 28.0)
        reg_font = dict(size=10, color="rgba(31,42,68,0.88)")
        L_rem = max(L_seg - L_d_core, 0.08 * L_seg)
        if side_n == "right":
            x_d_reg = x_disp(0.52 * L_d_core)
            x_f_reg = x_disp(L_d_core + 0.50 * L_rem)
        elif side_n == "internal":
            x_d_reg = support_X + 0.42 * min(L_d_core, max(L_seg - support_X, 1.0) * 0.92)
            x_f_reg = max(0.06 * L_seg, support_X * 0.42)
        else:
            x_d_reg = x_disp(0.48 * L_d_core)
            x_f_reg = x_disp(L_d_core + 0.50 * L_rem)
        fig.add_annotation(
            x=x_d_reg,
            y=y_reg_lbl,
            text="D-region",
            showarrow=False,
            font=reg_font,
            xanchor="center",
            yanchor="top",
        )
        fig.add_annotation(
            x=x_f_reg,
            y=y_reg_lbl,
            text="Flexural shear<br>region",
            showarrow=False,
            font=reg_font,
            xanchor="center",
            yanchor="top",
        )

    if (
        bool(show_mcft_mechanism_labels)
        and bool(show_compression_resultant)
        and bool(show_mean_crack_guideline)
        and len(mean_green_for_flow) >= 2
        and len(crack_pts) >= 3
        and flow_c_cx is not None
        and flow_c_y_top is not None
        and flow_c_y_bot is not None
    ):
        _check6_add_mcft_mechanism_labels(
            fig,
            D=float(D),
            L_seg=float(L_seg),
            L_d_core=float(L_d_core),
            crack_pts=crack_pts,
            mean_green_pts=list(mean_green_for_flow),
            theta_lbl_x=float(theta_lbl_x),
            theta_lbl_y=float(theta_lbl_y),
            cx_c=float(flow_c_cx),
            y_c_top=float(flow_c_y_top),
            y_c_bot=float(flow_c_y_bot),
            y_steel=float(y_steel),
            ast_lbl_x=float(ast_lbl_x),
            ast_arrow_x0=float(x_disp(min(0.20 * L_d_core, 0.14 * L_seg))),
            ast_arrow_x1=float(x_disp(min(0.88 * L_seg, L_seg - 0.06 * d_use))),
            tension_face=str(tension_face),
            side_n=str(side_n),
            y_bot_beam=float(y_bot_beam),
            y_top_beam=float(y_top_beam),
            y_stirr_bot=float(y_stirr_bot),
            y_stirr_top=float(y_stirr_top),
            stirrup_xds=stirrup_xd_list,
            show_region_labels=bool(show_region_labels),
            support_X=float(support_X),
            x_disp=x_disp,
        )

    ymin = y_ground - 0.14 * D
    ymax = y_top_beam + 0.22 * D
    xpad = 0.06 * (L_seg + 0.12 * D)
    xmin_plot = min(-0.10 * D, x_toe - 0.10 * D)
    if show_compression_resultant and side_n != "right":
        xmin_plot = min(xmin_plot, float(c_lbl_x) - 0.06 * D)
    if web_stm:
        flow_pad = max(0.18 * D, 0.06 * float(L_seg))
    else:
        flow_pad = (
            max(float(green_shift), 0.22 * D)
            if (show_green_strut_flow or show_mean_crack_guideline)
            else max(0.18 * D, 0.06 * float(L_seg))
        )
    xmax_plot = L_seg + flow_pad + 0.16 * D
    if side_n == "right":
        if show_compression_resultant:
            xmax_plot = max(xmax_plot, float(c_lbl_x) + 0.12 * D, x_tip + 0.10 * D)
        else:
            xmax_plot = max(xmax_plot, x_tip + 0.10 * D)
    xpad_right = xpad + 0.038 * D
    fig.update_xaxes(
        visible=False,
        range=[xmin_plot - xpad, xmax_plot + xpad_right],
        fixedrange=True,
    )
    fig.update_yaxes(
        visible=False,
        range=[ymin - 0.03 * D, ymax + 0.04 * D],
        fixedrange=True,
    )
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )
    return fig
