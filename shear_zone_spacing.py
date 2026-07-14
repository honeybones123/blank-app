"""Compatibility wrapper for zoned shear spacing calculations and diagram rendering."""

from __future__ import annotations

from calculations.shear_zone_spacing import (
    EnvelopeKind,
    ZoneSpacingDesign,
    ZoneSpacingSegment,
    _cot,
    _merge_intervals,
    _normalize_envelope_cantilever_udl,
    _normalize_envelope_ss_udl,
    _zone_color,
    _zone_intervals_cantilever,
    _zone_intervals_ss,
    asv_min_over_s_mm,
    asv_over_s_required_mm,
    code_s_max_mm,
    compute_zoned_shear_spacing,
    practical_s_min_mm,
    snap_spacing_down_mm,
)
from ui.diagrams.shear_zone_spacing_diagram import (
    build_zone_spacing_strip_figure as _shared_build_zone_spacing_strip_figure,
)


def build_zone_spacing_strip_figure(
    design: ZoneSpacingDesign,
    *,
    beam_depth_m: float = 0.25,
    title: str | None = None,
):
    return _shared_build_zone_spacing_strip_figure(
        design,
        beam_depth_m=beam_depth_m,
        title=title,
    )