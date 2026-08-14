"""Calculator-backed primary bending repair pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi
from typing import Any, Callable

from inputs_v2.application.candidate_evaluation import (
    bending_mandatory_failure,
    complete_compliance,
)
from inputs_v2.application.design_brain.bending_proportion_pipeline import BendingProportionPipeline
from inputs_v2.application.design_brain.bending_repair_policy import (
    generate_bending_reduction_specs,
    generate_bending_width_lanes,
)
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain.ratio_policy import ratio_gate_required
from inputs_v2.application.design_brain.section_strategies import revise_family_geometry
from inputs_v2.application.design_brain_apply import Candidate, propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.design_preferences import DesignPreferenceProfile


Calculate = Callable[[BeamInputs], EngineeringResult]
Evaluate = Callable[..., Any]
CompleteStage = Callable[[str], None]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]


@dataclass(frozen=True)
class BendingFailureOutcome:
    preview: DesignBrainPreview
    metrics: dict[str, float | int | bool | tuple[str, ...]] | None = None


class BendingFailurePipeline:
    """Evaluate, balance and verify the primary bending repair ladder."""

    def __init__(
        self,
        *,
        calculate: Calculate,
        evaluate: Evaluate,
        stage_map: dict[str, str] | None = None,
        complete_stage: CompleteStage = lambda _stage_id: None,
        rank_key: RankKey,
        preferences: DesignPreferenceProfile,
    ) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._stage_map = stage_map or {}
        self._complete_stage = complete_stage
        self._rank_key = rank_key
        self._preferences = preferences

    def _stage(self, stage_id: str) -> str:
        return self._stage_map.get(stage_id, stage_id)

    def preview(self, current: BeamInputs) -> BendingFailureOutcome:
        before = self._calculate(current)
        current_util = float(before.families.get("bending", {}).get("util", 0.0))
        current_bending_failed = bending_mandatory_failure(before)
        seed = propose_neutral_candidate(current)
        if current_util <= 0.0:
            return BendingFailureOutcome(
                DesignBrainPreview(seed, before, before, (), False, "no_bending_demand")
            )
        low, high = 0.85, 1.0
        midpoint = (low + high) / 2.0
        trials: list[tuple[float, Candidate, BeamInputs, EngineeringResult, float]] = []
        target_trial: tuple[float, Candidate, BeamInputs, EngineeringResult, float] | None = None
        completed_stages: set[str] = set()
        budget_exhausted = False
        for width_lane in generate_bending_width_lanes(current, current_util, low):
            by_depth: dict[float, list] = {}
            for spec in width_lane.candidates:
                by_depth.setdefault(float(spec.depth_mm), []).append(spec)
            for depth_mm, cell_specs in by_depth.items():
                ordered_specs = self._ordered_cell_specs(
                    current,
                    before,
                    tuple(cell_specs),
                    midpoint,
                )
                if not ordered_specs:
                    continue
                cell_target_trials: list[
                    tuple[float, Candidate, BeamInputs, EngineeringResult, float]
                ] = []
                for spec in ordered_specs:
                    stage_id = self._stage_id(current, spec)
                    candidate = Candidate(
                        f"bending-only-b{int(spec.width_mm)}-{int(spec.depth_mm)}-{spec.bars}-N{spec.diameter_mm}-rows{'-'.join(map(str, spec.row_counts))}",
                        current.revision,
                        current.content_hash,
                        revise_family_geometry(
                            current,
                            replace(
                                seed.proposal,
                                bottom_bars=spec.bars,
                                bottom_diameter_mm=spec.diameter_mm,
                            ),
                            width_mm=spec.width_mm,
                            depth_mm=spec.depth_mm,
                        ),
                        f"Bending ladder: select {spec.bars}-N{spec.diameter_mm} at {spec.depth_mm:.0f} mm depth and {spec.width_mm:.0f} mm width.",
                        spec.row_counts,
                    )
                    evaluation = self._evaluate(
                        current,
                        candidate,
                        stage_id=self._stage(stage_id),
                        provisional=True,
                    )
                    if evaluation.result is None:
                        if "search_budget_exhausted" in evaluation.rejection_codes:
                            budget_exhausted = True
                            break
                        continue
                    result = evaluation.result
                    util = float(result.families.get("bending", {}).get("util", 0.0))
                    in_band = low <= util <= high
                    if evaluation.usable:
                        distance = 0.0 if in_band else abs(util - midpoint)
                        congestion = result.families.get("reinforcement_fit", {}).get("congestion_class", "low")
                        congestion_penalty = {"low": 0.0, "moderate": 0.25, "high": 0.75, "invalid": 10.0}.get(congestion, 1.0)
                        edit_size = (
                            abs(spec.bars - current.bottom.bars)
                            + abs(spec.diameter_mm - current.bottom.diameter_mm) / 10.0
                            + abs(spec.depth_mm - current.depth_mm) / 100.0
                            + abs(spec.width_mm - current.width_mm) / 100.0
                            + (len(spec.row_counts) - 1) * 0.25
                            + congestion_penalty
                        )
                        row = (
                            distance + (0.0 if in_band else 10.0),
                            candidate,
                            evaluation.outcome.inputs,
                            result,
                            edit_size,
                        )
                        trials.append(row)
                        if in_band:
                            cell_target_trials.append(row)
                    # The closest-to-required steel candidate is ordered first.
                    # If it is already too weak and every remaining candidate
                    # contains less steel, this geometry cell has a proved
                    # section-level capacity ceiling and can be abandoned.
                    if spec is ordered_specs[0] and util > high:
                        first_area = self._steel_area(spec.bars, spec.diameter_mm)
                        if all(
                            self._steel_area(other.bars, other.diameter_mm) <= first_area
                            for other in ordered_specs[1:]
                        ):
                            break
                if cell_target_trials:
                    target_trial = min(
                        cell_target_trials,
                        key=lambda row: self._rank_key(
                            current, row[1], row[3], row[0], row[4]
                        ),
                    )
                if target_trial is not None or budget_exhausted:
                    break
            if target_trial is not None or budget_exhausted:
                break
            for stage_id in self._completed_stages_for_lane(current, width_lane.width_mm):
                mapped = self._stage(stage_id)
                if mapped not in completed_stages:
                    self._complete_stage(mapped)
                    completed_stages.add(mapped)
        if not trials:
            # A locked or empty width lane is still exhaustion evidence for
            # the declared width stage.  Record every unvisited stage before
            # returning so a blocked decision identifies the exact lock and
            # never masquerades as an incomplete search.
            for stage_id in (
                "increase_bottom_reinforcement",
                "add_reinforcement_layer",
                "increase_depth",
                "increase_width_at_ratio_limit",
            ):
                mapped = self._stage(stage_id)
                if mapped not in completed_stages:
                    self._complete_stage(mapped)
                    completed_stages.add(mapped)
            return BendingFailureOutcome(
                DesignBrainPreview(seed, before, before, (), False, "no_valid_bending_candidate", low, high)
            )

        def rank(row):
            return self._rank_key(current, row[1], row[3], row[0], row[4])

        if target_trial is not None:
            _, candidate, updated_inputs, after, _ = target_trial
        elif current_util < low:
            direct_reductions = []
            for spec in generate_bending_reduction_specs(current):
                trial = Candidate(
                    f"direct-cleanup-{int(spec.width_mm)}-{int(spec.depth_mm)}-{spec.bars}-N{spec.diameter_mm}",
                    current.revision,
                    current.content_hash,
                    revise_family_geometry(
                        current,
                        replace(
                            seed.proposal,
                            bottom_bars=spec.bars,
                            bottom_diameter_mm=spec.diameter_mm,
                        ),
                        width_mm=spec.width_mm,
                        depth_mm=spec.depth_mm,
                    ),
                    "Verified geometry reduction with minimum reinforcement retained.",
                    spec.row_counts,
                )
                evaluation = self._evaluate(
                    current,
                    trial,
                    stage_id=self._stage("increase_width_at_ratio_limit"),
                    provisional=True,
                )
                if evaluation.usable:
                    assert evaluation.result is not None
                    direct_reductions.append((spec.width_mm * spec.depth_mm, trial, evaluation.outcome.inputs, evaluation.result, abs(spec.bars - current.bottom.bars)))
            if direct_reductions:
                _, candidate, updated_inputs, after, _ = min(direct_reductions, key=lambda row: (row[0], row[4]))
            else:
                reductions = [
                    row for row in trials
                    if row[2].width_mm * row[2].depth_mm < current.width_mm * current.depth_mm
                    and complete_compliance(row[3])
                ]
                _, candidate, updated_inputs, after, _ = min(
                    reductions if reductions else trials,
                    key=(
                        (lambda row: (row[2].width_mm * row[2].depth_mm, row[4]))
                        if reductions else rank
                    ),
                )
        else:
            _, candidate, updated_inputs, after, _ = min(trials, key=rank)
        after_util = float(after.families.get("bending", {}).get("util", 0.0))
        safe_failure_repair = (
            current_bending_failed
            and after_util <= high
            and complete_compliance(after)
        )
        verified_geometry_cleanup = (
            current_util < low
            and candidate.proposal.width_mm * candidate.proposal.depth_mm
            < current.width_mm * current.depth_mm
            and after_util <= high
            and complete_compliance(after)
        )
        if (
            not safe_failure_repair
            and not verified_geometry_cleanup
            and (
                not (low <= after_util <= high)
                or abs(after_util - midpoint) >= abs(current_util - midpoint)
            )
        ):
            return BendingFailureOutcome(
                DesignBrainPreview(candidate, before, after, ("bottom.bars",), False, "no_improving_target_band_candidate", low, high)
            )

        initial = candidate, updated_inputs, after
        balance = BendingProportionPipeline(
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            stage_id=self._stage("increase_width_at_ratio_limit"),
            preferences=self._preferences,
        ).balance(
            current, before, candidate, updated_inputs, after
        )
        candidate, updated_inputs, after, reason = (
            balance.candidate,
            balance.updated_inputs,
            balance.result,
            balance.reason,
        )
        # ``after`` is the authoritative result returned by the shared
        # candidate-evaluation gateway.  Recalculating ``updated_inputs`` here
        # would create a second validation centre and could let this family
        # reinterpret a candidate differently from every other family.
        if not (
            low
            <= float(after.families.get("bending", {}).get("util", 0.0) or 0.0)
            <= high
        ) and reason == "proportion_balanced_candidate":
            candidate, updated_inputs, after = initial
            reason = "target_band_candidate"
        changed = tuple(
            field
            for field, old, new in (
                ("width_mm", current.width_mm, candidate.proposal.width_mm),
                ("depth_mm", current.depth_mm, candidate.proposal.depth_mm),
                ("bottom.bars", current.bottom.bars, candidate.proposal.bottom_bars),
                ("bottom.diameter_mm", current.bottom.diameter_mm, candidate.proposal.bottom_diameter_mm),
            )
            if old != new
        )
        final_util = float(after.families.get("bending", {}).get("util", 0.0) or 0.0)
        ratio_blocked = ratio_gate_required(
            current, candidate.proposal, after, self._preferences
        )
        unnecessary_layer = (
            current_util < low
            and
            len(candidate.row_counts)
            > int(current.bottom_arrangement.layer_count if current.bottom_arrangement is not None else 1)
            and candidate.proposal.width_mm >= current.width_mm
            and candidate.proposal.depth_mm >= current.depth_mm
            and final_util <= 1.0
        )
        geometry_reduced = candidate.proposal.width_mm * candidate.proposal.depth_mm < current.width_mm * current.depth_mm
        safe_cleanup = geometry_reduced and complete_compliance(after) and final_util <= 1.0 and not ratio_blocked
        safe_failure_repair = (
            current_bending_failed
            and final_util <= high
            and complete_compliance(after)
            and not ratio_blocked
        )
        if (
            final_util < low
            and candidate.proposal.width_mm < current.width_mm
            and candidate.proposal.depth_mm < current.depth_mm
            and complete_compliance(after)
            and not ratio_blocked
        ):
            safe_cleanup = True
        verified = (
            (low <= final_util <= high and not ratio_blocked and not unnecessary_layer)
            or safe_failure_repair
            or safe_cleanup
        )
        if ratio_blocked:
            final_reason = "ratio_proportion_review_required"
        elif unnecessary_layer:
            final_reason = "unnecessary_additional_reinforcement_layer"
        elif safe_failure_repair and not (low <= final_util <= high):
            final_reason = "safe_bending_failure_repair"
        elif safe_cleanup and not (low <= final_util <= high):
            final_reason = "safe_overdesign_cleanup"
        else:
            final_reason = reason if verified else "no_improving_target_band_candidate"
        return BendingFailureOutcome(
            DesignBrainPreview(candidate, before, after, changed, verified, final_reason, low, high),
            balance.metrics,
        )

    @staticmethod
    def _steel_area(bars: int, diameter_mm: int) -> float:
        return int(bars) * pi * float(diameter_mm) ** 2 / 4.0

    @classmethod
    def _ordered_cell_specs(cls, current, before, specs, midpoint):
        """Order a geometry cell around the steel area needed for the target.

        This is a family-owned search heuristic, not an acceptance shortcut:
        every returned arrangement still passes through the universal gateway.
        Impossible row layouts are omitted using the same cover/spacing geometry
        that the gateway subsequently verifies authoritatively.
        """

        current_capacity = float(
            before.families.get("bending", {}).get("phi_Mu_kNm", 0.0) or 0.0
        )
        demand = abs(float(current.actions.bending_moment_knm))
        target_capacity = demand / max(float(midpoint), 1e-9)
        current_area = cls._steel_area(
            current.bottom.bars, current.bottom.diameter_mm
        )
        current_effective = max(
            1.0,
            float(current.depth_mm)
            - float(current.bottom.cover_mm)
            - float(current.shear.diameter_mm)
            - float(current.bottom.diameter_mm) / 2.0,
        )

        possible = []
        for spec in specs:
            usable_width = float(spec.width_mm) - 2.0 * (
                float(current.bottom.cover_mm) + float(current.shear.diameter_mm)
            )
            if usable_width <= 0.0:
                continue
            if any(
                (usable_width - count * float(spec.diameter_mm))
                / max(count - 1, 1)
                < 20.0
                for count in spec.row_counts
            ):
                continue
            first_centre = (
                float(current.bottom.cover_mm)
                + float(current.shear.diameter_mm)
                + float(spec.diameter_mm) / 2.0
            )
            centroid = sum(
                count
                * (
                    first_centre
                    + index * (float(spec.diameter_mm) + 25.0)
                )
                for index, count in enumerate(spec.row_counts)
            ) / sum(spec.row_counts)
            effective = float(spec.depth_mm) - centroid
            if effective <= 0.0:
                continue
            if current_capacity > 0.0:
                estimated_area = (
                    current_area
                    * (target_capacity / current_capacity)
                    * (current_effective / effective)
                )
            else:
                estimated_area = cls._steel_area(spec.bars, spec.diameter_mm)
            possible.append((spec, estimated_area))

        return tuple(
            spec
            for spec, estimated_area in sorted(
                possible,
                key=lambda row: (
                    (
                        0
                        if (
                            row[0].width_mm == current.width_mm
                            and row[0].depth_mm == current.depth_mm
                            and len(row[0].row_counts) == 1
                        )
                        else 1
                        if (
                            row[0].width_mm == current.width_mm
                            and row[0].depth_mm == current.depth_mm
                        )
                        else 0
                    ),
                    abs(cls._steel_area(row[0].bars, row[0].diameter_mm) - row[1]),
                    len(row[0].row_counts),
                    cls._steel_area(row[0].bars, row[0].diameter_mm),
                    row[0].bars,
                    row[0].diameter_mm,
                    row[0].row_counts,
                ),
            )
        )

    @staticmethod
    def _stage_id(current: BeamInputs, spec) -> str:
        if spec.width_mm == current.width_mm and spec.depth_mm == current.depth_mm:
            return (
                "add_reinforcement_layer"
                if len(spec.row_counts) > 1
                else "increase_bottom_reinforcement"
            )
        if spec.width_mm == current.width_mm:
            return "increase_depth"
        return "increase_width_at_ratio_limit"

    @staticmethod
    def _completed_stages_for_lane(
        current: BeamInputs, width_mm: float
    ) -> tuple[str, ...]:
        if width_mm == float(current.width_mm):
            return (
                "increase_bottom_reinforcement",
                "add_reinforcement_layer",
                "increase_depth",
            )
        return ("increase_width_at_ratio_limit",)


__all__ = ["BendingFailureOutcome", "BendingFailurePipeline"]
