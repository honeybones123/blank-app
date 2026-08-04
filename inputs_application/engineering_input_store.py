"""Explicit draft-to-committed Inputs engineering state boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import copy
import hashlib
import json
import math
from typing import Any, Mapping, MutableMapping


DRAFT_STATE_KEY = "_inputs_draft_engineering_state_v1"
COMMITTED_STATE_KEY = "_inputs_committed_engineering_state_v1"
TRANSACTION_META_KEY = "_inputs_engineering_input_transaction_v1"
TRANSACTION_TRACE_KEY = "_inputs_engineering_input_transaction_trace_v1"
BEAM_SNAPSHOT_STATE_KEY = "_inputs_engineering_input_snapshot_by_beam_v2"
LEGACY_BEAM_COMMITTED_STATE_KEY = "_inputs_committed_engineering_state_by_beam_v1"


def should_reuse_committed_engineering_baseline(
    *,
    committed_state_present: bool,
    active_beam_id: str,
    committed_beam_id: str,
    shared_only_mode: bool,
    same_beam_route_return: bool,
    snapshot_update_pending: bool,
) -> bool:
    """Return whether the stored baseline still owns the next snapshot."""

    return bool(
        committed_state_present
        and active_beam_id
        and committed_beam_id == active_beam_id
        and not snapshot_update_pending
        and (not shared_only_mode or same_beam_route_return)
    )


def _semantic_hash_value(value: Any) -> Any:
    """Normalize values to the equality semantics used by change detection."""

    if isinstance(value, Mapping):
        return {
            str(key): _semantic_hash_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_semantic_hash_value(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        if value == 0.0:
            return 0
        if value.is_integer():
            return int(value)
        return value
    return value


def _stable_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        _semantic_hash_value(dict(value)),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EngineeringInputTransaction:
    draft_hash: str
    committed_hash: str
    revision: int
    changed_keys: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class InputSnapshotState:
    """Immutable read model for the latest committed engineering inputs."""

    revision: int = 0
    engineering_hash: str | None = None
    snapshot: dict[str, Any] = field(default_factory=dict)
    changed_keys: tuple[str, ...] = ()
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot", copy.deepcopy(self.snapshot or {}))


class InputSnapshotStore:
    """Session-owned draft and committed engineering input records."""

    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    def capture_draft(
        self,
        state: Mapping[str, Any],
        *,
        changed_keys: tuple[str, ...] = (),
        source: str,
    ) -> dict[str, Any]:
        draft = copy.deepcopy(dict(state))
        self._state[DRAFT_STATE_KEY] = draft
        self._state[f"{DRAFT_STATE_KEY}:hash"] = _stable_hash(draft)
        self._state[f"{DRAFT_STATE_KEY}:changed_keys"] = tuple(
            sorted(str(key) for key in changed_keys)
        )
        self._state[f"{DRAFT_STATE_KEY}:source"] = str(source)
        return draft

    def commit_draft(self, *, source: str) -> EngineeringInputTransaction:
        draft = dict(self._state.get(DRAFT_STATE_KEY) or {})
        if not draft:
            raise ValueError("cannot commit an empty engineering-input draft")
        previous = copy.deepcopy(self._state.get(COMMITTED_STATE_KEY) or {})
        changed_keys = tuple(
            sorted(
                key
                for key in set(previous) | set(draft)
                if previous.get(key) != draft.get(key)
            )
        )
        previous_metadata = dict(self._state.get(TRANSACTION_META_KEY) or {})
        previous_revision = int(
            previous_metadata.get(
                "revision",
                0,
            )
            or 0
        )
        draft_hash = _stable_hash(draft)
        previous_hash = _stable_hash(previous) if previous else None
        semantically_unchanged = bool(previous) and not changed_keys
        if semantically_unchanged and previous_revision > 0:
            revision = previous_revision
            committed_hash = str(
                previous_metadata.get("committed_hash")
                or previous_hash
                or draft_hash
            )
        else:
            revision = previous_revision + 1
            committed_hash = draft_hash
        transaction = EngineeringInputTransaction(
            draft_hash=draft_hash,
            committed_hash=committed_hash,
            revision=revision,
            changed_keys=changed_keys,
            source=str(source),
        )
        self._state[COMMITTED_STATE_KEY] = copy.deepcopy(draft)
        self._state[TRANSACTION_META_KEY] = asdict(transaction)
        return transaction

    def commit_for_beam(
        self,
        beam_id: str,
        state: Mapping[str, Any],
        *,
        changed_keys: tuple[str, ...] = (),
        source: str,
    ) -> InputSnapshotState:
        """Atomically commit one beam-owned input snapshot and global revision.

        The global record remains as a compatibility view for existing consumers.
        The beam-owned record is the route/navigation authority.
        """

        resolved_beam_id = str(beam_id or "").strip()
        if not resolved_beam_id:
            raise ValueError("beam_id is required for an engineering-input commit")
        previous_snapshot = self.current().snapshot
        draft = self.capture_draft(
            state,
            changed_keys=tuple(changed_keys),
            source=source,
        )
        transaction = self.commit_draft(source=source)
        trace = list(self._state.get(TRANSACTION_TRACE_KEY) or [])
        trace.append(
            {
                "beam_id": resolved_beam_id,
                "revision": transaction.revision,
                "changed_keys": list(transaction.changed_keys),
                "change_values": {
                    key: {
                        "before": copy.deepcopy(previous_snapshot.get(key)),
                        "after": copy.deepcopy(draft.get(key)),
                    }
                    for key in transaction.changed_keys[:50]
                },
                "source": transaction.source,
                "draft_hash": transaction.draft_hash,
                "committed_hash": transaction.committed_hash,
            }
        )
        self._state[TRANSACTION_TRACE_KEY] = trace[-20:]
        snapshot_state = InputSnapshotState(
            revision=transaction.revision,
            engineering_hash=transaction.committed_hash,
            snapshot=draft,
            changed_keys=transaction.changed_keys,
            source=transaction.source,
        )
        by_beam = dict(self._state.get(BEAM_SNAPSHOT_STATE_KEY) or {})
        by_beam[resolved_beam_id] = asdict(snapshot_state)
        self._state[BEAM_SNAPSHOT_STATE_KEY] = by_beam

        # Preserve the established payload during the cutover so routes that
        # have not yet moved to the typed store cannot observe different data.
        legacy_by_beam = dict(
            self._state.get(LEGACY_BEAM_COMMITTED_STATE_KEY) or {}
        )
        legacy_by_beam[resolved_beam_id] = copy.deepcopy(draft)
        self._state[LEGACY_BEAM_COMMITTED_STATE_KEY] = legacy_by_beam
        self._state["_inputs_engineering_input_store_active_beam_id"] = (
            resolved_beam_id
        )
        self._state["_inputs_workspace_revision"] = transaction.revision
        return snapshot_state

    def current_for_beam(self, beam_id: str) -> InputSnapshotState:
        """Return the latest committed snapshot for ``beam_id``."""

        resolved_beam_id = str(beam_id or "").strip()
        if not resolved_beam_id:
            return InputSnapshotState()
        by_beam = self._state.get(BEAM_SNAPSHOT_STATE_KEY)
        value = by_beam.get(resolved_beam_id) if isinstance(by_beam, dict) else None
        if isinstance(value, InputSnapshotState):
            return value
        if isinstance(value, dict):
            return InputSnapshotState(
                revision=int(value.get("revision", 0) or 0),
                engineering_hash=(
                    str(value.get("engineering_hash"))
                    if value.get("engineering_hash")
                    else None
                ),
                snapshot=dict(value.get("snapshot") or {}),
                changed_keys=tuple(value.get("changed_keys") or ()),
                source=(str(value.get("source")) if value.get("source") else None),
            )

        # Read old sessions without creating a second revision. A later edit
        # promotes this payload through ``commit_for_beam``.
        legacy = self._state.get(LEGACY_BEAM_COMMITTED_STATE_KEY)
        legacy_snapshot = (
            dict(legacy.get(resolved_beam_id) or {})
            if isinstance(legacy, dict)
            else {}
        )
        if not legacy_snapshot:
            return InputSnapshotState()
        current = self.current()
        return InputSnapshotState(
            revision=current.revision,
            engineering_hash=_stable_hash(legacy_snapshot),
            snapshot=legacy_snapshot,
            changed_keys=(),
            source="legacy_beam_snapshot_migration",
        )

    def current(self) -> InputSnapshotState:
        committed = copy.deepcopy(self._state.get(COMMITTED_STATE_KEY) or {})
        metadata = dict(self._state.get(TRANSACTION_META_KEY) or {})
        return InputSnapshotState(
            revision=int(metadata.get("revision", 0) or 0),
            engineering_hash=(
                str(metadata.get("committed_hash"))
                if metadata.get("committed_hash")
                else None
            ),
            snapshot=committed,
            changed_keys=tuple(metadata.get("changed_keys") or ()),
            source=(str(metadata.get("source")) if metadata.get("source") else None),
        )

    def committed(self) -> dict[str, Any]:
        return self.current().snapshot


# Transitional import compatibility only. Both names resolve to the exact same
# class and therefore the exact same storage owner.
EngineeringInputStore = InputSnapshotStore


__all__ = [
    "BEAM_SNAPSHOT_STATE_KEY",
    "COMMITTED_STATE_KEY",
    "DRAFT_STATE_KEY",
    "EngineeringInputStore",
    "EngineeringInputTransaction",
    "InputSnapshotState",
    "InputSnapshotStore",
    "LEGACY_BEAM_COMMITTED_STATE_KEY",
    "TRANSACTION_META_KEY",
    "TRANSACTION_TRACE_KEY",
    "should_reuse_committed_engineering_baseline",
]
