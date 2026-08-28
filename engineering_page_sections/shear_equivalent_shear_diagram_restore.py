"""Restore the Check 2 equivalent-shear diagram without changing engineering results.

The established Check 2 renderer already owns the combined V+T / V / T stress-flow
schematics when torsion design is required.  When Check 1 screens torsion out,
that renderer currently passes ``diagram_render_fn=None`` and the equivalent-shear
visual disappears entirely.  This presentation adapter reinstates a shear-only
version for that screened-out case, where the authoritative result is
``V_eq* = |V*|``.
"""

from __future__ import annotations

from typing import Any

import streamlit as st


def _render_screened_equivalent_shear(torsion_module: Any) -> None:
    """Render the existing section stress-flow schematic in shear-only mode."""

    st.markdown(
        """
        <style>
        .shear-sf-subheading { margin: 0.35rem 0 0.3rem 0; font-size: 0.95rem; font-weight: 600; color: rgba(49,51,63,0.95); }
        .shear-sf-helper { margin: 0.2rem 0 0.3rem 0; font-size: 0.875rem; color: rgba(49,51,63,0.72); line-height: 1.35; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="shear-sf-helper">Shear only — torsion was screened out in Check 1, so V<sub>eq</sub><sup>*</sup> = |V<sup>*</sup>|.</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="shear-sf-subheading">Stress flow schematic</p>',
        unsafe_allow_html=True,
    )

    from section_layout import compute_section_layout

    layout = compute_section_layout()
    raw_shape = layout.get("shape_name")
    shape_name = "Rectangle (b × D)"
    if isinstance(raw_shape, str) and raw_shape.strip():
        shape_name = raw_shape.strip()

    dims = layout.get("dims")
    reo = layout.get("reo")
    if not isinstance(dims, dict):
        dims = {}
    if not isinstance(reo, dict):
        reo = {}

    try:
        fig = torsion_module.plot_shear_torsion_section_2d(
            shape_name=shape_name,
            dims=dims,
            reo=reo,
            mode="V",
            show_labels=True,
            compact_stress_labels=True,
            show_schematic_footer=False,
        )
    except ValueError as exc:
        st.error(f"Reinforcement layout failed: {exc}")
        reo_no_bars = dict(reo)
        reo_no_bars.update(
            {
                "nb_top": 0,
                "db_top": 0.0,
                "nb_bot": 0,
                "db_bot": 0.0,
                "nb_or_s_top_1": 0.0,
                "nb_or_s_top_2": 0.0,
                "nb_or_s_bot_1": 0.0,
                "nb_or_s_bot_2": 0.0,
                "lig_d": 0.0,
                "lig_legs": 0,
            }
        )
        fig = torsion_module.plot_shear_torsion_section_2d(
            shape_name=shape_name,
            dims=dims,
            reo=reo_no_bars,
            mode="V",
            show_labels=True,
            compact_stress_labels=True,
            show_schematic_footer=False,
        )

    torsion_module._render_centered_shear_plotly(
        fig,
        chart_key="shear_equivalent_shear_stress_flow_diagram",
        max_width_px=torsion_module.SHEAR_VISUAL_MAX_WIDTH_PX,
    )


def install_equivalent_shear_diagram_restore() -> None:
    """Ensure Check 2 retains a technically correct diagram after torsion screening."""

    from engineering_page_sections import shear_torsion_dimensions_checks as torsion_module

    if getattr(torsion_module, "_equivalent_shear_screened_diagram_installed", False):
        return

    original_step = torsion_module.render_expandable_step

    def restored_step(*args: Any, **kwargs: Any):
        step_id = str(kwargs.get("step_id", ""))
        existing_diagram = kwargs.get("diagram_render_fn")
        if step_id != "shear_check2" or existing_diagram is not None:
            return original_step(*args, **kwargs)

        revised = dict(kwargs)
        revised["diagram_render_fn"] = lambda: _render_screened_equivalent_shear(
            torsion_module
        )
        return original_step(*args, **revised)

    torsion_module.render_expandable_step = restored_step
    torsion_module._equivalent_shear_screened_diagram_installed = True


__all__ = ["install_equivalent_shear_diagram_restore"]
