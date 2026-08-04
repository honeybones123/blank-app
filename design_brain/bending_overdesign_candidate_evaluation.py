"""Data boundary for bending-overdesign optimisation candidate evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any


REINFORCEMENT_UPDATE_KEYS = frozenset(
    {
        "bot1_count",
        "db_bot_1",
        "bot2_count",
        "db_bot_2",
        "bot_row_count",
        "bot_row_1_bars",
        "bot_row_1_dia",
        "bot_row_2_bars",
        "bot_row_2_dia",
    }
)
GEOMETRY_UPDATE_KEYS = frozenset(
    {
        "b",
        "bw",
        "D",
        "beam_width",
        "beam_depth",
        "beam_width_mm",
        "beam_depth_mm",
    }
)
ALLOWED_BENDING_OVERDESIGN_UPDATE_KEYS = REINFORCEMENT_UPDATE_KEYS | GEOMETRY_UPDATE_KEYS


def stable_bending_overdesign_candidate_hash(value: Any) -> str:
    """Return a deterministic hash for bending-overdesign boundary payloads."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def normalise_bending_overdesign_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    """Return a plain dict copy for boundary fields."""

    return dict(value or {})


def bending_overdesign_update_keys(value: dict[str, Any] | None) -> tuple[str, ...]:
    """Return sorted update keys for a candidate update payload."""

    return tuple(sorted(str(key) for key in normalise_bending_overdesign_mapping(value)))


def is_bending_overdesign_update(value: dict[str, Any] | None) -> bool:
    """Return whether an update is restricted to bending-overdesign fields."""

    keys = set(bending_overdesign_update_keys(value))
    return bool(keys) and keys <= set(ALLOWED_BENDING_OVERDESIGN_UPDATE_KEYS)


def is_reinforcement_update(value: dict[str, Any] | None) -> bool:
    """Return whether an update only changes bending reinforcement fields."""

    keys = set(bending_overdesign_update_keys(value))
    return bool(keys) and keys <= set(REINFORCEMENT_UPDATE_KEYS)


def is_geometry_update(value: dict[str, Any] | None) -> bool:
    """Return whether an update only changes controlled geometry fields."""

    keys = set(bending_overdesign_update_keys(value))
    return bool(keys) and keys <= set(GEOMETRY_UPDATE_KEYS)


def build_bending_overdesign_candidate_state_hash(
    base_state: dict[str, Any] | None,
    candidate_update: dict[str, Any] | None,
) -> str:
    """Hash the future non-mutating merge of base state and candidate update."""

    state = normalise_bending_overdesign_mapping(base_state)
    state.update(normalise_bending_overdesign_mapping(candidate_update))
    return stable_bending_overdesign_candidate_hash(state)


@dataclass(frozen=True)
class BendingOverdesignCandidateInput:
    """Base bending-overdesign state for optimisation candidate evaluation."""

    base_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def input_hash(self) -> str:
        return stable_bending_overdesign_candidate_hash(self.base_state)


@dataclass(frozen=True)
class BendingOverdesignCandidateUpdate:
    """Proposed non-committed bending-overdesign optimisation update."""

    updates: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def update_hash(self) -> str:
        return stable_bending_overdesign_candidate_hash(self.updates)

    @property
    def update_keys(self) -> tuple[str, ...]:
        return bending_overdesign_update_keys(self.updates)

    @property
    def bending_overdesign_update(self) -> bool:
        return is_bending_overdesign_update(self.updates)

    @property
    def reinforcement_update(self) -> bool:
        return is_reinforcement_update(self.updates)

    @property
    def geometry_update(self) -> bool:
        return is_geometry_update(self.updates)


@dataclass(frozen=True)
class BendingOverdesignCandidateEvaluation:
    """Normalized engineering result for a bending-overdesign optimisation candidate."""

    input_hash: str
    update_hash: str
    candidate_state_hash: str
    bending_utilisation: float | None = None
    previous_bending_utilisation: float | None = None
    target_band_status: dict[str, Any] = field(default_factory=dict)
    utilisation_moves_toward_target: bool | None = None
    bending_remains_compliant: bool | None = None
    constructability_status: dict[str, Any] = field(default_factory=dict)
    code_compliance_status: dict[str, Any] = field(default_factory=dict)
    minimum_reinforcement_status: dict[str, Any] = field(default_factory=dict)
    geometry_compliance_status: dict[str, Any] = field(default_factory=dict)
    beam_proportion_status: dict[str, Any] = field(default_factory=dict)
    reinforcement_quantity: dict[str, Any] = field(default_factory=dict)
    beam_volume: dict[str, Any] = field(default_factory=dict)
    cost_proxy: dict[str, Any] = field(default_factory=dict)
    capacity_summary: dict[str, Any] = field(default_factory=dict)
    failure_flags: dict[str, Any] = field(default_factory=dict)
    engineering_status: dict[str, Any] = field(default_factory=dict)
    evaluation_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_evaluation_hash(self) -> "BendingOverdesignCandidateEvaluation":
        """Return a copy with ``evaluation_hash`` populated from stable fields."""

        payload = self.to_dict()
        payload.pop("evaluation_hash", None)
        return BendingOverdesignCandidateEvaluation(
            **{
                **payload,
                "evaluation_hash": stable_bending_overdesign_candidate_hash(payload),
            }
        )


__all__ = [
    "ALLOWED_BENDING_OVERDESIGN_UPDATE_KEYS",
    "BendingOverdesignCandidateEvaluation",
    "BendingOverdesignCandidateInput",
    "BendingOverdesignCandidateUpdate",
    "GEOMETRY_UPDATE_KEYS",
    "REINFORCEMENT_UPDATE_KEYS",
    "bending_overdesign_update_keys",
    "build_bending_overdesign_candidate_state_hash",
    "is_bending_overdesign_update",
    "is_geometry_update",
    "is_reinforcement_update",
    "normalise_bending_overdesign_mapping",
    "stable_bending_overdesign_candidate_hash",
]
