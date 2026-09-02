"""Wide teaching diagram for the SLS cracked transformed section.

Presentation only.  All section geometry, neutral-axis location, steel areas and
transformation factors come from the authoritative SLS result/base section
figure.  This module only reorganises the visual explanation into a wide,
non-overlapping layout.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import plotly.graph_objects as go

from engineering_page_sections.bending_sls_diagram import (
    _STATE_COLOURS,
    make_sls_canonical_section_figure,
)


_CARD_BG = {
    "compression": "rgba(254,226,226,0.72)",
    "tension": "rgba(219,234,254,0.72)",
    "neutral": "rgba(241,245,249,0.86)",
}

_CALLOUT_COLOURS = {
    "compression": "#dc2626",
    "tension": "#2563eb",
    "neutral": "#64748b",
}

def _transformed_expression(state: str) -> str:
    if state == "compression":
        return "(n−1)A<sub>s</sub>"
    if state == "tension":
        return "nA<sub>s</sub>"
    return "kA<sub>s</sub>"


def make_sls_transformed_section_figure(result: Mapping[str, Any]) -> go.Figure:
    """Return the approved wide transformed-section teaching layout."""

    fig = make_sls_canonical_section_figure(result)

    width = max(1.0, float(result.get("width_mm", 0.0) or 0.0))
    depth = max(1.0, float(result.get("depth_mm", 0.0) or 0.0))
    dn_top = max(
        0.0,
        min(depth, float(result.get("neutral_axis_depth_from_top_mm", 0.0) or 0.0)),
    )
    compression_face = str(result.get("compression_face", "top") or "top").lower()
    layers = tuple(
        layer
        for layer in tuple(result.get("layers", ()) or ())
        if isinstance(layer, Mapping)
        and float(layer.get("area_mm2", 0.0) or 0.0) > 0.0
    )

    # Remove the compact right-hand labels from the base figure. Keep its real
    # section, physical bars, ligature cage, neutral-axis line and area-scaled
    # transformed bands, then rebuild only the teaching annotations.
    fig.layout.annotations = ()

    # Section labels stay inside the beam and away from the transformed-area
    # callout cards.
    if compression_face == "bottom":
        cracked_y0, cracked_y1 = 0.0, dn_top
    else:
        cracked_y0, cracked_y1 = dn_top, depth

    if cracked_y1 - cracked_y0 > 0.12 * depth:
        fig.add_annotation(
            x=0.5 * width,
            y=0.5 * (cracked_y0 + cracked_y1),
            text="Cracked concrete<br>tension inactive",
            showarrow=False,
            align="center",
            font=dict(color="#334155", size=12),
        )

    fig.add_annotation(
        x=1.08 * width,
        y=dn_top,
        text=f"d<sub>n</sub> = {dn_top:.1f} mm",
        showarrow=False,
        xanchor="left",
        font=dict(color="#6d28d9", size=12),
    )
    fig.add_annotation(
        x=0.5 * width,
        y=-0.085 * depth,
        text=f"b = {width:.0f} mm",
        showarrow=False,
        font=dict(color="#0f172a", size=11),
    )
    fig.add_annotation(
        x=-0.12 * width,
        y=0.5 * depth,
        text=f"D = {depth:.0f} mm",
        textangle=-90,
        showarrow=False,
        font=dict(color="#0f172a", size=11),
    )

    # Stack the layer cards down the right side.  Two layers reproduce the
    # approved top/bottom card layout; additional layers still remain readable.
    layer_count = max(1, len(layers))
    if layer_count == 1:
        card_ys = [0.50 * depth]
    else:
        card_ys = [
            depth * (0.23 + idx * (0.54 / max(1, layer_count - 1)))
            for idx in range(layer_count)
        ]

    for idx, (layer, card_y) in enumerate(zip(layers, card_ys), start=1):
        state = str(layer.get("state", "neutral") or "neutral")
        included = bool(layer.get("included", True))
        factor = float(layer.get("transformed_factor", 0.0) or 0.0)
        area = float(layer.get("area_mm2", 0.0) or 0.0)
        equivalent_area = factor * area
        label = str(layer.get("label", layer.get("layer_id", f"Layer {idx}")))
        colour = _CALLOUT_COLOURS.get(state, _CALLOUT_COLOURS["neutral"])
        expression = _transformed_expression(state)

        if included:
            transformed_line = (
                f"<b>{expression} = {factor:.3g} × {area:.1f} = "
                f"{equivalent_area:,.0f} mm²</b>"
            )
        else:
            transformed_line = "Equivalent transformed area: omitted"

        card_text = (
            f"<b>{label} ({state})</b><br><br>"
            f"● Physical steel area: &nbsp;A<sub>s</sub> = {area:.1f} mm²<br>"
            f"▭ Equivalent transformed area:<br>"
            f"{transformed_line}"
        )
        fig.add_annotation(
            x=1.34 * width,
            y=card_y,
            text=card_text,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            align="left",
            font=dict(color=colour, size=11 if layer_count <= 2 else 9.5),
            bgcolor=_CARD_BG.get(state, _CARD_BG["neutral"]),
            bordercolor=colour,
            borderwidth=1.5,
            borderpad=10,
        )

    fig.add_annotation(
        x=0.50 * width,
        y=1.105 * depth,
        text="<i>Translucent dashed band = equivalent transformed steel area</i>",
        showarrow=False,
        align="center",
        font=dict(color="#475569", size=10),
    )
    fig.add_annotation(
        x=-0.02 * width,
        y=-0.17 * depth,
        text="Steel layers replaced by equivalent transformed areas",
        showarrow=False,
        xanchor="left",
        align="left",
        font=dict(color="#475569", size=11),
    )

    fig.update_xaxes(
        range=[-0.22 * width, 2.85 * width],
        visible=False,
        fixedrange=True,
        constrain="domain",
    )
    fig.update_yaxes(
        range=[depth * 1.18, -depth * 0.22],
        visible=False,
        fixedrange=True,
        scaleanchor="x",
        scaleratio=1,
    )
    fig.update_layout(
        height=520,
        margin=dict(l=12, r=12, t=12, b=12),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        showlegend=False,
        dragmode=False,
    )
    return fig


__all__ = ["make_sls_transformed_section_figure"]
