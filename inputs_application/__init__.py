"""Typed replacement boundary for the Inputs page application runtime.

The package keeps its public exports, but loads adapter/runtime modules lazily.
This allows pure state and contract modules to be imported without eagerly
starting Streamlit or the legacy state bootstrap.
"""

from importlib import import_module

from inputs_application.contracts import (
    InputsApplyCommand,
    InputsEngineeringResult,
    InputsPageRequest,
    InputsPageResult,
    InputsPublicationResult,
    InputsSessionMutation,
)

_LAZY_EXPORTS = {
    "InputsApplicationPorts": ("inputs_application.runtime", "InputsApplicationPorts"),
    "run_inputs_transaction": ("inputs_application.runtime", "run_inputs_transaction"),
    "AuthoritativeDesignGuidePort": ("inputs_application.adapters", "AuthoritativeDesignGuidePort"),
    "CanonicalRecommendationApplyPort": ("inputs_application.adapters", "CanonicalRecommendationApplyPort"),
    "CallableApplyPort": ("inputs_application.adapters", "CallableApplyPort"),
    "CallableDesignGuidePort": ("inputs_application.adapters", "CallableDesignGuidePort"),
    "MappingSessionPort": ("inputs_application.adapters", "MappingSessionPort"),
    "ResolvedStateEngineeringPort": ("inputs_application.adapters", "ResolvedStateEngineeringPort"),
    "SharedStateSessionPort": ("inputs_application.adapters", "SharedStateSessionPort"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value

__all__ = [
    "InputsApplicationPorts",
    "AuthoritativeDesignGuidePort",
    "CanonicalRecommendationApplyPort",
    "CallableApplyPort",
    "CallableDesignGuidePort",
    "InputsApplyCommand",
    "InputsEngineeringResult",
    "InputsPageRequest",
    "InputsPageResult",
    "InputsPublicationResult",
    "MappingSessionPort",
    "ResolvedStateEngineeringPort",
    "SharedStateSessionPort",
    "InputsSessionMutation",
    "run_inputs_transaction",
]
