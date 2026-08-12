from __future__ import annotations

import pytest

from inputs_application.engineering_input_store import InputSnapshotStore


def test_committed_snapshot_is_recursively_immutable_and_hash_stable() -> None:
    state: dict[str, object] = {}
    store = InputSnapshotStore(state)
    committed = store.commit_for_beam(
        "B1",
        {"b": 300.0, "nested": {"rows": [{"bars": 4}]}},
        source="test",
    )
    original_hash = committed.engineering_hash

    with pytest.raises(TypeError):
        committed.snapshot["b"] = 350.0  # type: ignore[index]
    with pytest.raises(TypeError):
        committed.snapshot["nested"]["rows"][0]["bars"] = 6  # type: ignore[index]

    exported = committed.to_dict()
    exported["nested"]["rows"][0]["bars"] = 6
    reread = store.current_for_beam("B1")
    assert reread.snapshot["nested"]["rows"][0]["bars"] == 4
    assert reread.engineering_hash == original_hash


def test_committed_returns_a_defensive_copy() -> None:
    state: dict[str, object] = {}
    store = InputSnapshotStore(state)
    store.commit_for_beam("B1", {"b": 300.0}, source="test")

    exported = store.committed()
    exported["b"] = 400.0

    assert store.current().snapshot["b"] == 300.0
