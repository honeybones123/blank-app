"""Diagnostic adapter for the shear active-fail governing family.

This module exposes the strategy shape for `SHEAR_FAIL_GOVERNS` without routing
product behaviour through the family layer. It inspects already-computed
payloads/evidence only; it does not import `inputs_page`, generate candidates,
publish cards, create CTAs, or touch Streamlit/session state.
"""

from __future__ import annotations

from typing import Any

from design_brain.evidence import repair_search_exhaustive
from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyContext, FamilyStrategyMetadata
from design_brain.families.shear_fail_governs.repair_ladder import (
    DEFAULT_WIDTH_STEP_MM,
    PREFERRED_MINIMUM_SPACING_MM,
    build_shear_fail_diameter_ladder as _diameter_ladder,
    dedupe_shear_fail_repair_specs as _dedupe_repair_specs,
    build_shear_fail_normalised_update_diff as _normalised_update_diff,
    build_shear_fail_repair_ladder_evidence_overlay as _repair_ladder_evidence_overlay,
    build_shear_fail_repair_ladder_spec_payload as _repair_ladder_spec_payload,
    build_shear_fail_spacing_ladder as _spacing_ladder,
    build_shear_fail_width_ladder as _width_ladder,
    build_shear_fail_candidate_rows as _build_candidate_rows,
    build_shear_fail_exact_blockers as _build_exact_blockers,
    find_promotable_shear_fail_repair_candidate as _find_promotable_shear_repair_candidate,
    is_safe_shear_fail_executor_backed as _is_safe_shear_fail_executor_backed,
    is_shear_fail_candidate as _is_shear_fail_candidate,
    select_shear_fail_repair_candidate_from_ladder as _select_repair_candidate_from_ladder,
    shear_fail_active_failures as _extract_active_failures,
    shear_fail_candidate_id as _extract_candidate_id,
    shear_fail_candidate_updates as _shear_fail_candidate_updates,
    shear_fail_state_float as _coerce_state_float,
    shear_fail_state_int as _coerce_state_int,
    shear_fail_status as _extract_shear_status,
    shear_fail_util as _extract_shear_util,
)
from design_brain.families.shear_fail_governs.route_decision import (
    build_shear_fail_route_success_result as _build_route_success_result,
)
from design_brain.families.shear_fail_governs.runtime import (
    run_shear_fail_governs_ladder_runtime as _run_contract_runtime,
)
from design_brain.governing_state import classify_governing_state
from design_brain.shear_candidate_evaluation import (
    ShearCandidateEvaluation,
    ShearCandidateInput,
    ShearCandidateUpdate,
    build_shear_candidate_state_hash,
)


ADAPTER_VERSION = "shear_fail_adapter.v2"
DEFAULT_REO_SPACINGS = (75.0, 100.0, 125.0, 150.0, 175.0, 200.0, 225.0, 250.0, 275.0, 300.0)
DEFAULT_LIG_DIAMETERS = (10, 12, 16, 20, 24, 28, 32, 36, 40)

_REQUIRED_METHODS = (
    "classify",
    "generate_candidates",
    "rank_candidates",
    "build_evidence",
    "publish",
    "get_cta_rule",
)

_POSITIVE_EXPECTATIONS = (
    "shear failure identified",
    "repair ACTION or explicit FAIL/no-repair evidence",
    "single primary CTA if actionable",
)

_NEGATIVE_EXPECTATIONS = (
    "PASS terminal state",
    "Design is efficient",
    "BLOCKED cleanup",
    "blank Design Guide",
    "frozen Design Guide",
    "duplicate CTA",
    "stale previous outcome",
    "debug/probe output in normal mode",
)

_STALE_BLOCKER_KEYS = (
    "exact_blockers_by_family",
    "post_click_exact_blockers_by_family",
    "cleanup_evidence_by_family",
    "post_click_cleanup_evidence_by_family",
    "blocker_attempts_by_family",
    "local_cleanup_blocked_reasons",
    "local_cleanup_blocked_reasons_by_family",
)


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_status(value: Any) -> str:
    return str(value or "").strip().upper()


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
            or debug.get("local_cleanup_candidate_search_evidence")
        )
    classifier = _as_dict(context.classifier)
    if not classifier:
        classifier = _as_dict(
            _as_dict(payload.get("design_brain_result")).get("governing_state_classifier")
            or debug.get("governing_state_classifier")
        )
    return payload, primary, summary, evidence, debug, classifier


def _button_contract(primary: dict, debug: dict) -> dict:
    return _as_dict(
        primary.get("button_contract")
        or debug.get("displayed_primary_button_contract")
        or debug.get("primary_button_contract")
        or debug.get("button_contract")
    )


def _active_failures(summary: dict, evidence: dict, debug: dict, classifier: dict) -> list[str]:
    return _extract_active_failures(summary, evidence, debug, classifier)


def _shear_status(summary: dict, evidence: dict, debug: dict) -> str:
    return _extract_shear_status(summary, evidence, debug)


def _shear_util(summary: dict, evidence: dict, debug: dict) -> float | None:
    return _extract_shear_util(summary, evidence, debug)


def _candidate_id(row: dict, index: int) -> str:
    return _extract_candidate_id(row, index)


def _candidate_updates(row: dict) -> dict:
    return _shear_fail_candidate_updates(row)


def _state_float(state: dict, key: str, default: float) -> float:
    return _coerce_state_float(state, key, default)


def _state_int(state: dict, key: str, default: int) -> int:
    return _coerce_state_int(state, key, default)


def _dedupe_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _dedupe_repair_specs(specs)


def _is_shear_candidate(row: dict) -> bool:
    return _is_shear_fail_candidate(row)


def _safe_executor_backed(row: dict) -> bool:
    return _is_safe_shear_fail_executor_backed(row)


def _promotable_shear_repair_candidate(evidence: dict) -> dict:
    rows = _candidate_rows(evidence)
    return _find_promotable_shear_repair_candidate(evidence, rows)


def _candidate_rows(evidence: dict) -> list[dict]:
    return _build_candidate_rows(evidence)


def _exact_blockers(evidence: dict, primary: dict, debug: dict) -> dict:
    return _build_exact_blockers(evidence, primary, debug)


_RUNTIME_CONTRACT_STEP_BY_LANE = {
    "SPACING_REDUCTION": 1,
    "BAR_SIZE_INCREASE": 2,
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH": 3,
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH": 4,
    "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH": 5,
    "EXACT_STOP": 6,
    "EXHAUSTED": 7,
    "NO_VALID_REPAIR": 8,
}


def _runtime_rejecting_evaluator(
    candidate_input: ShearCandidateInput,
    candidate_update: ShearCandidateUpdate,
) -> ShearCandidateEvaluation:
    return ShearCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_shear_candidate_state_hash(candidate_input.base_state, candidate_update.updates),
        shear_utilisation=1.2,
        previous_shear_utilisation=1.2,
        utilisation_improved=False,
        code_compliance_status={"overall": "FAIL"},
        constructability_status={"overall": "CHECKED"},
        spacing_status={"status": "CHECKED"},
        bar_size_status={"status": "CHECKED"},
        leg_count_status={"status": "CHECKED"},
        geometry_status={"status": "CHECKED"},
        capacity_summary={"adapter": "contract_runtime_spec_generation"},
        failure_flags={"shear_fail": True},
        engineering_status={"overall": "FAIL", "target_band_status": "FAIL"},
    ).with_evaluation_hash()


def _flatten_runtime_shear_update(update: dict, *, width_key: str) -> dict[str, Any]:
    update_d = _as_dict(update)
    geometry = _as_dict(update_d.get("geometry"))
    reinforcement = _as_dict(update_d.get("reinforcement"))
    flat: dict[str, Any] = {}
    if "beam_depth_mm" in geometry:
        flat["D"] = float(geometry.get("beam_depth_mm"))
    if "beam_width_mm" in geometry:
        width = float(geometry.get("beam_width_mm"))
        flat[width_key] = width
        if width_key != "b":
            flat["b"] = width
    if "ligature_spacing_mm" in reinforcement:
        flat["s_lig"] = float(reinforcement.get("ligature_spacing_mm"))
    if "ligature_diameter_mm" in reinforcement:
        flat["lig_d"] = int(reinforcement.get("ligature_diameter_mm"))
    if "ligature_leg_count" in reinforcement:
        flat["lig_legs"] = int(reinforcement.get("ligature_leg_count"))
    return flat


def _runtime_strategy_label(record: dict) -> str:
    lane_id = str(record.get("lane_id") or "")
    updates = _as_dict(record.get("updates"))
    geometry = _as_dict(updates.get("geometry"))
    reinforcement = _as_dict(updates.get("reinforcement"))
    if lane_id == "SPACING_REDUCTION":
        return f"reduce spacing to {float(reinforcement.get('ligature_spacing_mm') or 0):.0f} mm"
    if lane_id == "BAR_SIZE_INCREASE":
        return (
            f"increase lig diameter to {int(reinforcement.get('ligature_diameter_mm') or 0)} "
            f"and restart spacing at {float(reinforcement.get('ligature_spacing_mm') or 0):.0f} mm"
        )
    if lane_id == "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH":
        return (
            f"increase depth to {float(geometry.get('beam_depth_mm') or 0):.0f} mm "
            f"and restart shear reinforcement search"
        )
    if lane_id == "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH":
        return (
            f"increase width to {float(geometry.get('beam_width_mm') or 0):.0f} mm "
            f"and restart shear reinforcement search"
        )
    if lane_id == "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH":
        return (
            f"increase lig legs to {int(reinforcement.get('ligature_leg_count') or 0)} "
            f"and restart spacing at {float(reinforcement.get('ligature_spacing_mm') or 0):.0f} mm"
        )
    return lane_id.lower()


class ShearFailFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="SHEAR_FAIL_GOVERNS",
        owner="design_brain.families.shear_fail.ShearFailFamily",
        candidate_strategy="contracted_spacing_first_shear_repair_ladder",
        ranking_strategy="contract_ladder_first_compliant_repair",
        evidence_strategy="family_owned_shear_repair_ladder_evidence",
        publication_rule="shear_fail_repair_action_or_exhausted_repair_proof",
        cta_rule="single_executor_backed_apply_cta_for_selected_shear_repair",
        affected_by_shared_helpers=("capacity_checks", "spacing_checks", "candidate_schema", "target_band_scoring"),
        regression_id="shear_fail_governs_repair_regression",
        migrated=True,
        locked=False,
    )

    def contracted_repair_ladder_specs(
        self,
        state: dict,
        *,
        width_key: str = "b",
        geometry_locked: bool = False,
        reo_spacings: tuple[float, ...] | list[float] | None = None,
        lig_diameters: tuple[int, ...] | list[int] | None = None,
    ) -> dict[str, Any]:
        """Return the contract-owned SHEAR_FAIL_GOVERNS repair ladder.

        The product may evaluate these specs with existing engineering helpers,
        but the option order, restart points, and stop boundary live here.
        """
        base = _as_dict(state)
        runtime_base = {
            **base,
            "geometry": {
                "beam_width_mm": _state_float(base, width_key, _state_float(base, "b", 400.0)),
                "beam_depth_mm": _state_float(base, "D", 600.0),
                "geometry_locked": bool(geometry_locked),
            },
            "reinforcement": {
                "ligature_spacing_mm": _state_float(base, "s_lig", 200.0),
                "ligature_diameter_mm": max(_state_int(base, "lig_d", 10), 10),
                "ligature_leg_count": max(_state_int(base, "lig_legs", 2), 2),
            },
            "constraints": {
                "geometry_locked": bool(geometry_locked),
                "minimum_spacing_mm": PREFERRED_MINIMUM_SPACING_MM,
            },
        }
        runtime_result = _run_contract_runtime(
            base_state=runtime_base,
            evaluate_candidate=_runtime_rejecting_evaluator,
        )
        runtime_trace_by_lane = {
            str(row.get("lane_id") or ""): dict(row)
            for row in runtime_result.ladder_trace
            if isinstance(row, dict)
        }
        specs: list[dict[str, Any]] = []
        index = 0
        for record in runtime_result.candidate_repairs:
            if not isinstance(record, dict):
                continue
            lane_id = str(record.get("lane_id") or "")
            flat_updates = _normalised_update_diff(
                base,
                _flatten_runtime_shear_update(dict(record.get("updates") or {}), width_key=width_key),
            )
            if not flat_updates:
                continue
            index += 1
            spec = _repair_ladder_spec_payload(
                ladder_index=index,
                step=int(_RUNTIME_CONTRACT_STEP_BY_LANE.get(lane_id, 0) or 0),
                strategy=_runtime_strategy_label(record),
                updates=flat_updates,
                restart_point=bool(record.get("restart_lanes")),
                escalation=lane_id if lane_id not in {"SPACING_REDUCTION", "BAR_SIZE_INCREASE"} else None,
            )
            spec.update(
                {
                    "lane_id": lane_id,
                    "runtime_authority": "run_shear_fail_governs_ladder_runtime",
                    "runtime_ladder_hash": runtime_result.ladder_hash,
                    "ladder_hash": runtime_result.ladder_hash,
                    "ladder_trace_ref": {
                        "lane_id": lane_id,
                        "lane_trace": runtime_trace_by_lane.get(lane_id),
                    },
                    "update_hash": record.get("update_hash"),
                    "candidate_state_hash": record.get("candidate_state_hash"),
                    "evaluation_hash": record.get("evaluation_hash"),
                    "restart_proof": {
                        "restart_lanes": tuple(record.get("restart_lanes") or ()),
                        "present": bool(record.get("restart_lanes")),
                    },
                    "ranking_proof": runtime_result.ranking_proof,
                }
            )
            specs.append(spec)

        deduped_specs = _dedupe_specs(specs)
        spacing_values = sorted(
            {
                float(_as_dict(spec.get("updates")).get("s_lig"))
                for spec in deduped_specs
                if _as_dict(spec.get("updates")).get("s_lig") not in (None, "")
            }
        )
        diameter_values = sorted(
            {
                int(_as_dict(spec.get("updates")).get("lig_d"))
                for spec in deduped_specs
                if _as_dict(spec.get("updates")).get("lig_d") not in (None, "")
            }
        )
        width_values = sorted(
            {
                float(_as_dict(spec.get("updates")).get(width_key) or _as_dict(spec.get("updates")).get("b"))
                for spec in deduped_specs
                if (
                    _as_dict(spec.get("updates")).get(width_key) not in (None, "")
                    or _as_dict(spec.get("updates")).get("b") not in (None, "")
                )
            }
        )
        stop_reason = (
            runtime_result.blocked_reason
            or runtime_result.exhausted_reason
            or "contract runtime ladder exhausted; legal no-repair proof required if shear still fails"
        )

        return {
            "family_name": "SHEAR_FAIL_GOVERNS",
            "governing_state": self.metadata.governing_state,
            "candidate_strategy": self.metadata.candidate_strategy,
            "runtime_authority": "run_shear_fail_governs_ladder_runtime",
            "runtime_ladder_hash": runtime_result.ladder_hash,
            "ladder_hash": runtime_result.ladder_hash,
            "ladder_trace": tuple(runtime_result.ladder_trace),
            "accepted_lane_evidence": tuple(runtime_result.accepted_lane_evidence),
            "rejected_lane_evidence": tuple(runtime_result.rejected_lane_evidence),
            "ranking_proof": runtime_result.ranking_proof,
            "exact_stop_proof": runtime_result.exact_stop_proof,
            "exhausted_reason": runtime_result.exhausted_reason,
            "no_valid_repair_proof": runtime_result.no_valid_repair_proof,
            "repair_reason_proof": runtime_result.repair_reason_proof,
            "cta_intent_proof": runtime_result.cta_intent_proof,
            "preferred_minimum_spacing_mm": PREFERRED_MINIMUM_SPACING_MM,
            "spacing_values_tried": list(spacing_values),
            "lig_diameters_tried": list(diameter_values),
            "widths_tried": list(width_values),
            "restart_rule": (
                "After every bar-size, depth, width, or leg-count change, restart the contract shear "
                "reinforcement search from spacing/bar-size policy."
            ),
            "ranking_rule": "Rank runtime candidates by target band, smallest geometry change, smallest reinforcement increase, constructability, and cost proxy.",
            "stop_reason_if_no_candidate": stop_reason,
            "specs": deduped_specs,
        }

    def select_repair_candidate_from_ladder(
        self,
        candidates: list[dict],
        *,
        target_low: float,
        target_high: float,
    ) -> dict[str, Any]:
        return _select_repair_candidate_from_ladder(
            candidates,
            target_low=target_low,
            target_high=target_high,
            ranking_strategy=self.metadata.ranking_strategy,
        )

    def repair_ladder_evidence_overlay(
        self,
        *,
        ladder: dict,
        selected_result: dict,
    ) -> dict[str, Any]:
        return _repair_ladder_evidence_overlay(
            ladder=ladder,
            selected_result=selected_result,
            family_route_owner=self.metadata.owner,
            family_candidate_strategy=self.metadata.candidate_strategy,
            family_ranking_strategy=self.metadata.ranking_strategy,
            family_evidence_strategy=self.metadata.evidence_strategy,
            family_publication_rule=self.metadata.publication_rule,
            family_cta_rule=self.metadata.cta_rule,
        )

    def classify(self, context: FamilyStrategyContext) -> dict[str, Any]:
        payload, primary, summary, evidence, debug, classifier = _context_payload(context)
        computed = classifier or classify_governing_state(
            payload=payload,
            primary=primary,
            summary=summary,
            evidence=evidence,
            debug=debug,
        )
        failures = _active_failures(summary, evidence, debug, computed)
        status = _shear_status(summary, evidence, debug)
        util = _shear_util(summary, evidence, debug)
        shear_fail_identified = bool("shear" in failures or status == "FAIL" or (util is not None and util > 1.0))
        missing = []
        if not summary:
            missing.append("summary")
        if not status and util is None and "shear" not in failures:
            missing.append("shear_status_or_util")
        return {
            **self._adapter_header("classify", context),
            "classification_source": "design_brain.governing_state.classify_governing_state plus existing overview/evidence fields",
            "classifier_governing_state": computed.get("governing_state"),
            "shear_fail_identified": bool(shear_fail_identified),
            "shear_status": status or None,
            "shear_util": util,
            "active_failures": list(failures),
            "missing_inputs": missing,
            "unsupported_reason": None if shear_fail_identified else "shear_fail_signal_not_present",
            "fallback_required": not bool(shear_fail_identified),
        }

    def generate_candidates(self, context: FamilyStrategyContext) -> dict[str, Any]:
        payload, primary, summary, evidence, debug, classifier = _context_payload(context)
        _ = payload, primary, summary, debug, classifier
        rows = _candidate_rows(evidence)
        shear_rows = [row for row in rows if _is_shear_candidate(row)]
        executable_rows = [row for row in shear_rows if _safe_executor_backed(row)]
        blocker = _exact_blockers(evidence, primary, debug).get("shear", {})
        missing = []
        if not evidence:
            missing.append("candidate_search_evidence")
        if not rows and not blocker:
            missing.append("candidate_rows_or_shear_blocker")
        ladder_used = bool(evidence.get("shear_fail_contract_ladder_used"))
        return {
            **self._adapter_header("generate_candidates", context),
            "candidate_source": self.metadata.candidate_strategy if ladder_used else (
                "existing inputs_page.py active shear repair search evidence"
            ),
            "candidate_strategy_mode": (
                "contract_ladder_evidence_verified" if ladder_used else "diagnostic_read_existing_evidence_only"
            ),
            "candidate_generation_called": bool(ladder_used),
            "candidate_selection_changed": bool(ladder_used),
            "candidate_row_count": len(rows),
            "shear_candidate_row_count": len(shear_rows),
            "safe_executor_backed_shear_candidate_count": len(executable_rows),
            "candidate_ids": [_candidate_id(row, idx) for idx, row in enumerate(shear_rows)],
            "contract_ladder_used": ladder_used,
            "contract_ladder_spacing_values": list(evidence.get("shear_fail_contract_ladder_spacing_values") or []),
            "contract_ladder_diameters": list(evidence.get("shear_fail_contract_ladder_diameters") or []),
            "contract_ladder_widths": list(evidence.get("shear_fail_contract_ladder_widths") or []),
            "fallback_required": not bool(executable_rows or blocker),
            "missing_inputs": missing,
            "unsupported_reason": None if rows or blocker else "no_existing_candidate_or_blocker_evidence_available",
        }

    def rank_candidates(self, context: FamilyStrategyContext, candidates: Any = None) -> dict[str, Any]:
        payload, primary, summary, evidence, debug, classifier = _context_payload(context)
        _ = payload, primary, summary, debug, classifier
        if isinstance(candidates, dict) and isinstance(candidates.get("candidate_rows"), list):
            rows = [dict(row) for row in candidates.get("candidate_rows") if isinstance(row, dict)]
        else:
            rows = _candidate_rows(evidence)
        shear_rows = [row for row in rows if _is_shear_candidate(row)]
        ladder_used = bool(evidence.get("shear_fail_contract_ladder_used"))
        diagnostic_order = sorted(
            enumerate(shear_rows),
            key=lambda item: (
                not _safe_executor_backed(item[1]),
                _as_float(item[1].get("preview_util") or item[1].get("expected_util")) is None,
                abs(float(_as_float(item[1].get("preview_util") or item[1].get("expected_util")) or 1.0) - 0.925),
                item[0],
            ),
        )
        ranked_ids = [_candidate_id(row, idx) for idx, row in diagnostic_order]
        return {
            **self._adapter_header("rank_candidates", context),
            "ranking_source": self.metadata.ranking_strategy if ladder_used else (
                "existing design_brain.ranking target-band scoring and design_brain.engine.select_target_band_winner"
            ),
            "ranking_strategy_mode": (
                "contract_ladder_first_compliant_repair" if ladder_used else "diagnostic_order_existing_rows_only"
            ),
            "ranking_applied_to_product": bool(ladder_used),
            "ranked_candidate_ids": ranked_ids,
            "ranked_candidate_count": len(ranked_ids),
            "contract_selected_ladder_index": evidence.get("shear_fail_selected_ladder_index"),
            "fallback_required": not bool(ranked_ids),
            "missing_inputs": [] if rows else ["candidate_rows"],
            "unsupported_reason": None if ranked_ids else "no_shear_candidate_rows_to_rank",
        }

    def build_evidence(self, context: FamilyStrategyContext, ranked_candidates: Any = None) -> dict[str, Any]:
        payload, primary, summary, evidence, debug, classifier = _context_payload(context)
        _ = payload, summary, classifier, ranked_candidates
        blockers = _exact_blockers(evidence, primary, debug)
        rows = _candidate_rows(evidence)
        shear_rows = [row for row in rows if _is_shear_candidate(row)]
        exhaustive = repair_search_exhaustive(evidence) or bool(_as_dict(blockers.get("shear")).get("repair_search_exhaustive"))
        missing = []
        if not evidence:
            missing.append("candidate_search_evidence")
        if not shear_rows and "shear" not in blockers:
            missing.append("shear_candidate_rows_or_exact_blocker")
        ladder_used = bool(evidence.get("shear_fail_contract_ladder_used"))
        return {
            **self._adapter_header("build_evidence", context),
            "evidence_source": self.metadata.evidence_strategy if ladder_used else (
                "existing design_brain.repair active_failure_blocker_payload / exact blockers, "
                "design_brain.evidence candidate_search_evidence_from_payload, and contracts validation"
            ),
            "evidence_strategy_mode": (
                "family_owned_contract_ladder_evidence" if ladder_used else "diagnostic_merge_existing_evidence_only"
            ),
            "evidence_mutated": bool(ladder_used),
            "repair_search_exhaustive": bool(exhaustive),
            "shear_exact_blocker_present": "shear" in blockers,
            "shear_exact_blocker": _as_dict(blockers.get("shear")),
            "shear_candidate_row_count": len(shear_rows),
            "contract_ladder_used": ladder_used,
            "fallback_required": not bool(shear_rows or blockers),
            "missing_inputs": missing,
            "unsupported_reason": None if evidence or blockers else "no_existing_shear_evidence_available",
        }

    def publish(self, context: FamilyStrategyContext, evidence: Any = None) -> dict[str, Any]:
        payload, primary, summary, evidence_map, debug, classifier = _context_payload(context)
        _ = payload, summary, classifier, evidence
        title = str(primary.get("title_main") or primary.get("title") or "").strip()
        intent = str(primary.get("guidance_intent") or "").strip()
        status = _normalise_status(primary.get("status") or primary.get("critical_status"))
        terminal = str(primary.get("design_guide_terminal_state") or debug.get("design_guide_terminal_state") or "").strip()
        title_lower = title.lower()
        visible_contradictions = []
        if "design is efficient" in title_lower:
            visible_contradictions.append("design_is_efficient_visible_for_shear_fail_context")
        if status == "PASS" or terminal:
            visible_contradictions.append("terminal_or_pass_visible_for_shear_fail_context")
        if "cleanup" in title_lower and "blocked" in title_lower:
            visible_contradictions.append("blocked_cleanup_visible_for_shear_fail_context")
        return {
            **self._adapter_header("publish", context),
            "publication_source": (
                "existing design_brain.engine resolve_design_guide_decision / resolve_design_guide_card "
                "and design_brain.publication outcome_id_for_publication"
            ),
            "publication_strategy_mode": "diagnostic_compare_visible_output_only",
            "publication_changed": False,
            "visible_title": title or None,
            "visible_intent": intent or None,
            "visible_status": status or None,
            "visible_terminal_state": terminal or None,
            "visible_contradictions": visible_contradictions,
            "fallback_required": not bool(title),
            "missing_inputs": [] if title else ["visible_primary_title"],
            "unsupported_reason": None if title else "visible_publication_not_available",
            "future_positive_expectations": list(_POSITIVE_EXPECTATIONS),
            "future_negative_expectations": list(_NEGATIVE_EXPECTATIONS),
            "evidence_available": bool(evidence_map),
        }

    def get_cta_rule(self, context: FamilyStrategyContext, evidence: Any = None) -> dict[str, Any]:
        payload, primary, summary, evidence_map, debug, classifier = _context_payload(context)
        _ = payload, summary, classifier, evidence
        contract = _button_contract(primary, debug)
        updates = _as_dict(contract.get("updates") or primary.get("updates") or primary.get("selected_action_updates"))
        cta_enabled = bool(contract.get("enabled") or contract.get("actionable"))
        executor_backed = bool(updates and str(contract.get("action_type") or primary.get("action_type") or "").strip())
        duplicate_cta_signal = bool(debug.get("duplicate_cta_detected") or evidence_map.get("duplicate_cta_detected"))
        return {
            **self._adapter_header("get_cta_rule", context),
            "cta_source": (
                "existing design_brain.engine button contract and inputs_page visible apply payload / queue path"
            ),
            "cta_strategy_mode": "diagnostic_read_existing_button_contract_only",
            "cta_changed": False,
            "creates_executable_cta": False,
            "current_cta_enabled": bool(cta_enabled),
            "current_cta_executor_backed": bool(executor_backed),
            "current_action_type": contract.get("action_type") or primary.get("action_type"),
            "current_update_keys": sorted(str(key) for key in updates.keys()),
            "future_cta_rule": "enabled only for one executor-backed shear repair action; otherwise disabled with explicit no-repair evidence",
            "single_primary_cta_expected": True,
            "duplicate_cta_signal": bool(duplicate_cta_signal),
            "fallback_required": bool(not cta_enabled and not evidence_map),
            "missing_inputs": [] if contract else ["button_contract"],
            "unsupported_reason": None if contract else "button_contract_not_available",
        }

    def route_existing_decision(
        self,
        context: FamilyStrategyContext,
        *,
        decision: dict,
        primary_item: dict,
        active_strength_failures: set[str],
    ) -> dict[str, Any]:
        """Route an already-built shear repair decision through the family owner.

        This preserves the existing candidate/CTA payload. It only owns the
        shear-fail presentation decision for a shear-only active repair action.
        """
        payload, primary, summary, evidence, debug, classifier = _context_payload(context)
        _ = payload, primary, debug, classifier
        active = {str(item or "").strip().lower() for item in set(active_strength_failures or set())}
        decision_in = _as_dict(decision)
        item_in = _as_dict(primary_item)
        button = _as_dict(decision_in.get("button_contract") or item_in.get("button_contract"))
        action_payload = _as_dict(item_in.get("action_payload"))
        resolved_candidate = _as_dict(item_in.get("resolved_candidate"))
        evidence_in = _as_dict(
            decision_in.get("candidate_search_evidence")
            or item_in.get("candidate_search_evidence")
            or evidence
        )
        promoted_candidate = _promotable_shear_repair_candidate(evidence_in)
        promoted_updates = _candidate_updates(promoted_candidate)
        updates = _as_dict(
            button.get("updates")
            or item_in.get("updates")
            or item_in.get("selected_action_updates")
            or action_payload.get("resolved_candidate_updates")
            or action_payload.get("updates")
            or resolved_candidate.get("updates")
            or promoted_updates
        )
        action_type = str(
            button.get("action_type")
            or item_in.get("action_type")
            or action_payload.get("resolved_candidate_action_type")
            or action_payload.get("action_type")
            or resolved_candidate.get("action_type")
            or promoted_candidate.get("action_type")
            or ("apply_resolved_candidate" if promoted_updates else "")
        ).strip()
        cta_enabled = bool(button.get("enabled") or button.get("actionable") or updates)
        shear_classification = self.classify(context)
        diagnostics = {
            **self._adapter_header("route_existing_decision", context),
            "family_routing_attempted": True,
            "family_routing_used": False,
            "fallback_used": True,
            "fallback_reason": None,
            "adapter_error": None,
            "product_routing_enabled": True,
            "read_only": False,
            "changes_publication": True,
            "creates_executable_cta": True,
            "active_strength_failures": sorted(active),
            "shear_fail_identified": bool(shear_classification.get("shear_fail_identified")),
        }
        if active != {"shear"}:
            diagnostics["fallback_reason"] = "active_strength_failures_not_shear_only"
            return {
                "used": False,
                "decision": decision_in,
                "primary_item": item_in,
                "diagnostics": diagnostics,
            }
        if not bool(shear_classification.get("shear_fail_identified")):
            diagnostics["fallback_reason"] = "shear_fail_not_identified"
            return {
                "used": False,
                "decision": decision_in,
                "primary_item": item_in,
                "diagnostics": diagnostics,
            }
        if not cta_enabled or action_type != "apply_resolved_candidate" or not updates:
            diagnostics["fallback_reason"] = "existing_repair_cta_not_executor_backed"
            return {
                "used": False,
                "decision": decision_in,
                "primary_item": item_in,
                "diagnostics": diagnostics,
            }

        candidate_id = str(
            button.get("candidate_id")
            or button.get("source_candidate_id")
            or promoted_candidate.get("candidate_id")
            or promoted_candidate.get("source_candidate_id")
            or evidence_in.get("selected_candidate_id")
            or evidence_in.get("closest_safe_candidate_id")
            or "shear_fail_repair_candidate"
        )
        candidate_title = str(
            promoted_candidate.get("title")
            or promoted_candidate.get("label")
            or evidence_in.get("selected_candidate_title")
            or "Shear capacity repair"
        )
        expected_util = (
            promoted_candidate.get("candidate_post_util")
            or promoted_candidate.get("preview_util")
            or promoted_candidate.get("expected_util")
            or evidence_in.get("selected_candidate_util")
            or button.get("expected_util")
        )
        result = _build_route_success_result(
            decision=decision_in,
            item=item_in,
            diagnostics=diagnostics,
            evidence=evidence_in,
            button=button,
            updates=updates,
            candidate_id=candidate_id,
            candidate_title=candidate_title,
            expected_util=expected_util,
            family_route_owner=self.metadata.owner,
            candidate_strategy=self.metadata.candidate_strategy,
            ranking_strategy=self.metadata.ranking_strategy,
            evidence_strategy=self.metadata.evidence_strategy,
            publication_rule=self.metadata.publication_rule,
            cta_rule=self.metadata.cta_rule,
            stale_blocker_keys=_STALE_BLOCKER_KEYS,
        )
        return {
            "used": bool(result.get("used")),
            "decision": _as_dict(result.get("decision")),
            "primary_item": _as_dict(result.get("primary_item")),
            "diagnostics": _as_dict(result.get("diagnostics")),
        }

    def _adapter_header(self, operation: str, context: FamilyStrategyContext) -> dict[str, Any]:
        return {
            "family_name": "SHEAR_FAIL_GOVERNS",
            "governing_state": self.metadata.governing_state,
            "adapter_version": ADAPTER_VERSION,
            "operation": operation,
            "owner": self.metadata.owner,
            "product_routing_enabled": False,
            "existing_logic_wrapped": {
                "classification": "read-only governing_state classifier and overview/evidence fields",
                "candidate": "existing inputs_page.py active shear repair search is described, not invoked",
                "ranking": "existing target-band ranking is described; diagnostic ordering only",
                "evidence": "existing repair/evidence maps are inspected",
                "publication": "existing engine/publication visible output is inspected",
                "cta": "existing button contract is inspected",
            },
            "mutates_product_state": False,
            "calls_ui_or_session_state": False,
            "changes_candidate_selection": False,
            "changes_publication": False,
            "creates_executable_cta": False,
            "required_methods": list(_REQUIRED_METHODS),
            "context_governing_state": context.governing_state,
            "read_only": True,
        }


__all__ = ["ShearFailFamily"]
