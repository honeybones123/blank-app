from typing import Dict, Any

from state_and_helpers import get_param


def build_deflection_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Contract-safe: reads from st.session_state only (no writes).
    Returns a dict with:
      - summary_delta_total_mm
      - summary_defl_limit_mm
      - summary_util_total
      - rows: list[dict] for summary/check tables
    """

    # -------- Read computed outputs first (preferred path) ----------
    delta_short_total = get_param("delta_short_total", None)
    delta_long_add = get_param("delta_long_add", None)
    delta_total = get_param("delta_total", None)
    defl_limit_mm = get_param("deflection_limit_mm", None)
    util_total = get_param("deflection_utilisation", None)

    # -------- Read only inputs (fallback for recompute) ----------
    L_m = float(get_param("span_L_m", get_param("L_m", st_state.get("span_L_m", st_state.get("L_m", 0.0)))) or 0.0)
    g_kNm = float(get_param("g_udl_kNm_per_m", get_param("g_kNm", get_param("g_line_kNm", 0.0))) or 0.0)
    q_kNm = float(get_param("q_udl_kNm_per_m", get_param("q_kNm", get_param("q_line_kNm", 0.0))) or 0.0)

    defl_limit_ratio = float(get_param("defl_limit_ratio", st_state.get("defl_limit_ratio", 250.0)) or 250.0)
    support_type = get_param("defl_support_type", get_param("support_type", "Simply supported"))

    Ec = float(get_param("Ec", get_param("E_c", st_state.get("Ec", st_state.get("E_c", 0.0)))) or 0.0)

    Ief = float(
        get_param("Ief_selected",
        get_param("Ief",
        get_param("I_ef", st_state.get("Ief_selected", st_state.get("Ief", st_state.get("I_ef", 0.0))))))
        or 0.0
    )

    psi_s = float(get_param("psi_udl", get_param("psi_s", get_param("defl_psi_s", 0.0))) or 0.0)

    Ast = float(get_param("Ast", get_param("Ast_bot", st_state.get("Ast", st_state.get("Ast_bot", 0.0)))) or 0.0)
    Asc = float(get_param("Asc", st_state.get("Asc", 0.0)) or 0.0)

    # ---------- Fallback recompute if any key outputs missing ----------
    if (
        delta_short_total is None
        or delta_long_add is None
        or delta_total is None
        or defl_limit_mm is None
    ):
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

        if defl_limit_mm is None or defl_limit_mm <= 0:
            L_mm = L_m * 1000.0
            defl_limit_mm = (L_mm / defl_limit_ratio) if defl_limit_ratio > 0 else 0.0
        util_total = delta_total / defl_limit_mm if defl_limit_mm and defl_limit_mm > 0 else None

    if defl_limit_mm is None:
        defl_limit_mm = 0.0

    util_short = (delta_short_total / defl_limit_mm) if defl_limit_mm > 0 else None
    util_long = (delta_long_add / defl_limit_mm) if defl_limit_mm > 0 else None
    util_total = (delta_total / defl_limit_mm) if defl_limit_mm > 0 else None

    def _status(util):
        if util is None:
            return "—"
        return "PASS" if util <= 1.0 else "FAIL"

    def _ok_from_status(status: str):
        if status == "PASS":
            return True
        if status == "FAIL":
            return False
        return None

    status_short = _status(util_short)
    status_long = _status(util_long)
    status_total = _status(util_total)

    rows = [
        {
            "uid": "defl_long",
            "title": "Total deflection (short + long-term)",
            "value": f"δtotal = {delta_total:.2f} mm",
            "limit": f"δlim = {defl_limit_mm:.2f} mm" if defl_limit_mm > 0 else "—",
            "util": f"{util_total:.2f}" if util_total is not None else "—",
            "status": status_total,
            "ok": _ok_from_status(status_total),
            "route_page": "deflection",
            "tab": "Long-term deflection",
            "is_primary": True,
        },
        {
            "uid": "defl_short",
            "title": "Short-term deflection (total load)",
            "value": f"δshort = {delta_short_total:.2f} mm",
            "limit": f"δlim = {defl_limit_mm:.2f} mm" if defl_limit_mm > 0 else "—",
            "util": f"{util_short:.2f}" if util_short is not None else "—",
            "status": status_short,
            "ok": _ok_from_status(status_short),
            "route_page": "deflection",
            "tab": "Short-term deflection",
        },
        {
            "uid": "defl_long",
            "title": "Additional long-term deflection",
            "value": f"δlong = {delta_long_add:.2f} mm",
            "limit": f"δlim = {defl_limit_mm:.2f} mm" if defl_limit_mm > 0 else "—",
            "util": f"{util_long:.2f}" if util_long is not None else "—",
            "status": status_long,
            "ok": _ok_from_status(status_long),
            "route_page": "deflection",
            "tab": "Long-term deflection",
        },
    ]

    return {
        "summary_delta_total_mm": delta_total,
        "summary_defl_limit_mm": defl_limit_mm,
        "summary_util_total": util_total,
        "rows": rows,
    }
