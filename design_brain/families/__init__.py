"""Stable family strategy types.

Registry access intentionally lives in :mod:`design_brain.families.registry`.
Keeping the package initializer independent prevents every family import from
eagerly loading the registry and recursively importing the family package.
"""

from design_brain.families.base import (
    DiagnosticFamilyStrategy,
    FamilyStrategyContext,
    FamilyStrategyMetadata,
    GoverningFamilyStrategy,
)
__all__ = [
    "DiagnosticFamilyStrategy",
    "FamilyStrategyContext",
    "FamilyStrategyMetadata",
    "GoverningFamilyStrategy",
]
