"""Coordination helpers for cases where multiple design families interact."""

from design_brain.engine import (
    _has_in_target_primary_refinement_candidate,
    _outside_target_evidence_allows_recommendation,
    _prefer_target_band_item,
)

__all__ = [
    "_has_in_target_primary_refinement_candidate",
    "_outside_target_evidence_allows_recommendation",
    "_prefer_target_band_item",
]
