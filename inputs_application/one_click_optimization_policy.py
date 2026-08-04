"""Target-domain and tightening policies for the one-click transaction."""

from __future__ import annotations

import math
from copy import deepcopy
from collections.abc import Callable

from inputs_application.geometry_search_policy import (
    geometry_lock_enabled,
    geometry_state_with_updates,
)
from inputs_application.recommendation_support import (
    resolve_geometry_width_context,
)
from inputs_application.state_utils import float_from_state
from inputs_application.candidate_identity import (
    make_auto_design_candidate_key as _make_auto_design_candidate_key,
)


def generate_smaller_geometry_variants(
    current_candidate: dict,
    mode_config: dict,
) -> list[dict]:
    """Permanent exact owner for bounded depth/width reduction variants."""
    state = dict(current_candidate.get("state") or {})
    if geometry_lock_enabled(state):
        return []
    strategy = str(
        mode_config.get("search_strategy", "balanced") or "balanced"
    )
    current_depth = float(
        current_candidate.get(
            "depth",
            float_from_state(state, "D", 600.0),
        )
        or float_from_state(state, "D", 600.0)
    )
    width_key, _, current_width = resolve_geometry_width_context(state)
    variants: dict[tuple, dict] = {}
    for depth in (current_depth - 50.0, current_depth - 100.0):
        if depth >= 350.0:
            candidate_state = geometry_state_with_updates(
                state,
                depth=depth,
            )
            variants[
                _make_auto_design_candidate_key(candidate_state)
            ] = candidate_state
    if strategy != "shallow":
        narrower = current_width - 50.0
        if narrower >= 250.0:
            candidate_state = geometry_state_with_updates(
                state,
                width=narrower,
            )
            variants[
                _make_auto_design_candidate_key(candidate_state)
            ] = candidate_state
        if width_key != "b":
            rectified = geometry_state_with_updates(
                state,
                width=current_width,
            )
            variants[
                _make_auto_design_candidate_key(rectified)
            ] = rectified
    return list(variants.values())


def candidate_bending_demand_util(candidate: dict) -> float | None:
    if not isinstance(candidate, dict):
        return None
    overview = candidate.get("overview") or {}
    bending_pack = (overview.get("packs") or {}).get("bending") or {}
    capacity = float(
        bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0
    )
    demand = float(
        bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0
    )
    if capacity <= 1e-9:
        return None
    return demand / capacity


def one_click_seed_target_domains_from_eval(
    eval_obj: dict | None,
    mode_config: dict,
    *,
    domain_score: Callable[..., dict],
) -> list[str]:
    if not isinstance(eval_obj, dict):
        return []
    scores = {
        domain: domain_score(eval_obj, domain, mode_config)
        for domain in ("bending", "shear")
    }
    failing = [
        domain
        for domain, score in scores.items()
        if not bool(score.get("pass"))
    ]
    if failing:
        return failing
    return [
        domain
        for domain in ("bending", "shear")
        if not bool((scores.get(domain) or {}).get("in_band"))
    ]


def one_click_tightening_mode_active(
    current_eval: dict,
    mode_config: dict,
    *,
    candidate_objective_util: Callable[[dict], float],
    default_target_min: float,
) -> bool:
    current_pass = bool(
        (current_eval.get("overview") or {}).get("all_key_pass")
    )
    domains = current_eval.get("target_domains_for_band")
    if (
        current_pass
        and isinstance(domains, (list, tuple, set))
        and domains
    ):
        try:
            low = float(
                mode_config.get("target_util_min", default_target_min)
                or default_target_min
            )
        except Exception:
            low = float(default_target_min)
        overview = current_eval.get("overview") or {}
        utils = dict(overview.get("utils") or {})
        bending_util = candidate_bending_demand_util(current_eval)
        if bending_util is None:
            bending_util = utils.get("bending")
        values = []
        for domain in domains:
            if str(domain).lower() == "bending":
                values.append(bending_util)
            elif str(domain).lower() == "shear":
                values.append(utils.get("shear"))
        parsed = []
        for value in values:
            try:
                resolved = float(value)
                if math.isfinite(resolved):
                    parsed.append(resolved)
            except Exception:
                pass
        return bool(
            parsed and any(value < low - 1e-6 for value in parsed)
        )
    try:
        low = float(
            mode_config.get("target_util_min", default_target_min)
            or default_target_min
        )
    except Exception:
        low = float(default_target_min)
    current_util = candidate_objective_util(current_eval)
    return bool(
        current_pass
        and math.isfinite(current_util)
        and current_util < low - 1e-6
    )


def one_click_still_materially_under_target(
    current_eval: dict,
    mode_config: dict,
    *,
    margin: float = 0.03,
    candidate_objective_util: Callable[[dict], float],
    candidate_target_domains: Callable[[dict], list[str]],
    domain_score: Callable[..., dict],
    default_target_min: float,
) -> bool:
    try:
        low = float(
            mode_config.get("target_util_min", default_target_min)
            or default_target_min
        )
    except Exception:
        low = float(default_target_min)
    current_pass = bool(
        (current_eval.get("overview") or {}).get("all_key_pass")
    )
    domains = candidate_target_domains(current_eval)
    resolved_margin = float(max(0.0, margin))
    if domains:
        under = False
        for domain in domains:
            score = domain_score(current_eval, domain, mode_config)
            util = score.get("util")
            try:
                resolved = float(util)
            except (TypeError, ValueError):
                continue
            if math.isfinite(resolved) and resolved < low - resolved_margin:
                under = True
                break
        return bool(current_pass and under)
    current_util = candidate_objective_util(current_eval)
    return bool(
        current_pass
        and math.isfinite(current_util)
        and current_util < low - resolved_margin
    )


def one_click_trace_eval_domain_payload(
    eval_obj: dict | None,
    mode_config: dict,
    *,
    candidate_target_band_distance: Callable[..., float],
    required_domain_progress: Callable[..., dict],
) -> dict:
    if not isinstance(eval_obj, dict):
        return {
            "target_domains_for_band": None,
            "target_domain_for_band": None,
            "candidate_domain_utils": {},
            "distance_to_band": None,
            "domain_scores": {},
            "domain_total_distance": None,
            "domain_max_distance": None,
        }
    raw_domains = eval_obj.get("target_domains_for_band")
    if isinstance(raw_domains, (list, tuple)):
        domains = list(raw_domains)
    elif raw_domains is None:
        domains = None
    else:
        domains = [raw_domains] if raw_domains else None
    raw_domain = eval_obj.get("target_domain_for_band")
    target_domain = (
        str(raw_domain).strip()
        if raw_domain is not None and str(raw_domain).strip()
        else None
    )
    overview = eval_obj.get("overview") or {}
    utils = (
        dict(overview.get("utils") or {})
        if isinstance(overview, dict)
        else {}
    )
    bending = candidate_bending_demand_util(eval_obj)
    if bending is None:
        bending = utils.get("bending")
    try:
        distance = float(
            candidate_target_band_distance(eval_obj, mode_config)
        )
    except Exception:
        distance = None
    try:
        progress = required_domain_progress(eval_obj, mode_config)
        scores = dict(progress.get("scores") or {})
        total_distance = float(
            progress.get("domain_total_distance", float("inf"))
        )
        max_distance = float(
            progress.get("domain_max_distance", float("inf"))
        )
    except Exception:
        progress = {}
        scores = {}
        total_distance = None
        max_distance = None
    return {
        "target_domains_for_band": domains,
        "target_domain_for_band": target_domain,
        "candidate_domain_utils": {
            "bending": bending,
            "shear": utils.get("shear"),
        },
        "distance_to_band": distance,
        "domain_scores": scores,
        "domain_total_distance": total_distance,
        "domain_max_distance": max_distance,
        "required_domain_count": progress.get("required_domain_count"),
        "required_fail_count": progress.get("required_fail_count"),
        "required_unsatisfied_count": progress.get(
            "required_unsatisfied_count"
        ),
        "required_satisfied_count": progress.get(
            "required_satisfied_count"
        ),
        "required_fail_domains": list(
            progress.get("required_fail_domains") or []
        ),
        "required_unsatisfied_domains": list(
            progress.get("required_unsatisfied_domains") or []
        ),
        "required_satisfied_domains": list(
            progress.get("required_satisfied_domains") or []
        ),
    }


def one_click_mixed_direction_rank_adjustment(
    current_eval: dict | None,
    candidate_eval: dict | None,
    mixed_mode: str | None,
    mode_config: dict,
    *,
    primary_improvement_margin: float = 0.02,
    domain_score: Callable[..., dict],
) -> dict:
    if mixed_mode == "bending_under_shear_over":
        primary_domain, secondary_domain = "bending", "shear"
    elif mixed_mode == "bending_over_shear_under":
        primary_domain, secondary_domain = "shear", "bending"
    else:
        return {
            "active": False,
            "mixed_mode": None,
            "primary_domain": None,
            "secondary_domain": None,
            "primary_material_improvement": False,
            "primary_distance": float("inf"),
            "secondary_distance": float("inf"),
            "current_secondary_distance": float("inf"),
        }
    current_primary = domain_score(
        current_eval, primary_domain, mode_config
    )
    candidate_primary = domain_score(
        candidate_eval, primary_domain, mode_config
    )
    current_secondary = domain_score(
        current_eval, secondary_domain, mode_config
    )
    candidate_secondary = domain_score(
        candidate_eval, secondary_domain, mode_config
    )
    current_primary_pass = bool(current_primary.get("pass"))
    candidate_primary_pass = bool(candidate_primary.get("pass"))
    current_primary_distance = float(
        current_primary.get("distance", float("inf")) or float("inf")
    )
    candidate_primary_distance = float(
        candidate_primary.get("distance", float("inf")) or float("inf")
    )
    current_secondary_distance = float(
        current_secondary.get("distance", float("inf")) or float("inf")
    )
    candidate_secondary_distance = float(
        candidate_secondary.get("distance", float("inf"))
        or float("inf")
    )
    margin = float(max(0.0, primary_improvement_margin))
    primary_improvement = bool(
        (candidate_primary_pass and not current_primary_pass)
        or (
            math.isfinite(current_primary_distance)
            and math.isfinite(candidate_primary_distance)
            and candidate_primary_distance
            <= current_primary_distance - margin
        )
    )
    return {
        "active": True,
        "mixed_mode": mixed_mode,
        "primary_domain": primary_domain,
        "secondary_domain": secondary_domain,
        "primary_material_improvement": primary_improvement,
        "primary_distance": candidate_primary_distance,
        "secondary_distance": (
            candidate_secondary_distance
            if primary_improvement
            else current_secondary_distance
        ),
        "current_secondary_distance": current_secondary_distance,
    }


def _target_domain_needing_work(
    candidate: dict,
    mode_config: dict,
    *,
    domains: list[str],
    domain_score: Callable[..., dict],
) -> str:
    scored: list[tuple[int, float, int, str]] = []
    for domain in domains:
        score = domain_score(candidate, domain, mode_config)
        if bool(score.get("in_band")):
            continue
        try:
            distance = float(score.get("distance"))
        except (TypeError, ValueError):
            distance = float("inf")
        if not math.isfinite(distance):
            distance = float("inf")
        status_weight = 1 if not bool(score.get("pass")) else 0
        order_weight = 1 if domain == "shear" else 0
        scored.append(
            (status_weight, distance, order_weight, domain)
        )
    if not scored:
        return ""
    scored.sort(
        key=lambda item: (item[0], item[1], item[2]),
        reverse=True,
    )
    return scored[0][3]


def one_click_attach_eval_target_domains(
    eval_obj: dict | None,
    target_domains_for_band,
    mode_config: dict,
    *,
    build_design_actions_context: Callable[[dict], dict],
    shear_demands_negligible: Callable[[dict | None], bool],
    domain_score: Callable[..., dict],
    bending_demand_abs_tol_knm: float,
) -> None:
    if not isinstance(eval_obj, dict):
        return
    requested = set(target_domains_for_band or [])
    raw_domains = [
        domain
        for domain in ("bending", "shear")
        if domain in requested
    ]
    overview = dict(eval_obj.get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    try:
        context = build_design_actions_context(
            dict(eval_obj.get("state") or {})
        )
        actions = dict(context.get("actions") or {})
    except Exception:
        actions = {}

    def relevant(domain: str) -> bool:
        status = str(
            statuses.get(domain) or ""
        ).strip().upper()
        if status == "FAIL":
            return True
        if domain == "shear":
            return not shear_demands_negligible(actions)
        if domain == "bending":
            try:
                demand = abs(
                    float(actions.get("Mu", 0.0) or 0.0)
                )
            except (TypeError, ValueError):
                return True
            return demand > bending_demand_abs_tol_knm + 1e-12
        return True

    domains = [domain for domain in raw_domains if relevant(domain)]
    if not domains:
        eval_obj.pop("target_domains_for_band", None)
        eval_obj.pop("target_domain_for_band", None)
        return
    eval_obj["target_domains_for_band"] = domains
    work_domain = _target_domain_needing_work(
        eval_obj,
        mode_config,
        domains=domains,
        domain_score=domain_score,
    )
    if work_domain:
        eval_obj["target_domain_for_band"] = work_domain
    else:
        eval_obj.pop("target_domain_for_band", None)


def one_click_mixed_direction_classification(
    eval_obj: dict | None,
    mode_config: dict,
    *,
    overdesign_margin: float = 0.03,
    domain_score: Callable[..., dict],
    build_design_actions_context: Callable[[dict], dict],
    shear_demands_negligible: Callable[[dict | None], bool],
    bending_demand_abs_tol_knm: float,
    default_target_min: float,
) -> str | None:
    bending = domain_score(eval_obj, "bending", mode_config)
    shear = domain_score(eval_obj, "shear", mode_config)
    try:
        low = float(
            mode_config.get("target_util_min", default_target_min)
            or default_target_min
        )
    except Exception:
        low = float(default_target_min)
    margin = float(max(0.0, overdesign_margin))
    state = dict((eval_obj or {}).get("state") or {})
    try:
        context = build_design_actions_context(state)
        actions = dict(context.get("actions") or {})
    except Exception:
        actions = {}

    def materially_over(score: dict) -> bool:
        try:
            util = float(score.get("util"))
        except (TypeError, ValueError):
            return False
        return bool(score.get("pass") and util < low - margin)

    try:
        bending_negligible = (
            abs(float(actions.get("Mu", 0.0) or 0.0))
            <= bending_demand_abs_tol_knm + 1e-12
        )
    except (TypeError, ValueError):
        bending_negligible = False
    if (
        not bool(bending.get("pass"))
        and materially_over(shear)
        and not shear_demands_negligible(actions)
    ):
        return "bending_under_shear_over"
    if (
        not bool(shear.get("pass"))
        and materially_over(bending)
        and not bending_negligible
    ):
        return "bending_over_shear_under"
    return None


def one_click_update_direction_summary(
    base_state: dict,
    updates: dict,
    *,
    guidance_state_snapshot: Callable[[dict | None], dict],
    design_width_value: Callable[[dict], float],
    float_from_state: Callable[..., float],
    effective_bottom_design_state: Callable[[dict], dict],
) -> dict:
    base = guidance_state_snapshot(dict(base_state or {}))
    trial = deepcopy(base)
    trial.update(dict(updates or {}))
    trial = guidance_state_snapshot(trial)
    base_width = float(design_width_value(base) or 0.0)
    trial_width = float(design_width_value(trial) or 0.0)
    base_depth = float(float_from_state(base, "D", 0.0) or 0.0)
    trial_depth = float(float_from_state(trial, "D", 0.0) or 0.0)
    base_steel = float(
        (effective_bottom_design_state(base) or {}).get(
            "Ast_bot", 0.0
        )
        or 0.0
    )
    trial_steel = float(
        (effective_bottom_design_state(trial) or {}).get(
            "Ast_bot", 0.0
        )
        or 0.0
    )
    geometry_growth = bool(
        trial_width > base_width + 1e-6
        or trial_depth > base_depth + 1e-6
    )
    geometry_reduction = bool(
        trial_width < base_width - 1e-6
        or trial_depth < base_depth - 1e-6
    )
    steel_growth = bool(trial_steel > base_steel + 1e-6)
    steel_reduction = bool(trial_steel < base_steel - 1e-6)
    return {
        "geometry_growth": geometry_growth,
        "geometry_reduction": geometry_reduction,
        "steel_growth": steel_growth,
        "steel_reduction": steel_reduction,
        "is_growth_only": bool(
            (geometry_growth or steel_growth)
            and not (geometry_reduction or steel_reduction)
        ),
        "is_reduction_candidate": bool(
            geometry_reduction or steel_reduction
        ),
    }


def one_click_in_band_shear_cleanup_candidate_allowed(
    current_eval: dict | None,
    candidate_eval: dict | None,
    updates: dict | None,
    mode_config: dict,
    *,
    shear_update_keys: frozenset[str],
    candidate_in_target_band: Callable[[dict, dict], bool],
    domain_score: Callable[..., dict],
    distance_tolerance: float = 0.015,
) -> bool:
    resolved_updates = dict(updates or {})
    if not bool(set(resolved_updates) & shear_update_keys):
        return False
    if not bool(
        (candidate_eval or {}).get("overview", {}).get("all_key_pass")
    ):
        return False
    if not candidate_in_target_band(candidate_eval or {}, mode_config):
        return False
    current_bending = domain_score(
        current_eval,
        "bending",
        mode_config,
    )
    candidate_bending = domain_score(
        candidate_eval,
        "bending",
        mode_config,
    )
    if bool(current_bending.get("pass")) and not bool(
        candidate_bending.get("pass")
    ):
        return False
    current_distance = float(
        current_bending.get("distance", float("inf"))
    )
    candidate_distance = float(
        candidate_bending.get("distance", float("inf"))
    )
    if not math.isfinite(current_distance):
        current_distance = float("inf")
    if not math.isfinite(candidate_distance):
        return False
    return bool(
        candidate_distance
        <= current_distance + float(max(distance_tolerance, 0.0))
    )


def one_click_build_user_visible_no_action_fields(
    stop_reason: str,
    debug: dict | None,
) -> dict[str, str | None]:
    messages = {
        "no_actionable_candidates": (
            "All candidates were filtered out; none preserved the "
            "governing checks with executable updates."
        ),
        "no_actionable_candidates_after_full_tightening_search": (
            "After the full tightening search, no actionable "
            "candidate remained."
        ),
        "non_material_remaining_candidates": (
            "Remaining candidates would not materially improve the design."
        ),
        "no_improving_candidate": (
            "No candidate improved the worst-case objective on this step."
        ),
    }
    resolved_debug = dict(debug or {})
    reason = str(stop_reason or "").strip()
    detail = messages.get(reason)
    if detail is None:
        if reason == "state_incoherent_after_rebuild":
            detail = (
                "The canonical beam state was incoherent after rebuild, "
                "so the one-click pass could not continue."
            )
        elif reason == "no_bars_resolved":
            detail = (
                "Add longitudinal reinforcement before running auto-design."
            )
        elif reason == "evaluate_failed":
            detail = (
                "Initial evaluation failed, so no trial updates could "
                "be scored."
            )
        else:
            detail = (
                f"Stop reason: {reason}."
                if reason
                else "The solver stopped before applying an update."
            )
    governing_domain = str(
        resolved_debug.get("governing_domain") or ""
    ).strip().lower()
    if reason == "state_incoherent_after_rebuild":
        headline = "One-click did not complete."
    elif governing_domain == "shear":
        headline = (
            "One-click ran, but the current shear candidate set was "
            "exhausted by practicality/code filters."
        )
    else:
        headline = (
            "One-click auto design ran, but no practical candidate "
            "was found."
        )
    visible_reason = f"{headline} — {detail}".strip()
    parts: list[str] = []
    for key in (
        "rejected_as_impractical_shear_layout",
        "rejected_as_spacing_too_weak",
        "rejected_as_web_crushing_marginal",
        "rejected_as_non_governing_cleanup",
    ):
        try:
            count = int(resolved_debug.get(key) or 0)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            parts.append(f"{key}: {count}")
    return {
        "user_visible_no_action_reason": visible_reason,
        "user_visible_rejection_summary": (
            "; ".join(parts) if parts else None
        ),
    }


def one_click_in_band_shear_cleanup_deferral(
    state: dict,
    eval_obj: dict | None,
    mode_config: dict,
    *,
    guidance_state_snapshot: Callable[[dict | None], dict],
    build_design_actions_context: Callable[[dict], dict],
    shear_reinforcement_is_active: Callable[[dict], bool],
    shear_demands_negligible: Callable[[dict | None], bool],
    governing_focus_from_overview: Callable[[dict | None], str],
    compute_shear_tightening_recommendation: Callable[..., dict | None],
    shear_update_keys: frozenset[str],
    evaluate_candidate_full: Callable[..., dict | None],
    cleanup_candidate_allowed: Callable[..., bool],
) -> dict:
    snapshot = guidance_state_snapshot(dict(state or {}))
    overview = dict((eval_obj or {}).get("overview") or {})
    try:
        context = build_design_actions_context(snapshot)
        actions = dict(context.get("actions") or {})
    except Exception:
        actions = {}
    result = {
        "active": False,
        "reason": "not_applicable",
        "recommendation": None,
        "candidate_eval": None,
    }
    if not shear_reinforcement_is_active(snapshot):
        result["reason"] = "inactive_links"
        return result
    shear_non_governing = bool(
        shear_demands_negligible(actions)
        or governing_focus_from_overview(overview) != "shear"
    )
    if not shear_non_governing:
        result["reason"] = "shear_still_governing"
        return result
    recommendation = compute_shear_tightening_recommendation(
        snapshot,
        out_debug={},
    )
    if not isinstance(recommendation, dict) or not dict(
        recommendation.get("updates") or {}
    ):
        result["reason"] = "no_legal_shear_cleanup_path"
        return result
    updates = dict(recommendation.get("updates") or {})
    if not bool(set(updates) & shear_update_keys):
        result["reason"] = "cleanup_not_shear_only"
        return result
    trial_state = dict(snapshot)
    trial_state.update(updates)
    candidate_eval = evaluate_candidate_full(
        guidance_state_snapshot(trial_state),
        source="one_click_in_band_shear_cleanup_probe",
        updates=updates,
    )
    if candidate_eval is None or not bool(
        (candidate_eval.get("overview") or {}).get("all_key_pass")
    ):
        result["reason"] = "cleanup_candidate_not_all_pass"
        return result
    if not cleanup_candidate_allowed(
        eval_obj,
        candidate_eval,
        updates,
        mode_config,
    ):
        result["reason"] = "cleanup_worsens_bending_materially"
        return result
    result.update(
        {
            "active": True,
            "reason": "blocked_non_governing_shear_cleanup_available",
            "recommendation": dict(recommendation),
            "candidate_eval": candidate_eval,
        }
    )
    return result


__all__ = [
    "candidate_bending_demand_util",
    "generate_smaller_geometry_variants",
    "one_click_mixed_direction_rank_adjustment",
    "one_click_mixed_direction_classification",
    "one_click_build_user_visible_no_action_fields",
    "one_click_in_band_shear_cleanup_candidate_allowed",
    "one_click_in_band_shear_cleanup_deferral",
    "one_click_attach_eval_target_domains",
    "one_click_seed_target_domains_from_eval",
    "one_click_still_materially_under_target",
    "one_click_tightening_mode_active",
    "one_click_trace_eval_domain_payload",
    "one_click_update_direction_summary",
]
