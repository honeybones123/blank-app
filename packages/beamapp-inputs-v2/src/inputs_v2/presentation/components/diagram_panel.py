"""Plotly implementation of the typed input-diagram component."""

import plotly.graph_objects as go

from inputs_v2.presentation.view_models.input_diagram import InputDiagramViewModel


# These values mirror the Runtime diagram contract, while remaining owned by V2.
_CONCRETE_FILL = "rgba(210,216,224,0.30)"
_CONCRETE_OUTLINE = "rgba(30,30,30,1.0)"
_REO_BOTTOM = "rgba(0,90,200,0.95)"
# The current Inputs-page reference renders both reinforcement layers in the
# same blue; retain the distinction in the view model, not by changing colour.
_REO_TOP = "rgba(0,90,200,0.95)"
_LINK_STEEL = "rgba(0,0,0,0.95)"


def build_section_figure(model: InputDiagramViewModel) -> go.Figure:
    fig = go.Figure()
    fig.add_shape(
        type="rect",
        x0=0,
        y0=0,
        x1=model.width_mm,
        y1=model.depth_mm,
        fillcolor=_CONCRETE_FILL,
        line={"color": _CONCRETE_OUTLINE, "width": 2},
        layer="below",
    )
    # The inset rectangle is the shear-link cage. It must disappear when
    # links are switched off; otherwise the diagram falsely shows links.
    # Keep the stirrup cage close to the longitudinal bars, matching the
    # Runtime section convention rather than using a large proportional inset.
    inset = model.cage_inset_mm
    if model.shear_links:
        all_bars = (*model.bars, *model.top_bars)
        left = min(bar.x_mm - bar.diameter_mm / 2.0 for bar in all_bars) - model.shear_diameter_mm / 2.0
        right = max(bar.x_mm + bar.diameter_mm / 2.0 for bar in all_bars) + model.shear_diameter_mm / 2.0
        top = min(bar.y_mm - bar.diameter_mm / 2.0 for bar in all_bars) - model.shear_diameter_mm / 2.0
        bottom = max(bar.y_mm + bar.diameter_mm / 2.0 for bar in all_bars) + model.shear_diameter_mm / 2.0
        fig.add_shape(
            type="rect",
            x0=left, y0=top, x1=right, y1=bottom,
            fillcolor="rgba(0,0,0,0)",
            line={"color": _CONCRETE_OUTLINE, "width": 2},
        )
    for bar in model.bars:
        radius = bar.diameter_mm / 2.0
        fig.add_shape(
            type="circle",
            x0=bar.x_mm - radius,
            y0=bar.y_mm - radius,
            x1=bar.x_mm + radius,
            y1=bar.y_mm + radius,
            fillcolor=_REO_BOTTOM,
            line={"color": _LINK_STEEL, "width": 1},
        )
    for bar in model.top_bars:
        radius = bar.diameter_mm / 2.0
        fig.add_shape(
            type="circle", x0=bar.x_mm - radius, y0=bar.y_mm - radius,
            x1=bar.x_mm + radius, y1=bar.y_mm + radius,
            fillcolor=_REO_TOP, line={"color": _LINK_STEEL, "width": 1},
        )
    if model.shear_links:
        all_bars = (*model.bars, *model.top_bars)
        left = min(bar.x_mm - bar.diameter_mm / 2.0 for bar in all_bars) - model.shear_diameter_mm / 2.0
        right = max(bar.x_mm + bar.diameter_mm / 2.0 for bar in all_bars) + model.shear_diameter_mm / 2.0
        top = min(bar.y_mm - bar.diameter_mm / 2.0 for bar in all_bars) - model.shear_diameter_mm / 2.0
        bottom = max(bar.y_mm + bar.diameter_mm / 2.0 for bar in all_bars) + model.shear_diameter_mm / 2.0
        fig.add_shape(
            type="rect", x0=left, y0=top, x1=right, y1=bottom,
            line={"color": _LINK_STEEL, "width": 2},
            fillcolor="rgba(0,0,0,0)",
        )
    margin = max(40.0, model.width_mm * 0.12)
    fig.update_xaxes(
        range=[-margin, model.width_mm + margin],
        visible=False,
        constrain="domain",
    )
    fig.update_yaxes(
        range=[model.depth_mm + margin, -margin],
        visible=False,
        scaleanchor="x",
        scaleratio=1,
    )
    fig.update_layout(
        height=470,
        margin={"l": 8, "r": 8, "t": 16, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        meta={
            "source_revision": model.source_revision,
            "source_hash": model.source_hash,
            "resolved_bar_count": model.resolved_bar_count,
            "top_bar_count": len(model.top_bars),
            "shear_link_count": len(model.shear_links),
        },
    )
    return fig


def build_3d_figure(model: InputDiagramViewModel) -> go.Figure:
    """Lightweight isometric section view; geometry is projected from the VM."""
    fig = go.Figure()
    w, d, span = model.width_mm, model.depth_mm, model.span_mm
    # Concrete prism: width=x, span=y (into the page), depth=z (vertical).
    for z in (0.0, d):
        fig.add_trace(go.Scatter3d(x=[0, w, w, 0, 0], y=[0, 0, span, span, 0], z=[z]*5,
                                   mode="lines", line={"color": _CONCRETE_OUTLINE, "width": 4}, showlegend=False))
    for x, y in ((0,0),(w,0),(w,span),(0,span)):
        fig.add_trace(go.Scatter3d(x=[x,x], y=[y,y], z=[0,d], mode="lines",
                                   line={"color": _CONCRETE_OUTLINE, "width": 4}, showlegend=False))
    for bar in (*model.bars, *model.top_bars):
        vertical_z = d - bar.y_mm
        fig.add_trace(go.Scatter3d(x=[bar.x_mm, bar.x_mm], y=[0, span], z=[vertical_z, vertical_z], mode="lines",
                                   line={"width": max(4, bar.diameter_mm / 2), "color": "#075fc4"}, showlegend=False))
    fig.update_layout(height=470, margin={"l": 0, "r": 0, "t": 8, "b": 0},
                      paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                      scene={"xaxis": {"visible": False}, "yaxis": {"visible": False}, "zaxis": {"visible": False}, "aspectmode": "data", "camera": {"eye": {"x": 1.6, "y": 1.8, "z": 1.0}}},
                      meta={"source_revision": model.source_revision, "source_hash": model.source_hash})
    return fig


def build_side_figure(model: InputDiagramViewModel) -> go.Figure:
    """Build the longitudinal/elevation projection from the same immutable model.

    This deliberately does not recalculate reinforcement or read widget state:
    the section and side views are two projections of one revision-tagged model.
    """
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, y0=0, x1=model.width_mm * 0.0 + 1.0,
                  y1=model.depth_mm, fillcolor=_CONCRETE_FILL,
                  line={"color": _CONCRETE_OUTLINE, "width": 2})
    for x in model.shear_links:
        fig.add_shape(type="line", x0=x / max(model.depth_mm, 1.0),
                      x1=x / max(model.depth_mm, 1.0), y0=0, y1=model.depth_mm,
                      line={"color": _LINK_STEEL, "width": 2})
    fig.update_xaxes(range=[-0.1, 1.1], visible=False)
    fig.update_yaxes(range=[model.depth_mm, 0], visible=False)
    fig.update_layout(height=220, margin={"l": 8, "r": 8, "t": 8, "b": 8},
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      showlegend=False, meta={"source_revision": model.source_revision,
                                               "source_hash": model.source_hash,
                                               "shear_link_count": len(model.shear_links)})
    return fig
