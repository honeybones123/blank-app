"""Compatibility exports for application-owned candidate identity."""

from inputs_application.candidate_identity import (
    AUTO_DESIGN_CANDIDATE_KEY_TRACKED_FIELDS,
    candidate_cache_key,
    make_auto_design_candidate_key,
)


def _make_auto_design_candidate_key(state: dict) -> tuple:
    return make_auto_design_candidate_key(state)


def _candidate_cache_key(state: dict) -> tuple:
    return candidate_cache_key(state)


__all__ = [
    "AUTO_DESIGN_CANDIDATE_KEY_TRACKED_FIELDS",
    "_candidate_cache_key",
    "_make_auto_design_candidate_key",
]
