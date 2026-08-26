"""Stress-field diagram and teaching presentation for the Shear page.

The authoritative MCFT values remain owned by the Shear calculation runtime.
This module only projects those values into the shared diagram shell and the
always-available teaching expander beneath it.
"""

from __future__ import annotations

from contextlib import nullcontext
from collections.abc import Callable
from typing import Any

import plotly.graph_objects as go

from shear_visuals import build_shear_behaviour_figure
from ui.diagrams.principal_stress_cue_diagram import (
    PRINCIPAL_STRESS_AXES_CUE_SCALE,
    build_principal_stress_axes_cue,
)


MCFT_ILLUSTRATION_DISCLAIMER = (
    "Illustrative only — schematic principal-stress-style field with optional "
    "strut-and-tie overlay, not a finite-element stress solution."
)
MCFT_STRESS_FIELD_CHART_KEY = "shear_behaviour_mcft_shell"


def render_mcft_display_options(st_module: Any) -> dict[str, bool]:
    """Render the existing presentation-only MCFT display controls."""

    st_module.caption("MCFT diagram display options")
    st_module.toggle(
        "Show strut-and-tie model",
        value=False,
        key="shear_show_stm_overlay",
    )
    st_module.toggle(
        "Show strut-and-tie flow",
        value=False,
        key="shear_show_stm_flow",
    )
    st_module.toggle(
        "Show load flow",
        value=False,
        key="shear_show_load_flow",
    )
    st_module.toggle(
        "Show cracks",
        value=True,
        key="shear_show_cracks",
    )
    st_module.toggle(
        "Show stress block",
        value=False,
        key="shear_show_stress_block",
    )
    return {
        "show_load_flow": bool(
            st_module.session_state.get("shear_show_load_flow", False)
        ),
        "show_cracks": bool(
            st_module.session_state.get("shear_show_cracks", True)
        ),
        "show_stress_block": bool(
            st_module.session_state.get("shear_show_stress_block", False)
        ),
        "show_stm_overlay": bool(
            st_module.session_state.get("shear_show_stm_overlay", False)
        ),
        "show_stm_flow": bool(
            st_module.session_state.get("shear_show_stm_flow", False)
        ),
    }


def build_mcft_stress_field_figure(
    *,
    theta_v_deg: float,
    options: dict[str, bool],
) -> tuple[go.Figure, bool]:
    """Build the existing MCFT visual from authoritative Shear evidence."""

    resolved_options = {
        "show_load_flow": bool(options.get("show_load_flow", False)),
        "show_cracks": bool(options.get("show_cracks", True)),
        "show_stress_block": bool(options.get("show_stress_block", False)),
        "show_stm_overlay": bool(options.get("show_stm_overlay", False)),
        "show_stm_flow": bool(options.get("show_stm_flow", False)),
    }
    figure = build_shear_behaviour_figure(
        visual_mode="Principal stress field",
        theta_v_deg=float(theta_v_deg),
        **resolved_options,
    )
    animated = bool(
        resolved_options["show_load_flow"] or resolved_options["show_stm_flow"]
    )
    return figure, animated


def render_mcft_stress_field_diagram(
    *,
    st_module: Any,
    theta_v_deg: float,
    render_plotly_diagram: Callable[..., Any],
    render_animated_plotly: Callable[..., Any],
    height_px: int,
) -> None:
    """Render MCFT inside the shared Shear diagram canvas."""

    figure, animated = build_mcft_stress_field_figure(
        theta_v_deg=theta_v_deg,
        options={
            "show_load_flow": bool(
                st_module.session_state.get("shear_show_load_flow", False)
            ),
            "show_cracks": bool(
                st_module.session_state.get("shear_show_cracks", True)
            ),
            "show_stress_block": bool(
                st_module.session_state.get("shear_show_stress_block", False)
            ),
            "show_stm_overlay": bool(
                st_module.session_state.get("shear_show_stm_overlay", False)
            ),
            "show_stm_flow": bool(
                st_module.session_state.get("shear_show_stm_flow", False)
            ),
        },
    )
    # Animated and static MCFT charts share the same viewport as the Shear
    # side view. The component owns its own frame, so reducing the Plotly
    # height here makes MCFT visibly shorter than the side view.
    plot_height_px = int(height_px)
    figure.update_layout(height=plot_height_px)
    if animated:
        render_animated_plotly(
            figure,
            height=plot_height_px,
            centered=True,
            chart_key=MCFT_STRESS_FIELD_CHART_KEY,
            compact_top=True,
            title_pad_t=8,
            max_width_px=1200,
        )
    else:
        render_plotly_diagram(
            figure,
            key=MCFT_STRESS_FIELD_CHART_KEY,
            title="MCFT stress field",
            center=True,
            config={"displayModeBar": False, "responsive": True},
        )


def render_stress_field_teaching(
    *,
    st_module: Any,
    theta_v_deg: float,
    render_centered_plotly: Callable[..., Any],
    body_only: bool = False,
) -> None:
    """Keep the established Stress Field lesson available for every view."""

    teaching_container = (
        nullcontext()
        if body_only
        else st_module.expander(
            "The Stress Field: Explaining the Modified Compression Field Theory and Strut-and-Tie Model"
        )
    )
    with teaching_container:
        st_module.markdown(
            r"""
The Modified Compression Field Theory (MCFT) and the strut-and-tie model (STM) are idealisations of the same underlying stress field. In this implementation, both use the same angle $\theta_v$ from the MCFT relationships (see Check 5), ensuring consistency between calculations and the visualised field.
            """
        )
        cue_col, note_col = st_module.columns([1, 1.5], gap="medium")
        with cue_col:
            render_centered_plotly(
                build_principal_stress_axes_cue(float(theta_v_deg)),
                chart_key="shear_principal_stress_axes_cue",
                max_width_px=int(540 * PRINCIPAL_STRESS_AXES_CUE_SCALE),
                height_px=int(190 * PRINCIPAL_STRESS_AXES_CUE_SCALE),
            )
        with note_col:
            st_module.markdown(
                r"""
The stress state resolves into principal directions where no shear acts on those planes (see [Mohr's circle](https://www.youtube.com/watch?v=_DH3546mSCM&msockid=3bf4b3e5318911f1b3cda493793b9b56)). Red trajectories show the principal compression $\sigma_1$, and blue trajectories show the principal tension $\sigma_2$.

The stress block diagrams represent a small element of the beam. The shear shown in Diagram (A) is a local stress component within the element and is not the same as the applied shear force $V^*$; the global shear $V^*$ is carried through the member by the combined action of the inclined compression field and associated tensile forces. In Diagram (A), shear is shown by forces acting parallel to the faces of the element, indicating the stresses are not aligned with the principal directions. The element is then rotated (Diagram (B)) to an orientation where the shear components are eliminated, corresponding to the transformation described by Mohr’s circle. In this orientation (Diagram (C)), only the principal stresses remain, shown as $\sigma_1$ (compression) and $\sigma_2$ (tension).

Within about one effective depth $d_v$ of supports, behaviour is a disturbed region (D-region), where stress flow is non-linear and idealised using a strut-and-tie model. The compression strut aligns with $\theta_v$.

Beyond this, in the flexural–shear region, stresses follow the rotating principal field. Cracks form approximately perpendicular to $\sigma_2$, with tensile forces carried by shear reinforcement and longitudinal reinforcement (dowel action).
                """
            )


__all__ = [
    "MCFT_ILLUSTRATION_DISCLAIMER",
    "MCFT_STRESS_FIELD_CHART_KEY",
    "build_mcft_stress_field_figure",
    "render_mcft_display_options",
    "render_mcft_stress_field_diagram",
    "render_stress_field_teaching",
]
