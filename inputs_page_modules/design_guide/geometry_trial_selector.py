"""Geometry trial selection coordination for the Inputs page Design Guide."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, MutableMapping


_GEOMETRY_TRIAL_SELECTOR_DEPENDENCIES: tuple[str, ...] = (
    "DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY",
    "GUIDANCE_LADDER_EARLY_STOP_UTIL",
    "GUIDANCE_SHALLOW_CORRECTION_METRIC_MARGIN",
    "GUIDANCE_SHALLOW_CORRECTION_MIN_DEPTH_DROP_MM",
    "GUIDANCE_SHALLOW_CORRECTION_MIN_D_OVER_TEMPLATE_MM",
    "SHARED_DEFAULTS",
    "_describe_guidance_step",
    "_design_guide_effective_reference_depth",
    "_design_optimisation_goal",
    "_evaluate_bending_with_bottom_state",
    "_evaluate_crack_with_state",
    "_evaluate_deflection_with_state",
    "_evaluate_shear_with_state",
    "_collect_design_overview",
    "_geometry_trial_delta_mm_total",
    "_geometry_width_depth_trial_specs",
    "_guidance_action_updates",
    "_log_guidance_ladder_debug",
    "_merge_guidance_state",
    "_parse_util_value",
    "_resolve_geometry_width_context",
    "_shallower_beam_correction_trial_updates",
    "_updates_match_state",
    "st",
)


@dataclass(frozen=True)
class GeometryTrialSelectorRuntime:
    geometry_trial_debug_key: str
    ladder_early_stop_util: float
    shallow_correction_metric_margin: float
    shallow_correction_min_depth_drop_mm: float
    shallow_correction_min_d_over_template_mm: float
    shared_defaults: dict
    describe_guidance_step: Callable[..., Any]
    design_guide_effective_reference_depth: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    evaluate_bending_with_bottom_state: Callable[..., Any]
    evaluate_crack_with_state: Callable[..., Any]
    evaluate_deflection_with_state: Callable[..., Any]
    evaluate_shear_with_state: Callable[..., Any]
    collect_design_overview: Callable[..., Any]
    geometry_trial_delta_mm_total: Callable[..., Any]
    geometry_width_depth_trial_specs: Callable[..., Any]
    guidance_action_updates: Callable[..., Any]
    log_guidance_ladder_debug: Callable[..., Any]
    merge_guidance_state: Callable[..., Any]
    parse_util_value: Callable[..., Any]
    resolve_geometry_width_context: Callable[..., Any]
    shallower_beam_correction_trial_updates: Callable[..., Any]
    updates_match_state: Callable[..., Any]
    session_state: MutableMapping[str, Any]


def bind_geometry_trial_selector_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _GEOMETRY_TRIAL_SELECTOR_DEPENDENCIES
            if name in namespace
        }
    )


def _read_metric_for_geometry_trial(
    state: dict,
    *,
    metric: str,
    bending_mode: str = "governing",
    runtime: GeometryTrialSelectorRuntime | None = None,
) -> float | None:
    """Read an existing overview metric for geometry-trial ranking."""

    if runtime is not None:
        _evaluate_bending_with_bottom_state = (
            runtime.evaluate_bending_with_bottom_state
        )
        _evaluate_crack_with_state = runtime.evaluate_crack_with_state
        _evaluate_deflection_with_state = (
            runtime.evaluate_deflection_with_state
        )
        _evaluate_shear_with_state = runtime.evaluate_shear_with_state
        _collect_design_overview = runtime.collect_design_overview
        _parse_util_value = runtime.parse_util_value
    else:
        namespace = globals()
        _evaluate_bending_with_bottom_state = namespace[
            "_evaluate_bending_with_bottom_state"
        ]
        _evaluate_crack_with_state = namespace["_evaluate_crack_with_state"]
        _evaluate_deflection_with_state = namespace[
            "_evaluate_deflection_with_state"
        ]
        _evaluate_shear_with_state = namespace["_evaluate_shear_with_state"]
        _collect_design_overview = namespace["_collect_design_overview"]
        _parse_util_value = namespace["_parse_util_value"]

    metric_key = str(metric or "").strip().lower()
    mode = str(bending_mode or "").strip().lower()
    if metric_key == "crack":
        crack = _evaluate_crack_with_state(state)
        return _parse_util_value(dict(crack or {}).get("util"))
    if metric_key == "deflection":
        deflection = _evaluate_deflection_with_state(state)
        return _parse_util_value(dict(deflection or {}).get("util"))
    if metric_key == "shear":
        shear = _evaluate_shear_with_state(state)
        return _parse_util_value(dict(shear or {}).get("web_util") or dict(shear or {}).get("util"))
    if metric_key == "bending" and mode != "ductility":
        bending = _evaluate_bending_with_bottom_state(state)
        value = _parse_util_value(
            dict(bending or {}).get("summary_util")
            or dict(bending or {}).get("util")
            or dict(bending or {}).get("governing_util")
        )
        if value is not None:
            return value

    try:
        overview = _collect_design_overview(dict(state or {}))
    except Exception:
        overview = {}
    packs = dict(overview.get("packs") or {})
    utils = dict(overview.get("utils") or {})

    if metric_key == "bending" and mode == "ductility":
        for row in list(dict(packs.get("bending") or {}).get("rows") or []):
            title = str(row.get("title") or "").strip().lower()
            uid = str(row.get("uid") or "").strip().lower()
            if "duct" in title or "duct" in uid:
                return _parse_util_value(row.get("util"))

    if metric_key in {"bending", "shear", "crack", "deflection"}:
        value = _parse_util_value(utils.get(metric_key))
        if value is not None:
            return value

    if metric_key == "bending":
        bending_pack = dict(packs.get("bending") or {})
        if mode in {"positive", "pos", "sagging"}:
            return _parse_util_value(dict(bending_pack.get("bending_pos") or {}).get("util"))
        if mode in {"negative", "neg", "hogging"}:
            return _parse_util_value(dict(bending_pack.get("bending_neg") or {}).get("util"))
        return _parse_util_value(bending_pack.get("summary_util"))
    if metric_key == "shear":
        shear_pack = dict(packs.get("shear") or {})
        return _parse_util_value(
            shear_pack.get("summary_governing_util")
            or shear_pack.get("summary_util")
        )
    if metric_key == "crack":
        return _parse_util_value(dict(packs.get("crack") or {}).get("summary_util"))
    if metric_key == "deflection":
        return _parse_util_value(dict(packs.get("deflection") or {}).get("summary_util_total"))
    return None


def _choose_geometry_trial_for_metric(
    state: dict,
    *,
    metric: str,
    baseline_util: float | None = None,
    bending_mode: str = "governing",
    ladder_name: str = "geometry_trial",
    runtime: GeometryTrialSelectorRuntime | None = None,
) -> dict | None:
    if runtime is not None:
        DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY = (
            runtime.geometry_trial_debug_key
        )
        GUIDANCE_LADDER_EARLY_STOP_UTIL = runtime.ladder_early_stop_util
        GUIDANCE_SHALLOW_CORRECTION_METRIC_MARGIN = (
            runtime.shallow_correction_metric_margin
        )
        GUIDANCE_SHALLOW_CORRECTION_MIN_DEPTH_DROP_MM = (
            runtime.shallow_correction_min_depth_drop_mm
        )
        GUIDANCE_SHALLOW_CORRECTION_MIN_D_OVER_TEMPLATE_MM = (
            runtime.shallow_correction_min_d_over_template_mm
        )
        SHARED_DEFAULTS = runtime.shared_defaults
        _describe_guidance_step = runtime.describe_guidance_step
        _design_guide_effective_reference_depth = (
            runtime.design_guide_effective_reference_depth
        )
        _design_optimisation_goal = runtime.design_optimisation_goal
        _geometry_trial_delta_mm_total = (
            runtime.geometry_trial_delta_mm_total
        )
        _geometry_width_depth_trial_specs = (
            runtime.geometry_width_depth_trial_specs
        )
        _guidance_action_updates = runtime.guidance_action_updates
        _log_guidance_ladder_debug = runtime.log_guidance_ladder_debug
        _merge_guidance_state = runtime.merge_guidance_state
        _resolve_geometry_width_context = (
            runtime.resolve_geometry_width_context
        )
        _shallower_beam_correction_trial_updates = (
            runtime.shallower_beam_correction_trial_updates
        )
        _updates_match_state = runtime.updates_match_state
        session_state = runtime.session_state
    else:
        namespace = globals()
        DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY = namespace[
            "DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY"
        ]
        GUIDANCE_LADDER_EARLY_STOP_UTIL = namespace[
            "GUIDANCE_LADDER_EARLY_STOP_UTIL"
        ]
        GUIDANCE_SHALLOW_CORRECTION_METRIC_MARGIN = namespace[
            "GUIDANCE_SHALLOW_CORRECTION_METRIC_MARGIN"
        ]
        GUIDANCE_SHALLOW_CORRECTION_MIN_DEPTH_DROP_MM = namespace[
            "GUIDANCE_SHALLOW_CORRECTION_MIN_DEPTH_DROP_MM"
        ]
        GUIDANCE_SHALLOW_CORRECTION_MIN_D_OVER_TEMPLATE_MM = namespace[
            "GUIDANCE_SHALLOW_CORRECTION_MIN_D_OVER_TEMPLATE_MM"
        ]
        SHARED_DEFAULTS = namespace["SHARED_DEFAULTS"]
        _describe_guidance_step = namespace["_describe_guidance_step"]
        _design_guide_effective_reference_depth = namespace[
            "_design_guide_effective_reference_depth"
        ]
        _design_optimisation_goal = namespace["_design_optimisation_goal"]
        _geometry_trial_delta_mm_total = namespace[
            "_geometry_trial_delta_mm_total"
        ]
        _geometry_width_depth_trial_specs = namespace[
            "_geometry_width_depth_trial_specs"
        ]
        _guidance_action_updates = namespace["_guidance_action_updates"]
        _log_guidance_ladder_debug = namespace[
            "_log_guidance_ladder_debug"
        ]
        _merge_guidance_state = namespace["_merge_guidance_state"]
        _resolve_geometry_width_context = namespace[
            "_resolve_geometry_width_context"
        ]
        _shallower_beam_correction_trial_updates = namespace[
            "_shallower_beam_correction_trial_updates"
        ]
        _updates_match_state = namespace["_updates_match_state"]
        session_state = namespace["st"].session_state

    def read_metric(st: dict) -> float | None:
        return _read_metric_for_geometry_trial(
            st,
            metric=metric,
            bending_mode=bending_mode,
            runtime=runtime,
        )

    base_u = read_metric(state) if baseline_util is None else float(baseline_util)
    if base_u is None or not math.isfinite(base_u):
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label="(init)",
            candidate_updates=None,
            decision="rejected",
            reason="missing_baseline_metric",
            metric_name=metric,
            metric_before=None,
            metric_after=None,
        )
        return None

    best: dict | None = None
    best_key: tuple | None = None
    for label, atype, payload in _geometry_width_depth_trial_specs():
        updates = _guidance_action_updates(atype, payload, state=state)
        if not updates or _updates_match_state(state, updates):
            _log_guidance_ladder_debug(
                ladder_name,
                candidate_label=label,
                candidate_updates=updates,
                decision="rejected",
                reason="noop",
                metric_name=metric,
                metric_before=base_u,
                metric_after=None,
            )
            continue
        trial_state = _merge_guidance_state(state, updates)
        nu = read_metric(trial_state)
        if nu is None or not math.isfinite(nu):
            _log_guidance_ladder_debug(
                ladder_name,
                candidate_label=label,
                candidate_updates=updates,
                decision="rejected",
                reason="missing_metric_after",
                metric_name=metric,
                metric_before=base_u,
                metric_after=None,
            )
            continue
        if nu >= base_u - 1e-9:
            _log_guidance_ladder_debug(
                ladder_name,
                candidate_label=label,
                candidate_updates=updates,
                decision="rejected",
                reason="no_improvement_vs_baseline",
                metric_name=metric,
                metric_before=base_u,
                metric_after=nu,
            )
            continue
        passes = nu <= 1.0 + 1e-9
        delta_tot = _geometry_trial_delta_mm_total(state, updates)
        d0 = float(state.get("D", 0.0) or 0.0)
        d_after = float(trial_state.get("D", d0) or d0)
        depth_growth = max(d_after - d0, 0.0)
        wkey, _, w0 = _resolve_geometry_width_context(state)
        w0 = float(w0 or 0.0)
        if wkey in updates:
            w1 = float(updates[wkey] or 0.0)
        else:
            w1 = w0
        width_growth = max(w1 - w0, 0.0)
        if _design_optimisation_goal(state) == "shallower_beam":
            key = (0 if passes else 1, round(float(nu), 2), depth_growth, width_growth, delta_tot)
        else:
            key = (0 if passes else 1, delta_tot, nu)
        if best_key is None or key < best_key:
            best_key = key
            after_state = trial_state
            ba = _describe_guidance_step(state, after_state, atype, updates)
            best = {
                "label": label,
                "action_type": atype,
                "payload": dict(payload),
                "updates": updates,
                "util_before": base_u,
                "util_after": nu,
                "before_after": ba,
            }

    cur_d = float(state.get("D", 0.0) or 0.0)
    ref_d = _design_guide_effective_reference_depth(state)
    tmpl_d = float(SHARED_DEFAULTS.get("D", 600.0))
    trial_debug: dict = {
        "correction_candidate_considered": False,
        "correction_candidate_summary": None,
        "correction_candidate_score": None,
        "correction_candidate_won": False,
        "reference_D": ref_d,
        "current_D": cur_d,
        "D_offset_from_reference": round(cur_d - ref_d, 3),
        "goal_alignment_penalty": round(max(0.0, cur_d - ref_d) / 100.0, 3),
    }
    if (
        best
        and _design_optimisation_goal(state) == "shallower_beam"
        and metric == "bending"
    ):
        best_upd = best.get("updates") or {}
        ts_best = _merge_guidance_state(state, best_upd)
        d_after_best = float(ts_best.get("D", cur_d) or cur_d)
        wkey, _, w0 = _resolve_geometry_width_context(state)
        w0 = float(w0 or 0.0)
        w_after = float(best_upd[wkey]) if wkey in best_upd else w0
        depth_growth_best = max(d_after_best - cur_d, 0.0)
        width_growth_best = max(w_after - w0, 0.0)
        growth_continuation = (
            depth_growth_best < 1e-9
            and width_growth_best > 1e-9
            and cur_d > tmpl_d + GUIDANCE_SHALLOW_CORRECTION_MIN_D_OVER_TEMPLATE_MM
        )
        if growth_continuation:
            trial_debug["correction_candidate_considered"] = True
            best_nu = float(best.get("util_after", 99.0) or 99.0)
            pick_upd: dict | None = None
            pick_nu: float | None = None
            pick_label: str | None = None
            pick_d = cur_d
            for clabel, cupd in _shallower_beam_correction_trial_updates(state):
                if _updates_match_state(state, cupd):
                    continue
                trial_m = _merge_guidance_state(state, cupd)
                nu_c = read_metric(trial_m)
                if nu_c is None or not math.isfinite(nu_c):
                    continue
                d_trial = float(trial_m.get("D", cur_d) or cur_d)
                if cur_d - d_trial < GUIDANCE_SHALLOW_CORRECTION_MIN_DEPTH_DROP_MM - 1e-9:
                    continue
                if nu_c > 1.0 + 1e-9:
                    continue
                if nu_c > best_nu + GUIDANCE_SHALLOW_CORRECTION_METRIC_MARGIN:
                    continue
                if nu_c >= base_u - 1e-9:
                    continue
                if pick_nu is None or nu_c < float(pick_nu) - 1e-9 or (
                    abs(nu_c - float(pick_nu)) < 1e-9 and d_trial < pick_d
                ):
                    pick_upd = dict(cupd)
                    pick_nu = float(nu_c)
                    pick_label = str(clabel)
                    pick_d = d_trial
            if pick_upd is not None and pick_nu is not None and pick_label is not None:
                after_c = _merge_guidance_state(state, pick_upd)
                ba_c = _describe_guidance_step(
                    state, after_c, "apply_geometry_recommendation", pick_upd,
                )
                best = {
                    "label": pick_label,
                    "action_type": "apply_geometry_recommendation",
                    "payload": {"updates": dict(pick_upd)},
                    "updates": dict(pick_upd),
                    "util_before": base_u,
                    "util_after": float(pick_nu),
                    "before_after": ba_c,
                }
                trial_debug["correction_candidate_won"] = True
                trial_debug["correction_candidate_score"] = float(pick_nu)
                trial_debug["correction_candidate_summary"] = pick_label
            else:
                trial_debug["correction_candidate_summary"] = (
                    "no compliant correction within util margin vs width-growth trial"
                )
    session_state[DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY] = trial_debug

    if best:
        ua = float(best.get("util_after", 99.0) or 99.0)
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label=str(best.get("label") or ""),
            candidate_updates=best.get("updates"),
            decision="accepted",
            reason="best_scored_trial",
            metric_name=metric,
            metric_before=base_u,
            metric_after=ua,
            early_stop=bool(ua <= GUIDANCE_LADDER_EARLY_STOP_UTIL),
        )
    else:
        _log_guidance_ladder_debug(
            ladder_name,
            candidate_label="(none)",
            candidate_updates=None,
            decision="rejected",
            reason="no_candidate_improved",
            metric_name=metric,
            metric_before=base_u,
            metric_after=None,
        )
    return best


__all__ = [
    "GeometryTrialSelectorRuntime",
    "bind_geometry_trial_selector_dependencies",
    "_read_metric_for_geometry_trial",
    "_choose_geometry_trial_for_metric",
]
