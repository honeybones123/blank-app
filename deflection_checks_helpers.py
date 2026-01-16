from typing import Any, Dict


def build_deflection_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Contract-safe: reads inputs/derived values from st.session_state only.
    No writes to st.session_state.
    Returns a dict with summary values and rows for summary/check tables.
    """
    # Span (meters) - keep in line with deflection.py
    L_m = st_state.get("defl_L_eff")
    if L_m is None:
        L_m = st_state.get("span_L_m", st_state.get("L_m"))
    if L_m is None:
        L_raw_mm = st_state.get("L", 0.0) or 0.0
        L_m = float(L_raw_mm) / 1000.0
    L_m = float(L_m or 0.0)

    # Deflection limit ratio (e.g., 250)
    defl_limit_ratio = float(st_state.get("defl_limit_ratio", 250.0) or 250.0)

    # Support condition
    support_type = st_state.get("defl_support_type", st_state.get("support_type", "Simply supported"))

    # Material stiffness (matches deflection page input)
    Ec = float(st_state.get("defl_Ec", st_state.get("Ec", st_state.get("E_c", 0.0))) or 0.0)

    # Reinforcement
    Ast = float(st_state.get("Ast_bot", st_state.get("Ast", 0.0)) or 0.0)
    Asc = float(st_state.get("Asc", st_state.get("Ast_top", 0.0)) or 0.0)

    # Effective stiffness (match deflection.py selection)
    use_simplified_ief = bool(st_state.get("defl_use_simplified_ief", True))
    if use_simplified_ief:
        fc = float(st_state.get("defl_fc", st_state.get("fc", 0.0)) or 0.0)
        b = float(st_state.get("b", 0.0) or 0.0)
        beff = float(st_state.get("defl_beff", b) or 0.0)
        bw = float(st_state.get("defl_bw", b) or 0.0)
        d = float(st_state.get("d", 0.0) or 0.0)
        try:
            from deflection import calc_ief_simplified
            Ief_selected, _, _, _, _, _ = calc_ief_simplified(
                fc=fc,
                beff=beff,
                bw=bw,
                d=d,
                Ast=Ast,
            )
        except Exception:
            Ief_selected = 1.0e11
    else:
        Ief_selected = float(st_state.get("defl_Ief_user", 1.0e11) or 1.0e11)

    # Sustained load factor (deflection.py uses psi_udl)
    psi_s = float(st_state.get("psi_udl", st_state.get("psi_s", st_state.get("defl_psi_s", 0.4))) or 0.4)

    # Service loads (for ratio and fallback)
    g_udl = float(
        st_state.get("g_udl_kNm_per_m", st_state.get("g_kNm", st_state.get("g_line_kNm", 0.0)))
        or 0.0
    )
    q_udl = float(
        st_state.get("q_udl_kNm_per_m", st_state.get("q_kNm", st_state.get("q_line_kNm", 0.0)))
        or 0.0
    )

    # Actions source (match deflection.py)
    actions_source = st_state.get("actions_source", "Manual design actions (inputs below)")
    is_design_driven = "Teaching" in actions_source or actions_source == "Teaching SFD/BMD page (|M|max, |V|max)"

    if is_design_driven:
        M_used = float(st_state.get("sfd_Mmax_abs_kNm", 0.0) or 0.0)
        V_used = float(st_state.get("sfd_Vmax_abs_kN", 0.0) or 0.0)
    else:
        M_used = float(st_state.get("Mu_star_manual", 0.0) or 0.0)
        V_used = float(st_state.get("Vu_star_manual", 0.0) or 0.0)

    # Compute w_used from M* or V* (same logic as deflection.py)
    w_used = None
    if L_m > 0:
        if support_type == "Simply supported":
            if M_used > 0:
                w_used = 8.0 * M_used / (L_m ** 2)
            elif V_used > 0:
                w_used = 2.0 * V_used / L_m
        elif support_type == "Cantilever":
            if M_used > 0:
                w_used = 2.0 * M_used / (L_m ** 2)
            elif V_used > 0:
                w_used = V_used / L_m
        else:
            if V_used > 0:
                w_used = 2.0 * V_used / L_m
            elif M_used > 0:
                w_used = 8.0 * M_used / (L_m ** 2)

    if w_used is None or w_used <= 0:
        w_used = g_udl + q_udl

    if w_used > 0:
        if (g_udl + q_udl) > 0:
            g_ratio = g_udl / (g_udl + q_udl)
            g_used = w_used * g_ratio
            q_used = w_used * (1.0 - g_ratio)
        else:
            g_used = w_used
            q_used = 0.0
    else:
        g_used = g_udl
        q_used = q_udl

    # Use the same calculation function as deflection page
    from deflection import calc_deflection_as3600

    results = calc_deflection_as3600(
        L_m=L_m,
        Ec=Ec,
        Ief=Ief_selected,
        g_kNm=g_used,
        q_kNm=q_used,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )

    if results is None or (isinstance(results, dict) and results.get("ok") is False):
        delta_short_total = 0.0
        delta_long_add = 0.0
        delta_total = 0.0
    else:
        delta_short_total = float(results.get("delta_short_total", 0.0) or 0.0)
        delta_long_add = float(results.get("delta_long_add", 0.0) or 0.0)
        delta_total = float(results.get("delta_total", delta_short_total + delta_long_add) or 0.0)

    # Limit (mm)
    L_mm = L_m * 1000.0
    defl_limit_mm = (L_mm / defl_limit_ratio) if defl_limit_ratio > 0 else 0.0

    util_short = (delta_short_total / defl_limit_mm) if defl_limit_mm > 0 else None
    util_long = (delta_long_add / defl_limit_mm) if defl_limit_mm > 0 else None
    util_total = (delta_total / defl_limit_mm) if defl_limit_mm > 0 else None

    def _status(util):
        if util is None:
            return "—"
        return "PASS" if util <= 1.0 else "FAIL"

    def _ok(status: str):
        if status == "PASS":
            return True
        if status == "FAIL":
            return False
        return None

    rows = [
        {
            "uid": "defl_short",
            "title": "Short-term deflection (total load)",
            "value": f"δshort = {delta_short_total:.2f} mm",
            "limit": f"δlim = {defl_limit_mm:.2f} mm" if defl_limit_mm > 0 else "—",
            "util": f"{util_short:.2f}" if util_short is not None else "—",
            "status": _status(util_short),
            "ok": _ok(_status(util_short)),
            "route_page": "deflection",
            "tab": "Short-term deflection",
            "is_primary": True,
        },
        {
            "uid": "defl_long",
            "title": "Additional long-term deflection",
            "value": f"δlong = {delta_long_add:.2f} mm",
            "limit": f"δlim = {defl_limit_mm:.2f} mm" if defl_limit_mm > 0 else "—",
            "util": f"{util_long:.2f}" if util_long is not None else "—",
            "status": _status(util_long),
            "ok": _ok(_status(util_long)),
            "route_page": "deflection",
            "tab": "Long-term deflection",
            "is_primary": False,
        },
        {
            "uid": "defl_total",
            "title": "Total deflection (short + long-term)",
            "value": f"δtotal = {delta_total:.2f} mm",
            "limit": f"δlim = {defl_limit_mm:.2f} mm" if defl_limit_mm > 0 else "—",
            "util": f"{util_total:.2f}" if util_total is not None else "—",
            "status": _status(util_total),
            "ok": _ok(_status(util_total)),
            "route_page": "deflection",
            "tab": "Long-term deflection",
            "is_primary": True,
        },
    ]

    return {
        "summary_delta_total_mm": delta_total,
        "summary_defl_limit_mm": defl_limit_mm,
        "summary_util_total": util_total,
        "rows": rows,
    }
