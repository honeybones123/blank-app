"""Inputs page Design Guide render coordinators."""

from .candidate_keys import (
    AUTO_DESIGN_CANDIDATE_KEY_TRACKED_FIELDS,
    _candidate_cache_key,
    _make_auto_design_candidate_key,
)
from .item_identity import _guidance_item_family, _guidance_item_source_candidate_id
from .panel_orchestration import render_design_guide_panel_orchestration
from .panel_coordinators import (
    render_design_guide_active_guard_presentation_engine_coordinator,
    render_design_guide_compute_preparation_coordinator,
    render_design_guide_final_render_branch_dispatch_coordinator,
    render_design_guide_initial_state_and_loading_coordinator,
    render_design_guide_panel_entry_trace_and_stage_coordinator,
    render_design_guide_panel_exit_state,
    render_design_guide_post_cleanup_publication_pre_render_coordinator,
    render_design_guide_postprocess_pre_render_plan_coordinator,
    render_design_guide_presentation_post_cleanup_gate_coordinator,
)
from .render_coordinators import (
    render_design_guide_component_cta,
    render_design_guide_post_apply_banner,
    render_guidance_secondary_items,
)
from .state_coherence import (
    _canonical_pack_is_valid,
    _coherence_debug_fields,
    _design_state_coherence_check,
)
from .update_families import (
    _COMPOUND_BOTTOM_UPDATE_KEYS,
    _COMPOUND_GEOMETRY_UPDATE_KEYS,
    _COMPOUND_SHEAR_UPDATE_KEYS,
    _compound_subfamilies_from_updates,
)

__all__ = [
    "AUTO_DESIGN_CANDIDATE_KEY_TRACKED_FIELDS",
    "_COMPOUND_BOTTOM_UPDATE_KEYS",
    "_COMPOUND_GEOMETRY_UPDATE_KEYS",
    "_COMPOUND_SHEAR_UPDATE_KEYS",
    "_candidate_cache_key",
    "_canonical_pack_is_valid",
    "_coherence_debug_fields",
    "_compound_subfamilies_from_updates",
    "_design_state_coherence_check",
    "_guidance_item_family",
    "_guidance_item_source_candidate_id",
    "_make_auto_design_candidate_key",
    "render_design_guide_panel_orchestration",
    "render_design_guide_active_guard_presentation_engine_coordinator",
    "render_design_guide_compute_preparation_coordinator",
    "render_design_guide_final_render_branch_dispatch_coordinator",
    "render_design_guide_initial_state_and_loading_coordinator",
    "render_design_guide_panel_entry_trace_and_stage_coordinator",
    "render_design_guide_panel_exit_state",
    "render_design_guide_post_cleanup_publication_pre_render_coordinator",
    "render_design_guide_postprocess_pre_render_plan_coordinator",
    "render_design_guide_presentation_post_cleanup_gate_coordinator",
    "render_design_guide_component_cta",
    "render_design_guide_post_apply_banner",
    "render_guidance_secondary_items",
]
