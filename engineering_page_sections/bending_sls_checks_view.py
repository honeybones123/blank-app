"""SLS Bending-check presentation boundary."""

from __future__ import annotations

from engineering_page_sections.bending_checks_context import BendingSlsChecksInput


def render_bending_sls_checks(view: BendingSlsChecksInput) -> None:
    """Render the existing authoritative SLS teaching sequence."""

    from bending_tabs import render_sls_tab

    render_sls_tab(
        view.mutable_results(),
        view.width_mm,
        view.overall_depth_mm,
        view.effective_depth_mm,
        view.reinforcement_area_mm2,
        view.concrete_modulus_mpa,
        view.steel_modulus_mpa,
        view.demand_kNm,
        summary_mode=False,
        moment_sign=view.moment_sign,
    )


__all__ = ["render_bending_sls_checks"]
