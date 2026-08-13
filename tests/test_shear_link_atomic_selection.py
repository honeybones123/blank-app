from inputs_application.shear_state_normalization import normalize_shear_link_pair


def test_selecting_diameter_activates_two_legs_atomically():
    assert normalize_shear_link_pair(
        {"lig_d": 10, "lig_legs": 0}, changed_key="lig_d"
    ) == {"lig_d": 10, "lig_legs": 2}


def test_turning_diameter_off_turns_legs_off_atomically():
    assert normalize_shear_link_pair(
        {"lig_d": 0, "lig_legs": 4}, changed_key="lig_d"
    ) == {"lig_d": 0, "lig_legs": 0}


def test_selecting_legs_activates_starter_diameter_atomically():
    assert normalize_shear_link_pair(
        {"lig_d": 0, "lig_legs": 4}, changed_key="lig_legs"
    ) == {"lig_d": 10, "lig_legs": 4}


def test_turning_legs_off_turns_diameter_off_atomically():
    assert normalize_shear_link_pair(
        {"lig_d": 16, "lig_legs": 0}, changed_key="lig_legs"
    ) == {"lig_d": 0, "lig_legs": 0}


def test_adapter_boundary_repairs_legacy_half_on_pair():
    assert normalize_shear_link_pair({"lig_d": 12, "lig_legs": 0}) == {
        "lig_d": 12,
        "lig_legs": 2,
    }
