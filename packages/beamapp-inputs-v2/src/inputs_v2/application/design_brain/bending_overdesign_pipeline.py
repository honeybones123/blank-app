"""Calculator-backed bending overdesign cleanup pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain.bending_overdesign_policy import (
    generate_overdesign_geometry_cells,
    generate_reinforcement_reductions,
    generate_shear_preservation_options,
)
from inputs_v2.application.design_brain.bending_overdesign_selection import (
    Trial,
    select_bending_overdesign_preview,
)
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain.candidate_arrangements import with_practical_bottom_rows
from inputs_v2.application.design_brain_apply import (
    Candidate,
    propose_neutral_candidate,
)
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.design_preferences import DesignPreferenceProfile


Calculate = Callable[[BeamInputs], EngineeringResult]
Evaluate = Callable[..., Any]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]
CompleteStage = Callable[[str, str | None], None]


@dataclass(frozen=True)
class BendingOverdesignOutcome:
    preview: DesignBrainPreview
    metrics: dict[str, object]


class BendingOverdesignPipeline:
    """Evaluate geometry, reinforcement and shear-preservation cleanup stages."""

    def __init__(
        self,
        *,
        calculate: Calculate,
        evaluate: Evaluate,
        rank_key: RankKey,
        complete_stage: CompleteStage,
        preferences: DesignPreferenceProfile,
        max_consecutive_infeasible: int = 80,
    ) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._complete_stage = complete_stage
        self._preferences = preferences
        self._max_consecutive_infeasible = max(1, max_consecutive_infeasible)

    def preview(self, current: BeamInputs) -> BendingOverdesignOutcome:
        before = self._calculate(current)
        current_util = float(
            before.families.get("bending", {}).get("util", 0.0) or 0.0
        )
        seed = propose_neutral_candidate(current)
        trials: list[Trial] = []
        reinforcement_trials: list[Trial] = []
        shear_preservation_queue: list[
            tuple[float, Candidate, EngineeringResult]
        ] = []
        metrics: dict[str, object] = {
            "proportion_triggered": False,
            "additional_evaluations": 0,
            "geometry_evaluations": 0,
            "reinforcement_evaluations": 0,
        }
        geometry_attempted = False
        minimum_reinforcement_blocked = False
        ductility_blocked = False
        improving_rejection_counts: dict[str, int] = {}

        def record_improving_rejections(evaluation, result) -> None:
            """Record only constraints that rejected a useful bending reduction."""

            if result is None or evaluation.usable:
                return
            trial_util = float(
                result.families.get("bending", {}).get("util", 0.0) or 0.0
            )
            if not current_util < trial_util <= 1.0:
                return
            for code in evaluation.rejection_codes:
                improving_rejection_counts[code] = (
                    improving_rejection_counts.get(code, 0) + 1
                )

        for cell in generate_overdesign_geometry_cells(current, current_util):
            metrics["geometry_evaluations"] = int(
                metrics["geometry_evaluations"]
            ) + 1
            geometry_attempted = True
            for bars, diameter in cell.arrangements:
                # The current design is evidence, not a cleanup candidate.  If
                # it enters the trial list it can hide the real constraint
                # that rejected every actual reduction.
                if (
                    cell.width_mm == current.width_mm
                    and cell.depth_mm == current.depth_mm
                    and bars == current.bottom.bars
                    and diameter == current.bottom.diameter_mm
                ):
                    continue
                proposal = replace(
                    seed.proposal,
                    width_mm=cell.width_mm,
                    depth_mm=cell.depth_mm,
                    bottom_bars=bars,
                    bottom_diameter_mm=diameter,
                )
                candidate = Candidate(
                    f"bending-overdesign-geometry-{int(cell.width_mm)}-{int(cell.depth_mm)}-{bars}-N{diameter}",
                    current.revision,
                    current.content_hash,
                    proposal,
                    "Test a smaller, rebalanced section while retaining every governing check.",
                )
                for arranged_candidate in with_practical_bottom_rows(candidate):
                    evaluation = self._evaluate(
                        current,
                        arranged_candidate,
                        stage_id="reduce_geometry_and_redesign",
                    )
                    metrics["additional_evaluations"] = int(
                        metrics["additional_evaluations"]
                    ) + 1
                    result = evaluation.result
                    record_improving_rejections(evaluation, result)
                    if result is not None:
                        bending = result.families.get("bending", {})
                        minimum_reinforcement_blocked |= (
                            str(bending.get("minimum_tensile_status", "PASS")).upper()
                            == "FAIL"
                        )
                        ductility_blocked |= (
                            str(result.families.get("ductility", {}).get("status", "PASS")).upper()
                            == "FAIL"
                        )
                        trial_util = float(bending.get("util", 0.0) or 0.0)
                        if (
                            not evaluation.usable
                            and current.actions.shear_force_kn > 0.0
                            and current_util < trial_util <= 1.0
                        ):
                            shear_preservation_queue.append(
                                (abs(trial_util - 0.925), arranged_candidate, result)
                            )
                    if not evaluation.usable or result is None:
                        continue
                    util = float(result.families.get("bending", {}).get("util", 0.0) or 0.0)
                    if util <= 1.0 and complete_compliance(result):
                        area_ratio = cell.width_mm * cell.depth_mm / max(
                            current.width_mm * current.depth_mm, 1.0
                        )
                        edit_size = (
                            abs(cell.width_mm - current.width_mm) / 100
                            + abs(cell.depth_mm - current.depth_mm) / 100
                            + abs(bars - current.bottom.bars)
                            + abs(diameter - current.bottom.diameter_mm) / 10
                            + (len(arranged_candidate.row_counts) - 1) * 0.25
                        )
                        trials.append(
                            (
                                area_ratio + abs(util - 0.925) * 0.05,
                                arranged_candidate,
                                result,
                                edit_size,
                            )
                        )
                        # One row is preferred.  Only fall back to the
                        # balanced second-row variant when the earlier
                        # arrangement was rejected by the shared gateway.
                        break
        self._complete_stage("reduce_geometry_and_redesign")

        reductions = generate_reinforcement_reductions(current)
        consecutive_infeasible = 0
        monotonic_stop = False
        for reduction_index, reduction in enumerate(reductions):
            candidate = Candidate(
                f"bending-overdesign-{reduction.bars}-N{reduction.diameter_mm}",
                current.revision,
                current.content_hash,
                replace(
                    seed.proposal,
                    bottom_bars=reduction.bars,
                    bottom_diameter_mm=reduction.diameter_mm,
                ),
                "Bending overdesign cleanup: reduce bottom reinforcement while preserving compliance.",
            )
            reduction_failed_bending = False
            reduction_usable = False
            for arranged_candidate in with_practical_bottom_rows(candidate):
                evaluation = self._evaluate(
                    current,
                    arranged_candidate,
                    stage_id="reduce_bottom_reinforcement",
                )
                metrics["reinforcement_evaluations"] = int(
                    metrics["reinforcement_evaluations"]
                ) + 1
                metrics["additional_evaluations"] = int(
                    metrics["additional_evaluations"]
                ) + 1
                result = evaluation.result
                record_improving_rejections(evaluation, result)
                reduction_failed_bending |= "bending_fail" in evaluation.rejection_codes
                if result is not None:
                    bending = result.families.get("bending", {})
                    util = float(bending.get("util", 0.0) or 0.0)
                    if (
                        not evaluation.usable
                        and current.actions.shear_force_kn > 0.0
                        and current_util < util <= 1.0
                    ):
                        shear_preservation_queue.append(
                            (abs(util - 0.925), arranged_candidate, result)
                        )
                if not evaluation.usable or result is None:
                    continue
                reduction_usable = True
                bending = result.families.get("bending", {})
                minimum_reinforcement_blocked |= (
                    str(bending.get("minimum_tensile_status", "PASS")).upper()
                    == "FAIL"
                )
                ductility_blocked |= (
                    str(result.families.get("ductility", {}).get("status", "PASS")).upper()
                    == "FAIL"
                )
                util = float(bending.get("util", 0.0) or 0.0)
                if util <= 1.0 and complete_compliance(result):
                    row = (
                        abs(util - 0.925),
                        arranged_candidate,
                        result,
                        abs(reduction.bars - current.bottom.bars)
                        + abs(reduction.diameter_mm - current.bottom.diameter_mm) / 10
                        + (len(arranged_candidate.row_counts) - 1) * 0.25,
                    )
                    reinforcement_trials.append(row)
                    trials.append(row)
                    break
            if reduction_usable:
                consecutive_infeasible = 0
            elif reduction_failed_bending:
                consecutive_infeasible += 1
            else:
                consecutive_infeasible = 0
            if (
                consecutive_infeasible >= self._max_consecutive_infeasible
                and self._remaining_reductions_are_not_stronger(
                    current, reduction, reductions[reduction_index + 1 :]
                )
            ):
                monotonic_stop = True
                metrics["consecutive_infeasible_stop"] = True
                metrics["consecutive_infeasible_count"] = consecutive_infeasible
                break
        self._complete_stage(
            "reduce_bottom_reinforcement",
            (
                "monotonic_bending_capacity_ceiling_proven"
                if monotonic_stop
                else None
            ),
        )
        self._complete_stage("remove_unnecessary_layer", None)

        self._append_shear_preservation_trials(
            current,
            current_util,
            shear_preservation_queue,
            trials,
            improving_rejection_counts,
        )
        self._complete_stage("preserve_near_limit_shear", None)
        preview = select_bending_overdesign_preview(
            current=current,
            before=before,
            seed=seed,
            trials=trials,
            reinforcement_trials=reinforcement_trials,
            geometry_attempted=geometry_attempted,
            minimum_reinforcement_blocked=minimum_reinforcement_blocked,
            ductility_blocked=ductility_blocked,
            improving_rejection_counts=improving_rejection_counts,
            rank_key=self._rank_key,
            preferences=self._preferences,
        )
        metrics["improving_rejection_counts"] = dict(
            sorted(improving_rejection_counts.items())
        )
        return BendingOverdesignOutcome(preview, metrics)

    @staticmethod
    def _tensile_potential(current: BeamInputs, bars: int, diameter_mm: int) -> float:
        effective_depth = max(
            current.depth_mm - current.bottom.cover_mm - diameter_mm / 2.0,
            1.0,
        )
        return bars * diameter_mm**2 * effective_depth

    @classmethod
    def _remaining_reductions_are_not_stronger(
        cls,
        current: BeamInputs,
        failed,
        remaining,
    ) -> bool:
        ceiling = cls._tensile_potential(
            current, failed.bars, failed.diameter_mm
        )
        return all(
            cls._tensile_potential(current, item.bars, item.diameter_mm)
            <= ceiling + 1e-9
            for item in remaining
        )

    def _append_shear_preservation_trials(
        self,
        current: BeamInputs,
        current_util: float,
        queue: list[tuple[float, Candidate, EngineeringResult]],
        trials: list[Trial],
        improving_rejection_counts: dict[str, int],
    ) -> None:
        for _distance, base_candidate, _base_result in sorted(
            queue, key=lambda row: row[0]
        )[:16]:
            for option in generate_shear_preservation_options(current):
                candidate = replace(
                    base_candidate,
                    candidate_id=(
                        f"{base_candidate.candidate_id}-preserve-shear-"
                        f"{option.diameter_mm}-{option.legs}-{int(option.spacing_mm)}"
                    ),
                    proposal=replace(
                        base_candidate.proposal,
                        shear_diameter_mm=option.diameter_mm,
                        shear_legs=option.legs,
                        shear_spacing_mm=option.spacing_mm,
                    ),
                    rationale=(
                        "Optimise bending while preserving the governing shear resistance."
                    ),
                )
                evaluation = self._evaluate(
                    current, candidate, stage_id="preserve_near_limit_shear"
                )
                result = evaluation.result
                if result is not None and not evaluation.usable:
                    util = float(
                        result.families.get("bending", {}).get("util", 0.0)
                        or 0.0
                    )
                    if current_util < util <= 1.0:
                        for code in evaluation.rejection_codes:
                            improving_rejection_counts[code] = (
                                improving_rejection_counts.get(code, 0) + 1
                            )
                if not evaluation.usable or result is None:
                    continue
                util = float(
                    result.families.get("bending", {}).get("util", 0.0) or 0.0
                )
                if not current_util < util <= 1.0:
                    continue
                area_ratio = (
                    candidate.proposal.width_mm * candidate.proposal.depth_mm
                    / max(current.width_mm * current.depth_mm, 1.0)
                )
                edit_size = (
                    abs(candidate.proposal.width_mm - current.width_mm) / 100
                    + abs(candidate.proposal.depth_mm - current.depth_mm) / 100
                    + abs(candidate.proposal.bottom_bars - current.bottom.bars)
                    + abs(
                        candidate.proposal.bottom_diameter_mm
                        - current.bottom.diameter_mm
                    )
                    / 10
                    + abs(option.diameter_mm - current.shear.diameter_mm) / 10
                    + abs(option.legs - current.shear.legs)
                    + abs(option.spacing_mm - current.shear.spacing_mm) / 100
                )
                trials.append(
                    (
                        area_ratio + abs(util - 0.925) * 0.05,
                        candidate,
                        result,
                        edit_size,
                    )
                )
                break


__all__ = ["BendingOverdesignOutcome", "BendingOverdesignPipeline"]
