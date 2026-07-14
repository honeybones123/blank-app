from batch_design.models import BatchBeamCase, BatchImportWarning
from batch_design.validation import validate_batch_cases, validate_beam_case


def test_validation_rejects_rows_without_member_id():
    errors, warnings = validate_beam_case(BatchBeamCase(member_id="", mz_star=10.0))

    assert warnings == []
    assert any(error.field == "member_id" for error in errors)


def test_validation_rejects_rows_without_final_design_actions():
    result = validate_batch_cases([BatchBeamCase(member_id="M1")])

    assert not result.valid
    assert result.invalid_cases[0].member_id == "M1"


def test_validation_accepts_member_with_one_design_action():
    result = validate_batch_cases([BatchBeamCase(member_id="M1", mz_star=10.0)])

    assert result.valid
    assert result.valid_cases[0].member_id == "M1"


def test_validation_detects_duplicate_member_ids():
    result = validate_batch_cases(
        [
            BatchBeamCase(member_id="M1", mz_star=10.0),
            BatchBeamCase(member_id="M1", mz_star=12.0),
        ]
    )

    assert not result.valid
    assert any(error.field == "member_id" and "Duplicate" in error.message for error in result.errors)


def test_validation_flags_suspicious_zero_design_actions():
    result = validate_batch_cases([BatchBeamCase(member_id="M1", n_star=0.0, vy_star=0.0, vz_star=0.0, mx_star=0.0, my_star=0.0, mz_star=0.0)])

    assert not result.valid
    assert any(warning.field == "demands" and "zero or missing" in warning.message for warning in result.warnings)
    assert any(error.field == "demands" for error in result.errors)


def test_validation_promotes_importer_error_warnings_to_errors():
    case = BatchBeamCase(member_id="M1", mz_star=10.0)
    case.warnings.append(
        BatchImportWarning(
            row_number=2,
            member_id="M1",
            field="mz_star",
            severity="error",
            message="bad numeric action",
        )
    )
    result = validate_batch_cases([case])

    assert not result.valid
    assert any(error.field == "mz_star" and error.message == "bad numeric action" for error in result.errors)
