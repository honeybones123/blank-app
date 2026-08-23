"""Bending input-card presentation helpers.

This module formats the existing revision-bound input snapshot.  It does not
calculate capacity or publish engineering results.
"""

from __future__ import annotations

from typing import Any, Mapping

from application.bottom_reinforcement_policy import (
    format_longitudinal_reinforcement_rows,
)
from engineering_page_sections.compact_check_inputs import (
    CheckInputCategory,
    CheckInputPanelConfig,
    InputSource,
    format_dimensions,
    format_number,
    join_summary,
)


def build_bending_input_panel_config(
    *,
    engineering_state: Mapping[str, Any],
    mu_pos_star_kNm: float,
    mu_neg_star_kNm: float,
    load_analysis_actions: bool,
) -> CheckInputPanelConfig:
    """Build the unchanged three-card Bending input presentation."""

    shape = str(engineering_state.get("sec_shape", "RECT") or "RECT")
    width = float(engineering_state.get("b", 0.0) or 0.0)
    depth = float(engineering_state.get("D", 0.0) or 0.0)
    concrete_strength = float(engineering_state.get("fc", 0.0) or 0.0)
    moment = max(abs(float(mu_pos_star_kNm)), abs(float(mu_neg_star_kNm)))
    axial_force = float(engineering_state.get("P_star", 0.0) or 0.0)
    bottom_summary = format_longitudinal_reinforcement_rows(
        engineering_state, face="bottom"
    )
    top_summary = format_longitudinal_reinforcement_rows(
        engineering_state, face="top"
    )

    return CheckInputPanelConfig(
        page_slug="bending",
        mount_closed_bodies=True,
        categories=(
            CheckInputCategory(
                "design_actions",
                "Design actions",
                join_summary(
                    f"M* {format_number(moment, 'kNm', decimals=1)}",
                    f"N* {format_number(axial_force, 'kN', decimals=1)}",
                ),
                lambda: None,
                source=(
                    InputSource.LOAD_ANALYSIS
                    if load_analysis_actions
                    else InputSource.BEAM_INPUTS
                ),
                icon="↧",
            ),
            CheckInputCategory(
                "section_material",
                "Section & material",
                join_summary(
                    format_dimensions(width, depth),
                    shape,
                    f"f'c {format_number(concrete_strength, 'MPa')}",
                ),
                lambda: None,
                icon="▣",
            ),
            CheckInputCategory(
                "reinforcement",
                "Reinforcement",
                join_summary(
                    f"Bottom {bottom_summary}",
                    f"Top {top_summary}",
                ),
                lambda: None,
                icon="●",
            ),
        ),
    )


__all__ = ["build_bending_input_panel_config"]
