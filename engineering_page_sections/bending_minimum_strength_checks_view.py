"""Minimum-strength Bending-check presentation boundary."""

from __future__ import annotations

from engineering_page_sections.bending_checks_context import (
    BendingMinimumStrengthChecksInput,
)


def render_bending_minimum_strength_checks(
    view: BendingMinimumStrengthChecksInput,
) -> None:
    """Render the existing minimum-strength teaching sequence."""

    from engineering_page_sections.bending_minimum_strength_checks import (
        render_minimum_strength_checks,
    )

    render_minimum_strength_checks(
        view.mutable_results(),
        view.width_mm,
        view.overall_depth_mm,
        view.concrete_strength_mpa,
        view.steel_yield_strength_mpa,
        view.reinforcement_area_mm2,
        summary_mode=False,
    )


__all__ = ["render_bending_minimum_strength_checks"]
