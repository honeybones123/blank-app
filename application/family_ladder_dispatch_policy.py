"""Application-owned family-ladder routing contract.

The concrete family registry is supplied by composition. This module owns
only the neutral routing decision and never imports a Design Brain family.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from application.contracts.family_classification import normalise_governing_family


LADDER_METHOD_BY_FAMILY: dict[str, str | None] = {
    "BENDING_FAIL_GOVERNS": "contracted_repair_ladder_specs",
    "SHEAR_FAIL_GOVERNS": "contracted_repair_ladder_specs",
    "COMBINED_BENDING_SHEAR_FAIL": "contracted_repair_ladder_specs",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": "contracted_mixed_ladder_result",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": "contracted_mixed_ladder_result",
    "BENDING_OVERDESIGN_GOVERNS": "contracted_optimisation_ladder_specs",
    "SHEAR_OVERDESIGN_GOVERNS": "contracted_optimisation_ladder_specs",
    "COMBINED_OVERDESIGN": "contracted_optimisation_ladder_specs",
    "SERVICEABILITY_GOVERNS": "contracted_serviceability_ladder_result",
    "MIN_BENDING_REO_GOVERNS": None,
    "MIN_SHEAR_REO_GOVERNS": None,
    "GEOMETRY_DETAILING_GOVERNS": "contracted_repair_ladder_specs",
    "LOCKED_NO_REPAIR": None,
    "TARGET_BAND_REACHED": None,
    "EXACT_STOP_PROVEN": None,
}
TERMINAL_FAMILIES = frozenset(
    family_id for family_id, method_name in LADDER_METHOD_BY_FAMILY.items() if method_name is None
)


@dataclass(frozen=True)
class FamilyLadderDispatchDecision:
    selected_family_id: str | None
    normalised_family_id: str | None
    classification_passed: bool
    classification_hash: str | None
    strategy_found: bool
    strategy_owner: str | None
    ladder_method: str | None
    candidate_contract_id: str | None
    generation_policy_id: str | None
    evaluation_policy_id: str | None
    selection_policy_id: str | None
    ladder_method_available: bool
    terminal_family: bool
    should_run_family_ladder: bool
    legacy_fallback_allowed: bool
    legacy_fallback_reason: str | None
    dispatch_owner: str = "application.family_ladder_dispatch_policy"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_family_ladder_dispatch(
    classification: dict[str, Any] | None,
    *,
    strategy_lookup: Callable[[str], Any],
) -> FamilyLadderDispatchDecision:
    classified = dict(classification or {})
    selected_raw = str(
        classified.get("selected_family_id") or classified.get("selected_family") or ""
    ).strip()
    selected = normalise_governing_family(selected_raw) if selected_raw else ""
    passed = bool(classified.get("classification_passed")) and bool(selected)
    classification_hash = str(
        classified.get("classification_hash")
        or (classified.get("selection_evidence") or {}).get("classification_hash")
        or ""
    ).strip() or None
    strategy = strategy_lookup(selected) if passed else None
    strategy_found = strategy is not None
    metadata = getattr(strategy, "metadata", None)
    strategy_owner = (
        str(getattr(metadata, "owner", "") or "").strip()
        or (f"{type(strategy).__module__}.{type(strategy).__name__}" if strategy is not None else None)
    )
    ladder_method = LADDER_METHOD_BY_FAMILY.get(selected)
    terminal = selected in TERMINAL_FAMILIES
    method_available = bool(
        ladder_method and strategy is not None and callable(getattr(strategy, ladder_method, None))
    )
    should_run = bool(passed and not terminal and method_available)
    candidate_contract_id = (
        f"{selected}.{ladder_method or 'terminal_no_candidates'}.v1" if passed else None
    )
    generation_policy_id = "terminal_no_candidates.v1" if terminal else ("ordered_family_contract.v1" if passed else None)
    evaluation_policy_id = "terminal_no_evaluation.v1" if terminal else ("authoritative_engineering_executor.v1" if passed else None)
    selection_policy_id = "terminal_typed_outcome.v1" if terminal else ("family_contract_rank_key.v1" if passed else None)
    fallback_reason: str | None = None
    fallback_allowed = False
    if not passed:
        fallback_reason = "family_classification_not_proven"
    elif terminal:
        fallback_reason = "terminal_family_does_not_require_candidate_search"
    elif selected not in LADDER_METHOD_BY_FAMILY:
        fallback_allowed = True
        fallback_reason = "classified_family_has_no_dispatch_contract"
    elif not strategy_found:
        fallback_allowed = True
        fallback_reason = "classified_family_strategy_not_registered"
    elif not method_available:
        fallback_allowed = True
        fallback_reason = "classified_family_ladder_entry_point_not_available"
    return FamilyLadderDispatchDecision(
        selected_family_id=selected_raw or None,
        normalised_family_id=selected or None,
        classification_passed=passed,
        classification_hash=classification_hash,
        strategy_found=strategy_found,
        strategy_owner=strategy_owner,
        ladder_method=ladder_method,
        candidate_contract_id=candidate_contract_id,
        generation_policy_id=generation_policy_id,
        evaluation_policy_id=evaluation_policy_id,
        selection_policy_id=selection_policy_id,
        ladder_method_available=method_available,
        terminal_family=terminal,
        should_run_family_ladder=should_run,
        legacy_fallback_allowed=fallback_allowed,
        legacy_fallback_reason=fallback_reason,
    )


__all__ = [
    "FamilyLadderDispatchDecision",
    "LADDER_METHOD_BY_FAMILY",
    "TERMINAL_FAMILIES",
    "resolve_family_ladder_dispatch",
]
