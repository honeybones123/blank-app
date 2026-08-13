"""Physical 2D ligature geometry shared by section diagram renderers.

All coordinates and thicknesses are expressed in section millimetres.  The
returned Plotly shapes therefore remain proportional to the concrete section
when the browser resizes the chart.
"""

from __future__ import annotations

import math
from typing import Any


def _polygon_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    return "M " + " L ".join(f"{x:.6g},{y:.6g}" for x, y in points) + " Z"


def _filled_polygon(points: list[tuple[float, float]], *, color: str) -> dict[str, Any]:
    return {
        "type": "path",
        "path": _polygon_path(points),
        "line": {"width": 0, "color": color},
        "fillcolor": color,
        "layer": "above",
    }


def _corner_band(
    *,
    cx: float,
    cy: float,
    outer_radius: float,
    thickness: float,
    angle_start: float,
    angle_end: float,
    color: str,
    segments: int = 10,
) -> dict[str, Any]:
    """Return one constant-thickness quarter-annulus as a filled polygon."""

    inner_radius = max(outer_radius - thickness, 0.0)
    angles = [
        angle_start + (angle_end - angle_start) * index / segments
        for index in range(segments + 1)
    ]
    outer = [
        (cx + outer_radius * math.cos(angle), cy + outer_radius * math.sin(angle))
        for angle in angles
    ]
    inner = [
        (cx + inner_radius * math.cos(angle), cy + inner_radius * math.sin(angle))
        for angle in reversed(angles)
    ]
    return _filled_polygon(outer + inner, color=color)


def build_rounded_ligature_shapes(
    *,
    outside_x0: float,
    outside_y0: float,
    outside_x1: float,
    outside_y1: float,
    diameter_mm: float,
    legs: int,
    color: str,
    bend_inner_radius_mm: float | None = None,
) -> list[dict[str, Any]]:
    """Build a closed, rounded ligature plus any intermediate vertical legs.

    ``outside_*`` describes the outside steel surface, so cover remains cover
    to the outside of the link.  The inside surface is exactly one link
    diameter inward.  The default bend is a stable drawing convention; it is
    not a substitute for a separate code bend-diameter verification.
    """

    diameter = float(diameter_mm or 0.0)
    leg_count = int(legs or 0)
    x0, x1 = sorted((float(outside_x0), float(outside_x1)))
    y0, y1 = sorted((float(outside_y0), float(outside_y1)))
    width = x1 - x0
    height = y1 - y0
    if diameter <= 0.0 or leg_count < 2 or width <= 2.0 * diameter or height <= 2.0 * diameter:
        return []

    # The diagram keeps the inside corner at the intersection of the two
    # straight inside faces.  This lets the extreme longitudinal bars remain
    # tangent to both faces while the outside steel edge is visibly rounded.
    # A verified bend radius can still be supplied explicitly by callers that
    # also provide a compatible longitudinal-bar arrangement.
    requested_inner = 0.0 if bend_inner_radius_mm is None else max(
        float(bend_inner_radius_mm), 0.0
    )
    max_outer = max(min(width, height) / 2.0, diameter)
    outer_radius = min(requested_inner + diameter, max_outer)
    outer_radius = max(outer_radius, diameter)

    cx_left = x0 + outer_radius
    cx_right = x1 - outer_radius
    cy_top = y0 + outer_radius
    cy_bottom = y1 - outer_radius

    shapes: list[dict[str, Any]] = []

    # Constant-thickness straight portions between the four rounded bends.
    if cx_right > cx_left:
        shapes.extend(
            [
                _filled_polygon(
                    [(cx_left, y0), (cx_right, y0), (cx_right, y0 + diameter), (cx_left, y0 + diameter)],
                    color=color,
                ),
                _filled_polygon(
                    [(cx_left, y1 - diameter), (cx_right, y1 - diameter), (cx_right, y1), (cx_left, y1)],
                    color=color,
                ),
            ]
        )
    if cy_bottom > cy_top:
        shapes.extend(
            [
                _filled_polygon(
                    [(x0, cy_top), (x0 + diameter, cy_top), (x0 + diameter, cy_bottom), (x0, cy_bottom)],
                    color=color,
                ),
                _filled_polygon(
                    [(x1 - diameter, cy_top), (x1, cy_top), (x1, cy_bottom), (x1 - diameter, cy_bottom)],
                    color=color,
                ),
            ]
        )

    shapes.extend(
        [
            _corner_band(cx=cx_left, cy=cy_top, outer_radius=outer_radius, thickness=diameter, angle_start=math.pi, angle_end=1.5 * math.pi, color=color),
            _corner_band(cx=cx_right, cy=cy_top, outer_radius=outer_radius, thickness=diameter, angle_start=1.5 * math.pi, angle_end=2.0 * math.pi, color=color),
            _corner_band(cx=cx_right, cy=cy_bottom, outer_radius=outer_radius, thickness=diameter, angle_start=0.0, angle_end=0.5 * math.pi, color=color),
            _corner_band(cx=cx_left, cy=cy_bottom, outer_radius=outer_radius, thickness=diameter, angle_start=0.5 * math.pi, angle_end=math.pi, color=color),
        ]
    )

    # Intermediate legs are real filled steel strips, not screen-pixel lines.
    if leg_count > 2:
        centre_x0 = x0 + diameter / 2.0
        centre_x1 = x1 - diameter / 2.0
        for index in range(1, leg_count - 1):
            centre_x = centre_x0 + (centre_x1 - centre_x0) * index / (leg_count - 1)
            shapes.append(
                _filled_polygon(
                    [
                        (centre_x - diameter / 2.0, y0 + diameter),
                        (centre_x + diameter / 2.0, y0 + diameter),
                        (centre_x + diameter / 2.0, y1 - diameter),
                        (centre_x - diameter / 2.0, y1 - diameter),
                    ],
                    color=color,
                )
            )

    return shapes
