"""Render-only Inputs diagram coordinators.

These helpers own page composition order for diagram panels only. They receive
typed region contexts and page-local render callbacks explicitly so
engineering/data ownership stays outside the render layer.
"""

from __future__ import annotations

import html
from typing import Any, Callable

from inputs_application.region_contexts import RevisionIdentity

from .models import InputsBeam3DRegionContext, InputsSection2DRegionContext


def _format_reo_number(value: Any) -> str:
    numeric = float(value or 0.0)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:g}"


def _longitudinal_arrangement_label(layers: Any) -> str:
    parts: list[str] = []
    for layer in list(layers or []):
        if not isinstance(layer, dict):
            continue
        count = len(list(layer.get("x") or []))
        diameter = float(layer.get("db", 0.0) or 0.0)
        if count > 0 and diameter > 0.0:
            parts.append(f"{count}N{_format_reo_number(diameter)}")
    return " + ".join(parts) if parts else "None"


def _render_reinforcement_arrangement_labels(
    *,
    st_module: Any,
    reo_layout: Any,
    reo: Any,
) -> None:
    """Label the exact reinforcement arrangement drawn by the model."""

    resolved_layout = dict(reo_layout or {})
    resolved_reo = dict(reo or {})
    bottom = _longitudinal_arrangement_label(resolved_layout.get("bottom"))
    top = _longitudinal_arrangement_label(resolved_layout.get("top"))
    link_diameter = float(resolved_reo.get("lig_d", 0.0) or 0.0)
    link_legs = int(float(resolved_reo.get("lig_legs", 0) or 0))
    link_spacing = float(resolved_reo.get("s_lig", 0.0) or 0.0)
    if link_diameter > 0.0 and link_legs >= 2 and link_spacing > 0.0:
        links = (
            f"{link_legs}-leg N{_format_reo_number(link_diameter)}"
            f" @ {_format_reo_number(link_spacing)} mm"
        )
    else:
        links = "Off"

    st_module.markdown(
        (
            '<div class="inputs-model-reo-labels" aria-label="Reinforcement arrangement">'
            f'<span><i class="inputs-model-reo-dot inputs-model-reo-dot--bottom"></i>Bottom: {html.escape(bottom)}</span>'
            f'<span><i class="inputs-model-reo-dot inputs-model-reo-dot--top"></i>Top: {html.escape(top)}</span>'
            f'<span><i class="inputs-model-reo-dot inputs-model-reo-dot--links"></i>Links: {html.escape(links)}</span>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_inputs_fast_model_block(
    *,
    st_module: Any,
    sync_callbacks: dict,
    model_state: dict | None,
    shared_toggle_fn: Callable[..., bool],
    render_3d_diagram_block_fn: Callable[..., Any],
    render_section_2d_diagram_block_fn: Callable[..., Any],
) -> None:
    title_col, toggle_col = st_module.columns([4.0, 1.4], gap="small")
    with title_col:
        st_module.markdown("## Model")
    with toggle_col:
        show_3d = shared_toggle_fn(
            "3D model",
            "inputs_fast_mode_show_3d_toggle",
            "fast_mode_show_3d",
            False,
            sync_callbacks,
        )
    if show_3d:
        render_3d_diagram_block_fn(compact=True, model_state=model_state)
    else:
        render_section_2d_diagram_block_fn(compact=True, model_state=model_state)


def render_inputs_section_2d_diagram_block(
    *,
    st_module: Any,
    region_context: InputsSection2DRegionContext,
    current_input_identity_fn: Callable[[], RevisionIdentity | None],
    compact: bool = False,
    height_scale: float = 1.0,
    time_perf_counter_fn: Callable[[], float],
    build_summary_cross_section_result_fn: Callable[..., Any],
    section_figure_builder_fn: Callable[..., Any],
    copy_deepcopy_fn: Callable[[Any], Any],
    render_plotly_diagram_fn: Callable[..., Any],
) -> None:
    """Render only the 2D context that still matches current input authority."""

    render_started = time_perf_counter_fn()
    current_identity = current_input_identity_fn()
    if current_identity != region_context.identity:
        st_module.info("2D section diagram is updating to the latest inputs.")
        return

    view_model = region_context.view_model
    shape_name = str(view_model.shape_name or "").strip().lower()
    if "rectangle" in shape_name or shape_name == "rect":
        required = ["b", "D"]
    elif shape_name.startswith("t"):
        required = ["bf", "tf", "bw", "D"]
    else:
        required = ["bf", "tf", "tw", "D"]

    missing = [key for key in required if view_model.dims.get(key) in (None, "", 0)]
    if missing:
        st_module.info("2D section diagram not available right now (inputs are still saved).")
        return

    fig_sec = None
    cache_mode = "miss"
    figure_started = time_perf_counter_fn()
    try:
        geo_fp = view_model.display_hash
        cached_fp = st_module.session_state.get("_inputs_model_2d_geo_fp")
        cached_fig = st_module.session_state.get("_inputs_model_2d_fig")
        if cached_fp == geo_fp and cached_fig is not None:
            cache_mode = "hit"
            fig_sec = copy_deepcopy_fn(cached_fig)
        else:
            result = build_summary_cross_section_result_fn(
                layout=region_context.layout,
                tension_face=view_model.tension_face,
                fallback_cover_side=float(view_model.fallback_cover_side),
                fallback_cover_top=float(view_model.fallback_cover_top),
                fallback_cover_bot=float(view_model.fallback_cover_bot),
                section_figure_builder=section_figure_builder_fn,
            )
            fig_sec = result.figure
            if fig_sec is None:
                raise ValueError("2D section diagram function returned None (fig is None)")
            st_module.session_state["_inputs_model_2d_fig"] = copy_deepcopy_fn(fig_sec)
            st_module.session_state["_inputs_model_2d_geo_fp"] = geo_fp
        st_module.session_state["_inputs_model_2d_source_identity"] = {
            "beam_id": region_context.beam_id,
            "input_revision": region_context.identity.input_revision,
            "engineering_hash": region_context.identity.engineering_hash,
            "display_hash": geo_fp,
        }
    except Exception as exc:
        st_module.warning(f"2D section diagram failed: {exc}")
        with st_module.expander("Diagram debug details"):
            st_module.exception(exc)
        return
    figure_prepare_ms = (time_perf_counter_fn() - figure_started) * 1000.0

    if fig_sec is not None:
        try:
            fig_sec.update_layout(
                autosize=True,
                height=int((475 if compact else 545) * max(0.25, float(height_scale))),
                margin=dict(l=4, r=4, t=4, b=4),
            )
        except Exception:
            pass
        st_module.markdown('<div class="inputs-page-main-diagram-wrap">', unsafe_allow_html=True)
        chart_started = time_perf_counter_fn()
        render_plotly_diagram_fn(
            fig_sec,
            key="inputs_section_2d_model_chart",
            use_container_width=True,
            config={"displayModeBar": False},
        )
        chart_emit_ms = (time_perf_counter_fn() - chart_started) * 1000.0
        st_module.markdown("</div>", unsafe_allow_html=True)
        _render_reinforcement_arrangement_labels(
            st_module=st_module,
            reo_layout=region_context.layout.get("reo_layout"),
            reo=region_context.layout.get("reo"),
        )
        st_module.session_state["_inputs_last_2d_diagram_timings_ms"] = {
            "cache_mode": cache_mode,
            "figure_prepare": round(figure_prepare_ms, 3),
            "chart_emit": round(chart_emit_ms, 3),
            "total": round(
                (time_perf_counter_fn() - render_started) * 1000.0,
                3,
            ),
        }


def render_inputs_3d_diagram_block(
    *,
    st_module: Any,
    region_context: InputsBeam3DRegionContext,
    current_input_identity_fn: Callable[[], RevisionIdentity | None],
    compact: bool = False,
    time_perf_counter_fn: Callable[[], float],
    copy_deepcopy_fn: Callable[[Any], Any],
    cache_json_fn: Callable[[Any], str],
    cached_make_section_3d_figure_fn: Callable[..., Any],
    build_inputs_beam_3d_figure_fn: Callable[..., Any],
    render_plotly_diagram_fn: Callable[..., Any],
) -> None:
    """Render only the 3D context that still matches current input authority."""

    render_started = time_perf_counter_fn()
    current_identity = current_input_identity_fn()
    if current_identity != region_context.identity:
        st_module.info("3D model is updating to the latest inputs.")
        return

    view_model = region_context.view_model
    geo_fp = view_model.display_hash
    cache_payload = st_module.session_state.get("_inputs_model_3d_cache", {})
    cached_fp = cache_payload.get("geo_fp")
    cached_shape = cache_payload.get("shape_name")
    cached_fig = cache_payload.get("fig")
    if cached_fp == geo_fp and cached_fig is not None and isinstance(cached_shape, str):
        cache_mode = "hit"
        shape_name = cached_shape
        fig3d = copy_deepcopy_fn(cached_fig)
    else:
        cache_mode = "miss"
        shape_name = view_model.shape_name
        if shape_name.startswith(("T-Section", "I-Section")):
            dims = dict(region_context.layout.get("dims") or {})
            reo = dict(region_context.layout.get("reo") or {})
            reo.update(
                {
                    "cover_bot": view_model.cover_bot,
                    "cover_top": view_model.cover_top,
                    "cover_side": view_model.cover_side,
                    "lig_d": view_model.lig_d,
                    "lig_legs": view_model.lig_legs,
                    "s_lig": view_model.s_lig,
                }
            )
            reo_layout = dict(view_model.reo_layout or {"top": [], "bottom": []})
            fig3d = cached_make_section_3d_figure_fn(
                shape_name=shape_name,
                dims_json=cache_json_fn(dims),
                reo_layout_json=cache_json_fn(reo_layout),
                reo_inputs_json=cache_json_fn(reo),
                show_shear=True,
                L_vis=900.0,
            )
        else:
            fig3d = build_inputs_beam_3d_figure_fn(
                shape_name=view_model.shape_name,
                shape_key=view_model.shape_key,
                outline_points=list(view_model.outline_points),
                b_box=float(view_model.b_box),
                D=float(view_model.D),
                L_plot=float(view_model.L_plot),
                fallback_width=float(view_model.fallback_width),
                cover_bot=float(view_model.cover_bot),
                cover_top=float(view_model.cover_top),
                cover_side=float(view_model.cover_side),
                lig_d=float(view_model.lig_d),
                lig_legs=int(view_model.lig_legs),
                s_lig=float(view_model.s_lig),
                reo_layout=dict(view_model.reo_layout or {}),
                cage=dict(view_model.cage or {}),
                resolved_bars=list(view_model.resolved_bars or ()),
            )
        st_module.session_state["_inputs_model_3d_cache"] = {
            "geo_fp": geo_fp,
            "shape_name": shape_name,
            "fig": copy_deepcopy_fn(fig3d),
        }
    st_module.session_state["_inputs_model_3d_source_identity"] = {
        "beam_id": region_context.beam_id,
        "input_revision": region_context.identity.input_revision,
        "engineering_hash": region_context.identity.engineering_hash,
        "display_hash": geo_fp,
    }

    st_module.markdown(
        """
        <style>
        div[data-testid="stPlotlyChart"] {
          border: 1px solid rgba(0,0,0,0.12);
          border-radius: 8px;
          background: #fff;
          overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if shape_name.startswith(("T-Section", "I-Section")):
        base_h = 360 if compact else 420
        fig3d.update_layout(
            height=int(int(base_h * 7 / 5) * 0.88),
            margin=dict(l=4, r=4, t=4, b=4),
        )
        st_module.markdown('<div class="inputs-page-main-diagram-wrap">', unsafe_allow_html=True)
        render_plotly_diagram_fn(
            fig3d,
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st_module.markdown("</div>", unsafe_allow_html=True)
    else:
        base_h = 410 if compact else 480
        h3d = int(int(base_h * 7 / 5) * 0.88)
        fig3d.update_layout(
            height=h3d,
            margin=dict(l=4, r=4, t=4, b=4),
        )
        st_module.markdown('<div class="inputs-page-main-diagram-wrap">', unsafe_allow_html=True)
        render_plotly_diagram_fn(
            fig3d,
            width="stretch",
            height=h3d,
            config={"displayModeBar": True},
        )
        st_module.markdown("</div>", unsafe_allow_html=True)

    _render_reinforcement_arrangement_labels(
        st_module=st_module,
        reo_layout=view_model.reo_layout,
        reo={
            "lig_d": view_model.lig_d,
            "lig_legs": view_model.lig_legs,
            "s_lig": view_model.s_lig,
        },
    )

    st_module.session_state["_inputs_last_3d_diagram_timings_ms"] = {
        "cache_mode": cache_mode,
        "total": round((time_perf_counter_fn() - render_started) * 1000.0, 3),
    }
