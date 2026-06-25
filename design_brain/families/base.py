"""Family-owned Design Brain strategy interfaces.

These interfaces are intentionally dormant. They define the ownership shape for
future governing-family migrations without routing product decisions through the
new family layer yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class FamilyStrategyContext:
    """Read-only inputs a family strategy may inspect in a future routing phase."""

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
    """No-op base for Phase 1 family shells.

    The methods deliberately return diagnostic placeholders instead of product
    decisions. Future migration phases should override one family at a time.
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
            "migrated": False,
            "locked": False,
            "read_only": True,
            "product_routing_enabled": False,
            "context_governing_state": context.governing_state,
            "reason": "family_strategy_shell_only",
        }


__all__ = [
    "DiagnosticFamilyStrategy",
    "FamilyStrategyContext",
    "FamilyStrategyMetadata",
    "GoverningFamilyStrategy",
]
