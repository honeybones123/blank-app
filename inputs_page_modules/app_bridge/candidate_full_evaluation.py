"""Full candidate evaluation coordination for the Inputs app bridge."""

from __future__ import annotations

import math
from typing import Any


_CANDIDATE_FULL_EVALUATION_DEPENDENCIES: tuple[str, ...] = (
    "st",
    "stable_fingerprint_for_payload",
    "get_rerun_pure_cache",
    "set_rerun_pure_cache",
    "ux_probe_record",
    "build_full_candidate_evaluation_result_projection",
    "_bottom_bar_count_from_state_for_app_bridge",
    "_bottom_row_count_from_state_for_app_bridge",
    "_build_design_actions_context_isolated_for_app_bridge",
    "_candidate_bottom_updates_for_app_bridge",
    "_candidate_shear_updates_for_app_bridge",
    "_candidate_state_with_effective_bottom_for_overview_for_app_bridge",
    "_collect_design_overview",
    "_design_width_value_for_app_bridge",
    "_effective_bottom_design_state_for_app_bridge",
    "_evaluate_bending_with_bottom_state_for_app_bridge",
    "_evaluate_crack_with_state_for_app_bridge",
    "_evaluate_deflection_with_state_for_app_bridge",
    "_evaluate_shear_with_state_for_app_bridge",
    "_float_from_state",
    "_int_from_state",
    "_log_phi_mu_capacity_mismatch_for_app_bridge",
    "_phi_mu_cap_knm_from_bending_for_app_bridge",
    "_reo_congestion_index_for_app_bridge",
    "_status_from_candidate_util_for_app_bridge",
)


def bind_candidate_full_evaluation_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _CANDIDATE_FULL_EVALUATION_DEPENDENCIES
            if name in namespace
        }
    )


def evaluate_candidate_full_for_app_bridge(
    candidate_state: dict,
    *,
    source: str = "full_eval",
    label: str | None = None,
    action_type: str | None = None,
    updates: dict | None = None,
) -> dict | None:
    eval_fp = stable_fingerprint_for_payload(
        {
            "candidate_state": candidate_state,
            "source": source,
            "label": label,
            "action_type": action_type,
            "updates": updates,
        }
    )
    if bool(st.session_state.get("_dev_mode")):
        assert candidate_state is not st.session_state, (
            "evaluate_candidate_full: pass a dict snapshot, not st.session_state"
        )
    cached_eval = get_rerun_pure_cache("evaluate_candidate_full", eval_fp)
    if isinstance(cached_eval, dict):
        ux_probe_record(
            "candidate_preview_evaluation.evaluate_candidate_full",
            fingerprint=eval_fp,
            cache_hit=True,
        )
        return cached_eval
    ux_probe_record(
        "candidate_preview_evaluation.evaluate_candidate_full",
        fingerprint=eval_fp,
        cache_hit=False,
    )

    bottom_updates = _candidate_bottom_updates_for_app_bridge(candidate_state)
    shear_updates = _candidate_shear_updates_for_app_bridge(candidate_state)
    overview_state = _candidate_state_with_effective_bottom_for_overview_for_app_bridge(
        candidate_state,
        bottom_updates,
    )
    crack = _evaluate_crack_with_state_for_app_bridge(candidate_state, bottom_updates=bottom_updates)
    deflection = _evaluate_deflection_with_state_for_app_bridge(candidate_state, bottom_updates=bottom_updates)
    base_overview = _collect_design_overview(
        overview_state,
        context=_build_design_actions_context_isolated_for_app_bridge(overview_state),
    )
    bending = _evaluate_bending_with_bottom_state_for_app_bridge(candidate_state, bottom_updates)
    shear = _evaluate_shear_with_state_for_app_bridge(
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
        shear_status = _status_from_candidate_util_for_app_bridge(shear_util)
    else:
        shear_status = base_shear_status

    statuses = dict(base_overview.get("statuses") or {})
    statuses["bending"] = bending_status
    statuses["shear"] = shear_status
    if crack is not None:
        crack_util = float(crack.get("util", 0.0) or 0.0)
        statuses["crack"] = _status_from_candidate_util_for_app_bridge(crack_util)
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
    direct_phi = _phi_mu_cap_knm_from_bending_for_app_bridge(bending)
    _log_phi_mu_capacity_mismatch_for_app_bridge(
        pack_phi_knm=pack_phi,
        direct_phi_knm=direct_phi,
    )
    bottom_state = _effective_bottom_design_state_for_app_bridge(candidate_state, bottom_updates)
    width = _design_width_value_for_app_bridge(candidate_state)
    depth = _float_from_state(candidate_state, "D", 600.0)
    shear_density = (
        _int_from_state(candidate_state, "lig_legs", 0)
        * max(_int_from_state(candidate_state, "lig_d", 0), 1) ** 2
    ) / max(_float_from_state(candidate_state, "s_lig", 200.0), 1.0)
    evaluated_candidate = build_full_candidate_evaluation_result_projection(
        candidate_state=candidate_state,
        source=source,
        label=label,
        action_type=action_type,
        updates=updates,
        overview=overview,
        bottom_state=bottom_state,
        width=width,
        depth=depth,
        ast_top=_float_from_state(candidate_state, "Ast_top", 0.0),
        bar_count=_bottom_bar_count_from_state_for_app_bridge(candidate_state, bottom_state),
        row_count=_bottom_row_count_from_state_for_app_bridge(candidate_state),
        reo_congestion_index=_reo_congestion_index_for_app_bridge(candidate_state, bottom_state),
        shear_density=shear_density,
        flexural_util=flexural_util,
        ductility_util=ductility_util,
        min_steel_util=min_steel_util,
        bending_present=bool(bending),
    )
    set_rerun_pure_cache("evaluate_candidate_full", eval_fp, evaluated_candidate)
    return evaluated_candidate
