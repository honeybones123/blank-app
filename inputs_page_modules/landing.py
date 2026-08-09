"""Inputs landing-state and landing-card helpers."""

from __future__ import annotations

import copy
from typing import Any, Callable

from inputs_page_modules.session import (
    build_inputs_has_design_actions_or_loads_decision,
    build_inputs_landing_dashboard_visibility_decision,
)
from state_and_helpers import get_param, get_sync_callbacks


INPUTS_SCROLL_DESIGN_ACTIONS_FLAG = "_inputs_pending_scroll_design_actions"
INPUTS_PENDING_NAV_PAGE_SLUG_KEY = "_pending_nav_page_slug"
# Presentation-only state matching V2's explicit landing -> workspace transition.
# The canonical input snapshot remains the authority for engineering values.
INPUTS_DESIGN_STARTED_KEY = "_inputs_design_started"


def _landing_design_action_values(get_param_fn: Callable[..., Any]) -> dict[str, Any]:
    return {
        "uls_Mstar": get_param_fn("uls_Mstar", 0.0),
        "uls_Vstar": get_param_fn("uls_Vstar", 0.0),
        "sls_Mstar": get_param_fn("sls_Mstar", 0.0),
        "sls_Vstar": get_param_fn("sls_Vstar", 0.0),
        "sls_Nstar": get_param_fn("sls_Nstar", 0.0),
        "Tu_star": get_param_fn("Tu_star", 0.0),
        "uls_Nstar_or_N_star": get_param_fn("uls_Nstar", 0.0) or get_param_fn("N_star", 0.0),
        "P_star": get_param_fn("P_star", 0.0),
        "load_Mstar_neg_proxy": get_param_fn("load_Mstar_neg_proxy", 0.0),
        "inputs_load_Mstar_neg_proxy": get_param_fn("inputs_load_Mstar_neg_proxy", 0.0),
        "inputs_load_Vstar_proxy": get_param_fn("inputs_load_Vstar_proxy", 0.0),
    }


def _landing_load_values(get_param_fn: Callable[..., Any]) -> dict[str, Any]:
    return {
        "g_udl_kNm_per_m": get_param_fn("g_udl_kNm_per_m", 0.0),
        "q_udl_kNm_per_m": get_param_fn("q_udl_kNm_per_m", 0.0),
    }


def inputs_show_landing_dashboard(
    *,
    get_param_fn: Callable[..., Any] = get_param,
    same_page_rerun_has_non_landing_state: bool = False,
    capacity_context_matches: bool = False,
) -> bool:
    decision = build_inputs_landing_dashboard_visibility_decision(
        same_page_rerun_has_non_landing_state=same_page_rerun_has_non_landing_state,
        design_action_values=_landing_design_action_values(get_param_fn),
        load_values=_landing_load_values(get_param_fn),
        capacity_context_matches=capacity_context_matches,
    )
    return bool(decision.show_landing_dashboard)


def inputs_has_design_actions_or_loads(*, get_param_fn: Callable[..., Any] = get_param) -> bool:
    action_values = {
        **_landing_design_action_values(get_param_fn),
        **_landing_load_values(get_param_fn),
    }
    decision = build_inputs_has_design_actions_or_loads_decision(
        action_values=action_values,
    )
    return bool(decision.has_design_actions_or_loads)


def _render_legacy_inputs_landing_card(
    *,
    st_module: Any,
    sync_callbacks: dict | None = None,
    get_sync_callbacks_fn: Callable[..., dict] = get_sync_callbacks,
    make_cross_section_figure_fn: Callable[[], Any] | None = None,
    scroll_design_actions_flag: str = INPUTS_SCROLL_DESIGN_ACTIONS_FLAG,
    pending_nav_page_slug_key: str = INPUTS_PENDING_NAV_PAGE_SLUG_KEY,
) -> None:
    """Render the legacy empty-input choice using shared diagrams and routing."""
    return

    if sync_callbacks is None:
        sync_callbacks = get_sync_callbacks_fn()
    _ = (sync_callbacks, scroll_design_actions_flag)

    st_module.markdown(
        """
<style>
.inputs-landing-intro {
  margin: 0.5rem 0 1rem;
}
.stApp .stMarkdown .inputs-landing-intro h2 {
  margin: 0 0 0.35rem !important;
  padding: 0 !important;
  border: 0 !important;
  color: #182230 !important;
  font-size: 1.35rem !important;
  font-weight: 700 !important;
  line-height: 1.3 !important;
}
.inputs-landing-intro p,
.inputs-landing-support {
  margin: 0;
  color: #475569;
  font-size: 0.95rem;
  font-weight: 400;
  line-height: 1.5;
}
div[data-testid="stHorizontalBlock"]:has(.st-key-inputs_landing_beam_card) {
  align-items: stretch !important;
  gap: 1rem !important;
}
.st-key-inputs_landing_beam_card,
.st-key-inputs_landing_load_card {
  height: 100%;
  min-height: 455px;
  box-sizing: border-box;
  padding: 1rem 1rem 0.95rem;
  border: 1px solid #dce3ec;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 3px 10px rgba(15, 23, 42, 0.06);
}
.st-key-inputs_landing_load_card {
  border-color: rgba(37, 99, 235, 0.34);
  background: rgba(37, 99, 235, 0.035);
}
.st-key-inputs_landing_beam_card > div[data-testid="stVerticalBlock"],
.st-key-inputs_landing_load_card > div[data-testid="stVerticalBlock"] {
  height: 100%;
}
.stApp .stMarkdown .inputs-landing-card-copy h3 {
  margin: 0 0 0.4rem !important;
  color: #182230 !important;
  font-size: 1.08rem !important;
  font-weight: 700 !important;
  line-height: 1.35 !important;
}
.inputs-landing-card-copy p {
  margin: 0 0 0.55rem;
  color: #334155;
  font-size: 0.92rem;
  font-weight: 400;
  line-height: 1.45;
}
.inputs-landing-card-copy p.secondary {
  margin-bottom: 0;
  color: #64748b;
  font-size: 0.86rem;
}
.st-key-inputs_landing_beam_diagram,
.st-key-inputs_landing_load_diagram,
.st-key-inputs_landing_bmd_diagram {
  margin: 0 !important;
}
.st-key-inputs_landing_open_beam_inputs,
.st-key-inputs_landing_open_load_analysis {
  margin-top: auto !important;
}
.st-key-inputs_landing_open_beam_inputs button {
  border: 1px solid #2563eb !important;
  background: #ffffff !important;
  color: #2563eb !important;
}
.st-key-inputs_landing_open_beam_inputs button:hover,
.st-key-inputs_landing_open_beam_inputs button:focus-visible {
  border-color: #1d4ed8 !important;
  background: rgba(37, 99, 235, 0.06) !important;
  color: #1d4ed8 !important;
}
.st-key-inputs_landing_open_load_analysis button {
  border: 1px solid #2563eb !important;
  background: #2563eb !important;
  color: #ffffff !important;
}
.st-key-inputs_landing_open_load_analysis button:hover,
.st-key-inputs_landing_open_load_analysis button:focus-visible {
  border-color: #1d4ed8 !important;
  background: #1d4ed8 !important;
  color: #ffffff !important;
}
.inputs-landing-support {
  margin: 0.8rem 0 1rem;
}
@media (max-width: 700px) {
  .st-key-inputs_landing_beam_card,
  .st-key-inputs_landing_load_card {
    min-height: 0;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )
    st_module.markdown(
        """
<div class="inputs-landing-intro">
  <h2>Start your beam design</h2>
  <p>Choose whether to define the beam directly or calculate its design actions from applied loads.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    def _open_beam_inputs() -> None:
        # A widget callback runs before the next script pass, so the landing
        # branch is replaced cleanly instead of being left above the workspace
        # by an interrupted in-render rerun.
        st_module.session_state[INPUTS_DESIGN_STARTED_KEY] = True

    def _open_load_analysis() -> None:
        # The router consumes this existing deferred-nav key before rendering
        # its radio, preserving the current Streamlit session and beam state.
        st_module.session_state[pending_nav_page_slug_key] = "design"

    beam_col, load_col = st_module.columns(2, gap="medium")
    with beam_col:
        with st_module.container(key="inputs_landing_beam_card"):
            st_module.markdown(
                """
<div class="inputs-landing-card-copy">
  <h3>Beam Inputs</h3>
  <p>Enter known design actions and define the beam size, materials and reinforcement.</p>
  <p class="secondary">Best when you already have design actions or want to check an existing beam.</p>
</div>
""",
                unsafe_allow_html=True,
            )
            if make_cross_section_figure_fn is not None:
                section_figure = copy.deepcopy(make_cross_section_figure_fn())
                if section_figure is not None:
                    section_figure.update_layout(
                        autosize=True,
                        height=225,
                        margin=dict(l=4, r=4, t=4, b=4),
                    )
                    section_figure.update_xaxes(showticklabels=False, title_text=None)
                    section_figure.update_yaxes(showticklabels=False, title_text=None)
                    with st_module.container(key="inputs_landing_beam_diagram"):
                        st_module.plotly_chart(
                            section_figure,
                            key="inputs_landing_beam_section_chart",
                            width="stretch",
                            config={"displayModeBar": False, "responsive": True},
                        )
            st_module.button(
                "Open Beam Inputs",
                key="inputs_landing_open_beam_inputs",
                width="stretch",
                on_click=_open_beam_inputs,
            )

    with load_col:
        with st_module.container(key="inputs_landing_load_card"):
            st_module.markdown(
                """
<div class="inputs-landing-card-copy">
  <h3>Load Analysis</h3>
  <p>Define the supports, span and applied loads to calculate the beam's design actions and diagrams.</p>
  <p class="secondary">Best when you know the loads but have not calculated the design actions.</p>
</div>
""",
                unsafe_allow_html=True,
            )
            from ui.diagrams.moment_shear_diagram import (
                figure_bmd_from_state,
                plot_load_diagram_plotly,
            )

            load_figure = plot_load_diagram_plotly(
                case="Simple beam – UDL over entire span",
                L=6.0,
                params={"w": 12.0},
                support_condition="Simply supported",
            )
            load_figure.layout.annotations = tuple(
                annotation
                for annotation in (load_figure.layout.annotations or ())
                if bool(annotation.showarrow)
            )
            load_figure.update_layout(
                autosize=True,
                height=115,
                margin=dict(l=4, r=4, t=4, b=4),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            load_figure.update_xaxes(visible=False)
            load_figure.update_yaxes(visible=False, range=[-0.34, 0.62])
            with st_module.container(key="inputs_landing_load_diagram"):
                st_module.plotly_chart(
                    load_figure,
                    key="inputs_landing_load_chart",
                    width="stretch",
                    config={"displayModeBar": False, "responsive": True},
                )

            x_values = [index * 0.25 for index in range(25)]
            moment_values = [x_value * (6.0 - x_value) for x_value in x_values]
            bmd_figure = figure_bmd_from_state(
                {
                    "x_plot": x_values,
                    "M_plot": moment_values,
                    "support_positions_plot": [0.0, 6.0],
                    "support_types_plot": ["pinned", "roller"],
                    "L": 6.0,
                    "preview_x_m": None,
                    "design_x_m": None,
                    "preview_M": None,
                    "x_pad": 0.35,
                    "support_type": "simply_supported",
                }
            )
            bmd_figure.update_layout(
                autosize=True,
                height=105,
                margin=dict(l=4, r=4, t=4, b=4),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            bmd_figure.update_xaxes(visible=False)
            bmd_figure.update_yaxes(visible=False)
            with st_module.container(key="inputs_landing_bmd_diagram"):
                st_module.plotly_chart(
                    bmd_figure,
                    key="inputs_landing_bmd_chart",
                    width="stretch",
                    config={"displayModeBar": False, "responsive": True},
                )
            st_module.button(
                "Open Load Analysis",
                key="inputs_landing_open_load_analysis",
                width="stretch",
                on_click=_open_load_analysis,
            )

    st_module.markdown(
        '<p class="inputs-landing-support">Not sure where to start? Use Load Analysis if you know the loads but not the design actions.</p>',
        unsafe_allow_html=True,
    )


def render_inputs_landing_card(
    *,
    st_module: Any,
    sync_callbacks: dict | None = None,
    get_sync_callbacks_fn: Callable[..., dict] = get_sync_callbacks,
    make_cross_section_figure_fn: Callable[[], Any] | None = None,
    scroll_design_actions_flag: str = INPUTS_SCROLL_DESIGN_ACTIONS_FLAG,
    pending_nav_page_slug_key: str = INPUTS_PENDING_NAV_PAGE_SLUG_KEY,
) -> None:
    """Compatibility hook retained for callers after Start became a route."""
    _ = (
        st_module,
        sync_callbacks,
        get_sync_callbacks_fn,
        make_cross_section_figure_fn,
        scroll_design_actions_flag,
        pending_nav_page_slug_key,
    )


def render_landing_card(**kwargs: Any) -> None:
    """Compatibility callback retained for the Inputs runtime; render nothing."""
    # Initial path selection now belongs to the top-level Start route.  Runtime
    # adapters still accept this callback, so keep its signature stable without
    # duplicating navigation inside Beam Inputs.
    _ = kwargs


__all__ = [
    "INPUTS_DESIGN_STARTED_KEY",
    "INPUTS_PENDING_NAV_PAGE_SLUG_KEY",
    "INPUTS_SCROLL_DESIGN_ACTIONS_FLAG",
    "inputs_has_design_actions_or_loads",
    "inputs_show_landing_dashboard",
    "render_inputs_landing_card",
    "render_landing_card",
]
