# deflection_core.py
# Core compute function for deflection (no Streamlit UI)

import math
from state_and_helpers import get_param, update_results
from deflection import (
    calc_ief_simplified,
    calc_deflection_as3600,
    calc_span_depth_limit,
)


def compute_deflection_results(publish: bool = True) -> dict:
    """
    Compute deflection results using current session state values.
    Reads all inputs from get_param(), performs calculations, and updates results.
    No Streamlit UI - pure computation.
    """
    import streamlit as st
    
    # Read geometry
    b = get_param("b", 400.0)
    D = get_param("D", 600.0)
    L = get_param("L", 8000.0)  # mm
    L_m = L / 1000.0  # Convert to meters
    
    # Read materials
    fc = get_param("fc", 32.0)
    Ec = get_param("Ec", 30000.0)
    
    # Read reinforcement
    Ast = get_param("Ast_bot", 0.0)
    Asc = get_param("Ast_top", 0.0)
    d = get_param("d", 560.0)
    
    # Defensive: ensure critical parameters are not None (use defaults if needed)
    if b is None:
        b = 400.0
    if D is None:
        D = 600.0
    if L is None:
        L = 8000.0
        L_m = L / 1000.0
    if fc is None:
        fc = 32.0
    if Ec is None:
        Ec = 30000.0
    if Ast is None:
        Ast = 0.0
    if Asc is None:
        Asc = 0.0
    if d is None:
        d = 560.0
    
    # Read loads from SFD/BMD page (unified loading system)
    # Note: load_case is a widget key (st.selectbox), not a shared key
    load_case = get_param("sfd_case", "Simple beam – UDL over entire span")
    
    # For UDL cases, read g and q directly
    g_udl = get_param("g_udl_kNm_per_m", None)
    q_udl = get_param("q_udl_kNm_per_m", None)
    
    # For point load cases, convert to equivalent UDL
    P_sls = get_param("P_sls_kN", None)
    G_point = get_param("G_point_kN", None)
    Q_point = get_param("Q_point_kN", None)
    
    if g_udl is not None and q_udl is not None:
        # UDL case - use actual g and q
        g_equiv = g_udl
        q_equiv = q_udl
    elif G_point is not None and Q_point is not None and L_m > 0:
        # Point load case - convert to equivalent UDL
        # M = PL/4 = wL²/8 => w = 2P/L
        g_equiv = 2.0 * G_point / L_m if L_m > 0 else 0.0
        q_equiv = 2.0 * Q_point / L_m if L_m > 0 else 0.0
    else:
        # Fallback defaults
        g_equiv = 8.0
        q_equiv = 4.0
    
    psi_s = get_param("psi_udl", 0.4)  # Sustained factor (for UDL cases)
    if psi_s is None:
        psi_s = get_param("psi_point", 0.4)  # Fallback to point load psi
    if psi_s is None:
        psi_s = 0.4  # Final fallback
    
    # Read deflection page inputs (use defaults if not set)
    beff = get_param("defl_beff", b)  # Default to b if not set
    bw = get_param("defl_bw", b)  # Default to b if not set
    L_eff = get_param("defl_L_eff", L_m)  # Default to L_m if not set
    support_type = get_param("defl_support_type", "Simply supported")
    defl_limit_ratio = get_param("defl_limit_ratio", 250.0)
    Fdef_kNm = get_param("defl_Fdef", 12.0)
    
    # Defensive: ensure beff and bw are not None (fallback to b)
    if beff is None:
        beff = b
    if bw is None:
        bw = b
    if L_eff is None:
        L_eff = L_m
    if support_type is None:
        support_type = "Simply supported"
    if defl_limit_ratio is None:
        defl_limit_ratio = 250.0
    if Fdef_kNm is None:
        Fdef_kNm = 12.0
    
    # Simplified section properties (for I_ef calculation)
    # If beff/bw equal b, they're using the default (redundant check, but kept for clarity)
    if beff == b:  # If not explicitly set, use b
        beff = b
    if bw == b:  # If not explicitly set, use b
        bw = b
    
    # Calculate effective moment of inertia
    ief_data = calc_ief_simplified(fc, beff, bw, d, Ast)
    Ief = ief_data[0]
    beta = ief_data[1]
    p = ief_data[2]
    p_lim = ief_data[3]
    Ief_max = ief_data[4]
    k1 = ief_data[5]
    
    # Calculate deflection
    results = calc_deflection_as3600(
        L_m=L_eff,
        Ec=Ec,
        Ief=Ief,
        g_kNm=g_equiv,
        q_kNm=q_equiv,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )
    
    delta_total = results["delta_total"]
    delta_short_total = results["delta_short_total"]
    delta_short_sust = results["delta_short_sust"]
    delta_long_add = results["delta_long_add"]
    kcs = results["kcs"]
    w_total = results["w_total"]
    w_sust = results["w_sust"]
    k2 = results["k2"]
    L_mm = results["L_mm"]
    
    # Deflection limit (L/250 for beams)
    defl_limit = L_mm / defl_limit_ratio if defl_limit_ratio > 0 and L_mm > 0 else 0.0
    defl_util = delta_total / defl_limit if defl_limit > 0 else 0.0
    
    # Span/depth check
    L_over_d = (L_mm / d) if d > 0 else 0.0
    L_over_d_limit, k1_span, k2_span = calc_span_depth_limit(
        ief=Ief,
        beff=beff,
        bw=bw,
        d=d,
        fc=fc,
        Ec=Ec,
        Fdef_kNm=Fdef_kNm,
        support_type=support_type,
        defl_limit_ratio=defl_limit_ratio,
    )
    
    out = {
        "deflection_total_mm": delta_total,
        "deflection_limit_mm": defl_limit,
        "deflection_utilisation": defl_util,
        "delta_short_total": delta_short_total,
        "delta_long_add": delta_long_add,
        "delta_total": delta_total,
    }
    
    # Store detailed results for report building
    if publish:
        import streamlit as st
        if "results" not in st.session_state:
            st.session_state["results"] = {}
        
        # Store all computed values for build_deflection_report
        st.session_state["results"]["_deflection_params"] = {
            "Ief": Ief,
            "beta": beta,
            "p": p,
            "p_lim": p_lim,
            "Ief_max": Ief_max,
            "k1": k1,
            "delta_total": delta_total,
            "delta_short_total": delta_short_total,
            "delta_short_sust": delta_short_sust,
            "delta_long_add": delta_long_add,
            "kcs": kcs,
            "w_total": w_total,
            "w_sust": w_sust,
            "k2": k2,
            "L_mm": L_mm,
            "defl_limit": defl_limit,
            "defl_util": defl_util,
            "L_over_d": L_over_d,
            "L_over_d_limit": L_over_d_limit,
            "k1_span": k1_span,
            "k2_span": k2_span,
            "fc": fc,
            "Ec": Ec,
            "beff": beff,
            "bw": bw,
            "d": d,
            "Ast": Ast,
            "Asc": Asc,
            "psi_s": psi_s,
            "support_type": support_type,
            "defl_limit_ratio": defl_limit_ratio,
            "Fdef_kNm": Fdef_kNm,
            "ratio_Asc_Ast": (Asc / Ast) if Ast > 0 else 0.0,
        }
        
        # Build and store report
        try:
            report = build_deflection_report(st.session_state["results"]["_deflection_params"])
            st.session_state["results"]["deflection_report"] = report
        except Exception as e:
            st.session_state["results"]["deflection_report_error"] = str(e)
    
    update_results(**out)
    return out


def build_deflection_report(params: dict) -> dict:
    """
    Build the deflection report structure (tabs + calc boxes) from computed values.
    
    Args:
        params: Dict with all computed deflection values
    
    Returns:
        dict with module_title, summary, and tabs structure
    """
    from reporting.report_content import make_calc_box, make_tab
    import math
    
    # Extract parameters
    Ief = params.get("Ief", 0.0)
    beta = params.get("beta", 1.0)
    p = params.get("p", 0.0)
    p_lim = params.get("p_lim", 0.0)
    Ief_max = params.get("Ief_max", 0.0)
    k1 = params.get("k1", 0.0)
    delta_total = params.get("delta_total", 0.0)
    delta_short_total = params.get("delta_short_total", 0.0)
    delta_short_sust = params.get("delta_short_sust", 0.0)
    delta_long_add = params.get("delta_long_add", 0.0)
    kcs = params.get("kcs", 0.0)
    w_total = params.get("w_total", 0.0)
    w_sust = params.get("w_sust", 0.0)
    k2 = params.get("k2", 0.0)
    L_mm = params.get("L_mm", 0.0)
    defl_limit = params.get("defl_limit", 0.0)
    defl_util = params.get("defl_util", 0.0)
    L_over_d = params.get("L_over_d", 0.0)
    L_over_d_limit = params.get("L_over_d_limit", None)
    k1_span = params.get("k1_span", 0.0)
    k2_span = params.get("k2_span", 0.0)
    fc = params.get("fc", 32.0)
    Ec = params.get("Ec", 30000.0)
    beff = params.get("beff", 400.0)
    bw = params.get("bw", 400.0)
    d = params.get("d", 560.0)
    Ast = params.get("Ast", 0.0)
    Asc = params.get("Asc", 0.0)
    psi_s = params.get("psi_s", 0.4)
    support_type = params.get("support_type", "Simply supported")
    defl_limit_ratio = params.get("defl_limit_ratio", 250.0)
    Fdef_kNm = params.get("Fdef_kNm", 12.0)
    ratio_Asc_Ast = params.get("ratio_Asc_Ast", 0.0)
    
    # Build summary
    overall_pass = defl_util <= 1.0 if defl_util is not None else None
    outcome = "PASS" if overall_pass is True else "FAIL" if overall_pass is False else "N/A"
    summary = [
        ("Demand (δ)", f"{delta_total:.2f} mm"),
        ("Capacity (δ_limit)", f"{defl_limit:.2f} mm" if defl_limit > 0 else "—"),
        ("Utilisation", f"{defl_util:.2f}" if defl_util is not None else "—"),
        ("Outcome", outcome),
    ]
    
    # SLS tab calculations
    sls_boxes = []
    
    # Check 1: Effective stiffness I_ef
    sls_boxes.append(make_calc_box(
        "4.1",
        "Effective stiffness I_ef",
        "info",
        f"I_ef = {Ief:.3e} mm^4",
        "AS 3600:2018 Cl. 8.5.3.1",
        [
            {"label": "Width ratio", "eq": "β = b_ef / b_w", "sub": f"= {beff:.1f} / {bw:.1f} = {beta:.3f}"},
            {"label": "Reinforcement ratio", "eq": "p = A_st / (b_ef * d)", "sub": f"= {Ast:.0f} / ({beff:.1f} * {d:.1f}) = {p:.5f}"},
            {"label": "Limit ratio", "eq": "p_lim", "sub": f"= {p_lim:.5f}"},
            {"label": "k_1 factor", "eq": "k_1 = I_ef / (b_ef * d^3)", "sub": f"= {Ief:.3e} / ({beff:.1f} * {d:.1f}^3) = {k1:.5f}"},
            {"label": "I_ef", "eq": "I_ef = k_1 * b_ef * d^3", "sub": f"= {k1:.5f} * {beff:.1f} * {d:.1f}^3 = {Ief:.3e} mm^4"},
            {"label": "I_ef,max cap", "eq": "I_ef <= I_ef,max", "sub": f"= {Ief:.3e} <= {Ief_max:.3e} mm^4"},
        ],
    ))
    
    # Check 2: Short-term deflection
    status_short = "pass" if (defl_limit > 0 and delta_short_total <= defl_limit) else ("fail" if defl_limit > 0 else "info")
    sls_boxes.append(make_calc_box(
        "4.2",
        "Short-term deflection (total load)",
        status_short,
        f"δ_st,total = {delta_short_total:.2f} mm",
        "AS 3600:2018 Cl. 8.5.3.1",
        [
            {"label": "Total service load", "eq": "w = g + q", "sub": f"= {w_total:.2f} kN/m"},
            {"label": "Deflection constant", "eq": "k_2 (support type)", "sub": f"= {k2:.5f} ({support_type})"},
            {"label": "Short-term deflection", "eq": "δ_st,total = k_2 * w * L_ef^4 / (E_c,eff * I_ef)", "sub": f"= {k2:.5f} * {w_total:.2f} * {L_mm:.0f}^4 / ({Ec:.0f} * {Ief:.3e}) = {delta_short_total:.2f} mm"},
        ],
    ))
    
    # Check 3: Long-term deflection
    status_long = "pass" if (defl_limit > 0 and delta_long_add <= defl_limit) else ("fail" if defl_limit > 0 else "info")
    sls_boxes.append(make_calc_box(
        "4.3",
        "Additional long-term deflection",
        status_long,
        f"δ_LT,add = {delta_long_add:.2f} mm",
        "AS 3600:2018 Cl. 8.5.3.2",
        [
            {"label": "Sustained load", "eq": "w_sust = g + ψ_s * q", "sub": f"= {w_sust:.2f} kN/m"},
            {"label": "Steel ratio", "eq": "A_sc / A_st", "sub": f"= {ratio_Asc_Ast:.3f}"},
            {"label": "Creep/shrinkage multiplier", "eq": "k_cs = max[2 - 1.2*(A_sc/A_st), 0.8]", "sub": f"= max[2 - 1.2*{ratio_Asc_Ast:.3f}, 0.8] = {kcs:.2f}"},
            {"label": "Short-term sustained", "eq": "δ_st,sust = k_2 * w_sust * L_ef^4 / (E_c,eff * I_ef)", "sub": f"= {k2:.5f} * {w_sust:.2f} * {L_mm:.0f}^4 / ({Ec:.0f} * {Ief:.3e}) = {delta_short_sust:.2f} mm"},
            {"label": "Additional long-term", "eq": "δ_LT,add = k_cs * δ_st,sust", "sub": f"= {kcs:.2f} * {delta_short_sust:.2f} = {delta_long_add:.2f} mm"},
        ],
    ))
    
    # Check 4: Total deflection
    status_total = "pass" if overall_pass is True else ("fail" if overall_pass is False else "info")
    sls_boxes.append(make_calc_box(
        "4.4",
        "Total deflection (short + long-term)",
        status_total,
        f"δ_total = {delta_total:.2f} mm",
        "AS 3600:2018 Cl. 8.5.3.2",
        [
            {"label": "Total deflection", "eq": "δ_total = δ_st,total + δ_LT,add", "sub": f"= {delta_short_total:.2f} + {delta_long_add:.2f} = {delta_total:.2f} mm"},
            {"label": "Deflection limit", "eq": "δ_limit = L_ef / (L/Δ)", "sub": f"= {L_mm:.0f} / {defl_limit_ratio:.0f} = {defl_limit:.2f} mm"},
            {"label": "Check", "eq": "δ_total <= δ_limit", "sub": f"{delta_total:.2f} <= {defl_limit:.2f} = {overall_pass}"},
            {"label": "Utilisation", "eq": "Util = δ_total / δ_limit", "sub": f"= {delta_total:.2f} / {defl_limit:.2f} = {defl_util:.2f}"},
        ],
    ))
    
    # Check 5: Span/depth deemed-to-conform
    if L_over_d_limit is not None and L_over_d_limit > 0:
        span_passes = L_over_d <= L_over_d_limit
        status_span = "pass" if span_passes else "fail"
        sls_boxes.append(make_calc_box(
            "4.5",
            "Span-to-depth ratio L_ef/d",
            status_span,
            f"L_ef/d = {L_over_d:.1f} vs limit = {L_over_d_limit:.1f}",
            "AS 3600:2018 Cl. 8.5.4",
            [
                {"label": "Stiffness factor", "eq": "k_1 = I_ef / (b_ef * d^3)", "sub": f"= {k1_span:.5f}"},
                {"label": "Deflection limit", "eq": "Δ/L_ef = 1 / (L/Δ)", "sub": f"= 1 / {defl_limit_ratio:.0f}"},
                {"label": "Span/depth limit", "eq": "(L_ef/d)_limit = [k_1 * (Δ/L_ef) * b_ef * E_c,eff / (k_2 * F_d,ef)]^(1/3)", "sub": f"= [{k1_span:.5f} * (1/{defl_limit_ratio:.0f}) * {beff:.1f} * {Ec:.0f} / ({k2_span:.5f} * {Fdef_kNm:.2f})]^(1/3) = {L_over_d_limit:.1f}"},
                {"label": "Actual ratio", "eq": "L_ef/d", "sub": f"= {L_mm:.0f} / {d:.1f} = {L_over_d:.1f}"},
                {"label": "Check", "eq": "L_ef/d <= (L_ef/d)_limit", "sub": f"{L_over_d:.1f} <= {L_over_d_limit:.1f} = {span_passes}"},
            ],
        ))
    
    # Create SLS tab
    sls_tab = make_tab("SLS Checks", sls_boxes)
    
    return {
        "module_title": "Deflection (SLS)",
        "summary": summary,
        "tabs": [sls_tab],
    }


# Backward compatibility alias (for inputs_page.py)
_compute_deflection_results = compute_deflection_results
