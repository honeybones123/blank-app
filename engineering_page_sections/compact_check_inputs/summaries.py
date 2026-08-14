"""Formatting helpers for compact input summaries.

These helpers are deliberately presentation-only.  They never provide an
engineering default: a missing value is rendered as ``Not provided``.
"""

from __future__ import annotations

from typing import Any


NOT_PROVIDED = "Not provided"


def format_number(value: Any, unit: str, *, decimals: int = 0) -> str:
    if value is None or value == "":
        return NOT_PROVIDED
    try:
        number = float(value)
    except (TypeError, ValueError):
        return NOT_PROVIDED
    return f"{number:.{decimals}f} {unit}".strip()


def format_dimensions(width: Any, depth: Any) -> str:
    if width is None or depth is None or width == "" or depth == "":
        return NOT_PROVIDED
    try:
        return f"{float(width):.0f} × {float(depth):.0f} mm"
    except (TypeError, ValueError):
        return NOT_PROVIDED


def join_summary(*parts: str) -> str:
    return " · ".join(part for part in parts if part)


__all__ = ["NOT_PROVIDED", "format_dimensions", "format_number", "join_summary"]
