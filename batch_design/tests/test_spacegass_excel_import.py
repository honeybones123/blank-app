import pandas as pd
from pathlib import Path

from batch_design.importers.spacegass_excel import SpaceGassExcelImporter
from batch_design.validation import validate_batch_cases


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_spacegass_csv_import_normalises_final_member_actions(tmp_path):
    csv_path = tmp_path / "spacegass.csv"
    pd.DataFrame(
        [
            {
                "Member": "12",
                "Member Size": "310UB40",
                "Length": 6.2,
                "N*": 10.0,
                "Vy*": 2.0,
                "Vz*": 55.0,
                "Mx*": 1.0,
                "My*": 8.0,
                "Mz*": 130.0,
                "Confidence": 0.92,
                "Governing Combo": "ULS-3",
            }
        ]
    ).to_csv(csv_path, index=False)

    imported = SpaceGassExcelImporter().import_rows(csv_path)

    assert imported.warnings == []
    assert imported.rows[0].member_id == "12"
    assert imported.rows[0].existing_section is None
    assert any(
        warning.severity == "warning" and warning.field == "existing_section"
        for warning in imported.rows[0].warnings
    )
    assert imported.rows[0].mz_star == 130.0
    assert validate_batch_cases(imported.rows).valid


def test_spacegass_valid_fixture_includes_source_metadata_and_confidence():
    imported = SpaceGassExcelImporter().import_rows(FIXTURE_DIR / "spacegass_valid_member_actions.csv")

    assert len(imported.rows) == 2
    assert imported.rows[0].member_id == "101"
    assert imported.rows[0].source.value == "spacegass_excel"
    assert imported.rows[0].existing_section is None
    assert imported.rows[0].confidence == 0.92
    assert imported.rows[0].governing_metadata["governing"] == "ULS-3"
    assert imported.rows[0].governing_metadata["governing_location"] == "2.6m"
    assert imported.rows[0].governing_metadata["source"] == "spacegass-final-actions.xlsx"
    assert validate_batch_cases(imported.rows).valid


def test_spacegass_alternate_column_fixture_is_supported():
    imported = SpaceGassExcelImporter().import_rows(FIXTURE_DIR / "spacegass_alternate_columns.csv")

    row = imported.rows[0]
    assert row.member_id == "201"
    assert row.existing_section == "RECT 300 x 600"
    assert row.length == 5.8
    assert row.vz_star == 45.0
    assert row.mz_star == 110.0
    assert row.governing_metadata["governing"] == "Envelope-A"
    assert row.governing_metadata["governing_location"] == "midspan"


def test_spacegass_invalid_fixture_surfaces_bad_rows_before_validation():
    imported = SpaceGassExcelImporter().import_rows(FIXTURE_DIR / "spacegass_invalid_member_actions.csv")

    invalid_numeric_row = next(row for row in imported.rows if row.member_id == "302")
    assert any(warning.severity == "error" and warning.field == "n_star" for warning in invalid_numeric_row.warnings)

    blank_id_row = next(row for row in imported.rows if not row.member_id)
    assert any(warning.severity == "error" and warning.field == "member_id" for warning in blank_id_row.warnings)
