"""Calculator-backed serviceability repair candidate pipeline."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain.section_strategies import revise_family_geometry
from inputs_v2.application.design_brain_apply import (
    Candidate,
    propose_neutral_candidate,
)
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.engineering.reinforcement_fit import practical_row_counts


Calculate = Callable[[BeamInputs], EngineeringResult]
Evaluate = Callable[..., Any]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]
CompleteStage = Callable[[str], None]


class ServiceabilityCandidatePipeline:
    """Search and select one fully recalculated serviceability repair."""

    def __init__(self, *, calculate: Calculate, evaluate: Evaluate, rank_key: RankKey, complete_stage: CompleteStage = lambda _stage_id: None) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._complete_stage = complete_stage

    def preview(self, current: BeamInputs) -> DesignBrainPreview:
        before = self._calculate(current)
        serviceability = before.families.get("serviceability", {})
        crack = before.families.get("crack_control", {})
        deflection_failed = str(serviceability.get("status", "PASS")).upper() == "FAIL"
        crack_failed = str(crack.get("status", "PASS")).upper() == "FAIL"
        if deflection_failed and crack_failed:
            state = "DEFLECTION_AND_CRACK_CONTROL_FAIL"
        elif deflection_failed:
            state = "DEFLECTION_ONLY_FAIL"
        elif crack_failed:
            state = "CRACK_CONTROL_ONLY_FAIL"
        else:
            state = "SERVICEABILITY_PASS"
        seed = propose_neutral_candidate(current)
        if not deflection_failed and not crack_failed:
            return DesignBrainPreview(seed, before, before, (), False, "serviceability_not_failed")

        trials = []
        widths = (current.width_mm,) if current.width_locked else tuple(current.width_mm + 25.0 * i for i in range(11))
        depths = (current.depth_mm,) if current.depth_locked else tuple(current.depth_mm + 25.0 * i for i in range(17))
        diameters = tuple(
            diameter
            for diameter in (10, 12, 16, 20, 24, 28, 32, 36, 40)
            if crack_failed and diameter <= current.bottom.diameter_mm
        ) or (current.bottom.diameter_mm,)
        bar_counts = tuple(range(max(2, current.bottom.bars), min(12, current.bottom.bars + 5) + 1))
        geometry_cells = tuple(
            sorted(
                (
                    (width, depth)
                    for width in widths
                    for depth in depths
                    if depth <= 2.0 * width
                ),
                key=lambda cell: (
                    max(
                        abs(cell[0] - current.width_mm) / 25.0,
                        abs(cell[1] - current.depth_mm) / 25.0,
                    ),
                    (
                        abs(cell[0] - current.width_mm)
                        + abs(cell[1] - current.depth_mm)
                    ),
                    abs(cell[1] - current.depth_mm),
                    abs(cell[0] - current.width_mm),
                ),
            )
        )
        current_stage_completed = False
        for width, depth in geometry_cells:
                cell_trials = []
                for bars in bar_counts:
                    for diameter in diameters:
                        proposal = revise_family_geometry(
                            current,
                            replace(
                                seed.proposal,
                                bottom_bars=bars,
                                bottom_diameter_mm=diameter,
                                shear_diameter_mm=current.shear.diameter_mm,
                                shear_legs=current.shear.legs,
                                shear_spacing_mm=current.shear.spacing_mm,
                            ),
                            width_mm=width,
                            depth_mm=depth,
                        )
                        for row_counts in practical_row_counts(bars):
                            candidate = Candidate(
                                f"serviceability-{int(width)}-{int(depth)}-{bars}-N{diameter}-rows{'-'.join(map(str, row_counts))}",
                                current.revision,
                                current.content_hash,
                                proposal,
                                f"{state}: test reinforcement distribution, layering and geometry; accept only after crack control, deflection, strength and fit all pass.",
                                row_counts,
                            )
                            stage_id = (
                                "redistribute_reinforcement"
                                if width == current.width_mm and depth == current.depth_mm
                                else "increase_stiffness"
                            )
                            evaluation = self._evaluate(
                                current, candidate, stage_id=stage_id, provisional=True
                            )
                            if "search_budget_exhausted" in evaluation.rejection_codes:
                                return self._select_best(current, before, seed, trials)
                            if not evaluation.usable:
                                continue
                            result = evaluation.result
                            assert result is not None
                            if not complete_compliance(result):
                                continue
                            serviceability_result = result.families.get("serviceability", {})
                            crack_result = result.families.get("crack_control", {})
                            edit = (
                                abs(width - current.width_mm) / 100
                                + abs(depth - current.depth_mm) / 100
                                + abs(bars - current.bottom.bars)
                                + abs(diameter - current.bottom.diameter_mm) / 10
                                + (len(row_counts) - 1) * 0.5
                            )
                            governing = max(
                                float(serviceability_result.get("deflection_util", 0.0) or 0.0),
                                float(crack_result.get("util", 0.0) or 0.0),
                            )
                            score = (
                                0.0
                                if 0.85 <= governing <= 1.0
                                else 0.85 - governing
                            )
                            row = (score, candidate, result, edit)
                            trials.append(row)
                            cell_trials.append(row)
                if width == current.width_mm and depth == current.depth_mm:
                    self._complete_stage("redistribute_reinforcement")
                    current_stage_completed = True
                if any(row[0] == 0.0 for row in cell_trials):
                    return self._select_best(current, before, seed, cell_trials)
        if not current_stage_completed:
            self._complete_stage("redistribute_reinforcement")
        self._complete_stage("increase_stiffness")
        return self._select_best(current, before, seed, trials)

    def _select_best(self, current, before, seed, trials) -> DesignBrainPreview:
        if not trials:
            reason = "serviceability_repair_blocked: no compliant candidate passed all required crack-control, deflection, strength and fit checks"
            return DesignBrainPreview(seed, before, before, (), False, reason, 0.85, 1.0)
        _, candidate, after, _ = min(
            trials,
            key=lambda row: self._rank_key(current, row[1], row[2], row[0], row[3]),
        )
        changed = tuple(
            field
            for field, old, new in (
                ("width_mm", current.width_mm, candidate.proposal.width_mm),
                ("depth_mm", current.depth_mm, candidate.proposal.depth_mm),
                ("bottom.bars", current.bottom.bars, candidate.proposal.bottom_bars),
                ("bottom.diameter_mm", current.bottom.diameter_mm, candidate.proposal.bottom_diameter_mm),
            )
            if old != new
        ) + (("bottom_arrangement",) if len(candidate.row_counts) > 1 else ())
        governing = max(
            float(after.families.get("serviceability", {}).get("deflection_util", 0.0) or 0.0),
            float(after.families.get("crack_control", {}).get("util", 0.0) or 0.0),
        )
        reason = (
            "serviceability_target_candidate"
            if 0.85 <= governing <= 1.0
            else "safe_serviceability_repair"
        )
        return DesignBrainPreview(candidate, before, after, changed, True, reason, 0.85, 1.0)


__all__ = ["ServiceabilityCandidatePipeline"]
