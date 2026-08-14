from __future__ import annotations

import pytest

from section_props.plotly_section import make_sectionA_figure


def _reo() -> dict:
    return {
        "cover_side": 40.0,
        "cover_top": 40.0,
        "cover_bot": 40.0,
        "min_clear_spacing": 25.0,
        "rowgap_top": 40.0,
        "rowgap_bot": 40.0,
        "lig_d": 0.0,
        "lig_legs": 0,
        "top_rows": [
            {"active": True, "mode": "Count", "bars": 2, "dia": 10.0, "row_index": 1}
        ],
        "bottom_rows": [
            {"active": True, "mode": "Count", "bars": 3, "dia": 20.0, "row_index": 1}
        ],
    }


@pytest.mark.parametrize(
    ("shape", "dims"),
    [
        ("T", {"bf": 600.0, "tf": 120.0, "bw": 300.0, "D": 475.0}),
        ("I", {"bf": 600.0, "tf": 120.0, "tw": 300.0, "D": 475.0}),
    ],
)
def test_flanged_longitudinal_bars_use_beam_face_colours(shape: str, dims: dict) -> None:
    figure = make_sectionA_figure(
        shape_name=shape,
        dims=dims,
        reo=_reo(),
        show_shear=True,
    )

    bar_colours = [
        item.fillcolor
        for item in figure.layout.shapes
        if item.type == "circle"
    ]

    assert bar_colours.count("#d62728") == 2
    assert bar_colours.count("#1f77b4") == 3
