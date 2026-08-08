from __future__ import annotations

import json
import math
import os
import time
from typing import Any

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from section_layout import compute_section_layout
from state_runtime_gateway import get_param
from widgets_helpers import main_longitudinal_reo_pair_labels
from ui.diagrams.diagram_styles import DIAGRAM_SIZE_BEHAVIOUR
from ui.diagrams.shear_diagram import build_shear_cross_section_figure_from_layout
from ui.diagrams import side_view_diagram as shared_side_view_diagram
from ui.diagrams.creep_shrinkage_diagram import (
    build_creep_schematic_plotly as _shared_build_creep_schematic_plotly,
    build_shrinkage_schematic_plotly as _shared_build_shrinkage_schematic_plotly,
)
from ui.diagrams.principal_stress_cue_diagram import (
    add_principal_stress_orientation_square as _shared_add_principal_stress_orientation_square,
)
from ui.diagrams.shear_behaviour_diagram import (
    STM_SNAP_X_RATIOS as _SHARED_STM_SNAP_X_RATIOS,
    STM_SNAP_Y_DV_FRACS as _SHARED_STM_SNAP_Y_DV_FRACS,
    add_shear_behaviour_beam_band as _shared_add_shear_behaviour_beam_band,
    add_shear_behaviour_fixed_support as _shared_add_shear_behaviour_fixed_support,
    add_shear_behaviour_pinned_support as _shared_add_shear_behaviour_pinned_support,
    add_shear_behaviour_point_load as _shared_add_shear_behaviour_point_load,
    add_force_line as _shared_add_force_line,
    add_load_flow_overlay as _shared_add_load_flow_overlay,
    add_ordered_trajectory_family as _shared_add_ordered_trajectory_family,
    add_principal_shear_crack_example as _shared_add_principal_shear_crack_example,
    add_sparse_trajectory_arrows as _shared_add_sparse_trajectory_arrows,
    add_stm_axis_vertical as _shared_add_stm_axis_vertical,
    add_stm_flow_polyline as _shared_add_stm_flow_polyline,
    add_stm_joint_angle_annotation as _shared_add_stm_joint_angle_annotation,
    add_stm_member as _shared_add_stm_member,
    add_stm_overlay_labels as _shared_add_stm_overlay_labels,
    add_shear_behaviour_udl as _shared_add_shear_behaviour_udl,
    add_strut_tie_node as _shared_add_strut_tie_node,
    add_trajectory_family as _shared_add_trajectory_family,
    add_trajectory_direction_arrow as _shared_add_trajectory_direction_arrow,
    blend_x as _shared_blend_x,
    build_compression_family as _shared_build_compression_family,
    build_crack_cues as _shared_build_crack_cues,
    build_compressive_trajectories as _shared_build_compressive_trajectories,
    build_shear_behaviour_base_figure as _shared_build_shear_behaviour_base_figure,
    build_shear_behaviour_load_shapes as _shared_build_shear_behaviour_load_shapes,
    build_shear_behaviour_support_shapes as _shared_build_shear_behaviour_support_shapes,
    build_shear_behaviour_zones as _shared_build_shear_behaviour_zones,
    build_tensile_trajectories as _shared_build_tensile_trajectories,
    build_tension_family as _shared_build_tension_family,
    beam_depth_scale as _shared_beam_depth_scale,
    cantilever_behaviour_zones as _shared_cantilever_behaviour_zones,
    cantilever_principal_crack_hits as _shared_cantilever_principal_crack_hits,
    cantilever_refine_crack_hit_for_compression_field as _shared_cantilever_refine_crack_hit_for_compression_field,
    clamp_field_points as _shared_clamp_field_points,
    compute_stm_cantilever_d_region_nodes as _shared_compute_stm_cantilever_d_region_nodes,
    compute_stm_simply_supported_d_region_nodes as _shared_compute_stm_simply_supported_d_region_nodes,
    compute_stress_field_geometry as _shared_compute_stress_field_geometry,
    compute_trajectory_count as _shared_compute_trajectory_count,
    compute_trajectory_half_widths as _shared_compute_trajectory_half_widths,
    densify_polyline as _shared_densify_polyline,
    display_zone_length as _shared_display_zone_length,
    field_line_spec as _shared_field_line_spec,
    field_y_limits as _shared_field_y_limits,
    linear_interpolate_points as _shared_linear_interpolate_points,
    mirror_trajectory_about_middepth as _shared_mirror_trajectory_about_middepth,
    mirror_field_line as _shared_mirror_field_line,
    parabolic_trajectory as _shared_parabolic_trajectory,
    polyline_polyline_best_hit as _shared_polyline_polyline_best_hit,
    polyline_segment_best_hit as _shared_polyline_segment_best_hit,
    polyline_tangent_at_x as _shared_polyline_tangent_at_x,
    polyline_y_at_x as _shared_polyline_y_at_x,
    principal_stress_marker_state as _shared_principal_stress_marker_state,
    render_field_cantilever_eccentric as _shared_render_field_cantilever_eccentric,
    render_field_cantilever_tip as _shared_render_field_cantilever_tip,
    render_field_cantilever_udl as _shared_render_field_cantilever_udl,
    render_field_ss_eccentric_point as _shared_render_field_ss_eccentric_point,
    render_field_ss_midspan_point as _shared_render_field_ss_midspan_point,
    render_field_ss_near_support_point as _shared_render_field_ss_near_support_point,
    render_field_ss_udl as _shared_render_field_ss_udl,
    render_principal_stress_cantilever_eccentric as _shared_render_principal_stress_cantilever_eccentric,
    render_principal_stress_cantilever_tip as _shared_render_principal_stress_cantilever_tip,
    render_principal_stress_cantilever_udl as _shared_render_principal_stress_cantilever_udl,
    render_principal_stress_ss_eccentric_point as _shared_render_principal_stress_ss_eccentric_point,
    render_principal_stress_ss_midspan_point as _shared_render_principal_stress_ss_midspan_point,
    render_principal_stress_ss_near_support_point as _shared_render_principal_stress_ss_near_support_point,
    render_principal_stress_ss_udl as _shared_render_principal_stress_ss_udl,
    render_stm_flow_overlay as _shared_render_stm_flow_overlay,
    render_stm_overlay as _shared_render_stm_overlay,
    render_strut_tie_cantilever_eccentric as _shared_render_strut_tie_cantilever_eccentric,
    render_strut_tie_cantilever_tip as _shared_render_strut_tie_cantilever_tip,
    render_strut_tie_cantilever_udl as _shared_render_strut_tie_cantilever_udl,
    render_strut_tie_ss_eccentric_point as _shared_render_strut_tie_ss_eccentric_point,
    render_strut_tie_ss_midspan_point as _shared_render_strut_tie_ss_midspan_point,
    render_strut_tie_ss_near_support_point as _shared_render_strut_tie_ss_near_support_point,
    render_strut_tie_ss_udl as _shared_render_strut_tie_ss_udl,
    sample_curve_point_and_tangent as _shared_sample_curve_point_and_tangent,
    sample_anchor_band as _shared_sample_anchor_band,
    sample_beam_y as _shared_sample_beam_y,
    scaled_rgba_alpha as _shared_scaled_rgba_alpha,
    segment_intersection as _shared_segment_intersection,
    shear_crack_x_band_m as _shared_shear_crack_x_band_m,
    support_d_region_bounds as _shared_support_d_region_bounds,
    support_edge_y_bot as _shared_support_edge_y_bot,
    support_edge_y_top as _shared_support_edge_y_top,
    support_zone_x_left as _shared_support_zone_x_left,
    support_zone_x_right as _shared_support_zone_x_right,
    symmetric_arch as _shared_symmetric_arch,
    stm_snap_inner_top_left as _shared_stm_snap_inner_top_left,
    stm_snap_inner_top_right as _shared_stm_snap_inner_top_right,
    stm_snap_ratio_to_grid as _shared_stm_snap_ratio_to_grid,
    stm_y_snap_levels_dv as _shared_stm_y_snap_levels_dv,
    trajectory_visual_weight as _shared_trajectory_visual_weight,
    trajectory_bow_scale as _shared_trajectory_bow_scale,
    trajectory_end_curvature_boost as _shared_trajectory_end_curvature_boost,
)


VISUAL_HEIGHT = 360
BEHAVIOUR_VISUAL_HEIGHT = DIAGRAM_SIZE_BEHAVIOUR["height"]
BEHAVIOUR_VISUAL_WIDTH = DIAGRAM_SIZE_BEHAVIOUR["width"]
SIDE_VIEW_VISUAL_HEIGHT = shared_side_view_diagram.SIDE_VIEW_VISUAL_HEIGHT
SIDE_VIEW_VISUAL_WIDTH = BEHAVIOUR_VISUAL_WIDTH
_BEAM_VIEWS_LEFT_RATIO = 0.38
_BEAM_VIEWS_RIGHT_RATIO = 0.62
_SIDE_VIEW_BREAK_SLENDERNESS = 10.0
_SHEAR_ZONE_SIDE_VIEW_FILLS = (
    "rgba(255,0,0,0.15)",
    "rgba(255,165,0,0.15)",
    "rgba(0,200,0,0.15)",
)
_BEAM_Y0 = 0.40
_BEAM_Y1 = 0.60
_DEFAULT_LOADING_CASE = "Simple beam – UDL over entire span"
_FIELD_TOP_PAD = 0.012
_FIELD_BOT_PAD = 0.012
_FIELD_SPLINE_SMOOTHING = 0.65


def _dbg_log(message: str, data: dict[str, Any], *, hypothesis_id: str, run_id: str = "ss_psf_debug") -> None:
    return


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if math.isnan(number):
            return float(default)
        return number
    except Exception:
        return float(default)


def _active_limit_state_for_visuals() -> str:
    return str(st.session_state.get("loads_edit_mode", get_param("loads_edit_mode", "ULS")) or "ULS").upper()


def _session_or_shared(widget_key: str, shared_key: str, default: Any = None) -> Any:
    widget_val = st.session_state.get(widget_key)
    if widget_val is not None:
        return widget_val
    shared_val = st.session_state.get(shared_key)
    if shared_val is not None:
        return shared_val
    return get_param(shared_key, default)


def _normalise_loading_case(raw_case: Any) -> str:
    case = str(raw_case or "").strip()
    if case.startswith("Simple beam"):
        return case
    if case.startswith("Cantilever"):
        return case
    if case.startswith("Overhanging beam"):
        return case
    return _DEFAULT_LOADING_CASE


def _shared_or_widget(shared_key: str, widget_key: str, default: Any = None) -> Any:
    shared_val = st.session_state.get(shared_key)
    if shared_val not in (None, ""):
        return shared_val
    widget_val = st.session_state.get(widget_key)
    if widget_val not in (None, ""):
        return widget_val
    return get_param(shared_key, default)


def _current_section_x(length_m: float) -> float | None:
    source = str(st.session_state.get("design_actions_source", get_param("design_actions_source", "max")) or "max")
    committed = bool(st.session_state.get("design_section_committed", False))
    design_x = _safe_float(st.session_state.get("design_section_x_m", get_param("design_section_x_m", 0.0)), 0.0)
    preview_x = _safe_float(st.session_state.get("section_cursor_x_m", get_param("section_cursor_x_m", 0.0)), 0.0)

    if source == "section":
        x_val = design_x if committed else preview_x
    elif committed and design_x > 0.0:
        x_val = design_x
    elif preview_x > 0.0:
        x_val = preview_x
    else:
        return None

    return x_val if 0.0 <= x_val <= length_m else None


def _get_canonical_shear_visual_loading_state() -> dict[str, Any]:
    mode = _active_limit_state_for_visuals()
    case = _normalise_loading_case(_shared_or_widget("sfd_case", "load_case", _DEFAULT_LOADING_CASE))
    length_mm = _safe_float(st.session_state.get("L", get_param("L", 3000.0)), 3000.0)
    span_m = max(length_mm / 1000.0, 0.1)
    loading_span_m = _safe_float(_shared_or_widget("span_L_m", "sfd_L_m", span_m), span_m)

    return {
        "mode": mode,
        "case": case,
        "span_m": span_m,
        "loading_span_m": max(loading_span_m, 0.0),
        "a_m": max(_safe_float(_shared_or_widget("a_m", "load_a_point", span_m / 2.0), span_m / 2.0), 0.0),
        "a_udl_m": max(_safe_float(_shared_or_widget("a_udl_m", "sfd_a_udl", span_m / 2.0), span_m / 2.0), 0.0),
        "a_cant_m": max(_safe_float(_shared_or_widget("a_cant_m", "sfd_a_cant", span_m / 2.0), span_m / 2.0), 0.0),
        "a_overhang_m": max(_safe_float(_shared_or_widget("a_overhang_m", "sfd_a_overhang", 0.0), 0.0), 0.0),
        "w_value": max(_safe_float(get_param("w_uls_kNm_per_m" if mode == "ULS" else "w_sls_kNm_per_m", 0.0), 0.0), 0.0),
        "point_value": max(_safe_float(get_param("P_uls_kN" if mode == "ULS" else "P_sls_kN", 0.0), 0.0), 0.0),
    }


def _get_canonical_shear_visual_support_state(loading_state: dict[str, Any] | None = None) -> str:
    support_pair = None
    support_resolution = None
    try:
        from deflection_support import (
            get_resolved_deflection_support_type,
            get_deflection_diagram_support_condition,
            _governing_span_support_pair,
        )

        support_type = str(get_resolved_deflection_support_type(st.session_state) or "Simply supported").strip()
        support_resolution = get_deflection_diagram_support_condition(st.session_state)
        support_pair = _governing_span_support_pair(st.session_state, support_resolution)
    except Exception:
        support_type = str(
            st.session_state.get(
                "defl_support_type",
                get_param("defl_support_type", "Simply supported"),
            )
            or "Simply supported"
        ).strip()
    if support_type == "Cantilever":
        canonical = "cantilever"
    elif support_type in ("Pinned–Pinned", "Pinned-Pinned"):
        canonical = "pinned_pinned"
    else:
        canonical = "simply_supported"
    return canonical


def _support_pair_from_resolved_support_type(support_type: str | None) -> tuple[str, str] | None:
    raw_label = str(support_type or "").strip()
    label = raw_label.replace("-", "–")
    if not label:
        return None
    if raw_label == "Fixed-ended":
        return ("Fixed", "Fixed")
    if label == "Fixed–Pinned":
        return ("Fixed", "Pinned")
    if label == "Pinned–Fixed":
        return ("Pinned", "Fixed")
    if label in ("Pinned–Pinned", "Continuous – end span", "Continuous – interior span"):
        return ("Pinned", "Pinned")
    if label == "Simply supported":
        return ("Pinned", "Roller")
    return None

def _get_canonical_shear_visual_span_state(loading_state: dict[str, Any] | None = None) -> dict[str, float]:
    loading_state = loading_state or _get_canonical_shear_visual_loading_state()
    span_m = max(_safe_float(loading_state.get("span_m", 0.0), 0.0), 0.1)
    overhang_m = max(_safe_float(loading_state.get("a_overhang_m", 0.0), 0.0), 0.0)
    total_length_m = span_m + overhang_m if str(loading_state.get("case", "")).startswith("Overhanging beam") else span_m
    return {
        "span_m": span_m,
        "overhang_m": overhang_m,
        "total_length_m": total_length_m,
    }


def _get_canonical_shear_visual_depth_state() -> dict[str, float]:
    D_m = max(_safe_float(get_param("D", 600.0), 600.0) / 1000.0, 0.1)
    d_m = _safe_float(st.session_state.get("d", get_param("d", 0.0)), 0.0) / 1000.0
    if d_m <= 0.0:
        d_m = D_m
    return {
        "D_m": D_m,
        "d_m": max(d_m, 0.05),
    }


def _get_canonical_shear_visual_section_location(length_m: float) -> float | None:
    return _current_section_x(length_m)


def _beam_model() -> dict[str, Any]:
    loading_state = _get_canonical_shear_visual_loading_state()
    support_condition = _get_canonical_shear_visual_support_state(loading_state)
    support_pair = None
    resolved_support_type = None
    try:
        from deflection_support import get_deflection_diagram_support_condition, _governing_span_support_pair

        support_resolution = get_deflection_diagram_support_condition(st.session_state)
        resolved_support_type = str(support_resolution.get("support_type") or "")
        support_pair = _governing_span_support_pair(st.session_state, support_resolution)
    except Exception:
        support_pair = None
        resolved_support_type = None
    if not isinstance(support_pair, tuple) or len(support_pair) != 2:
        support_pair = _support_pair_from_resolved_support_type(resolved_support_type)
    span_state = _get_canonical_shear_visual_span_state(loading_state)
    depth_state = _get_canonical_shear_visual_depth_state()
    section_layout = compute_section_layout()
    reo_layout = section_layout.get("reo_layout", {}) if isinstance(section_layout, dict) else {}

    bottom_layers = list(reo_layout.get("bottom", []) or [])
    top_layers = list(reo_layout.get("top", []) or [])

    support_positions = [0.0, span_state["span_m"]]
    if support_condition == "cantilever":
        support_positions = [0.0]

    return {
        **loading_state,
        **span_state,
        **depth_state,
        "support_condition": support_condition,
        "support_pair": support_pair,
        "support_positions": support_positions,
        "section_x_m": _get_canonical_shear_visual_section_location(span_state["total_length_m"]),
        "spacing_mm": max(_safe_float(get_param("s_lig", 0.0), 0.0), 0.0),
        "lig_legs": int(max(_safe_float(get_param("lig_legs", 0.0), 0.0), 0.0)),
        "bottom_layers": bottom_layers,
        "top_layers": top_layers,
        "reo_points": section_layout.get("reo_points", []) if isinstance(section_layout, dict) else [],
        "section_layout": section_layout,
    }


def _classify_shear_behaviour_visual_case(model: dict[str, Any]) -> str:
    case = str(model.get("case", "") or "")
    support_condition = str(model.get("support_condition", "simply_supported") or "simply_supported")

    if support_condition == "cantilever":
        if "point load at free end" in case:
            return "cantilever_tip"
        if "point load" in case:
            return "cantilever_eccentric"
        return "cantilever_udl"

    if case == "Simple beam – point load at centre":
        return "ss_midspan_point"
    if case == "Simple beam – point load at distance a from left":
        span_m = max(_safe_float(model.get("span_m", 0.0), 0.0), 0.1)
        load_x = max(0.0, min(_safe_float(model.get("a_m", span_m / 2.0), span_m / 2.0), span_m))
        if min(load_x, span_m - load_x) <= 0.28 * span_m:
            return "ss_near_support_point"
        return "ss_eccentric_point"
    if "UDL" in case:
        return "ss_udl"
    if case.startswith("Overhanging beam"):
        return "ss_near_support_point"
    return "fallback_simple"


def _build_behaviour_figure(length_m: float, beam_depth_m: float, height: int) -> go.Figure:
    return _shared_build_shear_behaviour_base_figure(
        length_m=length_m,
        beam_depth_m=beam_depth_m,
        height=height,
        width=BEHAVIOUR_VISUAL_WIDTH,
    )


def _cross_section_frame_size(width_mm: float, depth_mm: float) -> float:
    return max(width_mm, depth_mm) * 1.32


def _target_side_display_length(model: dict[str, Any]) -> float:
    beam_depth_m = max(_safe_float(model.get("D_m", 0.0), 0.0), 0.1)
    dims = ((model.get("section_layout") or {}).get("dims") or {})
    width_mm = _safe_float(dims.get("bf", dims.get("b", beam_depth_m * 1000.0)), beam_depth_m * 1000.0)
    cross_frame_m = _cross_section_frame_size(width_mm, beam_depth_m * 1000.0) / 1000.0
    x_range_target = cross_frame_m * (_BEAM_VIEWS_RIGHT_RATIO / _BEAM_VIEWS_LEFT_RATIO)
    return max(x_range_target - 0.4, max(0.85 * beam_depth_m, 0.18))


def _side_view_display_state(model: dict[str, Any]) -> dict[str, float | bool]:
    total_length_m = max(_safe_float(model.get("total_length_m", 0.0), 0.0), 0.1)
    beam_depth_m = max(_safe_float(model.get("D_m", 0.0), 0.0), 0.1)
    slenderness = total_length_m / beam_depth_m if beam_depth_m > 0.0 else 0.0
    if slenderness < _SIDE_VIEW_BREAK_SLENDERNESS:
        return {
            "use_break": False,
            "display_length_m": total_length_m,
            "left_keep_m": total_length_m,
            "right_start_m": total_length_m,
            "collapsed_mid_m": 0.0,
            "break_left_display_m": total_length_m * 0.5,
            "break_right_display_m": total_length_m * 0.5,
        }

    left_keep_m = min(max(0.50 * beam_depth_m, 0.025 * total_length_m, 0.12), 0.07 * total_length_m)
    right_start_m = total_length_m - left_keep_m
    hidden_mid_m = max(right_start_m - left_keep_m, 0.0)
    min_collapsed_m = max(0.45 * beam_depth_m, 0.09)
    target_display_length_m = _target_side_display_length(model)
    collapsed_mid_m = min(
        max(target_display_length_m - 2.0 * left_keep_m, min_collapsed_m),
        hidden_mid_m * 0.16 if hidden_mid_m > 0.0 else 0.0,
    )

    if hidden_mid_m <= 0.0 or collapsed_mid_m <= 0.0:
        return {
            "use_break": False,
            "display_length_m": total_length_m,
            "left_keep_m": total_length_m,
            "right_start_m": total_length_m,
            "collapsed_mid_m": 0.0,
            "break_left_display_m": total_length_m * 0.5,
            "break_right_display_m": total_length_m * 0.5,
        }

    return {
        "use_break": True,
        "display_length_m": left_keep_m + collapsed_mid_m + left_keep_m,
        "left_keep_m": left_keep_m,
        "right_start_m": right_start_m,
        "collapsed_mid_m": collapsed_mid_m,
        "break_left_display_m": left_keep_m,
        "break_right_display_m": left_keep_m + collapsed_mid_m,
    }


def _side_view_display_x(x_real: float, model: dict[str, Any]) -> float:
    state = model.get("side_view_display", {})
    if not state or not state.get("use_break"):
        return x_real

    left_keep_m = _safe_float(state.get("left_keep_m", 0.0), 0.0)
    right_start_m = _safe_float(state.get("right_start_m", 0.0), 0.0)
    collapsed_mid_m = _safe_float(state.get("collapsed_mid_m", 0.0), 0.0)
    total_length_m = max(_safe_float(model.get("total_length_m", 0.0), 0.0), 0.1)
    hidden_mid_m = max(right_start_m - left_keep_m, 0.0)

    x_real = max(0.0, min(x_real, total_length_m))
    if x_real <= left_keep_m or hidden_mid_m <= 0.0:
        return x_real
    if x_real >= right_start_m:
        return left_keep_m + collapsed_mid_m + (x_real - right_start_m)
    return left_keep_m + ((x_real - left_keep_m) / hidden_mid_m) * collapsed_mid_m


def _side_view_display_positions(values: list[float], model: dict[str, Any], *, min_spacing: float) -> list[float]:
    transformed = sorted(_side_view_display_x(x_val, model) for x_val in values)
    if not transformed:
        return []

    kept = [transformed[0]]
    for x_val in transformed[1:]:
        if x_val - kept[-1] >= min_spacing:
            kept.append(x_val)
    return kept


def _add_beam_band(fig: go.Figure, x_end: float, beam_depth_m: float | None = None) -> None:
    return _shared_add_shear_behaviour_beam_band(fig, x_end, beam_depth_m)


def _add_pinned_support(
    fig: go.Figure,
    x_pos: float,
    width: float,
    depth: float,
    beam_depth_m: float,
    *,
    roller: bool = False,
) -> None:
    return _shared_add_shear_behaviour_pinned_support(
        fig,
        x_pos,
        width,
        depth,
        beam_depth_m,
        roller=roller,
    )


def _add_fixed_support(fig: go.Figure, x_pos: float, hatch_dx: float, beam_depth_m: float) -> None:
    return _shared_add_shear_behaviour_fixed_support(fig, x_pos, hatch_dx, beam_depth_m)


def _build_shear_behaviour_support_shapes(fig: go.Figure, model: dict[str, Any]) -> None:
    return _shared_build_shear_behaviour_support_shapes(fig, model)


def _add_udl(fig: go.Figure, x0: float, x1: float, *, beam_depth_m: float, y_top: float, label: str | None = None) -> None:
    return _shared_add_shear_behaviour_udl(
        fig,
        x0,
        x1,
        beam_depth_m=beam_depth_m,
        y_top=y_top,
        label=label,
    )


def _add_point_load(fig: go.Figure, x_pos: float, *, beam_depth_m: float, y_top: float, label: str | None = None) -> None:
    return _shared_add_shear_behaviour_point_load(
        fig,
        x_pos,
        beam_depth_m=beam_depth_m,
        y_top=y_top,
        label=label,
    )


def _build_shear_behaviour_load_shapes(fig: go.Figure, model: dict[str, Any], *, show_labels: bool) -> None:
    return _shared_build_shear_behaviour_load_shapes(fig, model, show_labels=show_labels)


_side_view_y_bounds = shared_side_view_diagram.side_view_y_bounds
_build_side_view_figure = shared_side_view_diagram.build_side_view_figure
_side_view_display_state = shared_side_view_diagram.side_view_display_state
_side_view_display_length_from_model = shared_side_view_diagram.side_view_display_length_from_model
_side_view_display_x = shared_side_view_diagram.side_view_display_x
_side_view_display_positions = shared_side_view_diagram.side_view_display_positions
_add_side_view_break_marks = shared_side_view_diagram.add_side_view_break_marks
_add_side_view_pinned_support = shared_side_view_diagram.add_side_view_pinned_support
_add_side_view_fixed_support = shared_side_view_diagram.add_side_view_fixed_support
_build_side_view_support_shapes = shared_side_view_diagram.build_side_view_support_shapes


def _add_side_view_udl(fig: go.Figure, x0: float, x1: float, *, beam_depth_m: float, y_top: float, label: str | None = None) -> None:
    return shared_side_view_diagram.add_side_view_udl(
        fig,
        x0,
        x1,
        beam_depth_m=beam_depth_m,
        y_top=y_top,
        label=label,
    )


def _add_side_view_point_load(fig: go.Figure, x_pos: float, *, beam_depth_m: float, y_top: float, label: str | None = None) -> None:
    return shared_side_view_diagram.add_side_view_point_load(
        fig,
        x_pos,
        beam_depth_m=beam_depth_m,
        y_top=y_top,
        label=label,
    )


def _build_side_view_load_shapes(fig: go.Figure, model: dict[str, Any], *, show_labels: bool) -> None:
    return shared_side_view_diagram.build_side_view_load_shapes(fig, model, show_labels=show_labels)


def _no_shear_steel_inputs() -> bool:
    return shared_side_view_diagram.no_shear_steel_inputs()


def _shear_spacing_used_mm_pair(shear_zone_results: dict[str, Any] | None) -> tuple[float, float]:
    return shared_side_view_diagram.shear_spacing_used_mm_pair(shear_zone_results)


def _zone_label_is_midspan(label: str) -> bool:
    return shared_side_view_diagram.zone_label_is_midspan(label)


def _zones_metres_scaled_for_side_view(shear_zone_results: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    return shared_side_view_diagram.zones_metres_scaled_for_side_view(shear_zone_results, model)


def _get_bar_positions(x0: float, x1: float, spacing: float) -> list[float]:
    return shared_side_view_diagram.get_bar_positions(x0, x1, spacing)


def _stirrup_tuples_from_zones(
    zones: list[dict[str, Any]],
    length_m: float,
    *,
    s_global_m: float,
    support_condition: str = "simply_supported",
) -> list[tuple[float, float]]:
    return shared_side_view_diagram.stirrup_tuples_from_zones(
        zones,
        length_m,
        s_global_m=s_global_m,
        support_condition=support_condition,
    )


def _stirrup_tuples_uniform(model: dict[str, Any]) -> list[tuple[float, float]]:
    return shared_side_view_diagram.stirrup_tuples_uniform(model)


def _build_stirrup_markers(fig: go.Figure, model: dict[str, Any], *, shear_fails: bool = False) -> None:
    return shared_side_view_diagram.build_stirrup_markers(fig, model, shear_fails=shear_fails)


def _build_side_view_tension_reo(fig: go.Figure, model: dict[str, Any]) -> None:
    return shared_side_view_diagram.build_side_view_tension_reo(fig, model)


def _add_section_marker(fig: go.Figure, model: dict[str, Any]) -> None:
    return shared_side_view_diagram.add_section_marker(fig, model)


def _display_zone_length(model: dict[str, Any]) -> float:
    return _shared_display_zone_length(model)


def _support_d_region_bounds(model: dict[str, Any]) -> tuple[float, float]:
    return _shared_support_d_region_bounds(model)


def _shear_crack_x_band_m(model: dict[str, Any]) -> tuple[float, float]:
    """
    Horizontal band (m) where principal shear cracks should be drawn: flexural–shear zone only,
    outside D-regions (same extent as zone shading from _support_d_region_bounds).
    """
    return _shared_shear_crack_x_band_m(model)


# STM inner-node snapping: clean proportions of d_v / D-region width; θ_v remains exact after each adjustment.
_STM_SNAP_X_RATIOS: tuple[float, ...] = _SHARED_STM_SNAP_X_RATIOS
_STM_SNAP_Y_DV_FRACS: tuple[float, ...] = _SHARED_STM_SNAP_Y_DV_FRACS


def _stm_snap_ratio_to_grid(r_raw: float) -> float:
    return _shared_stm_snap_ratio_to_grid(r_raw)


def _stm_y_snap_levels_dv(
    d_v_m: float,
    beam_depth_m: float,
    bottom_tie_y: float,
) -> list[float]:
    return _shared_stm_y_snap_levels_dv(d_v_m, beam_depth_m, bottom_tie_y)


def _stm_snap_inner_top_left(
    x_bot: float,
    bottom_tie_y: float,
    d_region_width: float,
    tan_th: float,
    d_v_m: float,
    beam_depth_m: float,
    node_pad: float,
    dy_nom: float,
) -> tuple[float, float]:
    """
    Left support D-region (x_support = 0): snap horizontal fraction of D width, then snap y to d_v grid,
    then re-solve x for θ_v and clamp x to the D boundary (recompute y if clamped).
    """
    return _shared_stm_snap_inner_top_left(
        x_bot,
        bottom_tie_y,
        d_region_width,
        tan_th,
        d_v_m,
        beam_depth_m,
        node_pad,
        dy_nom,
    )


def _stm_snap_inner_top_right(
    x_bot: float,
    bottom_tie_y: float,
    span_m: float,
    right_d_start: float,
    tan_th: float,
    d_v_m: float,
    beam_depth_m: float,
    node_pad: float,
    dy_nom: float,
) -> tuple[float, float]:
    """Right support D-region measured from span end; same snapping policy as left."""
    return _shared_stm_snap_inner_top_right(
        x_bot,
        bottom_tie_y,
        span_m,
        right_d_start,
        tan_th,
        d_v_m,
        beam_depth_m,
        node_pad,
        dy_nom,
    )


def _build_shear_behaviour_zones(fig: go.Figure, model: dict[str, Any], case_kind: str) -> None:
    return _shared_build_shear_behaviour_zones(fig, model, case_kind)


def _sample_beam_y(sample_y: float, beam_depth_scale: float = 1.0) -> float:
    return _shared_sample_beam_y(sample_y, beam_depth_scale)


def _beam_depth_scale(model: dict[str, Any]) -> float:
    return _shared_beam_depth_scale(model)


def _field_y_limits(beam_depth_m: float = 0.6) -> tuple[float, float]:
    return _shared_field_y_limits(beam_depth_m)


def _clamp_field_points(points: list[tuple[float, float]], beam_depth_m: float = 0.6) -> list[tuple[float, float]]:
    return _shared_clamp_field_points(points, beam_depth_m)


def _add_force_line(
    fig: go.Figure,
    points: list[tuple[float, float]],
    color: str,
    width: float,
    label: str | None = None,
    label_pos: tuple[float, float] | None = None,
    opacity: float = 1.0,
    clamp_to_field: bool = True,
    smoothing: float = _FIELD_SPLINE_SMOOTHING,
    beam_depth_m: float = 0.6,
    line_shape: str = "spline",
) -> None:
    return _shared_add_force_line(
        fig,
        points,
        color,
        width,
        label=label,
        label_pos=label_pos,
        opacity=opacity,
        clamp_to_field=clamp_to_field,
        smoothing=smoothing,
        beam_depth_m=beam_depth_m,
        line_shape=line_shape,
    )


def _field_line_spec(
    points: list[tuple[float, float]],
    *,
    width: float,
    opacity: float = 1.0,
    label: str | None = None,
    label_pos: tuple[float, float] | None = None,
    smoothing: float | None = None,
) -> dict[str, Any]:
    return _shared_field_line_spec(
        points,
        width=width,
        opacity=opacity,
        label=label,
        label_pos=label_pos,
        smoothing=smoothing,
    )


def _mirror_field_line(spec: dict[str, Any], span_m: float) -> dict[str, Any]:
    return _shared_mirror_field_line(spec, span_m)


def _build_tension_family(fig: go.Figure, lines: list[dict[str, Any]]) -> None:
    return _shared_build_tension_family(fig, lines)


def _build_compression_family(fig: go.Figure, lines: list[dict[str, Any]]) -> None:
    return _shared_build_compression_family(fig, lines)


def _build_crack_cues(fig: go.Figure, cracks: list[dict[str, Any]]) -> None:
    return _shared_build_crack_cues(fig, cracks)


def _add_trajectory_family(
    fig: go.Figure,
    lines: list[list[tuple[float, float]]],
    color: str,
    *,
    width: float = 2.4,
    opacity: float = 0.62,
    smoothing: float = 0.97,
    beam_depth_m: float = 0.6,
) -> None:
    return _shared_add_trajectory_family(
        fig,
        lines,
        color,
        width=width,
        opacity=opacity,
        smoothing=smoothing,
        beam_depth_m=beam_depth_m,
    )


def _scaled_rgba_alpha(color: str, alpha_scale: float) -> str:
    return _shared_scaled_rgba_alpha(color, alpha_scale)


def _trajectory_visual_weight(line_idx: int, line_count: int) -> tuple[float, float]:
    return _shared_trajectory_visual_weight(line_idx, line_count)


def _sample_curve_point_and_tangent(
    pts: list[tuple[float, float]],
    curve_fraction: float,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    return _shared_sample_curve_point_and_tangent(pts, curve_fraction)


def _add_trajectory_direction_arrow(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    color: str,
    *,
    beam_depth_m: float,
    curve_fraction: float,
    alpha_scale: float,
    reverse: bool = False,
) -> None:
    return _shared_add_trajectory_direction_arrow(
        fig,
        pts,
        color,
        beam_depth_m=beam_depth_m,
        curve_fraction=curve_fraction,
        alpha_scale=alpha_scale,
        reverse=reverse,
    )


def _add_sparse_trajectory_arrows(
    fig: go.Figure,
    lines: list[list[tuple[float, float]]],
    color: str,
    *,
    beam_depth_m: float,
) -> None:
    return _shared_add_sparse_trajectory_arrows(
        fig,
        lines,
        color,
        beam_depth_m=beam_depth_m,
    )


def _add_load_flow_overlay(
    fig: go.Figure,
    lines: list[list[tuple[float, float]]],
    color: str,
    *,
    beam_depth_m: float,
    line_indices: list[int],
    outward_from_centre: bool = False,
    animate_motion: bool = False,
) -> None:
    return _shared_add_load_flow_overlay(
        fig,
        lines,
        color,
        beam_depth_m=beam_depth_m,
        line_indices=line_indices,
        outward_from_centre=outward_from_centre,
        animate_motion=animate_motion,
    )


def _stm_visual_context_active(model: dict[str, Any]) -> bool:
    return bool(model.get("show_stm_overlay", False) or model.get("show_stm_flow", False))


def _linear_interpolate_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    *,
    n: int,
) -> list[tuple[float, float]]:
    return _shared_linear_interpolate_points(p0, p1, n=n)


def _densify_polyline(
    pts: list[tuple[float, float]],
    *,
    n_per_seg: int = 16,
) -> list[tuple[float, float]]:
    return _shared_densify_polyline(pts, n_per_seg=n_per_seg)


def _add_stm_flow_polyline(
    fig: go.Figure,
    pts: list[tuple[float, float]],
    color: str,
    *,
    beam_depth_m: float,
    animate_motion: bool = True,
) -> None:
    return _shared_add_stm_flow_polyline(
        fig,
        pts,
        color,
        beam_depth_m=beam_depth_m,
        animate_motion=animate_motion,
    )


def _render_stm_flow_overlay(fig: go.Figure, model: dict[str, Any], case_kind: str) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_stm_flow_overlay(fig, model, case_kind, theta_v_deg=theta_v_deg)

def _blend_x(span_m: float, frac: float) -> float:
    return _shared_blend_x(span_m, frac)


def _parabolic_trajectory(
    x0: float,
    x1: float,
    y_end: float,
    y_peak: float,
    n: int = 9,
) -> list[tuple[float, float]]:
    return _shared_parabolic_trajectory(x0, x1, y_end, y_peak, n=n)


def _symmetric_arch(
    x0: float,
    x1: float,
    y_end: float,
    y_mid: float,
    *,
    n: int = 21,
    sharpness: float = 0.78,
    end_curvature_boost: float = 1.22,
) -> list[tuple[float, float]]:
    return _shared_symmetric_arch(
        x0,
        x1,
        y_end,
        y_mid,
        n=n,
        sharpness=sharpness,
        end_curvature_boost=end_curvature_boost,
    )


def _mirror_trajectory_about_middepth(
    pts: list[tuple[float, float]],
    beam_depth_m: float,
) -> list[tuple[float, float]]:
    return _shared_mirror_trajectory_about_middepth(pts, beam_depth_m)


def _support_zone_x_left() -> float:
    return _shared_support_zone_x_left()


def _support_zone_x_right(span_m: float) -> float:
    return _shared_support_zone_x_right(span_m)


def _support_edge_y_top(beam_depth_m: float) -> float:
    return _shared_support_edge_y_top(beam_depth_m)


def _support_edge_y_bot(beam_depth_m: float) -> float:
    return _shared_support_edge_y_bot(beam_depth_m)


def _add_strut_tie_node(fig: go.Figure, x: float, y: float) -> None:
    return _shared_add_strut_tie_node(fig, x, y)


def _add_stm_member(
    fig: go.Figure,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    width: float,
    *,
    opacity: float = 1.0,
    beam_depth_m: float = 0.6,
) -> None:
    return _shared_add_stm_member(
        fig,
        start,
        end,
        color,
        width,
        opacity=opacity,
        beam_depth_m=beam_depth_m,
    )


def _add_stm_axis_vertical(
    fig: go.Figure,
    x: float,
    y0: float,
    y1: float,
    color: str,
    width: float,
    *,
    opacity: float = 1.0,
    beam_depth_m: float = 0.6,
) -> None:
    return _shared_add_stm_axis_vertical(
        fig,
        x,
        y0,
        y1,
        color,
        width,
        opacity=opacity,
        beam_depth_m=beam_depth_m,
    )


def _current_mcft_theta_v_deg() -> float:
    return _safe_float(
        st.session_state.get(
            "crack_theta_deg",
            get_param("crack_theta_deg", st.session_state.get("theta_v_deg", get_param("theta_v_deg", 45.0))),
        ),
        45.0,
    )


def _add_principal_stress_orientation_square(
    fig: go.Figure,
    geometry: dict[str, float],
    *,
    principal_angle_deg: float,
    centre: tuple[float, float] | None = None,
) -> None:
    return _shared_add_principal_stress_orientation_square(
        fig,
        geometry,
        principal_angle_deg=principal_angle_deg,
        centre=centre,
    )

def _segment_intersection(
    a0: tuple[float, float],
    a1: tuple[float, float],
    b0: tuple[float, float],
    b1: tuple[float, float],
) -> tuple[float, float, float, float] | None:
    return _shared_segment_intersection(a0, a1, b0, b1)


def _polyline_polyline_best_hit(
    pc: list[tuple[float, float]],
    pt: list[tuple[float, float]],
    x_lo: float,
    x_hi: float,
) -> tuple[float, float, float, float, float, float] | None:
    """Rightmost segment-segment hit between two polylines within x ∈ [x_lo, x_hi]."""
    return _shared_polyline_polyline_best_hit(pc, pt, x_lo, x_hi)


def _polyline_y_at_x(poly: list[tuple[float, float]], xq: float) -> float | None:
    """Linearly interpolated y on polyline at x = xq (first matching segment)."""
    return _shared_polyline_y_at_x(poly, xq)


def _polyline_tangent_at_x(poly: list[tuple[float, float]], xq: float) -> tuple[float, float] | None:
    """Unnormalised tangent (dx, dy) on the segment that contains xq."""
    return _shared_polyline_tangent_at_x(poly, xq)


def _polyline_segment_best_hit(
    poly: list[tuple[float, float]],
    s0: tuple[float, float],
    s1: tuple[float, float],
    x_lo: float,
    x_hi: float,
) -> tuple[float, float, float, float] | None:
    """Rightmost intersection of polyline with segment s0–s1 inside x band; returns px, py, tx, ty on poly."""
    return _shared_polyline_segment_best_hit(poly, s0, s1, x_lo, x_hi)


def _cantilever_principal_crack_hits(
    compression: list[list[tuple[float, float]]],
    tension: list[list[tuple[float, float]]],
    span_m: float,
    model: dict[str, Any],
) -> list[dict[str, float]]:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_cantilever_principal_crack_hits(
        compression,
        tension,
        span_m,
        model,
        theta_v_deg=theta_v_deg,
    )

def _cantilever_refine_crack_hit_for_compression_field(
    h: dict[str, float],
    compression: list[list[tuple[float, float]]],
    span_m: float,
    *,
    x_lo: float,
    x_hi: float,
) -> dict[str, float]:
    """
    Shift hit right and vertically centre between two adjacent compression trajectories; align crack
    and stress-block rotation with local compression tangent + anti-clockwise offset. Stress block
    applies +20° internally, so principal_deg is reduced by 20° to match net orientation.
    """
    return _shared_cantilever_refine_crack_hit_for_compression_field(
        h,
        compression,
        span_m,
        x_lo=x_lo,
        x_hi=x_hi,
    )


def _principal_stress_marker_state(
    tension: list[list[tuple[float, float]]],
    compression: list[list[tuple[float, float]]],
    geometry: dict[str, float] | None = None,
) -> tuple[tuple[float, float], float] | None:
    return _shared_principal_stress_marker_state(tension, compression, geometry)


def _add_principal_shear_crack_example(
    fig: go.Figure,
    tension: list[list[tuple[float, float]]],
    compression: list[list[tuple[float, float]]],
    geometry: dict[str, float],
    marker_centre: tuple[float, float] | None = None,
    marker_angle_deg: float | None = None,
    *,
    cantilever_mode: bool = False,
) -> None:
    return _shared_add_principal_shear_crack_example(
        fig,
        tension,
        compression,
        geometry,
        marker_centre=marker_centre,
        marker_angle_deg=marker_angle_deg,
        cantilever_mode=cantilever_mode,
    )

def _add_stm_joint_angle_annotation(
    fig: go.Figure,
    joint: tuple[float, float],
    strut_end: tuple[float, float],
    text: str,
    *,
    color: str,
    beam_depth_m: float,
    tie_direction: str,
) -> None:
    return _shared_add_stm_joint_angle_annotation(
        fig,
        joint,
        strut_end,
        text,
        color=color,
        beam_depth_m=beam_depth_m,
        tie_direction=tie_direction,
    )


def _add_ordered_trajectory_family(
    fig: go.Figure,
    lines: list[list[tuple[float, float]]],
    color: str,
    *,
    width: float = 2.4,
    opacity: float = 0.62,
    smoothing: float = 0.97,
    beam_depth_m: float = 0.6,
    line_shape: str = "spline",
) -> None:
    return _shared_add_ordered_trajectory_family(
        fig,
        lines,
        color,
        width=width,
        opacity=opacity,
        smoothing=smoothing,
        beam_depth_m=beam_depth_m,
        line_shape=line_shape,
    )


def _compute_stress_field_geometry(model: dict[str, Any]) -> dict[str, float]:
    return _shared_compute_stress_field_geometry(model)


def _compute_trajectory_count(slenderness: float) -> int:
    return _shared_compute_trajectory_count(slenderness)


def _sample_anchor_band(count: int) -> list[float]:
    return _shared_sample_anchor_band(count)


def _compute_trajectory_half_widths(geometry: dict[str, float], count: int) -> list[float]:
    return _shared_compute_trajectory_half_widths(geometry, count)


def _trajectory_bow_scale(geometry: dict[str, float], width_factor: float) -> float:
    return _shared_trajectory_bow_scale(geometry, width_factor)


def _trajectory_end_curvature_boost(geometry: dict[str, float], width_factor: float) -> float:
    return _shared_trajectory_end_curvature_boost(geometry, width_factor)


def _build_tensile_trajectories(geometry: dict[str, float], count: int) -> list[list[tuple[float, float]]]:
    return _shared_build_tensile_trajectories(geometry, count)


def _build_compressive_trajectories(geometry: dict[str, float], count: int) -> list[list[tuple[float, float]]]:
    return _shared_build_compressive_trajectories(geometry, count)


def _render_principal_stress_ss_udl(fig: go.Figure, model: dict[str, Any]) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_principal_stress_ss_udl(fig, model, theta_v_deg=theta_v_deg)


def _render_principal_stress_ss_midspan_point(fig: go.Figure, model: dict[str, Any]) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_principal_stress_ss_midspan_point(fig, model, theta_v_deg=theta_v_deg)


def _render_principal_stress_ss_eccentric_point(fig: go.Figure, model: dict[str, Any]) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_principal_stress_ss_eccentric_point(fig, model, theta_v_deg=theta_v_deg)


def _render_principal_stress_ss_near_support_point(fig: go.Figure, model: dict[str, Any]) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_principal_stress_ss_near_support_point(fig, model, theta_v_deg=theta_v_deg)


def _render_principal_stress_cantilever_tip(fig: go.Figure, model: dict[str, Any]) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_principal_stress_cantilever_tip(fig, model, theta_v_deg=theta_v_deg)


def _render_principal_stress_cantilever_udl(fig: go.Figure, model: dict[str, Any]) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_principal_stress_cantilever_udl(fig, model, theta_v_deg=theta_v_deg)


def _render_principal_stress_cantilever_eccentric(fig: go.Figure, model: dict[str, Any]) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_principal_stress_cantilever_eccentric(fig, model, theta_v_deg=theta_v_deg)


def _compute_stm_simply_supported_d_region_nodes(
    model: dict[str, Any],
) -> dict[str, Any] | None:
    """
    D-region STM: bottom tie beam-wide; red struts at each support. Inner top nodes are snapped to
    clean fractions of d_v (vertical) and of D-region width (horizontal), then x/y are reconciled so
    strut angle equals θ_v exactly (clamp to D boundary recomputes the other coordinate).
    """
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_compute_stm_simply_supported_d_region_nodes(model, theta_v_deg=theta_v_deg)


def _compute_stm_cantilever_d_region_nodes(model: dict[str, Any]) -> dict[str, Any] | None:
    """D-region STM at fixed support; same d_v / D-width snapping as SS left strut; θ_v exact."""
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_compute_stm_cantilever_d_region_nodes(model, theta_v_deg=theta_v_deg)


def _render_strut_tie_ss_udl(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_strut_tie_ss_udl(
        fig,
        model,
        theta_v_deg=theta_v_deg,
        show_labels=show_labels,
    )

def _render_strut_tie_ss_midspan_point(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    _render_strut_tie_ss_udl(fig, model, show_labels=show_labels)


def _render_strut_tie_ss_eccentric_point(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    # Illustrative STM is D-region idealisation only (same dual D-region layout as UDL).
    _render_strut_tie_ss_udl(fig, model, show_labels=show_labels)


def _render_strut_tie_ss_near_support_point(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    _render_strut_tie_ss_eccentric_point(fig, model, show_labels=show_labels)


def _render_strut_tie_cantilever_tip(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_strut_tie_cantilever_tip(
        fig,
        model,
        theta_v_deg=theta_v_deg,
        show_labels=show_labels,
    )

def _render_strut_tie_cantilever_udl(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    _render_strut_tie_cantilever_tip(fig, model, show_labels=show_labels)


def _render_strut_tie_cantilever_eccentric(fig: go.Figure, model: dict[str, Any], *, show_labels: bool = True) -> None:
    _render_strut_tie_cantilever_tip(fig, model, show_labels=show_labels)


def _render_stm_overlay(fig: go.Figure, model: dict[str, Any], case_kind: str) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_render_stm_overlay(fig, model, case_kind, theta_v_deg=theta_v_deg)


def _add_stm_overlay_labels(fig: go.Figure, model: dict[str, Any], case_kind: str) -> None:
    theta_v_deg = _safe_float(model.get("theta_v_deg", _current_mcft_theta_v_deg()), _current_mcft_theta_v_deg())
    return _shared_add_stm_overlay_labels(fig, model, case_kind, theta_v_deg=theta_v_deg)


def _cantilever_behaviour_zones(model: dict[str, Any]) -> tuple[float, float]:
    return _shared_cantilever_behaviour_zones(model)


def _render_field_ss_midspan_point(fig: go.Figure, model: dict[str, Any]) -> None:
    return _shared_render_field_ss_midspan_point(fig, model)


def _render_field_ss_udl(fig: go.Figure, model: dict[str, Any]) -> None:
    return _shared_render_field_ss_udl(fig, model)


def _render_field_ss_eccentric_point(fig: go.Figure, model: dict[str, Any]) -> None:
    return _shared_render_field_ss_eccentric_point(fig, model)


def _render_field_ss_near_support_point(fig: go.Figure, model: dict[str, Any]) -> None:
    return _shared_render_field_ss_near_support_point(fig, model)


def _render_field_cantilever_tip(fig: go.Figure, model: dict[str, Any]) -> None:
    return _shared_render_field_cantilever_tip(fig, model)


def _render_field_cantilever_udl(fig: go.Figure, model: dict[str, Any]) -> None:
    return _shared_render_field_cantilever_udl(fig, model)


def _render_field_cantilever_eccentric(fig: go.Figure, model: dict[str, Any]) -> None:
    return _shared_render_field_cantilever_eccentric(fig, model)


def _render_shear_behaviour_field(
    fig: go.Figure,
    model: dict[str, Any],
    case_kind: str,
    visual_mode: str = "Principal stress field",
) -> None:
    if case_kind == "ss_midspan_point":
        _render_principal_stress_ss_midspan_point(fig, model)
    elif case_kind == "ss_udl":
        _render_principal_stress_ss_udl(fig, model)
    elif case_kind == "ss_near_support_point":
        _render_principal_stress_ss_near_support_point(fig, model)
    elif case_kind == "ss_eccentric_point":
        _render_principal_stress_ss_eccentric_point(fig, model)
    elif case_kind == "cantilever_tip":
        _render_principal_stress_cantilever_tip(fig, model)
    elif case_kind == "cantilever_udl":
        _render_principal_stress_cantilever_udl(fig, model)
    elif case_kind == "cantilever_eccentric":
        _render_principal_stress_cantilever_eccentric(fig, model)
    else:
        _render_principal_stress_ss_udl(fig, model)

    if bool(model.get("show_stm_geometry", model.get("show_stm_overlay", False))):
        _render_stm_overlay(fig, model, case_kind)
    if bool(model.get("show_stm_flow", False)):
        _render_stm_flow_overlay(fig, model, case_kind)


def build_shear_cross_section_figure(height: int = VISUAL_HEIGHT) -> go.Figure:
    layout = compute_section_layout()
    sec_shape = str(st.session_state.get("sec_shape", get_param("sec_shape", "RECT")) or "RECT")
    _, top_reo_label = main_longitudinal_reo_pair_labels(sec_shape, variant="inputs_compact")
    return build_shear_cross_section_figure_from_layout(
        layout=layout,
        height=height,
        active_tension_face=st.session_state.get("active_tension_face"),
        top_reo_label=top_reo_label,
    )


def build_shear_side_view_figure(
    height: int = SIDE_VIEW_VISUAL_HEIGHT,
    *,
    shear_fails: bool = False,
) -> go.Figure:
    model = _beam_model()
    if shear_fails:
        # Preserve the existing failure-specific link annotations.
        model["side_view_display"] = _side_view_display_state(model)
        display_length_m = _side_view_display_length_from_model(model)
        fig = _build_side_view_figure(
            model["total_length_m"],
            model["D_m"],
            height,
            model["support_condition"],
            display_length_m=display_length_m,
        )
        _add_beam_band(fig, display_length_m, model["D_m"])
        _build_side_view_support_shapes(fig, model)
        _build_side_view_tension_reo(fig, model)
        _build_stirrup_markers(fig, model, shear_fails=True)
        return fig
    return shared_side_view_diagram.build_standard_reinforced_beam_side_view(
        model,
        height=height,
    )


def build_shear_behaviour_figure(
    height: int = BEHAVIOUR_VISUAL_HEIGHT,
    visual_mode: str = "Principal stress field",
    theta_v_deg: float | None = None,
    show_load_flow: bool = False,
    show_cracks: bool = True,
    show_stress_block: bool = True,
    show_stm_overlay: bool = False,
    show_stm_flow: bool = False,
) -> go.Figure:
    model = _beam_model()
    if theta_v_deg is not None:
        model["theta_v_deg"] = theta_v_deg
    model["show_load_flow"] = bool(show_load_flow)
    model["show_cracks"] = bool(show_cracks)
    model["show_stress_block"] = bool(show_stress_block)
    model["show_stm_overlay"] = bool(show_stm_overlay)
    model["show_stm_flow"] = bool(show_stm_flow)
    model["show_stm_geometry"] = bool(show_stm_overlay or show_stm_flow)
    case_kind = _classify_shear_behaviour_visual_case(model)
    fig = _build_behaviour_figure(model["total_length_m"], model["D_m"], height)
    _add_beam_band(fig, model["total_length_m"], model["D_m"])
    _build_shear_behaviour_support_shapes(fig, model)
    _build_shear_behaviour_load_shapes(fig, model, show_labels=False)
    _build_shear_behaviour_zones(fig, model, case_kind)
    _render_shear_behaviour_field(fig, model, case_kind, visual_mode)
    return fig


def build_shrinkage_schematic_plotly(width_px: int = 1100, height_px: int = 420) -> go.Figure:
    return _shared_build_shrinkage_schematic_plotly(width_px=width_px, height_px=height_px)


def build_creep_schematic_plotly(width_px: int = 1100, height_px: int = 420) -> go.Figure:
    return _shared_build_creep_schematic_plotly(width_px=width_px, height_px=height_px)
