"""Smoke checks for extracted side-view diagram primitives."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import streamlit as st


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.diagrams import side_view_diagram  # noqa: E402
from ui.diagrams.diagram_styles import (  # noqa: E402
    REO_BOTTOM,
    REO_TOP,
    SUPPORT_PIN_MIN_WIDTH_MM,
    SUPPORT_PIN_DEPTH_BEAM_RATIO,
    SUPPORT_PIN_WIDTH_SPAN_RATIO,
    SUPPORT_ROLLER_RADIUS_BEAM_RATIO,
)


def _figure_signature(fig) -> tuple[int, int, int]:
    return (
        len(fig.data),
        len(fig.layout.shapes or []),
        len(fig.layout.annotations or []),
    )


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def _trace_hovertext(fig) -> list[list[str]]:
    out: list[list[str]] = []
    for trace in fig.data:
        hover = getattr(trace, "hovertext", None)
        if hover is None:
            out.append([])
        elif isinstance(hover, str):
            out.append([hover])
        else:
            out.append([str(item) for item in hover])
    return out


def _base_model() -> dict:
    return {
        "total_length_m": 8.0,
        "span_m": 8.0,
        "D_m": 0.6,
        "support_condition": "simply_supported",
        "support_positions": [0.0, 8.0],
        "section_layout": {"dims": {"b": 450.0, "D": 600.0}},
    }


def _check_shared_import_identity() -> list[str]:
    failures: list[str] = []
    import bending_side_view_diagram  # noqa: WPS433
    import creep  # noqa: WPS433
    import crack_side_view_diagram  # noqa: WPS433
    import shear_visuals  # noqa: WPS433
    from ui.diagrams import bending_side_view_diagram as bending_side_view_impl  # noqa: WPS433
    from ui.diagrams import crack_side_view_diagram as crack_side_view_impl  # noqa: WPS433

    expected = side_view_diagram.build_side_view_figure
    if shear_visuals._build_side_view_figure is not expected:
        failures.append("shear_visuals_not_using_shared_side_view_builder")
    if bending_side_view_diagram._build_side_view_figure is not expected:
        failures.append("bending_side_view_not_using_shared_side_view_builder")
    if crack_side_view_diagram._build_side_view_figure is not expected:
        failures.append("crack_side_view_not_using_shared_side_view_builder")
    if shear_visuals._build_side_view_support_shapes is not side_view_diagram.build_side_view_support_shapes:
        failures.append("shear_visuals_not_using_shared_support_shapes")
    if shear_visuals._add_side_view_break_marks is not side_view_diagram.add_side_view_break_marks:
        failures.append("shear_visuals_not_using_shared_break_marks")
    if shear_visuals.SIDE_VIEW_VISUAL_HEIGHT != side_view_diagram.SIDE_VIEW_VISUAL_HEIGHT:
        failures.append("shear_visuals_side_view_height_not_delegated")
    if shear_visuals._build_side_view_tension_reo is side_view_diagram.build_side_view_tension_reo:
        failures.append("shear_visuals_tension_reo_wrapper_not_preserved")
    if shear_visuals._add_section_marker is side_view_diagram.add_section_marker:
        failures.append("shear_visuals_section_marker_wrapper_not_preserved")
    if bending_side_view_diagram.build_bending_side_view_figure is not bending_side_view_impl.build_bending_side_view_figure:
        failures.append("bending_side_view_builder_not_delegated_to_ui_diagrams")
    if bending_side_view_diagram.build_creep_side_view_figures is not bending_side_view_impl.build_creep_side_view_figures:
        failures.append("creep_side_view_builder_not_delegated_to_ui_diagrams")
    if creep.build_creep_side_view_figures is not bending_side_view_impl.build_creep_side_view_figures:
        failures.append("creep_page_not_using_shared_side_view_builder")
    if hasattr(bending_side_view_impl, "render_bending_side_view_diagram"):
        failures.append("bending_side_view_render_wrapper_moved_into_ui_diagrams")
    if crack_side_view_diagram.build_crack_side_view_figure is not crack_side_view_impl.build_crack_side_view_figure:
        failures.append("crack_side_view_builder_not_delegated_to_ui_diagrams")
    if crack_side_view_diagram.build_crack_moment_diagram_figure is not crack_side_view_impl.build_crack_moment_diagram_figure:
        failures.append("crack_moment_builder_not_delegated_to_ui_diagrams")
    if hasattr(crack_side_view_impl, "render_crack_side_view_diagram"):
        failures.append("crack_side_view_render_wrapper_moved_into_ui_diagrams")
    if hasattr(crack_side_view_impl, "render_crack_moment_tab_plotly"):
        failures.append("crack_moment_render_wrapper_moved_into_ui_diagrams")
    bending_side_view_source = (ROOT / "ui" / "diagrams" / "bending_side_view_diagram.py").read_text(encoding="utf-8")
    if "from crack_side_view_diagram import" in bending_side_view_source:
        failures.append("bending_side_view_imports_crack_legacy_wrapper")
    return failures


def _check_side_view_load_builder() -> list[str]:
    failures: list[str] = []
    import shear_visuals  # noqa: WPS433

    cases = [
        shear_visuals._DEFAULT_LOADING_CASE,
        "Simple beam – point load at centre",
    ]
    for idx, case in enumerate(cases):
        model = _base_model()
        model.update(
            {
                "case": case,
                "mode": "ULS",
                "w_value": 22.5,
                "point_value": 125.0,
                "a_m": 2.4,
                "a_udl_m": 3.0,
                "a_cant_m": 2.0,
            }
        )
        model["side_view_display"] = side_view_diagram.side_view_display_state(model)
        shared_fig = side_view_diagram.build_side_view_figure(
            length_m=float(model["side_view_display"]["display_length_m"]),
            beam_depth_m=model["D_m"],
            height=260,
            support_condition=model["support_condition"],
        )
        wrapper_fig = side_view_diagram.build_side_view_figure(
            length_m=float(model["side_view_display"]["display_length_m"]),
            beam_depth_m=model["D_m"],
            height=260,
            support_condition=model["support_condition"],
        )
        side_view_diagram.build_side_view_load_shapes(shared_fig, model, show_labels=True)
        shear_visuals._build_side_view_load_shapes(wrapper_fig, model, show_labels=True)
        if _figure_signature(shared_fig) != _figure_signature(wrapper_fig):
            failures.append(f"side_view_load_signature_changed_{idx}")
        if _annotation_text(shared_fig) != _annotation_text(wrapper_fig):
            failures.append(f"side_view_load_annotations_changed_{idx}")
        if case == shear_visuals._DEFAULT_LOADING_CASE and not any("w*" in text for text in _annotation_text(shared_fig)):
            failures.append("side_view_udl_label_missing")
        if "point load" in case and not any("P*" in text for text in _annotation_text(shared_fig)):
            failures.append("side_view_point_label_missing")
    return failures


def _check_break_marks_builder() -> list[str]:
    failures: list[str] = []
    import shear_visuals  # noqa: WPS433

    model = _base_model()
    model["side_view_display"] = side_view_diagram.side_view_display_state(model)

    shared_fig = side_view_diagram.build_side_view_figure(
        length_m=float(model["side_view_display"]["display_length_m"]),
        beam_depth_m=model["D_m"],
        height=260,
        support_condition=model["support_condition"],
    )
    legacy_fig = side_view_diagram.build_side_view_figure(
        length_m=float(model["side_view_display"]["display_length_m"]),
        beam_depth_m=model["D_m"],
        height=260,
        support_condition=model["support_condition"],
    )
    side_view_diagram.add_side_view_break_marks(shared_fig, model)
    shear_visuals._add_side_view_break_marks(legacy_fig, model)

    if _figure_signature(shared_fig) != _figure_signature(legacy_fig):
        failures.append("legacy_break_marks_signature_changed")
    shared_shapes = list(shared_fig.layout.shapes or [])
    legacy_shapes = list(legacy_fig.layout.shapes or [])
    if len(shared_shapes) != 8:
        failures.append("shared_break_marks_shape_count_changed")
    if [shape.line.width for shape in shared_shapes] != [shape.line.width for shape in legacy_shapes]:
        failures.append("legacy_break_marks_line_widths_changed")
    if [shape.line.color for shape in shared_shapes] != [shape.line.color for shape in legacy_shapes]:
        failures.append("legacy_break_marks_line_colors_changed")
    return failures


def _check_tension_reo_builder() -> list[str]:
    failures: list[str] = []
    import shear_visuals  # noqa: WPS433

    model = _base_model()
    model["bottom_layers"] = [{"db": 20.0}, {"db": 16.0}]
    model["top_layers"] = [{"db": 12.0}]
    model["side_view_display"] = side_view_diagram.side_view_display_state(model)

    shared_fig = side_view_diagram.build_side_view_figure(
        length_m=float(model["side_view_display"]["display_length_m"]),
        beam_depth_m=model["D_m"],
        height=260,
        support_condition=model["support_condition"],
    )
    wrapper_fig = side_view_diagram.build_side_view_figure(
        length_m=float(model["side_view_display"]["display_length_m"]),
        beam_depth_m=model["D_m"],
        height=260,
        support_condition=model["support_condition"],
    )
    side_view_diagram.build_side_view_tension_reo(shared_fig, model)
    shear_visuals._build_side_view_tension_reo(wrapper_fig, model)

    shared_annotations = [str(getattr(annotation, "text", "") or "") for annotation in shared_fig.layout.annotations or []]
    wrapper_annotations = [str(getattr(annotation, "text", "") or "") for annotation in wrapper_fig.layout.annotations or []]
    if len(shared_fig.data) != 3:
        failures.append("shared_tension_reo_trace_count_changed")
    if len(wrapper_fig.data) != len(shared_fig.data):
        failures.append("legacy_tension_reo_trace_count_changed")
    if "Tension reo" not in shared_annotations:
        failures.append("shared_tension_reo_label_missing")
    if wrapper_annotations != shared_annotations:
        failures.append("legacy_tension_reo_annotations_changed")
    if [trace.line.width for trace in wrapper_fig.data] != [trace.line.width for trace in shared_fig.data]:
        failures.append("legacy_tension_reo_trace_widths_changed")
    return failures


def _check_section_marker_builder() -> list[str]:
    failures: list[str] = []
    import shear_visuals  # noqa: WPS433

    model = _base_model()
    model["section_x_m"] = 2.75
    model["side_view_display"] = side_view_diagram.side_view_display_state(model)

    shared_fig = side_view_diagram.build_side_view_figure(
        length_m=float(model["side_view_display"]["display_length_m"]),
        beam_depth_m=model["D_m"],
        height=260,
        support_condition=model["support_condition"],
    )
    wrapper_fig = side_view_diagram.build_side_view_figure(
        length_m=float(model["side_view_display"]["display_length_m"]),
        beam_depth_m=model["D_m"],
        height=260,
        support_condition=model["support_condition"],
    )
    side_view_diagram.add_section_marker(shared_fig, model)
    shear_visuals._add_section_marker(wrapper_fig, model)

    if _figure_signature(wrapper_fig) != _figure_signature(shared_fig):
        failures.append("legacy_section_marker_signature_changed")
    if _annotation_text(wrapper_fig) != _annotation_text(shared_fig):
        failures.append("legacy_section_marker_annotations_changed")
    marker_shapes = list(shared_fig.layout.shapes or [])
    if len(marker_shapes) != 1:
        failures.append("shared_section_marker_shape_count_changed")
    elif marker_shapes[0].line.dash != "dash":
        failures.append("shared_section_marker_dash_changed")
    if _annotation_text(shared_fig) != ["Section"]:
        failures.append("shared_section_marker_label_missing")
    return failures


def _check_stirrup_marker_builder() -> list[str]:
    failures: list[str] = []
    import shear_visuals  # noqa: WPS433

    model = _base_model()
    model.update(
        {
            "spacing_mm": 200.0,
            "lig_legs": 2,
        }
    )
    model["side_view_display"] = side_view_diagram.side_view_display_state(model)

    cases = [
        {
            "name": "provided",
            "session": {
                "lig_legs": 2,
                "lig_d": 10.0,
                "shear_zone_enabled": False,
                "shear_auto_design": False,
                "s_lig": 200.0,
                "shear_zone_results": None,
            },
        },
        {
            "name": "zoned",
            "session": {
                "lig_legs": 2,
                "lig_d": 10.0,
                "shear_zone_enabled": True,
                "shear_auto_design": True,
                "s_lig": 200.0,
                "shear_zone_results": {
                    "beam_length_mm": 8000.0,
                    "shear_mid_spacing_calc_mm": 180.0,
                    "shear_spacing_end_mm": 120.0,
                    "zones": [
                        {"start": 0.0, "end": 1.6, "spacing": 0.12, "label": "End zone", "fillcolor": None},
                        {"start": 1.6, "end": 6.4, "spacing": 0.18, "label": "Mid zone", "fillcolor": None},
                        {"start": 6.4, "end": 8.0, "spacing": 0.12, "label": "End zone", "fillcolor": None},
                    ],
                },
            },
        },
    ]
    for case in cases:
        for key, value in case["session"].items():
            st.session_state[key] = value
        shared_fig = side_view_diagram.build_side_view_figure(
            length_m=float(model["side_view_display"]["display_length_m"]),
            beam_depth_m=model["D_m"],
            height=260,
            support_condition=model["support_condition"],
        )
        wrapper_fig = side_view_diagram.build_side_view_figure(
            length_m=float(model["side_view_display"]["display_length_m"]),
            beam_depth_m=model["D_m"],
            height=260,
            support_condition=model["support_condition"],
        )
        side_view_diagram.build_stirrup_markers(shared_fig, model)
        shear_visuals._build_stirrup_markers(wrapper_fig, model)
        suffix = str(case["name"])
        if _figure_signature(shared_fig) != _figure_signature(wrapper_fig):
            failures.append(f"stirrup_marker_signature_changed_{suffix}")
        if _annotation_text(shared_fig) != _annotation_text(wrapper_fig):
            failures.append(f"stirrup_marker_annotations_changed_{suffix}")
        if _trace_hovertext(shared_fig) != _trace_hovertext(wrapper_fig):
            failures.append(f"stirrup_marker_hovertext_changed_{suffix}")
        if suffix == "provided" and not any("Provided spacing" in text for text in _annotation_text(shared_fig)):
            failures.append("provided_stirrup_label_missing")
        if suffix == "zoned" and not any("required" in text.lower() for text in _annotation_text(shared_fig)):
            failures.append("zoned_stirrup_label_missing")
    return failures


def _check_creep_reo_overlay_preserves_reo_identity() -> list[str]:
    failures: list[str] = []
    from ui.diagrams import bending_side_view_diagram as bending_side_view_impl  # noqa: WPS433

    model = _base_model()
    model["bottom_layers"] = [{"db": 20.0, "y": 550.0}]
    model["top_layers"] = [{"db": 16.0, "y": 55.0}]
    model["side_view_display"] = side_view_diagram.side_view_display_state(model)
    fig = side_view_diagram.build_side_view_figure(
        length_m=float(model["side_view_display"]["display_length_m"]),
        beam_depth_m=model["D_m"],
        height=260,
        support_condition=model["support_condition"],
    )
    x_m = np.linspace(0.0, 8.0, 9)
    defl = {
        "work": model["side_view_display"],
        "L_m": 8.0,
        "D_m": 0.6,
        "D_mm": 600.0,
        "x_m": x_m,
        "w_m": -0.035 * (4.0 * (x_m / 8.0) * (1.0 - x_m / 8.0)),
    }
    bending_side_view_impl._add_creep_secondary_reo(fig, model=model, defl=defl)

    trace_colours = [str(getattr(getattr(trace, "line", None), "color", "") or "") for trace in fig.data]
    annotations = _annotation_text(fig)
    if REO_BOTTOM not in trace_colours:
        failures.append("creep_bottom_reo_colour_not_preserved")
    if REO_TOP not in trace_colours:
        failures.append("creep_top_reo_colour_not_preserved")
    if "Tension reo" not in annotations:
        failures.append("creep_tension_reo_label_missing")
    if not any("Top" in text or "top" in text for text in annotations):
        failures.append("creep_top_reo_label_missing")
    return failures


def _check_support_proportions_match_deflection_contract() -> list[str]:
    failures: list[str] = []
    model = _base_model()
    model["side_view_display"] = side_view_diagram.side_view_display_state(model)
    display_length = float(model["side_view_display"]["display_length_m"])
    beam_depth = float(model["D_m"])
    fig = side_view_diagram.build_side_view_figure(
        length_m=display_length,
        beam_depth_m=beam_depth,
        height=260,
        support_condition=model["support_condition"],
    )
    side_view_diagram.build_side_view_support_shapes(fig, model)
    support_paths = [shape for shape in (fig.layout.shapes or []) if getattr(shape, "type", "") == "path"]
    if not support_paths:
        return ["side_view_support_contract_path_missing"]
    path = str(getattr(support_paths[0], "path", "") or "")
    expected_half_width = max(display_length * SUPPORT_PIN_WIDTH_SPAN_RATIO, SUPPORT_PIN_MIN_WIDTH_MM / 1000.0)
    expected_depth = beam_depth * SUPPORT_PIN_DEPTH_BEAM_RATIO
    if f"{-expected_half_width}" not in path or f"{expected_half_width}" not in path:
        failures.append("side_view_support_width_not_deflection_contract")
    if f"{-expected_depth}" not in path:
        failures.append("side_view_support_depth_not_deflection_contract")
    rollers = [shape for shape in (fig.layout.shapes or []) if getattr(shape, "type", "") == "circle"]
    if not rollers:
        failures.append("side_view_roller_contract_shape_missing")
    else:
        roller = rollers[0]
        radius = (float(roller.x1) - float(roller.x0)) / 2.0
        if abs(radius - beam_depth * SUPPORT_ROLLER_RADIUS_BEAM_RATIO) > 1e-9:
            failures.append("side_view_roller_radius_not_deflection_contract")
    return failures


def main() -> int:
    failures: list[str] = []

    model = _base_model()
    display_state = side_view_diagram.side_view_display_state(model)
    if not display_state.get("use_break"):
        failures.append("long_side_view_break_not_enabled")
    model["side_view_display"] = display_state

    x_mid = side_view_diagram.side_view_display_x(4.0, model)
    if not (display_state["break_left_display_m"] <= x_mid <= display_state["break_right_display_m"]):
        failures.append("side_view_display_x_not_collapsed_into_break")

    fig = side_view_diagram.build_side_view_figure(
        length_m=float(display_state["display_length_m"]),
        beam_depth_m=model["D_m"],
        height=260,
        support_condition=model["support_condition"],
    )
    side_view_diagram.build_side_view_support_shapes(fig, model)
    side_view_diagram.add_side_view_break_marks(fig, model)

    shapes = list(fig.layout.shapes or [])
    if not shapes:
        failures.append("side_view_shapes_missing")
    if not any(shape.type == "path" for shape in shapes):
        failures.append("pinned_support_shape_missing")
    if not any(shape.type == "circle" for shape in shapes):
        failures.append("roller_support_shape_missing")
    if len([shape for shape in shapes if shape.type == "line"]) < 4:
        failures.append("support_or_break_lines_missing")
    if fig.layout.xaxis.visible is not False:
        failures.append("x_axis_visible")
    if fig.layout.yaxis.visible is not False:
        failures.append("y_axis_visible")
    if fig.layout.yaxis.scaleanchor != "x":
        failures.append("y_axis_not_scaleanchored")

    failures.extend(_check_shared_import_identity())
    failures.extend(_check_side_view_load_builder())
    failures.extend(_check_break_marks_builder())
    failures.extend(_check_tension_reo_builder())
    failures.extend(_check_section_marker_builder())
    failures.extend(_check_stirrup_marker_builder())
    failures.extend(_check_creep_reo_overlay_preserves_reo_identity())
    failures.extend(_check_support_proportions_match_deflection_contract())

    if failures:
        print("DIAGRAM_SIDE_VIEW_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_SIDE_VIEW_SMOKE PASS")
    print("- shared side-view, load, break-mark, tension-reo, section-marker, stirrup-marker, bending-side, and crack-side builder import identity verified")
    print(f"- support/break shapes: {len(shapes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
