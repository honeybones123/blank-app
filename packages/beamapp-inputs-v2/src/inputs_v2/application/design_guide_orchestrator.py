"""Single typed orchestration boundary for V2 Design Guide families."""

from __future__ import annotations

from dataclasses import dataclass

from inputs_v2.application.design_brain_families import DesignFamily, classify_design_family
from inputs_v2.application.design_brain_service import DesignBrainPreview, DesignBrainService
from inputs_v2.application.design_brain_decision import FamilyDecision
from inputs_v2.application.design_brain.family_owners import (
    DECISION_OWNERS,
)
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.application.design_brain.search_profile import SearchProfile


@dataclass(frozen=True, slots=True)
class DesignGuideDecision:
    family: DesignFamily
    preview: DesignBrainPreview
    evidence: dict[str, object]


class DesignGuideOrchestrator:
    """Classify once, then delegate to exactly one family-owned ladder."""

    def __init__(self, search_profile: SearchProfile | None = None) -> None:
        self._service = DesignBrainService(search_profile)

    @staticmethod
    def registered_families() -> tuple[DesignFamily, ...]:
        """Return every contract family handled by this boundary."""
        return tuple(DesignFamily)

    def decide(self, current: BeamInputs) -> FamilyDecision:
        result = self._service._calculator.calculate_current(current).result
        if result is None:
            raise ValueError("calculation result is stale")
        family = classify_design_family(result, current)
        owner = DECISION_OWNERS[family]
        return owner.decide(current, result, self._service)

    def preview(self, current: BeamInputs) -> DesignGuideDecision:
        """Compatibility wrapper retained while callers migrate to decide()."""
        decision = self.decide(current)
        preview = DesignBrainPreview(
            decision.candidate,
            decision.current_result,
            decision.proposed_result or decision.current_result,
            decision.changed_fields,
            decision.apply_allowed,
            decision.reason,
        )
        return DesignGuideDecision(decision.family, preview, {
            "family": decision.family.value,
            "source_revision": current.revision,
            "status": decision.status.value,
        })
