"""Atomic bending-and-shear failure repair pipeline."""

from __future__ import annotations

from dataclasses import replace
from math import pi
from typing import Any, Callable

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain.candidate_arrangements import with_practical_bottom_rows
from inputs_v2.application.design_brain.ratio_policy import ratio_gate_required
from inputs_v2.application.design_brain_apply import Candidate, propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.engineering.minimum_reinforcement import (
    rectangular_minimum_tensile_area_mm2,
)


Calculate = Callable[[BeamInputs], EngineeringResult]
Evaluate = Callable[..., Any]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]
CompleteStage = Callable[[str], None]


class CombinedFailurePipeline:
    """Evaluate one atomic candidate that repairs both governing failures."""

    def __init__(self, *, calculate: Calculate, evaluate: Evaluate, rank_key: RankKey, complete_stage: CompleteStage = lambda _stage_id: None) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._complete_stage = complete_stage

    def preview(self, current: BeamInputs) -> DesignBrainPreview:
        before = self._calculate(current)
        bending_before = float(before.families.get("bending", {}).get("util", 0.0) or 0.0)
        seed = propose_neutral_candidate(current)
        trials: list[tuple[float, Candidate, EngineeringResult, float]] = []
        widths = (
            (float(current.width_mm),)
            if current.width_locked
            else (
                float(current.width_mm),
                *(
                    current.width_mm + 25.0 * index
                    for index in range(
                        1,
                        int((min(3000.0, 2.0 * current.width_mm) - current.width_mm) / 25.0) + 1,
                    )
                ),
            )
        )
        current_ast = current.bottom.bars * 0.7854 * current.bottom.diameter_mm**2
        for width in widths:
            max_depth = min(5000.0, 2.0 * width)
            depths = (
                (float(current.depth_mm),)
                if current.depth_locked
                else (
                    float(current.depth_mm),
                    *(depth for depth in range(int(current.depth_mm) + 50, int(max_depth) + 1, 50)),
                )
            )
            for depth in depths:
                demand_ast = (
                    current_ast
                    * max(bending_before, 1.0)
                    / 0.925
                    * current.depth_mm
                    / max(depth, 1.0)
                )
                bottom_options = []
                for bars in range(max(2, current.bottom.bars), 13):
                    for diameter in (10, 12, 16, 20, 24, 28, 32, 36, 40):
                        area = bars * pi * diameter**2 / 4.0
                        effective_depth = max(
                            float(depth)
                            - float(current.bottom.cover_mm)
                            - float(current.shear.diameter_mm)
                            - diameter / 2.0,
                            1.0,
                        )
                        minimum_ast = rectangular_minimum_tensile_area_mm2(
                            width_mm=width,
                            overall_depth_mm=depth,
                            effective_depth_mm=effective_depth,
                            concrete_strength_mpa=current.materials.concrete_strength_mpa,
                            reinforcement_strength_mpa=current.materials.reinforcement_strength_mpa,
                        )
                        required_ast = max(demand_ast, minimum_ast)
                        bottom_options.append(
                            (area, bars, diameter, required_ast)
                        )
                bottom_pool = sorted(
                    bottom_options,
                    key=lambda row: (
                        0 if row[0] >= row[3] else 1,
                        abs(row[0] - row[3]),
                        row[1],
                        row[2],
                    ),
                )[:12]
                links = sorted(
                    (
                        (0, 0, float(current.shear.spacing_mm), 0.0),
                        *(
                        (diameter, legs, spacing, legs * diameter**2 / spacing)
                        for diameter in (10, 12, 16)
                        for legs in (2, 4, 6, 8)
                        for spacing in (300.0, 250.0, 200.0, 175.0, 150.0, 125.0, 100.0)
                        ),
                    ),
                    key=lambda row: (row[3], row[0], row[1], -row[2]),
                )
                for _area, bars, diameter, _required_ast in bottom_pool:
                    # Prove that this geometry/reinforcement cell can carry
                    # shear before spending evaluations on its full ligature
                    # ladder.  If the strongest practical links still fail
                    # shear or web crushing, every weaker link arrangement is
                    # dominated and can be bypassed safely.
                    fit_probe = (10, 8, 100.0, 8.0)
                    probe, probe_rows, exhausted = self._evaluate_combination(
                        current,
                        seed,
                        before,
                        trials,
                        width,
                        depth,
                        bars,
                        diameter,
                        *fit_probe[:3],
                    )
                    if exhausted:
                        return self._select_best(current, before, seed, trials)
                    if probe is not None:
                        return probe
                    probe_rejections = set(probe_rows)
                    if probe_rejections & {
                        "reinforcement_fit_failed",
                        "bending_fail",
                        "ductility_fail",
                        "minimum_tensile_reinforcement_failed",
                        "serviceability_fail",
                        "crack_control_fail",
                    }:
                        continue
                    strongest = max(links, key=lambda row: row[3])
                    if probe_rejections & {
                        "shear_strength_failed",
                        "shear_web_crushing_failed",
                    }:
                        probe, strongest_rows, exhausted = self._evaluate_combination(
                            current,
                            seed,
                            before,
                            trials,
                            width,
                            depth,
                            bars,
                            diameter,
                            *strongest[:3],
                        )
                        if exhausted:
                            return self._select_best(current, before, seed, trials)
                        if probe is not None:
                            return probe
                        if {
                            "shear_strength_failed",
                            "shear_web_crushing_failed",
                        } & set(strongest_rows):
                            continue
                    for shear_diameter, legs, spacing, _index in links:
                        if (shear_diameter, legs, spacing) in {
                            fit_probe[:3],
                            strongest[:3],
                        }:
                            continue
                        preview, _rejections, exhausted = self._evaluate_combination(
                            current,
                            seed,
                            before,
                            trials,
                            width,
                            depth,
                            bars,
                            diameter,
                            shear_diameter,
                            legs,
                            spacing,
                        )
                        if exhausted:
                            return self._select_best(current, before, seed, trials)
                        if preview is not None:
                            return preview
        self._complete_stage("repair_reinforcement")
        self._complete_stage("increase_geometry_and_redesign")
        return self._select_best(current, before, seed, trials)

    def _evaluate_combination(
        self,
        current: BeamInputs,
        seed: Candidate,
        before: EngineeringResult,
        trials: list[tuple[float, Candidate, EngineeringResult, float]],
        width: float,
        depth: float,
        bars: int,
        diameter: int,
        shear_diameter: int,
        legs: int,
        spacing: float,
    ) -> tuple[DesignBrainPreview | None, tuple[str, ...], bool]:
        candidate = Candidate(
            f"combined-failure-{bars}-N{diameter}-{shear_diameter}-{legs}-{int(spacing)}",
            current.revision,
            current.content_hash,
            replace(
                seed.proposal,
                width_mm=width,
                depth_mm=depth,
                bottom_bars=bars,
                bottom_diameter_mm=diameter,
                shear_diameter_mm=shear_diameter,
                shear_legs=legs,
                shear_spacing_mm=spacing,
            ),
            "Combined bending/shear ladder: atomically repair both governing failures.",
        )
        stage_id = (
            "repair_reinforcement"
            if width == current.width_mm and depth == current.depth_mm
            else "increase_geometry_and_redesign"
        )
        rejections: list[str] = []
        for arranged_candidate in with_practical_bottom_rows(candidate):
            evaluation = self._evaluate(
                current, arranged_candidate, stage_id=stage_id
            )
            if "search_budget_exhausted" in evaluation.rejection_codes:
                return None, tuple(rejections), True
            if not evaluation.usable:
                rejections.extend(evaluation.rejection_codes)
                continue
            result = evaluation.result
            assert result is not None
            bend = float(result.families.get("bending", {}).get("util", 0.0) or 0.0)
            capacity = float(result.families.get("shear", {}).get("phi_Vu", 0.0) or 0.0)
            shear = abs(float(evaluation.outcome.inputs.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
            target = max(bend, shear)
            in_band = 0.85 <= bend <= 1.0 and 0.85 <= shear <= 1.0
            distance = abs(target - 0.925) + (0.0 if in_band else 10.0)
            edit_size = (
                abs(width - current.width_mm) / 100
                + abs(depth - current.depth_mm) / 100
                + abs(bars - current.bottom.bars)
                + abs(diameter - current.bottom.diameter_mm) / 10
                + abs(shear_diameter - current.shear.diameter_mm) / 10
                + abs(legs - current.shear.legs) / 2
                + abs(spacing - current.shear.spacing_mm) / 100
                + (len(arranged_candidate.row_counts) - 1) * 0.25
            )
            trials.append((distance, arranged_candidate, result, edit_size))
            if in_band:
                return (
                    DesignBrainPreview(arranged_candidate, before, result, ("bottom", "shear"), True, "combined_target_band_candidate", 0.85, 1.0),
                    tuple(dict.fromkeys(rejections)),
                    False,
                )
            # A repair family must not keep searching thousands of larger
            # sections after it has proved a fully compliant revision with
            # the governing shear demand in band.  Bending may legitimately
            # remain below the optimisation band when minimum tensile steel
            # or the shear-governed section size controls.
            if bend < 0.75 and 0.85 <= shear <= 1.0:
                return (
                    DesignBrainPreview(
                        arranged_candidate,
                        before,
                        result,
                        ("bottom", "shear"),
                        True,
                        "safe_combined_failure_repair",
                        0.85,
                        1.0,
                    ),
                    tuple(dict.fromkeys(rejections)),
                    False,
                )
            break
        return None, tuple(dict.fromkeys(rejections)), False

    def _select_best(
        self,
        current: BeamInputs,
        before: EngineeringResult,
        seed: Candidate,
        trials: list[tuple[float, Candidate, EngineeringResult, float]],
    ) -> DesignBrainPreview:
        if not trials:
            return DesignBrainPreview(seed, before, before, (), False, "no_valid_combined_repair", 0.85, 1.0)
        _, candidate, after, _ = min(
            trials,
            key=lambda row: self._rank_key(current, row[1], row[2], row[0], row[3]),
        )
        bend = float(after.families.get("bending", {}).get("util", 0.0) or 0.0)
        capacity = float(after.families.get("shear", {}).get("phi_Vu", 0.0) or 0.0)
        shear = abs(float(current.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
        # Failure repair and efficiency optimisation are separate decisions.
        # Every trial retained above is already fully compliant.  Prefer an
        # in-band result when the discrete candidate space contains one, but
        # do not block a safe repair merely because one repaired utilisation
        # falls below the optimisation band.  The next Design Brain run can
        # optimise that compliant design as a separate recommendation.
        accepted = (
            bend <= 1.0
            and shear <= 1.0
            and complete_compliance(after)
            and not ratio_gate_required(current, candidate.proposal, after)
        )
        if accepted:
            reason = (
                "combined_target_band_candidate"
                if 0.85 <= bend <= 1.0 and 0.85 <= shear <= 1.0
                else "safe_combined_failure_repair"
            )
        else:
            reason = "no_combined_target_band_candidate"
        return DesignBrainPreview(candidate, before, after, ("bottom", "shear"), accepted, reason, 0.85, 1.0)


__all__ = ["CombinedFailurePipeline"]
