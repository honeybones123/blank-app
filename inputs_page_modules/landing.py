"""Inputs landing-state and landing-card helpers."""

from __future__ import annotations

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
    sigma_raw = get_param_fn("sigma_sr", None)
    if sigma_raw is None:
        sigma_raw = get_param_fn("sigma_s_sls", 0.0)
    return {
        "uls_Mstar": get_param_fn("uls_Mstar", 0.0),
        "uls_Vstar": get_param_fn("uls_Vstar", 0.0),
        "sls_Mstar": get_param_fn("sls_Mstar", 0.0),
        "sls_Vstar": get_param_fn("sls_Vstar", 0.0),
        "sls_Nstar": get_param_fn("sls_Nstar", 0.0),
        "Tu_star": get_param_fn("Tu_star", 0.0),
        "uls_Nstar_or_N_star": get_param_fn("uls_Nstar", 0.0) or get_param_fn("N_star", 0.0),
        "P_star": get_param_fn("P_star", 0.0),
        "sigma_sr": sigma_raw,
        "load_Mstar_neg_proxy": get_param_fn("load_Mstar_neg_proxy", 0.0),
        "inputs_load_Mstar_neg_proxy": get_param_fn("inputs_load_Mstar_neg_proxy", 0.0),
        "inputs_load_Vstar_proxy": get_param_fn("inputs_load_Vstar_proxy", 0.0),
    }


def _landing_load_values(get_param_fn: Callable[..., Any]) -> dict[str, Any]:
    values = {
        "g_udl_kNm_per_m": get_param_fn("g_udl_kNm_per_m", 0.0),
        "q_udl_kNm_per_m": get_param_fn("q_udl_kNm_per_m", 0.0),
        # Point and staged load inputs are also applied loads. Omitting them
        # made a load-driven beam look empty and left the Design Brain waiting
        # even though the engineering transaction had a real load case.
        "G_point_kN": get_param_fn("G_point_kN", 0.0),
        "Q_point_kN": get_param_fn("Q_point_kN", 0.0),
    }
    for prefix in ("design_point_G_", "design_point_Q_"):
        for index in range(1, 7):
            values[f"{prefix}{index}"] = get_param_fn(f"{prefix}{index}", 0.0)
    return values


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


def render_inputs_landing_card(
    *,
    st_module: Any,
    sync_callbacks: dict | None = None,
    get_sync_callbacks_fn: Callable[..., dict] = get_sync_callbacks,
    scroll_design_actions_flag: str = INPUTS_SCROLL_DESIGN_ACTIONS_FLAG,
    pending_nav_page_slug_key: str = INPUTS_PENDING_NAV_PAGE_SLUG_KEY,
) -> None:
    """Render the empty-input welcome card and its two proven navigation actions."""
    if sync_callbacks is None:
        sync_callbacks = get_sync_callbacks_fn()
    _ = sync_callbacks

    st_module.markdown(
        """
<style>
.inputs-landing-wrap {
  width: 100%;
  max-width: none;
  box-sizing: border-box;
  margin: 0.5rem 0 1.25rem 0;
  padding: 1.35rem 1.25rem 1.45rem 1.25rem;
  border-radius: 12px;
  background: linear-gradient(165deg, rgba(31,119,180,0.06) 0%, rgba(49,51,63,0.04) 100%);
  border: 1px solid rgba(49,51,63,0.08);
  box-shadow: 0 1px 2px rgba(15,23,42,0.04);
}
.inputs-landing-wrap h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1.35rem;
  font-weight: 650;
  color: rgba(49,51,63,0.95);
}
.inputs-landing-wrap p.lead {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  line-height: 1.45;
  color: rgba(49,51,63,0.78);
}
.inputs-landing-options {
  margin: 0.75rem 0 0.35rem 0;
  padding-left: 1.1rem;
  color: rgba(49,51,63,0.82);
  font-size: 0.95rem;
}
.inputs-landing-options li { margin: 0.35rem 0; }
</style>
""",
        unsafe_allow_html=True,
    )
    st_module.markdown(
        """
<div class="inputs-landing-wrap">
  <h3>Start Your Design</h3>
  <p class="lead">This tool requires design actions or applied loads to begin.</p>
  <p style="margin:0 0 0.25rem 0;font-weight:600;font-size:0.92rem;color:rgba(49,51,63,0.72);">You can:</p>
  <ul class="inputs-landing-options">
    <li>Enter design actions (M*, V*, sigma)</li>
    <li>Use the Design Mode to generate loads automatically</li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )

    button_inputs, button_design = st_module.columns(2, gap="small")
    with button_inputs:
        if st_module.button(
            "Go to Design Inputs",
            key="inputs_landing_go_design_inputs",
            use_container_width=True,
        ):
            st_module.session_state[scroll_design_actions_flag] = True
            st_module.session_state[INPUTS_DESIGN_STARTED_KEY] = True
            st_module.rerun()
    with button_design:
        if st_module.button(
            "Open Design Mode",
            key="inputs_landing_open_detailed",
            use_container_width=True,
        ):
            st_module.session_state[pending_nav_page_slug_key] = "design"
            st_module.rerun()


def render_landing_card(**kwargs: Any) -> None:
    render_inputs_landing_card(**kwargs)


__all__ = [
    "INPUTS_DESIGN_STARTED_KEY",
    "INPUTS_PENDING_NAV_PAGE_SLUG_KEY",
    "INPUTS_SCROLL_DESIGN_ACTIONS_FLAG",
    "inputs_has_design_actions_or_loads",
    "inputs_show_landing_dashboard",
    "render_inputs_landing_card",
    "render_landing_card",
]
