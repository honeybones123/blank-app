from typing import Any, Dict

from calculations.bending import compute_bending_capacity_from_state_values
from engineering_check_ui import finalize_bending_check_row
from state_and_helpers import get_param


def compute_bending_capacity_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single-source bending capacity calculation from an explicit state dict.
    Returns both legacy and signed moment branch results.
    """
    lig_diameter_mm = float(get_param("lig_d", 0.0) or 0.0)
    return compute_bending_capacity_from_state_values(
        st_state,
        lig_diameter_mm=lig_diameter_mm,
    )


def build_bending_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure read-only helper.
    Uses bending_core's pure capacity calc so Inputs + Bending page always match.
    """
    cap = compute_bending_capacity_from_state(st_state)
    actions = dict(cap.get("actions") or {})
    Mu_star = float(cap.get("Mu_star", 0.0) or 0.0)
    Mu_pos_star = float(cap.get("Mu_pos_star", 0.0) or 0.0)
    Mu_neg_star = float(cap.get("Mu_neg_star", 0.0) or 0.0)
    has_sagging_case = bool(cap.get("has_sagging_case"))
    has_hogging_case = bool(cap.get("has_hogging_case"))
    bend_pos = dict(cap.get("bending_pos") or {})
    bend_neg = dict(cap.get("bending_neg") or {})
    results = dict(cap.get("legacy") or {})
    governing_case = str(cap.get("governing_case") or "")
    util = float(cap.get("governing_util", 0.0) or 0.0)
    phi_mu_governing = float(cap.get("governing_phi_mu_kNm", 0.0) or 0.0)
    Ast_bot = float(cap.get("Ast_bot", 0.0) or 0.0)

    k_u = results.get("ku", None)
    As_min = results.get("As_min", None)
    Mcr = results.get("Mcr", None)

    def _status_from_util(u: float | None):
        if u is None:
            return "—"
        if u <= 1.0:
            return "PASS"
        return "FAIL"

    rows: list[dict[str, Any]] = []

    def _add(row: dict[str, Any]) -> None:
        rows.append(finalize_bending_check_row(row))

    if has_sagging_case:
        phi_mu_pos = float(bend_pos.get("phi_Mu_kNm", 0.0) or 0.0)
        util_pos = float(bend_pos.get("util", 0.0) or 0.0)
        _add({
            "uid": "bend_strength_pos",
            "title": "Positive bending",
            "row_type": "capacity_action",
            "calculated": f"φMu(+) = {phi_mu_pos:.1f} kNm",
            "requirement": f"Mu*(+) = {Mu_pos_star:.1f} kNm",
            "util": f"{util_pos:.2f}" if phi_mu_pos > 0 else "—",
            "status": _status_from_util(util_pos) if phi_mu_pos > 0 else "—",
            "route_page": "bending",
            "moment_sign": "positive",
        })
    if has_hogging_case:
        phi_mu_neg = float(bend_neg.get("phi_Mu_kNm", 0.0) or 0.0)
        util_neg = float(bend_neg.get("util", 0.0) or 0.0)
        _add({
            "uid": "bend_strength_neg",
            "title": "Negative bending",
            "row_type": "capacity_action",
            "calculated": f"φMu(-) = {phi_mu_neg:.1f} kNm",
            "requirement": f"|Mu*(-)| = {Mu_neg_star:.1f} kNm",
            "util": f"{util_neg:.2f}" if phi_mu_neg > 0 else "—",
            "status": _status_from_util(util_neg) if phi_mu_neg > 0 else "—",
            "route_page": "bending",
            "moment_sign": "negative",
        })

    if As_min is not None and As_min == As_min:
        as_min_f = float(As_min)
        util_as = (as_min_f / Ast_bot) if Ast_bot and Ast_bot > 0 else None
        _add({
            "uid": "bend_Asmin",
            "title": "Minimum tensile reinforcement",
            "row_type": "provided_required",
            "calculated": f"As,provided = {Ast_bot:.0f} mm²",
            "requirement": f"As,min = {as_min_f:.0f} mm²",
            "util": f"{util_as:.2f}" if util_as is not None else "—",
            "status": "PASS" if As_min and Ast_bot >= As_min else "FAIL",
            "route_page": "bending",
        })

    if (Mcr is not None) and (Mcr == Mcr) and phi_mu_governing > 0:
        Mu_min = 1.2 * float(Mcr)
        mu_min_util = (Mu_min / phi_mu_governing) if phi_mu_governing > 0 else None
        _add({
            "uid": "bend_min_strength",
            "title": "Minimum design capacity requirement",
            "row_type": "provided_required",
            "calculated": f"φMu,cap = {phi_mu_governing:.1f} kNm",
            "requirement": f"(M_u,cap)_min = {Mu_min:.1f} kNm",
            "util": f"{mu_min_util:.2f}" if mu_min_util is not None else "—",
            "status": _status_from_util(mu_min_util),
            "route_page": "bending",
        })

    if (k_u is not None) and (k_u == k_u):
        ku_lim = 0.36
        ku_f = float(k_u)
        util_ku = (ku_f / ku_lim) if ku_lim else None
        _add({
            "uid": "bend_duct",
            "title": "Ductility limit",
            "row_type": "actual_limit",
            "calculated": f"k_u = {ku_f:.3f}",
            "requirement": f"k_u,lim = {ku_lim:.2f}",
            "util": f"{util_ku:.2f}" if util_ku is not None else "—",
            "status": "PASS" if ku_f <= ku_lim else "FAIL",
            "route_page": "bending",
        })

    # Signed service moment: same resolver as ULS demand (design vs manual / SFD vs section)
    Ms_sls = float(actions.get("SLS_M_signed", 0.0) or 0.0)
    _add({
        "uid": "bend_service_moment",
        "title": "Service bending moment",
        "row_type": "informational",
        "calculated": f"M_s = {Ms_sls:.1f} kNm",
        "requirement": "SLS design / manual actions",
        "util": "—",
        "status": "INFO",
        "is_informational": True,
        "route_page": "bending",
    })

    # When signed sag/hog cases are off, still surface φMu / Mu* so summary banner is moment capacity.
    has_split_moment = any(r.get("uid") in ("bend_strength_pos", "bend_strength_neg") for r in rows)
    phi_Mu_cap = float(results.get("phi_Mu_cap", 0.0) or 0.0)
    Mu_util_legacy = float(results.get("Mu_util", 0.0) or 0.0)
    if not has_split_moment and phi_Mu_cap > 0:
        rows.insert(
            0,
            finalize_bending_check_row({
                "uid": "bend_strength",
                "title": "Flexural strength capacity",
                "row_type": "capacity_action",
                "calculated": f"φMu = {phi_Mu_cap:.1f} kNm",
                "requirement": f"Mu* = {Mu_star:.1f} kNm",
                "util": f"{Mu_util_legacy:.2f}",
                "status": _status_from_util(Mu_util_legacy),
                "route_page": "bending",
            }),
        )

    # Summary banner (Inputs): primary row = governing moment check, not min steel / detailing.
    for r in rows:
        r["is_primary"] = False
    prim_uid: str | None = None
    pos_neg = [r for r in rows if r.get("uid") in ("bend_strength_pos", "bend_strength_neg")]
    if governing_case == "Negative bending" and any(r.get("uid") == "bend_strength_neg" for r in rows):
        prim_uid = "bend_strength_neg"
    elif governing_case == "Positive bending" and any(r.get("uid") == "bend_strength_pos" for r in rows):
        prim_uid = "bend_strength_pos"
    elif any(r.get("uid") == "bend_strength" for r in rows):
        prim_uid = "bend_strength"
    elif len(pos_neg) == 1:
        prim_uid = str(pos_neg[0].get("uid") or "")
    elif len(pos_neg) > 1:
        def _row_util(r: dict) -> float:
            try:
                return float(r.get("util") or 0.0)
            except (TypeError, ValueError):
                return 0.0

        prim_uid = str(max(pos_neg, key=_row_util).get("uid") or "")
    if prim_uid:
        for r in rows:
            if r.get("uid") == prim_uid:
                r["is_primary"] = True

    return {
        "summary_phiMu_kNm": float(results.get("phi_Mu_cap", 0.0) or 0.0),
        "summary_Mu_star_kNm": Mu_star,
        "summary_Ms_sls_kNm": Ms_sls,
        "summary_util": util,
        "summary_Mcr_kNm": Mcr,
        "has_sagging_case": has_sagging_case,
        "has_hogging_case": has_hogging_case,
        "governing_case": governing_case,
        "bending_pos": bend_pos,
        "bending_neg": bend_neg,
        "rows": rows,
        "actions_used": actions,
    }
