from application.engineering_snapshot import (
    build_engineering_input_snapshot_from_resolved_state,
)
from inputs_application.v2_engineering_calculation_adapter import (
    _beam_inputs_from_snapshot,
    _v2_api,
)


def test_shear_kv_method_is_part_of_engineering_identity_and_v2_input():
    general = build_engineering_input_snapshot_from_resolved_state(
        {"k_v_method": "General εx-based (Cl. 8.2.4.2)"}
    )
    simplified = build_engineering_input_snapshot_from_resolved_state(
        {"k_v_method": "Simplified non-prestressed (Cl. 8.2.4.3)"}
    )

    assert general.design_settings["k_v_method"] == (
        "General εx-based (Cl. 8.2.4.2)"
    )
    assert simplified.design_settings["k_v_method"] == (
        "Simplified non-prestressed (Cl. 8.2.4.3)"
    )
    assert general.engineering_hash != simplified.engineering_hash

    api = _v2_api()
    general_inputs, _rows, _loads = _beam_inputs_from_snapshot(
        general,
        api,
        revision=1,
    )
    simplified_inputs, _rows, _loads = _beam_inputs_from_snapshot(
        simplified,
        api,
        revision=1,
    )

    assert general_inputs.shear.kv_method is api["KvMethod"].GENERAL
    assert simplified_inputs.shear.kv_method is api["KvMethod"].SIMPLIFIED
