"""Isolated Beamapp Inputs V2 proof."""

from .domain.beam_inputs import (
    ActionInputs,
    BeamInputs,
    BottomReinforcement,
    LayoutMode,
    MaterialInputs,
    ShearReinforcement,
    SupportInputs,
    TopReinforcement,
)

# Runtime checks this explicit shape version before loading the concrete
# Design Brain.  Distribution version 0.1.0 has intentionally remained stable
# during the migration, so package metadata alone cannot detect an older wheel
# with an incompatible FamilyDecision contract.
RUNTIME_DESIGN_BRAIN_CONTRACT_VERSION = 2

__all__ = [
    "ActionInputs",
    "BeamInputs",
    "BottomReinforcement",
    "LayoutMode",
    "MaterialInputs",
    "RUNTIME_DESIGN_BRAIN_CONTRACT_VERSION",
    "ShearReinforcement",
    "SupportInputs",
    "TopReinforcement",
]
