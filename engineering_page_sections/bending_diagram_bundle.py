"""One-phase, presentation-only Bending diagram bundle renderer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


STATE_OPTIONS = ("ULS", "SLS (cracked)", "Uncracked")
STATE_KEYS = {
    "ULS": "uls",
    "SLS (cracked)": "sls_cracked",
    "Uncracked": "uncracked",
}


@dataclass(frozen=True)
class BendingDiagramRuntime:
    """Explicit presentation dependencies for the Bending diagram fragment."""

    st: Any
    get_param: Callable[..., Any]
    render_timing_mark: Callable[[str], None]
    plot_stress_strain_profiles: Callable[..., Any]
    plot_material_stress_strain_curves: Callable[..., Any]
    figure_bmd_from_state: Callable[..., Any]
    render_plotly_diagram: Callable[..., Any]
    render_section_title: Callable[..., Any]
    render_stable_tabs: Callable[..., Any]
    render_lazy_expander: Callable[..., Any]


def _build_bending_moment_state(
    runtime: BendingDiagramRuntime,
    *,
    mu_uls_active: float,
) -> dict:
    """Return the existing BMD presentation inputs without changing authority."""

    import numpy as np

    st = runtime.st
    get_param = runtime.get_param
    mode = str(
        st.session_state.get("actions_mode", "manual") or "manual"
    ).strip().lower()
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
            moment_values = (
                float(mu_uls_active or 0.0) * (1.0 - x_norm)
            ).tolist()
        else:
            moment_values = (
                4.0 * float(mu_uls_active or 0.0) * x_norm * (1.0 - x_norm)
            ).tolist()
    return {
        "x_plot": moment_x,
        "M_plot": moment_values,
        "support_positions_plot": list(
            st.session_state.get("bmd_support_positions_m") or []
        ),
        "support_types_plot": list(
            st.session_state.get("bmd_support_types") or []
        ),
        "L": float(moment_x[-1]),
        "preview_x_m": None,
        "design_x_m": None,
        "preview_M": None,
        "x_pad": max(float(moment_x[-1]) * 0.08, 0.12),
        "support_type": str(
            st.session_state.get("support_type")
            or get_param("support_type", "simply_supported")
            or "simply_supported"
        ).strip().lower(),
    }


def _side_view_identity_payload(
    runtime: BendingDiagramRuntime,
    *,
    section_fingerprint: str,
    state_option: str,
    projected_state: dict,
) -> dict:
    """Project the canonical inputs consumed by the live side-view builder.

    Do not include the application-wide ``results`` mapping here.  Other
    calculation pages legitimately publish into that mapping and must not
    invalidate an unchanged Bending presentation bundle.
    """

    st = runtime.st
    get_param = runtime.get_param

    from shear_visuals import _beam_model
    from ui.diagrams.crack_side_view_diagram import (
        _resolve_crack_diagram_window,
        _support_resolution,
        _total_structural_length_m,
    )

    model = _beam_model()
    window = _resolve_crack_diagram_window(projected_state)
    support = _support_resolution(projected_state)
    state_names = (
        "actions_mode",
        "bending_detail_view",
        "bending_side_view_show_strain",
        "bending_side_view_show_stress",
        "design_actions_source",
        "design_section_committed",
        "design_section_x_m",
        "section_cursor_x_m",
        "sfd_beam_system_mode",
        "design_beam_system_mode",
        "sfd_span_count",
        "defl_support_type",
    )
    parameter_names = (
        "crack_bmd_cache_fingerprint",
        "delta_total",
        "deflection_total_mm",
        "moment_x",
        "moment_values",
        "shear_x",
        "shear_M_uls_kNm",
        "shear_M_sls_kNm",
        "bending_sls_dn_mm",
        "bending_uls_c_pos_mm",
        "bending_uls_gamma_pos",
    )
    return {
        "state": state_option,
        "section_fingerprint": section_fingerprint,
        "projected_state": projected_state,
        "model": model,
        "window": window,
        "support": support,
        "total_structural_length_m": _total_structural_length_m(),
        "parameters": {
            name: get_param(name, None)
            for name in parameter_names
        },
        "side_state": {
            name: st.session_state.get(name)
            for name in state_names
        },
    }


def _prepare_identity(
    runtime: BendingDiagramRuntime,
    *,
    cached_layout: dict,
    mu_uls_active: float,
) -> dict:
    """Resolve authoritative state and deterministic presentation fingerprints."""

    st = runtime.st

    from engineering_page_sections.bending_diagram_bundle_cache import (
        bending_diagram_bundle_fingerprint,
        bending_moment_fingerprint,
        section_stress_strain_fingerprint,
        side_view_fingerprint,
    )
    from engineering_page_sections.bending_diagrams import (
        _build_bending_state_projection,
    )
    from ui.design_tokens import BENDING_STRESS_STRAIN_LAYOUT_VERSION
    from inputs_application.active_beam_engineering_state import (
        resolve_active_beam_engineering_state,
    )
    from inputs_application.authoritative_check_packs import (
        current_authoritative_family,
    )

    active_inputs = resolve_active_beam_engineering_state(st.session_state)
    input_values = dict(active_inputs.values)
    authoritative_bending = current_authoritative_family(
        st.session_state, "bending"
    )

    stress_model = str(
        st.session_state.get("concrete_stress_model", "rectangular")
        or "rectangular"
    )
    moment_sign = str(
        st.session_state.get("bending_detail_view", "positive") or "positive"
    )
    projections = {}
    section_fingerprints = {}
    side_fingerprints = {}
    for option in STATE_OPTIONS:
        state_label, projected_state = _build_bending_state_projection(
            option,
            stress_model=stress_model,
            moment_sign=moment_sign,
            input_state=input_values,
            authoritative_bending=authoritative_bending,
        )
        projections[option] = {
            "state_label": state_label,
            "projected_state": projected_state,
        }
        section_fingerprints[option] = section_stress_strain_fingerprint(
            {
                "layout_contract": BENDING_STRESS_STRAIN_LAYOUT_VERSION,
                "state": option,
                "state_label": state_label,
                "projection": projected_state,
                "layout": cached_layout,
                "moment_sign": moment_sign,
                "beam_revision": active_inputs.revision,
                "engineering_hash": active_inputs.engineering_hash,
                "authority_hash": active_inputs.authority_hash,
                "material": {
                    "fc": input_values.get("fc"),
                    "Ec": input_values.get("Ec"),
                    "fsy": input_values.get("fsy"),
                    "Es": input_values.get("Es"),
                    "stress_model": stress_model,
                },
            }
        )
        side_fingerprints[option] = side_view_fingerprint(
            _side_view_identity_payload(
                runtime,
                section_fingerprint=section_fingerprints[option],
                state_option=option,
                projected_state=projected_state,
            )
        )

    bmd_state = _build_bending_moment_state(
        runtime,
        mu_uls_active=mu_uls_active,
    )
    moment_fingerprint = bending_moment_fingerprint(bmd_state)
    bundle_fingerprint = bending_diagram_bundle_fingerprint(
        section_fingerprints=section_fingerprints,
        side_fingerprints=side_fingerprints,
        moment_fingerprint=moment_fingerprint,
    )
    return {
        "fingerprint": bundle_fingerprint,
        "cached_layout": cached_layout,
        "moment_sign": moment_sign,
        "projections": projections,
        "section_fingerprints": section_fingerprints,
        "side_fingerprints": side_fingerprints,
        "moment_fingerprint": moment_fingerprint,
        "bmd_state": bmd_state,
        "active_inputs": active_inputs,
    }


def _stabilise_figure(fig, *, kind: str, fingerprint: str):
    """Give cached figures deterministic identity and the shared canvas depth."""

    from ui.design_tokens import BENDING_DIAGRAM_PLOT_HEIGHT_PX

    for index, trace in enumerate(getattr(fig, "data", ()) or ()):
        try:
            trace.uid = f"bending-{kind}-{fingerprint[:12]}-{index}"
        except (AttributeError, TypeError, ValueError):
            pass
    fig.update_layout(
        height=int(BENDING_DIAGRAM_PLOT_HEIGHT_PX),
        uirevision=f"bending-{kind}-{fingerprint}",
    )
    return fig


def _figure_from_json(figure_json: str | None):
    if not figure_json:
        return None
    import plotly.io as pio

    return pio.from_json(figure_json)


def _load_cached_bundle(
    runtime: BendingDiagramRuntime,
    identity: dict,
    manifest: dict,
):
    """Load a validated bundle manifest into independent Plotly figures."""

    st = runtime.st

    from engineering_page_sections.bending_diagram_bundle_cache import (
        get_figure_json,
    )

    section_figures = {}
    side_figures = {}
    for option in STATE_OPTIONS:
        section_figures[option] = _figure_from_json(
            get_figure_json(
                st.session_state,
                kind="section",
                fingerprint=str(manifest["section"][option]),
            )
        )
        side_figures[option] = _figure_from_json(
            get_figure_json(
                st.session_state,
                kind="side",
                fingerprint=str(manifest["side"][option]),
            )
        )
    moment_figure = _figure_from_json(
        get_figure_json(
            st.session_state,
            kind="moment",
            fingerprint=str(manifest["moment"]),
        )
    )
    if (
        any(figure is None for figure in section_figures.values())
        or any(figure is None for figure in side_figures.values())
        or moment_figure is None
    ):
        return None
    return {
        "section": section_figures,
        "side": side_figures,
        "moment": moment_figure,
        "fingerprint": identity["fingerprint"],
    }


def _build_or_load_bundle(runtime: BendingDiagramRuntime, identity: dict):
    """Build missing pure presentation figures and store a bounded JSON bundle."""

    st = runtime.st
    render_timing_mark = runtime.render_timing_mark

    from bending_side_view_diagram import build_bending_side_view_figure
    from engineering_page_sections.bending_diagram_bundle_cache import (
        bundle_manifest,
        get_figure_json,
        put_bundle_manifest,
        put_figure_json,
    )

    render_timing_mark("bending.diagram.bundle.build.start")
    section_figures = {}
    for option in STATE_OPTIONS:
        fingerprint = identity["section_fingerprints"][option]
        figure = _figure_from_json(
            get_figure_json(
                st.session_state,
                kind="section",
                fingerprint=fingerprint,
            )
        )
        if figure is None:
            projection = identity["projections"][option]
            figure = runtime.plot_stress_strain_profiles(
                projection["projected_state"],
                state_label=projection["state_label"],
                layout=identity["cached_layout"],
                moment_sign=identity["moment_sign"],
            )
            figure = _stabilise_figure(
                figure,
                kind=f"section-{STATE_KEYS[option]}",
                fingerprint=fingerprint,
            )
            put_figure_json(
                st.session_state,
                kind="section",
                fingerprint=fingerprint,
                figure_json=figure.to_json(),
            )
        section_figures[option] = figure

    show_strain = bool(
        st.session_state.get("bending_side_view_show_strain", False)
    )
    show_stress = bool(
        st.session_state.get("bending_side_view_show_stress", False)
    )
    side_figures = {}
    for option in STATE_OPTIONS:
        fingerprint = identity["side_fingerprints"][option]
        figure = _figure_from_json(
            get_figure_json(
                st.session_state,
                kind="side",
                fingerprint=fingerprint,
            )
        )
        if figure is None:
            figure, _meta = build_bending_side_view_figure(
                st.session_state,
                stress_strain_fig=section_figures[option],
                show_strain_diagram=show_strain,
                show_stress_diagram=show_stress,
            )
            figure = _stabilise_figure(
                figure,
                kind=f"side-{STATE_KEYS[option]}",
                fingerprint=fingerprint,
            )
            put_figure_json(
                st.session_state,
                kind="side",
                fingerprint=fingerprint,
                figure_json=figure.to_json(),
            )
        side_figures[option] = figure

    moment_fingerprint = identity["moment_fingerprint"]
    moment_figure = _figure_from_json(
        get_figure_json(
            st.session_state,
            kind="moment",
            fingerprint=moment_fingerprint,
        )
    )
    if moment_figure is None:
        moment_figure = runtime.figure_bmd_from_state(
            identity["bmd_state"],
            show_m_peak=True,
        )
        moment_figure = _stabilise_figure(
            moment_figure,
            kind="moment",
            fingerprint=moment_fingerprint,
        )
        put_figure_json(
            st.session_state,
            kind="moment",
            fingerprint=moment_fingerprint,
            figure_json=moment_figure.to_json(),
        )

    manifest = bundle_manifest(
        section_fingerprints=identity["section_fingerprints"],
        side_fingerprints=identity["side_fingerprints"],
        moment_fingerprint=moment_fingerprint,
    )
    put_bundle_manifest(
        st.session_state,
        fingerprint=identity["fingerprint"],
        manifest=manifest,
    )
    render_timing_mark("bending.diagram.bundle.build.end")
    return {
        "section": section_figures,
        "side": side_figures,
        "moment": moment_figure,
        "fingerprint": identity["fingerprint"],
    }


def _render_material_teaching_lesson(runtime: BendingDiagramRuntime) -> None:
    from engineering_page_sections.bending_material_teaching import (
        render_bending_material_teaching_panel,
    )

    st = runtime.st
    selected_state = str(
        st.session_state.get(
            "bending_state_main",
            st.session_state.get("bending_state", "ULS"),
        )
        or "ULS"
    )
    render_bending_material_teaching_panel(
        selected_state=selected_state,
        plot_material_curves=runtime.plot_material_stress_strain_curves,
        render_plotly_diagram=runtime.render_plotly_diagram,
    )


def render_bending_state_controls(*, runtime: BendingDiagramRuntime) -> None:
    """Render state controls owned by the diagram-bundle fragment.

    A selection reruns only the diagram fragment and mounts the matching
    already-prepared figure.  No engineering calculation or full-page rerun is
    involved, and no browser mutation of Plotly-generated DOM is required.
    """

    st = runtime.st
    initial_state = str(
        st.session_state.get("_bending_diagram_initial_state", "ULS") or "ULS"
    )
    if initial_state not in STATE_OPTIONS:
        initial_state = "ULS"
    st.markdown("**State:**")
    st.radio(
        "State:",
        STATE_OPTIONS,
        key="bending_state_main",
        horizontal=True,
        index=STATE_OPTIONS.index(initial_state),
        label_visibility="collapsed",
    )
    selected_state = str(
        st.session_state.get("bending_state_main", initial_state) or initial_state
    )
    if selected_state not in STATE_OPTIONS:
        selected_state = "ULS"
    st.session_state["bending_state"] = selected_state
    state_labels = dict(
        st.session_state.get("_bending_diagram_state_labels", {}) or {}
    )
    st.session_state["bending_strain_state_local"] = str(
        state_labels.get(selected_state) or selected_state
    )
    runtime.render_lazy_expander(
        "\u2139\ufe0f From strain to stress to internal force",
        lambda: _render_material_teaching_lesson(runtime),
        key="bending_material_model_expander",
    )


def render_bending_diagram_bundle_panel(
    *,
    runtime: BendingDiagramRuntime,
    cached_layout: dict,
    mu_uls_active: float,
    diagram_shell_generation: int,
) -> None:
    """Render one light-to-ready Bending diagram bundle lifecycle."""

    st = runtime.st
    render_timing_mark = runtime.render_timing_mark

    from bending_side_view_diagram import (
        render_bending_side_view_controls,
        render_prepared_bending_side_view_diagram,
    )
    from engineering_page_sections.bending_diagram_bundle_cache import (
        get_bundle_manifest,
    )
    from engineering_page_sections.bending_diagrams import (
        render_bending_diagram_loading_shell,
    )

    generation = int(diagram_shell_generation)
    main_state = str(
        st.session_state.get(
            "bending_state_main",
            st.session_state.get("bending_state", "ULS"),
        )
        or "ULS"
    )
    if main_state not in STATE_OPTIONS:
        main_state = "ULS"
    st.session_state["bending_state"] = main_state
    st.session_state["_bending_diagram_initial_state"] = main_state

    identity = _prepare_identity(
        runtime,
        cached_layout=cached_layout,
        mu_uls_active=mu_uls_active,
    )
    st.session_state["_bending_diagram_bundle_fingerprint"] = identity["fingerprint"]
    st.session_state["_bending_diagram_state_labels"] = {
        option: identity["projections"][option]["state_label"]
        for option in STATE_OPTIONS
    }
    render_timing_mark("bending.diagram.bundle.cache_lookup.start")
    manifest = get_bundle_manifest(
        st.session_state,
        fingerprint=identity["fingerprint"],
    )
    bundle = None
    cache_hit = manifest is not None
    if manifest is not None:
        bundle = _load_cached_bundle(runtime, identity, manifest)
        cache_hit = bundle is not None
    render_timing_mark(
        "bending.diagram.bundle.cache_hit"
        if cache_hit
        else "bending.diagram.bundle.cache_miss"
    )

    bundle_clicked = st.button(
        "Prepare Bending diagram bundle",
        key="bending_deferred_bundle_button",
    )
    if bundle is None and bundle_clicked:
        from application.visualization_runtime_warmup import (
            start_visualization_runtime_warmup,
            wait_for_visualization_runtime_warmup,
        )
        from application.v2_runtime_warmup import start_v2_runtime_warmup

        start_v2_runtime_warmup()
        start_visualization_runtime_warmup()
        wait_for_visualization_runtime_warmup()
        bundle = _build_or_load_bundle(runtime, identity)

    selected_label = identity["projections"][main_state]["state_label"]
    st.session_state["bending_strain_state_local"] = selected_label

    st.markdown(
        '<div data-bending-diagrams-layout-slot data-bending-diagram-region-start '
        'data-bending-diagram-geometry-token="--sb-bending-diagram-plot-height" '
        'aria-hidden="true" style="height:0;line-height:0">&#8203;</div>',
        unsafe_allow_html=True,
    )
    runtime.render_section_title("Bending Diagrams")
    section_tab, side_view_tab, moment_tab = runtime.render_stable_tabs(
        st,
        labels=("Section & stress-strain models", "Side view", "Bending moment"),
        scope_id="bending-section-diagrams",
        install_runtime=False,
    )
    with section_tab:
        with st.container(key="bending_primary_plot_frame"):
            render_bending_diagram_loading_shell(
                st.container(key="bending_diagram_shell"),
                generation=generation,
            )
            with st.container(key="bending_diagram_live"):
                if bundle is not None:
                    render_timing_mark("bending.diagram.bundle.mount.start")
                    st.plotly_chart(
                        bundle["section"][main_state],
                        key=(
                            "bending_section_stress_strain_"
                            f"{STATE_KEYS[main_state]}_chart"
                        ),
                        width="stretch",
                        config={"displayModeBar": False},
                    )
    with side_view_tab:
        render_bending_side_view_controls()
        with st.container(key="bending_side_plot_frame"):
            render_bending_diagram_loading_shell(
                st.container(key="bending_side_diagram_shell"),
                generation=generation,
                primary=False,
            )
            with st.container(key="bending_side_diagram_live"):
                if bundle is not None:
                    render_prepared_bending_side_view_diagram(
                        bundle["side"][main_state],
                        render_controls=False,
                    )
    with moment_tab:
        with st.container(key="bending_moment_plot_frame"):
            render_bending_diagram_loading_shell(
                st.container(key="bending_moment_diagram_shell"),
                generation=generation,
                primary=False,
            )
            with st.container(key="bending_moment_diagram_live"):
                if bundle is not None:
                    runtime.render_plotly_diagram(
                        bundle["moment"],
                        key="bending_moment_diagram",
                        title="Bending moment diagram",
                        config={"displayModeBar": False},
                    )
                    render_timing_mark("bending.diagram.bundle.mount.end")

    st.markdown(
        '<span data-bending-diagram-region-end aria-hidden="true" '
        'style="height:0;line-height:0"></span>'
        '<span data-bending-lightweight-ready="'
        f'{generation}" aria-hidden="true" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    render_bending_state_controls(runtime=runtime)
    if bundle is not None:
        cache_status = "hit" if cache_hit else "miss"
        fingerprint = identity["fingerprint"]
        st.markdown(
            '<span data-bending-diagram-bundle-published="1" '
            f'data-bending-bundle-fingerprint="{fingerprint}" '
            f'data-bending-bundle-cache="{cache_status}" '
            f'data-bending-selected-state="{main_state}" '
            'aria-hidden="true" style="display:none"></span>',
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <style>
        .st-key-bending_deferred_bundle_button {
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

    if bundle is not None:
        components.html(
            f"""
            <script>
            (() => {{
              const doc = window.parent.document;
              const generation = {generation};
              const fingerprint = {identity["fingerprint"]!r};
              const runtimeKey = '__sbBendingDiagramReadyRuntime';
              const prior = window.parent[runtimeKey];
              if (prior && prior.cleanup) prior.cleanup();
              let cancelled = false;
              let timer = 0;
              const completePlot = (selector, requireDetail) => {{
                const plot = doc.querySelector(selector);
                if (!plot || !plot._fullLayout || !plot._fullData) return false;
                if (!plot.querySelector('.scatterlayer .trace')) return false;
                if (!requireDetail) return true;
                return Boolean(
                  plot.querySelector('g.shapelayer .shape-group')
                  && plot.querySelector('.annotation')
                );
              }};
              const markReady = () => {{
                if (cancelled) return;
                const published = [...doc.querySelectorAll(
                  '[data-bending-diagram-bundle-published="1"]'
                )].find((node) =>
                  node.getAttribute('data-bending-bundle-fingerprint') === fingerprint
                );
                const complete = Boolean(
                  published
                  && completePlot('.st-key-bending_diagram_live .js-plotly-plot', true)
                  && completePlot('.st-key-bending_side_diagram_live .js-plotly-plot', false)
                  && completePlot('.st-key-bending_moment_diagram_live .js-plotly-plot', false)
                );
                if (!complete) {{
                  timer = window.setTimeout(markReady, 25);
                  return;
                }}
                published.setAttribute('data-testid', 'bending-diagram-ready');
                published.setAttribute('data-bending-diagram-ready', String(generation));
                published.setAttribute(
                  'data-bending-diagram-bundle-ready', String(generation)
                );
              }};
              markReady();
              window.parent[runtimeKey] = {{
                cleanup: () => {{
                  cancelled = true;
                  if (timer) window.clearTimeout(timer);
                }}
              }};
            }})();
            </script>
            """,
            height=0,
        )
    else:

        components.html(
            f"""
            <script>
            (() => {{
              const doc = window.parent.document;
              const generation = {generation};
              const runtimeKey = '__sbBendingDiagramBundleRuntime';
              const prior = window.parent[runtimeKey];
              if (prior && prior.cleanup) prior.cleanup();
              let cancelled = false;
              let timer = 0;
              const requestBundleAfterPaint = () => {{
                if (cancelled) return;
                const light = doc.querySelector(
                  `[data-bending-lightweight-ready="${{generation}}"]`
                );
                const cards = doc.querySelector(
                  '[data-testid="bending-calculation-ready"]'
                );
                const ready = doc.querySelector(
                  `[data-bending-diagram-bundle-ready="${{generation}}"]`
                );
                if (ready) return;
                if (!light || !cards) {{
                  timer = window.setTimeout(requestBundleAfterPaint, 25);
                  return;
                }}
                window.requestAnimationFrame(() => window.requestAnimationFrame(() => {{
                  if (cancelled) return;
                  doc.documentElement.setAttribute(
                    'data-sb-bending-lightweight-painted', String(generation)
                  );
                  timer = window.setTimeout(() => {{
                    const button = doc.querySelector(
                      '.st-key-bending_deferred_bundle_button button'
                    );
                    if (button && !button.disabled) button.click();
                  }}, 150);
                }}));
              }};
              requestBundleAfterPaint();
              window.parent[runtimeKey] = {{
                cleanup: () => {{
                  cancelled = true;
                  if (timer) window.clearTimeout(timer);
                }}
              }};
            }})();
            </script>
            """,
            height=0,
        )
    render_timing_mark("bending_page.runtime.material_model.end")


__all__ = [
    "BendingDiagramRuntime",
    "render_bending_diagram_bundle_panel",
    "render_bending_state_controls",
]
