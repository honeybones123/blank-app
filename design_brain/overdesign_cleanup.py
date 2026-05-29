"""Overdesign and local-cleanup evidence boundaries."""

from design_brain.engine import (
    MATERIALLY_OVERPROVIDED_UTIL_THRESHOLD,
    _build_local_cleanup_evidence,
    _candidate_affects_material_family,
    _candidate_has_net_material_cleanup,
    _materially_overprovided_families,
    _summary_family_utils,
    _summary_governing_family,
)

__all__ = [
    "MATERIALLY_OVERPROVIDED_UTIL_THRESHOLD",
    "_build_local_cleanup_evidence",
    "_candidate_affects_material_family",
    "_candidate_has_net_material_cleanup",
    "_materially_overprovided_families",
    "_summary_family_utils",
    "_summary_governing_family",
]
