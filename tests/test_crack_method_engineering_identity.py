from application.engineering_snapshot import (
    build_engineering_input_snapshot_from_resolved_state,
)


def test_crack_control_method_is_part_of_engineering_identity():
    as3600 = build_engineering_input_snapshot_from_resolved_state(
        {"crack_control_method": "existing_as3600"}
    )
    ciria = build_engineering_input_snapshot_from_resolved_state(
        {"crack_control_method": "ciria_c766_ec2"}
    )

    assert as3600.design_settings["crack_control_method"] == "existing_as3600"
    assert ciria.design_settings["crack_control_method"] == "ciria_c766_ec2"
    assert as3600.engineering_hash != ciria.engineering_hash
