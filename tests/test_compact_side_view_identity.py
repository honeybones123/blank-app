from __future__ import annotations

import plotly.graph_objects as go

from widgets_helpers import compact_side_view_figure


def test_compact_side_view_assigns_stable_plotly_identity() -> None:
    figure = go.Figure(
        data=[
            go.Scatter(x=[0.0, 1.0], y=[0.0, 1.0]),
            go.Scatter(x=[0.0, 1.0], y=[1.0, 0.0]),
        ]
    )

    result = compact_side_view_figure(figure)

    assert [trace.uid for trace in result.data] == [
        "compact-side-view-0",
        "compact-side-view-1",
    ]
    assert result.layout.uirevision == "compact-side-view-v1"

