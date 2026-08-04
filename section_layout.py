# section_layout.pyb

import math
import numpy as np
import streamlit as st

from state_runtime_gateway import get_param, get_longitudinal_row_inputs
from section_props.reo_layout import (
    compute_longitudinal_reo_layout_T_I,
    flatten_reo_points as flatten_reo_points_T_I,
)
from section_props.shear_layout import compute_shear_reo_layout_T_I
from typing import Dict, Any, List, Mapping, Tuple, Optional


def _two_row_positions_width(n_bars, bar_dia, w_min, w_max):
    """
    SAME LOGIC as in Inputs page, but copied here so we can reuse it
    without Plotly. If you prefer, you can import from inputs_page
    instead, but that risks circular imports.
    """
    if n_bars <= 0:
        return [], []

    span = w_max - w_min
    if span <= 0:
        return [], []

    min_pitch = max(bar_dia * 1.6, span / 20.0)
    max_single = max(1, int(span // min_pitch))

    if n_bars <= max_single:
        xs1 = np.linspace(w_min, w_max, n_bars)
        return xs1.tolist(), []

    n1 = min(max_single, math.ceil(n_bars / 2))
    n2 = n_bars - n1
    if n2 > max_single:
        n2 = max_single
        n1 = n_bars - n2

    xs1 = np.linspace(w_min, w_max, n1)

    if n2 <= 0:
        xs2 = np.array([])
    elif n2 == 1:
        xs2 = np.array([(w_min + w_max) / 2.0])
    else:
        xs2 = np.linspace(w_min, w_max, n2)

    return xs1.tolist(), xs2.tolist()


def _internal_leg_positions(y_min, y_max, n_legs):
    if n_legs <= 2:
        return []
    span = y_max - y_min
    if span <= 0:
        return []
    return [y_min + span * j / (n_legs - 1) for j in range(1, n_legs - 1)]


def _flatten_reo_points_for_shear(reo_points: Optional[List[Dict[str, Any]]]) -> List[Dict[str, float]]:
    pts: List[Dict[str, float]] = []
    if not reo_points:
        return pts
    for pt in reo_points:
        try:
            db = float(pt.get("db", 0.0) or 0.0)
            x = float(pt.get("x", 0.0) or 0.0)
            y = float(pt.get("y", 0.0) or 0.0)
        except Exception:
            continue
        if db <= 0:
            continue
        pts.append({"x": x, "y": y, "db": db})
    return pts


def _cage_bounds_from_reo_points(
    reo_points: Optional[List[Dict[str, Any]]],
    *,
    default_x0: float,
    default_x1: float,
    default_y0: float,
    default_y1: float,
    clamp_x0: float,
    clamp_x1: float,
    clamp_y0: float,
    clamp_y1: float,
    visual_clearance: float,
) -> tuple[float, float, float, float]:
    pts = _flatten_reo_points_for_shear(reo_points)
    if not pts:
        return default_x0, default_x1, default_y0, default_y1

    min_x = min(pt["x"] - pt["db"] / 2.0 for pt in pts) - visual_clearance
    max_x = max(pt["x"] + pt["db"] / 2.0 for pt in pts) + visual_clearance
    min_y = min(pt["y"] - pt["db"] / 2.0 for pt in pts) - visual_clearance
    max_y = max(pt["y"] + pt["db"] / 2.0 for pt in pts) + visual_clearance

    x0 = max(clamp_x0, min(default_x0, min_x))
    x1 = min(clamp_x1, max(default_x1, max_x))
    y0 = max(clamp_y0, min(default_y0, min_y))
    y1 = min(clamp_y1, max(default_y1, max_y))
    return x0, x1, y0, y1


def compute_shear_reo_layout_pure(
    b: float,
    D: float,
    cover_bot: float,
    cover_top: float,
    cover_side: float,
    lig_d: float,
    lig_legs: int,
    reo_points: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    PURE FUNCTION: Compute shear reinforcement (stirrup/tie) layout for 2D section view.
    
    This function computes the positions of all stirrup legs in the cross-section.
    It is pure (no session state access) and suitable for caching.
    
    Args:
        b: Beam width (mm)
        D: Overall depth (mm)
        cover_bot: Bottom cover (mm)
        cover_top: Top cover (mm)
        cover_side: Side cover (mm)
        lig_d: Ligature/stirrup diameter (mm)
        lig_legs: Number of legs per stirrup
    
    Returns:
        {
            "stirrups": [
                {
                    "legs": [
                        {"x1": x1, "y1": y1, "x2": x2, "y2": y2},  # each leg as a line
                        ...
                    ],
                    "db": lig_d,
                }
            ],
            "cage": {
                "x0": cage_x0, "x1": cage_x1, "y0": cage_y0, "y1": cage_y1
            }
        }
    """
    visual_clearance = 0.0
    default_x0 = max(cover_side - visual_clearance, 5.0)
    default_x1 = min(b - cover_side + visual_clearance, b - 5.0)
    default_y0 = max(cover_top - visual_clearance, 5.0)
    default_y1 = min(D - cover_bot + visual_clearance, D - 5.0)
    cage_x0, cage_x1, cage_y0, cage_y1 = _cage_bounds_from_reo_points(
        reo_points,
        default_x0=default_x0,
        default_x1=default_x1,
        default_y0=default_y0,
        default_y1=default_y1,
        clamp_x0=5.0,
        clamp_x1=b - 5.0,
        clamp_y0=5.0,
        clamp_y1=D - 5.0,
        visual_clearance=visual_clearance,
    )
    
    # If no valid stirrups, return empty structure
    if lig_d <= 0 or lig_legs < 2 or cage_x1 <= cage_x0 or cage_y1 <= cage_y0:
        return {
            "stirrups": [],
            "cage": {
                "x0": cage_x0,
                "x1": cage_x1,
                "y0": cage_y0,
                "y1": cage_y1,
            }
        }
    
    # Stirrup leg positions
    # Left and right outer legs
    y_left = cage_x0
    y_right = cage_x1
    
    # Top and bottom horizontal legs
    y_top = cage_y0
    y_bot = cage_y1
    
    legs = []
    
    # Top horizontal leg (left to right)
    legs.append({
        "x1": y_left,
        "y1": y_top,
        "x2": y_right,
        "y2": y_top,
    })
    
    # Bottom horizontal leg (left to right)
    legs.append({
        "x1": y_left,
        "y1": y_bot,
        "x2": y_right,
        "y2": y_bot,
    })
    
    # Left vertical leg (top to bottom)
    legs.append({
        "x1": y_left,
        "y1": y_top,
        "x2": y_left,
        "y2": y_bot,
    })
    
    # Right vertical leg (top to bottom)
    legs.append({
        "x1": y_right,
        "y1": y_top,
        "x2": y_right,
        "y2": y_bot,
    })
    
    # Internal vertical legs (if lig_legs > 2)
    if lig_legs > 2:
        internal_x = _internal_leg_positions(y_left, y_right, lig_legs)
        for x_pos in internal_x:
            legs.append({
                "x1": x_pos,
                "y1": y_top,
                "x2": x_pos,
                "y2": y_bot,
            })
    
    return {
        "stirrups": [
            {
                "legs": legs,
                "db": lig_d,
            }
        ],
        "cage": {
            "x0": cage_x0,
            "x1": cage_x1,
            "y0": cage_y0,
            "y1": cage_y1,
        }
    }


# ============================================================
# CENTRAL LAYOUT ENGINE - 2-Layer Reinforcement System
# ============================================================

def compute_bar_layout_pure(
    b: float,
    cover_side: float,
    nb_or_s: float,
    db: float,
    s_min: float,
    rowgap: float = 60.0,
) -> Dict[str, Any]:
    """
    Pure function that computes bar layout for a single layer (1 or 2).
    
    INPUTS:
        b: Beam width (mm)
        cover_side: Side cover (mm)
        nb_or_s: User value - if < 30 = number of bars, if ≥ 30 = spacing (mm)
        db: Bar diameter (mm)
        s_min: Minimum clear spacing (mm)
        rowgap: Vertical gap between rows (mm) - used if splitting into 2 rows
    
    RETURNS:
        {
            "mode": "N" or "S",  # Number mode or Spacing mode
            "n_total": int,      # Total number of bars
            "n_row1": int,       # Bars in row 1
            "n_row2": int,       # Bars in row 2 (0 if single row)
            "s_actual": float,   # Actual spacing used (mm)
            "x_positions_row1": List[float],  # Bar centre x positions for row 1
            "x_positions_row2": List[float],  # Bar centre x positions for row 2
            "fits_single_row": bool,          # True if all bars fit in one row
            "auto_split": bool,               # True if auto-split occurred
            "warning": Optional[str],          # Warning message if layout is invalid
        }
    """
    # Compute available length for bar centres
    L_avail = b - 2 * (cover_side + db / 2.0)
    
    if L_avail <= 0:
        return {
            "mode": "N",
            "n_total": 0,
            "n_row1": 0,
            "n_row2": 0,
            "s_actual": 0.0,
            "x_positions_row1": [],
            "x_positions_row2": [],
            "fits_single_row": False,
            "auto_split": False,
            "warning": "Available width is too small for any bars",
        }
    
    # Determine mode and compute n_total
    if nb_or_s < 30.0:
        # NUMBER-OF-BARS MODE
        mode = "N"
        n_total = int(round(max(0, nb_or_s)))
        
        if n_total == 0:
            return {
                "mode": mode,
                "n_total": 0,
                "n_row1": 0,
                "n_row2": 0,
                "s_actual": 0.0,
                "x_positions_row1": [],
                "x_positions_row2": [],
                "fits_single_row": True,
                "auto_split": False,
                "warning": None,
                "s_min": s_min,
                "s_target": None,
                "s_used": 0.0,
            }
        
        # Required length with minimum spacing
        L_req = n_total * db + (n_total - 1) * s_min
        
        if L_req <= L_avail:
            # All bars fit in ONE row with min spacing
            if n_total == 1:
                x_positions = [b / 2.0]
                s_actual = L_avail
            else:
                x_start = cover_side + db / 2.0
                x_end = b - cover_side - db / 2.0
                x_positions = list(np.linspace(x_start, x_end, n_total))
                s_actual = (x_end - x_start) / (n_total - 1) if n_total > 1 else 0.0
            
            return {
                "mode": mode,
                "n_total": n_total,
                "n_row1": n_total,
                "n_row2": 0,
                "s_actual": s_actual,
                "x_positions_row1": x_positions,
                "x_positions_row2": [],
                "fits_single_row": True,
                "auto_split": False,
                "warning": None,
                "s_min": s_min,
                "s_target": None,
                "s_used": s_actual,
            }
        else:
            # Bars do NOT fit in one row - auto-split
            # Fill first row with as many bars as fit
            x_start = cover_side + db / 2.0
            x_end = b - cover_side - db / 2.0
            
            # Maximum bars in row 1: solve n1 * db + (n1 - 1) * s_min <= L_avail
            # n1 <= (L_avail + s_min) / (db + s_min)
            max_n_row1 = int((L_avail + s_min) / (db + s_min))
            max_n_row1 = max(1, max_n_row1)  # At least 1 bar
            
            n_row1 = min(n_total, max_n_row1)
            n_row2 = n_total - n_row1
            
            # Position bars in row 1
            if n_row1 == 1:
                x_positions_row1 = [b / 2.0]
            else:
                x_positions_row1 = list(np.linspace(x_start, x_end, n_row1))
            
            # Position bars in row 2
            if n_row2 == 0:
                x_positions_row2 = []
            elif n_row2 == 1:
                x_positions_row2 = [b / 2.0]
            else:
                x_positions_row2 = list(np.linspace(x_start, x_end, n_row2))
            
            s_actual = (x_end - x_start) / (n_row1 - 1) if n_row1 > 1 else 0.0
            
            warning = None
            if n_row2 > max_n_row1:
                warning = f"Bars still cannot fit with minimum spacing even after splitting. {n_total} bars requested, but only {n_row1 + max_n_row1} can fit."
            
            return {
                "mode": mode,
                "n_total": n_total,
                "n_row1": n_row1,
                "n_row2": n_row2,
                "s_actual": s_actual,
                "x_positions_row1": x_positions_row1,
                "x_positions_row2": x_positions_row2,
                "fits_single_row": False,
                "auto_split": True,
                "warning": warning,
                "s_min": s_min,
                "s_target": None,
                "s_used": s_actual,
            }
    
    else:
        # SPACING MODE
        mode = "S"
        s_target = nb_or_s
        
        # Clamp to minimum spacing
        s_used = max(s_target, s_min)
        
        if s_target < s_min:
            warning = f"Spacing {s_target:.1f} mm increased to minimum {s_min:.1f} mm"
        else:
            warning = None
        
        # Compute how many bars fit
        x_start = cover_side + db / 2.0
        x_end = b - cover_side - db / 2.0
        L_avail_centres = x_end - x_start
        
        if L_avail_centres <= 0:
            return {
                "mode": mode,
                "n_total": 0,
                "n_row1": 0,
                "n_row2": 0,
                "s_actual": s_used,
                "x_positions_row1": [],
                "x_positions_row2": [],
                "fits_single_row": False,
                "auto_split": False,
                "warning": "Available width is too small for any bars",
                "s_min": s_min,
                "s_target": s_target,
                "s_used": s_used,
            }
        
        # Number of bars that fit: n such that (n-1) * s_used <= L_avail_centres
        n_fit = int(L_avail_centres / s_used) + 1
        n_fit = max(1, n_fit)
        
        # Position bars
        if n_fit == 1:
            x_positions = [b / 2.0]
        else:
            x_positions = [x_start + i * s_used for i in range(n_fit)]
            # Ensure last bar doesn't exceed x_end
            if x_positions[-1] > x_end:
                x_positions = x_positions[:-1]
                n_fit = len(x_positions)
        
        return {
            "mode": mode,
            "n_total": n_fit,
            "n_row1": n_fit,
            "n_row2": 0,
            "s_actual": s_used,
            "x_positions_row1": x_positions,
            "x_positions_row2": [],
            "fits_single_row": True,
            "auto_split": False,
            "warning": warning,
        }


def _legacy_rows_from_inputs(
    *,
    section: str,
    rows: Optional[List[Dict[str, Any]]] = None,
    layer_1_value: float,
    layer_1_dia: float,
    layer_2_value: float,
    layer_2_dia: float,
) -> List[Dict[str, Any]]:
    if rows is not None:
        return [dict(row) for row in rows]
    prefix = "top" if section == "top" else "bot"
    defaults = [
        (1, layer_1_value, layer_1_dia, 2 if section == "top" else 4),
        (2, layer_2_value, layer_2_dia, 0),
    ]
    output: List[Dict[str, Any]] = []
    for row_index, nb_or_s, dia, default_bars in defaults:
        mode = "Spacing" if float(nb_or_s or 0.0) >= 30.0 else "Count"
        bars = int(round(float(nb_or_s or 0.0))) if mode == "Count" else default_bars
        spacing = float(nb_or_s or 200.0) if mode == "Spacing" else 200.0
        active = dia > 0.0 and ((mode == "Count" and bars > 0) or (mode == "Spacing" and spacing > 0.0))
        output.append({
            "row_index": row_index,
            "mode": mode,
            "bars": max(0, bars),
            "spacing": spacing,
            "dia": float(dia or 0.0),
            "nb_or_s": float(nb_or_s or 0.0),
            "visible": True,
            "active": active,
        })
    return output


def _count_from_spacing(width: float, dia: float, spacing: float) -> int:
    """
    Number of bars whose centres can be placed along a span ``width`` (mm) at
    nominal centre-to-centre spacing ``spacing`` (mm). Mirrors the spacing branch
    of ``compute_bar_layout_pure`` (trim if the last centre would lie past the span).

    ``dia`` is retained for API compatibility with ``_resolve_row_count``; spacing
    is interpreted as c/c pitch (same as the layout engine when nb_or_s ≥ 30).
    """
    _ = dia  # c/c layout uses pitch directly; bar diameter enforced elsewhere
    if width <= 0.0 or spacing <= 0.0:
        return 0
    s_used = float(spacing)
    n_fit = int(width / s_used) + 1
    n_fit = max(1, n_fit)
    if n_fit == 1:
        return 1
    x_start = 0.0
    x_end = width
    x_positions = [x_start + i * s_used for i in range(n_fit)]
    while len(x_positions) > 1 and x_positions[-1] > x_end + 1e-9:
        x_positions.pop()
    return len(x_positions)


def _resolve_row_count(mode: str, width: float, dia: float, value: float) -> int:
    if value <= 0.0 or dia <= 0.0 or width <= 0.0:
        return 0
    if mode == "Spacing":
        return _count_from_spacing(width, dia, value)
    return max(0, int(round(value)))


def _row_x_positions(x0: float, x1: float, n: int) -> list[float]:
    if n <= 0:
        return []
    if n == 1:
        return [(x0 + x1) / 2.0]
    dx = (x1 - x0) / (n - 1)
    return [x0 + i * dx for i in range(n)]


def _resolve_single_row_band(
    *,
    x0: float,
    x1: float,
    y: float,
    mode: str,
    value: float,
    dia: float,
    min_clear: float,
    row_index: int,
    section: str,
) -> Dict[str, Any]:
    width = x1 - x0
    n_bars = _resolve_row_count(mode, width, dia, value)
    xs = _row_x_positions(x0, x1, n_bars)
    warning = None
    if len(xs) > 1:
        clear = min((b - a) - dia for a, b in zip(xs[:-1], xs[1:]))
        if clear < min_clear - 1e-9:
            warning = f"{section.title()} row {row_index} clear spacing {clear:.1f} mm < minimum {min_clear:.1f} mm"
    spacing_actual = 0.0 if len(xs) <= 1 else (xs[1] - xs[0])
    return {
        "x": xs,
        "y": y,
        "db": dia,
        "row_index": row_index,
        "bar_count": len(xs),
        "spacing_actual": spacing_actual,
        "steel_area": len(xs) * math.pi * dia**2 / 4.0,
        "mode": mode,
        "fit_ok": warning is None,
        "warning": warning,
        "section": section,
    }


def compute_longitudinal_reo_layout(
    b: float,
    D: float,
    cover_bot: float,
    cover_top: float,
    cover_side: float,
    nb_or_s_bot_1: float,
    db_bot_1: float,
    nb_or_s_bot_2: float,
    db_bot_2: float,
    nb_or_s_top_1: float,
    db_top_1: float,
    nb_or_s_top_2: float,
    db_top_2: float,
    rowgap_bot: float,
    rowgap_top: float,
    s_min: float = 25.0,
    bottom_rows: Optional[List[Dict[str, Any]]] = None,
    top_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    CENTRAL FUNCTION: Compute all longitudinal reinforcement bar positions.
    
    This is the SINGLE SOURCE OF TRUTH for bar coordinates.
    All diagrams (2D, 3D, stress-strain) must use this function.
    
    Args:
        b: Beam width (mm)
        D: Overall depth (mm)
        cover_bot: Bottom cover (mm)
        cover_top: Top cover (mm)
        cover_side: Side cover (mm)
        nb_or_s_bot_1: Bottom Layer 1 bars or spacing (<30 = bars, ≥30 = spacing)
        db_bot_1: Bottom Layer 1 bar diameter (mm)
        nb_or_s_bot_2: Bottom Layer 2 bars or spacing
        db_bot_2: Bottom Layer 2 bar diameter (mm)
        nb_or_s_top_1: Top Layer 1 bars or spacing
        db_top_1: Top Layer 1 bar diameter (mm)
        nb_or_s_top_2: Top Layer 2 bars or spacing
        db_top_2: Top Layer 2 bar diameter (mm)
        rowgap_bot: Vertical gap between bottom rows (mm)
        rowgap_top: Vertical gap between top rows (mm)
        s_min: Minimum clear spacing (mm)
    
    Returns:
        {
            "bottom": [
                {"layer": 1, "x": [x1, x2, ...], "y": y1, "db": db_bot_1},
                {"layer": 2, "x": [x1, x2, ...], "y": y2, "db": db_bot_2},
            ],
            "top": [
                {"layer": 1, "x": [x1, x2, ...], "y": y1, "db": db_top_1},
                {"layer": 2, "x": [x1, x2, ...], "y": y2, "db": db_top_2},
            ],
        }
    """
    bottom_rows = _legacy_rows_from_inputs(
        section="bot",
        rows=bottom_rows,
        layer_1_value=nb_or_s_bot_1,
        layer_1_dia=db_bot_1,
        layer_2_value=nb_or_s_bot_2,
        layer_2_dia=db_bot_2,
    )
    top_rows = _legacy_rows_from_inputs(
        section="top",
        rows=top_rows,
        layer_1_value=nb_or_s_top_1,
        layer_1_dia=db_top_1,
        layer_2_value=nb_or_s_top_2,
        layer_2_dia=db_top_2,
    )

    bottom_layers: List[Dict[str, Any]] = []
    top_layers: List[Dict[str, Any]] = []
    warnings: List[str] = []

    prev_y = None
    prev_dia = None
    for row in [row for row in bottom_rows if row.get("active")]:
        dia = float(row.get("dia", 0.0) or 0.0)
        if dia <= 0.0:
            continue
        y = D - cover_bot - dia / 2.0 if prev_y is None else prev_y - prev_dia / 2.0 - rowgap_bot - dia / 2.0
        band = _resolve_single_row_band(
            x0=cover_side + dia / 2.0,
            x1=b - cover_side - dia / 2.0,
            y=y,
            mode=str(row.get("mode", "Count")),
            value=float(row.get("nb_or_s", 0.0) or 0.0),
            dia=dia,
            min_clear=max(dia, s_min),
            row_index=int(row.get("row_index", 1) or 1),
            section="bottom",
        )
        if y - dia / 2.0 < 0.0:
            band["fit_ok"] = False
            band["warning"] = f"Bottom row {band['row_index']} does not fit within available depth."
        band["layer"] = band["row_index"]
        if band.get("warning"):
            warnings.append(str(band["warning"]))
        bottom_layers.append(band)
        prev_y = y
        prev_dia = dia

    prev_y = None
    prev_dia = None
    for row in [row for row in top_rows if row.get("active")]:
        dia = float(row.get("dia", 0.0) or 0.0)
        if dia <= 0.0:
            continue
        y = cover_top + dia / 2.0 if prev_y is None else prev_y + prev_dia / 2.0 + rowgap_top + dia / 2.0
        band = _resolve_single_row_band(
            x0=cover_side + dia / 2.0,
            x1=b - cover_side - dia / 2.0,
            y=y,
            mode=str(row.get("mode", "Count")),
            value=float(row.get("nb_or_s", 0.0) or 0.0),
            dia=dia,
            min_clear=max(dia, s_min),
            row_index=int(row.get("row_index", 1) or 1),
            section="top",
        )
        if y + dia / 2.0 > D:
            band["fit_ok"] = False
            band["warning"] = f"Top row {band['row_index']} does not fit within available depth."
        band["layer"] = band["row_index"]
        if band.get("warning"):
            warnings.append(str(band["warning"]))
        top_layers.append(band)
        prev_y = y
        prev_dia = dia

    return {
        "bottom": bottom_layers,
        "top": top_layers,
        "warnings": warnings,
    }


def compute_section_layout_pure(
    b: float,
    D: float,
    cover_bot: float,
    cover_top: float,
    cover_side: float,
    nb_or_s_bot_1: float,
    db_bot_1: float,
    nb_or_s_bot_2: float,
    db_bot_2: float,
    nb_or_s_top_1: float,
    db_top_1: float,
    nb_or_s_top_2: float,
    db_top_2: float,
    rowgap_bot: float,
    rowgap_top: float,
    lig_legs: int = 2,
    lig_d: float = 10.0,
    bottom_rows: Optional[List[Dict[str, Any]]] = None,
    top_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    PURE FUNCTION: Compute a canonical 2D cross-section layout (geometry + bar positions)
    in *section coordinates*:

      - x: 0 → b (left to right)
      - y: 0 at top fibre, +D at soffit (same as Inputs 2D figure)

    This is a pure function with no session state access - suitable for caching.
    
    Args:
        b: Beam width (mm)
        D: Overall depth (mm)
        cover_bot: Bottom cover (mm)
        cover_top: Top cover (mm)
        cover_side: Side cover (mm)
        nb_or_s_bot_1: Bottom Layer 1 bars or spacing
        db_bot_1: Bottom Layer 1 bar diameter (mm)
        nb_or_s_bot_2: Bottom Layer 2 bars or spacing
        db_bot_2: Bottom Layer 2 bar diameter (mm)
        nb_or_s_top_1: Top Layer 1 bars or spacing
        db_top_1: Top Layer 1 bar diameter (mm)
        nb_or_s_top_2: Top Layer 2 bars or spacing
        db_top_2: Top Layer 2 bar diameter (mm)
        rowgap_bot: Vertical gap between bottom rows (mm)
        rowgap_top: Vertical gap between top rows (mm)
        lig_legs: Number of ligature legs
        lig_d: Ligature diameter (mm)

    Returns dict with:
      {
        "b": b,
        "D": D,
        "cage": { "x0":..., "x1":..., "y0":..., "y1":... },
        "bot":  { "x": [...], "y": [...], "db": db_bot },
        "top":  { "x": [...], "y": [...], "db": db_top },
        "lig":  { "legs": lig_legs, "d": lig_d, "internal_x": [...] },
        "reo_layout": { "bottom": [...], "top": [...] },
      }
    """

    # ---- Use central layout function (same as 3D model) ----
    reo_layout = compute_longitudinal_reo_layout(
        b=b, D=D,
        cover_bot=cover_bot, cover_top=cover_top, cover_side=cover_side,
        nb_or_s_bot_1=nb_or_s_bot_1, db_bot_1=db_bot_1,
        nb_or_s_bot_2=nb_or_s_bot_2, db_bot_2=db_bot_2,
        nb_or_s_top_1=nb_or_s_top_1, db_top_1=db_top_1,
        nb_or_s_top_2=nb_or_s_top_2, db_top_2=db_top_2,
        rowgap_bot=rowgap_bot, rowgap_top=rowgap_top,
        bottom_rows=bottom_rows,
        top_rows=top_rows,
    )
    
    # Flatten bottom layers into single lists (for backward compatibility)
    bot_x = []
    bot_y = []
    db_bot_primary = db_bot_1  # Use Layer 1 as primary for legacy compatibility
    for layer_data in reo_layout["bottom"]:
        bot_x.extend(layer_data["x"])
        bot_y.extend([layer_data["y"]] * len(layer_data["x"]))
    
    # Flatten top layers into single lists
    top_x = []
    top_y = []
    db_top_primary = db_top_1  # Use Layer 1 as primary for legacy compatibility
    for layer_data in reo_layout["top"]:
        top_x.extend(layer_data["x"])
        top_y.extend([layer_data["y"]] * len(layer_data["x"]))

    # Max longitudinal bar dia (for bar -> lig clearance)
    max_bar_d = max(
        [0.0]
        + [float(layer_data.get("db", 0.0) or 0.0) for layer_data in reo_layout.get("bottom", [])]
        + [float(layer_data.get("db", 0.0) or 0.0) for layer_data in reo_layout.get("top", [])]
    )
    horiz_clear = 0.5 * max_bar_d

    # ---- concrete outline is implicitly 0..b, 0..D ----

    # ---- lig cage based on covers ----
    cage_x0 = max(cover_side, 5.0)
    cage_x1 = min(b - cover_side, b - 5.0)
    cage_y0 = max(cover_top, 5.0)
    cage_y1 = min(D - cover_bot, D - 5.0)

    # internal lig leg x positions (for completeness)
    internal_legs_x = []
    if lig_d > 0 and lig_legs > 2:
        internal_legs_x = _internal_leg_positions(cage_x0, cage_x1, lig_legs)

    return {
        "b": b,
        "D": D,
        "cage": {
            "x0": cage_x0,
            "x1": cage_x1,
            "y0": cage_y0,
            "y1": cage_y1,
        },
        "bot": {"x": bot_x, "y": bot_y, "db": db_bot_primary},
        "top": {"x": top_x, "y": top_y, "db": db_top_primary},
        "lig": {
            "legs": lig_legs,
            "d": lig_d,
            "internal_x": internal_legs_x,
        },
        # NEW: Include full 2-layer structure for diagrams that need it
        "reo_layout": reo_layout,
    }


def compute_section_layout(state: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """
    Project one explicit input state into a section layout.

    The no-argument form preserves the established session-backed API for
    legacy callers.  Region consumers should pass their committed snapshot so
    layout construction cannot observe a mixture of session-state revisions.
    """
    source = state if state is not None else st.session_state

    def _get(name: str, default: Any = None) -> Any:
        if name in source:
            value = source.get(name)
            return default if value is None else value
        if state is None:
            return get_param(name, default)
        return default

    def _norm_shape_name(raw: str) -> str:
        raw = (raw or "").strip()
        lo = raw.lower()
        if lo.startswith("t"):
            return "T-Section"
        if lo.startswith("i"):
            return "I-Section"
        if lo.startswith("rectangle") or lo.startswith("rect"):
            return "Rectangle (b × D)"
        return "Rectangle (b × D)"

    raw_shape = (
        source.get("shape_name")
        or source.get("sec_shape")
        or source.get("section_shape")
        or source.get("geometry_section_shape")
        or _get("sec_shape")
        or "RECT"
    )
    shape_name = _norm_shape_name(str(raw_shape))


    D = float(_get("D", 600.0))
    if shape_name.startswith("T-Section"):
        dims = {
            "bf": float(_get("bf", 600.0)),
            "tf": float(_get("tf", 120.0)),
            "bw": float(_get("bw", 300.0)),
            "D": D,
        }
        b_env = dims["bf"]
    elif shape_name.startswith("I-Section"):
        dims = {
            "bf": float(_get("bf", 600.0)),
            "tf": float(_get("tf", 120.0)),
            "tw": float(_get("tw", 200.0)),
            "D": D,
        }
        b_env = dims["bf"]
    else:
        dims = {
            "b": float(_get("b", 400.0)),
            "D": D,
        }
        b_env = dims["b"]

    cover_bot = float(_get("cover_bot", 40.0))
    cover_top = float(_get("cover_top", 40.0))
    cover_side = _get("cover_side", None)
    if cover_side is None:
        cover_side = min(cover_top, cover_bot)
    cover_side = float(cover_side)

    rowgap_bot = float(_get("rowgap_bot", 60.0))
    rowgap_top = float(_get("rowgap_top", 60.0))
    min_clear = float(_get("s_min", 25.0))
    row_source = dict(source) if state is not None else None
    top_rows = get_longitudinal_row_inputs("top", row_source)
    bottom_rows = get_longitudinal_row_inputs("bot", row_source)

    def _mode(prefix: str) -> str:
        return str(source.get(f"inputs_{prefix}_layout_mode", source.get(f"{prefix}_layout_mode", "Count")))

    def _nb_or_s(prefix: str, default_count: float, default_spacing: float) -> float:
        if _mode(prefix) == "Count":
            return float(source.get(f"{prefix}_count", default_count))
        return float(source.get(f"{prefix}_spacing", default_spacing))

    db_bot_1 = float(_get("db_bot_1", 20.0))
    db_bot_2 = float(_get("db_bot_2", db_bot_1))
    db_top_1 = float(_get("db_top_1", 16.0))
    db_top_2 = float(_get("db_top_2", db_top_1))

    reo = {
        "cover_top": cover_top,
        "cover_bot": cover_bot,
        "cover_side": cover_side,
        "rowgap_top": rowgap_top,
        "rowgap_bot": rowgap_bot,
        "min_clear_spacing": min_clear,
        "top1_layout_mode": _mode("top1"),
        "top2_layout_mode": _mode("top2"),
        "bot1_layout_mode": _mode("bot1"),
        "bot2_layout_mode": _mode("bot2"),
        "nb_or_s_top_1": _nb_or_s("top1", 2.0, 200.0),
        "nb_or_s_top_2": _nb_or_s("top2", 0.0, 200.0),
        "nb_or_s_bot_1": _nb_or_s("bot1", 4.0, 200.0),
        "nb_or_s_bot_2": _nb_or_s("bot2", 0.0, 200.0),
        "db_top_1": db_top_1,
        "db_top_2": db_top_2,
        "db_bot_1": db_bot_1,
        "db_bot_2": db_bot_2,
        "nb_top": int(_nb_or_s("top1", 2.0, 200.0) + _nb_or_s("top2", 0.0, 200.0)) if _mode("top1") == "Count" else 0,
        "db_top": db_top_1,
        "nb_bot": int(_nb_or_s("bot1", 4.0, 200.0) + _nb_or_s("bot2", 0.0, 200.0)) if _mode("bot1") == "Count" else 0,
        "db_bot": db_bot_1,
        "top_rows": top_rows,
        "bottom_rows": bottom_rows,
        "lig_d": float(_get("lig_d", 0.0)),
        "lig_legs": int(_get("lig_legs", 0)),
        "s_lig": float(_get("s_lig", 200.0)),
        "top_flange_reo_enabled": bool(_get("top_flange_reo_enabled", False)),
        "bot_flange_reo_enabled": bool(_get("bot_flange_reo_enabled", False)),
        "top_flange_mirror_lr": bool(_get("top_flange_mirror_lr", True)),
        "bot_flange_mirror_lr": bool(_get("bot_flange_mirror_lr", True)),
        "top_flange_left_count": int(_get("top_flange_left_count", 0) or 0),
        "top_flange_left_dia": float(_get("top_flange_left_dia", 16.0)),
        "top_flange_left_rows": int(_get("top_flange_left_rows", 1) or 1),
        "top_flange_left_row_spacing": float(_get("top_flange_left_row_spacing", rowgap_top)),
        "top_flange_left_clear_spacing_mode": str(_get("top_flange_left_clear_spacing_mode", "count") or "count"),
        "top_flange_right_count": int(_get("top_flange_right_count", 0) or 0),
        "top_flange_right_dia": float(_get("top_flange_right_dia", 16.0)),
        "top_flange_right_rows": int(_get("top_flange_right_rows", 1) or 1),
        "top_flange_right_row_spacing": float(_get("top_flange_right_row_spacing", rowgap_top)),
        "top_flange_right_clear_spacing_mode": str(_get("top_flange_right_clear_spacing_mode", "count") or "count"),
        "bot_flange_left_count": int(_get("bot_flange_left_count", 0) or 0),
        "bot_flange_left_dia": float(_get("bot_flange_left_dia", 20.0)),
        "bot_flange_left_rows": int(_get("bot_flange_left_rows", 1) or 1),
        "bot_flange_left_row_spacing": float(_get("bot_flange_left_row_spacing", rowgap_bot)),
        "bot_flange_left_clear_spacing_mode": str(_get("bot_flange_left_clear_spacing_mode", "count") or "count"),
        "bot_flange_right_count": int(_get("bot_flange_right_count", 0) or 0),
        "bot_flange_right_dia": float(_get("bot_flange_right_dia", 20.0)),
        "bot_flange_right_rows": int(_get("bot_flange_right_rows", 1) or 1),
        "bot_flange_right_row_spacing": float(_get("bot_flange_right_row_spacing", rowgap_bot)),
        "bot_flange_right_clear_spacing_mode": str(_get("bot_flange_right_clear_spacing_mode", "count") or "count"),
        "top_flange_transverse_enabled": bool(_get("top_flange_transverse_enabled", False)),
        "bot_flange_transverse_enabled": bool(_get("bot_flange_transverse_enabled", False)),
        "top_flange_transverse_dia": float(_get("top_flange_transverse_dia", 10.0) or 10.0),
        "bot_flange_transverse_dia": float(_get("bot_flange_transverse_dia", 10.0) or 10.0),
        "top_flange_transverse_spacing": float(_get("top_flange_transverse_spacing", 200.0) or 200.0),
        "bot_flange_transverse_spacing": float(_get("bot_flange_transverse_spacing", 200.0) or 200.0),
        "top_flange_transverse_legs": int(_get("top_flange_transverse_legs", 2) or 2),
        "bot_flange_transverse_legs": int(_get("bot_flange_transverse_legs", 2) or 2),
    }

    if shape_name.startswith(("T-Section", "I-Section")):
        reo_err = None
        try:
            reo_layout = compute_longitudinal_reo_layout_T_I(
                shape_name=shape_name,
                dims=dims,
                cover_side=cover_side,
                cover_top=cover_top,
                cover_bot=cover_bot,
                min_clear_spacing=min_clear,
                rowgap_top=rowgap_top,
                rowgap_bot=rowgap_bot,
                reo=reo,
                max_rows=max(
                    len([row for row in top_rows if row.get("active")]),
                    len([row for row in bottom_rows if row.get("active")]),
                    1,
                ),
            )
            reo_points = flatten_reo_points_T_I(reo_layout)
        except ValueError as e:
            reo_err = str(e)
            reo_layout = {"top": [], "bottom": []}
            reo_points = []

        shear_layout = compute_shear_reo_layout_T_I(
            shape_name=shape_name,
            dims=dims,
            cover_side=cover_side,
            cover_top=cover_top,
            cover_bot=cover_bot,
            lig_d=float(reo.get("lig_d", 0.0)),
            lig_legs=int(reo.get("lig_legs", 0)),
            reo_points=reo_points,
        )
        cage = shear_layout.get("cage", {})
        lig = {"legs": int(reo.get("lig_legs", 0) or 0), "d": float(reo.get("lig_d", 0.0) or 0.0)}
        return {
            "shape_name": shape_name,
            "dims": dims,
            "reo": reo,
            "reo_layout": reo_layout,
            "reo_points": reo_points,
            "reo_error": reo_err,
            "b": b_env,
            "D": D,
            "cage": cage,
            "lig": lig,
        }

    # Rectangle fallback (use existing pure layout)
    layout = compute_section_layout_pure(
        b=b_env, D=D,
        cover_bot=cover_bot, cover_top=cover_top, cover_side=cover_side,
        nb_or_s_bot_1=float(reo.get("nb_or_s_bot_1", 4.0)),
        db_bot_1=db_bot_1,
        nb_or_s_bot_2=float(reo.get("nb_or_s_bot_2", 0.0)),
        db_bot_2=db_bot_2,
        nb_or_s_top_1=float(reo.get("nb_or_s_top_1", 2.0)),
        db_top_1=db_top_1,
        nb_or_s_top_2=float(reo.get("nb_or_s_top_2", 0.0)),
        db_top_2=db_top_2,
        rowgap_bot=rowgap_bot, rowgap_top=rowgap_top,
        lig_legs=int(reo.get("lig_legs", 0) or 0),
        lig_d=float(reo.get("lig_d", 0.0) or 0.0),
        bottom_rows=bottom_rows,
        top_rows=top_rows,
    )

    def _flatten_rect(layout_reo: Dict[str, Any]) -> List[Dict[str, Any]]:
        pts: List[Dict[str, Any]] = []
        for layer_name in ("top", "bottom"):
            for band in layout_reo.get(layer_name, []):
                db = float(band.get("db", 0.0))
                ys = band.get("y", [])
                if isinstance(ys, (int, float)):
                    ys = [ys] * len(band.get("x", []))
                for x, y in zip(band.get("x", []), ys):
                    pts.append({"x": float(x), "y": float(y), "db": db, "layer": layer_name})
        return pts

    layout.update({
        "shape_name": shape_name,
        "dims": dims,
        "reo": reo,
        "reo_points": _flatten_rect(layout.get("reo_layout", {})),
    })
    return layout


# Conditional caching: bypass in debug mode, cache in production
def _get_compute_section_layout_cached():
    """Get the cached or uncached version based on debug mode."""
    try:
        from src.debug.debug_flags import is_debug_enabled
        if is_debug_enabled():
            # Debug mode: no caching
            return _compute_section_layout_cached_impl
        else:
            # Production mode: use cache
            return st.cache_data(show_spinner=False)(_compute_section_layout_cached_impl)
    except ImportError:
        # Debug module not available: use cache
        return st.cache_data(show_spinner=False)(_compute_section_layout_cached_impl)

def _compute_section_layout_cached_impl(
    b: float,
    D: float,
    cover_bot: float,
    cover_top: float,
    cover_side: float,
    nb_or_s_bot_1: float,
    db_bot_1: float,
    nb_or_s_bot_2: float,
    db_bot_2: float,
    nb_or_s_top_1: float,
    db_top_1: float,
    nb_or_s_top_2: float,
    db_top_2: float,
    rowgap_bot: float,
    rowgap_top: float,
    lig_legs: int = 2,
    lig_d: float = 10.0,
) -> Dict[str, Any]:
    """
    CACHED wrapper for compute_section_layout_pure.
    
    This function caches the layout computation based on all input parameters.
    Use this in pages that draw diagrams to avoid recomputing layout on every rerun.
    
    Args: Same as compute_section_layout_pure
    
    Returns: Same as compute_section_layout_pure
    """
    return compute_section_layout_pure(
        b=b, D=D,
        cover_bot=cover_bot, cover_top=cover_top, cover_side=cover_side,
        nb_or_s_bot_1=nb_or_s_bot_1, db_bot_1=db_bot_1,
        nb_or_s_bot_2=nb_or_s_bot_2, db_bot_2=db_bot_2,
        nb_or_s_top_1=nb_or_s_top_1, db_top_1=db_top_1,
        nb_or_s_top_2=nb_or_s_top_2, db_top_2=db_top_2,
        rowgap_bot=rowgap_bot, rowgap_top=rowgap_top,
        lig_legs=lig_legs, lig_d=lig_d,
    )


# Public wrapper that uses conditional caching
def compute_section_layout_cached(*args, **kwargs):
    """Public wrapper for compute_section_layout_cached with conditional caching."""
    _compute_fn = _get_compute_section_layout_cached()
    return _compute_fn(*args, **kwargs)
