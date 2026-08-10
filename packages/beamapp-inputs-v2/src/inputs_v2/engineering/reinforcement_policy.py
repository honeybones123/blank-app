"""Passive reinforcement preferences and diagnostics.

This module never classifies a Design Brain family, accepts a candidate, or
publishes an Apply action. The owning family supplies the permitted options and
retains all filtering and ranking authority.
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReinforcementPreferenceConfig:
    preferred_longitudinal_diameters: tuple[int, ...] = (20, 24)
    distribution_longitudinal_diameters: tuple[int, ...] = (16,)
    heavy_longitudinal_diameters: tuple[int, ...] = (28, 32)
    specialist_longitudinal_diameters: tuple[int, ...] = (36,)
    preferred_bars_per_layer_min: int = 4
    preferred_bars_per_layer_max: int = 6
    strong_low_ratio_trigger: float = 0.003
    normal_low_ratio_trigger: float = 0.005
    central_ratio_preference_min: float = 0.006
    central_ratio_preference_max: float = 0.008
    preferred_ratio_max: float = 0.010
    high_ratio_review: float = 0.015
    preferred_link_diameters: tuple[int, ...] = (10, 12)
    heavy_link_diameters: tuple[int, ...] = (16,)
    exceptional_link_diameters: tuple[int, ...] = (20,)
    normal_concrete_reduction_threshold: float = 0.05
    normal_reinforcement_increase_limit: float = 0.25
    substantial_concrete_reduction_threshold: float = 0.10


DEFAULT_REINFORCEMENT_PREFERENCES = ReinforcementPreferenceConfig()


def tension_ratio(as_provided_mm2: float, width_mm: float, effective_depth_mm: float) -> float:
    """Return rho_t as a diagnostic; zero geometry returns zero safely."""
    denominator = float(width_mm) * float(effective_depth_mm)
    return float(as_provided_mm2) / denominator if denominator > 0 else 0.0


def ratio_trigger(ratio: float, config: ReinforcementPreferenceConfig = DEFAULT_REINFORCEMENT_PREFERENCES) -> str | None:
    if ratio < config.strong_low_ratio_trigger:
        return "very_low_tension_reinforcement_ratio"
    if ratio < config.normal_low_ratio_trigger:
        return "low_tension_reinforcement_ratio"
    return None
