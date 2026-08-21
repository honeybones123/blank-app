"""Bending diagram section helpers."""

from __future__ import annotations

def bind_runtime(namespace: dict) -> None:
    globals().update({key: value for key, value in namespace.items() if not key.startswith("__")})


def _bending_state_label(option: str, *, stress_model: str) -> str:
    """Return the presentation label without constructing engineering state."""
    if option == "ULS":
        return (
            "uls – parabolic"
            if stress_model == "parabolic"
            else "uls – rectangular"
        )
    if option.startswith("SLS"):
        return (
            "sls – parabolic"
            if stress_model == "parabolic"
            else "sls – linear"
        )
    return (
        "uncracked – parabolic"
        if stress_model == "parabolic"
        else "uncracked – linear"
    )


def _build_bending_state_projection(
    option: str,
    *,
    stress_model: str,
    moment_sign: str,
):
    """Return the exact state label and projection used by every diagram stage."""
    state_label = _bending_state_label(option, stress_model=stress_model)
    if option == "ULS":
        state_for_math = "ULS"
    elif option.startswith("SLS"):
        state_for_math = "SLS"
    else:
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


def render_bending_diagram_loading_shell(container, *, generation: int) -> None:
    """Reserve only the active plot canvas while its live figure is prepared.

    The Bending heading, native diagram tabs, State selector and material
    lesson are real lightweight controls and remain outside this shell.  The
    shell therefore owns exactly the same 320 px canvas as the live Plotly
    figure instead of approximating the depth of several unrelated sections.
    """

    with container:
        st.markdown(
            """
        <style>
        .st-key-bending_primary_plot_frame {
          display: grid !important;
          grid-template-columns: minmax(0, 1fr) !important;
          width: 100%;
          min-height: var(--sb-bending-diagram-plot-height, 320px);
        }
        .st-key-bending_primary_plot_frame
        > div[data-testid="stLayoutWrapper"] {
          grid-area: 1 / 1 !important;
          width: 100%;
          min-width: 0 !important;
          max-width: 100% !important;
        }
        .st-key-bending_diagram_shell {
          z-index: 2;
          height: var(--sb-bending-diagram-plot-height, 320px);
        }
        .st-key-bending_diagram_live {
          z-index: 1;
          min-height: var(--sb-bending-diagram-plot-height, 320px);
        }
        .st-key-bending_diagram_live
        > div[data-testid="stElementContainer"] {
          margin-bottom: 0 !important;
        }
        .bending-diagram-loading-region {
          box-sizing: border-box;
          height: var(--sb-bending-diagram-plot-height, 320px);
          width: 100%;
          overflow: hidden;
          background: #fff;
          color: #10234a;
          pointer-events: none;
        }
        .bending-diagram-loading-shell {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: .7rem;
          height: 100%;
          padding: .85rem 1rem;
          border: 1px solid #cbd5e1;
          border-radius: 10px;
          background: #f8fafc;
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
        html:has(
          .st-key-bending_diagram_live .js-plotly-plot .scatterlayer .trace
        ):has(
          .st-key-bending_diagram_live .js-plotly-plot g.shapelayer .shape-group
        ):has(
          .st-key-bending_diagram_live .js-plotly-plot .annotation
        )
        .st-key-bending_primary_plot_frame
        > div[data-testid="stLayoutWrapper"]:has(
          > .st-key-bending_diagram_shell
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
             data-bending-diagram-geometry-token="--sb-bending-diagram-plot-height"
             role="status" aria-live="polite">
          <div class="bending-diagram-loading-shell">
            <span class="bending-diagram-loading-icon" aria-hidden="true">&#9711;</span>
            <span class="bending-diagram-loading-copy">Preparing section stress and strain</span>
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
    """Publish the lightweight diagram panel before mounting any Plotly host.

    The first fragment pass emits the real heading, tabs, state selector and
    material-lesson header around a passive plot-sized shell.  A browser paint
    handshake then requests a fragment-only rerun which mounts the currently
    selected state.  Inactive states and inactive diagram tabs are never
    mounted on the cold critical path.
    """

    generation = int(diagram_shell_generation)
    if int(st.session_state.get("_bending_diagram_stage_generation", -1)) != generation:
        st.session_state["_bending_diagram_stage_generation"] = generation
        st.session_state["_bending_diagram_render_stage"] = "lightweight"
        st.session_state["_bending_side_view_published"] = False
        st.session_state["_bending_moment_view_published"] = False

    primary_clicked = st.button(
        "Load primary bending diagram",
        key="bending_deferred_primary_button",
    )
    side_clicked = st.button(
        "Load bending side view",
        key="bending_deferred_side_button",
    )
    moment_clicked = st.button(
        "Load bending moment diagram",
        key="bending_deferred_moment_button",
    )
    if primary_clicked or side_clicked or moment_clicked:
        st.session_state["_bending_diagram_render_stage"] = "primary"
    if side_clicked:
        st.session_state["_bending_side_view_published"] = True
    if moment_clicked:
        st.session_state["_bending_moment_view_published"] = True

    primary_published = (
        st.session_state.get("_bending_diagram_render_stage") == "primary"
    )
    side_published = bool(st.session_state.get("_bending_side_view_published", False))
    moment_published = bool(st.session_state.get("_bending_moment_view_published", False))

    # Direct Bending navigation intentionally lets the heading, summary,
    # calculation cards and fixed diagram shell stream before the plotting
    # dependency warm-up is complete.  Synchronise only at the diagram
    # boundary so figure construction remains deterministic.
    from application.visualization_runtime_warmup import (
        start_visualization_runtime_warmup,
        wait_for_visualization_runtime_warmup,
    )
    from application.v2_runtime_warmup import start_v2_runtime_warmup

    if primary_published:
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

    diagram_state_label = _bending_state_label(
        main_state,
        stress_model=stress_model,
    )
    st.session_state["bending_strain_state_local"] = diagram_state_label

    selected_fig_ss = None
    if primary_published:
        render_timing_mark("bending_page.runtime.diagram.start")
        render_timing_mark("bending_page.runtime.diagram.figure.start")
        _, projected_state = _build_bending_state_projection(
            main_state,
            stress_model=stress_model,
            moment_sign=moment_sign,
        )
        selected_fig_ss = _plot_stress_strain_profiles(
            projected_state,
            state_label=diagram_state_label,
            layout=cached_layout,
            moment_sign=moment_sign,
        )
        render_timing_mark("bending_page.runtime.diagram.figure.end")

    # The deferred summary browser binding used to contribute one zero-height
    # Streamlit stack slot before this section. Recreate that exact final-page
    # geometry here, after the visible loading shells have already streamed.
    st.markdown(
        '<div data-bending-diagrams-layout-slot data-bending-diagram-region-start '
        'data-bending-diagram-geometry-token="--sb-bending-diagram-plot-height" '
        'aria-hidden="true" '
        'style="height:0;line-height:0">&#8203;</div>',
        unsafe_allow_html=True,
    )
    render_section_title("Bending Diagrams")
    section_tab, side_view_tab, moment_tab = render_stable_tabs(
        st,
        labels=("Section & stress-strain models", "Side view", "Bending moment"),
        scope_id="bending-section-diagrams",
        install_runtime=False,
    )
    with section_tab:
        with st.container(key="bending_primary_plot_frame"):
            diagram_shell_container = st.container(key="bending_diagram_shell")
            render_bending_diagram_loading_shell(
                diagram_shell_container,
                generation=generation,
            )
            with st.container(key="bending_diagram_live"):
                if primary_published and selected_fig_ss is not None:
                    render_timing_mark("bending_page.runtime.diagram.streamlit.start")
                    state_key = {
                        "ULS": "uls",
                        "SLS (cracked)": "sls_cracked",
                        "Uncracked": "uncracked",
                    }[main_state]
                    st.plotly_chart(
                        selected_fig_ss,
                        key=f"bending_section_stress_strain_{state_key}_chart",
                        width="stretch",
                        config={"displayModeBar": False},
                    )
                    render_timing_mark("bending_page.runtime.diagram.streamlit.end")
                else:
                    st.markdown(
                        '<span data-bending-primary-plot-deferred="1" '
                        'aria-hidden="true" style="display:none"></span>',
                        unsafe_allow_html=True,
                    )
    with side_view_tab:
        if side_published:
            from bending_side_view_diagram import render_bending_side_view_diagram

            render_bending_side_view_diagram(
                st.session_state,
                stress_strain_fig=selected_fig_ss,
            )
        else:
            st.markdown(
                '<div data-bending-side-view-deferred="1" '
                'style="height:320px" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
    with moment_tab:
        if moment_published:
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
        else:
            st.markdown(
                '<div data-bending-moment-deferred="1" '
                'style="height:320px" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
    if primary_published:
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
    st.session_state["bending_state"] = st.session_state.get(
        "bending_state_main", main_state
    )

    def render_material_teaching_lesson() -> None:
        from engineering_page_sections.bending_material_teaching import (
            render_bending_material_teaching_panel,
        )

        selected_material_state = str(
            st.session_state.get(
                "bending_state_main",
                st.session_state.get("bending_state", "ULS"),
            )
            or "ULS"
        )
        render_bending_material_teaching_panel(
            selected_state=selected_material_state,
            plot_material_curves=_plot_material_stress_strain_curves,
            render_plotly_diagram=render_plotly_diagram,
        )

    render_lazy_expander(
        "ℹ️ From strain to stress to internal force",
        render_material_teaching_lesson,
        key="bending_material_model_expander",
    )
    st.markdown(
        '<span data-bending-diagram-region-end aria-hidden="true" '
        'style="height:0;line-height:0"></span>'
        '<span data-bending-lightweight-ready="'
        f'{generation}" aria-hidden="true" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    if primary_published:
        st.markdown(
            '<span data-testid="bending-diagram-ready" '
            f'data-bending-diagram-ready="{generation}" '
            f'data-bending-selected-state="{main_state}" '
            'aria-hidden="true" style="display:none"></span>',
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <style>
        .st-key-bending_deferred_primary_button,
        .st-key-bending_deferred_side_button,
        .st-key-bending_deferred_moment_button {
          display: none !important;
          height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
        (() => {{
          const doc = window.parent.document;
          const generation = {generation};
          const runtimeKey = '__sbBendingDeferredDiagramRuntime';
          const prior = window.parent[runtimeKey];
          if (prior && prior.cleanup) prior.cleanup();

          const button = (key) => doc.querySelector(`.st-key-${{key}} button`);
          const clickOnce = (key) => {{
            const target = button(key);
            if (!target || target.disabled) return false;
            target.click();
            return true;
          }};
          let cancelled = false;
          let timer = 0;
          const requestPrimaryAfterPaint = () => {{
            if (cancelled) return;
            const light = doc.querySelector(
              `[data-bending-lightweight-ready="${{generation}}"]`
            );
            const cards = doc.querySelector('[data-testid="bending-calculation-ready"]');
            const live = doc.querySelector(
              `[data-bending-diagram-ready="${{generation}}"]`
            );
            if (live) return;
            if (!light || !cards) {{
              timer = window.setTimeout(requestPrimaryAfterPaint, 25);
              return;
            }}
            window.requestAnimationFrame(() => window.requestAnimationFrame(() => {{
              if (cancelled) return;
              doc.documentElement.setAttribute(
                'data-sb-bending-lightweight-painted', String(generation)
              );
              // Leave a short, measurable interaction window after the first
              // complete lightweight paint.  This is not a loading delay: it
              // proves the browser can accept scroll input before Plotly work
              // begins and keeps the cold-load boundary regression-testable.
              timer = window.setTimeout(
                () => clickOnce('bending_deferred_primary_button'), 150
              );
            }}));
          }};

          const onPointerDown = (event) => {{
            const tab = event.target && event.target.closest
              ? event.target.closest('[role="tab"]')
              : null;
            if (!tab) return;
            const tabset = tab.closest('[data-testid="stTabs"]');
            if (!tabset || tabset.dataset.sbTabScope !== 'bending-section-diagrams') return;
            const label = (tab.textContent || '').trim();
            if (label === 'Side view') {{
              window.setTimeout(
                () => clickOnce('bending_deferred_side_button'), 0
              );
            }} else if (label === 'Bending moment') {{
              window.setTimeout(
                () => clickOnce('bending_deferred_moment_button'), 0
              );
            }}
          }};
          doc.addEventListener('pointerdown', onPointerDown, true);
          requestPrimaryAfterPaint();
          window.parent[runtimeKey] = {{
            cleanup: () => {{
              cancelled = true;
              if (timer) window.clearTimeout(timer);
              doc.removeEventListener('pointerdown', onPointerDown, true);
            }}
          }};
        }})();
        </script>
        """,
        height=0,
    )
    render_timing_mark("bending_page.runtime.material_model.end")


def render_bending_secondary_state_cache(
    *,
    cached_layout: dict,
    diagram_shell_generation: int,
) -> None:
    """Prepare inactive state figures after the primary chart is painted.

    This fragment mounts no Plotly host.  It only fills the existing bounded
    Python figure cache during browser idle time, so SLS and Uncracked do not
    compete with cold-page scrolling or the initial ULS paint.
    """

    generation = int(diagram_shell_generation)
    prepare_clicked = st.button(
        "Prepare remaining bending states",
        key="bending_prepare_secondary_button",
    )
    ready = (
        int(
            st.session_state.get(
                "_bending_secondary_diagrams_ready_generation", -1
            )
        )
        == generation
    )
    if prepare_clicked and not ready:
        selected = str(st.session_state.get("bending_state_main", "ULS") or "ULS")
        stress_model = st.session_state.get("concrete_stress_model", "rectangular")
        moment_sign = st.session_state.get("bending_detail_view", "positive")
        for option in ("ULS", "SLS (cracked)", "Uncracked"):
            if option == selected:
                continue
            state_label, projected = _build_bending_state_projection(
                option,
                stress_model=stress_model,
                moment_sign=moment_sign,
            )
            _plot_stress_strain_profiles(
                projected,
                state_label=state_label,
                layout=cached_layout,
                moment_sign=moment_sign,
            )
        st.session_state["_bending_secondary_diagrams_ready_generation"] = generation
        ready = True

    st.markdown(
        """
        <style>
        .st-key-bending_prepare_secondary_button {
          display: none !important;
          height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if ready:
        st.markdown(
            '<span data-bending-secondary-diagrams-ready="'
            f'{generation}" aria-hidden="true" style="display:none"></span>',
            unsafe_allow_html=True,
        )
        return

    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
        (() => {{
          const doc = window.parent.document;
          const generation = {generation};
          const start = () => {{
            const plot = doc.querySelector(
              '.st-key-bending_diagram_live .js-plotly-plot'
            );
            const complete = Boolean(
              plot
              && plot.querySelector('.scatterlayer .trace')
              && plot.querySelector('g.shapelayer .shape-group')
              && plot.querySelector('.annotation')
            );
            if (!complete) {{
              window.setTimeout(start, 50);
              return;
            }}
            const run = () => {{
              const button = doc.querySelector(
                '.st-key-bending_prepare_secondary_button button'
              );
              if (button && !button.disabled) button.click();
            }};
            if ('requestIdleCallback' in window.parent) {{
              window.parent.requestIdleCallback(run, {{timeout: 750}});
            }} else {{
              window.setTimeout(run, 250);
            }}
          }};
          start();
        }})();
        </script>
        """,
        height=0,
    )


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
