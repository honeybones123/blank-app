"""Authoritative overall standards and design-basis registry for the beam app."""

from __future__ import annotations

from dataclasses import dataclass


REFERENCE_SET_VERSION = "beam-reference-set.v1"


@dataclass(frozen=True)
class ReferenceEntry:
    key: str
    row_title: str
    standard_title: str
    identifier: str
    edition: str
    amendment_status: str
    application_use: str
    modules: tuple[str, ...]
    qualifications: str


REFERENCE_ENTRIES = (
    ReferenceEntry(
        key="concrete_design",
        row_title="Concrete design",
        standard_title="Concrete structures",
        identifier="AS 3600",
        edition="2018",
        amendment_status="Edition implemented by the current calculation engine; verify project amendment requirements.",
        application_use="Reinforced-concrete member strength, detailing, durability and serviceability checks.",
        modules=("Bending", "Shear", "Creep", "Shrinkage", "Crack Control", "Deflection"),
        qualifications="Project-specific departures, authority requirements and later amendments remain the engineer's responsibility.",
    ),
    ReferenceEntry(
        key="bridge_concrete",
        row_title="Bridge concrete design, where applicable",
        standard_title="Bridge design — Concrete",
        identifier="AS 5100.5",
        edition="2017",
        amendment_status="Applicable only when the project adopts bridge-design requirements; confirm amendments for the project.",
        application_use="Additional bridge concrete requirements where explicitly nominated by the project.",
        modules=("Project assumptions", "Engineering review"),
        qualifications="The base beam checks do not automatically establish that every bridge-specific requirement has been satisfied.",
    ),
    ReferenceEntry(
        key="structural_actions",
        row_title="Structural actions",
        standard_title="Structural design actions series",
        identifier="AS/NZS 1170",
        edition="Project-nominated editions",
        amendment_status="Load combinations and editions must be confirmed for the project and jurisdiction.",
        application_use="Basis for user-entered actions and Load Analysis load combinations.",
        modules=("Load Analysis", "Design actions"),
        qualifications="The application does not determine all project actions, importance levels or regulatory combinations automatically.",
    ),
    ReferenceEntry(
        key="serviceability_methods",
        row_title="Serviceability methods",
        standard_title="Concrete serviceability methods",
        identifier="AS 3600",
        edition="2018",
        amendment_status="Current implemented serviceability basis; confirm project criteria and amendments.",
        application_use="Crack-width, creep, shrinkage and deflection assessment.",
        modules=("Creep", "Shrinkage", "Crack Control", "Deflection"),
        qualifications="Project-specific deflection, crack-width, finish, vibration and long-term performance criteria can govern.",
    ),
    ReferenceEntry(
        key="assumptions_limitations",
        row_title="Calculation assumptions and limitations",
        standard_title="StructuralBase beam calculation basis",
        identifier="SB-BEAM-BASIS",
        edition="1",
        amendment_status="Controlled with the calculation-engine release.",
        application_use="Defines modelling scope, sign conventions, supported section types and calculation limitations.",
        modules=("All calculation modules",),
        qualifications="The detailed assumptions shown in each calculation remain authoritative for that check.",
    ),
    ReferenceEntry(
        key="clause_register",
        row_title="Clause-reference register",
        standard_title="StructuralBase calculation clause-reference register",
        identifier="SB-CLAUSE-REGISTER",
        edition="1",
        amendment_status="Maintained with the reference-set version.",
        application_use="Maps calculation-specific explanations to the nominated reference basis.",
        modules=("Bending", "Shear", "Creep", "Shrinkage", "Crack Control", "Deflection"),
        qualifications="Calculation-page references provide the check-specific clause context; the Start page is only an overview.",
    ),
)


def reference_entries() -> tuple[ReferenceEntry, ...]:
    return REFERENCE_ENTRIES


__all__ = ["REFERENCE_ENTRIES", "REFERENCE_SET_VERSION", "ReferenceEntry", "reference_entries"]
