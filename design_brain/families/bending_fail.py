"""Family owner for pure bending active-fail repair."""

from __future__ import annotations

import math
from typing import Any

from design_brain.candidate_evaluation import (
    BeamCandidateEvaluation,
    BeamCandidateInput,
    BeamCandidateUpdate,
    build_candidate_state_hash,
)
from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyContext, FamilyStrategyMetadata
from design_brain.families.bending_fail_governs.runtime import (
    NON_TERMINAL_LANES,
    bending_fail_governs_contract_lane_order,
    run_bending_fail_governs_ladder_runtime,
)
from design_brain.families.bending_fail_governs.contract import depth_width_rule
from design_brain.families.bending_fail_governs.repair_ladder import (
    BendingFailRepairLadderAddResult,
    build_bending_fail_layout_updates,
    build_bending_fail_known_bad_depth_width_record,
    build_bending_fail_repair_ladder_result,
    decide_bending_fail_repair_ladder_add,
)


ADAPTER_VERSION = "bending_fail_governs.v1"
DEFAULT_BAR_DIAMETERS = (10, 12, 16, 20, 24, 28, 32, 36, 40)
DEFAULT_DEPTH_STEPS_MM = (300.0, 550.0)
DEFAULT_WIDTH_STEPS_MM = (50.0, 100.0, 150.0, 200.0)
MIN_BOTTOM_CLEAR_SPACING_MM = 100.0

CONTRACT_RUNTIME_LANE_SPEC_META = {
    "DEPTH_INCREASE": {
        "stage_name": "contract_runtime_depth_increase",
        "strategy": "contract runtime depth increase",
        "escalation": "contract_runtime_depth_increase",
    },
    "SINGLE_LAYER_BOTTOM_REO": {
        "stage_name": "contract_runtime_single_layer_bottom_reo",
        "strategy": "contract runtime single-layer bottom reinforcement",
        "escalation": "contract_runtime_single_layer_bottom_reo",
    },
    "LARGER_BAR": {
        "stage_name": "contract_runtime_larger_bar",
        "strategy": "contract runtime larger bar",
        "escalation": "contract_runtime_larger_bar",
    },
    "WIDTH_INCREASE": {
        "stage_name": "contract_runtime_width_increase",
        "strategy": "contract runtime width increase",
        "escalation": "contract_runtime_width_increase",
    },
    "MULTI_LAYER_REO": {
        "stage_name": "contract_runtime_multi_layer_reo",
        "strategy": "contract runtime multi-layer reinforcement",
        "escalation": "contract_runtime_multi_layer_reo",
    },
}


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return int(default)
        return int(round(float(value)))
    except (TypeError, ValueError):
        return int(default)


def select_bending_fail_fallback_repair_candidate_from_ladder(
    candidates: list[dict] | tuple[dict, ...] | None,
) -> dict[str, Any]:
    """Select the bending-fail fallback ladder candidate in family-owned order."""

    rows = [dict(candidate or {}) for candidate in list(candidates or []) if isinstance(candidate, dict)]
    if not rows:
        return {
            "selected": {},
            "selection_source": "bending_controller_fallback_ranker",
            "family_selected": {},
        }
    selected = min(
        rows,
        key=lambda cand: (
            int(cand.get("bending_fail_ladder_index") or cand.get("ladder_index") or 999999),
            len(_as_dict(cand.get("updates"))),
        ),
    )
    return {
        "selected": dict(selected),
        "selection_source": "bending_controller_fallback_ranker",
        "family_selected": {},
    }


def _normalise_family(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"flexure", "reo", "reinforcement", "longitudinal"}:
        return "bending"
    if text in {"sectional_shear", "link", "links", "ligature", "ligatures"}:
        return "shear"
    return text


def _context_payload(context: FamilyStrategyContext) -> tuple[dict, dict, dict, dict, dict, dict]:
    payload = _as_dict(context.payload)
    debug = _as_dict(context.debug or payload.get("debug_trace"))
    primary = _as_dict(context.primary)
    if not primary:
        items = _as_list(payload.get("guidance_items"))
        primary = dict(items[0]) if items and isinstance(items[0], dict) else {}
    summary = _as_dict(context.summary or debug.get("overview"))
    evidence = _as_dict(context.evidence)
    if not evidence:
        evidence = _as_dict(
            primary.get("candidate_search_evidence")
            or _as_dict(primary.get("action_payload")).get("candidate_search_evidence")
            or _as_dict(primary.get("resolved_candidate")).get("candidate_search_evidence")
            or debug.get("candidate_search_evidence")
        )
    classifier = _as_dict(context.classifier)
    return payload, primary, summary, evidence, debug, classifier


def _active_strength_failures(summary: dict, debug: dict, classifier: dict) -> set[str]:
    failures: set[str] = set()
    for item in _as_list(classifier.get("active_failures") or debug.get("fail_keys") or summary.get("fail_keys")):
        family = _normalise_family(item)
        if family in {"bending", "shear"}:
            failures.add(family)
    statuses = _as_dict(summary.get("statuses"))
    for family, status in statuses.items():
        if str(status or "").strip().upper() == "FAIL" and _normalise_family(family) in {"bending", "shear"}:
            failures.add(_normalise_family(family))
    utils = _as_dict(summary.get("utils"))
    for family in ("bending", "shear"):
        util = _as_float(utils.get(family), default=-1.0)
        if util > 1.0:
            failures.add(family)
    return failures


def _button_contract(primary: dict, debug: dict) -> dict:
    return _as_dict(
        primary.get("button_contract")
        or debug.get("displayed_primary_button_contract")
        or debug.get("primary_button_contract")
        or debug.get("button_contract")
    )


def _updates_from(primary: dict, debug: dict) -> dict:
    contract = _button_contract(primary, debug)
    action_payload = _as_dict(primary.get("action_payload"))
    resolved = _as_dict(primary.get("resolved_candidate"))
    return _as_dict(
        contract.get("updates")
        or primary.get("updates")
        or primary.get("selected_action_updates")
        or action_payload.get("resolved_candidate_updates")
        or action_payload.get("updates")
        or resolved.get("updates")
    )


def _action_type_from(primary: dict, debug: dict) -> str:
    contract = _button_contract(primary, debug)
    action_payload = _as_dict(primary.get("action_payload"))
    resolved = _as_dict(primary.get("resolved_candidate"))
    return str(
        contract.get("action_type")
        or primary.get("action_type")
        or action_payload.get("resolved_candidate_action_type")
        or action_payload.get("action_type")
        or resolved.get("action_type")
        or ""
    ).strip()


def _normalised_update_diff(base: dict, updates: dict) -> dict:
    out: dict[str, Any] = {}
    for key, value in _as_dict(updates).items():
        if key not in base or str(base.get(key)) != str(value):
            out[key] = value
    return out


def _required_checks_acceptable(overview: dict) -> bool:
    statuses = _as_dict(_as_dict(overview).get("statuses"))
    tracked = [
        str(status or "").strip().upper()
        for status in statuses.values()
        if str(status or "").strip() not in {"", "-", "—"}
    ]
    if not tracked:
        return bool(_as_dict(overview).get("all_key_pass")) and not bool(_as_dict(overview).get("any_fail"))
    return not any(status in {"FAIL", "FAILED", "ERROR"} for status in tracked)


def _bottom_updates(*, row1_count: int, dia: int, row2_count: int = 0) -> dict[str, Any]:
    row1 = max(1, int(row1_count))
    row2 = max(0, int(row2_count))
    dia_i = max(10, int(dia))
    return {
        "bot1_layout_mode": "Count",
        "bot1_count": row1,
        "db_bot_1": dia_i,
        "bot2_layout_mode": "Count",
        "bot2_count": row2,
        "db_bot_2": dia_i,
        "bot_row_count": 2 if row2 > 0 else 1,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": row1,
        "bot_row_1_spacing": 0.0,
        "bot_row_1_dia": dia_i,
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": row2,
        "bot_row_2_spacing": 0.0,
        "bot_row_2_dia": dia_i,
    }


def _dedupe_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for spec in specs:
        updates = _as_dict(spec.get("updates"))
        key = tuple(sorted((str(key), repr(value)) for key, value in updates.items()))
        if not updates or key in seen:
            continue
        seen.add(key)
        out.append(dict(spec))
    return out


def _width_update(width_key: str, width: float) -> dict[str, Any]:
    updates = {width_key: float(width)}
    if width_key != "b":
        updates["b"] = float(width)
    return updates


def _depth_width_ratio_limit_from_contract() -> float:
    return _as_float(depth_width_rule().get("maximum_preferred_ratio"), 2.0)


def _depth_width_ratio(width: float, depth: float) -> float | None:
    width_f = _as_float(width, 0.0)
    depth_f = _as_float(depth, 0.0)
    if width_f <= 0.0 or depth_f <= 0.0:
        return None
    return depth_f / width_f


def _depth_width_ratio_blocked(width: float, depth: float, maximum_ratio: float) -> bool:
    ratio = _depth_width_ratio(width, depth)
    return ratio is not None and ratio > float(maximum_ratio) + 1e-9


def _contract_runtime_candidate_updates(
    *,
    width_key: str,
    geometry_locked: bool,
    base_width: float,
    base_depth: float,
    base_count: int,
    base_dia: int,
    next_dia: int,
    max_dia: int,
    maximum_depth_width_ratio: float,
) -> dict[str, dict[str, Any]]:
    split_row1 = max(2, int(math.ceil(float(base_count + 1) / 2.0)))
    split_row2 = max(2, int(base_count + 1) - split_row1)
    updates: dict[str, dict[str, Any]] = {
        "GEOMETRY_SANITY": {},
        "DEPTH_INCREASE": {},
        "SINGLE_LAYER_BOTTOM_REO": _bottom_updates(row1_count=base_count + 1, dia=base_dia),
        "LARGER_BAR": _bottom_updates(row1_count=base_count, dia=next_dia),
        "WIDTH_INCREASE": {},
        "MULTI_LAYER_REO": _bottom_updates(row1_count=split_row1, row2_count=split_row2, dia=max(next_dia, max_dia)),
        "EXACT_STOP": {},
        "NO_VALID_STRATEGY": {},
    }
    if not geometry_locked:
        depth_candidate = float(base_depth + 25.0)
        if not _depth_width_ratio_blocked(base_width, depth_candidate, maximum_depth_width_ratio):
            updates["DEPTH_INCREASE"] = {"D": depth_candidate}
        updates["WIDTH_INCREASE"] = _width_update(width_key, float(base_width + 50.0))
    return updates


def _contract_runtime_evaluator(
    candidate_input: BeamCandidateInput,
    candidate_update: BeamCandidateUpdate,
) -> BeamCandidateEvaluation:
    return BeamCandidateEvaluation(
        input_hash=candidate_input.state_hash,
        candidate_state_hash=build_candidate_state_hash(
            candidate_input.base_state,
            candidate_update.updates,
        ),
        update_hash=candidate_update.update_hash,
        bending_utilisation=None,
        shear_utilisation=None,
        engineering_status={"accepted": False, "lane_result": "SPEC_GENERATION_ONLY"},
        failure_flags={},
    ).with_evaluation_hash()


def bending_fail_no_valid_repair_proof_from_evidence(evidence: dict | None) -> dict[str, Any]:
    """Return family-owned no-valid-repair proof from exhaustive bending evidence.

    This is used by publication as a consumer of family proof. It deliberately
    requires exhaustive repair evidence and zero safe/executable candidates so a
    generic cap-only diagnostic cannot become a terminal no-apply result.
    """

    row = _as_dict(evidence)
    if isinstance(row.get("exact_blockers_by_family"), dict):
        row = {**row, **_as_dict(row["exact_blockers_by_family"].get("bending"))}
    if str(row.get("family") or "bending").strip().lower() != "bending":
        return {}
    active = {
        str(item or "").strip().lower()
        for item in _as_list(row.get("active_failures") or ["bending"])
        if str(item or "").strip()
    }
    if active and "bending" not in active:
        return {}
    repair_ran = str(row.get("repair_search_ran") or row.get("candidate_search_ran") or "").strip().lower()
    repair_exhaustive = str(
        row.get("repair_search_exhaustive") or row.get("candidate_search_exhaustive") or ""
    ).strip().lower()
    attempted = _as_int(row.get("attempted_candidate_count") or row.get("candidate_inventory_count"), 0)
    safe = _as_int(row.get("safe_repair_candidate_count") or row.get("safe_candidate_count"), 0)
    executable = _as_int(
        row.get("executable_repair_candidate_count")
        or row.get("executable_candidate_count")
        or row.get("safe_executor_backed_candidates_count"),
        0,
    )
    reason = str(
        row.get("reason")
        or row.get("outside_target_band_allowed_reason")
        or row.get("active_under_capacity_blocker_reason")
        or row.get("blocked_reason")
        or ""
    ).strip()
    scope = str(row.get("active_fail_repair_search_scope") or row.get("search_scope") or "").strip()
    source = str(row.get("source") or "").strip()
    if not (
        repair_ran == "true"
        and repair_exhaustive == "true"
        and attempted > 0
        and safe == 0
        and executable == 0
        and reason
        and ("bending" in scope.lower() or "bending" in source.lower() or not scope)
    ):
        return {}
    checked = tuple(row.get("contract_strategies_checked") or NON_TERMINAL_LANES)
    return {
        "family_id": "BENDING_FAIL_GOVERNS",
        "terminal_status": "REPAIR_BLOCKED",
        "repair_blocked": True,
        "blocked_reason": reason,
        "blocked_reason_source": "family_contract_blocker_proof",
        "internal_cap_only": False,
        "hard_blocker_proven": False,
        "contract_strategy_exhaustion_proven": True,
        "contract_strategies_checked": checked,
        "contract_strategies_blocked": tuple(row.get("contract_strategies_blocked") or ()),
        "contract_strategies_remaining": (),
        "implementation_caps_hit": tuple(row.get("implementation_caps_hit") or ()),
        "geometry_locks_used": tuple(row.get("geometry_locks_used") or ()),
        "project_constraints_used": tuple(row.get("project_constraints_used") or ()),
        "detailing_constraints_used": tuple(row.get("detailing_constraints_used") or ()),
        "evaluated_candidate_count": attempted,
        "safe_candidate_count": safe,
        "executable_candidate_count": executable,
        "proof_source": "BENDING_FAIL_GOVERNS.exhaustive_no_valid_repair_evidence",
    }


class BendingFailFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="BENDING_FAIL_GOVERNS",
        owner="design_brain.families.bending_fail.BendingFailFamily",
        candidate_strategy="contracted_bounded_pure_bending_repair_ladder",
        ranking_strategy="contract_ladder_first_compliant_bending_repair",
        evidence_strategy="family_owned_bending_active_failure_ladder_evidence",
        publication_rule="bending_repair_action_or_proven_no_repair",
        cta_rule="single_executor_backed_apply_cta_for_selected_bending_repair",
        affected_by_shared_helpers=("capacity_checks", "fit_checks", "candidate_schema", "target_band_scoring"),
        regression_id="bending_fail_governs_repair_regression",
        migrated=True,
        locked=False,
    )

    def contracted_repair_ladder_specs(
        self,
        state: dict,
        *,
        width_key: str = "b",
        geometry_locked: bool = False,
        bar_diameters: tuple[int, ...] | list[int] | None = None,
    ) -> dict[str, Any]:
        """Return the contract-owned staged pure bending repair ladder."""
        base = _as_dict(state)
        diameters = tuple(int(value) for value in (bar_diameters or DEFAULT_BAR_DIAMETERS))
        base_width = _as_float(base.get(width_key), _as_float(base.get("b"), 300.0))
        base_depth = _as_float(base.get("D"), 350.0)
        base_count = max(2, _as_int(base.get("bot_row_1_bars"), _as_int(base.get("bot1_count"), 2)))
        base_dia = max(10, _as_int(base.get("bot_row_1_dia"), _as_int(base.get("db_bot_1"), 10)))
        larger_dias = [int(dia) for dia in diameters if int(dia) > base_dia]
        max_dia = max(diameters) if diameters else base_dia
        next_dia = larger_dias[0] if larger_dias else base_dia
        cover_side = _as_float(base.get("cover_side"), 40.0)
        lig_d = max(0, _as_int(base.get("lig_d"), 0))
        maximum_depth_width_ratio = _depth_width_ratio_limit_from_contract()
        runtime_updates = _contract_runtime_candidate_updates(
            width_key=width_key,
            geometry_locked=geometry_locked,
            base_width=base_width,
            base_depth=base_depth,
            base_count=base_count,
            base_dia=base_dia,
            next_dia=next_dia,
            max_dia=max_dia,
            maximum_depth_width_ratio=maximum_depth_width_ratio,
        )
        runtime_result = run_bending_fail_governs_ladder_runtime(
            base_state=base,
            lane_candidate_updates=runtime_updates,
            evaluate_candidate=_contract_runtime_evaluator,
        )
        runtime_trace_by_lane = {
            str(row.get("lane_id") or ""): dict(row)
            for row in list(runtime_result.ladder_trace or ())
            if isinstance(row, dict)
        }
        runtime_order = bending_fail_governs_contract_lane_order()
        runtime_specs: list[dict[str, Any]] = []
        runtime_known_bad: list[dict[str, Any]] = []
        runtime_index = 0

        for lane_id in runtime_order:
            meta = CONTRACT_RUNTIME_LANE_SPEC_META.get(lane_id)
            if meta is None:
                continue
            full_updates = dict(runtime_updates.get(lane_id) or {})
            diff = _normalised_update_diff(base, full_updates)
            if not diff:
                continue
            width, depth, row1, row2, dia, split, clear = build_bending_fail_layout_updates(
                full_updates,
                width_key=width_key,
                base_width=base_width,
                base_depth=base_depth,
                base_count=base_count,
                base_dia=base_dia,
                cover_side=cover_side,
                lig_d=lig_d,
            )
            spacing_blocked = clear < MIN_BOTTOM_CLEAR_SPACING_MM - 1e-9
            ratio_blocked = _depth_width_ratio_blocked(width, depth, maximum_depth_width_ratio)
            if ratio_blocked:
                runtime_known_bad.append(
                    build_bending_fail_known_bad_depth_width_record(
                        stage_name=str(meta["stage_name"]),
                        strategy=str(meta["strategy"]),
                        width=width,
                        depth=depth,
                        row1=row1,
                        row2=row2,
                        dia=dia,
                        split=split,
                        clear=clear,
                        maximum_depth_width_ratio=maximum_depth_width_ratio,
                    )
                )
                continue
            if spacing_blocked:
                decision = decide_bending_fail_repair_ladder_add(
                    step=int(runtime_order.index(lane_id)),
                    stage_name=str(meta["stage_name"]),
                    strategy=str(meta["strategy"]),
                    updates=full_updates,
                    diff=None,
                    spacing_blocked=True,
                    width=width,
                    depth=depth,
                    row1=row1,
                    row2=row2,
                    dia=dia,
                    split=split,
                    clear=clear,
                    minimum_clear_spacing_mm=float(MIN_BOTTOM_CLEAR_SPACING_MM),
                    escalation=str(meta["escalation"]),
                )
                if decision.should_record_known_bad and decision.known_bad_record is not None:
                    runtime_known_bad.append(decision.known_bad_record)
                continue
            runtime_index += 1
            label = f"BENDING_FAIL_GOVERNS contract runtime {runtime_index}: {meta['strategy']}"
            decision = decide_bending_fail_repair_ladder_add(
                step=int(runtime_order.index(lane_id)),
                stage_name=str(meta["stage_name"]),
                strategy=str(meta["strategy"]),
                updates=full_updates,
                diff=diff,
                spacing_blocked=False,
                assigned_candidate_index=runtime_index,
                assigned_label=label,
                escalation=str(meta["escalation"]),
                width=width,
                depth=depth,
                row1=row1,
                row2=row2,
                dia=dia,
                split=split,
                clear=clear,
                minimum_clear_spacing_mm=float(MIN_BOTTOM_CLEAR_SPACING_MM),
            )
            if decision.should_append_spec and decision.spec_payload is not None:
                evidence = dict(runtime_trace_by_lane.get(lane_id) or {})
                spec = {
                    **decision.spec_payload,
                    "contract_runtime_authority": "run_bending_fail_governs_ladder_runtime",
                    "contract_runtime_lane_id": lane_id,
                    "selected_strategy_lane": lane_id,
                    "ladder_hash": runtime_result.ladder_hash,
                    "bending_fail_contract_runtime_ladder_hash": runtime_result.ladder_hash,
                    "ladder_trace_evidence": {
                        "lane_id": evidence.get("lane_id"),
                        "contract_lane_id": evidence.get("contract_lane_id"),
                        "lane_index": evidence.get("lane_index"),
                        "evaluation_hash": evidence.get("evaluation_hash"),
                    },
                    "update_hash": evidence.get("update_hash"),
                    "candidate_state_hash": evidence.get("candidate_state_hash"),
                }
                runtime_specs.append(spec)

        runtime_depth_steps = [25.0, 550.0]

        if not geometry_locked:
            runtime_width_steps = [50.0, 150.0, 200.0]
            if not runtime_specs:
                moderate_width_step = 50.0
                moderate_depth_step = 150.0
                moderate_width = float(base_width + moderate_width_step)
                moderate_depth = float(base_depth + moderate_depth_step)
                moderate_count = max(int(base_count) + 4, 7)
                moderate_dia = next((int(dia) for dia in diameters if int(dia) >= 20), int(max_dia))
                moderate_updates = {
                    **_width_update(width_key, moderate_width),
                    "D": moderate_depth,
                    **_bottom_updates(row1_count=moderate_count, row2_count=0, dia=moderate_dia),
                }
                diff = _normalised_update_diff(base, moderate_updates)
                if diff:
                    (
                        layout_width,
                        layout_depth,
                        row1,
                        row2,
                        dia,
                        split,
                        clear,
                    ) = build_bending_fail_layout_updates(
                        moderate_updates,
                        width_key=width_key,
                        base_width=base_width,
                        base_depth=base_depth,
                        base_count=base_count,
                        base_dia=base_dia,
                        cover_side=cover_side,
                        lig_d=lig_d,
                    )
                    if _depth_width_ratio_blocked(layout_width, layout_depth, maximum_depth_width_ratio):
                        runtime_known_bad.append(
                            build_bending_fail_known_bad_depth_width_record(
                                stage_name="contract_runtime_moderate_geometry_reo_rescue",
                                strategy=(
                                    f"contract runtime moderate geometry/reinforcement rescue to "
                                    f"{moderate_width:.0f} x {moderate_depth:.0f} mm with {moderate_count} N{moderate_dia}"
                                ),
                                width=layout_width,
                                depth=layout_depth,
                                row1=row1,
                                row2=row2,
                                dia=dia,
                                split=split,
                                clear=clear,
                                maximum_depth_width_ratio=maximum_depth_width_ratio,
                            )
                        )
                    else:
                        decision = decide_bending_fail_repair_ladder_add(
                            step=5,
                            stage_name="contract_runtime_moderate_geometry_reo_rescue",
                            strategy=(
                                f"contract runtime moderate geometry/reinforcement rescue to "
                                f"{moderate_width:.0f} x {moderate_depth:.0f} mm with {moderate_count} N{moderate_dia}"
                            ),
                            updates=moderate_updates,
                            diff=diff,
                            spacing_blocked=False,
                            assigned_candidate_index=runtime_index + 1,
                            assigned_label=(
                                f"BENDING_FAIL_GOVERNS contract runtime {runtime_index + 1}: "
                                "contract runtime moderate geometry/reinforcement rescue"
                            ),
                            escalation="bounded_geometry_and_reinforcement_repair",
                            width=layout_width,
                            depth=layout_depth,
                            row1=row1,
                            row2=row2,
                            dia=dia,
                            split=split,
                            clear=clear,
                            minimum_clear_spacing_mm=float(MIN_BOTTOM_CLEAR_SPACING_MM),
                        )
                        if decision.should_append_spec and decision.spec_payload is not None:
                            runtime_index += 1
                            moderate_update = BeamCandidateUpdate(updates=moderate_updates)
                            moderate_evaluation = _contract_runtime_evaluator(
                                BeamCandidateInput(base_state=base),
                                moderate_update,
                            )
                            runtime_specs.append(
                                {
                                    **decision.spec_payload,
                                    "contract_runtime_authority": "run_bending_fail_governs_ladder_runtime",
                                    "contract_runtime_lane_id": "MODERATE_GEOMETRY_REO_RESCUE",
                                    "selected_strategy_lane": "MODERATE_GEOMETRY_REO_RESCUE",
                                    "ladder_hash": runtime_result.ladder_hash,
                                    "bending_fail_contract_runtime_ladder_hash": runtime_result.ladder_hash,
                                    "ladder_trace_evidence": {
                                        "lane_id": "MODERATE_GEOMETRY_REO_RESCUE",
                                        "contract_lane_id": "moderate_geometry_reinforcement_rescue",
                                        "lane_index": 5,
                                        "evaluation_hash": moderate_evaluation.evaluation_hash,
                                    },
                                    "update_hash": moderate_update.update_hash,
                                    "candidate_state_hash": moderate_evaluation.candidate_state_hash,
                                    "spacing_threshold_basis": (
                                        "single-layer clear-spacing threshold is diagnostic for lane transition; "
                                        "candidate remains subject to full evaluator acceptance"
                                    ),
                                }
                            )
                            runtime_depth_steps.append(float(moderate_depth_step))

            heavy_count = max(base_count + 3, 6)
            heavy_row1 = int(math.ceil(float(heavy_count) / 2.0))
            heavy_row2 = max(0, int(heavy_count) - heavy_row1)
            rescue_width_depth_steps: list[tuple[float, float]] = [(200.0, 550.0), (150.0, 550.0)]
            governing_depth = float(base_depth + 550.0)
            governing_row_count = max(heavy_row1, heavy_row2)
            spacing_width = (
                float(MIN_BOTTOM_CLEAR_SPACING_MM) * float(max(0, governing_row_count - 1))
                + (2.0 * float(cover_side))
                + (2.0 * float(lig_d))
                + (float(governing_row_count) * float(max_dia))
            )
            ratio_width = governing_depth / float(maximum_depth_width_ratio or 1.0)
            required_width = max(float(base_width), spacing_width, ratio_width)
            required_width_step = max(0.0, math.ceil((required_width - float(base_width)) / 50.0) * 50.0)
            if required_width_step > 200.0:
                rescue_width_depth_steps.insert(0, (float(required_width_step), 550.0))
            for step, _ in rescue_width_depth_steps:
                if step not in runtime_width_steps:
                    runtime_width_steps.append(float(step))
                if 550.0 not in runtime_depth_steps:
                    runtime_depth_steps.append(550.0)
            for width_step, depth_step in rescue_width_depth_steps:
                width = float(base_width + width_step)
                width_updates = _width_update(width_key, width)
                depth = float(base_depth + depth_step)
                rescue_updates = {
                    **width_updates,
                    "D": depth,
                    **_bottom_updates(row1_count=heavy_row1, row2_count=heavy_row2, dia=max_dia),
                }
                diff = _normalised_update_diff(base, rescue_updates)
                if not diff:
                    continue
                layout_width, layout_depth, row1, row2, dia, split, clear = build_bending_fail_layout_updates(
                    rescue_updates,
                    width_key=width_key,
                    base_width=base_width,
                    base_depth=base_depth,
                    base_count=base_count,
                    base_dia=base_dia,
                    cover_side=cover_side,
                    lig_d=lig_d,
                )
                if _depth_width_ratio_blocked(layout_width, layout_depth, maximum_depth_width_ratio):
                    runtime_known_bad.append(
                        build_bending_fail_known_bad_depth_width_record(
                            stage_name="contract_runtime_combined_high_capacity_rescue",
                            strategy=(
                                f"contract runtime combined rescue to {width:.0f} x {depth:.0f} mm "
                                f"with split high-capacity bottom reinforcement ({heavy_row1}+{heavy_row2} N{max_dia})"
                            ),
                            width=layout_width,
                            depth=layout_depth,
                            row1=row1,
                            row2=row2,
                            dia=dia,
                            split=split,
                            clear=clear,
                            maximum_depth_width_ratio=maximum_depth_width_ratio,
                        )
                    )
                    continue
                decision = decide_bending_fail_repair_ladder_add(
                    step=6,
                    stage_name="contract_runtime_combined_high_capacity_rescue",
                    strategy=(
                        f"contract runtime combined rescue to {width:.0f} x {depth:.0f} mm "
                        f"with split high-capacity bottom reinforcement ({heavy_row1}+{heavy_row2} N{max_dia})"
                    ),
                    updates=rescue_updates,
                    diff=diff,
                    spacing_blocked=clear < MIN_BOTTOM_CLEAR_SPACING_MM - 1e-9,
                    assigned_candidate_index=runtime_index + 1,
                    assigned_label=(
                        f"BENDING_FAIL_GOVERNS contract runtime {runtime_index + 1}: "
                        "contract runtime combined high-capacity rescue"
                    ),
                    escalation="bounded_geometry_and_reinforcement_repair",
                    width=layout_width,
                    depth=layout_depth,
                    row1=row1,
                    row2=row2,
                    dia=dia,
                    split=split,
                    clear=clear,
                    minimum_clear_spacing_mm=float(MIN_BOTTOM_CLEAR_SPACING_MM),
                )
                if decision.should_record_known_bad and decision.known_bad_record is not None:
                    runtime_known_bad.append(decision.known_bad_record)
                    continue
                if decision.should_append_spec and decision.spec_payload is not None:
                    runtime_index += 1
                    rescue_update = BeamCandidateUpdate(updates=rescue_updates)
                    rescue_evaluation = _contract_runtime_evaluator(
                        BeamCandidateInput(base_state=base),
                        rescue_update,
                    )
                    spec = {
                        **decision.spec_payload,
                        "contract_runtime_authority": "run_bending_fail_governs_ladder_runtime",
                        "contract_runtime_lane_id": "MULTI_LAYER_REO",
                        "selected_strategy_lane": "MULTI_LAYER_REO",
                        "ladder_hash": runtime_result.ladder_hash,
                        "bending_fail_contract_runtime_ladder_hash": runtime_result.ladder_hash,
                        "ladder_trace_evidence": {
                            "lane_id": "MULTI_LAYER_REO",
                            "contract_lane_id": "multi_layer_reinforcement",
                            "lane_index": 5,
                            "evaluation_hash": rescue_evaluation.evaluation_hash,
                        },
                        "update_hash": rescue_update.update_hash,
                        "candidate_state_hash": rescue_evaluation.candidate_state_hash,
                    }
                    runtime_specs.append(spec)

        stop_reason = (
            "geometry locked; legal no-repair proof required if contract runtime candidates fail"
            if geometry_locked
            else "contract runtime ladder exhausted; legal no-repair proof required"
        )
        deduped_runtime_specs = _dedupe_specs(runtime_specs)
        spec_generation_accepted_evidence = [
            {
                "lane_id": spec.get("contract_runtime_lane_id"),
                "contract_lane_id": dict(spec.get("ladder_trace_evidence") or {}).get("contract_lane_id"),
                "lane_index": dict(spec.get("ladder_trace_evidence") or {}).get("lane_index"),
                "accepted": True,
                "engineering_acceptance": False,
                "reason": "SPEC_GENERATION_ACCEPTED_FOR_PAGE_EVALUATION",
                "update_hash": spec.get("update_hash"),
                "candidate_state_hash": spec.get("candidate_state_hash"),
                "evaluation_hash": dict(spec.get("ladder_trace_evidence") or {}).get("evaluation_hash"),
            }
            for spec in deduped_runtime_specs
            if isinstance(spec, dict)
        ]
        runtime_ladder = build_bending_fail_repair_ladder_result(
            governing_state=self.metadata.governing_state,
            candidate_strategy="contract_runtime_bending_fail_governs_ladder",
            bar_diameters_tried=[int(next_dia)] if int(next_dia) != int(base_dia) else [],
            depth_steps_mm=list(runtime_depth_steps) if not geometry_locked else [],
            width_steps_mm=list(runtime_width_steps) if not geometry_locked else [],
            minimum_clear_spacing_mm=float(MIN_BOTTOM_CLEAR_SPACING_MM),
            known_bad_candidates_skipped=runtime_known_bad,
            ranking_rule=(
                "Evaluate contract runtime candidates until a target-band executor-backed pure "
                "bending repair is found, or until all valid repair candidates are exhausted; "
                "rank compliant candidates by target-band satisfaction before ladder-order tie-breaks."
            ),
            stop_reason_if_no_candidate=stop_reason,
            specs=deduped_runtime_specs,
        )
        runtime_ladder.update(
            {
                "contract_runtime_authority": "run_bending_fail_governs_ladder_runtime",
                "contract_runtime_driven": True,
                "contract_lane_order": list(runtime_order),
                "selected_strategy_lane": runtime_result.selected_strategy_lane,
                "ladder_hash": runtime_result.ladder_hash,
                "bending_fail_contract_runtime_ladder_hash": runtime_result.ladder_hash,
                "ladder_trace": list(runtime_result.ladder_trace),
                "accepted_lane_evidence": list(runtime_result.accepted_lane_evidence)
                or spec_generation_accepted_evidence,
                "rejected_lane_evidence": list(runtime_result.rejected_lane_evidence),
                "spec_generation_accepted_evidence": spec_generation_accepted_evidence,
                "repair_reason_proof": dict(runtime_result.repair_reason_proof or {}),
                "blocked_reason": runtime_result.blocked_reason,
                "terminal_status": runtime_result.terminal_status,
                "repair_blocked": bool(runtime_result.repair_blocked),
                "blocked_reason_source": runtime_result.blocked_reason_source,
                "internal_cap_only": bool(runtime_result.internal_cap_only),
                "hard_blocker_proven": bool(runtime_result.hard_blocker_proven),
                "contract_strategy_exhaustion_proven": bool(runtime_result.contract_strategy_exhaustion_proven),
                "contract_strategies_checked": list(runtime_result.contract_strategies_checked),
                "contract_strategies_blocked": list(runtime_result.contract_strategies_blocked),
                "contract_strategies_remaining": list(runtime_result.contract_strategies_remaining),
                "implementation_caps_hit": list(runtime_result.implementation_caps_hit),
                "geometry_locks_used": list(runtime_result.geometry_locks_used),
                "project_constraints_used": list(runtime_result.project_constraints_used),
                "detailing_constraints_used": list(runtime_result.detailing_constraints_used),
                "cta_intent_proof": dict(runtime_result.cta_intent_proof or {}),
            }
        )
        return runtime_ladder

        specs: list[dict[str, Any]] = []
        skipped_known_bad: list[dict[str, Any]] = []
        add_results: list[BendingFailRepairLadderAddResult] = []
        index = 0

        def _updates_layout(updates: dict[str, Any]) -> tuple[float, float, int, int, int, bool, float]:
            return build_bending_fail_layout_updates(
                updates,
                width_key=width_key,
                base_width=base_width,
                base_depth=base_depth,
                base_count=base_count,
                base_dia=base_dia,
                cover_side=cover_side,
                lig_d=lig_d,
            )

        def _add(
            *,
            step: int,
            stage_name: str,
            strategy: str,
            updates: dict[str, Any],
            escalation: str | None = None,
            require_spacing_fit: bool = True,
        ) -> None:
            nonlocal index
            width, depth, row1, row2, dia, split, clear = _updates_layout(dict(updates or {}))
            spacing_blocked = require_spacing_fit and clear < MIN_BOTTOM_CLEAR_SPACING_MM - 1e-9
            if spacing_blocked:
                decision = decide_bending_fail_repair_ladder_add(
                    step=step,
                    stage_name=stage_name,
                    strategy=strategy,
                    updates=updates,
                    diff=None,
                    spacing_blocked=spacing_blocked,
                    width=width,
                    depth=depth,
                    row1=row1,
                    row2=row2,
                    dia=dia,
                    split=split,
                    clear=clear,
                    minimum_clear_spacing_mm=float(MIN_BOTTOM_CLEAR_SPACING_MM),
                )
                if decision.should_record_known_bad and decision.known_bad_record is not None:
                    skipped_known_bad.append(decision.known_bad_record)
                add_results.append(decision.add_result)
                return
            diff = _normalised_update_diff(base, updates)
            if not diff:
                decision = decide_bending_fail_repair_ladder_add(
                    step=step,
                    stage_name=stage_name,
                    strategy=strategy,
                    updates=updates,
                    diff=diff,
                    spacing_blocked=False,
                    width=width,
                    depth=depth,
                    row1=row1,
                    row2=row2,
                    dia=dia,
                    split=split,
                    clear=clear,
                    minimum_clear_spacing_mm=float(MIN_BOTTOM_CLEAR_SPACING_MM),
                )
                add_results.append(decision.add_result)
                return
            index += 1
            label = f"BENDING_FAIL_GOVERNS ladder {index}: {strategy}"
            decision = decide_bending_fail_repair_ladder_add(
                step=step,
                stage_name=stage_name,
                strategy=strategy,
                updates=updates,
                diff=diff,
                spacing_blocked=False,
                assigned_candidate_index=index,
                assigned_label=label,
                escalation=escalation,
                width=width,
                depth=depth,
                row1=row1,
                row2=row2,
                dia=dia,
                split=split,
                clear=clear,
                minimum_clear_spacing_mm=float(MIN_BOTTOM_CLEAR_SPACING_MM),
            )
            if decision.should_append_spec and decision.spec_payload is not None:
                specs.append(decision.spec_payload)
            add_results.append(decision.add_result)

        # Stage 1: reinforcement only, same b and D. Keep this deliberately
        # small and skip one-row layouts that are already known not to fit.
        for count in (base_count + 1, base_count + 2):
            _add(
                step=1,
                stage_name="stage_1_reo_only_same_geometry",
                strategy=f"increase bottom bar count to {count} using {base_dia} mm bars",
                updates=_bottom_updates(row1_count=count, dia=base_dia),
            )
        for dia in larger_dias[:4]:
            _add(
                step=1,
                stage_name="stage_1_reo_only_same_geometry",
                strategy=f"increase bottom bar diameter to {dia} mm",
                updates=_bottom_updates(row1_count=base_count, dia=dia),
            )
        for dia in (next_dia, max_dia):
            split_row1 = max(2, int(math.ceil(float(base_count + 1) / 2.0)))
            split_row2 = max(2, int(base_count + 1) - split_row1)
            _add(
                step=1,
                stage_name="stage_1_reo_only_same_geometry",
                strategy=f"split bottom reinforcement into two rows using N{int(dia)} bars",
                updates=_bottom_updates(row1_count=split_row1, row2_count=split_row2, dia=dia),
                escalation="same_geometry_split_row_reo",
            )

        if not geometry_locked:
            heavy_count = max(base_count + 3, 6)
            heavy_row1 = int(math.ceil(float(heavy_count) / 2.0))
            heavy_row2 = max(0, int(heavy_count) - heavy_row1)

            # Stage 2: increase depth in 25 mm increments, same width, and try
            # the most efficient bottom reinforcement layout that still fits.
            for depth_step in DEFAULT_DEPTH_STEPS_MM:
                depth = float(base_depth + depth_step)
                _add(
                    step=2,
                    stage_name="stage_2_depth_increments_same_width",
                    strategy=f"increase depth to {depth:.0f} mm and retry split bottom reinforcement",
                    updates={
                        "D": depth,
                        **_bottom_updates(
                            row1_count=max(2, int(math.ceil(float(base_count + 1) / 2.0))),
                            row2_count=max(2, int(base_count + 1) - int(math.ceil(float(base_count + 1) / 2.0))),
                            dia=max_dia,
                        ),
                    },
                    escalation="depth_increment_with_split_reo",
                )

            # Stage 3: increase width only after reinforcement fit/spacing is
            # the limiting factor, then retry split-row reinforcement.
            for width_step in DEFAULT_WIDTH_STEPS_MM:
                width = float(base_width + width_step)
                width_updates = {width_key: width}
                if width_key != "b":
                    width_updates["b"] = width
                _add(
                    step=3,
                    stage_name="stage_3_width_increments_for_reo_fit",
                    strategy=f"increase width to {width:.0f} mm and retry high-capacity split bottom reinforcement",
                    updates={**width_updates, **_bottom_updates(row1_count=heavy_row1, row2_count=heavy_row2, dia=max_dia)},
                    escalation="bar_fit_or_detailing_width_relief",
                )

            # Stage 4: compact combined rescue. Put the strongest known rescue
            # class first, then nearby bounded alternatives. This prevents the
            # family from walking a broad width/depth grid after fit has already
            # forced split high-capacity reinforcement.
            for width_step, depth_step in (
                (200.0, 550.0),
                (150.0, 550.0),
            ):
                width = float(base_width + width_step)
                width_updates = {width_key: width}
                if width_key != "b":
                    width_updates["b"] = width
                depth = float(base_depth + depth_step)
                _add(
                    step=4,
                    stage_name="stage_4_combined_rescue",
                    strategy=(
                        f"increase width to {width:.0f} mm and depth to {depth:.0f} mm "
                        f"with split high-capacity bottom reinforcement ({heavy_row1}+{heavy_row2} N{max_dia})"
                    ),
                    updates={
                        **width_updates,
                        "D": depth,
                        **_bottom_updates(row1_count=heavy_row1, row2_count=heavy_row2, dia=max_dia),
                    },
                    escalation="bounded_geometry_and_reinforcement_repair",
                )

        stop_reason = (
            "geometry locked; legal no-repair proof required if reinforcement ladder fails"
            if geometry_locked
            else "bounded bending repair ladder exhausted; legal no-repair proof required"
        )
        return build_bending_fail_repair_ladder_result(
            governing_state=self.metadata.governing_state,
            candidate_strategy=self.metadata.candidate_strategy,
            bar_diameters_tried=list(larger_dias),
            depth_steps_mm=list(DEFAULT_DEPTH_STEPS_MM if not geometry_locked else ()),
            width_steps_mm=list(DEFAULT_WIDTH_STEPS_MM if not geometry_locked else ()),
            minimum_clear_spacing_mm=float(MIN_BOTTOM_CLEAR_SPACING_MM),
            known_bad_candidates_skipped=skipped_known_bad,
            ranking_rule=(
                "Evaluate staged contract candidates until a target-band executor-backed pure "
                "bending repair is found, or until all valid repair candidates are exhausted; "
                "rank compliant candidates by target-band satisfaction before ladder-order tie-breaks."
            ),
            stop_reason_if_no_candidate=stop_reason,
            specs=_dedupe_specs(specs),
        )

    def select_repair_candidate_from_ladder(
        self,
        candidates: list[dict],
        *,
        target_low: float,
        target_high: float,
    ) -> dict[str, Any]:
        rows = [dict(row) for row in list(candidates or []) if isinstance(row, dict)]
        safe = [
            row
            for row in rows
            if bool(row.get("is_compliant"))
            and not bool(_as_dict(row.get("overview")).get("any_fail"))
            and bool(_required_checks_acceptable(_as_dict(row.get("overview"))))
        ]
        if not safe:
            return {
                "selected": None,
                "ranking_strategy": self.metadata.ranking_strategy,
                "selection_reason": "no_compliant_candidate_in_contract_ladder",
                "candidate_count": len(rows),
                "safe_candidate_count": 0,
            }
        selected = min(
            safe,
            key=lambda row: (
                0
                if float(target_low)
                <= _as_float(
                    row.get("candidate_post_util")
                    or row.get("worst_util")
                    or _as_dict(row.get("overview")).get("worst_util"),
                    0.0,
                )
                <= float(target_high)
                else 1,
                abs(
                    _as_float(row.get("candidate_post_util") or row.get("worst_util"), 0.0)
                    - ((float(target_low) + float(target_high)) / 2.0)
                ),
                int(row.get("bending_fail_ladder_index") or row.get("ladder_index") or 999999),
                len(_as_dict(row.get("updates"))),
            ),
        )
        selected_util = _as_float(
            selected.get("candidate_post_util")
            or selected.get("worst_util")
            or _as_dict(selected.get("overview")).get("worst_util"),
            0.0,
        )
        selected_in_target = bool(float(target_low) <= selected_util <= float(target_high))
        return {
            "selected": dict(selected),
            "ranking_strategy": self.metadata.ranking_strategy,
            "selection_reason": (
                "target_band_candidate_selected_by_contract"
                if selected_in_target
                else "best_compliant_candidate_selected_after_target_band_exhaustion"
            ),
            "candidate_count": len(rows),
            "safe_candidate_count": len(safe),
            "selected_ladder_index": int(selected.get("bending_fail_ladder_index") or selected.get("ladder_index") or 0),
            "target_low": float(target_low),
            "target_high": float(target_high),
            "selected_candidate_post_util": selected_util,
            "selected_in_target_band": selected_in_target,
        }

    def repair_ladder_evidence_overlay(
        self,
        *,
        ladder: dict,
        selected_result: dict,
    ) -> dict[str, Any]:
        selected = _as_dict(selected_result.get("selected"))
        spec_count = len(_as_list(ladder.get("specs")))
        known_bad_count = int(ladder.get("known_bad_candidate_count") or 0)
        generated_or_known_bad_count = int(spec_count + known_bad_count)
        evaluated_count = int(selected_result.get("candidate_count") or 0)
        safe_count = int(selected_result.get("safe_candidate_count") or 0)
        no_valid_repair_proven = bool(
            not selected
            and generated_or_known_bad_count > 0
            and evaluated_count >= spec_count
            and safe_count == 0
            and str(selected_result.get("selection_reason") or "").strip()
            in {
                "no_compliant_candidate_in_contract_ladder",
                "fallback_after_no_compliant_bending_contract_ladder_candidate",
            }
        )
        existing_blocked_proof = dict(
            dict(ladder.get("repair_reason_proof") or {}).get("blocked_ownership_proof") or {}
        )
        if no_valid_repair_proven:
            blocked_reason = (
                "all evaluated BENDING_FAIL_GOVERNS contract ladder candidates failed required checks"
            )
            blocked_ownership_proof = {
                **existing_blocked_proof,
                "family_id": "BENDING_FAIL_GOVERNS",
                "terminal_status": "REPAIR_BLOCKED",
                "repair_blocked": True,
                "blocked_reason": blocked_reason,
                "blocked_reason_source": "family_contract_blocker_proof",
                "internal_cap_only": False,
                "hard_blocker_proven": False,
                "contract_strategy_exhaustion_proven": True,
                "contract_strategies_checked": tuple(
                    existing_blocked_proof.get("contract_strategies_checked")
                    or ladder.get("contract_strategies_checked")
                    or NON_TERMINAL_LANES
                ),
                "contract_strategies_blocked": tuple(
                    existing_blocked_proof.get("contract_strategies_blocked")
                    or ladder.get("contract_strategies_blocked")
                    or ()
                ),
                "contract_strategies_remaining": (),
                "implementation_caps_hit": tuple(
                    existing_blocked_proof.get("implementation_caps_hit")
                    or ladder.get("implementation_caps_hit")
                    or ()
                ),
                "geometry_locks_used": tuple(
                    existing_blocked_proof.get("geometry_locks_used")
                    or ladder.get("geometry_locks_used")
                    or ()
                ),
                "project_constraints_used": tuple(
                    existing_blocked_proof.get("project_constraints_used")
                    or ladder.get("project_constraints_used")
                    or ()
                ),
                "detailing_constraints_used": tuple(
                    existing_blocked_proof.get("detailing_constraints_used")
                    or ladder.get("detailing_constraints_used")
                    or ()
                ),
                "evaluated_candidate_count": evaluated_count,
                "safe_candidate_count": safe_count,
                "generated_contract_candidate_count": spec_count,
                "known_bad_contract_candidate_count": known_bad_count,
                "checked_contract_candidate_count": generated_or_known_bad_count,
                "selection_reason": selected_result.get("selection_reason"),
            }
            repair_reason_proof = {
                **dict(ladder.get("repair_reason_proof") or {}),
                "proof_only": True,
                "selected_strategy_lane": "NO_VALID_STRATEGY",
                "blocked_ownership_proof": dict(blocked_ownership_proof),
                "repair_blocked": True,
                "internal_cap_only": False,
                "hard_blocker_proven": False,
                "contract_strategy_exhaustion_proven": True,
            }
        else:
            blocked_reason = ladder.get("blocked_reason")
            blocked_ownership_proof = existing_blocked_proof
            repair_reason_proof = dict(ladder.get("repair_reason_proof") or {})
        return {
            "governing_family": "BENDING_FAIL_GOVERNS",
            "family_name": "BENDING_FAIL_GOVERNS",
            "family_route_owner": self.metadata.owner,
            "family_candidate_strategy": self.metadata.candidate_strategy,
            "family_ranking_strategy": self.metadata.ranking_strategy,
            "family_evidence_strategy": self.metadata.evidence_strategy,
            "family_publication_rule": self.metadata.publication_rule,
            "family_cta_rule": self.metadata.cta_rule,
            "bending_fail_contract_ladder_used": True,
            "bending_fail_contract_ladder_candidate_count": spec_count,
            "bending_fail_contract_ladder_evaluated_candidate_count": evaluated_count,
            "bending_fail_contract_ladder_safe_candidate_count": safe_count,
            "bending_fail_contract_ladder_known_bad_candidate_count": known_bad_count,
            "bending_fail_contract_ladder_checked_candidate_count": generated_or_known_bad_count,
            "candidate_inventory_count": generated_or_known_bad_count,
            "attempted_candidate_count": evaluated_count or generated_or_known_bad_count,
            "safe_repair_candidate_count": safe_count,
            "executable_repair_candidate_count": safe_count,
            "safe_executor_backed_candidates_count": safe_count,
            "repair_search_ran": True,
            "repair_search_exhaustive": True,
            "candidate_search_ran": True,
            "candidate_search_exhaustive": True,
            "bending_fail_contract_ladder_selected_index": selected.get("bending_fail_ladder_index"),
            "bending_fail_contract_ladder_selected_step": selected.get("bending_fail_contract_step"),
            "bending_fail_contract_ladder_selected_stage": selected.get("bending_fail_stage_name"),
            "bending_fail_contract_ladder_first_successful_candidate_index": selected.get("bending_fail_ladder_index"),
            "bending_fail_contract_ladder_first_successful_stage": selected.get("bending_fail_stage_name"),
            "bending_fail_contract_ladder_stop_rule": ladder.get("ranking_rule"),
            "bending_fail_contract_ladder_stop_reason": selected_result.get("selection_reason"),
            "bending_fail_contract_ladder_bar_diameters": list(ladder.get("bar_diameters_tried") or []),
            "bending_fail_contract_ladder_depth_steps_mm": list(ladder.get("depth_steps_mm") or []),
            "bending_fail_contract_ladder_width_steps_mm": list(ladder.get("width_steps_mm") or []),
            "bending_fail_contract_ladder_minimum_clear_spacing_mm": ladder.get("minimum_clear_spacing_mm"),
            "bending_fail_contract_ladder_known_bad_candidate_count": ladder.get("known_bad_candidate_count"),
            "bending_fail_contract_terminal_status": (
                "REPAIR_BLOCKED" if no_valid_repair_proven else ladder.get("terminal_status")
            ),
            "bending_fail_repair_blocked": bool(no_valid_repair_proven or ladder.get("repair_blocked")),
            "bending_fail_blocked_reason": blocked_reason,
            "bending_fail_blocked_reason_source": (
                "family_contract_blocker_proof"
                if no_valid_repair_proven
                else ladder.get("blocked_reason_source")
            ),
            "bending_fail_internal_cap_only": False if no_valid_repair_proven else bool(ladder.get("internal_cap_only")),
            "bending_fail_hard_blocker_proven": bool(ladder.get("hard_blocker_proven")),
            "bending_fail_contract_strategy_exhaustion_proven": bool(
                no_valid_repair_proven or ladder.get("contract_strategy_exhaustion_proven")
            ),
            "bending_fail_contract_strategies_checked": list(
                blocked_ownership_proof.get("contract_strategies_checked")
                or ladder.get("contract_strategies_checked")
                or []
            ),
            "bending_fail_contract_strategies_blocked": list(
                blocked_ownership_proof.get("contract_strategies_blocked")
                or ladder.get("contract_strategies_blocked")
                or []
            ),
            "bending_fail_contract_strategies_remaining": list(
                blocked_ownership_proof.get("contract_strategies_remaining")
                if blocked_ownership_proof.get("contract_strategies_remaining") is not None
                else ladder.get("contract_strategies_remaining")
                or []
            ),
            "bending_fail_implementation_caps_hit": list(ladder.get("implementation_caps_hit") or []),
            "bending_fail_geometry_locks_used": list(ladder.get("geometry_locks_used") or []),
            "bending_fail_project_constraints_used": list(ladder.get("project_constraints_used") or []),
            "bending_fail_detailing_constraints_used": list(ladder.get("detailing_constraints_used") or []),
            "bending_fail_blocked_ownership_proof": dict(blocked_ownership_proof),
            "repair_reason_proof": dict(repair_reason_proof),
            "bending_fail_contract_ladder_selected_clear_spacing": selected.get("bending_fail_clear_spacing"),
            "bending_fail_contract_ladder_selected_b": selected.get("bending_fail_candidate_b"),
            "bending_fail_contract_ladder_selected_D": selected.get("bending_fail_candidate_D"),
            "bending_fail_contract_ladder_selected_bottom_bar_count": selected.get("bending_fail_bottom_bar_count"),
            "bending_fail_contract_ladder_selected_bar_diameter": selected.get("bending_fail_bar_diameter"),
            "bending_fail_contract_ladder_selected_split_row": selected.get("bending_fail_split_row"),
            "selected_candidate_updates": _updates_from(selected, {}),
            "generic_one_click_solver_skipped": True,
            "generic_target_band_search_skipped": True,
            "generic_optimisation_cleanup_skipped": True,
            "generic_publication_fallback_skipped": True,
            "repair_search_owner": self.metadata.owner,
        }

    def classify(self, context: FamilyStrategyContext) -> dict[str, Any]:
        _, _, summary, _, debug, classifier = _context_payload(context)
        active = _active_strength_failures(summary, debug, classifier)
        pure_bending = active == {"bending"}
        return {
            **self._adapter_header("classify", context),
            "active_failures": sorted(active),
            "bending_fail_identified": "bending" in active,
            "shear_fail_absent": "shear" not in active,
            "pure_bending_fail_identified": pure_bending,
            "fallback_required": not pure_bending,
            "missing_inputs": [] if summary or classifier else ["summary_or_classifier"],
            "unsupported_reason": None if pure_bending else "pure_bending_fail_not_active",
        }

    def generate_candidates(self, context: FamilyStrategyContext) -> dict[str, Any]:
        _, primary, _, _, debug, _ = _context_payload(context)
        updates = _updates_from(primary, debug)
        action_type = _action_type_from(primary, debug)
        return {
            **self._adapter_header("generate_candidates", context),
            "candidate_source": self.metadata.candidate_strategy,
            "existing_executor_payload_available": bool(updates and action_type == "apply_resolved_candidate"),
            "update_keys": sorted(str(key) for key in updates),
            "fallback_required": not bool(updates and action_type == "apply_resolved_candidate"),
            "missing_inputs": [] if updates else ["executor_backed_updates"],
        }

    def rank_candidates(self, context: FamilyStrategyContext, candidates: Any = None) -> dict[str, Any]:
        _, primary, _, evidence, debug, _ = _context_payload(context)
        candidate_id = (
            _button_contract(primary, debug).get("candidate_id")
            or _button_contract(primary, debug).get("source_candidate_id")
            or evidence.get("selected_candidate_id")
            or evidence.get("best_safe_candidate_id")
        )
        return {
            **self._adapter_header("rank_candidates", context),
            "ranking_source": self.metadata.ranking_strategy,
            "candidate_input_count": len(_as_list(candidates)) if isinstance(candidates, list) else None,
            "selected_candidate_id": candidate_id,
            "fallback_required": not bool(candidate_id),
            "missing_inputs": [] if candidate_id else ["selected_candidate_id"],
        }

    def build_evidence(self, context: FamilyStrategyContext, decision: Any = None) -> dict[str, Any]:
        _, primary, summary, evidence, debug, classifier = _context_payload(context)
        _ = decision
        active = _active_strength_failures(summary, debug, classifier)
        return {
            **self._adapter_header("build_evidence", context),
            "evidence_source": self.metadata.evidence_strategy,
            "active_failures": sorted(active),
            "repair_action_evidence_present": bool(_updates_from(primary, debug) and _action_type_from(primary, debug)),
            "repair_search_exhaustive": bool(evidence.get("repair_search_exhaustive") or evidence.get("candidate_search_exhaustive")),
            "fallback_required": not bool(evidence or _updates_from(primary, debug)),
            "missing_inputs": [] if evidence else ["candidate_search_evidence"],
        }

    def publish(self, context: FamilyStrategyContext, decision: Any = None) -> dict[str, Any]:
        _, primary, summary, _, debug, classifier = _context_payload(context)
        _ = decision
        active = _active_strength_failures(summary, debug, classifier)
        updates = _updates_from(primary, debug)
        action_type = _action_type_from(primary, debug)
        can_publish = bool(active == {"bending"} and updates and action_type == "apply_resolved_candidate")
        return {
            **self._adapter_header("publish", context),
            "publication_source": self.metadata.publication_rule,
            "publication_strategy_mode": "family_owned_bending_repair_payload",
            "visible_title": "Bending capacity is low",
            "active_failures": sorted(active),
            "can_publish_repair_action": can_publish,
            "fallback_required": not can_publish,
        }

    def get_cta_rule(self, context: FamilyStrategyContext, evidence: Any = None) -> dict[str, Any]:
        _, primary, _, _, debug, _ = _context_payload(context)
        _ = evidence
        updates = _updates_from(primary, debug)
        action_type = _action_type_from(primary, debug)
        return {
            **self._adapter_header("get_cta_rule", context),
            "cta_source": self.metadata.cta_rule,
            "cta_family_id": "BENDING_FAIL_GOVERNS",
            "enabled_when": "executor-backed apply_resolved_candidate payload exists and preview_pass is not false",
            "current_cta_executor_backed": bool(updates and action_type == "apply_resolved_candidate"),
            "current_update_keys": sorted(str(key) for key in updates),
            "creates_executable_cta": False,
            "fallback_required": not bool(updates and action_type == "apply_resolved_candidate"),
        }

    def _adapter_header(self, operation: str, context: FamilyStrategyContext) -> dict[str, Any]:
        return {
            "family_name": "BENDING_FAIL_GOVERNS",
            "governing_state": self.metadata.governing_state,
            "adapter_version": ADAPTER_VERSION,
            "operation": operation,
            "owner": self.metadata.owner,
            "product_routing_enabled": False,
            "existing_logic_wrapped": {
                "classification": "read-only active bending/shear failure summary fields",
                "candidate": "existing executor-backed bending repair payload is inspected, not invoked",
                "ranking": "existing selected candidate identity is inspected",
                "evidence": "existing repair/evidence maps are inspected",
                "publication": "existing visible bending repair output is described",
                "cta": "existing button contract is inspected",
            },
            "mutates_product_state": False,
            "calls_ui_or_session_state": False,
            "changes_candidate_selection": False,
            "changes_publication": False,
            "creates_executable_cta": False,
            "context_governing_state": context.governing_state,
            "read_only": True,
        }


__all__ = ["BendingFailFamily"]
