"""
User-facing strain diagram convention (AS 3600–aligned):

  - Compression: ε < 0 → plotted to the LEFT of the ε = 0 (beam-face) axis.
  - Tension:     ε > 0 → plotted to the RIGHT.

Solver outputs and internal bending diagram code may use a legacy layout convention
(compression strains positive, tension negative) for plane-sections geometry.
Use bending_internal_strain_to_display() only for **drawing** positions and numeric
labels; do not alter stored calculation results.
"""

from __future__ import annotations


def bending_internal_strain_to_display(eps_internal: float) -> float:
    """Map bending strain-panel internal ε (compression +, tension −) → display ε (compression −, tension +)."""
    return -float(eps_internal)


def strain_display_to_panel_x(
    eps_display: float,
    *,
    panel_x_center: float,
    half_w: float,
    eps_scale_max: float,
) -> float:
    """Linear map display strain → horizontal position in normalized panel coordinates."""
    denom = float(eps_scale_max) if abs(float(eps_scale_max)) > 1e-12 else 1e-12
    return float(panel_x_center) + (float(eps_display) / denom) * float(half_w)


def strain_color_display(eps_display: float) -> str:
    """Red for compression (ε < 0), blue for tension (ε > 0)."""
    return "red" if float(eps_display) < 0.0 else "blue"


def strain_label_anchor_display(
    eps_display: float,
    x_at: float,
    *,
    offset: float = 0.02,
) -> tuple[float, str]:
    """Annotation (x, xanchor) for a horizontal strain tick (offset in same units as x_at)."""
    if float(eps_display) < 0.0:
        return float(x_at) - float(offset), "right"
    return float(x_at) + float(offset), "left"
