"""Live diagram path snapshot for the visual style rollout.

This verifier is intentionally read-only. It records legacy/local visible paths
without failing them, and fails only when a migrated visible path no longer
routes through the shared diagram/style contract.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _has(source: str, *needles: str) -> bool:
    return all(needle in source for needle in needles)


def _shape_colours(fig: Any) -> dict[str, list[tuple[Any, Any]]]:
    shapes = list(fig.layout.shapes or [])
    rects = [
        (getattr(shape.line, "color", None), getattr(shape, "fillcolor", None))
        for shape in shapes
        if shape.type == "rect"
    ]
    circles = [
        (getattr(shape.line, "color", None), getattr(shape, "fillcolor", None))
        for shape in shapes
        if shape.type == "circle"
    ]
    lines = [
        (getattr(shape.line, "color", None), getattr(shape.line, "width", None))
        for shape in shapes
        if shape.type == "line"
    ]
    return {"rects": rects, "circles": circles, "lines": lines}


def _rect_section_layout() -> dict[str, Any]:
    return {
        "shape_name": "Rectangle (b x D)",
        "dims": {"b": 450.0, "D": 750.0},
        "reo": {
            "cover_side": 45.0,
            "cover_top": 40.0,
            "cover_bot": 50.0,
            "lig_d": 10.0,
            "lig_legs": 3,
            "min_clear_spacing": 20.0,
            "rowgap_top": 60.0,
            "rowgap_bot": 60.0,
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


def _check_inputs_paths(failures: list[str], observations: list[str], warnings: list[str]) -> None:
    source = _read("inputs_page.py")

    if _has(
        source,
        "from ui.diagrams.diagram_styles import",
        "CONCRETE_FILL_2D",
        "CONCRETE_OUTLINE",
        "LINK_STEEL",
        "REO_BOTTOM",
        "REO_TOP",
        "render_html_diagram",
        "def _render_fast_lightweight_2d_diagram",
        "_render_fast_lightweight_2d_diagram(model_state=model_state)",
        "render_html_diagram(",
        'key="inputs_fast_lightweight_2d_section_diagram"',
        "fullscreen_height=960",
        ".fast-model-concrete",
        "fill: {CONCRETE_FILL_2D};",
        "stroke: {CONCRETE_OUTLINE};",
        ".fast-model-bar-bottom",
        "fill: {REO_BOTTOM};",
        ".fast-model-bar-top",
        "fill: {REO_TOP};",
        "stroke: {LINK_STEEL};",
    ):
        observations.append("inputs_fast_model_inline_svg_uses_shared_style_constants")
        observations.append("inputs_fast_model_inline_svg_uses_shared_html_fullscreen_helper")
    else:
        failures.append("inputs_fast_model_inline_svg_shared_style_not_proven")

    for old_colour in (
        "fill: rgba(0,0,0,0);",
        "stroke: #000;",
        "fill: rgba(0,0,255,0.9);",
        "fill: rgba(255,0,0,0.9);",
        "background: rgba(0,0,255,0.9);",
        "background: rgba(255,0,0,0.9);",
        "border-top: 3px solid #000;",
    ):
        if old_colour in source:
            failures.append(f"inputs_fast_model_reintroduced_old_svg_colour:{old_colour}")

    if _has(
        source,
        "from ui.diagrams.section_diagram import build_summary_cross_section_result",
        "def make_summary_cross_section_figure",
        "result = build_summary_cross_section_result(",
        "def _render_section_2d_diagram_block",
    ):
        observations.append("inputs_detailed_or_browser_test_section_uses_shared_section_diagram")
    else:
        warnings.append("inputs_plotly_section_shared_path_not_proven")

    if _has(
        source,
        "cached_fp = st.session_state.get(\"_inputs_model_2d_geo_fp\")",
        "st.session_state[\"_inputs_model_2d_fig\"]",
    ):
        observations.append("inputs_plotly_section_has_session_figure_cache")


def _check_migrated_style_sources(failures: list[str]) -> None:
    required_by_file = {
        "ui/diagrams/deflection_diagram.py": [
            "from .diagram_styles import",
            "CONCRETE_FILL_2D",
            "CONCRETE_OUTLINE",
            "DEFLECTED_LINE",
            "UNDEFORMED_LINE",
            "ANNOTATION_BG",
        ],
        "ui/diagrams/side_view_diagram.py": [
            "from .diagram_styles import",
            "DIAGRAM_SIZE_LONGITUDINAL",
            "REO_BOTTOM",
            "REO_TOP",
            "LINK_STEEL",
            "SUPPORT_OUTLINE",
        ],
        "ui/diagrams/section_diagram.py": [
            "from .diagram_styles import",
            "CONCRETE_FILL_2D",
            "CONCRETE_OUTLINE",
            "REO_BOTTOM",
            "REO_TOP",
            "LINK_STEEL",
        ],
        "ui/diagrams/shear_diagram.py": [
            "from .diagram_styles import",
            "CONCRETE_FILL_2D",
            "CONCRETE_OUTLINE",
            "REO_BOTTOM",
            "REO_INACTIVE",
            "REO_TOP",
            "LINK_STEEL",
        ],
    }
    for rel_path, needles in required_by_file.items():
        source = _read(rel_path)
        for needle in needles:
            if needle not in source:
                failures.append(f"{rel_path}:missing_shared_style_use:{needle}")


def _check_shared_plotly_render_helper(failures: list[str], observations: list[str]) -> None:
    source = _read("widgets_helpers.py")
    if _has(
        source,
        "def render_plotly_diagram(",
        "def render_plotly_fullscreen_control(",
        "def render_pyplot_diagram(",
        "def render_image_diagram(",
        "def render_html_diagram(",
        "def _plotly_fullscreen_figure(",
        "horizontal_alignment=\"center\" if center else \"left\"",
        "st.dialog(title, width=\"large\")",
        "allow_fullscreen: bool = True",
        "preserve_figure_width: bool = False",
        "fullscreen_height: int = 960",
        "dialog_fig.update_layout(height=target_height)",
        "st.plotly_chart(",
        "st.pyplot(",
        "st.image(",
        "components.html(html_body",
    ):
        observations.append("shared_diagram_helpers_center_and_fullscreen_plotly_pyplot_image_html")
    else:
        failures.append("shared_diagram_helpers_missing_center_or_fullscreen_contract")


def _check_active_diagram_calls_use_fullscreen_helpers(
    failures: list[str],
    observations: list[str],
) -> None:
    active_sources = [
        "99_UI_sandbox.py",
        "apps/section_props_playground/app.py",
        "bending_page.py",
        "bending_side_view_diagram.py",
        "bending_tabs.py",
        "creep.py",
        "crack_side_view_diagram.py",
        "deflection.py",
        "inputs_page.py",
        "report_helpers.py",
        "sfd_bmd_page.py",
        "shear_page.py",
        "shrinkage.py",
    ]
    raw_call_pattern = re.compile(r"\bst\.(plotly_chart|pyplot|image)\s*\(")
    allowed_raw_substrings = {
        "st.image(report_logo, width=120)",
        'st.image(branding.get("logo_image_data"), width=120)',
    }
    offenders: list[str] = []
    for rel_path in active_sources:
        source = _read(rel_path)
        for match in raw_call_pattern.finditer(source):
            line_no = source.count("\n", 0, match.start()) + 1
            line = source.splitlines()[line_no - 1].strip()
            if any(allowed in line for allowed in allowed_raw_substrings):
                continue
            offenders.append(f"{rel_path}:{line_no}:{line}")
    if offenders:
        failures.append("active_diagram_raw_streamlit_render_calls_not_fullscreen_wrapped")
        failures.extend(offenders)
    else:
        observations.append("active_diagram_render_calls_use_fullscreen_helpers")


def _check_visible_routes(failures: list[str], observations: list[str], warnings: list[str]) -> None:
    deflection_source = _read("deflection.py")
    if _has(
        deflection_source,
        "from ui.diagrams.deflection_diagram import",
        "render_plotly_diagram",
        "build_deflected_beam_plotly",
        "beam_fig = build_deflected_beam_plotly(",
    ):
        observations.append("deflection_visible_diagram_routes_to_ui_diagrams_deflection")
    else:
        failures.append("deflection_visible_diagram_route_to_shared_module_not_proven")
    deflection_shared_render_call = (
        "render_plotly_diagram(\n"
        "                beam_fig,"
    )
    if _has(
        deflection_source,
        deflection_shared_render_call,
        'key="deflection_deflected_shape_diagram"',
        "center=True",
        "allow_fullscreen=True",
        "preserve_figure_width=True",
    ):
        observations.append("deflection_visible_diagram_preserves_centered_fixed_scale_width")
        observations.append("deflection_visible_diagram_has_fullscreen_option")
    else:
        failures.append("deflection_visible_diagram_shared_centered_fullscreen_render_not_proven")

    shear_visuals_source = _read("shear_visuals.py")
    shear_page_source = _read("shear_page.py")
    if _has(
        shear_visuals_source,
        "from ui.diagrams.shear_diagram import build_shear_cross_section_figure_from_layout",
        "def build_shear_cross_section_figure",
        "return build_shear_cross_section_figure_from_layout(",
    ) and "_render_shear_cross_section" in shear_page_source:
        observations.append("shear_section_routes_to_ui_diagrams_shear")
    else:
        failures.append("shear_section_route_to_shared_module_not_proven")

    if _has(
        shear_visuals_source,
        "from ui.diagrams import side_view_diagram as shared_side_view_diagram",
        "_build_side_view_figure = shared_side_view_diagram.build_side_view_figure",
        "def build_shear_side_view_figure",
        "_build_side_view_tension_reo(fig, model)",
        "_build_stirrup_markers(fig, model, shear_fails=shear_fails)",
    ):
        observations.append("shear_side_view_routes_to_shared_side_view_with_local_shear_overlays")
    else:
        failures.append("shear_side_view_shared_base_route_not_proven")

    if "_SHEAR_ZONE_SIDE_VIEW_FILLS" in shear_visuals_source or "_add_beam_band" in shear_visuals_source:
        warnings.append("shear_side_view_keeps_local_zone_or_band_overlay_colours")

    bending_impl = _read("ui/diagrams/bending_side_view_diagram.py")
    if _has(
        bending_impl,
        "from ui.diagrams.side_view_diagram import",
        "build_side_view_figure as _build_side_view_figure",
        "def build_bending_side_view_figure",
        "_build_side_view_figure(",
    ):
        observations.append("bending_side_view_partially_routes_to_shared_side_view_base")
    else:
        warnings.append("bending_side_view_shared_base_route_not_proven")
    for old_literal in (
        'trace.fillcolor = "rgba(255,255,255,1.0)"',
        'fillcolor="rgba(205,212,220,0.18)"',
        'line_color="rgba(35,35,35,0.82)"',
        'line_color="rgba(45,45,45,0.62)"',
        'line_color="rgba(30, 90, 180, 0.78)"',
    ):
        if old_literal in bending_impl:
            failures.append(f"bending_side_view_retains_unaligned_colour:{old_literal}")
    if _has(
        bending_impl,
        "CONCRETE_FILL_2D",
        "CONCRETE_OUTLINE",
        "DEFLECTED_FILL",
        "DEFLECTED_LINE",
        "COMPRESSION",
        "ANNOTATION_BG",
    ):
        observations.append("bending_side_view_local_overlays_use_shared_style_constants")
    else:
        failures.append("bending_side_view_shared_overlay_style_not_proven")

    crack_impl = _read("ui/diagrams/crack_side_view_diagram.py")
    if _has(
        crack_impl,
        "from ui.diagrams.side_view_diagram import",
        "build_side_view_figure as _build_side_view_figure",
        "def build_crack_side_view_figure",
        "_build_side_view_figure(",
    ):
        observations.append("crack_side_view_partially_routes_to_shared_side_view_base")
    else:
        warnings.append("crack_side_view_shared_base_route_not_proven")
    if "rgba(" in crack_impl:
        warnings.append("crack_side_view_keeps_local_crack_overlay_colours")

    if "plot_shear_step4_middepth_strain_diagram" in _read("shear_diagrams.py"):
        warnings.append("stress_or_strain_related_shear_diagrams_remain_out_of_scope")
    inputs_source = _read("inputs_page.py")
    if "build_inputs_beam_3d_figure" in inputs_source:
        warnings.append("inputs_3d_diagram_remains_local_render_path")
        if _has(
            inputs_source,
            "BASE_H = 560 if compact else 640",
            "BASE_H = 500 if compact else 580",
            'key="inputs_section_3d_diagram"',
            'key="inputs_section_3d_diagram_t_or_i"',
            "fullscreen_height=1120",
        ):
            observations.append("inputs_3d_diagram_has_larger_page_and_fullscreen_sizing")
        else:
            failures.append("inputs_3d_diagram_larger_fullscreen_sizing_not_proven")


def _check_generated_colours(failures: list[str], observations: list[str]) -> None:
    styles = importlib.import_module("ui.diagrams.diagram_styles")
    section = importlib.import_module("ui.diagrams.section_diagram")
    shear = importlib.import_module("ui.diagrams.shear_diagram")
    deflection = importlib.import_module("ui.diagrams.deflection_diagram")
    side_view = importlib.import_module("ui.diagrams.side_view_diagram")
    stress_strain = importlib.import_module("ui.diagrams.stress_strain_diagram")
    bending_side_view = importlib.import_module("ui.diagrams.bending_side_view_diagram")

    section_fig = section.build_summary_cross_section_result(layout=_rect_section_layout()).figure
    if section_fig is None:
        failures.append("section_generated_figure_missing")
    else:
        colours = _shape_colours(section_fig)
        if not colours["rects"] or colours["rects"][0] != (styles.CONCRETE_OUTLINE, styles.CONCRETE_FILL_2D):
            failures.append("section_generated_concrete_not_shared_style")
        if not any(fill == styles.REO_BOTTOM for _, fill in colours["circles"]):
            failures.append("section_generated_bottom_reo_not_shared_style")
        if not any(fill == styles.REO_TOP for _, fill in colours["circles"]):
            failures.append("section_generated_top_reo_not_shared_style")
        observations.append(
            "section_generated_colours:"
            f"concrete={colours['rects'][0] if colours['rects'] else None},"
            f"bars={sorted(set(fill for _, fill in colours['circles']))}"
        )

    shear_fig = shear.build_shear_cross_section_figure_from_layout(layout=_rect_section_layout(), height=360)
    shear_colours = _shape_colours(shear_fig)
    if not shear_colours["rects"] or shear_colours["rects"][0] != (styles.CONCRETE_OUTLINE, styles.CONCRETE_FILL_2D):
        failures.append("shear_generated_concrete_not_shared_style")
    if not any(fill == styles.REO_BOTTOM for _, fill in shear_colours["circles"]):
        failures.append("shear_generated_bottom_reo_not_shared_style")
    if not any(fill == styles.REO_TOP for _, fill in shear_colours["circles"]):
        failures.append("shear_generated_top_reo_not_shared_style")
    if not any(color == styles.LINK_STEEL for color, _ in shear_colours["lines"]):
        failures.append("shear_generated_links_not_shared_style")
    observations.append(
        "shear_generated_colours:"
        f"concrete={shear_colours['rects'][0] if shear_colours['rects'] else None},"
        f"bars={sorted(set(fill for _, fill in shear_colours['circles']))},"
        f"links={sorted(set(color for color, _ in shear_colours['lines']))}"
    )

    x = np.linspace(0.0, 6000.0, 7)
    w = np.array([0.0, -3.0, -7.0, -10.0, -7.0, -3.0, 0.0])
    defl_fig = deflection.build_deflected_shape_figure(
        x,
        w,
        6000.0,
        600.0,
        support_type="Simply supported",
        show_legend=True,
    )
    if defl_fig.layout.paper_bgcolor != styles.DIAGRAM_BG:
        failures.append("deflection_generated_bg_not_shared_style")
    if getattr(defl_fig.data[0], "fillcolor", None) != styles.DIAGRAM_TRANSPARENT:
        failures.append("deflection_generated_undeformed_reference_fill_not_transparent")
    if getattr(defl_fig.data[1], "fillcolor", None) != styles.CONCRETE_FILL_2D:
        failures.append("deflection_generated_beam_body_fill_not_concrete_style")
    if getattr(defl_fig.data[2].line, "color", None) != styles.DEFLECTED_LINE:
        failures.append("deflection_generated_deflection_cue_not_shared_style")
    observations.append(
        "deflection_generated_colours:"
        f"reference={getattr(defl_fig.data[0], 'fillcolor', None)},"
        f"beam={getattr(defl_fig.data[1], 'fillcolor', None)},"
        f"cue={getattr(defl_fig.data[2].line, 'color', None)}"
    )

    side_fig = side_view.build_side_view_figure(
        length_m=8.0,
        beam_depth_m=0.6,
        height=side_view.SIDE_VIEW_VISUAL_HEIGHT,
        support_condition="simply_supported",
    )
    model = {
        "side_view_display": {
            "display_length_m": 8.0,
            "display_start_m": 0.0,
            "scale_factor": 1.0,
            "has_breaks": False,
        },
        "D_m": 0.6,
        "total_length_m": 8.0,
        "bottom_layers": [{"db": 20.0}],
        "top_layers": [{"db": 16.0}],
    }
    side_view.build_side_view_tension_reo(side_fig, model)
    trace_colours = [getattr(trace.line, "color", None) for trace in side_fig.data]
    if styles.REO_BOTTOM not in trace_colours or styles.REO_TOP not in trace_colours:
        failures.append("side_view_generated_reo_traces_not_shared_style")
    observations.append(f"side_view_generated_reo_colours:{trace_colours}")

    bending_state = {
        "b": 450.0,
        "D": 750.0,
        "d": 690.0,
        "c": 160.0,
        "eps_c": 0.003,
        "eps_s": 0.002,
        "gamma": 0.8,
        "fs_t": 500.0,
        "fc": 40.0,
        "alpha2": 0.85,
    }
    bending_layout = _rect_section_layout()
    bending_layout.update(
        {
            "b": 450.0,
            "D": 750.0,
            "cage": {"x0": 40.0, "y0": 40.0, "x1": 410.0, "y1": 710.0},
            "lig": {"d": 0.0, "legs": 0},
        }
    )
    bend_fig = stress_strain.plot_stress_strain_profiles(
        bending_state,
        state_label="ULS",
        layout=bending_layout,
    )
    bend_rects = [
        (getattr(shape.line, "color", None), getattr(shape, "fillcolor", None))
        for shape in bend_fig.layout.shapes or []
        if shape.type == "rect"
    ]
    if not bend_rects or bend_rects[0] != (styles.CONCRETE_OUTLINE, styles.CONCRETE_FILL_2D):
        failures.append("bending_stress_strain_section_fill_not_shared_style")
    if len(bend_rects) < 2 or bend_rects[1][0] != styles.COMPRESSION:
        failures.append("bending_stress_strain_compression_block_not_compression_style")
    observations.append(f"bending_stress_strain_section_rect_colours:{bend_rects[:2]}")

    bending_side = go.Figure()
    bending_side.add_trace(
        go.Scatter(
            x=[0.0, 1.0, 1.0, 0.0, 0.0],
            y=[0.0, 0.0, 1.0, 1.0, 0.0],
            fill="toself",
            mode="lines",
            fillcolor="rgba(255,255,255,1.0)",
            line=dict(color="rgba(45,45,45,0.62)", width=2.0),
        )
    )
    bending_side_view._make_bending_beam_fill_white(bending_side)
    beam_trace = bending_side.data[0]
    if getattr(beam_trace, "fillcolor", None) != styles.CONCRETE_FILL_2D:
        failures.append("bending_side_view_beam_fill_not_shared_concrete")
    if getattr(getattr(beam_trace, "line", None), "color", None) != styles.CONCRETE_OUTLINE:
        failures.append("bending_side_view_beam_outline_not_shared_concrete")
    compression_source = go.Figure()
    compression_source.add_shape(
        type="rect",
        xref="x3",
        yref="y3",
        x0=0.0,
        x1=1.0,
        y0=0.0,
        y1=250.0,
        line=dict(color=styles.COMPRESSION),
        fillcolor="rgba(200,45,45,0.14)",
    )
    if bending_side_view._compression_zone_span_from_stress_figure(compression_source, D_src=750.0) is None:
        failures.append("bending_side_view_compression_shared_colour_not_detected")
    observations.append(
        "bending_side_view_generated_beam_colours:"
        f"fill={getattr(beam_trace, 'fillcolor', None)},"
        f"line={getattr(getattr(beam_trace, 'line', None), 'color', None)}"
    )


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    observations: list[str] = []

    _check_inputs_paths(failures, observations, warnings)
    _check_migrated_style_sources(failures)
    _check_shared_plotly_render_helper(failures, observations)
    _check_active_diagram_calls_use_fullscreen_helpers(failures, observations)
    _check_visible_routes(failures, observations, warnings)
    _check_generated_colours(failures, observations)

    if failures:
        print("DIAGRAM_VISUAL_LIVE_PATH_SNAPSHOT FAIL")
        for failure in failures:
            print(f"- {failure}")
        if warnings:
            print("Recorded legacy/local observations:")
            for warning in warnings:
                print(f"- {warning}")
        return 1

    print("DIAGRAM_VISUAL_LIVE_PATH_SNAPSHOT PASS")
    print("- migrated visible paths still consume shared style contract")
    print("- Inputs fast inline SVG now consumes shared style constants")
    print("- remaining legacy/local visible paths recorded without failing")
    for observation in observations:
        print(f"- {observation}")
    if warnings:
        print("Recorded legacy/local paths:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
