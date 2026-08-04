from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from design_brain.families.shear_fail_governs.contract import (
    family_identity,
    internal_strategy_lanes,
    load_shear_fail_governs_contract,
    ranking_criteria,
)
from design_brain.geometry_limits import (
    PROJECT_MAX_BEAM_DEPTH_MM,
    PROJECT_MAX_BEAM_WIDTH_MM,
    incremental_geometry_values,
)
from design_brain.shear_candidate_evaluation import (
    ShearCandidateEvaluation,
    ShearCandidateInput,
    ShearCandidateUpdate,
    stable_shear_candidate_hash,
)


CandidateEvaluator = Callable[[ShearCandidateInput, ShearCandidateUpdate], ShearCandidateEvaluation]

TARGET_BAND_LOWER = 0.85
TARGET_BAND_UPPER = 1.0
NON_TERMINAL_LANES = {
    "SPACING_REDUCTION",
    "BAR_SIZE_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH",
}
NON_TERMINAL_LANE_ORDER = (
    "SPACING_REDUCTION",
    "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "BAR_SIZE_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
)


@dataclass(frozen=True)
class ShearFailGovernsResult:
    """Contract-ordered SHEAR_FAIL_GOVERNS ladder runtime result."""

    selected_strategy_lane: str | None
    ladder_trace: tuple[dict[str, Any], ...]
    candidate_repairs: tuple[dict[str, Any], ...]
    selected_recommendation: dict[str, Any] | None
    accepted_lane_evidence: tuple[dict[str, Any], ...]
    rejected_lane_evidence: tuple[dict[str, Any], ...]
    ranking_proof: dict[str, Any]
    exact_stop_proof: dict[str, Any]
    exhausted_reason: str | None
    no_valid_repair_proof: dict[str, Any]
    repair_reason_proof: dict[str, Any]
    blocked_reason: str | None
    cta_intent_proof: dict[str, Any]
    ladder_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def shear_fail_governs_contract_lane_order() -> tuple[str, ...]:
    """Return the runtime lane order loaded from the family contract."""

    lanes = sorted(internal_strategy_lanes(), key=lambda lane: int(lane.get("lane_index") or 0))
    return tuple(str(lane.get("lane_id") or "") for lane in lanes)


def _nested_value(state: dict[str, Any], section: str, key: str, default: Any) -> Any:
    section_value = state.get(section)
    if isinstance(section_value, dict) and key in section_value:
        return section_value.get(key)
    return state.get(key, default)


def _lane_by_id() -> dict[str, dict[str, Any]]:
    return {str(lane.get("lane_id") or ""): dict(lane) for lane in internal_strategy_lanes()}


def _spacing_values(policy: dict[str, Any]) -> list[int]:
    return [int(value) for value in policy.get("spacing_values_mm") or ()]


def _bar_sizes(policy: dict[str, Any]) -> list[tuple[str, int]]:
    labels = [str(value) for value in policy.get("bar_size_labels") or ()]
    diameters = [int(value) for value in policy.get("bar_diameters_mm") or ()]
    return list(zip(labels, diameters, strict=False))


def _base_spacing_values(lane_map: dict[str, dict[str, Any]]) -> list[int]:
    return _spacing_values(dict((lane_map.get("SPACING_REDUCTION") or {}).get("search_policy") or {}))


def _base_bar_sizes(lane_map: dict[str, dict[str, Any]]) -> list[tuple[str, int]]:
    return _bar_sizes(dict((lane_map.get("BAR_SIZE_INCREASE") or {}).get("search_policy") or {}))


def _base_leg_counts(lane_map: dict[str, dict[str, Any]]) -> list[int]:
    policy = dict(
        (lane_map.get("LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH") or {}).get(
            "search_policy"
        )
        or {}
    )
    return [int(value) for value in policy.get("leg_counts") or ()]


def _current_reinforcement(base_state: dict[str, Any]) -> tuple[int, int, int]:
    spacing = int(
        float(
            _nested_value(
                base_state,
                "reinforcement",
                "ligature_spacing_mm",
                300,
            )
            or 300
        )
    )
    diameter = int(
        float(
            _nested_value(
                base_state,
                "reinforcement",
                "ligature_diameter_mm",
                10,
            )
            or 10
        )
    )
    legs = int(
        float(
            _nested_value(
                base_state,
                "reinforcement",
                "ligature_leg_count",
                2,
            )
            or 2
        )
    )
    return spacing, diameter, legs


def _diameter_label(diameter: int) -> str:
    return f"N{int(diameter)}"


def _legal_leg_counts(
    lane_map: dict[str, dict[str, Any]],
    *,
    current_legs: int,
) -> list[int]:
    return sorted(
        {
            int(current_legs),
            *[
                int(value)
                for value in _base_leg_counts(lane_map)
                if int(value) > int(current_legs)
            ],
        }
    )


def _reinforcement_restart_updates(
    *,
    base_state: dict[str, Any],
    lane_map: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Restart spacing, legs, then diameter without discarding earlier phases."""

    _, current_diameter, current_legs = _current_reinforcement(base_state)
    spacing_values = _base_spacing_values(lane_map)
    leg_counts = _legal_leg_counts(lane_map, current_legs=current_legs)
    diameter_options = [
        (_diameter_label(current_diameter), current_diameter),
        *[
            (label, diameter)
            for label, diameter in _base_bar_sizes(lane_map)
            if int(diameter) > int(current_diameter)
        ],
    ]
    updates: list[dict[str, Any]] = []
    for label, diameter in diameter_options:
        for leg_count in leg_counts:
            for spacing in spacing_values:
                updates.append(
                    {
                        "ligature_diameter_label": label,
                        "ligature_diameter_mm": int(diameter),
                        "ligature_leg_count": int(leg_count),
                        "ligature_spacing_mm": int(spacing),
                    }
                )
    return tuple(updates)


def _representative_reinforcement_restart_updates(
    updates: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    """Keep weak, middle, and strong restart levels for long geometry tails."""

    if len(updates) <= 3:
        return updates

    def _strength(row: dict[str, Any]) -> float:
        diameter = float(row.get("ligature_diameter_mm") or 0.0)
        legs = float(row.get("ligature_leg_count") or 0.0)
        spacing = float(row.get("ligature_spacing_mm") or 1.0)
        return legs * diameter * diameter / max(spacing, 1.0)

    ordered = sorted(
        updates,
        key=lambda row: (
            _strength(row),
            float(row.get("ligature_diameter_mm") or 0.0),
            float(row.get("ligature_leg_count") or 0.0),
            -float(row.get("ligature_spacing_mm") or 0.0),
        ),
    )
    indexes = (0, len(ordered) // 2, len(ordered) - 1)
    return tuple(ordered[index] for index in dict.fromkeys(indexes))


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
        "update": update,
        "restart_lanes": restart_lanes,
        "update_hash": ShearCandidateUpdate(updates=update).update_hash,
    }


def _candidate_updates_for_lane(
    *,
    lane_id: str,
    lane: dict[str, Any],
    base_state: dict[str, Any],
    lane_map: dict[str, dict[str, Any]],
    max_depth_steps: int,
    max_width_steps: int,
) -> tuple[dict[str, Any], ...]:
    policy = dict(lane.get("search_policy") or {})
    candidates: list[dict[str, Any]] = []
    current_spacing, current_diameter, current_legs = _current_reinforcement(base_state)

    if lane_id == "SPACING_REDUCTION":
        for spacing in _spacing_values(policy):
            if int(spacing) >= int(current_spacing):
                continue
            candidates.append(
                _candidate(
                    lane_id=lane_id,
                    ordinal=len(candidates) + 1,
                    update={"reinforcement": {"ligature_spacing_mm": spacing}},
                )
            )
        return tuple(candidates)

    if lane_id == "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH":
        restart = tuple(str(value) for value in policy.get("restart_after_each_leg_count_change") or ())
        for leg_count in [int(value) for value in policy.get("leg_counts") or ()]:
            if int(leg_count) <= int(current_legs):
                continue
            for spacing in [int(value) for value in policy.get("restart_spacing_values_mm") or ()]:
                candidates.append(
                    _candidate(
                        lane_id=lane_id,
                        ordinal=len(candidates) + 1,
                        update={
                            "reinforcement": {
                                "ligature_leg_count": int(leg_count),
                                "ligature_diameter_label": _diameter_label(current_diameter),
                                "ligature_diameter_mm": int(current_diameter),
                                "ligature_spacing_mm": int(spacing),
                            }
                        },
                        restart_lanes=restart,
                    )
                )
        return tuple(candidates)

    if lane_id == "BAR_SIZE_INCREASE":
        restart = tuple(str(value) for value in policy.get("restart_after_each_size") or ())
        for label, diameter in _bar_sizes(policy):
            if int(diameter) <= int(current_diameter):
                continue
            for leg_count in _legal_leg_counts(lane_map, current_legs=current_legs):
                for spacing in [int(value) for value in policy.get("restart_spacing_values_mm") or ()]:
                    candidates.append(
                        _candidate(
                            lane_id=lane_id,
                            ordinal=len(candidates) + 1,
                            update={
                                "reinforcement": {
                                    "ligature_diameter_label": label,
                                    "ligature_diameter_mm": int(diameter),
                                    "ligature_leg_count": int(leg_count),
                                    "ligature_spacing_mm": int(spacing),
                                }
                            },
                            restart_lanes=restart,
                        )
                    )
        return tuple(candidates)

    if lane_id == "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH":
        restart = tuple(str(value) for value in policy.get("restart_after_each_depth_change") or ())
        increment = float(policy.get("increment_mm") or 0.0)
        base_depth = float(_nested_value(base_state, "geometry", "beam_depth_mm", 0.0) or 0.0)
        legal_depths = incremental_geometry_values(
            base_depth,
            maximum_mm=PROJECT_MAX_BEAM_DEPTH_MM,
            increment_mm=increment,
        )[: max(0, int(max_depth_steps))]
        restart_updates = _reinforcement_restart_updates(
            base_state=base_state,
            lane_map=lane_map,
        )
        representative_updates = _representative_reinforcement_restart_updates(
            restart_updates
        )
        full_restart_steps = max(int(policy.get("max_increment_steps") or 0), 0)
        for step, depth in enumerate(legal_depths, start=1):
            active_updates = (
                restart_updates
                if step <= full_restart_steps
                else representative_updates
            )
            for reinforcement in active_updates:
                candidates.append(
                    _candidate(
                        lane_id=lane_id,
                        ordinal=len(candidates) + 1,
                        update={
                            "geometry": {"beam_depth_mm": depth},
                            "reinforcement": dict(reinforcement),
                        },
                        restart_lanes=restart,
                    )
                )
        return tuple(candidates)

    if lane_id == "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH":
        restart = tuple(str(value) for value in policy.get("restart_after_each_width_change") or ())
        increment = float(policy.get("increment_mm") or 0.0)
        base_width = float(_nested_value(base_state, "geometry", "beam_width_mm", 0.0) or 0.0)
        legal_widths = incremental_geometry_values(
            base_width,
            maximum_mm=PROJECT_MAX_BEAM_WIDTH_MM,
            increment_mm=increment,
        )[: max(0, int(max_width_steps))]
        restart_updates = _reinforcement_restart_updates(
            base_state=base_state,
            lane_map=lane_map,
        )
        representative_updates = _representative_reinforcement_restart_updates(
            restart_updates
        )
        full_restart_steps = max(int(policy.get("max_increment_steps") or 0), 0)
        for step, width in enumerate(legal_widths, start=1):
            active_updates = (
                restart_updates
                if step <= full_restart_steps
                else representative_updates
            )
            for reinforcement in active_updates:
                candidates.append(
                    _candidate(
                        lane_id=lane_id,
                        ordinal=len(candidates) + 1,
                        update={
                            "geometry": {"beam_width_mm": width},
                            "reinforcement": dict(reinforcement),
                        },
                        restart_lanes=restart,
                    )
                )
        return tuple(candidates)

    return ()


def _candidate_repair_record(
    *,
    candidate: dict[str, Any],
    boundary_input: ShearCandidateInput,
    evaluation: ShearCandidateEvaluation,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate.get("candidate_id"),
        "lane_id": candidate.get("lane_id"),
        "ordinal": candidate.get("ordinal"),
        "updates": dict(candidate.get("update") or {}),
        "restart_lanes": tuple(candidate.get("restart_lanes") or ()),
        "input_hash": boundary_input.input_hash,
        "update_hash": candidate.get("update_hash"),
        "candidate_state_hash": evaluation.candidate_state_hash,
        "evaluation_hash": evaluation.evaluation_hash,
        "shear_utilisation": evaluation.shear_utilisation,
        "previous_shear_utilisation": evaluation.previous_shear_utilisation,
        "utilisation_improved": evaluation.utilisation_improved,
        "engineering_status": dict(evaluation.engineering_status or {}),
        "code_compliance_status": dict(evaluation.code_compliance_status or {}),
        "constructability_status": dict(evaluation.constructability_status or {}),
        "failure_flags": dict(evaluation.failure_flags or {}),
    }


def _target_band_status(utilisation: float | None) -> str:
    if utilisation is None:
        return "UNKNOWN"
    if TARGET_BAND_LOWER <= float(utilisation) <= TARGET_BAND_UPPER:
        return "TARGET"
    if float(utilisation) > TARGET_BAND_UPPER:
        return "FAIL"
    return "BELOW_TARGET"


def _is_valid_repair(record: dict[str, Any]) -> bool:
    util = record.get("shear_utilisation")
    if _target_band_status(util) != "TARGET":
        return False
    status = dict(record.get("engineering_status") or {})
    code = dict(record.get("code_compliance_status") or {})
    constructability = dict(record.get("constructability_status") or {})
    flags = dict(record.get("failure_flags") or {})
    if flags.get("shear_fail") is True:
        return False
    return (
        str(status.get("overall") or "PASS").upper() != "FAIL"
        and str(code.get("overall") or "PASS").upper() != "FAIL"
        and str(constructability.get("overall") or "PASS").upper() != "FAIL"
    )


def _geometry_change_score(update: dict[str, Any]) -> float:
    geometry = dict(update.get("geometry") or {})
    score = 0.0
    for key in ("beam_depth_mm", "beam_width_mm"):
        if key in geometry:
            score += abs(float(geometry.get(key) or 0.0))
    return score


def _reinforcement_change_score(update: dict[str, Any]) -> float:
    reinforcement = dict(update.get("reinforcement") or {})
    score = 0.0
    if "ligature_spacing_mm" in reinforcement:
        score += max(0.0, 300.0 - float(reinforcement.get("ligature_spacing_mm") or 300.0))
    if "ligature_diameter_mm" in reinforcement:
        score += max(0.0, float(reinforcement.get("ligature_diameter_mm") or 10.0) - 10.0) * 10.0
    if "ligature_leg_count" in reinforcement:
        score += max(0.0, float(reinforcement.get("ligature_leg_count") or 2.0) - 2.0) * 25.0
    return score


def _constructability_score(record: dict[str, Any]) -> int:
    constructability = dict(record.get("constructability_status") or {})
    return 0 if str(constructability.get("overall") or "PASS").upper() == "PASS" else 1


def _ranking_key(record: dict[str, Any], update: dict[str, Any]) -> tuple[Any, ...]:
    util = record.get("shear_utilisation")
    target_delta = abs(float(util) - TARGET_BAND_UPPER) if util is not None else 999.0
    geometry_score = _geometry_change_score(update)
    reinforcement_score = _reinforcement_change_score(update)
    constructability_score = _constructability_score(record)
    cost_proxy = geometry_score * 10.0 + reinforcement_score
    return (
        0 if _target_band_status(util) == "TARGET" else 1,
        target_delta,
        geometry_score,
        reinforcement_score,
        constructability_score,
        cost_proxy,
        str(record.get("candidate_id") or ""),
    )


def _rank_repairs(records: list[dict[str, Any]], updates_by_id: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ranked = sorted(records, key=lambda record: _ranking_key(record, updates_by_id[str(record.get("candidate_id") or "")]))
    proof_rows = [
        {
            "candidate_id": record.get("candidate_id"),
            "lane_id": record.get("lane_id"),
            "ranking_key": _ranking_key(record, updates_by_id[str(record.get("candidate_id") or "")]),
            "evaluation_hash": record.get("evaluation_hash"),
        }
        for record in ranked
    ]
    return ranked, {
        "criteria": tuple(ranking_criteria()),
        "ranked_candidate_ids": tuple(str(record.get("candidate_id") or "") for record in ranked),
        "ranked_candidate_count": len(ranked),
        "proof_rows": tuple(proof_rows),
    }


def _lane_evidence(
    *,
    lane: dict[str, Any],
    candidate_count: int,
    valid_repairs: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    return {
        "lane_id": str(lane.get("lane_id") or ""),
        "lane_index": int(lane.get("lane_index") or 0),
        "title": str(lane.get("title") or ""),
        "candidate_count": int(candidate_count),
        "valid_repair_count": len(valid_repairs),
        "valid_repair_ids": tuple(str(record.get("candidate_id") or "") for record in valid_repairs),
        "reason": reason,
    }


def _exact_stop_allowed(base_state: dict[str, Any]) -> bool:
    util = _nested_value(base_state, "actions", "current_shear_utilisation", None)
    if util is None:
        util = _nested_value(base_state, "engineering_status", "current_shear_utilisation", None)
    try:
        parsed = float(util)
    except (TypeError, ValueError):
        return False
    return TARGET_BAND_LOWER <= parsed <= TARGET_BAND_UPPER


def _constraints_prohibit_remaining_repairs(base_state: dict[str, Any]) -> bool:
    value = _nested_value(base_state, "constraints", "constraints_prohibit_remaining_repairs", False)
    return bool(value)


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


def run_shear_fail_governs_ladder_runtime(
    *,
    base_state: dict[str, Any],
    evaluate_candidate: CandidateEvaluator,
    max_depth_steps: int = 1,
    max_width_steps: int = 1,
) -> ShearFailGovernsResult:
    """Run the contract-defined SHEAR_FAIL_GOVERNS ladder.

    The evaluator is injected so this runtime can use the shear candidate
    evaluation boundary without importing page/runtime evaluation code.
    """

    contract = load_shear_fail_governs_contract()
    identity = family_identity()
    lane_map = _lane_by_id()
    boundary_input = ShearCandidateInput(base_state=dict(base_state or {}))
    trace: list[dict[str, Any]] = []
    candidate_repairs: list[dict[str, Any]] = []
    accepted_evidence: list[dict[str, Any]] = []
    rejected_evidence: list[dict[str, Any]] = []
    updates_by_id: dict[str, dict[str, Any]] = {}
    selected_lane: str | None = None
    selected_recommendation: dict[str, Any] | None = None
    ranking_proof: dict[str, Any] = {"criteria": tuple(ranking_criteria()), "ranked_candidate_ids": (), "ranked_candidate_count": 0}
    exact_stop_proof: dict[str, Any] = {"allowed": False, "target_band": {"lower": TARGET_BAND_LOWER, "upper": TARGET_BAND_UPPER}}
    exhausted_reason: str | None = None
    no_valid_repair_proof: dict[str, Any] = {"allowed": False}
    blocked_reason: str | None = None
    base_depth = float(
        _nested_value(base_state, "geometry", "beam_depth_mm", 0.0) or 0.0
    )
    base_width = float(
        _nested_value(base_state, "geometry", "beam_width_mm", 0.0) or 0.0
    )
    depth_lane = lane_map.get(
        "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
        {},
    )
    width_lane = lane_map.get(
        "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
        {},
    )
    depth_increment = float(
        dict(depth_lane.get("search_policy") or {}).get("increment_mm") or 25.0
    )
    width_increment = float(
        dict(width_lane.get("search_policy") or {}).get("increment_mm") or 25.0
    )
    canonical_depth_steps = len(
        incremental_geometry_values(
            base_depth,
            maximum_mm=PROJECT_MAX_BEAM_DEPTH_MM,
            increment_mm=depth_increment,
        )
    )
    canonical_width_steps = len(
        incremental_geometry_values(
            base_width,
            maximum_mm=PROJECT_MAX_BEAM_WIDTH_MM,
            increment_mm=width_increment,
        )
    )
    canonical_geometry_exhausted = bool(
        int(max_depth_steps) >= canonical_depth_steps
        and int(max_width_steps) >= canonical_width_steps
    )

    for lane in sorted(internal_strategy_lanes(), key=lambda item: int(item.get("lane_index") or 0)):
        lane_id = str(lane.get("lane_id") or "")
        if lane_id in NON_TERMINAL_LANES:
            candidates = _candidate_updates_for_lane(
                lane_id=lane_id,
                lane=lane,
                base_state=base_state,
                lane_map=lane_map,
                max_depth_steps=max_depth_steps,
                max_width_steps=max_width_steps,
            )
            valid_repairs: list[dict[str, Any]] = []
            for candidate in candidates:
                update = ShearCandidateUpdate(updates=dict(candidate.get("update") or {}))
                evaluation = evaluate_candidate(boundary_input, update)
                if not isinstance(evaluation, ShearCandidateEvaluation):
                    raise TypeError("evaluate_candidate must return ShearCandidateEvaluation")
                if evaluation.evaluation_hash is None:
                    evaluation = evaluation.with_evaluation_hash()
                record = _candidate_repair_record(
                    candidate=candidate,
                    boundary_input=boundary_input,
                    evaluation=evaluation,
                )
                candidate_repairs.append(record)
                updates_by_id[str(candidate.get("candidate_id") or "")] = dict(candidate.get("update") or {})
                if _is_valid_repair(record):
                    valid_repairs.append(record)
            lane_trace = {
                **_lane_evidence(
                    lane=lane,
                    candidate_count=len(candidates),
                    valid_repairs=valid_repairs,
                    reason="valid_repair_found" if valid_repairs else "no_valid_repair_in_lane",
                ),
                "restart_evidence": tuple(
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "restart_lanes": tuple(candidate.get("restart_lanes") or ()),
                    }
                    for candidate in candidates
                    if candidate.get("restart_lanes")
                ),
            }
            trace.append(lane_trace)
            if valid_repairs:
                ranked, ranking_proof = _rank_repairs(valid_repairs, updates_by_id)
                selected = ranked[0]
                selected_lane = lane_id
                selected_recommendation = {
                    "strategy_lane": lane_id,
                    "candidate_id": selected.get("candidate_id"),
                    "update_hash": selected.get("update_hash"),
                    "candidate_state_hash": selected.get("candidate_state_hash"),
                    "evaluation_hash": selected.get("evaluation_hash"),
                    "shear_utilisation": selected.get("shear_utilisation"),
                }
                accepted_evidence.append(lane_trace)
                exact_stop_proof = {
                    "allowed": _target_band_status(selected.get("shear_utilisation")) == "TARGET",
                    "selected_candidate_id": selected.get("candidate_id"),
                    "shear_utilisation": selected.get("shear_utilisation"),
                    "target_band": {"lower": TARGET_BAND_LOWER, "upper": TARGET_BAND_UPPER},
                }
                break
            rejected_evidence.append(lane_trace)
            continue

        if lane_id == "EXACT_STOP":
            allowed = _exact_stop_allowed(base_state)
            exact_stop_proof = {
                "allowed": allowed,
                "target_band": {"lower": TARGET_BAND_LOWER, "upper": TARGET_BAND_UPPER},
                "source": "base_state_current_shear_utilisation",
            }
            trace.append({"lane_id": lane_id, "lane_index": int(lane.get("lane_index") or 0), "accepted": allowed})
            if allowed:
                selected_lane = lane_id
                accepted_evidence.append(trace[-1])
                break
            rejected_evidence.append(trace[-1])
            continue

        if lane_id == "EXHAUSTED":
            exhausted_reason = (
                "project maximum depth and width reached at 5000 mm"
                if canonical_geometry_exhausted
                else "all_contract_strategies_attempted"
            )
            trace.append(
                {
                    "lane_id": lane_id,
                    "lane_index": int(lane.get("lane_index") or 0),
                    "accepted": not _constraints_prohibit_remaining_repairs(base_state),
                    "exhausted_strategy_lanes": NON_TERMINAL_LANE_ORDER,
                    "canonical_geometry_exhausted": canonical_geometry_exhausted,
                    "project_geometry_limit_mm": {
                        "depth": PROJECT_MAX_BEAM_DEPTH_MM,
                        "width": PROJECT_MAX_BEAM_WIDTH_MM,
                    },
                }
            )
            if not _constraints_prohibit_remaining_repairs(base_state):
                selected_lane = lane_id
                if canonical_geometry_exhausted:
                    blocked_reason = exhausted_reason
                    no_valid_repair_proof = {
                        "allowed": True,
                        "all_branches_exhausted": True,
                        "constraints_prohibit_remaining_repairs": False,
                        "canonical_geometry_exhausted": True,
                        "project_geometry_limit_mm": {
                            "depth": PROJECT_MAX_BEAM_DEPTH_MM,
                            "width": PROJECT_MAX_BEAM_WIDTH_MM,
                        },
                    }
                accepted_evidence.append(trace[-1])
                break
            rejected_evidence.append(trace[-1])
            continue

        if lane_id == "NO_VALID_REPAIR":
            allowed = _constraints_prohibit_remaining_repairs(base_state)
            no_valid_repair_proof = {
                "allowed": allowed,
                "all_branches_exhausted": exhausted_reason is not None,
                "constraints_prohibit_remaining_repairs": allowed,
            }
            trace.append({"lane_id": lane_id, "lane_index": int(lane.get("lane_index") or 0), "accepted": allowed})
            if allowed:
                selected_lane = lane_id
                blocked_reason = "no_valid_repair_after_exhausted_contract_ladder"
                accepted_evidence.append(trace[-1])
                break
            rejected_evidence.append(trace[-1])

    if selected_lane is None:
        selected_lane = "EXHAUSTED"
        exhausted_reason = exhausted_reason or "contract_ladder_exhausted_without_selected_recommendation"

    repair_reason_proof = {
        "proof_only": True,
        "selected_strategy_lane": selected_lane,
        "accepted_lane_ids": tuple(str(evidence.get("lane_id") or "") for evidence in accepted_evidence),
        "rejected_lane_ids": tuple(str(evidence.get("lane_id") or "") for evidence in rejected_evidence),
    }
    cta_intent_proof = _build_cta_intent_proof(
        selected_lane=selected_lane,
        selected_recommendation=selected_recommendation,
        blocked_reason=blocked_reason,
    )
    result_payload = {
        "family_id": str(identity.get("family_id") or "SHEAR_FAIL_GOVERNS"),
        "contract_schema": str(contract.get("schema") or ""),
        "contract_lane_order": shear_fail_governs_contract_lane_order(),
        "input_hash": boundary_input.input_hash,
        "selected_strategy_lane": selected_lane,
        "ladder_trace": tuple(trace),
        "candidate_repairs": tuple(candidate_repairs),
        "selected_recommendation": selected_recommendation,
        "accepted_lane_evidence": tuple(accepted_evidence),
        "rejected_lane_evidence": tuple(rejected_evidence),
        "ranking_proof": ranking_proof,
        "exact_stop_proof": exact_stop_proof,
        "exhausted_reason": exhausted_reason,
        "no_valid_repair_proof": no_valid_repair_proof,
        "repair_reason_proof": repair_reason_proof,
        "blocked_reason": blocked_reason,
        "cta_intent_proof": cta_intent_proof,
    }
    ladder_hash = stable_shear_candidate_hash(_result_hash_payload(result_payload))
    return ShearFailGovernsResult(
        selected_strategy_lane=selected_lane,
        ladder_trace=tuple(trace),
        candidate_repairs=tuple(candidate_repairs),
        selected_recommendation=selected_recommendation,
        accepted_lane_evidence=tuple(accepted_evidence),
        rejected_lane_evidence=tuple(rejected_evidence),
        ranking_proof=ranking_proof,
        exact_stop_proof=exact_stop_proof,
        exhausted_reason=exhausted_reason,
        no_valid_repair_proof=no_valid_repair_proof,
        repair_reason_proof=repair_reason_proof,
        blocked_reason=blocked_reason,
        cta_intent_proof=cta_intent_proof,
        ladder_hash=ladder_hash,
    )


__all__ = [
    "CandidateEvaluator",
    "ShearFailGovernsResult",
    "run_shear_fail_governs_ladder_runtime",
    "shear_fail_governs_contract_lane_order",
]
