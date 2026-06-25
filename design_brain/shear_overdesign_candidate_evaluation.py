"""Data boundary for shear-overdesign optimisation candidate evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any


ALLOWED_SHEAR_OVERDESIGN_UPDATE_KEYS = frozenset({"s_lig", "lig_d", "lig_legs"})
PROHIBITED_GEOMETRY_UPDATE_KEYS = frozenset(
    {"b", "bw", "D", "beam_width", "beam_depth", "beam_width_mm", "beam_depth_mm"}
)


def stable_shear_overdesign_candidate_hash(value: Any) -> str:
    """Return a deterministic hash for shear-overdesign boundary payloads."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def normalise_shear_overdesign_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    """Return a plain dict copy for boundary fields."""

    return dict(value or {})


def shear_overdesign_update_keys(value: dict[str, Any] | None) -> tuple[str, ...]:
    """Return sorted update keys for a candidate update payload."""

    return tuple(sorted(str(key) for key in normalise_shear_overdesign_mapping(value)))


def is_shear_detailing_only_update(value: dict[str, Any] | None) -> bool:
    """Return whether an update is restricted to shear detailing fields."""

    keys = set(shear_overdesign_update_keys(value))
    return bool(keys) and keys <= set(ALLOWED_SHEAR_OVERDESIGN_UPDATE_KEYS)


def contains_geometry_reduction_update(value: dict[str, Any] | None) -> bool:
    """Return whether an update tries to change protected geometry fields."""

    keys = set(shear_overdesign_update_keys(value))
    return bool(keys & set(PROHIBITED_GEOMETRY_UPDATE_KEYS))


@dataclass(frozen=True)
class ShearOverdesignCandidateInput:
    """Base shear-overdesign state for optimisation candidate evaluation."""

    base_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def input_hash(self) -> str:
        return stable_shear_overdesign_candidate_hash(self.base_state)


@dataclass(frozen=True)
class ShearOverdesignCandidateUpdate:
    """Proposed non-committed shear-overdesign optimisation update."""

    updates: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def update_hash(self) -> str:
        return stable_shear_overdesign_candidate_hash(self.updates)

    @property
    def update_keys(self) -> tuple[str, ...]:
        return shear_overdesign_update_keys(self.updates)

    @property
    def shear_detailing_only(self) -> bool:
        return is_shear_detailing_only_update(self.updates)

    @property
    def geometry_reduction_attempted(self) -> bool:
        return contains_geometry_reduction_update(self.updates)


@dataclass(frozen=True)
class ShearOverdesignCandidateEvaluation:
    """Normalized engineering result for a shear-overdesign optimisation candidate."""

    input_hash: str
    update_hash: str
    candidate_state_hash: str
    shear_utilisation: float | None = None
    previous_shear_utilisation: float | None = None
    target_band_status: dict[str, Any] = field(default_factory=dict)
    utilisation_moves_toward_target: bool | None = None
    shear_remains_compliant: bool | None = None
    constructability_status: dict[str, Any] = field(default_factory=dict)
    mandatory_detailing_status: dict[str, Any] = field(default_factory=dict)
    shear_detailing_update_status: dict[str, Any] = field(default_factory=dict)
    geometry_restriction_status: dict[str, Any] = field(default_factory=dict)
    zero_shear_status: dict[str, Any] = field(default_factory=dict)
    ligature_removal_status: dict[str, Any] = field(default_factory=dict)
    reinforcement_quantity: dict[str, Any] = field(default_factory=dict)
    cost_proxy: dict[str, Any] = field(default_factory=dict)
    capacity_summary: dict[str, Any] = field(default_factory=dict)
    failure_flags: dict[str, Any] = field(default_factory=dict)
    engineering_status: dict[str, Any] = field(default_factory=dict)
    evaluation_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_evaluation_hash(self) -> "ShearOverdesignCandidateEvaluation":
        """Return a copy with ``evaluation_hash`` populated from stable fields."""

        payload = self.to_dict()
        payload.pop("evaluation_hash", None)
        return ShearOverdesignCandidateEvaluation(
            **{
                **payload,
                "evaluation_hash": stable_shear_overdesign_candidate_hash(payload),
            }
        )


def build_shear_overdesign_candidate_state_hash(
    base_state: dict[str, Any] | None,
    candidate_update: dict[str, Any] | None,
) -> str:
    """Hash the future non-mutating merge of base state and candidate update."""

    state = normalise_shear_overdesign_mapping(base_state)
    state.update(normalise_shear_overdesign_mapping(candidate_update))
    return stable_shear_overdesign_candidate_hash(state)


__all__ = [
    "ALLOWED_SHEAR_OVERDESIGN_UPDATE_KEYS",
    "PROHIBITED_GEOMETRY_UPDATE_KEYS",
    "ShearOverdesignCandidateEvaluation",
    "ShearOverdesignCandidateInput",
    "ShearOverdesignCandidateUpdate",
    "build_shear_overdesign_candidate_state_hash",
    "contains_geometry_reduction_update",
    "is_shear_detailing_only_update",
    "normalise_shear_overdesign_mapping",
    "shear_overdesign_update_keys",
    "stable_shear_overdesign_candidate_hash",
]
