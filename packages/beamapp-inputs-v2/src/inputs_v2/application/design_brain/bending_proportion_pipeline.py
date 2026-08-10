"""Bounded proportion-balancing pipeline for verified bending candidates."""

from __future__ import annotations

from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any, Callable

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain.bending_repair_policy import (
    generate_proportion_balance_specs,
)
from inputs_v2.application.design_brain_apply import Candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.design_preferences import DesignPreferenceProfile
from inputs_v2.engineering.reinforcement_policy import ratio_trigger, tension_ratio


Evaluate = Callable[..., Any]
RankKey = Callable[[BeamInputs, Candidate, EngineeringResult, float, float], tuple]


@dataclass(frozen=True)
class ProportionBalanceOutcome:
    candidate: Candidate
    updated_inputs: BeamInputs
    result: EngineeringResult
    reason: str
    metrics: dict[str, float | int | bool | tuple[str, ...]]


class BendingProportionPipeline:
    """Trigger, evaluate and select a bounded proportion-balancing repair."""

    def __init__(
        self,
        *,
        evaluate: Evaluate,
        rank_key: RankKey,
        preferences: DesignPreferenceProfile,
        stage_id: str = "reduce_geometry_and_redesign",
    ) -> None:
        self._evaluate = evaluate
        self._rank_key = rank_key
        self._stage_id = stage_id
        self._preferences = preferences

    def balance(
        self,
        current: BeamInputs,
        before: EngineeringResult,
        candidate: Candidate,
        updated_inputs: BeamInputs,
        after: EngineeringResult,
    ) -> ProportionBalanceOutcome:
        baseline_volume = candidate.proposal.width_mm * candidate.proposal.depth_mm
        baseline_steel = (
            candidate.proposal.bottom_bars
            * candidate.proposal.bottom_diameter_mm**2
        )
        provided_ast = float(
            before.families.get("bending", {}).get(
                "Ast_bot", baseline_steel * 0.7854
            )
            or 0.0
        )
        effective_depth = float(
            before.families.get("bending", {}).get(
                "effective_depth_mm",
                max(current.depth_mm - current.bottom.cover_mm, 1.0),
            )
            or 1.0
        )
        tension_ratio_value = tension_ratio(
            provided_ast, current.width_mm, effective_depth
        )
        trigger_reasons = self._trigger_reasons(
            current, candidate, tension_ratio_value
        )
        triggered = (
            not current.width_locked
            and not current.depth_locked
            and bool(trigger_reasons)
            and (
                baseline_volume
                > current.width_mm * current.depth_mm * 1.20
                or "high_depth_span_ratio" in trigger_reasons
                or tension_ratio_value < self._preferences.normal_low_ratio_trigger
            )
        )
        if not triggered:
            return ProportionBalanceOutcome(
                candidate,
                updated_inputs,
                after,
                "target_band_candidate",
                self._metrics(False, tension_ratio_value, ()),
            )

        started = perf_counter()
        cache: dict[
            tuple[float, float, int, int, tuple[int, ...]],
            EngineeringResult | None,
        ] = {}
        balanced: list[tuple[Candidate, EngineeringResult, float, float]] = []
        evaluations = 0
        cache_hits = 0
        for spec in generate_proportion_balance_specs(current, candidate):
            key = (
                spec.width_mm,
                spec.depth_mm,
                spec.bars,
                spec.diameter_mm,
                spec.row_counts,
            )
            if key not in cache:
                proposal = replace(
                    candidate.proposal,
                    width_mm=spec.width_mm,
                    depth_mm=spec.depth_mm,
                    bottom_bars=spec.bars,
                    bottom_diameter_mm=spec.diameter_mm,
                )
                trial = Candidate(
                    f"proportion-{int(spec.width_mm)}-{int(spec.depth_mm)}-{spec.bars}-N{spec.diameter_mm}",
                    current.revision,
                    current.content_hash,
                    proposal,
                    "Proportion-balancing trial.",
                    spec.row_counts,
                )
                evaluation = self._evaluate(
                    current,
                    trial,
                    stage_id=self._stage_id,
                    provisional=True,
                )
                cache[key] = evaluation.result if evaluation.usable else None
                evaluations += 1
            else:
                cache_hits += 1
            result = cache[key]
            if result is None or not complete_compliance(result):
                continue
            steel = spec.bars * spec.diameter_mm**2
            concrete_reduction = (
                1.0 - spec.width_mm * spec.depth_mm / baseline_volume
            )
            steel_increase = steel / max(baseline_steel, 1.0) - 1.0
            if concrete_reduction >= self._preferences.normal_concrete_reduction_threshold and (
                steel_increase <= self._preferences.normal_reinforcement_increase_limit
                or concrete_reduction >= self._preferences.substantial_concrete_reduction_threshold
            ):
                proposal = replace(
                    candidate.proposal,
                    width_mm=spec.width_mm,
                    depth_mm=spec.depth_mm,
                    bottom_bars=spec.bars,
                    bottom_diameter_mm=spec.diameter_mm,
                )
                trial = Candidate(
                    f"proportion-{int(spec.width_mm)}-{int(spec.depth_mm)}-{spec.bars}-N{spec.diameter_mm}",
                    current.revision,
                    current.content_hash,
                    proposal,
                    "Proportion-balanced section with a practical reinforcement increase.",
                    spec.row_counts,
                )
                util = float(
                    result.families.get("bending", {}).get("util", 0.0) or 0.0
                )
                edit_size = (
                    abs(spec.width_mm - current.width_mm) / 100.0
                    + abs(spec.depth_mm - current.depth_mm) / 100.0
                    + abs(spec.bars - current.bottom.bars)
                    + abs(spec.diameter_mm - current.bottom.diameter_mm) / 10.0
                    + max(0, len(spec.row_counts) - 1) * 0.25
                )
                balanced.append(
                    (trial, result, abs(util - 0.925), edit_size)
                )
        reason = "target_band_candidate"
        if balanced:
            candidate, after, _, _ = min(
                balanced,
                key=lambda item: self._rank_key(
                    current, item[0], item[1], item[2], item[3]
                ),
            )
            resolved = self._evaluate(
                current,
                candidate,
                stage_id=self._stage_id,
                provisional=True,
            )
            if resolved.usable:
                updated_inputs = resolved.outcome.inputs
            reason = "proportion_balanced_candidate"
        metrics = self._metrics(
            True,
            tension_ratio_value,
            tuple(trigger_reasons),
            evaluations=evaluations,
            cache_hits=cache_hits,
            elapsed_ms=round((perf_counter() - started) * 1000.0, 1),
        )
        return ProportionBalanceOutcome(
            candidate, updated_inputs, after, reason, metrics
        )

    def _trigger_reasons(
        self, current: BeamInputs, candidate: Candidate, ratio: float
    ) -> list[str]:
        reasons: list[str] = []
        if (
            candidate.proposal.width_mm > current.width_mm * 1.20
            or candidate.proposal.depth_mm > current.depth_mm * 1.20
        ):
            reasons.append("geometry_growth")
        if current.depth_mm / max(current.span_mm, 1.0) >= 0.35:
            reasons.append("high_depth_span_ratio")
        if candidate.proposal.bottom_bars <= current.bottom.bars + 1:
            reasons.append("near_minimum_longitudinal_reinforcement")
        ratio_reason = ratio_trigger(ratio, self._preferences)
        if ratio_reason:
            reasons.append(ratio_reason)
        if (
            abs(current.actions.shear_force_kn) > 0
            and current.shear.diameter_mm <= 12
        ):
            reasons.append("near_minimum_shear_reinforcement")
        return reasons

    @staticmethod
    def _metrics(
        triggered: bool,
        ratio: float,
        reasons: tuple[str, ...],
        *,
        evaluations: int = 0,
        cache_hits: int = 0,
        elapsed_ms: float = 0.0,
    ) -> dict[str, float | int | bool | tuple[str, ...]]:
        return {
            "proportion_triggered": triggered,
            "additional_evaluations": evaluations,
            "cache_hits": cache_hits,
            "tension_reinforcement_ratio": ratio,
            "elapsed_ms": elapsed_ms,
            "trigger_reasons": reasons,
        }


__all__ = ["BendingProportionPipeline", "ProportionBalanceOutcome"]
