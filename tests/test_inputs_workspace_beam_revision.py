from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_application.workspace_state_store import InputsWorkspaceStateStore


def test_workspace_revision_follows_active_beam_not_global_commit_counter() -> None:
    state = {"active_beam_id": "beam_1"}
    snapshots = InputSnapshotStore(state)
    beam_1 = snapshots.commit_active_beam(
        {"b": 300.0, "D": 600.0},
        source="test:beam_1",
    )
    state["active_beam_id"] = "beam_2"
    beam_2 = snapshots.commit_active_beam(
        {"b": 250.0, "D": 300.0},
        source="test:beam_2",
    )

    # The compatibility/global transaction is now revision 2, while the new
    # beam correctly owns its first revision.
    assert snapshots.current().revision == 2
    assert beam_1.revision == 1
    assert beam_2.revision == 1
    assert InputsWorkspaceStateStore(state).workspace_revision() == 1

    state["active_beam_id"] = "beam_1"
    assert InputsWorkspaceStateStore(state).workspace_revision() == 1


def test_each_beam_keeps_an_independent_workspace_revision() -> None:
    state = {"active_beam_id": "beam_1"}
    snapshots = InputSnapshotStore(state)
    snapshots.commit_active_beam(
        {"b": 300.0, "D": 600.0},
        source="test:beam_1:first",
    )
    state["active_beam_id"] = "beam_2"
    snapshots.commit_active_beam(
        {"b": 250.0, "D": 300.0},
        source="test:beam_2:first",
    )
    state["active_beam_id"] = "beam_1"
    snapshots.commit_active_beam(
        {"b": 325.0, "D": 650.0},
        source="test:beam_1:second",
    )

    assert InputsWorkspaceStateStore(state).workspace_revision() == 2
    state["active_beam_id"] = "beam_2"
    assert InputsWorkspaceStateStore(state).workspace_revision() == 1
