from typing import Any, Dict

import math
import json
import time
import os

from engineering_check_ui import sync_legacy_value_limit
from state_and_helpers import resolve_design_actions

def _agent_dbg_log(message: str, data: dict, *, run_id: str, hypothesis_id: str) -> None:
    return


def _shear_calc_context(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """Shared extraction: live dict, actions, and ShearInputs (no I/O)."""
    from shear_core import ShearInputs

    b = float(st_state.get("b") or 300.0)
    D = float(st_state.get("D") or 600.0)
    d = float(st_state.get("d") or 0.0)
    fc = float(st_state.get("fc") or 32.0)
    fsy = float(st_state.get("fsy") or 500.0)
    Ec = float(st_state.get("Ec") or 30000.0)
    Es = float(st_state.get("Es") or 200000.0)

    actions = resolve_design_actions(st_state)
    M_star = float(actions["Mu"])
    V_star = float(actions["Vu"])
    T_star = float(actions["Tu"])
    N_star = float(actions["Nu"])
    P_v = float(actions["Pu"])

    lig_d = float(st_state.get("lig_d") or 10.0)
    # Preserve 0 legs / 0 spacing — ``0 or 2.0`` incorrectly upgraded "no shear ligs" to 2 legs.
    try:
        legs = float(st_state.get("lig_legs", 0.0))
    except (TypeError, ValueError):
        legs = 0.0
    try:
        s_lig = float(st_state.get("s_lig", 200.0))
    except (TypeError, ValueError):
        s_lig = 200.0

    phi = float(st_state.get("phi_shear") or 0.75)

    kv_method = st_state.get(
        "k_v_method",
        st_state.get(
            "kv_method",
            st_state.get(
                "shear_k_v_method",
                st_state.get("inputs_k_v_method", "General εₓ-based (Cl. 8.2.4.2)"),
            ),
        ),
    )
    use_general_kv = "ε" in str(kv_method) or "8.2.4.2" in str(kv_method)

    A_st = float(
        st_state.get("shear_A_st")
        or (4 * (math.pi * 20**2 / 4))
    )
    A_pt = float(st_state.get("shear_A_pt") or 0.0)
    f_po = float(st_state.get("shear_f_po") or 0.0)
    A_ct_default = float(st_state.get("A_ct_default") or ((b * D / 2.0) if b and D else 0.0))
    A_ct = float(st_state.get("shear_A_ct") or A_ct_default)
    d_g = float(st_state.get("shear_d_g") or st_state.get("d_g") or 20.0)
    sum_duct = float(st_state.get("shear_sum_duct") or st_state.get("sum_duct") or 0.0)
    kd_option_selected = str(
        st_state.get("shear_k_d_option")
        or st_state.get("k_d_option")
        or "None (no ducts in web)"
    )
    kd_value_map = {
        "None (no ducts in web)": 0.0,
        "0.5 – steel ducts, grouted": 0.5,
        "0.8 – plastic ducts, grouted": 0.8,
        "1.2 – ungrouted ducts": 1.2,
    }
    k_d = float(kd_value_map.get(kd_option_selected, 0.0))

    db_bot_1 = float(st_state.get("db_bot_1") or st_state.get("db_bot") or 20.0)
    db_bot_2 = float(st_state.get("db_bot_2") or db_bot_1)

    sigma_cp = float(st_state.get("sigma_cp") or 0.0)

    live_state: Dict[str, Any] = {
        "b": b,
        "D": D,
        "d": d,
        "fc": fc,
        "fsy": fsy,
        "Ec": Ec,
        "Es": Es,
        "Mu": M_star,
        "Vu": V_star,
        "Tu": T_star,
        "Nu": N_star,
        "Pu": P_v,
        "lig_d": lig_d,
        "lig_legs": legs,
        "s_lig": s_lig,
        "A_st": A_st,
        "A_pt": A_pt,
        "f_po": f_po,
        "A_ct": A_ct,
        "d_g": d_g,
        "sigma_cp": sigma_cp,
        "sum_duct": sum_duct,
        "db_bot_1": db_bot_1,
        "db_bot_2": db_bot_2,
    }

    inp = ShearInputs(
        b=b, D=D, d=d, fc=fc, fsy=fsy, Ec=Ec, Es=Es,
        M_star=float(M_star or 0.0),
        V_star=float(V_star or 0.0),
        T_star=float(T_star or 0.0),
        N_star=float(N_star or 0.0),
        P_v=float(P_v or 0.0),
        phi=phi,
        sigma_cp=sigma_cp,
        A_st=A_st,
        A_pt=A_pt,
        f_po=f_po,
        A_ct=A_ct,
        d_g=d_g,
        lig_d=lig_d, legs=legs, s_lig=s_lig,
        use_general_kv=use_general_kv,
        sum_duct=sum_duct,
        k_d=k_d,
    )

    return {
        "live_state": live_state,
        "actions_used": actions,
        "phi": phi,
        "k_d": k_d,
        "use_general_kv": use_general_kv,
        "inputs": inp,
    }


def build_live_canonical_shear_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot of shear-related session fields (geometry, actions, links, bars) for UI / debug."""
    return dict(_shear_calc_context(st_state)["live_state"])


def build_shear_calc_bundle_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """Single run of shear_core from session: live_state, actions, results, phi, k_d, use_general_kv."""
    from shear_core import run_shear_calc

    ctx = _shear_calc_context(st_state)
    res = run_shear_calc(ctx["inputs"])
    # When auto spacing is off, keep live run_shear_calc outputs so manual link spacing
    # (shear_s_lig → s_lig) drives φV_u in the UI. When on, prefer canonical outputs from
    # _compute_shear_capacity (zoned / realigned spacing).
    use_canonical = bool(st_state.get("shear_auto_design", False))
    canonical_phi_vu = st_state.get("phi_Vu_cap")
    if use_canonical and canonical_phi_vu not in (None, 0, 0.0):
        # region agent log
        _agent_dbg_log(
            "bundle results overridden from canonical state",
            {
                "raw_phi_Vu": float(res.phi_Vu),
                "state_phi_Vu_cap": float(st_state.get("phi_Vu_cap") or 0.0),
                "state_shear_Vus_kN": float(st_state.get("shear_Vus_kN") or 0.0),
                "state_theta_v_deg": float(st_state.get("shear_theta_v_deg") or 0.0),
            },
            run_id="post-fix",
            hypothesis_id="UI_FIX",
        )
        # endregion
        res.phi_Vu = float(st_state.get("phi_Vu_cap") or res.phi_Vu)
        res.Vuc_kN = float(st_state.get("shear_Vuc_kN") or res.Vuc_kN)
        res.Vus_kN = float(st_state.get("shear_Vus_kN") or res.Vus_kN)
        res.Vu_total_kN = float(st_state.get("shear_Vu_total_kN") or res.Vu_total_kN)
        res.k_v = float(st_state.get("shear_k_v") or res.k_v)
        res.theta_v_deg = float(st_state.get("shear_theta_v_deg") or res.theta_v_deg)
        res.theta_v_rad = float(st_state.get("shear_theta_v_rad") or res.theta_v_rad)
        res.shear_ok = bool(res.phi_Vu >= res.V_eq)
    return {
        "live_state": ctx["live_state"],
        "actions_used": ctx["actions_used"],
        "results": res,
        "phi": ctx["phi"],
        "k_d": ctx["k_d"],
        "use_general_kv": ctx["use_general_kv"],
    }


def build_shear_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure helper for Inputs + Shear page.
    Calls run_shear_calc() directly (no writes).
    """
    bundle = build_shear_calc_bundle_from_state(st_state)
    ctx = _shear_calc_context(st_state)
    inp = ctx["inputs"]
    actions = bundle["actions_used"]
    V_star = float(actions["Vu"])

    if abs(V_star - 0.0) < 1e-6:
        print("[DEBUG] Vu being treated as zero in shear table")

    res = bundle["results"]
    phi = float(bundle["phi"])

    def _status_from_util(u: float | None):
        if u is None:
            return "—"
        if u <= 1.0:
            return "NEAR LIMIT" if u >= 0.9 else "PASS"
        return "FAIL"

    util = (res.V_eq / res.phi_Vu) if res.phi_Vu > 0 else float("nan")
    ok = (util <= 1.0) if util == util else None
    status = _status_from_util(util) if ok is not None else "—"

    phi_Vu_max = phi * res.Vu_max_kN
    util_web = (res.V_eq / phi_Vu_max) if phi_Vu_max > 0 else float("nan")
    ok_web = (util_web <= 1.0) if util_web == util_web else None
    status_web = _status_from_util(util_web) if ok_web is not None else "—"

    torsion_text = "NOT REQUIRED" if not res.torsion_required else "REQUIRED"

    sectional_shear_capacity_row = sync_legacy_value_limit({
        "uid": "shear_check8",
        "title": "Sectional shear capacity",
        "capacity": f"φVu = {res.phi_Vu:.1f} kN",
        "action": f"V*eq = {res.V_eq:.1f} kN",
        "util": f"{util:.2f}" if util == util else "—",
        "status": status,
        "route_page": "shear",
    })
    torsion_cracking_row = sync_legacy_value_limit({
        "uid": "shear_check1",
        "title": "Torsion cracking check",
        "capacity": f"Reference: 0.25 φ T_cr = {res.torsion_required_limit:.1f} kNm",
        "action": f"Torsion design {torsion_text}",
        "util": "—",
        "status": "INFO",
        "is_informational": True,
        "route_page": "shear",
    })
    web_crushing_row = sync_legacy_value_limit({
        "uid": "shear_check9",
        "title": "Web-crushing strength",
        "capacity": f"φVu,max = {phi_Vu_max:.1f} kN",
        "action": f"V*eq = {res.V_eq:.1f} kN",
        "util": f"{util_web:.2f}" if util_web == util_web else "—",
        "status": status_web,
        "route_page": "shear",
    })

    summary_rows = [
        sectional_shear_capacity_row,
        torsion_cracking_row,
        web_crushing_row,
    ]

    mcft_detail_rows = [
        sync_legacy_value_limit({
            "uid": "shear_check2",
            "title": "Equivalent design shear",
            "capacity": "—",
            "action": f"V*eq = {res.V_eq:.1f} kN",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }),
        sync_legacy_value_limit({
            "uid": "shear_check4",
            "title": "Longitudinal strain",
            "capacity": "—",
            "action": f"εx = {res.eps_x:.5f}",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }),
        sync_legacy_value_limit({
            "uid": "shear_check5",
            "title": "Shear model parameters",
            "capacity": "—",
            "action": f"k_v = {res.k_v:.3f}, θ_v = {res.theta_v_deg:.1f}°",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }),
        sync_legacy_value_limit({
            "uid": "shear_check6",
            "title": "Concrete shear strength",
            "capacity": "—",
            "action": f"Vuc = {res.Vuc_kN:.1f} kN",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }),
        sync_legacy_value_limit({
            "uid": "shear_check7",
            "title": "Steel shear strength",
            "capacity": "—",
            "action": f"Vs = Vus = {res.Vus_kN:.1f} kN",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }),
    ]

    rows = list(summary_rows) + list(mcft_detail_rows)

    return {
        "summary_phiVu_kN": res.phi_Vu,
        "summary_Veq_kN": res.V_eq,
        "summary_Vstar_kN": float(V_star),
        "summary_util": util,
        "rows": rows,
        "summary_rows": summary_rows,
        "mcft_detail_rows": mcft_detail_rows,
        "actions_used": actions,
    }
