"""Registry for dormant governing-family strategy shells."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from design_brain.families.base import GoverningFamilyStrategy
from design_brain.families.bending_cleanup import BendingCleanupFamily
from design_brain.families.bending_fail import BendingFailFamily
from design_brain.families.bending_fail_shear_overdesign import BendingFailShearOverdesignFamily
from design_brain.families.combined_bending_shear_fail import CombinedBendingShearFailFamily
from design_brain.families.combined_cleanup import CombinedCleanupFamily
from design_brain.families.exact_stop import ExactStopFamily
from design_brain.families.geometry_detailing import GeometryDetailingFamily
from design_brain.families.locked_no_repair import LockedNoRepairFamily
from design_brain.families.min_bending_reo import MinBendingReoFamily
from design_brain.families.min_shear_reo import MinShearReoFamily
from design_brain.families.serviceability import ServiceabilityFamily
from design_brain.families.shear_cleanup import ShearCleanupFamily
from design_brain.families.shear_fail import ShearFailFamily
from design_brain.families.shear_fail_bending_overdesign import ShearFailBendingOverdesignFamily
from design_brain.families.target_band import TargetBandFamily


GOVERNING_FAMILY_REGISTRY: Mapping[str, type[GoverningFamilyStrategy]] = MappingProxyType(
    {
        "BENDING_FAIL_GOVERNS": BendingFailFamily,
        "SHEAR_FAIL_GOVERNS": ShearFailFamily,
        "COMBINED_BENDING_SHEAR_FAIL": CombinedBendingShearFailFamily,
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": BendingFailShearOverdesignFamily,
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": ShearFailBendingOverdesignFamily,
        "BENDING_OVERDESIGN_GOVERNS": BendingCleanupFamily,
        "SHEAR_OVERDESIGN_GOVERNS": ShearCleanupFamily,
        "COMBINED_OVERDESIGN": CombinedCleanupFamily,
        "MIN_BENDING_REO_GOVERNS": MinBendingReoFamily,
        "MIN_SHEAR_REO_GOVERNS": MinShearReoFamily,
        "GEOMETRY_DETAILING_GOVERNS": GeometryDetailingFamily,
        "SERVICEABILITY_GOVERNS": ServiceabilityFamily,
        "LOCKED_NO_REPAIR": LockedNoRepairFamily,
        "TARGET_BAND_REACHED": TargetBandFamily,
        "EXACT_STOP_PROVEN": ExactStopFamily,
    }
)

GOVERNING_FAMILY_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "GEOMETRY_DETAILING_FAIL_GOVERNS": "GEOMETRY_DETAILING_GOVERNS",
        "GEOMETRY_GOVERNS_OPTIMISATION_STOP": "GEOMETRY_DETAILING_GOVERNS",
        "SPACING_DETAILING_GOVERNS_OPTIMISATION_STOP": "GEOMETRY_DETAILING_GOVERNS",
        "SERVICEABILITY_FAIL_GOVERNS": "SERVICEABILITY_GOVERNS",
        "SERVICEABILITY_GOVERNS_OPTIMISATION_STOP": "SERVICEABILITY_GOVERNS",
        "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    }
)


def normalise_governing_family(governing_state: str) -> str:
    key = str(governing_state or "").strip().upper()
    return GOVERNING_FAMILY_ALIASES.get(key, key)


def family_strategy_for(governing_state: str) -> GoverningFamilyStrategy | None:
    strategy_type = GOVERNING_FAMILY_REGISTRY.get(normalise_governing_family(governing_state))
    return strategy_type() if strategy_type is not None else None


__all__ = [
    "GOVERNING_FAMILY_ALIASES",
    "GOVERNING_FAMILY_REGISTRY",
    "family_strategy_for",
    "normalise_governing_family",
]
