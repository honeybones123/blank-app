from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from design_brain.candidate_evaluation import (
    BeamCandidateEvaluation,
    BeamCandidateInput,
    BeamCandidateUpdate,
    stable_candidate_evaluation_hash,
)
from design_brain.families.bending_fail_governs.contract import (
    family_identity,
    internal_strategy_lanes,
    load_bending_fail_governs_contract,
)


CONTRACT_LANE_ALIASES = {
    "geometry_sanity": "GEOMETRY_SANITY",
    "depth_increase": "DEPTH_INCREASE",
    "single_layer_bottom_reinforcement": "SINGLE_LAYER_BOTTOM_REO",
    "larger_bars": "LARGER_BAR",
    "width_increase": "WIDTH_INCREASE",
    "multi_layer_reinforcement": "MULTI_LAYER_REO",
    "exact_stop": "EXACT_STOP",
    "no_valid_strategy": "NO_VALID_STRATEGY",
}

TERMINAL_LANES = {"EXACT_STOP", "NO_VALID_STRATEGY"}
NON_TERMINAL_LANES = (
    "GEOMETRY_SANITY",
    "SINGLE_LAYER_BOTTOM_REO",
    "LARGER_BAR",
    "MULTI_LAYER_REO",
    "DEPTH_INCREASE",
    "WIDTH_INCREASE",
)

IMPLEMENTATION_CAP_ONLY_TERMS = (
    "internal search exhausted",
    "bounded move set exhausted",
    "bounded ladder exhausted",
    "candidate cap reached",
    "depth step cap reached",
    "width step cap reached",
    "maximum checked move-set depth reached",
    "maximum checked move-set width reached",
    "no generated candidates",
    "contract_ladder_exhausted_without_acceptance",
    "contract runtime ladder exhausted",
    "bounded bending repair ladder exhausted",
)


CandidateEvaluator = Callable[[BeamCandidateInput, BeamCandidateUpdate], BeamCandidateEvaluation]


@dataclass(frozen=True)
class BendingFailGovernsResult:
    """Contract-ordered BENDING_FAIL_GOVERNS ladder runtime result."""

    selected_strategy_lane: str | None
    ladder_trace: tuple[dict[str, Any], ...]
    selected_recommendation: dict[str, Any] | None
    accepted_lane_evidence: tuple[dict[str, Any], ...]
    rejected_lane_evidence: tuple[dict[str, Any], ...]
    repair_reason_proof: dict[str, Any]
    blocked_reason: str | None
    terminal_status: str | None
    repair_blocked: bool
    blocked_reason_source: str | None
    internal_cap_only: bool
    hard_blocker_proven: bool
    contract_strategy_exhaustion_proven: bool
    contract_strategies_checked: tuple[str, ...]
    contract_strategies_blocked: tuple[str, ...]
    contract_strategies_remaining: tuple[str, ...]
    implementation_caps_hit: tuple[str, ...]
    geometry_locks_used: tuple[str, ...]
    project_constraints_used: tuple[str, ...]
    detailing_constraints_used: tuple[str, ...]
    cta_intent_proof: dict[str, Any]
    ladder_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_bending_fail_governs_lane_id(lane_id: str) -> str:
    """Return the canonical public lane ID for a contract lane."""

    lane_text = str(lane_id or "")
    return CONTRACT_LANE_ALIASES.get(lane_text, lane_text.upper())


def bending_fail_governs_contract_lane_order() -> tuple[str, ...]:
    """Return the runtime lane order loaded from the family contract."""

    lanes = sorted(internal_strategy_lanes(), key=lambda lane: int(lane.get("lane_index") or 0))
    return tuple(canonical_bending_fail_governs_lane_id(str(lane.get("lane_id") or "")) for lane in lanes)


def _evaluation_decision(
    *,
    lane_id: str,
    evaluation: BeamCandidateEvaluation,
) -> tuple[bool, str]:
    status = dict(evaluation.engineering_status or {})
    lane_result = str(status.get("lane_result") or status.get("result") or "").upper()
    terminal_status = str(status.get("terminal_status") or "").upper()
    accepted_flag = bool(status.get("accepted"))

    if lane_id == "NO_VALID_STRATEGY":
        reason = str(status.get("blocked_reason") or terminal_status or lane_result or "NO_VALID_STRATEGY")
        proof = _no_valid_strategy_proof_from_status(status=status, reason=reason)
        return bool(proof["repair_blocked"]), reason
    if lane_id == "EXACT_STOP":
        accepted = terminal_status in {"EXACT_STOP", "TARGET_REACHED"} or lane_result in {
            "EXACT_STOP",
            "TARGET_REACHED",
            "ACCEPTED",
        }
        reason = str(terminal_status or lane_result or ("ACCEPTED" if accepted else "REJECTED"))
        return accepted, reason

    accepted = accepted_flag or lane_result in {"ACCEPTED", "TARGET_REACHED"}
    reason = str(lane_result or ("ACCEPTED" if accepted else "REJECTED"))
    return accepted, reason


def _tuple_from_status(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item or "").strip())
    return (str(value),)


def _status_bool(status: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = status.get(key)
        if isinstance(value, bool):
            if value:
                return True
            continue
        if str(value or "").strip().lower() in {"1", "true", "yes", "proven", "blocked"}:
            return True
    return False


def _implementation_caps_from_reason(reason: str | None) -> tuple[str, ...]:
    text = str(reason or "").strip().lower()
    return tuple(term for term in IMPLEMENTATION_CAP_ONLY_TERMS if term in text)


def _no_valid_strategy_proof_from_status(*, status: dict[str, Any], reason: str | None) -> dict[str, Any]:
    implementation_caps = tuple(
        dict.fromkeys(
            list(_tuple_from_status(status.get("implementation_caps_hit")))
            + list(_implementation_caps_from_reason(reason))
        )
    )
    internal_cap_only = bool(
        _status_bool(status, "internal_cap_only", "cap_only", "implementation_cap_only")
        or implementation_caps
    )
    hard_blocker = _status_bool(
        status,
        "hard_blocker_proven",
        "geometry_locked",
        "depth_locked_and_width_locked",
        "project_max_depth_reached",
        "project_max_width_reached",
        "detailing_constraints_prohibit_repair",
        "material_constraints_prohibit_repair",
    )
    strategy_exhaustion = _status_bool(status, "contract_strategy_exhaustion_proven")
    geometry_locks = _tuple_from_status(status.get("geometry_locks_used") or status.get("geometry_lock"))
    project_constraints = _tuple_from_status(status.get("project_constraints_used") or status.get("project_constraint"))
    detailing_constraints = _tuple_from_status(
        status.get("detailing_constraints_used") or status.get("detailing_constraint")
    )
    blocked_lanes = _tuple_from_status(status.get("contract_strategies_blocked") or status.get("blocked_strategy_lanes"))
    checked_lanes = _tuple_from_status(status.get("contract_strategies_checked") or status.get("exhausted_strategy_lanes"))
    if set(NON_TERMINAL_LANES).issubset(set(checked_lanes) | set(blocked_lanes)):
        strategy_exhaustion = True

    repair_blocked = bool((hard_blocker or strategy_exhaustion) and not internal_cap_only)
    return {
        "repair_blocked": repair_blocked,
        "internal_cap_only": internal_cap_only,
        "hard_blocker_proven": bool(hard_blocker),
        "contract_strategy_exhaustion_proven": bool(strategy_exhaustion),
        "implementation_caps_hit": implementation_caps,
        "geometry_locks_used": geometry_locks,
        "project_constraints_used": project_constraints,
        "detailing_constraints_used": detailing_constraints,
        "contract_strategies_checked": checked_lanes,
        "contract_strategies_blocked": blocked_lanes,
    }


def _lane_evidence(
    *,
    lane: dict[str, Any],
    lane_id: str,
    update: BeamCandidateUpdate,
    evaluation: BeamCandidateEvaluation,
    accepted: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "contract_lane_id": str(lane.get("lane_id") or ""),
        "lane_index": int(lane.get("lane_index") or 0),
        "title": str(lane.get("title") or ""),
        "accepted": bool(accepted),
        "reason": reason,
        "update_hash": update.update_hash,
        "candidate_state_hash": evaluation.candidate_state_hash,
        "evaluation_hash": evaluation.evaluation_hash,
        "bending_utilisation": evaluation.bending_utilisation,
        "shear_utilisation": evaluation.shear_utilisation,
        "failure_flags": dict(evaluation.failure_flags or {}),
        "engineering_status": dict(evaluation.engineering_status or {}),
    }


def _build_selected_recommendation(
    *,
    lane_id: str,
    update: BeamCandidateUpdate,
    evidence: dict[str, Any],
) -> dict[str, Any] | None:
    if lane_id in TERMINAL_LANES:
        return None
    return {
        "strategy_lane": lane_id,
        "update_hash": update.update_hash,
        "candidate_state_hash": evidence.get("candidate_state_hash"),
        "evaluation_hash": evidence.get("evaluation_hash"),
    }


def _build_repair_reason_proof(
    *,
    selected_lane: str | None,
    accepted_evidence: tuple[dict[str, Any], ...],
    rejected_evidence: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    return {
        "proof_only": True,
        "selected_strategy_lane": selected_lane,
        "accepted_lane_count": len(accepted_evidence),
        "rejected_lane_count": len(rejected_evidence),
        "accepted_lane_ids": tuple(evidence.get("lane_id") for evidence in accepted_evidence),
        "rejected_lane_ids": tuple(evidence.get("lane_id") for evidence in rejected_evidence),
    }


def _build_blocked_ownership_proof(
    *,
    selected_lane: str | None,
    blocked_reason: str | None,
    trace: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    checked: list[str] = []
    blocked: list[str] = []
    implementation_caps: list[str] = []
    geometry_locks: list[str] = []
    project_constraints: list[str] = []
    detailing_constraints: list[str] = []
    hard_blocker = False
    strategy_exhaustion = False
    internal_cap_only = False

    for row in trace:
        lane_id = str(row.get("lane_id") or "").strip()
        if lane_id in NON_TERMINAL_LANES:
            checked.append(lane_id)
        status = dict(row.get("engineering_status") or {})
        reason = str(row.get("reason") or status.get("blocked_reason") or "")
        proof = _no_valid_strategy_proof_from_status(status=status, reason=reason)
        if proof["hard_blocker_proven"]:
            hard_blocker = True
        if proof["contract_strategy_exhaustion_proven"]:
            strategy_exhaustion = True
        if proof["internal_cap_only"]:
            internal_cap_only = True
        blocked.extend(proof["contract_strategies_blocked"])
        implementation_caps.extend(proof["implementation_caps_hit"])
        geometry_locks.extend(proof["geometry_locks_used"])
        project_constraints.extend(proof["project_constraints_used"])
        detailing_constraints.extend(proof["detailing_constraints_used"])

    blocked_tuple = tuple(dict.fromkeys(blocked))
    checked_tuple = tuple(dict.fromkeys(checked))
    remaining_tuple = tuple(lane for lane in NON_TERMINAL_LANES if lane not in set(checked_tuple) | set(blocked_tuple))
    if selected_lane is None and blocked_reason is None:
        internal_cap_only = True
    repair_blocked = bool(selected_lane == "NO_VALID_STRATEGY" and (hard_blocker or strategy_exhaustion) and not internal_cap_only)
    return {
        "family_id": "BENDING_FAIL_GOVERNS",
        "terminal_status": (
            "REPAIR_BLOCKED"
            if repair_blocked
            else "DIAGNOSTIC_INCOMPLETE_NO_REPAIR_PROOF"
            if selected_lane is None
            else selected_lane
        ),
        "repair_blocked": repair_blocked,
        "blocked_reason": blocked_reason if repair_blocked else None,
        "blocked_reason_source": (
            "family_contract_blocker_proof"
            if repair_blocked
            else "diagnostic_internal_cap_only"
            if internal_cap_only
            else None
        ),
        "internal_cap_only": bool(internal_cap_only),
        "hard_blocker_proven": bool(hard_blocker),
        "contract_strategy_exhaustion_proven": bool(strategy_exhaustion),
        "contract_strategies_checked": checked_tuple,
        "contract_strategies_blocked": blocked_tuple,
        "contract_strategies_remaining": remaining_tuple,
        "implementation_caps_hit": tuple(dict.fromkeys(implementation_caps)),
        "geometry_locks_used": tuple(dict.fromkeys(geometry_locks)),
        "project_constraints_used": tuple(dict.fromkeys(project_constraints)),
        "detailing_constraints_used": tuple(dict.fromkeys(detailing_constraints)),
    }


def _build_cta_intent_proof(
    *,
    selected_lane: str | None,
    selected_recommendation: dict[str, Any] | None,
    blocked_reason: str | None,
) -> dict[str, Any]:
    return {
        "proof_only": True,
        "product_driving": False,
        "rendered": False,
        "applied": False,
        "selected_strategy_lane": selected_lane,
        "selected_update_hash": (selected_recommendation or {}).get("update_hash"),
        "blocked_reason": blocked_reason,
    }


def _result_hash_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "ladder_hash"}


def run_bending_fail_governs_ladder_runtime(
    *,
    base_state: dict[str, Any],
    evaluate_candidate: CandidateEvaluator,
    lane_candidate_updates: dict[str, dict[str, Any]] | None = None,
) -> BendingFailGovernsResult:
    """Run the contract-defined BENDING_FAIL_GOVERNS strategy ladder.

    The evaluator is injected so this family runtime can use the Candidate
    Evaluation API shape without importing page/runtime evaluation code.
    """

    contract = load_bending_fail_governs_contract()
    identity = family_identity()
    boundary_input = BeamCandidateInput(base_state=dict(base_state or {}))
    update_map = dict(lane_candidate_updates or {})
    trace: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    selected_lane: str | None = None
    selected_recommendation: dict[str, Any] | None = None
    blocked_reason: str | None = None

    for lane in sorted(internal_strategy_lanes(), key=lambda item: int(item.get("lane_index") or 0)):
        lane_id = canonical_bending_fail_governs_lane_id(str(lane.get("lane_id") or ""))
        update_payload = dict(update_map.get(lane_id) or update_map.get(str(lane.get("lane_id") or "")) or {})
        update = BeamCandidateUpdate(updates=update_payload)
        evaluation = evaluate_candidate(boundary_input, update)
        if not isinstance(evaluation, BeamCandidateEvaluation):
            raise TypeError("evaluate_candidate must return BeamCandidateEvaluation")
        if evaluation.evaluation_hash is None:
            evaluation = evaluation.with_evaluation_hash()

        accepted_lane, reason = _evaluation_decision(lane_id=lane_id, evaluation=evaluation)
        evidence = _lane_evidence(
            lane=lane,
            lane_id=lane_id,
            update=update,
            evaluation=evaluation,
            accepted=accepted_lane,
            reason=reason,
        )
        trace.append(evidence)
        if accepted_lane:
            accepted.append(evidence)
            selected_lane = lane_id
            selected_recommendation = _build_selected_recommendation(
                lane_id=lane_id,
                update=update,
                evidence=evidence,
            )
            if lane_id == "NO_VALID_STRATEGY":
                blocked_reason = reason
            break
        rejected.append(evidence)

    accepted_tuple = tuple(accepted)
    rejected_tuple = tuple(rejected)
    trace_tuple = tuple(trace)
    blocked_ownership_proof = _build_blocked_ownership_proof(
        selected_lane=selected_lane,
        blocked_reason=blocked_reason,
        trace=trace_tuple,
    )
    repair_reason_proof = _build_repair_reason_proof(
        selected_lane=selected_lane,
        accepted_evidence=accepted_tuple,
        rejected_evidence=rejected_tuple,
    )
    repair_reason_proof.update(
        {
            "blocked_ownership_proof": dict(blocked_ownership_proof),
            "internal_cap_only": bool(blocked_ownership_proof["internal_cap_only"]),
            "repair_blocked": bool(blocked_ownership_proof["repair_blocked"]),
            "hard_blocker_proven": bool(blocked_ownership_proof["hard_blocker_proven"]),
            "contract_strategy_exhaustion_proven": bool(
                blocked_ownership_proof["contract_strategy_exhaustion_proven"]
            ),
        }
    )
    cta_intent_proof = _build_cta_intent_proof(
        selected_lane=selected_lane,
        selected_recommendation=selected_recommendation,
        blocked_reason=blocked_reason if bool(blocked_ownership_proof["repair_blocked"]) else None,
    )

    result_payload = {
        "family_id": str(identity.get("family_id") or "BENDING_FAIL_GOVERNS"),
        "contract_schema": str(contract.get("schema") or ""),
        "contract_lane_order": bending_fail_governs_contract_lane_order(),
        "input_hash": boundary_input.state_hash,
        "selected_strategy_lane": selected_lane,
        "ladder_trace": trace_tuple,
        "selected_recommendation": selected_recommendation,
        "accepted_lane_evidence": accepted_tuple,
        "rejected_lane_evidence": rejected_tuple,
        "repair_reason_proof": repair_reason_proof,
        "blocked_reason": blocked_reason if bool(blocked_ownership_proof["repair_blocked"]) else None,
        **blocked_ownership_proof,
        "cta_intent_proof": cta_intent_proof,
    }
    ladder_hash = stable_candidate_evaluation_hash(_result_hash_payload(result_payload))
    return BendingFailGovernsResult(
        selected_strategy_lane=selected_lane,
        ladder_trace=trace_tuple,
        selected_recommendation=selected_recommendation,
        accepted_lane_evidence=accepted_tuple,
        rejected_lane_evidence=rejected_tuple,
        repair_reason_proof=repair_reason_proof,
        blocked_reason=blocked_reason if bool(blocked_ownership_proof["repair_blocked"]) else None,
        terminal_status=str(blocked_ownership_proof["terminal_status"] or ""),
        repair_blocked=bool(blocked_ownership_proof["repair_blocked"]),
        blocked_reason_source=blocked_ownership_proof["blocked_reason_source"],
        internal_cap_only=bool(blocked_ownership_proof["internal_cap_only"]),
        hard_blocker_proven=bool(blocked_ownership_proof["hard_blocker_proven"]),
        contract_strategy_exhaustion_proven=bool(blocked_ownership_proof["contract_strategy_exhaustion_proven"]),
        contract_strategies_checked=tuple(blocked_ownership_proof["contract_strategies_checked"]),
        contract_strategies_blocked=tuple(blocked_ownership_proof["contract_strategies_blocked"]),
        contract_strategies_remaining=tuple(blocked_ownership_proof["contract_strategies_remaining"]),
        implementation_caps_hit=tuple(blocked_ownership_proof["implementation_caps_hit"]),
        geometry_locks_used=tuple(blocked_ownership_proof["geometry_locks_used"]),
        project_constraints_used=tuple(blocked_ownership_proof["project_constraints_used"]),
        detailing_constraints_used=tuple(blocked_ownership_proof["detailing_constraints_used"]),
        cta_intent_proof=cta_intent_proof,
        ladder_hash=ladder_hash,
    )


__all__ = [
    "BendingFailGovernsResult",
    "CandidateEvaluator",
    "bending_fail_governs_contract_lane_order",
    "canonical_bending_fail_governs_lane_id",
    "run_bending_fail_governs_ladder_runtime",
]
