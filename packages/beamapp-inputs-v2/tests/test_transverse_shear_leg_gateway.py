from inputs_v2.application.candidate_evaluation import (
    complete_compliance,
    compliance_rejection_codes,
)
from inputs_v2.domain.engineering_result import EngineeringResult


def _result(*, transverse_spacing_ok: bool) -> EngineeringResult:
    return EngineeringResult(
        1,
        "hash",
        "ready",
        "test",
        families={
            "bending": {"status": "PASS", "minimum_tensile_status": "PASS"},
            "ductility": {"status": "PASS"},
            "geometry": {"status": "PASS"},
            "serviceability": {"status": "PASS"},
            "crack_control": {"status": "PASS"},
            "reinforcement_fit": {"accepted": True},
            "shear": {
                "shear_ok": True,
                "web_ok": True,
                "Asv": 157.08,
                "transverse_reinforcement_required": True,
                "min_shear_ok": True,
                "spacing_ok": True,
                "transverse_spacing_ok": transverse_spacing_ok,
            },
        },
    )


def test_universal_gateway_rejects_failed_transverse_leg_spacing() -> None:
    result = _result(transverse_spacing_ok=False)
    assert complete_compliance(result) is False
    assert "transverse_shear_leg_spacing_failed" in compliance_rejection_codes(result)


def test_universal_gateway_accepts_passing_transverse_leg_spacing() -> None:
    result = _result(transverse_spacing_ok=True)
    assert complete_compliance(result) is True
    assert "transverse_shear_leg_spacing_failed" not in compliance_rejection_codes(result)
