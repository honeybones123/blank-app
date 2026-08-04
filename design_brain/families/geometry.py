"""Geometry-owned Design Brain selection helpers."""

from __future__ import annotations


def select_geometry_tightening_recommendation_result(
    candidates: list[dict] | tuple[dict, ...] | None,
    *,
    current_score: float,
    width_key: str,
    width_label: str,
) -> dict:
    """Select the final geometry-tightening result from evaluated candidates.

    The caller owns evaluation, scoring, trace emission, and candidate summary
    enrichment. Candidates must already include a numeric ``score`` and may
    include a precomputed ``in_target_band`` boolean.
    """
    values = [dict(candidate) for candidate in list(candidates or []) if isinstance(candidate, dict)]
    if not values:
        return {
            "status": "no_result",
            "return_reason": "no_valid_candidates",
            "selected_candidate": None,
            "result": None,
        }
    best = min(
        values,
        key=lambda item: (
            float(item.get("score", float("inf"))),
            0 if bool(item.get("in_target_band")) else 1,
            float(item.get("depth", 0.0) or 0.0),
            float(item.get("width", 0.0) or 0.0),
        ),
    )
    if float(best.get("score", float("inf"))) >= float(current_score) - 1e-6:
        return {
            "status": "no_result",
            "return_reason": "best_does_not_improve_current_score",
            "selected_candidate": dict(best),
            "result": None,
        }
    result = {
        "updates": dict(best.get("updates") or {}),
        "width_key": str(width_key or ""),
        "width_label": str(width_label or ""),
        "width": float(best.get("width", 0.0) or 0.0),
        "depth": float(best.get("depth", 0.0) or 0.0),
        "util": float(best.get("worst_util", 0.0) or 0.0),
        "score": float(best.get("score", 0.0) or 0.0),
        "label": str(best.get("label") or ""),
        "candidate_summary": dict(best.get("candidate_summary") or {}),
        "candidate_type": "geometry",
    }
    return {
        "status": "selected",
        "return_reason": "selected_geometry_tightening_candidate",
        "selected_candidate": dict(best),
        "result": result,
    }
