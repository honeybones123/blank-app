from __future__ import annotations

import math
from typing import Dict, List, Any

from section_props.shape_utils import normalise_shape_name


def _x_positions_even(x_min: float, x_max: float, n: int) -> List[float]:
    if n <= 0:
        return []
    if n == 1:
        return [(x_min + x_max) / 2.0]
    dx = (x_max - x_min) / (n - 1)
    return [x_min + i * dx for i in range(n)]


def _check_clear_spacing(xs: List[float], db: float, min_clear: float) -> None:
    """Checks clear spacing between adjacent bars."""
    if len(xs) <= 1:
        return
    for a, b in zip(xs[:-1], xs[1:]):
        clear = (b - a) - db
        if clear < min_clear - 1e-9:
            raise ValueError(
                f"clear spacing {clear:.1f} mm < min_clear_spacing {min_clear:.1f} mm"
            )


def _count_from_spacing(width: float, db: float, s: float) -> int:
    # centers must be >= db + s
    c2c = db + s
    if width <= db:
        return 1
    return max(1, int(math.floor((width - db) / c2c)) + 1)


def _row_x_positions(x0: float, x1: float, n: int) -> list[float]:
    if n <= 0:
        return []
    if n == 1:
        return [(x0 + x1) / 2.0]
    dx = (x1 - x0) / (n - 1)
    return [x0 + i * dx for i in range(n)]


def _check_row_clear(xs: list[float], db: float, min_clear: float):
    for a, b in zip(xs[:-1], xs[1:]):
        clear = (b - a) - db
        if clear < min_clear - 1e-9:
            raise ValueError(f"clear spacing {clear:.1f} < min_clear_spacing {min_clear:.1f} mm")


def _merge_reo_layers(layout: dict) -> dict:
    """
    Compatibility shim:
    Ensures layout always contains legacy keys:
      - "top": list
      - "bottom": list
    while preserving any detailed groups (top_flange/top_web/etc).
    """
    if not isinstance(layout, dict):
        return {"top": [], "bottom": []}

    def _as_list(x):
        if not x:
            return []
        return x if isinstance(x, list) else [x]

    top = []
    bottom = []

    # legacy
    top += _as_list(layout.get("top"))
    bottom += _as_list(layout.get("bottom"))

    # new detailed keys (if present)
    top += _as_list(layout.get("top_flange"))
    top += _as_list(layout.get("top_web"))
    top += _as_list(layout.get("top_left"))
    top += _as_list(layout.get("top_right"))

    bottom += _as_list(layout.get("bottom_flange"))
    bottom += _as_list(layout.get("bottom_web"))
    bottom += _as_list(layout.get("bottom_left"))
    bottom += _as_list(layout.get("bottom_right"))

    # write back guaranteed keys
    layout["top"] = top
    layout["bottom"] = bottom
    return layout


def _split_flange_outstands(*, bf: float, web_w: float):
    """
    Returns the inner faces of the flange (web faces) for a symmetric section.
    If web_w >= bf, there are no outstands.
    """
    if web_w >= bf:
        return None
    xL_inner = (bf - web_w) / 2.0
    xR_inner = xL_inner + web_w
    return xL_inner, xR_inner


def _xs_even(x0: float, x1: float, n: int):
    if n <= 0:
        return []
    if n == 1:
        return [(x0 + x1) / 2.0]
    dx = (x1 - x0) / (n - 1)
    return [x0 + i * dx for i in range(n)]


def _check_clear(xs, db: float, min_clear: float):
    for a, b in zip(xs[:-1], xs[1:]):
        clear = (b - a) - db
        if clear < min_clear - 1e-9:
            raise ValueError(f"clear spacing {clear:.1f} < min_clear_spacing {min_clear:.1f} mm")


def _place_in_outstands(
    *,
    n: int,
    db: float,
    bf: float,
    web_w: float,
    cover_side: float,
    min_clear_spacing: float,
):
    """
    Places n bars in the flange OUTSTANDS only, applying cover to OUTER + INNER flange faces.
    Strategy:
      - Split bars roughly evenly between left and right outstands.
      - If n is odd, try to put 1 bar in the web zone center IF it fits between inner faces with cover.
        Otherwise put the extra bar on the right.
    Returns list of x positions.
    """
    if n <= 0:
        return []

    split = _split_flange_outstands(bf=bf, web_w=web_w)
    if split is None:
        # no outstands: treat like rectangular flange
        x0 = cover_side + db / 2.0
        x1 = bf - cover_side - db / 2.0
        xs = _xs_even(x0, x1, n)
        _check_clear(xs, db, min_clear_spacing)
        return xs

    xL_inner, xR_inner = split

    # Left outstand usable interval
    L0 = cover_side + db / 2.0
    L1 = xL_inner - cover_side - db / 2.0

    # Right outstand usable interval
    R0 = xR_inner + cover_side + db / 2.0
    R1 = bf - cover_side - db / 2.0

    if L1 <= L0 or R1 <= R0:
        raise ValueError(
            f"No horizontal room in flange outstands after covers. "
            f"bf={bf:.1f}, web_w={web_w:.1f}, cover_side={cover_side:.1f}, db={db:.1f}"
        )

    nL = n // 2
    nR = n // 2
    nC = 0

    if n % 2 == 1:
        # try a center bar in web zone (between inner faces), with cover to inner faces
        C0 = xL_inner + cover_side + db / 2.0
        C1 = xR_inner - cover_side - db / 2.0
        if C1 >= C0:
            nC = 1
        else:
            # no room in web zone -> push extra to right
            nR += 1

    xs = []
    if nL > 0:
        xsL = _xs_even(L0, L1, nL)
        _check_clear(xsL, db, min_clear_spacing)
        xs += xsL

    if nC == 1:
        xs.append((bf / 2.0))

    if nR > 0:
        xsR = _xs_even(R0, R1, nR)
        _check_clear(xsR, db, min_clear_spacing)
        xs += xsR

    # sort so plotting looks clean
    xs = sorted(xs)
    return xs


def _require_top_rows_within_flange(*, tf: float, cover_top: float, db: float, rowgap: float, rows_used: int) -> None:
    """
    Checks that all top rows fit inside top flange thickness tf.
    y=0 at top surface. Row 1 center is cover_top + db/2.
    Row i center is cover_top + db/2 + (i-1)*rowgap.
    Requirement: last_center + db/2 <= tf
    """
    if rows_used <= 1:
        return
    last_center = cover_top + db / 2.0 + (rows_used - 1) * rowgap
    if last_center + db / 2.0 > tf + 1e-9:
        raise ValueError(
            f"Top flange too thin for {rows_used} rows of bars: "
            f"need cover_top + db + (rows-1)*rowgap <= tf, but "
            f"{cover_top:.1f} + {db:.1f} + {(rows_used-1)*rowgap:.1f} = "
            f"{(cover_top + db + (rows_used-1)*rowgap):.1f} > tf {tf:.1f} mm. "
            f"Increase tf, reduce cover/db, or reduce rowgap/min clear."
        )


def _require_bottom_rows_within_flange(*, tf: float, D: float, cover_bot: float, db: float, rowgap: float, rows_used: int) -> None:
    """
    Checks that all bottom rows fit inside bottom flange thickness tf (for I-sections).
    Bottom surface is at y=D. Row 1 center is D - cover_bot - db/2.
    Row i center is D - cover_bot - db/2 - (i-1)*rowgap.
    Requirement: lowest_center - db/2 >= D - tf
    """
    if rows_used <= 1:
        return
    lowest_center = D - cover_bot - db / 2.0 - (rows_used - 1) * rowgap
    if lowest_center - db / 2.0 < (D - tf) - 1e-9:
        raise ValueError(
            f"Bottom flange too thin for {rows_used} rows of bars: "
            f"need cover_bot + db + (rows-1)*rowgap <= tf, but "
            f"{cover_bot:.1f} + {db:.1f} + {(rows_used-1)*rowgap:.1f} = "
            f"{(cover_bot + db + (rows_used-1)*rowgap):.1f} > tf {tf:.1f} mm. "
            f"Increase tf, reduce cover/db, or reduce rowgap/min clear."
        )


def _pack_rows(
    *,
    n: int,
    db: float,
    x0: float,
    x1: float,
    y_start: float,
    direction: int,
    min_clear_spacing: float,
    rowgap: float,
    max_rows: int,
) -> List[Dict]:
    """
    Packs n bars into up to max_rows rows inside [x0,x1] at y_start, stepping by rowgap.
    direction: +1 means rows go downward (increasing y), -1 means upward (decreasing y).
    Returns list of "bands": [{"x":[...], "y":[...], "db":db}, ...]
    """
    if n <= 0 or db <= 0:
        return []

    if x1 <= x0:
        raise ValueError("no horizontal room after covers")

    # If rowgap is missing/zero/too small, the "second row" will overlap the first
    # and LOOK like 1 row. Force a minimum rowgap based on bar diameter + min clear.
    min_rowgap = db + min_clear_spacing
    if rowgap is None or rowgap <= 0:
        rowgap = min_rowgap
    elif rowgap < min_rowgap:
        rowgap = min_rowgap

    # Estimate max bars in one row using min clear spacing
    # center-to-center >= db + min_clear
    c2c = db + min_clear_spacing
    width = x1 - x0

    # If only one bar can fit, it can always be centered in the available width.
    if n == 1:
        return [{"x": [(x0 + x1) / 2.0], "y": [y_start], "db": db}]

    # maximum count for even spacing respecting min clear
    # need (n-1)*c2c <= width  => n <= width/c2c + 1
    nmax = int(math.floor(width / c2c + 1.0))
    if nmax < 1:
        raise ValueError("no bars can fit within available width")

    bands: List[Dict] = []
    remaining = n
    row = 0

    while remaining > 0 and row < max_rows:
        row += 1
        put = min(remaining, nmax)

        # Evenly distribute across full width to keep symmetric look
        xs = _x_positions_even(x0, x1, put)
        _check_clear_spacing(xs, db, min_clear_spacing)

        y = y_start + direction * (row - 1) * rowgap
        bands.append({"x": xs, "y": [y] * len(xs), "db": db})

        remaining -= put

    if remaining > 0:
        raise ValueError(
            f"need {n} bars but only fit {n - remaining} bars in {max_rows} rows "
            f"(width={width:.1f}mm, db={db:.1f}mm, min_clear={min_clear_spacing:.1f}mm). "
            f"Try reducing bar count/diameter, reducing cover, or increasing bw/bf."
        )

    return bands


def compute_longitudinal_reo_layout_T_I(
    *,
    shape_name: str,
    dims: Dict[str, float],
    cover_side: float,
    cover_top: float,
    cover_bot: float,
    min_clear_spacing: float,
    rowgap_top: float,
    rowgap_bot: float,
    reo: Dict[str, Any],
    max_rows: int = 2,
) -> Dict[str, List[Dict]]:
    """
    Longitudinal bar layout for T and I sections (Stage 1).
    Supports up to 2 rows top and bottom.
    Coordinates: x in [0,bf], y in [0,D] (y positive downward).
    """
    shape = shape_name

    # --- Read 2-layer inputs (Count or Spacing) ---
    top1_mode = str(reo.get("top1_layout_mode", "Count"))
    top2_mode = str(reo.get("top2_layout_mode", "Count"))
    bot1_mode = str(reo.get("bot1_layout_mode", "Count"))
    bot2_mode = str(reo.get("bot2_layout_mode", "Count"))

    nb_or_s_top_1 = float(reo.get("nb_or_s_top_1", 0.0) or 0.0)
    nb_or_s_top_2 = float(reo.get("nb_or_s_top_2", 0.0) or 0.0)
    db_top_1 = float(reo.get("db_top_1", reo.get("db_top", 20.0)) or 20.0)
    db_top_2 = float(reo.get("db_top_2", db_top_1) or db_top_1)

    nb_or_s_bot_1 = float(reo.get("nb_or_s_bot_1", 0.0) or 0.0)
    nb_or_s_bot_2 = float(reo.get("nb_or_s_bot_2", 0.0) or 0.0)
    db_bot_1 = float(reo.get("db_bot_1", reo.get("db_bot", 20.0)) or 20.0)
    db_bot_2 = float(reo.get("db_bot_2", db_bot_1) or db_bot_1)

    rowgap_top = float(reo.get("rowgap_top", rowgap_top) or rowgap_top)
    rowgap_bot = float(reo.get("rowgap_bot", rowgap_bot) or rowgap_bot)

    # enforce minimum clear vertical gap between layers (clear gap, not c/c)
    rowgap_top = max(rowgap_top, min_clear_spacing)
    rowgap_bot = max(rowgap_bot, min_clear_spacing)

    if max_rows < 2:
        nb_or_s_top_2 = 0.0
        nb_or_s_bot_2 = 0.0

    if shape.startswith("T-Section"):
        bf = float(dims["bf"]); tf = float(dims["tf"]); bw = float(dims["bw"]); D = float(dims["D"])

        # --- Top bars IN FLANGE ---
        x0_t = cover_side + db_top_1 / 2.0
        x1_t = bf - cover_side - db_top_1 / 2.0
        width_top = x1_t - x0_t
        if width_top <= 0:
            raise ValueError("Top bars: no horizontal room after covers")

        if top1_mode == "Count":
            n_top_1 = int(nb_or_s_top_1)
        else:
            n_top_1 = 0 if nb_or_s_top_1 <= 0 else _count_from_spacing(width_top, db_top_1, nb_or_s_top_1)
        if top2_mode == "Count":
            n_top_2 = int(nb_or_s_top_2)
        else:
            n_top_2 = 0 if nb_or_s_top_2 <= 0 else _count_from_spacing(width_top, db_top_2, nb_or_s_top_2)

        # Row 1 center
        y_top_1 = cover_top + db_top_1 / 2.0
        # Row 2 center (rowgap is clear gap between bars)
        y_top_2 = y_top_1 + (db_top_1 / 2.0) + rowgap_top + (db_top_2 / 2.0)

        # flange vertical fit checks
        if n_top_2 > 0 and (y_top_2 + db_top_2 / 2.0 > tf + 1e-9):
            raise ValueError(
                f"Top flange too thin for 2 layers: tf={tf:.1f} mm, "
                f"needs cover_top + db1 + rowgap + db2 <= tf "
                f"({cover_top:.1f}+{db_top_1:.1f}+{rowgap_top:.1f}+{db_top_2:.1f} = "
                f"{(cover_top+db_top_1+rowgap_top+db_top_2):.1f})."
            )

        top: List[Dict] = []
        if n_top_1 > 0:
            # top flange outstands based on bw (web width for T)
            xs = _place_in_outstands(
                n=n_top_1,
                db=db_top_1,
                bf=bf,
                web_w=bw,
                cover_side=cover_side,
                min_clear_spacing=min_clear_spacing,
            )
            top.append({"x": xs, "y": [y_top_1]*len(xs), "db": db_top_1})

        if n_top_2 > 0:
            xs = _place_in_outstands(
                n=n_top_2,
                db=db_top_2,
                bf=bf,
                web_w=bw,
                cover_side=cover_side,
                min_clear_spacing=min_clear_spacing,
            )
            top.append({"x": xs, "y": [y_top_2]*len(xs), "db": db_top_2})

        # --- Bottom bars in WEB (T section) ---
        x_web0 = (bf - bw) / 2.0
        x_web1 = x_web0 + bw

        x0_b1 = x_web0 + cover_side + db_bot_1 / 2.0
        x1_b1 = x_web1 - cover_side - db_bot_1 / 2.0
        width_bot = x1_b1 - x0_b1
        if width_bot <= 0:
            raise ValueError("Bottom bars: no horizontal room after covers")

        if bot1_mode == "Count":
            n_bot_1 = int(nb_or_s_bot_1)
        else:
            n_bot_1 = 0 if nb_or_s_bot_1 <= 0 else _count_from_spacing(width_bot, db_bot_1, nb_or_s_bot_1)
        if bot2_mode == "Count":
            n_bot_2 = int(nb_or_s_bot_2)
        else:
            n_bot_2 = 0 if nb_or_s_bot_2 <= 0 else _count_from_spacing(width_bot, db_bot_2, nb_or_s_bot_2)

        y_bot_1 = D - cover_bot - db_bot_1 / 2.0
        y_bot_2 = y_bot_1 - (db_bot_1 / 2.0) - rowgap_bot - (db_bot_2 / 2.0)

        bottom: List[Dict] = []
        if n_bot_1 > 0:
            xs = _row_x_positions(x0_b1, x1_b1, n_bot_1)
            _check_row_clear(xs, db_bot_1, min_clear_spacing)
            bottom.append({"x": xs, "y": [y_bot_1]*len(xs), "db": db_bot_1})

        if n_bot_2 > 0:
            x0_b2 = x_web0 + cover_side + db_bot_2 / 2.0
            x1_b2 = x_web1 - cover_side - db_bot_2 / 2.0
            xs = _row_x_positions(x0_b2, x1_b2, n_bot_2)
            _check_row_clear(xs, db_bot_2, min_clear_spacing)
            bottom.append({"x": xs, "y": [y_bot_2]*len(xs), "db": db_bot_2})

        return _merge_reo_layers({"top": top, "bottom": bottom})

    if shape.startswith("I-Section"):
        bf = float(dims["bf"]); tf = float(dims["tf"]); tw = float(dims["tw"]); D = float(dims["D"])

        # --- Top bars in top flange width bf ---
        x0_t = cover_side + db_top_1 / 2.0
        x1_t = bf - cover_side - db_top_1 / 2.0
        width_top = x1_t - x0_t
        if width_top <= 0:
            raise ValueError("Top bars: no horizontal room after covers")

        if top1_mode == "Count":
            n_top_1 = int(nb_or_s_top_1)
        else:
            n_top_1 = 0 if nb_or_s_top_1 <= 0 else _count_from_spacing(width_top, db_top_1, nb_or_s_top_1)
        if top2_mode == "Count":
            n_top_2 = int(nb_or_s_top_2)
        else:
            n_top_2 = 0 if nb_or_s_top_2 <= 0 else _count_from_spacing(width_top, db_top_2, nb_or_s_top_2)

        y_top_1 = cover_top + db_top_1 / 2.0
        y_top_2 = y_top_1 + (db_top_1 / 2.0) + rowgap_top + (db_top_2 / 2.0)

        if n_top_2 > 0 and (y_top_2 + db_top_2 / 2.0 > tf + 1e-9):
            raise ValueError(
                f"Top flange too thin for 2 layers: tf={tf:.1f} mm, "
                f"needs cover_top + db1 + rowgap + db2 <= tf "
                f"({cover_top:.1f}+{db_top_1:.1f}+{rowgap_top:.1f}+{db_top_2:.1f} = "
                f"{(cover_top+db_top_1+rowgap_top+db_top_2):.1f})."
            )

        top: List[Dict] = []
        if n_top_1 > 0:
            xs = _place_in_outstands(
                n=n_top_1,
                db=db_top_1,
                bf=bf,
                web_w=tw,
                cover_side=cover_side,
                min_clear_spacing=min_clear_spacing,
            )
            top.append({"x": xs, "y": [y_top_1]*len(xs), "db": db_top_1})

        if n_top_2 > 0:
            xs = _place_in_outstands(
                n=n_top_2,
                db=db_top_2,
                bf=bf,
                web_w=tw,
                cover_side=cover_side,
                min_clear_spacing=min_clear_spacing,
            )
            top.append({"x": xs, "y": [y_top_2]*len(xs), "db": db_top_2})

        # --- Bottom bars in bottom flange width bf ---
        x0_b1 = cover_side + db_bot_1 / 2.0
        x1_b1 = bf - cover_side - db_bot_1 / 2.0
        width_bot = x1_b1 - x0_b1
        if width_bot <= 0:
            raise ValueError("Bottom bars: no horizontal room after covers")

        if bot1_mode == "Count":
            n_bot_1 = int(nb_or_s_bot_1)
        else:
            n_bot_1 = 0 if nb_or_s_bot_1 <= 0 else _count_from_spacing(width_bot, db_bot_1, nb_or_s_bot_1)
        if bot2_mode == "Count":
            n_bot_2 = int(nb_or_s_bot_2)
        else:
            n_bot_2 = 0 if nb_or_s_bot_2 <= 0 else _count_from_spacing(width_bot, db_bot_2, nb_or_s_bot_2)

        y_bot_1 = D - cover_bot - db_bot_1 / 2.0
        y_bot_2 = y_bot_1 - (db_bot_1 / 2.0) - rowgap_bot - (db_bot_2 / 2.0)

        if n_bot_2 > 0 and (y_bot_2 - db_bot_2 / 2.0 < (D - tf) - 1e-9):
            raise ValueError(
                f"Bottom flange too thin for 2 layers: tf={tf:.1f} mm, "
                f"needs cover_bot + db1 + rowgap + db2 <= tf "
                f"({cover_bot:.1f}+{db_bot_1:.1f}+{rowgap_bot:.1f}+{db_bot_2:.1f} = "
                f"{(cover_bot+db_bot_1+rowgap_bot+db_bot_2):.1f})."
            )

        bottom: List[Dict] = []
        if n_bot_1 > 0:
            xs = _place_in_outstands(
                n=n_bot_1,
                db=db_bot_1,
                bf=bf,
                web_w=tw,
                cover_side=cover_side,
                min_clear_spacing=min_clear_spacing,
            )
            bottom.append({"x": xs, "y": [y_bot_1]*len(xs), "db": db_bot_1})

        if n_bot_2 > 0:
            xs = _place_in_outstands(
                n=n_bot_2,
                db=db_bot_2,
                bf=bf,
                web_w=tw,
                cover_side=cover_side,
                min_clear_spacing=min_clear_spacing,
            )
            bottom.append({"x": xs, "y": [y_bot_2]*len(xs), "db": db_bot_2})

        return _merge_reo_layers({"top": top, "bottom": bottom})

    raise ValueError("Longitudinal reo layout currently supports only T-Section and I-Section.")


def flatten_reo_points(reo_layout: Dict[str, List[Dict]]) -> List[Dict]:
    pts: List[Dict] = []
    for layer_name in ("top", "bottom"):
        for band in reo_layout.get(layer_name, []):
            db = float(band["db"])
            for x, y in zip(band["x"], band["y"]):
                pts.append({"x": float(x), "y": float(y), "db": db, "layer": layer_name})
    return pts


def compute_longitudinal_reo_layout(
    *,
    shape_name: str,
    dims: Dict[str, float],
    cover_side: float,
    cover_top: float,
    cover_bot: float,
    min_clear_spacing: float,
    rowgap_top: float,
    rowgap_bot: float,
    reo: Dict[str, Any],
    max_rows: int = 2,
) -> Dict[str, List[Dict]]:
    shape_key = normalise_shape_name(shape_name)

    if shape_key in ("T", "I"):
        return compute_longitudinal_reo_layout_T_I(
            shape_name="T-Section" if shape_key == "T" else "I-Section",
            dims=dims,
            cover_side=cover_side,
            cover_top=cover_top,
            cover_bot=cover_bot,
            min_clear_spacing=min_clear_spacing,
            rowgap_top=rowgap_top,
            rowgap_bot=rowgap_bot,
            reo=reo,
            max_rows=max_rows,
        )
    if shape_key == "RECT":
        raise ValueError("Longitudinal reo layout currently supports only T-Section and I-Section.")

    raise ValueError(f"Unknown shape_name: {shape_name}")
