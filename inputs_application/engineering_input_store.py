"""Explicit draft-to-committed Inputs engineering state boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import copy
import hashlib
import json
import math
from typing import Any, Mapping, MutableMapping

from application.contracts.design_branch import DesignBranch, freeze_payload, thaw_payload
from inputs_application.design_branch_store import (
    LOAD_ANALYSIS_BRANCH_EXCLUDED_FIELDS,
    BeamDesignBranchStore,
)


DRAFT_STATE_KEY = "_inputs_draft_engineering_state_v1"
TRANSACTION_META_KEY = "_inputs_engineering_input_transaction_v1"
TRANSACTION_TRACE_KEY = "_inputs_engineering_input_transaction_trace_v1"


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
    snapshot: Mapping[str, Any] = field(default_factory=dict)
    changed_keys: tuple[str, ...] = ()
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot", freeze_payload(self.snapshot or {}))

    def to_mutable_dict(self) -> dict[str, Any]:
        return thaw_payload(self.snapshot)


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
        beam_id = str(self._state.get("active_beam_id") or "").strip()
        if not beam_id:
            raise ValueError("active_beam_id is required to commit engineering inputs")
        changed_keys = tuple(
            self._state.get(f"{DRAFT_STATE_KEY}:changed_keys") or ()
        )
        snapshot = self.commit_for_beam(
            beam_id,
            draft,
            changed_keys=changed_keys,
            source=source,
        )
        return EngineeringInputTransaction(
            draft_hash=_stable_hash(draft),
            committed_hash=str(snapshot.engineering_hash or ""),
            revision=snapshot.revision,
            changed_keys=snapshot.changed_keys,
            source=str(snapshot.source or source),
        )

    def commit_for_beam(
        self,
        beam_id: str,
        state: Mapping[str, Any],
        *,
        changed_keys: tuple[str, ...] = (),
        source: str,
        branch: DesignBranch | None = None,
        expected_branch_revision: int | None = None,
    ) -> InputSnapshotState:
        """Atomically commit one branch-owned input snapshot.

        ``BeamDesignBranchStore`` is the sole engineering owner.  The draft,
        transaction metadata and trace below are audit/display projections;
        no second per-beam payload is written.
        """

        resolved_beam_id = str(beam_id or "").strip()
        if not resolved_beam_id:
            raise ValueError("beam_id is required for an engineering-input commit")
        branch_store = BeamDesignBranchStore(self._state)
        resolved_branch = (
            DesignBranch(branch)
            if branch is not None
            else branch_store.active_context(
                resolved_beam_id,
                page_slug=str(
                    self._state.get("_active_page_slug")
                    or self._state.get("page_slug")
                    or "inputs"
                ),
            )
        )
        current_branch = branch_store.get(resolved_beam_id, resolved_branch)
        branch_revision = int(current_branch.revision if current_branch else 0)
        if expected_branch_revision is not None and int(expected_branch_revision) != branch_revision:
            raise ValueError(
                f"expected branch revision {expected_branch_revision}, current is {branch_revision}"
            )
        previous_beam_snapshot = self.current_for_beam(
            resolved_beam_id,
            branch=resolved_branch,
        )
        previous_beam_state = (
            previous_beam_snapshot.to_mutable_dict()
            if previous_beam_snapshot.revision > 0
            else {}
        )
        branch_state = dict(state)
        if resolved_branch is DesignBranch.LOAD_ANALYSIS:
            branch_state = {
                key: value
                for key, value in branch_state.items()
                if key not in LOAD_ANALYSIS_BRANCH_EXCLUDED_FIELDS
            }
        draft = self.capture_draft(
            branch_state,
            changed_keys=tuple(changed_keys),
            source=source,
        )
        committed_branch = branch_store.replace(
            resolved_beam_id,
            resolved_branch,
            expected_branch_revision=branch_revision,
            payload=draft,
            source=source,
        )
        effective_changed_keys = tuple(
            sorted(
                key
                for key in set(previous_beam_state) | set(draft)
                if previous_beam_state.get(key) != draft.get(key)
            )
        )
        if not previous_beam_state and changed_keys:
            effective_changed_keys = tuple(
                sorted(str(key) for key in changed_keys)
            )
        transaction = EngineeringInputTransaction(
            draft_hash=_stable_hash(draft),
            committed_hash=committed_branch.content_hash,
            revision=committed_branch.revision,
            changed_keys=effective_changed_keys,
            source=str(source),
        )
        self._state[TRANSACTION_META_KEY] = asdict(transaction)
        trace = list(self._state.get(TRANSACTION_TRACE_KEY) or [])
        trace.append(
            {
                "beam_id": resolved_beam_id,
                "design_branch": resolved_branch.value,
                "revision": transaction.revision,
                "changed_keys": list(transaction.changed_keys),
                "change_values": {
                    key: {
                        "before": copy.deepcopy(previous_beam_state.get(key)),
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
        self._state["_inputs_engineering_input_store_active_beam_id"] = (
            resolved_beam_id
        )
        branch_store.set_active_context(resolved_branch)
        self._state["_inputs_workspace_revision"] = transaction.revision
        # Navigation preservation belongs to the committed input transaction,
        # not to the slower engineering or Design Brain publication.  Arm the
        # handoff synchronously so leaving Inputs immediately after an edit
        # cannot allow stale widget defaults to overwrite this beam snapshot.
        self._state["_inputs_route_authority_armed"] = True
        return snapshot_state

    def commit_active_beam(
        self,
        state: Mapping[str, Any],
        *,
        changed_keys: tuple[str, ...] = (),
        source: str,
    ) -> InputSnapshotState:
        """Commit the currently routed beam through the one input boundary."""

        beam_id = str(self._state.get("active_beam_id") or "").strip()
        if not beam_id:
            raise ValueError("active_beam_id is required for an input commit")
        return self.commit_for_beam(
            beam_id,
            state,
            changed_keys=changed_keys,
            source=source,
        )

    def current_for_beam(
        self,
        beam_id: str,
        *,
        branch: DesignBranch | None = None,
    ) -> InputSnapshotState:
        """Return the latest committed snapshot for ``beam_id``."""

        resolved_beam_id = str(beam_id or "").strip()
        if not resolved_beam_id:
            return InputSnapshotState()
        branch_store = BeamDesignBranchStore(self._state)
        resolved_branch = (
            DesignBranch(branch)
            if branch is not None
            else branch_store.active_context(
                resolved_beam_id,
                page_slug=str(
                    self._state.get("_active_page_slug")
                    or self._state.get("page_slug")
                    or "inputs"
                ),
            )
        )
        branch_snapshot = branch_store.get(resolved_beam_id, resolved_branch)
        if branch_snapshot is not None:
            return InputSnapshotState(
                revision=branch_snapshot.revision,
                engineering_hash=branch_snapshot.content_hash,
                snapshot=branch_snapshot.to_payload(),
                changed_keys=(),
                source=branch_snapshot.source,
            )
        return InputSnapshotState()

    def current(self) -> InputSnapshotState:
        beam_id = str(self._state.get("active_beam_id") or "").strip()
        if beam_id:
            return self.current_for_beam(beam_id)
        return InputSnapshotState()

    def committed(self) -> dict[str, Any]:
        return self.current().to_mutable_dict()


# Transitional import compatibility only. Both names resolve to the exact same
# class and therefore the exact same storage owner.
EngineeringInputStore = InputSnapshotStore


__all__ = [
    "DRAFT_STATE_KEY",
    "EngineeringInputStore",
    "EngineeringInputTransaction",
    "InputSnapshotState",
    "InputSnapshotStore",
    "TRANSACTION_META_KEY",
    "TRANSACTION_TRACE_KEY",
    "should_reuse_committed_engineering_baseline",
]
