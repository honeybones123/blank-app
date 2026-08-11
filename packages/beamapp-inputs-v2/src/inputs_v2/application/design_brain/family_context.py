"""Typed context passed to exactly one selected Design Brain family."""

from dataclasses import dataclass

from inputs_v2.application.design_brain.search_profile import SearchProfile
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.design_preferences import DesignPreferenceProfile
from inputs_v2.domain.engineering_result import EngineeringResult


@dataclass(frozen=True, slots=True)
class FamilyRunContext:
    current: BeamInputs
    current_result: EngineeringResult
    preferences: DesignPreferenceProfile
    search_profile: SearchProfile


__all__ = ["FamilyRunContext"]
