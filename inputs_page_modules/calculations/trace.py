"""Trace-only calculation/explainer coordinators for the Inputs page."""

from __future__ import annotations

from typing import Any

from .builders import (
    build_inputs_calculation_explainer_source_hash,
    build_inputs_calculation_explainer_source_snapshot,
    build_inputs_calculation_explainer_view_model,
)


def render_inputs_calculation_explainer_trace(
    *,
    st_module: Any,
    BENDING_ROWS,
    SHEAR_ROWS,
    CRACK_ROWS,
    DEFLECTION_ROWS,
    results_version: int,
    summary_action_fp,
    trace_fn,
) -> None:
    source_snapshot = build_inputs_calculation_explainer_source_snapshot(
        bending_rows=BENDING_ROWS,
        shear_rows=SHEAR_ROWS,
        crack_rows=CRACK_ROWS,
        deflection_rows=DEFLECTION_ROWS,
        run_state={
            "results_version": results_version,
            "summary_action_fp": summary_action_fp,
        },
    )
    source_hash = build_inputs_calculation_explainer_source_hash(source_snapshot)
    view_model = build_inputs_calculation_explainer_view_model(source_snapshot)
    source_row_counts = {
        "bending": len(BENDING_ROWS or []),
        "shear": len(SHEAR_ROWS or []),
        "crack": len(CRACK_ROWS or []),
        "deflection": len(DEFLECTION_ROWS or []),
    }
    extracted_row_counts = {
        card.check_id: len(card.rows)
        for card in view_model.cards
    }
    trace_payload = {
        "calculation_explainer_view_model_trace_attempted": True,
        "calculation_explainer_view_model_trace_built": True,
        "calculation_explainer_view_model_trace_only": True,
        "calculation_explainer_view_model_trace_source": "inputs_page_modules.calculations",
        "temporary_wrapper_classification": "THIN_WRAPPER_KEEP_TEMPORARILY",
        "live_calculation_explainer_renderer_cutover": False,
        "calculation_explainer_source_hash": source_hash,
        "live_calculation_explainer_source_row_counts": source_row_counts,
        "extracted_calculation_explainer_row_counts": extracted_row_counts,
        "extracted_calculation_explainer_card_count": len(view_model.cards),
        "extracted_calculation_explainer_card_order": [
            card.check_id for card in view_model.cards
        ],
        "extracted_calculation_explainer_view_model_hash": view_model.display_hash,
    }
    st_module.session_state["_inputs_calculation_explainer_view_model_trace"] = trace_payload
    trace_fn("inputs_calculation_explainer_view_model_trace", **trace_payload)


__all__ = ["render_inputs_calculation_explainer_trace"]
