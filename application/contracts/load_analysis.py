"""Immutable, analysis-only state owned by the Load Analysis branch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from application.contracts.design_branch import canonical_hash, freeze_payload, thaw_payload


@dataclass(frozen=True)
class LoadAnalysisSnapshot:
    beam_id: str
    revision: int
    content_hash: str = ""
    analysis: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        beam_id = str(self.beam_id or "").strip()
        if not beam_id:
            raise ValueError("beam_id is required")
        revision = int(self.revision)
        if revision < 0:
            raise ValueError("revision cannot be negative")
        frozen = freeze_payload(self.analysis or {})
        expected = canonical_hash(frozen)
        supplied = str(self.content_hash or "").strip()
        if supplied and supplied != expected:
            raise ValueError("content_hash does not match Load Analysis payload")
        object.__setattr__(self, "beam_id", beam_id)
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "content_hash", supplied or expected)
        object.__setattr__(self, "analysis", frozen)

    def to_mutable_dict(self) -> dict[str, Any]:
        return thaw_payload(self.analysis)


__all__ = ["LoadAnalysisSnapshot"]
