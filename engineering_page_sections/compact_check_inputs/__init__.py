"""Shared compact input panel for calculation pages."""

from .contract import CheckInputCategory, CheckInputPanelConfig, InputSource
from .renderer import (
    compact_check_input_columns,
    compact_check_input_regions,
    render_compact_check_inputs,
)
from .summaries import NOT_PROVIDED, format_dimensions, format_number, join_summary

__all__ = [
    "CheckInputCategory",
    "CheckInputPanelConfig",
    "InputSource",
    "compact_check_input_columns",
    "compact_check_input_regions",
    "render_compact_check_inputs",
    "NOT_PROVIDED",
    "format_dimensions",
    "format_number",
    "join_summary",
]
