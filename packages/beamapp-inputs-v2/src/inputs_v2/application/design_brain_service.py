"""Typed, calculator-backed Design Brain orchestration for V2."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from time import perf_counter

from inputs_v2.application.calculation_coordinator import CalculationCoordinator
from inputs_v2.application.design_brain_apply import Candidate, ApplyOutcome, apply_candidate, propose_neutral_candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.design_preferences import (
    DEFAULT_DESIGN_PREFERENCES,
    DesignPreferenceProfile,
)
from inputs_v2.domain.serviceability_source import ServiceabilityActionSource
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator
from inputs_v2.engineering.reinforcement_fit import practical_row_counts
from inputs_v2.application.candidate_evaluation import (
    CandidateEvaluation,
    complete_compliance as _complete_compliance,
    evaluate_candidate,
)
from inputs_v2.application.design_brain.search_profile import SearchKind, SearchProfile
from inputs_v2.application.design_brain.candidate_ranking import (
    candidate_evidence,
    candidate_rank_key,
)
from inputs_v2.application.ranking_policy import CandidateEvidence
from inputs_v2.application.design_brain.preview import DesignBrainPreview
from inputs_v2.application.design_brain.serviceability_pipeline import ServiceabilityCandidatePipeline
from inputs_v2.application.design_brain.combined_overdesign_pipeline import CombinedOverdesignPipeline
from inputs_v2.application.design_brain.shear_failure_pipeline import ShearFailurePipeline
from inputs_v2.application.design_brain.bending_overdesign_pipeline import BendingOverdesignPipeline
from inputs_v2.application.design_brain.shear_overdesign_pipeline import ShearOverdesignPipeline
from inputs_v2.application.design_brain.combined_failure_pipeline import CombinedFailurePipeline
from inputs_v2.application.design_brain.bending_failure_pipeline import BendingFailurePipeline
from inputs_v2.application.design_brain.bending_proportion_pipeline import BendingProportionPipeline
from inputs_v2.application.design_brain.mixed_pipelines import (
    BendingFailureShearCleanupPipeline,
    ShearFailureBendingOptimisePipeline,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from inputs_v2.application.design_brain.family_owners import FamilyContract
    from inputs_v2.application.design_brain_decision import FamilyDecision
    from inputs_v2.application.design_brain.family_context import FamilyRunContext


class DesignBrainService:
    """Generate and evaluate proposals without accessing UI or session state."""

    def __init__(
        self,
        search_profile: SearchProfile | None = None,
        preference_profile: DesignPreferenceProfile | None = None,
    ) -> None:
        self._calculator = CalculationCoordinator(EngineeringCalculator())
        self.last_search_metrics: dict[str, float | int | bool] = {"proportion_triggered": False, "additional_evaluations": 0}
        self._active_family_contract = None
        self._active_family_current: BeamInputs | None = None
        self._active_family_result: EngineeringResult | None = None
        self._calculation_cache: dict[tuple[str, str], EngineeringResult | None] = {}
        self.search_profile = search_profile or SearchProfile()
        self.preference_profile = preference_profile or DEFAULT_DESIGN_PREFERENCES

    @contextmanager
    def family_contract(
        self,
        contract: "FamilyContract",
        context: "FamilyRunContext",
    ) -> "Iterator[None]":
        """Bind family-owned ranking rules for exactly one ladder execution."""

        previous = self._active_family_contract
        previous_current = self._active_family_current
        previous_result = self._active_family_result
        previous_preferences = self.preference_profile
        self._active_family_contract = contract
        self._active_family_current = context.current
        self._active_family_result = context.current_result
        self.preference_profile = context.preferences
        started = perf_counter()
        self.last_search_metrics = {
            "proportion_triggered": False,
            "additional_evaluations": 0,
            "candidates_attempted": 0,
            "candidates_valid": 0,
            "attempted_stage_ids": (),
            "completed_stage_ids": (),
            "stage_attempt_counts": {},
            "stage_valid_counts": {},
            "stage_rejections": {},
            "stage_stop_reasons": {},
            "rejection_counts": {},
            "candidate_records": [],
            "cache_hits": 0,
            "cache_misses": 0,
            "preference_profile_id": context.preferences.preference_profile_id,
            "preference_profile_version": context.preferences.preference_profile_version,
        }
        try:
            yield
        finally:
            self.last_search_metrics["elapsed_ms"] = round(
                (perf_counter() - started) * 1000.0, 3
            )
            self._active_family_contract = previous
            self._active_family_current = previous_current
            self._active_family_result = previous_result
            self.preference_profile = previous_preferences

    def complete_stage(self, stage_id: str, stop_reason: str | None = None) -> None:
        """Record that a family-owned stage was fully enumerated.

        Merely attempting a candidate is not exhaustion evidence.  Pipelines
        call this only after their ordered generator has completed.
        """

        if self._active_family_contract is None:
            # Direct preview helpers are retained for isolated pipeline tests.
            # They do not publish exact-stop evidence; only the orchestrator's
            # family-bound execution may do that.
            return
        declared = {stage.stage_id for stage in self._active_family_contract.ladder_stages}
        if stage_id not in declared:
            raise ValueError(
                f"Family {self._active_family_contract.family.value} does not own stage {stage_id}"
            )
        reasons = dict(self.last_search_metrics.get("stage_stop_reasons", {}) or {})
        if bool(self.last_search_metrics.get("budget_exhausted", False)):
            reasons[stage_id] = "search_budget_exhausted"
            self.last_search_metrics["stage_stop_reasons"] = reasons
            return

        stage = next(
            item
            for item in self._active_family_contract.ladder_stages
            if item.stage_id == stage_id
        )
        if stop_reason is None:
            locks: list[str] = []
            current = self._active_family_current
            if current is not None:
                if "width_mm" in stage.permitted_changes and current.width_locked:
                    locks.append("width_locked")
                if "depth_mm" in stage.permitted_changes and current.depth_locked:
                    locks.append("depth_locked")
            attempt_counts = dict(
                self.last_search_metrics.get("stage_attempt_counts", {}) or {}
            )
            geometry_only = set(stage.permitted_changes) <= {"width_mm", "depth_mm"}
            if locks and geometry_only and int(attempt_counts.get(stage_id, 0)) == 0:
                stop_reason = "user_lock_prevented_stage:" + ",".join(locks)
            elif locks:
                stop_reason = "search_space_enumerated_with:" + ",".join(locks)
            else:
                stop_reason = "search_space_enumerated"
        completed = list(self.last_search_metrics.get("completed_stage_ids", ()) or ())
        if stage_id not in completed:
            completed.append(stage_id)
        self.last_search_metrics["completed_stage_ids"] = tuple(completed)
        reasons[stage_id] = stop_reason
        self.last_search_metrics["stage_stop_reasons"] = reasons

    def merge_search_metrics(self, metrics: dict[str, object]) -> None:
        """Merge non-authoritative counters without erasing gateway evidence."""

        protected = {
            "attempted_stage_ids",
            "completed_stage_ids",
            "stage_attempt_counts",
            "stage_valid_counts",
            "stage_rejections",
            "stage_stop_reasons",
            "rejection_counts",
            "candidate_records",
            "candidates_attempted",
            "candidates_valid",
        }
        self.last_search_metrics.update(
            {key: value for key, value in metrics.items() if key not in protected}
        )

    def preview_terminal(self, current: BeamInputs, reason: str) -> DesignBrainPreview:
        """Return a no-mutation preview for an already terminal family."""

        result = self._calculator.calculate_current(current).result
        if result is None:
            raise ValueError("calculation result is stale")
        seed = propose_neutral_candidate(current)
        candidate = replace(
            seed,
            candidate_id=f"terminal-{reason}",
            rationale="Retain the verified current design.",
        )
        if self._active_family_contract is not None:
            self.complete_stage(
                self._active_family_contract.ladder_stages[0].stage_id
            )
        return DesignBrainPreview(candidate, result, result, (), False, reason)

    def preview_target_band(self, current: BeamInputs) -> DesignBrainPreview:
        """Run only the target family's bounded proportion-balancing stage."""

        before = self._calculator.calculate_current(current).result
        if before is None:
            raise ValueError("calculation result is stale")
        seed = propose_neutral_candidate(current)
        outcome = BendingProportionPipeline(
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            preferences=self.preference_profile,
            stage_id="proportion_balance_target_band",
        ).balance(current, before, seed, current, before)
        self.merge_search_metrics(outcome.metrics)
        triggered = bool(outcome.metrics.get("proportion_triggered", False))
        if not triggered:
            return DesignBrainPreview(
                seed, before, before, (), False, "target_band_candidate"
            )
        self.complete_stage(
            "proportion_balance_target_band",
            "proportion_balance_candidate_found"
            if outcome.reason == "proportion_balanced_candidate"
            else "bounded_proportion_search_exhausted",
        )
        if outcome.reason != "proportion_balanced_candidate":
            return DesignBrainPreview(
                seed, before, before, (), False, "proportion_balance_exhausted"
            )
        changed = self._candidate_change_keys(current, outcome.candidate)
        accepted = bool(changed) and _complete_compliance(outcome.result)
        return DesignBrainPreview(
            outcome.candidate,
            before,
            outcome.result,
            changed,
            accepted,
            "proportion_balanced_candidate",
        )

    @staticmethod
    def _has_sls(inputs: BeamInputs) -> bool:
        s = inputs.serviceability
        return any(abs(float(v or 0.0)) > 1e-12 for v in (s.moment_knm, s.shear_kn, s.permanent_udl_knm_per_m, s.imposed_udl_knm_per_m, s.equivalent_udl_knm_per_m))

    def _calculate_for_design_brain(self, inputs: BeamInputs) -> EngineeringResult | None:
        """Use a private provisional SLS proxy only for candidate ranking."""
        proxy_active = not self._has_sls(inputs) and inputs.serviceability.use_uls_fallback
        proxy_ratio = float(self.preference_profile.provisional_sls_uls_ratio)
        cache_key = (
            inputs.content_hash,
            f"proxy-{proxy_ratio:.6f}" if proxy_active else "explicit-sls",
        )
        if cache_key in self._calculation_cache:
            self.last_search_metrics["cache_hits"] = int(
                self.last_search_metrics.get("cache_hits", 0) or 0
            ) + 1
            return self._calculation_cache[cache_key]
        if int(self.last_search_metrics.get("cache_misses", 0) or 0) >= self._full_evaluation_budget():
            self.last_search_metrics["budget_exhausted"] = True
            self.last_search_metrics["budget_skipped_candidates"] = int(
                self.last_search_metrics.get("budget_skipped_candidates", 0) or 0
            ) + 1
            return None
        self.last_search_metrics["cache_misses"] = int(
            self.last_search_metrics.get("cache_misses", 0) or 0
        ) + 1
        if not proxy_active:
            result = self._calculator.calculate_current(inputs).result
            self._calculation_cache[cache_key] = result
            return result
        self.last_search_metrics["sls_source"] = (
            ServiceabilityActionSource.PROVISIONAL_ULS_RATIO_PROXY.value
        )
        self.last_search_metrics["sls_proxy_ratio"] = proxy_ratio
        provisional = replace(
            inputs,
            serviceability=replace(
                inputs.serviceability,
                moment_knm=proxy_ratio * float(inputs.actions.bending_moment_knm),
                shear_kn=proxy_ratio * float(inputs.actions.shear_force_kn),
                use_uls_fallback=True,
            ),
        )
        result = self._calculator.calculate_current(provisional).result
        if result is None:
            self._calculation_cache[cache_key] = None
            return None
        # The proxy is an internal calculation context, not a different
        # canonical input revision.  Never leak its synthetic input hash into
        # the published proposal contract.
        result = replace(
            result,
            source_revision=inputs.revision,
            source_hash=inputs.content_hash,
            families={
                **result.families,
                "serviceability": {
                    **result.families.get("serviceability", {}),
                    "status": (
                        "PROVISIONAL PASS"
                        if str(result.families.get("serviceability", {}).get("status", "")).upper() == "PASS"
                        else result.families.get("serviceability", {}).get("status")
                    ),
                    "action_source": ServiceabilityActionSource.PROVISIONAL_ULS_RATIO_PROXY.value,
                    "proxy_ratio": proxy_ratio,
                },
                "crack_control": {
                    **result.families.get("crack_control", {}),
                    "status": (
                        "PROVISIONAL PASS"
                        if str(result.families.get("crack_control", {}).get("status", "")).upper() == "PASS"
                        else result.families.get("crack_control", {}).get("status")
                    ),
                    "action_source": ServiceabilityActionSource.PROVISIONAL_ULS_RATIO_PROXY.value,
                    "proxy_ratio": proxy_ratio,
                },
            },
        )
        self._calculation_cache[cache_key] = result
        return result

    def _full_evaluation_budget(self) -> int:
        kind = (
            self._active_family_contract.search_kind
            if self._active_family_contract is not None
            else SearchKind.REPAIR
        )
        return self.search_profile.evaluation_budget(kind)

    def publish_preview(
        self,
        current: BeamInputs,
        preview: DesignBrainPreview,
    ) -> DesignBrainPreview:
        """Replace private proxy evidence with the canonical display result.

        Candidate acceptance is decided only by :meth:`_evaluate`.  This
        method performs no acceptance, ranking or family logic; it calculates
        the single selected proposal in the ordinary application context so
        synthetic SLS actions never appear in summaries, saved inputs or the
        result displayed beside the Apply action.
        """

        # With genuine SLS actions the family evaluation already used the
        # ordinary authoritative calculator.  Recalculating the selected
        # candidate here created a second post-family decision path: the
        # family could select a verified candidate and a later calculation
        # could replace its evidence and suppress Apply.  Preserve the exact
        # result that the family evaluated and ranked.
        if self._has_sls(current):
            return preview

        # A second calculation is required only for the private 0.60 ULS
        # proxy.  It strips synthetic SLS actions from the displayed and
        # published result without changing the family-owned selection.
        outcome = apply_candidate(current, preview.candidate)
        if not outcome.applied:
            return preview
        result = self._calculator.calculate_current(outcome.inputs).result
        if result is None:
            return preview
        return replace(preview, after=result)

    def _evaluate(
        self,
        current: BeamInputs,
        candidate: Candidate,
        *,
        stage_id: str,
        provisional: bool = False,
    ):
        """Evaluate and count every family candidate through one pipeline."""
        if not stage_id:
            raise ValueError("Every Design Brain candidate must identify its owning ladder stage")
        if self._active_family_contract is not None:
            declared = {
                stage.stage_id for stage in self._active_family_contract.ladder_stages
            }
            if stage_id not in declared:
                raise ValueError(
                    f"Family {self._active_family_contract.family.value} does not own stage {stage_id}"
                )
        if bool(self.last_search_metrics.get("budget_exhausted", False)):
            self.last_search_metrics["budget_skipped_candidates"] = int(
                self.last_search_metrics.get("budget_skipped_candidates", 0) or 0
            ) + 1
            return CandidateEvaluation(
                candidate,
                ApplyOutcome(False, "search_budget_exhausted", current),
                None,
                False,
                ("search_budget_exhausted",),
            )
        attempted_stage_ids = list(self.last_search_metrics.get("attempted_stage_ids", ()) or ())
        if stage_id not in attempted_stage_ids:
            attempted_stage_ids.append(stage_id)
        self.last_search_metrics["attempted_stage_ids"] = tuple(attempted_stage_ids)
        stage_attempt_counts = dict(self.last_search_metrics.get("stage_attempt_counts", {}) or {})
        stage_attempt_counts[stage_id] = int(stage_attempt_counts.get(stage_id, 0)) + 1
        self.last_search_metrics["stage_attempt_counts"] = stage_attempt_counts
        self.last_search_metrics["candidates_attempted"] = int(self.last_search_metrics.get("candidates_attempted", 0)) + 1
        # Candidate validation always includes the private proxy when genuine
        # SLS actions are absent. ``provisional`` remains temporarily accepted
        # at the call boundary while family pipelines migrate, but no family
        # may bypass the universal validation calculation.
        evaluation = evaluate_candidate(current, candidate, self._calculate_for_design_brain)
        candidate_records = list(
            self.last_search_metrics.get("candidate_records", []) or []
        )
        hard_congestion_codes = tuple(
            code
            for code in evaluation.rejection_codes
            if code in {
                "reinforcement_fit_failed",
                "cover_failed",
                "clear_spacing_failed",
                "row_spacing_failed",
                "anchorage_failed",
                "constructability_limit_failed",
            }
        )
        congestion_class = "low"
        if evaluation.result is not None:
            congestion_class = str(
                evaluation.result.families.get("reinforcement_fit", {}).get(
                    "congestion_class", "low"
                )
            ).lower()
        soft_congestion_score = (
            {
                "moderate": self.preference_profile.soft_congestion_moderate_penalty,
                "high": self.preference_profile.soft_congestion_high_penalty,
            }.get(congestion_class, 0.0)
            if not hard_congestion_codes
            else 0.0
        )
        candidate_records.append(
            CandidateEvidence(
                candidate_id=candidate.candidate_id,
                compliant=evaluation.mandatory_compliance,
                mandatory_checks_complete=evaluation.mandatory_compliance,
                stage_id=stage_id,
                proposed_changes=self._candidate_change_keys(current, candidate),
                row_counts=tuple(candidate.row_counts),
                calculated_checks=evaluation.calculated_checks,
                accepted_by_mandatory_checks=evaluation.mandatory_compliance,
                rejection_codes=evaluation.rejection_codes,
                hard_congestion_rejection_codes=hard_congestion_codes,
                soft_congestion_score=soft_congestion_score,
                soft_congestion_reasons=(
                    (f"{congestion_class}_congestion",)
                    if soft_congestion_score > 0.0
                    else ()
                ),
                elapsed_ms=round(float(evaluation.elapsed_ms), 3),
            )
        )
        self.last_search_metrics["candidate_records"] = candidate_records
        if evaluation.usable:
            self.last_search_metrics["candidates_valid"] = int(self.last_search_metrics.get("candidates_valid", 0)) + 1
            stage_valid_counts = dict(
                self.last_search_metrics.get("stage_valid_counts", {}) or {}
            )
            stage_valid_counts[stage_id] = int(
                stage_valid_counts.get(stage_id, 0)
            ) + 1
            self.last_search_metrics["stage_valid_counts"] = stage_valid_counts
        else:
            rejection_counts = dict(self.last_search_metrics.get("rejection_counts", {}) or {})
            stage_rejections = dict(self.last_search_metrics.get("stage_rejections", {}) or {})
            stage_counts = dict(stage_rejections.get(stage_id, {}) or {})
            for code in evaluation.rejection_codes:
                rejection_counts[code] = int(rejection_counts.get(code, 0)) + 1
                stage_counts[code] = int(stage_counts.get(code, 0)) + 1
            self.last_search_metrics["rejection_counts"] = rejection_counts
            stage_rejections[stage_id] = stage_counts
            self.last_search_metrics["stage_rejections"] = stage_rejections
        return evaluation

    @staticmethod
    def _candidate_change_keys(
        current: BeamInputs,
        candidate: Candidate,
    ) -> tuple[str, ...]:
        """Describe proposal mutations without interpreting their purpose."""

        proposal = candidate.proposal
        comparisons = (
            ("width_mm", current.width_mm, proposal.width_mm),
            ("depth_mm", current.depth_mm, proposal.depth_mm),
            ("bottom_bars", current.bottom.bars, proposal.bottom_bars),
            (
                "bottom_diameter_mm",
                current.bottom.diameter_mm,
                proposal.bottom_diameter_mm,
            ),
            ("shear_diameter_mm", current.shear.diameter_mm, proposal.shear_diameter_mm),
            ("shear_legs", current.shear.legs, proposal.shear_legs),
            ("shear_spacing_mm", current.shear.spacing_mm, proposal.shear_spacing_mm),
        )
        changes = [
            name for name, before, after in comparisons if before != after
        ]
        current_rows = (
            tuple(row.bar_count for row in current.bottom_arrangement.rows)
            if current.bottom_arrangement is not None
            else (int(current.bottom.bars),)
        )
        current_row_diameters = (
            tuple(
                float(row.bar_diameter_mm or current.bottom.diameter_mm)
                for row in current.bottom_arrangement.rows
            )
            if current.bottom_arrangement is not None
            else (float(current.bottom.diameter_mm),)
        )
        candidate_rows = candidate.row_counts or (
            int(candidate.proposal.bottom_bars),
        )
        candidate_row_diameters = candidate.row_diameters_mm or tuple(
            float(candidate.proposal.bottom_diameter_mm)
            for _ in candidate_rows
        )
        if tuple(candidate_rows) != current_rows:
            changes.append("bottom_row_counts")
        if tuple(candidate_row_diameters) != current_row_diameters:
            changes.append("bottom_row_diameters_mm")
        return tuple(changes)

    def _rank_key(
        self,
        current: BeamInputs,
        candidate: Candidate,
        result: EngineeringResult,
        target_distance: float,
        edit_size: float,
    ) -> tuple:
        """Use only the selected family's complete contract-bound policy."""
        if self._active_family_contract is None or self._active_family_result is None:
            raise RuntimeError("candidate ranking requires a selected family contract")
        evidence = candidate_evidence(
            current,
            candidate,
            result,
            target_distance,
            edit_size,
            family_contract=self._active_family_contract,
            current_result=self._active_family_result,
            preferences=self.preference_profile,
        )
        records = list(self.last_search_metrics.get("candidate_records", ()) or ())
        for index in range(len(records) - 1, -1, -1):
            if records[index].candidate_id == candidate.candidate_id:
                records[index] = replace(
                    records[index],
                    new_near_failure_count=evidence.new_near_failure_count,
                    constructability_penalty=evidence.constructability_penalty,
                    hard_congestion_rejection_codes=evidence.hard_congestion_rejection_codes,
                    soft_congestion_score=evidence.soft_congestion_score,
                    soft_congestion_reasons=evidence.soft_congestion_reasons,
                    near_limit_evidence=evidence.near_limit_evidence,
                    geometry_change_penalty=evidence.geometry_change_penalty,
                    material_quantity=evidence.material_quantity,
                    target_distance=evidence.target_distance,
                    edit_count=evidence.edit_count,
                )
                break
        self.last_search_metrics["candidate_records"] = records
        return candidate_rank_key(
            current,
            candidate,
            result,
            target_distance,
            edit_size,
            family_contract=self._active_family_contract,
            current_result=self._active_family_result,
            preferences=self.preference_profile,
        )

    def preview(self, current: BeamInputs) -> DesignBrainPreview:
        outcome = BendingFailurePipeline(
            calculate=lambda inputs: self._calculator.calculate_current(inputs).result,
            evaluate=self._evaluate,
            complete_stage=self.complete_stage,
            rank_key=self._rank_key,
            preferences=self.preference_profile,
        ).preview(current)
        if outcome.metrics is not None:
            self.merge_search_metrics(outcome.metrics)
        return outcome.preview
    def preview_shear_only(self, current: BeamInputs) -> DesignBrainPreview:
        """Apply the V1 SHEAR_FAIL_GOVERNS order: spacing, legs, diameter, depth, width."""
        pipeline = ShearFailurePipeline(
            calculate=lambda inputs: self._calculator.calculate_current(inputs).result,
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            complete_stage=self.complete_stage,
        )
        return pipeline.preview(current)

    def preview_combined_failure(self, current: BeamInputs) -> DesignBrainPreview:
        """Repair simultaneous bending and shear failure with one atomic candidate."""
        return CombinedFailurePipeline(
            calculate=lambda inputs: self._calculator.calculate_current(inputs).result,
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            preferences=self.preference_profile,
            complete_stage=self.complete_stage,
        ).preview(current)
    def preview_bending_failure_shear_cleanup(self, current: BeamInputs) -> DesignBrainPreview:
        """Distinct mixed-family entry point.

        The ordered mixed ladder is contract-owned even while it reuses the
        established bending repair engine for its first stage.  Keeping a
        separate entry point prevents the mixed family silently collapsing
        back into the bending-only owner during later ladder changes.
        """
        return BendingFailureShearCleanupPipeline(
            calculate=lambda inputs: self._calculator.calculate_current(inputs).result,
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            preferences=self.preference_profile,
            complete_stage=self.complete_stage,
            budget_exhausted=lambda: bool(
                self.last_search_metrics.get("budget_exhausted", False)
            ),
        ).preview(current)

    def preview_shear_failure_bending_optimise(self, current: BeamInputs) -> DesignBrainPreview:
        """Distinct mixed-family entry point for shear repair plus bending cleanup."""
        return ShearFailureBendingOptimisePipeline(
            calculate=lambda inputs: self._calculator.calculate_current(inputs).result,
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            complete_stage=self.complete_stage,
            budget_exhausted=lambda: bool(
                self.last_search_metrics.get("budget_exhausted", False)
            ),
        ).preview(current)

    def preview_bending_overdesign(self, current: BeamInputs) -> DesignBrainPreview:
        """V1 bending-overdesign cleanup: reduce bars/diameter, nearest safe target."""
        outcome = BendingOverdesignPipeline(
            calculate=lambda inputs: self._calculator.calculate_current(inputs).result,
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            complete_stage=self.complete_stage,
            preferences=self.preference_profile,
            max_consecutive_infeasible=self.search_profile.max_consecutive_infeasible,
        ).preview(current)
        self.merge_search_metrics(outcome.metrics)
        return outcome.preview
    def preview_shear_overdesign(self, current: BeamInputs) -> DesignBrainPreview:
        """V1 shear-overdesign cleanup: spacing, diameter, legs, then removal."""
        return ShearOverdesignPipeline(
            calculate=lambda inputs: self._calculator.calculate_current(inputs).result,
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            complete_stage=self.complete_stage,
            merge_metrics=self.merge_search_metrics,
        ).preview(current)
    def preview_geometry_detailing(self, current: BeamInputs) -> DesignBrainPreview:
        """Repair arrangement fit and geometry without partial edits."""
        before = self._calculator.calculate_current(current).result
        assert before is not None
        seed = propose_neutral_candidate(current)
        current_rows = tuple(
            row.bar_count for row in current.bottom_arrangement.rows
        ) if current.bottom_arrangement is not None else (current.bottom.bars,)
        for rows in practical_row_counts(current.bottom.bars):
            if rows == current_rows:
                continue
            candidate = replace(
                seed,
                candidate_id="geometry-detailing-arrangement-" + "-".join(map(str, rows)),
                rationale="Rearrange the bottom reinforcement into practical rows.",
                row_counts=rows,
            )
            evaluation = self._evaluate(
                current, candidate, stage_id="repair_arrangement"
            )
            if evaluation.usable and evaluation.result is not None:
                return DesignBrainPreview(
                    candidate,
                    before,
                    evaluation.result,
                    ("bottom",),
                    True,
                    "reinforcement_arrangement_repaired",
                    0.85,
                    1.0,
                )
        self.complete_stage("repair_arrangement")
        geometry_trials: list[tuple[float, Candidate, EngineeringResult]] = []
        widths = (
            (current.width_mm,)
            if current.width_locked
            else tuple(current.width_mm + 25.0 * index for index in range(0, 25))
        )
        for width in widths:
            depths = [current.depth_mm]
            if current.depth_mm > 2.0 * width and not current.depth_locked:
                depths.insert(0, max(200.0, 2.0 * width))
            for depth in dict.fromkeys(depths):
                if depth > 2.0 * width:
                    continue
                # Geometry and longitudinal detailing are one coordinated
                # repair.  A dimension-only candidate is not useful when the
                # current reinforcement also fails minimum steel or fit.
                # Enumerate standard bar arrangements here, then let the
                # universal calculation gateway decide compliance.
                arrangements = [
                    (current.bottom.bars, current.bottom.diameter_mm),
                    *(
                        (bar_count, diameter)
                        for diameter in (10, 12, 16, 20, 24, 28, 32, 36, 40)
                        for bar_count in range(2, 13)
                    ),
                ]
                for bar_count, diameter in dict.fromkeys(arrangements):
                    for rows in practical_row_counts(bar_count):
                        candidate = replace(
                            seed,
                            candidate_id=(
                                f"geometry-detailing-{int(width)}-{int(depth)}-"
                                f"{bar_count}N{diameter}-rows{'-'.join(map(str, rows))}"
                            ),
                            proposal=replace(
                                seed.proposal,
                                width_mm=width,
                                depth_mm=depth,
                                bottom_bars=bar_count,
                                bottom_diameter_mm=diameter,
                            ),
                            rationale="Repair geometry and reinforcement fit in one verified revision.",
                            row_counts=rows,
                        )
                        evaluation = self._evaluate(
                            current, candidate, stage_id="repair_geometry"
                        )
                        if "search_budget_exhausted" in evaluation.rejection_codes:
                            return DesignBrainPreview(
                                seed,
                                before,
                                before,
                                (),
                                False,
                                "search_budget_exhausted",
                            )
                        if evaluation.usable and evaluation.result is not None:
                            edit = (
                                abs(width - current.width_mm)
                                + abs(depth - current.depth_mm)
                                + 5.0 * abs(bar_count - current.bottom.bars)
                                + abs(diameter - current.bottom.diameter_mm)
                            )
                            geometry_trials.append((edit, candidate, evaluation.result))
                            break
                    if geometry_trials and geometry_trials[-1][1].proposal.width_mm == width and geometry_trials[-1][1].proposal.depth_mm == depth:
                        break
        self.complete_stage("repair_geometry")
        if not geometry_trials:
            return DesignBrainPreview(
                seed,
                before,
                before,
                (),
                False,
                "geometry_candidate_validation_failed",
            )
        _, candidate, after = min(geometry_trials, key=lambda row: row[0])
        changed = tuple(
            name for name, old, new in (
                ("width_mm", current.width_mm, candidate.proposal.width_mm),
                ("depth_mm", current.depth_mm, candidate.proposal.depth_mm),
            ) if old != new
        ) + (("bottom",) if (
            candidate.row_counts != current_rows
            or candidate.proposal.bottom_bars != current.bottom.bars
            or candidate.proposal.bottom_diameter_mm != current.bottom.diameter_mm
        ) else ())
        return DesignBrainPreview(
            candidate, before, after, changed, True, "geometry_ratio_repaired", 0.85, 1.0
        )

    def preview_serviceability(self, current: BeamInputs) -> DesignBrainPreview:
        """Repair crack control and deflection with fully recalculated candidates."""
        def calculate(inputs: BeamInputs) -> EngineeringResult:
            result = self._calculator.calculate_current(inputs).result
            if result is None:
                raise ValueError("calculation result is stale")
            return result

        return ServiceabilityCandidatePipeline(
            calculate=calculate,
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            complete_stage=self.complete_stage,
        ).preview(current)

    def preview_combined_overdesign(self, current: BeamInputs) -> DesignBrainPreview:
        """Reduce both reinforcement families in one reviewable candidate."""
        def calculate(inputs: BeamInputs) -> EngineeringResult:
            result = self._calculator.calculate_current(inputs).result
            if result is None:
                raise ValueError("calculation result is stale")
            return result

        return CombinedOverdesignPipeline(
            calculate=calculate,
            evaluate=self._evaluate,
            rank_key=self._rank_key,
            complete_stage=self.complete_stage,
            merge_metrics=self.merge_search_metrics,
            nearby_dimension_steps=self.search_profile.nearby_dimension_steps,
            max_continuation_rounds=self.search_profile.max_combined_continuation_rounds,
            preferences=self.preference_profile,
        ).preview(current)

    def apply(self, current: BeamInputs, preview: DesignBrainPreview) -> ApplyOutcome:
        return apply_candidate(current, preview.candidate)

    def apply_decision(self, current: BeamInputs, decision: "FamilyDecision") -> ApplyOutcome:
        """Apply only the exact authoritative candidate displayed to the user."""
        if not decision.apply_allowed or decision.candidate is None:
            return ApplyOutcome(False, "decision_does_not_allow_apply", current)
        if decision.candidate.source_revision != current.revision or decision.candidate.source_hash != current.content_hash:
            return ApplyOutcome(False, "stale_candidate", current)
        outcome = apply_candidate(current, decision.candidate)
        if not outcome.applied:
            return outcome
        recalculated = self._calculate_for_design_brain(outcome.inputs)
        displayed = decision.proposed_result
        if recalculated is None or displayed is None:
            return ApplyOutcome(False, "proposed_result_unavailable", current)
        if recalculated.source_hash != displayed.source_hash or recalculated.source_revision != displayed.source_revision:
            return ApplyOutcome(False, "displayed_proposal_mismatch", current)
        if not _complete_compliance(recalculated):
            return ApplyOutcome(False, "proposal_no_longer_compliant", current)
        return outcome
