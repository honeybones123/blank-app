# crack_core.py
# Core compute function for crack control (no Streamlit UI)

import math
from state_and_helpers import get_param, update_results
from crack_page import (
    table_sigma_max_A,
    table_sigma_max_B,
    calc_eps_diff,
    calc_sr_max,
)


def compute_crack_results(publish: bool = True) -> dict:
    """
    Compute crack control results using current session state values.
    Reads all inputs from get_param(), performs calculations, and updates results.
    No Streamlit UI - pure computation.
    """
    import streamlit as st
    
    # Read geometry
    b = get_param("b", 300.0)
    D = get_param("D", 600.0)
    cover_bot = get_param("cover_bot", 40.0)
    db_bot = get_param("db_bot", 20.0)
    s_bar_bot = get_param("s_bar_bot", 200.0)
    Ast = get_param("Ast_bot", 0.0)
    
    # Read materials
    fc = get_param("fc", 32.0)
    Ec = get_param("Ec", 30000.0)
    Es = get_param("Es", 200000.0)
    fsy = get_param("fsy", 500.0)
    
    # Read crack control settings
    exposure_class = get_param("exposure_class", "B1")
    wmax_choice = get_param("wmax_char_limit", 0.3)
    member_type = get_param("crack_member_type", "Primarily flexure")
    
    # Read linked SLS values
    sigma_sr = get_param("sigma_sr", None)
    if sigma_sr is None:
        sigma_sr = get_param("bending_sls_fs_outer", 0.0)
    phi_ce = get_param("phi_cc_t", 2.0)
    eps_cs_micro = get_param("eps_cs_total_micro", 300.0)
    eps_cs = eps_cs_micro * 1e-6
    
    # k1 and k2 from widgets
    k1 = get_param("crack_k1", 0.8)
    k2 = get_param("crk_k2", 0.5)
    
    # Effective area in tension
    c = cover_bot
    db = db_bot
    d_eff = D - c - db / 2.0
    height_eff = min(2.5 * c, max(D - d_eff, 0.0), D / 2.0)
    Aceff = b * max(height_eff, 1.0)
    rho_eff = Ast / Aceff if Aceff > 0 else 0.0
    
    # Table method (8.6.2.2)
    spacing = s_bar_bot
    sigma_table_A = table_sigma_max_A(db, wmax_choice)
    sigma_table_B = table_sigma_max_B(spacing, wmax_choice)
    
    if member_type == "Primarily tension":
        sigma_table_combined = sigma_table_A
    else:
        sigma_table_combined = max(sigma_table_A, sigma_table_B)
    
    sigma_08fsy = 0.8 * fsy
    sigma_allow_table = min(sigma_table_combined, sigma_08fsy)
    utilisation_table = sigma_sr / sigma_allow_table if sigma_allow_table > 0 else 0.0
    passes_table = utilisation_table <= 1.0
    
    # Direct calculation (8.6.2.3)
    fct_eff = 0.6 * math.sqrt(max(fc, 1.0))
    ne = (1.0 + phi_ce) * Es / Ec if Ec > 0 else 0.0
    
    eps_diff = calc_eps_diff(
        sigma_sr=sigma_sr,
        Es=Es,
        fct_eff=fct_eff,
        rho_eff=rho_eff,
        ne=ne,
        eps_cs=eps_cs,
    )
    
    sr_max = calc_sr_max(c_mm=c, db_mm=db, rho_eff=rho_eff, k1=k1, k2=k2)
    w_calc = sr_max * eps_diff
    utilisation_w = w_calc / wmax_choice if wmax_choice > 0 else 0.0
    passes_w = utilisation_w <= 1.0
    
    out = {
        "sigma_sr": sigma_sr,
        "sigma_allow_table": sigma_allow_table,
        "w_calc": w_calc,
        "wmax_char": wmax_choice,
        "passes_table": passes_table,
        "passes_w": passes_w,
        "crack_width": w_calc,
        "crack_utilisation": utilisation_w,
    }
    
    # Build report if publishing
    if publish:
        params = {
            "b": b, "D": D, "c": c, "db": db, "spacing": spacing, "Ast": Ast,
            "fc": fc, "Ec": Ec, "Es": Es, "fsy": fsy,
            "wmax_choice": wmax_choice, "member_type": member_type,
            "sigma_sr": sigma_sr, "phi_ce": phi_ce, "eps_cs": eps_cs,
            "k1": k1, "k2": k2,
            "Aceff": Aceff, "rho_eff": rho_eff, "fct_eff": fct_eff, "ne": ne,
            "sigma_table_A": sigma_table_A, "sigma_table_B": sigma_table_B,
            "sigma_table_combined": sigma_table_combined, "sigma_08fsy": sigma_08fsy,
            "sigma_allow_table": sigma_allow_table, "utilisation_table": utilisation_table,
            "passes_table": passes_table,
            "eps_diff": eps_diff, "sr_max": sr_max, "w_calc": w_calc,
            "utilisation_w": utilisation_w, "passes_w": passes_w,
        }
        try:
            report = build_crack_report(params)
            if "results" not in st.session_state:
                st.session_state["results"] = {}
            st.session_state["results"]["crack_report"] = report
        except Exception as e:
            if "results" not in st.session_state:
                st.session_state["results"] = {}
            st.session_state["results"]["crack_report_error"] = str(e)
    
    update_results(**out)
    return out


def build_crack_report(params: dict) -> dict:
    """
    Build the crack control report structure (tabs + calc boxes) from computed values.
    
    Args:
        params: Dict with all computed crack control values
    
    Returns:
        dict with module_title, summary, and tabs structure
    """
    from reporting.report_content import make_calc_box, make_tab
    import math
    
    # Extract parameters
    wmax_choice = params.get("wmax_choice", 0.3)
    sigma_sr = params.get("sigma_sr", 200.0)
    sigma_allow_table = params.get("sigma_allow_table", 0.0)
    utilisation_table = params.get("utilisation_table", 0.0)
    passes_table = params.get("passes_table", False)
    w_calc = params.get("w_calc", 0.0)
    utilisation_w = params.get("utilisation_w", 0.0)
    passes_w = params.get("passes_w", False)
    
    # Extract calculation details
    Aceff = params.get("Aceff", 0.0)
    rho_eff = params.get("rho_eff", 0.0)
    Ast = params.get("Ast", 0.0)
    fct_eff = params.get("fct_eff", 0.0)
    ne = params.get("ne", 0.0)
    eps_diff = params.get("eps_diff", 0.0)
    sr_max = params.get("sr_max", 0.0)
    c = params.get("c", 40.0)
    db = params.get("db", 20.0)
    k1 = params.get("k1", 0.8)
    k2 = params.get("k2", 0.5)
    Es = params.get("Es", 200000.0)
    Ec = params.get("Ec", 30000.0)
    phi_ce = params.get("phi_ce", 2.0)
    eps_cs_micro = params.get("eps_cs", 0.0) * 1e6
    sigma_table_A = params.get("sigma_table_A", 0.0)
    sigma_table_B = params.get("sigma_table_B", 0.0)
    sigma_table_combined = params.get("sigma_table_combined", 0.0)
    sigma_08fsy = params.get("sigma_08fsy", 0.0)
    member_type = params.get("member_type", "Primarily flexure")
    
    # Build summary
    overall_pass = passes_table and passes_w
    outcome = "PASS" if overall_pass else "FAIL"
    summary = [
        ("Demand (w)", f"{w_calc:.3f} mm"),
        ("Capacity (w_max)", f"{wmax_choice:.3f} mm"),
        ("Utilisation", f"{max(utilisation_table, utilisation_w):.2f}"),
        ("Outcome", outcome),
    ]
    
    # SLS tab calculations
    sls_boxes = []
    
    # Check 1: Inputs & limits
    sls_boxes.append(make_calc_box(
        "3.1",
        "Inputs & crack limits",
        "info",
        f"w'_max = {wmax_choice:.3f} mm, {member_type}",
        "AS 3600:2018 Cl. 8.6.2",
        [
            {"label": "Crack width limit", "eq": "w'_max", "sub": f"= {wmax_choice:.3f} mm"},
            {"label": "Member type", "eq": "Resultant action", "sub": f"= {member_type}"},
        ],
    ))
    
    # Check 2: Table method
    sls_boxes.append(make_calc_box(
        "3.2",
        "Table method — max steel stress σ_sr",
        "pass" if passes_table else "fail",
        f"σ_sr = {sigma_sr:.1f} MPa vs {sigma_allow_table:.1f} MPa",
        "AS 3600:2018 Cl. 8.6.2.2",
        [
            {"label": "Table 8.6.2.2(A)", "eq": "σ_max,A = f(d_b, w'_max)", "sub": f"= {sigma_table_A:.1f} MPa"},
            {"label": "Table 8.6.2.2(B)", "eq": "σ_max,B = f(s, w'_max)", "sub": f"= {sigma_table_B:.1f} MPa"},
            {"label": "Combined table limit", "eq": "σ_table = max(σ_max,A, σ_max,B)", "sub": f"= {sigma_table_combined:.1f} MPa"},
            {"label": "0.8*f_sy limit", "eq": "0.8*f_sy", "sub": f"= {sigma_08fsy:.1f} MPa"},
            {"label": "Allowable stress", "eq": "σ_allow = min(σ_table, 0.8*f_sy)", "sub": f"= {sigma_allow_table:.1f} MPa"},
            {"label": "Utilisation", "eq": "σ_sr / σ_allow", "sub": f"= {sigma_sr:.1f} / {sigma_allow_table:.1f} = {utilisation_table:.2f}"},
        ],
    ))
    
    # Check 3: Direct crack width calculation
    # Sub-step 3.1: Effective reinforcement ratio
    sls_boxes.append(make_calc_box(
        "3.3",
        "Effective reinforcement ratio ρ_eff",
        "info",
        f"ρ_eff = {rho_eff:.4f}",
        "AS 3600:2018 Cl. 8.6.2.3",
        [
            {"label": "Effective area", "eq": "A_c,eff = b*h_eff", "sub": f"= {Aceff:.0f} mm^2"},
            {"label": "Reinforcement ratio", "eq": "ρ_eff = A_s,t / A_c,eff", "sub": f"= {Ast:.0f} / {Aceff:.0f} = {rho_eff:.4f}"},
        ],
    ))
    
    # Sub-step 3.2: Difference in mean strain
    sls_boxes.append(make_calc_box(
        "3.4",
        "Difference in mean strain ε_sm - ε_cm",
        "info",
        f"ε_sm - ε_cm = {eps_diff:.3e}",
        "AS 3600:2018 Cl. 8.6.2.3(2)",
        [
            {"label": "Effective tensile strength", "eq": "f_ct,eff = 0.6*sqrt(f'c)", "sub": f"= {fct_eff:.2f} MPa"},
            {"label": "Modular ratio", "eq": "n_e = (1 + φ_ce)*E_s/E_c", "sub": f"= (1 + {phi_ce:.2f})*{Es:.0f}/{Ec:.0f} = {ne:.2f}"},
            {"label": "Strain difference", "eq": "ε_sm - ε_cm = σ_sr/E_s - 0.6*f_ct,eff/(E_s*ρ_eff)*(1+n_e*ρ_eff) + ε_cs", "sub": f"= {eps_diff:.3e}"},
        ],
    ))
    
    # Sub-step 3.3: Maximum crack spacing
    sls_boxes.append(make_calc_box(
        "3.5",
        "Maximum crack spacing s_r,max",
        "info",
        f"s_r,max = {sr_max:.1f} mm",
        "AS 3600:2018 Cl. 8.6.2.3(1)",
        [
            {"label": "Crack spacing", "eq": "s_r,max = 3.4*c + 0.3*k_1*k_2*d_b/ρ_eff", "sub": f"= 3.4*{c:.1f} + 0.3*{k1:.2f}*{k2:.2f}*{db:.1f}/{rho_eff:.4f} = {sr_max:.1f} mm"},
        ],
    ))
    
    # Sub-step 3.4: Crack width
    sls_boxes.append(make_calc_box(
        "3.6",
        "Direct crack width w",
        "pass" if passes_w else "fail",
        f"w = {w_calc:.3f} mm",
        "AS 3600:2018 Cl. 8.6.2.3",
        [
            {"label": "Crack width", "eq": "w = s_r,max*(ε_sm - ε_cm)", "sub": f"= {sr_max:.1f}*{eps_diff:.3e} = {w_calc:.3f} mm"},
            {"label": "Check", "eq": "w <= w'_max", "sub": f"{w_calc:.3f} <= {wmax_choice:.3f} = {passes_w}"},
            {"label": "Utilisation", "eq": "w / w'_max", "sub": f"= {w_calc:.3f} / {wmax_choice:.3f} = {utilisation_w:.2f}"},
        ],
    ))
    
    # Create SLS tab
    sls_tab = make_tab("SLS Checks", sls_boxes)
    
    return {
        "module_title": "Crack Control (SLS)",
        "summary": summary,
        "tabs": [sls_tab],
    }


# Backward compatibility alias
_compute_crack_results = compute_crack_results













