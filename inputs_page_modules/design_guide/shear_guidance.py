"""Shear guidance item coordination for the Inputs page Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


_SHEAR_GUIDANCE_DEPENDENCIES: tuple[str, ...] = (
    "_choose_geometry_trial_for_metric",
    "_compute_shear_recommendation",
    "_design_optimisation_goal",
    "_fallback_shear_reinforcement_step_updates",
    "_geometry_trial_title_for_choice",
    "_guidance_action_updates",
    "_guidance_bucket",
    "_guidance_change_lines_for_updates",
    "_guidance_item",
    "_log_shear_top_guidance_recommendation",
    "_next_tighter_link_spacing_updates",
    "_overall_status_from_rows",
    "_parse_util_value",
    "_shear_guidance_item_from_search_rec",
    "_shear_no_demand_cleanup_guidance_item_if_needed",
    "_shear_spacing_guidance_floor_mm",
    "_shear_state_label",
    "_updates_match_state",
)


@dataclass(frozen=True)
class ShearGuidanceRuntime:
    choose_geometry_trial_for_metric: Callable[..., Any]
    compute_shear_recommendation: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    fallback_shear_reinforcement_step_updates: Callable[..., Any]
    geometry_trial_title_for_choice: Callable[..., Any]
    guidance_action_updates: Callable[..., Any]
    guidance_bucket: Callable[..., Any]
    guidance_change_lines_for_updates: Callable[..., Any]
    guidance_item: Callable[..., Any]
    log_shear_top_guidance_recommendation: Callable[..., Any]
    next_tighter_link_spacing_updates: Callable[..., Any]
    overall_status_from_rows: Callable[..., Any]
    parse_util_value: Callable[..., Any]
    shear_guidance_item_from_search_rec: Callable[..., Any]
    shear_no_demand_cleanup_guidance_item_if_needed: Callable[..., Any]
    shear_spacing_guidance_floor_mm: Callable[..., Any]
    shear_state_label: Callable[..., Any]
    updates_match_state: Callable[..., Any]


def bind_shear_guidance_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SHEAR_GUIDANCE_DEPENDENCIES
            if name in namespace
        }
    )


def _shear_item_from_geometry_trials(
    state: dict,
    *,
    title: str,
    status: str,
    util: float | None,
    secondary: str,
    reasoning_fallback: str,
    levers: str,
    default_depth_delta: float,
    branch: str,
    _emit,
):
    if util is None:
        return None
    g = _choose_geometry_trial_for_metric(
        state,
        metric="shear",
        baseline_util=float(util),
        ladder_name="shear_geometry_trials",
    )
    if g:
        reasoning = (
            f"Why: width/depth trial chooser picked {g['label'].lower()} "
            f"(shear utilisation {float(util):.2f} → {float(g.get('util_after', 0.0) or 0.0):.2f})."
        )
        s_cl = _guidance_change_lines_for_updates(state, dict(g.get("updates") or {}))
        item = _guidance_item(
            "shear",
            _geometry_trial_title_for_choice(title, g, state),
            g["label"],
            secondary,
            reasoning,
            levers,
            str(g.get("action_type") or "increase_depth"),
            dict(g.get("payload") or {}),
            status=status,
            util=util,
            guidance_before_after=str(g.get("before_after") or "") or None,
            guidance_change_lines=s_cl or None,
        )
        return _emit(
            item,
            branch=branch,
            proposed_updates=dict(g.get("updates") or {}),
            expected_util_after=float(g.get("util_after", 0.0) or 0.0),
        )
    depth_payload = {"delta_mm": float(default_depth_delta)}
    depth_updates = _guidance_action_updates("increase_depth", depth_payload, state=state)
    if depth_updates and not _updates_match_state(state, depth_updates):
        item = _guidance_item(
            "shear",
            title,
            f"Increase depth D by ~{int(default_depth_delta)} mm",
            secondary,
            reasoning_fallback,
            levers,
            "increase_depth",
            depth_payload,
            status=status,
            util=util,
        )
        return _emit(item, branch=f"{branch}:depth_fallback_heuristic", proposed_updates=depth_updates)
    return None


def _shear_guidance_item(
    state: dict,
    pack: dict,
    *,
    runtime: ShearGuidanceRuntime | None = None,
) -> dict | None:
    if runtime is not None:
        _choose_geometry_trial_for_metric = (
            runtime.choose_geometry_trial_for_metric
        )
        _compute_shear_recommendation = (
            runtime.compute_shear_recommendation
        )
        _design_optimisation_goal = runtime.design_optimisation_goal
        _fallback_shear_reinforcement_step_updates = (
            runtime.fallback_shear_reinforcement_step_updates
        )
        _geometry_trial_title_for_choice = (
            runtime.geometry_trial_title_for_choice
        )
        _guidance_action_updates = runtime.guidance_action_updates
        _guidance_bucket = runtime.guidance_bucket
        _guidance_change_lines_for_updates = (
            runtime.guidance_change_lines_for_updates
        )
        _guidance_item = runtime.guidance_item
        _log_shear_top_guidance_recommendation = (
            runtime.log_shear_top_guidance_recommendation
        )
        _next_tighter_link_spacing_updates = (
            runtime.next_tighter_link_spacing_updates
        )
        _overall_status_from_rows = runtime.overall_status_from_rows
        _parse_util_value = runtime.parse_util_value
        _shear_guidance_item_from_search_rec = (
            runtime.shear_guidance_item_from_search_rec
        )
        _shear_no_demand_cleanup_guidance_item_if_needed = (
            runtime.shear_no_demand_cleanup_guidance_item_if_needed
        )
        _shear_spacing_guidance_floor_mm = (
            runtime.shear_spacing_guidance_floor_mm
        )
        _shear_state_label = runtime.shear_state_label
        _updates_match_state = runtime.updates_match_state
    else:
        namespace = globals()
        for dependency in _SHEAR_GUIDANCE_DEPENDENCIES:
            if dependency not in namespace:
                raise RuntimeError(
                    f"missing shear guidance dependency: {dependency}"
                )
        _choose_geometry_trial_for_metric = namespace[
            "_choose_geometry_trial_for_metric"
        ]
        _compute_shear_recommendation = namespace[
            "_compute_shear_recommendation"
        ]
        _design_optimisation_goal = namespace[
            "_design_optimisation_goal"
        ]
        _fallback_shear_reinforcement_step_updates = namespace[
            "_fallback_shear_reinforcement_step_updates"
        ]
        _geometry_trial_title_for_choice = namespace[
            "_geometry_trial_title_for_choice"
        ]
        _guidance_action_updates = namespace["_guidance_action_updates"]
        _guidance_bucket = namespace["_guidance_bucket"]
        _guidance_change_lines_for_updates = namespace[
            "_guidance_change_lines_for_updates"
        ]
        _guidance_item = namespace["_guidance_item"]
        _log_shear_top_guidance_recommendation = namespace[
            "_log_shear_top_guidance_recommendation"
        ]
        _next_tighter_link_spacing_updates = namespace[
            "_next_tighter_link_spacing_updates"
        ]
        _overall_status_from_rows = namespace["_overall_status_from_rows"]
        _parse_util_value = namespace["_parse_util_value"]
        _shear_guidance_item_from_search_rec = namespace[
            "_shear_guidance_item_from_search_rec"
        ]
        _shear_no_demand_cleanup_guidance_item_if_needed = namespace[
            "_shear_no_demand_cleanup_guidance_item_if_needed"
        ]
        _shear_spacing_guidance_floor_mm = namespace[
            "_shear_spacing_guidance_floor_mm"
        ]
        _shear_state_label = namespace["_shear_state_label"]
        _updates_match_state = namespace["_updates_match_state"]
    goal = _design_optimisation_goal(state)
    rows = pack.get("rows") or []
    util = _parse_util_value(pack.get("summary_util"))
    status, _ = _overall_status_from_rows(rows)
    bucket = _guidance_bucket(status, util)

    def _emit(
        item: dict,
        *,
        branch: str,
        proposed_updates: dict | None = None,
        expected_util_after: float | None = None,
        search_label: str | None = None,
    ) -> dict:
        _log_shear_top_guidance_recommendation(
            state,
            branch=branch,
            item=item,
            proposed_updates=proposed_updates,
            expected_util_after=expected_util_after,
            search_label=search_label,
        )
        return item

    if bucket == "fail":
        search_rec = _compute_shear_recommendation(state)
        if (
            search_rec
            and search_rec.get("updates")
            and not _updates_match_state(state, search_rec["updates"])
        ):
            item = _shear_guidance_item_from_search_rec(
                title="Shear governs",
                rec=search_rec,
                util=util,
                status=status,
                state=state,
            )
            return _emit(
                item,
                branch="fail:search",
                proposed_updates=dict(search_rec.get("updates") or {}),
                expected_util_after=float(search_rec.get("util", 0.0) or 0.0),
                search_label=str(search_rec.get("label") or ""),
            )

        if goal == "less_shear_reinforcement":
            geo_item = _shear_item_from_geometry_trials(
                state,
                title="Shear governs",
                status=status,
                util=util,
                secondary="Alternative: add link legs / diameter if geometry is fixed",
                reasoning_fallback="Why: a deeper section can relieve shear demand and avoid congested links.",
                levers="Key levers: D, link spacing, no. of legs",
                default_depth_delta=100.0,
                branch="fail:less_shear_geom",
                _emit=_emit,
            )
            if geo_item:
                return geo_item

        spacing_updates = _next_tighter_link_spacing_updates(state)
        if spacing_updates:
            item = _guidance_item(
                "shear",
                "Shear governs",
                "Tighten link spacing (next standard increment)",
                f"Trial: {_shear_state_label({**state, **spacing_updates})}",
                "Why: closer stirrup spacing increases shear capacity along the member.",
                "Key levers: link spacing, no. of legs, link diameter",
                "reduce_link_spacing",
                {
                    "updates": spacing_updates,
                    "delta_mm": 50,
                    "minimum_spacing": _shear_spacing_guidance_floor_mm(),
                },
                status=status,
                util=util,
            )
            return _emit(item, branch="fail:spacing_step", proposed_updates=spacing_updates)

        fu = _fallback_shear_reinforcement_step_updates(state)
        if fu:
            trial_state = dict(state)
            trial_state.update(fu)
            item = _guidance_item(
                "shear",
                "Shear governs",
                "Increase link legs or bar diameter",
                f"Trial: {_shear_state_label(trial_state)}",
                "Why: link spacing is already at the minimum spacing used in this guide; stronger stirrups are the next practical step.",
                "Key levers: no. of legs, link diameter, spacing, b, D",
                "apply_shear_recommendation",
                {"updates": fu},
                status=status,
                util=util,
            )
            return _emit(item, branch="fail:fallback_reo", proposed_updates=fu)

        geo_item = _shear_item_from_geometry_trials(
            state,
            title="Shear governs",
            status=status,
            util=util,
            secondary="Alternative: increase link legs / diameter if geometry is fixed",
            reasoning_fallback="Why: spacing and standard link upgrades are exhausted at the current geometry; section size is the next structural lever.",
            levers="Key levers: D, b, link layout",
            default_depth_delta=100.0,
            branch="fail:depth_fallback",
            _emit=_emit,
        )
        if geo_item:
            return geo_item

        return None

    if bucket == "warn":
        search_rec = _compute_shear_recommendation(state)
        if (
            search_rec
            and search_rec.get("updates")
            and not _updates_match_state(state, search_rec["updates"])
        ):
            item = _shear_guidance_item_from_search_rec(
                title="Shear is close to the limit",
                rec=search_rec,
                util=util,
                status=status,
                state=state,
            )
            return _emit(
                item,
                branch="warn:search",
                proposed_updates=dict(search_rec.get("updates") or {}),
                expected_util_after=float(search_rec.get("util", 0.0) or 0.0),
                search_label=str(search_rec.get("label") or ""),
            )

        if goal == "less_shear_reinforcement":
            geo_item = _shear_item_from_geometry_trials(
                state,
                title="Shear is close to the limit",
                status=status,
                util=util,
                secondary="Alternative: add link legs / diameter if geometry is fixed",
                reasoning_fallback="Why: modest depth can add reserve before tightening links.",
                levers="Key levers: D, link spacing, no. of legs",
                default_depth_delta=50.0,
                branch="warn:less_shear_geom",
                _emit=_emit,
            )
            if geo_item:
                return geo_item

        spacing_updates = _next_tighter_link_spacing_updates(state)
        if spacing_updates:
            item = _guidance_item(
                "shear",
                "Shear is close to the limit",
                "Tighten link spacing (next standard increment)",
                f"Trial: {_shear_state_label({**state, **spacing_updates})}",
                "Why: closer stirrup spacing adds reserve while keeping the beam shallow.",
                "Key levers: link spacing, no. of legs, link diameter",
                "reduce_link_spacing",
                {
                    "updates": spacing_updates,
                    "delta_mm": 25,
                    "minimum_spacing": _shear_spacing_guidance_floor_mm(),
                },
                status=status,
                util=util,
            )
            return _emit(item, branch="warn:spacing_step", proposed_updates=spacing_updates)

        fu = _fallback_shear_reinforcement_step_updates(state)
        if fu:
            trial_state = dict(state)
            trial_state.update(fu)
            item = _guidance_item(
                "shear",
                "Shear is close to the limit",
                "Increase link legs or bar diameter",
                f"Trial: {_shear_state_label(trial_state)}",
                "Why: link spacing is already at the minimum spacing used in this guide; stronger stirrups add reserve.",
                "Key levers: no. of legs, link diameter, spacing, b, D",
                "apply_shear_recommendation",
                {"updates": fu},
                status=status,
                util=util,
            )
            return _emit(item, branch="warn:fallback_reo", proposed_updates=fu)

        geo_item = _shear_item_from_geometry_trials(
            state,
            title="Shear is close to the limit",
            status=status,
            util=util,
            secondary="Alternative: increase link legs / diameter if geometry is fixed",
            reasoning_fallback="Why: link spacing is at the practical minimum in this guide; section size adds capacity without further congestion.",
            levers="Key levers: D, b, link layout",
            default_depth_delta=50.0,
            branch="warn:depth_fallback",
            _emit=_emit,
        )
        if geo_item:
            return geo_item

        return None

    cleanup_gi = _shear_no_demand_cleanup_guidance_item_if_needed(state)
    if cleanup_gi is not None:
        return cleanup_gi
    return None


__all__ = [
    "bind_shear_guidance_dependencies",
    "_shear_item_from_geometry_trials",
    "_shear_guidance_item",
]
