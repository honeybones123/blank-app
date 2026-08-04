"""Engineering evaluation helpers for recommendation panels."""

from __future__ import annotations

import math
from typing import Any, Callable, Mapping

from bending_checks_helpers import compute_bending_capacity_from_state
from inputs_application.engineering_predicates import (
    shear_demands_negligible,
    shear_reinforcement_is_active,
)
from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.state_utils import float_from_state, updates_match_state
from calculations.bending import effective_depth_with_links_mm
from calculations.design_actions import resolve_design_actions_from_state as resolve_design_actions


GUIDANCE_SHEAR_UTIL_NEGLIGIBLE = 0.08
CANONICAL_NO_SHEAR_SLIG_MM = 200.0


def _int_value(state: Mapping[str, Any], key: str, default: int) -> int:
    try:
        return int(float(state.get(key, default) or 0))
    except (TypeError, ValueError):
        return int(default)


def effective_bottom_design_state(
    state: Mapping[str, Any],
    bottom_updates: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = dict(state or {})
    depth = float_from_state(source, "D", 600.0)
    cover = float_from_state(source, "cover_bot", 40.0)
    if bottom_updates:
        diameter = float(bottom_updates["db_bot_1"])
        count = int(bottom_updates["bot1_count"]) + int(bottom_updates["bot2_count"])
        steel_area = count * math.pi * diameter**2 / 4.0
    else:
        diameter = float_from_state(source, "db_bot", float_from_state(source, "db_bot_1", 20.0))
        count = _int_value(source, "nb_bot", 0)
        steel_area = float_from_state(source, "Ast_bot", 0.0)
    effective_depth = effective_depth_with_links_mm(
        D_mm=depth,
        cover_to_ligs_mm=cover,
        lig_diameter_mm=float_from_state(source, "lig_d", 10.0),
        bar_diameter_mm=diameter,
    )
    return {
        "Ast_bot": float(steel_area),
        "db_bot": float(diameter),
        "nb_bot": int(count),
        "d_centroid": float(effective_depth),
    }


def evaluate_bending_with_bottom_state(
    state: Mapping[str, Any],
    bottom_updates: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    bottom = effective_bottom_design_state(state, bottom_updates)
    _, _, width = resolve_geometry_width_context(state)
    depth = float_from_state(state, "D", 600.0)
    if width <= 0 or depth <= 0:
        return None
    evaluation_state = dict(state)
    evaluation_state.update(
        {
            "b": width,
            "Ast_bot": bottom["Ast_bot"],
            "db_bot": bottom["db_bot"],
            "nb_bot": bottom["nb_bot"],
            "d": bottom["d_centroid"],
        }
    )
    capacity = compute_bending_capacity_from_state(evaluation_state)
    results = dict(capacity.get("legacy") or {})
    results.update(bottom)
    return results


def _uls_action(state: Mapping[str, Any], action: str) -> float:
    resolved = resolve_design_actions(dict(state))
    resolved_key = {"M": "Mu", "V": "Vu", "N": "Nu", "T": "Tu", "P": "Pu"}.get(action)
    if resolved_key and resolved.get(resolved_key) is not None:
        return float(resolved[resolved_key])
    return float_from_state(
        state,
        {"M": "uls_Mstar", "V": "uls_Vstar", "N": "uls_Nstar", "T": "Tu_star", "P": "P_star"}[action],
        0.0,
    )


def evaluate_shear_with_state(
    state: Mapping[str, Any],
    *,
    bottom_updates: Mapping[str, Any] | None = None,
    shear_updates: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    from shear_core import ShearInputs, run_shear_calc

    bottom = effective_bottom_design_state(state, bottom_updates)
    _, _, width = resolve_geometry_width_context(state)
    depth = float_from_state(state, "D", 600.0)
    phi = float_from_state(state, "phi_shear", 0.75)
    shear = dict(state)
    shear.update(dict(shear_updates or {}))
    lig_d = float_from_state(shear, "lig_d", 10.0)
    legs = float_from_state(shear, "lig_legs", 2.0)
    spacing = float_from_state(shear, "s_lig", 200.0)
    kv_method = str(state.get("k_v_method", "General epsilon-based (Cl. 8.2.4.2)") or "")
    kd_option = str(state.get("k_d_option", "None (no ducts in web)") or "")
    kd = {
        "None (no ducts in web)": 0.0,
        "0.5 – steel ducts, grouted": 0.5,
        "0.8 – plastic ducts, grouted": 0.8,
        "1.2 – ungrouted ducts": 1.2,
        "0.5 â€“ steel ducts, grouted": 0.5,
        "0.8 â€“ plastic ducts, grouted": 0.8,
        "1.2 â€“ ungrouted ducts": 1.2,
        "Prestressing ducts present (apply k_d)": 0.5,
    }.get(kd_option, 0.0)
    result = run_shear_calc(
        ShearInputs(
            b=width,
            D=depth,
            d=bottom["d_centroid"],
            fc=float_from_state(state, "fc", 40.0),
            fsy=float_from_state(state, "fsy", 500.0),
            Ec=float_from_state(state, "Ec", 30000.0),
            Es=float_from_state(state, "Es", 200000.0),
            M_star=_uls_action(state, "M"),
            V_star=_uls_action(state, "V"),
            T_star=_uls_action(state, "T"),
            N_star=_uls_action(state, "N"),
            P_v=_uls_action(state, "P"),
            phi=phi,
            sigma_cp=0.0,
            A_st=bottom["Ast_bot"],
            A_pt=0.0,
            f_po=0.0,
            A_ct=float_from_state(state, "A_ct_default", width * depth / 2.0),
            d_g=float_from_state(state, "d_g", 20.0),
            lig_d=lig_d,
            legs=legs,
            s_lig=spacing,
            use_general_kv=("8.2.4.2" in kv_method or "epsilon" in kv_method.lower() or "ex" in kv_method.lower()),
            sum_duct=float_from_state(state, "n_ducts", 0.0) * float_from_state(state, "duct_dia", 0.0),
            k_d=float(kd),
        )
    )
    phi_vu_max = phi * result.Vu_max_kN
    return {
        "results": result,
        "util": result.V_eq / result.phi_Vu if result.phi_Vu > 0 else float("inf"),
        "web_util": result.V_eq / phi_vu_max if phi_vu_max > 0 else float("inf"),
        "lig_d": lig_d,
        "lig_legs": int(legs),
        "s_lig": spacing,
    }


def shear_results_allow_no_transverse_links(result, *, phi: float) -> bool:
    if result is None:
        return False
    if bool(getattr(result, "torsion_required", True)):
        return False
    if not bool(getattr(result, "shear_ok", False)):
        return False
    equivalent_shear = float(getattr(result, "V_eq", 0.0) or 0.0)
    concrete_capacity = float(getattr(result, "Vuc_kN", 0.0) or 0.0)
    if concrete_capacity <= 1e-12:
        return abs(equivalent_shear) <= 1e-6
    return equivalent_shear <= 0.5 * float(phi) * concrete_capacity + 1e-6


def shear_state_eligible_for_no_links(state: dict) -> bool:
    nominal_spacing = float(max(float_from_state(state, "s_lig", 200.0), 1.0))
    preview = evaluate_shear_with_state(
        state,
        shear_updates={
            "lig_legs": 0,
            "lig_d": 0,
            "s_lig": nominal_spacing,
        },
    )
    if not preview:
        return False
    return shear_results_allow_no_transverse_links(
        preview.get("results"),
        phi=float_from_state(state, "phi_shear", 0.75),
    )


def shear_no_links_candidate_passes_code(
    state: dict,
    candidate: dict | None,
) -> bool:
    if not candidate:
        return False
    candidate_state = dict(candidate.get("state") or {})
    if _int_value(candidate_state, "lig_legs", -1) != 0:
        return True
    nominal_spacing = float(
        max(float_from_state(candidate_state, "s_lig", 1.0), 1.0)
    )
    preview = evaluate_shear_with_state(
        candidate_state,
        shear_updates={
            "lig_legs": 0,
            "lig_d": 0,
            "s_lig": nominal_spacing,
        },
    )
    if not preview:
        return False
    return shear_results_allow_no_transverse_links(
        preview.get("results"),
        phi=float_from_state(state, "phi_shear", 0.75),
    )


def try_shear_no_demand_cleanup_recommendation(
    state: dict,
    overview: dict,
    actions: dict,
    *,
    evaluate_candidate_full: Callable[..., dict | None],
    merge_rank_trace: Callable[[dict], None],
) -> dict | None:
    """Return the canonical no-links cleanup when design actions are negligible."""

    if not shear_demands_negligible(actions):
        return None
    if not shear_reinforcement_is_active(state):
        return None
    shear_util = ((overview or {}).get("utils") or {}).get("shear")
    try:
        shear_util_value = float(shear_util) if shear_util is not None else 0.0
        if math.isnan(shear_util_value):
            shear_util_value = 0.0
    except (TypeError, ValueError):
        shear_util_value = 0.0
    if shear_util_value > GUIDANCE_SHEAR_UTIL_NEGLIGIBLE:
        return None

    cleanup_updates = {
        "lig_d": 0,
        "lig_legs": 0,
        "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
    }
    if updates_match_state(state, cleanup_updates):
        return None
    trial_state = dict(state)
    trial_state.update(cleanup_updates)
    candidate = evaluate_candidate_full(
        trial_state,
        source="shear_no_demand_cleanup_probe",
        updates=cleanup_updates,
    )
    if not candidate or not bool(candidate.get("is_compliant")):
        merge_rank_trace(
            {
                "shear_no_demand_cleanup": {
                    "accepted": False,
                    "reason": "non_compliant_when_links_cleared",
                }
            }
        )
        return None

    shear_preview = evaluate_shear_with_state(
        dict(candidate.get("state") or trial_state)
    ) or {}
    merge_rank_trace(
        {
            "shear_no_demand_cleanup": {
                "accepted": True,
                "removed_shear_links": True,
                "prior_lig_d": _int_value(state, "lig_d", 0),
                "prior_lig_legs": _int_value(state, "lig_legs", 0),
            }
        }
    )
    return {
        "updates": dict(cleanup_updates),
        "label": "Remove shear reinforcement (no shear/torsion design demand)",
        "util": float(
            ((candidate.get("overview") or {}).get("utils") or {}).get("shear", 0.0)
            or 0.0
        ),
        "web_util": float(shear_preview.get("web_util", 0.0) or 0.0),
        "phi_vu": float(shear_preview.get("phi_vu", 0.0) or 0.0),
        "veq": float(shear_preview.get("veq", 0.0) or 0.0),
        "score": 0.0,
        "severity_band": "cleanup",
        "candidate_type": "no_shear_design_cleanup",
    }


__all__ = [
    "CANONICAL_NO_SHEAR_SLIG_MM",
    "GUIDANCE_SHEAR_UTIL_NEGLIGIBLE",
    "effective_bottom_design_state",
    "evaluate_bending_with_bottom_state",
    "evaluate_shear_with_state",
    "shear_results_allow_no_transverse_links",
    "shear_no_links_candidate_passes_code",
    "shear_state_eligible_for_no_links",
    "try_shear_no_demand_cleanup_recommendation",
]
