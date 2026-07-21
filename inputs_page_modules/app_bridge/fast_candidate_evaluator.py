"""Fast candidate evaluation kernel for the Inputs app bridge."""

from __future__ import annotations

import math
from typing import Any


_FAST_CANDIDATE_EVALUATOR_DEPENDENCIES: tuple[str, ...] = (
    "_bottom_bar_count_from_state",
    "_bottom_row_count_from_state",
    "_candidate_bottom_updates",
    "_candidate_shear_updates",
    "_design_width_value",
    "_effective_bottom_design_state",
    "_evaluate_bending_with_bottom_state",
    "_evaluate_crack_with_state",
    "_evaluate_deflection_with_state",
    "_evaluate_shear_with_state",
    "_float_from_state",
    "_int_from_state",
    "_reo_congestion_index",
    "_state_with_resolved_auto_design_actions",
    "_status_from_candidate_util",
    "_uls_action_from_state",
)


def bind_fast_candidate_evaluator_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _FAST_CANDIDATE_EVALUATOR_DEPENDENCIES
            if name in namespace
        }
    )


def evaluate_candidate_fast(candidate_state: dict, context: dict) -> dict | None:
    seed_overview = (
        context.get("reference_overview")
        or context.get("seed_overview")
        or {"statuses": {}, "utils": {}, "packs": {}}
    )
    eval_state = _state_with_resolved_auto_design_actions(candidate_state, context.get("actions"))
    bottom_updates = _candidate_bottom_updates(eval_state)
    shear_updates = _candidate_shear_updates(eval_state)
    crack = _evaluate_crack_with_state(eval_state, bottom_updates=bottom_updates)
    deflection = _evaluate_deflection_with_state(eval_state, bottom_updates=bottom_updates)
    bending = _evaluate_bending_with_bottom_state(eval_state, bottom_updates)
    shear = _evaluate_shear_with_state(
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
        shear_status = _status_from_candidate_util(shear_util)

    statuses = {
        "bending": bending_status,
        "shear": shear_status,
        "crack": _status_from_candidate_util(float(crack.get("util", 0.0) or 0.0)) if crack is not None else str(seed_overview.get("statuses", {}).get("crack", "PASS") or "PASS"),
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
        mu_star = float(_uls_action_from_state(eval_state, "M"))
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
    bottom_state = _effective_bottom_design_state(eval_state, bottom_updates)
    width = _design_width_value(eval_state)
    depth = _float_from_state(eval_state, "D", 600.0)
    shear_density = (
        _int_from_state(eval_state, "lig_legs", 0)
        * max(_int_from_state(eval_state, "lig_d", 0), 1) ** 2
    ) / max(_float_from_state(eval_state, "s_lig", 200.0), 1.0)
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
        "Ast_top": _float_from_state(eval_state, "Ast_top", 0.0),
        "bar_count": _bottom_bar_count_from_state(eval_state, bottom_state),
        "row_count": _bottom_row_count_from_state(eval_state),
        "reo_congestion_index": _reo_congestion_index(eval_state, bottom_state),
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
