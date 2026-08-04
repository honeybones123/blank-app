"""Design Guide page adapter.

This module owns the Streamlit page mounting boundary for the Design Guide.
The heavy controller/solver callbacks still live in ``inputs_page`` for now,
but routing the UI entrypoints through this file gives the page a stable home
for the staged extraction.
"""

from __future__ import annotations

from collections.abc import Callable
import html
import os
import time
from typing import Any


TraceFn = Callable[..., None]
RenderPanelFn = Callable[..., None]
DebugSidebarFn = Callable[[], None]


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _render_proof_pending_shell(st_module: Any) -> None:
    """Render a CTA-free Design Guide placeholder while proof/search is running."""
    applying = bool(st_module.session_state.get("_design_guide_component_apply_in_flight"))
    chips = ("Strength", "Detailing", "Serviceability", "Cleanup options")
    chips_html = "".join(
        f"<span class='dg-proof-pending-chip'>{html.escape(label)}</span>"
        for label in chips
    )
    title = "Applying one-click design..." if applying else "Checking design guidance&hellip;"
    subtext = (
        "Updating the beam inputs, recalculating checks, and preparing the final Design Guide result."
        if applying
        else "Reviewing strength, detailing, serviceability, and cleanup options."
    )
    shell_class = "dg-proof-pending-shell applying" if applying else "dg-proof-pending-shell"
    st_module.markdown(
        f"<section class='{shell_class}' data-testid='design-guide-proof-pending' "
        "aria-live='polite' aria-busy='true'>"
        "<div class='dg-proof-pending-eyebrow'>Design Guide</div>"
        f"<div class='dg-proof-pending-title'>{title}</div>"
        "<div class='dg-proof-pending-subtext'>"
        f"{html.escape(subtext)}"
        "</div>"
        "<div class='dg-proof-pending-bar' aria-hidden='true'>"
        "<span class='dg-proof-pending-bar-fill'></span></div>"
        f"<div class='dg-proof-pending-chips'>{chips_html}</div>"
        "</section>",
        unsafe_allow_html=True,
    )


def _has_final_design_guide_publication_payload(st_module: Any) -> bool:
    try:
        bundle = st_module.session_state.get("_design_guide_debug_bundle")
    except Exception:
        bundle = None
    if not isinstance(bundle, dict):
        return False
    payload = bundle.get("final_publication_verifier_payload")
    if not isinstance(payload, dict):
        return False
    if str(payload.get("publication_hash") or "").strip():
        return True
    state = str(
        payload.get("outcome_state")
        or payload.get("status")
        or payload.get("publication_status")
        or ""
    ).strip().upper()
    return state in {"PASS", "ACTION", "BLOCKED", "ERROR"}


def _should_skip_pre_widget_placeholder(st_module: Any) -> bool:
    _ = st_module
    return False


def render_pre_widget_placeholder(
    st_module: Any,
    slot: Any,
    *,
    render_heading: bool = True,
    render_pending_shell: bool = True,
) -> None:
    """Mount only the transient shell before the authoritative final card."""
    if _should_skip_pre_widget_placeholder(st_module):
        return
    with slot.container():
        if render_heading:
            st_module.markdown("## Design Guide")
        if render_pending_shell:
            _render_proof_pending_shell(st_module)
def render_final_panel(
    st_module: Any,
    *,
    slot: Any,
    sync_callbacks: dict,
    inputs_render_audit: dict[str, str] | None,
    inputs_detailed_mode: bool,
    fast_focus_section: str | None,
    render_panel: RenderPanelFn,
    trace: TraceFn,
    render_panel_accepts_sync_callbacks: bool = True,
) -> None:
    """Replace the placeholder with the proof-backed Design Guide panel."""
    slot.empty()
    render_epoch = int(
        st_module.session_state.get("_design_guide_render_epoch", 0) or 0
    ) + 1
    st_module.session_state["_design_guide_render_epoch"] = render_epoch
    st_module.session_state.pop("_design_guide_cta_rendered_epoch", None)

    def _render_panel_content() -> None:
        trace_started = time.perf_counter()
        if not render_panel_accepts_sync_callbacks:
            render_panel(
                inputs_render_audit=inputs_render_audit,
                fast_focus_section=fast_focus_section if inputs_detailed_mode else None,
            )
            mode = "detailed" if inputs_detailed_mode else "fast"
        elif inputs_detailed_mode:
            render_panel(
                sync_callbacks,
                inputs_render_audit,
                fast_focus_section=fast_focus_section,
            )
            mode = "detailed"
        else:
            render_panel(sync_callbacks, inputs_render_audit)
            mode = "fast"
        trace(
            "render_inputs.render_fast_design_guidance_panel",
            duration_ms=round((time.perf_counter() - trace_started) * 1000.0, 2),
            mode=mode,
            timing="after_core_inputs_widgets",
        )

    fragment = getattr(st_module, "fragment", None)
    fragment_disabled = str(os.environ.get("CODEX_ENABLE_DESIGN_GUIDE_FRAGMENT") or "").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }
    # The Inputs shell already owns the engineering-workspace fragment. A
    # nested Design Guide fragment can survive a parent rerun and leave old
    # cards/widgets mounted beside the new publication.
    session_state = getattr(st_module, "session_state", {})
    parent_fragment_active = any(
        session_state.get(key) == "fragment"
        for key in (
            "_inputs_engineering_calculation_workspace_fragment_mode",
            # Current architecture: Design Guide owns its explicit Inputs
            # fragment. Creating another fragment here would make the CTA
            # rerun only this inner panel while the queued Apply consumer at
            # the outer fragment entry never executes.
            "_inputs_design_guide_fragment_mode",
            # Transitional combined-workspace architecture.
            "_inputs_engineering_workspace_fragment_mode",
        )
    )
    fragment_enabled = not fragment_disabled and not parent_fragment_active
    if parent_fragment_active:
        # The workspace fragment already owns this rerun. Render directly
        # after clearing the slot so an additional slot container cannot keep
        # a previous Apply widget alive beside the current publication.
        st_module.session_state["_design_guide_fragment_mode"] = "outer_fragment"
        with slot.container():
            _render_panel_content()
    elif callable(fragment) and fragment_enabled:
        st_module.session_state["_design_guide_fragment_mode"] = "fragment"
        # Keep the fragment inside the stable slot. A page-scope fragment can
        # survive a later full rerun after slot.empty(), leaving duplicate
        # cards/widgets mounted at the same coordinates.
        with slot.container():
            fragment(_render_panel_content)()
    else:
        st_module.session_state["_design_guide_fragment_mode"] = (
            "outer_fragment" if parent_fragment_active else "full_page_fallback"
        )
        with slot.container():
            _render_panel_content()


def render_debug_sidebar(render_sidebar: DebugSidebarFn) -> None:
    """Render the Design Guide debug sidebar through the page boundary."""
    render_sidebar()
