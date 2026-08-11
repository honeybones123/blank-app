"""Family-owner protocol. Owners select one ladder and no other family."""

from __future__ import annotations

from typing import Protocol

from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.application.design_brain_decision import FamilyDecision
from inputs_v2.application.design_brain.family_context import FamilyRunContext


class FamilyOwner(Protocol):
    def validates_entry(self, context: FamilyRunContext) -> bool: ...

    def decide(
        self,
        context: FamilyRunContext,
        service: DesignBrainService,
    ) -> FamilyDecision: ...
