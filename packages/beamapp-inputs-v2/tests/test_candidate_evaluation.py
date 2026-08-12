from inputs_v2.application.candidate_evaluation import compliance_rejection_codes
from inputs_v2.domain.engineering_result import EngineeringResult


def test_candidate_rejection_evidence_names_every_failed_mandatory_check() -> None:
    result = EngineeringResult(
        source_revision=1,
        source_hash="fixture",
        status="FAIL",
        summary="fixture",
        families={
            "bending": {"status": "FAIL", "minimum_tensile_status": "FAIL"},
            "ductility": {"status": "FAIL"},
            "geometry": {"status": "FAIL"},
            "serviceability": {"status": "FAIL"},
            "crack_control": {"status": "FAIL"},
            "shear": {
                "shear_ok": False,
                "web_ok": False,
                "Asv": 100.0,
                "transverse_reinforcement_required": True,
                "min_shear_ok": False,
                "spacing_ok": False,
                "transverse_spacing_ok": False,
            },
            "reinforcement_fit": {"accepted": False},
        },
    )

    assert compliance_rejection_codes(result) == (
        "bending_fail",
        "ductility_fail",
        "geometry_fail",
        "serviceability_fail",
        "crack_control_fail",
        "minimum_tensile_reinforcement_failed",
        "shear_strength_failed",
        "shear_web_crushing_failed",
        "minimum_shear_reinforcement_failed",
        "shear_spacing_failed",
        "transverse_shear_leg_spacing_failed",
        "reinforcement_fit_failed",
    )
