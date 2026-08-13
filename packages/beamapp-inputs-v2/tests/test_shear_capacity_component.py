from types import SimpleNamespace

import pytest

from inputs_v2.engineering.legacy_snapshot.shear import (
    compute_shear_capacity_values as legacy_calculate,
)
from inputs_v2.engineering.shear_capacity import (
    ShearCapacityInput,
    compute_shear_capacity_values,
    torsion_section_geometry_values,
)


def _input(**changes) -> ShearCapacityInput:
    values = dict(
        b=300.0, D=600.0, d=550.0, fc=32.0, fsy=500.0,
        Ec=30000.0, Es=200000.0, M_star=180.0, V_star=160.0,
        T_star=0.0, N_star=0.0, P_v=0.0, phi=0.75, sigma_cp=0.0,
        A_st=2454.0, A_pt=402.0, f_po=0.0, A_ct=90000.0, d_g=20.0,
        lig_d=10.0, legs=2.0, s_lig=200.0, use_general_kv=False,
        sum_duct=0.0, k_d=1.0,
    )
    values.update(changes)
    return ShearCapacityInput(**values)


@pytest.mark.parametrize(
    "values",
    [
        _input(),
        _input(T_star=0.0, V_star=300.0, use_general_kv=True),
        _input(legs=0.0, lig_d=None, s_lig=None, fc=65.0),
        _input(N_star=-500.0, A_pt=0.0, A_st=500.0, sum_duct=50.0),
    ],
)
def test_shear_capacity_preserves_snapshot_numerical_parity(values) -> None:
    current = compute_shear_capacity_values(values)
    legacy = legacy_calculate(SimpleNamespace(**vars(values)))
    assert current.keys() == legacy.keys()
    for key, expected in legacy.items():
        if key in {"uh", "A_oh"}:
            # The legacy snapshot used an incorrect one-sided cover deduction.
            # Current values are independently checked at the link centre-line.
            continue
        if isinstance(expected, bool):
            assert current[key] is expected
        else:
            assert current[key] == pytest.approx(expected, rel=0.0, abs=1e-12, nan_ok=True)


def test_general_method_enforces_clause_82422_minimum_moment_term() -> None:
    values = _input(
        M_star=0.0,
        V_star=300.0,
        T_star=0.0,
        N_star=0.0,
        P_v=0.0,
        A_pt=0.0,
        f_po=0.0,
        A_st=1500.0,
        use_general_kv=True,
    )

    result = compute_shear_capacity_values(values)
    expected_force_n = 300.0 * 1_000.0
    expected_eps_x = expected_force_n / (values.Es * values.A_st)
    expected_kv = 0.4 / (1.0 + 1500.0 * expected_eps_x)

    assert result["term_M"] == pytest.approx(expected_force_n)
    assert result["eps_x"] == pytest.approx(expected_eps_x)
    assert result["k_v"] == pytest.approx(expected_kv)
    assert result["theta_v_deg"] == pytest.approx(29.0 + 7000.0 * expected_eps_x)


def test_general_method_combined_shear_torsion_matches_clause_82423() -> None:
    values = _input(
        M_star=180.0,
        V_star=300.0,
        T_star=80.0,
        P_v=0.0,
        N_star=0.0,
        A_pt=0.0,
        f_po=0.0,
        A_st=2_454.0,
        use_general_kv=True,
    )

    result = compute_shear_capacity_values(values)
    moment_force = values.M_star * 1_000_000.0 / result["d_v"]
    shear_force = values.V_star * 1_000.0
    torsion_force = (
        0.9 * values.T_star * 1_000_000.0 * result["uh"]
        / (2.0 * result["Ao"])
    )
    raw_resultant = (
        (moment_force + shear_force) ** 2 + torsion_force**2
    ) ** 0.5
    expected_resultant = max(raw_resultant, shear_force + torsion_force)
    expected_strain = expected_resultant / (
        2.0 * values.Es * values.A_st
    )

    assert result["torsion_required"] is True
    assert result["sqrt_inner"] == pytest.approx(expected_resultant)
    assert result["numerator"] == pytest.approx(expected_resultant)
    assert result["eps_x"] == pytest.approx(expected_strain)


def test_torsion_link_geometry_uses_actual_cover_and_link_centreline() -> None:
    result = torsion_section_geometry_values(
        300.0,
        500.0,
        cover_t_mm=35.0,
        link_diameter_mm=12.0,
    )

    # Centre-line offset = clear cover + half the closed-link diameter.
    assert result["A_oh"] == pytest.approx((300.0 - 82.0) * (500.0 - 82.0))
    assert result["uh"] == pytest.approx(2.0 * ((300.0 - 82.0) + (500.0 - 82.0)))
