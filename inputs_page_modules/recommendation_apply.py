"""Recommendation apply wrappers for the Inputs page."""

from __future__ import annotations

from typing import Any


_RECOMMENDATION_APPLY_NAMES: tuple[str, ...] = (
    "_apply_shared_updates",
    "_bottom_arrangement_to_shared_updates",
    "_compute_bottom_reo_recommendation",
    "_compute_geometry_recommendation",
    "_compute_shear_recommendation",
    "_shared_state_snapshot",
)


def _bind_recommendation_apply_globals(*, legacy_page: Any) -> None:
    namespace = globals()
    for name in _RECOMMENDATION_APPLY_NAMES:
        namespace[name] = getattr(legacy_page, name)


def apply_geometry_recommendation(legacy_page: Any, *, source: str) -> bool:
    _bind_recommendation_apply_globals(legacy_page=legacy_page)
    return _apply_geometry_recommendation(source=source)


def apply_bottom_reo_recommendation(legacy_page: Any, *, source: str) -> bool:
    _bind_recommendation_apply_globals(legacy_page=legacy_page)
    return _apply_bottom_reo_recommendation(source=source)


def apply_shear_recommendation(legacy_page: Any, *, source: str) -> bool:
    _bind_recommendation_apply_globals(legacy_page=legacy_page)
    return _apply_shear_recommendation(source=source)


def _apply_geometry_recommendation(*, source: str) -> bool:
    recommendation = _compute_geometry_recommendation(_shared_state_snapshot())
    if not recommendation:
        return False
    return _apply_shared_updates(recommendation["updates"], source=source)


def _apply_bottom_reo_recommendation(*, source: str) -> bool:
    recommendation = _compute_bottom_reo_recommendation(_shared_state_snapshot())
    if not recommendation:
        return False
    updates = recommendation.get("updates") or _bottom_arrangement_to_shared_updates(recommendation.get("arrangement") or {})
    return _apply_shared_updates(updates, source=source)


def _apply_shear_recommendation(*, source: str) -> bool:
    recommendation = _compute_shear_recommendation(_shared_state_snapshot())
    if not recommendation:
        return False
    return _apply_shared_updates(recommendation["updates"], source=source)
