"""Explicit owners for every non-terminal Design Brain family contract.

Each owner binds one family contract to one typed ladder entry point.  The
owners may reuse the common search engine, but neither the orchestrator nor
presentation can select a concrete ladder or reach into its implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Callable

from inputs_v2.application.design_brain_families import DesignFamily, ENTRY_CONDITIONS, EntryCondition
from inputs_v2.application.design_brain_service import DesignBrainPreview, DesignBrainService
from inputs_v2.application.ranking_policy import CandidateEvidence, NearLimitEvidence
from inputs_v2.application.design_brain.text_contracts import FAMILY_TEXT_CONTRACTS
from inputs_v2.application.design_brain.search_profile import SearchKind
from inputs_v2.application.design_brain.family_context import FamilyRunContext
from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain_decision import (
    DecisionStatus,
    FamilyDecision,
    SearchEvidence,
    StageSearchEvidence,
)
from inputs_v2.application.engineering_advice import (
    EngineeringAdviceResult,
    TargetBandBlocker,
    authoritative_checks,
    clause_references_from_checks,
    effects_for_changes,
    verified_changes,
)
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult


FamilyLadder = Callable[[DesignBrainService, BeamInputs], DesignBrainPreview]


class CtaIntent(StrEnum):
    """Presentation-neutral intent returned by a family decision."""

    APPLY_VERIFIED_PROPOSAL = "apply_verified_proposal"
    RETAIN_VERIFIED_DESIGN = "retain_verified_design"
    REVIEW_BLOCKER = "review_blocker"
    REQUEST_INPUT = "request_input"


class NearLimitDirection(StrEnum):
    UPPER_BOUND = "upper_bound"


class NearLimitComparison(StrEnum):
    NORMALISED_UTILISATION = "normalised_utilisation"


@dataclass(frozen=True, slots=True)
class NearLimitRule:
    check_id: str
    domain: str
    direction: NearLimitDirection
    threshold: float
    comparison_method: NearLimitComparison
    permit_required_repair_exception: bool = True


def _near_limit_value(result: EngineeringResult, check_id: str) -> float | None:
    if check_id == "bending_capacity":
        return float(result.families.get("bending", {}).get("util", 0.0) or 0.0)
    if check_id == "shear_strength":
        return float(result.families.get("shear", {}).get("util", 0.0) or 0.0)
    if check_id == "ductility":
        return float(result.families.get("ductility", {}).get("util", 0.0) or 0.0)
    if check_id == "crack_control":
        return float(result.families.get("crack_control", {}).get("util", 0.0) or 0.0)
    if check_id == "serviceability":
        return float(
            result.families.get("serviceability", {}).get("deflection_util", 0.0)
            or 0.0
        )
    return None


@dataclass(frozen=True, slots=True)
class NearLimitPolicy:
    """Explicit family-owned whitelist; an empty policy applies no penalty."""

    rules: tuple[NearLimitRule, ...] = ()

    def assess(
        self,
        current: EngineeringResult,
        proposed: EngineeringResult,
        *,
        repair_domains: tuple[str, ...],
        target_high: float,
    ) -> tuple[NearLimitEvidence, ...]:
        evidence: list[NearLimitEvidence] = []
        for rule in self.rules:
            current_value = _near_limit_value(current, rule.check_id)
            proposed_value = _near_limit_value(proposed, rule.check_id)
            if current_value is None or proposed_value is None:
                continue
            if rule.comparison_method is not NearLimitComparison.NORMALISED_UTILISATION:
                continue
            crossed = (
                rule.direction is NearLimitDirection.UPPER_BOUND
                and current_value <= rule.threshold < proposed_value <= target_high
            )
            required_repair_exception = (
                rule.permit_required_repair_exception
                and rule.domain in repair_domains
                and proposed_value <= target_high
            )
            evidence.append(
                NearLimitEvidence(
                    check_id=rule.check_id,
                    current_value=current_value,
                    proposed_value=proposed_value,
                    direction=rule.direction.value,
                    threshold=rule.threshold,
                    comparison_method=rule.comparison_method.value,
                    penalty_applied=crossed and not required_repair_exception,
                )
            )
        return tuple(evidence)


@dataclass(frozen=True, slots=True)
class LadderStage:
    """One deterministic engineering stage owned by a family."""

    stage_id: str
    permitted_changes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ImprovementPolicy:
    """Defines when a candidate is materially better than the current design."""

    active_domains: tuple[str, ...]
    require_complete_compliance: bool = True
    require_target_band: bool = True
    allow_safe_progress_below_band: bool = False
    allow_compliant_repair: bool = False


@dataclass(frozen=True, slots=True)
class RankingPolicy:
    """Ordered, reviewable candidate-ranking criteria."""

    criteria: tuple[str, ...] = (
        "complete_compliance",
        "conditional_preference_violation_count",
        "target_distance",
        "new_near_failure_count",
        "least_congestion",
        "least_material",
        "least_geometry_change",
        "fewest_changes",
        "candidate_id",
    )

    def rank_key(self, evidence: CandidateEvidence) -> tuple:
        values = {
            "complete_compliance": 0 if evidence.compliant and evidence.mandatory_checks_complete else 1,
            "conditional_preference_violation_count": len(
                evidence.conditional_preference_violation_codes
            ),
            "target_distance": evidence.target_distance,
            "new_near_failure_count": evidence.new_near_failure_count,
            "fewest_changes": evidence.edit_count,
            "least_congestion": evidence.soft_congestion_score,
            "least_geometry_change": evidence.geometry_change_penalty,
            "least_material": evidence.material_quantity,
            "candidate_id": evidence.candidate_id,
        }
        return tuple(values[criterion] for criterion in self.criteria)

    def select(self, evidence: tuple[CandidateEvidence, ...]) -> CandidateEvidence | None:
        """Perform the selected family's only final evidence selection."""

        passing = tuple(
            item
            for item in evidence
            if item.compliant
            and item.mandatory_checks_complete
            and not item.hard_congestion_rejection_codes
        )
        return min(passing, key=self.rank_key) if passing else None


@dataclass(frozen=True, slots=True)
class ExactStopPolicy:
    reason_codes: tuple[str, ...] = ()
    required_stage_ids: tuple[str, ...] = ()
    require_exhausted_search: bool = True


@dataclass(frozen=True, slots=True)
class FamilyOutcome:
    status: str
    final_family: DesignFamily
    cta_intent: CtaIntent


@dataclass(frozen=True, slots=True)
class FamilyResolution:
    """Complete family-owned terminal decision evidence.

    The orchestrator may render this result, but it must not reinterpret the
    candidate, target band, exact stop, status or CTA.
    """

    outcome: FamilyOutcome
    policy_accepted: bool
    current_failed: bool
    current_in_band: bool
    proposed_in_band: bool
    exact_stop_proven: bool
    current_utilisations: tuple[float, ...]
    proposed_utilisations: tuple[float, ...]


def _exact_stop_explanation(
    reason: str,
    improving_rejections: dict[str, int],
    fallback: str | None,
) -> str:
    """Describe only checks that rejected otherwise useful reductions."""

    if reason not in {
        "verified_bending_constraints_exhausted",
        "verified_shear_constraints_exhausted",
        "verified_combined_constraints_exhausted",
    }:
        return fallback or "The permitted family search is exhausted at a verified governing limit."

    constraints: list[str] = []

    def include(label: str, *codes: str) -> None:
        if any(int(improving_rejections.get(code, 0)) > 0 for code in codes):
            constraints.append(label)

    include("minimum tensile reinforcement", "minimum_tensile_reinforcement_failed")
    include(
        "the governing shear checks",
        "shear_strength_failed",
        "shear_web_crushing_failed",
        "transverse_reinforcement_required",
        "minimum_shear_reinforcement_failed",
        "shear_spacing_failed",
        "transverse_shear_leg_spacing_failed",
    )
    include("the deflection limit", "serviceability_fail")
    include("crack-control requirements", "crack_control_fail")
    include("the neutral-axis ductility limit", "ductility_fail")
    include("reinforcement fit and clear spacing", "reinforcement_fit_failed")
    include("the section geometry limit", "geometry_fail")
    include("the longitudinal reinforcement-ratio policy", "longitudinal_ratio_gate")
    include("the target-band improvement requirement", "no_utilisation_improvement")

    if not constraints:
        return fallback or "Every permitted reduction was rejected by a governing engineering check."
    if len(constraints) == 1:
        joined = constraints[0]
    else:
        joined = ", ".join(constraints[:-1]) + f" and {constraints[-1]}"
    domain = {
        "verified_bending_constraints_exhausted": "bending",
        "verified_shear_constraints_exhausted": "shear",
        "verified_combined_constraints_exhausted": "the combined design",
    }[reason]
    return (
        "Every permitted reinforcement and geometry reduction was assessed. "
        f"Candidates that improved {domain} were rejected by {joined}."
    )


@dataclass(frozen=True, slots=True)
class FamilyContract:
    family: DesignFamily
    owner_id: str
    entry_condition_id: str
    entry_condition: EntryCondition
    ladder_stages: tuple[LadderStage, ...]
    permitted_changes: tuple[str, ...]
    prohibited_changes: tuple[str, ...]
    required_checks: tuple[str, ...]
    improvement_policy: ImprovementPolicy
    search_kind: SearchKind
    ranking_policy: RankingPolicy = RankingPolicy()
    near_limit_policy: NearLimitPolicy = NearLimitPolicy()
    exact_stop_policy: ExactStopPolicy = ExactStopPolicy()
    blocker_contract_id: str = ""
    blocker_wording: tuple[tuple[str, str], ...] = ()
    action_intent: CtaIntent = CtaIntent.APPLY_VERIFIED_PROPOSAL
    pass_intent: CtaIntent = CtaIntent.RETAIN_VERIFIED_DESIGN
    blocked_intent: CtaIntent = CtaIntent.REVIEW_BLOCKER
    retain_compliant_on_optimisation_exhaustion: bool = False
    target_low: float = 0.85
    target_high: float = 1.0
    terminal_status: DecisionStatus | None = None

    @property
    def terminal_reason_codes(self) -> tuple[str, ...]:
        """Compatibility property while exact-stop consumers migrate."""
        return self.exact_stop_policy.reason_codes

    def resolve_outcome(
        self,
        *,
        current_failed: bool,
        current_compliant: bool,
        current_in_band: bool,
        preview_accepted: bool,
        proposed_in_band: bool,
        exact_stop_proven: bool,
        preview_reason: str,
    ) -> FamilyOutcome:
        """Own the final status and CTA intent for this family."""

        if self.terminal_status is not None:
            return FamilyOutcome(
                self.terminal_status.value,
                self.family,
                (
                    CtaIntent.REQUEST_INPUT
                    if self.terminal_status is DecisionStatus.INPUT_REQUIRED
                    else self.blocked_intent
                ),
            )

        if current_failed:
            status = "ACTION" if preview_accepted else "BLOCKED"
        elif current_in_band:
            if preview_accepted and proposed_in_band:
                return FamilyOutcome("ACTION", self.family, self.action_intent)
            if exact_stop_proven:
                return FamilyOutcome("PASS", DesignFamily.EXACT_STOP_PROVEN, self.pass_intent)
            # The current design is already calculator-verified and inside
            # every active target band.  A proportion-balancing preview that
            # is rejected (or falls back outside a target band) is evidence
            # to retain the current design, not a new engineering failure.
            # Keeping that failed preview out of publication also prevents a
            # green target-band state from turning red simply because a
            # non-actionable optimisation was assessed.
            if current_compliant:
                return FamilyOutcome("PASS", DesignFamily.TARGET_BAND_REACHED, self.pass_intent)
            return FamilyOutcome("BLOCKED", self.family, self.blocked_intent)
        elif exact_stop_proven and self.retain_compliant_on_optimisation_exhaustion:
            return FamilyOutcome("PASS", DesignFamily.EXACT_STOP_PROVEN, self.pass_intent)
        elif preview_accepted and (
            not self.improvement_policy.require_target_band
            or
            proposed_in_band
            or (
                self.improvement_policy.allow_safe_progress_below_band
                and preview_reason in {"safe_overdesign_cleanup", "proportion_balanced_candidate"}
            )
        ):
            status = "ACTION"
        else:
            status = "BLOCKED"
        intent = self.action_intent if status == "ACTION" else self.blocked_intent
        return FamilyOutcome(status, self.family, intent)

    def decide(
        self,
        *,
        current: BeamInputs,
        current_result: EngineeringResult,
        preview: DesignBrainPreview,
        search_metrics: dict[str, object],
        proposal_changed: bool = True,
    ) -> FamilyResolution:
        """Own candidate acceptance, exact stop, terminal status and CTA."""

        observed = self.observed_utilisations(current, current_result)
        current_utils = self.active_utilisations(current, current_result)
        proposed_utils = self.active_utilisations(current, preview.after)
        current_compliant = complete_compliance(current_result)
        current_failed = (
            not current_compliant
            or any(value > self.target_high for value in observed)
        )
        current_in_band = (
            self.family is DesignFamily.TARGET_BAND_REACHED
            and bool(observed)
            and all(self.target_low <= value <= self.target_high for value in observed)
        )
        proposed_in_band = bool(proposed_utils) and all(
            self.target_low <= value <= self.target_high for value in proposed_utils
        )
        # A calculator-backed preview is not an actionable proposal when it
        # resolves to the current canonical design.  Treating that no-op as
        # accepted would let the family publish ACTION without an Apply
        # command, violating the FamilyDecision contract.
        # The selected family ladder is the sole optimisation authority.  It
        # has already generated, calculator-checked, ranked and selected this
        # proposal under this contract's ImprovementPolicy.  Reapplying the
        # target-distance policy here created a second stopping gate: a fully
        # verified repair or cleanup could be selected by the family and then
        # lose its Apply action during publication.  This boundary therefore
        # validates only publication invariants; it does not rerank or
        # reinterpret the family-owned result.
        policy_accepted = (
            proposal_changed
            and preview.accepted
            and complete_compliance(preview.after)
        )
        candidates_attempted = max(
            int(search_metrics.get("candidates_attempted", 0) or 0),
            int(search_metrics.get("additional_evaluations", 0) or 0),
        )
        exact_stop = self.proves_exact_stop(
            preview_accepted=policy_accepted,
            preview_reason=preview.reason,
            candidates_attempted=candidates_attempted,
            empty_search_space_proven=bool(
                search_metrics.get("empty_search_space_proven", False)
            ),
            completed_stage_ids=tuple(search_metrics.get("completed_stage_ids", ()) or ()),
            stage_stop_reasons=dict(
                search_metrics.get("stage_stop_reasons", {}) or {}
            ),
            budget_exhausted=bool(search_metrics.get("budget_exhausted", False)),
        )
        outcome = self.resolve_outcome(
            current_failed=current_failed,
            current_compliant=current_compliant,
            current_in_band=current_in_band,
            preview_accepted=policy_accepted,
            proposed_in_band=proposed_in_band,
            exact_stop_proven=exact_stop,
            preview_reason=preview.reason,
        )
        return FamilyResolution(
            outcome=outcome,
            policy_accepted=policy_accepted,
            current_failed=current_failed,
            current_in_band=current_in_band,
            proposed_in_band=proposed_in_band,
            exact_stop_proven=exact_stop,
            current_utilisations=current_utils,
            proposed_utilisations=proposed_utils,
        )

    def proves_exact_stop(
        self,
        *,
        preview_accepted: bool,
        preview_reason: str,
        candidates_attempted: int,
        completed_stage_ids: tuple[str, ...],
        empty_search_space_proven: bool = False,
        stage_stop_reasons: dict[str, str] | None = None,
        budget_exhausted: bool = False,
    ) -> bool:
        policy = self.exact_stop_policy
        return (
            not preview_accepted
            and not budget_exhausted
            and preview_reason in policy.reason_codes
            and (candidates_attempted > 0 or empty_search_space_proven)
            and bool(policy.required_stage_ids)
            and set(policy.required_stage_ids).issubset(completed_stage_ids)
            and all(
                (stage_stop_reasons or {}).get(stage_id)
                for stage_id in policy.required_stage_ids
            )
        )

    def blocker_for(self, reason_code: str | None) -> str | None:
        if reason_code is None:
            return None
        canonical = reason_code.split(":", 1)[0]
        return next((text for code, text in self.blocker_wording if code == canonical), None)

    def active_utilisations(
        self,
        inputs: BeamInputs,
        result: EngineeringResult,
    ) -> tuple[float, ...]:
        """Return only strength utilisations governed by the target band.

        Mandatory checks still verify the complete proposal.  This narrower
        tuple prevents a passing preservation domain (for example bending in
        a shear repair) from being incorrectly required to enter the
        optimisation band before Apply can be authorised.

        Serviceability is an upper-bound compliance check, not an efficiency
        target.  A crack or deflection utilisation of 0.20 is safely passing;
        requiring it to reach the 0.85--1.00 ULS optimisation band would turn
        a verified design into a false blocked outcome after Apply.
        """

        values: list[float] = []
        domains = self.improvement_policy.active_domains
        if "bending" in domains and abs(float(inputs.actions.bending_moment_knm)) > 1e-9:
            values.append(float(result.families.get("bending", {}).get("util", 0.0) or 0.0))
        if "shear" in domains and abs(float(inputs.actions.shear_force_kn)) > 1e-9:
            shear = result.families.get("shear", {})
            capacity = float(shear.get("phi_Vu", 0.0) or 0.0)
            values.append(
                abs(float(inputs.actions.shear_force_kn)) / capacity
                if capacity > 0.0
                else float("inf")
            )
        return tuple(values)

    @staticmethod
    def observed_utilisations(
        inputs: BeamInputs,
        result: EngineeringResult,
    ) -> tuple[float, ...]:
        """Return active strength utilisations used by the classifier.

        SLS failures remain authoritative through ``complete_compliance`` and
        the serviceability family entry condition.  They are deliberately not
        interpreted as lower-bound target-band values.
        """

        values: list[float] = []
        if abs(float(inputs.actions.bending_moment_knm)) > 1e-9:
            values.append(float(result.families.get("bending", {}).get("util", 0.0) or 0.0))
        if abs(float(inputs.actions.shear_force_kn)) > 1e-9:
            shear = result.families.get("shear", {})
            capacity = float(shear.get("phi_Vu", 0.0) or 0.0)
            values.append(
                abs(float(inputs.actions.shear_force_kn)) / capacity
                if capacity > 0.0
                else float("inf")
            )
        return tuple(values)


@dataclass(frozen=True, slots=True)
class FamilyOwner:
    contract: FamilyContract
    ladder: FamilyLadder

    @property
    def family(self) -> DesignFamily:
        return self.contract.family

    def validates_entry(self, context: FamilyRunContext) -> bool:
        """Prove the classifier selected this owner through its own entry rule."""

        return (
            context.classification.selected_family is self.family
            and self.contract.entry_condition(context.classification.signals)
        )

    def preview(self, context: FamilyRunContext, service: DesignBrainService) -> DesignBrainPreview:
        with service.family_contract(self.contract, context):
            preview = self.ladder(service, context.current)
            if self.family is DesignFamily.ENGINEERING_REVIEW_REQUIRED:
                preview = replace(preview, reason=context.classification.reason_code)
            preview = service.publish_preview(context.current, preview)
        service.last_search_metrics["owner_id"] = self.contract.owner_id
        service.last_search_metrics["declared_stage_ids"] = tuple(
            stage.stage_id for stage in self.contract.ladder_stages
        )
        return preview

    def decide(
        self,
        context: FamilyRunContext,
        service: DesignBrainService,
    ) -> FamilyDecision:
        """Run this family's ladder and return its complete final decision."""

        if not self.validates_entry(context):
            raise ValueError(
                f"family entry validation failed for {self.family.value}"
            )

        current = context.current
        current_result = context.current_result
        preview = self.preview(context, service)
        metrics = service.last_search_metrics
        changes = verified_changes(
            current, preview.candidate.proposal, preview.candidate.row_counts
        )
        resolution = self.contract.decide(
            current=current,
            current_result=current_result,
            preview=preview,
            search_metrics=metrics,
            proposal_changed=bool(changes),
        )
        assert_candidate_proposal_permitted(
            self.contract, current, preview.candidate.proposal
        )
        assert_permitted_changes(
            self.contract, tuple(change.change_type for change in changes)
        )

        outcome = resolution.outcome
        status = DecisionStatus(outcome.status)
        final_family = outcome.final_family
        display_result = preview.after
        display_candidate = preview.candidate
        if status is DecisionStatus.PASS:
            changes = ()
            display_result = current_result
            display_candidate = None
        apply_allowed = (
            outcome.cta_intent is CtaIntent.APPLY_VERIFIED_PROPOSAL
            and resolution.policy_accepted
            and bool(changes)
        )

        blocker_code = preview.reason
        blocker = None
        if status is DecisionStatus.BLOCKED:
            rejection_counts = dict(metrics.get("rejection_counts", {}) or {})
            stage_stop_reasons = dict(
                metrics.get("stage_stop_reasons", {}) or {}
            )
            stop_evidence = " ".join(str(value) for value in stage_stop_reasons.values())
            locked_width = (
                int(rejection_counts.get("width_locked", 0)) > 0
                or "width_locked" in stop_evidence
            )
            locked_depth = (
                int(rejection_counts.get("depth_locked", 0)) > 0
                or "depth_locked" in stop_evidence
            )
            if not preview.accepted and locked_width and locked_depth:
                blocker_code = "geometry_locked"
                blocker = self.contract.blocker_for(blocker_code)
            elif not preview.accepted and locked_width:
                blocker_code = "width_locked"
                blocker = self.contract.blocker_for(blocker_code)
            elif not preview.accepted and locked_depth:
                blocker_code = "depth_locked"
                blocker = self.contract.blocker_for(blocker_code)
            else:
                blocker = self.contract.blocker_for(preview.reason)
            if bool(metrics.get("budget_exhausted", False)):
                blocker_code = "search_budget_exhausted"
                blocker = self.contract.blocker_for(blocker_code)
            elif preview.accepted and not resolution.policy_accepted:
                blocker_code = "verified_proposal_publication_invariant_failed"
                blocker = (
                    "The selected family proposal could not be published because its "
                    "verified Apply invariants were not satisfied"
                )
            elif blocker is None and rejection_counts:
                blocker_code = max(
                    rejection_counts,
                    key=lambda code: (int(rejection_counts[code]), code),
                )
                blocker = self.contract.blocker_for(blocker_code)
            elif blocker is None:
                blocker = (
                    "The family search did not produce a verified proposal; "
                    "review the recorded candidate rejection evidence"
                )
        elif status is DecisionStatus.PASS and resolution.exact_stop_proven:
            blocker_code = preview.reason
            blocker = _exact_stop_explanation(
                preview.reason,
                dict(metrics.get("improving_rejection_counts", {}) or {}),
                self.contract.blocker_for(preview.reason),
            )

        selected_text = FAMILY_TEXT_CONTRACTS[self.contract.family]
        final_text = FAMILY_TEXT_CONTRACTS[final_family]
        effects = effects_for_changes(changes, selected_text.engineering_purpose)
        current_checks = authoritative_checks(
            current, current_result, self.contract.required_checks
        )
        proposed_checks = authoritative_checks(
            current, display_result, self.contract.required_checks
        )
        references = clause_references_from_checks(current_checks + proposed_checks)
        governing_failed = next(
            (check for check in current_checks if check.status == "fail"), None
        )
        typed_blocker = None if blocker is None else TargetBandBlocker(
            check_id=(
                governing_failed.check_id
                if governing_failed is not None
                else "family_search"
            ),
            blocker_code=blocker_code,
            blocked_action=selected_text.engineering_purpose,
            governing_requirement=blocker,
            clause_reference=(
                governing_failed.clause_reference
                if governing_failed is not None
                else None
            ),
        )
        advice = EngineeringAdviceResult(
            current_checks=current_checks,
            proposed_checks=proposed_checks,
            recommended_changes=changes,
            engineering_effects=(
                effects
                or (
                    "The family has exhausted its verified search without a safe improving candidate.",
                )
                if resolution.exact_stop_proven
                else effects
            ),
            governing_check=final_family.value,
            clause_references=references,
            verified_compliance=(
                status in {DecisionStatus.PASS, DecisionStatus.ACTION}
                and (
                    not resolution.current_failed
                    or resolution.policy_accepted
                )
            ),
            apply_allowed=apply_allowed,
            blocked_reason=blocker,
            outcome_type=final_family.value,
            blocker=typed_blocker,
        )
        candidates_attempted = max(
            int(metrics.get("candidates_attempted", 0) or 0),
            int(metrics.get("additional_evaluations", 0) or 0),
        )
        attempted_stage_ids = tuple(metrics.get("attempted_stage_ids", ()) or ())
        attempted_stages = tuple(
            stage
            for stage in self.contract.ladder_stages
            if stage.stage_id in attempted_stage_ids
        )
        return FamilyDecision(
            family=final_family,
            classification=context.classification,
            status=status,
            display_heading=final_text.title_for(status.value),
            candidate=display_candidate,
            current_result=current_result,
            proposed_result=display_result,
            advice=advice,
            apply_allowed=apply_allowed,
            reason=preview.reason,
            changed_fields=() if status is DecisionStatus.PASS else preview.changed_fields,
            search_evidence=SearchEvidence(
                candidates_attempted=candidates_attempted,
                candidates_valid=int(metrics.get("candidates_valid", 0) or 0),
                geometry_attempted=any(
                    {"width_mm", "depth_mm"} & set(stage.permitted_changes)
                    for stage in attempted_stages
                ),
                reinforcement_attempted=any(
                    {"bottom", "top", "shear"} & set(stage.permitted_changes)
                    for stage in attempted_stages
                ),
                governing_blocker=blocker,
                exhausted=resolution.exact_stop_proven,
                empty_search_space_proven=bool(
                    metrics.get("empty_search_space_proven", False)
                ),
                declared_stage_ids=tuple(metrics.get("declared_stage_ids", ()) or ()),
                attempted_stage_ids=attempted_stage_ids,
                completed_stage_ids=tuple(metrics.get("completed_stage_ids", ()) or ()),
                stage_attempt_counts=tuple(
                    sorted(
                        (str(stage_id), int(count))
                        for stage_id, count in dict(
                            metrics.get("stage_attempt_counts", {}) or {}
                        ).items()
                    )
                ),
                stage_valid_counts=tuple(
                    sorted(
                        (str(stage_id), int(count))
                        for stage_id, count in dict(
                            metrics.get("stage_valid_counts", {}) or {}
                        ).items()
                    )
                ),
                rejection_counts=tuple(
                    sorted(
                        (str(code), int(count))
                        for code, count in dict(
                            metrics.get("rejection_counts", {}) or {}
                        ).items()
                    )
                ),
                improving_rejection_counts=tuple(
                    sorted(
                        (str(code), int(count))
                        for code, count in dict(
                            metrics.get("improving_rejection_counts", {}) or {}
                        ).items()
                    )
                ),
                stage_rejection_counts=tuple(
                    (
                        str(stage_id),
                        tuple(
                            sorted(
                                (str(code), int(count))
                                for code, count in dict(counts).items()
                            )
                        ),
                    )
                    for stage_id, counts in sorted(
                        dict(metrics.get("stage_rejections", {}) or {}).items()
                    )
                ),
                cache_hits=int(metrics.get("cache_hits", 0) or 0),
                cache_misses=int(metrics.get("cache_misses", 0) or 0),
                generated_candidates=int(metrics.get("candidates_attempted", 0) or 0),
                full_evaluations=int(metrics.get("cache_misses", 0) or 0),
                preference_profile_id=context.preferences.preference_profile_id,
                preference_profile_version=context.preferences.preference_profile_version,
                elapsed_ms=float(metrics.get("elapsed_ms", 0.0) or 0.0),
                budget_exhausted=bool(metrics.get("budget_exhausted", False)),
                budget_skipped_candidates=int(
                    metrics.get("budget_skipped_candidates", 0) or 0
                ),
                candidate_records=tuple(
                    metrics.get("candidate_records", ()) or ()
                ),
                stages=tuple(
                    StageSearchEvidence(
                        stage_id=stage.stage_id,
                        candidates_attempted=int(
                            dict(metrics.get("stage_attempt_counts", {}) or {}).get(
                                stage.stage_id, 0
                            )
                        ),
                        candidates_calculated=sum(
                            1
                            for record in tuple(
                                metrics.get("candidate_records", ()) or ()
                            )
                            if record.stage_id == stage.stage_id
                            and bool(record.calculated_checks)
                        ),
                        candidates_valid=int(
                            dict(metrics.get("stage_valid_counts", {}) or {}).get(
                                stage.stage_id, 0
                            )
                        ),
                        rejection_counts=tuple(
                            sorted(
                                (str(code), int(count))
                                for code, count in dict(
                                    dict(
                                        metrics.get("stage_rejections", {}) or {}
                                    ).get(stage.stage_id, {})
                                    or {}
                                ).items()
                            )
                        ),
                        completed=stage.stage_id
                        in tuple(metrics.get("completed_stage_ids", ()) or ()),
                        stop_reason=dict(
                            metrics.get("stage_stop_reasons", {}) or {}
                        ).get(stage.stage_id),
                    )
                    for stage in self.contract.ladder_stages
                ),
            ),
        )


def _bending_failure(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview(current)


def _shear_failure(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview_shear_only(current)


def _shear_failure_bending_optimise(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview_shear_failure_bending_optimise(current)


def _combined_failure(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview_combined_failure(current)


def _bending_overdesign(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview_bending_overdesign(current)


def _bending_failure_shear_cleanup(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview_bending_failure_shear_cleanup(current)


def _shear_overdesign(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview_shear_overdesign(current)


def _combined_overdesign(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview_combined_overdesign(current)


def _serviceability(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview_serviceability(current)


def _geometry_detailing(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview_geometry_detailing(current)


def _target_band_review(service: DesignBrainService, current: BeamInputs) -> DesignBrainPreview:
    return service.preview_target_band(current)


_NEVER_CHANGE = ("actions", "serviceability_inputs", "materials", "supports", "persistence", "widget_state")


_EVIDENCE_BLOCKERS: tuple[tuple[str, str], ...] = (
    ("geometry_locked", "The required beam-width and beam-depth revisions are locked by the user."),
    ("width_locked", "The required beam-width revision is locked by the user."),
    ("depth_locked", "The required beam-depth revision is locked by the user."),
    ("lock_state_mutation_forbidden", "A Design Brain candidate attempted to change a user-owned geometry lock."),
    ("reinforcement_fit_failed", "The proposed reinforcement does not fit with the required cover, clear spacing and row separation."),
    ("minimum_tensile_reinforcement_failed", "Minimum tensile reinforcement is not satisfied."),
    ("ductility_fail", "The proposed reinforcement exceeds the neutral-axis ductility limit."),
    ("bending_fail", "The proposed section does not provide the required flexural resistance."),
    ("shear_strength_failed", "The proposed section does not provide the required shear resistance."),
    ("shear_web_crushing_failed", "The proposed section exceeds the web-crushing limit."),
    ("transverse_reinforcement_required", "Transverse reinforcement is required for the proposed design."),
    ("minimum_shear_reinforcement_failed", "Minimum shear reinforcement is not satisfied."),
    ("shear_spacing_failed", "The proposed ligature spacing exceeds the permitted limit."),
    ("transverse_shear_leg_spacing_failed", "The fitted horizontal spacing between adjacent effective shear-link legs exceeds the permitted limit."),
    ("transverse_shear_leg_clear_spacing_failed", "The clear spacing between adjacent effective shear-link legs is below the required detailing clearance."),
    ("shear_cage_topology_unavailable", "No complete, buildable shear-cage topology is available for the proposed leg arrangement."),
    ("shear_cage_longitudinal_bar_collision", "An internal shear-link leg clashes with the longitudinal reinforcement."),
    ("internal_leg_anchorage_failed", "The proposed internal shear-link legs do not have sufficient anchorage space."),
    ("longitudinal_bar_restraint_failed", "The proposed shear cage does not enclose and restrain every longitudinal bar."),
    ("serviceability_fail", "Deflection remains above the allowable limit."),
    ("crack_control_fail", "Crack width remains above the allowable limit."),
    ("search_budget_exhausted", "The configured search budget was reached before every required ladder stage could be completed."),
)


_PRESERVE_BENDING_NEAR_LIMIT = NearLimitRule(
    check_id="bending_capacity",
    domain="bending",
    direction=NearLimitDirection.UPPER_BOUND,
    threshold=0.95,
    comparison_method=NearLimitComparison.NORMALISED_UTILISATION,
)
_PRESERVE_SHEAR_NEAR_LIMIT = NearLimitRule(
    check_id="shear_strength",
    domain="shear",
    direction=NearLimitDirection.UPPER_BOUND,
    threshold=0.95,
    comparison_method=NearLimitComparison.NORMALISED_UTILISATION,
)


def _contract(
    family: DesignFamily,
    owner_id: str,
    entry_condition_id: str,
    stages: tuple[LadderStage, ...],
    permitted: tuple[str, ...],
    checks: tuple[str, ...],
    *,
    active_domains: tuple[str, ...],
    search_kind: SearchKind,
    allow_safe_progress: bool = False,
    allow_compliant_repair: bool | None = None,
    require_target_band: bool = True,
    retain_compliant_on_optimisation_exhaustion: bool = False,
    exact_reasons: tuple[str, ...] = (),
    near_limit_rules: tuple[NearLimitRule, ...] = (),
) -> FamilyContract:
    return FamilyContract(
        family=family,
        owner_id=owner_id,
        entry_condition_id=entry_condition_id,
        entry_condition=ENTRY_CONDITIONS[family],
        ladder_stages=stages,
        permitted_changes=permitted,
        prohibited_changes=_NEVER_CHANGE,
        required_checks=checks,
        improvement_policy=ImprovementPolicy(
            active_domains,
            require_target_band=require_target_band,
            allow_safe_progress_below_band=allow_safe_progress,
            allow_compliant_repair=(
                search_kind is SearchKind.REPAIR
                if allow_compliant_repair is None
                else allow_compliant_repair
            ),
        ),
        search_kind=search_kind,
        near_limit_policy=NearLimitPolicy(near_limit_rules),
        retain_compliant_on_optimisation_exhaustion=retain_compliant_on_optimisation_exhaustion,
        exact_stop_policy=ExactStopPolicy(
            reason_codes=exact_reasons,
            required_stage_ids=tuple(stage.stage_id for stage in stages),
        ),
        blocker_contract_id=family.value.lower(),
        blocker_wording=tuple(
            (item.reason_code, item.sentence)
            for item in FAMILY_TEXT_CONTRACTS[family].blockers
        ) + _EVIDENCE_BLOCKERS,
    )


FAMILY_OWNERS: dict[DesignFamily, FamilyOwner] = {
    DesignFamily.TARGET_BAND_REACHED: FamilyOwner(_contract(
        DesignFamily.TARGET_BAND_REACHED,
        "target_band",
        "all_active_domains_in_target_band",
        (LadderStage("proportion_balance_target_band", ("width_mm", "depth_mm", "bottom")),),
        ("width_mm", "depth_mm", "bottom"),
        ("bending", "shear", "serviceability", "crack_control", "reinforcement_fit"),
        active_domains=("bending", "shear", "serviceability"),
        search_kind=SearchKind.OPTIMISATION,
        allow_safe_progress=True,
        retain_compliant_on_optimisation_exhaustion=True,
        exact_reasons=("proportion_balance_exhausted",),
    ), _target_band_review),
    DesignFamily.GEOMETRY_DETAILING_GOVERNS: FamilyOwner(_contract(
        DesignFamily.GEOMETRY_DETAILING_GOVERNS, "geometry_detailing", "invalid_geometry_or_reinforcement_fit",
        (LadderStage("repair_arrangement", ("bottom", "top", "shear")), LadderStage("repair_geometry", ("width_mm", "depth_mm"))),
        ("bottom", "top", "shear", "width_mm", "depth_mm"), ("geometry", "reinforcement_fit"), active_domains=("geometry",), search_kind=SearchKind.REPAIR, require_target_band=False,
    ), _geometry_detailing),
    DesignFamily.SERVICEABILITY_GOVERNS: FamilyOwner(_contract(
        DesignFamily.SERVICEABILITY_GOVERNS, "serviceability", "active_sls_check_fails",
        (LadderStage("redistribute_reinforcement", ("bottom",)), LadderStage("increase_stiffness", ("depth_mm", "width_mm"))),
        ("bottom", "depth_mm", "width_mm"), ("crack_control", "serviceability", "bending", "shear", "reinforcement_fit"), active_domains=("serviceability",), search_kind=SearchKind.REPAIR, require_target_band=False,
    ), _serviceability),
    DesignFamily.COMBINED_OVERDESIGN: FamilyOwner(_contract(
        DesignFamily.COMBINED_OVERDESIGN, "combined_overdesign", "bending_and_shear_below_target",
        (LadderStage("reduce_shear_reinforcement", ("shear",)), LadderStage("reduce_bending_reinforcement", ("bottom",)), LadderStage("reduce_geometry_and_redesign", ("width_mm", "depth_mm", "bottom", "shear"))),
        ("bottom", "shear", "width_mm", "depth_mm"), ("bending", "shear", "ductility", "reinforcement_fit"), active_domains=("bending", "shear"), search_kind=SearchKind.OPTIMISATION, allow_safe_progress=True, retain_compliant_on_optimisation_exhaustion=True,
        exact_reasons=("minimum_reinforcement_geometry_exhausted", "ductility_geometry_exhausted", "verified_bending_constraints_exhausted", "verified_combined_constraints_exhausted"),
    ), _combined_overdesign),
    DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN: FamilyOwner(_contract(
        DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN, "combined_failure", "bending_and_shear_fail",
        (LadderStage("repair_reinforcement", ("bottom", "shear")), LadderStage("increase_geometry_and_redesign", ("width_mm", "depth_mm", "bottom", "shear"))),
        ("bottom", "shear", "width_mm", "depth_mm"), ("bending", "shear", "ductility", "reinforcement_fit"), active_domains=("bending", "shear"), search_kind=SearchKind.REPAIR, require_target_band=False,
    ), _combined_failure),
    DesignFamily.SHEAR_FAIL_GOVERNS: FamilyOwner(_contract(
        DesignFamily.SHEAR_FAIL_GOVERNS, "shear_failure", "shear_fails_bending_not_overdesigned",
        (LadderStage("repair_ligatures", ("shear",)), LadderStage("increase_width", ("width_mm",)), LadderStage("increase_depth_and_redesign", ("depth_mm", "bottom", "shear"))),
        ("shear", "width_mm", "depth_mm", "bottom"), ("shear", "bending", "ductility", "reinforcement_fit"), active_domains=("shear",), search_kind=SearchKind.REPAIR, require_target_band=False,
    ), _shear_failure),
    DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS: FamilyOwner(_contract(
        DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS, "shear_failure_bending_optimise", "shear_fails_bending_below_target",
        (LadderStage("repair_ligatures", ("shear",)), LadderStage("coordinate_longitudinal_reduction", ("bottom", "shear")), LadderStage("resize_and_redesign", ("width_mm", "depth_mm", "bottom", "shear"))),
        ("bottom", "shear", "width_mm", "depth_mm"), ("shear", "bending", "ductility", "reinforcement_fit"), active_domains=("shear", "bending"), search_kind=SearchKind.REPAIR, require_target_band=False,
    ), _shear_failure_bending_optimise),
    DesignFamily.BENDING_FAIL_GOVERNS: FamilyOwner(_contract(
        DesignFamily.BENDING_FAIL_GOVERNS, "bending_failure", "bending_fails_shear_not_overdesigned",
        (LadderStage("increase_bottom_reinforcement", ("bottom",)), LadderStage("add_reinforcement_layer", ("bottom",)), LadderStage("increase_depth", ("depth_mm", "bottom")), LadderStage("increase_width_at_ratio_limit", ("width_mm", "depth_mm", "bottom"))),
        ("bottom", "width_mm", "depth_mm"), ("bending", "ductility", "minimum_tensile", "reinforcement_fit"), active_domains=("bending",), search_kind=SearchKind.REPAIR,
    ), _bending_failure),
    DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS: FamilyOwner(_contract(
        DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS, "bending_failure_shear_cleanup", "bending_fails_shear_below_target",
        (LadderStage("repair_bending", ("bottom",)), LadderStage("reduce_shear_excess", ("shear",)), LadderStage("coordinate_geometry", ("width_mm", "depth_mm", "bottom", "shear"))),
        ("bottom", "shear", "width_mm", "depth_mm"), ("bending", "shear", "ductility", "minimum_tensile", "reinforcement_fit"), active_domains=("bending", "shear"), search_kind=SearchKind.REPAIR, require_target_band=False,
        near_limit_rules=(_PRESERVE_SHEAR_NEAR_LIMIT,),
    ), _bending_failure_shear_cleanup),
    DesignFamily.BENDING_OVERDESIGN_GOVERNS: FamilyOwner(_contract(
        DesignFamily.BENDING_OVERDESIGN_GOVERNS, "bending_overdesign", "bending_below_target_other_active_domains_compliant",
        (LadderStage("reduce_bottom_reinforcement", ("bottom",)), LadderStage("remove_unnecessary_layer", ("bottom",)), LadderStage("reduce_geometry_and_redesign", ("width_mm", "depth_mm", "bottom")), LadderStage("preserve_near_limit_shear", ("shear",))),
        ("bottom", "width_mm", "depth_mm", "shear"), ("bending", "shear", "ductility", "minimum_tensile", "reinforcement_fit"), active_domains=("bending",), search_kind=SearchKind.OPTIMISATION, allow_safe_progress=True, retain_compliant_on_optimisation_exhaustion=True,
        exact_reasons=("minimum_reinforcement_geometry_exhausted", "ductility_geometry_exhausted", "verified_bending_constraints_exhausted"),
        near_limit_rules=(_PRESERVE_SHEAR_NEAR_LIMIT,),
    ), _bending_overdesign),
    DesignFamily.SHEAR_OVERDESIGN_GOVERNS: FamilyOwner(_contract(
        DesignFamily.SHEAR_OVERDESIGN_GOVERNS, "shear_overdesign", "shear_below_target_other_active_domains_compliant",
        (LadderStage("increase_spacing", ("shear",)), LadderStage("reduce_ligature_size_or_legs", ("shear",)), LadderStage("remove_unrequired_ligatures", ("shear",)), LadderStage("reduce_width_and_redesign", ("width_mm", "bottom", "shear"))),
        ("shear", "width_mm", "bottom"), ("shear", "bending", "ductility", "reinforcement_fit"), active_domains=("shear",), search_kind=SearchKind.OPTIMISATION, allow_safe_progress=True, retain_compliant_on_optimisation_exhaustion=True,
        exact_reasons=("minimum_shear_reinforcement_exhausted", "verified_shear_constraints_exhausted"),
        near_limit_rules=(_PRESERVE_BENDING_NEAR_LIMIT,),
    ), _shear_overdesign),
}


TERMINAL_FAMILIES = {
    DesignFamily.INPUT_REQUIRED,
    DesignFamily.ENGINEERING_REVIEW_REQUIRED,
    DesignFamily.EXACT_STOP_PROVEN,
    DesignFamily.LOCKED_NO_REPAIR,
}


def _terminal_contract(
    family: DesignFamily,
    owner_id: str,
    entry_condition_id: str,
    stage_id: str,
    checks: tuple[str, ...],
    *,
    terminal_status: DecisionStatus | None = None,
) -> FamilyContract:
    return FamilyContract(
        family=family,
        owner_id=owner_id,
        entry_condition_id=entry_condition_id,
        entry_condition=ENTRY_CONDITIONS[family],
        ladder_stages=(LadderStage(stage_id, ("none",)),),
        permitted_changes=("none",),
        prohibited_changes=("bottom", "top", "shear", "width_mm", "depth_mm", *_NEVER_CHANGE),
        required_checks=checks,
        improvement_policy=ImprovementPolicy(("terminal_verification",), require_target_band=False),
        search_kind=SearchKind.TERMINAL,
        exact_stop_policy=ExactStopPolicy(required_stage_ids=(stage_id,)),
        blocker_contract_id=family.value.lower(),
        blocker_wording=tuple(
            (item.reason_code, item.sentence)
            for item in FAMILY_TEXT_CONTRACTS[family].blockers
        ),
        terminal_status=terminal_status,
    )


TERMINAL_CONTRACTS: dict[DesignFamily, FamilyContract] = {
    DesignFamily.INPUT_REQUIRED: _terminal_contract(
        DesignFamily.INPUT_REQUIRED, "input_required", "no_design_actions_entered",
        "verify_design_actions_present", ("reinforcement_fit",),
        terminal_status=DecisionStatus.INPUT_REQUIRED,
    ),
    DesignFamily.ENGINEERING_REVIEW_REQUIRED: _terminal_contract(
        DesignFamily.ENGINEERING_REVIEW_REQUIRED,
        "engineering_review_required",
        "unclassified_or_invalid_engineering_state",
        "verify_engineering_state_classifiable",
        (
            "geometry",
            "bending",
            "shear",
            "ductility",
            "minimum_tensile",
            "serviceability",
            "crack_control",
            "reinforcement_fit",
        ),
        terminal_status=DecisionStatus.BLOCKED,
    ),
    DesignFamily.EXACT_STOP_PROVEN: _terminal_contract(
        DesignFamily.EXACT_STOP_PROVEN, "exact_stop", "active_family_search_exhausted_at_verified_limit",
        "verify_exact_stop_evidence", ("bending", "shear", "ductility", "minimum_tensile", "serviceability", "crack_control", "reinforcement_fit"),
    ),
    DesignFamily.LOCKED_NO_REPAIR: _terminal_contract(
        DesignFamily.LOCKED_NO_REPAIR, "locked_no_repair", "required_repair_prevented_by_explicit_lock",
        "verify_lock_and_failed_check", ("geometry", "bending", "shear", "ductility", "minimum_tensile", "serviceability", "crack_control", "reinforcement_fit"),
    ),
}


def _target_band_terminal(
    service: DesignBrainService, current: BeamInputs
) -> DesignBrainPreview:
    return service.preview_terminal(current, "target_band_reached")


def _input_required_terminal(
    service: DesignBrainService, current: BeamInputs
) -> DesignBrainPreview:
    return service.preview_terminal(current, "design_actions_required")


def _engineering_review_terminal(
    service: DesignBrainService, current: BeamInputs
) -> DesignBrainPreview:
    return service.preview_terminal(current, "engineering_review_required")


def _exact_stop_terminal(
    service: DesignBrainService, current: BeamInputs
) -> DesignBrainPreview:
    return service.preview_terminal(current, "exact_stop_proven")


def _locked_terminal(
    service: DesignBrainService, current: BeamInputs
) -> DesignBrainPreview:
    return service.preview_terminal(current, "locked_no_repair")


TERMINAL_OWNERS: dict[DesignFamily, FamilyOwner] = {
    DesignFamily.INPUT_REQUIRED: FamilyOwner(
        TERMINAL_CONTRACTS[DesignFamily.INPUT_REQUIRED],
        _input_required_terminal,
    ),
    DesignFamily.ENGINEERING_REVIEW_REQUIRED: FamilyOwner(
        TERMINAL_CONTRACTS[DesignFamily.ENGINEERING_REVIEW_REQUIRED],
        _engineering_review_terminal,
    ),
    DesignFamily.EXACT_STOP_PROVEN: FamilyOwner(
        TERMINAL_CONTRACTS[DesignFamily.EXACT_STOP_PROVEN],
        _exact_stop_terminal,
    ),
    DesignFamily.LOCKED_NO_REPAIR: FamilyOwner(
        TERMINAL_CONTRACTS[DesignFamily.LOCKED_NO_REPAIR],
        _locked_terminal,
    ),
}

DECISION_OWNERS: dict[DesignFamily, FamilyOwner] = {
    **FAMILY_OWNERS,
    **TERMINAL_OWNERS,
}


FAMILY_CONTRACTS: dict[DesignFamily, FamilyContract] = {
    **{family: owner.contract for family, owner in FAMILY_OWNERS.items()},
    **TERMINAL_CONTRACTS,
}


_CHANGE_OWNER = {
    "width_mm": "width_mm",
    "depth_mm": "depth_mm",
    "bottom_bars": "bottom",
    "bottom_diameter_mm": "bottom",
    "layer_count": "bottom",
    "shear_diameter_mm": "shear",
    "shear_legs": "shear",
    "shear_spacing_mm": "shear",
}


def assert_permitted_changes(contract: FamilyContract, change_types: tuple[str, ...]) -> None:
    """Reject proposal leakage across family-owned mutation boundaries."""

    permitted = set(contract.permitted_changes)
    unknown = tuple(change for change in change_types if change not in _CHANGE_OWNER)
    forbidden = tuple(
        change for change in change_types
        if change in _CHANGE_OWNER and _CHANGE_OWNER[change] not in permitted
    )
    if unknown or forbidden:
        details = ", ".join((*unknown, *forbidden))
        raise ValueError(f"{contract.family.value} proposed undeclared changes: {details}")


def assert_candidate_proposal_permitted(
    contract: FamilyContract,
    current: BeamInputs,
    proposal,
) -> None:
    """Compare the complete proposal so hidden, undisplayed mutations cannot leak."""

    groups = {
        "width_mm": (
            (current.width_mm, proposal.width_mm),
            (current.web_width_mm, proposal.web_width_mm),
        ),
        "depth_mm": ((current.depth_mm, proposal.depth_mm),),
        "geometry": (
            (current.span_mm, proposal.span_mm),
            (current.section_shape, proposal.section_shape),
            (current.flange_width_mm, proposal.flange_width_mm),
            (current.flange_thickness_mm, proposal.flange_thickness_mm),
        ),
        "bottom": (
            (current.bottom.mode, proposal.bottom_mode),
            (current.bottom.bars, proposal.bottom_bars),
            (current.bottom.spacing_mm, proposal.bottom_spacing_mm),
            (current.bottom.diameter_mm, proposal.bottom_diameter_mm),
            (current.bottom.cover_mm, proposal.bottom_cover_mm),
        ),
        "top": (
            (current.top.mode, proposal.top_mode),
            (current.top.bars, proposal.top_bars),
            (current.top.spacing_mm, proposal.top_spacing_mm),
            (current.top.diameter_mm, proposal.top_diameter_mm),
            (current.top.cover_mm, proposal.top_cover_mm),
        ),
        "shear": (
            (current.shear.diameter_mm, proposal.shear_diameter_mm),
            (current.shear.legs, proposal.shear_legs),
            (current.shear.spacing_mm, proposal.shear_spacing_mm),
        ),
        "materials": (
            (current.materials.concrete_strength_mpa, proposal.concrete_strength_mpa),
            (current.materials.reinforcement_strength_mpa, proposal.reinforcement_strength_mpa),
        ),
        "actions": (
            (current.actions.bending_moment_knm, proposal.bending_moment_knm),
            (current.actions.torsion_knm, proposal.torsion_knm),
            (current.actions.shear_force_kn, proposal.shear_force_kn),
            (current.actions.axial_force_kn, proposal.axial_force_kn),
        ),
        "supports": (
            (current.supports.left_type, proposal.left_support),
            (current.supports.right_type, proposal.right_support),
        ),
        "serviceability_inputs": (
            (current.serviceability.moment_knm, proposal.sls_moment_knm),
            (current.serviceability.shear_kn, proposal.sls_shear_kn),
            (current.serviceability.permanent_udl_knm_per_m, proposal.sls_permanent_udl_knm_per_m),
            (current.serviceability.imposed_udl_knm_per_m, proposal.sls_imposed_udl_knm_per_m),
            (current.serviceability.equivalent_udl_knm_per_m, proposal.sls_equivalent_udl_knm_per_m),
        ),
    }
    changed_groups = tuple(
        group for group, comparisons in groups.items()
        if any(before != after for before, after in comparisons)
    )
    forbidden = set(contract.prohibited_changes)
    permitted = set(contract.permitted_changes)
    leaks = tuple(group for group in changed_groups if group in forbidden or group not in permitted)
    if leaks:
        raise ValueError(
            f"{contract.family.value} proposal crosses owned boundaries: {', '.join(leaks)}"
        )
