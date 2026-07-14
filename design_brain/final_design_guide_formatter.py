"""Clean final Design Guide card formatter.

This module formats only from FinalDesignGuidePublication. It does not accept
legacy guidance-item dictionaries, old page render models, session state,
candidate-search internals, or apply-routing objects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from design_brain.final_design_guide_formatting_contract import (
    contract_hash,
    current_row_contract,
    outcome_state_mapping,
    preview_row_contract,
    required_test_ids,
    section_order,
    status_colour_contract,
)
from design_brain.final_publication import (
    FinalDesignGuidePublication,
    stable_final_publication_hash,
)

_FINAL_DESIGN_GUIDE_BLOCKER_COPY = {
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


@dataclass(frozen=True)
class FinalDesignGuideFormatSection:
    title: str
    rows: tuple[dict[str, Any], ...] = ()
    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideCardFormat:
    selected_family: str
    outcome_state: str
    tone: str
    tone_source: str
    title: str
    badge: str
    summary: str
    blocker_explanation: str
    governing_label: str
    cta: dict[str, Any] = field(default_factory=dict)
    sections: tuple[FinalDesignGuideFormatSection, ...] = ()
    required_test_ids: tuple[str, ...] = ()
    publication_hash: str | None = None
    display_hash: str | None = None
    cta_hash: str | None = None
    evidence_hash: str | None = None
    contract_hash: str | None = None
    format_hash: str | None = None
    source: str = "FinalDesignGuidePublication"
    renderer_driving: bool = False
    product_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "sections": tuple(section.to_dict() for section in self.sections),
        }


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _family_colour_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for tone, row in status_colour_contract().items():
        for family in dict(row).get("families") or ():
            out[str(family).strip().upper()] = str(tone).strip().lower()
    return out


def _tone_from_display(display_colour: str | None) -> str | None:
    value = str(display_colour or "").strip().lower()
    if value in {"red", "fail", "failure", "error"}:
        return "red"
    if value in {"green", "pass", "success", "accepted"}:
        return "green"
    if value in {"blue", "optimise", "optimize", "optimisation", "optimization", "efficiency"}:
        return "blue"
    if value in {"amber", "warn", "warning"}:
        return "amber"
    if value in {"grey", "gray", "info", "proof_pending"}:
        return "grey"
    return None


def _tone_for_publication(publication: FinalDesignGuidePublication) -> tuple[str, str]:
    selected_family = str(publication.selected_family or publication.evidence.selected_family or "").strip().upper()
    family_tone = _family_colour_map().get(selected_family)
    outcome = str(publication.outcome_state or "").strip().upper()
    state_row = dict(outcome_state_mapping().get(outcome) or {})
    explicit = str(state_row.get("tone") or "").strip().lower()
    if explicit and explicit != "family_contract":
        return explicit, f"outcome_state:{outcome}"
    if family_tone:
        return family_tone, f"family_contract:{selected_family}"
    display_tone = _tone_from_display(publication.display.colour_state or publication.display.bucket or publication.display.status)
    if display_tone:
        return display_tone, "publication.display"
    if outcome == "PASS":
        return "green", "outcome_state:PASS:fallback"
    if outcome in {"ACTION", "BLOCKED", "ERROR"}:
        return "red", f"outcome_state:{outcome}:fallback"
    return "grey", "proof_pending:fallback"


def _default_badge(outcome_state: str) -> str:
    row = dict(outcome_state_mapping().get(str(outcome_state or "").strip().upper()) or {})
    return _text(row.get("default_badge"), default="INFO")


_LEGACY_FINAL_BADGE_OUTCOME = {
    "NEXT": "ACTION",
    "RECOMMEND": "ACTION",
    "REPAIR": "ACTION",
    "TIGHTEN": "ACTION",
    "GOOD": "PASS",
    "OK": "PASS",
    "START": "PROOF_PENDING",
    "ALSO": "PROOF_PENDING",
    "WARN": "BLOCKED",
}


def resolve_final_design_guide_publication_badge(outcome_state: str) -> str:
    """Resolve the visible badge from the publication outcome contract.

    Legacy guidance items used badges such as GOOD, NEXT, or RECOMMEND. The
    clean final card renders publication outcomes only, so the visible badge is
    normalised to the outcome state's contract badge while leaving title,
    summary, CTA, and family evidence untouched.
    """

    return _default_badge(outcome_state)


def normalise_final_design_guide_legacy_badge(badge: Any) -> str:
    """Map old live-render badges to the final formatting badge vocabulary."""

    legacy = str(badge or "").strip().upper()
    if not legacy:
        return resolve_final_design_guide_publication_badge("PROOF_PENDING")
    outcome = _LEGACY_FINAL_BADGE_OUTCOME.get(legacy, legacy)
    return resolve_final_design_guide_publication_badge(outcome)


def _row_tone(status: Any) -> str:
    status_text = str(status or "").strip().upper()
    mapping = dict(current_row_contract().get("tone_mapping") or {})
    return str(mapping.get(status_text) or "grey").strip().lower()


def resolve_final_design_guide_status_tone(status: Any) -> str:
    """Resolve a current-row status tone from the formatting contract."""
    return _row_tone(status)


def clean_final_design_guide_reason_text(text: Any, *, fallback: str = "") -> str:
    """Clean final Design Guide reason copy without reading legacy item state."""
    raw = str(text or "").strip()
    if not raw:
        raw = fallback
    if not raw:
        return ""
    lowered = raw.lower()
    for token, replacement in _FINAL_DESIGN_GUIDE_BLOCKER_COPY.items():
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


def resolve_final_design_guide_why_body(guidance_why: Any = None, reasoning: Any = None) -> str:
    """Resolve compact why copy from explicit primitive fields."""
    w = str(guidance_why or "").strip()
    if w:
        if w.lower().startswith("why:"):
            return w[4:].strip() or w
        return w
    r = str(reasoning or "").strip()
    if not r:
        return ""
    if r.lower().startswith("why:"):
        return r[4:].strip() or r
    return r


def resolve_final_design_guide_failure_engineering_cause_text(failure_detail_text: Any) -> str:
    """Map detailed failure text to visible engineering-cause copy."""
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
        or ("phi" in detail and "mu" in detail)
        or "m_u" in detail
        or "mu*" in detail
    ):
        return "Applied design moment exceeds the available design bending capacity."
    return "The current section or reinforcement does not satisfy the named detailed bending check."


def build_final_design_guide_reason_display_rows(reasons: list[dict]) -> list[dict]:
    """Build Status section rows from current reason records."""
    rows: list[dict[str, Any]] = []
    for row in list(reasons or []):
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        rows.append(
            {
                "test_label": label.strip().lower().replace(" ", "-") or "reason",
                "label": label,
                "text": clean_final_design_guide_reason_text(row.get("text")),
            }
        )
    return rows


def build_final_design_guide_preview_display_rows(preview: dict, util_formatter) -> list[dict]:
    """Build Preview section rows from current preview records."""
    rows: list[dict[str, Any]] = []
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


def _current_rows(publication: FinalDesignGuidePublication) -> tuple[dict[str, Any], ...]:
    sections = _mapping(publication.display.expanded_evidence_sections)
    raw_rows = sections.get("current")
    if not isinstance(raw_rows, list):
        raw_rows = []
    required = tuple(str(value) for value in current_row_contract().get("required_fields") or ())
    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        status = _text(row.get("status"), default="-")
        out = {
            "family": _text(row.get("family"), row.get("key"), default=""),
            "label": _text(row.get("label"), row.get("family"), default=""),
            "value": _text(row.get("value"), row.get("util"), default="-"),
            "status": status,
            "tone": _text(row.get("tone"), _row_tone(status), default="grey"),
        }
        for field_name in required:
            out.setdefault(field_name, "")
        rows.append(out)
    return tuple(rows)


def _preview_rows(publication: FinalDesignGuidePublication) -> tuple[dict[str, Any], ...]:
    sections = _mapping(publication.display.expanded_evidence_sections)
    raw_display_rows = sections.get("preview_display_rows")
    required = tuple(str(value) for value in preview_row_contract().get("required_fields") or ())
    rows: list[dict[str, Any]] = []
    if isinstance(raw_display_rows, list):
        for row in raw_display_rows:
            if not isinstance(row, dict):
                continue
            out = {
                "family": _text(row.get("family"), default=""),
                "label": _text(row.get("label"), row.get("family"), default=""),
                "before": _text(row.get("before"), default="-"),
                "after": _text(row.get("after"), default="-"),
            }
            for field_name in required:
                out.setdefault(field_name, "")
            rows.append(out)
        return tuple(rows)

    raw_preview = sections.get("preview")
    if isinstance(raw_preview, dict):
        for family, row in sorted(raw_preview.items(), key=lambda item: str(item[0])):
            if not isinstance(row, dict):
                continue
            before = _text(row.get("before"), row.get("before_util"), row.get("current"), default="-")
            after = _text(row.get("after"), row.get("after_util"), row.get("proposed"), default="-")
            rows.append(
                {
                    "family": str(family),
                    "label": _text(row.get("label"), str(family).title(), default=str(family)),
                    "before": before,
                    "after": after,
                }
            )
    return tuple(rows)


def _reason_rows(publication: FinalDesignGuidePublication) -> tuple[dict[str, Any], ...]:
    sections = _mapping(publication.display.expanded_evidence_sections)
    raw_rows = sections.get("reason_display_rows") or sections.get("reasons")
    rows: list[dict[str, Any]] = []
    if isinstance(raw_rows, list):
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            label = _text(row.get("label"), default="Result")
            text = _text(row.get("text"), default="")
            if not text:
                continue
            rows.append(
                {
                    "test_label": _text(row.get("test_label"), label.lower().replace(" ", "-"), default="result"),
                    "label": label,
                    "text": text,
                }
            )
    if not rows and publication.blocker_reason:
        rows.append(
            {
                "test_label": "blocker",
                "label": "Blocker",
                "text": str(publication.blocker_reason),
            }
        )
    return tuple(rows)


def _details_rows(publication: FinalDesignGuidePublication) -> tuple[dict[str, Any], ...]:
    evidence = publication.evidence.to_dict()
    rows = [
        {"label": "Selected family", "value": publication.selected_family or ""},
        {"label": "Publication hash", "value": publication.publication_hash or ""},
    ]
    if evidence.get("compute_publication_evidence_hash"):
        rows.append({"label": "Compute evidence hash", "value": evidence["compute_publication_evidence_hash"]})
    return tuple(rows)


def _sections(publication: FinalDesignGuidePublication) -> tuple[FinalDesignGuideFormatSection, ...]:
    section_map = {
        "Current": FinalDesignGuideFormatSection("Current", _current_rows(publication), bool(_current_rows(publication))),
        "Preview after proposed change": FinalDesignGuideFormatSection(
            "Preview after proposed change",
            _preview_rows(publication),
            bool(_preview_rows(publication)),
        ),
        "Status": FinalDesignGuideFormatSection("Status", _reason_rows(publication), bool(_reason_rows(publication))),
        "Blocker evidence": FinalDesignGuideFormatSection(
            "Blocker evidence",
            ({"label": "Blocker", "text": publication.blocker_reason},) if publication.blocker_reason else (),
            bool(publication.blocker_reason),
        ),
        "Exact stop": FinalDesignGuideFormatSection(
            "Exact stop",
            (dict(publication.exact_stop_proof),) if publication.exact_stop_proof else (),
            bool(publication.exact_stop_proof),
        ),
        "Target band": FinalDesignGuideFormatSection(
            "Target band",
            (dict(publication.target_band_proof),) if publication.target_band_proof else (),
            bool(publication.target_band_proof),
        ),
        "Details": FinalDesignGuideFormatSection("Details", _details_rows(publication), True),
    }
    return tuple(section_map[name] for name in section_order() if name in section_map)


def _cta(publication: FinalDesignGuidePublication) -> dict[str, Any]:
    cta = publication.cta
    return {
        "enabled": bool(cta.enabled),
        "actionable": bool(cta.actionable),
        "label": _text(cta.label, default=""),
        "disabled_reason": _text(cta.disabled_reason, default=""),
        "action_type": _text(cta.action_type, default=""),
        "apply_payload_fingerprint": _text(cta.apply_payload_fingerprint, default=""),
        "button_contract_hash": _text(cta.button_contract_hash, default=""),
        "source_candidate_id": _text(cta.source_candidate_id, default=""),
    }


def build_final_design_guide_card_format(
    publication: FinalDesignGuidePublication,
) -> FinalDesignGuideCardFormat:
    """Build a clean display-format model from final publication truth only."""

    if not isinstance(publication, FinalDesignGuidePublication):
        raise TypeError("publication must be a FinalDesignGuidePublication")

    tone, tone_source = _tone_for_publication(publication)
    outcome_state = str(publication.outcome_state or "PROOF_PENDING").strip().upper()
    display = publication.display
    evidence = publication.evidence
    cta = _cta(publication)
    selected_family = _text(publication.selected_family, evidence.selected_family, default="")
    blocker = _text(display.blocker_explanation, publication.blocker_reason, evidence.blocker_reason, default="")
    title = _text(display.title, default="Design guidance")
    badge = resolve_final_design_guide_publication_badge(outcome_state)
    summary = _text(display.summary, blocker, default="")
    sections = _sections(publication)
    display_hash = stable_final_publication_hash(display.to_dict())
    cta_hash = stable_final_publication_hash(publication.cta.to_dict())
    evidence_hash = stable_final_publication_hash(evidence.to_dict())
    payload = {
        "selected_family": selected_family,
        "outcome_state": outcome_state,
        "tone": tone,
        "tone_source": tone_source,
        "title": title,
        "badge": badge,
        "summary": summary,
        "blocker_explanation": blocker,
        "governing_label": _text(display.status, selected_family, outcome_state, default=outcome_state),
        "cta": cta,
        "sections": tuple(section.to_dict() for section in sections),
        "required_test_ids": required_test_ids(),
        "publication_hash": publication.publication_hash,
        "display_hash": display_hash,
        "cta_hash": cta_hash,
        "evidence_hash": evidence_hash,
        "contract_hash": contract_hash(),
    }
    return FinalDesignGuideCardFormat(
        selected_family=selected_family,
        outcome_state=outcome_state,
        tone=tone,
        tone_source=tone_source,
        title=title,
        badge=badge,
        summary=summary,
        blocker_explanation=blocker,
        governing_label=payload["governing_label"],
        cta=cta,
        sections=sections,
        required_test_ids=required_test_ids(),
        publication_hash=publication.publication_hash,
        display_hash=display_hash,
        cta_hash=cta_hash,
        evidence_hash=evidence_hash,
        contract_hash=contract_hash(),
        format_hash=stable_final_publication_hash(payload),
    )


__all__ = [
    "FinalDesignGuideCardFormat",
    "FinalDesignGuideFormatSection",
    "build_final_design_guide_preview_display_rows",
    "build_final_design_guide_reason_display_rows",
    "build_final_design_guide_card_format",
    "clean_final_design_guide_reason_text",
    "normalise_final_design_guide_legacy_badge",
    "resolve_final_design_guide_failure_engineering_cause_text",
    "resolve_final_design_guide_publication_badge",
    "resolve_final_design_guide_status_tone",
    "resolve_final_design_guide_why_body",
]
