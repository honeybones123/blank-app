"""Authoritative overall standards and design-basis registry for the beam app."""

from __future__ import annotations

from dataclasses import dataclass


REFERENCE_SET_VERSION = "beam-reference-set.v3"


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


@dataclass(frozen=True)
class CalculationReferenceGroup:
    """Clause, table and figure citations shown by one calculation page."""

    key: str
    module: str
    standard_identifier: str
    edition: str
    scope: str
    references: tuple[str, ...]
    calculation_text_sources: tuple[str, ...]
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
        amendment_status="Clause 11.7.2 is implemented from the supplied edition incorporating Amendment No. 1 (November 2018); confirm later project amendments.",
        application_use="Restrained-wall horizontal crack-control reinforcement where explicitly selected.",
        modules=("Crack Control", "Project assumptions", "Engineering review"),
        qualifications="The Clause 11.7.2 result is one minimum only; Clause 11.7.1, strength and all other applicable bridge requirements remain separate checks.",
    ),
    ReferenceEntry(
        key="restrained_deformation",
        row_title="Restrained-deformation crack control, where selected",
        standard_title="Control of cracking caused by restrained deformation in concrete",
        identifier="CIRIA C766",
        edition="2018, revised with errata 2019 and 2020",
        amendment_status="The supplied errata is applied to the published equation path.",
        application_use="Restrained strain, crack initiation, minimum reinforcement, EC2 crack width and EC2 shrinkage equations.",
        modules=("Shrinkage", "Crack Control"),
        qualifications="Temperature changes and restraint factors are designer inputs. Exact parity with corrected CIRIA spreadsheets is not claimed.",
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
)


FULL_DOCUMENT_REFERENCE_KEYS = (
    "concrete_design",
    "bridge_concrete",
    "restrained_deformation",
    "structural_actions",
)


CALCULATION_REFERENCE_GROUPS = (
    CalculationReferenceGroup(
        key="bending",
        module="Bending",
        standard_identifier="AS 3600",
        edition="2018",
        scope="ULS flexural capacity, strain compatibility, ductility and cracked-section service-stress explanations.",
        references=(
            "Cl. 2.2",
            "Cl. 2.3",
            "Cl. 3.1.2",
            "Cl. 3.1.7",
            "Cl. 3.2.2",
            "Cl. 8.1",
            "Cl. 8.1.1",
            "Cl. 8.1.3",
            "Cl. 8.1.5",
            "Cl. 8.5",
            "Cl. 13.1",
        ),
        calculation_text_sources=("bending_tabs.py", "bending_page_runtime.py", "reporting/report_content.py"),
        qualifications="The register mirrors the citations displayed by the bending calculation texts; the detailed explanation beside each calculation remains controlling.",
    ),
    CalculationReferenceGroup(
        key="shear",
        module="Shear and torsion",
        standard_identifier="AS 3600",
        edition="2018",
        scope="Equivalent shear, effective shear section, MCFT/SMCFT capacity, web crushing and shear-reinforcement detailing.",
        references=(
            "Cl. 2.2",
            "Cl. 2.3",
            "Cl. 3.1",
            "Cl. 8.2",
            "Cl. 8.2.1",
            "Cl. 8.2.2",
            "Cl. 8.2.3",
            "Cl. 8.2.3.1",
            "Cl. 8.2.4",
            "Cl. 8.2.4.1",
            "Cl. 8.2.4.2",
            "Cl. 8.2.4.2.2(1)",
            "Cl. 8.2.4.2.3",
            "Cl. 8.2.4.3",
            "Cl. 8.2.4.4",
            "Cl. 8.2.5",
            "Cl. 8.2.5.1",
            "Cl. 8.2.5.2(a)",
            "Cl. 8.2.6",
            "Cl. 8.2.7",
            "Cl. 8.3.4",
            "Fig. C8.2.5.1",
        ),
        calculation_text_sources=("shear_steps.py", "shear_page_runtime.py", "shear_core.py", "reporting/report_content.py"),
        qualifications="The selected shear method determines which cited branch is applied. Confirm applicability and detailing requirements for the project.",
    ),
    CalculationReferenceGroup(
        key="creep",
        module="Creep",
        standard_identifier="AS 3600",
        edition="2018",
        scope="Basic, time-dependent and final creep coefficients and creep strain.",
        references=(
            "Cl. 3.1.8",
            "Cl. 3.1.8.1",
            "Cl. 3.1.8.3",
            "Table 3.1.8.2",
            "Table 3.1.8.3",
            "Fig. 3.1.8.3",
        ),
        calculation_text_sources=("creep.py", "calculations/creep_shrinkage.py", "reporting/report_content.py"),
        qualifications="Environment, loading age, notional thickness and project time horizon must match the assumptions shown on the Creep page.",
    ),
    CalculationReferenceGroup(
        key="shrinkage",
        module="Shrinkage",
        standard_identifier="AS 3600",
        edition="2018",
        scope="Autogenous shrinkage, drying shrinkage, notional thickness and time development.",
        references=(
            "Cl. 3.1.7",
            "Cl. 3.1.7.2",
            "Cl. 3.1.7.2(2),(3)",
            "Cl. 3.1.7.2(4),(5)",
            "Table 3.1.7.2",
            "Fig. 3.1.7.2",
        ),
        calculation_text_sources=("shrinkage.py", "calculations/creep_shrinkage.py", "reporting/report_content.py"),
        qualifications="Drying exposure, member geometry and notional-thickness assumptions must be reviewed for the actual member.",
    ),
    CalculationReferenceGroup(
        key="crack_control",
        module="Crack Control",
        standard_identifier="AS 3600",
        edition="2018",
        scope="Exposure-dependent limits, table-based steel-stress checks and direct flexural crack-width calculation.",
        references=(
            "Cl. 8.6",
            "Cl. 8.6.1",
            "Cl. 8.6.2",
            "Cl. 8.6.2.2",
            "Table 8.6.2.2(A)",
            "Table 8.6.2.2(B)",
            "Cl. 8.6.2.3",
            "Cl. 8.6.2.3(2)",
            "Cl. 8.6.2.3(3)",
        ),
        calculation_text_sources=("crack_page_runtime.py", "calculations/crack_control.py", "reporting/report_content.py"),
        qualifications="The applicable exposure classification, crack-width limit and reinforcement arrangement remain project inputs requiring engineering review.",
    ),
    CalculationReferenceGroup(
        key="shrinkage_ec2_c766",
        module="Shrinkage",
        standard_identifier="CIRIA C766 / BS EN 1992-1-1",
        edition="C766 2018 revised with errata 2019 and 2020; EC2 2004 equation basis",
        scope="Selected EC2 nominal drying, size/time development and autogenous shrinkage equation path.",
        references=("C766 Appendix A3, Eqs A3.1-A3.5", "C766 Appendix A4, Eqs A4.1-A4.3"),
        calculation_text_sources=("calculations/concrete_crack_shrinkage_methods.py", "shrinkage.py", "reporting/report_content.py"),
        qualifications="The result is equation-based and does not claim parity with the corrected CIRIA spreadsheets identified by the errata.",
    ),
    CalculationReferenceGroup(
        key="crack_control_as5100_wall",
        module="Crack Control",
        standard_identifier="AS 5100.5",
        edition="2017 incorporating Amendment No. 1 (November 2018)",
        scope="Selected restrained-wall horizontal crack-control reinforcement.",
        references=("Cl. 11.7.1", "Cl. 11.7.2", "Cl. 11.7.3"),
        calculation_text_sources=("calculations/concrete_crack_shrinkage_methods.py", "crack_page_runtime.py", "reporting/report_content.py"),
        qualifications="Clause 11.7.2 is not a complete wall design; strength and all applicable minimum/detailing provisions remain separate gates.",
    ),
    CalculationReferenceGroup(
        key="crack_control_c766_ec2",
        module="Crack Control",
        standard_identifier="CIRIA C766 / BS EN 1992-1-1 / BS EN 1992-3",
        edition="C766 2018 revised with errata 2019 and 2020",
        scope="Selected restrained strain, crack initiation, crack-inducing strain, minimum reinforcement, spacing and width equation path.",
        references=("C766 Eqs 3.1, 3.4, 3.6, 3.10, 3.12, 3.16, 3.20-3.23"),
        calculation_text_sources=("calculations/concrete_crack_shrinkage_methods.py", "crack_page_runtime.py", "reporting/report_content.py"),
        qualifications="Temperature and restraint inputs require project engineering. Exact corrected-spreadsheet parity is not claimed.",
    ),
    CalculationReferenceGroup(
        key="deflection",
        module="Deflection",
        standard_identifier="AS 3600",
        edition="2018",
        scope="Effective stiffness, short- and long-term deflection and deemed-to-conform span-to-depth checks.",
        references=(
            "Cl. 2.3",
            "Cl. 2.3.2",
            "Cl. 8.5",
            "Cl. 8.5.3",
            "Cl. 8.5.3.1",
            "Cl. 8.5.3.1(2),(3)",
            "Cl. 8.5.3.2",
            "Cl. 8.5.4",
        ),
        calculation_text_sources=("deflection_page_runtime.py", "reporting/report_content.py"),
        qualifications="Project-specific deflection limits, finishes, partitions, load duration and support conditions can govern over the default criteria.",
    ),
)


def reference_entries() -> tuple[ReferenceEntry, ...]:
    return REFERENCE_ENTRIES


def referenced_documents() -> tuple[ReferenceEntry, ...]:
    """Return the external source documents, excluding internal basis records."""
    entries_by_key = {entry.key: entry for entry in REFERENCE_ENTRIES}
    return tuple(entries_by_key[key] for key in FULL_DOCUMENT_REFERENCE_KEYS)


def calculation_reference_groups() -> tuple[CalculationReferenceGroup, ...]:
    return CALCULATION_REFERENCE_GROUPS


__all__ = [
    "CALCULATION_REFERENCE_GROUPS",
    "FULL_DOCUMENT_REFERENCE_KEYS",
    "REFERENCE_ENTRIES",
    "REFERENCE_SET_VERSION",
    "CalculationReferenceGroup",
    "ReferenceEntry",
    "calculation_reference_groups",
    "reference_entries",
    "referenced_documents",
]
