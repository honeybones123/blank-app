"""Target-band candidate normalisation and winner selection boundaries.

This module intentionally re-exports the existing implementation from
``design_brain.engine`` for the first architecture split. The behaviour remains
owned by the moved engine code; callers can migrate to this responsibility
module without changing payload shapes.
"""

from design_brain.engine import (
    _distance_to_band,
    _selection_sort_key,
    _target_band,
    _within_band,
    normalise_design_guide_candidate,
    select_target_band_winner,
)

__all__ = [
    "_distance_to_band",
    "_selection_sort_key",
    "_target_band",
    "_within_band",
    "normalise_design_guide_candidate",
    "select_target_band_winner",
]
