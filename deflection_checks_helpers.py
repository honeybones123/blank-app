from typing import Any, Dict

from engineering_check_ui import sync_legacy_value_limit
from calculations.deflection import (
    format_deflection_allowable_limit_mm as _format_deflection_allowable_limit_mm,
)
from state_and_helpers import (
    get_param,
    get_deflection_limit_ratio,
)


def build_deflection_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Contract-safe: reads from st.session_state only (no writes).
    Returns a dict with:
      - summary_delta_total_mm
      - summary_defl_limit_mm
      - summary_util_total
      - rows: list[dict] for summary/check tables
    """
    from deflection_support import get_resolved_deflection_support_type

    # -------- Read computed outputs first (preferred path) ----------
    delta_short_total = get_param("delta_short_total", None)
    delta_long_add = get_param("delta_long_add", None)
    delta_total = get_param("delta_total", None)
    defl_limit_mm = get_param("deflection_limit_mm", None)
    util_total = get_param("deflection_utilisation", None)

    # -------- Read only inputs (fallback for recompute) ----------
    L_m = float(get_param("span_L_m", get_param("L_m", st_state.get("span_L_m", st_state.get("L_m", 0.0)))) or 0.0)
    g_udl_raw = get_param("g_udl_kNm_per_m", get_param("g_kNm", get_param("g_line_kNm", 0.0)))
    q_udl_raw = get_param("q_udl_kNm_per_m", get_param("q_kNm", get_param("q_line_kNm", 0.0)))
    g_kNm = float(g_udl_raw or 0.0)
    q_kNm = float(q_udl_raw or 0.0)
    w_sls_fb = get_param("w_sls_kNm_per_m", None)
    sls_Mstar = get_param("sls_Mstar", None)
    sls_Vstar = get_param("sls_Vstar", None)

    def _has_nonzero_load(value: Any) -> bool:
        try:
            return abs(float(value or 0.0)) > 1e-12
        except Exception:
            return False

    has_service_load = any(
        _has_nonzero_load(value)
        for value in (g_udl_raw, q_udl_raw, w_sls_fb, sls_Mstar, sls_Vstar)
    )

    defl_limit_ratio = float(get_deflection_limit_ratio(get_param("defl_limit_ratio", st_state.get("defl_limit_ratio", 250.0))))
    support_type = get_resolved_deflection_support_type(st_state)

    Ec = float(
        get_param(
            "Eceff",
            get_param("Ec", get_param("E_c", st_state.get("Eceff", st_state.get("Ec", st_state.get("E_c", 0.0))))),
        )
        or 0.0
    )

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
        from calculations.deflection import (
            calc_deflection_as3600,
            derive_equiv_udl_from_actions,
            resolve_deflection_equiv_loads_from_inputs,
        )

        derived = derive_equiv_udl_from_actions(
            M_kNm=sls_Mstar,
            V_kN=sls_Vstar,
            L_m=L_m,
            support_type=support_type,
        )
        g_used, q_used = resolve_deflection_equiv_loads_from_inputs(
            derived=derived,
            w_sls=w_sls_fb,
            g_udl=g_udl_raw,
            q_udl=q_udl_raw,
        )

        if (float(g_used) + float(q_used)) <= 1e-12:
            delta_short_total = 0.0
            delta_long_add = 0.0
            delta_total = 0.0
        else:
            results = calc_deflection_as3600(
                L_m=L_m,
                Ec=Ec,
                Ief=Ief,
                g_kNm=g_used,
                q_kNm=q_used,
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
    if not has_service_load:
        util_short = None
        util_long = None
        util_total = None
        status_short = "NOT RUN"
        status_long = "NOT RUN"
        status_total = "NOT RUN"

    lim_txt = _format_deflection_allowable_limit_mm(float(defl_limit_mm or 0.0), defl_limit_ratio)

    def _row(*, uid, title, tab, delta_label, delta_val, util, status, is_primary=False):
        calc = f"{delta_label} = {delta_val:.2f} mm"
        r = {
            "uid": uid,
            "title": title,
            "calculated": calc,
            "requirement": lim_txt,
            "capacity": calc,
            "action": lim_txt,
            "util": f"{util:.2f}" if util is not None else "—",
            "status": status,
            "ok": _ok_from_status(status),
            "route_page": "deflection",
            "tab": tab,
            "is_primary": is_primary,
        }
        return sync_legacy_value_limit(r)

    rows = [
        _row(
            uid="defl_total",
            title="Total deflection (short + long-term)",
            tab="Long-term deflection",
            delta_label="δtotal",
            delta_val=float(delta_total or 0.0),
            util=util_total,
            status=status_total,
            is_primary=True,
        ),
        _row(
            uid="defl_short",
            title="Short-term deflection (total load)",
            tab="Short-term deflection",
            delta_label="δshort",
            delta_val=float(delta_short_total or 0.0),
            util=util_short,
            status=status_short,
        ),
        _row(
            uid="defl_long_add",
            title="Additional long-term deflection",
            tab="Long-term deflection",
            delta_label="δlong",
            delta_val=float(delta_long_add or 0.0),
            util=util_long,
            status=status_long,
        ),
    ]

    return {
        "summary_delta_total_mm": delta_total,
        "summary_defl_limit_mm": defl_limit_mm,
        "summary_util_total": util_total,
        "rows": rows,
    }
