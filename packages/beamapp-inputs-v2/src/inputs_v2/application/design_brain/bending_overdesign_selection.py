"""Selection and acceptance policy for evaluated bending cleanup trials."""

from __future__ import annotations

from typing import Callable, Sequence

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain.ratio_policy import ratio_gate_required
from inputs_v2.application.design_brain_apply import Candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult


Trial = tuple[float, Candidate, EngineeringResult, float]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]


def select_bending_overdesign_preview(
    *,
    current: BeamInputs,
    before: EngineeringResult,
    seed: Candidate,
    trials: Sequence[Trial],
    reinforcement_trials: Sequence[Trial],
    geometry_attempted: bool,
    minimum_reinforcement_blocked: bool,
    ductility_blocked: bool,
    rank_key: RankKey,
) -> DesignBrainPreview:
    """Select one cleanup in contract order and apply mandatory safety gates."""
    if not trials:
        if geometry_attempted and ductility_blocked:
            reason = "ductility_geometry_exhausted"
        elif geometry_attempted and minimum_reinforcement_blocked:
            reason = "minimum_reinforcement_geometry_exhausted"
        else:
            reason = "no_safe_bending_cleanup"
        return DesignBrainPreview(
            seed, before, before, (), False, reason, 0.85, 1.0
        )

    target_reinforcement = [
        row
        for row in reinforcement_trials
        if 0.85
        <= float(row[2].families.get("bending", {}).get("util", 0.0) or 0.0)
        <= 1.0
    ]
    geometry_trials = [
        row
        for row in trials
        if row[1].proposal.width_mm < current.width_mm
        or row[1].proposal.depth_mm < current.depth_mm
    ]
    current_util = float(
        before.families.get("bending", {}).get("util", 0.0) or 0.0
    )
    if target_reinforcement:
        _, candidate, after, _ = min(
            target_reinforcement,
            key=lambda row: (
                row[1].proposal.bottom_bars
                * row[1].proposal.bottom_diameter_mm**2,
                abs(float(row[2].families["bending"]["util"]) - 0.925),
                row[3],
            ),
        )
    elif current_util < 0.85 and geometry_trials:
        target_geometry = [
            row
            for row in geometry_trials
            if 0.85
            <= float(
                row[2].families.get("bending", {}).get("util", 0.0) or 0.0
            )
            <= 1.0
        ]
        if target_geometry:
            _, candidate, after, _ = min(
                target_geometry,
                key=lambda row: (
                    abs(float(row[2].families["bending"]["util"]) - 0.925),
                    row[1].proposal.width_mm * row[1].proposal.depth_mm,
                    row[3],
                ),
            )
        else:
            _, candidate, after, _ = min(
                geometry_trials,
                key=lambda row: (
                    -float(
                        row[2].families.get("bending", {}).get("util", 0.0)
                        or 0.0
                    ),
                    row[1].proposal.width_mm * row[1].proposal.depth_mm,
                    row[3],
                ),
            )
    else:
        _, candidate, after, _ = min(
            trials,
            key=lambda row: rank_key(
                current, row[1], row[2], row[0], row[3]
            ),
        )

    util = float(after.families.get("bending", {}).get("util", 0.0) or 0.0)
    zero_demand_cleanup = (
        abs(float(current.actions.shear_force_kn)) < 1e-9
        and (
            candidate.proposal.shear_diameter_mm < current.shear.diameter_mm
            or candidate.proposal.shear_legs < current.shear.legs
            or candidate.proposal.width_mm < current.width_mm
        )
    )
    accepted = (
        ((util > current_util and util <= 1.0) or zero_demand_cleanup)
        and complete_compliance(after)
        and not ratio_gate_required(current, candidate.proposal, after)
    )
    if (
        abs(float(current.actions.bending_moment_knm)) < 1e-9
        and abs(float(current.actions.shear_force_kn)) < 1e-9
    ):
        accepted = False
    geometry_floor_reached = (
        (current.width_locked or current.width_mm <= 150.0)
        and (current.depth_locked or current.depth_mm <= 200.0)
    )
    if accepted and util < 0.85:
        reason = "safe_overdesign_cleanup"
    elif accepted:
        reason = "bending_overdesign_cleanup"
    elif geometry_floor_reached:
        reason = "minimum_reinforcement_geometry_exhausted"
    else:
        reason = "no_improving_bending_cleanup"
    shear_changed = (
        candidate.proposal.shear_diameter_mm != current.shear.diameter_mm
        or candidate.proposal.shear_legs != current.shear.legs
        or candidate.proposal.shear_spacing_mm != current.shear.spacing_mm
    )
    changed_fields = ("bottom", "shear") if shear_changed else ("bottom",)
    return DesignBrainPreview(
        candidate,
        before,
        after,
        changed_fields,
        accepted,
        reason,
        0.85,
        1.0,
    )


__all__ = ["Trial", "select_bending_overdesign_preview"]
