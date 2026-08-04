"""Application-owned identity for the family-classification contract.

Page/runtime code only needs the contract version when it builds an input
transaction or publication fingerprint.  Keeping that identity here prevents
those consumers from importing the selected Design Brain implementation.  The
full family rules remain owned by the selected Design Brain until the new Brain
supplies its neutral classification contract.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any


FAMILY_CLASSIFICATION_CONTRACT_VERSION = "family_classification.v3"

GOVERNING_FAMILY_ALIASES = MappingProxyType(
    {
        "GEOMETRY_DETAILING_FAIL_GOVERNS": "GEOMETRY_DETAILING_GOVERNS",
        "GEOMETRY_GOVERNS_OPTIMISATION_STOP": "GEOMETRY_DETAILING_GOVERNS",
        "SPACING_DETAILING_GOVERNS_OPTIMISATION_STOP": "GEOMETRY_DETAILING_GOVERNS",
        "SERVICEABILITY_FAIL_GOVERNS": "SERVICEABILITY_GOVERNS",
        "SERVICEABILITY_GOVERNS_OPTIMISATION_STOP": "SERVICEABILITY_GOVERNS",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS": "COMBINED_BENDING_SHEAR_FAIL",
        "COMBINED_OVERDESIGN_GOVERNS": "COMBINED_OVERDESIGN",
        "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    }
)


def normalise_governing_family(governing_state: str) -> str:
    """Normalize a family alias without importing a family strategy registry."""

    key = str(governing_state or "").strip().upper()
    return GOVERNING_FAMILY_ALIASES.get(key, key)


def load_family_classification_contract() -> dict[str, Any]:
    """Return the application-owned identity needed by page fingerprints."""

    return {
        "contract_identity": {
            "contract_version": FAMILY_CLASSIFICATION_CONTRACT_VERSION,
        }
    }


__all__ = [
    "FAMILY_CLASSIFICATION_CONTRACT_VERSION",
    "GOVERNING_FAMILY_ALIASES",
    "load_family_classification_contract",
    "normalise_governing_family",
]
