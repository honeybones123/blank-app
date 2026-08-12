"""Family-owned coordinated repair pipelines for mixed ULS states."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain.bending_failure_pipeline import BendingFailurePipeline
from inputs_v2.application.design_brain.bending_overdesign_policy import (
    generate_overdesign_geometry_cells,
    generate_reinforcement_reductions,
)
from inputs_v2.application.design_brain.candidate_arrangements import with_practical_bottom_rows
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain.shear_failure_pipeline import ShearFailurePipeline
from inputs_v2.application.design_brain_apply import Candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.design_preferences import DesignPreferenceProfile


Calculate = Callable[[BeamInputs], EngineeringResult]
Evaluate = Callable[..., Any]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]
CompleteStage = Callable[[str], None]
BudgetExhausted = Callable[[], bool]


def _shear_util(inputs: BeamInputs, result: EngineeringResult) -> float:
    capacity = float(result.families.get("shear", {}).get("phi_Vu", 0.0) or 0.0)
    return abs(float(inputs.actions.shear_force_kn)) / capacity if capacity > 0.0 else 0.0


class BendingFailureShearCleanupPipeline:
    """Repair bending and remove shear excess in one atomic proposal."""

    def __init__(
        self,
        *,
        calculate: Calculate,
        evaluate: Evaluate,
        rank_key: RankKey,
        preferences: DesignPreferenceProfile,
        complete_stage: CompleteStage = lambda _stage_id: None,
        budget_exhausted: BudgetExhausted = lambda: False,
    ) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._preferences = preferences
        self._complete_stage = complete_stage
        self._budget_exhausted = budget_exhausted

    def preview(self, current: BeamInputs) -> DesignBrainPreview:
        base = BendingFailurePipeline(
            calculate=self._calculate,
            evaluate=self._evaluate,
            stage_map={
                "increase_bottom_reinforcement": "repair_bending",
                "add_reinforcement_layer": "repair_bending",
                "increase_depth": "coordinate_geometry",
                "increase_width_at_ratio_limit": "coordinate_geometry",
            },
            complete_stage=self._complete_stage,
            rank_key=self._rank_key,
            preferences=self._preferences,
        ).preview(current).preview
        if not base.accepted:
            return base

        options = self._shear_cleanup_options(current)
        trials: list[tuple[float, Candidate, EngineeringResult, float]] = []
        for diameter, legs, spacing in options:
            candidate = replace(
                base.candidate,
                candidate_id=(
                    f"mixed-bending-repair-shear-cleanup-{diameter}-{legs}-{int(spacing)}"
                ),
                proposal=replace(
                    base.candidate.proposal,
                    shear_diameter_mm=diameter,
                    shear_legs=legs,
                    shear_spacing_mm=spacing,
                ),
                rationale="Repair bending and remove unnecessary ligatures in one verified revision.",
            )
            evaluation = self._evaluate(
                current, candidate, stage_id="reduce_shear_excess"
            )
            if not evaluation.usable or evaluation.result is None:
                continue
            result = evaluation.result
            bending = float(result.families.get("bending", {}).get("util", 0.0) or 0.0)
            shear = _shear_util(current, result)
            distance = abs(bending - 0.925) + (
                abs(shear - 0.925) if current.actions.shear_force_kn else 0.0
            )
            material = legs * diameter**2 / max(spacing, 1.0) if diameter and legs else 0.0
            trials.append((distance, candidate, result, material))

        if not self._budget_exhausted():
            self._complete_stage("reduce_shear_excess")

        if not trials:
            return base
        _, candidate, result, _ = min(
            trials,
            key=lambda row: self._rank_key(current, row[1], row[2], row[0], row[3]),
        )
        return DesignBrainPreview(
            candidate,
            base.before,
            result,
            ("bottom", "shear", "width_mm", "depth_mm"),
            True,
            "safe_bending_repair_shear_cleanup",
            0.85,
            1.0,
        )

    @staticmethod
    def _shear_cleanup_options(current: BeamInputs) -> tuple[tuple[int, int, float], ...]:
        zero_demand = abs(float(current.actions.shear_force_kn)) < 1e-9
        options: list[tuple[int, int, float]] = []
        if zero_demand:
            options.append((0, 0, current.shear.spacing_mm))
        for diameter in (0, 10, 12, 16):
            for legs in ((0,) if diameter == 0 else (2, 4, 6, 8)):
                for spacing in (600.0, 500.0, 400.0, 300.0, 250.0, 200.0, 175.0, 150.0, 125.0, 100.0):
                    if diameter == 0 and not zero_demand:
                        continue
                    current_index = current.shear.legs * current.shear.diameter_mm**2 / max(current.shear.spacing_mm, 1.0)
                    proposed_index = legs * diameter**2 / max(spacing, 1.0) if diameter and legs else 0.0
                    if proposed_index < current_index - 1e-9:
                        options.append((diameter, legs, spacing))
        return tuple(dict.fromkeys(options))


class ShearFailureBendingOptimisePipeline:
    """Repair shear and optimise excess bending capacity atomically."""

    def __init__(
        self,
        *,
        calculate: Calculate,
        evaluate: Evaluate,
        rank_key: RankKey,
        complete_stage: CompleteStage = lambda _stage_id: None,
        budget_exhausted: BudgetExhausted = lambda: False,
    ) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._complete_stage = complete_stage
        self._budget_exhausted = budget_exhausted

    def preview(self, current: BeamInputs) -> DesignBrainPreview:
        base = ShearFailurePipeline(
            calculate=self._calculate,
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            stage_map={
                "repair_ligatures": "repair_ligatures",
                "increase_width": "resize_and_redesign",
                "increase_depth_and_redesign": "resize_and_redesign",
            },
            complete_stage=self._complete_stage,
        ).preview(current)
        if not base.accepted:
            return base

        trials: list[tuple[float, Candidate, EngineeringResult, float]] = []
        self._append_reinforcement_trials(current, base, trials)
        if not self._budget_exhausted():
            self._complete_stage("coordinate_longitudinal_reduction")
        self._append_geometry_trials(current, base, trials)
        if not self._budget_exhausted():
            self._complete_stage("resize_and_redesign")
        if not trials:
            return base
        _, candidate, result, _ = min(
            trials,
            key=lambda row: self._rank_key(current, row[1], row[2], row[0], row[3]),
        )
        return DesignBrainPreview(
            candidate,
            base.before,
            result,
            ("bottom", "shear", "width_mm", "depth_mm"),
            True,
            "safe_shear_repair_bending_optimised",
            0.85,
            1.0,
        )

    def _append_reinforcement_trials(self, current, base, trials) -> None:
        for reduction in generate_reinforcement_reductions(current):
            raw = replace(
                base.candidate,
                candidate_id=f"mixed-shear-repair-bending-{reduction.bars}-N{reduction.diameter_mm}",
                proposal=replace(
                    base.candidate.proposal,
                    bottom_bars=reduction.bars,
                    bottom_diameter_mm=reduction.diameter_mm,
                ),
                rationale="Repair shear and remove unnecessary bending reinforcement atomically.",
            )
            for candidate in with_practical_bottom_rows(raw):
                evaluation = self._evaluate(
                    current,
                    candidate,
                    stage_id="coordinate_longitudinal_reduction",
                )
                if not evaluation.usable or evaluation.result is None:
                    continue
                self._append_trial(current, candidate, evaluation.result, trials)
                break

    def _append_geometry_trials(self, current, base, trials) -> None:
        before_util = float(base.before.families.get("bending", {}).get("util", 0.0) or 0.0)
        for cell in generate_overdesign_geometry_cells(current, before_util):
            for bars, diameter in cell.arrangements:
                raw = replace(
                    base.candidate,
                    candidate_id=f"mixed-shear-repair-geometry-{int(cell.width_mm)}-{int(cell.depth_mm)}-{bars}-N{diameter}",
                    proposal=replace(
                        base.candidate.proposal,
                        width_mm=cell.width_mm,
                        depth_mm=cell.depth_mm,
                        bottom_bars=bars,
                        bottom_diameter_mm=diameter,
                    ),
                    rationale="Repair shear and resize the section while preserving every governing check.",
                )
                for candidate in with_practical_bottom_rows(raw):
                    evaluation = self._evaluate(
                        current, candidate, stage_id="resize_and_redesign"
                    )
                    if not evaluation.usable or evaluation.result is None:
                        continue
                    self._append_trial(current, candidate, evaluation.result, trials)
                    break

    @staticmethod
    def _append_trial(current, candidate, result, trials) -> None:
        if not complete_compliance(result):
            return
        bending = float(result.families.get("bending", {}).get("util", 0.0) or 0.0)
        shear = _shear_util(current, result)
        if bending > 1.0 or shear > 1.0:
            return
        distance = abs(bending - 0.925) + abs(shear - 0.925)
        edit = (
            abs(candidate.proposal.width_mm - current.width_mm) / 100.0
            + abs(candidate.proposal.depth_mm - current.depth_mm) / 100.0
            + abs(candidate.proposal.bottom_bars - current.bottom.bars)
            + abs(candidate.proposal.bottom_diameter_mm - current.bottom.diameter_mm) / 10.0
        )
        trials.append((distance, candidate, result, edit))


__all__ = [
    "BendingFailureShearCleanupPipeline",
    "ShearFailureBendingOptimisePipeline",
]
