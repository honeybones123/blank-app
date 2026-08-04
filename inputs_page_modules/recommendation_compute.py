"""Recommendation compute coordinators for the Inputs page."""

from __future__ import annotations

import math
import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping

from inputs_application.geometry_search_policy import (
    build_auto_design_context as _build_auto_design_context,
    design_mode_config as _design_mode_config,
    design_optimisation_goal as _design_optimisation_goal,
    generate_balanced_geometry_options as _generate_balanced_geometry_options,
    generate_same_or_larger_geometry_options,
    generate_shallower_or_equal_depths,
    generate_slightly_deeper_depths,
    geometry_lock_enabled as _geometry_lock_enabled,
    geometry_tightening_trial_updates as _geometry_tightening_trial_updates,
    recommendation_search_allowed as _recommendation_search_allowed,
    resolved_efficiency_target_band as _resolved_efficiency_target_band,
)
from inputs_application.recommendation_support import (
    resolve_geometry_width_context as _resolve_geometry_width_context,
    severe_shear_failure as _severe_shear_failure,
    shear_severity_band as _shear_severity_band,
)
from inputs_application.recommendation_evaluation import (
    evaluate_bending_with_bottom_state as _evaluate_bending_with_bottom_state,
    evaluate_shear_with_state as _evaluate_shear_with_state,
    shear_state_eligible_for_no_links as _shear_state_eligible_for_no_links,
    shear_no_links_candidate_passes_code as _shear_no_links_candidate_passes_code,
    try_shear_no_demand_cleanup_recommendation,
)
from inputs_application.recommendation_target_band import (
    annotate_candidate_target_band_metrics as _annotate_candidate_target_band_metrics,
)
from inputs_application.state_utils import (
    bottom_reo_state_label as _bottom_reo_state_label,
    float_from_state as _float_from_state,
    guidance_state_snapshot as _guidance_state_snapshot,
    shear_state_label as _shear_state_label,
    updates_match_state as _updates_match_state,
)
from inputs_application.candidate_metrics import int_from_state as _int_from_state
from inputs_application.secondary_bending_tightening import (
    generate_secondary_bending_tightening_states as _generate_secondary_bending_tightening_states,
)
from inputs_application.shear_candidate_selection import (
    combined_shear_seed_candidates as _combined_shear_seed_candidates,
)
from inputs_application.recommendation_diagnostics import (
    log_shear_candidate_debug,
    log_shear_ladder_attempt,
)
from inputs_application.auto_design_scoring_runtime import (
    build_auto_design_scoring_runtime,
)
from inputs_application.bottom_geometry_trials import (
    bottom_recommendation_geometry_trial_updates,
)
from inputs_application.bottom_compound_runtime import (
    build_bottom_compound_runtime,
)
from inputs_application.bottom_selector_runtime import (
    build_bottom_selector_runtime,
)
from inputs_application.recommendation_compound_contracts import (
    RecommendationCompoundRuntime,
)
from inputs_page_modules.recommendation_compound_candidates import (
    _append_geometry_bottom_compound_candidates,
)
from inputs_page_modules.design_guide.bottom_recommendation_selector import (
    BottomRecommendationSelectorRuntime,
    _collapse_bottom_geometry_width_depth_trials,
    _pick_best_bottom_recommendation_by_selector,
)
from inputs_page_modules.design_guide.auto_design_scoring import (
    AutoDesignScoringRuntime,
    _score_auto_design_candidate_components,
    candidate_materially_worsens as _candidate_materially_worsens,
)
from inputs_application.shear_recommendation_selector import (
    pick_best_shear_recommendation,
)
from inputs_page_modules.design_guide.severe_shear_escalation_log import (
    _log_severe_shear_escalation as _log_severe_shear_escalation_typed,
)
from inputs_page_modules.design_guide.candidate_keys import (
    _make_auto_design_candidate_key,
)
from inputs_page_modules.recommendation_shear_ladder import (
    _iter_shear_recommendation_ladder_states as _iter_shear_recommendation_ladder_states_typed,
)
from inputs_application.geometry_recommendation import (
    GeometryCandidateRuntime,
    compute_geometry_recommendation as compute_geometry_recommendation_typed,
)
from inputs_application.geometry_candidate_ranking import (
    rank_geometry_candidates as _keep_top_candidates,
)
from inputs_application.recommendation_primitives import (
    annotate_bottom_candidate_deltas as _annotate_bottom_reo_candidate_deltas,
    bottom_arrangement_to_shared_updates as _bottom_arrangement_to_shared_updates,
    bottom_recommendation_prefilter_ok as _bottom_recommendation_prefilter_ok,
    candidate_is_growth_move as _candidate_is_growth_move,
    candidate_materially_improves as _candidate_materially_improves,
    efficiency_reduction_profile as _efficiency_reduction_profile_from_overview,
    geometry_trial_axis_for_bottom as _geometry_trial_axis_for_bottom_rec,
    maybe_prefer_compound_over_pure_geometry as _maybe_prefer_compound_over_pure_geometry,
    invalid_shear_spacing_change_without_activation as _invalid_shear_spacing_change_without_activation_owned,
    practical_bottom_reo_label as _practical_bottom_reo_label,
    required_ast_for_arrangement as _required_ast_for_arrangement,
    candidate_is_within_smallest_fix_band as _candidate_is_within_smallest_fix_band,
    candidate_leg_counts as _candidate_leg_counts,
    shear_change_is_relevant as _shear_change_is_relevant,
    shear_change_magnitude as _shear_change_magnitude,
    shear_candidate_type as _shear_candidate_type,
    shear_detailing_updates_pure as _shear_detailing_updates_pure,
    shear_spacing_layout_must_not_trigger_strengthening as _shear_spacing_layout_must_not_trigger_strengthening,
    shear_recommendation_prefinal_eligible as _shear_recommendation_prefinal_eligible,
    shear_overview_is_conservative_cleanup as _shear_recommendation_overview_is_conservative_cleanup,
    shear_util_from_candidate as _shear_util_from_overview_candidate,
    shortlist_smallest_successful_shear_candidates as _shortlist_smallest_successful_shear_candidates,
)
from design_brain.families.bending import (
    build_bottom_reo_arrangement_pool_from_state,
    build_bottom_reo_guidance_change_lines_for_updates as _build_bottom_reo_guidance_change_lines_for_updates,
)


_BOTTOM_RECOMMENDATION_BAR_DIAMETERS = (10, 12, 16, 20, 24, 28, 32, 36, 40)
_BOTTOM_RECOMMENDATION_CANDIDATE_LIMIT = 20
_BOTTOM_RECOMMENDATION_GEOMETRY_TRIAL_DELTAS_MM = (25, 50)
_BOTTOM_RECOMMENDATION_DEBUG_PROBE = True


def _design_width_value(state: dict) -> float:
    return float(_resolve_geometry_width_context(state)[2])


def _generate_local_bottom_arrangements(
    state: dict,
    mode_config: dict,
    *,
    band: int,
    context: dict | None = None,
    limit: int | None = None,
) -> list[dict]:
    return build_bottom_reo_arrangement_pool_from_state(
        state,
        mode_config,
        band=band,
        context=context,
        limit=limit,
        bar_diameters=_BOTTOM_RECOMMENDATION_BAR_DIAMETERS,
        default_limit=_BOTTOM_RECOMMENDATION_CANDIDATE_LIMIT,
    )


def compute_geometry_recommendation(
    runtime: GeometryCandidateRuntime,
    state: dict,
) -> dict | None:
    return compute_geometry_recommendation_typed(
        state,
        runtime=runtime,
    )
@dataclass(frozen=True)
class RecommendationEvaluationRuntime:
    build_design_actions_context: Any
    collect_design_overview: Any
    combined_shear_truth_gate: Any
    evaluate_candidate_fast: Any
    evaluate_candidate_full: Any


@dataclass(frozen=True)
class RecommendationTraceRuntime:
    agent_debug_log: Any
    active_recommendation_trace: Any
    append_recommendation_trace: Any
    candidate_debug_enabled: bool
    log_candidate_rank: Any
    log_efficiency_growth_rejection: Any
    merge_rank_trace: Any


def _trace_runtime_from_namespace(
    namespace: Mapping[str, Any],
) -> RecommendationTraceRuntime:
    return RecommendationTraceRuntime(
        agent_debug_log=namespace["_agent_debug_log"],
        active_recommendation_trace=namespace["_ACTIVE_GUIDANCE_RECO_TRACE"],
        append_recommendation_trace=namespace["_append_design_guide_reco_trace"],
        candidate_debug_enabled=bool(
            getattr(namespace.get("st"), "session_state", {}).get("_dev_mode")
        ),
        log_candidate_rank=namespace["_log_design_reco_candidate_rank"],
        log_efficiency_growth_rejection=namespace["_log_efficiency_growth_rejection"],
        merge_rank_trace=namespace["_merge_design_guide_rank_trace"],
    )


def _evaluation_runtime_from_namespace(
    namespace: Mapping[str, Any],
) -> RecommendationEvaluationRuntime:
    return RecommendationEvaluationRuntime(
        build_design_actions_context=namespace["_build_design_actions_context"],
        collect_design_overview=namespace["_collect_design_overview"],
        combined_shear_truth_gate=namespace[
            "_combined_underdesign_shear_strengthening_truth_gate_payload"
        ],
        evaluate_candidate_fast=namespace["_evaluate_candidate_fast"],
        evaluate_candidate_full=namespace["evaluate_candidate_full"],
    )


@dataclass(frozen=True)
class BottomRecommendationRuntime:
    trace: RecommendationTraceRuntime
    compound: RecommendationCompoundRuntime
    evaluation: RecommendationEvaluationRuntime
    scoring: AutoDesignScoringRuntime
    selector: BottomRecommendationSelectorRuntime


_BOTTOM_RECOMMENDATION_NAMES: tuple[str, ...] = tuple(
    BottomRecommendationRuntime.__dataclass_fields__
)


def bottom_recommendation_runtime_from_namespace(
    namespace: Mapping[str, Any],
) -> BottomRecommendationRuntime:
    """Build an explicit runtime from a controlled verifier namespace."""

    values = {
        name: namespace[name]
        for name in BottomRecommendationRuntime.__dataclass_fields__
        if name not in {"compound", "evaluation", "scoring", "selector", "trace"}
    }
    values["evaluation"] = namespace.get("evaluation") or _evaluation_runtime_from_namespace(
        namespace
    )
    values["trace"] = namespace.get("trace") or _trace_runtime_from_namespace(namespace)
    values["scoring"] = namespace.get("scoring") or build_auto_design_scoring_runtime(
        agent_debug_log=namespace["_agent_debug_log"],
    )
    values["compound"] = namespace.get("compound") or build_bottom_compound_runtime(
        evaluate_candidate_fast=values["evaluation"].evaluate_candidate_fast,
    )
    values["selector"] = namespace.get("selector") or build_bottom_selector_runtime(
        scoring=values["scoring"],
        trace=values["trace"],
    )
    return BottomRecommendationRuntime(**values)


@dataclass(frozen=True)
class ShearRecommendationRuntime:
    trace: RecommendationTraceRuntime
    evaluation: RecommendationEvaluationRuntime
    scoring: AutoDesignScoringRuntime


_SHEAR_RECOMMENDATION_NAMES: tuple[str, ...] = tuple(
    ShearRecommendationRuntime.__dataclass_fields__
)


def shear_recommendation_runtime_from_namespace(
    namespace: Mapping[str, Any],
) -> ShearRecommendationRuntime:
    values = {
        name: namespace[name]
        for name in ShearRecommendationRuntime.__dataclass_fields__
        if name not in {"evaluation", "trace"}
    }
    values["evaluation"] = namespace.get("evaluation") or _evaluation_runtime_from_namespace(
        namespace
    )
    values["trace"] = namespace.get("trace") or _trace_runtime_from_namespace(namespace)
    return ShearRecommendationRuntime(**values)


def _bind_named_recommendation_globals(*, legacy_page: Any, names: tuple[str, ...]) -> None:
    namespace = globals()
    for name in names:
        namespace[name] = getattr(legacy_page, name)


def _emit_bottom_reo_filter_boundary_trace(
    *,
    state: dict[str, Any],
    candidates: list[dict[str, Any]],
    filtered: list[dict[str, Any]],
) -> None:
    """Emit a primitive pre-rank proof surface when runtime tracing is enabled."""

    if str(os.environ.get("DESIGN_GUIDE_RUNTIME_TRACE") or "").strip() != "1":
        return
    trace_path = str(os.environ.get("DESIGN_GUIDE_RUNTIME_TRACE_PATH") or "").strip()
    if not trace_path:
        return

    from design_brain.families.bending import (
        build_bottom_reo_evaluated_candidate_filter_boundary,
        build_bottom_reo_evaluated_candidate_filter_record,
    )

    def _hash(value: Any) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()[:16]

    def _identity(candidate: dict[str, Any]) -> str:
        return str(
            candidate.get("candidate_id")
            or candidate.get("source_candidate_id")
            or f"candidate:{_hash(candidate.get('updates') or {})}"
        )

    accepted_ids = {_identity(candidate) for candidate in filtered if isinstance(candidate, dict)}
    records: list[dict[str, Any]] = []
    for order_index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        updates = dict(candidate.get("updates") or {})
        arrangement = dict(candidate.get("arrangement") or {})
        overview = dict(candidate.get("overview") or {})
        utils = dict(overview.get("utils") or {})
        identity = _identity(candidate)
        record = build_bottom_reo_evaluated_candidate_filter_record(
            order_index=order_index,
            band=int(candidate.get("search_band", 0) or 0),
            arrangement_identity=arrangement,
            arrangement_signature=_hash(arrangement) if arrangement else None,
            arrangement_update_keys=sorted(str(key) for key in arrangement.keys()),
            arrangement_update_payload_hash=_hash(arrangement) if arrangement else None,
            evaluator_returned=True,
            status="accepted_prerank" if identity in accepted_ids else "rejected",
            reject_reason=None if identity in accepted_ids else "not_in_prerank_filtered_pool",
            accepted_prerank_candidate_identity=identity if identity in accepted_ids else None,
            candidate_update_keys=sorted(str(key) for key in updates.keys()),
            candidate_update_payload_hash=_hash(updates) if updates else None,
            utilisation_summary={
                "bending": utils.get("bending"),
                "shear": utils.get("shear"),
                "worst": candidate.get("worst_util") or overview.get("worst_util"),
            },
            target_band_status={
                "reaches_target_band": candidate.get("candidate_reaches_target_band"),
                "distance_to_target_band": candidate.get("candidate_distance_to_target_band"),
            },
        )
        records.append(record.to_dict())

    boundary = build_bottom_reo_evaluated_candidate_filter_boundary(
        records=records,
        input_arrangement_pool_hash=_hash(
            [record.get("arrangement_signature") for record in records]
        ) if records else None,
        source_family_runtime_id="design_brain.families.bending",
    ).to_dict()
    row = {
        "scenario": str(
            os.environ.get("DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO")
            or "BOTTOM_REO_EVAL_FILTER_BOUNDARY"
        ),
        "route_event": "bottom_reo_recommendation_candidates",
        "payload": {
            "input_state_hash": _hash(dict(state or {})),
            "evaluated_candidate_filter_boundary": boundary,
            "evaluated_candidate_filter_boundary_json": json.dumps(
                boundary, sort_keys=True, separators=(",", ":"), default=str
            ),
        },
    }
    try:
        with open(trace_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    except OSError:
        return


def _emit_bottom_reo_readiness_trace(
    *,
    state: dict[str, Any],
    candidates: list[dict[str, Any]],
    filtered: list[dict[str, Any]],
    ranked: list[dict[str, Any]],
    selected: dict[str, Any] | None,
    status: str,
    return_reason: str | None,
    result: dict[str, Any] | None,
) -> None:
    """Emit the current recommendation boundary for proof-only snapshots."""

    if str(os.environ.get("DESIGN_GUIDE_RUNTIME_TRACE") or "").strip() != "1":
        return
    trace_path = str(os.environ.get("DESIGN_GUIDE_RUNTIME_TRACE_PATH") or "").strip()
    if not trace_path:
        return

    def _hash(value: Any) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()[:16]

    def _identity(candidate: dict[str, Any] | None) -> str | None:
        if not isinstance(candidate, dict):
            return None
        return str(
            candidate.get("candidate_id")
            or candidate.get("source_candidate_id")
            or f"candidate:{_hash(candidate.get('updates') or {})}"
        )

    def _ids(items: list[dict[str, Any]]) -> list[str]:
        return [identity for item in items if (identity := _identity(item))]

    raw_ids = _ids([item for item in candidates if isinstance(item, dict)])
    filtered_ids = _ids([item for item in filtered if isinstance(item, dict)])
    ranked_ids = _ids([item for item in ranked if isinstance(item, dict)])
    selected_id = _identity(selected)
    updates = dict((selected or {}).get("updates") or {}) if isinstance(selected, dict) else {}
    selected_update_keys = sorted(str(key) for key in updates.keys())
    selected_reaches_band = bool(
        (selected or {}).get("candidate_reaches_target_band")
        or (selected or {}).get("in_target_band")
    ) if isinstance(selected, dict) else False
    target_low = 0.85
    target_high = 1.0
    selector_result = {
        "status": str(status),
        "selected_reason": "strict_band_winner_accept" if selected_id and selected_reaches_band else (
            "selector_top_valid" if selected_id else None
        ),
        "no_candidate_reason": return_reason,
        "selected_candidate_id": selected_id,
        "selected_candidate_identity": selected_id,
        "selected_update_keys": selected_update_keys,
        "selected_updates_hash": _hash(updates) if selected_id else None,
        "selected_candidate_trace_hash": _hash(selected) if selected else None,
        "strict_band_winner_seen": bool(selected_id and selected_reaches_band),
        "strict_band_winner_accepted": bool(selected_id and selected_reaches_band),
        "strict_band_rejected_reason": None,
        "legacy_rejection_reason": None,
        "selected_reaches_target_band": selected_reaches_band,
        "selected_because_band": bool(selected_id and selected_reaches_band),
        "winner_pool_mode": "strict_target_band" if selected_id and selected_reaches_band else None,
        "target_low": target_low,
        "target_high": target_high,
    }
    selected_decision = {
        "selected_candidate_id": selected_id,
        "selected_candidate_identity": selected_id,
        "filtered_candidate_order_hash": _hash(filtered_ids),
        "selected_candidate_update_keys": selected_update_keys,
        "ranked_candidate_identities": ranked_ids,
        "kept_candidate_identities": ranked_ids,
        "selected_candidate_updates_hash": _hash(updates) if selected_id else None,
        "selected_candidate_trace_hash": _hash(selected) if selected else None,
        "final_result_update_keys": sorted(str(key) for key in dict((result or {}).get("updates") or {}).keys()),
        "post_selector_guard_result": "selected" if selected_id else "no_result",
        "no_result_reason": return_reason,
        "compound_preference_changed": False,
        "compound_preference_selected": False,
    }
    candidate_payload = {
        "source_family_runtime_id": "normal_bottom_reo_recommendation",
        "generated_candidate_count": len(raw_ids),
        "generated_candidate_order_hash": _hash(raw_ids),
        "raw_candidate_count": len(raw_ids),
        "raw_candidate_order_hash": _hash(raw_ids),
        "filtered_candidate_count": len(filtered_ids),
        "filtered_candidate_order_hash": _hash(filtered_ids),
        "ranked_candidate_count": len(ranked_ids),
        "ranked_candidate_order_hash": _hash(ranked_ids),
        "candidate_count": len(raw_ids),
        "candidate_order": {"count": len(raw_ids), "order_hash": _hash(raw_ids), "identities": raw_ids},
        "candidate_order_hash": _hash(raw_ids),
    }
    pool_boundary = {
        **candidate_payload,
        "selected_candidate_id": selected_id,
        "selected_update_payload": updates,
        "target_band_status": {
            "target_low": target_low,
            "target_high": target_high,
            "selected_reaches_target_band": selected_reaches_band,
            "band_reacher_count": sum(
                1 for item in filtered
                if bool(item.get("candidate_reaches_target_band") or item.get("in_target_band"))
            ),
        },
        "reject_skip_reasons": {"no_result_reason": return_reason} if return_reason else {},
    }
    return_payload = {
        "status": str(status),
        "return_reason": return_reason,
        "selected_candidate_id": selected_id,
        "selected_candidate_identity": selected_id,
        "selected_update_keys": selected_update_keys,
        "selected_candidate_update_keys": selected_update_keys,
        "selected_candidate_update_keys_json": json.dumps(selected_update_keys),
        "final_result_update_keys": sorted(str(key) for key in dict((result or {}).get("updates") or {}).keys()),
        "selected_candidate_decision": selected_decision,
        "selected_candidate_decision_json": json.dumps(selected_decision, sort_keys=True),
        "selector_result": selector_result,
        "selector_result_json": json.dumps(selector_result, sort_keys=True),
        "candidate_pool_boundary": pool_boundary,
        "candidate_pool_boundary_json": json.dumps(pool_boundary, sort_keys=True),
        "selected_candidate_hash": _hash(selected) if selected else None,
        "selected_score": (selected or {}).get("score") if isinstance(selected, dict) else None,
        "ranked_candidate_count": len(ranked_ids),
        "ranked_candidate_order_hash": _hash(ranked_ids),
        "result": {
            "hash": _hash(result or {}),
            "update_keys": sorted(str(key) for key in dict((result or {}).get("updates") or {}).keys()),
        },
    }
    scenario = str(os.environ.get("DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO") or "BOTTOM_REO_READINESS")
    rows = [
        {
            "scenario": scenario,
            "event": "compute_guidance_route",
            "route_event": "bottom_reo_recommendation_candidates",
            "payload": candidate_payload,
        },
        {
            "scenario": scenario,
            "event": "compute_guidance_route",
            "route_event": "bottom_reo_recommendation_return",
            "payload": return_payload,
        },
    ]
    try:
        with open(trace_path, "a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    except OSError:
        return


def compute_bottom_reo_recommendation(
    runtime: BottomRecommendationRuntime,
    state: dict,
) -> dict | None:
    return _compute_bottom_reo_recommendation(
        state,
        runtime=runtime,
    )


def compute_shear_recommendation(
    runtime: ShearRecommendationRuntime,
    state: dict,
) -> dict | None:
    return _compute_shear_recommendation(
        state,
        runtime=runtime,
    )


def _shear_ladder_validate_candidate(
    state: dict,
    candidate: dict | None,
    *,
    branch: str,
    conservative: bool,
    baseline_shear_util: float | None,
    runtime: ShearRecommendationRuntime,
) -> tuple[bool, str]:
    if candidate is None:
        return False, "eval_none"
    updates = candidate.get("updates") or {}
    if not updates:
        return False, "empty_updates"
    if _updates_match_state(state, updates):
        return False, "no_state_change"
    if conservative:
        _pure_u, _bad_u = _shear_detailing_updates_pure(dict(updates))
        if not _pure_u:
            return False, "non_shear_detailing_updates_in_conservative_shear_ladder"
    cs = dict(candidate.get("state") or {})
    legs = _int_from_state(cs, "lig_legs", 0)
    if legs == 1:
        return False, "lig_legs_single_leg_forbidden"
    dia = _int_from_state(cs, "lig_d", 0)
    if legs > 0 and dia <= 0:
        return False, "zero_link_diameter"
    s_prop = _float_from_state(cs, "s_lig", 0.0)
    s_cur = _float_from_state(state, "s_lig", 0.0)
    leg_cur = max(_int_from_state(state, "lig_legs", 2), 2)
    new_util = ((candidate.get("overview") or {}).get("utils") or {}).get("shear")

    if conservative:
        if not bool(candidate.get("is_compliant")):
            return False, "not_compliant"
        if branch == "no_ligs":
            if legs != 0:
                return False, "no_ligs_branch_requires_zero_legs"
            if not _shear_state_eligible_for_no_links(state):
                return False, "no_links_not_eligible_precheck"
            if not _shear_no_links_candidate_passes_code(state, candidate):
                return False, "no_links_torsion_or_min_shear_or_strength"
            return True, "accepted"
        if legs == 0:
            return False, "zero_ligs_only_via_no_ligs_branch"
        if legs < 2:
            return False, "lig_legs_below_2"
        if branch == "spacing_looser" and s_prop <= s_cur + 1e-9:
            return False, "spacing_not_increased"
        if branch == "legs_down":
            if leg_cur <= 2 or legs >= leg_cur:
                return False, "legs_not_reduced"
        if branch == "dia_down":
            if dia >= _int_from_state(state, "lig_d", 0):
                return False, "dia_not_reduced"
        return True, "accepted"

    if legs == 0:
        return False, "zero_ligs_in_failing_branch"
    if legs < 2:
        return False, "lig_legs_below_2"
    if legs < leg_cur:
        return False, "removed_closed_ligs"
    if branch == "spacing_tighter" and s_cur > 1e-9 and s_prop >= s_cur - 1e-9:
        return False, "spacing_not_reduced"
    if new_util is None:
        return False, "missing_shear_util"
    try:
        nu = float(new_util)
        if math.isnan(nu):
            return False, "missing_shear_util"
    except (TypeError, ValueError):
        return False, "missing_shear_util"
    if baseline_shear_util is not None:
        if float(nu) >= float(baseline_shear_util) - 1e-9:
            return False, "shear_util_not_improved"
    return True, "accepted"


def _compute_bottom_reo_recommendation(
    state: dict,
    *,
    runtime: BottomRecommendationRuntime,
) -> dict | None:
    _ACTIVE_GUIDANCE_RECO_TRACE = runtime.trace.active_recommendation_trace
    _agent_debug_log = runtime.trace.agent_debug_log
    _append_design_guide_reco_trace = runtime.trace.append_recommendation_trace
    _build_design_actions_context = runtime.evaluation.build_design_actions_context
    _collect_design_overview = runtime.evaluation.collect_design_overview
    _evaluate_candidate_fast = runtime.evaluation.evaluate_candidate_fast
    _log_design_reco_candidate_rank = runtime.trace.log_candidate_rank
    _log_efficiency_growth_rejection = runtime.trace.log_efficiency_growth_rejection
    _merge_design_guide_rank_trace = runtime.trace.merge_rank_trace
    def _score_auto_design_candidate(
        candidate: dict,
        mode_config: dict,
        seed_candidate: dict,
    ) -> float:
        components = _score_auto_design_candidate_components(
            candidate,
            mode_config,
            seed_candidate,
            runtime=runtime.scoring,
        )
        candidate["_score_components"] = dict(components)
        return float(components.get("total_score", 0.0) or 0.0)
    evaluate_candidate_full = runtime.evaluation.evaluate_candidate_full
    state = _guidance_state_snapshot(state)
    started_at = time.perf_counter()
    design_context_br = _build_design_actions_context(state)
    overview_br = _collect_design_overview(state, context=design_context_br)
    if not _recommendation_search_allowed(state, overview_br):
        return None
    efficiency_reduction_only = _efficiency_reduction_profile_from_overview(overview_br)
    mode_config = _design_mode_config(_design_optimisation_goal(state))
    seed_candidate = evaluate_candidate_full(state, source="bottom_recommendation_seed")
    if not seed_candidate:
        return None
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    candidates: list[dict] = []
    for band in range(2):
        for arrangement in _generate_local_bottom_arrangements(state, mode_config, band=band, context=context):
            candidate_state = dict(state)
            candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="bottom_recommendation",
                label=_practical_bottom_reo_label(
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                ),
                action_type="apply_bottom_recommendation",
            )
            if candidate is None or _updates_match_state(state, candidate.get("updates", {})):
                continue
            candidate["arrangement"] = arrangement
            candidate["actual_ast"] = float(candidate.get("Ast_bot", 0.0) or 0.0)
            candidate["recommendation_family_tag"] = "pure_bottom_reo"
            candidates.append(candidate)

    if not _geometry_lock_enabled(state) and not efficiency_reduction_only:
        geo_axes = (
            ("increase_width", "increase_depth")
            if str(mode_config.get("search_strategy", "balanced") or "balanced") == "shallow"
            else ("increase_depth", "increase_width")
        )
        for d in _BOTTOM_RECOMMENDATION_GEOMETRY_TRIAL_DELTAS_MM:
            for atype in geo_axes:
                payload = {"delta_mm": float(d)}
                updates = bottom_recommendation_geometry_trial_updates(
                    atype,
                    payload,
                    state=state,
                )
                if not updates or _updates_match_state(state, updates):
                    continue
                cand_state = dict(state)
                cand_state.update(updates)
                geo_label = (
                    f"Increase depth D by {int(d)} mm"
                    if atype == "increase_depth"
                    else f"Increase section width by {int(d)} mm"
                )
                geo_cand = _evaluate_candidate_fast(
                    cand_state,
                    seed_state=seed_candidate["state"],
                    context=context,
                    eval_cache=eval_cache,
                    metrics=metrics,
                    source="bottom_recommendation_geometry",
                    label=geo_label,
                    action_type=str(atype),
                )
                if geo_cand is None or _updates_match_state(state, geo_cand.get("updates", {})):
                    continue
                geo_cand["recommendation_geometry_trial"] = True
                geo_cand["actual_ast"] = float(geo_cand.get("Ast_bot", 0.0) or 0.0)
                _gax = _geometry_trial_axis_for_bottom_rec(geo_cand, state)
                geo_cand["recommendation_family_tag"] = (
                    f"pure_geometry_{_gax}" if _gax in ("width", "depth") else "pure_geometry"
                )
                candidates.append(geo_cand)

    compound_stats: dict = {
        "geometry_seed_candidates_considered": 0,
        "width_seed_candidates_selected_for_compound": 0,
        "depth_seed_candidates_selected_for_compound": 0,
        "bottom_layout_trials_attempted_on_width_state": 0,
        "bottom_layout_trials_attempted_on_depth_state": 0,
        "compound_candidates_generated_count": 0,
        "compound_layout_reject_count": 0,
        "rejected_no_layout_variation": 0,
        "rejected_duplicate_signature": 0,
        "rejected_noncompliant": 0,
        "rejected_score_inferior": 0,
        "rejected_invalid_merge": 0,
        "rejected_same_as_current": 0,
        "rejected_filtered_by_family_collapse": 0,
        "rejected_eval_cap_or_none": 0,
        "compound_zero_generation_hints": [],
        "compound_stage_skipped_reason": None,
    }
    compound_trace_log: list[dict] = []
    if not _geometry_lock_enabled(state) and not efficiency_reduction_only:
        _append_geometry_bottom_compound_candidates(
            state=state,
            seed_candidate=seed_candidate,
            candidates=candidates,
            mode_config=mode_config,
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            compound_stats=compound_stats,
            compound_trace_log=compound_trace_log,
            runtime=runtime.compound,
        )
        if int(compound_stats.get("compound_candidates_generated_count", 0) or 0) == 0:
            hints: list[str] = []
            if int(compound_stats.get("geometry_seed_candidates_considered", 0) or 0) == 0:
                hints.append("no_geometry_trial_candidates_in_pool_for_compound")
            elif (
                int(compound_stats.get("width_seed_candidates_selected_for_compound", 0) or 0) == 0
                and int(compound_stats.get("depth_seed_candidates_selected_for_compound", 0) or 0) == 0
            ):
                hints.append("no_unique_geometry_seeds_after_util_sort_or_missing_axis_keys")
            elif (
                int(compound_stats.get("rejected_no_layout_variation", 0) or 0) > 0
                and int(compound_stats.get("bottom_layout_trials_attempted_on_width_state", 0) or 0)
                + int(compound_stats.get("bottom_layout_trials_attempted_on_depth_state", 0) or 0)
                == 0
            ):
                hints.append("layout_variation_rejects_only_no_eval_attempts")
            elif int(compound_stats.get("rejected_eval_cap_or_none", 0) or 0) > 0:
                hints.append("eval_cap_or_noop_blocked_all_successful_compound_evals")
            compound_stats["compound_zero_generation_hints"] = hints
    else:
        compound_stats["compound_stage_skipped_reason"] = "geometry_lock_or_efficiency_reduction"

    filtered: list[dict] = []
    for candidate in candidates:
        if candidate is None or _updates_match_state(state, candidate.get("updates") or {}):
            continue
        if not _candidate_materially_improves(seed_candidate, candidate):
            continue
        bu = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
        if bu is None:
            continue
        ok_pf, rsn_pf = _bottom_recommendation_prefilter_ok(seed_candidate, candidate, state)
        if not ok_pf:
            if candidate.get("recommendation_compound"):
                compound_stats["rejected_score_inferior"] = int(
                    compound_stats.get("rejected_score_inferior", 0) or 0,
                ) + 1
            _log_design_reco_candidate_rank(
                domain="bending",
                event="rejected",
                candidate=candidate,
                reason=str(rsn_pf),
            )
            continue
        filtered.append(candidate)

    if efficiency_reduction_only:
        fg: list[dict] = []
        for candidate in filtered:
            if _candidate_is_growth_move(seed_candidate, candidate):
                _log_efficiency_growth_rejection(
                    candidate_family="bottom_reo",
                    seed_candidate=seed_candidate,
                    candidate=candidate,
                )
                continue
            fg.append(candidate)
        filtered = fg
        _merge_design_guide_rank_trace(
            {
                "efficiency_bottom_ranked_after_growth_filter": [
                    str(c.get("label") or "") for c in filtered[:16]
                ],
            },
        )

    filtered = _collapse_bottom_geometry_width_depth_trials(
        filtered,
        state=state,
        seed_candidate=seed_candidate,
        mode_config=mode_config,
        efficiency_reduction_only=efficiency_reduction_only,
        runtime=runtime.selector,
    )
    _emit_bottom_reo_filter_boundary_trace(
        state=state,
        candidates=list(candidates),
        filtered=list(filtered),
    )

    compound_kept_count = sum(1 for c in filtered if c.get("recommendation_compound"))
    _compound_stage_payload = dict(compound_stats)
    _compound_stage_payload["compound_candidates_kept_count"] = compound_kept_count
    _compound_stage_payload["compound_trace_sample"] = compound_trace_log[:48]
    _merge_design_guide_rank_trace(
        {
            "bottom_recommendation_compound_stage": _compound_stage_payload,
        },
    )

    if _BOTTOM_RECOMMENDATION_DEBUG_PROBE:
        _agent_debug_log(
            "Bottom recommendation candidate pool",
            {
                "raw_count": len(candidates),
                "after_improvement_filter": len(filtered),
            },
            location="inputs_page.py:_compute_bottom_reo_recommendation:filter",
            hypothesis_id="H_DESIGN_RECO_RANK",
        )

    if not filtered:
        _emit_bottom_reo_readiness_trace(
            state=state,
            candidates=list(candidates),
            filtered=[],
            ranked=[],
            selected=None,
            status="no_result",
            return_reason="no_filtered_candidates",
            result=None,
        )
        _agent_debug_log(
            "Completed bottom recommendation compute",
            {
                "found_recommendation": False,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
            },
            location="inputs_page.py:_compute_bottom_reo_recommendation:end",
            hypothesis_id="H19",
        )
        return None

    for cand in filtered:
        _annotate_bottom_reo_candidate_deltas(cand, seed_candidate, state)
    for cand in filtered:
        if cand.get("score") is None:
            cand["score"] = _score_auto_design_candidate(cand, mode_config, seed_candidate)
    for cand in filtered:
        _annotate_candidate_target_band_metrics(cand, mode_config)
    # Ranking consumes the candidate engineering surface, not the page-local
    # optimisation-score annotation. Keep the annotation beside the ranking
    # call and restore it by identity for the unchanged downstream selector.
    ranking_candidates: list[dict[str, Any]] = []
    score_by_identity: dict[str, Any] = {}
    for candidate in filtered:
        ranking_candidate = dict(candidate)
        identity = str(
            ranking_candidate.get("candidate_id")
            or ranking_candidate.get("source_candidate_id")
            or ""
        )
        score_by_identity[identity] = ranking_candidate.pop("score", None)
        ranking_candidate.pop("_score_components", None)
        ranking_candidates.append(ranking_candidate)
    ranked_bottom = _keep_top_candidates(
        ranking_candidates,
        mode_config,
        limit=min(16, len(ranking_candidates)),
    )
    for ranked_candidate in ranked_bottom:
        identity = str(
            ranked_candidate.get("candidate_id")
            or ranked_candidate.get("source_candidate_id")
            or ""
        )
        if identity in score_by_identity:
            ranked_candidate["score"] = score_by_identity[identity]

    best = _pick_best_bottom_recommendation_by_selector(
        ranked_bottom,
        state=state,
        seed_candidate=seed_candidate,
        mode_config=mode_config,
        runtime=runtime.selector,
    )
    best = _maybe_prefer_compound_over_pure_geometry(
        best,
        ranked_bottom,
        state=state,
        seed_candidate=seed_candidate,
        mode_config=mode_config,
    )
    if best:
        _annotate_candidate_target_band_metrics(best, mode_config)
        _br_pool = [c for c in filtered if c.get("candidate_reaches_target_band")]
        best["winning_candidate_post_util"] = best.get("candidate_post_util")
        best["winning_candidate_reaches_target_band"] = best.get("candidate_reaches_target_band")
        best["winning_candidate_distance_to_target_band"] = best.get("candidate_distance_to_target_band")
        best["winning_candidate_selected_because_reaches_band"] = bool(_br_pool) and bool(
            best.get("candidate_reaches_target_band")
        )
    if not best or _updates_match_state(state, best.get("updates", {})):
        _agent_debug_log(
            "Completed bottom recommendation compute",
            {
                "found_recommendation": False,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
            },
            location="inputs_page.py:_compute_bottom_reo_recommendation:end",
            hypothesis_id="H19",
        )
        return None
    if efficiency_reduction_only and _candidate_is_growth_move(seed_candidate, best):
        _log_efficiency_growth_rejection(
            candidate_family="bottom_reo",
            seed_candidate=seed_candidate,
            candidate=best,
            extra={"stage": "post_selector_guard"},
        )
        _agent_debug_log(
            "Completed bottom recommendation compute",
            {
                "found_recommendation": False,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
                "reason": "growth_blocked_efficiency_reduction",
            },
            location="inputs_page.py:_compute_bottom_reo_recommendation:end",
            hypothesis_id="H19",
        )
        return None
    arrangement = dict(best.get("arrangement") or {})
    required_ast = 0.0
    if arrangement:
        selected_bending = _evaluate_bending_with_bottom_state(state, arrangement)
        if selected_bending:
            required_ast = float(_required_ast_for_arrangement(state, {
                "Ast_bot": float(best.get("actual_ast", 0.0) or 0.0),
                "db_bot": float(selected_bending.get("db_bot", 0.0) or 0.0),
                "nb_bot": int(selected_bending.get("nb_bot", 0) or 0),
                "d_centroid": float(selected_bending.get("d_centroid", 0.0) or 0.0),
            }))
    if _ACTIVE_GUIDANCE_RECO_TRACE is not None:
        seed_bu = ((seed_candidate.get("overview") or {}).get("utils") or {}).get("bending")
        _append_design_guide_reco_trace(
            {
                "domain": "bending",
                "event": "final_selected",
                "candidate_label": str(best.get("label") or ""),
                "candidate_type": (
                    "compound_geometry_bottom"
                    if best.get("recommendation_compound")
                    else (
                        "geometry_trial"
                        if best.get("recommendation_geometry_trial")
                        else "bottom_reo"
                    )
                ),
                "updates": dict(best.get("updates") or {}),
                "score": best.get("score"),
                "util_before": float(seed_bu) if seed_bu is not None else None,
                "util_after": float(
                    (best.get("overview") or {}).get("utils", {}).get("bending", 0.0) or 0.0
                ),
            }
        )
    ss = dict(seed_candidate.get("state") or {})
    bs = dict(best.get("state") or {})
    seed_D = float(seed_candidate.get("depth", _float_from_state(ss, "D", 0.0)) or _float_from_state(ss, "D", 0.0))
    best_D = float(best.get("depth", _float_from_state(bs, "D", 0.0)) or _float_from_state(bs, "D", 0.0))
    seed_b = float(seed_candidate.get("width", _design_width_value(ss)) or _design_width_value(ss))
    best_b = float(best.get("width", _design_width_value(bs)) or _design_width_value(bs))
    seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    best_ast = float(best.get("Ast_bot", 0.0) or 0.0)
    band_reachers = [c for c in filtered if c.get("candidate_reaches_target_band")]
    one_click_available = len(band_reachers) > 0
    _merge_design_guide_rank_trace(
        {
            "bottom_recommendation_pick": {
                "delta_D_mm": round(best_D - seed_D, 3),
                "delta_b_mm": round(best_b - seed_b, 3),
                "delta_Ast_bot": round(best_ast - seed_ast, 3),
                "geometry_trial": bool(best.get("recommendation_geometry_trial")),
                "label": str(best.get("label") or ""),
                "winning_candidate_is_compound": bool(best.get("recommendation_compound")),
                "winning_candidate_subfamilies": list(best.get("subfamilies") or []),
                "winning_candidate_family_tag": best.get("recommendation_family_tag"),
                "winning_candidate_delta_b_mm": best.get("delta_b_mm"),
                "winning_candidate_delta_D_mm": best.get("delta_D_mm"),
                "winning_candidate_delta_Ast_bot": best.get("delta_Ast_bot"),
                "winning_candidate_post_util": best.get("candidate_post_util"),
                "winning_candidate_reaches_target_band": best.get("candidate_reaches_target_band"),
                "winning_candidate_distance_to_target_band": best.get("candidate_distance_to_target_band"),
                "winning_candidate_selected_because_reaches_band": best.get(
                    "winning_candidate_selected_because_reaches_band",
                ),
                "one_click_convergence_available": one_click_available,
                "one_click_convergence_reason": (
                    "at_least_one_compliant_candidate_reaches_target_band_in_one_move"
                    if one_click_available
                    else "no_compliant_candidate_reaches_target_band_in_one_move"
                ),
                "local_step_selected_only_because_no_band_reaching_candidate": (
                    any(bool(c.get("is_compliant")) for c in filtered) and not one_click_available
                ),
                "evaluated_candidates_band_preview": [
                    {
                        "label": str(c.get("label") or "")[:80],
                        "candidate_post_util": c.get("candidate_post_util"),
                        "candidate_reaches_target_band": c.get("candidate_reaches_target_band"),
                        "candidate_distance_to_target_band": c.get("candidate_distance_to_target_band"),
                    }
                    for c in filtered[:24]
                ],
            },
        }
    )
    disp_label = str(best.get("label") or "")
    if best.get("recommendation_compound"):
        disp_label = str(best.get("guidance_recommendation_title") or disp_label)
    gcl = _build_bottom_reo_guidance_change_lines_for_updates(state, dict(best.get("updates") or {}))
    result_payload = {
        "arrangement": arrangement,
        "updates": dict(best.get("updates") or {}),
        "actual_ast": float(best.get("actual_ast", 0.0) or 0.0),
        "required_ast": required_ast,
        "util": float(best.get("overview", {}).get("utils", {}).get("bending", 0.0) or 0.0),
        "label": disp_label,
        "score": float(best.get("score", 0.0) or 0.0),
        "recommendation_compound": bool(best.get("recommendation_compound")),
        "subfamilies": list(best.get("subfamilies") or []),
        "recommendation_family_tag": best.get("recommendation_family_tag"),
        "guidance_recommendation_title": best.get("guidance_recommendation_title"),
        "delta_b_mm": float(best.get("delta_b_mm") or 0.0),
        "delta_D_mm": float(best.get("delta_D_mm") or 0.0),
        "delta_Ast_bot": float(best.get("delta_Ast_bot") or 0.0),
        "guidance_change_lines": gcl,
    }
    _emit_bottom_reo_readiness_trace(
        state=state,
        candidates=list(candidates),
        filtered=list(filtered),
        ranked=list(ranked_bottom),
        selected=best,
        status="selected",
        return_reason=None,
        result=result_payload,
    )
    return result_payload


def _compute_shear_recommendation(
    state: dict,
    *,
    runtime: ShearRecommendationRuntime,
) -> dict | None:
    _ACTIVE_GUIDANCE_RECO_TRACE = runtime.trace.active_recommendation_trace
    _append_design_guide_reco_trace = runtime.trace.append_recommendation_trace
    _build_design_actions_context = runtime.evaluation.build_design_actions_context
    _collect_design_overview = runtime.evaluation.collect_design_overview
    _evaluate_candidate_fast = runtime.evaluation.evaluate_candidate_fast
    _invalid_shear_spacing_change_without_activation = (
        lambda base_state, candidate_state, *, source: _invalid_shear_spacing_change_without_activation_owned(
            base_state,
            candidate_state,
            source=source,
            agent_debug_log=runtime.trace.agent_debug_log,
        )
    )
    _iter_shear_recommendation_ladder_states = (
        lambda current_state, *, conservative: _iter_shear_recommendation_ladder_states_typed(
            current_state,
            conservative=conservative,
        )
    )
    _log_design_reco_candidate_rank = runtime.trace.log_candidate_rank
    _log_efficiency_growth_rejection = runtime.trace.log_efficiency_growth_rejection
    _log_severe_shear_escalation = (
        lambda **kwargs: _log_severe_shear_escalation_typed(
            agent_debug_log=runtime.trace.agent_debug_log,
            enabled=runtime.trace.candidate_debug_enabled,
            **kwargs,
        )
    )
    _log_shear_candidate_debug = lambda **kwargs: log_shear_candidate_debug(
        agent_debug_log=runtime.trace.agent_debug_log,
        enabled=runtime.trace.candidate_debug_enabled,
        **kwargs,
    )
    _log_shear_ladder_attempt = (
        lambda state, **kwargs: log_shear_ladder_attempt(
            state,
            agent_debug_log=runtime.trace.agent_debug_log,
            enabled=True,
            **kwargs,
        )
    )
    _merge_design_guide_rank_trace = runtime.trace.merge_rank_trace
    def _score_auto_design_candidate(
        candidate: dict,
        mode_config: dict,
        seed_candidate: dict,
    ) -> float:
        components = _score_auto_design_candidate_components(
            candidate,
            mode_config,
            seed_candidate,
            runtime=runtime.scoring,
        )
        candidate["_score_components"] = dict(components)
        return float(components.get("total_score", 0.0) or 0.0)

    def candidate_materially_worsens(
        new_candidate: dict,
        old_candidate: dict,
        mode_config: dict,
        *,
        phase: str,
    ) -> bool:
        return _candidate_materially_worsens(
            new_candidate,
            old_candidate,
            mode_config,
            phase=phase,
            runtime=runtime.scoring,
        )
    evaluate_candidate_full = runtime.evaluation.evaluate_candidate_full
    state = _guidance_state_snapshot(state)
    design_context = _build_design_actions_context(state)
    overview = _collect_design_overview(state, context=design_context)
    if not _recommendation_search_allowed(state, overview):
        return None
    actions = design_context.get("actions") or {}
    cleanup_rec = try_shear_no_demand_cleanup_recommendation(
        state,
        overview,
        actions,
        evaluate_candidate_full=evaluate_candidate_full,
        merge_rank_trace=_merge_design_guide_rank_trace,
    )
    if cleanup_rec is not None:
        return cleanup_rec
    _reco_gate = runtime.evaluation.combined_shear_truth_gate(
        state,
        overview=overview,
        efficiency_classification=None,
    )
    if bool(_reco_gate.get("combined_underdesign_shear_truth_block_active")):
        _merge_design_guide_rank_trace({"shear_recommendation_truth_gate": dict(_reco_gate)})
        return None
    if not _shear_change_is_relevant(overview, actions):
        return None
    mode_config = _design_mode_config(_design_optimisation_goal(state))
    seed_candidate = evaluate_candidate_full(state, source="shear_recommendation_seed")
    if not seed_candidate:
        return None
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    seed_shear_util = (((seed_candidate or {}).get("overview") or {}).get("utils") or {}).get("shear")
    try:
        baseline_su = float(seed_shear_util) if seed_shear_util is not None else None
    except (TypeError, ValueError):
        baseline_su = None
    severity_band = _shear_severity_band(seed_shear_util)
    family_audit: dict[str, list[dict]] = {}
    conservative = _shear_recommendation_overview_is_conservative_cleanup(overview)
    ladder_mode = "conservative" if conservative else "strengthening"
    if _shear_spacing_layout_must_not_trigger_strengthening(state, overview) and not conservative:
        _merge_design_guide_rank_trace(
            {"shear_recommendation_suppressed": {"reason": "spacing_layout_non_governing_sectional_pass"}},
        )
        return None
    cur_legs_log = _int_from_state(state, "lig_legs", 0)
    cur_s_log = _float_from_state(state, "s_lig", 0.0)
    leg_search_counts = _candidate_leg_counts(cur_legs_log, conservative=conservative)

    trial_states = _iter_shear_recommendation_ladder_states(state, conservative=conservative)
    seen_keys: set[tuple] = set()
    candidates: list[dict] = []

    for branch, candidate_state in trial_states:
        ck = _make_auto_design_candidate_key(candidate_state)
        if ck in seen_keys:
            _log_shear_ladder_attempt(
                state,
                ladder_mode=ladder_mode,
                branch=branch,
                lig_legs=cur_legs_log,
                s_lig=cur_s_log,
                proposed_updates=None,
                expected_util_after=None,
                decision="rejected",
                reason="duplicate_candidate_state",
            )
            continue
        seen_keys.add(ck)
        if _invalid_shear_spacing_change_without_activation(
            state,
            candidate_state,
            source="shear_recommendation",
        ):
            _log_shear_ladder_attempt(
                state,
                ladder_mode=ladder_mode,
                branch=branch,
                lig_legs=cur_legs_log,
                s_lig=cur_s_log,
                proposed_updates=None,
                expected_util_after=None,
                decision="rejected",
                reason="invalid_spacing_without_activation",
            )
            continue
        candidate = _evaluate_candidate_fast(
            candidate_state,
            seed_state=seed_candidate["state"],
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            source="shear_recommendation",
            label=_shear_state_label(candidate_state),
            action_type="apply_shear_recommendation",
        )
        pu = (candidate or {}).get("updates")
        eu = None
        if candidate:
            try:
                eu = float(((candidate.get("overview") or {}).get("utils") or {}).get("shear") or float("nan"))
                if math.isnan(eu):
                    eu = None
            except (TypeError, ValueError):
                eu = None
        ok, reason = _shear_ladder_validate_candidate(
            state,
            candidate,
            branch=branch,
            conservative=conservative,
            baseline_shear_util=None if conservative else baseline_su,
            runtime=runtime,
        )
        _log_shear_ladder_attempt(
            state,
            ladder_mode=ladder_mode,
            branch=branch,
            lig_legs=cur_legs_log,
            s_lig=cur_s_log,
            proposed_updates=dict(pu) if isinstance(pu, dict) else None,
            expected_util_after=eu,
            decision="accepted" if ok else "rejected",
            reason=reason,
        )
        if not ok or candidate is None:
            _log_shear_candidate_debug(
                source="shear_recommendation",
                candidate_state=candidate_state,
                candidate=candidate,
            )
            continue
        if not conservative and candidate_materially_worsens(candidate, seed_candidate, mode_config, phase="shear_recommendation"):
            _log_shear_ladder_attempt(
                state,
                ladder_mode=ladder_mode,
                branch=branch,
                lig_legs=cur_legs_log,
                s_lig=cur_s_log,
                proposed_updates=dict(candidate.get("updates") or {}),
                expected_util_after=eu,
                decision="rejected",
                reason="materially_worse_non_shear",
            )
            continue
        candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
        candidate["shear_candidate_type"] = _shear_candidate_type(state, candidate.get("state") or candidate_state)
        candidate["shear_ladder_branch"] = branch
        _log_shear_candidate_debug(
            source="shear_recommendation",
            candidate_state=candidate_state,
            candidate=candidate,
        )
        candidates.append(candidate)

    if not conservative and _severe_shear_failure(seed_shear_util) and candidates:
        existing_keys = {_make_auto_design_candidate_key(dict(candidate.get("state") or {})) for candidate in candidates}
        ranked_base = _combined_shear_seed_candidates(
            candidates,
            seed_candidate=seed_candidate,
            base_state=state,
            severity_band=severity_band,
            seed_shear_util=seed_shear_util,
            limit=8,
        )
        for base_candidate in ranked_base:
            for combined_state in _generate_secondary_bending_tightening_states(base_candidate, limit=3):
                combined_key = _make_auto_design_candidate_key(combined_state)
                if combined_key in existing_keys:
                    continue
                combined_candidate = _evaluate_candidate_fast(
                    combined_state,
                    seed_state=seed_candidate["state"],
                    context=context,
                    eval_cache=eval_cache,
                    metrics=metrics,
                    source="shear_recommendation_combined",
                    label=(
                        f"Combined: {_shear_state_label(combined_state)}"
                        f" + {_bottom_reo_state_label(combined_state)}"
                    ),
                    action_type="apply_shear_recommendation",
                )
                pu_c = (combined_candidate or {}).get("updates")
                eu_c = None
                if combined_candidate:
                    try:
                        eu_c = float(((combined_candidate.get("overview") or {}).get("utils") or {}).get("shear") or float("nan"))
                        if math.isnan(eu_c):
                            eu_c = None
                    except (TypeError, ValueError):
                        eu_c = None
                ok_c, reason_c = _shear_ladder_validate_candidate(
                    state,
                    combined_candidate,
                    branch="combined_secondary_bending",
                    conservative=False,
                    baseline_shear_util=baseline_su,
                    runtime=runtime,
                )
                _log_shear_ladder_attempt(
                    state,
                    ladder_mode=ladder_mode,
                    branch="combined_secondary_bending",
                    lig_legs=cur_legs_log,
                    s_lig=cur_s_log,
                    proposed_updates=dict(pu_c) if isinstance(pu_c, dict) else None,
                    expected_util_after=eu_c,
                    decision="accepted" if ok_c else "rejected",
                    reason=reason_c,
                )
                if not ok_c or combined_candidate is None:
                    continue
                if candidate_materially_worsens(combined_candidate, seed_candidate, mode_config, phase="shear_recommendation"):
                    _log_shear_ladder_attempt(
                        state,
                        ladder_mode=ladder_mode,
                        branch="combined_secondary_bending",
                        lig_legs=cur_legs_log,
                        s_lig=cur_s_log,
                        proposed_updates=dict(combined_candidate.get("updates") or {}),
                        expected_util_after=eu_c,
                        decision="rejected",
                        reason="materially_worse_non_shear",
                    )
                    continue
                combined_candidate["score"] = _score_auto_design_candidate(combined_candidate, mode_config, seed_candidate)
                combined_candidate["shear_candidate_type"] = "combined"
                combined_candidate["secondary_actions_combined"] = True
                combined_candidate["shear_ladder_branch"] = "combined_secondary_bending"
                candidates.append(combined_candidate)
                existing_keys.add(combined_key)

    if not candidates:
        _log_severe_shear_escalation(
            source="_compute_shear_recommendation",
            seed_candidate=seed_candidate,
            severity_band=severity_band,
            candidates=[],
            selected=None,
            family_audit=family_audit,
        )
        return None

    for cand in candidates:
        if cand.get("score") is None:
            cand["score"] = _score_auto_design_candidate(cand, mode_config, seed_candidate)

    eligible_shear: list[dict] = []
    for cand in candidates:
        ok_el, rsn_el = _shear_recommendation_prefinal_eligible(
            cand,
            state=state,
            conservative=conservative,
            baseline_su=None if conservative else baseline_su,
        )
        if ok_el:
            eligible_shear.append(cand)
        else:
            _log_design_reco_candidate_rank(
                domain="shear",
                event="rejected",
                candidate=cand,
                reason=str(rsn_el),
                util_before=None if conservative else baseline_su,
                util_after=_shear_util_from_overview_candidate(cand),
            )
    if conservative and _efficiency_reduction_profile_from_overview(overview):
        filtered_es: list[dict] = []
        for cand in eligible_shear:
            if _candidate_is_growth_move(seed_candidate, cand):
                _log_efficiency_growth_rejection(
                    candidate_family="shear",
                    seed_candidate=seed_candidate,
                    candidate=cand,
                )
                continue
            filtered_es.append(cand)
        eligible_shear = filtered_es
    if not eligible_shear:
        _log_severe_shear_escalation(
            source="_compute_shear_recommendation",
            seed_candidate=seed_candidate,
            severity_band=severity_band,
            candidates=candidates,
            selected=None,
            family_audit=family_audit,
        )
        return None

    _, target_hi, _ = _resolved_efficiency_target_band(
        mode_config,
        goal=_design_optimisation_goal(state),
    )
    shortlisted_shear = _shortlist_smallest_successful_shear_candidates(
        eligible_shear,
        state,
        target_hi=target_hi,
    )
    shortlist_used = len(shortlisted_shear) < len(eligible_shear)
    shortlist_best_magnitude = (
        _shear_change_magnitude(shortlisted_shear[0], state)
        if shortlisted_shear else None
    )
    selector_pool = [
        c for c in shortlisted_shear
        if _candidate_is_within_smallest_fix_band(c, shortlist_best_magnitude, state)
    ]
    if not selector_pool:
        selector_pool = list(shortlisted_shear)
    selector_pool_band_reachers = [
        c for c in selector_pool
        if bool(c.get("candidate_reaches_target_band"))
    ]
    selector_pool_best_post_util = min(
        (
            float(c.get("candidate_post_util"))
            for c in selector_pool
            if c.get("candidate_post_util") is not None
        ),
        default=None,
    )
    reintroduced_larger_candidates: list[dict] = []
    for cand in shortlisted_shear:
        if cand in selector_pool:
            continue
        cand_reaches_band = bool(cand.get("candidate_reaches_target_band"))
        cand_post_util = cand.get("candidate_post_util")
        materially_better = False
        if cand_post_util is not None and selector_pool_best_post_util is not None:
            try:
                materially_better = float(cand_post_util) < float(selector_pool_best_post_util) - 0.05
            except (TypeError, ValueError):
                materially_better = False
        only_band_candidate = cand_reaches_band and not selector_pool_band_reachers
        if materially_better or only_band_candidate:
            reintroduced_larger_candidates.append(cand)
    if reintroduced_larger_candidates:
        selector_pool.extend(reintroduced_larger_candidates)
    ranked_shear = _keep_top_candidates(selector_pool, mode_config, limit=min(24, len(selector_pool)))

    best = pick_best_shear_recommendation(
        ranked_shear,
        state=state,
        seed_candidate=seed_candidate,
        mode_config=mode_config,
        conservative=conservative,
        baseline_su=None if conservative else baseline_su,
        log_candidate_rank=_log_design_reco_candidate_rank,
    )
    if not best:
        _log_severe_shear_escalation(
            source="_compute_shear_recommendation",
            seed_candidate=seed_candidate,
            severity_band=severity_band,
            candidates=candidates,
            selected=None,
            family_audit=family_audit,
        )
        return None
    shear_preview = _evaluate_shear_with_state(best.get("state") or state) or {}
    _log_severe_shear_escalation(
        source="_compute_shear_recommendation",
        seed_candidate=seed_candidate,
        severity_band=severity_band,
        candidates=candidates,
        selected=best,
        family_audit=family_audit,
    )
    if _ACTIVE_GUIDANCE_RECO_TRACE is not None:
        _append_design_guide_reco_trace(
            {
                "domain": "shear",
                "event": "final_selected",
                "candidate_label": str(best.get("label") or ""),
                "branch": str(best.get("shear_ladder_branch") or ""),
                "candidate_type": str(best.get("shear_candidate_type") or ""),
                "updates": dict(best.get("updates") or {}),
                "score": best.get("score"),
                "util_before": None if conservative else baseline_su,
                "util_after": _shear_util_from_overview_candidate(best),
                "shear_leg_search_counts": list(leg_search_counts),
                "shear_leg_search_mode": ladder_mode,
                "shear_best_candidate_leg_count": best.get("shear_candidate_leg_count"),
                "shear_best_candidate_leg_delta": best.get("shear_candidate_leg_delta"),
                "shear_best_candidate_practicality_penalty": best.get("shear_candidate_total_practicality_penalty"),
                "shear_smallest_fix_shortlist_used": bool(shortlist_used),
                "shear_smallest_fix_shortlist_count": int(len(shortlisted_shear)),
                "shear_smallest_fix_best_magnitude": shortlist_best_magnitude,
                "shear_selector_smallest_mag": shortlist_best_magnitude,
                "shear_selector_pool_count": len(selector_pool),
                "shear_selector_larger_candidates_reintroduced_count": len(reintroduced_larger_candidates),
                "shear_selected_change_magnitude": _shear_change_magnitude(best, state),
            }
        )
    return {
        "updates": dict(best.get("updates") or {}),
        "label": str(best.get("label") or ""),
        "util": float(best.get("overview", {}).get("utils", {}).get("shear", 0.0) or 0.0),
        "web_util": float(shear_preview.get("web_util", 0.0) or 0.0),
        "phi_vu": float(shear_preview.get("phi_vu", 0.0) or 0.0),
        "veq": float(shear_preview.get("veq", 0.0) or 0.0),
        "score": float(best.get("score", 0.0) or 0.0),
        "severity_band": severity_band,
        "candidate_type": str(best.get("shear_candidate_type") or _shear_candidate_type(state, best.get("state") or state)),
        "shear_leg_search_counts": list(leg_search_counts),
        "shear_leg_search_mode": "conservative" if conservative else "strengthening",
        "shear_best_candidate_leg_count": best.get("shear_candidate_leg_count"),
        "shear_best_candidate_leg_delta": best.get("shear_candidate_leg_delta"),
        "shear_best_candidate_practicality_penalty": best.get("shear_candidate_total_practicality_penalty"),
        "shear_smallest_fix_shortlist_used": bool(shortlist_used),
        "shear_smallest_fix_shortlist_count": int(len(shortlisted_shear)),
        "shear_smallest_fix_best_magnitude": shortlist_best_magnitude,
        "shear_selector_smallest_mag": shortlist_best_magnitude,
        "shear_selector_pool_count": len(selector_pool),
        "shear_selector_larger_candidates_reintroduced_count": len(reintroduced_larger_candidates),
        "shear_selected_change_magnitude": _shear_change_magnitude(best, state),
    }
