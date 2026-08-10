"""Pure reinforcement-ratio diagnostics using the one preference profile."""

from inputs_v2.domain.design_preferences import (
    DEFAULT_DESIGN_PREFERENCES,
    DesignPreferenceProfile,
)


def tension_ratio(as_provided_mm2: float, width_mm: float, effective_depth_mm: float) -> float:
    """Return rho_t as a diagnostic; zero geometry returns zero safely."""
    denominator = float(width_mm) * float(effective_depth_mm)
    return float(as_provided_mm2) / denominator if denominator > 0 else 0.0


def ratio_trigger(
    ratio: float,
    config: DesignPreferenceProfile = DEFAULT_DESIGN_PREFERENCES,
) -> str | None:
    if ratio < config.strong_low_ratio_trigger:
        return "very_low_tension_reinforcement_ratio"
    if ratio < config.normal_low_ratio_trigger:
        return "low_tension_reinforcement_ratio"
    return None


__all__ = ["ratio_trigger", "tension_ratio"]
