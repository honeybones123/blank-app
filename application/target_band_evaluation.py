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


def resolve_candidate_target_band_distance(
    candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> float:
    """Return the ranking distance to target band for a candidate."""

    domains = resolve_candidate_target_domains_for_band(candidate)
    if not domains:
        util = resolve_auto_design_candidate_objective_util(
            candidate,
            optimisation_goal_resolver=optimisation_goal_resolver,
        )
        mode = dict(mode_config or {})
        try:
            target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
            target_max = float(mode.get("target_util_max", default_target_max) or default_target_max)
        except Exception:
            target_min = float(default_target_min)
            target_max = float(default_target_max)
        return resolve_distance_to_target_band(util, target_min, target_max)
    return resolve_candidate_domain_max_distance(
        candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )


def resolve_candidate_target_band_total_distance(
    candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> float:
    """Return total target-band distance for candidate ranking."""

    return resolve_candidate_domain_total_distance(
        candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )


def resolve_candidate_step_improves(
    new_eval: dict[str, Any] | None,
    old_eval: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> bool:
    """Return whether a candidate step improves target-band progress."""

    old_candidate = old_eval if isinstance(old_eval, dict) else {}
    new_candidate = new_eval if isinstance(new_eval, dict) else {}
    old_pass = bool((old_candidate.get("overview") or {}).get("all_key_pass"))
    new_pass = bool((new_candidate.get("overview") or {}).get("all_key_pass"))
    old_ib = resolve_candidate_in_target_band(
        old_candidate, mode_config, default_target_min=default_target_min,
        default_target_max=default_target_max, fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    new_ib = resolve_candidate_in_target_band(
        new_candidate, mode_config, default_target_min=default_target_min,
        default_target_max=default_target_max, fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    old_u = resolve_auto_design_candidate_objective_util(
        old_candidate, optimisation_goal_resolver=optimisation_goal_resolver
    )
    new_u = resolve_auto_design_candidate_objective_util(
        new_candidate, optimisation_goal_resolver=optimisation_goal_resolver
    )
    old_d = resolve_candidate_target_band_distance(
        old_candidate, mode_config, default_target_min=default_target_min,
        default_target_max=default_target_max, fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    new_d = resolve_candidate_target_band_distance(
        new_candidate, mode_config, default_target_min=default_target_min,
        default_target_max=default_target_max, fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    if resolve_candidate_target_domains_for_band(old_candidate) or resolve_candidate_target_domains_for_band(new_candidate):
        old_progress = resolve_candidate_required_domain_progress(
            old_candidate, mode_config, default_target_min=default_target_min,
            default_target_max=default_target_max, fail_status=fail_status,
            optimisation_goal_resolver=optimisation_goal_resolver,
        )
        new_progress = resolve_candidate_required_domain_progress(
            new_candidate, mode_config, default_target_min=default_target_min,
            default_target_max=default_target_max, fail_status=fail_status,
            optimisation_goal_resolver=optimisation_goal_resolver,
        )
        old_fail = int(old_progress.get("required_fail_count", 0) or 0)
        new_fail = int(new_progress.get("required_fail_count", 0) or 0)
        old_unsatisfied = int(old_progress.get("required_unsatisfied_count", 0) or 0)
        new_unsatisfied = int(new_progress.get("required_unsatisfied_count", 0) or 0)
        old_max = float(old_progress.get("domain_max_distance", float("inf")))
        new_max = float(new_progress.get("domain_max_distance", float("inf")))
        old_total = float(old_progress.get("domain_total_distance", float("inf")))
        new_total = float(new_progress.get("domain_total_distance", float("inf")))
        if new_ib and not old_ib and new_pass:
            return True
        if new_fail < old_fail or new_unsatisfied < old_unsatisfied:
            return True
        if new_pass and not old_pass:
            max_not_worse = math.isfinite(old_max) and math.isfinite(new_max) and new_max <= old_max + 1e-6
            total_improved = math.isfinite(old_total) and math.isfinite(new_total) and new_total < old_total - 1e-6
            return bool(max_not_worse or total_improved)
        if new_max < old_max - 1e-6:
            return True
        if new_max <= old_max + 1e-6 and new_total < old_total - 1e-6:
            return True
        return False
    old_total = resolve_candidate_target_band_total_distance(
        old_candidate, mode_config, default_target_min=default_target_min,
        default_target_max=default_target_max, fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    new_total = resolve_candidate_target_band_total_distance(
        new_candidate, mode_config, default_target_min=default_target_min,
        default_target_max=default_target_max, fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    if new_pass and not old_pass or (new_ib and not old_ib and new_pass):
        return True
    if new_d < old_d - 1e-6:
        return True
    if new_d <= old_d + 1e-6 and new_total < old_total - 1e-6:
        return True
    mode = dict(mode_config or {})
    lo = float(mode.get("target_util_min", default_target_min) or default_target_min)
    hi = float(mode.get("target_util_max", default_target_max) or default_target_max)
    if old_u < lo and new_u > old_u + 1e-9 and new_pass == old_pass:
        return True
    if old_u > hi and new_u < old_u - 1e-9 and new_pass == old_pass:
        return True
    return False


def resolve_target_band_exhaustion_refinement_allowed(
    current_eval: dict[str, Any] | None,
    next_hop_payload: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> bool:
    """Return whether an exhaustion fallback refinement may be injected."""

    if not isinstance(current_eval, dict) or not isinstance(next_hop_payload, dict):
        return False
    if not bool((current_eval.get("overview") or {}).get("all_key_pass")):
        return False
    current_domains = list(resolve_candidate_target_domains_for_band(current_eval) or [])
    if len(current_domains) < 2:
        return False
    current_progress = resolve_candidate_required_domain_progress(
        current_eval, mode_config, default_target_min=default_target_min,
        default_target_max=default_target_max, fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    if int(current_progress.get("required_fail_count", 0) or 0) != 0:
        return False
    if int(current_progress.get("required_unsatisfied_count", 0) or 0) <= 1:
        return False
    candidate_eval = next_hop_payload.get("eval")
    if not isinstance(candidate_eval, dict):
        return False
    if not bool((candidate_eval.get("overview") or {}).get("all_key_pass")):
        return False
    candidate_progress = resolve_candidate_required_domain_progress(
        candidate_eval, mode_config, default_target_min=default_target_min,
        default_target_max=default_target_max, fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    if int(candidate_progress.get("required_fail_count", 0) or 0) != 0:
        return False
    if int(candidate_progress.get("required_unsatisfied_count", 0) or 0) > int(current_progress.get("required_unsatisfied_count", 0) or 0):
        return False
    current_max = float(current_progress.get("domain_max_distance", float("inf")))
    candidate_max = float(candidate_progress.get("domain_max_distance", float("inf")))
    current_total = float(current_progress.get("domain_total_distance", float("inf")))
    candidate_total = float(candidate_progress.get("domain_total_distance", float("inf")))
    if not all(math.isfinite(value) for value in (current_max, candidate_max, current_total, candidate_total)):
        return False
    if candidate_max > current_max + 1e-6 or candidate_total >= current_total - 1e-6:
        return False
    return resolve_candidate_step_improves(
        candidate_eval, current_eval, mode_config,
        default_target_min=default_target_min, default_target_max=default_target_max,
        fail_status=fail_status, optimisation_goal_resolver=optimisation_goal_resolver,
    )


def resolve_target_band_next_hop_precheck(
    current_eval: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    """Resolve pure preconditions before fallback refinement generation."""

    if not isinstance(current_eval, dict):
        return {"allowed": False, "reason": "missing_current_eval", "overview": {}, "current_distance": None, "current_state": {}}
    overview = dict((current_eval.get("overview") or {}))
    if not bool(overview.get("all_key_pass")):
        return {"allowed": False, "reason": "current_not_all_pass", "overview": overview, "current_distance": None, "current_state": {}}
    try:
        lo = float((mode_config or {}).get("target_util_min", default_target_min) or default_target_min)
        hi = float((mode_config or {}).get("target_util_max", default_target_max) or default_target_max)
    except Exception:
        lo = float(default_target_min)
        hi = float(default_target_max)
    try:
        worst = float(overview.get("governing_util", overview.get("worst_util", 0.0)) or 0.0)
    except (TypeError, ValueError):
        worst = None
    statuses = dict(overview.get("statuses") or {})
    any_fail = any(
        value == fail_status or str(value or "").strip().upper() == str(fail_status).strip().upper()
        for value in statuses.values()
    )
    if worst is not None and not any_fail and lo <= float(worst) <= hi:
        return {"allowed": False, "reason": "already_in_strict_target_band", "overview": overview, "current_distance": None, "current_state": {}}
    current_distance = resolve_candidate_target_band_distance(
        current_eval, mode_config, default_target_min=default_target_min,
        default_target_max=default_target_max, fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    if current_distance is None or not math.isfinite(float(current_distance)):
        return {"allowed": False, "reason": "non_finite_current_distance", "overview": overview, "current_distance": current_distance, "current_state": {}}
    current_state = dict(current_eval.get("state") or {})
    if not current_state:
        return {"allowed": False, "reason": "missing_current_state", "overview": overview, "current_distance": current_distance, "current_state": {}}
    return {"allowed": True, "reason": "allowed", "overview": overview, "current_distance": float(current_distance), "current_state": current_state}


__all__ = [
    "resolve_candidate_domain_max_distance",
    "resolve_candidate_domain_score",
    "resolve_candidate_domain_total_distance",
    "resolve_candidate_domain_util",
    "resolve_candidate_eval_domain_scores",
    "resolve_candidate_in_target_band",
    "resolve_candidate_required_domain_progress",
    "resolve_candidate_required_domains_satisfied",
    "resolve_candidate_step_improves",
    "resolve_candidate_target_band_distance",
    "resolve_candidate_target_band_total_distance",
    "resolve_target_band_exhaustion_refinement_allowed",
    "resolve_target_band_next_hop_precheck",
    "resolve_candidate_target_domains_for_band",
    "resolve_distance_to_target_band",
]
