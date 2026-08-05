"""Neutral compatibility surface for retired page recommendation helpers.

The V2 Design Brain publication is the sole recommendation authority.  These
callables remain import-compatible for extracted page coordinators but do not
load or execute the removed V1 recommendation graph.
"""

from __future__ import annotations

from typing import Any, Mapping


def compute_geometry_recommendation_for_page(state: dict, *, session_state: Mapping[str, Any]) -> None:
    del state, session_state
    return None


def compute_shear_recommendation_for_page(state: dict, *, session_state: Mapping[str, Any]) -> None:
    del state, session_state
    return None


def compute_bottom_recommendation_for_page(state: dict, *, session_state: Mapping[str, Any]) -> None:
    del state, session_state
    return None


__all__ = [
    "compute_bottom_recommendation_for_page",
    "compute_geometry_recommendation_for_page",
    "compute_shear_recommendation_for_page",
]
