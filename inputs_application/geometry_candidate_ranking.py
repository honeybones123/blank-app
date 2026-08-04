"""Deterministic ranking for geometry recommendation candidates."""

from __future__ import annotations

from typing import Any, Mapping

from inputs_application.geometry_search_policy import design_optimisation_goal
from inputs_application.candidate_identity import (
    make_auto_design_candidate_key as _make_auto_design_candidate_key,
)


def _ductility_util(candidate: Mapping[str, Any]) -> float | None:
    raw = dict(candidate.get("bending_components") or {}).get("ductility_util")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def _bending_demand_util(candidate: Mapping[str, Any]) -> float | None:
    bending = dict(
        dict(dict(candidate.get("overview") or {}).get("packs") or {}).get(
            "bending",
            {},
        )
    )
    phi = float(bending.get("summary_phiMu_kNm", 0.0) or 0.0)
    demand = float(bending.get("summary_Mu_star_kNm", 0.0) or 0.0)
    return demand / phi if phi > 1e-9 else None


def _objective_util(candidate: Mapping[str, Any]) -> float:
    state = dict(candidate.get("state") or {})
    goal = design_optimisation_goal(state)
    utils = dict(dict(candidate.get("overview") or {}).get("utils") or {})
    target_domain = str(candidate.get("target_domain_for_band") or "").lower()
    values = (
        [utils.get("shear")]
        if target_domain == "shear" or goal == "less_shear_reinforcement"
        else [_bending_demand_util(candidate), utils.get("shear")]
    )
    parsed = [float(value) for value in values if value is not None]
    return max(parsed) if parsed else float(candidate.get("worst_util", 0.0) or 0.0)


def _util_distance(candidate: Mapping[str, Any], mode: Mapping[str, Any]) -> float:
    util = _objective_util(candidate)
    low = float(mode["target_util_min"])
    high = float(mode["target_util_max"])
    if util < low:
        return low - util
    if util > high:
        return util - high
    return abs(util - ((low + high) / 2.0))


def _complexity(candidate: Mapping[str, Any]) -> float:
    existing = candidate.get("reo_complexity")
    if existing is not None:
        return float(existing)
    state = dict(candidate.get("state") or {})
    count_1 = int(float(state.get("bot1_count", 0) or 0))
    count_2 = int(float(state.get("bot2_count", 0) or 0))
    imbalance = abs(count_1 - count_2) if count_2 > 0 else 0
    return (
        int(candidate.get("bar_count", 0) or 0)
        + int(candidate.get("row_count", 1) or 1) * 8.0
        + float(candidate.get("reo_congestion_index", 0.0) or 0.0) * 12.0
        + imbalance * 3.0
    )


def _shallow_metrics(candidate: Mapping[str, Any]) -> tuple[int, bool, float, float]:
    depth = float(candidate.get("depth", 0.0) or 0.0)
    width = float(candidate.get("width", 0.0) or 0.0)
    seed_depth = float(candidate.get("_seed_depth", depth) or depth)
    seed_width = float(candidate.get("_seed_width", width) or width)
    seed_ast = float(
        candidate.get("_seed_ast_bot", candidate.get("Ast_bot", 0.0))
        or candidate.get("Ast_bot", 0.0)
        or 0.0
    )
    ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
    width_growth = max(width - seed_width, 0.0)
    depth_growth = depth > seed_depth + 1e-9
    width_increased = width > seed_width + 1e-9
    tier = (
        0
        if not width_increased and not depth_growth
        else 1
        if width_increased and not depth_growth
        else 2
        if width_increased
        else 3
    )
    depth_reduction = max(seed_depth - depth, 0.0)
    reo_growth = max(ast - seed_ast, 0.0)
    materially_shallower = depth_reduction >= 50.0 or (
        depth_reduction >= 25.0
        and width_growth <= 50.0
        and reo_growth <= 120.0
    )
    return tier, materially_shallower, width_growth, reo_growth


def _sort_key(candidate: Mapping[str, Any], mode: Mapping[str, Any]) -> tuple:
    strategy = str(mode.get("search_strategy", "balanced") or "balanced")
    compliant = 0 if bool(candidate.get("is_compliant")) else 1
    practical = 0 if (
        int(candidate.get("row_count", 0) or 0) <= 2
        and float(candidate.get("reo_congestion_index", 0.0) or 0.0)
        <= float(mode.get("practicality_congestion_limit", 20.0))
    ) else 1
    fail_count = int(candidate.get("fail_count", 0) or 0)
    worst = float(candidate.get("worst_util", float("inf")) or float("inf"))
    violation = max(worst - 1.0, 0.0) * 100.0 + fail_count * 25.0
    distance = _util_distance(candidate, mode)
    complexity = _complexity(candidate)
    depth = float(candidate.get("depth", 0.0) or 0.0)
    width = float(candidate.get("width", 0.0) or 0.0)
    bars = int(candidate.get("bar_count", 0) or 0)
    rows = int(candidate.get("row_count", 0) or 0)
    steel = float(candidate.get("Ast_bot", 0.0) or 0.0) + float(
        candidate.get("Ast_top", 0.0) or 0.0
    )
    tier, materially_shallower, width_growth, reo_growth = _shallow_metrics(
        candidate
    )
    if bool(candidate.get("_ductility_priority")):
        ductility = _ductility_util(candidate)
        ductility_value = (
            float(ductility) if ductility is not None else float("inf")
        )
        return (
            compliant,
            0 if ductility_value <= 1.0 else 1,
            max(ductility_value - 1.0, 0.0),
            ductility_value,
            int(candidate.get("_ductility_tier", 4) or 4),
            steel,
            practical,
            rows,
            bars,
            depth,
            width,
            distance,
            complexity,
        )
    if compliant:
        if strategy == "shallow":
            return (
                compliant, fail_count, violation, worst,
                0 if materially_shallower else 1, tier, depth,
                width_growth, reo_growth, practical, distance,
                complexity, steel, width,
            )
        if strategy == "low_reo":
            return (
                compliant, fail_count, violation, worst, practical,
                distance, complexity, rows, bars, depth, steel,
            )
        return (
            compliant, fail_count, violation, worst, practical,
            distance, depth, complexity, width, steel,
        )
    if strategy == "shallow":
        return (
            compliant, 0 if materially_shallower else 1, tier, depth,
            width_growth, reo_growth, practical, distance,
            complexity, steel, width,
        )
    if strategy == "low_reo":
        return (
            compliant, practical, complexity, rows, bars,
            distance, depth, steel,
        )
    low = float(mode["target_util_min"])
    high = float(mode["target_util_max"])
    objective = _objective_util(candidate)
    return (
        compliant,
        0 if low <= objective <= high else 1,
        practical,
        distance,
        depth,
        complexity,
        width,
        steel,
    )


def _dominates(
    candidate_a: Mapping[str, Any],
    candidate_b: Mapping[str, Any],
    mode: Mapping[str, Any],
) -> bool:
    if not bool(candidate_a.get("is_compliant")) or not bool(
        candidate_b.get("is_compliant")
    ):
        return False
    strategy = str(mode.get("search_strategy", "balanced") or "balanced")
    util_a = _util_distance(candidate_a, mode)
    util_b = _util_distance(candidate_b, mode)
    complexity_a = _complexity(candidate_a)
    complexity_b = _complexity(candidate_b)
    depth_a = float(candidate_a.get("depth", 0.0) or 0.0)
    depth_b = float(candidate_b.get("depth", 0.0) or 0.0)
    if strategy == "shallow":
        _, material_a, width_a, reo_a = _shallow_metrics(candidate_a)
        _, material_b, width_b, reo_b = _shallow_metrics(candidate_b)
        values_a = (
            0 if material_a else 1,
            depth_a,
            width_a,
            reo_a,
            complexity_a,
            util_a,
        )
        values_b = (
            0 if material_b else 1,
            depth_b,
            width_b,
            reo_b,
            complexity_b,
            util_b,
        )
        return all(a <= b for a, b in zip(values_a, values_b)) and any(
            a < b for a, b in zip(values_a, values_b)
        )
    if strategy == "low_reo":
        values_a = (
            complexity_a,
            int(candidate_a.get("row_count", 0) or 0),
            int(candidate_a.get("bar_count", 0) or 0),
            depth_a,
            util_a,
        )
        values_b = (
            complexity_b,
            int(candidate_b.get("row_count", 0) or 0),
            int(candidate_b.get("bar_count", 0) or 0),
            depth_b,
            util_b,
        )
        return all(a <= b for a, b in zip(values_a, values_b)) and any(
            a < b for a, b in zip(values_a, values_b)
        )
    values_a = (util_a, depth_a, complexity_a)
    values_b = (util_b, depth_b, complexity_b)
    return all(a <= b for a, b in zip(values_a, values_b)) and any(
        a < b for a, b in zip(values_a, values_b)
    )


def rank_geometry_candidates(
    candidates: list[dict[str, Any]],
    mode_config: Mapping[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Deduplicate and rank geometry candidates without session/debug authority."""

    effective_limit = min(max(1, int(limit)), 5)
    deduped: dict[tuple, dict[str, Any]] = {}
    for candidate in candidates:
        if not candidate:
            continue
        candidate.setdefault("reo_complexity", _complexity(candidate))
        key = _make_auto_design_candidate_key(candidate.get("state") or {})
        existing = deduped.get(key)
        if existing is None or _sort_key(candidate, mode_config) < _sort_key(
            existing,
            mode_config,
        ):
            deduped[key] = candidate
    ordered = sorted(
        deduped.values(),
        key=lambda item: _sort_key(item, mode_config),
    )
    kept: list[dict[str, Any]] = []
    for candidate in ordered:
        if any(_dominates(existing, candidate, mode_config) for existing in kept):
            continue
        if len(kept) >= effective_limit:
            continue
        kept.append(candidate)
    return kept


__all__ = ["rank_geometry_candidates"]
