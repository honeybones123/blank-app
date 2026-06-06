"""Design Guide page adapter.

This module owns the Streamlit page mounting boundary for the Design Guide.
The heavy controller/solver callbacks still live in ``inputs_page`` for now,
but routing the UI entrypoints through this file gives the page a stable home
for the staged extraction.
"""

from __future__ import annotations

from collections.abc import Callable
import html
import time
from typing import Any


TraceFn = Callable[..., None]
RenderPanelFn = Callable[..., None]
DebugSidebarFn = Callable[[], None]


def _proof_backed_placeholder_card(st_module: Any) -> dict | None:
    """Return a single exact-blocker card when final-panel proof already exists."""
    try:
        bundle = st_module.session_state.get("_design_guide_debug_bundle")
    except Exception:
        bundle = None
    if not isinstance(bundle, dict):
        return None
    intent = str(bundle.get("primary_guidance_intent") or bundle.get("primary_card_intent") or "").strip()
    if intent != "specific_blocker":
        return None
    contract = bundle.get("primary_button_contract") or bundle.get("button_contract") or {}
    if isinstance(contract, dict) and bool(contract.get("enabled") or contract.get("actionable")):
        return None
    exact_blockers = (
        bundle.get("post_click_exact_blockers_by_family")
        or bundle.get("exact_blockers_by_family")
        or {}
    )
    if not isinstance(exact_blockers, dict) or not exact_blockers:
        return None
    family = ""
    if isinstance(contract, dict):
        family = str(contract.get("family") or "").strip().lower()
    if family not in {"bending", "shear", "crack", "deflection", "combined"}:
        family = str(next(iter(exact_blockers), "design")).strip().lower()
    blocker = exact_blockers.get(family) if family in exact_blockers else next(iter(exact_blockers.values()), {})
    blocker = blocker if isinstance(blocker, dict) else {}
    truth = bundle.get("primary_display_truth") or {}
    truth = truth if isinstance(truth, dict) else {}
    util = truth.get("displayed_util")
    if util is None:
        util = blocker.get("current_util") or blocker.get("failed_check_util")
    reason = ""
    if isinstance(contract, dict):
        reason = str(contract.get("blocking_reason") or "").strip()
    if not reason:
        reason = str(
            blocker.get("reason")
            or blocker.get("why_reduction_would_hurt_other_design_elements")
            or "The exact cleanup search was exhausted and no executor-backed update preserved every required check."
        ).strip()
    title = str(bundle.get("primary_card_title") or bundle.get("final_primary_title") or "").strip()
    if not title or title.lower().startswith("cleanup blocked"):
        label = {
            "bending": "Bending cleanup",
            "shear": "Shear cleanup",
            "crack": "Crack control cleanup",
            "deflection": "Deflection cleanup",
            "combined": "Design cleanup",
        }.get(family, "Design cleanup")
        title = f"{label} blocked by exact engineering limit"
    return {"title": title, "family": family, "util": util, "reason": reason}


def _render_proof_backed_card(st_module: Any, proof_card: dict) -> None:
    util = proof_card.get("util")
    util_text = ""
    try:
        util_text = f" <span class='fast-guidance-title-util'>(utilisation = {float(util):.2f})</span>"
    except Exception:
        util_text = ""
    title = html.escape(str(proof_card.get("title") or "Design cleanup blocked"))
    reason = html.escape(str(proof_card.get("reason") or "Exact blocker evidence is available."))
    st_module.markdown(
        "<div class='fast-guidance-item warn'>"
        "<div class='fast-guidance-head'>"
        "<span class='fast-guidance-badge warn'>NEXT</span>"
        "<span class='fast-guidance-title-wrap'>"
        f"<span class='fast-guidance-title'>{title}</span>{util_text}"
        "</span></div>"
        f"<div class='fast-guidance-reason'><strong>Why</strong><br>{reason}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


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
    st_module.markdown(
        """
<style>
.dg-proof-pending-shell {
    min-height: 10.5rem;
    border: 1px solid rgba(37, 99, 235, 0.18);
    border-left: 4px solid rgb(37, 99, 235);
    border-radius: 8px;
    background: linear-gradient(180deg, rgba(248,250,252,0.96), rgba(241,245,249,0.72));
    padding: 0.92rem 1rem 0.98rem;
    color: rgb(31, 41, 55);
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.dg-proof-pending-shell.applying {
    border-color: rgba(22, 163, 74, 0.20);
    border-left-color: rgb(22, 163, 74);
    background: linear-gradient(180deg, rgba(240,253,244,0.96), rgba(248,250,252,0.82));
}
.dg-proof-pending-eyebrow {
    color: rgb(37, 99, 235);
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0;
    margin-bottom: 0.28rem;
}
.dg-proof-pending-shell.applying .dg-proof-pending-eyebrow {
    color: rgb(22, 101, 52);
}
.dg-proof-pending-title {
    font-size: 1.02rem;
    font-weight: 750;
    line-height: 1.25;
    margin-bottom: 0.22rem;
}
.dg-proof-pending-subtext {
    color: rgba(31, 41, 55, 0.72);
    font-size: 0.86rem;
    line-height: 1.35;
    margin-bottom: 0.8rem;
}
.dg-proof-pending-bar {
    position: relative;
    overflow: hidden;
    height: 0.44rem;
    border-radius: 999px;
    background: rgba(37, 99, 235, 0.12);
    margin-bottom: 0.78rem;
}
.dg-proof-pending-bar::after {
    content: "";
    position: absolute;
    inset: 0;
    width: 38%;
    border-radius: inherit;
    background: linear-gradient(90deg, rgba(37,99,235,0), rgba(37,99,235,0.42), rgba(37,99,235,0));
    animation: dgProofPendingSweep 1.35s ease-in-out infinite;
}
.dg-proof-pending-shell.applying .dg-proof-pending-bar {
    background: rgba(22, 163, 74, 0.14);
}
.dg-proof-pending-shell.applying .dg-proof-pending-bar::after {
    background: linear-gradient(90deg, rgba(22,163,74,0), rgba(22,163,74,0.44), rgba(22,163,74,0));
}
.dg-proof-pending-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.42rem;
}
.dg-proof-pending-chip {
    display: inline-flex;
    align-items: center;
    min-height: 1.55rem;
    padding: 0.18rem 0.56rem;
    border: 1px solid rgba(37, 99, 235, 0.18);
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.72);
    color: rgba(31, 41, 55, 0.78);
    font-size: 0.78rem;
    font-weight: 650;
}
@keyframes dgProofPendingSweep {
    0% { transform: translateX(-110%); }
    100% { transform: translateX(275%); }
}
@media (prefers-reduced-motion: reduce) {
    .dg-proof-pending-bar::after {
        animation: none;
        transform: translateX(80%);
    }
}
</style>
        """,
        unsafe_allow_html=True,
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
        "<div class='dg-proof-pending-bar' aria-hidden='true'></div>"
        f"<div class='dg-proof-pending-chips'>{chips_html}</div>"
        "</section>",
        unsafe_allow_html=True,
    )


def render_pre_widget_placeholder(st_module: Any, slot: Any) -> None:
    """Mount the lightweight Design Guide placeholder before inputs widgets."""
    with slot.container():
        st_module.markdown("### Design Guide")
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
) -> None:
    """Replace the placeholder with the proof-backed Design Guide panel."""
    slot.empty()
    with slot.container():
        trace_started = time.perf_counter()
        if inputs_detailed_mode:
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


def render_debug_sidebar(render_sidebar: DebugSidebarFn) -> None:
    """Render the Design Guide debug sidebar through the page boundary."""
    render_sidebar()
