"""Crack Control summary and method-aware teaching presentation."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from application.contracts.concrete_crack_shrinkage import CrackControlMethod
from ui_seamless_steps import bind_summary_clicks, render_clickable_summary_table
from widgets_helpers import render_page_explainer_expander


def render_crack_explainer(st_module: Any, method: str) -> None:
    if method == CrackControlMethod.AS5100_WALL.value:
        st_module.markdown(
            "AS 5100.5:2017 Clause 11.7.2 restrained-wall horizontal "
            "reinforcement check. Strength and Clause 11.7.1 remain separate "
            "design gates."
        )
        return
    if method == CrackControlMethod.CIRIA_C766_EC2.value:
        st_module.markdown(
            "CIRIA C766 / EC2 restrained-deformation equation path. "
            "Temperature changes and restraint factors are explicit designer "
            "inputs; corrected spreadsheet parity is not claimed."
        )
        return
    st_module.markdown(
        """
This page checks flexural crack control in reinforced concrete beams in accordance with **AS 3600:2018 Clause 8.6.2**, using:

- **Table method (no direct crack width)** — limiting steel stress from Tables 8.6.2.2(A)–(B)
- **Direct crack-width calculation** — per Clause 8.6.2.3:
"""
    )
    st_module.latex(
        r"w = s_{r,\max}\left(\varepsilon_{sm}-\varepsilon_{cm}\right)\le w'_{\max}"
    )
    st_module.markdown(
        """
The aim is to verify that cracking is **controlled** so that durability and appearance are not impaired.

You can:

- **See behaviour (cracks)** in the side-view diagram once results are available
- **Inspect cause (moment)** in the moment diagram—SLS bending moment, using the same cached data as Beam Actions when that page has been run
"""
    )


def render_crack_summary(
    st_module: Any,
    *,
    method: str,
    rows: Sequence[Mapping[str, Any]],
    key_prefix: str,
    set_step_open: Callable[[str], None],
) -> None:
    clicked_uid = render_clickable_summary_table(
        [dict(row) for row in rows], key_prefix=key_prefix
    )
    if clicked_uid:
        set_step_open(str(clicked_uid))
    bind_summary_clicks()
    render_page_explainer_expander(
        lambda: render_crack_explainer(st_module, method)
    )


__all__ = ["render_crack_explainer", "render_crack_summary"]
