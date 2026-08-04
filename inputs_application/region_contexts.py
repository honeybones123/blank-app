"""Immutable identities and contexts for independent Inputs regions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from inputs_application.summary_contracts import InputsSummaryCalculationSource


@dataclass(frozen=True)
class RevisionIdentity:
    """One authoritative input revision and its engineering result identity."""

    input_revision: int
    engineering_hash: str

    def __post_init__(self) -> None:
        if int(self.input_revision) < 0:
            raise ValueError("input_revision cannot be negative")
        if not str(self.engineering_hash or "").strip():
            raise ValueError("engineering_hash is required")

    def matches(self, *, input_revision: int, engineering_hash: str | None) -> bool:
        return bool(
            int(input_revision) == int(self.input_revision)
            and str(engineering_hash or "") == self.engineering_hash
        )


@dataclass(frozen=True)
class InputsDesignBrainRegionContext:
    """Stable inputs consumed by one Design Brain fragment render."""

    identity: RevisionIdentity
    beam_id: str
    inputs_detailed_mode: bool


@dataclass(frozen=True)
class InputsSummaryRegionContext:
    """One revision-matched engineering result consumed by Summary."""

    identity: RevisionIdentity
    resolved_inputs: Mapping[str, Any]
    packs: Mapping[str, Mapping[str, Any]]
    actions_used: Mapping[str, Any]

    def __post_init__(self) -> None:
        missing = {
            family
            for family in ("bending", "shear", "crack", "deflection")
            if not isinstance(self.packs.get(family), Mapping)
        }
        if missing:
            raise ValueError(
                "summary context is missing authoritative packs: "
                + ", ".join(sorted(missing))
            )


InputsSummaryRegionStatus = Literal[
    "awaiting_inputs",
    "updating",
    "ready",
    "failed",
]


@dataclass(frozen=True)
class InputsSummaryRegionState:
    """Explicit lifecycle state consumed by the independent Summary region."""

    input_revision: int
    status: InputsSummaryRegionStatus
    context: InputsSummaryRegionContext | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if int(self.input_revision) < 0:
            raise ValueError("input_revision cannot be negative")
        if self.status not in {
            "awaiting_inputs",
            "updating",
            "ready",
            "failed",
        }:
            raise ValueError(f"unsupported Summary region status: {self.status}")
        if self.status == "ready" and self.context is None:
            raise ValueError("ready Summary state requires a region context")
        if self.status != "ready" and self.context is not None:
            raise ValueError("only ready Summary state may carry a region context")
        if (
            self.context is not None
            and self.context.identity.input_revision != int(self.input_revision)
        ):
            raise ValueError("Summary state and context revisions must match")
        if self.status == "failed" and not str(self.error or "").strip():
            raise ValueError("failed Summary state requires an error")


@dataclass(frozen=True)
class InputsCalculationRegionContext:
    """Stable Summary handoff consumed by one Calculation region render."""

    identity: RevisionIdentity
    summary_source: InputsSummaryCalculationSource

    def __post_init__(self) -> None:
        if not isinstance(self.summary_source, InputsSummaryCalculationSource):
            raise TypeError(
                "summary_source must be an InputsSummaryCalculationSource"
            )


@dataclass(frozen=True)
class InputsControlsRegionContext:
    """Immutable active-beam inputs consumed by the Controls region."""

    beam_labels: tuple[tuple[str, str], ...]
    beam_order: tuple[str, ...]
    active_beam_id: str

    def __post_init__(self) -> None:
        if len(set(self.beam_order)) != len(self.beam_order):
            raise ValueError("beam_order cannot contain duplicates")
        if self.beam_order and self.active_beam_id not in self.beam_order:
            raise ValueError("active_beam_id must belong to beam_order")

    def labels_dict(self) -> dict[str, str]:
        return dict(self.beam_labels)


__all__ = [
    "InputsCalculationRegionContext",
    "InputsControlsRegionContext",
    "InputsDesignBrainRegionContext",
    "InputsSummaryRegionContext",
    "InputsSummaryRegionState",
    "InputsSummaryRegionStatus",
    "RevisionIdentity",
]
