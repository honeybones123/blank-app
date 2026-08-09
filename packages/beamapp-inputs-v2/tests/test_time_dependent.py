import math

import pytest

from inputs_v2.domain.beam_inputs import BeamInputs, TimeDependentInputs
from inputs_v2.engineering.legacy_snapshot.creep_shrinkage import calc_k3
from inputs_v2.engineering.engineering_calculator import EngineeringCalculator
from inputs_v2.engineering.time_dependent import (
    LoadingAgeFactorInput,
    calculate_loading_age_factor,
)


@pytest.mark.parametrize("age_days", [-20.0, 0.0, 1.0, 3.0, 7.0, 28.0, 365.0, 10_000.0])
def test_loading_age_factor_preserves_snapshot_numerical_parity(age_days: float) -> None:
    result = calculate_loading_age_factor(LoadingAgeFactorInput(age_days))
    assert result.k3 == pytest.approx(calc_k3(age_days), rel=0.0, abs=1e-15)
    assert result.effective_age_days == max(age_days, 1.0)


@pytest.mark.parametrize("age_days", [math.nan, math.inf, -math.inf])
def test_loading_age_factor_rejects_non_finite_age(age_days: float) -> None:
    with pytest.raises(ValueError, match="must be finite"):
        calculate_loading_age_factor(LoadingAgeFactorInput(age_days))


def test_authoritative_calculator_uses_v2_owned_loading_age_component() -> None:
    inputs = BeamInputs(
        time_dependent=TimeDependentInputs(age_at_loading_days=28.0)
    ).validated()
    result = EngineeringCalculator().calculate(inputs)
    expected = calculate_loading_age_factor(LoadingAgeFactorInput(28.0))
    assert result.source_revision == inputs.revision
    assert result.source_hash == inputs.content_hash
    assert result.families["creep_shrinkage"]["k3_age_loading"] == expected.k3
