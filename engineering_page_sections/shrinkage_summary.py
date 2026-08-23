"""Shrinkage authoritative summary presentation boundary."""

from __future__ import annotations

from typing import Any, Mapping

from engineering_check_ui import PARAMETRIC_RESULT_COLUMNS
from ui.summary_rows import build_shrinkage_summary_rows
from ui_seamless_steps import render_clickable_summary_table


def render_shrinkage_explainer(st_module) -> None:
    """Render the current user-facing Shrinkage explanation unchanged."""

    st_module.markdown(
        """
**What shrinkage is**
Concrete shrinkage is the time-dependent reduction in volume that occurs mainly due to **loss of moisture** (drying shrinkage) and ongoing hydration/chemical effects. It occurs even with no external load.

**Why it matters in design**
Shrinkage can cause:
- **Cracking** where restraint exists (reinforcement, supports, joints, composite action, etc.)
- **Additional curvature and long-term deflection**
- **Stress redistribution** in reinforcement where restrained
- **Durability impacts** through crack control requirements

**Units**
Shrinkage is a **strain** (dimensionless): ΔL/L
Commonly shown as **microstrain (µε)** where 1 µε = 1×10⁻⁶.

**Effect on design**
Shrinkage is not a force (kN). It is a time-dependent strain that can cause deformation and cracking in restrained members.
"""
    )


def render_shrinkage_summary(
    *,
    summary_values: Mapping[str, Any],
    bind_clicks,
) -> tuple[Mapping[str, Any], ...]:
    rows = build_shrinkage_summary_rows(
        eps_cse=float(summary_values.get("eps_cse") or 0.0),
        eps_csd_t=float(summary_values.get("eps_csd_t") or 0.0),
        eps_cs_total=float(summary_values.get("eps_cs_total") or 0.0),
    )
    render_clickable_summary_table(
        rows,
        key_prefix="shrinkage_summary",
        columns=PARAMETRIC_RESULT_COLUMNS,
    )
    bind_clicks()
    return tuple(rows)


__all__ = ["render_shrinkage_explainer", "render_shrinkage_summary"]
