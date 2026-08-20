"""Bending diagram section helpers."""

from __future__ import annotations


def _install_material_teaching_override(namespace: dict) -> None:
    """Replace only the bending material expander body with the styled lesson.

    ``bending_page_runtime`` already delegates diagram helpers through
    ``bind_runtime``.  Use that existing seam so the large page coordinator does
    not need a second copy of the teaching markup.  Engineering state and plot
    builders remain owned by the runtime; this wrapper changes presentation only.
    """

    original = namespace.get("render_lazy_expander")
    if original is None or getattr(original, "_sb_material_teaching_override", False):
        return

    def render_lazy_expander_with_material_lesson(label, render_body, *args, **kwargs):
        if kwargs.get("key") != "bending_material_model_expander":
            return original(label, render_body, *args, **kwargs)

        def render_styled_material_lesson() -> None:
            from engineering_page_sections.bending_material_teaching import (
                render_bending_material_teaching_panel,
            )

            st_module = namespace["st"]
            selected_state = str(
                st_module.session_state.get(
                    "bending_state_main",
                    st_module.session_state.get("bending_state", "ULS"),
                )
                or "ULS"
            )
            render_bending_material_teaching_panel(
                selected_state=selected_state,
                plot_material_curves=namespace["_plot_material_stress_strain_curves"],
                render_plotly_diagram=namespace["render_plotly_diagram"],
            )

        return original(
            "ℹ️ From strain to stress to internal force",
            render_styled_material_lesson,
            *args,
            **kwargs,
        )

    render_lazy_expander_with_material_lesson._sb_material_teaching_override = True
    namespace["render_lazy_expander"] = render_lazy_expander_with_material_lesson


def bind_runtime(namespace: dict) -> None:
    globals().update({key: value for key, value in namespace.items() if not key.startswith("__")})
    _install_material_teaching_override(namespace)


def render_bending_diagram_loading_shell(container, *, generation: int) -> None:
    """Reserve the measured diagram region while its figures are prepared.

    The completed Bending diagram block is 647.16 px high at both locked
    desktop and narrow viewports.  Publishing that footprint before the
    calculation cards are rendered lets the useful page stream immediately
    without moving later content when the real diagrams replace the shell.
    """

    with container:
        st.markdown(
            """
        <style>
        .bending-diagram-loading-region {
          box-sizing: border-box;
          height: 647.15625px;
          width: 100%;
          overflow: hidden;
          color: #10234a;
        }
        .bending-diagram-loading-heading {
          font-size: 17.6px;
          font-weight: 600;
          line-height: 1.35;
          margin: 0 0 1rem;
        }
        .bending-diagram-loading-shell {
          display: flex;
          align-items: center;
          gap: .7rem;
          min-height: 58px;
          padding: .85rem 1rem;
          border: 1px solid #cbd5e1;
          border-left: 5px solid #98a2b3;
          border-radius: 10px;
          background: #fff;
          color: #475569;
        }
        .bending-diagram-loading-icon {
          font-size: 1rem;
          line-height: 1;
        }
        .bending-diagram-loading-copy {
          font-size: .92rem;
          font-weight: 600;
          line-height: 1.4;
        }
        section.stMain:has([data-bending-diagram-ready="GENERATION"])
        div[data-testid="stElementContainer"]:has(
          [data-bending-diagram-shell="GENERATION"]
        ) {
          display: none !important;
          height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
        }
        </style>
        <div class="bending-diagram-loading-region"
             data-testid="bending-diagram-loading-region"
             data-bending-diagram-shell="GENERATION"
             role="status" aria-live="polite">
          <div class="bending-diagram-loading-heading">Bending Diagrams</div>
          <div class="bending-diagram-loading-shell">
            <span class="bending-diagram-loading-icon" aria-hidden="true">&#9711;</span>
            <span class="bending-diagram-loading-copy">Preparing bending diagrams</span>
          </div>
        </div>
            """.replace("GENERATION", str(int(generation))),
            unsafe_allow_html=True,
        )


def render_bending_calculation_loading_shell(container) -> None:
    """Reserve the measured collapsed ULS calculation region while mounting."""

    with container:
        st.markdown(
            """
            <style>
            .bending-calculation-loading-region {
              box-sizing: border-box;
              height: 869.21875px;
              width: 100%;
              overflow: hidden;
              color: #10234a;
              padding-top: 28px;
            }
            .bending-calculation-loading-heading {
              font-size: 17.6px;
              font-weight: 600;
              line-height: 1.35;
              margin: 0 0 1.25rem;
            }
            .bending-calculation-loading-tabs {
              display: flex;
              gap: 1.25rem;
              height: 38px;
              align-items: center;
              border-bottom: 1px solid #d8dee8;
              margin-bottom: 1.35rem;
              font-size: .86rem;
            }
            .bending-calculation-loading-tabs span:first-child {
              color: #ff4b4b;
              align-self: stretch;
              display: flex;
              align-items: center;
              border-bottom: 2px solid #ff4b4b;
            }
            .bending-calculation-loading-card {
              box-sizing: border-box;
              height: 60px;
              margin-bottom: 1rem;
              border-radius: 10px;
              border-left: 4px solid #2b83ba;
              background: #eaf3fa;
              position: relative;
              overflow: hidden;
            }
            .bending-calculation-loading-card::after {
              content: "";
              position: absolute;
              inset: 0;
              background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255,255,255,.42) 50%,
                transparent 100%
              );
              transform: translateX(-100%);
              animation: bending-calc-shell-pulse 1.4s ease-in-out infinite;
            }
            @keyframes bending-calc-shell-pulse {
              to { transform: translateX(100%); }
            }
            section.stMain:has([data-testid="bending-calculation-ready"])
            div[data-testid="stElementContainer"]:has(
              [data-testid="bending-calculation-loading-region"]
            ) {
              display: none !important;
              height: 0 !important;
              min-height: 0 !important;
              margin: 0 !important;
              padding: 0 !important;
            }
            </style>
            <div class="bending-calculation-loading-region"
                 data-testid="bending-calculation-loading-region"
                 role="status" aria-live="polite">
              <div class="bending-calculation-loading-heading">Bending design checks</div>
              <div class="bending-calculation-loading-tabs">
                <span>ULS Checks</span>
                <span>SLS Checks</span>
                <span>Minimum strength checks</span>
              </div>
              <div class="bending-calculation-loading-card"></div>
              <div class="bending-calculation-loading-card"></div>
              <div class="bending-calculation-loading-card"></div>
              <div class="bending-calculation-loading-card"></div>
              <div class="bending-calculation-loading-card"></div>
              <div class="bending-calculation-loading-card"></div>
              <div class="bending-calculation-loading-card"></div>
              <div class="bending-calculation-loading-card"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_bending_state_panel(
    *,
    cached_layout: dict,
    mu_uls_active: float,
    diagram_shell_generation: int,
) -> None:
    """Render the state-owned diagrams and teaching panel as one fragment body.

    The ULS/SLS/Uncracked selector changes presentation state only. Keeping its
    dependent diagrams inside this boundary prevents a state change from
    rebuilding the summary, input cards, and every calculation card.
    """

    # Direct Bending navigation intentionally lets the heading, summary,
    # calculation cards and fixed diagram shell stream before the plotting
    # dependency warm-up is complete.  Synchronise only at the diagram
    # boundary so figure construction remains deterministic.
    from application.visualization_runtime_warmup import (
        start_visualization_runtime_warmup,
        wait_for_visualization_runtime_warmup,
    )
    from application.v2_runtime_warmup import start_v2_runtime_warmup

    start_v2_runtime_warmup()
    start_visualization_runtime_warmup()
    wait_for_visualization_runtime_warmup()

    state_options = ("ULS", "SLS (cracked)", "Uncracked")
    selected_state = st.session_state.get(
        "bending_state_main",
        st.session_state.get("bending_state", "ULS"),
    )
    if selected_state not in state_options:
        selected_state = "ULS"
    main_state = str(selected_state)
    st.session_state["bending_state"] = main_state

    stress_model = st.session_state.get("concrete_stress_model", "rectangular")
    moment_sign = st.session_state.get("bending_detail_view", "positive")

    def state_projection(option: str):
        if option == "ULS":
            state_label = (
                "uls – parabolic"
                if stress_model == "parabolic"
                else "uls – rectangular"
            )
            state_for_math = "ULS"
        elif option.startswith("SLS"):
            state_label = (
                "sls – parabolic"
                if stress_model == "parabolic"
                else "sls – linear"
            )
            state_for_math = "SLS"
        else:
            state_label = (
                "uncracked – parabolic"
                if stress_model == "parabolic"
                else "uncracked – linear"
            )
            state_for_math = "Uncracked"

        projected_state = _stress_strain_state(
            state_for_math,
            moment_sign=moment_sign,
        )
        if state_for_math == "SLS":
            dn_cracked = st.session_state.get("bending_sls_dn")
            if dn_cracked is not None:
                projected_state["sls"] = {
                    "dn_cracked": float(dn_cracked),
                    "dn": float(dn_cracked),
                    "eps_c_top": st.session_state.get("bending_sls_eps_top"),
                    "eps_s_layers": [],
                    "sig_s_layers": [],
                    "y_layers": [],
                }
        return state_label, projected_state

    render_timing_mark("bending_page.runtime.diagram.start")
    diagram_state_label, _ = state_projection(main_state)
    st.session_state["bending_strain_state_local"] = diagram_state_label

    render_timing_mark("bending_page.runtime.diagram.figure.start")
    _, projected_state = state_projection(main_state)
    fig_ss = _plot_stress_strain_profiles(
        projected_state,
        state_label=diagram_state_label,
        layout=cached_layout,
        moment_sign=moment_sign,
    )
    render_timing_mark("bending_page.runtime.diagram.figure.end")

    render_section_title("Bending Diagrams")
    section_tab, side_view_tab, moment_tab = render_stable_tabs(
        st,
        labels=("Section & stress-strain models", "Side view", "Bending moment"),
        scope_id="bending-section-diagrams",
        install_runtime=False,
    )
    with section_tab:
        render_timing_mark("bending_page.runtime.diagram.streamlit.start")
        render_plotly_diagram(
            fig_ss,
            key="bending_section_stress_strain",
            title="Section stress and strain",
            config={"displayModeBar": False},
        )
        render_timing_mark("bending_page.runtime.diagram.streamlit.end")
    with side_view_tab:
        from bending_side_view_diagram import render_bending_side_view_diagram

        render_bending_side_view_diagram(
            st.session_state,
            stress_strain_fig=fig_ss,
        )
    with moment_tab:
        import numpy as np

        mode = str(st.session_state.get("actions_mode", "manual") or "manual").strip().lower()
        length_m = max(float(get_param("L", 3000.0) or 3000.0) / 1000.0, 0.1)
        moment_x = list(st.session_state.get("moment_x") or [])
        moment_values = list(st.session_state.get("moment_values") or [])
        if not (
            mode == "design"
            and moment_x
            and moment_values
            and len(moment_x) == len(moment_values)
        ):
            moment_x = np.linspace(0.0, length_m, 100).tolist()
            x_norm = np.asarray(moment_x, dtype=float) / length_m
            support_type = str(
                get_param("support_type", "simply_supported") or "simply_supported"
            ).strip().lower()
            if "cantilever" in support_type:
                moment_values = (float(mu_uls_active or 0.0) * (1.0 - x_norm)).tolist()
            else:
                moment_values = (
                    4.0 * float(mu_uls_active or 0.0) * x_norm * (1.0 - x_norm)
                ).tolist()
        bmd_state = {
            "x_plot": moment_x,
            "M_plot": moment_values,
            "support_positions_plot": list(
                st.session_state.get("bmd_support_positions_m") or []
            ),
            "support_types_plot": list(st.session_state.get("bmd_support_types") or []),
            "L": float(moment_x[-1]),
            "preview_x_m": None,
            "design_x_m": None,
            "preview_M": None,
            "x_pad": max(float(moment_x[-1]) * 0.08, 0.12),
            "support_type": str(
                st.session_state.get("support_type") or "simply_supported"
            ).strip().lower(),
        }
        render_plotly_diagram(
            figure_bmd_from_state(bmd_state, show_m_peak=True),
            key="bending_moment_diagram",
            title="Bending moment diagram",
            config={"displayModeBar": False},
        )
    render_timing_mark("bending_page.runtime.diagram.end")

    st.markdown("**State:**")
    st.radio(
        "State:",
        state_options,
        key="bending_state_main",
        horizontal=True,
        index=state_options.index(main_state),
        label_visibility="collapsed",
    )
    preserve_scroll_for_preceding_widget(
        st,
        scope_id="bending-state-selector",
    )
    st.session_state["bending_state"] = st.session_state.get(
        "bending_state_main", main_state
    )
    render_lazy_expander(
        "ℹ️ From strain to stress to internal force",
        lambda: None,
        key="bending_material_model_expander",
    )
    st.markdown(
        '<span data-testid="bending-diagram-ready" '
        f'data-bending-diagram-ready="{int(diagram_shell_generation)}" '
        'aria-hidden="true" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    # Prepare inactive projections in the bounded session-local cache without
    # mounting or transmitting additional charts.
    render_timing_mark("bending_page.runtime.diagram.preload.start")
    for option in state_options:
        if option == main_state:
            continue
        option_label, option_state = state_projection(option)
        _plot_stress_strain_profiles(
            option_state,
            state_label=option_label,
            layout=cached_layout,
            moment_sign=moment_sign,
        )
    render_timing_mark("bending_page.runtime.diagram.preload.end")
    render_timing_mark("bending_page.runtime.material_model.end")


def _coalesce_num(v, default: float) -> float:
    """Return default only if v is None (preserves 0)."""
    return default if v is None else float(v)


def _get_build_beam_3d_figure_pure():
    """Get the cached or uncached version of _build_beam_3d_figure_pure based on debug mode."""
    try:
        from src.debug.cache_control import cache_enabled
        if cache_enabled():
            # Caching enabled: use cache
            return st.cache_resource(show_spinner=False)(_build_beam_3d_figure_pure_impl)
        else:
            # Cache bypass enabled: return unwrapped function
            return _build_beam_3d_figure_pure_impl
    except ImportError:
        # Debug module not available: use cache
        return st.cache_resource(show_spinner=False)(_build_beam_3d_figure_pure_impl)


def _build_beam_3d_figure_pure_impl(
    b,
    D,
    L,
    Mu_star,
    phi_Mu_cap,
    c,
    strain_state,
    reo_layout,
    cover_bot,
    cover_top,
    cover_side,
    rowgap_bot,
    rowgap_top,
    lig_d,
    lig_legs,
    s_lig,
    debug_bust=None,
):
    """Compatibility wrapper for the shared 3D bending diagram builder."""
    return _shared_build_beam_3d_figure_pure(
        b,
        D,
        L,
        Mu_star,
        phi_Mu_cap,
        c,
        strain_state,
        reo_layout,
        cover_bot,
        cover_top,
        cover_side,
        rowgap_bot,
        rowgap_top,
        lig_d,
        lig_legs,
        s_lig,
        debug_bust=debug_bust,
    )


def _build_beam_3d_figure(b, D, L, Mu_star, phi_Mu_cap, c, strain_state: str = "ULS", layout=None):
    """
    Wrapper function that reads from session state and calls the cached pure function.

    Args:
        layout: Optional pre-computed section layout dict. If None, will compute from session state.
    """
    # Get all inputs from results (matches shear pattern)
    results = st.session_state.get("results", {})

    # --- ARCHITECTURE LOCK: bending diagrams must use results (with fallback to shared) ---
    # Note: Geometry values (b, D, d) are not in results - they're in shared state.
    # The guard ensures results dict exists and diagrams use the fallback pattern correctly.
    if st.session_state.get("_dev_mode", False):
        if "results" not in st.session_state:
            raise RuntimeError(
                "[ARCHITECTURE VIOLATION] Bending diagrams require results dict to exist. "
                "Call update_results() or run compute functions first."
            )

    # If layout is provided, extract reo_layout from it
    if layout is not None:
        reo_layout = layout.get("reo_layout")
        if reo_layout is None:
            # Fallback to computing from session state using results
            from section_layout import compute_longitudinal_reo_layout
            reo_layout = compute_longitudinal_reo_layout(
                b=results.get("b", b), D=results.get("D", D),
                cover_bot=results.get("cover_bot", 40.0), cover_top=results.get("cover_top", 40.0), cover_side=results.get("cover_side", 40.0),
                nb_or_s_bot_1=results.get("nb_or_s_bot_1", 4.0), db_bot_1=results.get("db_bot_1", 20.0),
                nb_or_s_bot_2=results.get("nb_or_s_bot_2", 0.0), db_bot_2=results.get("db_bot_2", 20.0),
                nb_or_s_top_1=results.get("nb_or_s_top_1", 2.0), db_top_1=results.get("db_top_1", 16.0),
                nb_or_s_top_2=results.get("nb_or_s_top_2", 0.0), db_top_2=results.get("db_top_2", 16.0),
                rowgap_bot=results.get("rowgap_bot", 60.0), rowgap_top=results.get("rowgap_top", 60.0),
            )
    else:
        # Compute from session state using results
        from section_layout import compute_longitudinal_reo_layout
        reo_layout = compute_longitudinal_reo_layout(
            b=results.get("b", b), D=results.get("D", D),
            cover_bot=results.get("cover_bot", 40.0), cover_top=results.get("cover_top", 40.0), cover_side=results.get("cover_side", 40.0),
            nb_or_s_bot_1=results.get("nb_or_s_bot_1", 4.0), db_bot_1=results.get("db_bot_1", 20.0),
            nb_or_s_bot_2=results.get("nb_or_s_bot_2", 0.0), db_bot_2=results.get("db_bot_2", 20.0),
            nb_or_s_top_1=results.get("nb_or_s_top_1", 2.0), db_top_1=results.get("db_top_1", 16.0),
            nb_or_s_top_2=results.get("nb_or_s_top_2", 0.0), db_top_2=results.get("db_top_2", 16.0),
            rowgap_bot=results.get("rowgap_bot", 60.0), rowgap_top=results.get("rowgap_top", 60.0),
        )

    # Get ligature spacing from results
    s_lig = results.get("s_lig", get_param("s_lig", 200.0))
    s_lig = float(s_lig) if s_lig is not None else 200.0

    # Cache-busting for debug mode
    debug_bust = None
    try:
        from src.debug.debug_flags import is_debug_enabled
        import hashlib
        import json
        if is_debug_enabled():
            # Create a signature from all dimension inputs
            dim_sig = {
                "b": results.get("b", b),
                "D": results.get("D", D),
                "L": results.get("L", L),
                "d": results.get("d", get_param("d", 560.0)),
                "cover_bot": results.get("cover_bot", 40.0),
                "cover_top": results.get("cover_top", 40.0),
                "cover_side": results.get("cover_side", 40.0),
            }
            debug_bust = hashlib.sha1(json.dumps(dim_sig, sort_keys=True).encode()).hexdigest()[:8]
    except ImportError:
        pass

    # Get cached or uncached version based on debug mode
    _build_fn = _get_build_beam_3d_figure_pure()
    return _build_fn(
        b, D, L, Mu_star, phi_Mu_cap, c, strain_state,
        reo_layout, results.get("cover_bot", 40.0), results.get("cover_top", 40.0),
        results.get("cover_side", 40.0), results.get("rowgap_bot", 60.0), results.get("rowgap_top", 60.0),
        results.get("lig_d", 10.0), results.get("lig_legs", 2), s_lig, debug_bust=debug_bust
    )
