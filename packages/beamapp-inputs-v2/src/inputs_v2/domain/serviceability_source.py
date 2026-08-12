"""Authoritative provenance for serviceability actions.

The provisional ULS-ratio source is reserved for private Design Brain
candidate evaluation.  It must never be written into ordinary calculations,
user inputs, saved load data or exported action data.
"""

from __future__ import annotations

from enum import StrEnum


class ServiceabilityActionSource(StrEnum):
    NOT_PROVIDED = "NOT_PROVIDED"
    ACTUAL_SLS_ACTIONS = "ACTUAL_SLS_ACTIONS"
    PROVISIONAL_ULS_RATIO_PROXY = "PROVISIONAL_ULS_RATIO_PROXY"


__all__ = ["ServiceabilityActionSource"]
