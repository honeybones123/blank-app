"""Design Guide panel orchestration coordinator for the Inputs shell."""

from __future__ import annotations

import time
from typing import Any

from . import panel_coordinators


def render_design_guide_panel_orchestration(
    *,
    current_owner: Any,
    sync_callbacks: dict | None = None,
    inputs_render_audit: dict[str, str] | None = None,
    fast_focus_section: str | None = None,
) -> None:
    """Sequence existing Design Guide sub-coordinators without owning logic."""

    _ = sync_callbacks
    stage_timings_ms: dict[str, float] = {}

    def _timed(name: str, started: float) -> None:
        stage_timings_ms[name] = round(
            (time.perf_counter() - started) * 1000,
            3,
        )

    def _publish_timings() -> None:
        st_module = getattr(current_owner, "st", None)
        if st_module is not None:
            st_module.session_state[
                "_inputs_design_guide_stage_timings_ms"
            ] = dict(stage_timings_ms)

    _started_at, _mark_stage = panel_coordinators.render_design_guide_panel_entry_trace_and_stage_coordinator(
        inputs_render_audit=inputs_render_audit,
        fast_focus_section=fast_focus_section,
    )
    _ = _started_at
    _ = _mark_stage
    stage_started = time.perf_counter()
    (
        current_state,
        fingerprint,
        sidebar_debug,
        settle_gate_decision,
        loading_rendered,
        terminal_state_current_in_target,
    ) = panel_coordinators.render_design_guide_initial_state_and_loading_coordinator(
        current_owner=current_owner,
        inputs_render_audit=inputs_render_audit,
    )
    _timed("initial", stage_started)
    if loading_rendered:
        _publish_timings()
        return
    stage_started = time.perf_counter()
    (
        guidance_items_raw,
        guidance_debug,
        banner_generic_only,
        guidance_cache_hit,
        guidance_fresh_compute_used,
        _,
        _,
        _,
        _,
        guidance_disp_state,
        guidance_compute_ms,
        fast_terminal_rendered,
    ) = panel_coordinators.render_design_guide_compute_preparation_coordinator(
        settle_gate_decision=settle_gate_decision,
        current_state=current_state,
        fingerprint=fingerprint,
    )
    _timed("compute_preparation", stage_started)
    if fast_terminal_rendered:
        _publish_timings()
        return
    _stage = (settle_gate_decision.get("_dg_initial") or {}).get("stage")
    stage_started = time.perf_counter()
    (
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
        not_started_rendered,
    ) = panel_coordinators.render_design_guide_postprocess_pre_render_plan_coordinator(
        current_owner=current_owner,
        guidance_items_raw=guidance_items_raw,
        guidance_debug=guidance_debug,
        guidance_disp_state=guidance_disp_state,
        current_state=current_state,
        fingerprint=fingerprint,
        fast_focus_section=fast_focus_section,
        guidance_fresh_compute_used=guidance_fresh_compute_used,
        sidebar_debug=sidebar_debug,
        _stage=_stage,
    )
    _timed("postprocess_render_plan", stage_started)
    if not_started_rendered:
        _publish_timings()
        return
    stage_started = time.perf_counter()
    (
        guidance_items,
        guidance_debug,
        _,
        terminal_state,
        terminal_state_source,
        _recommendation_result,
        dg_overview,
        mode_cfg,
        terminal_state_current_in_target,
        dg_engine_decision,
        dg_presentation,
        presentation_utils,
    ) = panel_coordinators.render_design_guide_active_guard_presentation_engine_coordinator(
        current_owner=current_owner,
        current_state=current_state,
        guidance_debug=guidance_debug,
        guidance_items=guidance_items,
        guidance_disp_state=guidance_disp_state,
        terminal_state=terminal_state,
        terminal_state_source=terminal_state_source,
        pending_recommendation=pending_recommendation,
        render_plan=render_plan,
        sidebar_debug=sidebar_debug,
        guidance_compute_ms=guidance_compute_ms,
        guidance_cache_hit=guidance_cache_hit,
        banner_generic_only=banner_generic_only,
        fast_focus_section=fast_focus_section,
        guidance_dedupe_meta=guidance_dedupe_meta,
        _recommendation_result=_recommendation_result,
    )
    _timed("active_guard_presentation", stage_started)
    _ = mode_cfg
    _ = dg_engine_decision
    _ = presentation_utils
    stage_started = time.perf_counter()
    (
        guidance_items,
        dg_presentation,
        _recommendation_result,
        guidance_debug,
        terminal_state,
        terminal_state_source,
        terminal_state_current_in_target,
        post_cleanup_render_audit,
        early_shear_return,
    ) = panel_coordinators.render_design_guide_presentation_post_cleanup_gate_coordinator(
        guidance_items=guidance_items,
        dg_presentation=dg_presentation,
        recommendation_result=_recommendation_result,
        guidance_debug=guidance_debug,
        terminal_state=terminal_state,
        terminal_state_source=terminal_state_source,
        dg_overview=dg_overview,
    )
    _timed("post_cleanup_gate", stage_started)
    if early_shear_return:
        _publish_timings()
        return
    stage_started = time.perf_counter()
    (
        _,
        _,
        guidance_items,
        terminal_state,
        terminal_state_source,
        dg_overview,
        dg_presentation,
        render_plan,
        active_failure_action,
        final_primary_item,
        active_failure_blocks,
        final_visible_context,
        final_visible_dependencies,
        final_visible_resolution,
        final_visible_item,
        cleanup_before_blocker,
        post_cleanup_render_audit,
        _,
        terminal_state_current_in_target,
        guidance_debug,
    ) = panel_coordinators.render_design_guide_post_cleanup_publication_pre_render_coordinator(
        guidance_items=guidance_items,
        terminal_state=terminal_state,
        terminal_state_source=terminal_state_source,
        dg_overview=dg_overview,
        dg_presentation=dg_presentation,
        render_plan=render_plan,
        guidance_debug=guidance_debug,
        post_cleanup_render_audit=post_cleanup_render_audit,
    )
    _timed("publication_pre_render", stage_started)
    _ = active_failure_action
    _ = final_primary_item
    _ = active_failure_blocks
    _ = final_visible_context
    _ = final_visible_dependencies
    _ = final_visible_item
    _ = cleanup_before_blocker
    stage_started = time.perf_counter()
    (
        guidance_debug,
        render_plan,
        dg_presentation,
        terminal_state,
        presentation_utils,
        guidance_items,
    ) = panel_coordinators.render_design_guide_final_render_branch_dispatch_coordinator(
        current_owner=current_owner,
        final_visible_resolution=final_visible_resolution,
        terminal_state_current_in_target=terminal_state_current_in_target,
        guidance_debug=guidance_debug,
        render_plan=render_plan,
        dg_presentation=dg_presentation,
        fingerprint=fingerprint,
        guidance_items_raw=guidance_items_raw,
        guidance_disp_state=guidance_disp_state,
        dg_overview=dg_overview,
        inputs_render_audit=inputs_render_audit,
        terminal_state=terminal_state,
        guidance_items=guidance_items,
        render_post_apply_banner=render_post_apply_banner,
        fast_focus_section=fast_focus_section,
    )
    _timed("final_render_dispatch", stage_started)
    stage_started = time.perf_counter()
    panel_coordinators.render_design_guide_panel_exit_state(
        guidance_debug=guidance_debug,
        render_plan=render_plan,
        dg_presentation=dg_presentation,
        terminal_state=terminal_state,
        presentation_utils=presentation_utils,
        guidance_items=guidance_items,
        render_post_apply_banner=render_post_apply_banner,
        fingerprint=fingerprint,
    )
    _timed("exit_state", stage_started)
    _publish_timings()
