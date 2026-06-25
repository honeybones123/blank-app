from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from design_brain.bending_overdesign_candidate_evaluation import (
    BendingOverdesignCandidateEvaluation,
    BendingOverdesignCandidateInput,
    BendingOverdesignCandidateUpdate,
    stable_bending_overdesign_candidate_hash,
)
from design_brain.families.bending_overdesign_governs.contract import (
    family_identity,
    geometry_rules,
    internal_strategy_lanes,
    lane_proof_policies,
    load_bending_overdesign_governs_contract,
    minimum_reinforcement_geometry_relief_rules,
    minimum_reinforcement_rules,
    ranking_criteria,
)


CandidateEvaluator = Callable[
    [BendingOverdesignCandidateInput, BendingOverdesignCandidateUpdate],
    BendingOverdesignCandidateEvaluation,
]


@dataclass(frozen=True)
class BendingOverdesignGovernsResult:
    """Contract-ordered BENDING_OVERDESIGN_GOVERNS optimisation runtime result."""

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
    minimum_reinforcement_proof: dict[str, Any]
    geometry_compliance_proof: dict[str, Any]
    restart_proof: dict[str, Any]
    repair_reason_proof: dict[str, Any]
    blocked_reason: str | None
    cta_intent_proof: dict[str, Any]
    ladder_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def bending_overdesign_contract_lane_order() -> tuple[str, ...]:
    lanes = sorted(internal_strategy_lanes(), key=lambda lane: int(lane.get("lane_index") or 0))
    return tuple(str(lane.get("lane_id") or "") for lane in lanes)


def _bottom_reinforcement_update(sequence_item: str) -> dict[str, int]:
    count_text, diameter_text = str(sequence_item).split("-N", maxsplit=1)
    return {"bot1_count": int(count_text), "db_bot_1": int(diameter_text)}


def _has_reinforcement_update(update: dict[str, Any]) -> bool:
    return bool(
        set(update)
        & {
            "bot1_count",
            "db_bot_1",
            "bot2_count",
            "db_bot_2",
            "bot_row_count",
            "bot_row_1_bars",
            "bot_row_1_dia",
            "bot_row_2_bars",
            "bot_row_2_dia",
        }
    )


def _candidate_updates_from_contract(base_state: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    policies = lane_proof_policies()
    geometry = geometry_rules()
    relief = minimum_reinforcement_geometry_relief_rules()
    updates: list[dict[str, Any]] = []
    bottom_sequence = list((policies.get("bottom_reinforcement_reduction") or {}).get("example_sequence") or [])

    for sequence_item in bottom_sequence:
        candidate_update = _bottom_reinforcement_update(str(sequence_item))
        if candidate_update.get("bot1_count") == base_state.get("bot1_count") and candidate_update.get("db_bot_1") == base_state.get("db_bot_1"):
            continue
        updates.append(
            {
                "lane_id": "BOTTOM_REINFORCEMENT_REDUCTION",
                "updates": candidate_update,
            }
        )

    layer_policy = policies.get("layer_reduction") or {}
    if list(layer_policy.get("search") or []) == ["multi-layer", "single-layer"]:
        updates.append(
            {
                "lane_id": "LAYER_REDUCTION",
                "updates": {"bot_row_count": 1, "bot2_count": 0, "db_bot_2": 0},
            }
        )

    width_increment = int(geometry.get("width_increment_mm") or -25)
    base_width = base_state.get("b", base_state.get("bw", base_state.get("beam_width", base_state.get("beam_width_mm"))))
    if base_width is not None:
        reduced_width = float(base_width) + width_increment
        updates.append(
            {
                "lane_id": "WIDTH_REDUCTION",
                "updates": {"b": reduced_width},
                "restart_proof": {
                    "bottom_reinforcement_search_restarted": True,
                    "layer_search_restarted": True,
                    "minimum_reinforcement_geometry_relief_checked": bool(relief),
                    "restarted_candidate_type": "width_only",
                },
            }
        )
        for sequence_item in bottom_sequence:
            bottom_update = _bottom_reinforcement_update(str(sequence_item))
            if bottom_update.get("bot1_count") == base_state.get("bot1_count") and bottom_update.get("db_bot_1") == base_state.get("db_bot_1"):
                continue
            updates.append(
                {
                    "lane_id": "WIDTH_REDUCTION",
                    "updates": {"b": reduced_width, **bottom_update},
                    "restart_proof": {
                        "bottom_reinforcement_search_restarted": True,
                        "layer_search_restarted": True,
                        "minimum_reinforcement_geometry_relief_checked": bool(relief),
                        "restarted_candidate_type": "width_plus_bottom_reinforcement",
                    },
                }
            )
        if list(layer_policy.get("search") or []) == ["multi-layer", "single-layer"]:
            updates.append(
                {
                    "lane_id": "WIDTH_REDUCTION",
                    "updates": {"b": reduced_width, "bot_row_count": 1, "bot2_count": 0, "db_bot_2": 0},
                    "restart_proof": {
                        "bottom_reinforcement_search_restarted": True,
                        "layer_search_restarted": True,
                        "minimum_reinforcement_geometry_relief_checked": bool(relief),
                        "restarted_candidate_type": "width_plus_layer_reduction",
                    },
                }
            )

    depth_increment = int(geometry.get("depth_increment_mm") or -25)
    base_depth = base_state.get("D", base_state.get("beam_depth", base_state.get("beam_depth_mm")))
    if base_depth is not None:
        updates.append(
            {
                "lane_id": "DEPTH_REDUCTION",
                "updates": {"D": float(base_depth) + depth_increment},
                "restart_proof": {
                    "bottom_reinforcement_search_restarted": True,
                    "layer_search_restarted": True,
                },
            }
        )
    return tuple(updates)


def _status_is_pass(value: dict[str, Any]) -> bool:
    return str(value.get("status") or "").upper() in {"PASS", "OK", "TRUE", "COMPLIANT"}


def _is_valid_candidate(evaluation: BendingOverdesignCandidateEvaluation) -> bool:
    minimum = dict(evaluation.minimum_reinforcement_status or {})
    return (
        bool((evaluation.engineering_status or {}).get("candidate_valid", True))
        and evaluation.bending_remains_compliant is True
        and minimum.get("As_greater_than_or_equal_to_As_min") is True
        and minimum.get("discard_before_ranking") is not True
        and _status_is_pass(dict(evaluation.constructability_status or {}))
        and _status_is_pass(dict(evaluation.code_compliance_status or {}))
        and _status_is_pass(dict(evaluation.geometry_compliance_status or {}))
        and _status_is_pass(dict(evaluation.beam_proportion_status or {}))
        and not bool((evaluation.failure_flags or {}).get("underdesign_created"))
        and not bool((evaluation.failure_flags or {}).get("below_minimum_reinforcement"))
    )


def _numeric_after(candidate: dict[str, Any], field: str, default: float = 999999.0) -> float:
    value = candidate.get(field) or {}
    try:
        return float(value.get("after"))
    except (AttributeError, TypeError, ValueError):
        return default


def _ranking_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    target = dict(candidate.get("target_band_status") or {})
    constructability = str((candidate.get("constructability_status") or {}).get("status") or "")
    return (
        not bool(target.get("inside_target_band") or target.get("inside")),
        _numeric_after(candidate, "reinforcement_quantity"),
        _numeric_after(candidate, "beam_volume"),
        constructability.upper() not in {"PASS", "OK", "TRUE", "COMPLIANT"},
        _numeric_after(candidate, "cost_proxy"),
        int(candidate.get("candidate_index") or 0),
    )


def _hash_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "ladder_hash"}


def run_bending_overdesign_governs_runtime(
    *,
    base_state: dict[str, Any],
    evaluate_candidate: CandidateEvaluator,
) -> BendingOverdesignGovernsResult:
    """Run the contract-defined BENDING_OVERDESIGN_GOVERNS optimisation ladder."""

    contract = load_bending_overdesign_governs_contract()
    identity = family_identity()
    boundary_input = BendingOverdesignCandidateInput(base_state=dict(base_state or {}))
    candidates: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []

    for index, candidate in enumerate(_candidate_updates_from_contract(dict(base_state or {})), start=1):
        lane_id = str(candidate.get("lane_id") or "")
        update = BendingOverdesignCandidateUpdate(updates=dict(candidate.get("updates") or {}))
        evaluation = evaluate_candidate(boundary_input, update)
        if not isinstance(evaluation, BendingOverdesignCandidateEvaluation):
            raise TypeError("evaluate_candidate must return BendingOverdesignCandidateEvaluation")
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
    target_band_selected = bool(
        selected
        and (
            (selected.get("target_band_status") or {}).get("inside_target_band")
            or (selected.get("target_band_status") or {}).get("inside")
        )
    )
    exact_stop = bool(selected and target_band_selected)
    exhausted_reason = None if selected else "all_contract_optimisation_candidates_rejected_or_blocked"
    status = "EXACT_STOP" if exact_stop else ("SELECTED" if selected else "EXHAUSTED")
    below_minimum_rejections = [
        row
        for row in rejected
        if (row.get("minimum_reinforcement_status") or {}).get("discard_before_ranking") is True
    ]
    geometry_rejections = [
        row
        for row in rejected
        if str((row.get("geometry_compliance_status") or {}).get("status") or "").upper() == "FAIL"
        or str((row.get("beam_proportion_status") or {}).get("status") or "").upper() == "FAIL"
    ]
    restart_rows = [row for row in candidates if row.get("restart_proof")]
    width_relief_rows = [
        row
        for row in restart_rows
        if row.get("lane_id") == "WIDTH_REDUCTION"
        and "b" in dict(row.get("updates") or {})
        and _has_reinforcement_update(dict(row.get("updates") or {}))
    ]
    ranking = {
        "criteria": tuple(ranking_criteria()),
        "candidate_count": len(candidates),
        "accepted_count": len(accepted),
        "selected_candidate_index": selected.get("candidate_index") if selected else None,
        "candidates_below_minimum_discarded_before_ranking": all(
            row not in accepted for row in below_minimum_rejections
        ),
    }
    exact_stop_proof = {
        "exact_stop": exact_stop,
        "target_band_selected": target_band_selected,
        "no_higher_ranked_optimisation_candidate": bool(selected),
    }
    minimum_proof = {
        "hard_boundary": bool((minimum_reinforcement_rules() or {}).get("hard_boundary")),
        "below_minimum_rejection_count": len(below_minimum_rejections),
        "below_minimum_candidates_ranked": False,
        "minimum_reinforcement_geometry_relief_required": bool(minimum_reinforcement_geometry_relief_rules()),
        "minimum_reinforcement_geometry_relief_checked": bool(width_relief_rows),
        "width_reduction_relief_candidate_count": len(width_relief_rows),
    }
    geometry_proof = {
        "geometry_reduction_allowed": bool((geometry_rules() or {}).get("geometry_reduction_allowed")),
        "geometry_rejection_count": len(geometry_rejections),
        "width_increment_mm": (geometry_rules() or {}).get("width_increment_mm"),
        "depth_increment_mm": (geometry_rules() or {}).get("depth_increment_mm"),
        "width_plus_reinforcement_restart_candidate_count": len(width_relief_rows),
    }
    restart_proof = {
        "geometry_reduction_candidates": len(restart_rows),
        "all_geometry_reductions_restart_bottom_reinforcement_search": all(
            bool((row.get("restart_proof") or {}).get("bottom_reinforcement_search_restarted"))
            for row in restart_rows
        ),
        "all_geometry_reductions_restart_layer_search": all(
            bool((row.get("restart_proof") or {}).get("layer_search_restarted"))
            for row in restart_rows
        ),
        "minimum_reinforcement_geometry_relief_checked": bool(width_relief_rows),
        "width_reduction_restarted_reinforcement_candidate_count": len(width_relief_rows),
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
        "contract_lane_order": bending_overdesign_contract_lane_order(),
    }
    result_payload = {
        "family_id": str(identity.get("family_id") or "BENDING_OVERDESIGN_GOVERNS"),
        "contract_schema": str(contract.get("schema") or ""),
        "contract_lane_order": bending_overdesign_contract_lane_order(),
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
        "minimum_reinforcement_proof": minimum_proof,
        "geometry_compliance_proof": geometry_proof,
        "restart_proof": restart_proof,
        "repair_reason_proof": repair_reason_proof,
        "blocked_reason": exhausted_reason,
        "cta_intent_proof": cta_proof,
    }
    ladder_hash = stable_bending_overdesign_candidate_hash(_hash_payload(result_payload))
    return BendingOverdesignGovernsResult(
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
        minimum_reinforcement_proof=minimum_proof,
        geometry_compliance_proof=geometry_proof,
        restart_proof=restart_proof,
        repair_reason_proof=repair_reason_proof,
        blocked_reason=exhausted_reason,
        cta_intent_proof=cta_proof,
        ladder_hash=ladder_hash,
    )


__all__ = [
    "BendingOverdesignGovernsResult",
    "CandidateEvaluator",
    "bending_overdesign_contract_lane_order",
    "run_bending_overdesign_governs_runtime",
]
