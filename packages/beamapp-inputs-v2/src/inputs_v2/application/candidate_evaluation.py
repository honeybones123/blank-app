"""Single candidate validation, calculation and mandatory-compliance pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from inputs_v2.application.design_brain_apply import ApplyOutcome, Candidate, apply_candidate
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult


CalculateCandidate = Callable[[BeamInputs], EngineeringResult | None]


def complete_compliance(result: EngineeringResult) -> bool:
    """Return true only when every calculated mandatory check passes."""
    accepted_statuses = {
        "bending": {"PASS", "INFO"},
        "ductility": {"PASS"},
        "geometry": {"PASS"},
        "serviceability": {"PASS", "NOT RUN", "PROVISIONAL PASS"},
        "crack_control": {"PASS", "NOT RUN", "PROVISIONAL PASS"},
    }
    for family_name, allowed in accepted_statuses.items():
        family = result.families.get(family_name)
        if family is None or str(family.get("status", "")).upper() not in allowed:
            return False
    bending = result.families.get("bending", {})
    if str(bending.get("minimum_tensile_status", "")).upper() != "PASS":
        return False
    shear = result.families.get("shear", {})
    if shear.get("shear_ok") is not True or shear.get("web_ok") is not True:
        return False
    links_provided = float(shear.get("Asv", 0.0) or 0.0) > 0.0
    links_required = bool(shear.get("transverse_reinforcement_required"))
    if links_required and not links_provided:
        return False
    if links_provided and shear.get("min_shear_ok") is not True:
        return False
    if links_provided and shear.get("spacing_ok") is not True:
        return False
    if links_provided and shear.get("transverse_spacing_ok") is not True:
        return False
    return bool(result.families.get("reinforcement_fit", {}).get("accepted", False))


def bending_mandatory_failure(result: EngineeringResult) -> bool:
    """Return true when an authoritative mandatory bending check fails.

    Bending-family selection is not based on flexural utilisation alone. A
    design also belongs to a bending-failure family when minimum tensile
    reinforcement or the Clause 8.1.5 ductility assessment fails. Repair
    pipelines must use the same definition so a fully compliant repair is not
    rejected merely because its flexural utilisation was already below 1.0.
    """

    bending = result.families.get("bending", {})
    ductility = result.families.get("ductility", {})
    return any(
        (
            float(bending.get("util", 0.0) or 0.0) > 1.0,
            str(bending.get("status", "PASS")).upper() == "FAIL",
            str(bending.get("minimum_tensile_status", "PASS")).upper() == "FAIL",
            str(ductility.get("status", "PASS")).upper() == "FAIL",
        )
    )


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    candidate: Candidate
    outcome: ApplyOutcome
    result: EngineeringResult | None
    mandatory_compliance: bool
    rejection_codes: tuple[str, ...] = ()
    calculated_checks: tuple[tuple[str, str], ...] = ()
    elapsed_ms: float = 0.0

    @property
    def usable(self) -> bool:
        return self.outcome.applied and self.result is not None and self.mandatory_compliance


def evaluate_candidate(
    current: BeamInputs,
    candidate: Candidate,
    calculate: CalculateCandidate,
) -> CandidateEvaluation:
    """Run the canonical pipeline; family rules may only rank usable results."""
    started = perf_counter()
    outcome = apply_candidate(current, candidate)
    if not outcome.applied:
        return CandidateEvaluation(
            candidate,
            outcome,
            None,
            False,
            (outcome.reason,),
            (),
            (perf_counter() - started) * 1000.0,
        )
    result = calculate(outcome.inputs)
    if result is None:
        return CandidateEvaluation(
            candidate,
            outcome,
            None,
            False,
            ("calculation_unavailable",),
            (),
            (perf_counter() - started) * 1000.0,
        )
    compliant = complete_compliance(result)
    return CandidateEvaluation(
        candidate,
        outcome,
        result,
        compliant,
        () if compliant else compliance_rejection_codes(result),
        calculated_check_statuses(result),
        (perf_counter() - started) * 1000.0,
    )


def calculated_check_statuses(result: EngineeringResult) -> tuple[tuple[str, str], ...]:
    """Return compact authoritative facts for candidate-search diagnostics."""

    families = result.families
    bending = families.get("bending", {})
    shear = families.get("shear", {})
    links_provided = float(shear.get("Asv", 0.0) or 0.0) > 0.0
    rows = (
        ("bending", str(bending.get("status", "MISSING")).upper()),
        (
            "minimum_tensile",
            str(bending.get("minimum_tensile_status", "MISSING")).upper(),
        ),
        (
            "ductility",
            str(families.get("ductility", {}).get("status", "MISSING")).upper(),
        ),
        ("shear_strength", "PASS" if shear.get("shear_ok") is True else "FAIL"),
        ("shear_web_crushing", "PASS" if shear.get("web_ok") is True else "FAIL"),
        (
            "transverse_reinforcement",
            "PASS"
            if not bool(shear.get("transverse_reinforcement_required")) or links_provided
            else "FAIL",
        ),
        (
            "minimum_shear_reinforcement",
            "NOT REQUIRED"
            if not links_provided
            else "PASS" if shear.get("min_shear_ok") is True else "FAIL",
        ),
        (
            "shear_spacing",
            "NOT REQUIRED"
            if not links_provided
            else "PASS" if shear.get("spacing_ok") is True else "FAIL",
        ),
        (
            "transverse_shear_leg_spacing",
            "NOT REQUIRED"
            if not links_provided
            else "PASS" if shear.get("transverse_spacing_ok") is True else "FAIL",
        ),
        (
            "geometry",
            str(families.get("geometry", {}).get("status", "MISSING")).upper(),
        ),
        (
            "reinforcement_fit",
            "PASS"
            if bool(families.get("reinforcement_fit", {}).get("accepted", False))
            else "FAIL",
        ),
        (
            "crack_control",
            str(families.get("crack_control", {}).get("status", "MISSING")).upper(),
        ),
        (
            "serviceability",
            str(families.get("serviceability", {}).get("status", "MISSING")).upper(),
        ),
    )
    return tuple(rows)


def compliance_rejection_codes(result: EngineeringResult) -> tuple[str, ...]:
    """Return stable evidence codes for every failed mandatory candidate check."""

    rejected: list[str] = []
    families = result.families
    for family_name, allowed in (
        ("bending", {"PASS", "INFO"}),
        ("ductility", {"PASS"}),
        ("geometry", {"PASS"}),
        ("serviceability", {"PASS", "NOT RUN", "PROVISIONAL PASS"}),
        ("crack_control", {"PASS", "NOT RUN", "PROVISIONAL PASS"}),
    ):
        status = str(families.get(family_name, {}).get("status", "MISSING")).upper()
        if status not in allowed:
            rejected.append(f"{family_name}_{status.lower().replace(' ', '_')}")
    bending = families.get("bending", {})
    if str(bending.get("minimum_tensile_status", "MISSING")).upper() != "PASS":
        rejected.append("minimum_tensile_reinforcement_failed")
    shear = families.get("shear", {})
    if shear.get("shear_ok") is not True:
        rejected.append("shear_strength_failed")
    if shear.get("web_ok") is not True:
        rejected.append("shear_web_crushing_failed")
    links_provided = float(shear.get("Asv", 0.0) or 0.0) > 0.0
    if bool(shear.get("transverse_reinforcement_required")) and not links_provided:
        rejected.append("transverse_reinforcement_required")
    if links_provided and shear.get("min_shear_ok") is not True:
        rejected.append("minimum_shear_reinforcement_failed")
    if links_provided and shear.get("spacing_ok") is not True:
        rejected.append("shear_spacing_failed")
    fit = families.get("reinforcement_fit", {})
    if links_provided and shear.get("transverse_spacing_ok") is not True:
        rejected.append("transverse_shear_leg_spacing_failed")
    if links_provided and shear.get("transverse_clear_spacing_ok") is False:
        rejected.append("transverse_shear_leg_clear_spacing_failed")
    if links_provided and shear.get("cage_topology_verified") is False:
        rejected.extend(tuple(shear.get("cage_rejection_codes", ())))
        if not shear.get("cage_rejection_codes"):
            rejected.append("shear_cage_topology_unavailable")
    if not bool(fit.get("accepted", False)):
        rejected.append("reinforcement_fit_failed")
        if str(fit.get("cover_status", "PASS")).upper() == "FAIL":
            rejected.append("cover_failed")
        if fit.get("horizontal_fit_ok") is False:
            rejected.append("clear_spacing_failed")
        if fit.get("vertical_fit_ok") is False:
            rejected.append("row_spacing_failed")
        if fit.get("aggregate_clearance_ok") is False:
            rejected.append("constructability_limit_failed")
    return tuple(dict.fromkeys(rejected))
