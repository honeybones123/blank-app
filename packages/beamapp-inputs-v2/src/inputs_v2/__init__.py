"""Isolated Beamapp Inputs V2 proof."""

from .domain.beam_inputs import (
    ActionInputs,
    BeamInputs,
    BottomReinforcement,
    KvMethod,
    LayoutMode,
    MaterialInputs,
    ShearReinforcement,
    SupportInputs,
    TopReinforcement,
)

# Runtime checks this explicit shape version before loading the concrete
# Design Brain. Package metadata alone cannot prove that a wheel contains the
# current contract, so deployment also verifies the wheel's source manifest.
RUNTIME_DESIGN_BRAIN_CONTRACT_VERSION = 2

__all__ = [
    "ActionInputs",
    "BeamInputs",
    "BottomReinforcement",
    "KvMethod",
    "LayoutMode",
    "MaterialInputs",
    "RUNTIME_DESIGN_BRAIN_CONTRACT_VERSION",
    "ShearReinforcement",
    "SupportInputs",
    "TopReinforcement",
]
