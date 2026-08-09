"""Family-owner protocol. Owners select one ladder and no other family."""

from __future__ import annotations

from typing import Protocol

from inputs_v2.application.design_brain_service import DesignBrainPreview, DesignBrainService
from inputs_v2.domain.beam_inputs import BeamInputs


class FamilyOwner(Protocol):
    def preview(self, current: BeamInputs, service: DesignBrainService) -> DesignBrainPreview: ...
