from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from design_brain.combined_bending_shear_candidate_merge import (
    CombinedBendingShearFailInputs,
    CombinedCandidateEvaluation,
    CombinedMergedCandidate,
    CombinedSourceCandidate,
    combined_candidate_state_hash,
    merge_updates,
    normalise_combined_canonical_reinforcement_updates,
    stable_combined_candidate_hash,
)
from design_brain.families.bending_and_shear_fail_govern.contract import (
    candidate_source_contract,
    contract_hash,
    exact_stop_rules,
    exhausted_rules,
    family_identity,
    load_bending_and_shear_fail_govern_contract,
    ranking_criteria,
    selection_boundary,
    target_band_refinement_lane,
)


CandidateEvaluator = Callable[[CombinedBendingShearFailInputs, CombinedMergedCandidate], CombinedCandidateEvaluation]


@dataclass(frozen=True)
class CombinedBendingShearFailResult:
    """Contract-driven combined bending/shear active-fail merge result."""

    status: str
    selected_strategy_lane: str | None
    combined_merge_trace: tuple[dict[str, Any], ...]
    candidate_repairs: tuple[dict[str, Any], ...]
    selected_recommendation: dict[str, Any] | None
    accepted_candidate_evidence: tuple[dict[str, Any], ...]
    rejected_candidate_evidence: tuple[dict[str, Any], ...]
    ranking_evidence: dict[str, Any]
    exact_stop_proof: dict[str, Any]
    exhausted_reason: str | None
    exhausted_proof: dict[str, Any]
    candidate_source_proof: dict[str, Any]
    target_band_refinement_proof: dict[str, Any]
    ownership_proof: dict[str, Any]
    selection_boundary_proof: dict[str, Any]
    cta_intent_proof: dict[str, Any]
    contract_hash: str
    runtime_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _source_candidate(value: dict[str, Any]) -> CombinedSourceCandidate:
    return CombinedSourceCandidate(
        source_family_id=str(value.get("source_family_id") or value.get("family_id") or ""),
        candidate_id=str(value.get("candidate_id") or value.get("id") or ""),
        updates=normalise_combined_canonical_reinforcement_updates(dict(value.get("updates") or {})),
        evidence=dict(value.get("evidence") or {}),
    )


def _merged_candidates(inputs: CombinedBendingShearFailInputs) -> tuple[CombinedMergedCandidate, ...]:
    bending_candidates = tuple(_source_candidate(candidate) for candidate in inputs.bending_fail_candidates)
    shear_candidates = tuple(_source_candidate(candidate) for candidate in inputs.shear_fail_candidates)
    approved_candidates = tuple(
        candidate
        for candidate in (_source_candidate(candidate) for candidate in inputs.approved_combined_merge_candidates)
        if candidate.source_allowed
    )
    merged: list[CombinedMergedCandidate] = []
    seen_candidate_ids: set[str] = set()

    def _append(
        *,
        candidate_id: str,
        sources: tuple[CombinedSourceCandidate, ...],
        updates: dict[str, Any],
        merge_rule_id: str,
    ) -> None:
        if not candidate_id or candidate_id in seen_candidate_ids or not updates:
            return
        seen_candidate_ids.add(candidate_id)
        merged.append(
            CombinedMergedCandidate(
                candidate_id=candidate_id,
                source_candidates=sources,
                updates=updates,
                merge_rule_id=merge_rule_id,
            )
        )

    def _is_reinforcement_only(candidate: CombinedSourceCandidate) -> bool:
        flags = candidate.interaction_flags
        return bool(
            flags.get("bending_reinforcement_changed")
            and not flags.get("shear_reinforcement_changed")
            and not flags.get("geometry_changed")
        )

    def _is_shear_only(candidate: CombinedSourceCandidate) -> bool:
        flags = candidate.interaction_flags
        return bool(
            flags.get("shear_reinforcement_changed")
            and not flags.get("bending_reinforcement_changed")
            and not flags.get("geometry_changed")
        )

    # The family contract is progressive: try each source-domain adjustment
    # independently before combining them, and do not enter shared geometry
    # until reinforcement-only, shear-only, and non-geometry combined
    # adjustments have been exhausted.
    bending_reinforcement_only = tuple(
        candidate
        for candidate in bending_candidates
        if _is_reinforcement_only(candidate)
    )
    shear_reinforcement_only = tuple(
        candidate
        for candidate in shear_candidates
        if _is_shear_only(candidate)
    )
    for candidate in bending_reinforcement_only:
        _append(
            candidate_id=f"bending_only:{candidate.candidate_id}",
            sources=(candidate,),
            updates=dict(candidate.updates),
            merge_rule_id="BENDING_REINFORCEMENT_ONLY",
        )
    for candidate in shear_reinforcement_only:
        _append(
            candidate_id=f"shear_only:{candidate.candidate_id}",
            sources=(candidate,),
            updates=dict(candidate.updates),
            merge_rule_id="SHEAR_REINFORCEMENT_ONLY",
        )

    if bending_candidates and shear_candidates:
        staged_pairs = sorted(
            (
                (bend_index, shear_index, bend, shear)
                for bend_index, bend in enumerate(bending_candidates)
                for shear_index, shear in enumerate(shear_candidates)
            ),
            key=lambda row: (
                max(row[0], row[1]),
                row[0] + row[1],
                row[0],
                row[1],
            ),
        )
        non_geometry_pairs = []
        geometry_pairs = []
        for bend_index, shear_index, bend, shear in staged_pairs:
            updates = merge_updates(bend.updates, shear.updates)
            flags = CombinedMergedCandidate(
                candidate_id="classification_probe",
                source_candidates=(bend, shear),
                updates=updates,
            ).interaction_flags
            row = (bend_index, shear_index, bend, shear, updates)
            if flags.get("geometry_changed"):
                geometry_pairs.append(row)
            else:
                non_geometry_pairs.append(row)
        for bend_index, shear_index, bend, shear, updates in non_geometry_pairs:
            _append(
                candidate_id=(
                    f"combined_adjustment:{bend.candidate_id}+"
                    f"{shear.candidate_id}"
                ),
                sources=(bend, shear),
                updates=updates,
                merge_rule_id="COMBINED_ADJUSTMENT",
            )
        for bend_index, shear_index, bend, shear, updates in geometry_pairs:
            _append(
                candidate_id=(
                    f"geometry:{bend.candidate_id}+{shear.candidate_id}"
                ),
                sources=(bend, shear),
                updates=updates,
                merge_rule_id="GEOMETRY_FALLBACK",
            )
    for approved in approved_candidates:
        _append(
            candidate_id=approved.candidate_id,
            sources=(approved,),
            updates=normalise_combined_canonical_reinforcement_updates(
                dict(approved.updates)
            ),
            merge_rule_id="APPROVED_COMBINED_MERGE_RULE",
        )
    return tuple(merged)


def _status_pass(value: dict[str, Any]) -> bool:
    return str(value.get("status") or "").upper() in {"PASS", "OK", "TRUE", "COMPLIANT"}


def _valid_combined_candidate(evaluation: CombinedCandidateEvaluation) -> bool:
    return (
        evaluation.both_failures_repaired is True
        and evaluation.bending_compliant is True
        and evaluation.shear_compliant is True
        and _status_pass(dict(evaluation.code_compliance_status or {}))
        and _status_pass(dict(evaluation.detailing_status or {}))
        and _status_pass(dict(evaluation.constructability_status or {}))
        and bool((evaluation.engineering_status or {}).get("candidate_valid", True))
    )


def _numeric_after(candidate: dict[str, Any], field: str, default: float = 999999.0) -> float:
    try:
        return float((candidate.get(field) or {}).get("after", default))
    except (TypeError, ValueError, AttributeError):
        return default


def _geometry_increase(candidate: dict[str, Any]) -> float:
    data = candidate.get("geometry_increase") or {}
    try:
        return float(data.get("total_mm", 0.0))
    except (TypeError, ValueError, AttributeError):
        return 999999.0


def _reinforcement_increase(candidate: dict[str, Any]) -> float:
    data = candidate.get("reinforcement_increase") or {}
    try:
        return float(data.get("total", 0.0))
    except (TypeError, ValueError, AttributeError):
        return 999999.0


def _worst_target_distance(candidate: dict[str, Any]) -> float:
    values = []
    for key in ("bending_utilisation_after", "shear_utilisation_after"):
        try:
            values.append(abs(float(candidate.get(key)) - 0.925))
        except (TypeError, ValueError):
            values.append(999999.0)
    return max(values)


def _ranking_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    both_inside = bool(candidate.get("bending_inside_target_band")) and bool(candidate.get("shear_inside_target_band"))
    constructability = str((candidate.get("constructability_status") or {}).get("status") or "")
    return (
        not bool(candidate.get("both_failures_repaired")),
        not both_inside,
        _worst_target_distance(candidate),
        _geometry_increase(candidate),
        _reinforcement_increase(candidate),
        constructability.upper() not in {"PASS", "OK", "TRUE", "COMPLIANT"},
        _numeric_after(candidate, "cost_proxy"),
        int(candidate.get("candidate_index") or 0),
    )


def _hash_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "runtime_hash"}


def run_combined_bending_shear_fail_runtime(
    *,
    inputs: CombinedBendingShearFailInputs,
    evaluate_candidate: CandidateEvaluator,
) -> CombinedBendingShearFailResult:
    """Run the contract-defined combined active-fail candidate merge runtime."""

    contract = load_bending_and_shear_fail_govern_contract()
    identity = family_identity()
    merged = _merged_candidates(inputs)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []

    for index, candidate in enumerate(merged, start=1):
        evaluation = evaluate_candidate(inputs, candidate)
        if not isinstance(evaluation, CombinedCandidateEvaluation):
            raise TypeError("evaluate_candidate must return CombinedCandidateEvaluation")
        if evaluation.evaluation_hash is None:
            evaluation = evaluation.with_evaluation_hash()
        valid = candidate.sources_allowed and _valid_combined_candidate(evaluation)
        row = {
            "candidate_index": index,
            "candidate_id": candidate.candidate_id,
            "source_family_ids": candidate.source_families,
            "merge_rule_id": candidate.merge_rule_id,
            "updates": dict(candidate.updates),
            "update_hash": candidate.update_hash,
            "candidate_state_hash": evaluation.candidate_state_hash,
            "evaluation_hash": evaluation.evaluation_hash,
            "accepted": valid,
            **{
                key: value
                for key, value in evaluation.to_dict().items()
                if key not in {"input_hash", "update_hash", "candidate_state_hash", "evaluation_hash"}
            },
        }
        repairs.append(row)
        trace.append(
            {
                "candidate_index": index,
                "candidate_id": candidate.candidate_id,
                "accepted": valid,
                "source_family_ids": candidate.source_families,
                "update_hash": candidate.update_hash,
                "evaluation_hash": evaluation.evaluation_hash,
            }
        )
        if valid:
            accepted.append(row)
        else:
            rejected.append(row)

    ranked = sorted(accepted, key=_ranking_key)
    selected = dict(ranked[0]) if ranked else None
    selected_lane = "COMBINED_SOURCE_MERGE" if selected else None
    target_band_repairs = [
        row
        for row in accepted
        if row.get("bending_inside_target_band") is True and row.get("shear_inside_target_band") is True
    ]
    exact_stop = bool(
        selected
        and selected.get("bending_compliant") is True
        and selected.get("shear_compliant") is True
        and selected.get("bending_inside_target_band") is True
        and selected.get("shear_inside_target_band") is True
    )
    missing_bending = not inputs.bending_fail_candidates
    missing_shear = not inputs.shear_fail_candidates
    exhausted_reason = None
    if not selected:
        if missing_bending:
            exhausted_reason = "bending repair exhausted"
        elif missing_shear:
            exhausted_reason = "shear repair exhausted"
        else:
            exhausted_reason = "no valid combined repair exists"
    status = "EXACT_STOP" if exact_stop else ("SELECTED" if selected else "EXHAUSTED")
    fallback_reason = None
    if selected and not exact_stop:
        fallback_reason = "best compliant combined repair selected because no evaluated target-band combined repair exists"
    ranking = {
        "criteria": tuple(ranking_criteria()),
        "candidate_count": len(repairs),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "target_band_candidate_count": len(target_band_repairs),
        "safe_fallback_candidate_count": len(accepted) - len(target_band_repairs),
        "selected_candidate_index": selected.get("candidate_index") if selected else None,
        "selected_inside_target_band": exact_stop,
        "fallback_selected": bool(fallback_reason),
        "fallback_reason": fallback_reason,
        "partial_repairs_ranked": False,
    }
    source_contract = candidate_source_contract()
    refinement_lane = target_band_refinement_lane()
    approved_rule_ids = tuple(
        str(row.get("candidate_id"))
        for row in repairs
        if row.get("merge_rule_id") == "APPROVED_COMBINED_MERGE_RULE"
    )
    source_proof = {
        "allowed_sources": tuple(source_contract.get("allowed_sources") or ()),
        "approved_merge_rules": tuple(source_contract.get("approved_merge_rules") or ()),
        "must_not_duplicate_ladders": source_contract.get("must_not_duplicate_ladders") is True,
        "target_band_refinement_lane_id": refinement_lane.get("lane_id"),
        "bending_source_candidate_count": len(inputs.bending_fail_candidates),
        "shear_source_candidate_count": len(inputs.shear_fail_candidates),
        "approved_combined_merge_candidate_count": len(inputs.approved_combined_merge_candidates),
        "merged_candidate_count": len(merged),
        "all_sources_allowed": all(candidate.sources_allowed for candidate in merged) if merged else True,
    }
    exact_proof = {
        "exact_stop": exact_stop,
        "rules": tuple(exact_stop_rules().get("allowed_when") or ()),
        "no_higher_ranked_combined_candidate": exact_stop,
        "target_band_candidate_count": len(target_band_repairs),
        "fallback_selected": bool(fallback_reason),
    }
    target_band_refinement_proof = {
        "lane_id": refinement_lane.get("lane_id"),
        "lane_allowed": refinement_lane.get("allowed") is True,
        "source_family_id": refinement_lane.get("source_family_id"),
        "must_use_only_contract_update_keys": refinement_lane.get("must_use_only_contract_update_keys") is True,
        "must_not_duplicate_source_family_ladders": refinement_lane.get("must_not_duplicate_source_family_ladders") is True,
        "approved_rule_candidate_ids": approved_rule_ids,
        "evaluated_candidate_count": len(repairs),
        "target_band_candidate_count": len(target_band_repairs),
        "safe_fallback_candidate_count": len(accepted) - len(target_band_repairs),
        "exact_stop_requires_evaluated_target_band": refinement_lane.get("exact_stop_requires_evaluated_target_band") is True,
        "exact_stop_allowed": exact_stop,
        "fallback_selected": bool(fallback_reason),
        "fallback_reason": fallback_reason,
    }
    exhausted_proof = {
        "exhausted": status == "EXHAUSTED",
        "rules": tuple(exhausted_rules().get("requires") or ()),
        "bending_candidates_attempted": bool(inputs.bending_fail_candidates),
        "shear_candidates_attempted": bool(inputs.shear_fail_candidates),
        "approved_combined_merge_candidates_attempted": True,
        "combined_merge_candidates_attempted": bool(merged),
        "specific_blocker": exhausted_reason,
    }
    ownership_proof = {
        "combined_owns_merge_and_ranking": True,
        "bending_ladder_owned_by_bending_fail_governs": True,
        "shear_ladder_owned_by_shear_fail_governs": True,
        "shared_output_apply_render_state_owned_outside_runtime": True,
    }
    selection_proof = {
        "selected_family_id": inputs.selected_family_id,
        "selection_boundary_satisfied": inputs.selection_boundary_satisfied,
        "runtime_performed_classification": False,
        "selection_boundary": selection_boundary(),
    }
    cta_proof = {
        "proof_only": True,
        "product_driving": False,
        "rendered": False,
        "applied": False,
    }
    payload = {
        "family_id": identity.get("family_id"),
        "runtime_family_id": identity.get("runtime_family_id"),
        "contract_schema": contract.get("schema"),
        "status": status,
        "selected_strategy_lane": selected_lane,
        "combined_merge_trace": tuple(trace),
        "candidate_repairs": tuple(repairs),
        "selected_recommendation": selected,
        "accepted_candidate_evidence": tuple(accepted),
        "rejected_candidate_evidence": tuple(rejected),
        "ranking_evidence": ranking,
        "exact_stop_proof": exact_proof,
        "exhausted_reason": exhausted_reason,
        "exhausted_proof": exhausted_proof,
        "candidate_source_proof": source_proof,
        "target_band_refinement_proof": target_band_refinement_proof,
        "ownership_proof": ownership_proof,
        "selection_boundary_proof": selection_proof,
        "cta_intent_proof": cta_proof,
        "contract_hash": contract_hash(),
    }
    runtime_hash = stable_combined_candidate_hash(_hash_payload(payload))
    return CombinedBendingShearFailResult(
        status=status,
        selected_strategy_lane=selected_lane,
        combined_merge_trace=tuple(trace),
        candidate_repairs=tuple(repairs),
        selected_recommendation=selected,
        accepted_candidate_evidence=tuple(accepted),
        rejected_candidate_evidence=tuple(rejected),
        ranking_evidence=ranking,
        exact_stop_proof=exact_proof,
        exhausted_reason=exhausted_reason,
        exhausted_proof=exhausted_proof,
        candidate_source_proof=source_proof,
        target_band_refinement_proof=target_band_refinement_proof,
        ownership_proof=ownership_proof,
        selection_boundary_proof=selection_proof,
        cta_intent_proof=cta_proof,
        contract_hash=contract_hash(),
        runtime_hash=runtime_hash,
    )


__all__ = [
    "CandidateEvaluator",
    "CombinedBendingShearFailResult",
    "run_combined_bending_shear_fail_runtime",
]
