from __future__ import annotations

import pytest

from inputs_application.engineering_input_store import (
    BEAM_SNAPSHOT_STATE_KEY,
    LEGACY_BEAM_COMMITTED_STATE_KEY,
    TRANSACTION_META_KEY,
    InputSnapshotStore,
)


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


def test_legacy_beam_snapshot_is_migrated_once_then_removed() -> None:
    state: dict[str, object] = {
        TRANSACTION_META_KEY: {"revision": 7},
        LEGACY_BEAM_COMMITTED_STATE_KEY: {
            "B1": {"b": 325.0, "nested": {"bars": [4, 4]}},
        },
    }

    store = InputSnapshotStore(state)
    migrated = store.current_for_beam("B1")

    assert LEGACY_BEAM_COMMITTED_STATE_KEY not in state
    assert migrated.revision == 7
    assert migrated.source == "legacy_beam_snapshot_migration"
    assert migrated.to_dict() == {"b": 325.0, "nested": {"bars": [4, 4]}}
    assert "B1" in state[BEAM_SNAPSHOT_STATE_KEY]  # type: ignore[operator]


def test_beam_commit_never_recreates_retired_legacy_store() -> None:
    state: dict[str, object] = {
        LEGACY_BEAM_COMMITTED_STATE_KEY: {"B1": {"b": 300.0}},
    }
    store = InputSnapshotStore(state)

    store.commit_for_beam("B1", {"b": 350.0}, changed_keys=("b",), source="test")

    assert LEGACY_BEAM_COMMITTED_STATE_KEY not in state
    assert store.current_for_beam("B1").snapshot["b"] == 350.0
