"""Neutral refresh contract for detailed engineering result pages.

The page shell decides where a result page renders. This contract decides only
whether the selected page needs one shared engineering refresh; it never
calculates, publishes, renders, or owns Streamlit state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ResultPageWorkspaceDecision:
    page_slug: str
    requires_calculation: bool
    reason: str


def resolve_result_page_workspace(
    page_slug: str,
    state: Mapping[str, Any],
) -> ResultPageWorkspaceDecision:
    """Return a deterministic refresh decision from shared engineering state."""

    slug = str(page_slug or "").strip().lower()
    if not slug:
        raise ValueError("page_slug is required")
    if bool(state.get("inputs_dirty")) or bool(state.get("_inputs_dirty")):
        return ResultPageWorkspaceDecision(slug, True, "engineering_inputs_dirty")
    if not isinstance(state.get("_cached_compute_results"), dict):
        return ResultPageWorkspaceDecision(slug, True, "calculation_cache_missing")
    if not isinstance(state.get("results"), dict):
        return ResultPageWorkspaceDecision(slug, True, "result_projection_missing")
    return ResultPageWorkspaceDecision(slug, False, "current_projection_reusable")


__all__ = ["ResultPageWorkspaceDecision", "resolve_result_page_workspace"]
