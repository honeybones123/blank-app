"""Calculator-backed shear overdesign cleanup pipeline."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain.candidate_arrangements import with_practical_bottom_rows
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain_apply import Candidate, propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult


Calculate = Callable[[BeamInputs], EngineeringResult]
Evaluate = Callable[..., Any]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]
CompleteStage = Callable[[str], None]
MergeMetrics = Callable[[dict[str, object]], None]


def _link_index(diameter_mm: int, legs: int, spacing_mm: float) -> float:
    """Comparable transverse-steel density for material-reduction checks."""

    if diameter_mm <= 0 or legs <= 0:
        return 0.0
    return legs * diameter_mm**2 / max(spacing_mm, 1.0)


class ShearOverdesignPipeline:
    """Reduce link density and optional width while preserving compliance."""

    def __init__(
        self,
        *,
        calculate: Calculate,
        evaluate: Evaluate,
        rank_key: RankKey,
        complete_stage: CompleteStage,
        merge_metrics: MergeMetrics = lambda _metrics: None,
    ) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._complete_stage = complete_stage
        self._merge_metrics = merge_metrics

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
        improving_rejections: dict[str, int] = {}

        def reject(*codes: str) -> None:
            for code in codes:
                improving_rejections[code] = improving_rejections.get(code, 0) + 1

        def publish_metrics() -> None:
            self._merge_metrics(
                {"improving_rejection_counts": dict(sorted(improving_rejections.items()))}
            )
        current_link_index = _link_index(
            current.shear.diameter_mm,
            current.shear.legs,
            current.shear.spacing_mm,
        )
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
                publish_metrics()
                return DesignBrainPreview(candidate, before, evaluation.result, ("shear",), True, "safe_overdesign_cleanup", 0.85, 1.0)
            reject(*evaluation.rejection_codes)

        trials: list[tuple[float, Candidate, EngineeringResult, float]] = []
        for spacing in (100.0, 125.0, 150.0, 175.0, 200.0, 250.0, 300.0, 400.0, 500.0, 600.0):
            for diameter in (0, 10, 12, 16):
                for legs in ((0,) if diameter == 0 else (2, 4, 6, 8)):
                    proposed_link_index = _link_index(diameter, legs, spacing)
                    # Overdesign may only publish a real material reduction.
                    # This also excludes the unchanged link arrangement from
                    # the candidate gateway and prevents a denser arrangement
                    # being mistaken for optimisation.
                    if proposed_link_index >= current_link_index - 1e-9:
                        continue
                    if diameter == 0 and not zero_demand:
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
                        reject(*evaluation.rejection_codes)
                        continue
                    result = evaluation.result
                    assert result is not None
                    capacity = float(result.families.get("shear", {}).get("phi_Vu", 0.0) or 0.0)
                    util = abs(float(current.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
                    if util <= 1.0 and complete_compliance(result):
                        trials.append((abs(util - 0.925), candidate, result, proposed_link_index))
                        if util <= current_util + 1e-9 and not zero_demand:
                            reject("no_utilisation_improvement")
        self._complete_stage("increase_spacing")
        self._complete_stage("reduce_ligature_size_or_legs")
        self._complete_stage("remove_unrequired_ligatures")
        if not current.width_locked:
            link_seeds = [seed, *(row[1] for row in sorted(trials, key=lambda row: row[0])[:8])]
            for width in range(int(current.width_mm) - 25, 149, -25):
                for link_seed in link_seeds:
                    raw = Candidate(
                        f"shear-overdesign-width-{width}-{link_seed.candidate_id}",
                        current.revision,
                        current.content_hash,
                        replace(link_seed.proposal, width_mm=float(width)),
                        "Shear overdesign cleanup: reduce width and redesign the reinforcement while preserving compliance.",
                    )
                    for candidate in with_practical_bottom_rows(raw):
                        evaluation = self._evaluate(
                            current, candidate, stage_id="reduce_width_and_redesign"
                        )
                        if not evaluation.usable or evaluation.result is None:
                            reject(*evaluation.rejection_codes)
                            continue
                        result = evaluation.result
                        capacity = float(result.families.get("shear", {}).get("phi_Vu", 0.0) or 0.0)
                        util = abs(float(current.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
                        if util <= 1.0 and complete_compliance(result):
                            trials.append((abs(util - 0.925), candidate, result, abs(width - current.width_mm) / 100))
                            break
        self._complete_stage("reduce_width_and_redesign")
        # No candidate calculation is necessary when every permitted shear
        # move is structurally absent: links are already off and width is at
        # its contractual minimum (or locked).  Record that fact explicitly
        # so exact-stop proof does not depend on inventing a fake candidate
        # attempt merely to make the counter non-zero.
        empty_search_space_proven = bool(
            current_link_index <= 1e-9
            and (current.width_locked or current.width_mm <= 150.0 + 1e-9)
        )
        if empty_search_space_proven:
            self._merge_metrics({"empty_search_space_proven": True})
        publish_metrics()
        if not trials:
            return DesignBrainPreview(
                seed,
                before,
                before,
                (),
                False,
                "verified_shear_constraints_exhausted",
                0.85,
                1.0,
            )
        _, candidate, after, _ = min(
            trials,
            key=lambda row: self._rank_key(current, row[1], row[2], row[0], row[3]),
        )
        capacity = float(after.families.get("shear", {}).get("phi_Vu", 0.0) or 0.0)
        util = abs(float(current.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
        material_cleanup = (
            (
                candidate.proposal.shear_diameter_mm != current.shear.diameter_mm
                or candidate.proposal.shear_legs != current.shear.legs
                or candidate.proposal.shear_spacing_mm != current.shear.spacing_mm
                or candidate.proposal.width_mm != current.width_mm
            )
            and float(after.families.get("bending", {}).get("util", 0.0) or 0.0) <= 1.0
        )
        accepted = (
            material_cleanup
            and (
                (util > current_util + 1e-9 and util <= 1.0)
                or zero_demand
            )
            and complete_compliance(after)
        )
        reason = (
            "safe_overdesign_cleanup"
            if accepted and util < 0.85
            else (
                "shear_overdesign_cleanup"
                if accepted
                else "verified_shear_constraints_exhausted"
            )
        )
        changed_items: list[str] = []
        if (
            current.shear.diameter_mm,
            current.shear.legs,
            current.shear.spacing_mm,
        ) != (
            candidate.proposal.shear_diameter_mm,
            candidate.proposal.shear_legs,
            candidate.proposal.shear_spacing_mm,
        ):
            changed_items.append("shear")
        if current.width_mm != candidate.proposal.width_mm:
            changed_items.append("width_mm")
        if (current.bottom.bars, current.bottom.diameter_mm) != (
            candidate.proposal.bottom_bars,
            candidate.proposal.bottom_diameter_mm,
        ):
            changed_items.append("bottom")
        changed = tuple(changed_items)
        return DesignBrainPreview(candidate, before, after, changed, accepted, reason, 0.85, 1.0)


__all__ = ["ShearOverdesignPipeline"]
