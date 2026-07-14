"""Smoke checks for the extracted deflection diagram builder."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.diagrams.deflection_diagram import (  # noqa: E402
    build_deflected_shape_figure,
    deflected_longitudinal_profile_mm,
)
from ui.diagrams.diagram_styles import (  # noqa: E402
    CONCRETE_FILL_2D,
    DEFLECTED_LINE,
    DEFLECTION_VISUAL_TARGET_DEPTH_RATIO,
    DEFLECTION_VISUAL_TARGET_MIN_MM,
    DIAGRAM_SIZE_LONGITUDINAL,
    DIAGRAM_TRANSPARENT,
    REO_BOTTOM,
    REO_TOP,
    diagram_deflection_visual_scale_factor,
)


def _ascii_safe(value) -> str:
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def _axis_title_text(axis) -> str:
    title = getattr(axis, "title", None)
    return str(getattr(title, "text", "") or "")


def _mm_per_pixel_ratio(fig) -> float:
    margin = fig.layout.margin
    plot_w = float(fig.layout.width - int(margin.l or 0) - int(margin.r or 0))
    plot_h = float(fig.layout.height - int(margin.t or 0) - int(margin.b or 0))
    x_range = tuple(fig.layout.xaxis.range or ())
    y_range = tuple(fig.layout.yaxis.range or ())
    x_mm_per_px = (float(x_range[1]) - float(x_range[0])) / plot_w
    y_mm_per_px = (float(y_range[1]) - float(y_range[0])) / plot_h
    return y_mm_per_px / x_mm_per_px


def _trace_named(fig, name: str):
    for trace in fig.data:
        if str(getattr(trace, "name", "") or "") == name:
            return trace
    return None


def main() -> int:
    x_mm, w_mm = deflected_longitudinal_profile_mm(
        L_mm=6000.0,
        support_type="Simply supported",
        delta_total=24.0,
        n_pts=80,
    )
    fig = build_deflected_shape_figure(
        x_mm=x_mm,
        w_mm=w_mm,
        L_mm=6000.0,
        D_mm=750.0,
        support_type="Simply supported",
        reo_layers={
            "bottom": [{"count": 4, "db": 20.0, "y_from_top_mm": 690.0}],
            "top": [{"count": 2, "db": 16.0, "y_from_top_mm": 60.0}],
        },
    )

    trace_names = [str(getattr(trace, "name", "") or "") for trace in fig.data]
    failures: list[str] = []

    if fig is None:
        failures.append("figure_missing")
    if not any(name == "Undeformed beam" for name in trace_names):
        failures.append("undeformed_beam_trace_missing")
    if not any(name == "Deflected beam" for name in trace_names):
        failures.append("deflected_beam_trace_missing")
    if not any(name == "Deflection (hover)" for name in trace_names):
        failures.append("hover_trace_missing")
    if not any(name.startswith("Max |") for name in trace_names):
        failures.append("max_marker_trace_missing")
    if not any(name == "Bottom reo" for name in trace_names):
        failures.append("bottom_reo_trace_missing")
    if not any(name == "Top reo" for name in trace_names):
        failures.append("top_reo_trace_missing")
    trace_colours = [str(getattr(getattr(trace, "line", None), "color", "") or "") for trace in fig.data]
    if REO_BOTTOM not in trace_colours:
        failures.append("bottom_reo_colour_not_shared")
    if REO_TOP not in trace_colours:
        failures.append("top_reo_colour_not_shared")
    if CONCRETE_FILL_2D not in [str(getattr(trace, "fillcolor", "") or "") for trace in fig.data]:
        failures.append("deflected_beam_body_not_concrete_coloured")
    if DEFLECTED_LINE not in trace_colours:
        failures.append("deflection_cue_line_missing")
    annotation_texts = [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]
    if "Bottom reo" in annotation_texts:
        failures.append("bottom_reo_label_should_not_render")
    if "Top reo" in annotation_texts:
        failures.append("top_reo_label_should_not_render")
    if len(fig.layout.shapes or ()) < 3:
        failures.append("support_shapes_missing")
    if str(fig.layout.title.text or ""):
        failures.append("title_should_not_render")
    if int(fig.layout.width or 0) != DIAGRAM_SIZE_LONGITUDINAL["width"]:
        failures.append("width_not_longitudinal_contract")
    if int(fig.layout.height or 0) != DIAGRAM_SIZE_LONGITUDINAL["height"]:
        failures.append("height_not_longitudinal_contract")
    if fig.layout.xaxis.showgrid is not False:
        failures.append("x_grid_not_disabled")
    if fig.layout.yaxis.showgrid is not False:
        failures.append("y_grid_not_disabled")
    if fig.layout.xaxis.visible is not False:
        failures.append("x_axis_frame_visible")
    if fig.layout.yaxis.visible is not False:
        failures.append("y_axis_frame_visible")
    if fig.layout.xaxis.showticklabels is not False:
        failures.append("x_tick_labels_not_disabled")
    if fig.layout.yaxis.showticklabels is not False:
        failures.append("y_tick_labels_not_disabled")
    if _axis_title_text(fig.layout.xaxis) != "":
        failures.append("x_axis_title_not_blank")
    if _axis_title_text(fig.layout.yaxis) != "":
        failures.append("y_axis_title_not_blank")
    if getattr(fig.layout.yaxis, "scaleanchor", None) != "x":
        failures.append("y_axis_not_scaleanchored_to_x")
    if float(getattr(fig.layout.yaxis, "scaleratio", 0.0) or 0.0) != 1.0:
        failures.append("y_axis_scaleratio_not_one")
    if any(text.startswith("Span L =") for text in annotation_texts):
        failures.append("span_marker_label_should_not_render")
    if any(text.startswith("Depth D =") for text in annotation_texts):
        failures.append("depth_marker_label_should_not_render")
    if tuple(fig.layout.xaxis.range or ()) != (-180.0, 6180.0):
        failures.append("span_range_not_tied_to_length")
    y_range = tuple(fig.layout.yaxis.range or ())
    if not y_range or float(y_range[0]) > -1.24 * 750.0:
        failures.append("support_glyphs_cropped_from_viewport")
    if abs(_mm_per_pixel_ratio(fig) - 1.0) > 0.02:
        failures.append("deflection_viewport_not_to_scale")

    x_extreme, w_extreme = deflected_longitudinal_profile_mm(
        L_mm=6000.0,
        support_type="Simply supported",
        delta_total=900.0,
        n_pts=80,
    )
    extreme_fig = build_deflected_shape_figure(
        x_mm=x_extreme,
        w_mm=w_extreme,
        L_mm=6000.0,
        D_mm=750.0,
        support_type="Simply supported",
    )
    expected_visual_drop = max(
        DEFLECTION_VISUAL_TARGET_DEPTH_RATIO * 750.0,
        DEFLECTION_VISUAL_TARGET_MIN_MM,
    )
    extreme_scale = diagram_deflection_visual_scale_factor(900.0, 750.0)
    if not (0.0 < extreme_scale < 1.0):
        failures.append("extreme_deflection_scale_should_downscale")
    hover_trace = _trace_named(extreme_fig, "Deflection (hover)")
    if hover_trace is None:
        failures.append("extreme_deflection_hover_trace_missing")
    else:
        visual_drop = max(abs(float(y)) for y in hover_trace.y)
        if abs(visual_drop - expected_visual_drop) > 1.0:
            failures.append("extreme_deflection_visual_drop_not_normalised")

    zero_fig = build_deflected_shape_figure(
        x_mm=x_mm,
        w_mm=[0.0 for _ in x_mm],
        L_mm=6000.0,
        D_mm=750.0,
        support_type="Simply supported",
        reo_layers={
            "bottom": [{"count": 4, "db": 20.0, "y_from_top_mm": 690.0}],
            "top": [{"count": 2, "db": 16.0, "y_from_top_mm": 60.0}],
        },
    )
    zero_trace_names = [str(getattr(trace, "name", "") or "") for trace in zero_fig.data]
    zero_trace_colours = [str(getattr(getattr(trace, "line", None), "color", "") or "") for trace in zero_fig.data]
    if any(name.startswith("Max |") for name in zero_trace_names):
        failures.append("zero_deflection_max_marker_should_not_render")
    if DEFLECTED_LINE in zero_trace_colours:
        failures.append("zero_deflection_visible_cue_should_not_render")
    if DIAGRAM_TRANSPARENT not in zero_trace_colours:
        failures.append("zero_deflection_hover_trace_not_transparent")

    x_8m, w_8m = deflected_longitudinal_profile_mm(
        L_mm=8000.0,
        support_type="Simply supported",
        delta_total=0.0,
        n_pts=80,
    )
    fig_8m = build_deflected_shape_figure(
        x_mm=x_8m,
        w_mm=w_8m,
        L_mm=8000.0,
        D_mm=750.0,
        support_type="Simply supported",
    )
    if tuple(fig_8m.layout.xaxis.range or ()) != (-240.0, 8240.0):
        failures.append("span_range_does_not_update")
    if abs(_mm_per_pixel_ratio(fig_8m) - 1.0) > 0.02:
        failures.append("deflection_8m_viewport_not_to_scale")

    fig_shallow = build_deflected_shape_figure(
        x_mm=x_mm,
        w_mm=w_mm,
        L_mm=6000.0,
        D_mm=450.0,
        support_type="Simply supported",
    )
    if tuple(fig.layout.yaxis.range or ()) == tuple(fig_shallow.layout.yaxis.range or ()):
        failures.append("depth_range_does_not_update")
    if abs(_mm_per_pixel_ratio(fig_shallow) - 1.0) > 0.02:
        failures.append("deflection_shallow_viewport_not_to_scale")

    x_cant, w_cant = deflected_longitudinal_profile_mm(
        L_mm=6000.0,
        support_type="Cantilever",
        delta_total=24.0,
        n_pts=80,
    )
    fig_cant = build_deflected_shape_figure(
        x_mm=x_cant,
        w_mm=w_cant,
        L_mm=6000.0,
        D_mm=750.0,
        support_type="Cantilever",
    )
    fixed_walls = [
        shape for shape in (fig_cant.layout.shapes or ())
        if getattr(shape, "type", "") == "line"
        and float(getattr(shape, "x0", 999.0)) == 0.0
        and float(getattr(shape, "x1", 999.0)) == 0.0
        and abs(float(getattr(shape, "y0", 0.0)) + 1162.5) < 1e-6
        and abs(float(getattr(shape, "y1", 0.0)) - 412.5) < 1e-6
    ]
    if not fixed_walls:
        failures.append("cantilever_fixed_support_not_centred_on_beam")
    cant_y_range = tuple(fig_cant.layout.yaxis.range or ())
    if not cant_y_range or float(cant_y_range[0]) > -1162.5 or float(cant_y_range[1]) < 412.5:
        failures.append("cantilever_fixed_support_cropped_from_viewport")

    if failures:
        print("DIAGRAM_DEFLECTION_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_DEFLECTION_SMOKE PASS")
    print(f"- traces: {_ascii_safe(trace_names)}")
    print(f"- support_shapes: {len(fig.layout.shapes or ())}")
    print("- axes: grids off, tick labels off, titles blank")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
