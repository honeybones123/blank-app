"""Immutable, non-authoritative engineering design preferences."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OptimisationMode(StrEnum):
    """Project preference mode interpreted only by the selected family."""

    STANDARD_BUILDABLE = "standard_buildable"


@dataclass(frozen=True, slots=True)
class DesignPreferenceProfile:
    """Passive preference values; this type contains no decision methods."""

    preference_profile_id: str = "beamapp-standard-buildable"
    preference_profile_version: str = "1.0.0"
    optimisation_mode: OptimisationMode = OptimisationMode.STANDARD_BUILDABLE
    dimension_increment_mm: float = 25.0
    preferred_longitudinal_diameters: tuple[int, ...] = (20, 24)
    distribution_longitudinal_diameters: tuple[int, ...] = (16,)
    heavy_longitudinal_diameters: tuple[int, ...] = (28, 32)
    specialist_longitudinal_diameters: tuple[int, ...] = (36,)
    preferred_bars_per_layer_min: int = 4
    preferred_bars_per_layer_max: int = 6
    preferred_layer_counts: tuple[int, ...] = (1, 2)
    strong_low_ratio_trigger: float = 0.003
    normal_low_ratio_trigger: float = 0.005
    central_ratio_preference_min: float = 0.006
    central_ratio_preference_max: float = 0.008
    preferred_ratio_max: float = 0.010
    high_ratio_review: float = 0.015
    preferred_link_diameters: tuple[int, ...] = (10, 12)
    heavy_link_diameters: tuple[int, ...] = (16,)
    exceptional_link_diameters: tuple[int, ...] = (20,)
    standard_link_spacings_mm: tuple[float, ...] = (
        100.0,
        125.0,
        150.0,
        175.0,
        200.0,
        250.0,
        300.0,
        400.0,
        500.0,
        600.0,
    )
    soft_congestion_moderate_penalty: float = 0.25
    soft_congestion_high_penalty: float = 0.75
    normal_concrete_reduction_threshold: float = 0.05
    normal_reinforcement_increase_limit: float = 0.25
    substantial_concrete_reduction_threshold: float = 0.10

    def __post_init__(self) -> None:
        if not self.preference_profile_id.strip():
            raise ValueError("preference_profile_id is required")
        if not self.preference_profile_version.strip():
            raise ValueError("preference_profile_version is required")
        if self.dimension_increment_mm <= 0.0:
            raise ValueError("dimension_increment_mm must be positive")
        if self.preferred_bars_per_layer_min < 2:
            raise ValueError("preferred_bars_per_layer_min must be at least two")
        if self.preferred_bars_per_layer_max < self.preferred_bars_per_layer_min:
            raise ValueError("preferred bar-count range is invalid")
        if not self.preferred_layer_counts or any(
            count not in {1, 2} for count in self.preferred_layer_counts
        ):
            raise ValueError("preferred_layer_counts must contain one or two layers")
        if tuple(sorted(set(self.standard_link_spacings_mm))) != self.standard_link_spacings_mm:
            raise ValueError("standard_link_spacings_mm must be unique and ascending")


DEFAULT_DESIGN_PREFERENCES = DesignPreferenceProfile()


__all__ = [
    "DEFAULT_DESIGN_PREFERENCES",
    "DesignPreferenceProfile",
    "OptimisationMode",
]
