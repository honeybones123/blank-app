"""Typed Calculation section owner for the Inputs workspace."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from inputs_page_modules.calculations import (
    render_inputs_calculation_explainer_trace,
)
from inputs_page_modules.summaries.pipeline import (
    InputsSummaryCalculationSource,
)


def render_inputs_calculation_fragment_current_coordinator(
    *,
    summary_source: InputsSummaryCalculationSource,
    trace_fn: Callable[..., Any],
) -> None:
    """Build Calculation trace state from the completed Summary snapshot."""

    if not isinstance(summary_source, InputsSummaryCalculationSource):
        raise TypeError(
            "summary_source must be an InputsSummaryCalculationSource"
        )
    render_inputs_calculation_explainer_trace(
        st_module=st,
        BENDING_ROWS=summary_source.bending_rows,
        SHEAR_ROWS=summary_source.shear_rows,
        CRACK_ROWS=summary_source.crack_rows,
        DEFLECTION_ROWS=summary_source.deflection_rows,
        results_version=summary_source.results_version,
        summary_action_fp=summary_source.summary_action_fp,
        trace_fn=trace_fn,
    )


__all__ = ["render_inputs_calculation_fragment_current_coordinator"]
