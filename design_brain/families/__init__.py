"""Dormant family-owned strategy shells for staged Design Brain routing."""

from design_brain.families.base import (
    DiagnosticFamilyStrategy,
    FamilyStrategyContext,
    FamilyStrategyMetadata,
    GoverningFamilyStrategy,
)
from design_brain.families.registry import (
    GOVERNING_FAMILY_ALIASES,
    GOVERNING_FAMILY_REGISTRY,
    family_strategy_for,
    normalise_governing_family,
)

__all__ = [
    "DiagnosticFamilyStrategy",
    "FamilyStrategyContext",
    "FamilyStrategyMetadata",
    "GOVERNING_FAMILY_ALIASES",
    "GOVERNING_FAMILY_REGISTRY",
    "GoverningFamilyStrategy",
    "family_strategy_for",
    "normalise_governing_family",
]
