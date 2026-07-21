"""Typed calculation/explainer view-model boundary for the Inputs page."""

from .builders import (
    build_inputs_calculation_explainer_source_hash,
    build_inputs_calculation_explainer_source_snapshot,
    build_inputs_calculation_explainer_view_model,
    stable_calculation_explainer_hash,
    stable_calculation_explainer_json,
)
from .models import (
    CalculationExplainerCardViewModel,
    CalculationExplainerRowViewModel,
    InputsCalculationExplainerSourceSnapshot,
    InputsCalculationExplainerSectionViewModel,
)
from .trace import render_inputs_calculation_explainer_trace

__all__ = [
    "CalculationExplainerCardViewModel",
    "CalculationExplainerRowViewModel",
    "InputsCalculationExplainerSourceSnapshot",
    "InputsCalculationExplainerSectionViewModel",
    "build_inputs_calculation_explainer_source_hash",
    "build_inputs_calculation_explainer_source_snapshot",
    "build_inputs_calculation_explainer_view_model",
    "render_inputs_calculation_explainer_trace",
    "stable_calculation_explainer_hash",
    "stable_calculation_explainer_json",
]
