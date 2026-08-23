"""ULS Bending-check presentation boundary."""

from __future__ import annotations

from engineering_page_sections.bending_checks_context import BendingUlsChecksInput


def render_bending_uls_checks(view: BendingUlsChecksInput) -> None:
    """Render the existing authoritative ULS teaching sequence."""

    from bending_tabs import render_uls_tab

    render_uls_tab(
        view.mutable_results(),
        view.width_mm,
        view.overall_depth_mm,
        view.concrete_strength_mpa,
        view.steel_yield_strength_mpa,
        view.reinforcement_area_mm2,
        view.effective_depth_mm,
        summary_mode=False,
        Mu_star_override=view.demand_kNm,
        moment_sign=view.moment_sign,
    )


__all__ = ["render_bending_uls_checks"]
