"""Family-owned Design Brain strategy interfaces.

These interfaces describe the ownership shape used by live family dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class FamilyStrategyContext:
    """Read-only inputs a family strategy may inspect during routing."""

    governing_state: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    primary: Mapping[str, Any] = field(default_factory=dict)
    summary: Mapping[str, Any] = field(default_factory=dict)
    evidence: Mapping[str, Any] = field(default_factory=dict)
    debug: Mapping[str, Any] = field(default_factory=dict)
    classifier: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FamilyStrategyMetadata:
    """Static ownership metadata for a governing family."""

    governing_state: str
    owner: str
    candidate_strategy: str
    ranking_strategy: str
    evidence_strategy: str
    publication_rule: str
    cta_rule: str
    affected_by_shared_helpers: tuple[str, ...] = ()
    regression_id: str | None = None
    migrated: bool = False
    locked: bool = False


@runtime_checkable
class GoverningFamilyStrategy(Protocol):
    """Protocol every governing-family strategy must satisfy."""

    metadata: FamilyStrategyMetadata

    def classify(self, context: FamilyStrategyContext) -> dict[str, Any]:
        """Return family-local classification diagnostics."""

    def generate_candidates(self, context: FamilyStrategyContext) -> dict[str, Any]:
        """Return family-owned candidate strategy output."""

    def rank_candidates(self, context: FamilyStrategyContext, candidates: Any = None) -> dict[str, Any]:
        """Return family-owned ranking strategy output."""

    def build_evidence(self, context: FamilyStrategyContext, decision: Any = None) -> dict[str, Any]:
        """Return family-owned evidence strategy output."""

    def publish(self, context: FamilyStrategyContext, decision: Any = None) -> dict[str, Any]:
        """Return family-owned publication output."""

    def get_cta_rule(self, context: FamilyStrategyContext) -> dict[str, Any]:
        """Return the explicit family CTA rule."""


class DiagnosticFamilyStrategy:
    """Compatibility diagnostics for strategies with contracted entry points.

    Live dispatch calls each family's explicit contracted ladder method (or a
    typed terminal outcome), not these generic methods. They remain useful to
    older audits and report the strategy's actual migration metadata.
    """

    metadata: FamilyStrategyMetadata

    def classify(self, context: FamilyStrategyContext) -> dict[str, Any]:
        return self._not_migrated(context, "classify")

    def generate_candidates(self, context: FamilyStrategyContext) -> dict[str, Any]:
        return self._not_migrated(context, "generate_candidates")

    def rank_candidates(self, context: FamilyStrategyContext, candidates: Any = None) -> dict[str, Any]:
        _ = candidates
        return self._not_migrated(context, "rank_candidates")

    def build_evidence(self, context: FamilyStrategyContext, decision: Any = None) -> dict[str, Any]:
        _ = decision
        return self._not_migrated(context, "build_evidence")

    def publish(self, context: FamilyStrategyContext, decision: Any = None) -> dict[str, Any]:
        _ = decision
        return self._not_migrated(context, "publish")

    def get_cta_rule(self, context: FamilyStrategyContext) -> dict[str, Any]:
        return self._not_migrated(context, "get_cta_rule")

    def _not_migrated(self, context: FamilyStrategyContext, operation: str) -> dict[str, Any]:
        return {
            "governing_state": self.metadata.governing_state,
            "operation": operation,
            "owner": self.metadata.owner,
            "migrated": bool(self.metadata.migrated),
            "locked": bool(self.metadata.locked),
            "read_only": True,
            "product_routing_enabled": bool(self.metadata.migrated),
            "context_governing_state": context.governing_state,
            "reason": "contracted_entry_point_owned_by_family_strategy",
        }


__all__ = [
    "DiagnosticFamilyStrategy",
    "FamilyStrategyContext",
    "FamilyStrategyMetadata",
    "GoverningFamilyStrategy",
]
