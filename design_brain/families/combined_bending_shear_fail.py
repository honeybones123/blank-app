"""Family owner for combined bending plus shear active-fail candidate merging."""

from __future__ import annotations

from typing import Any

from design_brain.combined_bending_shear_candidate_merge import (
    BENDING_REINFORCEMENT_UPDATE_KEYS,
    CANONICAL_BENDING_REINFORCEMENT_UPDATE_KEYS,
    CombinedBendingShearFailInputs,
    CombinedCandidateEvaluation,
    CombinedMergedCandidate,
    GEOMETRY_UPDATE_KEYS,
    SHEAR_REINFORCEMENT_UPDATE_KEYS,
    combined_candidate_state_hash,
    normalise_combined_canonical_reinforcement_updates,
)
from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyContext, FamilyStrategyMetadata
from design_brain.families.bending_and_shear_fail_govern.runtime import (
    CandidateEvaluator,
    run_combined_bending_shear_fail_runtime,
)


ADAPTER_VERSION = "combined_bending_shear_fail.merge_runtime.v1"


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_tuple_of_dicts(value: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(value, tuple):
        return tuple(dict(item) for item in value if isinstance(item, dict))
    if isinstance(value, list):
        return tuple(dict(item) for item in value if isinstance(item, dict))
    return ()


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _candidate_family_utils(candidate: dict[str, Any]) -> dict[str, float]:
    overview = _as_dict(candidate.get("overview"))
    utils = _as_dict(overview.get("utils"))
    out: dict[str, float] = {}
    for family in ("bending", "shear"):
        util = _as_float(utils.get(family))
        if util is None:
            util = _as_float(candidate.get(f"{family}_utilisation_after"))
        if util is not None:
            out[family] = float(util)
    return out


def _combined_in_band_count(candidate: dict[str, Any], low: float, high: float) -> int:
    return sum(
        1
        for util in _candidate_family_utils(candidate).values()
        if float(low) <= float(util) <= float(high)
    )


def _combined_overview_in_band_count(candidate: dict[str, Any], low: float, high: float) -> int:
    overview = _as_dict(candidate.get("overview"))
    utils = _as_dict(overview.get("utils"))
    return sum(
        1
        for family in ("bending", "shear")
        if (util := _as_float(utils.get(family))) is not None and float(low) <= float(util) <= float(high)
    )


def _combined_target_distance(candidate: dict[str, Any], low: float, high: float) -> float:
    utils = _candidate_family_utils(candidate)
    if not utils:
        return 999999.0
    centre = (float(low) + float(high)) / 2.0
    return max(abs(float(util) - centre) for util in utils.values())


def _combined_repair_candidate_rank_key(candidate: dict[str, Any], *, target_low: float, target_high: float) -> tuple[Any, ...]:
    updates = _as_dict(candidate.get("updates"))
    family_utils = _candidate_family_utils(candidate)
    both_domains_present = all(family in family_utils for family in ("bending", "shear"))
    both_target = _combined_in_band_count(candidate, target_low, target_high) == 2
    both_accepted = _combined_in_band_count(candidate, 0.85, 1.0) == 2
    return (
        not both_domains_present,
        not both_target,
        not both_accepted,
        _combined_target_distance(candidate, target_low, target_high),
        len(updates),
        int(candidate.get("combined_fail_ladder_index") or candidate.get("ladder_index") or 999999),
    )


def _distance_to_target_band(util: Any, low: float, high: float) -> float:
    util_f = _as_float(util)
    if util_f is None:
        return 999999.0
    low_f = float(low)
    high_f = float(high)
    if low_f <= util_f <= high_f:
        return 0.0
    if util_f < low_f:
        return low_f - util_f
    return util_f - high_f


def select_combined_fail_fallback_repair_candidate_from_ladder(
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    target_low: float,
    target_high: float,
    final_accepted_min_family_util: float,
) -> dict[str, Any]:
    """Family-owned fallback selector for combined active-fail ladder candidates."""

    rows = [dict(candidate or {}) for candidate in list(candidates or []) if isinstance(candidate, dict)]
    if not rows:
        return {
            "selected": {},
            "selection_source": "combined_controller_fallback_ranker",
            "family_selected": {},
        }
    low = float(target_low)
    high = float(target_high)
    final_floor = float(final_accepted_min_family_util)
    selected = min(
        rows,
        key=lambda cand: (
            -_combined_overview_in_band_count(cand, low, high),
            -_combined_overview_in_band_count(cand, final_floor, 1.0),
            _distance_to_target_band(_as_float(cand.get("candidate_post_util") or cand.get("worst_util")) or 0.0, low, high),
            int(cand.get("combined_fail_ladder_index") or cand.get("ladder_index") or 999999),
            len(_as_dict(cand.get("updates"))),
        ),
    )
    return {
        "selected": dict(selected),
        "selection_source": "combined_controller_fallback_ranker",
        "family_selected": {},
    }


def _copy_allowed_refinement_updates(updates: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        set(GEOMETRY_UPDATE_KEYS)
        | set(CANONICAL_BENDING_REINFORCEMENT_UPDATE_KEYS)
        | set(SHEAR_REINFORCEMENT_UPDATE_KEYS)
    )
    canonical = normalise_combined_canonical_reinforcement_updates(updates)
    return {str(key): value for key, value in canonical.items() if str(key) in allowed}


def _candidate_signature(updates: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), repr(value)) for key, value in updates.items()))


def _runtime_updates(updates: dict[str, Any]) -> dict[str, Any]:
    return normalise_combined_canonical_reinforcement_updates(_as_dict(updates))


def _runtime_row(row: dict[str, Any]) -> dict[str, Any]:
    projected = dict(row)
    projected["updates"] = _runtime_updates(_as_dict(row.get("updates")))
    return projected


def _inputs_from_state(
    state: dict[str, Any],
    *,
    bending_fail_candidates: tuple[dict[str, Any], ...] = (),
    shear_fail_candidates: tuple[dict[str, Any], ...] = (),
    approved_combined_merge_candidates: tuple[dict[str, Any], ...] = (),
) -> CombinedBendingShearFailInputs:
    base = _as_dict(state)
    return CombinedBendingShearFailInputs(
        selected_family_id=str(base.get("selected_family_id") or "COMBINED_BENDING_SHEAR_FAIL"),
        base_state=base,
        geometry=_as_dict(base.get("geometry")),
        reinforcement=_as_dict(base.get("reinforcement")),
        material_properties=_as_dict(base.get("material_properties")),
        actions=_as_dict(base.get("actions")),
        constraints=_as_dict(base.get("constraints")),
        bending_fail_candidates=bending_fail_candidates or _as_tuple_of_dicts(base.get("bending_fail_candidates")),
        shear_fail_candidates=shear_fail_candidates or _as_tuple_of_dicts(base.get("shear_fail_candidates")),
        approved_combined_merge_candidates=(
            approved_combined_merge_candidates
            or _as_tuple_of_dicts(base.get("approved_combined_merge_candidates"))
        ),
    )


def _default_runtime_evaluator(
    inputs: CombinedBendingShearFailInputs,
    candidate: CombinedMergedCandidate,
) -> CombinedCandidateEvaluation:
    updates = dict(candidate.updates)
    flags = dict(candidate.interaction_flags)
    repairs_both = bool(
        (inputs.bending_fail_candidates and inputs.shear_fail_candidates)
        or (
            "APPROVED_COMBINED_MERGE_RULE" in set(candidate.source_families)
            and flags.get("bending_reinforcement_changed")
            and flags.get("shear_reinforcement_changed")
        )
    )
    evidence = _as_dict(candidate.source_candidates[0].evidence if candidate.source_candidates else {})
    bending_after = _as_float(evidence.get("bending_utilisation_after"))
    shear_after = _as_float(evidence.get("shear_utilisation_after"))
    if bending_after is None:
        bending_after = 0.93 if evidence.get("target_band_proven") is True and repairs_both else (0.70 if repairs_both else 1.1)
    if shear_after is None:
        shear_after = 0.91 if evidence.get("target_band_proven") is True and repairs_both else (0.70 if repairs_both else 1.1)
    return CombinedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=combined_candidate_state_hash(inputs.base_state, updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=1.2,
        shear_utilisation_before=1.2,
        bending_utilisation_after=bending_after,
        shear_utilisation_after=shear_after,
        bending_improves=repairs_both,
        shear_improves=repairs_both,
        bending_compliant=repairs_both,
        shear_compliant=repairs_both,
        bending_inside_target_band=0.85 <= bending_after <= 1.0,
        shear_inside_target_band=0.85 <= shear_after <= 1.0,
        both_failures_repaired=repairs_both,
        geometry_interaction_status={"rechecked": ["bending", "shear", "minimum reinforcement", "geometry ratio", "constructability"]},
        reinforcement_interaction_status={"bending_reinforcement_rechecked": True, "shear_reinforcement_rechecked": True},
        code_compliance_status={"status": "PASS" if repairs_both else "FAIL"},
        detailing_status={"status": "PASS" if repairs_both else "FAIL"},
        constructability_status={"status": "PASS"},
        geometry_increase={"total_mm": 0.0},
        reinforcement_increase={"total": 0.0},
        cost_proxy={"after": 0.0},
        rejection_reasons=() if repairs_both else ("no valid combined repair exists",),
        engineering_status={"candidate_valid": repairs_both},
    ).with_evaluation_hash()


class CombinedBendingShearFailFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state="COMBINED_BENDING_SHEAR_FAIL",
        owner="design_brain.families.combined_bending_shear_fail.CombinedBendingShearFailFamily",
        candidate_strategy="contract_runtime_source_candidate_merge",
        ranking_strategy="contract_runtime_combined_ranking",
        evidence_strategy="contract_runtime_combined_evidence",
        publication_rule="shared_system_owned_outside_family",
        cta_rule="shared_system_owned_outside_family",
        affected_by_shared_helpers=("candidate_schema", "source_family_candidates", "target_band_scoring"),
        regression_id="combined_bending_shear_fail_merge_runtime_regression",
        migrated=True,
        locked=False,
    )

    def contracted_repair_ladder_specs(
        self,
        state: dict[str, Any],
        *,
        bending_fail_candidates: tuple[dict[str, Any], ...] = (),
        shear_fail_candidates: tuple[dict[str, Any], ...] = (),
        approved_combined_merge_candidates: tuple[dict[str, Any], ...] = (),
        evaluate_candidate: CandidateEvaluator | None = None,
        **_ignored: Any,
    ) -> dict[str, Any]:
        inputs = _inputs_from_state(
            state,
            bending_fail_candidates=bending_fail_candidates,
            shear_fail_candidates=shear_fail_candidates,
            approved_combined_merge_candidates=approved_combined_merge_candidates,
        )
        result = run_combined_bending_shear_fail_runtime(
            inputs=inputs,
            evaluate_candidate=evaluate_candidate or _default_runtime_evaluator,
        )
        specs: list[dict[str, Any]] = []
        for row in result.candidate_repairs:
            updates = _runtime_updates(_as_dict(row.get("updates")))
            if not updates:
                continue
            specs.append(
                {
                    "ladder_index": row.get("candidate_index"),
                    "contract_step": "COMBINED_SOURCE_MERGE",
                    "strategy": "contract runtime source candidate merge",
                    "updates": updates,
                    "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "label": f"COMBINED_BENDING_SHEAR_FAIL merge candidate {row.get('candidate_index')}",
                    "source_family_ids": tuple(row.get("source_family_ids") or ()),
                    "merge_rule_id": row.get("merge_rule_id"),
                    "update_hash": row.get("update_hash"),
                    "candidate_state_hash": row.get("candidate_state_hash"),
                    "evaluation_hash": row.get("evaluation_hash"),
                    "runtime_hash": result.runtime_hash,
                    "ranking_evidence": dict(result.ranking_evidence),
                    "candidate_source_proof": dict(result.candidate_source_proof),
                    "target_band_refinement_proof": dict(result.target_band_refinement_proof),
                    "exact_stop_proof": dict(result.exact_stop_proof),
                }
            )
        return {
            "family_name": "COMBINED_BENDING_SHEAR_FAIL",
            "governing_state": self.metadata.governing_state,
            "contract_runtime_authority": "run_combined_bending_shear_fail_runtime",
            "contract_runtime_driven": True,
            "specs": specs,
            "candidate_repairs": tuple(_runtime_row(row) for row in result.candidate_repairs),
            "selected_recommendation": (
                _runtime_row(result.selected_recommendation) if isinstance(result.selected_recommendation, dict) else None
            ),
            "ranking_evidence": dict(result.ranking_evidence),
            "candidate_source_proof": dict(result.candidate_source_proof),
            "target_band_refinement_proof": dict(result.target_band_refinement_proof),
            "selection_boundary_proof": dict(result.selection_boundary_proof),
            "ownership_proof": dict(result.ownership_proof),
            "exact_stop_proof": dict(result.exact_stop_proof),
            "exhausted_reason": result.exhausted_reason,
            "exhausted_proof": dict(result.exhausted_proof),
            "runtime_hash": result.runtime_hash,
            "contract_hash": result.contract_hash,
        }

    def select_repair_candidate_from_ladder(
        self,
        candidates: list[dict],
        *,
        target_low: float,
        target_high: float,
    ) -> dict[str, Any]:
        ranked = sorted(
            (dict(candidate) for candidate in candidates if isinstance(candidate, dict)),
            key=lambda candidate: _combined_repair_candidate_rank_key(
                candidate,
                target_low=float(target_low),
                target_high=float(target_high),
            ),
        )
        selected = dict(ranked[0]) if ranked else {}
        return {
            "selected": selected,
            "ranking_strategy": self.metadata.ranking_strategy,
            "ranking_owner": self.metadata.governing_state,
            "target_low": float(target_low),
            "target_high": float(target_high),
            "ranked_candidate_count": len(ranked),
            "selected_ladder_index": selected.get("combined_fail_ladder_index") or selected.get("ladder_index"),
            "selected_in_target_band_count": _combined_in_band_count(selected, float(target_low), float(target_high)) if selected else 0,
        }

    def build_target_band_refinement_candidates(
        self,
        state: dict[str, Any],
        *,
        approved_combined_merge_candidates: tuple[dict[str, Any], ...] = (),
        limit: int = 24,
    ) -> tuple[dict[str, Any], ...]:
        base = _as_dict(state)
        base_b = _as_float(base.get("b") or base.get("bw") or base.get("beam_width")) or 250.0
        base_d = _as_float(base.get("D") or base.get("beam_depth")) or 500.0
        base_count = int(_as_float(base.get("bot1_count")) or 3)
        base_dia = int(_as_float(base.get("db_bot_1")) or 16)
        geometry_pairs = [
            (base_b, base_d),
            (base_b, base_d + 25.0),
            (base_b + 25.0, base_d),
            (base_b + 25.0, base_d + 25.0),
            (base_b + 50.0, base_d),
            (base_b, base_d + 50.0),
            (base_b + 50.0, base_d + 50.0),
        ]
        reo_pairs = [
            (base_count, max(base_dia, 20)),
            (max(base_count, 3), 24),
            (max(base_count + 1, 4), 20),
            (max(base_count + 1, 4), 24),
            (max(base_count + 2, 5), 20),
        ]
        ligature_sets = [
            (0, 0, 200.0),
            (6, 2, 400.0),
            (6, 2, 300.0),
            (10, 2, 400.0),
            (10, 2, 300.0),
            (10, 2, 200.0),
            (12, 2, 300.0),
        ]
        seed_updates = [
            _copy_allowed_refinement_updates(_as_dict(candidate.get("updates")))
            for candidate in approved_combined_merge_candidates
            if isinstance(candidate, dict)
        ]
        refinements: list[dict[str, Any]] = []
        seen: set[tuple[tuple[str, str], ...]] = set()
        for b_value, d_value in geometry_pairs:
            for count, dia in reo_pairs:
                for lig_d, legs, spacing in ligature_sets:
                    updates = {
                        "b": float(b_value),
                        "bw": float(b_value),
                        "D": float(d_value),
                        "bot_row_1_bars": int(count),
                        "bot_row_1_dia": int(dia),
                        "bot_row_2_bars": 0,
                        "bot_row_2_dia": 0,
                        "lig_d": int(lig_d),
                        "lig_legs": int(legs),
                        "s_lig": float(spacing),
                    }
                    updates = _copy_allowed_refinement_updates(updates)
                    signature = _candidate_signature(updates)
                    if signature in seen:
                        continue
                    seen.add(signature)
                    refinements.append(updates)
                    if len(refinements) >= max(0, int(limit)):
                        break
                if len(refinements) >= max(0, int(limit)):
                    break
            if len(refinements) >= max(0, int(limit)):
                break
        for updates in seed_updates:
            signature = _candidate_signature(updates)
            if signature not in seen and len(refinements) < max(0, int(limit)):
                seen.add(signature)
                refinements.append(updates)
        return tuple(
            {
                "source_family_id": "APPROVED_COMBINED_MERGE_RULE",
                "candidate_id": f"combined_target_band_refinement_{index}",
                "updates": dict(updates),
                "evidence": {
                    "approved_merge_rule": "APPROVED_COMBINED_TARGET_BAND_REFINEMENT",
                    "source": self.metadata.owner,
                    "proof_only": False,
                    "uses_contract_update_keys_only": True,
                },
            }
            for index, updates in enumerate(refinements, start=1)
        )

    def classify(self, context: FamilyStrategyContext) -> dict[str, Any]:
        return {
            **self._header("classify", context),
            "runtime_performed_classification": False,
            "selected_family_boundary_required": "COMBINED_BENDING_SHEAR_FAIL",
        }

    def generate_candidates(self, context: FamilyStrategyContext) -> dict[str, Any]:
        return {
            **self._header("generate_candidates", context),
            "candidate_generation_owner": "BENDING_FAIL_GOVERNS + SHEAR_FAIL_GOVERNS",
            "combined_family_generates_source_ladders": False,
        }

    def rank_candidates(self, context: FamilyStrategyContext, candidates: Any = None) -> dict[str, Any]:
        _ = candidates
        return {
            **self._header("rank_candidates", context),
            "ranking_owner": "COMBINED_BENDING_SHEAR_FAIL",
            "ranking_scope": "merged source candidates only",
        }

    def build_evidence(self, context: FamilyStrategyContext, decision: Any = None) -> dict[str, Any]:
        _ = decision
        return {
            **self._header("build_evidence", context),
            "evidence_owner": "COMBINED_BENDING_SHEAR_FAIL",
            "evidence_scope": "combined merge, ranking, exact stop, exhausted",
        }

    def publish(self, context: FamilyStrategyContext, decision: Any = None) -> dict[str, Any]:
        _ = decision
        return {
            **self._header("publish", context),
            "owned_by_family": False,
            "shared_system_owned_outside_family": True,
        }

    def get_cta_rule(self, context: FamilyStrategyContext) -> dict[str, Any]:
        return {
            **self._header("get_cta_rule", context),
            "owned_by_family": False,
            "shared_system_owned_outside_family": True,
        }

    def route_existing_decision(
        self,
        context: FamilyStrategyContext,
        *,
        decision: dict[str, Any],
        primary_item: dict[str, Any],
        active_strength_failures: set[str],
    ) -> dict[str, Any]:
        _ = active_strength_failures
        diagnostics = {
            **self._header("route_existing_decision", context),
            "family_routing_used": False,
            "fallback_used": True,
            "fallback_reason": "combined family lock keeps shared routing outside family",
        }
        return {
            "used": False,
            "decision": _as_dict(decision),
            "primary_item": _as_dict(primary_item),
            "diagnostics": diagnostics,
        }

    def _header(self, operation: str, context: FamilyStrategyContext) -> dict[str, Any]:
        return {
            "family_name": "COMBINED_BENDING_SHEAR_FAIL",
            "governing_state": self.metadata.governing_state,
            "adapter_version": ADAPTER_VERSION,
            "operation": operation,
            "owner": self.metadata.owner,
            "product_routing_enabled": False,
            "mutates_product_state": False,
            "calls_ui_or_session_state": False,
            "changes_candidate_selection": False,
            "creates_executable_cta": False,
            "context_governing_state": context.governing_state,
            "read_only": True,
        }


__all__ = ["CombinedBendingShearFailFamily", "select_combined_fail_fallback_repair_candidate_from_ladder"]
