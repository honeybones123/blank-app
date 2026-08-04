"""One-click auto-design coordinators for the Inputs page.

This module preserves the old Inputs page one-click solver behaviour behind an
extracted coordinator boundary. The solver still delegates to the existing
legacy helper and Design Brain surfaces supplied by the compatibility shim.
"""

from __future__ import annotations

import copy
import math
import sys

from typing import Any

from inputs_application.legacy_design_brain_adapter import (
    build_target_band_fallback_scored_candidate as _build_target_band_fallback_scored_candidate,
    resolve_target_band_candidate_sort_key as _resolve_target_band_candidate_sort_key,
    select_target_band_ranked_candidate as _select_target_band_ranked_candidate,
)
from application.target_band_selection_policy import (
    resolve_target_band_selected_candidate_acceptance as _resolve_target_band_selected_candidate_acceptance,
)
from inputs_page_modules.design_guide.candidate_family_classification import (
    _candidate_family_matches_governing_domain,
)


_LEGACY_AUTO_DESIGN_NAMES: tuple[str, ...] = (
    'AUTO_DESIGN_REQUEST_SOURCE_KEY',
    'BEAM_STATUS_FAIL',
    'EFFICIENCY_TARGET_UTIL_MAX',
    'EFFICIENCY_TARGET_UTIL_MIN',
    'GUIDANCE_SHEAR_UTIL_NEGLIGIBLE',
    'RESCUE_SEED_LIBRARY',
    'SHARED_DEFAULTS',
    '_COMPOUND_SHEAR_UPDATE_KEYS',
    '_DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS',
    '_agent_debug_log',
    '_append_design_guide_trace',
    '_auto_design_invoke_debug_snapshot',
    '_build_canonical_design_state_pack',
    '_build_design_actions_context',
    '_build_recommendation_envelope',
    '_candidate_failure_coverage_summary',
    '_candidate_in_target_band',
    '_candidate_is_valid_primary_one_click',
    '_candidate_objective_util',
    '_candidate_state_signature',
    '_candidate_target_band_distance',
    '_candidate_target_domains_for_band',
    '_canonical_pack_is_valid',
    '_clear_auto_design_runtime_latches',
    '_coherence_debug_fields',
    '_collect_design_overview',
    '_compute_design_guidance_items',
    '_consume_auto_design_invoke_after_solver_entry_confirmed',
    '_current_design_guide_fail_fingerprint',
    '_design_guide_candidate_family',
    '_design_guide_trace_compare_meta',
    '_design_guide_tracer_path',
    '_design_mode_config',
    '_design_optimisation_goal',
    '_design_state_coherence_check',
    '_evaluate_auto_design_candidate',
    '_evaluate_shear_with_state',
    '_float_from_state',
    '_generate_tightening_candidates_for_governing_domain',
    '_governing_focus_from_overview',
    '_guidance_state_snapshot',
    '_int_from_state',
    '_invalidate_design_guide_caches',
    '_local_cleanup_acceptance_fingerprint',
    '_new_design_guide_trace_run_id',
    '_normalise_invalid_shear_state_updates',
    '_one_click_attach_eval_target_domains',
    '_one_click_best_next_hop_improving_candidate',
    '_one_click_budget_stop_has_better_next_hop',
    '_one_click_build_user_visible_no_action_fields',
    '_one_click_candidate_is_shear_governing_for_prune',
    '_one_click_collect_actionable_guidance_candidates',
    '_one_click_commit_audit_passes',
    '_one_click_committable_candidate_eval',
    '_one_click_diff_accumulated_updates',
    '_one_click_directional_tie_key',
    '_one_click_domain_max_distance',
    '_one_click_domain_needs_cleanup',
    '_one_click_domain_total_distance',
    '_one_click_exhaustion_next_hop_allowed',
    '_one_click_has_unresolved_spacing_envelope_fail',
    '_one_click_in_band_shear_cleanup_candidate_allowed',
    '_one_click_in_band_shear_cleanup_deferral',
    '_one_click_mixed_direction_classification',
    '_one_click_mixed_direction_rank_adjustment',
    '_one_click_post_commit_audit',
    '_one_click_required_domain_progress',
    '_one_click_required_domains_satisfied',
    '_one_click_seed_target_domains_from_eval',
    '_one_click_step_improves',
    '_one_click_still_materially_under_target',
    '_one_click_strict_target_band_ok',
    '_one_click_target_domains_for_eval',
    '_one_click_tightening_mode_active',
    '_one_click_trace_eval_domain_payload',
    '_one_click_update_direction_summary',
    '_overlay_current_normalized_shear_truth',
    '_parse_util_value',
    '_pop_inputs_widget_keys_for_shared_updates',
    '_record_one_click_shear_publish_audit',
    '_requires_full_coverage_for_primary_one_click',
    '_rescue_bootstrap_partial_commit_allowed',
    '_rescue_mode_default_debug',
    '_rescue_mode_eval_for_result',
    '_rescue_mode_path_improved',
    '_rescue_mode_seed_order',
    '_rescue_mode_should_enter',
    '_rescue_mode_validate_seed',
    '_restore_shared_state_snapshot',
    '_sanitize_shared_update_bundle',
    '_set_design_guide_live_breadcrumb',
    '_set_one_click_run_feedback',
    '_set_shared_updates',
    '_shared_state_snapshot',
    '_shear_demands_negligible',
    '_shear_preview_for_updates',
    '_should_run_auto_design',
    '_stage3_final_published_shear_truth_bundle',
    '_stage3_remaining_issue_class_from_overview_state',
    '_trace_compact_overview_dict',
    '_trace_compact_shared_geom_reo',
    '_tracer_one_click_action_source_summary',
    '_updates_match_state',
    'compute_efficiency_tightening_state',
    'evaluate_candidate_full',
    'finalize_auto_design_publish',
    'is_valid_progress_while_failing',
    'persist_active_beam_from_shared',
    'publish_normalized_final_shear_truth_to_session',
)


def _bind_legacy_auto_design_globals(
    *,
    legacy_page: Any,
    st_module: Any,
    sys_module: Any,
) -> None:
    namespace = globals()
    namespace["st"] = st_module
    namespace["sys"] = sys_module
    namespace["copy"] = getattr(legacy_page, "copy")
    namespace["math"] = getattr(legacy_page, "math")
    for name in _LEGACY_AUTO_DESIGN_NAMES:
        namespace[name] = getattr(legacy_page, name)


def solve_one_click_to_target_coordinator(
    legacy_page: Any,
    st_module: Any,
    sys_module: Any,
    state: dict,
    *,
    max_steps: int = 6,
    debug_enabled: bool = False,
    trace_run_id: str | None = None,
    trace_source: str = "one_click_solve",
    _rescue_enabled: bool = True,
    _rescue_attempted_seed_keys: tuple[str, ...] = (),
) -> dict:
    _bind_legacy_auto_design_globals(
        legacy_page=legacy_page,
        st_module=st_module,
        sys_module=sys_module,
    )
    return _solve_one_click_to_target(
        state,
        max_steps=max_steps,
        debug_enabled=debug_enabled,
        trace_run_id=trace_run_id,
        trace_source=trace_source,
        _rescue_enabled=_rescue_enabled,
        _rescue_attempted_seed_keys=_rescue_attempted_seed_keys,
    )


def run_one_click_auto_design_coordinator(
    legacy_page: Any,
    st_module: Any,
    sys_module: Any,
    *,
    trigger_fingerprint: tuple | None = None,
    entry_source: str = "inputs_handle_auto_design",
) -> dict:
    _bind_legacy_auto_design_globals(
        legacy_page=legacy_page,
        st_module=st_module,
        sys_module=sys_module,
    )
    return run_one_click_auto_design(
        trigger_fingerprint=trigger_fingerprint,
        entry_source=entry_source,
    )


def _append_one_click_solver_trace_coordinator(
    *,
    rid: str | None,
    stop_traced: list[bool],
    ev: str,
    dat: dict,
    trace_source: str,
) -> None:
    if rid:
        if ev == "stop":
            stop_traced[0] = True
        _append_design_guide_trace(ev, dat, run_id=rid, source=trace_source)


def _build_one_click_solver_trace_callback_coordinator(
    *,
    rid: str | None,
    stop_traced: list[bool],
    trace_source: str,
):
    def _trace_callback(ev: str, dat: dict) -> None:
        return _append_one_click_solver_trace_coordinator(
            rid=rid,
            stop_traced=stop_traced,
            ev=ev,
            dat=dat,
            trace_source=trace_source,
        )

    return _trace_callback


def _start_one_click_auto_design_run_entry_coordinator(
    *,
    trigger_fingerprint: tuple | None,
    entry_source: str,
) -> dict:
    _set_design_guide_live_breadcrumb("DG TRACE ENTRY")
    trace_run_id = _new_design_guide_trace_run_id()
    tracer_path = _design_guide_tracer_path()
    trace_src = "run_one_click_auto_design"
    entry_source_norm = str(entry_source or "inputs_handle_auto_design").strip() or "inputs_handle_auto_design"
    latch_owner = str(st.session_state.get("auto_design_latch_owner") or "").strip() or None
    try:
        _dg_should = bool(_should_run_auto_design())
        _dg_solver_running = bool(st.session_state.get("_solver_running"))
        _dg_compute_ip = bool(st.session_state.get("_compute_in_progress"))
    except Exception as _dg_e:
        _dg_should = f"<err:{_dg_e!r}>"
        _dg_solver_running = f"<err:{_dg_e!r}>"
        _dg_compute_ip = f"<err:{_dg_e!r}>"
    print(
        "DG TRACE ENTRY\n"
        f"trace_run_id={trace_run_id}\n"
        f"tracer_path={tracer_path}\n"
        f"_should_run_auto_design()={_dg_should}\n"
        f"_solver_running={_dg_solver_running}\n"
        f"_compute_in_progress={_dg_compute_ip}\n",
        file=sys.stderr,
        end="",
        flush=True,
    )

    _append_design_guide_trace(
        "trace_ping",
        {"tracer_path": tracer_path, "phase": "entry"},
        run_id=trace_run_id,
        source=trace_src,
    )

    _agent_debug_log(
        "Canonical one-click auto-design entrypoint invoked (run_one_click_auto_design)",
        {
            "trigger_fingerprint": None
            if trigger_fingerprint is None
            else str(trigger_fingerprint),
            "trace_run_id": trace_run_id,
            "design_guide_tracer_path": tracer_path,
            "run_one_click_entry_source": entry_source_norm,
            "auto_design_latch_owner": latch_owner,
        },
        location="inputs_page.py:run_one_click_auto_design",
        hypothesis_id="H_AUTO_DESIGN_PUBLIC",
    )
    return {
        "trace_run_id": trace_run_id,
        "tracer_path": tracer_path,
        "trace_src": trace_src,
        "entry_source_norm": entry_source_norm,
        "latch_owner": latch_owner,
    }


def _build_initial_blocked_solver_return_coordinator(
    *,
    initial_snapshot: dict,
    initial_coherence: dict,
    initial_pack_valid: bool,
    initial_stop_reason: str,
    rid: str | None,
    trace_callback,
) -> dict:
    trace_callback(
        "stop",
        {
            "stop_reason": initial_stop_reason,
            "status": "blocked",
            **_coherence_debug_fields(initial_coherence),
            "canonical_pack_valid": initial_pack_valid,
            "canonical_pack_error": initial_snapshot.get("canonical_pack_error"),
            "canonical_pack_error_stage": initial_snapshot.get("canonical_pack_error_stage"),
        },
    )
    dbg_blocked = {
        "iteration_count": 0,
        "initial_worst_util": None,
        "final_worst_util": None,
        "target_band": {},
        "stop_reason": initial_stop_reason,
        "reached_target_band": False,
        "step_candidate_labels": [],
        "all_key_pass": False,
        "trace_run_id": rid,
        **_coherence_debug_fields(initial_coherence),
        "canonical_pack_built": bool(initial_snapshot.get("canonical_pack_built")),
        "canonical_pack_valid": initial_pack_valid,
        "canonical_pack_source": initial_snapshot.get("canonical_pack_source"),
        "canonical_pack_error": initial_snapshot.get("canonical_pack_error"),
        "canonical_pack_error_stage": initial_snapshot.get("canonical_pack_error_stage"),
        "solver_blocked_by_incoherent_state": True,
    }
    return {
        "status": "blocked",
        "stop_reason": initial_stop_reason,
        "blocked_state_class": "hard_invalid",
        "step_count": 0,
        "initial_worst_util": None,
        "final_worst_util": None,
        "reached_target_band": False,
        "all_key_pass": False,
        "final_updates": {},
        "final_state_preview": copy.deepcopy(initial_snapshot),
        "step_trace": [],
        "winning_label": None,
        "winning_action_type": None,
        "one_click_solver_debug": dbg_blocked,
        "trace_run_id": rid,
    }


def _build_evaluate_failed_solver_return_coordinator(
    *,
    working: dict,
    t_lo: float,
    t_hi: float,
    rid: str | None,
    trace_callback,
) -> dict:
    dbg = {
        "iteration_count": 0,
        "initial_worst_util": None,
        "final_worst_util": None,
        "target_band": {"min": t_lo, "max": t_hi},
        "stop_reason": "evaluate_failed",
        "reached_target_band": False,
        "step_candidate_labels": [],
        "all_key_pass": False,
        "trace_run_id": rid,
    }
    trace_callback(
        "stop",
        {
            "stop_reason": "evaluate_failed",
            "step_count": 0,
            "status": "failed",
            "final_preview_util": None,
            "reached_target_band": False,
            "all_key_pass": False,
            "winning_label": None,
            "winning_action_type": None,
            "final_updates": {},
        },
    )
    return {
        "status": "failed",
        "stop_reason": "evaluate_failed",
        "step_count": 0,
        "initial_worst_util": None,
        "final_worst_util": None,
        "reached_target_band": False,
        "all_key_pass": False,
        "final_updates": {},
        "final_state_preview": copy.deepcopy(working),
        "step_trace": [],
        "winning_label": None,
        "winning_action_type": None,
        "one_click_solver_debug": dbg,
        "trace_run_id": rid,
    }


def _build_already_in_band_solver_return_coordinator(
    *,
    working: dict,
    init_worst: float,
    t_lo: float,
    t_hi: float,
    rid: str | None,
    early_in_band_exit_blocked_for_tightening: bool,
    early_in_band_exit_tightening_classification: str,
    early_in_band_exit_available_tightening_paths: list[str],
    early_in_band_exit_reason: str,
    trace_callback,
) -> dict:
    dbg = {
        "iteration_count": 0,
        "initial_worst_util": init_worst,
        "final_worst_util": init_worst,
        "target_band": {"min": t_lo, "max": t_hi},
        "stop_reason": "already_in_band",
        "reached_target_band": True,
        "step_candidate_labels": [],
        "all_key_pass": True,
        "trace_run_id": rid,
        "early_in_band_exit_blocked_for_tightening": bool(early_in_band_exit_blocked_for_tightening),
        "early_in_band_exit_tightening_classification": early_in_band_exit_tightening_classification,
        "early_in_band_exit_available_tightening_paths": list(early_in_band_exit_available_tightening_paths),
        "early_in_band_exit_reason": early_in_band_exit_reason,
        "early_in_band_shear_cleanup_deferred": False,
        "early_in_band_shear_cleanup_label": None,
        "shear_remove_links_candidate_seen": False,
        "shear_remove_links_candidate_truth_ok": False,
        "shear_remove_links_candidate_dropped_reason": "solver_exited_already_in_band",
        "shear_remove_links_candidate_materiality": "not_evaluated",
        "final_no_links_candidate_committed": False,
    }
    trace_callback(
        "stop",
        {
            "stop_reason": "already_in_band",
            "step_count": 0,
            "status": "no_action",
            "final_preview_util": init_worst,
            "reached_target_band": True,
            "all_key_pass": True,
            "winning_label": None,
            "winning_action_type": None,
            "final_updates": {},
            "early_in_band_exit_blocked_for_tightening": bool(early_in_band_exit_blocked_for_tightening),
            "early_in_band_exit_tightening_classification": early_in_band_exit_tightening_classification,
            "early_in_band_exit_available_tightening_paths": list(early_in_band_exit_available_tightening_paths),
            "early_in_band_exit_reason": early_in_band_exit_reason,
            "early_in_band_shear_cleanup_deferred": False,
            "early_in_band_shear_cleanup_label": None,
        },
    )
    return {
        "status": "no_action",
        "stop_reason": "already_in_band",
        "step_count": 0,
        "initial_worst_util": init_worst,
        "final_worst_util": init_worst,
        "reached_target_band": True,
        "all_key_pass": True,
        "final_updates": {},
        "final_state_preview": copy.deepcopy(working),
        "step_trace": [],
        "winning_label": None,
        "winning_action_type": None,
        "one_click_solver_debug": dbg,
        "trace_run_id": rid,
    }


def _trace_evaluate_failed_working_solver_stop_coordinator(
    *,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    trace_callback,
) -> tuple[str, str]:
    stop_reason = "evaluate_failed_working"
    status = "failed"
    trace_callback(
        "stop",
        {
            "stop_reason": stop_reason,
            "step_count": len(step_trace),
            "status": status,
            "final_preview_util": None,
            "reached_target_band": False,
            "all_key_pass": False,
            "winning_label": winning_label,
            "winning_action_type": winning_action_type,
            "final_updates": _one_click_diff_accumulated_updates(initial_snapshot, working),
        },
    )
    return stop_reason, status


def _trace_evaluate_failed_after_apply_solver_stop_coordinator(
    *,
    step_base: dict,
    step_trace: list[dict],
    initial_snapshot: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    trace_callback,
) -> tuple[dict, str, str]:
    working = step_base
    stop_reason = "evaluate_failed_after_apply"
    status = "failed"
    trace_callback(
        "stop",
        {
            "stop_reason": stop_reason,
            "step_count": len(step_trace),
            "status": status,
            "final_preview_util": None,
            "reached_target_band": False,
            "all_key_pass": False,
            "winning_label": winning_label,
            "winning_action_type": winning_action_type,
            "final_updates": _one_click_diff_accumulated_updates(initial_snapshot, working),
        },
    )
    return working, stop_reason, status


def _trace_current_reached_target_band_solver_stop_coordinator(
    *,
    cur_eval: dict,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    trace_callback,
) -> tuple[str, str]:
    stop_reason = "reached_target_band"
    status = "solved"
    trace_callback(
        "stop",
        {
            "stop_reason": stop_reason,
            "step_count": len(step_trace),
            "status": status,
            "final_preview_util": float((cur_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "reached_target_band": True,
            "all_key_pass": True,
            "winning_label": winning_label,
            "winning_action_type": winning_action_type,
            "final_updates": _one_click_diff_accumulated_updates(initial_snapshot, working),
        },
    )
    return stop_reason, status


def _trace_tightening_depth_budget_solver_stop_coordinator(
    *,
    cur_eval: dict,
    mode_config: dict,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    cur_ib: bool,
    cur_pass: bool,
    winning_label: str | None,
    winning_action_type: str | None,
    tightening_step_count: int,
    max_tightening_steps: int,
    candidate_family_depth_reached: str,
    trace_callback,
) -> tuple[str, str, float | None]:
    stop_reason = "tightening_depth_budget_reached"
    status = "exhausted"
    final_distance_to_band = _candidate_target_band_distance(cur_eval, mode_config)
    trace_callback(
        "stop",
        {
            "stop_reason": stop_reason,
            "step_count": len(step_trace),
            "status": status,
            "final_preview_util": float((cur_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "reached_target_band": bool(cur_ib and cur_pass),
            "all_key_pass": bool(cur_pass),
            "winning_label": winning_label,
            "winning_action_type": winning_action_type,
            "final_updates": _one_click_diff_accumulated_updates(initial_snapshot, working),
            "tightening_step_count": int(tightening_step_count),
            "tightening_depth_budget": int(max_tightening_steps),
            "still_materially_under_target": bool(
                _one_click_still_materially_under_target(cur_eval, mode_config, margin=0.03)
            ),
            "no_actionable_after_full_tightening_search": False,
            "candidate_family_depth_reached": candidate_family_depth_reached,
            "final_distance_to_band": final_distance_to_band,
        },
    )
    return stop_reason, status, final_distance_to_band


def _trace_no_actionable_candidates_solver_stop_coordinator(
    *,
    cur_eval: dict,
    mode_config: dict,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    governing_domain: str,
    tightening_mode_active: bool,
    rejected_as_non_material_improvement: int,
    no_actionable_after_full_tightening_search: bool,
    cur_ib: bool,
    cur_pass: bool,
    winning_label: str | None,
    winning_action_type: str | None,
    tightening_step_count: int,
    max_tightening_steps: int,
    candidate_family_depth_reached: str,
    trace_callback,
) -> tuple[str, str, float | None, bool]:
    still_under = bool(_one_click_still_materially_under_target(cur_eval, mode_config, margin=0.03))
    unresolved_spacing_fail = bool(
        governing_domain == "shear"
        and _one_click_has_unresolved_spacing_envelope_fail(cur_eval)
    )
    if unresolved_spacing_fail:
        stop_reason = "minimum_shear_detailing_limit"
    elif tightening_mode_active and still_under:
        no_actionable_after_full_tightening_search = True
        if rejected_as_non_material_improvement > 0:
            stop_reason = "non_material_remaining_candidates"
        else:
            stop_reason = "no_actionable_candidates_after_full_tightening_search"
    else:
        stop_reason = "no_actionable_candidates"
    status = "exhausted"
    final_distance_to_band = _candidate_target_band_distance(cur_eval, mode_config)
    trace_callback(
        "stop",
        {
            "stop_reason": stop_reason,
            "step_count": len(step_trace),
            "status": status,
            "final_preview_util": float((cur_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "reached_target_band": bool(cur_ib and cur_pass),
            "all_key_pass": bool(cur_pass),
            "winning_label": winning_label,
            "winning_action_type": winning_action_type,
            "final_updates": _one_click_diff_accumulated_updates(initial_snapshot, working),
            "tightening_step_count": int(tightening_step_count),
            "tightening_depth_budget": int(max_tightening_steps),
            "still_materially_under_target": still_under,
            "no_actionable_after_full_tightening_search": bool(no_actionable_after_full_tightening_search),
            "candidate_family_depth_reached": candidate_family_depth_reached,
            "final_distance_to_band": final_distance_to_band,
            "unresolved_spacing_envelope_fail": unresolved_spacing_fail,
        },
    )
    return stop_reason, status, final_distance_to_band, no_actionable_after_full_tightening_search


def _trace_rejected_best_candidate_solver_stop_coordinator(
    *,
    selected_candidate_acceptance: dict,
    best: dict,
    mode_config: dict,
    step_idx: int,
    cur_eval: dict,
    cur_pass: bool,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: str,
    best_distance_to_band_this_iteration,
    in_band_shear_cleanup_deferral: dict,
    trace_callback,
) -> tuple[str, str]:
    stop_reason = str(selected_candidate_acceptance.get("stop_reason") or "no_improving_candidate")
    status = "exhausted"
    trace_callback(
        "iteration_winner",
        {
            **_one_click_trace_eval_domain_payload(best["eval"], mode_config),
            "step": step_idx,
            "chosen_label": best.get("label"),
            "chosen_action_type": best.get("action_type"),
            "chosen_updates": dict(best.get("updates") or {}),
            "chosen_preview_util": best.get("worst_util"),
            "chosen_statuses": dict((best["eval"].get("overview") or {}).get("statuses") or {}),
            "reaches_target_band": bool(_candidate_in_target_band(best["eval"], mode_config)),
            "reason_selected": "rank_lexicographic_then_no_improvement_exit",
            "accepted": False,
            "in_band_shear_cleanup_deferred": bool(in_band_shear_cleanup_deferral.get("active")),
        },
    )
    trace_callback(
        "stop",
        {
            "stop_reason": stop_reason,
            "step_count": len(step_trace),
            "status": status,
            "final_preview_util": float((cur_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "reached_target_band": False,
            "all_key_pass": bool(cur_pass),
            "winning_label": winning_label,
            "winning_action_type": winning_action_type,
            "final_updates": _one_click_diff_accumulated_updates(initial_snapshot, working),
            "tightening_step_count": int(tightening_step_count),
            "tightening_depth_budget": int(max_tightening_steps),
            "still_materially_under_target": bool(
                _one_click_still_materially_under_target(cur_eval, mode_config, margin=0.03)
            ),
            "no_actionable_after_full_tightening_search": bool(no_actionable_after_full_tightening_search),
            "candidate_family_depth_reached": candidate_family_depth_reached,
            "best_distance_to_band_this_iteration": float(best_distance_to_band_this_iteration),
        },
    )
    return stop_reason, status


def _trace_accepted_best_candidate_solver_iteration_coordinator(
    *,
    best: dict,
    mode_config: dict,
    step_idx: int,
    tightening_step_count: int,
    max_tightening_steps: int,
    candidate_family_depth_reached: str,
    best_distance_to_band_this_iteration,
    trace_callback,
) -> None:
    trace_callback(
        "iteration_winner",
        {
            **_one_click_trace_eval_domain_payload(best["eval"], mode_config),
            "step": step_idx,
            "chosen_label": best.get("label"),
            "chosen_action_type": best.get("action_type"),
            "chosen_updates": dict(best.get("updates") or {}),
            "chosen_preview_util": best.get("worst_util"),
            "chosen_statuses": dict((best["eval"].get("overview") or {}).get("statuses") or {}),
            "reaches_target_band": bool(_candidate_in_target_band(best["eval"], mode_config)),
            "reason_selected": "rank_lexicographic_min_tuple_one_click_step_improves_true",
            "accepted": True,
            "tightening_step_count": int(tightening_step_count),
            "tightening_depth_budget": int(max_tightening_steps),
            "candidate_family_depth_reached": candidate_family_depth_reached,
            "best_distance_to_band_this_iteration": float(best_distance_to_band_this_iteration),
        },
    )


def _trace_post_step_reached_target_band_solver_stop_coordinator(
    *,
    w_gate_eval: dict,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: str,
    final_distance_to_band,
    trace_callback,
) -> tuple[str, str]:
    stop_reason = "reached_target_band"
    status = "solved"
    trace_callback(
        "stop",
        {
            "stop_reason": stop_reason,
            "step_count": len(step_trace),
            "status": status,
            "final_preview_util": float((w_gate_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "reached_target_band": True,
            "all_key_pass": True,
            "winning_label": winning_label,
            "winning_action_type": winning_action_type,
            "final_updates": _one_click_diff_accumulated_updates(initial_snapshot, working),
            "tightening_step_count": int(tightening_step_count),
            "tightening_depth_budget": int(max_tightening_steps),
            "continuing_tightening_after_step": False,
            "still_materially_under_target": False,
            "no_actionable_after_full_tightening_search": bool(no_actionable_after_full_tightening_search),
            "candidate_family_depth_reached": candidate_family_depth_reached,
            "final_distance_to_band": final_distance_to_band,
        },
    )
    return stop_reason, status


def _trace_post_step_solver_iteration_coordinator(
    *,
    w_gate_eval: dict,
    mode_config: dict,
    step_idx: int,
    winning_label: str | None,
    winning_action_type: str | None,
    tightening_step_count: int,
    max_tightening_steps: int,
    continuing_tightening_after_step: bool,
    still_under_after_step: bool,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: str,
    best_distance_to_band_this_iteration,
    final_distance_to_band,
    unresolved_spacing_fail_after_step: bool,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list[str],
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: int,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    final_resolved_shear_util,
    final_resolved_web_util,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    trace_callback,
) -> None:
    trace_callback(
        "iteration_winner",
        {
            **_one_click_trace_eval_domain_payload(w_gate_eval, mode_config),
            "step": step_idx,
            "chosen_label": winning_label,
            "chosen_action_type": winning_action_type,
            "tightening_step_count": int(tightening_step_count),
            "tightening_depth_budget": int(max_tightening_steps),
            "continuing_tightening_after_step": continuing_tightening_after_step,
            "still_materially_under_target": still_under_after_step,
            "no_actionable_after_full_tightening_search": bool(no_actionable_after_full_tightening_search),
            "candidate_family_depth_reached": candidate_family_depth_reached,
            "best_distance_to_band_this_iteration": float(best_distance_to_band_this_iteration),
            "final_distance_to_band": final_distance_to_band,
            "unresolved_spacing_envelope_fail": unresolved_spacing_fail_after_step,
            "shear_governing_mode_active": bool(shear_governing_mode_active),
            "shear_severity_band": shear_severity_band,
            "shear_candidate_family_order": list(shear_candidate_family_order),
            "spacing_candidates_considered": int(spacing_candidates_considered),
            "leg_candidates_considered": int(leg_candidates_considered),
            "dia_candidates_considered": int(dia_candidates_considered),
            "geometry_candidates_considered_for_shear": int(geometry_candidates_considered_for_shear),
            "combined_candidates_considered_for_shear": int(combined_candidates_considered_for_shear),
            "web_crushing_penalty_applied": int(web_crushing_penalty_applied),
            "rejected_as_spacing_too_weak": int(rejected_as_spacing_too_weak),
            "rejected_as_web_crushing_marginal": int(rejected_as_web_crushing_marginal),
            "rejected_as_impractical_shear_layout": int(rejected_as_impractical_shear_layout),
            "final_resolved_shear_util": final_resolved_shear_util,
            "final_resolved_web_util": final_resolved_web_util,
            "shear_governing_family_detected": bool(shear_governing_family_detected),
            "governing_family_exists_after_domain_fix": bool(governing_family_exists_after_domain_fix),
            "pruned_non_shear_family_count": int(pruned_non_shear_family_count),
            "accepted": True,
            "reason_selected": "post_apply_tightening_continuation_check",
        },
    )


def _trace_repeated_state_solver_stop_coordinator(
    *,
    step_base: dict,
    w_eval: dict | None,
    step_trace: list[dict],
    initial_snapshot: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    trace_callback,
) -> tuple[dict, str, str]:
    working = step_base
    stop_reason = "repeated_state"
    status = "exhausted"
    trace_callback(
        "stop",
        {
            "stop_reason": stop_reason,
            "step_count": len(step_trace),
            "status": status,
            "final_preview_util": float((w_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0)
            if w_eval
            else None,
            "reached_target_band": False,
            "all_key_pass": bool((w_eval.get("overview") or {}).get("all_key_pass")) if w_eval else False,
            "winning_label": winning_label,
            "winning_action_type": winning_action_type,
            "final_updates": _one_click_diff_accumulated_updates(initial_snapshot, working),
        },
    )
    return working, stop_reason, status


def _trace_final_fallback_solver_stop_coordinator(
    *,
    stop_reason: str,
    step_trace: list[dict],
    status: str,
    final_worst,
    final_in_band: bool,
    final_pass: bool,
    winning_label: str | None,
    winning_action_type: str | None,
    final_updates: dict,
    tightening_step_count: int,
    max_tightening_steps: int,
    final_eval: dict | None,
    mode_config: dict,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: str,
    final_distance_to_band,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list[str],
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: int,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    final_resolved_shear_util,
    final_resolved_web_util,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    rescue_debug: dict,
    trace_callback,
) -> None:
    trace_callback(
        "stop",
        {
            "stop_reason": stop_reason,
            "step_count": len(step_trace),
            "status": status,
            "final_preview_util": final_worst,
            "reached_target_band": bool(final_in_band and final_pass),
            "all_key_pass": final_pass,
            "winning_label": winning_label,
            "winning_action_type": winning_action_type,
            "final_updates": final_updates,
            "tightening_step_count": int(tightening_step_count),
            "tightening_depth_budget": int(max_tightening_steps),
            "still_materially_under_target": bool(
                _one_click_still_materially_under_target(final_eval or {}, mode_config, margin=0.03)
            ),
            "no_actionable_after_full_tightening_search": bool(no_actionable_after_full_tightening_search),
            "candidate_family_depth_reached": candidate_family_depth_reached,
            "final_distance_to_band": final_distance_to_band,
            "shear_governing_mode_active": bool(shear_governing_mode_active),
            "shear_severity_band": shear_severity_band,
            "shear_candidate_family_order": list(shear_candidate_family_order),
            "spacing_candidates_considered": int(spacing_candidates_considered),
            "leg_candidates_considered": int(leg_candidates_considered),
            "dia_candidates_considered": int(dia_candidates_considered),
            "geometry_candidates_considered_for_shear": int(geometry_candidates_considered_for_shear),
            "combined_candidates_considered_for_shear": int(combined_candidates_considered_for_shear),
            "web_crushing_penalty_applied": int(web_crushing_penalty_applied),
            "rejected_as_spacing_too_weak": int(rejected_as_spacing_too_weak),
            "rejected_as_web_crushing_marginal": int(rejected_as_web_crushing_marginal),
            "rejected_as_impractical_shear_layout": int(rejected_as_impractical_shear_layout),
            "final_resolved_shear_util": final_resolved_shear_util,
            "final_resolved_web_util": final_resolved_web_util,
            "shear_governing_family_detected": bool(shear_governing_family_detected),
            "governing_family_exists_after_domain_fix": bool(governing_family_exists_after_domain_fix),
            "pruned_non_shear_family_count": int(pruned_non_shear_family_count),
            "rescue_mode_entered": bool(rescue_debug.get("rescue_mode_entered")),
            "rescue_mode_entry_reason": rescue_debug.get("rescue_mode_entry_reason"),
            "rescue_mode_family": rescue_debug.get("rescue_mode_family"),
            "rescue_mode_tier_requested": rescue_debug.get("rescue_mode_tier_requested"),
            "rescue_mode_tier_used": rescue_debug.get("rescue_mode_tier_used"),
            "rescue_mode_seed_key": rescue_debug.get("rescue_mode_seed_key"),
            "rescue_mode_fallback_count": rescue_debug.get("rescue_mode_fallback_count"),
            "rescue_mode_ineffective_seeds": list(rescue_debug.get("rescue_mode_ineffective_seeds") or []),
            "rescue_mode_effective_seed_found": bool(rescue_debug.get("rescue_mode_effective_seed_found")),
            "rescue_mode_exit_reason": rescue_debug.get("rescue_mode_exit_reason"),
        },
    )


def _build_final_solver_debug_block_coordinator(
    *,
    final_solver_return_scope: dict,
) -> dict:
    scope = final_solver_return_scope
    return {
        "iteration_count": len(scope["step_trace"]),
        "initial_worst_util": scope["init_worst"],
        "final_worst_util": scope["final_worst"],
        "target_band": {"min": scope["t_lo"], "max": scope["t_hi"]},
        "stop_reason": scope["stop_reason"],
        "reached_target_band": bool(scope["final_in_band"] and scope["final_pass"]),
        "step_candidate_labels": [str(s.get("label") or "") for s in scope["step_trace"]],
        "all_key_pass": scope["final_pass"],
        "status": scope["status"],
        "trace_run_id": scope["rid"],
        **_coherence_debug_fields(scope["initial_coherence"]),
        "canonical_pack_built": True,
        "canonical_pack_source": "shared_rebuilt",
        "solver_blocked_by_incoherent_state": False,
        "tightening_step_count": int(scope["tightening_step_count"]),
        "tightening_depth_budget": int(scope["max_tightening_steps"]),
        "no_actionable_after_full_tightening_search": bool(scope["no_actionable_after_full_tightening_search"]),
        "candidate_family_depth_reached": scope["candidate_family_depth_reached"],
        "final_distance_to_band": scope["final_distance_to_band"],
        "shear_governing_mode_active": bool(scope["shear_governing_mode_active"]),
        "shear_severity_band": scope["shear_severity_band"],
        "shear_candidate_family_order": list(scope["shear_candidate_family_order"]),
        "spacing_candidates_considered": int(scope["spacing_candidates_considered"]),
        "leg_candidates_considered": int(scope["leg_candidates_considered"]),
        "dia_candidates_considered": int(scope["dia_candidates_considered"]),
        "geometry_candidates_considered_for_shear": int(scope["geometry_candidates_considered_for_shear"]),
        "combined_candidates_considered_for_shear": int(scope["combined_candidates_considered_for_shear"]),
        "web_crushing_penalty_applied": int(scope["web_crushing_penalty_applied"]),
        "rejected_as_spacing_too_weak": int(scope["rejected_as_spacing_too_weak"]),
        "rejected_as_web_crushing_marginal": int(scope["rejected_as_web_crushing_marginal"]),
        "rejected_as_impractical_shear_layout": int(scope["rejected_as_impractical_shear_layout"]),
        "final_resolved_shear_util": scope["final_resolved_shear_util"],
        "final_resolved_web_util": scope["final_resolved_web_util"],
        "shear_governing_family_detected": bool(scope["shear_governing_family_detected"]),
        "governing_family_exists_after_domain_fix": bool(scope["governing_family_exists_after_domain_fix"]),
        "pruned_non_shear_family_count": int(scope["pruned_non_shear_family_count"]),
        "governing_domain": scope["final_governing_domain"],
        "rejected_as_non_governing_cleanup": int(scope["rejected_as_non_governing_cleanup"]),
        "rejected_as_non_governing_shear_strengthening": int(scope["rejected_as_non_governing_shear_strengthening"]),
        "target_band_domain": scope["target_band_domain"],
        "target_domains_for_band": list(scope["target_domains_for_band"]),
        "final_target_domains_eval": list(scope["final_target_domains"]),
        "final_eval_band_trace": (
            _one_click_trace_eval_domain_payload(scope["final_eval"], scope["mode_config"])
            if isinstance(scope["final_eval"], dict)
            else {}
        ),
        "step_committable_eval_trace": list(scope["step_committable_eval_trace"]),
        "final_eval_internal_worst_util": scope["final_eval_internal_worst_util_dbg"],
        "final_eval_committable_worst_util": scope["final_eval_committable_worst_util_dbg"],
        "final_eval_used_source": scope["final_eval_used_source_dbg"],
        "final_eval_committable_updates": dict(scope["final_eval_committable_updates_dbg"] or {}),
        "final_objective_util": scope["final_objective_util"],
        "shear_remove_links_candidate_seen": bool(scope["shear_remove_links_candidate_seen"]),
        "shear_remove_links_candidate_truth_ok": bool(scope["shear_remove_links_candidate_truth_ok"]),
        "shear_remove_links_candidate_dropped_reason": scope["shear_remove_links_candidate_dropped_reason"],
        "shear_remove_links_candidate_materiality": scope["shear_remove_links_candidate_materiality"],
        "final_no_links_candidate_committed": False,
        "early_in_band_exit_blocked_for_tightening": bool(scope["early_in_band_exit_blocked_for_tightening"]),
        "early_in_band_exit_tightening_classification": scope["early_in_band_exit_tightening_classification"],
        "early_in_band_exit_available_tightening_paths": list(scope["early_in_band_exit_available_tightening_paths"]),
        "early_in_band_exit_reason": scope["early_in_band_exit_reason"],
        "partial_failing_final_updates_blocked": bool(scope["partial_failing_final_updates_blocked"]),
        "partial_failing_final_updates_raw": dict(scope["partial_failing_final_updates_raw"]),
        "best_available_out_of_band_retained": bool(scope["best_available_out_of_band_retained"]),
    }


def _build_final_solver_return_coordinator(
    *,
    step_trace: list[dict],
    init_worst,
    final_worst,
    t_lo,
    t_hi,
    stop_reason: str,
    final_in_band: bool,
    final_pass: bool,
    status: str,
    rid: str | None,
    initial_coherence,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: str,
    final_distance_to_band,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list[str],
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: int,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    final_resolved_shear_util,
    final_resolved_web_util,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    final_governing_domain,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    target_band_domain,
    target_domains_for_band,
    final_target_domains,
    final_eval,
    mode_config: dict,
    step_committable_eval_trace,
    final_eval_internal_worst_util_dbg,
    final_eval_committable_worst_util_dbg,
    final_eval_used_source_dbg,
    final_eval_committable_updates_dbg,
    final_objective_util,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason,
    shear_remove_links_candidate_materiality,
    early_in_band_exit_blocked_for_tightening: bool,
    early_in_band_exit_tightening_classification,
    early_in_band_exit_available_tightening_paths,
    early_in_band_exit_reason,
    partial_failing_final_updates_blocked: bool,
    partial_failing_final_updates_raw,
    best_available_out_of_band_retained: bool,
    rescue_debug: dict,
    rescue_gate_debug,
    final_updates: dict,
    working: dict,
    winning_label: str | None,
    winning_action_type: str | None,
) -> dict:
    final_solver_return_scope = locals()
    dbg = _build_final_solver_debug_block_coordinator(
        final_solver_return_scope=final_solver_return_scope,
    )
    return _build_final_solver_return_payload_with_debug_coordinator(
        final_solver_return_scope=final_solver_return_scope,
        dbg=dbg,
    )


def _build_final_solver_return_payload_with_debug_coordinator(
    *,
    final_solver_return_scope: dict,
    dbg: dict,
) -> dict:
    dbg.update(final_solver_return_scope["rescue_debug"])
    dbg["rescue_gate_debug"] = dict(
        final_solver_return_scope["rescue_gate_debug"] or {}
    )

    return {
        "status": final_solver_return_scope["status"],
        "stop_reason": final_solver_return_scope["stop_reason"],
        "step_count": len(final_solver_return_scope["step_trace"]),
        "initial_worst_util": final_solver_return_scope["init_worst"],
        "final_worst_util": final_solver_return_scope["final_worst"],
        "reached_target_band": bool(
            final_solver_return_scope["final_in_band"]
            and final_solver_return_scope["final_pass"]
        ),
        "all_key_pass": final_solver_return_scope["final_pass"],
        "final_updates": final_solver_return_scope["final_updates"],
        "final_state_preview": copy.deepcopy(
            (
                final_solver_return_scope["final_eval"].get("state")
                or final_solver_return_scope["working"]
            )
            if isinstance(final_solver_return_scope["final_eval"], dict)
            else final_solver_return_scope["working"]
        ),
        "step_trace": final_solver_return_scope["step_trace"],
        "winning_label": final_solver_return_scope["winning_label"],
        "winning_action_type": final_solver_return_scope["winning_action_type"],
        "one_click_solver_debug": dbg,
        "trace_run_id": final_solver_return_scope["rid"],
    }


def _trace_initial_solver_eval_coordinator(
    *,
    init_eval: dict,
    init_worst: float,
    init_in_band: bool,
    init_pass: bool,
    working: dict,
    trace_callback,
) -> None:
    _init_ov = init_eval.get("overview") if isinstance(init_eval.get("overview"), dict) else None
    trace_callback(
        "initial_eval",
        {
            "initial_worst_util": init_worst,
            "initial_statuses": dict((init_eval.get("overview") or {}).get("statuses") or {}),
            "initial_in_target_band": bool(init_in_band),
            "initial_all_key_pass": bool(init_pass),
            "stage3_shear_truth_at_initial_eval": _stage3_final_published_shear_truth_bundle(working),
            "stage3_remaining_issue_class": _stage3_remaining_issue_class_from_overview_state(working, _init_ov),
        },
    )


def _trace_candidate_pool_solver_coordinator(
    *,
    step_idx: int,
    raw_n: int,
    scored: list,
    pool_labels: list,
    tightening_mode_active: bool,
    governing_domain,
    tightening_meta: dict,
    material_improvement_threshold,
    reduction_candidates_considered: int,
    growth_candidates_rejected_in_tightening: int,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    rejected_as_non_material_improvement: int,
    tightening_step_count: int,
    max_tightening_steps: int,
    cur_eval: dict,
    mode_config: dict,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: str,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list[str],
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: int,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    domain_match_prune_used: bool,
    shear_prune_rule_source,
    fallback_next_hop_injected: bool,
    fallback_next_hop_reason,
    trace_callback,
) -> None:
    trace_callback(
        "candidate_pool",
        {
            "step": step_idx,
            "raw_candidate_count": int(raw_n),
            "actionable_candidate_count": len(scored),
            "labels_action_types": pool_labels,
            "no_actionable_candidates": len(scored) == 0,
            "tightening_mode_active": bool(tightening_mode_active),
            "governing_domain": governing_domain,
            "candidate_families_considered": list(tightening_meta.get("candidate_families_considered") or []),
            "candidate_families_pruned": list(tightening_meta.get("candidate_families_pruned") or []),
            "material_improvement_threshold": material_improvement_threshold,
            "reduction_candidates_considered": int(reduction_candidates_considered),
            "growth_candidates_rejected_in_tightening": int(growth_candidates_rejected_in_tightening),
            "rejected_as_non_governing_cleanup": int(rejected_as_non_governing_cleanup),
            "rejected_as_non_governing_shear_strengthening": int(rejected_as_non_governing_shear_strengthening),
            "rejected_as_non_material_improvement": int(rejected_as_non_material_improvement),
            "tightening_step_count": int(tightening_step_count),
            "tightening_depth_budget": int(max_tightening_steps),
            "still_materially_under_target": bool(
                _one_click_still_materially_under_target(cur_eval, mode_config, margin=0.03)
            ),
            "no_actionable_after_full_tightening_search": bool(no_actionable_after_full_tightening_search),
            "candidate_family_depth_reached": candidate_family_depth_reached,
            "best_distance_to_band_this_iteration": None,
            "shear_governing_mode_active": bool(shear_governing_mode_active),
            "shear_severity_band": shear_severity_band,
            "shear_candidate_family_order": list(shear_candidate_family_order),
            "spacing_candidates_considered": int(spacing_candidates_considered),
            "leg_candidates_considered": int(leg_candidates_considered),
            "dia_candidates_considered": int(dia_candidates_considered),
            "geometry_candidates_considered_for_shear": int(geometry_candidates_considered_for_shear),
            "combined_candidates_considered_for_shear": int(combined_candidates_considered_for_shear),
            "web_crushing_penalty_applied": int(web_crushing_penalty_applied),
            "rejected_as_spacing_too_weak": int(rejected_as_spacing_too_weak),
            "rejected_as_web_crushing_marginal": int(rejected_as_web_crushing_marginal),
            "rejected_as_impractical_shear_layout": int(rejected_as_impractical_shear_layout),
            "shear_governing_family_detected": bool(shear_governing_family_detected),
            "governing_family_exists_after_domain_fix": bool(governing_family_exists_after_domain_fix),
            "pruned_non_shear_family_count": int(pruned_non_shear_family_count),
            "domain_match_prune_used": bool(domain_match_prune_used),
            "shear_prune_rule_source": shear_prune_rule_source,
            "fallback_next_hop_injected": bool(fallback_next_hop_injected),
            "fallback_next_hop_reason": fallback_next_hop_reason,
        },
    )


def _trace_iteration_start_solver_coordinator(
    *,
    step_idx: int,
    cur_sig,
    working: dict,
    cur_eval: dict,
    t_lo,
    t_hi,
    tightening_mode_active: bool,
    governing_domain,
    material_improvement_threshold,
    tightening_step_count: int,
    max_tightening_steps: int,
    mode_config: dict,
    no_actionable_after_full_tightening_search: bool,
    shear_governing_mode_active: bool,
    shear_severity_band,
    shear_candidate_family_order: list,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    mixed_direction_mode,
    pruned_non_shear_family_count: int,
    domain_match_prune_used: bool,
    shear_prune_rule_source,
    trace_callback,
) -> None:
    trace_callback(
        "iteration_start",
        {
            "step": step_idx,
            "working_signature": list(cur_sig) if cur_sig else [],
            "working_summary": _trace_compact_shared_geom_reo(working),
            "current_worst_util": float((cur_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "target_band": {"min": t_lo, "max": t_hi},
            "current_overview": _trace_compact_overview_dict(cur_eval.get("overview")),
            "tightening_mode_active": bool(tightening_mode_active),
            "governing_domain": governing_domain,
            "material_improvement_threshold": material_improvement_threshold,
            "tightening_step_count": int(tightening_step_count),
            "tightening_depth_budget": int(max_tightening_steps),
            "still_materially_under_target": bool(
                _one_click_still_materially_under_target(cur_eval, mode_config, margin=0.03)
            ),
            "no_actionable_after_full_tightening_search": bool(no_actionable_after_full_tightening_search),
            "shear_governing_mode_active": bool(shear_governing_mode_active),
            "shear_severity_band": shear_severity_band,
            "shear_candidate_family_order": list(shear_candidate_family_order),
            "shear_governing_family_detected": bool(shear_governing_family_detected),
            "governing_family_exists_after_domain_fix": bool(governing_family_exists_after_domain_fix),
            "mixed_direction_mode": mixed_direction_mode,
            "pruned_non_shear_family_count": int(pruned_non_shear_family_count),
            "domain_match_prune_used": bool(domain_match_prune_used),
            "shear_prune_rule_source": shear_prune_rule_source,
        },
    )


def _prepare_one_click_solver_iteration_scoring_start_state_coordinator(
    *,
    step_idx: int,
    cur_sig: tuple,
    working: dict,
    cur_eval: dict,
    t_lo: float,
    t_hi: float,
    tightening_mode_active: bool,
    governing_domain: str | None,
    material_improvement_threshold: float,
    tightening_step_count: int,
    max_tightening_steps: int,
    mode_config: OneClickModeConfig,
    no_actionable_after_full_tightening_search: bool,
    shear_governing_mode_active: bool,
    shear_severity_band: str | None,
    shear_candidate_family_order: list,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    mixed_direction_mode: str,
    pruned_non_shear_family_count: int,
    domain_match_prune_used: bool,
    shear_prune_rule_source: str | None,
    trace_callback,
) -> dict:
    shear_prune_rule_source = "domain_matcher" if domain_match_prune_used else shear_prune_rule_source
    _trace_iteration_start_solver_coordinator(
        step_idx=step_idx,
        cur_sig=cur_sig,
        working=working,
        cur_eval=cur_eval,
        t_lo=t_lo,
        t_hi=t_hi,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        material_improvement_threshold=material_improvement_threshold,
        tightening_step_count=tightening_step_count,
        max_tightening_steps=max_tightening_steps,
        mode_config=mode_config,
        no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
        shear_governing_mode_active=shear_governing_mode_active,
        shear_severity_band=shear_severity_band,
        shear_candidate_family_order=shear_candidate_family_order,
        shear_governing_family_detected=shear_governing_family_detected,
        governing_family_exists_after_domain_fix=governing_family_exists_after_domain_fix,
        mixed_direction_mode=mixed_direction_mode,
        pruned_non_shear_family_count=pruned_non_shear_family_count,
        domain_match_prune_used=domain_match_prune_used,
        shear_prune_rule_source=shear_prune_rule_source,
        trace_callback=trace_callback,
    )
    cur_has_td = bool(_candidate_target_domains_for_band(cur_eval))
    cur_domain_progress = _one_click_required_domain_progress(cur_eval, mode_config) if cur_has_td else {}
    return {
        "shear_prune_rule_source": shear_prune_rule_source,
        "cur_has_td": cur_has_td,
        "cur_required_fail_count": int(cur_domain_progress.get("required_fail_count", 0) or 0),
        "cur_required_unsatisfied_count": int(
            cur_domain_progress.get("required_unsatisfied_count", 0) or 0
        ),
        "scored": [],
    }


def _prepare_one_click_solver_candidate_preview_eval_state_coordinator(
    *,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    direction: dict,
    working: dict,
    tightening_mode_active: bool,
    governing_domain: str | None,
    family_hint: str,
    rejected_as_evaluation_failed: int,
    trace_callback,
) -> dict:
    preview = copy.deepcopy(working)
    preview.update(norm_u)
    preview = _build_canonical_design_state_pack(_guidance_state_snapshot(preview))
    peval = evaluate_candidate_full(
        preview,
        source=f"one_click_preview_{step_idx}",
        label=rc["title"],
        action_type=rc["action_type"],
        updates=dict(norm_u),
    )
    if peval is None:
        rejected_as_evaluation_failed += 1
        _trace_candidate_eval_evaluation_failed_solver_coordinator(
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            direction=direction,
            tightening_mode_active=tightening_mode_active,
            governing_domain=governing_domain,
            family_hint=family_hint,
            trace_callback=trace_callback,
        )
        return {
            "peval": None,
            "preview": preview,
            "rejected_as_evaluation_failed": rejected_as_evaluation_failed,
            "should_continue": True,
        }
    return {
        "peval": peval,
        "preview": preview,
        "rejected_as_evaluation_failed": rejected_as_evaluation_failed,
        "should_continue": False,
    }


def _prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator(
    *,
    peval: dict,
    norm_u: dict,
    target_domains_for_band: list[str],
    mode_config: OneClickModeConfig,
    target_band_domain: str | None,
    cur_shear_failing: bool,
) -> dict:
    candidate_target_domains = _one_click_target_domains_for_eval(target_domains_for_band, norm_u)
    _one_click_attach_eval_target_domains(peval, candidate_target_domains, mode_config)
    if not candidate_target_domains:
        if target_band_domain == "shear" and cur_shear_failing:
            peval["target_domain_for_band"] = "shear"
        else:
            peval.pop("target_domain_for_band", None)
    return {
        "peval": peval,
        "candidate_target_domains": candidate_target_domains,
    }


def _handle_one_click_solver_duplicate_signature_candidate_coordinator(
    *,
    peval: dict,
    mode_config: OneClickModeConfig,
    seen_sigs: set,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    direction: dict,
    tightening_mode_active: bool,
    governing_domain: str | None,
    family_hint: str,
    rejected_as_duplicate_signature: int,
    trace_callback,
) -> dict:
    psig = _candidate_state_signature(peval)
    if psig and psig in seen_sigs:
        rejected_as_duplicate_signature += 1
        _new_u = _candidate_objective_util(peval)
        new_d = _candidate_target_band_distance(peval, mode_config)
        _trace_candidate_eval_duplicate_signature_solver_coordinator(
            peval=peval,
            mode_config=mode_config,
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            new_d=new_d,
            direction=direction,
            tightening_mode_active=tightening_mode_active,
            governing_domain=governing_domain,
            family_hint=family_hint,
            trace_callback=trace_callback,
        )
        return {
            "psig": psig,
            "rejected_as_duplicate_signature": rejected_as_duplicate_signature,
            "should_continue": True,
        }
    return {
        "psig": psig,
        "rejected_as_duplicate_signature": rejected_as_duplicate_signature,
        "should_continue": False,
    }


def _prepare_one_click_solver_candidates_coordinator(
    *,
    raw_candidates,
    working: dict,
    governing_domain,
    use_governing_domain_candidates: bool,
    cur_eval: dict,
    mode_config: dict,
) -> dict:
    pool_labels: list[dict] = []
    prepared: list[dict] = []
    prepared_samples: list[dict] = []
    reduction_candidates_considered = 0
    governing_family_exists = bool(
        use_governing_domain_candidates
        and any(
            _candidate_family_matches_governing_domain(
                str((rc or {}).get("_tightening_family") or _design_guide_candidate_family((rc or {}).get("item")) or ""),
                governing_domain,
            )
            for rc in (raw_candidates or [])
        )
    )
    shear_governing_family_detected = bool(
        governing_domain == "shear"
        and any(
            _candidate_family_matches_governing_domain(
                str((rc or {}).get("_tightening_family") or _design_guide_candidate_family((rc or {}).get("item")) or ""),
                "shear",
            )
            for rc in (raw_candidates or [])
        )
    )
    for rc in raw_candidates:
        family_hint = str(rc.get("_tightening_family") or _design_guide_candidate_family(rc.get("item")) or "")
        pool_labels.append(
            {
                "label": rc.get("title"),
                "action_type": rc.get("action_type"),
                "updates": dict(rc.get("raw_updates") or {}),
                "family": family_hint,
            },
        )
        raw_u = dict(rc["raw_updates"])
        norm_u = _normalise_invalid_shear_state_updates(working, raw_u, source="one_click_iter:normalize")
        direction = _one_click_update_direction_summary(working, norm_u or {})
        if direction.get("is_reduction_candidate"):
            reduction_candidates_considered += 1
        prepared.append(
            {
                "rc": rc,
                "raw_u": raw_u,
                "norm_u": norm_u,
                "direction": direction,
                "family": family_hint,
            },
        )
        if len(prepared_samples) < 6:
            prepared_samples.append(
                {
                    "label": rc.get("title"),
                    "action_type": rc.get("action_type"),
                    "family": family_hint,
                    "raw_updates": dict(raw_u),
                    "normalized_updates": dict(norm_u or {}),
                }
            )
    governing_family_exists_after_domain_fix = bool(governing_family_exists or shear_governing_family_detected)
    shear_domain_prune_active = bool(governing_domain == "shear" and shear_governing_family_detected)
    return {
        "pool_labels": pool_labels,
        "prepared": prepared,
        "prepared_samples": prepared_samples,
        "reduction_candidates_considered": int(reduction_candidates_considered),
        "governing_family_exists": bool(governing_family_exists),
        "shear_governing_family_detected": bool(shear_governing_family_detected),
        "governing_family_exists_after_domain_fix": governing_family_exists_after_domain_fix,
        "shear_domain_prune_active": shear_domain_prune_active,
        "should_apply_domain_prune": bool(governing_family_exists or shear_domain_prune_active),
        "mixed_direction_mode": _one_click_mixed_direction_classification(cur_eval, mode_config),
    }


def _trace_rescue_decision_solver_coordinator(
    *,
    rescue_should_enter: bool,
    rescue_entry_reason,
    rescue_family,
    rescue_tier_requested,
    final_pass: bool,
    final_updates: dict,
    stop_reason: str,
    rescue_gate_debug: dict,
    trace_callback,
) -> None:
    trace_callback(
        "rescue_decision",
        {
            "rescue_mode_entered": bool(rescue_should_enter),
            "rescue_mode_entry_reason": rescue_entry_reason,
            "rescue_mode_family": rescue_family,
            "rescue_mode_tier_requested": rescue_tier_requested,
            "final_pass": bool(final_pass),
            "final_updates_present": bool(final_updates),
            "stop_reason_before_rescue": stop_reason,
            "gate_debug": dict(rescue_gate_debug or {}),
        },
    )


def _trace_rescue_seed_attempt_solver_coordinator(
    *,
    seed_key: str,
    rescue_family,
    rescue_tier_requested,
    tier,
    seed_updates: dict,
    legal: bool,
    illegal_reason,
    fallback_count: int,
    trace_callback,
) -> None:
    trace_callback(
        "rescue_seed_attempt",
        {
            "seed_key": seed_key,
            "family": rescue_family,
            "requested_tier": rescue_tier_requested,
            "used_tier": tier,
            "seed_updates": dict(seed_updates),
            "seed_legal": bool(legal),
            "seed_illegal_reason": illegal_reason,
            "fallback_count": int(fallback_count),
        },
    )


def _trace_rescue_seed_ineffective_solver_coordinator(
    *,
    seed_key: str,
    rescue_family,
    rescue_tier_requested,
    tier,
    fallback_count: int,
    trace_callback,
) -> None:
    trace_callback(
        "rescue_seed_ineffective",
        {
            "seed_key": seed_key,
            "family": rescue_family,
            "requested_tier": rescue_tier_requested,
            "used_tier": tier,
            "fallback_count": int(fallback_count),
        },
    )


def _trace_rescue_exit_solver_coordinator(
    *,
    seed_key: str,
    rescue_family,
    rescue_tier_requested,
    tier,
    fallback_count: int,
    ineffective_seeds: list[str],
    rescue_result: dict,
    trace_callback,
) -> None:
    trace_callback(
        "rescue_exit",
        {
            "exit_reason": "effective_seed_handoff_to_normal_optimizer",
            "seed_key": seed_key,
            "family": rescue_family,
            "requested_tier": rescue_tier_requested,
            "used_tier": tier,
            "fallback_count": int(fallback_count),
            "ineffective_seeds": list(ineffective_seeds),
            "post_seed_stop_reason": rescue_result.get("stop_reason"),
            "post_seed_final_worst_util": rescue_result.get("final_worst_util"),
        },
    )


def _trace_candidate_eval_pre_eval_rejection_solver_coordinator(
    *,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    direction: dict,
    tightening_mode_active: bool,
    governing_domain,
    family_hint: str,
    rejection_reason: str,
    trace_callback,
    extra_fields: dict | None = None,
) -> None:
    payload = {
        "step": step_idx,
        "label": rc.get("title"),
        "action_type": rc.get("action_type"),
        "updates": dict(norm_u),
        "preview_util": None,
        "preview_statuses": None,
        "reaches_target_band": None,
        "distance_to_band": None,
        "duplicate_signature_rejected": False,
        "no_real_change_rejected": False,
        "evaluation_failed": False,
        "ranking_tuple": None,
        "tightening_mode_active": bool(tightening_mode_active),
        "reduction_candidate": bool(direction.get("is_reduction_candidate")),
        "growth_candidate": bool(direction.get("is_growth_only")),
        "governing_domain": governing_domain,
        "candidate_family": family_hint,
        "rejection_reason": rejection_reason,
    }
    if extra_fields:
        payload.update(extra_fields)
    trace_callback("candidate_eval", payload)


def _trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator(
    *,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    direction: dict,
    target_domains_for_band,
    tightening_mode_active: bool,
    governing_domain,
    family_hint: str,
    rejection_reason: str,
    trace_callback,
) -> None:
    _trace_candidate_eval_pre_eval_rejection_solver_coordinator(
        step_idx=step_idx,
        rc=rc,
        norm_u=norm_u,
        direction=direction,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        family_hint=family_hint,
        rejection_reason=rejection_reason,
        extra_fields={
            "target_domains_for_band": list(
                _one_click_target_domains_for_eval(target_domains_for_band, norm_u),
            ),
            "target_domain_for_band": None,
            "candidate_domain_utils": {},
        },
        trace_callback=trace_callback,
    )


def _trace_candidate_eval_evaluation_failed_solver_coordinator(
    *,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    direction: dict,
    tightening_mode_active: bool,
    governing_domain,
    family_hint: str,
    trace_callback,
) -> None:
    _trace_candidate_eval_pre_eval_rejection_solver_coordinator(
        step_idx=step_idx,
        rc=rc,
        norm_u=norm_u,
        direction=direction,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        family_hint=family_hint,
        rejection_reason="evaluation_failed",
        extra_fields={"evaluation_failed": True},
        trace_callback=trace_callback,
    )


def _trace_candidate_eval_no_real_change_solver_coordinator(
    *,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    raw_u: dict,
    direction: dict,
    tightening_mode_active: bool,
    governing_domain,
    family_hint: str,
    trace_callback,
) -> None:
    _trace_candidate_eval_pre_eval_rejection_solver_coordinator(
        step_idx=step_idx,
        rc=rc,
        norm_u=norm_u,
        direction=direction,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        family_hint=family_hint,
        rejection_reason="no_real_change",
        extra_fields={
            "updates": dict(norm_u) if norm_u else dict(raw_u),
            "no_real_change_rejected": True,
        },
        trace_callback=trace_callback,
    )


def _trace_candidate_eval_duplicate_signature_solver_coordinator(
    *,
    peval: dict,
    mode_config: dict,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    new_d,
    direction: dict,
    tightening_mode_active: bool,
    governing_domain,
    family_hint: str,
    trace_callback,
) -> None:
    trace_callback(
        "candidate_eval",
        {
            **_one_click_trace_eval_domain_payload(peval, mode_config),
            "step": step_idx,
            "label": rc.get("title"),
            "action_type": rc.get("action_type"),
            "updates": dict(norm_u),
            "preview_util": float((peval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "preview_statuses": dict((peval.get("overview") or {}).get("statuses") or {}),
            "reaches_target_band": bool(_candidate_in_target_band(peval, mode_config)),
            "distance_to_band": new_d,
            "duplicate_signature_rejected": True,
            "no_real_change_rejected": False,
            "evaluation_failed": False,
            "ranking_tuple": None,
            "tightening_mode_active": bool(tightening_mode_active),
            "reduction_candidate": bool(direction.get("is_reduction_candidate")),
            "growth_candidate": bool(direction.get("is_growth_only")),
            "governing_domain": governing_domain,
            "candidate_family": family_hint,
            "rejection_reason": "duplicate_signature",
        },
    )


def _trace_candidate_eval_shear_preview_rejection_solver_coordinator(
    *,
    peval: dict,
    mode_config: dict,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    new_d,
    governing_domain,
    family_hint: str,
    rejection_reason: str,
    trace_callback,
) -> None:
    trace_callback(
        "candidate_eval",
        {
            "step": step_idx,
            "label": rc.get("title"),
            "action_type": rc.get("action_type"),
            "updates": dict(norm_u),
            "preview_util": float((peval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "preview_statuses": dict((peval.get("overview") or {}).get("statuses") or {}),
            "reaches_target_band": bool(_candidate_in_target_band(peval, mode_config)),
            "distance_to_band": float(new_d),
            "duplicate_signature_rejected": False,
            "no_real_change_rejected": False,
            "evaluation_failed": False,
            "ranking_tuple": None,
            "tightening_mode_active": True,
            "governing_domain": governing_domain,
            "candidate_family": family_hint,
            "rejection_reason": rejection_reason,
        },
    )


def _trace_candidate_eval_wrong_direction_solver_coordinator(
    *,
    peval: dict,
    mode_config: dict,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    new_d,
    direction: dict,
    governing_domain,
    family_hint: str,
    multi_domain_step_improves: bool,
    all_pass_band_distance_improves: bool,
    trace_callback,
) -> None:
    trace_callback(
        "candidate_eval",
        {
            "step": step_idx,
            "label": rc.get("title"),
            "action_type": rc.get("action_type"),
            "updates": dict(norm_u),
            "preview_util": float((peval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "preview_statuses": dict((peval.get("overview") or {}).get("statuses") or {}),
            "reaches_target_band": bool(_candidate_in_target_band(peval, mode_config)),
            "distance_to_band": float(new_d),
            "duplicate_signature_rejected": False,
            "no_real_change_rejected": False,
            "evaluation_failed": False,
            "ranking_tuple": None,
            "tightening_mode_active": True,
            "reduction_candidate": bool(direction.get("is_reduction_candidate")),
            "growth_candidate": bool(direction.get("is_growth_only")),
            "governing_domain": governing_domain,
            "candidate_family": family_hint,
            "rejection_reason": "wrong_direction_reduction_mode",
            "multi_domain_step_improves": bool(multi_domain_step_improves),
            "all_pass_band_distance_improves": bool(all_pass_band_distance_improves),
        },
    )


def _trace_candidate_eval_non_material_solver_coordinator(
    *,
    peval: dict,
    mode_config: dict,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    new_d,
    direction: dict,
    governing_domain,
    family_hint: str,
    trace_callback,
) -> None:
    trace_callback(
        "candidate_eval",
        {
            "step": step_idx,
            "label": rc.get("title"),
            "action_type": rc.get("action_type"),
            "updates": dict(norm_u),
            "preview_util": float((peval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "preview_statuses": dict((peval.get("overview") or {}).get("statuses") or {}),
            "reaches_target_band": bool(_candidate_in_target_band(peval, mode_config)),
            "distance_to_band": float(new_d),
            "duplicate_signature_rejected": False,
            "no_real_change_rejected": False,
            "evaluation_failed": False,
            "ranking_tuple": None,
            "tightening_mode_active": True,
            "reduction_candidate": bool(direction.get("is_reduction_candidate")),
            "growth_candidate": bool(direction.get("is_growth_only")),
            "governing_domain": governing_domain,
            "candidate_family": family_hint,
            "rejection_reason": "non_material_improvement",
        },
    )


def _trace_candidate_eval_scored_solver_coordinator(
    *,
    peval: dict,
    mode_config: dict,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    nib: bool,
    new_d,
    sort_key,
    tier,
    domain_progress: dict,
    has_target_domains: bool,
    dk,
    mixed_direction_mode,
    mixed_rank: dict,
    tightening_mode_active: bool,
    direction: dict,
    governing_domain,
    family_hint: str,
    material_improvement_threshold,
    trace_callback,
) -> None:
    trace_callback(
        "candidate_eval",
        {
            **_one_click_trace_eval_domain_payload(peval, mode_config),
            "step": step_idx,
            "label": rc.get("title"),
            "action_type": rc.get("action_type"),
            "updates": dict(norm_u),
            "preview_util": float((peval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "preview_statuses": dict((peval.get("overview") or {}).get("statuses") or {}),
            "reaches_target_band": bool(nib),
            "distance_to_band": float(new_d),
            "duplicate_signature_rejected": False,
            "no_real_change_rejected": False,
            "evaluation_failed": False,
            "ranking_tuple": list(sort_key),
            "ranking_components": {
                "tier_pass_in_band": tier,
                "required_fail_count": int(domain_progress.get("required_fail_count", 0) or 0) if has_target_domains else None,
                "required_unsatisfied_count": int(domain_progress.get("required_unsatisfied_count", 0) or 0) if has_target_domains else None,
                "distance_to_band": float(new_d),
                "directional_tie_key": float(dk),
                "mixed_direction_mode": mixed_direction_mode,
                "mixed_primary_domain": mixed_rank.get("primary_domain"),
                "mixed_secondary_domain": mixed_rank.get("secondary_domain"),
                "mixed_primary_material_improvement": bool(mixed_rank.get("primary_material_improvement")),
                "mixed_primary_distance": float(mixed_rank.get("primary_distance", float("inf"))),
                "mixed_secondary_distance": float(mixed_rank.get("secondary_distance", float("inf"))),
                "tightening_mode_active": bool(tightening_mode_active),
                "reduction_candidate": bool(direction.get("is_reduction_candidate")),
                "governing_domain": governing_domain,
                "candidate_family": family_hint,
                "material_improvement_threshold": material_improvement_threshold,
                "update_key_count": len(norm_u),
            },
            "tightening_mode_active": bool(tightening_mode_active),
            "reduction_candidate": bool(direction.get("is_reduction_candidate")),
            "growth_candidate": bool(direction.get("is_growth_only")),
            "governing_domain": governing_domain,
            "candidate_family": family_hint,
            "rejection_reason": None,
        },
    )


def _prepare_one_click_solver_initial_state_coordinator(
    *,
    state: dict,
    trace_run_id: str | None,
    trace_source: str,
    rescue_attempted_seed_keys: tuple[str, ...],
) -> dict:
    rid = trace_run_id
    stop_traced: list[bool] = [False]
    rescue_debug = _rescue_mode_default_debug()
    attempted_seed_keys = set(str(k) for k in (rescue_attempted_seed_keys or ()) if str(k))
    trace_callback = _build_one_click_solver_trace_callback_coordinator(
        rid=rid,
        stop_traced=stop_traced,
        trace_source=trace_source,
    )
    initial_snapshot = copy.deepcopy(
        _build_canonical_design_state_pack(
            _overlay_current_normalized_shear_truth(_guidance_state_snapshot(dict(state or {})))
        )
    )
    initial_coherence = _design_state_coherence_check(initial_snapshot)
    initial_pack_valid = _canonical_pack_is_valid(initial_snapshot)
    initial_coherence_should_block = bool(initial_coherence.get("coherence_should_block"))
    initial_stop_reason = (
        str(initial_snapshot.get("canonical_pack_error") or "").strip()
        if not initial_pack_valid and str(initial_snapshot.get("canonical_pack_error") or "").strip()
        else str((initial_coherence.get("coherence_blocking_issues") or ["state_incoherent_after_rebuild"])[0])
    )
    return {
        "rid": rid,
        "stop_traced": stop_traced,
        "rescue_debug": rescue_debug,
        "attempted_seed_keys": attempted_seed_keys,
        "trace_callback": trace_callback,
        "initial_snapshot": initial_snapshot,
        "initial_coherence": initial_coherence,
        "initial_pack_valid": initial_pack_valid,
        "initial_coherence_should_block": initial_coherence_should_block,
        "initial_stop_reason": initial_stop_reason,
    }


def _prepare_one_click_solver_mode_budget_state_coordinator(
    *,
    initial_snapshot: dict,
    max_steps: int,
) -> dict:
    working = copy.deepcopy(initial_snapshot)
    mode_config = _design_mode_config(_design_optimisation_goal(working))

    t_lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    t_hi = float(mode_config.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    max_tightening_steps = max(1, min(int(max_steps), 4))
    return {
        "working": working,
        "mode_config": mode_config,
        "t_lo": t_lo,
        "t_hi": t_hi,
        "max_tightening_steps": max_tightening_steps,
        "tightening_budget_extensions_used": 0,
        "tightening_budget_extension_cap": max(0, int(max_steps) - int(max_tightening_steps)),
        "tightening_step_count": 0,
        "no_actionable_after_full_tightening_search": False,
        "candidate_family_depth_reached": "none",
        "final_distance_to_band": None,
        "shear_governing_mode_active": False,
        "shear_severity_band": "mild",
        "shear_candidate_family_order": [],
        "spacing_candidates_considered": 0,
        "leg_candidates_considered": 0,
        "dia_candidates_considered": 0,
        "geometry_candidates_considered_for_shear": 0,
        "combined_candidates_considered_for_shear": 0,
        "web_crushing_penalty_applied": 0,
        "rejected_as_spacing_too_weak": 0,
        "rejected_as_web_crushing_marginal": 0,
        "rejected_as_impractical_shear_layout": 0,
        "final_resolved_shear_util": None,
        "final_resolved_web_util": None,
        "step_committable_eval_trace": [],
        "final_eval_internal_worst_util_dbg": None,
        "final_eval_committable_worst_util_dbg": None,
        "final_eval_used_source_dbg": "internal_working_preview",
        "final_eval_committable_updates_dbg": {},
    }


def _prepare_one_click_solver_initial_eval_state_coordinator(
    *,
    working: dict,
    mode_config: dict,
    trace_callback,
) -> dict:
    init_eval = evaluate_candidate_full(
        _build_canonical_design_state_pack(working),
        source="one_click_solve_seed",
        label="Seed",
        action_type="one_click",
        updates={},
    )
    if init_eval is None:
        return {"init_eval": None}

    target_band_domain = _governing_focus_from_overview((init_eval.get("overview") or {}))
    initial_statuses = dict((init_eval.get("overview") or {}).get("statuses") or {})
    _init_shear_st = initial_statuses.get("shear")
    _init_shear_failing = bool(
        _init_shear_st == BEAM_STATUS_FAIL or str(_init_shear_st or "").strip().upper() == "FAIL",
    )
    target_domains_for_band = _one_click_seed_target_domains_from_eval(init_eval, mode_config)

    _init_td = _one_click_target_domains_for_eval(target_domains_for_band, {})
    _one_click_attach_eval_target_domains(init_eval, _init_td, mode_config)
    if not _init_td:
        if target_band_domain == "shear" and _init_shear_failing:
            init_eval["target_domain_for_band"] = "shear"
        else:
            init_eval.pop("target_domain_for_band", None)
    init_worst = float((init_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0)
    init_pass = bool((init_eval.get("overview") or {}).get("all_key_pass"))
    init_in_band = _candidate_in_target_band(init_eval, mode_config)
    init_progress = _one_click_required_domain_progress(init_eval, mode_config)
    _trace_initial_solver_eval_coordinator(
        init_eval=init_eval,
        init_worst=init_worst,
        init_in_band=init_in_band,
        init_pass=init_pass,
        working=working,
        trace_callback=trace_callback,
    )
    return {
        "init_eval": init_eval,
        "target_band_domain": target_band_domain,
        "initial_statuses": initial_statuses,
        "target_domains_for_band": target_domains_for_band,
        "init_worst": init_worst,
        "init_pass": init_pass,
        "init_in_band": init_in_band,
        "init_progress": init_progress,
    }


def _prepare_one_click_solver_early_in_band_gate_state_coordinator(
    *,
    working: dict,
    init_eval: dict,
    mode_config: dict,
    init_pass: bool,
    init_in_band: bool,
) -> dict:
    early_in_band_exit_blocked_for_tightening = False
    early_in_band_exit_tightening_classification = ""
    early_in_band_exit_available_tightening_paths: list[str] = []
    early_in_band_exit_reason = "seed_not_in_band_or_not_passing"
    early_in_band_shear_cleanup_deferral: dict = {
        "active": False,
        "reason": "not_evaluated",
        "recommendation": None,
        "candidate_eval": None,
    }
    if init_pass and init_in_band:
        eff_state_for_early_exit = None
        try:
            eff_state_for_early_exit = compute_efficiency_tightening_state(working)
        except Exception:
            eff_state_for_early_exit = None
        if isinstance(eff_state_for_early_exit, dict):
            early_in_band_exit_tightening_classification = str(
                eff_state_for_early_exit.get("classification") or ""
            ).strip()
            for _k in (
                "mode_tightening",
                "bottom_tightening",
                "shear_tightening",
                "geometry_tightening",
            ):
                _cand = eff_state_for_early_exit.get(_k)
                _updates = dict(_cand.get("updates") or {}) if isinstance(_cand, dict) else {}
                if _updates and not _updates_match_state(working, _updates):
                    early_in_band_exit_available_tightening_paths.append(_k)
        has_actionable_efficiency_tightening = bool(
            early_in_band_exit_tightening_classification == "inefficient"
            and early_in_band_exit_available_tightening_paths
        )
        if has_actionable_efficiency_tightening:
            early_in_band_exit_blocked_for_tightening = True
            early_in_band_exit_reason = "blocked_actionable_efficiency_tightening_available"
        else:
            early_in_band_exit_reason = "already_in_band_no_actionable_efficiency_tightening"
        early_in_band_shear_cleanup_deferral = _one_click_in_band_shear_cleanup_deferral(
            working,
            init_eval,
            mode_config,
        )
        if bool(early_in_band_shear_cleanup_deferral.get("active")):
            early_in_band_exit_blocked_for_tightening = True
            early_in_band_exit_reason = str(
                early_in_band_shear_cleanup_deferral.get("reason")
                or "blocked_non_governing_shear_cleanup_available"
            )
            if "shear_tightening" not in early_in_band_exit_available_tightening_paths:
                early_in_band_exit_available_tightening_paths.append("shear_tightening")
    return {
        "early_in_band_exit_blocked_for_tightening": early_in_band_exit_blocked_for_tightening,
        "early_in_band_exit_tightening_classification": early_in_band_exit_tightening_classification,
        "early_in_band_exit_available_tightening_paths": early_in_band_exit_available_tightening_paths,
        "early_in_band_exit_reason": early_in_band_exit_reason,
        "early_in_band_shear_cleanup_deferral": early_in_band_shear_cleanup_deferral,
        "should_return_already_in_band": bool(
            init_pass and init_in_band and not early_in_band_exit_blocked_for_tightening
        ),
    }


def _prepare_one_click_solver_iteration_state_coordinator(*, init_eval: dict) -> dict:
    seen_sigs: set[tuple] = set()
    sig0 = _candidate_state_signature(init_eval)
    if sig0:
        seen_sigs.add(sig0)

    return {
        "seen_sigs": seen_sigs,
        "step_trace": [],
        "stop_reason": "max_steps",
        "status": "exhausted",
        "winning_label": None,
        "winning_action_type": None,
        "final_governing_domain": _governing_focus_from_overview((init_eval.get("overview") or {})),
        "rejected_as_non_governing_cleanup": 0,
        "rejected_as_non_governing_shear_strengthening": 0,
        "shear_remove_links_candidate_seen": False,
        "shear_remove_links_candidate_truth_ok": False,
        "shear_remove_links_candidate_dropped_reason": None,
        "shear_remove_links_candidate_materiality": "not_evaluated",
    }


def _prepare_one_click_solver_current_iteration_eval_state_coordinator(
    *,
    step_idx: int,
    working: dict,
    mode_config: dict,
    target_band_domain: str,
    step_trace: list[dict],
    initial_snapshot: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    trace_callback,
) -> dict:
    cur_eval = evaluate_candidate_full(
        _build_canonical_design_state_pack(working),
        source=f"one_click_work_{step_idx}",
        label="Working",
        action_type="one_click",
        updates={},
    )
    if cur_eval is None:
        stop_reason, status = _trace_evaluate_failed_working_solver_stop_coordinator(
            step_trace=step_trace,
            initial_snapshot=initial_snapshot,
            working=working,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            trace_callback=trace_callback,
        )
        return {
            "cur_eval": None,
            "stop_reason": stop_reason,
            "status": status,
            "should_break": True,
        }

    cur_pass = bool((cur_eval.get("overview") or {}).get("all_key_pass"))
    cur_sig = _candidate_state_signature(cur_eval)
    tightening_mode_active = _one_click_tightening_mode_active(cur_eval, mode_config)
    governing_domain = _governing_focus_from_overview((cur_eval or {}).get("overview"))
    if bool(target_band_domain != "shear" and governing_domain == "shear" and not cur_pass):
        target_band_domain = "shear"
    cur_statuses = dict((cur_eval.get("overview") or {}).get("statuses") or {})
    cur_shear_status = cur_statuses.get("shear")
    cur_shear_failing = bool(
        cur_shear_status == BEAM_STATUS_FAIL or str(cur_shear_status or "").strip().upper() == "FAIL",
    )
    cur_fail_keys = {
        str(k or "").strip().lower()
        for k, v in cur_statuses.items()
        if v == BEAM_STATUS_FAIL or str(v or "").strip().upper() == "FAIL"
    }
    governing_domain_norm = str(governing_domain or "").strip().lower()
    governing_domain_failing = bool(
        governing_domain_norm in cur_fail_keys
        or (
            governing_domain_norm == "bending"
            and bool(cur_fail_keys & {"bending", "flexure", "ductility"})
        )
        or (governing_domain_norm == "shear" and "shear" in cur_fail_keys)
    )
    return {
        "cur_eval": cur_eval,
        "cur_pass": cur_pass,
        "cur_sig": cur_sig,
        "tightening_mode_active": tightening_mode_active,
        "governing_domain": governing_domain,
        "target_band_domain": target_band_domain,
        "cur_statuses": cur_statuses,
        "cur_shear_status": cur_shear_status,
        "cur_shear_failing": cur_shear_failing,
        "cur_fail_keys": cur_fail_keys,
        "governing_domain_norm": governing_domain_norm,
        "governing_domain_failing": governing_domain_failing,
        "should_break": False,
    }


def _prepare_one_click_solver_current_target_domain_state_coordinator(
    *,
    initial_snapshot: dict,
    working: dict,
    cur_eval: dict,
    mode_config: dict,
    target_domains_for_band,
    target_band_domain: str,
    cur_shear_failing: bool,
    cur_pass: bool,
    governing_domain: str,
    tightening_mode_active: bool,
) -> dict:
    step_accum = _one_click_diff_accumulated_updates(initial_snapshot, working)
    cur_target_domains = _one_click_target_domains_for_eval(target_domains_for_band, step_accum)
    _one_click_attach_eval_target_domains(cur_eval, cur_target_domains, mode_config)
    if not cur_target_domains:
        if target_band_domain == "shear" and cur_shear_failing:
            cur_eval["target_domain_for_band"] = "shear"
        else:
            cur_eval.pop("target_domain_for_band", None)
            if target_band_domain == "shear" and not cur_shear_failing and not cur_pass:
                target_band_domain = governing_domain

    cur_ib = _candidate_in_target_band(cur_eval, mode_config)
    target_work_domain = str(cur_eval.get("target_domain_for_band") or "").strip().lower()
    required_domain_work_active = bool(
        cur_target_domains
        and target_work_domain in ("bending", "shear")
        and not cur_ib
    )
    if required_domain_work_active:
        governing_domain = target_work_domain
        if _one_click_domain_needs_cleanup(cur_eval, target_work_domain, mode_config):
            tightening_mode_active = True

    if target_band_domain == "shear" and cur_shear_failing and not cur_ib:
        governing_domain = "shear"
        tightening_mode_active = bool(cur_pass)
    return {
        "step_accum": step_accum,
        "cur_target_domains": cur_target_domains,
        "target_band_domain": target_band_domain,
        "cur_ib": cur_ib,
        "target_work_domain": target_work_domain,
        "required_domain_work_active": required_domain_work_active,
        "governing_domain": governing_domain,
        "tightening_mode_active": tightening_mode_active,
    }


def _prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator(
    *,
    working: dict,
    cur_eval: dict,
    mode_config: dict,
    cur_pass: bool,
    cur_ib: bool,
    tightening_mode_active: bool,
    governing_domain: str,
) -> dict:
    in_band_shear_cleanup_deferral = {
        "active": False,
        "reason": "not_applicable",
        "recommendation": None,
        "candidate_eval": None,
    }
    if cur_pass and cur_ib:
        in_band_shear_cleanup_deferral = _one_click_in_band_shear_cleanup_deferral(
            working,
            cur_eval,
            mode_config,
        )
        if bool(in_band_shear_cleanup_deferral.get("active")):
            tightening_mode_active = True
            governing_domain = "shear"
    final_governing_domain = governing_domain
    shear_governing_mode_active = bool(governing_domain == "shear")
    return {
        "in_band_shear_cleanup_deferral": in_band_shear_cleanup_deferral,
        "tightening_mode_active": tightening_mode_active,
        "governing_domain": governing_domain,
        "final_governing_domain": final_governing_domain,
        "shear_governing_mode_active": shear_governing_mode_active,
        "shear_governing_family_detected": False,
        "pruned_non_shear_family_count": 0,
        "domain_match_prune_used": False,
        "shear_prune_rule_source": None,
        "material_improvement_threshold": 1e-3,
        "tightening_meta": {
            "candidate_families_considered": [],
            "candidate_families_pruned": [],
            "governing_domain": governing_domain,
        },
        "should_stop_current_reached_target_band": bool(
            cur_pass and cur_ib and not bool(in_band_shear_cleanup_deferral.get("active"))
        ),
    }


def _prepare_one_click_solver_tightening_depth_gate_state_coordinator(
    *,
    cur_eval: dict,
    mode_config: dict,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    cur_ib: bool,
    cur_pass: bool,
    winning_label: str | None,
    winning_action_type: str | None,
    tightening_mode_active: bool,
    tightening_step_count: int,
    max_tightening_steps: int,
    tightening_budget_extensions_used: int,
    tightening_budget_extension_cap: int,
    candidate_family_depth_reached: str,
    trace_callback,
) -> dict:
    cur_u = _candidate_objective_util(cur_eval)
    if tightening_mode_active and tightening_step_count > max_tightening_steps:
        if (
            tightening_budget_extensions_used < tightening_budget_extension_cap
            and _one_click_budget_stop_has_better_next_hop(cur_eval, mode_config)
        ):
            return {
                "cur_u": cur_u,
                "max_tightening_steps": max_tightening_steps + 1,
                "tightening_budget_extensions_used": tightening_budget_extensions_used + 1,
                "final_distance_to_band": None,
                "should_continue": True,
                "should_break": False,
            }
        stop_reason, status, final_distance_to_band = _trace_tightening_depth_budget_solver_stop_coordinator(
            cur_eval=cur_eval,
            mode_config=mode_config,
            step_trace=step_trace,
            initial_snapshot=initial_snapshot,
            working=working,
            cur_ib=cur_ib,
            cur_pass=cur_pass,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            tightening_step_count=tightening_step_count,
            max_tightening_steps=max_tightening_steps,
            candidate_family_depth_reached=candidate_family_depth_reached,
            trace_callback=trace_callback,
        )
        return {
            "cur_u": cur_u,
            "max_tightening_steps": max_tightening_steps,
            "tightening_budget_extensions_used": tightening_budget_extensions_used,
            "stop_reason": stop_reason,
            "status": status,
            "final_distance_to_band": final_distance_to_band,
            "should_continue": False,
            "should_break": True,
        }
    return {
        "cur_u": cur_u,
        "max_tightening_steps": max_tightening_steps,
        "tightening_budget_extensions_used": tightening_budget_extensions_used,
        "final_distance_to_band": None,
        "should_continue": False,
        "should_break": False,
    }


def _prepare_one_click_solver_candidate_collection_state_coordinator(
    *,
    working: dict,
    debug_enabled: bool,
    trace_run_id: str | None,
    step_idx: int,
    tightening_mode_active: bool,
    governing_domain_failing: bool,
    required_domain_work_active: bool,
    target_band_domain: str,
    cur_shear_failing: bool,
    governing_domain: str,
    cur_ib: bool,
    cur_eval: dict,
    mode_config: dict,
    tightening_step_count: int,
    tightening_meta: dict,
    candidate_family_depth_reached: str,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list[str],
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
) -> dict:
    raw_candidates, raw_n = _one_click_collect_actionable_guidance_candidates(
        working,
        debug_enabled=debug_enabled,
        trace_run_id=trace_run_id,
        trace_step=step_idx,
    )
    use_governing_domain_candidates = bool(
        tightening_mode_active
        or governing_domain_failing
        or required_domain_work_active
        or (
            target_band_domain == "shear"
            and cur_shear_failing
            and governing_domain == "shear"
            and not cur_ib
        )
    )
    if use_governing_domain_candidates:
        tightening_domain_candidates, tightening_meta = _generate_tightening_candidates_for_governing_domain(
            working,
            cur_eval,
            mode_config,
            tightening_step_count=tightening_step_count,
        )
        if tightening_domain_candidates:
            raw_candidates = tightening_domain_candidates + list(raw_candidates or [])
            raw_n = int(raw_n) + len(tightening_domain_candidates)
        candidate_family_depth_reached = str(tightening_meta.get("candidate_family_depth_reached") or "none")
        shear_governing_mode_active = bool(tightening_meta.get("shear_governing_mode_active", governing_domain == "shear"))
        shear_severity_band = str(tightening_meta.get("shear_severity_band") or shear_severity_band)
        shear_candidate_family_order = list(tightening_meta.get("shear_candidate_family_order") or [])
        spacing_candidates_considered = int(tightening_meta.get("spacing_candidates_considered", spacing_candidates_considered) or 0)
        leg_candidates_considered = int(tightening_meta.get("leg_candidates_considered", leg_candidates_considered) or 0)
        dia_candidates_considered = int(tightening_meta.get("dia_candidates_considered", dia_candidates_considered) or 0)
        geometry_candidates_considered_for_shear = int(
            tightening_meta.get("geometry_candidates_considered_for_shear", geometry_candidates_considered_for_shear) or 0
        )
        combined_candidates_considered_for_shear = int(
            tightening_meta.get("combined_candidates_considered_for_shear", combined_candidates_considered_for_shear) or 0
        )
    return {
        "raw_candidates": raw_candidates,
        "raw_n": raw_n,
        "use_governing_domain_candidates": use_governing_domain_candidates,
        "tightening_meta": tightening_meta,
        "candidate_family_depth_reached": candidate_family_depth_reached,
        "shear_governing_mode_active": shear_governing_mode_active,
        "shear_severity_band": shear_severity_band,
        "shear_candidate_family_order": shear_candidate_family_order,
        "spacing_candidates_considered": spacing_candidates_considered,
        "leg_candidates_considered": leg_candidates_considered,
        "dia_candidates_considered": dia_candidates_considered,
        "geometry_candidates_considered_for_shear": geometry_candidates_considered_for_shear,
        "combined_candidates_considered_for_shear": combined_candidates_considered_for_shear,
    }


def _prepare_one_click_solver_prepared_candidate_loop_state_coordinator(
    *,
    raw_candidates,
    working: dict,
    governing_domain: str,
    use_governing_domain_candidates: bool,
    cur_eval: dict,
    mode_config: dict,
) -> dict:
    prepared_candidate_state = _prepare_one_click_solver_candidates_coordinator(
        raw_candidates=raw_candidates,
        working=working,
        governing_domain=governing_domain,
        use_governing_domain_candidates=use_governing_domain_candidates,
        cur_eval=cur_eval,
        mode_config=mode_config,
    )
    return {
        "pool_labels": list(prepared_candidate_state["pool_labels"]),
        "prepared": list(prepared_candidate_state["prepared"]),
        "prepared_samples": list(prepared_candidate_state["prepared_samples"]),
        "reduction_candidates_considered": int(prepared_candidate_state["reduction_candidates_considered"]),
        "governing_family_exists": bool(prepared_candidate_state["governing_family_exists"]),
        "shear_governing_family_detected": bool(prepared_candidate_state["shear_governing_family_detected"]),
        "governing_family_exists_after_domain_fix": bool(
            prepared_candidate_state["governing_family_exists_after_domain_fix"]
        ),
        "shear_domain_prune_active": bool(prepared_candidate_state["shear_domain_prune_active"]),
        "should_apply_domain_prune": bool(prepared_candidate_state["should_apply_domain_prune"]),
        "mixed_direction_mode": prepared_candidate_state["mixed_direction_mode"],
        "growth_candidates_rejected_in_tightening": 0,
        "rejected_as_non_governing_cleanup": 0,
        "rejected_as_non_governing_shear_strengthening": 0,
        "rejected_as_non_material_improvement": 0,
        "rejected_as_no_real_change": 0,
        "rejected_as_duplicate_signature": 0,
        "rejected_as_evaluation_failed": 0,
    }


def _handle_one_click_solver_no_real_change_candidate_coordinator(
    *,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    raw_u: dict,
    direction: dict,
    working: dict,
    tightening_mode_active: bool,
    governing_domain: str,
    family_hint: str,
    rejected_as_no_real_change: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    trace_callback,
) -> dict:
    if norm_u and not _updates_match_state(working, norm_u):
        return {
            "rejected_as_no_real_change": rejected_as_no_real_change,
            "shear_remove_links_candidate_seen": shear_remove_links_candidate_seen,
            "shear_remove_links_candidate_dropped_reason": shear_remove_links_candidate_dropped_reason,
            "should_continue": False,
        }
    rejected_as_no_real_change += 1
    remove_links_probe_updates = dict(norm_u) if norm_u else dict(raw_u)
    remove_links_probe_state = dict(working)
    remove_links_probe_state.update(remove_links_probe_updates)
    if (
        governing_domain == "shear"
        and any(k in remove_links_probe_updates for k in ("lig_d", "lig_legs", "s_lig"))
        and _int_from_state(remove_links_probe_state, "lig_legs", 0) <= 0
        and _int_from_state(remove_links_probe_state, "lig_d", 0) <= 0
    ):
        shear_remove_links_candidate_seen = True
        shear_remove_links_candidate_dropped_reason = "no_real_change"
    _trace_candidate_eval_no_real_change_solver_coordinator(
        step_idx=step_idx,
        rc=rc,
        norm_u=norm_u,
        raw_u=raw_u,
        direction=direction,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        family_hint=family_hint,
        trace_callback=trace_callback,
    )
    return {
        "rejected_as_no_real_change": rejected_as_no_real_change,
        "shear_remove_links_candidate_seen": shear_remove_links_candidate_seen,
        "shear_remove_links_candidate_dropped_reason": shear_remove_links_candidate_dropped_reason,
        "should_continue": True,
    }


def _handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(
    *,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    direction: dict,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    target_domains_for_band: list[str],
    tightening_mode_active: bool,
    governing_domain: str | None,
    family_hint: str,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    trace_callback,
) -> dict:
    if governing_domain == "bending" and family_hint == "non_governing_cleanup":
        touches_shear = bool(set(norm_u) & _COMPOUND_SHEAR_UPDATE_KEYS)
        shear_cleanup_needed = _one_click_domain_needs_cleanup(cur_eval, "shear", mode_config)
        if touches_shear and not shear_cleanup_needed:
            rejected_as_non_governing_cleanup += 1
            _trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator(
                step_idx=step_idx,
                rc=rc,
                norm_u=norm_u,
                direction=direction,
                target_domains_for_band=target_domains_for_band,
                tightening_mode_active=tightening_mode_active,
                governing_domain=governing_domain,
                family_hint=family_hint,
                rejection_reason="non_governing_shear_cleanup_pruned",
                trace_callback=trace_callback,
            )
            return {
                "rejected_as_non_governing_cleanup": rejected_as_non_governing_cleanup,
                "rejected_as_non_governing_shear_strengthening": rejected_as_non_governing_shear_strengthening,
                "should_continue": True,
            }
    if governing_domain == "bending" and family_hint == "shear":
        _ov_sg = cur_eval.get("overview") or {}
        _st_sg = dict(_ov_sg.get("statuses") or {}).get("shear")
        shear_fail_for_strengthen = bool(
            _st_sg == BEAM_STATUS_FAIL or str(_st_sg or "").strip().upper() == "FAIL",
        )
        if not shear_fail_for_strengthen:
            rejected_as_non_governing_shear_strengthening += 1
            _trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator(
                step_idx=step_idx,
                rc=rc,
                norm_u=norm_u,
                direction=direction,
                target_domains_for_band=target_domains_for_band,
                tightening_mode_active=tightening_mode_active,
                governing_domain=governing_domain,
                family_hint=family_hint,
                rejection_reason="non_governing_shear_strengthening_pruned",
                trace_callback=trace_callback,
            )
            return {
                "rejected_as_non_governing_cleanup": rejected_as_non_governing_cleanup,
                "rejected_as_non_governing_shear_strengthening": rejected_as_non_governing_shear_strengthening,
                "should_continue": True,
            }
    return {
        "rejected_as_non_governing_cleanup": rejected_as_non_governing_cleanup,
        "rejected_as_non_governing_shear_strengthening": rejected_as_non_governing_shear_strengthening,
        "should_continue": False,
    }


def _handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator(
    *,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    direction: dict,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    tightening_mode_active: bool,
    governing_domain: str | None,
    family_hint: str,
    should_apply_domain_prune: bool,
    shear_domain_prune_active: bool,
    rejected_as_non_governing_cleanup: int,
    pruned_non_shear_family_count: int,
    domain_match_prune_used: bool,
    shear_prune_rule_source: str | None,
    trace_callback,
) -> dict:
    if should_apply_domain_prune:
        if governing_domain == "bending" and family_hint in (
            "shear_cleanup",
            "shear_spacing_layout_cleanup",
            "shear_adjust",
            "shear",
        ):
            rejected_as_non_governing_cleanup += 1
            _trace_candidate_eval_pre_eval_rejection_solver_coordinator(
                step_idx=step_idx,
                rc=rc,
                norm_u=norm_u,
                direction=direction,
                tightening_mode_active=True,
                governing_domain=governing_domain,
                family_hint=family_hint,
                rejection_reason="non_governing_cleanup_pruned",
                trace_callback=trace_callback,
            )
            return {
                "rejected_as_non_governing_cleanup": rejected_as_non_governing_cleanup,
                "pruned_non_shear_family_count": pruned_non_shear_family_count,
                "domain_match_prune_used": domain_match_prune_used,
                "shear_prune_rule_source": shear_prune_rule_source,
                "should_continue": True,
            }
        if governing_domain == "shear" and shear_domain_prune_active:
            shear_cleanup_candidate = bool(
                (
                    family_hint == "non_governing_cleanup"
                    or "cleanup" in family_hint
                    or family_hint.endswith("_cleanup")
                )
                and (set(norm_u) & _COMPOUND_SHEAR_UPDATE_KEYS)
                and _one_click_domain_needs_cleanup(cur_eval, "shear", mode_config)
            )
            if (
                not shear_cleanup_candidate
                and not _one_click_candidate_is_shear_governing_for_prune(
                    family_hint=family_hint,
                    norm_updates=norm_u,
                )
            ):
                rejected_as_non_governing_cleanup += 1
                pruned_non_shear_family_count += 1
                domain_match_prune_used = True
                shear_prune_rule_source = "domain_matcher"
                _trace_candidate_eval_pre_eval_rejection_solver_coordinator(
                    step_idx=step_idx,
                    rc=rc,
                    norm_u=norm_u,
                    direction=direction,
                    tightening_mode_active=True,
                    governing_domain=governing_domain,
                    family_hint=family_hint,
                    rejection_reason="shear_governing_pruned_non_shear_primary",
                    extra_fields={
                        "shear_prune_rule_source": str(shear_prune_rule_source or "domain_matcher"),
                        "domain_match_prune_used": bool(domain_match_prune_used),
                    },
                    trace_callback=trace_callback,
                )
                return {
                    "rejected_as_non_governing_cleanup": rejected_as_non_governing_cleanup,
                    "pruned_non_shear_family_count": pruned_non_shear_family_count,
                    "domain_match_prune_used": domain_match_prune_used,
                    "shear_prune_rule_source": shear_prune_rule_source,
                    "should_continue": True,
                }
    return {
        "rejected_as_non_governing_cleanup": rejected_as_non_governing_cleanup,
        "pruned_non_shear_family_count": pruned_non_shear_family_count,
        "domain_match_prune_used": domain_match_prune_used,
        "shear_prune_rule_source": shear_prune_rule_source,
        "should_continue": False,
    }


def _handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator(
    *,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    direction: dict,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    tightening_mode_active: bool,
    governing_domain: str | None,
    family_hint: str,
    rejected_as_non_governing_cleanup: int,
    trace_callback,
) -> dict:
    if governing_domain == "shear" and (
        family_hint == "non_governing_cleanup"
        or "cleanup" in family_hint
        or family_hint.endswith("_cleanup")
    ):
        touches_shear_cleanup = bool(set(norm_u) & _COMPOUND_SHEAR_UPDATE_KEYS)
        shear_cleanup_needed = _one_click_domain_needs_cleanup(cur_eval, "shear", mode_config)
        if not (touches_shear_cleanup and shear_cleanup_needed):
            rejected_as_non_governing_cleanup += 1
            _trace_candidate_eval_pre_eval_rejection_solver_coordinator(
                step_idx=step_idx,
                rc=rc,
                norm_u=norm_u,
                direction=direction,
                tightening_mode_active=tightening_mode_active,
                governing_domain=governing_domain,
                family_hint=family_hint,
                rejection_reason="shear_cleanup_family_pruned",
                trace_callback=trace_callback,
            )
            return {
                "rejected_as_non_governing_cleanup": rejected_as_non_governing_cleanup,
                "should_continue": True,
            }
    return {
        "rejected_as_non_governing_cleanup": rejected_as_non_governing_cleanup,
        "should_continue": False,
    }


def _handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator(
    *,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    direction: dict,
    tightening_mode_active: bool,
    reduction_candidates_considered: int,
    governing_domain: str | None,
    family_hint: str,
    growth_candidates_rejected_in_tightening: int,
    trace_callback,
) -> dict:
    if (
        tightening_mode_active
        and reduction_candidates_considered > 0
        and bool(direction.get("is_growth_only"))
    ):
        growth_candidates_rejected_in_tightening += 1
        _trace_candidate_eval_pre_eval_rejection_solver_coordinator(
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            direction=direction,
            tightening_mode_active=True,
            governing_domain=governing_domain,
            family_hint=family_hint,
            rejection_reason="growth_blocked_in_tightening_mode",
            trace_callback=trace_callback,
        )
        return {
            "growth_candidates_rejected_in_tightening": growth_candidates_rejected_in_tightening,
            "should_continue": True,
        }
    return {
        "growth_candidates_rejected_in_tightening": growth_candidates_rejected_in_tightening,
        "should_continue": False,
    }


def _build_one_click_solver_pre_scoring_prune_pass_result_state_coordinator(
    *,
    pre_scoring_prune_scope: dict,
) -> dict:
    return {
        "rejected_as_no_real_change": pre_scoring_prune_scope["rejected_as_no_real_change"],
        "shear_remove_links_candidate_seen": pre_scoring_prune_scope["shear_remove_links_candidate_seen"],
        "shear_remove_links_candidate_dropped_reason": pre_scoring_prune_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "rejected_as_non_governing_cleanup": pre_scoring_prune_scope["rejected_as_non_governing_cleanup"],
        "pruned_non_shear_family_count": pre_scoring_prune_scope["pruned_non_shear_family_count"],
        "domain_match_prune_used": pre_scoring_prune_scope["domain_match_prune_used"],
        "shear_prune_rule_source": pre_scoring_prune_scope["shear_prune_rule_source"],
        "growth_candidates_rejected_in_tightening": pre_scoring_prune_scope[
            "growth_candidates_rejected_in_tightening"
        ],
    }


def _run_one_click_solver_pre_scoring_prune_pass_coordinator(
    *,
    prepared: list[dict],
    step_idx: int,
    working: dict,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    tightening_mode_active: bool,
    governing_domain: str | None,
    should_apply_domain_prune: bool,
    shear_domain_prune_active: bool,
    reduction_candidates_considered: int,
    rejected_as_no_real_change: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    rejected_as_non_governing_cleanup: int,
    pruned_non_shear_family_count: int,
    domain_match_prune_used: bool,
    shear_prune_rule_source: str | None,
    growth_candidates_rejected_in_tightening: int,
    trace_callback,
) -> dict:
    for entry in prepared:
        rc = entry["rc"]
        raw_u = dict(entry["raw_u"])
        norm_u = dict(entry["norm_u"] or {})
        direction = dict(entry["direction"] or {})
        family_hint = str(entry.get("family") or "")
        raw_u = dict(rc["raw_updates"])
        no_real_change_state = _handle_one_click_solver_no_real_change_candidate_coordinator(
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            raw_u=raw_u,
            direction=direction,
            working=working,
            tightening_mode_active=tightening_mode_active,
            governing_domain=governing_domain,
            family_hint=family_hint,
            rejected_as_no_real_change=rejected_as_no_real_change,
            shear_remove_links_candidate_seen=shear_remove_links_candidate_seen,
            shear_remove_links_candidate_dropped_reason=shear_remove_links_candidate_dropped_reason,
            trace_callback=trace_callback,
        )
        rejected_as_no_real_change = no_real_change_state["rejected_as_no_real_change"]
        shear_remove_links_candidate_seen = no_real_change_state["shear_remove_links_candidate_seen"]
        shear_remove_links_candidate_dropped_reason = no_real_change_state[
            "shear_remove_links_candidate_dropped_reason"
        ]
        if no_real_change_state["should_continue"]:
            continue
        pre_scoring_domain_prune_state = _handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator(
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            direction=direction,
            cur_eval=cur_eval,
            mode_config=mode_config,
            tightening_mode_active=tightening_mode_active,
            governing_domain=governing_domain,
            family_hint=family_hint,
            should_apply_domain_prune=should_apply_domain_prune,
            shear_domain_prune_active=shear_domain_prune_active,
            rejected_as_non_governing_cleanup=rejected_as_non_governing_cleanup,
            pruned_non_shear_family_count=pruned_non_shear_family_count,
            domain_match_prune_used=domain_match_prune_used,
            shear_prune_rule_source=shear_prune_rule_source,
            trace_callback=trace_callback,
        )
        rejected_as_non_governing_cleanup = pre_scoring_domain_prune_state[
            "rejected_as_non_governing_cleanup"
        ]
        pruned_non_shear_family_count = pre_scoring_domain_prune_state[
            "pruned_non_shear_family_count"
        ]
        domain_match_prune_used = pre_scoring_domain_prune_state["domain_match_prune_used"]
        shear_prune_rule_source = pre_scoring_domain_prune_state["shear_prune_rule_source"]
        if pre_scoring_domain_prune_state["should_continue"]:
            continue
        shear_cleanup_prune_state = _handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator(
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            direction=direction,
            cur_eval=cur_eval,
            mode_config=mode_config,
            tightening_mode_active=tightening_mode_active,
            governing_domain=governing_domain,
            family_hint=family_hint,
            rejected_as_non_governing_cleanup=rejected_as_non_governing_cleanup,
            trace_callback=trace_callback,
        )
        rejected_as_non_governing_cleanup = shear_cleanup_prune_state[
            "rejected_as_non_governing_cleanup"
        ]
        if shear_cleanup_prune_state["should_continue"]:
            continue
        growth_prune_state = _handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator(
            step_idx=step_idx, rc=rc, norm_u=norm_u, direction=direction,
            tightening_mode_active=tightening_mode_active,
            reduction_candidates_considered=reduction_candidates_considered,
            governing_domain=governing_domain, family_hint=family_hint,
            growth_candidates_rejected_in_tightening=growth_candidates_rejected_in_tightening,
            trace_callback=trace_callback,
        )
        growth_candidates_rejected_in_tightening = growth_prune_state[
            "growth_candidates_rejected_in_tightening"
        ]
        if growth_prune_state["should_continue"]:
            continue
    return _build_one_click_solver_pre_scoring_prune_pass_result_state_coordinator(
        pre_scoring_prune_scope=locals(),
    )


def _prepare_one_click_solver_candidate_scalar_metric_state_coordinator(
    *,
    peval: dict,
    cur_eval: dict,
    working: dict,
    norm_u: dict,
    mode_config: OneClickModeConfig,
    governing_domain: str | None,
) -> dict:
    new_u = _candidate_objective_util(peval)
    new_d = _candidate_target_band_distance(peval, mode_config)
    old_d = _candidate_target_band_distance(cur_eval, mode_config)
    shear_preview = _shear_preview_for_updates(working, norm_u) if governing_domain == "shear" else None
    shear_util_preview = None
    web_util_preview = None
    if isinstance(shear_preview, dict):
        try:
            shear_util_preview = float(shear_preview.get("util")) if shear_preview.get("util") is not None else None
        except Exception:
            shear_util_preview = None
        try:
            web_util_preview = float(shear_preview.get("web_util")) if shear_preview.get("web_util") is not None else None
        except Exception:
            web_util_preview = None
    return {
        "new_u": new_u,
        "new_d": new_d,
        "old_d": old_d,
        "shear_preview": shear_preview,
        "remove_links_candidate": False,
        "remove_links_truth_ok": False,
        "shear_util_preview": shear_util_preview,
        "web_util_preview": web_util_preview,
    }


def _prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(
    *,
    peval: dict,
    preview: dict,
    working: dict,
    norm_u: dict,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    shear_remove_links_candidate_materiality: str,
) -> dict:
    s_now = float(_float_from_state(working, "s_lig", 0.0) or 0.0)
    s_new = float(_float_from_state(preview, "s_lig", s_now) or s_now)
    legs_new = int(_int_from_state(preview, "lig_legs", 0) or 0)
    dia_new = int(_int_from_state(preview, "lig_d", 0) or 0)
    remove_links_candidate = bool(
        any(k in norm_u for k in ("lig_d", "lig_legs", "s_lig"))
        and legs_new <= 0
        and dia_new <= 0
    )
    remove_links_truth_ok = False
    if remove_links_candidate:
        shear_remove_links_candidate_seen = True
        preview_actions = {}
        try:
            preview_ctx = _build_design_actions_context(preview)
            preview_actions = dict(preview_ctx.get("actions") or {})
        except Exception:
            preview_actions = {}
        preview_shear_util = _parse_util_value(
            ((peval.get("overview") or {}).get("utils") or {}).get("shear")
        )
        remove_links_truth_ok = bool(
            bool((peval.get("overview") or {}).get("all_key_pass"))
            and _shear_demands_negligible(preview_actions)
            and preview_shear_util is not None
            and float(preview_shear_util) <= float(GUIDANCE_SHEAR_UTIL_NEGLIGIBLE) + 1e-9
        )
        if remove_links_truth_ok:
            shear_remove_links_candidate_truth_ok = True
            shear_remove_links_candidate_materiality = "material_remove_links_truth_ok"
        else:
            shear_remove_links_candidate_dropped_reason = (
                "remove_links_truth_not_confirmed"
            )
    return {
        "s_new": s_new,
        "legs_new": legs_new,
        "dia_new": dia_new,
        "has_geometry_change": any(k in norm_u for k in ("D", "b", "bw")),
        "remove_links_candidate": remove_links_candidate,
        "remove_links_truth_ok": remove_links_truth_ok,
        "shear_remove_links_candidate_seen": shear_remove_links_candidate_seen,
        "shear_remove_links_candidate_truth_ok": shear_remove_links_candidate_truth_ok,
        "shear_remove_links_candidate_dropped_reason": shear_remove_links_candidate_dropped_reason,
        "shear_remove_links_candidate_materiality": shear_remove_links_candidate_materiality,
    }


def _handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(
    *,
    peval: dict,
    mode_config: OneClickModeConfig,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    new_d: float,
    governing_domain: str | None,
    family_hint: str,
    shear_util_preview: float | None,
    web_util_preview: float | None,
    s_new: float,
    legs_new: int,
    dia_new: int,
    has_geometry_change: bool,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    trace_callback,
) -> dict:
    if family_hint == "spacing_reduction" and shear_util_preview is not None and shear_util_preview > 1.04:
        rejected_as_spacing_too_weak += 1
        _trace_candidate_eval_shear_preview_rejection_solver_coordinator(
            peval=peval,
            mode_config=mode_config,
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            new_d=new_d,
            governing_domain=governing_domain,
            family_hint=family_hint,
            rejection_reason="spacing_too_weak_for_shear_recovery",
            trace_callback=trace_callback,
        )
        return {
            "rejected_as_spacing_too_weak": rejected_as_spacing_too_weak,
            "rejected_as_web_crushing_marginal": rejected_as_web_crushing_marginal,
            "rejected_as_impractical_shear_layout": rejected_as_impractical_shear_layout,
            "should_continue": True,
        }
    if web_util_preview is not None and web_util_preview > 0.98:
        rejected_as_web_crushing_marginal += 1
        _trace_candidate_eval_shear_preview_rejection_solver_coordinator(
            peval=peval,
            mode_config=mode_config,
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            new_d=new_d,
            governing_domain=governing_domain,
            family_hint=family_hint,
            rejection_reason="web_crushing_marginal",
            trace_callback=trace_callback,
        )
        return {
            "rejected_as_spacing_too_weak": rejected_as_spacing_too_weak,
            "rejected_as_web_crushing_marginal": rejected_as_web_crushing_marginal,
            "rejected_as_impractical_shear_layout": rejected_as_impractical_shear_layout,
            "should_continue": True,
        }
    if s_new < 90.0 and legs_new >= 6 and dia_new >= 16 and not has_geometry_change:
        rejected_as_impractical_shear_layout += 1
        _trace_candidate_eval_shear_preview_rejection_solver_coordinator(
            peval=peval,
            mode_config=mode_config,
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            new_d=new_d,
            governing_domain=governing_domain,
            family_hint=family_hint,
            rejection_reason="impractical_shear_layout",
            trace_callback=trace_callback,
        )
        return {
            "rejected_as_spacing_too_weak": rejected_as_spacing_too_weak,
            "rejected_as_web_crushing_marginal": rejected_as_web_crushing_marginal,
            "rejected_as_impractical_shear_layout": rejected_as_impractical_shear_layout,
            "should_continue": True,
        }
    return {
        "rejected_as_spacing_too_weak": rejected_as_spacing_too_weak,
        "rejected_as_web_crushing_marginal": rejected_as_web_crushing_marginal,
        "rejected_as_impractical_shear_layout": rejected_as_impractical_shear_layout,
        "should_continue": False,
    }


def _build_one_click_solver_candidate_shear_truth_preview_gate_result_state_coordinator(
    *,
    shear_truth_preview_scope: dict,
    should_continue: bool,
) -> dict:
    return {
        "remove_links_candidate": shear_truth_preview_scope["remove_links_candidate"],
        "remove_links_truth_ok": shear_truth_preview_scope["remove_links_truth_ok"],
        "shear_remove_links_candidate_seen": shear_truth_preview_scope["shear_remove_links_candidate_seen"],
        "shear_remove_links_candidate_truth_ok": shear_truth_preview_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        "shear_remove_links_candidate_dropped_reason": shear_truth_preview_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "shear_remove_links_candidate_materiality": shear_truth_preview_scope[
            "shear_remove_links_candidate_materiality"
        ],
        "rejected_as_spacing_too_weak": shear_truth_preview_scope["rejected_as_spacing_too_weak"],
        "rejected_as_web_crushing_marginal": shear_truth_preview_scope["rejected_as_web_crushing_marginal"],
        "rejected_as_impractical_shear_layout": shear_truth_preview_scope[
            "rejected_as_impractical_shear_layout"
        ],
        "should_continue": should_continue,
    }


def _handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator(
    *,
    governing_domain: str | None,
    peval: dict,
    preview: dict,
    working: dict,
    norm_u: dict,
    mode_config: OneClickModeConfig,
    step_idx: int,
    rc: dict,
    new_d: float,
    family_hint: str,
    shear_util_preview: float | None,
    web_util_preview: float | None,
    remove_links_candidate: bool,
    remove_links_truth_ok: bool,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    shear_remove_links_candidate_materiality: str,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    trace_callback,
) -> dict:
    if governing_domain != "shear":
        return _build_one_click_solver_candidate_shear_truth_preview_gate_result_state_coordinator(
            shear_truth_preview_scope=locals(),
            should_continue=False,
        )
    shear_remove_links_truth_state = (
        _prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(
            peval=peval,
            preview=preview,
            working=working,
            norm_u=norm_u,
            shear_remove_links_candidate_seen=shear_remove_links_candidate_seen,
            shear_remove_links_candidate_truth_ok=shear_remove_links_candidate_truth_ok,
            shear_remove_links_candidate_dropped_reason=(
                shear_remove_links_candidate_dropped_reason
            ),
            shear_remove_links_candidate_materiality=(
                shear_remove_links_candidate_materiality
            ),
        )
    )
    s_new = shear_remove_links_truth_state["s_new"]
    legs_new = shear_remove_links_truth_state["legs_new"]
    dia_new = shear_remove_links_truth_state["dia_new"]
    has_geometry_change = shear_remove_links_truth_state[
        "has_geometry_change"
    ]
    remove_links_candidate = shear_remove_links_truth_state[
        "remove_links_candidate"
    ]
    remove_links_truth_ok = shear_remove_links_truth_state[
        "remove_links_truth_ok"
    ]
    shear_remove_links_candidate_seen = shear_remove_links_truth_state[
        "shear_remove_links_candidate_seen"
    ]
    shear_remove_links_candidate_truth_ok = shear_remove_links_truth_state[
        "shear_remove_links_candidate_truth_ok"
    ]
    shear_remove_links_candidate_dropped_reason = shear_remove_links_truth_state[
        "shear_remove_links_candidate_dropped_reason"
    ]
    shear_remove_links_candidate_materiality = shear_remove_links_truth_state[
        "shear_remove_links_candidate_materiality"
    ]
    shear_preview_rejection_gate_state = (
        _handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(
            peval=peval,
            mode_config=mode_config,
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            new_d=new_d,
            governing_domain=governing_domain,
            family_hint=family_hint,
            shear_util_preview=shear_util_preview,
            web_util_preview=web_util_preview,
            s_new=s_new,
            legs_new=legs_new,
            dia_new=dia_new,
            has_geometry_change=has_geometry_change,
            rejected_as_spacing_too_weak=rejected_as_spacing_too_weak,
            rejected_as_web_crushing_marginal=rejected_as_web_crushing_marginal,
            rejected_as_impractical_shear_layout=(
                rejected_as_impractical_shear_layout
            ),
            trace_callback=trace_callback,
        )
    )
    rejected_as_spacing_too_weak = shear_preview_rejection_gate_state[
        "rejected_as_spacing_too_weak"
    ]
    rejected_as_web_crushing_marginal = shear_preview_rejection_gate_state[
        "rejected_as_web_crushing_marginal"
    ]
    rejected_as_impractical_shear_layout = shear_preview_rejection_gate_state[
        "rejected_as_impractical_shear_layout"
    ]
    return _build_one_click_solver_candidate_shear_truth_preview_gate_result_state_coordinator(
        shear_truth_preview_scope=locals(),
        should_continue=bool(shear_preview_rejection_gate_state["should_continue"]),
    )


def _handle_one_click_solver_candidate_wrong_direction_gate_coordinator(
    *,
    peval: dict,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    new_u: float,
    cur_u: float,
    new_d: float,
    old_d: float,
    direction: dict,
    governing_domain: str | None,
    family_hint: str,
    tightening_mode_active: bool,
    growth_candidates_rejected_in_tightening: int,
    trace_callback,
) -> dict:
    multi_domain_step_improves = bool(
        (_candidate_target_domains_for_band(cur_eval) or _candidate_target_domains_for_band(peval))
        and _one_click_step_improves(peval, cur_eval, mode_config)
    )
    preview_pass = bool((peval.get("overview") or {}).get("all_key_pass"))
    all_pass_band_distance_improves = bool(
        preview_pass
        and math.isfinite(old_d)
        and math.isfinite(new_d)
        and new_d < old_d - 1e-6
    )
    if (
        tightening_mode_active
        and new_u < cur_u - 1e-6
        and not multi_domain_step_improves
        and not all_pass_band_distance_improves
    ):
        growth_candidates_rejected_in_tightening += 1
        _trace_candidate_eval_wrong_direction_solver_coordinator(
            peval=peval,
            mode_config=mode_config,
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            new_d=new_d,
            direction=direction,
            governing_domain=governing_domain,
            family_hint=family_hint,
            multi_domain_step_improves=multi_domain_step_improves,
            all_pass_band_distance_improves=all_pass_band_distance_improves,
            trace_callback=trace_callback,
        )
        return {
            "growth_candidates_rejected_in_tightening": growth_candidates_rejected_in_tightening,
            "multi_domain_step_improves": multi_domain_step_improves,
            "all_pass_band_distance_improves": all_pass_band_distance_improves,
            "should_continue": True,
        }
    return {
        "growth_candidates_rejected_in_tightening": growth_candidates_rejected_in_tightening,
        "multi_domain_step_improves": multi_domain_step_improves,
        "all_pass_band_distance_improves": all_pass_band_distance_improves,
        "should_continue": False,
    }


def _handle_one_click_solver_candidate_non_material_gate_coordinator(
    *,
    peval: dict,
    mode_config: OneClickModeConfig,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    new_d: float,
    old_d: float,
    direction: dict,
    governing_domain: str | None,
    family_hint: str,
    tightening_mode_active: bool,
    material_improvement_threshold: float,
    remove_links_candidate: bool,
    remove_links_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    shear_remove_links_candidate_materiality: str,
    rejected_as_non_material_improvement: int,
    trace_callback,
) -> dict:
    if tightening_mode_active and (old_d - new_d) < material_improvement_threshold:
        if not (governing_domain == "shear" and remove_links_candidate and remove_links_truth_ok):
            if governing_domain == "shear" and remove_links_candidate:
                shear_remove_links_candidate_dropped_reason = "non_material_improvement"
                if shear_remove_links_candidate_materiality == "not_evaluated":
                    shear_remove_links_candidate_materiality = "non_material"
            rejected_as_non_material_improvement += 1
            _trace_candidate_eval_non_material_solver_coordinator(
                peval=peval,
                mode_config=mode_config,
                step_idx=step_idx,
                rc=rc,
                norm_u=norm_u,
                new_d=new_d,
                direction=direction,
                governing_domain=governing_domain,
                family_hint=family_hint,
                trace_callback=trace_callback,
            )
            return {
                "rejected_as_non_material_improvement": rejected_as_non_material_improvement,
                "shear_remove_links_candidate_dropped_reason": shear_remove_links_candidate_dropped_reason,
                "shear_remove_links_candidate_materiality": shear_remove_links_candidate_materiality,
                "should_continue": True,
            }
    return {
        "rejected_as_non_material_improvement": rejected_as_non_material_improvement,
        "shear_remove_links_candidate_dropped_reason": shear_remove_links_candidate_dropped_reason,
        "shear_remove_links_candidate_materiality": shear_remove_links_candidate_materiality,
        "should_continue": False,
    }


def _handle_one_click_solver_candidate_direction_material_gate_chain_coordinator(
    *,
    peval: dict,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    new_u: float,
    cur_u: float,
    new_d: float,
    old_d: float,
    direction: dict,
    governing_domain: str | None,
    family_hint: str,
    tightening_mode_active: bool,
    growth_candidates_rejected_in_tightening: int,
    material_improvement_threshold: float,
    remove_links_candidate: bool,
    remove_links_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    shear_remove_links_candidate_materiality: str,
    rejected_as_non_material_improvement: int,
    trace_callback,
) -> dict:
    wrong_direction_gate_state = (
        _handle_one_click_solver_candidate_wrong_direction_gate_coordinator(
            peval=peval,
            cur_eval=cur_eval,
            mode_config=mode_config,
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            new_u=new_u,
            cur_u=cur_u,
            new_d=new_d,
            old_d=old_d,
            direction=direction,
            governing_domain=governing_domain,
            family_hint=family_hint,
            tightening_mode_active=tightening_mode_active,
            growth_candidates_rejected_in_tightening=(
                growth_candidates_rejected_in_tightening
            ),
            trace_callback=trace_callback,
        )
    )
    growth_candidates_rejected_in_tightening = wrong_direction_gate_state[
        "growth_candidates_rejected_in_tightening"
    ]
    if wrong_direction_gate_state["should_continue"]:
        return {
            "growth_candidates_rejected_in_tightening": growth_candidates_rejected_in_tightening,
            "rejected_as_non_material_improvement": rejected_as_non_material_improvement,
            "shear_remove_links_candidate_dropped_reason": shear_remove_links_candidate_dropped_reason,
            "shear_remove_links_candidate_materiality": shear_remove_links_candidate_materiality,
            "should_continue": True,
        }
    non_material_gate_state = (
        _handle_one_click_solver_candidate_non_material_gate_coordinator(
            peval=peval,
            mode_config=mode_config,
            step_idx=step_idx,
            rc=rc,
            norm_u=norm_u,
            new_d=new_d,
            old_d=old_d,
            direction=direction,
            governing_domain=governing_domain,
            family_hint=family_hint,
            tightening_mode_active=tightening_mode_active,
            material_improvement_threshold=material_improvement_threshold,
            remove_links_candidate=remove_links_candidate,
            remove_links_truth_ok=remove_links_truth_ok,
            shear_remove_links_candidate_dropped_reason=(
                shear_remove_links_candidate_dropped_reason
            ),
            shear_remove_links_candidate_materiality=(
                shear_remove_links_candidate_materiality
            ),
            rejected_as_non_material_improvement=(
                rejected_as_non_material_improvement
            ),
            trace_callback=trace_callback,
        )
    )
    rejected_as_non_material_improvement = non_material_gate_state[
        "rejected_as_non_material_improvement"
    ]
    shear_remove_links_candidate_dropped_reason = non_material_gate_state[
        "shear_remove_links_candidate_dropped_reason"
    ]
    shear_remove_links_candidate_materiality = non_material_gate_state[
        "shear_remove_links_candidate_materiality"
    ]
    return {
        "growth_candidates_rejected_in_tightening": growth_candidates_rejected_in_tightening,
        "rejected_as_non_material_improvement": rejected_as_non_material_improvement,
        "shear_remove_links_candidate_dropped_reason": shear_remove_links_candidate_dropped_reason,
        "shear_remove_links_candidate_materiality": shear_remove_links_candidate_materiality,
        "should_continue": non_material_gate_state["should_continue"],
    }


def _build_one_click_solver_candidate_scoring_state_result_coordinator(
    *,
    scoring_state_scope: dict,
) -> dict:
    return {
        "okp": scoring_state_scope["okp"],
        "nib": scoring_state_scope["nib"],
        "tier": scoring_state_scope["tier"],
        "has_target_domains": scoring_state_scope["has_target_domains"],
        "new_max": scoring_state_scope["new_max"],
        "new_total": scoring_state_scope["new_total"],
        "prefer_total_before_max": scoring_state_scope["prefer_total_before_max"],
        "domain_progress": scoring_state_scope["domain_progress"],
        "required_fail_count": scoring_state_scope["required_fail_count"],
        "required_unsatisfied_count": scoring_state_scope["required_unsatisfied_count"],
        "mixed_rank": scoring_state_scope["mixed_rank"],
        "mixed_sort_prefix": scoring_state_scope["mixed_sort_prefix"],
        "sort_key": scoring_state_scope["sort_key"],
        "dk": scoring_state_scope["dk"],
        "web_crushing_penalty_applied": scoring_state_scope[
            "web_crushing_penalty_applied"
        ],
    }


def _prepare_one_click_solver_candidate_sorting_state_coordinator(
    *,
    scoring_state_scope: dict,
) -> dict:
    peval = scoring_state_scope["peval"]
    cur_eval = scoring_state_scope["cur_eval"]
    preview = scoring_state_scope["preview"]
    mode_config = scoring_state_scope["mode_config"]
    rc = scoring_state_scope["rc"]
    norm_u = scoring_state_scope["norm_u"]
    direction = scoring_state_scope["direction"]
    new_u = scoring_state_scope["new_u"]
    cur_u = scoring_state_scope["cur_u"]
    new_d = scoring_state_scope["new_d"]
    mixed_direction_mode = scoring_state_scope["mixed_direction_mode"]
    tightening_mode_active = scoring_state_scope["tightening_mode_active"]
    governing_domain = scoring_state_scope["governing_domain"]
    family_hint = scoring_state_scope["family_hint"]
    shear_util_preview = scoring_state_scope["shear_util_preview"]
    web_util_preview = scoring_state_scope["web_util_preview"]
    has_target_domains = scoring_state_scope["has_target_domains"]
    tier = scoring_state_scope["tier"]
    new_max = scoring_state_scope["new_max"]
    new_total = scoring_state_scope["new_total"]
    domain_progress = scoring_state_scope["domain_progress"]
    required_fail_count = scoring_state_scope["required_fail_count"]
    required_unsatisfied_count = scoring_state_scope["required_unsatisfied_count"]
    prefer_total_before_max = scoring_state_scope["prefer_total_before_max"]
    web_crushing_penalty_applied = scoring_state_scope[
        "web_crushing_penalty_applied"
    ]
    mixed_rank = _one_click_mixed_direction_rank_adjustment(
        cur_eval, peval, mixed_direction_mode, mode_config
    )
    mixed_sort_prefix = (
        (
            0 if bool(mixed_rank.get("primary_material_improvement")) else 1,
            float(mixed_rank.get("primary_distance", float("inf"))),
            float(mixed_rank.get("secondary_distance", float("inf"))),
        )
        if bool(mixed_rank.get("active"))
        else tuple()
    )
    if tightening_mode_active:
        wrong_dir_penalty = 0.0 if new_u >= cur_u - 1e-9 else float(cur_u - new_u)
        reduction_bias = 0 if bool(direction.get("is_reduction_candidate")) else 1
        shear_sort_util = float("inf")
        web_sort_util = float("inf")
        practical_spacing_penalty = 0
        congestion_penalty = 0
        goal_bias = 0
        if governing_domain == "shear":
            shear_sort_util = float(shear_util_preview) if shear_util_preview is not None else float("inf")
            web_sort_util = float(web_util_preview) if web_util_preview is not None else float("inf")
            if web_sort_util > 0.9:
                web_crushing_penalty_applied += 1
            shear_candidate_type = str(rc.get("_shear_candidate_type") or "")
            practical_spacing_penalty = 1 if (
                shear_candidate_type == "spacing"
                and float(_float_from_state(preview, "s_lig", 0.0) or 0.0) <= 100.0
            ) else 0
            congestion_penalty = int(float(peval.get("reo_congestion_index", 0.0) or 0.0) > 2.2)
            goal = _design_optimisation_goal(preview)
            if goal == "less_shear_reinforcement" and family_hint in ("more_legs", "larger_dia"):
                goal_bias = 1
            if goal == "shallower_beam" and family_hint == "depth_increase":
                goal_bias = 1
            domain_progress = _one_click_required_domain_progress(peval, mode_config) if has_target_domains else {}
            required_fail_count = int(domain_progress.get("required_fail_count", 0) or 0)
            required_unsatisfied_count = int(domain_progress.get("required_unsatisfied_count", 0) or 0)
        sort_key = _resolve_target_band_candidate_sort_key(
            tier=tier,
            mixed_sort_prefix=mixed_sort_prefix,
            tightening_mode_active=True,
            governing_domain=governing_domain,
            has_target_domains=has_target_domains,
            new_max=new_max,
            new_total=new_total,
            required_fail_count=required_fail_count,
            required_unsatisfied_count=required_unsatisfied_count,
            prefer_total_before_max=prefer_total_before_max,
            shear_sort_util=shear_sort_util,
            web_sort_util=web_sort_util,
            practical_spacing_penalty=practical_spacing_penalty,
            congestion_penalty=congestion_penalty,
            goal_bias=goal_bias,
            new_distance=new_d,
            wrong_dir_penalty=wrong_dir_penalty,
            reduction_bias=reduction_bias,
            update_count=len(norm_u),
        )
        dk = wrong_dir_penalty
    else:
        dk = _one_click_directional_tie_key(cur_u, new_u, mode_config)
        sort_key = _resolve_target_band_candidate_sort_key(
            tier=tier,
            mixed_sort_prefix=mixed_sort_prefix,
            tightening_mode_active=False,
            governing_domain=governing_domain,
            has_target_domains=has_target_domains,
            new_max=new_max,
            new_total=new_total,
            required_fail_count=required_fail_count,
            required_unsatisfied_count=required_unsatisfied_count,
            prefer_total_before_max=prefer_total_before_max,
            new_distance=new_d,
            directional_tie_key=dk,
            update_count=len(norm_u),
        )
    return {
        "domain_progress": domain_progress,
        "required_fail_count": required_fail_count,
        "required_unsatisfied_count": required_unsatisfied_count,
        "mixed_rank": mixed_rank,
        "mixed_sort_prefix": mixed_sort_prefix,
        "sort_key": sort_key,
        "dk": dk,
        "web_crushing_penalty_applied": web_crushing_penalty_applied,
    }


def _prepare_one_click_solver_candidate_scoring_state_coordinator(
    *,
    peval: dict,
    cur_eval: dict,
    preview: dict,
    mode_config: OneClickModeConfig,
    rc: dict,
    norm_u: dict,
    direction: dict,
    new_u: float,
    cur_u: float,
    new_d: float,
    mixed_direction_mode: bool,
    tightening_mode_active: bool,
    governing_domain: str | None,
    family_hint: str,
    shear_util_preview: float | None,
    web_util_preview: float | None,
    cur_has_td: bool,
    cur_required_fail_count: int,
    cur_required_unsatisfied_count: int,
    web_crushing_penalty_applied: int,
) -> dict:
    okp = bool((peval.get("overview") or {}).get("all_key_pass"))
    nib = _candidate_in_target_band(peval, mode_config)
    tier = 0 if (okp and nib) else 1
    has_target_domains = bool(_candidate_target_domains_for_band(peval))
    new_max = _one_click_domain_max_distance(peval, mode_config) if has_target_domains else None
    new_total = _one_click_domain_total_distance(peval, mode_config) if has_target_domains else None
    prefer_total_before_max = False
    if has_target_domains and okp and not mixed_direction_mode:
        domain_progress = _one_click_required_domain_progress(peval, mode_config)
        required_fail_count = int(domain_progress.get("required_fail_count", 0) or 0)
        required_unsatisfied_count = int(domain_progress.get("required_unsatisfied_count", 0) or 0)
        prefer_total_before_max = bool(
            cur_has_td
            and bool((cur_eval.get("overview") or {}).get("all_key_pass"))
            and cur_required_fail_count == 0
            and required_fail_count == 0
            and cur_required_unsatisfied_count > 1
            and required_unsatisfied_count > 1
            and len(_candidate_target_domains_for_band(peval) or []) > 1
        )
    else:
        domain_progress = _one_click_required_domain_progress(peval, mode_config) if has_target_domains else {}
        required_fail_count = int(domain_progress.get("required_fail_count", 0) or 0)
        required_unsatisfied_count = int(domain_progress.get("required_unsatisfied_count", 0) or 0)
    sorting_state = _prepare_one_click_solver_candidate_sorting_state_coordinator(
        scoring_state_scope=locals(),
    )
    domain_progress = sorting_state["domain_progress"]
    required_fail_count = sorting_state["required_fail_count"]
    required_unsatisfied_count = sorting_state["required_unsatisfied_count"]
    mixed_rank = sorting_state["mixed_rank"]
    mixed_sort_prefix = sorting_state["mixed_sort_prefix"]
    sort_key = sorting_state["sort_key"]
    dk = sorting_state["dk"]
    web_crushing_penalty_applied = sorting_state[
        "web_crushing_penalty_applied"
    ]
    return _build_one_click_solver_candidate_scoring_state_result_coordinator(
        scoring_state_scope=locals(),
    )


def _handle_one_click_solver_candidate_scored_append_trace_coordinator(
    *,
    scored: list[dict],
    peval: dict,
    mode_config: OneClickModeConfig,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    psig,
    new_d: float,
    sort_key,
    nib: bool,
    tier,
    domain_progress: dict,
    has_target_domains: bool,
    dk,
    mixed_direction_mode: bool,
    mixed_rank: dict,
    tightening_mode_active: bool,
    direction: dict,
    governing_domain: str | None,
    family_hint: str,
    material_improvement_threshold: float,
    trace_callback,
) -> dict:
    ap = rc["item"].get("action_payload") if isinstance(rc["item"].get("action_payload"), dict) else {}
    summary = str(ap.get("guidance_change_summary_compact") or "").strip() or None
    scored.append(
        {
            "sort_key": sort_key,
            "eval": peval,
            "updates": dict(norm_u),
            "label": rc["title"],
            "action_type": rc["action_type"],
            "signature": psig,
            "change_summary": summary,
            "worst_util": float((peval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
        },
    )
    _trace_candidate_eval_scored_solver_coordinator(
        peval=peval,
        mode_config=mode_config,
        step_idx=step_idx,
        rc=rc,
        norm_u=norm_u,
        nib=nib,
        new_d=new_d,
        sort_key=sort_key,
        tier=tier,
        domain_progress=domain_progress,
        has_target_domains=has_target_domains,
        dk=dk,
        mixed_direction_mode=mixed_direction_mode,
        mixed_rank=mixed_rank,
        tightening_mode_active=tightening_mode_active,
        direction=direction,
        governing_domain=governing_domain,
        family_hint=family_hint,
        material_improvement_threshold=material_improvement_threshold,
        trace_callback=trace_callback,
    )
    return {"scored": scored}


def _handle_one_click_solver_candidate_scored_assembly_chain_coordinator(
    *,
    scored: list[dict],
    peval: dict,
    cur_eval: dict,
    preview: dict,
    mode_config: OneClickModeConfig,
    step_idx: int,
    rc: dict,
    norm_u: dict,
    direction: dict,
    psig,
    new_u: float,
    cur_u: float,
    new_d: float,
    mixed_direction_mode,
    tightening_mode_active: bool,
    governing_domain: str | None,
    family_hint: str,
    shear_util_preview: float | None,
    web_util_preview: float | None,
    cur_has_td: bool,
    cur_required_fail_count: int,
    cur_required_unsatisfied_count: int,
    web_crushing_penalty_applied: int,
    material_improvement_threshold: float,
    trace_callback,
) -> dict:
    scoring_state = _prepare_one_click_solver_candidate_scoring_state_coordinator(
        peval=peval,
        cur_eval=cur_eval,
        preview=preview,
        mode_config=mode_config,
        rc=rc,
        norm_u=norm_u,
        direction=direction,
        new_u=new_u,
        cur_u=cur_u,
        new_d=new_d,
        mixed_direction_mode=mixed_direction_mode,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        family_hint=family_hint,
        shear_util_preview=shear_util_preview,
        web_util_preview=web_util_preview,
        cur_has_td=cur_has_td,
        cur_required_fail_count=cur_required_fail_count,
        cur_required_unsatisfied_count=cur_required_unsatisfied_count,
        web_crushing_penalty_applied=web_crushing_penalty_applied,
    )
    nib = scoring_state["nib"]
    tier = scoring_state["tier"]
    has_target_domains = scoring_state["has_target_domains"]
    domain_progress = scoring_state["domain_progress"]
    mixed_rank = scoring_state["mixed_rank"]
    sort_key = scoring_state["sort_key"]
    dk = scoring_state["dk"]
    web_crushing_penalty_applied = scoring_state["web_crushing_penalty_applied"]
    scored_append_trace_state = _handle_one_click_solver_candidate_scored_append_trace_coordinator(
        scored=scored,
        peval=peval,
        mode_config=mode_config,
        step_idx=step_idx,
        rc=rc,
        norm_u=norm_u,
        psig=psig,
        new_d=new_d,
        sort_key=sort_key,
        nib=nib,
        tier=tier,
        domain_progress=domain_progress,
        has_target_domains=has_target_domains,
        dk=dk,
        mixed_direction_mode=mixed_direction_mode,
        mixed_rank=mixed_rank,
        tightening_mode_active=tightening_mode_active,
        direction=direction,
        governing_domain=governing_domain,
        family_hint=family_hint,
        material_improvement_threshold=material_improvement_threshold,
        trace_callback=trace_callback,
    )
    return {
        "scored": scored_append_trace_state["scored"],
        "web_crushing_penalty_applied": web_crushing_penalty_applied,
    }


def _build_one_click_solver_single_candidate_pre_metric_result_state_coordinator(
    *,
    pre_metric_scope: dict,
    peval=None,
    preview=None,
    psig=None,
    should_continue: bool = False,
) -> dict:
    return {
        "rc": pre_metric_scope["rc"],
        "raw_u": pre_metric_scope["raw_u"],
        "norm_u": pre_metric_scope["norm_u"],
        "direction": pre_metric_scope["direction"],
        "family_hint": pre_metric_scope["family_hint"],
        "peval": peval,
        "preview": preview,
        "psig": psig,
        "rejected_as_non_governing_cleanup": pre_metric_scope["rejected_as_non_governing_cleanup"],
        "rejected_as_non_governing_shear_strengthening": pre_metric_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        "rejected_as_evaluation_failed": pre_metric_scope["rejected_as_evaluation_failed"],
        "rejected_as_duplicate_signature": pre_metric_scope["rejected_as_duplicate_signature"],
        "should_continue": should_continue,
    }


def _run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator(
    *,
    entry: dict,
    step_idx: int,
    working: dict,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    target_domains_for_band: list[str],
    tightening_mode_active: bool,
    governing_domain: str | None,
    cur_shear_failing: bool,
    target_band_domain: str | None,
    seen_sigs: set,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    rejected_as_evaluation_failed: int,
    rejected_as_duplicate_signature: int,
    trace_callback,
) -> dict:
    rc = entry["rc"]
    raw_u = dict(entry["raw_u"])
    norm_u = dict(entry["norm_u"] or {})
    direction = dict(entry["direction"] or {})
    family_hint = str(entry.get("family") or "")
    domain_prune_state = _handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(
        step_idx=step_idx,
        rc=rc,
        norm_u=norm_u,
        direction=direction,
        cur_eval=cur_eval,
        mode_config=mode_config,
        target_domains_for_band=target_domains_for_band,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        family_hint=family_hint,
        rejected_as_non_governing_cleanup=rejected_as_non_governing_cleanup,
        rejected_as_non_governing_shear_strengthening=rejected_as_non_governing_shear_strengthening,
        trace_callback=trace_callback,
    )
    rejected_as_non_governing_cleanup = domain_prune_state[
        "rejected_as_non_governing_cleanup"
    ]
    rejected_as_non_governing_shear_strengthening = domain_prune_state[
        "rejected_as_non_governing_shear_strengthening"
    ]
    if domain_prune_state["should_continue"]:
        return _build_one_click_solver_single_candidate_pre_metric_result_state_coordinator(
            pre_metric_scope=locals(),
            should_continue=True,
        )

    preview_eval_state = _prepare_one_click_solver_candidate_preview_eval_state_coordinator(
        step_idx=step_idx,
        rc=rc,
        norm_u=norm_u,
        direction=direction,
        working=working,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        family_hint=family_hint,
        rejected_as_evaluation_failed=rejected_as_evaluation_failed,
        trace_callback=trace_callback,
    )
    peval = preview_eval_state["peval"]
    preview = preview_eval_state["preview"]
    rejected_as_evaluation_failed = preview_eval_state["rejected_as_evaluation_failed"]
    if preview_eval_state["should_continue"]:
        return _build_one_click_solver_single_candidate_pre_metric_result_state_coordinator(
            pre_metric_scope=locals(),
            peval=peval,
            preview=preview,
            should_continue=True,
        )

    target_domain_state = _prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator(
        peval=peval,
        norm_u=norm_u,
        target_domains_for_band=target_domains_for_band,
        mode_config=mode_config,
        target_band_domain=target_band_domain,
        cur_shear_failing=cur_shear_failing,
    )
    peval = target_domain_state["peval"]
    duplicate_signature_state = _handle_one_click_solver_duplicate_signature_candidate_coordinator(
        peval=peval,
        mode_config=mode_config,
        seen_sigs=seen_sigs,
        step_idx=step_idx,
        rc=rc,
        norm_u=norm_u,
        direction=direction,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        family_hint=family_hint,
        rejected_as_duplicate_signature=rejected_as_duplicate_signature,
        trace_callback=trace_callback,
    )
    psig = duplicate_signature_state["psig"]
    rejected_as_duplicate_signature = duplicate_signature_state[
        "rejected_as_duplicate_signature"
    ]
    if duplicate_signature_state["should_continue"]:
        return _build_one_click_solver_single_candidate_pre_metric_result_state_coordinator(
            pre_metric_scope=locals(),
            peval=peval,
            preview=preview,
            psig=psig,
            should_continue=True,
        )

    return _build_one_click_solver_single_candidate_pre_metric_result_state_coordinator(
        pre_metric_scope=locals(),
        peval=peval,
        preview=preview,
        psig=psig,
    )


def _build_one_click_solver_single_candidate_post_metric_scoring_result_state_coordinator(
    *,
    post_metric_scope: dict,
) -> dict:
    return {
        "scored": post_metric_scope["scored"],
        "rejected_as_non_governing_cleanup": post_metric_scope[
            "rejected_as_non_governing_cleanup"
        ],
        "rejected_as_non_governing_shear_strengthening": post_metric_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        "rejected_as_evaluation_failed": post_metric_scope[
            "rejected_as_evaluation_failed"
        ],
        "rejected_as_duplicate_signature": post_metric_scope[
            "rejected_as_duplicate_signature"
        ],
        "rejected_as_non_material_improvement": post_metric_scope[
            "rejected_as_non_material_improvement"
        ],
        "growth_candidates_rejected_in_tightening": post_metric_scope[
            "growth_candidates_rejected_in_tightening"
        ],
        "shear_remove_links_candidate_seen": post_metric_scope[
            "shear_remove_links_candidate_seen"
        ],
        "shear_remove_links_candidate_truth_ok": post_metric_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        "shear_remove_links_candidate_dropped_reason": post_metric_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "shear_remove_links_candidate_materiality": post_metric_scope[
            "shear_remove_links_candidate_materiality"
        ],
        "rejected_as_spacing_too_weak": post_metric_scope[
            "rejected_as_spacing_too_weak"
        ],
        "rejected_as_web_crushing_marginal": post_metric_scope[
            "rejected_as_web_crushing_marginal"
        ],
        "rejected_as_impractical_shear_layout": post_metric_scope[
            "rejected_as_impractical_shear_layout"
        ],
        "web_crushing_penalty_applied": post_metric_scope[
            "web_crushing_penalty_applied"
        ],
    }


def _dispatch_one_click_solver_candidate_shear_truth_preview_gate_from_post_metric_coordinator(
    *,
    post_metric_scope: dict,
) -> dict:
    return _handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator(
        governing_domain=post_metric_scope["governing_domain"],
        peval=post_metric_scope["peval"],
        preview=post_metric_scope["preview"],
        working=post_metric_scope["working"],
        norm_u=post_metric_scope["norm_u"],
        mode_config=post_metric_scope["mode_config"],
        step_idx=post_metric_scope["step_idx"],
        rc=post_metric_scope["rc"],
        new_d=post_metric_scope["new_d"],
        family_hint=post_metric_scope["family_hint"],
        shear_util_preview=post_metric_scope["shear_util_preview"],
        web_util_preview=post_metric_scope["web_util_preview"],
        remove_links_candidate=post_metric_scope["remove_links_candidate"],
        remove_links_truth_ok=post_metric_scope["remove_links_truth_ok"],
        shear_remove_links_candidate_seen=post_metric_scope[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_truth_ok=post_metric_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        shear_remove_links_candidate_dropped_reason=post_metric_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        shear_remove_links_candidate_materiality=post_metric_scope[
            "shear_remove_links_candidate_materiality"
        ],
        rejected_as_spacing_too_weak=post_metric_scope["rejected_as_spacing_too_weak"],
        rejected_as_web_crushing_marginal=post_metric_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=post_metric_scope[
            "rejected_as_impractical_shear_layout"
        ],
        trace_callback=post_metric_scope["trace_callback"],
    )


def _dispatch_one_click_solver_candidate_direction_material_gate_chain_from_post_metric_coordinator(
    *,
    post_metric_scope: dict,
) -> dict:
    return _handle_one_click_solver_candidate_direction_material_gate_chain_coordinator(
        peval=post_metric_scope["peval"],
        cur_eval=post_metric_scope["cur_eval"],
        mode_config=post_metric_scope["mode_config"],
        step_idx=post_metric_scope["step_idx"],
        rc=post_metric_scope["rc"],
        norm_u=post_metric_scope["norm_u"],
        new_u=post_metric_scope["new_u"],
        cur_u=post_metric_scope["cur_u"],
        new_d=post_metric_scope["new_d"],
        old_d=post_metric_scope["old_d"],
        direction=post_metric_scope["direction"],
        governing_domain=post_metric_scope["governing_domain"],
        family_hint=post_metric_scope["family_hint"],
        tightening_mode_active=post_metric_scope["tightening_mode_active"],
        growth_candidates_rejected_in_tightening=post_metric_scope[
            "growth_candidates_rejected_in_tightening"
        ],
        material_improvement_threshold=post_metric_scope[
            "material_improvement_threshold"
        ],
        remove_links_candidate=post_metric_scope["remove_links_candidate"],
        remove_links_truth_ok=post_metric_scope["remove_links_truth_ok"],
        shear_remove_links_candidate_dropped_reason=post_metric_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        shear_remove_links_candidate_materiality=post_metric_scope[
            "shear_remove_links_candidate_materiality"
        ],
        rejected_as_non_material_improvement=post_metric_scope[
            "rejected_as_non_material_improvement"
        ],
        trace_callback=post_metric_scope["trace_callback"],
    )


def _dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator(
    *,
    post_metric_scope: dict,
) -> dict:
    return _handle_one_click_solver_candidate_scored_assembly_chain_coordinator(
        scored=post_metric_scope["scored"],
        peval=post_metric_scope["peval"],
        cur_eval=post_metric_scope["cur_eval"],
        preview=post_metric_scope["preview"],
        mode_config=post_metric_scope["mode_config"],
        step_idx=post_metric_scope["step_idx"],
        rc=post_metric_scope["rc"],
        norm_u=post_metric_scope["norm_u"],
        direction=post_metric_scope["direction"],
        psig=post_metric_scope["psig"],
        new_u=post_metric_scope["new_u"],
        cur_u=post_metric_scope["cur_u"],
        new_d=post_metric_scope["new_d"],
        mixed_direction_mode=post_metric_scope["mixed_direction_mode"],
        tightening_mode_active=post_metric_scope["tightening_mode_active"],
        governing_domain=post_metric_scope["governing_domain"],
        family_hint=post_metric_scope["family_hint"],
        shear_util_preview=post_metric_scope["shear_util_preview"],
        web_util_preview=post_metric_scope["web_util_preview"],
        cur_has_td=post_metric_scope["cur_has_td"],
        cur_required_fail_count=post_metric_scope["cur_required_fail_count"],
        cur_required_unsatisfied_count=post_metric_scope[
            "cur_required_unsatisfied_count"
        ],
        web_crushing_penalty_applied=post_metric_scope[
            "web_crushing_penalty_applied"
        ],
        material_improvement_threshold=post_metric_scope[
            "material_improvement_threshold"
        ],
        trace_callback=post_metric_scope["trace_callback"],
    )


def _prepare_one_click_solver_single_candidate_post_metric_scalar_state_coordinator(
    *,
    post_metric_scope: dict,
) -> dict:
    return _prepare_one_click_solver_candidate_scalar_metric_state_coordinator(
        peval=post_metric_scope["peval"],
        cur_eval=post_metric_scope["cur_eval"],
        working=post_metric_scope["working"],
        norm_u=post_metric_scope["norm_u"],
        mode_config=post_metric_scope["mode_config"],
        governing_domain=post_metric_scope["governing_domain"],
    )


def _run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator(
    *,
    rc: dict,
    step_idx: int,
    norm_u: dict,
    direction: dict,
    family_hint: str,
    peval: dict,
    preview: dict,
    psig,
    working: dict,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    tightening_mode_active: bool,
    governing_domain: str | None,
    cur_u: float,
    mixed_direction_mode,
    cur_has_td: bool,
    cur_required_fail_count: int,
    cur_required_unsatisfied_count: int,
    material_improvement_threshold: float,
    scored: list[dict],
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    rejected_as_evaluation_failed: int,
    rejected_as_duplicate_signature: int,
    rejected_as_non_material_improvement: int,
    growth_candidates_rejected_in_tightening: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    shear_remove_links_candidate_materiality: str,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    web_crushing_penalty_applied: int,
    trace_callback,
) -> dict:
    scalar_metric_state = (
        _prepare_one_click_solver_single_candidate_post_metric_scalar_state_coordinator(
            post_metric_scope=locals(),
        )
    )
    new_u = scalar_metric_state["new_u"]
    new_d = scalar_metric_state["new_d"]
    old_d = scalar_metric_state["old_d"]
    remove_links_candidate = scalar_metric_state["remove_links_candidate"]
    remove_links_truth_ok = scalar_metric_state["remove_links_truth_ok"]
    shear_util_preview = scalar_metric_state["shear_util_preview"]
    web_util_preview = scalar_metric_state["web_util_preview"]
    shear_truth_preview_gate_state = (
        _dispatch_one_click_solver_candidate_shear_truth_preview_gate_from_post_metric_coordinator(
            post_metric_scope=locals(),
        )
    )
    remove_links_candidate = shear_truth_preview_gate_state["remove_links_candidate"]
    remove_links_truth_ok = shear_truth_preview_gate_state["remove_links_truth_ok"]
    shear_remove_links_candidate_seen = shear_truth_preview_gate_state[
        "shear_remove_links_candidate_seen"
    ]
    shear_remove_links_candidate_truth_ok = shear_truth_preview_gate_state[
        "shear_remove_links_candidate_truth_ok"
    ]
    shear_remove_links_candidate_dropped_reason = shear_truth_preview_gate_state[
        "shear_remove_links_candidate_dropped_reason"
    ]
    shear_remove_links_candidate_materiality = shear_truth_preview_gate_state[
        "shear_remove_links_candidate_materiality"
    ]
    rejected_as_spacing_too_weak = shear_truth_preview_gate_state[
        "rejected_as_spacing_too_weak"
    ]
    rejected_as_web_crushing_marginal = shear_truth_preview_gate_state[
        "rejected_as_web_crushing_marginal"
    ]
    rejected_as_impractical_shear_layout = shear_truth_preview_gate_state[
        "rejected_as_impractical_shear_layout"
    ]
    if shear_truth_preview_gate_state["should_continue"]:
        return _build_one_click_solver_single_candidate_post_metric_scoring_result_state_coordinator(
            post_metric_scope=locals(),
        )

    direction_material_gate_chain_state = (
        _dispatch_one_click_solver_candidate_direction_material_gate_chain_from_post_metric_coordinator(
            post_metric_scope=locals(),
        )
    )
    growth_candidates_rejected_in_tightening = direction_material_gate_chain_state[
        "growth_candidates_rejected_in_tightening"
    ]
    rejected_as_non_material_improvement = direction_material_gate_chain_state[
        "rejected_as_non_material_improvement"
    ]
    shear_remove_links_candidate_dropped_reason = direction_material_gate_chain_state[
        "shear_remove_links_candidate_dropped_reason"
    ]
    shear_remove_links_candidate_materiality = direction_material_gate_chain_state[
        "shear_remove_links_candidate_materiality"
    ]
    if direction_material_gate_chain_state["should_continue"]:
        return _build_one_click_solver_single_candidate_post_metric_scoring_result_state_coordinator(
            post_metric_scope=locals(),
        )

    scored_assembly_chain_state = (
        _dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator(
            post_metric_scope=locals(),
        )
    )
    scored = scored_assembly_chain_state["scored"]
    web_crushing_penalty_applied = scored_assembly_chain_state[
        "web_crushing_penalty_applied"
    ]
    return _build_one_click_solver_single_candidate_post_metric_scoring_result_state_coordinator(
        post_metric_scope=locals(),
    )


def _build_one_click_solver_single_candidate_scoring_flow_result_state_coordinator(
    *,
    scoring_flow_scope: dict,
) -> dict:
    return {
        "scored": scoring_flow_scope["scored"],
        "rejected_as_non_governing_cleanup": scoring_flow_scope[
            "rejected_as_non_governing_cleanup"
        ],
        "rejected_as_non_governing_shear_strengthening": scoring_flow_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        "rejected_as_evaluation_failed": scoring_flow_scope[
            "rejected_as_evaluation_failed"
        ],
        "rejected_as_duplicate_signature": scoring_flow_scope[
            "rejected_as_duplicate_signature"
        ],
        "rejected_as_non_material_improvement": scoring_flow_scope[
            "rejected_as_non_material_improvement"
        ],
        "growth_candidates_rejected_in_tightening": scoring_flow_scope[
            "growth_candidates_rejected_in_tightening"
        ],
        "shear_remove_links_candidate_seen": scoring_flow_scope[
            "shear_remove_links_candidate_seen"
        ],
        "shear_remove_links_candidate_truth_ok": scoring_flow_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        "shear_remove_links_candidate_dropped_reason": scoring_flow_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "shear_remove_links_candidate_materiality": scoring_flow_scope[
            "shear_remove_links_candidate_materiality"
        ],
        "rejected_as_spacing_too_weak": scoring_flow_scope[
            "rejected_as_spacing_too_weak"
        ],
        "rejected_as_web_crushing_marginal": scoring_flow_scope[
            "rejected_as_web_crushing_marginal"
        ],
        "rejected_as_impractical_shear_layout": scoring_flow_scope[
            "rejected_as_impractical_shear_layout"
        ],
        "web_crushing_penalty_applied": scoring_flow_scope[
            "web_crushing_penalty_applied"
        ],
    }


def _run_one_click_solver_single_candidate_scoring_flow_coordinator(
    *,
    entry: dict,
    step_idx: int,
    working: dict,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    target_domains_for_band: list[str],
    tightening_mode_active: bool,
    governing_domain: str | None,
    cur_shear_failing: bool,
    target_band_domain: str | None,
    seen_sigs: set,
    cur_u: float,
    mixed_direction_mode,
    cur_has_td: bool,
    cur_required_fail_count: int,
    cur_required_unsatisfied_count: int,
    material_improvement_threshold: float,
    scored: list[dict],
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    rejected_as_evaluation_failed: int,
    rejected_as_duplicate_signature: int,
    rejected_as_non_material_improvement: int,
    growth_candidates_rejected_in_tightening: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    shear_remove_links_candidate_materiality: str,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    web_crushing_penalty_applied: int,
    trace_callback,
) -> dict:
    pre_metric_gate_state = (
        _run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator(
            entry=entry,
            step_idx=step_idx,
            working=working,
            cur_eval=cur_eval,
            mode_config=mode_config,
            target_domains_for_band=target_domains_for_band,
            tightening_mode_active=tightening_mode_active,
            governing_domain=governing_domain,
            cur_shear_failing=cur_shear_failing,
            target_band_domain=target_band_domain,
            seen_sigs=seen_sigs,
            rejected_as_non_governing_cleanup=rejected_as_non_governing_cleanup,
            rejected_as_non_governing_shear_strengthening=(
                rejected_as_non_governing_shear_strengthening
            ),
            rejected_as_evaluation_failed=rejected_as_evaluation_failed,
            rejected_as_duplicate_signature=rejected_as_duplicate_signature,
            trace_callback=trace_callback,
        )
    )
    rc = pre_metric_gate_state["rc"]
    norm_u = pre_metric_gate_state["norm_u"]
    direction = pre_metric_gate_state["direction"]
    family_hint = pre_metric_gate_state["family_hint"]
    peval = pre_metric_gate_state["peval"]
    preview = pre_metric_gate_state["preview"]
    psig = pre_metric_gate_state["psig"]
    rejected_as_non_governing_cleanup = pre_metric_gate_state[
        "rejected_as_non_governing_cleanup"
    ]
    rejected_as_non_governing_shear_strengthening = pre_metric_gate_state[
        "rejected_as_non_governing_shear_strengthening"
    ]
    rejected_as_evaluation_failed = pre_metric_gate_state[
        "rejected_as_evaluation_failed"
    ]
    rejected_as_duplicate_signature = pre_metric_gate_state[
        "rejected_as_duplicate_signature"
    ]
    if pre_metric_gate_state["should_continue"]:
        return _build_one_click_solver_single_candidate_scoring_flow_result_state_coordinator(
            scoring_flow_scope=locals(),
        )

    return _run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator(
        scored=scored,
        peval=peval,
        cur_eval=cur_eval,
        preview=preview,
        mode_config=mode_config,
        step_idx=step_idx,
        rc=rc,
        norm_u=norm_u,
        direction=direction,
        psig=psig,
        cur_u=cur_u,
        mixed_direction_mode=mixed_direction_mode,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        family_hint=family_hint,
        cur_has_td=cur_has_td,
        cur_required_fail_count=cur_required_fail_count,
        cur_required_unsatisfied_count=cur_required_unsatisfied_count,
        rejected_as_non_governing_cleanup=rejected_as_non_governing_cleanup,
        rejected_as_non_governing_shear_strengthening=rejected_as_non_governing_shear_strengthening,
        rejected_as_evaluation_failed=rejected_as_evaluation_failed,
        rejected_as_duplicate_signature=rejected_as_duplicate_signature,
        rejected_as_non_material_improvement=rejected_as_non_material_improvement,
        growth_candidates_rejected_in_tightening=growth_candidates_rejected_in_tightening,
        shear_remove_links_candidate_seen=shear_remove_links_candidate_seen,
        shear_remove_links_candidate_truth_ok=shear_remove_links_candidate_truth_ok,
        shear_remove_links_candidate_dropped_reason=shear_remove_links_candidate_dropped_reason,
        shear_remove_links_candidate_materiality=shear_remove_links_candidate_materiality,
        rejected_as_spacing_too_weak=rejected_as_spacing_too_weak,
        rejected_as_web_crushing_marginal=rejected_as_web_crushing_marginal,
        rejected_as_impractical_shear_layout=rejected_as_impractical_shear_layout,
        web_crushing_penalty_applied=web_crushing_penalty_applied,
        material_improvement_threshold=material_improvement_threshold,
        working=working,
        trace_callback=trace_callback,
    )


def _build_one_click_solver_candidate_scoring_loop_result_state_coordinator(
    *,
    scoring_loop_scope: dict,
) -> dict:
    return {
        "scored": scoring_loop_scope["scored"],
        "rejected_as_non_governing_cleanup": scoring_loop_scope[
            "rejected_as_non_governing_cleanup"
        ],
        "rejected_as_non_governing_shear_strengthening": scoring_loop_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        "rejected_as_evaluation_failed": scoring_loop_scope[
            "rejected_as_evaluation_failed"
        ],
        "rejected_as_duplicate_signature": scoring_loop_scope[
            "rejected_as_duplicate_signature"
        ],
        "rejected_as_non_material_improvement": scoring_loop_scope[
            "rejected_as_non_material_improvement"
        ],
        "growth_candidates_rejected_in_tightening": scoring_loop_scope[
            "growth_candidates_rejected_in_tightening"
        ],
        "shear_remove_links_candidate_seen": scoring_loop_scope[
            "shear_remove_links_candidate_seen"
        ],
        "shear_remove_links_candidate_truth_ok": scoring_loop_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        "shear_remove_links_candidate_dropped_reason": scoring_loop_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "shear_remove_links_candidate_materiality": scoring_loop_scope[
            "shear_remove_links_candidate_materiality"
        ],
        "rejected_as_spacing_too_weak": scoring_loop_scope[
            "rejected_as_spacing_too_weak"
        ],
        "rejected_as_web_crushing_marginal": scoring_loop_scope[
            "rejected_as_web_crushing_marginal"
        ],
        "rejected_as_impractical_shear_layout": scoring_loop_scope[
            "rejected_as_impractical_shear_layout"
        ],
        "web_crushing_penalty_applied": scoring_loop_scope[
            "web_crushing_penalty_applied"
        ],
    }


def _unpack_one_click_solver_single_candidate_scoring_flow_state_coordinator(
    *,
    single_candidate_scoring_flow_state: dict,
) -> tuple:
    return (
        single_candidate_scoring_flow_state["scored"],
        single_candidate_scoring_flow_state["rejected_as_non_governing_cleanup"],
        single_candidate_scoring_flow_state[
            "rejected_as_non_governing_shear_strengthening"
        ],
        single_candidate_scoring_flow_state["rejected_as_evaluation_failed"],
        single_candidate_scoring_flow_state["rejected_as_duplicate_signature"],
        single_candidate_scoring_flow_state["rejected_as_non_material_improvement"],
        single_candidate_scoring_flow_state[
            "growth_candidates_rejected_in_tightening"
        ],
        single_candidate_scoring_flow_state["shear_remove_links_candidate_seen"],
        single_candidate_scoring_flow_state["shear_remove_links_candidate_truth_ok"],
        single_candidate_scoring_flow_state[
            "shear_remove_links_candidate_dropped_reason"
        ],
        single_candidate_scoring_flow_state["shear_remove_links_candidate_materiality"],
        single_candidate_scoring_flow_state["rejected_as_spacing_too_weak"],
        single_candidate_scoring_flow_state["rejected_as_web_crushing_marginal"],
        single_candidate_scoring_flow_state["rejected_as_impractical_shear_layout"],
        single_candidate_scoring_flow_state["web_crushing_penalty_applied"],
    )


def _unpack_one_click_solver_candidate_fallback_pool_trace_state_coordinator(
    *,
    candidate_fallback_pool_trace_state: dict,
) -> tuple[list[dict], bool, str | None]:
    return (
        candidate_fallback_pool_trace_state["scored"],
        candidate_fallback_pool_trace_state["fallback_next_hop_injected"],
        candidate_fallback_pool_trace_state["fallback_next_hop_reason"],
    )


def _run_one_click_solver_candidate_scoring_loop_coordinator(
    *,
    prepared: list[dict],
    step_idx: int,
    working: dict,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    target_domains_for_band: list[str],
    tightening_mode_active: bool,
    governing_domain: str | None,
    cur_shear_failing: bool,
    target_band_domain: str | None,
    seen_sigs: set,
    cur_u: float,
    mixed_direction_mode,
    cur_has_td: bool,
    cur_required_fail_count: int,
    cur_required_unsatisfied_count: int,
    material_improvement_threshold: float,
    scored: list[dict],
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    rejected_as_evaluation_failed: int,
    rejected_as_duplicate_signature: int,
    rejected_as_non_material_improvement: int,
    growth_candidates_rejected_in_tightening: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    shear_remove_links_candidate_materiality: str,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    web_crushing_penalty_applied: int,
    trace_callback,
) -> dict:
    for entry in prepared:
        single_candidate_scoring_flow_state = (
            _run_one_click_solver_single_candidate_scoring_flow_coordinator(
                entry=entry,
                step_idx=step_idx,
                working=working,
                cur_eval=cur_eval,
                mode_config=mode_config,
                target_domains_for_band=target_domains_for_band,
                tightening_mode_active=tightening_mode_active,
                governing_domain=governing_domain,
                cur_shear_failing=cur_shear_failing,
                target_band_domain=target_band_domain,
                seen_sigs=seen_sigs,
                cur_u=cur_u,
                mixed_direction_mode=mixed_direction_mode,
                cur_has_td=cur_has_td,
                cur_required_fail_count=cur_required_fail_count,
                cur_required_unsatisfied_count=cur_required_unsatisfied_count,
                material_improvement_threshold=material_improvement_threshold,
                scored=scored,
                rejected_as_non_governing_cleanup=rejected_as_non_governing_cleanup,
                rejected_as_non_governing_shear_strengthening=(
                    rejected_as_non_governing_shear_strengthening
                ),
                rejected_as_evaluation_failed=rejected_as_evaluation_failed,
                rejected_as_duplicate_signature=rejected_as_duplicate_signature,
                rejected_as_non_material_improvement=rejected_as_non_material_improvement,
                growth_candidates_rejected_in_tightening=(
                    growth_candidates_rejected_in_tightening
                ),
                shear_remove_links_candidate_seen=shear_remove_links_candidate_seen,
                shear_remove_links_candidate_truth_ok=shear_remove_links_candidate_truth_ok,
                shear_remove_links_candidate_dropped_reason=(
                    shear_remove_links_candidate_dropped_reason
                ),
                shear_remove_links_candidate_materiality=(
                    shear_remove_links_candidate_materiality
                ),
                rejected_as_spacing_too_weak=rejected_as_spacing_too_weak,
                rejected_as_web_crushing_marginal=rejected_as_web_crushing_marginal,
                rejected_as_impractical_shear_layout=(
                    rejected_as_impractical_shear_layout
                ),
                web_crushing_penalty_applied=web_crushing_penalty_applied,
                trace_callback=trace_callback,
            )
        )
        (
            scored,
            rejected_as_non_governing_cleanup,
            rejected_as_non_governing_shear_strengthening,
            rejected_as_evaluation_failed,
            rejected_as_duplicate_signature,
            rejected_as_non_material_improvement,
            growth_candidates_rejected_in_tightening,
            shear_remove_links_candidate_seen,
            shear_remove_links_candidate_truth_ok,
            shear_remove_links_candidate_dropped_reason,
            shear_remove_links_candidate_materiality,
            rejected_as_spacing_too_weak,
            rejected_as_web_crushing_marginal,
            rejected_as_impractical_shear_layout,
            web_crushing_penalty_applied,
        ) = _unpack_one_click_solver_single_candidate_scoring_flow_state_coordinator(
            single_candidate_scoring_flow_state=single_candidate_scoring_flow_state,
        )

    return _build_one_click_solver_candidate_scoring_loop_result_state_coordinator(
        scoring_loop_scope=locals()
    )


def _build_one_click_solver_scored_candidate_selection_state_result_coordinator(
    *,
    scored: list[dict],
    fallback_next_hop_injected: bool,
    fallback_next_hop_reason: str | None,
    candidate_selection_or_stop_state: dict,
) -> dict:
    return {
        "scored": scored,
        "fallback_next_hop_injected": fallback_next_hop_injected,
        "fallback_next_hop_reason": fallback_next_hop_reason,
        "no_actionable_after_full_tightening_search": candidate_selection_or_stop_state[
            "no_actionable_after_full_tightening_search"
        ],
        "best": candidate_selection_or_stop_state["best"],
        "best_distance_to_band_this_iteration": candidate_selection_or_stop_state[
            "best_distance_to_band_this_iteration"
        ],
        "should_break": candidate_selection_or_stop_state["should_break"],
        "stop_reason": candidate_selection_or_stop_state["stop_reason"],
        "status": candidate_selection_or_stop_state["status"],
        "final_distance_to_band": candidate_selection_or_stop_state[
            "final_distance_to_band"
        ],
    }


def _dispatch_one_click_solver_candidate_fallback_pool_trace_from_selection_coordinator(
    *,
    selection_scope: dict,
) -> dict:
    return _handle_one_click_solver_candidate_fallback_pool_trace_coordinator(
        scored=selection_scope["scored"],
        cur_eval=selection_scope["cur_eval"],
        working=selection_scope["working"],
        mode_config=selection_scope["mode_config"],
        tightening_mode_active=selection_scope["tightening_mode_active"],
        step_idx=selection_scope["step_idx"],
        raw_n=selection_scope["raw_n"],
        pool_labels=selection_scope["pool_labels"],
        governing_domain=selection_scope["governing_domain"],
        tightening_meta=selection_scope["tightening_meta"],
        material_improvement_threshold=selection_scope[
            "material_improvement_threshold"
        ],
        reduction_candidates_considered=selection_scope[
            "reduction_candidates_considered"
        ],
        growth_candidates_rejected_in_tightening=selection_scope[
            "growth_candidates_rejected_in_tightening"
        ],
        rejected_as_non_governing_cleanup=selection_scope[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=selection_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        rejected_as_non_material_improvement=selection_scope[
            "rejected_as_non_material_improvement"
        ],
        tightening_step_count=selection_scope["tightening_step_count"],
        max_tightening_steps=selection_scope["max_tightening_steps"],
        no_actionable_after_full_tightening_search=selection_scope[
            "no_actionable_after_full_tightening_search"
        ],
        candidate_family_depth_reached=selection_scope[
            "candidate_family_depth_reached"
        ],
        shear_governing_mode_active=selection_scope["shear_governing_mode_active"],
        shear_severity_band=selection_scope["shear_severity_band"],
        shear_candidate_family_order=selection_scope["shear_candidate_family_order"],
        spacing_candidates_considered=selection_scope["spacing_candidates_considered"],
        leg_candidates_considered=selection_scope["leg_candidates_considered"],
        dia_candidates_considered=selection_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=selection_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=selection_scope[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=selection_scope["web_crushing_penalty_applied"],
        rejected_as_spacing_too_weak=selection_scope["rejected_as_spacing_too_weak"],
        rejected_as_web_crushing_marginal=selection_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=selection_scope[
            "rejected_as_impractical_shear_layout"
        ],
        shear_governing_family_detected=selection_scope[
            "shear_governing_family_detected"
        ],
        governing_family_exists_after_domain_fix=selection_scope[
            "governing_family_exists_after_domain_fix"
        ],
        pruned_non_shear_family_count=selection_scope[
            "pruned_non_shear_family_count"
        ],
        domain_match_prune_used=selection_scope["domain_match_prune_used"],
        shear_prune_rule_source=selection_scope["shear_prune_rule_source"],
        trace_callback=selection_scope["trace_callback"],
    )


def _resolve_one_click_solver_scored_candidate_selection_state_coordinator(
    *,
    scored: list[dict],
    cur_eval: dict,
    working: dict,
    mode_config: OneClickModeConfig,
    tightening_mode_active: bool,
    step_idx: int,
    raw_n: int,
    pool_labels: list[str],
    governing_domain: str | None,
    tightening_meta: dict,
    material_improvement_threshold: float,
    reduction_candidates_considered: int,
    growth_candidates_rejected_in_tightening: int,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    rejected_as_non_material_improvement: int,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: bool,
    shear_governing_mode_active: bool,
    shear_severity_band: str | None,
    shear_candidate_family_order: list,
    spacing_candidates_considered: bool,
    leg_candidates_considered: bool,
    dia_candidates_considered: bool,
    geometry_candidates_considered_for_shear: bool,
    combined_candidates_considered_for_shear: bool,
    web_crushing_penalty_applied: int,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    domain_match_prune_used: bool,
    shear_prune_rule_source: str | None,
    cur_pass: bool,
    step_trace: list[dict],
    initial_snapshot: dict,
    cur_ib: bool,
    winning_label: str | None,
    winning_action_type: str | None,
    in_band_shear_cleanup_deferral: bool,
    trace_callback,
) -> dict:
    candidate_fallback_pool_trace_state = (
        _dispatch_one_click_solver_candidate_fallback_pool_trace_from_selection_coordinator(
            selection_scope=locals(),
        )
    )
    (
        scored,
        fallback_next_hop_injected,
        fallback_next_hop_reason,
    ) = _unpack_one_click_solver_candidate_fallback_pool_trace_state_coordinator(
        candidate_fallback_pool_trace_state=candidate_fallback_pool_trace_state,
    )

    candidate_selection_or_stop_state = _handle_one_click_solver_candidate_selection_or_stop_coordinator(
        scored=scored,
        cur_eval=cur_eval,
        mode_config=mode_config,
        step_idx=step_idx,
        cur_pass=cur_pass,
        step_trace=step_trace,
        initial_snapshot=initial_snapshot,
        working=working,
        governing_domain=governing_domain,
        tightening_mode_active=tightening_mode_active,
        rejected_as_non_material_improvement=rejected_as_non_material_improvement,
        no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
        cur_ib=cur_ib,
        winning_label=winning_label,
        winning_action_type=winning_action_type,
        tightening_step_count=tightening_step_count,
        max_tightening_steps=max_tightening_steps,
        candidate_family_depth_reached=candidate_family_depth_reached,
        in_band_shear_cleanup_deferral=in_band_shear_cleanup_deferral,
        trace_callback=trace_callback,
    )
    return _build_one_click_solver_scored_candidate_selection_state_result_coordinator(
        scored=scored,
        fallback_next_hop_injected=fallback_next_hop_injected,
        fallback_next_hop_reason=fallback_next_hop_reason,
        candidate_selection_or_stop_state=candidate_selection_or_stop_state,
    )


def _build_one_click_solver_iteration_gate_ready_state_coordinator(
    *,
    iteration_gate_scope: dict,
) -> dict:
    return {
        "should_continue": False,
        "should_break": False,
        "cur_eval": iteration_gate_scope["cur_eval"],
        "cur_pass": iteration_gate_scope["cur_pass"],
        "cur_sig": iteration_gate_scope["cur_sig"],
        "tightening_mode_active": iteration_gate_scope["tightening_mode_active"],
        "governing_domain": iteration_gate_scope["governing_domain"],
        "target_band_domain": iteration_gate_scope["target_band_domain"],
        "cur_statuses": iteration_gate_scope["cur_statuses"],
        "cur_shear_status": iteration_gate_scope["cur_shear_status"],
        "cur_shear_failing": iteration_gate_scope["cur_shear_failing"],
        "cur_fail_keys": iteration_gate_scope["cur_fail_keys"],
        "governing_domain_norm": iteration_gate_scope["governing_domain_norm"],
        "governing_domain_failing": iteration_gate_scope["governing_domain_failing"],
        "cur_ib": iteration_gate_scope["cur_ib"],
        "target_work_domain": iteration_gate_scope["target_work_domain"],
        "required_domain_work_active": iteration_gate_scope["required_domain_work_active"],
        "in_band_shear_cleanup_deferral": iteration_gate_scope[
            "in_band_shear_cleanup_deferral"
        ],
        "final_governing_domain": iteration_gate_scope["final_governing_domain"],
        "shear_governing_mode_active": iteration_gate_scope["shear_governing_mode_active"],
        "shear_governing_family_detected": iteration_gate_scope[
            "shear_governing_family_detected"
        ],
        "pruned_non_shear_family_count": iteration_gate_scope[
            "pruned_non_shear_family_count"
        ],
        "domain_match_prune_used": iteration_gate_scope["domain_match_prune_used"],
        "shear_prune_rule_source": iteration_gate_scope["shear_prune_rule_source"],
        "material_improvement_threshold": iteration_gate_scope[
            "material_improvement_threshold"
        ],
        "tightening_meta": iteration_gate_scope["tightening_meta"],
        "cur_u": iteration_gate_scope["cur_u"],
        "max_tightening_steps": iteration_gate_scope["max_tightening_steps"],
        "tightening_budget_extensions_used": iteration_gate_scope[
            "tightening_budget_extensions_used"
        ],
    }


def _dispatch_one_click_solver_current_target_domain_state_from_iteration_gate_coordinator(
    *,
    iteration_gate_scope: dict,
) -> dict:
    return _prepare_one_click_solver_current_target_domain_state_coordinator(
        initial_snapshot=iteration_gate_scope["initial_snapshot"],
        working=iteration_gate_scope["working"],
        cur_eval=iteration_gate_scope["cur_eval"],
        mode_config=iteration_gate_scope["mode_config"],
        target_domains_for_band=iteration_gate_scope["target_domains_for_band"],
        target_band_domain=iteration_gate_scope["target_band_domain"],
        cur_shear_failing=iteration_gate_scope["cur_shear_failing"],
        cur_pass=iteration_gate_scope["cur_pass"],
        governing_domain=iteration_gate_scope["governing_domain"],
        tightening_mode_active=iteration_gate_scope["tightening_mode_active"],
    )


def _dispatch_one_click_solver_tightening_depth_gate_state_from_iteration_gate_coordinator(
    *,
    iteration_gate_scope: dict,
) -> dict:
    return _prepare_one_click_solver_tightening_depth_gate_state_coordinator(
        cur_eval=iteration_gate_scope["cur_eval"],
        mode_config=iteration_gate_scope["mode_config"],
        step_trace=iteration_gate_scope["step_trace"],
        initial_snapshot=iteration_gate_scope["initial_snapshot"],
        working=iteration_gate_scope["working"],
        cur_ib=iteration_gate_scope["cur_ib"],
        cur_pass=iteration_gate_scope["cur_pass"],
        winning_label=iteration_gate_scope["winning_label"],
        winning_action_type=iteration_gate_scope["winning_action_type"],
        tightening_mode_active=iteration_gate_scope["tightening_mode_active"],
        tightening_step_count=iteration_gate_scope["tightening_step_count"],
        max_tightening_steps=iteration_gate_scope["max_tightening_steps"],
        tightening_budget_extensions_used=iteration_gate_scope[
            "tightening_budget_extensions_used"
        ],
        tightening_budget_extension_cap=iteration_gate_scope[
            "tightening_budget_extension_cap"
        ],
        candidate_family_depth_reached=iteration_gate_scope[
            "candidate_family_depth_reached"
        ],
        trace_callback=iteration_gate_scope["trace_callback"],
    )


def _prepare_one_click_solver_iteration_gate_after_current_eval_state_coordinator(
    *,
    iteration_gate_scope: dict,
    current_iteration_eval_state: dict,
) -> dict:
    cur_eval = current_iteration_eval_state["cur_eval"]
    working = iteration_gate_scope["working"]
    mode_config = iteration_gate_scope["mode_config"]
    target_band_domain = iteration_gate_scope["target_band_domain"]
    target_domains_for_band = iteration_gate_scope["target_domains_for_band"]
    step_trace = iteration_gate_scope["step_trace"]
    initial_snapshot = iteration_gate_scope["initial_snapshot"]
    winning_label = iteration_gate_scope["winning_label"]
    winning_action_type = iteration_gate_scope["winning_action_type"]
    tightening_step_count = iteration_gate_scope["tightening_step_count"]
    max_tightening_steps = iteration_gate_scope["max_tightening_steps"]
    tightening_budget_extensions_used = iteration_gate_scope["tightening_budget_extensions_used"]
    tightening_budget_extension_cap = iteration_gate_scope["tightening_budget_extension_cap"]
    candidate_family_depth_reached = iteration_gate_scope["candidate_family_depth_reached"]
    trace_callback = iteration_gate_scope["trace_callback"]
    cur_pass = current_iteration_eval_state["cur_pass"]
    cur_sig = current_iteration_eval_state["cur_sig"]
    tightening_mode_active = current_iteration_eval_state["tightening_mode_active"]
    governing_domain = current_iteration_eval_state["governing_domain"]
    target_band_domain = current_iteration_eval_state["target_band_domain"]
    cur_statuses = current_iteration_eval_state["cur_statuses"]
    cur_shear_status = current_iteration_eval_state["cur_shear_status"]
    cur_shear_failing = current_iteration_eval_state["cur_shear_failing"]
    cur_fail_keys = current_iteration_eval_state["cur_fail_keys"]
    governing_domain_norm = current_iteration_eval_state["governing_domain_norm"]
    governing_domain_failing = current_iteration_eval_state["governing_domain_failing"]

    current_target_domain_state = (
        _dispatch_one_click_solver_current_target_domain_state_from_iteration_gate_coordinator(
            iteration_gate_scope=locals(),
        )
    )
    target_band_domain = current_target_domain_state["target_band_domain"]
    cur_ib = current_target_domain_state["cur_ib"]
    target_work_domain = current_target_domain_state["target_work_domain"]
    required_domain_work_active = current_target_domain_state["required_domain_work_active"]
    governing_domain = current_target_domain_state["governing_domain"]
    tightening_mode_active = current_target_domain_state["tightening_mode_active"]

    in_band_cleanup_pool_state = _prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator(
        working=working,
        cur_eval=cur_eval,
        mode_config=mode_config,
        cur_pass=cur_pass,
        cur_ib=cur_ib,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
    )
    in_band_shear_cleanup_deferral = in_band_cleanup_pool_state["in_band_shear_cleanup_deferral"]
    tightening_mode_active = in_band_cleanup_pool_state["tightening_mode_active"]
    governing_domain = in_band_cleanup_pool_state["governing_domain"]
    final_governing_domain = in_band_cleanup_pool_state["final_governing_domain"]
    shear_governing_mode_active = in_band_cleanup_pool_state["shear_governing_mode_active"]
    shear_governing_family_detected = in_band_cleanup_pool_state["shear_governing_family_detected"]
    pruned_non_shear_family_count = in_band_cleanup_pool_state["pruned_non_shear_family_count"]
    domain_match_prune_used = in_band_cleanup_pool_state["domain_match_prune_used"]
    shear_prune_rule_source = in_band_cleanup_pool_state["shear_prune_rule_source"]
    material_improvement_threshold = in_band_cleanup_pool_state["material_improvement_threshold"]
    tightening_meta = in_band_cleanup_pool_state["tightening_meta"]
    if in_band_cleanup_pool_state["should_stop_current_reached_target_band"]:
        stop_reason, status = _trace_current_reached_target_band_solver_stop_coordinator(
            cur_eval=cur_eval,
            step_trace=step_trace,
            initial_snapshot=initial_snapshot,
            working=working,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            trace_callback=trace_callback,
        )
        return {
            "should_continue": False,
            "should_break": True,
            "stop_reason": stop_reason,
            "status": status,
            "final_distance_to_band": None,
            "cur_eval": cur_eval,
        }

    tightening_depth_gate_state = (
        _dispatch_one_click_solver_tightening_depth_gate_state_from_iteration_gate_coordinator(
            iteration_gate_scope=locals(),
        )
    )
    cur_u = tightening_depth_gate_state["cur_u"]
    max_tightening_steps = tightening_depth_gate_state["max_tightening_steps"]
    tightening_budget_extensions_used = tightening_depth_gate_state["tightening_budget_extensions_used"]
    if tightening_depth_gate_state["should_continue"]:
        return {
            "should_continue": True,
            "should_break": False,
            "cur_eval": cur_eval,
            "cur_u": cur_u,
            "max_tightening_steps": max_tightening_steps,
            "tightening_budget_extensions_used": tightening_budget_extensions_used,
        }
    if tightening_depth_gate_state["should_break"]:
        return {
            "should_continue": False,
            "should_break": True,
            "stop_reason": tightening_depth_gate_state["stop_reason"],
            "status": tightening_depth_gate_state["status"],
            "final_distance_to_band": tightening_depth_gate_state["final_distance_to_band"],
            "cur_eval": cur_eval,
            "cur_u": cur_u,
            "max_tightening_steps": max_tightening_steps,
            "tightening_budget_extensions_used": tightening_budget_extensions_used,
        }

    return _build_one_click_solver_iteration_gate_ready_state_coordinator(
        iteration_gate_scope=locals(),
    )


def _prepare_one_click_solver_iteration_gate_state_coordinator(
    *,
    step_idx: int,
    working: dict,
    mode_config: OneClickModeConfig,
    target_band_domain: str | None,
    target_domains_for_band: list[str],
    step_trace: list[dict],
    initial_snapshot: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    tightening_step_count: int,
    max_tightening_steps: int,
    tightening_budget_extensions_used: int,
    tightening_budget_extension_cap: int,
    candidate_family_depth_reached: bool,
    trace_callback,
) -> dict:
    current_iteration_eval_state = _prepare_one_click_solver_current_iteration_eval_state_coordinator(
        step_idx=step_idx,
        working=working,
        mode_config=mode_config,
        target_band_domain=target_band_domain,
        step_trace=step_trace,
        initial_snapshot=initial_snapshot,
        winning_label=winning_label,
        winning_action_type=winning_action_type,
        trace_callback=trace_callback,
    )
    cur_eval = current_iteration_eval_state["cur_eval"]
    if cur_eval is None:
        return {
            "should_continue": False,
            "should_break": True,
            "stop_reason": current_iteration_eval_state["stop_reason"],
            "status": current_iteration_eval_state["status"],
            "final_distance_to_band": None,
            "cur_eval": None,
        }

    return _prepare_one_click_solver_iteration_gate_after_current_eval_state_coordinator(
        iteration_gate_scope=locals(),
        current_iteration_eval_state=current_iteration_eval_state,
    )


def _build_one_click_solver_candidate_pipeline_result_state_coordinator(
    *,
    candidate_pipeline_scope: dict,
) -> dict:
    return {
        "raw_n": candidate_pipeline_scope["raw_n"],
        "pool_labels": candidate_pipeline_scope["pool_labels"],
        "prepared": candidate_pipeline_scope["prepared"],
        "prepared_samples": candidate_pipeline_scope["prepared_samples"],
        "reduction_candidates_considered": candidate_pipeline_scope[
            "reduction_candidates_considered"
        ],
        "governing_family_exists": candidate_pipeline_scope["governing_family_exists"],
        "shear_governing_family_detected": candidate_pipeline_scope[
            "shear_governing_family_detected"
        ],
        "governing_family_exists_after_domain_fix": candidate_pipeline_scope[
            "governing_family_exists_after_domain_fix"
        ],
        "mixed_direction_mode": candidate_pipeline_scope["mixed_direction_mode"],
        "tightening_meta": candidate_pipeline_scope["tightening_meta"],
        "candidate_family_depth_reached": candidate_pipeline_scope[
            "candidate_family_depth_reached"
        ],
        "shear_governing_mode_active": candidate_pipeline_scope[
            "shear_governing_mode_active"
        ],
        "shear_severity_band": candidate_pipeline_scope["shear_severity_band"],
        "shear_candidate_family_order": candidate_pipeline_scope[
            "shear_candidate_family_order"
        ],
        "spacing_candidates_considered": candidate_pipeline_scope[
            "spacing_candidates_considered"
        ],
        "leg_candidates_considered": candidate_pipeline_scope["leg_candidates_considered"],
        "dia_candidates_considered": candidate_pipeline_scope["dia_candidates_considered"],
        "geometry_candidates_considered_for_shear": candidate_pipeline_scope[
            "geometry_candidates_considered_for_shear"
        ],
        "combined_candidates_considered_for_shear": candidate_pipeline_scope[
            "combined_candidates_considered_for_shear"
        ],
        "rejected_as_non_governing_cleanup": candidate_pipeline_scope[
            "rejected_as_non_governing_cleanup"
        ],
        "rejected_as_non_governing_shear_strengthening": candidate_pipeline_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        "rejected_as_non_material_improvement": candidate_pipeline_scope[
            "rejected_as_non_material_improvement"
        ],
        "rejected_as_no_real_change": candidate_pipeline_scope[
            "rejected_as_no_real_change"
        ],
        "rejected_as_duplicate_signature": candidate_pipeline_scope[
            "rejected_as_duplicate_signature"
        ],
        "rejected_as_evaluation_failed": candidate_pipeline_scope[
            "rejected_as_evaluation_failed"
        ],
        "shear_remove_links_candidate_seen": candidate_pipeline_scope[
            "shear_remove_links_candidate_seen"
        ],
        "shear_remove_links_candidate_dropped_reason": candidate_pipeline_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "pruned_non_shear_family_count": candidate_pipeline_scope[
            "pruned_non_shear_family_count"
        ],
        "domain_match_prune_used": candidate_pipeline_scope["domain_match_prune_used"],
        "shear_prune_rule_source": candidate_pipeline_scope["shear_prune_rule_source"],
        "growth_candidates_rejected_in_tightening": candidate_pipeline_scope[
            "growth_candidates_rejected_in_tightening"
        ],
        "cur_has_td": candidate_pipeline_scope["cur_has_td"],
        "cur_required_fail_count": candidate_pipeline_scope["cur_required_fail_count"],
        "cur_required_unsatisfied_count": candidate_pipeline_scope[
            "cur_required_unsatisfied_count"
        ],
        "scored": candidate_pipeline_scope["scored"],
    }


def _prepare_one_click_solver_candidate_pipeline_pre_scoring_state_coordinator(
    *,
    raw_candidates: list[dict],
    working: dict,
    governing_domain: str | None,
    use_governing_domain_candidates: bool,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    step_idx: int,
    tightening_mode_active: bool,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    pruned_non_shear_family_count: int,
    domain_match_prune_used: bool,
    shear_prune_rule_source: str | None,
    trace_callback,
) -> dict:
    prepared_loop_state = _prepare_one_click_solver_prepared_candidate_loop_state_coordinator(
        raw_candidates=raw_candidates,
        working=working,
        governing_domain=governing_domain,
        use_governing_domain_candidates=use_governing_domain_candidates,
        cur_eval=cur_eval,
        mode_config=mode_config,
    )
    pre_scoring_prune_pass_state = _run_one_click_solver_pre_scoring_prune_pass_coordinator(
        prepared=prepared_loop_state["prepared"],
        step_idx=step_idx,
        working=working,
        cur_eval=cur_eval,
        mode_config=mode_config,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        should_apply_domain_prune=prepared_loop_state["should_apply_domain_prune"],
        shear_domain_prune_active=prepared_loop_state["shear_domain_prune_active"],
        reduction_candidates_considered=prepared_loop_state["reduction_candidates_considered"],
        rejected_as_no_real_change=prepared_loop_state["rejected_as_no_real_change"],
        shear_remove_links_candidate_seen=shear_remove_links_candidate_seen,
        shear_remove_links_candidate_dropped_reason=shear_remove_links_candidate_dropped_reason,
        rejected_as_non_governing_cleanup=prepared_loop_state["rejected_as_non_governing_cleanup"],
        pruned_non_shear_family_count=pruned_non_shear_family_count,
        domain_match_prune_used=domain_match_prune_used,
        shear_prune_rule_source=shear_prune_rule_source,
        growth_candidates_rejected_in_tightening=prepared_loop_state[
            "growth_candidates_rejected_in_tightening"
        ],
        trace_callback=trace_callback,
    )
    return {
        "pool_labels": prepared_loop_state["pool_labels"],
        "prepared": prepared_loop_state["prepared"],
        "prepared_samples": prepared_loop_state["prepared_samples"],
        "reduction_candidates_considered": prepared_loop_state["reduction_candidates_considered"],
        "governing_family_exists": prepared_loop_state["governing_family_exists"],
        "shear_governing_family_detected": prepared_loop_state["shear_governing_family_detected"],
        "governing_family_exists_after_domain_fix": prepared_loop_state[
            "governing_family_exists_after_domain_fix"
        ],
        "shear_domain_prune_active": prepared_loop_state["shear_domain_prune_active"],
        "should_apply_domain_prune": prepared_loop_state["should_apply_domain_prune"],
        "mixed_direction_mode": prepared_loop_state["mixed_direction_mode"],
        "growth_candidates_rejected_in_tightening": pre_scoring_prune_pass_state[
            "growth_candidates_rejected_in_tightening"
        ],
        "rejected_as_non_governing_cleanup": pre_scoring_prune_pass_state[
            "rejected_as_non_governing_cleanup"
        ],
        "rejected_as_non_governing_shear_strengthening": prepared_loop_state[
            "rejected_as_non_governing_shear_strengthening"
        ],
        "rejected_as_non_material_improvement": prepared_loop_state[
            "rejected_as_non_material_improvement"
        ],
        "rejected_as_no_real_change": pre_scoring_prune_pass_state["rejected_as_no_real_change"],
        "rejected_as_duplicate_signature": prepared_loop_state["rejected_as_duplicate_signature"],
        "rejected_as_evaluation_failed": prepared_loop_state["rejected_as_evaluation_failed"],
        "shear_remove_links_candidate_seen": pre_scoring_prune_pass_state[
            "shear_remove_links_candidate_seen"
        ],
        "shear_remove_links_candidate_dropped_reason": pre_scoring_prune_pass_state[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "pruned_non_shear_family_count": pre_scoring_prune_pass_state[
            "pruned_non_shear_family_count"
        ],
        "domain_match_prune_used": pre_scoring_prune_pass_state["domain_match_prune_used"],
        "shear_prune_rule_source": pre_scoring_prune_pass_state["shear_prune_rule_source"],
    }


def _dispatch_one_click_solver_candidate_collection_state_from_candidate_pipeline_coordinator(
    *,
    candidate_pipeline_scope: dict,
) -> dict:
    return _prepare_one_click_solver_candidate_collection_state_coordinator(
        working=candidate_pipeline_scope["working"],
        debug_enabled=candidate_pipeline_scope["debug_enabled"],
        trace_run_id=candidate_pipeline_scope["trace_run_id"],
        step_idx=candidate_pipeline_scope["step_idx"],
        tightening_mode_active=candidate_pipeline_scope["tightening_mode_active"],
        governing_domain_failing=candidate_pipeline_scope["governing_domain_failing"],
        required_domain_work_active=candidate_pipeline_scope[
            "required_domain_work_active"
        ],
        target_band_domain=candidate_pipeline_scope["target_band_domain"],
        cur_shear_failing=candidate_pipeline_scope["cur_shear_failing"],
        governing_domain=candidate_pipeline_scope["governing_domain"],
        cur_ib=candidate_pipeline_scope["cur_ib"],
        cur_eval=candidate_pipeline_scope["cur_eval"],
        mode_config=candidate_pipeline_scope["mode_config"],
        tightening_step_count=candidate_pipeline_scope["tightening_step_count"],
        tightening_meta=candidate_pipeline_scope["tightening_meta"],
        candidate_family_depth_reached=candidate_pipeline_scope[
            "candidate_family_depth_reached"
        ],
        shear_governing_mode_active=candidate_pipeline_scope[
            "shear_governing_mode_active"
        ],
        shear_severity_band=candidate_pipeline_scope["shear_severity_band"],
        shear_candidate_family_order=candidate_pipeline_scope[
            "shear_candidate_family_order"
        ],
        spacing_candidates_considered=candidate_pipeline_scope[
            "spacing_candidates_considered"
        ],
        leg_candidates_considered=candidate_pipeline_scope["leg_candidates_considered"],
        dia_candidates_considered=candidate_pipeline_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=candidate_pipeline_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=candidate_pipeline_scope[
            "combined_candidates_considered_for_shear"
        ],
    )


def _run_one_click_solver_candidate_pipeline_after_collection_coordinator(
    *,
    candidate_pipeline_scope: dict,
    candidate_collection_state: dict,
) -> dict:
    candidate_pipeline_after_collection_scope = dict(candidate_pipeline_scope)
    candidate_pipeline_after_collection_scope.update(
        {
            key: candidate_collection_state[key]
            for key in (
                "raw_candidates",
                "raw_n",
                "use_governing_domain_candidates",
                "tightening_meta",
                "candidate_family_depth_reached",
                "shear_governing_mode_active",
                "shear_severity_band",
                "shear_candidate_family_order",
                "spacing_candidates_considered",
                "leg_candidates_considered",
                "dia_candidates_considered",
                "geometry_candidates_considered_for_shear",
                "combined_candidates_considered_for_shear",
            )
        }
    )

    pre_scoring_state = _prepare_one_click_solver_candidate_pipeline_pre_scoring_state_coordinator(
        raw_candidates=candidate_pipeline_after_collection_scope["raw_candidates"],
        working=candidate_pipeline_after_collection_scope["working"],
        governing_domain=candidate_pipeline_after_collection_scope["governing_domain"],
        use_governing_domain_candidates=candidate_pipeline_after_collection_scope[
            "use_governing_domain_candidates"
        ],
        cur_eval=candidate_pipeline_after_collection_scope["cur_eval"],
        mode_config=candidate_pipeline_after_collection_scope["mode_config"],
        step_idx=candidate_pipeline_after_collection_scope["step_idx"],
        tightening_mode_active=candidate_pipeline_after_collection_scope[
            "tightening_mode_active"
        ],
        shear_remove_links_candidate_seen=candidate_pipeline_after_collection_scope[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_dropped_reason=candidate_pipeline_after_collection_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        pruned_non_shear_family_count=candidate_pipeline_after_collection_scope[
            "pruned_non_shear_family_count"
        ],
        domain_match_prune_used=candidate_pipeline_after_collection_scope[
            "domain_match_prune_used"
        ],
        shear_prune_rule_source=candidate_pipeline_after_collection_scope[
            "shear_prune_rule_source"
        ],
        trace_callback=candidate_pipeline_after_collection_scope["trace_callback"],
    )
    candidate_pipeline_after_collection_scope.update(pre_scoring_state)

    iteration_scoring_start_state = _prepare_one_click_solver_iteration_scoring_start_state_coordinator(
        step_idx=candidate_pipeline_after_collection_scope["step_idx"],
        cur_sig=candidate_pipeline_after_collection_scope["cur_sig"],
        working=candidate_pipeline_after_collection_scope["working"],
        cur_eval=candidate_pipeline_after_collection_scope["cur_eval"],
        t_lo=candidate_pipeline_after_collection_scope["t_lo"],
        t_hi=candidate_pipeline_after_collection_scope["t_hi"],
        tightening_mode_active=candidate_pipeline_after_collection_scope[
            "tightening_mode_active"
        ],
        governing_domain=candidate_pipeline_after_collection_scope["governing_domain"],
        material_improvement_threshold=candidate_pipeline_after_collection_scope[
            "material_improvement_threshold"
        ],
        tightening_step_count=candidate_pipeline_after_collection_scope[
            "tightening_step_count"
        ],
        max_tightening_steps=candidate_pipeline_after_collection_scope[
            "max_tightening_steps"
        ],
        mode_config=candidate_pipeline_after_collection_scope["mode_config"],
        no_actionable_after_full_tightening_search=candidate_pipeline_after_collection_scope[
            "no_actionable_after_full_tightening_search"
        ],
        shear_governing_mode_active=candidate_pipeline_after_collection_scope[
            "shear_governing_mode_active"
        ],
        shear_severity_band=candidate_pipeline_after_collection_scope[
            "shear_severity_band"
        ],
        shear_candidate_family_order=candidate_pipeline_after_collection_scope[
            "shear_candidate_family_order"
        ],
        shear_governing_family_detected=candidate_pipeline_after_collection_scope[
            "shear_governing_family_detected"
        ],
        governing_family_exists_after_domain_fix=candidate_pipeline_after_collection_scope[
            "governing_family_exists_after_domain_fix"
        ],
        mixed_direction_mode=candidate_pipeline_after_collection_scope[
            "mixed_direction_mode"
        ],
        pruned_non_shear_family_count=candidate_pipeline_after_collection_scope[
            "pruned_non_shear_family_count"
        ],
        domain_match_prune_used=candidate_pipeline_after_collection_scope[
            "domain_match_prune_used"
        ],
        shear_prune_rule_source=candidate_pipeline_after_collection_scope[
            "shear_prune_rule_source"
        ],
        trace_callback=candidate_pipeline_after_collection_scope["trace_callback"],
    )
    candidate_pipeline_after_collection_scope.update(iteration_scoring_start_state)

    return _build_one_click_solver_candidate_pipeline_result_state_coordinator(
        candidate_pipeline_scope=candidate_pipeline_after_collection_scope,
    )


def _prepare_one_click_solver_candidate_pipeline_state_coordinator(
    *,
    working: dict,
    debug_enabled: bool,
    trace_run_id: str,
    step_idx: int,
    tightening_mode_active: bool,
    governing_domain_failing: bool,
    required_domain_work_active: bool,
    target_band_domain: str | None,
    cur_shear_failing: bool,
    governing_domain: str | None,
    cur_ib: bool,
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    tightening_step_count: int,
    tightening_meta: dict,
    candidate_family_depth_reached: bool,
    shear_governing_mode_active: bool,
    shear_severity_band: str | None,
    shear_candidate_family_order: list,
    spacing_candidates_considered: bool,
    leg_candidates_considered: bool,
    dia_candidates_considered: bool,
    geometry_candidates_considered_for_shear: bool,
    combined_candidates_considered_for_shear: bool,
    cur_sig,
    t_lo: float,
    t_hi: float,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    target_domains_for_band: list[str],
    pruned_non_shear_family_count: int,
    domain_match_prune_used: bool,
    shear_prune_rule_source: str | None,
    material_improvement_threshold: float,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_dropped_reason: str | None,
    trace_callback,
) -> dict:
    candidate_collection_state = (
        _dispatch_one_click_solver_candidate_collection_state_from_candidate_pipeline_coordinator(
            candidate_pipeline_scope=locals(),
        )
    )
    return _run_one_click_solver_candidate_pipeline_after_collection_coordinator(
        candidate_pipeline_scope=locals(),
        candidate_collection_state=candidate_collection_state,
    )


def _build_one_click_solver_runtime_setup_ready_state_coordinator(
    *,
    runtime_setup_scope: dict,
) -> dict:
    solver_iteration_state = runtime_setup_scope["solver_iteration_state"]
    return {
        "should_return": False,
        "rid": runtime_setup_scope["rid"],
        "stop_traced": runtime_setup_scope["stop_traced"],
        "rescue_debug": runtime_setup_scope["rescue_debug"],
        "attempted_seed_keys": runtime_setup_scope["attempted_seed_keys"],
        "trace_callback": runtime_setup_scope["trace_callback"],
        "initial_snapshot": runtime_setup_scope["initial_snapshot"],
        "initial_coherence": runtime_setup_scope["initial_coherence"],
        "working": runtime_setup_scope["working"],
        "mode_config": runtime_setup_scope["mode_config"],
        "t_lo": runtime_setup_scope["t_lo"],
        "t_hi": runtime_setup_scope["t_hi"],
        "max_tightening_steps": runtime_setup_scope["max_tightening_steps"],
        "tightening_budget_extensions_used": runtime_setup_scope[
            "tightening_budget_extensions_used"
        ],
        "tightening_budget_extension_cap": runtime_setup_scope[
            "tightening_budget_extension_cap"
        ],
        "tightening_step_count": runtime_setup_scope["tightening_step_count"],
        "no_actionable_after_full_tightening_search": runtime_setup_scope[
            "no_actionable_after_full_tightening_search"
        ],
        "candidate_family_depth_reached": runtime_setup_scope[
            "candidate_family_depth_reached"
        ],
        "final_distance_to_band": runtime_setup_scope["final_distance_to_band"],
        "shear_governing_mode_active": runtime_setup_scope["shear_governing_mode_active"],
        "shear_severity_band": runtime_setup_scope["shear_severity_band"],
        "shear_candidate_family_order": runtime_setup_scope["shear_candidate_family_order"],
        "spacing_candidates_considered": runtime_setup_scope["spacing_candidates_considered"],
        "leg_candidates_considered": runtime_setup_scope["leg_candidates_considered"],
        "dia_candidates_considered": runtime_setup_scope["dia_candidates_considered"],
        "geometry_candidates_considered_for_shear": runtime_setup_scope[
            "geometry_candidates_considered_for_shear"
        ],
        "combined_candidates_considered_for_shear": runtime_setup_scope[
            "combined_candidates_considered_for_shear"
        ],
        "web_crushing_penalty_applied": runtime_setup_scope["web_crushing_penalty_applied"],
        "rejected_as_spacing_too_weak": runtime_setup_scope["rejected_as_spacing_too_weak"],
        "rejected_as_web_crushing_marginal": runtime_setup_scope[
            "rejected_as_web_crushing_marginal"
        ],
        "rejected_as_impractical_shear_layout": runtime_setup_scope[
            "rejected_as_impractical_shear_layout"
        ],
        "final_resolved_shear_util": runtime_setup_scope["final_resolved_shear_util"],
        "final_resolved_web_util": runtime_setup_scope["final_resolved_web_util"],
        "step_committable_eval_trace": runtime_setup_scope["step_committable_eval_trace"],
        "target_band_domain": runtime_setup_scope["target_band_domain"],
        "target_domains_for_band": runtime_setup_scope["target_domains_for_band"],
        "init_worst": runtime_setup_scope["init_worst"],
        "init_pass": runtime_setup_scope["init_pass"],
        "init_progress": runtime_setup_scope["init_progress"],
        "init_eval": runtime_setup_scope["init_eval"],
        "early_in_band_exit_blocked_for_tightening": runtime_setup_scope[
            "early_in_band_exit_blocked_for_tightening"
        ],
        "early_in_band_exit_tightening_classification": runtime_setup_scope[
            "early_in_band_exit_tightening_classification"
        ],
        "early_in_band_exit_available_tightening_paths": runtime_setup_scope[
            "early_in_band_exit_available_tightening_paths"
        ],
        "early_in_band_exit_reason": runtime_setup_scope["early_in_band_exit_reason"],
        "seen_sigs": solver_iteration_state["seen_sigs"],
        "step_trace": solver_iteration_state["step_trace"],
        "stop_reason": solver_iteration_state["stop_reason"],
        "status": solver_iteration_state["status"],
        "winning_label": solver_iteration_state["winning_label"],
        "winning_action_type": solver_iteration_state["winning_action_type"],
        "final_governing_domain": solver_iteration_state["final_governing_domain"],
        "rejected_as_non_governing_cleanup": solver_iteration_state[
            "rejected_as_non_governing_cleanup"
        ],
        "rejected_as_non_governing_shear_strengthening": solver_iteration_state[
            "rejected_as_non_governing_shear_strengthening"
        ],
        "shear_remove_links_candidate_seen": solver_iteration_state[
            "shear_remove_links_candidate_seen"
        ],
        "shear_remove_links_candidate_truth_ok": solver_iteration_state[
            "shear_remove_links_candidate_truth_ok"
        ],
        "shear_remove_links_candidate_dropped_reason": solver_iteration_state[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "shear_remove_links_candidate_materiality": solver_iteration_state[
            "shear_remove_links_candidate_materiality"
        ],
    }


def _prepare_one_click_solver_runtime_setup_after_mode_budget_state_coordinator(
    *,
    runtime_setup_scope: dict,
    solver_mode_budget_state: dict,
) -> dict:
    runtime_ready_scope = dict(runtime_setup_scope)
    runtime_ready_scope.update(solver_mode_budget_state)

    solver_initial_eval_state = _prepare_one_click_solver_initial_eval_state_coordinator(
        working=runtime_ready_scope["working"],
        mode_config=runtime_ready_scope["mode_config"],
        trace_callback=runtime_ready_scope["trace_callback"],
    )
    init_eval = solver_initial_eval_state["init_eval"]
    if init_eval is None:
        return {
            "should_return": True,
            "return_result": _build_evaluate_failed_solver_return_coordinator(
                working=runtime_ready_scope["working"],
                t_lo=runtime_ready_scope["t_lo"],
                t_hi=runtime_ready_scope["t_hi"],
                rid=runtime_ready_scope["rid"],
                trace_callback=runtime_ready_scope["trace_callback"],
            ),
        }
    runtime_ready_scope.update(
        {
            "init_eval": init_eval,
            "target_band_domain": solver_initial_eval_state["target_band_domain"],
            "target_domains_for_band": solver_initial_eval_state[
                "target_domains_for_band"
            ],
            "init_worst": solver_initial_eval_state["init_worst"],
            "init_pass": solver_initial_eval_state["init_pass"],
            "init_in_band": solver_initial_eval_state["init_in_band"],
            "init_progress": solver_initial_eval_state["init_progress"],
        }
    )

    early_in_band_gate_state = _prepare_one_click_solver_early_in_band_gate_state_coordinator(
        working=runtime_ready_scope["working"],
        init_eval=runtime_ready_scope["init_eval"],
        mode_config=runtime_ready_scope["mode_config"],
        init_pass=runtime_ready_scope["init_pass"],
        init_in_band=runtime_ready_scope["init_in_band"],
    )
    runtime_ready_scope.update(
        {
            "early_in_band_exit_blocked_for_tightening": early_in_band_gate_state[
                "early_in_band_exit_blocked_for_tightening"
            ],
            "early_in_band_exit_tightening_classification": early_in_band_gate_state[
                "early_in_band_exit_tightening_classification"
            ],
            "early_in_band_exit_available_tightening_paths": early_in_band_gate_state[
                "early_in_band_exit_available_tightening_paths"
            ],
            "early_in_band_exit_reason": early_in_band_gate_state[
                "early_in_band_exit_reason"
            ],
        }
    )
    if early_in_band_gate_state["should_return_already_in_band"]:
        return {
            "should_return": True,
            "return_result": _build_already_in_band_solver_return_coordinator(
                working=runtime_ready_scope["working"],
                init_worst=runtime_ready_scope["init_worst"],
                t_lo=runtime_ready_scope["t_lo"],
                t_hi=runtime_ready_scope["t_hi"],
                rid=runtime_ready_scope["rid"],
                early_in_band_exit_blocked_for_tightening=runtime_ready_scope[
                    "early_in_band_exit_blocked_for_tightening"
                ],
                early_in_band_exit_tightening_classification=runtime_ready_scope[
                    "early_in_band_exit_tightening_classification"
                ],
                early_in_band_exit_available_tightening_paths=runtime_ready_scope[
                    "early_in_band_exit_available_tightening_paths"
                ],
                early_in_band_exit_reason=runtime_ready_scope[
                    "early_in_band_exit_reason"
                ],
                trace_callback=runtime_ready_scope["trace_callback"],
            ),
        }

    runtime_ready_scope[
        "solver_iteration_state"
    ] = _prepare_one_click_solver_iteration_state_coordinator(
        init_eval=runtime_ready_scope["init_eval"]
    )
    return _build_one_click_solver_runtime_setup_ready_state_coordinator(
        runtime_setup_scope=runtime_ready_scope,
    )


def _prepare_one_click_solver_runtime_setup_after_initial_state_coordinator(
    *,
    runtime_setup_scope: dict,
    solver_initial_state: dict,
) -> dict:
    runtime_after_initial_scope = dict(runtime_setup_scope)
    runtime_after_initial_scope.update(
        {
            "rid": solver_initial_state["rid"],
            "stop_traced": solver_initial_state["stop_traced"],
            "rescue_debug": solver_initial_state["rescue_debug"],
            "attempted_seed_keys": solver_initial_state["attempted_seed_keys"],
            "trace_callback": solver_initial_state["trace_callback"],
            "initial_snapshot": solver_initial_state["initial_snapshot"],
            "initial_coherence": solver_initial_state["initial_coherence"],
            "initial_pack_valid": bool(solver_initial_state["initial_pack_valid"]),
            "initial_coherence_should_block": bool(
                solver_initial_state["initial_coherence_should_block"]
            ),
            "initial_stop_reason": solver_initial_state["initial_stop_reason"],
        }
    )
    if (
        not runtime_after_initial_scope["initial_pack_valid"]
    ) or runtime_after_initial_scope["initial_coherence_should_block"]:
        return {
            "should_return": True,
            "return_result": _build_initial_blocked_solver_return_coordinator(
                initial_snapshot=runtime_after_initial_scope["initial_snapshot"],
                initial_coherence=runtime_after_initial_scope["initial_coherence"],
                initial_pack_valid=runtime_after_initial_scope["initial_pack_valid"],
                initial_stop_reason=runtime_after_initial_scope["initial_stop_reason"],
                rid=runtime_after_initial_scope["rid"],
                trace_callback=runtime_after_initial_scope["trace_callback"],
            ),
        }

    solver_mode_budget_state = _prepare_one_click_solver_mode_budget_state_coordinator(
        initial_snapshot=runtime_after_initial_scope["initial_snapshot"],
        max_steps=runtime_after_initial_scope["max_steps"],
    )
    return _prepare_one_click_solver_runtime_setup_after_mode_budget_state_coordinator(
        runtime_setup_scope=runtime_after_initial_scope,
        solver_mode_budget_state=solver_mode_budget_state,
    )


def _prepare_one_click_solver_runtime_setup_state_coordinator(
    *,
    state: dict,
    max_steps: int,
    trace_run_id: str | None,
    trace_source: str,
    rescue_attempted_seed_keys: tuple[str, ...],
) -> dict:
    solver_initial_state = _prepare_one_click_solver_initial_state_coordinator(
        state=state,
        trace_run_id=trace_run_id,
        trace_source=trace_source,
        rescue_attempted_seed_keys=rescue_attempted_seed_keys,
    )
    return _prepare_one_click_solver_runtime_setup_after_initial_state_coordinator(
        runtime_setup_scope=locals(),
        solver_initial_state=solver_initial_state,
    )


def _handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(
    *,
    scored: list[dict],
    cur_eval: dict,
    working: dict,
    mode_config: OneClickModeConfig,
    tightening_mode_active: bool,
) -> dict:
    fallback_next_hop_injected = False
    fallback_next_hop_reason = None
    if not scored:
        still_under_for_fallback = bool(
            _one_click_still_materially_under_target(cur_eval, mode_config, margin=0.03)
        )
        next_hop_payload = None
        if tightening_mode_active and still_under_for_fallback:
            next_hop_payload = _one_click_best_next_hop_improving_candidate(cur_eval, mode_config)
        if _one_click_exhaustion_next_hop_allowed(cur_eval, next_hop_payload, mode_config):
            hop_updates = dict(next_hop_payload.get("updates") or {})
            if not hop_updates:
                hop_updates = _one_click_diff_accumulated_updates(
                    dict(working or {}),
                    dict(next_hop_payload.get("state") or {}),
                )
            if hop_updates:
                hop_eval = dict(next_hop_payload.get("eval") or {})
                fallback_row = _build_target_band_fallback_scored_candidate(
                    next_hop_payload=next_hop_payload,
                    updates=hop_updates,
                    signature=_candidate_state_signature(hop_eval),
                )
                if fallback_row:
                    scored.append(fallback_row)
                    fallback_next_hop_injected = True
                    fallback_next_hop_reason = "guidance_exhausted_but_refinement_next_hop_exists"
    return {
        "scored": scored,
        "fallback_next_hop_injected": fallback_next_hop_injected,
        "fallback_next_hop_reason": fallback_next_hop_reason,
    }


def _handle_one_click_solver_candidate_fallback_pool_trace_coordinator(
    *,
    scored: list[dict],
    cur_eval: dict,
    working: dict,
    mode_config: OneClickModeConfig,
    tightening_mode_active: bool,
    step_idx: int,
    raw_n: int,
    pool_labels: list,
    governing_domain,
    tightening_meta: dict,
    material_improvement_threshold,
    reduction_candidates_considered: int,
    growth_candidates_rejected_in_tightening: int,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    rejected_as_non_material_improvement: int,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: str,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list[str],
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: int,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    domain_match_prune_used: bool,
    shear_prune_rule_source,
    trace_callback,
) -> dict:
    fallback_next_hop_state = (
        _handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(
            scored=scored,
            cur_eval=cur_eval,
            working=working,
            mode_config=mode_config,
            tightening_mode_active=tightening_mode_active,
        )
    )
    scored = fallback_next_hop_state["scored"]
    fallback_next_hop_injected = fallback_next_hop_state["fallback_next_hop_injected"]
    fallback_next_hop_reason = fallback_next_hop_state["fallback_next_hop_reason"]

    _trace_candidate_pool_solver_coordinator(
        step_idx=step_idx,
        raw_n=raw_n,
        scored=scored,
        pool_labels=pool_labels,
        tightening_mode_active=tightening_mode_active,
        governing_domain=governing_domain,
        tightening_meta=tightening_meta,
        material_improvement_threshold=material_improvement_threshold,
        reduction_candidates_considered=reduction_candidates_considered,
        growth_candidates_rejected_in_tightening=growth_candidates_rejected_in_tightening,
        rejected_as_non_governing_cleanup=rejected_as_non_governing_cleanup,
        rejected_as_non_governing_shear_strengthening=rejected_as_non_governing_shear_strengthening,
        rejected_as_non_material_improvement=rejected_as_non_material_improvement,
        tightening_step_count=tightening_step_count,
        max_tightening_steps=max_tightening_steps,
        cur_eval=cur_eval,
        mode_config=mode_config,
        no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
        candidate_family_depth_reached=candidate_family_depth_reached,
        shear_governing_mode_active=shear_governing_mode_active,
        shear_severity_band=shear_severity_band,
        shear_candidate_family_order=shear_candidate_family_order,
        spacing_candidates_considered=spacing_candidates_considered,
        leg_candidates_considered=leg_candidates_considered,
        dia_candidates_considered=dia_candidates_considered,
        geometry_candidates_considered_for_shear=geometry_candidates_considered_for_shear,
        combined_candidates_considered_for_shear=combined_candidates_considered_for_shear,
        web_crushing_penalty_applied=web_crushing_penalty_applied,
        rejected_as_spacing_too_weak=rejected_as_spacing_too_weak,
        rejected_as_web_crushing_marginal=rejected_as_web_crushing_marginal,
        rejected_as_impractical_shear_layout=rejected_as_impractical_shear_layout,
        shear_governing_family_detected=shear_governing_family_detected,
        governing_family_exists_after_domain_fix=governing_family_exists_after_domain_fix,
        pruned_non_shear_family_count=pruned_non_shear_family_count,
        domain_match_prune_used=domain_match_prune_used,
        shear_prune_rule_source=shear_prune_rule_source,
        fallback_next_hop_injected=fallback_next_hop_injected,
        fallback_next_hop_reason=fallback_next_hop_reason,
        trace_callback=trace_callback,
    )
    return {
        "scored": scored,
        "fallback_next_hop_injected": fallback_next_hop_injected,
        "fallback_next_hop_reason": fallback_next_hop_reason,
    }


def _handle_one_click_solver_no_scored_stop_branch_coordinator(
    *,
    scored: list[dict],
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    governing_domain: str | None,
    tightening_mode_active: bool,
    rejected_as_non_material_improvement: int,
    no_actionable_after_full_tightening_search: bool,
    cur_ib: bool,
    cur_pass: bool,
    winning_label,
    winning_action_type,
    tightening_step_count: int,
    max_tightening_steps: int,
    candidate_family_depth_reached,
    trace_callback,
) -> dict:
    if scored:
        return {
            "stop_reason": None,
            "status": None,
            "final_distance_to_band": None,
            "no_actionable_after_full_tightening_search": no_actionable_after_full_tightening_search,
            "should_break": False,
        }
    (
        stop_reason,
        status,
        final_distance_to_band,
        no_actionable_after_full_tightening_search,
    ) = _trace_no_actionable_candidates_solver_stop_coordinator(
        cur_eval=cur_eval,
        mode_config=mode_config,
        step_trace=step_trace,
        initial_snapshot=initial_snapshot,
        working=working,
        governing_domain=governing_domain,
        tightening_mode_active=tightening_mode_active,
        rejected_as_non_material_improvement=rejected_as_non_material_improvement,
        no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
        cur_ib=cur_ib,
        cur_pass=cur_pass,
        winning_label=winning_label,
        winning_action_type=winning_action_type,
        tightening_step_count=tightening_step_count,
        max_tightening_steps=max_tightening_steps,
        candidate_family_depth_reached=candidate_family_depth_reached,
        trace_callback=trace_callback,
    )
    return {
        "stop_reason": stop_reason,
        "status": status,
        "final_distance_to_band": final_distance_to_band,
        "no_actionable_after_full_tightening_search": no_actionable_after_full_tightening_search,
        "should_break": True,
    }


def _handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(
    *,
    scored: list[dict],
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    step_idx: int,
    cur_pass: bool,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    winning_label,
    winning_action_type,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached,
    in_band_shear_cleanup_deferral: dict,
    trace_callback,
) -> dict:
    best = _select_target_band_ranked_candidate(scored) or scored[0]
    best_distance_to_band_this_iteration = _candidate_target_band_distance(best["eval"], mode_config)
    allow_in_band_shear_cleanup_candidate = bool(
        bool(in_band_shear_cleanup_deferral.get("active"))
        and _one_click_in_band_shear_cleanup_candidate_allowed(
            cur_eval,
            best.get("eval"),
            best.get("updates"),
            mode_config,
        )
    )
    selected_candidate_acceptance = _resolve_target_band_selected_candidate_acceptance(
        candidate_improves=_one_click_step_improves(best["eval"], cur_eval, mode_config),
        allow_in_band_shear_cleanup_candidate=allow_in_band_shear_cleanup_candidate,
    )
    if not bool(selected_candidate_acceptance.get("accepted")):
        stop_reason, status = _trace_rejected_best_candidate_solver_stop_coordinator(
            selected_candidate_acceptance=selected_candidate_acceptance,
            best=best,
            mode_config=mode_config,
            step_idx=step_idx,
            cur_eval=cur_eval,
            cur_pass=cur_pass,
            step_trace=step_trace,
            initial_snapshot=initial_snapshot,
            working=working,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            tightening_step_count=tightening_step_count,
            max_tightening_steps=max_tightening_steps,
            no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
            candidate_family_depth_reached=candidate_family_depth_reached,
            best_distance_to_band_this_iteration=best_distance_to_band_this_iteration,
            in_band_shear_cleanup_deferral=in_band_shear_cleanup_deferral,
            trace_callback=trace_callback,
        )
        return {
            "best": best,
            "best_distance_to_band_this_iteration": best_distance_to_band_this_iteration,
            "selected_candidate_acceptance": selected_candidate_acceptance,
            "stop_reason": stop_reason,
            "status": status,
            "should_break": True,
        }
    return {
        "best": best,
        "best_distance_to_band_this_iteration": best_distance_to_band_this_iteration,
        "selected_candidate_acceptance": selected_candidate_acceptance,
        "stop_reason": None,
        "status": None,
        "should_break": False,
    }


def _handle_one_click_solver_candidate_selection_or_stop_coordinator(
    *,
    scored: list[dict],
    cur_eval: dict,
    mode_config: OneClickModeConfig,
    step_idx: int,
    cur_pass: bool,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    governing_domain: str | None,
    tightening_mode_active: bool,
    rejected_as_non_material_improvement: int,
    no_actionable_after_full_tightening_search: bool,
    cur_ib: bool,
    winning_label,
    winning_action_type,
    tightening_step_count: int,
    max_tightening_steps: int,
    candidate_family_depth_reached,
    in_band_shear_cleanup_deferral: dict,
    trace_callback,
) -> dict:
    no_scored_stop_branch_state = _handle_one_click_solver_no_scored_stop_branch_coordinator(
        scored=scored,
        cur_eval=cur_eval,
        mode_config=mode_config,
        step_trace=step_trace,
        initial_snapshot=initial_snapshot,
        working=working,
        governing_domain=governing_domain,
        tightening_mode_active=tightening_mode_active,
        rejected_as_non_material_improvement=rejected_as_non_material_improvement,
        no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
        cur_ib=cur_ib,
        cur_pass=cur_pass,
        winning_label=winning_label,
        winning_action_type=winning_action_type,
        tightening_step_count=tightening_step_count,
        max_tightening_steps=max_tightening_steps,
        candidate_family_depth_reached=candidate_family_depth_reached,
        trace_callback=trace_callback,
    )
    if no_scored_stop_branch_state["should_break"]:
        return {
            "best": None,
            "best_distance_to_band_this_iteration": None,
            "selected_candidate_acceptance": None,
            "stop_reason": no_scored_stop_branch_state["stop_reason"],
            "status": no_scored_stop_branch_state["status"],
            "final_distance_to_band": no_scored_stop_branch_state["final_distance_to_band"],
            "no_actionable_after_full_tightening_search": no_scored_stop_branch_state[
                "no_actionable_after_full_tightening_search"
            ],
            "should_break": True,
        }

    selected_candidate_acceptance_gate_state = (
        _handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(
            scored=scored,
            cur_eval=cur_eval,
            mode_config=mode_config,
            step_idx=step_idx,
            cur_pass=cur_pass,
            step_trace=step_trace,
            initial_snapshot=initial_snapshot,
            working=working,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            tightening_step_count=tightening_step_count,
            max_tightening_steps=max_tightening_steps,
            no_actionable_after_full_tightening_search=(
                no_actionable_after_full_tightening_search
            ),
            candidate_family_depth_reached=candidate_family_depth_reached,
            in_band_shear_cleanup_deferral=in_band_shear_cleanup_deferral,
            trace_callback=trace_callback,
        )
    )
    return {
        "best": selected_candidate_acceptance_gate_state["best"],
        "best_distance_to_band_this_iteration": selected_candidate_acceptance_gate_state[
            "best_distance_to_band_this_iteration"
        ],
        "selected_candidate_acceptance": selected_candidate_acceptance_gate_state[
            "selected_candidate_acceptance"
        ],
        "stop_reason": selected_candidate_acceptance_gate_state["stop_reason"],
        "status": selected_candidate_acceptance_gate_state["status"],
        "final_distance_to_band": None,
        "no_actionable_after_full_tightening_search": (
            no_actionable_after_full_tightening_search
        ),
        "should_break": selected_candidate_acceptance_gate_state["should_break"],
    }


def _handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator(
    *,
    best: dict,
    mode_config: dict,
    step_idx: int,
    tightening_step_count: int,
    max_tightening_steps: int,
    candidate_family_depth_reached: str,
    best_distance_to_band_this_iteration,
    initial_snapshot: dict,
    working: dict,
    step_trace: list[dict],
    winning_label: str | None,
    winning_action_type: str | None,
    target_domains_for_band,
    target_band_domain: str | None,
    seen_sigs: set,
    trace_callback,
) -> dict:
    _trace_accepted_best_candidate_solver_iteration_coordinator(
        best=best,
        mode_config=mode_config,
        step_idx=step_idx,
        tightening_step_count=tightening_step_count,
        max_tightening_steps=max_tightening_steps,
        candidate_family_depth_reached=candidate_family_depth_reached,
        best_distance_to_band_this_iteration=best_distance_to_band_this_iteration,
        trace_callback=trace_callback,
    )

    step_base = copy.deepcopy(working)
    working.update(best["updates"])
    working = _build_canonical_design_state_pack(working)
    w_eval = evaluate_candidate_full(
        _build_canonical_design_state_pack(working),
        source=f"one_click_after_step_{step_idx}",
        label=best["label"],
        action_type=best["action_type"],
        updates=dict(best["updates"]),
    )
    if w_eval is None:
        working, stop_reason, status = _trace_evaluate_failed_after_apply_solver_stop_coordinator(
            step_base=step_base,
            step_trace=step_trace,
            initial_snapshot=initial_snapshot,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            trace_callback=trace_callback,
        )
        return {
            "working": working,
            "w_eval": None,
            "accumulated_updates": None,
            "target_domains": None,
            "stop_reason": stop_reason,
            "status": status,
            "should_break": True,
        }

    _w_stat = dict((w_eval.get("overview") or {}).get("statuses") or {})
    _w_shear_st = _w_stat.get("shear")
    _w_shear_failing = bool(
        _w_shear_st == BEAM_STATUS_FAIL or str(_w_shear_st or "").strip().upper() == "FAIL",
    )
    accumulated_updates = _one_click_diff_accumulated_updates(initial_snapshot, working)
    target_domains = _one_click_target_domains_for_eval(target_domains_for_band, accumulated_updates)
    _one_click_attach_eval_target_domains(w_eval, target_domains, mode_config)
    if not target_domains:
        if target_band_domain == "shear" and _w_shear_failing:
            w_eval["target_domain_for_band"] = "shear"
        else:
            w_eval.pop("target_domain_for_band", None)

    wsig = _candidate_state_signature(w_eval)
    if wsig and wsig in seen_sigs:
        working, stop_reason, status = _trace_repeated_state_solver_stop_coordinator(
            step_base=step_base,
            w_eval=w_eval,
            step_trace=step_trace,
            initial_snapshot=initial_snapshot,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            trace_callback=trace_callback,
        )
        return {
            "working": working,
            "w_eval": w_eval,
            "accumulated_updates": accumulated_updates,
            "target_domains": target_domains,
            "stop_reason": stop_reason,
            "status": status,
            "should_break": True,
        }
    if wsig:
        seen_sigs.add(wsig)
    bsig = best.get("signature")
    if bsig:
        seen_sigs.add(bsig)

    return {
        "working": working,
        "w_eval": w_eval,
        "accumulated_updates": accumulated_updates,
        "target_domains": target_domains,
        "stop_reason": None,
        "status": None,
        "should_break": False,
    }


def _handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator(
    *,
    best: dict,
    mode_config: dict,
    step_idx: int,
    initial_snapshot: dict,
    accumulated_updates: dict,
    w_eval: dict,
    governing_domain: str | None,
    tightening_mode_active: bool,
    tightening_step_count: int,
    step_trace: list[dict],
    step_committable_eval_trace: list[dict],
) -> dict:
    winning_label = str(best.get("label") or "")
    winning_action_type = str(best.get("action_type") or "")
    winning_updates = dict(best.get("updates") or {})
    if governing_domain == "shear" and any(k in winning_updates for k in ("D", "b", "bw")) and any(
        k in winning_updates for k in ("lig_d", "lig_legs", "s_lig")
    ):
        winning_label = "Combined shear + geometry tightening"
    if tightening_mode_active:
        tightening_step_count += 1
    step_trace.append(
        {
            "step": step_idx + 1,
            "label": winning_label,
            "action_type": winning_action_type,
            "worst_util": best["worst_util"],
            "all_key_pass": bool((best["eval"].get("overview") or {}).get("all_key_pass")),
            "reached_target_band": _candidate_in_target_band(best["eval"], mode_config),
            "change_summary": best.get("change_summary"),
        },
    )

    w_commit_eval, w_commit_sanitized_updates, _ = _one_click_committable_candidate_eval(
        initial_snapshot,
        accumulated_updates,
        source=f"one_click_after_step_{step_idx}_committable",
        label=winning_label,
        action_type=winning_action_type,
    )
    w_gate_eval = w_commit_eval or w_eval
    step_committable_eval_trace.append(
        {
            "step": step_idx,
            "winning_label": winning_label,
            "internal_preview_worst_util": float((w_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
            "committable_preview_worst_util": (
                None
                if not isinstance(w_commit_eval, dict)
                else float((w_commit_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0)
            ),
            "committable_preview_updates": dict(w_commit_sanitized_updates or {}),
        },
    )
    return {
        "winning_label": winning_label,
        "winning_action_type": winning_action_type,
        "tightening_step_count": tightening_step_count,
        "w_gate_eval": w_gate_eval,
    }


def _handle_one_click_solver_post_step_metrics_and_trace_coordinator(
    *,
    w_gate_eval: dict,
    working: dict,
    mode_config: dict,
    step_idx: int,
    governing_domain: str | None,
    tightening_mode_active: bool,
    tightening_step_count: int,
    max_tightening_steps: int,
    winning_label: str | None,
    winning_action_type: str | None,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: str,
    best_distance_to_band_this_iteration,
    shear_governing_mode_active: bool,
    shear_severity_band: str | None,
    shear_candidate_family_order,
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: int,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    final_resolved_shear_util,
    final_resolved_web_util,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    trace_callback,
) -> dict:
    w_pass = bool((w_gate_eval.get("overview") or {}).get("all_key_pass"))
    unresolved_spacing_fail_after_step = bool(
        governing_domain == "shear"
        and _one_click_has_unresolved_spacing_envelope_fail(w_gate_eval)
    )
    still_under_after_step = bool(_one_click_still_materially_under_target(w_gate_eval, mode_config, margin=0.03))
    continuing_tightening_after_step = bool(
        tightening_mode_active
        and w_pass
        and still_under_after_step
        and tightening_step_count <= max_tightening_steps
    )
    final_distance_to_band = _candidate_target_band_distance(w_gate_eval, mode_config)
    shear_after = _evaluate_shear_with_state(w_gate_eval.get("state") or working) if governing_domain == "shear" else None
    if isinstance(shear_after, dict):
        try:
            final_resolved_shear_util = float(shear_after.get("util")) if shear_after.get("util") is not None else final_resolved_shear_util
        except Exception:
            pass
        try:
            final_resolved_web_util = float(shear_after.get("web_util")) if shear_after.get("web_util") is not None else final_resolved_web_util
        except Exception:
            pass
    _trace_post_step_solver_iteration_coordinator(
        w_gate_eval=w_gate_eval,
        mode_config=mode_config,
        step_idx=step_idx,
        winning_label=winning_label,
        winning_action_type=winning_action_type,
        tightening_step_count=tightening_step_count,
        max_tightening_steps=max_tightening_steps,
        continuing_tightening_after_step=continuing_tightening_after_step,
        still_under_after_step=still_under_after_step,
        no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
        candidate_family_depth_reached=candidate_family_depth_reached,
        best_distance_to_band_this_iteration=best_distance_to_band_this_iteration,
        final_distance_to_band=final_distance_to_band,
        unresolved_spacing_fail_after_step=unresolved_spacing_fail_after_step,
        shear_governing_mode_active=shear_governing_mode_active,
        shear_severity_band=shear_severity_band,
        shear_candidate_family_order=shear_candidate_family_order,
        spacing_candidates_considered=spacing_candidates_considered,
        leg_candidates_considered=leg_candidates_considered,
        dia_candidates_considered=dia_candidates_considered,
        geometry_candidates_considered_for_shear=geometry_candidates_considered_for_shear,
        combined_candidates_considered_for_shear=combined_candidates_considered_for_shear,
        web_crushing_penalty_applied=web_crushing_penalty_applied,
        rejected_as_spacing_too_weak=rejected_as_spacing_too_weak,
        rejected_as_web_crushing_marginal=rejected_as_web_crushing_marginal,
        rejected_as_impractical_shear_layout=rejected_as_impractical_shear_layout,
        final_resolved_shear_util=final_resolved_shear_util,
        final_resolved_web_util=final_resolved_web_util,
        shear_governing_family_detected=shear_governing_family_detected,
        governing_family_exists_after_domain_fix=governing_family_exists_after_domain_fix,
        pruned_non_shear_family_count=pruned_non_shear_family_count,
        trace_callback=trace_callback,
    )
    return {
        "w_pass": w_pass,
        "unresolved_spacing_fail_after_step": unresolved_spacing_fail_after_step,
        "still_under_after_step": still_under_after_step,
        "continuing_tightening_after_step": continuing_tightening_after_step,
        "final_distance_to_band": final_distance_to_band,
        "final_resolved_shear_util": final_resolved_shear_util,
        "final_resolved_web_util": final_resolved_web_util,
    }


def _build_one_click_solver_accepted_candidate_post_step_result_state_coordinator(
    *,
    accepted_post_step_scope: dict,
) -> dict:
    post_step_metrics_state = accepted_post_step_scope["post_step_metrics_state"]
    post_step_target_band_stop_gate_state = accepted_post_step_scope[
        "post_step_target_band_stop_gate_state"
    ]
    return {
        "working": accepted_post_step_scope["working"],
        "w_eval": accepted_post_step_scope["w_eval"],
        "accumulated_updates": accepted_post_step_scope["accumulated_updates"],
        "target_domains": accepted_post_step_scope["target_domains"],
        "winning_label": accepted_post_step_scope["winning_label"],
        "winning_action_type": accepted_post_step_scope["winning_action_type"],
        "tightening_step_count": accepted_post_step_scope["tightening_step_count"],
        "w_gate_eval": accepted_post_step_scope["w_gate_eval"],
        "w_pass": post_step_metrics_state["w_pass"],
        "unresolved_spacing_fail_after_step": post_step_metrics_state[
            "unresolved_spacing_fail_after_step"
        ],
        "still_under_after_step": post_step_metrics_state["still_under_after_step"],
        "continuing_tightening_after_step": post_step_metrics_state[
            "continuing_tightening_after_step"
        ],
        "final_distance_to_band": post_step_metrics_state["final_distance_to_band"],
        "final_resolved_shear_util": post_step_metrics_state["final_resolved_shear_util"],
        "final_resolved_web_util": post_step_metrics_state["final_resolved_web_util"],
        "stop_reason": post_step_target_band_stop_gate_state["stop_reason"],
        "status": post_step_target_band_stop_gate_state["status"],
        "should_break": post_step_target_band_stop_gate_state["should_break"],
    }


def _build_one_click_solver_apply_selected_candidate_break_state_coordinator(
    *,
    apply_selected_candidate_state: dict,
    working: dict,
    w_eval,
    accumulated_updates,
    target_domains,
    winning_label: str | None,
    winning_action_type: str | None,
    tightening_step_count: int,
    final_resolved_shear_util,
    final_resolved_web_util,
) -> dict:
    return {
        "working": working,
        "w_eval": w_eval,
        "accumulated_updates": accumulated_updates,
        "target_domains": target_domains,
        "winning_label": winning_label,
        "winning_action_type": winning_action_type,
        "tightening_step_count": tightening_step_count,
        "w_gate_eval": None,
        "w_pass": None,
        "unresolved_spacing_fail_after_step": None,
        "still_under_after_step": None,
        "continuing_tightening_after_step": None,
        "final_distance_to_band": None,
        "final_resolved_shear_util": final_resolved_shear_util,
        "final_resolved_web_util": final_resolved_web_util,
        "stop_reason": apply_selected_candidate_state["stop_reason"],
        "status": apply_selected_candidate_state["status"],
        "should_break": True,
    }


def _dispatch_one_click_solver_post_step_metrics_and_trace_from_accepted_post_step_coordinator(
    *,
    accepted_post_step_scope: dict,
) -> dict:
    return _handle_one_click_solver_post_step_metrics_and_trace_coordinator(
        w_gate_eval=accepted_post_step_scope["w_gate_eval"],
        working=accepted_post_step_scope["working"],
        mode_config=accepted_post_step_scope["mode_config"],
        step_idx=accepted_post_step_scope["step_idx"],
        governing_domain=accepted_post_step_scope["governing_domain"],
        tightening_mode_active=accepted_post_step_scope["tightening_mode_active"],
        tightening_step_count=accepted_post_step_scope["tightening_step_count"],
        max_tightening_steps=accepted_post_step_scope["max_tightening_steps"],
        winning_label=accepted_post_step_scope["winning_label"],
        winning_action_type=accepted_post_step_scope["winning_action_type"],
        no_actionable_after_full_tightening_search=accepted_post_step_scope[
            "no_actionable_after_full_tightening_search"
        ],
        candidate_family_depth_reached=accepted_post_step_scope[
            "candidate_family_depth_reached"
        ],
        best_distance_to_band_this_iteration=accepted_post_step_scope[
            "best_distance_to_band_this_iteration"
        ],
        shear_governing_mode_active=accepted_post_step_scope[
            "shear_governing_mode_active"
        ],
        shear_severity_band=accepted_post_step_scope["shear_severity_band"],
        shear_candidate_family_order=accepted_post_step_scope[
            "shear_candidate_family_order"
        ],
        spacing_candidates_considered=accepted_post_step_scope[
            "spacing_candidates_considered"
        ],
        leg_candidates_considered=accepted_post_step_scope["leg_candidates_considered"],
        dia_candidates_considered=accepted_post_step_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=accepted_post_step_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=accepted_post_step_scope[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=accepted_post_step_scope[
            "web_crushing_penalty_applied"
        ],
        rejected_as_spacing_too_weak=accepted_post_step_scope[
            "rejected_as_spacing_too_weak"
        ],
        rejected_as_web_crushing_marginal=accepted_post_step_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=accepted_post_step_scope[
            "rejected_as_impractical_shear_layout"
        ],
        final_resolved_shear_util=accepted_post_step_scope[
            "final_resolved_shear_util"
        ],
        final_resolved_web_util=accepted_post_step_scope["final_resolved_web_util"],
        shear_governing_family_detected=accepted_post_step_scope[
            "shear_governing_family_detected"
        ],
        governing_family_exists_after_domain_fix=accepted_post_step_scope[
            "governing_family_exists_after_domain_fix"
        ],
        pruned_non_shear_family_count=accepted_post_step_scope[
            "pruned_non_shear_family_count"
        ],
        trace_callback=accepted_post_step_scope["trace_callback"],
    )


def _handle_one_click_solver_accepted_candidate_apply_flow_coordinator(
    *,
    accepted_post_step_scope: dict,
) -> dict:
    apply_selected_candidate_state = (
        _handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator(
            best=accepted_post_step_scope["best"],
            mode_config=accepted_post_step_scope["mode_config"],
            step_idx=accepted_post_step_scope["step_idx"],
            tightening_step_count=accepted_post_step_scope["tightening_step_count"],
            max_tightening_steps=accepted_post_step_scope["max_tightening_steps"],
            candidate_family_depth_reached=accepted_post_step_scope[
                "candidate_family_depth_reached"
            ],
            best_distance_to_band_this_iteration=accepted_post_step_scope[
                "best_distance_to_band_this_iteration"
            ],
            initial_snapshot=accepted_post_step_scope["initial_snapshot"],
            working=accepted_post_step_scope["working"],
            step_trace=accepted_post_step_scope["step_trace"],
            winning_label=accepted_post_step_scope["winning_label"],
            winning_action_type=accepted_post_step_scope["winning_action_type"],
            target_domains_for_band=accepted_post_step_scope[
                "target_domains_for_band"
            ],
            target_band_domain=accepted_post_step_scope["target_band_domain"],
            seen_sigs=accepted_post_step_scope["seen_sigs"],
            trace_callback=accepted_post_step_scope["trace_callback"],
        )
    )
    working = apply_selected_candidate_state["working"]
    w_eval = apply_selected_candidate_state["w_eval"]
    accumulated_updates = apply_selected_candidate_state["accumulated_updates"]
    target_domains = apply_selected_candidate_state["target_domains"]
    if apply_selected_candidate_state["should_break"]:
        return {
            "should_return": True,
            "result": _build_one_click_solver_apply_selected_candidate_break_state_coordinator(
                apply_selected_candidate_state=apply_selected_candidate_state,
                working=working,
                w_eval=w_eval,
                accumulated_updates=accumulated_updates,
                target_domains=target_domains,
                winning_label=accepted_post_step_scope["winning_label"],
                winning_action_type=accepted_post_step_scope["winning_action_type"],
                tightening_step_count=accepted_post_step_scope[
                    "tightening_step_count"
                ],
                final_resolved_shear_util=accepted_post_step_scope[
                    "final_resolved_shear_util"
                ],
                final_resolved_web_util=accepted_post_step_scope[
                    "final_resolved_web_util"
                ],
            ),
        }
    return {
        "should_return": False,
        "working": working,
        "w_eval": w_eval,
        "accumulated_updates": accumulated_updates,
        "target_domains": target_domains,
    }


def _handle_one_click_solver_accepted_candidate_post_step_coordinator(
    *,
    best: dict,
    mode_config: dict,
    step_idx: int,
    tightening_step_count: int,
    max_tightening_steps: int,
    candidate_family_depth_reached: str,
    best_distance_to_band_this_iteration,
    initial_snapshot: dict,
    working: dict,
    step_trace: list[dict],
    winning_label: str | None,
    winning_action_type: str | None,
    target_domains_for_band,
    target_band_domain: str | None,
    seen_sigs: set,
    governing_domain: str | None,
    tightening_mode_active: bool,
    step_committable_eval_trace: list[dict],
    no_actionable_after_full_tightening_search: bool,
    shear_governing_mode_active: bool,
    shear_severity_band: str | None,
    shear_candidate_family_order,
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: int,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    final_resolved_shear_util,
    final_resolved_web_util,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    trace_callback,
) -> dict:
    apply_flow_state = _handle_one_click_solver_accepted_candidate_apply_flow_coordinator(
        accepted_post_step_scope=locals(),
    )
    if apply_flow_state["should_return"]:
        return apply_flow_state["result"]
    working = apply_flow_state["working"]
    w_eval = apply_flow_state["w_eval"]
    accumulated_updates = apply_flow_state["accumulated_updates"]
    target_domains = apply_flow_state["target_domains"]

    post_apply_trace_state = (
        _handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator(
            best=best,
            mode_config=mode_config,
            step_idx=step_idx,
            initial_snapshot=initial_snapshot,
            accumulated_updates=accumulated_updates,
            w_eval=w_eval,
            governing_domain=governing_domain,
            tightening_mode_active=tightening_mode_active,
            tightening_step_count=tightening_step_count,
            step_trace=step_trace,
            step_committable_eval_trace=step_committable_eval_trace,
        )
    )
    winning_label = post_apply_trace_state["winning_label"]
    winning_action_type = post_apply_trace_state["winning_action_type"]
    tightening_step_count = post_apply_trace_state["tightening_step_count"]
    w_gate_eval = post_apply_trace_state["w_gate_eval"]
    post_step_metrics_state = (
        _dispatch_one_click_solver_post_step_metrics_and_trace_from_accepted_post_step_coordinator(
            accepted_post_step_scope=locals(),
        )
    )
    post_step_target_band_stop_gate_state = (
        _handle_one_click_solver_post_step_target_band_stop_gate_coordinator(
            w_pass=post_step_metrics_state["w_pass"],
            w_gate_eval=w_gate_eval,
            mode_config=mode_config,
            unresolved_spacing_fail_after_step=post_step_metrics_state[
                "unresolved_spacing_fail_after_step"
            ],
            step_trace=step_trace,
            initial_snapshot=initial_snapshot,
            working=working,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            tightening_step_count=tightening_step_count,
            max_tightening_steps=max_tightening_steps,
            no_actionable_after_full_tightening_search=(
                no_actionable_after_full_tightening_search
            ),
            candidate_family_depth_reached=candidate_family_depth_reached,
            final_distance_to_band=post_step_metrics_state["final_distance_to_band"],
            trace_callback=trace_callback,
        )
    )
    return _build_one_click_solver_accepted_candidate_post_step_result_state_coordinator(
        accepted_post_step_scope=locals(),
    )


def _handle_one_click_solver_post_step_target_band_stop_gate_coordinator(
    *,
    w_pass: bool,
    w_gate_eval: dict,
    mode_config: dict,
    unresolved_spacing_fail_after_step: bool,
    step_trace: list[dict],
    initial_snapshot: dict,
    working: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: str,
    final_distance_to_band,
    trace_callback,
) -> dict:
    if w_pass and _candidate_in_target_band(w_gate_eval, mode_config) and not unresolved_spacing_fail_after_step:
        stop_reason, status = _trace_post_step_reached_target_band_solver_stop_coordinator(
            w_gate_eval=w_gate_eval,
            step_trace=step_trace,
            initial_snapshot=initial_snapshot,
            working=working,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            tightening_step_count=tightening_step_count,
            max_tightening_steps=max_tightening_steps,
            no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
            candidate_family_depth_reached=candidate_family_depth_reached,
            final_distance_to_band=final_distance_to_band,
            trace_callback=trace_callback,
        )
        return {
            "stop_reason": stop_reason,
            "status": status,
            "should_break": True,
        }
    return {
        "stop_reason": None,
        "status": None,
        "should_break": False,
    }


def _prepare_one_click_solver_final_evaluation_state_coordinator(
    *,
    working: dict,
    initial_snapshot: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    target_domains_for_band,
    target_band_domain: str | None,
    mode_config: dict,
    init_worst,
    final_resolved_shear_util,
    final_resolved_web_util,
) -> dict:
    final_eval_internal = evaluate_candidate_full(
        _build_canonical_design_state_pack(working),
        source="one_click_final",
        label="Final",
        action_type="one_click",
        updates={},
    )
    final_updates = _one_click_diff_accumulated_updates(initial_snapshot, working)
    final_eval_committable, final_sanitized_updates, _ = _one_click_committable_candidate_eval(
        initial_snapshot,
        final_updates,
        source="one_click_final_committable",
        label=winning_label or "Final",
        action_type=winning_action_type or "one_click",
    )
    final_eval = final_eval_committable or final_eval_internal
    final_eval_internal_worst_util_dbg = (
        None
        if not isinstance(final_eval_internal, dict)
        else float(((final_eval_internal.get("overview") or {}).get("worst_util", 0.0) or 0.0))
    )
    final_eval_committable_worst_util_dbg = (
        None
        if not isinstance(final_eval_committable, dict)
        else float(((final_eval_committable.get("overview") or {}).get("worst_util", 0.0) or 0.0))
    )
    final_eval_used_source_dbg = (
        "committable_preview" if isinstance(final_eval_committable, dict) else "internal_working_preview"
    )
    final_eval_committable_updates_dbg = dict(final_sanitized_updates or {})
    final_target_domains: list[str] = []
    if isinstance(final_eval, dict):
        _f_stat = dict((final_eval.get("overview") or {}).get("statuses") or {})
        _f_shear_st = _f_stat.get("shear")
        _f_shear_failing = bool(
            _f_shear_st == BEAM_STATUS_FAIL or str(_f_shear_st or "").strip().upper() == "FAIL",
        )
        final_target_domains = _one_click_target_domains_for_eval(target_domains_for_band, final_updates)
        _one_click_attach_eval_target_domains(final_eval, final_target_domains, mode_config)
        if not final_target_domains:
            if target_band_domain == "shear" and _f_shear_failing:
                final_eval["target_domain_for_band"] = "shear"
            else:
                final_eval.pop("target_domain_for_band", None)
    final_worst = (
        float((final_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0) if final_eval is not None else init_worst
    )
    final_pass = bool((final_eval.get("overview") or {}).get("all_key_pass")) if final_eval is not None else False
    final_ok = _one_click_required_domains_satisfied(final_eval, mode_config) if final_eval is not None else False
    final_spacing_fail = bool(
        final_eval is not None and _one_click_has_unresolved_spacing_envelope_fail(final_eval)
    )
    if final_spacing_fail:
        final_pass = False
        final_ok = False
    final_in_band = final_ok
    final_band_hit = bool(
        final_eval is not None
        and (
            (
                final_pass
                and _candidate_in_target_band(final_eval, mode_config)
            )
            or _one_click_strict_target_band_ok((final_eval or {}).get("overview"), mode_config)
        )
        and not final_spacing_fail
    )
    if final_band_hit:
        final_ok = True
        final_in_band = True
    final_objective_util = _candidate_objective_util(final_eval or {})
    final_distance_to_band = _candidate_target_band_distance(final_eval or {}, mode_config)
    final_shear_preview = _evaluate_shear_with_state((final_eval or {}).get("state") or working)
    if isinstance(final_shear_preview, dict):
        try:
            final_resolved_shear_util = float(final_shear_preview.get("util")) if final_shear_preview.get("util") is not None else final_resolved_shear_util
        except Exception:
            pass
        try:
            final_resolved_web_util = float(final_shear_preview.get("web_util")) if final_shear_preview.get("web_util") is not None else final_resolved_web_util
        except Exception:
            pass
    return {
        "final_eval_internal": final_eval_internal,
        "final_updates": final_updates,
        "final_eval_committable": final_eval_committable,
        "final_sanitized_updates": final_sanitized_updates,
        "final_eval": final_eval,
        "final_eval_internal_worst_util_dbg": final_eval_internal_worst_util_dbg,
        "final_eval_committable_worst_util_dbg": final_eval_committable_worst_util_dbg,
        "final_eval_used_source_dbg": final_eval_used_source_dbg,
        "final_eval_committable_updates_dbg": final_eval_committable_updates_dbg,
        "final_target_domains": final_target_domains,
        "final_worst": final_worst,
        "final_pass": final_pass,
        "final_ok": final_ok,
        "final_spacing_fail": final_spacing_fail,
        "final_in_band": final_in_band,
        "final_band_hit": final_band_hit,
        "final_objective_util": final_objective_util,
        "final_distance_to_band": final_distance_to_band,
        "final_resolved_shear_util": final_resolved_shear_util,
        "final_resolved_web_util": final_resolved_web_util,
    }


def _handle_one_click_solver_partial_failing_final_updates_guard_coordinator(
    *,
    final_updates: dict,
    final_ok: bool,
    final_eval: dict | None,
    mode_config: dict,
    init_pass: bool,
    final_pass: bool,
    init_progress: dict,
    init_eval: dict,
    final_spacing_fail: bool,
    final_target_domains,
    stop_reason: str | None,
    winning_label: str | None,
    winning_action_type: str | None,
) -> dict:
    partial_failing_final_updates_blocked = False
    best_available_out_of_band_retained = False
    partial_failing_final_updates_raw = dict(final_updates or {})
    if final_updates and not final_ok:
        final_progress = _one_click_required_domain_progress(final_eval, mode_config) if final_eval is not None else {}
        overdesign_best_effort_allowed = bool(
            init_pass
            and final_pass
            and int(init_progress.get("required_fail_count", 0) or 0) == 0
            and int(final_progress.get("required_fail_count", 0) or 0) == 0
            and _one_click_step_improves(final_eval or {}, init_eval, mode_config)
        )
        failing_case_cleanup_allowed = bool(
            int(init_progress.get("required_fail_count", 0) or 0) > 0
            and int(final_progress.get("required_fail_count", 0) or 0)
            < int(init_progress.get("required_fail_count", 0) or 0)
            and _one_click_step_improves(final_eval or {}, init_eval, mode_config)
        )
        if final_spacing_fail:
            partial_failing_final_updates_blocked = True
            final_updates = {}
            stop_reason = "minimum_shear_detailing_limit"
            winning_label = None
            winning_action_type = None
        elif overdesign_best_effort_allowed or failing_case_cleanup_allowed:
            stop_reason = "best_available_out_of_band_candidate"
            best_available_out_of_band_retained = True
        else:
            partial_failing_final_updates_blocked = True
            final_updates = {}
            stop_reason = (
                "no_multi_domain_target_candidate"
                if len(final_target_domains) >= 2
                else "no_full_coverage_candidate"
            )
            winning_label = None
            winning_action_type = None
    return {
        "final_updates": final_updates,
        "stop_reason": stop_reason,
        "winning_label": winning_label,
        "winning_action_type": winning_action_type,
        "partial_failing_final_updates_blocked": partial_failing_final_updates_blocked,
        "partial_failing_final_updates_raw": partial_failing_final_updates_raw,
        "best_available_out_of_band_retained": best_available_out_of_band_retained,
    }


def _handle_one_click_solver_final_band_hit_stop_normalization_coordinator(
    *,
    final_band_hit: bool,
    stop_reason: str | None,
    status: str | None,
) -> dict:
    if final_band_hit and str(stop_reason or "") in {
        "best_available_out_of_band_candidate",
        "no_improving_candidate",
        "no_actionable_candidates_after_full_tightening_search",
        "non_material_remaining_candidates",
        "no_actionable_candidates",
        "tightening_depth_budget_reached",
    }:
        stop_reason = "reached_target_band"
        status = "solved"
    return {
        "stop_reason": stop_reason,
        "status": status,
    }


def _prepare_one_click_solver_rescue_entry_decision_state_coordinator(
    *,
    rescue_enabled: bool,
    rescue_debug: dict,
    initial_snapshot: dict,
    init_eval: dict,
    final_eval: dict | None,
    final_pass: bool,
    final_updates: dict,
    stop_reason: str | None,
    mode_config: dict,
    trace_callback,
) -> dict:
    rescue_should_enter = False
    rescue_entry_reason = None
    rescue_family = None
    rescue_tier_requested = None
    rescue_gate_debug: dict = {}
    if rescue_enabled:
        (
            rescue_should_enter,
            rescue_entry_reason,
            rescue_family,
            rescue_tier_requested,
            rescue_gate_debug,
        ) = _rescue_mode_should_enter(
            state=initial_snapshot,
            init_eval=init_eval,
            final_eval=final_eval,
            final_pass=bool(final_pass),
            final_updates=dict(final_updates or {}),
            stop_reason=str(stop_reason or ""),
            mode_config=mode_config,
        )
    rescue_debug["rescue_mode_entered"] = bool(rescue_should_enter)
    rescue_debug["rescue_mode_entry_reason"] = rescue_entry_reason
    rescue_debug["rescue_mode_family"] = rescue_family
    rescue_debug["rescue_mode_tier_requested"] = rescue_tier_requested
    rescue_debug["rescue_mode_exit_reason"] = (
        "not_entered" if not rescue_should_enter else rescue_debug.get("rescue_mode_exit_reason")
    )
    _trace_rescue_decision_solver_coordinator(
        rescue_should_enter=rescue_should_enter,
        rescue_entry_reason=rescue_entry_reason,
        rescue_family=rescue_family,
        rescue_tier_requested=rescue_tier_requested,
        final_pass=final_pass,
        final_updates=final_updates,
        stop_reason=stop_reason,
        rescue_gate_debug=rescue_gate_debug,
        trace_callback=trace_callback,
    )
    return {
        "rescue_should_enter": rescue_should_enter,
        "rescue_entry_reason": rescue_entry_reason,
        "rescue_family": rescue_family,
        "rescue_tier_requested": rescue_tier_requested,
        "rescue_gate_debug": rescue_gate_debug,
    }


def _complete_one_click_solver_effective_rescue_seed_handoff_coordinator(
    *,
    rescue_seed_scope: dict,
) -> dict:
    rescue_result = rescue_seed_scope["rescue_result"]
    initial_snapshot = rescue_seed_scope["initial_snapshot"]
    target_domains_for_band = rescue_seed_scope["target_domains_for_band"]
    mode_config = rescue_seed_scope["mode_config"]
    rescue_entry_reason = rescue_seed_scope["rescue_entry_reason"]
    rescue_family = rescue_seed_scope["rescue_family"]
    rescue_tier_requested = rescue_seed_scope["rescue_tier_requested"]
    tier = rescue_seed_scope["tier"]
    seed_key = rescue_seed_scope["seed_key"]
    fallback_count = rescue_seed_scope["fallback_count"]
    ineffective_seeds = rescue_seed_scope["ineffective_seeds"]
    trace_callback = rescue_seed_scope["trace_callback"]

    rescue_dbg = dict((rescue_result.get("one_click_solver_debug") or {}))
    rescue_final_preview = _guidance_state_snapshot(
        dict((rescue_result.get("final_state_preview") or {}) or {}),
    )
    rescue_result["final_updates"] = _one_click_diff_accumulated_updates(
        initial_snapshot,
        rescue_final_preview,
    )
    rescue_result["final_state_preview"] = rescue_final_preview
    rescue_result_eval = None
    try:
        rescue_result_eval = evaluate_candidate_full(
            _build_canonical_design_state_pack(copy.deepcopy(rescue_final_preview)),
            source="rescue_mode_outer_result_eval",
            label="Rescue outer result",
            action_type="rescue_mode",
            updates={},
        )
    except Exception:
        rescue_result_eval = None
    if isinstance(rescue_result_eval, dict):
        rescue_target_domains = _one_click_target_domains_for_eval(
            target_domains_for_band,
            rescue_result.get("final_updates") or {},
        )
        _one_click_attach_eval_target_domains(
            rescue_result_eval,
            rescue_target_domains,
            mode_config,
        )
        rescue_pass = bool((rescue_result_eval.get("overview") or {}).get("all_key_pass"))
        rescue_in_band = bool(
            rescue_pass
            and _candidate_in_target_band(rescue_result_eval, mode_config)
            and not _one_click_has_unresolved_spacing_envelope_fail(rescue_result_eval)
        )
        rescue_result["final_worst_util"] = float(
            (rescue_result_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0
        )
        rescue_result["all_key_pass"] = bool(rescue_pass)
        rescue_result["reached_target_band"] = bool(rescue_in_band)
        rescue_result["final_state_preview"] = copy.deepcopy(
            (rescue_result_eval.get("state") or rescue_final_preview)
        )
        if rescue_in_band:
            rescue_result["status"] = "solved"
            rescue_result["stop_reason"] = "reached_target_band"
    rescue_dbg.update(
        {
            "rescue_mode_entered": True,
            "rescue_mode_entry_reason": rescue_entry_reason,
            "rescue_mode_family": rescue_family,
            "rescue_mode_tier_requested": rescue_tier_requested,
            "rescue_mode_tier_used": tier,
            "rescue_mode_seed_key": seed_key,
            "rescue_mode_seed_legal": True,
            "rescue_mode_seed_illegal_reason": None,
            "rescue_mode_fallback_count": int(fallback_count),
            "rescue_mode_ineffective_seeds": list(ineffective_seeds),
            "rescue_mode_effective_seed_found": True,
            "rescue_mode_exit_reason": "effective_seed_handoff_to_normal_optimizer",
        }
    )
    rescue_result["one_click_solver_debug"] = rescue_dbg
    _trace_rescue_exit_solver_coordinator(
        seed_key=seed_key,
        rescue_family=rescue_family,
        rescue_tier_requested=rescue_tier_requested,
        tier=tier,
        fallback_count=fallback_count,
        ineffective_seeds=ineffective_seeds,
        rescue_result=rescue_result,
        trace_callback=trace_callback,
    )
    return {
        "should_return_rescue_result": True,
        "rescue_result": rescue_result,
    }


def _prepare_one_click_solver_rescue_seed_loop_state_coordinator(
    *,
    rescue_should_enter: bool,
    rescue_family: str | None,
    rescue_tier_requested: str | None,
    rescue_entry_reason: str | None,
    initial_snapshot: dict,
    max_steps: int,
    debug_enabled: bool,
    trace_run_id: str | None,
    trace_source: str,
    attempted_seed_keys: set[str],
    rescue_debug: dict,
    final_eval: dict | None,
    mode_config: dict,
    target_domains_for_band: list[str],
    trace_callback,
) -> dict:
    rescue_result = None
    if rescue_should_enter and rescue_family and rescue_tier_requested:
        seed_order = _rescue_mode_seed_order(rescue_tier_requested)
        fallback_count = 0
        ineffective_seeds: list[str] = []
        for idx, tier in enumerate(seed_order):
            seed_spec = dict(((RESCUE_SEED_LIBRARY.get(rescue_family) or {}).get(tier)) or {})
            if not seed_spec:
                continue
            seed_key = str(seed_spec.get("key") or f"{rescue_family}_{tier}")
            if seed_key in attempted_seed_keys:
                continue
            if idx > 0:
                fallback_count += 1
            seed_updates = dict(seed_spec.get("updates") or {})
            legal, illegal_reason, seeded_state = _rescue_mode_validate_seed(initial_snapshot, seed_updates)
            _trace_rescue_seed_attempt_solver_coordinator(
                seed_key=seed_key,
                rescue_family=rescue_family,
                rescue_tier_requested=rescue_tier_requested,
                tier=tier,
                seed_updates=seed_updates,
                legal=legal,
                illegal_reason=illegal_reason,
                fallback_count=fallback_count,
                trace_callback=trace_callback,
            )
            if not legal:
                attempted_seed_keys.add(seed_key)
                rescue_debug["rescue_mode_tier_used"] = tier
                rescue_debug["rescue_mode_seed_key"] = seed_key
                rescue_debug["rescue_mode_seed_legal"] = False
                rescue_debug["rescue_mode_seed_illegal_reason"] = illegal_reason
                continue
            rescue_result = _solve_one_click_to_target(
                seeded_state,
                max_steps=max_steps,
                debug_enabled=debug_enabled,
                trace_run_id=trace_run_id,
                trace_source=trace_source,
                _rescue_enabled=False,
                _rescue_attempted_seed_keys=tuple(sorted(attempted_seed_keys | {seed_key})),
            )
            rescue_eval = _rescue_mode_eval_for_result(rescue_result)
            improved = _rescue_mode_path_improved(rescue_eval, final_eval, mode_config)
            if not improved:
                attempted_seed_keys.add(seed_key)
                ineffective_seeds.append(seed_key)
                rescue_debug["rescue_mode_tier_used"] = tier
                rescue_debug["rescue_mode_seed_key"] = seed_key
                rescue_debug["rescue_mode_seed_legal"] = True
                rescue_debug["rescue_mode_seed_illegal_reason"] = None
                rescue_debug["rescue_mode_fallback_count"] = int(fallback_count)
                rescue_debug["rescue_mode_ineffective_seeds"] = list(ineffective_seeds)
                _trace_rescue_seed_ineffective_solver_coordinator(
                    seed_key=seed_key,
                    rescue_family=rescue_family,
                    rescue_tier_requested=rescue_tier_requested,
                    tier=tier,
                    fallback_count=fallback_count,
                    trace_callback=trace_callback,
                )
                continue
            return _complete_one_click_solver_effective_rescue_seed_handoff_coordinator(
                rescue_seed_scope=locals(),
            )
        rescue_debug["rescue_mode_fallback_count"] = int(fallback_count)
        rescue_debug["rescue_mode_ineffective_seeds"] = list(ineffective_seeds)
        rescue_debug["rescue_mode_effective_seed_found"] = False
        rescue_debug["rescue_mode_exit_reason"] = "no_legal_effective_seed_found"
    return {
        "should_return_rescue_result": False,
        "rescue_result": rescue_result,
    }


def _dispatch_one_click_solver_final_trace_return_coordinator(
    *,
    finalization_scope: dict,
) -> dict:
    return _complete_one_click_solver_final_trace_and_return_coordinator(
        stop_reason=finalization_scope["stop_reason"],
        step_trace=finalization_scope["step_trace"],
        status=finalization_scope["status"],
        final_worst=finalization_scope["final_worst"],
        final_in_band=finalization_scope["final_in_band"],
        final_pass=finalization_scope["final_pass"],
        winning_label=finalization_scope["winning_label"],
        winning_action_type=finalization_scope["winning_action_type"],
        final_updates=finalization_scope["final_updates"],
        tightening_step_count=finalization_scope["tightening_step_count"],
        max_tightening_steps=finalization_scope["max_tightening_steps"],
        final_eval=finalization_scope["final_eval"],
        mode_config=finalization_scope["mode_config"],
        no_actionable_after_full_tightening_search=finalization_scope[
            "no_actionable_after_full_tightening_search"
        ],
        candidate_family_depth_reached=finalization_scope["candidate_family_depth_reached"],
        final_distance_to_band=finalization_scope["final_distance_to_band"],
        shear_governing_mode_active=finalization_scope["shear_governing_mode_active"],
        shear_severity_band=finalization_scope["shear_severity_band"],
        shear_candidate_family_order=finalization_scope["shear_candidate_family_order"],
        spacing_candidates_considered=finalization_scope["spacing_candidates_considered"],
        leg_candidates_considered=finalization_scope["leg_candidates_considered"],
        dia_candidates_considered=finalization_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=finalization_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=finalization_scope[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=finalization_scope["web_crushing_penalty_applied"],
        rejected_as_spacing_too_weak=finalization_scope["rejected_as_spacing_too_weak"],
        rejected_as_web_crushing_marginal=finalization_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=finalization_scope[
            "rejected_as_impractical_shear_layout"
        ],
        final_resolved_shear_util=finalization_scope["final_resolved_shear_util"],
        final_resolved_web_util=finalization_scope["final_resolved_web_util"],
        shear_governing_family_detected=finalization_scope[
            "shear_governing_family_detected"
        ],
        governing_family_exists_after_domain_fix=finalization_scope[
            "governing_family_exists_after_domain_fix"
        ],
        pruned_non_shear_family_count=finalization_scope["pruned_non_shear_family_count"],
        rescue_debug=finalization_scope["rescue_debug"],
        trace_callback=finalization_scope["trace_callback"],
        trace_run_id=finalization_scope["trace_run_id"],
        stop_traced=finalization_scope["stop_traced"],
        init_worst=finalization_scope["init_worst"],
        t_lo=finalization_scope["t_lo"],
        t_hi=finalization_scope["t_hi"],
        initial_coherence=finalization_scope["initial_coherence"],
        final_governing_domain=finalization_scope["final_governing_domain"],
        rejected_as_non_governing_cleanup=finalization_scope[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=finalization_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        target_band_domain=finalization_scope["target_band_domain"],
        target_domains_for_band=finalization_scope["target_domains_for_band"],
        final_target_domains=finalization_scope["final_target_domains"],
        step_committable_eval_trace=finalization_scope["step_committable_eval_trace"],
        final_eval_internal_worst_util_dbg=finalization_scope[
            "final_eval_internal_worst_util_dbg"
        ],
        final_eval_committable_worst_util_dbg=finalization_scope[
            "final_eval_committable_worst_util_dbg"
        ],
        final_eval_used_source_dbg=finalization_scope["final_eval_used_source_dbg"],
        final_eval_committable_updates_dbg=finalization_scope[
            "final_eval_committable_updates_dbg"
        ],
        final_objective_util=finalization_scope["final_objective_util"],
        shear_remove_links_candidate_seen=finalization_scope[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_truth_ok=finalization_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        shear_remove_links_candidate_dropped_reason=finalization_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        shear_remove_links_candidate_materiality=finalization_scope[
            "shear_remove_links_candidate_materiality"
        ],
        early_in_band_exit_blocked_for_tightening=finalization_scope[
            "early_in_band_exit_blocked_for_tightening"
        ],
        early_in_band_exit_tightening_classification=finalization_scope[
            "early_in_band_exit_tightening_classification"
        ],
        early_in_band_exit_available_tightening_paths=finalization_scope[
            "early_in_band_exit_available_tightening_paths"
        ],
        early_in_band_exit_reason=finalization_scope["early_in_band_exit_reason"],
        partial_failing_final_updates_blocked=finalization_scope[
            "partial_failing_final_updates_blocked"
        ],
        partial_failing_final_updates_raw=finalization_scope[
            "partial_failing_final_updates_raw"
        ],
        best_available_out_of_band_retained=finalization_scope[
            "best_available_out_of_band_retained"
        ],
        rescue_gate_debug=finalization_scope["rescue_gate_debug"],
        working=finalization_scope["working"],
    )


def _build_one_click_solver_pre_selection_candidate_evaluation_state_coordinator(
    *,
    pre_selection_scope: dict,
) -> dict:
    return {
        "cur_eval": pre_selection_scope["cur_eval"],
        "cur_pass": pre_selection_scope["cur_pass"],
        "tightening_mode_active": pre_selection_scope["tightening_mode_active"],
        "governing_domain": pre_selection_scope["governing_domain"],
        "target_band_domain": pre_selection_scope["target_band_domain"],
        "cur_ib": pre_selection_scope["cur_ib"],
        "in_band_shear_cleanup_deferral": pre_selection_scope[
            "in_band_shear_cleanup_deferral"
        ],
        "final_governing_domain": pre_selection_scope["final_governing_domain"],
        "shear_governing_mode_active": pre_selection_scope["shear_governing_mode_active"],
        "shear_governing_family_detected": pre_selection_scope[
            "shear_governing_family_detected"
        ],
        "governing_family_exists_after_domain_fix": pre_selection_scope[
            "governing_family_exists_after_domain_fix"
        ],
        "pruned_non_shear_family_count": pre_selection_scope[
            "pruned_non_shear_family_count"
        ],
        "domain_match_prune_used": pre_selection_scope["domain_match_prune_used"],
        "shear_prune_rule_source": pre_selection_scope["shear_prune_rule_source"],
        "material_improvement_threshold": pre_selection_scope[
            "material_improvement_threshold"
        ],
        "tightening_meta": pre_selection_scope["tightening_meta"],
        "raw_n": pre_selection_scope["raw_n"],
        "pool_labels": pre_selection_scope["pool_labels"],
        "reduction_candidates_considered": pre_selection_scope[
            "reduction_candidates_considered"
        ],
        "candidate_family_depth_reached": pre_selection_scope[
            "candidate_family_depth_reached"
        ],
        "shear_severity_band": pre_selection_scope["shear_severity_band"],
        "shear_candidate_family_order": pre_selection_scope["shear_candidate_family_order"],
        "spacing_candidates_considered": pre_selection_scope["spacing_candidates_considered"],
        "leg_candidates_considered": pre_selection_scope["leg_candidates_considered"],
        "dia_candidates_considered": pre_selection_scope["dia_candidates_considered"],
        "geometry_candidates_considered_for_shear": pre_selection_scope[
            "geometry_candidates_considered_for_shear"
        ],
        "combined_candidates_considered_for_shear": pre_selection_scope[
            "combined_candidates_considered_for_shear"
        ],
        "rejected_as_non_governing_cleanup": pre_selection_scope[
            "rejected_as_non_governing_cleanup"
        ],
        "rejected_as_non_governing_shear_strengthening": pre_selection_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        "rejected_as_non_material_improvement": pre_selection_scope[
            "rejected_as_non_material_improvement"
        ],
        "growth_candidates_rejected_in_tightening": pre_selection_scope[
            "growth_candidates_rejected_in_tightening"
        ],
        "scored": pre_selection_scope["scored"],
        "shear_remove_links_candidate_seen": pre_selection_scope[
            "shear_remove_links_candidate_seen"
        ],
        "shear_remove_links_candidate_truth_ok": pre_selection_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        "shear_remove_links_candidate_dropped_reason": pre_selection_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "shear_remove_links_candidate_materiality": pre_selection_scope[
            "shear_remove_links_candidate_materiality"
        ],
        "rejected_as_spacing_too_weak": pre_selection_scope[
            "rejected_as_spacing_too_weak"
        ],
        "rejected_as_web_crushing_marginal": pre_selection_scope[
            "rejected_as_web_crushing_marginal"
        ],
        "rejected_as_impractical_shear_layout": pre_selection_scope[
            "rejected_as_impractical_shear_layout"
        ],
        "web_crushing_penalty_applied": pre_selection_scope[
            "web_crushing_penalty_applied"
        ],
    }


def _dispatch_one_click_solver_candidate_pipeline_state_from_pre_selection_coordinator(
    *,
    pre_selection_scope: dict,
) -> dict:
    return _prepare_one_click_solver_candidate_pipeline_state_coordinator(
        working=pre_selection_scope["working"],
        debug_enabled=pre_selection_scope["debug_enabled"],
        trace_run_id=pre_selection_scope["trace_run_id"],
        step_idx=pre_selection_scope["step_idx"],
        tightening_mode_active=pre_selection_scope["tightening_mode_active"],
        governing_domain_failing=pre_selection_scope["governing_domain_failing"],
        required_domain_work_active=pre_selection_scope["required_domain_work_active"],
        target_band_domain=pre_selection_scope["target_band_domain"],
        cur_shear_failing=pre_selection_scope["cur_shear_failing"],
        governing_domain=pre_selection_scope["governing_domain"],
        cur_ib=pre_selection_scope["cur_ib"],
        cur_eval=pre_selection_scope["cur_eval"],
        mode_config=pre_selection_scope["mode_config"],
        tightening_step_count=pre_selection_scope["tightening_step_count"],
        tightening_meta=pre_selection_scope["tightening_meta"],
        candidate_family_depth_reached=pre_selection_scope[
            "candidate_family_depth_reached"
        ],
        shear_governing_mode_active=pre_selection_scope["shear_governing_mode_active"],
        shear_severity_band=pre_selection_scope["shear_severity_band"],
        shear_candidate_family_order=pre_selection_scope["shear_candidate_family_order"],
        spacing_candidates_considered=pre_selection_scope["spacing_candidates_considered"],
        leg_candidates_considered=pre_selection_scope["leg_candidates_considered"],
        dia_candidates_considered=pre_selection_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=pre_selection_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=pre_selection_scope[
            "combined_candidates_considered_for_shear"
        ],
        cur_sig=pre_selection_scope["cur_sig"],
        t_lo=pre_selection_scope["t_lo"],
        t_hi=pre_selection_scope["t_hi"],
        max_tightening_steps=pre_selection_scope["max_tightening_steps"],
        no_actionable_after_full_tightening_search=pre_selection_scope[
            "no_actionable_after_full_tightening_search"
        ],
        target_domains_for_band=pre_selection_scope[
            "target_domains_for_band"
        ],
        pruned_non_shear_family_count=pre_selection_scope[
            "pruned_non_shear_family_count"
        ],
        domain_match_prune_used=pre_selection_scope["domain_match_prune_used"],
        shear_prune_rule_source=pre_selection_scope["shear_prune_rule_source"],
        material_improvement_threshold=pre_selection_scope[
            "material_improvement_threshold"
        ],
        rejected_as_non_governing_cleanup=pre_selection_scope[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=pre_selection_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        shear_remove_links_candidate_seen=pre_selection_scope[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_dropped_reason=pre_selection_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        trace_callback=pre_selection_scope["trace_callback"],
    )


def _dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(
    *,
    pre_selection_scope: dict,
) -> dict:
    return _run_one_click_solver_candidate_scoring_loop_coordinator(
        prepared=pre_selection_scope["prepared"],
        step_idx=pre_selection_scope["step_idx"],
        working=pre_selection_scope["working"],
        cur_eval=pre_selection_scope["cur_eval"],
        mode_config=pre_selection_scope["mode_config"],
        target_domains_for_band=pre_selection_scope["target_domains_for_band"],
        tightening_mode_active=pre_selection_scope["tightening_mode_active"],
        governing_domain=pre_selection_scope["governing_domain"],
        cur_shear_failing=pre_selection_scope["cur_shear_failing"],
        target_band_domain=pre_selection_scope["target_band_domain"],
        seen_sigs=pre_selection_scope["seen_sigs"],
        cur_u=pre_selection_scope["cur_u"],
        mixed_direction_mode=pre_selection_scope["mixed_direction_mode"],
        cur_has_td=pre_selection_scope["cur_has_td"],
        cur_required_fail_count=pre_selection_scope["cur_required_fail_count"],
        cur_required_unsatisfied_count=pre_selection_scope[
            "cur_required_unsatisfied_count"
        ],
        material_improvement_threshold=pre_selection_scope[
            "material_improvement_threshold"
        ],
        scored=pre_selection_scope["scored"],
        rejected_as_non_governing_cleanup=pre_selection_scope[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=pre_selection_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        rejected_as_evaluation_failed=pre_selection_scope[
            "rejected_as_evaluation_failed"
        ],
        rejected_as_duplicate_signature=pre_selection_scope[
            "rejected_as_duplicate_signature"
        ],
        rejected_as_non_material_improvement=pre_selection_scope[
            "rejected_as_non_material_improvement"
        ],
        growth_candidates_rejected_in_tightening=pre_selection_scope[
            "growth_candidates_rejected_in_tightening"
        ],
        shear_remove_links_candidate_seen=pre_selection_scope[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_truth_ok=pre_selection_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        shear_remove_links_candidate_dropped_reason=pre_selection_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        shear_remove_links_candidate_materiality=pre_selection_scope[
            "shear_remove_links_candidate_materiality"
        ],
        rejected_as_spacing_too_weak=pre_selection_scope[
            "rejected_as_spacing_too_weak"
        ],
        rejected_as_web_crushing_marginal=pre_selection_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=pre_selection_scope[
            "rejected_as_impractical_shear_layout"
        ],
        web_crushing_penalty_applied=pre_selection_scope[
            "web_crushing_penalty_applied"
        ],
        trace_callback=pre_selection_scope["trace_callback"],
    )


def _run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator(
    *,
    pre_selection_scope: dict,
) -> dict:
    pre_selection_scope = dict(pre_selection_scope)
    candidate_pipeline_state = (
        _dispatch_one_click_solver_candidate_pipeline_state_from_pre_selection_coordinator(
            pre_selection_scope=pre_selection_scope,
        )
    )
    pre_selection_scope.update(candidate_pipeline_state)
    scoring_loop_state = _dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(
        pre_selection_scope=pre_selection_scope,
    )
    pre_selection_scope.update(scoring_loop_state)
    return _build_one_click_solver_pre_selection_candidate_evaluation_state_coordinator(
        pre_selection_scope=pre_selection_scope,
    )


def _run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator(
    *,
    iteration_gate_state: dict,
    working: dict,
    debug_enabled: bool,
    trace_run_id: str | None,
    step_idx: int,
    mode_config: dict,
    target_domains_for_band,
    target_band_domain,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: bool,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list,
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: bool,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason,
    shear_remove_links_candidate_materiality,
    t_lo,
    t_hi,
    seen_sigs: set,
    trace_callback,
) -> dict:
    pre_selection_scope = dict(locals())
    pre_selection_scope.update(iteration_gate_state)
    return _run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator(
        pre_selection_scope=pre_selection_scope,
    )


def _build_one_click_solver_selection_stop_iteration_state_coordinator(
    *,
    scored_candidate_selection_state: dict,
    working: dict,
    target_band_domain,
    winning_label,
    winning_action_type,
    tightening_step_count: int,
    candidate_family_depth_reached: bool,
    final_governing_domain,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list,
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: bool,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    final_resolved_shear_util,
    final_resolved_web_util,
    no_actionable_after_full_tightening_search: bool,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason,
    shear_remove_links_candidate_materiality,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
) -> dict:
    return {
        "should_break": True,
        "working": working,
        "target_band_domain": target_band_domain,
        "winning_label": winning_label,
        "winning_action_type": winning_action_type,
        "tightening_step_count": tightening_step_count,
        "candidate_family_depth_reached": candidate_family_depth_reached,
        "final_governing_domain": final_governing_domain,
        "shear_governing_mode_active": shear_governing_mode_active,
        "shear_severity_band": shear_severity_band,
        "shear_candidate_family_order": shear_candidate_family_order,
        "spacing_candidates_considered": spacing_candidates_considered,
        "leg_candidates_considered": leg_candidates_considered,
        "dia_candidates_considered": dia_candidates_considered,
        "geometry_candidates_considered_for_shear": geometry_candidates_considered_for_shear,
        "combined_candidates_considered_for_shear": combined_candidates_considered_for_shear,
        "web_crushing_penalty_applied": web_crushing_penalty_applied,
        "rejected_as_spacing_too_weak": rejected_as_spacing_too_weak,
        "rejected_as_web_crushing_marginal": rejected_as_web_crushing_marginal,
        "rejected_as_impractical_shear_layout": rejected_as_impractical_shear_layout,
        "final_resolved_shear_util": final_resolved_shear_util,
        "final_resolved_web_util": final_resolved_web_util,
        "stop_reason": scored_candidate_selection_state["stop_reason"],
        "status": scored_candidate_selection_state["status"],
        "final_distance_to_band": scored_candidate_selection_state[
            "final_distance_to_band"
        ],
        "no_actionable_after_full_tightening_search": no_actionable_after_full_tightening_search,
        "rejected_as_non_governing_cleanup": rejected_as_non_governing_cleanup,
        "rejected_as_non_governing_shear_strengthening": rejected_as_non_governing_shear_strengthening,
        "shear_remove_links_candidate_seen": shear_remove_links_candidate_seen,
        "shear_remove_links_candidate_truth_ok": shear_remove_links_candidate_truth_ok,
        "shear_remove_links_candidate_dropped_reason": shear_remove_links_candidate_dropped_reason,
        "shear_remove_links_candidate_materiality": shear_remove_links_candidate_materiality,
        "shear_governing_family_detected": shear_governing_family_detected,
        "governing_family_exists_after_domain_fix": governing_family_exists_after_domain_fix,
        "pruned_non_shear_family_count": pruned_non_shear_family_count,
    }


def _build_one_click_solver_accepted_iteration_state_coordinator(
    *,
    accepted_candidate_post_step_state: dict,
    target_band_domain,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: bool,
    final_governing_domain,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list,
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: bool,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason,
    shear_remove_links_candidate_materiality,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
) -> dict:
    return {
        "should_break": accepted_candidate_post_step_state["should_break"],
        "working": accepted_candidate_post_step_state["working"],
        "winning_label": accepted_candidate_post_step_state["winning_label"],
        "winning_action_type": accepted_candidate_post_step_state["winning_action_type"],
        "tightening_step_count": accepted_candidate_post_step_state[
            "tightening_step_count"
        ],
        "final_distance_to_band": accepted_candidate_post_step_state[
            "final_distance_to_band"
        ],
        "final_resolved_shear_util": accepted_candidate_post_step_state[
            "final_resolved_shear_util"
        ],
        "final_resolved_web_util": accepted_candidate_post_step_state[
            "final_resolved_web_util"
        ],
        "stop_reason": accepted_candidate_post_step_state["stop_reason"],
        "status": accepted_candidate_post_step_state["status"],
        "target_band_domain": target_band_domain,
        "no_actionable_after_full_tightening_search": no_actionable_after_full_tightening_search,
        "candidate_family_depth_reached": candidate_family_depth_reached,
        "final_governing_domain": final_governing_domain,
        "shear_governing_mode_active": shear_governing_mode_active,
        "shear_severity_band": shear_severity_band,
        "shear_candidate_family_order": shear_candidate_family_order,
        "spacing_candidates_considered": spacing_candidates_considered,
        "leg_candidates_considered": leg_candidates_considered,
        "dia_candidates_considered": dia_candidates_considered,
        "geometry_candidates_considered_for_shear": geometry_candidates_considered_for_shear,
        "combined_candidates_considered_for_shear": combined_candidates_considered_for_shear,
        "web_crushing_penalty_applied": web_crushing_penalty_applied,
        "rejected_as_spacing_too_weak": rejected_as_spacing_too_weak,
        "rejected_as_web_crushing_marginal": rejected_as_web_crushing_marginal,
        "rejected_as_impractical_shear_layout": rejected_as_impractical_shear_layout,
        "rejected_as_non_governing_cleanup": rejected_as_non_governing_cleanup,
        "rejected_as_non_governing_shear_strengthening": rejected_as_non_governing_shear_strengthening,
        "shear_remove_links_candidate_seen": shear_remove_links_candidate_seen,
        "shear_remove_links_candidate_truth_ok": shear_remove_links_candidate_truth_ok,
        "shear_remove_links_candidate_dropped_reason": shear_remove_links_candidate_dropped_reason,
        "shear_remove_links_candidate_materiality": shear_remove_links_candidate_materiality,
        "shear_governing_family_detected": shear_governing_family_detected,
        "governing_family_exists_after_domain_fix": governing_family_exists_after_domain_fix,
        "pruned_non_shear_family_count": pruned_non_shear_family_count,
    }


def _dispatch_one_click_solver_post_selection_candidate_selection_state_coordinator(
    *,
    post_selection_scope: dict,
) -> dict:
    return _resolve_one_click_solver_scored_candidate_selection_state_coordinator(
        scored=post_selection_scope["scored"],
        cur_eval=post_selection_scope["cur_eval"],
        working=post_selection_scope["working"],
        mode_config=post_selection_scope["mode_config"],
        tightening_mode_active=post_selection_scope["tightening_mode_active"],
        step_idx=post_selection_scope["step_idx"],
        raw_n=post_selection_scope["raw_n"],
        pool_labels=post_selection_scope["pool_labels"],
        governing_domain=post_selection_scope["governing_domain"],
        tightening_meta=post_selection_scope["tightening_meta"],
        material_improvement_threshold=post_selection_scope[
            "material_improvement_threshold"
        ],
        reduction_candidates_considered=post_selection_scope[
            "reduction_candidates_considered"
        ],
        growth_candidates_rejected_in_tightening=post_selection_scope[
            "growth_candidates_rejected_in_tightening"
        ],
        rejected_as_non_governing_cleanup=post_selection_scope[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=post_selection_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        rejected_as_non_material_improvement=post_selection_scope[
            "rejected_as_non_material_improvement"
        ],
        tightening_step_count=post_selection_scope["tightening_step_count"],
        max_tightening_steps=post_selection_scope["max_tightening_steps"],
        no_actionable_after_full_tightening_search=post_selection_scope[
            "no_actionable_after_full_tightening_search"
        ],
        candidate_family_depth_reached=post_selection_scope[
            "candidate_family_depth_reached"
        ],
        shear_governing_mode_active=post_selection_scope["shear_governing_mode_active"],
        shear_severity_band=post_selection_scope["shear_severity_band"],
        shear_candidate_family_order=post_selection_scope["shear_candidate_family_order"],
        spacing_candidates_considered=post_selection_scope["spacing_candidates_considered"],
        leg_candidates_considered=post_selection_scope["leg_candidates_considered"],
        dia_candidates_considered=post_selection_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=post_selection_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=post_selection_scope[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=post_selection_scope["web_crushing_penalty_applied"],
        rejected_as_spacing_too_weak=post_selection_scope["rejected_as_spacing_too_weak"],
        rejected_as_web_crushing_marginal=post_selection_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=post_selection_scope[
            "rejected_as_impractical_shear_layout"
        ],
        shear_governing_family_detected=post_selection_scope[
            "shear_governing_family_detected"
        ],
        governing_family_exists_after_domain_fix=post_selection_scope[
            "governing_family_exists_after_domain_fix"
        ],
        pruned_non_shear_family_count=post_selection_scope["pruned_non_shear_family_count"],
        domain_match_prune_used=post_selection_scope["domain_match_prune_used"],
        shear_prune_rule_source=post_selection_scope["shear_prune_rule_source"],
        cur_pass=post_selection_scope["cur_pass"],
        step_trace=post_selection_scope["step_trace"],
        initial_snapshot=post_selection_scope["initial_snapshot"],
        cur_ib=post_selection_scope["cur_ib"],
        winning_label=post_selection_scope["winning_label"],
        winning_action_type=post_selection_scope["winning_action_type"],
        in_band_shear_cleanup_deferral=post_selection_scope[
            "in_band_shear_cleanup_deferral"
        ],
        trace_callback=post_selection_scope["trace_callback"],
    )


def _dispatch_one_click_solver_accepted_candidate_post_step_from_post_selection_coordinator(
    *,
    post_selection_scope: dict,
) -> dict:
    return _handle_one_click_solver_accepted_candidate_post_step_coordinator(
        best=post_selection_scope["best"],
        mode_config=post_selection_scope["mode_config"],
        step_idx=post_selection_scope["step_idx"],
        tightening_step_count=post_selection_scope["tightening_step_count"],
        max_tightening_steps=post_selection_scope["max_tightening_steps"],
        candidate_family_depth_reached=post_selection_scope[
            "candidate_family_depth_reached"
        ],
        best_distance_to_band_this_iteration=post_selection_scope[
            "best_distance_to_band_this_iteration"
        ],
        initial_snapshot=post_selection_scope["initial_snapshot"],
        working=post_selection_scope["working"],
        step_trace=post_selection_scope["step_trace"],
        winning_label=post_selection_scope["winning_label"],
        winning_action_type=post_selection_scope["winning_action_type"],
        target_domains_for_band=post_selection_scope["target_domains_for_band"],
        target_band_domain=post_selection_scope["target_band_domain"],
        seen_sigs=post_selection_scope["seen_sigs"],
        governing_domain=post_selection_scope["governing_domain"],
        tightening_mode_active=post_selection_scope["tightening_mode_active"],
        step_committable_eval_trace=post_selection_scope[
            "step_committable_eval_trace"
        ],
        no_actionable_after_full_tightening_search=post_selection_scope[
            "no_actionable_after_full_tightening_search"
        ],
        shear_governing_mode_active=post_selection_scope["shear_governing_mode_active"],
        shear_severity_band=post_selection_scope["shear_severity_band"],
        shear_candidate_family_order=post_selection_scope["shear_candidate_family_order"],
        spacing_candidates_considered=post_selection_scope["spacing_candidates_considered"],
        leg_candidates_considered=post_selection_scope["leg_candidates_considered"],
        dia_candidates_considered=post_selection_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=post_selection_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=post_selection_scope[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=post_selection_scope[
            "web_crushing_penalty_applied"
        ],
        rejected_as_spacing_too_weak=post_selection_scope[
            "rejected_as_spacing_too_weak"
        ],
        rejected_as_web_crushing_marginal=post_selection_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=post_selection_scope[
            "rejected_as_impractical_shear_layout"
        ],
        final_resolved_shear_util=post_selection_scope["final_resolved_shear_util"],
        final_resolved_web_util=post_selection_scope["final_resolved_web_util"],
        shear_governing_family_detected=post_selection_scope[
            "shear_governing_family_detected"
        ],
        governing_family_exists_after_domain_fix=post_selection_scope[
            "governing_family_exists_after_domain_fix"
        ],
        pruned_non_shear_family_count=post_selection_scope[
            "pruned_non_shear_family_count"
        ],
        trace_callback=post_selection_scope["trace_callback"],
    )


def _dispatch_one_click_solver_accepted_iteration_state_from_post_selection_coordinator(
    *,
    post_selection_scope: dict,
    accepted_candidate_post_step_state: dict,
) -> dict:
    return _build_one_click_solver_accepted_iteration_state_coordinator(
        accepted_candidate_post_step_state=accepted_candidate_post_step_state,
        target_band_domain=post_selection_scope["target_band_domain"],
        no_actionable_after_full_tightening_search=post_selection_scope[
            "no_actionable_after_full_tightening_search"
        ],
        candidate_family_depth_reached=post_selection_scope[
            "candidate_family_depth_reached"
        ],
        final_governing_domain=post_selection_scope["final_governing_domain"],
        shear_governing_mode_active=post_selection_scope["shear_governing_mode_active"],
        shear_severity_band=post_selection_scope["shear_severity_band"],
        shear_candidate_family_order=post_selection_scope["shear_candidate_family_order"],
        spacing_candidates_considered=post_selection_scope["spacing_candidates_considered"],
        leg_candidates_considered=post_selection_scope["leg_candidates_considered"],
        dia_candidates_considered=post_selection_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=post_selection_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=post_selection_scope[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=post_selection_scope["web_crushing_penalty_applied"],
        rejected_as_spacing_too_weak=post_selection_scope["rejected_as_spacing_too_weak"],
        rejected_as_web_crushing_marginal=post_selection_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=post_selection_scope[
            "rejected_as_impractical_shear_layout"
        ],
        rejected_as_non_governing_cleanup=post_selection_scope[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=post_selection_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        shear_remove_links_candidate_seen=post_selection_scope[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_truth_ok=post_selection_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        shear_remove_links_candidate_dropped_reason=post_selection_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        shear_remove_links_candidate_materiality=post_selection_scope[
            "shear_remove_links_candidate_materiality"
        ],
        shear_governing_family_detected=post_selection_scope[
            "shear_governing_family_detected"
        ],
        governing_family_exists_after_domain_fix=post_selection_scope[
            "governing_family_exists_after_domain_fix"
        ],
        pruned_non_shear_family_count=post_selection_scope[
            "pruned_non_shear_family_count"
        ],
    )


def _run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator(
    *,
    scored,
    cur_eval,
    working: dict,
    mode_config: dict,
    tightening_mode_active: bool,
    step_idx: int,
    raw_n,
    pool_labels,
    governing_domain,
    tightening_meta,
    material_improvement_threshold,
    reduction_candidates_considered,
    growth_candidates_rejected_in_tightening,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    rejected_as_non_material_improvement: int,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: bool,
    final_governing_domain,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list,
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: bool,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    domain_match_prune_used: bool,
    shear_prune_rule_source,
    cur_pass: bool,
    step_trace: list,
    initial_snapshot: dict,
    cur_ib,
    winning_label,
    winning_action_type,
    in_band_shear_cleanup_deferral,
    target_domains_for_band,
    target_band_domain,
    seen_sigs: set,
    step_committable_eval_trace,
    final_resolved_shear_util,
    final_resolved_web_util,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason,
    shear_remove_links_candidate_materiality,
    trace_callback,
) -> dict:
    scored_candidate_selection_state = (
        _dispatch_one_click_solver_post_selection_candidate_selection_state_coordinator(
            post_selection_scope=locals(),
        )
    )
    no_actionable_after_full_tightening_search = scored_candidate_selection_state[
        "no_actionable_after_full_tightening_search"
    ]
    best = scored_candidate_selection_state["best"]
    best_distance_to_band_this_iteration = scored_candidate_selection_state[
        "best_distance_to_band_this_iteration"
    ]
    if scored_candidate_selection_state["should_break"]:
        return _build_one_click_solver_selection_stop_iteration_state_coordinator(
            scored_candidate_selection_state=scored_candidate_selection_state,
            working=working,
            target_band_domain=target_band_domain,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            tightening_step_count=tightening_step_count,
            candidate_family_depth_reached=candidate_family_depth_reached,
            final_governing_domain=final_governing_domain,
            shear_governing_mode_active=shear_governing_mode_active,
            shear_severity_band=shear_severity_band,
            shear_candidate_family_order=shear_candidate_family_order,
            spacing_candidates_considered=spacing_candidates_considered,
            leg_candidates_considered=leg_candidates_considered,
            dia_candidates_considered=dia_candidates_considered,
            geometry_candidates_considered_for_shear=geometry_candidates_considered_for_shear,
            combined_candidates_considered_for_shear=combined_candidates_considered_for_shear,
            web_crushing_penalty_applied=web_crushing_penalty_applied,
            rejected_as_spacing_too_weak=rejected_as_spacing_too_weak,
            rejected_as_web_crushing_marginal=rejected_as_web_crushing_marginal,
            rejected_as_impractical_shear_layout=rejected_as_impractical_shear_layout,
            final_resolved_shear_util=final_resolved_shear_util,
            final_resolved_web_util=final_resolved_web_util,
            no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
            rejected_as_non_governing_cleanup=rejected_as_non_governing_cleanup,
            rejected_as_non_governing_shear_strengthening=rejected_as_non_governing_shear_strengthening,
            shear_remove_links_candidate_seen=shear_remove_links_candidate_seen,
            shear_remove_links_candidate_truth_ok=shear_remove_links_candidate_truth_ok,
            shear_remove_links_candidate_dropped_reason=shear_remove_links_candidate_dropped_reason,
            shear_remove_links_candidate_materiality=shear_remove_links_candidate_materiality,
            shear_governing_family_detected=shear_governing_family_detected,
            governing_family_exists_after_domain_fix=governing_family_exists_after_domain_fix,
            pruned_non_shear_family_count=pruned_non_shear_family_count,
        )

    accepted_candidate_post_step_state = (
        _dispatch_one_click_solver_accepted_candidate_post_step_from_post_selection_coordinator(
            post_selection_scope=locals(),
        )
    )
    return _dispatch_one_click_solver_accepted_iteration_state_from_post_selection_coordinator(
        post_selection_scope=locals(),
        accepted_candidate_post_step_state=accepted_candidate_post_step_state,
    )


def _build_one_click_solver_iteration_candidate_flow_post_selection_shear_fields_coordinator(
    *,
    pre_selection_state: dict,
) -> dict:
    return {
        "spacing_candidates_considered": pre_selection_state[
            "spacing_candidates_considered"
        ],
        "leg_candidates_considered": pre_selection_state["leg_candidates_considered"],
        "dia_candidates_considered": pre_selection_state["dia_candidates_considered"],
        "geometry_candidates_considered_for_shear": pre_selection_state[
            "geometry_candidates_considered_for_shear"
        ],
        "combined_candidates_considered_for_shear": pre_selection_state[
            "combined_candidates_considered_for_shear"
        ],
        "web_crushing_penalty_applied": pre_selection_state[
            "web_crushing_penalty_applied"
        ],
        "rejected_as_spacing_too_weak": pre_selection_state[
            "rejected_as_spacing_too_weak"
        ],
        "rejected_as_web_crushing_marginal": pre_selection_state[
            "rejected_as_web_crushing_marginal"
        ],
        "rejected_as_impractical_shear_layout": pre_selection_state[
            "rejected_as_impractical_shear_layout"
        ],
        "shear_governing_family_detected": pre_selection_state[
            "shear_governing_family_detected"
        ],
        "governing_family_exists_after_domain_fix": pre_selection_state[
            "governing_family_exists_after_domain_fix"
        ],
        "pruned_non_shear_family_count": pre_selection_state[
            "pruned_non_shear_family_count"
        ],
    }


def _build_one_click_solver_iteration_candidate_flow_post_selection_scope_coordinator(
    *,
    iteration_candidate_flow_scope: dict,
    pre_selection_state: dict,
) -> dict:
    return {
        "scored": pre_selection_state["scored"],
        "cur_eval": pre_selection_state["cur_eval"],
        "working": iteration_candidate_flow_scope["working"],
        "mode_config": iteration_candidate_flow_scope["mode_config"],
        "tightening_mode_active": pre_selection_state["tightening_mode_active"],
        "step_idx": iteration_candidate_flow_scope["step_idx"],
        "raw_n": pre_selection_state["raw_n"],
        "pool_labels": pre_selection_state["pool_labels"],
        "governing_domain": pre_selection_state["governing_domain"],
        "tightening_meta": pre_selection_state["tightening_meta"],
        "material_improvement_threshold": pre_selection_state[
            "material_improvement_threshold"
        ],
        "reduction_candidates_considered": pre_selection_state[
            "reduction_candidates_considered"
        ],
        "growth_candidates_rejected_in_tightening": pre_selection_state[
            "growth_candidates_rejected_in_tightening"
        ],
        "rejected_as_non_governing_cleanup": pre_selection_state[
            "rejected_as_non_governing_cleanup"
        ],
        "rejected_as_non_governing_shear_strengthening": pre_selection_state[
            "rejected_as_non_governing_shear_strengthening"
        ],
        "rejected_as_non_material_improvement": pre_selection_state[
            "rejected_as_non_material_improvement"
        ],
        "tightening_step_count": iteration_candidate_flow_scope[
            "tightening_step_count"
        ],
        "max_tightening_steps": iteration_candidate_flow_scope["max_tightening_steps"],
        "no_actionable_after_full_tightening_search": iteration_candidate_flow_scope[
            "no_actionable_after_full_tightening_search"
        ],
        "candidate_family_depth_reached": pre_selection_state[
            "candidate_family_depth_reached"
        ],
        "final_governing_domain": pre_selection_state["final_governing_domain"],
        "shear_governing_mode_active": pre_selection_state[
            "shear_governing_mode_active"
        ],
        "shear_severity_band": pre_selection_state["shear_severity_band"],
        "shear_candidate_family_order": pre_selection_state[
            "shear_candidate_family_order"
        ],
        **_build_one_click_solver_iteration_candidate_flow_post_selection_shear_fields_coordinator(
            pre_selection_state=pre_selection_state,
        ),
        "domain_match_prune_used": pre_selection_state["domain_match_prune_used"],
        "shear_prune_rule_source": pre_selection_state["shear_prune_rule_source"],
        "cur_pass": pre_selection_state["cur_pass"],
        "step_trace": iteration_candidate_flow_scope["step_trace"],
        "initial_snapshot": iteration_candidate_flow_scope["initial_snapshot"],
        "cur_ib": pre_selection_state["cur_ib"],
        "winning_label": iteration_candidate_flow_scope["winning_label"],
        "winning_action_type": iteration_candidate_flow_scope["winning_action_type"],
        "in_band_shear_cleanup_deferral": pre_selection_state[
            "in_band_shear_cleanup_deferral"
        ],
        "target_domains_for_band": iteration_candidate_flow_scope[
            "target_domains_for_band"
        ],
        "target_band_domain": pre_selection_state["target_band_domain"],
        "seen_sigs": iteration_candidate_flow_scope["seen_sigs"],
        "step_committable_eval_trace": iteration_candidate_flow_scope[
            "step_committable_eval_trace"
        ],
        "final_resolved_shear_util": iteration_candidate_flow_scope[
            "final_resolved_shear_util"
        ],
        "final_resolved_web_util": iteration_candidate_flow_scope[
            "final_resolved_web_util"
        ],
        "shear_remove_links_candidate_seen": pre_selection_state[
            "shear_remove_links_candidate_seen"
        ],
        "shear_remove_links_candidate_truth_ok": pre_selection_state[
            "shear_remove_links_candidate_truth_ok"
        ],
        "shear_remove_links_candidate_dropped_reason": pre_selection_state[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "shear_remove_links_candidate_materiality": pre_selection_state[
            "shear_remove_links_candidate_materiality"
        ],
        "trace_callback": iteration_candidate_flow_scope["trace_callback"],
    }


def _dispatch_one_click_solver_post_selection_acceptance_flow_from_iteration_candidate_flow_coordinator(
    *,
    iteration_candidate_flow_scope: dict,
) -> dict:
    return _run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator(
        scored=iteration_candidate_flow_scope["scored"],
        cur_eval=iteration_candidate_flow_scope["cur_eval"],
        working=iteration_candidate_flow_scope["working"],
        mode_config=iteration_candidate_flow_scope["mode_config"],
        tightening_mode_active=iteration_candidate_flow_scope["tightening_mode_active"],
        step_idx=iteration_candidate_flow_scope["step_idx"],
        raw_n=iteration_candidate_flow_scope["raw_n"],
        pool_labels=iteration_candidate_flow_scope["pool_labels"],
        governing_domain=iteration_candidate_flow_scope["governing_domain"],
        tightening_meta=iteration_candidate_flow_scope["tightening_meta"],
        material_improvement_threshold=iteration_candidate_flow_scope[
            "material_improvement_threshold"
        ],
        reduction_candidates_considered=iteration_candidate_flow_scope[
            "reduction_candidates_considered"
        ],
        growth_candidates_rejected_in_tightening=iteration_candidate_flow_scope[
            "growth_candidates_rejected_in_tightening"
        ],
        rejected_as_non_governing_cleanup=iteration_candidate_flow_scope[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=iteration_candidate_flow_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        rejected_as_non_material_improvement=iteration_candidate_flow_scope[
            "rejected_as_non_material_improvement"
        ],
        tightening_step_count=iteration_candidate_flow_scope["tightening_step_count"],
        max_tightening_steps=iteration_candidate_flow_scope["max_tightening_steps"],
        no_actionable_after_full_tightening_search=iteration_candidate_flow_scope[
            "no_actionable_after_full_tightening_search"
        ],
        candidate_family_depth_reached=iteration_candidate_flow_scope[
            "candidate_family_depth_reached"
        ],
        final_governing_domain=iteration_candidate_flow_scope["final_governing_domain"],
        shear_governing_mode_active=iteration_candidate_flow_scope[
            "shear_governing_mode_active"
        ],
        shear_severity_band=iteration_candidate_flow_scope["shear_severity_band"],
        shear_candidate_family_order=iteration_candidate_flow_scope[
            "shear_candidate_family_order"
        ],
        spacing_candidates_considered=iteration_candidate_flow_scope[
            "spacing_candidates_considered"
        ],
        leg_candidates_considered=iteration_candidate_flow_scope["leg_candidates_considered"],
        dia_candidates_considered=iteration_candidate_flow_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=iteration_candidate_flow_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=iteration_candidate_flow_scope[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=iteration_candidate_flow_scope[
            "web_crushing_penalty_applied"
        ],
        rejected_as_spacing_too_weak=iteration_candidate_flow_scope[
            "rejected_as_spacing_too_weak"
        ],
        rejected_as_web_crushing_marginal=iteration_candidate_flow_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=iteration_candidate_flow_scope[
            "rejected_as_impractical_shear_layout"
        ],
        shear_governing_family_detected=iteration_candidate_flow_scope[
            "shear_governing_family_detected"
        ],
        governing_family_exists_after_domain_fix=iteration_candidate_flow_scope[
            "governing_family_exists_after_domain_fix"
        ],
        pruned_non_shear_family_count=iteration_candidate_flow_scope[
            "pruned_non_shear_family_count"
        ],
        domain_match_prune_used=iteration_candidate_flow_scope["domain_match_prune_used"],
        shear_prune_rule_source=iteration_candidate_flow_scope["shear_prune_rule_source"],
        cur_pass=iteration_candidate_flow_scope["cur_pass"],
        step_trace=iteration_candidate_flow_scope["step_trace"],
        initial_snapshot=iteration_candidate_flow_scope["initial_snapshot"],
        cur_ib=iteration_candidate_flow_scope["cur_ib"],
        winning_label=iteration_candidate_flow_scope["winning_label"],
        winning_action_type=iteration_candidate_flow_scope["winning_action_type"],
        in_band_shear_cleanup_deferral=iteration_candidate_flow_scope[
            "in_band_shear_cleanup_deferral"
        ],
        target_domains_for_band=iteration_candidate_flow_scope["target_domains_for_band"],
        target_band_domain=iteration_candidate_flow_scope["target_band_domain"],
        seen_sigs=iteration_candidate_flow_scope["seen_sigs"],
        step_committable_eval_trace=iteration_candidate_flow_scope[
            "step_committable_eval_trace"
        ],
        final_resolved_shear_util=iteration_candidate_flow_scope[
            "final_resolved_shear_util"
        ],
        final_resolved_web_util=iteration_candidate_flow_scope["final_resolved_web_util"],
        shear_remove_links_candidate_seen=iteration_candidate_flow_scope[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_truth_ok=iteration_candidate_flow_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        shear_remove_links_candidate_dropped_reason=iteration_candidate_flow_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        shear_remove_links_candidate_materiality=iteration_candidate_flow_scope[
            "shear_remove_links_candidate_materiality"
        ],
        trace_callback=iteration_candidate_flow_scope["trace_callback"],
    )


def _run_one_click_solver_iteration_candidate_flow_coordinator(
    *,
    iteration_gate_state: dict,
    working: dict,
    debug_enabled: bool,
    trace_run_id: str | None,
    step_idx: int,
    mode_config: dict,
    target_domains_for_band,
    target_band_domain,
    initial_snapshot: dict,
    winning_label,
    winning_action_type,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached: bool,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list,
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: bool,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    final_resolved_shear_util,
    final_resolved_web_util,
    step_committable_eval_trace,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason,
    shear_remove_links_candidate_materiality,
    t_lo,
    t_hi,
    seen_sigs: set,
    step_trace: list,
    trace_callback,
) -> dict:
    pre_selection_state = (
        _run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator(
            iteration_gate_state=iteration_gate_state,
            working=working,
            debug_enabled=debug_enabled,
            trace_run_id=trace_run_id,
            step_idx=step_idx,
            mode_config=mode_config,
            target_domains_for_band=target_domains_for_band,
            target_band_domain=target_band_domain,
            tightening_step_count=tightening_step_count,
            max_tightening_steps=max_tightening_steps,
            no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
            candidate_family_depth_reached=candidate_family_depth_reached,
            shear_governing_mode_active=shear_governing_mode_active,
            shear_severity_band=shear_severity_band,
            shear_candidate_family_order=shear_candidate_family_order,
            spacing_candidates_considered=spacing_candidates_considered,
            leg_candidates_considered=leg_candidates_considered,
            dia_candidates_considered=dia_candidates_considered,
            geometry_candidates_considered_for_shear=geometry_candidates_considered_for_shear,
            combined_candidates_considered_for_shear=combined_candidates_considered_for_shear,
            web_crushing_penalty_applied=web_crushing_penalty_applied,
            rejected_as_spacing_too_weak=rejected_as_spacing_too_weak,
            rejected_as_web_crushing_marginal=rejected_as_web_crushing_marginal,
            rejected_as_impractical_shear_layout=rejected_as_impractical_shear_layout,
            rejected_as_non_governing_cleanup=rejected_as_non_governing_cleanup,
            rejected_as_non_governing_shear_strengthening=rejected_as_non_governing_shear_strengthening,
            shear_remove_links_candidate_seen=shear_remove_links_candidate_seen,
            shear_remove_links_candidate_truth_ok=shear_remove_links_candidate_truth_ok,
            shear_remove_links_candidate_dropped_reason=shear_remove_links_candidate_dropped_reason,
            shear_remove_links_candidate_materiality=shear_remove_links_candidate_materiality,
            t_lo=t_lo,
            t_hi=t_hi,
            seen_sigs=seen_sigs,
            trace_callback=trace_callback,
        )
    )
    iteration_candidate_flow_post_selection_scope = (
        _build_one_click_solver_iteration_candidate_flow_post_selection_scope_coordinator(
            iteration_candidate_flow_scope=locals(),
            pre_selection_state=pre_selection_state,
        )
    )

    return _dispatch_one_click_solver_post_selection_acceptance_flow_from_iteration_candidate_flow_coordinator(
        iteration_candidate_flow_scope=iteration_candidate_flow_post_selection_scope,
    )


def _build_one_click_solver_iteration_loop_result_state_coordinator(
    *,
    iteration_loop_scope: dict,
) -> dict:
    return {
        "working": iteration_loop_scope["working"],
        "target_band_domain": iteration_loop_scope["target_band_domain"],
        "winning_label": iteration_loop_scope["winning_label"],
        "winning_action_type": iteration_loop_scope["winning_action_type"],
        "tightening_step_count": iteration_loop_scope["tightening_step_count"],
        "max_tightening_steps": iteration_loop_scope["max_tightening_steps"],
        "tightening_budget_extensions_used": iteration_loop_scope[
            "tightening_budget_extensions_used"
        ],
        "no_actionable_after_full_tightening_search": iteration_loop_scope[
            "no_actionable_after_full_tightening_search"
        ],
        "candidate_family_depth_reached": iteration_loop_scope[
            "candidate_family_depth_reached"
        ],
        "final_distance_to_band": iteration_loop_scope["final_distance_to_band"],
        "final_governing_domain": iteration_loop_scope["final_governing_domain"],
        "shear_governing_mode_active": iteration_loop_scope["shear_governing_mode_active"],
        "shear_severity_band": iteration_loop_scope["shear_severity_band"],
        "shear_candidate_family_order": iteration_loop_scope["shear_candidate_family_order"],
        "spacing_candidates_considered": iteration_loop_scope["spacing_candidates_considered"],
        "leg_candidates_considered": iteration_loop_scope["leg_candidates_considered"],
        "dia_candidates_considered": iteration_loop_scope["dia_candidates_considered"],
        "geometry_candidates_considered_for_shear": iteration_loop_scope[
            "geometry_candidates_considered_for_shear"
        ],
        "combined_candidates_considered_for_shear": iteration_loop_scope[
            "combined_candidates_considered_for_shear"
        ],
        "web_crushing_penalty_applied": iteration_loop_scope["web_crushing_penalty_applied"],
        "rejected_as_spacing_too_weak": iteration_loop_scope[
            "rejected_as_spacing_too_weak"
        ],
        "rejected_as_web_crushing_marginal": iteration_loop_scope[
            "rejected_as_web_crushing_marginal"
        ],
        "rejected_as_impractical_shear_layout": iteration_loop_scope[
            "rejected_as_impractical_shear_layout"
        ],
        "final_resolved_shear_util": iteration_loop_scope["final_resolved_shear_util"],
        "final_resolved_web_util": iteration_loop_scope["final_resolved_web_util"],
        "step_committable_eval_trace": iteration_loop_scope["step_committable_eval_trace"],
        "step_trace": iteration_loop_scope["step_trace"],
        "stop_reason": iteration_loop_scope["stop_reason"],
        "status": iteration_loop_scope["status"],
        "rejected_as_non_governing_cleanup": iteration_loop_scope[
            "rejected_as_non_governing_cleanup"
        ],
        "rejected_as_non_governing_shear_strengthening": iteration_loop_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        "shear_remove_links_candidate_seen": iteration_loop_scope[
            "shear_remove_links_candidate_seen"
        ],
        "shear_remove_links_candidate_truth_ok": iteration_loop_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        "shear_remove_links_candidate_dropped_reason": iteration_loop_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        "shear_remove_links_candidate_materiality": iteration_loop_scope[
            "shear_remove_links_candidate_materiality"
        ],
        "shear_governing_family_detected": iteration_loop_scope[
            "shear_governing_family_detected"
        ],
        "governing_family_exists_after_domain_fix": iteration_loop_scope[
            "governing_family_exists_after_domain_fix"
        ],
        "pruned_non_shear_family_count": iteration_loop_scope[
            "pruned_non_shear_family_count"
        ],
    }


def _dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator(
    *,
    iteration_loop_scope: dict,
) -> dict:
    return _run_one_click_solver_iteration_candidate_flow_coordinator(
        iteration_gate_state=iteration_loop_scope["iteration_gate_state"],
        working=iteration_loop_scope["working"],
        debug_enabled=iteration_loop_scope["debug_enabled"],
        trace_run_id=iteration_loop_scope["trace_run_id"],
        step_idx=iteration_loop_scope["step_idx"],
        mode_config=iteration_loop_scope["mode_config"],
        target_domains_for_band=iteration_loop_scope["target_domains_for_band"],
        target_band_domain=iteration_loop_scope["target_band_domain"],
        initial_snapshot=iteration_loop_scope["initial_snapshot"],
        winning_label=iteration_loop_scope["winning_label"],
        winning_action_type=iteration_loop_scope["winning_action_type"],
        tightening_step_count=iteration_loop_scope["tightening_step_count"],
        max_tightening_steps=iteration_loop_scope["max_tightening_steps"],
        no_actionable_after_full_tightening_search=iteration_loop_scope[
            "no_actionable_after_full_tightening_search"
        ],
        candidate_family_depth_reached=iteration_loop_scope[
            "candidate_family_depth_reached"
        ],
        shear_governing_mode_active=iteration_loop_scope["shear_governing_mode_active"],
        shear_severity_band=iteration_loop_scope["shear_severity_band"],
        shear_candidate_family_order=iteration_loop_scope["shear_candidate_family_order"],
        spacing_candidates_considered=iteration_loop_scope["spacing_candidates_considered"],
        leg_candidates_considered=iteration_loop_scope["leg_candidates_considered"],
        dia_candidates_considered=iteration_loop_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=iteration_loop_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=iteration_loop_scope[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=iteration_loop_scope[
            "web_crushing_penalty_applied"
        ],
        rejected_as_spacing_too_weak=iteration_loop_scope[
            "rejected_as_spacing_too_weak"
        ],
        rejected_as_web_crushing_marginal=iteration_loop_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=iteration_loop_scope[
            "rejected_as_impractical_shear_layout"
        ],
        final_resolved_shear_util=iteration_loop_scope["final_resolved_shear_util"],
        final_resolved_web_util=iteration_loop_scope["final_resolved_web_util"],
        step_committable_eval_trace=iteration_loop_scope["step_committable_eval_trace"],
        rejected_as_non_governing_cleanup=iteration_loop_scope[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=iteration_loop_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        shear_remove_links_candidate_seen=iteration_loop_scope[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_truth_ok=iteration_loop_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        shear_remove_links_candidate_dropped_reason=iteration_loop_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        shear_remove_links_candidate_materiality=iteration_loop_scope[
            "shear_remove_links_candidate_materiality"
        ],
        t_lo=iteration_loop_scope["t_lo"],
        t_hi=iteration_loop_scope["t_hi"],
        seen_sigs=iteration_loop_scope["seen_sigs"],
        step_trace=iteration_loop_scope["step_trace"],
        trace_callback=iteration_loop_scope["trace_callback"],
    )


def _unpack_one_click_solver_iteration_candidate_flow_state_for_loop_coordinator(
    *,
    iteration_candidate_flow_state: dict,
) -> tuple:
    return (
        iteration_candidate_flow_state["working"],
        iteration_candidate_flow_state["target_band_domain"],
        iteration_candidate_flow_state["winning_label"],
        iteration_candidate_flow_state["winning_action_type"],
        iteration_candidate_flow_state["tightening_step_count"],
        iteration_candidate_flow_state["no_actionable_after_full_tightening_search"],
        iteration_candidate_flow_state["candidate_family_depth_reached"],
        iteration_candidate_flow_state["final_distance_to_band"],
        iteration_candidate_flow_state["final_governing_domain"],
        iteration_candidate_flow_state["shear_governing_mode_active"],
        iteration_candidate_flow_state["shear_severity_band"],
        iteration_candidate_flow_state["shear_candidate_family_order"],
        iteration_candidate_flow_state["spacing_candidates_considered"],
        iteration_candidate_flow_state["leg_candidates_considered"],
        iteration_candidate_flow_state["dia_candidates_considered"],
        iteration_candidate_flow_state["geometry_candidates_considered_for_shear"],
        iteration_candidate_flow_state["combined_candidates_considered_for_shear"],
        iteration_candidate_flow_state["web_crushing_penalty_applied"],
        iteration_candidate_flow_state["rejected_as_spacing_too_weak"],
        iteration_candidate_flow_state["rejected_as_web_crushing_marginal"],
        iteration_candidate_flow_state["rejected_as_impractical_shear_layout"],
        iteration_candidate_flow_state["final_resolved_shear_util"],
        iteration_candidate_flow_state["final_resolved_web_util"],
        iteration_candidate_flow_state["stop_reason"],
        iteration_candidate_flow_state["status"],
        iteration_candidate_flow_state["rejected_as_non_governing_cleanup"],
        iteration_candidate_flow_state["rejected_as_non_governing_shear_strengthening"],
        iteration_candidate_flow_state["shear_remove_links_candidate_seen"],
        iteration_candidate_flow_state["shear_remove_links_candidate_truth_ok"],
        iteration_candidate_flow_state["shear_remove_links_candidate_dropped_reason"],
        iteration_candidate_flow_state["shear_remove_links_candidate_materiality"],
        iteration_candidate_flow_state["shear_governing_family_detected"],
        iteration_candidate_flow_state["governing_family_exists_after_domain_fix"],
        iteration_candidate_flow_state["pruned_non_shear_family_count"],
    )


def _dispatch_one_click_solver_iteration_gate_state_from_iteration_loop_coordinator(
    *,
    iteration_loop_scope: dict,
) -> dict:
    return _prepare_one_click_solver_iteration_gate_state_coordinator(
        step_idx=iteration_loop_scope["step_idx"],
        working=iteration_loop_scope["working"],
        mode_config=iteration_loop_scope["mode_config"],
        target_band_domain=iteration_loop_scope["target_band_domain"],
        target_domains_for_band=iteration_loop_scope["target_domains_for_band"],
        step_trace=iteration_loop_scope["step_trace"],
        initial_snapshot=iteration_loop_scope["initial_snapshot"],
        winning_label=iteration_loop_scope["winning_label"],
        winning_action_type=iteration_loop_scope["winning_action_type"],
        tightening_step_count=iteration_loop_scope["tightening_step_count"],
        max_tightening_steps=iteration_loop_scope["max_tightening_steps"],
        tightening_budget_extensions_used=iteration_loop_scope[
            "tightening_budget_extensions_used"
        ],
        tightening_budget_extension_cap=iteration_loop_scope[
            "tightening_budget_extension_cap"
        ],
        candidate_family_depth_reached=iteration_loop_scope[
            "candidate_family_depth_reached"
        ],
        trace_callback=iteration_loop_scope["trace_callback"],
    )


def _run_one_click_solver_iteration_loop_coordinator(
    *,
    max_steps: int,
    debug_enabled: bool,
    trace_run_id: str | None,
    trace_callback,
    working: dict,
    mode_config: dict,
    target_band_domain,
    target_domains_for_band,
    step_trace: list,
    initial_snapshot: dict,
    winning_label,
    winning_action_type,
    tightening_step_count: int,
    max_tightening_steps: int,
    tightening_budget_extensions_used: int,
    tightening_budget_extension_cap: int,
    candidate_family_depth_reached: bool,
    stop_reason: str,
    status: str,
    final_distance_to_band,
    final_governing_domain,
    shear_governing_mode_active: bool,
    shear_severity_band: str,
    shear_candidate_family_order: list,
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: bool,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    final_resolved_shear_util,
    final_resolved_web_util,
    step_committable_eval_trace,
    no_actionable_after_full_tightening_search: bool,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason,
    shear_remove_links_candidate_materiality,
    t_lo,
    t_hi,
    seen_sigs: set,
) -> dict:
    for step_idx in range(max_steps):
        iteration_gate_state = (
            _dispatch_one_click_solver_iteration_gate_state_from_iteration_loop_coordinator(
                iteration_loop_scope=locals(),
            )
        )
        if "max_tightening_steps" in iteration_gate_state:
            max_tightening_steps = iteration_gate_state["max_tightening_steps"]
        if "tightening_budget_extensions_used" in iteration_gate_state:
            tightening_budget_extensions_used = iteration_gate_state["tightening_budget_extensions_used"]
        if iteration_gate_state["should_continue"]:
            continue
        if iteration_gate_state["should_break"]:
            stop_reason = iteration_gate_state["stop_reason"]
            status = iteration_gate_state["status"]
            if iteration_gate_state.get("final_distance_to_band") is not None:
                final_distance_to_band = iteration_gate_state["final_distance_to_band"]
            break

        iteration_candidate_flow_state = (
            _dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator(
                iteration_loop_scope=locals(),
            )
        )
        (
            working,
            target_band_domain,
            winning_label,
            winning_action_type,
            tightening_step_count,
            no_actionable_after_full_tightening_search,
            candidate_family_depth_reached,
            final_distance_to_band,
            final_governing_domain,
            shear_governing_mode_active,
            shear_severity_band,
            shear_candidate_family_order,
            spacing_candidates_considered,
            leg_candidates_considered,
            dia_candidates_considered,
            geometry_candidates_considered_for_shear,
            combined_candidates_considered_for_shear,
            web_crushing_penalty_applied,
            rejected_as_spacing_too_weak,
            rejected_as_web_crushing_marginal,
            rejected_as_impractical_shear_layout,
            final_resolved_shear_util,
            final_resolved_web_util,
            stop_reason,
            status,
            rejected_as_non_governing_cleanup,
            rejected_as_non_governing_shear_strengthening,
            shear_remove_links_candidate_seen,
            shear_remove_links_candidate_truth_ok,
            shear_remove_links_candidate_dropped_reason,
            shear_remove_links_candidate_materiality,
            shear_governing_family_detected,
            governing_family_exists_after_domain_fix,
            pruned_non_shear_family_count,
        ) = _unpack_one_click_solver_iteration_candidate_flow_state_for_loop_coordinator(
            iteration_candidate_flow_state=iteration_candidate_flow_state,
        )
        if iteration_candidate_flow_state["should_break"]:
            break

    return _build_one_click_solver_iteration_loop_result_state_coordinator(
        iteration_loop_scope=locals(),
    )


def _build_one_click_solver_final_trace_return_payload_coordinator(
    *,
    final_trace_scope: dict,
) -> dict:
    return _build_final_solver_return_coordinator(
        step_trace=final_trace_scope["step_trace"],
        init_worst=final_trace_scope["init_worst"],
        final_worst=final_trace_scope["final_worst"],
        t_lo=final_trace_scope["t_lo"],
        t_hi=final_trace_scope["t_hi"],
        stop_reason=final_trace_scope["stop_reason"],
        final_in_band=final_trace_scope["final_in_band"],
        final_pass=final_trace_scope["final_pass"],
        status=final_trace_scope["status"],
        rid=final_trace_scope["trace_run_id"],
        initial_coherence=final_trace_scope["initial_coherence"],
        tightening_step_count=final_trace_scope["tightening_step_count"],
        max_tightening_steps=final_trace_scope["max_tightening_steps"],
        no_actionable_after_full_tightening_search=final_trace_scope[
            "no_actionable_after_full_tightening_search"
        ],
        candidate_family_depth_reached=final_trace_scope["candidate_family_depth_reached"],
        final_distance_to_band=final_trace_scope["final_distance_to_band"],
        shear_governing_mode_active=final_trace_scope["shear_governing_mode_active"],
        shear_severity_band=final_trace_scope["shear_severity_band"],
        shear_candidate_family_order=final_trace_scope["shear_candidate_family_order"],
        spacing_candidates_considered=final_trace_scope["spacing_candidates_considered"],
        leg_candidates_considered=final_trace_scope["leg_candidates_considered"],
        dia_candidates_considered=final_trace_scope["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=final_trace_scope[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=final_trace_scope[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=final_trace_scope["web_crushing_penalty_applied"],
        rejected_as_spacing_too_weak=final_trace_scope["rejected_as_spacing_too_weak"],
        rejected_as_web_crushing_marginal=final_trace_scope[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=final_trace_scope[
            "rejected_as_impractical_shear_layout"
        ],
        final_resolved_shear_util=final_trace_scope["final_resolved_shear_util"],
        final_resolved_web_util=final_trace_scope["final_resolved_web_util"],
        shear_governing_family_detected=final_trace_scope["shear_governing_family_detected"],
        governing_family_exists_after_domain_fix=final_trace_scope[
            "governing_family_exists_after_domain_fix"
        ],
        pruned_non_shear_family_count=final_trace_scope["pruned_non_shear_family_count"],
        final_governing_domain=final_trace_scope["final_governing_domain"],
        rejected_as_non_governing_cleanup=final_trace_scope[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=final_trace_scope[
            "rejected_as_non_governing_shear_strengthening"
        ],
        target_band_domain=final_trace_scope["target_band_domain"],
        target_domains_for_band=final_trace_scope["target_domains_for_band"],
        final_target_domains=final_trace_scope["final_target_domains"],
        final_eval=final_trace_scope["final_eval"],
        mode_config=final_trace_scope["mode_config"],
        step_committable_eval_trace=final_trace_scope["step_committable_eval_trace"],
        final_eval_internal_worst_util_dbg=final_trace_scope[
            "final_eval_internal_worst_util_dbg"
        ],
        final_eval_committable_worst_util_dbg=final_trace_scope[
            "final_eval_committable_worst_util_dbg"
        ],
        final_eval_used_source_dbg=final_trace_scope["final_eval_used_source_dbg"],
        final_eval_committable_updates_dbg=final_trace_scope[
            "final_eval_committable_updates_dbg"
        ],
        final_objective_util=final_trace_scope["final_objective_util"],
        shear_remove_links_candidate_seen=final_trace_scope[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_truth_ok=final_trace_scope[
            "shear_remove_links_candidate_truth_ok"
        ],
        shear_remove_links_candidate_dropped_reason=final_trace_scope[
            "shear_remove_links_candidate_dropped_reason"
        ],
        shear_remove_links_candidate_materiality=final_trace_scope[
            "shear_remove_links_candidate_materiality"
        ],
        early_in_band_exit_blocked_for_tightening=final_trace_scope[
            "early_in_band_exit_blocked_for_tightening"
        ],
        early_in_band_exit_tightening_classification=final_trace_scope[
            "early_in_band_exit_tightening_classification"
        ],
        early_in_band_exit_available_tightening_paths=final_trace_scope[
            "early_in_band_exit_available_tightening_paths"
        ],
        early_in_band_exit_reason=final_trace_scope["early_in_band_exit_reason"],
        partial_failing_final_updates_blocked=final_trace_scope[
            "partial_failing_final_updates_blocked"
        ],
        partial_failing_final_updates_raw=final_trace_scope["partial_failing_final_updates_raw"],
        best_available_out_of_band_retained=final_trace_scope[
            "best_available_out_of_band_retained"
        ],
        rescue_debug=final_trace_scope["rescue_debug"],
        rescue_gate_debug=final_trace_scope["rescue_gate_debug"],
        final_updates=final_trace_scope["final_updates"],
        working=final_trace_scope["working"],
        winning_label=final_trace_scope["winning_label"],
        winning_action_type=final_trace_scope["winning_action_type"],
    )


def _complete_one_click_solver_final_trace_and_return_coordinator(
    *,
    stop_reason,
    step_trace: list[dict],
    status: str,
    final_worst,
    final_in_band: bool,
    final_pass: bool,
    winning_label: str | None,
    winning_action_type: str | None,
    final_updates: dict,
    tightening_step_count: int,
    max_tightening_steps: int,
    final_eval: dict,
    mode_config: dict,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached,
    final_distance_to_band,
    shear_governing_mode_active: bool,
    shear_severity_band: str | None,
    shear_candidate_family_order,
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: int,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    final_resolved_shear_util,
    final_resolved_web_util,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    rescue_debug: dict,
    trace_callback,
    trace_run_id: str | None,
    stop_traced: list,
    init_worst,
    t_lo,
    t_hi,
    initial_coherence,
    final_governing_domain,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    target_band_domain: str | None,
    target_domains_for_band,
    final_target_domains,
    step_committable_eval_trace: list[dict],
    final_eval_internal_worst_util_dbg,
    final_eval_committable_worst_util_dbg,
    final_eval_used_source_dbg,
    final_eval_committable_updates_dbg,
    final_objective_util,
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason,
    shear_remove_links_candidate_materiality,
    early_in_band_exit_blocked_for_tightening: bool,
    early_in_band_exit_tightening_classification,
    early_in_band_exit_available_tightening_paths,
    early_in_band_exit_reason,
    partial_failing_final_updates_blocked: bool,
    partial_failing_final_updates_raw,
    best_available_out_of_band_retained: bool,
    rescue_gate_debug: dict,
    working: dict,
) -> dict:
    if trace_run_id and not stop_traced[0]:
        _trace_final_fallback_solver_stop_coordinator(
            stop_reason=stop_reason,
            step_trace=step_trace,
            status=status,
            final_worst=final_worst,
            final_in_band=final_in_band,
            final_pass=final_pass,
            winning_label=winning_label,
            winning_action_type=winning_action_type,
            final_updates=final_updates,
            tightening_step_count=tightening_step_count,
            max_tightening_steps=max_tightening_steps,
            final_eval=final_eval,
            mode_config=mode_config,
            no_actionable_after_full_tightening_search=no_actionable_after_full_tightening_search,
            candidate_family_depth_reached=candidate_family_depth_reached,
            final_distance_to_band=final_distance_to_band,
            shear_governing_mode_active=shear_governing_mode_active,
            shear_severity_band=shear_severity_band,
            shear_candidate_family_order=shear_candidate_family_order,
            spacing_candidates_considered=spacing_candidates_considered,
            leg_candidates_considered=leg_candidates_considered,
            dia_candidates_considered=dia_candidates_considered,
            geometry_candidates_considered_for_shear=geometry_candidates_considered_for_shear,
            combined_candidates_considered_for_shear=combined_candidates_considered_for_shear,
            web_crushing_penalty_applied=web_crushing_penalty_applied,
            rejected_as_spacing_too_weak=rejected_as_spacing_too_weak,
            rejected_as_web_crushing_marginal=rejected_as_web_crushing_marginal,
            rejected_as_impractical_shear_layout=rejected_as_impractical_shear_layout,
            final_resolved_shear_util=final_resolved_shear_util,
            final_resolved_web_util=final_resolved_web_util,
            shear_governing_family_detected=shear_governing_family_detected,
            governing_family_exists_after_domain_fix=governing_family_exists_after_domain_fix,
            pruned_non_shear_family_count=pruned_non_shear_family_count,
            rescue_debug=rescue_debug,
            trace_callback=trace_callback,
        )

    return _build_one_click_solver_final_trace_return_payload_coordinator(
        final_trace_scope=locals(),
    )


def _dispatch_one_click_solver_rescue_seed_loop_from_finalization_coordinator(
    *,
    finalization_scope: dict,
) -> dict:
    return _prepare_one_click_solver_rescue_seed_loop_state_coordinator(
        rescue_should_enter=finalization_scope["rescue_should_enter"],
        rescue_family=finalization_scope["rescue_family"],
        rescue_tier_requested=finalization_scope["rescue_tier_requested"],
        rescue_entry_reason=finalization_scope["rescue_entry_reason"],
        initial_snapshot=finalization_scope["initial_snapshot"],
        max_steps=finalization_scope["max_steps"],
        debug_enabled=finalization_scope["debug_enabled"],
        trace_run_id=finalization_scope["trace_run_id"],
        trace_source=finalization_scope["trace_source"],
        attempted_seed_keys=finalization_scope["attempted_seed_keys"],
        rescue_debug=finalization_scope["rescue_debug"],
        final_eval=finalization_scope["final_eval"],
        mode_config=finalization_scope["mode_config"],
        target_domains_for_band=finalization_scope["target_domains_for_band"],
        trace_callback=finalization_scope["trace_callback"],
    )


def _dispatch_one_click_solver_partial_failing_final_updates_guard_from_finalization_coordinator(
    *,
    finalization_scope: dict,
) -> dict:
    return _handle_one_click_solver_partial_failing_final_updates_guard_coordinator(
        final_updates=finalization_scope["final_updates"],
        final_ok=finalization_scope["final_ok"],
        final_eval=finalization_scope["final_eval"],
        mode_config=finalization_scope["mode_config"],
        init_pass=finalization_scope["init_pass"],
        final_pass=finalization_scope["final_pass"],
        init_progress=finalization_scope["init_progress"],
        init_eval=finalization_scope["init_eval"],
        final_spacing_fail=finalization_scope["final_spacing_fail"],
        final_target_domains=finalization_scope["final_target_domains"],
        stop_reason=finalization_scope["stop_reason"],
        winning_label=finalization_scope["winning_label"],
        winning_action_type=finalization_scope["winning_action_type"],
    )


def _dispatch_one_click_solver_final_evaluation_state_from_finalization_coordinator(
    *,
    finalization_scope: dict,
) -> dict:
    return _prepare_one_click_solver_final_evaluation_state_coordinator(
        working=finalization_scope["working"],
        initial_snapshot=finalization_scope["initial_snapshot"],
        winning_label=finalization_scope["winning_label"],
        winning_action_type=finalization_scope["winning_action_type"],
        target_domains_for_band=finalization_scope["target_domains_for_band"],
        target_band_domain=finalization_scope["target_band_domain"],
        mode_config=finalization_scope["mode_config"],
        init_worst=finalization_scope["init_worst"],
        final_resolved_shear_util=finalization_scope["final_resolved_shear_util"],
        final_resolved_web_util=finalization_scope["final_resolved_web_util"],
    )


def _dispatch_one_click_solver_final_band_hit_stop_normalization_from_finalization_coordinator(
    *,
    finalization_scope: dict,
) -> dict:
    return _handle_one_click_solver_final_band_hit_stop_normalization_coordinator(
        final_band_hit=finalization_scope["final_band_hit"],
        stop_reason=finalization_scope["stop_reason"],
        status=finalization_scope["status"],
    )


def _dispatch_one_click_solver_rescue_entry_decision_from_finalization_coordinator(
    *,
    finalization_scope: dict,
) -> dict:
    return _prepare_one_click_solver_rescue_entry_decision_state_coordinator(
        rescue_enabled=finalization_scope["rescue_enabled"],
        rescue_debug=finalization_scope["rescue_debug"],
        initial_snapshot=finalization_scope["initial_snapshot"],
        init_eval=finalization_scope["init_eval"],
        final_eval=finalization_scope["final_eval"],
        final_pass=finalization_scope["final_pass"],
        final_updates=finalization_scope["final_updates"],
        stop_reason=finalization_scope["stop_reason"],
        mode_config=finalization_scope["mode_config"],
        trace_callback=finalization_scope["trace_callback"],
    )


def _dispatch_one_click_solver_rescue_seed_result_from_finalization_coordinator(
    *,
    finalization_scope: dict,
) -> tuple[bool, dict | None]:
    rescue_seed_loop_state = (
        _dispatch_one_click_solver_rescue_seed_loop_from_finalization_coordinator(
            finalization_scope=finalization_scope,
        )
    )
    return (
        bool(rescue_seed_loop_state["should_return_rescue_result"]),
        rescue_seed_loop_state["rescue_result"],
    )


def _unpack_one_click_solver_final_evaluation_state_for_finalization_coordinator(
    *,
    final_evaluation_state: dict,
) -> tuple:
    return (
        final_evaluation_state["final_eval_internal"],
        final_evaluation_state["final_updates"],
        final_evaluation_state["final_eval"],
        final_evaluation_state["final_eval_internal_worst_util_dbg"],
        final_evaluation_state["final_eval_committable_worst_util_dbg"],
        final_evaluation_state["final_eval_used_source_dbg"],
        final_evaluation_state["final_eval_committable_updates_dbg"],
        final_evaluation_state["final_target_domains"],
        final_evaluation_state["final_worst"],
        final_evaluation_state["final_pass"],
        final_evaluation_state["final_ok"],
        final_evaluation_state["final_spacing_fail"],
        final_evaluation_state["final_in_band"],
        final_evaluation_state["final_band_hit"],
        final_evaluation_state["final_objective_util"],
        final_evaluation_state["final_distance_to_band"],
        final_evaluation_state["final_resolved_shear_util"],
        final_evaluation_state["final_resolved_web_util"],
    )


def _unpack_one_click_solver_partial_failing_guard_state_for_finalization_coordinator(
    *,
    partial_failing_final_updates_guard_state: dict,
) -> tuple:
    return (
        partial_failing_final_updates_guard_state["final_updates"],
        partial_failing_final_updates_guard_state["stop_reason"],
        partial_failing_final_updates_guard_state["winning_label"],
        partial_failing_final_updates_guard_state["winning_action_type"],
        partial_failing_final_updates_guard_state[
            "partial_failing_final_updates_blocked"
        ],
        partial_failing_final_updates_guard_state["partial_failing_final_updates_raw"],
        partial_failing_final_updates_guard_state[
            "best_available_out_of_band_retained"
        ],
    )


def _run_one_click_solver_finalization_after_final_evaluation_coordinator(
    *,
    finalization_scope: dict,
    final_evaluation_state: dict,
) -> dict:
    (
        final_eval_internal,
        final_updates,
        final_eval,
        final_eval_internal_worst_util_dbg,
        final_eval_committable_worst_util_dbg,
        final_eval_used_source_dbg,
        final_eval_committable_updates_dbg,
        final_target_domains,
        final_worst,
        final_pass,
        final_ok,
        final_spacing_fail,
        final_in_band,
        final_band_hit,
        final_objective_util,
        final_distance_to_band,
        final_resolved_shear_util,
        final_resolved_web_util,
    ) = _unpack_one_click_solver_final_evaluation_state_for_finalization_coordinator(
        final_evaluation_state=final_evaluation_state,
    )
    finalization_after_eval_scope = dict(finalization_scope)
    finalization_after_eval_scope.update(
        {
            "final_eval_internal": final_eval_internal,
            "final_updates": final_updates,
            "final_eval": final_eval,
            "final_eval_internal_worst_util_dbg": final_eval_internal_worst_util_dbg,
            "final_eval_committable_worst_util_dbg": final_eval_committable_worst_util_dbg,
            "final_eval_used_source_dbg": final_eval_used_source_dbg,
            "final_eval_committable_updates_dbg": final_eval_committable_updates_dbg,
            "final_target_domains": final_target_domains,
            "final_worst": final_worst,
            "final_pass": final_pass,
            "final_ok": final_ok,
            "final_spacing_fail": final_spacing_fail,
            "final_in_band": final_in_band,
            "final_band_hit": final_band_hit,
            "final_objective_util": final_objective_util,
            "final_distance_to_band": final_distance_to_band,
            "final_resolved_shear_util": final_resolved_shear_util,
            "final_resolved_web_util": final_resolved_web_util,
        }
    )

    partial_failing_final_updates_guard_state = (
        _dispatch_one_click_solver_partial_failing_final_updates_guard_from_finalization_coordinator(
            finalization_scope=finalization_after_eval_scope,
        )
    )
    (
        final_updates,
        stop_reason,
        winning_label,
        winning_action_type,
        partial_failing_final_updates_blocked,
        partial_failing_final_updates_raw,
        best_available_out_of_band_retained,
    ) = _unpack_one_click_solver_partial_failing_guard_state_for_finalization_coordinator(
        partial_failing_final_updates_guard_state=partial_failing_final_updates_guard_state,
    )
    finalization_after_eval_scope.update(
        {
            "final_updates": final_updates,
            "stop_reason": stop_reason,
            "winning_label": winning_label,
            "winning_action_type": winning_action_type,
            "partial_failing_final_updates_blocked": partial_failing_final_updates_blocked,
            "partial_failing_final_updates_raw": partial_failing_final_updates_raw,
            "best_available_out_of_band_retained": best_available_out_of_band_retained,
        }
    )

    final_band_hit_stop_normalization_state = (
        _dispatch_one_click_solver_final_band_hit_stop_normalization_from_finalization_coordinator(
            finalization_scope=finalization_after_eval_scope,
        )
    )
    finalization_after_eval_scope.update(
        {
            "stop_reason": final_band_hit_stop_normalization_state["stop_reason"],
            "status": final_band_hit_stop_normalization_state["status"],
        }
    )

    rescue_entry_decision_state = (
        _dispatch_one_click_solver_rescue_entry_decision_from_finalization_coordinator(
            finalization_scope=finalization_after_eval_scope,
        )
    )
    finalization_after_eval_scope.update(
        {
            "rescue_should_enter": rescue_entry_decision_state["rescue_should_enter"],
            "rescue_entry_reason": rescue_entry_decision_state["rescue_entry_reason"],
            "rescue_family": rescue_entry_decision_state["rescue_family"],
            "rescue_tier_requested": rescue_entry_decision_state["rescue_tier_requested"],
            "rescue_gate_debug": rescue_entry_decision_state["rescue_gate_debug"],
        }
    )

    should_return_rescue_result, rescue_result = (
        _dispatch_one_click_solver_rescue_seed_result_from_finalization_coordinator(
            finalization_scope=finalization_after_eval_scope,
        )
    )
    if should_return_rescue_result:
        return rescue_result

    return _dispatch_one_click_solver_final_trace_return_coordinator(
        finalization_scope=finalization_after_eval_scope,
    )


def _finalize_one_click_solver_result_coordinator(
    *,
    working: dict,
    initial_snapshot: dict,
    winning_label: str | None,
    winning_action_type: str | None,
    target_domains_for_band,
    target_band_domain: str | None,
    mode_config: dict,
    init_worst,
    final_resolved_shear_util,
    final_resolved_web_util,
    init_pass: bool,
    init_progress,
    init_eval: dict,
    stop_reason,
    status: str,
    rescue_enabled: bool,
    rescue_debug: dict,
    max_steps: int,
    debug_enabled: bool,
    trace_run_id: str | None,
    trace_source: str,
    attempted_seed_keys: set,
    stop_traced: list,
    step_trace: list[dict],
    t_lo,
    t_hi,
    initial_coherence,
    tightening_step_count: int,
    max_tightening_steps: int,
    no_actionable_after_full_tightening_search: bool,
    candidate_family_depth_reached,
    shear_governing_mode_active: bool,
    shear_severity_band: str | None,
    shear_candidate_family_order,
    spacing_candidates_considered: int,
    leg_candidates_considered: int,
    dia_candidates_considered: int,
    geometry_candidates_considered_for_shear: int,
    combined_candidates_considered_for_shear: int,
    web_crushing_penalty_applied: int,
    rejected_as_spacing_too_weak: int,
    rejected_as_web_crushing_marginal: int,
    rejected_as_impractical_shear_layout: int,
    shear_governing_family_detected: bool,
    governing_family_exists_after_domain_fix: bool,
    pruned_non_shear_family_count: int,
    final_governing_domain,
    rejected_as_non_governing_cleanup: int,
    rejected_as_non_governing_shear_strengthening: int,
    step_committable_eval_trace: list[dict],
    shear_remove_links_candidate_seen: bool,
    shear_remove_links_candidate_truth_ok: bool,
    shear_remove_links_candidate_dropped_reason,
    shear_remove_links_candidate_materiality,
    early_in_band_exit_blocked_for_tightening: bool,
    early_in_band_exit_tightening_classification,
    early_in_band_exit_available_tightening_paths,
    early_in_band_exit_reason,
    trace_callback,
) -> dict:
    final_evaluation_state = (
        _dispatch_one_click_solver_final_evaluation_state_from_finalization_coordinator(
            finalization_scope=locals(),
        )
    )
    return _run_one_click_solver_finalization_after_final_evaluation_coordinator(
        finalization_scope=locals(),
        final_evaluation_state=final_evaluation_state,
    )


def _finish_one_click_solver_iteration_loop_result_coordinator(
    *,
    runtime_setup_state: dict,
    iteration_loop_state: dict,
    max_steps: int,
    debug_enabled: bool,
    trace_source: str,
    rescue_enabled: bool,
) -> dict:
    return _finalize_one_click_solver_result_coordinator(
        working=iteration_loop_state["working"],
        initial_snapshot=runtime_setup_state["initial_snapshot"],
        winning_label=iteration_loop_state["winning_label"],
        winning_action_type=iteration_loop_state["winning_action_type"],
        target_domains_for_band=runtime_setup_state["target_domains_for_band"],
        target_band_domain=iteration_loop_state["target_band_domain"],
        mode_config=runtime_setup_state["mode_config"],
        init_worst=runtime_setup_state["init_worst"],
        final_resolved_shear_util=iteration_loop_state["final_resolved_shear_util"],
        final_resolved_web_util=iteration_loop_state["final_resolved_web_util"],
        init_pass=runtime_setup_state["init_pass"],
        init_progress=runtime_setup_state["init_progress"],
        init_eval=runtime_setup_state["init_eval"],
        stop_reason=iteration_loop_state["stop_reason"],
        status=iteration_loop_state["status"],
        rescue_enabled=rescue_enabled,
        rescue_debug=runtime_setup_state["rescue_debug"],
        max_steps=max_steps,
        debug_enabled=debug_enabled,
        trace_run_id=runtime_setup_state["rid"],
        trace_source=trace_source,
        attempted_seed_keys=runtime_setup_state["attempted_seed_keys"],
        stop_traced=runtime_setup_state["stop_traced"],
        step_trace=iteration_loop_state["step_trace"],
        t_lo=runtime_setup_state["t_lo"],
        t_hi=runtime_setup_state["t_hi"],
        initial_coherence=runtime_setup_state["initial_coherence"],
        tightening_step_count=iteration_loop_state["tightening_step_count"],
        max_tightening_steps=iteration_loop_state["max_tightening_steps"],
        no_actionable_after_full_tightening_search=iteration_loop_state[
            "no_actionable_after_full_tightening_search"
        ],
        candidate_family_depth_reached=iteration_loop_state[
            "candidate_family_depth_reached"
        ],
        shear_governing_mode_active=iteration_loop_state["shear_governing_mode_active"],
        shear_severity_band=iteration_loop_state["shear_severity_band"],
        shear_candidate_family_order=iteration_loop_state["shear_candidate_family_order"],
        spacing_candidates_considered=iteration_loop_state["spacing_candidates_considered"],
        leg_candidates_considered=iteration_loop_state["leg_candidates_considered"],
        dia_candidates_considered=iteration_loop_state["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=iteration_loop_state[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=iteration_loop_state[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=iteration_loop_state["web_crushing_penalty_applied"],
        rejected_as_spacing_too_weak=iteration_loop_state["rejected_as_spacing_too_weak"],
        rejected_as_web_crushing_marginal=iteration_loop_state[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=iteration_loop_state[
            "rejected_as_impractical_shear_layout"
        ],
        shear_governing_family_detected=iteration_loop_state[
            "shear_governing_family_detected"
        ],
        governing_family_exists_after_domain_fix=iteration_loop_state[
            "governing_family_exists_after_domain_fix"
        ],
        pruned_non_shear_family_count=iteration_loop_state["pruned_non_shear_family_count"],
        final_governing_domain=iteration_loop_state["final_governing_domain"],
        rejected_as_non_governing_cleanup=iteration_loop_state[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=iteration_loop_state[
            "rejected_as_non_governing_shear_strengthening"
        ],
        step_committable_eval_trace=iteration_loop_state["step_committable_eval_trace"],
        shear_remove_links_candidate_seen=iteration_loop_state[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_truth_ok=iteration_loop_state[
            "shear_remove_links_candidate_truth_ok"
        ],
        shear_remove_links_candidate_dropped_reason=iteration_loop_state[
            "shear_remove_links_candidate_dropped_reason"
        ],
        shear_remove_links_candidate_materiality=iteration_loop_state[
            "shear_remove_links_candidate_materiality"
        ],
        early_in_band_exit_blocked_for_tightening=runtime_setup_state[
            "early_in_band_exit_blocked_for_tightening"
        ],
        early_in_band_exit_tightening_classification=runtime_setup_state[
            "early_in_band_exit_tightening_classification"
        ],
        early_in_band_exit_available_tightening_paths=runtime_setup_state[
            "early_in_band_exit_available_tightening_paths"
        ],
        early_in_band_exit_reason=runtime_setup_state["early_in_band_exit_reason"],
        trace_callback=runtime_setup_state["trace_callback"],
    )


def _dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(
    *,
    runtime_setup_state: dict,
    max_steps: int,
    debug_enabled: bool,
) -> dict:
    return _run_one_click_solver_iteration_loop_coordinator(
        max_steps=max_steps,
        debug_enabled=debug_enabled,
        trace_run_id=runtime_setup_state["rid"],
        trace_callback=runtime_setup_state["trace_callback"],
        working=runtime_setup_state["working"],
        mode_config=runtime_setup_state["mode_config"],
        target_band_domain=runtime_setup_state["target_band_domain"],
        target_domains_for_band=runtime_setup_state["target_domains_for_band"],
        step_trace=runtime_setup_state["step_trace"],
        initial_snapshot=runtime_setup_state["initial_snapshot"],
        winning_label=runtime_setup_state["winning_label"],
        winning_action_type=runtime_setup_state["winning_action_type"],
        tightening_step_count=runtime_setup_state["tightening_step_count"],
        max_tightening_steps=runtime_setup_state["max_tightening_steps"],
        tightening_budget_extensions_used=runtime_setup_state[
            "tightening_budget_extensions_used"
        ],
        tightening_budget_extension_cap=runtime_setup_state[
            "tightening_budget_extension_cap"
        ],
        candidate_family_depth_reached=runtime_setup_state[
            "candidate_family_depth_reached"
        ],
        stop_reason=runtime_setup_state["stop_reason"],
        status=runtime_setup_state["status"],
        final_distance_to_band=runtime_setup_state["final_distance_to_band"],
        final_governing_domain=runtime_setup_state["final_governing_domain"],
        shear_governing_mode_active=runtime_setup_state[
            "shear_governing_mode_active"
        ],
        shear_severity_band=runtime_setup_state["shear_severity_band"],
        shear_candidate_family_order=runtime_setup_state[
            "shear_candidate_family_order"
        ],
        spacing_candidates_considered=runtime_setup_state[
            "spacing_candidates_considered"
        ],
        leg_candidates_considered=runtime_setup_state["leg_candidates_considered"],
        dia_candidates_considered=runtime_setup_state["dia_candidates_considered"],
        geometry_candidates_considered_for_shear=runtime_setup_state[
            "geometry_candidates_considered_for_shear"
        ],
        combined_candidates_considered_for_shear=runtime_setup_state[
            "combined_candidates_considered_for_shear"
        ],
        web_crushing_penalty_applied=runtime_setup_state[
            "web_crushing_penalty_applied"
        ],
        rejected_as_spacing_too_weak=runtime_setup_state[
            "rejected_as_spacing_too_weak"
        ],
        rejected_as_web_crushing_marginal=runtime_setup_state[
            "rejected_as_web_crushing_marginal"
        ],
        rejected_as_impractical_shear_layout=runtime_setup_state[
            "rejected_as_impractical_shear_layout"
        ],
        final_resolved_shear_util=runtime_setup_state["final_resolved_shear_util"],
        final_resolved_web_util=runtime_setup_state["final_resolved_web_util"],
        step_committable_eval_trace=runtime_setup_state[
            "step_committable_eval_trace"
        ],
        no_actionable_after_full_tightening_search=runtime_setup_state[
            "no_actionable_after_full_tightening_search"
        ],
        rejected_as_non_governing_cleanup=runtime_setup_state[
            "rejected_as_non_governing_cleanup"
        ],
        rejected_as_non_governing_shear_strengthening=runtime_setup_state[
            "rejected_as_non_governing_shear_strengthening"
        ],
        shear_remove_links_candidate_seen=runtime_setup_state[
            "shear_remove_links_candidate_seen"
        ],
        shear_remove_links_candidate_truth_ok=runtime_setup_state[
            "shear_remove_links_candidate_truth_ok"
        ],
        shear_remove_links_candidate_dropped_reason=runtime_setup_state[
            "shear_remove_links_candidate_dropped_reason"
        ],
        shear_remove_links_candidate_materiality=runtime_setup_state[
            "shear_remove_links_candidate_materiality"
        ],
        t_lo=runtime_setup_state["t_lo"],
        t_hi=runtime_setup_state["t_hi"],
        seen_sigs=runtime_setup_state["seen_sigs"],
    )


def _solve_one_click_to_target(
    state: dict,
    *,
    max_steps: int = 6,
    debug_enabled: bool = False,
    trace_run_id: str | None = None,
    trace_source: str = "one_click_solve",
    _rescue_enabled: bool = True,
    _rescue_attempted_seed_keys: tuple[str, ...] = (),
) -> dict:
    """
    Pure iterative one-click solver: temp state only, no session writes / reruns.
    Uses ``_compute_design_guidance_items(..., request_kind=\"design_guide\")`` only.
    """
    runtime_setup_state = _prepare_one_click_solver_runtime_setup_state_coordinator(
        state=state,
        max_steps=max_steps,
        trace_run_id=trace_run_id,
        trace_source=trace_source,
        rescue_attempted_seed_keys=_rescue_attempted_seed_keys,
    )
    if runtime_setup_state["should_return"]:
        return runtime_setup_state["return_result"]

    iteration_loop_state = (
        _dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(
            runtime_setup_state=runtime_setup_state,
            max_steps=max_steps,
            debug_enabled=debug_enabled,
        )
    )
    return _finish_one_click_solver_iteration_loop_result_coordinator(
        runtime_setup_state=runtime_setup_state,
        iteration_loop_state=iteration_loop_state,
        max_steps=max_steps,
        debug_enabled=debug_enabled,
        trace_source=trace_source,
        rescue_enabled=_rescue_enabled,
    )


def _trace_run_skipped_return_coordinator(
    skip_reason: str,
    *,
    trace_run_id: str,
    tracer_path: str,
    trace_src: str,
    entry_source_norm: str,
    trigger_fingerprint: tuple | None,
    return_with_latch_clear,
) -> dict:
    idle_code = {
        "compute_in_progress": "deferred_compute_in_progress",
        "solver_running": "deferred_solver_running",
        "should_run_auto_design_false": "idle_should_run_false",
    }.get(skip_reason, skip_reason)
    dbg_snap = _auto_design_invoke_debug_snapshot()
    solver_running_bypassed = bool(
        st.session_state.get("_solver_running", False)
        and entry_source_norm == "inputs_handle_auto_design"
        and str(st.session_state.get("auto_design_latch_owner") or "").strip() == "handle_auto_design"
    )
    try:
        st.session_state["auto_design_idle_reason"] = idle_code
        st.session_state["_auto_design_idle_reason"] = idle_code
        st.session_state["auto_design_invoke_consumed"] = False
    except Exception:
        pass
    print(
        "DG TRACE SKIP\n"
        f"skip_reason={skip_reason}\n"
        f"auto_design_idle_reason={idle_code}\n"
        f"trace_run_id={trace_run_id}\n"
        f"tracer_path={tracer_path}\n",
        file=sys.stderr,
        end="",
        flush=True,
    )
    _append_design_guide_trace(
        "run_skipped",
        {
            "skip_reason": skip_reason,
            "auto_design_idle_reason": idle_code,
            "tracer_path": tracer_path,
            "trace_run_id": trace_run_id,
            "run_one_click_entry_source": entry_source_norm,
            "auto_design_latch_owner": str(st.session_state.get("auto_design_latch_owner") or "") or None,
            "run_one_click_solver_running_bypassed": solver_running_bypassed,
            "action_source_summary": _tracer_one_click_action_source_summary(trigger_fingerprint),
            **dbg_snap,
        },
        run_id=trace_run_id,
        source=trace_src,
    )
    common = {
        "trace_run_id": trace_run_id,
        "design_guide_tracer_path": tracer_path,
        "tracer_skip_reason": skip_reason,
        "tracer_entry_reached": True,
        "auto_design_idle_reason": idle_code,
        "auto_design_invoke_consumed": False,
        "run_one_click_entry_source": entry_source_norm,
        "auto_design_latch_owner": str(st.session_state.get("auto_design_latch_owner") or "") or None,
        "run_one_click_solver_running_bypassed": solver_running_bypassed,
        **dbg_snap,
    }
    if skip_reason == "solver_running":
        return return_with_latch_clear(
            "run_one_click_auto_design:deferred_solver_running",
            {
                "status": "deferred",
                "steps": ["Auto-design deferred while solver is running."],
                **common,
            },
        )
    if skip_reason == "compute_in_progress":
        return return_with_latch_clear(
            "run_one_click_auto_design:deferred_compute_in_progress",
            {
                "status": "deferred",
                "steps": ["Auto-design deferred while compute is running."],
                **common,
            },
        )
    return return_with_latch_clear(
        "run_one_click_auto_design:idle_should_run_false",
        {
            "status": "idle",
            "steps": [],
            **common,
        },
    )


def _trace_run_end_coordinator(
    overall_result_status: str,
    *,
    commit_audit: dict | None,
    init_u,
    fin_u,
    commit_rejected: bool,
    commit_reject_reason: str | None,
    dbg: dict,
    trace_run_id: str,
    action_sig: str,
    goal,
    stop_reason: str | None,
    win_l: str | None,
    final_updates: dict,
    trace_src: str,
) -> None:
    match_ok = None
    live_worst = None
    live_statuses = None
    if isinstance(commit_audit, dict):
        match_ok = bool(commit_audit.get("post_commit_matches_intended_updates"))
        live_worst = commit_audit.get("post_commit_live_worst_util")
        live_statuses = (commit_audit or {}).get("post_commit_live_statuses")
    if live_worst is None:
        try:
            live_overview = _collect_design_overview(_guidance_state_snapshot(_shared_state_snapshot()))
            live_worst = live_overview.get("governing_util", live_overview.get("worst_util"))
            live_statuses = dict(live_overview.get("statuses") or {})
        except Exception:
            live_worst = None
            live_statuses = None
    try:
        iwu = float(init_u) if init_u is not None else None
    except (TypeError, ValueError):
        iwu = None
    try:
        fwu = float(fin_u) if fin_u is not None else None
    except (TypeError, ValueError):
        fwu = None
    _append_design_guide_trace(
        "run_end",
        {
            "overall_result_status": overall_result_status,
            "stop_reason": stop_reason,
            "final_live_worst_util": live_worst if live_worst is not None else fwu,
            "commit_matched_intended_updates": match_ok,
            "one_click_commit_rejected": bool(commit_rejected),
            "one_click_commit_reject_reason": commit_reject_reason,
            "one_click_commit_rolled_back": bool(commit_rejected),
            "pre_commit_worst_util": dbg.get("pre_commit_worst_util"),
            "post_commit_live_worst_util": (
                (commit_audit or {}).get("post_commit_live_worst_util")
                if isinstance(commit_audit, dict)
                else None
            ),
            "post_commit_live_statuses": live_statuses,
            "restored_after_failed_commit": bool(commit_rejected),
            "compare": _design_guide_trace_compare_meta(
                run_id=trace_run_id,
                action_signature=action_sig,
                goal=str(goal) if goal is not None else None,
                starting_worst_util=iwu,
                ending_worst_util=fwu,
                stop_reason=stop_reason or None,
                winner_label=str(win_l) if win_l else None,
                final_updates=final_updates,
            ),
        },
        run_id=trace_run_id,
        source=trace_src,
    )


def _result_recommendation_envelope_coordinator(
    *,
    status: str,
    dbg: dict,
    commit_audit: dict | None,
    updates: dict | None = None,
    blocked_reason: str | None = None,
    commit_eligible: bool | None = None,
) -> dict:
    return _build_recommendation_envelope(
        updates=updates,
        source="one_click_auto_design",
        status=status,
        blocked_reason=blocked_reason,
        commit_eligible=commit_eligible,
        audit=commit_audit if isinstance(commit_audit, dict) else None,
        required_domains=(
            dbg.get("final_target_domains_eval")
            or dbg.get("target_domains_for_band")
            or dbg.get("target_domain_for_band")
            or []
        ),
    )


def _attach_no_action_visibility_coordinator(
    *,
    stop_reason: str | None,
    dbg: dict,
) -> dict[str, str | None]:
    uv = _one_click_build_user_visible_no_action_fields(stop_reason, dbg)
    dbg["user_visible_no_action_reason"] = uv["user_visible_no_action_reason"]
    dbg["user_visible_rejection_summary"] = uv["user_visible_rejection_summary"]
    return uv


def _build_one_click_base_steps_coordinator(
    *,
    stop_reason: str | None,
    step_count,
    init_u,
    fin_u,
    reached,
    dbg: dict,
    win_l: str | None,
    solver_final_updates: dict | None,
    commit_blocked_reason: str | None,
    commit_rejected: bool,
) -> list[str]:
    base_steps = [
        f"One-click solve: stop={stop_reason}, steps={step_count}, util {init_u} \u2192 {fin_u}, band_reached={reached}.",
    ]
    if stop_reason in ("no_actionable_candidates_after_full_tightening_search", "non_material_remaining_candidates"):
        gdom = str(dbg.get("governing_domain") or "governing")
        base_steps.append(f"No further practical {gdom}-tightening candidate found.")
    if bool(dbg.get("shear_governing_mode_active")) and str(win_l or "").strip().lower() == "combined shear + geometry tightening":
        base_steps.append("Direct link-only tightening was insufficient; combined geometry + shear reinforcement was selected.")
    if solver_final_updates:
        if commit_blocked_reason:
            base_steps.append(
                "No single one-click update currently covers all failing checks; no changes were applied.",
            )
        elif commit_rejected:
            base_steps.append(
                "Live post-commit validation failed; the candidate was rolled back and no changes were kept.",
            )
        else:
            base_steps.append("Updates committed to the beam (single batch).")
    else:
        base_steps.append("No shared-state changes applied.")
    return base_steps


def _attach_normalized_shear_truth_debug_coordinator(target: dict | None, bundle: dict | None) -> None:
    if not isinstance(target, dict):
        return
    normalized = dict(bundle or {})
    target["final_shear_truth_normalized_source"] = st.session_state.get("_final_shear_truth_normalized_source")
    target["final_shear_truth_normalized_latest"] = dict(
        st.session_state.get("_final_shear_truth_normalized_latest") or normalized,
    )
    target["final_shear_truth_bundle_complete"] = normalized.get("final_shear_truth_bundle_complete")
    target["shear_truth_status"] = normalized.get("shear_truth_status")
    target["final_shear_truth_resolved"] = normalized.get("final_shear_truth_resolved")
    target["final_shear_truth_failure_reason"] = normalized.get("final_shear_truth_failure_reason")
    target["published_result_spacing_mm"] = normalized.get("published_result_spacing_mm")
    target["published_result_spacing_meaning"] = normalized.get("published_result_spacing_meaning")


def _publish_current_normalized_shear_truth_coordinator(source: str, target: dict | None = None) -> dict | None:
    try:
        bundle = publish_normalized_final_shear_truth_to_session(source=source)
    except Exception:
        return None
    _attach_normalized_shear_truth_debug_coordinator(target, bundle)
    return bundle


def _return_with_latch_clear_coordinator(
    *,
    reason: str,
    payload: dict,
    auto_design_stale_latch_cleared_at_entry: bool,
    auto_design_stale_latch_clear_reason: str,
) -> dict:
    clear_payload = _clear_auto_design_runtime_latches(reason)
    if isinstance(payload, dict):
        payload["auto_design_latch_clear"] = dict(clear_payload)
        payload["auto_design_stale_latch_cleared_at_entry"] = bool(
            auto_design_stale_latch_cleared_at_entry
        )
        payload["auto_design_stale_latch_clear_reason"] = (
            auto_design_stale_latch_clear_reason
        )
    return payload


def _resolve_auto_design_stale_latch_entry_state_coordinator(
    *,
    entry_source_norm: str,
) -> dict:
    request_source = str(
        st.session_state.get("auto_design_request_source")
        or st.session_state.get(AUTO_DESIGN_REQUEST_SOURCE_KEY)
        or entry_source_norm
        or ""
    ).strip()
    auto_design_stale_latch_cleared_at_entry = False
    auto_design_stale_latch_clear_reason = ""
    if (
        st.session_state.get("_solver_running")
        and not bool(st.session_state.get("_compute_in_progress", False))
    ):
        stale_owner = str(st.session_state.get("auto_design_latch_owner") or "").strip()
        direct_request = request_source in {
            "primary_apply_button",
            "run_one_click_auto_design",
            "inputs_handle_auto_design",
        }
        if direct_request and not stale_owner:
            clear_payload = _clear_auto_design_runtime_latches(
                "run_one_click_auto_design:stale_solver_running_missing_owner"
            )
            auto_design_stale_latch_cleared_at_entry = True
            auto_design_stale_latch_clear_reason = str(clear_payload.get("reason") or "")
    st.session_state["auto_design_stale_latch_cleared_at_entry"] = bool(
        auto_design_stale_latch_cleared_at_entry
    )
    st.session_state["auto_design_stale_latch_clear_reason"] = (
        auto_design_stale_latch_clear_reason
    )
    return {
        "request_source": request_source,
        "auto_design_stale_latch_cleared_at_entry": bool(auto_design_stale_latch_cleared_at_entry),
        "auto_design_stale_latch_clear_reason": auto_design_stale_latch_clear_reason,
    }


def _resolve_auto_design_run_skip_gate_coordinator(
    *,
    entry_source_norm: str,
) -> dict:
    if st.session_state.get("_compute_in_progress"):
        return {
            "skip_reason": "compute_in_progress",
            "solver_running_bypassed": False,
        }
    if not _should_run_auto_design():
        return {
            "skip_reason": "should_run_auto_design_false",
            "solver_running_bypassed": False,
        }
    solver_running_bypassed = bool(
        st.session_state.get("_solver_running", False)
        and entry_source_norm == "inputs_handle_auto_design"
        and str(st.session_state.get("auto_design_latch_owner") or "").strip() == "handle_auto_design"
    )
    if st.session_state.get("_solver_running") and not solver_running_bypassed:
        return {
            "skip_reason": "solver_running",
            "solver_running_bypassed": bool(solver_running_bypassed),
        }
    return {
        "skip_reason": None,
        "solver_running_bypassed": bool(solver_running_bypassed),
    }


def _prepare_one_click_auto_design_run_state_coordinator(
    *,
    trigger_fingerprint: tuple | None,
    trace_run_id: str,
    tracer_path: str,
    trace_src: str,
    entry_source_norm: str,
    solver_running_bypassed: bool,
) -> dict:
    _consume_auto_design_invoke_after_solver_entry_confirmed()
    st.session_state.pop("_one_click_run_feedback", None)
    one_click_run_feedback_cleared_at_entry = True

    current_state_raw = _guidance_state_snapshot(_shared_state_snapshot())
    raw_coherence = _design_state_coherence_check(current_state_raw)
    current_state = _build_canonical_design_state_pack(current_state_raw)
    canonical_coherence = _design_state_coherence_check(current_state)
    canonical_pack_valid = _canonical_pack_is_valid(current_state)
    canonical_pack_error = str(current_state.get("canonical_pack_error") or "").strip() or None
    canonical_pack_error_stage = str(current_state.get("canonical_pack_error_stage") or "").strip() or None
    goal = _design_optimisation_goal(current_state)
    action_sig = str(trigger_fingerprint) if trigger_fingerprint is not None else "default_one_click"
    pack_invalid_block = (not canonical_pack_valid) or bool(canonical_coherence.get("coherence_should_block"))

    pre_run_overview = None
    pe0 = None
    if not pack_invalid_block:
        try:
            pe0 = evaluate_candidate_full(
                copy.deepcopy(current_state),
                source="one_click_trace_run_start",
                label="TraceSeed",
                action_type="one_click",
                updates={},
            )
            if isinstance(pe0, dict):
                pre_run_overview = _trace_compact_overview_dict(pe0.get("overview"))
        except Exception:
            pre_run_overview = None
            pe0 = None

    try:
        swu = (
            float(pre_run_overview["worst_util"])
            if isinstance(pre_run_overview, dict) and pre_run_overview.get("worst_util") is not None
            else None
        )
    except (TypeError, ValueError):
        swu = None

    print(
        "DG TRACE RUN_START\n"
        f"trace_run_id={trace_run_id}\n"
        f"tracer_path={tracer_path}\n",
        file=sys.stderr,
        end="",
        flush=True,
    )
    pe0_overview = pe0.get("overview") if isinstance(pe0, dict) else None
    _append_design_guide_trace(
        "run_start",
        {
            "action_source": "trigger_fingerprint"
            if trigger_fingerprint is not None
            else "inputs_handle_auto_design",
            "resolved_action_signature": action_sig,
            "optimisation_goal": goal,
            "shared_subset": _trace_compact_shared_geom_reo(current_state),
            "run_one_click_entry_source": entry_source_norm,
            "auto_design_latch_owner": str(st.session_state.get("auto_design_latch_owner") or "") or None,
            "run_one_click_solver_running_bypassed": bool(solver_running_bypassed),
            "stage3_shear_truth_at_run_start": _stage3_final_published_shear_truth_bundle(current_state),
            "stage3_remaining_issue_class": _stage3_remaining_issue_class_from_overview_state(
                current_state,
                pe0_overview if isinstance(pe0_overview, dict) else None,
            ),
            "pre_run_overview": pre_run_overview,
            "compare": _design_guide_trace_compare_meta(
                run_id=trace_run_id,
                action_signature=action_sig,
                goal=str(goal) if goal is not None else None,
                starting_worst_util=swu,
                ending_worst_util=None,
                stop_reason=None,
                winner_label=None,
                final_updates={},
            ),
            **_coherence_debug_fields(canonical_coherence),
            "state_coherence_ok_before_rebuild": bool(raw_coherence.get("coherence_ok")),
            "state_coherence_issues_before_rebuild": list(raw_coherence.get("issues") or []),
            "coherence_blocking_issues_before_rebuild": list(raw_coherence.get("coherence_blocking_issues") or []),
            "coherence_nonblocking_issues_before_rebuild": list(raw_coherence.get("coherence_nonblocking_issues") or []),
            "coherence_should_block_before_rebuild": bool(raw_coherence.get("coherence_should_block")),
            "state_coherence_warning_before_rebuild": bool(raw_coherence.get("state_coherence_warning")),
            "state_coherence_warning_issues_before_rebuild": list(raw_coherence.get("state_coherence_warning_issues") or []),
            "canonical_pack_built": bool(current_state.get("canonical_pack_built")),
            "canonical_pack_valid": canonical_pack_valid,
            "canonical_pack_source": current_state.get("canonical_pack_source"),
            "canonical_pack_error": canonical_pack_error,
            "canonical_pack_error_stage": canonical_pack_error_stage,
            "solver_blocked_by_incoherent_state": pack_invalid_block,
        },
        run_id=trace_run_id,
        source=trace_src,
    )
    return {
        "one_click_run_feedback_cleared_at_entry": bool(one_click_run_feedback_cleared_at_entry),
        "raw_coherence": raw_coherence,
        "current_state": current_state,
        "canonical_coherence": canonical_coherence,
        "canonical_pack_valid": bool(canonical_pack_valid),
        "canonical_pack_error": canonical_pack_error,
        "canonical_pack_error_stage": canonical_pack_error_stage,
        "goal": goal,
        "action_sig": action_sig,
        "pack_invalid_block": bool(pack_invalid_block),
    }


def _build_auto_design_blocked_incoherent_common_debug_fields_coordinator(
    *,
    current_state: dict,
    canonical_coherence: dict,
    canonical_pack_valid: bool,
    canonical_pack_error,
    canonical_pack_error_stage,
    entry_source_norm: str,
    solver_running_bypassed: bool,
) -> dict:
    return {
        **_coherence_debug_fields(canonical_coherence),
        "canonical_pack_built": bool(current_state.get("canonical_pack_built")),
        "canonical_pack_valid": canonical_pack_valid,
        "canonical_pack_source": current_state.get("canonical_pack_source"),
        "canonical_pack_error": canonical_pack_error,
        "canonical_pack_error_stage": canonical_pack_error_stage,
        "run_one_click_entry_source": entry_source_norm,
        "auto_design_latch_owner": str(st.session_state.get("auto_design_latch_owner") or "") or None,
        "run_one_click_solver_running_bypassed": bool(solver_running_bypassed),
        "solver_blocked_by_incoherent_state": True,
    }


def _attach_auto_design_blocked_incoherent_fail_keys_coordinator(
    *,
    blocked_dbg: dict,
    current_state: dict,
) -> None:
    try:
        blocked_overview = _collect_design_overview(current_state)
        blocked_dbg["current_fail_keys_source"] = "canonical_overview"
        blocked_dbg["current_fail_fingerprint"] = dict(_current_design_guide_fail_fingerprint(blocked_overview))
        blocked_statuses = dict((blocked_overview.get("statuses") or {}))
        blocked_dbg["current_fail_keys"] = sorted(
            str(k or "").strip().lower()
            for k, v in blocked_statuses.items()
            if v == BEAM_STATUS_FAIL or str(v or "").strip().upper() == "FAIL"
        )
    except Exception:
        blocked_dbg["current_fail_keys_source"] = "canonical_overview"
        blocked_dbg.setdefault("current_fail_fingerprint", {})
        blocked_dbg.setdefault("current_fail_keys", [])


def _apply_auto_design_blocked_incoherent_user_visible_fields_coordinator(
    *,
    blocked_stop_reason: str,
    blocked_dbg: dict,
    blocked_dbg_inner: dict,
) -> dict:
    uv_blocked = _one_click_build_user_visible_no_action_fields(blocked_stop_reason, blocked_dbg)
    if blocked_stop_reason == "no_bars_resolved":
        uv_blocked["user_visible_no_action_reason"] = "Add longitudinal reinforcement before running auto-design."
    blocked_dbg.update(uv_blocked)
    for uv_key in ("user_visible_no_action_reason", "user_visible_rejection_summary"):
        if uv_key in uv_blocked:
            blocked_dbg_inner[uv_key] = uv_blocked[uv_key]
    return uv_blocked


def _handle_auto_design_blocked_incoherent_state_coordinator(
    *,
    current_state: dict,
    raw_coherence: dict,
    canonical_coherence: dict,
    canonical_pack_valid: bool,
    canonical_pack_error,
    canonical_pack_error_stage,
    trace_run_id: str,
    tracer_path: str,
    trace_src: str,
    entry_source_norm: str,
    solver_running_bypassed: bool,
    one_click_run_feedback_cleared_at_entry: bool,
    return_with_latch_clear,
) -> dict:
    blocked_stop_reason = canonical_pack_error or str(
        (canonical_coherence.get("coherence_blocking_issues") or ["state_incoherent_after_rebuild"])[0]
    )
    trace_blocked_fields = _build_auto_design_blocked_incoherent_common_debug_fields_coordinator(
        current_state=current_state,
        canonical_coherence=canonical_coherence,
        canonical_pack_valid=canonical_pack_valid,
        canonical_pack_error=canonical_pack_error,
        canonical_pack_error_stage=canonical_pack_error_stage,
        entry_source_norm=entry_source_norm,
        solver_running_bypassed=solver_running_bypassed,
    )
    _append_design_guide_trace(
        "run_end",
        {
            "overall_result_status": "blocked",
            "stop_reason": blocked_stop_reason,
            "final_live_worst_util": None,
            "commit_matched_intended_updates": None,
            **trace_blocked_fields,
            "state_coherence_ok_before_rebuild": bool(raw_coherence.get("coherence_ok")),
            "state_coherence_issues_before_rebuild": list(raw_coherence.get("issues") or []),
            "coherence_blocking_issues_before_rebuild": list(raw_coherence.get("coherence_blocking_issues") or []),
            "coherence_nonblocking_issues_before_rebuild": list(raw_coherence.get("coherence_nonblocking_issues") or []),
            "coherence_should_block_before_rebuild": bool(raw_coherence.get("coherence_should_block")),
            "state_coherence_warning_before_rebuild": bool(raw_coherence.get("state_coherence_warning")),
            "state_coherence_warning_issues_before_rebuild": list(raw_coherence.get("state_coherence_warning_issues") or []),
        },
        run_id=trace_run_id,
        source=trace_src,
    )
    blocked_dbg_inner = _build_auto_design_blocked_incoherent_common_debug_fields_coordinator(
        current_state=current_state,
        canonical_coherence=canonical_coherence,
        canonical_pack_valid=canonical_pack_valid,
        canonical_pack_error=canonical_pack_error,
        canonical_pack_error_stage=canonical_pack_error_stage,
        entry_source_norm=entry_source_norm,
        solver_running_bypassed=solver_running_bypassed,
    )
    blocked_dbg_fields = _build_auto_design_blocked_incoherent_common_debug_fields_coordinator(
        current_state=current_state,
        canonical_coherence=canonical_coherence,
        canonical_pack_valid=canonical_pack_valid,
        canonical_pack_error=canonical_pack_error,
        canonical_pack_error_stage=canonical_pack_error_stage,
        entry_source_norm=entry_source_norm,
        solver_running_bypassed=solver_running_bypassed,
    )
    blocked_dbg = {
        "trace_run_id": trace_run_id,
        "design_guide_tracer_path": tracer_path,
        "tracer_skip_reason": None,
        "tracer_entry_reached": True,
        **blocked_dbg_fields,
    }
    uv_blocked = _apply_auto_design_blocked_incoherent_user_visible_fields_coordinator(
        blocked_stop_reason=blocked_stop_reason,
        blocked_dbg=blocked_dbg,
        blocked_dbg_inner=blocked_dbg_inner,
    )
    blocked_dbg["one_click_run_feedback_cleared_at_entry"] = bool(one_click_run_feedback_cleared_at_entry)
    normalized_blocked = _publish_current_normalized_shear_truth_coordinator(
        "run_one_click_auto_design:post_current_eval:blocked",
        blocked_dbg,
    )
    _attach_normalized_shear_truth_debug_coordinator(blocked_dbg_inner, normalized_blocked)
    _attach_auto_design_blocked_incoherent_fail_keys_coordinator(
        blocked_dbg=blocked_dbg,
        current_state=current_state,
    )
    _set_one_click_run_feedback(
        status="blocked",
        reason=blocked_stop_reason,
        extra_payload={
            "current_fail_fingerprint": dict(blocked_dbg.get("current_fail_fingerprint") or {}),
            "current_fail_keys": list(blocked_dbg.get("current_fail_keys") or []),
            "current_fail_keys_source": "canonical_overview",
        },
        debug_target=blocked_dbg,
    )
    return return_with_latch_clear("run_one_click_auto_design:blocked_incoherent_state", {
        "status": "blocked",
        "stop_reason": blocked_stop_reason,
        "blocked_state_class": "hard_invalid",
        "steps": ["One-click solve blocked: add longitudinal reinforcement before running auto-design."],
        "recommendation": None,
        "recommendation_result": None,
        "auto_design_solver_recommendation": None,
        "one_click_solve": {
            "status": "blocked",
            "stop_reason": blocked_stop_reason,
            "blocked_state_class": "hard_invalid",
            "one_click_solver_debug": blocked_dbg_inner,
        },
        "one_click_solver_debug": blocked_dbg,
        "one_click_commit_audit": None,
        "trace_run_id": trace_run_id,
        "design_guide_tracer_path": tracer_path,
        "tracer_skip_reason": None,
        "tracer_entry_reached": True,
        **uv_blocked,
    })


def _build_auto_design_post_solver_debug_coordinator(
    *,
    solve: dict,
    trace_run_id: str,
    tracer_path: str,
    raw_coherence: dict,
    current_state: dict,
    canonical_coherence: dict,
    canonical_pack_valid: bool,
    canonical_pack_error,
    canonical_pack_error_stage,
    entry_source_norm: str,
    solver_running_bypassed: bool,
    one_click_run_feedback_cleared_at_entry: bool,
) -> dict:
    dbg = dict(solve.get("one_click_solver_debug") or {})
    dbg["trace_run_id"] = trace_run_id
    dbg["design_guide_tracer_path"] = tracer_path
    dbg["tracer_skip_reason"] = None
    dbg["tracer_entry_reached"] = True
    dbg.update(_coherence_debug_fields(canonical_coherence))
    dbg["state_coherence_ok_before_rebuild"] = bool(raw_coherence.get("coherence_ok"))
    dbg["state_coherence_issues_before_rebuild"] = list(raw_coherence.get("issues") or [])
    dbg["coherence_blocking_issues_before_rebuild"] = list(raw_coherence.get("coherence_blocking_issues") or [])
    dbg["coherence_nonblocking_issues_before_rebuild"] = list(raw_coherence.get("coherence_nonblocking_issues") or [])
    dbg["coherence_should_block_before_rebuild"] = bool(raw_coherence.get("coherence_should_block"))
    dbg["state_coherence_warning_before_rebuild"] = bool(raw_coherence.get("state_coherence_warning"))
    dbg["state_coherence_warning_issues_before_rebuild"] = list(raw_coherence.get("state_coherence_warning_issues") or [])
    dbg["canonical_pack_built"] = bool(current_state.get("canonical_pack_built"))
    dbg["canonical_pack_valid"] = canonical_pack_valid
    dbg["canonical_pack_source"] = current_state.get("canonical_pack_source")
    dbg["canonical_pack_error"] = canonical_pack_error
    dbg["canonical_pack_error_stage"] = canonical_pack_error_stage
    dbg["run_one_click_entry_source"] = entry_source_norm
    dbg["auto_design_latch_owner"] = str(st.session_state.get("auto_design_latch_owner") or "") or None
    dbg["run_one_click_solver_running_bypassed"] = bool(solver_running_bypassed)
    dbg["solver_blocked_by_incoherent_state"] = False
    dbg["auto_design_invoke_consumed"] = bool(st.session_state.get("auto_design_invoke_consumed"))
    dbg["auto_design_idle_reason"] = None
    dbg.update(_auto_design_invoke_debug_snapshot())
    dbg["one_click_commit_blocked_reason"] = None
    dbg["one_click_run_feedback_status"] = None
    dbg["one_click_run_feedback_reason"] = None
    dbg["one_click_final_candidate_valid_for_commit"] = None
    dbg["one_click_final_candidate_valid_reason"] = "missing_candidate"
    dbg["one_click_final_candidate_fail_keys"] = []
    dbg["one_click_final_candidate_remaining_fail_keys"] = []
    dbg["one_click_run_feedback_cleared_at_entry"] = bool(one_click_run_feedback_cleared_at_entry)
    dbg["one_click_blocked_feedback_fail_fingerprint"] = {}
    dbg["final_no_links_candidate_committed"] = False

    try:
        current_overview = _collect_design_overview(current_state)
        dbg["current_fail_keys_source"] = "canonical_overview"
        dbg["current_fail_fingerprint"] = dict(_current_design_guide_fail_fingerprint(current_overview))
        current_statuses = dict((current_overview.get("statuses") or {}))
        dbg["current_fail_keys"] = sorted(
            str(k or "").strip().lower()
            for k, v in current_statuses.items()
            if v == BEAM_STATUS_FAIL or str(v or "").strip().upper() == "FAIL"
        )
    except Exception:
        dbg["current_fail_keys_source"] = "canonical_overview"
        dbg.setdefault("current_fail_fingerprint", {})
        dbg.setdefault("current_fail_keys", [])
    return dbg


def _prepare_auto_design_final_candidate_commit_context_coordinator(
    *,
    solve: dict,
    current_state: dict,
    final_updates: dict,
    win_l,
    win_at,
    dbg: dict,
) -> dict:
    current_overview = _collect_design_overview(current_state)
    current_fail_fingerprint = _current_design_guide_fail_fingerprint(current_overview)
    dbg["current_fail_keys_source"] = "canonical_overview"
    dbg["current_fail_fingerprint"] = dict(current_fail_fingerprint)
    current_statuses = dict((current_overview.get("statuses") or {}))
    dbg["current_fail_keys"] = sorted(
        str(k or "").strip().lower()
        for k, v in current_statuses.items()
        if v == BEAM_STATUS_FAIL or str(v or "").strip().upper() == "FAIL"
    )
    dbg["shear_fail_status_used"] = str(
        ((current_overview.get("statuses") or {}).get("shear") or "")
    ).strip()
    dbg["shear_fail_util_used"] = _parse_util_value(
        ((current_overview.get("utils") or {}).get("shear"))
    )
    dbg["current_shear_status"] = dbg["shear_fail_status_used"]
    dbg["current_shear_util"] = dbg["shear_fail_util_used"]
    dbg["current_shear_selection_origin"] = str(
        current_overview.get("overview_shear_selection_origin") or ""
    ).strip()
    dbg["one_click_blocked_feedback_fail_fingerprint"] = dict(current_fail_fingerprint)
    try:
        # Prefer the solver's packed post-step state so pre-commit preview matches
        # one_click_solve (diff-only apply to current_state can miss canonical fields and
        # falsely clear bending FAIL that the solver already saw on the winner path).
        solver_final_preview = solve.get("final_state_preview")
        if isinstance(solver_final_preview, dict) and solver_final_preview:
            candidate_for_commit = _evaluate_auto_design_candidate(
                _build_canonical_design_state_pack(copy.deepcopy(solver_final_preview)),
                updates=None,
                source="one_click_commit_full_coverage_gate",
                label=str(win_l or "Apply one-click design"),
                action_type=str(win_at or "") or None,
            )
        else:
            candidate_for_commit = _evaluate_auto_design_candidate(
                current_state,
                updates=final_updates,
                source="one_click_commit_full_coverage_gate",
                label=str(win_l or "Apply one-click design"),
                action_type="apply_resolved_candidate",
            )
    except Exception:
        candidate_for_commit = None
    candidate_commit_coverage = _candidate_failure_coverage_summary(current_state, candidate_for_commit or {})
    if isinstance(candidate_for_commit, dict):
        candidate_for_commit["failure_coverage"] = dict(candidate_commit_coverage)
        candidate_for_commit["covers_all_current_failures"] = bool(
            candidate_commit_coverage.get("covers_all_current_failures"),
        )
        candidate_for_commit["covered_fail_keys"] = list(
            candidate_commit_coverage.get("covered_fail_keys") or [],
        )
        candidate_for_commit["remaining_fail_keys"] = list(
            candidate_commit_coverage.get("remaining_fail_keys") or [],
        )
    final_candidate_valid_for_commit, final_candidate_commit_meta = _candidate_is_valid_primary_one_click(
        candidate_for_commit,
        current_overview,
    )
    dbg["one_click_final_candidate_valid_for_commit"] = bool(final_candidate_valid_for_commit)
    dbg["one_click_final_candidate_valid_reason"] = str(
        final_candidate_commit_meta.get("reason") or "missing_candidate",
    )
    dbg["one_click_final_candidate_fail_keys"] = list(final_candidate_commit_meta.get("fail_keys") or [])
    dbg["one_click_final_candidate_remaining_fail_keys"] = list(
        final_candidate_commit_meta.get("remaining_fail_keys") or [],
    )
    dbg["candidate_covered_fail_keys"] = list(final_candidate_commit_meta.get("covered_fail_keys") or [])
    dbg["candidate_remaining_fail_keys"] = list(
        final_candidate_commit_meta.get("remaining_fail_keys") or [],
    )
    return {
        "dbg": dbg,
        "current_overview": current_overview,
        "candidate_for_commit": candidate_for_commit,
        "final_candidate_valid_for_commit": bool(final_candidate_valid_for_commit),
        "final_candidate_commit_meta": final_candidate_commit_meta,
    }


def _resolve_auto_design_partial_commit_allowance_coordinator(
    *,
    solve: dict,
    current_state: dict,
    current_overview: dict,
    candidate_for_commit,
    final_candidate_commit_meta: dict,
    solver_final_updates: dict,
    dbg: dict,
) -> dict:
    allow_partial_one_click_commit = False
    _req_fc_gate, _fail_keys_gate = _requires_full_coverage_for_primary_one_click(current_overview)
    _fk_set = set(_fail_keys_gate or [])
    _bend_family = {"bending", "flexure", "ductility"}
    _has_bend_fail = bool(_fk_set & _bend_family)
    _has_shear_fail = "shear" in _fk_set
    if (
        str(final_candidate_commit_meta.get("reason") or "") == "partial_failure_coverage"
        and _req_fc_gate
        and _has_bend_fail
        and _has_shear_fail
        and isinstance(candidate_for_commit, dict)
        and bool(solver_final_updates)
    ):
        _seed_gate = evaluate_candidate_full(
            _guidance_state_snapshot(current_state),
            source="one_click_partial_commit_combined_gate_seed",
            updates={},
        )
        if isinstance(_seed_gate, dict) and is_valid_progress_while_failing(
            candidate_for_commit,
            _seed_gate,
        ):
            allow_partial_one_click_commit = True
    if (
        not allow_partial_one_click_commit
        and str(solve.get("stop_reason") or "") == "best_available_out_of_band_candidate"
        and isinstance(candidate_for_commit, dict)
        and bool(solver_final_updates)
    ):
        _seed_gate_best_effort = evaluate_candidate_full(
            _guidance_state_snapshot(current_state),
            source="one_click_best_effort_cleanup_gate_seed",
            updates={},
        )
        if isinstance(_seed_gate_best_effort, dict) and is_valid_progress_while_failing(
            candidate_for_commit,
            _seed_gate_best_effort,
        ):
            allow_partial_one_click_commit = True
            dbg["one_click_best_effort_cleanup_commit"] = True
    if not allow_partial_one_click_commit:
        _seed_gate_rescue = evaluate_candidate_full(
            _guidance_state_snapshot(current_state),
            source="one_click_rescue_bootstrap_gate_seed",
            updates={},
        )
        if _rescue_bootstrap_partial_commit_allowed(
            solve=solve,
            current_fail_keys=_fail_keys_gate,
            candidate_for_commit=candidate_for_commit,
            candidate_commit_meta=final_candidate_commit_meta,
            solver_final_updates=solver_final_updates,
            seed_eval=_seed_gate_rescue if isinstance(_seed_gate_rescue, dict) else None,
        ):
            allow_partial_one_click_commit = True
            dbg["one_click_rescue_bootstrap_commit"] = True
    return {
        "allow_partial_one_click_commit": bool(allow_partial_one_click_commit),
        "dbg": dbg,
    }


def _resolve_auto_design_partial_commit_gate_coordinator(
    *,
    solve: dict,
    current_state: dict,
    current_overview: dict,
    candidate_for_commit,
    final_candidate_valid_for_commit: bool,
    final_candidate_commit_meta: dict,
    solver_final_updates: dict,
    final_updates: dict,
    dbg: dict,
    win_l,
    win_at,
    trace_run_id: str,
    trace_src: str,
) -> dict:
    commit_blocked_reason: str | None = None
    if (
        not bool(final_candidate_valid_for_commit)
        and str(final_candidate_commit_meta.get("reason") or "")
        in ("partial_failure_coverage", "candidate_preview_has_fail_status")
    ):
        partial_commit_allowance = _resolve_auto_design_partial_commit_allowance_coordinator(
            solve=solve,
            current_state=current_state,
            current_overview=current_overview,
            candidate_for_commit=candidate_for_commit,
            final_candidate_commit_meta=final_candidate_commit_meta,
            solver_final_updates=solver_final_updates,
            dbg=dbg,
        )
        allow_partial_one_click_commit = partial_commit_allowance[
            "allow_partial_one_click_commit"
        ]
        dbg = partial_commit_allowance["dbg"]
        if allow_partial_one_click_commit:
            dbg["one_click_partial_progress_commit"] = True
            dbg["one_click_commit_blocked_reason"] = None
            dbg["one_click_final_candidate_valid_for_commit"] = True
            final_candidate_valid_for_commit = True
            _append_design_guide_trace(
                "commit_allowed_partial_combined_fail"
                if not bool(dbg.get("one_click_best_effort_cleanup_commit"))
                and not bool(dbg.get("one_click_rescue_bootstrap_commit"))
                else "commit_allowed_best_effort_cleanup",
                {
                    "winning_label": win_l,
                    "winning_action_type": win_at,
                    "current_fail_keys": list(final_candidate_commit_meta.get("fail_keys") or []),
                    "candidate_covered_fail_keys": list(final_candidate_commit_meta.get("covered_fail_keys") or []),
                    "candidate_remaining_fail_keys": list(final_candidate_commit_meta.get("remaining_fail_keys") or []),
                    "final_updates": dict(final_updates),
                    "rescue_bootstrap_commit": bool(dbg.get("one_click_rescue_bootstrap_commit")),
                },
                run_id=trace_run_id,
                source=trace_src,
            )
        else:
            commit_blocked_reason = str(final_candidate_commit_meta.get("reason") or "missing_candidate")
            dbg["one_click_commit_blocked_reason"] = commit_blocked_reason
            _append_design_guide_trace(
                "commit_blocked",
                {
                    "commit_blocked_reason": commit_blocked_reason,
                    "winning_label": win_l,
                    "winning_action_type": win_at,
                    "current_fail_keys": list(final_candidate_commit_meta.get("fail_keys") or []),
                    "candidate_covered_fail_keys": list(final_candidate_commit_meta.get("covered_fail_keys") or []),
                    "candidate_remaining_fail_keys": list(final_candidate_commit_meta.get("remaining_fail_keys") or []),
                    "final_updates": dict(final_updates),
                },
                run_id=trace_run_id,
                source=trace_src,
            )
            final_updates = {}
    else:
        dbg["one_click_commit_blocked_reason"] = None
    return {
        "dbg": dbg,
        "final_updates": final_updates,
        "final_candidate_valid_for_commit": bool(final_candidate_valid_for_commit),
        "commit_blocked_reason": commit_blocked_reason,
    }


def _prepare_auto_design_commit_start_coordinator(
    *,
    current_state: dict,
    final_updates: dict,
    dbg: dict,
    win_l,
    win_at,
    trace_run_id: str,
    trace_src: str,
) -> dict:
    pre_commit_shared_state = copy.deepcopy(_shared_state_snapshot())
    sanitized_preview, sanitize_meta = _sanitize_shared_update_bundle(
        final_updates,
        source="auto_design_commit",
    )
    dbg["final_updates_raw_keys"] = sorted([str(k) for k in dict(final_updates or {}).keys()])
    dbg["final_updates_sanitized_keys"] = sorted([str(k) for k in dict(sanitized_preview or {}).keys()])
    dbg["final_updates_dropped_nonshared_keys"] = list(sanitize_meta.get("dropped_nonshared_keys") or [])
    dbg["final_updates_dropped_private_keys"] = list(sanitize_meta.get("dropped_private_keys") or [])
    commit_mode_config = _design_mode_config(_design_optimisation_goal(current_state))
    raw_commit_preview = None
    sanitized_commit_preview = None
    try:
        raw_commit_preview = _evaluate_auto_design_candidate(
            current_state,
            updates=final_updates,
            source="one_click_commit_preview_raw",
            label=str(win_l or "Apply one-click design"),
            action_type="apply_resolved_candidate",
        )
    except Exception:
        raw_commit_preview = None
    try:
        sanitized_commit_preview = _evaluate_auto_design_candidate(
            current_state,
            updates=sanitized_preview,
            source="one_click_commit_preview_sanitized",
            label=str(win_l or "Apply one-click design"),
            action_type="apply_resolved_candidate",
        )
    except Exception:
        sanitized_commit_preview = None
    dbg["raw_commit_preview_worst_util"] = (
        None
        if not isinstance(raw_commit_preview, dict)
        else float((((raw_commit_preview.get("overview") or {}).get("worst_util")) or 0.0))
    )
    dbg["raw_commit_preview_statuses"] = (
        dict((raw_commit_preview.get("overview") or {}).get("statuses") or {})
        if isinstance(raw_commit_preview, dict)
        else {}
    )
    dbg["sanitized_commit_preview_worst_util"] = (
        None
        if not isinstance(sanitized_commit_preview, dict)
        else float((((sanitized_commit_preview.get("overview") or {}).get("worst_util")) or 0.0))
    )
    dbg["sanitized_commit_preview_statuses"] = (
        dict((sanitized_commit_preview.get("overview") or {}).get("statuses") or {})
        if isinstance(sanitized_commit_preview, dict)
        else {}
    )
    if str(dbg.get("target_band_domain") or "").strip().lower() == "shear":
        if isinstance(raw_commit_preview, dict):
            raw_commit_preview["target_domain_for_band"] = "shear"
        if isinstance(sanitized_commit_preview, dict):
            sanitized_commit_preview["target_domain_for_band"] = "shear"
    _record_one_click_shear_publish_audit(
        stage="iterative_selected_candidate",
        source="one_click_auto_design:iterative",
        candidate_updates=final_updates,
        publish_attempted=False,
        publish_blocked=True,
    )
    try:
        pre_ev = evaluate_candidate_full(
            _guidance_state_snapshot(pre_commit_shared_state),
            source="one_click_pre_commit_audit",
            label="Pre-commit",
            action_type="one_click",
            updates={},
        )
        if isinstance(pre_ev, dict):
            pre_commit_worst_util = float((pre_ev.get("overview") or {}).get("worst_util", 0.0) or 0.0)
    except Exception:
        pre_commit_worst_util = None
    dbg["pre_commit_worst_util"] = pre_commit_worst_util

    _append_design_guide_trace(
        "commit_start",
        {
            "final_updates": dict(final_updates),
            "final_updates_raw_keys": list(dbg.get("final_updates_raw_keys") or []),
            "final_updates_sanitized_keys": list(dbg.get("final_updates_sanitized_keys") or []),
            "final_updates_dropped_nonshared_keys": list(dbg.get("final_updates_dropped_nonshared_keys") or []),
            "final_updates_dropped_private_keys": list(dbg.get("final_updates_dropped_private_keys") or []),
            "winning_label": win_l,
            "winning_action_type": win_at,
            "pre_commit_worst_util": pre_commit_worst_util,
            "raw_commit_preview_worst_util": dbg.get("raw_commit_preview_worst_util"),
            "raw_commit_preview_statuses": dict(dbg.get("raw_commit_preview_statuses") or {}),
            "sanitized_commit_preview_worst_util": dbg.get("sanitized_commit_preview_worst_util"),
            "sanitized_commit_preview_statuses": dict(dbg.get("sanitized_commit_preview_statuses") or {}),
        },
        run_id=trace_run_id,
        source=trace_src,
    )
    return {
        "dbg": dbg,
        "pre_commit_shared_state": pre_commit_shared_state,
        "pre_commit_worst_util": pre_commit_worst_util,
        "commit_mode_config": commit_mode_config,
    }


def _apply_auto_design_commit_write_audit_setup_coordinator(
    *,
    final_updates: dict,
    dbg: dict,
    stop_reason: str,
    current_overview: dict,
) -> dict:
    _set_shared_updates(final_updates, source="auto_design_commit")
    _publish_current_normalized_shear_truth_coordinator(
        "run_one_click_auto_design:post_current_eval:post_commit_write",
        dbg,
    )
    _post_commit_state_probe = _shared_state_snapshot()
    dbg["final_no_links_candidate_committed"] = bool(
        any(k in final_updates for k in ("lig_d", "lig_legs", "s_lig"))
        and _int_from_state(_post_commit_state_probe, "lig_legs", 0) <= 0
        and _int_from_state(_post_commit_state_probe, "lig_d", 0) <= 0
    )
    _record_one_click_shear_publish_audit(
        stage="final_commit_publish",
        source="auto_design_commit",
        candidate_updates=final_updates,
        publish_attempted=True,
        publish_blocked=False,
    )
    _pop_inputs_widget_keys_for_shared_updates(final_updates)
    commit_audit = _one_click_post_commit_audit(final_updates)
    dbg["one_click_commit_audit"] = dict(commit_audit)
    dbg["audited_commit_updates"] = dict(commit_audit.get("audited_commit_updates") or {})
    dbg["ignored_commit_update_keys"] = list(commit_audit.get("ignored_commit_update_keys") or [])
    dbg["has_row_model_updates"] = bool(commit_audit.get("has_row_model_updates"))
    dbg["ignored_row_model_legacy_mirror_keys"] = list(commit_audit.get("ignored_row_model_legacy_mirror_keys") or [])
    dbg["post_commit_mismatch_keys"] = list(commit_audit.get("post_commit_mismatch_keys") or [])
    dbg["post_commit_mismatch_details"] = dict(commit_audit.get("post_commit_mismatch_details") or {})
    dbg["post_commit_live_worst_util"] = commit_audit.get("post_commit_live_worst_util")
    dbg["post_commit_live_statuses"] = commit_audit.get("post_commit_live_statuses")
    dbg["one_click_best_effort_cleanup_commit"] = bool(
        str(stop_reason or "") == "best_available_out_of_band_candidate"
        and any(
            str(v).strip() == "FAIL" or v == BEAM_STATUS_FAIL
            for v in dict(current_overview.get("statuses") or {}).values()
        )
    )
    st.session_state["_one_click_post_commit_audit_latest"] = {
        "post_commit_matches_intended_updates": commit_audit.get("post_commit_matches_intended_updates"),
        "post_commit_mismatch_keys": list(commit_audit.get("post_commit_mismatch_keys") or []),
        "ignored_commit_update_keys": list(commit_audit.get("ignored_commit_update_keys") or []),
        "has_row_model_updates": bool(commit_audit.get("has_row_model_updates")),
        "ignored_row_model_legacy_mirror_keys": list(commit_audit.get("ignored_row_model_legacy_mirror_keys") or []),
        "post_commit_live_worst_util": commit_audit.get("post_commit_live_worst_util"),
        "post_commit_live_statuses": dict(commit_audit.get("post_commit_live_statuses") or {}),
    }
    return {
        "dbg": dbg,
        "commit_audit": commit_audit,
    }


def _handle_auto_design_commit_rejected_rollback_coordinator(
    *,
    commit_audit: dict,
    commit_reject_reason,
    dbg: dict,
    pre_commit_shared_state: dict,
    pre_commit_worst_util,
    solver_final_updates: dict,
    trace_run_id: str,
    trace_src: str,
) -> dict:
    commit_rejected = True
    dbg["final_no_links_candidate_committed"] = False
    _restore_shared_state_snapshot(pre_commit_shared_state, source="one_click_auto_design:rollback_failed_commit")
    try:
        persist_active_beam_from_shared()
    except Exception:
        pass
    _pop_inputs_widget_keys_for_shared_updates({k: pre_commit_shared_state.get(k) for k in SHARED_DEFAULTS.keys()})
    final_updates = {}
    dbg["one_click_commit_rejected"] = True
    dbg["one_click_commit_reject_reason"] = commit_reject_reason
    dbg["one_click_commit_rolled_back"] = True
    dbg["restored_after_failed_commit"] = True
    _append_design_guide_trace(
        "commit_rejected",
        {
            "reject_reason": commit_reject_reason,
            "one_click_commit_rejected": True,
            "one_click_commit_rolled_back": True,
            "audited_commit_updates": commit_audit.get("audited_commit_updates"),
            "ignored_commit_update_keys": commit_audit.get("ignored_commit_update_keys"),
            "has_row_model_updates": commit_audit.get("has_row_model_updates"),
            "ignored_row_model_legacy_mirror_keys": commit_audit.get("ignored_row_model_legacy_mirror_keys"),
            "post_commit_mismatch_keys": commit_audit.get("post_commit_mismatch_keys"),
            "post_commit_mismatch_details": commit_audit.get("post_commit_mismatch_details"),
            "pre_commit_worst_util": pre_commit_worst_util,
            "post_commit_live_worst_util": commit_audit.get("post_commit_live_worst_util"),
            "post_commit_live_statuses": commit_audit.get("post_commit_live_statuses"),
            "restored_after_failed_commit": True,
            "attempted_final_updates": dict(solver_final_updates),
            "final_updates_raw_keys": list(dbg.get("final_updates_raw_keys") or []),
            "final_updates_sanitized_keys": list(dbg.get("final_updates_sanitized_keys") or []),
            "final_updates_dropped_nonshared_keys": list(dbg.get("final_updates_dropped_nonshared_keys") or []),
            "final_updates_dropped_private_keys": list(dbg.get("final_updates_dropped_private_keys") or []),
        },
        run_id=trace_run_id,
        source=trace_src,
    )
    _invalidate_design_guide_caches(
        reason="one_click_auto_design:commit_rejected",
        updated_keys=list(solver_final_updates.keys()),
    )
    rollback_publish_payload = finalize_auto_design_publish(
        updated_keys=sorted(list(solver_final_updates.keys())),
        source="one_click_auto_design:commit_rollback",
        focus_section="shear" if any(k in {"lig_d", "lig_legs", "s_lig"} for k in solver_final_updates.keys()) else None,
        set_run_design_clicked=True,
    )
    dbg["rollback_publish_payload"] = dict(rollback_publish_payload)
    _agent_debug_log(
        "One-click commit rejected after live validation; rolled back",
        {
            "reject_reason": commit_reject_reason,
            "audit": dict(commit_audit),
            "audited_commit_updates": commit_audit.get("audited_commit_updates"),
            "ignored_commit_update_keys": commit_audit.get("ignored_commit_update_keys"),
            "has_row_model_updates": commit_audit.get("has_row_model_updates"),
            "ignored_row_model_legacy_mirror_keys": commit_audit.get("ignored_row_model_legacy_mirror_keys"),
            "post_commit_mismatch_keys": commit_audit.get("post_commit_mismatch_keys"),
            "post_commit_mismatch_details": commit_audit.get("post_commit_mismatch_details"),
        },
        location="inputs_page.py:run_one_click_auto_design:commit_rejected",
        hypothesis_id="H_ONE_CLICK_COMMIT",
    )
    return {
        "dbg": dbg,
        "final_updates": final_updates,
        "commit_rejected": bool(commit_rejected),
        "commit_reject_reason": commit_reject_reason,
    }


def _handle_auto_design_commit_success_audit_setup_coordinator(
    *,
    commit_audit: dict,
    final_updates: dict,
    dbg: dict,
    trace_run_id: str,
    trace_src: str,
) -> dict:
    try:
        persist_active_beam_from_shared()
    except Exception:
        pass
    dbg["one_click_commit_rejected"] = False
    dbg["one_click_commit_reject_reason"] = None
    dbg["one_click_commit_rolled_back"] = False
    dbg["restored_after_failed_commit"] = False
    _append_design_guide_trace(
        "commit_audit",
        {
            **dict(commit_audit),
            "audited_commit_updates": commit_audit.get("audited_commit_updates"),
            "ignored_commit_update_keys": commit_audit.get("ignored_commit_update_keys"),
            "has_row_model_updates": commit_audit.get("has_row_model_updates"),
            "ignored_row_model_legacy_mirror_keys": commit_audit.get("ignored_row_model_legacy_mirror_keys"),
            "post_commit_mismatch_keys": commit_audit.get("post_commit_mismatch_keys"),
            "post_commit_mismatch_details": commit_audit.get("post_commit_mismatch_details"),
            "final_updates_raw_keys": list(dbg.get("final_updates_raw_keys") or []),
            "final_updates_sanitized_keys": list(dbg.get("final_updates_sanitized_keys") or []),
            "final_updates_dropped_nonshared_keys": list(dbg.get("final_updates_dropped_nonshared_keys") or []),
            "final_updates_dropped_private_keys": list(dbg.get("final_updates_dropped_private_keys") or []),
        },
        run_id=trace_run_id,
        source=trace_src,
    )
    _invalidate_design_guide_caches(
        reason="one_click_auto_design",
        updated_keys=list(final_updates.keys()),
    )
    success_publish_payload = finalize_auto_design_publish(
        updated_keys=sorted(list(final_updates.keys())),
        source="one_click_auto_design",
        focus_section="shear" if any(k in {"lig_d", "lig_legs", "s_lig"} for k in final_updates.keys()) else None,
        set_run_design_clicked=True,
    )
    try:
        accepted_fp = _local_cleanup_acceptance_fingerprint(_shared_state_snapshot())
        _DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.add(accepted_fp)
        st.session_state["_design_guide_post_cleanup_acceptance_fp"] = accepted_fp
        st.session_state["_design_guide_post_cleanup_acceptance_enabled"] = True
    except Exception:
        pass
    dbg["success_publish_payload"] = dict(success_publish_payload)
    refreshed_commit_audit = _one_click_post_commit_audit(final_updates)
    if isinstance(refreshed_commit_audit, dict):
        commit_audit = refreshed_commit_audit
        dbg["one_click_commit_audit"] = dict(commit_audit)
        dbg["audited_commit_updates"] = dict(commit_audit.get("audited_commit_updates") or {})
        dbg["ignored_commit_update_keys"] = list(commit_audit.get("ignored_commit_update_keys") or [])
        dbg["has_row_model_updates"] = bool(commit_audit.get("has_row_model_updates"))
        dbg["ignored_row_model_legacy_mirror_keys"] = list(
            commit_audit.get("ignored_row_model_legacy_mirror_keys") or []
        )
        dbg["post_commit_mismatch_keys"] = list(commit_audit.get("post_commit_mismatch_keys") or [])
        dbg["post_commit_mismatch_details"] = dict(commit_audit.get("post_commit_mismatch_details") or {})
        dbg["post_commit_live_worst_util"] = commit_audit.get("post_commit_live_worst_util")
        dbg["post_commit_live_statuses"] = commit_audit.get("post_commit_live_statuses")
        st.session_state["_one_click_post_commit_audit_latest"] = {
            "post_commit_matches_intended_updates": commit_audit.get("post_commit_matches_intended_updates"),
            "post_commit_mismatch_keys": list(commit_audit.get("post_commit_mismatch_keys") or []),
            "ignored_commit_update_keys": list(commit_audit.get("ignored_commit_update_keys") or []),
            "has_row_model_updates": bool(commit_audit.get("has_row_model_updates")),
            "ignored_row_model_legacy_mirror_keys": list(
                commit_audit.get("ignored_row_model_legacy_mirror_keys") or []
            ),
            "post_commit_live_worst_util": commit_audit.get("post_commit_live_worst_util"),
            "post_commit_live_statuses": dict(commit_audit.get("post_commit_live_statuses") or {}),
        }
    _agent_debug_log(
        "One-click iterative commit audit",
        dict(commit_audit),
        location="inputs_page.py:run_one_click_auto_design:commit_audit",
        hypothesis_id="H_ONE_CLICK_COMMIT",
    )
    return {
        "dbg": dbg,
        "commit_audit": commit_audit,
    }


def _prepare_auto_design_strict_post_commit_gate_coordinator(
    *,
    commit_mode_config: dict,
    dbg: dict,
) -> dict:
    strict_live_state = _guidance_state_snapshot(_shared_state_snapshot())
    strict_live_overview = _collect_design_overview(strict_live_state)
    strict_live_ok = _one_click_strict_target_band_ok(strict_live_overview, commit_mode_config)
    dbg["one_click_strict_post_commit_target_band_ok"] = bool(strict_live_ok)
    dbg["one_click_strict_post_commit_live_worst_util"] = strict_live_overview.get(
        "governing_util",
        strict_live_overview.get("worst_util"),
    )
    dbg["one_click_strict_post_commit_statuses"] = dict(strict_live_overview.get("statuses") or {})
    return {
        "dbg": dbg,
        "strict_live_ok": bool(strict_live_ok),
        "strict_live_state": strict_live_state,
        "strict_live_overview": strict_live_overview,
    }


def _handle_auto_design_strict_followup_commit_coordinator(
    *,
    trace_run_id: str,
    dbg: dict,
    final_updates: dict,
    commit_audit: dict,
    commit_mode_config: dict,
) -> dict:
    try:
        follow_strict_state = _build_canonical_design_state_pack(
            _overlay_current_normalized_shear_truth(
                _guidance_state_snapshot(_shared_state_snapshot()),
            ),
        )
        strict_follow = _solve_one_click_to_target(
            follow_strict_state,
            max_steps=2,
            debug_enabled=False,
            trace_run_id=f"{trace_run_id}_strict_band_follow",
            trace_source="one_click_followup_after_strict_band_mismatch",
        )
        fu_strict = dict(strict_follow.get("final_updates") or {})
        dbg["one_click_strict_followup_stop_reason"] = str(strict_follow.get("stop_reason") or "")
        dbg["one_click_strict_followup_update_keys"] = sorted(fu_strict.keys())
        if fu_strict:
            pre_strict = copy.deepcopy(_shared_state_snapshot())
            san_strict, _meta_strict = _sanitize_shared_update_bundle(
                fu_strict,
                source="auto_design_commit_strict_followup",
            )
            if san_strict:
                _set_shared_updates(san_strict, source="auto_design_commit_strict_followup")
                _publish_current_normalized_shear_truth_coordinator(
                    "run_one_click_auto_design:post_strict_followup_write",
                    dbg,
                )
                _pop_inputs_widget_keys_for_shared_updates(san_strict)
                audit_strict = _one_click_post_commit_audit(san_strict)
                live_strict_overview = _collect_design_overview(
                    _guidance_state_snapshot(_shared_state_snapshot()),
                )
                strict_passes, strict_rej = _one_click_commit_audit_passes(
                    audit_strict,
                    partial_progress_commit=False,
                    pre_commit_worst_util=None,
                )
                strict_band_ok_after = _one_click_strict_target_band_ok(
                    live_strict_overview,
                    commit_mode_config,
                )
                if strict_passes and strict_band_ok_after:
                    try:
                        persist_active_beam_from_shared()
                    except Exception:
                        pass
                    _invalidate_design_guide_caches(
                        reason="one_click_auto_design:strict_followup",
                        updated_keys=list(san_strict.keys()),
                    )
                    finalize_auto_design_publish(
                        updated_keys=sorted(list(san_strict.keys())),
                        source="one_click_auto_design:strict_followup",
                        focus_section="shear"
                        if any(k in {"lig_d", "lig_legs", "s_lig"} for k in san_strict.keys())
                        else None,
                        set_run_design_clicked=True,
                    )
                    dbg["one_click_strict_followup_committed"] = True
                    dbg["one_click_strict_followup_commit_audit"] = dict(audit_strict)
                    dbg["one_click_strict_post_commit_target_band_ok"] = True
                    dbg["one_click_strict_post_commit_live_worst_util"] = live_strict_overview.get(
                        "governing_util",
                        live_strict_overview.get("worst_util"),
                    )
                    dbg["one_click_strict_post_commit_statuses"] = dict(
                        live_strict_overview.get("statuses") or {},
                    )
                    final_updates = {**dict(final_updates or {}), **dict(san_strict)}
                    commit_audit = audit_strict
                else:
                    _restore_shared_state_snapshot(
                        pre_strict,
                        source="one_click_auto_design:rollback_strict_followup_failed_audit",
                    )
                    try:
                        persist_active_beam_from_shared()
                    except Exception:
                        pass
                    _pop_inputs_widget_keys_for_shared_updates(
                        {k: pre_strict.get(k) for k in SHARED_DEFAULTS.keys()},
                    )
                    dbg["one_click_strict_followup_committed"] = False
                    dbg["one_click_strict_followup_reject_reason"] = str(
                        strict_rej or "strict_target_band_not_reached",
                    )
    except Exception as _strict_follow_exc:
        dbg["one_click_strict_followup_exception"] = repr(_strict_follow_exc)
    return {
        "dbg": dbg,
        "final_updates": final_updates,
        "commit_audit": commit_audit,
    }


def _apply_auto_design_partial_followup_commit_success_coordinator(
    *,
    san_follow: dict,
    audit_follow: dict,
    follow_solve: dict,
    final_updates: dict,
    commit_audit: dict,
    dbg: dict,
    stop_reason: str,
    fin_u,
    reached: bool,
) -> dict:
    try:
        persist_active_beam_from_shared()
    except Exception:
        pass
    _invalidate_design_guide_caches(
        reason="one_click_auto_design:followup",
        updated_keys=list(san_follow.keys()),
    )
    finalize_auto_design_publish(
        updated_keys=sorted(list(san_follow.keys())),
        source="one_click_auto_design:followup",
        focus_section="shear"
        if any(k in {"lig_d", "lig_legs", "s_lig"} for k in san_follow.keys())
        else None,
        set_run_design_clicked=True,
    )
    dbg["one_click_followup_committed"] = True
    dbg["one_click_followup_commit_audit"] = dict(audit_follow)
    final_updates = {**dict(final_updates or {}), **dict(san_follow)}
    commit_audit = audit_follow
    dbg["one_click_commit_audit"] = dict(commit_audit)
    dbg["audited_commit_updates"] = dict(commit_audit.get("audited_commit_updates") or {})
    dbg["ignored_commit_update_keys"] = list(
        commit_audit.get("ignored_commit_update_keys") or [],
    )
    dbg["has_row_model_updates"] = bool(commit_audit.get("has_row_model_updates"))
    dbg["ignored_row_model_legacy_mirror_keys"] = list(
        commit_audit.get("ignored_row_model_legacy_mirror_keys") or []
    )
    dbg["post_commit_mismatch_keys"] = list(commit_audit.get("post_commit_mismatch_keys") or [])
    dbg["post_commit_mismatch_details"] = dict(
        commit_audit.get("post_commit_mismatch_details") or {},
    )
    dbg["post_commit_live_worst_util"] = commit_audit.get("post_commit_live_worst_util")
    dbg["post_commit_live_statuses"] = commit_audit.get("post_commit_live_statuses")
    st.session_state["_one_click_post_commit_audit_latest"] = {
        "post_commit_matches_intended_updates": commit_audit.get(
            "post_commit_matches_intended_updates",
        ),
        "post_commit_mismatch_keys": list(commit_audit.get("post_commit_mismatch_keys") or []),
        "ignored_commit_update_keys": list(
            commit_audit.get("ignored_commit_update_keys") or [],
        ),
        "has_row_model_updates": bool(commit_audit.get("has_row_model_updates")),
        "ignored_row_model_legacy_mirror_keys": list(
            commit_audit.get("ignored_row_model_legacy_mirror_keys") or []
        ),
        "post_commit_live_worst_util": commit_audit.get("post_commit_live_worst_util"),
        "post_commit_live_statuses": dict(
            commit_audit.get("post_commit_live_statuses") or {},
        ),
    }
    follow_stop_reason = str(follow_solve.get("stop_reason") or "").strip()
    if follow_stop_reason:
        stop_reason = follow_stop_reason
    follow_worst = commit_audit.get("post_commit_live_worst_util")
    try:
        if follow_worst is not None:
            fin_u = float(follow_worst)
    except (TypeError, ValueError):
        pass
    follow_statuses = dict(commit_audit.get("post_commit_live_statuses") or {})
    if follow_stop_reason == "reached_target_band":
        reached = True
        fin_u = float(commit_audit.get("post_commit_live_worst_util") or fin_u or 0.0)
    if follow_statuses:
        dbg["one_click_followup_post_commit_live_statuses"] = dict(follow_statuses)
    return {
        "dbg": dbg,
        "final_updates": final_updates,
        "commit_audit": commit_audit,
        "stop_reason": stop_reason,
        "fin_u": fin_u,
        "reached": reached,
    }


def _handle_auto_design_partial_followup_rejected_rollback_coordinator(
    *,
    pre_follow: dict,
    rej_follow,
    dbg: dict,
) -> dict:
    _restore_shared_state_snapshot(
        pre_follow,
        source="one_click_auto_design:rollback_followup_failed_audit",
    )
    try:
        persist_active_beam_from_shared()
    except Exception:
        pass
    _pop_inputs_widget_keys_for_shared_updates(
        {k: pre_follow.get(k) for k in SHARED_DEFAULTS.keys()},
    )
    dbg["one_click_followup_committed"] = False
    dbg["one_click_followup_reject_reason"] = str(rej_follow or "")
    return {"dbg": dbg}


def _build_auto_design_partial_progress_followup_commit_result_state_coordinator(
    *,
    followup_scope: dict,
) -> dict:
    return {
        "dbg": followup_scope["dbg"],
        "final_updates": followup_scope["final_updates"],
        "commit_audit": followup_scope["commit_audit"],
        "stop_reason": followup_scope["stop_reason"],
        "fin_u": followup_scope["fin_u"],
        "reached": bool(followup_scope["reached"]),
    }


def _handle_auto_design_partial_progress_followup_commit_coordinator(
    *,
    trace_run_id: str,
    dbg: dict,
    final_updates: dict,
    commit_audit: dict,
    stop_reason: str,
    fin_u,
    reached: bool,
) -> dict:
    if bool(dbg.get("one_click_partial_progress_commit")) and bool(
        set(dbg.get("candidate_remaining_fail_keys") or []) & {"bending", "flexure", "ductility"},
    ):
        try:
            current_state_follow = _build_canonical_design_state_pack(
                _overlay_current_normalized_shear_truth(
                    _guidance_state_snapshot(_shared_state_snapshot()),
                ),
            )
            follow_solve = _solve_one_click_to_target(
                current_state_follow,
                max_steps=4,
                debug_enabled=False,
                trace_run_id=f"{trace_run_id}_bend_follow",
                trace_source="one_click_followup_after_partial_shear",
            )
            fu_follow = dict(follow_solve.get("final_updates") or {})
            dbg["one_click_followup_stop_reason"] = str(follow_solve.get("stop_reason") or "")
            dbg["one_click_followup_update_keys"] = sorted(fu_follow.keys())
            if fu_follow:
                trial_follow = dict(_guidance_state_snapshot(current_state_follow))
                trial_follow.update(fu_follow)
                pe_follow = evaluate_candidate_full(
                    _guidance_state_snapshot(trial_follow),
                    source="one_click_followup_bending_gate",
                    updates=fu_follow,
                )
                _bend_stat = ""
                if isinstance(pe_follow, dict):
                    _bend_stat = str(
                        ((pe_follow.get("overview") or {}).get("statuses") or {}).get("bending") or "",
                    ).strip().upper()
                if _bend_stat == "FAIL":
                    pass
                else:
                    san_follow, _meta_follow = _sanitize_shared_update_bundle(
                        fu_follow,
                        source="auto_design_commit_followup",
                    )
                    if san_follow:
                        pre_follow = copy.deepcopy(_shared_state_snapshot())
                        pre_follow_worst: float | None = None
                        try:
                            _pre_ev_f = evaluate_candidate_full(
                                _guidance_state_snapshot(pre_follow),
                                source="one_click_followup_pre_commit_worst",
                                updates={},
                            )
                            if isinstance(_pre_ev_f, dict):
                                pre_follow_worst = float(
                                    (_pre_ev_f.get("overview") or {}).get("worst_util", 0.0) or 0.0,
                                )
                        except (TypeError, ValueError):
                            pre_follow_worst = None
                        if pre_follow_worst is None:
                            try:
                                _ov_pf = _collect_design_overview(
                                    _guidance_state_snapshot(pre_follow),
                                )
                                pre_follow_worst = float(_ov_pf.get("worst_util") or 0.0)
                            except (TypeError, ValueError):
                                pre_follow_worst = None
                        _set_shared_updates(san_follow, source="auto_design_commit_followup")
                        _publish_current_normalized_shear_truth_coordinator(
                            "run_one_click_auto_design:post_followup_write",
                            dbg,
                        )
                        _pop_inputs_widget_keys_for_shared_updates(san_follow)
                        audit_follow = _one_click_post_commit_audit(san_follow)
                        passes_follow, rej_follow = _one_click_commit_audit_passes(
                            audit_follow,
                            partial_progress_commit=bool(pre_follow_worst is not None),
                            pre_commit_worst_util=pre_follow_worst,
                        )
                        if passes_follow:
                            followup_success_context = (
                                _apply_auto_design_partial_followup_commit_success_coordinator(
                                    san_follow=san_follow,
                                    audit_follow=audit_follow,
                                    follow_solve=follow_solve,
                                    final_updates=final_updates,
                                    commit_audit=commit_audit,
                                    dbg=dbg,
                                    stop_reason=stop_reason,
                                    fin_u=fin_u,
                                    reached=reached,
                                )
                            )
                            dbg = followup_success_context["dbg"]
                            final_updates = followup_success_context["final_updates"]
                            commit_audit = followup_success_context["commit_audit"]
                            stop_reason = str(followup_success_context["stop_reason"] or "")
                            fin_u = followup_success_context["fin_u"]
                            reached = bool(followup_success_context["reached"])
                        else:
                            followup_rollback_context = (
                                _handle_auto_design_partial_followup_rejected_rollback_coordinator(
                                    pre_follow=pre_follow,
                                    rej_follow=rej_follow,
                                    dbg=dbg,
                                )
                            )
                            dbg = followup_rollback_context["dbg"]
        except Exception as _follow_exc:
            dbg["one_click_followup_exception"] = repr(_follow_exc)
    return _build_auto_design_partial_progress_followup_commit_result_state_coordinator(
        followup_scope=locals(),
    )


def _prepare_auto_design_post_current_eval_response_context_coordinator(
    *,
    stop_reason: str,
    step_count: int,
    init_u,
    fin_u,
    reached: bool,
    dbg: dict,
    win_l,
    solver_final_updates: dict,
    commit_blocked_reason: str | None,
    commit_rejected: bool,
) -> dict:
    _publish_current_normalized_shear_truth_coordinator(
        "run_one_click_auto_design:post_current_eval",
        dbg,
    )
    base_steps = _build_one_click_base_steps_coordinator(
        stop_reason=stop_reason,
        step_count=step_count,
        init_u=init_u,
        fin_u=fin_u,
        reached=reached,
        dbg=dbg,
        win_l=win_l,
        solver_final_updates=solver_final_updates,
        commit_blocked_reason=commit_blocked_reason,
        commit_rejected=bool(commit_rejected),
    )
    return {
        "base_steps": base_steps,
    }


def _return_auto_design_commit_rejected_response_coordinator(
    *,
    commit_audit: dict | None,
    init_u,
    fin_u,
    commit_reject_reason: str | None,
    dbg: dict,
    trace_run_id: str,
    action_sig,
    goal,
    stop_reason: str,
    win_l,
    win_at,
    final_updates: dict,
    trace_src: str,
    pre_commit_worst_util,
    base_steps: list,
    solver_final_updates: dict,
    solve: dict,
    solver_stop_reason: str,
    tracer_path: str,
    return_with_latch_clear,
) -> dict:
    _trace_run_end_coordinator(
        "commit_rejected",
        commit_audit=commit_audit if isinstance(commit_audit, dict) else None,
        init_u=init_u,
        fin_u=fin_u,
        commit_rejected=True,
        commit_reject_reason=commit_reject_reason,
        dbg=dbg,
        trace_run_id=trace_run_id,
        action_sig=action_sig,
        goal=goal,
        stop_reason=stop_reason,
        win_l=win_l,
        final_updates=final_updates,
        trace_src=trace_src,
    )
    uvr_commit = (
        "One-click candidate was rejected after live validation; no changes were applied. "
        "The candidate failed live post-commit validation and was rolled back."
    )
    _set_one_click_run_feedback(
        status="rejected",
        reason=commit_reject_reason or stop_reason,
        winning_label=win_l,
        winning_action_type=win_at,
        pre_commit_worst_util=pre_commit_worst_util,
        extra_payload={
            "current_fail_fingerprint": dict(dbg.get("current_fail_fingerprint") or {}),
            "current_fail_keys": list(dbg.get("current_fail_keys") or []),
            "current_fail_keys_source": "canonical_overview",
            "shear_fail_status_used": dbg.get("shear_fail_status_used"),
            "shear_fail_util_used": dbg.get("shear_fail_util_used"),
            "current_shear_status": dbg.get("current_shear_status"),
            "current_shear_util": dbg.get("current_shear_util"),
            "current_shear_selection_origin": dbg.get("current_shear_selection_origin"),
        },
        debug_target=dbg,
    )
    return return_with_latch_clear("run_one_click_auto_design:commit_rejected", {
        "status": "rejected",
        "stop_reason": "commit_validation_failed",
        "one_click_solver_stop_reason": solver_stop_reason,
        "steps": base_steps,
        "recommendation": None,
        "recommendation_result": None,
        "auto_design_solver_recommendation": None,
        "recommendation_envelope": _result_recommendation_envelope_coordinator(
            status="rejected",
            dbg=dbg,
            commit_audit=commit_audit if isinstance(commit_audit, dict) else None,
            updates=solver_final_updates,
            blocked_reason=commit_reject_reason or stop_reason,
            commit_eligible=False,
        ),
        "one_click_solve": solve,
        "one_click_solver_debug": dbg,
        "one_click_commit_audit": commit_audit,
        "trace_run_id": trace_run_id,
        "design_guide_tracer_path": tracer_path,
        "tracer_skip_reason": None,
        "tracer_entry_reached": True,
        "one_click_commit_rejected": True,
        "one_click_commit_reject_reason": commit_reject_reason,
        "one_click_commit_rolled_back": True,
        "user_visible_commit_rejection": uvr_commit,
    })


def _return_auto_design_commit_blocked_response_coordinator(
    *,
    commit_audit: dict | None,
    init_u,
    fin_u,
    commit_rejected: bool,
    commit_reject_reason: str | None,
    commit_blocked_reason: str | None,
    dbg: dict,
    trace_run_id: str,
    action_sig,
    goal,
    stop_reason: str,
    win_l,
    win_at,
    final_updates: dict,
    trace_src: str,
    pre_commit_worst_util,
    base_steps: list,
    solver_final_updates: dict,
    solve: dict,
    solver_stop_reason: str,
    tracer_path: str,
    return_with_latch_clear,
) -> dict:
    _trace_run_end_coordinator(
        "no_actionable_full_coverage_candidate",
        commit_audit=commit_audit if isinstance(commit_audit, dict) else None,
        init_u=init_u,
        fin_u=fin_u,
        commit_rejected=bool(commit_rejected),
        commit_reject_reason=commit_reject_reason,
        dbg=dbg,
        trace_run_id=trace_run_id,
        action_sig=action_sig,
        goal=goal,
        stop_reason=stop_reason,
        win_l=win_l,
        final_updates=final_updates,
        trace_src=trace_src,
    )
    _set_one_click_run_feedback(
        status="blocked",
        reason=commit_blocked_reason or stop_reason,
        winning_label=win_l,
        winning_action_type=win_at,
        pre_commit_worst_util=pre_commit_worst_util,
        extra_payload={
            "current_fail_fingerprint": dict(dbg.get("current_fail_fingerprint") or {}),
            "current_fail_keys": list(dbg.get("current_fail_keys") or []),
            "current_fail_keys_source": "canonical_overview",
            "shear_fail_status_used": dbg.get("shear_fail_status_used"),
            "shear_fail_util_used": dbg.get("shear_fail_util_used"),
            "current_shear_status": dbg.get("current_shear_status"),
            "current_shear_util": dbg.get("current_shear_util"),
            "current_shear_selection_origin": dbg.get("current_shear_selection_origin"),
        },
        debug_target=dbg,
    )
    return return_with_latch_clear("run_one_click_auto_design:partial_failure_coverage", {
        "status": "no_actionable_full_coverage_candidate",
        "stop_reason": "partial_failure_coverage",
        "one_click_solver_stop_reason": solver_stop_reason,
        "steps": base_steps,
        "recommendation": None,
        "recommendation_result": None,
        "auto_design_solver_recommendation": None,
        "recommendation_envelope": _result_recommendation_envelope_coordinator(
            status="blocked",
            dbg=dbg,
            commit_audit=commit_audit if isinstance(commit_audit, dict) else None,
            updates=solver_final_updates,
            blocked_reason=commit_blocked_reason or stop_reason,
            commit_eligible=False,
        ),
        "one_click_solve": solve,
        "one_click_solver_debug": dbg,
        "one_click_commit_audit": commit_audit,
        "trace_run_id": trace_run_id,
        "design_guide_tracer_path": tracer_path,
        "tracer_skip_reason": None,
        "tracer_entry_reached": True,
        "current_fail_keys": list(dbg.get("current_fail_keys") or []),
        "candidate_covered_fail_keys": list(dbg.get("candidate_covered_fail_keys") or []),
        "candidate_remaining_fail_keys": list(dbg.get("candidate_remaining_fail_keys") or []),
        "one_click_commit_blocked_reason": "partial_failure_coverage",
        "user_visible_no_action_reason": (
            "No single one-click update currently covers all failing checks. "
            "The current best local moves address only part of the fail set, so the guide is showing separate next steps."
        ),
    })


def _return_auto_design_failed_no_action_response_coordinator(
    *,
    commit_audit: dict | None,
    init_u,
    fin_u,
    commit_rejected: bool,
    commit_reject_reason: str | None,
    dbg: dict,
    trace_run_id: str | None,
    action_sig,
    goal,
    stop_reason: str,
    win_l,
    win_at,
    final_updates: dict,
    trace_src,
    pre_commit_worst_util: float | None,
    base_steps: list,
    solver_final_updates: dict,
    solve: dict,
    tracer_path: str | None,
    return_with_latch_clear,
) -> dict:
    _trace_run_end_coordinator(
        "no_action",
        commit_audit=commit_audit,
        init_u=init_u,
        fin_u=fin_u,
        commit_rejected=bool(commit_rejected),
        commit_reject_reason=commit_reject_reason,
        dbg=dbg,
        trace_run_id=trace_run_id,
        action_sig=action_sig,
        goal=goal,
        stop_reason=stop_reason,
        win_l=win_l,
        final_updates=final_updates,
        trace_src=trace_src,
    )
    _uv_na = _attach_no_action_visibility_coordinator(stop_reason=stop_reason, dbg=dbg)
    _set_one_click_run_feedback(
        status="blocked",
        reason=stop_reason,
        winning_label=win_l,
        winning_action_type=win_at,
        pre_commit_worst_util=pre_commit_worst_util,
        extra_payload={
            "current_fail_fingerprint": dict(dbg.get("current_fail_fingerprint") or {}),
            "current_fail_keys": list(dbg.get("current_fail_keys") or []),
            "current_fail_keys_source": "canonical_overview",
        },
        debug_target=dbg,
    )
    return return_with_latch_clear("run_one_click_auto_design:no_action_failed", {
        "status": "no_action",
        "stop_reason": stop_reason,
        "steps": base_steps + ["Solver evaluation failed; no changes applied."],
        "recommendation": None,
        "recommendation_result": None,
        "auto_design_solver_recommendation": None,
        "recommendation_envelope": _result_recommendation_envelope_coordinator(
            status="failed",
            dbg=dbg,
            commit_audit=commit_audit,
            updates=solver_final_updates,
            blocked_reason=stop_reason,
            commit_eligible=False,
        ),
        "one_click_solve": solve,
        "one_click_solver_debug": dbg,
        "one_click_commit_audit": commit_audit,
        "trace_run_id": trace_run_id,
        "design_guide_tracer_path": tracer_path,
        "tracer_skip_reason": None,
        "tracer_entry_reached": True,
        **_uv_na,
    })


def _return_auto_design_blocked_status_response_coordinator(
    *,
    commit_audit: dict | None,
    init_u,
    fin_u,
    commit_rejected: bool,
    commit_reject_reason: str | None,
    dbg: dict,
    trace_run_id: str | None,
    action_sig,
    goal,
    stop_reason: str,
    win_l,
    win_at,
    final_updates: dict,
    trace_src,
    pre_commit_worst_util: float | None,
    base_steps: list,
    solver_final_updates: dict,
    solve: dict,
    tracer_path: str | None,
    return_with_latch_clear,
) -> dict:
    _trace_run_end_coordinator(
        "blocked",
        commit_audit=commit_audit,
        init_u=init_u,
        fin_u=fin_u,
        commit_rejected=bool(commit_rejected),
        commit_reject_reason=commit_reject_reason,
        dbg=dbg,
        trace_run_id=trace_run_id,
        action_sig=action_sig,
        goal=goal,
        stop_reason=stop_reason,
        win_l=win_l,
        final_updates=final_updates,
        trace_src=trace_src,
    )
    _uv_na = _attach_no_action_visibility_coordinator(stop_reason=stop_reason, dbg=dbg)
    _set_one_click_run_feedback(
        status="blocked",
        reason=stop_reason,
        winning_label=win_l,
        winning_action_type=win_at,
        pre_commit_worst_util=pre_commit_worst_util,
        extra_payload={
            "current_fail_fingerprint": dict(dbg.get("current_fail_fingerprint") or {}),
            "current_fail_keys": list(dbg.get("current_fail_keys") or []),
            "current_fail_keys_source": "canonical_overview",
        },
        debug_target=dbg,
    )
    return return_with_latch_clear("run_one_click_auto_design:blocked", {
        "status": "blocked",
        "stop_reason": stop_reason,
        "steps": base_steps,
        "recommendation": None,
        "recommendation_result": None,
        "auto_design_solver_recommendation": None,
        "recommendation_envelope": _result_recommendation_envelope_coordinator(
            status="blocked",
            dbg=dbg,
            commit_audit=commit_audit,
            updates=solver_final_updates,
            blocked_reason=stop_reason,
            commit_eligible=False,
        ),
        "one_click_solve": solve,
        "one_click_solver_debug": dbg,
        "one_click_commit_audit": commit_audit,
        "trace_run_id": trace_run_id,
        "design_guide_tracer_path": tracer_path,
        "tracer_skip_reason": None,
        "tracer_entry_reached": True,
        **_uv_na,
    })


def _return_auto_design_already_in_band_response_coordinator(
    *,
    commit_audit: dict | None,
    init_u,
    fin_u,
    commit_rejected: bool,
    commit_reject_reason: str | None,
    dbg: dict,
    trace_run_id: str | None,
    action_sig,
    goal,
    stop_reason: str,
    win_l,
    final_updates: dict,
    trace_src,
    base_steps: list,
    solve: dict,
    tracer_path: str | None,
    return_with_latch_clear,
) -> dict:
    _trace_run_end_coordinator(
        "pass",
        commit_audit=commit_audit,
        init_u=init_u,
        fin_u=fin_u,
        commit_rejected=bool(commit_rejected),
        commit_reject_reason=commit_reject_reason,
        dbg=dbg,
        trace_run_id=trace_run_id,
        action_sig=action_sig,
        goal=goal,
        stop_reason=stop_reason,
        win_l=win_l,
        final_updates=final_updates,
        trace_src=trace_src,
    )
    st.session_state.pop("_one_click_run_feedback", None)
    return return_with_latch_clear("run_one_click_auto_design:already_in_band", {
        "status": "pass",
        "stop_reason": stop_reason,
        "steps": base_steps,
        "recommendation": None,
        "recommendation_result": None,
        "auto_design_solver_recommendation": None,
        "recommendation_envelope": _result_recommendation_envelope_coordinator(
            status="no_action",
            dbg=dbg,
            commit_audit=commit_audit,
            updates={},
            blocked_reason="already_in_band",
            commit_eligible=False,
        ),
        "one_click_solve": solve,
        "one_click_solver_debug": dbg,
        "one_click_commit_audit": commit_audit,
        "trace_run_id": trace_run_id,
        "design_guide_tracer_path": tracer_path,
        "tracer_skip_reason": None,
        "tracer_entry_reached": True,
    })


def _return_auto_design_ready_response_coordinator(
    *,
    commit_audit: dict | None,
    init_u,
    fin_u,
    commit_rejected: bool,
    commit_reject_reason: str | None,
    dbg: dict,
    trace_run_id: str | None,
    action_sig,
    goal,
    stop_reason: str,
    win_l,
    final_updates: dict,
    trace_src,
    base_steps: list,
    solve: dict,
    tracer_path: str | None,
    return_with_latch_clear,
) -> dict:
    _trace_run_end_coordinator(
        "ready",
        commit_audit=commit_audit,
        init_u=init_u,
        fin_u=fin_u,
        commit_rejected=bool(commit_rejected),
        commit_reject_reason=commit_reject_reason,
        dbg=dbg,
        trace_run_id=trace_run_id,
        action_sig=action_sig,
        goal=goal,
        stop_reason=stop_reason,
        win_l=win_l,
        final_updates=final_updates,
        trace_src=trace_src,
    )
    st.session_state.pop("_one_click_run_feedback", None)
    return return_with_latch_clear("run_one_click_auto_design:ready", {
        "status": "ready",
        "stop_reason": stop_reason,
        "steps": base_steps,
        "recommendation": None,
        "recommendation_result": None,
        "auto_design_solver_recommendation": None,
        "recommendation_envelope": _result_recommendation_envelope_coordinator(
            status="ready",
            dbg=dbg,
            commit_audit=commit_audit,
            updates=final_updates,
            commit_eligible=True,
        ),
        "one_click_solve": solve,
        "one_click_solver_debug": dbg,
        "one_click_commit_audit": commit_audit,
        "trace_run_id": trace_run_id,
        "design_guide_tracer_path": tracer_path,
        "tracer_skip_reason": None,
        "tracer_entry_reached": True,
    })


def _return_auto_design_default_no_action_response_coordinator(
    *,
    commit_audit: dict | None,
    init_u,
    fin_u,
    commit_rejected: bool,
    commit_reject_reason: str | None,
    commit_blocked_reason: str | None,
    dbg: dict,
    trace_run_id: str | None,
    action_sig,
    goal,
    stop_reason: str,
    win_l,
    win_at,
    final_updates: dict,
    trace_src,
    pre_commit_worst_util: float | None,
    base_steps: list,
    solver_final_updates: dict,
    solve: dict,
    tracer_path: str | None,
    return_with_latch_clear,
) -> dict:
    _trace_run_end_coordinator(
        "no_action",
        commit_audit=commit_audit,
        init_u=init_u,
        fin_u=fin_u,
        commit_rejected=bool(commit_rejected),
        commit_reject_reason=commit_reject_reason,
        dbg=dbg,
        trace_run_id=trace_run_id,
        action_sig=action_sig,
        goal=goal,
        stop_reason=stop_reason,
        win_l=win_l,
        final_updates=final_updates,
        trace_src=trace_src,
    )
    _uv_na = _attach_no_action_visibility_coordinator(stop_reason=stop_reason, dbg=dbg)
    blocked_reason = commit_reject_reason or commit_blocked_reason or stop_reason
    _set_one_click_run_feedback(
        status="blocked",
        reason=blocked_reason,
        winning_label=win_l,
        winning_action_type=win_at,
        pre_commit_worst_util=pre_commit_worst_util,
        extra_payload={
            "current_fail_fingerprint": dict(dbg.get("current_fail_fingerprint") or {}),
            "current_fail_keys": list(dbg.get("current_fail_keys") or []),
            "current_fail_keys_source": "canonical_overview",
        },
        debug_target=dbg,
    )
    return return_with_latch_clear("run_one_click_auto_design:no_action", {
        "status": "no_action",
        "stop_reason": stop_reason,
        "steps": base_steps,
        "recommendation": None,
        "recommendation_result": None,
        "auto_design_solver_recommendation": None,
        "recommendation_envelope": _result_recommendation_envelope_coordinator(
            status="no_action",
            dbg=dbg,
            commit_audit=commit_audit,
            updates=solver_final_updates,
            blocked_reason=blocked_reason,
            commit_eligible=False,
        ),
        "one_click_solve": solve,
        "one_click_solver_debug": dbg,
        "one_click_commit_audit": commit_audit,
        "trace_run_id": trace_run_id,
        "design_guide_tracer_path": tracer_path,
        "tracer_skip_reason": None,
        "tracer_entry_reached": True,
        **_uv_na,
    })


def _prepare_auto_design_post_solver_response_seed_coordinator(
    *,
    solve: dict,
) -> dict:
    solver_final_updates = dict(solve.get("final_updates") or {})
    stop_reason = str(solve.get("stop_reason") or "")
    return {
        "commit_audit": None,
        "solver_final_updates": solver_final_updates,
        "final_updates": solver_final_updates,
        "stop_reason": stop_reason,
        "solver_stop_reason": stop_reason,
        "commit_rejected": False,
        "commit_reject_reason": None,
        "commit_blocked_reason": None,
        "pre_commit_worst_util": None,
        "step_count": int(solve.get("step_count") or 0),
        "init_u": solve.get("initial_worst_util"),
        "fin_u": solve.get("final_worst_util"),
        "reached": bool(solve.get("reached_target_band")),
        "win_l": solve.get("winning_label"),
        "win_at": solve.get("winning_action_type"),
    }


def _dispatch_auto_design_commit_rejected_response_from_final_response_coordinator(
    *,
    final_response_scope: dict,
) -> dict:
    return _return_auto_design_commit_rejected_response_coordinator(
        commit_audit=final_response_scope["commit_audit_payload"],
        init_u=final_response_scope["init_u"],
        fin_u=final_response_scope["fin_u"],
        commit_reject_reason=final_response_scope["commit_reject_reason"],
        dbg=final_response_scope["dbg"],
        trace_run_id=final_response_scope["trace_run_id"],
        action_sig=final_response_scope["action_sig"],
        goal=final_response_scope["goal"],
        stop_reason=final_response_scope["stop_reason"],
        win_l=final_response_scope["win_l"],
        win_at=final_response_scope["win_at"],
        final_updates=final_response_scope["final_updates"],
        trace_src=final_response_scope["trace_src"],
        pre_commit_worst_util=final_response_scope["pre_commit_worst_util"],
        base_steps=final_response_scope["base_steps"],
        solver_final_updates=final_response_scope["solver_final_updates"],
        solve=final_response_scope["solve"],
        solver_stop_reason=final_response_scope["solver_stop_reason"],
        tracer_path=final_response_scope["tracer_path"],
        return_with_latch_clear=final_response_scope["return_with_latch_clear"],
    )


def _dispatch_auto_design_commit_blocked_response_from_final_response_coordinator(
    *,
    final_response_scope: dict,
) -> dict:
    return _return_auto_design_commit_blocked_response_coordinator(
        commit_audit=final_response_scope["commit_audit_payload"],
        init_u=final_response_scope["init_u"],
        fin_u=final_response_scope["fin_u"],
        commit_rejected=bool(final_response_scope["commit_rejected"]),
        commit_reject_reason=final_response_scope["commit_reject_reason"],
        commit_blocked_reason=final_response_scope["commit_blocked_reason"],
        dbg=final_response_scope["dbg"],
        trace_run_id=final_response_scope["trace_run_id"],
        action_sig=final_response_scope["action_sig"],
        goal=final_response_scope["goal"],
        stop_reason=final_response_scope["stop_reason"],
        win_l=final_response_scope["win_l"],
        win_at=final_response_scope["win_at"],
        final_updates=final_response_scope["final_updates"],
        trace_src=final_response_scope["trace_src"],
        pre_commit_worst_util=final_response_scope["pre_commit_worst_util"],
        base_steps=final_response_scope["base_steps"],
        solver_final_updates=final_response_scope["solver_final_updates"],
        solve=final_response_scope["solve"],
        solver_stop_reason=final_response_scope["solver_stop_reason"],
        tracer_path=final_response_scope["tracer_path"],
        return_with_latch_clear=final_response_scope["return_with_latch_clear"],
    )


def _dispatch_auto_design_blocked_status_response_from_final_response_coordinator(
    *,
    final_response_scope: dict,
) -> dict:
    return _return_auto_design_blocked_status_response_coordinator(
        commit_audit=final_response_scope["commit_audit_payload"],
        init_u=final_response_scope["init_u"],
        fin_u=final_response_scope["fin_u"],
        commit_rejected=bool(final_response_scope["commit_rejected"]),
        commit_reject_reason=final_response_scope["commit_reject_reason"],
        dbg=final_response_scope["dbg"],
        trace_run_id=final_response_scope["trace_run_id"],
        action_sig=final_response_scope["action_sig"],
        goal=final_response_scope["goal"],
        stop_reason=final_response_scope["stop_reason"],
        win_l=final_response_scope["win_l"],
        win_at=final_response_scope["win_at"],
        final_updates=final_response_scope["final_updates"],
        trace_src=final_response_scope["trace_src"],
        pre_commit_worst_util=final_response_scope["pre_commit_worst_util"],
        base_steps=final_response_scope["base_steps"],
        solver_final_updates=final_response_scope["solver_final_updates"],
        solve=final_response_scope["solve"],
        tracer_path=final_response_scope["tracer_path"],
        return_with_latch_clear=final_response_scope["return_with_latch_clear"],
    )


def _dispatch_auto_design_terminal_status_response_from_final_response_coordinator(
    *,
    final_response_scope: dict,
) -> dict:
    commit_audit_payload = final_response_scope["commit_audit_payload"]
    init_u = final_response_scope["init_u"]
    fin_u = final_response_scope["fin_u"]
    commit_rejected = bool(final_response_scope["commit_rejected"])
    commit_reject_reason = final_response_scope["commit_reject_reason"]
    commit_blocked_reason = final_response_scope["commit_blocked_reason"]
    dbg = final_response_scope["dbg"]
    trace_run_id = final_response_scope["trace_run_id"]
    action_sig = final_response_scope["action_sig"]
    goal = final_response_scope["goal"]
    stop_reason = final_response_scope["stop_reason"]
    win_l = final_response_scope["win_l"]
    win_at = final_response_scope["win_at"]
    final_updates = final_response_scope["final_updates"]
    trace_src = final_response_scope["trace_src"]
    pre_commit_worst_util = final_response_scope["pre_commit_worst_util"]
    base_steps = final_response_scope["base_steps"]
    solver_final_updates = final_response_scope["solver_final_updates"]
    solve = final_response_scope["solve"]
    tracer_path = final_response_scope["tracer_path"]
    return_with_latch_clear = final_response_scope["return_with_latch_clear"]
    out_status = final_response_scope["out_status"]
    if out_status == "failed":
        return _return_auto_design_failed_no_action_response_coordinator(
            commit_audit=commit_audit_payload,
            init_u=init_u,
            fin_u=fin_u,
            commit_rejected=commit_rejected,
            commit_reject_reason=commit_reject_reason,
            dbg=dbg,
            trace_run_id=trace_run_id,
            action_sig=action_sig,
            goal=goal,
            stop_reason=stop_reason,
            win_l=win_l,
            win_at=win_at,
            final_updates=final_updates,
            trace_src=trace_src,
            pre_commit_worst_util=pre_commit_worst_util,
            base_steps=base_steps,
            solver_final_updates=solver_final_updates,
            solve=solve,
            tracer_path=tracer_path,
            return_with_latch_clear=return_with_latch_clear,
        )
    if out_status == "no_action" and stop_reason == "already_in_band":
        return _return_auto_design_already_in_band_response_coordinator(
            commit_audit=commit_audit_payload,
            init_u=init_u,
            fin_u=fin_u,
            commit_rejected=commit_rejected,
            commit_reject_reason=commit_reject_reason,
            dbg=dbg,
            trace_run_id=trace_run_id,
            action_sig=action_sig,
            goal=goal,
            stop_reason=stop_reason,
            win_l=win_l,
            final_updates=final_updates,
            trace_src=trace_src,
            base_steps=base_steps,
            solve=solve,
            tracer_path=tracer_path,
            return_with_latch_clear=return_with_latch_clear,
        )
    if final_updates:
        return _return_auto_design_ready_response_coordinator(
            commit_audit=commit_audit_payload,
            init_u=init_u,
            fin_u=fin_u,
            commit_rejected=commit_rejected,
            commit_reject_reason=commit_reject_reason,
            dbg=dbg,
            trace_run_id=trace_run_id,
            action_sig=action_sig,
            goal=goal,
            stop_reason=stop_reason,
            win_l=win_l,
            final_updates=final_updates,
            trace_src=trace_src,
            base_steps=base_steps,
            solve=solve,
            tracer_path=tracer_path,
            return_with_latch_clear=return_with_latch_clear,
        )
    return _return_auto_design_default_no_action_response_coordinator(
        commit_audit=commit_audit_payload,
        init_u=init_u,
        fin_u=fin_u,
        commit_rejected=commit_rejected,
        commit_reject_reason=commit_reject_reason,
        commit_blocked_reason=commit_blocked_reason,
        dbg=dbg,
        trace_run_id=trace_run_id,
        action_sig=action_sig,
        goal=goal,
        stop_reason=stop_reason,
        win_l=win_l,
        win_at=win_at,
        final_updates=final_updates,
        trace_src=trace_src,
        pre_commit_worst_util=pre_commit_worst_util,
        base_steps=base_steps,
        solver_final_updates=solver_final_updates,
        solve=solve,
        tracer_path=tracer_path,
        return_with_latch_clear=return_with_latch_clear,
    )


def _dispatch_auto_design_final_response_coordinator(
    *,
    commit_audit: dict | None,
    init_u,
    fin_u,
    commit_rejected: bool,
    commit_reject_reason: str | None,
    commit_blocked_reason: str | None,
    dbg: dict,
    trace_run_id: str | None,
    action_sig,
    goal,
    stop_reason: str,
    win_l,
    win_at,
    final_updates: dict,
    trace_src,
    pre_commit_worst_util: float | None,
    base_steps: list,
    solver_final_updates: dict,
    solve: dict,
    solver_stop_reason: str,
    tracer_path: str | None,
    return_with_latch_clear,
) -> dict:
    commit_audit_payload = commit_audit if isinstance(commit_audit, dict) else None
    if commit_rejected:
        return _dispatch_auto_design_commit_rejected_response_from_final_response_coordinator(
            final_response_scope=locals(),
        )

    if commit_blocked_reason:
        return _dispatch_auto_design_commit_blocked_response_from_final_response_coordinator(
            final_response_scope=locals(),
        )

    out_status = str(solve.get("status") or "exhausted")
    if out_status == "blocked":
        return _dispatch_auto_design_blocked_status_response_from_final_response_coordinator(
            final_response_scope=locals(),
        )
    return _dispatch_auto_design_terminal_status_response_from_final_response_coordinator(
        final_response_scope=locals(),
    )


def _finish_auto_design_post_current_eval_and_dispatch_coordinator(
    *,
    stop_reason,
    step_count,
    init_u,
    fin_u,
    reached: bool,
    dbg: dict,
    win_l,
    solver_final_updates,
    commit_blocked_reason,
    commit_rejected: bool,
    commit_audit,
    commit_reject_reason,
    trace_run_id,
    action_sig,
    goal,
    win_at,
    final_updates,
    trace_src,
    pre_commit_worst_util,
    solve,
    solver_stop_reason,
    tracer_path,
    return_with_latch_clear,
) -> dict:
    post_current_eval_context = _prepare_auto_design_post_current_eval_response_context_coordinator(
        stop_reason=stop_reason,
        step_count=step_count,
        init_u=init_u,
        fin_u=fin_u,
        reached=reached,
        dbg=dbg,
        win_l=win_l,
        solver_final_updates=solver_final_updates,
        commit_blocked_reason=commit_blocked_reason,
        commit_rejected=bool(commit_rejected),
    )
    base_steps = post_current_eval_context["base_steps"]

    return _dispatch_auto_design_final_response_coordinator(
        commit_audit=commit_audit,
        init_u=init_u,
        fin_u=fin_u,
        commit_rejected=bool(commit_rejected),
        commit_reject_reason=commit_reject_reason,
        commit_blocked_reason=commit_blocked_reason,
        dbg=dbg,
        trace_run_id=trace_run_id,
        action_sig=action_sig,
        goal=goal,
        stop_reason=stop_reason,
        win_l=win_l,
        win_at=win_at,
        final_updates=final_updates,
        trace_src=trace_src,
        pre_commit_worst_util=pre_commit_worst_util,
        base_steps=base_steps,
        solver_final_updates=solver_final_updates,
        solve=solve,
        solver_stop_reason=solver_stop_reason,
        tracer_path=tracer_path,
        return_with_latch_clear=return_with_latch_clear,
    )


def _resolve_auto_design_final_candidate_partial_commit_orchestration_coordinator(
    *,
    solve,
    current_state: dict,
    final_updates,
    win_l,
    win_at,
    dbg: dict,
    solver_final_updates,
    trace_run_id,
    trace_src,
) -> dict:
    final_candidate_context = _prepare_auto_design_final_candidate_commit_context_coordinator(
        solve=solve,
        current_state=current_state,
        final_updates=final_updates,
        win_l=win_l,
        win_at=win_at,
        dbg=dbg,
    )
    dbg = final_candidate_context["dbg"]
    current_overview = final_candidate_context["current_overview"]
    candidate_for_commit = final_candidate_context["candidate_for_commit"]
    final_candidate_valid_for_commit = bool(
        final_candidate_context["final_candidate_valid_for_commit"]
    )
    final_candidate_commit_meta = final_candidate_context["final_candidate_commit_meta"]
    partial_commit_gate = _resolve_auto_design_partial_commit_gate_coordinator(
        solve=solve,
        current_state=current_state,
        current_overview=current_overview,
        candidate_for_commit=candidate_for_commit,
        final_candidate_valid_for_commit=final_candidate_valid_for_commit,
        final_candidate_commit_meta=final_candidate_commit_meta,
        solver_final_updates=solver_final_updates,
        final_updates=final_updates,
        dbg=dbg,
        win_l=win_l,
        win_at=win_at,
        trace_run_id=trace_run_id,
        trace_src=trace_src,
    )
    return {
        "dbg": partial_commit_gate["dbg"],
        "current_overview": current_overview,
        "final_updates": partial_commit_gate["final_updates"],
        "commit_blocked_reason": partial_commit_gate["commit_blocked_reason"],
    }


def _build_auto_design_commit_orchestration_result_state_coordinator(
    *,
    commit_orchestration_scope: dict,
) -> dict:
    return {
        "dbg": commit_orchestration_scope["dbg"],
        "final_updates": commit_orchestration_scope["final_updates"],
        "commit_blocked_reason": commit_orchestration_scope["commit_blocked_reason"],
        "pre_commit_worst_util": commit_orchestration_scope["pre_commit_worst_util"],
        "commit_audit": commit_orchestration_scope["commit_audit"],
        "commit_rejected": commit_orchestration_scope["commit_rejected"],
        "commit_reject_reason": commit_orchestration_scope["commit_reject_reason"],
        "stop_reason": commit_orchestration_scope["stop_reason"],
        "fin_u": commit_orchestration_scope["fin_u"],
        "reached": commit_orchestration_scope["reached"],
    }


def _dispatch_auto_design_final_candidate_partial_gate_from_commit_orchestration_coordinator(
    *,
    commit_orchestration_scope: dict,
) -> dict:
    return _resolve_auto_design_final_candidate_partial_commit_orchestration_coordinator(
        solve=commit_orchestration_scope["solve"],
        current_state=commit_orchestration_scope["current_state"],
        final_updates=commit_orchestration_scope["final_updates"],
        win_l=commit_orchestration_scope["win_l"],
        win_at=commit_orchestration_scope["win_at"],
        dbg=commit_orchestration_scope["dbg"],
        solver_final_updates=commit_orchestration_scope["solver_final_updates"],
        trace_run_id=commit_orchestration_scope["trace_run_id"],
        trace_src=commit_orchestration_scope["trace_src"],
    )


def _dispatch_auto_design_commit_start_from_commit_orchestration_coordinator(
    *,
    commit_orchestration_scope: dict,
) -> dict:
    return _prepare_auto_design_commit_start_coordinator(
        current_state=commit_orchestration_scope["current_state"],
        final_updates=commit_orchestration_scope["final_updates"],
        dbg=commit_orchestration_scope["dbg"],
        win_l=commit_orchestration_scope["win_l"],
        win_at=commit_orchestration_scope["win_at"],
        trace_run_id=commit_orchestration_scope["trace_run_id"],
        trace_src=commit_orchestration_scope["trace_src"],
    )


def _run_auto_design_commit_orchestration_coordinator(
    *,
    solve,
    current_state: dict,
    final_updates,
    win_l,
    win_at,
    dbg: dict,
    solver_final_updates,
    trace_run_id,
    trace_src,
    stop_reason,
    commit_blocked_reason,
    pre_commit_worst_util,
    commit_audit,
    commit_rejected: bool,
    commit_reject_reason,
    fin_u,
    reached: bool,
) -> dict:
    if final_updates:
        final_candidate_partial_gate = (
            _dispatch_auto_design_final_candidate_partial_gate_from_commit_orchestration_coordinator(
                commit_orchestration_scope=locals(),
            )
        )
        dbg = final_candidate_partial_gate["dbg"]
        current_overview = final_candidate_partial_gate["current_overview"]
        final_updates = final_candidate_partial_gate["final_updates"]
        commit_blocked_reason = final_candidate_partial_gate["commit_blocked_reason"]

    if final_updates:
        commit_start_context = (
            _dispatch_auto_design_commit_start_from_commit_orchestration_coordinator(
                commit_orchestration_scope=locals(),
            )
        )
        dbg = commit_start_context["dbg"]
        pre_commit_shared_state = commit_start_context["pre_commit_shared_state"]
        pre_commit_worst_util = commit_start_context["pre_commit_worst_util"]
        commit_mode_config = commit_start_context["commit_mode_config"]
        commit_write_setup = _apply_auto_design_commit_write_audit_setup_coordinator(
            final_updates=final_updates,
            dbg=dbg,
            stop_reason=stop_reason,
            current_overview=current_overview,
        )
        dbg = commit_write_setup["dbg"]
        commit_audit = commit_write_setup["commit_audit"]
        passes, rej_r = _one_click_commit_audit_passes(
            commit_audit,
            partial_progress_commit=bool(dbg.get("one_click_partial_progress_commit")),
            best_effort_cleanup_commit=bool(dbg.get("one_click_best_effort_cleanup_commit")),
            pre_commit_worst_util=pre_commit_worst_util,
            pre_commit_statuses=dict(current_overview.get("statuses") or {}),
        )
        if not passes:
            commit_reject_reason = rej_r
            commit_rejected_context = _handle_auto_design_commit_rejected_rollback_coordinator(
                commit_audit=commit_audit,
                commit_reject_reason=commit_reject_reason,
                dbg=dbg,
                pre_commit_shared_state=pre_commit_shared_state,
                pre_commit_worst_util=pre_commit_worst_util,
                solver_final_updates=solver_final_updates,
                trace_run_id=trace_run_id,
                trace_src=trace_src,
            )
            dbg = commit_rejected_context["dbg"]
            final_updates = commit_rejected_context["final_updates"]
            commit_rejected = bool(commit_rejected_context["commit_rejected"])
            commit_reject_reason = commit_rejected_context["commit_reject_reason"]
        else:
            commit_success_context = _handle_auto_design_commit_success_audit_setup_coordinator(
                commit_audit=commit_audit,
                final_updates=final_updates,
                dbg=dbg,
                trace_run_id=trace_run_id,
                trace_src=trace_src,
            )
            dbg = commit_success_context["dbg"]
            commit_audit = commit_success_context["commit_audit"]
            if bool(reached) and isinstance(commit_audit, dict):
                strict_post_commit_gate = _prepare_auto_design_strict_post_commit_gate_coordinator(
                    commit_mode_config=commit_mode_config,
                    dbg=dbg,
                )
                dbg = strict_post_commit_gate["dbg"]
                _strict_live_ok = bool(strict_post_commit_gate["strict_live_ok"])
                if not _strict_live_ok:
                    strict_followup_context = _handle_auto_design_strict_followup_commit_coordinator(
                        trace_run_id=trace_run_id,
                        dbg=dbg,
                        final_updates=final_updates,
                        commit_audit=commit_audit,
                        commit_mode_config=commit_mode_config,
                    )
                    dbg = strict_followup_context["dbg"]
                    final_updates = strict_followup_context["final_updates"]
                    commit_audit = strict_followup_context["commit_audit"]
            partial_followup_context = _handle_auto_design_partial_progress_followup_commit_coordinator(
                trace_run_id=trace_run_id,
                dbg=dbg,
                final_updates=final_updates,
                commit_audit=commit_audit,
                stop_reason=stop_reason,
                fin_u=fin_u,
                reached=reached,
            )
            dbg = partial_followup_context["dbg"]
            final_updates = partial_followup_context["final_updates"]
            commit_audit = partial_followup_context["commit_audit"]
            stop_reason = str(partial_followup_context["stop_reason"] or "")
            fin_u = partial_followup_context["fin_u"]
            reached = bool(partial_followup_context["reached"])

    return _build_auto_design_commit_orchestration_result_state_coordinator(
        commit_orchestration_scope=locals(),
    )


def _run_auto_design_post_solver_commit_orchestration_coordinator(
    *,
    solve: dict,
    current_state: dict,
    dbg: dict,
    trace_run_id,
    trace_src,
) -> dict:
    post_solver_response_seed = _prepare_auto_design_post_solver_response_seed_coordinator(solve=solve)
    commit_audit: dict | None = post_solver_response_seed["commit_audit"]
    solver_final_updates = post_solver_response_seed["solver_final_updates"]
    final_updates = post_solver_response_seed["final_updates"]
    stop_reason = post_solver_response_seed["stop_reason"]
    solver_stop_reason = post_solver_response_seed["solver_stop_reason"]
    commit_rejected = bool(post_solver_response_seed["commit_rejected"])
    commit_reject_reason: str | None = post_solver_response_seed["commit_reject_reason"]
    commit_blocked_reason: str | None = post_solver_response_seed["commit_blocked_reason"]
    pre_commit_worst_util: float | None = post_solver_response_seed["pre_commit_worst_util"]
    step_count = post_solver_response_seed["step_count"]
    init_u = post_solver_response_seed["init_u"]
    fin_u = post_solver_response_seed["fin_u"]
    reached = bool(post_solver_response_seed["reached"])
    win_l = post_solver_response_seed["win_l"]
    win_at = post_solver_response_seed["win_at"]
    commit_orchestration = _run_auto_design_commit_orchestration_coordinator(
        solve=solve,
        current_state=current_state,
        final_updates=final_updates,
        win_l=win_l,
        win_at=win_at,
        dbg=dbg,
        solver_final_updates=solver_final_updates,
        trace_run_id=trace_run_id,
        trace_src=trace_src,
        stop_reason=stop_reason,
        commit_blocked_reason=commit_blocked_reason,
        pre_commit_worst_util=pre_commit_worst_util,
        commit_audit=commit_audit,
        commit_rejected=bool(commit_rejected),
        commit_reject_reason=commit_reject_reason,
        fin_u=fin_u,
        reached=reached,
    )
    return {
        "dbg": commit_orchestration["dbg"],
        "final_updates": commit_orchestration["final_updates"],
        "commit_blocked_reason": commit_orchestration["commit_blocked_reason"],
        "pre_commit_worst_util": commit_orchestration["pre_commit_worst_util"],
        "commit_audit": commit_orchestration["commit_audit"],
        "commit_rejected": bool(commit_orchestration["commit_rejected"]),
        "commit_reject_reason": commit_orchestration["commit_reject_reason"],
        "stop_reason": str(commit_orchestration["stop_reason"] or ""),
        "fin_u": commit_orchestration["fin_u"],
        "reached": bool(commit_orchestration["reached"]),
        "step_count": step_count,
        "init_u": init_u,
        "win_l": win_l,
        "win_at": win_at,
        "solver_final_updates": solver_final_updates,
        "solver_stop_reason": solver_stop_reason,
    }


def _run_one_click_auto_design_solver_and_final_response_coordinator(
    *,
    auto_design_run_scope: dict,
) -> dict:
    current_state = auto_design_run_scope["current_state"]
    trace_run_id = auto_design_run_scope["trace_run_id"]
    tracer_path = auto_design_run_scope["tracer_path"]
    trace_src = auto_design_run_scope["trace_src"]
    raw_coherence = auto_design_run_scope["raw_coherence"]
    canonical_coherence = auto_design_run_scope["canonical_coherence"]
    canonical_pack_valid = auto_design_run_scope["canonical_pack_valid"]
    canonical_pack_error = auto_design_run_scope["canonical_pack_error"]
    canonical_pack_error_stage = auto_design_run_scope["canonical_pack_error_stage"]
    entry_source_norm = auto_design_run_scope["entry_source_norm"]
    solver_running_bypassed = auto_design_run_scope["_solver_running_bypassed"]
    feedback_cleared = auto_design_run_scope["_one_click_run_feedback_cleared_at_entry"]

    solve = _solve_one_click_to_target(
        current_state,
        max_steps=6,
        debug_enabled=False,
        trace_run_id=trace_run_id,
        trace_source="one_click_solve",
    )
    dbg = _build_auto_design_post_solver_debug_coordinator(
        solve=solve,
        trace_run_id=trace_run_id,
        tracer_path=tracer_path,
        raw_coherence=raw_coherence,
        current_state=current_state,
        canonical_coherence=canonical_coherence,
        canonical_pack_valid=canonical_pack_valid,
        canonical_pack_error=canonical_pack_error,
        canonical_pack_error_stage=canonical_pack_error_stage,
        entry_source_norm=entry_source_norm,
        solver_running_bypassed=solver_running_bypassed,
        one_click_run_feedback_cleared_at_entry=feedback_cleared,
    )
    post_solver_commit_state = _run_auto_design_post_solver_commit_orchestration_coordinator(
        solve=solve,
        current_state=current_state,
        dbg=dbg,
        trace_run_id=trace_run_id,
        trace_src=trace_src,
    )
    return _finish_auto_design_post_current_eval_and_dispatch_coordinator(
        stop_reason=post_solver_commit_state["stop_reason"],
        step_count=post_solver_commit_state["step_count"],
        init_u=post_solver_commit_state["init_u"],
        fin_u=post_solver_commit_state["fin_u"],
        reached=post_solver_commit_state["reached"],
        dbg=post_solver_commit_state["dbg"],
        win_l=post_solver_commit_state["win_l"],
        solver_final_updates=post_solver_commit_state["solver_final_updates"],
        commit_blocked_reason=post_solver_commit_state["commit_blocked_reason"],
        commit_rejected=bool(post_solver_commit_state["commit_rejected"]),
        commit_audit=post_solver_commit_state["commit_audit"],
        commit_reject_reason=post_solver_commit_state["commit_reject_reason"],
        trace_run_id=trace_run_id,
        action_sig=auto_design_run_scope["action_sig"],
        goal=auto_design_run_scope["goal"],
        win_at=post_solver_commit_state["win_at"],
        final_updates=post_solver_commit_state["final_updates"],
        trace_src=trace_src,
        pre_commit_worst_util=post_solver_commit_state["pre_commit_worst_util"],
        solve=solve,
        solver_stop_reason=post_solver_commit_state["solver_stop_reason"],
        tracer_path=tracer_path,
        return_with_latch_clear=auto_design_run_scope["_return_with_latch_clear"],
    )


def run_one_click_auto_design(
    *,
    trigger_fingerprint: tuple | None = None,
    entry_source: str = "inputs_handle_auto_design",
) -> dict:
    """Canonical public solver entry for one-click auto design (Inputs + Design Guide)."""
    run_entry_state = _start_one_click_auto_design_run_entry_coordinator(
        trigger_fingerprint=trigger_fingerprint,
        entry_source=entry_source,
    )
    trace_run_id = run_entry_state["trace_run_id"]
    tracer_path = run_entry_state["tracer_path"]
    trace_src = run_entry_state["trace_src"]
    entry_source_norm = run_entry_state["entry_source_norm"]

    stale_latch_entry_state = _resolve_auto_design_stale_latch_entry_state_coordinator(
        entry_source_norm=entry_source_norm,
    )
    auto_design_stale_latch_cleared_at_entry = bool(
        stale_latch_entry_state["auto_design_stale_latch_cleared_at_entry"]
    )
    auto_design_stale_latch_clear_reason = stale_latch_entry_state[
        "auto_design_stale_latch_clear_reason"
    ]

    def _return_with_latch_clear(reason: str, payload: dict) -> dict:
        return _return_with_latch_clear_coordinator(
            reason=reason,
            payload=payload,
            auto_design_stale_latch_cleared_at_entry=auto_design_stale_latch_cleared_at_entry,
            auto_design_stale_latch_clear_reason=auto_design_stale_latch_clear_reason,
        )

    skip_gate_state = _resolve_auto_design_run_skip_gate_coordinator(
        entry_source_norm=entry_source_norm,
    )
    _solver_running_bypassed = bool(skip_gate_state["solver_running_bypassed"])
    if skip_gate_state["skip_reason"]:
        return _trace_run_skipped_return_coordinator(
            skip_gate_state["skip_reason"],
            trace_run_id=trace_run_id,
            tracer_path=tracer_path,
            trace_src=trace_src,
            entry_source_norm=entry_source_norm,
            trigger_fingerprint=trigger_fingerprint,
            return_with_latch_clear=_return_with_latch_clear,
        )
    run_state = _prepare_one_click_auto_design_run_state_coordinator(
        trigger_fingerprint=trigger_fingerprint,
        trace_run_id=trace_run_id,
        tracer_path=tracer_path,
        trace_src=trace_src,
        entry_source_norm=entry_source_norm,
        solver_running_bypassed=_solver_running_bypassed,
    )
    _one_click_run_feedback_cleared_at_entry = bool(run_state["one_click_run_feedback_cleared_at_entry"])
    raw_coherence = run_state["raw_coherence"]
    current_state = run_state["current_state"]
    canonical_coherence = run_state["canonical_coherence"]
    canonical_pack_valid = bool(run_state["canonical_pack_valid"])
    canonical_pack_error = run_state["canonical_pack_error"]
    canonical_pack_error_stage = run_state["canonical_pack_error_stage"]
    goal = run_state["goal"]
    action_sig = run_state["action_sig"]
    _pack_invalid_block = bool(run_state["pack_invalid_block"])

    if _pack_invalid_block:
        return _handle_auto_design_blocked_incoherent_state_coordinator(
            current_state=current_state,
            raw_coherence=raw_coherence,
            canonical_coherence=canonical_coherence,
            canonical_pack_valid=canonical_pack_valid,
            canonical_pack_error=canonical_pack_error,
            canonical_pack_error_stage=canonical_pack_error_stage,
            trace_run_id=trace_run_id,
            tracer_path=tracer_path,
            trace_src=trace_src,
            entry_source_norm=entry_source_norm,
            solver_running_bypassed=_solver_running_bypassed,
            one_click_run_feedback_cleared_at_entry=_one_click_run_feedback_cleared_at_entry,
            return_with_latch_clear=_return_with_latch_clear,
        )

    return _run_one_click_auto_design_solver_and_final_response_coordinator(
        auto_design_run_scope=locals(),
    )
