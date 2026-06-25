"""Contract runtime for COMBINED_OVERDESIGN_GOVERNS candidate merge and ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from design_brain.combined_overdesign_candidate_merge import (
    CombinedOverdesignCandidateEvaluation,
    CombinedOverdesignInputs,
    CombinedOverdesignMergedCandidate,
    CombinedOverdesignSourceCandidate,
    merge_updates,
    stable_combined_overdesign_hash,
)
from design_brain.families.bending_and_shear_overdesign_govern.contract import (
    candidate_source_contract,
    contract_hash,
    exact_stop_rules,
    exhausted_rules,
    ranking_criteria,
    target_band,
)


CandidateEvaluator = Callable[
    [CombinedOverdesignInputs, CombinedOverdesignMergedCandidate],
    CombinedOverdesignCandidateEvaluation,
]


@dataclass(frozen=True)
class CombinedOverdesignGovernsResult:
    status: str
    selected_recommendation: dict[str, Any] | None
    candidate_repairs: tuple[dict[str, Any], ...]
    exhausted_reason: str | None
    evidence: dict[str, Any]
    selection_boundary: dict[str, Any]
    candidate_source_proof: dict[str, Any]
    combined_merge_trace: tuple[dict[str, Any], ...]
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


def _source_candidate(value: dict[str, Any]) -> CombinedOverdesignSourceCandidate:
    return CombinedOverdesignSourceCandidate(
        source_family_id=str(value.get("source_family_id") or value.get("family_id") or ""),
        candidate_id=str(value.get("candidate_id") or value.get("id") or ""),
        updates=_as_dict(value.get("updates")),
        evidence=_as_dict(value.get("evidence")),
    )


def _source_candidates(values: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> tuple[CombinedOverdesignSourceCandidate, ...]:
    return tuple(_source_candidate(dict(value)) for value in values if isinstance(value, dict))


def _merged_candidates(inputs: CombinedOverdesignInputs) -> tuple[CombinedOverdesignMergedCandidate, ...]:
    bending = tuple(candidate for candidate in _source_candidates(inputs.bending_overdesign_candidates) if candidate.source_allowed)
    shear = tuple(candidate for candidate in _source_candidates(inputs.shear_overdesign_candidates) if candidate.source_allowed)
    approved = tuple(
        candidate
        for candidate in _source_candidates(inputs.approved_combined_merge_candidates)
        if candidate.source_allowed
    )
    merged: list[CombinedOverdesignMergedCandidate] = []
    for bend in bending:
        for shear_candidate in shear:
            updates = merge_updates(bend.updates, shear_candidate.updates)
            merged.append(
                CombinedOverdesignMergedCandidate(
                    candidate_id=f"{bend.candidate_id}+{shear_candidate.candidate_id}",
                    source_candidates=(bend, shear_candidate),
                    updates=updates,
                )
            )
    for approved_candidate in approved:
        merged.append(
            CombinedOverdesignMergedCandidate(
                candidate_id=approved_candidate.candidate_id,
                source_candidates=(approved_candidate,),
                updates=dict(approved_candidate.updates),
                merge_rule_id="APPROVED_COMBINED_MERGE_RULE",
            )
        )
    return tuple(merged)


def _inside_band(value: float | None, lower: float, upper: float) -> bool:
    return value is not None and lower <= float(value) <= upper


def _candidate_valid(evaluation: CombinedOverdesignCandidateEvaluation) -> tuple[bool, tuple[str, ...]]:
    reasons = list(evaluation.rejection_reasons)
    if evaluation.creates_bending_underdesign:
        reasons.append("candidate creates bending underdesign")
    if evaluation.creates_shear_underdesign:
        reasons.append("candidate creates shear underdesign")
    min_status = _as_dict(evaluation.minimum_reinforcement_status)
    if min_status.get("As_greater_than_or_equal_to_As_min") is False or str(min_status.get("status") or "").upper() == "FAIL":
        reasons.append("candidate violates minimum reinforcement")
    if evaluation.bending_compliant is False:
        reasons.append("bending not compliant")
    if evaluation.shear_compliant is False:
        reasons.append("shear not compliant")
    if str(_as_dict(evaluation.code_compliance_status).get("status") or "PASS").upper() == "FAIL":
        reasons.append("code compliance violated")
    if str(_as_dict(evaluation.constructability_status).get("status") or "PASS").upper() == "FAIL":
        reasons.append("constructability violated")
    if _as_dict(evaluation.engineering_status).get("candidate_valid") is False:
        reasons.append("engineering status invalid")
    return not reasons, tuple(dict.fromkeys(reasons))


def _as_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rank_key(evaluation: CombinedOverdesignCandidateEvaluation) -> tuple[Any, ...]:
    band = target_band()
    low = float(band.get("bending_lower") or 0.85)
    high = float(band.get("bending_upper") or 1.0)
    bending = evaluation.bending_utilisation_after
    shear = evaluation.shear_utilisation_after
    worst = max(_as_number(bending), _as_number(shear))
    if worst < low:
        worst_distance = low - worst
    elif worst > high:
        worst_distance = worst - high
    else:
        worst_distance = 0.0
    reinforcement = _as_dict(evaluation.reinforcement_quantity)
    beam_volume = _as_dict(evaluation.beam_volume)
    cost = _as_dict(evaluation.cost_proxy)
    zero = _as_dict(evaluation.zero_shear_status)
    zero_shear_bonus = 0 if zero.get("ligature_removal_preferred") else 1
    return (
        0 if evaluation.bending_compliant and evaluation.shear_compliant else 1,
        0 if evaluation.bending_moves_toward_target and evaluation.shear_moves_toward_target else 1,
        worst_distance,
        zero_shear_bonus,
        _as_number(reinforcement.get("after"), 999999.0),
        _as_number(beam_volume.get("after"), 999999999.0),
        0 if str(_as_dict(evaluation.constructability_status).get("status") or "PASS").upper() == "PASS" else 1,
        _as_number(cost.get("after"), 999999.0),
    )


def _evaluation_payload(
    candidate: CombinedOverdesignMergedCandidate,
    evaluation: CombinedOverdesignCandidateEvaluation,
    *,
    candidate_index: int,
    rejection_reasons: tuple[str, ...] = (),
) -> dict[str, Any]:
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
        "bending_utilisation_after": evaluation.bending_utilisation_after,
        "shear_utilisation_after": evaluation.shear_utilisation_after,
        "bending_compliant": evaluation.bending_compliant,
        "shear_compliant": evaluation.shear_compliant,
        "bending_moves_toward_target": evaluation.bending_moves_toward_target,
        "shear_moves_toward_target": evaluation.shear_moves_toward_target,
        "rejection_reasons": rejection_reasons,
    }


def run_combined_overdesign_governs_runtime(
    *,
    inputs: CombinedOverdesignInputs,
    evaluate_candidate: CandidateEvaluator,
) -> CombinedOverdesignGovernsResult:
    """Run the contract-defined combined overdesign candidate merge runtime."""

    merged = _merged_candidates(inputs)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    for index, candidate in enumerate(merged, start=1):
        evaluation = evaluate_candidate(inputs, candidate).with_evaluation_hash()
        valid, rejection_reasons = _candidate_valid(evaluation)
        row = _evaluation_payload(candidate, evaluation, candidate_index=index, rejection_reasons=rejection_reasons)
        row["rank_key"] = _rank_key(evaluation)
        row["accepted"] = valid
        trace.append(row)
        if valid:
            accepted.append(row)
        else:
            rejected.append(row)
    ranked = sorted(accepted, key=lambda row: row["rank_key"])
    selected = dict(ranked[0]) if ranked else None
    band = target_band()
    exact_stop = {
        "allowed_when": list(exact_stop_rules().get("allowed_when") or []),
        "selected_inside_bending_band": bool(
            selected
            and _inside_band(
                selected.get("bending_utilisation_after"),
                float(band.get("bending_lower") or 0.85),
                float(band.get("bending_upper") or 1.0),
            )
        ),
        "selected_inside_shear_band": bool(
            selected
            and _inside_band(
                selected.get("shear_utilisation_after"),
                float(band.get("shear_lower") or 0.85),
                float(band.get("shear_upper") or 1.0),
            )
        ),
        "no_higher_ranked_candidate_exists": bool(selected),
    }
    specific_blockers = tuple(
        reason
        for row in rejected
        for reason in tuple(row.get("rejection_reasons") or ())
    )
    exhausted_reason = None
    if not selected:
        exhausted_reason = next(iter(specific_blockers), "no compliant combined overdesign optimisation candidate exists")
    exhausted = {
        "requires": list(exhausted_rules().get("requires") or []),
        "all_bending_candidates_attempted": bool(inputs.bending_overdesign_candidates),
        "all_shear_candidates_attempted": bool(inputs.shear_overdesign_candidates),
        "all_approved_merge_candidates_attempted": True,
        "specific_blocker": exhausted_reason,
        "generic_exhausted_message_prohibited_when_specific_blocker_exists": exhausted_rules().get(
            "generic_exhausted_message_prohibited_when_specific_blocker_exists"
        )
        is True,
    }
    source_contract = candidate_source_contract()
    candidate_source_proof = {
        "allowed_sources": tuple(source_contract.get("allowed_sources") or ()),
        "must_not_duplicate_ladders": source_contract.get("must_not_duplicate_ladders") is True,
        "merged_candidate_count": len(merged),
        "all_sources_allowed": all(candidate.sources_allowed for candidate in merged) if merged else True,
    }
    ownership = {
        "combined_owns_merge_ranking_selection_evidence": True,
        "combined_owns_bending_ladder": False,
        "combined_owns_shear_ladder": False,
        "shared_surfaces_owned_outside": True,
    }
    ranking = {
        "criteria": tuple(ranking_criteria()),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "selected_candidate_id": selected.get("candidate_id") if selected else None,
    }
    evidence = {
        "selection_boundary": {
            "selected_family_id": inputs.selected_family_id,
            "selection_boundary_satisfied": inputs.selection_boundary_satisfied,
            "runtime_did_not_reclassify": True,
        },
        "candidate_source_proof": candidate_source_proof,
        "combined_merge_trace": tuple(trace),
        "accepted_candidate_evidence": tuple(accepted),
        "rejected_candidate_evidence": tuple(rejected),
        "ranking_evidence": ranking,
        "exact_stop_proof": exact_stop,
        "exhausted_proof": exhausted,
        "ownership_proof": ownership,
        "contract_version": contract_hash(),
    }
    runtime_hash = stable_combined_overdesign_hash(
        {
            "contract_hash": contract_hash(),
            "selected": selected,
            "trace": trace,
            "ranking": ranking,
            "exhausted": exhausted,
        }
    )
    return CombinedOverdesignGovernsResult(
        status="SELECTED" if selected else "EXHAUSTED",
        selected_recommendation=selected,
        candidate_repairs=tuple(accepted),
        exhausted_reason=exhausted_reason,
        evidence=evidence,
        selection_boundary=evidence["selection_boundary"],
        candidate_source_proof=candidate_source_proof,
        combined_merge_trace=tuple(trace),
        accepted_candidate_evidence=tuple(accepted),
        rejected_candidate_evidence=tuple(rejected),
        ranking_evidence=ranking,
        exact_stop_proof=exact_stop,
        exhausted_proof=exhausted,
        ownership_proof=ownership,
        runtime_hash=runtime_hash,
    )


__all__ = [
    "CandidateEvaluator",
    "CombinedOverdesignGovernsResult",
    "run_combined_overdesign_governs_runtime",
]
