"""Pure candidate-evaluation projections owned by the application layer."""

from __future__ import annotations

from typing import Any


def build_full_candidate_evaluation_result_projection(
    *,
    candidate_state: dict[str, Any] | None,
    source: str,
    label: str | None,
    action_type: str | None,
    updates: dict[str, Any] | None,
    overview: dict[str, Any],
    bottom_state: dict[str, Any],
    width: int | float,
    depth: int | float,
    ast_top: int | float,
    bar_count: int,
    row_count: int,
    reo_congestion_index: int | float,
    shear_density: int | float,
    flexural_util: int | float | None,
    ductility_util: int | float | None,
    min_steel_util: int | float | None,
    bending_present: bool,
) -> dict[str, Any]:
    """Build a candidate result from already evaluated, plain facts."""

    overview_d = dict(overview or {})
    bottom_state_d = dict(bottom_state or {})
    statuses = dict(overview_d.get("statuses") or {})
    fail_count = sum(1 for status in statuses.values() if status == "FAIL")
    source_text = str(source or "")
    return {
        "source": source_text,
        "label": label or source_text.replace("_", " ").title(),
        "action_type": action_type,
        "updates": dict(updates or {}),
        "state": candidate_state if isinstance(candidate_state, dict) else {},
        "overview": overview_d,
        "bottom_state": bottom_state_d,
        "width": float(width),
        "depth": float(depth),
        "Ast_bot": float(bottom_state_d.get("Ast_bot", 0.0) or 0.0),
        "Ast_top": float(ast_top),
        "bar_count": int(bar_count),
        "row_count": int(row_count),
        "reo_congestion_index": float(reo_congestion_index),
        "shear_density": float(shear_density),
        "bending_components": {
            "flexural_util": flexural_util if bending_present else None,
            "ductility_util": ductility_util if bending_present else None,
            "min_steel_util": min_steel_util if bending_present else None,
        },
        "is_compliant": bool(overview_d.get("all_key_pass")),
        "worst_util": float(overview_d.get("worst_util") or 0.0),
        "fail_count": fail_count,
    }


__all__ = ["build_full_candidate_evaluation_result_projection"]
