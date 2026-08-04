"""Smoke checks for extracted section diagram builders."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import plotly.graph_objects as go  # noqa: E402

from ui.diagrams.section_diagram import build_summary_cross_section_result  # noqa: E402


def _failures_for_rect() -> list[str]:
    layout = {
        "shape_name": "Rectangle (b x D)",
        "dims": {"b": 450.0, "D": 750.0},
        "reo": {
            "cover_side": 45.0,
            "cover_top": 40.0,
            "cover_bot": 50.0,
            "lig_d": 10.0,
            "lig_legs": 3,
        },
        "reo_layout": {
            "bottom": [{"x": [120.0, 210.0, 300.0, 390.0], "y": 690.0, "db": 20.0}],
            "top": [{"x": [160.0, 290.0], "y": 60.0, "db": 16.0}],
        },
    }
    result = build_summary_cross_section_result(layout=layout)
    fig = result.figure
    failures: list[str] = []
    if fig is None:
        return ["rect_figure_missing"]
    shapes = list(fig.layout.shapes or [])
    rects = [shape for shape in shapes if shape.type == "rect"]
    circles = [shape for shape in shapes if shape.type == "circle"]
    lines = [shape for shape in shapes if shape.type == "line"]
    if len(rects) < 2:
        failures.append("rect_outline_or_ligature_missing")
    if len(circles) != 6:
        failures.append(f"rect_expected_6_bar_circles_got_{len(circles)}")
    if len(lines) < 1:
        failures.append("rect_internal_ligature_leg_missing")
    if fig.layout.xaxis.showgrid is not False:
        failures.append("rect_x_grid_not_disabled")
    if fig.layout.yaxis.showgrid is not False:
        failures.append("rect_y_grid_not_disabled")
    if fig.layout.yaxis.scaleanchor != "x":
        failures.append("rect_y_axis_not_scaleanchored")
    return failures


def _fake_t_section_builder(**_kwargs):
    fig = go.Figure()
    fig.add_shape(
        type="path",
        path="M 0,0 L 900,0 L 900,150 L 550,150 L 550,750 L 350,750 L 350,150 L 0,150 Z",
        line=dict(width=1.2, color="black"),
        fillcolor="rgba(0,0,0,0)",
    )
    return fig


def _failures_for_t_section_dimensions() -> list[str]:
    layout = {
        "shape_name": "T-Section",
        "dims": {"bf": 900.0, "tf": 150.0, "bw": 200.0, "D": 750.0},
        "reo": {"cover_side": 45.0, "cover_top": 40.0, "cover_bot": 50.0},
    }
    result = build_summary_cross_section_result(
        layout=layout,
        section_figure_builder=_fake_t_section_builder,
    )
    fig = result.figure
    failures: list[str] = []
    if fig is None:
        return ["t_section_figure_missing"]
    annotation_text = [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]
    expected_fragments = [
        "bf = 900 mm",
        "D = 750 mm",
        "tf = 150 mm",
        "bw = 200 mm",
        "cover(top/bot/side) = 40/50/45 mm",
    ]
    for fragment in expected_fragments:
        if not any(fragment in text for text in annotation_text):
            failures.append(f"t_section_annotation_missing_{fragment.replace(' ', '_')}")
    if fig.layout.xaxis.showgrid is not False:
        failures.append("t_section_x_grid_not_disabled")
    if fig.layout.yaxis.showgrid is not False:
        failures.append("t_section_y_grid_not_disabled")
    return failures


def main() -> int:
    failures = []
    failures.extend(_failures_for_rect())
    failures.extend(_failures_for_t_section_dimensions())
    if failures:
        print("DIAGRAM_SECTION_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("DIAGRAM_SECTION_SMOKE PASS")
    print("- rectangle outline, bars, ligature, and axes verified")
    print("- T-section dimension and cover annotations verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
