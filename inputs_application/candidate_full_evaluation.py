"""Typed, application-owned full candidate evaluation coordination."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class FullCandidateEvaluationRuntime:
    session_state: Mapping[str, Any]
    stable_fingerprint: Callable[[Any], str]
    get_cache: Callable[[str, str], Any]
    set_cache: Callable[[str, str, Any], None]
    probe_record: Callable[..., None]
    build_projection: Callable[..., dict]
    bottom_bar_count: Callable[..., int]
    bottom_row_count: Callable[[dict], int]
    build_actions_context: Callable[[dict], dict]
    candidate_bottom_updates: Callable[[dict], dict | None]
    candidate_shear_updates: Callable[[dict], dict]
    overview_state: Callable[[dict, dict | None], dict]
    collect_overview: Callable[..., dict]
    design_width: Callable[[dict], float]
    effective_bottom: Callable[[dict, dict | None], dict]
    evaluate_bending: Callable[[dict, dict | None], dict | None]
    evaluate_crack: Callable[..., dict | None]
    evaluate_deflection: Callable[..., dict | None]
    evaluate_shear: Callable[..., dict | None]
    float_from_state: Callable[[dict, str, float], float]
    int_from_state: Callable[[dict, str, int], int]
    log_capacity_mismatch: Callable[..., None]
    phi_mu_capacity: Callable[[dict | None], float]
    reo_congestion: Callable[[dict, dict | None], float]
    status_from_util: Callable[[float | None], str]


def evaluate_candidate_full_for_app_bridge(
    candidate_state: dict,
    *,
    source: str = "full_eval",
    label: str | None = None,
    action_type: str | None = None,
    updates: dict | None = None,
    runtime: FullCandidateEvaluationRuntime,
) -> dict | None:
    eval_fp = runtime.stable_fingerprint(
        {
            "candidate_state": candidate_state,
            "source": source,
            "label": label,
            "action_type": action_type,
            "updates": updates,
        }
    )
    if bool(runtime.session_state.get("_dev_mode")):
        assert candidate_state is not runtime.session_state, (
            "evaluate_candidate_full: pass a dict snapshot, not st.session_state"
        )
    cached_eval = runtime.get_cache("evaluate_candidate_full", eval_fp)
    if isinstance(cached_eval, dict):
        runtime.probe_record(
            "candidate_preview_evaluation.evaluate_candidate_full",
            fingerprint=eval_fp,
            cache_hit=True,
        )
        return cached_eval
    runtime.probe_record(
        "candidate_preview_evaluation.evaluate_candidate_full",
        fingerprint=eval_fp,
        cache_hit=False,
    )

    bottom_updates = runtime.candidate_bottom_updates(candidate_state)
    shear_updates = runtime.candidate_shear_updates(candidate_state)
    overview_state = runtime.overview_state(
        candidate_state,
        bottom_updates,
    )
    crack = runtime.evaluate_crack(candidate_state, bottom_updates=bottom_updates)
    deflection = runtime.evaluate_deflection(candidate_state, bottom_updates=bottom_updates)
    base_overview = runtime.collect_overview(
        overview_state,
        context=runtime.build_actions_context(overview_state),
    )
    bending = runtime.evaluate_bending(candidate_state, bottom_updates)
    shear = runtime.evaluate_shear(
        candidate_state,
        bottom_updates=bottom_updates,
        shear_updates=shear_updates,
    )

    bending_util = None
    bending_status = "\u2014"
    flexural_util = None
    ductility_util = None
    min_steel_util = None
    if bending:
        flexural_util = float(bending.get("Mu_util", float("inf")))
        try:
            ductility_util = float(bending.get("ku", 0.0) or 0.0) / 0.36 if bending.get("ku") is not None else None
        except Exception:
            ductility_util = None
        try:
            as_min = float(bending.get("As_min", 0.0) or 0.0)
            ast = float(bending.get("Ast_bot", 0.0) or 0.0)
            if ast > 0.0 and as_min > 0.0:
                min_steel_util = as_min / ast
        except Exception:
            min_steel_util = None
        bending_util = flexural_util
        if bending_util is not None and math.isnan(bending_util):
            bending_util = None
        governs = [
            util
            for util in (flexural_util, ductility_util, min_steel_util)
            if util is not None and not math.isnan(util)
        ]
        if governs:
            if any(util > 1.0 for util in governs):
                bending_status = "FAIL"
            elif any(util >= 0.95 for util in governs):
                bending_status = "NEAR LIMIT"
            else:
                bending_status = "PASS"

    shear_util = None
    shear_status = "\u2014"
    base_shear_util = None
    try:
        base_shear_raw = ((base_overview.get("utils") or {}).get("shear"))
        base_shear_util = float(base_shear_raw) if base_shear_raw is not None else None
        if base_shear_util is not None and math.isnan(base_shear_util):
            base_shear_util = None
    except Exception:
        base_shear_util = None
    base_shear_status = str((base_overview.get("statuses") or {}).get("shear") or "\u2014")
    if base_shear_util is not None:
        shear_util = base_shear_util
        shear_status = base_shear_status
    elif shear:
        shear_candidates = []
        for value in (shear.get("util"), shear.get("web_util")):
            try:
                coerced = float(value)
            except Exception:
                continue
            if not math.isnan(coerced):
                shear_candidates.append(coerced)
        shear_util = max(shear_candidates, default=None)
        shear_status = runtime.status_from_util(shear_util)
    else:
        shear_status = base_shear_status

    statuses = dict(base_overview.get("statuses") or {})
    statuses["bending"] = bending_status
    statuses["shear"] = shear_status
    if crack is not None:
        crack_util = float(crack.get("util", 0.0) or 0.0)
        statuses["crack"] = runtime.status_from_util(crack_util)
    if deflection is not None:
        statuses["deflection"] = str(deflection.get("status") or "\u2014")
    utils = dict(base_overview.get("utils") or {})
    utils["bending"] = bending_util
    utils["shear"] = shear_util
    if crack is not None:
        utils["crack"] = float(crack.get("util", 0.0) or 0.0)
    if deflection is not None:
        utils["deflection"] = deflection.get("util")
    packs = dict(base_overview.get("packs") or {})
    direct_phi = runtime.phi_mu_capacity(bending)
    if bending:
        bending_pack = dict(packs.get("bending") or {})
        bending_pack["summary_phiMu_kNm"] = direct_phi
        packs["bending"] = bending_pack
    if deflection is not None:
        packs["deflection"] = dict(deflection.get("pack") or {})
    tracked_statuses = [status for status in statuses.values() if status not in ("\u2014", "")]
    overview = {
        "packs": packs,
        "statuses": statuses,
        "utils": utils,
        "any_fail": any(status == "FAIL" for status in tracked_statuses),
        "any_warn": any(status == "NEAR LIMIT" for status in tracked_statuses),
        "all_key_pass": bool(tracked_statuses) and all(status == "PASS" for status in tracked_statuses),
        "worst_util": max((util for util in utils.values() if util is not None), default=0.0),
    }
    pack_phi = float(((overview.get("packs") or {}).get("bending") or {}).get("summary_phiMu_kNm", 0.0) or 0.0)
    runtime.log_capacity_mismatch(
        pack_phi_knm=pack_phi,
        direct_phi_knm=direct_phi,
    )
    bottom_state = runtime.effective_bottom(candidate_state, bottom_updates)
    width = runtime.design_width(candidate_state)
    depth = runtime.float_from_state(candidate_state, "D", 600.0)
    shear_density = (
        runtime.int_from_state(candidate_state, "lig_legs", 0)
        * max(runtime.int_from_state(candidate_state, "lig_d", 0), 1) ** 2
    ) / max(runtime.float_from_state(candidate_state, "s_lig", 200.0), 1.0)
    evaluated_candidate = runtime.build_projection(
        candidate_state=candidate_state,
        source=source,
        label=label,
        action_type=action_type,
        updates=updates,
        overview=overview,
        bottom_state=bottom_state,
        width=width,
        depth=depth,
        ast_top=runtime.float_from_state(candidate_state, "Ast_top", 0.0),
        bar_count=runtime.bottom_bar_count(candidate_state, bottom_state),
        row_count=runtime.bottom_row_count(candidate_state),
        reo_congestion_index=runtime.reo_congestion(candidate_state, bottom_state),
        shear_density=shear_density,
        flexural_util=flexural_util,
        ductility_util=ductility_util,
        min_steel_util=min_steel_util,
        bending_present=bool(bending),
    )
    runtime.set_cache("evaluate_candidate_full", eval_fp, evaluated_candidate)
    return evaluated_candidate


__all__ = [
    "FullCandidateEvaluationRuntime",
    "evaluate_candidate_full_for_app_bridge",
]
