"""Typed, application-owned fast candidate evaluation kernel."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FastCandidateEvaluationRuntime:
    bottom_bar_count: Callable[[dict, dict | None], int]
    bottom_row_count: Callable[[dict], int]
    candidate_bottom_updates: Callable[[dict], dict | None]
    candidate_shear_updates: Callable[[dict], dict]
    design_width: Callable[[dict], float]
    effective_bottom: Callable[[dict, dict | None], dict]
    evaluate_bending: Callable[[dict, dict | None], dict | None]
    evaluate_crack: Callable[..., dict | None]
    evaluate_deflection: Callable[..., dict | None]
    evaluate_shear: Callable[..., dict | None]
    float_from_state: Callable[[dict, str, float], float]
    int_from_state: Callable[[dict, str, int], int]
    reo_congestion: Callable[[dict, dict | None], float]
    resolve_actions: Callable[[dict, dict | None], dict]
    status_from_util: Callable[[float | None], str]
    uls_action: Callable[[dict, str], float]


def evaluate_candidate_fast(
    candidate_state: dict,
    context: dict,
    *,
    runtime: FastCandidateEvaluationRuntime,
) -> dict | None:
    seed_overview = (
        context.get("reference_overview")
        or context.get("seed_overview")
        or {"statuses": {}, "utils": {}, "packs": {}}
    )
    eval_state = runtime.resolve_actions(candidate_state, context.get("actions"))
    bottom_updates = runtime.candidate_bottom_updates(eval_state)
    shear_updates = runtime.candidate_shear_updates(eval_state)
    crack = runtime.evaluate_crack(eval_state, bottom_updates=bottom_updates)
    deflection = runtime.evaluate_deflection(eval_state, bottom_updates=bottom_updates)
    bending = runtime.evaluate_bending(eval_state, bottom_updates)
    shear = runtime.evaluate_shear(
        eval_state,
        bottom_updates=bottom_updates,
        shear_updates=shear_updates,
    )

    flexural_util = None
    ductility_util = None
    min_steel_util = None
    bending_util = None
    bending_status = "—"
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
            u
            for u in (flexural_util, ductility_util, min_steel_util)
            if u is not None and not math.isnan(u)
        ]
        if governs:
            if any(u > 1.0 for u in governs):
                bending_status = "FAIL"
            elif any(u >= 0.95 for u in governs):
                bending_status = "NEAR LIMIT"
            else:
                bending_status = "PASS"
        else:
            bending_status = "—"

    shear_util = None
    shear_status = "—"
    if shear:
        shear_candidates = []
        for value in (shear.get("util"), shear.get("web_util")):
            try:
                resolved = float(value)
            except Exception:
                continue
            if not math.isnan(resolved):
                shear_candidates.append(resolved)
        shear_util = max(shear_candidates, default=None)
        shear_status = runtime.status_from_util(shear_util)

    statuses = {
        "bending": bending_status,
        "shear": shear_status,
        "crack": runtime.status_from_util(float(crack.get("util", 0.0) or 0.0)) if crack is not None else str(seed_overview.get("statuses", {}).get("crack", "PASS") or "PASS"),
        "deflection": str(deflection.get("status") or "PASS") if deflection is not None else str(seed_overview.get("statuses", {}).get("deflection", "PASS") or "PASS"),
    }
    utils = {
        "bending": bending_util,
        "shear": shear_util,
        "crack": float(crack.get("util", 0.0) or 0.0) if crack is not None else seed_overview.get("utils", {}).get("crack"),
        "deflection": deflection.get("util") if deflection is not None else seed_overview.get("utils", {}).get("deflection"),
    }
    tracked_statuses = [status for status in statuses.values() if status not in ("—", "")]
    bend_pack: dict = {}
    if bending:
        phi_cap = float(bending.get("phi_Mu_cap", 0.0) or 0.0)
        mu_star = float(runtime.uls_action(eval_state, "M"))
        dem_util = (mu_star / phi_cap) if phi_cap > 1e-9 else None
        bend_pack = {
            "summary_phiMu_kNm": phi_cap,
            "summary_Mu_star_kNm": mu_star,
            "summary_util": dem_util,
            "rows": [],
        }
    overview = {
        "packs": {"bending": bend_pack} if bend_pack else {},
        "statuses": statuses,
        "utils": utils,
        "any_fail": any(status == "FAIL" for status in tracked_statuses),
        "any_warn": any(status == "NEAR LIMIT" for status in tracked_statuses),
        "all_key_pass": bool(tracked_statuses) and all(status == "PASS" for status in tracked_statuses),
        "worst_util": max((util for util in utils.values() if util is not None), default=0.0),
    }
    bottom_state = runtime.effective_bottom(eval_state, bottom_updates)
    width = runtime.design_width(eval_state)
    depth = runtime.float_from_state(eval_state, "D", 600.0)
    shear_density = (
        runtime.int_from_state(eval_state, "lig_legs", 0)
        * max(runtime.int_from_state(eval_state, "lig_d", 0), 1) ** 2
    ) / max(runtime.float_from_state(eval_state, "s_lig", 200.0), 1.0)
    fail_count = sum(1 for status in overview["statuses"].values() if status == "FAIL")
    return {
        "source": "fast_eval",
        "label": "Fast Eval",
        "action_type": None,
        "updates": {},
        "state": dict(candidate_state),
        "overview": overview,
        "bottom_state": bottom_state,
        "width": float(width),
        "depth": float(depth),
        "Ast_bot": float(bottom_state.get("Ast_bot", 0.0) or 0.0),
        "Ast_top": runtime.float_from_state(eval_state, "Ast_top", 0.0),
        "bar_count": runtime.bottom_bar_count(eval_state, bottom_state),
        "row_count": runtime.bottom_row_count(eval_state),
        "reo_congestion_index": runtime.reo_congestion(eval_state, bottom_state),
        "shear_density": float(shear_density),
        "bending_components": {
            "flexural_util": flexural_util if bending else None,
            "ductility_util": ductility_util if bending else None,
            "min_steel_util": min_steel_util if bending else None,
        },
        "is_compliant": bool(overview["all_key_pass"]),
        "worst_util": float(overview["worst_util"] or 0.0),
        "fail_count": fail_count,
    }


__all__ = ["FastCandidateEvaluationRuntime", "evaluate_candidate_fast"]
