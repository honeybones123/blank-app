"""Inputs page Design Guide render coordinators.

Public exports are retained, but implementation modules load lazily so pure
compatibility helpers do not eagerly import Streamlit/rendering state.
"""

from importlib import import_module


_LAZY_EXPORTS = {
    "AUTO_DESIGN_CANDIDATE_KEY_TRACKED_FIELDS": (".candidate_keys", "AUTO_DESIGN_CANDIDATE_KEY_TRACKED_FIELDS"),
    "_candidate_cache_key": (".candidate_keys", "_candidate_cache_key"),
    "_make_auto_design_candidate_key": (".candidate_keys", "_make_auto_design_candidate_key"),
    "_guidance_item_family": (".item_identity", "_guidance_item_family"),
    "_guidance_item_source_candidate_id": (".item_identity", "_guidance_item_source_candidate_id"),
    "render_design_guide_panel_orchestration": (".panel_orchestration", "render_design_guide_panel_orchestration"),
    "render_design_guide_active_guard_presentation_engine_coordinator": (".panel_coordinators", "render_design_guide_active_guard_presentation_engine_coordinator"),
    "render_design_guide_compute_preparation_coordinator": (".panel_coordinators", "render_design_guide_compute_preparation_coordinator"),
    "render_design_guide_final_render_branch_dispatch_coordinator": (".panel_coordinators", "render_design_guide_final_render_branch_dispatch_coordinator"),
    "render_design_guide_initial_state_and_loading_coordinator": (".panel_coordinators", "render_design_guide_initial_state_and_loading_coordinator"),
    "render_design_guide_panel_entry_trace_and_stage_coordinator": (".panel_coordinators", "render_design_guide_panel_entry_trace_and_stage_coordinator"),
    "render_design_guide_panel_exit_state": (".panel_coordinators", "render_design_guide_panel_exit_state"),
    "render_design_guide_post_cleanup_publication_pre_render_coordinator": (".panel_coordinators", "render_design_guide_post_cleanup_publication_pre_render_coordinator"),
    "render_design_guide_postprocess_pre_render_plan_coordinator": (".panel_coordinators", "render_design_guide_postprocess_pre_render_plan_coordinator"),
    "render_design_guide_presentation_post_cleanup_gate_coordinator": (".panel_coordinators", "render_design_guide_presentation_post_cleanup_gate_coordinator"),
    "render_design_guide_component_cta": (".render_coordinators", "render_design_guide_component_cta"),
    "render_design_guide_post_apply_banner": (".render_coordinators", "render_design_guide_post_apply_banner"),
    "render_guidance_secondary_items": (".render_coordinators", "render_guidance_secondary_items"),
    "_canonical_pack_is_valid": (".state_coherence", "_canonical_pack_is_valid"),
    "_coherence_debug_fields": (".state_coherence", "_coherence_debug_fields"),
    "_design_state_coherence_check": (".state_coherence", "_design_state_coherence_check"),
    "_COMPOUND_BOTTOM_UPDATE_KEYS": (".update_families", "_COMPOUND_BOTTOM_UPDATE_KEYS"),
    "_COMPOUND_GEOMETRY_UPDATE_KEYS": (".update_families", "_COMPOUND_GEOMETRY_UPDATE_KEYS"),
    "_COMPOUND_SHEAR_UPDATE_KEYS": (".update_families", "_COMPOUND_SHEAR_UPDATE_KEYS"),
    "_compound_subfamilies_from_updates": (".update_families", "_compound_subfamilies_from_updates"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


__all__ = list(_LAZY_EXPORTS)
