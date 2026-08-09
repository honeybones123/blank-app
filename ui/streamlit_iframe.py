"""Supported Streamlit iframe boundary for trusted application HTML."""

from __future__ import annotations

from typing import Any


_NO_SCROLL_STYLE = (
    "<style>html,body{overflow:hidden!important;scrollbar-width:none!important;}"
    "body::-webkit-scrollbar{display:none!important;}</style>"
)


def render_trusted_iframe(
    st_module: Any,
    body: str,
    *,
    height: int | str,
    scrolling: bool = False,
    width: int | str = "stretch",
) -> Any:
    """Render app-owned HTML while preserving the former scroll contract."""

    content = str(body)
    if not scrolling:
        content = _NO_SCROLL_STYLE + content
    resolved_width = 1 if isinstance(width, int) and width <= 0 else width
    resolved_height = 1 if isinstance(height, int) and height <= 0 else height
    return st_module.iframe(
        content,
        width=resolved_width,
        height=resolved_height,
    )


__all__ = ["render_trusted_iframe"]
