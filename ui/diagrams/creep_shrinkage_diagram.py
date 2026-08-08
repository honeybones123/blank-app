"""Creep and shrinkage teaching schematic figure builders."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import plotly.graph_objects as go

from inputs_page_modules.diagrams.source_projection import (
    build_section_outline_points_and_bbox,
)
from section_props.shape_utils import normalise_shape_name
from ui.diagrams.diagram_models import SectionDiagramResult
from ui.diagrams.diagram_styles import (
    ANNOTATION_BG,
    ANNOTATION_TEXT,
    CONCRETE_OUTLINE,
    DIAGRAM_BG,
    LINK_STEEL,
)
from ui.diagrams.section_diagram import build_summary_cross_section_result
from ui.diagrams.side_view_diagram import (
    build_standard_reinforced_beam_side_view,
    fit_side_view_figure_to_content,
    side_view_display_length_from_model,
    side_view_display_state,
)


_SHRINKAGE_EVAPORATION_BLUE = "#1f77b4"
_SHRINKAGE_MOISTURE_BLUE = "rgba(31,119,180,0.34)"
_SHRINKAGE_NAVY = "#1e293b"
_SHRINKAGE_SURFACE_BAND = "rgba(71,85,105,0.34)"
_SHRINKAGE_ORIGINAL_OUTLINE = "rgba(100,116,139,0.62)"


BaseSectionBuilder = Callable[..., SectionDiagramResult]
SideViewBuilder = Callable[..., go.Figure]


def _outline_for_layout(
    layout: dict[str, Any],
) -> tuple[list[tuple[float, float]], float, float]:
    """Use the same canonical outline projection as the shared beam diagrams."""
    shape_name = str(layout.get("shape_name") or "Rectangle (b x D)")
    dims = dict(layout.get("dims") or {})
    shape_key = normalise_shape_name(shape_name)
    return build_section_outline_points_and_bbox(
        sec_shape=shape_key,
        b=float(dims.get("b", layout.get("b", 400.0)) or 400.0),
        D=float(dims.get("D", layout.get("D", 600.0)) or 600.0),
        bf=float(dims.get("bf", dims.get("b", 600.0)) or 600.0),
        tf=float(dims.get("tf", 120.0) or 120.0),
        bw=float(dims.get("bw", 300.0) or 300.0),
        tw=float(dims.get("tw", 200.0) or 200.0),
    )


def _path_from_points(
    points: list[tuple[float, float]], *, close: bool = True
) -> str:
    if not points:
        return ""
    commands = [f"M {points[0][0]:.5f},{points[0][1]:.5f}"]
    commands.extend(f"L {x:.5f},{y:.5f}" for x, y in points[1:])
    if close and points[-1] != points[0]:
        commands.append("Z")
    return " ".join(commands)


def _point_in_polygon(
    x: float,
    y: float,
    points: list[tuple[float, float]],
) -> bool:
    inside = False
    polygon = points[:-1] if len(points) > 1 and points[0] == points[-1] else points
    if len(polygon) < 3:
        return False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        crosses = (yi > y) != (yj > y)
        if crosses:
            x_intersection = (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
            if x < x_intersection:
                inside = not inside
        j = i
    return inside


def _horizontal_section_bounds(
    points: list[tuple[float, float]],
    y: float,
    fallback_width: float,
) -> tuple[float, float]:
    intersections: list[float] = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if abs(y1 - y0) <= 1e-9:
            continue
        if min(y0, y1) <= y <= max(y0, y1):
            t = (y - y0) / (y1 - y0)
            intersections.append(x0 + t * (x1 - x0))
    if len(intersections) < 2:
        return 0.0, float(fallback_width)
    return min(intersections), max(intersections)


def _exposed_edge_kind(faces_option: str) -> str:
    label = str(faces_option or "").strip().lower()
    if "one face" in label:
        return "top"
    if "two face" in label:
        return "top_bottom"
    if "four face" in label or "column" in label:
        return "all"
    return "top_sides"


def _add_leader_label(
    fig: go.Figure,
    *,
    target_x: float,
    target_y: float,
    label_x: float,
    label_y: float,
    text: str,
) -> None:
    fig.add_annotation(
        x=target_x,
        y=target_y,
        ax=label_x,
        ay=label_y,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text=text,
        showarrow=True,
        arrowhead=0,
        arrowwidth=1.0,
        arrowcolor=_SHRINKAGE_NAVY,
        font=dict(size=11, color=ANNOTATION_TEXT),
        bgcolor=ANNOTATION_BG,
        borderpad=3,
        align="left",
    )


def build_shrinkage_cross_section_result(
    *,
    layout: dict[str, Any],
    faces_option: str = "Beam - three faces exposed",
    height_px: int = 650,
    base_section_builder: BaseSectionBuilder | None = None,
) -> SectionDiagramResult:
    """Overlay drying-shrinkage teaching cues on the shared section figure.

    The concrete geometry, reinforcement, links, colours, line weights and
    responsive Plotly behaviour all originate from the standard section
    builder. This function owns only the shrinkage-specific teaching overlay.
    """
    builder = base_section_builder or build_summary_cross_section_result
    reo = dict(layout.get("reo") or {})
    base_result = builder(
        layout=layout,
        fallback_cover_side=float(reo.get("cover_side", 40.0) or 40.0),
        fallback_cover_top=float(reo.get("cover_top", 40.0) or 40.0),
        fallback_cover_bot=float(reo.get("cover_bot", 40.0) or 40.0),
    )
    if base_result.figure is None:
        return base_result

    fig = base_result.figure
    points, width, depth = _outline_for_layout(layout)
    width = max(float(width), 1.0)
    depth = max(float(depth), 1.0)
    centre_x = 0.5 * width
    frame = max(width, 0.72 * depth)
    exposed_kind = _exposed_edge_kind(faces_option)

    # Pale-blue moisture particles, deterministically distributed inside the
    # actual shared section outline so visual snapshots remain stable.
    rng = np.random.default_rng(3600)
    moisture_x: list[float] = []
    moisture_y: list[float] = []
    for row in range(10):
        for col in range(10):
            x = width * (0.07 + 0.86 * (col + 0.5) / 10.0)
            y = depth * (0.07 + 0.86 * (row + 0.5) / 10.0)
            x += float(rng.uniform(-0.012, 0.012)) * width
            y += float(rng.uniform(-0.012, 0.012)) * depth
            if _point_in_polygon(x, y, points):
                moisture_x.append(x)
                moisture_y.append(y)
    fig.add_trace(
        go.Scatter(
            x=moisture_x,
            y=moisture_y,
            mode="markers",
            marker=dict(size=5, color=_SHRINKAGE_MOISTURE_BLUE),
            hovertemplate="Moisture in concrete<extra></extra>",
            name="Moisture",
            showlegend=False,
        )
    )

    # Exposed-face surface band. The edge selection follows the current member
    # exposure choice while retaining the canonical outline coordinates.
    tolerance = 1e-7 * max(width, depth)
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        is_top = abs(y0) <= tolerance and abs(y1) <= tolerance
        is_bottom = abs(y0 - depth) <= tolerance and abs(y1 - depth) <= tolerance
        is_vertical = abs(x1 - x0) <= tolerance
        include = is_top
        if exposed_kind == "top_bottom":
            include = is_top or is_bottom
        elif exposed_kind == "top_sides":
            include = is_top or is_vertical
        elif exposed_kind == "all":
            include = True
        if include:
            fig.add_shape(
                type="line",
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                line=dict(color=_SHRINKAGE_SURFACE_BAND, width=7),
                layer="above",
            )

    # Original perimeter and exaggerated contracted perimeter.
    fig.add_shape(
        type="path",
        path=_path_from_points(points),
        line=dict(color=_SHRINKAGE_ORIGINAL_OUTLINE, width=1.5, dash="dash"),
        fillcolor="rgba(0,0,0,0)",
        layer="above",
    )
    contraction_scale = 0.965
    contracted = [
        (
            centre_x + (x - centre_x) * contraction_scale,
            0.5 * depth + (y - 0.5 * depth) * contraction_scale,
        )
        for x, y in points
    ]
    fig.add_shape(
        type="path",
        path=_path_from_points(contracted),
        line=dict(color=CONCRETE_OUTLINE, width=2.0),
        fillcolor="rgba(0,0,0,0)",
        layer="above",
    )

    # Fine, shallow cracks: secondary to the section and reinforcement.
    for fraction, lean in ((0.27, -0.010), (0.50, 0.012), (0.73, -0.008)):
        x0 = width * fraction
        crack_points = [
            (x0, 0.0),
            (x0 + lean * width, 0.025 * depth),
            (x0 - 0.006 * width, 0.050 * depth),
            (x0 + 0.004 * width, 0.070 * depth),
        ]
        fig.add_shape(
            type="path",
            path=_path_from_points(crack_points, close=False),
            line=dict(color="rgba(30,41,59,0.72)", width=1.15),
            fillcolor="rgba(0,0,0,0)",
            layer="above",
        )

    # Moisture arrows leave the exposed top and, where applicable, side faces.
    def _outward_arrow(x: float, y: float, ax: float, ay: float) -> None:
        fig.add_annotation(
            x=x,
            y=y,
            ax=ax,
            ay=ay,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=0.85,
            arrowwidth=1.7,
            arrowcolor=_SHRINKAGE_EVAPORATION_BLUE,
        )

    for fraction in (0.25, 0.50, 0.75):
        _outward_arrow(width * fraction, -0.17 * depth, width * fraction, 0.01 * depth)
    side_y = 0.42 * depth
    side_left, side_right = _horizontal_section_bounds(points, side_y, width)
    if exposed_kind in {"top_sides", "all"}:
        _outward_arrow(side_left - 0.14 * frame, side_y, side_left + 0.01 * frame, side_y)
        _outward_arrow(side_right + 0.14 * frame, side_y, side_right - 0.01 * frame, side_y)
    if exposed_kind in {"top_bottom", "all"}:
        _outward_arrow(0.68 * width, 1.15 * depth, 0.68 * width, 0.99 * depth)

    fig.add_annotation(
        x=centre_x + 0.52 * frame,
        y=-0.25 * depth,
        text="<b>Moisture loss</b>",
        showarrow=False,
        font=dict(size=12, color=_SHRINKAGE_EVAPORATION_BLUE),
        bgcolor=ANNOTATION_BG,
        borderpad=3,
    )

    # Inward contraction arrows on all four sides.
    contraction_y = 0.60 * depth
    contract_left, contract_right = _horizontal_section_bounds(points, contraction_y, width)
    for x, y, ax, ay in (
        (contract_left + 0.08 * frame, contraction_y, contract_left - 0.04 * frame, contraction_y),
        (contract_right - 0.08 * frame, contraction_y, contract_right + 0.04 * frame, contraction_y),
        (centre_x, 0.08 * depth, centre_x, -0.04 * depth),
        (centre_x, 0.92 * depth, centre_x, 1.04 * depth),
    ):
        fig.add_annotation(
            x=x,
            y=y,
            ax=ax,
            ay=ay,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.75,
            arrowwidth=1.25,
            arrowcolor=_SHRINKAGE_NAVY,
        )

    _add_leader_label(
        fig,
        target_x=0.08 * width,
        target_y=0.0,
        label_x=centre_x - 0.88 * frame,
        label_y=-0.12 * depth,
        text="Surface dries first",
    )
    _add_leader_label(
        fig,
        target_x=0.27 * width,
        target_y=0.045 * depth,
        label_x=centre_x - 0.90 * frame,
        label_y=0.24 * depth,
        text="Shrinkage cracking",
    )
    _add_leader_label(
        fig,
        target_x=contract_right - 0.04 * frame,
        target_y=contraction_y,
        label_x=centre_x + 0.90 * frame,
        label_y=0.76 * depth,
        text="Concrete contracts as it dries",
    )

    # Longitudinal shortening indicator beneath the cross-section.
    original_x0, original_x1 = centre_x - 0.42 * width, centre_x + 0.42 * width
    current_x0, current_x1 = centre_x - 0.34 * width, centre_x + 0.34 * width
    indicator_y = 1.22 * depth
    fig.add_shape(
        type="line",
        x0=original_x0,
        y0=indicator_y,
        x1=original_x1,
        y1=indicator_y,
        line=dict(color=_SHRINKAGE_ORIGINAL_OUTLINE, width=1.5, dash="dash"),
        layer="above",
    )
    fig.add_shape(
        type="line",
        x0=current_x0,
        y0=indicator_y,
        x1=current_x1,
        y1=indicator_y,
        line=dict(color=LINK_STEEL, width=2.0),
        layer="above",
    )
    for x, ax in ((current_x0, original_x0), (current_x1, original_x1)):
        fig.add_annotation(
            x=x,
            y=indicator_y,
            ax=ax,
            ay=indicator_y,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.75,
            arrowwidth=1.25,
            arrowcolor=_SHRINKAGE_NAVY,
        )
    fig.add_annotation(
        x=centre_x,
        y=1.34 * depth,
        text="<b>Beam shortens</b>",
        showarrow=False,
        font=dict(size=12, color=_SHRINKAGE_NAVY),
    )
    fig.add_annotation(
        x=centre_x,
        y=1.08 * depth,
        text="<i>Deformation exaggerated</i>",
        showarrow=False,
        font=dict(size=10, color=ANNOTATION_TEXT),
    )

    reo_layout = dict(layout.get("reo_layout") or {})
    bottom_layers = list(reo_layout.get("bottom") or [])
    top_layers = list(reo_layout.get("top") or [])
    bottom_count = sum(len(layer.get("x") or []) for layer in bottom_layers)
    top_count = sum(len(layer.get("x") or []) for layer in top_layers)
    existing_meta = fig.layout.meta if isinstance(fig.layout.meta, dict) else {}
    fig.update_layout(
        autosize=True,
        height=int(height_px),
        paper_bgcolor=DIAGRAM_BG,
        plot_bgcolor=DIAGRAM_BG,
        showlegend=False,
        margin=dict(l=12, r=12, t=18, b=18),
        meta={
            **dict(existing_meta),
            "diagram_component": "shared_standard_beam_cross_section_with_shrinkage_overlay",
            "base_component": "ui.diagrams.section_diagram.build_summary_cross_section_result",
            "section_shape": str(layout.get("shape_name") or ""),
            "source_dimensions": dict(layout.get("dims") or {}),
            "source_cover": {
                "top": float(reo.get("cover_top", 0.0) or 0.0),
                "bottom": float(reo.get("cover_bot", 0.0) or 0.0),
                "side": float(reo.get("cover_side", 0.0) or 0.0),
            },
            "source_reinforcement": {
                "bottom_bar_count": int(bottom_count),
                "top_bar_count": int(top_count),
                "bottom_layer_count": len(bottom_layers),
                "top_layer_count": len(top_layers),
                "link_diameter": float(reo.get("lig_d", 0.0) or 0.0),
                "link_legs": int(reo.get("lig_legs", 0) or 0),
            },
            "shrinkage_overlay": {
                "moisture_particles": len(moisture_x),
                "exposed_faces": exposed_kind,
                "deformation_exaggerated": True,
                "beam_shortening_indicator": True,
            },
        },
    )
    fig.update_xaxes(
        visible=False,
        range=[centre_x - 1.08 * frame, centre_x + 1.08 * frame],
        fixedrange=True,
    )
    fig.update_yaxes(
        visible=False,
        range=[1.47 * depth, -0.36 * depth],
        fixedrange=True,
        scaleanchor="x",
        scaleratio=1,
    )
    return SectionDiagramResult(fig, error_message=base_result.error_message)


def build_shrinkage_side_view_result(
    *,
    layout: dict[str, Any],
    faces_option: str = "Beam - three faces exposed",
    height_px: int = 520,
    model: dict[str, Any] | None = None,
    base_side_view_builder: SideViewBuilder | None = None,
) -> SectionDiagramResult:
    """Overlay drying-shrinkage cues on the shared longitudinal beam view."""
    if model is None:
        # Imported lazily because shear_visuals also exposes compatibility
        # wrappers for the historical creep/shrinkage diagrams.
        from shear_visuals import _beam_model

        work_model = dict(_beam_model())
    else:
        work_model = dict(model)

    dims = dict(layout.get("dims") or {})
    reo = dict(layout.get("reo") or {})
    reo_layout = dict(layout.get("reo_layout") or {})
    depth_mm = float(dims.get("D", 600.0) or 600.0)
    depth_m = max(depth_mm / 1000.0, 0.05)
    work_model["D_m"] = depth_m
    work_model["section_layout"] = layout
    work_model["bottom_layers"] = list(reo_layout.get("bottom") or [])
    work_model["top_layers"] = list(reo_layout.get("top") or [])
    work_model["spacing_mm"] = max(float(reo.get("s_lig", work_model.get("spacing_mm", 0.0)) or 0.0), 0.0)
    work_model["lig_legs"] = int(max(float(reo.get("lig_legs", work_model.get("lig_legs", 0)) or 0), 0.0))
    work_model["total_length_m"] = max(float(work_model.get("total_length_m", 6.0) or 6.0), 0.1)
    work_model["span_m"] = max(float(work_model.get("span_m", work_model["total_length_m"]) or work_model["total_length_m"]), 0.1)
    work_model.setdefault("support_condition", "simply_supported")
    work_model.setdefault("support_pair", ("Pinned", "Roller"))
    work_model.setdefault("support_positions", [0.0, work_model["total_length_m"]])
    work_model["side_view_display"] = side_view_display_state(work_model)

    builder = base_side_view_builder or build_standard_reinforced_beam_side_view
    fig = builder(work_model, height=int(height_px))
    display_length_m = side_view_display_length_from_model(work_model)
    frame = max(display_length_m, 1e-6)
    exposed_kind = _exposed_edge_kind(faces_option)

    # The shared beam band remains the source of geometry and fill. Its outline
    # becomes the original dashed perimeter, with a contracted solid outline
    # drawn just inside it for the shrinkage teaching overlay.
    for shape in fig.layout.shapes or ():
        if (
            str(getattr(shape, "type", "")) == "rect"
            and abs(float(getattr(shape, "x0", -1.0) or 0.0)) <= 1e-9
            and abs(float(getattr(shape, "y0", -1.0) or 0.0)) <= 1e-9
            and abs(float(getattr(shape, "x1", 0.0) or 0.0) - display_length_m) <= 1e-8
            and abs(float(getattr(shape, "y1", 0.0) or 0.0) - depth_m) <= 1e-8
        ):
            shape.line.color = _SHRINKAGE_ORIGINAL_OUTLINE
            shape.line.width = 1.5
            shape.line.dash = "dash"
            break

    x_inset = 0.026 * display_length_m
    y_inset = 0.035 * depth_m
    contracted_x0 = x_inset
    contracted_x1 = display_length_m - x_inset
    contracted_y0 = y_inset
    contracted_y1 = depth_m - y_inset
    fig.add_shape(
        type="rect",
        x0=contracted_x0,
        y0=contracted_y0,
        x1=contracted_x1,
        y1=contracted_y1,
        line=dict(color=CONCRETE_OUTLINE, width=2.0),
        fillcolor="rgba(0,0,0,0)",
        layer="above",
    )

    # Surface band follows the exposed faces in the side elevation.
    surface_edges = [(contracted_x0, contracted_y1, contracted_x1, contracted_y1)]
    if exposed_kind in {"top_sides", "all"}:
        surface_edges.extend(
            [
                (contracted_x0, contracted_y0, contracted_x0, contracted_y1),
                (contracted_x1, contracted_y0, contracted_x1, contracted_y1),
            ]
        )
    if exposed_kind in {"top_bottom", "all"}:
        surface_edges.append((contracted_x0, contracted_y0, contracted_x1, contracted_y0))
    for x0, y0, x1, y1 in surface_edges:
        fig.add_shape(
            type="line",
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            line=dict(color=_SHRINKAGE_SURFACE_BAND, width=6),
            layer="above",
        )

    # Moisture particles are distributed through the beam body. Their hover
    # text also reports the live section and reinforcement inputs that cannot
    # all be distinguished geometrically in a longitudinal elevation.
    rng = np.random.default_rng(3610)
    moisture_x: list[float] = []
    moisture_y: list[float] = []
    for row in range(4):
        for col in range(18):
            moisture_x.append(
                contracted_x0
                + (contracted_x1 - contracted_x0) * (col + 0.5) / 18.0
                + float(rng.uniform(-0.007, 0.007)) * frame
            )
            moisture_y.append(
                contracted_y0
                + (contracted_y1 - contracted_y0) * (row + 0.5) / 4.0
                + float(rng.uniform(-0.018, 0.018)) * depth_m
            )

    bottom_layers = list(reo_layout.get("bottom") or [])
    top_layers = list(reo_layout.get("top") or [])
    bottom_count = sum(len(layer.get("x") or []) for layer in bottom_layers)
    top_count = sum(len(layer.get("x") or []) for layer in top_layers)
    width_mm = float(dims.get("bf", dims.get("b", 0.0)) or 0.0)
    hover_text = (
        f"Section: {width_mm:.0f} × {depth_mm:.0f} mm"
        f"<br>Bottom bars: {bottom_count}"
        f"<br>Top bars: {top_count}"
        f"<br>Links: {float(reo.get('lig_d', 0.0) or 0.0):.0f} mm"
        f" @ {float(reo.get('s_lig', 0.0) or 0.0):.0f} mm"
    )
    fig.add_trace(
        go.Scatter(
            x=moisture_x,
            y=moisture_y,
            mode="markers",
            marker=dict(size=5, color=_SHRINKAGE_MOISTURE_BLUE),
            hovertemplate=hover_text + "<extra>Moisture</extra>",
            name="Moisture",
            showlegend=False,
        )
    )

    def _arrow(x: float, y: float, ax: float, ay: float, *, blue: bool = False) -> None:
        fig.add_annotation(
            x=x,
            y=y,
            ax=ax,
            ay=ay,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=3 if blue else 2,
            arrowsize=0.82,
            arrowwidth=1.6 if blue else 1.2,
            arrowcolor=_SHRINKAGE_EVAPORATION_BLUE if blue else _SHRINKAGE_NAVY,
        )

    for fraction in (0.22, 0.50, 0.78):
        x_val = fraction * display_length_m
        _arrow(x_val, 1.34 * depth_m, x_val, contracted_y1, blue=True)
    if exposed_kind in {"top_sides", "all"}:
        _arrow(-0.055 * frame, 0.52 * depth_m, contracted_x0, 0.52 * depth_m, blue=True)
        _arrow(1.055 * frame, 0.52 * depth_m, contracted_x1, 0.52 * depth_m, blue=True)

    # Fine surface-starting cracks remain secondary to the shared beam detail.
    for fraction, lean in ((0.31, -0.010), (0.56, 0.012), (0.73, -0.008)):
        x0 = fraction * display_length_m
        crack_points = [
            (x0, contracted_y1),
            (x0 + lean * frame, 0.94 * depth_m),
            (x0 - 0.006 * frame, 0.88 * depth_m),
            (x0 + 0.004 * frame, 0.82 * depth_m),
        ]
        fig.add_shape(
            type="path",
            path=_path_from_points(crack_points, close=False),
            line=dict(color="rgba(30,41,59,0.72)", width=1.1),
            fillcolor="rgba(0,0,0,0)",
            layer="above",
        )

    # Inward arrows communicate contraction in both length and depth.
    _arrow(contracted_x0 + 0.045 * frame, 0.50 * depth_m, -0.035 * frame, 0.50 * depth_m)
    _arrow(contracted_x1 - 0.045 * frame, 0.50 * depth_m, 1.035 * frame, 0.50 * depth_m)
    _arrow(0.50 * frame, contracted_y1 - 0.08 * depth_m, 0.50 * frame, 1.13 * depth_m)
    _arrow(0.50 * frame, contracted_y0 + 0.08 * depth_m, 0.50 * frame, -0.13 * depth_m)

    fig.add_annotation(
        x=0.50 * frame,
        y=1.52 * depth_m,
        text="<b>Moisture loss</b>",
        showarrow=False,
        font=dict(size=12, color=_SHRINKAGE_EVAPORATION_BLUE),
        bgcolor=ANNOTATION_BG,
        borderpad=3,
    )
    _add_leader_label(
        fig,
        target_x=0.16 * frame,
        target_y=contracted_y1,
        label_x=0.08 * frame,
        label_y=1.66 * depth_m,
        text="Surface dries first",
    )
    _add_leader_label(
        fig,
        target_x=0.56 * frame,
        target_y=0.91 * depth_m,
        label_x=0.70 * frame,
        label_y=1.66 * depth_m,
        text="Shrinkage cracking",
    )
    fig.add_annotation(
        x=0.50 * frame,
        y=-0.50 * depth_m,
        text="Concrete contracts as it dries",
        showarrow=False,
        font=dict(size=11, color=ANNOTATION_TEXT),
        bgcolor=ANNOTATION_BG,
        borderpad=3,
    )
    fig.add_annotation(
        x=0.97 * frame,
        y=1.48 * depth_m,
        text="<i>Deformation exaggerated</i>",
        showarrow=False,
        font=dict(size=10, color=ANNOTATION_TEXT),
        xanchor="right",
    )

    # Length comparison is aligned to the longitudinal beam rather than shown
    # as a detached cross-section indicator.
    indicator_y = -0.72 * depth_m
    original_x0, original_x1 = 0.12 * frame, 0.88 * frame
    current_x0, current_x1 = 0.18 * frame, 0.82 * frame
    fig.add_shape(
        type="line",
        x0=original_x0,
        y0=indicator_y,
        x1=original_x1,
        y1=indicator_y,
        line=dict(color=_SHRINKAGE_ORIGINAL_OUTLINE, width=1.5, dash="dash"),
        layer="above",
    )
    fig.add_shape(
        type="line",
        x0=current_x0,
        y0=indicator_y,
        x1=current_x1,
        y1=indicator_y,
        line=dict(color=LINK_STEEL, width=2.0),
        layer="above",
    )
    _arrow(current_x0, indicator_y, original_x0, indicator_y)
    _arrow(current_x1, indicator_y, original_x1, indicator_y)
    fig.add_annotation(
        x=0.50 * frame,
        y=-0.91 * depth_m,
        text="<b>Beam shortens</b>",
        showarrow=False,
        font=dict(size=12, color=_SHRINKAGE_NAVY),
    )

    fit_side_view_figure_to_content(
        fig,
        length_m=work_model["total_length_m"],
        beam_depth_m=depth_m,
        support_condition=str(work_model.get("support_condition", "simply_supported")),
        height=int(height_px),
        display_length_m=display_length_m,
        y_min_needed=-1.02 * depth_m,
        y_max_needed=1.78 * depth_m,
    )
    existing_meta = fig.layout.meta if isinstance(fig.layout.meta, dict) else {}
    fig.update_layout(
        paper_bgcolor=DIAGRAM_BG,
        plot_bgcolor=DIAGRAM_BG,
        meta={
            **dict(existing_meta),
            "diagram_component": "shared_standard_beam_side_view_with_shrinkage_overlay",
            "base_component": "ui.diagrams.side_view_diagram.build_standard_reinforced_beam_side_view",
            "source_dimensions": dims,
            "source_span_m": float(work_model["total_length_m"]),
            "source_cover": {
                "top": float(reo.get("cover_top", 0.0) or 0.0),
                "bottom": float(reo.get("cover_bot", 0.0) or 0.0),
                "side": float(reo.get("cover_side", 0.0) or 0.0),
            },
            "source_reinforcement": {
                "bottom_bar_count": int(bottom_count),
                "top_bar_count": int(top_count),
                "bottom_layer_count": len(bottom_layers),
                "top_layer_count": len(top_layers),
                "link_diameter": float(reo.get("lig_d", 0.0) or 0.0),
                "link_legs": int(reo.get("lig_legs", 0) or 0),
                "link_spacing": float(reo.get("s_lig", 0.0) or 0.0),
            },
            "shrinkage_overlay": {
                "view": "longitudinal_side_elevation",
                "moisture_particles": len(moisture_x),
                "exposed_faces": exposed_kind,
                "deformation_exaggerated": True,
                "beam_shortening_indicator": True,
            },
        },
    )
    return SectionDiagramResult(fig)


def build_shrinkage_schematic_plotly(width_px: int = 1100, height_px: int = 420) -> go.Figure:
    rng = np.random.default_rng(42)

    fig = go.Figure()

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------
    x0, x1 = 8.0, 96.0
    y0, y1 = 4.0, 18.0
    crust_y0 = 17.2

    # Main slab
    fig.add_shape(
        type="rect",
        x0=x0, y0=y0, x1=x1, y1=y1,
        line=dict(color="black", width=2),
        fillcolor="rgb(233,226,214)",
        layer="below",
    )

    # Dry thin crust strip
    fig.add_shape(
        type="rect",
        x0=x0, y0=crust_y0, x1=x1, y1=y1,
        line=dict(color="rgba(0,0,0,0)", width=0),
        fillcolor="rgb(205,189,166)",
        layer="below",
    )

    # ------------------------------------------------------------------
    # Concrete stipple texture
    # ------------------------------------------------------------------
    n_dots = 1800
    dots_x = rng.uniform(x0 + 0.6, x1 - 0.6, n_dots)
    dots_y = rng.uniform(y0 + 0.4, y1 - 0.6, n_dots)

    fig.add_trace(
        go.Scatter(
            x=dots_x,
            y=dots_y,
            mode="markers",
            marker=dict(size=2, color="rgba(120,110,95,0.22)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # ------------------------------------------------------------------
    # Aggregate particles
    # ------------------------------------------------------------------
    n_agg = 70
    agg_x = rng.uniform(x0 + 1.2, x1 - 1.2, n_agg)
    agg_y = rng.uniform(y0 + 1.0, y1 - 0.8, n_agg)
    agg_size = rng.uniform(6, 18, n_agg)

    fig.add_trace(
        go.Scatter(
            x=agg_x,
            y=agg_y,
            mode="markers",
            marker=dict(
                size=agg_size,
                color="rgb(147, 208, 232)",
                line=dict(color="black", width=0.8),
                symbol="circle",
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # Some larger "stone" pieces near top for visual similarity
    fig.add_trace(
        go.Scatter(
            x=[19, 33, 43, 64, 77, 88],
            y=[16.8, 16.5, 16.3, 16.9, 16.1, 16.7],
            mode="markers",
            marker=dict(
                size=[14, 22, 18, 16, 20, 15],
                color="rgb(147, 208, 232)",
                line=dict(color="black", width=1.0),
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # ------------------------------------------------------------------
    # Cracks (wavy lines descending from the top surface)
    # ------------------------------------------------------------------
    def add_crack(x_start: float, y_top: float, y_bot: float, amp: float = 0.45, phase: float = 0.0):
        ys = np.linspace(y_top, y_bot, 120)
        t = np.linspace(0, 1, 120)
        xs = x_start + amp * np.sin(2.6 * np.pi * t + phase) * (0.6 + 0.7 * t)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(color="black", width=2.2),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    add_crack(13.0, 17.9, 12.0, amp=0.38, phase=0.0)
    add_crack(25.5, 17.9, 11.2, amp=0.46, phase=0.6)
    add_crack(38.5, 17.9, 4.3, amp=0.52, phase=1.2)
    add_crack(51.0, 17.9, 13.0, amp=0.36, phase=0.9)
    add_crack(69.5, 17.9, 12.0, amp=0.34, phase=0.4)
    add_crack(79.5, 17.9, 4.4, amp=0.56, phase=1.0)
    add_crack(92.0, 17.9, 10.0, amp=0.34, phase=0.2)

    # ------------------------------------------------------------------
    # Evaporation arrows
    # ------------------------------------------------------------------
    evap_x = [14, 26, 35, 46, 57, 67, 78, 86, 95]
    for xi in evap_x:
        fig.add_annotation(
            x=xi,
            y=25.0,
            ax=xi - 0.8,
            ay=18.6,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.0,
            arrowwidth=1.8,
            arrowcolor=_SHRINKAGE_EVAPORATION_BLUE,
        )

    # ------------------------------------------------------------------
    # Left dashed bracket for drying shrinkage
    # ------------------------------------------------------------------
    bx = 4.7
    fig.add_shape(
        type="line",
        x0=bx, y0=y0, x1=bx, y1=y1,
        line=dict(color="black", width=2, dash="dash"),
    )
    fig.add_shape(
        type="line",
        x0=bx, y0=y0, x1=x0, y1=y0,
        line=dict(color="black", width=2, dash="dash"),
    )
    fig.add_shape(
        type="line",
        x0=bx, y0=y1, x1=x0, y1=y1,
        line=dict(color="black", width=2, dash="dash"),
    )

    # Little bottom arrows showing inward shrinkage
    fig.add_annotation(
        x=7.4, y=1.3, ax=4.7, ay=1.3,
        xref="x", yref="y", axref="x", ayref="y",
        text="", showarrow=True, arrowhead=2, arrowwidth=1.8, arrowcolor="black"
    )
    fig.add_annotation(
        x=9.1, y=1.3, ax=11.8, ay=1.3,
        xref="x", yref="y", axref="x", ayref="y",
        text="", showarrow=True, arrowhead=2, arrowwidth=1.8, arrowcolor="black"
    )

    # ------------------------------------------------------------------
    # Labels / callouts
    # ------------------------------------------------------------------
    fig.add_annotation(
        x=12.0, y=24.7,
        text="<b>Water loss through<br>evaporation</b>",
        showarrow=False,
        font=dict(size=18, color=_SHRINKAGE_EVAPORATION_BLUE),
        align="left",
    )

    fig.add_annotation(
        x=39.0, y=18.1,
        ax=49.0, ay=26.4,
        xref="x", yref="y", axref="x", ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowwidth=2.0,
        arrowcolor="black",
    )

    fig.add_annotation(
        x=74.0, y=18.1,
        ax=66.0, ay=26.2,
        xref="x", yref="y", axref="x", ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowwidth=2.0,
        arrowcolor="black",
    )

    fig.add_annotation(
        x=61.0, y=28.0,
        text="<b>Plastic<br>Shrinkage<br>Cracks</b>",
        showarrow=False,
        font=dict(size=18, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=90.5, y=18.0,
        ax=88.0, ay=26.8,
        xref="x", yref="y", axref="x", ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowwidth=2.0,
        arrowcolor="black",
    )

    fig.add_annotation(
        x=87.0, y=28.0,
        text="<b>Dry Thin<br>Crust</b>",
        showarrow=False,
        font=dict(size=18, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=1.6,
        y=(y0 + y1) / 2,
        text="<b>Drying Shrinkage</b>",
        textangle=-90,
        showarrow=False,
        font=dict(size=20, color="black"),
    )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    fig.update_xaxes(
        visible=False,
        range=[0, 100],
        fixedrange=True,
    )
    fig.update_yaxes(
        visible=False,
        range=[0, 30],
        fixedrange=True,
        scaleanchor=None,
    )

    fig.update_layout(
        width=width_px,
        height=height_px,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig


def build_creep_schematic_plotly(width_px: int = 1100, height_px: int = 420) -> go.Figure:
    """
    Teaching schematic: concrete prism under sustained compression — elastic + creep shortening.
    Visual language matches build_shrinkage_schematic_plotly (axes 0–100 × 0–30).
    """
    rng = np.random.default_rng(43)

    fig = go.Figure()

    x0 = 8.0
    x_right_ref = 96.0  # original (undeformed) length reference at right
    x_right_elastic = 94.2  # conceptual end after instantaneous elastic shortening
    x_right_curr = 92.4  # end after additional creep over time
    y0, y1 = 4.0, 18.0

    # Ghost outline: original prism (undeformed length)
    fig.add_shape(
        type="rect",
        x0=x0,
        y0=y0,
        x1=x_right_ref,
        y1=y1,
        line=dict(color="rgba(80,80,80,0.55)", width=1.5, dash="dash"),
        fillcolor="rgba(233,226,214,0.18)",
        layer="below",
    )

    # Current prism body (shortened — sustained load + creep)
    fig.add_shape(
        type="rect",
        x0=x0,
        y0=y0,
        x1=x_right_curr,
        y1=y1,
        line=dict(color="black", width=2),
        fillcolor="rgb(233,226,214)",
        layer="below",
    )

    # Subtle “elastic-only” interior hint (slightly darker strip near right end)
    fig.add_shape(
        type="rect",
        x0=x_right_elastic - 0.15,
        y0=y0 + 0.35,
        x1=x_right_curr + 0.08,
        y1=y1 - 0.35,
        line=dict(color="rgba(0,0,0,0)", width=0),
        fillcolor="rgba(205,189,166,0.35)",
        layer="below",
    )

    # Stipple (current volume only)
    n_dots = 1600
    dots_x = rng.uniform(x0 + 0.6, x_right_curr - 0.5, n_dots)
    dots_y = rng.uniform(y0 + 0.4, y1 - 0.6, n_dots)
    fig.add_trace(
        go.Scatter(
            x=dots_x,
            y=dots_y,
            mode="markers",
            marker=dict(size=2, color="rgba(120,110,95,0.22)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    n_agg = 65
    agg_x = rng.uniform(x0 + 1.0, x_right_curr - 1.0, n_agg)
    agg_y = rng.uniform(y0 + 1.0, y1 - 0.8, n_agg)
    agg_size = rng.uniform(6, 17, n_agg)
    fig.add_trace(
        go.Scatter(
            x=agg_x,
            y=agg_y,
            mode="markers",
            marker=dict(
                size=agg_size,
                color="rgb(147, 208, 232)",
                line=dict(color="black", width=0.8),
                symbol="circle",
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # Reference: fixed left face
    fig.add_shape(
        type="line",
        x0=x0,
        y0=y0 - 0.35,
        x1=x0,
        y1=y1 + 0.35,
        line=dict(color="black", width=2, dash="dash"),
        layer="below",
    )

    # Reference: original right face (undeformed end)
    fig.add_shape(
        type="line",
        x0=x_right_ref,
        y0=y0,
        x1=x_right_ref,
        y1=y1,
        line=dict(color="rgba(60,60,60,0.75)", width=2, dash="dash"),
        layer="below",
    )

    # Internal creep / flow cues (gentle curves drifting toward fixed end)
    for i, (xa, xb) in enumerate([(18.0, 78.0), (28.0, 85.0), (22.0, 72.0), (38.0, 88.0)]):
        t = np.linspace(0, 1, 48)
        xs = xa + (xb - xa) * t + 0.55 * np.sin(2.4 * np.pi * t + 0.4 * i)
        ys = (y0 + y1) / 2 + 2.8 * np.sin(1.1 * np.pi * t + i * 0.35)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(color="rgba(40,40,40,0.45)", width=1.2, dash="dot"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Short internal dashed arrows (delayed strain development), pointing left
    for xi, yi in [(30, 12.5), (48, 9.8), (62, 14.0), (76, 11.2)]:
        fig.add_annotation(
            x=xi - 2.8,
            y=yi,
            ax=xi + 1.4,
            ay=yi,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=0.85,
            arrowwidth=1.2,
            arrowcolor="rgba(35,35,35,0.75)",
        )

    # Sustained compression: downward arrows above prism
    for xi in [16, 30, 44, 58, 72, 86]:
        fig.add_annotation(
            x=xi,
            y=24.8,
            ax=xi + 0.35,
            ay=18.35,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.0,
            arrowwidth=1.8,
            arrowcolor="black",
        )

    # Reactions: upward arrows below
    for xi in [20, 38, 54, 70, 84]:
        fig.add_annotation(
            x=xi,
            y=1.55,
            ax=xi + 0.25,
            ay=3.85,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.0,
            arrowwidth=1.8,
            arrowcolor="black",
        )

    # Dimension: elastic + creep separation at right (horizontal bracket via line + arrows)
    fig.add_shape(
        type="line",
        x0=x_right_elastic,
        y0=2.35,
        x1=x_right_ref,
        y1=2.35,
        line=dict(color="black", width=1.2, dash="dot"),
        layer="above",
    )
    fig.add_shape(
        type="line",
        x0=x_right_curr,
        y0=2.0,
        x1=x_right_elastic,
        y1=2.0,
        line=dict(color="black", width=1.2),
        layer="above",
    )

    # Labels (minimal set)
    fig.add_annotation(
        x=48.0,
        y=26.8,
        text="<b>Sustained compressive stress</b>",
        showarrow=False,
        font=dict(size=18, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=88.0,
        y=19.8,
        text="<b>Instantaneous<br>elastic strain</b>",
        showarrow=False,
        font=dict(size=14, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=(x_right_curr + x_right_ref) / 2,
        y=1.05,
        text="<b>Additional creep strain over time</b>",
        showarrow=False,
        font=dict(size=14, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=44.0,
        y=11.0,
        text="<b>Time-dependent viscoelastic<br>deformation</b>",
        showarrow=False,
        font=dict(size=14, color="black"),
        align="center",
    )

    fig.add_annotation(
        x=50.0,
        y=28.3,
        text="<i>Deformation increases with time while load is maintained</i>",
        showarrow=False,
        font=dict(size=11, color="#333333"),
        align="center",
    )

    fig.update_xaxes(
        visible=False,
        range=[0, 100],
        fixedrange=True,
    )
    fig.update_yaxes(
        visible=False,
        range=[0, 30],
        fixedrange=True,
        scaleanchor=None,
    )

    fig.update_layout(
        width=width_px,
        height=height_px,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )

    return fig
