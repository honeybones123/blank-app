"""Main-panel auto-design status rendering for the Inputs Design Guide."""

from __future__ import annotations

from typing import Any


_MAIN_PANEL_STATUS_DEPENDENCIES: tuple[str, ...] = (
    "AUTO_DESIGN_REQUEST_SOURCE_KEY",
    "DESIGN_GUIDE_DEBUG_BUNDLE_KEY",
    "_sync_auto_design_invoke_pending_field",
    "st",
    "ux_probe_record",
)


def bind_main_panel_status_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _MAIN_PANEL_STATUS_DEPENDENCIES
            if name in namespace
        }
    )


def _render_auto_design_main_panel_status() -> None:
    """
    Lightweight main-panel copy for idle/deferred/cancel - no debug sidebar required.
    Skips noise when there is nothing to report.
    """
    try:
        ads = str(st.session_state.get("auto_design_status") or "").strip()
        if ads == "running":
            st.caption("Auto-design is running on the current inputs.")
            return
        if ads == "rejected":
            sr0 = st.session_state.get("_solver_result")
            if isinstance(sr0, dict):
                uvc = sr0.get("user_visible_commit_rejection")
                if uvc:
                    st.warning(str(uvc))
                    return
        if ads == "no_action":
            sr0 = st.session_state.get("_solver_result")
            if isinstance(sr0, dict):
                uvr = sr0.get("user_visible_no_action_reason")
                urej = sr0.get("user_visible_rejection_summary")
                if uvr:
                    ux_probe_record(
                        "design_guide_legacy_no_action_info_banner_suppressed",
                        meta={"source": "_solver_result"},
                    )
                if urej:
                    st.caption(str(urej))
                if uvr or urej:
                    return
    except Exception:
        pass

    try:
        sr0 = st.session_state.get("_solver_result")
        if not isinstance(sr0, dict):
            bundle0 = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {}
            passive_reason = str(bundle0.get("user_visible_no_action_reason") or "").strip()
            passive_stop_reason = str(bundle0.get("stop_reason") or "").strip()
            if passive_reason:
                ux_probe_record(
                    "design_guide_legacy_no_action_info_banner_suppressed",
                    meta={
                        "source": DESIGN_GUIDE_DEBUG_BUNDLE_KEY,
                        "has_stop_reason": bool(passive_stop_reason),
                    },
                )
                return
    except Exception:
        pass

    idle = str(
        st.session_state.get("auto_design_idle_reason")
        or st.session_state.get("_auto_design_idle_reason")
        or "",
    ).strip()
    if not idle or idle == "idle_not_invoked":
        return
    _sync_auto_design_invoke_pending_field()
    src = str(
        st.session_state.get("auto_design_request_source")
        or st.session_state.get(AUTO_DESIGN_REQUEST_SOURCE_KEY)
        or "",
    ).strip()
    labels = {
        "idle_should_run_false": "Auto-design did not run: waiting for invoke.",
        "deferred_compute_in_progress": "Auto-design deferred: compute in progress.",
        "deferred_solver_running": "Auto-design deferred: solver already running.",
        "request_cancelled_by_guidance_commit": "Auto-design request was cancelled.",
    }
    base = labels.get(idle, f"Auto-design did not run ({idle}).")
    if src and idle not in ("request_cancelled_by_guidance_commit",):
        base = f"{base} (request: {src})"
    st.caption(base)


__all__ = [
    "bind_main_panel_status_dependencies",
    "_render_auto_design_main_panel_status",
]
