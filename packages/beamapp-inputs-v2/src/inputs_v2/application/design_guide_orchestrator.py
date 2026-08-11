"""Single typed orchestration boundary for V2 Design Guide families."""

from __future__ import annotations

from dataclasses import dataclass

from inputs_v2.application.design_brain_families import (
    DesignFamily,
    FamilyClassification,
    classify_design_family_selection,
)
from inputs_v2.application.design_brain_service import DesignBrainPreview, DesignBrainService
from inputs_v2.application.design_brain_decision import FamilyDecision
from inputs_v2.application.design_brain.family_owners import (
    DECISION_OWNERS,
)
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.application.design_brain.search_profile import SearchProfile
from inputs_v2.application.design_brain.family_context import FamilyRunContext
from inputs_v2.domain.design_preferences import (
    DEFAULT_DESIGN_PREFERENCES,
    DesignPreferenceProfile,
)


@dataclass(frozen=True, slots=True)
class DesignGuideDecision:
    family: DesignFamily
    preview: DesignBrainPreview
    evidence: dict[str, object]


class DesignGuideOrchestrator:
    """Classify once, then delegate to exactly one family-owned ladder."""

    def __init__(
        self,
        search_profile: SearchProfile | None = None,
        preference_profile: DesignPreferenceProfile | None = None,
    ) -> None:
        self._search_profile = search_profile or SearchProfile()
        self._preference_profile = preference_profile or DEFAULT_DESIGN_PREFERENCES
        self._service = DesignBrainService(
            self._search_profile,
            self._preference_profile,
        )

    @staticmethod
    def registered_families() -> tuple[DesignFamily, ...]:
        """Return every contract family handled by this boundary."""
        return tuple(DesignFamily)

    def decide(self, current: BeamInputs) -> FamilyDecision:
        result = self._service._calculator.calculate_current(current).result
        if result is None:
            raise ValueError("calculation result is stale")
        classification = classify_design_family_selection(result, current)
        family = classification.selected_family
        owner = DECISION_OWNERS[family]
        context = FamilyRunContext(
            current=current,
            current_result=result,
            classification=classification,
            preferences=self._preference_profile,
            search_profile=self._search_profile,
        )
        if not owner.validates_entry(context):
            classification = FamilyClassification(
                selected_family=DesignFamily.ENGINEERING_REVIEW_REQUIRED,
                selected_entry_condition_id="selected_family_entry_validation_failed",
                matched_families=classification.matched_families,
                signals=classification.signals,
                reason_code="selected_family_entry_validation_failed",
            )
            owner = DECISION_OWNERS[DesignFamily.ENGINEERING_REVIEW_REQUIRED]
            context = FamilyRunContext(
                current=current,
                current_result=result,
                classification=classification,
                preferences=self._preference_profile,
                search_profile=self._search_profile,
            )
        return owner.decide(context, self._service)

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
