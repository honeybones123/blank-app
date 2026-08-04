"""Auto assignment engine for normalized Batch Design rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from batch_design.models import BatchAssignmentResult, BatchBeamCase, BatchBeamTemplate, BatchDesignResult


PREFERENCE_ORDER = ("same_depth", "same_width", "same_reo_cage", "closest_utilisation", "standardised_grouping")


def _template_from_result(result: BatchDesignResult) -> BatchBeamTemplate:
    return result.to_template()


def _candidate_capacity(template: BatchBeamTemplate, demand_key: str) -> float:
    try:
        return float(template.capacities.get(demand_key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _demand_utilisation(case: BatchBeamCase, template: BatchBeamTemplate) -> float | None:
    utils: list[float] = []
    for key, demand in case.demand_vector().items():
        demand_abs = abs(float(demand or 0.0))
        if demand_abs <= 0.0:
            continue
        capacity = abs(_candidate_capacity(template, key))
        if capacity <= 0.0:
            return None
        utils.append(demand_abs / capacity)
    return max(utils) if utils else 0.0


def _template_field(template: BatchBeamTemplate, name: str) -> Any:
    if name in template.parameters:
        return template.parameters.get(name)
    return getattr(template, name, None)


def _preference_penalty(case: BatchBeamCase, template: BatchBeamTemplate, preferences: Mapping[str, Any]) -> float:
    penalty = 0.0
    metadata = dict(case.governing_metadata or {})
    if preferences.get("same_depth"):
        desired = metadata.get("D") or metadata.get("depth")
        if desired is not None and _template_field(template, "D") != desired:
            penalty += 0.2
    if preferences.get("same_width"):
        desired = metadata.get("b") or metadata.get("width")
        if desired is not None and _template_field(template, "b") != desired:
            penalty += 0.2
    if preferences.get("same_reo_cage"):
        desired = metadata.get("reo_cage")
        if desired is not None and template.reinforcement.get("reo_cage") != desired:
            penalty += 0.2
    if preferences.get("standardised_grouping") and template.metadata.get("standard_group") if hasattr(template, "metadata") else False:
        penalty -= 0.05
    return penalty


def assign_beam_case(
    case: BatchBeamCase,
    candidates: Iterable[BatchBeamTemplate | BatchDesignResult],
    *,
    preferences: Mapping[str, Any] | None = None,
) -> BatchAssignmentResult:
    preferences = dict(preferences or {})
    normalized = [
        _template_from_result(candidate) if isinstance(candidate, BatchDesignResult) else candidate
        for candidate in candidates
    ]
    rejected: list[dict[str, Any]] = []
    passing: list[tuple[float, float, BatchBeamTemplate]] = []

    for template in normalized:
        if not template.passing:
            rejected.append({"template_id": template.template_id, "reason": "candidate is not passing"})
            continue
        utilisation = _demand_utilisation(case, template)
        if utilisation is None:
            rejected.append({"template_id": template.template_id, "reason": "missing capacity for demanded action"})
            continue
        if utilisation > 1.0:
            rejected.append({"template_id": template.template_id, "reason": f"utilisation {utilisation:.3f} exceeds 1.0"})
            continue

        if preferences.get("closest_utilisation", True):
            base_score = abs(1.0 - utilisation)
        else:
            base_score = utilisation
        score = base_score + _preference_penalty(case, template, preferences)
        passing.append((score, utilisation, template))

    if not passing:
        return BatchAssignmentResult(
            member_id=case.member_id,
            assigned_template_id=None,
            assigned_label=None,
            passed=False,
            reason="No passing candidate met all demanded actions.",
            rejected_candidates=rejected,
        )

    passing.sort(key=lambda item: item[0])
    _, utilisation, template = passing[0]
    return BatchAssignmentResult(
        member_id=case.member_id,
        assigned_template_id=template.template_id,
        assigned_label=template.label,
        passed=True,
        reason=f"Selected nearest stronger passing candidate at utilisation {utilisation:.3f}.",
        utilisation=utilisation,
        rejected_candidates=rejected,
    )


def assign_batch_cases(
    cases: Iterable[BatchBeamCase],
    candidates: Iterable[BatchBeamTemplate | BatchDesignResult],
    *,
    preferences: Mapping[str, Any] | None = None,
) -> list[BatchAssignmentResult]:
    candidate_list = list(candidates)
    return [assign_beam_case(case, candidate_list, preferences=preferences) for case in cases]
