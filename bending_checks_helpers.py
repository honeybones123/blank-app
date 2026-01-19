from typing import Dict, Any


def build_bending_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure read-only helper.
    Uses bending_core's pure capacity calc so Inputs + Bending page always match.
    """
    b = float(st_state.get("b") or 0.0)
    D = float(st_state.get("D") or 0.0)
    fc = float(st_state.get("fc") or 0.0)
    fsy = float(st_state.get("fsy") or 0.0)
    phi = float(st_state.get("phi_bend") or 0.8)

    Ast = float(st_state.get("Ast_bot") or 0.0)
    d_input = float(st_state.get("d") or 0.0)

    cover_bot = float(st_state.get("cover_bot") or 0.0)
    db_bot = float(st_state.get("db_bot") or 0.0)
    nb_bot = float(st_state.get("nb_bot") or 0.0)
    rowgap_bot = float(st_state.get("rowgap_bot") or 0.0)

    actions_uls = st_state.get("actions_uls", {})
    Mu_star = None
    if isinstance(actions_uls, dict):
        Mu_star = actions_uls.get("M")
    if Mu_star is None:
        Mu_star = float(st_state.get("Mu_star") or st_state.get("load_Mstar_proxy") or 0.0)
    Mu_star = float(Mu_star or 0.0)

    from bending_core import _compute_bending_capacity_pure_impl

    results = _compute_bending_capacity_pure_impl(
        b=b,
        D=D,
        fc=fc,
        fsy=fsy,
        Ast=Ast,
        Mu_star=Mu_star,
        phi=phi,
        d_input=d_input,
        cover_bot=cover_bot,
        db_bot=db_bot,
        nb_bot=nb_bot,
        rowgap_bot=rowgap_bot,
    )

    phi_Mu = float(results.get("phi_Mu_cap", 0.0) or 0.0)
    util = float(results.get("Mu_util", 0.0) or 0.0)
    k_u = results.get("ku", None)
    As_min = results.get("As_min", None)
    Mcr = results.get("Mcr", None)

    def _status_from_util(u: float | None):
        if u is None:
            return "—"
        if u <= 1.0:
            return "NEAR LIMIT" if u >= 0.9 else "PASS"
        return "FAIL"

    ok = (util <= 1.0) if phi_Mu > 0 else None
    status = _status_from_util(util) if phi_Mu > 0 else "—"

    rows = [
        {
            "uid": "bend_strength",
            "title": "Flexural strength",
            "value": f"φMu = {phi_Mu:.1f} kNm",
            "limit": f"Mu* = {Mu_star:.1f} kNm",
            "util": f"{util:.2f}" if phi_Mu > 0 else "—",
            "status": status,
            "route_page": "bending",
        }
    ]

    if As_min is not None and As_min == As_min:
        rows.append({
            "uid": "bend_Asmin",
            "title": "Minimum tensile steel",
            "value": f"As = {Ast:.0f} mm²",
            "limit": f"As,min = {float(As_min):.0f} mm²",
            "util": f"{(Ast/As_min):.2f}" if As_min else "—",
            "status": "PASS" if As_min and Ast >= As_min else "FAIL",
            "route_page": "bending",
        })

    if (Mcr is not None) and (Mcr == Mcr) and phi_Mu > 0:
        Mu_min = 1.2 * float(Mcr)
        mu_min_util = (Mu_min / phi_Mu) if phi_Mu > 0 else None
        rows.append({
            "uid": "bend_min_strength",
            "title": "Minimum required design capacity (Mu,cap)_min",
            "value": f"φMu,cap = {phi_Mu:.1f} kNm",
            "limit": f"(Mu,cap)_min = {Mu_min:.1f} kNm",
            "util": f"{mu_min_util:.2f}" if mu_min_util is not None else "—",
            "status": _status_from_util(mu_min_util),
            "route_page": "bending",
        })

    if (k_u is not None) and (k_u == k_u):
        ku_lim = 0.36
        rows.append({
            "uid": "bend_duct",
            "title": "Ductility (k_u limit)",
            "value": f"k_u = {float(k_u):.3f}",
            "limit": f"k_u,lim = {ku_lim:.2f}",
            "util": f"{(float(k_u)/ku_lim):.2f}" if ku_lim else "—",
            "status": "PASS" if float(k_u) <= ku_lim else "FAIL",
            "route_page": "bending",
        })

    fs_outer = st_state.get("bending_sls_fs_outer")
    if fs_outer is None:
        fs_outer = st_state.get("sigma_s_sls")
    try:
        fs_outer = float(fs_outer) if fs_outer is not None else None
    except Exception:
        fs_outer = None

    fs_limit = (0.6 * fsy) if fsy > 0 else None
    fs_util = (fs_outer / fs_limit) if (fs_outer is not None and fs_limit) else None
    if fs_outer is not None and fs_limit:
        rows.append({
            "uid": "bend_sls_stress",
            "title": "Steel stresses at SLS (each layer)",
            "value": f"f_s,max = {fs_outer:.1f} MPa",
            "limit": f"0.6 fsy = {fs_limit:.1f} MPa",
            "util": f"{fs_util:.2f}" if fs_util is not None else "—",
            "status": _status_from_util(fs_util),
            "route_page": "bending",
        })

    return {
        "summary_phiMu_kNm": phi_Mu,
        "summary_Mu_star_kNm": Mu_star,
        "summary_util": util,
        "summary_Mcr_kNm": Mcr,
        "rows": rows,
    }
