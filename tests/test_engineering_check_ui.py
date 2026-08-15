from engineering_check_ui import BENDING_ROW_UID_TO_TAB, resolve_jump_target_id


def test_v2_bending_summary_rows_resolve_to_retained_detail_cards() -> None:
    expected = {
        "v2_bending_capacity": ("bending_uls_1_7", "ULS Checks"),
        "v2_bending_minimum_tensile": ("bending_min_2_5", "Minimum strength checks"),
        "v2_bending_ductility": ("bending_uls_1_5", "ULS Checks"),
        "v2_bending_service_moment": ("bending_sls_3_4", "SLS Checks"),
        "v2_bending_minimum_capacity": ("bending_min_2_4", "Minimum strength checks"),
    }

    for uid, (anchor, tab) in expected.items():
        assert resolve_jump_target_id({"uid": uid}) == anchor
        assert BENDING_ROW_UID_TO_TAB[uid] == tab
