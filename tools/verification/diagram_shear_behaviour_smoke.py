"""Smoke checks for extracted shear behaviour diagram frame builders."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.disable(logging.WARNING)

import shear_page  # noqa: E402
import shear_visuals  # noqa: E402
from ui.diagrams.principal_stress_cue_diagram import (  # noqa: E402
    PRINCIPAL_STRESS_AXES_CUE_SCALE,
    add_principal_stress_orientation_square,
    build_principal_stress_axes_cue,
)
from ui.diagrams.shear_behaviour_diagram import build_shear_behaviour_base_figure  # noqa: E402
from ui.diagrams.shear_behaviour_diagram import build_shear_behaviour_load_shapes  # noqa: E402
from ui.diagrams.shear_behaviour_diagram import (  # noqa: E402
    STM_SNAP_X_RATIOS,
    STM_SNAP_Y_DV_FRACS,
    add_force_line,
    add_load_flow_overlay,
    add_ordered_trajectory_family,
    add_principal_shear_crack_example,
    add_sparse_trajectory_arrows,
    add_stm_axis_vertical,
    add_stm_flow_polyline,
    add_stm_joint_angle_annotation,
    add_stm_member,
    add_stm_overlay_labels,
    add_shear_behaviour_beam_band,
    add_strut_tie_node,
    add_trajectory_family,
    add_trajectory_direction_arrow,
    beam_depth_scale,
    blend_x,
    build_compression_family,
    build_compressive_trajectories,
    build_crack_cues,
    build_shear_behaviour_support_shapes,
    build_shear_behaviour_zones,
    build_tensile_trajectories,
    build_tension_family,
    cantilever_principal_crack_hits,
    cantilever_behaviour_zones,
    cantilever_refine_crack_hit_for_compression_field,
    clamp_field_points,
    compute_stm_cantilever_d_region_nodes,
    compute_stm_simply_supported_d_region_nodes,
    compute_stress_field_geometry,
    compute_trajectory_count,
    compute_trajectory_half_widths,
    densify_polyline,
    display_zone_length,
    field_line_spec,
    field_y_limits,
    linear_interpolate_points,
    mirror_field_line,
    mirror_trajectory_about_middepth,
    parabolic_trajectory,
    polyline_polyline_best_hit,
    polyline_segment_best_hit,
    polyline_tangent_at_x,
    polyline_y_at_x,
    principal_stress_marker_state,
    render_field_cantilever_eccentric,
    render_field_cantilever_tip,
    render_field_cantilever_udl,
    render_field_ss_eccentric_point,
    render_field_ss_midspan_point,
    render_field_ss_near_support_point,
    render_field_ss_udl,
    render_principal_stress_cantilever_eccentric,
    render_principal_stress_cantilever_tip,
    render_principal_stress_cantilever_udl,
    render_principal_stress_ss_eccentric_point,
    render_principal_stress_ss_midspan_point,
    render_principal_stress_ss_near_support_point,
    render_principal_stress_ss_udl,
    render_stm_flow_overlay,
    render_stm_overlay,
    render_strut_tie_cantilever_tip,
    render_strut_tie_ss_udl,
    sample_curve_point_and_tangent,
    sample_anchor_band,
    sample_beam_y,
    scaled_rgba_alpha,
    segment_intersection,
    shear_crack_x_band_m,
    support_d_region_bounds,
    support_edge_y_bot,
    support_edge_y_top,
    support_zone_x_left,
    support_zone_x_right,
    symmetric_arch,
    stm_snap_inner_top_left,
    stm_snap_inner_top_right,
    stm_snap_ratio_to_grid,
    stm_y_snap_levels_dv,
    trajectory_bow_scale,
    trajectory_end_curvature_boost,
    trajectory_visual_weight,
)


def _signature(fig) -> tuple[int, int, int]:
    return (
        len(fig.data),
        len(fig.layout.shapes or []),
        len(fig.layout.annotations or []),
    )


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def _check_behaviour_base() -> list[str]:
    kwargs = dict(length_m=6.0, beam_depth_m=0.75, height=420)
    legacy_fig = shear_visuals._build_behaviour_figure(**kwargs)
    module_fig = build_shear_behaviour_base_figure(**kwargs, width=shear_visuals.BEHAVIOUR_VISUAL_WIDTH)
    failures: list[str] = []
    if _signature(legacy_fig) != _signature(module_fig):
        failures.append("behaviour_base_signature_changed")
    if int(legacy_fig.layout.height or 0) != 420:
        failures.append("behaviour_base_height_not_preserved")
    if int(legacy_fig.layout.width or 0) != int(shear_visuals.BEHAVIOUR_VISUAL_WIDTH):
        failures.append("behaviour_base_width_not_preserved")
    if legacy_fig.layout.xaxis.visible is not False:
        failures.append("behaviour_base_x_axis_visible")
    if legacy_fig.layout.yaxis.visible is not False:
        failures.append("behaviour_base_y_axis_visible")
    if legacy_fig.layout.yaxis.scaleanchor != "x":
        failures.append("behaviour_base_y_axis_not_scaleanchored")
    return failures


def _base_load_model(case: str) -> dict:
    return {
        "case": case,
        "mode": "ULS",
        "span_m": 6.0,
        "total_length_m": 6.0,
        "D_m": 0.75,
        "w_value": 22.5,
        "point_value": 125.0,
        "a_m": 2.4,
        "a_udl_m": 3.0,
        "a_cant_m": 2.0,
    }


def _support_model(*, support_condition: str = "simply_supported", support_pair=None) -> dict:
    support_positions = [0.0] if support_condition == "cantilever" else [0.0, 6.0]
    return {
        "case": shear_visuals._DEFAULT_LOADING_CASE,
        "mode": "ULS",
        "span_m": 6.0,
        "total_length_m": 6.0,
        "D_m": 0.75,
        "d_m": 0.66,
        "support_condition": support_condition,
        "support_positions": support_positions,
        "support_pair": support_pair,
    }


def _check_behaviour_support_shapes() -> list[str]:
    failures: list[str] = []
    models = [
        _support_model(),
        _support_model(support_pair=("Fixed", "Pinned")),
        _support_model(support_condition="cantilever"),
    ]
    for idx, model in enumerate(models):
        module_fig = build_shear_behaviour_base_figure(
            length_m=6.0,
            beam_depth_m=0.75,
            height=420,
            width=shear_visuals.BEHAVIOUR_VISUAL_WIDTH,
        )
        legacy_fig = shear_visuals._build_behaviour_figure(length_m=6.0, beam_depth_m=0.75, height=420)
        add_shear_behaviour_beam_band(module_fig, model["total_length_m"], model["D_m"])
        shear_visuals._add_beam_band(legacy_fig, model["total_length_m"], model["D_m"])
        build_shear_behaviour_support_shapes(module_fig, model)
        shear_visuals._build_shear_behaviour_support_shapes(legacy_fig, model)
        if _signature(module_fig) != _signature(legacy_fig):
            failures.append(f"behaviour_support_signature_changed_{idx}")
        module_shape_types = [shape.type for shape in module_fig.layout.shapes or []]
        legacy_shape_types = [shape.type for shape in legacy_fig.layout.shapes or []]
        if module_shape_types != legacy_shape_types:
            failures.append(f"behaviour_support_shape_types_changed_{idx}")
        if idx == 0 and "circle" not in module_shape_types:
            failures.append("behaviour_support_roller_missing")
        if idx == 2 and module_shape_types.count("line") < 6:
            failures.append("behaviour_support_cantilever_hatching_missing")
    return failures


def _check_behaviour_load_shapes() -> list[str]:
    failures: list[str] = []
    cases = [
        shear_visuals._DEFAULT_LOADING_CASE,
        "Simple beam – point load at centre",
    ]
    for idx, case in enumerate(cases):
        module_fig = build_shear_behaviour_base_figure(
            length_m=6.0,
            beam_depth_m=0.75,
            height=420,
            width=shear_visuals.BEHAVIOUR_VISUAL_WIDTH,
        )
        legacy_fig = shear_visuals._build_behaviour_figure(length_m=6.0, beam_depth_m=0.75, height=420)
        model = _base_load_model(case)
        build_shear_behaviour_load_shapes(module_fig, model, show_labels=True)
        shear_visuals._build_shear_behaviour_load_shapes(legacy_fig, model, show_labels=True)
        if _signature(module_fig) != _signature(legacy_fig):
            failures.append(f"behaviour_load_signature_changed_{idx}")
        module_annotations = _annotation_text(module_fig)
        legacy_annotations = _annotation_text(legacy_fig)
        if module_annotations != legacy_annotations:
            failures.append(f"behaviour_load_annotations_changed_{idx}")
        if case == shear_visuals._DEFAULT_LOADING_CASE and not any("w*" in text for text in module_annotations):
            failures.append("behaviour_load_udl_label_missing")
        if "point load" in case and not any("P*" in text for text in module_annotations):
            failures.append("behaviour_load_point_label_missing")
    return failures


def _check_behaviour_zones() -> list[str]:
    failures: list[str] = []
    models = [
        _support_model(),
        _support_model(support_condition="cantilever"),
    ]
    for idx, model in enumerate(models):
        module_fig = build_shear_behaviour_base_figure(
            length_m=6.0,
            beam_depth_m=0.75,
            height=420,
            width=shear_visuals.BEHAVIOUR_VISUAL_WIDTH,
        )
        legacy_fig = shear_visuals._build_behaviour_figure(length_m=6.0, beam_depth_m=0.75, height=420)
        build_shear_behaviour_zones(module_fig, model, "test")
        shear_visuals._build_shear_behaviour_zones(legacy_fig, model, "test")
        if support_d_region_bounds(model) != shear_visuals._support_d_region_bounds(model):
            failures.append(f"behaviour_zone_bounds_changed_{idx}")
        if _signature(module_fig) != _signature(legacy_fig):
            failures.append(f"behaviour_zone_signature_changed_{idx}")
        if _annotation_text(module_fig) != _annotation_text(legacy_fig):
            failures.append(f"behaviour_zone_annotations_changed_{idx}")
        zone_labels = _annotation_text(module_fig)
        if "D-region" not in zone_labels:
            failures.append(f"behaviour_zone_d_region_label_missing_{idx}")
        if idx == 0 and not any("Flexural-dominated" in label for label in zone_labels):
            failures.append("behaviour_zone_flexural_label_missing")
        if idx == 1 and not any("flexural-shear" in label for label in zone_labels):
            failures.append("behaviour_zone_cantilever_shear_span_label_missing")
    return failures


def _check_field_line_primitives() -> list[str]:
    failures: list[str] = []
    points = [(0.0, -0.2), (0.35, 0.32), (0.7, 0.9)]

    if field_y_limits(0.7) != shear_visuals._field_y_limits(0.7):
        failures.append("field_y_limits_wrapper_changed")
    if clamp_field_points(points, 0.7) != shear_visuals._clamp_field_points(points, 0.7):
        failures.append("clamp_field_points_wrapper_changed")

    module_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    legacy_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_force_line(
        module_fig,
        points,
        "rgba(10,20,30,0.9)",
        3.0,
        label="Force",
        label_pos=(0.4, 0.5),
        beam_depth_m=0.7,
    )
    shear_visuals._add_force_line(
        legacy_fig,
        points,
        "rgba(10,20,30,0.9)",
        3.0,
        label="Force",
        label_pos=(0.4, 0.5),
        beam_depth_m=0.7,
    )
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("force_line_signature_changed")
    if _annotation_text(module_fig) != _annotation_text(legacy_fig):
        failures.append("force_line_annotations_changed")

    spec = field_line_spec(points, width=2.2, opacity=0.7, label="Spec", label_pos=(0.2, 0.4))
    if spec != shear_visuals._field_line_spec(points, width=2.2, opacity=0.7, label="Spec", label_pos=(0.2, 0.4)):
        failures.append("field_line_spec_wrapper_changed")
    if mirror_field_line(spec, 2.0) != shear_visuals._mirror_field_line(spec, 2.0):
        failures.append("mirror_field_line_wrapper_changed")

    module_family_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    legacy_family_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    lines = [
        spec,
        field_line_spec([(0.1, 0.1), (0.3, 0.4), (0.6, 0.5)], width=1.5, opacity=0.35),
    ]
    build_tension_family(module_family_fig, lines)
    build_compression_family(module_family_fig, lines[:1])
    build_crack_cues(module_family_fig, lines[:1])
    add_trajectory_family(module_family_fig, [[(0.0, 0.1), (0.4, 0.5), (0.8, 0.2)]], "rgba(1,2,3,0.4)")
    shear_visuals._build_tension_family(legacy_family_fig, lines)
    shear_visuals._build_compression_family(legacy_family_fig, lines[:1])
    shear_visuals._build_crack_cues(legacy_family_fig, lines[:1])
    shear_visuals._add_trajectory_family(legacy_family_fig, [[(0.0, 0.1), (0.4, 0.5), (0.8, 0.2)]], "rgba(1,2,3,0.4)")
    if _signature(module_family_fig) != _signature(legacy_family_fig):
        failures.append("field_family_signature_changed")
    if _annotation_text(module_family_fig) != _annotation_text(legacy_family_fig):
        failures.append("field_family_annotations_changed")
    if len(module_family_fig.data) != 5:
        failures.append("field_family_trace_count_changed")

    field_model = {
        "span_m": 4.0,
        "total_length_m": 4.0,
        "D_m": 0.7,
        "d_m": 0.62,
        "support_condition": "simply_supported",
    }
    module_field_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    legacy_field_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    render_field_ss_midspan_point(module_field_fig, field_model)
    shear_visuals._render_field_ss_midspan_point(legacy_field_fig, field_model)
    if _signature(module_field_fig) != _signature(legacy_field_fig):
        failures.append("render_field_ss_midspan_point_signature_changed")
    if _annotation_text(module_field_fig) != _annotation_text(legacy_field_fig):
        failures.append("render_field_ss_midspan_point_annotations_changed")
    if len(module_field_fig.data) != 11:
        failures.append("render_field_ss_midspan_point_trace_count_changed")

    module_udl_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    legacy_udl_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    render_field_ss_udl(module_udl_fig, field_model)
    shear_visuals._render_field_ss_udl(legacy_udl_fig, field_model)
    if _signature(module_udl_fig) != _signature(legacy_udl_fig):
        failures.append("render_field_ss_udl_signature_changed")
    if _annotation_text(module_udl_fig) != _annotation_text(legacy_udl_fig):
        failures.append("render_field_ss_udl_annotations_changed")
    if len(module_udl_fig.data) != 8:
        failures.append("render_field_ss_udl_trace_count_changed")

    def _check_eccentric_case(a_m: float, suffix: str) -> None:
        eccentric_model = dict(field_model, a_m=a_m)
        module_eccentric_fig = build_shear_behaviour_base_figure(
            length_m=4.0,
            beam_depth_m=0.7,
            height=260,
            width=520,
        )
        legacy_eccentric_fig = build_shear_behaviour_base_figure(
            length_m=4.0,
            beam_depth_m=0.7,
            height=260,
            width=520,
        )
        render_field_ss_eccentric_point(module_eccentric_fig, eccentric_model)
        shear_visuals._render_field_ss_eccentric_point(legacy_eccentric_fig, eccentric_model)
        if _signature(module_eccentric_fig) != _signature(legacy_eccentric_fig):
            failures.append(f"render_field_ss_eccentric_point_signature_changed_{suffix}")
        if _annotation_text(module_eccentric_fig) != _annotation_text(legacy_eccentric_fig):
            failures.append(f"render_field_ss_eccentric_point_annotations_changed_{suffix}")
        if len(module_eccentric_fig.data) != 10:
            failures.append(f"render_field_ss_eccentric_point_trace_count_changed_{suffix}")

    _check_eccentric_case(1.2, "left")
    _check_eccentric_case(3.0, "right")

    def _check_near_support_case(a_m: float, suffix: str) -> None:
        near_support_model = dict(field_model, a_m=a_m)
        module_near_fig = build_shear_behaviour_base_figure(
            length_m=4.0,
            beam_depth_m=0.7,
            height=260,
            width=520,
        )
        legacy_near_fig = build_shear_behaviour_base_figure(
            length_m=4.0,
            beam_depth_m=0.7,
            height=260,
            width=520,
        )
        render_field_ss_near_support_point(module_near_fig, near_support_model)
        shear_visuals._render_field_ss_near_support_point(legacy_near_fig, near_support_model)
        if _signature(module_near_fig) != _signature(legacy_near_fig):
            failures.append(f"render_field_ss_near_support_point_signature_changed_{suffix}")
        if _annotation_text(module_near_fig) != _annotation_text(legacy_near_fig):
            failures.append(f"render_field_ss_near_support_point_annotations_changed_{suffix}")
        if len(module_near_fig.data) != 9:
            failures.append(f"render_field_ss_near_support_point_trace_count_changed_{suffix}")

    _check_near_support_case(0.8, "left")
    _check_near_support_case(3.2, "right")

    cantilever_model = dict(field_model, support_condition="cantilever", a_cant_m=2.0)

    module_cantilever_tip_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    legacy_cantilever_tip_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    render_field_cantilever_tip(module_cantilever_tip_fig, cantilever_model)
    shear_visuals._render_field_cantilever_tip(legacy_cantilever_tip_fig, cantilever_model)
    if _signature(module_cantilever_tip_fig) != _signature(legacy_cantilever_tip_fig):
        failures.append("render_field_cantilever_tip_signature_changed")
    if _annotation_text(module_cantilever_tip_fig) != _annotation_text(legacy_cantilever_tip_fig):
        failures.append("render_field_cantilever_tip_annotations_changed")
    if len(module_cantilever_tip_fig.data) != 7:
        failures.append("render_field_cantilever_tip_trace_count_changed")

    module_cantilever_udl_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    legacy_cantilever_udl_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    render_field_cantilever_udl(module_cantilever_udl_fig, cantilever_model)
    shear_visuals._render_field_cantilever_udl(legacy_cantilever_udl_fig, cantilever_model)
    if _signature(module_cantilever_udl_fig) != _signature(legacy_cantilever_udl_fig):
        failures.append("render_field_cantilever_udl_signature_changed")
    if _annotation_text(module_cantilever_udl_fig) != _annotation_text(legacy_cantilever_udl_fig):
        failures.append("render_field_cantilever_udl_annotations_changed")
    if len(module_cantilever_udl_fig.data) != 5:
        failures.append("render_field_cantilever_udl_trace_count_changed")

    module_cantilever_eccentric_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    legacy_cantilever_eccentric_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    render_field_cantilever_eccentric(module_cantilever_eccentric_fig, cantilever_model)
    shear_visuals._render_field_cantilever_eccentric(legacy_cantilever_eccentric_fig, cantilever_model)
    if _signature(module_cantilever_eccentric_fig) != _signature(legacy_cantilever_eccentric_fig):
        failures.append("render_field_cantilever_eccentric_signature_changed")
    if _annotation_text(module_cantilever_eccentric_fig) != _annotation_text(legacy_cantilever_eccentric_fig):
        failures.append("render_field_cantilever_eccentric_annotations_changed")
    if len(module_cantilever_eccentric_fig.data) != 5:
        failures.append("render_field_cantilever_eccentric_trace_count_changed")
    return failures


def _check_trajectory_utilities() -> list[str]:
    failures: list[str] = []
    pts = [(0.0, 0.1), (0.4, 0.5), (0.8, 0.2), (1.0, 0.4)]

    color_cases = [
        ("rgba(10,20,30,0.8)", 0.5),
        ("rgb(10,20,30)", 0.5),
        ("rgba(10,20,30,bad)", 0.5),
        ("rgba(10,20,30,0.8)", 2.0),
    ]
    for idx, (color, alpha_scale) in enumerate(color_cases):
        if scaled_rgba_alpha(color, alpha_scale) != shear_visuals._scaled_rgba_alpha(color, alpha_scale):
            failures.append(f"scaled_rgba_alpha_wrapper_changed_{idx}")

    for idx, args in enumerate([(0, 1), (0, 4), (2, 4)]):
        if trajectory_visual_weight(*args) != shear_visuals._trajectory_visual_weight(*args):
            failures.append(f"trajectory_visual_weight_wrapper_changed_{idx}")

    if sample_curve_point_and_tangent(pts, 0.5) != shear_visuals._sample_curve_point_and_tangent(pts, 0.5):
        failures.append("sample_curve_point_and_tangent_wrapper_changed")
    if sample_curve_point_and_tangent([(0.0, 0.1), (0.2, 0.2)], 0.5) is not None:
        failures.append("sample_curve_short_input_not_none")
    if sample_curve_point_and_tangent([(0.0, 0.1), (0.0, 0.1), (0.0, 0.1)], 0.5) is not None:
        failures.append("sample_curve_zero_tangent_not_none")

    module_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    legacy_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_trajectory_direction_arrow(
        module_fig,
        pts,
        "rgba(10,20,30,0.8)",
        beam_depth_m=0.7,
        curve_fraction=0.5,
        alpha_scale=0.6,
        reverse=True,
    )
    shear_visuals._add_trajectory_direction_arrow(
        legacy_fig,
        pts,
        "rgba(10,20,30,0.8)",
        beam_depth_m=0.7,
        curve_fraction=0.5,
        alpha_scale=0.6,
        reverse=True,
    )
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("trajectory_direction_arrow_signature_changed")
    if [annotation.arrowcolor for annotation in module_fig.layout.annotations or []] != [
        annotation.arrowcolor for annotation in legacy_fig.layout.annotations or []
    ]:
        failures.append("trajectory_direction_arrow_color_changed")

    sparse_lines = [
        [(0.0, 0.1), (0.2, 0.2), (0.4, 0.3), (0.6, 0.25)],
        [(0.0, 0.2), (0.3, 0.45), (0.6, 0.25), (0.9, 0.4)],
        [(0.0, 0.3), (0.2, 0.45), (0.5, 0.5), (0.8, 0.2)],
    ]
    module_sparse_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    legacy_sparse_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_sparse_trajectory_arrows(module_sparse_fig, sparse_lines, "rgba(10,20,30,0.8)", beam_depth_m=0.7)
    shear_visuals._add_sparse_trajectory_arrows(legacy_sparse_fig, sparse_lines, "rgba(10,20,30,0.8)", beam_depth_m=0.7)
    if _signature(module_sparse_fig) != _signature(legacy_sparse_fig):
        failures.append("sparse_trajectory_arrows_signature_changed")
    if len(module_sparse_fig.layout.annotations or []) != 2:
        failures.append("sparse_trajectory_arrows_annotation_count_changed")

    ordered_module_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    ordered_legacy_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_ordered_trajectory_family(
        ordered_module_fig,
        sparse_lines,
        "rgba(10,20,30,0.8)",
        width=2.9,
        opacity=0.7,
        smoothing=0.4,
        beam_depth_m=0.7,
        line_shape="linear",
    )
    shear_visuals._add_ordered_trajectory_family(
        ordered_legacy_fig,
        sparse_lines,
        "rgba(10,20,30,0.8)",
        width=2.9,
        opacity=0.7,
        smoothing=0.4,
        beam_depth_m=0.7,
        line_shape="linear",
    )
    if _signature(ordered_module_fig) != _signature(ordered_legacy_fig):
        failures.append("ordered_trajectory_family_signature_changed")
    if [trace.line.width for trace in ordered_module_fig.data] != [trace.line.width for trace in ordered_legacy_fig.data]:
        failures.append("ordered_trajectory_family_widths_changed")
    return failures


def _check_load_flow_overlay() -> list[str]:
    failures: list[str] = []
    lines = [
        [(i / 10.0, 0.1 + 0.05 * (i % 3)) for i in range(10)],
        [(i / 10.0, 0.2 + 0.04 * (i % 4)) for i in range(10)],
    ]

    static_module_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    static_legacy_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_load_flow_overlay(
        static_module_fig,
        lines,
        "rgba(10,20,30,0.8)",
        beam_depth_m=0.7,
        line_indices=[0, 0, 99],
    )
    shear_visuals._add_load_flow_overlay(
        static_legacy_fig,
        lines,
        "rgba(10,20,30,0.8)",
        beam_depth_m=0.7,
        line_indices=[0, 0, 99],
    )
    if _signature(static_module_fig) != _signature(static_legacy_fig):
        failures.append("load_flow_static_signature_changed")
    if len(static_module_fig.data) != 2:
        failures.append("load_flow_static_dedup_trace_count_changed")
    if len(static_module_fig.layout.annotations or []) != 6:
        failures.append("load_flow_static_arrow_count_changed")

    animated_module_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    animated_legacy_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_load_flow_overlay(
        animated_module_fig,
        lines,
        "rgba(10,20,30,0.8)",
        beam_depth_m=0.7,
        line_indices=[1],
        outward_from_centre=True,
        animate_motion=True,
    )
    shear_visuals._add_load_flow_overlay(
        animated_legacy_fig,
        lines,
        "rgba(10,20,30,0.8)",
        beam_depth_m=0.7,
        line_indices=[1],
        outward_from_centre=True,
        animate_motion=True,
    )
    if _signature(animated_module_fig) != _signature(animated_legacy_fig):
        failures.append("load_flow_animated_signature_changed")
    animated_meta = [getattr(trace, "meta", None) for trace in animated_module_fig.data if getattr(trace, "meta", None)]
    legacy_meta = [getattr(trace, "meta", None) for trace in animated_legacy_fig.data if getattr(trace, "meta", None)]
    if animated_meta != legacy_meta:
        failures.append("load_flow_animated_meta_changed")
    if len(animated_meta) != 2:
        failures.append("load_flow_animated_meta_count_changed")
    if len(animated_module_fig.layout.annotations or []) != 2:
        failures.append("load_flow_outward_arrow_count_changed")
    return failures


def _check_stm_flow_polyline() -> list[str]:
    failures: list[str] = []
    pts = [(0.0, 0.1), (0.4, 0.5), (0.8, 0.2)]

    if linear_interpolate_points((0.0, 0.0), (1.0, 1.0), n=4) != shear_visuals._linear_interpolate_points(
        (0.0, 0.0), (1.0, 1.0), n=4
    ):
        failures.append("linear_interpolate_points_wrapper_changed")
    if densify_polyline(pts, n_per_seg=5) != shear_visuals._densify_polyline(pts, n_per_seg=5):
        failures.append("densify_polyline_wrapper_changed")
    if densify_polyline([(0.1, 0.2)], n_per_seg=5) != [(0.1, 0.2)]:
        failures.append("densify_single_point_changed")

    animated_module_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    animated_legacy_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_stm_flow_polyline(
        animated_module_fig,
        pts,
        "rgba(10,20,30,0.8)",
        beam_depth_m=0.7,
        animate_motion=True,
    )
    shear_visuals._add_stm_flow_polyline(
        animated_legacy_fig,
        pts,
        "rgba(10,20,30,0.8)",
        beam_depth_m=0.7,
        animate_motion=True,
    )
    if _signature(animated_module_fig) != _signature(animated_legacy_fig):
        failures.append("stm_flow_polyline_animated_signature_changed")
    animated_meta = [getattr(trace, "meta", None) for trace in animated_module_fig.data if getattr(trace, "meta", None)]
    legacy_meta = [getattr(trace, "meta", None) for trace in animated_legacy_fig.data if getattr(trace, "meta", None)]
    if animated_meta != legacy_meta:
        failures.append("stm_flow_polyline_animated_meta_changed")
    if len(animated_module_fig.layout.annotations or []) != 2:
        failures.append("stm_flow_polyline_arrow_count_changed")

    static_module_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    static_legacy_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_stm_flow_polyline(
        static_module_fig,
        pts,
        "rgba(10,20,30,0.8)",
        beam_depth_m=0.7,
        animate_motion=False,
    )
    shear_visuals._add_stm_flow_polyline(
        static_legacy_fig,
        pts,
        "rgba(10,20,30,0.8)",
        beam_depth_m=0.7,
        animate_motion=False,
    )
    if _signature(static_module_fig) != _signature(static_legacy_fig):
        failures.append("stm_flow_polyline_static_signature_changed")
    if len(static_module_fig.data) != 1:
        failures.append("stm_flow_polyline_static_trace_count_changed")

    ss_flow_model = {
        "total_length_m": 4.0,
        "span_m": 4.0,
        "D_m": 0.7,
        "d_m": 0.62,
        "support_condition": "simply_supported",
        "theta_v_deg": 36.5,
        "show_stm_flow": True,
    }
    cantilever_flow_model = dict(ss_flow_model, support_condition="cantilever")

    def _check_flow_overlay(case_kind: str, flow_model: dict, suffix: str, expected_data: int, expected_annotations: int) -> None:
        module_flow_fig = build_shear_behaviour_base_figure(
            length_m=4.0,
            beam_depth_m=0.7,
            height=260,
            width=520,
        )
        legacy_flow_fig = build_shear_behaviour_base_figure(
            length_m=4.0,
            beam_depth_m=0.7,
            height=260,
            width=520,
        )
        render_stm_flow_overlay(module_flow_fig, flow_model, case_kind, theta_v_deg=flow_model["theta_v_deg"])
        shear_visuals._render_stm_flow_overlay(legacy_flow_fig, flow_model, case_kind)
        if _signature(module_flow_fig) != _signature(legacy_flow_fig):
            failures.append(f"render_stm_flow_overlay_signature_changed_{suffix}")
        module_meta = [getattr(trace, "meta", None) for trace in module_flow_fig.data if getattr(trace, "meta", None)]
        legacy_meta = [getattr(trace, "meta", None) for trace in legacy_flow_fig.data if getattr(trace, "meta", None)]
        if module_meta != legacy_meta:
            failures.append(f"render_stm_flow_overlay_meta_changed_{suffix}")
        if len(module_flow_fig.data) != expected_data:
            failures.append(f"render_stm_flow_overlay_trace_count_changed_{suffix}")
        if len(module_flow_fig.layout.annotations or []) != expected_annotations:
            failures.append(f"render_stm_flow_overlay_arrow_count_changed_{suffix}")

    _check_flow_overlay("ss_udl", ss_flow_model, "ss", expected_data=16, expected_annotations=16)
    _check_flow_overlay("cantilever_tip", cantilever_flow_model, "cantilever", expected_data=8, expected_annotations=8)
    _check_flow_overlay("fallback_simple", ss_flow_model, "fallback", expected_data=16, expected_annotations=16)

    hidden_flow_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    render_stm_flow_overlay(
        hidden_flow_fig,
        dict(ss_flow_model, show_stm_flow=False),
        "ss_udl",
        theta_v_deg=ss_flow_model["theta_v_deg"],
    )
    if _signature(hidden_flow_fig) != (0, 0, 0):
        failures.append("render_stm_flow_overlay_hidden_not_noop")
    return failures


def _check_trajectory_geometry_helpers() -> list[str]:
    failures: list[str] = []
    pts = [(0.0, 0.1), (0.4, 0.5), (0.8, 0.2)]

    if blend_x(6.0, 0.25) != shear_visuals._blend_x(6.0, 0.25):
        failures.append("blend_x_wrapper_changed")
    if parabolic_trajectory(0.0, 1.0, 0.1, 0.5, n=7) != shear_visuals._parabolic_trajectory(
        0.0, 1.0, 0.1, 0.5, n=7
    ):
        failures.append("parabolic_trajectory_wrapper_changed")
    if symmetric_arch(0.0, 1.0, 0.6, 0.2, n=9) != shear_visuals._symmetric_arch(
        0.0, 1.0, 0.6, 0.2, n=9
    ):
        failures.append("symmetric_arch_wrapper_changed")
    if mirror_trajectory_about_middepth(pts, 0.7) != shear_visuals._mirror_trajectory_about_middepth(pts, 0.7):
        failures.append("mirror_trajectory_wrapper_changed")
    if support_zone_x_left() != shear_visuals._support_zone_x_left():
        failures.append("support_zone_left_wrapper_changed")
    if support_zone_x_right(6.0) != shear_visuals._support_zone_x_right(6.0):
        failures.append("support_zone_right_wrapper_changed")
    if support_edge_y_top(0.7) != shear_visuals._support_edge_y_top(0.7):
        failures.append("support_edge_top_wrapper_changed")
    if support_edge_y_bot(0.7) != shear_visuals._support_edge_y_bot(0.7):
        failures.append("support_edge_bot_wrapper_changed")
    if STM_SNAP_X_RATIOS != shear_visuals._STM_SNAP_X_RATIOS:
        failures.append("stm_snap_x_ratios_changed")
    if STM_SNAP_Y_DV_FRACS != shear_visuals._STM_SNAP_Y_DV_FRACS:
        failures.append("stm_snap_y_dv_fracs_changed")
    for idx, raw_ratio in enumerate((0.42, 0.61, 0.74, 1.2)):
        if stm_snap_ratio_to_grid(raw_ratio) != shear_visuals._stm_snap_ratio_to_grid(raw_ratio):
            failures.append(f"stm_snap_ratio_to_grid_wrapper_changed_{idx}")
    if stm_y_snap_levels_dv(0.62, 0.7, 0.05) != shear_visuals._stm_y_snap_levels_dv(0.62, 0.7, 0.05):
        failures.append("stm_y_snap_levels_dv_wrapper_changed")
    left_args = (0.08, 0.05, 0.62, 0.82, 0.62, 0.7, 0.03, 0.34)
    if stm_snap_inner_top_left(*left_args) != shear_visuals._stm_snap_inner_top_left(*left_args):
        failures.append("stm_snap_inner_top_left_wrapper_changed")
    right_args = (3.92, 0.05, 4.0, 3.38, 0.82, 0.62, 0.7, 0.03, 0.34)
    if stm_snap_inner_top_right(*right_args) != shear_visuals._stm_snap_inner_top_right(*right_args):
        failures.append("stm_snap_inner_top_right_wrapper_changed")

    model = {
        "total_length_m": 4.0,
        "span_m": 4.0,
        "D_m": 0.7,
        "d_m": 0.62,
        "support_condition": "simply_supported",
        "theta_v_deg": 36.5,
    }
    cantilever_model = {
        "total_length_m": 4.0,
        "span_m": 4.0,
        "D_m": 0.7,
        "d_m": 0.62,
        "support_condition": "cantilever",
        "theta_v_deg": 36.5,
    }
    if display_zone_length(model) != shear_visuals._display_zone_length(model):
        failures.append("display_zone_length_wrapper_changed")
    if shear_crack_x_band_m(model) != shear_visuals._shear_crack_x_band_m(model):
        failures.append("shear_crack_x_band_wrapper_changed")
    if shear_crack_x_band_m(cantilever_model) != shear_visuals._shear_crack_x_band_m(cantilever_model):
        failures.append("shear_crack_x_band_cantilever_wrapper_changed")
    if sample_beam_y(0.24, 0.7) != shear_visuals._sample_beam_y(0.24, 0.7):
        failures.append("sample_beam_y_wrapper_changed")
    if beam_depth_scale(model) != shear_visuals._beam_depth_scale(model):
        failures.append("beam_depth_scale_wrapper_changed")
    if compute_stress_field_geometry(model) != shear_visuals._compute_stress_field_geometry(model):
        failures.append("compute_stress_field_geometry_wrapper_changed")
    if cantilever_behaviour_zones(cantilever_model) != shear_visuals._cantilever_behaviour_zones(cantilever_model):
        failures.append("cantilever_behaviour_zones_wrapper_changed")
    short_cantilever_model = {"span_m": 0.18, "d_m": 0.5}
    if cantilever_behaviour_zones(short_cantilever_model) != shear_visuals._cantilever_behaviour_zones(short_cantilever_model):
        failures.append("cantilever_behaviour_zones_short_span_wrapper_changed")
    if compute_stm_simply_supported_d_region_nodes(model, theta_v_deg=model["theta_v_deg"]) != shear_visuals._compute_stm_simply_supported_d_region_nodes(model):
        failures.append("compute_stm_simply_supported_nodes_wrapper_changed")
    if compute_stm_cantilever_d_region_nodes(cantilever_model, theta_v_deg=cantilever_model["theta_v_deg"]) != shear_visuals._compute_stm_cantilever_d_region_nodes(cantilever_model):
        failures.append("compute_stm_cantilever_nodes_wrapper_changed")
    collapsed_ss_model = dict(model, span_m=1.0, total_length_m=10.0, d_m=0.6)
    if compute_stm_simply_supported_d_region_nodes(collapsed_ss_model, theta_v_deg=36.5) is not None:
        failures.append("compute_stm_simply_supported_collapsed_not_none")

    geometry = {
        "beam_left": 0.0,
        "beam_right": 4.0,
        "beam_bottom": 0.0,
        "beam_top": 0.7,
        "L_plot": 4.0,
        "D_plot": 0.7,
        "d_plot": 0.62,
        "slenderness": 6.45,
        "left_deep_limit": 0.62,
        "right_deep_limit": 3.38,
        "flexural_width": 2.76,
        "centre_x": 2.0,
        "top_anchor_y": 0.686,
        "bottom_anchor_y": 0.014,
        "tensile_apex_inner_y": 0.252,
        "tensile_apex_outer_y": 0.154,
        "compressive_apex_inner_y": 0.448,
        "compressive_apex_outer_y": 0.546,
        "bow_gain": 1.03,
        "end_curvature_gain": 0.97,
    }
    if compute_trajectory_count(geometry["slenderness"]) != shear_visuals._compute_trajectory_count(geometry["slenderness"]):
        failures.append("compute_trajectory_count_wrapper_changed")
    if sample_anchor_band(5) != shear_visuals._sample_anchor_band(5):
        failures.append("sample_anchor_band_wrapper_changed")
    if compute_trajectory_half_widths(geometry, 5) != shear_visuals._compute_trajectory_half_widths(geometry, 5):
        failures.append("compute_trajectory_half_widths_wrapper_changed")
    if trajectory_bow_scale(geometry, 0.65) != shear_visuals._trajectory_bow_scale(geometry, 0.65):
        failures.append("trajectory_bow_scale_wrapper_changed")
    if trajectory_end_curvature_boost(geometry, 0.65) != shear_visuals._trajectory_end_curvature_boost(geometry, 0.65):
        failures.append("trajectory_end_curvature_boost_wrapper_changed")
    tensile_module = build_tensile_trajectories(geometry, 5)
    tensile_legacy = shear_visuals._build_tensile_trajectories(geometry, 5)
    compression_module = build_compressive_trajectories(geometry, 5)
    compression_legacy = shear_visuals._build_compressive_trajectories(geometry, 5)
    if tensile_module != tensile_legacy:
        failures.append("build_tensile_trajectories_wrapper_changed")
    if compression_module != compression_legacy:
        failures.append("build_compressive_trajectories_wrapper_changed")
    if [len(line) for line in tensile_module] != [25, 25, 25, 25, 25]:
        failures.append("build_tensile_trajectories_sample_count_changed")
    if [len(line) for line in compression_module] != [25, 25, 25, 25, 25]:
        failures.append("build_compressive_trajectories_sample_count_changed")

    module_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    legacy_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_strut_tie_node(module_fig, 0.25, 0.35)
    shear_visuals._add_strut_tie_node(legacy_fig, 0.25, 0.35)
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("strut_tie_node_signature_changed")
    if len(module_fig.data) != 1:
        failures.append("strut_tie_node_trace_count_changed")
    elif module_fig.data[0].marker.size != legacy_fig.data[0].marker.size:
        failures.append("strut_tie_node_marker_size_changed")

    module_member_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    legacy_member_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_stm_member(
        module_member_fig,
        (0.1, 0.2),
        (0.8, 0.5),
        "rgba(10,20,30,0.8)",
        3.1,
        opacity=0.6,
        beam_depth_m=0.7,
    )
    shear_visuals._add_stm_member(
        legacy_member_fig,
        (0.1, 0.2),
        (0.8, 0.5),
        "rgba(10,20,30,0.8)",
        3.1,
        opacity=0.6,
        beam_depth_m=0.7,
    )
    add_stm_axis_vertical(
        module_member_fig,
        0.4,
        0.6,
        0.2,
        "rgba(20,40,60,0.7)",
        2.4,
        opacity=0.5,
        beam_depth_m=0.7,
    )
    shear_visuals._add_stm_axis_vertical(
        legacy_member_fig,
        0.4,
        0.6,
        0.2,
        "rgba(20,40,60,0.7)",
        2.4,
        opacity=0.5,
        beam_depth_m=0.7,
    )
    if _signature(module_member_fig) != _signature(legacy_member_fig):
        failures.append("stm_member_axis_signature_changed")
    if [trace.line.width for trace in module_member_fig.data] != [trace.line.width for trace in legacy_member_fig.data]:
        failures.append("stm_member_axis_widths_changed")

    module_angle_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    legacy_angle_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_stm_joint_angle_annotation(
        module_angle_fig,
        (0.2, 0.1),
        (0.7, 0.52),
        "35 deg",
        color="rgba(90,20,20,0.9)",
        beam_depth_m=0.7,
        tie_direction="right",
    )
    shear_visuals._add_stm_joint_angle_annotation(
        legacy_angle_fig,
        (0.2, 0.1),
        (0.7, 0.52),
        "35 deg",
        color="rgba(90,20,20,0.9)",
        beam_depth_m=0.7,
        tie_direction="right",
    )
    if _signature(module_angle_fig) != _signature(legacy_angle_fig):
        failures.append("stm_joint_angle_signature_changed")
    if _annotation_text(module_angle_fig) != _annotation_text(legacy_angle_fig):
        failures.append("stm_joint_angle_label_changed")
    if len(module_angle_fig.data) != 1:
        failures.append("stm_joint_angle_trace_count_changed")
    elif list(module_angle_fig.data[0].x) != list(legacy_angle_fig.data[0].x) or list(module_angle_fig.data[0].y) != list(legacy_angle_fig.data[0].y):
        failures.append("stm_joint_angle_arc_points_changed")

    no_op_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_stm_joint_angle_annotation(
        no_op_fig,
        (0.2, 0.1),
        (0.7, 0.1),
        "0 deg",
        color="rgba(90,20,20,0.9)",
        beam_depth_m=0.7,
        tie_direction="right",
    )
    if _signature(no_op_fig) != (0, 0, 0):
        failures.append("stm_joint_angle_zero_delta_not_noop")

    stm_model = dict(model, show_stm_overlay=True)
    module_stm_ss_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    legacy_stm_ss_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    render_strut_tie_ss_udl(module_stm_ss_fig, stm_model, theta_v_deg=stm_model["theta_v_deg"])
    shear_visuals._render_strut_tie_ss_udl(legacy_stm_ss_fig, stm_model)
    if _signature(module_stm_ss_fig) != _signature(legacy_stm_ss_fig):
        failures.append("render_strut_tie_ss_udl_signature_changed")
    if _annotation_text(module_stm_ss_fig) != _annotation_text(legacy_stm_ss_fig):
        failures.append("render_strut_tie_ss_udl_annotations_changed")
    if len(module_stm_ss_fig.data) != 15:
        failures.append("render_strut_tie_ss_udl_trace_count_changed")
    if len(module_stm_ss_fig.layout.annotations or []) != 4:
        failures.append("render_strut_tie_ss_udl_annotation_count_changed")

    stm_cantilever_model = dict(cantilever_model, show_stm_overlay=True)
    module_stm_cantilever_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    legacy_stm_cantilever_fig = build_shear_behaviour_base_figure(
        length_m=4.0,
        beam_depth_m=0.7,
        height=260,
        width=520,
    )
    render_strut_tie_cantilever_tip(
        module_stm_cantilever_fig,
        stm_cantilever_model,
        theta_v_deg=stm_cantilever_model["theta_v_deg"],
    )
    shear_visuals._render_strut_tie_cantilever_tip(legacy_stm_cantilever_fig, stm_cantilever_model)
    if _signature(module_stm_cantilever_fig) != _signature(legacy_stm_cantilever_fig):
        failures.append("render_strut_tie_cantilever_tip_signature_changed")
    if _annotation_text(module_stm_cantilever_fig) != _annotation_text(legacy_stm_cantilever_fig):
        failures.append("render_strut_tie_cantilever_tip_annotations_changed")
    if len(module_stm_cantilever_fig.data) != 8:
        failures.append("render_strut_tie_cantilever_tip_trace_count_changed")
    if len(module_stm_cantilever_fig.layout.annotations or []) != 3:
        failures.append("render_strut_tie_cantilever_tip_annotation_count_changed")

    def _check_overlay_labels(case_kind: str, overlay_model: dict, suffix: str) -> None:
        module_labels_fig = build_shear_behaviour_base_figure(
            length_m=4.0,
            beam_depth_m=0.7,
            height=260,
            width=520,
        )
        legacy_labels_fig = build_shear_behaviour_base_figure(
            length_m=4.0,
            beam_depth_m=0.7,
            height=260,
            width=520,
        )
        add_stm_overlay_labels(
            module_labels_fig,
            overlay_model,
            case_kind,
            theta_v_deg=overlay_model["theta_v_deg"],
        )
        shear_visuals._add_stm_overlay_labels(legacy_labels_fig, overlay_model, case_kind)
        if _signature(module_labels_fig) != _signature(legacy_labels_fig):
            failures.append(f"stm_overlay_labels_signature_changed_{suffix}")
        if _annotation_text(module_labels_fig) != _annotation_text(legacy_labels_fig):
            failures.append(f"stm_overlay_labels_annotations_changed_{suffix}")
        if len(module_labels_fig.layout.annotations or []) != 2:
            failures.append(f"stm_overlay_labels_count_changed_{suffix}")

    _check_overlay_labels("ss_udl", stm_model, "ss")
    _check_overlay_labels("cantilever_tip", stm_cantilever_model, "cantilever")
    _check_overlay_labels("fallback_simple", stm_model, "fallback")

    def _check_overlay(case_kind: str, overlay_model: dict, suffix: str, expected_data: int, expected_annotations: int) -> None:
        module_overlay_fig = build_shear_behaviour_base_figure(
            length_m=4.0,
            beam_depth_m=0.7,
            height=260,
            width=520,
        )
        legacy_overlay_fig = build_shear_behaviour_base_figure(
            length_m=4.0,
            beam_depth_m=0.7,
            height=260,
            width=520,
        )
        render_stm_overlay(module_overlay_fig, overlay_model, case_kind, theta_v_deg=overlay_model["theta_v_deg"])
        shear_visuals._render_stm_overlay(legacy_overlay_fig, overlay_model, case_kind)
        if _signature(module_overlay_fig) != _signature(legacy_overlay_fig):
            failures.append(f"render_stm_overlay_signature_changed_{suffix}")
        if _annotation_text(module_overlay_fig) != _annotation_text(legacy_overlay_fig):
            failures.append(f"render_stm_overlay_annotations_changed_{suffix}")
        if len(module_overlay_fig.data) != expected_data:
            failures.append(f"render_stm_overlay_trace_count_changed_{suffix}")
        if len(module_overlay_fig.layout.annotations or []) != expected_annotations:
            failures.append(f"render_stm_overlay_annotation_count_changed_{suffix}")

    _check_overlay("ss_udl", stm_model, "ss", expected_data=15, expected_annotations=4)
    _check_overlay("cantilever_tip", stm_cantilever_model, "cantilever", expected_data=8, expected_annotations=3)

    stm_hidden_titles_model = dict(stm_model, show_stm_overlay=False)
    _check_overlay("ss_udl", stm_hidden_titles_model, "ss_hidden_titles", expected_data=13, expected_annotations=0)
    return failures


def _check_polyline_geometry_helpers() -> list[str]:
    failures: list[str] = []
    poly_a = [(0.0, 0.0), (0.5, 0.5), (1.0, 0.2)]
    poly_b = [(0.0, 0.5), (0.5, 0.0), (1.0, 0.6)]
    segment_start = (0.1, 0.4)
    segment_end = (0.9, 0.1)

    if segment_intersection((0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0)) != shear_visuals._segment_intersection(
        (0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0)
    ):
        failures.append("segment_intersection_wrapper_changed")
    if segment_intersection((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)) is not None:
        failures.append("segment_intersection_parallel_not_none")
    if polyline_polyline_best_hit(poly_a, poly_b, 0.0, 1.0) != shear_visuals._polyline_polyline_best_hit(poly_a, poly_b, 0.0, 1.0):
        failures.append("polyline_polyline_best_hit_wrapper_changed")
    if polyline_polyline_best_hit(poly_a, poly_b, 1.1, 1.5) is not None:
        failures.append("polyline_polyline_best_hit_band_not_none")
    if polyline_y_at_x(poly_a, 0.25) != shear_visuals._polyline_y_at_x(poly_a, 0.25):
        failures.append("polyline_y_at_x_wrapper_changed")
    if polyline_y_at_x(poly_a, 2.0) is not None:
        failures.append("polyline_y_at_x_outside_not_none")
    if polyline_tangent_at_x(poly_a, 0.75) != shear_visuals._polyline_tangent_at_x(poly_a, 0.75):
        failures.append("polyline_tangent_at_x_wrapper_changed")
    if polyline_tangent_at_x(poly_a, 2.0) is not None:
        failures.append("polyline_tangent_outside_not_none")
    if polyline_segment_best_hit(poly_a, segment_start, segment_end, 0.0, 1.0) != shear_visuals._polyline_segment_best_hit(
        poly_a, segment_start, segment_end, 0.0, 1.0
    ):
        failures.append("polyline_segment_best_hit_wrapper_changed")
    if polyline_segment_best_hit(poly_a, segment_start, segment_end, 1.1, 1.5) is not None:
        failures.append("polyline_segment_best_hit_band_not_none")

    hit = {"x": 0.42, "y": 0.25, "crack_angle_rad": 0.0, "principal_deg": 0.0}
    compression = [
        [(0.0, 0.62), (0.5, 0.48), (1.0, 0.32)],
        [(0.0, 0.38), (0.5, 0.28), (1.0, 0.18)],
    ]
    module_refined = cantilever_refine_crack_hit_for_compression_field(hit, compression, 1.0, x_lo=0.1, x_hi=0.9)
    legacy_refined = shear_visuals._cantilever_refine_crack_hit_for_compression_field(hit, compression, 1.0, x_lo=0.1, x_hi=0.9)
    if module_refined != legacy_refined:
        failures.append("cantilever_refine_crack_hit_wrapper_changed")
    fallback_refined = cantilever_refine_crack_hit_for_compression_field(hit, [], 1.0, x_lo=0.1, x_hi=0.9)
    legacy_fallback = shear_visuals._cantilever_refine_crack_hit_for_compression_field(hit, [], 1.0, x_lo=0.1, x_hi=0.9)
    if fallback_refined != legacy_fallback:
        failures.append("cantilever_refine_crack_hit_fallback_changed")

    tension_lines = [
        [(0.0, 0.08), (0.5, 0.16), (1.0, 0.10)],
        [(0.0, 0.12), (0.5, 0.20), (1.0, 0.14)],
    ]
    compression_lines = [
        [(0.0, 0.58), (0.5, 0.48), (1.0, 0.35)],
        [(0.0, 0.52), (0.5, 0.42), (1.0, 0.30)],
        [(0.0, 0.46), (0.5, 0.36), (1.0, 0.25)],
    ]
    marker_geometry = {
        "L_plot": 1.0,
        "d_plot": 0.7,
        "left_deep_limit": 0.2,
        "centre_x": 0.55,
        "beam_bottom": 0.0,
        "D_plot": 0.7,
        "crack_x_lo": 0.1,
        "crack_x_hi": 0.8,
        "shortness": 0.1,
        "longness": 0.2,
    }
    module_marker = principal_stress_marker_state(tension_lines, compression_lines, marker_geometry)
    legacy_marker = shear_visuals._principal_stress_marker_state(tension_lines, compression_lines, marker_geometry)
    if module_marker != legacy_marker:
        failures.append("principal_stress_marker_state_wrapper_changed")
    if principal_stress_marker_state(tension_lines, compression_lines[:2], marker_geometry) is not None:
        failures.append("principal_stress_marker_state_short_compression_not_none")

    cantilever_model = {
        "total_length_m": 1.0,
        "span_m": 1.0,
        "D_m": 0.7,
        "d_m": 0.62,
        "support_condition": "cantilever",
        "theta_v_deg": 36.5,
    }
    module_hits = cantilever_principal_crack_hits(
        compression_lines,
        tension_lines,
        1.0,
        cantilever_model,
        theta_v_deg=cantilever_model["theta_v_deg"],
    )
    legacy_hits = shear_visuals._cantilever_principal_crack_hits(
        compression_lines,
        tension_lines,
        1.0,
        cantilever_model,
    )
    if module_hits != legacy_hits:
        failures.append("cantilever_principal_crack_hits_wrapper_changed")

    crack_geometry = dict(
        marker_geometry,
        cantilever_crack_hits=module_hits,
        beam_left=0.0,
        beam_right=1.0,
        beam_top=0.7,
    )
    module_crack_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    legacy_crack_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_principal_shear_crack_example(
        module_crack_fig,
        tension_lines,
        compression_lines,
        crack_geometry,
        marker_centre=module_marker[0] if module_marker is not None else None,
        marker_angle_deg=module_marker[1] if module_marker is not None else None,
    )
    shear_visuals._add_principal_shear_crack_example(
        legacy_crack_fig,
        tension_lines,
        compression_lines,
        crack_geometry,
        marker_centre=module_marker[0] if module_marker is not None else None,
        marker_angle_deg=module_marker[1] if module_marker is not None else None,
    )
    if _signature(module_crack_fig) != _signature(legacy_crack_fig):
        failures.append("principal_shear_crack_signature_changed")
    if len(module_crack_fig.layout.annotations or []) != len(legacy_crack_fig.layout.annotations or []):
        failures.append("principal_shear_crack_annotation_count_changed")

    module_cantilever_crack_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    legacy_cantilever_crack_fig = build_shear_behaviour_base_figure(
        length_m=1.0,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_principal_shear_crack_example(
        module_cantilever_crack_fig,
        tension_lines,
        compression_lines,
        crack_geometry,
        cantilever_mode=True,
    )
    shear_visuals._add_principal_shear_crack_example(
        legacy_cantilever_crack_fig,
        tension_lines,
        compression_lines,
        crack_geometry,
        cantilever_mode=True,
    )
    if _signature(module_cantilever_crack_fig) != _signature(legacy_cantilever_crack_fig):
        failures.append("principal_shear_crack_cantilever_signature_changed")
    if len(module_cantilever_crack_fig.layout.annotations or []) != len(legacy_cantilever_crack_fig.layout.annotations or []):
        failures.append("principal_shear_crack_cantilever_annotation_count_changed")

    principal_model = {
        "total_length_m": 4.0,
        "span_m": 4.0,
        "D_m": 0.7,
        "d_m": 0.62,
        "support_condition": "simply_supported",
        "theta_v_deg": 36.5,
        "show_cracks": True,
        "show_stress_block": True,
    }

    def _check_principal_renderer(
        renderer,
        legacy_renderer,
        suffix: str,
        *,
        model: dict | None = None,
        show_load_flow: bool = False,
    ) -> None:
        local_model = dict(model or principal_model, show_load_flow=show_load_flow)
        beam_depth_m = float(local_model.get("D_m", 0.7))
        length_m = float(local_model.get("span_m", 4.0))
        module_principal_fig = build_shear_behaviour_base_figure(
            length_m=length_m,
            beam_depth_m=beam_depth_m,
            height=260,
            width=520,
        )
        legacy_principal_fig = build_shear_behaviour_base_figure(
            length_m=length_m,
            beam_depth_m=beam_depth_m,
            height=260,
            width=520,
        )
        renderer(module_principal_fig, local_model, theta_v_deg=local_model["theta_v_deg"])
        legacy_renderer(legacy_principal_fig, local_model)
        if _signature(module_principal_fig) != _signature(legacy_principal_fig):
            failures.append(f"principal_stress_renderer_signature_changed_{suffix}")
        if _annotation_text(module_principal_fig) != _annotation_text(legacy_principal_fig):
            failures.append(f"principal_stress_renderer_annotations_changed_{suffix}")
        module_meta = [getattr(trace, "meta", None) for trace in module_principal_fig.data if getattr(trace, "meta", None)]
        legacy_meta = [getattr(trace, "meta", None) for trace in legacy_principal_fig.data if getattr(trace, "meta", None)]
        if module_meta != legacy_meta:
            failures.append(f"principal_stress_renderer_meta_changed_{suffix}")
        if len(module_principal_fig.data) < 8:
            failures.append(f"principal_stress_renderer_trace_count_low_{suffix}")

    _check_principal_renderer(render_principal_stress_ss_udl, shear_visuals._render_principal_stress_ss_udl, "ss_udl")
    _check_principal_renderer(
        render_principal_stress_ss_udl,
        shear_visuals._render_principal_stress_ss_udl,
        "ss_udl_load_flow",
        show_load_flow=True,
    )
    _check_principal_renderer(
        render_principal_stress_ss_midspan_point,
        shear_visuals._render_principal_stress_ss_midspan_point,
        "ss_midspan",
    )
    _check_principal_renderer(
        render_principal_stress_ss_eccentric_point,
        shear_visuals._render_principal_stress_ss_eccentric_point,
        "ss_eccentric",
    )
    _check_principal_renderer(
        render_principal_stress_ss_near_support_point,
        shear_visuals._render_principal_stress_ss_near_support_point,
        "ss_near_support",
    )

    cantilever_principal_model = dict(
        principal_model,
        support_condition="cantilever",
        total_length_m=3.2,
        span_m=3.2,
        D_m=0.62,
        d_m=0.55,
    )
    _check_principal_renderer(
        render_principal_stress_cantilever_tip,
        shear_visuals._render_principal_stress_cantilever_tip,
        "cantilever_tip",
        model=cantilever_principal_model,
    )
    _check_principal_renderer(
        render_principal_stress_cantilever_tip,
        shear_visuals._render_principal_stress_cantilever_tip,
        "cantilever_tip_load_flow",
        model=cantilever_principal_model,
        show_load_flow=True,
    )
    _check_principal_renderer(
        render_principal_stress_cantilever_udl,
        shear_visuals._render_principal_stress_cantilever_udl,
        "cantilever_udl",
        model=cantilever_principal_model,
    )
    _check_principal_renderer(
        render_principal_stress_cantilever_eccentric,
        shear_visuals._render_principal_stress_cantilever_eccentric,
        "cantilever_eccentric",
        model=cantilever_principal_model,
    )
    return failures


def _check_principal_stress_cue() -> list[str]:
    module_fig = build_principal_stress_axes_cue(45.0)
    legacy_fig = shear_page._build_principal_stress_axes_cue()
    annotations = _annotation_text(module_fig)
    failures: list[str] = []
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("principal_cue_legacy_signature_changed")
    if int(module_fig.layout.width or 0) != int(540 * PRINCIPAL_STRESS_AXES_CUE_SCALE):
        failures.append("principal_cue_width_not_preserved")
    if int(module_fig.layout.height or 0) != int(190 * PRINCIPAL_STRESS_AXES_CUE_SCALE):
        failures.append("principal_cue_height_not_preserved")
    if module_fig.layout.xaxis.visible is not False:
        failures.append("principal_cue_x_axis_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("principal_cue_y_axis_visible")
    if module_fig.layout.yaxis.scaleanchor != "x":
        failures.append("principal_cue_y_axis_not_scaleanchored")
    for expected in ("(A) stress state", "(B) rotate", "(C) principal", "No shear"):
        if not any(expected in text for text in annotations):
            failures.append(f"principal_cue_annotation_missing_{expected.replace(' ', '_')}")
    if len(module_fig.data) < 8:
        failures.append("principal_cue_trace_count_too_low")

    geometry = {
        "centre_x": 0.55,
        "D_plot": 0.7,
        "L_plot": 1.6,
        "flexural_width": 0.9,
    }
    square_module_fig = build_shear_behaviour_base_figure(
        length_m=1.6,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    square_legacy_fig = build_shear_behaviour_base_figure(
        length_m=1.6,
        beam_depth_m=0.7,
        height=260,
        width=420,
    )
    add_principal_stress_orientation_square(square_module_fig, geometry, principal_angle_deg=37.5)
    shear_visuals._add_principal_stress_orientation_square(square_legacy_fig, geometry, principal_angle_deg=37.5)
    if _signature(square_module_fig) != _signature(square_legacy_fig):
        failures.append("principal_orientation_square_signature_changed")
    if len(square_module_fig.data) != 5:
        failures.append("principal_orientation_square_trace_count_changed")
    if len(square_module_fig.layout.annotations or []) != 4:
        failures.append("principal_orientation_square_annotation_count_changed")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_behaviour_base())
    failures.extend(_check_behaviour_support_shapes())
    failures.extend(_check_behaviour_load_shapes())
    failures.extend(_check_behaviour_zones())
    failures.extend(_check_field_line_primitives())
    failures.extend(_check_trajectory_utilities())
    failures.extend(_check_load_flow_overlay())
    failures.extend(_check_stm_flow_polyline())
    failures.extend(_check_trajectory_geometry_helpers())
    failures.extend(_check_polyline_geometry_helpers())
    failures.extend(_check_principal_stress_cue())

    if failures:
        print("DIAGRAM_SHEAR_BEHAVIOUR_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_SHEAR_BEHAVIOUR_SMOKE PASS")
    print("- shear behaviour base frame, support, load-shape, and zone wrappers verified")
    print("- field force-line primitive, SS and cantilever renderer wrappers verified")
    print("- trajectory utility and ordered-family wrappers verified")
    print("- load-flow overlay wrapper verified")
    print("- STM flow polyline and overlay wrappers verified")
    print("- stress-field geometry, cantilever zones, STM snapping/node builders, trajectory builders, strut-tie renderers, STM overlays, and STM joint-angle wrappers verified")
    print("- polyline geometry, principal crack helper, and principal-stress renderer wrappers verified")
    print("- principal-stress cue module builder and legacy wrapper verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
