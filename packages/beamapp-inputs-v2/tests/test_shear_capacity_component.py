from types import SimpleNamespace

import pytest

from inputs_v2.engineering.legacy_snapshot.shear import (
    compute_shear_capacity_values as legacy_calculate,
)
from inputs_v2.engineering.shear_capacity import (
    ShearCapacityInput,
    compute_shear_capacity_values,
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
        _input(T_star=80.0, V_star=300.0, use_general_kv=True),
        _input(legs=0.0, lig_d=None, s_lig=None, fc=65.0),
        _input(N_star=-500.0, A_pt=0.0, A_st=500.0, sum_duct=50.0),
    ],
)
def test_shear_capacity_preserves_snapshot_numerical_parity(values) -> None:
    current = compute_shear_capacity_values(values)
    legacy = legacy_calculate(SimpleNamespace(**vars(values)))
    assert current.keys() == legacy.keys()
    for key, expected in legacy.items():
        if isinstance(expected, bool):
            assert current[key] is expected
        else:
            assert current[key] == pytest.approx(expected, rel=0.0, abs=1e-12, nan_ok=True)
