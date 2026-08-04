"""Application-owned target-band evaluation policies."""

from __future__ import annotations

import math
from typing import Any, Callable

from application.candidate_objective_policy import (
    resolve_auto_design_candidate_objective_util,
)
from inputs_application.one_click_optimization_policy import (
    candidate_bending_demand_util,
)


def resolve_distance_to_target_band(util: Any, target_min: Any, target_max: Any) -> float:
    """Return absolute distance from a utilisation value to a target band."""

    try:
        u = float(util)
        lo = float(target_min)
        hi = float(target_max)
    except (TypeError, ValueError):
        return float("inf")
    if lo <= u <= hi:
        return 0.0
    if u < lo:
        return lo - u
    return u - hi


def resolve_candidate_target_domains_for_band(candidate: dict[str, Any] | None) -> list[str]:
    """Return normalized target-band domains for a candidate."""

    if not isinstance(candidate, dict):
        return []
    raw = candidate.get("target_domains_for_band")
    if not isinstance(raw, list) or not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        domain = str(item or "").strip().lower()
        if domain in ("flexure", "ductility", "bottom", "bottom_reo"):
            domain = "bending"
        if domain not in ("bending", "shear"):
            continue
        if domain not in seen:
            out.append(domain)
            seen.add(domain)
    return out


def resolve_candidate_domain_util(candidate: dict[str, Any] | None, domain: str) -> float | None:
    """Resolve candidate utilisation for a target-band domain."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    resolved_domain = str(domain or "").strip().lower()
    if resolved_domain == "bending":
        demand_util = candidate_bending_demand_util(candidate_d)
        if demand_util is not None:
            try:
                value = float(demand_util)
                if math.isfinite(value):
                    return value
            except Exception:
                pass
        raw = ((candidate_d.get("overview") or {}).get("utils") or {}).get("bending")
        try:
            value = float(raw)
            if math.isfinite(value):
                return value
        except Exception:
            return None
        return None
    if resolved_domain == "shear":
        raw = ((candidate_d.get("overview") or {}).get("utils") or {}).get("shear")
        try:
            value = float(raw)
            if math.isfinite(value):
                return value
        except Exception:
            return None
        return None
    return None


def resolve_candidate_domain_score(
    eval_obj: dict[str, Any] | None,
    domain: str,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
) -> dict[str, Any]:
    """Build the target-band score for a single candidate domain."""

    resolved_domain = str(domain or "").strip().lower()
    overview = dict((eval_obj or {}).get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    status = statuses.get(resolved_domain)
    util = resolve_candidate_domain_util(eval_obj or {}, resolved_domain)
    mode = dict(mode_config or {})
    try:
        target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
        target_max = float(mode.get("target_util_max", default_target_max) or default_target_max)
    except Exception:
        target_min = float(default_target_min)
        target_max = float(default_target_max)
    resolved_util = None
    if util is not None:
        try:
            candidate_util = float(util)
            if math.isfinite(candidate_util):
                resolved_util = candidate_util
        except Exception:
            resolved_util = None
    fail = bool(status == fail_status or str(status or "").strip().upper() == "FAIL")
    ok_status = not fail
    distance = float("inf") if resolved_util is None else resolve_distance_to_target_band(
        resolved_util, target_min, target_max
    )
    return {
        "domain": resolved_domain,
        "status": status,
        "util": resolved_util,
        "distance": distance,
        "in_band": bool(resolved_util is not None and target_min <= resolved_util <= target_max and ok_status),
        "pass": bool(ok_status),
        "under": bool(resolved_util is not None and resolved_util < target_min),
        "over": bool(resolved_util is not None and resolved_util > target_max),
    }


def resolve_candidate_eval_domain_scores(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
) -> dict[str, dict[str, Any]]:
    """Build target-band scores for every candidate target domain."""

    return {
        domain: resolve_candidate_domain_score(
            eval_obj,
            domain,
            mode_config,
            default_target_min=default_target_min,
            default_target_max=default_target_max,
            fail_status=fail_status,
        )
        for domain in resolve_candidate_target_domains_for_band(eval_obj or {})
    }


def resolve_candidate_required_domain_progress(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    """Summarize required target-domain progress for candidate ranking."""

    scores = resolve_candidate_eval_domain_scores(
        eval_obj,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
    )
    mode = dict(mode_config or {})
    try:
        target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
        target_max = float(mode.get("target_util_max", default_target_max) or default_target_max)
    except (TypeError, ValueError, KeyError):
        target_min = float(default_target_min)
        target_max = float(default_target_max)
    if not scores:
        util = resolve_auto_design_candidate_objective_util(
            eval_obj or {}, optimisation_goal_resolver=optimisation_goal_resolver
        )
        try:
            util = float(util)
        except (TypeError, ValueError):
            util = None
        overview = dict((eval_obj or {}).get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        all_key_pass = bool(overview.get("all_key_pass"))
        any_fail = any(
            status == fail_status or str(status or "").strip().upper() == "FAIL"
            for status in statuses.values()
        )
        ok_status = bool(all_key_pass and not any_fail)
        in_band = bool(
            util is not None
            and math.isfinite(float(util))
            and target_min <= float(util) <= target_max
            and ok_status
        )
        distance = (
            float("inf")
            if util is None or not math.isfinite(float(util))
            else resolve_distance_to_target_band(float(util), target_min, target_max)
        )
        return {
            "scores": {},
            "required_domain_count": 0,
            "required_fail_count": 0 if ok_status else 1,
            "required_unsatisfied_count": 0 if in_band else 1,
            "required_satisfied_count": 1 if in_band else 0,
            "required_fail_domains": [] if ok_status else ["objective"],
            "required_unsatisfied_domains": [] if in_band else ["objective"],
            "required_satisfied_domains": ["objective"] if in_band else [],
            "domain_total_distance": float(distance),
            "domain_max_distance": float(distance),
        }
    fail_domains: list[str] = []
    unsatisfied_domains: list[str] = []
    satisfied_domains: list[str] = []
    total = 0.0
    max_distance = float("-inf")
    for domain, score in scores.items():
        if not bool(score.get("pass")):
            fail_domains.append(domain)
        if bool(score.get("pass")) and bool(score.get("in_band")):
            satisfied_domains.append(domain)
        else:
            unsatisfied_domains.append(domain)
        dist = score.get("distance")
        if dist is None or not math.isfinite(float(dist)):
            total = float("inf")
            max_distance = float("inf")
            continue
        fd = float(dist)
        if not math.isfinite(total):
            continue
        total += fd
        max_distance = max(max_distance, fd)
    if max_distance == float("-inf"):
        max_distance = float("inf")
    return {
        "scores": scores,
        "required_domain_count": len(scores),
        "required_fail_count": len(fail_domains),
        "required_unsatisfied_count": len(unsatisfied_domains),
        "required_satisfied_count": len(satisfied_domains),
        "required_fail_domains": fail_domains,
        "required_unsatisfied_domains": unsatisfied_domains,
        "required_satisfied_domains": satisfied_domains,
        "domain_total_distance": float(total),
        "domain_max_distance": float(max_distance),
    }


def resolve_candidate_domain_total_distance(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> float:
    progress = resolve_candidate_required_domain_progress(
        eval_obj,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    return float(progress.get("domain_total_distance", float("inf")))


def resolve_candidate_domain_max_distance(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> float:
    progress = resolve_candidate_required_domain_progress(
        eval_obj,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    return float(progress.get("domain_max_distance", float("inf")))


def resolve_candidate_required_domains_satisfied(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> bool:
    if not isinstance(eval_obj, dict):
        return False
    progress = resolve_candidate_required_domain_progress(
        eval_obj,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    return int(progress.get("required_unsatisfied_count", 0) or 0) == 0


def resolve_candidate_in_target_band(
    candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> bool:
    if not isinstance(candidate, dict):
        return False
    return resolve_candidate_required_domains_satisfied(
        candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )


__all__ = [
    "resolve_candidate_domain_max_distance",
    "resolve_candidate_domain_score",
    "resolve_candidate_domain_total_distance",
    "resolve_candidate_domain_util",
    "resolve_candidate_eval_domain_scores",
    "resolve_candidate_in_target_band",
    "resolve_candidate_required_domain_progress",
    "resolve_candidate_required_domains_satisfied",
    "resolve_candidate_target_domains_for_band",
    "resolve_distance_to_target_band",
]
