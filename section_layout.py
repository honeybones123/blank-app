# section_layout.py
import math
import numpy as np
import streamlit as st

from state_and_helpers import get_param
from typing import Dict, Any, List, Tuple, Optional


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


def compute_shear_reo_layout_pure(
    b: float,
    D: float,
    cover_bot: float,
    cover_top: float,
    cover_side: float,
    lig_d: float,
    lig_legs: int,
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
    # Compute cage boundaries (same as in compute_section_layout_pure)
    cage_x0 = max(cover_side, 5.0)
    cage_x1 = min(b - cover_side, b - 5.0)
    cage_y0 = max(cover_top, 5.0)
    cage_y1 = min(D - cover_bot, D - 5.0)
    
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
    # Compute layout for each layer independently
    s_min_bot_1 = max(db_bot_1, s_min)
    layout_bot_1 = compute_bar_layout_pure(
        b=b, cover_side=cover_side, nb_or_s=nb_or_s_bot_1,
        db=db_bot_1, s_min=s_min_bot_1, rowgap=rowgap_bot
    )
    
    layout_bot_2 = None
    if nb_or_s_bot_2 > 0:
        s_min_bot_2 = max(db_bot_2, s_min)
        layout_bot_2 = compute_bar_layout_pure(
            b=b, cover_side=cover_side, nb_or_s=nb_or_s_bot_2,
            db=db_bot_2, s_min=s_min_bot_2, rowgap=rowgap_bot
        )
    
    s_min_top_1 = max(db_top_1, s_min)
    layout_top_1 = compute_bar_layout_pure(
        b=b, cover_side=cover_side, nb_or_s=nb_or_s_top_1,
        db=db_top_1, s_min=s_min_top_1, rowgap=rowgap_top
    )
    
    layout_top_2 = None
    if nb_or_s_top_2 > 0:
        s_min_top_2 = max(db_top_2, s_min)
        layout_top_2 = compute_bar_layout_pure(
            b=b, cover_side=cover_side, nb_or_s=nb_or_s_top_2,
            db=db_top_2, s_min=s_min_top_2, rowgap=rowgap_top
        )
    
    # Bottom Layer 1: y position from bottom cover
    y_bot_layer1 = D - (cover_bot + db_bot_1 / 2.0)
    
    # Bottom Layer 2: y position with rowgap offset (above Layer 1)
    y_bot_layer2 = y_bot_layer1 - rowgap_bot if layout_bot_2 else None
    
    # Top Layer 1: y position from top cover
    y_top_layer1 = cover_top + db_top_1 / 2.0
    
    # Top Layer 2: y position with rowgap offset (below Layer 1)
    y_top_layer2 = y_top_layer1 + rowgap_top if layout_top_2 else None
    
    # Build bottom layers
    bottom_layers = []
    
    # Bottom Layer 1 - use row 1 positions only (Layer 1 is always in its own row)
    if layout_bot_1["n_row1"] > 0:
        bottom_layers.append({
            "layer": 1,
            "x": layout_bot_1["x_positions_row1"],
            "y": y_bot_layer1,
            "db": db_bot_1,
        })
    
    # Bottom Layer 2 - separate row
    if layout_bot_2 and layout_bot_2["n_row1"] > 0:
        bottom_layers.append({
            "layer": 2,
            "x": layout_bot_2["x_positions_row1"],
            "y": y_bot_layer2,
            "db": db_bot_2,
        })
    
    # Build top layers
    top_layers = []
    
    # Top Layer 1 - use row 1 positions only
    if layout_top_1["n_row1"] > 0:
        top_layers.append({
            "layer": 1,
            "x": layout_top_1["x_positions_row1"],
            "y": y_top_layer1,
            "db": db_top_1,
        })
    
    # Top Layer 2 - separate row
    if layout_top_2 and layout_top_2["n_row1"] > 0:
        top_layers.append({
            "layer": 2,
            "x": layout_top_2["x_positions_row1"],
            "y": y_top_layer2,
            "db": db_top_2,
        })
    
    return {
        "bottom": bottom_layers,
        "top": top_layers,
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

    # Max longitudinal bar dia (for bar → lig clearance)
    max_bar_d = max(db_bot_1, db_bot_2, db_top_1, db_top_2, 0.0)
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


def compute_section_layout() -> Dict[str, Any]:
    """
    Wrapper that reads from session state and calls the pure function.
    For backward compatibility - new code should use compute_section_layout_cached().
    """
    # Geometry
    b = float(get_param("b", 400.0) or 400.0)
    D = float(get_param("D", 600.0) or 600.0)

    # Get 2-layer reinforcement parameters (same as 3D model)
    nb_or_s_bot_1 = float(get_param("nb_or_s_bot_1", 4.0) or 4.0)
    db_bot_1 = float(get_param("db_bot_1", 20.0) or 20.0)
    nb_or_s_bot_2 = float(get_param("nb_or_s_bot_2", 0.0) or 0.0)
    db_bot_2 = float(get_param("db_bot_2", 20.0) or 20.0)
    
    nb_or_s_top_1 = float(get_param("nb_or_s_top_1", 2.0) or 2.0)
    db_top_1 = float(get_param("db_top_1", 16.0) or 16.0)
    nb_or_s_top_2 = float(get_param("nb_or_s_top_2", 0.0) or 0.0)
    db_top_2 = float(get_param("db_top_2", 16.0) or 16.0)

    rowgap_bot = float(get_param("rowgap_bot", 60.0) or 60.0)
    rowgap_top = float(get_param("rowgap_top", 60.0) or 60.0)

    cover_bot = float(get_param("cover_bot", 40.0) or 40.0)
    cover_top = float(get_param("cover_top", 40.0) or 40.0)

    cover_side = float(
        st.session_state.get("inputs_cover_side_local", min(cover_top, cover_bot))
    )

    # Shear reinforcement
    lig_legs_raw = get_param("lig_legs", 2)
    try:
        lig_legs = int(lig_legs_raw or 0)
    except Exception:
        lig_legs = 0

    lig_d = float(get_param("lig_d", 10.0) or 10.0)

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


@st.cache_data(show_spinner=False)
def compute_section_layout_cached(
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




