"""Underdesign repair boundaries for failed-check Design Guide states."""

from design_brain.engine import (
    _candidate_affects_family,
    _candidate_updates,
    _has_required_failure,
)

__all__ = [
    "_candidate_affects_family",
    "_candidate_updates",
    "_has_required_failure",
]
