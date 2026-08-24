"""V2 Design Guide card rendered from the neutral publication contract.

This module deliberately knows nothing about the V2 implementation.  It is a
presentation adapter: the selected DesignBrainService supplies an immutable
result and this renderer turns its display/CTA models into the V2 card visual.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from typing import Any, Callable

from application.contracts.design_brain import AuthoritativeDesignResult


def _text(value: Any, fallback: str = "") -> str:
    value = str(value or "").strip()
    return value or fallback


def _queue_v2_design_guide_apply(st_module: Any, payload: dict[str, Any]) -> None:
    """Queue one immutable Apply intent before the workspace render starts."""

    queued_payload = dict(payload)
    st_module.session_state["pending_recommendation"] = dict(queued_payload)
    st_module.session_state["_inputs_action_apply_recommendation_payload"] = dict(queued_payload)
    st_module.session_state["_inputs_action_apply_recommendation"] = True


def _commit_v2_design_guide_apply(
    st_module: Any,
    payload: dict[str, Any],
    apply_handler: Callable[[], Any],
) -> None:
    """Commit the pre-verified payload in the button callback transaction.

    A callback is guaranteed to run before Streamlit performs the widget's
    owning fragment render.  Merely queueing the payload relied on that
    fragment body being re-entered, which is not guaranteed for every cold or
    remounted hosted widget.  The queued command could consequently remain
    dormant until a later edit.  Execute the existing typed Apply handler now;
    the one automatic fragment render then sees only the committed revision.
    """

    _queue_v2_design_guide_apply(st_module, payload)
    apply_handler()
    st_module.session_state["_inputs_atomic_revision_guard_pending"] = True


def _format_clause_reference(value: Any) -> str:
    """Render typed clause metadata without leaking Python reprs into the UI."""

    if isinstance(value, Mapping):
        standard = _text(value.get("standard"), "AS 3600")
        edition = _text(value.get("edition"), "2018")
        clause = _text(value.get("clause"))
        title = _text(value.get("title"))
        if clause and title:
            return f"{standard} {edition} Cl. {clause}: {title}"
        if clause:
            return f"{standard} {edition} Cl. {clause}"
        return f"{standard} {edition}"
    return _text(value)


def _normalise_visual_state(raw_state: Any, badge: Any) -> str:
    """Map V2 semantic or literal colour states to Runtime CSS classes."""

    state = _text(raw_state, "info").lower()
    badge_text = _text(badge).upper()
    if state in {"blocked", "fail", "failed", "error", "red"} or badge_text == "BLOCKED":
        return "fail"
    if state in {"action", "optimise", "optimize", "blue"}:
        return "optimise"
    if state in {"warning", "warn", "orange", "yellow"}:
        return "warn"
    if state in {"pass", "success", "ok", "green"} or badge_text == "PASS":
        return "pass"
    if state in {"info", "grey", "gray"}:
        return "info"
    return "info"


def render_v2_design_guide_loading_shell(
    *,
    st_module: Any,
    design_guide_slot: Any,
) -> None:
    """Render the Design Brain loading boundary without global run-state CSS."""

    with design_guide_slot.container():
        st_module.markdown(
            """
<style>
.inputs-v2-brain-runtime-loading-shell {
  display:flex;
  align-items:center;
  gap:.7rem;
  min-height:58px;
  padding:.85rem 1rem;
  margin:.7rem 0;
  border:1px solid #cbd5e1;
  border-left:5px solid #98a2b3;
  border-radius:10px;
  background:#fff;
  color:#475569;
}
.inputs-v2-brain-runtime-loading-icon { font-size:1.25rem; line-height:1; }
.inputs-v2-brain-runtime-loading-copy { font-weight:700; color:#334155; }
.inputs-v2-brain-runtime-loading-dot {
  display:inline-block;
  width:.42rem;
  height:.42rem;
  margin-left:.18rem;
  border-radius:999px;
  background:#94a3b8;
  animation:inputs-v2-runtime-pulse 1s infinite alternate;
}
.inputs-v2-brain-runtime-loading-dot:nth-child(2) { animation-delay:.2s; }
.inputs-v2-brain-runtime-loading-dot:nth-child(3) { animation-delay:.4s; }
@keyframes inputs-v2-runtime-pulse { from { opacity:.25; } to { opacity:1; } }
</style>
<div data-testid="inputs-v2-design-brain-runtime-loading" class="inputs-v2-brain-runtime-loading-shell" style="display:flex" role="status" aria-live="polite">
  <span class="inputs-v2-brain-runtime-loading-icon" aria-hidden="true">🧠</span>
  <span class="inputs-v2-brain-runtime-loading-copy">Updating Design Guide
    <span class="inputs-v2-brain-runtime-loading-dot"></span>
    <span class="inputs-v2-brain-runtime-loading-dot"></span>
    <span class="inputs-v2-brain-runtime-loading-dot"></span>
  </span>
</div>
""",
            unsafe_allow_html=True,
        )


def render_v2_design_guide_card(
    *,
    st_module: Any,
    design_guide_slot: Any,
    result: AuthoritativeDesignResult,
    apply_payload: Mapping[str, Any] | None = None,
    apply_handler: Callable[[], Any] | None = None,
) -> None:
    """Render the replacement V2 card in the existing Design Guide slot."""

    display = dict(result.display_model or {})
    cta = dict(result.cta_model or {})
    publication = dict(result.final_publication or {})
    nested = dict(publication.get("final_design_guide_publication") or publication)
    guidance_items = list(nested.get("guidance_items") or [])
    primary = dict(guidance_items[0]) if guidance_items and isinstance(guidance_items[0], dict) else {}

    badge = _text(display.get("v2_badge"), _text(display.get("badge"), _text(display.get("status"), "INFO"))).upper()
    family = _text(display.get("selected_family_id"), _text(result.governing_family, "UNKNOWN"))
    summary = _text(display.get("v2_advice_text"), _text(primary.get("rationale"), _text(primary.get("summary"), "No recommendation published.")))
    no_design_actions = bool(display.get("v2_no_design_actions"))
    clause_metadata = display.get("clause_metadata")
    clause_refs = list(
        clause_metadata.get("references") or []
        if isinstance(clause_metadata, Mapping)
        else []
    )
    # V2's advice text already carries its canonical References line.  Only
    # add a compact metadata line when a provider omitted that line; never use
    # ``str(dict)`` because it exposes an implementation detail in the card.
    clause_text = ""
    if clause_refs and "references:" not in summary.lower():
        formatted_refs = [_format_clause_reference(ref) for ref in clause_refs[:3]]
        clause_text = "; ".join(ref for ref in formatted_refs if ref)
    # The V2 provider calls the failing state ``blocked`` while its standalone
    # renderer maps that state to the visual ``fail`` class.  Keep that mapping
    # in this presentation adapter so the Runtime card has the same colours and
    # CTA treatment as the V2 app without changing V2's domain result.
    # Some V2 display providers expose the presentation state as the literal
    # colour name (``red``/``green``/``blue``/``orange``), while the Runtime
    # contract normally uses semantic names.  Normalize both forms here so
    # the CTA colour cannot drift just because the provider representation
    # changed at the adapter boundary.
    state = _normalise_visual_state(
        _text(display.get("v2_state_class"), _text(display.get("colour_state"), "info")),
        badge,
    )

    try:
        summary_util = float(display.get("v2_governing_utilisation") or 0.0)
    except (TypeError, ValueError):
        summary_util = 0.0
    heading = _text(display.get("v2_heading"), family)
    # V2 owns the text, status, and governing utilisation in this label.  Do
    # not translate the family again in Runtime: that was the source of the
    # previously different card answers.
    summary_label = f"**{badge}**  **{heading}**  |  Governing utilisation: {summary_util:.2f}"

    with design_guide_slot.container():
        st_module.markdown(
            "<style>"
             ".inputs-v2-root .inputs-v2-card-label{color:#343a40;font-size:1.05rem;font-weight:700;border-bottom:1px solid #dce3ec;padding-bottom:.55rem;margin:.25rem 0 .85rem;}"
             ".inputs-v2-root,.inputs-v2-root ~ div[data-testid=\"stExpander\"],div[data-testid=\"stVerticalBlock\"]:has(.inputs-v2-root) > div[data-testid=\"stLayoutWrapper\"]{width:100%;max-width:none;}"
            ".inputs-v2-brain-runtime-loading-shell{display:none;align-items:center;gap:.7rem;min-height:58px;padding:.85rem 1rem;margin:.7rem 0;border:1px solid #cbd5e1;border-left:5px solid #98a2b3;border-radius:10px;background:#fff;color:#475569;}"
            ".inputs-v2-brain-runtime-loading-icon{font-size:1.25rem;line-height:1;}"
            ".inputs-v2-brain-runtime-loading-copy{font-weight:700;color:#334155;}"
            ".inputs-v2-brain-runtime-loading-dot{display:inline-block;width:.42rem;height:.42rem;margin-left:.18rem;border-radius:999px;background:#94a3b8;animation:inputs-v2-runtime-pulse 1s infinite alternate;}"
            ".inputs-v2-brain-runtime-loading-dot:nth-child(2){animation-delay:.2s;}"
            ".inputs-v2-brain-runtime-loading-dot:nth-child(3){animation-delay:.4s;}"
            "@keyframes inputs-v2-runtime-pulse{from{opacity:.25}to{opacity:1}}"
            "/* Mirrored from the latest V2 Design Guide presentation: a native expander is the clickable shell. */"
            "div[data-testid=\"stExpander\"]:has(.inputs-v2-design-guide-copy){border:1px solid #cbd5e1;border-radius:10px;overflow:hidden;background:#f8fafc;margin:.4rem 0;}"
            "div[data-testid=\"stExpander\"]:has(.inputs-v2-design-guide-copy) summary{height:var(--sb-collapsed-card-height,40px)!important;min-height:var(--sb-collapsed-card-height,40px)!important;padding:0 .8rem!important;box-sizing:border-box!important;display:flex!important;align-items:center!important;font-weight:700;color:var(--sb-heading-color,#0f172a);}"
            "div[data-testid=\"stExpander\"]:has(.inputs-v2-design-guide-copy) summary>div{min-height:0!important;height:auto!important;display:flex!important;align-items:center!important;}"
            "div[data-testid=\"stExpander\"]:has(.inputs-v2-design-guide-copy) summary p{margin:0!important;line-height:1.2!important;}"
            "div[data-testid=\"stExpander\"]:has(.inputs-v2-design-guide-copy) details:not([open]){height:var(--sb-collapsed-card-height,40px)!important;min-height:var(--sb-collapsed-card-height,40px)!important;}"
            "div[data-testid=\"stExpander\"]:has(.inputs-v2-design-guide-copy) details:not([open])>[data-testid=\"stExpanderDetails\"]{display:none!important;height:0!important;min-height:0!important;padding:0!important;margin:0!important;}"
            "div[data-testid=\"stExpander\"]:has(.inputs-v2-design-guide-copy) summary svg{display:none;}"
            "div[data-testid=\"stExpander\"]:has(.inputs-v2-design-guide-copy) summary:before{content:\"\\1F9E0\";display:inline-block;margin-right:.65rem;font-size:1.25rem;vertical-align:middle;}"
            "div[data-testid=\"stExpander\"]:has(.inputs-v2-design-guide-copy) summary:hover{background:#eef3ff;}"
            "div[data-testid=\"stExpander\"]:has(.inputs-v2-design-guide-copy)>div[role=\"region\"]{padding:0 .7rem .7rem;}"
            ".inputs-v2-root.inputs-v2-design-guide-copy{border:0!important;background:transparent!important;padding:.35rem .2rem .15rem!important;margin:0!important;border-radius:0!important;line-height:1.42;}"
            ".inputs-v2-brain-state-fail,.inputs-v2-brain-state-pass,.inputs-v2-brain-state-optimise,.inputs-v2-brain-state-info,.inputs-v2-brain-state-warn,.inputs-v2-brain-state-empty{display:none!important;}"
            # Limit the semantic colour to the Design Guide workspace block.
            # A broad ancestor :has() selector also sees the unrelated Batch
            # Design expander higher in the page and paints it red/blue.
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-fail) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"]{background:#fff0f0;border-color:#e03131;border-left:5px solid #e03131;}"
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-fail) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"] summary:hover{background:#ffe3e3;}"
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-optimise) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"]{background:#eef3ff;border-color:#4263eb;border-left:5px solid #4263eb;}"
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-optimise) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"] summary:hover{background:#dbe4ff;}"
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-pass) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"]{background:#edf8ef;border-color:#2f9e44;border-left:5px solid #2f9e44;}"
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-pass) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"] summary:hover{background:#dff3e3;}"
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-empty) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"]{background:#fff;border-color:#adb5bd;border-left:5px solid #868e96;}"
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-empty) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"] summary:hover{background:#f8f9fa;}"
            # The expander owns the single semantic left edge.  Applying the
            # same border to its summary creates a second inset stripe.
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-fail) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"] details>summary{background:#fff0f0!important;border-left:0!important;}"
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-optimise) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"] details>summary{background:#eef3ff!important;border-left:0!important;}"
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-pass) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"] details>summary{background:#edf8ef!important;border-left:0!important;}"
            "div[data-testid=\"stVerticalBlock\"]:has(> div[data-testid=\"stElementContainer\"] .inputs-v2-brain-state-empty) > div[data-testid=\"stLayoutWrapper\"] div[data-testid=\"stExpander\"] details>summary{background:#fff!important;border-left:0!important;}"
            ".inputs-v2-root .inputs-v2-design-guide-cta-gap{height:.8rem;}"
            "div[data-testid=\"stButton\"]>button{width:100%;border-radius:8px;}"
            "div[data-testid=\"stButton\"]>button:not(:disabled){background:#4263eb;color:#fff;border-color:#4263eb;}"
            "div[data-testid=\"stButton\"]>button:disabled{background:#f1f3f5;color:#868e96;border-color:#ced4da;}"
            "div[class*=\"st-key-v2_design_guide_apply_scope_fail\"] button:not(:disabled),div[class*=\"st-key-v2_design_guide_apply_scope_blocked\"] button:not(:disabled){background:#e03131 !important;border-color:#e03131 !important;color:#fff !important;}"
            "div[class*=\"st-key-v2_design_guide_apply_scope_pass\"] button:not(:disabled){background:#2f9e44 !important;border-color:#2f9e44 !important;color:#fff !important;}"
            "div[class*=\"st-key-v2_design_guide_apply_scope_optimise\"] button:not(:disabled){background:#4263eb !important;border-color:#4263eb !important;color:#fff !important;}"
            "div[class*=\"st-key-v2_design_guide_apply_scope_warn\"] button:not(:disabled){background:#f08c00 !important;border-color:#f08c00 !important;color:#fff !important;}"
            "div[class*=\"st-key-v2_design_guide_apply_scope_info\"] button:not(:disabled){background:#64748b !important;border-color:#64748b !important;color:#fff !important;}"
            # Header action styling is intentionally broad for the page shell;
            # these higher-specificity rules keep the Design Brain CTA tied to
            # its own semantic state when both regions share a Streamlit
            # vertical block.
            "div[data-testid=\"stVerticalBlock\"][class*=\"st-key-v2_design_guide_apply_scope_fail\"] div[data-testid=\"stButton\"]>button:not(:disabled),div[data-testid=\"stVerticalBlock\"][class*=\"st-key-v2_design_guide_apply_scope_blocked\"] div[data-testid=\"stButton\"]>button:not(:disabled){background:#e03131 !important;border-color:#e03131 !important;color:#fff !important;}"
            "div[data-testid=\"stVerticalBlock\"][class*=\"st-key-v2_design_guide_apply_scope_pass\"] div[data-testid=\"stButton\"]>button:not(:disabled){background:#2f9e44 !important;border-color:#2f9e44 !important;color:#fff !important;}"
            "div[data-testid=\"stVerticalBlock\"][class*=\"st-key-v2_design_guide_apply_scope_optimise\"] div[data-testid=\"stButton\"]>button:not(:disabled){background:#4263eb !important;border-color:#4263eb !important;color:#fff !important;}"
            "div[data-testid=\"stVerticalBlock\"][class*=\"st-key-v2_design_guide_apply_scope_warn\"] div[data-testid=\"stButton\"]>button:not(:disabled){background:#f08c00 !important;border-color:#f08c00 !important;color:#fff !important;}"
            "div[data-testid=\"stVerticalBlock\"][class*=\"st-key-v2_design_guide_apply_scope_info\"] div[data-testid=\"stButton\"]>button:not(:disabled){background:#64748b !important;border-color:#64748b !important;color:#fff !important;}"
            "</style>"
             '<div class="inputs-v2-root"><div class="inputs-v2-card-label">Design Guide</div>'
            '<div data-testid="inputs-v2-design-brain-runtime-loading" class="inputs-v2-brain-runtime-loading-shell" role="status" aria-live="polite">'
            '<span class="inputs-v2-brain-runtime-loading-icon" aria-hidden="true">&#129504;</span>'
             '<span class="inputs-v2-brain-runtime-loading-copy">Updating Design Guide'
            '<span class="inputs-v2-brain-runtime-loading-dot"></span>'
            '<span class="inputs-v2-brain-runtime-loading-dot"></span>'
            '<span class="inputs-v2-brain-runtime-loading-dot"></span>'
            '</span></div></div>'
            f'<span data-testid="v2-design-guide-card" class="inputs-v2-brain-state-{html.escape(state)}" aria-hidden="true">{html.escape(family)}</span>',
            unsafe_allow_html=True,
        )

        if no_design_actions:
            st_module.markdown(
                '<span class="inputs-v2-brain-state-empty" aria-hidden="true">NO_DESIGN_ACTIONS</span>',
                unsafe_allow_html=True,
            )
            with st_module.expander(
                 "**NO LOADS**  **Design Guide waiting for actions**  |  Governing utilisation: 0.00",
                expanded=False,
            ):
                st_module.markdown(
                    '<div class="inputs-v2-root inputs-v2-design-guide-copy empty">'
                     'No design actions entered. Add loads and the Design Guide will check and optimise your beam.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            return

        with st_module.expander(summary_label, expanded=False):
            st_module.markdown(
                f'<div class="inputs-v2-root inputs-v2-design-guide-copy {html.escape(state)}">'
                f'<div>{html.escape(summary).replace(chr(10), "<br>")}</div>'
                + (f'<div class="inputs-v2-design-guide-meta">{html.escape(clause_text)}</div>' if clause_text else "")
                + '</div>',
                unsafe_allow_html=True,
            )
        st_module.markdown(
            '<div class="inputs-v2-root inputs-v2-design-guide-cta-gap"></div>',
            unsafe_allow_html=True,
        )

        # Apply identity is bound by the application workspace immediately
        # before rendering.  The renderer may display/queue that exact payload
        # but cannot manufacture revision evidence or Apply authority itself.
        payload = dict(
            apply_payload
            if apply_payload is not None
            else result.apply_payload or {}
        )
        enabled = bool(cta.get("enabled") or cta.get("actionable")) and bool(payload.get("updates") or payload.get("resolved_candidate_updates"))
        if enabled:
            if apply_handler is None:
                raise RuntimeError(
                    "Actionable Design Brain publication has no typed Apply handler"
                )
            label = _text(cta.get("label"), "Apply recommendation")
            # Scope the state styling to this card's own Apply button.  A
            # broad ancestor ``:has(...)`` selector can see unrelated/stale
            # cards elsewhere in the page and incorrectly turn an ACTION
            # button red when the current card is blue.
            with st_module.container(key=f"v2_design_guide_apply_scope_{state}"):
                # Queue the immutable, pre-verified publication in Streamlit's
                # button callback.  Callbacks run before the fragment body is
                # re-entered, so the owning workspace consumes and commits the
                # command before rendering any summary, diagram or Design
                # Brain region.  Handling the click after ``button()`` returned
                # rendered the old summary first and then needed a second
                # rerun, which exposed mixed revisions on cold hosted sessions.
                st_module.button(
                    label,
                    key=f"v2_design_guide_apply_{_text(publication.get('publication_hash'), 'current')}",
                    use_container_width=True,
                    on_click=_commit_v2_design_guide_apply,
                    args=(st_module, payload, apply_handler),
                )


__all__ = [
    "render_v2_design_guide_card",
    "render_v2_design_guide_loading_shell",
]
