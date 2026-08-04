from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from design_brain.families.shear_overdesign_governs.contract import (
    family_identity,
    internal_strategy_lanes,
    lane_proof_policies,
    load_shear_overdesign_governs_contract,
    ranking_criteria,
)
from design_brain.shear_overdesign_candidate_evaluation import (
    ShearOverdesignCandidateEvaluation,
    ShearOverdesignCandidateInput,
    ShearOverdesignCandidateUpdate,
    stable_shear_overdesign_candidate_hash,
)


CandidateEvaluator = Callable[
    [ShearOverdesignCandidateInput, ShearOverdesignCandidateUpdate],
    ShearOverdesignCandidateEvaluation,
]


@dataclass(frozen=True)
class ShearOverdesignGovernsResult:
    """Contract-ordered SHEAR_OVERDESIGN_GOVERNS optimisation runtime result."""

    status: str
    selected_strategy_lane: str | None
    ladder_trace: tuple[dict[str, Any], ...]
    candidate_repairs: tuple[dict[str, Any], ...]
    selected_recommendation: dict[str, Any] | None
    accepted_lane_evidence: tuple[dict[str, Any], ...]
    rejected_lane_evidence: tuple[dict[str, Any], ...]
    ranking_proof: dict[str, Any]
    exact_stop_proof: dict[str, Any]
    exhausted_reason: str | None
    zero_shear_override_proof: dict[str, Any]
    geometry_restriction_proof: dict[str, Any]
    repair_reason_proof: dict[str, Any]
    blocked_reason: str | None
    cta_intent_proof: dict[str, Any]
    ladder_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def shear_overdesign_contract_lane_order() -> tuple[str, ...]:
    lanes = sorted(internal_strategy_lanes(), key=lambda lane: int(lane.get("lane_index") or 0))
    return tuple(str(lane.get("lane_id") or "") for lane in lanes)


def _candidate_updates_from_contract(base_state: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    policies = lane_proof_policies()
    updates: list[dict[str, Any]] = []

    for spacing in list((policies.get("spacing_increase") or {}).get("spacing_search_mm") or []):
        updates.append({"lane_id": "SPACING_INCREASE", "updates": {"s_lig": spacing}})

    for size in list((policies.get("bar_size_reduction") or {}).get("bar_size_search") or []):
        diameter = int(str(size).replace("N", ""))
        for spacing in list((policies.get("spacing_increase") or {}).get("spacing_search_mm") or []):
            updates.append(
                {
                    "lane_id": "BAR_SIZE_REDUCTION",
                    "updates": {"lig_d": diameter, "s_lig": spacing},
                    "restart_proof": {"spacing_search_restarted": True},
                }
            )

    for legs in list((policies.get("leg_count_reduction") or {}).get("leg_count_search") or []):
        for size in list((policies.get("bar_size_reduction") or {}).get("bar_size_search") or []):
            diameter = int(str(size).replace("N", ""))
            for spacing in list((policies.get("spacing_increase") or {}).get("spacing_search_mm") or []):
                updates.append(
                    {
                        "lane_id": "LEG_COUNT_REDUCTION",
                        "updates": {"lig_legs": legs, "lig_d": diameter, "s_lig": spacing},
                        "restart_proof": {
                            "spacing_search_restarted": True,
                            "bar_size_search_restarted": True,
                        },
                    }
                )

    removal_policy = dict((policies.get("ligature_removal") or {}))
    removal_update: dict[str, Any] = {}
    if bool(base_state.get("lig_legs") or base_state.get("lig_d") or base_state.get("s_lig")):
        removal_update = dict(removal_policy.get("canonical_update") or {})
        updates.append(
            {
                "lane_id": "LIGATURE_REMOVAL",
                "updates": dict(removal_update),
                "zero_shear_override_candidate": True,
            }
        )
    width_policy = dict((policies.get("width_reduction") or {}))
    width_step = float(width_policy.get("width_step_mm") or 25.0)
    minimum_width = float(width_policy.get("minimum_width_mm") or 0.0)
    current_width = _float_from_state(base_state, ("b", "bw", "beam_width", "beam_width_mm"))
    if current_width is not None and width_step > 0:
        next_width = current_width - width_step
        while next_width >= minimum_width:
            width_updates = dict(removal_update)
            width_updates["b"] = next_width
            updates.append(
                {
                    "lane_id": "WIDTH_REDUCTION",
                    "updates": width_updates,
                    "restart_proof": {
                        "full_reinforcement_arrangement_rebuilt": True,
                        "bar_fit_rechecked": True,
                        "ligature_fit_rechecked": True,
                        "complete_design_state_recomputed": True,
                    },
                }
            )
            next_width -= width_step
    return tuple(updates)


def _is_valid_candidate(evaluation: ShearOverdesignCandidateEvaluation) -> bool:
    status = dict(evaluation.engineering_status or {})
    return (
        bool(status.get("candidate_valid", True))
        and evaluation.shear_remains_compliant is True
        and not bool((evaluation.geometry_restriction_status or {}).get("geometry_reduction_attempted"))
        and bool((evaluation.shear_detailing_update_status or {}).get("contract_update_allowed"))
        and not bool((evaluation.failure_flags or {}).get("underdesign_created"))
    )


def _float_from_state(state: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in state:
            continue
        try:
            return float(state.get(key))
        except (TypeError, ValueError):
            continue
    return None


def _reinforcement_after(candidate: dict[str, Any]) -> float:
    quantity = dict(candidate.get("reinforcement_quantity") or {})
    try:
        return float(quantity.get("after"))
    except (TypeError, ValueError):
        return 999999.0


def _cost_after(candidate: dict[str, Any]) -> float:
    cost = dict(candidate.get("cost_proxy") or {})
    try:
        return float(cost.get("after"))
    except (TypeError, ValueError):
        return 999999.0


def _width_after(candidate: dict[str, Any]) -> float:
    width = (candidate.get("width_reduction_status") or {}).get("width_after")
    if width is None:
        width = (candidate.get("updates") or {}).get("b")
    try:
        return float(width)
    except (TypeError, ValueError):
        return 999999.0


def _material_quantity_after(candidate: dict[str, Any]) -> float:
    geometry = dict(candidate.get("width_reduction_status") or {})
    try:
        return float(geometry.get("width_after"))
    except (TypeError, ValueError):
        return _width_after(candidate)


def _ranking_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    target = dict(candidate.get("target_band_status") or {})
    ligature = dict(candidate.get("ligature_removal_status") or {})
    zero = dict(candidate.get("zero_shear_status") or {})
    zero_no_ligatures = bool(zero.get("zero_or_negligible_shear")) and bool(
        ligature.get("no_unnecessary_ligatures_remain")
    )
    constructability = str((candidate.get("constructability_status") or {}).get("status") or "")
    return (
        _width_after(candidate),
        not bool(target.get("inside_target_band")),
        not zero_no_ligatures,
        not bool(ligature.get("no_unnecessary_ligatures_remain")),
        _reinforcement_after(candidate),
        _material_quantity_after(candidate),
        constructability != "PASS",
        _cost_after(candidate),
        int(candidate.get("candidate_index") or 0),
    )


def _hash_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "ladder_hash"}


def run_shear_overdesign_governs_runtime(
    *,
    base_state: dict[str, Any],
    evaluate_candidate: CandidateEvaluator,
) -> ShearOverdesignGovernsResult:
    """Run the contract-defined SHEAR_OVERDESIGN_GOVERNS optimisation ladder."""

    contract = load_shear_overdesign_governs_contract()
    identity = family_identity()
    boundary_input = ShearOverdesignCandidateInput(base_state=dict(base_state or {}))
    candidates: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []

    for index, candidate in enumerate(_candidate_updates_from_contract(dict(base_state or {})), start=1):
        lane_id = str(candidate.get("lane_id") or "")
        update = ShearOverdesignCandidateUpdate(updates=dict(candidate.get("updates") or {}))
        evaluation = evaluate_candidate(boundary_input, update)
        if not isinstance(evaluation, ShearOverdesignCandidateEvaluation):
            raise TypeError("evaluate_candidate must return ShearOverdesignCandidateEvaluation")
        if evaluation.evaluation_hash is None:
            evaluation = evaluation.with_evaluation_hash()
        valid = _is_valid_candidate(evaluation)
        row = {
            "candidate_index": index,
            "lane_id": lane_id,
            "updates": dict(update.updates),
            "update_hash": update.update_hash,
            "candidate_state_hash": evaluation.candidate_state_hash,
            "evaluation_hash": evaluation.evaluation_hash,
            "accepted": valid,
            "restart_proof": dict(candidate.get("restart_proof") or {}),
            "zero_shear_override_candidate": bool(candidate.get("zero_shear_override_candidate")),
            **{
                key: value
                for key, value in evaluation.to_dict().items()
                if key
                not in {
                    "input_hash",
                    "update_hash",
                    "candidate_state_hash",
                    "evaluation_hash",
                }
            },
        }
        candidates.append(row)
        trace.append(
            {
                "lane_id": lane_id,
                "candidate_index": index,
                "accepted": valid,
                "update_hash": update.update_hash,
                "evaluation_hash": evaluation.evaluation_hash,
            }
        )
        if valid:
            accepted.append(row)
        else:
            rejected.append(row)

    ranked = sorted(accepted, key=_ranking_key)
    selected = dict(ranked[0]) if ranked else None
    selected_lane = str(selected.get("lane_id")) if selected else None
    zero_shear_selected = bool(
        selected
        and (selected.get("zero_shear_status") or {}).get("zero_or_negligible_shear")
        and (selected.get("ligature_removal_status") or {}).get("no_unnecessary_ligatures_remain")
    )
    target_band_selected = bool(selected and (selected.get("target_band_status") or {}).get("inside_target_band"))
    exact_stop = bool(selected and (target_band_selected or zero_shear_selected))
    exhausted_reason = None if selected else "all_contract_optimisation_candidates_rejected_or_blocked"
    status = "EXACT_STOP" if exact_stop else ("SELECTED" if selected else "EXHAUSTED")
    ranking = {
        "criteria": tuple(ranking_criteria()),
        "candidate_count": len(candidates),
        "accepted_count": len(accepted),
        "selected_candidate_index": selected.get("candidate_index") if selected else None,
        "zero_shear_no_ligatures_ranks_first": zero_shear_selected,
        "smallest_safe_width_selected": (
            _width_after(selected) == min(_width_after(row) for row in accepted)
            if selected and accepted
            else False
        ),
    }
    width_candidates = [row for row in candidates if row.get("lane_id") == "WIDTH_REDUCTION"]
    accepted_width_candidates = [row for row in accepted if row.get("lane_id") == "WIDTH_REDUCTION"]
    smallest_safe_width = (
        min(_width_after(row) for row in accepted_width_candidates)
        if accepted_width_candidates
        else None
    )
    blocked_width_candidates = [row for row in width_candidates if row not in accepted_width_candidates]
    exact_stop_proof = {
        "exact_stop": exact_stop,
        "target_band_selected": target_band_selected,
        "zero_shear_no_unnecessary_ligatures_remain": zero_shear_selected,
        "width_reduction_attempted": bool(width_candidates),
        "smallest_safe_width": smallest_safe_width,
        "blocked_width_candidate_count": len(blocked_width_candidates),
        "next_width_blocker": (
            blocked_width_candidates[0].get("engineering_status")
            if blocked_width_candidates
            else None
        ),
    }
    zero_shear_proof = {
        "zero_or_negligible_shear": bool(float((base_state or {}).get("Vu") or 0.0) == 0.0),
        "ligatures_exist_before": bool(
            (base_state or {}).get("lig_legs") or (base_state or {}).get("lig_d") or (base_state or {}).get("s_lig")
        ),
        "zero_shear_candidate_seen": any(bool(row.get("zero_shear_override_candidate")) for row in candidates),
        "must_not_terminate_for_zero_utilisation": True,
    }
    geometry_proof = {
        "depth_reduction_prohibited": True,
        "width_reduction_allowed": True,
        "candidate_updates_touch_prohibited_geometry": any(
            bool((row.get("geometry_restriction_status") or {}).get("geometry_reduction_attempted"))
            for row in candidates
        ),
        "width_reduction_attempted": bool(width_candidates),
        "width_candidates_tested": tuple(
            {
                "candidate_index": row.get("candidate_index"),
                "width_after": _width_after(row),
                "accepted": bool(row.get("accepted")),
                "update_hash": row.get("update_hash"),
                "candidate_state_hash": row.get("candidate_state_hash"),
                "engineering_status": row.get("engineering_status"),
                "reinforcement_fit_status": row.get("reinforcement_fit_status"),
            }
            for row in width_candidates
        ),
        "smallest_safe_width": smallest_safe_width,
    }
    cta_proof = {
        "proof_only": True,
        "product_driving": False,
        "rendered": False,
        "applied": False,
        "selected_strategy_lane": selected_lane,
    }
    repair_reason_proof = {
        "proof_only": True,
        "selected_strategy_lane": selected_lane,
        "accepted_lane_count": len(accepted),
        "rejected_lane_count": len(rejected),
        "contract_lane_order": shear_overdesign_contract_lane_order(),
    }
    result_payload = {
        "family_id": str(identity.get("family_id") or "SHEAR_OVERDESIGN_GOVERNS"),
        "contract_schema": str(contract.get("schema") or ""),
        "contract_lane_order": shear_overdesign_contract_lane_order(),
        "status": status,
        "selected_strategy_lane": selected_lane,
        "ladder_trace": tuple(trace),
        "candidate_repairs": tuple(candidates),
        "selected_recommendation": selected,
        "accepted_lane_evidence": tuple(accepted),
        "rejected_lane_evidence": tuple(rejected),
        "ranking_proof": ranking,
        "exact_stop_proof": exact_stop_proof,
        "exhausted_reason": exhausted_reason,
        "zero_shear_override_proof": zero_shear_proof,
        "geometry_restriction_proof": geometry_proof,
        "repair_reason_proof": repair_reason_proof,
        "blocked_reason": exhausted_reason,
        "cta_intent_proof": cta_proof,
    }
    ladder_hash = stable_shear_overdesign_candidate_hash(_hash_payload(result_payload))
    return ShearOverdesignGovernsResult(
        status=status,
        selected_strategy_lane=selected_lane,
        ladder_trace=tuple(trace),
        candidate_repairs=tuple(candidates),
        selected_recommendation=selected,
        accepted_lane_evidence=tuple(accepted),
        rejected_lane_evidence=tuple(rejected),
        ranking_proof=ranking,
        exact_stop_proof=exact_stop_proof,
        exhausted_reason=exhausted_reason,
        zero_shear_override_proof=zero_shear_proof,
        geometry_restriction_proof=geometry_proof,
        repair_reason_proof=repair_reason_proof,
        blocked_reason=exhausted_reason,
        cta_intent_proof=cta_proof,
        ladder_hash=ladder_hash,
    )


__all__ = [
    "CandidateEvaluator",
    "ShearOverdesignGovernsResult",
    "run_shear_overdesign_governs_runtime",
    "shear_overdesign_contract_lane_order",
]
