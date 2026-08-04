"""Application-owned resolved Inputs summary-state transaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, MutableMapping

from inputs_application.candidate_metrics import candidate_bottom_updates
from inputs_application.recommendation_evaluation import (
    effective_bottom_design_state,
)
from inputs_page_modules.design_overview_adapter import (
    build_design_actions_context,
)
from inputs_page_modules.session import (
    build_inputs_design_action_result_overlay_snapshot,
    build_inputs_normalized_shear_truth_overlay_snapshot,
    build_inputs_shear_widget_mirror_overlay_plan,
    build_inputs_summary_debug_payload_snapshot,
    build_inputs_summary_shared_only_decision,
    build_inputs_summary_source_shaping_snapshot,
    build_inputs_summary_state_mode_marker_snapshot,
)
from state_and_helpers import (
    TAB_KEYS,
    build_legacy_longitudinal_mirrors_from_rows,
    normalize_final_published_shear_truth,
    stable_fingerprint_for_payload,
)


INPUTS_PAGE_TAB_KEYS = {
    shared_key: widget_key
    for widget_key, shared_key in TAB_KEYS.items()
    if str(widget_key).startswith("inputs_")
}
SUMMARY_OVERLAY_SKIP_SHARED_KEYS = (
    "results_version",
    "pending_recommendation",
    "_solver_result",
    "_bend_pack",
    "_shear_pack",
    "_crack_pack",
    "_defl_pack",
    "_summary_cache_version",
    "_summary_cache_action_fp",
)
SUMMARY_OVERLAY_SKIP_LONGITUDINAL_KEYS = (
    "bot_row_count", "top_row_count", "bot1_layout_mode", "bot1_count",
    "bot1_spacing", "db_bot_1", "bot2_layout_mode", "bot2_count",
    "bot2_spacing", "db_bot_2", "top1_layout_mode", "top1_count",
    "top1_spacing", "db_top_1", "top2_layout_mode", "top2_count",
    "top2_spacing", "db_top_2",
)
SUMMARY_OVERLAY_SKIP_PREFIXES = ("bot_row_", "top_row_")
SHEAR_TRIPLE_DEFERRED_OVERLAY_KEYS = ("s_lig", "lig_d", "lig_legs")
SUMMARY_DESIGN_ACTION_RESULT_KEYS = (
    "Mu_star", "Mu_star_kNm", "Mu_star_kNm_signed", "Vu_star",
    "sfd_Mmax_abs_kNm", "sfd_Vmax_abs_kN", "M_pos_max_uls_kNm",
    "M_neg_min_uls_kNm", "M_pos_max_sls_kNm", "M_neg_min_sls_kNm",
    "sfd_Msls_max_kNm", "sfd_Vsls_max_kN",
)
CURRENT_SHEAR_TRUTH_SESSION_KEYS = (
    "shear_design_status", "shear_envelope_status", "shear_truth_status",
    "shear_truth_reason", "shear_truth_util_governing",
    "shear_truth_web_util_governing", "shear_truth_util_source",
    "shear_truth_web_util_source", "shear_truth_governing_check_name",
    "shear_truth_governing_reason", "shear_truth_governing_source",
    "shear_util_governing", "shear_util_min", "final_shear_status_source",
    "final_shear_truth_resolved", "final_shear_truth_failure_reason",
    "final_shear_spacing_reason", "final_shear_publication_path",
    "final_shear_truth_bundle_complete", "shear_required_spacing_mm",
    "shear_effective_spacing_mm", "shear_governing_spacing_source",
    "published_result_spacing_mm", "published_result_spacing_meaning",
    "shear_provided_input_spacing_mm", "shear_input_spacing_mm",
    "shear_sectional_check_spacing_mm", "V_eq_kN", "Vu_star", "uls_Vstar",
    "load_Vstar_proxy", "shear_Vu_total_kN", "phi_Vu_cap",
    "phi_Vu_max_kN", "phiVu_max", "phi_vu_max",
)


@dataclass(frozen=True)
class InputsSummaryStateRuntime:
    design_guide_fingerprint: Callable[[dict], Any]
    guidance_state_snapshot: Callable[[dict], dict]
    session_state: MutableMapping[str, Any]
    shared_state_snapshot: Callable[[], dict]
    ux_probe_record: Callable[..., Any]


def _recompute_local_fields(state: dict) -> dict:
    working = dict(state or {})
    working.update(build_legacy_longitudinal_mirrors_from_rows(working))
    context = build_design_actions_context(working)
    resolved = dict(context.get("state") or working)
    resolved.update(build_legacy_longitudinal_mirrors_from_rows(resolved))
    bottom = effective_bottom_design_state(
        resolved,
        candidate_bottom_updates(resolved),
    )
    if float(bottom.get("d_centroid", 0.0) or 0.0) > 0.0:
        resolved["d"] = float(bottom["d_centroid"])
    if int(bottom.get("nb_bot", 0) or 0) > 0 and float(
        bottom.get("db_bot", 0.0) or 0.0
    ) > 0.0:
        resolved.update(
            {
                "Ast_bot": float(bottom["Ast_bot"]),
                "db_bot": float(bottom["db_bot"]),
                "nb_bot": int(bottom["nb_bot"]),
            }
        )
    resolved.update(build_legacy_longitudinal_mirrors_from_rows(resolved))
    return resolved


def _overlay_normalized_shear_truth(
    state: dict,
    session_state: MutableMapping[str, Any],
) -> dict:
    base = dict(state or {})
    session_overlay = {
        key: session_state.get(key)
        for key in CURRENT_SHEAR_TRUTH_SESSION_KEYS
        if key in session_state
    }
    normalized = normalize_final_published_shear_truth(
        {**base, **session_overlay}
    )
    snapshot = build_inputs_normalized_shear_truth_overlay_snapshot(
        base_state=base,
        session_shear_truth_values=session_overlay,
        normalized_shear_truth_values=normalized,
    )
    return dict(snapshot.merged_state)


def resolve_design_guide_lightweight_state(
    runtime: InputsSummaryStateRuntime,
    incoming: dict | None,
) -> dict:
    """Resolve the Design Guide state without the deep canonical reo pack."""
    session = runtime.session_state
    baseline = runtime.guidance_state_snapshot(runtime.shared_state_snapshot())
    raw = runtime.guidance_state_snapshot(dict(incoming or {}))
    working = dict(raw)
    working.update(build_legacy_longitudinal_mirrors_from_rows(working))

    decision = build_inputs_summary_shared_only_decision(
        applying_auto_design=bool(session.get("_applying_auto_design")),
        force_inputs_widget_reseed_once=bool(
            session.get("_force_inputs_widget_reseed_once")
        ),
        pending_inputs_apply_refresh=bool(
            session.get("_pending_inputs_apply_refresh")
        ),
        inputs_longitudinal_reo_force_refresh_processed_this_run=bool(
            session.get(
                "_inputs_longitudinal_reo_force_refresh_processed_this_run"
            )
        ),
    )
    if not bool(decision.shared_only_mode):
        overlay_plan = build_inputs_shear_widget_mirror_overlay_plan(
            page_slug=str(session.get("page_slug") or ""),
            base_state=baseline,
            working_state=working,
            overlay_applied={},
            widget_state=session,
        )
        working = dict(overlay_plan.working_state)

    resolved = _recompute_local_fields(working)
    resolved.update(build_legacy_longitudinal_mirrors_from_rows(resolved))
    for proof_key in (
        "exact_stop_available",
        "exact_stop_proven",
        "exact_stop_proof",
        "locked_no_repair",
        "locked_repair_blocked",
        "all_repair_paths_locked",
        "repair_blocked_by_lock",
        "no_valid_repair_available",
        "repair_required",
        "reinforcement_lock",
        "reo_locked",
        "shear_lock",
        "geometry_lock",
    ):
        if proof_key in raw:
            resolved[proof_key] = raw.get(proof_key)
        elif proof_key in session:
            resolved[proof_key] = session.get(proof_key)
    return _overlay_normalized_shear_truth(resolved, session)


def resolve_inputs_summary_state(
    runtime: InputsSummaryStateRuntime,
) -> tuple[dict, dict]:
    session = runtime.session_state
    base = runtime.guidance_state_snapshot(runtime.shared_state_snapshot())
    decision = build_inputs_summary_shared_only_decision(
        applying_auto_design=bool(session.get("_applying_auto_design")),
        force_inputs_widget_reseed_once=bool(
            session.get("_force_inputs_widget_reseed_once")
        ),
        pending_inputs_apply_refresh=bool(
            session.get("_pending_inputs_apply_refresh")
        ),
        inputs_longitudinal_reo_force_refresh_processed_this_run=bool(
            session.get(
                "_inputs_longitudinal_reo_force_refresh_processed_this_run"
            )
        ),
    )
    shared_only_mode = bool(decision.shared_only_mode)
    shared_only_reason = str(decision.reason)
    shaped = build_inputs_summary_source_shaping_snapshot(
        base_state=base,
        source_state=session,
        input_tab_keys=INPUTS_PAGE_TAB_KEYS,
        skip_shared_keys=SUMMARY_OVERLAY_SKIP_SHARED_KEYS,
        skip_longitudinal_keys=SUMMARY_OVERLAY_SKIP_LONGITUDINAL_KEYS,
        skip_prefixes=SUMMARY_OVERLAY_SKIP_PREFIXES,
        deferred_overlay_keys=SHEAR_TRIPLE_DEFERRED_OVERLAY_KEYS,
        shared_only_mode=shared_only_mode,
        shared_only_reason=shared_only_reason,
    )
    working = dict(shaped.working_state)
    overlay_applied = dict(shaped.overlay_applied)
    runtime.ux_probe_record(
        "inputs_summary_source_shaping_delegated",
        meta={"module_display_hash": shaped.display_hash, "live_page_cutover": True},
    )
    if shared_only_mode:
        shear_debug = {
            "shear_widget_overlay_applied": False,
            "shear_widget_overlay_source": "shared_only_suppressed",
            "overlay_s_lig": working.get("s_lig"),
            "overlay_lig_d": working.get("lig_d"),
            "overlay_lig_legs": working.get("lig_legs"),
        }
    else:
        shear_plan = build_inputs_shear_widget_mirror_overlay_plan(
            page_slug=str(session.get("page_slug") or ""),
            base_state=base,
            working_state=working,
            overlay_applied=overlay_applied,
            widget_state=session,
        )
        working = dict(shear_plan.working_state)
        overlay_applied = dict(shear_plan.overlay_applied)
        shear_debug = dict(shear_plan.debug_payload)
    action_overlay = build_inputs_design_action_result_overlay_snapshot(
        working_state=working,
        source_state=session,
        result_keys=SUMMARY_DESIGN_ACTION_RESULT_KEYS,
        overlay_applied=overlay_applied,
    )
    working = dict(action_overlay.working_state)
    overlay_applied = dict(action_overlay.overlay_applied)
    design_action_overlay = dict(action_overlay.result_overlay)
    runtime.ux_probe_record(
        "inputs_summary_design_action_result_overlay_delegated",
        meta={
            "overlay_count": len(design_action_overlay),
            "module_display_hash": action_overlay.display_hash,
            "live_page_cutover": True,
        },
    )
    working.update(build_legacy_longitudinal_mirrors_from_rows(working))
    resolved = _overlay_normalized_shear_truth(
        _recompute_local_fields(working),
        session,
    )
    subset_keys = (
        "b", "D", "fc", "fsy", "uls_Mstar", "Mu_star", "uls_Vstar",
        "Vu_star", "Tu_star", "bot1_count", "bot2_count", "db_bot_1",
        "db_bot_2", "lig_d", "lig_legs", "s_lig", "Ast_bot", "d",
    )
    debug_snapshot = build_inputs_summary_debug_payload_snapshot(
        base_state=base,
        resolved_state=resolved,
        overlay_applied=overlay_applied,
        shear_overlay_debug=shear_debug,
        design_action_result_overlay=design_action_overlay,
        shared_only_mode=shared_only_mode,
        shared_only_reason=shared_only_reason,
        design_guide_fingerprint=runtime.design_guide_fingerprint(resolved),
        subset_keys=subset_keys,
    )
    debug = dict(debug_snapshot.debug_payload)
    debug["summary_design_action_result_overlay_count"] = len(
        design_action_overlay
    )
    debug["summary_design_action_result_overlay_keys"] = list(
        design_action_overlay
    )
    debug["row_model_legacy_sync_applied"] = bool(
        resolved.get("row_model_legacy_sync_applied")
    )
    debug["row_model_legacy_sync_diff_keys"] = list(
        resolved.get("row_model_legacy_sync_diff_keys") or []
    )
    runtime.ux_probe_record(
        "inputs_summary_debug_payload_delegated",
        meta={
            "module_display_hash": debug_snapshot.display_hash,
            "live_page_cutover": True,
        },
    )
    marker = build_inputs_summary_state_mode_marker_snapshot(
        base_state=base,
        widget_shear_state={
            "inputs_s_lig": session.get("inputs_s_lig"),
            "inputs_lig_d": session.get("inputs_lig_d"),
            "inputs_lig_legs": session.get("inputs_lig_legs"),
        },
        shared_only_mode=shared_only_mode,
        shared_only_reason=shared_only_reason,
        overlay_count=len(overlay_applied),
    )
    session["_inputs_summary_state_mode"] = dict(marker.marker_payload)
    runtime.ux_probe_record(
        "inputs_summary_state_mode_marker_delegated",
        meta={"module_display_hash": marker.display_hash, "live_page_cutover": True},
    )
    runtime.ux_probe_record(
        "inputs_page.summary_state_build",
        fingerprint=stable_fingerprint_for_payload(resolved),
        meta={
            "shared_only_mode": shared_only_mode,
            "overlay_count": len(overlay_applied),
        },
    )
    return resolved, debug


__all__ = ["InputsSummaryStateRuntime", "resolve_inputs_summary_state"]
