from __future__ import annotations

from design_page_runtime import plot_load_diagram_plotly
from ui.diagrams.moment_shear_diagram import (
    figure_bmd_from_state,
    figure_sfd_from_state,
)


def test_load_sfd_and_bmd_use_the_same_horizontal_plot_grid() -> None:
    length_m = 2.0
    section_x_m = 1.0
    x_values = [0.0, section_x_m, length_m]

    load_figure = plot_load_diagram_plotly(
        "Simple beam – UDL over entire span",
        length_m,
        {"w": 0.0},
        preview_x_m=section_x_m,
        support_condition="Simply supported",
    )
    plot_state = {
        "x_plot": x_values,
        "V_plot": [0.0, 0.0, 0.0],
        "M_plot": [0.0, 0.0, 0.0],
        "support_positions_plot": [0.0, length_m],
        "support_types_plot": ["pinned", "roller"],
        "L": length_m,
        "preview_x_m": section_x_m,
        "design_x_m": None,
        "preview_V": 0.0,
        "preview_M": 0.0,
        "x_pad": 0.16,
        "support_type": "simply_supported",
        "design_mode_active": False,
        "zone_limit_m": 0.0,
    }
    figures = [
        load_figure,
        figure_sfd_from_state(plot_state),
        figure_bmd_from_state(plot_state),
    ]

    assert {tuple(figure.layout.xaxis.domain) for figure in figures} == {
        (0.0, 1.0)
    }
    assert len({tuple(figure.layout.xaxis.range) for figure in figures}) == 1
    assert {figure.layout.margin.l for figure in figures} == {72}
    assert {figure.layout.margin.r for figure in figures} == {16}

