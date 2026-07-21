"""Design Guide panel orchestration coordinator for the Inputs shell."""

from __future__ import annotations

from typing import Any


def render_design_guide_panel_orchestration(
    *,
    coordinator_owner: Any,
    sync_callbacks: dict | None = None,
    inputs_render_audit: dict[str, str] | None = None,
    fast_focus_section: str | None = None,
) -> None:
    """Sequence existing Design Guide sub-coordinators without owning logic."""

    _ = sync_callbacks
    _started_at, _mark_stage = coordinator_owner.render_design_guide_panel_entry_trace_and_stage_coordinator(
        inputs_render_audit=inputs_render_audit,
        fast_focus_section=fast_focus_section,
    )
    _ = _started_at
    _ = _mark_stage
    (
        current_state,
        fingerprint,
        sidebar_debug,
        settle_gate_decision,
        loading_rendered,
        terminal_state_current_in_target,
    ) = coordinator_owner.render_design_guide_initial_state_and_loading_coordinator(
        inputs_render_audit=inputs_render_audit,
    )
    if loading_rendered:
        return
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
    ) = coordinator_owner.render_design_guide_compute_preparation_coordinator(
        settle_gate_decision=settle_gate_decision,
        current_state=current_state,
        fingerprint=fingerprint,
    )
    if fast_terminal_rendered:
        return
    _stage = (settle_gate_decision.get("_dg_initial") or {}).get("stage")
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
    ) = coordinator_owner.render_design_guide_postprocess_pre_render_plan_coordinator(
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
    if not_started_rendered:
        return
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
    ) = coordinator_owner.render_design_guide_active_guard_presentation_engine_coordinator(
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
    _ = mode_cfg
    _ = dg_engine_decision
    _ = presentation_utils
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
    ) = coordinator_owner.render_design_guide_presentation_post_cleanup_gate_coordinator(
        guidance_items=guidance_items,
        dg_presentation=dg_presentation,
        recommendation_result=_recommendation_result,
        guidance_debug=guidance_debug,
        terminal_state=terminal_state,
        terminal_state_source=terminal_state_source,
        dg_overview=dg_overview,
    )
    if early_shear_return:
        return
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
    ) = coordinator_owner.render_design_guide_post_cleanup_publication_pre_render_coordinator(
        guidance_items=guidance_items,
        terminal_state=terminal_state,
        terminal_state_source=terminal_state_source,
        dg_overview=dg_overview,
        dg_presentation=dg_presentation,
        render_plan=render_plan,
        guidance_debug=guidance_debug,
        post_cleanup_render_audit=post_cleanup_render_audit,
    )
    _ = active_failure_action
    _ = final_primary_item
    _ = active_failure_blocks
    _ = final_visible_context
    _ = final_visible_dependencies
    _ = final_visible_item
    _ = cleanup_before_blocker
    (
        guidance_debug,
        render_plan,
        dg_presentation,
        terminal_state,
        presentation_utils,
        guidance_items,
    ) = coordinator_owner.render_design_guide_final_render_branch_dispatch_coordinator(
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
    coordinator_owner.render_design_guide_panel_exit_state(
        guidance_debug=guidance_debug,
        render_plan=render_plan,
        dg_presentation=dg_presentation,
        terminal_state=terminal_state,
        presentation_utils=presentation_utils,
        guidance_items=guidance_items,
        render_post_apply_banner=render_post_apply_banner,
        fingerprint=fingerprint,
    )
