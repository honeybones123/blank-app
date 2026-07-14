from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from design_brain.bending_fail_shear_overdesign_candidate_merge import (
    BendingFailShearOverdesignInputs,
    MixedCandidateEvaluation,
    MixedMergedCandidate,
    MixedSourceCandidate,
    merge_updates,
    stable_bending_fail_shear_overdesign_hash,
)
from design_brain.families.bending_fail_shear_overdesign_governs.contract import (
    candidate_source_contract,
    contract_hash,
    exact_stop_rules,
    exhausted_rules,
    priority_contract,
    ranking_criteria,
    target_band,
)


CandidateEvaluator = Callable[
    [BendingFailShearOverdesignInputs, MixedMergedCandidate],
    MixedCandidateEvaluation,
]


@dataclass(frozen=True)
class BendingFailShearOverdesignResult:
    status: str
    selected_recommendation: dict[str, Any] | None
    candidate_repairs: tuple[dict[str, Any], ...]
    exhausted_reason: str | None
    evidence: dict[str, Any]
    selection_boundary: dict[str, Any]
    candidate_source_proof: dict[str, Any]
    mixed_merge_trace: tuple[dict[str, Any], ...]
    accepted_candidate_evidence: tuple[dict[str, Any], ...]
    rejected_candidate_evidence: tuple[dict[str, Any], ...]
    ranking_evidence: dict[str, Any]
    exact_stop_proof: dict[str, Any]
    exhausted_proof: dict[str, Any]
    ownership_proof: dict[str, Any]
    runtime_hash: str

    def to_family_result_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "selected_recommendation": self.selected_recommendation,
            "candidate_repairs": self.candidate_repairs,
            "exhausted_reason": self.exhausted_reason,
            "evidence": self.evidence,
            "runtime_hash": self.runtime_hash,
        }


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _source_candidate(value: dict[str, Any]) -> MixedSourceCandidate:
    return MixedSourceCandidate(
        source_family_id=str(value.get("source_family_id") or value.get("family_id") or ""),
        candidate_id=str(value.get("candidate_id") or value.get("id") or ""),
        updates=_as_dict(value.get("updates")),
        evidence=_as_dict(value.get("evidence")),
    )


def _source_candidates(values: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> tuple[MixedSourceCandidate, ...]:
    return tuple(_source_candidate(dict(value)) for value in values if isinstance(value, dict))


def _merged_candidates(inputs: BendingFailShearOverdesignInputs) -> tuple[MixedMergedCandidate, ...]:
    bending = tuple(candidate for candidate in _source_candidates(inputs.bending_fail_candidates) if candidate.source_allowed)
    shear = tuple(candidate for candidate in _source_candidates(inputs.shear_overdesign_candidates) if candidate.source_allowed)
    approved = tuple(candidate for candidate in _source_candidates(inputs.approved_mixed_merge_candidates) if candidate.source_allowed)
    merged: list[MixedMergedCandidate] = []
    for bend in bending:
        # Bending repair alone is valid as a fallback because bending repair is mandatory.
        merged.append(
            MixedMergedCandidate(
                candidate_id=bend.candidate_id,
                source_candidates=(bend,),
                updates=dict(bend.updates),
                merge_rule_id="MANDATORY_BENDING_REPAIR_ONLY",
            )
        )
        for shear_candidate in shear:
            merged.append(
                MixedMergedCandidate(
                    candidate_id=f"{bend.candidate_id}+{shear_candidate.candidate_id}",
                    source_candidates=(bend, shear_candidate),
                    updates=merge_updates(bend.updates, shear_candidate.updates),
                )
            )
    for approved_candidate in approved:
        merged.append(
            MixedMergedCandidate(
                candidate_id=approved_candidate.candidate_id,
                source_candidates=(approved_candidate,),
                updates=dict(approved_candidate.updates),
                merge_rule_id="APPROVED_MIXED_MERGE_RULE",
            )
        )
    return tuple(merged)


def _status_fail(status: dict[str, Any]) -> bool:
    return str(status.get("status") or status.get("overall") or "PASS").upper() == "FAIL"


def _candidate_valid(candidate: MixedMergedCandidate, evaluation: MixedCandidateEvaluation) -> tuple[bool, tuple[str, ...]]:
    reasons = list(evaluation.rejection_reasons)
    if not candidate.has_mandatory_bending_source:
        reasons.append("missing mandatory bending repair source")
    if evaluation.bending_repaired is not True:
        reasons.append("candidate leaves bending underdesign unresolved")
    if evaluation.shear_compliant is not True or evaluation.creates_shear_underdesign is True:
        reasons.append("candidate creates shear underdesign")
    if _status_fail(_as_dict(evaluation.code_compliance_status)):
        reasons.append("candidate violates code compliance")
    if _status_fail(_as_dict(evaluation.constructability_status)):
        reasons.append("candidate violates constructability")
    if _as_dict(evaluation.engineering_status).get("candidate_valid") is False:
        reasons.append("engineering status invalid")
    return not reasons, tuple(dict.fromkeys(reasons))


def _as_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _target_distance(value: float | None, lower: float = 0.85, upper: float = 1.0) -> float:
    if value is None:
        return 999.0
    parsed = float(value)
    if parsed < lower:
        return lower - parsed
    if parsed > upper:
        return parsed - upper
    return 0.0


def _inside_band(value: Any, lower: Any, upper: Any) -> bool:
    try:
        parsed = float(value)
        lower_f = float(lower)
        upper_f = float(upper)
    except (TypeError, ValueError):
        return False
    return lower_f <= parsed <= upper_f


def _row_inside_target_band(row: dict[str, Any], band: dict[str, Any]) -> bool:
    evaluation = _as_dict(row.get("evaluation"))
    return bool(
        _inside_band(
            evaluation.get("bending_utilisation_after"),
            band.get("bending_lower", 0.85),
            band.get("bending_upper", 1.0),
        )
        and _inside_band(
            evaluation.get("shear_utilisation_after"),
            band.get("shear_lower", 0.85),
            band.get("shear_upper", 1.0),
        )
    )


def _rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    evaluation = _as_dict(row.get("evaluation"))
    reinforcement = _as_dict(evaluation.get("reinforcement_quantity"))
    beam_volume = _as_dict(evaluation.get("beam_volume"))
    cost = _as_dict(evaluation.get("cost_proxy"))
    return (
        0 if evaluation.get("bending_repaired") is True else 1,
        0 if evaluation.get("shear_compliant") is True else 1,
        _target_distance(evaluation.get("bending_utilisation_after")),
        _target_distance(evaluation.get("shear_utilisation_after")),
        _as_number(beam_volume.get("geometry_increase"), 0.0),
        _as_number(reinforcement.get("increase"), 0.0),
        0 if not _status_fail(_as_dict(evaluation.get("constructability_status"))) else 1,
        _as_number(cost.get("after"), 0.0),
    )


def _row(
    candidate: MixedMergedCandidate,
    evaluation: MixedCandidateEvaluation,
    *,
    candidate_index: int,
    rejection_reasons: tuple[str, ...],
    accepted: bool,
) -> dict[str, Any]:
    payload = evaluation.to_dict()
    return {
        "candidate_index": candidate_index,
        "candidate_id": candidate.candidate_id,
        "source_family_ids": candidate.source_families,
        "source_candidates": tuple(source.candidate_id for source in candidate.source_candidates),
        "merge_rule_id": candidate.merge_rule_id,
        "updates": dict(candidate.updates),
        "update_hash": candidate.update_hash,
        "candidate_state_hash": evaluation.candidate_state_hash,
        "evaluation_hash": evaluation.evaluation_hash,
        "bending_repaired": evaluation.bending_repaired,
        "shear_compliant": evaluation.shear_compliant,
        "creates_shear_underdesign": evaluation.creates_shear_underdesign,
        "rejection_reasons": rejection_reasons,
        "accepted": accepted,
        "evaluation": payload,
    }


def run_bending_fail_shear_overdesign_runtime(
    *,
    inputs: BendingFailShearOverdesignInputs,
    evaluate_candidate: CandidateEvaluator,
) -> BendingFailShearOverdesignResult:
    merged = _merged_candidates(inputs)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    for index, candidate in enumerate(merged, start=1):
        evaluation = evaluate_candidate(inputs, candidate).with_evaluation_hash()
        valid, rejection_reasons = _candidate_valid(candidate, evaluation)
        row = _row(
            candidate,
            evaluation,
            candidate_index=index,
            rejection_reasons=rejection_reasons,
            accepted=valid,
        )
        row["rank_key"] = _rank_key(row)
        trace.append(row)
        if valid:
            accepted.append(row)
        else:
            rejected.append(row)
    ranked = sorted(accepted, key=_rank_key)
    selected = dict(ranked[0]) if ranked else None
    band = target_band()
    target_band_candidate_count = sum(1 for row in accepted if _row_inside_target_band(row, band))
    selected_inside_target_band = bool(selected and _row_inside_target_band(selected, band))
    selected_evaluation = _as_dict(selected.get("evaluation") if selected else {})
    target_band_refinement_proof = {
        "lane_id": band.get("candidate_lane"),
        "target_band_candidate_count": target_band_candidate_count,
        "selected_inside_target_band": selected_inside_target_band,
        "selected_inside_bending_band": bool(
            selected
            and _inside_band(
                selected_evaluation.get("bending_utilisation_after"),
                band.get("bending_lower", 0.85),
                band.get("bending_upper", 1.0),
            )
        ),
        "selected_inside_shear_band": bool(
            selected
            and _inside_band(
                selected_evaluation.get("shear_utilisation_after"),
                band.get("shear_lower", 0.85),
                band.get("shear_upper", 1.0),
            )
        ),
        "fallback_reason": None
        if selected_inside_target_band
        else band.get("fallback"),
    }
    specific_blockers = tuple(reason for row in rejected for reason in tuple(row.get("rejection_reasons") or ()))
    exhausted_reason = None if selected else next(iter(specific_blockers), "no valid mixed recommendation exists")
    source_contract = candidate_source_contract()
    candidate_source_proof = {
        "allowed_sources": tuple(source_contract.get("allowed_sources") or ()),
        "must_not_duplicate_ladders": source_contract.get("must_not_duplicate_ladders") is True,
        "mandatory_source": source_contract.get("mandatory_source"),
        "opportunistic_source": source_contract.get("opportunistic_source"),
        "merged_candidate_count": len(merged),
        "all_sources_allowed": all(candidate.sources_allowed for candidate in merged) if merged else True,
    }
    ranking = {
        "criteria": tuple(ranking_criteria()),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "selected_candidate_id": selected.get("candidate_id") if selected else None,
        "target_band_candidate_count": target_band_candidate_count,
        "target_band_selected": selected_inside_target_band,
        "fallback_reason": target_band_refinement_proof.get("fallback_reason"),
    }
    exact_stop = {
        "allowed_when": tuple(exact_stop_rules().get("allowed_when") or ()),
        "selected_bending_repaired": bool(selected and selected.get("bending_repaired")),
        "selected_shear_compliant": bool(selected and selected.get("shear_compliant")),
        "selected_inside_bending_band": bool(target_band_refinement_proof.get("selected_inside_bending_band")),
        "selected_inside_shear_band": bool(target_band_refinement_proof.get("selected_inside_shear_band")),
        "no_higher_ranked_candidate_exists": bool(ranked and selected == ranked[0]),
        "shear_optimisation_opportunistic_only": priority_contract().get("opportunistic_objective") == "shear optimisation",
    }
    exhausted = {
        "requires": tuple(exhausted_rules().get("requires") or ()),
        "all_bending_repair_candidates_attempted": bool(inputs.bending_fail_candidates),
        "all_shear_optimisation_candidates_attempted": True,
        "all_approved_merge_candidates_attempted": True,
        "specific_blocker": exhausted_reason,
    }
    ownership = {
        "mixed_owns_merge_ranking_selection_evidence": True,
        "mixed_owns_bending_repair_ladder": False,
        "mixed_owns_shear_optimisation_ladder": False,
        "shared_surfaces_owned_outside": True,
    }
    evidence = {
        "selection_boundary": {
            "selected_family_id": inputs.selected_family_id,
            "selection_boundary_satisfied": inputs.selection_boundary_satisfied,
            "runtime_did_not_reclassify": True,
        },
        "candidate_source_proof": candidate_source_proof,
        "mixed_merge_trace": tuple(trace),
        "accepted_candidate_evidence": tuple(accepted),
        "rejected_candidate_evidence": tuple(rejected),
        "ranking_evidence": ranking,
        "target_band_refinement_proof": target_band_refinement_proof,
        "exact_stop_proof": exact_stop,
        "exhausted_proof": exhausted,
        "ownership_proof": ownership,
        "contract_version": contract_hash(),
    }
    runtime_hash = stable_bending_fail_shear_overdesign_hash(
        {
            "contract_hash": contract_hash(),
            "selected": selected,
            "trace": trace,
            "ranking": ranking,
            "exhausted": exhausted,
        }
    )
    return BendingFailShearOverdesignResult(
        status="SELECTED" if selected else "EXHAUSTED",
        selected_recommendation=selected,
        candidate_repairs=tuple(accepted),
        exhausted_reason=exhausted_reason,
        evidence=evidence,
        selection_boundary=evidence["selection_boundary"],
        candidate_source_proof=candidate_source_proof,
        mixed_merge_trace=tuple(trace),
        accepted_candidate_evidence=tuple(accepted),
        rejected_candidate_evidence=tuple(rejected),
        ranking_evidence=ranking,
        exact_stop_proof=exact_stop,
        exhausted_proof=exhausted,
        ownership_proof=ownership,
        runtime_hash=runtime_hash,
    )


__all__ = [
    "BendingFailShearOverdesignResult",
    "BendingFailShearOverdesignInputs",
    "CandidateEvaluator",
    "run_bending_fail_shear_overdesign_runtime",
]
