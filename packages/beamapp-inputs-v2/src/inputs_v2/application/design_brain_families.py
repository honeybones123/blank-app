"""V2-owned Design Guide family classification boundary.

The identifiers and priority are copied from the V1 family contract, but the
classifier consumes only typed V2 results and never imports the V1 runtime.
"""

from __future__ import annotations

from enum import StrEnum
from dataclasses import dataclass
from math import isfinite
from typing import Callable

from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.domain.beam_inputs import BeamInputs


class DesignFamily(StrEnum):
    INPUT_REQUIRED = "INPUT_REQUIRED"
    ENGINEERING_REVIEW_REQUIRED = "ENGINEERING_REVIEW_REQUIRED"
    EXACT_STOP_PROVEN = "EXACT_STOP_PROVEN"
    LOCKED_NO_REPAIR = "LOCKED_NO_REPAIR"
    GEOMETRY_DETAILING_GOVERNS = "GEOMETRY_DETAILING_GOVERNS"
    BENDING_AND_SHEAR_FAIL_GOVERN = "BENDING_AND_SHEAR_FAIL_GOVERN"
    BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS = "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
    SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS = "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS"
    BENDING_FAIL_GOVERNS = "BENDING_FAIL_GOVERNS"
    SHEAR_FAIL_GOVERNS = "SHEAR_FAIL_GOVERNS"
    SERVICEABILITY_GOVERNS = "SERVICEABILITY_GOVERNS"
    COMBINED_OVERDESIGN = "COMBINED_OVERDESIGN"
    BENDING_OVERDESIGN_GOVERNS = "BENDING_OVERDESIGN_GOVERNS"
    SHEAR_OVERDESIGN_GOVERNS = "SHEAR_OVERDESIGN_GOVERNS"
    TARGET_BAND_REACHED = "TARGET_BAND_REACHED"


V1_FAMILY_PRIORITY: tuple[DesignFamily, ...] = tuple(DesignFamily)


@dataclass(frozen=True, slots=True)
class DesignSignals:
    design_actions_present: bool
    geometry_invalid: bool
    bending_utilisation: float
    shear_utilisation: float
    bending_failed: bool
    shear_failed: bool
    bending_domain: bool
    shear_domain: bool
    zero_bending_with_reinforcement: bool
    zero_shear_with_reinforcement: bool
    serviceability_failed: bool

    @property
    def active_utilisations(self) -> tuple[float, ...]:
        return tuple(
            value
            for active, value in (
                (self.bending_domain, self.bending_utilisation),
                (self.shear_domain, self.shear_utilisation),
            )
            if active
        )


EntryCondition = Callable[[DesignSignals], bool]


@dataclass(frozen=True, slots=True)
class FamilyClassification:
    """Immutable proof of the classifier's one authoritative selection."""

    selected_family: DesignFamily
    selected_entry_condition_id: str
    matched_families: tuple[DesignFamily, ...]
    signals: DesignSignals
    reason_code: str


def design_signals(result: EngineeringResult, inputs: BeamInputs | None) -> DesignSignals:
    bending = result.families.get("bending", {})
    ductility = result.families.get("ductility", {})
    shear = result.families.get("shear", {})
    bend_util = float(bending.get("util", 0.0) or 0.0)
    phi_vu = float(shear.get("phi_Vu", 0.0) or 0.0)
    shear_action = abs(float(shear.get("V_eq", 0.0) or 0.0))
    shear_util = shear_action / phi_vu if phi_vu > 0 else 0.0
    bending_action = abs(float(
        inputs.actions.bending_moment_knm
        if inputs is not None
        else bending.get("M_star_kNm", 0.0)
    ))
    design_actions_present = bool(
        inputs is None
        or any(
            abs(float(value)) > 1e-9
            for value in (
                inputs.actions.bending_moment_knm,
                inputs.actions.torsion_knm,
                inputs.actions.shear_force_kn,
                inputs.actions.axial_force_kn,
            )
        )
    )
    bending_domain = bending_action > 1e-9
    links_provided = float(shear.get("Asv", 0.0) or 0.0) > 0.0
    shear_domain = (
        shear_action > 1e-9
        or links_provided
        or bool(inputs is not None and (inputs.shear.diameter_mm > 0 or inputs.shear.legs > 0))
    )
    bending_failed = bool(bending_domain and (
        bend_util > 1.0
        or str(bending.get("status", "PASS")).upper() == "FAIL"
        or str(bending.get("minimum_tensile_status", "PASS")).upper() == "FAIL"
        or str(ductility.get("status", "PASS")).upper() == "FAIL"
    ))
    shear_failed = bool(shear_action > 1e-9 and (
        shear_util > 1.0
        or shear.get("shear_ok") is False
        or shear.get("web_ok") is False
        or (bool(shear.get("transverse_reinforcement_required")) and not links_provided)
        or (links_provided and shear.get("min_shear_ok") is False)
        or (links_provided and shear.get("spacing_ok") is False)
    ))
    fit = result.families.get("reinforcement_fit", {})
    geometry_invalid = bool(inputs is not None and (
        inputs.depth_mm / inputs.width_mm > 2.0
        or (inputs.shear.diameter_mm == 0 and inputs.shear.legs != 0)
        or fit.get("accepted") is False
    ))
    bottom_reinforcement_provided = (
        bool(inputs.bottom.bars > 0 or inputs.bottom.diameter_mm > 0)
        if inputs is not None
        else float(bending.get("Ast_tension_mm2", 0.0) or 0.0) > 0.0
    )
    zero_bending = bool(not bending_domain and bottom_reinforcement_provided)
    zero_shear = bool(shear_action < 1e-9 and (
        links_provided
        or bool(inputs is not None and (inputs.shear.diameter_mm > 0 or inputs.shear.legs > 0))
    ))
    serviceability = result.families.get("serviceability", {})
    crack = result.families.get("crack_control", {})
    serviceability_failed = (
        str(serviceability.get("status", "")).upper() == "FAIL"
        or str(crack.get("status", "")).upper() == "FAIL"
    )
    return DesignSignals(
        design_actions_present=design_actions_present,
        geometry_invalid=geometry_invalid,
        bending_utilisation=bend_util,
        shear_utilisation=shear_util,
        bending_failed=bending_failed,
        shear_failed=shear_failed,
        bending_domain=bending_domain,
        shear_domain=shear_domain,
        zero_bending_with_reinforcement=zero_bending,
        zero_shear_with_reinforcement=zero_shear,
        serviceability_failed=serviceability_failed,
    )


ENTRY_CONDITIONS: dict[DesignFamily, EntryCondition] = {
    DesignFamily.INPUT_REQUIRED: lambda s: not s.design_actions_present,
    # Review-required is an explicit fail-closed terminal outcome.  It is not
    # part of CLASSIFICATION_PRIORITY and can never compete with an
    # engineering family.
    DesignFamily.ENGINEERING_REVIEW_REQUIRED: lambda _s: True,
    DesignFamily.GEOMETRY_DETAILING_GOVERNS: lambda s: s.geometry_invalid,
    DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN: lambda s: s.bending_failed and s.shear_failed,
    DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS: lambda s: (
        s.bending_failed
        and not s.shear_failed
        and s.shear_utilisation < 0.85
        and (s.shear_domain or s.zero_shear_with_reinforcement)
    ),
    DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS: lambda s: (
        s.shear_failed
        and not s.bending_failed
        and s.bending_utilisation < 0.85
        and (s.bending_domain or s.zero_bending_with_reinforcement)
    ),
    DesignFamily.BENDING_FAIL_GOVERNS: lambda s: s.bending_failed,
    DesignFamily.SHEAR_FAIL_GOVERNS: lambda s: s.shear_failed,
    DesignFamily.SERVICEABILITY_GOVERNS: lambda s: s.serviceability_failed,
    DesignFamily.COMBINED_OVERDESIGN: lambda s: (
        (s.zero_bending_with_reinforcement and s.zero_shear_with_reinforcement)
        or (
            not s.bending_failed and not s.shear_failed and not s.serviceability_failed
            and s.bending_utilisation < 0.85 and s.shear_utilisation < 0.85
            and s.bending_domain and s.shear_domain
        )
    ),
    DesignFamily.BENDING_OVERDESIGN_GOVERNS: lambda s: (
        not s.bending_failed and not s.shear_failed and (
            s.zero_bending_with_reinforcement
            or (not s.serviceability_failed and s.bending_utilisation < 0.85 and not s.shear_domain)
            or (not s.serviceability_failed and s.bending_utilisation < 0.85 and 0.85 <= s.shear_utilisation <= 1.0)
        )
    ),
    DesignFamily.SHEAR_OVERDESIGN_GOVERNS: lambda s: (
        not s.bending_failed and not s.shear_failed and (
            s.zero_shear_with_reinforcement
            or (not s.serviceability_failed and s.shear_domain and s.shear_utilisation < 0.85 and not s.bending_domain)
            or (not s.serviceability_failed and s.shear_domain and s.shear_utilisation < 0.85 and 0.85 <= s.bending_utilisation <= 1.0)
        )
    ),
    DesignFamily.TARGET_BAND_REACHED: lambda s: (
        not s.bending_failed and not s.shear_failed
        and bool(s.active_utilisations)
        and all(0.85 <= value <= 1.0 for value in s.active_utilisations)
    ),
    DesignFamily.EXACT_STOP_PROVEN: lambda s: False,
    DesignFamily.LOCKED_NO_REPAIR: lambda s: False,
}


CLASSIFICATION_PRIORITY: tuple[DesignFamily, ...] = (
    DesignFamily.INPUT_REQUIRED,
    DesignFamily.GEOMETRY_DETAILING_GOVERNS,
    DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN,
    DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS,
    DesignFamily.BENDING_FAIL_GOVERNS,
    DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS,
    DesignFamily.SHEAR_FAIL_GOVERNS,
    DesignFamily.SERVICEABILITY_GOVERNS,
    DesignFamily.COMBINED_OVERDESIGN,
    DesignFamily.BENDING_OVERDESIGN_GOVERNS,
    DesignFamily.SHEAR_OVERDESIGN_GOVERNS,
    DesignFamily.TARGET_BAND_REACHED,
)


def classify_design_family_selection(
    result: EngineeringResult,
    inputs: BeamInputs | None = None,
) -> FamilyClassification:
    """Classify once and return immutable selection evidence.

    ``EXACT_STOP_PROVEN`` and ``LOCKED_NO_REPAIR`` are family-owned outcomes,
    not classifier fallbacks.  Unsupported or invalid states fail closed as
    ``ENGINEERING_REVIEW_REQUIRED``.
    """
    signals = design_signals(result, inputs)
    matched = tuple(
        family
        for family in CLASSIFICATION_PRIORITY
        if ENTRY_CONDITIONS[family](signals)
    )

    if matched and matched[0] is DesignFamily.INPUT_REQUIRED:
        return FamilyClassification(
            selected_family=DesignFamily.INPUT_REQUIRED,
            selected_entry_condition_id="no_design_actions_entered",
            matched_families=matched,
            signals=signals,
            reason_code="no_design_actions_entered",
        )

    if any(not isfinite(value) for value in (
        signals.bending_utilisation,
        signals.shear_utilisation,
    )):
        return FamilyClassification(
            selected_family=DesignFamily.ENGINEERING_REVIEW_REQUIRED,
            selected_entry_condition_id="invalid_engineering_result",
            matched_families=matched,
            signals=signals,
            reason_code="non_finite_utilisation",
        )

    unsupported_action_domain = bool(
        inputs is not None
        and abs(float(inputs.actions.bending_moment_knm)) <= 1e-9
        and abs(float(inputs.actions.shear_force_kn)) <= 1e-9
        and (
            abs(float(inputs.actions.torsion_knm)) > 1e-9
            or abs(float(inputs.actions.axial_force_kn)) > 1e-9
        )
    )
    if unsupported_action_domain:
        return FamilyClassification(
            selected_family=DesignFamily.ENGINEERING_REVIEW_REQUIRED,
            selected_entry_condition_id="unsupported_action_domain",
            matched_families=matched,
            signals=signals,
            reason_code="unsupported_action_domain",
        )

    if matched:
        selected = matched[0]
        return FamilyClassification(
            selected_family=selected,
            selected_entry_condition_id=selected.value.lower(),
            matched_families=matched,
            signals=signals,
            reason_code="priority_entry_condition_matched",
        )

    return FamilyClassification(
        selected_family=DesignFamily.ENGINEERING_REVIEW_REQUIRED,
        selected_entry_condition_id="no_family_entry_condition_matched",
        matched_families=(),
        signals=signals,
        reason_code="no_family_entry_condition_matched",
    )


def classify_design_family(
    result: EngineeringResult,
    inputs: BeamInputs | None = None,
) -> DesignFamily:
    """Compatibility projection of the authoritative classification evidence."""

    return classify_design_family_selection(result, inputs).selected_family
