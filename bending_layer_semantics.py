"""
Single source of truth for sagging vs hogging tension/compression layer semantics.

All bending diagrams and any helper that needs “which face is tension” should use
`resolve_bending_faces` + `resolve_bending_layer_geometry` rather than inferring
from bar position or hardcoding bottom steel as tension.
"""

from __future__ import annotations

from typing import Any


def resolve_bending_faces(moment_sign: str) -> tuple[str, str, bool]:
    """
    From the active bending case (display / demand sign).

    Returns:
        tension_face: "bottom" | "top"
        compression_face: "top" | "bottom"
        is_hogging: True if moment_sign is negative (hogging)
    """
    sign = str(moment_sign or "positive").strip().lower()
    is_hogging = sign == "negative"
    if is_hogging:
        return "top", "bottom", True
    return "bottom", "top", False


def _collect_reo_layout_rows(reo_layout: dict, side: str) -> list[dict]:
    if not reo_layout:
        return []
    keys = (
        ["top", "top_flange", "top_web", "top_left", "top_right"]
        if side == "top"
        else ["bottom", "bottom_flange", "bottom_web", "bottom_left", "bottom_right"]
    )
    out: list[dict] = []
    for k in keys:
        v = reo_layout.get(k)
        if not v:
            continue
        out += v if isinstance(v, list) else [v]
    return out


def resolve_bending_layer_geometry(
    layout: dict[str, Any] | None,
    *,
    moment_sign: str,
    D: float,
    fallback_y_tension: float,
) -> dict[str, Any]:
    """
    Resolve centroids, d / d', and extreme compression fibre from section layout.

    fallback_y_tension: y of tension steel from top (mm) when layout has no bars,
        typically from _stress_strain_state / effective-depth helpers.
    """
    tension_face, compression_face, is_hogging = resolve_bending_faces(moment_sign)
    Df = float(D or 0.0)
    y_comp_extreme = 0.0 if tension_face == "bottom" else Df
    y_tension = float(fallback_y_tension)
    y_compression_steel: float | None = None

    tension_layer_coords: list[dict[str, Any]] = []
    compression_layer_coords: list[dict[str, Any]] = []

    if not layout:
        d_mm = y_tension if tension_face == "bottom" else max(0.0, Df - y_tension)
        return {
            "tension_face": tension_face,
            "compression_face": compression_face,
            "is_hogging": is_hogging,
            "plot_neg": is_hogging,
            "y_comp_extreme": y_comp_extreme,
            "compression_block_face": "top" if tension_face == "bottom" else "bottom",
            "y_tension_centroid": y_tension,
            "y_compression_steel_centroid": y_compression_steel,
            "d_value": d_mm,
            "d_prime_value": None,
            "tension_layer_coords": tension_layer_coords,
            "compression_layer_coords": compression_layer_coords,
        }

    pts = layout.get("reo_points") or []
    if pts:
        for p in pts:
            layer = p.get("layer")
            if layer == tension_face:
                tension_layer_coords.append(dict(p))
            elif layer == compression_face:
                compression_layer_coords.append(dict(p))
        b_ys = [float(p["y"]) for p in pts if p.get("layer") == "bottom"]
        t_ys = [float(p["y"]) for p in pts if p.get("layer") == "top"]
        if tension_face == "bottom":
            if b_ys:
                y_tension = max(b_ys)
            if t_ys:
                y_compression_steel = sum(t_ys) / len(t_ys)
        else:
            if t_ys:
                y_tension = min(t_ys)
            if b_ys:
                y_compression_steel = sum(b_ys) / len(b_ys)
    else:
        rlay = layout.get("reo_layout")
        if rlay and isinstance(rlay, dict):
            b_ys = []
            for layer_data in _collect_reo_layout_rows(rlay, "bottom"):
                try:
                    b_ys.append(float(layer_data["y"]))
                except Exception:
                    pass
            t_ys = []
            for layer_data in _collect_reo_layout_rows(rlay, "top"):
                try:
                    t_ys.append(float(layer_data["y"]))
                except Exception:
                    pass
            if tension_face == "bottom":
                if b_ys:
                    y_tension = max(b_ys)
                if t_ys:
                    y_compression_steel = sum(t_ys) / len(t_ys)
            else:
                if t_ys:
                    y_tension = min(t_ys)
                if b_ys:
                    y_compression_steel = sum(b_ys) / len(b_ys)

    d_mm = y_tension if tension_face == "bottom" else max(0.0, Df - y_tension)
    d_prime_mm: float | None = None
    if y_compression_steel is not None:
        if tension_face == "bottom":
            d_prime_mm = max(0.0, float(y_compression_steel))
        else:
            d_prime_mm = max(0.0, Df - float(y_compression_steel))

    return {
        "tension_face": tension_face,
        "compression_face": compression_face,
        "is_hogging": is_hogging,
        "plot_neg": is_hogging,
        "y_comp_extreme": y_comp_extreme,
        "compression_block_face": "top" if tension_face == "bottom" else "bottom",
        "y_tension_centroid": y_tension,
        "y_compression_steel_centroid": y_compression_steel,
        "d_value": d_mm,
        "d_prime_value": d_prime_mm,
        "tension_layer_coords": tension_layer_coords,
        "compression_layer_coords": compression_layer_coords,
    }
