"""Authoritative StructuralBase design disclaimer configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisclaimerConfig:
    version: str
    effective_date: str
    material_update_requires_renewal: bool
    short_notice: str
    full_sections: tuple[tuple[str, str], ...]


DISCLAIMER = DisclaimerConfig(
    version="design-disclaimer.v1",
    effective_date="2026-08-09",
    material_update_requires_renewal=False,
    short_notice=(
        "StructuralBase is a design-assistance and educational tool. Results must be "
        "reviewed and independently verified by a suitably qualified engineer before "
        "being used for design, documentation or construction."
    ),
    full_sections=(
        (
            "Professional review required",
            "StructuralBase does not replace professional engineering judgement, project-specific verification, independent checking or statutory approval.",
        ),
        (
            "Inputs and assumptions",
            "The user is responsible for the accuracy, completeness and suitability of all geometry, materials, loads, supports, exposure conditions and project assumptions.",
        ),
        (
            "Standards and project requirements",
            "The nominated standards and calculation methods may not cover every structure, jurisdiction, loading condition, durability exposure, construction stage or project specification.",
        ),
        (
            "Use of results",
            "Results must be independently checked before they are used for design decisions, drawings, specifications, certification, procurement or construction.",
        ),
    ),
)


__all__ = ["DISCLAIMER", "DisclaimerConfig"]
