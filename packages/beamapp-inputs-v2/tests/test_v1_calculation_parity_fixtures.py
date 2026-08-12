import pytest

from inputs_v2.engineering.engineering_calculator import EngineeringCalculator
from inputs_v2.domain.beam_inputs import ActionInputs, BeamInputs


@pytest.mark.parametrize(
    ("inputs", "phi_mu", "phi_vu"),
    [
        (BeamInputs().validated(), 26.225658214998063, 27.215352112824114),
        (BeamInputs(width_mm=300.0, depth_mm=500.0).validated(), 46.838674389902366, 58.27287158275281),
    ],
)
def test_authoritative_calculation_regression_fixtures(inputs: BeamInputs, phi_mu: float, phi_vu: float) -> None:
    result = EngineeringCalculator().calculate(inputs)
    assert result.source_revision == inputs.revision
    assert result.source_hash == inputs.content_hash
    assert result.families["bending"]["phi_Mu_kNm"] == pytest.approx(phi_mu, rel=2e-3)
    assert result.families["shear"]["phi_Vu"] == pytest.approx(phi_vu, rel=2e-3)
    assert result.families["serviceability"]["limit_mm"] > 0
    assert result.families["crack_control"]["limit_mm"] == pytest.approx(0.30)
