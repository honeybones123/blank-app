from typing import Dict, Any
import math


def build_shear_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure helper for Inputs + Shear page.
    Calls run_shear_calc() directly (no writes).
    """
    from shear_core import ShearInputs, run_shear_calc

    b = float(st_state.get("b") or 300.0)
    D = float(st_state.get("D") or 600.0)
    d = float(st_state.get("d") or 0.0)
    fc = float(st_state.get("fc") or 32.0)
    fsy = float(st_state.get("fsy") or 500.0)
    Ec = float(st_state.get("Ec") or 30000.0)
    Es = float(st_state.get("Es") or 200000.0)

    actions_uls = st_state.get("actions_uls", {})
    V_star = None
    M_star = None
    T_star = None
    if isinstance(actions_uls, dict):
        V_star = actions_uls.get("V")
        M_star = actions_uls.get("M")
        T_star = actions_uls.get("T")

    if V_star is None:
        V_star = float(
            st_state.get("Vu_star")
            or st_state.get("Vu_star_kN")
            or st_state.get("load_Vstar_proxy")
            or 0.0
        )
    if M_star is None:
        M_star = float(st_state.get("Mu_star") or 0.0)
    if T_star is None:
        T_star = float(st_state.get("Tu_star") or 0.0)

    lig_d = float(st_state.get("lig_d") or 10.0)
    legs = float(st_state.get("lig_legs") or 2.0)
    s_lig = float(st_state.get("s_lig") or 200.0)

    phi = float(st_state.get("phi_shear") or 0.75)

    kv_method = st_state.get("k_v_method", st_state.get("kv_method", "General εₓ-based (Cl. 8.2.4.2)"))
    use_general_kv = "ε" in str(kv_method) or "8.2.4.2" in str(kv_method)

    inp = ShearInputs(
        b=b, D=D, d=d, fc=fc, fsy=fsy, Ec=Ec, Es=Es,
        M_star=float(M_star or 0.0),
        V_star=float(V_star or 0.0),
        T_star=float(T_star or 0.0),
        N_star=float(st_state.get("N_star") or 0.0),
        P_v=float(st_state.get("P_star") or 0.0),
        phi=phi,
        sigma_cp=float(st_state.get("sigma_cp") or 0.0),
        A_st=float(st_state.get("Ast_bot") or 0.0),
        A_pt=0.0, f_po=0.0,
        A_ct=b * D / 2.0 if b and D else 0.0,
        d_g=float(st_state.get("d_g") or 20.0),
        lig_d=lig_d, legs=legs, s_lig=s_lig,
        use_general_kv=use_general_kv,
        sum_duct=0.0,
        k_d=0.0,
    )

    res = run_shear_calc(inp)

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

    rows = [
        {
            "uid": "shear_check8",
            "title": "Sectional shear capacity",
            "value": f"φVu = {res.phi_Vu:.1f} kN",
            "limit": f"V*eq = {res.V_eq:.1f} kN",
            "util": f"{util:.2f}" if util == util else "—",
            "status": status,
            "route_page": "shear",
        },
        {
            "uid": "shear_check1",
            "title": "Torsion cracking check",
            "value": f"Torsion design is {torsion_text}",
            "limit": f"0.25 φ Tcr = {res.torsion_required_limit:.1f} kNm",
            "util": "—",
            "status": "PASS" if not res.torsion_required else "FAIL",
            "route_page": "shear",
        },
        {
            "uid": "shear_check2",
            "title": "Equivalent shear $V_{eq}^*$",
            "value": f"V*eq = {res.V_eq:.1f} kN",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        },
        {
            "uid": "shear_check4",
            "title": "Longitudinal strain $\\varepsilon_x$",
            "value": f"εx = {res.eps_x:.5f}",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        },
        {
            "uid": "shear_check5",
            "title": "MCFT parameters (k_v and θ_v)",
            "value": f"k_v = {res.k_v:.3f}, θ_v = {res.theta_v_deg:.1f}°",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        },
        {
            "uid": "shear_check6",
            "title": "Concrete shear strength V_uc",
            "value": f"Vuc = {res.Vuc_kN:.1f} kN",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        },
        {
            "uid": "shear_check7",
            "title": "Steel shear strength V_s",
            "value": f"Vs = Vus = {res.Vus_kN:.1f} kN",
            "limit": "—",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        },
        {
            "uid": "shear_check9",
            "title": "Web-crushing strength",
            "value": f"φVu,max = {phi_Vu_max:.1f} kN",
            "limit": f"V*eq = {res.V_eq:.1f} kN",
            "util": f"{util_web:.2f}" if util_web == util_web else "—",
            "status": status_web,
            "route_page": "shear",
        },
    ]

    return {
        "summary_phiVu_kN": res.phi_Vu,
        "summary_Veq_kN": res.V_eq,
        "summary_util": util,
        "rows": rows,
    }
