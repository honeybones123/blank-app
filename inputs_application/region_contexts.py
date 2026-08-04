"""Immutable identities and contexts for independent Inputs regions."""

from __future__ import annotations

from dataclasses import dataclass


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


__all__ = ["InputsDesignBrainRegionContext", "RevisionIdentity"]
