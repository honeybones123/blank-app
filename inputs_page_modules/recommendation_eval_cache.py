"""Page adapter for the optional rerun-scoped recommendation evaluation cache."""

from __future__ import annotations

from typing import Any, Mapping

from inputs_application.recommendation_store import RecommendationStore


def get_recommendation_eval_cache(
    session_state: Mapping[str, Any],
    *,
    enabled: bool,
) -> dict:
    return RecommendationStore(session_state).evaluation_cache(enabled=enabled)


__all__ = ["get_recommendation_eval_cache"]
