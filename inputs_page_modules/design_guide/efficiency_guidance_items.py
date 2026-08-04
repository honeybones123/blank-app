"""Efficiency guidance item coordination for the Inputs page Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


_EFFICIENCY_GUIDANCE_ITEM_DEPENDENCIES: tuple[str, ...] = (
    "GUIDANCE_INEFFICIENT_UTIL_THRESHOLD",
    "GUIDANCE_TARGET_UTIL_MAX",
    "GUIDANCE_TARGET_UTIL_MIN",
    "GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL",
    "_bending_demands_negligible",
    "_can_emit_efficiency_terminal_state",
    "_design_optimisation_goal",
    "_evaluate_auto_design_candidate",
    "_geometry_lock_enabled",
    "_guidance_item",
    "_guidance_item_is_resolved_one_click",
    "_guidance_objective_util_from_overview",
    "_is_design_guide_good_utilisation_band",
    "_mode_recommendation_expected_bend_util",
    "_promote_guidance_item_to_resolved_candidate",
    "_resolve_design_actions_from_state",
    "_resolved_shear_cleanup_is_executor_safe",
)


@dataclass(frozen=True)
class EfficiencyGuidanceRuntime:
    guidance_inefficient_util_threshold: float
    guidance_target_util_max: float
    guidance_target_util_min: float
    guidance_undersized_done_block_util: float
    bending_demands_negligible: Callable[..., Any]
    can_emit_efficiency_terminal_state: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    evaluate_auto_design_candidate: Callable[..., Any]
    geometry_lock_enabled: Callable[..., Any]
    guidance_item: Callable[..., Any]
    guidance_item_is_resolved_one_click: Callable[..., Any]
    guidance_objective_util_from_overview: Callable[..., Any]
    is_design_guide_good_utilisation_band: Callable[..., Any]
    mode_recommendation_expected_bend_util: Callable[..., Any]
    promote_guidance_item_to_resolved_candidate: Callable[..., Any]
    resolve_design_actions_from_state: Callable[..., Any]
    resolved_shear_cleanup_is_executor_safe: Callable[..., Any]


def _bind_efficiency_guidance_runtime(
    runtime: EfficiencyGuidanceRuntime,
) -> None:
    globals().update(
        {
            "GUIDANCE_INEFFICIENT_UTIL_THRESHOLD": runtime.guidance_inefficient_util_threshold,
            "GUIDANCE_TARGET_UTIL_MAX": runtime.guidance_target_util_max,
            "GUIDANCE_TARGET_UTIL_MIN": runtime.guidance_target_util_min,
            "GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL": runtime.guidance_undersized_done_block_util,
            "_bending_demands_negligible": runtime.bending_demands_negligible,
            "_can_emit_efficiency_terminal_state": runtime.can_emit_efficiency_terminal_state,
            "_design_optimisation_goal": runtime.design_optimisation_goal,
            "_evaluate_auto_design_candidate": runtime.evaluate_auto_design_candidate,
            "_geometry_lock_enabled": runtime.geometry_lock_enabled,
            "_guidance_item": runtime.guidance_item,
            "_guidance_item_is_resolved_one_click": runtime.guidance_item_is_resolved_one_click,
            "_guidance_objective_util_from_overview": runtime.guidance_objective_util_from_overview,
            "_is_design_guide_good_utilisation_band": runtime.is_design_guide_good_utilisation_band,
            "_mode_recommendation_expected_bend_util": runtime.mode_recommendation_expected_bend_util,
            "_promote_guidance_item_to_resolved_candidate": runtime.promote_guidance_item_to_resolved_candidate,
            "_resolve_design_actions_from_state": runtime.resolve_design_actions_from_state,
            "_resolved_shear_cleanup_is_executor_safe": runtime.resolved_shear_cleanup_is_executor_safe,
        }
    )


def bind_efficiency_guidance_item_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _EFFICIENCY_GUIDANCE_ITEM_DEPENDENCIES
            if name in namespace
        }
    )


def _efficiency_guidance_items(
    state: dict,
    efficiency_state: dict,
    *,
    runtime: EfficiencyGuidanceRuntime | None = None,
) -> list[dict]:
    if runtime is not None:
        _bind_efficiency_guidance_runtime(runtime)
    if str(efficiency_state.get("classification") or "") == "optimal":
        return []
    if str(efficiency_state.get("classification") or "") == "very_low_demand":
        return []
    eligible = bool(
        efficiency_state.get("conservative")
        or (
            bool(efficiency_state.get("efficiency_moves_ok"))
            and efficiency_state.get("shear_tightening") is not None
        )
    )
    if not eligible:
        return []

    target_lo = float(efficiency_state.get("target_band_lo", GUIDANCE_TARGET_UTIL_MIN) or GUIDANCE_TARGET_UTIL_MIN)
    target_hi = float(efficiency_state.get("target_band_hi", GUIDANCE_TARGET_UTIL_MAX) or GUIDANCE_TARGET_UTIL_MAX)
    safe_cleanup_mode_active = bool(efficiency_state.get("optimisation_safe_cleanup_mode_active"))
    efficiency_state["target_efficiency_band"] = [target_lo, target_hi]
    efficiency_state.setdefault("terminal_state_blocked", False)
    efficiency_state.setdefault("terminal_state_block_reason", None)

    goal = _design_optimisation_goal(state)
    items: list[dict] = []
    utils = efficiency_state["overview"]["utils"]
    mode_tighten = efficiency_state.get("mode_tightening")
    bottom_tighten = efficiency_state.get("bottom_tightening")
    shear_tighten = efficiency_state.get("shear_tightening")
    geometry_tighten = efficiency_state.get("geometry_tightening")
    shear_relevant = bool(efficiency_state.get("shear_relevant"))
    shear_cleanup_possible = bool(efficiency_state.get("shear_cleanup_possible"))
    bending_util_now = utils.get("bending")
    actions = dict(
        efficiency_state.get("actions_used")
        or _resolve_design_actions_from_state(state)
        or {}
    )
    shear_executor_candidate: dict | None = None
    shear_executor_primary_eligible = False
    if isinstance(shear_tighten, dict) and dict(shear_tighten.get("updates") or {}):
        try:
            _candidate_probe = dict(shear_tighten.get("resolved_candidate") or {})
            if not _candidate_probe:
                _candidate_probe = _evaluate_auto_design_candidate(
                    state,
                    updates=dict(shear_tighten.get("updates") or {}),
                    source="guidance_shear_executor_backed",
                    label=str(shear_tighten.get("label") or "Adjust shear reinforcement"),
                    action_type=str(shear_tighten.get("action_type") or "apply_shear_recommendation"),
                ) or {}
            if isinstance(_candidate_probe, dict) and _candidate_probe:
                _candidate_probe["updates"] = dict(
                    _candidate_probe.get("updates")
                    or shear_tighten.get("resolved_candidate_updates")
                    or shear_tighten.get("updates")
                    or {}
                )
                _candidate_probe["action_type"] = str(
                    shear_tighten.get("resolved_candidate_action_type")
                    or shear_tighten.get("action_type")
                    or _candidate_probe.get("action_type")
                    or "apply_shear_recommendation"
                ).strip()
                _candidate_probe["label"] = str(
                    shear_tighten.get("resolved_candidate_label")
                    or shear_tighten.get("label")
                    or _candidate_probe.get("label")
                    or "Adjust shear reinforcement"
                ).strip()
                _candidate_probe["candidate_post_util"] = (
                    shear_tighten.get("resolved_candidate_post_util")
                    if shear_tighten.get("resolved_candidate_post_util") is not None
                    else _candidate_probe.get("candidate_post_util", _candidate_probe.get("worst_util"))
                )
                _candidate_probe["candidate_reaches_target_band"] = bool(
                    shear_tighten.get("resolved_candidate_reaches_target_band")
                    if shear_tighten.get("resolved_candidate_reaches_target_band") is not None
                    else (
                        _candidate_probe.get("candidate_reaches_target_band")
                        or _candidate_probe.get("reaches_target_band")
                    )
                )
                if _resolved_shear_cleanup_is_executor_safe(
                    {
                        "action_payload": {"resolved_candidate_updates": dict(_candidate_probe.get("updates") or {})},
                        "resolved_candidate": _candidate_probe,
                        "action_type": str(_candidate_probe.get("action_type") or "apply_shear_recommendation"),
                        "bucket": "efficiency",
                    },
                    state=state,
                    overview=efficiency_state["overview"],
                ):
                    shear_executor_candidate = _candidate_probe
                    shear_executor_primary_eligible = bool(
                        _bending_demands_negligible(actions)
                        or _is_design_guide_good_utilisation_band(bending_util_now)
                    )
        except Exception:
            shear_executor_candidate = None
            shear_executor_primary_eligible = False

    if mode_tighten and not safe_cleanup_mode_active:
        expected_bend_util = _mode_recommendation_expected_bend_util(mode_tighten)
        if expected_bend_util is None:
            expected_bend_util = _guidance_objective_util_from_overview(efficiency_state["overview"], goal)
        focus = str(mode_tighten.get("focus") or "general")
        title = "Design can be tightened"
        if focus == "geometry":
            title = "Section reserve is high"
        elif focus == "bending":
            title = "Bending reserve is high"
        elif focus == "shear":
            title = "Shear reserve is high"

        if goal == "shallower_beam":
            primary = "Apply recommendation"
            reasoning = "Why: the current design has reserve, and the next recommendation trials a shallower practical section while staying compliant."
        elif goal == "less_longitudinal_reinforcement":
            primary = "Apply recommendation"
            reasoning = "Why: the current design has reserve, and the next recommendation simplifies bottom reinforcement before any broader section change."
        elif goal == "less_shear_reinforcement":
            primary = "Apply recommendation"
            reasoning = "Why: the current design has reserve, and the next recommendation reduces shear demand in the direction of the selected optimisation goal."
        else:
            primary = "Apply recommendation"
            reasoning = "Why: the current design passes comfortably, so the next recommendation moves it toward the preferred practical utilisation band."

        levers = "Key levers: depth D, section width, reinforcement layout, target utilisation band"
        if focus == "bending":
            levers = f"Key levers: bottom reinforcement, arrangement, target utilisation band {target_lo:.2f}-{target_hi:.2f}"
        elif focus == "shear":
            levers = f"Key levers: link spacing, number of legs, target utilisation band {target_lo:.2f}-{target_hi:.2f}"
        elif focus == "geometry":
            levers = f"Key levers: depth D, section width, target utilisation band {target_lo:.2f}-{target_hi:.2f}"

        items.append(
            _guidance_item(
                focus,
                title,
                primary,
                f"Recommended improvement: {mode_tighten['label']}.",
                reasoning,
                levers,
                "apply_mode_recommendation",
                dict(mode_tighten),
                status="EFFICIENCY",
                util=expected_bend_util,
            )
        )
        efficiency_state["terminal_state_blocked"] = False
        efficiency_state["terminal_state_block_reason"] = None
        reserve_for_shear_alongside_mode = bool(
            efficiency_state.get("shear_overdesign_reserve_guidance_eligible")
            or shear_executor_primary_eligible
        )
        if not reserve_for_shear_alongside_mode:
            efficiency_state["mode_guidance_return_blocked_for_shear_reserve"] = False
            efficiency_state["efficiency_guidance_items_summary"] = [
                {"title_main": i.get("title_main"), "action_type": i.get("action_type")}
                for i in items
                if isinstance(i, dict)
            ]
            return items
        efficiency_state["mode_guidance_return_blocked_for_shear_reserve"] = True

    show_geometry_tighten = bool(geometry_tighten) and goal in ("balanced", "shallower_beam")
    if goal == "less_longitudinal_reinforcement" and geometry_tighten and not bottom_tighten:
        show_geometry_tighten = True

    if show_geometry_tighten and goal == "shallower_beam":
        items.append(
            _guidance_item(
                "geometry",
                "Section reserve is high",
                "Reduce beam depth while staying compliant",
                f"Alternative: trial {geometry_tighten['label']}.",
                "Why: the selected goal prefers a shallower section, and the current reserve is high enough to tighten geometry first.",
                f"Key levers: depth D, section width, target utilisation band {target_lo:.2f}-{target_hi:.2f}",
                "tighten_geometry",
                {"updates": geometry_tighten["updates"]},
                status="EFFICIENCY",
                util=efficiency_state["overview"]["worst_util"],
            )
        )

    if bottom_tighten and utils.get("bending") is not None and utils["bending"] <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD:
        if goal == "less_longitudinal_reinforcement":
            primary = "Reduce bottom reinforcement slightly"
            reasoning = "Why: bottom steel reserve is high, so you can tighten the design toward a more efficient utilisation band."
        elif goal == "shallower_beam":
            primary = "Trim bottom reinforcement while preserving beam depth"
            reasoning = "Why: the beam passes comfortably, so steel can be reduced before changing the shallower geometry."
        else:
            primary = "Design is conservative. Reduce bottom reinforcement."
            reasoning = "Why: bending reserve is high and can be tightened toward a practical utilisation band."
        items.append(
            _guidance_item(
                "bending",
                "Bending reserve is high",
                primary,
                "Alternative: tighten to an efficient practical design.",
                reasoning,
                f"Key levers: bottom reinforcement, arrangement, target utilisation band {target_lo:.2f}-{target_hi:.2f}",
                "reduce_bottom_reinforcement",
                {"updates": bottom_tighten["arrangement"]},
                status="EFFICIENCY",
                util=utils["bending"],
            )
        )

    if show_geometry_tighten and goal != "shallower_beam":
        if goal == "less_longitudinal_reinforcement":
            primary = "Trim section size only if reinforcement is already practical"
            reasoning = "Why: this goal still prefers simpler reinforcement first, but the section can also be tightened when reserve remains high."
        else:
            primary = "Section reserve is high. Trim the beam slightly."
            reasoning = "Why: after checking steel efficiency, a smaller section can move the beam closer to the target utilisation band."
        items.append(
            _guidance_item(
                "geometry",
                "Section reserve is high",
                primary,
                f"Alternative: trial {geometry_tighten['label']}.",
                reasoning,
                f"Key levers: depth D, section width, target utilisation band {target_lo:.2f}-{target_hi:.2f}",
                "tighten_geometry",
                {"updates": geometry_tighten["updates"]},
                status="EFFICIENCY",
                util=efficiency_state["overview"]["worst_util"],
            )
        )

    if shear_tighten and (
        (utils.get("shear") is not None and utils["shear"] <= GUIDANCE_INEFFICIENT_UTIL_THRESHOLD)
        or shear_cleanup_possible
        or safe_cleanup_mode_active
    ):
        if not shear_relevant and shear_cleanup_possible:
            title = "Shear reinforcement can likely be reduced"
            primary = "Shear reinforcement can likely be reduced"
            reasoning = "Why: shear demand is non-critical, but ligatures are still present and can likely be relaxed safely."
        elif goal == "less_shear_reinforcement":
            title = "Shear reserve is high"
            primary = "Shear reserve is high. Reduce ligature demand."
            reasoning = "Why: the current links are more conservative than needed for the selected goal."
        elif goal == "shallower_beam":
            title = "Shear reserve is high"
            primary = "Ease shear reinforcement before changing geometry"
            reasoning = "Why: the beam already passes comfortably, so link demand can be tightened while keeping depth."
        else:
            title = "Shear reserve is high"
            primary = "Shear reserve is high. Increase link spacing."
            reasoning = "Why: shear capacity reserve is comfortably above demand."
        secondary = (
            f"Alternative: use {shear_tighten['label']}."
            if shear_tighten.get("action_type") == "reduce_number_of_legs"
            else "Alternative: reduce the number of legs if spacing is already practical."
        )
        shear_item = _guidance_item(
            "shear",
            title,
            primary,
            secondary,
            reasoning,
            f"Key levers: link spacing, number of legs, target utilisation band {target_lo:.2f}-{target_hi:.2f}",
            shear_tighten["action_type"],
            {"updates": shear_tighten["updates"]},
            status="EFFICIENCY",
            util=utils["shear"],
        )
        shear_resolved_candidate = dict(shear_executor_candidate or shear_tighten.get("resolved_candidate") or {})
        if not shear_resolved_candidate:
            try:
                shear_resolved_candidate = _evaluate_auto_design_candidate(
                    state,
                    updates=dict(shear_tighten.get("updates") or {}),
                    source="guidance_shear_executor_backed",
                    label=str(shear_tighten.get("label") or title),
                    action_type=str(shear_tighten.get("action_type") or "apply_shear_recommendation"),
                ) or {}
            except Exception:
                shear_resolved_candidate = {}
        if isinstance(shear_resolved_candidate, dict) and shear_resolved_candidate:
            shear_resolved_candidate["updates"] = dict(
                shear_resolved_candidate.get("updates")
                or shear_tighten.get("resolved_candidate_updates")
                or shear_tighten.get("updates")
                or {}
            )
            shear_resolved_candidate["action_type"] = str(
                shear_tighten.get("resolved_candidate_action_type")
                or shear_tighten.get("action_type")
                or shear_resolved_candidate.get("action_type")
                or "apply_shear_recommendation"
            ).strip()
            shear_resolved_candidate["label"] = str(
                shear_tighten.get("resolved_candidate_label")
                or shear_tighten.get("label")
                or shear_resolved_candidate.get("label")
                or title
            ).strip()
            shear_resolved_candidate["candidate_post_util"] = (
                shear_tighten.get("resolved_candidate_post_util")
                if shear_tighten.get("resolved_candidate_post_util") is not None
                else shear_resolved_candidate.get("candidate_post_util", shear_resolved_candidate.get("worst_util"))
            )
            shear_resolved_candidate["candidate_reaches_target_band"] = bool(
                shear_tighten.get("resolved_candidate_reaches_target_band")
                if shear_tighten.get("resolved_candidate_reaches_target_band") is not None
                else (
                    shear_resolved_candidate.get("candidate_reaches_target_band")
                    or shear_resolved_candidate.get("reaches_target_band")
                )
            )
            if _resolved_shear_cleanup_is_executor_safe(
                {"action_payload": {"resolved_candidate_updates": dict(shear_resolved_candidate.get("updates") or {})},
                 "resolved_candidate": shear_resolved_candidate,
                 "action_type": str(shear_resolved_candidate.get("action_type") or "apply_shear_recommendation"),
                 "bucket": "efficiency"},
                state=state,
                overview=efficiency_state["overview"],
            ):
                promoted = _promote_guidance_item_to_resolved_candidate(
                    shear_item,
                    shear_resolved_candidate,
                    state=state,
                )
                if isinstance(promoted, dict):
                    shear_item = promoted
        force_actionable_shear_cleanup_primary = bool(
            shear_executor_primary_eligible
            and bool((efficiency_state.get("overview") or {}).get("all_key_pass"))
            and str(shear_item.get("action_type") or "").strip()
            and _guidance_item_is_resolved_one_click(shear_item)
            and _resolved_shear_cleanup_is_executor_safe(
                shear_item,
                state=state,
                overview=efficiency_state["overview"],
            )
        )
        if force_actionable_shear_cleanup_primary:
            trailing_items = [existing for existing in items if isinstance(existing, dict)]
            items = [shear_item] + trailing_items[:1]
            efficiency_state["surfaced_shear_reserve_item"] = True
            efficiency_state["forced_actionable_shear_cleanup_primary"] = True
            efficiency_state["efficiency_guidance_items_summary"] = [
                {"title_main": i.get("title_main"), "action_type": i.get("action_type")}
                for i in items
                if isinstance(i, dict)
            ]
            return items
        prefer_shear_primary = bool(
            _bending_demands_negligible(actions)
            or _is_design_guide_good_utilisation_band(bending_util_now)
        )
        if prefer_shear_primary and str(shear_item.get("action_type") or "").strip():
            items.insert(0, shear_item)
        else:
            items.append(shear_item)
        if bool(efficiency_state.get("mode_guidance_return_blocked_for_shear_reserve")):
            efficiency_state["surfaced_shear_reserve_item"] = True

    if safe_cleanup_mode_active and items:
        efficiency_state["efficiency_guidance_items_summary"] = [
            {"title_main": i.get("title_main"), "action_type": i.get("action_type")}
            for i in items
            if isinstance(i, dict)
        ]
        return items

    if not items:
        exhaust = dict(efficiency_state.get("exhaustion_map") or {})
        worst = float(efficiency_state["overview"].get("worst_util", 0) or 0)
        can_term, term_reason = _can_emit_efficiency_terminal_state(worst, exhaust)
        blocked = (not can_term) and worst < float(GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL)
        efficiency_state["terminal_state_blocked"] = blocked
        efficiency_state["terminal_state_block_reason"] = None if can_term else term_reason
        if not can_term and worst < float(GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL):
            items.append(
                _guidance_item(
                    "general",
                    "Section still underutilised",
                    "Further safe reductions are being explored",
                    "Optional: use the shear, bottom reinforcement, and geometry panels for on-demand reduction trials.",
                    (
                        "Why: worst utilisation is still below the practical target band, so the guide keeps "
                        "reduction-oriented guidance active instead of treating the design as finished."
                    ),
                    "Key levers: shear links, bottom steel, section geometry, target utilisation band",
                    None,
                    None,
                    status="EFFICIENCY",
                    util=worst,
                )
            )
        else:
            geometry_locked = _geometry_lock_enabled(state)
            title = "No further safe local reductions available"
            primary = "Critical case solved. Reducing non-critical provisions has reached a safe limit."
            if geometry_locked:
                title = "Geometry locked for optimisation"
                primary = "Geometry locked. Optimisation is limited to reinforcement/detailing changes."
            items.append(
                _guidance_item(
                    "general",
                    title,
                    primary,
                    "No further local reductions available without impacting the protected critical case.",
                    (
                        "Why: the governing case is being protected, and no remaining local cleanup move "
                        "can reduce non-critical provision while keeping all checks acceptable."
                    ),
                    "Key levers: protected critical case, local reinforcement/detailing, geometry lock",
                    None,
                    None,
                    status="EFFICIENCY",
                    util=efficiency_state["overview"]["worst_util"],
                )
            )

    efficiency_state["efficiency_guidance_items_summary"] = [
        {"title_main": i.get("title_main"), "action_type": i.get("action_type")}
        for i in items
        if isinstance(i, dict)
    ]
    return items


__all__ = [
    "bind_efficiency_guidance_item_dependencies",
    "_efficiency_guidance_items",
]
