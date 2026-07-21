"""Inputs page app-facing constants.

These constants are consumed by ``app.py`` outside the routed Inputs page.
Keeping them here removes pure constant reads from the old physical page while
preserving the existing session keys and numeric thresholds.
"""

from __future__ import annotations


DESIGN_GUIDE_DEBUG_BUNDLE_KEY = "_design_guide_debug_bundle"
DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY = "_design_guide_last_apply_route"
DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY = "design_guide_primary_apply_payload"
DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY = "design_guide_primary_payload_binding_audit"
DESIGN_GUIDE_NEEDS_REFRESH_KEY = "_design_guide_needs_refresh"
DESIGN_GUIDE_PANEL_BASELINE_FP_KEY = "_design_guide_panel_baseline_fingerprint"
DESIGN_GUIDE_RECO_TRACE_KEY = "_design_guide_reco_trace"
DESIGN_GUIDE_RANK_TRACE_KEY = "_design_guide_rank_trace"
DESIGN_GUIDE_APPLY_BANNER_KEY = "_design_guide_apply_banner_payload"
DESIGN_GUIDE_APPLY_BANNER_META_KEY = "_design_guide_apply_banner_meta"
DESIGN_GUIDE_STEP_HISTORY_KEY = "_design_guide_step_history"
DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY = "_design_guide_first_target_band_step"
DESIGN_GUIDE_HISTORY_ANCHOR_KEY = "_design_guide_history_anchor"
DESIGN_GUIDE_PENDING_STEP_CTX_KEY = "_design_guide_pending_step_ctx"
DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY = "_design_guide_cached_fingerprint"
DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY = "_design_guide_cached_items"
DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY = "_design_guide_cached_debug"
DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY = "_design_guide_fp"
DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY = "_design_guide_cache"

EFFICIENCY_TARGET_UTIL_MIN = 0.88
EFFICIENCY_TARGET_UTIL_MAX = 0.95
TARGET_BAND_EPS = 0.005
GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN = 1.0
GUIDANCE_TORSION_DEMAND_ABS_TOL_KNM = 0.5
FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85


__all__ = [
    "DESIGN_GUIDE_DEBUG_BUNDLE_KEY",
    "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
    "DESIGN_GUIDE_NEEDS_REFRESH_KEY",
    "DESIGN_GUIDE_PANEL_BASELINE_FP_KEY",
    "DESIGN_GUIDE_APPLY_BANNER_KEY",
    "DESIGN_GUIDE_APPLY_BANNER_META_KEY",
    "DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY",
    "DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY",
    "DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY",
    "DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY",
    "DESIGN_GUIDE_HISTORY_ANCHOR_KEY",
    "DESIGN_GUIDE_PENDING_STEP_CTX_KEY",
    "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY",
    "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY",
    "DESIGN_GUIDE_RANK_TRACE_KEY",
    "DESIGN_GUIDE_RECO_TRACE_KEY",
    "DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY",
    "DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY",
    "DESIGN_GUIDE_STEP_HISTORY_KEY",
    "EFFICIENCY_TARGET_UTIL_MAX",
    "EFFICIENCY_TARGET_UTIL_MIN",
    "FINAL_ACCEPTED_MIN_FAMILY_UTIL",
    "GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN",
    "GUIDANCE_TORSION_DEMAND_ABS_TOL_KNM",
    "TARGET_BAND_EPS",
]
