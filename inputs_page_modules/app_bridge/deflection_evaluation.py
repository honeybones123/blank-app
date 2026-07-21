"""Deflection evaluation coordination for Inputs app-bridge candidates."""

from __future__ import annotations

from typing import Any


_DEFLECTION_EVALUATION_DEPENDENCIES: tuple[str, ...] = (
    "_design_width_value",
    "_design_width_value_for_app_bridge",
    "_effective_bottom_design_state",
    "_effective_bottom_design_state_for_app_bridge",
    "_float_from_state",
    "_status_from_candidate_util",
    "_status_from_candidate_util_for_app_bridge",
    "st",
)


def bind_deflection_evaluation_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _DEFLECTION_EVALUATION_DEPENDENCIES
            if name in namespace
        }
    )


def _evaluate_deflection_with_state_for_app_bridge(
    state: dict,
    *,
    bottom_updates: dict | None = None,
) -> dict | None:
    from deflection import (
        _derive_equiv_udl_from_actions,
        calc_ief_simplified,
        calc_deflection_as3600,
        get_resolved_deflection_support_type,
    )

    bottom_state = _effective_bottom_design_state_for_app_bridge(state, bottom_updates)
    b = _design_width_value_for_app_bridge(state)
    fc = _float_from_state(state, "fc", 32.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    Asc = _float_from_state(state, "Ast_top", 0.0)
    d = float(bottom_state.get("d_centroid", 0.0) or 0.0)
    beff = _float_from_state(state, "defl_beff", b)
    bw = _float_from_state(state, "defl_bw", b)
    psi_s = _float_from_state(state, "psi_udl", _float_from_state(state, "psi_s", _float_from_state(state, "defl_psi_s", 0.4)))
    defl_limit_ratio = _float_from_state(state, "defl_limit_ratio", 250.0)
    g_udl = _float_from_state(state, "g_udl_kNm_per_m", _float_from_state(state, "g_kNm", _float_from_state(state, "g_line_kNm", 0.0)))
    q_udl = _float_from_state(state, "q_udl_kNm_per_m", _float_from_state(state, "q_kNm", _float_from_state(state, "q_line_kNm", 0.0)))
    w_sls = _float_from_state(state, "w_sls_kNm_per_m", 0.0)
    sls_Mstar = state.get("sls_Mstar")
    sls_Vstar = state.get("sls_Vstar")
    support_type = get_resolved_deflection_support_type(st.session_state)

    L_m = _float_from_state(state, "defl_L_eff", 0.0)
    if L_m <= 0.0:
        L_m = _float_from_state(state, "span_L_m", _float_from_state(state, "L_m", 0.0))
    if L_m <= 0.0:
        L_mm = _float_from_state(state, "L", 0.0)
        if L_mm > 0.0:
            L_m = L_mm / 1000.0

    if not (b > 0.0 and fc > 0.0 and Ec > 0.0 and Ast > 0.0 and d > 0.0 and L_m > 0.0):
        return None

    ief, _, _, _, _, _ = calc_ief_simplified(fc, max(beff, b), max(bw, min(bw, b) if bw > 0 else b), d, Ast)
    derived = _derive_equiv_udl_from_actions(
        M_kNm=None if sls_Mstar is None else float(sls_Mstar),
        V_kN=None if sls_Vstar is None else float(sls_Vstar),
        L_m=L_m,
        support_type=support_type,
    )
    if derived.get("w_kN_per_m") is not None:
        w_used = float(derived.get("w_kN_per_m") or 0.0)
    elif w_sls > 0.0:
        w_used = float(w_sls)
    else:
        w_used = float(g_udl + q_udl)

    if w_used > 0.0 and (g_udl + q_udl) > 0.0:
        g_ratio = float(g_udl) / float(g_udl + q_udl)
        g_equiv = w_used * g_ratio
        q_equiv = w_used * (1.0 - g_ratio)
    else:
        g_equiv = float(g_udl)
        q_equiv = float(q_udl if w_used <= 0.0 else 0.0)

    results = calc_deflection_as3600(
        L_m=L_m,
        Ec=Ec,
        Ief=ief,
        g_kNm=g_equiv,
        q_kNm=q_equiv,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )
    if not results or results.get("ok") is False:
        return None

    L_mm = float(results.get("L_mm", L_m * 1000.0) or (L_m * 1000.0))
    defl_limit = (L_mm / defl_limit_ratio) if defl_limit_ratio > 0.0 else 0.0
    util = (float(results.get("delta_total", 0.0) or 0.0) / defl_limit) if defl_limit > 0.0 else None
    status = _status_from_candidate_util_for_app_bridge(util)
    return {
        "delta_total": float(results.get("delta_total", 0.0) or 0.0),
        "defl_limit": float(defl_limit),
        "util": None if util is None else float(util),
        "status": status,
        "passes": bool(util is not None and util <= 1.0),
        "pack": {
            "summary_delta_total_mm": float(results.get("delta_total", 0.0) or 0.0),
            "summary_defl_limit_mm": float(defl_limit),
            "summary_util_total": None if util is None else float(util),
            "rows": [{
                "uid": "defl_total",
                "title": "Total deflection (short + long-term)",
                "value": f"δtotal = {float(results.get('delta_total', 0.0) or 0.0):.2f} mm",
                "limit": f"δlim = {float(defl_limit):.2f} mm" if defl_limit > 0.0 else "—",
                "util": "—" if util is None else f"{float(util):.2f}",
                "status": status,
                "ok": None if util is None else bool(util <= 1.0),
                "route_page": "deflection",
                "tab": "Long-term deflection",
                "is_primary": True,
            }],
        },
    }


def _evaluate_deflection_with_state(state: dict, *, bottom_updates: dict | None = None) -> dict | None:
    from deflection import (
        _derive_equiv_udl_from_actions,
        calc_ief_simplified,
        calc_deflection_as3600,
        get_resolved_deflection_support_type,
    )

    bottom_state = _effective_bottom_design_state(state, bottom_updates)
    b = _design_width_value(state)
    fc = _float_from_state(state, "fc", 32.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    Asc = _float_from_state(state, "Ast_top", 0.0)
    d = float(bottom_state.get("d_centroid", 0.0) or 0.0)
    beff = _float_from_state(state, "defl_beff", b)
    bw = _float_from_state(state, "defl_bw", b)
    psi_s = _float_from_state(state, "psi_udl", _float_from_state(state, "psi_s", _float_from_state(state, "defl_psi_s", 0.4)))
    defl_limit_ratio = _float_from_state(state, "defl_limit_ratio", 250.0)
    g_udl = _float_from_state(state, "g_udl_kNm_per_m", _float_from_state(state, "g_kNm", _float_from_state(state, "g_line_kNm", 0.0)))
    q_udl = _float_from_state(state, "q_udl_kNm_per_m", _float_from_state(state, "q_kNm", _float_from_state(state, "q_line_kNm", 0.0)))
    w_sls = _float_from_state(state, "w_sls_kNm_per_m", 0.0)
    sls_Mstar = state.get("sls_Mstar")
    sls_Vstar = state.get("sls_Vstar")
    # Support resolution uses live session (SFD / actions_mode), not the local candidate dict.
    support_type = get_resolved_deflection_support_type(st.session_state)

    L_m = _float_from_state(state, "defl_L_eff", 0.0)
    if L_m <= 0.0:
        L_m = _float_from_state(state, "span_L_m", _float_from_state(state, "L_m", 0.0))
    if L_m <= 0.0:
        L_mm = _float_from_state(state, "L", 0.0)
        if L_mm > 0.0:
            L_m = L_mm / 1000.0

    if not (b > 0.0 and fc > 0.0 and Ec > 0.0 and Ast > 0.0 and d > 0.0 and L_m > 0.0):
        return None

    ief, _, _, _, _, _ = calc_ief_simplified(fc, max(beff, b), max(bw, min(bw, b) if bw > 0 else b), d, Ast)
    derived = _derive_equiv_udl_from_actions(
        M_kNm=None if sls_Mstar is None else float(sls_Mstar),
        V_kN=None if sls_Vstar is None else float(sls_Vstar),
        L_m=L_m,
        support_type=support_type,
    )
    if derived.get("w_kN_per_m") is not None:
        w_used = float(derived.get("w_kN_per_m") or 0.0)
    elif w_sls > 0.0:
        w_used = float(w_sls)
    else:
        w_used = float(g_udl + q_udl)

    if w_used > 0.0 and (g_udl + q_udl) > 0.0:
        g_ratio = float(g_udl) / float(g_udl + q_udl)
        g_equiv = w_used * g_ratio
        q_equiv = w_used * (1.0 - g_ratio)
    else:
        g_equiv = float(g_udl)
        q_equiv = float(q_udl if w_used <= 0.0 else 0.0)

    results = calc_deflection_as3600(
        L_m=L_m,
        Ec=Ec,
        Ief=ief,
        g_kNm=g_equiv,
        q_kNm=q_equiv,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )
    if not results or results.get("ok") is False:
        return None

    L_mm = float(results.get("L_mm", L_m * 1000.0) or (L_m * 1000.0))
    defl_limit = (L_mm / defl_limit_ratio) if defl_limit_ratio > 0.0 else 0.0
    util = (float(results.get("delta_total", 0.0) or 0.0) / defl_limit) if defl_limit > 0.0 else None
    status = _status_from_candidate_util(util)
    return {
        "delta_total": float(results.get("delta_total", 0.0) or 0.0),
        "defl_limit": float(defl_limit),
        "util": None if util is None else float(util),
        "status": status,
        "passes": bool(util is not None and util <= 1.0),
        "pack": {
            "summary_delta_total_mm": float(results.get("delta_total", 0.0) or 0.0),
            "summary_defl_limit_mm": float(defl_limit),
            "summary_util_total": None if util is None else float(util),
            "rows": [{
                "uid": "defl_total",
                "title": "Total deflection (short + long-term)",
                "value": f"Î´total = {float(results.get('delta_total', 0.0) or 0.0):.2f} mm",
                "limit": f"Î´lim = {float(defl_limit):.2f} mm" if defl_limit > 0.0 else "â€”",
                "util": "â€”" if util is None else f"{float(util):.2f}",
                "status": status,
                "ok": None if util is None else bool(util <= 1.0),
                "route_page": "deflection",
                "tab": "Long-term deflection",
                "is_primary": True,
            }],
        },
    }
