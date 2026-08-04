"""Typed Inputs-page diagram models.

These models describe diagram request data only. They do not render Streamlit,
do not compute engineering truth, and do not own session state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InputsDiagramSourceSnapshot:
    layout: dict[str, Any]
    shared_state: dict[str, Any]
    tension_face: str | None = None
    fallback_cover_side: float = 40.0
    fallback_cover_top: float = 40.0
    fallback_cover_bot: float = 40.0
    fallback_width: float = 400.0
    fallback_depth: float = 600.0
    span_length: float = 3000.0
    outline_points: tuple[tuple[float, float], ...] = ()
    outline_width: float = 400.0
    outline_depth: float = 600.0


@dataclass(frozen=True)
class Section2DFigureRequestViewModel:
    shape_name: str
    dims: dict[str, Any]
    reo: dict[str, Any]
    show_shear: bool
    show_dn: bool = False
    dn: float = 0.0
    tension_face: str | None = None
    fallback_cover_side: float = 40.0
    fallback_cover_top: float = 40.0
    fallback_cover_bot: float = 40.0
    display_hash: str = ""


@dataclass(frozen=True)
class Beam3DFigureRequestViewModel:
    shape_name: str
    shape_key: str
    outline_points: tuple[tuple[float, float], ...]
    b_box: float
    D: float
    L_plot: float
    fallback_width: float
    cover_bot: float
    cover_top: float
    cover_side: float
    lig_d: float
    lig_legs: int
    s_lig: float
    reo_layout: dict[str, Any]
    cage: dict[str, Any]
    resolved_bars: tuple[dict[str, Any], ...] | None = None
    display_hash: str = ""


@dataclass(frozen=True)
class InputsDiagramSectionViewModel:
    section_2d: Section2DFigureRequestViewModel
    beam_3d: Beam3DFigureRequestViewModel
    display_hash: str

