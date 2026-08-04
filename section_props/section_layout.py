from __future__ import annotations
import math


def _x_positions_even(x_min: float, x_max: float, n: int):
    if n <= 0:
        return []
    if n == 1:
        return [(x_min + x_max) / 2]
    dx = (x_max - x_min) / (n - 1)
    return [x_min + i * dx for i in range(n)]


def compute_longitudinal_reo_layout(
    *,
    b: float,
    D: float,
    cover_side: float,
    cover_top: float,
    cover_bot: float,
    nb_top: int,
    db_top: float,
    nb_bot: int,
    db_bot: float,
    min_clear_spacing: float = 20.0,
    rowgap_top: float = 60.0,
    rowgap_bot: float = 60.0,
):
    """
    Returns 2-layer structure identical to your app’s plotting expectations:

    {
      "top":    [ {"x":[...], "y":[...], "db":...}, {"x":[...], "y":[...], "db":...}, ... ],
      "bottom": [ {"x":[...], "y":[...], "db":...}, ... ]
    }

    Rules:
    - cover to edge
    - min clear spacing between bars in same row
    - multi-row packing if needed
    - single bar row centered
    """

    def pack_layer(nbars: int, db: float, y0: float, direction: int, rowgap: float):
        # direction: +1 goes downwards (top layers), -1 goes upwards (bottom layers)
        if nbars <= 0 or db <= 0:
            return []

        r = db / 2.0
        x_min = cover_side + r
        x_max = b - cover_side - r
        if x_max <= x_min:
            return []

        # max bars in one row based on min clear spacing
        pitch = db + min_clear_spacing
        avail = x_max - x_min
        if avail <= 0:
            return []

        max_in_row = int(math.floor(avail / pitch) + 1)
        max_in_row = max(1, max_in_row)

        layers = []
        remaining = nbars
        row = 0

        while remaining > 0:
            nrow = min(max_in_row, remaining)
            remaining -= nrow

            xs = _x_positions_even(x_min, x_max, nrow)
            y = y0 + direction * row * rowgap

            layers.append(
                {
                    "x": xs,
                    "y": [y] * len(xs),
                    "db": db,
                }
            )
            row += 1

        return layers

    # y positions are bar CENTRELINE, consistent with plotting
    top_layers = pack_layer(
        nb_top, db_top,
        y0=cover_top + db_top / 2.0,
        direction=+1,
        rowgap=rowgap_top,
    )
    bot_layers = pack_layer(
        nb_bot, db_bot,
        y0=D - cover_bot - db_bot / 2.0,
        direction=-1,
        rowgap=rowgap_bot,
    )

    return {"top": top_layers, "bottom": bot_layers}


def _internal_leg_positions(x_min: float, x_max: float, n_legs: int):
    """Internal stirrup leg positions across width (excluding the two outer legs)."""
    if n_legs <= 2:
        return []
    span = x_max - x_min
    if span <= 0:
        return []
    return [x_min + span * j / (n_legs - 1) for j in range(1, n_legs - 1)]


def _flatten_reo_points_for_shear(reo_points: list[dict] | None) -> list[dict[str, float]]:
    pts: list[dict[str, float]] = []
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


def compute_shear_reo_layout_pure(
    *,
    b: float,
    D: float,
    cover_bot: float,
    cover_top: float,
    cover_side: float,
    lig_d: float,
    lig_legs: int,
    reo_points: list[dict] | None = None,
):
    """
    Pure shear layout used for Plotly drawing.

    Returns:
    {
      "cage": {"x0","y0","x1","y1"},
      "stirrups": [
         {"legs": [{"x1","y1","x2","y2"}, ...]}
      ]
    }

    Cage is drawn as a rectangle (centreline-ish) inside cover.
    Legs are vertical line segments.
    """

    # Basic validity
    if lig_d <= 0 or lig_legs < 2:
        return {"cage": None, "stirrups": []}

    visual_clearance = 0.0
    default_x0 = max(cover_side - visual_clearance, 5.0)
    default_x1 = min(b - cover_side + visual_clearance, b - 5.0)
    default_y0 = max(cover_top - visual_clearance, 5.0)
    default_y1 = min(D - cover_bot + visual_clearance, D - 5.0)

    pts = _flatten_reo_points_for_shear(reo_points)
    if pts:
        min_x = min(pt["x"] - pt["db"] / 2.0 for pt in pts) - visual_clearance
        max_x = max(pt["x"] + pt["db"] / 2.0 for pt in pts) + visual_clearance
        min_y = min(pt["y"] - pt["db"] / 2.0 for pt in pts) - visual_clearance
        max_y = max(pt["y"] + pt["db"] / 2.0 for pt in pts) + visual_clearance
        x0 = max(5.0, min(default_x0, min_x))
        x1 = min(b - 5.0, max(default_x1, max_x))
        y0 = max(5.0, min(default_y0, min_y))
        y1 = min(D - 5.0, max(default_y1, max_y))
    else:
        x0, x1, y0, y1 = default_x0, default_x1, default_y0, default_y1

    # Guard (don’t draw garbage)
    if x1 <= x0 or y1 <= y0:
        return {"cage": None, "stirrups": []}

    cage = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}

    # Stirrup legs: outer legs + internal legs (equally spaced between outer legs)
    xs = [x0] + _internal_leg_positions(x0, x1, lig_legs) + [x1]

    legs = [{"x1": x, "y1": y0, "x2": x, "y2": y1} for x in xs]

    return {
        "cage": cage,
        "stirrups": [{"legs": legs}],
    }


