"""Shear local-cleanup recommendation coordination for the Inputs page Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


_SHEAR_LOCAL_CLEANUP_DEPENDENCIES: tuple[str, ...] = (
    "CANONICAL_NO_SHEAR_SLIG_MM",
    "GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN",
    "_candidate_preview_statuses_have_explicit_fail",
    "_compute_shear_tightening_recommendation",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_distance_to_target_band",
    "_evaluate_auto_design_candidate",
    "_float_from_state",
    "_guidance_cleanup_candidate_id",
    "_guidance_item",
    "_one_click_domain_needs_cleanup",
    "_overview_required_checks_acceptable",
    "_post_click_accepted_green_audit",
    "_promote_guidance_item_to_resolved_candidate",
    "_resolved_efficiency_target_band",
    "_resolve_design_actions_from_state",
    "_shear_demands_negligible",
    "_shear_cleanup_materially_reduces_reinforcement",
    "_shear_reinforcement_is_active",
    "_updates_match_state",
)


@dataclass(frozen=True)
class ShearLocalCleanupRuntime:
    canonical_no_shear_spacing_mm: float
    shear_demand_abs_tol_kn: float
    candidate_preview_statuses_have_explicit_fail: Callable[..., Any]
    compute_shear_tightening_recommendation: Callable[..., Any]
    design_mode_config: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    distance_to_target_band: Callable[..., Any]
    evaluate_auto_design_candidate: Callable[..., Any]
    float_from_state: Callable[..., Any]
    guidance_cleanup_candidate_id: Callable[..., Any]
    guidance_item: Callable[..., Any]
    one_click_domain_needs_cleanup: Callable[..., Any]
    overview_required_checks_acceptable: Callable[..., Any]
    post_click_accepted_green_audit: Callable[..., Any]
    promote_guidance_item_to_resolved_candidate: Callable[..., Any]
    resolved_efficiency_target_band: Callable[..., Any]
    resolve_design_actions_from_state: Callable[..., Any]
    shear_demands_negligible: Callable[..., Any]
    shear_cleanup_materially_reduces_reinforcement: Callable[..., Any]
    shear_reinforcement_is_active: Callable[..., Any]
    updates_match_state: Callable[..., Any]


def _bind_shear_local_cleanup_runtime(
    runtime: ShearLocalCleanupRuntime,
) -> None:
    globals().update(
        {
            "CANONICAL_NO_SHEAR_SLIG_MM": runtime.canonical_no_shear_spacing_mm,
            "GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN": runtime.shear_demand_abs_tol_kn,
            "_candidate_preview_statuses_have_explicit_fail": runtime.candidate_preview_statuses_have_explicit_fail,
            "_compute_shear_tightening_recommendation": runtime.compute_shear_tightening_recommendation,
            "_design_mode_config": runtime.design_mode_config,
            "_design_optimisation_goal": runtime.design_optimisation_goal,
            "_distance_to_target_band": runtime.distance_to_target_band,
            "_evaluate_auto_design_candidate": runtime.evaluate_auto_design_candidate,
            "_float_from_state": runtime.float_from_state,
            "_guidance_cleanup_candidate_id": runtime.guidance_cleanup_candidate_id,
            "_guidance_item": runtime.guidance_item,
            "_one_click_domain_needs_cleanup": runtime.one_click_domain_needs_cleanup,
            "_overview_required_checks_acceptable": runtime.overview_required_checks_acceptable,
            "_post_click_accepted_green_audit": runtime.post_click_accepted_green_audit,
            "_promote_guidance_item_to_resolved_candidate": runtime.promote_guidance_item_to_resolved_candidate,
            "_resolved_efficiency_target_band": runtime.resolved_efficiency_target_band,
            "_resolve_design_actions_from_state": runtime.resolve_design_actions_from_state,
            "_shear_demands_negligible": runtime.shear_demands_negligible,
            "_shear_cleanup_materially_reduces_reinforcement": runtime.shear_cleanup_materially_reduces_reinforcement,
            "_shear_reinforcement_is_active": runtime.shear_reinforcement_is_active,
            "_updates_match_state": runtime.updates_match_state,
        }
    )


def bind_shear_local_cleanup_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SHEAR_LOCAL_CLEANUP_DEPENDENCIES
            if name in namespace
        }
    )


def _best_safe_shear_local_cleanup_recommendation(
    state: dict,
    overview: dict,
    first_recommendation: dict | None,
) -> dict | None:
    mode_cfg = _design_mode_config(_design_optimisation_goal(state))
    t_lo, t_hi, _ = _resolved_efficiency_target_band(mode_cfg, goal=_design_optimisation_goal(state))
    base_state = dict(state)
    working_state = dict(state)
    cumulative_updates: dict = {}
    best_rec: dict | None = None
    best_distance = float("inf")
    try:
        starting_worst = float(
            (overview or {}).get("worst_util")
            or (overview or {}).get("governing_util")
            or 0.0
        )
    except Exception:
        starting_worst = 0.0
    starting_below_target = bool(starting_worst < float(t_lo) - 1e-9)

    if not starting_below_target and isinstance(first_recommendation, dict):
        first_updates = dict(
            first_recommendation.get("updates")
            or first_recommendation.get("resolved_candidate_updates")
            or {}
        )
        if "s_lig" not in first_updates and "link_spacing" in first_updates:
            first_updates["s_lig"] = first_updates.get("link_spacing")
        current_spacing = _float_from_state(base_state, "s_lig", 0.0)
        next_spacing = _float_from_state({**base_state, **first_updates}, "s_lig", current_spacing)
        if next_spacing > current_spacing + 1e-9:
            best_spacing_rec: dict | None = None
            best_spacing_value = float(current_spacing)
            current_dia = int(_float_from_state(base_state, "lig_d", 0.0) or 0)
            current_legs = int(_float_from_state(base_state, "lig_legs", 0.0) or 0)
            spacing_values = [
                float(spacing)
                for spacing in (125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 375, 400)
                if float(spacing) > float(current_spacing) + 1e-9
            ]
            for spacing in spacing_values:
                spacing_updates = dict(first_updates)
                if current_dia > 0:
                    spacing_updates["lig_d"] = int(current_dia)
                if current_legs > 0:
                    spacing_updates["lig_legs"] = int(current_legs)
                spacing_updates["s_lig"] = float(spacing)
                trial_state = dict(base_state)
                trial_state.update(spacing_updates)
                if not _shear_cleanup_materially_reduces_reinforcement(base_state, trial_state):
                    continue
                try:
                    candidate = _evaluate_auto_design_candidate(
                        base_state,
                        updates=spacing_updates,
                        source="safe_local_shear_cleanup_final_spacing",
                        label=str(first_recommendation.get("label") or "Shear local cleanup"),
                        action_type=str(first_recommendation.get("action_type") or "apply_shear_recommendation"),
                    )
                except Exception:
                    candidate = None
                if not isinstance(candidate, dict):
                    continue
                candidate_overview = dict(candidate.get("overview") or {})
                if bool(candidate_overview.get("any_fail")) or not _overview_required_checks_acceptable(candidate_overview):
                    continue
                if _candidate_preview_statuses_have_explicit_fail(dict(candidate_overview.get("statuses") or {})):
                    continue
                try:
                    post_worst = float(candidate_overview.get("worst_util", candidate.get("worst_util", 0.0)) or 0.0)
                except Exception:
                    post_worst = 0.0
                if float(spacing) >= best_spacing_value - 1e-9:
                    best_spacing_value = float(spacing)
                    best_spacing_rec = {
                        **dict(first_recommendation),
                        "updates": dict(spacing_updates),
                        "resolved_candidate": {
                            **dict(candidate),
                            "updates": dict(spacing_updates),
                            "action_type": str(candidate.get("action_type") or first_recommendation.get("action_type") or "apply_shear_recommendation"),
                            "label": str(candidate.get("label") or first_recommendation.get("label") or "Shear local cleanup"),
                            "candidate_post_util": post_worst,
                            "candidate_reaches_target_band": bool(t_lo <= post_worst <= t_hi),
                        },
                        "resolved_candidate_updates": dict(spacing_updates),
                        "resolved_candidate_post_util": post_worst,
                        "resolved_candidate_reaches_target_band": bool(t_lo <= post_worst <= t_hi),
                    }
            if isinstance(best_spacing_rec, dict):
                no_links_updates = {
                    "lig_d": 0,
                    "lig_legs": 0,
                    "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
                }
                no_links_state = dict(base_state)
                no_links_state.update(no_links_updates)
                if (
                    not _updates_match_state(base_state, no_links_updates)
                    and _shear_cleanup_materially_reduces_reinforcement(base_state, no_links_state)
                ):
                    try:
                        no_links_candidate = _evaluate_auto_design_candidate(
                            base_state,
                            updates=no_links_updates,
                            source="safe_local_shear_cleanup_final_no_links",
                            label="Remove shear links",
                            action_type="apply_shear_recommendation",
                        )
                    except Exception:
                        no_links_candidate = None
                    if isinstance(no_links_candidate, dict):
                        no_links_overview = dict(no_links_candidate.get("overview") or {})
                        no_links_audit = _post_click_accepted_green_audit(
                            no_links_overview,
                            blocker_source={},
                            state=no_links_state,
                        )
                        try:
                            no_links_worst = float(
                                no_links_overview.get("worst_util", no_links_candidate.get("worst_util", 0.0))
                                or 0.0
                            )
                        except Exception:
                            no_links_worst = 0.0
                        if (
                            not bool(no_links_overview.get("any_fail"))
                            and _overview_required_checks_acceptable(no_links_overview)
                            and not _candidate_preview_statuses_have_explicit_fail(
                                dict(no_links_overview.get("statuses") or {})
                            )
                            and bool(t_lo <= no_links_worst <= t_hi)
                            and bool(no_links_audit.get("post_click_accepted_green_valid"))
                        ):
                            return {
                                **dict(first_recommendation),
                                "label": "Remove shear links",
                                "updates": dict(no_links_updates),
                                "resolved_candidate": {
                                    **dict(no_links_candidate),
                                    "updates": dict(no_links_updates),
                                    "action_type": "apply_shear_recommendation",
                                    "label": "Remove shear links",
                                    "candidate_post_util": no_links_worst,
                                    "candidate_reaches_target_band": True,
                                    "post_click_exact_blockers_by_family": dict(
                                        no_links_audit.get("post_click_exact_blockers_by_family") or {}
                                    ),
                                },
                                "resolved_candidate_updates": dict(no_links_updates),
                                "resolved_candidate_post_util": no_links_worst,
                                "resolved_candidate_reaches_target_band": True,
                                "post_click_exact_blockers_by_family": dict(
                                    no_links_audit.get("post_click_exact_blockers_by_family") or {}
                                ),
                            }
                best_spacing_updates = dict(
                    best_spacing_rec.get("updates")
                    or best_spacing_rec.get("resolved_candidate_updates")
                    or {}
                )
                best_spacing_overview = dict(
                    (best_spacing_rec.get("resolved_candidate") or {}).get("overview")
                    or {}
                )
                best_spacing_state = dict(base_state)
                best_spacing_state.update(best_spacing_updates)
                best_spacing_audit = _post_click_accepted_green_audit(
                    best_spacing_overview,
                    blocker_source=best_spacing_rec,
                    state=best_spacing_state,
                )
                if bool(best_spacing_audit.get("post_click_accepted_green_valid")):
                    return best_spacing_rec

    for step_idx in range(12):
        rec = first_recommendation if step_idx == 0 else None
        if not isinstance(rec, dict):
            try:
                rec = _compute_shear_tightening_recommendation(working_state, out_debug={})
            except Exception:
                rec = None
        if not isinstance(rec, dict):
            break
        step_updates = dict(rec.get("updates") or rec.get("resolved_candidate_updates") or {})
        if not step_updates:
            break
        next_cumulative = dict(cumulative_updates)
        next_cumulative.update(step_updates)
        if _updates_match_state(base_state, next_cumulative):
            break

        trial_state = dict(base_state)
        trial_state.update(next_cumulative)
        if not _shear_cleanup_materially_reduces_reinforcement(base_state, trial_state):
            break

        try:
            candidate = _evaluate_auto_design_candidate(
                base_state,
                updates=next_cumulative,
                source=f"safe_local_shear_cleanup_step_{step_idx + 1}",
                label=str(rec.get("label") or "Shear local cleanup"),
                action_type=str(rec.get("action_type") or "apply_shear_recommendation"),
            )
        except Exception:
            candidate = None
        if not isinstance(candidate, dict):
            break
        candidate_overview = dict(candidate.get("overview") or {})
        if bool(candidate_overview.get("any_fail")) or not _overview_required_checks_acceptable(candidate_overview):
            break
        if _candidate_preview_statuses_have_explicit_fail(dict(candidate_overview.get("statuses") or {})):
            break

        try:
            post_worst = float(candidate_overview.get("worst_util", candidate.get("worst_util", 0.0)) or 0.0)
        except Exception:
            post_worst = 0.0
        distance = _distance_to_target_band(post_worst, t_lo, t_hi)
        if distance <= best_distance + 1e-9:
            best_distance = distance
            best_rec = {
                **dict(rec),
                "updates": dict(next_cumulative),
                "resolved_candidate": {
                    **dict(candidate),
                    "updates": dict(next_cumulative),
                    "action_type": str(candidate.get("action_type") or rec.get("action_type") or "apply_shear_recommendation"),
                    "label": str(candidate.get("label") or rec.get("label") or "Shear local cleanup"),
                    "candidate_post_util": post_worst,
                    "candidate_reaches_target_band": bool(t_lo <= post_worst <= t_hi),
                },
                "resolved_candidate_updates": dict(next_cumulative),
                "resolved_candidate_post_util": post_worst,
                "resolved_candidate_reaches_target_band": bool(t_lo <= post_worst <= t_hi),
            }

        cumulative_updates = next_cumulative
        working_state = trial_state
        if starting_below_target and post_worst >= t_lo and not _shear_reinforcement_is_active(trial_state):
            break

    return best_rec if isinstance(best_rec, dict) else None


def _shear_tightening_as_local_cleanup_item(
    state: dict,
    overview: dict,
    efficiency_state: dict | None,
    *,
    runtime: ShearLocalCleanupRuntime | None = None,
) -> dict | None:
    if runtime is not None:
        _bind_shear_local_cleanup_runtime(runtime)
    es = efficiency_state if isinstance(efficiency_state, dict) else {}
    actions = dict(es.get("actions_used") or _resolve_design_actions_from_state(state) or {})
    direct_vu = abs(_float_from_state(state, "uls_Vstar", _float_from_state(state, "Vu_star", 0.0)))
    if _shear_demands_negligible(actions) or direct_vu <= float(GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN) + 1e-12:
        return None
    shear_tighten = es.get("shear_tightening")
    if not isinstance(shear_tighten, dict) or not dict(shear_tighten.get("updates") or {}):
        cur_eval = {"state": dict(state), "overview": dict(overview or {})}
        mode_cfg = _design_mode_config(_design_optimisation_goal(state))
        if bool(es.get("shear_cleanup_possible")) or _one_click_domain_needs_cleanup(cur_eval, "shear", mode_cfg):
            try:
                shear_tighten = _compute_shear_tightening_recommendation(state, out_debug={})
            except Exception:
                shear_tighten = None
    if not isinstance(shear_tighten, dict) or not dict(shear_tighten.get("updates") or {}):
        return None
    shear_tighten = _best_safe_shear_local_cleanup_recommendation(state, overview, shear_tighten)
    if not isinstance(shear_tighten, dict) or not dict(shear_tighten.get("updates") or {}):
        return None
    utils = dict((overview or {}).get("utils") or {})
    shear_util = shear_tighten.get("resolved_candidate_post_util")
    if shear_util is None:
        shear_util = utils.get("shear")
    if shear_util is None:
        shear_util = shear_tighten.get("util")
    title = "Design is safe - optional cleanup available"
    action_type = str(shear_tighten.get("action_type") or "increase_link_spacing").strip()
    item = _guidance_item(
        "shear",
        title,
        "Shear reserve is high. Optional cleanup can relax the link layout.",
        f"Alternative: use {shear_tighten.get('label') or 'a lighter shear link layout'}.",
        "Why: shear passes below the target band, so the local link layout can be relaxed safely.",
        "Key levers: link spacing, number of legs, target utilisation band",
        action_type,
        {"updates": dict(shear_tighten.get("updates") or {})},
        status="EFFICIENCY",
        util=shear_util,
    )
    resolved_candidate = dict(shear_tighten.get("resolved_candidate") or {})
    if resolved_candidate:
        resolved_candidate["updates"] = dict(
            resolved_candidate.get("updates")
            or shear_tighten.get("resolved_candidate_updates")
            or shear_tighten.get("updates")
            or {}
        )
        resolved_candidate["action_type"] = str(
            resolved_candidate.get("action_type")
            or shear_tighten.get("resolved_candidate_action_type")
            or action_type
        ).strip()
        resolved_candidate["label"] = str(
            resolved_candidate.get("label")
            or shear_tighten.get("resolved_candidate_label")
            or shear_tighten.get("label")
            or title
        ).strip()
        promoted = _promote_guidance_item_to_resolved_candidate(item, resolved_candidate, state=state)
        out_item = promoted if isinstance(promoted, dict) else item
        if isinstance(out_item, dict):
            resolved_updates = dict(resolved_candidate.get("updates") or shear_tighten.get("updates") or {})
            candidate_id = _guidance_cleanup_candidate_id("shear", resolved_updates)
            out_item["action_type"] = "apply_resolved_candidate"
            out_item["resolved_candidate_updates"] = dict(resolved_updates)
            out_item["updates"] = dict(resolved_updates)
            out_item["candidate_id"] = candidate_id
            out_item["source_candidate_id"] = candidate_id
            payload = dict(out_item.get("action_payload") or {})
            payload["resolved_candidate_updates"] = dict(resolved_updates)
            payload["resolved_candidate_action_type"] = "apply_resolved_candidate"
            payload["resolved_candidate"] = dict(resolved_candidate)
            payload["source_candidate_id"] = candidate_id
            payload["candidate_id"] = candidate_id
            out_item["action_payload"] = payload
            resolved_out = dict(out_item.get("resolved_candidate") or resolved_candidate)
            resolved_out["updates"] = dict(resolved_updates)
            resolved_out["candidate_id"] = candidate_id
            resolved_out["source_candidate_id"] = candidate_id
            out_item["resolved_candidate"] = resolved_out
            contract = dict(out_item.get("button_contract") or {})
            if contract:
                contract["action_type"] = "apply_resolved_candidate"
                contract["updates"] = dict(resolved_updates)
                contract["preview_pass"] = True
                contract["blocking_reason"] = None
                contract["actionable"] = True
                contract["source_candidate_id"] = candidate_id
                contract["candidate_id"] = candidate_id
                out_item["button_contract"] = contract
        return out_item
    return item


__all__ = [
    "bind_shear_local_cleanup_dependencies",
    "_best_safe_shear_local_cleanup_recommendation",
    "_shear_tightening_as_local_cleanup_item",
]
