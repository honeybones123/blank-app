"""Crack and deflection serviceability ladder candidate coordination."""

from __future__ import annotations

from typing import Any


_SERVICEABILITY_LADDER_CANDIDATE_DEPENDENCIES: tuple[str, ...] = (
    "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM",
    "GUIDANCE_LADDER_EARLY_STOP_UTIL",
    "_describe_guidance_step",
    "_evaluate_crack_with_state",
    "_evaluate_deflection_with_state",
    "_float_from_state",
    "_guidance_action_updates",
    "_log_guidance_ladder_debug",
    "_merge_guidance_state",
    "_updates_match_state",
)


def bind_serviceability_ladder_candidate_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SERVICEABILITY_LADDER_CANDIDATE_DEPENDENCIES
            if name in namespace
        }
    )


def _try_crack_ladder_candidate(
    state: dict,
    *,
    label: str,
    updates: dict | None,
    base_util: float,
    ladder_name: str = "crack_ladder",
) -> dict | None:
    if not updates:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=None,
            decision="rejected",
            reason="empty_updates",
            metric_name="crack_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    if _updates_match_state(state, updates):
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="noop_vs_state",
            metric_name="crack_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    ev = _evaluate_crack_with_state(_merge_guidance_state(state, updates))
    if not ev:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="crack_eval_none",
            metric_name="crack_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    nu = float(ev.get("util", 0.0) or 0.0)
    if nu >= base_util - 1e-9:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="no_improvement",
            metric_name="crack_util",
            metric_before=base_util,
            metric_after=nu,
        )
        return None
    early = nu <= GUIDANCE_LADDER_EARLY_STOP_UTIL and nu <= 1.0 + 1e-9
    _log_guidance_ladder_debug(
        ladder_name,
        candidate_label=label,
        candidate_updates=updates,
        decision="accepted",
        reason="improves_crack_util",
        metric_name="crack_util",
        metric_before=base_util,
        metric_after=nu,
        early_stop=early,
    )
    return {"label": label, "updates": updates, "util_after": nu, "early_stop": early}


def _try_deflection_ladder_candidate(
    state: dict,
    *,
    label: str,
    updates: dict | None,
    base_util: float,
    ladder_name: str = "deflection_ladder",
) -> dict | None:
    if not updates:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=None,
            decision="rejected",
            reason="empty_updates",
            metric_name="deflection_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    if _updates_match_state(state, updates):
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="noop_vs_state",
            metric_name="deflection_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    ev = _evaluate_deflection_with_state(_merge_guidance_state(state, updates))
    if not ev or ev.get("util") is None:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="deflection_eval_none",
            metric_name="deflection_util",
            metric_before=base_util,
            metric_after=None,
        )
        return None
    nu = float(ev.get("util", 0.0) or 0.0)
    if nu >= base_util - 1e-9:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=label,
            candidate_updates=updates,
            decision="rejected",
            reason="no_improvement",
            metric_name="deflection_util",
            metric_before=base_util,
            metric_after=nu,
        )
        return None
    early = nu <= GUIDANCE_LADDER_EARLY_STOP_UTIL and nu <= 1.0 + 1e-9
    _log_guidance_ladder_debug(
        ladder_name,
        candidate_label=label,
        candidate_updates=updates,
        decision="accepted",
        reason="improves_deflection_util",
        metric_name="deflection_util",
        metric_before=base_util,
        metric_after=nu,
        early_stop=early,
    )
    return {"label": label, "updates": updates, "util_after": nu, "early_stop": early}


def _deflection_ladder_sustained_load_updates(state: dict) -> dict | None:
    for key in ("g_udl_kNm_per_m", "g_kNm", "g_line_kNm"):
        v = _float_from_state(state, key, 0.0)
        if v > 1e-9:
            return {key: float(v * 0.92)}
    return None


def _pick_deflection_ladder_first_improvement(state: dict, *, base_util: float) -> dict | None:
    ladder_name = "deflection_ladder"
    for d in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
        payload = {"delta_mm": float(d)}
        u = _guidance_action_updates("increase_depth", payload, state=state)
        label = f"Increase depth D by {int(d)} mm"
        r = _try_deflection_ladder_candidate(
            state,
            label=label,
            updates=u,
            base_util=base_util,
            ladder_name=ladder_name,
        )
        if r:
            r["kind"] = "geometry"
            r["action_type"] = "increase_depth"
            r["payload"] = payload
            r["before_after"] = _describe_guidance_step(
                state,
                _merge_guidance_state(state, u),
                "increase_depth",
                u,
            )
            return r

    for d in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
        payload = {"delta_mm": float(d)}
        u = _guidance_action_updates("increase_width", payload, state=state)
        label = f"Increase section width by {int(d)} mm"
        r = _try_deflection_ladder_candidate(
            state,
            label=label,
            updates=u,
            base_util=base_util,
            ladder_name=ladder_name,
        )
        if r:
            r["kind"] = "geometry"
            r["action_type"] = "increase_width"
            r["payload"] = payload
            r["before_after"] = _describe_guidance_step(
                state,
                _merge_guidance_state(state, u),
                "increase_width",
                u,
            )
            return r

    lu = _deflection_ladder_sustained_load_updates(state)
    r = _try_deflection_ladder_candidate(
        state,
        label="Reduce sustained dead load (one small step, ~8%)",
        updates=lu,
        base_util=base_util,
        ladder_name=ladder_name,
    )
    if r:
        r["kind"] = "sustained_load"
        r["before_after"] = _describe_guidance_step(
            state,
            _merge_guidance_state(state, lu),
            "deflection_reduce_sustained_load",
            lu,
        )
        return r

    return None


__all__ = [
    "bind_serviceability_ladder_candidate_dependencies",
    "_try_crack_ladder_candidate",
    "_try_deflection_ladder_candidate",
    "_deflection_ladder_sustained_load_updates",
    "_pick_deflection_ladder_first_improvement",
]
