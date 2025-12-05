# section_layout.py
import math
import numpy as np
import streamlit as st

from state_and_helpers import get_param
from typing import Dict, Any


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


def compute_section_layout() -> Dict[str, Any]:
    """
    Compute a canonical 2D cross-section layout (geometry + bar positions)
    in *section coordinates*:

      - x: 0 → b (left to right)
      - y: 0 at top fibre, +D at soffit (same as Inputs 2D figure)

    Returns dict with:
      {
        "b": b,
        "D": D,
        "cage": { "x0":..., "x1":..., "y0":..., "y1":... },
        "bot":  { "x": [...], "y": [...], "db": db_bot },
        "top":  { "x": [...], "y": [...], "db": db_top },
        "lig":  { "legs": lig_legs, "d": lig_d, "internal_x": [...] },
      }
    """
    # Geometry
    b = float(get_param("b", 400.0) or 400.0)
    D = float(get_param("D", 600.0) or 600.0)

    # Longitudinal reinforcement
    nb_bot = int(get_param("nb_bot", 4) or 0)
    nb_top = int(get_param("nb_top", 2) or 0)
    db_bot = float(get_param("db_bot", 20.0) or 20.0)
    db_top = float(get_param("db_top", 16.0) or 16.0)

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

    # Max longitudinal bar dia (for bar → lig clearance)
    max_bar_d = max(db_bot, db_top, 0.0)
    horiz_clear = 0.5 * max_bar_d

    # ---- concrete outline is implicitly 0..b, 0..D ----

    # ---- lig cage based on covers ----
    cage_x0 = max(cover_side, 5.0)
    cage_x1 = min(b - cover_side, b - 5.0)
    cage_y0 = max(cover_top, 5.0)
    cage_y1 = min(D - cover_bot, D - 5.0)

    # ---- bar positions (same logic as Inputs figure) ----
    x_min = cage_x0 + horiz_clear
    x_max = cage_x1 - horiz_clear
    if x_max <= x_min:
        mid = 0.5 * (cage_x0 + cage_x1)
        span = max(10.0, (cage_x1 - cage_x0) * 0.4)
        x_min = mid - span / 2.0
        x_max = mid + span / 2.0

    max_bar_d_vertical = max(db_bot, db_top, max(1.0, abs(lig_d)))
    bar_edge_offset = max_bar_d_vertical * 0.8
    y_min_cage = cage_y0 + bar_edge_offset
    y_max_cage = cage_y1 - bar_edge_offset

    # bottom bars
    y1_bot = D - (cover_bot + 0.5 * db_bot)
    y2_bot = y1_bot - rowgap_bot
    min_z_bot = 0.5 * db_bot + 5.0
    max_z_bot = D - 0.5 * db_bot - 5.0
    y1_bot = float(
        np.clip(y1_bot, max(y_min_cage, min_z_bot), min(y_max_cage, max_z_bot))
    )
    y2_bot = float(
        np.clip(y2_bot, max(y_min_cage, min_z_bot), min(y_max_cage, max_z_bot))
    )

    bx1, bx2 = _two_row_positions_width(nb_bot, db_bot, x_min, x_max)
    bot_x = bx1 + bx2
    bot_y = [y1_bot] * len(bx1) + [y2_bot] * len(bx2)

    # top bars
    y1_top = cover_top + 0.5 * db_top
    y2_top = y1_top + rowgap_top
    min_z_top = 0.5 * db_top + 5.0
    max_z_top = D - 0.5 * db_top - 5.0
    y1_top = float(
        np.clip(y1_top, max(y_min_cage, min_z_top), min(y_max_cage, max_z_top))
    )
    y2_top = float(
        np.clip(y2_top, max(y_min_cage, min_z_top), min(y_max_cage, max_z_top))
    )

    tx1, tx2 = _two_row_positions_width(nb_top, db_top, x_min, x_max)
    top_x = tx1 + tx2
    top_y = [y1_top] * len(tx1) + [y2_top] * len(tx2)

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
        "bot": {"x": bot_x, "y": bot_y, "db": db_bot},
        "top": {"x": top_x, "y": top_y, "db": db_top},
        "lig": {
            "legs": lig_legs,
            "d": lig_d,
            "internal_x": internal_legs_x,
        },
    }
