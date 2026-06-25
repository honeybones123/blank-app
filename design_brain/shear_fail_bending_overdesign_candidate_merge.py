"""Data boundary for shear-fail plus bending-overdesign mixed candidate merging."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any


ALLOWED_SHEAR_FAIL_BENDING_OVERDESIGN_SOURCE_FAMILIES = frozenset(
    {"SHEAR_FAIL_GOVERNS", "BENDING_OVERDESIGN_GOVERNS", "APPROVED_MIXED_MERGE_RULE"}
)
GEOMETRY_UPDATE_KEYS = frozenset({"D", "beam_depth", "beam_depth_mm", "b", "bw", "beam_width", "beam_width_mm"})
BENDING_REINFORCEMENT_UPDATE_KEYS = frozenset(
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
SHEAR_REINFORCEMENT_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})


def stable_shear_fail_bending_overdesign_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def normalise_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def update_keys(value: dict[str, Any] | None) -> tuple[str, ...]:
    return tuple(sorted(str(key) for key in normalise_mapping(value)))


def source_family_allowed(value: str | None) -> bool:
    return str(value or "") in ALLOWED_SHEAR_FAIL_BENDING_OVERDESIGN_SOURCE_FAMILIES


def merge_updates(*updates: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for update in updates:
        merged.update(normalise_mapping(update))
    return merged


def interaction_flags(updates: dict[str, Any] | None) -> dict[str, bool]:
    keys = set(update_keys(updates))
    return {
        "geometry_changed": bool(keys & set(GEOMETRY_UPDATE_KEYS)),
        "bending_reinforcement_changed": bool(keys & set(BENDING_REINFORCEMENT_UPDATE_KEYS)),
        "shear_reinforcement_changed": bool(keys & set(SHEAR_REINFORCEMENT_UPDATE_KEYS)),
    }


def mixed_candidate_state_hash(
    base_state: dict[str, Any] | None,
    combined_updates: dict[str, Any] | None,
) -> str:
    state = normalise_mapping(base_state)
    state.update(normalise_mapping(combined_updates))
    return stable_shear_fail_bending_overdesign_hash(state)


@dataclass(frozen=True)
class ShearFailBendingOverdesignInputs:
    selected_family_id: str
    base_state: dict[str, Any] = field(default_factory=dict)
    geometry: dict[str, Any] = field(default_factory=dict)
    reinforcement: dict[str, Any] = field(default_factory=dict)
    material_properties: dict[str, Any] = field(default_factory=dict)
    actions: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    shear_fail_candidates: tuple[dict[str, Any], ...] = ()
    bending_overdesign_candidates: tuple[dict[str, Any], ...] = ()
    approved_mixed_merge_candidates: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def input_hash(self) -> str:
        return stable_shear_fail_bending_overdesign_hash(self.to_dict())

    @property
    def selection_boundary_satisfied(self) -> bool:
        return self.selected_family_id == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"


@dataclass(frozen=True)
class MixedSourceCandidate:
    source_family_id: str
    candidate_id: str
    updates: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def source_allowed(self) -> bool:
        return source_family_allowed(self.source_family_id)

    @property
    def update_hash(self) -> str:
        return stable_shear_fail_bending_overdesign_hash(self.updates)

    @property
    def interaction_flags(self) -> dict[str, bool]:
        return interaction_flags(self.updates)


@dataclass(frozen=True)
class MixedMergedCandidate:
    candidate_id: str
    source_candidates: tuple[MixedSourceCandidate, ...]
    updates: dict[str, Any] = field(default_factory=dict)
    merge_rule_id: str = "PAIRWISE_SHEAR_FAIL_BENDING_OVERDESIGN_MERGE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def update_hash(self) -> str:
        return stable_shear_fail_bending_overdesign_hash(self.updates)

    @property
    def source_families(self) -> tuple[str, ...]:
        return tuple(candidate.source_family_id for candidate in self.source_candidates)

    @property
    def sources_allowed(self) -> bool:
        return bool(self.source_candidates) and all(candidate.source_allowed for candidate in self.source_candidates)

    @property
    def has_mandatory_shear_source(self) -> bool:
        return "SHEAR_FAIL_GOVERNS" in self.source_families

    @property
    def has_opportunistic_bending_source(self) -> bool:
        return "BENDING_OVERDESIGN_GOVERNS" in self.source_families

    @property
    def interaction_flags(self) -> dict[str, bool]:
        return interaction_flags(self.updates)


@dataclass(frozen=True)
class MixedCandidateEvaluation:
    input_hash: str
    update_hash: str
    candidate_state_hash: str
    source_family_ids: tuple[str, ...] = ()
    source_candidates: tuple[str, ...] = ()
    bending_utilisation_before: float | None = None
    shear_utilisation_before: float | None = None
    bending_utilisation_after: float | None = None
    shear_utilisation_after: float | None = None
    shear_repaired: bool | None = None
    bending_compliant: bool | None = None
    bending_inside_target_band: bool | None = None
    shear_inside_target_band: bool | None = None
    bending_moves_toward_target: bool | None = None
    creates_bending_underdesign: bool | None = None
    code_compliance_status: dict[str, Any] = field(default_factory=dict)
    constructability_status: dict[str, Any] = field(default_factory=dict)
    geometry_interaction_status: dict[str, Any] = field(default_factory=dict)
    reinforcement_interaction_status: dict[str, Any] = field(default_factory=dict)
    reinforcement_quantity: dict[str, Any] = field(default_factory=dict)
    beam_volume: dict[str, Any] = field(default_factory=dict)
    cost_proxy: dict[str, Any] = field(default_factory=dict)
    rejection_reasons: tuple[str, ...] = ()
    engineering_status: dict[str, Any] = field(default_factory=dict)
    evaluation_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_evaluation_hash(self) -> "MixedCandidateEvaluation":
        payload = self.to_dict()
        payload.pop("evaluation_hash", None)
        return MixedCandidateEvaluation(
            **{
                **payload,
                "evaluation_hash": stable_shear_fail_bending_overdesign_hash(payload),
            }
        )


__all__ = [
    "ALLOWED_SHEAR_FAIL_BENDING_OVERDESIGN_SOURCE_FAMILIES",
    "BENDING_REINFORCEMENT_UPDATE_KEYS",
    "GEOMETRY_UPDATE_KEYS",
    "MixedCandidateEvaluation",
    "MixedMergedCandidate",
    "MixedSourceCandidate",
    "SHEAR_REINFORCEMENT_UPDATE_KEYS",
    "ShearFailBendingOverdesignInputs",
    "interaction_flags",
    "merge_updates",
    "mixed_candidate_state_hash",
    "normalise_mapping",
    "source_family_allowed",
    "stable_shear_fail_bending_overdesign_hash",
    "update_keys",
]
