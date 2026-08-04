from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from design_brain.families.serviceability_governs.contract import (
    contract_hash,
    family_identity,
    load_serviceability_governs_contract,
    ranking_criteria,
    repair_ladder,
    serviceability_contract_lane_order,
)
from design_brain.serviceability_candidate_evaluation import (
    ServiceabilityCandidateEvaluation,
    ServiceabilityCandidateInput,
    ServiceabilityCandidateUpdate,
    stable_serviceability_candidate_hash,
)
from design_brain.geometry_limits import (
    PROJECT_MAX_BEAM_DEPTH_MM,
    PROJECT_MAX_BEAM_WIDTH_MM,
    project_depth_values,
    project_width_values,
)


CandidateEvaluator = Callable[
    [ServiceabilityCandidateInput, ServiceabilityCandidateUpdate],
    ServiceabilityCandidateEvaluation,
]

NON_TERMINAL_LANES = (
    "BOTTOM_REINFORCEMENT_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "COMBINED_GEOMETRY_REINFORCEMENT_SEARCH",
)
TERMINAL_LANES = {"EXACT_STOP", "EXHAUSTED"}


@dataclass(frozen=True)
class ServiceabilityInputs:
    """Selected-family runtime input for SERVICEABILITY_GOVERNS."""

    selected_family_id: str = "SERVICEABILITY_GOVERNS"
    base_state: dict[str, Any] = field(default_factory=dict)
    geometry: dict[str, Any] = field(default_factory=dict)
    reinforcement: dict[str, Any] = field(default_factory=dict)
    material_properties: dict[str, Any] = field(default_factory=dict)
    actions: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)

    def to_base_state(self) -> dict[str, Any]:
        if self.base_state:
            return dict(self.base_state)
        return {
            "geometry": dict(self.geometry),
            "reinforcement": dict(self.reinforcement),
            "material_properties": dict(self.material_properties),
            "actions": dict(self.actions),
            "constraints": dict(self.constraints),
        }


@dataclass(frozen=True)
class ServiceabilityGovernsResult:
    """Contract-ordered SERVICEABILITY_GOVERNS runtime result."""

    status: str
    selected_strategy_lane: str | None
    selected_recommendation: dict[str, Any] | None
    candidate_repairs: tuple[dict[str, Any], ...]
    exhausted_reason: str | None
    evidence: dict[str, Any]
    ladder_trace: tuple[dict[str, Any], ...]
    accepted_lane_evidence: tuple[dict[str, Any], ...]
    rejected_lane_evidence: tuple[dict[str, Any], ...]
    ranking_evidence: dict[str, Any]
    exact_stop_proof: dict[str, Any]
    exhausted_proof: dict[str, Any]
    ownership_proof: dict[str, Any]
    ladder_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _nested_value(state: dict[str, Any], section: str, key: str, default: Any) -> Any:
    section_value = state.get(section)
    if isinstance(section_value, dict) and key in section_value:
        return section_value.get(key)
    return state.get(key, default)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _base_bottom_count(base_state: dict[str, Any]) -> int:
    return int(_number(_nested_value(base_state, "reinforcement", "bottom_bar_count", 3), 3.0))


def _base_depth(base_state: dict[str, Any]) -> float:
    return _number(_nested_value(base_state, "geometry", "beam_depth_mm", 500.0), 500.0)


def _base_width(base_state: dict[str, Any]) -> float:
    return _number(_nested_value(base_state, "geometry", "beam_width_mm", 300.0), 300.0)


def _geometry_locked(base_state: dict[str, Any]) -> bool:
    return bool(
        _nested_value(base_state, "constraints", "geometry_locked", False)
        or _nested_value(base_state, "geometry", "geometry_locked", False)
    )


def _candidate(
    *,
    lane_id: str,
    ordinal: int,
    update: dict[str, Any],
    restart_lanes: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "candidate_id": f"{lane_id}:{ordinal}",
        "lane_id": lane_id,
        "ordinal": ordinal,
        "updates": update,
        "restart_lanes": restart_lanes,
        "update_hash": ServiceabilityCandidateUpdate(updates=update).update_hash,
    }


def _candidate_updates_for_lane(
    lane_id: str,
    base_state: dict[str, Any],
    *,
    max_geometry_steps: int | None,
) -> tuple[dict[str, Any], ...]:
    candidates: list[dict[str, Any]] = []
    bottom_count = _base_bottom_count(base_state)
    depth = _base_depth(base_state)
    width = _base_width(base_state)
    geometry_locked = _geometry_locked(base_state)

    if lane_id == "BOTTOM_REINFORCEMENT_INCREASE":
        candidates.append(
            _candidate(
                lane_id=lane_id,
                ordinal=1,
                update={"reinforcement": {"bottom_bar_count": bottom_count + 1}},
            )
        )
        return tuple(candidates)

    if lane_id == "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH":
        if geometry_locked:
            return ()
        depth_values = project_depth_values(depth)
        if max_geometry_steps is not None:
            depth_values = depth_values[: max(0, int(max_geometry_steps))]
        for depth_value in depth_values:
            candidates.append(
                _candidate(
                    lane_id=lane_id,
                    ordinal=len(candidates) + 1,
                    update={
                        "geometry": {"beam_depth_mm": depth_value},
                        "reinforcement": {"bottom_bar_count": bottom_count + 1},
                    },
                    restart_lanes=("BOTTOM_REINFORCEMENT_INCREASE",),
                )
            )
        return tuple(candidates)

    if lane_id == "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH":
        if geometry_locked:
            return ()
        width_values = project_width_values(width)
        if max_geometry_steps is not None:
            width_values = width_values[: max(0, int(max_geometry_steps))]
        for width_value in width_values:
            candidates.append(
                _candidate(
                    lane_id=lane_id,
                    ordinal=len(candidates) + 1,
                    update={
                        "geometry": {"beam_width_mm": width_value},
                        "reinforcement": {"bottom_bar_count": bottom_count + 1},
                    },
                    restart_lanes=("BOTTOM_REINFORCEMENT_INCREASE",),
                )
            )
        return tuple(candidates)

    if lane_id == "COMBINED_GEOMETRY_REINFORCEMENT_SEARCH":
        if geometry_locked:
            return ()
        depth_values = project_depth_values(depth)
        width_values = project_width_values(width)
        total_steps = max(len(depth_values), len(width_values))
        if max_geometry_steps is not None:
            total_steps = min(total_steps, max(0, int(max_geometry_steps)))
        for step in range(total_steps):
            depth_value = (
                depth_values[min(step, len(depth_values) - 1)]
                if depth_values
                else depth
            )
            width_value = (
                width_values[min(step, len(width_values) - 1)]
                if width_values
                else width
            )
            candidates.append(
                _candidate(
                    lane_id=lane_id,
                    ordinal=len(candidates) + 1,
                    update={
                        "geometry": {
                            "beam_depth_mm": depth_value,
                            "beam_width_mm": width_value,
                        },
                        "reinforcement": {"bottom_bar_count": bottom_count + 1},
                    },
                )
            )
        return tuple(candidates)

    return ()


def _status_is_pass(status: dict[str, Any]) -> bool:
    return str(status.get("overall") or status.get("status") or "PASS").upper() != "FAIL"


def _is_valid_repair(evaluation: ServiceabilityCandidateEvaluation) -> tuple[bool, str]:
    flags = dict(evaluation.failure_flags or {})
    if not evaluation.serviceability_improved:
        return False, "serviceability_not_improved"
    if not evaluation.serviceability_compliant:
        return False, "serviceability_not_compliant"
    if flags.get("bending_fail"):
        return False, "bending_failure_created"
    if flags.get("shear_fail"):
        return False, "shear_failure_created"
    if not _status_is_pass(dict(evaluation.code_compliance_status or {})):
        return False, "code_compliance_failed"
    if not _status_is_pass(dict(evaluation.constructability_status or {})):
        return False, "constructability_failed"
    return True, "valid_serviceability_repair"


def _geometry_increase(update: dict[str, Any], base_state: dict[str, Any]) -> float:
    geometry = dict(update.get("geometry") or {})
    score = 0.0
    if "beam_depth_mm" in geometry:
        score += max(0.0, _number(geometry.get("beam_depth_mm")) - _base_depth(base_state))
    if "beam_width_mm" in geometry:
        score += max(0.0, _number(geometry.get("beam_width_mm")) - _base_width(base_state))
    return score


def _reinforcement_increase(update: dict[str, Any], base_state: dict[str, Any]) -> float:
    reinforcement = dict(update.get("reinforcement") or {})
    if "bottom_bar_count" not in reinforcement:
        return 0.0
    return max(0.0, _number(reinforcement.get("bottom_bar_count")) - _base_bottom_count(base_state))


def _cost_proxy(update: dict[str, Any], base_state: dict[str, Any]) -> float:
    return _geometry_increase(update, base_state) * 10.0 + _reinforcement_increase(update, base_state) * 25.0


def _candidate_record(
    *,
    candidate: dict[str, Any],
    evaluation: ServiceabilityCandidateEvaluation,
    valid: bool,
    decision_reason: str,
    base_state: dict[str, Any],
) -> dict[str, Any]:
    updates = dict(candidate.get("updates") or {})
    return {
        "candidate_id": candidate.get("candidate_id"),
        "lane_id": candidate.get("lane_id"),
        "ordinal": candidate.get("ordinal"),
        "updates": updates,
        "restart_lanes": tuple(candidate.get("restart_lanes") or ()),
        "update_hash": candidate.get("update_hash"),
        "candidate_state_hash": evaluation.candidate_state_hash,
        "evaluation_hash": evaluation.evaluation_hash,
        "serviceability_utilisation": evaluation.serviceability_utilisation,
        "serviceability_improved": evaluation.serviceability_improved,
        "serviceability_compliant": evaluation.serviceability_compliant,
        "failure_flags": dict(evaluation.failure_flags or {}),
        "blocker_status": dict(evaluation.blocker_status or {}),
        "geometry_increase": _geometry_increase(updates, base_state),
        "reinforcement_increase": _reinforcement_increase(updates, base_state),
        "cost_proxy": _cost_proxy(updates, base_state),
        "valid": valid,
        "decision_reason": decision_reason,
    }


def _ranking_key(record: dict[str, Any]) -> tuple[Any, ...]:
    constructability_fail = bool((record.get("failure_flags") or {}).get("constructability_fail"))
    return (
        0 if record.get("valid") else 1,
        _number(record.get("geometry_increase")),
        _number(record.get("reinforcement_increase")),
        1 if constructability_fail else 0,
        _number(record.get("cost_proxy")),
        str(record.get("candidate_id") or ""),
    )


def _rank_valid(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ranked = sorted(records, key=_ranking_key)
    return ranked, {
        "criteria": tuple(ranking_criteria()),
        "ranked_candidate_ids": tuple(str(record.get("candidate_id") or "") for record in ranked),
        "ranked_candidate_count": len(ranked),
        "proof_rows": tuple(
            {
                "candidate_id": record.get("candidate_id"),
                "lane_id": record.get("lane_id"),
                "ranking_key": _ranking_key(record),
                "evaluation_hash": record.get("evaluation_hash"),
            }
            for record in ranked
        ),
    }


def _current_serviceability_exact_stop(base_state: dict[str, Any]) -> bool:
    util = _nested_value(base_state, "engineering_status", "serviceability_utilisation", None)
    if util is None:
        util = _nested_value(base_state, "actions", "current_serviceability_utilisation", None)
    strength_ok = not bool(_nested_value(base_state, "failure_flags", "bending_fail", False)) and not bool(
        _nested_value(base_state, "failure_flags", "shear_fail", False)
    )
    return util is not None and _number(util, 999.0) <= 1.0 and strength_ok


def _specific_blockers(base_state: dict[str, Any], records: list[dict[str, Any]]) -> tuple[str, ...]:
    blockers: list[str] = []
    constraint_blockers = _nested_value(base_state, "constraints", "blocker_reasons", ())
    if isinstance(constraint_blockers, (list, tuple)):
        blockers.extend(str(item) for item in constraint_blockers if item)
    for record in records:
        status = dict(record.get("blocker_status") or {})
        reasons = status.get("reasons") or ()
        if isinstance(reasons, (list, tuple)):
            blockers.extend(str(item) for item in reasons if item)
    return tuple(dict.fromkeys(blockers))


def _lane_evidence(
    *,
    lane_id: str,
    lane_index: int,
    candidate_count: int,
    valid_records: list[dict[str, Any]],
    rejected_records: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "lane_index": lane_index,
        "candidate_count": candidate_count,
        "valid_candidate_ids": tuple(str(record.get("candidate_id") or "") for record in valid_records),
        "rejected_candidate_ids": tuple(str(record.get("candidate_id") or "") for record in rejected_records),
        "valid_repair_count": len(valid_records),
        "rejected_repair_count": len(rejected_records),
        "reason": reason,
    }


def _result_hash_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "ladder_hash"}


def run_serviceability_governs_ladder_runtime(
    *,
    serviceability_inputs: ServiceabilityInputs,
    evaluate_candidate: CandidateEvaluator,
    max_geometry_steps: int | None = None,
) -> ServiceabilityGovernsResult:
    """Run the contract-defined SERVICEABILITY_GOVERNS ladder."""

    if serviceability_inputs.selected_family_id != "SERVICEABILITY_GOVERNS":
        raise ValueError("SERVICEABILITY_GOVERNS runtime requires selected family identity")

    contract = load_serviceability_governs_contract()
    identity = family_identity()
    base_state = serviceability_inputs.to_base_state()
    boundary_input = ServiceabilityCandidateInput(base_state=base_state)
    lane_order = serviceability_contract_lane_order()
    restart_after = dict(repair_ladder().get("restart_after") or {})

    trace: list[dict[str, Any]] = []
    candidate_repairs: list[dict[str, Any]] = []
    accepted_lane_evidence: list[dict[str, Any]] = []
    rejected_lane_evidence: list[dict[str, Any]] = []
    selected_strategy_lane: str | None = None
    selected_recommendation: dict[str, Any] | None = None
    ranking_evidence: dict[str, Any] = {"criteria": tuple(ranking_criteria()), "ranked_candidate_ids": (), "ranked_candidate_count": 0}
    exact_stop_proof: dict[str, Any] = {"allowed": False}
    exhausted_proof: dict[str, Any] = {"allowed": False, "specific_blockers": ()}
    exhausted_reason: str | None = None

    for index, lane_id in enumerate(lane_order, start=1):
        if lane_id in NON_TERMINAL_LANES:
            candidates = _candidate_updates_for_lane(lane_id, base_state, max_geometry_steps=max_geometry_steps)
            lane_records: list[dict[str, Any]] = []
            valid_records: list[dict[str, Any]] = []
            rejected_records: list[dict[str, Any]] = []
            for candidate in candidates:
                update = ServiceabilityCandidateUpdate(updates=dict(candidate.get("updates") or {}))
                evaluation = evaluate_candidate(boundary_input, update)
                if not isinstance(evaluation, ServiceabilityCandidateEvaluation):
                    raise TypeError("evaluate_candidate must return ServiceabilityCandidateEvaluation")
                if evaluation.evaluation_hash is None:
                    evaluation = evaluation.with_evaluation_hash()
                valid, reason = _is_valid_repair(evaluation)
                record = _candidate_record(
                    candidate=candidate,
                    evaluation=evaluation,
                    valid=valid,
                    decision_reason=reason,
                    base_state=base_state,
                )
                lane_records.append(record)
                candidate_repairs.append(record)
                if valid:
                    valid_records.append(record)
                    break
                else:
                    rejected_records.append(record)
            lane_evidence = {
                **_lane_evidence(
                    lane_id=lane_id,
                    lane_index=index,
                    candidate_count=len(candidates),
                    valid_records=valid_records,
                    rejected_records=rejected_records,
                    reason="valid_repair_found" if valid_records else "no_valid_repair_in_lane",
                ),
                "restart_after": tuple(restart_after.get(lane_id) or ()),
                "restart_evidence": tuple(
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "restart_lanes": tuple(candidate.get("restart_lanes") or ()),
                    }
                    for candidate in candidates
                    if candidate.get("restart_lanes")
                ),
            }
            trace.append(lane_evidence)
            if valid_records:
                ranked, ranking_evidence = _rank_valid(valid_records)
                selected = ranked[0]
                selected_strategy_lane = lane_id
                selected_recommendation = {
                    "strategy_lane": lane_id,
                    "candidate_id": selected.get("candidate_id"),
                    "updates": dict(selected.get("updates") or {}),
                    "update_hash": selected.get("update_hash"),
                    "candidate_state_hash": selected.get("candidate_state_hash"),
                    "evaluation_hash": selected.get("evaluation_hash"),
                    "serviceability_utilisation": selected.get("serviceability_utilisation"),
                }
                accepted_lane_evidence.append(lane_evidence)
                exact_stop_proof = {
                    "allowed": True,
                    "selected_candidate_id": selected.get("candidate_id"),
                    "serviceability_compliant": True,
                    "strength_compliant": True,
                    "no_higher_ranked_repair_exists": True,
                }
                break
            rejected_lane_evidence.append(lane_evidence)
            continue

        if lane_id == "EXACT_STOP":
            allowed = _current_serviceability_exact_stop(base_state)
            exact_stop_proof = {
                "allowed": allowed,
                "source": "base_state_current_serviceability_utilisation",
                "serviceability_compliant": allowed,
                "strength_compliant": allowed,
                "no_higher_ranked_repair_exists": allowed,
            }
            lane_evidence = {
                "lane_id": lane_id,
                "lane_index": index,
                "accepted": allowed,
                "reason": "current_state_is_serviceability_compliant" if allowed else "current_state_not_exact_stop",
            }
            trace.append(lane_evidence)
            if allowed:
                selected_strategy_lane = lane_id
                accepted_lane_evidence.append(lane_evidence)
                break
            rejected_lane_evidence.append(lane_evidence)
            continue

        if lane_id == "EXHAUSTED":
            blockers = list(_specific_blockers(base_state, candidate_repairs))
            if not blockers and _geometry_locked(base_state):
                blockers.append("geometry locked")
            if max_geometry_steps is None:
                blockers.append(
                    "project maximum depth and width reached at 5000 mm"
                )
            blockers = list(dict.fromkeys(blockers))
            exhausted_reason = blockers[0] if blockers else "all_ladder_branches_attempted_no_valid_compliant_repair"
            exhausted_proof = {
                "allowed": bool(blockers),
                "all_ladder_branches_attempted": True,
                "no_valid_compliant_repair_exists": selected_recommendation is None,
                "specific_blockers": tuple(blockers),
                "project_geometry_limit_mm": {
                    "depth": PROJECT_MAX_BEAM_DEPTH_MM,
                    "width": PROJECT_MAX_BEAM_WIDTH_MM,
                },
            }
            lane_evidence = {
                "lane_id": lane_id,
                "lane_index": index,
                "accepted": True,
                "reason": exhausted_reason,
                "specific_blockers": tuple(blockers),
            }
            trace.append(lane_evidence)
            selected_strategy_lane = lane_id
            accepted_lane_evidence.append(lane_evidence)
            break

    if selected_strategy_lane is None:
        selected_strategy_lane = "EXHAUSTED"
        exhausted_reason = exhausted_reason or "contract_ladder_ended_without_selection"

    status = "REPAIRED" if selected_recommendation else ("EXACT_STOP" if selected_strategy_lane == "EXACT_STOP" else "EXHAUSTED")
    ownership_proof = {
        "family_owns_engineering_decision": True,
        "family_owns_candidate_generation": True,
        "family_owns_ranking": True,
        "family_owns_blockers": True,
        "shared_system_ownership_not_entered": True,
    }
    evidence = {
        "selection_boundary": {
            "selected_family_id": serviceability_inputs.selected_family_id,
            "runtime_performs_family_selection": False,
        },
        "serviceability_governing_proof": {
            "family_id": str(identity.get("family_id") or "SERVICEABILITY_GOVERNS"),
            "contract_hash": contract_hash(),
        },
        "ladder_trace": tuple(trace),
        "accepted_candidate_evidence": tuple(accepted_lane_evidence),
        "rejected_candidate_evidence": tuple(rejected_lane_evidence),
        "ranking_evidence": ranking_evidence,
        "exact_stop_proof": exact_stop_proof,
        "exhausted_proof": exhausted_proof,
        "ownership_proof": ownership_proof,
        "contract_version": str(contract.get("schema") or ""),
    }
    result_payload = {
        "family_id": str(identity.get("family_id") or "SERVICEABILITY_GOVERNS"),
        "contract_schema": str(contract.get("schema") or ""),
        "contract_lane_order": lane_order,
        "input_hash": boundary_input.input_hash,
        "status": status,
        "selected_strategy_lane": selected_strategy_lane,
        "selected_recommendation": selected_recommendation,
        "candidate_repairs": tuple(candidate_repairs),
        "exhausted_reason": exhausted_reason,
        "evidence": evidence,
    }
    ladder_hash = stable_serviceability_candidate_hash(_result_hash_payload(result_payload))
    return ServiceabilityGovernsResult(
        status=status,
        selected_strategy_lane=selected_strategy_lane,
        selected_recommendation=selected_recommendation,
        candidate_repairs=tuple(candidate_repairs),
        exhausted_reason=exhausted_reason,
        evidence=evidence,
        ladder_trace=tuple(trace),
        accepted_lane_evidence=tuple(accepted_lane_evidence),
        rejected_lane_evidence=tuple(rejected_lane_evidence),
        ranking_evidence=ranking_evidence,
        exact_stop_proof=exact_stop_proof,
        exhausted_proof=exhausted_proof,
        ownership_proof=ownership_proof,
        ladder_hash=ladder_hash,
    )


__all__ = [
    "CandidateEvaluator",
    "ServiceabilityGovernsResult",
    "ServiceabilityInputs",
    "run_serviceability_governs_ladder_runtime",
]
