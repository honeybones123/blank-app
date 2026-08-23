"""Creep authoritative summary presentation boundary."""

from __future__ import annotations

from typing import Any, Mapping

from engineering_check_ui import PARAMETRIC_RESULT_COLUMNS
from ui.summary_rows import build_creep_summary_rows
from ui_seamless_steps import render_clickable_summary_table


def render_creep_explainer(st_module) -> None:
    """Render the existing AS 3600 Creep page explanation."""

    st_module.markdown(
        r"""
This page computes **concrete creep coefficient** and **creep strain** in accordance with
**AS 3600:2018 Clause 3.1.8**, including:

- **Basic creep coefficient** ($\varphi_{cc,b}$) — Table 3.1.8.2
- **Design creep coefficient** at time $t$, $\varphi_{cc}(t) = k_2 k_3 k_4 k_5 k_6 \, \varphi_{cc,b}$ — Cl. 3.1.8.3
- **Final creep coefficient** after 30 years, $\varphi^{\*}_{cc}$ — Table 3.1.8.3
- **Creep strain** at time $t$, $\varepsilon_{cc} = \varphi_{cc}(t)\, \sigma_0 / E_c$ — Cl. 3.1.8.1

Creep coefficients are dimensionless; creep strains are reported in microstrain ($\times 10^{-6}$).

Concrete creep is the gradual increase in strain and deflection under sustained loading. The applied sustained load is unchanged, but concrete compression strain grows with time, increasing curvature and long-term deflection.

The immediate tab shows the beam in its cracked short-term state. The long-term tab shows the additional deflection caused by creep, with $\delta_{creep}$ representing the increase from immediate to long-term deflection.
"""
    )


def render_creep_summary(
    *,
    summary_values: Mapping[str, Any],
    bind_clicks,
) -> tuple[Mapping[str, Any], ...]:
    """Render the unchanged summary from already-published Creep values."""

    rows = build_creep_summary_rows(
        phi_cc_t=float(summary_values.get("phi_cc_t") or 0.0),
        phi_cc_star_table=float(
            summary_values.get("phi_cc_star_table") or 0.0
        ),
        eps_cc_micro=float(summary_values.get("eps_cc_micro") or 0.0),
    )
    render_clickable_summary_table(
        rows,
        key_prefix="creep_page_summary",
        columns=PARAMETRIC_RESULT_COLUMNS,
    )
    bind_clicks()
    return tuple(rows)


__all__ = ["render_creep_explainer", "render_creep_summary"]
