"""Bending diagram section helpers."""

from __future__ import annotations

import streamlit as st

from bending_core import _stress_strain_state
from state_and_helpers import get_param
from ui.diagrams.bending_3d_diagram import (
    build_beam_3d_figure_pure as _shared_build_beam_3d_figure_pure,
)


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
    input_state=None,
    authoritative_bending=None,
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
        input_state=input_state,
        authoritative_bending=authoritative_bending,
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


def render_bending_diagram_loading_shell(
    container,
    *,
    generation: int,
    primary: bool = True,
) -> None:
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
        .st-key-bending_primary_plot_frame,
        .st-key-bending_side_plot_frame,
        .st-key-bending_moment_plot_frame {
          display: grid !important;
          grid-template-columns: minmax(0, 1fr) !important;
          width: 100%;
          min-height: var(--sb-bending-diagram-plot-height, 320px);
        }
        .st-key-bending_primary_plot_frame
        > div[data-testid="stLayoutWrapper"],
        .st-key-bending_side_plot_frame
        > div[data-testid="stLayoutWrapper"],
        .st-key-bending_moment_plot_frame
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
        .st-key-bending_side_diagram_live,
        .st-key-bending_moment_diagram_live {
          z-index: 1;
          min-height: var(--sb-bending-diagram-plot-height, 320px);
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
        html:has(.st-key-bending_side_diagram_live .js-plotly-plot)
        .st-key-bending_side_plot_frame
        > div[data-testid="stLayoutWrapper"]:has(
          > .st-key-bending_side_diagram_shell
        ),
        html:has(.st-key-bending_moment_diagram_live .js-plotly-plot)
        .st-key-bending_moment_plot_frame
        > div[data-testid="stLayoutWrapper"]:has(
          > .st-key-bending_moment_diagram_shell
        ) {
          display: none !important;
          height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
        }
        </style>
        <div class="bending-diagram-loading-region"
             PRIMARY_ATTRIBUTES
             data-bending-diagram-geometry-token="--sb-bending-diagram-plot-height"
             role="status" aria-live="polite">
          <div class="bending-diagram-loading-shell">
            <span class="bending-diagram-loading-icon" aria-hidden="true">&#9711;</span>
            <span class="bending-diagram-loading-copy">Preparing section stress and strain</span>
          </div>
        </div>
            """
            .replace(
                "PRIMARY_ATTRIBUTES",
                (
                    'data-testid="bending-diagram-loading-region" '
                    f'data-bending-diagram-shell="{int(generation)}"'
                    if primary
                    else f'data-bending-tab-shell="{int(generation)}"'
                ),
            ),
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
