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

    title = _text(display.get("title"), "UNKNOWN")
    badge = _text(display.get("v2_badge"), _text(display.get("badge"), _text(display.get("status"), "INFO"))).upper()
    family = _text(display.get("selected_family_id"), _text(result.governing_family, "UNKNOWN"))
    summary = _text(display.get("v2_advice_text"), _text(primary.get("rationale"), _text(primary.get("summary"), "No recommendation published.")))
    clause_refs = list((display.get("clause_metadata") or {}).get("references") or [])
    clause_text = ", ".join(_text(ref) for ref in clause_refs[:3])
    state = _text(display.get("v2_state_class"), _text(display.get("colour_state"), "info")).lower()

    with design_guide_slot.container():
        st_module.markdown(
            "<style>"
            ".inputs-v2-root .inputs-v2-card-label{color:#343a40;font-size:1.05rem;font-weight:700;border-bottom:1px solid #dce3ec;padding-bottom:.55rem;margin:.25rem 0 .85rem;}"
            ".inputs-v2-root .inputs-v2-design-guide-item{border-top:1px solid rgba(49,51,63,.08);border-left:4px solid #2563eb;border-radius:10px;padding:.92rem .95rem;margin:.7rem 0;line-height:1.42;background:rgba(37,99,235,.08);}"
            ".inputs-v2-root .inputs-v2-design-guide-item.pass{background:rgba(47,158,68,.08);border-left-color:#2f9e44;}"
            ".inputs-v2-root .inputs-v2-design-guide-item.warn{background:rgba(240,140,0,.08);border-left-color:#f08c00;}"
            ".inputs-v2-root .inputs-v2-design-guide-item.fail{background:rgba(224,49,49,.08);border-left-color:#e03131;}"
            ".inputs-v2-root .inputs-v2-design-guide-item.optimise{background:rgba(37,99,235,.08);border-left-color:#2563eb;}"
            ".inputs-v2-root .inputs-v2-design-guide-item.info{background:rgba(100,116,139,.08);border-left-color:#64748b;}"
            ".inputs-v2-root .inputs-v2-design-guide-head{display:flex;align-items:center;gap:.5rem;margin-bottom:.32rem;}"
            ".inputs-v2-root .inputs-v2-design-guide-badge{font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;padding:.18rem .48rem;border-radius:999px;color:#fff;background:#2563eb;}"
            ".inputs-v2-root .inputs-v2-design-guide-badge.pass{background:#2f9e44;}.inputs-v2-root .inputs-v2-design-guide-badge.fail{background:#e03131;}.inputs-v2-root .inputs-v2-design-guide-badge.optimise{background:#2563eb;}.inputs-v2-root .inputs-v2-design-guide-badge.info{background:#64748b;}"
            ".inputs-v2-root .inputs-v2-design-guide-title{font-weight:800;color:#0f172a;}.inputs-v2-root .inputs-v2-design-guide-meta{color:#64748b;font-size:.82rem;margin-top:.28rem;}"
            "</style>"
            '<div class="inputs-v2-root"><div class="inputs-v2-card-label">Design Brain</div></div>'
            f'<div data-testid="v2-design-guide-card" class="inputs-v2-root inputs-v2-design-guide-item {html.escape(state)}">'
            f'<div class="inputs-v2-design-guide-head"><span class="inputs-v2-design-guide-badge {html.escape(state)}">{html.escape(badge)}</span>'
            f'<span class="inputs-v2-design-guide-title">{html.escape(title)}</span></div>'
            f'<div>{html.escape(summary).replace(chr(10), "<br>")}</div>'
            + (f'<div class="inputs-v2-design-guide-meta">{html.escape(clause_text)}</div>' if clause_text else "")
            + '</div>',
            unsafe_allow_html=True,
        )

        payload = dict(result.apply_payload or {})
        enabled = bool(cta.get("enabled") or cta.get("actionable")) and bool(payload.get("updates") or payload.get("resolved_candidate_updates"))
        if enabled:
            label = _text(cta.get("label"), "Apply recommendation")
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
        elif family not in {"BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "COMBINED_OVERDESIGN", "TARGET_BAND_REACHED"}:
            reason = _text(cta.get("disabled_reason"), "No approved candidate is available for Apply.")
            st_module.button("Apply recommendation", key="v2_design_guide_apply_disabled", disabled=True, use_container_width=True, help=reason)
            st_module.caption(reason.replace("_", " "))


__all__ = ["render_v2_design_guide_card"]
