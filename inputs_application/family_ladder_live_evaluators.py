"""Live full-engineering adapters for Design Brain family ladder runtimes.

The family runtimes own candidate order, ranking, exact-stop and exhaustion.
This application adapter supplies the one thing they must not fake in product
routing: evaluation by the authoritative full engineering candidate service.
"""

from __future__ import annotations

from typing import Any, Callable

from inputs_application.legacy_design_brain_adapter import (
    BendingOverdesignCandidateEvaluation,
    BendingOverdesignCandidateInput,
    BendingOverdesignCandidateUpdate,
    build_bending_overdesign_candidate_state_hash,
)
from inputs_application.legacy_design_brain_adapter import (
    ServiceabilityCandidateEvaluation,
    ServiceabilityCandidateInput,
    ServiceabilityCandidateUpdate,
    build_serviceability_candidate_state_hash,
)
from inputs_application.legacy_design_brain_adapter import (
    ShearOverdesignCandidateEvaluation,
    ShearOverdesignCandidateInput,
    ShearOverdesignCandidateUpdate,
    build_shear_overdesign_candidate_state_hash,
)
from inputs_application.legacy_design_brain_adapter import (
    ShearFailBendingOverdesignEvaluation,
    ShearFailBendingOverdesignCandidate,
    ShearFailBendingOverdesignInputs,
    shear_fail_bending_overdesign_state_hash,
)
from inputs_application.legacy_design_brain_adapter import (
    BendingFailShearOverdesignInputs,
    BendingFailShearOverdesignEvaluation,
    BendingFailShearOverdesignCandidate,
    bending_fail_shear_overdesign_state_hash,
)
from inputs_application.legacy_design_brain_adapter import (
    CombinedOverdesignCandidateEvaluation,
    CombinedOverdesignInputs,
    CombinedOverdesignMergedCandidate,
    combined_overdesign_candidate_state_hash,
)


FullCandidateEvaluator = Callable[..., dict[str, Any] | None]


def serviceability_updates_to_app_updates(
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    """Translate the family contract's nested state into canonical app keys."""

    source = dict(updates or {})
    app_updates = {
        key: value
        for key, value in source.items()
        if key not in {"geometry", "reinforcement"}
    }
    geometry = dict(source.get("geometry") or {})
    reinforcement = dict(source.get("reinforcement") or {})
    if "beam_depth_mm" in geometry:
        app_updates["D"] = geometry["beam_depth_mm"]
    if "beam_width_mm" in geometry:
        app_updates["b"] = geometry["beam_width_mm"]
    if "bottom_bar_count" in reinforcement:
        app_updates["bot1_count"] = reinforcement["bottom_bar_count"]
    return app_updates


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _status_failed(value: Any) -> bool:
    return str(value or "").strip().upper() in {"FAIL", "FAILED", "ERROR"}


def _distance_to_band(value: float | None, low: float = 0.85, high: float = 1.0) -> float:
    if value is None:
        return float("inf")
    if value < low:
        return low - value
    if value > high:
        return value - high
    return 0.0


def _run_full_candidate(
    evaluate_full: FullCandidateEvaluator,
    base_state: dict[str, Any],
    updates: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    trial_state = dict(base_state or {})
    trial_state.update(dict(updates or {}))
    result = evaluate_full(
        trial_state,
        updates=dict(updates or {}),
        source=source,
        label=source,
        action_type="apply_resolved_candidate",
    )
    return dict(result or {}) if isinstance(result, dict) else {}


def build_bending_overdesign_live_evaluator(
    evaluate_full: FullCandidateEvaluator,
    *,
    ignore_existing_failures: tuple[str, ...] = (),
) -> Callable[
    [BendingOverdesignCandidateInput, BendingOverdesignCandidateUpdate],
    BendingOverdesignCandidateEvaluation,
]:
    def evaluate(
        candidate_input: BendingOverdesignCandidateInput,
        candidate_update: BendingOverdesignCandidateUpdate,
    ) -> BendingOverdesignCandidateEvaluation:
        base = dict(candidate_input.base_state or {})
        updates = dict(candidate_update.updates or {})
        full = _run_full_candidate(
            evaluate_full,
            base,
            updates,
            source="bending_overdesign_family_ladder",
        )
        overview = dict(full.get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        utils = dict(overview.get("utils") or {})
        bending = dict(full.get("bending") or {})
        util = _number(utils.get("bending"))
        previous = _number(
            base.get("bending_utilisation")
            or base.get("bending_util")
            or base.get("Mu_util")
        )
        as_after = _number(
            full.get("Ast_bot")
            or bending.get("Ast_bot")
            or bending.get("As")
            or (overview.get("packs") or {}).get("bending", {}).get("Ast_bot")
        )
        as_min = _number(
            bending.get("As_min")
            or (overview.get("packs") or {}).get("bending", {}).get("As_min")
        )
        bending_ok = bool(
            util is not None
            and util <= 1.0 + 1e-9
            and not _status_failed(statuses.get("bending"))
        )
        ignored = {str(key).strip().lower() for key in ignore_existing_failures}
        remaining_failures = {
            str(key).strip().lower()
            for key, value in statuses.items()
            if _status_failed(value) and str(key).strip().lower() not in ignored
        }
        all_ok = bool(full and not remaining_failures)
        minimum_ok = bool(
            as_after is None
            or as_min is None
            or as_after + 1e-9 >= as_min
        )
        geometry_after = dict(base)
        geometry_after.update(updates)
        width = _number(
            geometry_after.get("b")
            or geometry_after.get("bw")
            or geometry_after.get("beam_width")
        )
        depth = _number(
            geometry_after.get("D")
            or geometry_after.get("beam_depth")
        )
        candidate_valid = bool(
            all_ok
            and bending_ok
            and minimum_ok
            and candidate_update.bending_overdesign_update
        )
        result = BendingOverdesignCandidateEvaluation(
            input_hash=candidate_input.input_hash,
            update_hash=candidate_update.update_hash,
            candidate_state_hash=build_bending_overdesign_candidate_state_hash(base, updates),
            bending_utilisation=util,
            previous_bending_utilisation=previous,
            target_band_status={"inside_target_band": bool(util is not None and 0.85 <= util <= 1.0)},
            utilisation_moves_toward_target=bool(
                util is not None
                and (
                    previous is None
                    or _distance_to_band(util) <= _distance_to_band(previous) + 1e-9
                )
            ),
            bending_remains_compliant=bending_ok,
            constructability_status={"status": "PASS" if all_ok else "FAIL", "source": "full_candidate_overview"},
            code_compliance_status={"status": "PASS" if all_ok else "FAIL", "statuses": statuses},
            minimum_reinforcement_status={
                "As": as_after,
                "As_min": as_min,
                "As_greater_than_or_equal_to_As_min": minimum_ok,
                "discard_before_ranking": not minimum_ok,
            },
            geometry_compliance_status={"status": "PASS" if all_ok else "FAIL"},
            beam_proportion_status={"status": "PASS" if all_ok else "FAIL"},
            reinforcement_quantity={"after": as_after},
            beam_volume={"after": width * depth if width is not None and depth is not None else None},
            cost_proxy={"after": width * depth if width is not None and depth is not None else None},
            capacity_summary=overview,
            failure_flags={
                "underdesign_created": not bending_ok,
                "below_minimum_reinforcement": not minimum_ok,
            },
            engineering_status={
                "candidate_valid": candidate_valid,
                "result": "ACCEPTED" if candidate_valid else "REJECTED",
                "source": "evaluate_candidate_full",
            },
        )
        return result.with_evaluation_hash()

    return evaluate


def build_shear_overdesign_live_evaluator(
    evaluate_full: FullCandidateEvaluator,
    *,
    ignore_existing_failures: tuple[str, ...] = (),
) -> Callable[
    [ShearOverdesignCandidateInput, ShearOverdesignCandidateUpdate],
    ShearOverdesignCandidateEvaluation,
]:
    def evaluate(
        candidate_input: ShearOverdesignCandidateInput,
        candidate_update: ShearOverdesignCandidateUpdate,
    ) -> ShearOverdesignCandidateEvaluation:
        base = dict(candidate_input.base_state or {})
        updates = dict(candidate_update.updates or {})
        full = _run_full_candidate(
            evaluate_full,
            base,
            updates,
            source="shear_overdesign_family_ladder",
        )
        overview = dict(full.get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        utils = dict(overview.get("utils") or {})
        shear_util = _number(utils.get("shear"))
        bending_util = _number(utils.get("bending"))
        previous_shear = _number(base.get("shear_utilisation") or base.get("shear_util"))
        previous_bending = _number(base.get("bending_utilisation") or base.get("bending_util"))
        ignored = {str(key).strip().lower() for key in ignore_existing_failures}
        remaining_failures = {
            str(key).strip().lower()
            for key, value in statuses.items()
            if _status_failed(value) and str(key).strip().lower() not in ignored
        }
        all_ok = bool(full and not remaining_failures)
        shear_ok = bool(
            shear_util is not None
            and shear_util <= 1.0 + 1e-9
            and not _status_failed(statuses.get("shear"))
        )
        removes_links = bool(
            updates.get("lig_d") == 0 and updates.get("lig_legs") == 0
        )
        base_width = _number(base.get("b") or base.get("bw") or base.get("beam_width"))
        width_after = _number(
            updates.get("b")
            or updates.get("bw")
            or updates.get("beam_width")
            or base_width
        )
        candidate_valid = bool(
            all_ok
            and shear_ok
            and candidate_update.contract_allowed_update
            and not candidate_update.geometry_reduction_attempted
        )
        result = ShearOverdesignCandidateEvaluation(
            input_hash=candidate_input.input_hash,
            update_hash=candidate_update.update_hash,
            candidate_state_hash=build_shear_overdesign_candidate_state_hash(base, updates),
            shear_utilisation=shear_util,
            previous_shear_utilisation=previous_shear,
            target_band_status={"inside_target_band": bool(shear_util is not None and 0.85 <= shear_util <= 1.0)},
            utilisation_moves_toward_target=bool(
                shear_util is not None
                and (
                    previous_shear is None
                    or _distance_to_band(shear_util) <= _distance_to_band(previous_shear) + 1e-9
                )
            ),
            shear_remains_compliant=shear_ok,
            constructability_status={"status": "PASS" if all_ok else "FAIL"},
            mandatory_detailing_status={"status": "PASS" if all_ok else "FAIL"},
            shear_detailing_update_status={
                "shear_detailing_only": candidate_update.shear_detailing_only,
                "contract_update_allowed": candidate_update.contract_allowed_update,
                "update_keys": candidate_update.update_keys,
            },
            geometry_restriction_status={
                "geometry_reduction_attempted": candidate_update.geometry_reduction_attempted,
                "depth_reduction_prohibited": True,
                "width_reduction_allowed": True,
            },
            width_reduction_status={
                "width_before": base_width,
                "width_after": width_after,
                "width_reduction_attempted": candidate_update.width_reduction_attempted,
                "width_locked": False,
                "next_width_blocker": None if candidate_valid else "full_engineering_candidate_rejected",
            },
            bending_utilisation=bending_util,
            previous_bending_utilisation=previous_bending,
            reinforcement_fit_status={"status": "PASS" if all_ok else "FAIL"},
            serviceability_status={
                "status": "FAIL"
                if _status_failed(statuses.get("deflection"))
                or _status_failed(statuses.get("crack"))
                else "PASS"
            },
            crack_control_status={"status": statuses.get("crack")},
            zero_shear_status={
                "zero_or_negligible_shear": bool(shear_util is not None and abs(shear_util) <= 1e-12),
                "must_not_terminate_for_zero_utilisation": True,
            },
            ligature_removal_status={"no_unnecessary_ligatures_remain": removes_links},
            reinforcement_quantity={
                "after": 0.0 if removes_links else _number(updates.get("lig_legs") or base.get("lig_legs"))
            },
            cost_proxy={"after": width_after},
            capacity_summary=overview,
            failure_flags={"underdesign_created": not shear_ok},
            engineering_status={
                "candidate_valid": candidate_valid,
                "result": "ACCEPTED" if candidate_valid else "REJECTED",
                "source": "evaluate_candidate_full",
            },
        )
        return result.with_evaluation_hash()

    return evaluate


def build_serviceability_live_evaluator(
    evaluate_candidate: FullCandidateEvaluator,
    *,
    evaluation_source: str = "evaluate_candidate_full",
) -> Callable[
    [ServiceabilityCandidateInput, ServiceabilityCandidateUpdate],
    ServiceabilityCandidateEvaluation,
]:
    def evaluate(
        candidate_input: ServiceabilityCandidateInput,
        candidate_update: ServiceabilityCandidateUpdate,
    ) -> ServiceabilityCandidateEvaluation:
        base = dict(candidate_input.base_state or {})
        updates = serviceability_updates_to_app_updates(candidate_update.updates)
        full = _run_full_candidate(
            evaluate_candidate,
            base,
            updates,
            source="serviceability_family_ladder",
        )
        overview = dict(full.get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        utils = dict(overview.get("utils") or {})
        crack_util = _number(utils.get("crack"))
        deflection_util = _number(utils.get("deflection"))
        serviceability_values = [
            value for value in (crack_util, deflection_util) if value is not None
        ]
        serviceability_util = max(serviceability_values) if serviceability_values else None
        previous = _number(base.get("serviceability_utilisation"))
        serviceability_ok = bool(
            serviceability_util is not None
            and serviceability_util <= 1.0 + 1e-9
            and not _status_failed(statuses.get("crack"))
            and not _status_failed(statuses.get("deflection"))
        )
        strength_ok = bool(
            not _status_failed(statuses.get("bending"))
            and not _status_failed(statuses.get("shear"))
        )
        all_ok = bool(full and overview.get("all_key_pass") and not overview.get("any_fail"))
        candidate_valid = bool(all_ok and serviceability_ok and strength_ok)
        result = ServiceabilityCandidateEvaluation(
            input_hash=candidate_input.input_hash,
            update_hash=candidate_update.update_hash,
            candidate_state_hash=build_serviceability_candidate_state_hash(base, updates),
            serviceability_utilisation=serviceability_util,
            previous_serviceability_utilisation=previous,
            serviceability_improved=bool(
                serviceability_util is not None
                and (previous is None or serviceability_util < previous - 1e-9)
            ),
            serviceability_compliant=serviceability_ok,
            deflection_status={"status": statuses.get("deflection"), "utilisation": deflection_util},
            crack_control_status={"status": statuses.get("crack"), "utilisation": crack_util},
            strength_status={"status": "PASS" if strength_ok else "FAIL"},
            code_compliance_status={"status": "PASS" if all_ok else "FAIL", "statuses": statuses},
            constructability_status={"status": "PASS" if all_ok else "FAIL"},
            geometry_status={"status": "PASS" if all_ok else "FAIL"},
            reinforcement_status={"status": "PASS" if all_ok else "FAIL"},
            blocker_status={"blocked": not candidate_valid},
            capacity_summary=overview,
            failure_flags={
                "serviceability_failure": not serviceability_ok,
                "strength_failure": not strength_ok,
            },
            engineering_status={
                "candidate_valid": candidate_valid,
                "result": "ACCEPTED" if candidate_valid else "REJECTED",
                "source": str(evaluation_source),
            },
        )
        return result.with_evaluation_hash()

    return evaluate


def build_shear_fail_bending_overdesign_live_evaluator(
    evaluate_full: FullCandidateEvaluator,
) -> Callable[
    [ShearFailBendingOverdesignInputs, ShearFailBendingOverdesignCandidate],
    ShearFailBendingOverdesignEvaluation,
]:
    def evaluate(
        inputs: ShearFailBendingOverdesignInputs,
        candidate: ShearFailBendingOverdesignCandidate,
    ) -> ShearFailBendingOverdesignEvaluation:
        base = dict(inputs.base_state or {})
        updates = dict(candidate.updates or {})
        full = _run_full_candidate(
            evaluate_full,
            base,
            updates,
            source="shear_fail_bending_overdesign_family_ladder",
        )
        overview = dict(full.get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        utils = dict(overview.get("utils") or {})
        bending_after = _number(utils.get("bending"))
        shear_after = _number(utils.get("shear"))
        bending_before = _number(base.get("bending_utilisation"))
        shear_before = _number(base.get("shear_utilisation"))
        bending_ok = not _status_failed(statuses.get("bending")) and bool(
            bending_after is not None and bending_after <= 1.0 + 1e-9
        )
        shear_ok = not _status_failed(statuses.get("shear")) and bool(
            shear_after is not None and shear_after <= 1.0 + 1e-9
        )
        candidate_valid = bool(
            full
            and overview.get("all_key_pass")
            and not overview.get("any_fail")
            and bending_ok
            and shear_ok
        )
        result = ShearFailBendingOverdesignEvaluation(
            input_hash=inputs.input_hash,
            update_hash=candidate.update_hash,
            candidate_state_hash=shear_fail_bending_overdesign_state_hash(base, updates),
            source_family_ids=candidate.source_families,
            source_candidates=tuple(
                source.candidate_id for source in candidate.source_candidates
            ),
            bending_utilisation_before=bending_before,
            shear_utilisation_before=shear_before,
            bending_utilisation_after=bending_after,
            shear_utilisation_after=shear_after,
            shear_repaired=shear_ok,
            bending_compliant=bending_ok,
            bending_inside_target_band=bool(
                bending_after is not None and 0.85 <= bending_after <= 1.0
            ),
            shear_inside_target_band=bool(
                shear_after is not None and 0.85 <= shear_after <= 1.0
            ),
            bending_moves_toward_target=(
                _distance_to_band(bending_after) < _distance_to_band(bending_before)
            ),
            creates_bending_underdesign=not bending_ok,
            code_compliance_status={"status": "PASS" if candidate_valid else "FAIL"},
            constructability_status={"status": "PASS" if candidate_valid else "FAIL"},
            geometry_interaction_status=dict(candidate.interaction_flags),
            reinforcement_interaction_status=dict(candidate.interaction_flags),
            reinforcement_quantity={"increase": len(updates)},
            beam_volume={
                "geometry_increase": sum(
                    1 for key in ("b", "D") if key in updates
                )
            },
            cost_proxy={"after": len(updates)},
            engineering_status={
                "candidate_valid": candidate_valid,
                "source": "evaluate_candidate_full",
            },
        )
        return result.with_evaluation_hash()

    return evaluate


def build_bending_fail_shear_overdesign_live_evaluator(
    evaluate_full: FullCandidateEvaluator,
) -> Callable[
    [BendingFailShearOverdesignInputs, BendingFailShearOverdesignCandidate],
    BendingFailShearOverdesignEvaluation,
]:
    def evaluate(
        inputs: BendingFailShearOverdesignInputs,
        candidate: BendingFailShearOverdesignCandidate,
    ) -> BendingFailShearOverdesignEvaluation:
        base = dict(inputs.base_state or {})
        updates = dict(candidate.updates or {})
        full = _run_full_candidate(
            evaluate_full,
            base,
            updates,
            source="bending_fail_shear_overdesign_family_ladder",
        )
        overview = dict(full.get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        utils = dict(overview.get("utils") or {})
        bending_after = _number(utils.get("bending"))
        shear_after = _number(utils.get("shear"))
        bending_before = _number(base.get("bending_utilisation"))
        shear_before = _number(base.get("shear_utilisation"))
        bending_ok = not _status_failed(statuses.get("bending")) and bool(
            bending_after is not None and bending_after <= 1.0 + 1e-9
        )
        shear_ok = not _status_failed(statuses.get("shear")) and bool(
            shear_after is not None and shear_after <= 1.0 + 1e-9
        )
        candidate_valid = bool(
            full
            and overview.get("all_key_pass")
            and not overview.get("any_fail")
            and bending_ok
            and shear_ok
        )
        result = BendingFailShearOverdesignEvaluation(
            input_hash=inputs.input_hash,
            update_hash=candidate.update_hash,
            candidate_state_hash=bending_fail_shear_overdesign_state_hash(base, updates),
            source_family_ids=candidate.source_families,
            source_candidates=tuple(
                source.candidate_id for source in candidate.source_candidates
            ),
            bending_utilisation_before=bending_before,
            shear_utilisation_before=shear_before,
            bending_utilisation_after=bending_after,
            shear_utilisation_after=shear_after,
            bending_repaired=bending_ok,
            shear_compliant=shear_ok,
            bending_inside_target_band=bool(
                bending_after is not None and 0.85 <= bending_after <= 1.0
            ),
            shear_inside_target_band=bool(
                shear_after is not None and 0.85 <= shear_after <= 1.0
            ),
            shear_moves_toward_target=(
                _distance_to_band(shear_after) < _distance_to_band(shear_before)
            ),
            creates_shear_underdesign=not shear_ok,
            code_compliance_status={"status": "PASS" if candidate_valid else "FAIL"},
            constructability_status={"status": "PASS" if candidate_valid else "FAIL"},
            geometry_interaction_status=dict(candidate.interaction_flags),
            reinforcement_interaction_status=dict(candidate.interaction_flags),
            reinforcement_quantity={"increase": len(updates)},
            beam_volume={
                "geometry_increase": sum(
                    1 for key in ("b", "D") if key in updates
                )
            },
            cost_proxy={"after": len(updates)},
            engineering_status={
                "candidate_valid": candidate_valid,
                "source": "evaluate_candidate_full",
            },
        )
        return result.with_evaluation_hash()

    return evaluate


def build_combined_overdesign_live_evaluator(
    evaluate_full: FullCandidateEvaluator,
) -> Callable[
    [CombinedOverdesignInputs, CombinedOverdesignMergedCandidate],
    CombinedOverdesignCandidateEvaluation,
]:
    def evaluate(
        inputs: CombinedOverdesignInputs,
        candidate: CombinedOverdesignMergedCandidate,
    ) -> CombinedOverdesignCandidateEvaluation:
        base = dict(inputs.base_state or {})
        updates = dict(candidate.updates or {})
        full = _run_full_candidate(
            evaluate_full,
            base,
            updates,
            source="combined_overdesign_family_ladder",
        )
        overview = dict(full.get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        utils = dict(overview.get("utils") or {})
        bending_after = _number(utils.get("bending"))
        shear_after = _number(utils.get("shear"))
        bending_before = _number(base.get("bending_utilisation"))
        shear_before = _number(base.get("shear_utilisation"))
        bending_ok = not _status_failed(statuses.get("bending")) and bool(
            bending_after is not None and bending_after <= 1.0 + 1e-9
        )
        shear_ok = not _status_failed(statuses.get("shear")) and bool(
            shear_after is not None and shear_after <= 1.0 + 1e-9
        )
        candidate_valid = bool(
            full
            and overview.get("all_key_pass")
            and not overview.get("any_fail")
            and bending_ok
            and shear_ok
        )
        bending = dict(full.get("bending") or {})
        as_after = _number(bending.get("Ast_bot") or bending.get("As"))
        as_min = _number(bending.get("As_min"))
        minimum_ok = bool(
            as_after is None or as_min is None or as_after + 1e-9 >= as_min
        )
        result = CombinedOverdesignCandidateEvaluation(
            input_hash=inputs.input_hash,
            update_hash=candidate.update_hash,
            candidate_state_hash=combined_overdesign_candidate_state_hash(base, updates),
            source_family_ids=candidate.source_families,
            source_candidates=tuple(
                source.candidate_id for source in candidate.source_candidates
            ),
            bending_utilisation_before=bending_before,
            shear_utilisation_before=shear_before,
            bending_utilisation_after=bending_after,
            shear_utilisation_after=shear_after,
            bending_moves_toward_target=(
                _distance_to_band(bending_after) <= _distance_to_band(bending_before)
            ),
            shear_moves_toward_target=(
                _distance_to_band(shear_after) <= _distance_to_band(shear_before)
            ),
            bending_compliant=bending_ok,
            shear_compliant=shear_ok,
            bending_inside_target_band=bool(
                bending_after is not None and 0.85 <= bending_after <= 1.0
            ),
            shear_inside_target_band=bool(
                shear_after is not None and 0.85 <= shear_after <= 1.0
            ),
            creates_bending_underdesign=not bending_ok,
            creates_shear_underdesign=not shear_ok,
            minimum_reinforcement_status={
                "As": as_after,
                "As_min": as_min,
                "As_greater_than_or_equal_to_As_min": minimum_ok,
                "status": "PASS" if minimum_ok else "FAIL",
            },
            zero_shear_status={
                "zero_shear": bool(shear_after is not None and abs(shear_after) <= 1e-12)
            },
            geometry_interaction_status=dict(candidate.interaction_flags),
            reinforcement_interaction_status=dict(candidate.interaction_flags),
            code_compliance_status={"status": "PASS" if candidate_valid else "FAIL"},
            detailing_status={"status": "PASS" if candidate_valid else "FAIL"},
            constructability_status={"status": "PASS" if candidate_valid else "FAIL"},
            reinforcement_quantity={"after": len(updates)},
            beam_volume={"after": None},
            cost_proxy={"after": len(updates)},
            engineering_status={
                "candidate_valid": candidate_valid and minimum_ok,
                "source": "evaluate_candidate_full",
            },
        )
        return result.with_evaluation_hash()

    return evaluate


__all__ = [
    "FullCandidateEvaluator",
    "build_bending_overdesign_live_evaluator",
    "build_bending_fail_shear_overdesign_live_evaluator",
    "build_serviceability_live_evaluator",
    "build_combined_overdesign_live_evaluator",
    "build_shear_fail_bending_overdesign_live_evaluator",
    "build_shear_overdesign_live_evaluator",
    "serviceability_updates_to_app_updates",
]
