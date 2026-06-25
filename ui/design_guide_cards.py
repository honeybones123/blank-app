"""Pure Design Guide card display helpers."""

from __future__ import annotations

import hashlib
import html
import json
import re

from ui.design_guide_models import DesignGuideCardDataAttributeFields, DesignGuideCardRenderModel


_DESIGN_GUIDE_CARD_DATA_ATTRIBUTE_FIELDS = (
    ("data-selected-family-id", "selected_family_id"),
    ("data-selected-family", "selected_family"),
    ("data-selection-reason", "selection_reason"),
    ("data-published-family-id", "published_family_id"),
    ("data-cta-family-id", "cta_family_id"),
    ("data-apply-payload-family-id", "apply_payload_family_id"),
    ("data-candidate-family-id", "candidate_family_id"),
    ("data-card-family-id", "card_family_id"),
    ("data-family-selection-source", "family_selection_source"),
    ("data-family-selection-contract", "family_selection_contract"),
    ("data-family-chooser-contract", "family_chooser_contract"),
    ("data-rejected-families", "rejected_families"),
    ("data-selection-evidence", "selection_evidence"),
    ("data-matched-family-ids", "matched_family_ids"),
    ("data-raw-state-flags", "raw_state_flags"),
    ("data-family-match-passed", "family_match_passed"),
    ("data-family-match-violation-reason", "family_match_violation_reason"),
    ("data-family-route-owner", "family_route_owner"),
    ("data-family-early-dispatch-used", "family_early_dispatch_used"),
    ("data-generic-one-click-solver-skipped", "generic_one_click_solver_skipped"),
    ("data-generic-target-band-search-skipped", "generic_target_band_search_skipped"),
    ("data-generic-optimisation-cleanup-skipped", "generic_optimisation_cleanup_skipped"),
    ("data-generic-publication-fallback-skipped", "generic_publication_fallback_skipped"),
    ("data-direct-target-band-bypassed-by-family-owner", "direct_target_band_bypassed_by_family_owner"),
    ("data-family-ladder-candidate-count", "family_ladder_candidate_count"),
    ("data-render-contract-enabled", "render_contract_enabled"),
    ("data-render-cta-enabled", "render_cta_enabled"),
    ("data-render-action-type", "render_action_type"),
    ("data-render-update-count", "render_update_count"),
    ("data-render-blocking-reason", "render_blocking_reason"),
    ("data-render-cta-payload-id", "render_cta_payload_id"),
    ("data-render-gate-condition", "render_gate_condition"),
    ("data-render-gate-pres-show-apply", "render_gate_pres_show_apply"),
    ("data-render-gate-effective-action", "render_gate_effective_action"),
    ("data-render-gate-terminal-exact", "render_gate_terminal_exact"),
    ("data-render-gate-button-enabled", "render_gate_button_enabled"),
    ("data-render-gate-vm-cta-enabled", "render_gate_vm_cta_enabled"),
)


_DESIGN_GUIDE_BLOCKER_COPY = {
    "candidate_post_click_bending_cleanup_no_serviceability_safe_arrangement": (
        "Trial bottom reinforcement reductions were exhausted. Further reduction would break serviceability, "
        "spacing, ductility, or detailing limits."
    ),
    "candidate_shear_cleanup_floor_no_links_remaining": (
        "Links are already removed. Further shear reduction would require geometry or bending changes."
    ),
    "shear_cleanup_floor_no_links_remaining": (
        "Links are already removed. Further shear reduction would require geometry or bending changes."
    ),
    "combined_active_failure_practical_ladder_exhausted": (
        "No practical combined strengthening candidate satisfies the required limit."
    ),
}


def _design_guide_card_data_attributes_html(data_attributes: dict) -> str:
    """Render already-resolved Design Guide card data attributes."""
    attrs = dict(data_attributes or {})
    return " ".join(
        f"{html_name}='{html.escape(str(attrs.get(key) or ''))}'"
        for html_name, key in _DESIGN_GUIDE_CARD_DATA_ATTRIBUTE_FIELDS
    )


def _assemble_design_guide_card_data_attribute_scalars(
    fields: DesignGuideCardDataAttributeFields,
) -> dict:
    """Serialise resolved Design Guide card fields into stable scalar attributes."""
    return {
        "selected_family_id": str(fields.selected_family_id or "").strip(),
        "selected_family": str(fields.selected_family or "").strip(),
        "selection_reason": str(fields.selection_reason or "").strip(),
        "published_family_id": str(fields.published_family_id or "").strip(),
        "cta_family_id": str(fields.cta_family_id or "").strip(),
        "apply_payload_family_id": str(fields.apply_payload_family_id or "").strip(),
        "candidate_family_id": str(fields.candidate_family_id or "").strip(),
        "card_family_id": str(fields.card_family_id or "").strip(),
        "family_selection_source": str(fields.family_selection_source or "").strip(),
        "family_selection_contract": str(fields.family_selection_contract or "").strip(),
        "family_chooser_contract": str(fields.family_chooser_contract or "").strip(),
        "rejected_families": json.dumps(fields.rejected_families or {}, sort_keys=True),
        "selection_evidence": json.dumps(fields.selection_evidence or {}, sort_keys=True),
        "matched_family_ids": json.dumps(fields.matched_family_ids or [], sort_keys=True),
        "raw_state_flags": json.dumps(fields.raw_state_flags or {}, sort_keys=True),
        "family_match_passed": str(fields.family_match_passed).strip(),
        "family_match_violation_reason": str(fields.family_match_violation_reason or "").strip(),
        "family_route_owner": str(fields.family_route_owner or "").strip(),
        "family_early_dispatch_used": str(fields.family_early_dispatch_used or "").strip(),
        "generic_one_click_solver_skipped": str(fields.generic_one_click_solver_skipped or "").strip(),
        "generic_target_band_search_skipped": str(fields.generic_target_band_search_skipped or "").strip(),
        "generic_optimisation_cleanup_skipped": str(fields.generic_optimisation_cleanup_skipped or "").strip(),
        "generic_publication_fallback_skipped": str(fields.generic_publication_fallback_skipped or "").strip(),
        "direct_target_band_bypassed_by_family_owner": str(
            fields.direct_target_band_bypassed_by_family_owner or ""
        ).strip(),
        "family_ladder_candidate_count": str(fields.family_ladder_candidate_count or "").strip(),
        "render_contract_enabled": str(fields.render_contract_enabled or "").strip(),
        "render_cta_enabled": str(fields.render_cta_enabled or "").strip(),
        "render_action_type": str(fields.render_action_type or "").strip(),
        "render_update_count": str(fields.render_update_count or "").strip(),
        "render_blocking_reason": str(fields.render_blocking_reason or "").strip(),
        "render_cta_payload_id": str(fields.render_cta_payload_id or "").strip(),
        "render_gate_condition": str(fields.render_gate_condition or "").strip(),
        "render_gate_pres_show_apply": str(fields.render_gate_pres_show_apply or "").strip(),
        "render_gate_effective_action": str(fields.render_gate_effective_action or "").strip(),
        "render_gate_terminal_exact": str(fields.render_gate_terminal_exact or "").strip(),
        "render_gate_button_enabled": str(fields.render_gate_button_enabled or "").strip(),
        "render_gate_vm_cta_enabled": str(fields.render_gate_vm_cta_enabled or "").strip(),
    }


def _guidance_card_why_body(item: dict) -> str:
    w = item.get("guidance_why")
    if isinstance(w, str) and w.strip():
        t = w.strip()
        if t.lower().startswith("why:"):
            return t[4:].strip() or t
        return t
    r = str(item.get("reasoning") or "").strip()
    if not r:
        return ""
    if r.lower().startswith("why:"):
        return r[4:].strip() or r
    return r


def _design_guide_text_html(text: object) -> str:
    """Escape display copy while preserving intentional line breaks and bullets."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    html_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            html_lines.append("")
        elif stripped.startswith("- "):
            html_lines.append("&bull; " + html.escape(stripped[2:]))
        else:
            html_lines.append(html.escape(line))
    return "<br>".join(html_lines)


def _design_guide_clean_main_card_text(text: object, *, fallback: str = "") -> str:
    raw = str(text or "").strip()
    if not raw:
        raw = fallback
    if not raw:
        return ""
    lowered = raw.lower()
    for token, replacement in _DESIGN_GUIDE_BLOCKER_COPY.items():
        if token in lowered:
            return replacement
    raw = re.sub(r"\bcandidate_[a-z0-9_:-]+\b", "checked candidate", raw, flags=re.I)
    raw = re.sub(r"\b[a-z0-9]+(?:_[a-z0-9]+){3,}\b", "checked rule", raw, flags=re.I)
    raw = raw.replace("actual value utilisation", "utilisation")
    raw = raw.replace("required limit <=", "limit")
    raw = raw.replace("limit/capacity -", "limit not published")
    raw = raw.replace("value -", "value not published")
    raw = raw.replace("failed not published", "no published failing rule")
    raw = re.sub(r"\s+", " ", raw).strip()
    raw_l = raw.lower()
    if raw_l.startswith("blocked because") or raw_l.startswith(
        (
            "bending is currently",
            "shear is currently",
            "shear links are already removed",
            "we checked a combined cleanup",
        )
    ) or ("the attempted design" in raw_l and "we are keeping" in raw_l):
        return raw if len(raw) <= 650 else raw[:647].rstrip() + "..."
    if len(raw) > 210:
        parts = re.split(r"(?<=[.!?])\s+", raw)
        raw = parts[0].strip() if parts and len(parts[0]) <= 210 else raw[:207].rstrip() + "..."
    return raw


def _design_guide_card_tone_for_status(status: str) -> str:
    label = str(status or "").strip().upper()
    if label == "FAIL":
        return "red"
    if label in {"NEAR LIMIT", "LOW UTILISATION", "LOW UTILIZATION", "WATCH", "WARN", "WARNING"}:
        return "amber"
    if label in {"PASS", "OK", "GOOD", "ACCEPTED"}:
        return "green"
    return "grey"


def _design_guide_failure_engineering_cause_text(failure_detail_text: str) -> str:
    detail = str(failure_detail_text or "").strip().lower()
    if not detail:
        return "The current section or reinforcement does not provide enough capacity for the applied demand."
    if "ductility" in detail or "k_u" in detail or "ku" in detail or "neutral axis" in detail:
        return "Reduce k_u / make the neutral axis shallower so the section remains ductile."
    if (
        "minimum tensile" in detail
        or "minimum reinforcement" in detail
        or "minimum reo" in detail
        or "as,min" in detail
        or "as_min" in detail
    ):
        return (
            "Minimum tensile reinforcement provides baseline tensile capacity, crack robustness, "
            "and protection against brittle under-reinforced behaviour."
        )
    if (
        "minimum design capacity" in detail
        or "minimum design strength" in detail
        or "minimum strength" in detail
        or "minimum moment" in detail
        or "m_min" in detail
        or "mmin" in detail
    ):
        return "The section must meet the code minimum design strength even when the applied demand is low."
    if (
        "positive bending" in detail
        or "flexural strength" in detail
        or "bending capacity" in detail
        or "phi" in detail and "mu" in detail
        or "m_u" in detail
        or "mu*" in detail
    ):
        return "Applied design moment exceeds the available design bending capacity."
    return "The current section or reinforcement does not satisfy the named detailed bending check."


def _design_guide_format_mm_value(value: object) -> str:
    try:
        numeric = float(value)
    except Exception:
        return str(value or "").strip() or "recorded"
    if abs(numeric - round(numeric)) <= 1e-9:
        return str(int(round(numeric)))
    return f"{numeric:.1f}".rstrip("0").rstrip(".")


def _design_guide_reason_display_rows(reasons: list[dict]) -> list[dict]:
    rows = []
    for row in list(reasons or []):
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        rows.append(
            {
                "test_label": label.strip().lower().replace(" ", "-") or "reason",
                "label": label,
                "text": _design_guide_clean_main_card_text(row.get("text")),
            }
        )
    return rows


def _design_guide_preview_display_rows(preview: dict, util_formatter) -> list[dict]:
    rows = []
    preview_d = dict(preview or {})
    for family_key, family_label in (
        ("bending", "Bending"),
        ("shear", "Shear"),
        ("crack", "Crack"),
        ("deflection", "Deflection"),
    ):
        row = dict(preview_d.get(family_key) or {})
        if not row:
            continue
        before = (
            f"{util_formatter(row.get('before_util'))} "
            f"{str(row.get('before_status') or '-').upper()}"
        ).strip()
        after = (
            f"{util_formatter(row.get('after_util'))} "
            f"{str(row.get('after_status') or '-').upper()}"
        ).strip()
        rows.append(
            {
                "family": family_key,
                "label": family_label,
                "before": before,
                "after": after,
            }
        )
    return rows


def _design_guide_dashboard_card_html_from_render_model(model: DesignGuideCardRenderModel) -> str:
    status = str(model.status or "info").strip().lower()
    pill = str(model.pill or "INFO").strip().upper()
    title = str(model.title or "Design guidance").strip()
    governing = str(model.governing_label or "").strip()
    summary_line = str(model.main_text or "").strip()
    card_class = str(model.card_class or "").strip()
    card_classes = f"{card_class} dg-card dg-card--{html.escape(status)}"
    toggle_id = "dg-toggle-" + hashlib.sha1(
        f"{status}|{pill}|{title}|{governing}|{summary_line}".encode("utf-8", errors="ignore")
    ).hexdigest()[:12]
    current_html = []
    marker_by_tone = {"green": "&check;", "amber": "&bull;", "red": "!", "grey": "i"}
    for row in list(model.current_rows or []):
        family = str(row.get("family") or "").strip().lower()
        label = str(row.get("label") or family.title()).strip()
        value = str(row.get("value") or "-").strip()
        row_status = str(row.get("status") or "-").strip().upper()
        tone = str(row.get("tone") or "grey").strip().lower()
        current_html.append(
            "<div class='dg-current-chip dg-current-chip--{tone}' data-testid='design-guide-current-{family}'>"
            "<span class='dg-current-marker'>{marker}</span>"
            "<span><div class='dg-current-main'>{label} {value}</div>"
            "<div class='dg-current-status'>{status_text}</div></span>"
            "</div>".format(
                tone=html.escape(tone),
                family=html.escape(family),
                marker=marker_by_tone.get(tone, "i"),
                label=html.escape(label),
                value=html.escape(value),
                status_text=html.escape(row_status),
            )
        )
    reason_html = []
    for row in list(model.reason_display_rows or []):
        reason_html.append(
            "<div class='dg-reason-row' data-testid='design-guide-reason-{test_label}'>"
            "<span class='dg-reason-icon'>i</span>"
            "<span class='dg-reason-label'>{label}</span>"
            "<span class='dg-reason-text'>{text}</span>"
            "</div>".format(
                test_label=html.escape(str(row.get("test_label") or "reason")),
                label=html.escape(str(row.get("label") or "")),
                text=html.escape(str(row.get("text") or "")),
            )
        )
    preview_html = []
    for row in list(model.preview_display_rows or []):
        preview_html.append(
            "<div class='dg-preview-row' data-testid='design-guide-preview-{family}'>"
            "{label}: {before} &rarr; {after}</div>".format(
                family=html.escape(str(row.get("family") or "")),
                label=html.escape(str(row.get("label") or "")),
                before=html.escape(str(row.get("before") or "")),
                after=html.escape(str(row.get("after") or "")),
            )
        )
    summary_html = (
        f"<div class='dg-summary-line' data-testid='design-guide-collapsed-summary'>{html.escape(summary_line)}</div>"
        if summary_line
        else ""
    )
    preview_section = (
        "<div class='dg-section-title'>Preview after proposed change</div>"
        f"<div class='dg-preview-grid' data-testid='design-guide-preview-row'>{''.join(preview_html)}</div>"
        if preview_html
        else ""
    )
    ladder_stop_section = str(model.ladder_stop_html or "")
    current_section = (
        "<div class='dg-current-title'>Current</div>"
        f"<div class='dg-current-grid' data-testid='design-guide-current-row'>{''.join(current_html)}</div>"
        if current_html
        else ""
    )
    details_section = ""
    if model.details_enabled:
        details_section = "".join(
            [
                "<details class='dg-details-row' data-testid='design-guide-details'>",
                "<summary>&gt; Details</summary>",
                f"<pre class='dg-details-body'>{html.escape(str(model.details_text or ''))}</pre>",
                "</details>",
            ]
        )
    data_attrs_html = _design_guide_card_data_attributes_html(dict(model.data_attributes or {}))
    return "".join(
        [
            (
                f"<details class='{card_classes}' data-testid='design-guide-card' id='{html.escape(toggle_id)}' "
                f"{data_attrs_html}>"
            ),
            "<summary class='dg-header' data-testid='design-guide-collapsible-header'>",
            "<span class='dg-header-top'>",
            "<span class='dg-header-left'>",
            f"<span class='dg-status-pill dg-status-pill--{html.escape(status)}' data-testid='design-guide-status-pill'>{html.escape(pill)}</span>",
            f"<span class='dg-title' data-testid='design-guide-title'>{html.escape(title)}</span>",
            "</span>",
            "<span class='dg-header-right'>",
            f"<span class='dg-util-pill' data-testid='design-guide-governing-utilisation'>{html.escape(governing)}</span>",
            "<span class='dg-expand-toggle' data-testid='design-guide-expand-toggle' aria-hidden='true'>&rsaquo;</span>",
            "</span>",
            "</span>",
            summary_html,
            "</summary>",
            "<div class='dg-expanded-body' data-testid='design-guide-expanded-body'>",
            current_section,
            preview_section,
            f"<div class='dg-section-title'>{html.escape(str(model.section_title or 'Status'))}</div>",
            f"<div class='dg-reason-list' data-testid='design-guide-main-explanation'>{''.join(reason_html)}</div>",
            ladder_stop_section,
            details_section,
            "</div>",
            "</details>",
        ]
    )
