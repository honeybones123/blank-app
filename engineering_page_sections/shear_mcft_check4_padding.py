"""Presentation-only vertical padding for the MCFT Check 4 diagrams."""

from __future__ import annotations


MCFT_CHECK4_VERTICAL_PAD = 0.18


def install_mcft_check4_vertical_padding() -> None:
    """Give the shared MCFT Check 4 beam-face sketch more top/bottom headroom."""
    from ui.diagrams import mcft_diagram

    mcft_diagram.MCFT_CHECK4_Y_PAD = MCFT_CHECK4_VERTICAL_PAD


__all__ = [
    "MCFT_CHECK4_VERTICAL_PAD",
    "install_mcft_check4_vertical_padding",
]
