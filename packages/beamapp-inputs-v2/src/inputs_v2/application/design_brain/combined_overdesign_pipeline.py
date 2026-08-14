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
from inputs_v2.application.design_brain.ratio_policy import (
    ratio_gate_required,
    ratio_review_required,
)
from inputs_v2.application.design_brain.section_strategies import (
    proposal_concrete_area_mm2,
    revise_family_geometry,
)
from inputs_v2.application.design_brain_apply import (
    Candidate,
    apply_candidate,
    propose_neutral_candidate,
)
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.design_preferences import DesignPreferenceProfile


Calculate = Callable[[BeamInputs], EngineeringResult]
Evaluate = Callable[..., Any]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]
CompleteStage = Callable[[str], None]
MergeMetrics = Callable[[dict[str, object]], None]
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
        merge_metrics: MergeMetrics = lambda _metrics: None,
        nearby_dimension_steps: int,
        max_continuation_rounds: int,
        preferences: DesignPreferenceProfile,
    ) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._complete_stage = complete_stage
        self._merge_metrics = merge_metrics
        self._nearby_dimension_steps = nearby_dimension_steps
        self._max_continuation_rounds = max(1, max_continuation_rounds)
        self._preferences = preferences

    def preview(self, current: BeamInputs) -> DesignBrainPreview:
        """Publish one proposal after bounded family-owned continuation.

        A later reinforcement reduction can become valid only after an
        earlier geometry reduction.  Fast mode therefore continues from its
        own verified proposal for a small configured number of rounds.  Every
        round shares the same calculation cache and full-evaluation budget;
        only the final proposal is rebased to the user's current revision.
        """

        best = self._preview_once(current)
        applied_best = apply_candidate(current, best.candidate) if best.accepted else None
        proportion_review_pending = bool(
            applied_best is not None
            and applied_best.applied
            and ratio_review_required(
                applied_best.inputs,
                best.after,
                self._preferences,
            )
        )
        if (
            not best.accepted
            or (
                _distance(_active_utils(current, best.after)) == 0.0
                and not proportion_review_pending
            )
            or self._max_continuation_rounds <= 1
        ):
            self._merge_metrics({"combined_continuation_rounds_completed": 1})
            return best

        working = current
        working_preview = best
        completed = 1
        seen = {self._proposal_signature(best.candidate)}
        for _round in range(1, self._max_continuation_rounds):
            applied = apply_candidate(working, working_preview.candidate)
            if not applied.applied:
                break
            working = applied.inputs
            next_preview = self._preview_once(working, geometry_ceiling=current)
            completed += 1
            if not next_preview.accepted:
                break

            rebased = replace(
                next_preview.candidate,
                candidate_id=f"combined-continuation-{completed}-{next_preview.candidate.candidate_id}",
                source_revision=current.revision,
                source_hash=current.content_hash,
            )
            signature = self._proposal_signature(rebased)
            if signature in seen:
                break
            seen.add(signature)
            evaluation = self._evaluate(
                current,
                rebased,
                stage_id="reduce_geometry_and_redesign",
            )
            if not evaluation.usable or evaluation.result is None:
                break

            result = evaluation.result
            distance = _distance(_active_utils(current, result))
            current_distance = _distance(_active_utils(current, best.after))
            edit = self._edit_size(current, rebased)
            current_edit = self._edit_size(current, best.candidate)
            if self._rank_key(current, rebased, result, distance, edit) >= self._rank_key(
                current,
                best.candidate,
                best.after,
                current_distance,
                current_edit,
            ):
                break

            best = DesignBrainPreview(
                rebased,
                best.before,
                result,
                self._changed_fields(current, rebased),
                True,
                (
                    "combined_overdesign_cleanup"
                    if distance == 0.0
                    else "safe_overdesign_cleanup"
                ),
                0.85,
                1.0,
            )
            working_preview = next_preview
            if distance == 0.0:
                break

        self._merge_metrics({"combined_continuation_rounds_completed": completed})
        return best

    def _preview_once(
        self,
        current: BeamInputs,
        geometry_ceiling: BeamInputs | None = None,
    ) -> DesignBrainPreview:
        before = self._calculate(current)
        seed = propose_neutral_candidate(current)
        current_distance = _distance(_active_utils(current, before))
        finish_nearby_frontier = (
            ratio_review_required(current, before, self._preferences)
            or (
                abs(float(current.actions.shear_force_kn)) < 1e-9
                and current.shear.diameter_mm > 0
                and current.shear.legs > 0
            )
        )
        improving_rejections: dict[str, int] = {}
        continuation_rounds_completed = 0
        continuation_attempts: list[int] = []

        def reject(*codes: str) -> None:
            for code in codes:
                improving_rejections[code] = improving_rejections.get(code, 0) + 1

        def publish_metrics() -> None:
            self._merge_metrics(
                {
                    "improving_rejection_counts": dict(sorted(improving_rejections.items())),
                    "combined_continuation_rounds_completed": continuation_rounds_completed,
                    "combined_continuation_attempts_by_round": tuple(continuation_attempts),
                }
            )

        shear_options = self._shear_stage(current, seed)
        self._complete_stage("reduce_shear_reinforcement")
        bending_options = self._bending_stage(current, seed)
        self._complete_stage("reduce_bending_reinforcement")

        # Preserve a neutral side of either cross-product.  This permits one
        # domain to reach an exact stop while the other still improves.
        # The independent stages provide evidence about moves that work at
        # the current geometry.  The coordinated stage must also request raw
        # reductions that can become valid only after geometry changes;
        # otherwise Fast mode can require a second Apply merely to discover
        # a smaller reinforcement arrangement at the revised section.
        raw_shear = self._raw_shear_proposals(current, seed)
        merged_shear = self._merge_proposals(
            tuple(candidate for _, candidate, _, _ in shear_options[:10]),
            raw_shear,
        )
        if abs(float(current.actions.shear_force_kn)) < 1e-9:
            zero_links = tuple(
                candidate
                for candidate in raw_shear
                if candidate.proposal.shear_diameter_mm == 0
                and candidate.proposal.shear_legs == 0
            )
            merged_shear = self._merge_proposals(zero_links, merged_shear)
        shear_proposals = [seed, *merged_shear]
        bending_proposals = [
            seed,
            *self._merge_proposals(
                tuple(candidate for _, candidate, _, _ in bending_options[:10]),
                self._raw_bending_proposals(
                    current,
                    seed,
                    float(before.families.get("bending", {}).get("util", 0.0) or 0.0),
                ),
            ),
        ]
        trials: list[Trial] = []
        for geometry_frontier in self._geometry_frontiers(
            current,
            self._nearby_dimension_steps,
            1,
            geometry_ceiling=geometry_ceiling,
        ):
            round_attempts = 0
            for width, depth in geometry_frontier:
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
                            proposal=revise_family_geometry(
                                current,
                                replace(
                                    seed.proposal,
                                    bottom_bars=bending_candidate.proposal.bottom_bars,
                                    bottom_diameter_mm=bending_candidate.proposal.bottom_diameter_mm,
                                    shear_diameter_mm=shear_candidate.proposal.shear_diameter_mm,
                                    shear_legs=shear_candidate.proposal.shear_legs,
                                    shear_spacing_mm=shear_candidate.proposal.shear_spacing_mm,
                                ),
                                width_mm=width,
                                depth_mm=depth,
                            ),
                            rationale="Reduce bending reinforcement, ligatures and geometry in one verified revision.",
                        )
                        for candidate in with_practical_bottom_rows(raw):
                            round_attempts += 1
                            evaluation = self._evaluate(
                                current,
                                candidate,
                                stage_id="reduce_geometry_and_redesign",
                            )
                            if not evaluation.usable or evaluation.result is None:
                                reject(*evaluation.rejection_codes)
                                continue
                            result = evaluation.result
                            if ratio_gate_required(
                                current,
                                candidate.proposal,
                                result,
                                self._preferences,
                            ):
                                reject("longitudinal_ratio_gate")
                                continue
                            # A preferred low reinforcement ratio is not a
                            # compliance failure, but it is a declared
                            # proportion-balancing trigger for this family.
                            # Do not stop at the first ULS target candidate
                            # while that trigger is still unresolved; require
                            # the same material geometry reduction used by the
                            # target-band balancing stage.
                            if ratio_review_required(
                                evaluation.outcome.inputs,
                                result,
                                self._preferences,
                            ) and (
                                proposal_concrete_area_mm2(candidate.proposal)
                                > current.section_geometry.concrete_area_mm2 * 0.95
                            ):
                                reject("proportion_balance_required")
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
                # Finish the current bounded geometry frontier even after the
                # first target-band hit.  A later nearby standard dimension
                # can complete the same family's proportion-balancing or
                # zero-demand ligature cleanup.  Stopping at the first hit
                # was the source of repeated Apply cycles.
                if any(row[0] == 0.0 for row in trials) and not finish_nearby_frontier:
                    break
            continuation_rounds_completed += 1
            continuation_attempts.append(round_attempts)
            if any(row[0] == 0.0 for row in trials):
                break
        self._complete_stage("reduce_geometry_and_redesign")
        publish_metrics()

        if not trials:
            return DesignBrainPreview(
                seed,
                before,
                before,
                (),
                False,
                "verified_combined_constraints_exhausted",
                0.85,
                1.0,
            )
        target_trials = [row for row in trials if row[0] == 0.0]
        improving = [row for row in trials if row[0] < current_distance]
        selectable = target_trials or improving
        if not selectable:
            return DesignBrainPreview(
                seed,
                before,
                before,
                (),
                False,
                "verified_combined_constraints_exhausted",
                0.85,
                1.0,
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

    @staticmethod
    def _proposal_signature(candidate: Candidate) -> tuple[object, ...]:
        proposal = candidate.proposal
        return (
            proposal.width_mm,
            proposal.depth_mm,
            proposal.bottom_bars,
            proposal.bottom_diameter_mm,
            candidate.row_counts,
            proposal.shear_diameter_mm,
            proposal.shear_legs,
            proposal.shear_spacing_mm,
        )

    @classmethod
    def _merge_proposals(
        cls,
        ranked: tuple[Candidate, ...],
        raw: tuple[Candidate, ...],
    ) -> tuple[Candidate, ...]:
        """Keep target-directed moves plus a bounded raw coordination tail."""

        merged: list[Candidate] = []
        seen: set[tuple[object, ...]] = set()
        # Reserve capacity for both target-directed candidates that already
        # pass at the current geometry and raw candidates that may become
        # valid only after resizing.
        for candidate in (*ranked[:6], *raw[:6]):
            signature = cls._proposal_signature(candidate)
            if signature in seen:
                continue
            seen.add(signature)
            merged.append(candidate)
            if len(merged) >= 10:
                break
        return tuple(merged)

    @staticmethod
    def _edit_size(current: BeamInputs, candidate: Candidate) -> float:
        proposal = candidate.proposal
        return (
            abs(proposal.width_mm - current.width_mm) / 100.0
            + abs(proposal.depth_mm - current.depth_mm) / 100.0
            + abs(proposal.bottom_bars - current.bottom.bars)
            + abs(proposal.bottom_diameter_mm - current.bottom.diameter_mm) / 10.0
            + abs(proposal.shear_spacing_mm - current.shear.spacing_mm) / 100.0
        )

    @staticmethod
    def _changed_fields(
        current: BeamInputs,
        candidate: Candidate,
    ) -> tuple[str, ...]:
        proposal = candidate.proposal
        return tuple(
            field
            for field, old, new in (
                ("width_mm", current.width_mm, proposal.width_mm),
                ("depth_mm", current.depth_mm, proposal.depth_mm),
                ("bottom.bars", current.bottom.bars, proposal.bottom_bars),
                (
                    "bottom.diameter_mm",
                    current.bottom.diameter_mm,
                    proposal.bottom_diameter_mm,
                ),
                (
                    "shear.diameter_mm",
                    current.shear.diameter_mm,
                    proposal.shear_diameter_mm,
                ),
                ("shear.legs", current.shear.legs, proposal.shear_legs),
                (
                    "shear.spacing_mm",
                    current.shear.spacing_mm,
                    proposal.shear_spacing_mm,
                ),
            )
            if old != new
        )

    def _shear_stage(self, current: BeamInputs, seed: Candidate) -> list[Trial]:
        current_index = current.shear.legs * current.shear.diameter_mm**2 / max(current.shear.spacing_mm, 1.0)
        zero_demand = abs(float(current.actions.shear_force_kn)) < 1e-9
        trials: list[Trial] = []
        for diameter in (0, 10, 12, 16):
            for legs in ((0,) if diameter == 0 else (2, 3, 4, 5, 6, 8)):
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
    def _raw_bending_proposals(
        current: BeamInputs,
        seed: Candidate,
        current_utilisation: float,
    ) -> tuple[Candidate, ...]:
        current_index = current.bottom.bars * current.bottom.diameter_mm**2
        arrangements = sorted(
            (
                (bars * diameter**2, bars, diameter)
                for bars in range(2, 9)
                for diameter in (10, 12, 16, 20, 24, 28, 32, 36, 40)
                if bars * diameter**2 < current_index
            ),
            key=lambda row: (-row[0], row[1], row[2]),
        )
        target_index = current_index * max(current_utilisation, 0.01) / 0.925
        nearest_target = sorted(
            arrangements,
            key=lambda row: (abs(row[0] - target_index), row[1], row[2]),
        )[:4]
        selected = tuple(
            dict.fromkeys(
                (*arrangements[:3], *nearest_target, *arrangements[-3:])
            )
        )[:10]
        return tuple(
            replace(
                seed,
                candidate_id=f"combined-raw-bending-{bars}N{diameter}",
                proposal=replace(
                    seed.proposal,
                    bottom_bars=bars,
                    bottom_diameter_mm=diameter,
                ),
            )
            for _index, bars, diameter in selected
        )

    @staticmethod
    def _raw_shear_proposals(
        current: BeamInputs,
        seed: Candidate,
    ) -> tuple[Candidate, ...]:
        current_index = (
            current.shear.legs
            * current.shear.diameter_mm**2
            / max(current.shear.spacing_mm, 1.0)
            if current.shear.diameter_mm and current.shear.legs
            else 0.0
        )
        zero_demand = abs(float(current.actions.shear_force_kn)) < 1e-9
        options: list[tuple[float, int, int, float]] = []
        for diameter in (0, 10, 12, 16):
            for legs in ((0,) if diameter == 0 else (2, 3, 4, 5, 6, 8)):
                for spacing in (
                    600.0,
                    500.0,
                    400.0,
                    300.0,
                    250.0,
                    200.0,
                    175.0,
                    150.0,
                    125.0,
                    100.0,
                ):
                    if diameter == 0 and not zero_demand:
                        continue
                    index = (
                        legs * diameter**2 / max(spacing, 1.0)
                        if diameter and legs
                        else 0.0
                    )
                    if index >= current_index - 1e-9:
                        continue
                    options.append((index, diameter, legs, spacing))
        nearest = sorted(
            options,
            key=lambda row: (current_index - row[0], row[1], row[2], -row[3]),
        )[:10]
        if zero_demand and current_index > 0.0:
            # Removing unrequired links is the terminal zero-demand shear
            # cleanup.  A nearest-index slice otherwise drops this option as
            # "too far" from a heavily reinforced current arrangement and
            # forces a second Apply through SHEAR_OVERDESIGN_GOVERNS.
            zero_option = (0.0, 0, 0, current.shear.spacing_mm)
            nearest = [zero_option, *(row for row in nearest if row[1] != 0)][:10]
        return tuple(
            replace(
                seed,
                candidate_id=(
                    f"combined-raw-shear-{diameter}-{legs}-{int(spacing)}"
                ),
                proposal=replace(
                    seed.proposal,
                    shear_diameter_mm=diameter,
                    shear_legs=legs,
                    shear_spacing_mm=spacing,
                ),
            )
            for _index, diameter, legs, spacing in nearest
        )

    @staticmethod
    def _nearby_geometry(
        current: BeamInputs,
        steps: int,
        geometry_ceiling: BeamInputs | None = None,
    ) -> tuple[tuple[float, float], ...]:
        if current.width_locked:
            widths = (current.width_mm,)
        else:
            reduced_widths = tuple(
                value
                for value in (
                    current.width_mm - 25.0 * index for index in range(steps)
                )
                if value >= 150.0
            )
            restored_widths = (
                tuple(
                    value
                    for value in (
                        current.width_mm + 25.0 * index
                        for index in range(1, steps + 1)
                    )
                )
                if geometry_ceiling is not None
                else ()
            )
            widths = tuple(dict.fromkeys((*reduced_widths, *restored_widths)))
        if current.depth_locked:
            depths = (current.depth_mm,)
        else:
            reduced_depths = tuple(
                value
                for value in (
                    current.depth_mm - 25.0 * index for index in range(steps + 1)
                )
                if value >= 200.0
            )
            restored_depths = (
                tuple(
                    value
                    for value in (
                        current.depth_mm + 25.0 * index
                        for index in range(1, steps + 1)
                    )
                )
                if geometry_ceiling is not None
                else ()
            )
            depths = tuple(dict.fromkeys((*reduced_depths, *restored_depths)))
        ceiling_area = (
            geometry_ceiling.width_mm * geometry_ceiling.depth_mm
            if geometry_ceiling is not None
            else None
        )
        return tuple(
            (width, depth)
            for width in widths
            for depth in depths
            if depth <= 2.0 * width
            and (ceiling_area is None or width * depth <= ceiling_area)
        )

    @classmethod
    def _geometry_frontiers(
        cls,
        current: BeamInputs,
        steps: int,
        rounds: int,
        *,
        geometry_ceiling: BeamInputs | None = None,
    ) -> tuple[tuple[tuple[float, float], ...], ...]:
        """Return bounded, non-overlapping nearby geometry frontiers.

        Fast mode starts with its existing nearby standard dimensions.  It
        expands only when that frontier contains no target-band candidate.
        All candidates still belong to this family, share the same evaluation
        budget and participate in one final family-owned ranking.
        """

        frontiers: list[tuple[tuple[float, float], ...]] = []
        seen: set[tuple[float, float]] = set()
        for round_number in range(1, max(1, rounds) + 1):
            expanded = cls._nearby_geometry(
                current,
                steps * round_number,
                geometry_ceiling,
            )
            frontier = tuple(cell for cell in expanded if cell not in seen)
            if not frontier:
                break
            frontiers.append(frontier)
            seen.update(frontier)
        return tuple(frontiers)


__all__ = ["CombinedOverdesignPipeline"]
