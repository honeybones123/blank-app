"""Pure diagram projection from canonical BeamInputs."""

from __future__ import annotations

from dataclasses import dataclass
import math

from inputs_v2.domain.beam_inputs import BeamInputs, LayoutMode
from inputs_v2.domain.reinforcement_arrangement import ReinforcementArrangement


@dataclass(frozen=True, slots=True)
class DiagramBar:
    x_mm: float
    y_mm: float
    diameter_mm: float


@dataclass(frozen=True, slots=True)
class InputDiagramViewModel:
    source_revision: int
    source_hash: str
    width_mm: float
    depth_mm: float
    span_mm: float
    cage_inset_mm: float
    shear_diameter_mm: float
    bars: tuple[DiagramBar, ...]
    top_bars: tuple[DiagramBar, ...]
    shear_links: tuple[float, ...]
    resolved_bar_count: int
    bottom_rows: tuple[tuple[DiagramBar, ...], ...] = ()


def _resolved_count(inputs: BeamInputs) -> int:
    bottom = inputs.bottom
    if bottom.mode is LayoutMode.COUNT:
        return bottom.bars
    centre_cover = bottom.cover_mm + bottom.diameter_mm / 2.0
    usable = max(0.0, inputs.width_mm - 2.0 * centre_cover)
    return max(2, min(12, int(math.floor(usable / bottom.spacing_mm)) + 1))


def build_input_diagram_view_model(inputs: BeamInputs, arrangement: ReinforcementArrangement | None = None) -> InputDiagramViewModel:
    arrangement = inputs.bottom_arrangement if arrangement is None else arrangement
    count = _resolved_count(inputs)
    radius = inputs.bottom.diameter_mm / 2.0
    edge = inputs.bottom.cover_mm + radius
    usable = max(0.0, inputs.width_mm - 2.0 * edge)
    step = usable / max(1, count - 1)
    y = inputs.depth_mm - edge
    bars = tuple(
        DiagramBar(x_mm=edge + index * step, y_mm=y, diameter_mm=inputs.bottom.diameter_mm)
        for index in range(count)
    )
    bottom_rows: tuple[tuple[DiagramBar, ...], ...] = (bars,)
    if arrangement is not None and arrangement.rows:
        row_items = []
        for row in arrangement.rows:
            row_count = row.bar_count
            row_diameter = row.bar_diameter_mm or arrangement.bar_diameter_mm
            row_edge = inputs.bottom.cover_mm + row_diameter / 2.0
            row_usable = max(0.0, inputs.width_mm - 2.0 * row_edge)
            row_step = row_usable / max(1, row_count - 1)
            row_items.append(tuple(
                DiagramBar(row_edge + index * row_step, inputs.depth_mm - row.centre_from_tension_face_mm, row_diameter)
                for index in range(row_count)
            ))
        bottom_rows = tuple(row_items)
        bars = tuple(bar for row in bottom_rows for bar in row)
    top_edge = inputs.top.cover_mm + inputs.top.diameter_mm / 2.0
    top_usable = max(0.0, inputs.width_mm - 2.0 * top_edge)
    top_count = inputs.top.bars if inputs.top.mode is LayoutMode.COUNT else max(2, min(12, int(math.floor(top_usable / inputs.top.spacing_mm)) + 1))
    top_step = top_usable / max(1, top_count - 1)
    top_bars = tuple(
        DiagramBar(x_mm=top_edge + index * top_step, y_mm=top_edge, diameter_mm=inputs.top.diameter_mm)
        for index in range(top_count)
    )
    # An inactive link definition must not draw placeholder dotted guides.
    # Runtime only renders the stirrup when diameter and legs are active.
    if inputs.shear.diameter_mm > 0 and inputs.shear.legs >= 2:
        link_count = max(1, min(5, int(math.ceil(inputs.depth_mm / inputs.shear.spacing_mm))))
        shear_links = tuple(inputs.shear.spacing_mm * (index + 0.5) for index in range(link_count))
    else:
        shear_links = ()
    return InputDiagramViewModel(
        source_revision=inputs.revision,
        source_hash=inputs.content_hash,
        width_mm=inputs.width_mm,
        depth_mm=inputs.depth_mm,
        span_mm=inputs.span_mm,
        # Stirrup centreline sits outside the longitudinal-bar perimeter.
        # Place the inner face of the link steel directly against the outer
        # face of the largest longitudinal bar (allowing for the drawn line).
        cage_inset_mm=max(inputs.bottom.cover_mm + inputs.bottom.diameter_mm + inputs.shear.diameter_mm / 2.0 - 2.0, 5.0),
        shear_diameter_mm=inputs.shear.diameter_mm,
        bars=bars,
        top_bars=top_bars,
        shear_links=shear_links,
        resolved_bar_count=count,
        bottom_rows=bottom_rows,
    )
