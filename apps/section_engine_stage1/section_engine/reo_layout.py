from __future__ import annotations
import math
from typing import Dict, List, Tuple


def _x_positions_even(x_min: float, x_max: float, n: int) -> List[float]:
    if n <= 0:
        return []
    if n == 1:
        return [(x_min + x_max) / 2.0]
    dx = (x_max - x_min) / (n - 1)
    return [x_min + i * dx for i in range(n)]


def _pack_in_box(
    *,
    nbars: int,
    db: float,
    x0: float, x1: float,
    y0: float, y1: float,
    min_clear_spacing: float,
    rowgap: float,
    direction: int,   # +1 rows go down, -1 rows go up
    max_rows=1,
) -> List[Dict]:
    """
    Packs bars within the rectangular placement box [x0,x1]×[y0,y1] (bar centrelines).
    Ensures:
      - min clear spacing in x
      - multiple rows if needed
      - stops if vertical space exhausted (never draws outside)
    Returns layers: [{"x":[...],"y":[...],"db":db}, ...]
    """
    if nbars <= 0 or db <= 0:
        return []
    r = db / 2.0

    # x limits already centreline-based; guard
    if x1 <= x0:
        return []

    # If rowgap is missing/zero/too small, the "second row" will overlap the first
    # and LOOK like 1 row. Force a minimum rowgap based on bar diameter + min clear.
    min_rowgap = db + min_clear_spacing
    if rowgap is None or rowgap <= 0:
        rowgap = min_rowgap
    elif rowgap < min_rowgap:
        rowgap = min_rowgap

    pitch = db + min_clear_spacing
    avail = x1 - x0
    max_in_row = int(math.floor(avail / pitch) + 1)
    max_in_row = max(1, max_in_row)

    layers: List[Dict] = []
    remaining = nbars
    rows = 0

    # first row y is at y0 (for top) or y1 (for bottom) depending on direction
    base_y = y0 if direction > 0 else y1

    while remaining > 0 and rows < max_rows:
        nrow = min(max_in_row, remaining)
        remaining -= nrow

        xs = _x_positions_even(x0, x1, nrow)
        y = base_y + direction * rows * rowgap

        # hard clamp: if row centerline exits box, stop (no outside drawing)
        if y < y0 - 1e-6 or y > y1 + 1e-6:
            break

        layers.append({"x": xs, "y": [y] * len(xs), "db": db})
        rows += 1

    if remaining > 0:
        raise ValueError(
            f"Cannot fit reinforcement: {remaining} bar(s) could not be placed "
            f"within the available zone using the current cover/spacing/row-gap. "
            f"Try: reduce bar count/diameter, reduce min clear spacing, reduce row gap, "
            f"increase flange thickness (top) / available depth (bottom), or increase width."
        )

    return layers


def compute_longitudinal_reo_layout_T_I(
    *,
    shape_name: str,
    dims: Dict[str, float],
    cover_side: float,
    cover_top: float,
    cover_bot: float,
    nb_top: int,
    db_top: float,
    nb_bot: int,
    db_bot: float,
    min_clear_spacing: float,
    rowgap_top: float,
    rowgap_bot: float,
) -> Dict[str, List[Dict]]:
    """
    Stage-1: T/I only.
    Bars are constrained to actual concrete perimeters (not just envelope):

    T:
      - top bars inside flange (0..bf, 0..tf)
      - bottom bars inside web zone (x_web0..x_web1, tf..D)

    I:
      - top bars inside top flange (0..bf, 0..tf)
      - bottom bars inside bottom flange (0..bf, D-tf..D)
    """
    bf = float(dims["bf"])
    D = float(dims["D"])
    tf = float(dims["tf"])

    # Centreline limits
    def x_limits_full_width(db: float) -> Tuple[float, float]:
        r = db / 2.0
        return (cover_side + r, bf - cover_side - r)

    def y_limits(y_min_edge: float, y_max_edge: float, db: float) -> Tuple[float, float]:
        r = db / 2.0
        return (y_min_edge + r, y_max_edge - r)

    if shape_name.startswith("T-Section"):
        bw = float(dims["bw"])
        x_web0 = (bf - bw) / 2.0
        x_web1 = x_web0 + bw

        # Top bars: flange only
        x0_t, x1_t = x_limits_full_width(db_top)
        y0_t, y1_t = y_limits(cover_top, tf - cover_top, db_top)
        try:
            top = _pack_in_box(
                nbars=nb_top, db=db_top,
                x0=x0_t, x1=x1_t,
                y0=y0_t, y1=y1_t,
                min_clear_spacing=min_clear_spacing,
                rowgap=rowgap_top,
                direction=+1,
                max_rows=2,
            )
        except ValueError as e:
            raise ValueError(f"Top reinforcement (I/T flange) layout invalid: {e}") from None

        # Bottom bars: web zone only
        r_bot = db_bot / 2.0
        x0_b = x_web0 + cover_side + r_bot
        x1_b = x_web1 - cover_side - r_bot
        y0_b, y1_b = y_limits(tf, D - cover_bot, db_bot)
        try:
            bottom = _pack_in_box(
                nbars=nb_bot, db=db_bot,
                x0=x0_b, x1=x1_b,
                y0=y0_b, y1=y1_b,
                min_clear_spacing=min_clear_spacing,
                rowgap=rowgap_bot,
                direction=-1,
                max_rows=2,
            )
        except ValueError as e:
            raise ValueError(f"Bottom reinforcement (I/T zone) layout invalid: {e}") from None

        return {"top": top, "bottom": bottom}

    if shape_name.startswith("I-Section"):
        tw = float(dims["tw"])

        # Top bars: top flange
        x0_t, x1_t = x_limits_full_width(db_top)
        y0_t, y1_t = y_limits(cover_top, tf - cover_top, db_top)
        try:
            top = _pack_in_box(
                nbars=nb_top, db=db_top,
                x0=x0_t, x1=x1_t,
                y0=y0_t, y1=y1_t,
                min_clear_spacing=min_clear_spacing,
                rowgap=rowgap_top,
                direction=+1,
                max_rows=2,
            )
        except ValueError as e:
            raise ValueError(f"Top reinforcement (I/T flange) layout invalid: {e}") from None

        # Bottom bars: bottom flange
        x0_b, x1_b = x_limits_full_width(db_bot)
        y0_b, y1_b = y_limits(D - tf + cover_bot, D - cover_bot, db_bot)
        try:
            bottom = _pack_in_box(
                nbars=nb_bot, db=db_bot,
                x0=x0_b, x1=x1_b,
                y0=y0_b, y1=y1_b,
                min_clear_spacing=min_clear_spacing,
                rowgap=rowgap_bot,
                direction=-1,
                max_rows=2,
            )
        except ValueError as e:
            raise ValueError(f"Bottom reinforcement (I/T zone) layout invalid: {e}") from None

        return {"top": top, "bottom": bottom}

    raise ValueError("Stage-1 reo layout supports only T-Section and I-Section.")


def flatten_reo_points(reo_layout: Dict[str, List[Dict]]) -> List[Dict]:
    pts: List[Dict] = []
    for layer_name in ("top", "bottom"):
        for band in reo_layout.get(layer_name, []):
            db = float(band["db"])
            for x, y in zip(band["x"], band["y"]):
                pts.append({"x": float(x), "y": float(y), "db": db, "layer": layer_name})
    return pts
