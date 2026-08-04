"""V2 Design Guide card rendered from the neutral publication contract.

This module deliberately knows nothing about the V2 implementation.  It is a
presentation adapter: the selected DesignBrainService supplies an immutable
result and this renderer turns its display/CTA models into the V2 card visual.
"""

from __future__ import annotations

import html
from typing import Any

from application.contracts.design_brain import AuthoritativeDesignResult


def _text(value: Any, fallback: str = "") -> str:
    value = str(value or "").strip()
    return value or fallback


def render_v2_design_guide_card(
    *,
    st_module: Any,
    design_guide_slot: Any,
    result: AuthoritativeDesignResult,
) -> None:
    """Render the replacement V2 card in the existing Design Guide slot."""

    display = dict(result.display_model or {})
    cta = dict(result.cta_model or {})
    publication = dict(result.final_publication or {})
    nested = dict(publication.get("final_design_guide_publication") or publication)
    guidance_items = list(nested.get("guidance_items") or [])
    primary = dict(guidance_items[0]) if guidance_items and isinstance(guidance_items[0], dict) else {}

    title = _text(display.get("title"), "Design recommendation")
    badge = _text(display.get("badge"), _text(display.get("status"), "INFO")).upper()
    family = _text(display.get("selected_family_id"), _text(result.governing_family, "UNKNOWN"))
    summary = _text(primary.get("rationale"), _text(primary.get("summary"), _text(display.get("summary"), "No recommendation published.")))
    clause_refs = list((display.get("clause_metadata") or {}).get("references") or [])
    clause_text = ", ".join(_text(ref) for ref in clause_refs[:3])
    state = _text(display.get("colour_state"), "info").lower()
    colours = {
        "action": ("#eef3ff", "#4263eb"),
        "pass": ("#edf8ef", "#2f9e44"),
        "blocked": ("#fff0f0", "#e03131"),
        "fail": ("#fff0f0", "#e03131"),
        "info": ("#f1f3f5", "#64748b"),
    }
    background, border = colours.get(state, colours["info"])

    with design_guide_slot.container():
        st_module.markdown(
            "<div style=\"font-size:1.15rem;font-weight:700;margin:0 0 .75rem 0;\">Design Guide</div>"
            f"<div data-testid=\"v2-design-guide-card\" style=\"background:{background};border:1px solid {border};border-left:5px solid {border};border-radius:10px;padding:14px 16px;margin-bottom:8px;\">"
            f"<div style=\"display:flex;align-items:center;gap:10px;flex-wrap:wrap;\">"
            f"<span style=\"background:{border};color:#fff;border-radius:999px;padding:4px 12px;font-size:.75rem;font-weight:700;\">{html.escape(badge)}</span>"
            f"<span style=\"font-weight:700;color:#202938;\">{html.escape(title)}</span>"
            f"<span style=\"margin-left:auto;color:#334155;font-size:.78rem;\">{html.escape(family)}</span>"
            "</div>"
            f"<div style=\"margin-top:10px;color:#263241;line-height:1.45;\">{html.escape(summary)}</div>"
            + (f"<div style=\"margin-top:8px;color:#526173;font-size:.78rem;\">{html.escape(clause_text)}</div>" if clause_text else "")
            + "</div>",
            unsafe_allow_html=True,
        )

        payload = dict(result.apply_payload or {})
        enabled = bool(cta.get("enabled") or cta.get("actionable")) and bool(payload.get("updates") or payload.get("resolved_candidate_updates"))
        if enabled:
            label = _text(cta.get("label"), "Review proposed design before Apply")
            pressed = st_module.button(
                label,
                key=f"v2_design_guide_apply_{_text(publication.get('publication_hash'), 'current')}",
                use_container_width=True,
            )
            if pressed:
                # Reuse the existing revision/stale-candidate Apply transaction
                # boundary.  Only the visual card changes; Apply authority does
                # not move into the renderer.
                st_module.session_state["_inputs_action_apply_recommendation_payload"] = payload
                st_module.session_state["_inputs_action_apply_recommendation"] = True
                st_module.rerun()
        else:
            reason = _text(cta.get("disabled_reason"), "No approved candidate is available for Apply.")
            st_module.button("Apply recommendation", key="v2_design_guide_apply_disabled", disabled=True, use_container_width=True, help=reason)
            st_module.caption(reason.replace("_", " "))


__all__ = ["render_v2_design_guide_card"]
