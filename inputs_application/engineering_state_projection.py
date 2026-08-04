"""Canonical projection from committed Inputs into calculation-ready state."""

from __future__ import annotations

from typing import Any, Mapping

from calculations.bending import effective_depth_with_links_mm
from inputs_application.candidate_metrics import candidate_bottom_updates
from inputs_application.recommendation_evaluation import (
    effective_bottom_design_state,
)
from inputs_application.state_utils import state_with_resolved_design_actions
from state_and_helpers import build_legacy_longitudinal_mirrors_from_rows


def rebuild_engineering_derived_state(
    state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Rebuild calculation fields from canonical geometry and reinforcement."""

    working = dict(state or {})
    working.update(build_legacy_longitudinal_mirrors_from_rows(working))
    resolved = state_with_resolved_design_actions(working)
    resolved.update(build_legacy_longitudinal_mirrors_from_rows(resolved))

    bottom = effective_bottom_design_state(
        resolved,
        candidate_bottom_updates(resolved),
    )
    if float(bottom.get("d_centroid", 0.0) or 0.0) > 0.0:
        resolved["d"] = float(bottom["d_centroid"])
    if int(bottom.get("nb_bot", 0) or 0) > 0 and float(
        bottom.get("db_bot", 0.0) or 0.0
    ) > 0.0:
        resolved.update(
            {
                "Ast_bot": float(bottom["Ast_bot"]),
                "db_bot": float(bottom["db_bot"]),
                "nb_bot": int(bottom["nb_bot"]),
            }
        )

    top_count = int(float(resolved.get("nb_top", 0) or 0))
    top_diameter = float(
        resolved.get("db_top", resolved.get("db_top_1", 0.0)) or 0.0
    )
    if top_count > 0 and top_diameter > 0.0:
        resolved["do"] = effective_depth_with_links_mm(
            D_mm=float(resolved.get("D", 0.0) or 0.0),
            cover_to_ligs_mm=float(resolved.get("cover_top", 0.0) or 0.0),
            lig_diameter_mm=float(resolved.get("lig_d", 0.0) or 0.0),
            bar_diameter_mm=top_diameter,
        )

    resolved.update(build_legacy_longitudinal_mirrors_from_rows(resolved))
    return resolved


__all__ = ["rebuild_engineering_derived_state"]
