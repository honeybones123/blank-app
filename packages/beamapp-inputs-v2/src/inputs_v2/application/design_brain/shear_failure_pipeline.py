"""Calculator-backed shear failure repair pipeline."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain.candidate_arrangements import with_practical_bottom_rows
from inputs_v2.application.design_brain.shear_repair_policy import generate_shear_repair_specs
from inputs_v2.application.design_brain_apply import Candidate, propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult

Calculate = Callable[[BeamInputs], EngineeringResult]
Evaluate = Callable[..., Any]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]
CompleteStage = Callable[[str], None]


class ShearFailurePipeline:
    """Evaluate the declared shear ladder and select one verified repair."""

    def __init__(
        self,
        *,
        calculate: Calculate,
        evaluate: Evaluate,
        rank_key: RankKey,
        stage_map: dict[str, str] | None = None,
        complete_stage: CompleteStage = lambda _stage_id: None,
    ) -> None:
        self._calculate = calculate
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._stage_map = stage_map or {}
        self._complete_stage = complete_stage

    def _stage(self, stage_id: str) -> str:
        return self._stage_map.get(stage_id, stage_id)

    def preview(self, current: BeamInputs) -> DesignBrainPreview:
        before = self._calculate(current)
        capacity = float(before.families.get("shear", {}).get("phi_Vu", 0.0))
        current_util = abs(float(current.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
        seed = propose_neutral_candidate(current)
        # Entry into this family is owned by the family classifier and includes
        # every authoritative shear check, not only headline capacity.  A
        # section may have phiVu >= V* while still failing the transverse-
        # reinforcement, minimum-link or spacing checks.  Rechecking headline
        # utilisation here created a second decision centre and suppressed the
        # repair ladder for those valid failure states.
        low, high = 0.85, 1.0
        trials: list[tuple[float, Candidate, BeamInputs, EngineeringResult, float]] = []
        for lane, changes, edit_size in generate_shear_repair_specs(current, current_util):
            candidate = Candidate(
                f"shear-only-{lane}-{len(trials)}",
                current.revision,
                current.content_hash,
                replace(seed.proposal, **changes),
                f"Shear-only ladder: {lane} repair toward 0.85–1.00 utilisation.",
            )
            stage_id = {
                "spacing": "repair_ligatures",
                "legs": "repair_ligatures",
                "diameter": "repair_ligatures",
                "width": "increase_width",
                "depth": "increase_depth_and_redesign",
                "coordinated_geometry": "increase_depth_and_redesign",
            }.get(lane, "repair_ligatures")
            variants = (
                with_practical_bottom_rows(candidate)
                if candidate.proposal.bottom_bars != current.bottom.bars
                else (candidate,)
            )
            for arranged_candidate in variants:
                evaluation = self._evaluate(
                    current, arranged_candidate, stage_id=self._stage(stage_id)
                )
                if "search_budget_exhausted" in evaluation.rejection_codes:
                    return self._select_best(current, before, seed, trials, low, high)
                if not evaluation.usable:
                    continue
                result = evaluation.result
                assert result is not None
                capacity = float(result.families.get("shear", {}).get("phi_Vu", 0.0))
                util = abs(float(evaluation.outcome.inputs.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
                in_band = low <= util <= high
                distance = 0.0 if in_band else abs(util - (low + high) / 2.0)
                trials.append((distance + (0.0 if in_band else 10.0), arranged_candidate, evaluation.outcome.inputs, result, edit_size))
                if in_band:
                    changed = tuple(
                        name for name, old, new in (
                            ("shear", current.shear, evaluation.outcome.inputs.shear),
                            ("bottom", current.bottom, evaluation.outcome.inputs.bottom),
                            ("width_mm", current.width_mm, evaluation.outcome.inputs.width_mm),
                            ("depth_mm", current.depth_mm, evaluation.outcome.inputs.depth_mm),
                        ) if old != new
                    )
                    return DesignBrainPreview(arranged_candidate, before, result, changed, True, "shear_target_band_candidate", low, high)
                break
        for stage_id in (
            "repair_ligatures",
            "increase_width",
            "increase_depth_and_redesign",
        ):
            self._complete_stage(self._stage(stage_id))
        return self._select_best(current, before, seed, trials, low, high)

    def _select_best(
        self,
        current: BeamInputs,
        before: EngineeringResult,
        seed: Candidate,
        trials: list[tuple[float, Candidate, BeamInputs, EngineeringResult, float]],
        low: float,
        high: float,
    ) -> DesignBrainPreview:
        if not trials:
            return DesignBrainPreview(seed, before, before, (), False, "no_valid_shear_repair", low, high)
        _, candidate, _, after, _ = min(
            trials,
            key=lambda row: self._rank_key(current, row[1], row[3], row[0], row[4]),
        )
        capacity = float(after.families.get("shear", {}).get("phi_Vu", 0.0))
        util = abs(float(current.actions.shear_force_kn)) / capacity if capacity > 0 else 0.0
        compliant = complete_compliance(after)
        accepted = util <= high and compliant
        reason = (
            "shear_target_band_candidate"
            if accepted and util >= low
            else "safe_shear_failure_repair"
            if accepted
            else "no_improving_shear_target_band_candidate"
        )
        changed = tuple(
            name for name, old, new in (
                ("bottom", current.bottom.bars, candidate.proposal.bottom_bars),
                ("width_mm", current.width_mm, candidate.proposal.width_mm),
                ("depth_mm", current.depth_mm, candidate.proposal.depth_mm),
            ) if old != new
        )
        changed = ("shear",) + changed
        return DesignBrainPreview(candidate, before, after, changed, accepted, reason, low, high)


__all__ = ["ShearFailurePipeline"]
