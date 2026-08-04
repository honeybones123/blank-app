"""Design Guide panel sub-coordinators for the Inputs shell.

These functions preserve the existing panel sequencing behavior while keeping
the physical wrapper layer outside the old page. The ``current_owner`` argument
is the temporary boundary for the remaining current-coordinator layer.
"""

from __future__ import annotations

import time
from typing import Any


def render_design_guide_panel_entry_trace_and_stage_coordinator(**kwargs):
    _ = kwargs
    return time.perf_counter(), lambda _label: None


def render_design_guide_initial_state_and_loading_coordinator(
    *,
    current_owner: Any,
    inputs_render_audit: dict[str, str] | None = None,
):
    _dg_initial = current_owner.render_design_guide_initial_cache_compute_current_coordinator(
        inputs_render_audit=inputs_render_audit,
    )
    current_state = dict(_dg_initial["current_state"])
    fingerprint = _dg_initial["fingerprint"]
    sidebar_debug = bool(_dg_initial["sidebar_debug"])
    return current_state, fingerprint, sidebar_debug, {"_dg_initial": _dg_initial}, False, False


def render_design_guide_compute_preparation_coordinator(
    *,
    settle_gate_decision: dict,
    current_state: dict,
    fingerprint,
):
    _ = fingerprint
    _dg_initial = dict(settle_gate_decision.get("_dg_initial") or {})
    if not _dg_initial:
        return [], {}, False, False, False, False, False, False, False, current_state, 0.0, True
    banner_generic_only = bool(_dg_initial["banner_generic_only"])
    guidance_items_raw = list(_dg_initial["guidance_items_raw"] or [])
    guidance_debug = dict(_dg_initial["guidance_debug"] or {})
    guidance_cache_hit = bool(_dg_initial["guidance_cache_hit"])
    guidance_fresh_compute_used = bool(_dg_initial["guidance_fresh_compute_used"])
    guidance_compute_ms = _dg_initial["guidance_compute_ms"]
    guidance_disp_state = dict(_dg_initial["guidance_disp_state"] or current_state)
    return (
        guidance_items_raw,
        guidance_debug,
        banner_generic_only,
        guidance_cache_hit,
        guidance_fresh_compute_used,
        False,
        False,
        False,
        False,
        guidance_disp_state,
        guidance_compute_ms,
        False,
    )


def render_design_guide_postprocess_pre_render_plan_coordinator(
    *,
    current_owner: Any,
    guidance_items_raw: list[dict],
    guidance_debug: dict,
    guidance_disp_state: dict,
    current_state: dict,
    fingerprint,
    fast_focus_section: str | None,
    guidance_fresh_compute_used: bool,
    sidebar_debug: bool,
    _stage,
):
    _item_postprocess = current_owner.render_design_guide_item_postprocess_current_coordinator(
        guidance_items_raw=guidance_items_raw,
        guidance_disp_state=guidance_disp_state,
        guidance_debug=guidance_debug,
        _stage=_stage,
    )
    guidance_items = list(_item_postprocess["guidance_items"] or [])
    guidance_dedupe_meta = dict(_item_postprocess["guidance_dedupe_meta"] or {})
    collapse_meta = dict(_item_postprocess["collapse_meta"] or {})
    _branch_for_rr = _item_postprocess["_branch_for_rr"]
    _recommendation_result = _item_postprocess["_recommendation_result"]
    redundancy_meta = dict(_item_postprocess["redundancy_meta"] or {})
    _ = dict(_item_postprocess["family_suppression_meta"] or {})
    _render_coherence_result = current_owner.render_design_guide_render_coherence_current_coordinator(
        current_state=current_state,
        guidance_debug=guidance_debug,
        guidance_items=guidance_items,
        guidance_disp_state=guidance_disp_state,
        _recommendation_result=_recommendation_result,
        _branch_for_rr=_branch_for_rr,
        _stage=_stage,
    )
    guidance_items = list(_render_coherence_result["guidance_items"] or [])
    guidance_disp_state = dict(_render_coherence_result["guidance_disp_state"] or {})
    _recommendation_result = _render_coherence_result["_recommendation_result"]
    _render_coherence_repairs = list(_render_coherence_result["_render_coherence_repairs"] or [])
    _render_coherence_needed = bool(_render_coherence_result["_render_coherence_needed"])
    _render_plan_result = current_owner.render_design_guide_render_plan_current_coordinator(
        guidance_debug=guidance_debug,
        guidance_items=guidance_items,
        guidance_disp_state=guidance_disp_state,
        _recommendation_result=_recommendation_result,
        collapse_meta=collapse_meta,
        redundancy_meta=redundancy_meta,
        fingerprint=fingerprint,
        fast_focus_section=fast_focus_section,
        guidance_fresh_compute_used=guidance_fresh_compute_used,
        sidebar_debug=sidebar_debug,
        _render_coherence_repairs=_render_coherence_repairs,
        _render_coherence_needed=_render_coherence_needed,
        _stage=_stage,
    )
    if bool(_render_plan_result.get("early_return")):
        return (
            guidance_items,
            guidance_debug,
            guidance_disp_state,
            guidance_dedupe_meta,
            _render_plan_result.get("_recommendation_result"),
            _render_plan_result.get("terminal_state"),
            str(_render_plan_result.get("terminal_state_source") or ""),
            _render_plan_result.get("pending_recommendation"),
            dict(_render_plan_result.get("render_plan") or {}),
            bool(_render_plan_result.get("render_post_apply_banner")),
            True,
        )
    terminal_state = _render_plan_result["terminal_state"]
    terminal_state_source = str(_render_plan_result["terminal_state_source"] or "")
    pending_recommendation = _render_plan_result["pending_recommendation"]
    render_plan = dict(_render_plan_result["render_plan"] or {})
    render_post_apply_banner = bool(_render_plan_result["render_post_apply_banner"])
    _recommendation_result = _render_plan_result["_recommendation_result"]
    return (
        guidance_items,
        guidance_debug,
        guidance_disp_state,
        guidance_dedupe_meta,
        _recommendation_result,
        terminal_state,
        terminal_state_source,
        pending_recommendation,
        render_plan,
        render_post_apply_banner,
        False,
    )


def render_design_guide_active_guard_presentation_engine_coordinator(
    *,
    current_owner: Any,
    current_state: dict,
    guidance_debug: dict,
    guidance_items: list[dict],
    guidance_disp_state: dict,
    terminal_state,
    terminal_state_source: str,
    pending_recommendation,
    render_plan: dict,
    sidebar_debug: bool,
    guidance_compute_ms,
    guidance_cache_hit: bool,
    banner_generic_only: bool,
    fast_focus_section: str | None,
    guidance_dedupe_meta: dict,
    _recommendation_result,
):
    active_timings_ms: dict[str, float] = {}
    active_started = time.perf_counter()
    _debug_bundle_result = current_owner.render_design_guide_debug_bundle_current_coordinator(
        current_state=current_state,
        guidance_debug=guidance_debug,
        guidance_items=guidance_items,
        guidance_disp_state=guidance_disp_state,
        terminal_state=terminal_state,
        render_plan=render_plan,
        sidebar_debug=sidebar_debug,
        guidance_compute_ms=guidance_compute_ms,
        guidance_cache_hit=guidance_cache_hit,
        banner_generic_only=banner_generic_only,
        fast_focus_section=fast_focus_section,
        guidance_dedupe_meta=guidance_dedupe_meta,
        _recommendation_result=_recommendation_result,
    )
    active_timings_ms["debug_bundle"] = round(
        (time.perf_counter() - active_started) * 1000,
        3,
    )
    efficiency_state = dict(_debug_bundle_result.get("efficiency_state") or {})
    active_started = time.perf_counter()
    _presentation_local_cleanup = current_owner.render_design_guide_presentation_local_cleanup_current_coordinator(
        guidance_debug=guidance_debug,
        guidance_items=guidance_items,
        guidance_disp_state=guidance_disp_state,
        efficiency_state=efficiency_state,
        terminal_state=terminal_state,
        terminal_state_source=terminal_state_source,
        _recommendation_result=_recommendation_result,
        pending_recommendation=pending_recommendation,
    )
    active_timings_ms["presentation_local_cleanup"] = round(
        (time.perf_counter() - active_started) * 1000,
        3,
    )
    _dg_overview = _presentation_local_cleanup["_dg_overview"]
    _dg_presentation = dict(_presentation_local_cleanup["_dg_presentation"] or {})
    terminal_state = _presentation_local_cleanup["terminal_state"]
    terminal_state_source = str(_presentation_local_cleanup["terminal_state_source"] or "")
    guidance_items = list(_presentation_local_cleanup["guidance_items"] or [])
    _recommendation_result = _presentation_local_cleanup["_recommendation_result"]
    active_started = time.perf_counter()
    current_owner.render_design_guide_feedback_cta_current_coordinator(
        _dg_overview=_dg_overview,
        guidance_debug=guidance_debug,
    )
    active_timings_ms["feedback_cta"] = round(
        (time.perf_counter() - active_started) * 1000,
        3,
    )
    current_owner.st.session_state[
        "_inputs_design_guide_active_stage_timings_ms"
    ] = active_timings_ms
    return (
        guidance_items,
        guidance_debug,
        [],
        terminal_state,
        terminal_state_source,
        _recommendation_result,
        _dg_overview,
        {},
        False,
        {},
        _dg_presentation,
        {},
    )


def render_design_guide_presentation_post_cleanup_gate_coordinator(
    *,
    guidance_items: list[dict],
    dg_presentation: dict,
    recommendation_result,
    guidance_debug: dict,
    terminal_state,
    terminal_state_source: str,
    dg_overview,
):
    _ = dg_overview
    return (
        guidance_items,
        dg_presentation,
        recommendation_result,
        guidance_debug,
        terminal_state,
        terminal_state_source,
        False,
        {},
        False,
    )


def render_design_guide_post_cleanup_publication_pre_render_coordinator(
    *,
    guidance_items: list[dict],
    terminal_state,
    terminal_state_source: str,
    dg_overview,
    dg_presentation: dict,
    render_plan: dict,
    guidance_debug: dict,
    post_cleanup_render_audit: dict,
):
    _ = post_cleanup_render_audit
    return (
        False,
        [],
        guidance_items,
        terminal_state,
        terminal_state_source,
        dg_overview,
        dg_presentation,
        render_plan,
        {},
        None,
        [],
        {},
        {},
        {},
        None,
        {},
        {},
        False,
        False,
        guidance_debug,
    )


def render_design_guide_final_render_branch_dispatch_coordinator(
    *,
    current_owner: Any,
    final_visible_resolution,
    terminal_state_current_in_target: bool,
    guidance_debug: dict,
    render_plan: dict,
    dg_presentation: dict,
    fingerprint,
    guidance_items_raw: list[dict],
    guidance_disp_state: dict,
    dg_overview,
    inputs_render_audit: dict[str, str] | None,
    terminal_state,
    guidance_items: list[dict],
    render_post_apply_banner: bool,
    fast_focus_section: str | None,
):
    _ = final_visible_resolution
    _ = terminal_state_current_in_target
    current_owner.render_design_guide_final_render_current_coordinator(
        guidance_debug=guidance_debug,
        _dg_presentation=dg_presentation,
        fingerprint=fingerprint,
        guidance_items_raw=guidance_items_raw,
        guidance_disp_state=guidance_disp_state,
        _dg_overview=dg_overview,
        inputs_render_audit=inputs_render_audit,
        terminal_state=terminal_state,
        guidance_items=guidance_items,
        render_plan=render_plan,
        render_post_apply_banner=render_post_apply_banner,
        fast_focus_section=fast_focus_section,
    )
    current_owner.render_design_guide_publication_exit_state_current_coordinator()
    return guidance_debug, render_plan, dg_presentation, terminal_state, {}, guidance_items


def render_design_guide_panel_exit_state(**kwargs) -> None:
    _ = kwargs
