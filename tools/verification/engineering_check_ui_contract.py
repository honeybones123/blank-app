from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bending_layer_semantics import resolve_bending_faces, resolve_bending_layer_geometry
from engineering_check_ui import (
    BENDING_DETAIL_CHECK_COLUMNS,
    DEFLECTION_CHECK_SUMMARY_COLUMNS,
    ENGINEERING_CHECK_COLUMNS,
    finalize_bending_check_row,
    resolve_jump_target_id,
    summary_cell_display,
    sync_legacy_value_limit,
)


def test_column_contracts() -> None:
    assert [col["key"] for col in ENGINEERING_CHECK_COLUMNS] == [
        "title",
        "capacity",
        "action",
        "util",
        "status",
    ]
    assert [col["key"] for col in DEFLECTION_CHECK_SUMMARY_COLUMNS] == [
        "title",
        "calculated",
        "requirement",
        "util",
        "status",
    ]
    assert [col["key"] for col in BENDING_DETAIL_CHECK_COLUMNS] == [
        "title",
        "calculated",
        "requirement",
        "util",
        "status",
    ]


def test_jump_target_contracts() -> None:
    assert resolve_jump_target_id({"jump_target_id": "explicit_step", "uid": "bend_strength_pos"}) == "explicit_step"
    assert resolve_jump_target_id({"uid": "bend_strength_pos"}) == "bending_uls_1_7"
    assert resolve_jump_target_id({"uid": "defl_total"}) == "defl_long"
    assert resolve_jump_target_id({"uid": "shear_check6"}) == "shear_check6"
    assert resolve_jump_target_id({}) == ""


def test_summary_cell_display_contracts() -> None:
    row = {
        "title": "Strength",
        "value": "150 kNm",
        "limit": "120 kNm",
        "util": "0.80",
        "status": "PASS",
    }
    assert summary_cell_display(row, "capacity") == "150 kNm"
    assert summary_cell_display(row, "action") == "120 kNm"
    assert summary_cell_display(row, "calculated") == "150 kNm"
    assert summary_cell_display(row, "requirement") == "120 kNm"
    assert summary_cell_display(row, "title") == "Strength"
    assert summary_cell_display(row, "missing") == ""


def test_bending_row_legacy_mirror_contract() -> None:
    row = finalize_bending_check_row({"title": "Bending", "calculated": "180 kNm", "requirement": "125 kNm"})
    assert row["capacity"] == "180 kNm"
    assert row["value"] == "180 kNm"
    assert row["action"] == "125 kNm"
    assert row["limit"] == "125 kNm"

    legacy = sync_legacy_value_limit({"capacity": "200 kN", "action": "150 kN"})
    assert legacy["value"] == "200 kN"
    assert legacy["limit"] == "150 kN"


def test_bending_face_semantics_contract() -> None:
    assert resolve_bending_faces("positive") == ("bottom", "top", False)
    assert resolve_bending_faces("negative") == ("top", "bottom", True)
    assert resolve_bending_faces("") == ("bottom", "top", False)


def test_bending_layer_geometry_contract() -> None:
    layout = {
        "reo_points": [
            {"layer": "bottom", "x": 100, "y": 650},
            {"layer": "bottom", "x": 200, "y": 660},
            {"layer": "top", "x": 100, "y": 55},
            {"layer": "top", "x": 200, "y": 65},
        ]
    }
    sagging = resolve_bending_layer_geometry(layout, moment_sign="positive", D=750, fallback_y_tension=620)
    assert sagging["tension_face"] == "bottom"
    assert sagging["compression_face"] == "top"
    assert sagging["d_value"] == 660
    assert sagging["d_prime_value"] == 60
    assert sagging["compression_block_face"] == "top"

    hogging = resolve_bending_layer_geometry(layout, moment_sign="negative", D=750, fallback_y_tension=90)
    assert hogging["tension_face"] == "top"
    assert hogging["compression_face"] == "bottom"
    assert hogging["d_value"] == 695
    assert hogging["d_prime_value"] == 95
    assert hogging["compression_block_face"] == "bottom"


def main() -> int:
    test_column_contracts()
    test_jump_target_contracts()
    test_summary_cell_display_contracts()
    test_bending_row_legacy_mirror_contract()
    test_bending_face_semantics_contract()
    test_bending_layer_geometry_contract()
    print("engineering_check_ui_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
