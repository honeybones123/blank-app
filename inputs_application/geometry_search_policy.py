"""Pure geometry search policy shared by Inputs recommendation runtimes."""

from __future__ import annotations

import math
from typing import Any, Mapping

from application.contracts.design_policy import (
    AUTO_DESIGN_MODE_CONFIG,
    DESIGN_OPTIMISATION_GOAL_LABELS,
    resolve_design_mode_config,
    resolve_design_optimisation_goal,
    resolve_efficiency_target_band,
)
from inputs_application.policy_constants import (
    EFFICIENCY_TARGET_UTIL_MAX,
    EFFICIENCY_TARGET_UTIL_MIN,
)
from design_brain.families.bending_fail_governs.geometry_ratio import (
    bending_depth_width_ratio_limit,
    depth_width_ratio,
)
from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.recommendation_evaluation import effective_bottom_design_state
from inputs_application.state_utils import (
    float_from_state,
    guidance_state_snapshot,
    state_with_resolved_design_actions,
    updates_match_state,
)
from inputs_application.candidate_identity import (
    make_auto_design_candidate_key as _make_auto_design_candidate_key,
)
from calculations.design_actions import resolve_design_actions_from_state as resolve_design_actions


def design_optimisation_goal(state: Mapping[str, Any]) -> str:
    return str(
        resolve_design_optimisation_goal(
            dict(state),
            goal_labels=DESIGN_OPTIMISATION_GOAL_LABELS,
            default_goal="balanced",
        )
    )


def design_mode_config(goal: str | None = None) -> dict[str, Any]:
    return resolve_design_mode_config(
        goal or "balanced",
        mode_config_by_goal=AUTO_DESIGN_MODE_CONFIG,
        default_goal="balanced",
    )


def resolved_efficiency_target_band(
    mode_config: Mapping[str, Any] | None = None,
    *,
    goal: str | None = None,
) -> tuple[float, float, bool]:
    return resolve_efficiency_target_band(
        mode_config,
        goal=goal or "balanced",
        mode_config_by_goal=AUTO_DESIGN_MODE_CONFIG,
        default_low=EFFICIENCY_TARGET_UTIL_MIN,
        default_high=EFFICIENCY_TARGET_UTIL_MAX,
        default_goal="balanced",
    )


def geometry_lock_enabled(state: Mapping[str, Any]) -> bool:
    return bool(state.get("optimisation_lock_geometry", False))


def _parse_util(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def _ductility_governs_overview(overview: Mapping[str, Any] | None) -> bool:
    rows = (
        dict(dict(overview or {}).get("packs") or {})
        .get("bending", {})
        .get("rows", [])
    )
    ductility_row = next(
        (row for row in rows if str(row.get("title") or "") == "Ductility limit"),
        None,
    )
    flexural_row = next(
        (
            row
            for row in rows
            if str(row.get("title") or "") == "Flexural strength capacity"
        ),
        None,
    )
    ductility = _parse_util((ductility_row or {}).get("util"))
    flexural = _parse_util((flexural_row or {}).get("util"))
    candidates = [
        value for value in (ductility, flexural) if value is not None
    ]
    return bool(
        ductility is not None
        and candidates
        and ductility >= max(candidates) - 1e-6
        and ductility >= 0.85
    )


def build_auto_design_context(
    seed_state: Mapping[str, Any],
    mode_config: Mapping[str, Any],
    reference_overview: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the immutable inputs used by recommendation candidate evaluation."""

    overview = dict(reference_overview or {})
    actions = resolve_design_actions(dict(seed_state))
    resolved_seed = state_with_resolved_design_actions(seed_state, actions)
    shear_util = float(dict(overview.get("utils") or {}).get("shear", 0.0) or 0.0)
    shear_relevant = float(actions.get("Vu", 0.0) or 0.0) > 0.0 and shear_util >= 0.20
    return {
        "seed_state": dict(resolved_seed),
        "mode_config": dict(mode_config),
        "mode_signature": str(
            mode_config.get("search_strategy", "balanced") or "balanced"
        ),
        "actions": dict(actions),
        "actions_signature": tuple(actions.get("signature", ())),
        "seed_overview": overview,
        "ductility_priority": _ductility_governs_overview(overview),
        "geometry_locked": geometry_lock_enabled(seed_state),
        "disable_shear_strength_candidates": bool(overview) and not shear_relevant,
        "disable_shear_cleanup_candidates": False,
        "seen_candidate_keys": set(),
        "layout_fit_cache": {},
    }


def recommendation_search_allowed(
    state: Mapping[str, Any],
    overview: Mapping[str, Any] | None,
) -> bool:
    """Return whether the current state has enough design truth for a search."""

    resolved_state = guidance_state_snapshot(state)
    _, _, width = resolve_geometry_width_context(resolved_state)
    depth = float_from_state(resolved_state, "D", 0.0)
    span = float_from_state(resolved_state, "L", 0.0)
    utils = dict(dict(overview or {}).get("utils") or {})
    no_key_results = all(
        util is None or float(util) <= 0.0
        for util in (utils.get("bending"), utils.get("shear"))
    )
    if width <= 0.0 or depth <= 0.0 or span <= 0.0 or no_key_results:
        return False

    actions = resolve_design_actions(resolved_state)
    no_actions = max(
        (
            abs(float(actions.get(key, 0.0) or 0.0))
            for key in ("Mu", "Vu", "Nu", "Tu")
        ),
        default=0.0,
    ) <= 1e-9
    bottom = effective_bottom_design_state(resolved_state)
    no_bottom_reo = (
        float(bottom.get("Ast_bot", 0.0) or 0.0) <= 0.0
        or int(bottom.get("nb_bot", 0) or 0) <= 0
        or float(bottom.get("db_bot", 0.0) or 0.0) <= 0.0
    )
    no_shear_reo = (
        int(float(resolved_state.get("lig_legs", 0) or 0)) <= 0
        or float_from_state(resolved_state, "lig_d", 0.0) <= 0.0
        or float_from_state(resolved_state, "s_lig", 0.0) <= 0.0
    )
    return not (no_actions and (no_bottom_reo or no_shear_reo))


def _candidate_component(candidate: Mapping[str, Any], key: str) -> float | None:
    try:
        value = float(dict(candidate.get("bending_components") or {}).get(key))
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else value


def candidate_ductility_governs(candidate: Mapping[str, Any] | None) -> bool:
    if not isinstance(candidate, Mapping):
        return False
    ductility = _candidate_component(candidate, "ductility_util")
    if ductility is None:
        return False
    governing = [
        value
        for value in (
            _candidate_component(candidate, "flexural_util"),
            _candidate_component(candidate, "min_steel_util"),
            ductility,
        )
        if value is not None
    ]
    return bool(
        governing
        and ductility >= max(governing) - 1e-6
        and ductility >= 0.85
    )


def rescue_geometry_width_for_depth_ratio(
    state: Mapping[str, Any] | None,
    updates: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    resolved_updates = dict(updates or {})
    if not resolved_updates or "D" not in resolved_updates:
        return dict(updates) if isinstance(updates, Mapping) else None
    resolved_state = dict(state or {})
    width_key, _, current_width = resolve_geometry_width_context(resolved_state)
    if width_key in resolved_updates:
        return resolved_updates
    try:
        depth = float(resolved_updates.get("D") or resolved_state.get("D") or 0.0)
        width = float(
            resolved_state.get(width_key, current_width) or current_width or 0.0
        )
        limit = float(bending_depth_width_ratio_limit())
        ratio = depth_width_ratio(width=width, depth=depth)
    except (TypeError, ValueError):
        return resolved_updates
    if ratio is None or ratio <= limit + 1e-9:
        return resolved_updates
    required_width = max(width, depth / limit, 250.0)
    rescued_width = float(int(round(required_width / 10.0) * 10))
    if rescued_width < required_width:
        rescued_width += 10.0
    resolved_updates[width_key] = rescued_width
    if width_key != "b":
        resolved_updates["b"] = rescued_width
    return resolved_updates


def geometry_state_with_updates(
    base_state: Mapping[str, Any],
    *,
    depth: float | None = None,
    width: float | None = None,
) -> dict[str, Any]:
    candidate_state = dict(base_state)
    width_key, _, current_width = resolve_geometry_width_context(dict(base_state))
    if depth is not None:
        candidate_state["D"] = float(int(round(max(350.0, depth) / 10.0) * 10))
    if width is not None:
        resolved_width = float(int(round(max(250.0, width) / 10.0) * 10))
        candidate_state[width_key] = resolved_width
        if width_key != "b":
            candidate_state["b"] = resolved_width
    else:
        candidate_state[width_key] = float(current_width)
    ratio_updates = {"D": candidate_state.get("D")}
    if width is not None:
        ratio_updates[width_key] = candidate_state.get(width_key)
    candidate_state.update(
        rescue_geometry_width_for_depth_ratio(base_state, ratio_updates) or {}
    )
    return candidate_state


def geometry_tightening_trial_updates(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    resolved_state = dict(state)
    goal = design_optimisation_goal(resolved_state)
    width_key, _, current_width = resolve_geometry_width_context(resolved_state)
    current_depth = float_from_state(resolved_state, "D", 600.0)
    unique: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {}

    def add(width: float, depth: float) -> None:
        rounded_width = float(int(round(max(250.0, width) / 10.0) * 10))
        rounded_depth = float(int(round(max(350.0, depth) / 10.0) * 10))
        updates = {width_key: rounded_width, "D": rounded_depth}
        if width_key != "b":
            updates["b"] = rounded_width
        if not updates_match_state(resolved_state, updates):
            unique[tuple(sorted((key, str(value)) for key, value in updates.items()))] = updates

    trials = {
        "shallower_beam": (
            (current_width, current_depth - 100.0),
            (current_width, current_depth - 50.0),
            (current_width - 50.0, current_depth - 50.0),
            (current_width - 50.0, current_depth),
        ),
        "balanced": (
            (current_width, current_depth - 50.0),
            (current_width - 50.0, current_depth),
            (current_width - 50.0, current_depth - 50.0),
        ),
        "less_longitudinal_reinforcement": (
            (current_width, current_depth - 50.0),
            (current_width - 50.0, current_depth),
        ),
    }.get(goal, ((current_width, current_depth - 50.0),))
    for width, depth in trials:
        add(width, depth)
    return list(unique.values())


def generate_shallower_or_equal_depths(seed_candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    seed_state = dict(seed_candidate.get("state") or {})
    if geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(
        seed_candidate.get("depth", float_from_state(seed_state, "D", 600.0))
        or float_from_state(seed_state, "D", 600.0)
    )
    return [
        geometry_state_with_updates(seed_state, depth=depth)
        for depth in (seed_depth - 100.0, seed_depth - 50.0, seed_depth)
        if depth >= 350.0
    ]


def generate_slightly_deeper_depths(seed_candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    seed_state = dict(seed_candidate.get("state") or {})
    if geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(
        seed_candidate.get("depth", float_from_state(seed_state, "D", 600.0))
        or float_from_state(seed_state, "D", 600.0)
    )
    return [
        geometry_state_with_updates(seed_state, depth=seed_depth + 50.0),
        geometry_state_with_updates(seed_state, depth=seed_depth + 100.0),
    ]


def _dedupe(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list(
        {
            _make_auto_design_candidate_key(state): state
            for state in states
        }.values()
    )


def generate_same_or_larger_geometry_options(seed_candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    seed_state = dict(seed_candidate.get("state") or {})
    if geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(
        seed_candidate.get("depth", float_from_state(seed_state, "D", 600.0))
        or float_from_state(seed_state, "D", 600.0)
    )
    _, _, current_width = resolve_geometry_width_context(seed_state)
    if candidate_ductility_governs(seed_candidate):
        pairs = (
            (seed_depth, None),
            (seed_depth, current_width + 50.0),
            (seed_depth, current_width + 100.0),
            (seed_depth + 50.0, None),
            (seed_depth + 50.0, current_width + 50.0),
            (seed_depth + 100.0, None),
        )
    else:
        pairs = (
            (seed_depth, None),
            (seed_depth + 50.0, None),
            (seed_depth + 100.0, None),
            (seed_depth, current_width + 50.0),
            (seed_depth + 50.0, current_width + 50.0),
        )
    return _dedupe(
        [
            geometry_state_with_updates(seed_state, depth=depth, width=width)
            for depth, width in pairs
        ]
    )


def generate_balanced_geometry_options(seed_candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    seed_state = dict(seed_candidate.get("state") or {})
    if geometry_lock_enabled(seed_state):
        return []
    seed_depth = float(
        seed_candidate.get("depth", float_from_state(seed_state, "D", 600.0))
        or float_from_state(seed_state, "D", 600.0)
    )
    _, _, current_width = resolve_geometry_width_context(seed_state)
    pairs = (
        (
            (seed_depth, None),
            (seed_depth, current_width + 50.0),
            (seed_depth, current_width + 100.0),
            (seed_depth + 50.0, None),
        )
        if candidate_ductility_governs(seed_candidate)
        else (
            (seed_depth, None),
            (seed_depth - 50.0, None),
            (seed_depth + 50.0, None),
            (seed_depth, current_width - 50.0),
            (seed_depth, current_width + 50.0),
        )
    )
    return _dedupe(
        [
            geometry_state_with_updates(seed_state, depth=depth, width=width)
            for depth, width in pairs
        ]
    )


__all__ = [
    "candidate_ductility_governs",
    "build_auto_design_context",
    "design_mode_config",
    "design_optimisation_goal",
    "generate_balanced_geometry_options",
    "generate_same_or_larger_geometry_options",
    "generate_shallower_or_equal_depths",
    "generate_slightly_deeper_depths",
    "geometry_lock_enabled",
    "geometry_state_with_updates",
    "geometry_tightening_trial_updates",
    "recommendation_search_allowed",
    "rescue_geometry_width_for_depth_ratio",
]
