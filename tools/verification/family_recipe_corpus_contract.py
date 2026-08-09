"""Certify every frozen live-family recipe against explicit predicates.

Recipe names are historical regression labels.  They are never treated as
engineering truth: this verifier recalculates each state, derives the family
from authoritative result checks, and then classifies the old label as an
exact match, a documented alias, or an invalid fixture.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from application.engineering_input_validation import EngineeringInputValidationError
from application.engineering_snapshot import (
    build_engineering_input_snapshot_from_resolved_state,
)
from inputs_application.new_design_brain_adapter import _beam_inputs_from_snapshot, _v2_api
from inputs_v2.application.design_brain_families import (
    DesignFamily,
    classify_design_family,
)
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator
from tools.verification.recipes.one_click_recipe_defs import DEBUG_CASES, build_state


LIVE_PREFIX = "LIVE_FUZZ_"
LEGACY_ALIASES = {
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS": DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN,
    "COMBINED_OVERDESIGN_GOVERNS": DesignFamily.COMBINED_OVERDESIGN,
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS,
}


@dataclass(frozen=True, slots=True)
class IndependentSignals:
    actions_present: bool
    geometry_invalid: bool
    bending_util: float
    shear_util: float
    bending_failed: bool
    shear_failed: bool
    bending_domain: bool
    shear_domain: bool
    zero_bending_with_reinforcement: bool
    zero_shear_with_reinforcement: bool
    serviceability_failed: bool


def _historical_label(name: str) -> str:
    return name.removeprefix(LIVE_PREFIX).rsplit("_", 1)[0]


def _independent_signals(inputs, result) -> IndependentSignals:
    bending = result.families["bending"]
    ductility = result.families["ductility"]
    shear = result.families["shear"]
    serviceability = result.families["serviceability"]
    crack = result.families["crack_control"]
    fit = result.families["reinforcement_fit"]

    bending_action = abs(float(inputs.actions.bending_moment_knm))
    shear_action = abs(float(shear.get("V_eq", 0.0) or 0.0))
    bending_util = float(bending.get("util", 0.0) or 0.0)
    phi_vu = float(shear.get("phi_Vu", 0.0) or 0.0)
    shear_util = shear_action / phi_vu if phi_vu > 0.0 else 0.0
    links_provided = float(shear.get("Asv", 0.0) or 0.0) > 0.0
    bending_domain = bending_action > 1e-9
    shear_domain = bool(
        shear_action > 1e-9
        or links_provided
        or inputs.shear.diameter_mm > 0
        or inputs.shear.legs > 0
    )
    bending_failed = bool(
        bending_domain
        and (
            bending_util > 1.0
            or str(bending.get("status", "PASS")).upper() == "FAIL"
            or str(bending.get("minimum_tensile_status", "PASS")).upper() == "FAIL"
            or str(ductility.get("status", "PASS")).upper() == "FAIL"
        )
    )
    shear_failed = bool(
        shear_action > 1e-9
        and (
            shear_util > 1.0
            or shear.get("shear_ok") is False
            or shear.get("web_ok") is False
            or (bool(shear.get("transverse_reinforcement_required")) and not links_provided)
            or (links_provided and shear.get("min_shear_ok") is False)
            or (links_provided and shear.get("spacing_ok") is False)
        )
    )
    bottom_reinforcement = inputs.bottom.bars > 0 or inputs.bottom.diameter_mm > 0
    return IndependentSignals(
        actions_present=any(
            abs(float(value)) > 1e-9
            for value in (
                inputs.actions.bending_moment_knm,
                inputs.actions.torsion_knm,
                inputs.actions.shear_force_kn,
                inputs.actions.axial_force_kn,
            )
        ),
        geometry_invalid=bool(
            inputs.depth_mm / inputs.width_mm > 2.0
            or (inputs.shear.diameter_mm == 0 and inputs.shear.legs != 0)
            or fit.get("accepted") is False
        ),
        bending_util=bending_util,
        shear_util=shear_util,
        bending_failed=bending_failed,
        shear_failed=shear_failed,
        bending_domain=bending_domain,
        shear_domain=shear_domain,
        zero_bending_with_reinforcement=not bending_domain and bottom_reinforcement,
        zero_shear_with_reinforcement=shear_action < 1e-9
        and (links_provided or inputs.shear.diameter_mm > 0 or inputs.shear.legs > 0),
        serviceability_failed=(
            str(serviceability.get("status", "")).upper() == "FAIL"
            or str(crack.get("status", "")).upper() == "FAIL"
        ),
    )


def _independent_family(s: IndependentSignals) -> DesignFamily:
    if not s.actions_present:
        return DesignFamily.INPUT_REQUIRED
    if s.geometry_invalid:
        return DesignFamily.GEOMETRY_DETAILING_GOVERNS
    if s.bending_failed and s.shear_failed:
        return DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN
    if (
        s.bending_failed
        and not s.shear_failed
        and s.shear_util < 0.85
        and (s.shear_domain or s.zero_shear_with_reinforcement)
    ):
        return DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS
    if s.bending_failed:
        return DesignFamily.BENDING_FAIL_GOVERNS
    if (
        s.shear_failed
        and not s.bending_failed
        and s.bending_util < 0.85
        and (s.bending_domain or s.zero_bending_with_reinforcement)
    ):
        return DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS
    if s.shear_failed:
        return DesignFamily.SHEAR_FAIL_GOVERNS
    if s.serviceability_failed:
        return DesignFamily.SERVICEABILITY_GOVERNS
    if (
        s.zero_bending_with_reinforcement and s.zero_shear_with_reinforcement
    ) or (
        s.bending_util < 0.85
        and s.shear_util < 0.85
        and s.bending_domain
        and s.shear_domain
    ):
        return DesignFamily.COMBINED_OVERDESIGN
    if s.zero_bending_with_reinforcement or (
        s.bending_util < 0.85
        and (not s.shear_domain or 0.85 <= s.shear_util <= 1.0)
    ):
        return DesignFamily.BENDING_OVERDESIGN_GOVERNS
    if s.zero_shear_with_reinforcement or (
        s.shear_domain
        and s.shear_util < 0.85
        and (not s.bending_domain or 0.85 <= s.bending_util <= 1.0)
    ):
        return DesignFamily.SHEAR_OVERDESIGN_GOVERNS
    if s.bending_domain or s.shear_domain:
        return DesignFamily.TARGET_BAND_REACHED
    return DesignFamily.EXACT_STOP_PROVEN


def verify_family_recipe_corpus() -> Counter[str]:
    cases = [case for case in DEBUG_CASES if case["name"].startswith(LIVE_PREFIX)]
    assert len(cases) == 90
    assert len({case["name"] for case in cases}) == 90
    counts: Counter[str] = Counter()

    for case in cases:
        label = _historical_label(case["name"])
        state = build_state(case["changes"])
        snapshot = build_engineering_input_snapshot_from_resolved_state(state)
        try:
            inputs, *_ = _beam_inputs_from_snapshot(snapshot, _v2_api(), 0, state)
        except EngineeringInputValidationError as exc:
            assert label == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
            assert state["lig_legs"] == 3
            assert "Shear link legs must be 2, 4, 6 or 8" in str(exc)
            counts["invalid_input_fixture"] += 1
            continue

        result = EngineeringCalculator().calculate(inputs)
        independently_derived = _independent_family(_independent_signals(inputs, result))
        production = classify_design_family(result, inputs)
        assert production is independently_derived, (
            f"{case['name']}: production={production.value}, "
            f"independent={independently_derived.value}"
        )

        if label == production.value:
            counts["confirmed"] += 1
        elif LEGACY_ALIASES.get(label) is production:
            counts["alias"] += 1
        elif (
            label == "BENDING_FAIL_GOVERNS"
            and production is DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS
        ):
            counts["mislabeled_fixture"] += 1
        else:
            raise AssertionError(
                f"unclassified corpus difference: {case['name']} => {production.value}"
            )

    assert counts == Counter(
        confirmed=40,
        alias=30,
        mislabeled_fixture=10,
        invalid_input_fixture=10,
    )
    return counts


def main() -> None:
    counts = verify_family_recipe_corpus()
    details = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    print(f"family recipe corpus contract: PASS (90 cases; {details})")


if __name__ == "__main__":
    main()
