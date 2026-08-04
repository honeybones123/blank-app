"""Inputs summary source and view-model extraction boundary."""

from .builders import build_inputs_summary_html, build_inputs_summary_view_model
from .models import (
    InputsSummaryCardSource,
    InputsSummarySectionViewModel,
    InputsSummarySourceSnapshot,
    SummaryCardViewModel,
)
from .render_coordinators import render_inputs_summary_expanders_and_tables_current_coordinator

__all__ = [
    "InputsSummaryCardSource",
    "InputsSummarySectionViewModel",
    "InputsSummarySourceSnapshot",
    "SummaryCardViewModel",
    "build_inputs_summary_html",
    "build_inputs_summary_view_model",
    "render_inputs_summary_expanders_and_tables_current_coordinator",
]
