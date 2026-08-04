"""Pure runtime contracts for geometry/bottom compound recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RecommendationCompoundRuntime:
    annotate_bottom_deltas: Callable[..., None]
    arrangement_fits_state: Callable[..., bool]
    bottom_arrangement_updates: Callable[[dict], dict]
    compound_effective_signature: Callable[[dict, dict], tuple]
    compound_title: Callable[[str, str], str]
    candidate_state_updates: Callable[[dict, dict], dict]
    compound_signature_preview: Callable[[dict, dict], dict]
    evaluate_candidate_fast: Callable[..., dict | None]
    generate_bottom_arrangements: Callable[..., list[dict]]
    geometry_trial_axis: Callable[[dict, dict], str | None]
    practical_bottom_label: Callable[[int, int, int], str]
    select_geometry_seeds: Callable[..., list[dict]]
    updates_match_state: Callable[[dict, dict], bool]


__all__ = ["RecommendationCompoundRuntime"]
