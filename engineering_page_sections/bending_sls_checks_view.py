"""SLS Bending-check presentation boundary."""

from __future__ import annotations

from engineering_page_sections.bending_checks_context import BendingSlsChecksInput


def render_bending_sls_checks(view: BendingSlsChecksInput) -> None:
    """Render the existing authoritative SLS teaching sequence."""

    from engineering_page_sections.bending_sls_checks import (
        render_authoritative_sls_checks,
    )

    render_authoritative_sls_checks(
        top_results=view.mutable_results(),
        b=view.width_mm,
        D=view.overall_depth_mm,
        d=view.effective_depth_mm,
        Ast=view.reinforcement_area_mm2,
        Ec=view.concrete_modulus_mpa,
        Es=view.steel_modulus_mpa,
        Mu_star=view.demand_kNm,
        moment_sign=view.moment_sign,
    )


__all__ = ["render_bending_sls_checks"]
