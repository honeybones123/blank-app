from application.beam_summary_policy import (
    BEAM_STATUS_FAIL,
    BEAM_STATUS_NOT_RUN,
    BEAM_STATUS_PASS,
    BEAM_STATUS_WARN,
    classify_beam_check_rows,
    get_beam_overall_status,
    normalize_beam_status,
)


def main() -> None:
    assert normalize_beam_status("PASS", utilisation=0.89) == BEAM_STATUS_PASS
    assert normalize_beam_status("OK", utilisation=0.90) == BEAM_STATUS_WARN
    assert normalize_beam_status(utilisation=1.01) == BEAM_STATUS_FAIL
    assert normalize_beam_status("INFO") == BEAM_STATUS_NOT_RUN

    classified = classify_beam_check_rows(
        bending_rows=[
            {"title": "Flexural strength capacity", "status": "PASS"},
            {"title": "Ductility limit", "status": "FAIL"},
        ],
        shear_rows=[{"title": "Sectional shear capacity", "status": "PASS"}],
    )
    assert classified["strength_status"] == BEAM_STATUS_PASS
    assert classified["detailing_status"] == BEAM_STATUS_FAIL
    assert classified["overall_status"] == BEAM_STATUS_FAIL
    assert classified["notes"] == ["Ductility limit: FAIL"]

    assert get_beam_overall_status(
        {"strength_status": "PASS", "detailing_status": "WARN"}
    ) == BEAM_STATUS_WARN
    print("beam_summary_policy_contract PASS")


if __name__ == "__main__":
    main()
