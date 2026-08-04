"""Permanent typed assembly for geometry/bottom compound recommendations."""

from __future__ import annotations

from typing import Callable

from inputs_application.design_brain_composition import build_bottom_arrangement_pool_builder
from inputs_application.candidate_metrics import candidate_state_to_shared_updates
from inputs_application.recommendation_primitives import (
    annotate_bottom_candidate_deltas,
    bottom_arrangement_to_shared_updates,
    geometry_trial_axis_for_bottom,
    practical_bottom_reo_label,
)
from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.state_utils import float_from_state, updates_match_state
from inputs_application.recommendation_compound_contracts import (
    RecommendationCompoundRuntime,
)
from section_layout import compute_bar_layout_pure


BOTTOM_RECOMMENDATION_BAR_DIAMETERS = (10, 12, 16, 20, 24, 28, 32, 36, 40)
BOTTOM_RECOMMENDATION_CANDIDATE_LIMIT = 20


def arrangement_fits_state(
    state: dict,
    arrangement: dict,
    *,
    layout_cache: dict | None = None,
) -> bool:
    width = float(resolve_geometry_width_context(state)[2])
    cover_side = float_from_state(state, "cover_side", 40.0)
    row_gap = float_from_state(state, "rowgap_bot", 60.0)
    diameter = int(arrangement.get("db_bot_1", 0) or 0)
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    if count_1 < 2 or diameter <= 0:
        return False
    minimum_spacing = max(float(diameter), 25.0)
    cache = layout_cache if isinstance(layout_cache, dict) else {}

    def _row_fits(count: int) -> bool:
        key = (width, cover_side, row_gap, diameter, count)
        layout = cache.get(key)
        if layout is None:
            layout = compute_bar_layout_pure(
                b=width,
                cover_side=cover_side,
                nb_or_s=float(count),
                db=float(diameter),
                s_min=minimum_spacing,
                rowgap=row_gap,
            )
            cache[key] = layout
        return bool(layout.get("fits_single_row", False))

    if not _row_fits(count_1):
        return False
    return count_2 <= 0 or (count_2 >= 2 and _row_fits(count_2))


def compound_signature_preview(
    seed_state: dict,
    compound_state: dict,
) -> dict:
    updates = candidate_state_to_shared_updates(seed_state, compound_state)
    width_key, _, _ = resolve_geometry_width_context(seed_state)
    order = (
        width_key,
        "D",
        "bot_row_count",
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
    )
    return {key: updates[key] for key in order if key in updates}


def compound_title(axis: str, geometry_label: str) -> str:
    if axis == "width":
        return "Increase width and rebalance bottom reinforcement"
    if axis == "depth":
        return "Increase depth and adjust bottom reinforcement"
    label = str(geometry_label or "").strip()
    return (
        f"Adjust geometry and bottom reinforcement ({label})"
        if label
        else "Adjust geometry and bottom reinforcement"
    )


def compound_effective_signature(
    seed_state: dict,
    compound_state: dict,
) -> tuple:
    updates = candidate_state_to_shared_updates(seed_state, compound_state)
    return tuple(
        (
            key,
            round(float(value), 6) if isinstance(value, float) else value,
        )
        for key, value in sorted(updates.items())
    )


def select_top_geometry_seeds(
    candidates: list[dict],
    state: dict,
    axis: str,
    *,
    limit: int,
) -> list[dict]:
    geometry = [
        candidate
        for candidate in candidates
        if candidate.get("recommendation_geometry_trial")
        and geometry_trial_axis_for_bottom(candidate, state) == axis
    ]

    def _sort_key(candidate: dict) -> float:
        raw = ((candidate.get("overview") or {}).get("utils") or {}).get(
            "bending"
        )
        try:
            return float(raw) if raw is not None else 999.0
        except (TypeError, ValueError):
            return 999.0

    picked = []
    seen = set()
    for candidate in sorted(geometry, key=_sort_key):
        updates = dict(candidate.get("updates") or {})
        if axis == "width":
            width_key, _, _ = resolve_geometry_width_context(state)
            if width_key not in updates:
                continue
            try:
                marker = ("width", round(float(updates[width_key]), 3))
            except (TypeError, ValueError):
                continue
        elif axis == "depth":
            if "D" not in updates:
                continue
            try:
                marker = ("depth", round(float(updates["D"]), 3))
            except (TypeError, ValueError):
                continue
        else:
            continue
        if marker in seen:
            continue
        seen.add(marker)
        picked.append(candidate)
        if len(picked) >= limit:
            break
    return picked


def generate_bottom_arrangements(
    state: dict,
    mode_config: dict,
    *,
    band: int,
    context: dict | None = None,
    limit: int | None = None,
) -> list[dict]:
    return build_bottom_arrangement_pool_builder()(
        state,
        mode_config,
        band=band,
        context=context,
        limit=limit,
        bar_diameters=BOTTOM_RECOMMENDATION_BAR_DIAMETERS,
        default_limit=BOTTOM_RECOMMENDATION_CANDIDATE_LIMIT,
    )


def build_bottom_compound_runtime(
    *,
    evaluate_candidate_fast: Callable[..., dict | None],
) -> RecommendationCompoundRuntime:
    return RecommendationCompoundRuntime(
        annotate_bottom_deltas=annotate_bottom_candidate_deltas,
        arrangement_fits_state=arrangement_fits_state,
        bottom_arrangement_updates=bottom_arrangement_to_shared_updates,
        compound_effective_signature=compound_effective_signature,
        compound_title=compound_title,
        candidate_state_updates=candidate_state_to_shared_updates,
        compound_signature_preview=compound_signature_preview,
        evaluate_candidate_fast=evaluate_candidate_fast,
        generate_bottom_arrangements=generate_bottom_arrangements,
        geometry_trial_axis=geometry_trial_axis_for_bottom,
        practical_bottom_label=practical_bottom_reo_label,
        select_geometry_seeds=select_top_geometry_seeds,
        updates_match_state=updates_match_state,
    )


__all__ = [
    "arrangement_fits_state",
    "build_bottom_compound_runtime",
    "compound_effective_signature",
    "compound_signature_preview",
    "compound_title",
    "select_top_geometry_seeds",
]
