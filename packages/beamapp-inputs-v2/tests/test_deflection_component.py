import pytest

from inputs_v2.engineering.deflection import (
    DeflectionInput,
    calculate_deflection,
    derive_equivalent_udl_from_actions,
    resolve_equivalent_loads,
)
from inputs_v2.engineering.legacy_snapshot.deflection import (
    calc_deflection_as3600,
    calc_ief_simplified,
    derive_equiv_udl_from_actions,
    resolve_deflection_equiv_loads_from_inputs,
)


@pytest.mark.parametrize(
    "values",
    [
        DeflectionInput(6.0, 30000.0, 32.0, 300.0, 300.0, 550.0, 1963.5, 402.1, 8.0, 3.0, 0.4, "Simply supported"),
        DeflectionInput(3.5, 28000.0, 50.0, 250.0, 200.0, 420.0, 982.0, 0.0, 5.0, 7.0, 0.7, "Cantilever"),
        DeflectionInput(8.0, 35000.0, 65.0, 1000.0, 300.0, 700.0, 6000.0, 4000.0, 20.0, 10.0, 0.3, "Fixed-ended"),
        DeflectionInput(5.0, 30000.0, 25.0, 200.0, 200.0, 350.0, 0.0, 0.0, 0.0, 0.0, 0.4, "Continuous"),
    ],
)
def test_deflection_preserves_snapshot_numerical_parity(values: DeflectionInput) -> None:
    current = calculate_deflection(values)
    legacy_inertia, *_ = calc_ief_simplified(
        values.concrete_strength_mpa,
        values.effective_width_mm,
        values.web_width_mm,
        values.effective_depth_mm,
        values.tension_steel_area_mm2,
    )
    legacy = calc_deflection_as3600(
        values.span_m,
        values.concrete_modulus_mpa,
        legacy_inertia,
        values.permanent_udl_kn_per_m,
        values.imposed_udl_kn_per_m,
        values.sustained_load_factor,
        values.support_condition,
        values.tension_steel_area_mm2,
        values.compression_steel_area_mm2,
    )
    assert current.effective_inertia_mm4 == pytest.approx(legacy_inertia, rel=0.0, abs=1e-9)
    assert current.short_term_mm == pytest.approx(legacy["delta_short_total"], rel=0.0, abs=1e-12)
    assert current.sustained_short_term_mm == pytest.approx(legacy["delta_short_sust"], rel=0.0, abs=1e-12)
    assert current.long_term_addition_mm == pytest.approx(legacy["delta_long_add"], rel=0.0, abs=1e-12)
    assert current.total_mm == pytest.approx(legacy["delta_total"], rel=0.0, abs=1e-12)


@pytest.mark.parametrize(
    ("moment", "shear", "span", "support"),
    [
        (90.0, 60.0, 6.0, "Simply supported"),
        (45.0, None, 3.0, "Cantilever"),
        (None, 25.0, 5.0, "Continuous"),
        (10.0, 100.0, 4.0, "Fixed-ended"),
    ],
)
def test_equivalent_action_load_preserves_snapshot_parity(moment, shear, span, support) -> None:
    current = derive_equivalent_udl_from_actions(
        moment_knm=moment, shear_kn=shear, span_m=span, support_condition=support
    )
    legacy = derive_equiv_udl_from_actions(moment, shear, span, support)["w_kN_per_m"]
    assert current == pytest.approx(legacy, rel=0.0, abs=1e-15)


def test_load_source_precedence_preserves_snapshot_parity() -> None:
    legacy_derived = derive_equiv_udl_from_actions(None, None, 6.0, "Simply supported")
    expected = resolve_deflection_equiv_loads_from_inputs(
        derived=legacy_derived, w_sls=12.0, g_udl=8.0, q_udl=4.0
    )
    assert resolve_equivalent_loads(
        derived_udl=None, equivalent_udl=12.0, permanent_udl=8.0, imposed_udl=4.0
    ) == pytest.approx(expected, rel=0.0, abs=1e-15)


def test_deflection_rejects_non_finite_inputs() -> None:
    values = DeflectionInput(6.0, 30000.0, 32.0, 300.0, 300.0, 550.0, float("nan"), 0.0, 8.0, 3.0, 0.4, "Simply supported")
    with pytest.raises(ValueError, match="tension_steel_area_mm2 must be finite"):
        calculate_deflection(values)
