import pytest

from inputs_v2.application.calculation_coordinator import calculate_legacy_shadow_current
from inputs_v2.application.design_brain_families import DesignFamily, classify_design_family, design_signals
from inputs_v2.domain.beam_inputs import ActionInputs, BeamInputs, ShearReinforcement
from inputs_v2.domain.engineering_result import EngineeringResult


def _classification_result(bending_util: float, shear_util: float) -> EngineeringResult:
    return EngineeringResult(
        source_revision=0,
        source_hash="fixture",
        status="complete",
        summary="family regression fixture",
        families={
            "bending": {"util": bending_util},
            "shear": {"phi_Vu": 100.0, "V_eq": 100.0 * shear_util},
            "serviceability": {"status": "PASS"},
            "crack_control": {"status": "PASS"},
        },
    )


def test_no_design_actions_select_typed_input_required_family_first() -> None:
    inputs = BeamInputs().validated()
    result = calculate_legacy_shadow_current(inputs)
    assert result is not None
    assert classify_design_family(result, inputs) is DesignFamily.INPUT_REQUIRED


def test_family_classifier_selects_shear_failure() -> None:
    inputs = BeamInputs(actions=ActionInputs(shear_force_kn=300.0)).validated()
    result = calculate_legacy_shadow_current(inputs)
    assert result is not None
    assert classify_design_family(result) is DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS


def test_family_classifier_selects_combined_failure() -> None:
    inputs = BeamInputs(actions=ActionInputs(bending_moment_knm=1000.0, shear_force_kn=300.0)).validated()
    result = calculate_legacy_shadow_current(inputs)
    assert result is not None
    assert classify_design_family(result) is DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN


def test_family_classifier_selects_geometry_blocker_before_strength_family() -> None:
    inputs = BeamInputs(
        width_mm=200.0,
        depth_mm=450.0,
        actions=ActionInputs(bending_moment_knm=10.0),
    ).validated()
    result = calculate_legacy_shadow_current(inputs)
    assert result is not None
    assert classify_design_family(result, inputs) is DesignFamily.GEOMETRY_DETAILING_GOVERNS


def test_serviceability_result_is_calculated_and_can_governs() -> None:
    inputs = BeamInputs(
        actions=ActionInputs(bending_moment_knm=5000.0),
        serviceability=BeamInputs().serviceability.__class__(moment_knm=5000.0),
    ).validated()
    result = calculate_legacy_shadow_current(inputs)
    assert result is not None
    assert "deflection_util" in result.families["serviceability"]
    assert result.families["serviceability"]["status"] == "FAIL"
    assert classify_design_family(result, inputs) is not DesignFamily.EXACT_STOP_PROVEN


def test_single_family_overdesign_is_distinct() -> None:
    inputs = BeamInputs(actions=ActionInputs(shear_force_kn=24.5)).validated()
    result = calculate_legacy_shadow_current(inputs)
    assert result is not None
    assert classify_design_family(result, inputs) is DesignFamily.BENDING_OVERDESIGN_GOVERNS


def test_target_band_requires_every_active_uls_domain_to_be_in_band() -> None:
    inputs = BeamInputs(
        actions=ActionInputs(bending_moment_knm=500.0, shear_force_kn=300.0),
        shear=ShearReinforcement(diameter_mm=12, legs=2, spacing_mm=200),
    ).validated()
    assert classify_design_family(_classification_result(0.74, 0.98), inputs) is DesignFamily.BENDING_OVERDESIGN_GOVERNS
    assert classify_design_family(_classification_result(0.95, 0.41), inputs) is DesignFamily.SHEAR_OVERDESIGN_GOVERNS
    assert classify_design_family(_classification_result(0.95, 0.98), inputs) is DesignFamily.TARGET_BAND_REACHED


@pytest.mark.parametrize(
    ("bending_util", "shear_util", "expected"),
    (
        (1.20, 1.20, DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN),
        (1.20, 0.40, DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS),
        (1.20, 0.95, DesignFamily.BENDING_FAIL_GOVERNS),
        (0.40, 1.20, DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS),
        (0.95, 1.20, DesignFamily.SHEAR_FAIL_GOVERNS),
        (0.40, 0.40, DesignFamily.COMBINED_OVERDESIGN),
        (0.40, 0.95, DesignFamily.BENDING_OVERDESIGN_GOVERNS),
        (0.95, 0.40, DesignFamily.SHEAR_OVERDESIGN_GOVERNS),
        (0.95, 0.95, DesignFamily.TARGET_BAND_REACHED),
    ),
)
def test_strength_family_regression_matrix(
    bending_util: float,
    shear_util: float,
    expected: DesignFamily,
) -> None:
    inputs = BeamInputs(
        actions=ActionInputs(bending_moment_knm=500.0, shear_force_kn=300.0),
        shear=ShearReinforcement(diameter_mm=12, legs=2, spacing_mm=200),
    ).validated()
    assert classify_design_family(_classification_result(bending_util, shear_util), inputs) is expected


def test_serviceability_family_regression_fixture() -> None:
    result = _classification_result(0.95, 0.95)
    result.families["crack_control"]["status"] = "FAIL"
    inputs = BeamInputs(
        actions=ActionInputs(bending_moment_knm=500.0, shear_force_kn=300.0),
        shear=ShearReinforcement(diameter_mm=12, legs=2, spacing_mm=200),
    ).validated()
    assert classify_design_family(result, inputs) is DesignFamily.SERVICEABILITY_GOVERNS


def test_serviceability_failure_is_not_hidden_by_uls_overdesign() -> None:
    result = _classification_result(0.40, 0.40)
    result.families["crack_control"]["status"] = "FAIL"
    inputs = BeamInputs(
        actions=ActionInputs(bending_moment_knm=500.0, shear_force_kn=300.0),
        shear=ShearReinforcement(diameter_mm=12, legs=2, spacing_mm=200),
    ).validated()
    assert classify_design_family(result, inputs) is DesignFamily.SERVICEABILITY_GOVERNS


def test_minimum_tensile_failure_is_routed_to_bending_repair_not_overdesign() -> None:
    inputs = BeamInputs(actions=ActionInputs(bending_moment_knm=10.0)).validated()
    result = calculate_legacy_shadow_current(inputs)
    assert result is not None
    assert result.families["bending"]["util"] < 0.85
    assert result.families["bending"]["minimum_tensile_status"] == "FAIL"
    assert classify_design_family(result, inputs) is DesignFamily.BENDING_FAIL_GOVERNS


def test_mandatory_shear_failure_is_routed_to_repair_even_below_summary_limit() -> None:
    inputs = BeamInputs(
        actions=ActionInputs(bending_moment_knm=500.0, shear_force_kn=300.0),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=600),
    ).validated()
    result = _classification_result(0.95, 0.90)
    result.families["shear"].update({
        "Asv": 157.0,
        "shear_ok": True,
        "web_ok": True,
        "transverse_reinforcement_required": True,
        "min_shear_ok": False,
        "spacing_ok": True,
    })
    assert classify_design_family(result, inputs) is DesignFamily.SHEAR_FAIL_GOVERNS


def test_zero_shear_demand_with_links_is_cleanup_not_failure() -> None:
    inputs = BeamInputs(
        actions=ActionInputs(bending_moment_knm=500.0, shear_force_kn=0.0),
        shear=ShearReinforcement(diameter_mm=12, legs=2, spacing_mm=200),
    ).validated()
    result = _classification_result(0.95, 0.0)
    result.families["shear"].update({
        "Asv": 226.0,
        "shear_ok": True,
        "web_ok": True,
        "transverse_reinforcement_required": False,
        "min_shear_ok": False,
        "spacing_ok": True,
    })
    signals = design_signals(result, inputs)
    assert signals.shear_failed is False
    assert classify_design_family(result, inputs) is DesignFamily.SHEAR_OVERDESIGN_GOVERNS
