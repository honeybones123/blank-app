"""Family-owned visible wording and blocker contracts for Design Brain."""

from __future__ import annotations

from dataclasses import dataclass

from inputs_v2.application.design_brain_families import DesignFamily


@dataclass(frozen=True, slots=True)
class BlockerText:
    reason_code: str
    sentence: str


@dataclass(frozen=True, slots=True)
class FamilyTextContract:
    family: DesignFamily
    action_title: str
    blocked_title: str
    pass_title: str
    engineering_purpose: str
    required_checks: tuple[str, ...]
    blockers: tuple[BlockerText, ...] = ()

    def title_for(self, status: str) -> str:
        if status == "ACTION":
            return self.action_title
        if status == "PASS":
            return self.pass_title
        return self.blocked_title

    def blocker_for(self, reason_code: str | None) -> str | None:
        if reason_code is None:
            return None
        canonical = reason_code.split(":", 1)[0]
        return next((item.sentence for item in self.blockers if item.reason_code == canonical), None)


_BENDING_BLOCKERS = (
    BlockerText("no_bending_demand", "No bending action is available to verify a bending revision."),
    BlockerText("no_valid_bending_candidate", "No reinforcement arrangement satisfied bending strength, ductility, minimum tensile reinforcement and fit."),
    BlockerText("no_improving_target_band_candidate", "No verified bending candidate improved the design into the target band."),
    BlockerText("no_improving_bending_cleanup", "No further bending reduction reached the target band without breaching a verified strength, ductility, minimum-reinforcement or fit requirement."),
    BlockerText("no_safe_bending_cleanup", "No safe reduction satisfied bending strength, ductility, minimum tensile reinforcement and fit."),
    BlockerText("minimum_reinforcement_geometry_exhausted", "Minimum tensile reinforcement governs after all permitted geometry reductions were assessed."),
    BlockerText("ductility_geometry_exhausted", "The neutral-axis ductility limit governs after all permitted geometry revisions were assessed."),
)

_SHEAR_BLOCKERS = (
    BlockerText("shear_not_failed", "The current shear check does not require a strength repair."),
    BlockerText("no_valid_shear_repair", "No ligature and geometry arrangement satisfied all governing shear checks."),
    BlockerText("no_improving_shear_target_band_candidate", "No verified shear candidate improved the design into the target band."),
    BlockerText("no_safe_shear_cleanup", "Further ligature reduction would breach a verified shear or detailing requirement."),
    BlockerText("no_improving_shear_cleanup", "No further ligature reduction reached the target band while preserving every governing shear requirement."),
    BlockerText("minimum_shear_reinforcement_exhausted", "Minimum shear reinforcement prevents any further ligature reduction."),
)

_COMBINED_BLOCKERS = (
    BlockerText("no_valid_combined_repair", "No coordinated bending, shear and geometry revision satisfied every governing check."),
    BlockerText("no_combined_target_band_candidate", "No coordinated candidate brought the governing strength checks into the target band."),
    BlockerText("no_safe_combined_cleanup", "No further combined material reduction preserves all governing checks."),
    BlockerText("no_improving_combined_cleanup", "No coordinated revision placed every active governing check within its target band while preserving compliance."),
) + _BENDING_BLOCKERS + _SHEAR_BLOCKERS

_SERVICEABILITY_BLOCKERS = (
    BlockerText("serviceability_not_failed", "The supplied serviceability actions do not require a serviceability repair."),
    BlockerText("no_valid_serviceability_candidate", "No reinforcement or geometry revision satisfied the governing serviceability check."),
    BlockerText("no_improving_serviceability_candidate", "No verified revision brought the governing crack-control or deflection check within its allowable limit."),
    BlockerText("serviceability_repair_blocked", "No candidate passed all required crack-control, deflection, strength and reinforcement-fit checks."),
)

_GEOMETRY_BLOCKERS = (
    BlockerText("geometry_already_compliant", "The current section already satisfies the configured geometry limit."),
    BlockerText("geometry_candidate_validation_failed", "The proposed geometry revision failed canonical input or reinforcement-fit validation."),
)


FAMILY_TEXT_CONTRACTS: dict[DesignFamily, FamilyTextContract] = {
    DesignFamily.INPUT_REQUIRED: FamilyTextContract(
        DesignFamily.INPUT_REQUIRED,
        "Design actions required", "Design actions required", "Design actions required",
        "No design actions entered. Add loads and the Design Brain will check and optimise your beam.",
        ("reinforcement_fit",), (),
    ),
    DesignFamily.GEOMETRY_DETAILING_GOVERNS: FamilyTextContract(
        DesignFamily.GEOMETRY_DETAILING_GOVERNS,
        "Verified geometry and detailing revision", "Geometry and detailing review required", "Geometry and detailing verified",
        "Restore the section proportions and reinforcement arrangement required for a buildable design.",
        ("geometry", "reinforcement_fit"), _GEOMETRY_BLOCKERS,
    ),
    DesignFamily.SERVICEABILITY_GOVERNS: FamilyTextContract(
        DesignFamily.SERVICEABILITY_GOVERNS,
        "Verified serviceability revision", "Serviceability revision required", "Serviceability checks verified",
        "Improve crack control or deflection while preserving every governing strength and detailing check.",
        ("crack_control", "serviceability", "bending", "shear", "reinforcement_fit"), _SERVICEABILITY_BLOCKERS,
    ),
    DesignFamily.COMBINED_OVERDESIGN: FamilyTextContract(
        DesignFamily.COMBINED_OVERDESIGN,
        "Verified combined optimisation", "Combined optimisation review required", "Compliant combined design retained",
        "Remove unnecessary concrete and reinforcement through one coordinated bending-and-shear revision.",
        ("bending", "shear", "ductility", "reinforcement_fit"), _COMBINED_BLOCKERS,
    ),
    DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN: FamilyTextContract(
        DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN,
        "Verified combined strength revision", "Combined strength revision required", "Combined strength checks verified",
        "Repair bending and shear together without transferring failure to ductility, serviceability or detailing.",
        ("bending", "shear", "ductility", "reinforcement_fit"), _COMBINED_BLOCKERS,
    ),
    DesignFamily.SHEAR_FAIL_GOVERNS: FamilyTextContract(
        DesignFamily.SHEAR_FAIL_GOVERNS,
        "Verified shear revision", "Shear design revision required", "Shear design verified",
        "Provide the transverse and longitudinal resistance required by the governing shear mechanism.",
        ("shear", "bending", "ductility", "reinforcement_fit"), _SHEAR_BLOCKERS,
    ),
    DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS: FamilyTextContract(
        DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS,
        "Verified shear and bending revision", "Shear and bending revision required", "Shear and bending design verified",
        "Repair shear and remove unnecessary bending capacity in one coordinated, compliant revision.",
        ("shear", "bending", "ductility", "reinforcement_fit"), _SHEAR_BLOCKERS + _BENDING_BLOCKERS,
    ),
    DesignFamily.BENDING_FAIL_GOVERNS: FamilyTextContract(
        DesignFamily.BENDING_FAIL_GOVERNS,
        "Verified bending revision", "Bending design revision required", "Bending design verified",
        "Restore flexural strength while satisfying ductility, minimum tensile reinforcement and reinforcement fit.",
        ("bending", "ductility", "minimum_tensile", "reinforcement_fit"), _BENDING_BLOCKERS,
    ),
    DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS: FamilyTextContract(
        DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS,
        "Verified bending and shear revision", "Bending and shear revision required", "Bending and shear design verified",
        "Repair bending and remove unnecessary shear reinforcement without compromising either resistance mechanism.",
        ("bending", "shear", "ductility", "minimum_tensile", "reinforcement_fit"), _BENDING_BLOCKERS + _SHEAR_BLOCKERS,
    ),
    DesignFamily.BENDING_OVERDESIGN_GOVERNS: FamilyTextContract(
        DesignFamily.BENDING_OVERDESIGN_GOVERNS,
        "Verified bending optimisation", "Bending optimisation review required", "Compliant bending design retained",
        "Reduce unnecessary longitudinal reinforcement or section size while retaining verified flexural compliance.",
        ("bending", "shear", "ductility", "minimum_tensile", "reinforcement_fit"), _BENDING_BLOCKERS,
    ),
    DesignFamily.SHEAR_OVERDESIGN_GOVERNS: FamilyTextContract(
        DesignFamily.SHEAR_OVERDESIGN_GOVERNS,
        "Verified shear optimisation", "Shear optimisation review required", "Compliant shear design retained",
        "Reduce unnecessary ligatures or section width while retaining every governing shear requirement.",
        ("shear", "bending", "ductility", "reinforcement_fit"), _SHEAR_BLOCKERS,
    ),
    DesignFamily.TARGET_BAND_REACHED: FamilyTextContract(
        DesignFamily.TARGET_BAND_REACHED,
        "Target band reached", "Target-band verification required", "Target band reached",
        "Retain the verified design because every active governing check is within its target band.",
        ("bending", "shear", "serviceability", "crack_control", "reinforcement_fit"), (),
    ),
    DesignFamily.EXACT_STOP_PROVEN: FamilyTextContract(
        DesignFamily.EXACT_STOP_PROVEN,
        "Verified exact stop", "Exact-stop verification required", "Verified exact stop",
        "Retain the current design because the permitted search is exhausted at a verified governing limit.",
        ("bending", "shear", "ductility", "minimum_tensile", "serviceability", "crack_control", "reinforcement_fit"),
        _COMBINED_BLOCKERS + _SERVICEABILITY_BLOCKERS + _GEOMETRY_BLOCKERS,
    ),
    DesignFamily.LOCKED_NO_REPAIR: FamilyTextContract(
        DesignFamily.LOCKED_NO_REPAIR,
        "Verified constrained revision", "Further design review required", "Locked design verified",
        "Identify the governing failed check and the exact locked input that prevents a compliant repair.",
        ("geometry", "bending", "shear", "ductility", "minimum_tensile", "serviceability", "crack_control", "reinforcement_fit"),
        (BlockerText("geometry_or_reinforcement_locked", "A required geometry or reinforcement change is locked by the user."),),
    ),
}
