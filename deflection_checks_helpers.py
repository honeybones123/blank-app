from typing import Dict, Any


def build_deflection_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Contract-safe: reads from st.session_state only (no writes).
    Returns a dict with:
      - summary_delta_total_mm
      - summary_defl_limit_mm
      - summary_util_total
      - rows: list[dict] for summary/check tables
    """

    # -------- Read only inputs ----------
    L_m = float(st_state.get("span_L_m", st_state.get("L_m", 0.0)) or 0.0)
    g_kNm = float(st_state.get("g_kNm", st_state.get("g_line_kNm", 0.0)) or 0.0)
    q_kNm = float(st_state.get("q_kNm", st_state.get("q_line_kNm", 0.0)) or 0.0)

    defl_limit_ratio = float(st_state.get("defl_limit_ratio", 250.0) or 250.0)
    support_type = st_state.get("support_type", "Simply supported")

    Ec = float(st_state.get("Ec", st_state.get("E_c", 0.0)) or 0.0)

    Ief = float(
        st_state.get("Ief_selected",
        st_state.get("Ief",
        st_state.get("I_ef", 0.0)))
        or 0.0
    )

    psi_s = float(st_state.get("psi_s", st_state.get("defl_psi_s", 0.0)) or 0.0)

    Ast = float(st_state.get("Ast", st_state.get("Ast_bot", 0.0)) or 0.0)
    Asc = float(st_state.get("Asc", 0.0) or 0.0)

    # ---------- Call the same calc the deflection page uses ----------
    from deflection import calc_deflection_as3600

    results = calc_deflection_as3600(
        L_m=L_m,
        Ec=Ec,
        Ief=Ief,
        g_kNm=g_kNm,
        q_kNm=q_kNm,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )

    delta_short_total = float(results.get("delta_short_total", 0.0) or 0.0)
    delta_long_add = float(results.get("delta_long_add", 0.0) or 0.0)
    delta_total = float(results.get("delta_total", delta_short_total + delta_long_add) or 0.0)

    L_mm = L_m * 1000.0
    defl_limit_mm = (L_mm / defl_limit_ratio) if defl_limit_ratio > 0 else 0.0

    util_short = (delta_short_total / defl_limit_mm) if defl_limit_mm > 0 else None
    util_long = (delta_long_add / defl_limit_mm) if defl_limit_mm > 0 else None
    util_total = (delta_total / defl_limit_mm) if defl_limit_mm > 0 else None

    def _status(util):
        if util is None:
            return "—"
        return "PASS" if util <= 1.0 else "FAIL"

    rows = [
        {
            "uid": "defl_short",
            "title": "Short-term deflection (total load)",
            "value": f"δshort = {delta_short_total:.2f} mm",
            "limit": f"δlim = {defl_limit_mm:.2f} mm" if defl_limit_mm > 0 else "—",
            "util": f"{util_short:.2f}" if util_short is not None else "—",
            "status": _status(util_short),
            "route_page": "deflection",
        },
        {
            "uid": "defl_long",
            "title": "Additional long-term deflection",
            "value": f"δlong = {delta_long_add:.2f} mm",
            "limit": f"δlim = {defl_limit_mm:.2f} mm" if defl_limit_mm > 0 else "—",
            "util": f"{util_long:.2f}" if util_long is not None else "—",
            "status": _status(util_long),
            "route_page": "deflection",
        },
        {
            "uid": "defl_total",
            "title": "Total deflection (short + long-term)",
            "value": f"δtotal = {delta_total:.2f} mm",
            "limit": f"δlim = {defl_limit_mm:.2f} mm" if defl_limit_mm > 0 else "—",
            "util": f"{util_total:.2f}" if util_total is not None else "—",
            "status": _status(util_total),
            "route_page": "deflection",
        },
    ]

    return {
        "summary_delta_total_mm": delta_total,
        "summary_defl_limit_mm": defl_limit_mm,
        "summary_util_total": util_total,
        "rows": rows,
    }
