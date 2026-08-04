"""Application-owned identity for the family-classification contract.

Page/runtime code only needs the contract version when it builds an input
transaction or publication fingerprint.  Keeping that identity here prevents
those consumers from importing the selected Design Brain implementation.  The
full family rules remain owned by the selected Design Brain until the new Brain
supplies its neutral classification contract.
"""

from __future__ import annotations

from typing import Any


FAMILY_CLASSIFICATION_CONTRACT_VERSION = "family_classification.v3"


def load_family_classification_contract() -> dict[str, Any]:
    """Return the application-owned identity needed by page fingerprints."""

    return {
        "contract_identity": {
            "contract_version": FAMILY_CLASSIFICATION_CONTRACT_VERSION,
        }
    }


__all__ = [
    "FAMILY_CLASSIFICATION_CONTRACT_VERSION",
    "load_family_classification_contract",
]
