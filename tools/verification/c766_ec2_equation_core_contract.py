"""Executable checks for the source-verified C766/EC2 equation core."""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from application.contracts.concrete_crack_shrinkage import (  # noqa: E402
    C766CrackControlInput,
    C766EndRestraintInput,
    C766MinimumReinforcementInput,
    CementClass,
    EC2C766ShrinkageInput,
    RestraintType,
)
from calculations.concrete_crack_shrinkage_methods import (  # noqa: E402
    calculate_c766_crack_control,
    calculate_c766_end_restraint,
    calculate_c766_minimum_reinforcement,
    calculate_ec2_c766_shrinkage,
)


def main() -> None:
    # C766 corrected simplified early-age expression: 0.5*a_c*T1 - 0.5*eps_ctu.
    early = calculate_c766_crack_control(
        C766CrackControlInput(
            restraint_type=RestraintType.CONTINUOUS_EDGE,
            temperature_drop_early_c=20.0,
            temperature_change_long_term_c=0.0,
            thermal_expansion_per_c=12e-6,
            autogenous_shrinkage_early=0.0,
            autogenous_shrinkage_long_term=0.0,
            drying_shrinkage=0.0,
            restraint_early=0.5 / 0.65,
            restraint_medium=0.0,
            restraint_long_term=0.0,
            tensile_strain_capacity=70e-6,
            cover_mm=45.0,
            bar_diameter_mm=20.0,
            effective_reinforcement_ratio=0.01,
        )
    )
    assert math.isclose(early.restrained_strain, 120e-6)
    assert early.crack_initiates is True
    assert math.isclose(early.crack_inducing_strain, 85e-6)
    assert math.isclose(early.maximum_crack_spacing_mm, 833.0)
    assert math.isclose(early.characteristic_crack_width_mm, 0.070805)

    minimum = calculate_c766_minimum_reinforcement(
        C766MinimumReinforcementInput(
            concrete_tension_area_mm2=250_000.0,
            mean_tensile_strength_at_cracking_mpa=3.0,
            reinforcement_yield_strength_mpa=500.0,
            stress_distribution_coefficient_kc=1.0,
            non_uniform_stress_coefficient_k=1.0,
            edge_restraint_factor=1.0,
        )
    )
    assert minimum.edge_load_transfer_coefficient == 0.5
    assert math.isclose(minimum.required_area_mm2, 525.0)

    end = calculate_c766_end_restraint(
        C766EndRestraintInput(
            effective_modular_ratio=7.0,
            non_uniform_stress_coefficient_k=0.65,
            stress_distribution_coefficient_kc=1.0,
            characteristic_tensile_strength_at_cracking_mpa=2.0,
            reinforcement_modulus_mpa=200_000.0,
            reinforcement_ratio_total_to_tension_area=0.01,
            cover_mm=45.0,
            bar_diameter_mm=20.0,
            effective_reinforcement_ratio=0.01,
        )
    )
    expected_end_strain = 0.5 * 7.0 * 0.65 * 2.0 / 200_000.0 * (1.0 + 1.0 / 0.07)
    assert math.isclose(end.crack_inducing_strain, expected_end_strain)
    assert math.isclose(end.characteristic_crack_width_mm, 833.0 * expected_end_strain)

    shrinkage = calculate_ec2_c766_shrinkage(
        EC2C766ShrinkageInput(
            characteristic_cylinder_strength_mpa=40.0,
            relative_humidity_percent=51.0,
            cement_class=CementClass.SLOW,
            concrete_area_mm2=600_000.0,
            drying_perimeter_mm=2_000.0,
            age_days=36_500.0,
            drying_start_age_days=7.0,
        )
    )
    assert shrinkage.mean_compressive_strength_mpa == 48.0
    assert shrinkage.notional_size_mm == 600.0
    assert shrinkage.size_coefficient_kh == 0.70
    assert math.isclose(shrinkage.drying_shrinkage * 1e6, 312.3834356351677)
    assert math.isclose(shrinkage.autogenous_shrinkage * 1e6, 75.0)

    print("PASS: source-verified CIRIA C766 / EC2 equation core contract")


if __name__ == "__main__":
    main()
