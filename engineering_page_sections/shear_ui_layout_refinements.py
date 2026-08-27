"""Presentation-only refinements for selected Shear check diagrams.

This module keeps the authoritative Shear engineering untouched. It installs
small wrappers around the established presentation functions so the torsion
schematic is more compact and MCFT Check 4 places its two existing explanatory
diagrams side-by-side below the calculation box.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

import streamlit as st

from widgets_helpers import calcbox, info_i_button


_TORSION_COMPACT_HEIGHT_PX = 420
_MCFT_CHECK4_HEIGHT_PX = 430
_MCFT_CHECK4_MAX_WIDTH_PX = 540

_ACTIVE_MCFT_VIEW: ContextVar[Any | None] = ContextVar(
    "shear_mcft_layout_refinement_view",
    default=None,
)


def _resolve_check4_strain_inputs(mcft_module: Any, view: Any) -> tuple[float, float, float, dict[str, Any]]:
    """Reuse the established Check 4 strain-profile inputs without recalculation changes."""

    eps_x_mcft = float(view.eps_x)
    eps_top_uls = None
    eps_bot_uls = None

    for key in ("eps_c",):
        value = st.session_state.get(key)
        if value is not None:
            try:
                eps_top_uls = float(value)
                break
            except (TypeError, ValueError):
                pass

    for key in ("eps_s",):
        value = st.session_state.get(key)
        if value is not None:
            try:
                eps_bot_uls = float(value)
                break
            except (TypeError, ValueError):
                pass

    if eps_top_uls is None or eps_bot_uls is None:
        try:
            from bending_core import _stress_strain_state

            state_dict = _stress_strain_state("ULS")
            if eps_top_uls is None and "eps_c" in state_dict:
                eps_top_uls = float(state_dict["eps_c"])
            if eps_bot_uls is None and "eps_s" in state_dict:
                eps_bot_uls = float(state_dict["eps_s"])
        except Exception:
            pass

    if eps_top_uls is None or eps_bot_uls is None:
        eps_top_uls, eps_bot_uls = mcft_module.derive_eps_top_bot_for_step4_diagram(
            eps_x_mcft,
            delta=0.00035,
        )

    force_geom_kwargs: dict[str, Any] = {}
    moment_sign = str(
        st.session_state.get("bending_detail_view", "positive") or "positive"
    ).strip().lower()
    try:
        from bending_core import _stress_strain_state

        uls = _stress_strain_state("ULS", moment_sign)
        section_depth = float(uls.get("D") or 0.0)
        neutral_axis = float(uls.get("c") or 0.0)
        gamma = float(uls.get("gamma") or 0.0)
        effective_depth = float(uls.get("d") or 0.0)
        if section_depth > 1e-6 and neutral_axis > 1e-6 and gamma > 1e-6:
            force_geom_kwargs = {
                "force_section_D_mm": section_depth,
                "force_section_c_mm": neutral_axis,
                "force_section_gamma": gamma,
                "force_tension_steel_y_from_top_mm": effective_depth,
                "force_moment_sign": moment_sign,
            }
    except Exception:
        force_geom_kwargs = {}

    return (
        float(eps_top_uls),
        eps_x_mcft,
        float(eps_bot_uls),
        force_geom_kwargs,
    )


def _render_check4_technical_basis() -> None:
    """Keep the existing Check 4 technical-basis affordance with the new layout."""

    spacer, info_col = st.columns([0.92, 0.08])
    with spacer:
        pass
    with info_col:
        with info_i_button(help_text="Longitudinal strain εx (MCFT)"):
            st.markdown(
                r"""
### Longitudinal strain $\varepsilon_x$ (MCFT)

Check 4 evaluates the average longitudinal strain at mid-depth for the Modified
Compression Field Theory shear model. Bending, axial load and the longitudinal
component of the diagonal compression field all contribute to this strain.

The **internal force resolution** diagram shows how the section actions resolve
into longitudinal resisting forces. The **longitudinal strain profile** diagram
then shows how the resulting mid-depth strain relates to the top and bottom
section strains.

The calculated $\varepsilon_x$ is carried into the following MCFT checks to
resolve $k_v$ and $\theta_v$.
"""
            )


def _render_check4_diagrams(mcft_module: Any, view: Any) -> None:
    eps_top_uls, eps_x_mcft, eps_bot_uls, force_geom_kwargs = (
        _resolve_check4_strain_inputs(mcft_module, view)
    )

    fig_force = mcft_module.make_mcft_longitudinal_strain_profile_fig(
        eps_top_uls=eps_top_uls,
        eps_x_mcft=eps_x_mcft,
        eps_bot_uls=eps_bot_uls,
        title="Longitudinal strain profile",
        height=_MCFT_CHECK4_HEIGHT_PX,
        force_resolution=True,
        force_theta_deg=float(view.theta_v_deg),
        **force_geom_kwargs,
    )
    mcft_module._standardise_shear_visual_layout(
        fig_force,
        title_pad_t=int(mcft_module.MCFT_BEHAVIOUR_MARGIN["t"]),
    )
    fig_force.update_layout(
        height=_MCFT_CHECK4_HEIGHT_PX,
        autosize=True,
        width=None,
    )

    fig_strain = mcft_module.make_mcft_longitudinal_strain_profile_fig(
        eps_top_uls=eps_top_uls,
        eps_x_mcft=eps_x_mcft,
        eps_bot_uls=eps_bot_uls,
        title="Longitudinal strain profile",
        height=_MCFT_CHECK4_HEIGHT_PX,
        force_resolution=False,
    )
    mcft_module._standardise_shear_visual_layout(
        fig_strain,
        title_pad_t=int(mcft_module.MCFT_BEHAVIOUR_MARGIN["t"]),
    )
    fig_strain.update_layout(
        height=_MCFT_CHECK4_HEIGHT_PX,
        autosize=True,
        width=None,
    )

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### Internal force resolution")
        mcft_module._render_centered_shear_plotly(
            fig_force,
            chart_key="shear_mcft_diagram_force",
            max_width_px=_MCFT_CHECK4_MAX_WIDTH_PX,
            height_px=_MCFT_CHECK4_HEIGHT_PX,
            title_pad_t=int(mcft_module.MCFT_BEHAVIOUR_MARGIN["t"]),
            compact_top=True,
        )
    with right:
        st.markdown("#### Longitudinal strain profile")
        mcft_module._render_centered_shear_plotly(
            fig_strain,
            chart_key="shear_mcft_diagram_strain",
            max_width_px=_MCFT_CHECK4_MAX_WIDTH_PX,
            height_px=_MCFT_CHECK4_HEIGHT_PX,
            title_pad_t=int(mcft_module.MCFT_BEHAVIOUR_MARGIN["t"]),
            compact_top=True,
        )


def install_shear_ui_layout_refinements() -> None:
    """Install idempotent presentation wrappers used by the Shear page."""

    from engineering_page_sections import shear_mcft_strength_checks as mcft_module
    from engineering_page_sections import shear_torsion_dimensions_checks as torsion_module

    if getattr(torsion_module, "_compact_torsion_layout_installed", False) is False:
        original_centered = torsion_module._render_centered_shear_plotly

        def compact_torsion_centered(fig, *, chart_key: str, **kwargs):
            if chart_key == "torsion_cracking_diagram":
                kwargs["height_px"] = _TORSION_COMPACT_HEIGHT_PX
                kwargs.setdefault("compact_top", True)
                fig.update_layout(height=_TORSION_COMPACT_HEIGHT_PX)
            return original_centered(fig, chart_key=chart_key, **kwargs)

        torsion_module._render_centered_shear_plotly = compact_torsion_centered
        torsion_module._compact_torsion_layout_installed = True

    if getattr(mcft_module, "_check4_side_by_side_layout_installed", False):
        return

    original_step = mcft_module.render_expandable_step
    original_render = mcft_module.render_shear_mcft_strength_checks

    def refined_step(*args: Any, **kwargs: Any):
        step_id = str(kwargs.get("step_id", ""))
        view = _ACTIVE_MCFT_VIEW.get()
        if step_id != "shear_check4" or view is None:
            return original_step(*args, **kwargs)

        calc_md = kwargs.get("calc_md")
        status_kind = kwargs.get("status_kind")

        def render_check4_body() -> None:
            calcbox(
                calc_md,
                status=status_kind,
                uid="shear_check4__details",
            )
            _render_check4_technical_basis()
            _render_check4_diagrams(mcft_module, view)

        revised = dict(kwargs)
        revised["calc_md"] = None
        revised["calc_render_fn"] = render_check4_body
        revised["diagram_render_fn"] = None
        return original_step(*args, **revised)

    def refined_render(view: Any) -> None:
        token = _ACTIVE_MCFT_VIEW.set(view)
        try:
            original_render(view)
        finally:
            _ACTIVE_MCFT_VIEW.reset(token)

    mcft_module.render_expandable_step = refined_step
    mcft_module.render_shear_mcft_strength_checks = refined_render
    mcft_module._check4_side_by_side_layout_installed = True


__all__ = ["install_shear_ui_layout_refinements"]
