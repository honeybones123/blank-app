"""Inputs page diagram source and view-model builders."""

from .builders import (
    build_beam_3d_request_view_model,
    build_inputs_diagram_view_model,
    build_section_2d_request_view_model,
)
from .models import (
    Beam3DFigureRequestViewModel,
    InputsBeam3DRegionContext,
    InputsDiagramSectionViewModel,
    InputsDiagramSourceSnapshot,
    InputsSection2DRegionContext,
    Section2DFigureRequestViewModel,
)
from .render_coordinators import (
    render_inputs_3d_diagram_block,
    render_inputs_fast_model_block,
    render_inputs_section_2d_diagram_block,
)
from .source_projection import build_section_outline_points_and_bbox

__all__ = [
    "Beam3DFigureRequestViewModel",
    "InputsBeam3DRegionContext",
    "InputsDiagramSectionViewModel",
    "InputsDiagramSourceSnapshot",
    "InputsSection2DRegionContext",
    "Section2DFigureRequestViewModel",
    "build_section_outline_points_and_bbox",
    "build_beam_3d_request_view_model",
    "build_inputs_diagram_view_model",
    "build_section_2d_request_view_model",
    "render_inputs_3d_diagram_block",
    "render_inputs_fast_model_block",
    "render_inputs_section_2d_diagram_block",
]
