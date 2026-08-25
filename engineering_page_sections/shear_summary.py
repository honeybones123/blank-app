"""Shear engineering-summary and page-explainer presentation boundary."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Mapping

from engineering_page_sections.shear_page_context import ShearPageSnapshot
from ui.summary_rows import (
    build_shear_clickable_summary_rows,
    build_shear_legacy_summary_rows,
    filter_shear_summary_rows,
)
from ui_seamless_steps import render_clickable_summary_table


@dataclass(frozen=True, slots=True)
class ShearSummaryResult:
    legacy_rows: tuple[Mapping[str, Any], ...]
    published_rows: tuple[Mapping[str, Any], ...]
    summary_utilisation: float


def render_shear_explainer(
    st_module,
    *,
    safe_image: Callable[..., None],
    info_button: Callable[..., Any],
    calc_box: Callable[[str], None],
) -> None:
    """Render the existing Shear page explainer without runtime globals."""

    col_left, col_right = st_module.columns([1, 1])

    with col_left:
        st_module.markdown(
            r"""
This page computes **ultimate shear and torsion capacity** outputs in accordance with **AS 3600:2018** using the MCFT-based shear method, and reports the governing utilisation checks.

- **Design shear capacity**
  $ \phi V_{uc} = \phi(V_c + V_s) $, used for the governing shear strength check.

- **Concrete shear contribution (MCFT)**
  $ V_c = k_v \cdot b_v \cdot d_v \cdot \sqrt{f'_c} $, depends on $\varepsilon_x$ and $\theta_v$.

- **Torsion and interaction (when applicable)**
  $ V_{eq}^* = \sqrt{(V^*)^2 + V_{t,eq}^2} $, used for combined shear–torsion checks.

### When to use each method

Use the **simplified method** for typical non-prestressed reinforced concrete beams when the **AS 3600** simplified-method conditions are satisfied.

Use the **general method** when those limits are not met, or when a more rigorous shear check is needed.

The simplified route is for **ordinary beams only** where the standard conditions apply—for example a **non-prestressed** member, **no applied axial tension**, and the **ordinary material and property limits** the code requires for that method.

### Why

The simplified method is a **faster** standard check that uses **fixed code assumptions** (the MCFT-style simplification permitted for qualifying beams).

The general method is **more detailed** because it **calculates shear parameters from the actual section actions and response**. That makes it more suitable when effects such as **axial force**, **torsion**, or other **non-standard conditions** are important.

In short:

- **Simplified** — quicker, standard code-permitted beam check when conditions are met.
- **General** — more detailed, action-sensitive check.
        """
        )

    with col_right:
        _spacer_col, img_col, info_col = st_module.columns([1, 5, 1])

        with img_col:
            st_module.markdown(
                "<div style='text-align:center;'>",
                unsafe_allow_html=True,
            )
            safe_image(
                "assets/shear_flexural_cracks_dv.png",
                caption=None,
                width=396,
            )
            st_module.markdown("</div>", unsafe_allow_html=True)

        with info_col:
            with info_button(use_container_width=True):
                calc_box(
                    r"""
**What is shear in a beam?**






- Shear forces act **perpendicular to the beam axis**.

- You can picture shear as a stack of playing cards where layers **try to slide** past each other.

- In a beam, one part of the cross-section wants to slide relative to the next, creating **internal shear stresses**.






**Critical section for shear – $d_v$**






- The design shear check is taken at a distance **$d_v$ from the face of the support**.

- At this section we take the **design shear $V^{\ast}$**, ignoring any distributed load between the support and $d_v$.

- If significant concentrated loads fall inside this region, the behaviour is closer to a **strut-and-tie / deep beam** and a STM model is required.

- AS 3600 defines effective shear depth



  $$d_v = \max\left(0.72D,\;0.9d_0\right)$$



  where $d_0$ is the depth to the centroid of the **tension reinforcement** in the tensile zone.

"""
                )


def render_shear_summary(
    page_snapshot: ShearPageSnapshot,
    *,
    publish_summary: Callable[[float, float], None],
    publish_rows: Callable[[list[dict[str, Any]]], None],
    bind_clicks: Callable[[], None],
    render_explainer_expander: Callable[[Callable[[], None]], None],
    render_explainer: Callable[[], None],
) -> ShearSummaryResult:
    """Render the canonical Shear summary in its established order."""

    legacy_rows = build_shear_legacy_summary_rows(
        page_snapshot.check_pack.get("rows") or []
    )
    summary_util_raw = page_snapshot.check_pack.get("summary_util")
    try:
        summary_utilisation = float(summary_util_raw)
    except (TypeError, ValueError):
        summary_utilisation = math.nan

    publish_summary(
        float(page_snapshot.check_pack.get("summary_phiVu_kN") or 0.0),
        (
            float(summary_utilisation)
            if not math.isnan(summary_utilisation)
            else 0.0
        ),
    )
    published_rows = build_shear_clickable_summary_rows(legacy_rows)
    publish_rows(published_rows)
    display_rows = filter_shear_summary_rows(legacy_rows)
    render_clickable_summary_table(
        build_shear_clickable_summary_rows(display_rows),
        key_prefix="shear_summary",
    )
    bind_clicks()
    render_explainer_expander(render_explainer)
    return ShearSummaryResult(
        legacy_rows=tuple(legacy_rows),
        published_rows=tuple(published_rows),
        summary_utilisation=summary_utilisation,
    )


__all__ = [
    "ShearSummaryResult",
    "render_shear_explainer",
    "render_shear_summary",
]
