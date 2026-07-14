"""Shared visual constants for diagram modules.

Keep constants local and explicit; do not set global Plotly defaults here.
"""

from __future__ import annotations

from typing import Any


# General
DIAGRAM_BG = "white"
DIAGRAM_TRANSPARENT = "rgba(0,0,0,0)"

# Concrete
CONCRETE_FILL_2D = "rgba(210,216,224,0.30)"
CONCRETE_FILL_3D = "#cccccc"
CONCRETE_OUTLINE = "rgba(30,30,30,1.0)"

# Reinforcement
REO_BOTTOM = "rgba(0,90,200,0.95)"
REO_TOP = "rgba(200,45,45,0.95)"
REO_INACTIVE = "rgba(136,136,136,0.92)"
LINK_STEEL = "rgba(0,0,0,0.95)"

# Supports
SUPPORT_OUTLINE = "rgba(35,35,35,1.0)"
SUPPORT_FILL = "rgba(35,35,35,0.12)"
SUPPORT_GROUND = "rgba(80,80,80,0.85)"
SUPPORT_GROUND_HATCH = "rgba(80,80,80,0.82)"
SUPPORT_ROLLER_FILL = "rgba(255,255,255,0.55)"
SUPPORT_PIN_WIDTH_SPAN_RATIO = 0.02
SUPPORT_PIN_MIN_WIDTH_MM = 18.0
SUPPORT_PIN_DEPTH_BEAM_RATIO = 0.12
SUPPORT_PIN_MIN_DEPTH_MM = 10.0
SUPPORT_GROUND_DROP_BEAM_RATIO = 0.12
SUPPORT_GROUND_MIN_DROP_MM = 8.0
SUPPORT_ROLLER_RADIUS_BEAM_RATIO = 0.04
SUPPORT_ROLLER_MIN_RADIUS_MM = 5.0
SUPPORT_FIXED_OVERHANG_BEAM_RATIO = 0.55
SUPPORT_FIXED_HATCH_SPAN_RATIO = 0.015
SUPPORT_FIXED_MIN_HATCH_MM = 12.0

# Deflection
DEFLECTED_FILL = "rgba(31,119,180,0.30)"
DEFLECTED_LINE = "rgba(31,119,180,1.0)"
UNDEFORMED_FILL = "rgba(210,210,210,0.22)"
UNDEFORMED_LINE = "rgba(140,140,140,0.95)"
MAX_DEFLECTION_MARKER = "#c0392b"
DEFLECTION_VISUAL_TARGET_DEPTH_RATIO = 0.20
DEFLECTION_VISUAL_TARGET_MIN_MM = 35.0
DEFLECTION_VISUAL_SCALE_MIN = 0.05
DEFLECTION_VISUAL_SCALE_MAX = 40.0

# Engineering meaning colours
COMPRESSION = "rgba(200,45,45,0.95)"
TENSION = "rgba(0,90,200,0.95)"
CRACK_LINE = "rgba(6,6,10,0.97)"

# Annotations
ANNOTATION_BG = "rgba(255,255,255,0.9)"
ANNOTATION_BORDER = "rgba(0,0,0,0.15)"
ANNOTATION_TEXT = "#333"
TITLE_TEXT = "#222"
REFERENCE_LINE = "rgba(0,0,0,0)"
MARKER_OUTLINE = "white"

# Sizes
DIAGRAM_SIZE_LONGITUDINAL = {"width": 1120, "height": 390}
DIAGRAM_SIZE_BEHAVIOUR = {"width": 1120, "height": 630}
DIAGRAM_HEIGHT_ANALYSIS = 420
DIAGRAM_HEIGHT_SECTION_COMPACT = 475
DIAGRAM_HEIGHT_SECTION_NORMAL = 545
DIAGRAM_HEIGHT_STEP_DETAIL = 540
DIAGRAM_HEIGHT_STRIP = 140
DIAGRAM_HEIGHT_LOCATOR = 70
DIAGRAM_HEIGHT_SFD_BMD = 300
DIAGRAM_HEIGHT_MOMENT_SMALL = 260
DIAGRAM_HEIGHT_3D_SMALL = 350


def diagram_line(color: str, width: float = 1.0, **kwargs: Any) -> dict[str, Any]:
    """Return a Plotly line style dictionary."""
    return {"color": color, "width": width, **kwargs}


def diagram_annotation_style(
    *,
    size: int = 11,
    color: str = ANNOTATION_TEXT,
    bgcolor: str = ANNOTATION_BG,
    bordercolor: str = ANNOTATION_BORDER,
    borderwidth: int = 1,
    borderpad: int = 4,
) -> dict[str, Any]:
    """Return shared Plotly annotation styling."""
    return {
        "font": {"size": size, "color": color},
        "bgcolor": bgcolor,
        "bordercolor": bordercolor,
        "borderwidth": borderwidth,
        "borderpad": borderpad,
    }


def diagram_deflection_visual_scale_factor(
    max_abs_deflection_mm: float,
    depth_mm: float,
) -> float:
    """Shared vertical exaggeration for longitudinal deflected-shape diagrams."""
    try:
        max_abs = abs(float(max_abs_deflection_mm))
        depth = abs(float(depth_mm))
    except (TypeError, ValueError):
        return 1.0
    if max_abs <= 1e-15 or depth <= 0.0:
        return 1.0
    target_visual_drop = max(
        DEFLECTION_VISUAL_TARGET_DEPTH_RATIO * depth,
        DEFLECTION_VISUAL_TARGET_MIN_MM,
    )
    raw_scale = target_visual_drop / max_abs
    return float(min(max(raw_scale, DEFLECTION_VISUAL_SCALE_MIN), DEFLECTION_VISUAL_SCALE_MAX))


def apply_diagram_layout(
    fig: Any,
    height: int,
    margin: dict[str, int] | None = None,
    background: str = DIAGRAM_BG,
    showlegend: bool = False,
) -> Any:
    """Apply visual-only shared Plotly layout defaults."""
    fig.update_layout(
        height=height,
        margin=margin,
        paper_bgcolor=background,
        plot_bgcolor=background,
        showlegend=showlegend,
    )
    return fig
