"""Crack-control guidance item coordination for the Inputs page Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


_CRACK_GUIDANCE_DEPENDENCIES: tuple[str, ...] = (
    "REO_SPACINGS",
    "_describe_guidance_step",
    "_evaluate_crack_with_state",
    "_guidance_bucket",
    "_guidance_item",
    "_merge_guidance_state",
    "_overall_status_from_rows",
    "_parse_util_value",
    "_pick_crack_ladder_first_improvement",
)


@dataclass(frozen=True)
class CrackGuidanceRuntime:
    reo_spacings: tuple[float, ...]
    describe_guidance_step: Callable[..., Any]
    evaluate_crack_with_state: Callable[..., Any]
    guidance_bucket: Callable[..., Any]
    guidance_item: Callable[..., Any]
    merge_guidance_state: Callable[..., Any]
    overall_status_from_rows: Callable[..., Any]
    parse_util_value: Callable[..., Any]
    pick_crack_ladder_first_improvement: Callable[..., Any]


@dataclass(frozen=True)
class CrackLadderRuntime:
    reo_counts: tuple[int, ...]
    reo_spacings: tuple[float, ...]
    ladder_early_stop_util: float
    arrangement_fits_state: Callable[..., Any]
    bottom_arrangement_to_shared_updates: Callable[..., Any]
    choose_geometry_trial_for_metric: Callable[..., Any]
    evaluate_crack_with_state: Callable[..., Any]
    guidance_action_updates: Callable[..., Any]
    log_guidance_ladder_debug: Callable[..., Any]
    merge_guidance_state: Callable[..., Any]
    updates_match_state: Callable[..., Any]


def _pick_crack_ladder_first_improvement(
    state: dict,
    *,
    base_util: float,
    runtime: CrackLadderRuntime,
) -> dict | None:
    ladder_name = "crack_ladder"

    def try_candidate(label: str, updates: dict | None) -> dict | None:
        def debug(
            decision: str,
            reason: str,
            metric_after: float | None,
            *,
            early_stop: bool = False,
        ) -> None:
            runtime.log_guidance_ladder_debug(
                ladder_name,
                candidate_label=label,
                candidate_updates=updates,
                decision=decision,
                reason=reason,
                metric_name="crack_util",
                metric_before=base_util,
                metric_after=metric_after,
                early_stop=early_stop,
            )

        if not updates:
            debug("rejected", "empty_updates", None)
            return None
        if runtime.updates_match_state(state, updates):
            debug("rejected", "noop_vs_state", None)
            return None
        evaluation = runtime.evaluate_crack_with_state(
            runtime.merge_guidance_state(state, updates)
        )
        if not evaluation:
            debug("rejected", "crack_eval_none", None)
            return None
        util_after = float(evaluation.get("util", 0.0) or 0.0)
        if util_after >= base_util - 1e-9:
            debug("rejected", "no_improvement", util_after)
            return None
        early = (
            util_after <= runtime.ladder_early_stop_util
            and util_after <= 1.0 + 1e-9
        )
        debug("accepted", "improves_crack_util", util_after, early_stop=early)
        return {
            "label": label,
            "updates": dict(updates),
            "util_after": util_after,
            "early_stop": early,
        }

    if str(state.get("bot1_layout_mode", "Count") or "Count") == "Spacing":
        updates = runtime.guidance_action_updates(
            "reduce_bar_spacing",
            {
                "delta_mm": 25.0,
                "minimum_spacing": float(min(runtime.reo_spacings)),
            },
            state=state,
        )
        result = try_candidate("Tighten bottom bar spacing (one step)", updates)
        if result:
            result["kind"] = "bottom_explicit"
            return result

    count_1 = int(state.get("bot1_count", 4) or 4)
    count_2 = int(state.get("bot2_count", 0) or 0)
    diameter_1 = int(state.get("db_bot_1", 20) or 20)
    diameter_2 = int(
        state.get("db_bot_2", state.get("db_bot_1", 20))
        or state.get("db_bot_1", 20)
    )
    updates = None
    if count_1 < max(runtime.reo_counts):
        updates = runtime.bottom_arrangement_to_shared_updates(
            {
                "bot1_count": count_1 + 1,
                "bot2_count": count_2,
                "db_bot_1": diameter_1,
                "db_bot_2": diameter_2,
            }
        )
        if updates and runtime.updates_match_state(state, updates):
            updates = None
    if updates is None and count_2 < max(runtime.reo_counts):
        updates = runtime.bottom_arrangement_to_shared_updates(
            {
                "bot1_count": count_1,
                "bot2_count": count_2 + 1,
                "db_bot_1": diameter_1,
                "db_bot_2": diameter_2,
            }
        )
        if updates and runtime.updates_match_state(state, updates):
            updates = None
    result = try_candidate("Add one bottom bar", updates)
    if result:
        result["kind"] = "bottom_explicit"
        return result

    updates = None
    if count_2 > 0 and count_1 > 0 and diameter_1 == diameter_2:
        merged = {
            "bot1_count": count_1 + count_2,
            "bot2_count": 0,
            "db_bot_1": diameter_1,
            "db_bot_2": diameter_1,
        }
        if runtime.arrangement_fits_state(state, merged):
            updates = runtime.bottom_arrangement_to_shared_updates(merged)
            if updates and runtime.updates_match_state(state, updates):
                updates = None
    result = try_candidate(
        "Consolidate bottom bars into one row (same total bars)",
        updates,
    )
    if result:
        result["kind"] = "bottom_explicit"
        return result

    geometry = runtime.choose_geometry_trial_for_metric(
        state,
        metric="crack",
        baseline_util=base_util,
        ladder_name="crack_geometry_trials",
    )
    if not geometry:
        return None
    return {
        "kind": "geometry",
        "label": geometry["label"],
        "action_type": geometry["action_type"],
        "payload": geometry["payload"],
        "updates": geometry["updates"],
        "util_after": geometry["util_after"],
        "before_after": geometry.get("before_after"),
    }


def bind_crack_guidance_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _CRACK_GUIDANCE_DEPENDENCIES
            if name in namespace
        }
    )


def _crack_guidance_item(
    state: dict,
    pack: dict,
    *,
    runtime: CrackGuidanceRuntime | None = None,
) -> dict | None:
    if runtime is not None:
        REO_SPACINGS = runtime.reo_spacings
        _describe_guidance_step = runtime.describe_guidance_step
        _evaluate_crack_with_state = runtime.evaluate_crack_with_state
        _guidance_bucket = runtime.guidance_bucket
        _guidance_item = runtime.guidance_item
        _merge_guidance_state = runtime.merge_guidance_state
        _overall_status_from_rows = runtime.overall_status_from_rows
        _parse_util_value = runtime.parse_util_value
        _pick_crack_ladder_first_improvement = (
            runtime.pick_crack_ladder_first_improvement
        )
    else:
        namespace = globals()
        REO_SPACINGS = namespace["REO_SPACINGS"]
        _describe_guidance_step = namespace["_describe_guidance_step"]
        _evaluate_crack_with_state = namespace[
            "_evaluate_crack_with_state"
        ]
        _guidance_bucket = namespace["_guidance_bucket"]
        _guidance_item = namespace["_guidance_item"]
        _merge_guidance_state = namespace["_merge_guidance_state"]
        _overall_status_from_rows = namespace["_overall_status_from_rows"]
        _parse_util_value = namespace["_parse_util_value"]
        _pick_crack_ladder_first_improvement = namespace[
            "_pick_crack_ladder_first_improvement"
        ]
    rows = pack.get("rows") or []
    util_candidates = [_parse_util_value(r.get("util")) for r in rows]
    util_values = [u for u in util_candidates if u is not None]
    util = max(util_values) if util_values else None
    status, _ = _overall_status_from_rows(rows)
    bucket = _guidance_bucket(status, util)
    if bucket not in ("fail", "warn"):
        return None
    base = _evaluate_crack_with_state(state)
    if not base:
        return None
    base_u = float(base.get("util", 0.0) or 0.0)
    picked = _pick_crack_ladder_first_improvement(state, base_util=base_u)
    if not picked:
        return None
    u_after = float(picked.get("util_after", 0.0) or 0.0)
    kind = str(picked.get("kind") or "")
    is_fail = bucket == "fail"
    title = "Crack control is failing" if is_fail else "Crack control is close to the limit"
    secondary = "Alternative: review cover and exposure inputs on the Crack page."
    levers = "Key levers: bar spacing, bar count, layout, cover, b, D"
    if kind == "geometry":
        reasoning = (
            f"Why: crack ladder — reinforcement and layout first, then best geometry trial (utilisation {util:.2f} → {u_after:.2f})."
            if util is not None
            else f"Why: geometry trial improves crack utilisation to {u_after:.2f}."
        )
        return _guidance_item(
            "crack",
            title,
            str(picked.get("label") or "Increase section size"),
            secondary,
            reasoning,
            levers,
            str(picked.get("action_type") or "increase_depth"),
            dict(picked.get("payload") or {}),
            status=status,
            util=util,
            guidance_before_after=str(picked.get("before_after") or "") or None,
        )
    updates = dict(picked.get("updates") or {})
    after_st = _merge_guidance_state(state, updates)
    ba = _describe_guidance_step(state, after_st, "reduce_bar_spacing", updates)
    reasoning = (
        f"Why: crack ladder — spacing, bar count, then crack-efficient layout before geometry ({util:.2f} → {u_after:.2f})."
        if util is not None
        else f"Why: crack-control ladder step ({u_after:.2f})."
    )
    return _guidance_item(
        "crack",
        title,
        str(picked.get("label") or "Adjust bottom reinforcement"),
        secondary,
        reasoning,
        levers,
        "reduce_bar_spacing",
        {"updates": updates, "delta_mm": 25.0, "minimum_spacing": float(min(REO_SPACINGS))},
        status=status,
        util=util,
        guidance_before_after=ba or None,
    )
