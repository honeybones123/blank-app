# crack_side_view_diagram.py
# Beam side elevation for Crack page: longitudinal reo, flexural cracks, and deflected member
# only (grey fill matching Shear side-view beam band; no undeformed rectangle).

from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from state_runtime_gateway import get_param
from widgets_helpers import main_longitudinal_reo_pair_labels
from shear_visuals import _beam_model
from ui.diagrams.side_view_diagram import (
    SIDE_VIEW_VISUAL_HEIGHT,
    _safe_float,
    build_side_view_tension_reo as _build_side_view_tension_reo,
    fit_side_view_figure_to_content as _fit_side_view_figure_to_content,
    build_side_view_figure as _build_side_view_figure,
    build_side_view_support_shapes as _build_side_view_support_shapes,
    side_view_display_length_from_model as _side_view_display_length_from_model,
    side_view_display_state as _side_view_display_state,
    side_view_display_x as _side_view_display_x,
)
from ui.diagrams.crack_moment_diagram import (
    build_crack_moment_diagram_figure as _shared_build_crack_moment_diagram_figure,
)
from ui.diagrams.diagram_styles import REO_BOTTOM, REO_TOP, diagram_deflection_visual_scale_factor


def _diagram_kind(support_type: str | None) -> str:
    from deflection_support import _support_props

    return str(
        _support_props(support_type).get("diagram", "simply_supported_udl")
        or "simply_supported_udl"
    )


def _resolved_sls_moment_arrays_global() -> tuple[np.ndarray, np.ndarray] | None:
    """Full-beam SLS M(x) from results (global x along the structural axis)."""
    x_raw = list(get_param("moment_x", []) or [])
    m_raw = list(get_param("moment_values", []) or [])
    if len(x_raw) < 2 or len(m_raw) != len(x_raw):
        x_raw = list(get_param("shear_x", []) or [])
        m_raw = list(get_param("shear_M_sls_kNm", []) or [])
    x = np.asarray(x_raw, dtype=float).reshape(-1)
    m = np.asarray(m_raw, dtype=float).reshape(-1)
    if x.size < 2 or m.size != x.size or not np.all(np.isfinite(x)) or not np.all(np.isfinite(m)):
        return None
    return x, m


def _multi_span_node_positions_m() -> list[float] | None:
    """Return cumulative support positions (m) for multi-span design beams, or None if single-span."""
    beam_mode = str(
        st.session_state.get("sfd_beam_system_mode")
        or st.session_state.get("design_beam_system_mode")
        or get_param("design_beam_system_mode", "Single span")
        or "Single span"
    ).strip()
    if beam_mode != "Multi-span":
        return None
    try:
        n_spans = int(
            round(
                float(
                    st.session_state.get("sfd_span_count", get_param("design_span_count", 2.0) or 2.0)
                )
            )
        )
    except (TypeError, ValueError):
        n_spans = 2
    n_spans = max(2, min(5, n_spans))
    nodes = [0.0]
    for i in range(1, n_spans + 1):
        Li = float(
            st.session_state.get(f"sfd_span_len_{i}", get_param(f"design_span_len_{i}", 4.0) or 4.0)
        )
        nodes.append(nodes[-1] + max(0.2, Li))
    return nodes


def _resolve_crack_diagram_window(state: Any) -> dict[str, Any]:
    """
    Optional multi-span window: slice to governing span (max |M| in span, tie → deflection controlling span),
    rebase local x to [0, L]. Single-span: full beam, no caption.
    Cached on ``crack_bmd_cache_fingerprint`` for performance (no recompute on tab switch).
    """
    fp = str(get_param("crack_bmd_cache_fingerprint", "") or "")
    cache = st.session_state.get("_crack_diagram_window_cache_v2")
    if isinstance(cache, dict) and cache.get("fp") == fp:
        return cache["data"]

    nodes = _multi_span_node_positions_m()
    ms = _resolved_sls_moment_arrays_global()
    L_inputs_mm = float(get_param("L", 3000.0) or 3000.0)
    L_fallback_m = max(L_inputs_mm / 1000.0, 0.1)

    if not nodes or len(nodes) < 3 or ms is None:
        xg, Mg = (ms[0], ms[1]) if ms is not None else (np.array([]), np.array([]))
        if xg.size >= 2:
            Lw = float(xg[-1])
        else:
            Lw = L_fallback_m
        out = {
            "multi": False,
            "x0_m": 0.0,
            "L_m": max(Lw, 0.1),
            "x_m": np.asarray(xg, dtype=float),
            "M_m": np.asarray(Mg, dtype=float),
            "governing_caption": None,
            "span_index": 0,
        }
        st.session_state["_crack_diagram_window_cache_v2"] = {"fp": fp, "data": out}
        return out

    xg, Mg = ms
    n_seg = len(nodes) - 1
    scores: list[float] = []
    for i in range(n_seg):
        a, b = float(nodes[i]), float(nodes[i + 1])
        mask = (xg >= a - 1e-9) & (xg <= b + 1e-9)
        scores.append(float(np.max(np.abs(Mg[mask]))) if np.any(mask) else -1.0)
    best = int(np.argmax(np.array(scores))) if scores else 0
    mx = max(scores) if scores else -1.0
    try:
        from deflection_support import get_deflection_diagram_support_condition

        src = state if isinstance(state, dict) else st.session_state
        sup = get_deflection_diagram_support_condition(src)
        ctrl = int(sup.get("controlling_span_idx", 0) or 0)
        ctrl = max(0, min(ctrl, n_seg - 1))
    except Exception:
        ctrl = best
    ties = [j for j, s in enumerate(scores) if s >= mx - 1e-9 * max(abs(mx), 1.0)]
    if len(ties) > 1 and ctrl in ties:
        best = ctrl

    x0, x1 = float(nodes[best]), float(nodes[best + 1])
    Lw = max(x1 - x0, 0.1)
    mask = (xg >= x0 - 1e-9) & (xg <= x1 + 1e-9)
    xloc = np.asarray(xg[mask] - x0, dtype=float)
    Mloc = np.asarray(Mg[mask], dtype=float)
    if xloc.size < 2:
        x_dense = np.linspace(0.0, Lw, max(24, int(120 * Lw / max(Lw, 0.15))), dtype=float)
        Mloc = np.interp(x_dense, xg, Mg, left=float(Mg[0]), right=float(Mg[-1]))
        xloc = x_dense

    out = {
        "multi": True,
        "x0_m": x0,
        "L_m": Lw,
        "x_m": xloc,
        "M_m": Mloc,
        "governing_caption": "Displaying governing span",
        "span_index": int(best),
    }
    st.session_state["_crack_diagram_window_cache_v2"] = {"fp": fp, "data": out}
    return out


def _bottom_fiber_tension_mask(
    xi: np.ndarray, diagram_kind: str, support_type: str | None
) -> np.ndarray:
    xi = np.asarray(xi, dtype=float)
    stv = str(support_type or "")
    if diagram_kind == "cantilever_udl":
        return xi >= 0.20
    if diagram_kind == "fixed_fixed_udl":
        return (xi >= 0.14) & (xi <= 0.86)
    if diagram_kind == "fixed_pinned_udl":
        return (xi >= 0.07) & (xi <= 0.94)
    if diagram_kind == "continuous_span_udl":
        if "interior" in stv:
            return (xi >= 0.06) & (xi <= 0.94)
        if "end span" in stv:
            return (xi >= 0.08) & (xi <= 0.98)
        return (xi >= 0.06) & (xi <= 0.96)
    return np.ones_like(xi, dtype=bool)


def _bottom_tension_intensity(
    xi: float, diagram_kind: str, support_type: str | None
) -> float:
    # Coerce in case callers pass 0-d or 1-element arrays from numpy / session data.
    try:
        xi_f = float(np.asarray(xi, dtype=float).ravel()[0])
    except (TypeError, ValueError, IndexError):
        xi_f = 0.0
    if not _bottom_fiber_tension_mask(np.array([xi_f]), diagram_kind, support_type)[0]:
        return 0.0
    m = math.sin(math.pi * xi_f) ** 2
    if diagram_kind == "cantilever_udl":
        return float(np.clip((xi_f - 0.18) / 0.72, 0.0, 1.0)) * m
    if diagram_kind == "continuous_span_udl" and "interior" in str(support_type or ""):
        return float(np.clip(m, 0.0, 1.0))
    return float(np.clip(m, 0.0, 1.0))


def _downsample_crack_stations_uniform(xs: list[float], n_cap: int) -> list[float]:
    """
    When ``len(xs) > n_cap`` (very small calculated ``s_cr``), thin stations uniformly along x
    so spacing intent stays ~even (no arbitrary moment-based thinning).
    """
    if n_cap < 4 or len(xs) <= n_cap:
        return sorted(set(float(t) for t in xs if math.isfinite(t)))
    arr = np.array(sorted(set(float(t) for t in xs if math.isfinite(t))), dtype=float)
    if arr.size <= n_cap:
        return arr.tolist()
    inds = np.unique(np.round(np.linspace(0, arr.size - 1, n_cap)).astype(int))
    return [float(arr[i]) for i in inds.tolist()]


def _smooth_1d_3pt(values: list[float]) -> list[float]:
    """Light 3-point moving average (edge-padded) to avoid abrupt crack-height steps."""
    if len(values) < 3:
        return list(values)
    a = np.asarray(values, dtype=float)
    out = np.empty_like(a)
    out[0] = (2 * a[0] + a[1]) / 3.0
    out[-1] = (a[-2] + 2 * a[-1]) / 3.0
    out[1:-1] = (a[:-2] + a[1:-1] + a[2:]) / 3.0
    return [float(v) for v in out.tolist()]


def _smooth_1d_5pt(values: list[float]) -> list[float]:
    """Wider low-pass on crack moment weights for smoother crack heights along the span."""
    if len(values) < 5:
        return _smooth_1d_3pt(values)
    a = np.asarray(values, dtype=float)
    k = np.array([1.0, 4.0, 6.0, 4.0, 1.0], dtype=float) / 16.0
    out = np.copy(a)
    for i in range(2, len(a) - 2):
        out[i] = float(np.dot(k, a[i - 2 : i + 3]))
    out[0] = float((10 * a[0] + 5 * a[1] - a[2]) / 14.0)
    out[1] = float((4 * a[0] + 9 * a[1] + 4 * a[2] - a[3]) / 16.0)
    out[-2] = float((-a[-4] + 4 * a[-3] + 9 * a[-2] + 4 * a[-1]) / 16.0)
    out[-1] = float((-a[-3] + 5 * a[-2] + 10 * a[-1]) / 14.0)
    return [float(v) for v in out.tolist()]


def _bar_midpoints_m_from_model(model: Mapping[str, Any] | None) -> list[float]:
    """Physical x (m) at mid-gaps between bottom longitudinal bars when layout ``x`` (mm) is available."""
    if model is None:
        return []
    layers = model.get("bottom_layers") or []
    if not isinstance(layers, list) or not layers:
        return []
    lyr0 = layers[0]
    if not isinstance(lyr0, Mapping):
        return []
    xb = lyr0.get("x")
    if not isinstance(xb, (list, tuple)) or len(xb) < 2:
        return []
    xv = sorted(float(t) / 1000.0 for t in xb if t is not None)
    if len(xv) < 2:
        return []
    return [0.5 * (xv[i] + xv[i + 1]) for i in range(len(xv) - 1)]


def _enforce_min_separation_cracks(xs: list[float], dmin: float) -> list[float]:
    if dmin <= 0 or not xs:
        return sorted(xs)
    out: list[float] = []
    for x in sorted(float(t) for t in xs if math.isfinite(t)):
        if not out or x - out[-1] >= dmin:
            out.append(x)
    return out


def _snap_crack_x_bar_midpoints(
    xs: list[float],
    model: Mapping[str, Any] | None,
    *,
    L_m: float,
    s_cr_m: float,
) -> list[float]:
    """Snap crack stations toward mid-points between bottom bars (fallback: legacy phase snap)."""
    mids = _bar_midpoints_m_from_model(model)
    if len(mids) < 1:
        return _snap_crack_x_reo_phase(xs, model, s_cr_m)
    sm = sorted(mids)
    pitch = float(np.median(np.diff(np.asarray(sm, dtype=float)))) if len(sm) >= 2 else max(0.05 * L_m, s_cr_m)
    if not math.isfinite(pitch) or pitch <= 0.0:
        pitch = max(0.05 * L_m, s_cr_m)
    lim = max(0.72 * pitch, 0.85 * s_cr_m)
    out: list[float] = []
    for x in xs:
        xf = float(x)
        best = float(min(sm, key=lambda m: abs(float(m) - xf)))
        if abs(best - xf) <= lim:
            out.append(best)
        else:
            step = min(0.32 * pitch, 0.22 * s_cr_m) * (1.0 if best >= xf else -1.0)
            out.append(float(np.clip(xf + step, 0.02 * L_m, 0.98 * L_m)))
    out = sorted(set(out))
    dmin = max(0.11 * s_cr_m, 0.07 * pitch, 0.012 * L_m)
    return _enforce_min_separation_cracks(out, dmin)


def _snap_crack_x_reo_phase(
    xs: list[float],
    model: Mapping[str, Any] | None,
    s_cr_m: float,
) -> list[float]:
    """
    Snap along-span crack positions to a coarse grid derived from s_cr, with a phase offset from
    bottom-bar lateral spacing (mid gap) so vertical cracks sit away from a rigid bar-station grid.
    """
    phase = 0.25 * s_cr_m
    if model is not None:
        layers = model.get("bottom_layers") or []
        if isinstance(layers, list) and layers:
            lyr0 = layers[0]
            if isinstance(lyr0, Mapping):
                xb = lyr0.get("x")
                if isinstance(xb, (list, tuple)) and len(xb) >= 2:
                    xv = sorted(float(t) for t in xb if t is not None)
                    if len(xv) >= 2:
                        gaps = [xv[j + 1] - xv[j] for j in range(len(xv) - 1)]
                        pitch_mm = float(np.median(np.asarray(gaps, dtype=float)))
                        if math.isfinite(pitch_mm) and pitch_mm > 0.0:
                            phase = float(
                                np.clip(
                                    0.5 * pitch_mm / 1000.0,
                                    0.03 * s_cr_m,
                                    0.48 * s_cr_m,
                                )
                            )
    grid = max(0.08 * s_cr_m, 1e-4)
    out: list[float] = []
    for x in xs:
        xb = float(x) + phase
        snapped = round(xb / grid) * grid
        out.append(float(snapped - phase))
    return sorted(set(out))


def _flexural_bottom_station_allowed(
    x_m: float,
    L_m: float,
    diagram_kind: str,
    support_type: str | None,
    moment_series: tuple[np.ndarray, np.ndarray] | None,
) -> bool:
    """
    Bottom flexural crack only where SLS sagging ``M(x) > 0`` (when ``moment_series`` is available),
    combined with the same support/diagram mask used elsewhere; otherwise sketch tension mask only.
    """
    L_m = max(float(L_m), 1e-9)
    xi = float(np.clip(x_m / L_m, 0.0, 1.0))
    mo_x, mo_m = moment_series if moment_series is not None else (None, None)
    if (
        mo_x is not None
        and mo_m is not None
        and mo_x.size >= 2
        and mo_m.size == mo_x.size
        and np.all(np.isfinite(mo_x))
        and np.all(np.isfinite(mo_m))
    ):
        m_at = float(
            np.interp(
                float(x_m),
                np.asarray(mo_x, dtype=float),
                np.asarray(mo_m, dtype=float),
                left=float(mo_m[0]),
                right=float(mo_m[-1]),
            )
        )
        m_scale = max(float(np.max(np.abs(np.asarray(mo_m, dtype=float)))), 1e-12)
        if m_at <= max(1e-9 * m_scale, 1e-9):
            return False
        brk = float(_bottom_tension_intensity(xi, diagram_kind, support_type))
        return brk >= 0.05
    return float(_bottom_tension_intensity(xi, diagram_kind, support_type)) >= 0.10


def _crack_x_stations_m(
    L_m: float,
    s_cr_mm: float,
    diagram_kind: str,
    support_type: str | None,
    *,
    n_cap: int = 56,
    model: Mapping[str, Any] | None = None,
    moment_series: tuple[np.ndarray, np.ndarray] | None = None,
) -> list[float]:
    """
    Crack stations from **calculated** spacing ``s_{r,max}`` (mm → m): uniform steps ``s_cr`` along the span,
    kept only in bottom-tension (sagging) regions per shared ``moment_x`` / ``moment_values`` when present.
    Mid-gap snap to bottom bars; uniform thinning if count exceeds ``n_cap`` (performance).
    """
    if L_m <= 0:
        return []
    s_cr = max(0.040, float(s_cr_mm) / 1000.0)
    lo, hi = 0.02 * L_m, 0.98 * L_m
    out: list[float] = []
    x = lo
    while x <= hi + 1e-9 * L_m:
        if _flexural_bottom_station_allowed(
            float(x), L_m, diagram_kind, support_type, moment_series
        ):
            out.append(float(x))
        x += s_cr
    out = sorted(set(out))
    out = _snap_crack_x_bar_midpoints(out, model, L_m=L_m, s_cr_m=s_cr)
    return _downsample_crack_stations_uniform(out, n_cap)


def _crack_line_style(
    w_mm: float, *, wmax_mm: float | None = None
) -> tuple[float, str, str]:
    """
    Crack stroke width (plotly px) ∝ sqrt(w_k) for visible contrast; fill rgba for tapered crack polygon.
    Very small w still draws faint cracks (non-zero linewidth).
    """
    w = max(0.0, float(w_mm))
    if not math.isfinite(w):
        w = 0.0
    if wmax_mm is not None:
        try:
            wm = float(wmax_mm)
        except (TypeError, ValueError):
            wm = 0.0
        if math.isfinite(wm) and wm > 0.0:
            wn = float(np.clip(w / wm, 0.0, 3.2))
        else:
            wn = float(np.clip(w / 0.30, 0.0, 3.2))
    else:
        wn = float(np.clip(w / 0.30, 0.0, 3.2))
    w_eff = float(math.sqrt(max(wn, 0.0)))
    lw = float(np.clip(1.02 + 5.85 * w_eff, 1.02, 7.35))
    if w <= 1e-9:
        lw = max(lw, 1.12)
    stroke = "rgba(6,6,10,0.97)"
    fa = float(np.clip(0.36 + 0.22 * w_eff, 0.36, 0.82))
    fill = f"rgba(12,12,18,{fa:.3f})"
    return lw, stroke, fill


def _sagging_moment_shape_norm(xi: float, diagram_kind: str, support_type: str | None) -> float:
    """0..1; 1 at maximum sagging-moment region for the active diagram (sketch-scale)."""
    xi = float(np.clip(xi, 0.0, 1.0))
    if diagram_kind == "cantilever_udl":
        return float(np.clip((1.0 - xi) ** 2, 0.0, 1.0))
    if diagram_kind == "fixed_fixed_udl":
        return float(np.clip(math.sin(math.pi * xi) ** 2, 0.0, 1.0))
    if diagram_kind in ("fixed_pinned_udl", "continuous_span_udl"):
        return float(np.clip(4.0 * xi * (1.0 - xi), 0.0, 1.0))
    return float(np.clip(4.0 * xi * (1.0 - xi), 0.0, 1.0))


def _resolved_sls_moment_arrays() -> tuple[np.ndarray, np.ndarray] | None:
    """Full-beam SLS M(x) (alias for :func:`_resolved_sls_moment_arrays_global`)."""
    return _resolved_sls_moment_arrays_global()


def _moment_pos_envelope_efficiency_at(
    x_m: float,
    L_m: float,
    diagram_kind: str,
    support_type_label: str,
    x_ser: np.ndarray | None,
    M_ser: np.ndarray | None,
) -> float:
    """
    Normalised sagging contribution in 0..1 for bottom-fibre crack scaling.
    When SLS ``M(x)`` is available, uses **M⁺ / max(M⁺)** with hogging cut-off (``M ≤ 0`` → no crack height)
    and a light sketch mask near supports; otherwise falls back to the diagram sketch envelope.
    """
    L_m = max(float(L_m), 1e-9)
    xi = float(np.clip(x_m / L_m, 0.0, 1.0))
    if x_ser is not None and M_ser is not None and x_ser.size >= 2 and M_ser.size == x_ser.size:
        m_at = float(np.interp(x_m, x_ser, M_ser, left=float(M_ser[0]), right=float(M_ser[-1])))
        if m_at <= 0.0:
            return 0.0
        m_pos_max = max(1e-9, float(np.max(np.maximum(0.0, M_ser))))
        brk = float(_bottom_tension_intensity(xi, diagram_kind, support_type_label))
        if brk < 0.05:
            return 0.0
        m_pos = max(0.0, m_at)
        return float(np.clip(m_pos / m_pos_max, 0.0, 1.0))
    brk = float(_bottom_tension_intensity(xi, diagram_kind, support_type_label))
    if brk < 0.10:
        return 0.0
    return float(_sagging_moment_shape_norm(xi, diagram_kind, support_type_label))


def _uls_compression_centroid_y_from_top_mm(D_mm: float) -> float | None:
    """
    ULS rectangular stress block (positive bending): resultant at depth a/2 from the
    compression face, with a = γ·c (c and γ from the sagging capacity solve).
    """
    try:
        c_mm = float(get_param("bending_uls_c_pos_mm", 0.0) or 0.0)
        gamma = float(get_param("bending_uls_gamma_pos", 0.0) or 0.0)
    except Exception:
        return None
    if not math.isfinite(c_mm) or not math.isfinite(gamma):
        return None
    if c_mm <= 0.0 or gamma <= 0.0:
        return None
    a_mm = gamma * c_mm
    if not math.isfinite(a_mm) or a_mm <= 0.0:
        return None
    a_mm = min(a_mm, max(D_mm, 1.0))
    return 0.5 * a_mm


def _bending_sls_dn_mm() -> float | None:
    """SLS cracked neutral-axis depth from compression face (mm), if published."""
    for key in ("bending_sls_dn_mm", "bending_sls_dn"):
        try:
            raw = get_param(key, None)
        except Exception:
            raw = None
        if raw is None:
            continue
        try:
            dn = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(dn) and dn > 0.0:
            return dn
    return None


def _layer_y_from_top_mm(layer: Mapping[str, Any] | None) -> float | None:
    """Longitudinal layer ``y`` in mm from compression face (section_layout convention)."""
    if not layer:
        return None
    raw = layer.get("y")
    if raw is None:
        return None
    try:
        y_mm = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(y_mm) or y_mm <= 0.0:
        return None
    return y_mm


def _tension_steel_y_from_top_mm(model: Mapping[str, Any] | None = None) -> float | None:
    """
    Distance from compression face to outer tension steel (mm), for side-view T.
    Prefer the first bottom row from ``compute_section_layout`` (matches drawn bars when ``y`` is set).
    """
    if model is not None:
        layers = model.get("bottom_layers") or []
        if isinstance(layers, list) and layers:
            y_mm = _layer_y_from_top_mm(layers[0] if isinstance(layers[0], Mapping) else None)
            if y_mm is not None:
                return y_mm
    try:
        raw = get_param("bending_sls_y_tension_outer", None)
    except Exception:
        raw = None
    if raw is not None:
        try:
            y_mm = float(raw)
            if math.isfinite(y_mm) and y_mm > 0.0:
                return y_mm
        except (TypeError, ValueError):
            pass
    try:
        d_mm = float(get_param("d", 0.0) or 0.0)
    except (TypeError, ValueError):
        d_mm = 0.0
    if math.isfinite(d_mm) and d_mm > 0.0:
        return d_mm
    return None


def _crack_height_severity_from_w_mm(w_mm: float | None) -> float:
    """Scale crack height slightly with calculated width (load / tension severity)."""
    if w_mm is None:
        return 1.0
    try:
        w = float(w_mm)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(w) or w < 0.0:
        return 1.0
    return float(np.clip(0.74 + 0.62 * min(w / 0.22, 1.85), 0.74, 1.58))


def _neutral_axis_y_from_bottom_m(D_m: float) -> float | None:
    """
    Side-view y of NA (m, from soffit) when SLS cracked NA depth from compression face is in session.
    """
    dn_mm = _bending_sls_dn_mm()
    if dn_mm is None:
        return None
    dn = float(dn_mm)
    D_mm = max(float(D_m) * 1000.0, 1.0)
    dn = min(dn, D_mm - 1e-3)
    return float(D_m - dn / 1000.0)


def _flexural_crack_y0_y1_undeformed_m(
    *,
    xm: float,
    L_m: float,
    D_m: float,
    diagram_kind: str,
    support_type_label: str,
    w_mm: float | None = None,
    m_pos_eff: float | None = None,
) -> tuple[float, float]:
    """
    Undeformed crack tip depths (m from soffit): taller at high moment, shorter at low moment,
    minimum height for visibility, capped at NA when depth is available.
    Crack height also scales slightly with calculated crack width w (tension severity).
    """
    y0_und = 0.028 * D_m
    y_full_und = min(0.58 * D_m, max(0.22 * D_m, 0.52 * float(get_param("d", 520.0) or 520.0) / 1000.0))
    span_h = max(y_full_und - y0_und, 1e-6)
    h_min = max(0.07 * D_m, 0.012)
    xi = xm / max(L_m, 1e-9)
    if m_pos_eff is not None and math.isfinite(float(m_pos_eff)):
        m_scale = float(np.clip(float(m_pos_eff), 0.0, 1.0))
    else:
        m_scale = _sagging_moment_shape_norm(xi, diagram_kind, support_type_label)
    m_scale *= _crack_height_severity_from_w_mm(w_mm)
    m_scale = float(np.clip(m_scale, 0.0, 1.0))
    y1 = y0_und + max(h_min, m_scale * span_h)
    y1 = max(y1, y0_und + h_min)
    na_y = _neutral_axis_y_from_bottom_m(D_m)
    eps = max(0.002 * D_m, 0.001)
    if na_y is not None and math.isfinite(na_y):
        y_cap = float(na_y) - eps
    else:
        try:
            d_m = float(get_param("d", 520.0) or 520.0) / 1000.0
        except (TypeError, ValueError):
            d_m = 0.52 * D_m
        d_m = max(d_m, 0.05 * D_m)
        y_cap = float(np.clip(0.72 * d_m, 0.18 * D_m, 0.78 * D_m))
    y1 = min(y1, y_cap)
    y1 = max(y1, y0_und + h_min)
    return y0_und, y1


def _support_resolution(state: Any) -> dict[str, Any]:
    try:
        from deflection_support import get_deflection_diagram_support_condition

        return get_deflection_diagram_support_condition(state)
    except Exception:
        return {"support_type": "Simply supported", "continuous_end_side": None}


def _pick_reported_delta_total_mm() -> float | None:
    """Best-effort δ_total from the deflection pipeline (may be 0.0 before/without loads)."""
    for key in ("delta_total", "deflection_total_mm"):
        try:
            v = get_param(key)
        except Exception:
            v = None
        if v is None:
            continue
        try:
            f = float(v)
            if math.isfinite(f):
                return f
        except (TypeError, ValueError):
            continue
    try:
        params = (st.session_state.get("results") or {}).get("_deflection_params") or {}
        v = params.get("delta_total")
        if v is not None:
            f = float(v)
            if math.isfinite(f):
                return f
    except Exception:
        pass
    return None


def _ensure_deflection_results_for_diagram() -> None:
    try:
        from deflection_core import compute_deflection_results
        compute_deflection_results(publish=False)
    except Exception:
        pass


def _stub_extend_deflection_xy_mm(
    x: np.ndarray,
    w: np.ndarray,
    L_mm: float,
    support_type: str | None,
    continuous_end_side: Any,
) -> tuple[np.ndarray, np.ndarray]:
    """Match ``build_deflected_beam_plotly`` mesh extension for continuous spans."""
    x = np.asarray(x, dtype=float).reshape(-1)
    w = np.asarray(w, dtype=float).reshape(-1)
    L_mm = float(L_mm)
    if not x.size:
        return x, w
    st_val = (support_type or "").strip()
    _stub = max(0.025 * L_mm, 20.0)
    if st_val == "Continuous – interior span":
        x0 = float(x[0])
        if x0 > -_stub + 1e-6:
            left_pts = np.linspace(-_stub, x0, 8, endpoint=False)
            if left_pts.size:
                x = np.r_[left_pts, x]
                w = np.r_[np.full_like(left_pts, w[0]), w]
    if st_val == "Continuous – end span" and str(continuous_end_side or "right").lower() == "left":
        x0 = float(x[0])
        if x0 > -_stub + 1e-6:
            left_pts = np.linspace(-_stub, x0, 8, endpoint=False)
            if left_pts.size:
                x = np.r_[left_pts, x]
                w = np.r_[np.full_like(left_pts, w[0]), w]
    if st_val == "Continuous – end span" and str(continuous_end_side or "right").lower() != "left":
        xn = float(x[-1])
        right_pts = np.linspace(xn, xn + _stub, 8)[1:]
        if right_pts.size:
            x = np.r_[x, right_pts]
            w = np.r_[w, np.full_like(right_pts, w[-1])]
    if st_val == "Continuous – interior span":
        xn = float(x[-1])
        right_pts = np.linspace(xn, xn + _stub, 8)[1:]
        if right_pts.size:
            x = np.r_[x, right_pts]
            w = np.r_[w, np.full_like(right_pts, w[-1])]
    return x, w


def compute_crack_diagram_deflection_mesh(
    model: dict[str, Any],
    L_mm: float,
    D_mm: float,
    support_resolution: Mapping[str, Any],
) -> dict[str, Any] | None:
    """
    Bottom-fibre deflection w_m(x) in metres along span (visual exaggeration), plus display x.
    Used for deflected slab, reo polylines, and cracks riding the deflected shape.
    """
    L_mm = float(L_mm)
    if L_mm <= 0.0:
        return None

    from ui.diagrams.deflection_diagram import deflected_longitudinal_profile_mm

    _ensure_deflection_results_for_diagram()
    reported = _pick_reported_delta_total_mm()
    floor_mm = max(16.0, 0.004 * L_mm)
    if reported is None or not math.isfinite(reported):
        delta_for_shape = floor_mm
    else:
        delta_for_shape = max(abs(float(reported)), floor_mm)

    support_type = str(support_resolution.get("support_type") or "Simply supported")
    continuous_end_side = support_resolution.get("continuous_end_side")

    x_mm, w_mm = deflected_longitudinal_profile_mm(
        L_mm, support_type, delta_for_shape, n_pts=200
    )
    x = np.asarray(x_mm, dtype=float).reshape(-1)
    w = np.asarray(w_mm, dtype=float).reshape(-1)
    x, w = _stub_extend_deflection_xy_mm(x, w, L_mm, support_type, continuous_end_side)

    D_mm = float(max(D_mm, 1.0))
    max_abs_defl = float(np.max(np.abs(w))) if w.size else 0.0
    scale_factor = diagram_deflection_visual_scale_factor(max_abs_defl, D_mm)
    w_vis = np.asarray(w * scale_factor, dtype=float).reshape(-1)

    work = dict(model)
    work["side_view_display"] = _side_view_display_state(work)

    x_m = x / 1000.0
    w_m = w_vis / 1000.0
    order = np.argsort(x_m, kind="mergesort")
    x_m = x_m[order]
    w_m = w_m[order]
    x_disp = np.array(
        [_side_view_display_x(float(xi), work) for xi in x_m],
        dtype=float,
    )

    L_m = max(float(work.get("total_length_m", 0.0)), 1e-9)
    D_m = max(float(work.get("D_m", 0.0)), 1e-9)
    return {
        "x_m": x_m,
        "w_m": w_m,
        "x_disp": x_disp,
        "work": work,
        "D_m": D_m,
        "L_m": L_m,
        "D_mm": D_mm,
    }


def _defl_w_at_x(defl: dict[str, Any], x_m: float) -> float:
    xm = defl["x_m"]
    wm = defl["w_m"]
    if xm.size == 0:
        return 0.0
    if xm.size == 1:
        return float(wm[0])
    x_c = float(np.clip(x_m, float(xm[0]), float(xm[-1])))
    return float(np.interp(x_c, xm, wm))


def _total_structural_length_m() -> float:
    """Structural axis length (m) for deflection template; matches global moment / multi-span nodes when available."""
    ms = _resolved_sls_moment_arrays_global()
    if ms is not None and ms[0].size >= 2:
        return max(float(ms[0][-1]), 1e-6)
    nodes = _multi_span_node_positions_m()
    if nodes:
        return max(float(nodes[-1]), 1e-6)
    return max(float(get_param("L", 3000.0) or 3000.0) / 1000.0, 0.1)


def _slice_rebase_deflection_mesh(
    defl: dict[str, Any] | None,
    x0_m: float,
    L_win_m: float,
    model_window: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Crop a full-span deflection mesh to ``[x0_m, x0_m + L_win_m]`` and rebase local x to ``0 … L_win_m``.
    """
    if defl is None:
        return None
    xm = np.asarray(defl["x_m"], dtype=float).reshape(-1)
    wm = np.asarray(defl["w_m"], dtype=float).reshape(-1)
    if xm.size == 0:
        return None
    # Uniform local stations so the diagram span is exactly ``0 … L_win`` (coarse global meshes can
    # miss endpoints and would otherwise leave a slight gap vs moment ribbon / supports).
    n = max(48, int(140 * L_win_m / max(L_win_m, 0.12)))
    xloc = np.linspace(0.0, float(L_win_m), n, dtype=float)
    wloc = np.interp(
        float(x0_m) + xloc,
        xm,
        wm,
        left=float(wm[0]),
        right=float(wm[-1]),
    )
    if xloc.size < 2:
        return None
    mw = dict(model_window)
    mw["total_length_m"] = float(L_win_m)
    if str(mw.get("support_condition")) != "cantilever":
        mw["support_positions"] = [0.0, float(L_win_m)]
    work = dict(mw)
    work["side_view_display"] = _side_view_display_state(work)
    x_disp = np.array([_side_view_display_x(float(x), work) for x in xloc], dtype=float)
    return {
        **defl,
        "x_m": np.asarray(xloc, dtype=float),
        "w_m": np.asarray(wloc, dtype=float),
        "x_disp": x_disp,
        "work": work,
        "L_m": float(L_win_m),
    }


def _shift_longitudinal_layer_stations_mm(model: dict[str, Any], dx_m: float) -> None:
    """Rebase bar ``x`` lists (mm along member) when diagram window is a span slice."""
    if dx_m <= 1e-12:
        return
    dx_mm = float(dx_m) * 1000.0
    for key in ("bottom_layers", "top_layers"):
        layers = model.get(key) or []
        if not isinstance(layers, list):
            continue
        out: list[Any] = []
        for ly in layers:
            if not isinstance(ly, Mapping):
                out.append(ly)
                continue
            d = dict(ly)
            xb = d.get("x")
            if isinstance(xb, (list, tuple)) and len(xb) >= 2:
                d["x"] = [float(t) - dx_mm for t in xb if t is not None]
            out.append(d)
        model[key] = out


def _x_anchor_peak_positive_moment(
    moment_series: tuple[np.ndarray, np.ndarray] | None, L_m: float
) -> float | None:
    """Physical x (m, local window) at maximum sagging M⁺ for label / peak alignment."""
    if moment_series is None:
        return None
    x, m = moment_series
    x = np.asarray(x, dtype=float).reshape(-1)
    m = np.asarray(m, dtype=float).reshape(-1)
    if x.size < 2 or m.size != x.size:
        return None
    mpos = np.maximum(0.0, m)
    if float(np.max(mpos)) <= 1e-12:
        return float(0.5 * max(L_m, 1e-9))
    idx = int(np.argmax(mpos))
    return float(np.clip(x[idx], 0.0, max(L_m, 1e-9)))


def _x_anchor_max_abs_moment(
    moment_series: tuple[np.ndarray, np.ndarray] | None, L_m: float
) -> float | None:
    """Physical x (m) where |M| is maximum — primary anchor for crack-width label."""
    if moment_series is None:
        return None
    x, m = moment_series
    x = np.asarray(x, dtype=float).reshape(-1)
    m = np.asarray(m, dtype=float).reshape(-1)
    if x.size < 2 or m.size != x.size:
        return None
    if float(np.max(np.abs(m))) <= 1e-12:
        return float(0.5 * max(L_m, 1e-9))
    idx = int(np.argmax(np.abs(m)))
    return float(np.clip(x[idx], 0.0, max(L_m, 1e-9)))


def _add_sls_compression_tension_markers(
    fig: go.Figure, defl: dict[str, Any], model: Mapping[str, Any]
) -> None:
    """
    Sketch internal resultants C (compression concrete) and T (tension steel) at midspan,
    riding the same rigid vertical translation w(x) as the section. C prefers the ULS rectangular
    stress-block centroid (half of γ·c from the compression face) when bending has published
    c and γ for positive bending; otherwise the SLS cracked wedge centroid (two-thirds d_n).
    T uses the outer bottom bar row from
    the section layout when available, else bending_sls_y_tension_outer or effective depth d.
    """
    work = defl["work"]
    L_m = max(float(defl["L_m"]), 1e-9)
    D_m = max(float(defl["D_m"]), 1e-9)
    D_mm = max(float(defl.get("D_mm") or D_m * 1000.0), 1.0)

    y_t_mm = _tension_steel_y_from_top_mm(model)
    if y_t_mm is None or y_t_mm <= 0.0 or y_t_mm >= D_mm - 1e-3:
        return

    xm = 0.50 * L_m
    xd = float(_side_view_display_x(xm, work))
    w0 = float(_defl_w_at_x(defl, xm))
    y_T = w0 + (D_m - float(y_t_mm) / 1000.0)

    y_c_top_mm: float | None = _uls_compression_centroid_y_from_top_mm(D_mm)
    if y_c_top_mm is None:
        dn_mm = _bending_sls_dn_mm()
        if dn_mm is not None:
            dn_use = min(float(dn_mm), D_mm - 1e-3)
            y_c_top_mm = (2.0 / 3.0) * dn_use

    y_C: float | None = None
    if y_c_top_mm is not None and y_c_top_mm > 0.0:
        y_c_from_top_m = float(y_c_top_mm) / 1000.0
        y_C = w0 + (D_m - y_c_from_top_m)
        if y_C <= y_T + 0.01 * D_m:
            y_C = min(w0 + 0.95 * D_m, max(y_C, y_T + max(0.06 * D_m, 0.03)))

    common = dict(
        xref="x",
        yref="y",
        showarrow=False,
        xanchor="center",
        bgcolor="rgba(255,255,255,0.80)",
        bordercolor="rgba(0,0,0,0.10)",
        borderwidth=1,
        borderpad=3,
    )
    if y_C is not None:
        fig.add_annotation(
            x=xd,
            y=y_C,
            xshift=-14,
            text="<b>C</b>",
            font=dict(size=13, color="#154360"),
            **common,
        )
    fig.add_annotation(
        x=xd,
        y=y_T,
        xshift=14,
        text="<b>T</b>",
        font=dict(size=13, color="#922b21"),
        **common,
    )


def _add_faint_moment_ribbon_deflected(
    fig: go.Figure,
    defl: dict[str, Any],
    *,
    diagram_kind: str,
    support_type_label: str,
    moment_series: tuple[np.ndarray, np.ndarray] | None = None,
) -> None:
    """
    Faint band **inside the tension zone** of the member: height ∝ max(0, M(x)) / max(|M|),
    only where the bottom fibre is in tension (sagging M > 0). No visible outline.
    """
    xm = defl["x_m"]
    wm = defl["w_m"]
    work = defl["work"]
    D_m = float(defl["D_m"])
    L_m = max(float(defl["L_m"]), 1e-9)
    if xm.size < 2:
        return
    n_rib = int(np.clip(24 + 140.0 * L_m / max(L_m, 0.15), 56, 240))
    xs = np.linspace(0.0, L_m, n_rib, dtype=float)
    w_line = np.interp(xs, xm, wm, left=float(wm[0]), right=float(wm[-1]))
    mo_x, mo_m = moment_series if moment_series is not None else (None, None)
    norm = np.zeros(n_rib, dtype=float)
    if (
        mo_x is not None
        and mo_m is not None
        and mo_x.size >= 2
        and mo_m.size == mo_x.size
        and np.all(np.isfinite(mo_x))
        and np.all(np.isfinite(mo_m))
    ):
        M_at = np.interp(
            xs,
            np.asarray(mo_x, dtype=float),
            np.asarray(mo_m, dtype=float),
            left=float(mo_m[0]),
            right=float(mo_m[-1]),
        )
        m_den = max(float(np.max(np.abs(np.asarray(mo_m, dtype=float)))), 1e-9)
        m_pos = np.maximum(0.0, M_at)
        tens = np.array(
            [
                _bottom_tension_intensity(float(np.clip(xx / L_m, 0.0, 1.0)), diagram_kind, support_type_label)
                for xx in xs
            ],
            dtype=float,
        )
        norm = np.where((M_at > 0.0) & (tens >= 0.10), m_pos / m_den, 0.0)
    else:
        for i in range(n_rib):
            norm[i] = _moment_pos_envelope_efficiency_at(
                float(xs[i]), L_m, diagram_kind, support_type_label, None, None
            )
    norm = np.where(norm < 0.02, 0.0, norm)
    x_disp = np.array([_side_view_display_x(float(xx), work) for xx in xs], dtype=float)
    y_lo = w_line + 0.004 * D_m
    thk = np.clip(0.58 * D_m * norm, 0.0, 0.92 * D_m)
    y_hi = y_lo + thk
    x_poly = np.r_[x_disp, x_disp[::-1]]
    y_poly = np.r_[y_lo, y_hi[::-1]]
    fig.add_trace(
        go.Scatter(
            x=x_poly,
            y=y_poly,
            fill="toself",
            mode="lines",
            fillcolor="rgba(175, 195, 245, 0.09)",
            line=dict(width=0, color="rgba(0,0,0,0)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )


def _add_faint_moment_ribbon_straight(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    diagram_kind: str,
    support_type_label: str,
    moment_series: tuple[np.ndarray, np.ndarray] | None = None,
) -> None:
    """Moment intensity band on undeformed geometry when deflection mesh is unavailable."""
    work = dict(model)
    work["side_view_display"] = _side_view_display_state(work)
    L_m = max(float(work["total_length_m"]), 1e-9)
    D_m = max(float(work["D_m"]), 1e-9)
    n = 160
    xs = np.linspace(0.0, L_m, n, dtype=float)
    mo_x, mo_m = moment_series if moment_series is not None else (None, None)
    norm = np.zeros(n, dtype=float)
    if (
        mo_x is not None
        and mo_m is not None
        and mo_x.size >= 2
        and mo_m.size == mo_x.size
    ):
        M_at = np.interp(
            xs,
            np.asarray(mo_x, dtype=float),
            np.asarray(mo_m, dtype=float),
            left=float(mo_m[0]),
            right=float(mo_m[-1]),
        )
        m_den = max(float(np.max(np.abs(np.asarray(mo_m, dtype=float)))), 1e-9)
        m_pos = np.maximum(0.0, M_at)
        tens = np.array(
            [
                _bottom_tension_intensity(float(np.clip(xx / L_m, 0.0, 1.0)), diagram_kind, support_type_label)
                for xx in xs
            ],
            dtype=float,
        )
        norm = np.where((M_at > 0.0) & (tens >= 0.10), m_pos / m_den, 0.0)
    else:
        for i in range(n):
            norm[i] = _moment_pos_envelope_efficiency_at(
                float(xs[i]), L_m, diagram_kind, support_type_label, None, None
            )
    norm = np.where(norm < 0.02, 0.0, norm)
    x_disp = np.array([_side_view_display_x(float(xx), work) for xx in xs], dtype=float)
    y_lo = np.full_like(xs, 0.004 * D_m, dtype=float)
    thk = np.clip(0.58 * D_m * norm, 0.0, 0.92 * D_m)
    y_hi = y_lo + thk
    x_poly = np.r_[x_disp, x_disp[::-1]]
    y_poly = np.r_[y_lo, y_hi[::-1]]
    fig.add_trace(
        go.Scatter(
            x=x_poly,
            y=y_poly,
            fill="toself",
            mode="lines",
            fillcolor="rgba(175, 195, 245, 0.09)",
            line=dict(width=0, color="rgba(0,0,0,0)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )


def _add_deflected_beam_polygon_trace(fig: go.Figure, defl: dict[str, Any]) -> None:
    """Deflected beam only: same grey fill and outline as Shear ``_add_beam_band`` (no straight reference)."""
    D_mm = float(defl["D_mm"])
    x_disp = defl["x_disp"]
    w_m = defl["w_m"]
    y_top_m = w_m + D_mm / 1000.0
    y_bot_m = w_m
    x_poly = np.r_[x_disp, x_disp[::-1], x_disp[:1]]
    y_poly = np.r_[y_top_m, y_bot_m[::-1], y_top_m[:1]]

    fig.add_trace(
        go.Scatter(
            x=x_poly,
            y=y_poly,
            fill="toself",
            mode="lines",
            fillcolor="rgba(205,212,220,0.35)",
            line=dict(color="rgba(35,35,35,1.0)", width=2),
            hoverinfo="skip",
            showlegend=False,
        )
    )


def _add_tension_reo_on_deflected_shape(
    fig: go.Figure,
    model: dict[str, Any],
    defl: dict[str, Any],
) -> None:
    """Longitudinal reo as polylines following rigid vertical translation of each fibre (same w(x))."""
    bottom_layers = model.get("bottom_layers", []) or []
    top_layers = model.get("top_layers", []) or []
    if not bottom_layers and not top_layers:
        return

    work = defl["work"]
    L_m = float(defl["L_m"])
    D_m = float(defl["D_m"])
    D_mm = float(max(defl.get("D_mm") or D_m * 1000.0, 1.0))
    xm = defl["x_m"]
    wm = defl["w_m"]

    bottom_base_y = 0.11 * D_m
    top_base_y = 0.89 * D_m
    n = 129
    xs = np.linspace(0.0, L_m, n)
    w_line = np.interp(xs, xm, wm) if xm.size else np.zeros_like(xs)
    x_d = np.array([_side_view_display_x(float(x), work) for x in xs], dtype=float)

    for idx, layer in enumerate(bottom_layers[:2]):
        db = max(_safe_float(layer.get("db", 20.0), 20.0), 10.0)
        y_mm = _layer_y_from_top_mm(layer if isinstance(layer, Mapping) else None)
        if y_mm is not None and y_mm < D_mm - 1e-6:
            y_und = D_m - y_mm / 1000.0
        else:
            y_und = min(bottom_base_y + idx * 0.07 * D_m, 0.85 * D_m)
        y_path = w_line + y_und
        fig.add_trace(
            go.Scatter(
                x=x_d,
                y=y_path,
                mode="lines",
                line=dict(
                    color=REO_BOTTOM,
                    width=max(2.85, min(5.8, db / 4.6)),
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    for idx, layer in enumerate(top_layers[:2]):
        db = max(_safe_float(layer.get("db", 20.0), 20.0), 10.0)
        y_mm = _layer_y_from_top_mm(layer if isinstance(layer, Mapping) else None)
        if y_mm is not None and y_mm < D_mm - 1e-6:
            y_und = D_m - y_mm / 1000.0
        else:
            y_und = max(top_base_y - idx * 0.07 * D_m, 0.15 * D_m)
        y_path = w_line + y_und
        fig.add_trace(
            go.Scatter(
                x=x_d,
                y=y_path,
                mode="lines",
                line=dict(color=REO_TOP, width=max(2.0, min(4.5, db / 6.0))),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    if bottom_layers:
        xa = 0.82 * L_m
        lyr0 = bottom_layers[0]
        y_mm0 = _layer_y_from_top_mm(lyr0 if isinstance(lyr0, Mapping) else None)
        if y_mm0 is not None and y_mm0 < D_mm - 1e-6:
            y_note_bot = D_m - y_mm0 / 1000.0
        else:
            y_note_bot = min(bottom_base_y + 0.04 * D_m, 0.90 * D_m)
        fig.add_annotation(
            x=_side_view_display_x(xa, work),
            y=_defl_w_at_x(defl, xa) + y_note_bot,
            text="Tension reo",
            showarrow=False,
            font=dict(size=10, color=REO_BOTTOM),
        )
    if top_layers:
        _side_sec = str(st.session_state.get("sec_shape", get_param("sec_shape", "RECT")) or "RECT")
        _, _side_top_lbl = main_longitudinal_reo_pair_labels(_side_sec, variant="inputs_compact")
        xa = 0.22 * L_m
        t0 = top_layers[0]
        y_mm_top0 = _layer_y_from_top_mm(t0 if isinstance(t0, Mapping) else None)
        if y_mm_top0 is not None and y_mm_top0 < D_mm - 1e-6:
            y_note_top = D_m - y_mm_top0 / 1000.0
        else:
            y_note_top = max(top_base_y - 0.04 * D_m, 0.10 * D_m)
        fig.add_annotation(
            x=_side_view_display_x(xa, work),
            y=_defl_w_at_x(defl, xa) + y_note_top,
            text=_side_top_lbl,
            showarrow=False,
            font=dict(size=10, color=REO_TOP),
        )


def _trace_flexural_crack_tapered(
    fig: go.Figure,
    *,
    xm: float,
    y0: float,
    y1: float,
    work: Mapping[str, Any],
    L_m: float,
    lw: float,
    stroke: str,
    fill: str,
) -> None:
    """Tapered crack (wider at soffit, narrower at tip) in display coordinates."""
    frac_top = 0.36
    dx_m = max(0.00072 * L_m, 0.0005 * float(lw) * L_m / 5.8)
    xl = float(_side_view_display_x(xm - dx_m, work))
    xr = float(_side_view_display_x(xm + dx_m, work))
    xtl = float(_side_view_display_x(xm - dx_m * frac_top, work))
    xtr = float(_side_view_display_x(xm + dx_m * frac_top, work))
    xs = [xl, xr, xtr, xtl, xl]
    ys = [y0, y0, y1, y1, y0]
    edge = float(np.clip(0.16 * lw, 0.55, 1.85))
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            fill="toself",
            mode="lines",
            fillcolor=fill,
            line=dict(color=stroke, width=edge),
            hoverinfo="skip",
            showlegend=False,
        )
    )


def _add_flexural_cracks_straight(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    support_type_label: str,
    sr_max_mm: float,
    w_mm: float,
    wmax_mm: float | None = None,
    moment_series: tuple[np.ndarray, np.ndarray] | None = None,
    height_scale: float = 1.0,
) -> float | None:
    """Fallback flexural cracks on undeformed geometry when deflection mesh is unavailable."""
    work = dict(model)
    if not work.get("side_view_display"):
        work["side_view_display"] = _side_view_display_state(work)
    L_m = max(float(work["total_length_m"]), 1e-9)
    D_m = max(float(work["D_m"]), 1e-9)
    dk = _diagram_kind(support_type_label)
    stations = _crack_x_stations_m(
        L_m,
        sr_max_mm,
        dk,
        support_type_label,
        model=model,
        moment_series=moment_series,
    )
    lw, stroke, fill = _crack_line_style(w_mm, wmax_mm=wmax_mm)
    mo_x, mo_m = moment_series if moment_series is not None else (None, None)
    m_effs = [
        float(_moment_pos_envelope_efficiency_at(float(xm), L_m, dk, support_type_label, mo_x, mo_m))
        for xm in stations
    ]
    m_effs = _smooth_1d_5pt(_smooth_1d_3pt(m_effs))
    crack_height_scale = float(np.clip(height_scale, 1.0, 2.0))
    best_x: float | None = None
    best_h = -1.0
    for xm, m_eff in zip(stations, m_effs):
        y0, y1 = _flexural_crack_y0_y1_undeformed_m(
            xm=xm,
            L_m=L_m,
            D_m=D_m,
            diagram_kind=dk,
            support_type_label=support_type_label,
            w_mm=w_mm,
            m_pos_eff=m_eff,
        )
        if crack_height_scale > 1.0:
            y1 = min(0.92 * D_m, y0 + (y1 - y0) * crack_height_scale)
        h = float(y1 - y0)
        if h > best_h:
            best_h = h
            best_x = float(xm)
        _trace_flexural_crack_tapered(
            fig,
            xm=float(xm),
            y0=float(y0),
            y1=float(y1),
            work=work,
            L_m=L_m,
            lw=lw,
            stroke=stroke,
            fill=fill,
        )
    return best_x


def _add_flexural_cracks_on_deflected_shape(
    fig: go.Figure,
    defl: dict[str, Any],
    *,
    support_type_label: str,
    sr_max_mm: float,
    w_mm: float,
    wmax_mm: float | None = None,
    model: Mapping[str, Any] | None = None,
    moment_series: tuple[np.ndarray, np.ndarray] | None = None,
    height_scale: float = 1.0,
) -> float | None:
    """
    Tapered crack polygons in display x, shifted vertically by local w(x) (rigid with section).
    Returns physical x (m, local window) at tallest crack (for optional leader targeting).
    """
    work = defl["work"]
    L_m = float(defl["L_m"])
    D_m = float(defl["D_m"])
    dk = _diagram_kind(support_type_label)
    stations = _crack_x_stations_m(
        L_m,
        sr_max_mm,
        dk,
        support_type_label,
        model=model,
        moment_series=moment_series,
    )

    lw, stroke, fill = _crack_line_style(w_mm, wmax_mm=wmax_mm)
    mo_x, mo_m = moment_series if moment_series is not None else (None, None)
    m_effs: list[float] = []
    for xm in stations:
        m_effs.append(
            float(
                _moment_pos_envelope_efficiency_at(
                    float(xm), L_m, dk, support_type_label, mo_x, mo_m
                )
            )
        )
    m_effs = _smooth_1d_5pt(_smooth_1d_3pt(m_effs))
    crack_height_scale = float(np.clip(height_scale, 1.0, 2.0))
    best_x: float | None = None
    best_h = -1.0
    for xm, m_eff in zip(stations, m_effs):
        y0_und, y1_und = _flexural_crack_y0_y1_undeformed_m(
            xm=xm,
            L_m=L_m,
            D_m=D_m,
            diagram_kind=dk,
            support_type_label=support_type_label,
            w_mm=w_mm,
            m_pos_eff=m_eff,
        )
        if crack_height_scale > 1.0:
            y1_und = min(0.92 * D_m, y0_und + (y1_und - y0_und) * crack_height_scale)
        h = float(y1_und - y0_und)
        if h > best_h:
            best_h = h
            best_x = float(xm)
        w0 = _defl_w_at_x(defl, xm)
        y0 = w0 + y0_und
        y1 = w0 + y1_und
        _trace_flexural_crack_tapered(
            fig,
            xm=float(xm),
            y0=float(y0),
            y1=float(y1),
            work=work,
            L_m=L_m,
            lw=lw,
            stroke=stroke,
            fill=fill,
        )
    return best_x


def _add_crack_width_annotation(
    fig: go.Figure,
    model: dict[str, Any],
    *,
    defl: dict[str, Any] | None,
    w_mm: float,
    wmax_mm: float | None,
    x_anchor_m: float | None = None,
    support_type_label: str = "Simply supported",
    moment_series: tuple[np.ndarray, np.ndarray] | None = None,
    L_m_override: float | None = None,
    D_m_override: float | None = None,
) -> None:
    """
    Crack width label at max(|M|) x, with a subtle leader to the crack tip at that location.
    """
    work = dict(model)
    work["side_view_display"] = _side_view_display_state(work)
    L_m = max(float(L_m_override or work.get("total_length_m", 0.1)), 1e-9)
    D_m = max(float(D_m_override or work.get("D_m", 0.1)), 1e-9)
    xa = float(x_anchor_m) if x_anchor_m is not None else 0.98 * L_m
    xa = float(np.clip(xa, 0.02 * L_m, 0.98 * L_m))
    xd = float(_side_view_display_x(xa, work))
    w_at = float(_defl_w_at_x(defl, xa) if defl is not None else 0.0)
    dk = _diagram_kind(support_type_label)
    mo_x, mo_m = moment_series if moment_series is not None else (None, None)
    m_eff = float(
        _moment_pos_envelope_efficiency_at(
            xa, L_m, dk, support_type_label, mo_x, mo_m
        )
    )
    _y0u, y1u = _flexural_crack_y0_y1_undeformed_m(
        xm=xa,
        L_m=L_m,
        D_m=D_m,
        diagram_kind=dk,
        support_type_label=support_type_label,
        w_mm=w_mm,
        m_pos_eff=m_eff,
    )
    y_tip = w_at + float(y1u)
    y_lbl = y_tip + max(0.09 * D_m, 0.018)
    wv = max(0.0, float(w_mm))
    if not math.isfinite(wv):
        wv = 0.0
    lim = wmax_mm
    if lim is None or not math.isfinite(float(lim)) or float(lim) <= 0:
        try:
            lim = float(get_param("wmax_char_limit", get_param("wmax_char", 0.3)) or 0.3)
        except Exception:
            lim = 0.3
    lim = float(lim)
    fig.add_annotation(
        x=xd,
        y=y_lbl,
        xref="x",
        yref="y",
        ax=xd,
        ay=y_tip,
        axref="x",
        ayref="y",
        text=f"<b>w = {wv:.3f} mm</b><br><span style='font-size:10px'>w'max = {lim:.2f} mm</span>",
        showarrow=True,
        arrowhead=2,
        arrowsize=0.55,
        arrowwidth=1.1,
        arrowcolor="rgba(55,55,65,0.45)",
        xanchor="center",
        align="center",
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="rgba(0,0,0,0.14)",
        borderwidth=1,
        borderpad=5,
        font=dict(size=12, color="#111"),
    )


def _crack_diagram_metrics_from_shared(
    crack_metrics: Mapping[str, Any] | None,
) -> dict[str, float]:
    """
    Diagram inputs from the same crack outputs published via ``update_results`` / ``RESULT_KEYS``
    (``crack_sr_max_mm``, ``crack_width``, …), with optional same-run overrides from ``crack_metrics``.
    """
    cm = dict(crack_metrics or {})
    try:
        sr = float(cm["sr_max_mm"]) if cm.get("sr_max_mm") is not None else float(get_param("crack_sr_max_mm", 0.0) or 0.0)
    except (TypeError, ValueError):
        sr = float(get_param("crack_sr_max_mm", 0.0) or 0.0)
    if not math.isfinite(sr) or sr <= 0.0:
        sr = float(get_param("crack_sr_max_mm", 0.0) or 0.0)
    if not math.isfinite(sr) or sr <= 0.0:
        sr = max(float(get_param("crack_sr_max_mm", 180.0) or 180.0), 80.0)
    try:
        wv = cm.get("w_calc_mm")
        if wv is None:
            wv = get_param("crack_width", get_param("w_calc", 0.0))
        w_mm = float(wv or 0.0)
    except (TypeError, ValueError):
        w_mm = 0.0
    if not math.isfinite(w_mm) or w_mm < 0.0:
        w_mm = 0.0
    wmax_raw = cm.get("wmax_mm")
    if wmax_raw is not None:
        try:
            wmax_mm = float(wmax_raw)
        except (TypeError, ValueError):
            wmax_mm = float(get_param("wmax_char_limit", get_param("wmax_char", 0.3)) or 0.3)
    else:
        try:
            wmax_mm = float(get_param("wmax_char_limit", get_param("wmax_char", 0.3)) or 0.3)
        except (TypeError, ValueError):
            wmax_mm = 0.3
    if not math.isfinite(wmax_mm) or wmax_mm <= 0.0:
        wmax_mm = 0.3
    return {"sr_max_mm": sr, "w_calc_mm": w_mm, "wmax_mm": wmax_mm}


def build_crack_side_view_figure(
    state: Any,
    crack_metrics: Mapping[str, Any] | None = None,
) -> go.Figure:
    """Side elevation: deflected beam (grey), supports, reo, cracks, w label — no undeformed rectangle."""
    mets = _crack_diagram_metrics_from_shared(crack_metrics)
    sr_mm = float(mets["sr_max_mm"])
    w_mm = float(mets["w_calc_mm"])
    wmax_mm: float | None = float(mets["wmax_mm"])

    window = _resolve_crack_diagram_window(state)
    L_win = max(float(window["L_m"]), 0.1)
    x0 = float(window["x0_m"])
    wx, wM = window["x_m"], window["M_m"]
    moment_series: tuple[np.ndarray, np.ndarray] | None = None
    if isinstance(wx, np.ndarray) and isinstance(wM, np.ndarray) and wx.size >= 2 and wM.size == wx.size:
        moment_series = (wx, wM)

    model = _beam_model()
    D_mm = float(get_param("D", 600.0) or 600.0)
    D_m = max(D_mm / 1000.0, 0.05)
    model["D_m"] = D_m

    L_total_m = max(_total_structural_length_m(), L_win)
    model_mesh = dict(model)
    model_mesh["total_length_m"] = L_total_m
    model_mesh["span_m"] = L_total_m

    model_disp = dict(model)
    model_disp["total_length_m"] = L_win
    model_disp["span_m"] = L_win
    model_disp["D_m"] = D_m
    if str(model_disp.get("support_condition")) != "cantilever":
        model_disp["support_positions"] = [0.0, L_win]
    model_disp["side_view_display"] = _side_view_display_state(model_disp)
    sec = model.get("section_x_m")
    if sec is not None and bool(window.get("multi")):
        try:
            model_disp["section_x_m"] = float(
                np.clip(float(sec) - x0, 0.02 * L_win, 0.98 * L_win)
            )
        except (TypeError, ValueError):
            pass
    _shift_longitudinal_layer_stations_mm(model_disp, x0)

    sup_res = _support_resolution(state)
    support_lbl = str(sup_res.get("support_type") or "Simply supported")
    dk = _diagram_kind(support_lbl)

    fig = _build_side_view_figure(
        L_win,
        D_m,
        SIDE_VIEW_VISUAL_HEIGHT,
        str(model_disp.get("support_condition", "simply_supported") or "simply_supported"),
        display_length_m=_side_view_display_length_from_model(model_disp),
    )
    defl_full = compute_crack_diagram_deflection_mesh(
        model_mesh, L_total_m * 1000.0, D_mm, sup_res
    )
    defl = _slice_rebase_deflection_mesh(defl_full, x0, L_win, model_disp)
    if defl is not None:
        _fit_side_view_figure_to_content(
            fig,
            length_m=L_win,
            beam_depth_m=D_m,
            support_condition=str(model_disp.get("support_condition", "simply_supported") or "simply_supported"),
            height=SIDE_VIEW_VISUAL_HEIGHT,
            display_length_m=_side_view_display_length_from_model(model_disp),
            y_min_needed=float(np.min(defl["w_m"])),
            y_max_needed=float(np.max(defl["w_m"])) + D_m,
        )
        _add_faint_moment_ribbon_deflected(
            fig,
            defl,
            diagram_kind=dk,
            support_type_label=support_lbl,
            moment_series=moment_series,
        )
        _add_deflected_beam_polygon_trace(fig, defl)
        _build_side_view_support_shapes(fig, model_disp)
        _add_tension_reo_on_deflected_shape(fig, model_disp, defl)
        _add_flexural_cracks_on_deflected_shape(
            fig,
            defl,
            support_type_label=support_lbl,
            sr_max_mm=sr_mm,
            w_mm=w_mm,
            wmax_mm=wmax_mm,
            model=model_disp,
            moment_series=moment_series,
        )
        _add_sls_compression_tension_markers(fig, defl, model_disp)
    else:
        _add_faint_moment_ribbon_straight(
            fig,
            model_disp,
            diagram_kind=dk,
            support_type_label=support_lbl,
            moment_series=moment_series,
        )
        _build_side_view_support_shapes(fig, model_disp)
        _build_side_view_tension_reo(fig, model_disp)
        _add_flexural_cracks_straight(
            fig,
            model_disp,
            support_type_label=support_lbl,
            sr_max_mm=sr_mm,
            w_mm=w_mm,
            wmax_mm=wmax_mm,
            moment_series=moment_series,
        )
    x_label = _x_anchor_max_abs_moment(moment_series, L_win)
    if x_label is None:
        x_label = _x_anchor_peak_positive_moment(moment_series, L_win)
    _add_crack_width_annotation(
        fig,
        model_disp,
        defl=defl,
        w_mm=w_mm,
        wmax_mm=wmax_mm,
        x_anchor_m=x_label,
        support_type_label=support_lbl,
        moment_series=moment_series,
        L_m_override=L_win,
        D_m_override=D_m,
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(t=8, b=8, l=8, r=8),
        uirevision="crack_diagram_suite_v2",
    )
    return fig


def build_crack_moment_diagram_figure(
    *,
    x_values,
    moment_values,
    L: float,
    support_positions: list[float],
    support_types: list[str],
    support_type_fallback: str,
) -> go.Figure:
    return _shared_build_crack_moment_diagram_figure(
        x_values=x_values,
        moment_values=moment_values,
        L=L,
        support_positions=support_positions,
        support_types=support_types,
        support_type_fallback=support_type_fallback,
    )


