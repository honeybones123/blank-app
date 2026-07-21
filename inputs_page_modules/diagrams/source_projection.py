"""Inputs-page diagram source projection helpers."""

from __future__ import annotations


def build_section_outline_points_and_bbox(
    *,
    sec_shape: str,
    b: float = 400.0,
    D: float = 600.0,
    bf: float = 600.0,
    tf: float = 120.0,
    bw: float = 300.0,
    tw: float = 200.0,
) -> tuple[list[tuple[float, float]], float, float]:
    if sec_shape == "RECT":
        pts = [(0, 0), (b, 0), (b, D), (0, D), (0, 0)]
        return pts, b, D

    if sec_shape == "T":
        tf = max(1.0, min(tf, D))
        bw = max(1.0, min(bw, bf))

        x_web0 = 0.5 * (bf - bw)
        x_web1 = x_web0 + bw

        pts = [
            (0, 0),
            (bf, 0),
            (bf, tf),
            (x_web1, tf),
            (x_web1, D),
            (x_web0, D),
            (x_web0, tf),
            (0, tf),
            (0, 0),
        ]
        return pts, bf, D

    tf = max(1.0, min(tf, 0.5 * D))
    tw = max(1.0, min(tw, bf))

    x_web0 = 0.5 * (bf - tw)
    x_web1 = x_web0 + tw
    y_bot_flange_top = D - tf

    pts = [
        (0, 0),
        (bf, 0),
        (bf, tf),
        (x_web1, tf),
        (x_web1, y_bot_flange_top),
        (bf, y_bot_flange_top),
        (bf, D),
        (0, D),
        (0, y_bot_flange_top),
        (x_web0, y_bot_flange_top),
        (x_web0, tf),
        (0, tf),
        (0, 0),
    ]
    return pts, bf, D


__all__ = ["build_section_outline_points_and_bbox"]
