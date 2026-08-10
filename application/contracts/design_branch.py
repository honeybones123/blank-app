"""Page-neutral contracts for beam-owned design branches.

The main-design selection is deliberately separate from engineering identity.
Changing which branch a page displays must not alter either branch payload or
invalidate its calculation/Design Brain cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import copy
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping


class DesignBranch(str, Enum):
    BEAM_INPUTS = "beam_inputs"
    LOAD_ANALYSIS = "load_analysis"


def canonical_hash(value: Any) -> str:
    """Return a deterministic hash for JSON-shaped contract values."""

    payload = json.dumps(
        thaw_payload(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def freeze_payload(value: Any) -> Any:
    """Recursively freeze a JSON-shaped value."""

    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): freeze_payload(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_payload(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze_payload(item) for item in value)
    return copy.deepcopy(value)


def thaw_payload(value: Any) -> Any:
    """Return a defensive mutable serialization of a frozen value."""

    if isinstance(value, Mapping):
        return {str(key): thaw_payload(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [thaw_payload(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((thaw_payload(item) for item in value), key=repr)
    return copy.deepcopy(value)


@dataclass(frozen=True)
class BeamDesignSnapshot:
    beam_id: str
    design_branch: DesignBranch
    revision: int
    content_hash: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    source: str = ""
    source_revision: int | None = None
    source_hash: str | None = None

    def __post_init__(self) -> None:
        beam_id = str(self.beam_id or "").strip()
        if not beam_id:
            raise ValueError("beam_id is required")
        revision = int(self.revision)
        if revision < 0:
            raise ValueError("revision cannot be negative")
        branch = DesignBranch(self.design_branch)
        frozen = freeze_payload(self.payload or {})
        expected_hash = canonical_hash(frozen)
        supplied_hash = str(self.content_hash or "").strip()
        if supplied_hash and supplied_hash != expected_hash:
            raise ValueError("content_hash does not match the frozen branch payload")
        object.__setattr__(self, "beam_id", beam_id)
        object.__setattr__(self, "design_branch", branch)
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "content_hash", supplied_hash or expected_hash)
        object.__setattr__(self, "payload", frozen)

    def to_payload(self) -> dict[str, Any]:
        return thaw_payload(self.payload)

    def to_mutable_dict(self) -> dict[str, Any]:
        """Explicit defensive-copy alias used at mutable UI boundaries."""

        return self.to_payload()

    def to_record(self) -> dict[str, Any]:
        return {
            "beam_id": self.beam_id,
            "design_branch": self.design_branch.value,
            "revision": self.revision,
            "content_hash": self.content_hash,
            "payload": self.to_payload(),
            "source": self.source,
            "source_revision": self.source_revision,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True)
class MainDesignSelection:
    beam_id: str
    selected_branch: DesignBranch
    revision: int
    content_hash: str = ""

    def __post_init__(self) -> None:
        beam_id = str(self.beam_id or "").strip()
        if not beam_id:
            raise ValueError("beam_id is required")
        branch = DesignBranch(self.selected_branch)
        revision = int(self.revision)
        if revision < 0:
            raise ValueError("revision cannot be negative")
        expected_hash = canonical_hash(
            {
                "beam_id": beam_id,
                "selected_branch": branch.value,
                "revision": revision,
            }
        )
        supplied_hash = str(self.content_hash or "").strip()
        if supplied_hash and supplied_hash != expected_hash:
            raise ValueError("selection content_hash is invalid")
        object.__setattr__(self, "beam_id", beam_id)
        object.__setattr__(self, "selected_branch", branch)
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "content_hash", supplied_hash or expected_hash)

    def to_record(self) -> dict[str, Any]:
        return {
            "beam_id": self.beam_id,
            "selected_branch": self.selected_branch.value,
            "revision": self.revision,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class BranchWorkspaceIdentity:
    beam_id: str
    design_branch: DesignBranch
    branch_revision: int
    branch_hash: str
    load_analysis_revision: int | None
    load_analysis_hash: str | None
    action_source: str
    action_selection_policy: str
    design_actions_hash: str
    calculation_version: str


@dataclass(frozen=True)
class InputsDisplayIdentity:
    beam_id: str
    selected_branch: DesignBranch
    selection_revision: int
    selection_hash: str
    workspace_identity: BranchWorkspaceIdentity


__all__ = [
    "BeamDesignSnapshot",
    "BranchWorkspaceIdentity",
    "DesignBranch",
    "InputsDisplayIdentity",
    "MainDesignSelection",
    "canonical_hash",
    "freeze_payload",
    "thaw_payload",
]
