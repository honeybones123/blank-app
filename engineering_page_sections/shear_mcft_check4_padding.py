"""Presentation-only vertical framing for the MCFT Check 4 diagrams."""

from __future__ import annotations


# Keep only a small axis-space buffer around the full-depth beam-face line.
# Larger values shrink the visible line inside a fixed-height Plotly shell.
MCFT_CHECK4_VERTICAL_PAD = 0.06


def install_mcft_check4_vertical_padding() -> None:
    """Give MCFT Check 4 enough clearance without visually shortening the section."""
    from ui.diagrams import mcft_diagram

    mcft_diagram.MCFT_CHECK4_Y_PAD = MCFT_CHECK4_VERTICAL_PAD


__all__ = [
    "MCFT_CHECK4_VERTICAL_PAD",
    "install_mcft_check4_vertical_padding",
]
