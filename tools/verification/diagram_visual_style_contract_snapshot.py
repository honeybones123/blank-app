"""Visual style contract snapshot for migrated diagram modules.

This verifier intentionally covers only the shared style contract and migrated
renderers. Other diagram modules are still allowed to contain legacy hard-coded
colours and sizes until their staged migration pass.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import streamlit as st


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REQUIRED_CONSTANTS = {
    "DIAGRAM_BG",
    "DIAGRAM_TRANSPARENT",
    "CONCRETE_FILL_2D",
    "CONCRETE_FILL_3D",
    "CONCRETE_OUTLINE",
    "REO_BOTTOM",
    "REO_TOP",
    "REO_INACTIVE",
    "LINK_STEEL",
    "SUPPORT_OUTLINE",
    "SUPPORT_FILL",
    "SUPPORT_GROUND",
    "SUPPORT_ROLLER_FILL",
    "DEFLECTED_FILL",
    "DEFLECTED_LINE",
    "DEFLECTION_VISUAL_SCALE_MIN",
    "DEFLECTION_VISUAL_SCALE_MAX",
    "DEFLECTION_VISUAL_TARGET_DEPTH_RATIO",
    "DEFLECTION_VISUAL_TARGET_MIN_MM",
    "UNDEFORMED_FILL",
    "UNDEFORMED_LINE",
    "COMPRESSION",
    "TENSION",
    "CRACK_LINE",
    "ANNOTATION_BG",
    "ANNOTATION_BORDER",
    "ANNOTATION_TEXT",
    "REFERENCE_LINE",
    "DIAGRAM_SIZE_LONGITUDINAL",
    "DIAGRAM_SIZE_BEHAVIOUR",
    "DIAGRAM_HEIGHT_ANALYSIS",
    "DIAGRAM_HEIGHT_SECTION_COMPACT",
    "DIAGRAM_HEIGHT_SECTION_NORMAL",
    "DIAGRAM_HEIGHT_STEP_DETAIL",
    "DIAGRAM_HEIGHT_STRIP",
    "DIAGRAM_HEIGHT_LOCATOR",
    "DIAGRAM_HEIGHT_SFD_BMD",
    "DIAGRAM_HEIGHT_MOMENT_SMALL",
    "DIAGRAM_HEIGHT_3D_SMALL",
}

REQUIRED_HELPERS = {
    "diagram_line",
    "diagram_annotation_style",
    "apply_diagram_layout",
}

DEFLECTION_REQUIRED_USES = {
    "DIAGRAM_SIZE_LONGITUDINAL",
    "DIAGRAM_BG",
    "DIAGRAM_TRANSPARENT",
    "SUPPORT_OUTLINE",
    "SUPPORT_FILL",
    "SUPPORT_GROUND",
    "SUPPORT_ROLLER_FILL",
    "CONCRETE_FILL_2D",
    "CONCRETE_OUTLINE",
    "UNDEFORMED_LINE",
    "DEFLECTED_LINE",
    "ANNOTATION_BG",
    "ANNOTATION_BORDER",
}

DEFLECTION_FORBIDDEN_LITERALS = {
    '"rgba(35,35,35,1.0)"',
    '"rgba(35,35,35,0.12)"',
    '"rgba(80,80,80,0.85)"',
    '"rgba(255,255,255,0.55)"',
    '"rgba(210,210,210,0.22)"',
    '"rgba(140,140,140,0.95)"',
    '"rgba(31,119,180,0.30)"',
    '"rgba(31,119,180,1.0)"',
    '"rgba(0,0,0,0)"',
    '"rgba(255,255,255,0.9)"',
    '"rgba(0,0,0,0.15)"',
    '"#c0392b"',
    '"#333"',
    '"#222"',
    "height=420",
}

DEFLECTION_EXPECTED_TRACE_NAMES = [
    "Undeformed beam",
    "Deflected beam",
    "Deflection (hover)",
    "Max |\u03b4|",
]

SIDE_VIEW_REQUIRED_USES = {
    "DIAGRAM_SIZE_LONGITUDINAL",
    "DIAGRAM_BG",
    "DIAGRAM_TRANSPARENT",
    "REO_BOTTOM",
    "REO_TOP",
    "LINK_STEEL",
    "REO_INACTIVE",
    "SUPPORT_OUTLINE",
    "SUPPORT_FILL",
    "SUPPORT_GROUND",
    "SUPPORT_GROUND_HATCH",
    "SUPPORT_ROLLER_FILL",
    "MARKER_OUTLINE",
    "ANNOTATION_TEXT",
}

SIDE_VIEW_FORBIDDEN_PRIMARY_LITERALS = {
    '"white"',
    '"rgba(0,90,200,0.95)"',
    '"rgba(200,45,45,0.95)"',
    '"rgba(0,0,0,0.85)"',
    '"rgba(0,0,0,0.95)"',
    '"rgba(0,0,0,0)"',
    '"rgba(35,35,35,1.0)"',
    '"rgba(35,35,35,0.95)"',
    '"rgba(35,35,35,0.12)"',
    '"rgba(80,80,80,0.85)"',
    '"rgba(80,80,80,0.82)"',
    '"rgba(255,255,255,0.55)"',
    '"rgba(40,40,40,0.95)"',
    '"rgba(60,60,60,0.9)"',
    '"rgba(70,70,70,0.9)"',
    '"rgba(100,100,100,0.85)"',
    '"rgba(100,100,100,0.9)"',
    "SIDE_VIEW_VISUAL_WIDTH = 1120",
    "SIDE_VIEW_VISUAL_HEIGHT = 260",
}

SECTION_REQUIRED_USES = {
    "ANNOTATION_TEXT",
    "CONCRETE_FILL_2D",
    "CONCRETE_OUTLINE",
    "DIAGRAM_TRANSPARENT",
    "LINK_STEEL",
    "REO_BOTTOM",
    "REO_TOP",
}

SECTION_FORBIDDEN_PRIMARY_PATTERNS = {
    'line=dict(color="black"',
    'line=dict(width=1, color="black"',
    'font=dict(size=12, color="black"',
    'fillcolor="rgba(0,0,0,0)"',
    '_add_layer_circles(layer, "rgba(0,0,255,0.9)")',
    '_add_layer_circles(layer, "rgba(255,0,0,0.9)")',
}

SHEAR_REQUIRED_USES = {
    "ANNOTATION_BG",
    "ANNOTATION_TEXT",
    "CONCRETE_FILL_2D",
    "CONCRETE_OUTLINE",
    "DIAGRAM_BG",
    "DIAGRAM_TRANSPARENT",
    "LINK_STEEL",
    "REO_BOTTOM",
    "REO_INACTIVE",
    "REO_TOP",
}

SHEAR_FORBIDDEN_PRIMARY_PATTERNS = {
    'line=dict(color="black"',
    'line=dict(width=1.2, color="rgba(0,0,0,0.85)")',
    'line=dict(color="rgba(0,0,0,0.95)"',
    'fillcolor="rgba(245,245,245,1.0)"',
    'shape.fillcolor = "rgba(210,216,224,0.30)"',
    'font=dict(size=11, color="rgba(95,95,95,0.9)")',
    'font=dict(size=11, color="rgba(200,45,45,0.95)")',
    'font=dict(size=11, color="rgba(0,90,200,0.95)")',
    'paper_bgcolor="white"',
    'plot_bgcolor="white"',
}

SHEAR_BEHAVIOUR_REQUIRED_USES = {
    "CONCRETE_FILL_2D",
    "CONCRETE_OUTLINE",
    "DIAGRAM_BG",
    "SUPPORT_FILL",
    "SUPPORT_FIXED_HATCH_SPAN_RATIO",
    "SUPPORT_FIXED_MIN_HATCH_MM",
    "SUPPORT_FIXED_OVERHANG_BEAM_RATIO",
    "SUPPORT_GROUND",
    "SUPPORT_GROUND_DROP_BEAM_RATIO",
    "SUPPORT_GROUND_MIN_DROP_MM",
    "SUPPORT_GROUND_HATCH",
    "SUPPORT_OUTLINE",
    "SUPPORT_PIN_DEPTH_BEAM_RATIO",
    "SUPPORT_PIN_MIN_DEPTH_MM",
    "SUPPORT_PIN_MIN_WIDTH_MM",
    "SUPPORT_PIN_WIDTH_SPAN_RATIO",
    "SUPPORT_ROLLER_FILL",
    "SUPPORT_ROLLER_MIN_RADIUS_MM",
    "SUPPORT_ROLLER_RADIUS_BEAM_RATIO",
}

SHEAR_BEHAVIOUR_FORBIDDEN_SUPPORT_PATTERNS = {
    '"rgba(205,212,220,0.35)"',
    '"rgba(35,35,35,1.0)"',
    '"rgba(35,35,35,0.12)"',
    '"rgba(80,80,80,0.85)"',
    '"rgba(80,80,80,0.82)"',
    '"rgba(255,255,255,0.55)"',
    'paper_bgcolor="white"',
    'plot_bgcolor="white"',
    "support_w = max(length_m * 0.03, 0.09)",
    "support_d = max(0.28 * beam_depth_m, 0.08)",
}


def _failures_for_style_module(styles) -> list[str]:
    failures: list[str] = []
    missing = sorted(name for name in REQUIRED_CONSTANTS if not hasattr(styles, name))
    failures.extend(f"missing_constant_{name}" for name in missing)

    missing_helpers = sorted(name for name in REQUIRED_HELPERS if not callable(getattr(styles, name, None)))
    failures.extend(f"missing_helper_{name}" for name in missing_helpers)

    if styles.DIAGRAM_SIZE_LONGITUDINAL != {"width": 1120, "height": 390}:
        failures.append("longitudinal_size_contract_changed")
    if styles.DIAGRAM_SIZE_BEHAVIOUR != {"width": 1120, "height": 630}:
        failures.append("behaviour_size_contract_changed")
    expected_heights = {
        "DIAGRAM_HEIGHT_ANALYSIS": 420,
        "DIAGRAM_HEIGHT_SECTION_COMPACT": 475,
        "DIAGRAM_HEIGHT_SECTION_NORMAL": 545,
        "DIAGRAM_HEIGHT_STEP_DETAIL": 540,
        "DIAGRAM_HEIGHT_STRIP": 140,
        "DIAGRAM_HEIGHT_LOCATOR": 70,
        "DIAGRAM_HEIGHT_SFD_BMD": 300,
        "DIAGRAM_HEIGHT_MOMENT_SMALL": 260,
        "DIAGRAM_HEIGHT_3D_SMALL": 350,
    }
    for name, expected in expected_heights.items():
        if getattr(styles, name, None) != expected:
            failures.append(f"{name.lower()}_changed")

    style_source = (ROOT / "ui" / "diagrams" / "diagram_styles.py").read_text(encoding="utf-8")
    if "streamlit" in style_source:
        failures.append("diagram_styles_imports_or_mentions_streamlit")
    if "session_state" in style_source or "get_param" in style_source:
        failures.append("diagram_styles_depends_on_app_state")
    return failures


def _failures_for_deflection_source() -> list[str]:
    failures: list[str] = []
    source = (ROOT / "ui" / "diagrams" / "deflection_diagram.py").read_text(encoding="utf-8")
    if "from .diagram_styles import" not in source:
        failures.append("deflection_diagram_not_importing_style_contract")
    for name in sorted(DEFLECTION_REQUIRED_USES):
        if name not in source:
            failures.append(f"deflection_missing_style_use_{name}")
    for literal in sorted(DEFLECTION_FORBIDDEN_LITERALS):
        if literal in source:
            failures.append(f"deflection_retains_literal_{literal.strip(chr(34)).replace('#', 'hex_')}")
    return failures


def _failures_for_deflection_figure(styles, deflection) -> list[str]:
    failures: list[str] = []
    x = np.linspace(0.0, 6000.0, 7)
    w = np.array([0.0, -3.0, -7.0, -10.0, -7.0, -3.0, 0.0])
    fig = deflection.build_deflected_shape_figure(
        x,
        w,
        6000.0,
        600.0,
        support_type="Simply supported",
        show_legend=True,
    )

    if int(fig.layout.width or 0) != styles.DIAGRAM_SIZE_LONGITUDINAL["width"]:
        failures.append("deflection_width_not_from_longitudinal_contract")
    if int(fig.layout.height or 0) != styles.DIAGRAM_SIZE_LONGITUDINAL["height"]:
        failures.append("deflection_height_not_from_longitudinal_contract")
    if fig.layout.plot_bgcolor != styles.DIAGRAM_BG:
        failures.append("deflection_plot_bg_not_contract")
    if fig.layout.paper_bgcolor != styles.DIAGRAM_BG:
        failures.append("deflection_paper_bg_not_contract")

    if len(fig.data) < 4:
        failures.append("deflection_trace_count_changed")
        return failures

    trace_names = [str(getattr(trace, "name", "") or "") for trace in fig.data[:4]]
    if trace_names != DEFLECTION_EXPECTED_TRACE_NAMES:
        failures.append("deflection_trace_names_changed")
    if getattr(fig.data[0], "showlegend", None) is False:
        failures.append("undeformed_legend_item_removed")
    if getattr(fig.data[1], "showlegend", None) is False:
        failures.append("deflected_legend_item_removed")
    if getattr(fig.data[2], "showlegend", None) is not False:
        failures.append("hover_trace_legend_state_changed")
    if "actual" not in str(getattr(fig.data[2], "hovertemplate", "") or ""):
        failures.append("deflection_hover_text_lost_actual_value")
    if "mm" not in str(getattr(fig.data[2], "hovertemplate", "") or ""):
        failures.append("deflection_hover_text_lost_units")
    if "actual" not in str(getattr(fig.data[3], "hovertemplate", "") or ""):
        failures.append("max_marker_hover_text_lost_actual_value")

    if getattr(fig.data[0], "fillcolor", None) != styles.DIAGRAM_TRANSPARENT:
        failures.append("undeformed_reference_fill_not_transparent_contract")
    if getattr(fig.data[0].line, "color", None) != styles.UNDEFORMED_LINE:
        failures.append("undeformed_line_not_contract")
    if getattr(fig.data[1], "fillcolor", None) != styles.CONCRETE_FILL_2D:
        failures.append("deflected_beam_fill_not_concrete_contract")
    if getattr(fig.data[1].line, "color", None) != styles.CONCRETE_OUTLINE:
        failures.append("deflected_beam_outline_not_concrete_contract")
    if getattr(fig.data[2].line, "color", None) != styles.DEFLECTED_LINE:
        failures.append("deflection_cue_line_not_contract")
    if tuple(fig.layout.xaxis.range or ()) != (-180.0, 6180.0):
        failures.append("deflection_x_range_not_tied_to_active_length")
    if getattr(fig.layout.yaxis, "scaleanchor", None) != "x":
        failures.append("deflection_y_axis_not_scaleanchored_to_x")
    if float(getattr(fig.layout.yaxis, "scaleratio", 0.0) or 0.0) != 1.0:
        failures.append("deflection_y_axis_scaleratio_not_one")
    margin = fig.layout.margin
    plot_w = float(fig.layout.width - int(margin.l or 0) - int(margin.r or 0))
    plot_h = float(fig.layout.height - int(margin.t or 0) - int(margin.b or 0))
    x_range = tuple(fig.layout.xaxis.range or ())
    y_range = tuple(fig.layout.yaxis.range or ())
    if len(x_range) == 2 and len(y_range) == 2 and plot_w > 0.0 and plot_h > 0.0:
        x_mm_per_px = (float(x_range[1]) - float(x_range[0])) / plot_w
        y_mm_per_px = (float(y_range[1]) - float(y_range[0])) / plot_h
        if abs((y_mm_per_px / x_mm_per_px) - 1.0) > 0.02:
            failures.append("deflection_viewport_not_to_scale")
    else:
        failures.append("deflection_viewport_scale_not_measurable")

    marker = getattr(fig.data[3], "marker", None)
    if getattr(marker, "color", None) != styles.MAX_DEFLECTION_MARKER:
        failures.append("max_marker_not_contract")
    if getattr(marker, "symbol", None) != "circle":
        failures.append("max_marker_symbol_changed")
    if int(getattr(marker, "size", 0) or 0) != 9:
        failures.append("max_marker_size_changed")

    shapes = list(fig.layout.shapes or [])
    if len(shapes) < 5:
        failures.append("deflection_support_shapes_missing")
    else:
        if getattr(shapes[0].line, "color", None) != styles.SUPPORT_OUTLINE:
            failures.append("support_outline_not_contract")
        if getattr(shapes[0], "fillcolor", None) != styles.SUPPORT_FILL:
            failures.append("support_fill_not_contract")

    annotations = list(fig.layout.annotations or [])
    if not annotations:
        failures.append("deflection_annotation_missing")
    else:
        ann = annotations[0]
        if "max" not in str(getattr(ann, "text", "") or "").lower():
            failures.append("deflection_max_annotation_text_changed")
        if "mm" not in str(getattr(ann, "text", "") or ""):
            failures.append("deflection_max_annotation_units_lost")
        if getattr(ann.font, "color", None) != styles.ANNOTATION_TEXT:
            failures.append("annotation_text_not_contract")
        if getattr(ann, "bgcolor", None) != styles.ANNOTATION_BG:
            failures.append("annotation_bg_not_contract")
        if getattr(ann, "bordercolor", None) != styles.ANNOTATION_BORDER:
            failures.append("annotation_border_not_contract")
    annotation_texts = [str(getattr(annotation, "text", "") or "") for annotation in annotations]
    for removed_text in ("Span L =", "Depth D =", "Top reo", "Bottom reo"):
        if any(text.startswith(removed_text) or text == removed_text for text in annotation_texts):
            failures.append(f"deflection_removed_annotation_returned:{removed_text}")

    title = getattr(getattr(fig.layout, "title", None), "text", "") or ""
    if str(title):
        failures.append("deflection_title_should_not_render")

    return failures


def _base_side_view_model() -> dict:
    return {
        "total_length_m": 8.0,
        "span_m": 8.0,
        "D_m": 0.6,
        "support_condition": "simply_supported",
        "support_positions": [0.0, 8.0],
        "section_layout": {"dims": {"b": 450.0, "D": 600.0}},
    }


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def _trace_hovertext(fig) -> list[str]:
    out: list[str] = []
    for trace in fig.data:
        hover = getattr(trace, "hovertext", None)
        if hover is None:
            continue
        if isinstance(hover, str):
            out.append(hover)
        else:
            out.extend(str(item) for item in hover)
    return out


def _failures_for_side_view_source() -> list[str]:
    failures: list[str] = []
    source = (ROOT / "ui" / "diagrams" / "side_view_diagram.py").read_text(encoding="utf-8")
    if "from .diagram_styles import" not in source:
        failures.append("side_view_diagram_not_importing_style_contract")
    for name in sorted(SIDE_VIEW_REQUIRED_USES):
        if name not in source:
            failures.append(f"side_view_missing_style_use_{name}")
    for literal in sorted(SIDE_VIEW_FORBIDDEN_PRIMARY_LITERALS):
        if literal in source:
            failures.append(f"side_view_retains_primary_literal_{literal.strip(chr(34)).replace('#', 'hex_')}")
    return failures


def _new_side_view_fig(side_view, model: dict) -> object:
    return side_view.build_side_view_figure(
        length_m=float(model["side_view_display"]["display_length_m"]),
        beam_depth_m=model["D_m"],
        height=side_view.SIDE_VIEW_VISUAL_HEIGHT,
        support_condition=model["support_condition"],
    )


def _failures_for_side_view_figure(styles, side_view) -> list[str]:
    import shear_visuals  # noqa: WPS433

    failures: list[str] = []
    model = _base_side_view_model()
    model["side_view_display"] = side_view.side_view_display_state(model)

    fig = _new_side_view_fig(side_view, model)
    if int(fig.layout.width or 0) != styles.DIAGRAM_SIZE_LONGITUDINAL["width"]:
        failures.append("side_view_width_not_from_longitudinal_contract")
    if int(fig.layout.height or 0) != styles.DIAGRAM_SIZE_LONGITUDINAL["height"]:
        failures.append("side_view_height_not_from_longitudinal_contract")
    if int(side_view.SIDE_VIEW_VISUAL_WIDTH) != styles.DIAGRAM_SIZE_LONGITUDINAL["width"]:
        failures.append("side_view_width_constant_not_contract")
    if int(side_view.SIDE_VIEW_VISUAL_HEIGHT) != styles.DIAGRAM_SIZE_LONGITUDINAL["height"]:
        failures.append("side_view_height_constant_not_contract")
    if fig.layout.paper_bgcolor != styles.DIAGRAM_BG:
        failures.append("side_view_paper_bg_not_contract")
    if fig.layout.plot_bgcolor != styles.DIAGRAM_BG:
        failures.append("side_view_plot_bg_not_contract")

    side_view.build_side_view_support_shapes(fig, model)
    side_view.add_side_view_break_marks(fig, model)
    shapes = list(fig.layout.shapes or [])
    if not any(shape.type == "path" for shape in shapes):
        failures.append("side_view_pinned_support_shape_removed")
    if not any(shape.type == "circle" for shape in shapes):
        failures.append("side_view_roller_support_shape_removed")
    if len([shape for shape in shapes if shape.type == "line"]) < 4:
        failures.append("side_view_support_or_break_lines_removed")
    if not any(getattr(shape.line, "color", None) == styles.SUPPORT_OUTLINE for shape in shapes if hasattr(shape, "line")):
        failures.append("side_view_support_outline_not_contract")
    if not any(getattr(shape, "fillcolor", None) == styles.SUPPORT_FILL for shape in shapes):
        failures.append("side_view_support_fill_not_contract")

    reo_model = dict(model)
    reo_model["bottom_layers"] = [{"db": 20.0}, {"db": 16.0}]
    reo_model["top_layers"] = [{"db": 12.0}]
    st.session_state["sec_shape"] = "RECT"
    reo_fig = _new_side_view_fig(side_view, reo_model)
    side_view.build_side_view_tension_reo(reo_fig, reo_model)
    if len(reo_fig.data) != 3:
        failures.append("side_view_reo_trace_count_changed")
    reo_annotations = _annotation_text(reo_fig)
    if "Tension reo" not in reo_annotations:
        failures.append("side_view_tension_reo_label_removed")
    if len(reo_annotations) < 2:
        failures.append("side_view_top_reo_label_removed")
    if not reo_fig.data or getattr(reo_fig.data[0].line, "color", None) != styles.REO_BOTTOM:
        failures.append("side_view_bottom_reo_not_contract")
    if len(reo_fig.data) >= 3 and getattr(reo_fig.data[-1].line, "color", None) != styles.REO_TOP:
        failures.append("side_view_top_reo_not_contract")
    if any(getattr(trace, "showlegend", None) is not False for trace in reo_fig.data):
        failures.append("side_view_reo_legend_state_changed")

    section_model = dict(model, section_x_m=2.75)
    section_fig = _new_side_view_fig(side_view, section_model)
    side_view.add_section_marker(section_fig, section_model)
    if _annotation_text(section_fig) != ["Section"]:
        failures.append("side_view_section_marker_label_changed")
    section_shapes = list(section_fig.layout.shapes or [])
    if len(section_shapes) != 1 or getattr(section_shapes[0].line, "dash", None) != "dash":
        failures.append("side_view_section_marker_shape_changed")

    load_model = dict(
        model,
        case=shear_visuals._DEFAULT_LOADING_CASE,
        mode="ULS",
        w_value=22.5,
        point_value=125.0,
        a_m=2.4,
        a_udl_m=3.0,
        a_cant_m=2.0,
    )
    load_fig = _new_side_view_fig(side_view, load_model)
    side_view.build_side_view_load_shapes(load_fig, load_model, show_labels=True)
    if not any("w*" in text and "kN/m" in text for text in _annotation_text(load_fig)):
        failures.append("side_view_udl_label_removed")
    if any(getattr(trace, "showlegend", None) is not False for trace in load_fig.data):
        failures.append("side_view_load_legend_state_changed")

    for key, value in {
        "lig_legs": 2,
        "lig_d": 10.0,
        "shear_zone_enabled": False,
        "shear_auto_design": False,
        "s_lig": 200.0,
        "shear_zone_results": None,
    }.items():
        st.session_state[key] = value
    stirrup_model = dict(model, spacing_mm=200.0, lig_legs=2)
    stirrup_fig = _new_side_view_fig(side_view, stirrup_model)
    side_view.build_stirrup_markers(stirrup_fig, stirrup_model)
    stirrup_annotations = _annotation_text(stirrup_fig)
    if not any("Provided spacing" in text for text in stirrup_annotations):
        failures.append("side_view_provided_spacing_label_removed")
    if not any("Provided spacing:" in text and "mm" in text for text in _trace_hovertext(stirrup_fig)):
        failures.append("side_view_provided_spacing_hover_removed")
    if not any(getattr(shape.line, "color", None) == styles.LINK_STEEL for shape in stirrup_fig.layout.shapes or []):
        failures.append("side_view_stirrup_lines_not_contract")

    for key, value in {
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
    }.items():
        st.session_state[key] = value
    zoned_fig = _new_side_view_fig(side_view, stirrup_model)
    side_view.build_stirrup_markers(zoned_fig, stirrup_model)
    zoned_annotations = _annotation_text(zoned_fig)
    if not any("required" in text.lower() for text in zoned_annotations):
        failures.append("side_view_required_zone_label_removed")
    if not any("Required spacing" in text and "mm" in text for text in _trace_hovertext(zoned_fig)):
        failures.append("side_view_required_spacing_hover_removed")
    if not any(shape.type == "rect" for shape in zoned_fig.layout.shapes or []):
        failures.append("side_view_zone_marker_shapes_removed")

    return failures


def _section_rect_layout() -> dict:
    return {
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


def _fake_t_section_builder(**_kwargs):
    import plotly.graph_objects as go  # noqa: WPS433

    fig = go.Figure()
    fig.add_shape(
        type="path",
        path="M 0,0 L 900,0 L 900,150 L 550,150 L 550,750 L 350,750 L 350,150 L 0,150 Z",
        line=dict(width=1.2, color="black"),
        fillcolor="rgba(0,0,0,0)",
    )
    return fig


def _failures_for_section_source() -> list[str]:
    failures: list[str] = []
    source = (ROOT / "ui" / "diagrams" / "section_diagram.py").read_text(encoding="utf-8")
    if "from .diagram_styles import" not in source:
        failures.append("section_diagram_not_importing_style_contract")
    for name in sorted(SECTION_REQUIRED_USES):
        if name not in source:
            failures.append(f"section_missing_style_use_{name}")
    for pattern in sorted(SECTION_FORBIDDEN_PRIMARY_PATTERNS):
        if pattern in source:
            failures.append(f"section_retains_primary_literal_{pattern}")
    if "height=" in source or "update_layout(\n        height" in source:
        failures.append("section_module_started_owning_height")
    return failures


def _failures_for_section_figure(styles, section) -> list[str]:
    failures: list[str] = []
    result = section.build_summary_cross_section_result(layout=_section_rect_layout())
    fig = result.figure
    if fig is None:
        return ["section_rect_figure_missing"]
    if result.error_message is not None:
        failures.append("section_rect_unexpected_error_message")
    shapes = list(fig.layout.shapes or [])
    rects = [shape for shape in shapes if shape.type == "rect"]
    circles = [shape for shape in shapes if shape.type == "circle"]
    lines = [shape for shape in shapes if shape.type == "line"]
    if len(rects) < 2:
        failures.append("section_rect_outline_or_ligature_removed")
    if len(circles) != 6:
        failures.append(f"section_rect_bar_count_changed_{len(circles)}")
    if len(lines) < 1:
        failures.append("section_rect_internal_ligature_removed")
    if fig.layout.height is not None:
        failures.append("section_rect_height_became_module_owned")
    if fig.layout.paper_bgcolor != styles.DIAGRAM_TRANSPARENT:
        failures.append("section_paper_bg_not_contract")
    if fig.layout.plot_bgcolor != styles.DIAGRAM_TRANSPARENT:
        failures.append("section_plot_bg_not_contract")

    outer_rect = rects[0] if rects else None
    if outer_rect is not None:
        if getattr(outer_rect.line, "color", None) != styles.CONCRETE_OUTLINE:
            failures.append("section_concrete_outline_not_contract")
        if getattr(outer_rect, "fillcolor", None) != styles.CONCRETE_FILL_2D:
            failures.append("section_concrete_fill_not_contract")
    bottom_circles = [shape for shape in circles if getattr(shape, "fillcolor", None) == styles.REO_BOTTOM]
    top_circles = [shape for shape in circles if getattr(shape, "fillcolor", None) == styles.REO_TOP]
    if len(bottom_circles) != 4:
        failures.append(f"section_bottom_reo_count_or_colour_changed_{len(bottom_circles)}")
    if len(top_circles) != 2:
        failures.append(f"section_top_reo_count_or_colour_changed_{len(top_circles)}")
    expected_bottom_x0 = [110.0, 200.0, 290.0, 380.0]
    actual_bottom_x0 = sorted(float(shape.x0) for shape in bottom_circles)
    if actual_bottom_x0 != expected_bottom_x0:
        failures.append("section_bottom_reo_positions_changed")
    expected_top_x0 = [152.0, 282.0]
    actual_top_x0 = sorted(float(shape.x0) for shape in top_circles)
    if actual_top_x0 != expected_top_x0:
        failures.append("section_top_reo_positions_changed")
    if not any(getattr(shape.line, "color", None) == styles.LINK_STEEL for shape in lines):
        failures.append("section_ligature_link_not_contract")

    t_layout = {
        "shape_name": "T-Section",
        "dims": {"bf": 900.0, "tf": 150.0, "bw": 200.0, "D": 750.0},
        "reo": {"cover_side": 45.0, "cover_top": 40.0, "cover_bot": 50.0},
    }
    t_result = section.build_summary_cross_section_result(
        layout=t_layout,
        section_figure_builder=_fake_t_section_builder,
    )
    t_fig = t_result.figure
    if t_fig is None:
        failures.append("section_t_figure_missing")
        return failures
    expected_fragments = [
        "bf = 900 mm",
        "D = 750 mm",
        "tf = 150 mm",
        "bw = 200 mm",
        "cover(top/bot/side) = 40/50/45 mm",
    ]
    t_annotations = _annotation_text(t_fig)
    for fragment in expected_fragments:
        if not any(fragment in text for text in t_annotations):
            failures.append(f"section_dimension_text_missing_{fragment.replace(' ', '_')}")
    if not t_fig.layout.shapes or getattr(t_fig.layout.shapes[0], "fillcolor", None) != styles.CONCRETE_FILL_2D:
        failures.append("section_t_concrete_fill_not_contract")
    if not t_fig.layout.shapes or getattr(t_fig.layout.shapes[0].line, "color", None) != styles.CONCRETE_OUTLINE:
        failures.append("section_t_concrete_outline_not_contract")
    if t_fig.layout.height is not None:
        failures.append("section_t_height_became_module_owned")
    if any(getattr(annotation.font, "color", None) != styles.ANNOTATION_TEXT for annotation in t_fig.layout.annotations or []):
        failures.append("section_annotation_text_not_contract")
    if len(t_fig.data) != 0 and _trace_hovertext(t_fig):
        failures.append("section_unexpected_hover_text_changed")
    return failures


def _shear_rect_layout() -> dict:
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


def _failures_for_shear_source() -> list[str]:
    failures: list[str] = []
    source = (ROOT / "ui" / "diagrams" / "shear_diagram.py").read_text(encoding="utf-8")
    if "from .diagram_styles import" not in source:
        failures.append("shear_diagram_not_importing_style_contract")
    for name in sorted(SHEAR_REQUIRED_USES):
        if name not in source:
            failures.append(f"shear_missing_style_use_{name}")
    for pattern in sorted(SHEAR_FORBIDDEN_PRIMARY_PATTERNS):
        if pattern in source:
            failures.append(f"shear_retains_primary_literal_{pattern}")
    return failures


def _failures_for_shear_behaviour_source() -> list[str]:
    failures: list[str] = []
    source = (ROOT / "ui" / "diagrams" / "shear_behaviour_diagram.py").read_text(encoding="utf-8")
    if "from ui.diagrams.diagram_styles import" not in source:
        failures.append("shear_behaviour_not_importing_style_contract")
    for name in sorted(SHEAR_BEHAVIOUR_REQUIRED_USES):
        if name not in source:
            failures.append(f"shear_behaviour_missing_style_use_{name}")
    for pattern in sorted(SHEAR_BEHAVIOUR_FORBIDDEN_SUPPORT_PATTERNS):
        if pattern in source:
            failures.append(f"shear_behaviour_retains_support_literal_{pattern}")
    return failures


def _failures_for_shear_behaviour_figure(styles, behaviour) -> list[str]:
    failures: list[str] = []
    fig = behaviour.build_shear_behaviour_base_figure(
        length_m=6.0,
        beam_depth_m=0.75,
        height=styles.DIAGRAM_SIZE_BEHAVIOUR["height"],
        width=styles.DIAGRAM_SIZE_BEHAVIOUR["width"],
    )
    behaviour.add_shear_behaviour_beam_band(fig, 6.0, 0.75)
    behaviour.build_shear_behaviour_support_shapes(
        fig,
        {
            "total_length_m": 6.0,
            "span_m": 6.0,
            "D_m": 0.75,
            "d_m": 0.69,
            "support_condition": "simply_supported",
            "support_positions": [0.0, 6.0],
            "support_pair": ("Pinned", "Roller"),
        },
    )

    if int(fig.layout.width or 0) != styles.DIAGRAM_SIZE_BEHAVIOUR["width"]:
        failures.append("shear_behaviour_width_not_behaviour_contract")
    if int(fig.layout.height or 0) != styles.DIAGRAM_SIZE_BEHAVIOUR["height"]:
        failures.append("shear_behaviour_height_not_behaviour_contract")
    if fig.layout.paper_bgcolor != styles.DIAGRAM_BG or fig.layout.plot_bgcolor != styles.DIAGRAM_BG:
        failures.append("shear_behaviour_background_not_contract")

    shapes = list(fig.layout.shapes or [])
    beam_rects = [
        shape
        for shape in shapes
        if shape.type == "rect"
        and abs(float(getattr(shape, "x0", -1.0))) < 1e-9
        and abs(float(getattr(shape, "x1", -1.0)) - 6.0) < 1e-9
        and abs(float(getattr(shape, "y0", -1.0))) < 1e-9
        and abs(float(getattr(shape, "y1", -1.0)) - 0.75) < 1e-9
    ]
    if not beam_rects:
        failures.append("shear_behaviour_beam_band_missing")
    else:
        beam = beam_rects[0]
        if getattr(beam, "fillcolor", None) != styles.CONCRETE_FILL_2D:
            failures.append("shear_behaviour_beam_fill_not_contract")
        if getattr(beam.line, "color", None) != styles.CONCRETE_OUTLINE:
            failures.append("shear_behaviour_beam_outline_not_contract")

    support_paths = [shape for shape in shapes if shape.type == "path"]
    support_circles = [shape for shape in shapes if shape.type == "circle"]
    support_lines = [shape for shape in shapes if shape.type == "line"]
    if len(support_paths) < 2:
        failures.append("shear_behaviour_pinned_supports_missing")
    if not any(getattr(shape, "fillcolor", None) == styles.SUPPORT_FILL for shape in support_paths):
        failures.append("shear_behaviour_support_fill_not_contract")
    if not any(getattr(shape.line, "color", None) == styles.SUPPORT_OUTLINE for shape in support_paths):
        failures.append("shear_behaviour_support_outline_not_contract")
    if not any(getattr(shape.line, "color", None) == styles.SUPPORT_GROUND for shape in support_lines):
        failures.append("shear_behaviour_support_ground_not_contract")
    if not any(getattr(shape, "fillcolor", None) == styles.SUPPORT_ROLLER_FILL for shape in support_circles):
        failures.append("shear_behaviour_roller_fill_not_contract")

    return failures


def _failures_for_shear_figure(styles, shear) -> list[str]:
    failures: list[str] = []
    fig = shear.build_shear_cross_section_figure_from_layout(layout=_shear_rect_layout(), height=360)
    shapes = list(fig.layout.shapes or [])
    rects = [shape for shape in shapes if shape.type == "rect"]
    circles = [shape for shape in shapes if shape.type == "circle"]
    lines = [shape for shape in shapes if shape.type == "line"]
    annotations = _annotation_text(fig)

    if int(fig.layout.height or 0) != 360:
        failures.append("shear_cross_section_height_not_preserved")
    if fig.layout.paper_bgcolor != styles.DIAGRAM_BG:
        failures.append("shear_cross_section_paper_bg_not_contract")
    if fig.layout.plot_bgcolor != styles.DIAGRAM_BG:
        failures.append("shear_cross_section_plot_bg_not_contract")
    if len(rects) < 2:
        failures.append("shear_section_or_ligature_rect_missing")
    if len(circles) != 6:
        failures.append(f"shear_longitudinal_reo_count_changed_{len(circles)}")
    if len(lines) < 3:
        failures.append("shear_ligature_lines_removed")

    outer_rect = rects[0] if rects else None
    if outer_rect is not None:
        if getattr(outer_rect.line, "color", None) != styles.CONCRETE_OUTLINE:
            failures.append("shear_concrete_outline_not_contract")
        if getattr(outer_rect, "fillcolor", None) != styles.CONCRETE_FILL_2D:
            failures.append("shear_concrete_fill_not_contract")
    if not any(getattr(shape.line, "color", None) == styles.LINK_STEEL for shape in lines):
        failures.append("shear_ligature_link_not_contract")
    if any(getattr(shape.line, "color", None) != styles.LINK_STEEL for shape in circles):
        failures.append("shear_reo_outline_not_contract")

    bottom_circles = [shape for shape in circles if getattr(shape, "fillcolor", None) == styles.REO_BOTTOM]
    top_circles = [shape for shape in circles if getattr(shape, "fillcolor", None) == styles.REO_TOP]
    if len(bottom_circles) != 4:
        failures.append(f"shear_bottom_reo_count_or_colour_changed_{len(bottom_circles)}")
    if len(top_circles) != 2:
        failures.append(f"shear_top_reo_count_or_colour_changed_{len(top_circles)}")
    if sorted(float(shape.x0) for shape in bottom_circles) != [110.0, 200.0, 290.0, 380.0]:
        failures.append("shear_bottom_reo_positions_changed")
    if sorted(float(shape.x0) for shape in top_circles) != [152.0, 282.0]:
        failures.append("shear_top_reo_positions_changed")

    for expected in ("b = 450 mm", "D = 750 mm", "Top reo", "Tension reo", "Shear reinforcement"):
        if not any(expected in text for text in annotations):
            failures.append(f"shear_annotation_missing_{expected.replace(' ', '_')}")
    for annotation in fig.layout.annotations or []:
        text = str(getattr(annotation, "text", "") or "")
        color = getattr(annotation.font, "color", None)
        if text in {"b = 450 mm", "D = 750 mm"} and color != styles.ANNOTATION_TEXT:
            failures.append("shear_dimension_annotation_text_not_contract")
        if text == "Top reo" and color != styles.REO_TOP:
            failures.append("shear_top_reo_label_not_contract")
        if text == "Tension reo" and color != styles.REO_BOTTOM:
            failures.append("shear_tension_reo_label_not_contract")
        if text == "Shear reinforcement" and color != styles.LINK_STEEL:
            failures.append("shear_reinforcement_label_not_contract")

    step3 = shear.plot_shear_step3_section_params_plotly(
        b_mm=450.0,
        D_mm=750.0,
        bv_mm=420.0,
        dv_mm=690.0,
        Asv_mm2=240.0,
        height=360,
    )
    if int(step3.layout.height or 0) != 360:
        failures.append("shear_step3_height_not_preserved")
    if step3.layout.paper_bgcolor != styles.DIAGRAM_BG or step3.layout.plot_bgcolor != styles.DIAGRAM_BG:
        failures.append("shear_step3_background_not_contract")
    step3_shapes = list(step3.layout.shapes or [])
    if not step3_shapes or getattr(step3_shapes[0].line, "color", None) != styles.CONCRETE_OUTLINE:
        failures.append("shear_step3_concrete_outline_not_contract")
    if not step3_shapes or getattr(step3_shapes[0], "fillcolor", None) != styles.CONCRETE_FILL_2D:
        failures.append("shear_step3_concrete_fill_not_contract")
    if not any(shape.type == "line" and getattr(shape.line, "color", None) == styles.LINK_STEEL for shape in step3_shapes):
        failures.append("shear_step3_dv_marker_not_contract")
    for expected in ("b<sub>v</sub>", "d<sub>v</sub>", "A<sub>sv</sub>"):
        if not any(expected in text for text in _annotation_text(step3)):
            failures.append(f"shear_step3_annotation_missing_{expected}")
    if any(
        str(getattr(annotation, "text", "") or "")
        and getattr(annotation.font, "color", None) != styles.ANNOTATION_TEXT
        for annotation in step3.layout.annotations or []
        if "sub" in str(getattr(annotation, "text", "") or "")
    ):
        failures.append("shear_step3_dimension_annotation_not_contract")
    if not any(getattr(annotation, "bgcolor", None) == styles.ANNOTATION_BG for annotation in step3.layout.annotations or []):
        failures.append("shear_step3_asv_annotation_bg_not_contract")

    torsion = shear.plot_shear_torsion_section_2d(
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
    torsion_text = _annotation_text(torsion)
    for expected in ("tau_v", "tau_T", "opposes", "adds", "Section + reinforcement"):
        if not any(expected in text for text in torsion_text):
            failures.append(f"shear_torsion_annotation_missing_{expected.replace(' ', '_')}")
    if not any(getattr(shape.line, "color", None) == styles.LINK_STEEL for shape in torsion.layout.shapes or []):
        failures.append("shear_torsion_ligature_link_not_contract")
    for annotation in torsion.layout.annotations or []:
        text = str(getattr(annotation, "text", "") or "")
        if text in {"opposes", "adds", "Section + reinforcement (schematic)"} and getattr(annotation.font, "color", None) != styles.ANNOTATION_TEXT:
            failures.append("shear_torsion_annotation_text_not_contract")

    return failures


def main() -> int:
    styles = importlib.import_module("ui.diagrams.diagram_styles")
    deflection = importlib.import_module("ui.diagrams.deflection_diagram")
    side_view = importlib.import_module("ui.diagrams.side_view_diagram")
    section = importlib.import_module("ui.diagrams.section_diagram")
    shear = importlib.import_module("ui.diagrams.shear_diagram")
    shear_behaviour = importlib.import_module("ui.diagrams.shear_behaviour_diagram")

    failures: list[str] = []
    failures.extend(_failures_for_style_module(styles))
    failures.extend(_failures_for_deflection_source())
    failures.extend(_failures_for_deflection_figure(styles, deflection))
    failures.extend(_failures_for_side_view_source())
    failures.extend(_failures_for_side_view_figure(styles, side_view))
    failures.extend(_failures_for_section_source())
    failures.extend(_failures_for_section_figure(styles, section))
    failures.extend(_failures_for_shear_source())
    failures.extend(_failures_for_shear_figure(styles, shear))
    failures.extend(_failures_for_shear_behaviour_source())
    failures.extend(_failures_for_shear_behaviour_figure(styles, shear_behaviour))

    if failures:
        print("DIAGRAM_VISUAL_STYLE_CONTRACT_SNAPSHOT FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_VISUAL_STYLE_CONTRACT_SNAPSHOT PASS")
    print("- shared style constants and helpers present")
    print("- deflection diagram consumes Stage 1 style contract")
    print("- deflection hover text, legend items, max marker, supports, and clean-label contract preserved")
    print("- side-view diagram consumes Stage 2 style contract")
    print("- side-view labels, hover text, legend states, annotations, markers, supports, and zones preserved")
    print("- section diagram consumes Stage 3 style contract")
    print("- section geometry, reo markers, ligatures, dimensions, annotations, and caller-owned sizing preserved")
    print("- shear diagram consumes Stage 4 style contract")
    print("- shear geometry, reo markers, links, dimensions, annotations, and caller-owned sizing preserved")
    print("- shear behaviour / MCFT diagram consumes shared beam/support/background contract")
    print("- non-migrated diagram modules intentionally not enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
