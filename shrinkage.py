"""Compatibility facade for callers that still import :mod:`shrinkage`."""

from __future__ import annotations

from shrinkage_page import (
    compute_shrinkage_components_for_crack_control,
    compute_shrinkage_results,
    render_shrinkage,
    render_shrinkage_page,
)


__all__ = [
    "compute_shrinkage_components_for_crack_control",
    "compute_shrinkage_results",
    "render_shrinkage",
    "render_shrinkage_page",
]
