"""Presentation-only boundary for selected FamilyResult display models."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any

from design_brain.display_formatting_contract import (
    contract_hash,
    required_sections,
    status_colour_contract,
)
from design_brain.shared.schemas import FamilyResult


@dataclass(frozen=True)
class DisplaySection:
    title: str
    items: tuple[dict[str, Any], ...] = ()
    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DisplayModel:
    family_id: str
    status: str
    tone: str
    colour: str
    icon: str
    sections: tuple[DisplaySection, ...]
    contract_version: str
    source_family_result_hash: str
    presentation_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "sections": tuple(section.to_dict() for section in self.sections),
        }


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _normalise_item(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if value is None:
        return {}
    return {"value": value}


def _family_result_engineering_payload(result: FamilyResult) -> dict[str, Any]:
    return {
        "family_id": result.family_id,
        "is_applicable": result.is_applicable,
        "governing_score": result.governing_score,
        "status": result.status,
        "selected_candidate": result.selected_candidate,
        "updates": result.updates,
        "blockers": result.blockers,
        "evidence": result.evidence,
        "lock_proof": result.lock_proof,
    }


def _family_colour(family_id: str, status: str | None) -> str:
    family = str(family_id or "").strip().upper()
    status_text = str(status or "").strip().upper()
    colours = status_colour_contract()
    for colour, config in colours.items():
        families = {str(value).upper() for value in dict(config).get("families") or ()}
        if family in families:
            return str(colour).upper()
    if any(term in status_text for term in ("FAIL", "REPAIR", "UNDERDESIGN", "SERVICEABILITY")):
        return "RED"
    if any(term in status_text for term in ("OVERDESIGN", "OPTIM", "CLEANUP")):
        return "BLUE"
    return "GREEN"


def _tone_and_icon(colour: str) -> tuple[str, str]:
    if colour == "RED":
        return "repair_required", "alert"
    if colour == "BLUE":
        return "optimisation_available", "tune"
    return "compliant", "check"


def _evidence_sections(result: FamilyResult) -> tuple[DisplaySection, ...]:
    evidence = dict(result.evidence or {})
    sections: list[DisplaySection] = []
    exact_stop = evidence.get("exact_stop_proof") or evidence.get("exact_stop") or (result.lock_proof or {}).get("exact_stop_proof")
    exhausted = (
        evidence.get("exhausted_proof")
        or evidence.get("exhausted_reason")
        or (result.lock_proof or {}).get("exhausted_proof")
    )
    target_band = evidence.get("target_band") or evidence.get("target_band_status")
    if target_band:
        sections.append(DisplaySection("Target Band", (_normalise_item(target_band),)))
    if exact_stop:
        sections.append(DisplaySection("Exact Stop", (_normalise_item(exact_stop),)))
    if exhausted:
        sections.append(DisplaySection("Exhausted Reason", (_normalise_item(exhausted),)))
    return tuple(sections)


def build_display_model_from_family_result(result: FamilyResult) -> DisplayModel:
    """Convert one selected family result into presentation fields only."""

    engineering_payload = _family_result_engineering_payload(result)
    source_hash = _stable_hash(engineering_payload)
    colour = _family_colour(result.family_id, result.status)
    tone, icon = _tone_and_icon(colour)
    evidence = dict(result.evidence or {})
    sections: list[DisplaySection] = [
        DisplaySection(
            "Outcome",
            (
                {
                    "family_id": result.family_id,
                    "status": result.status,
                    "is_applicable": result.is_applicable,
                    "governing_score": result.governing_score,
                },
            ),
        ),
        DisplaySection("Recommendation", (_normalise_item(result.selected_candidate or result.updates),)),
        DisplaySection("Why Selected", (_normalise_item(evidence.get("why_selected") or evidence.get("ranking_evidence")),)),
        DisplaySection("Evidence", (_normalise_item(evidence),)),
        DisplaySection("Blockers", tuple(_normalise_item(row) for row in list(result.blockers or []))),
        DisplaySection("Status", ({"colour": colour, "tone": tone, "icon": icon, "status": result.status},)),
    ]
    section_names = {section.title for section in sections}
    for required in required_sections():
        if required not in section_names:
            sections.append(DisplaySection(required, ()))
    sections.extend(_evidence_sections(result))
    presentation_payload = {
        "family_id": result.family_id,
        "status": result.status,
        "colour": colour,
        "tone": tone,
        "icon": icon,
        "sections": tuple(section.to_dict() for section in sections),
        "contract_version": contract_hash(),
        "source_family_result_hash": source_hash,
    }
    return DisplayModel(
        family_id=result.family_id,
        status=str(result.status or ""),
        tone=tone,
        colour=colour,
        icon=icon,
        sections=tuple(sections),
        contract_version=contract_hash(),
        source_family_result_hash=source_hash,
        presentation_hash=_stable_hash(presentation_payload),
    )


__all__ = [
    "DisplayModel",
    "DisplaySection",
    "build_display_model_from_family_result",
]
