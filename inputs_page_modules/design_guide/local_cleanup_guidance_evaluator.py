"""Local-cleanup guidance-item evaluation coordination for the Inputs Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


_LOCAL_CLEANUP_GUIDANCE_EVALUATOR_DEPENDENCIES: tuple[str, ...] = (
    "_candidate_preview_statuses_have_explicit_fail",
    "_design_optimisation_goal",
    "_design_width_value",
    "_distance_to_target_band",
    "_evaluate_auto_design_candidate",
    "_float_from_state",
    "_governing_focus_from_overview",
    "_guidance_cleanup_candidate_id",
    "_guidance_executor_actionability_contract",
    "_guidance_item_is_resolved_one_click",
    "_local_cleanup_family_for_updates",
    "_local_cleanup_material_proxy",
    "_local_cleanup_materially_reduces",
    "_one_click_domain_needs_cleanup",
    "_overview_required_checks_acceptable",
    "_promote_guidance_item_to_resolved_candidate",
    "_resolve_recommendation_updates",
    "_resolved_efficiency_target_band",
    "_resolved_shear_cleanup_is_executor_safe",
    "_state_update_reduces_section_size",
    "_updates_match_state",
)


@dataclass(frozen=True)
class LocalCleanupGuidanceEvaluatorRuntime:
    candidate_preview_statuses_have_explicit_fail: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    design_width_value: Callable[..., Any]
    distance_to_target_band: Callable[..., Any]
    evaluate_auto_design_candidate: Callable[..., Any]
    float_from_state: Callable[..., Any]
    governing_focus_from_overview: Callable[..., Any]
    guidance_cleanup_candidate_id: Callable[..., Any]
    guidance_executor_actionability_contract: Callable[..., Any]
    guidance_item_is_resolved_one_click: Callable[..., Any]
    local_cleanup_family_for_updates: Callable[..., Any]
    local_cleanup_material_proxy: Callable[..., Any]
    local_cleanup_materially_reduces: Callable[..., Any]
    one_click_domain_needs_cleanup: Callable[..., Any]
    overview_required_checks_acceptable: Callable[..., Any]
    promote_guidance_item_to_resolved_candidate: Callable[..., Any]
    resolve_recommendation_updates: Callable[..., Any]
    resolved_efficiency_target_band: Callable[..., Any]
    resolved_shear_cleanup_is_executor_safe: Callable[..., Any]
    state_update_reduces_section_size: Callable[..., Any]
    updates_match_state: Callable[..., Any]


def bind_local_cleanup_guidance_evaluator_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _LOCAL_CLEANUP_GUIDANCE_EVALUATOR_DEPENDENCIES
            if name in namespace
        }
    )


def _local_cleanup_family_from_item_identity(item: dict | None) -> str:
    if not isinstance(item, dict):
        return ""
    raw = str(
        item.get("affected_family")
        or item.get("selected_family_id")
        or item.get("published_family_id")
        or item.get("family_id")
        or item.get("family")
        or ""
    ).strip()
    normalised = raw.lower()
    if normalised in {"bending", "bending_overdesign_governs"}:
        return "bending"
    if normalised in {"shear", "shear_overdesign_governs"}:
        return "shear"
    if normalised in {"combined", "combined_overdesign"}:
        return "combined"
    if normalised in {"geometry", "geometry_detailing_governs"}:
        return "geometry"
    return ""


def _evaluate_local_cleanup_guidance_item(
    item: dict | None,
    *,
    state: dict,
    overview: dict,
    mode_config: dict,
    source: str,
    runtime: LocalCleanupGuidanceEvaluatorRuntime | None = None,
) -> tuple[dict | None, dict]:
    if runtime is not None:
        _candidate_preview_statuses_have_explicit_fail = (
            runtime.candidate_preview_statuses_have_explicit_fail
        )
        _design_optimisation_goal = runtime.design_optimisation_goal
        _design_width_value = runtime.design_width_value
        _distance_to_target_band = runtime.distance_to_target_band
        _evaluate_auto_design_candidate = (
            runtime.evaluate_auto_design_candidate
        )
        _float_from_state = runtime.float_from_state
        _governing_focus_from_overview = (
            runtime.governing_focus_from_overview
        )
        _guidance_cleanup_candidate_id = (
            runtime.guidance_cleanup_candidate_id
        )
        _guidance_executor_actionability_contract = (
            runtime.guidance_executor_actionability_contract
        )
        _guidance_item_is_resolved_one_click = (
            runtime.guidance_item_is_resolved_one_click
        )
        _local_cleanup_family_for_updates = (
            runtime.local_cleanup_family_for_updates
        )
        _local_cleanup_material_proxy = (
            runtime.local_cleanup_material_proxy
        )
        _local_cleanup_materially_reduces = (
            runtime.local_cleanup_materially_reduces
        )
        _one_click_domain_needs_cleanup = (
            runtime.one_click_domain_needs_cleanup
        )
        _overview_required_checks_acceptable = (
            runtime.overview_required_checks_acceptable
        )
        _promote_guidance_item_to_resolved_candidate = (
            runtime.promote_guidance_item_to_resolved_candidate
        )
        _resolve_recommendation_updates = (
            runtime.resolve_recommendation_updates
        )
        _resolved_efficiency_target_band = (
            runtime.resolved_efficiency_target_band
        )
        _resolved_shear_cleanup_is_executor_safe = (
            runtime.resolved_shear_cleanup_is_executor_safe
        )
        _state_update_reduces_section_size = (
            runtime.state_update_reduces_section_size
        )
        _updates_match_state = runtime.updates_match_state
    else:
        namespace = globals()
        _candidate_preview_statuses_have_explicit_fail = namespace[
            "_candidate_preview_statuses_have_explicit_fail"
        ]
        _design_optimisation_goal = namespace["_design_optimisation_goal"]
        _design_width_value = namespace["_design_width_value"]
        _distance_to_target_band = namespace["_distance_to_target_band"]
        _evaluate_auto_design_candidate = namespace[
            "_evaluate_auto_design_candidate"
        ]
        _float_from_state = namespace["_float_from_state"]
        _governing_focus_from_overview = namespace[
            "_governing_focus_from_overview"
        ]
        _guidance_cleanup_candidate_id = namespace[
            "_guidance_cleanup_candidate_id"
        ]
        _guidance_executor_actionability_contract = namespace[
            "_guidance_executor_actionability_contract"
        ]
        _guidance_item_is_resolved_one_click = namespace[
            "_guidance_item_is_resolved_one_click"
        ]
        _local_cleanup_family_for_updates = namespace[
            "_local_cleanup_family_for_updates"
        ]
        _local_cleanup_material_proxy = namespace[
            "_local_cleanup_material_proxy"
        ]
        _local_cleanup_materially_reduces = namespace[
            "_local_cleanup_materially_reduces"
        ]
        _one_click_domain_needs_cleanup = namespace[
            "_one_click_domain_needs_cleanup"
        ]
        _overview_required_checks_acceptable = namespace[
            "_overview_required_checks_acceptable"
        ]
        _promote_guidance_item_to_resolved_candidate = namespace[
            "_promote_guidance_item_to_resolved_candidate"
        ]
        _resolve_recommendation_updates = namespace[
            "_resolve_recommendation_updates"
        ]
        _resolved_efficiency_target_band = namespace[
            "_resolved_efficiency_target_band"
        ]
        _resolved_shear_cleanup_is_executor_safe = namespace[
            "_resolved_shear_cleanup_is_executor_safe"
        ]
        _state_update_reduces_section_size = namespace[
            "_state_update_reduces_section_size"
        ]
        _updates_match_state = namespace["_updates_match_state"]
    detail = {
        "blocked_reason": None,
        "family": None,
        "candidate_id": None,
        "distance": float("inf"),
        "candidate_complexity_score": None,
        "net_efficiency_delta": None,
        "material_proxy_before": None,
        "material_proxy_after": None,
        "material_proxy_delta": None,
        "is_executable": False,
        "advisory_only": True,
    }
    if not isinstance(item, dict):
        detail["blocked_reason"] = "invalid_candidate"
        return None, detail

    action_type = str(item.get("action_type") or "").strip()
    if not action_type:
        detail["blocked_reason"] = "candidate_not_actionable"
        return None, detail

    try:
        updates = _resolve_recommendation_updates(item, state=state)
    except Exception:
        updates = {}
    updates = dict(updates or {})
    if not updates or _updates_match_state(state, updates):
        detail["blocked_reason"] = "cleanup_no_material_update"
        return None, detail

    explicit_family = _local_cleanup_family_from_item_identity(item)
    family = explicit_family or _local_cleanup_family_for_updates(updates, item, state)
    detail["family"] = family
    detail["candidate_id"] = _guidance_cleanup_candidate_id(family, updates)

    candidate_state = dict(state)
    candidate_state.update(updates)
    before_proxy = _local_cleanup_material_proxy(state)
    after_proxy = _local_cleanup_material_proxy(candidate_state)
    detail["candidate_complexity_score"] = len(updates)
    detail["material_proxy_before"] = before_proxy
    detail["material_proxy_after"] = after_proxy
    detail["material_proxy_delta"] = after_proxy - before_proxy
    detail["net_efficiency_delta"] = before_proxy - after_proxy
    if after_proxy >= before_proxy - 1e-6:
        detail["blocked_reason"] = "cleanup_no_net_material_efficiency"
        return None, detail
    if _state_update_reduces_section_size(state, candidate_state) is False:
        try:
            w0 = float(_design_width_value(state) or 0.0)
            w1 = float(_design_width_value(candidate_state) or w0)
            d0 = float(_float_from_state(state, "D", 0.0) or 0.0)
            d1 = float(_float_from_state(candidate_state, "D", d0) or d0)
            if w1 > w0 + 1e-9 or d1 > d0 + 1e-9:
                detail["blocked_reason"] = "cleanup_increases_geometry_without_section_reduction"
                return None, detail
        except Exception:
            pass
    if not _local_cleanup_materially_reduces(family, state, candidate_state):
        detail["blocked_reason"] = "cleanup_not_material"
        return None, detail

    if bool(overview.get("any_fail")) or not _overview_required_checks_acceptable(overview):
        detail["blocked_reason"] = "active_failure_needs_strengthening"
        return None, detail

    if family == "shear":
        cur_eval = {"state": dict(state), "overview": dict(overview or {})}
        if not _one_click_domain_needs_cleanup(cur_eval, "shear", mode_config):
            detail["blocked_reason"] = "shear_not_below_target"
            return None, detail

    try:
        candidate = _evaluate_auto_design_candidate(
            state,
            updates=updates,
            source=source,
            label=str(
                item.get("resolved_candidate_label")
                or (item.get("action_payload") or {}).get("resolved_candidate_label")
                or item.get("title_main")
                or "Local cleanup",
            ),
            action_type=action_type,
        )
    except Exception:
        candidate = None
    if not isinstance(candidate, dict):
        detail["blocked_reason"] = "cleanup_preview_failed"
        return None, detail

    candidate["updates"] = dict(candidate.get("updates") or updates)
    candidate["action_type"] = str(candidate.get("action_type") or action_type)
    candidate["label"] = str(candidate.get("label") or item.get("title_main") or "Local cleanup")
    candidate_overview = dict(candidate.get("overview") or {})
    if bool(candidate_overview.get("any_fail")) or not _overview_required_checks_acceptable(candidate_overview):
        detail["blocked_reason"] = "cleanup_preview_not_all_pass"
        return None, detail
    if _candidate_preview_statuses_have_explicit_fail(dict(candidate_overview.get("statuses") or {})):
        detail["blocked_reason"] = "cleanup_preview_has_fail_status"
        return None, detail

    if family == "shear" and not _resolved_shear_cleanup_is_executor_safe(
        _promote_guidance_item_to_resolved_candidate(item, candidate, state=state),
        state=state,
        overview=overview,
    ):
        detail["blocked_reason"] = "shear_cleanup_not_executor_safe"
        return None, detail

    t_lo, t_hi, _ = _resolved_efficiency_target_band(mode_config, goal=_design_optimisation_goal(state))
    try:
        post_worst = float(candidate_overview.get("worst_util", candidate.get("worst_util", 0.0)) or 0.0)
    except Exception:
        post_worst = float("inf")
    detail["distance"] = _distance_to_target_band(post_worst, t_lo, t_hi)
    try:
        current_worst = float((overview or {}).get("worst_util") or 0.0)
    except Exception:
        current_worst = None
    if current_worst is not None and current_worst < float(t_lo) - 1e-9:
        current_distance = _distance_to_target_band(current_worst, t_lo, t_hi)
        if (
            detail["distance"] >= current_distance - 1e-9
            and str(detail.get("family") or "") != str(_governing_focus_from_overview(overview) or "")
        ):
            detail["blocked_reason"] = "cleanup_does_not_move_governing_utilisation_toward_target"
            return None, detail
    promoted = _promote_guidance_item_to_resolved_candidate(item, candidate, state=state)
    if not _guidance_item_is_resolved_one_click(promoted):
        detail["blocked_reason"] = "cleanup_not_executor_backed"
        return None, detail
    allowed, executor_reason = _guidance_executor_actionability_contract(promoted, state=state)
    if not allowed:
        detail["blocked_reason"] = executor_reason or "cleanup_not_executable"
        detail["advisory_only"] = True
        detail["is_executable"] = False
        return None, detail
    detail["is_executable"] = True
    detail["advisory_only"] = False
    return promoted, detail
