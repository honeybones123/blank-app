"""Ordered, atomic material and geometry cleanup for combined overdesign."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain.bending_overdesign_policy import (
    generate_reinforcement_reductions,
)
from inputs_v2.application.design_brain.candidate_arrangements import (
    with_practical_bottom_rows,
)
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain.ratio_policy import ratio_gate_required
from inputs_v2.application.design_brain_apply import Candidate, propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult


Calculate = Callable[[BeamInputs], EngineeringResult]
Evaluate = Callable[..., Any]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]
CompleteStage = Callable[[str], None]
Trial = tuple[float, Candidate, EngineeringResult, float]


def _active_utils(inputs: BeamInputs, result: EngineeringResult) -> tuple[float, ...]:
    values: list[float] = []
    if abs(float(inputs.actions.bending_moment_knm)) > 1e-9:
        values.append(float(result.families.get("bending", {}).get("util", 0.0) or 0.0))
    if abs(float(inputs.actions.shear_force_kn)) > 1e-9:
        capacity = float(result.families.get("shear", {}).get("phi_Vu", 0.0) or 0.0)
        values.append(abs(float(inputs.actions.shear_force_kn)) / capacity if capacity > 0.0 else float("inf"))
    return tuple(values)


def _distance(values: tuple[float, ...]) -> float:
    return sum(0.85 - value if value < 0.85 else value - 1.0 if value > 1.0 else 0.0 for value in values)


class CombinedOverdesignPipeline:
    """Run three declared cleanup stages, then publish one atomic proposal."""

    def __init__(
        self,
        *,
        calculate: Calculate,
        evaluate: Evaluate,
        rank_key: RankKey,
        complete_stage: CompleteStage,
        nearby_dimension_steps: int,
    ) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._complete_stage = complete_stage
        self._nearby_dimension_steps = nearby_dimension_steps

    def preview(self, current: BeamInputs) -> DesignBrainPreview:
        before = self._calculate(current)
        seed = propose_neutral_candidate(current)
        current_distance = _distance(_active_utils(current, before))

        shear_options = self._shear_stage(current, seed)
        self._complete_stage("reduce_shear_reinforcement")
        bending_options = self._bending_stage(current, seed)
        self._complete_stage("reduce_bending_reinforcement")

        # Preserve a neutral side of either cross-product.  This permits one
        # domain to reach an exact stop while the other still improves.
        shear_proposals = [seed, *(candidate for _, candidate, _, _ in shear_options[:10])]
        bending_proposals = [seed, *(candidate for _, candidate, _, _ in bending_options[:10])]
        trials: list[Trial] = []
        geometry_cells = self._nearby_geometry(current, self._nearby_dimension_steps)
        for width, depth in geometry_cells:
            for shear_candidate in shear_proposals:
                for bending_candidate in bending_proposals:
                    if shear_candidate is seed and bending_candidate is seed and width == current.width_mm and depth == current.depth_mm:
                        continue
                    raw = Candidate(
                        candidate_id=(
                            f"combined-overdesign-{int(width)}-{int(depth)}-"
                            f"{bending_candidate.proposal.bottom_bars}N{bending_candidate.proposal.bottom_diameter_mm}-"
                            f"{shear_candidate.proposal.shear_diameter_mm}-{shear_candidate.proposal.shear_legs}-"
                            f"{int(shear_candidate.proposal.shear_spacing_mm)}"
                        ),
                        source_revision=current.revision,
                        source_hash=current.content_hash,
                        proposal=replace(
                            seed.proposal,
                            width_mm=width,
                            depth_mm=depth,
                            bottom_bars=bending_candidate.proposal.bottom_bars,
                            bottom_diameter_mm=bending_candidate.proposal.bottom_diameter_mm,
                            shear_diameter_mm=shear_candidate.proposal.shear_diameter_mm,
                            shear_legs=shear_candidate.proposal.shear_legs,
                            shear_spacing_mm=shear_candidate.proposal.shear_spacing_mm,
                        ),
                        rationale="Reduce bending reinforcement, ligatures and geometry in one verified revision.",
                    )
                    for candidate in with_practical_bottom_rows(raw):
                        evaluation = self._evaluate(
                            current,
                            candidate,
                            stage_id="reduce_geometry_and_redesign",
                        )
                        if not evaluation.usable or evaluation.result is None:
                            continue
                        result = evaluation.result
                        if ratio_gate_required(current, candidate.proposal, result):
                            continue
                        values = _active_utils(current, result)
                        distance = _distance(values)
                        edit = (
                            abs(width - current.width_mm) / 100.0
                            + abs(depth - current.depth_mm) / 100.0
                            + abs(candidate.proposal.bottom_bars - current.bottom.bars)
                            + abs(candidate.proposal.bottom_diameter_mm - current.bottom.diameter_mm) / 10.0
                            + abs(candidate.proposal.shear_spacing_mm - current.shear.spacing_mm) / 100.0
                        )
                        trials.append((distance, candidate, result, edit))
                        break
            if any(row[0] == 0.0 for row in trials):
                # Nearby standard dimensions are ordered by least change.  A
                # target-band solution proves that broader cells are needless.
                break
        self._complete_stage("reduce_geometry_and_redesign")

        if not trials:
            return DesignBrainPreview(
                seed, before, before, (), False, "no_safe_combined_cleanup", 0.85, 1.0
            )
        target_trials = [row for row in trials if row[0] == 0.0]
        improving = [row for row in trials if row[0] < current_distance]
        selectable = target_trials or improving
        if not selectable:
            return DesignBrainPreview(
                seed, before, before, (), False, "no_improving_combined_cleanup", 0.85, 1.0
            )
        _, candidate, after, _ = min(
            selectable,
            key=lambda row: self._rank_key(current, row[1], row[2], row[0], row[3]),
        )
        changed = tuple(
            field
            for field, old, new in (
                ("width_mm", current.width_mm, candidate.proposal.width_mm),
                ("depth_mm", current.depth_mm, candidate.proposal.depth_mm),
                ("bottom.bars", current.bottom.bars, candidate.proposal.bottom_bars),
                ("bottom.diameter_mm", current.bottom.diameter_mm, candidate.proposal.bottom_diameter_mm),
                ("shear.diameter_mm", current.shear.diameter_mm, candidate.proposal.shear_diameter_mm),
                ("shear.legs", current.shear.legs, candidate.proposal.shear_legs),
                ("shear.spacing_mm", current.shear.spacing_mm, candidate.proposal.shear_spacing_mm),
            )
            if old != new
        )
        reason = "combined_overdesign_cleanup" if target_trials else "safe_overdesign_cleanup"
        return DesignBrainPreview(candidate, before, after, changed, True, reason, 0.85, 1.0)

    def _shear_stage(self, current: BeamInputs, seed: Candidate) -> list[Trial]:
        current_index = current.shear.legs * current.shear.diameter_mm**2 / max(current.shear.spacing_mm, 1.0)
        zero_demand = abs(float(current.actions.shear_force_kn)) < 1e-9
        trials: list[Trial] = []
        for diameter in (0, 10, 12, 16):
            for legs in ((0,) if diameter == 0 else (2, 4, 6, 8)):
                for spacing in (600.0, 500.0, 400.0, 300.0, 250.0, 200.0, 175.0, 150.0, 125.0, 100.0):
                    if diameter == 0 and not zero_demand:
                        continue
                    index = legs * diameter**2 / max(spacing, 1.0) if diameter and legs else 0.0
                    if index >= current_index - 1e-9:
                        continue
                    candidate = replace(
                        seed,
                        candidate_id=f"combined-shear-{diameter}-{legs}-{int(spacing)}",
                        proposal=replace(seed.proposal, shear_diameter_mm=diameter, shear_legs=legs, shear_spacing_mm=spacing),
                    )
                    evaluation = self._evaluate(current, candidate, stage_id="reduce_shear_reinforcement")
                    if evaluation.usable and evaluation.result is not None:
                        values = _active_utils(current, evaluation.result)
                        trials.append((_distance(values), candidate, evaluation.result, index))
        return sorted(trials, key=lambda row: self._rank_key(current, row[1], row[2], row[0], row[3]))

    def _bending_stage(self, current: BeamInputs, seed: Candidate) -> list[Trial]:
        trials: list[Trial] = []
        for reduction in generate_reinforcement_reductions(current):
            raw = replace(
                seed,
                candidate_id=f"combined-bending-{reduction.bars}N{reduction.diameter_mm}",
                proposal=replace(seed.proposal, bottom_bars=reduction.bars, bottom_diameter_mm=reduction.diameter_mm),
            )
            for candidate in with_practical_bottom_rows(raw):
                evaluation = self._evaluate(current, candidate, stage_id="reduce_bending_reinforcement")
                if evaluation.usable and evaluation.result is not None:
                    values = _active_utils(current, evaluation.result)
                    area = reduction.bars * reduction.diameter_mm**2
                    trials.append((_distance(values), candidate, evaluation.result, area))
                    break
        return sorted(trials, key=lambda row: self._rank_key(current, row[1], row[2], row[0], row[3]))

    @staticmethod
    def _nearby_geometry(current: BeamInputs, steps: int) -> tuple[tuple[float, float], ...]:
        widths = (current.width_mm,) if current.width_locked else tuple(
            value for value in (current.width_mm - 25.0 * index for index in range(steps)) if value >= 150.0
        )
        depths = (current.depth_mm,) if current.depth_locked else tuple(
            value for value in (current.depth_mm - 25.0 * index for index in range(steps + 1)) if value >= 200.0
        )
        return tuple((width, depth) for width in widths for depth in depths if depth <= 2.0 * width)


__all__ = ["CombinedOverdesignPipeline"]
