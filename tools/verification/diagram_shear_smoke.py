"""Smoke checks for extracted shear diagram builders."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shear_diagrams import (  # noqa: E402
    plot_shear_step3_section_params_plotly as legacy_plot_shear_step3_section_params_plotly,
    plot_shear_torsion_section_2d as legacy_plot_shear_torsion_section_2d,
)
from ui.diagrams.shear_diagram import (  # noqa: E402
    build_shear_cross_section_figure_from_layout,
    plot_shear_step3_section_params_plotly,
    plot_shear_torsion_section_2d,
)


def _rect_layout() -> dict:
    return {
        "shape_name": "Rectangle (b x D)",
        "dims": {"b": 450.0, "D": 750.0},
        "reo": {
            "cover_top": 40.0,
            "cover_bot": 50.0,
            "cover_side": 45.0,
            "min_clear_spacing": 20.0,
            "rowgap_top": 60.0,
            "rowgap_bot": 60.0,
            "lig_d": 10.0,
            "lig_legs": 3,
        },
        "reo_layout": {
            "bottom": [{"x": [120.0, 210.0, 300.0, 390.0], "y": 690.0, "db": 20.0}],
            "top": [{"x": [160.0, 290.0], "y": 60.0, "db": 16.0}],
        },
        "reo_points": [
            {"x": 120.0, "y": 690.0, "db": 20.0, "layer": "bottom"},
            {"x": 210.0, "y": 690.0, "db": 20.0, "layer": "bottom"},
            {"x": 300.0, "y": 690.0, "db": 20.0, "layer": "bottom"},
            {"x": 390.0, "y": 690.0, "db": 20.0, "layer": "bottom"},
            {"x": 160.0, "y": 60.0, "db": 16.0, "layer": "top"},
            {"x": 290.0, "y": 60.0, "db": 16.0, "layer": "top"},
        ],
    }


def _figure_signature(fig) -> tuple[int, int, int]:
    shapes = list(fig.layout.shapes or [])
    annotations = list(fig.layout.annotations or [])
    return (len(fig.data), len(shapes), len(annotations))


def _check_torsion_schematic() -> list[str]:
    kwargs = dict(
        shape_name="Rectangle (b x D)",
        dims={"b": 450.0, "D": 750.0},
        reo={
            "cover_top": 40.0,
            "cover_bot": 50.0,
            "cover_side": 45.0,
            "nb_top": 2,
            "db_top": 16.0,
            "nb_bot": 4,
            "db_bot": 20.0,
            "min_clear_spacing": 20.0,
            "rowgap_top": 60.0,
            "rowgap_bot": 60.0,
            "lig_d": 10.0,
            "lig_legs": 3,
        },
        mode="V+T",
    )
    module_fig = plot_shear_torsion_section_2d(**kwargs)
    legacy_fig = legacy_plot_shear_torsion_section_2d(**kwargs)
    annotations = [
        str(getattr(annotation, "text", "") or "")
        for annotation in module_fig.layout.annotations or []
    ]
    failures: list[str] = []
    for expected in ("tau_v", "tau_T", "opposes", "adds", "Section + reinforcement"):
        if not any(expected in text for text in annotations):
            failures.append(f"torsion_annotation_missing_{expected.replace(' ', '_')}")
    if _figure_signature(module_fig) != _figure_signature(legacy_fig):
        failures.append("torsion_legacy_signature_changed")
    if module_fig.layout.xaxis.visible is not False:
        failures.append("torsion_x_axis_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("torsion_y_axis_visible")
    return failures


def _check_step3_section_params() -> list[str]:
    kwargs = dict(
        b_mm=450.0,
        D_mm=750.0,
        bv_mm=420.0,
        dv_mm=690.0,
        Asv_mm2=240.0,
        height=360,
    )
    module_fig = plot_shear_step3_section_params_plotly(**kwargs)
    legacy_fig = legacy_plot_shear_step3_section_params_plotly(**kwargs)
    annotations = [
        str(getattr(annotation, "text", "") or "")
        for annotation in module_fig.layout.annotations or []
    ]
    failures: list[str] = []
    for expected in ("b<sub>v</sub>", "d<sub>v</sub>", "A<sub>sv</sub>"):
        if not any(expected in text for text in annotations):
            failures.append(f"step3_annotation_missing_{expected}")
    if _figure_signature(module_fig) != _figure_signature(legacy_fig):
        failures.append("step3_legacy_signature_changed")
    if int(module_fig.layout.height or 0) != 360:
        failures.append("step3_height_not_preserved")
    if module_fig.layout.xaxis.visible is not False:
        failures.append("step3_x_axis_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("step3_y_axis_visible")
    return failures


def main() -> int:
    fig = build_shear_cross_section_figure_from_layout(
        layout=_rect_layout(),
        height=360,
        top_reo_label="Top reo",
    )
    failures: list[str] = []
    shapes = list(fig.layout.shapes or [])
    annotations = [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]
    circles = [shape for shape in shapes if shape.type == "circle"]
    rects = [shape for shape in shapes if shape.type == "rect"]
    lines = [shape for shape in shapes if shape.type == "line"]

    if len(rects) < 2:
        failures.append("section_or_ligature_rect_missing")
    if len(circles) < 6:
        failures.append(f"longitudinal_reo_overlay_missing_got_{len(circles)}")
    if len(lines) < 1:
        failures.append("internal_ligature_leg_missing")
    for expected in ("b = 450 mm", "D = 750 mm", "Top reo", "Tension reo", "Shear reinforcement"):
        if not any(expected in text for text in annotations):
            failures.append(f"annotation_missing_{expected.replace(' ', '_')}")
    if fig.layout.xaxis.visible is not False:
        failures.append("x_axis_visible")
    if fig.layout.yaxis.visible is not False:
        failures.append("y_axis_visible")
    if fig.layout.yaxis.scaleanchor != "x":
        failures.append("y_axis_not_scaleanchored")
    if int(fig.layout.height or 0) != 360:
        failures.append("height_not_preserved")
    failures.extend(_check_torsion_schematic())
    failures.extend(_check_step3_section_params())

    if failures:
        print("DIAGRAM_SHEAR_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_SHEAR_SMOKE PASS")
    print(f"- shapes: rects={len(rects)}, circles={len(circles)}, lines={len(lines)}")
    print("- annotations and axes verified")
    print("- torsion schematic module builder and legacy wrapper verified")
    print("- Step 3 section-parameter module builder and legacy wrapper verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
