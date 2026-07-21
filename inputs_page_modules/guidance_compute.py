"""Design Guide guidance-compute coordinators for the Inputs page.

These functions preserve the old Inputs page compute behaviour behind an
extracted coordinator boundary. Engineering authority remains in the existing
Design Brain and legacy helper surfaces injected by the compatibility shim.
"""

from __future__ import annotations

from typing import Any


_ACTIVE_GUIDANCE_RANK_TRACE: list[dict] | None = None
_ACTIVE_GUIDANCE_RECO_TRACE: list[dict] | None = None


_LEGACY_COMPUTE_NAMES: tuple[str, ...] = (
    'CANONICAL_NO_SHEAR_SLIG_MM',
    'DESIGN_GUIDE_ALGORITHM_VERSION',
    'EFFICIENCY_TARGET_UTIL_MIN',
    'FINAL_ACCEPTED_MIN_FAMILY_UTIL',
    'GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD',
    'TARGET_BAND_EPS',
    '_DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS',
    '_agent_debug_log',
    '_align_guidance_items_to_candidate_search_evidence',
    '_annotate_candidate_target_band_metrics',
    '_auto_design_results_from_candidate',
    '_auto_design_solver_recommendation_as_guidance_item',
    '_bending_guidance_item',
    '_build_candidate_search_evidence',
    '_build_canonical_design_state_pack',
    '_build_design_actions_context',
    '_candidate_cache_key',
    '_candidate_is_valid_primary_one_click',
    '_canonical_pack_is_valid',
    '_coherence_debug_fields',
    '_collapse_to_single_primary_guidance_item',
    '_collect_design_overview',
    '_compute_mode_guidance_recommendation',
    '_crack_guidance_item',
    '_dedupe_guidance_items_for_display',
    '_deflection_guidance_item',
    '_derive_design_guide_terminal_state_from_current_overview',
    '_design_guide_apply_button_contracts_to_items',
    '_design_guide_apply_copy_model_to_items',
    '_design_guide_apply_display_truth_to_items',
    '_design_guide_guidance_intent_debug_rows',
    '_design_guide_lightweight_guidance_state',
    '_design_guide_terminal_state_from_render_artifacts',
    '_design_mode_config',
    '_design_optimisation_goal',
    '_design_optimisation_goal_label',
    '_design_state_coherence_check',
    '_direct_target_band_guidance_item',
    '_efficiency_guidance_items',
    '_efficiency_state_has_valid_candidate',
    '_ensure_design_guide_debug_trace_coherent',
    '_evaluate_auto_design_candidate',
    '_get_actionable_target_band_winner',
    '_get_one_click_band_reaching_candidate',
    '_guidance_governing_primary_action',
    '_guidance_item',
    '_guidance_item_from_resolved_candidate',
    '_guidance_item_is_resolved_one_click',
    '_guidance_item_source_candidate_id',
    '_guidance_not_started',
    '_guidance_start_item',
    '_guidance_state_snapshot',
    '_in_target_shear_congestion_reshape_guidance_item',
    '_is_in_target_zone_with_eps',
    '_local_cleanup_acceptance_fingerprint',
    '_local_cleanup_post_apply_acceptance_matches',
    '_log_guidance_branch_governing_mismatch',
    '_materialize_guidance_candidate',
    '_maybe_promote_safe_local_cleanup_primary',
    '_merge_target_band_probe_to_debug_sink',
    '_optimal_guidance_item',
    '_optimisation_candidate_family',
    '_overview_required_checks_acceptable',
    '_parse_util_value',
    '_passing_guidance_item',
    '_post_click_accepted_green_audit',
    '_prefer_target_band_guidance_item_order',
    '_promote_guidance_item_to_resolved_candidate',
    '_recommendation_result_for_primary_guidance_card',
    '_recommendation_updates_for_envelope',
    '_requires_full_coverage_for_primary_one_click',
    '_resolve_design_actions_from_state',
    '_resolve_recommendation_updates',
    '_resolved_efficiency_target_band',
    '_sanitize_guidance_items_for_executor_contract',
    '_select_primary_optimisation_candidate',
    '_shear_cleanup_materially_reduces_reinforcement',
    '_shear_demands_negligible',
    '_shear_governing_fallback_resolved_candidate',
    '_shear_guidance_item',
    '_shear_reinforcement_is_active',
    '_shear_tightening_as_local_cleanup_item',
    '_solve_one_click_candidate',
    '_try_compound_efficiency_guidance_item',
    '_try_compound_strengthening_guidance_item',
    '_updates_match_state',
    '_very_low_demand_guidance_item',
    'compute_efficiency_tightening_state',
    'evaluate_candidate_full',
    'get_rerun_pure_cache',
    'identify_materially_overprovided_non_governing_families',
    'is_unnecessarily_overdesigned',
    'legacy_item_from_decision',
    'resolve_design_guide_decision',
    'run_auto_design_solver',
    'set_rerun_pure_cache',
    'speed_profile_record',
    'stable_fingerprint_for_payload',
    'target_band_payload',
    'ux_probe_record',
)


def _bind_legacy_compute_globals(
    *,
    legacy_page: Any,
    st_module: Any,
    os_module: Any,
    sys_module: Any,
) -> None:
    namespace = globals()
    namespace["st"] = st_module
    namespace["os"] = os_module
    namespace["sys"] = sys_module
    for name in _LEGACY_COMPUTE_NAMES:
        namespace[name] = getattr(legacy_page, name)


def compute_design_guidance_items_core(
    legacy_page: Any,
    st_module: Any,
    os_module: Any,
    sys_module: Any,
    state: dict,
    debug_sink: dict | None = None,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
) -> list[dict]:
    _bind_legacy_compute_globals(
        legacy_page=legacy_page,
        st_module=st_module,
        os_module=os_module,
        sys_module=sys_module,
    )
    return _compute_design_guidance_items_core(
        state,
        debug_sink,
        guidance_debug_verbose=guidance_debug_verbose,
        debug_enabled=debug_enabled,
    )


def compute_design_guidance_items(
    legacy_page: Any,
    st_module: Any,
    os_module: Any,
    sys_module: Any,
    state: dict,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
    request_kind: str = "design_guide",
) -> dict:
    _bind_legacy_compute_globals(
        legacy_page=legacy_page,
        st_module=st_module,
        os_module=os_module,
        sys_module=sys_module,
    )
    return _compute_design_guidance_items(
        state,
        guidance_debug_verbose=guidance_debug_verbose,
        debug_enabled=debug_enabled,
        request_kind=request_kind,
    )


def _compute_design_guidance_items_core(
    state: dict,
    debug_sink: dict | None = None,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
) -> list[dict]:
    _core_stage_debug = os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    if _core_stage_debug:
        print("DG_STAGE core_entry", file=sys.stderr, flush=True)
    design_context = _build_design_actions_context(state)
    if _core_stage_debug:
        print("DG_STAGE core_after_context", file=sys.stderr, flush=True)
    guidance_state = dict(design_context.get("state") or _guidance_state_snapshot(state))
    overview = _collect_design_overview(guidance_state, context=design_context)
    if _core_stage_debug:
        print(
            f"DG_STAGE core_after_overview any_fail={bool(overview.get('any_fail'))} all_pass={bool(overview.get('all_key_pass'))} worst={overview.get('worst_util')}",
            file=sys.stderr,
            flush=True,
        )
    mode_config = _design_mode_config(_design_optimisation_goal(guidance_state))
    target_band_with_eps_passed = _is_in_target_zone_with_eps(overview, mode_config, eps=TARGET_BAND_EPS)
    if _core_stage_debug:
        print(f"DG_STAGE core_after_target_check target={target_band_with_eps_passed}", file=sys.stderr, flush=True)
    guidance_branch = "unknown"
    _verbose = True if guidance_debug_verbose is None else bool(guidance_debug_verbose)
    _sink_is_dict = isinstance(debug_sink, dict)
    full_dbg = _sink_is_dict and _verbose
    min_dbg = _sink_is_dict and _verbose
    if min_dbg:
        debug_sink["guidance_resolved_state"] = guidance_state
    if full_dbg:
        debug_sink["overview"] = overview
        debug_sink["overview_actions_used"] = overview.get("actions_used")
        debug_sink["guidance_actions_used"] = dict(design_context.get("actions") or {})
        debug_sink["target_band_eps"] = float(TARGET_BAND_EPS)
        debug_sink["target_band_with_eps_passed"] = bool(target_band_with_eps_passed)
    if _core_stage_debug:
        print("DG_STAGE core_before_not_started_check", file=sys.stderr, flush=True)
    _not_started = _guidance_not_started(guidance_state, overview)
    if _core_stage_debug:
        print(f"DG_STAGE core_after_not_started_check not_started={_not_started}", file=sys.stderr, flush=True)
    if _not_started:
        guidance_branch = "not_started"
        if _core_stage_debug:
            print("DG_STAGE core_before_start_item", file=sys.stderr, flush=True)
        start_item = _guidance_start_item(guidance_state)
        if _core_stage_debug:
            print("DG_STAGE core_after_start_item", file=sys.stderr, flush=True)
        if _sink_is_dict:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = start_item.get("action_type")
            debug_sink["selected_title"] = start_item.get("title_main")
        return [start_item]
    _post_apply_acceptance_audit = {}
    if _local_cleanup_post_apply_acceptance_matches(guidance_state):
        _post_apply_acceptance_audit = _post_click_accepted_green_audit(
            overview,
            blocker_source=debug_sink if isinstance(debug_sink, dict) else None,
            state=guidance_state,
        )
        if min_dbg:
            debug_sink.update(_post_apply_acceptance_audit)
    if (
        _local_cleanup_post_apply_acceptance_matches(guidance_state)
        and not bool(overview.get("any_fail"))
        and bool(target_band_with_eps_passed)
        and bool(_post_apply_acceptance_audit.get("post_click_accepted_green_valid"))
    ):
        guidance_branch = "post_apply_local_cleanup_accepted"
        accepted_util = _parse_util_value(overview.get("worst_util") or overview.get("governing_util"))
        target_lo, target_hi, _ = _resolved_efficiency_target_band(
            mode_config,
            goal=_design_optimisation_goal(guidance_state),
        )
        accepted_item = _guidance_item(
            "general",
            "Design accepted - target band achieved",
            "The one-click cleanup has been applied and the current design is inside the target band.",
            None,
            "Why: all required checks remain acceptable, governing utilisation is inside the target band, and this is the accepted post-click Design Guide state.",
            "Key checks: bending, shear, serviceability, target utilisation band",
            None,
            None,
            status="PASS",
            util=accepted_util,
        )
        accepted_item["guidance_intent"] = "already_efficient"
        accepted_item["design_guide_terminal_state"] = "optimal"
        accepted_item["display_truth"] = {
            "display_truth_source": "published_summary",
            "displayed_util": accepted_util,
            "displayed_status": "OPTIMAL",
            "target_low": float(target_lo),
            "target_high": float(target_hi),
            "displayed_within_target_band": True,
            "source_summary_util": accepted_util,
            "source_candidate_util": None,
            "source_post_commit_util": accepted_util,
        }
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = None
            debug_sink["selected_title"] = accepted_item.get("title_main")
            debug_sink["post_click_accepted_green"] = True
            debug_sink["post_click_accepted_green_valid"] = True
            debug_sink["post_click_design_guide_state"] = "accepted_green"
            debug_sink["post_click_executable_safe_cleanup_count"] = 0
            debug_sink["safe_local_cleanup_count"] = 0
            debug_sink["executable_safe_cleanup_count"] = 0
            debug_sink["local_cleanup_search_ran"] = False
            debug_sink["local_cleanup_search_exhaustive"] = True
            debug_sink["terminal_state_reason"] = "post_apply_cleanup_state_accepted"
        return [accepted_item]
    if (
        _local_cleanup_post_apply_acceptance_matches(guidance_state)
        and not bool(_post_apply_acceptance_audit.get("post_click_accepted_green_valid", True))
        and min_dbg
    ):
        debug_sink["post_click_accepted_green"] = False
        debug_sink["terminal_state_blocked_by_local_cleanup"] = True
        debug_sink["terminal_state_blocked_reason"] = str(
            _post_apply_acceptance_audit.get("post_click_accepted_green_invalid_reason")
            or "post_apply_cleanup_state_has_unresolved_overprovided_family"
        )
    governing_action, primary_utils = _guidance_governing_primary_action(overview)
    if full_dbg:
        debug_sink["governing_action"] = governing_action
        debug_sink["primary_utils"] = dict(primary_utils)
    packs = dict(overview.get("packs") or {})
    bend_pack = dict(packs.get("bending") or {})
    shear_pack = dict(packs.get("shear") or {})
    crack_pack = dict(packs.get("crack") or {})
    defl_pack = dict(packs.get("deflection") or {})

    items = [
        _bending_guidance_item(guidance_state, bend_pack),
        _shear_guidance_item(guidance_state, shear_pack),
        _crack_guidance_item(guidance_state, crack_pack),
        _deflection_guidance_item(guidance_state, defl_pack),
    ]
    filtered = [item for item in items if item is not None]
    filtered.sort(key=lambda item: item["priority"], reverse=True)
    governing_item = next(
        (item for item in filtered if str(item.get("check_key") or "") == str(governing_action or "")),
        None,
    )
    critical = [
        item for item in filtered
        if item["bucket"] in ("fail", "warn")
        and (
            item["bucket"] == "fail"
            or item.get("util") is None
            or item["util"] >= GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD
            or bool(overview.get("any_fail"))
            or bool(overview.get("any_warn"))
        )
    ]
    governing_item_is_critical = bool(governing_item and governing_item in critical)
    out_of_band_live = not (
        _overview_required_checks_acceptable(overview) and bool(target_band_with_eps_passed)
    )
    primary_one_click_requires_full_coverage, primary_one_click_fail_keys = (
        _requires_full_coverage_for_primary_one_click(overview)
    )
    primary_critical = (
        next(
            (
                item for item in critical
                if str(item.get("check_key") or "") == str(governing_action or "")
            ),
            critical[0],
        )
        if critical
        else None
    )
    if not bool(overview.get("any_fail")):
        reshape_item = _in_target_shear_congestion_reshape_guidance_item(
            guidance_state,
            overview,
            mode_config,
            debug_sink=debug_sink if full_dbg else None,
        )
        if reshape_item:
            guidance_branch = "in_target_shear_congestion_reshape"
            if full_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = reshape_item.get("action_type")
                debug_sink["selected_title"] = reshape_item.get("title_main")
                debug_sink["actionable_target_band_winner_exists"] = True
                debug_sink["actionable_target_band_winner_family"] = "compound"
                debug_sink["actionable_target_band_winner_subfamilies"] = ["geometry", "bottom_reo", "shear"]
                debug_sink["actionable_target_band_winner_change_lines"] = list(
                    reshape_item.get("guidance_change_lines") or []
                )
                debug_sink["optimal_short_circuit_blocked"] = True
                debug_sink["optimal_short_circuit_block_reason"] = "in_target_shear_congestion_reshape"
                debug_sink["surfaced_guidance_branch"] = guidance_branch
                debug_sink["surfaced_selected_action_type"] = reshape_item.get("action_type")
                debug_sink["surfaced_selected_title"] = reshape_item.get("title_main")
            elif min_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = reshape_item.get("action_type")
                debug_sink["selected_title"] = reshape_item.get("title_main")
            return [reshape_item]
    if (
        _overview_required_checks_acceptable(overview)
        and not bool(overview.get("any_fail"))
        and bool(target_band_with_eps_passed)
    ):
        if _core_stage_debug:
            print("DG_STAGE core_before_material_family_check", file=sys.stderr, flush=True)
        family_utils, material_families, governing_family = identify_materially_overprovided_non_governing_families(overview)
        if _core_stage_debug:
            print(f"DG_STAGE core_after_material_family_check families={material_families}", file=sys.stderr, flush=True)
        in_target_final_audit = _post_click_accepted_green_audit(
            overview,
            blocker_source=debug_sink if isinstance(debug_sink, dict) else None,
            state=guidance_state,
        )
        if bool(in_target_final_audit.get("post_click_accepted_green_valid")):
            accepted_item = _optimal_guidance_item(guidance_state, overview)
            accepted_item["guidance_intent"] = "already_efficient"
            if min_dbg:
                debug_sink.update(in_target_final_audit)
                debug_sink["guidance_branch"] = "target_band_final_accepted"
                debug_sink["selected_action_type"] = None
                debug_sink["selected_title"] = accepted_item.get("title_main")
                debug_sink["post_click_accepted_green"] = True
                debug_sink["post_click_accepted_green_valid"] = True
                debug_sink["post_click_design_guide_state"] = "accepted_green"
                debug_sink["post_click_executable_safe_cleanup_count"] = 0
                debug_sink["safe_local_cleanup_count"] = 0
                debug_sink["executable_safe_cleanup_count"] = 0
                debug_sink["local_cleanup_search_ran"] = bool(material_families)
                debug_sink["local_cleanup_search_exhaustive"] = bool(material_families)
                debug_sink["terminal_state_reason"] = "target_band_final_accepted_with_exact_blockers"
            return [accepted_item]
        if material_families:
            try:
                if _core_stage_debug:
                    print("DG_STAGE core_before_direct_target_band_item", file=sys.stderr, flush=True)
                local_cleanup_item = _direct_target_band_guidance_item(
                    guidance_state,
                    overview,
                    mode_config,
                    strengthening=False,
                    debug_sink=debug_sink if min_dbg else None,
                )
                if _core_stage_debug:
                    print(f"DG_STAGE core_after_direct_target_band_item item={bool(isinstance(local_cleanup_item, dict))}", file=sys.stderr, flush=True)
            except Exception:
                local_cleanup_item = None
            if isinstance(local_cleanup_item, dict) and _guidance_item_is_resolved_one_click(local_cleanup_item):
                local_cleanup_item["guidance_intent"] = "optional_cleanup"
                local_cleanup_item["local_cleanup_candidate"] = True
                if min_dbg:
                    evidence = dict(local_cleanup_item.get("candidate_search_evidence") or {})
                    debug_sink["guidance_branch"] = "in_target_material_local_cleanup"
                    debug_sink["selected_action_type"] = local_cleanup_item.get("action_type")
                    debug_sink["selected_title"] = local_cleanup_item.get("title_main")
                    debug_sink["family_utils"] = dict(family_utils)
                    debug_sink["materially_overprovided_families"] = list(material_families)
                    debug_sink["governing_family"] = governing_family
                    debug_sink["local_cleanup_search_ran"] = True
                    debug_sink["local_cleanup_search_exhaustive"] = True
                    debug_sink["safe_local_cleanup_count"] = int(evidence.get("safe_executor_backed_candidates_count") or 1)
                    debug_sink["local_cleanup_candidate_search_evidence"] = dict(evidence)
                    debug_sink["candidate_search_evidence"] = dict(evidence)
                    debug_sink["local_cleanup_candidate_inventory"] = list(evidence.get("safe_executor_backed_candidates") or [])
                    debug_sink["local_cleanup_candidate_inventory_count"] = len(debug_sink["local_cleanup_candidate_inventory"])
                    debug_sink["candidate_inventory_count"] = debug_sink["local_cleanup_candidate_inventory_count"]
                    debug_sink["terminal_state_blocked_by_local_cleanup"] = True
                return [local_cleanup_item]
            if "shear" in {str(f or "").strip().lower() for f in material_families}:
                shear_cleanup_item = _shear_tightening_as_local_cleanup_item(
                    guidance_state,
                    overview,
                    design_context.get("efficiency_state") if isinstance(design_context, dict) else None,
                )
                if isinstance(shear_cleanup_item, dict) and _guidance_item_is_resolved_one_click(shear_cleanup_item):
                    shear_cleanup_item["guidance_intent"] = "optional_cleanup"
                    shear_cleanup_item["local_cleanup_candidate"] = True
                    if min_dbg:
                        debug_sink["guidance_branch"] = "in_target_shear_material_local_cleanup"
                        debug_sink["selected_action_type"] = shear_cleanup_item.get("action_type")
                        debug_sink["selected_title"] = shear_cleanup_item.get("title_main")
                        debug_sink["family_utils"] = dict(family_utils)
                        debug_sink["materially_overprovided_families"] = list(material_families)
                        debug_sink["governing_family"] = governing_family
                        debug_sink["local_cleanup_search_ran"] = True
                        debug_sink["local_cleanup_search_exhaustive"] = True
                        debug_sink["safe_local_cleanup_count"] = 1
                        debug_sink["executable_safe_cleanup_count"] = 1
                        debug_sink["terminal_state_blocked_by_local_cleanup"] = True
                    return [shear_cleanup_item]
    resolved_one_click_candidate: dict | None = None
    # Bounded one-click search: only when keys do not all pass and a critical item needs
    # an actionable strengthen path. Skip the full search for in-band / passive outcomes
    # (handled later without this solver).
    run_bounded_one_click_solver = (
        bool(overview.get("any_fail"))
        and bool(critical)
    )
    if min_dbg:
        debug_sink["one_click_primary_requires_full_coverage"] = bool(primary_one_click_requires_full_coverage)
        debug_sink["one_click_primary_fail_keys"] = list(primary_one_click_fail_keys)
        debug_sink["one_click_primary_candidate_valid"] = False
        debug_sink["one_click_primary_candidate_valid_reason"] = "missing_candidate"
        debug_sink["one_click_primary_candidate_covers_all_current_failures"] = False
        debug_sink["one_click_primary_candidate_remaining_fail_keys"] = []
        debug_sink["one_click_commit_blocked_reason"] = None
        debug_sink["shear_fallback_primary_blocked_due_to_partial_coverage"] = False
    try:
        if run_bounded_one_click_solver:
            resolved_one_click_candidate = _solve_one_click_candidate(
                guidance_state,
                goal=_design_optimisation_goal(guidance_state),
                debug_enabled=debug_enabled,
            )
    except Exception:
        resolved_one_click_candidate = None
    if run_bounded_one_click_solver and (
        not isinstance(resolved_one_click_candidate, dict)
        or not bool(resolved_one_click_candidate.get("candidate_reaches_target_band"))
    ):
        try:
            direct_item = _direct_target_band_guidance_item(
                guidance_state,
                overview,
                mode_config,
                strengthening=True,
                debug_sink=debug_sink if min_dbg else None,
            )
        except Exception:
            direct_item = None
        if isinstance(direct_item, dict):
            if min_dbg:
                debug_sink["guidance_branch"] = "critical_direct_target_band_search"
                debug_sink["selected_action_type"] = direct_item.get("action_type")
                debug_sink["selected_title"] = direct_item.get("title_main")
                debug_sink["critical_branch_used_direct_target_band_search"] = True
                debug_sink["one_click_candidate_available_at_step_start"] = True
                debug_sink["one_click_candidate_label_at_step_start"] = str(direct_item.get("title_main") or "")
            return [direct_item]
    used_shear_fallback_candidate = False
    if (
        resolved_one_click_candidate is None
        and run_bounded_one_click_solver
        and str(governing_action or "") == "shear"
    ):
        resolved_one_click_candidate = _shear_governing_fallback_resolved_candidate(guidance_state, mode_config)
        used_shear_fallback_candidate = isinstance(resolved_one_click_candidate, dict)
    one_click_solver_trace = {}
    if full_dbg:
        debug_sink["one_click_solver"] = one_click_solver_trace
    if isinstance(resolved_one_click_candidate, dict):
        primary = _guidance_item_from_resolved_candidate(
            resolved_one_click_candidate,
            state=guidance_state,
            overview=overview,
            title=str(resolved_one_click_candidate.get("label") or "Apply one-click design"),
            reasoning="This option is the best compliant one-click design found in the bounded search.",
            status="FAIL",
            primary_action="Apply recommendation",
        )
        primary_one_click_valid, primary_one_click_meta = _candidate_is_valid_primary_one_click(
            primary,
            overview,
        )
        if min_dbg:
            payload = dict(primary.get("action_payload") or {})
            failure_coverage = dict(payload.get("failure_coverage") or {})
            debug_sink["one_click_critical_candidate_exists"] = True
            debug_sink["one_click_critical_candidate_label"] = str(resolved_one_click_candidate.get("label") or "")
            debug_sink["one_click_critical_candidate_action_type"] = str(primary.get("action_type") or "")
            debug_sink["one_click_critical_candidate_post_util"] = resolved_one_click_candidate.get("candidate_post_util", resolved_one_click_candidate.get("worst_util"))
            debug_sink["one_click_critical_candidate_reaches_target_band"] = bool(
                resolved_one_click_candidate.get("candidate_reaches_target_band"),
            )
            debug_sink["compound_shear_augmented"] = bool(
                resolved_one_click_candidate.get("compound_shear_augmented")
                or payload.get("compound_shear_augmented"),
            )
            debug_sink["covers_all_current_failures"] = bool(
                primary.get("covers_all_current_failures")
                or failure_coverage.get("covers_all_current_failures"),
            )
            debug_sink["covered_fail_keys"] = list(
                primary.get("covered_fail_keys")
                or failure_coverage.get("covered_fail_keys")
                or [],
            )
            debug_sink["remaining_fail_keys"] = list(
                primary.get("remaining_fail_keys")
                or failure_coverage.get("remaining_fail_keys")
                or [],
            )
            debug_sink["one_click_primary_requires_full_coverage"] = bool(
                primary_one_click_meta.get("requires_full_coverage"),
            )
            debug_sink["one_click_primary_fail_keys"] = list(primary_one_click_meta.get("fail_keys") or [])
            debug_sink["one_click_primary_candidate_valid"] = bool(primary_one_click_valid)
            debug_sink["one_click_primary_candidate_valid_reason"] = str(
                primary_one_click_meta.get("reason") or "missing_candidate",
            )
            debug_sink["one_click_primary_candidate_covers_all_current_failures"] = bool(
                primary_one_click_meta.get("covers_all_current_failures"),
            )
            debug_sink["one_click_primary_candidate_remaining_fail_keys"] = list(
                primary_one_click_meta.get("remaining_fail_keys") or [],
            )
            debug_sink["one_click_critical_candidate_surfaced"] = bool(primary_one_click_valid)
            debug_sink["one_click_critical_candidate_suppressed_reason"] = (
                None if primary_one_click_valid else str(primary_one_click_meta.get("reason") or "missing_candidate")
            )
            debug_sink["critical_branch_used_one_click_override"] = bool(primary_one_click_valid)
            if used_shear_fallback_candidate and not primary_one_click_valid:
                debug_sink["shear_fallback_primary_blocked_due_to_partial_coverage"] = bool(
                    str(primary_one_click_meta.get("reason") or "") == "partial_failure_coverage",
                )
            if primary_one_click_valid:
                debug_sink["primary_guidance_item_action_type"] = primary.get("action_type")
                debug_sink["primary_guidance_item_has_resolved_candidate_payload"] = bool(
                    payload.get("resolved_candidate_updates"),
                )
                debug_sink["primary_guidance_item_resolved_candidate_label"] = payload.get("resolved_candidate_label")
                debug_sink["guidance_branch"] = "critical_apply_resolved_candidate"
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
            debug_sink["one_click_candidate_available_at_step_start"] = True
            debug_sink["one_click_candidate_label_at_step_start"] = str(
                resolved_one_click_candidate.get("label") or payload.get("resolved_candidate_label") or "",
            )
        if primary_one_click_valid:
            guidance_branch = "critical_apply_resolved_candidate"
            return [primary]
        if min_dbg:
            debug_sink["one_click_invalid_solver_candidate_blocked_from_primary"] = True
            debug_sink["one_click_invalid_solver_candidate_blocked_reason"] = str(
                primary_one_click_meta.get("reason") or "candidate_not_valid_primary_one_click",
            )
    one_click_probe: dict | None = {} if min_dbg else None
    one_click_critical_item: dict | None = None
    one_click_candidate: dict | None = None
    try:
        if out_of_band_live and not bool(overview.get("all_key_pass")):
            mode_recommendation = _compute_mode_guidance_recommendation(guidance_state)
            if isinstance(mode_recommendation, dict):
                base_candidate = _evaluate_auto_design_candidate(guidance_state, source="guidance_primary_seed")
                one_click_candidate = _materialize_guidance_candidate(
                    base_candidate,
                    mode_recommendation,
                    source="guidance_primary_one_click_candidate",
                )
                if one_click_candidate:
                    _annotate_candidate_target_band_metrics(one_click_candidate, mode_config)
                if one_click_candidate and not bool(one_click_candidate.get("is_compliant")):
                    one_click_candidate = None
                if one_click_candidate and not bool(
                    one_click_candidate.get("candidate_reaches_target_band")
                    or one_click_candidate.get("reaches_target_band")
                ):
                    one_click_candidate = None
    except Exception:
        one_click_candidate = None
    if one_click_candidate:
        one_click_critical_item = _guidance_item_from_resolved_candidate(
            one_click_candidate,
            state=guidance_state,
            overview=overview,
            title=str(one_click_candidate.get("label") or "Apply one-click design"),
            reasoning="This option brings the design into the target utilisation band in one move.",
            status="FAIL",
            primary_action="Apply recommendation",
        )
        if isinstance(one_click_probe, dict):
            failure_coverage = dict((one_click_critical_item.get("action_payload") or {}).get("failure_coverage") or {})
            one_click_probe["one_click_critical_candidate_exists"] = True
            one_click_probe["one_click_critical_candidate_label"] = str(one_click_candidate.get("label") or "")
            one_click_probe["one_click_critical_candidate_action_type"] = str(
                one_click_critical_item.get("action_type")
                or (one_click_critical_item.get("action_payload") or {}).get("resolved_candidate_action_type")
                or "",
            )
            one_click_probe["one_click_critical_candidate_post_util"] = one_click_candidate.get("worst_util")
            one_click_probe["one_click_critical_candidate_reaches_target_band"] = True
            one_click_probe["compound_shear_augmented"] = bool(
                one_click_candidate.get("compound_shear_augmented")
                or (one_click_critical_item.get("action_payload") or {}).get("compound_shear_augmented"),
            )
            one_click_probe["covers_all_current_failures"] = bool(
                one_click_critical_item.get("covers_all_current_failures")
                or failure_coverage.get("covers_all_current_failures"),
            )
            one_click_probe["covered_fail_keys"] = list(
                one_click_critical_item.get("covered_fail_keys")
                or failure_coverage.get("covered_fail_keys")
                or [],
            )
            one_click_probe["remaining_fail_keys"] = list(
                one_click_critical_item.get("remaining_fail_keys")
                or failure_coverage.get("remaining_fail_keys")
                or [],
            )
            one_click_probe["one_click_critical_candidate_suppressed_reason"] = None
    else:
        one_click_critical_item = _get_one_click_band_reaching_candidate(
            guidance_state,
            overview,
            mode_config=mode_config,
            primary_hint=primary_critical,
            debug_extra=one_click_probe,
        )
    primary_one_click_valid = False
    primary_one_click_meta = {
        "requires_full_coverage": bool(primary_one_click_requires_full_coverage),
        "fail_keys": list(primary_one_click_fail_keys),
        "valid": False,
        "reason": "missing_candidate",
        "covers_all_current_failures": False,
        "remaining_fail_keys": [],
        "covered_fail_keys": [],
    }
    if one_click_critical_item is not None:
        primary_one_click_valid, primary_one_click_meta = _candidate_is_valid_primary_one_click(
            one_click_critical_item,
            overview,
        )
        if isinstance(one_click_probe, dict):
            one_click_probe["one_click_primary_requires_full_coverage"] = bool(
                primary_one_click_meta.get("requires_full_coverage"),
            )
            one_click_probe["one_click_primary_fail_keys"] = list(primary_one_click_meta.get("fail_keys") or [])
            one_click_probe["one_click_primary_candidate_valid"] = bool(primary_one_click_valid)
            one_click_probe["one_click_primary_candidate_valid_reason"] = str(
                primary_one_click_meta.get("reason") or "missing_candidate",
            )
            one_click_probe["one_click_primary_candidate_covers_all_current_failures"] = bool(
                primary_one_click_meta.get("covers_all_current_failures"),
            )
            one_click_probe["one_click_primary_candidate_remaining_fail_keys"] = list(
                primary_one_click_meta.get("remaining_fail_keys") or [],
            )
            if not primary_one_click_valid:
                one_click_probe["one_click_critical_candidate_suppressed_reason"] = str(
                    primary_one_click_meta.get("reason") or "missing_candidate",
        )
    if min_dbg:
        debug_sink["one_click_critical_candidate_exists"] = bool(one_click_probe.get("one_click_critical_candidate_exists"))
        debug_sink["one_click_critical_candidate_label"] = one_click_probe.get("one_click_critical_candidate_label")
        debug_sink["one_click_critical_candidate_action_type"] = one_click_probe.get("one_click_critical_candidate_action_type")
        debug_sink["one_click_critical_candidate_post_util"] = one_click_probe.get("one_click_critical_candidate_post_util")
        debug_sink["one_click_critical_candidate_reaches_target_band"] = bool(
            one_click_probe.get("one_click_critical_candidate_reaches_target_band"),
        )
        debug_sink["compound_shear_augmented"] = bool(one_click_probe.get("compound_shear_augmented"))
        debug_sink["covers_all_current_failures"] = bool(one_click_probe.get("covers_all_current_failures"))
        debug_sink["covered_fail_keys"] = list(one_click_probe.get("covered_fail_keys") or [])
        debug_sink["remaining_fail_keys"] = list(one_click_probe.get("remaining_fail_keys") or [])
        debug_sink["one_click_primary_requires_full_coverage"] = bool(
            one_click_probe.get("one_click_primary_requires_full_coverage", primary_one_click_requires_full_coverage),
        )
        debug_sink["one_click_primary_fail_keys"] = list(
            one_click_probe.get("one_click_primary_fail_keys") or primary_one_click_fail_keys,
        )
        debug_sink["one_click_primary_candidate_valid"] = bool(
            one_click_probe.get("one_click_primary_candidate_valid", primary_one_click_valid),
        )
        debug_sink["one_click_primary_candidate_valid_reason"] = one_click_probe.get(
            "one_click_primary_candidate_valid_reason",
            primary_one_click_meta.get("reason"),
        )
        debug_sink["one_click_primary_candidate_covers_all_current_failures"] = bool(
            one_click_probe.get(
                "one_click_primary_candidate_covers_all_current_failures",
                primary_one_click_meta.get("covers_all_current_failures"),
            ),
        )
        debug_sink["one_click_primary_candidate_remaining_fail_keys"] = list(
            one_click_probe.get("one_click_primary_candidate_remaining_fail_keys")
            or primary_one_click_meta.get("remaining_fail_keys")
            or [],
        )
        debug_sink["one_click_critical_candidate_surfaced"] = False
        debug_sink["one_click_critical_candidate_suppressed_reason"] = one_click_probe.get(
            "one_click_critical_candidate_suppressed_reason",
        )
        debug_sink["critical_branch_used_one_click_override"] = False
        if not out_of_band_live:
            debug_sink["one_click_critical_candidate_suppressed_reason"] = "already_in_target_band_or_passing"
        debug_sink["one_click_candidate_available_at_step_start"] = bool(
            one_click_probe.get("one_click_critical_candidate_exists"),
        )
        debug_sink["one_click_candidate_label_at_step_start"] = one_click_probe.get(
            "one_click_critical_candidate_label",
        )
    efficiency_state = compute_efficiency_tightening_state(guidance_state, context=design_context)
    safe_cleanup_mode_active = bool(efficiency_state.get("optimisation_safe_cleanup_mode_active"))
    if safe_cleanup_mode_active and not bool(overview.get("any_fail")):
        critical = []
        governing_item_is_critical = False
        primary_critical = None
        one_click_critical_item = None
        if min_dbg:
            debug_sink["safe_cleanup_mode_suppressed_nonfailing_critical_cards"] = True
            debug_sink["safe_cleanup_mode_reason"] = efficiency_state.get("optimisation_safe_cleanup_mode_reason")
    if (
        one_click_critical_item is not None
        and out_of_band_live
        and critical
        and bool(primary_one_click_valid)
    ):
        guidance_branch = "critical_apply_resolved_candidate"
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = one_click_critical_item.get("action_type")
            debug_sink["selected_title"] = one_click_critical_item.get("title_main")
            debug_sink["one_click_critical_candidate_surfaced"] = True
            debug_sink["one_click_critical_candidate_suppressed_reason"] = None
            debug_sink["critical_branch_used_one_click_override"] = True
            debug_sink["primary_guidance_item_action_type"] = one_click_critical_item.get("action_type")
            debug_sink["primary_guidance_item_has_resolved_candidate_payload"] = bool(
                (one_click_critical_item.get("action_payload") or {}).get("resolved_candidate_updates"),
            )
            debug_sink["primary_guidance_item_resolved_candidate_label"] = (
                (one_click_critical_item.get("action_payload") or {}).get("resolved_candidate_label")
            )
        return [one_click_critical_item]
    if (
        one_click_critical_item is not None
        and out_of_band_live
        and (bool(overview.get("any_fail")) or bool(overview.get("any_warn")))
        and bool(primary_one_click_valid)
    ):
        guidance_branch = "critical_apply_resolved_candidate_noncritical_bucket"
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = one_click_critical_item.get("action_type")
            debug_sink["selected_title"] = one_click_critical_item.get("title_main")
            debug_sink["one_click_critical_candidate_surfaced"] = True
            debug_sink["one_click_critical_candidate_suppressed_reason"] = None
            debug_sink["critical_branch_used_one_click_override"] = True
        return [one_click_critical_item]
    if critical and governing_item_is_critical:
        primary = primary_critical or critical[0]
        action_type = str(primary.get("action_type") or "")
        guidance_branch = f"critical_{action_type}" if action_type else "critical_items"
        _log_guidance_branch_governing_mismatch(
            guidance_branch=guidance_branch,
            governing_action=governing_action,
            primary_utils=primary_utils,
            selected_item=primary,
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
        _compound_ud_dbg: dict = {}
        compound_item = _try_compound_strengthening_guidance_item(
            guidance_state,
            overview,
            primary,
            compound_underdesign_debug=_compound_ud_dbg if min_dbg else None,
        )
        if min_dbg:
            for _k_ud, _v_ud in _compound_ud_dbg.items():
                if str(_k_ud).startswith("underdesign_"):
                    debug_sink[_k_ud] = _v_ud
        if compound_item:
            head = [compound_item]
        else:
            head = [primary]
        # Single primary critical card UX: do not append a second competing critical card.
        return head
    if critical and not governing_item_is_critical and bool(guidance_state.get("_dev_mode")):
        _agent_debug_log(
            "Suppressed non-governing critical branch",
            {
                "governing_action": governing_action,
                "primary_utils": primary_utils,
                "suppressed_critical_items": [
                    {
                        "check_key": item.get("check_key"),
                        "title": item.get("title_main"),
                        "action_type": item.get("action_type"),
                        "util": item.get("util"),
                    }
                    for item in critical
                ],
                "governing_item": None if governing_item is None else {
                    "check_key": governing_item.get("check_key"),
                    "title": governing_item.get("title_main"),
                    "action_type": governing_item.get("action_type"),
                    "util": governing_item.get("util"),
                    "bucket": governing_item.get("bucket"),
                },
            },
            location="inputs_page.py:_compute_design_guidance_items",
            hypothesis_id="H_GUIDANCE_GOVERNING",
        )
    if full_dbg:
        debug_sink["efficiency_tightening_state"] = efficiency_state
        debug_sink["efficiency_actions_used"] = efficiency_state.get("actions_used")
        debug_sink["is_efficiency_reduction_mode"] = bool(efficiency_state.get("is_efficiency_reduction_mode"))
        debug_sink["efficiency_exhaustion_map"] = efficiency_state.get("exhaustion_map")
        debug_sink["efficiency_worst_util"] = efficiency_state.get("worst_util")
        debug_sink["guidance_target_efficiency_band"] = [
            efficiency_state.get("target_band_lo"),
            efficiency_state.get("target_band_hi"),
        ]
        debug_sink["strongly_underutilised"] = bool(efficiency_state.get("strongly_underutilised"))
        debug_sink["very_low_demand"] = bool(efficiency_state.get("very_low_demand"))
        debug_sink["optimisation_safe_cleanup_mode_active"] = bool(
            efficiency_state.get("optimisation_safe_cleanup_mode_active")
        )
        debug_sink["optimisation_safe_cleanup_mode_reason"] = efficiency_state.get(
            "optimisation_safe_cleanup_mode_reason"
        )
        debug_sink["optimisation_cleanup_candidates_found_count"] = int(
            efficiency_state.get("optimisation_cleanup_candidates_found_count") or 0
        )
    if min_dbg:
        debug_sink.setdefault("optimisation_selector_governing_action", str(governing_action or "other"))
        debug_sink.setdefault("optimisation_selector_family_bias_applied", False)
        debug_sink.setdefault("optimisation_selector_candidate_counts_by_family", {})
        debug_sink.setdefault("optimisation_selector_winning_family", None)
        debug_sink.setdefault("optimisation_selector_used_geometry_fallback", False)
        debug_sink.setdefault("optimisation_selector_fallback_reason", None)
        debug_sink.setdefault("optimisation_selector_candidate_reaches_target_band", False)
        debug_sink.setdefault("optimisation_selector_candidate_all_key_pass", False)
        debug_sink.setdefault("primary_optimisation_selection_owner", "legacy_fallback")
    if not bool(overview.get("any_fail")):
        reshape_item = _in_target_shear_congestion_reshape_guidance_item(
            guidance_state,
            overview,
            mode_config,
            debug_sink=debug_sink if full_dbg else None,
        )
        if reshape_item:
            guidance_branch = "in_target_shear_congestion_reshape"
            if full_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = reshape_item.get("action_type")
                debug_sink["selected_title"] = reshape_item.get("title_main")
                debug_sink["actionable_target_band_winner_exists"] = True
                debug_sink["actionable_target_band_winner_family"] = "compound"
                debug_sink["actionable_target_band_winner_subfamilies"] = ["geometry", "bottom_reo", "shear"]
                debug_sink["actionable_target_band_winner_change_lines"] = list(
                    reshape_item.get("guidance_change_lines") or []
                )
                debug_sink["optimal_short_circuit_blocked"] = True
                debug_sink["optimal_short_circuit_block_reason"] = "in_target_shear_congestion_reshape"
                debug_sink["surfaced_guidance_branch"] = guidance_branch
                debug_sink["surfaced_selected_action_type"] = reshape_item.get("action_type")
                debug_sink["surfaced_selected_title"] = reshape_item.get("title_main")
            elif min_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = reshape_item.get("action_type")
                debug_sink["selected_title"] = reshape_item.get("title_main")
            return [reshape_item]
    if str(efficiency_state.get("classification") or "") == "very_low_demand":
        vld_item = _very_low_demand_guidance_item(guidance_state, overview)
        guidance_branch = "very_low_demand"
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = vld_item.get("action_type")
            debug_sink["selected_title"] = vld_item.get("title_main")
        return [vld_item]
    efficiency_items = _efficiency_guidance_items(guidance_state, efficiency_state)
    compound_eff_item = _try_compound_efficiency_guidance_item(guidance_state, efficiency_state)
    if compound_eff_item:
        compound_eff_item["priority"] = float(compound_eff_item.get("priority") or 0.0) + 25.0
        efficiency_items.insert(0, compound_eff_item)
    if full_dbg:
        debug_sink["terminal_state_blocked"] = efficiency_state.get("terminal_state_blocked")
        debug_sink["terminal_state_block_reason"] = efficiency_state.get("terminal_state_block_reason")
        debug_sink["efficiency_guidance_items_summary"] = [
            {"title_main": i.get("title_main"), "action_type": i.get("action_type")}
            for i in efficiency_items
            if isinstance(i, dict)
        ]
    if efficiency_items:
        efficiency_items.sort(key=lambda item: item["priority"], reverse=True)
        selector_result = _select_primary_optimisation_candidate(
            state=guidance_state,
            overview=overview,
            mode_config=mode_config,
            governing_action=governing_action,
            candidates=efficiency_items,
            overdesign_stepwise_band_fallback=bool(
                str(efficiency_state.get("classification") or "").strip().lower() == "inefficient"
                and bool(overview.get("all_key_pass"))
            ),
        )
        primary = selector_result.get("selected_candidate")
        selected_family = selector_result.get("selected_family")
        selector_debug = dict(selector_result.get("selector_debug") or {})
        if primary is None:
            primary = next(
                (
                    item for item in efficiency_items
                    if str(item.get("check_key") or "") == str(governing_action or "")
                ),
                efficiency_items[0],
            )
            selected_family = _optimisation_candidate_family(primary, guidance_state)
            selector_debug = {
                **selector_debug,
                "optimisation_selector_winning_family": selected_family,
                "optimisation_selector_fallback_reason": (
                    selector_debug.get("optimisation_selector_fallback_reason")
                    or "shared_selector_no_primary_legacy_order_used"
                ),
                "primary_optimisation_selection_owner": "legacy_fallback",
            }
        action_type = str(primary.get("action_type") or "")
        guidance_branch = f"efficiency_{action_type}" if action_type else "efficiency_tightening"
        _log_guidance_branch_governing_mismatch(
            guidance_branch=guidance_branch,
            governing_action=governing_action,
            primary_utils=primary_utils,
            selected_item=primary,
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
            debug_sink["optimisation_selector_governing_action"] = selector_debug.get(
                "optimisation_selector_governing_action",
            )
            debug_sink["optimisation_selector_family_bias_applied"] = bool(
                selector_debug.get("optimisation_selector_family_bias_applied"),
            )
            debug_sink["optimisation_selector_candidate_counts_by_family"] = dict(
                selector_debug.get("optimisation_selector_candidate_counts_by_family") or {},
            )
            debug_sink["optimisation_selector_winning_family"] = selector_debug.get(
                "optimisation_selector_winning_family",
            ) or selected_family
            debug_sink["optimisation_selector_used_geometry_fallback"] = bool(
                selector_debug.get("optimisation_selector_used_geometry_fallback"),
            )
            debug_sink["optimisation_selector_fallback_reason"] = selector_debug.get(
                "optimisation_selector_fallback_reason",
            )
            debug_sink["optimisation_selector_candidate_reaches_target_band"] = bool(
                selector_debug.get("optimisation_selector_candidate_reaches_target_band"),
            )
            debug_sink["optimisation_selector_candidate_all_key_pass"] = bool(
                selector_debug.get("optimisation_selector_candidate_all_key_pass"),
            )
            debug_sink["primary_optimisation_selection_owner"] = selector_debug.get(
                "primary_optimisation_selection_owner",
                "legacy_fallback",
            )
            debug_sink["overdesign_no_band_reacher_but_compliant_candidates_exist"] = bool(
                selector_debug.get("overdesign_no_band_reacher_but_compliant_candidates_exist"),
            )
            debug_sink["overdesign_stepwise_fallback_used"] = bool(
                selector_debug.get("overdesign_stepwise_fallback_used"),
            )
            debug_sink["overdesign_stepwise_fallback_family"] = selector_debug.get(
                "overdesign_stepwise_fallback_family",
            )
            debug_sink["overdesign_stepwise_fallback_reason"] = selector_debug.get(
                "overdesign_stepwise_fallback_reason",
            )
            debug_sink["overdesign_stepwise_selected_post_util"] = selector_debug.get(
                "overdesign_stepwise_selected_post_util",
            )
            if str(debug_sink["primary_optimisation_selection_owner"]) == "legacy_fallback":
                debug_sink["legacy_fallback_reason"] = (
                    selector_debug.get("optimisation_selector_fallback_reason")
                    or "shared_selector_unavailable"
                )
                debug_sink["candidate_family"] = selected_family
                debug_sink["governing_action"] = governing_action
        remaining = [item for item in efficiency_items if item is not primary]
        return [primary] + remaining[:1]
    if overview["all_key_pass"] and target_band_with_eps_passed:
        tb_probe: dict | None = {} if full_dbg else None
        actionable_tb = _get_actionable_target_band_winner(
            guidance_state, overview, debug_extra=tb_probe,
        )
        if actionable_tb:
            guidance_branch = "target_band_actionable_winner"
            if full_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = actionable_tb.get("action_type")
                debug_sink["selected_title"] = actionable_tb.get("title_main")
                debug_sink["actionable_target_band_winner_exists"] = True
                debug_sink["actionable_target_band_winner_family"] = tb_probe.get("family")
                debug_sink["actionable_target_band_winner_subfamilies"] = tb_probe.get("subfamilies")
                debug_sink["actionable_target_band_winner_change_lines"] = tb_probe.get("change_lines")
                debug_sink["optimal_short_circuit_blocked"] = True
                debug_sink["optimal_short_circuit_block_reason"] = str(
                    tb_probe.get("target_band_override_reason") or "target_band_strict_override_passed",
                )
                debug_sink["surfaced_guidance_branch"] = guidance_branch
                debug_sink["surfaced_selected_action_type"] = actionable_tb.get("action_type")
                debug_sink["surfaced_selected_title"] = actionable_tb.get("title_main")
                _merge_target_band_probe_to_debug_sink(debug_sink, tb_probe)
            elif min_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = actionable_tb.get("action_type")
                debug_sink["selected_title"] = actionable_tb.get("title_main")
            return [actionable_tb]
        guidance_branch = "optimal"
        optimal_item = _optimal_guidance_item(guidance_state, overview)
        if full_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = optimal_item.get("action_type")
            debug_sink["selected_title"] = optimal_item.get("title_main")
            debug_sink["actionable_target_band_winner_exists"] = False
            debug_sink["actionable_target_band_winner_family"] = None
            debug_sink["actionable_target_band_winner_subfamilies"] = None
            debug_sink["actionable_target_band_winner_change_lines"] = None
            debug_sink["optimal_short_circuit_blocked"] = False
            debug_sink["optimal_short_circuit_block_reason"] = str(
                tb_probe.get("target_band_override_reason") or tb_probe.get("reason") or "no_actionable_winner",
            )
            debug_sink["surfaced_guidance_branch"] = guidance_branch
            debug_sink["surfaced_selected_action_type"] = optimal_item.get("action_type")
            debug_sink["surfaced_selected_title"] = optimal_item.get("title_main")
            _merge_target_band_probe_to_debug_sink(debug_sink, tb_probe)
        elif min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = optimal_item.get("action_type")
            debug_sink["selected_title"] = optimal_item.get("title_main")
        return [optimal_item]
    passive_fallback_allowed = (
        overview["all_key_pass"]
        and (
            _is_in_target_zone_with_eps(overview, mode_config, eps=TARGET_BAND_EPS)
            or not _efficiency_state_has_valid_candidate(efficiency_state)
        )
    )
    if filtered:
        primary = next(
            (
                item for item in filtered
                if str(item.get("check_key") or "") == str(governing_action or "")
            ),
            filtered[0],
        )
        action_type = str(primary.get("action_type") or "")
        guidance_branch = f"passing_guidance_{action_type}" if action_type else "passing_guidance_fallback"
        _log_guidance_branch_governing_mismatch(
            guidance_branch=guidance_branch,
            governing_action=governing_action,
            primary_utils=primary_utils,
            selected_item=primary,
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
        return [primary]
    if not passive_fallback_allowed:
        guidance_branch = "passing_guidance_blocked"
        blocked_item = _guidance_item(
            "general",
            "Design can be tightened",
            "Review optimisation options",
            "Automatic tightening did not yield a safe passive fallback under the resolved action set.",
            (
                f"Why: the current beam passes, but the resolved actions still place it outside the preferred "
                f"target zone for {_design_optimisation_goal_label(guidance_state).lower()}."
            ),
            "Key levers: optimisation preference, geometry, reinforcement",
            None,
            None,
            status="EFFICIENCY",
            util=overview["worst_util"],
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = blocked_item.get("action_type")
            debug_sink["selected_title"] = blocked_item.get("title_main")
        return [blocked_item]
    guidance_branch = "passing_guidance_fallback"
    passing_item = _passing_guidance_item(guidance_state, overview)
    if min_dbg:
        debug_sink["guidance_branch"] = guidance_branch
        debug_sink["selected_action_type"] = passing_item.get("action_type")
        debug_sink["selected_title"] = passing_item.get("title_main")
    return [passing_item]


def _compute_design_guidance_items(
    state: dict,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
    request_kind: str = "design_guide",
) -> dict:
    """
    Layer 3 pure guidance compute (Recommendation Engine entrypoint).
    Returns all artifacts needed by UI/state layers without mutating session state.

    Canonical recommendation_result matches the Design Guide primary card: it is derived from
    deduped guidance items using the same resolver state as the panel (guidance_resolved_state).

    request_kind:
      - "design_guide": guidance core only (default).
      - "auto_design": also runs run_auto_design_solver(...) as an internal subroutine and prepends
        its recommendation as a guidance item so the same dedupe + primary-card pipeline applies.
    """
    request_kind_norm = str(request_kind or "design_guide").strip() or "design_guide"
    state = _design_guide_lightweight_guidance_state(state)
    canonical_state = _build_canonical_design_state_pack(state)
    guidance_runtime_fp = stable_fingerprint_for_payload(
        {
            "guidance_algorithm_version": DESIGN_GUIDE_ALGORITHM_VERSION,
            "design_guide_algorithm_version": DESIGN_GUIDE_ALGORITHM_VERSION,
            "request_kind": request_kind_norm,
            "guidance_debug_verbose": bool(guidance_debug_verbose),
            "debug_enabled": bool(debug_enabled),
            "canonical_state": canonical_state,
            "post_cleanup_acceptance_enabled": bool(
                st.session_state.get("_design_guide_post_cleanup_acceptance_enabled")
            ),
            "post_cleanup_acceptance_fp": st.session_state.get("_design_guide_post_cleanup_acceptance_fp"),
            "post_cleanup_acceptance_global_match": (
                _local_cleanup_acceptance_fingerprint(state) in _DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
            ),
        }
    )
    cached_runtime_payload = get_rerun_pure_cache(
        "compute_design_guidance_items",
        guidance_runtime_fp,
    )
    if isinstance(cached_runtime_payload, dict):
        ux_probe_record(
            "guidance_item_computation.compute_design_guidance_items",
            fingerprint=guidance_runtime_fp,
            cache_hit=True,
            meta={"request_kind": request_kind_norm},
        )
        speed_profile_record(
            "guidance_item_computation.compute_design_guidance_items.cache_hit",
            0.0,
            category="compute",
        )
        return cached_runtime_payload
    ux_probe_record(
        "guidance_item_computation.compute_design_guidance_items",
        fingerprint=guidance_runtime_fp,
        cache_hit=False,
        meta={"request_kind": request_kind_norm},
    )
    canonical_pack_valid = _canonical_pack_is_valid(canonical_state)
    state_coherence = _design_state_coherence_check(canonical_state)
    coherence_should_block = bool(state_coherence.get("coherence_should_block"))
    try:
        import session_state_final_log as _ssl

        _ssl.ssl_mark_recommendation_engine_invoked()
    except Exception:
        pass
    if (not canonical_pack_valid) or coherence_should_block:
        stop_reason = str(
            canonical_state.get("canonical_pack_error")
            or (state_coherence.get("coherence_blocking_issues") or ["state_incoherent_after_rebuild"])[0]
        )
        actions_used = _resolve_design_actions_from_state(state)
        blocked_guidance_branch = "blocked_invalid_canonical_pack" if not canonical_pack_valid else "blocked_hard_invalid_state"
        blocked_user_reason = (
            "Add longitudinal reinforcement before running auto-design."
            if stop_reason == "no_bars_resolved"
            else f"Design Guide blocked: {stop_reason}."
        )
        blocked_debug = {
            "guidance_branch": blocked_guidance_branch,
            "selected_action_type": None,
            "selected_title": None,
            "guidance_resolved_state": dict(canonical_state),
            "longitudinal_reo_truth_source": canonical_state.get("longitudinal_reo_truth_source"),
            "row_model_legacy_sync_applied": bool(canonical_state.get("row_model_legacy_sync_applied")),
            "row_model_legacy_sync_diff_keys": list(canonical_state.get("row_model_legacy_sync_diff_keys") or []),
            "overview": {
                "packs": {},
                "statuses": {
                    "bending": "FAIL",
                    "shear": "—",
                    "crack": "—",
                    "deflection": "—",
                },
                "utils": {
                    "bending": None,
                    "shear": None,
                    "crack": None,
                    "deflection": None,
                },
                "any_fail": True,
                "any_warn": False,
                "all_key_pass": False,
                "worst_util": 0.0,
                "actions_used": dict(actions_used or {}),
            },
            "efficiency_tightening_state": {
                "classification": "blocked_invalid_state",
            },
            **_coherence_debug_fields(state_coherence),
            "canonical_pack_built": bool(canonical_state.get("canonical_pack_built")),
            "canonical_pack_valid": canonical_pack_valid,
            "canonical_pack_source": canonical_state.get("canonical_pack_source"),
            "canonical_pack_error": canonical_state.get("canonical_pack_error"),
            "canonical_pack_error_stage": canonical_state.get("canonical_pack_error_stage"),
            "solver_blocked_by_incoherent_state": True,
            "stop_reason": stop_reason,
            "user_visible_no_action_reason": blocked_user_reason,
        }
        out: dict = {
            "guidance_items": [],
            "blocked_state_class": "hard_invalid",
            "debug_trace": blocked_debug,
            "cache_data": {
                "guidance_cache_fp": _candidate_cache_key(dict(state or {})),
            },
            "recommendation_result": None,
        }
        if request_kind_norm == "auto_design":
            out["auto_design_solver_recommendation"] = None
            out["auto_design_seed_failed"] = True
        set_rerun_pure_cache("compute_design_guidance_items", guidance_runtime_fp, out)
        return out
    try:
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE fast_path_before_overview", file=sys.stderr, flush=True)
        fast_overview = _collect_design_overview(state)
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE fast_path_after_overview", file=sys.stderr, flush=True)
        fast_mode_cfg = _design_mode_config(_design_optimisation_goal(state))
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE fast_path_after_mode_cfg", file=sys.stderr, flush=True)
        fast_in_target = bool(
            _overview_required_checks_acceptable(fast_overview)
            and not fast_overview.get("any_fail")
            and _is_in_target_zone_with_eps(fast_overview, fast_mode_cfg, eps=TARGET_BAND_EPS)
        )
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print(f"DG_STAGE fast_path_after_in_target in_target={fast_in_target}", file=sys.stderr, flush=True)
        fast_utils = dict(fast_overview.get("utils") or {})
        fast_shear_util = _parse_util_value(fast_utils.get("shear"))
        fast_actions = dict((_build_design_actions_context(state) or {}).get("actions") or {})
        fast_shear_demand_meaningful = not _shear_demands_negligible(fast_actions)
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print(f"DG_STAGE fast_path_after_shear_util shear={fast_shear_util}", file=sys.stderr, flush=True)
        if (
            request_kind_norm == "design_guide"
            and False  # Disabled: real-click proof showed this shortcut can bypass final accepted-state evidence.
            and fast_in_target
            and _shear_reinforcement_is_active(state)
            and fast_shear_demand_meaningful
            and fast_shear_util is not None
            and float(fast_shear_util) < float(FINAL_ACCEPTED_MIN_FAMILY_UTIL)
        ):
            _fast_stage_debug = os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
            fast_efficiency_state = {
                "family_utils": dict(fast_utils),
                "materially_overprovided_families": ["shear"],
                "shear_cleanup_possible": True,
            }
            fast_item = None
            no_links_updates = {
                "lig_d": 0,
                "lig_legs": 0,
                "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
            }
            no_links_state = dict(state)
            no_links_state.update(no_links_updates)
            if (
                not _updates_match_state(state, no_links_updates)
                and _shear_cleanup_materially_reduces_reinforcement(state, no_links_state)
            ):
                if _fast_stage_debug:
                    print("DG_STAGE fast_path_before_no_links_eval", file=sys.stderr, flush=True)
                no_links_candidate = _evaluate_auto_design_candidate(
                    state,
                    updates=no_links_updates,
                    source="target_band_active_shear_local_cleanup_fast_path",
                    label="Remove shear links",
                    action_type="apply_shear_recommendation",
                )
                if _fast_stage_debug:
                    print(f"DG_STAGE fast_path_after_no_links_eval candidate={bool(isinstance(no_links_candidate, dict))}", file=sys.stderr, flush=True)
                if isinstance(no_links_candidate, dict):
                    no_links_overview = dict(no_links_candidate.get("overview") or {})
                    if _fast_stage_debug:
                        print("DG_STAGE fast_path_before_no_links_audit", file=sys.stderr, flush=True)
                    no_links_audit = _post_click_accepted_green_audit(
                        no_links_overview,
                        blocker_source={},
                        state=no_links_state,
                    )
                    if _fast_stage_debug:
                        print("DG_STAGE fast_path_after_no_links_audit", file=sys.stderr, flush=True)
                    no_links_worst = _parse_util_value(
                        no_links_overview.get("worst_util", no_links_candidate.get("worst_util"))
                    )
                    fast_t_lo, fast_t_hi, _ = _resolved_efficiency_target_band(
                        fast_mode_cfg,
                        goal=_design_optimisation_goal(state),
                    )
                    if (
                        no_links_worst is not None
                        and float(fast_t_lo) <= float(no_links_worst) <= float(fast_t_hi)
                        and _overview_required_checks_acceptable(no_links_overview)
                        and not bool(no_links_overview.get("any_fail"))
                        and bool(no_links_audit.get("post_click_accepted_green_valid"))
                    ):
                        fast_base_item = _guidance_item(
                            "shear",
                            "Design is safe - optional cleanup available",
                            "Shear reserve is high. Optional cleanup can remove the link layout.",
                            "Alternative: remove shear links.",
                            "Why: shear passes below the target band, so the local link layout can be relaxed safely.",
                            "Key levers: link spacing, number of legs, target utilisation band",
                            "apply_shear_recommendation",
                            {"updates": dict(no_links_updates)},
                            status="EFFICIENCY",
                            util=no_links_worst,
                        )
                        no_links_candidate = {
                            **dict(no_links_candidate),
                            "updates": dict(no_links_updates),
                            "action_type": "apply_shear_recommendation",
                            "label": "Remove shear links",
                            "candidate_post_util": no_links_worst,
                            "candidate_reaches_target_band": True,
                            "post_click_exact_blockers_by_family": dict(
                                no_links_audit.get("post_click_exact_blockers_by_family") or {}
                            ),
                        }
                        fast_item = _promote_guidance_item_to_resolved_candidate(
                            fast_base_item,
                            no_links_candidate,
                            state=state,
                        )
            if not isinstance(fast_item, dict) and _fast_stage_debug:
                print("DG_STAGE fast_path_skipped_non_final_shear_tightening_fallback", file=sys.stderr, flush=True)
            if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
                print(f"DG_STAGE fast_path_after_item item={bool(isinstance(fast_item, dict))}", file=sys.stderr, flush=True)
            if isinstance(fast_item, dict):
                fast_items = _design_guide_apply_button_contracts_to_items(
                    [fast_item],
                    state=state,
                )
                fast_items = _design_guide_apply_display_truth_to_items(
                    fast_items,
                    state=state,
                    overview=fast_overview,
                    mode_config=fast_mode_cfg,
                )
                fast_recommendation = _recommendation_result_for_primary_guidance_card(
                    fast_items,
                    state,
                    branch="target_band_active_shear_local_cleanup_fast_path",
                    request_kind=request_kind_norm,
                )
                fast_primary = fast_items[0] if fast_items and isinstance(fast_items[0], dict) else {}
                fast_evidence = dict(
                    fast_primary.get("candidate_search_evidence")
                    or (fast_primary.get("action_payload") or {}).get("candidate_search_evidence")
                    or (fast_primary.get("resolved_candidate") or {}).get("candidate_search_evidence")
                    or {}
                )
                fast_debug = {
                    "guidance_branch": "target_band_active_shear_local_cleanup_fast_path",
                    "selected_action_type": fast_primary.get("action_type"),
                    "selected_title": fast_primary.get("title_main"),
                    "overview": dict(fast_overview),
                    "efficiency_tightening_state": dict(fast_efficiency_state),
                    "candidate_search_evidence": dict(fast_evidence),
                    "local_cleanup_candidate_search_evidence": dict(fast_evidence),
                    "family_utils": dict(fast_utils),
                    "materially_overprovided_families": ["shear"],
                    "local_cleanup_search_ran": True,
                    "local_cleanup_search_exhaustive": True,
                    "safe_local_cleanup_count": 1,
                    "executable_safe_cleanup_count": 1,
                    "design_guide_render_state_source": "target_band_active_shear_local_cleanup_fast_path",
                    **_coherence_debug_fields(state_coherence),
                    "canonical_pack_built": bool(canonical_state.get("canonical_pack_built")),
                    "canonical_pack_valid": bool(canonical_state.get("canonical_pack_valid")),
                    "canonical_pack_source": canonical_state.get("canonical_pack_source"),
                    "canonical_pack_error": canonical_state.get("canonical_pack_error"),
                    "canonical_pack_error_stage": canonical_state.get("canonical_pack_error_stage"),
                    "longitudinal_reo_truth_source": canonical_state.get("longitudinal_reo_truth_source"),
                    "row_model_legacy_sync_applied": bool(canonical_state.get("row_model_legacy_sync_applied")),
                    "row_model_legacy_sync_diff_keys": list(canonical_state.get("row_model_legacy_sync_diff_keys") or []),
                    "solver_blocked_by_incoherent_state": False,
                    "primary_guidance_intent": str(fast_primary.get("guidance_intent") or "").strip(),
                    "primary_button_contract": dict(fast_primary.get("button_contract") or {}),
                    "primary_display_truth": dict(fast_primary.get("display_truth") or {}),
                }
                fast_out = {
                    "guidance_items": list(fast_items or []),
                    "debug_trace": dict(fast_debug),
                    "cache_data": {
                        "guidance_cache_fp": _candidate_cache_key(dict(state or {})),
                    },
                    "recommendation_result": fast_recommendation,
                }
                set_rerun_pure_cache("compute_design_guidance_items", guidance_runtime_fp, fast_out)
                return fast_out
    except Exception:
        pass
    debug_trace: dict = {}
    rank_trace: list[dict] = []
    reco_trace: list[dict] = []
    global _ACTIVE_GUIDANCE_RANK_TRACE
    global _ACTIVE_GUIDANCE_RECO_TRACE
    prev_rank_trace = _ACTIVE_GUIDANCE_RANK_TRACE
    prev_reco_trace = _ACTIVE_GUIDANCE_RECO_TRACE
    _ACTIVE_GUIDANCE_RANK_TRACE = rank_trace if debug_enabled else None
    _ACTIVE_GUIDANCE_RECO_TRACE = reco_trace if debug_enabled else None
    try:
        guidance_items = _compute_design_guidance_items_core(
            state,
            debug_sink=debug_trace,
            guidance_debug_verbose=guidance_debug_verbose,
            debug_enabled=debug_enabled,
        )
    finally:
        _ACTIVE_GUIDANCE_RANK_TRACE = prev_rank_trace
        _ACTIVE_GUIDANCE_RECO_TRACE = prev_reco_trace
    if rank_trace:
        debug_trace["rank_trace"] = list(rank_trace)
    if reco_trace:
        debug_trace["reco_trace"] = list(reco_trace)
    if (
        request_kind_norm == "design_guide"
        and str(debug_trace.get("guidance_branch") or "").strip() == "not_started"
    ):
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE wrapper_not_started_fast_return", file=sys.stderr, flush=True)
        debug_trace.update(_coherence_debug_fields(state_coherence))
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE wrapper_not_started_after_coherence", file=sys.stderr, flush=True)
        debug_trace["canonical_pack_built"] = bool(canonical_state.get("canonical_pack_built"))
        debug_trace["canonical_pack_valid"] = bool(canonical_state.get("canonical_pack_valid"))
        debug_trace["canonical_pack_source"] = canonical_state.get("canonical_pack_source")
        debug_trace["solver_blocked_by_incoherent_state"] = False
        debug_trace["design_guide_render_state_source"] = "lightweight_overlay_state"
        out = {
            "guidance_items": list(guidance_items or []),
            "debug_trace": dict(debug_trace),
            "cache_data": {
                "guidance_cache_fp": _candidate_cache_key(dict(state or {})),
            },
            "recommendation_result": None,
        }
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE wrapper_not_started_before_cache", file=sys.stderr, flush=True)
        set_rerun_pure_cache("compute_design_guidance_items", guidance_runtime_fp, out)
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE wrapper_not_started_return", file=sys.stderr, flush=True)
        return out

    auto_design_solver_recommendation: dict | None = None
    auto_design_seed_failed = False
    if request_kind_norm == "auto_design":
        gs = _guidance_state_snapshot(dict(state or {}))
        seed_candidate = evaluate_candidate_full(gs, source="single_pass_auto_design_seed")
        if seed_candidate is None:
            auto_design_seed_failed = True
        else:
            results = _auto_design_results_from_candidate(seed_candidate)
            auto_design_solver_recommendation = run_auto_design_solver(gs, results)
            if auto_design_solver_recommendation:
                injected = _auto_design_solver_recommendation_as_guidance_item(auto_design_solver_recommendation)
                if injected is not None:
                    guidance_items = [injected] + list(guidance_items or [])
        if isinstance(debug_trace, dict):
            debug_trace["recommendation_engine_auto_design"] = {
                "seed_failed": bool(auto_design_seed_failed),
                "solver_returned_value": auto_design_solver_recommendation is not None,
            }

    coherent_trace, coherence_repairs = _ensure_design_guide_debug_trace_coherent(
        state=dict(state or {}),
        guidance_items=list(guidance_items or []),
        debug_trace=dict(debug_trace),
    )
    if coherence_repairs:
        _agent_debug_log(
            "compute_debug_trace_coherence_repaired",
            {"fields": list(coherence_repairs)},
            location="inputs_page.py:_compute_design_guidance_items:debug_trace_coherence",
            hypothesis_id="H_DG_DEBUG_TRACE_COHERENCE",
        )
    debug_trace = coherent_trace
    debug_trace.update(_coherence_debug_fields(state_coherence))
    debug_trace["canonical_pack_built"] = bool(canonical_state.get("canonical_pack_built"))
    debug_trace["canonical_pack_valid"] = bool(canonical_state.get("canonical_pack_valid"))
    debug_trace["canonical_pack_source"] = canonical_state.get("canonical_pack_source")
    debug_trace["canonical_pack_error"] = canonical_state.get("canonical_pack_error")
    debug_trace["canonical_pack_error_stage"] = canonical_state.get("canonical_pack_error_stage")
    debug_trace["longitudinal_reo_truth_source"] = canonical_state.get("longitudinal_reo_truth_source")
    debug_trace["row_model_legacy_sync_applied"] = bool(canonical_state.get("row_model_legacy_sync_applied"))
    debug_trace["row_model_legacy_sync_diff_keys"] = list(canonical_state.get("row_model_legacy_sync_diff_keys") or [])
    debug_trace["solver_blocked_by_incoherent_state"] = False
    debug_trace["design_guide_render_state_source"] = "lightweight_overlay_state"

    gb = debug_trace.get("guidance_branch") if isinstance(debug_trace, dict) else None
    branch_hint = str(gb).strip() if isinstance(gb, str) and str(gb).strip() else None
    gs_resolved = debug_trace.get("guidance_resolved_state") if isinstance(debug_trace, dict) else None
    disp = dict(gs_resolved) if isinstance(gs_resolved, dict) else dict(state or {})
    deduped_guidance_items, guidance_dedupe_meta = _dedupe_guidance_items_for_display(
        list(guidance_items or []),
        disp,
    )
    collapsed_guidance_items, collapse_meta = _collapse_to_single_primary_guidance_item(
        deduped_guidance_items,
        disp,
    )
    collapsed_guidance_items = _sanitize_guidance_items_for_executor_contract(
        collapsed_guidance_items,
        state=disp,
        debug_sink=debug_trace,
    )
    collapsed_guidance_items, _local_cleanup_meta = _maybe_promote_safe_local_cleanup_primary(
        collapsed_guidance_items,
        state=disp,
        overview=dict(debug_trace.get("overview") or {}),
        efficiency_state=dict(debug_trace.get("efficiency_tightening_state") or {}),
        mode_config=_design_mode_config(_design_optimisation_goal(disp)),
        debug_sink=debug_trace,
        source="compute_design_guidance_items",
    )
    collapsed_guidance_items = _prefer_target_band_guidance_item_order(
        collapsed_guidance_items,
        state=disp,
        mode_config=_design_mode_config(_design_optimisation_goal(disp)),
    )
    collapsed_guidance_items = _align_guidance_items_to_candidate_search_evidence(collapsed_guidance_items)
    collapsed_guidance_items = _design_guide_apply_copy_model_to_items(
        collapsed_guidance_items,
        state=disp,
        overview=dict(debug_trace.get("overview") or {}),
        efficiency_state=dict(debug_trace.get("efficiency_tightening_state") or {}),
    )
    debug_trace["guidance_dedupe_meta"] = dict(guidance_dedupe_meta)
    debug_trace["design_guide_single_primary_override"] = bool(collapse_meta.get("collapsed"))
    debug_trace["design_guide_single_primary_reason"] = collapse_meta.get("reason")
    debug_trace["design_guide_single_primary_subfamilies"] = list(collapse_meta.get("subfamilies") or [])
    debug_trace["design_guide_single_primary_covered_fail_keys"] = list(collapse_meta.get("covered_fail_keys") or [])
    debug_trace["design_guide_single_primary_remaining_fail_keys"] = list(collapse_meta.get("remaining_fail_keys") or [])
    recommendation_result = _recommendation_result_for_primary_guidance_card(
        collapsed_guidance_items,
        disp,
        branch=branch_hint,
        request_kind=request_kind_norm,
    )
    explicit_terminal_state = _design_guide_terminal_state_from_render_artifacts(
        collapsed_guidance_items,
        debug_trace,
    )
    derived_terminal_state = _derive_design_guide_terminal_state_from_current_overview(
        debug_trace,
        disp,
        collapsed_guidance_items,
    )
    terminal_state = explicit_terminal_state
    terminal_state_source = "explicit_render_artifact" if explicit_terminal_state else "none"
    if not terminal_state and derived_terminal_state:
        terminal_state = derived_terminal_state
        terminal_state_source = "derived_current_overview"
    terminal_meta = dict(debug_trace.get("_derived_terminal_state_meta") or {})
    debug_trace["design_guide_terminal_state"] = terminal_state
    debug_trace["design_guide_terminal_state_source"] = terminal_state_source
    debug_trace["design_guide_terminal_current_fail_keys"] = list(terminal_meta.get("current_fail_keys") or [])
    debug_trace["design_guide_terminal_current_governing_util"] = terminal_meta.get("current_governing_util")
    debug_trace["design_guide_terminal_target_band_lo"] = terminal_meta.get("target_band_lo")
    debug_trace["design_guide_terminal_target_band_hi"] = terminal_meta.get("target_band_hi")
    if terminal_state in {"optimal", "very_low_demand"}:
        recommendation_result = None
        if not str(debug_trace.get("guidance_branch") or "").strip():
            debug_trace["guidance_branch"] = terminal_state
    guidance_branch_norm = str(debug_trace.get("guidance_branch") or "").strip()
    if guidance_branch_norm in {"passing_guidance_fallback", "passing_guidance_blocked"}:
        if not recommendation_result:
            if guidance_branch_norm == "passing_guidance_blocked":
                debug_trace.setdefault("stop_reason", "cleanup_candidate_blocked")
                debug_trace.setdefault(
                    "user_visible_no_action_reason",
                    "Cleanup is advisory for the current all-pass state because no directly executable "
                    "tightening move under the resolved actions kept every governing check acceptable.",
                )
            else:
                debug_trace.setdefault("stop_reason", "no_actionable_cleanup_candidate")
                debug_trace.setdefault(
                    "user_visible_no_action_reason",
                    "Cleanup is advisory for the current all-pass state because the current move set did not "
                    "produce an actionable tightening candidate that preserved every governing check.",
                )
    if not recommendation_result and collapsed_guidance_items:
        primary_item = collapsed_guidance_items[0] if isinstance(collapsed_guidance_items[0], dict) else None
        overview_dbg = dict(debug_trace.get("overview") or {})
        statuses_dbg = dict(overview_dbg.get("statuses") or {})
        all_key_pass_dbg = bool(overview_dbg.get("all_key_pass"))
        worst_util_dbg = _parse_util_value(overview_dbg.get("worst_util"))
        action_type_dbg = str((primary_item or {}).get("action_type") or "").strip()
        contract_block_reason = str((primary_item or {}).get("executor_contract_blocked_reason") or "").strip()
        if (
            primary_item
            and not action_type_dbg
            and all_key_pass_dbg
            and worst_util_dbg is not None
            and float(worst_util_dbg) < float(EFFICIENCY_TARGET_UTIL_MIN)
            and all(str(v or "").upper() in {"PASS", "INFO", "NEAR LIMIT", "—", "-"} for v in statuses_dbg.values())
        ):
            debug_trace.setdefault("stop_reason", "no_actionable_cleanup_candidate")
            if contract_block_reason == "primary_efficiency_card_not_executor_backed":
                blocked_item = _guidance_item(
                    "general",
                    "Cleanup is advisory for this design state",
                    "Advisory reduction ideas need manual review before they can be applied.",

                    (
                        "The current all-pass state is below the target band, but the available "
                        "advisory reductions are not attached to an executor-backed one-click move."
                    ),
                    (
                        "Why: the guide avoided a one-click change because the candidate must be directly executable "
                        "and must keep every governing check acceptable."
                    ),
                    "Key levers: manual geometry, reinforcement, shear detailing review",
                    None,
                    None,
                    status="EFFICIENCY",
                    util=worst_util_dbg,
                )
                if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict):
                    collapsed_guidance_items[0] = blocked_item
                debug_trace.setdefault(
                    "user_visible_no_action_reason",
                    "Cleanup is advisory for the current all-pass state because the available reduction ideas "
                    "are not attached to an executor-backed local move.",
                )
            else:
                blocked_item = _guidance_item(
                    "general",
                    "Cleanup is advisory for this design state",
                    "No directly executable local reduction kept every governing check acceptable.",
                    (
                        "The current all-pass state remains below the target band, so manual cleanup "
                        "can still be reviewed against geometry, reinforcement, and detailing trade-offs."
                    ),
                    (
                        "Why: the solver avoided a one-click change because the available move set did not preserve "
                        "all governing checks while moving the design toward the target band."
                    ),
                    "Key levers: manual geometry, reinforcement, shear detailing review",
                    None,
                    None,
                    status="EFFICIENCY",
                    util=worst_util_dbg,
                )
                if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict):
                    collapsed_guidance_items[0] = blocked_item
                debug_trace.setdefault(
                    "user_visible_no_action_reason",
                    "Cleanup is advisory for the current all-pass state because the available move set did not "
                    "preserve every governing check while moving toward the target band.",
                )
    collapsed_guidance_items = _design_guide_apply_copy_model_to_items(
        collapsed_guidance_items,
        state=disp,
        overview=dict(debug_trace.get("overview") or {}),
        efficiency_state=dict(debug_trace.get("efficiency_tightening_state") or {}),
    )
    collapsed_guidance_items = _design_guide_apply_button_contracts_to_items(
        collapsed_guidance_items,
        state=disp,
    )
    collapsed_guidance_items = _design_guide_apply_display_truth_to_items(
        collapsed_guidance_items,
        state=disp,
        overview=dict(debug_trace.get("overview") or {}),
        mode_config=_design_mode_config(_design_optimisation_goal(disp)),
    )
    if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict):
        _overview_for_engine = dict(debug_trace.get("overview") or {})
        _mode_cfg_for_engine = _design_mode_config(_design_optimisation_goal(disp))
        _primary_for_engine = collapsed_guidance_items[0]
        _primary_truth_for_engine = dict(_primary_for_engine.get("display_truth") or {})
        _primary_button_for_engine = dict(_primary_for_engine.get("button_contract") or {})
        _primary_evidence_for_engine = dict(
            _primary_for_engine.get("candidate_search_evidence")
            or (_primary_for_engine.get("action_payload") or {}).get("candidate_search_evidence")
            or (_primary_for_engine.get("resolved_candidate") or {}).get("candidate_search_evidence")
            or {}
        )
        try:
            _engine_decision_for_compute = resolve_design_guide_decision(
                current_state=dict(disp),
                summary=dict(_overview_for_engine),
                raw_items=list(collapsed_guidance_items),
                candidate_evidence=dict(_primary_evidence_for_engine),
                # Transitional candidate preparation only. Final Design Guide decision,
                # target-band winner selection, and outside-target allowance are owned by
                # design_guidance_engine.resolve_design_guide_decision.
                raw_candidates=list(collapsed_guidance_items),
                target_band=target_band_payload(_design_optimisation_goal(disp)),
                context={
                    "goal": _design_optimisation_goal(disp),
                    "headline": str(_primary_for_engine.get("title_main") or "Design guidance"),
                    "primary_item_has_actionable_updates": bool(
                        _recommendation_updates_for_envelope(_primary_for_engine)
                    ),
                    "worst": _parse_util_value(_overview_for_engine.get("worst_util")),
                    "any_fail": bool(_overview_for_engine.get("any_fail")),
                    "any_warn": bool(_overview_for_engine.get("any_warn")),
                    "all_key_pass": bool(_overview_for_engine.get("all_key_pass")),
                    "overdesigned": bool(
                        is_unnecessarily_overdesigned(
                            _overview_for_engine,
                            dict(debug_trace.get("efficiency_tightening_state") or {}),
                        )
                    ),
                    "in_target_band": bool(
                        _is_in_target_zone_with_eps(
                            _overview_for_engine,
                            _mode_cfg_for_engine,
                            eps=TARGET_BAND_EPS,
                        )
                    ),
                    "guidance_intent": str(_primary_for_engine.get("guidance_intent") or "").strip(),
                    "candidate_search_evidence": dict(
                        _primary_evidence_for_engine
                        or debug_trace.get("local_cleanup_candidate_search_evidence")
                        or {}
                    ),
                    "local_cleanup_candidate_search_evidence": dict(
                        debug_trace.get("local_cleanup_candidate_search_evidence")
                        or _primary_evidence_for_engine
                        or {}
                    ),
                    "local_cleanup_search_exhaustive": debug_trace.get("local_cleanup_search_exhaustive"),
                    "unsupported_cleanup_families": list(debug_trace.get("unsupported_cleanup_families") or []),
                    "local_cleanup_blocked_reasons_by_family": dict(debug_trace.get("local_cleanup_blocked_reasons_by_family") or {}),
                    "efficiency_state": dict(debug_trace.get("efficiency_tightening_state") or {}),
                },
            )
        except Exception:
            _engine_decision_for_compute = {}
        _terminal_primary_for_compute = legacy_item_from_decision(
            _primary_for_engine,
            _engine_decision_for_compute,
        )
        if (
            isinstance(_terminal_primary_for_compute, dict)
            and str(_terminal_primary_for_compute.get("guidance_intent") or "") == "already_efficient"
        ):
            collapsed_guidance_items[0] = _terminal_primary_for_compute
            debug_trace["design_guide_engine_decision"] = dict(_engine_decision_for_compute)
    if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict):
        primary_item_for_evidence = collapsed_guidance_items[0]
        existing_evidence = dict(
            primary_item_for_evidence.get("candidate_search_evidence")
            or (primary_item_for_evidence.get("action_payload") or {}).get("candidate_search_evidence")
            or (primary_item_for_evidence.get("resolved_candidate") or {}).get("candidate_search_evidence")
            or {}
        )
        if not existing_evidence:
            mode_cfg_evidence = _design_mode_config(_design_optimisation_goal(disp))
            t_lo_evidence, t_hi_evidence, _ = _resolved_efficiency_target_band(
                mode_cfg_evidence,
                goal=_design_optimisation_goal(disp),
            )
            evidence_candidates: list[dict] = []
            for idx, item in enumerate(collapsed_guidance_items, start=1):
                if not isinstance(item, dict):
                    continue
                contract = dict(item.get("button_contract") or {})
                truth = dict(item.get("display_truth") or {})
                updates = dict(contract.get("updates") or _resolve_recommendation_updates(item, disp) or {})
                preview_util = (
                    contract.get("expected_util")
                    if contract.get("expected_util") is not None
                    else truth.get("source_candidate_util", truth.get("displayed_util"))
                )
                evidence_candidates.append(
                    {
                        "candidate_id": _guidance_item_source_candidate_id(item) or f"displayed_candidate_{idx:03d}",
                        "label": item.get("title_main") or f"Displayed candidate {idx}",
                        "updates": dict(updates),
                        "candidate_post_util": preview_util,
                        "worst_util": preview_util,
                        "is_compliant": bool(contract.get("preview_pass") and contract.get("blocking_reason") in (None, "")),
                        "overview": {},
                    }
                )
            selected_for_evidence = evidence_candidates[0] if evidence_candidates else None
            existing_evidence = _build_candidate_search_evidence(
                selected_candidate=selected_for_evidence,
                all_candidates=evidence_candidates,
                target_low=float(t_lo_evidence),
                target_high=float(t_hi_evidence),
                exhaustive=True,
                search_scope="final_displayed_design_guide_candidates",
                selected_title=str(primary_item_for_evidence.get("title_main") or ""),
            )
        primary_item_for_evidence["candidate_search_evidence"] = dict(existing_evidence)
        primary_item_for_evidence["candidate_id"] = existing_evidence.get("selected_candidate_id")
        primary_item_for_evidence["source_candidate_id"] = existing_evidence.get("selected_candidate_id")
        _evidence_payload = dict(primary_item_for_evidence.get("action_payload") or {})
        _evidence_payload["candidate_search_evidence"] = dict(existing_evidence)
        _evidence_payload["source_candidate_id"] = existing_evidence.get("selected_candidate_id")
        primary_item_for_evidence["action_payload"] = _evidence_payload
        _evidence_resolved = dict(primary_item_for_evidence.get("resolved_candidate") or {})
        _evidence_resolved["candidate_search_evidence"] = dict(existing_evidence)
        _evidence_resolved["candidate_id"] = existing_evidence.get("selected_candidate_id")
        _evidence_resolved["source_candidate_id"] = existing_evidence.get("selected_candidate_id")
        primary_item_for_evidence["resolved_candidate"] = _evidence_resolved
        _evidence_contract = dict(primary_item_for_evidence.get("button_contract") or {})
        if _evidence_contract:
            _evidence_contract["source_candidate_id"] = existing_evidence.get("selected_candidate_id")
            primary_item_for_evidence["button_contract"] = _evidence_contract
        debug_trace["candidate_search_evidence"] = dict(existing_evidence)
    debug_trace["guidance_intent_items"] = _design_guide_guidance_intent_debug_rows(collapsed_guidance_items)
    debug_trace["displayed_guidance_intent_items"] = list(debug_trace["guidance_intent_items"])
    debug_trace["primary_guidance_intent"] = (
        str((collapsed_guidance_items[0] or {}).get("guidance_intent") or "").strip()
        if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict)
        else None
    )
    debug_trace["primary_button_contract"] = (
        dict((collapsed_guidance_items[0] or {}).get("button_contract") or {})
        if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict)
        else {}
    )
    debug_trace["primary_display_truth"] = (
        dict((collapsed_guidance_items[0] or {}).get("display_truth") or {})
        if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict)
        else {}
    )
    out: dict = {
        "guidance_items": list(collapsed_guidance_items or []),
        "debug_trace": dict(debug_trace),
        "cache_data": {
            "guidance_cache_fp": _candidate_cache_key(dict(state or {})),
        },
        "recommendation_result": recommendation_result,
    }
    if request_kind_norm == "auto_design":
        out["auto_design_solver_recommendation"] = auto_design_solver_recommendation
        out["auto_design_seed_failed"] = bool(auto_design_seed_failed)
    set_rerun_pure_cache("compute_design_guidance_items", guidance_runtime_fp, out)
    return out
