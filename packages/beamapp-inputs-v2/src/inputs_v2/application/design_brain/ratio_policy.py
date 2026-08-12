"""Longitudinal reinforcement-ratio review policy for candidate acceptance."""

from __future__ import annotations

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.design_preferences import (
    DEFAULT_DESIGN_PREFERENCES,
    DesignPreferenceProfile,
)
from inputs_v2.engineering.reinforcement_policy import ratio_trigger, tension_ratio


def ratio_review_required(
    inputs: BeamInputs,
    result: EngineeringResult,
    preferences: DesignPreferenceProfile = DEFAULT_DESIGN_PREFERENCES,
) -> bool:
    """Return true when longitudinal steel is below the policy review floor."""
    bending = result.families.get("bending", {})
    ast = float(bending.get("Ast_bot", bending.get("Ast_tension_mm2", 0.0)) or 0.0)
    cover = float(getattr(getattr(inputs, "bottom", None), "cover_mm", 40.0) or 40.0)
    effective_depth = float(
        bending.get("effective_depth_mm", max(float(inputs.depth_mm) - cover, 1.0))
        or 1.0
    )
    return ratio_trigger(
        tension_ratio(ast, float(inputs.width_mm), effective_depth), preferences
    ) is not None


def ratio_gate_required(
    current: BeamInputs,
    proposal: BeamInputs,
    result: EngineeringResult,
    preferences: DesignPreferenceProfile = DEFAULT_DESIGN_PREFERENCES,
) -> bool:
    """Request further review only when low-ratio geometry was not improved.

    The ratio bands are optimisation triggers, not code-failure limits. A
    calculator-compliant candidate that materially reduces the concrete
    section remains eligible even when minimum reinforcement leaves its ratio
    below the preferred band.
    """
    if not ratio_review_required(proposal, result, preferences):
        return False
    enlarged = (
        float(proposal.width_mm) > float(current.width_mm) * 1.20
        or float(proposal.depth_mm) > float(current.depth_mm) * 1.20
    )
    current_area = float(current.width_mm) * float(current.depth_mm)
    proposal_area = float(proposal.width_mm) * float(proposal.depth_mm)
    geometry_materially_reduced = proposal_area <= current_area * 0.95
    bending = result.families.get("bending", {})
    ast = float(bending.get("Ast_bot", bending.get("Ast_tension_mm2", 0.0)) or 0.0)
    effective_depth = float(
        bending.get(
            "effective_depth_mm",
            max(float(proposal.depth_mm) - 40.0, 1.0),
        )
        or 1.0
    )
    ratio = tension_ratio(ast, float(proposal.width_mm), effective_depth)
    return (
        ratio < preferences.strong_low_ratio_trigger
        and not enlarged
        and not geometry_materially_reduced
    )


__all__ = ["ratio_gate_required", "ratio_review_required"]
