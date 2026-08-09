"""Calculator-backed shear overdesign cleanup pipeline."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain_apply import Candidate, propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult


Calculate = Callable[[BeamInputs], EngineeringResult]
Evaluate = Callable[..., Any]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]
CompleteStage = Callable[[str], None]


class ShearOverdesignPipeline:
    """Reduce link density and optional width while preserving compliance."""

    def __init__(self, *, calculate: Calculate, evaluate: Evaluate, rank_key: RankKey, complete_stage: CompleteStage) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._complete_stage = complete_stage

    def preview(self, current: BeamInputs) -> DesignBrainPreview:
        before = self._calculate(current)
        capacity = float(before.families.get("shear", {}).get("phi_Vu", 0.0) or 0.0)
        current_util = abs(float(current.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
        seed = propose_neutral_candidate(current)
        seed = replace(
            seed,
            proposal=replace(
                seed.proposal,
                bottom_bars=current.bottom.bars,
                bottom_diameter_mm=current.bottom.diameter_mm,
                bottom_spacing_mm=current.bottom.spacing_mm,
                bottom_cover_mm=current.bottom.cover_mm,
            ),
        )
        zero_demand = abs(float(current.actions.shear_force_kn)) < 1e-9
        if zero_demand and current.shear.diameter_mm > 0 and current.shear.legs > 0:
            candidate = Candidate(
                "shear-overdesign-zero-demand-remove-links",
                current.revision,
                current.content_hash,
                replace(
                    seed.proposal,
                    shear_diameter_mm=0,
                    shear_legs=0,
                    shear_spacing_mm=current.shear.spacing_mm,
                ),
                "Remove unnecessary ligatures because no design shear action is present.",
            )
            evaluation = self._evaluate(
                current, candidate, stage_id="remove_unrequired_ligatures"
            )
            if evaluation.usable and evaluation.result is not None:
                return DesignBrainPreview(candidate, before, evaluation.result, ("shear",), True, "safe_overdesign_cleanup", 0.85, 1.0)

        trials: list[tuple[float, Candidate, EngineeringResult, float]] = []
        for spacing in (100.0, 125.0, 150.0, 175.0, 200.0, 250.0, 300.0, 400.0, 500.0, 600.0):
            for diameter in (0, 10, 12, 16):
                legs = 0 if diameter == 0 else current.shear.legs or 2
                if zero_demand and (
                    diameter == current.shear.diameter_mm
                    and legs == current.shear.legs
                    and spacing == current.shear.spacing_mm
                ):
                    continue
                candidate = Candidate(
                    f"shear-overdesign-{diameter}-{legs}-{int(spacing)}",
                    current.revision,
                    current.content_hash,
                    replace(seed.proposal, shear_diameter_mm=diameter, shear_legs=legs, shear_spacing_mm=spacing),
                    "Shear overdesign cleanup: reduce link density while preserving compliance.",
                )
                if diameter == 0:
                    stage_id = "remove_unrequired_ligatures"
                elif diameter < current.shear.diameter_mm or legs < current.shear.legs:
                    stage_id = "reduce_ligature_size_or_legs"
                else:
                    stage_id = "increase_spacing"
                evaluation = self._evaluate(current, candidate, stage_id=stage_id)
                if not evaluation.usable:
                    continue
                result = evaluation.result
                assert result is not None
                capacity = float(result.families.get("shear", {}).get("phi_Vu", 0.0) or 0.0)
                util = abs(float(current.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
                if util <= 1.0 and complete_compliance(result):
                    trials.append((abs(util - 0.925), candidate, result, abs(spacing - current.shear.spacing_mm) / 100 + abs(diameter - current.shear.diameter_mm) / 10))
        self._complete_stage("increase_spacing")
        self._complete_stage("reduce_ligature_size_or_legs")
        self._complete_stage("remove_unrequired_ligatures")
        if zero_demand:
            for width in range(int(current.width_mm) - 25, 149, -25):
                candidate = Candidate(
                    f"shear-overdesign-width-{width}",
                    current.revision,
                    current.content_hash,
                    replace(seed.proposal, width_mm=float(width), shear_diameter_mm=0, shear_legs=0),
                    "Shear overdesign cleanup: remove links and reduce width while preserving bending compliance.",
                )
                evaluation = self._evaluate(
                    current, candidate, stage_id="reduce_width_and_redesign"
                )
                if not evaluation.usable:
                    continue
                result = evaluation.result
                assert result is not None
                bend_util = float(result.families.get("bending", {}).get("util", 0.0) or 0.0)
                if bend_util <= 1.0 and complete_compliance(result):
                    trials.append((abs(bend_util - 0.925), candidate, result, abs(width - current.width_mm) / 100))
        self._complete_stage("reduce_width_and_redesign")
        if not trials:
            return DesignBrainPreview(seed, before, before, (), False, "no_safe_shear_cleanup", 0.85, 1.0)
        _, candidate, after, _ = min(
            trials,
            key=lambda row: self._rank_key(current, row[1], row[2], row[0], row[3]),
        )
        capacity = float(after.families.get("shear", {}).get("phi_Vu", 0.0) or 0.0)
        util = abs(float(current.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
        zero_demand_cleanup = (
            zero_demand
            and (
                candidate.proposal.shear_diameter_mm != current.shear.diameter_mm
                or candidate.proposal.shear_legs != current.shear.legs
                or candidate.proposal.shear_spacing_mm != current.shear.spacing_mm
                or candidate.proposal.width_mm != current.width_mm
            )
            and float(after.families.get("bending", {}).get("util", 0.0) or 0.0) <= 1.0
        )
        accepted = ((util > current_util and util <= 1.0) or zero_demand_cleanup) and complete_compliance(after)
        reason = (
            "safe_overdesign_cleanup"
            if accepted and util < 0.85
            else ("shear_overdesign_cleanup" if accepted else "no_improving_shear_cleanup")
        )
        return DesignBrainPreview(candidate, before, after, ("shear",), accepted, reason, 0.85, 1.0)


__all__ = ["ShearOverdesignPipeline"]
