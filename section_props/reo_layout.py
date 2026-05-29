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
    top += _as_list(layout.get("top_flange_left"))
    top += _as_list(layout.get("top_flange_right"))
    top += _as_list(layout.get("top_web"))
    top += _as_list(layout.get("top_left"))
    top += _as_list(layout.get("top_right"))

    bottom += _as_list(layout.get("bottom_flange"))
    bottom += _as_list(layout.get("bottom_flange_left"))
    bottom += _as_list(layout.get("bottom_flange_right"))
    bottom += _as_list(layout.get("bottom_web"))
    bottom += _as_list(layout.get("bottom_left"))
    bottom += _as_list(layout.get("bottom_right"))

    # write back guaranteed keys
    layout["top"] = top
    layout["bottom"] = bottom
    return layout


def _bars_per_row(total: int, rows: int) -> list[int]:
    total_i = max(0, int(total or 0))
    rows_i = max(1, int(rows or 1))
    base = total_i // rows_i
    rem = total_i % rows_i
    return [base + (1 if i < rem else 0) for i in range(rows_i)]


def _extract_group_rows(reo: Dict[str, Any], *, prefix: str) -> dict:
    return {
        "enabled": bool(reo.get(f"{prefix}_enabled", False)),
        "count": max(0, int(float(reo.get(f"{prefix}_count", 0) or 0))),
        "dia": float(reo.get(f"{prefix}_dia", 0.0) or 0.0),
        "rows": max(1, int(float(reo.get(f"{prefix}_rows", 1) or 1))),
        "row_spacing": float(reo.get(f"{prefix}_row_spacing", 60.0) or 60.0),
        "clear_spacing_mode": str(reo.get(f"{prefix}_clear_spacing_mode", "count") or "count"),
    }


def _safe_row_x_positions(
    n_bars,
    b,
    cover,
    db,
    s_min,
):
    x_left = cover + db / 2
    x_right = b - cover - db / 2

    if n_bars <= 0:
        return []

    if n_bars == 1:
        return [(x_left + x_right) / 2]

    available = x_right - x_left
    required = n_bars * db + (n_bars - 1) * s_min

    if required > available:
        raise ValueError(
            f"Reo does not fit: bars={n_bars}, required={required:.1f}, available={available:.1f}"
        )

    spacing = available / (n_bars - 1)
    return [x_left + i * spacing for i in range(n_bars)]


def _build_flange_group_bands(
    *,
    face: str,
    zone: str,
    x0: float,
    x1: float,
    y_start: float,
    y_step: float,
    count: int,
    dia: float,
    rows: int,
    min_clear_spacing: float,
    source_group: str,
    warnings: list[str],
) -> list[dict]:
    if count <= 0 or dia <= 0.0:
        return []
    bars_by_row = _bars_per_row(count, rows)
    bands: list[dict] = []
    for idx, row_count in enumerate(bars_by_row, start=1):
        if row_count <= 0:
            continue
        y = y_start + (idx - 1) * y_step
        usable_width = max(float(x1 - x0), 0.0)
        xs_local = _safe_row_x_positions(
            row_count,
            usable_width,
            0.0,
            dia,
            min_clear_spacing,
        )
        xs = [float(x0) + float(x) for x in xs_local]
        if len(xs) != row_count:
            raise ValueError(
                f"Bar layout mismatch: expected {row_count}, got {len(xs)}"
            )
        bands.append({
            "x": xs,
            "y": [y] * len(xs),
            "db": dia,
            "row_index": idx,
            "face": face,
            "zone": zone,
            "source_group": source_group,
            "anchored": True,
        })
    return bands


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
    from state_and_helpers import get_longitudinal_row_inputs

    def _row_model_rows(section_key: str) -> List[Dict[str, Any]]:
        rows = get_longitudinal_row_inputs(section_key, source=reo)
        out: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            mode = str(row.get("mode", "Count") or "Count")
            dia = float(row.get("dia", 0.0) or 0.0)
            bars = max(0, int(float(row.get("bars", row.get("count", 0)) or 0)))
            spacing = float(row.get("spacing", 0.0) or 0.0)
            nb_or_s = float(bars if mode == "Count" else spacing)
            active = bool(row.get("active", True)) and dia > 0.0 and (
                (mode == "Count" and bars > 0) or (mode == "Spacing" and spacing > 0.0)
            )
            if not active:
                continue
            out.append({
                "row_index": int(row.get("row_index", idx)),
                "mode": mode,
                "nb_or_s": nb_or_s,
                "bars": bars,
                "spacing": spacing,
                "dia": dia,
                "active": active,
            })
        return out[:max_rows]

    def _row_count(row: Dict[str, Any], width: float) -> int:
        dia = float(row.get("dia", 0.0) or 0.0)
        value = float(row.get("nb_or_s", row.get("spacing" if row.get("mode") == "Spacing" else "bars", 0.0)) or 0.0)
        if dia <= 0.0 or value <= 0.0 or width <= 0.0:
            return 0
        if str(row.get("mode", "Count")) == "Spacing":
            return _count_from_spacing(width, dia, value)
        return max(0, int(round(value)))

    rowgap_top = max(float(reo.get("rowgap_top", rowgap_top) or rowgap_top), min_clear_spacing)
    rowgap_bot = max(float(reo.get("rowgap_bot", rowgap_bot) or rowgap_bot), min_clear_spacing)
    top_rows = _row_model_rows("top")
    bottom_rows = _row_model_rows("bot")
    warnings: list[str] = []

    if shape.startswith("T-Section"):
        bf = float(dims["bf"]); tf = float(dims["tf"]); bw = float(dims["bw"]); D = float(dims["D"])
        x_web0 = (bf - bw) / 2.0
        x_web1 = x_web0 + bw

        top_web: List[Dict] = []
        prev_y = None
        prev_dia = None
        for row in top_rows:
            dia = float(row.get("dia", 0.0) or 0.0)
            y = cover_top + dia / 2.0 if prev_y is None else prev_y + prev_dia / 2.0 + rowgap_top + dia / 2.0
            if y + dia / 2.0 > tf + 1e-9:
                warnings.append(f"Top web row {int(row.get('row_index', 1))} does not fit within flange thickness; row ignored.")
                continue
            # Web longitudinal bars must remain inside the web band.
            x0_t = x_web0 + cover_side + dia / 2.0
            x1_t = x_web1 - cover_side - dia / 2.0
            width_top = x1_t - x0_t
            if width_top <= 0:
                warnings.append("Top web bars: no horizontal room after covers.")
                continue
            n_top = _row_count(row, width_top)
            xs_local = _safe_row_x_positions(n_top, width_top, 0.0, dia, min_clear_spacing)
            xs = [x0_t + x for x in xs_local]
            if len(xs) != n_top:
                raise ValueError(f"Bar layout mismatch: expected {n_top}, got {len(xs)}")
            top_web.append({
                "x": xs,
                "y": [y] * len(xs),
                "db": dia,
                "row_index": int(row.get("row_index", 1)),
                "face": "top",
                "zone": "web",
                "source_group": f"top_web_row_{int(row.get('row_index', 1))}",
                "anchored": True,
            })
            prev_y = y
            prev_dia = dia

        bottom_web: List[Dict] = []
        prev_y = None
        prev_dia = None
        for row in bottom_rows:
            dia = float(row.get("dia", 0.0) or 0.0)
            y = D - cover_bot - dia / 2.0 if prev_y is None else prev_y - prev_dia / 2.0 - rowgap_bot - dia / 2.0
            if y - dia / 2.0 < tf - 1e-9:
                warnings.append(f"Bottom web row {int(row.get('row_index', 1))} does not fit within available web depth; row ignored.")
                continue
            x0_b = x_web0 + cover_side + dia / 2.0
            x1_b = x_web1 - cover_side - dia / 2.0
            width_bot = x1_b - x0_b
            if width_bot <= 0:
                warnings.append("Bottom web bars: no horizontal room after covers.")
                continue
            n_bot = _row_count(row, width_bot)
            xs_local = _safe_row_x_positions(n_bot, width_bot, 0.0, dia, min_clear_spacing)
            xs = [x0_b + x for x in xs_local]
            if len(xs) != n_bot:
                raise ValueError(f"Bar layout mismatch: expected {n_bot}, got {len(xs)}")
            bottom_web.append({
                "x": xs,
                "y": [y] * len(xs),
                "db": dia,
                "row_index": int(row.get("row_index", 1)),
                "face": "bottom",
                "zone": "web",
                "source_group": f"bottom_web_row_{int(row.get('row_index', 1))}",
                "anchored": True,
            })
            prev_y = y
            prev_dia = dia

        xL_inner = (bf - bw) / 2.0
        xR_inner = xL_inner + bw
        top_flange_enabled = bool(reo.get("top_flange_reo_enabled", False))
        bot_flange_enabled = bool(reo.get("bot_flange_reo_enabled", False))
        top_mirror = bool(reo.get("top_flange_mirror_lr", True))
        bot_mirror = bool(reo.get("bot_flange_mirror_lr", True))

        top_left = _extract_group_rows(reo, prefix="top_flange_left")
        top_right = _extract_group_rows(reo, prefix="top_flange_right")
        if top_mirror:
            top_right = dict(top_left)
        bot_left = _extract_group_rows(reo, prefix="bot_flange_left")
        bot_right = _extract_group_rows(reo, prefix="bot_flange_right")
        if bot_mirror:
            bot_right = dict(bot_left)

        top_flange_left = []
        top_flange_right = []
        if top_flange_enabled:
            top_flange_left = _build_flange_group_bands(
                face="top",
                zone="flange_left",
                x0=cover_side + max(top_left["dia"], 0.0) / 2.0,
                x1=xL_inner - cover_side - max(top_left["dia"], 0.0) / 2.0,
                y_start=cover_top + max(top_left["dia"], 0.0) / 2.0,
                y_step=max(top_left["row_spacing"], top_left["dia"] + min_clear_spacing),
                count=top_left["count"],
                dia=top_left["dia"],
                rows=top_left["rows"],
                min_clear_spacing=min_clear_spacing,
                source_group="top_flange_left",
                warnings=warnings,
            )
            top_flange_right = _build_flange_group_bands(
                face="top",
                zone="flange_right",
                x0=xR_inner + cover_side + max(top_right["dia"], 0.0) / 2.0,
                x1=bf - cover_side - max(top_right["dia"], 0.0) / 2.0,
                y_start=cover_top + max(top_right["dia"], 0.0) / 2.0,
                y_step=max(top_right["row_spacing"], top_right["dia"] + min_clear_spacing),
                count=top_right["count"],
                dia=top_right["dia"],
                rows=top_right["rows"],
                min_clear_spacing=min_clear_spacing,
                source_group="top_flange_right",
                warnings=warnings,
            )

        bottom_flange_left: list[dict] = []
        bottom_flange_right: list[dict] = []
        if bot_flange_enabled:
            warnings.append("Bottom flange groups were enabled for a T-section; T-sections have no bottom flange, so these groups are ignored.")

        out = _merge_reo_layers({
            "top_web": top_web,
            "bottom_web": bottom_web,
            "top_flange_left": top_flange_left,
            "top_flange_right": top_flange_right,
            "bottom_flange_left": bottom_flange_left,
            "bottom_flange_right": bottom_flange_right,
        })
        out["warnings"] = warnings
        return out

    if shape.startswith("I-Section"):
        bf = float(dims["bf"]); tf = float(dims["tf"]); tw = float(dims["tw"]); D = float(dims["D"])

        top_web: List[Dict] = []
        prev_y = None
        prev_dia = None
        for row in top_rows:
            dia = float(row.get("dia", 0.0) or 0.0)
            y = cover_top + dia / 2.0 if prev_y is None else prev_y + prev_dia / 2.0 + rowgap_top + dia / 2.0
            if y + dia / 2.0 > tf + 1e-9:
                warnings.append(f"Top web row {int(row.get('row_index', 1))} does not fit within top flange; row ignored.")
                continue
            x0_t = ((bf - tw) / 2.0) + cover_side + dia / 2.0
            x1_t = ((bf + tw) / 2.0) - cover_side - dia / 2.0
            width_top = x1_t - x0_t
            if width_top <= 0:
                warnings.append("Top web bars: no horizontal room after covers.")
                continue
            n_top = _row_count(row, width_top)
            xs_local = _safe_row_x_positions(n_top, width_top, 0.0, dia, min_clear_spacing)
            xs = [x0_t + x for x in xs_local]
            if len(xs) != n_top:
                raise ValueError(f"Bar layout mismatch: expected {n_top}, got {len(xs)}")
            top_web.append({
                "x": xs,
                "y": [y] * len(xs),
                "db": dia,
                "row_index": int(row.get("row_index", 1)),
                "face": "top",
                "zone": "web",
                "source_group": f"top_web_row_{int(row.get('row_index', 1))}",
                "anchored": True,
            })
            prev_y = y
            prev_dia = dia

        bottom_web: List[Dict] = []
        prev_y = None
        prev_dia = None
        for row in bottom_rows:
            dia = float(row.get("dia", 0.0) or 0.0)
            y = D - cover_bot - dia / 2.0 if prev_y is None else prev_y - prev_dia / 2.0 - rowgap_bot - dia / 2.0
            if y - dia / 2.0 < (D - tf) - 1e-9:
                warnings.append(f"Bottom web row {int(row.get('row_index', 1))} does not fit within bottom flange; row ignored.")
                continue
            x0_b = ((bf - tw) / 2.0) + cover_side + dia / 2.0
            x1_b = ((bf + tw) / 2.0) - cover_side - dia / 2.0
            width_bot = x1_b - x0_b
            if width_bot <= 0:
                warnings.append("Bottom web bars: no horizontal room after covers.")
                continue
            n_bot = _row_count(row, width_bot)
            xs_local = _safe_row_x_positions(n_bot, width_bot, 0.0, dia, min_clear_spacing)
            xs = [x0_b + x for x in xs_local]
            if len(xs) != n_bot:
                raise ValueError(f"Bar layout mismatch: expected {n_bot}, got {len(xs)}")
            bottom_web.append({
                "x": xs,
                "y": [y] * len(xs),
                "db": dia,
                "row_index": int(row.get("row_index", 1)),
                "face": "bottom",
                "zone": "web",
                "source_group": f"bottom_web_row_{int(row.get('row_index', 1))}",
                "anchored": True,
            })
            prev_y = y
            prev_dia = dia

        xL_inner = (bf - tw) / 2.0
        xR_inner = xL_inner + tw
        top_flange_enabled = bool(reo.get("top_flange_reo_enabled", False))
        bot_flange_enabled = bool(reo.get("bot_flange_reo_enabled", False))
        top_mirror = bool(reo.get("top_flange_mirror_lr", True))
        bot_mirror = bool(reo.get("bot_flange_mirror_lr", True))

        top_left = _extract_group_rows(reo, prefix="top_flange_left")
        top_right = _extract_group_rows(reo, prefix="top_flange_right")
        if top_mirror:
            top_right = dict(top_left)
        bot_left = _extract_group_rows(reo, prefix="bot_flange_left")
        bot_right = _extract_group_rows(reo, prefix="bot_flange_right")
        if bot_mirror:
            bot_right = dict(bot_left)

        top_flange_left: list[dict] = []
        top_flange_right: list[dict] = []
        if top_flange_enabled:
            top_flange_left = _build_flange_group_bands(
                face="top",
                zone="flange_left",
                x0=cover_side + max(top_left["dia"], 0.0) / 2.0,
                x1=xL_inner - cover_side - max(top_left["dia"], 0.0) / 2.0,
                y_start=cover_top + max(top_left["dia"], 0.0) / 2.0,
                y_step=max(top_left["row_spacing"], top_left["dia"] + min_clear_spacing),
                count=top_left["count"],
                dia=top_left["dia"],
                rows=top_left["rows"],
                min_clear_spacing=min_clear_spacing,
                source_group="top_flange_left",
                warnings=warnings,
            )
            top_flange_right = _build_flange_group_bands(
                face="top",
                zone="flange_right",
                x0=xR_inner + cover_side + max(top_right["dia"], 0.0) / 2.0,
                x1=bf - cover_side - max(top_right["dia"], 0.0) / 2.0,
                y_start=cover_top + max(top_right["dia"], 0.0) / 2.0,
                y_step=max(top_right["row_spacing"], top_right["dia"] + min_clear_spacing),
                count=top_right["count"],
                dia=top_right["dia"],
                rows=top_right["rows"],
                min_clear_spacing=min_clear_spacing,
                source_group="top_flange_right",
                warnings=warnings,
            )

        bottom_flange_left: list[dict] = []
        bottom_flange_right: list[dict] = []
        if bot_flange_enabled:
            bottom_flange_left = _build_flange_group_bands(
                face="bottom",
                zone="flange_left",
                x0=cover_side + max(bot_left["dia"], 0.0) / 2.0,
                x1=xL_inner - cover_side - max(bot_left["dia"], 0.0) / 2.0,
                y_start=D - cover_bot - max(bot_left["dia"], 0.0) / 2.0,
                y_step=-max(bot_left["row_spacing"], bot_left["dia"] + min_clear_spacing),
                count=bot_left["count"],
                dia=bot_left["dia"],
                rows=bot_left["rows"],
                min_clear_spacing=min_clear_spacing,
                source_group="bottom_flange_left",
                warnings=warnings,
            )
            bottom_flange_right = _build_flange_group_bands(
                face="bottom",
                zone="flange_right",
                x0=xR_inner + cover_side + max(bot_right["dia"], 0.0) / 2.0,
                x1=bf - cover_side - max(bot_right["dia"], 0.0) / 2.0,
                y_start=D - cover_bot - max(bot_right["dia"], 0.0) / 2.0,
                y_step=-max(bot_right["row_spacing"], bot_right["dia"] + min_clear_spacing),
                count=bot_right["count"],
                dia=bot_right["dia"],
                rows=bot_right["rows"],
                min_clear_spacing=min_clear_spacing,
                source_group="bottom_flange_right",
                warnings=warnings,
            )

        out = _merge_reo_layers({
            "top_web": top_web,
            "bottom_web": bottom_web,
            "top_flange_left": top_flange_left,
            "top_flange_right": top_flange_right,
            "bottom_flange_left": bottom_flange_left,
            "bottom_flange_right": bottom_flange_right,
        })
        out["warnings"] = warnings
        return out

    raise ValueError("Longitudinal reo layout currently supports only T-Section and I-Section.")


def flatten_reo_points(reo_layout: Dict[str, List[Dict]]) -> List[Dict]:
    pts: List[Dict] = []
    for layer_name in ("top", "bottom"):
        for band in reo_layout.get(layer_name, []):
            db = float(band["db"])
            for x, y in zip(band["x"], band["y"]):
                pts.append({"x": float(x), "y": float(y), "db": db, "layer": layer_name})
    return pts


def resolve_longitudinal_bars_from_layout(
    *,
    shape_name: str,
    dims: Dict[str, float],
    reo_layout: Dict[str, List[Dict]],
) -> List[Dict[str, Any]]:
    bars: List[Dict[str, Any]] = []
    shape_key = normalise_shape_name(shape_name)
    detailed_layer_keys = (
        "top_web",
        "bottom_web",
        "top_flange_left",
        "top_flange_right",
        "bottom_flange_left",
        "bottom_flange_right",
    )
    has_detailed = any(reo_layout.get(key) for key in detailed_layer_keys)
    if shape_key in ("T", "I") and has_detailed:
        # Canonical T/I path: consume detailed groups only to avoid double-counting.
        layer_keys = detailed_layer_keys
    else:
        # RECT / legacy fallback
        layer_keys = (
            "top",
            "bottom",
            "top_web",
            "bottom_web",
            "top_flange",
            "bottom_flange",
            "top_flange_left",
            "top_flange_right",
            "bottom_flange_left",
            "bottom_flange_right",
        )
    seen_physical: set[tuple[Any, ...]] = set()
    bar_idx = 1
    for layer_name in layer_keys:
        for band in (reo_layout.get(layer_name) or []):
            xs = [float(x) for x in (band.get("x") or [])]
            ys = band.get("y") or []
            if isinstance(ys, (int, float)):
                ys = [float(ys)] * len(xs)
            dia = float(band.get("db", 0.0) or 0.0)
            if dia <= 0.0:
                continue
            face = str(band.get("face") or ("top" if "top" in layer_name else "bottom"))
            zone = str(
                band.get("zone")
                or (
                    "web"
                    if "web" in layer_name
                    else ("flange_left" if "left" in layer_name else ("flange_right" if "right" in layer_name else "web"))
                )
            )
            source_group = str(band.get("source_group") or layer_name)
            anchored = bool(band.get("anchored", True))
            for x, y in zip(xs, ys):
                key = (
                    face,
                    zone,
                    round(float(x), 6),
                    round(float(y), 6),
                    round(float(dia), 6),
                    source_group,
                )
                if key in seen_physical:
                    continue
                seen_physical.add(key)
                bars.append({
                    "id": f"bar_{bar_idx}",
                    "face": face,
                    "zone": zone,
                    "x_mm": float(x),
                    "y_mm": float(y),
                    "dia_mm": dia,
                    "area_mm2": math.pi * dia ** 2 / 4.0,
                    "anchored": anchored,
                    "source_group": source_group,
                })
                bar_idx += 1
    assert len(bars) > 0, "No bars resolved"
    return bars


def point_in_concrete_mm(
    x_mm: float,
    y_mm: float,
    *,
    shape_key: str,
    dims: Dict[str, float],
) -> bool:
    """
    True if (x_mm, y_mm) lies in cast concrete for T or I (section coords:
    x = width 0..bf, y = depth from top 0..D). Used for dev checks on resolved bars.
    """
    x = float(x_mm)
    y = float(y_mm)
    if shape_key == "T":
        bf = float(dims.get("bf", 0.0) or 0.0)
        tf = float(dims.get("tf", 0.0) or 0.0)
        bw = float(dims.get("bw", 0.0) or 0.0)
        D = float(dims.get("D", 0.0) or 0.0)
        if bf <= 0.0 or D <= 0.0:
            return False
        x0w = (bf - bw) / 2.0
        x1w = x0w + bw
        if x < -1e-6 or x > bf + 1e-6 or y < -1e-6 or y > D + 1e-6:
            return False
        if y <= tf + 1e-9:
            return True
        return x0w - 1e-9 <= x <= x1w + 1e-9
    if shape_key == "I":
        bf = float(dims.get("bf", 0.0) or 0.0)
        tf = float(dims.get("tf", 0.0) or 0.0)
        tw = float(dims.get("tw", 0.0) or 0.0)
        D = float(dims.get("D", 0.0) or 0.0)
        if bf <= 0.0 or D <= 0.0:
            return False
        x0w = (bf - tw) / 2.0
        x1w = x0w + tw
        if x < -1e-6 or x > bf + 1e-6 or y < -1e-6 or y > D + 1e-6:
            return False
        if y <= tf + 1e-9:
            return True
        if y >= D - tf - 1e-9:
            return True
        return x0w - 1e-9 <= x <= x1w + 1e-9
    b = float(dims.get("b", dims.get("bf", 0.0)) or 0.0)
    D = float(dims.get("D", 0.0) or 0.0)
    return -1e-6 <= x <= b + 1e-6 and -1e-6 <= y <= D + 1e-6


def dev_warnings_bars_outside_concrete(
    bars: List[Dict[str, Any]],
    shape_name: str,
    dims: Dict[str, float],
) -> List[str]:
    """Emit one warning string per resolved bar whose center lies outside concrete (void)."""
    key = normalise_shape_name(shape_name)
    if key not in ("T", "I"):
        return []
    msgs: List[str] = []
    for bar in bars:
        x = float(bar.get("x_mm", 0.0) or 0.0)
        y = float(bar.get("y_mm", 0.0) or 0.0)
        if not point_in_concrete_mm(x, y, shape_key=key, dims=dims):
            bid = str(bar.get("id", ""))
            msgs.append(
                f"Reo 3D/dev: bar {bid} center ({x:.1f}, {y:.1f}) mm is outside concrete (void) "
                f"for {shape_name}."
            )
    return msgs


def resolve_active_tension_reinforcement(
    section_geom: Dict[str, Any],
    resolved_longitudinal_bars: List[Dict[str, Any]],
    moment_sign: str,
    neutral_axis_data: Dict[str, Any] | None = None,
) -> dict:
    sign = str(moment_sign or "positive").strip().lower()
    tension_face = "top" if (sign.startswith("neg") or "hog" in sign) else "bottom"
    active_bars = [bar for bar in resolved_longitudinal_bars if str(bar.get("face")) == tension_face]
    active_web_bars = [bar for bar in active_bars if "web" in str(bar.get("zone", ""))]
    active_flange_bars = [bar for bar in active_bars if "flange" in str(bar.get("zone", ""))]

    if active_bars:
        x_min = min(float(bar["x_mm"]) - float(bar["dia_mm"]) / 2.0 for bar in active_bars)
        x_max = max(float(bar["x_mm"]) + float(bar["dia_mm"]) / 2.0 for bar in active_bars)
        y_min = min(float(bar["y_mm"]) - float(bar["dia_mm"]) / 2.0 for bar in active_bars)
        y_max = max(float(bar["y_mm"]) + float(bar["dia_mm"]) / 2.0 for bar in active_bars)
    else:
        x_min = x_max = y_min = y_max = 0.0

    x_sorted = sorted(float(bar["x_mm"]) for bar in active_bars)
    spacing = [x_sorted[i + 1] - x_sorted[i] for i in range(len(x_sorted) - 1)]
    spacing_summary = {
        "count": len(spacing),
        "min_mm": min(spacing) if spacing else 0.0,
        "max_mm": max(spacing) if spacing else 0.0,
        "avg_mm": (sum(spacing) / len(spacing)) if spacing else 0.0,
        "values_mm": spacing,
    }
    ast_active = sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in active_bars)
    neutral_axis_data = neutral_axis_data or {}
    return {
        "tension_face": tension_face,
        "active_bars": active_bars,
        "active_web_bars": active_web_bars,
        "active_flange_bars": active_flange_bars,
        "tension_zone_width_mm": max(0.0, x_max - x_min),
        "tension_zone_bounds": {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max},
        "Ast_active_mm2": ast_active,
        "bar_spacing_summary": spacing_summary,
        "outermost_active_bar_positions": {"left_x_mm": x_min, "right_x_mm": x_max},
        "neutral_axis_data": neutral_axis_data,
    }


def resolve_crack_tension_width(
    section_shape: str,
    section_geom: Dict[str, Any],
    moment_sign: str,
    active_bars: List[Dict[str, Any]],
) -> dict:
    shape = normalise_shape_name(section_shape)
    sign = str(moment_sign or "positive").strip().lower()
    top_tension = sign.startswith("neg") or "hog" in sign
    has_flange = any("flange" in str(bar.get("zone", "")) for bar in active_bars)
    has_web = any("web" in str(bar.get("zone", "")) for bar in active_bars)

    if shape == "RECT":
        width_default = float(section_geom.get("b", 0.0) or section_geom.get("bf", 0.0) or 0.0)
    elif shape == "T":
        if top_tension:
            width_default = float(section_geom.get("bf", 0.0) or section_geom.get("b", 0.0) or 0.0)
        else:
            width_default = float(section_geom.get("bw", section_geom.get("b_web", section_geom.get("b", 0.0))) or 0.0)
    else:
        width_default = float(section_geom.get("bf", section_geom.get("b", 0.0)) or 0.0)

    if not active_bars:
        return {
            "crack_tension_width_mm": width_default,
            "crack_flange_participation_used": False,
            "crack_web_participation_used": False,
            "crack_tension_zone_bounds": {"x_min": 0.0, "x_max": width_default},
        }

    x_min = min(float(bar["x_mm"]) - float(bar["dia_mm"]) / 2.0 for bar in active_bars)
    x_max = max(float(bar["x_mm"]) + float(bar["dia_mm"]) / 2.0 for bar in active_bars)
    spread = max(0.0, x_max - x_min)

    if shape == "T" and not top_tension:
        width_eff = min(width_default, spread if spread > 0.0 else width_default)
    elif shape == "T" and top_tension:
        bw = float(section_geom.get("bw", section_geom.get("b_web", 0.0)) or 0.0)
        if has_flange:
            width_eff = min(width_default, max(bw, spread))
        else:
            width_eff = bw if bw > 0.0 else min(width_default, spread if spread > 0.0 else width_default)
    elif shape == "I":
        tw = float(section_geom.get("tw", section_geom.get("b_web", 0.0)) or 0.0)
        if has_flange:
            width_eff = min(width_default, max(tw, spread))
        else:
            width_eff = tw if tw > 0.0 else min(width_default, spread if spread > 0.0 else width_default)
    else:
        width_eff = min(width_default, spread if spread > 0.0 else width_default)

    return {
        "crack_tension_width_mm": max(0.0, width_eff),
        "crack_flange_participation_used": bool(has_flange),
        "crack_web_participation_used": bool(has_web),
        "crack_tension_zone_bounds": {"x_min": x_min, "x_max": x_max},
    }


def analyze_resolved_longitudinal_bars(
    *,
    shape_name: str,
    dims: Dict[str, float],
    bars: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Developer diagnostics for resolved longitudinal bars."""
    shape_key = normalise_shape_name(shape_name)
    warnings: list[str] = []
    duplicates: list[str] = []
    out_of_bounds: list[str] = []
    zone_mismatch: list[str] = []

    # section envelope
    if shape_key in ("T", "I"):
        W = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
    else:
        W = float(dims.get("b", dims.get("bf", 0.0)) or 0.0)
    D = float(dims.get("D", 0.0) or 0.0)

    # zone bands (for T/I)
    x_web0 = x_web1 = None
    if shape_key == "T":
        bf = float(dims.get("bf", 0.0) or 0.0)
        bw = float(dims.get("bw", 0.0) or 0.0)
        x_web0 = (bf - bw) / 2.0
        x_web1 = x_web0 + bw
    elif shape_key == "I":
        bf = float(dims.get("bf", 0.0) or 0.0)
        tw = float(dims.get("tw", 0.0) or 0.0)
        x_web0 = (bf - tw) / 2.0
        x_web1 = x_web0 + tw

    seen: set[tuple[Any, ...]] = set()
    for bar in bars:
        bar_id = str(bar.get("id", ""))
        x = float(bar.get("x_mm", 0.0) or 0.0)
        y = float(bar.get("y_mm", 0.0) or 0.0)
        d = float(bar.get("dia_mm", 0.0) or 0.0)
        zone = str(bar.get("zone", ""))
        src = str(bar.get("source_group", ""))
        face = str(bar.get("face", ""))
        dup_key = (face, zone, round(x, 6), round(y, 6), round(d, 6), src)
        if dup_key in seen:
            duplicates.append(bar_id)
        seen.add(dup_key)

        # out-of-bounds envelope check
        if x - d / 2.0 < -1e-6 or x + d / 2.0 > W + 1e-6 or y - d / 2.0 < -1e-6 or y + d / 2.0 > D + 1e-6:
            out_of_bounds.append(bar_id)

        # zone-band sanity for T/I
        if x_web0 is not None and x_web1 is not None:
            if zone == "web" and not (x_web0 - 1e-6 <= x <= x_web1 + 1e-6):
                zone_mismatch.append(bar_id)
            if zone == "flange_left" and not (x < x_web0 - 1e-6):
                zone_mismatch.append(bar_id)
            if zone == "flange_right" and not (x > x_web1 + 1e-6):
                zone_mismatch.append(bar_id)

    if duplicates:
        warnings.append(f"Duplicate resolved longitudinal bars detected: {len(duplicates)}")
    if out_of_bounds:
        warnings.append(f"Resolved longitudinal bars outside section bounds: {len(out_of_bounds)}")
    if zone_mismatch:
        warnings.append(f"Resolved longitudinal bars with zone/placement mismatch: {len(zone_mismatch)}")

    return {
        "warnings": warnings,
        "duplicates": duplicates,
        "out_of_bounds": out_of_bounds,
        "zone_mismatch": zone_mismatch,
    }


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
