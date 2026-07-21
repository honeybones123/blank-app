"""Render-only Inputs diagram coordinators.

These helpers own page composition order for diagram panels only. They receive
Streamlit and page-local render callbacks explicitly so engineering/data
ownership stays with the existing modules and wrappers.
"""

from __future__ import annotations

from typing import Any, Callable


def render_inputs_fast_model_block(
    *,
    st_module: Any,
    sync_callbacks: dict,
    model_state: dict | None,
    shared_toggle_fn: Callable[..., bool],
    render_with_temporary_model_state_fn: Callable[..., Any],
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
        render_with_temporary_model_state_fn(
            model_state,
            lambda: render_3d_diagram_block_fn(compact=True, model_state=model_state),
        )
    else:
        render_with_temporary_model_state_fn(
            model_state,
            lambda: render_section_2d_diagram_block_fn(compact=True, model_state=model_state),
        )


def render_inputs_section_2d_diagram_block(
    *,
    st_module: Any,
    compact: bool = False,
    model_state: dict | None = None,
    time_perf_counter_fn: Callable[[], float],
    inputs_geometry_fingerprint_fn: Callable[..., Any],
    make_summary_cross_section_figure_fn: Callable[[], Any],
    copy_deepcopy_fn: Callable[[Any], Any],
    render_plotly_diagram_fn: Callable[..., Any],
) -> None:
    """Render the 2D section diagram only using page-supplied callbacks."""

    time_perf_counter_fn()
    sec_shape = st_module.session_state.get("sec_shape", "RECT")

    if sec_shape == "RECT":
        required = ["b", "D"]
    elif sec_shape == "T":
        required = ["bf", "tf", "bw", "D"]
    else:
        required = ["bf", "tf", "tw", "D"]

    missing = [key for key in required if st_module.session_state.get(key) in (None, "", 0)]
    if missing:
        st_module.info("2D section diagram not available right now (inputs are still saved).")
        return

    fig_sec = None
    try:
        geo_fp = inputs_geometry_fingerprint_fn(model_state)
        cached_fp = st_module.session_state.get("_inputs_model_2d_geo_fp")
        cached_fig = st_module.session_state.get("_inputs_model_2d_fig")
        if cached_fp == geo_fp and cached_fig is not None:
            fig_sec = copy_deepcopy_fn(cached_fig)
        else:
            fig_sec = make_summary_cross_section_figure_fn()
            if fig_sec is None:
                raise ValueError("2D section diagram function returned None (fig is None)")
            st_module.session_state["_inputs_model_2d_fig"] = copy_deepcopy_fn(fig_sec)
            st_module.session_state["_inputs_model_2d_geo_fp"] = geo_fp
    except Exception as exc:
        st_module.warning(f"2D section diagram failed: {exc}")
        with st_module.expander("Diagram debug details"):
            st_module.exception(exc)
        return

    if fig_sec is not None:
        try:
            fig_sec.update_layout(
                autosize=True,
                height=(475 if compact else 545),
                margin=dict(l=4, r=4, t=4, b=4),
            )
        except Exception:
            pass
        st_module.markdown('<div class="inputs-page-main-diagram-wrap">', unsafe_allow_html=True)
        render_plotly_diagram_fn(
            fig_sec,
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st_module.markdown("</div>", unsafe_allow_html=True)


def render_inputs_3d_diagram_block(
    *,
    st_module: Any,
    compact: bool = False,
    model_state: dict | None = None,
    time_perf_counter_fn: Callable[[], float],
    inputs_geometry_fingerprint_fn: Callable[..., Any],
    copy_deepcopy_fn: Callable[[Any], Any],
    compute_section_layout_fn: Callable[[], dict],
    shared_state_snapshot_fn: Callable[[], dict],
    cache_json_fn: Callable[[Any], str],
    cached_make_section_3d_figure_fn: Callable[..., Any],
    make_beam_3d_figure_fn: Callable[[], Any],
    render_plotly_diagram_fn: Callable[..., Any],
) -> None:
    """Render the 3D section/beam diagram only using page-supplied callbacks."""

    time_perf_counter_fn()
    geo_fp = inputs_geometry_fingerprint_fn(model_state)
    cache_payload = st_module.session_state.get("_inputs_model_3d_cache", {})
    cached_fp = cache_payload.get("geo_fp")
    cached_shape = cache_payload.get("shape_name")
    cached_fig = cache_payload.get("fig")
    if cached_fp == geo_fp and cached_fig is not None and isinstance(cached_shape, str):
        shape_name = cached_shape
        fig3d = copy_deepcopy_fn(cached_fig)
    else:
        layout = compute_section_layout_fn()
        shape_name = layout.get("shape_name", "Rectangle (b Ã— D)")
        dims = layout.get("dims", {})
        reo = dict(layout.get("reo", {}))
        shared_state = dict(model_state) if isinstance(model_state, dict) else shared_state_snapshot_fn()
        reo["lig_d"] = float(shared_state.get("lig_d", reo.get("lig_d", 0.0)) or 0.0)
        reo["lig_legs"] = int(shared_state.get("lig_legs", reo.get("lig_legs", 0)) or 0)
        reo["s_lig"] = float(shared_state.get("s_lig", reo.get("s_lig", 200.0)) or 200.0)
        reo_layout = layout.get("reo_layout", {})
        if shape_name.startswith(("T-Section", "I-Section")):
            if not isinstance(reo_layout, dict):
                reo_layout = {"top": [], "bottom": []}
            fig3d = cached_make_section_3d_figure_fn(
                shape_name=shape_name,
                dims_json=cache_json_fn(dims),
                reo_layout_json=cache_json_fn(reo_layout),
                reo_inputs_json=cache_json_fn(reo),
                show_shear=True,
                L_vis=900.0,
            )
        else:
            fig3d = make_beam_3d_figure_fn()
        st_module.session_state["_inputs_model_3d_cache"] = {
            "geo_fp": geo_fp,
            "shape_name": shape_name,
            "fig": copy_deepcopy_fn(fig3d),
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
