"""Incremental permanent provider for the one-click transaction runtime."""

from __future__ import annotations

from functools import partial
import copy
import math
import os
from types import SimpleNamespace
from typing import Any

from application.target_band_domain_policy import (
    resolve_target_band_candidate_domains_for_updates,
)
from application.target_band_evaluation import (
    resolve_candidate_domain_max_distance,
    resolve_candidate_domain_score,
    resolve_candidate_domain_total_distance,
    resolve_candidate_in_target_band,
    resolve_candidate_required_domain_progress,
    resolve_candidate_required_domains_satisfied,
    resolve_candidate_step_improves,
    resolve_target_band_exhaustion_refinement_allowed,
    resolve_target_band_next_hop_precheck,
)
from application.target_band_refinement_policy import (
    select_best_target_band_refinement_candidate,
)
from inputs_application.engineering_predicates import (
    parse_util_value,
    shear_demands_negligible,
    shear_reinforcement_is_active,
)
from application.candidate_delta_policy import diff_candidate_state_updates
from inputs_application.candidate_metrics import int_from_state
from inputs_application.geometry_search_policy import (
    build_auto_design_context,
    design_mode_config,
    design_optimisation_goal,
)
from inputs_application.guidance_entrypoint import (
    GuidanceEntrypointRuntime,
    compute_inputs_guidance,
)
from inputs_application.design_guide_fingerprint import (
    design_guide_fingerprint,
)
from inputs_application.recommendation_envelope import (
    build_recommendation_envelope,
)
from inputs_application.one_click_policies import (
    one_click_directional_tie_key,
    one_click_exhaustion_next_hop_allowed,
    one_click_has_unresolved_spacing_envelope_fail,
    rescue_bootstrap_partial_commit_allowed,
    stage3_remaining_issue_class_from_overview_state,
)
from inputs_application.one_click_candidate_policy import (
    candidate_failure_coverage_summary,
    current_design_guide_fail_fingerprint,
    design_guide_candidate_family,
    evaluate_auto_design_candidate,
    governing_focus_from_overview,
    one_click_candidate_is_shear_governing_for_prune,
    rescue_mode_eval_for_result,
    rescue_mode_validate_seed,
    shear_preview_for_updates,
)
from inputs_application.one_click_session import (
    clear_auto_design_runtime_latches,
    consume_auto_design_invoke_after_solver_entry_confirmed,
    invalidate_design_guide_caches,
    normalise_invalid_shear_state_updates,
    pop_inputs_widget_keys_for_shared_updates,
    record_one_click_shear_publish_audit,
    restore_shared_state_snapshot,
    sanitize_shared_update_bundle,
    set_one_click_run_feedback,
    set_design_guide_live_breadcrumb,
    set_shared_updates,
    should_run_auto_design,
)
from inputs_application.recommendation_evaluation import (
    effective_bottom_design_state,
    evaluate_shear_with_state,
)
from inputs_application.recommendation_support import design_width_value
from inputs_application.state_utils import (
    bottom_reo_state_label,
    float_from_state,
    guidance_state_snapshot,
    shared_state_snapshot,
    updates_match_state,
)
from inputs_application.one_click_tracing import (
    agent_debug_log,
    append_design_guide_trace,
    auto_design_invoke_debug_snapshot,
    design_guide_trace_compare_meta,
    design_guide_tracer_path,
    design_guide_tracer_verbose_log,
    new_design_guide_trace_run_id,
    trace_compact_overview_dict,
    trace_compact_shared_geom_reo,
    tracer_one_click_action_source_summary,
    stage3_final_published_shear_truth_bundle,
)
from inputs_application.shear_truth_policy import (
    overlay_current_normalized_shear_truth,
)
from inputs_application.shear_recommendation_selector import (
    _candidate_objective_util,
)
from inputs_application.policy_constants import (
    EFFICIENCY_TARGET_UTIL_MAX,
    EFFICIENCY_TARGET_UTIL_MIN,
)
from inputs_page_modules.auto_design_compute import (
    _LEGACY_AUTO_DESIGN_NAMES,
)
from inputs_page_modules.design_guide.state_coherence import (
    _canonical_pack_is_valid,
    _coherence_debug_fields,
    _design_state_coherence_check,
)
from inputs_page_modules.design_guide.primary_one_click_validation import (
    _candidate_is_valid_primary_one_click,
)
from inputs_application.local_cleanup_acceptance import (
    build_local_cleanup_acceptance_fingerprint,
)
from inputs_application.canonical_runtime_contracts import (
    CanonicalDesignStatePackRuntime,
)
from inputs_page_modules.app_bridge.canonical_design_state_pack import (
    _build_canonical_design_state_pack_for_app_bridge,
)
from inputs_application.canonical_runtime_contracts import (
    CanonicalConvenienceResyncRuntime,
)
from inputs_page_modules.app_bridge.canonical_convenience_resync import (
    _apply_canonical_convenience_resync_to_shared,
    _canonical_convenience_fields_from_state,
    convenience_scalar_differs,
)
from inputs_page_modules.widgets.shear_widget_seed import (
    request_shear_widget_seed_from_shared,
)
from inputs_page_modules.design_guide.transient_clear import (
    clear_design_guide_transient_ui_state,
)
from inputs_application.one_click_commit_policy import (
    one_click_commit_audit_passes,
    one_click_committable_candidate_eval,
    one_click_post_commit_audit,
)
from inputs_application.one_click_optimization_policy import (
    generate_smaller_geometry_variants,
    one_click_attach_eval_target_domains,
    one_click_build_user_visible_no_action_fields,
    one_click_in_band_shear_cleanup_candidate_allowed,
    one_click_in_band_shear_cleanup_deferral,
    one_click_mixed_direction_classification,
    one_click_mixed_direction_rank_adjustment,
    one_click_seed_target_domains_from_eval,
    one_click_still_materially_under_target,
    one_click_tightening_mode_active,
    one_click_trace_eval_domain_payload,
    one_click_update_direction_summary,
)
from inputs_application.guidance_runtime_config import (
    REO_BAR_DIAS,
    REO_SPACINGS,
)
from inputs_application.geometry_search_policy import geometry_lock_enabled
from inputs_application.recommendation_primitives import (
    activation_shear_state,
    shear_candidate_type,
)
from inputs_application.recommendation_support import (
    resolve_geometry_width_context,
    shear_severity_band,
)
from inputs_application.one_click_rescue_policy import (
    RESCUE_SEED_LIBRARY,
    rescue_mode_should_enter,
)
from inputs_application.one_click_next_hop import (
    OneClickNextHopRuntime,
    one_click_best_next_hop_improving_candidate,
    one_click_budget_stop_has_better_next_hop,
)
from inputs_page_modules.design_guide.efficiency_tightening_state import (
    compute_efficiency_tightening_state,
)
from inputs_page_modules.guidance_compute import (
    _application_generate_cleanup_candidates,
    _application_generate_less_bottom_reo_variants,
    _application_generate_less_shear_reo_variants,
    _application_generate_simpler_layout_variants,
    _application_shear_cleanup_possible,
    _guidance_action_updates,
    _requires_full_coverage_for_primary_one_click,
)
from inputs_page_modules.recommendation_compute import (
    _generate_local_bottom_arrangements,
)
from inputs_application.shear_escalation_runtime import (
    ShearEscalationRuntime,
    generate_escalated_shear_states,
)
from inputs_page_modules.design_guide.shear_governing_candidates import (
    ShearGoverningCandidateRuntime,
    _generate_shear_governing_candidates,
)
from inputs_page_modules.design_guide.governing_domain_tightening_candidates import (
    GoverningDomainTighteningRuntime,
    _generate_tightening_candidates_for_governing_domain,
)
from inputs_page_modules.design_guide.resolved_candidate_guidance_item import (
    _ensure_guidance_item_resolved_candidate_payload,
)
from inputs_page_modules.app_bridge.actionable_guidance_candidates import (
    ActionableGuidanceCollectionRuntime,
    _one_click_collect_actionable_guidance_candidates,
)
from inputs_application.candidate_identity import (
    make_auto_design_candidate_key as _make_auto_design_candidate_key,
)
from inputs_page_modules.design_guide.candidate_family_classification import (
    _candidate_family_matches_governing_domain,
)
from inputs_page_modules.design_overview_adapter import (
    build_design_actions_context,
    collect_design_overview,
)
from inputs_page_modules.recommendation_candidate_adapter import (
    evaluate_full_candidate,
)
from inputs_application.local_cleanup_acceptance import (
    DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS,
)
from inputs_application.summary_state_runtime import (
    InputsSummaryStateRuntime,
    resolve_inputs_summary_state,
)
from state_and_helpers import (
    BEAM_STATUS_FAIL,
    SHARED_DEFAULTS,
    finalize_auto_design_publish,
    persist_active_beam_from_shared,
    publish_normalized_final_shear_truth_to_session,
    set_shared,
)
from shear_checks_helpers import build_shear_check_rows_from_state


def _one_click_domain_needs_cleanup_owned(
    eval_obj: dict | None,
    domain: str,
    mode_config: dict,
) -> bool:
    score = resolve_candidate_domain_score(
        eval_obj,
        domain,
        mode_config,
        default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
        default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
        fail_status=BEAM_STATUS_FAIL,
    )
    return bool(score.get("pass") and score.get("under"))


def _candidate_in_target_band_owned(
    candidate: dict,
    mode_config: dict,
) -> bool:
    return resolve_candidate_in_target_band(
        candidate,
        mode_config,
        default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
        default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
        fail_status=BEAM_STATUS_FAIL,
        optimisation_goal_resolver=design_optimisation_goal,
    )


def _candidate_target_domains_for_band_owned(
    candidate: dict,
) -> list[str]:
    if not isinstance(candidate, dict):
        return []
    raw = candidate.get("target_domains_for_band")
    if not isinstance(raw, list) or not raw:
        return []
    output = []
    seen = set()
    for item in raw:
        domain = str(item or "").strip().lower()
        if domain in ("flexure", "ductility", "bottom", "bottom_reo"):
            domain = "bending"
        if domain not in ("bending", "shear") or domain in seen:
            continue
        output.append(domain)
        seen.add(domain)
    return output


def _candidate_target_band_distance_owned(
    candidate: dict,
    mode_config: dict,
) -> float:
    if _candidate_target_domains_for_band_owned(candidate):
        return float(
            resolve_candidate_domain_max_distance(
                candidate,
                mode_config,
                default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
                default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
                fail_status=BEAM_STATUS_FAIL,
                optimisation_goal_resolver=design_optimisation_goal,
            )
        )
    util = float(_candidate_objective_util(candidate))
    low = float(
        mode_config.get(
            "target_util_min",
            EFFICIENCY_TARGET_UTIL_MIN,
        )
        or EFFICIENCY_TARGET_UTIL_MIN
    )
    high = float(
        mode_config.get(
            "target_util_max",
            EFFICIENCY_TARGET_UTIL_MAX,
        )
        or EFFICIENCY_TARGET_UTIL_MAX
    )
    if util != util:
        return float("inf")
    if low <= util <= high:
        return 0.0
    return low - util if util < low else util - high


def _is_valid_progress_while_failing_owned(
    new_candidate: dict | None,
    old_candidate: dict | None,
) -> bool:
    if not new_candidate or not old_candidate:
        return False
    if bool(new_candidate.get("is_compliant")):
        return True

    def failures(candidate: dict) -> set[str]:
        statuses = (
            (candidate.get("overview") or {}).get("statuses", {}) or {}
        )
        return {
            key.replace("_", " ")
            for key in ("bending", "shear", "crack", "deflection")
            if str(statuses.get(key, "") or "") == "FAIL"
        }

    old_failed = failures(old_candidate)
    new_failed = failures(new_candidate)
    old_util = float(old_candidate.get("worst_util", 999.0) or 999.0)
    new_util = float(new_candidate.get("worst_util", 999.0) or 999.0)
    if new_failed != old_failed and len(new_failed) < len(old_failed):
        return True
    if new_util < old_util - 0.01:
        return True
    return _candidate_state_signature_owned(
        new_candidate
    ) != _candidate_state_signature_owned(old_candidate)


def _candidate_state_signature_owned(candidate: dict | None) -> tuple:
    if not candidate:
        return ()
    return _make_auto_design_candidate_key(
        guidance_state_snapshot(dict(candidate.get("state") or {}))
    )


def _rescue_mode_default_debug_owned() -> dict:
    return {
        "rescue_mode_entered": False,
        "rescue_mode_entry_reason": None,
        "rescue_mode_family": None,
        "rescue_mode_tier_requested": None,
        "rescue_mode_tier_used": None,
        "rescue_mode_seed_key": None,
        "rescue_mode_seed_legal": None,
        "rescue_mode_seed_illegal_reason": None,
        "rescue_mode_fallback_count": 0,
        "rescue_mode_ineffective_seeds": [],
        "rescue_mode_effective_seed_found": False,
        "rescue_mode_exit_reason": None,
    }


def _rescue_mode_seed_order_owned(
    requested_tier: str | None,
) -> list[str]:
    order = ("medium", "high", "very_high", "extreme")
    if requested_tier not in order:
        return []
    if requested_tier == "extreme":
        return ["very_high", "extreme"]
    index = order.index(requested_tier)
    result = list(order[index:])
    if "extreme" in result and requested_tier != "very_high":
        return [
            tier for tier in result if tier != "extreme"
        ] + ["extreme"]
    return result


def _one_click_strict_target_band_ok_owned(
    overview: dict | None,
    mode_config: dict,
) -> bool:
    if not isinstance(overview, dict):
        return False
    try:
        low = float(
            mode_config.get(
                "target_util_min",
                EFFICIENCY_TARGET_UTIL_MIN,
            )
            or EFFICIENCY_TARGET_UTIL_MIN
        )
        high = float(
            mode_config.get(
                "target_util_max",
                EFFICIENCY_TARGET_UTIL_MAX,
            )
            or EFFICIENCY_TARGET_UTIL_MAX
        )
        worst = float(
            overview.get(
                "governing_util",
                overview.get("worst_util", 0.0),
            )
            or 0.0
        )
    except (TypeError, ValueError):
        return False
    statuses = dict(overview.get("statuses") or {})
    any_fail = any(
        value == BEAM_STATUS_FAIL
        or str(value or "").strip().upper() == "FAIL"
        for value in statuses.values()
    )
    return bool(not any_fail and low <= worst <= high)


def _normalise_shear_shared(
    *,
    source: str,
    shared_snapshot: Any,
    normalise_updates: Any,
    set_shared_fn: Any,
) -> bool:
    current_state = shared_snapshot()
    updates = normalise_updates(current_state, {}, source=source)
    if not updates:
        return False
    for key, value in updates.items():
        set_shared_fn(key, value, source=source)
    return True


def build_partial_one_click_runtime_provider(
    *,
    st_module: Any,
    guidance_runtime: GuidanceEntrypointRuntime,
) -> SimpleNamespace:
    session_state = st_module.session_state
    auto_invoke_key = "_auto_design_auto_invoke"
    request_timestamp_key = "_auto_design_requested_at_ts"
    request_source_key = "_auto_design_request_source"
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tracer_path = partial(
        design_guide_tracer_path,
        base_directory=repo_root,
    )
    debug_log = partial(
        agent_debug_log,
        log_path=(
            "/Users/jonathonleggo/Library/CloudStorage/"
            "OneDrive-Personal/Documents/GitHub/complete-app/"
            ".cursor/debug.log"
        ),
    )
    tracer_verbose = partial(
        design_guide_tracer_verbose_log,
        session_state=session_state,
    )
    append_trace = partial(
        append_design_guide_trace,
        tracer_path_fn=tracer_path,
        tracer_verbose_log_fn=tracer_verbose,
        agent_debug_log_fn=debug_log,
    )
    guidance_action_updates = partial(
        _guidance_action_updates,
        runtime=guidance_runtime.compute_runtime.guidance_action_updates,
    )

    def resolve_item_updates(item: dict, *, state: dict | None = None) -> dict:
        action_type = str(item.get("action_type") or "").strip()
        payload = dict(item.get("action_payload") or item)
        return dict(
            guidance_action_updates(
                action_type,
                payload,
                state=state,
            )
            or {}
        )

    ensure_resolved_payload = partial(
        _ensure_guidance_item_resolved_candidate_payload,
        resolve_updates=resolve_item_updates,
    )
    actionable_collection_runtime = ActionableGuidanceCollectionRuntime(
        append_design_guide_trace=append_trace,
        compute_design_guidance_items=partial(
            compute_inputs_guidance,
            guidance_runtime,
        ),
        ensure_guidance_item_resolved_candidate_payload=(
            ensure_resolved_payload
        ),
        guidance_action_updates=guidance_action_updates,
    )
    generate_less_shear_variants = partial(
        _application_generate_less_shear_reo_variants,
        reo_spacings=tuple(float(value) for value in REO_SPACINGS),
        reo_bar_dias=tuple(int(value) for value in REO_BAR_DIAS),
        canonical_no_shear_spacing_mm=200.0,
    )
    generate_less_bottom_variants = partial(
        _application_generate_less_bottom_reo_variants,
        generate_local_bottom_arrangements=(
            _generate_local_bottom_arrangements
        ),
    )
    generate_simpler_variants = partial(
        _application_generate_simpler_layout_variants,
        generate_local_bottom_arrangements=(
            _generate_local_bottom_arrangements
        ),
    )
    shear_cleanup_possible = partial(
        _application_shear_cleanup_possible,
        reo_spacings=tuple(float(value) for value in REO_SPACINGS),
    )
    generate_cleanup_variants = partial(
        _application_generate_cleanup_candidates,
        generate_less_bottom_reo_variants=(
            generate_less_bottom_variants
        ),
        generate_simpler_layout_variants=generate_simpler_variants,
        generate_less_shear_reo_variants=generate_less_shear_variants,
        shear_cleanup_possible=shear_cleanup_possible,
    )
    collect_overview = partial(
        collect_design_overview,
        session_state=session_state,
    )
    evaluate_full = partial(
        evaluate_full_candidate,
        session_state=session_state,
    )
    overlay_shear_truth = partial(
        overlay_current_normalized_shear_truth,
        session_state=session_state,
    )
    domain_score = partial(
        resolve_candidate_domain_score,
        default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
        default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
        fail_status=BEAM_STATUS_FAIL,
    )
    eval_domain_scores = lambda eval_obj, mode_config: {
        domain: domain_score(eval_obj, domain, mode_config)
        for domain in _candidate_target_domains_for_band_owned(
            eval_obj or {}
        )
    }
    escalated_shear_runtime = ShearEscalationRuntime(
        reo_bar_dias=tuple(int(value) for value in REO_BAR_DIAS),
        reo_spacings=tuple(float(value) for value in REO_SPACINGS),
        activation_shear_state=activation_shear_state,
        float_from_state=float_from_state,
        geometry_lock_enabled=geometry_lock_enabled,
        int_from_state=int_from_state,
        make_auto_design_candidate_key=_make_auto_design_candidate_key,
        resolve_geometry_width_context=resolve_geometry_width_context,
        shear_candidate_type=shear_candidate_type,
        shear_reinforcement_is_active=shear_reinforcement_is_active,
    )
    shear_governing_runtime = ShearGoverningCandidateRuntime(
        generate_escalated_shear_states=partial(
            generate_escalated_shear_states,
            runtime=escalated_shear_runtime,
        ),
        guidance_state_snapshot=guidance_state_snapshot,
        one_click_diff_accumulated_updates=(
            diff_candidate_state_updates
        ),
        shear_severity_band=shear_severity_band,
    )
    generate_shear_governing = partial(
        _generate_shear_governing_candidates,
        runtime=shear_governing_runtime,
    )
    tightening_runtime = GoverningDomainTighteningRuntime(
        efficiency_target_util_min=float(EFFICIENCY_TARGET_UTIL_MIN),
        build_design_actions_context_isolated=build_design_actions_context,
        candidate_target_domains_for_band=(
            _candidate_target_domains_for_band_owned
        ),
        candidate_objective_util=_candidate_objective_util,
        compute_bottom_reo_recommendation=(
            guidance_runtime.compute_runtime.one_click_band_candidate
            .compute_bottom_reo_recommendation
        ),
        effective_bottom_design_state=effective_bottom_design_state,
        float_from_state=float_from_state,
        generate_shear_governing_candidates=generate_shear_governing,
        governing_focus_from_overview=governing_focus_from_overview,
        guidance_state_snapshot=guidance_state_snapshot,
        int_from_state=int_from_state,
        one_click_diff_accumulated_updates=(
            diff_candidate_state_updates
        ),
        one_click_domain_needs_cleanup=(
            _one_click_domain_needs_cleanup_owned
        ),
        one_click_eval_domain_scores=eval_domain_scores,
        one_click_required_domains_satisfied=partial(
            resolve_candidate_required_domains_satisfied,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
            default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
            fail_status=BEAM_STATUS_FAIL,
            optimisation_goal_resolver=design_optimisation_goal,
        ),
        generate_cleanup_candidates=generate_cleanup_variants,
        generate_less_bottom_reo_variants=(
            generate_less_bottom_variants
        ),
        generate_less_shear_reo_variants=(
            generate_less_shear_variants
        ),
        generate_simpler_layout_variants=generate_simpler_variants,
        generate_smaller_geometry_variants=(
            generate_smaller_geometry_variants
        ),
    )
    cleanup_candidate_allowed = partial(
        one_click_in_band_shear_cleanup_candidate_allowed,
        shear_update_keys=frozenset(
            {"lig_d", "lig_legs", "s_lig"}
        ),
        candidate_in_target_band=_candidate_in_target_band_owned,
        domain_score=domain_score,
    )
    normalize_shear_updates = partial(
        normalise_invalid_shear_state_updates,
        canonical_no_shear_spacing=200.0,
        reo_bar_diameters=(
            10, 12, 16, 20, 24, 28, 32, 36, 40
        ),
        reo_spacings=(
            75, 100, 125, 150, 175, 200, 225, 250, 275, 300
        ),
        int_from_state=int_from_state,
        float_from_state=float_from_state,
        dev_mode_enabled=lambda: bool(
            session_state.get("_dev_mode")
        ),
    )
    sanitize_updates = partial(
        sanitize_shared_update_bundle,
        shared_defaults=SHARED_DEFAULTS,
    )
    shared_snapshot = partial(shared_state_snapshot, session_state)
    resolve_summary_state = partial(
        resolve_inputs_summary_state,
        InputsSummaryStateRuntime(
            design_guide_fingerprint=design_guide_fingerprint,
            guidance_state_snapshot=guidance_state_snapshot,
            session_state=session_state,
            shared_state_snapshot=shared_snapshot,
            ux_probe_record=lambda *args, **kwargs: None,
        ),
    )
    build_canonical_pack = partial(
        _build_canonical_design_state_pack_for_app_bridge,
        runtime=CanonicalDesignStatePackRuntime(
            guidance_state_snapshot=guidance_state_snapshot,
        ),
    )
    attach_target_domains = partial(
        one_click_attach_eval_target_domains,
        build_design_actions_context=build_design_actions_context,
        shear_demands_negligible=shear_demands_negligible,
        domain_score=domain_score,
        bending_demand_abs_tol_knm=1.0,
    )
    next_hop_runtime = OneClickNextHopRuntime(
        target_util_min=float(EFFICIENCY_TARGET_UTIL_MIN),
        target_util_max=float(EFFICIENCY_TARGET_UTIL_MAX),
        fail_status=BEAM_STATUS_FAIL,
        max_local_candidates_per_iteration=12,
        optimisation_goal_resolver=design_optimisation_goal,
        resolve_precheck=resolve_target_band_next_hop_precheck,
        candidate_target_domains_for_band=(
            _candidate_target_domains_for_band_owned
        ),
        build_auto_design_context=build_auto_design_context,
        generate_smaller_geometry_variants=(
            generate_smaller_geometry_variants
        ),
        generate_less_bottom_reo_variants=(
            generate_less_bottom_variants
        ),
        generate_less_shear_reo_variants=(
            generate_less_shear_variants
        ),
        generate_simpler_layout_variants=generate_simpler_variants,
        shear_governing_truth_allows_overdesign_cleanup=(
            guidance_runtime.compute_runtime.efficiency_tightening_state
            .shear_governing_truth_allows_overdesign_cleanup
        ),
        shear_cleanup_possible=shear_cleanup_possible,
        make_candidate_key=_make_auto_design_candidate_key,
        select_best_refinement_candidate=(
            select_best_target_band_refinement_candidate
        ),
        build_canonical_design_state_pack=build_canonical_pack,
        evaluate_candidate_full=evaluate_full,
        attach_eval_target_domains=attach_target_domains,
        has_unresolved_spacing_envelope_fail=(
            one_click_has_unresolved_spacing_envelope_fail
        ),
    )
    evaluate_auto = partial(
        evaluate_auto_design_candidate,
        guidance_state_snapshot=guidance_state_snapshot,
        evaluate_candidate_full=evaluate_full,
    )
    canonical_convenience_fields = partial(
        _canonical_convenience_fields_from_state,
        runtime=CanonicalConvenienceResyncRuntime(
            agent_debug_log=lambda *args, **kwargs: None,
            build_canonical_design_state_pack=build_canonical_pack,
            convenience_scalar_differs=convenience_scalar_differs,
            guidance_state_snapshot=guidance_state_snapshot,
            session_state=session_state,
            set_shared=set_shared,
            shared_state_snapshot=shared_snapshot,
        ),
    )
    normalise_shear_in_shared = lambda *, source: _normalise_shear_shared(
        source=source,
        shared_snapshot=shared_snapshot,
        normalise_updates=normalize_shear_updates,
        set_shared_fn=set_shared,
    )
    refresh_shear_widgets = lambda *, source: (
        request_shear_widget_seed_from_shared(
            state=session_state,
            reason=source,
            agent_debug_log_fn=lambda *args, **kwargs: None,
        )
    )
    convenience_runtime = CanonicalConvenienceResyncRuntime(
        agent_debug_log=lambda *args, **kwargs: None,
        build_canonical_design_state_pack=build_canonical_pack,
        convenience_scalar_differs=convenience_scalar_differs,
        guidance_state_snapshot=guidance_state_snapshot,
        session_state=session_state,
        set_shared=set_shared,
        shared_state_snapshot=shared_snapshot,
    )
    resync_convenience = partial(
        _apply_canonical_convenience_resync_to_shared,
        runtime=convenience_runtime,
    )
    values = {
        "copy": copy,
        "math": math,
        "AUTO_DESIGN_REQUEST_SOURCE_KEY": request_source_key,
        "BEAM_STATUS_FAIL": BEAM_STATUS_FAIL,
        "EFFICIENCY_TARGET_UTIL_MAX": float(
            EFFICIENCY_TARGET_UTIL_MAX
        ),
        "EFFICIENCY_TARGET_UTIL_MIN": float(
            EFFICIENCY_TARGET_UTIL_MIN
        ),
        "GUIDANCE_SHEAR_UTIL_NEGLIGIBLE": 0.08,
        "RESCUE_SEED_LIBRARY": RESCUE_SEED_LIBRARY,
        "SHARED_DEFAULTS": SHARED_DEFAULTS,
        "_agent_debug_log": debug_log,
        "_append_design_guide_trace": append_trace,
        "_COMPOUND_SHEAR_UPDATE_KEYS": frozenset(
            {"lig_d", "lig_legs", "s_lig"}
        ),
        "_DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS": (
            DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
        ),
        "_build_design_actions_context": build_design_actions_context,
        "_build_canonical_design_state_pack": build_canonical_pack,
        "_build_recommendation_envelope": build_recommendation_envelope,
        "_canonical_pack_is_valid": _canonical_pack_is_valid,
        "_auto_design_invoke_debug_snapshot": partial(
            auto_design_invoke_debug_snapshot,
            session_state=session_state,
            auto_invoke_key=auto_invoke_key,
            request_source_key=request_source_key,
            request_timestamp_key=request_timestamp_key,
        ),
        "_clear_auto_design_runtime_latches": partial(
            clear_auto_design_runtime_latches,
            session_state=session_state,
        ),
        "_coherence_debug_fields": _coherence_debug_fields,
        "_collect_design_overview": collect_overview,
        "_compute_design_guidance_items": partial(
            compute_inputs_guidance,
            guidance_runtime,
        ),
        "_consume_auto_design_invoke_after_solver_entry_confirmed": partial(
            consume_auto_design_invoke_after_solver_entry_confirmed,
            session_state=session_state,
            auto_invoke_key=auto_invoke_key,
            request_timestamp_key=request_timestamp_key,
            request_source_key=request_source_key,
        ),
        "_design_mode_config": design_mode_config,
        "_design_optimisation_goal": design_optimisation_goal,
        "_design_state_coherence_check": _design_state_coherence_check,
        "_design_guide_trace_compare_meta": (
            design_guide_trace_compare_meta
        ),
        "_design_guide_candidate_family": design_guide_candidate_family,
        "_design_guide_tracer_path": tracer_path,
        "_evaluate_shear_with_state": evaluate_shear_with_state,
        "_evaluate_auto_design_candidate": partial(
            evaluate_auto,
        ),
        "_float_from_state": float_from_state,
        "_guidance_state_snapshot": guidance_state_snapshot,
        "_invalidate_design_guide_caches": partial(
            invalidate_design_guide_caches,
            session_state=session_state,
            clear_transient_ui_state=(
                clear_design_guide_transient_ui_state
            ),
            agent_debug_log=debug_log,
        ),
        "_parse_util_value": parse_util_value,
        "_int_from_state": int_from_state,
        "_candidate_is_valid_primary_one_click": (
            _candidate_is_valid_primary_one_click
        ),
        "_candidate_failure_coverage_summary": partial(
            candidate_failure_coverage_summary,
            collect_design_overview=collect_overview,
        ),
        "_candidate_in_target_band": _candidate_in_target_band_owned,
        "_candidate_state_signature": _candidate_state_signature_owned,
        "_candidate_objective_util": _candidate_objective_util,
        "_candidate_target_band_distance": (
            _candidate_target_band_distance_owned
        ),
        "_candidate_target_domains_for_band": (
            _candidate_target_domains_for_band_owned
        ),
        "_local_cleanup_acceptance_fingerprint": (
            build_local_cleanup_acceptance_fingerprint
        ),
        "_current_design_guide_fail_fingerprint": partial(
            current_design_guide_fail_fingerprint,
            parse_util_value=parse_util_value,
        ),
        "_governing_focus_from_overview": governing_focus_from_overview,
        "_new_design_guide_trace_run_id": (
            new_design_guide_trace_run_id
        ),
        "_one_click_diff_accumulated_updates": (
            diff_candidate_state_updates
        ),
        "_one_click_domain_total_distance": partial(
            resolve_candidate_domain_total_distance,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
            default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
            fail_status=BEAM_STATUS_FAIL,
            optimisation_goal_resolver=design_optimisation_goal,
        ),
        "_one_click_domain_max_distance": partial(
            resolve_candidate_domain_max_distance,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
            default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
            fail_status=BEAM_STATUS_FAIL,
            optimisation_goal_resolver=design_optimisation_goal,
        ),
        "_one_click_domain_needs_cleanup": (
            _one_click_domain_needs_cleanup_owned
        ),
        "_one_click_attach_eval_target_domains": partial(
            attach_target_domains,
        ),
        "_one_click_mixed_direction_classification": partial(
            one_click_mixed_direction_classification,
            domain_score=domain_score,
            build_design_actions_context=build_design_actions_context,
            shear_demands_negligible=shear_demands_negligible,
            bending_demand_abs_tol_knm=1.0,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
        ),
        "_one_click_mixed_direction_rank_adjustment": partial(
            one_click_mixed_direction_rank_adjustment,
            domain_score=domain_score,
        ),
        "_one_click_candidate_is_shear_governing_for_prune": partial(
            one_click_candidate_is_shear_governing_for_prune,
            family_matches_governing_domain=(
                _candidate_family_matches_governing_domain
            ),
        ),
        "_one_click_directional_tie_key": partial(
            one_click_directional_tie_key,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
            default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
        ),
        "_one_click_exhaustion_next_hop_allowed": partial(
            one_click_exhaustion_next_hop_allowed,
            resolver=resolve_target_band_exhaustion_refinement_allowed,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
            default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
            fail_status=BEAM_STATUS_FAIL,
            optimisation_goal_resolver=design_optimisation_goal,
        ),
        "_one_click_has_unresolved_spacing_envelope_fail": (
            one_click_has_unresolved_spacing_envelope_fail
        ),
        "_one_click_commit_audit_passes": (
            partial(
                one_click_commit_audit_passes,
                fail_status=BEAM_STATUS_FAIL,
            )
        ),
        "_one_click_collect_actionable_guidance_candidates": partial(
            _one_click_collect_actionable_guidance_candidates,
            runtime=actionable_collection_runtime,
        ),
        "_generate_tightening_candidates_for_governing_domain": partial(
            _generate_tightening_candidates_for_governing_domain,
            runtime=tightening_runtime,
        ),
        "_one_click_build_user_visible_no_action_fields": (
            one_click_build_user_visible_no_action_fields
        ),
        "_one_click_best_next_hop_improving_candidate": partial(
            one_click_best_next_hop_improving_candidate,
            runtime=next_hop_runtime,
        ),
        "_one_click_budget_stop_has_better_next_hop": partial(
            one_click_budget_stop_has_better_next_hop,
            runtime=next_hop_runtime,
        ),
        "_one_click_in_band_shear_cleanup_candidate_allowed": partial(
            cleanup_candidate_allowed,
        ),
        "_one_click_in_band_shear_cleanup_deferral": partial(
            one_click_in_band_shear_cleanup_deferral,
            guidance_state_snapshot=guidance_state_snapshot,
            build_design_actions_context=build_design_actions_context,
            shear_reinforcement_is_active=(
                shear_reinforcement_is_active
            ),
            shear_demands_negligible=shear_demands_negligible,
            governing_focus_from_overview=(
                governing_focus_from_overview
            ),
            compute_shear_tightening_recommendation=(
                guidance_runtime.compute_runtime
                .efficiency_tightening_state
                .compute_shear_tightening_recommendation
            ),
            shear_update_keys=frozenset(
                {"lig_d", "lig_legs", "s_lig"}
            ),
            evaluate_candidate_full=evaluate_full,
            cleanup_candidate_allowed=cleanup_candidate_allowed,
        ),
        "_one_click_committable_candidate_eval": partial(
            one_click_committable_candidate_eval,
            sanitize_shared_update_bundle=sanitize_updates,
            guidance_state_snapshot=guidance_state_snapshot,
            normalise_invalid_shear_state_updates=(
                normalize_shear_updates
            ),
            canonical_convenience_fields_from_state=(
                canonical_convenience_fields
            ),
            canonical_convenience_meta_key=(
                "__canonical_convenience_meta__"
            ),
            evaluate_auto_design_candidate=evaluate_auto,
        ),
        "_one_click_post_commit_audit": partial(
            one_click_post_commit_audit,
            shared_defaults=SHARED_DEFAULTS,
            shared_state_snapshot=shared_snapshot,
            guidance_state_snapshot=guidance_state_snapshot,
            build_canonical_design_state_pack=build_canonical_pack,
            collect_design_overview=collect_overview,
            evaluate_candidate_full=evaluate_full,
            resolve_summary_state=lambda: resolve_summary_state()[0],
        ),
        "_one_click_required_domain_progress": partial(
            resolve_candidate_required_domain_progress,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
            default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
            fail_status=BEAM_STATUS_FAIL,
            optimisation_goal_resolver=design_optimisation_goal,
        ),
        "_one_click_required_domains_satisfied": partial(
            resolve_candidate_required_domains_satisfied,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
            default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
            fail_status=BEAM_STATUS_FAIL,
            optimisation_goal_resolver=design_optimisation_goal,
        ),
        "_one_click_seed_target_domains_from_eval": partial(
            one_click_seed_target_domains_from_eval,
            domain_score=domain_score,
        ),
        "_one_click_still_materially_under_target": partial(
            one_click_still_materially_under_target,
            candidate_objective_util=_candidate_objective_util,
            candidate_target_domains=(
                _candidate_target_domains_for_band_owned
            ),
            domain_score=domain_score,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
        ),
        "_one_click_step_improves": partial(
            resolve_candidate_step_improves,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
            default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
            fail_status=BEAM_STATUS_FAIL,
            optimisation_goal_resolver=design_optimisation_goal,
        ),
        "_one_click_strict_target_band_ok": (
            _one_click_strict_target_band_ok_owned
        ),
        "_one_click_target_domains_for_eval": (
            resolve_target_band_candidate_domains_for_updates
        ),
        "_one_click_tightening_mode_active": partial(
            one_click_tightening_mode_active,
            candidate_objective_util=_candidate_objective_util,
            default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
        ),
        "_one_click_trace_eval_domain_payload": partial(
            one_click_trace_eval_domain_payload,
            candidate_target_band_distance=(
                _candidate_target_band_distance_owned
            ),
            required_domain_progress=partial(
                resolve_candidate_required_domain_progress,
                default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
                default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
                fail_status=BEAM_STATUS_FAIL,
                optimisation_goal_resolver=design_optimisation_goal,
            ),
        ),
        "_one_click_update_direction_summary": partial(
            one_click_update_direction_summary,
            guidance_state_snapshot=guidance_state_snapshot,
            design_width_value=design_width_value,
            float_from_state=float_from_state,
            effective_bottom_design_state=(
                effective_bottom_design_state
            ),
        ),
        "_overlay_current_normalized_shear_truth": overlay_shear_truth,
        "_normalise_invalid_shear_state_updates": normalize_shear_updates,
        "_pop_inputs_widget_keys_for_shared_updates": partial(
            pop_inputs_widget_keys_for_shared_updates,
            session_state=session_state,
        ),
        "_record_one_click_shear_publish_audit": partial(
            record_one_click_shear_publish_audit,
            session_state=session_state,
        ),
        "_restore_shared_state_snapshot": partial(
            restore_shared_state_snapshot,
            shared_defaults=SHARED_DEFAULTS,
            set_shared=set_shared,
            normalise_invalid_shear_state_in_shared=(
                normalise_shear_in_shared
            ),
            refresh_canonical_shear_widgets=refresh_shear_widgets,
            apply_canonical_convenience_resync_to_shared=(
                resync_convenience
            ),
        ),
        "_requires_full_coverage_for_primary_one_click": (
            _requires_full_coverage_for_primary_one_click
        ),
        "_rescue_mode_default_debug": _rescue_mode_default_debug_owned,
        "_rescue_mode_eval_for_result": partial(
            rescue_mode_eval_for_result,
            build_canonical_design_state_pack=build_canonical_pack,
            evaluate_candidate_full=evaluate_full,
        ),
        "_rescue_mode_validate_seed": partial(
            rescue_mode_validate_seed,
            guidance_state_snapshot=guidance_state_snapshot,
            overlay_current_normalized_shear_truth=(
                overlay_shear_truth
            ),
            build_canonical_design_state_pack=build_canonical_pack,
            design_state_coherence_check=(
                _design_state_coherence_check
            ),
            canonical_pack_is_valid=_canonical_pack_is_valid,
            evaluate_candidate_full=evaluate_full,
        ),
        "_rescue_bootstrap_partial_commit_allowed": (
            rescue_bootstrap_partial_commit_allowed
        ),
        "_rescue_mode_seed_order": _rescue_mode_seed_order_owned,
        "_sanitize_shared_update_bundle": sanitize_updates,
        "_set_one_click_run_feedback": partial(
            set_one_click_run_feedback,
            session_state=session_state,
        ),
        "_set_design_guide_live_breadcrumb": partial(
            set_design_guide_live_breadcrumb,
            session_state=session_state,
        ),
        "_set_shared_updates": partial(
            set_shared_updates,
            session_state=session_state,
            sanitize_updates=sanitize_updates,
            append_trace=append_trace,
            set_shared=set_shared,
            normalise_invalid_shear_state_in_shared=(
                normalise_shear_in_shared
            ),
            refresh_canonical_shear_widgets=refresh_shear_widgets,
            apply_canonical_convenience_resync_to_shared=(
                resync_convenience
            ),
        ),
        "_rescue_mode_path_improved": partial(
            lambda step_improves, rescue_eval, base_eval, mode_config: bool(
                isinstance(rescue_eval, dict)
                and isinstance(base_eval, dict)
                and step_improves(
                    rescue_eval,
                    base_eval,
                    mode_config,
                )
            ),
            partial(
                resolve_candidate_step_improves,
                default_target_min=float(EFFICIENCY_TARGET_UTIL_MIN),
                default_target_max=float(EFFICIENCY_TARGET_UTIL_MAX),
                fail_status=BEAM_STATUS_FAIL,
                optimisation_goal_resolver=design_optimisation_goal,
            ),
        ),
        "_rescue_mode_should_enter": partial(
            rescue_mode_should_enter,
            candidate_objective_util=_candidate_objective_util,
            domain_score=domain_score,
            build_design_actions_context=build_design_actions_context,
        ),
        "_shared_state_snapshot": shared_snapshot,
        "_stage3_remaining_issue_class_from_overview_state": (
            stage3_remaining_issue_class_from_overview_state
        ),
        "_stage3_final_published_shear_truth_bundle": (
            stage3_final_published_shear_truth_bundle
        ),
        "_trace_compact_overview_dict": trace_compact_overview_dict,
        "_trace_compact_shared_geom_reo": partial(
            trace_compact_shared_geom_reo,
            int_from_state=int_from_state,
            float_from_state=float_from_state,
            bottom_reo_state_label=bottom_reo_state_label,
        ),
        "_tracer_one_click_action_source_summary": partial(
            tracer_one_click_action_source_summary,
            session_state=session_state,
            auto_invoke_key=auto_invoke_key,
            request_source_key=request_source_key,
            request_timestamp_key=request_timestamp_key,
        ),
        "_shear_demands_negligible": shear_demands_negligible,
        "_shear_preview_for_updates": partial(
            shear_preview_for_updates,
            guidance_state_snapshot=guidance_state_snapshot,
            build_shear_check_rows_from_state=(
                build_shear_check_rows_from_state
            ),
        ),
        "_should_run_auto_design": partial(
            should_run_auto_design,
            session_state=session_state,
            auto_invoke_key=auto_invoke_key,
        ),
        "_updates_match_state": updates_match_state,
        "evaluate_candidate_full": evaluate_full,
        "compute_efficiency_tightening_state": partial(
            compute_efficiency_tightening_state,
            runtime=(
                guidance_runtime.compute_runtime
                .efficiency_tightening_state
            ),
        ),
        "finalize_auto_design_publish": finalize_auto_design_publish,
        "is_valid_progress_while_failing": (
            _is_valid_progress_while_failing_owned
        ),
        "persist_active_beam_from_shared": persist_active_beam_from_shared,
        "publish_normalized_final_shear_truth_to_session": (
            publish_normalized_final_shear_truth_to_session
        ),
    }
    return SimpleNamespace(**values)


def missing_one_click_runtime_dependencies(provider: Any) -> tuple[str, ...]:
    return tuple(
        name
        for name in _LEGACY_AUTO_DESIGN_NAMES
        if not hasattr(provider, name)
    )


__all__ = [
    "build_partial_one_click_runtime_provider",
    "missing_one_click_runtime_dependencies",
]
