"""Design Guide debug sidebar render coordinator."""

from __future__ import annotations

import json
from typing import Any, Callable


def render_design_guide_debug_sidebar(
    *,
    st_module: Any,
    sidebar_debug_enabled_fn: Callable[[], bool],
    clear_transient_ui_state_fn: Callable[..., None],
    auto_design_invoke_debug_snapshot_fn: Callable[[], dict],
    debug_bundle_key: str,
    reco_trace_key: str,
) -> None:
    if not sidebar_debug_enabled_fn():
        return
    st_module.sidebar.divider()
    st_module.sidebar.caption("Design Guide Debug")
    if st_module.sidebar.button("Clear design guide UI state", key="_dg_debug_clear_transient_ui"):
        clear_transient_ui_state_fn(clear_history=False, preserve_apply_banner=False)
        st_module.rerun()
    bundle = st_module.session_state.get(debug_bundle_key) or {}
    trace = st_module.session_state.get(reco_trace_key) or []
    live_crumb = st_module.session_state.get("_dg_live_breadcrumb") or {}

    st_module.sidebar.warning(
        "DG live breadcrumb: "
        f"{str(live_crumb.get('label') or 'none')} @ {str(live_crumb.get('ts') or 'n/a')}",
    )
    st_module.sidebar.code(
        json.dumps(
            {
                "label": live_crumb.get("label"),
                "ts": live_crumb.get("ts"),
                "extra": dict(live_crumb.get("extra") or {}),
            },
            indent=2,
            default=str,
        ),
    )
    with st_module.sidebar.expander("One-click auto-design invoke", expanded=False):
        st_module.json(
            {
                **auto_design_invoke_debug_snapshot_fn(),
                "auto_design_idle_reason": st_module.session_state.get("auto_design_idle_reason"),
                "auto_design_invoke_set": st_module.session_state.get("auto_design_invoke_set"),
                "auto_design_invoke_consumed": st_module.session_state.get("auto_design_invoke_consumed"),
                "canonical_convenience_resync_applied": st_module.session_state.get(
                    "canonical_convenience_resync_applied"
                ),
                "canonical_convenience_fields_updated": st_module.session_state.get(
                    "canonical_convenience_fields_updated"
                ),
                "convenience_field_drift_detected": st_module.session_state.get(
                    "convenience_field_drift_detected"
                ),
            }
        )

    with st_module.sidebar.expander("Guidance Selection", expanded=False):
        st_module.json(
            {
                "guidance_branch": bundle.get("guidance_branch"),
                "governing_action": bundle.get("governing_action"),
                "primary_utils": bundle.get("primary_utils"),
                "selected_action_type": bundle.get("selected_action_type"),
                "selected_title": bundle.get("selected_title"),
                "guidance_items": bundle.get("guidance_items_summary"),
            }
        )

    with st_module.sidebar.expander("Candidates", expanded=False):
        st_module.json(
            {
                "overview_utils": (bundle.get("overview") or {}).get("utils")
                if isinstance(bundle.get("overview"), dict)
                else None,
                "overview_statuses": (bundle.get("overview") or {}).get("statuses")
                if isinstance(bundle.get("overview"), dict)
                else None,
                "current_design_summary": bundle.get("current_design_summary"),
                "efficiency_snippet": {
                    "mode_tightening": bundle.get("next_mode_recommendation"),
                    "bottom_tightening": bundle.get("bottom_tightening"),
                },
            }
        )

    with st_module.sidebar.expander("Stage 3 shear truth (final published)", expanded=False):
        st_module.json(
            {
                "design_guide_shear_truth_source": bundle.get("design_guide_shear_truth_source"),
                "stage3_remaining_issue_class": bundle.get("stage3_remaining_issue_class"),
                "stage3_shear_truth_debug": bundle.get("stage3_shear_truth_debug"),
                "overview_stage3_embedded": (bundle.get("overview") or {}).get("stage3_shear_truth_debug")
                if isinstance(bundle.get("overview"), dict)
                else None,
            }
        )

    with st_module.sidebar.expander("Scores / Ranking", expanded=False):
        st_module.json(
            {
                "fingerprints": bundle.get("fingerprints"),
                "resolved_guidance_actions": bundle.get("resolved_guidance_actions"),
                "reco_trace_tail": trace[-20:] if trace else [],
            }
        )

    with st_module.sidebar.expander("Rejections", expanded=False):
        rejects = [t for t in trace if str(t.get("event") or "") == "rejected"]
        st_module.json({"recent_rejections": rejects[-30:], "rejection_count": len(rejects)})

    with st_module.sidebar.expander("Step history (compact)", expanded=False):
        st_module.json(bundle.get("design_guide_step_history_compact") or [])

    with st_module.sidebar.expander("Full probe (raw)", expanded=False):
        st_module.json(bundle)


__all__ = ["render_design_guide_debug_sidebar"]
